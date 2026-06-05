# v0.0.15 refactor rules

## Goal

Move the dashboard away from the legacy `static/app.js` monolith without changing user data or breaking known real days.

## Hard rules

- Do not add new DOM patch wrappers.
- Do not append large emergency blocks to `static/app.js`.
- Keep new JS/CSS modules below ~250 lines.
- Keep card components small and focused.
- Run known-day regression before every commit:
  - `python3 scripts/check_known_days_v015.py`

## Current technical debt

- `static/app.js` is a legacy monolith.
- Multiple historical patches override or wrap dashboard rendering.
- Food Intelligence is currently the safest source for day totals.
- v0.0.15 should migrate in slices, not rewrite everything at once.

## Safe migration order

1. Add guards and tests.
2. Extract pure formatting/date/API helpers.
3. Extract meal-card render helper.
4. Replace only meal card rendering in legacy dashboard.
5. Extract activity, weight and body cards.
6. Add `/api/day-dashboard` only after the UI has stable tests.
