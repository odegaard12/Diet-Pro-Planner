#!/usr/bin/env python3
"""
Diet Pro Planner v0.0.15 known-days regression checks.

These checks protect dashboard/Food Intelligence behavior for real known days
after dashboard refactor and Food Intelligence truth normalization.

They intentionally validate only stable aggregate facts:
- score
- label
- meal count
- total kcal
- total protein

Private DB content is not committed; this script only checks the local running
instance at http://127.0.0.1:8099.
"""

from __future__ import annotations

import json
import math
import sys
import urllib.error
import urllib.request


BASE = "http://127.0.0.1:8099"

EXPECTED = {
    "2026-06-03": {
        "score": 93,
        "label": "Buen día",
        "meals": 7,
        "kcal": 2307.0,
        "protein": 130.4,
    },
    "2026-06-04": {
        "score": 83,
        "label": "Buen día",
        "meals": 8,
        "kcal": 2297.3,
        "protein": 122.7,
    },
    "2026-06-05": {
        "score": 90,
        "label": "Buen día",
        "meals": 4,
        "kcal": 1964.8,
        "protein": 158.2,
    },
}

TOLERANCE_KCAL = 1.0
TOLERANCE_PROTEIN = 0.3


def fetch_json(path: str) -> dict:
    url = BASE + path
    try:
        with urllib.request.urlopen(url, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"HTTP ERROR {exc.code} {url}\n{body[:2000]}") from exc
    except Exception as exc:
        raise SystemExit(f"ERROR fetching {url}: {exc}") from exc


def totals_from_day(day: dict) -> tuple[float, float]:
    totals = day.get("totals")
    if isinstance(totals, dict) and ("kcal" in totals or "protein" in totals):
        return float(totals.get("kcal") or 0), float(totals.get("protein") or 0)

    kcal = 0.0
    protein = 0.0
    for meal in day.get("meals") or []:
        mt = meal.get("totals") or {}
        kcal += float(mt.get("kcal") or 0)
        protein += float(mt.get("protein") or 0)
    return kcal, protein


def assert_close(date: str, name: str, got: float, expected: float, tolerance: float) -> None:
    if not math.isclose(got, expected, abs_tol=tolerance):
        raise AssertionError(
            f"{date}: expected {name} {expected}, got {got} "
            f"(tolerance {tolerance})"
        )


def check_day(date: str, expected: dict) -> None:
    day = fetch_json(f"/api/food-intel/day?date={date}")
    analysis = day.get("analysis") or {}
    meals = day.get("meals") or []
    kcal, protein = totals_from_day(day)

    score = analysis.get("score")
    label = analysis.get("label")

    print(f"\n== {date} ==")
    print("score:", score)
    print("label:", label)
    print("meals:", len(meals))
    print("total_kcal:", round(kcal, 1))
    print("total_protein:", round(protein, 1))

    if score != expected["score"]:
        raise AssertionError(f"{date}: expected score {expected['score']}, got {score}")

    if label != expected["label"]:
        raise AssertionError(f"{date}: expected label {expected['label']!r}, got {label!r}")

    if len(meals) != expected["meals"]:
        raise AssertionError(f"{date}: expected {expected['meals']} meals, got {len(meals)}")

    assert_close(date, "kcal", round(kcal, 1), expected["kcal"], TOLERANCE_KCAL)
    assert_close(date, "protein", round(protein, 1), expected["protein"], TOLERANCE_PROTEIN)

    for meal in meals:
        mt = meal.get("totals") or {}
        print(
            f"  {meal.get('time')} · {meal.get('name')}: "
            f"{round(float(mt.get('kcal') or 0), 1)} kcal · "
            f"{round(float(mt.get('protein') or 0), 1)} g prot"
        )


def main() -> int:
    print("Diet Pro Planner known-days regression checks")
    print("Base:", BASE)

    try:
        fetch_json("/api/food-intel/health")
    except SystemExit:
        # Some older builds may not expose health consistently; main day API is enough.
        pass

    for date, expected in EXPECTED.items():
        check_day(date, expected)

    print("\nOK: known days regression checks passed")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print("ERROR:", exc)
        raise SystemExit(1)
