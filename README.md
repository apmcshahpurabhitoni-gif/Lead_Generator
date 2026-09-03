# 🚀 LeadHunter

LeadHunter is a private lead-discovery and sales-workspace application for finding businesses, researching publicly available information, scoring sales opportunities, drafting outreach, and managing a simple pipeline.

## Architecture

- **FastAPI** — application and dashboard API
- **Telegram** — bot interface and webhook delivery
- **Supabase/Postgres** — leads, research, activities, jobs, searches and CRM data
- **Google Places** — optional primary discovery provider
- **OpenStreetMap / Overpass** — discovery fallback
- **Website crawler** — robots-aware public website research
- **Ollama Cloud** — optional outreach drafting with a deterministic fallback

Dashboard and Telegram use the same discovery, research, scoring and database workflow. There is no second dashboard implementation.

## Pipeline

`NEW → RESEARCHED → QUALIFIED → CONTACTED → RESPONDED → MEETING → PROPOSAL → NEGOTIATION → WON`

Terminal states: `LOST`, `NOT_INTERESTED`, `DO_NOT_CONTACT`.

Generating a message is an activity, not a pipeline status. Research never downgrades an active CRM status.

## Run locally

1. Create a Python 3.13 environment.
2. Install `requirements.txt`.
3. Copy `.env.example` to `.env` and configure secrets.
4. Apply `schema.sql` to a fresh Supabase/Postgres database.
5. For an existing database, apply the SQL files in `migrations/` in order.
6. Start with:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

## Dashboard

Open `/dashboard`. It is a private Basic-Auth dashboard with five sections:

- Leads
- Find
- Analytics
- Outreach
- Settings

The mobile navigation is a single bottom navigation bar. Four themes are available: Light Modern, Dark Modern, Light Neo and Dark Neo.

## Telegram webhook

Set:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_WEBHOOK_SECRET`
- `WEBHOOK_BASE_URL`
- `ADMIN_TELEGRAM_ID`

The application configures:

`POST /telegram/webhook`

Telegram's `X-Telegram-Bot-Api-Secret-Token` header is verified before an update is queued for python-telegram-bot.

Status is available at:

`GET /telegram/status`

## Discovery

Google Places is used when `GOOGLE_MAPS_API_KEY` is configured. The application paginates provider results up to the requested safety limit where the provider supplies another page. If Google is unavailable or not configured, OSM/Overpass is used.

Provider result position is **not** presented as Google Search/local-pack ranking.

## Research truthfulness

Research distinguishes what was actually observed from what was not checked. Public directory links are reported when the business website publishes them; absence of such a link is not treated as proof that a third-party listing does not exist.

No synthetic research is generated for unresearched leads.

## Database migrations

`schema.sql` is the canonical fresh-install schema.

For an existing production database, use the SQL in `migrations/`. Review any legacy duplicate identities before adding additional uniqueness constraints.

## Tests

Run:

```bash
pytest -q
python -m compileall -q .
```

The dashboard JavaScript can be syntax-checked with Node:

```bash
python - <<'PY'
import re
from pathlib import Path
s=Path("dashboard.py").read_text()
Path("/tmp/dashboard.js").write_text(re.search(r"<script>\n(.*?)\n</script>", s, re.S).group(1))
PY
node --check /tmp/dashboard.js
```

## Render

The included `Procfile` starts the canonical FastAPI application:

`uvicorn main:app --host 0.0.0.0 --port $PORT`

Keep real secrets in Render environment settings, never in Git.
