APP_VERSION = "4.0.0"
RELEASE_DATE = "2026-09-07"
WHATS_NEW = [
    "🎨 Dashboard 4.0 with four themes and responsive navigation",
    "🔌 Dashboard wired to canonical Database, discovery and Research Worker services",
    "📁 Discovery datasets use persisted jobs and authoritative search_results",
    "🔎 Lead research now loads the real business record before calling the worker",
    "🛡️ Unimplemented features return explicit status instead of fake data",
]
def version_label() -> str:
    return f"v{APP_VERSION}"
