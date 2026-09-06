"""
LeadHunter Dashboard 4.0
Run: mounted by main.py or directly with `uvicorn dashboard:app`.
"""
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from dashboard_ui.api import router
from dashboard_ui.templates import DASHBOARD_HTML

app = FastAPI(title="LeadHunter Dashboard", version="4.0.0")
app.include_router(router, prefix="/api")

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    return DASHBOARD_HTML
