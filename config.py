"""Central runtime configuration."""
import os
from constants import CITIES

APP_VERSION = "4.0.0"
RELEASE_DATE = "2026-09-03"
BUSINESS_TIMEZONE = "Asia/Kolkata"
DASHBOARD_URL = os.getenv("DASHBOARD_URL", os.getenv("WEBHOOK_BASE_URL", "http://localhost")).rstrip("/")

WHATS_NEW = [
    "🧭 One canonical lead workflow shared by Dashboard and Telegram.",
    "🛡️ Lead identity now prefers provider IDs and preserves existing contact data.",
    "🔎 Research and scoring no longer fabricate unverified directory or SEO evidence.",
    "📱 Canonical five-section responsive dashboard with four themes.",
    "📨 Telegram webhook receiver and status endpoint are active.",
]

def env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()
