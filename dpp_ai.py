"""Optional AI coach and AI label reading (BYOK, disabled by default).

Policy (see reports/v017c-pantry-ai-byok-plan.md): no central key, keys only in
the local environment, daily limit, response cache and local fallback. The
rule-based Smart Coach keeps working when AI is off or fails.

Configuration (environment only — keys are never written to disk):
- Claude: ``ANTHROPIC_API_KEY`` (+ optional ``DPP_AI_MODEL``, default claude-opus-5-5)
- OpenAI-compatible / local: ``DPP_AI_PROVIDER=openai_compat``, ``DPP_AI_BASE_URL``,
  ``DPP_AI_MODEL`` and optional ``DPP_AI_API_KEY``
- ``DPP_AI_DAILY_LIMIT`` (default 30 calls/day), ``DPP_AI_EFFORT`` (Claude, default medium)

Privacy: only what the request needs leaves the machine — targets, today's
foods and grams, recent averages and pantry names. No names, tokens, notes
or Strava data are sent.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from flask import jsonify, request

import dpp_ai_claude
import dpp_ai_openai_compat
import dpp_config as config
import dpp_db
import dpp_profile
from dpp_ai_claude import ProviderError
from dpp_validate import ApiError, json_body

CACHE_TTL_HOURS = {"coach": 12, "label": 24 * 365}

COACH_SYSTEM = (
    "Eres un dietista-nutricionista deportivo que asesora a una persona adulta que quiere perder grasa "
    "manteniendo músculo. Hablas en español de España, tono directo, práctico y amable, sin moralizar. "
    "Basas cada consejo en los datos recibidos: objetivos, lo comido hoy, entrenos y medias recientes. "
    "Si hay despensa, propones la siguiente comida solo con alimentos de la despensa y cantidades en gramos "
    "(pasta/arroz en seco, carne en crudo, aceite medido). No diagnosticas ni sustituyes a un profesional "
    "sanitario; si los datos sugieren un riesgo (ingesta muy baja, pérdida muy rápida) lo dices con claridad."
)

LABEL_SYSTEM = (
    "Extraes la información nutricional de la foto de una etiqueta de alimento. Devuelve valores POR 100 g "
    "(o 100 ml). Si la etiqueta solo da valores por ración, conviértelos a 100 g usando el tamaño de ración. "
    "La sal en gramos (si solo aparece sodio, sal = sodio x 2,5). Si no puedes leer un valor, usa 0 y baja la "
    "confianza. No inventes datos."
)

COACH_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "headline": {"type": "string", "description": "Resumen del día en una frase corta"},
        "assessment": {"type": "string", "description": "2-3 frases valorando el día frente a los objetivos"},
        "next_meal": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {"food": {"type": "string"}, "grams": {"type": "number"}},
                        "required": ["food", "grams"],
                        "additionalProperties": False,
                    },
                },
                "why": {"type": "string"},
            },
            "required": ["title", "items", "why"],
            "additionalProperties": False,
        },
        "tips": {"type": "array", "items": {"type": "string"}, "description": "Máximo 4 consejos accionables"},
        "warnings": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["headline", "assessment", "next_meal", "tips", "warnings"],
    "additionalProperties": False,
}

LABEL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "brand": {"type": "string"},
        "per_100g": {
            "type": "object",
            "properties": {k: {"type": "number"} for k in ("kcal", "protein", "carbs", "fat", "sugar", "salt")},
            "required": ["kcal", "protein", "carbs", "fat", "sugar", "salt"],
            "additionalProperties": False,
        },
        "serving_g": {"type": "number", "description": "Tamaño de ración en gramos, 0 si no aparece"},
        "confidence": {"type": "string", "enum": ["alta", "media", "baja"]},
        "notes": {"type": "string"},
    },
    "required": ["name", "brand", "per_100g", "serving_g", "confidence", "notes"],
    "additionalProperties": False,
}


def settings() -> dict[str, Any]:
    provider = str(os.environ.get("DPP_AI_PROVIDER") or "").strip().lower()
    has_anthropic = bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))
    if not provider:
        provider = "anthropic" if has_anthropic else ("openai_compat" if os.environ.get("DPP_AI_BASE_URL") else "")
    if provider in {"none", "off", "disabled"}:
        provider = ""
    model = str(os.environ.get("DPP_AI_MODEL") or "").strip()
    if provider == "anthropic":
        model = model or dpp_ai_claude.DEFAULT_MODEL
    effort = str(os.environ.get("DPP_AI_EFFORT") or "medium").strip().lower()
    if effort not in {"low", "medium", "high", "xhigh", "max"}:
        effort = "medium"
    try:
        limit = max(0, int(os.environ.get("DPP_AI_DAILY_LIMIT") or 30))
    except ValueError:
        limit = 30
    enabled = (provider == "anthropic") or (provider == "openai_compat" and bool(os.environ.get("DPP_AI_BASE_URL")) and bool(model))
    return {"enabled": enabled and limit > 0, "provider": provider, "model": model, "effort": effort, "daily_limit": limit}


def _usage_today(db) -> int:
    row = db.execute("SELECT COALESCE(SUM(calls),0) FROM ai_usage WHERE day=?", (date.today().isoformat(),)).fetchone()
    return int(row[0] or 0)


def _record_usage(kind: str, usage: dict[str, int]) -> None:
    with dpp_db.connect() as db:
        db.execute(
            "INSERT INTO ai_usage(day,kind,calls,input_tokens,output_tokens) VALUES(?,?,1,?,?) "
            "ON CONFLICT(day,kind) DO UPDATE SET calls=calls+1, input_tokens=input_tokens+excluded.input_tokens, "
            "output_tokens=output_tokens+excluded.output_tokens",
            (date.today().isoformat(), kind, usage.get("input_tokens", 0), usage.get("output_tokens", 0)),
        )


def _cache_get(key: str, kind: str) -> dict[str, Any] | None:
    hours = CACHE_TTL_HOURS[kind]
    with dpp_db.connect() as db:
        row = db.execute(
            "SELECT response FROM ai_cache WHERE key=? AND kind=? AND created_at >= datetime('now', ?)",
            (key, kind, f"-{hours} hours"),
        ).fetchone()
    return json.loads(row["response"]) if row else None


def _cache_put(key: str, kind: str, value: dict[str, Any]) -> None:
    with dpp_db.connect() as db:
        db.execute(
            "INSERT INTO ai_cache(key,kind,response,created_at) VALUES(?,?,?,CURRENT_TIMESTAMP) "
            "ON CONFLICT(key) DO UPDATE SET response=excluded.response, created_at=CURRENT_TIMESTAMP",
            (key, kind, json.dumps(value, ensure_ascii=False)),
        )
        db.execute("DELETE FROM ai_cache WHERE kind='coach' AND created_at < datetime('now','-7 days')")


def _call(kind: str, *, system: str, text: str, schema: dict[str, Any], image: tuple[bytes, str] | None = None,
          cache_key_extra: str = "") -> tuple[dict[str, Any], bool]:
    cfg = settings()
    if not cfg["enabled"]:
        raise ApiError("IA no configurada: define ANTHROPIC_API_KEY (o un proveedor compatible) en .env", 503)
    key = hashlib.sha256(json.dumps([kind, cfg["provider"], cfg["model"], system, text, cache_key_extra],
                                    ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    cached = _cache_get(key, kind)
    if cached is not None:
        return cached, True
    with dpp_db.connect() as db:
        if _usage_today(db) >= cfg["daily_limit"]:
            raise ApiError(f"Límite diario de IA alcanzado ({cfg['daily_limit']} llamadas). Se reinicia mañana.", 429)
    try:
        if cfg["provider"] == "anthropic":
            result, usage = dpp_ai_claude.generate_json(
                model=cfg["model"], system=system, text=text, schema=schema, image=image, effort=cfg["effort"])
        else:
            result, usage = dpp_ai_openai_compat.generate_json(
                base_url=str(os.environ.get("DPP_AI_BASE_URL") or ""), api_key=str(os.environ.get("DPP_AI_API_KEY") or ""),
                model=cfg["model"], system=system, text=text, schema=schema, image=image)
    except ProviderError as exc:
        raise ApiError(str(exc), exc.status) from None
    _record_usage(kind, usage)
    _cache_put(key, kind, result)
    return result, False


# ---------------------------------------------------------------------------
# Context
# ---------------------------------------------------------------------------

def build_coach_context(day: str) -> dict[str, Any]:
    profile = dpp_profile.get_profile()
    computed = dpp_profile.compute_now(profile)
    with dpp_db.connect() as db:
        meals = []
        for meal in db.execute("SELECT id, time, name FROM meals WHERE date=? ORDER BY time, id", (day,)).fetchall():
            items = db.execute(
                "SELECT food_name, grams, kcal, protein FROM meal_items WHERE meal_id=? ORDER BY id", (meal["id"],)
            ).fetchall()
            meals.append({
                "hora": meal["time"], "tipo": meal["name"],
                "alimentos": [{"nombre": i["food_name"], "g": round(i["grams"]), "kcal": round(i["kcal"]),
                               "proteina_g": round(i["protein"], 1)} for i in items],
            })
        workouts = [{"tipo": w["name"], "min": round(w["minutes"]), "kcal": round(w["kcal"])}
                    for w in db.execute("SELECT name, minutes, kcal FROM workouts WHERE date=? ORDER BY time", (day,))]
        start = (date.fromisoformat(day) - timedelta(days=7)).isoformat()
        recent = db.execute(
            """SELECT COUNT(*) dias, ROUND(AVG(k)) kcal, ROUND(AVG(p),1) proteina FROM (
                 SELECT m.date, SUM(i.kcal) k, SUM(i.protein) p FROM meals m JOIN meal_items i ON i.meal_id=m.id
                 WHERE m.date >= ? AND m.date < ? GROUP BY m.date HAVING SUM(i.kcal) >= 800)""",
            (start, day),
        ).fetchone()
    pantry_names: list[str] = []
    try:
        pantry_path = Path(config.PANTRY_PATH)
        if pantry_path.exists():
            data = json.loads(pantry_path.read_text(encoding="utf-8"))
            pantry_names = [str(i.get("name")) for i in data.get("items") or []
                            if isinstance(i, dict) and i.get("available") and i.get("priority") != "avoid"][:40]
    except (OSError, ValueError):
        pantry_names = []
    totals = {
        "kcal": round(sum(i["kcal"] for m in meals for i in m["alimentos"])),
        "proteina_g": round(sum(i["proteina_g"] for m in meals for i in m["alimentos"]), 1),
    }
    return {
        "fecha": day,
        "objetivos": {
            "kcal_base": computed["kcal_base_target"],
            "bonus_deporte": f"{round(float(profile['sport_bonus_factor']) * 100)}% de las kcal de entreno",
            "proteina_g": [computed["protein"]["goal_min_g"], computed["protein"]["max_g"]],
            "aceite_g_max": profile["oil_max_g"],
            "peso_actual_kg": computed["weight_kg"],
            "peso_objetivo_kg": profile["goal_weight_kg"],
        },
        "hoy": {"comidas": meals, "totales": totals, "entrenos": workouts},
        "ultimos_7_dias": dict(recent) if recent else {},
        "despensa_disponible": pantry_names,
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

def _prepare_image(path: Path, max_side: int = 1568) -> bytes:
    """Upright, downscaled JPEG: fewer tokens and well under provider size limits."""
    from io import BytesIO

    from PIL import Image, ImageOps

    with Image.open(path) as img:
        img = ImageOps.exif_transpose(img).convert("RGB")
        img.thumbnail((max_side, max_side))
        out = BytesIO()
        img.save(out, format="JPEG", quality=88)
    return out.getvalue()


def _label_to_food(label: dict[str, Any]) -> dict[str, Any]:
    per100 = label.get("per_100g") or {}
    bounds = {"kcal": 900, "protein": 100, "carbs": 100, "fat": 100, "sugar": 100, "salt": 100}
    nutrition = {}
    for key, hi in bounds.items():
        try:
            value = float(per100.get(key) or 0)
        except (TypeError, ValueError):
            value = 0.0
        nutrition[key] = round(min(hi, max(0.0, value)), 2)
    serving = float(label.get("serving_g") or 0)
    if 0 < serving <= 2000:
        nutrition["typical_g"] = round(serving, 1)
    return {
        "product": {"name": str(label.get("name") or "")[:160], "brand": str(label.get("brand") or "")[:120]},
        "nutrition": nutrition,
        "confidence": label.get("confidence") or "media",
        "warnings": [str(label.get("notes") or "")] if label.get("notes") else [],
    }


def register_ai_routes(app) -> None:
    @app.get("/api/ai/status")
    def ai_status():
        cfg = settings()
        with dpp_db.connect() as db:
            used = _usage_today(db)
        return jsonify({
            "ok": True, **cfg, "used_today": used,
            "privacy": "Se envían objetivos, alimentos y gramos de hoy, medias recientes y nombres de la despensa. "
                       "Nunca tokens, notas personales ni datos de Strava.",
        })

    @app.post("/api/ai/coach")
    def ai_coach():
        body = json_body()
        day = str(body.get("date") or date.today().isoformat())
        try:
            date.fromisoformat(day)
        except ValueError:
            raise ApiError("Fecha no válida") from None
        question = str(body.get("question") or "").strip()[:500]
        context = build_coach_context(day)
        prompt = "Datos (JSON):\n" + json.dumps(context, ensure_ascii=False, sort_keys=True)
        prompt += "\n\nPregunta concreta: " + question if question else "\n\nDame el análisis del día y la siguiente mejor comida."
        advice, cached = _call("coach", system=COACH_SYSTEM, text=prompt, schema=COACH_SCHEMA)
        cfg = settings()
        return jsonify({"ok": True, "advice": advice, "cached": cached, "provider": cfg["provider"], "model": cfg["model"]})

    @app.post("/api/ai/label")
    def ai_label():
        if "photo" in request.files:
            import app as legacy
            path, photo_url = legacy.save_uploaded_photo()
        else:
            photo_url = str(json_body().get("photo_path") or "")
            name = photo_url.rsplit("/", 1)[-1]
            path = config.UPLOADS_DIR / name
            if not photo_url.startswith("/uploads/") or "/" in name or not path.is_file():
                raise ApiError("Foto no encontrada", 404)
        data = _prepare_image(path)
        digest = hashlib.sha256(data).hexdigest()
        label, cached = _call("label", system=LABEL_SYSTEM, text="Extrae la tabla nutricional de esta etiqueta.",
                              schema=LABEL_SCHEMA, image=(data, "image/jpeg"), cache_key_extra=digest)
        return jsonify({"ok": True, "photo_path": photo_url, "cached": cached, "engine": "ai", **_label_to_food(label)})
