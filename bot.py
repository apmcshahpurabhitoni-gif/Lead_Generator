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

BUSINESSES = [
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
    ("📞 Called", "CONTACTED"), ("💬 Responded", "RESPONDED"),
    ("📅 Meeting", "MEETING"), ("📄 Proposal", "PROPOSAL"),
    ("🤝 Negotiation", "NEGOTIATION"), ("💰 Won", "WON"),
    ("❌ Lost", "LOST"), ("🚫 Not interested", "NOT_INTERESTED"),
]


def authorized(update: Update) -> bool:
    admin = os.getenv("ADMIN_TELEGRAM_ID")
    return not admin or bool(update.effective_user and str(update.effective_user.id) == str(admin))


def button(label: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(label, callback_data=data)


def home_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [button("🏢 BUSINESSES", "businesses")],
        [button("🔎 FIND LEADS", "findmenu"), button("🔥 HOT LEADS", "hotmenu")],
        [button("📋 OPEN LEAD", "leadmenu"), button("💰 DEAL", "dealmenu")],
        [button("📅 TODAY", "todaymenu"), button("📈 STATS", "statsmenu")],
        [button("⏰ FOLLOW-UPS", "followmenu"), button("❓ HELP", "helpmenu")],
    ])


def business_keyboard(page: int = 0) -> InlineKeyboardMarkup:
    page = max(0, min(page, (len(BUSINESSES) - 1) // PAGE_SIZE))
    start = page * PAGE_SIZE
    items = BUSINESSES[start:start + PAGE_SIZE]
    rows = [[button(label, f"business:{key}")] for label, key in items]
    nav = []
    if page > 0:
        nav.append(button("⬅️ PREVIOUS", f"businesses:{page - 1}"))
    if start + PAGE_SIZE < len(BUSINESSES):
        nav.append(button("NEXT ➡️", f"businesses:{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append([button("🏠 MAIN MENU", "home")])
    return InlineKeyboardMarkup(rows)


def city_keyboard(industry: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [button("📍 JABALPUR", f"search:Jabalpur:{industry}")],
        [button("✏️ OTHER CITY", f"othercity:{industry}")],
        [button("⬅️ BUSINESSES", "businesses")],
    ])


def lead_keyboard(bid: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [button("📋 AUDIT", f"audit:{bid}"), button("💬 MESSAGE", f"msg:{bid}")],
        [button("📞 CALL", f"call:{bid}"), button("⏰ FOLLOW-UP", f"follow:{bid}")],
        [button("💰 DEAL", f"deal:{bid}"), button("📝 STATUS", f"status:{bid}")],
        [button("🕘 HISTORY", f"history:{bid}")],
        [button("🏠 MAIN MENU", "home")],
    ])


def status_keyboard(bid: int) -> InlineKeyboardMarkup:
    buttons = [button(label, f"setstatus:{bid}:{status}") for label, status in STATUS_OPTIONS]
    return InlineKeyboardMarkup(
        [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
        + [[button("⬅️ LEAD", f"lead:{bid}")]]
    )


def score_icon(score: int) -> str:
    return "🔥" if score >= 80 else "🟠" if score >= 60 else "🟡" if score >= 40 else "⚪"


def business_label(key: str) -> str:
    return next((x[0] for x in BUSINESSES if x[1] == key), key.title())


def format_lead(lead: dict) -> str:
    score = int(lead.get("score", 0) or 0)
    services = ", ".join(lead.get("recommended_services") or []) or "—"
    problems = "\n".join(
        f"🔴 {html.escape(str(x))}" for x in (lead.get("problems") or [])[:8]
    ) or "✅ No stored problems yet."
    return (
        f"{score_icon(score)} <b>{html.escape(str(lead.get('name', 'Unnamed Business')))}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"📍 <b>Location:</b> {html.escape(str(lead.get('city') or '—'))}\n"
        f"🏢 <b>Business:</b> {html.escape(str(lead.get('industry') or '—'))}\n"
        f"🌐 <b>Website:</b> {html.escape(str(lead.get('website') or 'Not found'))}\n"
        f"📞 <b>Phone:</b> {html.escape(str(lead.get('phone') or 'Not found'))}\n\n"
        f"🎯 <b>Score:</b> {score}/100\n"
        f"📌 <b>Priority:</b> {html.escape(str(lead.get('priority') or '—'))}\n"
        f"🧭 <b>Status:</b> {html.escape(str(lead.get('status') or 'NEW'))}\n"
        f"💼 <b>Recommended:</b> {html.escape(services)}\n\n"
        "🚨 <b>PROBLEMS / EVIDENCE</b>\n" + problems
    )


async def send_home(update: Update) -> None:
    await update.message.reply_text(
        "🚀 <b>LEADHUNTER</b>\n"
        "<i>Lead generation & sales command center</i>\n\n"
        "Choose an action below. <b>You do not need to remember any command.</b>\n\n"
        "🏢 <b>BUSINESSES</b> = the complete business-type directory\n"
        "🔎 <b>FIND LEADS</b> = discover new prospects",
        parse_mode="HTML", reply_markup=home_keyboard()
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if authorized(update):
        await send_home(update)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return
    await update.message.reply_text(
        "❓ <b>HOW TO USE LEADHUNTER</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "🏢 <b>BUSINESSES</b> — opens the complete business list.\n"
        "🔎 <b>FIND LEADS</b> — choose a business type and city.\n"
        "🔥 <b>HOT LEADS</b> — shows the highest-priority prospects.\n"
        "📋 <b>OPEN LEAD</b> — opens a lead by ID or from a lead list.\n"
        "💬 <b>MESSAGE</b> — creates a personalized WhatsApp draft for manual sending.\n"
        "📞 <b>CALL</b> — records the outcome of your manual call.\n"
        "⏰ <b>FOLLOW-UP</b> — creates a follow-up reminder.\n"
        "💰 <b>DEAL</b> — records deal value and stage.\n"
        "📅 <b>TODAY</b> — shows today's activity.\n"
        "📈 <b>STATS</b> — shows recent history.\n\n"
        "🔐 <b>Privacy rule:</b> WhatsApp/email are never automatically sent or tracked.",
        parse_mode="HTML", reply_markup=home_keyboard()
    )


async def send_businesses(target, page: int = 0):
    total_pages = (len(BUSINESSES) + PAGE_SIZE - 1) // PAGE_SIZE
    page = max(0, min(page, total_pages - 1))
    start = page * PAGE_SIZE
    end = min(start + PAGE_SIZE, len(BUSINESSES))
    await target.edit_message_text(
        "🏢 <b>BUSINESSES</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "Select a business type to prospect.\n"
        "<b>No typing required.</b>\n\n"
        f"📚 Showing <b>{start + 1}–{end}</b> of <b>{len(BUSINESSES)}</b>\n"
        f"📄 Page <b>{page + 1}/{total_pages}</b>",
        parse_mode="HTML", reply_markup=business_keyboard(page)
    )


async def run_find(app: Application, city: str, industry: str, chat_id: int):
    db: Database = app.bot_data["db"]
    job_id = await db.create_job("DISCOVERY", city, industry)
    processed = succeeded = failed = 0
    try:
        candidates = await discover_businesses(city, industry, 50)
        if not candidates:
            if job_id:
                await db.finish_job(job_id, 0, 0, 0)
            await app.bot.send_message(
                chat_id,
                "❌ <b>NO RESULTS</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
                f"📍 {html.escape(city)}\n"
                f"🏢 {html.escape(business_label(industry))}\n\n"
                "Try another business type or city.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([
                    [button("🏢 BUSINESSES", "businesses")],
                    [button("🏠 MAIN MENU", "home")],
                ])
            )
            return

        for candidate in candidates:
            processed += 1
            bid = None
            try:
                bid, _ = await db.upsert_business(candidate)
                if bid and processed <= MAX_RESEARCH_PER_SEARCH:
                    research = await research_business(candidate)
                    await db.save_research_and_score(bid, research, score_lead(research))
                if bid:
                    succeeded += 1
                else:
                    failed += 1
            except Exception as exc:
                failed += 1
                log.exception("Lead processing failed")
                if bid:
                    await db.record_activity(bid, "PROCESSING_FAILED", "system", str(exc))

        if job_id:
            await db.finish_job(job_id, processed, succeeded, failed)

        await app.bot.send_message(
            chat_id,
            "✅ <b>SEARCH COMPLETE</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📍 <b>City:</b> {html.escape(city)}\n"
            f"🏢 <b>Business:</b> {html.escape(business_label(industry))}\n\n"
            f"📥 <b>Found:</b> {len(candidates)}\n"
            f"🧪 <b>Deep researched:</b> {min(len(candidates), MAX_RESEARCH_PER_SEARCH)}\n"
            f"💾 <b>Saved:</b> {succeeded}\n"
            f"⚠️ <b>Failed:</b> {failed}",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [button("🔥 HOT LEADS", "hotmenu"), button("🏢 BUSINESSES", "businesses")],
                [button("🏠 MAIN MENU", "home")],
            ])
        )
    except Exception as exc:
        if job_id:
            await db.finish_job(job_id, processed, succeeded, failed, str(exc)[:1000])
        await app.bot.send_message(
            chat_id,
            "❌ <b>SEARCH FAILED</b>\n\n" + html.escape(str(exc)[:800]),
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [button("🏢 BUSINESSES", "businesses")],
                [button("🏠 MAIN MENU", "home")],
            ])
        )


async def find_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return
    if len(context.args) < 2:
        await update.message.reply_text(
            "🔎 <b>FIND LEADS</b>\n\nChoose a business type below, then choose the city.",
            parse_mode="HTML", reply_markup=business_keyboard(0)
        )
        return
    city, industry = context.args[0], " ".join(context.args[1:])
    await update.message.reply_text(
        "🔎 <b>SEARCH QUEUED</b>\n━━━━━━━━━━━━━━━━━━━━\n"
        f"📍 {html.escape(city)}\n🏢 {html.escape(industry)}\n\n"
        "⏳ Research is running in the background.",
        parse_mode="HTML", reply_markup=InlineKeyboardMarkup([[button("🏠 MAIN MENU", "home")]])
    )
    context.application.create_task(
        run_find(context.application, city, industry, update.effective_chat.id), update=update
    )


async def hot_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if authorized(update):
        await show_hot(update.message, context.application)


async def show_hot(target, app: Application, page: int = 0):
    db = app.bot_data["db"]
    leads = await db.list_leads("HOT", PAGE_SIZE + 1, page * PAGE_SIZE)
    if not leads and page > 0:
        page -= 1
        leads = await db.list_leads("HOT", PAGE_SIZE + 1, page * PAGE_SIZE)
    if not leads:
        await target.reply_text(
            "🔥 <b>HOT LEADS</b>\n\nNo hot leads yet. Run a search to find prospects.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [button("🔎 FIND LEADS", "findmenu")], [button("🏠 MAIN MENU", "home")]
            ])
        )
        return
    has_next = len(leads) > PAGE_SIZE
    leads = leads[:PAGE_SIZE]
    body = "\n".join(
        f"{score_icon(int(x.get('score', 0) or 0))} <b>{html.escape(str(x['name']))}</b> · {x.get('score', 0)}/100\n"
        f"📍 {html.escape(str(x.get('city') or '—'))}" for x in leads
    )
    kb = [[button(f"{score_icon(int(x.get('score', 0) or 0))} {str(x['name'])[:26]}", f"lead:{x['id']}")] for x in leads]
    nav = []
    if page > 0:
        nav.append(button("⬅️ PREVIOUS", f"page:HOT:{page - 1}"))
    if has_next:
        nav.append(button("NEXT ➡️", f"page:HOT:{page + 1}"))
    if nav:
        kb.append(nav)
    kb.append([button("🏢 BUSINESSES", "businesses"), button("🏠 MENU", "home")])
    await target.reply_text(
        f"🔥 <b>HOT LEADS</b> · PAGE {page + 1}\n━━━━━━━━━━━━━━━━━━━━\n\n{body}",
        parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb)
    )


async def lead_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text(
            "📋 <b>OPEN LEAD</b>\n\nOpen a lead from <b>HOT LEADS</b>, or enter:\n<code>/lead 123</code>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [button("🔥 HOT LEADS", "hotmenu")], [button("🏠 MAIN MENU", "home")]
            ])
        )
        return
    await show_lead(update.message, context.application, int(context.args[0]))


async def show_lead(target, app: Application, bid: int):
    db = app.bot_data["db"]
    lead = await db.get_lead(bid)
    if not lead:
        await target.reply_text(
            "❌ <b>LEAD NOT FOUND</b>\n\nCheck the lead ID and try again.",
            parse_mode="HTML", reply_markup=home_keyboard()
        )
        return
    await target.reply_text(
        format_lead(lead), parse_mode="HTML", reply_markup=lead_keyboard(bid), disable_web_page_preview=True
    )


async def deal_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return
    if len(context.args) < 4 or not context.args[0].isdigit():
        await update.message.reply_text(
            "💰 <b>DEAL</b>\n\nRecord a deal using:\n"
            "<code>/deal LEAD_ID VALUE STAGE SERVICE1,SERVICE2</code>\n\n"
            "Example:\n<code>/deal 123 55000 PROPOSAL Website,SEO,GBP</code>",
            parse_mode="HTML", reply_markup=home_keyboard()
        )
        return
    try:
        bid = int(context.args[0])
        value = float(context.args[1])
        stage = context.args[2].upper()
        services = [s.strip() for s in " ".join(context.args[3:]).split(",") if s.strip()]
        if stage not in {"PROPOSAL", "NEGOTIATION", "WON", "LOST"}:
            raise ValueError("Stage must be PROPOSAL, NEGOTIATION, WON or LOST")
        db = context.application.bot_data["db"]
        if not await db.get_lead(bid):
            raise ValueError("Lead not found")
        deal_id = await db.upsert_deal(bid, value, services, stage)
        await db.record_activity(bid, "DEAL_UPDATED", "telegram", f"{stage} ₹{value:.0f}")
        if stage in {"WON", "LOST"}:
            await db.set_status(bid, stage)
        await update.message.reply_text(
            "💰 <b>DEAL SAVED</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🆔 <b>Deal:</b> {deal_id}\n"
            f"💵 <b>Value:</b> ₹{value:,.0f}\n"
            f"📌 <b>Stage:</b> {html.escape(stage)}\n"
            f"💼 <b>Services:</b> {html.escape(', '.join(services))}",
            parse_mode="HTML", reply_markup=home_keyboard()
        )
    except Exception as exc:
        await update.message.reply_text(
            f"❌ <b>DEAL NOT SAVED</b>\n\n{html.escape(str(exc))}",
            parse_mode="HTML", reply_markup=home_keyboard()
        )


async def today_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if authorized(update):
        await show_today(update.message, context.application)


async def show_today(target, app: Application):
    stats = await app.bot_data["db"].today_stats()
    body = "\n".join(
        f"• {html.escape(str(k).replace('_', ' ').title())}: <b>{v}</b>" for k, v in stats.items()
    ) or "No activity recorded yet."
    await target.reply_text(
        "📅 <b>TODAY</b>\n━━━━━━━━━━━━━━━━━━━━\n\n" + body,
        parse_mode="HTML", reply_markup=home_keyboard()
    )


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if authorized(update):
        await show_stats(update.message, context.application)


async def show_stats(target, app: Application):
    rows = await app.bot_data["db"].history(14)
    body = "\n".join(
        f"📅 {r['date']} · 🔎 {r.get('leads_found', 0)} · 📞 {r.get('calls', 0)} · 📅 {r.get('meetings', 0)} · 💰 {r.get('won', 0)}"
        for r in rows
    ) or "No history yet."
    await target.reply_text(
        "📈 <b>14-DAY HISTORY</b>\n━━━━━━━━━━━━━━━━━━━━\n\n" + body,
        parse_mode="HTML", reply_markup=home_keyboard()
    )


async def followups_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if authorized(update):
        await show_followups(update.message, context.application)


async def show_followups(target, app: Application):
    rows = await app.bot_data["db"].due_followups(10)
    body = "\n".join(
        f"⏰ <b>{html.escape(r['business_name'])}</b> · {html.escape(str(r['due_at']))}" for r in rows
    ) or "✅ Nothing is due right now."
    kb = [[button(f"⏰ {r['business_name'][:25]}", f"lead:{r['business_id']}")] for r in rows]
    kb.append([button("🏠 MAIN MENU", "home")])
    await target.reply_text(
        "⏰ <b>FOLLOW-UPS</b>\n━━━━━━━━━━━━━━━━━━━━\n\n" + body,
        parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb)
    )


async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if not authorized(update):
        await q.answer()
        return
    await q.answer()
    db = context.application.bot_data["db"]
    parts = q.data.split(":")
    action = parts[0]

    if action == "home":
        await q.edit_message_text("🚀 <b>LEADHUNTER</b>\n\nChoose an action below:", parse_mode="HTML", reply_markup=home_keyboard())
        return
    if action == "businesses":
        page = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
        await send_businesses(q, page)
        return
    if action == "business":
        industry = ":".join(parts[1:])
        await q.edit_message_text(
            f"🏢 <b>{html.escape(business_label(industry))}</b>\n━━━━━━━━━━━━━━━━━━━━\n\n📍 <b>Choose where to search:</b>",
            parse_mode="HTML", reply_markup=city_keyboard(industry)
        )
        return
    if action == "findmenu":
        await q.edit_message_text(
            "🔎 <b>FIND LEADS</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
            "First choose a business type.\nThen choose the city.\n\n"
            "⏳ The search and research will run in the background.",
            parse_mode="HTML", reply_markup=business_keyboard(0)
        )
        return
    if action == "search":
        city = parts[1]
        industry = ":".join(parts[2:])
        await q.edit_message_text(
            "🔎 <b>SEARCH STARTED</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📍 <b>City:</b> {html.escape(city)}\n"
            f"🏢 <b>Business:</b> {html.escape(business_label(industry))}\n\n"
            "⏳ <b>Research is running in the background.</b>\n"
            "I will send the results here when complete.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[button("🏢 BUSINESSES", "businesses"), button("🏠 MENU", "home")]])
        )
        context.application.create_task(run_find(context.application, city, industry, q.message.chat_id), update=update)
        return
    if action == "othercity":
        industry = ":".join(parts[1:])
        await q.edit_message_text(
            "✏️ <b>OTHER CITY</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
            "Type the city using:\n"
            f"<code>/find CITY {html.escape(industry)}</code>\n\n"
            "Example:\n"
            f"<code>/find indore {html.escape(industry)}</code>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[button("⬅️ BUSINESSES", "businesses")], [button("🏠 MAIN MENU", "home")]])
        )
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
    if action == "leadmenu":
        await q.edit_message_text(
            "📋 <b>OPEN LEAD</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
            "Open a lead from a list below, or use:\n<code>/lead LEAD_ID</code>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[button("🔥 HOT LEADS", "hotmenu")], [button("🏠 MAIN MENU", "home")]])
        )
        return
    if action == "dealmenu":
        await q.edit_message_text(
            "💰 <b>DEAL</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
            "Record a deal using:\n<code>/deal LEAD_ID VALUE STAGE SERVICE1,SERVICE2</code>\n\n"
            "Example:\n<code>/deal 123 55000 PROPOSAL Website,SEO,GBP</code>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[button("🔥 HOT LEADS", "hotmenu")], [button("🏠 MAIN MENU", "home")]])
        )
        return
    if action == "helpmenu":
        await q.edit_message_text(
            "❓ <b>HELP</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
            "🏢 Businesses = complete business directory\n"
            "🔎 Find Leads = discover prospects\n"
            "🔥 Hot Leads = highest-priority leads\n"
            "📋 Open Lead = open a lead\n"
            "💰 Deal = record sales pipeline\n"
            "📅 Today = today's activity\n"
            "📈 Stats = recent history\n"
            "⏰ Follow-ups = due follow-ups\n\n"
            "💬 Messages are drafts for manual WhatsApp sending only.",
            parse_mode="HTML", reply_markup=home_keyboard()
        )
        return
    if action == "page":
        priority = parts[1]
        page = int(parts[2])
        leads = await db.list_leads(priority, PAGE_SIZE + 1, page * PAGE_SIZE)
        has_next = len(leads) > PAGE_SIZE
        leads = leads[:PAGE_SIZE]
        kb = [[button(f"{score_icon(int(x.get('score', 0) or 0))} {str(x['name'])[:26]}", f"lead:{x['id']}")] for x in leads]
        nav = []
        if page:
            nav.append(button("⬅️ PREVIOUS", f"page:{priority}:{page - 1}"))
        if has_next:
            nav.append(button("NEXT ➡️", f"page:{priority}:{page + 1}"))
        if nav:
            kb.append(nav)
        kb.append([button("🏠 MENU", "home")])
        body = "\n".join(
            f"{score_icon(int(x.get('score', 0) or 0))} {html.escape(str(x['name']))} — {x.get('score', 0)}/100" for x in leads
        ) or "No leads on this page."
        await q.edit_message_text(
            f"🔥 <b>{html.escape(priority)} LEADS · PAGE {page + 1}</b>\n━━━━━━━━━━━━━━━━━━━━\n\n" + body,
            parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb)
        )
        return

    if len(parts) < 2 or not parts[1].isdigit():
        return
    bid = int(parts[1])
    lead = await db.get_lead(bid)
    if not lead:
        await q.edit_message_text("❌ <b>LEAD NOT FOUND</b>\n\nCheck the lead ID and try again.", parse_mode="HTML", reply_markup=home_keyboard())
        return

    if action == "lead":
        await q.edit_message_text(format_lead(lead), parse_mode="HTML", reply_markup=lead_keyboard(bid), disable_web_page_preview=True)
    elif action == "audit":
        await db.record_activity(bid, "AUDIT_VIEWED", "telegram", "Online audit viewed")
        await q.edit_message_text(
            f"📋 <b>ONLINE AUDIT</b>\n<b>{html.escape(lead['name'])}</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{html.escape(db.format_research(await db.get_research(bid)))}",
            parse_mode="HTML", reply_markup=lead_keyboard(bid)
        )
    elif action == "history":
        rows = await db.activities(bid, 20)
        body = "\n".join(
            f"🕘 {html.escape(str(r['created_at']))} · <b>{html.escape(str(r['action']))}</b> · {html.escape(str(r.get('notes') or ''))}" for r in rows
        ) or "No activity yet."
        await q.edit_message_text("🕘 <b>HISTORY</b>\n━━━━━━━━━━━━━━━━━━━━\n\n" + body, parse_mode="HTML", reply_markup=lead_keyboard(bid))
    elif action == "deal":
        await q.edit_message_text(
            "💰 <b>DEAL</b>\n\nUse:\n<code>/deal LEAD_ID VALUE STAGE SERVICE1,SERVICE2</code>\n\n"
            "Example:\n<code>/deal 123 55000 PROPOSAL Website,SEO,GBP</code>",
            parse_mode="HTML", reply_markup=lead_keyboard(bid)
        )
    elif action == "msg":
        try:
            draft = await generate_whatsapp_message(lead, await db.get_research(bid))
            await db.record_activity(bid, "MESSAGE_DRAFT_GENERATED", "telegram", "WhatsApp draft generated")
            await q.edit_message_text(
                "💬 <b>PERSONALIZED WHATSAPP DRAFT</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
                f"{html.escape(draft)}\n\n📋 <b>Copy and send manually.</b>\n"
                "🔐 No WhatsApp/email sending or tracking.",
                parse_mode="HTML", reply_markup=lead_keyboard(bid)
            )
        except Exception as exc:
            await q.edit_message_text(
                "❌ <b>MESSAGE GENERATION FAILED</b>\n\n" + html.escape(str(exc)[:500]),
                parse_mode="HTML", reply_markup=lead_keyboard(bid)
            )
    elif action == "call":
        await db.record_activity(bid, "CALL_WORKFLOW_OPENED", "telegram", "User opened call workflow")
        await q.edit_message_text(
            f"📞 <b>CALL</b>\n<b>{html.escape(lead['name'])}</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📞 <b>Phone:</b> {html.escape(str(lead.get('phone') or 'Not found'))}\n\nChoose the outcome:",
            parse_mode="HTML", reply_markup=status_keyboard(bid)
        )
    elif action == "follow":
        due = datetime.now(timezone.utc) + timedelta(days=3)
        await db.create_followup(bid, due, "Default 3-day follow-up")
        await db.record_activity(bid, "FOLLOWUP_CREATED", "telegram", f"Follow-up due {due.isoformat()}")
        await q.edit_message_text(
            "⏰ <b>FOLLOW-UP CREATED</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🏢 <b>Business:</b> {html.escape(lead['name'])}\n"
            f"📅 <b>Due:</b> {due.date()}\n\nYou can see it in FOLLOW-UPS.",
            parse_mode="HTML", reply_markup=lead_keyboard(bid)
        )
    elif action == "status":
        await q.edit_message_text(
            "📝 <b>STATUS</b>\n━━━━━━━━━━━━━━━━━━━━\n\nChoose the new status:",
            parse_mode="HTML", reply_markup=status_keyboard(bid)
        )
    elif action == "setstatus" and len(parts) >= 3:
        status = parts[2]
        await db.set_status(bid, status)
        await db.record_activity(bid, f"STATUS_{status}", "telegram", "Manual user update")
        if status == "CONTACTED":
            await db.record_activity(bid, "CALL_COMPLETED", "telegram", "Call marked as completed")
        await q.edit_message_text(
            "✅ <b>STATUS UPDATED</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🏢 <b>Business:</b> {html.escape(lead['name'])}\n"
            f"🧭 <b>Status:</b> {html.escape(status)}",
            parse_mode="HTML", reply_markup=lead_keyboard(bid)
        )


def create_application(db: Database) -> Application:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required")
    app = Application.builder().token(token).build()
    app.bot_data["db"] = db
    for command, handler in [
        ("start", start), ("help", help_command), ("find", find_command),
        ("hot", hot_command), ("lead", lead_command), ("deal", deal_command),
        ("today", today_command), ("stats", stats_command), ("followups", followups_command),
    ]:
        app.add_handler(CommandHandler(command, handler))
    app.add_handler(CallbackQueryHandler(callbacks))
    return app
