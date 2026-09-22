import os

APP_VERSION = "4.4.0"
RELEASE_DATE = "2026-09-22"
WHATS_NEW = [
    "📱 New mobile dashboard at /m — a pocket-sized LeadHunter workspace",
    "🏠 Mobile Home with live metrics, recent datasets and service health",
    "▤ Leads tab: dataset chips, search, filters and tap-to-open lead sheets",
    "📞 One-tap Call / WhatsApp / Email / Website actions on every lead",
    "⌕ Research, Pitch and Save-to-Act actions run right from the sheet",
    "⌕ Full discovery flow with live job progress on mobile",
    "◫ Stats tab with lead totals and city/service charts",
    "◐ Same four-theme system: Light/Dark × Modern/Neo, remembered locally",
]
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")


def version_label():
    return f"v{APP_VERSION}"