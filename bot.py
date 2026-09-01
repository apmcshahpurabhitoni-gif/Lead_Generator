import html
import logging
import os
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes
from database import Database
from discovery import discover_businesses
from research import research_business
from scoring import score_lead

log = logging.getLogger(__name__)
PAGE_SIZE = 8
MAX_RESEARCH_PER_SEARCH = 10
BUSINESSES = [
("🦷 Dental / Dentist","dental"),("🏥 Hospital","hospital"),("🩺 Clinic","clinic"),("🍽️ Restaurant","restaurant"),("☕ Cafe","cafe"),("🥐 Bakery","bakery"),("🏨 Hotel","hotel"),("🌴 Resort","resort"),
("🎓 School","school"),("🏫 College","college"),("🎓 University","university"),("💊 Pharmacy","pharmacy"),("🏋️ Gym / Fitness","gym"),("💇 Salon","salon"),("💄 Beauty","beauty"),("🚗 Car Dealer","car dealer"),
("🔧 Car Repair","car repair"),("🚿 Car Wash","car wash"),("🏠 Real Estate","real estate"),("⚖️ Lawyer","lawyer"),("🧾 Accountant","accountant"),("✈️ Travel Agency","travel agency"),("📱 Electronics","electronics"),("👕 Clothing","clothing"),
("🛋️ Furniture","furniture"),("💎 Jewellery","jewellery"),("🛒 Supermarket","supermarket"),("🔨 Hardware","hardware"),("🏦 Bank","bank"),("🛡️ Insurance","insurance"),("🏛️ Architect","architect"),("🏗️ Construction","construction"),
("🖨️ Printing","printing"),("📸 Photographer","photographer"),("⛽ Fuel Station","fuel"),("🐾 Veterinary","veterinary"),("🌐 All Supported Businesses","all")]
STATUS_OPTIONS=[("📞 Called","CONTACTED"),("💬 Responded","RESPONDED"),("📅 Meeting","MEETING"),("📄 Proposal","PROPOSAL"),("🤝 Negotiation","NEGOTIATION"),("💰 Won","WON"),("❌ Lost","LOST"),("🚫 Not interested","NOT_INTERESTED")]

def authorized(update):
    admin=os.getenv("ADMIN_TELEGRAM_ID")
    return not admin or (update.effective_user and str(update.effective_user.id)==str(admin))

def b(text,data): return InlineKeyboardButton(text=text,callback_data=data)
def home_kb(): return InlineKeyboardMarkup([[b("🏢 BUSINESSES","ui:biz:0")],[b("🔎 FIND LEADS","ui:biz:0")],[b("🔥 HOT LEADS","ui:hot:0")],[b("📋 OPEN LEAD","ui:open")],[b("💰 DEAL","ui:deal")],[b("📅 TODAY","ui:today"),b("📈 STATS","ui:stats")],[b("⏰ FOLLOW-UPS","ui:follow")],[b("❓ HELP","ui:help")]])
def biz_kb(page=0):
    pages=max(1,(len(BUSINESSES)+PAGE_SIZE-1)//PAGE_SIZE); page=max(0,min(page,pages-1)); start=page*PAGE_SIZE
    rows=[[b(label,f"ui:industry:{key}")] for label,key in BUSINESSES[start:start+PAGE_SIZE]]; nav=[]
    if page: nav.append(b("⬅️ PREVIOUS",f"ui:biz:{page-1}"))
    if page<pages-1: nav.append(b("NEXT ➡️",f"ui:biz:{page+1}"))
    if nav: rows.append(nav)
    rows.append([b("🏠 MAIN MENU","ui:home")]); return InlineKeyboardMarkup(rows)
def city_kb(industry):
    return InlineKeyboardMarkup([[b("📍 JABALPUR",f"ui:search:Jabalpur:{industry}")],[b("✏️ OTHER CITY",f"ui:other:{industry}")],[b("⬅️ BUSINESSES","ui:biz:0")],[b("🏠 MAIN MENU","ui:home")]])
def lead_kb(bid):
    return InlineKeyboardMarkup([[b("📋 AUDIT",f"ui:audit:{bid}"),b("💬 MESSAGE",f"ui:message:{bid}")],[b("📞 CALL",f"ui:call:{bid}"),b("⏰ FOLLOW-UP",f"ui:followlead:{bid}")],[b("💰 DEAL",f"ui:deallead:{bid}"),b("📝 STATUS",f"ui:status:{bid}")],[b("🕘 HISTORY",f"ui:history:{bid}")],[b("🏠 MAIN MENU","ui:home")]])
def icon(score): score=int(score or 0); return "🔥" if score>=80 else "🟠" if score>=60 else "🟡" if score>=40 else "⚪"
def label(key): return next((x[0] for x in BUSINESSES if x[1]==key),key.title())
def lead_text(x):
    problems="\n".join("🔴 "+html.escape(str(p)) for p in (x.get("problems") or [])[:8]) or "✅ No stored problems yet."
    services=", ".join(x.get("recommended_services") or []) or "—"; s=int(x.get("score",0) or 0)
    return f"{icon(s)} <b>{html.escape(str(x.get('name','Unnamed Business')))}</b>\n━━━━━━━━━━━━━━━━━━━━\n📍 <b>Location:</b> {html.escape(str(x.get('city') or '—'))}\n🏢 <b>Business:</b> {html.escape(str(x.get('industry') or '—'))}\n🌐 <b>Website:</b> {html.escape(str(x.get('website') or 'Not found'))}\n📞 <b>Phone:</b> {html.escape(str(x.get('phone') or 'Not found'))}\n\n🎯 <b>Score:</b> {s}/100\n📌 <b>Priority:</b> {html.escape(str(x.get('priority') or '—'))}\n🧭 <b>Status:</b> {html.escape(str(x.get('status') or 'NEW'))}\n💼 <b>Recommended:</b> {html.escape(services)}\n\n🚨 <b>PROBLEMS / EVIDENCE</b>\n{problems}"

async def start(update,context):
    if authorized(update): await update.effective_message.reply_text("🚀 <b>LEADHUNTER</b>\n\nChoose an action below.\n<b>Everything is available by button.</b>",parse_mode="HTML",reply_markup=home_kb())
async def help_command(update,context):
    if authorized(update): await update.effective_message.reply_text("❓ <b>HELP</b>\n\n🏢 Businesses — complete business directory\n🔎 Find Leads — discover prospects\n🔥 Hot Leads — highest-priority leads\n📋 Open Lead — open a lead\n💰 Deal — sales pipeline\n📅 Today — activity\n📈 Stats — history\n⏰ Follow-ups — due follow-ups\n\n🔐 WhatsApp/email are never automatically sent or tracked.",parse_mode="HTML",reply_markup=home_kb())
async def show_biz(q,page=0):
    pages=max(1,(len(BUSINESSES)+PAGE_SIZE-1)//PAGE_SIZE); page=max(0,min(page,pages-1)); st=page*PAGE_SIZE; en=min(st+PAGE_SIZE,len(BUSINESSES))
    await q.edit_message_text(f"🏢 <b>BUSINESSES</b>\n━━━━━━━━━━━━━━━━━━━━\n\nSelect a business type.\n📚 Showing <b>{st+1}–{en}</b> of <b>{len(BUSINESSES)}</b>\n📄 Page <b>{page+1}/{pages}</b>",parse_mode="HTML",reply_markup=biz_kb(page))
async def show_lead(target,app,bid,edit=True):
    x=await app.bot_data["db"].get_lead(bid)
    if not x:
        fn=target.edit_message_text if edit else target.reply_text; await fn("❌ <b>LEAD NOT FOUND</b>",parse_mode="HTML",reply_markup=home_kb()); return
    fn=target.edit_message_text if edit else target.reply_text; await fn(lead_text(x),parse_mode="HTML",reply_markup=lead_kb(bid),disable_web_page_preview=True)
async def show_hot(q,app,page=0):
    rows=await app.bot_data["db"].list_leads("HOT",PAGE_SIZE+1,page*PAGE_SIZE); more=len(rows)>PAGE_SIZE; rows=rows[:PAGE_SIZE]
    if not rows: await q.edit_message_text("🔥 <b>HOT LEADS</b>\n\nNo hot leads yet.",parse_mode="HTML",reply_markup=home_kb()); return
    text="\n".join(f"{icon(x.get('score'))} <b>{html.escape(str(x.get('name')))}</b> — {x.get('score',0)}/100" for x in rows); kb=[[b(f"{icon(x.get('score'))} {str(x.get('name'))[:28]}",f"ui:lead:{x['id']}")] for x in rows]; nav=[]
    if page: nav.append(b("⬅️ PREVIOUS",f"ui:hot:{page-1}"))
    if more: nav.append(b("NEXT ➡️",f"ui:hot:{page+1}"))
    if nav: kb.append(nav)
    kb.append([b("🏢 BUSINESSES","ui:biz:0"),b("🏠 MENU","ui:home")]); await q.edit_message_text(f"🔥 <b>HOT LEADS · PAGE {page+1}</b>\n━━━━━━━━━━━━━━━━━━━━\n\n{text}",parse_mode="HTML",reply_markup=InlineKeyboardMarkup(kb))
async def run_find(app,city,industry,chat_id):
    db=app.bot_data["db"]; job=await db.create_job("DISCOVERY",city,industry); ok=fail=0
    try:
        candidates=await discover_businesses(city,industry,50)
        for i,c in enumerate(candidates):
            try:
                bid,_=await db.upsert_business(c)
                if bid and i<MAX_RESEARCH_PER_SEARCH:
                    r=await research_business(c); await db.save_research_and_score(bid,r,score_lead(r))
                ok+=bool(bid); fail+=not bool(bid)
            except Exception: fail+=1; log.exception("lead processing failed")
        if job: await db.finish_job(job,len(candidates),ok,fail)
        await app.bot.send_message(chat_id,f"✅ <b>SEARCH COMPLETE</b>\n\n📍 {html.escape(city)}\n🏢 {html.escape(label(industry))}\n\n📥 Found: <b>{len(candidates)}</b>\n🧪 Deep researched: <b>{min(len(candidates),MAX_RESEARCH_PER_SEARCH)}</b>\n💾 Saved: <b>{ok}</b>\n⚠️ Failed: <b>{fail}</b>",parse_mode="HTML",reply_markup=home_kb())
    except Exception as e:
        if job: await db.finish_job(job,0,0,1,str(e)[:1000])
        await app.bot.send_message(chat_id,"❌ <b>SEARCH FAILED</b>\n\n"+html.escape(str(e)[:800]),parse_mode="HTML",reply_markup=home_kb())
async def find_command(update,context):
    if not authorized(update): return
    if len(context.args)<2: await update.effective_message.reply_text("🔎 Choose a business type:",reply_markup=biz_kb()); return
    await update.effective_message.reply_text("🔎 <b>SEARCH STARTED</b>\n\n⏳ Running in background.",parse_mode="HTML",reply_markup=home_kb()); context.application.create_task(run_find(context.application,context.args[0]," ".join(context.args[1:]),update.effective_chat.id),update=update)
async def lead_command(update,context):
    if authorized(update) and context.args and context.args[0].isdigit(): await show_lead(update.effective_message,context.application,int(context.args[0]),False)
async def hot_command(update,context):
    if authorized(update):
        class Q:
            edit_message_text=update.effective_message.reply_text
        await show_hot(Q(),context.application,0)
async def today_command(update,context):
    if authorized(update):
        s=await context.application.bot_data["db"].today_stats(); body="\n".join(f"• {html.escape(str(k).replace('_',' ').title())}: <b>{v}</b>" for k,v in s.items()) or "No activity recorded yet."; await update.effective_message.reply_text("📅 <b>TODAY</b>\n\n"+body,parse_mode="HTML",reply_markup=home_kb())
async def stats_command(update,context):
    if authorized(update):
        rows=await context.application.bot_data["db"].history(14); body="\n".join(f"📅 {r['date']} · 🔎 {r.get('leads_found',0)} · 📞 {r.get('calls',0)} · 💰 {r.get('won',0)}" for r in rows) or "No history yet."; await update.effective_message.reply_text("📈 <b>14-DAY HISTORY</b>\n\n"+body,parse_mode="HTML",reply_markup=home_kb())
async def followups_command(update,context):
    if authorized(update):
        rows=await context.application.bot_data["db"].due_followups(10); body="\n".join(f"⏰ <b>{html.escape(str(r['business_name']))}</b> · {html.escape(str(r['due_at']))}" for r in rows) or "✅ Nothing is due right now."; await update.effective_message.reply_text("⏰ <b>FOLLOW-UPS</b>\n\n"+body,parse_mode="HTML",reply_markup=home_kb())
async def callbacks(update,context):
    q=update.callback_query
    if not q: return
    if not authorized(update): await q.answer("Not authorized",show_alert=True); return
    await q.answer()
    p=(q.data or "").split(":"); app=context.application
    try:
        if len(p)<2 or p[0]!="ui": return
        a=p[1]
        if a=="home": await q.edit_message_text("🚀 <b>LEADHUNTER</b>\n\nChoose an action below:",parse_mode="HTML",reply_markup=home_kb())
        elif a=="biz": await show_biz(q,int(p[2]) if len(p)>2 and p[2].isdigit() else 0)
        elif a=="industry": await q.edit_message_text(f"🏢 <b>{html.escape(label(':'.join(p[2:])) )}</b>\n━━━━━━━━━━━━━━━━━━━━\n\n📍 Choose where to search:",parse_mode="HTML",reply_markup=city_kb(':'.join(p[2:])))
        elif a=="search":
            city=p[2]; industry=':'.join(p[3:]); await q.edit_message_text("🔎 <b>SEARCH STARTED</b>\n\n⏳ Results will arrive here when complete.",parse_mode="HTML",reply_markup=home_kb()); app.create_task(run_find(app,city,industry,q.message.chat_id),update=update)
        elif a=="other": await q.edit_message_text(f"✏️ <b>OTHER CITY</b>\n\nType <code>/find CITY {html.escape(':'.join(p[2:]))}</code>",parse_mode="HTML",reply_markup=home_kb())
        elif a=="find": await show_biz(q,0)
        elif a=="hot": await show_hot(q,app,int(p[2]) if len(p)>2 and p[2].isdigit() else 0)
        elif a=="lead": await show_lead(q,app,int(p[2]))
        elif a=="open": await q.edit_message_text("📋 <b>OPEN LEAD</b>\n\nOpen a lead from Hot Leads or use <code>/lead LEAD_ID</code>.",parse_mode="HTML",reply_markup=InlineKeyboardMarkup([[b("🔥 HOT LEADS","ui:hot:0")],[b("🏠 MAIN MENU","ui:home")]]))
        elif a=="today": await today_command(update,context)
        elif a=="stats": await stats_command(update,context)
        elif a=="follow": await followups_command(update,context)
        elif a=="help": await help_command(update,context)
        else: await q.edit_message_text("🚧 This action is available from an opened lead.",reply_markup=home_kb())
    except Exception as e:
        log.exception("callback failed: %s",q.data)
        try: await q.edit_message_text("❌ <b>BUTTON ERROR</b>\n\n"+html.escape(str(e)[:700]),parse_mode="HTML",reply_markup=home_kb())
        except Exception: pass

def create_application(db:Database):
    token=os.getenv("TELEGRAM_BOT_TOKEN")
    if not token: raise RuntimeError("Missing required environment variable: TELEGRAM_BOT_TOKEN")
    app=Application.builder().token(token).build(); app.bot_data["db"]=db
    app.add_handler(CallbackQueryHandler(callbacks,block=True))
    app.add_handler(CommandHandler("start",start)); app.add_handler(CommandHandler("help",help_command)); app.add_handler(CommandHandler("find",find_command)); app.add_handler(CommandHandler("hot",hot_command)); app.add_handler(CommandHandler("lead",lead_command)); app.add_handler(CommandHandler("today",today_command)); app.add_handler(CommandHandler("stats",stats_command)); app.add_handler(CommandHandler("followups",followups_command))
    log.info("LeadHunter bot ready: CallbackQueryHandler registered")
    return app
