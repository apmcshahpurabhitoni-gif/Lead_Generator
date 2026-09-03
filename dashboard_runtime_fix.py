"""Apply mandatory compatibility fixes to the embedded dashboard HTML.

Loaded explicitly by main.py after dashboard is imported, so this does not depend on
Python's optional sitecustomize startup hook.
"""

import dashboard


_LEGACY = '<div id="leads" class="leads"><div class="empty">Loading leads…</div></div>'
_FIXED = '<div id="leadlist" class="leads"><div class="empty">Loading leads…</div></div>'

page = dashboard.PAGE.replace(_LEGACY, _FIXED)
page = page.replace('$("leads").innerHTML=', '$("leadlist").innerHTML=')

# Make the dashboard resilient if an unexpected client-side element lookup fails.
page = page.replace(
    'function renderLeads(){let x=rows();$("leadlist").innerHTML=',
    'function renderLeads(){let x=rows();let el=$("leadlist");if(!el)return;el.innerHTML=',
)

dashboard.PAGE = page
