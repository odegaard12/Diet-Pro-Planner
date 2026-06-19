# Diet Pro Planner v0.0.21 — Full modern UI

## Approved visual direction

The isolated prototype in PR #29 is the visual source of truth.

Keep:

- warm off-white background;
- compact dark navigation;
- strong typography and generous whitespace;
- action-first Smart Coach;
- compact metric cards;
- responsive mobile bottom navigation;
- no floating desktop action dock;
- no oversized admin-dashboard blocks.

Change:

- replace the green accent with a cobalt/indigo palette that matches the app icon;
- use orange only for races, warnings and attention states;
- preserve semantic green for success only.

## Migration strategy

The production root `/` stays on v0.0.20 until the complete UI is approved.

The new UI is implemented and reviewed at `/v021` with real local APIs. The final commit will switch `/` only after desktop and mobile review.

## Pages to migrate

1. Today dashboard.
2. Quick meal registration.
3. Smart Coach and pantry actions.
4. Sport registration and activity history.
5. Planned versus real activity.
6. Templates.
7. Foods, products and OCR.
8. Editable pantry.
9. Weekly meal plan.
10. Weight and body composition.
11. Strava integrations.
12. Complete history.

## Acceptance criteria

- All current workflows remain available.
- No private data is added to Git.
- Existing SQLite schema remains compatible.
- Desktop and mobile are reviewed page by page.
- No growth in legacy `static/app.js` or `static/styles.css`.
- New frontend code lives under `static/v021/`.
- CI, privacy guard, known-day checks and Docker smoke pass.
- PR remains draft until every page is approved.
