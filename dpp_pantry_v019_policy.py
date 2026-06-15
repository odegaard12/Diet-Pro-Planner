from __future__ import annotations

from typing import Any


def apply_pantry_v019_policy(module: Any) -> None:
    """Prefer solid protein for main-meal alternatives.

    Protein drinks and dairy remain valid pantry items and fallback options, but
    they should not displace chicken, tuna, eggs, ham or similar solid proteins
    in a complete lunch/dinner suggestion when those foods are available.
    """

    original_groups = module._groups

    def strict_groups(pantry, excluded):
        proteins, vegetables, carbs = original_groups(pantry, excluded)
        solid = [
            item for item in proteins
            if item.get("category") in {"protein", "protein_fat"}
        ]
        if solid:
            proteins = solid
        return proteins, vegetables, carbs

    module._groups = strict_groups
