# API

All `/api/*` routes require authentication except `/api/auth/login`, `/api/auth/logout`, `/api/auth/status`
(`{mode, authenticated}`) and the Strava OAuth callback.

### Core

- `GET /health`
- `GET /api/state`
- `GET /api/insights/today`
- `POST /api/meals` · `PUT /api/meals/<id>` · `POST /api/meals/<id>/duplicate` · `DELETE /api/meals/<id>`
- `POST /api/foods` · `DELETE /api/foods/<id>`
- `POST /api/weights` · `PUT /api/weights/<id>` · `DELETE /api/weights/<id>`
- `POST /api/workouts` · `DELETE /api/workouts/<id>`

### Goals and progress

- `GET /api/profile` · `PUT /api/profile`
- `GET /api/analytics/overview?days=60`
- `GET /api/analytics/tdee`

### Data

- `GET /api/backup` · `POST /api/backup` · `GET /api/backup/download`
- `GET /api/export/meals.csv` · `weights.csv` · `workouts.csv`
- `GET /api/export` *(JSON)*

### Food database and AI

- `GET /api/foods/barcode/<code>`
- `GET /api/foods/search-online?q=...`
- `GET /api/ai/status` · `POST /api/ai/coach` · `POST /api/ai/label`

### Food Intelligence and Smart Coach

- `GET /api/food-intel/day`
- `POST /api/food-intel/meal-plan`
- `GET /api/food-intel/health`
- `GET /api/smart-coach/day`
- `POST /api/smart-coach/alternative`
- `POST /api/smart-coach/unavailable`

### Pantry

- `GET /api/pantry`
- `POST /api/pantry`
- `GET /api/pantry/v2`
- `POST /api/pantry/v2`

### Activity planning

- `GET /api/activity-plan`
- `POST /api/activity-plan`
- `PUT /api/activity-plan/<id>`
- `DELETE /api/activity-plan/<id>`

### Body composition

- `GET /api/body-snapshot/latest`
- `GET /api/body-trends?days=45`

### Strava

- `GET /api/strava/status`
- `POST /api/strava/preview`
- `POST /api/strava/import`
- `GET /api/strava/auto-status`
- `POST /api/strava/auto-config`
- `POST /api/strava/auto-run`
- `GET /api/integrations/strava/config`
- `POST /api/integrations/strava/config`
- `GET /api/integrations/strava/diagnostics`
- `POST /api/integrations/strava/test`
- `POST /api/integrations/strava/disconnect`
