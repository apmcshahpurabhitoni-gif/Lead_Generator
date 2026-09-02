"""LeadHunter dashboard V9: Telegram handoff action over V8 UI."""
import html
import os
from fastapi import Header, HTTPException, Request
import dashboard_v8 as _base

router = _base.router

async def _telegram_details(business_id: int, request: Request, authorization: str | None):
    _base.req(authorization)
    admin = os.getenv("ADMIN_TELEGRAM_ID", "").strip()
    if not admin:
        raise HTTPException(503, "ADMIN_TELEGRAM_ID is not configured")
    db = _base.Database()
    lead = await db.get_lead(business_id)
    if not lead:
        raise HTTPException(404, "Lead not found")
    research = await db.get_research(business_id) or {}
    g = research.get("google") or {}
    local = research.get("local") or {}
    search = research.get("search") or {}
    phone = lead.get("phone") or ((local.get("phones") or [None])[0] if isinstance(local.get("phones"), list) else None)
    email = lead.get("email") or ((local.get("emails") or [None])[0] if isinstance(local.get("emails"), list) else None)
    score = int(lead.get("score", 0) or 0)
    rank = g.get("local_rank")
    problems = lead.get("problems") or research.get("problems") or []
    breakdown = research.get("score_breakdown") or []
    services = lead.get("recommended_services") or []
    q = search.get("query") or f"{lead.get('industry', 'business')} in {lead.get('city', '')}"
    lines = [
        "📤 <b>LEAD SENT FROM DASHBOARD</b>",
        "━━━━━━━━━━━━━━━━━━━━",
        f"🏢 <b>{html.escape(str(lead.get('name') or 'Unnamed Business'))}</b>",
        f"📍 <b>Location:</b> {html.escape(str(lead.get('city') or '—'))}",
        f"🏷️ <b>Business:</b> {html.escape(str(lead.get('industry') or '—'))}",
        "",
        f"🎯 <b>Opportunity:</b> {score}/100",
        f"🔥 <b>Priority:</b> {html.escape(str(lead.get('priority') or '—'))}",
        f"🧭 <b>Status:</b> {html.escape(str(lead.get('status') or 'NEW'))}",
        "",
        f"🌐 <b>Website:</b> {html.escape(str(lead.get('website') or 'Not found'))}",
        f"📞 <b>Phone:</b> {html.escape(str(phone or 'Not found'))}",
        f"✉️ <b>Email:</b> {html.escape(str(email or 'Not found'))}",
        f"📍 <b>Google local:</b> #{html.escape(str(rank)) if rank else 'Not measured'}",
        f"⭐ <b>Rating:</b> {html.escape(str(g.get('rating') or 'Not found'))} · 💬 {html.escape(str(g.get('review_count') or 'Not found'))} reviews",
        f"🔎 <b>Query:</b> {html.escape(str(q))}",
        "",
        "⚠️ <b>PROBLEMS FOUND</b>",
    ]
    if problems:
        lines.extend(f"• {html.escape(str(x))}" for x in problems[:8])
    else:
        lines.append("• No major problem recorded.")
    lines += ["", "🛠️ <b>RECOMMENDED SERVICES</b>"]
    if services:
        lines.extend(f"• {html.escape(str(x))}" for x in services[:8])
    else:
        lines.append("• Audit first")
    lines += ["", "💡 <b>WHY PITCH</b>"]
    if breakdown:
        lines.extend(f"• {html.escape(str(k))}: <b>+{v}</b>" for k, v in breakdown if v)
    else:
        lines.append("• Sales opportunity identified from the research.")
    maps_url = g.get("maps_url") or lead.get("google_maps_url")
    website = lead.get("website")
    if maps_url or website:
        lines += ["", "🔗 <b>USEFUL LINKS</b>"]
        if maps_url and str(maps_url).startswith("http"):
            lines.append(f'• <a href="{html.escape(str(maps_url), quote=True)}">Google Maps</a>')
        if website and str(website).startswith("http"):
            lines.append(f'• <a href="{html.escape(str(website), quote=True)}">Website</a>')
    text = "\n".join(lines)
    bot = getattr(getattr(request.app, "state", None), "bot", None)
    if not bot or not getattr(bot, "bot", None):
        raise HTTPException(503, "Telegram bot is not ready")
    try:
        await bot.bot.send_message(chat_id=int(admin), text=text, parse_mode="HTML", disable_web_page_preview=True)
    except Exception as exc:
        raise HTTPException(502, f"Telegram send failed: {str(exc)[:300]}")
    try:
        await db.record_activity(business_id, "TELEGRAM_SENT", "dashboard", "Lead details sent to Telegram")
    except Exception:
        pass
    return {"ok": True, "business_id": business_id, "sent_to": "configured Telegram admin"}

@router.post("/dashboard/api/leads/{business_id}/telegram")
async def send_lead_to_telegram(business_id: int, request: Request, authorization: str | None = Header(default=None)):
    return await _telegram_details(business_id, request, authorization)

PAGE = _base.PAGE
CSS = r'''
.telegram-send{margin-top:8px!important;background:var(--accent2)!important;color:#071114!important;border-color:var(--accent2)!important;font-weight:900!important}
.telegram-send:disabled{opacity:.65;cursor:wait}.telegram-send.sent{background:var(--green)!important;color:#fff!important;border-color:var(--green)!important}
@media(max-width:700px){.telegram-send{width:100%;min-height:46px!important}}
'''
JS = r'''
<script>
(function(){
  async function getLeads(){
    try{const r=await fetch('/dashboard/api/leads?limit=1000',{credentials:'same-origin'});const j=await r.json();return j.leads||[]}catch(e){return []}
  }
  function addButtons(){
    document.querySelectorAll('.lead').forEach(card=>{
      if(card.querySelector('.telegram-send'))return;
      const nameEl=card.querySelector('.name');
      const actions=card.querySelector('.actionsline');
      if(!nameEl||!actions)return;
      const name=(nameEl.textContent||'').trim();
      const b=document.createElement('button');b.type='button';b.className='btn telegram-send';b.textContent='✈️ Send to Telegram';b.dataset.leadName=name;
      b.addEventListener('click',async e=>{
        e.stopPropagation();
        if(b.disabled)return;
        b.disabled=true;b.textContent='⏳ Sending…';
        try{
          const leads=await getLeads();const found=leads.find(x=>String(x.name||'').trim()===name);
          if(!found)throw new Error('Lead could not be matched. Refresh the page and try again.');
          const r=await fetch('/dashboard/api/leads/'+encodeURIComponent(found.id)+'/telegram',{method:'POST',credentials:'same-origin',headers:{'Accept':'application/json'}});
          const j=await r.json();if(!r.ok)throw new Error(j.detail||'Telegram send failed');
          b.classList.add('sent');b.textContent='✅ Sent to Telegram';
          if(typeof window.toast==='function')window.toast('Lead details sent to Telegram');
        }catch(err){b.disabled=false;b.textContent='✈️ Send to Telegram';if(typeof window.toast==='function')window.toast('⚠️ '+err.message);else alert(err.message)}
      });
      actions.appendChild(b);
    });
  }
  document.addEventListener('DOMContentLoaded',function(){
    addButtons();
    new MutationObserver(addButtons).observe(document.body,{childList:true,subtree:true});
  });
})();
</script>
'''
PAGE = PAGE.replace('</style>', CSS + '</style>', 1)
PAGE = PAGE.replace('</body>', JS + '</body>', 1)
_base.PAGE = PAGE
