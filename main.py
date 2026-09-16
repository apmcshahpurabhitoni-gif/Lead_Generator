import logging, os, secrets
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from bot import create_application, notify_bot_started
from config import APP_VERSION, RELEASE_DATE, WHATS_NEW
from dashboard import router as dashboard_router
from database import Database
from research_client import worker_status

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
log = logging.getLogger("leadhunter")


def validate_configuration():
    missing = [x for x in ("SUPABASE_URL", "SUPABASE_KEY") if not os.getenv(x, "").strip()]
    if missing:
        raise RuntimeError("Missing required environment variables: " + ", ".join(missing))


@asynccontextmanager
async def lifespan(app):
    validate_configuration()
    app.state.db = Database()
    app.state.service_status = {
        "database": True,
        "telegram": False,
        "research_worker": False,
        "ai_provider": bool(os.getenv("OLLAMA_API_KEY", "")),
    }

    telegram_configured = all(
        os.getenv(x, "").strip()
        for x in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_WEBHOOK_SECRET", "WEBHOOK_BASE_URL")
    )
    if telegram_configured:
        app.state.bot = create_application(app.state.db)
        app.state.bot.bot_data.update(
            {"version": APP_VERSION, "release_date": RELEASE_DATE, "whats_new": WHATS_NEW}
        )
        await app.state.bot.initialize()
        await app.state.bot.start()

        base_url = os.getenv("WEBHOOK_BASE_URL", "").strip().rstrip("/")
        webhook_url = f"{base_url}/telegram/webhook"
        secret = os.getenv("TELEGRAM_WEBHOOK_SECRET", "").strip()
        try:
            await app.state.bot.bot.set_webhook(
                url=webhook_url,
                secret_token=secret,
                drop_pending_updates=False,
            )
            app.state.service_status["telegram"] = True
            log.info("Telegram webhook configured: %s", webhook_url)
            await notify_bot_started(app.state.bot)
        except Exception:
            log.exception("Telegram webhook configuration failed")
            await app.state.bot.stop()
            await app.state.bot.shutdown()
            app.state.bot = None
            raise RuntimeError("Telegram webhook could not be configured")
    else:
        app.state.bot = None

    app.state.worker_status = await worker_status()
    app.state.service_status["research_worker"] = bool(app.state.worker_status.get("reachable"))

    try:
        yield
    finally:
        if app.state.bot:
            try:
                await app.state.bot.bot.delete_webhook(drop_pending_updates=False)
            except Exception:
                log.exception("Telegram webhook cleanup failed")
            try:
                await app.state.bot.stop()
                await app.state.bot.shutdown()
            except Exception:
                log.exception("Telegram shutdown failed")


app = FastAPI(title="LeadHunter", version=APP_VERSION, lifespan=lifespan)
app.include_router(dashboard_router)


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def root():
    return RedirectResponse("/dashboard", status_code=307)


@app.get("/health")
async def health():
    return {"ok": True, "service": "leadhunter", "version": APP_VERSION}


@app.get("/system/status")
async def system_status(request: Request):
    return {
        "ok": True,
        "version": APP_VERSION,
        "services": getattr(request.app.state, "service_status", {}),
        "worker": getattr(request.app.state, "worker_status", {}),
    }


@app.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    expected = os.getenv("TELEGRAM_WEBHOOK_SECRET", "")
    header = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not expected or not secrets.compare_digest(header, expected):
        raise HTTPException(403, "Invalid Telegram secret token")
    bot = getattr(request.app.state, "bot", None)
    if not bot:
        raise HTTPException(503, "Telegram bot is not ready")
    from telegram import Update

    update = Update.de_json(await request.json(), bot.bot)
    if update is None:
        raise HTTPException(400, "Invalid Telegram update")
    await bot.update_queue.put(update)
    return {"ok": True}
