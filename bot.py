import html
import logging
import os
from datetime import datetime, timedelta, timezone

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler

from database import Database
from discovery import discover_businesses
from research import research_business
from scoring import score_lead
from ai import generate_whatsapp_message

log = logging.getLogger(__name__)
PAGE_SIZE = 8
MAX_RESEARCH_PER_SEARCH = 5

BUSINESSES = [
    ("🦷 Dental / Dentist", "dental"), ("🏥 Hospital", "hospital"),
    ("🩺 Clinic", "clinic"), ("🍽️ Restaurant", "restaurant"),
    ("☕ Cafe", "cafe"), ("🥐 Bakery", "bakery"), ("🏨 Hotel", "hotel"),
    ("🌴 Resort", "resort"), ("🎓 School", "school"), ("🏫 College", "college"),
    ("🎓 University", "university"), ("💊 Pharmacy", "pharmacy"),
    ("🏋️ Gym / Fitness", "gym"), ("💇 Salon", "salon"), ("💄 Beauty", "beauty"),
    ("🚗 Car Dealer", "car dealer"), ("🔧 Car Repair", "car repair"),
    ("🚿 Car Wash", "car wash"), ("🏠 Real Estate", "real estate"),
    ("⚖️ Lawyer", "lawyer"), ("🧾 Accountant", "accountant"),
    ("✈️ Travel Agency", "travel agency"), ("📱 Electronics", "electronics"),
    ("👕 Clothing", "clothing"), ("🛋️ Furniture", "furniture"),
    ("💎 Jewellery", "jewellery"), ("🛒 Supermarket", "supermarket"),
    ("🔨 Hardware", "hardware"), ("🏦 Bank", "bank"), ("🛡️ Insurance", "insurance"),
    ("🏛️ Architect", "architect"), ("🏗️ Construction", "construction"),
    ("🖨️ Printing", "printing"), ("📸 Photographer", "photographer"),
    ("⛽ Fuel Station", "fuel"), ("🐾 Veterinary", "veterinary"),
    ("🌐 All Supported Businesses", "all"),
]

STATUS_OPTIONS = [
    ("📞 Called", "CONTACTED"), ("💬 Responded", "RESPONDED"),
    ("📅 Meeting", "MEETING"), ("📄 Proposal", "PROPOSAL"),
    ("🤝 Negotiation", "NEGOTIATION"), ("💰 Won", "WON"),
    ("❌ Lost", "LOST"), ("🚫 Not interested", "NOT_INTERESTED"),
]


def authorized(update):
    admin = os.getenv("ADMIN_TELEGRAM_ID", "").strip()
    return not admin or (update.effective_user and str(update.effective_user.id) == admin)


def B(text, data):
    return InlineKeyboardButton(text=text, callback_data=data)


def menu():
    return InlineKeyboardMarkup([
        [B("🏢 BUSINESSES", "ui:biz:0"), B("📚 SAVED LEADS", "ui:saved:0")],
        [B("🔎 FIND LEADS", "ui:biz:0")],
        [B("🔥 HOT LEADS", "ui:hot:0")],
        [B("📋 OPEN LEAD", "ui:open")],
        [B("💰 DEAL PIPELINE", "ui:deal")],
        [B("📅 TODAY", "ui:today"), B("📈 STATS", "ui:stats")],
        [B("⏰ FOLLOW-UPS", "ui:follow")],
        [B("❓ HELP", "ui:help")],
    ])


def biz_menu(page=0):
    pages = max(1, (len(BUSINESSES) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, pages - 1))
    start = page * PAGE_SIZE
    rows = [[B(label, f"ui:industry:{key}")] for label, key in BUSINESSES[start:start + PAGE_SIZE]]
    nav = []
    if page:
        nav.append(B("⬅️ PREVIOUS", f"ui:biz:{page - 1}"))
    if page < pages - 1:
        nav.append(B("NEXT ➡️", f"ui:biz:{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append([B("🏠 MAIN MENU", "ui:home")])
    return InlineKeyboardMarkup(rows)


def city_menu(industry):
    return InlineKeyboardMarkup([
        [B("📍 JABALPUR", f"ui:search:Jabalpur:{industry}")],
        [B("✏️ OTHER CITY", f"ui:other:{industry}")],
        [B("⬅️ BUSINESSES", "ui:biz:0"), B("🏠 MAIN MENU", "ui:home")],
    ])


def lead_menu(lead):
    bid = lead["id"]
    rows = []
    website = str(lead.get("website") or "").strip()
    if website.startswith(("http://", "https://")):
        rows.append([InlineKeyboardButton("🌐 OPEN WEBSITE", url=website)])
    rows.extend([
        [B("📋 FULL AUDIT", f"ui:audit:{bid}"), B("💬 MESSAGE", f"ui:message:{bid}")],
        [B("📞 CALL RECORDED", f"ui:call:{bid}"), B("⏰ FOLLOW-UP", f"ui:followlead:{bid}")],
        [B("💰 DEAL", f"ui:deallead:{bid}"), B("📝 STATUS", f"ui:status:{bid}")],
        [B("🕘 HISTORY", f"ui:history:{bid}")],
        [B("📚 SAVED LEADS", "ui:saved:0"), B("🏠 MAIN MENU", "ui:home")],
    ])
    return InlineKeyboardMarkup(rows)


def score_icon(score):
    score = int(score or 0)
    return "🔥" if score >= 80 else "🟠" if score >= 60 else "🟡" if score >= 40 else "⚪"


def industry_label(key):
    return next((x[0] for x in BUSINESSES if x[1] == key), str(key).title())


def short(value, limit=42):
    text = str(value or "—").strip()
    return text if len(text) <= limit else text[:limit - 1] + "…"


def lead_list_line(index, lead):
    name = html.escape(short(lead.get("name", "Unnamed Business"), 34))
    score = int(lead.get("score", 0) or 0)
    phone = short(lead.get("phone"), 18)
    website = short(lead.get("website"), 25) if lead.get("website") else "No website"
    return f"<b>{index}.</b> {score_icon(score)} <b>{name}</b> · <b>{score}/100</b>\n   📞 {html.escape(phone)} · 🌐 {html.escape(website)}"


def lead_text(lead):
    problems = "\n".join(
        "🔴 " + html.escape(str(problem)) for problem in (lead.get("problems") or [])[:8]
    ) or "✅ No stored problems."
    services = ", ".join(lead.get("recommended_services") or []) or "—"
    score = int(lead.get("score", 0) or 0)
    bid = html.escape(str(lead.get("id", "—")))
    return (
        f"{score_icon(score)} <b>{html.escape(str(lead.get('name', 'Unnamed Business')))}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🆔 <b>Lead #:</b> {bid}\n"
        f"📍 <b>Location:</b> {html.escape(str(lead.get('city') or '—'))}\n"
        f"🏢 <b>Business:</b> {html.escape(str(lead.get('industry') or '—'))}\n"
        f"🌐 <b>Website:</b> {html.escape(str(lead.get('website') or 'Not found'))}\n"
        f"📞 <b>Phone:</b> {html.escape(str(lead.get('phone') or 'Not found'))}\n\n"
        f"🎯 <b>Opportunity Score:</b> {score}/100\n"
        f"📌 <b>Priority:</b> {html.escape(str(lead.get('priority') or '—'))}\n"
        f"🧭 <b>Status:</b> {html.escape(str(lead.get('status') or 'NEW'))}\n"
        f"💼 <b>Recommended Services:</b> {html.escape(services)}\n\n"
        f"🚨 <b>PROBLEMS / EVIDENCE</b>\n{problems}\n\n"
        f"👇 <b>Use the buttons below to work this lead.</b>"
    )


async def edit_or_reply(target, text, reply_markup=None, parse_mode="HTML"):
    try:
        await target.edit_message_text(
            text,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
            disable_web_page_preview=True,
        )
        return
    except Exception as exc:
        log.warning("Telegram edit failed; sending fallback message: %s", exc)
    message = getattr(target, "message", None)
    if message:
        await message.reply_text(
            text,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
            disable_web_page_preview=True,
        )


async def start(update, context):
    if authorized(update):
        await update.effective_message.reply_text(
            "🚀 <b>LEADHUNTER</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
            "👋 Welcome!\n🎯 Discover → research → score → contact manually.\n\n"
            "👇 <b>Choose an action:</b>",
            parse_mode="HTML", reply_markup=menu(),
        )


async def help_command(update, context):
    if authorized(update):
        await update.effective_message.reply_text(
            "❓ <b>LEADHUNTER HELP</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
            "🏢 <b>Businesses</b> — browse supported categories\n"
            "🔎 <b>Find Leads</b> — discover and research prospects\n"
            "📚 <b>Saved Leads</b> — every saved business\n"
            "🔥 <b>Hot Leads</b> — highest-priority leads\n"
            "📋 <b>Open Lead</b> — open a lead by ID\n"
            "💬 <b>Message</b> — generate a WhatsApp draft only\n"
            "📞 <b>Call Recorded</b> — manually record a call\n"
            "⏰ <b>Follow-up</b> — create a reminder\n"
            "💰 <b>Deal</b> — open/manage pipeline\n\n"
            "🔐 WhatsApp and email are <b>never automatically sent or tracked</b>.",
            parse_mode="HTML", reply_markup=menu(),
        )


async def show_biz(q, page=0):
    pages = max(1, (len(BUSINESSES) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, pages - 1))
    start = page * PAGE_SIZE
    end = min(start + PAGE_SIZE, len(BUSINESSES))
    await q.edit_message_text(
        f"🏢 <b>BUSINESSES</b>\n━━━━━━━━━━━━━━━━━━━━\n"
        f"📚 Showing <b>{start + 1}–{end}</b> of <b>{len(BUSINESSES)}</b>\n"
        f"📄 Page <b>{page + 1}/{pages}</b>\n\n👇 Select a business type:",
        parse_mode="HTML", reply_markup=biz_menu(page),
    )


async def show_lead(target, app, bid, edit=True):
    lead = await app.bot_data["db"].get_lead(bid)
    if not lead:
        text = "❌ <b>LEAD NOT FOUND</b>\n\nThe saved lead may have been removed."
        if edit:
            await edit_or_reply(target, text, menu())
        else:
            await target.reply_text(text, parse_mode="HTML", reply_markup=menu())
        return
    if edit:
        await edit_or_reply(target, lead_text(lead), lead_menu(lead))
    else:
        await target.reply_text(lead_text(lead), parse_mode="HTML", reply_markup=lead_menu(lead), disable_web_page_preview=True)


async def show_results(q, app, city, industry, page=0):
    offset = page * PAGE_SIZE
    rows = await app.bot_data["db"].list_search_results(city, industry, PAGE_SIZE + 1, offset)
    more = len(rows) > PAGE_SIZE
    rows = rows[:PAGE_SIZE]
    if not rows:
        await q.edit_message_text(
            f"📋 <b>SEARCH RESULTS</b>\n━━━━━━━━━━━━━━━━━━━━\n\nNo saved leads found for <b>{html.escape(city)}</b> · <b>{html.escape(industry_label(industry))}</b>.",
            parse_mode="HTML", reply_markup=menu(),
        )
        return
    lines = [lead_list_line(offset + i + 1, lead) for i, lead in enumerate(rows)]
    await q.edit_message_text(
        f"📋 <b>SEARCH RESULTS</b>\n━━━━━━━━━━━━━━━━━━━━\n"
        f"📍 <b>{html.escape(city)}</b> · 🏢 <b>{html.escape(industry_label(industry))}</b>\n"
        f"📄 Leads <b>{offset + 1}–{offset + len(rows)}</b>\n\n"
        + "\n".join(lines) +
        "\n\n👇 <b>Tap a numbered lead below to OPEN ITS FULL PROFILE.</b>",
        parse_mode="HTML", reply_markup=result_menu(rows, city, industry, page, more, offset),
        disable_web_page_preview=True,
    )


def result_menu(rows, city, industry, page, more, offset=0):
    keyboard = []
    for i, lead in enumerate(rows):
        number = offset + i + 1
        label = f"{number}️⃣ {short(lead.get('name', 'Lead'), 30)} · {int(lead.get('score', 0) or 0)}/100"
        keyboard.append([B(label, f"ui:lead:{lead['id']}")])
    nav = []
    if page:
        nav.append(B("⬅️ PREVIOUS", f"ui:results:{city}:{industry}:{page - 1}"))
    if more:
        nav.append(B("NEXT ➡️", f"ui:results:{city}:{industry}:{page + 1}"))
    if nav:
        keyboard.append(nav)
    keyboard.append([B("📚 ALL SAVED", "ui:saved:0"), B("🏠 MAIN MENU", "ui:home")])
    return InlineKeyboardMarkup(keyboard)


async def show_saved(q, app, page=0):
    offset = page * PAGE_SIZE
    rows = await app.bot_data["db"].list_leads(None, PAGE_SIZE + 1, offset)
    more = len(rows) > PAGE_SIZE
    rows = rows[:PAGE_SIZE]
    if not rows:
        await q.edit_message_text(
            "📚 <b>SAVED LEADS</b>\n━━━━━━━━━━━━━━━━━━━━\n\nNo leads saved yet. Run a search first.",
            parse_mode="HTML", reply_markup=menu(),
        )
        return
    lines = [lead_list_line(offset + i + 1, lead) for i, lead in enumerate(rows)]
    keyboard = []
    for i, lead in enumerate(rows):
        number = offset + i + 1
        label = f"{number}️⃣ {short(lead.get('name', 'Lead'), 30)} · {int(lead.get('score', 0) or 0)}/100"
        keyboard.append([B(label, f"ui:lead:{lead['id']}")])
    nav = []
    if page:
        nav.append(B("⬅️ PREVIOUS", f"ui:saved:{page - 1}"))
    if more:
        nav.append(B("NEXT ➡️", f"ui:saved:{page + 1}"))
    if nav:
        keyboard.append(nav)
    keyboard.append([B("🏠 MAIN MENU", "ui:home")])
    await q.edit_message_text(
        f"📚 <b>SAVED LEADS · PAGE {page + 1}</b>\n━━━━━━━━━━━━━━━━━━━━\n"
        f"📄 Leads <b>{offset + 1}–{offset + len(rows)}</b>\n\n"
        + "\n".join(lines) +
        "\n\n👇 <b>Tap a numbered button to open the FULL lead.</b>",
        parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard), disable_web_page_preview=True,
    )


async def show_hot(q, app, page=0):
    rows = await app.bot_data["db"].list_leads("HOT", PAGE_SIZE + 1, page * PAGE_SIZE)
    more = len(rows) > PAGE_SIZE
    rows = rows[:PAGE_SIZE]
    if not rows:
        await q.edit_message_text(
            "🔥 <b>HOT LEADS</b>\n━━━━━━━━━━━━━━━━━━━━\n\nNo hot leads yet. Leads become HOT at 80+/100.",
            parse_mode="HTML", reply_markup=menu(),
        )
        return
    offset = page * PAGE_SIZE
    lines = [lead_list_line(offset + i + 1, lead) for i, lead in enumerate(rows)]
    keyboard = [[B(f"{offset + i + 1}️⃣ {short(lead.get('name'), 30)} · {int(lead.get('score', 0) or 0)}/100", f"ui:lead:{lead['id']}")] for i, lead in enumerate(rows)]
    nav = []
    if page:
        nav.append(B("⬅️ PREVIOUS", f"ui:hot:{page - 1}"))
    if more:
        nav.append(B("NEXT ➡️", f"ui:hot:{page + 1}"))
    if nav:
        keyboard.append(nav)
    keyboard.append([B("📚 SAVED LEADS", "ui:saved:0"), B("🏠 MAIN MENU", "ui:home")])
    await q.edit_message_text(
        f"🔥 <b>HOT LEADS · PAGE {page + 1}</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
        + "\n".join(lines) +
        "\n\n👇 <b>Tap a lead to open its full profile.</b>",
        parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard), disable_web_page_preview=True,
    )


async def run_find(app, city, industry, chat_id):
    db = app.bot_data["db"]
    job = await db.create_job("DISCOVERY", city, industry)
    saved = failed = 0
    try:
        candidates = await discover_businesses(city, industry, 50)
        for i, candidate in enumerate(candidates):
            try:
                bid, _ = await db.upsert_business(candidate)
                if bid and i < MAX_RESEARCH_PER_SEARCH:
                    research = await research_business(candidate)
                    await db.save_research_and_score(bid, research, score_lead(research))
                saved += 1 if bid else 0
                failed += 0 if bid else 1
            except Exception:
                failed += 1
                log.exception("lead processing failed")
        if job:
            await db.finish_job(job, len(candidates), saved, failed)
        await app.bot.send_message(
            chat_id,
            f"✅ <b>SEARCH COMPLETE</b>\n━━━━━━━━━━━━━━━━━━━━\n"
            f"📍 {html.escape(city)}\n🏢 {html.escape(industry_label(industry))}\n\n"
            f"📥 Found: <b>{len(candidates)}</b>\n🧪 Researched: <b>{min(len(candidates), MAX_RESEARCH_PER_SEARCH)}</b>\n"
            f"💾 Saved: <b>{saved}</b>\n⚠️ Failed: <b>{failed}</b>\n\n"
            "👇 <b>Open the saved leads below.</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [B(f"📋 OPEN {saved} SAVED LEADS", "ui:saved:0")],
                [B("🔥 HOT LEADS", "ui:hot:0"), B("🏠 MAIN MENU", "ui:home")],
            ]),
        )
    except Exception as exc:
        if job:
            await db.finish_job(job, 0, 0, 1, str(exc)[:1000])
        await app.bot.send_message(
            chat_id,
            "❌ <b>SEARCH FAILED</b>\n━━━━━━━━━━━━━━━━━━━━\n\n" + html.escape(str(exc)[:900]),
            parse_mode="HTML", reply_markup=menu(),
        )


async def find_command(update, context):
    if not authorized(update):
        return
    if len(context.args) < 2:
        await update.effective_message.reply_text(
            "🔎 <b>FIND LEADS</b>\n\nType:\n<code>/find Jabalpur dental</code>",
            parse_mode="HTML", reply_markup=biz_menu(),
        )
        return
    city = context.args[0]
    industry = " ".join(context.args[1:]).strip()
    await update.effective_message.reply_text(
        "🔎 <b>SEARCH STARTED</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
        "⏳ Research is running in the background.\n📬 Results will arrive here.",
        parse_mode="HTML", reply_markup=menu(),
    )
    context.application.create_task(run_find(context.application, city, industry, update.effective_chat.id), update=update)


async def lead_command(update, context):
    if authorized(update) and context.args and context.args[0].isdigit():
        await show_lead(update.effective_message, context.application, int(context.args[0]), False)


async def hot_command(update, context):
    if not authorized(update):
        return
    rows = await context.application.bot_data["db"].list_leads("HOT", PAGE_SIZE, 0)
    if not rows:
        await update.effective_message.reply_text("🔥 <b>HOT LEADS</b>\n\nNo hot leads yet.", parse_mode="HTML", reply_markup=menu())
        return
    keyboard = [[B(f"{i + 1}️⃣ {short(lead.get('name'), 30)} · {int(lead.get('score', 0) or 0)}/100", f"ui:lead:{lead['id']}")] for i, lead in enumerate(rows)]
    await update.effective_message.reply_text(
        "🔥 <b>HOT LEADS</b>\n━━━━━━━━━━━━━━━━━━━━\n\n" +
        "\n".join(lead_list_line(i + 1, lead) for i, lead in enumerate(rows)),
        parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard), disable_web_page_preview=True,
    )


async def today_command(update, context):
    if authorized(update):
        stats = await context.application.bot_data["db"].today_stats()
        body = "\n".join(f"• {html.escape(k.replace('_', ' ').title())}: <b>{v}</b>" for k, v in stats.items())
        await update.effective_message.reply_text("📅 <b>TODAY</b>\n━━━━━━━━━━━━━━━━━━━━\n\n" + body, parse_mode="HTML", reply_markup=menu())


async def stats_command(update, context):
    if authorized(update):
        rows = await context.application.bot_data["db"].history(14)
        body = "\n".join(f"📅 {r['date']} · 🔎 {r.get('leads_found', 0)} · 📞 {r.get('calls', 0)} · 💰 {r.get('won', 0)}" for r in rows) or "No history yet."
        await update.effective_message.reply_text("📈 <b>14-DAY HISTORY</b>\n━━━━━━━━━━━━━━━━━━━━\n\n" + body, parse_mode="HTML", reply_markup=menu())


async def followups_command(update, context):
    if authorized(update):
        rows = await context.application.bot_data["db"].due_followups(10)
        body = "\n".join(f"⏰ <b>{html.escape(str(r['business_name']))}</b> · {html.escape(str(r['due_at']))}" for r in rows) or "✅ Nothing is due right now."
        await update.effective_message.reply_text("⏰ <b>FOLLOW-UPS</b>\n━━━━━━━━━━━━━━━━━━━━\n\n" + body, parse_mode="HTML", reply_markup=menu())


async def callbacks(update, context):
    query = update.callback_query
    if not query:
        return
    if not authorized(update):
        await query.answer("Not authorized", show_alert=True)
        return
    try:
        await query.answer()
    except Exception:
        pass
    parts = (query.data or "").split(":")
    if len(parts) < 2 or parts[0] != "ui":
        return
    action = parts[1]
    app = context.application
    db = app.bot_data["db"]
    try:
        if action == "home":
            await query.edit_message_text("🚀 <b>LEADHUNTER</b>\n━━━━━━━━━━━━━━━━━━━━\n\n👇 <b>Choose an action:</b>", parse_mode="HTML", reply_markup=menu())
        elif action == "biz":
            await show_biz(query, int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0)
        elif action == "industry":
            key = ":".join(parts[2:])
            await query.edit_message_text(f"🏢 <b>{html.escape(industry_label(key))}</b>\n━━━━━━━━━━━━━━━━━━━━\n\n📍 <b>Choose where to search:</b>", parse_mode="HTML", reply_markup=city_menu(key))
        elif action == "search":
            city = parts[2]
            industry = ":".join(parts[3:])
            await query.edit_message_text("🔎 <b>SEARCH STARTED</b>\n━━━━━━━━━━━━━━━━━━━━\n\n⏳ Running in background…", parse_mode="HTML", reply_markup=menu())
            app.create_task(run_find(app, city, industry, query.message.chat_id), update=update)
        elif action == "other":
            industry = ":".join(parts[2:])
            await query.edit_message_text(f"✏️ <b>OTHER CITY</b>\n\nType:\n<code>/find CITY {html.escape(industry)}</code>", parse_mode="HTML", reply_markup=menu())
        elif action == "results":
            city = parts[2]
            industry = parts[3]
            page = int(parts[4]) if len(parts) > 4 and parts[4].isdigit() else 0
            await show_results(query, app, city, industry, page)
        elif action == "saved":
            page = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
            await show_saved(query, app, page)
        elif action == "hot":
            page = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
            await show_hot(query, app, page)
        elif action == "lead":
            await show_lead(query, app, int(parts[2]), True)
        elif action == "open":
            await query.edit_message_text("📋 <b>OPEN LEAD</b>\n━━━━━━━━━━━━━━━━━━━━\n\nUse <code>/lead LEAD_ID</code>, or open one from Saved Leads.", parse_mode="HTML", reply_markup=InlineKeyboardMarkup([[B("📚 SAVED LEADS", "ui:saved:0")], [B("🔥 HOT LEADS", "ui:hot:0")], [B("🏠 MAIN MENU", "ui:home")]]))
        elif action == "today":
            await today_command(update, context)
        elif action == "stats":
            await stats_command(update, context)
        elif action == "follow":
            await followups_command(update, context)
        elif action == "help":
            await help_command(update, context)
        elif action == "audit":
            bid = int(parts[2])
            research = await db.get_research(bid)
            lead = await db.get_lead(bid)
            await edit_or_reply(query, "📋 <b>FULL LEAD AUDIT</b>\n━━━━━━━━━━━━━━━━━━━━\n\n" + html.escape(db.format_research(research)), lead_menu(lead) if lead else menu())
        elif action == "message":
            bid = int(parts[2])
            lead = await db.get_lead(bid)
            research = await db.get_research(bid)
            if not lead:
                await edit_or_reply(query, "❌ <b>LEAD NOT FOUND</b>", menu())
                return
            try:
                draft = await generate_whatsapp_message(lead, research)
            except Exception as exc:
                log.warning("AI message failed: %s", exc)
                draft = "Unable to generate the AI draft right now. Use the audit findings to write manually."
            await db.record_activity(bid, "MESSAGE_DRAFTED", "telegram", "WhatsApp draft generated; not sent")
            await edit_or_reply(query, "💬 <b>WHATSAPP DRAFT</b>\n━━━━━━━━━━━━━━━━━━━━\n\n" + html.escape(draft) + "\n\n📌 <b>Copy → open WhatsApp → paste → send manually.</b>", lead_menu(lead))
        elif action == "call":
            bid = int(parts[2])
            lead = await db.get_lead(bid)
            await db.record_activity(bid, "CALL_COMPLETED", "telegram", "Manual call action recorded")
            await db.set_status(bid, "CONTACTED")
            await edit_or_reply(query, "📞 <b>CALL RECORDED</b>\n━━━━━━━━━━━━━━━━━━━━\n\n☎️ Phone: <b>" + html.escape(str((lead or {}).get("phone") or "Not found")) + "</b>\n\n📝 Status updated to <b>CONTACTED</b>.", lead_menu(lead) if lead else menu())
        elif action == "followlead":
            bid = int(parts[2])
            due = datetime.now(timezone.utc) + timedelta(days=1)
            await db.create_followup(bid, due, "Default follow-up created from Telegram")
            await db.record_activity(bid, "FOLLOWUP_CREATED", "telegram", f"Due {due.isoformat()}")
            lead = await db.get_lead(bid)
            await edit_or_reply(query, "⏰ <b>FOLLOW-UP CREATED</b>\n━━━━━━━━━━━━━━━━━━━━\n\n📅 Due: <b>tomorrow</b>\n🗂 Status: <b>OPEN</b>", lead_menu(lead) if lead else menu())
        elif action == "status":
            bid = int(parts[2])
            rows = [[B(label, f"ui:statusset:{bid}:{value}")] for label, value in STATUS_OPTIONS]
            rows.append([B("⬅️ LEAD", f"ui:lead:{bid}"), B("🏠 MENU", "ui:home")])
            await query.edit_message_text("📝 <b>UPDATE STATUS</b>\n━━━━━━━━━━━━━━━━━━━━\n\nChoose the new sales status:", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(rows))
        elif action == "statusset":
            bid = int(parts[2])
            status = parts[3]
            await db.set_status(bid, status)
            await db.record_activity(bid, "STATUS_" + status, "telegram", "Status updated from Telegram")
            await show_lead(query, app, bid, True)
        elif action == "history":
            bid = int(parts[2])
            rows = await db.activities(bid, 30)
            body = "\n".join(f"🕘 {html.escape(str(row.get('created_at', '')))[:19]} · <b>{html.escape(str(row.get('action', '')))}</b> · {html.escape(str(row.get('notes') or ''))}" for row in rows) or "No activity yet."
            lead = await db.get_lead(bid)
            await edit_or_reply(query, "🕘 <b>LEAD HISTORY</b>\n━━━━━━━━━━━━━━━━━━━━\n\n" + body, lead_menu(lead) if lead else menu())
        elif action == "deallead":
            bid = int(parts[2])
            await db.upsert_deal(bid, None, [], "PROPOSAL", "Deal opened from Telegram")
            await db.set_status(bid, "PROPOSAL")
            lead = await db.get_lead(bid)
            await edit_or_reply(query, "💰 <b>DEAL OPENED</b>\n━━━━━━━━━━━━━━━━━━━━\n\nStage: <b>PROPOSAL</b>\nValue: <b>Not set</b>", lead_menu(lead) if lead else menu())
        elif action == "deal":
            rows = await db.list_deals(20)
            body = "\n".join(f"💰 <b>{html.escape(str(row['business_name']))}</b> · {html.escape(str(row['stage']))} · ₹{row.get('value') or '—'}" for row in rows) or "No deals yet."
            await query.edit_message_text("💰 <b>DEAL PIPELINE</b>\n━━━━━━━━━━━━━━━━━━━━\n\n" + body, parse_mode="HTML", reply_markup=menu())
    except Exception as exc:
        log.exception("callback failed | data=%s", query.data)
        try:
            await edit_or_reply(query, "❌ <b>ACTION FAILED</b>\n━━━━━━━━━━━━━━━━━━━━\n\n" + html.escape(str(exc)[:700]), menu())
        except Exception:
            log.exception("failed to send callback error")


def create_application(db: Database):
    app = Application.builder().token(os.environ["TELEGRAM_BOT_TOKEN"]).build()
    app.bot_data["db"] = db
    app.add_handler(CallbackQueryHandler(callbacks))
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("find", find_command))
    app.add_handler(CommandHandler("lead", lead_command))
    app.add_handler(CommandHandler("hot", hot_command))
    app.add_handler(CommandHandler("today", today_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("followups", followups_command))
    return app
