# 🚀 LeadHunter

Simple online lead discovery and sales tracking system.

## Runtime

- FastAPI + Telegram webhook
- Supabase storage
- OpenStreetMap Nominatim + Overpass discovery
- Website research with robots.txt checks
- Deterministic lead scoring
- Optional Ollama Cloud message drafts
- Minimal private dashboard
- Designed for Render web service deployment

## Telegram

Commands: `/start`, `/help`, `/find CITY INDUSTRY`, `/lead ID`, `/hot`, `/today`, `/stats`, `/followups`.

The button menu covers business categories, discovery, lead audit, message drafting, calls, follow-ups, statuses, history and deals.

WhatsApp and email are manual only. LeadHunter does not automatically send or track them.

## Required environment

See `.env.example`. Keep all real secrets only in the Render environment settings.

## Render

Start command is defined by `Procfile`:

`uvicorn main:app --host 0.0.0.0 --port $PORT`

The application configures its Telegram webhook on startup and does not delete the webhook during normal shutdown. `/telegram/status` checks and self-heals the webhook.

## Supabase

Run `schema.sql` once in the Supabase SQL editor. It is idempotent and will not drop existing data.
