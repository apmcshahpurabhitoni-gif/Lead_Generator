"""Telegram handoff endpoint shared by the canonical dashboard."""
import html, os
from fastapi import Header, HTTPException, Request
import dashboard_v10 as _dashboard
router=_dashboard.router

@router.post('/dashboard/api/leads/{business_id}/telegram')
async def send_lead_to_telegram(business_id:int,request:Request,authorization:str|None=Header(default=None)):
    _dashboard.auth(authorization)
    admin=os.getenv('ADMIN_TELEGRAM_ID','').strip()
    if not admin: raise HTTPException(503,'ADMIN_TELEGRAM_ID is not configured')
    db=_dashboard._base.Database(); lead=await db.get_lead(business_id)
    if not lead: raise HTTPException(404,'Lead not found')
    research=await db.get_research(business_id) or {}; g=research.get('google') or {}; loc=research.get('local') or {}
    phone=lead.get('phone') or ((loc.get('phones') or [None])[0] if isinstance(loc.get('phones'),list) else None)
    email=lead.get('email') or ((loc.get('emails') or [None])[0] if isinstance(loc.get('emails'),list) else None)
    score=int(lead.get('score',0) or 0); problems=lead.get('problems') or research.get('problems') or []; services=lead.get('recommended_services') or []; breakdown=research.get('score_breakdown') or []
    q=(research.get('search') or {}).get('query') or f"{lead.get('industry','business')} in {lead.get('city','')}"; rank=g.get('local_rank')
    lines=['📤 <b>LEAD SENT FROM DASHBOARD</b>','━━━━━━━━━━━━━━━━━━━━',f"🏢 <b>{html.escape(str(lead.get('name') or 'Unnamed Business'))}</b>",f"📍 <b>Location:</b> {html.escape(str(lead.get('city') or '—'))}",f"🏷️ <b>Business:</b> {html.escape(str(lead.get('industry') or '—'))}",'',f'🎯 <b>Opportunity:</b> {score}/100',f"🔥 <b>Priority:</b> {html.escape(str(lead.get('priority') or '—'))}",f"🧭 <b>Status:</b> {html.escape(str(lead.get('status') or 'NEW'))}",'',f"🌐 <b>Website:</b> {html.escape(str(lead.get('website') or 'Not found'))}",f"📞 <b>Phone:</b> {html.escape(str(phone or 'Not found'))}",f"✉️ <b>Email:</b> {html.escape(str(email or 'Not found'))}",f"📍 <b>Google local:</b> #{html.escape(str(rank)) if rank else 'Not measured'}",f"⭐ <b>Rating:</b> {html.escape(str(g.get('rating') or 'Not found'))} · 💬 {html.escape(str(g.get('review_count') or 'Not found'))} reviews",f"🔎 <b>Query:</b> {html.escape(str(q))}",'','⚠️ <b>PROBLEMS FOUND</b>']
    lines += [f'• {html.escape(str(x))}' for x in problems[:8]] if problems else ['• No major problem recorded.']
    lines += ['','🛠️ <b>RECOMMENDED SERVICES</b>']
    lines += [f'• {html.escape(str(x))}' for x in services[:8]] if services else ['• Audit first']
    lines += ['','💡 <b>WHY PITCH</b>']
    lines += [f'• {html.escape(str(k))}: <b>+{v}</b>' for k,v in breakdown if v] or ['• Sales opportunity identified from verified research.']
    maps=g.get('maps_url') or lead.get('google_maps_url'); website=lead.get('website')
    if maps or website:
        lines += ['','🔗 <b>USEFUL LINKS</b>']
        if maps and str(maps).startswith('http'): lines.append(f'<a href="{html.escape(str(maps),quote=True)}">📍 Google Maps</a>')
        if website and str(website).startswith('http'): lines.append(f'<a href="{html.escape(str(website),quote=True)}">🌐 Website</a>')
    bot=getattr(getattr(request.app,'state',None),'bot',None)
    if not bot or not getattr(bot,'bot',None): raise HTTPException(503,'Telegram bot is not ready')
    try: await bot.bot.send_message(chat_id=int(admin),text='\n'.join(lines),parse_mode='HTML',disable_web_page_preview=True)
    except Exception as exc: raise HTTPException(502,f'Telegram send failed: {str(exc)[:300]}')
    try: await db.record_activity(business_id,'TELEGRAM_SENT','dashboard','Lead details sent to Telegram')
    except Exception: pass
    return {'ok':True,'business_id':business_id,'sent_to':'configured Telegram admin'}
