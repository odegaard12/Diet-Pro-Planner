# Diet Pro Planner v0.0.18 — Strava stability and web settings

## Highlights

- Configure Strava privately from the web.
- Connect, renew, test and disconnect without editing .env.
- Use the Raspberry LAN callback without a PowerShell tunnel.
- Preview activities with one API request.
- Fetch exact detail only for new activities being imported.
- Cache activity details locally.
- Protect imports against duplicates and concurrent sync operations.
- Display Strava API consumption and handle HTTP 429 cleanly.
- Use a recent-window auto-sync instead of repeatedly scanning the full history.
- Introduce a compact professional Integrations screen.

## Privacy

Client secrets, OAuth tokens, activity cache and diagnostics remain local under data/ and are excluded from Git.

## Validation

- OAuth connected with activity:read_all.
- Preview returned 9 activities using 1 read request and 0 detail requests.
- Duplicate detection confirmed.
- Docker build and health smoke passed.
