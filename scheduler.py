import logging
import os

from apscheduler.schedulers.asyncio import AsyncIOScheduler

log = logging.getLogger(__name__)


def start_scheduler(db, bot_app):
    scheduler = AsyncIOScheduler(timezone="UTC")

    async def followup_job():
        try:
            rows = await db.due_followups(limit=10)
            if not rows:
                return
            chat_id = os.getenv("ADMIN_TELEGRAM_ID")
            if not chat_id:
                return
            text = "⏰ *FOLLOW-UPS DUE*\n\n" + "\n".join(
                f"• {r['business_name']} — {r['due_at']}" for r in rows
            )
            await bot_app.bot.send_message(chat_id=int(chat_id), text=text, parse_mode="Markdown")
        except Exception:
            log.exception("Follow-up job failed")

    # One lightweight hourly reminder job. Discovery is deliberately not
    # scheduled until a real provider with documented limits is configured.
    scheduler.add_job(followup_job, "interval", hours=1, id="followups", replace_existing=True)
    scheduler.start()
    return scheduler
