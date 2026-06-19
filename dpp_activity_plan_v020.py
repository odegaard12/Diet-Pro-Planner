from __future__ import annotations

import ipaddress
import re
import sqlite3
import unicodedata
from datetime import date, datetime, timedelta
from typing import Any

from flask import jsonify, request


VERSION = "v0.0.20-dev"
VALID_INTENSITIES = {"easy", "moderate", "hard", "recovery"}
VALID_MANUAL_STATUSES = {"planned", "skipped", "cancelled"}


def _plain(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(ch for ch in text if not unicodedata.combining(ch)).lower().strip()


def _category(value: Any) -> str:
    text = _plain(value)
    rules = (
        ("padel", ("padel", "pádel")),
        ("run", ("run", "carrera", "carreira", "correr", "running", "cinta")),
        ("walk", ("walk", "paseo", "caminata", "caminar", "hike", "sender")),
        ("bike", ("ride", "bike", "bici", "bicicleta", "mountainbike")),
        ("strength", ("weight", "fuerza", "pesas", "gimnasio", "tren superior", "tren inferior")),
        ("hiit", ("hiit", "high intensity", "interval")),
        ("mobility", ("movilidad", "mobility", "core", "estir")),
        ("workout", ("workout", "funcional", "entrenamiento", "training")),
        ("swim", ("swim", "natacion", "natación")),
    )
    for category, words in rules:
        if any(word in text for word in words):
            return category
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-") or "other"


def _private_request() -> bool:
    raw = request.headers.get("X-Forwarded-For", request.remote_addr or "")
    raw = raw.split(",", 1)[0].strip()
    try:
        address = ipaddress.ip_address(raw)
        return bool(address.is_private or address.is_loopback or address.is_link_local)
    except ValueError:
        return raw in {"localhost", "srv-web-01"}


def _iso_day(value: Any, fallback: str | None = None) -> str:
    raw = str(value or fallback or "").strip()
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date().isoformat()
    except ValueError as exc:
        raise ValueError("Fecha no válida; usa YYYY-MM-DD") from exc


def _hm(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        return datetime.strptime(raw, "%H:%M").strftime("%H:%M")
    except ValueError as exc:
        raise ValueError("Hora no válida; usa HH:MM") from exc


def _number(value: Any, default: float = 0.0, minimum: float = 0.0, maximum: float = 100000.0) -> float:
    try:
        number = float(value if value not in (None, "") else default)
    except (TypeError, ValueError):
        number = default
    return round(min(maximum, max(minimum, number)), 2)


def _ensure_schema(db: sqlite3.Connection) -> None:
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS activity_plans(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          date TEXT NOT NULL,
          time TEXT NOT NULL DEFAULT '',
          title TEXT NOT NULL,
          sport_type TEXT NOT NULL DEFAULT 'Workout',
          minutes REAL NOT NULL DEFAULT 0,
          distance_km REAL NOT NULL DEFAULT 0,
          target_kcal REAL NOT NULL DEFAULT 0,
          intensity TEXT NOT NULL DEFAULT 'moderate',
          notes TEXT NOT NULL DEFAULT '',
          manual_status TEXT NOT NULL DEFAULT 'planned',
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    db.execute("CREATE INDEX IF NOT EXISTS idx_activity_plans_date ON activity_plans(date)")
    db.commit()


def _plan_payload(payload: dict[str, Any], existing: dict[str, Any] | None = None) -> dict[str, Any]:
    base = dict(existing or {})
    title = str(payload.get("title", base.get("title", ""))).strip()[:120]
    sport_type = str(payload.get("sport_type", base.get("sport_type", title or "Workout"))).strip()[:80]
    if not title:
        title = sport_type or "Entreno"
    intensity = _plain(payload.get("intensity", base.get("intensity", "moderate")))
    if intensity not in VALID_INTENSITIES:
        intensity = "moderate"
    manual_status = _plain(payload.get("manual_status", base.get("manual_status", "planned")))
    if manual_status not in VALID_MANUAL_STATUSES:
        manual_status = "planned"
    return {
        "date": _iso_day(payload.get("date"), base.get("date") or date.today().isoformat()),
        "time": _hm(payload.get("time", base.get("time", ""))),
        "title": title,
        "sport_type": sport_type or "Workout",
        "minutes": _number(payload.get("minutes", base.get("minutes", 0)), maximum=1440),
        "distance_km": _number(payload.get("distance_km", base.get("distance_km", 0)), maximum=1000),
        "target_kcal": _number(payload.get("target_kcal", base.get("target_kcal", 0)), maximum=10000),
        "intensity": intensity,
        "notes": str(payload.get("notes", base.get("notes", ""))).strip()[:1000],
        "manual_status": manual_status,
    }


def _time_minutes(value: Any) -> int | None:
    raw = str(value or "")
    try:
        hh, mm = raw[:5].split(":")
        return int(hh) * 60 + int(mm)
    except Exception:
        return None


def _word_overlap(left: Any, right: Any) -> int:
    stop = {"de", "del", "la", "el", "por", "con", "al", "y", "entreno", "entrenamiento"}
    a = {word for word in re.findall(r"[a-z0-9]+", _plain(left)) if len(word) > 2 and word not in stop}
    b = {word for word in re.findall(r"[a-z0-9]+", _plain(right)) if len(word) > 2 and word not in stop}
    return len(a & b)


def _match_score(plan: dict[str, Any], workout: dict[str, Any]) -> float:
    same_category = _category(plan.get("sport_type") or plan.get("title")) == _category(
        workout.get("name") or workout.get("notes")
    )
    score = 100.0 if same_category else 0.0
    score += min(24, _word_overlap(
        f"{plan.get('title', '')} {plan.get('sport_type', '')}",
        f"{workout.get('name', '')} {workout.get('notes', '')}",
    ) * 8)
    plan_minutes = float(plan.get("minutes") or 0)
    actual_minutes = float(workout.get("minutes") or 0)
    if plan_minutes and actual_minutes:
        score += max(0, 20 - abs(plan_minutes - actual_minutes) / max(5, plan_minutes) * 20)
    plan_time = _time_minutes(plan.get("time"))
    actual_time = _time_minutes(workout.get("time"))
    if plan_time is not None and actual_time is not None:
        score += max(0, 12 - abs(plan_time - actual_time) / 30)
    return round(score, 2)


def _match_plans(
    plans: list[dict[str, Any]],
    workouts: list[dict[str, Any]],
    today_value: str | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    today_iso = _iso_day(today_value, date.today().isoformat())
    workouts_by_day: dict[str, list[dict[str, Any]]] = {}
    for workout in workouts:
        workouts_by_day.setdefault(str(workout.get("date") or ""), []).append(dict(workout))

    used: set[int] = set()
    output: list[dict[str, Any]] = []
    for raw_plan in sorted(plans, key=lambda item: (str(item.get("date")), str(item.get("time")), int(item.get("id") or 0))):
        plan = dict(raw_plan)
        manual = str(plan.get("manual_status") or "planned")
        plan["matched_workout"] = None
        plan["match_score"] = None

        if manual in {"cancelled", "skipped"}:
            plan["status"] = manual
            output.append(plan)
            continue

        candidates = [
            workout for workout in workouts_by_day.get(str(plan.get("date")), [])
            if int(workout.get("id") or 0) not in used
        ]
        same = [
            workout for workout in candidates
            if _category(plan.get("sport_type") or plan.get("title")) == _category(workout.get("name") or workout.get("notes"))
        ]
        pool = same or candidates
        match = max(pool, key=lambda workout: _match_score(plan, workout), default=None)
        score = _match_score(plan, match) if match else 0

        if match and (same or score >= 18):
            used.add(int(match.get("id") or 0))
            plan["matched_workout"] = match
            plan["match_score"] = score
            plan["status"] = "completed" if same else "changed"
        elif str(plan.get("date")) > today_iso:
            plan["status"] = "upcoming"
        elif str(plan.get("date")) == today_iso:
            plan["status"] = "pending"
        else:
            plan["status"] = "missed"
        output.append(plan)

    extras = [workout for workout in workouts if int(workout.get("id") or 0) not in used]
    return output, extras


def _summary(plans: list[dict[str, Any]], workouts: list[dict[str, Any]], today_value: str | None = None) -> dict[str, Any]:
    today_iso = _iso_day(today_value, date.today().isoformat())
    counts = {key: 0 for key in ("completed", "changed", "missed", "pending", "upcoming", "skipped", "cancelled")}
    for plan in plans:
        status = str(plan.get("status") or "pending")
        counts[status] = counts.get(status, 0) + 1
    eligible = sum(
        1 for plan in plans
        if str(plan.get("date")) <= today_iso and plan.get("status") not in {"cancelled", "skipped"}
    )
    fulfilled = counts["completed"] + counts["changed"]
    return {
        **counts,
        "planned": len(plans),
        "eligible": eligible,
        "fulfilled": fulfilled,
        "adherence_pct": round(fulfilled / eligible * 100) if eligible else None,
        "planned_minutes": round(sum(float(plan.get("minutes") or 0) for plan in plans), 1),
        "real_minutes": round(sum(float(workout.get("minutes") or 0) for workout in workouts), 1),
        "real_kcal": round(sum(float(workout.get("kcal") or 0) for workout in workouts), 1),
    }


def register_activity_plan_v020(app, legacy) -> None:
    with legacy.con() as db:
        _ensure_schema(db)

    def list_payload() -> dict[str, Any]:
        start = _iso_day(request.args.get("from"), (date.today() - timedelta(days=7)).isoformat())
        end = _iso_day(request.args.get("to"), (date.today() + timedelta(days=14)).isoformat())
        if end < start:
            start, end = end, start
        with legacy.con() as db:
            _ensure_schema(db)
            plans = [dict(row) for row in db.execute(
                "SELECT * FROM activity_plans WHERE date BETWEEN ? AND ? ORDER BY date,time,id",
                (start, end),
            ).fetchall()]
            workouts = [dict(row) for row in db.execute(
                "SELECT * FROM workouts WHERE date BETWEEN ? AND ? ORDER BY date,time,id",
                (start, end),
            ).fetchall()]
        matched, extras = _match_plans(plans, workouts)
        return {
            "ok": True,
            "version": VERSION,
            "from": start,
            "to": end,
            "plans": matched,
            "extra_workouts": extras,
            "summary": _summary(matched, workouts),
        }

    @app.get("/api/activity-plan")
    def activity_plan_list():
        return jsonify(list_payload())

    @app.post("/api/activity-plan")
    def activity_plan_create():
        if not _private_request():
            return jsonify({"ok": False, "error": "La planificación solo se puede editar desde la red local"}), 403
        try:
            item = _plan_payload(request.get_json(silent=True) or {})
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        with legacy.con() as db:
            _ensure_schema(db)
            cur = db.execute(
                """
                INSERT INTO activity_plans(date,time,title,sport_type,minutes,distance_km,target_kcal,intensity,notes,manual_status,updated_at)
                VALUES(:date,:time,:title,:sport_type,:minutes,:distance_km,:target_kcal,:intensity,:notes,:manual_status,CURRENT_TIMESTAMP)
                """,
                item,
            )
            item_id = int(cur.lastrowid)
            db.commit()
            row = dict(db.execute("SELECT * FROM activity_plans WHERE id=?", (item_id,)).fetchone())
        return jsonify({"ok": True, "version": VERSION, "message": "Actividad planificada guardada", "plan": row})

    @app.put("/api/activity-plan/<int:item_id>")
    def activity_plan_update(item_id: int):
        if not _private_request():
            return jsonify({"ok": False, "error": "La planificación solo se puede editar desde la red local"}), 403
        with legacy.con() as db:
            _ensure_schema(db)
            current = db.execute("SELECT * FROM activity_plans WHERE id=?", (item_id,)).fetchone()
            if not current:
                return jsonify({"ok": False, "error": "Actividad planificada no encontrada"}), 404
            try:
                item = _plan_payload(request.get_json(silent=True) or {}, dict(current))
            except ValueError as exc:
                return jsonify({"ok": False, "error": str(exc)}), 400
            db.execute(
                """
                UPDATE activity_plans SET
                  date=:date,time=:time,title=:title,sport_type=:sport_type,minutes=:minutes,
                  distance_km=:distance_km,target_kcal=:target_kcal,intensity=:intensity,
                  notes=:notes,manual_status=:manual_status,updated_at=CURRENT_TIMESTAMP
                WHERE id=:id
                """,
                {**item, "id": item_id},
            )
            db.commit()
            row = dict(db.execute("SELECT * FROM activity_plans WHERE id=?", (item_id,)).fetchone())
        return jsonify({"ok": True, "version": VERSION, "message": "Plan actualizado", "plan": row})

    @app.post("/api/activity-plan/<int:item_id>/status")
    def activity_plan_status(item_id: int):
        if not _private_request():
            return jsonify({"ok": False, "error": "La planificación solo se puede editar desde la red local"}), 403
        status = _plain((request.get_json(silent=True) or {}).get("status"))
        if status not in VALID_MANUAL_STATUSES:
            return jsonify({"ok": False, "error": "Estado no válido"}), 400
        with legacy.con() as db:
            _ensure_schema(db)
            cur = db.execute(
                "UPDATE activity_plans SET manual_status=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (status, item_id),
            )
            db.commit()
        if not cur.rowcount:
            return jsonify({"ok": False, "error": "Actividad planificada no encontrada"}), 404
        return jsonify({"ok": True, "version": VERSION, "message": "Estado actualizado"})

    @app.delete("/api/activity-plan/<int:item_id>")
    def activity_plan_delete(item_id: int):
        if not _private_request():
            return jsonify({"ok": False, "error": "La planificación solo se puede editar desde la red local"}), 403
        with legacy.con() as db:
            _ensure_schema(db)
            cur = db.execute("DELETE FROM activity_plans WHERE id=?", (item_id,))
            db.commit()
        if not cur.rowcount:
            return jsonify({"ok": False, "error": "Actividad planificada no encontrada"}), 404
        return jsonify({"ok": True, "version": VERSION, "message": "Actividad planificada eliminada"})

    for rule in list(app.url_map.iter_rules()):
        if rule.rule == "/health":
            app.view_functions[rule.endpoint] = lambda: jsonify(
                {"app": "Diet Pro Planner", "ok": True, "version": VERSION}
            )
            break
