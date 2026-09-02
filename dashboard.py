import base64
import html
import os
import secrets
from typing import Any
from urllib.parse import quote_plus

from fastapi import APIRouter, Header, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from database import Database

router = APIRouter()


def authorized(value: str | None) -> bool:
    user = os.getenv("DASHBOARD_USER", "")
    password = os.getenv("DASHBOARD_PASSWORD", "")
    if not user or not password or not value or not value.startswith("Basic "):
        return False
    try:
        decoded = base64.b64decode(value[6:]).decode()
        supplied_user, supplied_password = decoded.split(":", 1)
        return secrets.compare_digest(supplied_user, user) and secrets.compare_digest(supplied_password, password)
    except Exception:
        return False


def require_dashboard(authorization: str | None) -> None:
    if not authorized(authorization):
        raise HTTPException(
            status_code=401,
            detail="Dashboard authentication required",
            headers={"WWW-Authenticate": "Basic"},
        )


class StatusUpdate(BaseModel):
    status: str


STAGES = [
    ("NEW", "🔎 Discovered"),
    ("VERIFIED", "🧹 Verified"),
    ("QUALIFIED", "🎯 Qualified"),
    ("RESEARCHED", "📋 Researched"),
    ("MESSAGE_GENERATED", "✉️ Message generated"),
    ("CONTACTED", "📤 Contacted"),
    ("RESPONDED", "💬 Replied"),
    ("MEETING", "📅 Meeting"),
    ("PROPOSAL", "📄 Proposal"),
    ("WON", "💰 Won"),
    ("LOST", "❌ Lost"),
]


def _esc(value: Any) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(authorization: str | None = Header(default=None)):
    require_dashboard(authorization)
    db = Database()
    stats = await db.today_stats()
    history = await db.history(14)

    cards = [
        ("🔎", "Leads", stats["leads_found"]),
        ("🎯", "Qualified", stats["qualified"]),
        ("🔥", "Hot", stats["hot_leads"]),
        ("📞", "Calls", stats["calls"]),
        ("💬", "Contacted", stats["contacted"]),
        ("↩️", "Replies", stats["replies"]),
        ("📅", "Meetings", stats["meetings"]),
        ("📄", "Proposals", stats["proposals"]),
        ("💰", "Won", stats["won"]),
        ("❌", "Lost", stats["lost"]),
    ]
    cards_html = "".join(
        f'<div class="stat-card"><span>{icon}</span><div><small>{_esc(label)}</small><strong>{value}</strong></div></div>'
        for icon, label, value in cards
    )
    rows = "".join(
        f'<tr><td>{_esc(r.get("date", ""))}</td><td>{r.get("leads_found", 0)}</td><td>{r.get("contacted", 0)}</td><td>{r.get("replies", 0)}</td><td>{r.get("meetings", 0)}</td><td>{r.get("won", 0)}</td></tr>'
        for r in history
    )

    template = '''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="theme-color" content="#0b1020">
<title>LeadHunter · Lead Intelligence</title>
<style>
:root{color-scheme:dark;--bg:#080c18;--panel:#101729;--panel2:#151d31;--line:#26304a;--text:#f7f9ff;--muted:#8d98b2;--accent:#8b5cf6;--accent2:#22d3ee;--good:#34d399;--hot:#fb923c;--warn:#fbbf24;--bad:#fb7185;--shadow:0 20px 60px rgba(0,0,0,.28)}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:radial-gradient(circle at 10% 0%,rgba(139,92,246,.13),transparent 32%),radial-gradient(circle at 100% 10%,rgba(34,211,238,.09),transparent 28%),var(--bg);color:var(--text);font:14px/1.5 Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}button,input{font:inherit}button{cursor:pointer}a{color:inherit;text-decoration:none}
.app{display:grid;grid-template-columns:250px 1fr;min-height:100vh}.sidebar{position:sticky;top:0;height:100vh;padding:22px 16px;border-right:1px solid var(--line);background:rgba(8,12,24,.78);backdrop-filter:blur(18px)}.brand{display:flex;gap:11px;align-items:center;padding:8px 10px 22px}.brand-mark{width:38px;height:38px;border-radius:12px;display:grid;place-items:center;background:linear-gradient(135deg,var(--accent),var(--accent2));box-shadow:0 8px 30px rgba(139,92,246,.3)}.brand strong{font-size:17px}.brand small{display:block;color:var(--muted)}.nav-label{padding:18px 10px 8px;color:#64708b;font-size:11px;text-transform:uppercase;letter-spacing:.12em}.nav button{width:100%;border:0;background:transparent;color:#b7c0d5;text-align:left;padding:10px 11px;border-radius:10px;margin:2px 0;transition:.2s}.nav button:hover,.nav button.active{background:var(--panel2);color:white;transform:translateX(2px)}
.main{min-width:0;padding:24px clamp(16px,3vw,38px) 50px}.topbar{display:flex;align-items:center;justify-content:space-between;gap:16px;margin-bottom:24px}.eyebrow{color:var(--accent2);font-size:12px;font-weight:700;letter-spacing:.1em;text-transform:uppercase}h1{margin:3px 0;font-size:clamp(25px,3vw,36px);letter-spacing:-.04em}.muted{color:var(--muted)}.top-actions{display:flex;gap:8px;align-items:center}.btn{border:1px solid var(--line);background:var(--panel);color:var(--text);border-radius:11px;padding:9px 13px;transition:.2s;box-shadow:0 5px 18px rgba(0,0,0,.12)}.btn:hover{border-color:#455273;transform:translateY(-1px)}.btn.primary{border-color:transparent;background:linear-gradient(135deg,#7c3aed,#06b6d4);font-weight:700}
.stats{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:10px;margin-bottom:24px}.stat-card{background:linear-gradient(180deg,rgba(21,29,49,.92),rgba(16,23,41,.92));border:1px solid var(--line);border-radius:15px;padding:14px;display:flex;gap:10px;align-items:center;min-width:0;transition:.22s}.stat-card:hover{transform:translateY(-2px);border-color:#3b4868}.stat-card span{font-size:21px}.stat-card small{display:block;color:var(--muted);white-space:nowrap}.stat-card strong{display:block;font-size:24px;letter-spacing:-.03em}
.workspace{display:grid;grid-template-columns:220px minmax(0,1fr);gap:14px;align-items:start}.panel{background:rgba(16,23,41,.88);border:1px solid var(--line);border-radius:17px;box-shadow:var(--shadow)}.categories{padding:10px;position:sticky;top:18px}.category{width:100%;display:flex;align-items:center;justify-content:space-between;border:0;background:transparent;color:#aeb8ce;padding:10px;border-radius:10px;text-align:left;transition:.2s}.category:hover,.category.active{background:#1a2339;color:#fff}.category .count{font-size:11px;color:#6f7b96}.content{min-width:0}.content-head{padding:18px 18px 12px}.content-head-row{display:flex;align-items:center;justify-content:space-between;gap:12px}.content-head h2{margin:0;font-size:20px}.search{margin-top:14px;display:flex;gap:8px}.search input{flex:1;min-width:0;border:1px solid var(--line);background:#0c1324;color:white;border-radius:11px;padding:11px 13px;outline:none}.locations{display:flex;gap:7px;overflow:auto;padding:4px 18px 13px}.tab{border:1px solid var(--line);background:#0d1425;color:#9da8c0;padding:8px 12px;border-radius:999px;white-space:nowrap}.tab.active{background:rgba(139,92,246,.18);border-color:rgba(139,92,246,.55);color:#fff}
.leads{padding:0 12px 14px}.lead{border:1px solid var(--line);background:linear-gradient(180deg,#11192b,#0f1627);border-radius:13px;margin-top:8px;overflow:hidden;transition:.2s;animation:rise .28s ease both}.lead:hover{border-color:#394866}.lead.open{border-color:#5b4a87;box-shadow:0 12px 35px rgba(0,0,0,.2)}.lead-summary{min-height:58px;display:grid;grid-template-columns:minmax(180px,2fr) minmax(110px,1fr) 70px 70px minmax(105px,1fr) auto;align-items:center;gap:12px;padding:10px 12px;cursor:pointer}.lead-name{font-weight:750;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.lead-meta{color:#8f9ab4;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.rating{color:#fcd34d}.score{font-weight:800}.score.hot{color:var(--hot)}.score.warm{color:var(--warn)}.status-pill{justify-self:start;border:1px solid var(--line);padding:4px 8px;border-radius:999px;color:#c8d0df;font-size:11px;white-space:nowrap}.google{justify-self:end;border:1px solid #33405e;background:#151e33;color:#e8edff;border-radius:9px;padding:7px 9px;font-weight:650}.chevron{color:#72809d;transition:.2s}.lead.open .chevron{transform:rotate(180deg)}
.details{display:none;border-top:1px solid var(--line);padding:16px}.lead.open .details{display:block}.detail-grid{display:grid;grid-template-columns:1.2fr 1fr;gap:16px}.section{background:#0d1424;border:1px solid #202a42;border-radius:12px;padding:13px}.section h3{margin:0 0 10px;font-size:12px;text-transform:uppercase;letter-spacing:.08em;color:#8490aa}.facts{display:grid;grid-template-columns:110px 1fr;gap:7px;font-size:13px}.facts b{color:#7f8ba5;font-weight:600}.facts span{overflow-wrap:anywhere}.links,.opps{display:flex;flex-wrap:wrap;gap:7px}.link{border:1px solid var(--line);padding:7px 9px;border-radius:9px;background:#131b2e;color:#dce3f3}.opp{padding:6px 8px;border-radius:8px;background:#172039;border:1px solid #273452;color:#cfd7e8;font-size:12px}.status-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px}.status-check{display:flex;align-items:center;gap:8px;padding:8px;border:1px solid #222d45;border-radius:9px;background:#111a2c;color:#9da8bf;cursor:pointer}.status-check.active{border-color:rgba(52,211,153,.4);background:rgba(52,211,153,.08);color:#dcfce7}.activity{margin-top:8px;color:#8f9ab2;font-size:12px}.detail-actions{display:flex;justify-content:flex-end;gap:8px;margin-top:12px}.empty{padding:55px 20px;text-align:center;color:#7f8aa2}.empty strong{display:block;color:#dfe5f3;font-size:17px;margin-bottom:5px}.toast{position:fixed;right:20px;bottom:20px;background:#151e33;border:1px solid #394866;color:#fff;padding:11px 14px;border-radius:11px;box-shadow:var(--shadow);opacity:0;transform:translateY(10px);pointer-events:none;transition:.25s;z-index:20}.toast.show{opacity:1;transform:translateY(0)}.spinner{width:15px;height:15px;border:2px solid #64708b;border-top-color:white;border-radius:50%;animation:spin .7s linear infinite;display:inline-block;vertical-align:-3px}.history{margin-top:24px;padding:18px}.history h2{margin:0 0 13px;font-size:18px}table{width:100%;border-collapse:collapse}th,td{padding:10px 8px;text-align:left;border-bottom:1px solid var(--line);color:#b9c2d5}th{font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:#727e98}@keyframes rise{from{opacity:0;transform:translateY(5px)}to{opacity:1;transform:none}}@keyframes spin{to{transform:rotate(360deg)}}
@media (max-width:1100px){.stats{grid-template-columns:repeat(3,1fr)}.lead-summary{grid-template-columns:minmax(180px,2fr) 1fr 65px 65px auto}.status-pill{display:none}}@media (max-width:820px){.app{grid-template-columns:1fr}.sidebar{position:relative;height:auto;border-right:0;border-bottom:1px solid var(--line);padding:10px 12px}.brand{padding:5px 4px 9px}.nav-label,.nav button:nth-child(n+6){display:none}.nav{display:flex;overflow:auto;gap:4px}.nav button{width:auto;white-space:nowrap}.workspace{grid-template-columns:1fr}.categories{position:static;display:flex;overflow:auto;gap:5px}.category{min-width:max-content}.detail-grid{grid-template-columns:1fr}}@media (max-width:620px){.main{padding:16px 10px 35px}.stats{grid-template-columns:repeat(2,1fr)}.topbar{align-items:flex-start}.top-actions .btn:first-child{display:none}.lead-summary{grid-template-columns:minmax(0,1fr) auto auto;gap:7px}.lead-summary .lead-meta,.lead-summary .rating{display:none}.google{font-size:0;padding:7px}.google::before{content:"🔎";font-size:14px}.score{font-size:12px}.facts{grid-template-columns:90px 1fr}.status-grid{grid-template-columns:1fr}.history{overflow:auto}table{min-width:560px}}
@media (prefers-reduced-motion:reduce){*,*::before,*::after{animation-duration:.01ms!important;transition-duration:.01ms!important;scroll-behavior:auto!important}}
</style>
</head>
<body>
<div class="app">
<aside class="sidebar">
<div class="brand"><div class="brand-mark">🚀</div><div><strong>LeadHunter</strong><small>Lead intelligence</small></div></div>
<nav class="nav"><div class="nav-label">Workspace</div><button class="active" type="button">🏠 Overview</button><button type="button" onclick="document.getElementById('leadWorkspace').scrollIntoView({behavior:'smooth'})">👥 Leads</button><button type="button" onclick="focusSearch()">🔎 Find / Filter</button><button type="button" onclick="document.getElementById('history').scrollIntoView({behavior:'smooth'})">📊 Analytics</button><button type="button">✉️ Outreach</button><button type="button">⚙️ Settings</button></nav>
</aside>
<main class="main">
<header class="topbar"><div><div class="eyebrow">Lead workspace</div><h1>Business leads</h1><div class="muted">Persistent records · dynamic locations · manual research shortcuts</div></div><div class="top-actions"><button class="btn" onclick="loadLeads()">↻ Refresh</button><button class="btn primary" onclick="focusSearch()">＋ Search leads</button></div></header>
<section class="stats">__CARDS__</section>
<section class="workspace" id="leadWorkspace"><aside class="panel categories" id="categories"><div class="nav-label" style="padding-top:4px">Business types</div><div class="empty"><span class="spinner"></span></div></aside><section class="panel content"><div class="content-head"><div class="content-head-row"><div><div class="eyebrow" id="categoryEyebrow">All businesses</div><h2 id="categoryTitle">All leads</h2></div><span class="muted" id="leadCount"></span></div><div class="search"><input id="leadSearch" type="search" autocomplete="off" placeholder="Search business, city, phone or website…" oninput="render()"><button class="btn" onclick="clearSearch()">Clear</button></div></div><div class="locations" id="locations"></div><div class="leads" id="leads"><div class="empty"><span class="spinner"></span><strong>Loading saved leads…</strong></div></div></section></section>
<section class="panel history" id="history"><h2>📈 Recent activity</h2><table><thead><tr><th>Date</th><th>Leads</th><th>Contacted</th><th>Replies</th><th>Meetings</th><th>Won</th></tr></thead><tbody>__ROWS__</tbody></table></section>
</main></div><div class="toast" id="toast"></div>
<script>
const stages=__STAGES__;
let leads=[];let selectedCategory='ALL';let selectedCity='ALL';let openLead=null;
const esc=s=>String(s??'').replace(/[&<>\'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
const norm=s=>String(s??'').trim().toLowerCase();
function toast(msg){const el=document.getElementById('toast');el.textContent=msg;el.classList.add('show');clearTimeout(window.__toast);window.__toast=setTimeout(()=>el.classList.remove('show'),2400)}
function googleUrl(lead){const q=[lead.name,lead.city,lead.state].filter(Boolean).join(' ');return 'https://www.google.com/search?q='+encodeURIComponent(q)}
function mapsUrl(lead){const q=[lead.name,lead.city,lead.state].filter(Boolean).join(' ');return 'https://www.google.com/maps/search/?api=1&query='+encodeURIComponent(q)}
async function loadLeads(){document.getElementById('leads').innerHTML='<div class="empty"><span class="spinner"></span><strong>Loading saved leads…</strong></div>';try{const r=await fetch('/dashboard/api/leads?limit=500');if(!r.ok)throw new Error('Failed to load leads');leads=await r.json();buildNavigation();render();toast('Lead database refreshed')}catch(e){document.getElementById('leads').innerHTML='<div class="empty"><strong>Could not load leads</strong><div>'+esc(e.message)+'</div></div>'}}
function buildNavigation(){const groups={};leads.forEach(l=>{const k=(l.industry||'Other').trim()||'Other';(groups[k]??=[]).push(l)});const cats=document.getElementById('categories');cats.innerHTML='<div class="nav-label" style="padding-top:4px">Business types</div>';const allBtn=document.createElement('button');allBtn.className='category '+(selectedCategory==='ALL'?'active':'');allBtn.innerHTML='<span>✨ All businesses</span><span class="count">'+leads.length+'</span>';allBtn.onclick=()=>{selectedCategory='ALL';selectedCity='ALL';buildNavigation();render()};cats.appendChild(allBtn);Object.entries(groups).sort((a,b)=>a[0].localeCompare(b[0])).forEach(([cat,items])=>{const b=document.createElement('button');b.className='category '+(selectedCategory===cat?'active':'');b.innerHTML='<span>'+esc(cat)+'</span><span class="count">'+items.length+'</span>';b.onclick=()=>{selectedCategory=cat;selectedCity='ALL';buildNavigation();render()};cats.appendChild(b)});const locs=leads.filter(l=>selectedCategory==='ALL'||norm(l.industry)===norm(selectedCategory)).reduce((m,l)=>{const c=(l.city||'Unknown').trim()||'Unknown';m[c]=(m[c]||0)+1;return m},{});const locEl=document.getElementById('locations');locEl.innerHTML='';const all=document.createElement('button');all.className='tab '+(selectedCity==='ALL'?'active':'');all.textContent='ALL '+Object.values(locs).reduce((a,b)=>a+b,0);all.onclick=()=>{selectedCity='ALL';render()};locEl.appendChild(all);Object.entries(locs).sort((a,b)=>a[0].localeCompare(b[0])).forEach(([city,count])=>{const t=document.createElement('button');t.className='tab '+(selectedCity===city?'active':'');t.textContent=city+' '+count;t.onclick=()=>{selectedCity=city;render()};locEl.appendChild(t)})}
function filtered(){const q=norm(document.getElementById('leadSearch').value);return leads.filter(l=>(selectedCategory==='ALL'||norm(l.industry)===norm(selectedCategory))&&(selectedCity==='ALL'||norm(l.city)===norm(selectedCity))&&(!q||[l.name,l.city,l.industry,l.phone,l.website,l.email].some(v=>norm(v).includes(q))))}
function render(){const list=filtered();document.getElementById('categoryTitle').textContent=selectedCategory==='ALL'?'All leads':selectedCategory;document.getElementById('categoryEyebrow').textContent=selectedCity==='ALL'?'All locations':selectedCity;document.getElementById('leadCount').textContent=list.length+' saved lead'+(list.length===1?'':'s');const el=document.getElementById('leads');if(!list.length){el.innerHTML='<div class="empty"><strong>No leads in this view</strong><div>Run a search or choose another business type/location.</div></div>';return}el.innerHTML=list.map((l,i)=>leadCard(l,i)).join('')}
function leadCard(l,i){const open=openLead===l.id?' open':'';const score=Number(l.score||0);const tone=score>=85?'hot':score>=60?'warm':'';const status=stages.find(s=>s[0]===l.status)?.[1]||l.status||'🔎 Discovered';const services=(l.recommended_services||[]).slice(0,8).map(x=>'<span class="opp">'+esc(x)+'</span>').join('');const links=[l.website?'<a class="link" target="_blank" rel="noopener noreferrer" href="'+esc(l.website)+'">🌐 Website</a>':'','<a class="link" target="_blank" rel="noopener noreferrer" href="'+mapsUrl(l)+'">📍 Maps</a>'].filter(Boolean).join('');const checks=stages.map(([key,label])=>'<label class="status-check '+(l.status===key?'active':'')+'"><input type="radio" name="status-'+l.id+'" '+(l.status===key?'checked':'')+' onchange="setStatus('+l.id+',\''+key+'\')">'+label+'</label>').join('');const activity=l.updated_at?'Last updated · '+new Date(l.updated_at).toLocaleString():'';return '<article class="lead'+open+'" data-id="'+l.id+'"><div class="lead-summary" onclick="toggleLead('+l.id+')"><div class="lead-name">'+(l.industry?'🏢 ':'')+esc(l.name)+'</div><div class="lead-meta">📍 '+esc(l.city||'—')+'</div><div class="rating">⭐ '+esc(l.rating??'—')+'</div><div class="score '+tone+'">'+score+'/100</div><span class="status-pill">'+esc(status)+'</span><button class="google" type="button" onclick="event.stopPropagation();window.open(googleUrl('+JSON.stringify(l)+'),\'_blank\',\'noopener,noreferrer\')">🔎 Google</button><span class="chevron">⌄</span></div><div class="details"><div class="detail-grid"><div class="section"><h3>Business information</h3><div class="facts"><b>Business</b><span>'+esc(l.name)+'</span><b>Category</b><span>'+esc(l.industry||'—')+'</span><b>Location</b><span>'+esc(l.city||'—')+'</span><b>Phone</b><span>'+esc(l.phone||'—')+'</span><b>Email</b><span>'+esc(l.email||'—')+'</span><b>Website</b><span>'+esc(l.website||'—')+'</span><b>Lead score</b><span><strong>'+score+'/100</strong> · '+esc(l.priority||'LOW')+'</span></div></div><div class="section"><h3>Quick research</h3><div class="links">'+links+'<a class="link" target="_blank" rel="noopener noreferrer" href="'+googleUrl(l)+'">🔎 Search business</a></div><div class="opps" style="margin-top:10px">'+(services||'<span class="muted">No recommended services yet</span>')+'</div></div><div class="section"><h3>Lead stage</h3><div class="status-grid">'+checks+'</div></div><div class="section"><h3>Notes & activity</h3><div class="muted">'+esc((l.problems||[]).slice(0,5).join(' · ')||'No problems recorded.')+'</div><div class="activity">'+esc(activity)+'</div><div class="detail-actions"><button class="btn" onclick="event.stopPropagation();window.open(googleUrl('+JSON.stringify(l)+'),\'_blank\',\'noopener,noreferrer\')">🔎 Research on Google</button></div></div></div></div></article>'}
function toggleLead(id){openLead=openLead===id?null:id;render()}
async function setStatus(id,status){try{const r=await fetch('/dashboard/api/leads/'+id+'/status',{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({status})});if(!r.ok)throw new Error('Status update failed');const l=leads.find(x=>x.id===id);if(l)l.status=status;render();toast('Status updated')}catch(e){toast(e.message)}}
function focusSearch(){document.getElementById('leadSearch').focus();document.getElementById('leadSearch').scrollIntoView({behavior:'smooth',block:'center'})}
function clearSearch(){document.getElementById('leadSearch').value='';render();focusSearch()}
loadLeads();
</script>
</body></html>'''

    stages_json = "[" + ",".join("[" + repr(k) + "," + repr(v) + "]" for k, v in STAGES) + "]"
    page = template.replace("__CARDS__", cards_html).replace("__ROWS__", rows or '<tr><td colspan="6">No history yet.</td></tr>').replace("__STAGES__", stages_json)
    return HTMLResponse(page)


@router.get("/dashboard/api/leads")
async def dashboard_leads(
    authorization: str | None = Header(default=None),
    limit: int = Query(default=500, ge=1, le=1000),
):
    require_dashboard(authorization)
    return await Database().list_leads(limit=limit)


@router.patch("/dashboard/api/leads/{business_id}/status")
async def dashboard_set_status(
    business_id: int,
    payload: StatusUpdate,
    authorization: str | None = Header(default=None),
):
    require_dashboard(authorization)
    allowed = {key for key, _ in STAGES}
    status = payload.status.strip().upper()
    if status not in allowed:
        raise HTTPException(status_code=400, detail="Invalid lead status")
    db = Database()
    lead = await db.get_lead(business_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    old = lead.get("status") or "NEW"
    await db.set_status(business_id, status)
    if old != status:
        await db.record_activity(business_id, f"STATUS_{status}", "dashboard", f"Status changed from {old} to {status}")
    return {"ok": True, "business_id": business_id, "status": status}
