"""Authentication, sessions, CSRF and HTTP security headers.

Login modes (checked in this order):

1. **User + password**: ``DPP_ADMIN_USER`` + ``DPP_ADMIN_PASSWORD_HASH`` (scrypt hash
   generated with ``python -m dpp_security hash-password``). The login form asks for both.
2. **Shared token** (legacy): ``DPP_AUTH_TOKEN`` typed in the login form. Used only when
   no user/password is configured, so existing installs keep working after an upgrade.

``Authorization: Bearer <DPP_AUTH_TOKEN>`` (or ``X-DPP-Auth``) keeps working for
automation in both modes whenever the token is set.

Browser sessions are server-side: the signed cookie only carries a random session id
whose SHA-256 is stored in ``DATA_DIR/auth_sessions.db``. Logout deletes it, so a copied
cookie stops working immediately. Sessions expire (absolute + idle limits) and are
invalidated when the password, user or token changes.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import html
import ipaddress
import os
import secrets
import sqlite3
import sys
import threading
import time
from collections import defaultdict, deque
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlparse

from flask import g, jsonify, request, session

import dpp_config as config


AUTH_TOKEN_ENV = "DPP_AUTH_TOKEN"
ADMIN_USER_ENV = "DPP_ADMIN_USER"
ADMIN_HASH_ENV = "DPP_ADMIN_PASSWORD_HASH"
TRUSTED_PROXIES_ENV = "DPP_TRUSTED_PROXIES"
_SESSION_KEY = "sid"
_PROTECTED_PAGES = {"/", "/weight-2"}
_EXEMPT_API_PATHS = {
    "/api/auth/login",
    "/api/auth/logout",
    "/api/auth/status",
    "/api/strava/callback",
}
_UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
# Content types a cookie-authenticated write may use. Plain HTML forms can only send
# urlencoded, multipart or text/plain; the app's fetch() calls send JSON (or multipart
# for photo uploads), and multipart is still guarded by the Origin/Sec-Fetch-Site checks.
_WRITE_MIMETYPES = {"", "application/json", "multipart/form-data"}

# Brute-force protection for the login endpoint and wrong bearer tokens (per client address).
LOGIN_MAX_FAILURES = 8
LOGIN_WINDOW_SECONDS = 15 * 60
_LOGIN_FAILURES: dict[str, deque] = defaultdict(deque)
_LOGIN_LOCK = threading.Lock()

# Password hashing: scrypt from the standard library (memory-hard, ~32 MiB per hash).
_SCRYPT_N = 2 ** 15
_SCRYPT_R = 8
_SCRYPT_P = 1


def _env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(str(os.environ.get(name) or default).strip())
    except ValueError:
        value = default
    return max(minimum, min(maximum, value))


SESSION_DAYS = _env_int("DPP_SESSION_DAYS", 30, 1, 365)
SESSION_IDLE_HOURS = _env_int("DPP_SESSION_IDLE_HOURS", 7 * 24, 1, 365 * 24)
MAX_JSON_BYTES = _env_int("DPP_MAX_JSON_KB", 2048, 16, 50 * 1024) * 1024

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


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _scrypt(password: str, salt: bytes, n: int, r: int, p: int, dklen: int) -> bytes:
    return hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=n, r=r, p=p, dklen=dklen,
        maxmem=128 * r * (n + p + 2) + 2 ** 20,
    )


def hash_password(password: str) -> str:
    """``scrypt:N:r:p:salt:hash`` (base64url, no ``$`` so it is safe in docker-compose .env files)."""
    if not password:
        raise ValueError("La contraseña no puede estar vacía")
    salt = secrets.token_bytes(16)
    digest = _scrypt(password, salt, _SCRYPT_N, _SCRYPT_R, _SCRYPT_P, 32)
    return f"scrypt:{_SCRYPT_N}:{_SCRYPT_R}:{_SCRYPT_P}:{_b64(salt)}:{_b64(digest)}"


def _parse_hash(stored: str):
    parts = str(stored or "").strip().split(":")
    if len(parts) != 6 or parts[0] != "scrypt":
        return None
    try:
        n, r, p = int(parts[1]), int(parts[2]), int(parts[3])
        salt, digest = _unb64(parts[4]), _unb64(parts[5])
    except (ValueError, TypeError):
        return None
    if not (2 ** 14 <= n <= 2 ** 20 and n & (n - 1) == 0 and 1 <= r <= 32 and 1 <= p <= 16):
        return None
    if len(salt) < 16 or len(digest) < 32:
        return None
    return n, r, p, salt, digest


def password_hash_is_valid(stored: str) -> bool:
    stored = str(stored or "").strip()
    if "$" in stored:  # werkzeug generate_password_hash() format
        return stored.split(":", 1)[0] in {"scrypt", "pbkdf2"} and stored.count("$") == 2
    return _parse_hash(stored) is not None


def verify_password(password: str, stored: str) -> bool:
    """Constant-time check; never raises."""
    stored = str(stored or "").strip()
    try:
        if "$" in stored:
            from werkzeug.security import check_password_hash

            return password_hash_is_valid(stored) and check_password_hash(stored, str(password or ""))
        parsed = _parse_hash(stored)
        if not parsed:
            return False
        n, r, p, salt, digest = parsed
        candidate = _scrypt(str(password or ""), salt, n, r, p, len(digest))
        return hmac.compare_digest(candidate, digest)
    except (ValueError, TypeError, MemoryError):
        return False


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

def configured_auth_token() -> str:
    return str(os.environ.get(AUTH_TOKEN_ENV) or "").strip()


def configured_admin_user() -> str:
    return str(os.environ.get(ADMIN_USER_ENV) or "").strip()


def configured_admin_hash() -> str:
    return str(os.environ.get(ADMIN_HASH_ENV) or "").strip()


def password_login_configured() -> bool:
    return bool(configured_admin_user()) and password_hash_is_valid(configured_admin_hash())


def auth_is_configured() -> bool:
    return bool(configured_auth_token()) or password_login_configured()


def login_mode() -> str:
    if password_login_configured():
        return "password"
    return "token" if configured_auth_token() else "none"


def _credential_fingerprint() -> str:
    """Changes whenever the login credentials change, which invalidates every session."""
    if password_login_configured():
        material = f"password\0{configured_admin_user()}\0{configured_admin_hash()}"
    else:
        material = f"token\0{configured_auth_token()}"
    return hashlib.sha256(("dpp-cred::" + material).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Brute-force protection
# ---------------------------------------------------------------------------

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
        failures = _LOGIN_FAILURES.get(address)
        if not failures:
            return 0
        while failures and now - failures[0] > LOGIN_WINDOW_SECONDS:
            failures.popleft()
        if len(failures) >= LOGIN_MAX_FAILURES:
            return int(LOGIN_WINDOW_SECONDS - (now - failures[0])) + 1
    return 0


def _record_login_failure(address: str) -> None:
    now = time.monotonic()
    with _LOGIN_LOCK:
        if len(_LOGIN_FAILURES) > 5000:
            # Bound memory: forget addresses whose last failure left the window.
            for key in [k for k, q in _LOGIN_FAILURES.items() if not q or now - q[-1] > LOGIN_WINDOW_SECONDS]:
                _LOGIN_FAILURES.pop(key, None)
        _LOGIN_FAILURES[address].append(now)


def _clear_login_failures(address: str) -> None:
    with _LOGIN_LOCK:
        _LOGIN_FAILURES.pop(address, None)


# ---------------------------------------------------------------------------
# Request helpers
# ---------------------------------------------------------------------------

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


def _token_matches(candidate: str) -> bool:
    token = configured_auth_token()
    return bool(token) and hmac.compare_digest(str(candidate or "").encode("utf-8"), token.encode("utf-8"))


def _same_origin_request() -> bool:
    source = str(request.headers.get("Origin") or request.headers.get("Referer") or "").strip()
    if not source:
        return False
    parsed = urlparse(source)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False
    return hmac.compare_digest(parsed.netloc.lower(), request.host.lower())


def csrf_check_passes() -> bool:
    """CSRF guard for cookie-authenticated writes (bearer requests carry no ambient credentials).

    Requires all of: Sec-Fetch-Site same-origin (when the browser sends it), an Origin or
    Referer equal to this host, and a content type an HTML form cannot forge silently
    (JSON, multipart for photo uploads, or no body). The current frontend already
    satisfies this with plain ``fetch()``; no custom header is needed.
    """
    fetch_site = str(request.headers.get("Sec-Fetch-Site") or "").strip().lower()
    if fetch_site and fetch_site != "same-origin":
        return False
    if not _same_origin_request():
        return False
    mimetype = (request.mimetype or "").lower()
    if mimetype not in _WRITE_MIMETYPES:
        return False
    if not mimetype and (request.content_length or 0) > 0:
        return False
    return True


# ---------------------------------------------------------------------------
# Server-side sessions
# ---------------------------------------------------------------------------

_SESSION_DB_LOCK = threading.Lock()
_LAST_SEEN_WRITE_SECONDS = 300


def _session_db_path() -> Path:
    return Path(config.DATA_DIR) / "auth_sessions.db"


def _create_private_file(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(fd)
    except FileExistsError:
        pass
    try:
        path.chmod(0o600)
    except OSError:
        pass


def _session_db() -> sqlite3.Connection:
    path = _session_db_path()
    if not path.exists():
        _create_private_file(path)
    db = sqlite3.connect(str(path), timeout=10)
    db.execute(
        "CREATE TABLE IF NOT EXISTS sessions("
        " id_hash TEXT PRIMARY KEY, username TEXT NOT NULL, cred TEXT NOT NULL,"
        " created_at REAL NOT NULL, last_seen REAL NOT NULL, expires_at REAL NOT NULL)"
    )
    return db


def _sid_hash(sid: str) -> str:
    return hashlib.sha256(("dpp-sid::" + sid).encode("utf-8")).hexdigest()


def create_session(username: str) -> str:
    sid = secrets.token_urlsafe(32)
    now = time.time()
    with _SESSION_DB_LOCK:
        db = _session_db()
        try:
            with db:
                db.execute("DELETE FROM sessions WHERE expires_at < ? OR last_seen < ?",
                           (now, now - SESSION_IDLE_HOURS * 3600))
                db.execute(
                    "INSERT INTO sessions(id_hash, username, cred, created_at, last_seen, expires_at) VALUES(?,?,?,?,?,?)",
                    (_sid_hash(sid), username, _credential_fingerprint(), now, now, now + SESSION_DAYS * 86400),
                )
        finally:
            db.close()
    return sid


def session_is_valid(sid) -> bool:
    if not isinstance(sid, str) or not (20 <= len(sid) <= 100):
        return False
    now = time.time()
    key = _sid_hash(sid)
    with _SESSION_DB_LOCK:
        db = _session_db()
        try:
            with db:
                row = db.execute("SELECT cred, last_seen, expires_at FROM sessions WHERE id_hash=?", (key,)).fetchone()
                if not row:
                    return False
                cred, last_seen, expires_at = row
                fresh = expires_at > now and now - last_seen < SESSION_IDLE_HOURS * 3600
                if not fresh or not hmac.compare_digest(str(cred), _credential_fingerprint()):
                    db.execute("DELETE FROM sessions WHERE id_hash=?", (key,))
                    return False
                if now - last_seen > _LAST_SEEN_WRITE_SECONDS:
                    db.execute("UPDATE sessions SET last_seen=? WHERE id_hash=?", (now, key))
                return True
        finally:
            db.close()


def revoke_session(sid) -> None:
    if not isinstance(sid, str) or not sid:
        return
    with _SESSION_DB_LOCK:
        db = _session_db()
        try:
            with db:
                db.execute("DELETE FROM sessions WHERE id_hash=?", (_sid_hash(sid),))
        finally:
            db.close()


def revoke_all_sessions() -> int:
    with _SESSION_DB_LOCK:
        db = _session_db()
        try:
            with db:
                return db.execute("DELETE FROM sessions").rowcount or 0
        finally:
            db.close()


def _session_is_valid() -> bool:
    return session_is_valid(session.get(_SESSION_KEY))


def load_secret_key() -> str:
    """FLASK_SECRET_KEY if set; otherwise a random key generated once in DATA_DIR (mode 600)."""
    explicit = str(os.environ.get("FLASK_SECRET_KEY") or os.environ.get("SECRET_KEY") or "").strip()
    if explicit:
        return explicit
    path = Path(config.DATA_DIR) / ".session_secret"
    for _attempt in range(2):
        try:
            value = path.read_text(encoding="utf-8").strip()
            if len(value) >= 32:
                return value
        except OSError:
            pass
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            continue  # another worker created it: read it on the next attempt
        except OSError:
            break
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(secrets.token_hex(32))
    print("[DPP] WARNING: no se pudo guardar la clave de sesión en el directorio de datos; "
          "las sesiones se cerrarán al reiniciar", file=sys.stderr)
    return secrets.token_hex(32)


# ---------------------------------------------------------------------------
# Login page
# ---------------------------------------------------------------------------

def _protected_kind(path: str) -> str | None:
    if path in _PROTECTED_PAGES:
        return "page"
    if path.startswith("/uploads/"):
        return "upload"
    if path.startswith("/api/") and path not in _EXEMPT_API_PATHS:
        return "api"
    return None


def _login_page(next_path: str = "/", setup_required: bool = False):
    safe_next = html.escape(safe_next_path(next_path), quote=True)
    nonce = secrets.token_urlsafe(16)
    title = "Diet Pro Planner · Acceso protegido"
    if setup_required:
        body = """
        <p>La API privada está bloqueada hasta configurar el acceso.</p>
        <p>Define <code>DPP_ADMIN_USER</code> + <code>DPP_ADMIN_PASSWORD_HASH</code>
        (o un <code>DPP_AUTH_TOKEN</code> largo y aleatorio) en tu <code>.env</code> local y reinicia la aplicación.</p>
        """
    else:
        if login_mode() == "password":
            fields = """
          <label for="username">Usuario</label>
          <input id="username" name="username" type="text" autocomplete="username" autocapitalize="none" spellcheck="false" required />
          <label for="password">Contraseña</label>
          <input id="password" name="password" type="password" autocomplete="current-password" required />"""
        else:
            fields = """
          <label for="token">Token de acceso</label>
          <input id="token" name="token" type="password" autocomplete="current-password" required />"""
        body = f"""
        <form id="loginForm">{fields}
          <input id="next" name="next" type="hidden" value="{safe_next}" />
          <button type="submit">Entrar</button>
          <p id="error" role="alert"></p>
        </form>
        <script nonce="{nonce}">
        document.getElementById('loginForm')?.addEventListener('submit', async (event) => {{
          event.preventDefault();
          const value = (id) => (document.getElementById(id)?.value ?? undefined);
          const error = document.getElementById('error');
          error.textContent = '';
          const response = await fetch('/api/auth/login', {{
            method: 'POST',
            credentials: 'same-origin',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{username: value('username'), password: value('password'), token: value('token'), next: value('next') || '/'}})
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
    page = f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta name="robots" content="noindex" />
  <title>{title}</title>
  <meta name="theme-color" content="#0d1117" />
  <link rel="icon" type="image/png" href="/static/icon-192.png" />
  <style nonce="{nonce}">
    /* Same tokens as static/css/base.css (inline: this page's CSP only allows nonce styles). */
    :root {{ color-scheme: dark; --bg: #0d1117; --surface: #161b22; --border: #30363d; --text: #e6edf3; --text-2: #8b949e;
      --primary: #fb923c; --primary-ink: #1c1510; --bad: #f87171; --ring: rgba(251, 146, 60, .25); }}
    *, *::before, *::after {{ box-sizing: border-box; }}
    body {{ margin: 0; min-height: 100vh; min-height: 100dvh; display: grid; place-items: center; padding: 20px 16px;
      background: var(--bg); color: var(--text); font: 16px/1.5 Inter, ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif; }}
    main {{ width: 100%; max-width: 400px; padding: 28px 24px; border: 1px solid var(--border); border-radius: 20px; background: var(--surface);
      box-shadow: 0 12px 36px rgba(15, 27, 45, .12); }}
    .brand {{ display: flex; align-items: center; gap: 12px; margin-bottom: 18px; }}
    .brand img {{ width: 44px; height: 44px; border-radius: 12px; }}
    h1 {{ margin: 0; font-size: 20px; font-weight: 750; }}
    .brand p, .hint {{ margin: 0; color: var(--text-2); font-size: 14px; }}
    .hint {{ margin-bottom: 16px; }}
    code {{ background: var(--bg); padding: 1px 6px; border-radius: 6px; }}
    form {{ display: grid; gap: 8px; }}
    label {{ font-size: 14px; font-weight: 650; color: var(--text-2); margin-top: 4px; }}
    input, button {{ width: 100%; min-height: 48px; font: inherit; font-size: 16px; border-radius: 12px; }}
    input {{ padding: 0 14px; border: 1px solid var(--border); background: var(--surface); color: var(--text); }}
    input:focus {{ outline: none; border-color: var(--primary); box-shadow: 0 0 0 3px var(--ring); }}
    button {{ margin-top: 8px; border: 0; background: var(--primary); color: var(--primary-ink); font-weight: 700; cursor: pointer; }}
    #error {{ min-height: 1.4em; margin: 4px 0 0; color: var(--bad); font-size: 14px; }}
  </style>
</head>
<body>
  <main>
    <div class="brand"><img src="/static/icon-192.png" alt="" /><div><h1>Diet Pro Planner</h1><p>Acceso privado</p></div></div>
    <p class="hint">Entra para ver tus comidas, peso y entrenos.</p>
    {body}
  </main>
</body>
</html>"""
    csp = "; ".join([
        "default-src 'none'",
        f"script-src 'nonce-{nonce}'",
        f"style-src 'nonce-{nonce}'",
        "connect-src 'self'",
        "img-src 'self'",
        "base-uri 'none'",
        "form-action 'self'",
        "frame-ancestors 'none'",
    ])
    return page, 200, {"Content-Security-Policy": csp, "Cache-Control": "no-store"}


def _api_unauthorized(message: str, status_code: int):
    challenge = "Be" + "arer realm=" + '"Diet Pro Planner"'
    response = jsonify({"ok": False, "error": message})
    response.status_code = status_code
    response.headers["WWW-Authenticate"] = challenge
    response.headers["Cache-Control"] = "no-store"
    return response


def _current_page_path() -> str:
    return request.full_path[:-1] if request.full_path.endswith("?") else request.full_path


def _reject_for_missing_config(kind: str):
    if kind == "page":
        return _login_page(_current_page_path(), setup_required=True)
    return _api_unauthorized("Configura DPP_ADMIN_USER + DPP_ADMIN_PASSWORD_HASH o DPP_AUTH_TOKEN", 503)


def _reject_for_missing_auth(kind: str):
    if kind == "page":
        return _login_page(_current_page_path())
    return _api_unauthorized("Autenticación requerida", 401)


def _too_many_attempts(retry_after: int):
    response = _api_unauthorized(f"Demasiados intentos. Espera {max(1, retry_after // 60)} min.", 429)
    response.headers["Retry-After"] = str(retry_after)
    return response


def protect_request():
    path = request.path or "/"
    # Bodies other than photo uploads are small JSON documents (Flask >= 3.1 per-request limit).
    if (request.mimetype or "") != "multipart/form-data":
        request.max_content_length = MAX_JSON_BYTES
    if path == "/health" or path.startswith("/static/"):
        return None
    kind = _protected_kind(path)
    if not kind:
        return None
    if not auth_is_configured():
        return _reject_for_missing_config(kind)
    candidate = _header_token()
    header_ok = bool(candidate) and _token_matches(candidate)
    if candidate and not header_ok:
        # Wrong bearer tokens count towards the same brute-force limit as the login form.
        address = _request_address() or "unknown"
        retry_after = _login_blocked(address)
        if retry_after:
            return _too_many_attempts(retry_after)
        _record_login_failure(address)
    session_ok = not header_ok and _session_is_valid()
    if not (header_ok or session_ok):
        return _reject_for_missing_auth(kind)
    g.dpp_auth = "token" if header_ok else "session"
    if session_ok and request.method in _UNSAFE_METHODS and not csrf_check_passes():
        return jsonify({"ok": False, "error": "Origen no permitido"}), 403
    return None


def _check_credentials(body: dict) -> tuple[bool, str]:
    """Returns (ok, username). Always does the same work for unknown users (no user enumeration)."""
    if login_mode() == "password":
        username = str(body.get("username") or "").strip()[:200]
        password = str(body.get("password") or "")[:1024]
        expected_user = configured_admin_user()
        user_ok = hmac.compare_digest(username.casefold().encode("utf-8"), expected_user.casefold().encode("utf-8"))
        password_ok = verify_password(password, configured_admin_hash())
        return (user_ok and password_ok), expected_user
    candidate = str(body.get("token") or body.get("password") or "").strip()[:1024]
    return (bool(candidate) and _token_matches(candidate)), "token"


def register_security(app) -> None:
    if getattr(app, "_dpp_security_registered", False):
        return

    if str(os.environ.get(ADMIN_HASH_ENV) or "").strip() and not password_login_configured():
        print(f"[DPP] WARNING: {ADMIN_HASH_ENV} no es válido o falta {ADMIN_USER_ENV}; "
              "se usa el login por token", file=sys.stderr)
    if not app.secret_key:
        app.secret_key = load_secret_key()
    # Never run the Werkzeug debugger (remote code execution) even if FLASK_DEBUG leaks in.
    app.config["DEBUG"] = False
    app.debug = False
    # Assigned (not setdefault): Flask's default config already defines these keys.
    app.config["SESSION_COOKIE_NAME"] = "dpp_session"
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    # Set DPP_COOKIE_SECURE=1 when the app is served over HTTPS (reverse proxy).
    cookie_secure = str(os.environ.get("DPP_COOKIE_SECURE") or "").lower() in {"1", "true", "yes"}
    app.config["SESSION_COOKIE_SECURE"] = cookie_secure
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=SESSION_DAYS)
    app.config["SESSION_REFRESH_EACH_REQUEST"] = False

    @app.before_request
    def _dpp_protect_request():
        return protect_request()

    @app.after_request
    def _dpp_security_headers(response):
        headers = response.headers
        headers.setdefault("X-Content-Type-Options", "nosniff")
        headers.setdefault("X-Frame-Options", "DENY")
        headers.setdefault("Referrer-Policy", "same-origin")
        headers.setdefault("Permissions-Policy", "camera=(self), microphone=(), geolocation=(), payment=(), usb=()")
        headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")
        headers.setdefault("Content-Security-Policy", CONTENT_SECURITY_POLICY)
        if cookie_secure:
            headers.setdefault("Strict-Transport-Security", "max-age=31536000")
        path = request.path or ""
        if path.startswith("/api/") or path.startswith("/uploads/"):
            # Health data must never be stored by shared or browser caches.
            headers["Cache-Control"] = "no-store"
        return response

    @app.get("/api/auth/status")
    def _dpp_auth_status():
        # Session only: checking bearer tokens here would be an oracle outside the rate limit.
        return jsonify({"ok": True, "mode": login_mode(), "authenticated": _session_is_valid()})

    @app.post("/api/auth/login")
    def _dpp_auth_login():
        if not auth_is_configured():
            return jsonify({"ok": False, "error": "Configura el acceso en .env antes de iniciar sesión"}), 503
        if request.headers.get("Origin") and not _same_origin_request():
            return jsonify({"ok": False, "error": "Origen no permitido"}), 403
        address = _request_address() or "unknown"
        retry_after = _login_blocked(address)
        if retry_after:
            return _too_many_attempts(retry_after)
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            body = {}
        ok, username = _check_credentials(body)
        previous = session.get(_SESSION_KEY)
        # Rotation: any pre-login session id (fixation, or the old session) is discarded.
        revoke_session(previous)
        session.clear()
        if not ok:
            _record_login_failure(address)
            message = "Usuario o contraseña incorrectos" if login_mode() == "password" else "Token no válido"
            return jsonify({"ok": False, "error": message}), 401
        _clear_login_failures(address)
        session[_SESSION_KEY] = create_session(username)
        session.permanent = True
        return jsonify({"ok": True, "next": safe_next_path(body.get("next")), "mode": login_mode()})

    @app.post("/api/auth/logout")
    def _dpp_auth_logout():
        revoke_session(session.get(_SESSION_KEY))
        session.clear()
        response = jsonify({"ok": True})
        response.headers["Clear-Site-Data"] = '"cache", "storage"'
        return response

    app._dpp_security_registered = True


def _cli(argv: list[str]) -> int:
    import getpass

    usage = (
        "Uso:\n"
        "  python -m dpp_security hash-password [--stdin]   genera DPP_ADMIN_PASSWORD_HASH\n"
        "  python -m dpp_security revoke-sessions           cierra todas las sesiones abiertas\n"
    )
    if not argv or argv[0] in {"-h", "--help"}:
        print(usage)
        return 0 if argv else 2
    if argv[0] == "hash-password":
        if "--stdin" in argv[1:]:
            password = sys.stdin.readline().rstrip("\r\n")
        else:
            password = getpass.getpass("Contraseña: ")
            if password != getpass.getpass("Repite la contraseña: "):
                print("Las contraseñas no coinciden", file=sys.stderr)
                return 1
        if len(password) < 10:
            print("Usa al menos 10 caracteres", file=sys.stderr)
            return 1
        print(hash_password(password))
        return 0
    if argv[0] == "revoke-sessions":
        print(f"Sesiones cerradas: {revoke_all_sessions()}")
        return 0
    print(usage, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(_cli(sys.argv[1:]))
