"""Offline-queue idempotency: a retried POST with the same client_id never creates a second row."""

from __future__ import annotations

import unittest

import _env
import dpp_db
import dpp_entrypoint
from test_api_core import reset_user_data


class ClientIdTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = dpp_entrypoint.app
        cls.app.config.update(TESTING=True)

    def setUp(self) -> None:
        reset_user_data()
        self.client = self.app.test_client()

    def post(self, path, payload):
        return self.client.post(path, json=payload, headers=_env.AUTH)

    def count(self, table: str) -> int:
        with dpp_db.connect() as db:
            return db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

    def test_meal_retry_returns_same_id(self) -> None:
        with dpp_db.connect() as db:
            fid = db.execute("SELECT id FROM foods LIMIT 1").fetchone()["id"]
        payload = {"date": "2026-06-01", "time": "14:00", "name": "Comida", "items": [{"food_id": fid, "grams": 100}], "client_id": "m-1"}
        first, second = self.post("/api/meals", payload), self.post("/api/meals", payload)
        self.assertEqual((first.status_code, second.status_code), (200, 200))
        self.assertEqual(first.get_json(), second.get_json())
        self.assertEqual((self.count("meals"), self.count("meal_items")), (1, 1))

    def test_weight_retry_returns_same_id(self) -> None:
        payload = {"date": "2026-06-01", "time": "07:30", "kg": 80.5, "client_id": "w-1"}
        first, second = self.post("/api/weights", payload), self.post("/api/weights", payload)
        self.assertTrue(first.get_json()["id"])
        self.assertEqual(first.get_json(), second.get_json())
        self.assertEqual(self.count("weights"), 1)

    def test_workout_retry_returns_same_id(self) -> None:
        payload = {"date": "2026-06-01", "time": "19:00", "name": "Run", "minutes": 30, "kcal": 300, "client_id": "k-1"}
        first, second = self.post("/api/workouts", payload), self.post("/api/workouts", payload)
        self.assertTrue(first.get_json()["id"])
        self.assertEqual(first.get_json(), second.get_json())
        self.assertEqual(self.count("workouts"), 1)

    def test_without_client_id_behaves_as_before(self) -> None:
        with dpp_db.connect() as db:
            fid = db.execute("SELECT id FROM foods LIMIT 1").fetchone()["id"]
        meal = {"date": "2026-06-01", "time": "14:00", "name": "Comida", "items": [{"food_id": fid, "grams": 100}]}
        a, b = self.post("/api/meals", meal), self.post("/api/meals", meal)
        self.assertNotEqual(a.get_json()["id"], b.get_json()["id"])
        w = {"date": "2026-06-01", "time": "07:30", "kg": 80.5}
        self.assertFalse(self.post("/api/weights", w).get_json()["duplicate"])
        self.assertTrue(self.post("/api/weights", w).get_json()["duplicate"])
        self.assertEqual((self.count("meals"), self.count("weights")), (2, 1))


if __name__ == "__main__":
    unittest.main()
