import logging, os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from bot import create_application
from database import Database
from dashboard import router as dashboard_router

APP_VERSION = "3.8.0"
RELEASE_DATE = "2026-09-03"
WHATS_NEW = [
    "🧭 Rebuilt the dashboard as one canonical workspace instead of stacked dashboard versions.",
    "⚡ Faster lead loading with batched research reads instead of one database request per lead.",
    "💾 Saved searches now have durable result membership.",
    "📱 Mobile-first five-page navigation: Leads, Find, Analytics, Outreach and Settings.",
    "🎨 Light Modern, Dark Modern, Light Neo and Dark Neo remain available in Settings.",
    "📨 Lead details can be sent directly to the configured Telegram admin.",
]

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
log = logging.getLogger("leadhunter")


def required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def safe_url(url: str) -> str:
    parts = url.rstrip("/").split("/")
    return "/".join(parts[:-1] + ["***"]) if len(parts) > 1 else "***"


def routes() -> list[str]:
    return sorted({getattr(r, "path", "") for r in app.routes if getattr(r, "path", "")})


async def configure_webhook() -> dict:
    bot_app = app.state.bot
    base = required("WEBHOOK_BASE_URL").rstrip("/")
    secret = required("TELEGRAM_WEBHOOK_SECRET")
    expected = f"{base}/telegram/webhook/{secret}"
    info = await bot_app.bot.get_webhook_info()
    if info.url != expected:
        await bot_app.bot.set_webhook(
            url=expected,
            secret_token=secret,
            allowed_updates=["message", "callback_query"],
            max_connections=5,
            drop_pending_updates=False,
        )
        info = await bot_app.bot.get_webhook_info()
    app.state.webhook_url = expected
    app.state.webhook_configured = info.url == expected
    return {
        "configured": app.state.webhook_configured,
        "url": safe_url(info.url),
        "pending_update_count": info.pending_update_count,
        "last_error_message": info.last_error_message,
        "last_error_date": info.last_error_date,
    }


async def startup_messages() -> None:
    admin = os.getenv("ADMIN_TELEGRAM_ID", "").strip()
    if not admin:
        return
    dashboard_url = "https://lead-generator-zzty.onrender.com/dashboard"
    started = (
        "🟢 <b>LEADHUNTER BOT STARTED</b>\n━━━━━━━━━━━━━━━━━━━━\n"
        f"🤖 Status: <b>ONLINE</b>\n📦 Running Version: <b>v{APP_VERSION}</b>\n"
        f"📅 Release: <b>{RELEASE_DATE}</b>\n🔗 Telegram: <b>CONNECTED</b>\n"
        f"✅ Webhook: <b>READY</b>\n📊 Dashboard: <a href=\"{dashboard_url}\">OPEN DASHBOARD</a>"
    )
    whats_new = f"🆕 <b>WHAT'S NEW · v{APP_VERSION}</b>\n━━━━━━━━━━━━━━━━━━━━\n\n" + "\n".join(WHATS_NEW)
    try:
        await app.state.bot.bot.send_message(chat_id=int(admin), text=started, parse_mode="HTML")
        await app.state.bot.bot.send_message(chat_id=int(admin), text=whats_new, parse_mode="HTML")
    except Exception:
        log.exception("Startup messages failed")


@asynccontextmanager
async def lifespan(application: FastAPI):
    application.state.db = Database()
    application.state.bot = create_application(application.state.db)
    application.state.bot.bot_data.update({"version": APP_VERSION, "release_date": RELEASE_DATE, "whats_new": WHATS_NEW})
    await application.state.bot.initialize()
    await application.state.bot.start()
    me = await application.state.bot.bot.get_me()
    application.state.bot_identity = {"id": me.id, "username": me.username or "", "first_name": me.first_name or ""}
    await configure_webhook()
    await startup_messages()
    log.info("LeadHunter startup complete | version=%s", APP_VERSION)
    try:
        yield
    finally:
        try:
            await application.state.bot.stop()
            await application.state.bot.shutdown()
        except Exception:
            log.exception("Telegram shutdown failed")


app = FastAPI(title="LeadHunter", version=APP_VERSION, lifespan=lifespan)
app.include_router(dashboard_router)


@app.get("/")
async def root():
    return {"service": "LeadHunter", "status": "online", "version": APP_VERSION, "release_date": RELEASE_DATE, "telegram": "webhook", "health": "/health", "telegram_status": "/telegram/status", "version_info": "/version"}


@app.get("/health")
async def health():
    return {"ok": True, "service": "leadhunter", "version": APP_VERSION, "release_date": RELEASE_DATE}


@app.get("/version")
async def version():
    return {"ok": True, "service": "leadhunter", "version": APP_VERSION, "release_date": RELEASE_DATE, "whats_new": WHATS_NEW}


@app.get("/__routes")
async def route_list():
    return {"ok": True, "version": APP_VERSION, "routes": routes()}
