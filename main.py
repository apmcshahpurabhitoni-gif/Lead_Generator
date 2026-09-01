import logging
import os
import secrets
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException, Request
from telegram import Update

from bot import create_application
from dashboard import router as dashboard_router
from database import Database

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


@asynccontextmanager
async def lifespan(app: FastAPI):
    db = Database()
    bot = create_application(db)
    await bot.initialize()
    await bot.start()
    base_url = require_env("WEBHOOK_BASE_URL").rstrip("/")
    secret = require_env("TELEGRAM_WEBHOOK_SECRET")
    await bot.bot.set_webhook(
        url=f"{base_url}/telegram/webhook/{secret}",
        secret_token=secret,
        allowed_updates=Update.ALL_TYPES,
        max_connections=5,
        drop_pending_updates=True,
    )
    app.state.bot = bot
    app.state.db = db
    try:
        yield
    finally:
        await bot.bot.delete_webhook(drop_pending_updates=False)
        await bot.stop()
        await bot.shutdown()


app = FastAPI(title="LeadHunter", lifespan=lifespan)
app.include_router(dashboard_router)


@app.get("/")
async def root():
    return {"service": "LeadHunter", "status": "online", "dashboard": "/dashboard"}


@app.get("/health")
async def health():
    return {"ok": True, "service": "leadhunter"}


@app.post("/telegram/webhook/{path_secret}")
async def telegram_webhook(path_secret: str, request: Request, x_telegram_bot_api_secret_token: str | None = Header(default=None)):
    expected = os.getenv("TELEGRAM_WEBHOOK_SECRET")
    if not expected or not secrets.compare_digest(path_secret, expected):
        raise HTTPException(status_code=404, detail="Not found")
    if not x_telegram_bot_api_secret_token or not secrets.compare_digest(x_telegram_bot_api_secret_token, expected):
        raise HTTPException(status_code=403, detail="Invalid webhook secret")
    payload = await request.json()
    update = Update.de_json(payload, app.state.bot.bot)
    await app.state.bot.process_update(update)
    return {"ok": True}
