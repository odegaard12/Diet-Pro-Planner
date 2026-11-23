"""Strava duplicate detection compares ids exactly, never by substring."""

from __future__ import annotations

import unittest

import _env  # noqa: F401
import dpp_db
import dpp_strava_v018 as sv
from test_api_core import reset_user_data


class StravaDedupTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_user_data()

    def add(self, db, notes: str, source: str | None = None, external_id: str = "") -> int:
        cur = db.execute("INSERT INTO workouts(date,time,name,minutes,notes) VALUES('2026-06-01','07:00','Run',30,?)", (notes,))
        if source:
            db.execute("UPDATE workouts SET source=?, external_id=? WHERE id=?", (source, external_id, cur.lastrowid))
        return cur.lastrowid

    def test_note_id_parsing(self) -> None:
        self.assertEqual(sv.note_strava_ids("Strava · x · id=1000001 · kcal"), ["1000001"])
        self.assertEqual(sv.note_strava_ids("valid=1000001 pid=2"), [])
        self.assertEqual(sv.note_strava_ids("id=1000001abc"), ["1000001"])

    def test_prefix_id_does_not_match_longer_id(self) -> None:
        with dpp_db.connect() as db:
            self.add(db, "Strava · A · id=10000012 · kcal")
            self.assertIsNone(sv.find_workout_by_strava_id(db, "1000001", indexed=False))
            self.assertIsNone(sv.find_workout_by_strava_id(db, "1000001", indexed=True))

    def test_manual_note_with_similar_text_is_not_matched(self) -> None:
        with dpp_db.connect() as db:
            self.add(db, "carrera valid=1000001 con amigos")
            self.assertIsNone(sv.find_workout_by_strava_id(db, "1000001", indexed=True))

    def test_exact_legacy_note_id_matches(self) -> None:
        with dpp_db.connect() as db:
            self.add(db, "Strava · A · id=10000012 · kcal")
            want = self.add(db, "Strava · B · id=1000001 · kcal")
            self.assertEqual(sv.find_workout_by_strava_id(db, "1000001", indexed=False)["id"], want)

    def test_external_id_preferred_when_indexed(self) -> None:
        with dpp_db.connect() as db:
            want = self.add(db, "renamed by user", source="strava", external_id="1000001")
            self.assertEqual(sv.find_workout_by_strava_id(db, "1000001", indexed=True)["id"], want)


if __name__ == "__main__":
    unittest.main()
