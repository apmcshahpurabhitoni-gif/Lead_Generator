import html,logging,os
from datetime import datetime,timedelta,timezone
from telegram import InlineKeyboardButton,InlineKeyboardMarkup,Update
from telegram.ext import Application,CallbackQueryHandler,CommandHandler
from database import Database
from discovery import discover_businesses
from research import research_business,google_places_enrich
from scoring import score_lead
from ai import generate_whatsapp_message
log=logging.getLogger(__name__)
PAGE_SIZE=8
MAX_RESEARCH_PER_SEARCH=10
BUSINESSES=[("🦷 Dental / Dentist","dental"),("🏥 Hospital","hospital"),("🩺 Clinic","clinic"),("🍽️ Restaurant","restaurant"),("☕ Cafe","cafe"),("🥐 Bakery","bakery"),("🏨 Hotel","hotel"),("🌴 Resort","resort"),("🎓 School","school"),("🏫 College","college"),("🎓 University","university"),("💊 Pharmacy","pharmacy"),("🏋️ Gym / Fitness","gym"),("💇 Salon","salon"),("💄 Beauty","beauty"),("🚗 Car Dealer","car dealer"),("🔧 Car Repair","car repair"),("🚿 Car Wash","car wash"),("🏠 Real Estate","real estate"),("⚖️ Lawyer","lawyer"),("🧾 Accountant","accountant"),("✈️ Travel Agency","travel agency"),("📱 Electronics","electronics"),("👕 Clothing","clothing"),("🛋️ Furniture","furniture"),("💎 Jewellery","jewellery"),("🛒 Supermarket","supermarket"),("🔨 Hardware","hardware"),("🏦 Bank","bank"),("🛡️ Insurance","insurance"),("🏛️ Architect","architect"),("🏗️ Construction","construction"),("🖨️ Printing","printing"),("📸 Photographer","photographer"),("⛽ Fuel Station","fuel"),("🐾 Veterinary","veterinary"),("🌐 All Supported Businesses","all")]
STATUS_OPTIONS=[("📞 Called","CONTACTED"),("💬 Responded","RESPONDED"),("📅 Meeting","MEETING"),("📄 Proposal","PROPOSAL"),("🤝 Negotiation","NEGOTIATION"),("💰 Won","WON"),("❌ Lost","LOST"),("🚫 Not interested","NOT_INTERESTED")]
def authorized(u):
 a=os.getenv("ADMIN_TELEGRAM_ID","").strip(); return not a or (u.effective_user and str(u.effective_user.id)==a)
def B(t,d): return InlineKeyboardButton(t,callback_data=d)
def menu(): return InlineKeyboardMarkup([[B("🏢 BUSINESSES","ui:biz:0"),B("📚 SAVED LEADS","ui:saved:0")],[B("🔎 FIND LEADS","ui:biz:0")],[B("🔥 HOT LEADS","ui:hot:0")],[B("📋 OPEN LEAD","ui:open")],[B("💰 DEAL PIPELINE","ui:deal")],[B("📅 TODAY","ui:today"),B("📈 STATS","ui:stats")],[B("⏰ FOLLOW-UPS","ui:follow")],[B("❓ HELP","ui:help")]])
def label(k): return next((x[0] for x in BUSINESSES if x[1]==k),str(k).title())
def icon(s): s=int(s or 0); return "🔥" if s>=80 else "🟠" if s>=60 else "🟡" if s>=40 else "⚪"
def short(v,n=32): s=str(v or "—"); return s if len(s)<=n else s[:n-1]+"…"
def biz_menu(page=0):
 pages=max(1,(len(BUSINESSES)+PAGE_SIZE-1)//PAGE_SIZE); page=max(0,min(page,pages-1)); st=page*PAGE_SIZE; rows=[[B(a,f"ui:industry:{b}")] for a,b in BUSINESSES[st:st+PAGE_SIZE]]; nav=[]
 if page: nav.append(B("⬅️ PREVIOUS",f"ui:biz:{page-1}"))
 if page<pages-1: nav.append(B("NEXT ➡️",f"ui:biz:{page+1}"))
 if nav: rows.append(nav)
 rows.append([B("🏠 MAIN MENU","ui:home")]); return InlineKeyboardMarkup(rows)
def city_menu(ind): return InlineKeyboardMarkup([[B("📍 JABALPUR",f"ui:search:Jabalpur:{ind}")],[B("✏️ OTHER CITY",f"ui:other:{ind}")],[B("⬅️ BUSINESSES","ui:biz:0"),B("🏠 MAIN MENU","ui:home")]])
def lead_menu(lead):
 bid=lead["id"]; rows=[]; w=str(lead.get("website") or ""); m=str(lead.get("google_maps_url") or "")
 if w.startswith(("http://","https://")): rows.append([InlineKeyboardButton("🌐 OPEN WEBSITE",url=w)])
 if m.startswith("http"): rows.append([InlineKeyboardButton("📍 OPEN GOOGLE MAPS",url=m)])
 rows += [[B("📋 FULL AUDIT",f"ui:audit:{bid}"),B("💬 MESSAGE",f"ui:message:{bid}")],[B("📞 CALL RECORDED",f"ui:call:{bid}"),B("⏰ FOLLOW-UP",f"ui:followlead:{bid}")],[B("💰 DEAL",f"ui:deallead:{bid}"),B("📝 STATUS",f"ui:status:{bid}")],[B("🕘 HISTORY",f"ui:history:{bid}")],[B("📚 SAVED LEADS","ui:saved:0"),B("🏠 MAIN MENU","ui:home")]]; return InlineKeyboardMarkup(rows)
async def edit(q,text,kb):
 try: await q.edit_message_text(text,parse_mode="HTML",reply_markup=kb,disable_web_page_preview=True)
 except Exception:
  if q.message: await q.message.reply_text(text,parse_mode="HTML",reply_markup=kb,disable_web_page_preview=True)
def lead_text(l,r):
 g=r.get("google",{}); loc=r.get("local",{}); seo=r.get("seo",{}); s=r.get("search",{}); score=int(l.get("score",0) or 0); rank=g.get("local_rank"); q=html.escape(str(s.get("query") or f"{l.get('industry')} in {l.get('city')}")); phone=l.get("phone") or (loc.get("phones") or [None])[0]; email=l.get("email") or (loc.get("emails") or [None])[0]
 gl=f"📍 <b>Google Local Position:</b> #{rank} for <i>{q}</i>" if rank else "📍 <b>Google Local Position:</b> Not measured"
 br=r.get("score_breakdown") or [("Base opportunity",30)]; why="\n".join(f"• {html.escape(str(k))}: <b>+{v}</b>" for k,v in br if v)
 probs="\n".join("🔴 "+html.escape(str(x)) for x in (l.get("problems") or [])[:8]) or "✅ No major problem recorded."
 return f"{icon(score)} <b>{html.escape(str(l.get('name','Unnamed Business')))}</b>\n━━━━━━━━━━━━━━━━━━━━\n🆔 <b>Lead #:</b> {l.get('id','—')}\n📍 <b>Location:</b> {html.escape(str(l.get('city') or '—'))}\n🏢 <b>Business:</b> {html.escape(str(l.get('industry') or '—'))}\n🌐 <b>Website:</b> {html.escape(str(l.get('website') or 'Not found'))}\n📞 <b>Phone:</b> {html.escape(str(phone or 'Not found'))}\n✉️ <b>Email:</b> {html.escape(str(email or 'Not found'))}\n\n{gl}\n🔎 <b>Google Organic Position:</b> Not measured\n⭐ <b>Google Rating:</b> {g.get('rating') or 'Not found'} · 💬 <b>Reviews:</b> {g.get('review_count') or 'Not found'}\n\n🎯 <b>OPPORTUNITY SCORE: {score}/100</b>\nℹ️ This is a <b>sales-opportunity score</b>, not a Google ranking.\n📌 <b>Priority:</b> {html.escape(str(l.get('priority') or '—'))}\n🧭 <b>Status:</b> {html.escape(str(l.get('status') or 'NEW'))}\n💼 <b>Recommended Pitch:</b> {html.escape(', '.join(l.get('recommended_services') or []) or 'Audit first')}\n\n💡 <b>WHY WE ARE PITCHING</b>\n{why}\n\n🚨 <b>VERIFIED EVIDENCE</b>\n{probs}"
async def show_lead(q,app,bid):
 db=app.bot_data["db"]; l=await db.get_lead(bid)
 if not l: await edit(q,"❌ <b>LEAD NOT FOUND</b>",menu()); return
 await edit(q,lead_text(l,await db.get_research(bid)),lead_menu(l))
def saved_kb(rows,page,more):
 kb=[]; off=page*PAGE_SIZE
 for i,x in enumerate(rows): kb.append([B(f"{off+i+1}️⃣ {short(x.get('name'),28)} · {int(x.get('score',0) or 0)}/100",f"ui:lead:{x['id']}")])
 nav=[]
 if page: nav.append(B("⬅️ PREVIOUS",f"ui:saved:{page-1}"))
 if more: nav.append(B("NEXT ➡️",f"ui:saved:{page+1}"))
 if nav: kb.append(nav)
 kb.append([B("🏠 MAIN MENU","ui:home")]); return InlineKeyboardMarkup(kb)
async def show_saved(q,app,page=0):
 rows=await app.bot_data["db"].list_leads(None,PAGE_SIZE+1,page*PAGE_SIZE); more=len(rows)>PAGE_SIZE; rows=rows[:PAGE_SIZE]
 if not rows: await edit(q,"📚 <b>SAVED LEADS</b>\n━━━━━━━━━━━━━━━━━━━━\n\nNo leads saved yet.",menu()); return
 lines=[]
 for i,x in enumerate(rows): lines.append(f"<b>{page*PAGE_SIZE+i+1}.</b> {icon(x.get('score'))} <b>{html.escape(short(x.get('name'),30))}</b> · <b>{x.get('score',0)}/100</b>\n   📞 {html.escape(short(x.get('phone'),18))} · ✉️ {html.escape(short(x.get('email'),20))}")
 await edit(q,"📚 <b>SAVED LEADS · PAGE %s</b>\n━━━━━━━━━━━━━━━━━━━━\n\n%s\n\n👇 <b>Tap a numbered button to open the full lead.</b>"%(page+1,"\n".join(lines)),saved_kb(rows,page,more))
async def show_hot(q,app,page=0):
 rows=await app.bot_data["db"].list_leads("HOT",PAGE_SIZE+1,page*PAGE_SIZE); more=len(rows)>PAGE_SIZE; rows=rows[:PAGE_SIZE]
 if not rows: await edit(q,"🔥 <b>HOT LEADS</b>\n━━━━━━━━━━━━━━━━━━━━\n\nNo hot leads yet.\n\nℹ️ Hot = Opportunity Score ≥80.",menu()); return
 await edit(q,"🔥 <b>HOT LEADS · PAGE %s</b>\n━━━━━━━━━━━━━━━━━━━━\n\n%s"%(page+1,"\n".join(f"{icon(x.get('score'))} <b>{html.escape(str(x.get('name')))}</b> · {x.get('score',0)}/100" for x in rows)),saved_kb(rows,page,more))
async def run_find(app,city,industry,chat_id):
 db=app.bot_data["db"]; job=await db.create_job("DISCOVERY",city,industry); saved=failed=0
 try:
  candidates=await discover_businesses(city,industry,50); google=await google_places_enrich(city,industry,candidates)
  for i,c in enumerate(candidates):
   try:
    if i<MAX_RESEARCH_PER_SEARCH: r=await research_business(c)
    else: r={"website":{"exists":bool(c.get('website'))},"seo":{"score":100 if c.get('website') else 0},"local":{"phone_found":bool(c.get('phone')),"email_found":bool(c.get('email'))},"google":{},"search":{},"problems":[]}
    r["search"]["query"]=google.get("query"); r["google"]={**r.get("google",{}),"local_rank":c.get("google_local_rank"),"rating":c.get("google_rating"),"review_count":c.get("google_review_count"),"maps_url":c.get("google_maps_url")}; sc=score_lead(r); r["score_breakdown"]=sc.get("breakdown",[])
    bid,_=await db.upsert_business(c)
    if bid: await db.save_research_and_score(bid,r,sc); saved+=1
    else: failed+=1
   except Exception: failed+=1; log.exception("lead processing failed")
  if job: await db.finish_job(job,len(candidates),saved,failed)
  await app.bot.send_message(chat_id,f"✅ <b>SEARCH COMPLETE</b>\n━━━━━━━━━━━━━━━━━━━━\n📍 {html.escape(city)}\n🏢 {html.escape(label(industry))}\n\n📥 Found: <b>{len(candidates)}</b>\n🔎 Google enrichment: <b>{google.get('status')}</b>\n🧪 Fully researched: <b>{min(len(candidates),MAX_RESEARCH_PER_SEARCH)}</b>\n💾 Saved: <b>{saved}</b>\n⚠️ Failed: <b>{failed}</b>\n\n👇 <b>Open 📚 SAVED LEADS and tap a numbered lead.</b>",parse_mode="HTML",reply_markup=menu())
 except Exception as e:
  if job: await db.finish_job(job,0,0,1,str(e)[:1000])
  await app.bot.send_message(chat_id,"❌ <b>SEARCH FAILED</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"+html.escape(str(e)[:900]),parse_mode="HTML",reply_markup=menu())
async def start(u,c):
 if authorized(u): await u.effective_message.reply_text("🚀 <b>LEADHUNTER</b>\n━━━━━━━━━━━━━━━━━━━━\n\n🎯 Discover → verify contacts → check Google visibility → research → score → pitch.\n\n👇 <b>Choose an action:</b>",parse_mode="HTML",reply_markup=menu())
async def help_command(u,c):
 if authorized(u): await u.effective_message.reply_text("❓ <b>HELP</b>\n━━━━━━━━━━━━━━━━━━━━\n\n📚 Saved Leads = every saved business\n🎯 Opportunity Score = sales opportunity, NOT Google rank\n📍 Google Local Position = tested Google Places position when API is connected\n🔎 Organic Google Position = not claimed without a compliant rank source\n📞 Phone + ✉️ email = shown when publicly found\n\n🔐 No automatic WhatsApp/email sending or tracking.",parse_mode="HTML",reply_markup=menu())
async def find_command(u,c):
 if not authorized(u): return
 if len(c.args)<2: await u.effective_message.reply_text("🔎 <b>FIND LEADS</b>\n\nExample: <code>/find Jabalpur dental</code>",parse_mode="HTML",reply_markup=biz_menu()); return
 city=c.args[0]; ind=" ".join(c.args[1:]); await u.effective_message.reply_text("🔎 <b>SEARCH STARTED</b>\n━━━━━━━━━━━━━━━━━━━━\n⏳ Discovering, enriching and researching…",parse_mode="HTML",reply_markup=menu()); c.application.create_task(run_find(c.application,city,ind,u.effective_chat.id),update=u)
async def lead_command(u,c):
 if authorized(u) and c.args and c.args[0].isdigit():
  db=c.application.bot_data["db"]; l=await db.get_lead(int(c.args[0]));
  if l: await u.effective_message.reply_text(lead_text(l,await db.get_research(int(c.args[0]))),parse_mode="HTML",reply_markup=lead_menu(l),disable_web_page_preview=True)
async def today_command(u,c):
 if authorized(u):
  s=await c.application.bot_data["db"].today_stats(); await u.effective_message.reply_text("📅 <b>TODAY</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"+"\n".join(f"• {k.replace('_',' ').title()}: <b>{v}</b>" for k,v in s.items()),parse_mode="HTML",reply_markup=menu())
async def stats_command(u,c):
 if authorized(u):
  rows=await c.application.bot_data["db"].history(14); await u.effective_message.reply_text("📈 <b>14-DAY HISTORY</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"+"\n".join(f"📅 {r['date']} · 🔎 {r.get('leads_found',0)} · 📞 {r.get('calls',0)} · 💰 {r.get('won',0)}" for r in rows),parse_mode="HTML",reply_markup=menu())
async def followups_command(u,c):
 if authorized(u):
  rows=await c.application.bot_data["db"].due_followups(10); await u.effective_message.reply_text("⏰ <b>FOLLOW-UPS</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"+"\n".join(f"⏰ <b>{html.escape(str(x['business_name']))}</b> · {x['due_at']}" for x in rows) or "",parse_mode="HTML",reply_markup=menu())
async def callbacks(u,c):
 q=u.callback_query
 if not q: return
 if not authorized(u): await q.answer("Not authorized",show_alert=True); return
 await q.answer(); p=(q.data or "").split(":"); a=p[1] if len(p)>1 else ""; app=c.application; db=app.bot_data["db"]
 try:
  if a=="home": await edit(q,"🚀 <b>LEADHUNTER</b>\n━━━━━━━━━━━━━━━━━━━━\n\n👇 Choose an action:",menu())
  elif a=="biz": await q.edit_message_text("🏢 <b>BUSINESSES</b>\n━━━━━━━━━━━━━━━━━━━━\n\n👇 Select a business type:",parse_mode="HTML",reply_markup=biz_menu(int(p[2]) if len(p)>2 else 0))
  elif a=="industry": k=":".join(p[2:]); await q.edit_message_text(f"🏢 <b>{html.escape(label(k))}</b>\n━━━━━━━━━━━━━━━━━━━━\n\n📍 Choose where to search:",parse_mode="HTML",reply_markup=city_menu(k))
  elif a=="search": city=p[2]; ind=":".join(p[3:]); await q.edit_message_text("🔎 <b>SEARCH STARTED</b>\n━━━━━━━━━━━━━━━━━━━━\n⏳ Working in background…",parse_mode="HTML",reply_markup=menu()); app.create_task(run_find(app,city,ind,q.message.chat_id),update=u)
  elif a=="other": await q.edit_message_text(f"✏️ Type <code>/find CITY {html.escape(':'.join(p[2:]))}</code>",parse_mode="HTML",reply_markup=menu())
  elif a=="saved": await show_saved(q,app,int(p[2]) if len(p)>2 else 0)
  elif a=="hot": await show_hot(q,app,int(p[2]) if len(p)>2 else 0)
  elif a=="lead": await show_lead(q,app,int(p[2]))
  elif a=="open": await q.edit_message_text("📋 <b>OPEN LEAD</b>\n\nUse <code>/lead LEAD_ID</code> or 📚 Saved Leads.",parse_mode="HTML",reply_markup=menu())
  elif a=="today": await today_command(u,c)
  elif a=="stats": await stats_command(u,c)
  elif a=="follow": await followups_command(u,c)
  elif a=="help": await help_command(u,c)
  elif a=="audit":
   bid=int(p[2]); r=await db.get_research(bid); body=Database.format_research(r)+"\n\nScore breakdown:\n"+"\n".join(f"• {k}: +{v}" for k,v in r.get("score_breakdown",[])); await edit(q,"📋 <b>FULL AUDIT</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"+html.escape(body),lead_menu(await db.get_lead(bid)))
  elif a=="message":
   bid=int(p[2]); l=await db.get_lead(bid); r=await db.get_research(bid); draft=await generate_whatsapp_message(l,r); await db.record_activity(bid,"MESSAGE_DRAFTED","telegram","WhatsApp draft generated; not sent"); await edit(q,"💬 <b>PERSONALIZED PITCH</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"+html.escape(draft),lead_menu(l))
  elif a=="call":
   bid=int(p[2]); l=await db.get_lead(bid); await db.record_activity(bid,"CALL_COMPLETED","telegram","Manual call action recorded"); await db.set_status(bid,"CONTACTED"); await edit(q,"📞 <b>CALL RECORDED</b>\n━━━━━━━━━━━━━━━━━━━━\n\n📞 Phone: <b>"+html.escape(str((l or {}).get('phone') or 'Not found'))+"</b>\n📝 Status: <b>CONTACTED</b>",lead_menu(l))
  elif a=="followlead":
   bid=int(p[2]); due=datetime.now(timezone.utc)+timedelta(days=1); await db.create_followup(bid,due,"Default follow-up from Telegram"); await edit(q,"⏰ <b>FOLLOW-UP CREATED</b>\n━━━━━━━━━━━━━━━━━━━━\n\n📅 Due: <b>tomorrow</b>",lead_menu(await db.get_lead(bid)))
  elif a=="status":
   bid=int(p[2]); rows=[[B(x,f"ui:statusset:{bid}:{y}")] for x,y in STATUS_OPTIONS]; rows.append([B("⬅️ LEAD",f"ui:lead:{bid}"),B("🏠 MENU","ui:home")]); await q.edit_message_text("📝 <b>UPDATE STATUS</b>\n\nChoose status:",parse_mode="HTML",reply_markup=InlineKeyboardMarkup(rows))
  elif a=="statusset":
   bid=int(p[2]); await db.set_status(bid,p[3]); await db.record_activity(bid,"STATUS_"+p[3],"telegram","Status updated"); await show_lead(q,app,bid)
  elif a=="history":
   bid=int(p[2]); rows=await db.activities(bid,30); body="\n".join(f"🕘 {str(x.get('created_at',''))[:19]} · <b>{html.escape(str(x.get('action','')))}</b> · {html.escape(str(x.get('notes') or ''))}" for x in rows) or "No activity yet."; await edit(q,"🕘 <b>LEAD HISTORY</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"+body,lead_menu(await db.get_lead(bid)))
  elif a=="deallead":
   bid=int(p[2]); await db.upsert_deal(bid,None,[],"PROPOSAL","Deal opened from Telegram"); await db.set_status(bid,"PROPOSAL"); await edit(q,"💰 <b>DEAL OPENED</b>\n━━━━━━━━━━━━━━━━━━━━\n\nStage: <b>PROPOSAL</b>",lead_menu(await db.get_lead(bid)))
  elif a=="deal":
   rows=await db.list_deals(20); await edit(q,"💰 <b>DEAL PIPELINE</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"+("\n".join(f"💰 <b>{html.escape(str(x['business_name']))}</b> · {x['stage']} · ₹{x.get('value') or '—'}" for x in rows) or "No deals yet."),menu())
 except Exception as e: log.exception("callback failed"); await edit(q,"❌ <b>ACTION FAILED</b>\n\n"+html.escape(str(e)[:700]),menu())
def create_application(db:Database):
 app=Application.builder().token(os.environ["TELEGRAM_BOT_TOKEN"]).build(); app.bot_data["db"]=db; app.add_handler(CallbackQueryHandler(callbacks)); app.add_handler(CommandHandler("start",start)); app.add_handler(CommandHandler("help",help_command)); app.add_handler(CommandHandler("find",find_command)); app.add_handler(CommandHandler("lead",lead_command)); app.add_handler(CommandHandler("today",today_command)); app.add_handler(CommandHandler("stats",stats_command)); app.add_handler(CommandHandler("followups",followups_command)); return app
