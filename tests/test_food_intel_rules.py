"""Pure-function tests for dpp_food_intel_rules (no Flask)."""

from __future__ import annotations

import unittest

import _env  # noqa: F401
from dpp_food_intel_rules import normalize_body_snapshot, normalize_food_intel_day


def day(items, protein=0, extra=None):
    d = {"totals": {"protein": protein}, "meals": [{"name": "M", "notes": "", "items": [{"food_name": n, "grams": g} for n, g in items]}]}
    d.update(extra or {})
    return d


class RulesTests(unittest.TestCase):
    def test_empty_day_gets_oil_key(self) -> None:
        self.assertEqual(normalize_food_intel_day({}), {"oil_g": 0.0})

    def test_pure_oil_counts_dish_does_not(self) -> None:
        out = normalize_food_intel_day(day([("Aceite oliva virgen extra", 10), ("Pollo al aceite", 200)], extra={"analysis": {"oil_g": 99}}))
        self.assertEqual(out["oil_g"], 10.0)
        self.assertEqual(out["analysis"]["oil_g"], 10.0)

    def test_oil_keys_overwritten_even_if_not_numeric(self) -> None:
        out = normalize_food_intel_day({"oil": 5, "x": {"olive_oil_g": 9, "aceite_g": "n/a"}, "analysis": {}})
        self.assertEqual(out["x"]["aceite_g"], 0.0)

    def test_high_protein_drops_advice_and_softens_status(self) -> None:
        d = day([("Arroz", 100)], protein=140, extra={"tips": ["Cierra con 20-30 g de proteína: x", "Falta proteína útil"]})
        self.assertEqual(normalize_food_intel_day(d)["tips"], ["Proteína en objetivo"])

    def test_low_protein_keeps_advice(self) -> None:
        d = day([("Arroz", 100)], protein=50, extra={"tips": ["Cierra con 20-30 g de proteína: x"]})
        self.assertEqual(normalize_food_intel_day(d)["tips"], ["Cierra con 20-30 g de proteína: x"])

    def test_protein_cacao_is_not_an_extra(self) -> None:
        d = day([("Alpro protein cacao", 200)], extra={"msg": "Extras detectados: chocolate."})
        self.assertEqual(normalize_food_intel_day(d)["msg"], "Sin extras relevantes")

    def test_real_chocolate_still_counts(self) -> None:
        d = day([("Chocolate onzas", 20)], extra={"msg": "Extras detectados: chocolate."})
        self.assertEqual(normalize_food_intel_day(d)["msg"], "Extras detectados: chocolate.")

    def test_cheesecake_galleta_is_safe_plain_galleta_is_not(self) -> None:
        safe = day([("Tarta de queso con galleta", 100)], extra={"msg": "Extras detectados: galleta."})
        self.assertEqual(normalize_food_intel_day(safe)["msg"], "Sin extras relevantes")
        plain = day([("Galleta", 20)], extra={"msg": "Extras detectados: galleta."})
        self.assertEqual(normalize_food_intel_day(plain)["msg"], "Extras detectados: galleta.")

    def test_body_snapshot_aliases(self) -> None:
        out = normalize_body_snapshot({"metrics": {"hybrid_charge": {"value": 7}}})
        self.assertEqual(out["metrics"]["biocharge"], {"value": 7})
        self.assertEqual(len(out["metrics"]), 5)

    def test_body_snapshot_other_shapes_pass_through(self) -> None:
        for data in ({"available": False}, {"metrics": []}, {"metrics": {"weight": {"value": 1}}}):
            self.assertEqual(normalize_body_snapshot(dict(data)), data)


if __name__ == "__main__":
    unittest.main()
