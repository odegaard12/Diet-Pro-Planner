#!/usr/bin/env python3
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import dpp_pantry_v019 as pantry


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="dpp-v019-") as tmp:
        target = Path(tmp) / "pantry.json"
        os.environ["DPP_PANTRY"] = str(target)

        saved = pantry._write_pantry([
            {"name": "Pollo", "available": True, "stock": "ok", "category": "protein", "priority": "prefer"},
            {"name": "Atún", "available": True, "stock": "ok", "category": "protein", "priority": "normal"},
            {"name": "Judías verdes", "available": True, "stock": "low", "category": "vegetable", "priority": "prefer"},
            {"name": "Arroz", "available": True, "stock": "ok", "category": "carb", "priority": "normal"},
            {"name": "Nocilla", "available": False, "stock": "out", "category": "sweet", "priority": "avoid", "risk": "anxiety"},
        ])
        assert target.exists(), "pantry.json was not created"
        assert len(saved["items"]) == 5
        assert len({item["id"] for item in saved["items"]}) == 5

        loaded = pantry._read_pantry()
        stats = pantry._stats(loaded)
        assert stats == {"total": 5, "available": 4, "low": 1, "out": 1, "preferred": 2, "avoid": 1}, stats

        options = pantry._meal_options(loaded, "padel", [])
        assert len(options) >= 2, options
        assert "Pollo" in options[0]["primary"]
        assert "50-60 g en seco" in options[0]["primary"]

        alternatives = pantry._meal_options(loaded, "sin_entreno", options[0]["pantry_used"])
        assert alternatives, "expected an alternative after excluding first option"
        assert "Atún" in alternatives[0]["primary"]

        print("OK v0.0.19 pantry: normalization, stats and alternatives")


if __name__ == "__main__":
    main()
