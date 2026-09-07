"""LeadHunter Dashboard."""
from fastapi import APIRouter,Request
from fastapi.responses import HTMLResponse,RedirectResponse
from config import APP_VERSION
from dashboard_ui.api import router as api_router
from dashboard_ui.templates import DASHBOARD_HTML
from auth import enabled
__APP_VERSION__=APP_VERSION
router=APIRouter()
router.include_router(api_router,prefix="/api")
def dashboard_response(request:Request):
    if enabled() and not request.session.get("authenticated"): return RedirectResponse("/login",302)
    return HTMLResponse(DASHBOARD_HTML)
@router.get("/dashboard",include_in_schema=False)
async def dashboard(request:Request): return dashboard_response(request)
@router.get("/dashboard/",include_in_schema=False)
async def dashboard_slash(request:Request): return dashboard_response(request)
