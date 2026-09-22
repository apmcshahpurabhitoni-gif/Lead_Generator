# LeadHunter v4.4.0

Local Business Discovery & Intelligence Platform.

## Dashboard
Open `/dashboard`. No login or password is required.

## Mobile Dashboard
Open `/m` (also at `/dashboard/m`) for the mobile-first experience. It is a
two-thumb, app-like workspace over the exact same `/dashboard/api/*` contract:

- **Home** — live metric tiles, recent datasets, one-tap access to Find and Act, service health.
- **Leads** — swipeable dataset chips, instant search, All/Hot/Researched filters, tap-to-open lead bottom sheet with Call / WhatsApp / Email / Website actions plus Research, Pitch and Save-to-Act.
- **Find** — business type, city and lead-count pickers with a live discovery progress bar.
- **Stats** — lead totals and city/service bar charts.
- **Act** — saved opportunities and due follow-ups, each opening its lead directly.

The mobile dashboard shares the desktop's four locked themes
(Light Modern, Dark Modern, Light Neo, Dark Neo) and remembers the choice.
A 📱 button on the desktop topbar jumps to `/m`; the mobile app bar links back.

The desktop dashboard is dataset-first: choose a business type and city, run
discovery, then use the Leads workspace dataset dropdown to select a completed
dataset. Its lead records load directly without typing internal IDs. Lead
cards are collapsed by default and expand to show the available business
record and actions.

Four locked visual themes are retained: Light Modern, Dark Modern, Light Neo and Dark Neo.

## Runtime wiring
- Dashboard UI calls the real `/dashboard/api/*` contract.
- Dataset selection resolves through `/dashboard/api/datasets/{id}/leads`.
- The Leads workspace provides a real dataset dropdown; changing it reloads the selected dataset's lead records.
- Lead actions resolve through `/dashboard/api/leads/{id}` and its research/pitch endpoints.
- Act/Outreach resolves saved opportunities back to the first-class lead record.
- Telegram uses `/telegram/webhook`; startup registers the webhook against `WEBHOOK_BASE_URL` and verifies requests with `TELEGRAM_WEBHOOK_SECRET`.
- Application shutdown removes the Telegram webhook cleanly.

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
Required (Keys tab): `SUPABASE_URL` plus one Supabase API key —
`SUPABASE_SERVICE_ROLE_KEY` (recommended, server-side) or `SUPABASE_ANON_KEY`.
The legacy `SUPABASE_KEY` alias is still accepted.
Telegram webhook runtime additionally requires `TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_SECRET` and `WEBHOOK_BASE_URL`.

Research Worker is optional. Discovery and dashboard continue to work without it; worker-backed intelligence is shown as NOT_CONFIGURED.

## Run
```bash
uvicorn main:app --reload
pytest -q
```

Version: 4.4.0  
Release date: 2026-09-22