import os

APP_VERSION = "4.3.0"
RELEASE_DATE = "2026-09-16"
WHATS_NEW = [
    "🧭 Dataset-first dashboard workflow with real API-backed lead loading",
    "🔗 Direct lead opening from Act without guessing a dataset ID",
    "📊 Analytics cards now consume the canonical totals contract",
    "🧩 Outreach records include real lead name, city, industry and contact context",
    "🛡️ Invalid dataset IDs return explicit 404s instead of silent empty states",
    "🧪 Added dashboard API contract regression coverage",
    "🎨 Four persistent dashboard themes retained and isolated from backend logic",
]
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")


def version_label():
    return f"v{APP_VERSION}"
