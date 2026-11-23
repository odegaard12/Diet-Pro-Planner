"""Characterization tests for /api/food-intel/day and /api/body-snapshot/latest
as produced by the rules in dpp_food_intel_rules.py (formerly an after_request hook).

They pin CURRENT behaviour (including odd corners) so a refactor cannot change
it silently. Do not "fix" an expectation here without fixing the code on purpose.
"""

from __future__ import annotations

import unittest

import _env
import dpp_db
import dpp_entrypoint
import dpp_food_intel_rules as patch
from test_api_core import reset_user_data

DAY = "2026-06-01"
PROTEIN_ADVICE = "Cierra con 20-30 g de proteína: merluza, huevo, jamón, atún, Alpro o yogur proteico."
# Makes the day analysable (>= 2 meals and >= 600 kcal).
FILLER = ("20:00", "Cena", "", [("Arroz", 200, 700, 6)])


class FoodIntelDayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = dpp_entrypoint.app
        cls.app.config.update(TESTING=True)

    def setUp(self) -> None:
        reset_user_data()
        self.client = self.app.test_client()

    def day(self, meals, filler=True):
        meals = list(meals) + ([FILLER] if filler else [])
        with dpp_db.connect() as db:
            for time, name, notes, items in meals:
                mid = db.execute("INSERT INTO meals(date,time,name,notes) VALUES(?,?,?,?)", (DAY, time, name, notes)).lastrowid
                for fname, grams, kcal, prot in items:
                    db.execute(
                        "INSERT INTO meal_items(meal_id,food_name,grams,kcal,protein,carbs,fat,sugar,salt) VALUES(?,?,?,?,?,?,?,?,?)",
                        (mid, fname, grams, kcal, prot, 0, 0, 0, 0),
                    )
        resp = self.client.get(f"/api/food-intel/day?date={DAY}", headers=_env.AUTH)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers["Content-Type"], "application/json; charset=utf-8")
        self.assertEqual(int(resp.headers["Content-Length"]), len(resp.data))
        return resp.get_json()

    @staticmethod
    def extras(d):
        return d["analysis"]["rules"]["extras"]

    @staticmethod
    def notes_of(d, meal_name):
        return [m["notes"] for m in d["meals"] if m["name"] == meal_name][0]

    # ---- oil rule -------------------------------------------------------
    def test_oil_counts_only_pure_oil_items(self) -> None:
        d = self.day([("12:00", "Comida", "", [("Aceite de oliva", 10, 90, 0), ("Pollo con aceite", 100, 100, 20)])])
        self.assertEqual(d["oil_g"], 10.0)
        self.assertEqual(d["analysis"]["oil_g"], 10.0)
        self.assertEqual(d["summary"]["oil_g"], 10.0)  # the legacy value would be 110
        self.assertEqual(d["meals"][0]["oil_g"], 10.0)
        # current behaviour: the oil rule score/message is computed BEFORE the rewrite
        # from the legacy 110 g, so it still says "Aceite alto" next to oil_g == 10.
        self.assertEqual(d["analysis"]["rules"]["oil"]["message"], "Aceite alto")

    def test_oil_brand_prefix_counts_and_dish_with_oil_does_not(self) -> None:
        d = self.day([("12:00", "Comida", "", [("Aceite oliva Hacendado", 5, 45, 0), ("Patatas fritas en aceite", 200, 300, 4)])])
        self.assertEqual(d["oil_g"], 5.0)

    def test_oil_zero_when_no_oil_item(self) -> None:
        d = self.day([("12:00", "Comida", "", [("Pollo", 100, 100, 20)])])
        self.assertEqual(d["oil_g"], 0.0)
        self.assertEqual(d["analysis"]["oil_g"], 0.0)
        self.assertEqual(d["analysis"]["rules"]["oil"]["message"], "Aceite controlado")

    def test_insufficient_day_still_gets_oil_keys(self) -> None:
        d = self.day([("12:00", "Comida", "", [("Aceite", 10, 90, 0)])], filler=False)
        self.assertEqual(d["analysis"]["semaphore"], "insufficient")
        self.assertEqual(d["analysis"]["rules"], {})
        self.assertEqual(d["analysis"]["oil_g"], 10.0)
        self.assertEqual(d["oil_g"], 10.0)

    # ---- cacao / chocolate rule ----------------------------------------
    def test_protein_cacao_drink_is_not_an_extra(self) -> None:
        d = self.day([("12:00", "Comida", "", [("Alpro Protein cacao", 250, 170, 12)])])
        self.assertEqual(self.extras(d)["hits"], [])
        self.assertEqual(self.extras(d)["message"], "Sin extras relevantes")

    def test_protein_chocolate_drink_extra_is_removed(self) -> None:
        d = self.day([("12:00", "Comida", "", [("Batido proteico chocolate", 250, 170, 25)])])
        # current behaviour: hits keeps "chocolate" but message and advice are cleaned
        self.assertEqual(self.extras(d)["hits"], ["chocolate"])
        self.assertEqual(self.extras(d)["message"], "Sin extras relevantes")
        self.assertEqual(d["analysis"]["recommendations"], [PROTEIN_ADVICE])

    def test_real_chocolate_still_counts(self) -> None:
        d = self.day([("12:00", "Comida", "", [("Chocolate onzas", 20, 100, 1)])])
        self.assertEqual(self.extras(d)["message"], "Extras detectados: chocolate")
        self.assertIn("No añadas más extras hoy: chocolate.", d["analysis"]["recommendations"])

    def test_protein_chocolate_plus_real_chocolate_keeps_extra(self) -> None:
        d = self.day([("12:00", "Comida", "", [("Batido proteico chocolate", 250, 170, 25), ("Churros con chocolate", 100, 300, 3)])])
        self.assertEqual(self.extras(d)["message"], "Extras detectados: chocolate")

    # ---- galleta rule ---------------------------------------------------
    def test_galleta_inside_cheesecake_is_not_an_extra(self) -> None:
        d = self.day([("12:00", "Postre", "", [("Tarta de queso con galleta", 100, 300, 5)])])
        self.assertEqual(self.extras(d)["hits"], ["galleta"])  # current behaviour: raw hits untouched
        self.assertEqual(self.extras(d)["message"], "Sin extras relevantes")
        self.assertEqual(d["analysis"]["recommendations"], [PROTEIN_ADVICE])

    def test_plain_galleta_still_counts(self) -> None:
        d = self.day([("12:00", "Postre", "", [("Galleta maria", 30, 100, 2)])])
        self.assertEqual(self.extras(d)["message"], "Extras detectados: galleta")
        self.assertIn("No añadas más extras hoy: galleta.", d["analysis"]["recommendations"])

    def test_cheesecake_plus_plain_galleta_keeps_extra(self) -> None:
        d = self.day([("12:00", "Postre", "", [("Tarta de queso con galleta", 100, 300, 5), ("Galleta maria", 30, 100, 2)])])
        self.assertEqual(self.extras(d)["message"], "Extras detectados: galleta")

    def test_safe_galleta_with_real_chocolate_leaves_artifacts(self) -> None:
        d = self.day([("12:00", "Postre", "", [("Tarta de queso con galleta", 100, 300, 5), ("Chocolate pre", 20, 100, 1)])])
        # current behaviour: the galleta rule strips "galleta" out of the joined extras text,
        # leaving odd fragments instead of a clean message.
        self.assertEqual(self.extras(d)["message"], "Sin extras relevantes, chocolate")
        self.assertEqual(d["analysis"]["recommendations"], [PROTEIN_ADVICE, ", chocolate."])

    # ---- protein advice rule -------------------------------------------
    def test_high_protein_has_no_protein_advice(self) -> None:
        d = self.day([("12:00", "Comida", "", [("Pollo", 500, 500, 140)])])
        self.assertGreaterEqual(d["summary"]["protein"], 130)
        self.assertEqual(d["analysis"]["recommendations"], ["Mantén el plan actual; no añadas extras."])

    def test_low_protein_keeps_protein_advice(self) -> None:
        d = self.day([("12:00", "Comida", "", [("Pollo", 500, 500, 50)])])
        self.assertLess(d["summary"]["protein"], 130)
        self.assertEqual(d["analysis"]["recommendations"], [PROTEIN_ADVICE])
        self.assertEqual(d["analysis"]["main_action"], PROTEIN_ADVICE)

    def test_high_protein_rewrites_user_notes_too(self) -> None:
        d = self.day([("12:00", "Comida", "Falta proteína útil (objetivo 130-150 g)", [("Pollo", 500, 500, 140)])])
        # current behaviour: every string in the response is rewritten, including user notes
        self.assertEqual(self.notes_of(d, "Comida"), "Proteína en objetivo (Proteína en objetivo)")

    def test_high_protein_blanks_advice_text_held_in_a_dict_value(self) -> None:
        d = self.day([("12:00", "Comida", "Cierra con 20-30 g de proteína", [("Pollo", 500, 500, 140)])])
        self.assertEqual(self.notes_of(d, "Comida"), "")  # list entries are dropped, dict values just become ""

    def test_low_protein_leaves_user_notes_alone(self) -> None:
        d = self.day([("12:00", "Comida", "Falta proteína útil", [("Pollo", 500, 500, 50)])])
        self.assertEqual(self.notes_of(d, "Comida"), "Falta proteína útil")

    # ---- direct pins on the normalizer ---------------------------------
    def test_normalize_food_intel_day_edge_inputs(self) -> None:
        self.assertEqual(patch.normalize_food_intel_day({}), {"oil_g": 0.0})
        out = patch.normalize_food_intel_day({"oil": 5, "x": {"olive_oil_g": 9, "aceite_g": "n/a"}, "analysis": {}})
        self.assertEqual(out["oil"], 0.0)
        self.assertEqual(out["x"]["olive_oil_g"], 0.0)
        self.assertEqual(out["x"]["aceite_g"], 0.0)  # current behaviour: overwritten even when not numeric
        self.assertEqual(out["analysis"], {"oil_g": 0.0})

    def test_other_food_intel_routes_are_untouched(self) -> None:
        resp = self.client.get("/api/food-intel/health", headers=_env.AUTH)
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn("oil_g", resp.get_json())


class BodySnapshotTests(unittest.TestCase):
    ALIASES = ("biocharge_current", "biocharge_wakeup", "biocharge", "hybrid_charge", "hybird_charge")

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = dpp_entrypoint.app
        cls.app.config.update(TESTING=True)

    def setUp(self) -> None:
        self.client = self.app.test_client()
        self.drop()

    def tearDown(self) -> None:
        self.drop()

    @staticmethod
    def drop() -> None:
        with dpp_db.connect() as db:
            db.execute("DROP TABLE IF EXISTS body_composition")

    @staticmethod
    def seed(rows) -> None:
        with dpp_db.connect() as db:
            db.execute(
                "CREATE TABLE body_composition(id INTEGER PRIMARY KEY, date TEXT, time TEXT, metric TEXT,"
                " value REAL, unit TEXT, source TEXT, confidence TEXT, notes TEXT)"
            )
            for date, time, metric, value in rows:
                db.execute(
                    "INSERT INTO body_composition(date,time,metric,value,unit,source,confidence,notes) VALUES(?,?,?,?,?,?,?,?)",
                    (date, time, metric, value, "u", "scale", None, None),
                )

    def get(self):
        resp = self.client.get("/api/body-snapshot/latest", headers=_env.AUTH)
        self.assertEqual(resp.status_code, 200)
        return resp.get_json()

    def test_missing_table_is_unavailable(self) -> None:
        self.assertEqual(
            self.get(),
            {"ok": True, "available": False, "version": "v0.0.14.1", "reason": "body_composition table not found"},
        )

    def test_empty_table_is_unavailable(self) -> None:
        self.seed([])
        self.assertEqual(self.get()["reason"], "no body composition records")

    def test_single_alias_is_copied_to_all_aliases(self) -> None:
        self.seed([("2026-06-01", "07:00", "hybrid_charge", 80.0), ("2026-06-01", "07:00", "weight", 80.0)])
        m = self.get()["metrics"]
        for alias in self.ALIASES:
            self.assertEqual(m[alias]["value"], 80.0, alias)
            self.assertEqual(m[alias]["source"], "scale")
            self.assertEqual(m[alias]["confidence"], "media")  # null confidence -> default
        self.assertEqual(sorted(m), sorted(set(self.ALIASES) | {"weight"}))

    def test_alias_priority_and_existing_values_win(self) -> None:
        self.seed([("2026-06-01", "07:00", "biocharge", 60.0), ("2026-06-01", "07:00", "hybrid_charge", 90.0)])
        m = self.get()["metrics"]
        # biocharge precedes hybrid_charge in the search order, so it is the copy source
        self.assertEqual(m["biocharge_current"]["value"], 60.0)
        self.assertEqual(m["biocharge_wakeup"]["value"], 60.0)
        self.assertEqual(m["hybrid_charge"]["value"], 90.0)  # setdefault: an existing key is not overwritten
        self.assertEqual(m["hybird_charge"]["value"], 60.0)

    def test_no_charge_metric_leaves_metrics_untouched(self) -> None:
        self.seed([("2026-06-01", "07:00", "weight", 80.0)])
        d = self.get()
        self.assertEqual(list(d["metrics"]), ["weight"])
        self.assertEqual(d["derived"], {"fat_mass_kg": None, "lean_mass_kg": None, "muscle_weight_pct": None})

    def test_latest_snapshot_deltas_and_previous(self) -> None:
        self.seed([
            ("2026-05-30", "07:00", "weight", 81.0),
            ("2026-05-30", "07:00", "biocharge_wakeup", 50.0),
            ("2026-06-01", "07:00", "weight", 80.0),
            ("2026-06-01", "07:00", "body_fat_pct", 20.0),
            ("2026-06-01", "07:00", "biocharge_wakeup", 70.0),
        ])
        d = self.get()
        self.assertEqual(d["date"], "2026-06-01")
        self.assertEqual(d["previous"], {"date": "2026-05-30", "time": "07:00"})
        self.assertEqual(d["deltas"], {"weight": -1.0, "biocharge_wakeup": 20.0})  # body_fat_pct has no previous value
        self.assertEqual(d["derived"]["fat_mass_kg"], 16.0)
        self.assertEqual(d["derived"]["lean_mass_kg"], 64.0)
        self.assertIn(d["freshness"]["label"], ("recent", "old"))  # depends on today's date vs the fixed 2026-06-01
        # current behaviour: alias copies are added by the hook after deltas were computed
        self.assertNotIn("biocharge_current", d["deltas"])
        self.assertEqual(d["metrics"]["biocharge_current"]["value"], 70.0)


if __name__ == "__main__":
    unittest.main()
