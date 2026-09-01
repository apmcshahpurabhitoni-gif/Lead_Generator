import os
from datetime import datetime, timedelta, timezone

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

from ai import generate_whatsapp_message
from database import Database
from discovery import discover_businesses
from research import research_business
from scoring import score_lead

PAGE_SIZE = 10
STATUS_OPTIONS = [
    ("📞 Called", "CONTACTED"),
    ("💬 Responded", "RESPONDED"),
    ("📅 Meeting", "MEETING"),
    ("📄 Proposal", "PROPOSAL"),
    ("🤝 Negotiation", "NEGOTIATION"),
    ("💰 Won", "WON"),
    ("❌ Lost", "LOST"),
    ("🚫 Not interested", "NOT_INTERESTED"),
]


def authorized(update: Update) -> bool:
    admin_id = os.getenv("ADMIN_TELEGRAM_ID")
    if not admin_id:
        return True
    return bool(update.effective_user and str(update.effective_user.id) == str(admin_id))


def lead_keyboard(business_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Audit", callback_data=f"audit:{business_id}"),
         InlineKeyboardButton("💬 Message", callback_data=f"msg:{business_id}")],
        [InlineKeyboardButton("📞 Call", callback_data=f"call:{business_id}"),
         InlineKeyboardButton("⏰ Follow-up", callback_data=f"follow:{business_id}")],
        [InlineKeyboardButton("📝 Status", callback_data=f"status:{business_id}")],
    ])


def status_keyboard(business_id: int) -> InlineKeyboardMarkup:
    buttons = [InlineKeyboardButton(label, callback_data=f"setstatus:{business_id}:{status}") for label, status in STATUS_OPTIONS]
    return InlineKeyboardMarkup([buttons[i:i + 2] for i in range(0, len(buttons), 2)])


def format_lead(lead: dict) -> str:
    score = int(lead.get("score", 0) or 0)
    icon = "🔥" if score >= 80 else "🟠" if score >= 60 else "🟡"
    services = lead.get("recommended_services") or []
    problems = lead.get("problems") or []
    problems_text = "\n".join(f"🔴 {p}" for p in problems[:8]) or "✅ No stored issues yet."
    return (
        f"{icon} *{lead['name']}*\n\n"
        f"📍 {lead.get('city') or '—'}\n"
        f"🏢 {lead.get('industry') or '—'}\n"
        f"🌐 {lead.get('website') or '—'}\n"
        f"📞 {lead.get('phone') or '—'}\n\n"
        f"🎯 *Score:* {score}/100\n"
        f"📌 *Priority:* {lead.get('priority') or '—'}\n"
        f"🧭 *Status:* {lead.get('status') or 'NEW'}\n"
        f"💼 *Recommended:* {', '.join(services) if services else '—'}\n\n"
        f"🚨 *Problems / evidence*\n{problems_text}"
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return
    await update.message.reply_text(
        "🚀 *LeadHunter ready*\n\n"
        "🔎 `/find jabalpur dental`\n"
        "🔥 `/hot`\n"
        "📋 `/lead 123`\n"
        "📅 `/today`\n"
        "📈 `/stats`\n"
        "⏰ `/followups`",
        parse_mode="Markdown",
    )


async def find_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return
    if len(context.args) < 2:
        await update.message.reply_text("Use: `/find <city> <industry>`", parse_mode="Markdown")
        return

    city = context.args[0]
    industry = " ".join(context.args[1:])
    db: Database = context.application.bot_data["db"]

    await update.message.reply_text(
        f"🔎 *Search started*\n\n📍 {city}\n🏢 {industry}\n\n"
        "I will use only configured/permitted sources. No fake leads are generated.",
        parse_mode="Markdown",
    )

    candidates = await discover_businesses(city, industry)
    if not candidates:
        await update.message.reply_text(
            "⚠️ No discovery source is configured yet.\n\n"
            "The research/scoring/Telegram layers are ready, but I will not fabricate businesses or scrape a restricted source."
        )
        return

    saved = 0
    for candidate in candidates:
        business_id = await db.upsert_business(candidate)
        if not business_id:
            continue
        saved += 1
        try:
            research = await research_business(candidate)
            score = score_lead(research)
            await db.save_research_and_score(business_id, research, score)
        except Exception as exc:
            await db.record_activity(business_id, "RESEARCH_FAILED", "system", str(exc)[:500])

    hot = await db.list_leads(priority="HOT", limit=20)
    await update.message.reply_text(
        f"✅ *Finished*\n\n📥 Saved: {saved}\n🔥 Hot: {len(hot)}\n\nUse /hot to inspect the best opportunities.",
        parse_mode="Markdown",
    )


async def hot_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return
    db: Database = context.application.bot_data["db"]
    leads = await db.list_leads(priority="HOT", limit=PAGE_SIZE)
    if not leads:
        await update.message.reply_text("🔥 No hot leads available.")
        return

    lines = ["🔥 *HOT LEADS — 1st page*", ""]
    keyboard = []
    for lead in leads:
        lines.append(f"🔥 *{lead['name']}* — {lead.get('score', 0)}/100")
        lines.append(f"📍 {lead.get('city') or '—'}")
        lines.append(f"💼 {', '.join(lead.get('recommended_services') or []) or '—'}\n")
        keyboard.append([InlineKeyboardButton(
            f"🔥 {lead['name'][:28]} ({lead.get('score', 0)})", callback_data=f"lead:{lead['id']}"
        )])
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))


async def lead_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Use: `/lead <id>`", parse_mode="Markdown")
        return
    db: Database = context.application.bot_data["db"]
    lead = await db.get_lead(int(context.args[0]))
    if not lead:
        await update.message.reply_text("❌ Lead not found.")
        return
    await update.message.reply_text(format_lead(lead), parse_mode="Markdown", reply_markup=lead_keyboard(lead["id"]))


async def today_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return
    stats = await context.application.bot_data["db"].today_stats()
    await update.message.reply_text(
        "📅 *TODAY*\n\n"
        f"🔎 Leads: {stats['leads_found']}\n🎯 Qualified: {stats['qualified']}\n🔥 Hot: {stats['hot_leads']}\n"
        f"📞 Calls marked: {stats['calls']}\n💬 Contacted: {stats['contacted']}\n💬 Replies: {stats['replies']}\n"
        f"📅 Meetings: {stats['meetings']}\n📄 Proposals: {stats['proposals']}\n💰 Won: {stats['won']}",
        parse_mode="Markdown",
    )


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return
    rows = await context.application.bot_data["db"].history(days=14)
    if not rows:
        await update.message.reply_text("📈 No history yet.")
        return
    text = "📈 *14-DAY HISTORY*\n\n" + "\n".join(
        f"📅 {r['date']} — 🔎 {r.get('leads_found',0)} | 📞 {r.get('calls',0)} | 📅 {r.get('meetings',0)} | 💰 {r.get('won',0)}"
        for r in rows
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def followups_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return
    rows = await context.application.bot_data["db"].due_followups(limit=10)
    if not rows:
        await update.message.reply_text("⏰ No follow-ups due.")
        return
    keyboard = [[InlineKeyboardButton(f"⏰ {r['business_name'][:30]}", callback_data=f"lead:{r['business_id']}")] for r in rows]
    text = "⏰ *FOLLOW-UPS DUE*\n\n" + "\n".join(f"• {r['business_name']} — {r['due_at']}" for r in rows)
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))


async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not authorized(update):
        await query.answer()
        return
    await query.answer()
    db: Database = context.application.bot_data["db"]
    parts = query.data.split(":")
    action = parts[0]
    business_id = int(parts[1])
    lead = await db.get_lead(business_id)
    if not lead:
        await query.edit_message_text("❌ Lead not found.")
        return

    await db.record_telegram_event(business_id, action.upper(), query.message.message_id)

    if action == "lead":
        await query.edit_message_text(format_lead(lead), parse_mode="Markdown", reply_markup=lead_keyboard(business_id))
    elif action == "audit":
        research = await db.get_research(business_id)
        await query.edit_message_text(
            f"📋 *AUDIT — {lead['name']}*\n\n{db.format_research(research)}",
            parse_mode="Markdown", reply_markup=lead_keyboard(business_id)
        )
    elif action == "msg":
        try:
            draft = await generate_whatsapp_message(lead, await db.get_research(business_id))
            await db.record_activity(business_id, "MESSAGE_DRAFT_GENERATED", "telegram", "WhatsApp draft generated")
            await query.edit_message_text(
                f"💬 *MESSAGE DRAFT*\n\n{draft}\n\n⚠️ Draft only. LeadHunter does not send or track WhatsApp/email.",
                parse_mode="Markdown", reply_markup=lead_keyboard(business_id)
            )
        except Exception as exc:
            await query.edit_message_text(f"❌ AI message failed: {str(exc)[:500]}", reply_markup=lead_keyboard(business_id))
    elif action == "call":
        await db.record_activity(business_id, "CALL_WORKFLOW_OPENED", "telegram", "User opened call workflow")
        await query.edit_message_text(
            f"📞 *CALL — {lead['name']}*\n\n📞 Public business number: {lead.get('phone') or 'Not found'}\n\n"
            "After the call choose the outcome:",
            parse_mode="Markdown", reply_markup=status_keyboard(business_id)
        )
    elif action == "follow":
        due = datetime.now(timezone.utc) + timedelta(days=3)
        await db.create_followup(business_id, due, "Default 3-day follow-up")
        await db.record_activity(business_id, "FOLLOWUP_CREATED", "telegram", f"Due {due.isoformat()}")
        await query.edit_message_text(f"⏰ Follow-up created for {due.date()}.", reply_markup=lead_keyboard(business_id))
    elif action == "status":
        await query.edit_message_text("📝 Choose the new status:", reply_markup=status_keyboard(business_id))
    elif action == "setstatus":
        status = parts[2]
        await db.set_status(business_id, status)
        await db.record_activity(business_id, f"STATUS_{status}", "telegram", "Manual user update")
        await query.edit_message_text(f"✅ Status: *{status}*", parse_mode="Markdown", reply_markup=lead_keyboard(business_id))


def create_application(db: Database) -> Application:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required")
    app = Application.builder().token(token).build()
    app.bot_data["db"] = db
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", start))
    app.add_handler(CommandHandler("find", find_command))
    app.add_handler(CommandHandler("hot", hot_command))
    app.add_handler(CommandHandler("lead", lead_command))
    app.add_handler(CommandHandler("today", today_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("followups", followups_command))
    app.add_handler(CallbackQueryHandler(callbacks))
    return app
