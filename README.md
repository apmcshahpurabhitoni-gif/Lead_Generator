# LeadHunter v4.3.0

Local Business Discovery & Intelligence Platform.

## Dashboard
Open `/dashboard`. No login or password is required.

The dashboard displays v4.3.0 and uses four themes: Light Modern, Dark Modern, Light Neo and Dark Neo.

The dashboard workflow is dataset-first: choose a business type and city, run discovery, select a completed dataset, and its lead records load directly without typing internal IDs. Lead cards are collapsed by default and expand to show the available business record and actions.

## Research Data States
- 🟢 AVAILABLE — verified data is available.
- ❌ NOT_FOUND — checked and no item was found.
- ⚪ NOT_CONFIGURED — future data source is not connected yet.
- ⚠️ FAILED — configured check failed.

LeadHunter never converts unavailable future intelligence into a fake zero or false missing finding.

## Architecture
Dashboard / Telegram → FastAPI → Database → Discovery → Research Worker → Research Normalizer → Scoring → Dashboard / AI Pitch / Outreach.

## Dashboard Contract
- `/dashboard/api/health` — service health
- `/dashboard/api/overview` — dashboard metrics and recent datasets
- `/dashboard/api/datasets` — discovery datasets
- `/dashboard/api/datasets/{id}/leads` — all leads belonging to a dataset
- `/dashboard/api/leads/{id}` — first-class lead detail
- `/dashboard/api/leads/{id}/research` — run research and scoring
- `/dashboard/api/leads/{id}/pitch` — generate outreach pitch
- `/dashboard/api/analytics` — canonical analytics plus flat UI aliases
- `/dashboard/api/outreach` — saved opportunities with lead context

## Configuration
See `.env.example`.
Required: `SUPABASE_URL` and `SUPABASE_KEY`.

Research Worker is optional. Discovery and dashboard continue to work without it; worker-backed intelligence is shown as NOT_CONFIGURED.

## Run
```bash
uvicorn main:app --reload
pytest -q
```

Version: 4.3.0  
Release date: 2026-09-16
