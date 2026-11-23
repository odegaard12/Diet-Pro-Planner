"""Legacy Strava helpers: token/OAuth-state files, kcal estimate, activity fetching and auto-sync.

Extracted from app.py without behaviour changes (the routes stay in app.py and are overridden by dpp_strava_v018).
It must not import ``app``: DB access goes through dpp_db and paths through dpp_config.
"""
from __future__ import annotations

import hmac
import json
import os
import secrets
import threading
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any

import requests

import dpp_config as config
import dpp_profile
import dpp_validate as v
from dpp_state import con, today_iso

DATA = config.DATA_DIR



# -----------------------------
# Strava integration (optional)
# -----------------------------
STRAVA_TOKEN_FILE = DATA / "strava_tokens.json"
STRAVA_STATE_FILE = DATA / "strava_oauth_state.txt"


def strava_config() -> dict[str, str]:
    return {
        "client_id": os.environ.get("STRAVA_CLIENT_ID", "").strip(),
        "client_secret": os.environ.get("STRAVA_CLIENT_SECRET", "").strip(),
        "redirect_uri": os.environ.get("STRAVA_REDIRECT_URI", "").strip(),
    }


def strava_configured() -> bool:
    cfg = strava_config()
    return bool(cfg["client_id"] and cfg["client_secret"] and cfg["redirect_uri"])


def read_strava_tokens() -> dict[str, Any] | None:
    if not STRAVA_TOKEN_FILE.exists():
        return None
    try:
        return json.loads(STRAVA_TOKEN_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None


def write_private_text(path: Path, text: str) -> None:
    """Atomic write of a secret file created with mode 600 (never world-readable, not even briefly)."""
    tmp = path.with_name(f".{path.name}.{secrets.token_hex(4)}.tmp")
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)
    try:
        path.chmod(0o600)
    except OSError:
        pass


def write_strava_tokens(tokens: dict[str, Any]) -> None:
    write_private_text(STRAVA_TOKEN_FILE, json.dumps(tokens, ensure_ascii=False, indent=2))


def estimate_strava_kcal(activity_type: str, minutes: float) -> float:
    # Estimación simple si Strava no devuelve calorías: MET x peso corporal actual.
    mets = {
        "Walk": 3.5,
        "Hike": 5.3,
        "Run": 8.5,
        "Ride": 6.5,
        "VirtualRide": 6.0,
        "Workout": 6.0,
        "WeightTraining": 4.8,
        "HIIT": 8.0,
    }
    met = mets.get(activity_type, 5.5)
    return dpp_profile.estimate_met_kcal(met, minutes)


def refresh_strava_if_needed(tokens: dict[str, Any]) -> dict[str, Any]:
    cfg = strava_config()
    if int(tokens.get("expires_at") or 0) > int(time.time()) + 120:
        return tokens
    r = requests.post(
        "https://www.strava.com/oauth/token",
        data={
            "client_id": cfg["client_id"],
            "client_secret": cfg["client_secret"],
            "grant_type": "refresh_token",
            "refresh_token": tokens.get("refresh_token"),
        },
        timeout=20,
    )
    r.raise_for_status()
    new_tokens = r.json()
    write_strava_tokens(new_tokens)
    return new_tokens


STRAVA_STATE_TTL_SECONDS = 30 * 60


def issue_strava_oauth_state() -> str:
    """Reuse a recent state so several open tabs share one valid connect link."""
    try:
        if STRAVA_STATE_FILE.exists() and time.time() - STRAVA_STATE_FILE.stat().st_mtime < STRAVA_STATE_TTL_SECONDS / 2:
            current = STRAVA_STATE_FILE.read_text(encoding="utf-8").strip()
            if len(current) >= 24:
                return current
    except OSError:
        pass
    state = secrets.token_urlsafe(24)
    write_private_text(STRAVA_STATE_FILE, state)
    return state


def consume_strava_oauth_state(received: str) -> bool:
    """One-time, constant-time, expiring check (rejects callbacks without a pending state)."""
    try:
        if not STRAVA_STATE_FILE.exists():
            return False
        expected = STRAVA_STATE_FILE.read_text(encoding="utf-8").strip()
        fresh = time.time() - STRAVA_STATE_FILE.stat().st_mtime < STRAVA_STATE_TTL_SECONDS
    except OSError:
        return False
    ok = bool(expected) and fresh and hmac.compare_digest(str(received or ""), expected)
    if ok:
        STRAVA_STATE_FILE.unlink(missing_ok=True)
    return ok


def _epoch_from_date(value: str, end: bool = False) -> int:
    if not value:
        return 0
    dt = datetime.strptime(value, "%Y-%m-%d")
    if end:
        dt = dt.replace(hour=23, minute=59, second=59)
    return int(dt.timestamp())



def _strava_fetch_activity_detail(access_token: str, activity_id: str) -> dict[str, Any] | None:
    """Fetch detailed activity data so calories match the Strava activity page when available."""
    if not activity_id:
        return None
    r = requests.get(
        f"https://www.strava.com/api/v3/activities/{activity_id}",
        headers={"Authorization": f"Bearer {access_token}"},
        params={"include_all_efforts": "false"},
        timeout=25,
    )
    if r.status_code in {401, 403, 404}:
        return None
    r.raise_for_status()
    data = r.json()
    return data if isinstance(data, dict) else None


def _strava_fetch_range(after_date: str, before_date: str, detailed: bool = True) -> list[dict[str, Any]]:
    tokens = read_strava_tokens()
    if not tokens:
        raise RuntimeError("Strava no conectado")
    tokens = refresh_strava_if_needed(tokens)
    access_token = tokens["access_token"]

    after = _epoch_from_date(after_date, False)
    before = _epoch_from_date(before_date, True) if before_date else int(time.time())

    out = []
    for page in range(1, 6):
        r = requests.get(
            "https://www.strava.com/api/v3/athlete/activities",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"after": after, "before": before, "page": page, "per_page": 100},
            timeout=25,
        )
        r.raise_for_status()
        batch = r.json()
        if not batch:
            break
        out.extend(batch)
        if len(batch) < 100:
            break

    if detailed:
        detailed_out = []
        for item in out:
            sid = str(item.get("id") or "")
            detail = None
            if sid:
                try:
                    detail = _strava_fetch_activity_detail(access_token, sid)
                except Exception:
                    detail = None
            if detail:
                merged = {**item, **detail}
                # Preserve local start fields if Strava detail omits them.
                for k in ("start_date", "start_date_local"):
                    if not merged.get(k) and item.get(k):
                        merged[k] = item.get(k)
                detailed_out.append(merged)
            else:
                detailed_out.append(item)
        out = detailed_out

    return out



def _strava_card(a: dict[str, Any]) -> dict[str, Any]:
    start = a.get("start_date_local") or a.get("start_date") or ""
    sid = str(a.get("id") or "")
    sport = a.get("sport_type") or a.get("type") or "Strava"
    typ = a.get("type") or sport
    title = a.get("name") or sport
    minutes = round(float(a.get("moving_time") or a.get("elapsed_time") or 0) / 60, 1)
    km = round(float(a.get("distance") or 0) / 1000, 2)

    kcal = 0.0
    for key in ("calories", "calorie", "kcal"):
        try:
            val = a.get(key)
            if val is not None and float(val) > 0:
                kcal = float(val)
                break
        except Exception:
            pass
    if kcal <= 0 and minutes:
        kcal = estimate_strava_kcal(typ, minutes)

    return {
        "id": sid,
        "date": start[:10],
        "time": start[11:16] if len(start) >= 16 else "12:00",
        "title": title,
        "type": typ,
        "sport_type": sport,
        "minutes": minutes,
        "distance_km": km,
        "kcal": round(kcal, 1),
        "url": f"https://www.strava.com/activities/{sid}" if sid else "",
    }


# V004_STRAVA_AUTO_SYNC

STRAVA_AUTO_FILE = DATA / "strava_auto_sync.json"
STRAVA_AUTO_LOCK = threading.Lock()
STRAVA_AUTO_THREAD_STARTED = False


def _auto_now_label() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def read_strava_auto_config() -> dict[str, Any]:
    base = {
        "enabled": False,
        "interval_minutes": 30,
        "after_date": "",
        "last_sync_at": "",
        "last_success_at": "",
        "last_message": "Aún no sincronizado automáticamente",
        "last_result": {},
        "_last_run_ts": 0,
    }
    if not STRAVA_AUTO_FILE.exists():
        return base
    try:
        data = json.loads(STRAVA_AUTO_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            base.update(data)
    except Exception:
        pass
    return base


def write_strava_auto_config(cfg: dict[str, Any]) -> None:
    STRAVA_AUTO_FILE.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


def _latest_strava_import_date() -> str:
    try:
        with con() as db:
            row = db.execute(
                """
                SELECT date FROM workouts
                WHERE notes LIKE 'Strava ·%id=%'
                ORDER BY date DESC, time DESC, id DESC
                LIMIT 1
                """
            ).fetchone()
        return row["date"] if row else ""
    except Exception:
        return ""


def _strava_import_all_in_range(after_date: str, before_date: str) -> dict[str, Any]:
    raw = _strava_fetch_range(after_date, before_date)
    imported = 0
    skipped = 0

    with con() as db:
        for item in raw:
            a = _strava_card(item)
            if not a.get("id"):
                continue

            found = db.execute(
                "SELECT id FROM workouts WHERE notes LIKE ? LIMIT 1",
                (f"%id={a['id']}%",),
            ).fetchone()
            notes = f"Strava · {a['title']} · id={a['id']} · kcal desde detalle Strava"
            if found:
                db.execute(
                    "UPDATE workouts SET minutes=?, distance_km=?, kcal=?, notes=? WHERE id=?",
                    (a["minutes"], a["distance_km"], a["kcal"], notes, found["id"]),
                )
                skipped += 1
                continue

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
            imported += 1

    return {"received": len(raw), "imported": imported, "skipped": skipped, "after_date": after_date, "before_date": before_date}


def run_strava_auto_sync(force: bool = False) -> dict[str, Any]:
    with STRAVA_AUTO_LOCK:
        cfg = read_strava_auto_config()
        if not force and not cfg.get("enabled"):
            return {"ok": True, "enabled": False, "message": "Sincronización automática desactivada"}

        if not read_strava_tokens():
            cfg["last_sync_at"] = _auto_now_label()
            cfg["last_message"] = "Strava no conectado"
            write_strava_auto_config(cfg)
            return {"ok": False, "error": "Strava no conectado"}

        after_date = (cfg.get("after_date") or _latest_strava_import_date() or date.fromtimestamp(time.time() - 14 * 86400).isoformat())
        before_date = today_iso()

        try:
            result = _strava_import_all_in_range(after_date, before_date)
            label = _auto_now_label()
            cfg["last_sync_at"] = label
            cfg["last_success_at"] = label
            cfg["last_message"] = f"Sincronizado correctamente a {label}"
            cfg["last_result"] = result
            cfg["_last_run_ts"] = int(time.time())
            write_strava_auto_config(cfg)
            return {"ok": True, **result, "message": cfg["last_message"]}
        except Exception as exc:
            label = _auto_now_label()
            cfg["last_sync_at"] = label
            cfg["last_message"] = f"Error sincronizando a {label}: {v.public_error(exc)}"
            cfg["_last_run_ts"] = int(time.time())
            write_strava_auto_config(cfg)
            return {"ok": False, "error": v.public_error(exc), "message": cfg["last_message"]}


def _strava_auto_loop() -> None:
    while True:
        try:
            cfg = read_strava_auto_config()
            if cfg.get("enabled"):
                interval = max(5, int(cfg.get("interval_minutes") or 30)) * 60
                last = int(cfg.get("_last_run_ts") or 0)
                if time.time() - last >= interval:
                    run_strava_auto_sync(force=True)
        except Exception as exc:
            try:
                cfg = read_strava_auto_config()
                cfg["last_sync_at"] = _auto_now_label()
                cfg["last_message"] = f"Error en auto-sync: {v.public_error(exc)}"
                write_strava_auto_config(cfg)
            except Exception:
                pass
        time.sleep(60)


def start_strava_auto_thread() -> None:
    global STRAVA_AUTO_THREAD_STARTED
    if STRAVA_AUTO_THREAD_STARTED:
        return
    STRAVA_AUTO_THREAD_STARTED = True
    t = threading.Thread(target=_strava_auto_loop, name="strava-auto-sync", daemon=True)
    t.start()
