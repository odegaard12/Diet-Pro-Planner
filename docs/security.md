# Access protection and security model

- **User + password login (recommended).** Generate a scrypt hash and put it in `.env`:

  ```bash
  docker compose exec diet-pro-planner python -m dpp_security hash-password   # or: python -m dpp_security hash-password
  ```

  ```dotenv
  DPP_ADMIN_USER=admin
  DPP_ADMIN_PASSWORD_HASH=scrypt:32768:8:1:...   # output of the command above (no $ signs, safe for compose)
  ```

  Then `docker compose up -d`. The password itself is never stored; only the salted scrypt hash.
- **Token login (legacy fallback).** If no user/password is configured, the login screen asks for `DPP_AUTH_TOKEN`
  as before, so upgrading never locks an existing install out. Keep `DPP_AUTH_TOKEN` set even with a password:
  automation can keep using the `Authorization: Bearer <DPP_AUTH_TOKEN>` header (or `X-DPP-Auth`).
- Sessions are server-side (`data/auth_sessions.db`, only SHA-256 of the session id is stored): logout really
  invalidates the cookie, every login issues a new session id, and sessions expire after `DPP_SESSION_DAYS`
  (default 30) or `DPP_SESSION_IDLE_HOURS` without use (default 168). Changing the password, user or token logs
  every session out; `python -m dpp_security revoke-sessions` does it on demand. The cookie signing key is
  generated once in `data/.session_secret` (mode 600) unless `FLASK_SECRET_KEY` is set.
- Login attempts and wrong bearer tokens are rate limited per client address (8 per 15 min); sessions use an
  HttpOnly, SameSite=Lax cookie (`DPP_COOKIE_SECURE=1` behind HTTPS, which also enables HSTS).
- CSRF: cookie-authenticated writes must come from the same origin (`Origin`/`Referer` = this host,
  `Sec-Fetch-Site: same-origin` when sent) with a JSON or multipart body; HTML forms from other sites are rejected.
- Behind a reverse proxy, set `DPP_TRUSTED_PROXIES` so the limiter sees real client addresses (otherwise every client shares the proxy's address).
- `/health` stays public for Docker and uptime checks.
- Strava `client_secret` is read from `STRAVA_CLIENT_SECRET` only and is never stored in `data/integrations.json`.

## Docker hardening

Build and start:

```bash
docker compose up -d --build
```

The container starts as root only long enough to give `./data` to uid/gid `10001` (older installs have root-owned
files there), then drops every privilege and runs as that user. The root filesystem is read-only (only `./data` and
a `/tmp` tmpfs are writable), `no-new-privileges` is set and capabilities are limited to the ones the entrypoint
needs. To read `./data` from the host afterwards use `sudo` (files are private, mode 600/700).

Default local URL:

```text
http://localhost:8099
```

LAN example:

```text
http://raspberrypi.local:8099
```
