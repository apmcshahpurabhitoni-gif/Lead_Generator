"""Apply dashboard compatibility fixes after the dashboard router is imported."""

import dashboard
from dashboard_page1 import PAGE as OVERVIEW_PAGE

# Page-by-page dashboard rebuild: Page 1 is the new Overview. Keep the existing
# backend/API routes in dashboard.py untouched so later pages can be rebuilt
# incrementally without changing the data layer.
dashboard.PAGE = OVERVIEW_PAGE
