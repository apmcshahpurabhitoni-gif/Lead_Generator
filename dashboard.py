"""LeadHunter Dashboard."""
from fastapi import APIRouter,Request
from fastapi.responses import HTMLResponse
from config import APP_VERSION
from dashboard_ui.api import router as api_router
from dashboard_ui.templates import DASHBOARD_HTML
__APP_VERSION__=APP_VERSION
router=APIRouter()
router.include_router(api_router,prefix="/api")
@router.get("/dashboard",include_in_schema=False)
@router.get("/dashboard/",include_in_schema=False)
async def dashboard(request:Request): return HTMLResponse(DASHBOARD_HTML)
