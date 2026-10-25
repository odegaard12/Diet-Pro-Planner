"""Data review: each kind of problem is found, a clean database stays quiet and nothing is modified."""
from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

import _env  # noqa: F401  (isolated data dir + auth token; must come first)

import dpp_config
import dpp_data_audit
import dpp_db

NOW = datetime(2026, 10, 25, 12, 0)
TODAY = "2026-10-25"


def _fresh_db(tmp: Path) -> Path:
    path = tmp / "dieta.db"
    with dpp_db.connect(path) as db:
        db.executescript(
            """
            CREATE TABLE foods(id INTEGER PRIMARY KEY, name TEXT UNIQUE, kcal REAL, protein REAL, carbs REAL, fat REAL);
            CREATE TABLE meals(id INTEGER PRIMARY KEY, date TEXT, time TEXT, name TEXT, notes TEXT);
            CREATE TABLE meal_items(id INTEGER PRIMARY KEY, meal_id INTEGER, food_id INTEGER, food_name TEXT, grams REAL, kcal REAL);
            CREATE TABLE weights(id INTEGER PRIMARY KEY, date TEXT, time TEXT, kg REAL, official INTEGER);
            CREATE TABLE workouts(id INTEGER PRIMARY KEY, date TEXT, time TEXT, name TEXT, minutes REAL, kcal REAL);
            CREATE TABLE templates(id INTEGER PRIMARY KEY, name TEXT, payload TEXT);
            INSERT INTO foods(name, kcal, protein, carbs, fat) VALUES('Arroz', 360, 7, 79, 1);
            """
        )
        db.commit()
    return path


def _audit(path: Path, backups: list[dict] | None = None) -> dict:
    real = dpp_db.connect
    fresh = backups if backups is not None else [{"name": "dieta-x.db", "created_at": "2026-10-25T03:00:00"}]
    with mock.patch.object(dpp_db, "connect", lambda p=None: real(path)), mock.patch.object(dpp_db, "list_backups", lambda d=None: fresh):
        return dpp_data_audit.run_audit(today=TODAY, now=NOW)


class DataAuditTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.path = _fresh_db(Path(self._tmp.name))

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def ids(self, report: dict) -> set[str]:
        return {f["id"] for f in report["findings"]}

    def test_clean_database_has_no_findings(self) -> None:
        report = _audit(self.path)
        self.assertEqual(report["findings"], [])
        self.assertEqual(report["summary"], {"error": 0, "warn": 0, "info": 0})

    def test_detects_each_kind_of_problem(self) -> None:
        with dpp_db.connect(self.path) as db:
            db.execute("INSERT INTO foods(name, kcal, protein, carbs, fat) VALUES('Imposible', 500, 60, 50, 10)")  # 120 g per 100 g
            db.execute("INSERT INTO foods(name, kcal, protein, carbs, fat) VALUES('Kcal mal', 900, 10, 10, 1)")
            db.execute("INSERT INTO meals(id, date, time, name) VALUES(1, '2026-10-20', '14:00', 'Comida'), (2, '2026-10-20', '14:00', 'Comida'), (3, '2026-11-30', '10:00', 'Cena')")
            db.execute("INSERT INTO meal_items(meal_id, food_id, food_name, grams, kcal) VALUES(1, NULL, 'Borrado', 100, 100), (2, 1, 'Arroz', 5000, 7000)")
            db.execute("INSERT INTO weights(date, time, kg, official) VALUES('2026-10-01', '08:00', 87.5, 1), ('2026-10-02', '08:00', 77.5, 1), ('2026-10-03', '08:00', 87.0, 1), ('2026-10-04', '08:00', 80.0, 1), ('2026-10-05', '08:00', 5, 0)")
            db.execute("INSERT INTO workouts(date, time, name, minutes, kcal) VALUES('2026-10-10', '18:00', 'Correr', 900, 9000)")
            db.execute("INSERT INTO templates(name, payload) VALUES('Rota', ?), ('Rota 2', 'no es json')", (json.dumps({"items": [{"food": "Fantasma", "grams": 50}]}),))
            db.commit()
        report = _audit(self.path, backups=[])
        self.assertEqual(self.ids(report), {
            "foods_over_100g", "foods_kcal_mismatch", "items_food_deleted", "items_huge_grams", "days_over_6000",
            "meals_duplicated", "meals_future", "weights_spike", "weights_jump", "weights_range", "workouts_extreme",
            "templates_missing_foods", "backup_none",
        })
        levels = [f["level"] for f in report["findings"]]
        self.assertEqual(levels, sorted(levels, key=("error", "warn", "info").index))  # errors first
        self.assertGreaterEqual(report["summary"]["error"], 2)

    def test_one_typo_is_a_single_spike_not_two_jumps(self) -> None:
        with dpp_db.connect(self.path) as db:
            db.execute("INSERT INTO weights(date, time, kg, official) VALUES('2026-10-01', '08:00', 87.5, 1), ('2026-10-02', '08:00', 77.5, 1), ('2026-10-03', '08:00', 87.0, 1)")
            db.commit()
        report = _audit(self.path)
        self.assertEqual(self.ids(report), {"weights_spike"})
        self.assertEqual(report["findings"][0]["count"], 1)

    def test_old_backup_is_reported_and_recent_is_not(self) -> None:
        old = _audit(self.path, backups=[{"name": "dieta-a.db", "created_at": "2026-10-10T03:00:00"}])
        self.assertIn("backup_old", self.ids(old))
        self.assertNotIn("backup_old", self.ids(_audit(self.path)))

    def test_examples_are_capped_and_data_is_not_modified(self) -> None:
        with dpp_db.connect(self.path) as db:
            for n in range(12):
                db.execute("INSERT INTO foods(name, kcal, protein, carbs, fat) VALUES(?, 100, 70, 70, 0)", (f"Malo {n}",))
            db.commit()
        before = self.path.read_bytes()
        report = _audit(self.path)
        finding = next(f for f in report["findings"] if f["id"] == "foods_over_100g")
        self.assertEqual(finding["count"], 12)
        self.assertEqual(len(finding["items"]), dpp_data_audit.MAX_ITEMS)
        self.assertEqual(self.path.read_bytes(), before)


class DataAuditEndpointTests(unittest.TestCase):
    def test_endpoint_requires_login_and_returns_a_report(self) -> None:
        import dpp_entrypoint

        client = dpp_entrypoint.legacy.app.test_client()
        self.assertEqual(client.get("/api/data-audit").status_code, 401)
        response = client.get("/api/data-audit", headers=_env.AUTH)
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertTrue(body["ok"])
        self.assertEqual(set(body["summary"]), {"error", "warn", "info"})
        self.assertTrue(str(dpp_config.DB_PATH))


if __name__ == "__main__":
    unittest.main()
