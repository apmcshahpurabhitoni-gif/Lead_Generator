# LeadHunter v4.0.0

Local Business Discovery & Intelligence Platform.

## Dashboard
Open `/dashboard`.

- 🏠 Overview
- 🔍 Find Leads
- ◈ Explore persisted discovery datasets
- 📊 Analytics from real database data
- 📤 Outreach pipeline
- 🎨 Four themes
- 📱 Responsive mobile navigation

## Architecture
```text
Dashboard / Telegram
        ↓
      FastAPI
        ↓
 Canonical Database
        ↓
Discovery Workflow
        ↓
Google Places / OSM
        ↓
Persisted Leads + search_results
        ↓
Research Worker Client
        ↓
Research Worker / SearXNG
        ↓
Scoring + Persistence
```

## Data integrity
LeadHunter does not fabricate Google rankings, Maps rankings, review history, owner response rates or website findings. Unavailable intelligence is shown as unavailable.

## Run
```bash
uvicorn main:app --reload
```

Open:
`http://127.0.0.1:8000/dashboard`

## Required configuration
See `.env.example`. Production requires Telegram, Supabase and Research Worker variables configured.

## Important
Dashboard v4 is wired to the canonical `Database`, `lead_workflow`, `discovery` and `research_client` modules. Pitch generation is intentionally unavailable until a real backend implementation exists; the dashboard returns an explicit 501 instead of fake output.

## Testing
```bash
pytest -q
```

**Version:** 4.0.0  
**Release date:** 2026-09-07
