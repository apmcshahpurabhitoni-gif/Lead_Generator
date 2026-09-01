# 🚀 LeadHunter

A small personal lead-intelligence system operated mainly through Telegram.

## Locked scope

- Telegram is the primary interface.
- Koyeb Web Service + Telegram webhook keeps the bot online without a local PC.
- Supabase stores businesses, research, activities, Telegram events, follow-ups, deals, jobs and daily statistics.
- Ollama Cloud/Gemma creates explanations and WhatsApp drafts only.
- WhatsApp/email are not sent or tracked by LeadHunter.
- Calls are manually recorded through Telegram.
- The dashboard is a small private history/statistics page at `/dashboard`.
- Discovery uses OpenStreetMap/Overpass for real business candidates. Coverage is incomplete and is not a replacement for Google Maps.
- Website research respects `robots.txt`, limits pages/bytes, caches robots rules in memory, rate-limits requests and backs off on 429s.

## Files

- `main.py` — FastAPI app, Telegram webhook and lifecycle
- `bot.py` — Telegram commands, buttons, statuses, follow-ups and deals
- `discovery.py` — Nominatim city lookup + Overpass business discovery + request budgets
- `research.py` — small robots-aware website audit
- `scoring.py` — deterministic opportunity scoring/service matching
- `ai.py` — Ollama Cloud/Gemma
- `database.py` — all Supabase access
- `dashboard.py` — minimal private dashboard
- `schema.sql` — database schema
- `requirements.txt` — runtime dependencies
- `Procfile` — Koyeb buildpack start command
- `.python-version` — Python runtime

## Supabase

Run `schema.sql` in Supabase SQL Editor. It is safe to run again because tables/indexes use `if not exists` and new columns use `alter table ... add column if not exists`.

## Koyeb

Koyeb supports GitHub-driven FastAPI deployment with a buildpack and a custom run command. Use:

`uvicorn main:app --host 0.0.0.0 --port $PORT`

Required environment variables:

`TELEGRAM_BOT_TOKEN`, `ADMIN_TELEGRAM_ID`, `TELEGRAM_WEBHOOK_SECRET`, `WEBHOOK_BASE_URL`, `SUPABASE_URL`, `SUPABASE_KEY`, `OLLAMA_API_KEY`, `OLLAMA_BASE_URL`, `OLLAMA_MODEL`, `DASHBOARD_USER`, `DASHBOARD_PASSWORD`.

After Koyeb gives you the public `*.koyeb.app` URL, put that exact URL in `WEBHOOK_BASE_URL` and redeploy. The application automatically calls Telegram `setWebhook` at startup using the secret path and Telegram's secret-token header.

## Telegram commands

- `/start`
- `/find <city> <industry>`
- `/hot`
- `/lead <id>`
- `/deal <lead_id> <value> <stage> <service1,service2>`
- `/today`
- `/stats`
- `/followups`

Example:

`/find jabalpur dental`

`/deal 123 55000 PROPOSAL Website,SEO,GBP`

## Tracking

The system records what LeadHunter does and what you explicitly mark: Telegram interactions, call/status actions, follow-ups and deal stages/values.

It does not claim that a WhatsApp/email was sent or that a phone call happened unless you explicitly mark the relevant action in Telegram.

## Discovery safety

The public OpenStreetMap Nominatim service has strict usage rules. LeadHunter uses it only to resolve the requested city and uses Overpass for the actual POI query. It does not systematically download all POIs through Nominatim.

Overpass is a shared public resource. LeadHunter uses small queries, a low request rate, a daily safety budget, a 30-second pause after Overpass 429 responses, and a maximum of 50 candidates per search.

## Research safety

For each business with a website: check robots.txt; research at most 5 pages; reject responses above 1.5 MB; store structured findings instead of full HTML; rate-limit and back off; never bypass CAPTCHAs or access controls.

## Limitation

OpenStreetMap coverage varies by city and industry. A business absent from OSM is not evidence that it does not exist. Additional permitted sources can be added later without changing the Telegram/database architecture.
