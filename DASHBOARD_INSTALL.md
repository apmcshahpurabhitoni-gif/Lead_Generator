# LeadHunter Dashboard 4.0 — Quick Guide

## Install
Copy `dashboard.py` and the `dashboard_ui` folder into the repository root.

## Test locally
```bash
uvicorn dashboard:app --reload
```

Open:
`http://127.0.0.1:8000`

## If main.py already runs FastAPI
Mount or import the dashboard app/router according to the existing app structure. Do not run two servers on the same Render service.

## Before deployment
1. Keep existing `database.py`, `lead_workflow.py`, `research_client.py`.
2. Test `/api/health`.
3. Test Find Leads.
4. Test Explore.
5. Verify Research Worker environment variables are configured.

## Important
The dashboard intentionally shows unavailable intelligence instead of fake Google/review/ranking data.
