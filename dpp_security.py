from __future__ import annotations

import hashlib
import hmac
import html
import ipaddress
import os
import threading
import time
from collections import defaultdict, deque
from datetime import timedelta
from urllib.parse import urlparse

from flask import jsonify, request, session


AUTH_TOKEN_ENV = "DPP_AUTH_TOKEN"
TRUSTED_PROXIES_ENV = "DPP_TRUSTED_PROXIES"
_SESSION_FLAG = "dpp_authenticated"
_PROTECTED_PAGES = {"/", "/weight-2"}
_EXEMPT_API_PATHS = {
    "/api/auth/login",
    "/api/strava/callback",
}
_UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

# Brute-force protection for the login endpoint (per client address).
LOGIN_MAX_FAILURES = 8
LOGIN_WINDOW_SECONDS = 15 * 60
_LOGIN_FAILURES: dict[str, deque] = defaultdict(deque)
_LOGIN_LOCK = threading.Lock()

# Inline handlers (onclick=…) are still used by the legacy UI, so scripts need
# 'unsafe-inline'; the policy still blocks every external origin, plugins and
# framing, which removes data-exfiltration and clickjacking paths.
CONTENT_SECURITY_POLICY = "; ".join([
    "default-src 'self'",
    "script-src 'self' 'unsafe-inline'",
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: blob:",
    "font-src 'self' data:",
    "connect-src 'self'",
    "media-src 'self' blob:",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
])


def safe_next_path(value) -> str:
    """Only same-site absolute paths: rejects //evil.com, /\\evil.com and schemes."""
    text = str(value or "").strip()
    if not text.startswith("/") or text.startswith("//") or text.startswith("/\\"):
        return "/"
    if any(ord(ch) < 32 for ch in text) or "\\" in text:
        return "/"
    return text[:500]


def _login_blocked(address: str) -> int:
    """Seconds until the address may retry, or 0."""
    now = time.monotonic()
    with _LOGIN_LOCK:
        failures = _LOGIN_FAILURES[address]
        while failures and now - failures[0] > LOGIN_WINDOW_SECONDS:
            failures.popleft()
        if len(failures) >= LOGIN_MAX_FAILURES:
            return int(LOGIN_WINDOW_SECONDS - (now - failures[0])) + 1
    return 0


def _record_login_failure(address: str) -> None:
    with _LOGIN_LOCK:
        _LOGIN_FAILURES[address].append(time.monotonic())


def _clear_login_failures(address: str) -> None:
    with _LOGIN_LOCK:
        _LOGIN_FAILURES.pop(address, None)


def configured_auth_token() -> str:
    return str(os.environ.get(AUTH_TOKEN_ENV) or "").strip()


def auth_is_configured() -> bool:
    return bool(configured_auth_token())


def _trusted_proxy_values() -> tuple[str, ...]:
    raw = str(os.environ.get(TRUSTED_PROXIES_ENV) or "")
    return tuple(part.strip() for part in raw.split(",") if part.strip())


def _matches_trusted_proxy(remote_addr: str) -> bool:
    if not remote_addr:
        return False
    for value in _trusted_proxy_values():
        try:
            network = ipaddress.ip_network(value, strict=False)
            if ipaddress.ip_address(remote_addr) in network:
                return True
        except ValueError:
            if hmac.compare_digest(remote_addr, value):
                return True
    return False


def _request_address() -> str:
    remote_addr = str(request.remote_addr or "").strip()
    if _matches_trusted_proxy(remote_addr):
        forwarded = str(request.headers.get("X-Forwarded-For") or "").split(",", 1)[0].strip()
        if forwarded:
            return forwarded
    return remote_addr


def is_private_request() -> bool:
    raw = _request_address()
    try:
        address = ipaddress.ip_address(raw)
        return bool(address.is_private or address.is_loopback or address.is_link_local)
    except ValueError:
        return raw in {"localhost", "raspberrypi"}


def _header_token() -> str:
    value = str(request.headers.get("Authorization") or "").strip()
    if value.lower().startswith("bearer "):
        return value[7:].strip()
    return str(request.headers.get("X-DPP-Auth") or "").strip()


def _header_token_is_valid() -> bool:
    token = configured_auth_token()
    return bool(token) and hmac.compare_digest(_header_token().encode("utf-8"), token.encode("utf-8"))


def _session_is_valid() -> bool:
    return session.get(_SESSION_FLAG) is True


def _same_origin_request() -> bool:
    source = str(request.headers.get("Origin") or request.headers.get("Referer") or "").strip()
    if not source:
        return False
    parsed = urlparse(source)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False
    return hmac.compare_digest(parsed.netloc.lower(), request.host.lower())


def _protected_kind(path: str) -> str | None:
    if path in _PROTECTED_PAGES:
        return "page"
    if path.startswith("/uploads/"):
        return "upload"
    if path.startswith("/api/") and path not in _EXEMPT_API_PATHS:
        return "api"
    return None


def _login_page(next_path: str = "/", setup_required: bool = False) -> str:
    safe_next = html.escape(safe_next_path(next_path), quote=True)
    title = "Diet Pro Planner · Acceso protegido"
    if setup_required:
        body = """
        <p>La API privada está bloqueada hasta configurar <code>DPP_AUTH_TOKEN</code>.</p>
        <p>Define un token largo y aleatorio en tu <code>.env</code> local y reinicia la aplicación.</p>
        """
    else:
        body = f"""
        <form id="loginForm">
          <label for="token">Token de acceso</label>
          <input id="token" name="token" type="password" autocomplete="current-password" required />
          <input id="next" name="next" type="hidden" value="{safe_next}" />
          <button type="submit">Entrar</button>
          <p id="error" role="alert"></p>
        </form>
        <script>
        document.getElementById('loginForm')?.addEventListener('submit', async (event) => {{
          event.preventDefault();
          const token = document.getElementById('token').value;
          const next = document.getElementById('next').value || '/';
          const error = document.getElementById('error');
          error.textContent = '';
          const response = await fetch('/api/auth/login', {{
            method: 'POST',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{token, next}})
          }});
          const payload = await response.json().catch(() => ({{error: 'Error'}}));
          if (!response.ok || !payload.ok) {{
            error.textContent = payload.error || 'No se pudo iniciar sesión';
            return;
          }}
          const target = String(payload.next || '/');
          window.location.assign(target.startsWith('/') && !target.startsWith('//') ? target : '/');
        }});
        </script>
        """
    return f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{title}</title>
  <style>
    :root {{ color-scheme: light dark; font-family: system-ui, sans-serif; }}
    body {{ margin: 0; min-height: 100vh; display: grid; place-items: center; background: #0f172a; color: #e2e8f0; }}
    main {{ width: min(92vw, 28rem); padding: 2rem; border-radius: 1rem; background: rgba(15, 23, 42, 0.92); box-shadow: 0 20px 45px rgba(15, 23, 42, 0.35); }}
    h1 {{ margin-top: 0; font-size: 1.75rem; }}
    p {{ line-height: 1.5; }}
    code {{ background: rgba(148, 163, 184, 0.15); padding: 0.15rem 0.35rem; border-radius: 0.3rem; }}
    form {{ display: grid; gap: 0.75rem; }}
    label {{ font-weight: 600; }}
    input, button {{ font: inherit; padding: 0.8rem 0.9rem; border-radius: 0.75rem; border: 1px solid rgba(148, 163, 184, 0.3); }}
    input {{ background: rgba(15, 23, 42, 0.6); color: inherit; }}
    button {{ background: #22c55e; color: #052e16; font-weight: 700; cursor: pointer; }}
    #error {{ min-height: 1.4rem; color: #fca5a5; margin: 0; }}
  </style>
</head>
<body>
  <main>
    <h1>Diet Pro Planner</h1>
    <p>Esta instalación requiere autenticación para acceder a la API privada y a los archivos subidos.</p>
    {body}
  </main>
</body>
</html>"""


def _api_unauthorized(message: str, status_code: int):
    challenge = "Be" + "arer realm=" + '"Diet Pro Planner"'
    response = jsonify({"ok": False, "error": message})
    response.status_code = status_code
    response.headers["WWW-Authenticate"] = challenge
    response.headers["Cache-Control"] = "no-store"
    return response


def _reject_for_missing_config(kind: str):
    if kind == "page":
        return _login_page(request.full_path[:-1] if request.query_string else request.path, setup_required=True), 200
    return _api_unauthorized(
        "Configura DPP_AUTH_TOKEN para habilitar la API privada",
        503,
    )


def _reject_for_missing_auth(kind: str):
    if kind == "page":
        return _login_page(request.full_path[:-1] if request.query_string else request.path), 200
    return _api_unauthorized("Autenticación requerida", 401)


def protect_request():
    path = request.path or "/"
    if path == "/health" or path.startswith("/static/"):
        return None
    kind = _protected_kind(path)
    if not kind:
        return None
    if not auth_is_configured():
        return _reject_for_missing_config(kind)
    header_ok = _header_token_is_valid()
    session_ok = _session_is_valid()
    if _header_token() and not header_ok:
        # Wrong bearer tokens count towards the same brute-force limit as the login form.
        address = _request_address() or "unknown"
        retry_after = _login_blocked(address)
        if retry_after:
            response = _api_unauthorized("Demasiados intentos; espera unos minutos", 429)
            response.headers["Retry-After"] = str(retry_after)
            return response
        _record_login_failure(address)
    if not (header_ok or session_ok):
        return _reject_for_missing_auth(kind)
    if session_ok and not header_ok and request.method in _UNSAFE_METHODS and not _same_origin_request():
        return jsonify({"ok": False, "error": "Origen no permitido"}), 403
    return None


def register_security(app) -> None:
    if getattr(app, "_dpp_security_registered", False):
        return

    if not app.secret_key:
        explicit = os.environ.get("FLASK_SECRET_KEY") or os.environ.get("SECRET_KEY")
        # Derived from the access token by default: rotating the token logs every session out.
        seed = explicit or configured_auth_token() or "diet-pro-planner"
        app.secret_key = hashlib.sha256(f"dpp-session::{seed}".encode("utf-8")).hexdigest()
    # Assigned (not setdefault): Flask's default config already defines these keys.
    app.config["SESSION_COOKIE_NAME"] = "dpp_session"
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    # Set DPP_COOKIE_SECURE=1 when the app is served over HTTPS (reverse proxy).
    app.config["SESSION_COOKIE_SECURE"] = str(os.environ.get("DPP_COOKIE_SECURE") or "").lower() in {"1", "true", "yes"}
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=30)

    @app.before_request
    def _dpp_protect_request():
        return protect_request()

    @app.after_request
    def _dpp_security_headers(response):
        headers = response.headers
        headers.setdefault("X-Content-Type-Options", "nosniff")
        headers.setdefault("X-Frame-Options", "DENY")
        headers.setdefault("Referrer-Policy", "same-origin")
        headers.setdefault("Permissions-Policy", "camera=(self), microphone=(), geolocation=(), payment=()")
        headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        headers.setdefault("Content-Security-Policy", CONTENT_SECURITY_POLICY)
        path = request.path or ""
        if path.startswith("/api/") or path.startswith("/uploads/"):
            # Health data must never be stored by shared or browser caches.
            headers["Cache-Control"] = "no-store"
        return response

    @app.post("/api/auth/login")
    def _dpp_auth_login():
        if not auth_is_configured():
            return jsonify({"ok": False, "error": "Configura DPP_AUTH_TOKEN antes de iniciar sesión"}), 503
        address = _request_address() or "unknown"
        retry_after = _login_blocked(address)
        if retry_after:
            response = jsonify({"ok": False, "error": f"Demasiados intentos. Espera {max(1, retry_after // 60)} min."})
            response.status_code = 429
            response.headers["Retry-After"] = str(retry_after)
            return response
        body = request.get_json(silent=True) or {}
        candidate = str(body.get("token") or body.get("password") or "").strip()
        token = configured_auth_token()
        if not candidate or not hmac.compare_digest(candidate.encode("utf-8"), token.encode("utf-8")):
            _record_login_failure(address)
            session.clear()
            return jsonify({"ok": False, "error": "Token no válido"}), 401
        _clear_login_failures(address)
        session.clear()
        session[_SESSION_FLAG] = True
        session.permanent = True
        return jsonify({"ok": True, "next": safe_next_path(body.get("next"))})

    @app.post("/api/auth/logout")
    def _dpp_auth_logout():
        session.clear()
        return jsonify({"ok": True})

    app._dpp_security_registered = True
