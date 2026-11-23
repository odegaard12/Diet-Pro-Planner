"""MET/kcal estimates for workouts and Strava-style activities."""

from __future__ import annotations

import unittest

import _env
import dpp_db
import dpp_entrypoint
import dpp_profile
from test_api_core import reset_user_data


class KcalEstimateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = dpp_entrypoint.app
        cls.app.config.update(TESTING=True)
        cls.legacy = dpp_entrypoint.legacy

    def test_met_formula(self) -> None:
        # kcal = MET * 3.5 * kg / 200 * minutes
        self.assertEqual(dpp_profile.estimate_met_kcal(8, 30, 80), round(8 * 3.5 * 80 / 200 * 30))
        self.assertEqual(dpp_profile.estimate_met_kcal(8, 30, 80), 336)
        self.assertEqual(dpp_profile.estimate_met_kcal(5, 0, 80), 0)

    def test_met_uses_current_weight_by_default(self) -> None:
        self.assertEqual(
            dpp_profile.estimate_met_kcal(6, 45),
            dpp_profile.estimate_met_kcal(6, 45, dpp_profile.current_weight()),
        )

    def test_known_sport_uses_its_met(self) -> None:
        weight = dpp_profile.current_weight()
        self.assertEqual(self.legacy.estimate_strava_kcal("Run", 60), dpp_profile.estimate_met_kcal(8.5, 60, weight))
        self.assertEqual(self.legacy.estimate_strava_kcal("Walk", 60), dpp_profile.estimate_met_kcal(3.5, 60, weight))

    def test_unknown_sport_falls_back_to_default_met(self) -> None:
        weight = dpp_profile.current_weight()
        self.assertEqual(self.legacy.estimate_strava_kcal("Curling", 60), dpp_profile.estimate_met_kcal(5.5, 60, weight))

    def test_trailrun_current_behaviour(self) -> None:
        # Current behaviour, not necessarily desirable: "TrailRun" is not in the MET table, so it gets the
        # generic 5.5 MET instead of the 8.5 of "Run". In practice the Strava card passes the coarse `type`
        # ("Run"), so only callers that pass `sport_type` directly hit this fallback.
        weight = dpp_profile.current_weight()
        self.assertEqual(self.legacy.estimate_strava_kcal("TrailRun", 60), dpp_profile.estimate_met_kcal(5.5, 60, weight))
        card = self.legacy._strava_card({"id": 1000001, "type": "Run", "sport_type": "TrailRun", "moving_time": 3600, "start_date_local": "2026-06-01T08:00:00Z"})
        self.assertEqual(card["kcal"], float(dpp_profile.estimate_met_kcal(8.5, 60, weight)))

    def test_workout_without_kcal_uses_exercise_met(self) -> None:
        reset_user_data()
        client = self.app.test_client()
        with dpp_db.connect() as db:
            db.execute("INSERT OR REPLACE INTO exercises(name,met) VALUES('Test MET',7)")
        got = client.post("/api/workouts", json={"name": "Test MET", "minutes": 30, "date": "2026-06-01", "time": "07:00"}, headers=_env.AUTH).get_json()
        self.assertEqual(got["kcal"], dpp_profile.estimate_met_kcal(7, 30, dpp_profile.current_weight()))


if __name__ == "__main__":
    unittest.main()
