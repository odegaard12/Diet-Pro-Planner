from __future__ import annotations

import io
import unittest
from datetime import date, timedelta

import _env
import dpp_db
import dpp_entrypoint
from dpp_analytics import _ema, _slope_per_day, adaptive_tdee


def reset_user_data() -> None:
    with dpp_db.connect() as db:
        for table in ("meal_items", "meals", "workouts", "weights"):
            db.execute(f"DELETE FROM {table}")
        db.execute("DELETE FROM app_settings")


class CoreApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = dpp_entrypoint.app
        cls.app.config.update(TESTING=True)

    def setUp(self) -> None:
        reset_user_data()
        self.client = self.app.test_client()

    def post(self, path, payload):
        return self.client.post(path, json=payload, headers=_env.AUTH)

    def food_id(self, name="Pollo pechuga cruda Pazo de Pías"):
        with dpp_db.connect() as db:
            return db.execute("SELECT id FROM foods WHERE name=?", (name,)).fetchone()["id"]

    def test_identical_meals_are_both_saved_with_items(self) -> None:
        payload = {"date": "2026-06-01", "time": "14:00", "name": "Comida", "items": [{"food_id": self.food_id(), "grams": 200}]}
        first, second = self.post("/api/meals", payload), self.post("/api/meals", payload)
        self.assertEqual((first.status_code, second.status_code), (200, 200))
        self.assertNotEqual(first.get_json()["id"], second.get_json()["id"])
        with dpp_db.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM meal_items").fetchone()[0], 2)

    def test_validation_errors_are_json_400(self) -> None:
        cases = [
            ("/api/weights", {"kg": "abc"}),
            ("/api/weights", {"kg": 5}),
            ("/api/meals", {"items": []}),
            ("/api/meals", {"items": [{"food_id": self.food_id(), "grams": -3}]}),
            ("/api/meals", {"date": "2026-13-40", "items": [{"food_id": self.food_id(), "grams": 10}]}),
            ("/api/foods", {"name": "X", "protein": 80, "carbs": 80}),
            ("/api/foods", {"name": "X", "barcode": "12ab"}),
            ("/api/plans", {"raw": "{not json"}),
        ]
        for path, payload in cases:
            with self.subTest(path=path, payload=payload):
                response = self.post(path, payload)
                self.assertEqual(response.status_code, 400)
                self.assertFalse(response.get_json()["ok"])

    def test_malformed_bodies_are_400(self) -> None:
        for path, payload in (("/api/meals", [1, 2]), ("/api/weights", ["x"]),
                              ("/api/meals", {"items": [{"food_id": {"x": 1}, "grams": 10}]})):
            with self.subTest(path=path, payload=payload):
                self.assertEqual(self.client.post(path, json=payload, headers=_env.AUTH).status_code, 400)
        response = self.client.put("/api/profile", json={"activity_level": []}, headers=_env.AUTH)
        self.assertEqual(response.status_code, 400)

    def test_zero_grams_falls_back_to_typical_portion(self) -> None:
        mid = self.post("/api/meals", {"items": [{"food_name": "Arroz seco", "grams": 0}]}).get_json()["id"]
        with dpp_db.connect() as db:
            grams = db.execute("SELECT grams FROM meal_items WHERE meal_id=?", (mid,)).fetchone()[0]
        self.assertEqual(grams, 80.0)

    def test_seed_does_not_resurrect_deleted_foods(self) -> None:
        import app
        fid = self.food_id("Manzana")
        self.assertEqual(self.client.delete(f"/api/foods/{fid}", headers=_env.AUTH).status_code, 200)
        with dpp_db.connect() as db:
            db.execute("INSERT OR IGNORE INTO app_settings(key,value) VALUES('seed_done','true')")
        app.init_db()
        with dpp_db.connect() as db:
            self.assertIsNone(db.execute("SELECT 1 FROM foods WHERE name='Manzana'").fetchone())

    def test_state_foods_always_have_ids(self) -> None:
        import app
        foods = [{"id": 3, "name": "Huevos", "purchased": 1}, {"id": 9, "name": "Huevo entero", "purchased": 1},
                 {"id": 4, "name": "Chocolate", "purchased": 0}]
        clean = app._dpp_v0141_sanitize_foods_list(foods)
        self.assertEqual([(f["id"], f["name"]) for f in clean], [(9, "Huevo entero"), (4, "Chocolate onzas estimado")])
        state = self.client.get("/api/state", headers=_env.AUTH).get_json()
        self.assertTrue(all(f.get("id") is not None for f in state["foods"]))

    def test_duplicate_update_and_delete_meal(self) -> None:
        mid = self.post("/api/meals", {"date": "2026-06-01", "time": "08:00", "name": "Desayuno", "items": [{"food_id": self.food_id(), "grams": 100}]}).get_json()["id"]
        copy = self.post(f"/api/meals/{mid}/duplicate", {"date": "2026-06-02"}).get_json()
        self.assertTrue(copy["ok"])
        response = self.client.put(f"/api/meals/{copy['id']}", json={"date": "2026-06-02", "time": "09:00", "name": "Desayuno", "items": [{"food_id": self.food_id(), "grams": 150}]}, headers=_env.AUTH)
        self.assertEqual(response.status_code, 200)
        with dpp_db.connect() as db:
            row = db.execute("SELECT m.date, m.time, i.grams FROM meals m JOIN meal_items i ON i.meal_id=m.id WHERE m.id=?", (copy["id"],)).fetchone()
        self.assertEqual(tuple(row), ("2026-06-02", "09:00", 150.0))
        self.assertEqual(self.client.post("/api/meals/999999/duplicate", json={}, headers=_env.AUTH).status_code, 404)

    def test_food_barcode_kept_and_delete(self) -> None:
        self.assertEqual(self.post("/api/foods", {"name": "Yogur test", "kcal": 60, "protein": 10, "barcode": "8410000000017"}).status_code, 200)
        # Saving again without barcode must not erase it.
        self.post("/api/foods", {"name": "Yogur test", "kcal": 61, "protein": 10})
        lookup = self.client.get("/api/foods/barcode/8410000000017", headers=_env.AUTH).get_json()
        self.assertEqual((lookup["found"], lookup["source"], lookup["food"]["kcal"]), (True, "local", 61.0))
        fid = lookup["food"]["id"]
        self.assertEqual(self.client.delete(f"/api/foods/{fid}", headers=_env.AUTH).status_code, 200)
        self.assertEqual(self.client.delete(f"/api/foods/{fid}", headers=_env.AUTH).status_code, 404)

    def test_profile_drives_targets(self) -> None:
        response = self.client.put("/api/profile", json={"protein_target_g": 160, "goal_weight_kg": 75, "sex": "male", "birth_year": 1990, "height_cm": 180, "kcal_mode": "auto"}, headers=_env.AUTH)
        self.assertEqual(response.status_code, 200)
        computed = response.get_json()["computed"]
        self.assertEqual(computed["protein"]["target_g"], 160)
        self.assertEqual(computed["kcal_mode_used"], "auto")
        self.assertIsNotNone(computed["bmr_kcal"])
        insights = self.client.get("/api/insights/today", headers=_env.AUTH).get_json()
        self.assertEqual(insights["targets"]["goal_weight_kg"], 75)
        self.assertEqual(insights["targets"]["protein_target_g"], 160)
        bad = self.client.put("/api/profile", json={"oil_normal_g": 20, "oil_max_g": 10}, headers=_env.AUTH)
        self.assertEqual(bad.status_code, 400)
        self.assertEqual(self.client.put("/api/profile", json={"kcal_mode": "magic"}, headers=_env.AUTH).status_code, 400)

    def test_exports_and_backup_download(self) -> None:
        self.post("/api/weights", {"date": "2026-06-01", "time": "07:30", "kg": 85.4, "official": True})
        csv = self.client.get("/api/export/weights.csv", headers=_env.AUTH)
        self.assertEqual(csv.status_code, 200)
        self.assertIn("85,4", csv.get_data(as_text=True))
        backup = self.client.get("/api/backup/download", headers=_env.AUTH)
        self.assertEqual(backup.status_code, 200)
        self.assertTrue(backup.data.startswith(b"SQLite format 3"))
        backup.close()
        self.assertEqual(self.client.get("/api/export/secrets.csv", headers=_env.AUTH).status_code, 404)

    def test_analytics_overview_and_adaptive_tdee(self) -> None:
        # 35 days eating 2000 kcal while losing 0.5 kg/week -> TDEE ≈ 2000 + 0.5*7700/7 = 2550.
        food = self.food_id("Arroz seco")  # 360 kcal / 100 g
        today = date.today()
        with dpp_db.connect() as db:
            for back in range(35, 0, -1):
                d = (today - timedelta(days=back)).isoformat()
                db.execute("INSERT INTO weights(date,time,kg,official,context) VALUES(?,?,?,?,?)", (d, "07:30", round(90 - (35 - back) * 0.5 / 7, 3), 1, ""))
                for t in ("09:00", "14:00"):
                    mid = db.execute("INSERT INTO meals(date,time,name,notes) VALUES(?,?,?,?)", (d, t, "Comida", "")).lastrowid
                    db.execute("INSERT INTO meal_items(meal_id,food_id,food_name,grams,kcal,protein) VALUES(?,?,?,?,?,?)", (mid, food, "Arroz seco", 277.8, 1000, 70))
        tdee = adaptive_tdee()
        self.assertEqual(tdee["confidence"], "alta")
        self.assertAlmostEqual(tdee["tdee"], 2550, delta=15)
        self.assertAlmostEqual(tdee["weight_slope_kg_week"], -0.5, delta=0.02)
        data = self.client.get("/api/analytics/overview?days=30", headers=_env.AUTH).get_json()
        self.assertTrue(data["ok"])
        self.assertEqual(len(data["series"]), 30)
        self.assertAlmostEqual(data["summary"]["rate_kg_week"], -0.5, delta=0.02)
        self.assertEqual(data["summary"]["protein_hit_days"], data["summary"]["complete_days"])
        self.assertTrue(data["summary"]["eta"])
        self.assertTrue(any("Gasto real" in i["title"] for i in data["insights"]))

    def test_analytics_helpers(self) -> None:
        self.assertEqual(_ema([None, 80.0, None, 81.0]), [None, 80.0, 80.0, 80.1])
        self.assertIsNone(_slope_per_day([(0, 1.0), (1, 2.0)]), "needs >= 4 points over a week")
        self.assertAlmostEqual(_slope_per_day([(0, 10.0), (3, 9.7), (6, 9.4), (9, 9.1)]), -0.1)


class UploadValidationTests(unittest.TestCase):
    def test_valid_image_upload(self) -> None:
        from PIL import Image
        buffer = io.BytesIO()
        Image.new("RGB", (40, 40), "white").save(buffer, format="PNG")
        buffer.seek(0)
        client = dpp_entrypoint.app.test_client()
        response = client.post("/api/food-photo", headers=_env.AUTH, data={"photo": (buffer, "label.png")}, content_type="multipart/form-data")
        self.assertEqual(response.status_code, 200)
        url = response.get_json()["photo_path"]
        served = client.get(url, headers=_env.AUTH)
        self.assertEqual(served.status_code, 200)
        served.close()


if __name__ == "__main__":
    unittest.main()
