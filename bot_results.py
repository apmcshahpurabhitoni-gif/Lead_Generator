import html, logging, os
from datetime import datetime, timedelta, timezone
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CallbackQueryHandler, CommandHandler
from database import Database
from discovery import discover_businesses
from research import research_business
from scoring import score_lead
from ai import generate_whatsapp_message

log=logging.getLogger(__name__)
PAGE_SIZE=8
MAX_RESEARCH_PER_SEARCH=5
BUSINESSES=[("🦷 Dental / Dentist","dental"),("🏥 Hospital","hospital"),("🩺 Clinic","clinic"),("🍽️ Restaurant","restaurant"),("☕ Cafe","cafe"),("🥐 Bakery","bakery"),("🏨 Hotel","hotel"),("🌴 Resort","resort"),("🎓 School","school"),("🏫 College","college"),("🎓 University","university"),("💊 Pharmacy","pharmacy"),("🏋️ Gym / Fitness","gym"),("💇 Salon","salon"),("💄 Beauty","beauty"),("🚗 Car Dealer","car dealer"),("🔧 Car Repair","car repair"),("🚿 Car Wash","car wash"),("🏠 Real Estate","real estate"),("⚖️ Lawyer","lawyer"),("🧾 Accountant","accountant"),("✈️ Travel Agency","travel agency"),("📱 Electronics","electronics"),("👕 Clothing","clothing"),("🛋️ Furniture","furniture"),("💎 Jewellery","jewellery"),("🛒 Supermarket","supermarket"),("🔨 Hardware","hardware"),("🏦 Bank","bank"),("🛡️ Insurance","insurance"),("🏛️ Architect","architect"),("🏗️ Construction","construction"),("🖨️ Printing","printing"),("📸 Photographer","photographer"),("⛽ Fuel Station","fuel"),("🐾 Veterinary","veterinary"),("🌐 All Supported Businesses","all")]
STATUS_OPTIONS=[("📞 Called","CONTACTED"),("💬 Responded","RESPONDED"),("📅 Meeting","MEETING"),("📄 Proposal","PROPOSAL"),("🤝 Negotiation","NEGOTIATION"),("💰 Won","WON"),("❌ Lost","LOST"),("🚫 Not interested","NOT_INTERESTED")]

def authorized(update):
    admin=os.getenv("ADMIN_TELEGRAM_ID","").strip()
    return not admin or (update.effective_user and str(update.effective_user.id)==admin)

def B(text,data): return InlineKeyboardButton(text=text,callback_data=data)
def menu():
    return InlineKeyboardMarkup([[B("🏢 BUSINESSES","ui:biz:0"),B("📚 SAVED LEADS","ui:saved:0")],[B("🔎 FIND LEADS","ui:biz:0")],[B("🔥 HOT LEADS","ui:hot:0")],[B("📋 OPEN LEAD","ui:open")],[B("💰 DEAL PIPELINE","ui:deal")],[B("📅 TODAY","ui:today"),B("📈 STATS","ui:stats")],[B("⏰ FOLLOW-UPS","ui:follow")],[B("❓ HELP","ui:help")]])
def biz_menu(page=0):
    pages=max(1,(len(BUSINESSES)+PAGE_SIZE-1)//PAGE_SIZE); page=max(0,min(page,pages-1)); start=page*PAGE_SIZE
    rows=[[B(label,f"ui:industry:{key}")] for label,key in BUSINESSES[start:start+PAGE_SIZE]]; nav=[]
    if page: nav.append(B("⬅️ PREVIOUS",f"ui:biz:{page-1}"))
    if page<pages-1: nav.append(B("NEXT ➡️",f"ui:biz:{page+1}"))
    if nav: rows.append(nav)
    rows.append([B("🏠 MAIN MENU","ui:home")]); return InlineKeyboardMarkup(rows)
def city_menu(industry):
    return InlineKeyboardMarkup([[B("📍 JABALPUR",f"ui:search:Jabalpur:{industry}")],[B("✏️ OTHER CITY",f"ui:other:{industry}")],[B("⬅️ BUSINESSES","ui:biz:0"),B("🏠 MAIN MENU","ui:home")]])
def lead_menu(bid):
    return InlineKeyboardMarkup([[B("📋 AUDIT","ui:audit:%s"%bid),B("💬 MESSAGE","ui:message:%s"%bid)],[B("📞 CALL","ui:call:%s"%bid),B("⏰ FOLLOW-UP","ui:followlead:%s"%bid)],[B("💰 DEAL","ui:deallead:%s"%bid),B("📝 STATUS","ui:status:%s"%bid)],[B("🕘 HISTORY","ui:history:%s"%bid)],[B("🏠 MAIN MENU","ui:home")]])
def score_icon(s):
    s=int(s or 0); return "🔥" if s>=80 else "🟠" if s>=60 else "🟡" if s>=40 else "⚪"
def industry_label(key): return next((x[0] for x in BUSINESSES if x[1]==key),key.title())
def lead_text(x):
    problems="\n".join("🔴 "+html.escape(str(p)) for p in (x.get("problems") or [])[:8]) or "✅ No stored problems."
    services=", ".join(x.get("recommended_services") or []) or "—"; s=int(x.get("score",0) or 0)
    return f"{score_icon(s)} <b>{html.escape(str(x.get('name','Unnamed Business')))}</b>\n━━━━━━━━━━━━━━━━━━━━\n📍 <b>Location:</b> {html.escape(str(x.get('city') or '—'))}\n🏢 <b>Business:</b> {html.escape(str(x.get('industry') or '—'))}\n🌐 <b>Website:</b> {html.escape(str(x.get('website') or 'Not found'))}\n📞 <b>Phone:</b> {html.escape(str(x.get('phone') or 'Not found'))}\n\n🎯 <b>Score:</b> {s}/100\n📌 <b>Priority:</b> {html.escape(str(x.get('priority') or '—'))}\n🧭 <b>Status:</b> {html.escape(str(x.get('status') or 'NEW'))}\n💼 <b>Recommended:</b> {html.escape(services)}\n\n🚨 <b>PROBLEMS / EVIDENCE</b>\n{problems}"

async def start(update,context):
    if authorized(update): await update.effective_message.reply_text("🚀 <b>LEADHUNTER</b>\n━━━━━━━━━━━━━━━━━━━━\n\n👋 Welcome!\n🎯 Find businesses → research them → score opportunities → contact manually.\n\n👇 <b>Choose an action:</b>",parse_mode="HTML",reply_markup=menu())
async def help_command(update,context):
    if authorized(update): await update.effective_message.reply_text("❓ <b>LEADHUNTER HELP</b>\n━━━━━━━━━━━━━━━━━━━━\n🏢 Businesses — browse categories\n📚 Saved Leads — see every discovered lead\n🔎 Find Leads — discover and research prospects\n🔥 Hot Leads — highest-priority opportunities\n📋 Open Lead — open a saved lead by ID\n💰 Deal Pipeline — manage deals\n📅 Today / 📈 Stats — activity\n⏰ Follow-ups — due follow-ups\n\n🔐 WhatsApp and email are <b>never automatically sent or tracked</b>.",parse_mode="HTML",reply_markup=menu())
async def show_biz(q,page=0):
    pages=max(1,(len(BUSINESSES)+PAGE_SIZE-1)//PAGE_SIZE); page=max(0,min(page,pages-1)); st=page*PAGE_SIZE; en=min(st+PAGE_SIZE,len(BUSINESSES))
    await q.edit_message_text(f"🏢 <b>BUSINESSES</b>\n━━━━━━━━━━━━━━━━━━━━\n📚 Showing <b>{st+1}–{en}</b> of <b>{len(BUSINESSES)}</b>\n📄 Page <b>{page+1}/{pages}</b>\n\nSelect a business type:",parse_mode="HTML",reply_markup=biz_menu(page))
async def show_lead(target,app,bid,edit=True):
    x=await app.bot_data["db"].get_lead(bid)
    if not x:
        fn=target.edit_message_text if edit else target.reply_text; await fn("❌ <b>LEAD NOT FOUND</b>",parse_mode="HTML",reply_markup=menu()); return
    fn=target.edit_message_text if edit else target.reply_text; await fn(lead_text(x),parse_mode="HTML",reply_markup=lead_menu(bid),disable_web_page_preview=True)
async def show_results(q,app,city,industry,page=0):
    offset=page*PAGE_SIZE; rows=await app.bot_data["db"].list_search_results(city,industry,PAGE_SIZE+1,offset); more=len(rows)>PAGE_SIZE; rows=rows[:PAGE_SIZE]
    if not rows:
        await q.edit_message_text(f"📋 <b>SEARCH RESULTS</b>\n━━━━━━━━━━━━━━━━━━━━\n\nNo saved leads found for <b>{html.escape(city)}</b> · <b>{html.escape(industry_label(industry))}</b>.",parse_mode="HTML",reply_markup=menu()); return
    start=offset+1; end=offset+len(rows)
    text="\n".join(f"{score_icon(x.get('score'))} <b>{html.escape(str(x.get('name','Lead')))}</b> · {int(x.get('score',0) or 0)}/100" for x in rows)
    await q.edit_message_text(f"📋 <b>SEARCH RESULTS</b>\n━━━━━━━━━━━━━━━━━━━━\n📍 {html.escape(city)}\n🏢 {html.escape(industry_label(industry))}\n📄 Showing <b>{start}–{end}</b>\n\n{text}\n\n👇 <b>Tap a business to open the full lead.</b>",parse_mode="HTML",reply_markup=result_menu(rows,city,industry,page,more))
async def show_saved(q,app,page=0):
    offset=page*PAGE_SIZE; rows=await app.bot_data["db"].list_leads(None,PAGE_SIZE+1,offset); more=len(rows)>PAGE_SIZE; rows=rows[:PAGE_SIZE]
    if not rows:
        await q.edit_message_text("📚 <b>SAVED LEADS</b>\n━━━━━━━━━━━━━━━━━━━━\n\nNo leads saved yet.",parse_mode="HTML",reply_markup=menu()); return
    text="\n".join(f"{score_icon(x.get('score'))} <b>{html.escape(str(x.get('name','Lead')))}</b> · {int(x.get('score',0) or 0)}/100 · {html.escape(str(x.get('city') or '—'))}" for x in rows)
    kb=[[B(f"{score_icon(x.get('score'))} {str(x.get('name','Lead'))[:30]}",f"ui:lead:{x['id']}")] for x in rows]; nav=[]
    if page: nav.append(B("⬅️ PREVIOUS",f"ui:saved:{page-1}"))
    if more: nav.append(B("NEXT ➡️",f"ui:saved:{page+1}"))
    if nav: kb.append(nav)
    kb.append([B("🏠 MAIN MENU","ui:home")])
    await q.edit_message_text(f"📚 <b>SAVED LEADS · PAGE {page+1}</b>\n━━━━━━━━━━━━━━━━━━━━\n\n{text}\n\n👇 <b>Tap a business to open it.</b>",parse_mode="HTML",reply_markup=InlineKeyboardMarkup(kb))
def result_menu(rows,city,industry,page,more):
    kb=[[B(f"{score_icon(x.get('score'))} {str(x.get('name','Lead'))[:32]}",f"ui:lead:{x['id']}")] for x in rows]; nav=[]
    if page: nav.append(B("⬅️ PREVIOUS",f"ui:results:{city}:{industry}:{page-1}"))
    if more: nav.append(B("NEXT ➡️",f"ui:results:{city}:{industry}:{page+1}"))
    if nav: kb.append(nav)
    kb.append([B("📚 ALL SAVED","ui:saved:0"),B("🏠 MAIN MENU","ui:home")])
    return InlineKeyboardMarkup(kb)
async def show_hot(q,app,page=0):
    rows=await app.bot_data["db"].list_leads("HOT",PAGE_SIZE+1,page*PAGE_SIZE); more=len(rows)>PAGE_SIZE; rows=rows[:PAGE_SIZE]
    if not rows: await q.edit_message_text("🔥 <b>HOT LEADS</b>\n━━━━━━━━━━━━━━━━━━━━\n\nNo hot leads yet.",parse_mode="HTML",reply_markup=menu()); return
    text="\n".join(f"{score_icon(x.get('score'))} <b>{html.escape(str(x.get('name')))}</b> — {x.get('score',0)}/100" for x in rows)
    kb=[[B(f"{score_icon(x.get('score'))} {str(x.get('name'))[:28]}",f"ui:lead:{x['id']}")] for x in rows]; nav=[]
    if page: nav.append(B("⬅️ PREVIOUS",f"ui:hot:{page-1}"))
    if more: nav.append(B("NEXT ➡️",f"ui:hot:{page+1}"))
    if nav: kb.append(nav)
    kb.append([B("📚 SAVED LEADS","ui:saved:0"),B("🏠 MENU","ui:home")])
    await q.edit_message_text(f"🔥 <b>HOT LEADS · PAGE {page+1}</b>\n━━━━━━━━━━━━━━━━━━━━\n\n{text}",parse_mode="HTML",reply_markup=InlineKeyboardMarkup(kb))
async def run_find(app,city,industry,chat_id):
    db=app.bot_data["db"]; job=await db.create_job("DISCOVERY",city,industry); saved=failed=0
    try:
        candidates=await discover_businesses(city,industry,50)
        for i,c in enumerate(candidates):
            try:
                bid,_=await db.upsert_business(c)
                if bid and i<MAX_RESEARCH_PER_SEARCH:
                    research=await research_business(c); await db.save_research_and_score(bid,research,score_lead(research))
                saved += 1 if bid else 0; failed += 0 if bid else 1
            except Exception: failed+=1; log.exception("lead processing failed")
        if job: await db.finish_job(job,len(candidates),saved,failed)
        await app.bot.send_message(chat_id,f"✅ <b>SEARCH COMPLETE</b>\n━━━━━━━━━━━━━━━━━━━━\n📍 {html.escape(city)}\n🏢 {html.escape(industry_label(industry))}\n\n📥 Found: <b>{len(candidates)}</b>\n🧪 Researched: <b>{min(len(candidates),MAX_RESEARCH_PER_SEARCH)}</b>\n💾 Saved: <b>{saved}</b>\n⚠️ Failed: <b>{failed}</b>\n\n👇 <b>Your leads are ready.</b> Tap <b>VIEW RESULTS</b> to open them.",parse_mode="HTML",reply_markup=InlineKeyboardMarkup([[B(f"📋 VIEW {saved} RESULTS","ui:results:%s:%s:0"%(city,industry))],[B("📚 ALL SAVED LEADS","ui:saved:0"),B("🏠 MAIN MENU","ui:home")]]))
    except Exception as exc:
        if job: await db.finish_job(job,0,0,1,str(exc)[:1000])
        await app.bot.send_message(chat_id,"❌ <b>SEARCH FAILED</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"+html.escape(str(exc)[:900]),parse_mode="HTML",reply_markup=menu())
async def find_command(update,context):
    if not authorized(update): return
    if len(context.args)<2:
        await update.effective_message.reply_text("🔎 <b>FIND LEADS</b>\n\nUse the buttons below or type:\n<code>/find Jabalpur dental</code>",parse_mode="HTML",reply_markup=biz_menu()); return
    city=context.args[0]; industry=" ".join(context.args[1:]).strip()
    await update.effective_message.reply_text("🔎 <b>SEARCH STARTED</b>\n━━━━━━━━━━━━━━━━━━━━\n⏳ Research is running in the background.\n📬 Results will arrive here.",parse_mode="HTML",reply_markup=menu())
    context.application.create_task(run_find(context.application,city,industry,update.effective_chat.id),update=update)
async def lead_command(update,context):
    if authorized(update) and context.args and context.args[0].isdigit(): await show_lead(update.effective_message,context.application,int(context.args[0]),False)
async def hot_command(update,context):
    if not authorized(update): return
    rows=await context.application.bot_data["db"].list_leads("HOT",PAGE_SIZE,0)
    if not rows: await update.effective_message.reply_text("🔥 <b>HOT LEADS</b>\n\nNo hot leads yet.",parse_mode="HTML",reply_markup=menu()); return
    kb=[[B(f"{score_icon(x.get('score'))} {str(x.get('name'))[:28]}",f"ui:lead:{x['id']}")] for x in rows]; kb.append([B("🏠 MENU","ui:home")])
    await update.effective_message.reply_text("🔥 <b>HOT LEADS</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"+"\n".join(f"{score_icon(x.get('score'))} {html.escape(str(x.get('name')))} — {x.get('score',0)}/100" for x in rows),parse_mode="HTML",reply_markup=InlineKeyboardMarkup(kb))
async def today_command(update,context):
    if authorized(update):
        s=await context.application.bot_data["db"].today_stats(); body="\n".join(f"• {html.escape(k.replace('_',' ').title())}: <b>{v}</b>" for k,v in s.items()); await update.effective_message.reply_text("📅 <b>TODAY</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"+body,parse_mode="HTML",reply_markup=menu())
async def stats_command(update,context):
    if authorized(update):
        rows=await context.application.bot_data["db"].history(14); body="\n".join(f"📅 {r['date']} · 🔎 {r.get('leads_found',0)} · 📞 {r.get('calls',0)} · 💰 {r.get('won',0)}" for r in rows) or "No history yet."; await update.effective_message.reply_text("📈 <b>14-DAY HISTORY</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"+body,parse_mode="HTML",reply_markup=menu())
async def followups_command(update,context):
    if authorized(update):
        rows=await context.application.bot_data["db"].due_followups(10); body="\n".join(f"⏰ <b>{html.escape(str(r['business_name']))}</b> · {html.escape(str(r['due_at']))}" for r in rows) or "✅ Nothing is due right now."; await update.effective_message.reply_text("⏰ <b>FOLLOW-UPS</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"+body,parse_mode="HTML",reply_markup=menu())

async def callbacks(update,context):
    q=update.callback_query
    if not q: return
    if not authorized(update): await q.answer("Not authorized",show_alert=True); return
    await q.answer(); parts=(q.data or "").split(":")
    if len(parts)<2 or parts[0]!="ui": return
    action=parts[1]; app=context.application; db=app.bot_data["db"]
    try:
        if action=="home": await q.edit_message_text("🚀 <b>LEADHUNTER</b>\n━━━━━━━━━━━━━━━━━━━━\n\n👇 Choose an action:",parse_mode="HTML",reply_markup=menu())
        elif action=="biz": await show_biz(q,int(parts[2]) if len(parts)>2 and parts[2].isdigit() else 0)
        elif action=="industry":
            key=":".join(parts[2:]); await q.edit_message_text(f"🏢 <b>{html.escape(industry_label(key))}</b>\n━━━━━━━━━━━━━━━━━━━━\n\n📍 Choose where to search:",parse_mode="HTML",reply_markup=city_menu(key))
        elif action=="search":
            city=parts[2]; industry=":".join(parts[3:]); await q.edit_message_text("🔎 <b>SEARCH STARTED</b>\n━━━━━━━━━━━━━━━━━━━━\n⏳ Running in background…",parse_mode="HTML",reply_markup=menu()); app.create_task(run_find(app,city,industry,q.message.chat_id),update=update)
        elif action=="other": await q.edit_message_text(f"✏️ <b>OTHER CITY</b>\n\nType:\n<code>/find CITY {html.escape(':'.join(parts[2:]))}</code>",parse_mode="HTML",reply_markup=menu())
        elif action=="results":
            city=parts[2]; industry=parts[3]; page=int(parts[4]) if len(parts)>4 and parts[4].isdigit() else 0; await show_results(q,app,city,industry,page)
        elif action=="saved": await show_saved(q,app,int(parts[2]) if len(parts)>2 and parts[2].isdigit() else 0)
        elif action=="hot": await show_hot(q,app,int(parts[2]) if len(parts)>2 and parts[2].isdigit() else 0)
        elif action=="lead": await show_lead(q,app,int(parts[2]))
        elif action=="open": await q.edit_message_text("📋 <b>OPEN LEAD</b>\n\nUse <code>/lead LEAD_ID</code>, or choose one below.",parse_mode="HTML",reply_markup=InlineKeyboardMarkup([[B("📚 SAVED LEADS","ui:saved:0")],[B("🔥 HOT LEADS","ui:hot:0")],[B("🏠 MAIN MENU","ui:home")]]))
        elif action=="today": await today_command(update,context)
        elif action=="stats": await stats_command(update,context)
        elif action=="follow": await followups_command(update,context)
        elif action=="help": await help_command(update,context)
        elif action=="audit":
            bid=int(parts[2]); r=await db.get_research(bid); await q.edit_message_text("📋 <b>LEAD AUDIT</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"+html.escape(db.format_research(r)),parse_mode="HTML",reply_markup=lead_menu(bid))
        elif action=="message":
            bid=int(parts[2]); lead=await db.get_lead(bid); research=await db.get_research(bid)
            if not lead: await q.edit_message_text("❌ Lead not found.",reply_markup=menu()); return
            try: draft=await generate_whatsapp_message(lead,research)
            except Exception as exc: draft="Unable to generate AI draft right now. Use the audit findings to write manually."; log.warning("AI message failed: %s",exc)
            await db.record_activity(bid,"MESSAGE_DRAFTED","telegram","WhatsApp draft generated; not sent")
            await q.edit_message_text("💬 <b>WHATSAPP DRAFT</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"+html.escape(draft),parse_mode="HTML",reply_markup=lead_menu(bid))
        elif action=="call":
            bid=int(parts[2]); lead=await db.get_lead(bid); await db.record_activity(bid,"CALL_COMPLETED","telegram","Manual call action recorded"); await db.set_status(bid,"CONTACTED"); await q.edit_message_text("📞 <b>CALL RECORDED</b>\n━━━━━━━━━━━━━━━━━━━━\n\nPhone: <b>"+html.escape(str((lead or {}).get("phone") or "Not found"))+"</b>\n\n📝 Status updated to <b>CONTACTED</b>.",parse_mode="HTML",reply_markup=lead_menu(bid))
        elif action=="followlead":
            bid=int(parts[2]); due=datetime.now(timezone.utc)+timedelta(days=1); await db.create_followup(bid,due,"Default follow-up created from Telegram"); await db.record_activity(bid,"FOLLOWUP_CREATED","telegram",f"Due {due.isoformat()}"); await q.edit_message_text("⏰ <b>FOLLOW-UP CREATED</b>\n━━━━━━━━━━━━━━━━━━━━\n\n📅 Due: <b>tomorrow</b>\n🗂 Status: <b>OPEN</b>",parse_mode="HTML",reply_markup=lead_menu(bid))
        elif action=="status":
            bid=int(parts[2]); rows=[[B(label,f"ui:statusset:{bid}:{value}")] for label,value in STATUS_OPTIONS]; rows.append([B("⬅️ LEAD","ui:lead:%s"%bid),B("🏠 MENU","ui:home")]); await q.edit_message_text("📝 <b>UPDATE STATUS</b>\n\nChoose the new sales status:",parse_mode="HTML",reply_markup=InlineKeyboardMarkup(rows))
        elif action=="statusset":
            bid=int(parts[2]); status=parts[3]; await db.set_status(bid,status); await db.record_activity(bid,"STATUS_"+status,"telegram","Status updated from Telegram"); await show_lead(q,app,bid)
        elif action=="history":
            bid=int(parts[2]); rows=await db.activities(bid,30); body="\n".join(f"🕘 {html.escape(str(r.get('created_at','')))[:19]} · <b>{html.escape(str(r.get('action','')))}</b> · {html.escape(str(r.get('notes') or ''))}" for r in rows) or "No activity yet."; await q.edit_message_text("🕘 <b>LEAD HISTORY</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"+body,parse_mode="HTML",reply_markup=lead_menu(bid))
        elif action=="deallead":
            bid=int(parts[2]); await db.upsert_deal(bid,None,[],"PROPOSAL","Deal opened from Telegram"); await db.set_status(bid,"PROPOSAL"); await q.edit_message_text("💰 <b>DEAL OPENED</b>\n━━━━━━━━━━━━━━━━━━━━\n\nStage: <b>PROPOSAL</b>\nValue: <b>Not set</b>",parse_mode="HTML",reply_markup=lead_menu(bid))
        elif action=="deal":
            rows=await db.list_deals(20); text="\n".join(f"💰 <b>{html.escape(str(r['business_name']))}</b> · {r['stage']} · ₹{r.get('value') or '—'}" for r in rows) or "No deals yet."; await q.edit_message_text("💰 <b>DEAL PIPELINE</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"+text,parse_mode="HTML",reply_markup=menu())
    except Exception as exc:
        log.exception("callback failed | data=%s",q.data)
        await q.edit_message_text("❌ <b>ACTION FAILED</b>\n\n"+html.escape(str(exc)[:700]),parse_mode="HTML",reply_markup=menu())

def create_application(db: Database):
    app=Application.builder().token(os.environ["TELEGRAM_BOT_TOKEN"]).build(); app.bot_data["db"]=db
    app.add_handler(CallbackQueryHandler(callbacks))
    app.add_handler(CommandHandler("start",start)); app.add_handler(CommandHandler("help",help_command)); app.add_handler(CommandHandler("find",find_command)); app.add_handler(CommandHandler("lead",lead_command)); app.add_handler(CommandHandler("hot",hot_command)); app.add_handler(CommandHandler("today",today_command)); app.add_handler(CommandHandler("stats",stats_command)); app.add_handler(CommandHandler("followups",followups_command))
    return app
