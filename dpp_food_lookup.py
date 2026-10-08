"""Food lookup: local catalog by barcode + Open Food Facts (open database, no key).

Only the barcode or the search text leaves the machine. Results are cached
in ``data/off_cache.json``. Disable with ``DPP_OFF_ENABLED=0``.
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
from typing import Any

import requests
from flask import jsonify, request

import dpp_config as config
import dpp_db
from dpp_validate import ApiError

USER_AGENT = f"DietProPlanner/{config.VERSION.lstrip('v')} (self-hosted; github.com/odegaard12/Diet-Pro-Planner)"
FIELDS = "code,product_name,product_name_es,generic_name,brands,nutriments,serving_quantity,serving_size,quantity,nutriscore_grade,nova_group"
CACHE_FILE = config.DATA_DIR / "off_cache.json"
CACHE_TTL_SECONDS = 30 * 86400
_CACHE_LOCK = threading.Lock()
_BARCODE_RE = re.compile(r"^\d{8,14}$")


def enabled() -> bool:
    return str(os.environ.get("DPP_OFF_ENABLED", "1")).strip().lower() not in {"0", "false", "no", "off"}


def _country() -> str:
    value = str(os.environ.get("DPP_OFF_COUNTRY") or "es").strip().lower()
    return value if re.fullmatch(r"[a-z]{2}|world", value) else "es"


def _read_cache() -> dict[str, Any]:
    try:
        data = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _cache(key: str, value: Any | None = None) -> Any:
    with _CACHE_LOCK:
        cache = _read_cache()
        if value is None:
            hit = cache.get(key)
            if isinstance(hit, dict) and time.time() - float(hit.get("t", 0)) < CACHE_TTL_SECONDS:
                return hit.get("v")
            return None
        cache[key] = {"t": time.time(), "v": value}
        if len(cache) > 600:
            for old in sorted(cache, key=lambda k: cache[k].get("t", 0))[: len(cache) - 500]:
                cache.pop(old, None)
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = CACHE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
        tmp.replace(CACHE_FILE)
        return value


def _num(nutriments: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = nutriments.get(key)
        try:
            if value not in (None, ""):
                return float(value)
        except (TypeError, ValueError):
            continue
    return None


def normalize_product(product: dict[str, Any]) -> dict[str, Any] | None:
    n = product.get("nutriments") or {}
    kcal = _num(n, "energy-kcal_100g")
    if kcal is None:
        kj = _num(n, "energy-kj_100g", "energy_100g")
        kcal = kj / 4.184 if kj is not None else None
    salt = _num(n, "salt_100g")
    if salt is None:
        sodium = _num(n, "sodium_100g")
        salt = sodium * 2.5 if sodium is not None else None
    name = str(product.get("product_name_es") or product.get("product_name") or product.get("generic_name") or "").strip()
    if not name or kcal is None:
        return None
    brand = str(product.get("brands") or "").split(",")[0].strip()
    serving = _num(product, "serving_quantity")
    values = {
        "kcal": kcal, "protein": _num(n, "proteins_100g"), "carbs": _num(n, "carbohydrates_100g"),
        "fat": _num(n, "fat_100g"), "sugar": _num(n, "sugars_100g"), "salt": salt,
    }
    missing = [k for k, v in values.items() if v is None]
    caps = {"kcal": 900, "protein": 100, "carbs": 100, "fat": 100, "sugar": 100, "salt": 100}
    food = {k: round(min(caps[k], max(0.0, v or 0.0)), 2) for k, v in values.items()}
    code = str(product.get("code") or "")
    food.update({
        "name": (f"{name} {brand}".strip() if brand and brand.lower() not in name.lower() else name)[:160],
        "brand": brand[:120],
        "typical_g": round(serving, 1) if serving and 0 < serving <= 2000 else 100,
        "barcode": code if _BARCODE_RE.match(code) else "",
        "source_note": (
            f"Open Food Facts · código {code} · por 100 g"
            + (f" · ración {product.get('serving_size')}" if product.get("serving_size") else "")
            + (f" · faltan: {', '.join(missing)}" if missing else "")
        ),
        "nutriscore": str(product.get("nutriscore_grade") or "").upper()[:1],
        "nova": product.get("nova_group"),
        "complete": not missing,
    })
    return food


def _get(url: str, params: dict[str, Any]) -> dict[str, Any]:
    try:
        response = requests.get(url, params=params, headers={"User-Agent": USER_AGENT}, timeout=12)
    except requests.RequestException:
        raise ApiError("Open Food Facts no responde; prueba más tarde", 502) from None
    if response.status_code == 404:
        return {}
    if response.status_code == 429:
        raise ApiError("Open Food Facts limita las búsquedas; espera un minuto", 429)
    if response.status_code >= 400:
        raise ApiError(f"Open Food Facts devolvió {response.status_code}", 502)
    try:
        return response.json()
    except ValueError:
        raise ApiError("Respuesta no válida de Open Food Facts", 502) from None


def local_by_barcode(code: str) -> dict[str, Any] | None:
    with dpp_db.connect() as db:
        cols = {row[1] for row in db.execute("PRAGMA table_info(foods)").fetchall()}
        if "barcode" not in cols:
            return None
        row = db.execute("SELECT * FROM foods WHERE barcode=? LIMIT 1", (code,)).fetchone()
    return dict(row) if row else None


def lookup_barcode(code: str) -> dict[str, Any]:
    if not _BARCODE_RE.match(code):
        raise ApiError("Código de barras no válido (8 a 14 dígitos)")
    local = local_by_barcode(code)
    if local:
        return {"found": True, "source": "local", "food": local, "cached": False}
    if not enabled():
        return {"found": False, "source": "none", "food": None, "cached": False}
    cached = _cache(f"code:{code}")
    if cached is not None:
        return {"found": bool(cached), "source": "openfoodfacts", "food": cached or None, "cached": True}
    data = _get(f"https://world.openfoodfacts.org/api/v2/product/{code}", {"fields": FIELDS})
    food = normalize_product(data.get("product") or {}) if data.get("status") in (1, "1") else None
    _cache(f"code:{code}", food or {})
    return {"found": bool(food), "source": "openfoodfacts", "food": food, "cached": False}


def search_online(query: str) -> list[dict[str, Any]]:
    query = re.sub(r"\s+", " ", query).strip()[:80]
    if len(query) < 3:
        raise ApiError("Escribe al menos 3 letras")
    if not enabled():
        raise ApiError("Búsqueda online desactivada (DPP_OFF_ENABLED=0)", 503)
    key = f"q:{_country()}:{query.lower()}"
    cached = _cache(key)
    if cached is not None:
        return cached
    host = "world" if _country() == "world" else _country()
    data = _get(f"https://{host}.openfoodfacts.org/cgi/search.pl", {
        "search_terms": query, "search_simple": 1, "action": "process", "json": 1,
        "page_size": 12, "fields": FIELDS,
    })
    results = [food for food in (normalize_product(p) for p in data.get("products") or []) if food]
    return _cache(key, results[:10])


def register_food_lookup_routes(app) -> None:
    @app.get("/api/foods/barcode/<code>")
    def food_barcode(code: str):
        return jsonify({"ok": True, **lookup_barcode(code.strip())})

    @app.get("/api/foods/search-online")
    def food_search_online():
        return jsonify({"ok": True, "results": search_online(str(request.args.get("q") or ""))})
