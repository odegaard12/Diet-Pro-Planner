"""Read-only data review (``GET /api/data-audit``): finds likely typos and broken references.

Every check is independent and never changes data. A finding says what looks wrong, shows up to
``MAX_ITEMS`` examples and where to fix it, so the person decides (nothing is repaired automatically).
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from typing import Any

from flask import jsonify

import dpp_db

MAX_ITEMS = 5
LEVELS = ("error", "warn", "info")


def _has(db, table: str) -> bool:
    return dpp_db._table_exists(db, table)


def _finding(fid: str, level: str, title: str, detail: str, items: list[str], count: int, fix: str) -> dict[str, Any]:
    return {"id": fid, "level": level, "title": title, "detail": detail, "count": count, "items": items[:MAX_ITEMS], "fix": fix}


def _foods_macros(db) -> list[dict]:
    if not _has(db, "foods"):
        return []
    out = []
    over = [r["name"] for r in db.execute(
        "SELECT name FROM foods WHERE protein + carbs + fat > 100.5 ORDER BY name")]
    if over:
        out.append(_finding("foods_over_100g", "error", "Alimentos con más de 100 g de macros por 100 g",
                            "Proteína + hidratos + grasa no puede superar 100 g por cada 100 g: casi seguro hay un dato mal escrito.",
                            over, len(over), "foods"))
    odd = [f'{r["name"]} ({r["kcal"]:.0f} kcal declaradas, {4 * r["protein"] + 4 * r["carbs"] + 9 * r["fat"]:.0f} por macros)'
           for r in db.execute("SELECT name, kcal, protein, carbs, fat FROM foods WHERE kcal > 0 ORDER BY name")
           if abs(r["kcal"] - (4 * r["protein"] + 4 * r["carbs"] + 9 * r["fat"])) > max(40, 0.25 * r["kcal"])]
    if odd:
        out.append(_finding("foods_kcal_mismatch", "warn", "Calorías que no cuadran con los macros",
                            "Las kcal difieren mucho de lo que suman proteína, hidratos y grasa (fibra y alcohol pueden explicar parte).",
                            odd, len(odd), "foods"))
    return out


def _meals(db, today: str) -> list[dict]:
    if not (_has(db, "meals") and _has(db, "meal_items")):
        return []
    out = []
    gone = [f'{r["date"]} {r["meal"]}: {r["food_name"]}' for r in db.execute(
        "SELECT m.date, m.name AS meal, i.food_name FROM meal_items i JOIN meals m ON m.id = i.meal_id "
        "WHERE i.food_id IS NULL AND NOT EXISTS (SELECT 1 FROM foods f WHERE f.name = i.food_name) "
        "ORDER BY m.date DESC")]
    if gone:
        out.append(_finding("items_food_deleted", "info", "Comidas con alimentos que ya no están en el catálogo",
                            "Los datos de esas comidas se conservan, pero no se pueden repetir ni editar los gramos con el catálogo.",
                            gone, len(gone), "history"))
    big = [f'{r["date"]} {r["food_name"]}: {r["grams"]:.0f} g' for r in db.execute(
        "SELECT m.date, i.food_name, i.grams FROM meal_items i JOIN meals m ON m.id = i.meal_id "
        "WHERE i.grams > 2000 ORDER BY i.grams DESC")]
    if big:
        out.append(_finding("items_huge_grams", "warn", "Raciones de más de 2 kg",
                            "Puede ser un gramo de más al teclear (5000 en vez de 500).", big, len(big), "history"))
    heavy = [f'{r["date"]}: {r["kcal"]:.0f} kcal' for r in db.execute(
        "SELECT m.date, SUM(i.kcal) AS kcal FROM meals m JOIN meal_items i ON i.meal_id = m.id "
        "GROUP BY m.date HAVING SUM(i.kcal) > 6000 ORDER BY m.date DESC")]
    if heavy:
        out.append(_finding("days_over_6000", "warn", "Días con más de 6000 kcal",
                            "Revisa si alguna comida tiene un alimento o una cantidad equivocados.", heavy, len(heavy), "history"))
    dup = [f'{r["date"]} {r["time"]} {r["name"]} (x{r["n"]})' for r in db.execute(
        "SELECT date, time, name, COUNT(*) AS n FROM meals GROUP BY date, time, name HAVING n > 1 ORDER BY date DESC")]
    if dup:
        out.append(_finding("meals_duplicated", "info", "Comidas repetidas a la misma hora",
                            "Misma fecha, hora y tipo: puede ser un doble guardado.", dup, len(dup), "history"))
    limit = (date.fromisoformat(today) + timedelta(days=1)).isoformat()
    future = [f'{r["date"]} {r["name"]}' for r in db.execute(
        "SELECT date, name FROM meals WHERE date > ? ORDER BY date", (limit,))]
    if future:
        out.append(_finding("meals_future", "warn", "Comidas con fecha futura",
                            "Más de un día por delante de hoy: probablemente el año o el día están mal.", future, len(future), "history"))
    return out


def _weights(db, today: str) -> list[dict]:
    if not _has(db, "weights"):
        return []
    out = []
    rows = db.execute("SELECT date, kg FROM weights WHERE official = 1 ORDER BY date, time, id").fetchall()
    days = lambda a, b: (date.fromisoformat(b["date"]) - date.fromisoformat(a["date"])).days  # noqa: E731
    spikes: list[str] = []
    jumps: list[str] = []
    skip = -1
    for i in range(1, len(rows)):
        prev, cur = rows[i - 1], rows[i]
        if i == skip or days(prev, cur) > 3 or abs(cur["kg"] - prev["kg"]) <= 3:
            continue
        nxt = rows[i + 1] if i + 1 < len(rows) else None
        if nxt and days(cur, nxt) <= 3 and abs(nxt["kg"] - prev["kg"]) <= 3:
            spikes.append(f'{cur["date"]}: {cur["kg"]:.1f} kg (a su alrededor ronda {prev["kg"]:.1f})')
            skip = i + 1  # the way back is the same typo, not a second jump
        else:
            jumps.append(f'{prev["date"]} {prev["kg"]:.1f} kg → {cur["date"]} {cur["kg"]:.1f} kg')
    if spikes:
        out.append(_finding("weights_spike", "warn", "Pesos que parecen una errata",
                            "Un solo día muy distinto a los de antes y después (por ejemplo 77,5 entre pesos de 87): distorsiona la tendencia.",
                            spikes, len(spikes), "weights"))
    if jumps:
        out.append(_finding("weights_jump", "warn", "Saltos de peso de más de 3 kg en 3 días",
                            "Puede ser un cambio real o una errata al teclear; confirma que el dato es correcto.",
                            jumps, len(jumps), "weights"))
    bad = [f'{r["date"]}: {r["kg"]} kg' for r in db.execute(
        "SELECT date, kg FROM weights WHERE kg < 30 OR kg > 300 ORDER BY date DESC")]
    if bad:
        out.append(_finding("weights_range", "error", "Pesos fuera de lo razonable (menos de 30 o más de 300 kg)",
                            "Seguramente un decimal o una cifra mal escritos.", bad, len(bad), "weights"))
    limit = (date.fromisoformat(today) + timedelta(days=1)).isoformat()
    future = [f'{r["date"]}: {r["kg"]} kg' for r in db.execute(
        "SELECT date, kg FROM weights WHERE date > ? ORDER BY date", (limit,))]
    if future:
        out.append(_finding("weights_future", "warn", "Pesos con fecha futura", "Revisa la fecha.", future, len(future), "weights"))
    return out


def _workouts(db) -> list[dict]:
    if not _has(db, "workouts"):
        return []
    odd = [f'{r["date"]} {r["name"]}: {r["minutes"]:.0f} min, {r["kcal"]:.0f} kcal' for r in db.execute(
        "SELECT date, name, minutes, kcal FROM workouts "
        "WHERE minutes > 900 OR kcal > 10000 OR (minutes > 0 AND kcal / minutes > 30) ORDER BY date DESC")]
    if not odd:
        return []
    return [_finding("workouts_extreme", "warn", "Entrenos con duración o calorías extremas",
                     "Más de 15 horas, más de 10000 kcal o más de 30 kcal por minuto: puede ser un error de minutos o de unidades (una salida larga de verdad no cuenta).",
                     odd, len(odd), "sport")]


def _references(db) -> list[dict]:
    """Templates whose foods no longer exist (they would load incomplete)."""
    if not (_has(db, "templates") and _has(db, "foods")):
        return []
    names = {r["name"] for r in db.execute("SELECT name FROM foods")}
    broken = []
    for r in db.execute("SELECT name, payload FROM templates ORDER BY name"):
        try:
            items = json.loads(r["payload"] or "{}").get("items", [])
        except (TypeError, ValueError, AttributeError):
            broken.append(f'{r["name"]}: contenido ilegible')
            continue
        missing = sorted({str(i.get("food")) for i in items if isinstance(i, dict) and i.get("food") not in names})
        if missing:
            broken.append(f'{r["name"]}: falta {", ".join(missing[:3])}')
    if not broken:
        return []
    return [_finding("templates_missing_foods", "warn", "Plantillas con alimentos que ya no existen",
                     "Al cargarlas faltarán esos alimentos. Recréalos en Alimentos o edita la plantilla.",
                     broken, len(broken), "templates")]


def _backup(now: datetime) -> list[dict]:
    backups = dpp_db.list_backups()
    if not backups:
        return [_finding("backup_none", "warn", "Todavía no hay ninguna copia de seguridad",
                         "Crea una desde Ajustes › Copias y exportación.", [], 0, "goals")]
    age = now - datetime.fromisoformat(backups[0]["created_at"])
    if age > timedelta(days=3):
        return [_finding("backup_old", "warn", f"La última copia tiene {age.days} días",
                         "Las copias automáticas diarias parecen detenidas; crea una a mano.",
                         [backups[0]["name"]], 1, "goals")]
    return []


def run_audit(today: str | None = None, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now()
    today = today or now.date().isoformat()
    findings: list[dict] = []
    with dpp_db.connect() as db:
        findings += _foods_macros(db)
        findings += _meals(db, today)
        findings += _weights(db, today)
        findings += _workouts(db)
        findings += _references(db)
    findings += _backup(now)
    findings.sort(key=lambda f: LEVELS.index(f["level"]))
    summary = {level: sum(1 for f in findings if f["level"] == level) for level in LEVELS}
    return {"ok": True, "checked_at": now.isoformat(timespec="seconds"), "summary": summary, "findings": findings}


def register_data_audit_routes(app) -> None:
    @app.get("/api/data-audit")
    def data_audit():
        return jsonify(run_audit())
