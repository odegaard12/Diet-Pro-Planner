from __future__ import annotations

import json
import os
import re
import secrets
import sqlite3
import time
import urllib.parse
from pathlib import Path
from typing import Any

import requests
from flask import Flask, jsonify, request, send_from_directory
from werkzeug.utils import secure_filename
from PIL import Image
import pytesseract

import dpp_config as config
import dpp_db
import dpp_profile
import dpp_validate as v
from dpp_strava_legacy import (  # noqa: F401  (re-exported: dpp_strava_v018 and tests use legacy.<name>)
    STRAVA_TOKEN_FILE, STRAVA_STATE_FILE, strava_config, strava_configured, read_strava_tokens,
    write_private_text, write_strava_tokens, estimate_strava_kcal, refresh_strava_if_needed,
    STRAVA_STATE_TTL_SECONDS, issue_strava_oauth_state, consume_strava_oauth_state, _epoch_from_date,
    _strava_fetch_activity_detail, _strava_fetch_range, _strava_card, STRAVA_AUTO_FILE, STRAVA_AUTO_LOCK,
    _auto_now_label, read_strava_auto_config, write_strava_auto_config,
    _latest_strava_import_date, _strava_import_all_in_range, run_strava_auto_sync, _strava_auto_loop,
    start_strava_auto_thread,
)
from dpp_state import (  # noqa: F401  (re-exported: other modules and tests use legacy.<name>)
    today_iso, now_hm, con, rows, ensure_schema, upsert_food, seed_food_if_missing, get_food, calc_item,
    totals, _insert_meal_items, _client_id, _existing_by_client_id, create_meal, insert_meal,
    insert_meal_by_names, seed, fix_existing_data, init_db, meal_with_items, build_state,
)
from dpp_state import (  # noqa: F401  (re-exported: tests use app._dpp_v0141_*)
    _dpp_v0141_canonical_key, _dpp_v0141_fix_food_dict, _dpp_v0141_fix_strings, _dpp_v0141_sanitize_recursive, _dpp_v0141_sanitize_foods_list, _dpp_v0141_sanitize_state_payload,
)
from dpp_insights import (  # noqa: F401  (re-exported: tests and routes use app.<name>)
    _v012_safe_float, _v012_day_meals, _v012_day_workouts, _v012_meal_totals, _v012_workout_totals,
    _v012_latest_weight, _v012_official_weights, _v012_weight_summary, _v012_days_since_last_workout,
    _v012_week_summary, _v012_card, _v012_build_insights,
)
from dpp_nutrition import (  # noqa: F401  (re-exported: tests and routes use app.<name>)
    _fi_qident, _fi_float, _fi_round, _fi_dicts, _fi_cols, _fi_has_table, _fi_clean_text, _fi_get_rows,
    _fi_find_food, _fi_item_name, _fi_item_grams, _fi_macro_from_food, _fi_macro_from_item, _fi_item_macros,
    _fi_confidence, _fi_day_meals, _fi_day_workouts, _fi_sum_day, _fi_workout_totals, _fi_confidence_day,
    _fi_score_day, _fi_build_day, _fimp_norm, _fimp_foods, _fimp_match_food, _fimp_food_macro,
    _fimp_sum_items, _fimp_item, _fimp_pick, _fimp_plan_option, _fimp_make_options,
)
from dpp_ocr import (  # noqa: F401  (re-exported: other modules and tests use app._ocr3_*)
    _ocr3_basic_curado_payload, _ocr3_file_hash, _ocr3_generic_extract, _ocr3_load_cache,
    _ocr3_looks_basic_curado, _ocr3_norm, _ocr3_preprocess_fast, _ocr3_save_cache, _ocr3_text_fast,
)
from dpp_food_intel_rules import normalize_body_snapshot, normalize_food_intel_day
from dpp_validate import ApiError

config.ensure_dirs()
BASE = config.BASE_DIR
DATA = config.DATA_DIR
UPLOADS = config.UPLOADS_DIR
DB = config.DB_PATH

app = Flask(__name__, static_folder=str(BASE / "static"), static_url_path="/static")
app.config["MAX_CONTENT_LENGTH"] = config.MAX_UPLOAD_MB * 1024 * 1024


@app.get("/api/strava/status")
def api_strava_status():
    cfg = strava_config()
    tokens = read_strava_tokens()
    configured = strava_configured()
    connect_url = ""
    if configured:
        state = issue_strava_oauth_state()
        params = {
            "client_id": cfg["client_id"],
            "redirect_uri": cfg["redirect_uri"],
            "response_type": "code",
            "approval_prompt": "auto",
            "scope": "read,activity:read_all",
            "state": state,
        }
        connect_url = "https://www.strava.com/oauth/authorize?" + urllib.parse.urlencode(params)
    return jsonify({
        "configured": configured,
        "connected": bool(tokens and tokens.get("access_token")),
        "connect_url": connect_url,
        "message": "Configura STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET y STRAVA_REDIRECT_URI en .env" if not configured else "Listo para conectar Strava",
    })


@app.get("/api/strava/callback")
def api_strava_callback():
    if not strava_configured():
        return "Strava no configurado en .env", 400
    if not consume_strava_oauth_state(request.args.get("state", "")):
        return "Estado OAuth no válido o caducado; vuelve a pulsar Conectar Strava", 400
    code = request.args.get("code")
    if not code:
        return "Falta code de Strava", 400
    cfg = strava_config()
    r = requests.post(
        "https://www.strava.com/oauth/token",
        data={
            "client_id": cfg["client_id"],
            "client_secret": cfg["client_secret"],
            "code": code,
            "grant_type": "authorization_code",
        },
        timeout=20,
    )
    r.raise_for_status()
    write_strava_tokens(r.json())
    return "<h1>Strava conectado</h1><p>Ya puedes volver a Dieta Pro y pulsar Sincronizar Strava.</p>"


@app.post("/api/strava/sync")
def api_strava_sync():
    tokens = read_strava_tokens()
    if not tokens:
        return jsonify({"error": "Strava no conectado"}), 400
    tokens = refresh_strava_if_needed(tokens)
    days = int(v.number(v.json_body().get("days"), "days", default=14, minimum=1, maximum=365))
    after = int(time.time()) - days * 86400
    r = requests.get(
        "https://www.strava.com/api/v3/athlete/activities",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
        params={"after": after, "per_page": 50},
        timeout=25,
    )
    r.raise_for_status()
    activities = r.json()
    imported = 0
    with con() as db:
        for a in activities:
            start = (a.get("start_date_local") or a.get("start_date") or "")
            if not start:
                continue
            d = start[:10]
            tm = start[11:16] if len(start) >= 16 else "12:00"
            minutes = round(float(a.get("moving_time") or a.get("elapsed_time") or 0) / 60, 1)
            distance_km = round(float(a.get("distance") or 0) / 1000, 2)
            name = a.get("type") or a.get("sport_type") or "Strava"
            title = a.get("name") or name
            kcal = float(a.get("calories") or 0)
            if kcal <= 0 and minutes:
                kcal = estimate_strava_kcal(name, minutes)
            notes = f"Strava · {title} · id={a.get('id')}"
            cur = db.execute(
                "INSERT OR IGNORE INTO workouts(date,time,exercise_id,name,minutes,distance_km,kcal,notes) VALUES(?,?,?,?,?,?,?,?)",
                (d, tm, None, name, minutes, distance_km, kcal, notes),
            )
            if cur.rowcount:
                imported += 1
    return jsonify({"ok": True, "imported": imported, "received": len(activities)})


Image.MAX_IMAGE_PIXELS = 64_000_000  # above 2x this Pillow refuses to open (decompression bombs)


def save_uploaded_photo() -> tuple[Path, str]:
    """Validate and store the multipart ``photo`` field; returns (path, public_url)."""
    if "photo" not in request.files:
        raise ApiError("Falta archivo photo")
    file = request.files["photo"]
    if not file.filename:
        raise ApiError("Archivo vacío")
    ext = Path(secure_filename(file.filename)).suffix.lower()
    if ext not in {".jpg", ".jpeg", ".png", ".webp"}:
        raise ApiError("Formato no soportado (usa JPG, PNG o WEBP)")
    # Validate the content before anything is written to disk.
    try:
        with Image.open(file.stream) as img:
            detected = img.format
            img.verify()
        # The content must really be one of the allowed formats (not just the extension).
        if detected not in {"JPEG", "PNG", "WEBP", "MPO"}:
            raise ValueError("unsupported image format")
    except Image.DecompressionBombError:
        raise ApiError("Imagen demasiado grande; reduce la resolución de la foto", 413) from None
    except Exception:
        raise ApiError("El archivo no es una imagen válida") from None
    file.stream.seek(0)
    name = f"food-{int(time.time())}-{secrets.token_hex(4)}{ext}"
    path = UPLOADS / name
    file.save(path)
    return path, f"/uploads/{name}"


@app.post("/api/food-photo")
def api_food_photo():
    _path, url = save_uploaded_photo()
    return jsonify({"ok": True, "photo_path": url})


@app.get("/uploads/<name>")
def uploaded_file(name: str):
    if not name or Path(name).name != name or secure_filename(name) != name:
        return "", 404
    return send_from_directory(UPLOADS, name)


@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.get("/favicon.ico")
def favicon():
    return send_from_directory(app.static_folder, "icon-192.png", mimetype="image/png", max_age=86400)


@app.get("/api/state")
def api_state():
    return jsonify(build_state())


def _food_payload(d: dict[str, Any]) -> dict[str, Any]:
    name = v.text(d.get("name"), 160)
    if not name:
        raise ApiError("Falta nombre")
    per100 = {"kcal": 900, "protein": 100, "carbs": 100, "fat": 100, "sugar": 100, "salt": 100}
    food = {"name": name, "brand": v.text(d.get("brand"), 120)}
    for key, hi in per100.items():
        food[key] = round(v.number(d.get(key), key, default=0, maximum=hi), 2)
    food.update({
        "typical_g": round(v.number(d.get("typical_g"), "ración", default=100, minimum=0.1, maximum=5000), 1),
        "purchased": 1 if d.get("purchased") in (True, 1, "1", "true", "on") else 0,
        "source_note": v.text(d.get("source_note"), 2000),
        "notes": v.text(d.get("notes"), 1000),
        "photo_path": v.text(d.get("photo_path"), 200),
        "barcode": v.text(d.get("barcode"), 14),
    })
    if food["barcode"] and not re.fullmatch(r"\d{8,14}", food["barcode"]):
        raise ApiError("Código de barras no válido")
    if food["photo_path"] and not re.fullmatch(r"/uploads/[A-Za-z0-9._-]+", food["photo_path"]):
        raise ApiError("photo_path no válido")
    if food["protein"] + food["carbs"] + food["fat"] > 101:
        raise ApiError("Proteína + hidratos + grasa no pueden superar 100 g por 100 g")
    return food


@app.post("/api/foods")
def api_foods():
    food = _food_payload(v.json_body())
    with con() as db:
        upsert_food(db, food)
        row = db.execute("SELECT id FROM foods WHERE name=?", (food["name"],)).fetchone()
    return jsonify({"ok": True, "id": row["id"] if row else None})


@app.delete("/api/foods/<int:item_id>")
def delete_food(item_id: int):
    with con() as db:
        # meal_items keep their own name/grams/macros (food_id becomes NULL).
        cur = db.execute("DELETE FROM foods WHERE id=?", (item_id,))
    if not cur.rowcount:
        raise ApiError("Alimento no encontrado", 404)
    return jsonify({"ok": True})


def _weight_payload(d: dict[str, Any]) -> tuple:
    return (
        v.iso_date(d.get("date"), today_iso()),
        v.hhmm(d.get("time"), now_hm()),
        round(v.number(d.get("kg"), "kg", minimum=20, maximum=400), 2),
        1 if d.get("official") in (True, 1, "1", "true", "on") else 0,
        v.text(d.get("context"), 200),
    )


@app.post("/api/weights")
def api_weights():
    d = v.json_body()
    cid = _client_id(d)
    with con() as db:
        wid = _existing_by_client_id(db, "weights", cid)
        if wid is not None:  # retried offline POST: same record, nothing inserted
            return jsonify({"ok": True, "id": wid, "duplicate": False})
        cur = db.execute("INSERT OR IGNORE INTO weights(date,time,kg,official,context,client_id) VALUES(?,?,?,?,?,?)", (*_weight_payload(d), cid))
    return jsonify({"ok": True, "id": cur.lastrowid if cur.rowcount else None, "duplicate": not cur.rowcount})


@app.put("/api/weights/<int:item_id>")
def update_weight(item_id: int):
    with con() as db:
        cur = db.execute("UPDATE weights SET date=?,time=?,kg=?,official=?,context=? WHERE id=?", (*_weight_payload(v.json_body()), item_id))
    if not cur.rowcount:
        raise ApiError("Peso no encontrado", 404)
    return jsonify({"ok": True})


@app.delete("/api/weights/<int:item_id>")
def delete_weight(item_id: int):
    with con() as db:
        db.execute("DELETE FROM weights WHERE id=?", (item_id,))
    return jsonify({"ok": True})


def _meal_items_from_payload(db: sqlite3.Connection, items_in: Any) -> list[dict[str, Any]]:
    if not isinstance(items_in, list) or not items_in:
        raise ApiError("Añade alimentos")
    if len(items_in) > 60:
        raise ApiError("Demasiados alimentos en una comida")
    items = []
    for it in items_in:
        if not isinstance(it, dict):
            raise ApiError("Alimento no válido")
        food = None
        food_id = v.integer_id(it.get("food_id"), "food_id")
        if food_id is not None:
            r = db.execute("SELECT * FROM foods WHERE id=?", (food_id,)).fetchone()
            food = dict(r) if r else None
        if not food and it.get("food_name"):
            r = db.execute("SELECT * FROM foods WHERE name=?", (v.text(it.get("food_name"), 160),)).fetchone()
            food = dict(r) if r else None
        if not food:
            raise ApiError(f"Alimento no encontrado: {v.text(it.get('food_name') or it.get('food_id'), 80)}")
        # Empty or 0 grams falls back to the typical portion (as before v0.1.0).
        grams = v.number(it.get("grams"), "gramos", default=food["typical_g"], minimum=0, maximum=5000) or float(food["typical_g"] or 100)
        items.append(calc_item(food, grams))
    return items


def _meal_header(d: dict[str, Any]) -> dict[str, Any]:
    return {
        "date": v.iso_date(d.get("date"), today_iso()),
        "time": v.hhmm(d.get("time"), now_hm()),
        "name": v.text(d.get("name"), 60) or "Comida",
        "notes": v.text(d.get("notes"), 500),
    }


@app.post("/api/meals")
def api_meals():
    d = v.json_body()
    with con() as db:
        cid = _client_id(d)
        mid = _existing_by_client_id(db, "meals", cid)
        if mid is None:  # a retried offline POST that already arrived is not inserted again
            items = _meal_items_from_payload(db, d.get("items"))
            mid = create_meal(db, {**_meal_header(d), "client_id": cid}, items)
    return jsonify({"ok": True, "id": mid})


@app.put("/api/meals/<int:item_id>")
def update_meal(item_id: int):
    d = v.json_body()
    with con() as db:
        if not db.execute("SELECT 1 FROM meals WHERE id=?", (item_id,)).fetchone():
            raise ApiError("Comida no encontrada", 404)
        header = _meal_header(d)
        db.execute("UPDATE meals SET date=?,time=?,name=?,notes=? WHERE id=?", (header["date"], header["time"], header["name"], header["notes"], item_id))
        if "items" in d:
            items = _meal_items_from_payload(db, d.get("items"))
            db.execute("DELETE FROM meal_items WHERE meal_id=?", (item_id,))
            _insert_meal_items(db, item_id, items)
    return jsonify({"ok": True, "id": item_id})


@app.post("/api/meals/<int:item_id>/duplicate")
def duplicate_meal(item_id: int):
    """Repeat a logged meal (same items and grams) on another day/time."""
    d = v.json_body()
    with con() as db:
        meal = db.execute("SELECT * FROM meals WHERE id=?", (item_id,)).fetchone()
        if not meal:
            raise ApiError("Comida no encontrada", 404)
        items = rows(db.execute("SELECT * FROM meal_items WHERE meal_id=? ORDER BY id", (item_id,)))
        header = {
            "date": v.iso_date(d.get("date"), today_iso()),
            "time": v.hhmm(d.get("time"), meal["time"]),
            "name": meal["name"],
            "notes": meal["notes"] or "",
        }
        mid = create_meal(db, header, items)
    return jsonify({"ok": True, "id": mid})


@app.delete("/api/meals/<int:item_id>")
def delete_meal(item_id: int):
    with con() as db:
        db.execute("DELETE FROM meals WHERE id=?", (item_id,))
    return jsonify({"ok": True})


@app.post("/api/workouts")
def api_workouts():
    d = v.json_body()
    name = v.text(d.get("name"), 80) or "Entreno"
    minutes = v.number(d.get("minutes"), "minutos", default=0, maximum=1440)
    distance = v.number(d.get("distance_km"), "distancia", default=0, maximum=1000)
    kcal = v.number(d.get("kcal"), "kcal", default=0, maximum=15000)
    cid = _client_id(d)
    with con() as db:
        wid = _existing_by_client_id(db, "workouts", cid)
        if wid is not None:  # retried offline POST: return the stored record
            row = db.execute("SELECT kcal FROM workouts WHERE id=?", (wid,)).fetchone()
            return jsonify({"ok": True, "id": wid, "kcal": row["kcal"]})
        ex = db.execute("SELECT * FROM exercises WHERE name=?", (name,)).fetchone()
        ex_id = ex["id"] if ex else None
        if kcal <= 0 and ex and minutes:
            kcal = dpp_profile.estimate_met_kcal(float(ex["met"]), minutes)
        cur = db.execute(
            "INSERT OR IGNORE INTO workouts(date,time,exercise_id,name,minutes,distance_km,kcal,notes,client_id) VALUES(?,?,?,?,?,?,?,?,?)",
            (v.iso_date(d.get("date"), today_iso()), v.hhmm(d.get("time"), now_hm()), ex_id, name, minutes, distance, kcal, v.text(d.get("notes"), 500), cid),
        )
    return jsonify({"ok": True, "id": cur.lastrowid if cur.rowcount else None, "kcal": kcal})


@app.delete("/api/workouts/<int:item_id>")
def delete_workout(item_id: int):
    with con() as db:
        db.execute("DELETE FROM workouts WHERE id=?", (item_id,))
    return jsonify({"ok": True})


@app.post("/api/exercises")
def api_exercises():
    d = v.json_body()
    name = v.text(d.get("name"), 80)
    if not name:
        raise ApiError("Falta nombre")
    met = v.number(d.get("met"), "MET", default=5, minimum=1, maximum=25)
    with con() as db:
        db.execute("INSERT INTO exercises(name,met,kcal_per_min,notes) VALUES(?,?,?,?) ON CONFLICT(name) DO UPDATE SET met=excluded.met,notes=excluded.notes", (name, met, 0, v.text(d.get("notes"), 300)))
    return jsonify({"ok": True})


@app.post("/api/templates")
def api_templates():
    d = v.json_body()
    name = v.text(d.get("name"), 120)
    if not name:
        raise ApiError("Falta nombre de plantilla")
    raw = d.get("payload")
    try:
        payload = json.loads(raw) if isinstance(raw, str) else (raw or {})
    except json.JSONDecodeError:
        raise ApiError("Plantilla con JSON no válido") from None
    if not isinstance(payload, dict):
        raise ApiError("Plantilla no válida")
    with con() as db:
        db.execute("INSERT INTO templates(name,notes,kind,payload) VALUES(?,?,?,?) ON CONFLICT(name) DO UPDATE SET notes=excluded.notes,kind=excluded.kind,payload=excluded.payload", (name, v.text(d.get("notes"), 500), v.text(d.get("kind"), 20) or "meal", json.dumps(payload, ensure_ascii=False)))
    return jsonify({"ok": True})


@app.post("/api/plans")
def api_plans():
    d = v.json_body()
    raw = d.get("raw") or d.get("payload")
    try:
        payload = json.loads(raw) if isinstance(raw, str) else (raw or {})
    except json.JSONDecodeError as exc:
        raise ApiError(f"JSON no válido: {exc.msg} (línea {exc.lineno})") from None
    if not isinstance(payload, dict) or not isinstance(payload.get("days", []), list):
        raise ApiError("El plan debe ser un objeto con una lista 'days'")
    name = v.text(payload.get("name"), 120) or "Plan semanal"
    with con() as db:
        db.execute("INSERT INTO plans(name,payload) VALUES(?,?)", (name, json.dumps(payload, ensure_ascii=False)))
    return jsonify({"ok": True})


@app.get("/api/export")
def api_export():
    return jsonify(build_state())



# V002_STRAVA_MANUAL_IMPORT

@app.post("/api/strava/preview")
def api_strava_preview():
    d = v.json_body()
    after_date = v.iso_date(d.get("after_date"), today_iso(), "after_date")
    before_date = v.iso_date(d.get("before_date"), today_iso(), "before_date")
    try:
        raw = _strava_fetch_range(after_date, before_date)
        acts = [_strava_card(a) for a in raw if a.get("id")]

        with con() as db:
            for a in acts:
                found = db.execute(
                    "SELECT id FROM workouts WHERE notes LIKE ? LIMIT 1",
                    (f"%id={a['id']}%",),
                ).fetchone()
                a["already_imported"] = bool(found)

        return jsonify({"ok": True, "activities": acts, "received": len(acts)})
    except Exception as e:
        return jsonify({"error": v.public_error(e)}), 400


@app.post("/api/strava/import")
def api_strava_import():
    d = v.json_body()
    raw_ids = d.get("ids") or []
    if not isinstance(raw_ids, list) or len(raw_ids) > 500:
        raise ApiError("ids debe ser una lista")
    ids = {str(x) for x in raw_ids}
    if not ids:
        return jsonify({"error": "No seleccionaste actividades"}), 400

    after_date = v.iso_date(d.get("after_date"), today_iso(), "after_date")
    before_date = v.iso_date(d.get("before_date"), today_iso(), "before_date")

    try:
        raw = _strava_fetch_range(after_date, before_date)
        imported = 0
        skipped = 0

        with con() as db:
            for item in raw:
                a = _strava_card(item)
                if a["id"] not in ids:
                    continue

                notes = f"Strava · {a['title']} · id={a['id']}"
                before = db.total_changes
                db.execute(
                    """
                    INSERT OR IGNORE INTO workouts(date,time,exercise_id,name,minutes,distance_km,kcal,notes)
                    VALUES(?,?,?,?,?,?,?,?)
                    """,
                    (
                        a["date"],
                        a["time"],
                        None,
                        a["sport_type"],
                        a["minutes"],
                        a["distance_km"],
                        a["kcal"],
                        notes,
                    ),
                )

                if db.total_changes > before:
                    imported += 1
                else:
                    skipped += 1

        return jsonify({"ok": True, "imported": imported, "skipped": skipped})
    except Exception as e:
        return jsonify({"error": v.public_error(e)}), 400



# V003_STRAVA_LAST_ENDPOINT
@app.get("/api/strava/last")
def api_strava_last():
    with con() as db:
        row = db.execute(
            "SELECT date, time, name, notes FROM workouts WHERE notes LIKE 'Strava ·%' AND notes LIKE '%id=%' ORDER BY date DESC, time DESC, id DESC LIMIT 1"
        ).fetchone()
    if not row:
        return jsonify({"ok": True, "found": False})
    return jsonify({
        "ok": True,
        "found": True,
        "date": row["date"],
        "time": row["time"],
        "name": row["name"],
        "notes": row["notes"],
    })



@app.get("/api/strava/auto-status")
def api_strava_auto_status():
    cfg = read_strava_auto_config()
    cfg["latest_import_date"] = _latest_strava_import_date()
    return jsonify(cfg)


@app.post("/api/strava/auto-config")
def api_strava_auto_config():
    d = v.json_body()
    cfg = read_strava_auto_config()
    cfg["enabled"] = bool(d.get("enabled"))
    cfg["after_date"] = v.iso_date(d.get("after_date") or cfg.get("after_date") or _latest_strava_import_date(), today_iso(), "after_date")
    try:
        cfg["interval_minutes"] = max(5, min(1440, int(d.get("interval_minutes") or cfg.get("interval_minutes") or 30)))
    except Exception:
        cfg["interval_minutes"] = 30
    cfg["last_message"] = "Sincronización automática activada" if cfg["enabled"] else "Sincronización automática desactivada"
    write_strava_auto_config(cfg)
    start_strava_auto_thread()
    return jsonify({"ok": True, **cfg})


@app.post("/api/strava/auto-run")
def api_strava_auto_run():
    result = run_strava_auto_sync(force=True)
    status = 200 if result.get("ok") else 400
    return jsonify(result), status


# DPP_OCR3_START
# Local-only OCR3.
# Faster path:
# - SHA256 cache for repeated label photos.
# - One good OCR pass first; fallback only if text is poor.
# - Known-label correction for Eroski Basic "Curado Queso de mezcla".
# - Hard validation to avoid garbage values like protein=848 or salt=20.

@app.post("/api/food-photo-ocr")
def api_food_photo_ocr():
    path, photo_url = save_uploaded_photo()
    name = path.name
    file_hash = _ocr3_file_hash(path)
    cache = _ocr3_load_cache()

    if file_hash in cache:
        cached = cache[file_hash]
        cached = dict(cached)
        cached["ok"] = True
        cached["photo_path"] = f"/uploads/{name}"
        cached["cache_hit"] = True
        return jsonify(cached)

    try:
        text, mode = _ocr3_text_fast(path)
        text = _ocr3_norm(text)

        if _ocr3_looks_basic_curado(text):
            parsed = _ocr3_basic_curado_payload(text)
        else:
            parsed = _ocr3_generic_extract(text)

        response = {
            "ok": True,
            "photo_path": f"/uploads/{name}",
            "ocr_text": text,
            "ocr_engine": "tesseract-spa-eng-ocr3",
            "ocr_mode": mode,
            "cache_hit": False,
            **parsed,
        }

        cache[file_hash] = {k: v for k, v in response.items() if k not in {"ok", "photo_path"}}
        _ocr3_save_cache(cache)
        return jsonify(response)
    except Exception as exc:
        return jsonify({
            "ok": True,
            "photo_path": f"/uploads/{name}",
            "ocr_text": "",
            "nutrition": {},
            "product": {},
            "serving": {},
            "extra": {},
            "confidence": "error",
            "warnings": [v.public_error(exc, "No se pudo leer la etiqueta")],
            "ocr_error": v.public_error(exc, "No se pudo leer la etiqueta"),
            "ocr_engine": "tesseract-spa-eng-ocr3",
        })


@app.get("/api/ocr/status")
def api_ocr_status():
    try:
        version = str(pytesseract.get_tesseract_version())
        return jsonify({"ok": True, "engine": "tesseract", "version": version, "languages": "spa+eng", "parser": "ocr3"})
    except Exception as exc:
        return jsonify({"ok": False, "error": v.public_error(exc, "Tesseract no disponible")}), 500

# DPP_OCR3_END



# DPP_V012_INSIGHTS_START
# Dashboard inteligente v0.0.12.
# Backend local-first: calcula estado diario, semáforo y consejos sin depender del render JS.

# Targets now come from the editable profile: see dpp_profile.legacy_targets().

@app.get("/api/insights/today")
def api_v012_insights_today():
    d = request.args.get("date") or today_iso()
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", d):
        return jsonify({"error": "Fecha inválida"}), 400
    try:
        return jsonify(_v012_build_insights(d))
    except Exception as exc:
        return jsonify({"error": v.public_error(exc)}), 500

@app.get("/health")
def api_v012_health():
    return jsonify({"ok": True, "app": config.APP_NAME, "version": config.VERSION})
# DPP_V012_INSIGHTS_END

init_db()



# DPP_FOOD_INTEL_CORE_START
# v0.0.14.1 - Food Intelligence Core
# Backend only. No UI changes.

from datetime import date as _fi_date

# Targets now come from the editable profile: see dpp_profile.legacy_targets().

def _dpp_rules_response(data, rule):
    """Sort keys (as jsonify did), apply the pure rule, emit compact UTF-8 JSON like the removed hook."""
    def _sorted(o):
        if isinstance(o, dict):
            return {k: _sorted(o[k]) for k in sorted(o)}
        if isinstance(o, (list, tuple)):
            return [_sorted(x) for x in o]
        return o
    body = json.dumps(rule(_sorted(data)), ensure_ascii=False, separators=(",", ":"))
    resp = app.response_class(body)
    resp.headers["Content-Type"] = "application/json; charset=utf-8"
    resp.headers["Content-Length"] = str(len(body.encode("utf-8")))
    return resp

@app.route("/api/food-intel/day", methods=["GET", "POST"])
def api_food_intel_day():
    payload = {}
    if request.method == "POST":
        try:
            payload = v.json_body()
        except Exception:
            payload = {}

    d = v.iso_date(request.args.get("date") or payload.get("date"), _fi_date.today().isoformat())
    planned_workout = payload.get("planned_workout")
    if planned_workout is not None and not isinstance(planned_workout, dict):
        planned_workout = None

    # Soporte GET:
    # /api/food-intel/day?date=2026-06-02&planned_workout=1&planned_minutes=105&planned_sport=Funcional
    if not planned_workout and request.args.get("planned_workout"):
        planned_workout = {
            "sport": v.text(request.args.get("planned_sport"), 80) or "Entreno planificado",
            "duration_min": v.number(request.args.get("planned_minutes"), "planned_minutes", default=0, maximum=1440),
            "intensity": v.text(request.args.get("planned_intensity"), 20) or "moderate",
        }

    return _dpp_rules_response(_fi_build_day(d, planned_workout=planned_workout), normalize_food_intel_day)

@app.route("/api/food-intel/health")
def api_food_intel_health():
    return jsonify({
        "ok": True,
        "module": "food-intelligence",
        "version": "v0.0.14.1",
        "endpoints": [
            "/api/food-intel/day",
            "/api/food-intel/meal-plan",
            "/api/food-intel/health",
        ],
    })

# DPP_FOOD_INTEL_CORE_END




# DPP_FOOD_INTEL_MEAL_PLAN_START
# v0.0.14.1 - Food Intelligence Meal Planner
# Backend only. Uses local foods + day analysis. No UI changes.

@app.route("/api/food-intel/meal-plan", methods=["POST"])
def api_food_intel_meal_plan():
    payload = v.json_body()
    d = v.iso_date(payload.get("date"), _fi_date.today().isoformat())
    meal = v.text(payload.get("meal") or payload.get("slot"), 40) or "next"
    available_foods = payload.get("available_foods") or payload.get("inventory") or []
    if not isinstance(available_foods, list) or len(available_foods) > 1000:
        raise ApiError("available_foods debe ser una lista")
    if payload.get("planned_workout") is not None and not isinstance(payload.get("planned_workout"), dict):
        raise ApiError("planned_workout no válido")
    training_today = bool(payload.get("training_today") or payload.get("planned_workout"))

    current_day = _fi_build_day(d, planned_workout=payload.get("planned_workout") if training_today else None)
    return jsonify({
        "ok": True,
        "version": "v0.0.14.1-food-intel",
        "engine": "heuristic_local",
        "plan": _fimp_make_options(d, meal, available_foods, training_today, current_day),
        "day_analysis": {
            "score": current_day.get("analysis", {}).get("score"),
            "semaphore": current_day.get("analysis", {}).get("semaphore"),
            "confidence": current_day.get("confidence", {}),
            "summary": current_day.get("summary", {}),
        },
    })

# DPP_FOOD_INTEL_MEAL_PLAN_END




# DPP_BODY_SNAPSHOT_API_START
# v0.0.14.1 · Optional body snapshot API.
# Smart-scale body composition is treated as an estimated trend snapshot,
# not as a mandatory daily metric and not as a medical diagnosis.

@app.route("/api/body-snapshot/latest")
def api_body_snapshot_latest():
    from datetime import date as _date

    con = dpp_db.connect(DB)

    table = con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='body_composition'"
    ).fetchone()

    if not table:
        con.close()
        return _dpp_rules_response({
            "ok": True,
            "available": False,
            "version": "v0.0.14.1",
            "reason": "body_composition table not found"
        }, normalize_body_snapshot)

    latest = con.execute("""
        SELECT date, time
        FROM body_composition
        GROUP BY date, time
        ORDER BY date DESC, time DESC
        LIMIT 1
    """).fetchone()

    if not latest:
        con.close()
        return _dpp_rules_response({
            "ok": True,
            "available": False,
            "version": "v0.0.14.1",
            "reason": "no body composition records"
        }, normalize_body_snapshot)

    rows = con.execute("""
        SELECT metric, value, unit, source, confidence, notes
        FROM body_composition
        WHERE date=? AND time=?
        ORDER BY metric
    """, (latest["date"], latest["time"])).fetchall()

    previous = con.execute("""
        SELECT date, time
        FROM body_composition
        WHERE (date < ? OR (date = ? AND time < ?))
        GROUP BY date, time
        ORDER BY date DESC, time DESC
        LIMIT 1
    """, (latest["date"], latest["date"], latest["time"])).fetchone()

    prev_metrics = {}
    if previous:
        prev_rows = con.execute("""
            SELECT metric, value
            FROM body_composition
            WHERE date=? AND time=?
        """, (previous["date"], previous["time"])).fetchall()
        prev_metrics = {r["metric"]: r["value"] for r in prev_rows}

    con.close()

    metrics = {}
    for r in rows:
        metrics[r["metric"]] = {
            "value": r["value"],
            "unit": r["unit"] or "",
            "source": r["source"] or "",
            "confidence": r["confidence"] or "media",
            "notes": r["notes"] or ""
        }

    def val(key):
        try:
            return float((metrics.get(key) or {}).get("value") or 0)
        except Exception:
            return 0.0

    def pval(key):
        try:
            return float(prev_metrics.get(key) or 0)
        except Exception:
            return 0.0

    weight = val("weight")
    fat_pct = val("body_fat_pct")
    muscle = val("muscle_mass_kg")

    derived = {
        "fat_mass_kg": round(weight * fat_pct / 100.0, 2) if weight and fat_pct else None,
        "lean_mass_kg": round(weight - (weight * fat_pct / 100.0), 2) if weight and fat_pct else None,
        "muscle_weight_pct": round(muscle / weight * 100.0, 1) if muscle and weight else None,
    }

    deltas = {}
    for key in ["weight", "body_fat_pct", "water_pct", "muscle_mass_kg", "visceral_fat", "bmr_kcal", "biocharge_wakeup", "hrv"]:
        if key in metrics and key in prev_metrics:
            deltas[key] = round(val(key) - pval(key), 2)

    try:
        days_old = (_date.today() - _date.fromisoformat(latest["date"])).days
    except Exception:
        days_old = None

    if days_old is None:
        freshness = "unknown"
    elif days_old <= 2:
        freshness = "fresh"
    elif days_old <= 7:
        freshness = "recent"
    else:
        freshness = "old"

    return _dpp_rules_response({
        "ok": True,
        "available": True,
        "version": "v0.0.14.1",
        "date": latest["date"],
        "time": latest["time"],
        "freshness": {
            "days_old": days_old,
            "label": freshness
        },
        "metrics": metrics,
        "derived": derived,
        "deltas": deltas,
        "previous": {
            "date": previous["date"] if previous else None,
            "time": previous["time"] if previous else None
        },
        "message": "Foto corporal estimada por bioimpedancia. Usar tendencia semanal, no valor aislado."
    }, normalize_body_snapshot)

# DPP_BODY_SNAPSHOT_API_END



# DPP_V0141_API_STATE_SANITIZER_START
# v0.0.14.1 safety net: sanitize legacy catalog aliases in /api/state.
# This is intentionally response-level because some UI state can be built from
# more than one source, not only the current foods table.
import json as _dpp_v0141_json
from flask import request as _dpp_v0141_request

@app.after_request
def _dpp_v0141_after_request_sanitize_api_state(response):
    try:
        if _dpp_v0141_request.path != "/api/state" or response.status_code != 200:
            return response

        data = response.get_json(silent=True)
        if data is None:
            return response

        data = _dpp_v0141_sanitize_state_payload(data)
        # Modify in place so headers added by other hooks (security, caching) survive.
        response.set_data(_dpp_v0141_json.dumps(data, ensure_ascii=False))
        response.mimetype = "application/json"
        return response
    except Exception:
        return response
# DPP_V0141_API_STATE_SANITIZER_END



# DPP_BODY_TRENDS_V2_START
try:
    from dpp_body_trends import register_body_trends_routes
    register_body_trends_routes(app)
except Exception as exc:
    print(f"WARN: body trends routes not registered: {exc}")
# DPP_BODY_TRENDS_V2_END


# BEGIN DPP_SMART_COACH_ROUTE
try:
    from dpp_smart_coach import register_smart_coach_routes
    register_smart_coach_routes(app)
except Exception as exc:
    print("WARN: smart coach routes disabled:", exc)
# END DPP_SMART_COACH_ROUTE

if __name__ == "__main__":
    start_strava_auto_thread()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8099")), debug=False)
