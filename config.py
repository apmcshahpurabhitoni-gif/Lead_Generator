import os
APP_VERSION="4.0.0"
RELEASE_DATE="2026-09-07"
WHATS_NEW=["🔐 Secure dashboard authentication","📁 Dataset-based discovery","🔎 Real job progress and research wiring","✨ AI pitch generation","📊 Real analytics and outreach data"]
ENVIRONMENT=os.getenv("ENVIRONMENT","development")
def version_label(): return f"v{APP_VERSION}"
