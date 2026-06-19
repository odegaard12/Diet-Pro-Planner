# Security Policy

## Supported versions

Security fixes are applied to the latest released version and to the current `main` branch.

Older releases are not maintained separately. Users should update to the latest release before reporting a problem that may already have been fixed.

## Reporting a vulnerability

Please do not open a public issue for a vulnerability that could expose private food logs, SQLite data, Strava credentials, API keys, uploaded label images or local network details.

Use GitHub private vulnerability reporting when it is available for this repository. If that option is not available, contact the maintainer privately through the GitHub profile for `@odegaard12` and include:

- the affected version or commit;
- the component and route involved;
- clear reproduction steps;
- the expected and actual result;
- the potential impact;
- a suggested remediation, when known.

Do not include real access tokens, client secrets, private databases, personal health data or full `.env` files in the report. Replace them with redacted examples.

## Response targets

The project aims to:

- acknowledge a valid private report within 7 days;
- assess severity and scope within 14 days;
- publish or coordinate a fix as soon as practical;
- credit the reporter when requested and appropriate.

These are best-effort targets for a personal open-source project, not guaranteed service levels.

## Security model

Diet Pro Planner is local-first and is intended to run on a trusted private network. The public repository must never contain runtime secrets or personal data.

Private files include, but are not limited to:

- `data/dieta.db` and other SQLite databases;
- `data/pantry.json`;
- Strava tokens, activity caches and ignored-ID lists;
- integration credentials and BYOK provider keys;
- OCR uploads and label photos;
- backups, exports and `.env` files.

The application should not be exposed directly to the public internet without a separately reviewed authentication and reverse-proxy configuration.
