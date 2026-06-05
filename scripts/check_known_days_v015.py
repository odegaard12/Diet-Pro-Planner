#!/usr/bin/env python3
"""
Local regression checks for Diet Pro Planner real user days.

This script is intentionally local-first:
- It validates the running local app at http://127.0.0.1:8099.
- It does not include private food logs or database files.
- It only checks aggregate expectations that are already visible in the app/API.
"""

from __future__ import annotations

import json
import math
import sys
import urllib.request
from dataclasses import dataclass
from typing import Any


BASE = "http://127.0.0.1:8099"


@dataclass(frozen=True)
class MealExpectation:
    marker: str
    kcal: float
    protein: float
    tolerance_kcal: float = 3.0
    tolerance_protein: float = 0.4


@dataclass(frozen=True)
class DayExpectation:
    date: str
    meals_count: int | None = None
    min_score: int | None = None
    max_score: int | None = None
    total_kcal: float | None = None
    total_protein: float | None = None
    tolerance_kcal: float = 8.0
    tolerance_protein: float = 0.8
    meal_expectations: tuple[MealExpectation, ...] = ()


EXPECTED_DAYS: tuple[DayExpectation, ...] = (
    DayExpectation(
        date="2026-06-03",
        meals_count=None,
        min_score=85,
        max_score=100,
    ),
    DayExpectation(
        date="2026-06-04",
        meals_count=8,
        min_score=80,
        max_score=95,
        total_protein=122.7,
        meal_expectations=(
            MealExpectation("REAL_0406_DESAYUNO_TOSTADAS_PLATANO", 361.7, 8.4),
            MealExpectation("REAL_0406_CAFE_OFICINA", 40.0, 0.0),
            MealExpectation("REAL_0406_COMIDA_3_FAJITAS_POLLO_PIMIENTO", 729.0, 60.2),
            MealExpectation("REAL_0406_CENA_HUEVOS_CHORIZO_PAN", 511.0, 24.6),
        ),
    ),
    DayExpectation(
        date="2026-06-05",
        meals_count=3,
        min_score=85,
        max_score=100,
        total_kcal=1554.0,
        total_protein=135.7,
        meal_expectations=(
            MealExpectation("REAL_0506_DESAYUNO_TOSTADA_CACAHUETE_BANANA_YOGUR_ALPRO", 568.4, 33.0),
            MealExpectation("REAL_0506_COMIDA_POLLO_PASTA_SALTEADO_SETAS_GAMBAS", 627.7, 64.8),
            MealExpectation("REAL_0506_MERIENDA_COCHE_PRE_PADEL_BATIDO_PLATANO", 357.9, 37.9),
        ),
    ),
)


def fetch_json(path: str) -> dict[str, Any]:
    url = BASE + path
    with urllib.request.urlopen(url, timeout=20) as response:
        raw = response.read().decode("utf-8")
    return json.loads(raw)


def approx(actual: float, expected: float, tolerance: float) -> bool:
    return math.isfinite(actual) and abs(actual - expected) <= tolerance


def get_day(date: str) -> dict[str, Any]:
    return fetch_json(f"/api/food-intel/day?date={date}")


def meal_by_marker(day: dict[str, Any], marker: str) -> dict[str, Any] | None:
    for meal in day.get("meals", []):
        notes = str(meal.get("notes") or "")
        if marker in notes:
            return meal
    return None


def fail(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    raise SystemExit(1)


def check_day(exp: DayExpectation) -> None:
    day = get_day(exp.date)
    meals = day.get("meals", [])
    analysis = day.get("analysis", {})
    score = analysis.get("score")

    print(f"\n== {exp.date} ==")
    print("score:", score)
    print("label:", analysis.get("label"))
    print("meals:", len(meals))

    if exp.meals_count is not None and len(meals) != exp.meals_count:
        fail(f"{exp.date}: expected {exp.meals_count} meals, got {len(meals)}")

    if exp.min_score is not None and score is not None and score < exp.min_score:
        fail(f"{exp.date}: score too low: {score} < {exp.min_score}")

    if exp.max_score is not None and score is not None and score > exp.max_score:
        fail(f"{exp.date}: score too high: {score} > {exp.max_score}")

    totals = day.get("totals") or {}
    # Some versions expose aggregate totals under analysis/cards only.
    total_kcal = totals.get("kcal")
    total_protein = totals.get("protein")

    if total_kcal is None:
        total_kcal = sum(float((m.get("totals") or {}).get("kcal") or 0) for m in meals)
    if total_protein is None:
        total_protein = sum(float((m.get("totals") or {}).get("protein") or 0) for m in meals)

    print("total_kcal:", round(float(total_kcal), 1))
    print("total_protein:", round(float(total_protein), 1))

    if exp.total_kcal is not None and not approx(float(total_kcal), exp.total_kcal, exp.tolerance_kcal):
        fail(f"{exp.date}: total kcal expected {exp.total_kcal}, got {total_kcal}")

    if exp.total_protein is not None and not approx(float(total_protein), exp.total_protein, exp.tolerance_protein):
        fail(f"{exp.date}: total protein expected {exp.total_protein}, got {total_protein}")

    for meal_exp in exp.meal_expectations:
        meal = meal_by_marker(day, meal_exp.marker)
        if not meal:
            fail(f"{exp.date}: missing meal marker {meal_exp.marker}")

        mt = meal.get("totals") or {}
        kcal = float(mt.get("kcal") or 0)
        protein = float(mt.get("protein") or 0)

        print(
            f"{meal.get('time', '')} · {meal.get('name', '')}: "
            f"{round(kcal, 1)} kcal · {round(protein, 1)} g prot"
        )

        if not approx(kcal, meal_exp.kcal, meal_exp.tolerance_kcal):
            fail(f"{exp.date}: {meal_exp.marker} kcal expected {meal_exp.kcal}, got {kcal}")

        if not approx(protein, meal_exp.protein, meal_exp.tolerance_protein):
            fail(f"{exp.date}: {meal_exp.marker} protein expected {meal_exp.protein}, got {protein}")


def main() -> int:
    print("Diet Pro Planner known-days regression checks")
    print("Base:", BASE)

    # Health smoke.
    try:
        fetch_json("/api/food-intel/health")
    except Exception as exc:
        print(f"WARN: /api/food-intel/health unavailable or non-json: {exc}")

    for exp in EXPECTED_DAYS:
        check_day(exp)

    print("\nOK: known days regression checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
