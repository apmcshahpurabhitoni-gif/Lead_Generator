"""LeadHunter Dashboard — mounted by main.py at /dashboard."""
from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from config import APP_VERSION
from dashboard_ui.api import router as api_router
from dashboard_ui.templates import DASHBOARD_HTML

__APP_VERSION__ = APP_VERSION
router = APIRouter()
router.include_router(api_router, prefix="/api")

@router.get("/dashboard", response_class=HTMLResponse, include_in_schema=False)
async def dashboard():
    return DASHBOARD_HTML

@router.get("/dashboard/", response_class=HTMLResponse, include_in_schema=False)
async def dashboard_slash():
    return DASHBOARD_HTML
