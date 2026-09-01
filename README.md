# LeadHunter 🚀

A simple personal lead-intelligence system operated through Telegram, with a small private dashboard for history and statistics.

## Locked scope

- Telegram is the primary operating interface.
- Small private dashboard for daily history/statistics.
- Supabase stores businesses, research, activities, Telegram events, follow-ups, and daily statistics.
- Ollama Cloud/Gemma generates explanations and WhatsApp message drafts.
- WhatsApp/email are not sent or tracked by LeadHunter.
- Calls are manually recorded through Telegram.
- Every important LeadHunter action is logged.
- Discovery uses compliant/allowed APIs or public sources only; no Google/Maps HTML scraping or CAPTCHA bypass.
- Per-source budgets, delays, caching and backoff are mandatory before a real provider is connected.

## Files

- `main.py` — runtime entry point
- `bot.py` — Telegram interface and user actions
- `discovery.py` — discovery source interface and rate controls
- `research.py` — website research and audit
- `scoring.py` — deterministic scoring and service matching
- `ai.py` — Ollama Cloud/Gemma integration
- `database.py` — Supabase data access
- `scheduler.py` — lightweight scheduled reminders
- `dashboard.py` — minimal dashboard
- `schema.sql` — Supabase schema
- `requirements.txt` — Python dependencies
- `.env.example` — required environment variable names
- `render.yaml` — deployment configuration

## Important deployment note

A free Render web service is not a reliable permanent worker for Telegram long-polling. The code therefore keeps Telegram, dashboard/API, and scheduling concerns separated so deployment can use an online host arrangement that actually supports a persistent bot process. Do not assume the free web-service plan alone will keep polling alive 24/7.

## Setup

1. Create a Supabase project.
2. Run `schema.sql` in the Supabase SQL editor.
3. Create a Telegram bot with BotFather.
4. Set environment variables from `.env.example`.
5. Configure Ollama Cloud credentials/model.
6. Implement and configure at least one approved discovery provider before using `/find`.

## Telegram commands

- `/start`
- `/help`
- `/find <city> <industry>`
- `/hot`
- `/lead <id>`
- `/today`
- `/stats`
- `/followups`

## Status flow

`NEW → RESEARCHED → QUALIFIED → CONTACTED → RESPONDED → MEETING → PROPOSAL → NEGOTIATION → WON`

Alternative outcomes: `LOST`, `NOT_INTERESTED`, `DO_NOT_CONTACT`.

## Tracking rules

LeadHunter distinguishes:

- message generated vs. user-marked contacted
- Telegram message sent vs. user interaction with the lead
- call intent vs. user-confirmed call outcome

The system never claims a WhatsApp/email was sent, a phone conversation occurred, or a Telegram message was read unless the user explicitly records the event.

## Rate-limit rules

Provider-specific request limits must come from the provider's current documentation. LeadHunter uses configurable request budgets, minimum delays, 429 handling, bounded retries, and caching. Never add a source by guessing its limits.
