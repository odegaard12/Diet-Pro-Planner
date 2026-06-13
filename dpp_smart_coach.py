from __future__ import annotations

import os
import sqlite3
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from flask import jsonify, request


DEFAULT_DB = os.environ.get("DPP_DB", "data/dieta.db")
DEFAULT_PANTRY = os.environ.get("DPP_PANTRY", "data/pantry.json")


def _q(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _cols(cur: sqlite3.Cursor, table: str) -> List[str]:
    try:
        return [r[1] for r in cur.execute(f"PRAGMA table_info({_q(table)})").fetchall()]
    except Exception:
        return []


def _table_exists(cur: sqlite3.Cursor, table: str) -> bool:
    return cur.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone() is not None


def _pick(cols: List[str], names: List[str]) -> Optional[str]:
    low = {c.lower(): c for c in cols}
    for name in names:
        if name.lower() in low:
            return low[name.lower()]
    return None


def _num(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def _food_per100(cur: sqlite3.Cursor, food_id: Any, names: List[str]) -> float:
    if food_id in (None, "") or not _table_exists(cur, "foods"):
        return 0.0

    fc = _cols(cur, "foods")
    col = _pick(fc, names)
    if not col:
        return 0.0

    try:
        row = cur.execute(f"SELECT {_q(col)} FROM foods WHERE id=? LIMIT 1", (food_id,)).fetchone()
        if not row:
            return 0.0
        return _num(row[0])
    except Exception:
        return 0.0


def _sum_meal_items(cur: sqlite3.Cursor, meal_id: Any) -> Dict[str, float]:
    item_table = None
    for table in ["meal_items", "meal_foods", "meal_entries"]:
        if _table_exists(cur, table):
            item_table = table
            break

    if not item_table:
        return {"kcal": 0.0, "protein": 0.0, "carbs": 0.0, "fat": 0.0}

    ic = _cols(cur, item_table)
    meal_id_col = _pick(ic, ["meal_id", "mealId", "parent_id"])
    if not meal_id_col:
        return {"kcal": 0.0, "protein": 0.0, "carbs": 0.0, "fat": 0.0}

    kcal_col = _pick(ic, ["kcal", "calories"])
    protein_col = _pick(ic, ["protein", "protein_g"])
    carbs_col = _pick(ic, ["carbs", "carbs_g"])
    fat_col = _pick(ic, ["fat", "fat_g"])
    grams_col = _pick(ic, ["grams", "g", "quantity", "amount"])
    food_id_col = _pick(ic, ["food_id", "foodId"])

    rows = cur.execute(
        f"SELECT * FROM {_q(item_table)} WHERE {_q(meal_id_col)}=?",
        (meal_id,),
    ).fetchall()

    totals = {"kcal": 0.0, "protein": 0.0, "carbs": 0.0, "fat": 0.0}

    for r in rows:
        grams = _num(r[grams_col]) if grams_col else 0.0
        food_id = r[food_id_col] if food_id_col else None

        kcal = _num(r[kcal_col]) if kcal_col else 0.0
        protein = _num(r[protein_col]) if protein_col else 0.0
        carbs = _num(r[carbs_col]) if carbs_col else 0.0
        fat = _num(r[fat_col]) if fat_col else 0.0

        # Fallback: si el item no trae totales, calcular desde foods por 100 g.
        if grams > 0 and food_id not in (None, ""):
            if kcal == 0:
                kcal = grams * _food_per100(cur, food_id, ["kcal_100", "kcal_per_100g", "calories_100g", "kcal"]) / 100
            if protein == 0:
                protein = grams * _food_per100(cur, food_id, ["protein_100", "protein_per_100g", "protein"]) / 100
            if carbs == 0:
                carbs = grams * _food_per100(cur, food_id, ["carbs_100", "carbs_per_100g", "carbs"]) / 100
            if fat == 0:
                fat = grams * _food_per100(cur, food_id, ["fat_100", "fat_per_100g", "fat"]) / 100

        totals["kcal"] += kcal
        totals["protein"] += protein
        totals["carbs"] += carbs
        totals["fat"] += fat

    return {k: round(v, 1) for k, v in totals.items()}


def _food_per100(cur: sqlite3.Cursor, food_id: Any, names: List[str]) -> float:
    if food_id in (None, "") or not _table_exists(cur, "foods"):
        return 0.0

    fc = _cols(cur, "foods")
    col = _pick(fc, names)
    if not col:
        return 0.0

    try:
        row = cur.execute(f"SELECT {_q(col)} FROM foods WHERE id=? LIMIT 1", (food_id,)).fetchone()
        if not row:
            return 0.0
        return _num(row[0])
    except Exception:
        return 0.0


def _sum_meal_items(cur: sqlite3.Cursor, meal_id: Any) -> Dict[str, float]:
    item_table = None
    for table in ["meal_items", "meal_foods", "meal_entries"]:
        if _table_exists(cur, table):
            item_table = table
            break

    if not item_table:
        return {"kcal": 0.0, "protein": 0.0, "carbs": 0.0, "fat": 0.0}

    ic = _cols(cur, item_table)
    meal_id_col = _pick(ic, ["meal_id", "mealId", "parent_id"])
    if not meal_id_col:
        return {"kcal": 0.0, "protein": 0.0, "carbs": 0.0, "fat": 0.0}

    kcal_col = _pick(ic, ["kcal", "calories"])
    protein_col = _pick(ic, ["protein", "protein_g"])
    carbs_col = _pick(ic, ["carbs", "carbs_g"])
    fat_col = _pick(ic, ["fat", "fat_g"])
    grams_col = _pick(ic, ["grams", "g", "quantity", "amount"])
    food_id_col = _pick(ic, ["food_id", "foodId"])

    rows = cur.execute(
        f"SELECT * FROM {_q(item_table)} WHERE {_q(meal_id_col)}=?",
        (meal_id,),
    ).fetchall()

    totals = {"kcal": 0.0, "protein": 0.0, "carbs": 0.0, "fat": 0.0}

    for r in rows:
        grams = _num(r[grams_col]) if grams_col else 0.0
        food_id = r[food_id_col] if food_id_col else None

        kcal = _num(r[kcal_col]) if kcal_col else 0.0
        protein = _num(r[protein_col]) if protein_col else 0.0
        carbs = _num(r[carbs_col]) if carbs_col else 0.0
        fat = _num(r[fat_col]) if fat_col else 0.0

        # Fallback: si el item no trae totales, calcular desde foods por 100 g.
        if grams > 0 and food_id not in (None, ""):
            if kcal == 0:
                kcal = grams * _food_per100(cur, food_id, ["kcal_100", "kcal_per_100g", "calories_100g", "kcal"]) / 100
            if protein == 0:
                protein = grams * _food_per100(cur, food_id, ["protein_100", "protein_per_100g", "protein"]) / 100
            if carbs == 0:
                carbs = grams * _food_per100(cur, food_id, ["carbs_100", "carbs_per_100g", "carbs"]) / 100
            if fat == 0:
                fat = grams * _food_per100(cur, food_id, ["fat_100", "fat_per_100g", "fat"]) / 100

        totals["kcal"] += kcal
        totals["protein"] += protein
        totals["carbs"] += carbs
        totals["fat"] += fat

    return {k: round(v, 1) for k, v in totals.items()}


def _fetch_meals(cur: sqlite3.Cursor, day: str) -> List[Dict[str, Any]]:
    if not _table_exists(cur, "meals"):
        return []

    mc = _cols(cur, "meals")
    date_col = _pick(mc, ["date", "day"])
    if not date_col:
        return []

    time_col = _pick(mc, ["time", "hour"])
    name_col = _pick(mc, ["name", "title", "meal_name"])
    notes_col = _pick(mc, ["notes", "note", "description", "comment"])
    kcal_col = _pick(mc, ["kcal", "calories", "total_kcal"])
    protein_col = _pick(mc, ["protein", "protein_g", "total_protein"])
    carbs_col = _pick(mc, ["carbs", "carbs_g", "total_carbs"])
    fat_col = _pick(mc, ["fat", "fat_g", "total_fat"])

    rows = cur.execute(
        f"SELECT * FROM meals WHERE {_q(date_col)}=? ORDER BY COALESCE({_q(time_col)}, '') ASC, id ASC"
        if time_col else
        f"SELECT * FROM meals WHERE {_q(date_col)}=? ORDER BY id ASC",
        (day,),
    ).fetchall()

    meals = []
    for r in rows:
        meal_id = r["id"] if "id" in r.keys() else None

        row_totals = {
            "kcal": _num(r[kcal_col]) if kcal_col else 0.0,
            "protein": _num(r[protein_col]) if protein_col else 0.0,
            "carbs": _num(r[carbs_col]) if carbs_col else 0.0,
            "fat": _num(r[fat_col]) if fat_col else 0.0,
        }

        item_totals = _sum_meal_items(cur, meal_id) if meal_id is not None else {"kcal": 0.0, "protein": 0.0, "carbs": 0.0, "fat": 0.0}

        # La verdad de la app está en los items cuando existen.
        totals = item_totals if item_totals["kcal"] > 0 else row_totals

        meals.append({
            "id": meal_id,
            "time": str(r[time_col] or "") if time_col else "",
            "name": str(r[name_col] or "") if name_col else "Comida",
            "notes": str(r[notes_col] or "") if notes_col else "",
            "kcal": totals["kcal"],
            "protein": totals["protein"],
            "carbs": totals["carbs"],
            "fat": totals["fat"],
        })

    return meals


def _fetch_workouts(cur: sqlite3.Cursor, day: str) -> List[Dict[str, Any]]:
    if not _table_exists(cur, "workouts"):
        return []

    wc = _cols(cur, "workouts")
    date_col = _pick(wc, ["date", "day"])
    if not date_col:
        return []

    time_col = _pick(wc, ["time", "hour", "start_time"])
    name_col = _pick(wc, ["name", "title", "sport", "type", "activity_type"])
    kcal_col = _pick(wc, ["kcal", "calories", "energy", "calories_kcal"])
    duration_col = _pick(wc, ["duration_min", "minutes", "duration"])

    order = f"ORDER BY COALESCE({_q(time_col)}, '') ASC, id ASC" if time_col else "ORDER BY id ASC"
    rows = cur.execute(
        f"SELECT * FROM workouts WHERE {_q(date_col)}=? {order}",
        (day,),
    ).fetchall()

    workouts = []
    for r in rows:
        workouts.append({
            "time": str(r[time_col] or "") if time_col else "",
            "name": str(r[name_col] or "") if name_col else "Entreno",
            "kcal": _num(r[kcal_col]) if kcal_col else 0.0,
            "duration_min": _num(r[duration_col]) if duration_col else 0.0,
        })

    return workouts


def _fetch_weight(cur: sqlite3.Cursor, day: str) -> Optional[Dict[str, Any]]:
    if not _table_exists(cur, "weights"):
        return None

    wc = _cols(cur, "weights")
    date_col = _pick(wc, ["date", "day"])
    kg_col = _pick(wc, ["kg", "weight", "weight_kg", "value"])
    time_col = _pick(wc, ["time", "hour"])
    official_col = _pick(wc, ["official", "is_official"])
    context_col = _pick(wc, ["context", "notes", "note"])

    if not date_col or not kg_col:
        return None

    where = f"{_q(date_col)}<=?"
    order = f"ORDER BY {_q(date_col)} DESC"
    if official_col:
        order += f", {_q(official_col)} DESC"
    order += ", id DESC"

    r = cur.execute(
        f"SELECT * FROM weights WHERE {where} {order} LIMIT 1",
        (day,),
    ).fetchone()

    if not r:
        return None

    return {
        "date": r[date_col],
        "time": r[time_col] if time_col else "",
        "kg": _num(r[kg_col]),
        "official": bool(r[official_col]) if official_col else False,
        "context": r[context_col] if context_col else "",
    }


def _fetch_metric(cur: sqlite3.Cursor, day: str, metrics: List[str]) -> Optional[Dict[str, Any]]:
    if not _table_exists(cur, "body_composition"):
        return None

    wanted = [m.lower() for m in metrics]
    placeholders = ",".join(["?"] * len(wanted))

    rows = cur.execute(
        f"""
        SELECT date, time, metric, value, unit, source, confidence, notes
        FROM body_composition
        WHERE date<=?
          AND lower(metric) IN ({placeholders})
        ORDER BY date DESC, time DESC, id DESC
        LIMIT 1
        """,
        [day] + wanted,
    ).fetchall()

    if not rows:
        return None

    r = rows[0]
    return {
        "date": r["date"],
        "time": r["time"],
        "metric": r["metric"],
        "value": _num(r["value"]),
        "unit": r["unit"],
        "source": r["source"],
        "confidence": r["confidence"],
    }



def _norm_text(value: Any) -> str:
    s = str(value or "").lower()
    repl = {
        "á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u",
        "ü": "u", "ñ": "n"
    }
    for a, b in repl.items():
        s = s.replace(a, b)
    return s


def _candidate_pantry_paths(path: str = DEFAULT_PANTRY) -> List[str]:
    candidates: List[str] = []

    def add(value: Any) -> None:
        if not value:
            return
        s = str(value)
        if s not in candidates:
            candidates.append(s)

    add(path)
    add(os.environ.get("DPP_PANTRY"))
    add(os.path.join(os.getcwd(), "data", "pantry.json"))
    add(os.path.join(os.path.dirname(__file__), "data", "pantry.json"))
    add("/app/data/pantry.json")

    return candidates


def _load_pantry(path: str = DEFAULT_PANTRY) -> Dict[str, Any]:
    import json as _json
    candidates = _candidate_pantry_paths(path)

    chosen = None
    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            chosen = candidate
            break

    if not chosen:
        return {
            "available": False,
            "items": [],
            "candidates": candidates,
            "message": "No hay despensa configurada o no se encuentra pantry.json."
        }

    try:
        with open(chosen, "r", encoding="utf-8") as fh:
            data = _json.load(fh)

        if not isinstance(data, dict):
            raise ValueError("pantry root is not object")

        items = data.get("items") or []
        if not isinstance(items, list):
            items = []

        return {
            "available": True,
            "path": chosen,
            "version": data.get("version"),
            "updated_at": data.get("updated_at"),
            "items": items,
        }
    except Exception as exc:
        return {
            "available": False,
            "path": chosen,
            "items": [],
            "error": str(exc),
            "message": "No pude leer despensa."
        }


def _pantry_available_items(pantry: Dict[str, Any]) -> List[Dict[str, Any]]:
    items = pantry.get("items") or []
    out = []
    for item in items:
        if not isinstance(item, dict):
            continue
        if item.get("available") is True:
            out.append(item)
    return out


def _pantry_names(pantry: Dict[str, Any], include_avoid: bool = False) -> List[str]:
    names = []
    for item in _pantry_available_items(pantry):
        priority = _norm_text(item.get("priority"))
        if not include_avoid and priority == "avoid":
            continue
        name = item.get("name")
        if name:
            names.append(str(name))
    return names


def _pantry_find(pantry: Dict[str, Any], categories: List[str], names: List[str] | None = None) -> Optional[Dict[str, Any]]:
    cats = {_norm_text(x) for x in categories}
    wanted = [_norm_text(x) for x in (names or [])]

    candidates = []
    for item in _pantry_available_items(pantry):
        priority = _norm_text(item.get("priority"))
        if priority == "avoid":
            continue

        cat = _norm_text(item.get("category"))
        name = _norm_text(item.get("name"))

        if cat in cats or any(w in name for w in wanted):
            candidates.append(item)

    if not candidates:
        return None

    priority_order = {"prefer": 0, "normal": 1, "secondary": 2}
    candidates.sort(key=lambda x: priority_order.get(_norm_text(x.get("priority")), 5))
    return candidates[0]


def _pantry_avoid_items(pantry: Dict[str, Any]) -> List[str]:
    avoid = []
    for item in _pantry_available_items(pantry):
        priority = _norm_text(item.get("priority"))
        risk = item.get("risk")
        if priority == "avoid" or risk:
            name = item.get("name")
            if name:
                avoid.append(str(name))
    return avoid



def _build_pantry_next_meal(pantry: Dict[str, Any], training_type: str, breakfast_only: bool) -> Optional[Dict[str, Any]]:
    if not pantry.get("available"):
        return None

    protein = _pantry_find(
        pantry,
        ["protein", "protein_drink", "protein_fat"],
        ["pollo", "atun", "huevo", "jamon", "yogur", "alpro"],
    )
    vegetable = _pantry_find(
        pantry,
        ["vegetable", "verdura"],
        ["judias", "ensalada", "verdura", "brocoli"],
    )
    carb = _pantry_find(
        pantry,
        ["carb", "hidrato"],
        ["arroz", "pasta", "patata", "pan"],
    )

    used = [x.get("name") for x in [protein, vegetable, carb] if x and x.get("name")]
    avoid = _pantry_avoid_items(pantry)

    if not protein:
        return {
            "title": "Siguiente mejor comida",
            "primary": "No veo proteína principal en despensa: usa una proteína magra disponible + verdura + hidrato medido.",
            "why": "El desayuno fue bajo en proteína; sin proteína disponible concreta, recomiendo por categoría para no inventar.",
            "avoid": avoid,
            "pantry_used": used,
            "source": "pantry_rules"
        }

    protein_name = protein.get("name", "proteína")
    vegetable_name = vegetable.get("name", "verdura") if vegetable else "verdura"
    carb_name = carb.get("name", "arroz/pasta") if carb else "hidrato medido"

    protein_amount = "220-250 g" if _norm_text(protein_name).find("pollo") >= 0 else "1 ración alta"
    vegetable_amount = "250-300 g"
    carb_amount = "50-60 g en seco" if training_type in ["padel", "entreno_fuerte", "carrera", "bici"] or breakfast_only else "40-50 g en seco"

    primary = f"{protein_name} {protein_amount} + {vegetable_name} {vegetable_amount} + {carb_name} {carb_amount}."

    why = "Uso tu despensa: priorizo proteína disponible, verdura y un hidrato medido."
    if breakfast_only:
        why += " Solo llevas desayuno bajo en proteína; esta comida corrige el día."
    if training_type in ["padel", "entreno_fuerte", "carrera", "bici"]:
        why += " Como hay entreno o gasto previsto/registrado, no conviene recortar hidrato en exceso."

    return {
        "title": "Siguiente mejor comida",
        "primary": primary,
        "why": why,
        "avoid": avoid,
        "pantry_used": used,
        "source": "pantry_rules"
    }

def _previous_day(day: str) -> str:
    return (date.fromisoformat(day) - timedelta(days=1)).isoformat()


def _contains_any(text: str, words: List[str]) -> bool:
    low = text.lower()
    return any(w.lower() in low for w in words)


def _classify_training(workout_kcal: float, workouts: List[Dict[str, Any]]) -> str:
    names = " ".join(str(w.get("name", "")) for w in workouts).lower()

    if workout_kcal <= 0:
        return "sin_entreno"
    if "padel" in names or "pádel" in names:
        return "padel"
    if "run" in names or "carrera" in names:
        return "carrera"
    if "bike" in names or "bici" in names or "cycling" in names:
        return "bici"
    if workout_kcal >= 700:
        return "entreno_fuerte"
    if workout_kcal >= 250:
        return "entreno_moderado"
    return "suave"


def _build_recommendations(
    day: str,
    meals: List[Dict[str, Any]],
    workouts: List[Dict[str, Any]],
    weight: Optional[Dict[str, Any]],
    biocharge: Optional[Dict[str, Any]],
    prev_meals: List[Dict[str, Any]],
) -> Dict[str, Any]:
    total_kcal = round(sum(m["kcal"] for m in meals), 1)
    total_protein = round(sum(m["protein"] for m in meals), 1)
    total_carbs = round(sum(m["carbs"] for m in meals), 1)
    total_fat = round(sum(m["fat"] for m in meals), 1)
    workout_kcal = round(sum(w["kcal"] for w in workouts), 1)

    training_type = _classify_training(workout_kcal, workouts)
    base_ready = len(meals) >= 2 or total_kcal >= 600

    today_text = " ".join((m["name"] + " " + m["notes"]) for m in meals)
    prev_text = " ".join((m["name"] + " " + m["notes"]) for m in prev_meals)

    had_sugar_or_anxiety_yesterday = _contains_any(
        prev_text,
        ["nocilla", "pepsi", "ansiedad", "tortilla", "snack", "dulce"],
    )

    low_protein = total_protein < 70
    very_low_protein = total_protein < 35
    low_energy = total_kcal < 700
    breakfast_only = len(meals) == 1 and _contains_any(today_text, ["desayuno", "tostada", "plátano", "platano"])

    headline = "Base insuficiente: registra comida real antes de valorar el score."
    if base_ready:
        if low_protein:
            headline = "Día abierto: falta proteína útil."
        elif workout_kcal > 500:
            headline = "Día con entreno: prioriza recuperación, no recorte agresivo."
        else:
            headline = "Día controlado: mantén proteína y aceite medido."

    next_meal = {
        "title": "Siguiente mejor comida",
        "primary": "Pollo 200-250 g + judías 250-300 g + arroz seco 50-60 g.",
        "why": "Desayuno bajo en proteína; esta comida corrige proteína, mete verdura y deja hidrato limpio si hay pádel.",
        "avoid": ["Nocilla", "Pepsi normal", "más tortitas/pan por ansiedad", "queso si ya hay pollo"],
    }

    if training_type == "sin_entreno":
        next_meal["primary"] = "Pollo 200-250 g + judías 250-300 g + arroz seco 40-50 g."
        next_meal["why"] = "Sin entreno registrado aún: proteína alta, verdura y menos hidrato que en día con pádel."
    elif training_type in ["padel", "entreno_fuerte", "carrera", "bici"]:
        next_meal["primary"] = "Pollo 220-250 g + judías 250-300 g + arroz seco 60 g."
        next_meal["why"] = "Día con gasto alto: no ayunar; comer limpio con proteína e hidrato medido."

    if breakfast_only:
        next_meal["primary"] = "Ahora: pollo 220-250 g + judías 250-300 g + arroz seco 50-60 g."
        next_meal["why"] = "Solo llevas tostada, plátano y café: faltan proteínas; esta comida arregla el día."

    if very_low_protein:
        protein_message = "Proteína muy baja todavía: intenta meter 55-70 g en comida."
    elif low_protein:
        protein_message = "Proteína baja: siguiente comida debe ser proteica."
    else:
        protein_message = "Proteína razonable por ahora."

    weight_message = None
    if weight:
        weight_message = f"Peso usado: {weight['kg']:.2f} kg ({weight['date']}). No juzgar peso aislado."

    biocharge_message = None
    if biocharge:
        biocharge_message = f"BioCharge {biocharge['value']:.0f} ({biocharge['date']}): energía/recuperación disponible."

    flags = []
    if not base_ready:
        flags.append("score_no_calculado_por_base_insuficiente")
    if breakfast_only:
        flags.append("solo_desayuno_bajo_en_proteina")
    if had_sugar_or_anxiety_yesterday:
        flags.append("ayer_hubo_dulce_o_ansiedad")
    if workout_kcal == 0:
        flags.append("sin_entreno_registrado")
    if total_protein < 35:
        flags.append("proteina_muy_baja")

    quick_actions = [
        "No compenses con ayuno.",
        "Mide arroz/pasta en seco.",
        "Aceite 0-5 g en esta comida.",
        "Si hay pádel: merienda Alpro/yogur o plátano según hambre.",
    ]

    return {
        "date": day,
        "status": "base_insuficiente" if not base_ready else "analizable",
        "headline": headline,
        "totals": {
            "meals": len(meals),
            "kcal": total_kcal,
            "protein": total_protein,
            "carbs": total_carbs,
            "fat": total_fat,
            "workout_kcal": workout_kcal,
        },
        "training_type": training_type,
        "weight": weight,
        "biocharge": biocharge,
        "messages": {
            "protein": protein_message,
            "weight": weight_message,
            "biocharge": biocharge_message,
            "yesterday": "Ayer hubo señales de azúcar/ansiedad: hoy conviene comida limpia, no castigo." if had_sugar_or_anxiety_yesterday else None,
        },
        "flags": flags,
        "next_meal": next_meal,
        "pantry": {
            "available": _load_pantry().get("available"),
            "used": next_meal.get("pantry_used", []),
            "available_names": _pantry_names(_load_pantry())[:20],
            "avoid_names": _pantry_avoid_items(_load_pantry())[:20],
        },
        "quick_actions": quick_actions,
    }


def build_smart_coach_day(db_path: str, day: str) -> Dict[str, Any]:
    if not os.path.exists(db_path):
        return {
            "ok": False,
            "error": f"No existe DB: {db_path}",
            "date": day,
        }

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    meals = _fetch_meals(cur, day)
    workouts = _fetch_workouts(cur, day)
    weight = _fetch_weight(cur, day)
    biocharge = _fetch_metric(
        cur,
        day,
        ["biocharge_current", "biocharge_wakeup", "biocharge", "hybrid_charge", "hybird_charge"],
    )
    prev_meals = _fetch_meals(cur, _previous_day(day))

    coach = _build_recommendations(day, meals, workouts, weight, biocharge, prev_meals)

    conn.close()


    return {
        "ok": True,
        "version": "v0.0.17-smart-coach",
        "coach": coach,
    }


def register_smart_coach_routes(app):
    @app.get("/api/smart-coach/day")
    def smart_coach_day():
        day = request.args.get("date") or date.today().isoformat()
        db_path = os.environ.get("DPP_DB", DEFAULT_DB)
        return jsonify(build_smart_coach_day(db_path, day))

    @app.get("/api/pantry")
    def pantry_get():
        pantry = _load_pantry(os.environ.get("DPP_PANTRY", DEFAULT_PANTRY))
        return jsonify({
            "ok": True,
            "pantry": pantry,
        })

    @app.post("/api/pantry")
    def pantry_post():
        import json as _json
        payload = request.get_json(silent=True) or {}
        if not isinstance(payload, dict):
            return jsonify({"ok": False, "error": "payload must be object"}), 400

        items = payload.get("items")
        if not isinstance(items, list):
            return jsonify({"ok": False, "error": "items must be list"}), 400

        safe = {
            "version": 1,
            "updated_at": str(date.today()),
            "items": items,
        }

        path = os.environ.get("DPP_PANTRY", DEFAULT_PANTRY)
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            _json.dump(safe, fh, ensure_ascii=False, indent=2)

        return jsonify({
            "ok": True,
            "pantry": _load_pantry(path),
        })
