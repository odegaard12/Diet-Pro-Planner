from __future__ import annotations

import json
import os
import tempfile
import time
import unittest
from pathlib import Path

import _env  # noqa: F401  (isolated data dir + auth token; must come first)
from flask import Flask

import dpp_entrypoint
import dpp_security
from dpp_strava_v018 import register_strava_v018


class ProtectedApplicationSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = dpp_entrypoint.legacy.app
        cls.app.config.update(TESTING=True)
        cls.routes = {rule.rule for rule in cls.app.url_map.iter_rules()}

    def setUp(self) -> None:
        self.client = self.app.test_client()

    @staticmethod
    def auth_headers() -> dict[str, str]:
        return {"Authorization": "Be" + "arer " + os.environ["DPP_AUTH_TOKEN"]}

    def test_required_routes_exist(self) -> None:
        for route in ("/", "/health", "/api/state", "/api/auth/login"):
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
        import dpp_config
        self.assertEqual(payload.get("version"), dpp_config.VERSION)
        self.assertTrue(str(payload.get("version") or "").startswith("v0."))

    def test_api_requires_authentication(self) -> None:
        response = self.client.get("/api/state")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.headers.get("Cache-Control"), "no-store")
        self.assertIn("Bearer", response.headers.get("WWW-Authenticate", ""))
        payload = response.get_json()
        self.assertEqual(payload.get("error"), "Autenticación requerida")

    def test_api_state_accepts_bearer_auth(self) -> None:
        response = self.client.get("/api/state", headers=self.auth_headers())
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.get_json(), dict)

    def test_login_creates_session(self) -> None:
        response = self.client.post("/api/auth/login", json={"token": "test-token", "next": "/"})
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload.get("ok"))

        state = self.client.get("/api/state")
        self.assertEqual(state.status_code, 200)
        self.assertIsInstance(state.get_json(), dict)

    def test_upload_path_traversal_is_rejected(self) -> None:
        response = self.client.get("/uploads/..%2Fapp.py", headers=self.auth_headers())
        self.assertEqual(response.status_code, 404)

    def test_local_only_write_does_not_trust_spoofed_forwarded_for(self) -> None:
        response = self.client.post(
            "/api/pantry/v2",
            headers={**self.auth_headers(), "X-Forwarded-For": "127.0.0.1"},
            json={"items": []},
            environ_overrides={"REMOTE_ADDR": "8.8.8.8"},
        )
        self.assertEqual(response.status_code, 403)
        payload = response.get_json()
        self.assertIn("red local", payload.get("error", ""))

    def test_local_only_write_allows_real_local_requests(self) -> None:
        response = self.client.post(
            "/api/pantry/v2",
            headers=self.auth_headers(),
            json={"items": []},
            environ_overrides={"REMOTE_ADDR": "127.0.0.1"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload.get("ok"))


    def test_tests_use_isolated_data_dir(self) -> None:
        import dpp_config
        self.assertEqual(Path(dpp_config.DATA_DIR), _env.DATA_DIR)
        self.assertTrue(str(dpp_config.PANTRY_PATH).startswith(str(_env.DATA_DIR)))

    def test_security_headers_on_api_and_pages(self) -> None:
        for path, headers in (("/api/state", self.auth_headers()), ("/", {})):
            with self.subTest(path=path):
                response = self.client.get(path, headers=headers)
                self.assertEqual(response.headers.get("X-Frame-Options"), "DENY")
                self.assertEqual(response.headers.get("X-Content-Type-Options"), "nosniff")
                self.assertIn("frame-ancestors 'none'", response.headers.get("Content-Security-Policy", ""))
        self.assertEqual(self.client.get("/api/state", headers=self.auth_headers()).headers.get("Cache-Control"), "no-store")

    def test_login_next_rejects_open_redirects(self) -> None:
        for candidate, expected in (("//evil.example/x", "/"), ("/\\evil.example", "/"), ("https://evil.example", "/"), ("/weight-2", "/weight-2")):
            with self.subTest(next=candidate):
                response = self.client.post("/api/auth/login", json={"token": "test-token", "next": candidate})
                self.assertEqual(response.get_json().get("next"), expected)

    def test_login_page_escapes_next_parameter(self) -> None:
        client = self.app.test_client()
        response = client.get('/?x="><script>alert(1)</script>')
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(b"<script>alert(1)</script>", response.data)

    def test_login_rate_limit_blocks_bruteforce(self) -> None:
        address = "198.51.100.7"
        dpp_security._LOGIN_FAILURES.pop(address, None)
        try:
            for _ in range(dpp_security.LOGIN_MAX_FAILURES):
                response = self.client.post("/api/auth/login", json={"token": "wrong"}, environ_overrides={"REMOTE_ADDR": address})
                self.assertEqual(response.status_code, 401)
            blocked = self.client.post("/api/auth/login", json={"token": "test-token"}, environ_overrides={"REMOTE_ADDR": address})
            self.assertEqual(blocked.status_code, 429)
            self.assertTrue(blocked.headers.get("Retry-After"))
        finally:
            dpp_security._LOGIN_FAILURES.pop(address, None)

    def test_session_cookie_flags(self) -> None:
        client = self.app.test_client()
        response = client.post("/api/auth/login", json={"token": "test-token"})
        cookie = response.headers.get("Set-Cookie", "")
        self.assertIn("dpp_session=", cookie)
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Lax", cookie)

    def test_wrong_bearer_tokens_are_rate_limited(self) -> None:
        address = "198.51.100.8"
        dpp_security._LOGIN_FAILURES.pop(address, None)
        try:
            bad = {"Authorization": "Bearer nope"}
            codes = [self.client.get("/api/state", headers=bad, environ_overrides={"REMOTE_ADDR": address}).status_code
                     for _ in range(dpp_security.LOGIN_MAX_FAILURES + 1)]
            self.assertEqual(codes[:-1], [401] * dpp_security.LOGIN_MAX_FAILURES)
            self.assertEqual(codes[-1], 429)
        finally:
            dpp_security._LOGIN_FAILURES.pop(address, None)

    def test_strava_callback_requires_pending_state(self) -> None:
        legacy = dpp_entrypoint.legacy
        os.environ.update({"STRAVA_CLIENT_ID": "1", "STRAVA_CLIENT_SECRET": "s", "STRAVA_REDIRECT_URI": "http://localhost/api/strava/callback"})
        try:
            legacy.STRAVA_STATE_FILE.unlink(missing_ok=True)
            self.assertEqual(self.client.get("/api/strava/callback?state=anything&code=x").status_code, 400)
            state = legacy.issue_strava_oauth_state()
            self.assertEqual(legacy.issue_strava_oauth_state(), state, "recent state is reused across tabs")
            self.assertFalse(legacy.consume_strava_oauth_state("wrong"))
            self.assertTrue(legacy.consume_strava_oauth_state(state))
            self.assertFalse(legacy.consume_strava_oauth_state(state), "state is single use")
            stale = legacy.issue_strava_oauth_state()
            old = time.time() - legacy.STRAVA_STATE_TTL_SECONDS - 5
            os.utime(legacy.STRAVA_STATE_FILE, (old, old))
            self.assertFalse(legacy.consume_strava_oauth_state(stale), "expired state is rejected")
        finally:
            for key in ("STRAVA_CLIENT_ID", "STRAVA_CLIENT_SECRET", "STRAVA_REDIRECT_URI"):
                os.environ.pop(key, None)

    def test_upload_rejects_non_images(self) -> None:
        import io
        response = self.client.post(
            "/api/food-photo",
            headers=self.auth_headers(),
            data={"photo": (io.BytesIO(b"not an image"), "label.jpg")},
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("imagen", response.get_json().get("error", ""))

    def test_unknown_api_route_returns_json_404(self) -> None:
        response = self.client.get("/api/does-not-exist", headers=self.auth_headers())
        self.assertEqual(response.status_code, 404)
        self.assertFalse(response.get_json().get("ok"))


class StravaConfigStorageTests(unittest.TestCase):
    def _legacy(self, root: Path):
        class LegacyStub:
            DATA = root
            STRAVA_TOKEN_FILE = root / "tokens.json"
            STRAVA_STATE_FILE = root / "state.txt"

            @staticmethod
            def strava_config() -> dict[str, str]:
                return {
                    "client_id": str(os.environ.get("STRAVA_CLIENT_ID", "")).strip(),
                    "client_secret": str(os.environ.get("STRAVA_CLIENT_SECRET", "")).strip(),
                    "redirect_uri": str(os.environ.get("STRAVA_REDIRECT_URI", "")).strip(),
                }

            @staticmethod
            def refresh_strava_if_needed(tokens):
                return tokens

            @staticmethod
            def _epoch_from_date(_value, _end=False) -> int:
                return 0

            @staticmethod
            def _strava_card(item):
                return {"id": item.get("id")}

            @staticmethod
            def read_strava_tokens():
                return {}

            @staticmethod
            def read_strava_auto_config():
                return {}

            @staticmethod
            def write_strava_tokens(_tokens) -> None:
                return None

            @staticmethod
            def strava_configured() -> bool:
                return True

        return LegacyStub()

    def test_legacy_client_secret_is_removed_from_disk(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_file = root / "integrations.json"
            config_file.write_text(json.dumps({
                "strava": {
                    "client_id": "12345",
                    "client_secret": "legacy-secret-123456",
                    "redirect_uri": "http://localhost:8099/api/strava/callback",
                }
            }), encoding="utf-8")
            app = Flask(__name__)
            app.config.update(TESTING=True)
            os.environ["STRAVA_CLIENT_SECRET"] = "env-secret-123456"
            register_strava_v018(app, self._legacy(root))

            client = app.test_client()
            response = client.get(
                "/api/integrations/strava/config",
                environ_overrides={"REMOTE_ADDR": "127.0.0.1"},
            )
            self.assertEqual(response.status_code, 200)

            stored = json.loads(config_file.read_text(encoding="utf-8"))
            self.assertNotIn("client_secret", stored.get("strava", {}))

    def test_strava_config_rejects_client_secret_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            app = Flask(__name__)
            app.config.update(TESTING=True)
            os.environ["STRAVA_CLIENT_SECRET"] = "env-secret-123456"
            register_strava_v018(app, self._legacy(root))

            client = app.test_client()
            response = client.post(
                "/api/integrations/strava/config",
                json={
                    "client_id": "12345",
                    "client_secret": "plaintext-secret-123456",
                    "redirect_uri": "http://localhost:8099/api/strava/callback",
                },
                environ_overrides={"REMOTE_ADDR": "127.0.0.1"},
            )
            self.assertEqual(response.status_code, 400)
            payload = response.get_json()
            self.assertIn("ya no se guarda en disco", payload.get("error", ""))

    def test_strava_config_persists_only_public_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_file = root / "integrations.json"
            app = Flask(__name__)
            app.config.update(TESTING=True)
            os.environ["STRAVA_CLIENT_SECRET"] = "env-secret-123456"
            register_strava_v018(app, self._legacy(root))

            client = app.test_client()
            response = client.post(
                "/api/integrations/strava/config",
                json={
                    "client_id": "12345",
                    "redirect_uri": "http://localhost:8099/api/strava/callback",
                },
                environ_overrides={"REMOTE_ADDR": "127.0.0.1"},
            )
            self.assertEqual(response.status_code, 200)
            stored = json.loads(config_file.read_text(encoding="utf-8"))
            self.assertEqual(stored.get("strava", {}).get("client_id"), "12345")
            self.assertEqual(
                stored.get("strava", {}).get("redirect_uri"),
                "http://localhost:8099/api/strava/callback",
            )
            self.assertNotIn("client_secret", stored.get("strava", {}))


if __name__ == "__main__":
    unittest.main()
