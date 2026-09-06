# LeadHunter v3.3.0

LeadHunter is a production-oriented Telegram + FastAPI lead-intelligence workspace. Telegram and the dashboard share one canonical Supabase-backed state for leads, research, discovery jobs, search results, activities, follow-ups and deals.

## Architecture

```text
Telegram ─┐
          ├──> Canonical Lead Workflow
Dashboard ┘          │
                     ▼
          Discovery → Research → Scoring → Persistence
                     │
          ┌──────────┴──────────┐
          ▼                     ▼
       Telegram              Dashboard
```

## Dashboard

One production dashboard source is served from `dashboard.py`.

- Lead overview and pipeline metrics
- Saved searches and result sets
- Live discovery jobs
- Collapsible lead intelligence cards
- Lead scoring evidence and recommended services
- Analytics and opportunity concentration
- Outreach queue
- Pitch generation
- Telegram lead handoff
- Pipeline status updates
- Light, dark and Neo workspace themes

## Required environment

```text
TELEGRAM_BOT_TOKEN
ADMIN_TELEGRAM_ID
WEBHOOK_BASE_URL
SUPABASE_URL
SUPABASE_KEY
DASHBOARD_USER
DASHBOARD_PASSWORD
```

Optional integrations are documented in `.env.example`, including Google Maps and the deployed Research Worker.

## Validation

```bash
pytest -q
python -m compileall -q .
```

## Release v3.3.0

- Added Render-compatible GET/HEAD health checks for reliable deployment health probes.
- Updated the dashboard and documentation release version to 3.3.0.
- Consolidated dashboard runtime into one canonical source.
- Removed temporary dashboard override architecture.
- Dashboard URL is environment-configurable.
- Unified dashboard API and persisted lead state.
- Discovery, search results, analytics, outreach and lead actions use the same backend data.
- Research Worker integration settings documented.


## v3.3.0 Architecture
LeadHunter delegates research to the separately deployed Research Worker using `RESEARCH_WORKER_URL`, `WORKER_API_KEY`, and `RESEARCH_WORKER_PATH`. The production flow is Discovery → Research Worker → Scoring → Supabase → Dashboard.
