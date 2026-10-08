# Diet Pro Planner — Security hardening for private self-hosting

_Shipped as part of v0.1.0._

v0.0.21 focuses on tightening the local deployment surface without changing the local-first product model.

## Highlights

- Required authentication for private `/api/*` endpoints and `/uploads/*` access.
- Local browser login flow plus bearer-token support for automation or trusted local clients.
- Safer local-network validation that ignores forged `X-Forwarded-For` headers unless the proxy is explicitly trusted.
- Strava `client_secret` is no longer persisted in `data/integrations.json`.
- Legacy disk-backed Strava config is sanitized automatically if an older plaintext secret is found.
- Upload serving now rejects traversal-style paths instead of relying on permissive path routing.

## Operational notes

- Keep `DPP_AUTH_TOKEN` only in your private local `.env`.
- Keep `STRAVA_CLIENT_SECRET` only in your private local `.env`.
- `/health` remains public so Docker and uptime checks keep working.

## Validation

- Python fatal-error lint and compilation passed.
- JavaScript syntax checks passed.
- Frontend budget and repository privacy guards passed.
- Pantry and activity-plan regression checks passed.
- Flask security smoke tests passed.
- No secrets were detected in the changed files.
