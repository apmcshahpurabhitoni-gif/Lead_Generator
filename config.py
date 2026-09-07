import os
APP_VERSION="4.1.0"
RELEASE_DATE="2026-09-07"
WHATS_NEW=["🧠 Canonical future-ready research contract","⚪ Clear AVAILABLE / NOT FOUND / NOT CONFIGURED states","🔎 Research Worker normalization","📊 Research intelligence shown on lead cards","🔐 Authentication and startup hardening","🧹 Legacy documentation cleanup"]
ENVIRONMENT=os.getenv("ENVIRONMENT","development")
def version_label(): return f"v{APP_VERSION}"
