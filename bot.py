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
MAX_RESEARCH_PER_SEARCH = 10

# User-facing business menu. The user selects a type instead of guessing keywords.
INDUSTRIES = [
    ("🦷 Dental / Dentist", "dental"), ("🏥 Hospital", "hospital"), ("🩺 Clinic", "clinic"),
    ("🍽️ Restaurant", "restaurant"), ("☕ Cafe", "cafe"), ("🥐 Bakery", "bakery"),
    ("🏨 Hotel", "hotel"), ("🌴 Resort", "resort"), ("🎓 School", "school"),
    ("🏫 College", "college"), ("🎓 University", "university"), ("💊 Pharmacy", "pharmacy"),
    ("🏋️ Gym / Fitness", "gym"), ("💇 Salon", "salon"), ("💄 Beauty", "beauty"),
    ("🚗 Car Dealer", "car dealer"), ("🔧 Car Repair", "car repair"), ("🚿 Car Wash", "car wash"),
    ("🏠 Real Estate", "real estate"), ("⚖️ Lawyer", "lawyer"), ("🧾 Accountant", "accountant"),
    ("✈️ Travel Agency", "travel agency"), ("📱 Electronics", "electronics"), ("👕 Clothing", "clothing"),
    ("🛋️ Furniture", "furniture"), ("💎 Jewellery", "jewellery"), ("🛒 Supermarket", "supermarket"),
    ("🔨 Hardware", "hardware"), ("🏦 Bank", "bank"), ("🛡️ Insurance", "insurance"),
    ("🏛️ Architect", "architect"), ("🏗️ Construction", "construction"), ("🖨️ Printing", "printing"),
    ("📸 Photographer", "photographer"), ("⛽ Fuel Station", "fuel"), ("🐾 Veterinary", "veterinary"),
    ("🌐 All Supported Businesses", "all"),
]
STATUS_OPTIONS = [
    ("📞 Called", "CONTACTED"), ("💬 Responded", "RESPONDED"), ("📅 Meeting", "MEETING"),
    ("📄 Proposal", "PROPOSAL"), ("🤝 Negotiation", "NEGOTIATION"), ("💰 Won", "WON"),
    ("❌ Lost", "LOST"), ("🚫 Not interested", "NOT_INTERESTED"),
]


def authorized(update: Update) -> bool:
    admin = os.getenv("ADMIN_TELEGRAM_ID")
    return not admin or bool(update.effective_user and str(update.effective_user.id) == str(admin))


def home_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔎 FIND NEW LEADS", callback_data="findmenu")],
        [InlineKeyboardButton("🔥 HOT LEADS", callback_data="hotmenu"), InlineKeyboardButton("📅 TODAY", callback_data="todaymenu")],
        [InlineKeyboardButton("📈 STATS", callback_data="statsmenu"), InlineKeyboardButton("⏰ FOLLOW-UPS", callback_data="followmenu")],
        [InlineKeyboardButton("❓ HELP", callback_data="helpmenu")],
    ])


def industry_keyboard(page: int = 0) -> InlineKeyboardMarkup:
    start = page * PAGE_SIZE
    items = INDUSTRIES[start:start + PAGE_SIZE]
    rows = [[InlineKeyboardButton(label, callback_data=f"industry:{key}")] for label, key in items]
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"industries:{page - 1}"))
    if start + PAGE_SIZE < len(INDUSTRIES):
        nav.append(InlineKeyboardButton("Next ➡️", callback_data=f"industries:{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton("🏠 MAIN MENU", callback_data="home")])
    return InlineKeyboardMarkup(rows)


def city_keyboard(industry: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📍 JABALPUR", callback_data=f"search:Jabalpur:{industry}")],
        [InlineKeyboardButton("✏️ OTHER CITY", callback_data=f"othercity:{industry}")],
        [InlineKeyboardButton("⬅️ INDUSTRIES", callback_data="industries:0")],
    ])


def lead_keyboard(bid: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 AUDIT", callback_data=f"audit:{bid}"), InlineKeyboardButton("💬 MESSAGE", callback_data=f"msg:{bid}")],
        [InlineKeyboardButton("📞 CALL", callback_data=f"call:{bid}"), InlineKeyboardButton("⏰ FOLLOW-UP", callback_data=f"follow:{bid}")],
        [InlineKeyboardButton("💰 DEAL", callback_data=f"deal:{bid}"), InlineKeyboardButton("📝 STATUS", callback_data=f"status:{bid}")],
        [InlineKeyboardButton("🕘 HISTORY", callback_data=f"history:{bid}")],
    ])


def status_keyboard(bid: int) -> InlineKeyboardMarkup:
    buttons = [InlineKeyboardButton(label, callback_data=f"setstatus:{bid}:{status}") for label, status in STATUS_OPTIONS]
    return InlineKeyboardMarkup([buttons[i:i + 2] for i in range(0, len(buttons), 2)])


def score_icon(score: int) -> str:
    return "🔥" if score >= 80 else "🟠" if score >= 60 else "🟡" if score >= 40 else "⚪"


def format_lead(lead: dict) -> str:
    score = int(lead.get("score", 0) or 0)
    services = ", ".join(lead.get("recommended_services") or []) or "—"
    problems = "\n".join(f"🔴 {html.escape(str(x))}" for x in (lead.get("problems") or [])[:8]) or "✅ No stored problems yet."
    return (
        f"{score_icon(score)} <b>{html.escape(str(lead.get('name', 'Unnamed Business')))}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"📍 <b>Location:</b> {html.escape(str(lead.get('city') or '—'))}\n"
        f"🏢 <b>Industry:</b> {html.escape(str(lead.get('industry') or '—'))}\n"
        f"🌐 <b>Website:</b> {html.escape(str(lead.get('website') or 'Not found'))}\n"
        f"📞 <b>Phone:</b> {html.escape(str(lead.get('phone') or 'Not found'))}\n\n"
        f"🎯 <b>Opportunity Score:</b> {score}/100\n"
        f"📌 <b>Priority:</b> {html.escape(str(lead.get('priority') or '—'))}\n"
        f"🧭 <b>Status:</b> {html.escape(str(lead.get('status') or 'NEW'))}\n"
        f"💼 <b>Recommended:</b> {html.escape(services)}\n\n"
        "🚨 <b>PROBLEMS / EVIDENCE</b>\n" + problems + "\n\n"
        f"🗺️ <b>Source:</b> {html.escape(str(lead.get('source') or 'unknown'))}"
    )


async def send_home(update: Update) -> None:
    text = (
        "🚀 <b>LEADHUNTER</b>\n<i>AI-Powered Lead Command Center</i>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🔎 <b>Find</b> new businesses\n🧪 <b>Audit</b> their online presence\n"
        "🎯 <b>Score</b> sales opportunities\n💬 <b>Create</b> personalized outreach\n"
        "📞 <b>Track</b> calls & follow-ups\n💰 <b>Manage</b> deals & pipeline\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n💡 <b>Ready to hunt your next client?</b>\n"
        "👇 Choose an action below — <b>no commands to remember.</b>"
    )
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=home_keyboard())


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if authorized(update):
        await send_home(update)


async def send_industry_menu(target, page: int = 0):
    text = (
        "🔎 <b>FIND NEW LEADS</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
        "🏢 <b>Choose a business type</b>\n"
        "No guessing. No keywords to remember.\n\n"
        f"📚 Options {page * PAGE_SIZE + 1}–{min((page + 1) * PAGE_SIZE, len(INDUSTRIES))} of {len(INDUSTRIES)}"
    )
    await target.edit_message_text(text, parse_mode="HTML", reply_markup=industry_keyboard(page))


async def run_find(app: Application, city: str, industry: str, chat_id: int):
    db: Database = app.bot_data["db"]
    job_id = await db.create_job("DISCOVERY", city, industry)
    processed = succeeded = failed = 0
    try:
        candidates = await discover_businesses(city, industry, 50)
        if not candidates:
            await app.bot.send_message(chat_id, "⚠️ <b>NO USABLE BUSINESSES FOUND</b>\n\nTry another business type or city.", parse_mode="HTML")
            if job_id:
                await db.finish_job(job_id, 0, 0, 0)
            return
        for candidate in candidates:
            processed += 1
            business_id = None
            try:
                business_id, _ = await db.upsert_business(candidate)
                if not business_id:
                    failed += 1
                    continue
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
        text = (
            "✅ <b>LEAD HUNT COMPLETE</b>\n━━━━━━━━━━━━━━━━━━━━\n"
            f"📍 <b>City:</b> {html.escape(city)}\n🏢 <b>Type:</b> {html.escape(industry)}\n\n"
            f"📥 <b>Businesses found:</b> {len(candidates)}\n🔥 <b>Hot:</b> {hot}+\n"
            f"🟠 <b>High:</b> {high}+\n🧪 <b>Deep researched:</b> {min(len(candidates), MAX_RESEARCH_PER_SEARCH)}\n"
            f"⚠️ <b>Failed:</b> {failed}\n\n🎯 Tap <b>VIEW HOT LEADS</b> to start working them.\n"
            "🗺️ <i>OpenStreetMap coverage varies by area.</i>"
        )
        await app.bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔥 VIEW HOT LEADS", callback_data="hotmenu")],
            [InlineKeyboardButton("🔎 FIND ANOTHER TYPE", callback_data="findmenu")],
            [InlineKeyboardButton("🏠 MAIN MENU", callback_data="home")],
        ]))
        if job_id:
            await db.finish_job(job_id, processed, succeeded, failed)
    except Exception as exc:
        log.exception("Discovery failed")
        if job_id:
            await db.finish_job(job_id, processed, succeeded, failed, str(exc)[:1000])
        await app.bot.send_message(chat_id, f"❌ <b>SEARCH COULD NOT BE COMPLETED</b>\n\n{html.escape(str(exc)[:800])}", parse_mode="HTML")


async def find_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return
    if len(context.args) < 2:
        await update.message.reply_text(
            "🔎 <b>Let's find leads without guessing.</b>\n\nTap <b>FIND NEW LEADS</b> and choose the business type.",
            parse_mode="HTML", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔎 FIND NEW LEADS", callback_data="findmenu")]])
        )
        return
    city, industry = context.args[0], " ".join(context.args[1:])
    await update.message.reply_text(f"🔎 <b>SEARCH QUEUED</b>\n\n📍 {html.escape(city)}\n🏢 {html.escape(industry)}\n\n⏳ Research is running in the background.", parse_mode="HTML")
    context.application.create_task(run_find(context.application, city, industry, update.effective_chat.id), update=update)


async def hot_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if authorized(update):
        await show_hot(update.message, context.application)


async def show_hot(target, app: Application):
    db: Database = app.bot_data["db"]
    leads = await db.list_leads("HOT", PAGE_SIZE + 1)
    if not leads:
        await target.reply_text("🔥 <b>HOT LEADS</b>\n━━━━━━━━━━━━━━━━━━━━\n\nNo hot leads yet.\n\n🔎 Run a lead hunt to populate your pipeline.", parse_mode="HTML", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔎 FIND NEW LEADS", callback_data="findmenu")]]))
        return
    has_next = len(leads) > PAGE_SIZE
    leads = leads[:PAGE_SIZE]
    lines = ["🔥 <b>HOT LEADS</b>", "━━━━━━━━━━━━━━━━━━━━", "🎯 Highest-priority opportunities first.\n"]
    for x in leads:
        lines.append(f"{score_icon(int(x.get('score', 0) or 0))} <b>{html.escape(str(x['name']))}</b> · <code>{x.get('score', 0)}/100</code>\n📍 {html.escape(str(x.get('city') or '—'))}\n💼 {html.escape(', '.join(x.get('recommended_services') or []) or '—')}\n")
    kb = [[InlineKeyboardButton(f"🔥 {str(x['name'])[:25]} · {x.get('score', 0)}", callback_data=f"lead:{x['id']}")] for x in leads]
    if has_next:
        kb.append([InlineKeyboardButton("Next ➡️", callback_data="page:HOT:1")])
    kb.append([InlineKeyboardButton("🔎 FIND MORE", callback_data="findmenu"), InlineKeyboardButton("🏠 MENU", callback_data="home")])
    await target.reply_text("\n".join(lines), parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb))


async def lead_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update) or not context.args or not context.args[0].isdigit():
        await update.message.reply_text("📋 <b>OPEN A LEAD</b>\n\nUse the lead buttons from <b>HOT LEADS</b>, or <code>/lead 123</code>.", parse_mode="HTML")
        return
    db: Database = context.application.bot_data["db"]
    lead = await db.get_lead(int(context.args[0]))
    if not lead:
        await update.message.reply_text("❌ <b>Lead not found.</b>", parse_mode="HTML")
        return
    sent = await update.message.reply_text(format_lead(lead), parse_mode="HTML", reply_markup=lead_keyboard(lead["id"]), disable_web_page_preview=True)
    await db.record_telegram_event(lead["id"], "LEAD_DISPLAYED", sent.message_id)


async def deal_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update) or len(context.args) < 4 or not context.args[0].isdigit():
        await update.message.reply_text("💰 <b>SAVE A DEAL</b>\n\n<code>/deal LEAD_ID VALUE STAGE SERVICE1,SERVICE2</code>\n\nExample: <code>/deal 123 55000 PROPOSAL Website,SEO,GBP</code>", parse_mode="HTML")
        return
    try:
        bid, value, stage, services = int(context.args[0]), float(context.args[1]), context.args[2].upper(), context.args[3:]
        services = [s.strip() for s in " ".join(services).split(",") if s.strip()]
        if stage not in {"PROPOSAL", "NEGOTIATION", "WON", "LOST"}:
            raise ValueError("Choose PROPOSAL, NEGOTIATION, WON or LOST")
    except ValueError as exc:
        await update.message.reply_text(f"❌ <b>Deal not saved</b>\n\n{html.escape(str(exc))}", parse_mode="HTML")
        return
    db: Database = context.application.bot_data["db"]
    if not await db.get_lead(bid):
        await update.message.reply_text("❌ <b>Lead not found.</b>", parse_mode="HTML")
        return
    deal_id = await db.upsert_deal(bid, value, services, stage)
    if stage in {"WON", "LOST"}:
        await db.set_status(bid, stage)
    await update.message.reply_text(f"💰 <b>DEAL SAVED</b>\n━━━━━━━━━━━━━━━━━━━━\n🆔 <b>ID:</b> {deal_id}\n💵 <b>Value:</b> ₹{value:,.0f}\n📌 <b>Stage:</b> {html.escape(stage)}\n💼 <b>Services:</b> {html.escape(', '.join(services))}", parse_mode="HTML")


async def today_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if authorized(update):
        await show_today(update.message, context.application)


async def show_today(target, app: Application):
    s = await app.bot_data["db"].today_stats()
    text = ("📅 <b>TODAY'S ACTIVITY</b>\n━━━━━━━━━━━━━━━━━━━━\n"
            f"🔎 Leads found: <b>{s['leads_found']}</b>\n🎯 Qualified: <b>{s['qualified']}</b>\n🔥 Hot leads: <b>{s['hot_leads']}</b>\n\n"
            f"📞 Calls: <b>{s['calls']}</b>\n💬 Contacted: <b>{s['contacted']}</b>\n💬 Replies: <b>{s['replies']}</b>\n📅 Meetings: <b>{s['meetings']}</b>\n\n"
            f"📄 Proposals: <b>{s['proposals']}</b>\n💰 Won: <b>{s['won']}</b>\n❌ Lost: <b>{s['lost']}</b>")
    await target.reply_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 MAIN MENU", callback_data="home")]]))


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if authorized(update):
        await show_stats(update.message, context.application)


async def show_stats(target, app: Application):
    rows = await app.bot_data["db"].history(14)
    body = "\n".join(f"📅 {r['date']} · 🔎 {r.get('leads_found', 0)} · 📞 {r.get('calls', 0)} · 📅 {r.get('meetings', 0)} · 💰 {r.get('won', 0)}" for r in rows) or "No history yet."
    await target.reply_text(f"📈 <b>14-DAY PIPELINE HISTORY</b>\n━━━━━━━━━━━━━━━━━━━━\n\n{body}", parse_mode="HTML", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 MAIN MENU", callback_data="home")]]))


async def followups_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if authorized(update):
        await show_followups(update.message, context.application)


async def show_followups(target, app: Application):
    rows = await app.bot_data["db"].due_followups(10)
    if not rows:
        await target.reply_text("⏰ <b>FOLLOW-UPS</b>\n━━━━━━━━━━━━━━━━━━━━\n\n✅ Nothing is due right now.", parse_mode="HTML", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 MAIN MENU", callback_data="home")]]))
        return
    kb = [[InlineKeyboardButton(f"⏰ {r['business_name'][:28]}", callback_data=f"lead:{r['business_id']}")] for r in rows]
    kb.append([InlineKeyboardButton("🏠 MAIN MENU", callback_data="home")])
    body = "\n".join(f"🔔 <b>{html.escape(r['business_name'])}</b>\n📅 {r['due_at']}\n" for r in rows)
    await target.reply_text(f"⏰ <b>FOLLOW-UPS DUE</b>\n━━━━━━━━━━━━━━━━━━━━\n\n{body}", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb))


async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if not authorized(update):
        await q.answer()
        return
    await q.answer()
    db: Database = context.application.bot_data["db"]
    parts = q.data.split(":")
    action = parts[0]

    # Navigation callbacks are handled before lead-ID callbacks.
    if action == "home":
        await q.edit_message_text("🚀 <b>LEADHUNTER</b>\n\n👇 Choose what you want to do:", parse_mode="HTML", reply_markup=home_keyboard())
        return
    if action in {"findmenu", "industries"}:
        page = int(parts[1]) if action == "industries" and len(parts) > 1 else 0
        await send_industry_menu(q, page)
        return
    if action == "industry":
        industry = parts[1]
        label = next((label for label, key in INDUSTRIES if key == industry), industry.title())
        await q.edit_message_text(f"🏢 <b>{html.escape(label)}</b>\n━━━━━━━━━━━━━━━━━━━━\n\n📍 <b>Where should I search?</b>", parse_mode="HTML", reply_markup=city_keyboard(industry))
        return
    if action == "search":
        city, industry = parts[1], ":".join(parts[2:])
        label = next((label for label, key in INDUSTRIES if key == industry), industry.title())
        await q.edit_message_text(f"🔎 <b>LEAD HUNT STARTED</b>\n━━━━━━━━━━━━━━━━━━━━\n📍 {html.escape(city)}\n🏢 {html.escape(label)}\n\n⏳ Finding businesses and researching the strongest opportunities...\n\n💡 You can leave Telegram and come back when the result arrives.", parse_mode="HTML")
        context.application.create_task(run_find(context.application, city, industry, q.message.chat_id), update=update)
        return
    if action == "othercity":
        industry = ":".join(parts[1:])
        label = next((label for label, key in INDUSTRIES if key == industry), industry.title())
        await q.edit_message_text(f"✏️ <b>OTHER CITY</b>\n\nYou selected <b>{html.escape(label)}</b>.\n\nUse:\n<code>/find CITY {html.escape(industry)}</code>\n\nExample:\n<code>/find indore {html.escape(industry)}</code>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ BACK TO INDUSTRIES", callback_data="industries:0")]]))
        return
    if action == "hotmenu":
        await show_hot(q.message, context.application)
        return
    if action == "todaymenu":
        await show_today(q.message, context.application)
        return
    if action == "statsmenu":
        await show_stats(q.message, context.application)
        return
    if action == "followmenu":
        await show_followups(q.message, context.application)
        return
    if action == "helpmenu":
        await q.edit_message_text("❓ <b>LEADHUNTER HELP</b>\n━━━━━━━━━━━━━━━━━━━━\n\n🔎 <b>Find Leads</b> → choose business type → city.\n🔥 <b>Hot Leads</b> → highest-priority prospects.\n📋 <b>Audit</b> → website/online evidence.\n💬 <b>Message</b> → personalized WhatsApp draft.\n📞 <b>Call</b> → manually record outcome.\n⏰ <b>Follow-up</b> → create reminder.\n💰 <b>Deal</b> → track value and stage.\n🕘 <b>History</b> → see lead activity.\n\n🔐 <i>WhatsApp/email are not sent or tracked.</i>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 MAIN MENU", callback_data="home")]]))
        return
    if action == "page":
        priority, page = parts[1], int(parts[2])
        leads = await db.list_leads(priority, PAGE_SIZE + 1, page * PAGE_SIZE)
        has_next = len(leads) > PAGE_SIZE
        leads = leads[:PAGE_SIZE]
        kb = [[InlineKeyboardButton(f"{str(x['name'])[:28]} · {x.get('score', 0)}", callback_data=f"lead:{x['id']}")] for x in leads]
        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"page:{priority}:{page - 1}"))
        if has_next:
            nav.append(InlineKeyboardButton("Next ➡️", callback_data=f"page:{priority}:{page + 1}"))
        if nav:
            kb.append(nav)
        kb.append([InlineKeyboardButton("🏠 MENU", callback_data="home")])
        body = "\n".join(f"{score_icon(int(x.get('score', 0) or 0))} <b>{html.escape(str(x['name']))}</b> — {x.get('score', 0)}/100" for x in leads)
        await q.edit_message_text(f"🔥 <b>{priority} LEADS · PAGE {page + 1}</b>\n━━━━━━━━━━━━━━━━━━━━\n\n{body}", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb))
        return

    if len(parts) < 2 or not parts[1].isdigit():
        return
    bid = int(parts[1])
    lead = await db.get_lead(bid)
    if not lead:
        await q.edit_message_text("❌ <b>Lead not found.</b>", parse_mode="HTML")
        return
    await db.record_telegram_event(bid, action.upper(), q.message.message_id)

    if action == "lead":
        await q.edit_message_text(format_lead(lead), parse_mode="HTML", reply_markup=lead_keyboard(bid), disable_web_page_preview=True)
    elif action == "audit":
        audit = html.escape(db.format_research(await db.get_research(bid)))
        await q.edit_message_text(f"📋 <b>ONLINE AUDIT</b>\n<b>{html.escape(lead['name'])}</b>\n━━━━━━━━━━━━━━━━━━━━\n\n{audit}", parse_mode="HTML", reply_markup=lead_keyboard(bid))
    elif action == "history":
        rows = await db.activities(bid, 20)
        body = "\n".join(f"🕘 {r['created_at']}\n<b>{html.escape(r['action'])}</b> · {html.escape(r.get('notes') or '')}\n" for r in rows) or "No activity yet."
        await q.edit_message_text(f"🕘 <b>LEAD HISTORY</b>\n━━━━━━━━━━━━━━━━━━━━\n\n{body}", parse_mode="HTML", reply_markup=lead_keyboard(bid))
    elif action == "deal":
        await q.edit_message_text("💰 <b>DEAL TRACKING</b>\n━━━━━━━━━━━━━━━━━━━━\n\nUse:\n<code>/deal LEAD_ID VALUE STAGE SERVICE1,SERVICE2</code>\n\nExample:\n<code>/deal 123 55000 PROPOSAL Website,SEO,GBP</code>", parse_mode="HTML", reply_markup=lead_keyboard(bid))
    elif action == "msg":
        try:
            draft = await generate_whatsapp_message(lead, await db.get_research(bid))
            await db.record_activity(bid, "MESSAGE_DRAFT_GENERATED", "telegram", "WhatsApp draft generated")
            await q.edit_message_text(f"💬 <b>PERSONALIZED MESSAGE</b>\n━━━━━━━━━━━━━━━━━━━━\n\n{html.escape(draft)}\n\n📋 <i>Copy this draft and send it manually.</i>\n🔐 <i>LeadHunter does not send or track WhatsApp/email.</i>", parse_mode="HTML", reply_markup=lead_keyboard(bid))
        except Exception as exc:
            await q.edit_message_text(f"❌ <b>AI message could not be generated.</b>\n\n{html.escape(str(exc)[:500])}", parse_mode="HTML", reply_markup=lead_keyboard(bid))
    elif action == "call":
        await db.record_activity(bid, "CALL_WORKFLOW_OPENED", "telegram", "User opened call workflow")
        await q.edit_message_text(f"📞 <b>CALL WORKFLOW</b>\n<b>{html.escape(lead['name'])}</b>\n━━━━━━━━━━━━━━━━━━━━\n\n📞 <b>Business number:</b> {html.escape(str(lead.get('phone') or 'Not found'))}\n\n🎯 <b>What happened?</b> Choose the outcome below.", parse_mode="HTML", reply_markup=status_keyboard(bid))
    elif action == "follow":
        due = datetime.now(timezone.utc) + timedelta(days=3)
        await db.create_followup(bid, due, "Default 3-day follow-up")
        await db.record_activity(bid, "FOLLOWUP_CREATED", "telegram", f"Due {due.isoformat()}")
        await q.edit_message_text(f"⏰ <b>FOLLOW-UP CREATED</b>\n━━━━━━━━━━━━━━━━━━━━\n\n📅 Due: <b>{due.date()}</b>\n\n🔔 It is now in your follow-up list.", parse_mode="HTML", reply_markup=lead_keyboard(bid))
    elif action == "status":
        await q.edit_message_text("📝 <b>UPDATE LEAD STATUS</b>\n━━━━━━━━━━━━━━━━━━━━\n\nChoose what happened:", parse_mode="HTML", reply_markup=status_keyboard(bid))
    elif action == "setstatus":
        status = parts[2]
        await db.set_status(bid, status)
        await db.record_activity(bid, f"STATUS_{status}", "telegram", "Manual user update")
        if status == "CONTACTED":
            await db.record_activity(bid, "CALL_COMPLETED", "telegram", "User marked lead as called")
        await q.edit_message_text(f"✅ <b>STATUS UPDATED</b>\n━━━━━━━━━━━━━━━━━━━━\n\n🏢 {html.escape(lead['name'])}\n🧭 New status: <b>{html.escape(status)}</b>", parse_mode="HTML", reply_markup=lead_keyboard(bid))


def create_application(db: Database) -> Application:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required")
    app = Application.builder().token(token).build()
    app.bot_data["db"] = db
    for command, handler in [
        ("start", start), ("help", start), ("find", find_command), ("hot", hot_command),
        ("lead", lead_command), ("deal", deal_command), ("today", today_command),
        ("stats", stats_command), ("followups", followups_command),
    ]:
        app.add_handler(CommandHandler(command, handler))
    app.add_handler(CallbackQueryHandler(callbacks))
    return app
