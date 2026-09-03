# LeadHunter

LeadHunter is a Telegram + FastAPI lead-intelligence application. Telegram and the dashboard share one canonical Supabase-backed lead, research, search-job, activity, deal and follow-up state.

## Architecture

- **FastAPI** — application, webhook and dashboard API
- **Telegram** — bot interface and lead actions
- **Supabase** — canonical persisted application state
- **Discovery → Research → Scoring → Persistence** — canonical lead workflow
- **Dashboard** — reads and mutates the same persisted state used by Telegram

## Runtime

The included `Procfile` starts the canonical FastAPI application.

## Validation

Run:

```bash
pytest -q
python -m compileall -q .
```

## Release

Current release: **v3.0.0** — unified Telegram + Dashboard wiring.

### What's new in v3.0.0

- Unified Telegram and dashboard lead workflow.
- Canonical persisted lead/search/job/pipeline state.
- Consistent status and activity updates across interfaces.
- Dashboard discovery and lead-detail APIs use the same workflow/database layer.
- Stronger validation and safer application-level error handling.
- Wiring-focused validation before the dashboard UI rebuild.
