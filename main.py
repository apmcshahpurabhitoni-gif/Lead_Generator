import logging,os,secrets
from contextlib import asynccontextmanager
from fastapi import FastAPI,HTTPException,Request,Response
from fastapi.responses import HTMLResponse,RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
from pydantic import BaseModel
from bot import create_application
from database import Database
from dashboard import router as dashboard_router
from config import APP_VERSION
from research_client import worker_status
from auth import validate_auth_config,enabled as auth_enabled,verify_credentials,check_login_rate_limit,create_session
logging.basicConfig(level=logging.INFO); log=logging.getLogger("leadhunter")
class LoginRequest(BaseModel): username:str; password:str
def validate_configuration():
    missing=[x for x in ("SUPABASE_URL","SUPABASE_KEY") if not os.getenv(x,"").strip()]
    if missing: raise RuntimeError("Missing required environment variables: "+", ".join(missing))
    validate_auth_config()
@asynccontextmanager
async def lifespan(app):
    validate_configuration(); app.state.db=Database()
    app.state.service_status={"database":True,"telegram":False,"research_worker":False,"ai_provider":bool(os.getenv("OLLAMA_API_KEY",""))}
    if all(os.getenv(x,"").strip() for x in ("TELEGRAM_BOT_TOKEN","TELEGRAM_WEBHOOK_SECRET","WEBHOOK_BASE_URL")):
        app.state.bot=create_application(app.state.db); await app.state.bot.initialize(); await app.state.bot.start(); app.state.service_status["telegram"]=True
    else: app.state.bot=None
    if os.getenv("RESEARCH_WORKER_URL","").strip():
        app.state.worker_status=await worker_status(); app.state.service_status["research_worker"]=bool(app.state.worker_status.get("reachable"))
    else: app.state.worker_status={"configured":False,"reachable":False}
    try: yield
    finally:
        if getattr(app.state,"bot",None):
            try: await app.state.bot.stop(); await app.state.bot.shutdown()
            except Exception: log.exception("Telegram shutdown failed")
app=FastAPI(title="LeadHunter",version=APP_VERSION,lifespan=lifespan)
app.add_middleware(SessionMiddleware,secret_key=os.getenv("SESSION_SECRET","development-only-change-me"),session_cookie="leadhunter_session",max_age=86400,same_site="lax",https_only=os.getenv("ENVIRONMENT","development").lower()=="production")
app.include_router(dashboard_router)
@app.get("/login",response_class=HTMLResponse,include_in_schema=False)
async def login_page(request:Request):
    if not auth_enabled() or request.session.get("authenticated"): return RedirectResponse("/dashboard",302)
    return HTMLResponse("<!doctype html><html><body><h1>🔎 LeadHunter</h1><form onsubmit='return false'><input id=u placeholder=Username><input id=p type=password placeholder=Password><button onclick=\"fetch('/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:u.value,password:p.value})}).then(r=>r.ok?location='/dashboard':alert('Invalid username or password'))\">Sign In</button></form></body></html>")
@app.post("/auth/login")
async def login(req:LoginRequest,request:Request):
    if not auth_enabled(): return {"ok":True,"authenticated":True}
    check_login_rate_limit(request)
    if not verify_credentials(req.username,req.password): raise HTTPException(401,"Invalid username or password")
    create_session(request,req.username); return {"ok":True,"authenticated":True,"csrf_token":request.session["csrf_token"]}
@app.post("/auth/logout")
async def logout(request:Request): request.session.clear(); return {"ok":True}
@app.get("/auth/status")
async def auth_status(request:Request): return {"authenticated":not auth_enabled() or bool(request.session.get("authenticated")),"username":request.session.get("username"),"csrf_token":request.session.get("csrf_token")}
@app.get("/")
async def root(): return {"ok":True,"service":"leadhunter","version":APP_VERSION}
@app.get("/health")
async def health(): return {"ok":True,"service":"leadhunter","version":APP_VERSION}
@app.get("/system/status")
async def system_status(request:Request): return {"ok":True,"version":APP_VERSION,"services":getattr(request.app.state,"service_status",{})}
@app.post("/telegram/webhook")
async def telegram_webhook(request:Request):
    expected=os.getenv("TELEGRAM_WEBHOOK_SECRET",""); header=request.headers.get("X-Telegram-Bot-Api-Secret-Token","")
    if not expected or not secrets.compare_digest(header,expected): raise HTTPException(403,"Invalid Telegram secret token")
    bot=getattr(request.app.state,"bot",None)
    if not bot: raise HTTPException(503,"Telegram bot is not ready")
    from telegram import Update
    await bot.update_queue.put(Update.de_json(await request.json(),bot.bot)); return {"ok":True}
