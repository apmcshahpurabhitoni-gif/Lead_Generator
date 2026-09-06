import os

APP_VERSION = "3.3.0"
RELEASE_DATE = "2026-09-06"
WHATS_NEW = [
    "🔗 LeadHunter now uses the deployed Research Worker for research",
    "🩺 Unified health and system dependency status checks",
    "📊 Clean database-to-dashboard search result wiring",
    "🧹 Consolidated database migration path and runtime hardening",
    "🛡️ Clear production configuration validation and failure messages",
]

def version_label() -> str:
    return f"v{APP_VERSION}"
