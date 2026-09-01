import html
import logging
import os
from datetime import datetime, timedelta, timezone

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

from ai import generate_whatsapp_message
from database import Database
from discovery import discover_businesses
from research import research_business
from scoring import score_lead

log = logging.getLogger(__name__)
PAGE_SIZE = 10
MAX_RESEARCH_PER_SEARCH = 25
STATUS_OPTIONS = [("📞 Called", "CONTACTED"), ("💬 Responded", "RESPONDED"), ("📅 Meeting", "MEETING"), ("📄 Proposal", "PROPOSAL"), ("🤝 Negotiation", "NEGOTIATION"), ("💰 Won", "WON"), ("❌ Lost", "LOST"), ("🚫 Not interested", "NOT_INTERESTED")]


def authorized(update: Update) -> bool:
    admin = os.getenv("ADMIN_TELEGRAM_ID")
    return not admin or bool(update.effective_user and str(update.effective_user.id) == str(admin))


def lead_keyboard(bid: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Audit", callback_data=f"audit:{bid}"), InlineKeyboardButton("💬 Message", callback_data=f"msg:{bid}")],
        [InlineKeyboardButton("📞 Call", callback_data=f"call:{bid}"), InlineKeyboardButton("⏰ Follow-up", callback_data=f"follow:{bid}")],
        [InlineKeyboardButton("💰 Deal", callback_data=f"deal:{bid}"), InlineKeyboardButton("📝 Status", callback_data=f"status:{bid}")],
        [InlineKeyboardButton("🕘 History", callback_data=f"history:{bid}")],
    ])


def status_keyboard(bid: int) -> InlineKeyboardMarkup:
    b = [InlineKeyboardButton(a, callback_data=f"setstatus:{bid}:{s}") for a, s in STATUS_OPTIONS]
    return InlineKeyboardMarkup([b[i:i + 2] for i in range(0, len(b), 2)])


def format_lead(lead: dict) -> str:
    score = int(lead.get("score", 0) or 0)
    icon = "🔥" if score >= 80 else "🟠" if score >= 60 else "🟡" if score >= 40 else "⚪"
    services = ", ".join(lead.get("recommended_services") or []) or "—"
    problems = "\n".join(f"🔴 {html.escape(str(x))}" for x in (lead.get("problems") or [])[:8]) or "✅ No stored problems yet."
    return (f"{icon} <b>{html.escape(str(lead.get('name','')))}</b>\n\n"
            f"📍 {html.escape(str(lead.get('city') or '—'))}\n🏢 {html.escape(str(lead.get('industry') or '—'))}\n"
            f"🌐 {html.escape(str(lead.get('website') or '—'))}\n📞 {html.escape(str(lead.get('phone') or '—'))}\n\n"
            f"🎯 <b>Score:</b> {score}/100\n📌 <b>Priority:</b> {html.escape(str(lead.get('priority') or '—'))}\n"
            f"🧭 <b>Status:</b> {html.escape(str(lead.get('status') or 'NEW'))}\n💼 <b>Recommended:</b> {html.escape(services)}\n\n"
            f"🚨 <b>Problems / evidence</b>\n{problems}\n\n🗺️ Source: {html.escape(str(lead.get('source') or 'unknown'))}")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if authorized(update):
        await update.message.reply_text("🚀 <b>LeadHunter ready</b>\n\n🔎 <code>/find jabalpur dental</code>\n🔥 <code>/hot</code>\n📋 <code>/lead 123</code>\n💰 <code>/deal 123 55000 PROPOSAL Website,SEO</code>\n📅 <code>/today</code>\n📈 <code>/stats</code>\n⏰ <code>/followups</code>", parse_mode="HTML")


async def run_find(app: Application, city: str, industry: str, chat_id: int):
    db: Database = app.bot_data["db"]
    job_id = await db.create_job("DISCOVERY", city, industry)
    processed = succeeded = failed = 0
    try:
        candidates = await discover_businesses(city, industry, 50)
        if not candidates:
            await app.bot.send_message(chat_id, "⚠️ <b>No usable businesses found.</b>", parse_mode="HTML")
            if job_id: await db.finish_job(job_id, 0, 0, 0)
            return
        for candidate in candidates:
            processed += 1
            business_id = None
            try:
                business_id, _ = await db.upsert_business(candidate)
                if not business_id:
                    failed += 1; continue
                succeeded += 1
                if processed <= MAX_RESEARCH_PER_SEARCH:
                    research = await research_business(candidate)
                    await db.save_research_and_score(business_id, research, score_lead(research))
            except Exception as exc:
                failed += 1
                log.exception("Lead processing failed")
                if business_id:
                    await db.record_activity(business_id, "PROCESSING_FAILED", "system", str(exc))
        hot = len(await db.list_leads("HOT", PAGE_SIZE))
        high = len(await db.list_leads("HIGH", PAGE_SIZE))
        await app.bot.send_message(chat_id, f"✅ <b>Search complete</b>\n\n📍 {html.escape(city)}\n🏢 {html.escape(industry)}\n\n📥 Candidates: {len(candidates)}\n🔥 Hot: {hot}+\n🟠 High: {high}+\n🔎 Researched: {min(len(candidates), MAX_RESEARCH_PER_SEARCH)}\n⚠️ Failed: {failed}\n\nUse <code>/hot</code>.\n🗺️ OpenStreetMap coverage is incomplete.", parse_mode="HTML")
        if job_id: await db.finish_job(job_id, processed, succeeded, failed)
    except Exception as exc:
        log.exception("Discovery failed")
        if job_id: await db.finish_job(job_id, processed, succeeded, failed, str(exc)[:1000])
        await app.bot.send_message(chat_id, f"❌ <b>Search failed safely</b>\n<code>{html.escape(str(exc)[:800])}</code>", parse_mode="HTML")


async def find_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update): return
    if len(context.args) < 2:
        await update.message.reply_text("Use: <code>/find &lt;city&gt; &lt;industry&gt;</code>", parse_mode="HTML"); return
    city, industry = context.args[0], " ".join(context.args[1:])
    await update.message.reply_text(f"🔎 <b>Search queued</b>\n\n📍 {html.escape(city)}\n🏢 {html.escape(industry)}", parse_mode="HTML")
    context.application.create_task(run_find(context.application, city, industry, update.effective_chat.id), update=update)


async def hot_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update): return
    db: Database = context.application.bot_data["db"]
    leads = await db.list_leads("HOT", PAGE_SIZE + 1)
    if not leads:
        await update.message.reply_text("🔥 No hot leads available."); return
    has_next = len(leads) > PAGE_SIZE; leads = leads[:PAGE_SIZE]
    text = "🔥 <b>HOT LEADS</b>\n\n" + "\n".join(f"🔥 <b>{html.escape(str(x['name']))}</b> — {x.get('score',0)}/100\n📍 {html.escape(str(x.get('city') or '—'))}\n💼 {html.escape(', '.join(x.get('recommended_services') or []) or '—')}\n" for x in leads)
    kb = [[InlineKeyboardButton(f"🔥 {str(x['name'])[:28]} ({x.get('score',0)})", callback_data=f"lead:{x['id']}")] for x in leads]
    if has_next: kb.append([InlineKeyboardButton("Next ➡️", callback_data="page:HOT:1")])
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb))


async def lead_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update) or not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Use: <code>/lead &lt;id&gt;</code>", parse_mode="HTML"); return
    db: Database = context.application.bot_data["db"]
    lead = await db.get_lead(int(context.args[0]))
    if not lead: await update.message.reply_text("❌ Lead not found."); return
    sent = await update.message.reply_text(format_lead(lead), parse_mode="HTML", reply_markup=lead_keyboard(lead["id"]), disable_web_page_preview=True)
    await db.record_telegram_event(lead["id"], "LEAD_DISPLAYED", sent.message_id)


async def deal_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update) or len(context.args) < 4 or not context.args[0].isdigit():
        await update.message.reply_text("Use: <code>/deal &lt;lead_id&gt; &lt;value&gt; &lt;stage&gt; &lt;service1,service2&gt;</code>", parse_mode="HTML"); return
    try:
        bid, value, stage, services = int(context.args[0]), float(context.args[1]), context.args[2].upper(), context.args[3:]
        services = [s.strip() for s in " ".join(services).split(",") if s.strip()]
        if stage not in {"PROPOSAL", "NEGOTIATION", "WON", "LOST"}: raise ValueError("Invalid deal stage")
    except ValueError as exc:
        await update.message.reply_text(f"❌ {html.escape(str(exc))}"); return
    db: Database = context.application.bot_data["db"]
    if not await db.get_lead(bid): await update.message.reply_text("❌ Lead not found."); return
    deal_id = await db.upsert_deal(bid, value, services, stage)
    if stage in {"WON", "LOST"}: await db.set_status(bid, stage)
    await update.message.reply_text(f"💰 <b>Deal saved</b>\n\nID: {deal_id}\nValue: ₹{value:,.0f}\nStage: {html.escape(stage)}\nServices: {html.escape(', '.join(services))}", parse_mode="HTML")


async def today_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update): return
    s = await context.application.bot_data["db"].today_stats()
    await update.message.reply_text("📅 <b>TODAY</b>\n\n" + "\n".join([f"🔎 Leads: {s['leads_found']}", f"🎯 Qualified: {s['qualified']}", f"🔥 Hot: {s['hot_leads']}", f"📞 Calls: {s['calls']}", f"💬 Contacted: {s['contacted']}", f"💬 Replies: {s['replies']}", f"📅 Meetings: {s['meetings']}", f"📄 Proposals: {s['proposals']}", f"💰 Won: {s['won']}", f"❌ Lost: {s['lost']}"]), parse_mode="HTML")


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update): return
    rows = await context.application.bot_data["db"].history(14)
    await update.message.reply_text("📈 <b>14-DAY HISTORY</b>\n\n" + ("\n".join(f"📅 {r['date']} — 🔎 {r.get('leads_found',0)} | 📞 {r.get('calls',0)} | 📅 {r.get('meetings',0)} | 💰 {r.get('won',0)}" for r in rows) or "No history yet."), parse_mode="HTML")


async def followups_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update): return
    rows = await context.application.bot_data["db"].due_followups(10)
    if not rows: await update.message.reply_text("⏰ No follow-ups due."); return
    kb = [[InlineKeyboardButton(f"⏰ {r['business_name'][:30]}", callback_data=f"lead:{r['business_id']}")] for r in rows]
    await update.message.reply_text("⏰ <b>FOLLOW-UPS DUE</b>\n\n" + "\n".join(f"• {html.escape(r['business_name'])} — {r['due_at']}" for r in rows), parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb))


async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if not authorized(update): await q.answer(); return
    await q.answer()
    db: Database = context.application.bot_data["db"]
    parts = q.data.split(":"); action = parts[0]
    if action == "page":
        priority, page = parts[1], int(parts[2]); leads = await db.list_leads(priority, PAGE_SIZE + 1, page * PAGE_SIZE); has_next = len(leads) > PAGE_SIZE; leads = leads[:PAGE_SIZE]
        kb = [[InlineKeyboardButton(f"{x['name'][:28]} ({x.get('score',0)})", callback_data=f"lead:{x['id']}")] for x in leads]
        nav=[]
        if page > 0: nav.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"page:{priority}:{page-1}"))
        if has_next: nav.append(InlineKeyboardButton("Next ➡️", callback_data=f"page:{priority}:{page+1}"))
        if nav: kb.append(nav)
        await q.edit_message_text(f"🔥 <b>{priority} LEADS — page {page+1}</b>\n\n" + "\n".join(f"🔥 {html.escape(str(x['name']))} — {x.get('score',0)}/100" for x in leads), parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb)); return
    if len(parts) < 2 or not parts[1].isdigit(): return
    bid = int(parts[1]); lead = await db.get_lead(bid)
    if not lead: await q.edit_message_text("❌ Lead not found."); return
    await db.record_telegram_event(bid, action.upper(), q.message.message_id)
    if action == "lead":
        await q.edit_message_text(format_lead(lead), parse_mode="HTML", reply_markup=lead_keyboard(bid), disable_web_page_preview=True)
    elif action == "audit":
        await q.edit_message_text(f"📋 <b>AUDIT — {html.escape(lead['name'])}</b>\n\n{html.escape(db.format_research(await db.get_research(bid)))}", parse_mode="HTML", reply_markup=lead_keyboard(bid))
    elif action == "history":
        rows = await db.activities(bid, 20)
        await q.edit_message_text("🕘 <b>LEAD HISTORY</b>\n\n" + ("\n".join(f"• {r['created_at']} — <b>{html.escape(r['action'])}</b> — {html.escape(r.get('notes') or '')}" for r in rows) or "No activity yet."), parse_mode="HTML", reply_markup=lead_keyboard(bid))
    elif action == "deal":
        await q.edit_message_text("💰 <b>DEAL</b>\n\nUse:\n<code>/deal LEAD_ID VALUE STAGE SERVICE1,SERVICE2</code>\n\nExample:\n<code>/deal 123 55000 PROPOSAL Website,SEO,GBP</code>", parse_mode="HTML", reply_markup=lead_keyboard(bid))
    elif action == "msg":
        try:
            draft = await generate_whatsapp_message(lead, await db.get_research(bid))
            await db.record_activity(bid, "MESSAGE_DRAFT_GENERATED", "telegram", "WhatsApp draft generated")
            await q.edit_message_text(f"💬 <b>MESSAGE DRAFT</b>\n\n{html.escape(draft)}\n\n⚠️ Draft only. LeadHunter does not send or track WhatsApp/email.", parse_mode="HTML", reply_markup=lead_keyboard(bid))
        except Exception as exc:
            await q.edit_message_text(f"❌ AI message failed: {html.escape(str(exc)[:500])}", reply_markup=lead_keyboard(bid))
    elif action == "call":
        await db.record_activity(bid, "CALL_WORKFLOW_OPENED", "telegram", "User opened call workflow")
        await q.edit_message_text(f"📞 <b>CALL — {html.escape(lead['name'])}</b>\n\n📞 Public business number: <b>{html.escape(str(lead.get('phone') or 'Not found'))}</b>\n\nAfter the call choose the outcome:", parse_mode="HTML", reply_markup=status_keyboard(bid))
    elif action == "follow":
        due = datetime.now(timezone.utc) + timedelta(days=3); await db.create_followup(bid, due, "Default 3-day follow-up"); await db.record_activity(bid, "FOLLOWUP_CREATED", "telegram", f"Due {due.isoformat()}"); await q.edit_message_text(f"⏰ Follow-up created for <b>{due.date()}</b>.", parse_mode="HTML", reply_markup=lead_keyboard(bid))
    elif action == "status":
        await q.edit_message_text("📝 <b>Choose status:</b>", parse_mode="HTML", reply_markup=status_keyboard(bid))
    elif action == "setstatus":
        status = parts[2]; await db.set_status(bid, status); await db.record_activity(bid, f"STATUS_{status}", "telegram", "Manual user update")
        if status == "CONTACTED": await db.record_activity(bid, "CALL_COMPLETED", "telegram", "User marked lead as called")
        await q.edit_message_text(f"✅ <b>Status:</b> {html.escape(status)}", parse_mode="HTML", reply_markup=lead_keyboard(bid))


def create_application(db: Database) -> Application:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token: raise RuntimeError("TELEGRAM_BOT_TOKEN is required")
    app = Application.builder().token(token).build(); app.bot_data["db"] = db
    for command, handler in [("start", start), ("help", start), ("find", find_command), ("hot", hot_command), ("lead", lead_command), ("deal", deal_command), ("today", today_command), ("stats", stats_command), ("followups", followups_command)]:
        app.add_handler(CommandHandler(command, handler))
    app.add_handler(CallbackQueryHandler(callbacks))
    return app
