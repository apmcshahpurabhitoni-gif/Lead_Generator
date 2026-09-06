import logging, os, secrets
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request, Response
from bot import create_application
from database import Database
from dashboard import router as dashboard_router
from config import APP_VERSION, RELEASE_DATE, WHATS_NEW
from research_client import worker_status

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
log = logging.getLogger("leadhunter")
REQUIRED = ("TELEGRAM_BOT_TOKEN", "TELEGRAM_WEBHOOK_SECRET", "WEBHOOK_BASE_URL", "SUPABASE_URL", "SUPABASE_KEY", "DASHBOARD_USER", "DASHBOARD_PASSWORD", "RESEARCH_WORKER_URL", "WORKER_API_KEY")

def required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value

def validate_configuration() -> None:
    missing = [name for name in REQUIRED if not os.getenv(name, "").strip()]
    if missing:
        raise RuntimeError("Missing required environment variables: " + ", ".join(missing))

def safe_url(url: str) -> str:
    parts = url.rstrip("/").split("/")
    return "/".join(parts[:-1] + ["***"]) if len(parts) > 1 else "***"

async def configure_webhook(application: FastAPI) -> dict:
    bot_app = application.state.bot
    base = required("WEBHOOK_BASE_URL").rstrip("/")
    secret = required("TELEGRAM_WEBHOOK_SECRET")
    expected = f"{base}/telegram/webhook"
    info = await bot_app.bot.get_webhook_info()
    if info.url != expected:
        await bot_app.bot.set_webhook(url=expected, secret_token=secret, allowed_updates=["message", "callback_query"], max_connections=5, drop_pending_updates=False)
        info = await bot_app.bot.get_webhook_info()
    application.state.webhook_url = expected
    application.state.webhook_configured = info.url == expected
    return {"configured": application.state.webhook_configured, "url": safe_url(info.url)}

async def startup_messages(application: FastAPI) -> None:
    admin = os.getenv("ADMIN_TELEGRAM_ID", "").strip()
    if not admin:
        return
    dashboard_url = os.getenv("DASHBOARD_URL", "").strip() or (required("WEBHOOK_BASE_URL").rstrip("/") + "/dashboard")
    started = ("🟢 <b>LEADHUNTER BOT STARTED</b>\n━━━━━━━━━━━━━━━━━━━━\n" f"🤖 Status: <b>ONLINE</b>\n📦 Version: <b>v{APP_VERSION}</b>\n📅 Release: <b>{RELEASE_DATE}</b>\n🔗 Telegram: <b>CONNECTED</b>\n📊 Dashboard: <a href=\"{dashboard_url}\">OPEN DASHBOARD</a>")
    whats_new = f"🆕 <b>WHAT'S NEW · v{APP_VERSION}</b>\n━━━━━━━━━━━━━━━━━━━━\n\n" + "\n".join(WHATS_NEW)
    try:
        await application.state.bot.bot.send_message(chat_id=int(admin), text=started, parse_mode="HTML")
        await application.state.bot.bot.send_message(chat_id=int(admin), text=whats_new, parse_mode="HTML")
    except Exception:
        log.exception("Startup messages failed")

@asynccontextmanager
async def lifespan(application: FastAPI):
    validate_configuration()
    application.state.db = Database()
    application.state.bot = create_application(application.state.db)
    application.state.bot.bot_data.update({"version": APP_VERSION, "release_date": RELEASE_DATE, "whats_new": WHATS_NEW})
    await application.state.bot.initialize(); await application.state.bot.start()
    me = await application.state.bot.bot.get_me()
    application.state.bot_identity = {"id": me.id, "username": me.username or "", "first_name": me.first_name or ""}
    await configure_webhook(application)
    application.state.worker_status = await worker_status()
    if not application.state.worker_status.get("reachable"):
        log.warning("Research Worker is not reachable: %s", application.state.worker_status)
    await startup_messages(application)
    log.info("LeadHunter startup complete | version=%s", APP_VERSION)
    try: yield
    finally:
        try: await application.state.bot.stop(); await application.state.bot.shutdown()
        except Exception: log.exception("Telegram shutdown failed")

app = FastAPI(title="LeadHunter", version=APP_VERSION, lifespan=lifespan)
app.include_router(dashboard_router)

@app.get("/")
async def root():
    return {"ok": True, "service": "leadhunter", "version": APP_VERSION, "release_date": RELEASE_DATE, "status": "healthy", "health": "/health", "system": "/system/status"}

@app.head("/")
async def root_head(): return Response(status_code=200)

@app.get("/health")
async def health(): return {"ok": True, "service": "leadhunter", "version": APP_VERSION, "status": "healthy"}

@app.get("/system/status")
async def system_status(request: Request):
    worker = await worker_status() if os.getenv("RESEARCH_WORKER_URL", "").strip() else {"configured": False, "reachable": False}
    request.app.state.worker_status = worker
    return {"ok": bool(worker.get("reachable")), "version": APP_VERSION, "database": "configured" if os.getenv("SUPABASE_URL", "").strip() else "missing", "telegram": "ready" if getattr(request.app.state, "bot", None) else "not_ready", "research_worker": worker}

@app.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    expected = os.getenv("TELEGRAM_WEBHOOK_SECRET", "").strip(); header_secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not expected or not secrets.compare_digest(header_secret, expected): raise HTTPException(403, "Invalid Telegram secret token")
    bot_app = getattr(request.app.state, "bot", None)
    if not bot_app: raise HTTPException(503, "Telegram bot is not ready")
    from telegram import Update
    update = Update.de_json(await request.json(), bot_app.bot); await bot_app.update_queue.put(update)
    return {"ok": True}

@app.get("/telegram/status")
async def telegram_status(request: Request):
    return {"ok": True, "configured": all(os.getenv(x, "").strip() for x in ("TELEGRAM_BOT_TOKEN","WEBHOOK_BASE_URL","TELEGRAM_WEBHOOK_SECRET")), "bot_running": bool(getattr(request.app.state, "bot", None)), "webhook_configured": bool(getattr(request.app.state, "webhook_configured", False))}

@app.get("/version")
async def version(): return {"ok": True, "service": "leadhunter", "version": APP_VERSION, "release_date": RELEASE_DATE, "whats_new": WHATS_NEW}
