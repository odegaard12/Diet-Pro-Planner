from __future__ import annotations

import unittest

import dpp_entrypoint


class PublicApplicationSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = dpp_entrypoint.legacy.app
        cls.app.config.update(TESTING=True)
        cls.client = cls.app.test_client()
        cls.routes = {rule.rule for rule in cls.app.url_map.iter_rules()}

    def test_required_public_routes_exist(self) -> None:
        for route in ("/", "/health", "/api/state"):
            with self.subTest(route=route):
                self.assertIn(route, self.routes)

    def test_index_loads(self) -> None:
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Diet Pro Planner", response.data)

    def test_health_is_json_and_ok(self) -> None:
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIsInstance(payload, dict)
        self.assertTrue(payload.get("ok"))
        self.assertEqual(payload.get("app"), "Diet Pro Planner")
        self.assertTrue(str(payload.get("version") or "").startswith("v0.0."))

    def test_state_returns_json(self) -> None:
        response = self.client.get("/api/state")
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.get_json(), dict)

    def test_pantry_v2_when_registered(self) -> None:
        if "/api/pantry/v2" not in self.routes:
            self.skipTest("Pantry v2 is not present in this branch")
        response = self.client.get("/api/pantry/v2")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload.get("ok"))
        self.assertIn("stats", payload)

    def test_activity_plan_when_registered(self) -> None:
        if "/api/activity-plan" not in self.routes:
            self.skipTest("Activity plan is not present in this branch")
        response = self.client.get(
            "/api/activity-plan?from=2026-06-15&to=2026-06-21"
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload.get("ok"))
        self.assertIn("summary", payload)


if __name__ == "__main__":
    unittest.main()
