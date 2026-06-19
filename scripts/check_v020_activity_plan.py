#!/usr/bin/env python3
from __future__ import annotations

import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    import flask  # noqa: F401
except ModuleNotFoundError:
    flask_stub = types.ModuleType("flask")
    flask_stub.jsonify = lambda value=None, **kwargs: value if value is not None else kwargs
    flask_stub.request = types.SimpleNamespace()
    sys.modules["flask"] = flask_stub

import dpp_activity_plan_v020 as module


def main() -> None:
    plans = [
        {
            "id": 1, "date": "2026-06-15", "time": "19:00", "title": "Pádel",
            "sport_type": "Pádel", "minutes": 90, "manual_status": "planned",
        },
        {
            "id": 2, "date": "2026-06-16", "time": "18:00", "title": "Carrera suave",
            "sport_type": "Carrera", "minutes": 45, "manual_status": "planned",
        },
        {
            "id": 3, "date": "2026-06-14", "time": "10:00", "title": "Fuerza",
            "sport_type": "Fuerza", "minutes": 60, "manual_status": "planned",
        },
        {
            "id": 4, "date": "2026-06-13", "time": "20:00", "title": "Movilidad",
            "sport_type": "Movilidad + Core", "minutes": 30, "manual_status": "skipped",
        },
    ]
    workouts = [
        {
            "id": 101, "date": "2026-06-15", "time": "19:10", "name": "Padel",
            "minutes": 88, "distance_km": 0, "kcal": 900, "notes": "Strava",
        },
        {
            "id": 102, "date": "2026-06-14", "time": "11:00", "name": "MountainBikeRide",
            "minutes": 95, "distance_km": 19, "kcal": 850, "notes": "Strava",
        },
        {
            "id": 103, "date": "2026-06-15", "time": "21:00", "name": "Walk",
            "minutes": 40, "distance_km": 3, "kcal": 220, "notes": "Strava",
        },
    ]

    matched, extras = module._match_plans(plans, workouts, "2026-06-15")
    by_id = {item["id"]: item for item in matched}

    assert module._category("Pádel por la tarde") == "padel"
    assert module._category("IV Carreira Popular") == "run"
    assert module._category("Vía Verde en bici") == "bike"

    assert by_id[1]["status"] == "completed", by_id[1]
    assert by_id[1]["matched_workout"]["id"] == 101
    assert by_id[2]["status"] == "upcoming", by_id[2]
    assert by_id[3]["status"] == "changed", by_id[3]
    assert by_id[3]["matched_workout"]["id"] == 102
    assert by_id[4]["status"] == "skipped", by_id[4]
    assert [item["id"] for item in extras] == [103], extras

    summary = module._summary(matched, workouts, "2026-06-15")
    assert summary["completed"] == 1
    assert summary["changed"] == 1
    assert summary["skipped"] == 1
    assert summary["upcoming"] == 1
    assert summary["eligible"] == 2
    assert summary["fulfilled"] == 2
    assert summary["adherence_pct"] == 100

    payload = module._plan_payload({
        "date": "2026-06-20", "time": "10:30", "title": "Carrera 8K",
        "sport_type": "Carrera", "minutes": 50, "distance_km": 8,
        "target_kcal": 600, "intensity": "hard", "notes": "A Estrada",
    })
    assert payload["date"] == "2026-06-20"
    assert payload["distance_km"] == 8
    assert payload["intensity"] == "hard"

    print("OK v0.0.20 activity plan: categories, matching, extras, status and summary")


if __name__ == "__main__":
    main()
