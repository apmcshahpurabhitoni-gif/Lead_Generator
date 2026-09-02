import logging, os, secrets
from contextlib import asynccontextmanager
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from telegram import Update
from bot import create_application
from database import Database
from dashboard_v8 import router as dashboard_router
APP_VERSION="3.6.2"
RELEASE_DATE="2026-09-02"
WHATS_NEW=["🎨 Four selectable dashboard looks: Light Modern, Dark Modern, Light Neo and Dark Neo.","🧹 Removed duplicated and corrupted sales-intelligence cards; the canonical lead data is shown once.","📊 Lead cards now use a clean collapsed/expanded hierarchy with Google, website, phone and email signals.","⚠️ Problems, evidence, recommended services, pitch, links, stage and activity are grouped into readable sections.","📱 Mobile spacing, touch targets and expanded-card animation were redesigned for phone-first use."]
logging.basicConfig(level=logging.INFO,format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"); log=logging.getLogger("leadhunter")
def required(name:str)->str:
 value=os.getenv(name,"").strip()
 if not value: raise RuntimeError(f"Missing required environment variable: {name}")
 return value
def safe_url(url:str)->str:
 parts=url.rstrip("/").split("/"); return "/".join(parts[:-1]+["***"]) if len(parts)>1 else "***"
def routes()->list[str]: return sorted({getattr(r,"path","") for r in app.routes if getattr(r,"path","")})
async def configure_webhook()->dict:
 bot_app=app.state.bot; base=required("WEBHOOK_BASE_URL").rstrip("/"); secret=required("TELEGRAM_WEBHOOK_SECRET"); expected=f"{base}/telegram/webhook/{secret}"; info=await bot_app.bot.get_webhook_info()
 if info.url!=expected: await bot_app.bot.set_webhook(url=expected,secret_token=secret,allowed_updates=["message","callback_query"],max_connections=5,drop_pending_updates=False); info=await bot_app.bot.get_webhook_info()
 app.state.webhook_url=expected; app.state.webhook_configured=info.url==expected; return {"configured":app.state.webhook_configured,"url":safe_url(info.url),"pending_update_count":info.pending_update_count,"last_error_message":info.last_error_message,"last_error_date":info.last_error_date}
async def startup_messages()->None:
 admin=os.getenv("ADMIN_TELEGRAM_ID","").strip()
 if not admin:return
 dashboard_url="https://lead-generator-zzty.onrender.com/dashboard"; started=f"🟢 <b>LEADHUNTER BOT STARTED</b>\n━━━━━━━━━━━━━━━━━━━━\n🤖 Status: <b>ONLINE</b>\n📦 Running Version: <b>v{APP_VERSION}</b>\n📅 Release: <b>{RELEASE_DATE}</b>\n🔗 Telegram: <b>CONNECTED</b>\n✅ Webhook: <b>READY</b>\n📊 Dashboard: <a href=\"{dashboard_url}\">OPEN DASHBOARD</a>"; whats_new=f"🆕 <b>WHAT'S NEW · v{APP_VERSION}</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"+"\n".join(WHATS_NEW)
 try: await app.state.bot.bot.send_message(chat_id=int(admin),text=started,parse_mode="HTML"); await app.state.bot.bot.send_message(chat_id=int(admin),text=whats_new,parse_mode="HTML")
 except Exception: log.exception("Startup messages failed")
@asynccontextmanager
async def lifespan(application:FastAPI):
 application.state.db=Database(); application.state.bot=create_application(application.state.db); application.state.bot.bot_data.update({"version":APP_VERSION,"release_date":RELEASE_DATE,"whats_new":WHATS_NEW}); await application.state.bot.initialize(); await application.state.bot.start(); me=await application.state.bot.bot.get_me(); application.state.bot_identity={"id":me.id,"username":me.username or "","first_name":me.first_name or ""}; await configure_webhook(); await startup_messages(); log.info("LeadHunter startup complete | version=%s",APP_VERSION)
 try: yield
 finally:
  try: await application.state.bot.stop(); await application.state.bot.shutdown()
  except Exception: log.exception("Telegram shutdown failed")
app=FastAPI(title="LeadHunter",version=APP_VERSION,lifespan=lifespan); app.include_router(dashboard_router)
@app.get("/")
async def root(): return {"service":"LeadHunter","status":"online","version":APP_VERSION,"release_date":RELEASE_DATE,"telegram":"webhook","health":"/health","telegram_status":"/telegram/status","version_info":"/version"}
@app.get("/health")
async def health(): return {"ok":True,"service":"leadhunter","version":APP_VERSION,"release_date":RELEASE_DATE}
@app.get("/version")
async def version(): return {"ok":True,"service":"leadhunter","version":APP_VERSION,"release_date":RELEASE_DATE,"whats_new":WHATS_NEW}
@app.get("/__routes")
async def route_list(): return {"ok":True,"version":APP_VERSION,"routes":routes()}
