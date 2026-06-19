# Dashboard modules

v0.0.15 migrates dashboard code out of the legacy `static/app.js` monolith.

Rules:
- Keep each module below ~250 lines.
- While `static/app.js` is a classic script, use small `*.global.js` bridge modules before ESM migration.
- Prefer pure model/render helpers.
- Do not add DOM patch wrappers here.
- Do not mutate global state from card modules.
- Keep `/api/food-intel/day` as the current source of truth until `/api/day-dashboard` exists.

Planned split:
- `dashboard.model.js`: pure calculations and view-model shaping.
- `meal-card.global.js`: compact meal card rendering bridge for legacy `static/app.js`.
- `workout-card.global.js`: compact workout card rendering bridge for legacy `static/app.js`.
- `activity-card.js`: future activity card rendering only.
- `weight-card.js`: official/reference weight rendering only.
- `body-card.js`: bioimpedance/body snapshot rendering only.
- `dashboard.render.js`: final layout composition.
