import os

APP_VERSION = "4.3.1"
RELEASE_DATE = "2026-09-16"
WHATS_NEW = [
    "🔌 Telegram webhook is now registered and verified during application startup",
    "🧹 Telegram webhook lifecycle is cleaned up safely on shutdown",
    "🧭 Direct Act → Lead navigation no longer races dataset loading",
    "🛡️ Dashboard IDs and query limits are validated at the API boundary",
    "📦 Outreach request validation now uses safe defaults and bounded notes",
    "🧪 JavaScript syntax coverage now includes the runtime adapter as well as the embedded dashboard",
]
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")


def version_label():
    return f"v{APP_VERSION}"
