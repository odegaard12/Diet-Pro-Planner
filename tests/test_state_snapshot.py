"""Pins the /api/state meals output (order, fields, totals) so the query strategy can change safely."""

from __future__ import annotations

import unittest

import _env
import dpp_db
import dpp_entrypoint
from test_api_core import reset_user_data


class StateSnapshotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = dpp_entrypoint.app
        cls.app.config.update(TESTING=True)

    def setUp(self) -> None:
        reset_user_data()
        self.client = self.app.test_client()

    def test_state_meals_match_per_meal_reference(self) -> None:
        legacy = dpp_entrypoint.legacy
        with dpp_db.connect() as db:
            for date, time, name, n_items in (
                ("2026-06-01", "08:00", "Desayuno", 2),
                ("2026-06-01", "14:00", "Comida", 3),
                ("2026-06-02", "09:00", "Vacia", 0),
                ("2026-06-02", "21:00", "Cena", 1),
            ):
                mid = db.execute("INSERT INTO meals(date,time,name) VALUES(?,?,?)", (date, time, name)).lastrowid
                for i in range(n_items):
                    db.execute(
                        "INSERT INTO meal_items(meal_id,food_name,grams,kcal,protein,carbs,fat,sugar,salt) VALUES(?,?,?,?,?,?,?,?,?)",
                        (mid, f"{name}-{i}", 100 + i, 50.5 + i, 3.25, 10.1, 1.2, 0.5, 0.123),
                    )
            expected = [
                {**dict(m), "items": its, "totals": legacy.totals(its)}
                for m in db.execute("SELECT * FROM meals ORDER BY date DESC, time DESC, id DESC LIMIT 300").fetchall()
                for its in [[dict(r) for r in db.execute("SELECT * FROM meal_items WHERE meal_id=? ORDER BY id", (m["id"],))]]
            ]
        got = self.client.get("/api/state", headers=_env.AUTH).get_json()["meals"]
        self.assertEqual([m["name"] for m in got], ["Cena", "Vacia", "Comida", "Desayuno"])
        self.assertEqual([len(m["items"]) for m in got], [1, 0, 3, 2])
        self.assertEqual(got[1]["totals"], legacy.totals([]))
        self.assertEqual(got, expected)


if __name__ == "__main__":
    unittest.main()
