"""Progress analytics: trends, adaptive energy expenditure and adherence.

``GET /api/analytics/overview?days=60`` powers the "Progreso" page.

Method notes (kept deliberately simple and explainable):
- Trend weight: exponential moving average (alpha 0.1) of daily official
  weights, which hides water/glycogen noise.
- Rate: least-squares slope of the last 28 days of weights, in kg/week.
- Adaptive TDEE: average intake on fully logged days minus the energy implied
  by the weight slope (7700 kcal/kg) over the last 28 complete days.
  Needs >= 14 logged days and >= 6 weigh-ins; otherwise it is not used.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from statistics import mean
from typing import Any

from flask import jsonify, request

import dpp_db
import dpp_profile

KCAL_PER_KG = 7700.0
EMA_ALPHA = 0.1
COMPLETE_DAY_MIN_KCAL = 800
COMPLETE_DAY_MIN_MEALS = 2


def _daterange(start: date, end: date):
    for offset in range((end - start).days + 1):
        yield start + timedelta(days=offset)


def _load_days(start: date, end: date) -> dict[str, dict[str, Any]]:
    days = {
        d.isoformat(): {
            "date": d.isoformat(), "meals": 0, "kcal": 0.0, "protein": 0.0, "carbs": 0.0,
            "fat": 0.0, "sugar": 0.0, "salt": 0.0, "workout_kcal": 0.0, "workout_min": 0.0,
            "workouts": 0, "weight": None, "weight_official": False,
        }
        for d in _daterange(start, end)
    }
    s, e = start.isoformat(), end.isoformat()
    with dpp_db.connect() as db:
        for row in db.execute(
            """
            SELECT m.date, COUNT(DISTINCT m.id) AS meals,
                   COALESCE(SUM(i.kcal),0) AS kcal, COALESCE(SUM(i.protein),0) AS protein,
                   COALESCE(SUM(i.carbs),0) AS carbs, COALESCE(SUM(i.fat),0) AS fat,
                   COALESCE(SUM(i.sugar),0) AS sugar, COALESCE(SUM(i.salt),0) AS salt
            FROM meals m LEFT JOIN meal_items i ON i.meal_id = m.id
            WHERE m.date BETWEEN ? AND ? GROUP BY m.date
            """,
            (s, e),
        ):
            if row["date"] in days:
                days[row["date"]].update({k: (round(float(row[k]), 1) if k != "meals" else int(row[k]))
                                          for k in ("meals", "kcal", "protein", "carbs", "fat", "sugar", "salt")})
        for row in db.execute(
            "SELECT date, COUNT(*) n, COALESCE(SUM(kcal),0) kcal, COALESCE(SUM(minutes),0) minutes "
            "FROM workouts WHERE date BETWEEN ? AND ? GROUP BY date",
            (s, e),
        ):
            if row["date"] in days:
                days[row["date"]].update({"workouts": int(row["n"]), "workout_kcal": round(float(row["kcal"]), 1),
                                          "workout_min": round(float(row["minutes"]), 1)})
        has_official = db.execute("SELECT 1 FROM weights WHERE official=1 LIMIT 1").fetchone() is not None
        for row in db.execute(
            "SELECT date, kg, official FROM weights WHERE date BETWEEN ? AND ? ORDER BY date, official, time, id",
            (s, e),
        ):
            if row["date"] not in days or (has_official and not row["official"]):
                continue
            # Last official reading of the day wins (ordered by official, time).
            days[row["date"]].update({"weight": round(float(row["kg"]), 2), "weight_official": bool(row["official"])})
    for day in days.values():
        day["complete"] = day["meals"] >= COMPLETE_DAY_MIN_MEALS and day["kcal"] >= COMPLETE_DAY_MIN_KCAL
    return days


def _ema(values: list[float | None]) -> list[float | None]:
    out: list[float | None] = []
    trend: float | None = None
    for value in values:
        if value is not None:
            trend = value if trend is None else trend + EMA_ALPHA * (value - trend)
        out.append(round(trend, 2) if trend is not None else None)
    return out


def _slope_per_day(points: list[tuple[int, float]]) -> float | None:
    if len(points) < 4 or points[-1][0] - points[0][0] < 7:
        return None
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    mx, my = mean(xs), mean(ys)
    den = sum((x - mx) ** 2 for x in xs)
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den if den else None


def adaptive_tdee(end: date | None = None, window: int = 28) -> dict[str, Any] | None:
    """Energy expenditure measured from real intake vs. weight change."""
    end = end or date.today() - timedelta(days=1)  # today's log is still incomplete
    start = end - timedelta(days=window - 1)
    days = list(_load_days(start, end).values())
    logged = [d for d in days if d["complete"]]
    weighed = [(i, d["weight"]) for i, d in enumerate(days) if d["weight"] is not None]
    slope = _slope_per_day(weighed)
    if len(logged) < 14 or len(weighed) < 6 or slope is None:
        return {
            "tdee": None, "confidence": "insuficiente", "logged_days": len(logged), "weigh_ins": len(weighed),
            "window_days": window, "message": "Faltan datos: registra al menos 14 días completos y 6 pesajes en 4 semanas.",
        }
    avg_intake = mean(d["kcal"] for d in logged)
    tdee = max(1200.0, min(5500.0, avg_intake - slope * KCAL_PER_KG))
    confidence = "alta" if len(logged) >= 21 and len(weighed) >= 10 else "media"
    return {
        "tdee": round(tdee),
        "confidence": confidence,
        "avg_intake_kcal": round(avg_intake),
        "weight_slope_kg_week": round(slope * 7, 2),
        "avg_workout_kcal": round(mean(d["workout_kcal"] for d in days)),
        "logged_days": len(logged),
        "weigh_ins": len(weighed),
        "window_days": window,
        "from": start.isoformat(),
        "to": end.isoformat(),
    }


def _streak(days_by_date: dict[str, dict[str, Any]], today: date) -> int:
    cursor = today if days_by_date.get(today.isoformat(), {}).get("meals") else today - timedelta(days=1)
    count = 0
    while days_by_date.get(cursor.isoformat(), {}).get("meals"):
        count += 1
        cursor -= timedelta(days=1)
    return count


def _top_foods(start: date, end: date, order: str) -> list[dict[str, Any]]:
    with dpp_db.connect() as db:
        rows = db.execute(
            f"""
            SELECT i.food_name AS name, COUNT(*) AS times, ROUND(SUM(i.grams)) AS grams,
                   ROUND(SUM(i.kcal)) AS kcal, ROUND(SUM(i.protein), 1) AS protein
            FROM meal_items i JOIN meals m ON m.id = i.meal_id
            WHERE m.date BETWEEN ? AND ? GROUP BY i.food_name ORDER BY {order} DESC LIMIT 8
            """,
            (start.isoformat(), end.isoformat()),
        ).fetchall()
    return [dict(r) for r in rows]


def overview(days: int = 60) -> dict[str, Any]:
    today = date.today()
    days = max(7, min(365, int(days)))
    start = today - timedelta(days=days - 1)
    # Extra history so the moving average is already settled at the range start.
    warmup = start - timedelta(days=30)
    all_days = _load_days(warmup, today)
    ordered = [all_days[d.isoformat()] for d in _daterange(warmup, today)]
    trend = _ema([d["weight"] for d in ordered])
    for day, value in zip(ordered, trend):
        day["trend"] = value
    series = [d for d in ordered if d["date"] >= start.isoformat()]

    profile = dpp_profile.get_profile()
    tdee = adaptive_tdee()
    computed = dpp_profile.compute(profile, tdee)
    base = computed["kcal_base_target"]
    factor, cap = float(profile["sport_bonus_factor"]), float(profile["max_sport_bonus_kcal"])
    protein_goal = computed["protein"]["goal_min_g"]
    for day in series:
        day["kcal_target"] = round(base + min(day["workout_kcal"], cap) * factor)

    recent = [(i, d["weight"]) for i, d in enumerate(ordered[-28:]) if d["weight"] is not None]
    slope = _slope_per_day(recent)
    latest_trend = next((d["trend"] for d in reversed(ordered) if d["trend"] is not None), None)
    goal = float(profile["goal_weight_kg"])
    eta = None
    if slope is not None and latest_trend is not None and slope < -0.005 and latest_trend > goal:
        days_to_goal = (latest_trend - goal) / -slope
        if days_to_goal <= 730:
            eta = (today + timedelta(days=round(days_to_goal))).isoformat()

    complete = [d for d in series if d["complete"]]
    past = [d for d in series if d["date"] < today.isoformat()]
    protein_hits = sum(1 for d in complete if d["protein"] >= protein_goal)
    kcal_hits = sum(1 for d in complete if abs(d["kcal"] - d["kcal_target"]) <= d["kcal_target"] * 0.1)
    weekday = [d["kcal"] for d in complete if date.fromisoformat(d["date"]).weekday() < 5]
    weekend = [d["kcal"] for d in complete if date.fromisoformat(d["date"]).weekday() >= 5]

    weeks: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for d in series:
        monday = date.fromisoformat(d["date"]) - timedelta(days=date.fromisoformat(d["date"]).weekday())
        weeks[monday.isoformat()].append(d)
    weekly = []
    for monday, items in sorted(weeks.items()):
        logged = [d for d in items if d["complete"]]
        weights = [d["weight"] for d in items if d["weight"] is not None]
        weekly.append({
            "week": monday,
            "logged_days": len(logged),
            "avg_kcal": round(mean(d["kcal"] for d in logged)) if logged else None,
            "avg_protein": round(mean(d["protein"] for d in logged), 1) if logged else None,
            "workout_kcal": round(sum(d["workout_kcal"] for d in items)),
            "workout_min": round(sum(d["workout_min"] for d in items)),
            "avg_weight": round(mean(weights), 2) if weights else None,
            "trend_end": next((d["trend"] for d in reversed(items) if d["trend"] is not None), None),
        })

    macro = None
    if complete:
        p, c, f = (mean(d[k] for d in complete) for k in ("protein", "carbs", "fat"))
        total = p * 4 + c * 4 + f * 9 or 1
        macro = {"protein_pct": round(p * 400 / total), "carbs_pct": round(c * 400 / total), "fat_pct": round(f * 900 / total),
                 "protein_g": round(p, 1), "carbs_g": round(c, 1), "fat_g": round(f, 1)}

    summary = {
        "days": days,
        "logged_days": sum(1 for d in series if d["meals"]),
        "complete_days": len(complete),
        "logging_pct": round(sum(1 for d in past if d["complete"]) / len(past) * 100) if past else None,
        "streak_days": _streak(all_days, today),
        "avg_kcal": round(mean(d["kcal"] for d in complete)) if complete else None,
        "avg_protein": round(mean(d["protein"] for d in complete), 1) if complete else None,
        "protein_hit_days": protein_hits,
        "kcal_in_range_days": kcal_hits,
        "weekday_avg_kcal": round(mean(weekday)) if weekday else None,
        "weekend_avg_kcal": round(mean(weekend)) if weekend else None,
        "workout_kcal": round(sum(d["workout_kcal"] for d in series)),
        "workout_sessions": sum(d["workouts"] for d in series),
        "trend_weight": latest_trend,
        "rate_kg_week": round(slope * 7, 2) if slope is not None else None,
        "goal_weight": goal,
        "eta": eta,
    }
    return {
        "ok": True,
        "range": {"from": start.isoformat(), "to": today.isoformat(), "days": days},
        "targets": computed,
        "adaptive_tdee": tdee,
        "summary": summary,
        "macro_split": macro,
        "series": series,
        "weekly": weekly,
        "top_foods_kcal": _top_foods(start, today, "SUM(i.kcal)"),
        "top_foods_protein": _top_foods(start, today, "SUM(i.protein)"),
        "insights": _insights(summary, tdee, computed, profile),
    }


def _fmt(value: float, digits: int = 0) -> str:
    text = f"{value:,.{digits}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return text


def _insights(s: dict[str, Any], tdee: dict[str, Any] | None, computed: dict[str, Any], profile: dict[str, Any]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    if s["rate_kg_week"] is not None:
        rate = s["rate_kg_week"]
        tone = "good" if -1.0 <= rate <= -0.2 else "warn" if rate < -1.0 else "info"
        text = f"Ritmo real {_fmt(rate, 2)} kg/semana (últimas 4 semanas)."
        if s["eta"]:
            text += f" A este ritmo llegas a {_fmt(s['goal_weight'], 1)} kg hacia el {s['eta']}."
        if rate < -1.0:
            text += " Es rápido: protege proteína y descanso."
        out.append({"tone": tone, "title": "Ritmo de pérdida", "text": text})
    if tdee and tdee.get("tdee"):
        diff = round(tdee["tdee"] - computed["kcal_base_target"])
        out.append({
            "tone": "info",
            "title": f"Gasto real ≈ {_fmt(tdee['tdee'])} kcal/día",
            "text": f"Calculado con {tdee['logged_days']} días registrados y {tdee['weigh_ins']} pesajes (confianza {tdee['confidence']}). "
                    f"Tu objetivo base deja un margen de {_fmt(diff)} kcal.",
        })
    elif tdee:
        out.append({"tone": "info", "title": "Gasto real: aún calibrando", "text": tdee.get("message", "")})
    if s["complete_days"]:
        pct = round(s["protein_hit_days"] / s["complete_days"] * 100)
        out.append({
            "tone": "good" if pct >= 70 else "warn",
            "title": f"Proteína en objetivo {s['protein_hit_days']}/{s['complete_days']} días",
            "text": f"Media {_fmt(s['avg_protein'] or 0, 1)} g/día frente a {computed['protein']['goal_min_g']}–{computed['protein']['max_g']} g.",
        })
    if s["weekday_avg_kcal"] and s["weekend_avg_kcal"]:
        gap = s["weekend_avg_kcal"] - s["weekday_avg_kcal"]
        if abs(gap) >= 250:
            out.append({
                "tone": "warn" if gap > 0 else "info",
                "title": "Patrón de fin de semana",
                "text": f"El fin de semana comes {_fmt(abs(gap))} kcal {'más' if gap > 0 else 'menos'} de media que entre semana.",
            })
    if s["streak_days"] >= 3:
        out.append({"tone": "good", "title": f"Racha de {s['streak_days']} días", "text": "Días seguidos registrando comida. La constancia es lo que hace fiables los datos."})
    elif s["logging_pct"] is not None and s["logging_pct"] < 60:
        out.append({"tone": "warn", "title": "Registro incompleto", "text": f"Solo {s['logging_pct']}% de días completos: las tendencias pierden precisión."})
    return out


def register_analytics_routes(app) -> None:
    @app.get("/api/analytics/overview")
    def analytics_overview():
        try:
            days = max(7, min(730, int(request.args.get("days", 60))))
        except ValueError:
            days = 60
        return jsonify(overview(days))

    @app.get("/api/analytics/tdee")
    def analytics_tdee():
        return jsonify({"ok": True, "adaptive_tdee": adaptive_tdee()})
