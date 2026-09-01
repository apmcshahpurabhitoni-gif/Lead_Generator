import logging
import os
import secrets
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException, Request
from telegram import Update

from bot import create_application
from database import Database
from dashboard import router as dashboard_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
log = logging.getLogger("leadhunter")


def required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


@asynccontextmanager
async def lifespan(app: FastAPI):
    db = Database()
    telegram_app = create_application(db)
    await telegram_app.initialize()
    await telegram_app.start()

    base_url = required("WEBHOOK_BASE_URL").rstrip("/")
    secret = required("TELEGRAM_WEBHOOK_SECRET")
    webhook_url = f"{base_url}/telegram/webhook/{secret}"

    await telegram_app.bot.set_webhook(
        url=webhook_url,
        secret_token=secret,
        allowed_updates=["message", "callback_query"],
        max_connections=5,
        drop_pending_updates=False,
    )
    info = await telegram_app.bot.get_webhook_info()
    log.info(
        "Telegram webhook READY | url=%s | pending=%s | last_error=%s",
        info.url,
        info.pending_update_count,
        info.last_error_message,
    )

    app.state.bot = telegram_app
    app.state.db = db
    app.state.webhook_url = webhook_url

    try:
        yield
    finally:
        # IMPORTANT: never delete the Telegram webhook when Render restarts/sleeps.
        # Telegram must keep the webhook so the next incoming update can reach Render.
        try:
            await telegram_app.stop()
            await telegram_app.shutdown()
        except Exception:
            log.exception("Telegram application shutdown failed")


app = FastAPI(title="LeadHunter", lifespan=lifespan)
app.include_router(dashboard_router)


@app.get("/")
async def root():
    return {
        "service": "LeadHunter",
        "status": "online",
        "telegram": "webhook",
        "dashboard": "/dashboard",
    }


@app.get("/health")
async def health():
    return {"ok": True, "service": "leadhunter", "telegram": "webhook"}


@app.get("/telegram/status")
async def telegram_status():
    bot = getattr(app.state, "bot", None)
    if bot is None:
        return {"ok": False, "telegram": "not_initialized"}
    info = await bot.bot.get_webhook_info()
    return {
        "ok": True,
        "url_configured": bool(info.url),
        "pending_update_count": info.pending_update_count,
        "last_error_message": info.last_error_message,
        "last_error_date": info.last_error_date,
        "last_synchronization_error_date": info.last_synchronization_error_date,
    }


@app.post("/telegram/webhook/{path_secret}")
async def telegram_webhook(
    path_secret: str,
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
):
    expected = os.getenv("TELEGRAM_WEBHOOK_SECRET", "").strip()
    if not expected or not secrets.compare_digest(path_secret, expected):
        raise HTTPException(status_code=404, detail="Not found")
    if not x_telegram_bot_api_secret_token or not secrets.compare_digest(
        x_telegram_bot_api_secret_token, expected
    ):
        raise HTTPException(status_code=403, detail="Invalid webhook secret")

    payload = await request.json()
    update = Update.de_json(payload, app.state.bot.bot)
    log.info(
        "Telegram update RECEIVED | update_id=%s | callback=%s | message=%s",
        update.update_id,
        bool(update.callback_query),
        bool(update.message),
    )

    try:
        await app.state.bot.process_update(update)
    except Exception:
        log.exception("Telegram update processing failed | update_id=%s", update.update_id)
        raise

    return {"ok": True}
