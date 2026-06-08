#!/usr/bin/env python3
"""
Diet Pro Planner known-days regression checks.

These checks validate the current private/local demo dataset served by the
running app. They intentionally hit localhost and are meant as a deployment
smoke/regression guard, not as public fixture data.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from typing import Any, Dict


BASE = os.environ.get("DPP_BASE_URL", "http://127.0.0.1:8099").rstrip("/")

EXPECTED = {'2026-06-03': {'label': 'Buen día',
                'meal_rows': [{'kcal': 315.8, 'name': 'Desayuno', 'protein': 32.5, 'time': '10:25'},
                              {'kcal': 668.4, 'name': 'Comida', 'protein': 34.7, 'time': '14:45'},
                              {'kcal': 339.9, 'name': 'Merienda', 'protein': 16.6, 'time': '17:45'},
                              {'kcal': 82.5, 'name': 'Extra pre-entreno', 'protein': 0.9, 'time': '18:45'},
                              {'kcal': 220.0, 'name': 'Extra antes de cenar', 'protein': 2.4, 'time': '21:15'},
                              {'kcal': 612.0, 'name': 'Cena', 'protein': 33.1, 'time': '22:00'},
                              {'kcal': 68.4, 'name': 'Postre proteico', 'protein': 10.2, 'time': '22:20'}],
                'meals': 7,
                'score': 93,
                'total_kcal': 2307.0,
                'total_protein': 130.4},
 '2026-06-04': {'label': 'Cuidado',
                'meal_rows': [{'kcal': 361.7, 'name': 'Desayuno', 'protein': 8.4, 'time': '08:00'},
                              {'kcal': 40.0, 'name': 'Café oficina', 'protein': 0.0, 'time': '11:30'},
                              {'kcal': 729.2, 'name': 'Comida', 'protein': 60.2, 'time': '15:30'},
                              {'kcal': 133.5, 'name': 'Pre-entreno', 'protein': 1.6, 'time': '16:00'},
                              {'kcal': 82.5, 'name': 'Chocolate pre', 'protein': 0.9, 'time': '17:00'},
                              {'kcal': 274.8, 'name': 'Merienda recuperación', 'protein': 25.2, 'time': '19:00'},
                              {'kcal': 165.0, 'name': 'Chocolate vuelta', 'protein': 1.8, 'time': '20:45'},
                              {'kcal': 510.6, 'name': 'Cena', 'protein': 24.6, 'time': '22:00'}],
                'meals': 8,
                'score': 78,
                'total_kcal': 2297.3,
                'total_protein': 122.7},
 '2026-06-05': {'label': 'Buen día',
                'meal_rows': [{'kcal': 567.8, 'name': 'Desayuno', 'protein': 33.0, 'time': '10:30'},
                              {'kcal': 803.1, 'name': 'Comida', 'protein': 72.3, 'time': '15:00'},
                              {'kcal': 240.4, 'name': 'Merienda', 'protein': 22.7, 'time': '20:30'},
                              {'kcal': 353.5, 'name': 'Cena pre pádel', 'protein': 30.2, 'time': '22:00'}],
                'meals': 4,
                'score': 85,
                'total_kcal': 1964.8,
                'total_protein': 158.2}}

KCAL_TOLERANCE = 1.0
PROTEIN_TOLERANCE = 0.5


def fetch_json(path: str) -> Dict[str, Any]:
    with urllib.request.urlopen(BASE + path, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def as_float(value: Any) -> float | None:
    try:
        return float(value)
    except Exception:
        return None


def meal_value(meal: Dict[str, Any], key: str) -> float:
    direct = as_float(meal.get(key))
    if direct is not None:
        return direct

    totals = meal.get("totals") or {}
    nested = as_float(totals.get(key))
    if nested is not None:
        return nested

    if key == "protein":
        for alt in ["protein_g", "total_protein"]:
            value = as_float(meal.get(alt))
            if value is not None:
                return value

    if key == "kcal":
        for alt in ["calories", "total_kcal"]:
            value = as_float(meal.get(alt))
            if value is not None:
                return value

    return 0.0


def extract_day(day: str) -> Dict[str, Any]:
    data = fetch_json(f"/api/food-intel/day?date={day}")
    analysis = data.get("analysis") or {}
    meals = data.get("meals") or []
    totals = data.get("totals") or {}

    kcal = (
        as_float(totals.get("kcal"))
        or as_float(totals.get("total_kcal"))
        or as_float(analysis.get("total_kcal"))
        or as_float(analysis.get("kcal"))
        or sum(meal_value(meal, "kcal") for meal in meals)
    )

    protein = (
        as_float(totals.get("protein"))
        or as_float(totals.get("total_protein"))
        or as_float(analysis.get("total_protein"))
        or as_float(analysis.get("protein"))
        or sum(meal_value(meal, "protein") for meal in meals)
    )

    return {
        "score": analysis.get("score"),
        "label": analysis.get("label"),
        "meals": len(meals),
        "total_kcal": round(float(kcal or 0), 1),
        "total_protein": round(float(protein or 0), 1),
        "meal_rows": [
            {
                "time": meal.get("time") or "",
                "name": meal.get("name") or meal.get("title") or "Comida",
                "kcal": round(meal_value(meal, "kcal"), 1),
                "protein": round(meal_value(meal, "protein"), 1),
            }
            for meal in meals
        ],
    }


def fail(message: str) -> None:
    print("ERROR:", message)
    sys.exit(1)


def assert_close(day: str, field: str, actual: float, expected: float, tolerance: float) -> None:
    if abs(actual - expected) > tolerance:
        fail(f"{day}: expected {field} {expected}, got {actual}")


def main() -> None:
    print("Diet Pro Planner known-days regression checks")
    print("Base:", BASE)

    for day, expected in EXPECTED.items():
        actual = extract_day(day)

        print()
        print(f"== {day} ==")
        print("score:", actual["score"])
        print("label:", actual["label"])
        print("meals:", actual["meals"])
        print("total_kcal:", actual["total_kcal"])
        print("total_protein:", actual["total_protein"])

        for row in actual["meal_rows"]:
            print(f"  {row['time']} · {row['name']}: {row['kcal']} kcal · {row['protein']} g prot")

        if actual["score"] != expected["score"]:
            fail(f"{day}: expected score {expected['score']}, got {actual['score']}")
        if actual["label"] != expected["label"]:
            fail(f"{day}: expected label {expected['label']}, got {actual['label']}")
        if actual["meals"] != expected["meals"]:
            fail(f"{day}: expected {expected['meals']} meals, got {actual['meals']}")

        assert_close(day, "total_kcal", actual["total_kcal"], expected["total_kcal"], KCAL_TOLERANCE)
        assert_close(day, "total_protein", actual["total_protein"], expected["total_protein"], PROTEIN_TOLERANCE)

    print()
    print("OK: known days regression checks passed")


if __name__ == "__main__":
    main()
