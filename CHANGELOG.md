# Changelog

## v3.1.0 — 2026-09-06

### Dashboard
- Consolidated the production dashboard into `dashboard.py`.
- Removed the temporary runtime page override architecture.
- Kept lead cards, discovery, analytics, outreach and settings in one workspace.
- All dashboard data is loaded from canonical API endpoints.

### Wiring
- Dashboard and Telegram share canonical persisted lead state.
- Dashboard URL is configurable with `DASHBOARD_URL`.
- Research Worker configuration is documented in `.env.example`.

### Validation
- Python compilation checked.
- Existing repository tests retained and executed.
