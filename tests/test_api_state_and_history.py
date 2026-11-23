"""Extra /api/state characterization: limits, ordering and empty shape.

Complements test_state_snapshot.py, which already pins meals/items/totals equality.
"""

from __future__ import annotations

import unittest

import _env
import dpp_db
import dpp_entrypoint
from test_api_core import reset_user_data


class StateLimitsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = dpp_entrypoint.app
        cls.app.config.update(TESTING=True)

    def setUp(self) -> None:
        reset_user_data()
        self.client = self.app.test_client()

    def state(self):
        resp = self.client.get("/api/state", headers=_env.AUTH)
        self.assertEqual(resp.status_code, 200)
        return resp.get_json()

    def test_empty_state_shape(self) -> None:
        s = self.state()
        for key in ("today", "now", "foods", "exercises", "weights", "meals", "workouts", "templates", "plans"):
            self.assertIn(key, s)
        self.assertEqual((s["meals"], s["weights"], s["workouts"]), ([], [], []))

    def test_more_than_300_meals_are_trimmed_newest_first(self) -> None:
        with dpp_db.connect() as db:
            for i in range(305):
                db.execute("INSERT INTO meals(date,time,name) VALUES(?,?,?)", (f"2026-01-{1 + i // 24:02d}", f"{i % 24:02d}:00", f"m{i}"))
        meals = self.state()["meals"]
        self.assertEqual(len(meals), 300)
        keys = [(m["date"], m["time"], m["id"]) for m in meals]
        self.assertEqual(keys, sorted(keys, reverse=True))
        names = {m["name"] for m in meals}
        self.assertEqual(meals[0]["name"], "m304")
        self.assertNotIn("m0", names)  # the 5 oldest rows are dropped
        self.assertNotIn("m4", names)
        self.assertIn("m5", names)

    def test_same_slot_ties_break_by_id_descending(self) -> None:
        with dpp_db.connect() as db:
            for name in ("a", "b", "c"):
                db.execute("INSERT INTO meals(date,time,name) VALUES('2026-06-01','12:00',?)", (name,))
        self.assertEqual([m["name"] for m in self.state()["meals"]], ["c", "b", "a"])

    def test_meal_items_are_attached_only_to_their_meal_in_id_order(self) -> None:
        with dpp_db.connect() as db:
            m1 = db.execute("INSERT INTO meals(date,time,name) VALUES('2026-06-01','08:00','one')").lastrowid
            m2 = db.execute("INSERT INTO meals(date,time,name) VALUES('2026-06-01','09:00','two')").lastrowid
            for mid, fname in ((m1, "x"), (m2, "y"), (m1, "z")):
                db.execute("INSERT INTO meal_items(meal_id,food_name,grams,kcal) VALUES(?,?,?,?)", (mid, fname, 100, 10))
        by_name = {m["name"]: [i["food_name"] for i in m["items"]] for m in self.state()["meals"]}
        self.assertEqual(by_name, {"one": ["x", "z"], "two": ["y"]})

    def test_weights_trim_to_300_newest_first(self) -> None:
        with dpp_db.connect() as db:
            for i in range(302):
                db.execute("INSERT INTO weights(date,time,kg) VALUES(?,?,?)", (f"2026-{1 + i // 28:02d}-{1 + i % 28:02d}", "07:00", 70 + i / 100))
        weights = self.state()["weights"]
        self.assertEqual(len(weights), 300)
        dates = [w["date"] for w in weights]
        self.assertEqual(dates, sorted(dates, reverse=True))

    def test_workouts_trim_to_300_newest_first(self) -> None:
        with dpp_db.connect() as db:
            for i in range(302):
                db.execute(
                    "INSERT INTO workouts(date,time,name,minutes,notes) VALUES(?,?,?,?,?)",
                    (f"2026-{1 + i // 28:02d}-{1 + i % 28:02d}", "18:00", f"w{i}", 30, ""),
                )
        workouts = self.state()["workouts"]
        self.assertEqual(len(workouts), 300)
        self.assertEqual(workouts[0]["name"], "w301")
        self.assertNotIn("w0", {w["name"] for w in workouts})


if __name__ == "__main__":
    unittest.main()
