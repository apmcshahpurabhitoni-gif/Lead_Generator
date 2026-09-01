import asyncio
import logging
import os

from bot import create_application
from database import Database

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

async def run_bot() -> None:
    db = Database()
    app = create_application(db)

    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)

    try:
        while True:
            await asyncio.sleep(3600)
    finally:
        await app.updater.stop()
        await app.stop()
        await app.shutdown()

if __name__ == "__main__":
    if os.getenv("RUN_TELEGRAM_BOT", "false").lower() != "true":
        raise SystemExit("Set RUN_TELEGRAM_BOT=true to run the Telegram bot.")
    asyncio.run(run_bot())
