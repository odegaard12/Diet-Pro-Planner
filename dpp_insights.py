"""Daily dashboard insights (v0.0.12): meal/workout totals, weight summary, traffic light and advice.

Extracted from app.py without behaviour changes. It must not import ``app``.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from datetime import timedelta as _dpp_v012_timedelta

import dpp_profile
from dpp_state import con, rows, totals

# Targets come from the editable profile: see dpp_profile.legacy_targets().


def _v012_safe_float(v, default=0.0):
    try:
        return float(v or default)
    except Exception:
        return float(default)

def _v012_day_meals(db, d: str):
    meals = []
    for m in db.execute("SELECT * FROM meals WHERE date=? ORDER BY time,id", (d,)).fetchall():
        md = dict(m)
        its = rows(db.execute("SELECT * FROM meal_items WHERE meal_id=? ORDER BY id", (m["id"],)))
        md["items"] = its
        md["totals"] = totals(its)
        meals.append(md)
    return meals

def _v012_day_workouts(db, d: str):
    return rows(db.execute("SELECT * FROM workouts WHERE date=? ORDER BY time,id", (d,)))

def _v012_meal_totals(meals):
    out = {
        "kcal": 0.0,
        "protein": 0.0,
        "carbs": 0.0,
        "fat": 0.0,
        "sugar": 0.0,
        "salt": 0.0,
        "oil_g": 0.0,
        "sweet_hits": [],
        "text_blob": "",
    }
    names = []
    sweet_re = re.compile(r"chocolate|galleta|piruleta|dulce|tirma|helado|boll|donut|postre|nutella", re.I)
    for m in meals:
        t = m.get("totals") or {}
        out["kcal"] += _v012_safe_float(t.get("kcal"))
        out["protein"] += _v012_safe_float(t.get("protein"))
        out["carbs"] += _v012_safe_float(t.get("carbs"))
        out["fat"] += _v012_safe_float(t.get("fat"))
        out["sugar"] += _v012_safe_float(t.get("sugar"))
        out["salt"] += _v012_safe_float(t.get("salt"))
        names.extend([str(m.get("name","")), str(m.get("notes",""))])
        for it in m.get("items") or []:
            fn = str(it.get("food_name",""))
            names.append(fn)
            if re.search(r"aceite", fn, re.I):
                out["oil_g"] += _v012_safe_float(it.get("grams"))
            if sweet_re.search(fn):
                out["sweet_hits"].append(fn)
    out["text_blob"] = " ".join(names).lower()
    for k in ["kcal","protein","carbs","fat","sugar","salt","oil_g"]:
        out[k] = round(out[k], 1 if k != "salt" else 2)
    out["sweet_hits"] = sorted(set(out["sweet_hits"]))
    return out

def _v012_workout_totals(workouts):
    minutes = sum(_v012_safe_float(w.get("minutes")) for w in workouts)
    kcal = sum(_v012_safe_float(w.get("kcal")) for w in workouts)
    distance = sum(_v012_safe_float(w.get("distance_km")) for w in workouts)
    sports = {}
    for w in workouts:
        name = str(w.get("name") or "Entreno")
        sports[name] = sports.get(name, 0) + 1
    return {
        "count": len(workouts),
        "minutes": round(minutes, 1),
        "kcal": round(kcal, 1),
        "distance_km": round(distance, 2),
        "sports": sports,
    }

def _v012_latest_weight(db):
    r = db.execute("SELECT * FROM weights ORDER BY date DESC,time DESC,id DESC LIMIT 1").fetchone()
    return dict(r) if r else None

def _v012_official_weights(db):
    return rows(db.execute("SELECT * FROM weights WHERE official=1 ORDER BY date,time,id"))

def _v012_weight_summary(db, targets=None):
    targets = targets or dpp_profile.legacy_targets()
    ws = _v012_official_weights(db)
    latest = _v012_latest_weight(db)
    current = _v012_safe_float(latest.get("kg")) if latest else None
    goal = targets["goal_weight_kg"]

    if ws:
        start = _v012_safe_float(ws[0].get("kg"), targets["fallback_start_weight_kg"])
    else:
        start = targets["fallback_start_weight_kg"]

    trend = {
        "label": "Sin tendencia",
        "weekly_kg": None,
        "delta_kg": None,
        "days": 0,
        "status": "info",
    }

    if len(ws) >= 2:
        first = ws[0]
        last = ws[-1]
        d0 = datetime.strptime(first["date"], "%Y-%m-%d").date()
        d1 = datetime.strptime(last["date"], "%Y-%m-%d").date()
        days = max(1, (d1 - d0).days)
        delta = _v012_safe_float(last["kg"]) - _v012_safe_float(first["kg"])
        weekly = delta / days * 7.0
        trend.update({
            "weekly_kg": round(weekly, 2),
            "delta_kg": round(delta, 2),
            "days": days,
        })
        if days < 7 or len(ws) < 5:
            trend["label"] = "Bajada inicial" if delta < 0 else "Subida inicial" if delta > 0 else "Estable"
            trend["status"] = "info"
        elif weekly < -1.0:
            trend["label"] = "Bajada rápida"
            trend["status"] = "warn"
        elif weekly < -0.35:
            trend["label"] = "Bajada correcta"
            trend["status"] = "good"
        elif weekly > 0.15:
            trend["label"] = "Subiendo"
            trend["status"] = "bad"
        else:
            trend["label"] = "Estable"
            trend["status"] = "info"

    kg_lost = round(start - current, 2) if current is not None else None
    kg_remaining = round(max(0.0, current - goal), 2) if current is not None else None

    eta = None
    if current is not None and kg_remaining is not None:
        weekly_loss = None
        if trend["weekly_kg"] is not None and trend["weekly_kg"] < -0.1:
            weekly_loss = abs(trend["weekly_kg"])
        if weekly_loss:
            days_to_goal = int(round(kg_remaining / weekly_loss * 7))
            if 0 <= days_to_goal <= 365:
                eta = (date.today() + _dpp_v012_timedelta(days=days_to_goal)).isoformat()

    return {
        "latest": latest,
        "official_count": len(ws),
        "start_kg": round(start, 2),
        "current_kg": round(current, 2) if current is not None else None,
        "goal_kg": goal,
        "kg_lost": kg_lost,
        "kg_remaining": kg_remaining,
        "eta": eta,
        "trend": trend,
    }

def _v012_days_since_last_workout(db, d: str):
    r = db.execute("SELECT date FROM workouts WHERE date<=? ORDER BY date DESC,time DESC,id DESC LIMIT 1", (d,)).fetchone()
    if not r:
        return None
    try:
        dd = datetime.strptime(d, "%Y-%m-%d").date()
        ww = datetime.strptime(r["date"], "%Y-%m-%d").date()
        return max(0, (dd - ww).days)
    except Exception:
        return None

def _v012_week_summary(db, d: str):
    end_d = datetime.strptime(d, "%Y-%m-%d").date()
    start_d = end_d - _dpp_v012_timedelta(days=6)
    workouts = rows(db.execute(
        "SELECT * FROM workouts WHERE date>=? AND date<=? ORDER BY date,time,id",
        (start_d.isoformat(), end_d.isoformat()),
    ))
    return _v012_workout_totals(workouts)

def _v012_card(label, value, pct, status, sub="", kind="generic"):
    try:
        pct = float(pct)
    except Exception:
        pct = 0
    return {
        "label": label,
        "value": value,
        "pct": max(0, min(100, round(pct, 1))),
        "status": status,
        "sub": sub,
        "kind": kind,
    }

def _v012_build_insights(d: str):
    targets = dpp_profile.legacy_targets()
    with con() as db:
        meals = _v012_day_meals(db, d)
        workouts = _v012_day_workouts(db, d)
        mt = _v012_meal_totals(meals)
        wt = _v012_workout_totals(workouts)
        weight = _v012_weight_summary(db, targets)
        week = _v012_week_summary(db, d)
        days_since_workout = _v012_days_since_last_workout(db, d)

    protein_target = targets["protein_target_g"]
    protein_min = targets["protein_min_g"]
    sport_bonus = min(wt["kcal"], targets["max_sport_bonus_kcal"]) * targets["sport_bonus_factor"]
    kcal_target = round(targets["kcal_base_target"] + sport_bonus)
    kcal_margin = round(kcal_target - mt["kcal"])
    estimated_deficit = max(0, kcal_margin)

    alerts = []
    advice = []

    if not meals:
        advice.append({
            "severity": "info",
            "title": "Empieza registrando una comida",
            "text": "El dashboard se vuelve útil cuando hay comida real del día.",
        })

    if mt["protein"] < 80:
        alerts.append("Proteína muy baja")
        advice.append({
            "severity": "warn",
            "title": "Prioridad: proteína",
            "text": "Siguiente comida con pollo, huevos, atún, yogur proteico, jamón cocido extra o queso fresco batido.",
        })
    elif mt["protein"] < protein_min:
        advice.append({
            "severity": "info",
            "title": "Proteína aceptable, pero falta cerrar",
            "text": "Intenta terminar el día cerca de 130 g sin subir aceite ni dulces.",
        })
    else:
        advice.append({
            "severity": "good",
            "title": "Proteína bien encaminada",
            "text": "Mantén el cierre limpio y no recortes de más.",
        })

    if mt["oil_g"] > targets["oil_bad_g"]:
        alerts.append("Aceite alto")
        advice.append({
            "severity": "bad",
            "title": "Aceite alto",
            "text": "Resto del día con sartén antiadherente y 0–5 g de aceite.",
        })
    elif mt["oil_g"] > targets["oil_max_g"]:
        advice.append({
            "severity": "warn",
            "title": "Aceite algo alto",
            "text": "No pases de 5 g en la siguiente comida.",
        })

    if mt["kcal"] > kcal_target + 550:
        alerts.append("Calorías muy altas")
        advice.append({
            "severity": "bad",
            "title": "Cierre de emergencia",
            "text": "Cena muy simple: proteína magra + verdura. Sin pan, dulce ni aceite extra.",
        })
    elif mt["kcal"] > kcal_target + 250:
        advice.append({
            "severity": "warn",
            "title": "Vas algo pasado",
            "text": "Cierra con proteína y verdura. Evita compensar con más cardio si tienes hambre real.",
        })
    elif mt["kcal"] < 900 and len(meals) <= 1:
        advice.append({
            "severity": "info",
            "title": "Todavía hay poco registrado",
            "text": "Planifica comida/cena para no llegar con ansiedad por la noche.",
        })

    if mt["sweet_hits"]:
        advice.append({
            "severity": "warn",
            "title": "Dulce detectado",
            "text": "No pasa nada: el cierre debe ser limpio, alto en proteína y sin picoteo.",
        })

    if wt["kcal"] >= 900:
        advice.append({
            "severity": "good",
            "title": "Mucho gasto deportivo",
            "text": "Puedes meter carbohidrato controlado, pero no conviertas el deporte en barra libre.",
        })
    elif wt["kcal"] >= 300:
        advice.append({
            "severity": "good",
            "title": "Buen gasto de actividad",
            "text": "Recupera con proteína y agua; evita picoteo automático.",
        })

    if days_since_workout is not None and days_since_workout >= 4:
        advice.append({
            "severity": "warn",
            "title": "Varios días sin entrenar",
            "text": "Mete una sesión corta: paseo largo, pádel, fuerza o bici suave.",
        })

    trend = weight["trend"]
    if trend["status"] == "warn":
        advice.append({
            "severity": "warn",
            "title": "Peso bajando rápido",
            "text": "No recortes proteína. Si hay fatiga, sube un poco carbohidrato en días de entreno.",
        })
    elif trend["status"] == "bad":
        advice.append({
            "severity": "warn",
            "title": "Peso subiendo",
            "text": "Revisa aceite, dulces, pan y raciones de pasta/arroz de los últimos días.",
        })

    score = 100
    if mt["protein"] < 80:
        score -= 28
    elif mt["protein"] < protein_min:
        score -= 14
    if mt["oil_g"] > targets["oil_bad_g"]:
        score -= 22
    elif mt["oil_g"] > targets["oil_max_g"]:
        score -= 10
    if mt["kcal"] > kcal_target + 550:
        score -= 30
    elif mt["kcal"] > kcal_target + 250:
        score -= 14
    if mt["sweet_hits"]:
        score -= 8
    if days_since_workout is not None and days_since_workout >= 4:
        score -= 8
    score = max(0, min(100, score))

    if score >= 78 and not alerts:
        semaphore = "green"
        semaphore_label = "Buen día"
    elif score >= 55:
        semaphore = "yellow"
        semaphore_label = "Cuidado"
    else:
        semaphore = "red"
        semaphore_label = "Exceso / corregir"

    main_action = "Cierra el día limpio y alto en proteína."
    if advice:
        priority = sorted(advice, key=lambda x: {"bad": 0, "warn": 1, "info": 2, "good": 3}.get(x["severity"], 4))[0]
        main_action = priority["text"]

    kcal_status = "bad" if mt["kcal"] > kcal_target + 550 else "warn" if mt["kcal"] > kcal_target + 250 else "good"
    protein_status = "good" if mt["protein"] >= protein_min else "warn" if mt["protein"] >= 80 else "bad"
    oil_status = "good" if mt["oil_g"] <= targets["oil_max_g"] else "warn" if mt["oil_g"] <= targets["oil_bad_g"] else "bad"
    activity_status = "good" if wt["kcal"] >= 300 else "info"

    cards = [
        _v012_card("Proteína", f"{mt['protein']:.0f} g", mt["protein"] / protein_target * 100, protein_status, f"objetivo {targets['protein_target_min_g']:.0f}-{targets['protein_high_g']:.0f} g", "protein"),
        _v012_card("Comida", f"{mt['kcal']:.0f} kcal", mt["kcal"] / max(1, kcal_target) * 100, kcal_status, f"objetivo flexible {kcal_target:.0f} kcal", "kcal"),
        _v012_card("Aceite", f"{mt['oil_g']:.0f} g", mt["oil_g"] / targets["oil_max_g"] * 100, oil_status, "5 g normal · 10 g máximo", "oil"),
        _v012_card("Actividad", f"{wt['kcal']:.0f} kcal", min(100, wt["kcal"] / 900 * 100), activity_status, f"{wt['minutes']:.0f} min · {wt['count']} sesiones", "activity"),
    ]

    if weight["current_kg"] is not None:
        remaining = weight["kg_remaining"]
        lost = weight["kg_lost"]
        cards.append(_v012_card(
            "Peso",
            f"{weight['current_kg']:.1f} kg",
            100 if remaining == 0 else max(0, min(100, (lost or 0) / max(0.1, (weight['start_kg'] - weight['goal_kg'])) * 100)),
            weight["trend"]["status"],
            f"{remaining:.1f} kg hasta {weight['goal_kg']:.0f} kg" if remaining is not None else f"objetivo {weight['goal_kg']:.0f} kg",
            "weight",
        ))

    return {
        "ok": True,
        "date": d,
        "targets": targets,
        "score": score,
        "semaphore": semaphore,
        "semaphore_label": semaphore_label,
        "main_action": main_action,
        "meals": {
            "count": len(meals),
            **mt,
        },
        "workouts": wt,
        "week": week,
        "weight": weight,
        "kcal_target": kcal_target,
        "kcal_margin": kcal_margin,
        "estimated_deficit": estimated_deficit,
        "alerts": alerts,
        "advice": advice[:6],
        "cards": cards,
        "days_since_workout": days_since_workout,
    }
