import os

APP_VERSION = "3.0.0"
RELEASE_DATE = "2026-09-03"
WHATS_NEW = [
    "🔗 Unified Telegram + Dashboard lead workflow",
    "🗄️ Dashboard and Telegram now use the same persisted lead state",
    "📊 Canonical discovery jobs, search results, pipeline statuses and analytics",
    "🔄 Consistent lead status/activity updates across both interfaces",
    "🛡️ Stronger API validation and safer user-facing error handling",
    "🧭 Fixed dashboard search/result wiring and lead-detail data flow",
    "🧪 Wiring-focused validation added before the dashboard UI rebuild",
]

# Runtime configuration is intentionally kept in environment variables.
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
ADMIN_TELEGRAM_ID = os.getenv("ADMIN_TELEGRAM_ID", "").strip()
SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "").strip()
WEBHOOK_BASE_URL = os.getenv("WEBHOOK_BASE_URL", "").strip()
TELEGRAM_WEBHOOK_SECRET = os.getenv("TELEGRAM_WEBHOOK_SECRET", "").strip()
DASHBOARD_USER = os.getenv("DASHBOARD_USER", "").strip()
DASHBOARD_PASSWORD = os.getenv("DASHBOARD_PASSWORD", "").strip()
