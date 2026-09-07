# Changelog

## v4.2.0 — 2026-09-07
- Rebuilt the dashboard against the verified backend API contract.
- Replaced free-text discovery inputs with business type, city and lead count dropdowns.
- Fixed dataset loading to use `GET /api/datasets/{search_id}/leads`.
- Fixed discovery to send `category`, `city`, `max_results` and `refresh`.
- Completed real Research, Pitch and Outreach actions.
- Added explicit loading, empty and error states for dashboard data.
- Added four persistent themes: Light Modern, Dark Modern, Light Neo and Dark Neo.
- Kept datasets as business type + city workspaces and reused completed datasets instead of creating duplicate history.

## v4.1.0 — 2026-09-07
- Added canonical future-ready Research Data Contract.
- Added explicit AVAILABLE, NOT_FOUND, NOT_CONFIGURED and FAILED states.
- Added Research Worker response normalization before scoring and persistence.

## v4.0.0 — 2026-09-07
- Dashboard authentication and dataset workflow release.
