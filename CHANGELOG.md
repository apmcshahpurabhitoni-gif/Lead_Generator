# Changelog

## v4.3.2 — 2026-09-16
- Added a real dataset dropdown to the Leads workspace so users select datasets instead of typing dataset IDs.
- Dataset selection now loads through the existing `/api/datasets/{search_id}/leads` contract and keeps the active dataset synchronized with the lead list.
- Added compact responsive styling for the dataset selector without changing the locked visual theme system.
- Preserved the direct Act → Lead path and removed the dataset-loading race from that flow.

## v4.3.1 — 2026-09-16
- Registered the Telegram webhook during application startup using `WEBHOOK_BASE_URL` and the configured secret token.
- Added safe Telegram webhook cleanup on application shutdown.
- Passed release date and What's New metadata into the Telegram bot runtime.
- Fixed direct Act → Lead navigation so it cannot be overwritten by an asynchronous dataset load.
- Added API boundary validation for lead IDs, dataset IDs, job IDs and dataset query limits.
- Replaced the mutable outreach services default with a safe Pydantic default factory and bounded notes.
- Extended dashboard JavaScript syntax regression coverage to the separate runtime adapter.

## v4.3.0 — 2026-09-16
- Hardened the dashboard API/UI contract instead of relying on frontend guesses.
- Analytics now exposes canonical nested totals plus explicit flat aliases consumed by the dashboard.
- Dataset lead loading validates the dataset first and returns a clear 404 for an invalid dataset ID.
- Act/Outreach now returns real lead context including name, city, industry and contact fields.
- Act opens a lead directly through `/api/leads/{id}` instead of inventing or guessing a dataset ID.
- Saving an outreach opportunity now fails explicitly if persistence does not return a deal ID.
- Added dashboard contract regression tests for analytics, invalid datasets and outreach context.
- Kept business logic in the existing backend services; the dashboard runtime adapter only handles presentation/API contract compatibility.
- Retained the four locked visual themes: Light Modern, Dark Modern, Light Neo and Dark Neo.

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