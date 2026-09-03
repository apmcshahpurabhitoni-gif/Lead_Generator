"""Runtime compatibility patch for the dashboard HTML shipped in older builds.

This is intentionally tiny and self-contained: Python imports sitecustomize during
startup, so the legacy duplicate DOM id is corrected before FastAPI serves PAGE.
"""

try:
    import dashboard

    page = dashboard.PAGE
    page = page.replace(
        '<div id="leads" class="leads"><div class="empty">Loading leads…</div></div>',
        '<div id="leadlist" class="leads"><div class="empty">Loading leads…</div></div>',
    )
    page = page.replace('$("leads").innerHTML=', '$("leadlist").innerHTML=')
    dashboard.PAGE = page
except Exception:
    # Never prevent the application from starting because of this compatibility shim.
    pass
