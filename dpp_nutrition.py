"""Food Intelligence (v0.0.14.1): day analysis, confidence/score and meal-plan option builders.

Extracted from app.py without behaviour changes (routes stay in app.py). It must not import ``app``.
"""
from __future__ import annotations

import dpp_profile
from dpp_state import con

# Targets come from the editable profile: see dpp_profile.legacy_targets().


def _fi_qident(name):
    return '"' + str(name).replace('"', '""') + '"'

def _fi_float(v, default=0.0):
    try:
        if v is None or v == "":
            return default
        return float(v)
    except Exception:
        return default

def _fi_round(v, nd=1):
    try:
        return round(float(v), nd)
    except Exception:
        return 0

def _fi_dicts(cur):
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]

def _fi_cols(db, table):
    try:
        return [r[1] for r in db.execute(f"PRAGMA table_info({_fi_qident(table)})").fetchall()]
    except Exception:
        return []

def _fi_has_table(db, table):
    row = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None

def _fi_clean_text(v):
    return str(v or "").replace("prote?na", "proteína").replace("d?a", "día").replace("caf?", "café").replace("pl?tano", "plátano").replace("jam?n", "jamón").replace("at?n", "atún").replace("Estimaci?n", "Estimación").replace("peque?as", "pequeñas")

# Identifiers are interpolated into SQL, so only these hard-coded tables/orderings are allowed;
# every value goes through bound parameters.
_FI_TABLES = frozenset({"foods", "meals", "meal_items", "workouts"})
_FI_ORDERS = frozenset({"", "time ASC, id ASC", "id ASC", "name ASC"})


def _fi_get_rows(db, table, where="", params=(), order=""):
    if table not in _FI_TABLES or order not in _FI_ORDERS:
        raise ValueError("table/order not allowed")
    if not _fi_has_table(db, table):
        return []
    sql = f"SELECT * FROM {_fi_qident(table)}"
    if where:
        sql += " WHERE " + where
    if order:
        sql += " ORDER BY " + order
    return _fi_dicts(db.execute(sql, params))

def _fi_find_food(db, item):
    if not _fi_has_table(db, "foods"):
        return None

    food_cols = _fi_cols(db, "foods")
    item_cols = set(item.keys())

    if "food_id" in item_cols and item.get("food_id") and "id" in food_cols:
        rows = _fi_get_rows(db, "foods", f"{_fi_qident('id')}=?", (item.get("food_id"),))
        if rows:
            return rows[0]

    name = item.get("food_name") or item.get("name") or item.get("food") or ""
    if name and "name" in food_cols:
        rows = _fi_get_rows(db, "foods", f"{_fi_qident('name')}=?", (name,))
        if rows:
            return rows[0]

        rows = _fi_get_rows(db, "foods", f"LOWER({_fi_qident('name')})=LOWER(?)", (name,))
        if rows:
            return rows[0]

    return None

def _fi_item_name(item, food):
    return _fi_clean_text(
        item.get("food_name")
        or item.get("name")
        or item.get("food")
        or (food or {}).get("name")
        or "Alimento"
    )

def _fi_item_grams(item, food):
    for key in ["grams", "g", "quantity_g", "amount_g"]:
        if key in item and item.get(key) not in (None, ""):
            return _fi_float(item.get(key), 0.0)
    if food and food.get("typical_g") not in (None, ""):
        return _fi_float(food.get("typical_g"), 0.0)
    return 0.0

def _fi_macro_from_food(food, grams, macro):
    if not food or macro not in food:
        return 0.0
    return _fi_float(food.get(macro), 0.0) * grams / 100.0

def _fi_macro_from_item(item, macro):
    if macro in item and item.get(macro) not in (None, ""):
        return _fi_float(item.get(macro), 0.0)
    return 0.0

def _fi_item_macros(item, food, grams):
    if food:
        return {
            "kcal": _fi_macro_from_food(food, grams, "kcal"),
            "protein": _fi_macro_from_food(food, grams, "protein"),
            "carbs": _fi_macro_from_food(food, grams, "carbs"),
            "fat": _fi_macro_from_food(food, grams, "fat"),
            "sugar": _fi_macro_from_food(food, grams, "sugar"),
            "salt": _fi_macro_from_food(food, grams, "salt"),
        }

    return {
        "kcal": _fi_macro_from_item(item, "kcal"),
        "protein": _fi_macro_from_item(item, "protein"),
        "carbs": _fi_macro_from_item(item, "carbs"),
        "fat": _fi_macro_from_item(item, "fat"),
        "sugar": _fi_macro_from_item(item, "sugar"),
        "salt": _fi_macro_from_item(item, "salt"),
    }

def _fi_confidence(item, food, grams):
    text = " ".join([
        _fi_clean_text(_fi_item_name(item, food)).lower(),
        _fi_clean_text((food or {}).get("brand", "")).lower(),
        _fi_clean_text((food or {}).get("source_note", "")).lower(),
        _fi_clean_text((food or {}).get("notes", "")).lower(),
    ])

    if "barcode" in text or "codigo" in text or "etiqueta" in text or "ocr" in text:
        source = 0.90
        source_label = "local_label_or_ocr"
    elif any(x in text for x in ["estim", "casero", "mezclad", "gofre", "helado", "churrasco", "asador"]):
        source = 0.55
        source_label = "estimated_or_composite"
    elif food:
        source = 0.82
        source_label = "local_food"
    else:
        source = 0.45
        source_label = "manual_unknown"

    quantity = 1.00 if grams > 0 else 0.50

    completeness_fields = ["kcal", "protein", "carbs", "fat", "sugar", "salt"]
    if food:
        present = sum(1 for x in completeness_fields if food.get(x) not in (None, ""))
    else:
        present = sum(1 for x in completeness_fields if item.get(x) not in (None, ""))
    completeness = 1.00 if present >= 6 else 0.85 if present >= 4 else 0.70

    score = 0.55 * source + 0.30 * quantity + 0.15 * completeness

    if score >= 0.90:
        label = "exacta"
    elif score >= 0.80:
        label = "alta"
    elif score >= 0.60:
        label = "media"
    else:
        label = "baja"

    return {
        "score": round(score, 3),
        "label": label,
        "source_label": source_label,
        "quantity_score": quantity,
        "completeness_score": completeness,
    }

def _fi_day_meals(db, d):
    meals = _fi_get_rows(db, "meals", f"{_fi_qident('date')}=?", (d,), "time ASC, id ASC")
    if not meals:
        return []

    item_cols = _fi_cols(db, "meal_items")
    has_items = _fi_has_table(db, "meal_items") and "meal_id" in item_cols

    out = []
    for m in meals:
        meal_id = m.get("id")
        items = _fi_get_rows(db, "meal_items", f"{_fi_qident('meal_id')}=?", (meal_id,), "id ASC") if has_items and meal_id is not None else []

        item_out = []
        totals = {"kcal": 0, "protein": 0, "carbs": 0, "fat": 0, "sugar": 0, "salt": 0}
        oil_g = 0.0
        flags = []

        for it in items:
            food = _fi_find_food(db, it)
            grams = _fi_item_grams(it, food)
            name = _fi_item_name(it, food)
            macros = _fi_item_macros(it, food, grams)
            conf = _fi_confidence(it, food, grams)

            for k in totals:
                totals[k] += macros.get(k, 0.0)

            lower = name.lower()
            if "aceite" in lower:
                oil_g += grams

            if any(x in lower for x in ["pepsi normal", "gofre", "helado", "galleta", "chocolate", "tirma", "piruleta"]):
                flags.append("extra_or_sweet")

            if conf["label"] in ("media", "baja"):
                flags.append("estimated_or_low_confidence")

            item_out.append({
                "name": name,
                "grams": _fi_round(grams, 1),
                "macros": {k: _fi_round(v, 1) for k, v in macros.items()},
                "confidence": conf,
            })

        out.append({
            "id": meal_id,
            "date": m.get("date"),
            "time": m.get("time"),
            "name": _fi_clean_text(m.get("name", "Comida")),
            "notes": _fi_clean_text(m.get("notes", "")),
            "items": item_out,
            "totals": {k: _fi_round(v, 1) for k, v in totals.items()},
            "oil_g": _fi_round(oil_g, 1),
            "flags": sorted(set(flags)),
        })

    return out

def _fi_day_workouts(db, d):
    if not _fi_has_table(db, "workouts"):
        return []
    cols = _fi_cols(db, "workouts")
    if "date" not in cols:
        return []
    return _fi_get_rows(db, "workouts", f"{_fi_qident('date')}=?", (d,), "time ASC, id ASC")

def _fi_sum_day(meals):
    totals = {"kcal": 0, "protein": 0, "carbs": 0, "fat": 0, "sugar": 0, "salt": 0}
    oil_g = 0.0
    items = []

    for m in meals:
        for k in totals:
            totals[k] += _fi_float(m["totals"].get(k), 0.0)
        oil_g += _fi_float(m.get("oil_g"), 0.0)
        items.extend(m.get("items", []))

    totals["oil_g"] = oil_g
    return {k: _fi_round(v, 1) for k, v in totals.items()}, items

def _fi_workout_totals(workouts):
    kcal = 0.0
    minutes = 0.0
    count = len(workouts)

    for w in workouts:
        kcal += _fi_float(w.get("kcal") or w.get("calories") or w.get("energy"), 0.0)
        minutes += _fi_float(w.get("minutes") or w.get("duration_min"), 0.0)

    return {
        "count": count,
        "kcal": _fi_round(kcal, 1),
        "minutes": _fi_round(minutes, 1),
    }

def _fi_confidence_day(items):
    if not items:
        return {"score": 0.0, "label": "sin_datos", "reasons": ["Sin alimentos registrados"]}

    weighted = 0.0
    kcal_total = 0.0
    low = 0
    estimated = 0

    for it in items:
        kcal = max(1.0, _fi_float(it.get("macros", {}).get("kcal"), 0.0))
        conf = it.get("confidence", {})
        weighted += kcal * _fi_float(conf.get("score"), 0.0)
        kcal_total += kcal
        if conf.get("label") in ("media", "baja"):
            low += 1
        if conf.get("source_label") == "estimated_or_composite":
            estimated += 1

    score = weighted / kcal_total if kcal_total else 0.0

    # Si hay alimentos estimados o compuestos, no vendemos falsa precisión.
    # El día puede estar bien formulado, pero la confianza de datos baja a media.
    if estimated:
        score = min(score, 0.79)

    if score >= 0.90:
        label = "exacta"
    elif score >= 0.80:
        label = "alta"
    elif score >= 0.60:
        label = "media"
    else:
        label = "baja"

    reasons = []
    if estimated:
        reasons.append(f"{estimated} alimentos estimados o compuestos")
    if low:
        reasons.append(f"{low} alimentos con confianza media/baja")
    if not reasons:
        reasons.append("Mayoría de alimentos trazables por gramos y macros")

    return {"score": round(score, 3), "label": label, "reasons": reasons}

def _fi_score_day(totals, meals, workouts, planned_workout=None):
    targets = dpp_profile.legacy_targets()
    kcal = _fi_float(totals.get("kcal"), 0.0)
    protein = _fi_float(totals.get("protein"), 0.0)
    carbs = _fi_float(totals.get("carbs"), 0.0)
    oil = _fi_float(totals.get("oil_g"), 0.0)
    salt = _fi_float(totals.get("salt"), 0.0)

    workout_totals = _fi_workout_totals(workouts)
    training_today = workout_totals["count"] > 0 or bool(planned_workout)

    if len(meals) < 2 or kcal < 600:
        return {
            "score": None,
            "semaphore": "insufficient",
            "label": "Base insuficiente",
            "main_action": "Registra al menos 2 comidas o 600 kcal para analizar el día.",
            "rules": {},
            "recommendations": ["Registra comida real antes de valorar si vas bien o mal."],
            "kcal_target": targets["kcal_base_target"],
            "kcal_margin": _fi_round(targets["kcal_base_target"] - kcal, 0),
        }

    sport_bonus = min(workout_totals["kcal"], targets["max_sport_bonus_kcal"]) * targets["sport_bonus_factor"]
    if planned_workout and workout_totals["kcal"] == 0:
        sport_bonus = max(sport_bonus, 150.0)

    kcal_target = round(targets["kcal_base_target"] + sport_bonus)
    kcal_margin = kcal_target - kcal

    rules = {}

    if protein <= 0:
        p_score = 0
    elif targets["protein_target_min_g"] <= protein <= 160:
        p_score = 30
    elif protein < targets["protein_target_min_g"]:
        p_score = max(0, 30 * protein / targets["protein_target_min_g"])
    else:
        p_score = max(15, 30 - (protein - 160) * 0.20)

    rules["protein"] = {
        "score": round(p_score, 1),
        "status": "ok" if p_score >= 27 else "watch" if p_score >= 20 else "bad",
        "message": "Proteína en objetivo" if p_score >= 27 else "Falta proteína útil",
    }

    if -450 <= kcal_margin <= 350:
        e_score = 20
    elif kcal_margin > 350:
        e_score = max(0, 20 - ((kcal_margin - 350) / 40))
    else:
        e_score = max(0, 20 - ((abs(kcal_margin) - 450) / 40))

    rules["energy"] = {
        "score": round(e_score, 1),
        "status": "ok" if e_score >= 16 else "watch" if e_score >= 10 else "bad",
        "message": "Energía ajustada" if e_score >= 16 else "Energía a vigilar",
        "target_kcal": kcal_target,
        "margin_kcal": round(kcal_margin),
    }

    if training_today:
        if protein >= 120 and carbs >= 140:
            t_score = 15 if workout_totals["count"] > 0 else 14
            t_msg = "Bien alineado con entreno real" if workout_totals["count"] > 0 else "Bien alineado con entreno planificado"
        elif protein >= 100 and carbs >= 90:
            t_score = 10
            t_msg = "Aceptable para entreno"
        else:
            t_score = 5
            t_msg = "Entreno con combustible o recuperación justos"
    else:
        t_score = 8
        t_msg = "Sin entreno real registrado"

    rules["training_alignment"] = {
        "score": t_score,
        "status": "ok" if t_score >= 10 else "watch",
        "message": t_msg,
    }

    if oil <= 5:
        o_score = 10
    elif oil <= 10:
        o_score = 7
    elif oil <= 15:
        o_score = 3
    else:
        o_score = 0

    rules["oil"] = {
        "score": o_score,
        "status": "ok" if o_score >= 7 else "watch" if o_score >= 3 else "bad",
        "message": "Aceite controlado" if o_score >= 7 else "Aceite alto",
    }

    text_blob = " ".join([
        m.get("name", "") + " " + m.get("notes", "") + " " + " ".join([it.get("name", "") for it in m.get("items", [])])
        for m in meals
    ]).lower()

    extra_hits = [x for x in ["pepsi normal", "gofre", "helado", "galleta", "chocolate", "tirma", "piruleta"] if x in text_blob]

    if not extra_hits:
        x_score = 10
    elif len(extra_hits) == 1:
        x_score = 7
    else:
        x_score = 3

    rules["extras"] = {
        "score": x_score,
        "status": "ok" if x_score >= 7 else "watch" if x_score >= 4 else "bad",
        "message": "Sin extras relevantes" if not extra_hits else "Extras detectados: " + ", ".join(extra_hits),
        "hits": extra_hits,
    }

    if salt <= 4:
        s_score = 5
    elif salt <= 6:
        s_score = 3
    elif salt <= 8:
        s_score = 1
    else:
        s_score = 0

    rules["salt"] = {
        "score": s_score,
        "status": "ok" if s_score >= 5 else "watch" if s_score >= 1 else "bad",
        "message": "Sal correcta" if s_score >= 5 else "Sal alta: posible retención de agua",
    }

    fv_terms = ["platano", "plátano", "guisantes", "judia", "judía", "verdura", "patata", "manzana", "naranja", "champi"]
    fv_hits = [x for x in fv_terms if x in text_blob]

    if len(set(fv_hits)) >= 2:
        f_score = 10
    elif fv_hits:
        f_score = 5
    else:
        f_score = 0

    rules["fruit_veg_fiber"] = {
        "score": f_score,
        "status": "ok" if f_score >= 5 else "watch",
        "message": "Fruta/verdura suficiente" if f_score >= 10 else "Fruta/verdura mejorable",
    }

    score = round(sum(_fi_float(v.get("score"), 0.0) for v in rules.values()))

    if score >= 80:
        sem = "green"
        label = "Buen día"
    elif score >= 60:
        sem = "yellow"
        label = "Cuidado"
    else:
        sem = "red"
        label = "Corregir"

    recs = []
    if protein < 130:
        recs.append("Cierra con 20-30 g de proteína: merluza, huevo, jamón, atún, Alpro o yogur proteico.")
    if kcal_margin > 450 and training_today:
        recs.append("No recortes más: respeta la comida post-entreno.")
    if kcal_margin < -250:
        recs.append("Cierre limpio: sin Pepsi normal, dulce ni aceite extra.")
    if salt > 5:
        recs.append("Bebe agua y no interpretes el peso de mañana como grasa.")
    if extra_hits:
        recs.append("No añadas más extras hoy: " + ", ".join(extra_hits) + ".")
    if not recs:
        recs.append("Mantén el plan actual; no añadas extras.")

    return {
        "score": score,
        "semaphore": sem,
        "label": label,
        "main_action": recs[0],
        "rules": rules,
        "recommendations": recs,
        "kcal_target": kcal_target,
        "kcal_margin": round(kcal_margin),
    }

def _fi_build_day(d, planned_workout=None):
    with con() as db:
        meals = _fi_day_meals(db, d)
        workouts = _fi_day_workouts(db, d)

    totals, items = _fi_sum_day(meals)
    confidence = _fi_confidence_day(items)
    workout_totals = _fi_workout_totals(workouts)
    score = _fi_score_day(totals, meals, workouts, planned_workout)

    return {
        "ok": True,
        "date": d,
        "version": "v0.0.14.1-food-intel",
        "summary": totals,
        "meals_count": len(meals),
        "items_count": len(items),
        "workouts": workout_totals,
        "confidence": confidence,
        "analysis": score,
        "meals": meals,
    }


def _fimp_norm(v):
    return _fi_clean_text(str(v or "")).lower().strip()

def _fimp_foods(db):
    if not _fi_has_table(db, "foods"):
        return []
    return _fi_get_rows(db, "foods", "", (), "name ASC")

def _fimp_match_food(foods, wanted):
    w = _fimp_norm(wanted)
    if not w:
        return None

    # Exact / contains match.
    for f in foods:
        name = _fimp_norm(f.get("name"))
        brand = _fimp_norm(f.get("brand"))
        if w == name or w in name or name in w or w in brand:
            return f

    # Token match.
    wt = [x for x in w.replace("/", " ").replace("+", " ").split() if len(x) >= 3]
    best = None
    best_score = 0
    for f in foods:
        hay = _fimp_norm((f.get("name") or "") + " " + (f.get("brand") or ""))
        score = sum(1 for x in wt if x in hay)
        if score > best_score:
            best_score = score
            best = f

    return best if best_score else None

def _fimp_food_macro(food, grams):
    return {
        "kcal": _fi_round(_fi_float(food.get("kcal")) * grams / 100.0, 1),
        "protein": _fi_round(_fi_float(food.get("protein")) * grams / 100.0, 1),
        "carbs": _fi_round(_fi_float(food.get("carbs")) * grams / 100.0, 1),
        "fat": _fi_round(_fi_float(food.get("fat")) * grams / 100.0, 1),
        "sugar": _fi_round(_fi_float(food.get("sugar")) * grams / 100.0, 1),
        "salt": _fi_round(_fi_float(food.get("salt")) * grams / 100.0, 1),
    }

def _fimp_sum_items(items):
    total = {"kcal": 0, "protein": 0, "carbs": 0, "fat": 0, "sugar": 0, "salt": 0}
    for it in items:
        m = it.get("macros", {})
        for k in total:
            total[k] += _fi_float(m.get(k), 0)
    return {k: _fi_round(v, 1) for k, v in total.items()}

def _fimp_item(food, grams, reason=""):
    return {
        "food_id": food.get("id"),
        "food_name": _fi_clean_text(food.get("name")),
        "grams": _fi_round(grams, 1),
        "macros": _fimp_food_macro(food, grams),
        "reason": reason,
    }

def _fimp_pick(foods, names):
    for n in names:
        f = _fimp_match_food(foods, n)
        if f:
            return f
    return None

def _fimp_plan_option(title, items, why, confidence_label="media"):
    totals = _fimp_sum_items(items)
    return {
        "title": title,
        "items": items,
        "totals": totals,
        "why": why,
        "confidence": {
            "label": confidence_label,
            "score": 0.80 if confidence_label == "alta" else 0.68 if confidence_label == "media" else 0.55,
        },
    }

def _fimp_make_options(date_value, meal, available_foods, training_today, current_day):
    with con() as db:
        foods = _fimp_foods(db)

    available = available_foods or []
    lower_available = [_fimp_norm(x) for x in available]

    def allowed(food):
        if not lower_available:
            return True
        name = _fimp_norm(food.get("name"))
        brand = _fimp_norm(food.get("brand"))
        return any(x in name or name in x or x in brand for x in lower_available)

    foods_allowed = [f for f in foods if allowed(f)]
    if not foods_allowed:
        foods_allowed = foods

    summary = current_day.get("summary", {})
    analysis = current_day.get("analysis", {})
    kcal_target = _fi_float(analysis.get("kcal_target"), 1900)
    kcal_now = _fi_float(summary.get("kcal"), 0)
    protein_now = _fi_float(summary.get("protein"), 0)

    targets = dpp_profile.legacy_targets()
    protein_goal = targets["protein_target_min_g"]
    protein_remaining = max(0, protein_goal - protein_now)
    kcal_remaining = max(0, kcal_target - kcal_now)

    protein_food = _fimp_pick(foods_allowed, [
        "merluza", "pollo", "atun", "atún", "huevo", "jamon", "jamón", "alpro", "yogur", "queso fresco"
    ])
    carb_food = _fimp_pick(foods_allowed, [
        "patata", "pasta", "arroz", "pan", "platano", "plátano", "guisantes"
    ])
    volume_food = _fimp_pick(foods_allowed, [
        "guisantes", "judia", "judía", "verdura", "gelatina", "champi"
    ])
    alpro = _fimp_pick(foods_allowed, ["alpro", "batido proteico"])
    gelatina = _fimp_pick(foods_allowed, ["gelatina"])

    options = []

    # Option 1: clean protein meal
    if protein_food:
        grams_p = 250
        lname = _fimp_norm(protein_food.get("name"))
        if "huevo" in lname:
            grams_p = 120
        elif "jamon" in lname or "jamón" in lname:
            grams_p = 100
        elif "alpro" in lname or "yogur" in lname:
            grams_p = 250

        items = [_fimp_item(protein_food, grams_p, "ancla de proteína")]
        if carb_food:
            lname_c = _fimp_norm(carb_food.get("name"))
            grams_c = 300 if training_today and ("patata" in lname_c or "guisantes" in lname_c) else 250
            if "pasta" in lname_c:
                grams_c = 300 if training_today else 220
            if "pan" in lname_c:
                grams_c = 45
            if "platano" in lname_c or "plátano" in lname_c:
                grams_c = 120
            items.append(_fimp_item(carb_food, grams_c, "hidrato ajustado al dia"))
        if volume_food and volume_food.get("id") not in [x.get("food_id") for x in items]:
            grams_v = 150
            if "gelatina" in _fimp_norm(volume_food.get("name")):
                grams_v = 100
            items.append(_fimp_item(volume_food, grams_v, "volumen/saciedad"))

        options.append(_fimp_plan_option(
            "Opcion limpia y segura",
            items,
            "Prioriza proteína, controla aceite y mantiene la energía dentro del objetivo.",
            "alta" if protein_food and carb_food else "media",
        ))

    # Option 2: post-workout / training meal
    if training_today:
        items = []
        pasta = _fimp_pick(foods_allowed, ["pasta mezclada", "pasta"])
        if pasta:
            items.append(_fimp_item(pasta, 300, "post-entreno con hidrato"))
        elif carb_food:
            items.append(_fimp_item(carb_food, 300, "hidrato post-entreno"))

        if alpro:
            items.append(_fimp_item(alpro, 250, "proteína fácil post-entreno"))
        elif protein_food and protein_food.get("id") not in [x.get("food_id") for x in items]:
            items.append(_fimp_item(protein_food, 150, "refuerzo de proteina"))

        if items:
            options.append(_fimp_plan_option(
                "Opcion post-entreno",
                items,
                "Pensada para recuperar tras entreno: hidrato medido + proteína.",
                "media",
            ))

    # Option 3: light close
    items = []
    if protein_food:
        grams_p = 200
        if "huevo" in _fimp_norm(protein_food.get("name")):
            grams_p = 120
        items.append(_fimp_item(protein_food, grams_p, "cerrar proteína"))
    if gelatina:
        items.append(_fimp_item(gelatina, 100, "postre bajo en kcal"))
    elif volume_food and volume_food.get("id") not in [x.get("food_id") for x in items]:
        items.append(_fimp_item(volume_food, 120, "volumen sin subir mucho kcal"))
    if items:
        options.append(_fimp_plan_option(
            "Opcion ligera",
            items,
            "Para cerrar el día sin pasarte si ya llevas suficiente energía.",
            "media",
        ))

    # Rank options by how close they get to remaining needs without overdoing.
    for opt in options:
        t = opt["totals"]
        protein_after = protein_now + _fi_float(t.get("protein"), 0)
        kcal_after = kcal_now + _fi_float(t.get("kcal"), 0)
        protein_gap = abs(targets["protein_target_g"] + 5 - protein_after)
        kcal_gap = abs(kcal_target - kcal_after)
        opt["fit_score"] = max(0, round(100 - protein_gap * 1.2 - kcal_gap / 35, 0))

    options = sorted(options, key=lambda x: x.get("fit_score", 0), reverse=True)

    return {
        "date": date_value,
        "meal": meal,
        "training_today": bool(training_today),
        "current": {
            "kcal": _fi_round(kcal_now, 1),
            "protein": _fi_round(protein_now, 1),
            "kcal_target": _fi_round(kcal_target, 0),
            "kcal_remaining": _fi_round(kcal_remaining, 0),
            "protein_remaining_to_130": _fi_round(protein_remaining, 1),
            "protein_goal_g": _fi_round(protein_goal, 0),
        },
        "available_foods_used": available,
        "options": options[:3],
        "rules": [
            "protein_first",
            "training_allows_more_carbs",
            "avoid_liquid_calories",
            "estimated_foods_lower_confidence",
        ],
    }
