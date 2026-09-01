import logging
import os
import secrets
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from telegram import Update

from bot import create_application
from database import Database
from dashboard import router as dashboard_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
log = logging.getLogger("leadhunter")


APP_VERSION = "webhook-self-heal-1"


def required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def webhook_display_url(url: str) -> str:
    """Hide the Telegram webhook secret from logs and responses."""
    if not url:
        return ""
    parts = url.rstrip("/").split("/")
    if len(parts) >= 2:
        parts[-1] = "***"
    return "/".join(parts)


async def configure_webhook(app: FastAPI) -> dict:
    """Set the Telegram webhook and verify what Telegram actually stored."""
    telegram_app = app.state.bot
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
    configured = bool(info.url)

    app.state.webhook_url = webhook_url
    app.state.webhook_configured = configured

    log.info(
        "Telegram webhook CHECK | configured=%s | url=%s | pending=%s | last_error=%s",
        configured,
        webhook_display_url(info.url),
        info.pending_update_count,
        info.last_error_message,
    )

    return {
        "configured": configured,
        "url": webhook_display_url(info.url),
        "pending_update_count": info.pending_update_count,
        "last_error_message": info.last_error_message,
        "last_error_date": info.last_error_date,
        "last_synchronization_error_date": info.last_synchronization_error_date,
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    db = Database()
    telegram_app = create_application(db)
    await telegram_app.initialize()
    await telegram_app.start()

    app.state.bot = telegram_app
    app.state.db = db
    app.state.webhook_url = ""
    app.state.webhook_configured = False

    await configure_webhook(app)

    log.info("LeadHunter startup complete | version=%s", APP_VERSION)
    for route in app.routes:
        methods = ",".join(sorted(route.methods or []))
        log.info("ROUTE LOADED | %s | %s", methods, route.path)

    try:
        yield
    finally:
        # Do NOT call delete_webhook here. Telegram must retain the webhook
        # across Render restarts so pending updates can be delivered next time.
        try:
            await telegram_app.stop()
            await telegram_app.shutdown()
        except Exception:
            log.exception("Telegram application shutdown failed")


app = FastAPI(title="LeadHunter", version=APP_VERSION, lifespan=lifespan)
app.include_router(dashboard_router)


@app.get("/")
async def root():
    return {
        "service": "LeadHunter",
        "status": "online",
        "version": APP_VERSION,
        "telegram": "webhook",
        "dashboard": "/dashboard",
        "health": "/health",
        "telegram_status": "/telegram/status",
    }


@app.get("/health")
async def health():
    return {
        "ok": True,
        "service": "leadhunter",
        "version": APP_VERSION,
        "telegram": "webhook",
    }


@app.get("/__routes")
async def routes():
    return {
        "ok": True,
        "version": APP_VERSION,
        "routes": sorted(
            {
                getattr(route, "path", "")
                for route in app.routes
                if getattr(route, "path", "")
            }
        ),
    }


@app.get("/telegram/status")
async def telegram_status():
    telegram_app = getattr(app.state, "bot", None)
    if telegram_app is None:
        return JSONResponse(
            status_code=503,
            content={"ok": False, "telegram": "not_initialized"},
        )

    try:
        info = await telegram_app.bot.get_webhook_info()
        repaired = False

        # Telegram currently reports no webhook. Re-register it immediately
        # instead of making the user restart or manually repair the bot.
        if not info.url:
            log.warning(
                "Telegram webhook MISSING | pending=%s | attempting self-heal",
                info.pending_update_count,
            )
            await configure_webhook(app)
            repaired = True
            info = await telegram_app.bot.get_webhook_info()

        app.state.webhook_configured = bool(info.url)

        return {
            "ok": True,
            "version": APP_VERSION,
            "url_configured": bool(info.url),
            "url": webhook_display_url(info.url),
            "pending_update_count": info.pending_update_count,
            "last_error_message": info.last_error_message,
            "last_error_date": info.last_error_date,
            "last_synchronization_error_date": info.last_synchronization_error_date,
            "self_healed": repaired,
        }
    except Exception as exc:
        log.exception("Telegram webhook status/self-heal failed")
        return JSONResponse(
            status_code=503,
            content={
                "ok": False,
                "version": APP_VERSION,
                "error": "telegram_webhook_check_failed",
                "detail": str(exc),
            },
        )


@app.post("/telegram/webhook/{path_secret}")
async def telegram_webhook(
    path_secret: str,
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
):
    expected = os.getenv("TELEGRAM_WEBHOOK_SECRET", "").strip()

    path_ok = bool(expected) and secrets.compare_digest(path_secret, expected)
    header_ok = bool(x_telegram_bot_api_secret_token) and bool(expected) and secrets.compare_digest(
        x_telegram_bot_api_secret_token, expected
    )

    log.info(
        "Telegram webhook HTTP request | path_ok=%s | header_ok=%s",
        path_ok,
        header_ok,
    )

    if not path_ok:
        raise HTTPException(status_code=404, detail="Not found")
    if not header_ok:
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


@app.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
)
async def unmatched_route(path: str, request: Request):
    """Return useful diagnostics instead of Render/FastAPI's generic 404."""
    log.warning("UNMATCHED HTTP REQUEST | method=%s | path=/%s", request.method, path)
    return JSONResponse(
        status_code=404,
        content={
            "ok": False,
            "error": "route_not_found",
            "path": f"/{path}",
            "version": APP_VERSION,
            "routes": sorted(
                {
                    getattr(route, "path", "")
                    for route in app.routes
                    if getattr(route, "path", "") and getattr(route, "path", "") != "/{path:path}"
                }
            ),
        },
    )
