"""Login, sessions, CSRF, headers and injection hardening (v0.2.0)."""

from __future__ import annotations

import io
import os
import sqlite3
import sys
import unittest
from unittest import mock

import _env  # noqa: F401  (isolated data dir + auth token; must come first)

import dpp_config
import dpp_entrypoint
import dpp_security
from dpp_validate import ApiError, public_error

ORIGIN = {"Origin": "http://localhost"}
TEST_PASSWORD = "correct horse battery staple"
_HASH = dpp_security.hash_password(TEST_PASSWORD)


class _Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = dpp_entrypoint.legacy.app
        cls.app.config.update(TESTING=True)

    def setUp(self) -> None:
        dpp_security._LOGIN_FAILURES.clear()
        self.client = self.app.test_client()

    def tearDown(self) -> None:
        dpp_security._LOGIN_FAILURES.clear()

    def login_token(self, client=None):
        return (client or self.client).post("/api/auth/login", json={"token": os.environ["DPP_AUTH_TOKEN"]}, headers=ORIGIN)

    def cookie(self, client=None) -> str:
        found = (client or self.client).get_cookie("dpp_session")
        return found.value if found else ""


class PasswordHashingTests(unittest.TestCase):
    def test_roundtrip_and_format(self) -> None:
        self.assertTrue(_HASH.startswith("scrypt:"))
        self.assertNotIn("$", _HASH, "must be safe inside docker-compose .env files")
        self.assertTrue(dpp_security.verify_password(TEST_PASSWORD, _HASH))
        self.assertFalse(dpp_security.verify_password(TEST_PASSWORD + "x", _HASH))
        self.assertFalse(dpp_security.verify_password("", _HASH))

    def test_salted(self) -> None:
        self.assertNotEqual(dpp_security.hash_password("same-password-1"), dpp_security.hash_password("same-password-1"))

    def test_malformed_hashes_never_verify(self) -> None:
        for bad in ("", "plain", "scrypt:1:8:1:AAAA:BBBB", "scrypt:32768:8:1::", "md5:abc", _HASH[:-4]):
            with self.subTest(bad=bad):
                self.assertFalse(dpp_security.verify_password(TEST_PASSWORD, bad))
                if bad != _HASH[:-4]:
                    self.assertFalse(dpp_security.password_hash_is_valid(bad))

    def test_werkzeug_hash_is_accepted(self) -> None:
        from werkzeug.security import generate_password_hash

        stored = generate_password_hash("another-password", method="pbkdf2:sha256:600000")
        self.assertTrue(dpp_security.password_hash_is_valid(stored))
        self.assertTrue(dpp_security.verify_password("another-password", stored))
        self.assertFalse(dpp_security.verify_password("wrong", stored))

    def test_cli_hash_password_from_stdin(self) -> None:
        with mock.patch.object(sys, "stdin", io.StringIO(TEST_PASSWORD + "\n")), \
                mock.patch("sys.stdout", new_callable=io.StringIO) as out:
            self.assertEqual(dpp_security._cli(["hash-password", "--stdin"]), 0)
        self.assertTrue(dpp_security.verify_password(TEST_PASSWORD, out.getvalue().strip()))


class PasswordLoginTests(_Base):
    def setUp(self) -> None:
        super().setUp()
        patcher = mock.patch.dict(os.environ, {"DPP_ADMIN_USER": "admin", "DPP_ADMIN_PASSWORD_HASH": _HASH})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_status_reports_password_mode(self) -> None:
        payload = self.client.get("/api/auth/status").get_json()
        self.assertEqual(payload["mode"], "password")
        self.assertFalse(payload["authenticated"])

    def test_login_page_asks_for_user_and_password(self) -> None:
        body = self.client.get("/").get_data(as_text=True)
        self.assertIn('id="username"', body)
        self.assertIn('id="password"', body)

    def test_login_success_creates_working_session(self) -> None:
        response = self.client.post("/api/auth/login", json={"username": "admin", "password": TEST_PASSWORD}, headers=ORIGIN)
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(self.client.get("/api/state").status_code, 200)
        self.assertTrue(self.client.get("/api/auth/status").get_json()["authenticated"])

    def test_wrong_password_or_user_is_rejected(self) -> None:
        for body in ({"username": "admin", "password": "nope"}, {"username": "root", "password": TEST_PASSWORD},
                     {"username": "admin"}, {}):
            with self.subTest(body=body):
                response = self.client.post("/api/auth/login", json=body, headers=ORIGIN)
                self.assertEqual(response.status_code, 401)
                self.assertNotIn("dpp_session=", response.headers.get("Set-Cookie", "").replace("dpp_session=;", ""))
        self.assertEqual(self.client.get("/api/state").status_code, 401)

    def test_token_is_not_accepted_in_the_form_in_password_mode(self) -> None:
        self.assertEqual(self.login_token().status_code, 401)

    def test_bearer_token_keeps_working_for_automation(self) -> None:
        self.assertEqual(self.client.get("/api/state", headers=_env.AUTH).status_code, 200)

    def test_password_login_is_rate_limited(self) -> None:
        for _ in range(dpp_security.LOGIN_MAX_FAILURES):
            self.client.post("/api/auth/login", json={"username": "admin", "password": "x"}, headers=ORIGIN)
        blocked = self.client.post("/api/auth/login", json={"username": "admin", "password": TEST_PASSWORD}, headers=ORIGIN)
        self.assertEqual(blocked.status_code, 429)
        self.assertTrue(blocked.headers.get("Retry-After"))

    def test_changing_the_password_invalidates_sessions(self) -> None:
        self.client.post("/api/auth/login", json={"username": "admin", "password": TEST_PASSWORD}, headers=ORIGIN)
        self.assertEqual(self.client.get("/api/state").status_code, 200)
        with mock.patch.dict(os.environ, {"DPP_ADMIN_PASSWORD_HASH": dpp_security.hash_password("a-new-password")}):
            self.assertEqual(self.client.get("/api/state").status_code, 401)

    def test_invalid_hash_falls_back_to_token_login(self) -> None:
        with mock.patch.dict(os.environ, {"DPP_ADMIN_PASSWORD_HASH": "not-a-hash"}):
            self.assertEqual(dpp_security.login_mode(), "token")
            self.assertEqual(self.login_token().status_code, 200)


class SessionLifecycleTests(_Base):
    def test_logout_really_invalidates_the_cookie(self) -> None:
        self.assertEqual(self.login_token().status_code, 200)
        stolen = self.cookie()
        self.assertTrue(stolen)
        self.assertEqual(self.client.post("/api/auth/logout", headers=ORIGIN).status_code, 200)
        replay = self.app.test_client()
        replay.set_cookie("dpp_session", stolen)
        self.assertEqual(replay.get("/api/state").status_code, 401, "a copied cookie must die with logout")

    def test_login_rotates_the_session_id(self) -> None:
        self.login_token()
        first = self.cookie()
        self.login_token()
        second = self.cookie()
        self.assertNotEqual(first, second)
        old = self.app.test_client()
        old.set_cookie("dpp_session", first)
        self.assertEqual(old.get("/api/state").status_code, 401)
        self.assertEqual(self.client.get("/api/state").status_code, 200)

    def test_sessions_are_stored_hashed_server_side(self) -> None:
        self.login_token()
        with sqlite3.connect(str(dpp_config.DATA_DIR / "auth_sessions.db")) as db:
            hashes = [row[0] for row in db.execute("SELECT id_hash FROM sessions")]
        self.assertTrue(hashes)
        self.assertTrue(all(len(h) == 64 for h in hashes))

    def test_expired_session_is_rejected(self) -> None:
        self.login_token()
        with sqlite3.connect(str(dpp_config.DATA_DIR / "auth_sessions.db")) as db:
            db.execute("UPDATE sessions SET expires_at = 0")
        self.assertEqual(self.client.get("/api/state").status_code, 401)

    def test_token_rotation_invalidates_sessions(self) -> None:
        self.login_token()
        with mock.patch.dict(os.environ, {"DPP_AUTH_TOKEN": "rotated-token"}):
            self.assertEqual(self.client.get("/api/state").status_code, 401)

    def test_forged_cookie_is_rejected(self) -> None:
        client = self.app.test_client()
        client.set_cookie("dpp_session", "eyJkcHBfYXV0aGVudGljYXRlZCI6dHJ1ZX0.forged.sig")
        self.assertEqual(client.get("/api/state").status_code, 401)

    def test_secret_key_is_persisted_privately(self) -> None:
        path = dpp_config.DATA_DIR / ".session_secret"
        self.assertTrue(path.exists())
        self.assertGreaterEqual(len(path.read_text(encoding="utf-8").strip()), 32)
        if os.name == "posix":
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_debug_is_forced_off(self) -> None:
        self.assertFalse(self.app.debug)


class CsrfTests(_Base):
    def setUp(self) -> None:
        super().setUp()
        self.assertEqual(self.login_token().status_code, 200)

    def post_weight(self, **kwargs):
        return self.client.post("/api/weights", **kwargs)

    def test_same_origin_json_write_is_allowed(self) -> None:
        response = self.post_weight(json={"kg": 70, "date": "2020-01-01", "time": "07:00"}, headers=ORIGIN)
        self.assertEqual(response.status_code, 200)

    def test_write_without_origin_is_rejected(self) -> None:
        self.assertEqual(self.post_weight(json={"kg": 70}).status_code, 403)

    def test_cross_site_origin_is_rejected(self) -> None:
        self.assertEqual(self.post_weight(json={"kg": 70}, headers={"Origin": "http://evil.example"}).status_code, 403)

    def test_other_port_on_same_host_is_rejected(self) -> None:
        self.assertEqual(self.post_weight(json={"kg": 70}, headers={"Origin": "http://localhost:8102"}).status_code, 403)

    def test_sec_fetch_site_cross_site_is_rejected(self) -> None:
        headers = {**ORIGIN, "Sec-Fetch-Site": "cross-site"}
        self.assertEqual(self.post_weight(json={"kg": 70}, headers=headers).status_code, 403)

    def test_html_form_content_types_are_rejected(self) -> None:
        for content_type in ("application/x-www-form-urlencoded", "text/plain"):
            with self.subTest(content_type=content_type):
                response = self.post_weight(data='{"kg": 70}', content_type=content_type, headers=ORIGIN)
                self.assertEqual(response.status_code, 403)

    def test_delete_requires_same_origin(self) -> None:
        self.assertEqual(self.client.delete("/api/weights/999999").status_code, 403)

    def test_bearer_requests_skip_csrf(self) -> None:
        client = self.app.test_client()
        self.assertEqual(client.post("/api/weights", json={"kg": 71, "date": "2020-01-02"}, headers=_env.AUTH).status_code, 200)

    def test_cross_origin_login_is_rejected(self) -> None:
        response = self.app.test_client().post("/api/auth/login", json={"token": "test-token"},
                                               headers={"Origin": "http://evil.example"})
        self.assertEqual(response.status_code, 403)


class InjectionAndValidationTests(_Base):
    def count(self, table: str) -> int:
        import dpp_db

        allowed = {"foods", "weights", "meals"}
        assert table in allowed
        with dpp_db.connect() as db:
            return int(db.execute(f"SELECT COUNT(*) FROM {dpp_db.qident(table)}").fetchone()[0])

    def test_sql_in_query_dates_returns_400(self) -> None:
        payloads = ["2026-01-01' OR '1'='1", "1; DROP TABLE meals;--", "2026-01-01 UNION SELECT * FROM foods"]
        endpoints = ["/api/insights/today?date=", "/api/food-intel/day?date=", "/api/smart-coach/day?date=",
                     "/api/activity-plan?from="]
        meals_before = self.count("meals")
        for endpoint in endpoints:
            for payload in payloads:
                with self.subTest(endpoint=endpoint, payload=payload):
                    from urllib.parse import quote

                    response = self.client.get(endpoint + quote(payload), headers=_env.AUTH)
                    self.assertEqual(response.status_code, 400, response.get_data(as_text=True)[:200])
                    self.assertFalse(response.get_json().get("ok", False))
        self.assertEqual(self.count("meals"), meals_before)

    def test_sql_in_text_fields_is_stored_literally(self) -> None:
        name = "Robert'); DROP TABLE foods;--"
        response = self.client.post("/api/foods", json={"name": name, "kcal": 100}, headers=_env.AUTH)
        self.assertEqual(response.status_code, 200)
        state = self.client.get("/api/state", headers=_env.AUTH).get_json()
        self.assertIn(name, [food["name"] for food in state["foods"]])
        self.assertGreater(self.count("foods"), 0)

    def test_sql_in_numbers_is_a_400(self) -> None:
        before = self.count("weights")
        response = self.client.post("/api/weights", json={"kg": "70; DROP TABLE weights"}, headers=_env.AUTH)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.count("weights"), before)

    def test_sql_in_path_segments(self) -> None:
        self.assertEqual(self.client.get("/api/export/meals%3BDROP.csv", headers=_env.AUTH).status_code, 404)
        self.assertEqual(self.client.delete("/api/meals/1%20OR%201=1", headers=_env.AUTH).status_code, 404)

    def test_non_object_json_is_400(self) -> None:
        for path in ("/api/weights", "/api/meals", "/api/foods"):
            with self.subTest(path=path):
                response = self.client.post(path, json=["x"], headers=_env.AUTH)
                self.assertEqual(response.status_code, 400)

    def test_oversized_json_body_is_413(self) -> None:
        big = {"notes": "x" * (dpp_security.MAX_JSON_BYTES + 10), "kg": 70}
        response = self.client.post("/api/weights", json=big, headers=_env.AUTH)
        self.assertEqual(response.status_code, 413)

    def test_upload_with_fake_extension_is_rejected(self) -> None:
        gif = b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9\x04\x00\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
        response = self.client.post("/api/food-photo", headers=_env.AUTH,
                                    data={"photo": (io.BytesIO(gif), "label.jpg")}, content_type="multipart/form-data")
        self.assertEqual(response.status_code, 400)

    def test_legacy_pantry_write_is_local_only(self) -> None:
        response = self.client.post("/api/pantry", json={"items": []}, headers=_env.AUTH,
                                    environ_overrides={"REMOTE_ADDR": "8.8.8.8"})
        self.assertEqual(response.status_code, 403)

    def test_csv_export_neutralizes_formulas(self) -> None:
        from dpp_data_api import _csv_cell

        self.assertEqual(_csv_cell("=HYPERLINK(\"x\")"), "'=HYPERLINK(\"x\")")
        self.assertEqual(_csv_cell("@SUM(A1)"), "'@SUM(A1)")
        self.assertEqual(_csv_cell("Pollo"), "Pollo")
        self.assertEqual(_csv_cell(1.5), "1,5")


class ErrorAndHeaderTests(_Base):
    def test_public_error_hides_library_details(self) -> None:
        import requests

        response = requests.Response()
        response.status_code = 500
        response.url = "https://api.example/oauth/token?secret=abc"
        error = requests.HTTPError("500 Server Error for url: " + response.url, response=response)
        self.assertNotIn("secret", public_error(error))
        self.assertNotIn("abc", public_error(KeyError("access_token-abc")))
        self.assertEqual(public_error(ApiError("Fecha no válida")), "Fecha no válida")
        self.assertEqual(public_error(RuntimeError("Strava no conectado")), "Strava no conectado")

    def test_unexpected_errors_do_not_leak_tracebacks(self) -> None:
        with mock.patch.object(dpp_entrypoint.legacy, "build_state", side_effect=sqlite3.OperationalError("near SELECT secret")):
            response = self.client.get("/api/state", headers=_env.AUTH)
        self.assertEqual(response.status_code, 500)
        text = response.get_data(as_text=True)
        self.assertNotIn("Traceback", text)
        self.assertNotIn("secret", text)

    def test_security_headers(self) -> None:
        for path, headers in (("/api/state", _env.AUTH), ("/", _env.AUTH), ("/health", {})):
            with self.subTest(path=path):
                response = self.client.get(path, headers=headers)
                h = response.headers
                self.assertEqual(h.get("X-Content-Type-Options"), "nosniff")
                self.assertEqual(h.get("X-Frame-Options"), "DENY")
                self.assertEqual(h.get("Referrer-Policy"), "same-origin")
                self.assertIn("camera=", h.get("Permissions-Policy", ""))
                self.assertEqual(h.get("Cross-Origin-Resource-Policy"), "same-origin")
                csp = h.get("Content-Security-Policy", "")
                for directive in ("default-src 'self'", "object-src 'none'", "frame-ancestors 'none'", "base-uri 'self'"):
                    self.assertIn(directive, csp)

    def test_login_page_uses_a_nonce_csp(self) -> None:
        response = self.app.test_client().get("/")
        csp = response.headers.get("Content-Security-Policy", "")
        self.assertIn("'nonce-", csp)
        self.assertNotIn("unsafe-inline", csp)
        nonce = csp.split("'nonce-", 1)[1].split("'", 1)[0]
        self.assertIn(f'nonce="{nonce}"', response.get_data(as_text=True))

    def test_api_status_does_not_validate_bearer_tokens(self) -> None:
        payload = self.client.get("/api/auth/status", headers={"Authorization": "Bearer test-token"}).get_json()
        self.assertFalse(payload["authenticated"])


if __name__ == "__main__":
    unittest.main()
