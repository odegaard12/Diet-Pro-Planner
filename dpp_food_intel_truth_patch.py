"""
Diet Pro Planner truth patch.

Small response-normalization layer for:
- body snapshot BioCharge / Zepp Hybrid Charge aliases
- Food Intelligence false positives:
  - oil counted from non-pure-oil food names
  - cacao/chocolate protein products
  - galleta inside cheesecake wording
  - protein advice when protein is already high

This module is intentionally small and removable once the canonical
Food Intelligence backend is refactored into a proper day-dashboard endpoint.
"""

from __future__ import annotations

import json
import re
from copy import deepcopy
from typing import Any


PURE_OIL_NAMES = {
    "aceite",
    "aceite oliva",
    "aceite de oliva",
    "aceite oliva virgen extra",
    "aove",
    "aceite oliva virgen",
}

PROTEIN_CHOCOLATE_PATTERNS = (
    "alpro protein cacao",
    "alpro protein chocolate",
    "batido proteico chocolate",
    "batido proteico 7 proteínas",
    "batido proteico 7 proteinas",
    "proteína cacao",
    "proteina cacao",
)

SAFE_GALLETA_CONTEXTS = (
    "tarta queso con galleta",
    "tarta de queso con galleta",
    "base de galleta",
    "queso con galleta",
)


def _lower_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).casefold()


def _num(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _iter_meal_items(day: dict[str, Any]):
    for meal in day.get("meals") or []:
        if not isinstance(meal, dict):
            continue
        for item in meal.get("items") or []:
            if isinstance(item, dict):
                yield item


def _item_name(item: dict[str, Any]) -> str:
    return str(
        item.get("food_name")
        or item.get("food")
        or item.get("name")
        or item.get("label")
        or ""
    )


def _item_grams(item: dict[str, Any]) -> float:
    return _num(item.get("grams", item.get("g", item.get("amount_g"))), 0.0)


def _is_pure_oil_item(item: dict[str, Any]) -> bool:
    name = _lower_text(_item_name(item)).strip()
    normalized = re.sub(r"\s+", " ", name)

    if normalized in PURE_OIL_NAMES:
        return True

    # Allow specific pure-oil names with brand/detail, but reject dishes where
    # oil is only a cooking method or ingredient phrase.
    if normalized.startswith("aceite oliva ") or normalized.startswith("aceite de oliva "):
        return True

    return False


def _recompute_pure_oil_grams(day: dict[str, Any]) -> float:
    return round(sum(_item_grams(item) for item in _iter_meal_items(day) if _is_pure_oil_item(item)), 1)


def _all_food_text(day: dict[str, Any]) -> str:
    chunks: list[str] = []
    for meal in day.get("meals") or []:
        if not isinstance(meal, dict):
            continue
        chunks.append(str(meal.get("name") or ""))
        chunks.append(str(meal.get("notes") or ""))
        for item in meal.get("items") or []:
            if isinstance(item, dict):
                chunks.append(_item_name(item))
    return " ".join(chunks).casefold()


def _has_only_safe_galleta(text: str) -> bool:
    if "galleta" not in text:
        return False

    cleaned = text
    for ctx in SAFE_GALLETA_CONTEXTS:
        cleaned = cleaned.replace(ctx, " ")

    return "galleta" not in cleaned


def _has_only_safe_chocolate(text: str) -> bool:
    if "chocolate" not in text and "cacao" not in text:
        return False

    cleaned = text
    for pat in PROTEIN_CHOCOLATE_PATTERNS:
        cleaned = cleaned.replace(pat, " ")

    # Real chocolate item names should still count.
    real_chocolate = (
        "chocolate onzas",
        "onzas chocolate",
        "chocolate pre",
        "chocolate post",
        "churro con chocolate",
        "churros con chocolate",
    )
    if any(p in cleaned for p in real_chocolate):
        return False

    return "chocolate" not in cleaned and "cacao" not in cleaned


def _protein_total(day: dict[str, Any]) -> float:
    totals = day.get("totals")
    if isinstance(totals, dict):
        p = totals.get("protein", totals.get("protein_g"))
        if p is not None:
            return _num(p)

    total = 0.0
    for meal in day.get("meals") or []:
        if not isinstance(meal, dict):
            continue
        mt = meal.get("totals")
        if isinstance(mt, dict):
            total += _num(mt.get("protein", mt.get("protein_g")))
    return total


def _clean_string(value: str, *, protein_g: float, text_blob: str) -> str:
    out = value

    # Remove/soften protein advice when the day already has enough protein.
    if protein_g >= 130:
        if "Cierra con 20-30 g de proteína" in out:
            return ""
        out = out.replace("Falta proteína útil", "Proteína en objetivo")
        out = out.replace("objetivo 130-150 g", "Proteína en objetivo")

    if _has_only_safe_galleta(text_blob):
        out = re.sub(r"No añadas más extras hoy:\s*galleta\.?", "", out, flags=re.I).strip()
        out = re.sub(r"Extras detectados:\s*galleta\.?", "Sin extras relevantes", out, flags=re.I).strip()

    if _has_only_safe_chocolate(text_blob):
        out = re.sub(r"No añadas más extras hoy:\s*chocolate\.?", "", out, flags=re.I).strip()
        out = re.sub(r"Extras detectados:\s*chocolate\.?", "Sin extras relevantes", out, flags=re.I).strip()

    out = re.sub(r"\s{2,}", " ", out).strip()
    return out


def _walk_clean(obj: Any, *, protein_g: float, text_blob: str) -> Any:
    if isinstance(obj, str):
        return _clean_string(obj, protein_g=protein_g, text_blob=text_blob)

    if isinstance(obj, list):
        cleaned = [_walk_clean(x, protein_g=protein_g, text_blob=text_blob) for x in obj]
        return [x for x in cleaned if x not in ("", None)]

    if isinstance(obj, dict):
        return {k: _walk_clean(v, protein_g=protein_g, text_blob=text_blob) for k, v in obj.items()}

    return obj


def _set_oil_keys(obj: Any, oil_g: float) -> Any:
    if isinstance(obj, list):
        return [_set_oil_keys(x, oil_g) for x in obj]

    if isinstance(obj, dict):
        for key in list(obj.keys()):
            lk = str(key).casefold()
            if lk in {"oil_g", "oil_grams", "oilgrams", "olive_oil_g", "aceite_g"}:
                obj[key] = oil_g
            elif lk == "oil" and isinstance(obj.get(key), (int, float)):
                obj[key] = oil_g
            else:
                obj[key] = _set_oil_keys(obj[key], oil_g)
    return obj


def normalize_body_snapshot(data: dict[str, Any]) -> dict[str, Any]:
    metrics = data.get("metrics")
    if not isinstance(metrics, dict):
        return data

    source = None
    for key in ("biocharge_current", "biocharge_wakeup", "biocharge", "hybrid_charge", "hybird_charge"):
        if isinstance(metrics.get(key), dict):
            source = metrics[key]
            break

    if source:
        for alias in ("biocharge_current", "biocharge_wakeup", "biocharge", "hybrid_charge", "hybird_charge"):
            metrics.setdefault(alias, deepcopy(source))

    return data


def normalize_food_intel_day(data: dict[str, Any]) -> dict[str, Any]:
    text_blob = _all_food_text(data)
    protein_g = _protein_total(data)
    oil_g = _recompute_pure_oil_grams(data)

    data = _walk_clean(data, protein_g=protein_g, text_blob=text_blob)
    data = _set_oil_keys(data, oil_g)

    # Explicit top-level/back-compat keys for dashboard consumers.
    data["oil_g"] = oil_g
    if isinstance(data.get("analysis"), dict):
        data["analysis"]["oil_g"] = oil_g

    # If protein is clearly enough, do not leave contradictory message fields.
    if protein_g >= 130 and isinstance(data.get("analysis"), dict):
        for key in ("protein_label", "protein_status", "protein_message"):
            if key in data["analysis"] and isinstance(data["analysis"][key], str):
                data["analysis"][key] = _clean_string(data["analysis"][key], protein_g=protein_g, text_blob=text_blob)

    return data


def _replace_json_response(response, data: dict[str, Any]):
    body = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    response.set_data(body)
    response.headers["Content-Type"] = "application/json; charset=utf-8"
    response.headers["Content-Length"] = str(len(body.encode("utf-8")))
    return response


def register_food_intel_truth_patch(app):
    @app.after_request
    def dpp_truth_patch_after_request(response):  # pragma: no cover - Flask hook
        try:
            import flask

            path = flask.request.path or ""
            if not response.is_json:
                return response

            if path == "/api/body-snapshot/latest":
                data = response.get_json(silent=True)
                if isinstance(data, dict):
                    return _replace_json_response(response, normalize_body_snapshot(data))

            if path == "/api/food-intel/day":
                data = response.get_json(silent=True)
                if isinstance(data, dict):
                    return _replace_json_response(response, normalize_food_intel_day(data))

        except Exception:
            return response

        return response
