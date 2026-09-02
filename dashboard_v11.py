"""LeadHunter V11 canonical dashboard runtime hardening.

This version deliberately does not depend on V10's browser JavaScript.  The
V10 backend/router and visual CSS are reused, but the dashboard page gets a
small independent frontend so a JavaScript parse/runtime error in an older
page cannot leave the user with only the header.
"""
import asyncio
import re
from fastapi import Header, Query
import dashboard_v10 as _base

router = _base.router


@router.get('/dashboard/api/leads_fast')
async def leads_fast(
    authorization: str | None = Header(default=None),
    limit: int = Query(100, ge=1, le=200),
):
    _base.auth(authorization)
    db = _base._base.Database()
    rows = await db.list_leads(None, limit, 0)

    async def enrich(row):
        try:
            row['research'] = await db.get_research(int(row['id'])) or {}
        except Exception:
            row['research'] = {}
        return row

    rows = await asyncio.gather(*(enrich(row) for row in rows))
    return {'ok': True, 'leads': rows, 'count': len(rows)}


# Reuse V10's carefully built responsive visual system, but replace its
# browser layer with a tiny, independently booting dashboard application.
PAGE = _base.PAGE

# Keep the existing CSS/theme/header, but make every view have a useful
# server-rendered fallback.  Regex is intentional: V10 has changed its
# section contents between revisions, so an exact empty-section replacement
# is too brittle.
main_start = PAGE.find('<main>')
main_end = PAGE.find('</main>', main_start)
if main_start >= 0 and main_end > main_start:
    views = '''<main>
<section class="view active" id="leads">
  <div class="pagehead"><div><div class="eyebrow">Lead workspace</div><h1>Your leads.</h1><div class="sub">Your saved leads, previous searches and priorities in one place.</div></div></div>
  <div class="metrics"><div class="metric"><small>Total leads</small><strong id="m-total">—</strong><span>Saved in workspace</span></div><div class="metric"><small>Hot</small><strong id="m-hot">—</strong><span>Highest priority</span></div><div class="metric"><small>Qualified</small><strong id="m-qualified">—</strong><span>Ready for outreach</span></div><div class="metric"><small>Contacted</small><strong id="m-contacted">—</strong><span>Outreach started</span></div><div class="metric"><small>Won</small><strong id="m-won">—</strong><span>Closed deals</span></div></div>
  <section class="workspace"><div class="sectionhead"><div><h2>Saved searches</h2><p>Reopen a previous city + business search without starting again.</p></div></div><div id="searches"><div class="empty">⏳ Loading saved searches…</div></div></section>
  <section class="workspace"><div class="sectionhead"><div><h2>Lead pipeline</h2><p>Tap any lead to view research, evidence, score and outreach actions.</p></div></div><div id="lead-list"><div class="empty">⏳ Loading your leads…</div></div></section>
</section>
<section class="view" id="find"><div class="pagehead"><div><div class="eyebrow">Discovery</div><h1>Find new leads.</h1><div class="sub">Choose a business type, Madhya Pradesh city and lead count.</div></div></div><section class="workspace"><div class="findgrid"><div class="field"><label>Business type</label><select id="find-type"></select></div><div class="field"><label>City</label><select id="find-city"></select></div><div class="field"><label>Lead count</label><select id="find-limit"><option>10</option><option selected>20</option><option>30</option><option>50</option></select></div></div><div class="actions" style="margin-top:10px"><button class="btn primary" id="find-btn">🔎 Find businesses</button></div><div id="find-status" style="margin-top:10px"></div></section></section>
<section class="view" id="analytics"><div class="pagehead"><div><div class="eyebrow">Sales intelligence</div><h1>Know where to focus.</h1><div class="sub">Pipeline, markets, business types and service opportunities.</div></div></div><div class="analytics"><section class="workspace"><h2>Pipeline</h2><div id="analytics-total" class="empty">⏳ Loading analytics…</div></section><section class="workspace"><h2>Best cities</h2><div id="analytics-cities" class="empty">⏳ Loading…</div></section><section class="workspace"><h2>Business types</h2><div id="analytics-industries" class="empty">⏳ Loading…</div></section><section class="workspace"><h2>Recommended services</h2><div id="analytics-services" class="empty">⏳ Loading…</div></section></div></section>
<section class="view" id="outreach"><div class="pagehead"><div><div class="eyebrow">Next action</div><h1>Who should you contact?</h1><div class="sub">Your highest-priority untouched opportunities first.</div></div></div><section class="workspace"><div id="outreach-list"><div class="empty">⏳ Loading outreach queue…</div></div></section></section>
<section class="view" id="settings"><div class="pagehead"><div><div class="eyebrow">Preferences</div><h1>Make it yours.</h1><div class="sub">Choose the dashboard appearance.</div></div></div><div class="settings"><div class="theme" data-theme="light"><b>☀️ Light Modern</b><span>Clean SaaS workspace with soft surfaces.</span></div><div class="theme" data-theme="dark"><b>🌙 Dark Modern</b><span>Graphite surfaces with subtle accents.</span></div><div class="theme" data-theme="neo"><b>✦ Light Neo</b><span>Bold borders and tactile controls.</span></div><div class="theme" data-theme="darkneo"><b>⚡ Dark Neo</b><span>High contrast and tactile styling.</span></div></div></section>
</main>'''
    PAGE = PAGE[:main_start] + views + PAGE[main_end + len('</main>'):]

# Remove the entire V10 browser script.  The replacement below is intentionally
# self-contained and uses only standard browser APIs.
PAGE = re.sub(r'<script>.*?</script>', '', PAGE, count=1, flags=re.S)

SAFE_JS = r'''<script>
(function(){
  const NAV=[['leads','📋','Leads'],['find','🔎','Find'],['analytics','📊','Analytics'],['outreach','✉️','Outreach'],['settings','⚙️','Settings']];
  const TYPES=[['🦷 Dental / Dentist','dental'],['🏥 Hospital','hospital'],['🩺 Clinic','clinic'],['🍽️ Restaurant','restaurant'],['☕ Cafe','cafe'],['🥐 Bakery','bakery'],['🏨 Hotel','hotel'],['🌴 Resort','resort'],['🎓 School','school'],['🏫 College','college'],['💊 Pharmacy','pharmacy'],['🏋️ Gym / Fitness','gym'],['💇 Salon','salon'],['💄 Beauty','beauty'],['🚗 Car Dealer','car dealer'],['🔧 Car Repair','car repair'],['🚿 Car Wash','car wash'],['🏠 Real Estate','real estate'],['⚖️ Lawyer','lawyer'],['🧾 Accountant','accountant'],['✈️ Travel Agency','travel agency'],['📱 Electronics','electronics'],['👕 Clothing','clothing'],['🛋️ Furniture','furniture'],['💎 Jewellery','jewellery'],['🛒 Supermarket','supermarket'],['🔨 Hardware','hardware'],['🏛️ Architect','architect'],['🏗️ Construction','construction'],['🖨️ Printing','printing'],['📸 Photographer','photographer'],['⛽ Fuel Station','fuel'],['🐾 Veterinary','veterinary']];
  const CITIES=['Bhopal','Indore','Jabalpur','Gwalior','Ujjain','Sagar','Rewa','Satna','Dewas','Ratlam','Burhanpur','Khandwa','Chhindwara','Vidisha','Shivpuri','Morena','Singrauli','Damoh','Mandsaur','Neemuch','Sehore','Betul','Itarsi','Narmadapuram','Khargone','Barwani','Dhar','Datia','Bhind','Balaghat','Chhatarpur','Tikamgarh','Panna','Raisen','Rajgarh','Shajapur','Agar Malwa','Alirajpur','Anuppur','Ashoknagar','Dindori','Harda','Jhabua','Katni','Mandla','Narsinghpur','Sheopur','Sidhi','Umaria'];
  const STAGES=['NEW','VERIFIED','QUALIFIED','RESEARCHED','MESSAGE_GENERATED','CONTACTED','RESPONDED','MEETING','PROPOSAL','NEGOTIATION','WON','LOST'];
  const $=s=>document.querySelector(s), esc=v=>String(v==null?'':v).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  let leads=[];
  function toast(x){let t=$('#toast');if(!t)return;t.textContent=x;t.classList.add('show');setTimeout(()=>t.classList.remove('show'),2600)}
  async function api(url,opt){const r=await fetch(url,Object.assign({credentials:'same-origin',headers:{Accept:'application/json'}},opt||{}));let j={};try{j=await r.json()}catch(e){}if(!r.ok)throw Error(j.detail||'Request failed ('+r.status+')');return j}
  function paintNav(){
    $('#nav').innerHTML=NAV.map(x=>`<button class="${location.hash.slice(1)==x[0]?'active':''}" data-page="${x[0]}">${x[1]} ${x[2]}</button>`).join('');
    $('#bottom').innerHTML=NAV.map(x=>`<button class="${location.hash.slice(1)==x[0]?'active':''}" data-page="${x[0]}"><span>${x[1]}</span>${x[2]}</button>`).join('');
    document.querySelectorAll('[data-page]').forEach(b=>b.onclick=()=>{location.hash=b.dataset.page;show(b.dataset.page)});
  }
  function show(p){p=NAV.some(x=>x[0]==p)?p:'leads';document.querySelectorAll('.view').forEach(v=>v.classList.toggle('active',v.id==p));paintNav();if(p==='analytics')loadAnalytics();if(p==='outreach')loadOutreach();}
  function leadCard(l){
    const r=l.research||{}, g=r.google||{}, w=r.website||{}, local=r.local||{};
    const score=l.score==null?'—':l.score, pr=l.priority||'NORMAL';
    const problems=(r.problems||[]).slice(0,4).map(x=>`<span class="chip">${esc(typeof x==='string'?x:x.problem||x.title||JSON.stringify(x))}</span>`).join('');
    const services=(l.recommended_services||r.recommended_services||[]).slice(0,5).map(x=>`<span class="service">${esc(x)}</span>`).join('');
    return `<article class="lead"><div class="summary" data-open="${l.id}"><div><div class="name">${esc(l.name||'Unnamed business')}</div><div class="subline">${esc(l.industry||'Business')} · ${esc(l.city||'')} ${g.local_rank?'· Google #'+esc(g.local_rank):''}</div></div><div class="score">${esc(score)}</div><span class="priority ${String(pr).toLowerCase()}">${esc(pr)}</span><span>›</span></div><div class="details" id="d-${l.id}" hidden><div class="hero"><h2>${esc(l.name||'Unnamed business')}</h2><div class="badges"><span class="badge">🎯 Score ${esc(score)}</span><span class="badge">${esc(pr)}</span><span class="badge">${esc(l.status||'NEW')}</span></div><div class="signals"><div class="signal ${g.local_rank?'good':''}"><b>Google local</b><strong>${g.local_rank?'#'+esc(g.local_rank):'Not found'}</strong></div><div class="signal ${w.exists?'good':'warn'}"><b>Website</b><strong>${w.exists?'Verified':'Missing'}</strong></div><div class="signal ${local.phone_found?'good':'warn'}"><b>Phone</b><strong>${local.phone_found?'Available':'Missing'}</strong></div><div class="signal ${local.email_found?'good':'warn'}"><b>Email</b><strong>${local.email_found?'Available':'Missing'}</strong></div></div></div><div class="detailgrid"><div class="block"><h3>Opportunity</h3><div class="evidence">${problems||'<div>No major problems recorded.</div>'}</div></div><div class="block"><h3>Recommended services</h3><div class="badges">${services||'<span class="badge">Research required</span>'}</div></div></div><div class="block"><h3>Contact</h3><div class="facts"><b>Phone</b><span>${esc(l.phone||'Not available')}</span><b>Email</b><span>${esc(l.email||'Not available')}</span><b>Rating</b><span>${g.rating?esc(g.rating)+' / 5':'Not available'} ${g.review_count?'('+esc(g.review_count)+' reviews)':''}</span><b>Website</b><span>${w.url?`<a href="${esc(w.url)}" target="_blank" rel="noopener">Open website ↗</a>`:'Not available'}</span></div></div><div class="actions" style="margin-top:9px"><button class="btn primary" data-telegram="${l.id}">📨 Send to Telegram</button><button class="btn" data-pitch="${l.id}">✍️ Generate pitch</button><select class="btn" data-status="${l.id}" style="max-width:190px">${STAGES.map(s=>`<option ${s==l.status?'selected':''}>${s}</option>`).join('')}</select></div><div class="pitch block" id="p-${l.id}" hidden><h3>Recommended pitch</h3><p></p></div></div></article>`;
  }
  async function loadLeads(){
    try{const j=await api('/dashboard/api/leads_fast?limit=100');leads=j.leads||[];$('#lead-list').innerHTML=leads.length?leads.map(leadCard).join(''):'<div class="empty">📭 No leads yet. Open Find to discover your first businesses.</div>';
      $('#m-total').textContent=leads.length;$('#m-hot').textContent=leads.filter(x=>x.priority==='HOT').length;$('#m-qualified').textContent=leads.filter(x=>['QUALIFIED','RESEARCHED','CONTACTED','RESPONDED','MEETING','PROPOSAL','NEGOTIATION','WON'].includes(x.status)).length;$('#m-contacted').textContent=leads.filter(x=>['CONTACTED','RESPONDED','MEETING','PROPOSAL','NEGOTIATION','WON'].includes(x.status)).length;$('#m-won').textContent=leads.filter(x=>x.status==='WON').length;bindLeads();
    }catch(e){$('#lead-list').innerHTML=`<div class="empty">⚠️ ${esc(e.message)}<br><small>Refresh the page after the server finishes deploying.</small></div>`}
  }
  function bindLeads(){document.querySelectorAll('[data-open]').forEach(b=>b.onclick=()=>{const d=$('#d-'+b.dataset.open);d.hidden=!d.hidden;b.parentElement.parentElement.classList.toggle('open',!d.hidden)});document.querySelectorAll('[data-telegram]').forEach(b=>b.onclick=async e=>{e.stopPropagation();try{await api('/dashboard/api/leads/'+b.dataset.telegram+'/telegram',{method:'POST'});toast('✅ Lead sent to Telegram')}catch(x){toast('⚠️ '+x.message)}});document.querySelectorAll('[data-pitch]').forEach(b=>b.onclick=async e=>{e.stopPropagation();const d=$('#p-'+b.dataset.pitch);try{const j=await api('/dashboard/api/leads/'+b.dataset.pitch+'/message',{method:'POST'});d.querySelector('p').textContent=j.message||'No message returned';d.hidden=false}catch(x){toast('⚠️ '+x.message)}});document.querySelectorAll('[data-status]').forEach(s=>s.onchange=async e=>{try{await api('/dashboard/api/leads/'+s.dataset.status+'/status',{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({status:s.value})});toast('✅ Status updated')}catch(x){toast('⚠️ '+x.message)}})}
  async function loadSearches(){try{const j=await api('/dashboard/api/searches?limit=30');const a=j.searches||[];$('#searches').innerHTML=a.length?a.map(s=>`<div class="search" data-search="${s.id}"><div><b>${esc(s.industry||'Business')} · ${esc(s.city||'')}</b><small>${esc(s.status||'')} · ${esc(s.created_at||'')}</small></div><strong>${esc(s.result_count??s.saved_count??'—')}<small>results</small></strong></div>`).join(''):'<div class="empty">🗂️ No saved searches yet. Use Find to create one.</div>';document.querySelectorAll('[data-search]').forEach(x=>x.onclick=async()=>{try{const q=await api('/dashboard/api/searches/'+x.dataset.search+'/leads?limit=100');leads=q.leads||[];$('#lead-list').innerHTML=leads.length?leads.map(leadCard).join(''):'<div class="empty">No leads in this saved search.</div>';bindLeads();show('leads')}catch(e){toast('⚠️ '+e.message)}})}catch(e){$('#searches').innerHTML=`<div class="empty">⚠️ ${esc(e.message)}</div>`}}
  function fillFind(){const t=$('#find-type'),c=$('#find-city');t.innerHTML=TYPES.map(x=>`<option value="${esc(x[1])}">${esc(x[0])}</option>`).join('');c.innerHTML=CITIES.map(x=>`<option>${esc(x)}</option>`).join('');c.value='Jabalpur'}
  async function discover(){const b=$('#find-btn'),s=$('#find-status');b.disabled=true;s.innerHTML='<div class="empty">🔄 Starting discovery…</div>';try{const j=await api('/dashboard/api/discover',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({business_type:$('#find-type').value,city:$('#find-city').value,limit:Number($('#find-limit').value)})});s.innerHTML='<div class="empty">🔎 Discovery started. Job #'+esc(j.job_id)+' is running. Your results will be saved automatically.</div>';const id=j.job_id;let n=0;const poll=async()=>{if(n++>60)return;try{const q=await api('/dashboard/api/jobs/'+id);const x=q.job||{};if(x.status==='COMPLETED'||x.status==='FAILED'){s.innerHTML='<div class="empty">'+(x.status==='COMPLETED'?'✅ Discovery complete — '+esc(x.saved_count||0)+' leads saved.':'⚠️ Discovery failed: '+esc(x.error||'Unknown error'))+'</div>';await loadLeads();await loadSearches();return}s.innerHTML='<div class="empty">🔎 Discovery running… saved '+esc(x.saved_count||0)+' so far.</div>';setTimeout(poll,1500)}catch(e){s.innerHTML='<div class="empty">⚠️ '+esc(e.message)+'</div>'}};poll()}catch(e){s.innerHTML='<div class="empty">⚠️ '+esc(e.message)+'</div>'}finally{b.disabled=false}}
  async function loadAnalytics(){try{const j=await api('/dashboard/api/analytics');$('#analytics-total').innerHTML=`<div class="rank"><b>Leads</b><strong>${esc(j.totals.leads)}</strong></div><div class="rank"><b>Qualified</b><strong>${esc(j.totals.qualified)}</strong></div><div class="rank"><b>Contacted</b><strong>${esc(j.totals.contacted)}</strong></div><div class="rank"><b>Won</b><strong>${esc(j.totals.won)}</strong></div>`;$('#analytics-cities').innerHTML=(j.cities||[]).map(x=>`<div class="rank"><span>${esc(x.name)}</span><b>${esc(x.count)}</b></div>`).join('')||'<div class="empty">No data yet.</div>';$('#analytics-industries').innerHTML=(j.industries||[]).map(x=>`<div class="rank"><span>${esc(x.name)}</span><b>${esc(x.count)}</b></div>`).join('')||'<div class="empty">No data yet.</div>';$('#analytics-services').innerHTML=(j.services||[]).map(x=>`<div class="rank"><span>${esc(x.name)}</span><b>${esc(x.count)}</b></div>`).join('')||'<div class="empty">No data yet.</div>'}catch(e){toast('⚠️ '+e.message)}}
  async function loadOutreach(){try{const j=await api('/dashboard/api/outreach?limit=30');const a=j.leads||[];$('#outreach-list').innerHTML=a.length?a.map(leadCard).join(''):'<div class="empty">🎉 No untouched qualified leads right now.</div>';bindLeads()}catch(e){$('#outreach-list').innerHTML=`<div class="empty">⚠️ ${esc(e.message)}</div>`}}
  function theme(){const x=localStorage.lh_theme||'light';document.body.classList.toggle('dark',x==='dark'||x==='darkneo');document.body.classList.toggle('neo',x==='neo'||x==='darkneo');document.querySelectorAll('.theme').forEach(t=>t.classList.toggle('active',t.dataset.theme===x));document.querySelector('meta[name=theme-color]').content=x==='dark'||x==='darkneo'?'#0c1118':'#f7f8fc'}
  function boot(){
    $('#toast')||document.body.insertAdjacentHTML('beforeend','<div class="toast" id="toast"></div>');
    if(!$('#bottom'))document.body.insertAdjacentHTML('beforeend','<nav class="bottom" id="bottom"></nav>');
    if(!$('#nav'))$('#nav');
    paintNav();fillFind();theme();
    document.querySelectorAll('.theme').forEach(t=>t.onclick=()=>{localStorage.lh_theme=t.dataset.theme;theme()});
    $('#find-btn').onclick=discover;window.addEventListener('hashchange',()=>show(location.hash.slice(1)));show(location.hash.slice(1)||'leads');
    loadLeads();loadSearches();
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot);else boot();
})();
</script>'''
PAGE = PAGE.replace('</body>', SAFE_JS + '</body>')
_base.PAGE = PAGE
