from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import _env  # noqa: F401
import dpp_db

LEGACY_SCHEMA = """
CREATE TABLE foods(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE, brand TEXT DEFAULT '',
  kcal REAL NOT NULL DEFAULT 0, protein REAL NOT NULL DEFAULT 0, carbs REAL NOT NULL DEFAULT 0, fat REAL NOT NULL DEFAULT 0,
  sugar REAL NOT NULL DEFAULT 0, salt REAL NOT NULL DEFAULT 0, typical_g REAL NOT NULL DEFAULT 100,
  purchased INTEGER NOT NULL DEFAULT 0, source_note TEXT DEFAULT '', notes TEXT DEFAULT '', photo_path TEXT DEFAULT '',
  created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE weights(id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT NOT NULL, time TEXT NOT NULL, kg REAL NOT NULL,
  official INTEGER NOT NULL DEFAULT 0, context TEXT DEFAULT '', UNIQUE(date,time,kg,context));
CREATE TABLE meals(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          date TEXT NOT NULL,
          time TEXT NOT NULL,
          name TEXT NOT NULL,
          notes TEXT DEFAULT '',
          UNIQUE(date,time,name,notes)
        );
CREATE TABLE meal_items(id INTEGER PRIMARY KEY AUTOINCREMENT, meal_id INTEGER NOT NULL REFERENCES meals(id) ON DELETE CASCADE,
  food_id INTEGER REFERENCES foods(id) ON DELETE SET NULL, food_name TEXT NOT NULL, grams REAL NOT NULL,
  kcal REAL NOT NULL DEFAULT 0, protein REAL NOT NULL DEFAULT 0, carbs REAL NOT NULL DEFAULT 0, fat REAL NOT NULL DEFAULT 0,
  sugar REAL NOT NULL DEFAULT 0, salt REAL NOT NULL DEFAULT 0);
CREATE TABLE workouts(id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT NOT NULL, time TEXT NOT NULL, exercise_id INTEGER,
  name TEXT NOT NULL, minutes REAL NOT NULL DEFAULT 0, distance_km REAL NOT NULL DEFAULT 0, kcal REAL NOT NULL DEFAULT 0,
  notes TEXT DEFAULT '', UNIQUE(date,time,name,minutes,notes));
"""


def build_legacy_db(path: Path) -> None:
    db = sqlite3.connect(path)
    db.executescript(LEGACY_SCHEMA)
    db.execute("INSERT INTO foods(id,name,kcal,protein,carbs,fat) VALUES(1,'Pollo',110,23,0,1.6)")
    db.execute("INSERT INTO foods(id,name,kcal,protein,carbs,fat) VALUES(2,'Arroz seco',360,7,78,0.8)")
    db.execute("INSERT INTO meals(id,date,time,name,notes) VALUES(7,'2026-06-01','14:00','Comida','')")
    db.execute("INSERT INTO meal_items(meal_id,food_id,food_name,grams,kcal,protein) VALUES(7,1,'Pollo',200,220,46)")
    # Imported by a local script: grams only, no macros (and no food_id).
    db.execute("INSERT INTO meal_items(meal_id,food_id,food_name,grams) VALUES(7,NULL,'Arroz seco',80)")
    db.execute("INSERT INTO workouts(date,time,name,minutes,kcal,notes) VALUES('2026-06-01','19:00','Run',40,450,'Strava · Rodaje · id=123456 · kcal desde detalle Strava')")
    db.execute("INSERT INTO workouts(date,time,name,minutes,kcal,notes) VALUES('2026-06-02','19:00','HIIT',30,300,'manual id=9')")
    db.execute("INSERT INTO weights(date,time,kg,official) VALUES('2026-06-01','07:30',86.2,1)")
    db.commit()
    db.close()


class MigrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.db_path = self.root / "dieta.db"
        build_legacy_db(self.db_path)
        self._backups = dpp_db.config.BACKUPS_DIR
        dpp_db.config.BACKUPS_DIR = self.root / "backups"

    def tearDown(self) -> None:
        dpp_db.config.BACKUPS_DIR = self._backups
        self.tmp.cleanup()

    def test_full_migration_preserves_data_and_backs_up(self) -> None:
        applied = dpp_db.migrate(self.db_path)
        self.assertEqual(applied, [m[0] for m in dpp_db.MIGRATIONS])
        self.assertEqual(dpp_db.user_version(self.db_path), dpp_db.SCHEMA_VERSION)
        backups = list((self.root / "backups").glob("dieta-*-pre-migration-v0-to-v*.db"))
        self.assertEqual(len(backups), 1, "an existing database is snapshotted before migrating")
        with dpp_db.connect(backups[0]) as snap:
            self.assertEqual(snap.execute("SELECT COUNT(*) FROM meal_items").fetchone()[0], 2)

        with dpp_db.connect(self.db_path) as db:
            # Items survived the meals table rebuild (no cascade on DROP TABLE).
            self.assertEqual(db.execute("SELECT COUNT(*) FROM meal_items WHERE meal_id=7").fetchone()[0], 2)
            sql = db.execute("SELECT sql FROM sqlite_master WHERE name='meals'").fetchone()[0]
            self.assertNotIn("UNIQUE", sql.upper())
            # Two identical meals at the same minute are now both stored.
            db.execute("INSERT INTO meals(date,time,name,notes) VALUES('2026-06-01','14:00','Comida','')")
            self.assertEqual(db.execute("SELECT COUNT(*) FROM meals WHERE date='2026-06-01'").fetchone()[0], 2)
            # Strava id backfilled only for Strava rows.
            rows = dict(db.execute("SELECT name, external_id FROM workouts").fetchall())
            self.assertEqual(rows, {"Run": "123456", "HIIT": ""})
            # Zero-macro item repaired from the catalog by name.
            rice = db.execute("SELECT kcal, protein, carbs FROM meal_items WHERE food_name='Arroz seco'").fetchone()
            self.assertEqual(tuple(rice), (288.0, 5.6, 62.4))
            self.assertIn("barcode", [r[1] for r in db.execute("PRAGMA table_info(foods)")])
            self.assertIsNotNone(db.execute("SELECT 1 FROM sqlite_master WHERE name='app_settings'").fetchone())
            # Foreign keys still cascade after the rebuild.
            db.execute("DELETE FROM meals WHERE id=7")
            self.assertEqual(db.execute("SELECT COUNT(*) FROM meal_items WHERE meal_id=7").fetchone()[0], 0)

    def test_dangling_food_reference_does_not_block_upgrade(self) -> None:
        # Old cleanup scripts deleted foods with foreign keys off, leaving orphan food_id values.
        db = sqlite3.connect(self.db_path)
        db.execute("INSERT INTO foods(id,name,kcal,protein) VALUES(3,'Huevos',155,13)")
        db.execute("INSERT INTO meal_items(meal_id,food_id,food_name,grams,kcal,protein) VALUES(7,3,'Huevo entero',120,186,15.6)")
        db.execute("DELETE FROM foods WHERE id=3")
        db.commit()
        db.close()
        dpp_db.migrate(self.db_path)
        with dpp_db.connect(self.db_path) as conn:
            row = conn.execute("SELECT food_id, grams, kcal FROM meal_items WHERE food_name='Huevo entero'").fetchone()
            self.assertEqual(tuple(row), (None, 120.0, 186.0), "orphan reference nulled, item data kept")
            self.assertEqual(conn.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_failed_migration_does_not_snapshot_on_every_retry(self) -> None:
        def boom(_db):
            raise RuntimeError("simulated failure")
        broken = dpp_db.MIGRATIONS + [(99, "boom", boom)]
        counts = []
        with mock.patch.object(dpp_db, "MIGRATIONS", broken):
            for _ in range(4):
                with self.assertRaises(RuntimeError):
                    dpp_db.migrate(self.db_path)
                counts.append(len(list((self.root / "backups").glob("*.db"))))
        # One copy per distinct version jump (v0->v99, then v5->v99); retries add nothing.
        self.assertEqual(counts, [1, 2, 2, 2])
        self.assertEqual(dpp_db.user_version(self.db_path), dpp_db.SCHEMA_VERSION, "earlier migrations stay applied")

    def test_meals_rebuild_keeps_views_triggers_and_sequence(self) -> None:
        db = sqlite3.connect(self.db_path)
        db.execute("INSERT INTO meals(id,date,time,name,notes) VALUES(50,'2026-06-03','10:00','Snack','')")
        db.execute("DELETE FROM meals WHERE id=50")
        db.execute("CREATE VIEW v_meals AS SELECT id, date FROM meals")
        db.execute("CREATE TABLE audit(meal_id INTEGER)")
        db.execute("CREATE TRIGGER trg_meals AFTER INSERT ON meals BEGIN INSERT INTO audit(meal_id) VALUES(new.id); END")
        db.commit()
        db.close()
        dpp_db.migrate(self.db_path)
        with dpp_db.connect(self.db_path) as conn:
            new_id = conn.execute("INSERT INTO meals(date,time,name,notes) VALUES('2026-06-04','10:00','Snack','')").lastrowid
            self.assertGreater(new_id, 50, "ids of deleted meals are not reused")
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM audit").fetchone()[0], 1, "trigger recreated")
            self.assertGreaterEqual(conn.execute("SELECT COUNT(*) FROM v_meals").fetchone()[0], 2, "view recreated")

    def test_migrate_is_idempotent(self) -> None:
        dpp_db.migrate(self.db_path)
        self.assertEqual(dpp_db.migrate(self.db_path), [])
        self.assertEqual(len(list((self.root / "backups").glob("*.db"))), 1)

    def test_fresh_database_is_not_backed_up(self) -> None:
        empty = self.root / "fresh.db"
        sqlite3.connect(empty).close()
        dpp_db.migrate(empty)
        self.assertEqual(dpp_db.user_version(empty), dpp_db.SCHEMA_VERSION)
        self.assertFalse(list((self.root / "backups").glob("*.db")))

    def test_connect_closes_on_context_exit(self) -> None:
        with dpp_db.connect(self.db_path) as db:
            db.execute("SELECT 1")
        with self.assertRaises(sqlite3.ProgrammingError):
            db.execute("SELECT 1")

    def test_daily_backup_rotation(self) -> None:
        folder = self.root / "backups"
        folder.mkdir()
        for day in range(1, 20):
            (folder / f"dieta-202601{day:02d}-000000-daily.db").write_bytes(b"x")
        (folder / "dieta-20260101-000000-manual.db").write_bytes(b"x")
        removed = dpp_db.prune_daily_backups(keep=14, dest_dir=folder)
        self.assertEqual(removed, 5)
        self.assertTrue((folder / "dieta-20260101-000000-manual.db").exists(), "manual copies are never pruned")
        self.assertEqual(len(list(folder.glob("*-daily.db"))), 14)


if __name__ == "__main__":
    unittest.main()


class GenericCatalogTests(unittest.TestCase):
    def test_adds_missing_and_keeps_user_foods(self) -> None:
        import sqlite3
        import dpp_catalog
        db = sqlite3.connect(":memory:")
        db.execute("CREATE TABLE foods(id INTEGER PRIMARY KEY, name TEXT, brand TEXT, kcal REAL, protein REAL, carbs REAL, fat REAL, sugar REAL, salt REAL, typical_g REAL, purchased INTEGER, source_note TEXT, notes TEXT)")
        db.execute("INSERT INTO foods(name, brand, kcal, protein) VALUES('Salmón', 'Mío', 999, 1)")
        added = dpp_catalog.add_missing(db)
        self.assertEqual(added, len(dpp_catalog.GENERIC_FOODS) - 1)
        self.assertEqual(db.execute("SELECT kcal, brand FROM foods WHERE name='Salmón'").fetchone(), (999, "Mío"))
        self.assertEqual(dpp_catalog.add_missing(db), 0)