"""Personal profile and nutrition targets.

Replaces the personal values that used to be hard-coded across the app
(90.0 kg start weight, 80 kg goal, 175 cm, 1900 kcal, 135 g protein…).
Defaults reproduce the previous behaviour exactly, so nothing changes until
the profile is edited from the "Objetivos" page.

Calorie modes:
- ``manual``: fixed base target (previous behaviour).
- ``auto``: Mifflin-St Jeor BMR x activity factor minus the deficit implied
  by the weekly weight-loss rate.
- ``adaptive``: like ``auto`` but uses the energy expenditure measured from
  real intake vs. trend weight (see dpp_analytics) once there is enough data.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any

from flask import jsonify, request

import dpp_db
from dpp_validate import ApiError, number

KCAL_PER_KG = 7700.0
ACTIVITY_FACTORS = {"sedentary": 1.2, "light": 1.375, "moderate": 1.55, "active": 1.725}
SEXES = {"", "male", "female"}
KCAL_MODES = {"manual", "auto", "adaptive"}
PROTEIN_MODES = {"fixed", "per_kg"}

DEFAULT_PROFILE: dict[str, Any] = {
    "sex": "",
    "birth_year": None,
    "height_cm": 175.0,
    "start_weight_kg": 90.0,
    "goal_weight_kg": 80.0,
    # Daily movement *excluding* logged workouts (those add a sport bonus).
    "activity_level": "sedentary",
    "kcal_mode": "manual",
    "kcal_base_target": 1900.0,
    "target_rate_kg_week": 0.5,
    "protein_mode": "fixed",
    "protein_target_g": 135.0,
    "protein_g_per_kg": 1.6,
    "oil_normal_g": 5.0,
    "oil_max_g": 10.0,
    "oil_bad_g": 15.0,
    "sport_bonus_factor": 0.35,
    "max_sport_bonus_kcal": 900.0,
}

_NUMERIC_LIMITS = {
    "birth_year": (1900, date.today().year - 10),
    "height_cm": (120, 230),
    "start_weight_kg": (30, 300),
    "goal_weight_kg": (30, 300),
    "kcal_base_target": (1000, 5000),
    "target_rate_kg_week": (0, 1.2),
    "protein_target_g": (40, 300),
    "protein_g_per_kg": (0.8, 3.0),
    "oil_normal_g": (0, 50),
    "oil_max_g": (0, 80),
    "oil_bad_g": (0, 120),
    "sport_bonus_factor": (0, 1),
    "max_sport_bonus_kcal": (0, 3000),
}


def _load_raw() -> dict[str, Any]:
    try:
        with dpp_db.connect() as db:
            row = db.execute("SELECT value FROM app_settings WHERE key='profile'").fetchone()
        data = json.loads(row["value"]) if row else {}
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def get_profile() -> dict[str, Any]:
    profile = dict(DEFAULT_PROFILE)
    profile.update({k: v for k, v in _load_raw().items() if k in DEFAULT_PROFILE})
    return profile


def save_profile(payload: dict[str, Any]) -> dict[str, Any]:
    profile = get_profile()
    for key, value in payload.items():
        if key not in DEFAULT_PROFILE:
            continue
        if key in {"sex", "activity_level", "kcal_mode", "protein_mode"}:
            value = str(value or "").strip().lower() if isinstance(value, (str, type(None))) else "<invalid>"
        if key == "sex":
            if value not in SEXES:
                raise ApiError("Sexo no válido")
        elif key == "activity_level":
            if value not in ACTIVITY_FACTORS:
                raise ApiError("Nivel de actividad no válido")
        elif key == "kcal_mode":
            if value not in KCAL_MODES:
                raise ApiError("Modo de calorías no válido")
        elif key == "protein_mode":
            if value not in PROTEIN_MODES:
                raise ApiError("Modo de proteína no válido")
        elif key == "birth_year":
            value = None if value in (None, "") else int(number(value, "año de nacimiento", minimum=_NUMERIC_LIMITS[key][0], maximum=_NUMERIC_LIMITS[key][1]))
        elif key in _NUMERIC_LIMITS:
            lo, hi = _NUMERIC_LIMITS[key]
            value = round(number(value, key, minimum=lo, maximum=hi), 2)
        profile[key] = value
    if profile["oil_normal_g"] > profile["oil_max_g"] or profile["oil_max_g"] > profile["oil_bad_g"]:
        raise ApiError("Aceite: normal ≤ máximo ≤ alto")
    with dpp_db.connect() as db:
        db.execute(
            "INSERT INTO app_settings(key,value,updated_at) VALUES('profile',?,CURRENT_TIMESTAMP) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=CURRENT_TIMESTAMP",
            (json.dumps(profile, ensure_ascii=False),),
        )
    return profile


def current_weight(profile: dict[str, Any] | None = None) -> float:
    profile = profile or get_profile()
    try:
        with dpp_db.connect() as db:
            latest_official = db.execute(
                "SELECT kg, date FROM weights WHERE official=1 ORDER BY date DESC, time DESC, id DESC LIMIT 1"
            ).fetchone()
            latest_any = db.execute(
                "SELECT kg, date FROM weights ORDER BY date DESC, time DESC, id DESC LIMIT 1"
            ).fetchone()
        # Prefer an official weight unless a reference weight is much more recent.
        pick = latest_official or latest_any
        if latest_official and latest_any and latest_any["date"] > latest_official["date"]:
            days = (date.fromisoformat(latest_any["date"]) - date.fromisoformat(latest_official["date"])).days
            if days > 14:
                pick = latest_any
        if pick and float(pick["kg"] or 0) > 0:
            return float(pick["kg"])
    except Exception:
        pass
    return float(profile.get("start_weight_kg") or DEFAULT_PROFILE["start_weight_kg"])


def bmr_mifflin(profile: dict[str, Any], weight_kg: float) -> float | None:
    sex, year, height = profile.get("sex"), profile.get("birth_year"), profile.get("height_cm")
    if not (sex and year and height and weight_kg):
        return None
    age = date.today().year - int(year)
    base = 10 * weight_kg + 6.25 * float(height) - 5 * age
    return round(base + (5 if sex == "male" else -161))


def compute(profile: dict[str, Any] | None = None, adaptive_tdee: dict[str, Any] | None = None) -> dict[str, Any]:
    """Resolve the effective targets for today from the profile."""
    profile = profile or get_profile()
    weight = current_weight(profile)
    bmr = bmr_mifflin(profile, weight)
    factor = ACTIVITY_FACTORS.get(profile["activity_level"], 1.2)
    tdee_base = round(bmr * factor) if bmr else None
    deficit = round(float(profile["target_rate_kg_week"]) * KCAL_PER_KG / 7)
    missing = [k for k in ("sex", "birth_year", "height_cm") if not profile.get(k)]

    mode_used = "manual"
    kcal_base = float(profile["kcal_base_target"])
    if profile["kcal_mode"] in {"auto", "adaptive"} and tdee_base:
        mode_used, kcal_base = "auto", tdee_base - deficit
    if profile["kcal_mode"] == "adaptive" and adaptive_tdee and adaptive_tdee.get("confidence") in {"media", "alta"}:
        # Measured TDEE already includes the average workout; keep today's sport
        # bonus neutral on average by removing the mean bonus from the base.
        avg_bonus = float(adaptive_tdee.get("avg_workout_kcal") or 0) * float(profile["sport_bonus_factor"])
        mode_used, kcal_base = "adaptive", float(adaptive_tdee["tdee"]) - deficit - avg_bonus
    floor = max(1200.0, float(bmr or 0) * 0.95) if mode_used != "manual" else 1000.0
    kcal_base = round(max(floor, kcal_base))

    if profile["protein_mode"] == "per_kg":
        reference = min(weight, float(profile["goal_weight_kg"]) * 1.15)
        protein_target = round(float(profile["protein_g_per_kg"]) * reference)
    else:
        protein_target = round(float(profile["protein_target_g"]))
    # Same proportions as the historical 120 / 130 / 135 / 150 bands.
    protein = {
        "min_g": round(protein_target * 120 / 135),
        "goal_min_g": round(protein_target * 130 / 135),
        "target_g": protein_target,
        "max_g": round(protein_target * 150 / 135),
    }
    return {
        "weight_kg": round(weight, 2),
        "bmr_kcal": bmr,
        "tdee_without_workouts_kcal": tdee_base,
        "deficit_kcal": deficit,
        "kcal_mode": profile["kcal_mode"],
        "kcal_mode_used": mode_used,
        "kcal_base_target": kcal_base,
        "protein": protein,
        "missing_for_auto": missing,
        "bmi": round(weight / (float(profile["height_cm"]) / 100) ** 2, 1) if profile.get("height_cm") else None,
    }


def _adaptive_tdee_if_needed(profile: dict[str, Any]) -> dict[str, Any] | None:
    if profile.get("kcal_mode") != "adaptive":
        return None
    try:
        import dpp_analytics
        return dpp_analytics.adaptive_tdee()
    except Exception:
        return None


def compute_now(profile: dict[str, Any] | None = None) -> dict[str, Any]:
    """compute() with the measured TDEE when the profile uses adaptive mode."""
    profile = profile or get_profile()
    return compute(profile, _adaptive_tdee_if_needed(profile))


def legacy_targets(adaptive: bool = True) -> dict[str, Any]:
    """Targets in the key layout used by the v0.0.12 insights and Food Intelligence."""
    profile = get_profile()
    c = compute(profile, _adaptive_tdee_if_needed(profile) if adaptive else None)
    p = c["protein"]
    return {
        "height_cm": profile["height_cm"],
        "goal_weight_kg": float(profile["goal_weight_kg"]),
        "fallback_start_weight_kg": float(profile["start_weight_kg"]),
        "protein_min_g": float(p["min_g"]),
        "protein_low_g": float(p["min_g"]),
        "protein_target_min_g": float(p["goal_min_g"]),
        "protein_target_g": float(p["target_g"]),
        "protein_target_max_g": float(p["max_g"]),
        "protein_high_g": float(p["max_g"]),
        "oil_normal_g": float(profile["oil_normal_g"]),
        "oil_max_g": float(profile["oil_max_g"]),
        "oil_bad_g": float(profile["oil_bad_g"]),
        "kcal_base_target": float(c["kcal_base_target"]),
        "max_sport_bonus_kcal": float(profile["max_sport_bonus_kcal"]),
        "sport_bonus_factor": float(profile["sport_bonus_factor"]),
    }


def estimate_met_kcal(met: float, minutes: float, weight_kg: float | None = None) -> float:
    weight = weight_kg or current_weight()
    return round(float(met) * 3.5 * weight / 200 * float(minutes))


def register_profile_routes(app) -> None:
    @app.get("/api/profile")
    def profile_get():
        profile = get_profile()
        tdee = None
        try:
            import dpp_analytics
            tdee = dpp_analytics.adaptive_tdee()
        except Exception:
            tdee = None
        return jsonify({
            "ok": True,
            "profile": profile,
            "computed": compute(profile, tdee),
            "adaptive_tdee": tdee,
            "options": {
                "activity_levels": list(ACTIVITY_FACTORS),
                "kcal_modes": sorted(KCAL_MODES),
                "protein_modes": sorted(PROTEIN_MODES),
            },
        })

    @app.put("/api/profile")
    def profile_put():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            raise ApiError("El perfil debe ser un objeto JSON")
        profile = save_profile(payload)
        return jsonify({"ok": True, "profile": profile, "computed": compute_now(profile), "message": "Objetivos guardados"})
