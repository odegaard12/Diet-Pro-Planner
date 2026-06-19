"""
Diet Pro Planner — Weight & Body Composition 2.0 backend.

Adds:
- GET /api/body-trends?days=30
- GET /weight-2

The module is schema-tolerant and reads local SQLite data only.
"""

from __future__ import annotations

import os
import sqlite3
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from flask import jsonify, request, send_from_directory


def _db_path() -> str:
    candidates = [
        os.environ.get("DPP_DB_PATH"),
        os.environ.get("DATABASE_PATH"),
        "data/dieta.db",
        "data/diet.db",
        "data/app.db",
        "/app/data/dieta.db",
        "/app/data/diet.db",
        "/app/data/app.db",
    ]
    for item in candidates:
        if item and Path(item).exists():
            return item
    return "data/dieta.db"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def _columns(conn: sqlite3.Connection, table: str) -> List[str]:
    if not _table_exists(conn, table):
        return []
    return [str(r["name"]) for r in conn.execute(f'PRAGMA table_info("{table}")')]


def _pick(cols: Iterable[str], names: Iterable[str]) -> Optional[str]:
    lowered = {c.lower(): c for c in cols}
    for name in names:
        if name.lower() in lowered:
            return lowered[name.lower()]
    return None


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(str(value).replace(",", "."))
    except Exception:
        return None


def _safe_int(value: Any) -> Optional[int]:
    number = _safe_float(value)
    if number is None:
        return None
    return int(round(number))


def _date_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    # Accept YYYY-MM-DD or datetime-like strings.
    if len(raw) >= 10 and raw[4:5] == "-" and raw[7:8] == "-":
        return raw[:10]
    return raw


def _time_str(value: Any) -> str:
    if value is None:
        return ""
    raw = str(value).strip()
    if not raw:
        return ""
    if "T" in raw and len(raw.split("T", 1)[1]) >= 5:
        return raw.split("T", 1)[1][:5]
    if " " in raw and len(raw.split(" ", 1)[1]) >= 5:
        return raw.split(" ", 1)[1][:5]
    return raw[:5]


def _parse_day(value: str) -> Optional[date]:
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d").date()
    except Exception:
        return None


def _range_from_request() -> Tuple[str, str, int]:
    today = date.today()
    days = request.args.get("days", "45")
    try:
        days_i = max(7, min(365, int(days)))
    except Exception:
        days_i = 45

    end_s = request.args.get("to")
    start_s = request.args.get("from")

    end = _parse_day(end_s) if end_s else today
    if end is None:
        end = today

    start = _parse_day(start_s) if start_s else end - timedelta(days=days_i - 1)
    if start is None:
        start = end - timedelta(days=days_i - 1)

    return start.isoformat(), end.isoformat(), (end - start).days + 1


def _series_summary(items: List[Dict[str, Any]], value_key: str = "value") -> Dict[str, Any]:
    valid = [x for x in items if _safe_float(x.get(value_key)) is not None]
    if not valid:
        return {
            "count": 0,
            "latest": None,
            "previous": None,
            "first": None,
            "delta_from_first": None,
            "delta_from_previous": None,
            "direction": "flat",
        }

    first = valid[0]
    latest = valid[-1]
    previous = valid[-2] if len(valid) >= 2 else None

    latest_v = _safe_float(latest.get(value_key))
    first_v = _safe_float(first.get(value_key))
    prev_v = _safe_float(previous.get(value_key)) if previous else None

    delta_first = None if latest_v is None or first_v is None else round(latest_v - first_v, 2)
    delta_prev = None if latest_v is None or prev_v is None else round(latest_v - prev_v, 2)

    direction = "flat"
    if delta_first is not None:
        if delta_first < -0.05:
            direction = "down"
        elif delta_first > 0.05:
            direction = "up"

    return {
        "count": len(valid),
        "latest": latest,
        "previous": previous,
        "first": first,
        "delta_from_first": delta_first,
        "delta_from_previous": delta_prev,
        "direction": direction,
    }


def _read_weights(conn: sqlite3.Connection, start: str, end: str) -> Dict[str, Any]:
    cols = _columns(conn, "weights")
    if not cols:
        return {"items": [], "official": [], "reference": [], "summary": {}, "meta": {"table": None}}

    date_col = _pick(cols, ["date", "day", "created_date", "measured_date", "record_date"])
    time_col = _pick(cols, ["time", "hour", "created_time", "measured_time"])
    kg_col = _pick(cols, ["kg", "weight", "weight_kg", "value"])
    official_col = _pick(cols, ["official", "is_official", "isOfficial"])
    context_col = _pick(cols, ["context", "notes", "note", "source"])

    if not date_col or not kg_col:
        return {"items": [], "official": [], "reference": [], "summary": {}, "meta": {"table": "weights", "error": "missing date/kg columns"}}

    select_cols = [date_col, kg_col]
    for c in [time_col, official_col, context_col]:
        if c and c not in select_cols:
            select_cols.append(c)

    sql = f'''
        SELECT {", ".join(f'"{c}"' for c in select_cols)}
        FROM "weights"
        WHERE "{date_col}" >= ? AND "{date_col}" <= ?
        ORDER BY "{date_col}" ASC {',' + '"' + time_col + '" ASC' if time_col else ''}
    '''
    rows = conn.execute(sql, (start, end)).fetchall()

    items: List[Dict[str, Any]] = []
    for row in rows:
        d = _date_str(row[date_col])
        kg = _safe_float(row[kg_col])
        if not d or kg is None:
            continue
        official = bool(row[official_col]) if official_col else True
        item = {
            "date": d,
            "time": _time_str(row[time_col]) if time_col else "",
            "kg": round(kg, 2),
            "value": round(kg, 2),
            "official": official,
            "type": "official" if official else "reference",
            "context": str(row[context_col] or "") if context_col else "",
        }
        items.append(item)

    official_items = [x for x in items if x["official"]]
    reference_items = [x for x in items if not x["official"]]

    return {
        "items": items,
        "official": official_items,
        "reference": reference_items,
        "summary": {
            "all": _series_summary(items, "kg"),
            "official": _series_summary(official_items, "kg"),
            "reference": _series_summary(reference_items, "kg"),
        },
        "meta": {"table": "weights", "columns": cols},
    }


METRIC_ALIASES = {
    "body_fat_pct": ["body_fat_pct", "fat_pct", "grasa_pct", "body_fat", "grasa"],
    "fat_mass_kg": ["fat_mass_kg", "fat_kg", "masa_grasa_kg"],
    "water_pct": ["water_pct", "agua_pct", "water", "agua"],
    "muscle_mass_kg": ["muscle_mass_kg", "muscle_kg", "muscle_mass", "masa_muscular_kg"],
    "skeletal_muscle_kg": ["skeletal_muscle_kg", "skeletal_muscle", "musculo_esqueletico_kg"],
    "visceral_fat": ["visceral_fat", "visceral_fat_rating", "grasa_visceral", "visceral"],
    "bmr_kcal": ["bmr_kcal", "bmr", "basal_metabolism", "metabolismo_basal"],
    "protein_pct": ["protein_pct", "protein", "proteina_pct"],
    "subcutaneous_fat_pct": ["subcutaneous_fat_pct", "subcutaneous_fat", "grasa_subcutanea_pct"],
    "bone_mass_kg": ["bone_mass_kg", "bone_mass", "masa_osea_kg"],
    "biocharge": ["biocharge", "biocharge_current", "biocharge_wakeup", "hybrid_charge", "hybridcharge"],
    "bmi": ["bmi", "imc"],
}


def _canonical_metric(metric: str) -> str:
    low = metric.strip().lower()
    for canon, aliases in METRIC_ALIASES.items():
        if low in aliases:
            return canon
    return low


def _read_body_metrics(conn: sqlite3.Connection, start: str, end: str) -> Dict[str, Any]:
    table = "body_composition"
    cols = _columns(conn, table)
    if not cols:
        return {"metrics": {}, "snapshots": [], "meta": {"table": None}}

    date_col = _pick(cols, ["date", "day", "created_date", "measured_date", "record_date"])
    time_col = _pick(cols, ["time", "hour", "created_time", "measured_time"])
    metric_col = _pick(cols, ["metric", "name", "key"])
    value_col = _pick(cols, ["value", "metric_value", "amount"])
    unit_col = _pick(cols, ["unit"])
    source_col = _pick(cols, ["source"])
    notes_col = _pick(cols, ["notes", "note"])
    confidence_col = _pick(cols, ["confidence"])

    if not date_col or not metric_col or not value_col:
        return {
            "metrics": {},
            "snapshots": [],
            "meta": {"table": table, "error": "missing date/metric/value columns", "columns": cols},
        }

    select_cols = [date_col, metric_col, value_col]
    for c in [time_col, unit_col, source_col, notes_col, confidence_col]:
        if c and c not in select_cols:
            select_cols.append(c)

    sql = f'''
        SELECT {", ".join(f'"{c}"' for c in select_cols)}
        FROM "{table}"
        WHERE "{date_col}" >= ? AND "{date_col}" <= ?
        ORDER BY "{date_col}" ASC {',' + '"' + time_col + '" ASC' if time_col else ''}
    '''
    rows = conn.execute(sql, (start, end)).fetchall()

    metrics: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    snapshots: Dict[Tuple[str, str], Dict[str, Any]] = {}

    for row in rows:
        d = _date_str(row[date_col])
        if not d:
            continue
        t = _time_str(row[time_col]) if time_col else ""
        raw_metric = str(row[metric_col] or "").strip()
        canon = _canonical_metric(raw_metric)
        value = _safe_float(row[value_col])
        if not canon or value is None:
            continue

        item = {
            "date": d,
            "time": t,
            "metric": canon,
            "raw_metric": raw_metric,
            "value": round(value, 2),
            "unit": str(row[unit_col] or "") if unit_col else "",
            "source": str(row[source_col] or "") if source_col else "",
            "confidence": str(row[confidence_col] or "") if confidence_col else "",
            "notes": str(row[notes_col] or "") if notes_col else "",
        }
        metrics[canon].append(item)

        key = (d, t)
        snap = snapshots.setdefault(key, {"date": d, "time": t, "metrics": {}})
        snap["metrics"][canon] = item

    metrics_out = {
        name: {
            "items": items,
            "summary": _series_summary(items, "value"),
        }
        for name, items in sorted(metrics.items())
    }

    snapshot_items = sorted(snapshots.values(), key=lambda x: (x["date"], x["time"]))

    return {
        "metrics": metrics_out,
        "snapshots": snapshot_items,
        "meta": {"table": table, "columns": cols},
    }


def _latest_metric(body: Dict[str, Any], name: str) -> Optional[float]:
    metric = body.get("metrics", {}).get(name)
    if not metric:
        return None
    latest = metric.get("summary", {}).get("latest")
    if not latest:
        return None
    return _safe_float(latest.get("value"))


def _insights(weights: Dict[str, Any], body: Dict[str, Any]) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []

    official = weights.get("summary", {}).get("official", {})
    if official.get("count"):
        latest = official.get("latest") or {}
        delta = official.get("delta_from_first")
        if delta is not None:
            if delta < -0.3:
                out.append({
                    "type": "weight",
                    "level": "good",
                    "title": "Peso oficial bajando",
                    "message": f"Último oficial {latest.get('kg')} kg. Cambio del rango: {delta} kg.",
                })
            elif delta > 0.3:
                out.append({
                    "type": "weight",
                    "level": "watch",
                    "title": "Peso oficial subiendo",
                    "message": f"Último oficial {latest.get('kg')} kg. Revisa sal, hidratos, sueño y entrenos antes de juzgar grasa.",
                })
            else:
                out.append({
                    "type": "weight",
                    "level": "neutral",
                    "title": "Peso oficial estable",
                    "message": f"Último oficial {latest.get('kg')} kg. La tendencia del rango está bastante plana.",
                })

    fat = body.get("metrics", {}).get("body_fat_pct", {}).get("summary", {})
    if fat.get("count"):
        latest = fat.get("latest") or {}
        delta = fat.get("delta_from_first")
        if delta is not None:
            out.append({
                "type": "composition",
                "level": "neutral",
                "title": "Grasa corporal como tendencia",
                "message": f"Última lectura {latest.get('value')}%. Cambio del rango: {delta} puntos. Úsalo semanalmente, no día a día.",
            })

    bio = body.get("metrics", {}).get("biocharge", {}).get("summary", {})
    if bio.get("count"):
        latest = bio.get("latest") or {}
        value = _safe_float(latest.get("value"))
        if value is not None:
            level = "good" if value >= 70 else "watch" if value < 60 else "neutral"
            msg = "Buena disponibilidad para entrenar/seguir plan." if value >= 70 else "Recuperación justa: evita recortar agresivo." if value < 60 else "Recuperación aceptable: mantén rutina limpia."
            out.append({
                "type": "recovery",
                "level": level,
                "title": f"BioCharge / Hybrid Charge {int(round(value))}",
                "message": msg,
            })

    if not out:
        out.append({
            "type": "system",
            "level": "neutral",
            "title": "Aún faltan datos",
            "message": "Registra varios pesos oficiales y snapshots de báscula para generar tendencias útiles.",
        })

    return out


def get_body_trends_payload() -> Dict[str, Any]:
    start, end, days = _range_from_request()

    with _connect() as conn:
        weights = _read_weights(conn, start, end)
        body = _read_body_metrics(conn, start, end)

    return {
        "status": "ok",
        "range": {"from": start, "to": end, "days": days},
        "weights": weights,
        "body": body,
        "insights": _insights(weights, body),
        "meta": {
            "db_path": _db_path(),
            "warning": "Smart-scale body-composition values are trend context, not absolute daily truth.",
        },
    }


def register_body_trends_routes(app) -> None:
    if getattr(app, "_dpp_body_trends_registered", False):
        return

    @app.get("/api/body-trends")
    def api_body_trends():
        try:
            return jsonify(get_body_trends_payload())
        except Exception as exc:
            return jsonify({"status": "error", "error": str(exc)}), 500

    @app.get("/weight-2")
    def weight_2_page():
        return send_from_directory("static", "weight-2.html")

    app._dpp_body_trends_registered = True
