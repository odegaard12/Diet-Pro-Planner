"""The session cookie is Secure (and HSTS is sent) when the request arrives over HTTPS, never over plain HTTP."""

from __future__ import annotations

import os
import unittest

import _env  # noqa: F401  (isolated data dir + auth token; must come first)

import dpp_entrypoint
import dpp_security


class HttpsCookieTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = dpp_entrypoint.legacy.app
        cls.app.config.update(TESTING=True)

    def setUp(self) -> None:
        dpp_security._LOGIN_FAILURES.clear()

    def _login(self, scheme: str):
        client = self.app.test_client()
        return client.post(
            "/api/auth/login",
            json={"token": os.environ["DPP_AUTH_TOKEN"]},
            headers={"Origin": f"{scheme}://localhost"},
            base_url=f"{scheme}://localhost",
        )

    def test_cookie_is_secure_over_https(self) -> None:
        response = self._login("https")
        self.assertEqual(response.status_code, 200)
        cookie = response.headers.get("Set-Cookie", "")
        self.assertIn("Secure", cookie)
        self.assertIn("HttpOnly", cookie)
        self.assertIn("max-age=", response.headers.get("Strict-Transport-Security", ""))

    def test_cookie_is_not_secure_over_plain_http(self) -> None:
        response = self._login("http")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("Secure", response.headers.get("Set-Cookie", ""))
        self.assertNotIn("Strict-Transport-Security", response.headers)


if __name__ == "__main__":
    unittest.main()
