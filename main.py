import logging, os, secrets
from contextlib import asynccontextmanager
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from telegram import Update
from bot import create_application
from database import Database
from dashboard import router as dashboard_router

APP_VERSION="3.0.0"
logging.basicConfig(level=logging.INFO,format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
log=logging.getLogger("leadhunter")

def required(name:str)->str:
    value=os.getenv(name,"").strip()
    if not value: raise RuntimeError(f"Missing required environment variable: {name}")
    return value

def safe_url(url:str)->str:
    parts=url.rstrip("/").split("/")
    return "/".join(parts[:-1]+["***"]) if len(parts)>1 else "***"

def routes()->list[str]: return sorted({getattr(r,"path","") for r in app.routes if getattr(r,"path","")})

async def configure_webhook()->dict:
    bot_app=app.state.bot; base=required("WEBHOOK_BASE_URL").rstrip("/"); secret=required("TELEGRAM_WEBHOOK_SECRET"); expected=f"{base}/telegram/webhook/{secret}"
    info=await bot_app.bot.get_webhook_info()
    if info.url!=expected:
        await bot_app.bot.set_webhook(url=expected,secret_token=secret,allowed_updates=["message","callback_query"],max_connections=5,drop_pending_updates=False)
        info=await bot_app.bot.get_webhook_info()
    app.state.webhook_url=expected; app.state.webhook_configured=(info.url==expected)
    return {"configured":app.state.webhook_configured,"url":safe_url(info.url),"pending_update_count":info.pending_update_count,"last_error_message":info.last_error_message,"last_error_date":info.last_error_date}

async def startup_message()->None:
    admin=os.getenv("ADMIN_TELEGRAM_ID","").strip()
    if not admin: return
    text=f"🟢 <b>LEADHUNTER ONLINE</b>\n━━━━━━━━━━━━━━━━━━━━\n🤖 Status: <b>ONLINE</b>\n📦 Version: <b>v{APP_VERSION}</b>\n🔗 Telegram: <b>CONNECTED</b>\n✅ Webhook: <b>READY</b>"
    try: await app.state.bot.bot.send_message(chat_id=int(admin),text=text,parse_mode="HTML")
    except Exception: log.exception("Startup message failed")

@asynccontextmanager
async def lifespan(application:FastAPI):
    application.state.db=Database(); application.state.bot=create_application(application.state.db)
    await application.state.bot.initialize(); await application.state.bot.start()
    me=await application.state.bot.bot.get_me(); application.state.bot_identity={"id":me.id,"username":me.username or "","first_name":me.first_name or ""}
    await configure_webhook(); await startup_message(); log.info("LeadHunter startup complete | version=%s",APP_VERSION)
    try: yield
    finally:
        try: await application.state.bot.stop(); await application.state.bot.shutdown()
        except Exception: log.exception("Telegram shutdown failed")

app=FastAPI(title="LeadHunter",version=APP_VERSION,lifespan=lifespan)
app.include_router(dashboard_router)

@app.get("/")
async def root(): return {"service":"LeadHunter","status":"online","version":APP_VERSION,"telegram":"webhook","health":"/health","telegram_status":"/telegram/status"}
@app.get("/health")
async def health(): return {"ok":True,"service":"leadhunter","version":APP_VERSION}
@app.get("/__routes")
async def route_list(): return {"ok":True,"version":APP_VERSION,"routes":routes()}
@app.get("/telegram/identity")
async def identity(): return {"ok":True,"version":APP_VERSION,"bot":getattr(app.state,"bot_identity",{})}
@app.get("/telegram/status")
async def telegram_status():
    bot_app=getattr(app.state,"bot",None)
    if not bot_app: return JSONResponse(status_code=503,content={"ok":False,"error":"bot_not_initialized"})
    try:
        info=await bot_app.bot.get_webhook_info(); expected=f"{required('WEBHOOK_BASE_URL').rstrip('/')}/telegram/webhook/{required('TELEGRAM_WEBHOOK_SECRET')}"; repaired=False
        if info.url!=expected: await configure_webhook(); repaired=True; info=await bot_app.bot.get_webhook_info()
        return {"ok":True,"version":APP_VERSION,"url_configured":info.url==expected,"url":safe_url(info.url),"pending_update_count":info.pending_update_count,"last_error_message":info.last_error_message,"last_error_date":info.last_error_date,"self_healed":repaired,"bot":getattr(app.state,"bot_identity",{})}
    except Exception as exc:
        log.exception("Telegram status failed"); return JSONResponse(status_code=503,content={"ok":False,"error":"telegram_status_failed","detail":str(exc)})

@app.post("/telegram/webhook/{path_secret}")
async def telegram_webhook(path_secret:str,request:Request,x_telegram_bot_api_secret_token:str|None=Header(default=None)):
    expected=os.getenv("TELEGRAM_WEBHOOK_SECRET","").strip()
    if not expected or not secrets.compare_digest(path_secret,expected): raise HTTPException(status_code=404,detail="Not found")
    if not x_telegram_bot_api_secret_token or not secrets.compare_digest(x_telegram_bot_api_secret_token,expected): raise HTTPException(status_code=403,detail="Invalid webhook secret")
    update=Update.de_json(await request.json(),app.state.bot.bot)
    log.info("Telegram update RECEIVED | update_id=%s | callback=%s | message=%s",update.update_id,bool(update.callback_query),bool(update.message))
    await app.state.bot.process_update(update)
    return {"ok":True}

@app.api_route("/{path:path}",methods=["GET","POST","PUT","PATCH","DELETE","OPTIONS","HEAD"])
async def unmatched(path:str,request:Request): return JSONResponse(status_code=404,content={"ok":False,"error":"route_not_found","path":"/"+path,"version":APP_VERSION})
