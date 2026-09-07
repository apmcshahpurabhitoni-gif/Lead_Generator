# LeadHunter v4.1.0

Local Business Discovery & Intelligence Platform.

## Dashboard
Open `/dashboard`. No login or password is required.

The dashboard displays v4.1.0 and uses four themes: Default, Dark, Neo Light and Neo Dark.

## Research Data States
- 🟢 AVAILABLE — verified data is available.
- ❌ NOT_FOUND — checked and no item was found.
- ⚪ NOT_CONFIGURED — future data source is not connected yet.
- ⚠️ FAILED — configured check failed.

LeadHunter never converts unavailable future intelligence into a fake zero or false missing finding.

## Architecture
Dashboard / Telegram → FastAPI → Database → Discovery → Research Worker → Research Normalizer → Scoring → Dashboard / AI Pitch / Outreach.

## Configuration
See .env.example.
Required: SUPABASE_URL and SUPABASE_KEY.

Research Worker is optional. Discovery and dashboard continue to work without it; worker-backed intelligence is shown as NOT_CONFIGURED.

## Run
uvicorn main:app --reload
pytest -q

Version: 4.1.0
Release date: 2026-09-07
