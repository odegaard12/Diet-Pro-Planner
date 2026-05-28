# Diet Pro Planner

**Current version:** v0.0.3

Local-first web app for tracking body weight, meals by grams, reusable foods, meal templates, workouts, weekly plans and optional integrations.

Designed to run privately on a Raspberry Pi with Docker. Personal data stays local.

## Features

- Official and reference weight tracking.
- Meal logging by saved foods and grams.
- Reusable meal templates where quantities can be adjusted before saving.
- Product catalog with brand, nutrition values and optional local label photo.
- Manual workout logging.
- Strava OAuth connection.
- Manual Strava import by date range.
- Optional auto-load of Strava activity previews when opening the integration page.
- Duplicate prevention for imported Strava activities.
- Spanish/English UI toggle.
- Local app icon and browser favicon.
- Local SQLite database in `data/dieta.db`.

## Privacy

Do not commit local/private files. The repository excludes them through `.gitignore`:

- `data/`
- `*.db`
- `*.sqlite`
- `.env`
- tokens
- backups
- ZIP files
- local label photos

Strava tokens are stored locally under `data/` and are not committed.

## Docker

```bash
docker compose up -d --build
```

Default local URL:

```text
http://localhost:8099
```

## Strava local setup

Diet Pro Planner can connect to Strava without exposing the Raspberry Pi to the internet.

Recommended local OAuth flow:

1. Create a Strava API application.
2. Set the website to `http://localhost:8099`.
3. Set the authorization callback domain to `localhost`.
4. Store `STRAVA_CLIENT_ID`, `STRAVA_CLIENT_SECRET` and `STRAVA_REDIRECT_URI` in the local `.env` file.
5. Open an SSH tunnel from your computer to the Raspberry Pi:

```bash
ssh -N -L 8099:127.0.0.1:8099 user@raspberry-ip
```

6. Open `http://localhost:8099`.
7. Go to `Integrations -> Strava -> Connect Strava`.

## Strava import workflow

No background sync is performed by default.

The integration page supports:

- choose start date
- choose end date
- search activities
- review activities before importing
- select all / select none
- import selected activities
- avoid duplicates
- optionally load activity previews automatically when opening the page
- start from the last imported Strava date

## Releases

- `v0.0.1`: first clean public release.
- `v0.0.2`: manual Strava import by date range.
- `v0.0.3`: app icon, bilingual UI toggle and Strava auto-preview option.
