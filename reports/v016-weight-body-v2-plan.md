# Weight & Body Composition 2.0 — first cut

Goal: turn smart-scale and weight records into trend intelligence.

## Added

- `/api/body-trends?days=30`
- `/weight-2`
- Standalone static UI:
  - `static/weight-2.html`
  - `static/weight-2.css`
  - `static/weight-2.js`

## Principles

- Official weight drives trend.
- Reference weight explains context but does not replace official trend.
- Bioimpedance values are trend context, not daily truth.
- BioCharge / Hybrid Charge is recovery context, not a nutrition score.
- No changes to `static/app.js`.

## Next

- Link Weight 2.0 from the main app.
- Add charts instead of table-only series.
- Add weekly comparison cards.
- Add smarter insights using sport, sleep/RHR when available, and nutrition context.
