from __future__ import annotations

import ipaddress
import json
import os
import re
import unicodedata
from datetime import date, datetime
from pathlib import Path
from typing import Any

from flask import jsonify, request

import dpp_smart_coach as smart


VERSION = "v0.0.19-dev"
CATEGORIES = {
    "protein", "protein_drink", "protein_fat", "vegetable", "carb",
    "fruit", "dairy", "sweet", "drink", "other",
}
PRIORITIES = {"prefer", "normal", "secondary", "avoid"}


def _plain(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(ch for ch in text if not unicodedata.combining(ch)).lower()


def _slug(value: Any) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", _plain(value)).strip("-")
    return slug[:60] or "item"


def _private_request() -> bool:
    raw = request.headers.get("X-Forwarded-For", request.remote_addr or "")
    raw = raw.split(",", 1)[0].strip()
    try:
        address = ipaddress.ip_address(raw)
        return bool(address.is_private or address.is_loopback or address.is_link_local)
    except ValueError:
        return raw in {"localhost", "srv-web-01"}


def _pantry_path() -> Path:
    return Path(os.environ.get("DPP_PANTRY", smart.DEFAULT_PANTRY))


def _normalize_item(raw: Any, used_ids: set[str]) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    name = str(raw.get("name") or "").strip()[:100]
    if not name:
        return None

    base_id = _slug(raw.get("id") or name)
    item_id = base_id
    index = 2
    while item_id in used_ids:
        item_id = f"{base_id}-{index}"
        index += 1
    used_ids.add(item_id)

    category = _slug(raw.get("category") or "other").replace("-", "_")
    if category not in CATEGORIES:
        category = "other"
    priority = _plain(raw.get("priority") or "normal")
    if priority not in PRIORITIES:
        priority = "normal"

    available = raw.get("available") is True
    stock = str(raw.get("stock") or ("ok" if available else "out")).strip().lower()
    if stock not in {"ok", "low", "out"}:
        stock = "ok" if available else "out"
    if stock == "out":
        available = False

    item = {
        "id": item_id,
        "name": name,
        "available": available,
        "stock": stock,
        "category": category,
        "priority": priority,
        "notes": str(raw.get("notes") or "").strip()[:500],
    }
    risk = str(raw.get("risk") or "").strip()[:80]
    if risk:
        item["risk"] = risk
    return item


def _read_pantry() -> dict[str, Any]:
    path = _pantry_path()
    payload: dict[str, Any] = {}
    try:
        if path.exists():
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                payload = loaded
    except Exception:
        payload = {}

    used_ids: set[str] = set()
    items: list[dict[str, Any]] = []
    for raw in payload.get("items") or []:
        item = _normalize_item(raw, used_ids)
        if item:
            items.append(item)

    return {
        "version": 2,
        "updated_at": payload.get("updated_at") or "",
        "items": items,
    }


def _write_pantry(items: list[Any]) -> dict[str, Any]:
    used_ids: set[str] = set()
    clean: list[dict[str, Any]] = []
    for raw in items:
        item = _normalize_item(raw, used_ids)
        if item:
            clean.append(item)

    payload = {
        "version": 2,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "items": clean,
    }
    path = _pantry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        tmp.chmod(0o600)
    except Exception:
        pass
    tmp.replace(path)
    try:
        path.chmod(0o600)
    except Exception:
        pass
    return payload


def _stats(pantry: dict[str, Any]) -> dict[str, int]:
    items = pantry.get("items") or []
    return {
        "total": len(items),
        "available": sum(1 for item in items if item.get("available")),
        "low": sum(1 for item in items if item.get("stock") == "low"),
        "out": sum(1 for item in items if not item.get("available") or item.get("stock") == "out"),
        "preferred": sum(1 for item in items if item.get("available") and item.get("priority") == "prefer"),
        "avoid": sum(1 for item in items if item.get("priority") == "avoid"),
    }


def _priority(item: dict[str, Any]) -> tuple[int, str]:
    order = {"prefer": 0, "normal": 1, "secondary": 2, "avoid": 9}
    return order.get(str(item.get("priority")), 5), _plain(item.get("name"))


def _groups(pantry: dict[str, Any], excluded: set[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    available = [
        item for item in pantry.get("items") or []
        if item.get("available") and item.get("stock") != "out"
        and item.get("priority") != "avoid"
        and _plain(item.get("name")) not in excluded
    ]
    available.sort(key=_priority)
    proteins = [item for item in available if item.get("category") in {"protein", "protein_drink", "protein_fat", "dairy"}]
    vegetables = [item for item in available if item.get("category") == "vegetable"]
    carbs = [item for item in available if item.get("category") in {"carb", "fruit"}]
    return proteins, vegetables, carbs


def _protein_amount(name: str) -> str:
    value = _plain(name)
    if "pollo" in value or "pavo" in value:
        return "200-250 g"
    if "atun" in value:
        return "120-160 g"
    if "huevo" in value:
        return "2-3 unidades"
    if "jamon" in value:
        return "100-140 g"
    if "yogur" in value or "alpro" in value or "queso fresco" in value:
        return "1-2 raciones"
    return "1 ración alta"


def _meal_options(pantry: dict[str, Any], training_type: str, excluded_names: list[str]) -> list[dict[str, Any]]:
    excluded = {_plain(name) for name in excluded_names if name}
    proteins, vegetables, carbs = _groups(pantry, excluded)
    if not proteins:
        return []

    vegetables = vegetables or [None]
    carbs = carbs or [None]
    active = training_type in {"padel", "entreno_fuerte", "carrera", "bici", "entreno_moderado"}
    carb_amount = "50-60 g en seco" if active else "35-50 g en seco"

    options: list[dict[str, Any]] = []
    for p_index, protein in enumerate(proteins[:6]):
        vegetable = vegetables[p_index % len(vegetables)]
        carb = carbs[(p_index + (1 if len(carbs) > 1 else 0)) % len(carbs)]
        parts = [f"{protein['name']} {_protein_amount(protein['name'])}"]
        used = [protein["name"]]
        if vegetable:
            parts.append(f"{vegetable['name']} 250-300 g")
            used.append(vegetable["name"])
        if carb:
            parts.append(f"{carb['name']} {carb_amount}")
            used.append(carb["name"])
        options.append({
            "title": "Otra comida posible",
            "primary": " + ".join(parts) + ".",
            "why": "Alternativa construida solo con alimentos marcados como disponibles en tu despensa.",
            "avoid": [item["name"] for item in pantry.get("items") or [] if item.get("available") and item.get("priority") == "avoid"][:6],
            "pantry_used": used,
            "source": "pantry_v019",
        })
    return options


def _alternative(day: str, excluded_names: list[str], offset: int = 0) -> dict[str, Any]:
    db_path = os.environ.get("DPP_DB", smart.DEFAULT_DB)
    base = smart.build_smart_coach_day(db_path, day)
    coach = base.get("coach") or {}
    pantry = _read_pantry()
    options = _meal_options(pantry, str(coach.get("training_type") or "sin_entreno"), excluded_names)
    if not options:
        return {
            "ok": False,
            "error": "No quedan combinaciones suficientes. Actualiza la despensa o vuelve a activar algún alimento.",
            "pantry": pantry,
        }
    selected = options[max(0, int(offset)) % len(options)]
    return {
        "ok": True,
        "version": VERSION,
        "date": day,
        "alternative": selected,
        "alternatives_available": len(options),
        "pantry": {"available": True, "used": selected.get("pantry_used", []), "stats": _stats(pantry)},
    }


def register_pantry_v019(app, legacy) -> None:
    @app.get("/api/pantry/v2")
    def pantry_v2_get():
        pantry = _read_pantry()
        return jsonify({"ok": True, "version": VERSION, "pantry": pantry, "stats": _stats(pantry)})

    @app.post("/api/pantry/v2")
    def pantry_v2_save():
        if not _private_request():
            return jsonify({"ok": False, "error": "La despensa solo se puede editar desde la red local"}), 403
        payload = request.get_json(silent=True) or {}
        items = payload.get("items")
        if not isinstance(items, list):
            return jsonify({"ok": False, "error": "items debe ser una lista"}), 400
        pantry = _write_pantry(items)
        return jsonify({"ok": True, "version": VERSION, "message": "Despensa guardada", "pantry": pantry, "stats": _stats(pantry)})

    @app.post("/api/smart-coach/alternative")
    def smart_coach_alternative():
        payload = request.get_json(silent=True) or {}
        day = str(payload.get("date") or date.today().isoformat())
        excluded = payload.get("exclude") if isinstance(payload.get("exclude"), list) else []
        offset = int(payload.get("offset") or 0)
        result = _alternative(day, [str(value) for value in excluded], offset)
        return jsonify(result), (200 if result.get("ok") else 409)

    @app.post("/api/smart-coach/unavailable")
    def smart_coach_unavailable():
        if not _private_request():
            return jsonify({"ok": False, "error": "Acción disponible solo desde la red local"}), 403
        payload = request.get_json(silent=True) or {}
        names = payload.get("names") if isinstance(payload.get("names"), list) else []
        normalized = {_plain(value) for value in names if value}
        if not normalized:
            return jsonify({"ok": False, "error": "Selecciona al menos un alimento"}), 400

        pantry = _read_pantry()
        changed: list[str] = []
        for item in pantry.get("items") or []:
            if _plain(item.get("name")) in normalized:
                item["available"] = False
                item["stock"] = "out"
                changed.append(str(item.get("name")))
        pantry = _write_pantry(pantry.get("items") or [])

        day = str(payload.get("date") or date.today().isoformat())
        result = _alternative(day, changed, int(payload.get("offset") or 0))
        result.update({"changed": changed, "message": f"Marcado como no disponible: {', '.join(changed)}", "stats": _stats(pantry)})
        return jsonify(result), (200 if result.get("ok") else 409)

    # During branch validation, expose the actual candidate version without editing legacy app.py.
    for rule in list(app.url_map.iter_rules()):
        if rule.rule == "/health":
            app.view_functions[rule.endpoint] = lambda: jsonify({
                "app": "Diet Pro Planner", "ok": True, "version": VERSION
            })
            break
