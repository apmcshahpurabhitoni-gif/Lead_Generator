import os
APP_VERSION="4.2.0"
RELEASE_DATE="2026-09-07"
WHATS_NEW=[
"🔌 Dashboard rebuilt against verified backend endpoints",
"🔽 Dropdown-based business type, city and lead count discovery",
"📁 Dataset click now loads /api/datasets/{id}/leads",
"🔬 Real Research, Pitch and Outreach actions",
"🎨 Four persistent dashboard themes",
"⚪ Explicit AVAILABLE / NOT FOUND / NOT CONFIGURED intelligence states",
]
ENVIRONMENT=os.getenv("ENVIRONMENT","development")
def version_label(): return f"v{APP_VERSION}"
