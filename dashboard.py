import base64
import html
import os
import secrets
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from database import Database

router = APIRouter()

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
        raise HTTPException(status_code=401, detail="Dashboard authentication required", headers={"WWW-Authenticate": "Basic"})


class StatusUpdate(BaseModel):
    status: str


def _esc(value: Any) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(authorization: str | None = Header(default=None)):
    require_dashboard(authorization)
    db = Database()
    stats = await db.today_stats()
    history = await db.history(14)

    cards = [
        ("🔎", "Leads", stats["leads_found"]), ("🎯", "Qualified", stats["qualified"]),
        ("🔥", "Hot", stats["hot_leads"]), ("📞", "Calls", stats["calls"]),
        ("💬", "Contacted", stats["contacted"]), ("↩️", "Replies", stats["replies"]),
        ("📅", "Meetings", stats["meetings"]), ("📄", "Proposals", stats["proposals"]),
        ("💰", "Won", stats["won"]), ("❌", "Lost", stats["lost"]),
    ]
    cards_html = "".join(
        f'<article class="stat"><span class="stat-icon">{icon}</span><span><small>{_esc(label)}</small><strong>{value}</strong></span></article>'
        for icon, label, value in cards
    )
    rows = "".join(
        f'<tr><td>{_esc(row.get("date", ""))}</td><td>{row.get("leads_found", 0)}</td><td>{row.get("contacted", 0)}</td><td>{row.get("replies", 0)}</td><td>{row.get("meetings", 0)}</td><td>{row.get("won", 0)}</td></tr>'
        for row in history
    ) or '<tr><td colspan="6">No history yet.</td></tr>'

    template = r'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#080d18">
<title>LeadHunter · Lead Intelligence</title>
<style>
:root{color-scheme:dark;--bg:#070b15;--panel:#0d1424;--panel2:#111b2e;--panel3:#17233a;--line:#22304a;--text:#f7f9ff;--muted:#8996b1;--accent:#8b5cf6;--cyan:#22d3ee;--green:#34d399;--orange:#fb923c;--yellow:#fbbf24;--radius:18px}
*{box-sizing:border-box}html,body{width:100%;min-width:0;overflow-x:hidden}body{margin:0;background:radial-gradient(circle at 5% -5%,rgba(139,92,246,.18),transparent 30%),radial-gradient(circle at 100% 0%,rgba(34,211,238,.10),transparent 26%),var(--bg);color:var(--text);font:14px/1.5 Inter,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}button,input{font:inherit}button{cursor:pointer}a{color:inherit;text-decoration:none}
.app{min-height:100dvh;display:grid;grid-template-columns:240px minmax(0,1fr)}.sidebar{position:sticky;top:0;height:100dvh;padding:20px 14px;border-right:1px solid var(--line);background:rgba(7,11,21,.9);backdrop-filter:blur(20px);z-index:10}.brand{display:flex;align-items:center;gap:11px;padding:5px 8px 20px}.brand-mark{width:40px;height:40px;flex:0 0 40px;display:grid;place-items:center;border-radius:13px;background:linear-gradient(135deg,var(--accent),var(--cyan));font-size:21px;box-shadow:0 10px 30px rgba(139,92,246,.28)}.brand strong{display:block;font-size:17px}.brand small{display:block;color:var(--muted)}.nav{display:grid;gap:3px}.nav-label{padding:16px 9px 7px;color:#61708c;font-size:10px;font-weight:800;letter-spacing:.14em;text-transform:uppercase}.nav button{width:100%;border:0;background:transparent;color:#aeb9cf;text-align:left;padding:10px 11px;border-radius:11px}.nav button:hover,.nav button.active{background:var(--panel2);color:#fff}
.main{min-width:0;padding:26px clamp(14px,3vw,38px) 50px}.topbar{display:flex;align-items:flex-start;justify-content:space-between;gap:18px;margin-bottom:22px}.eyebrow{color:var(--cyan);font-size:11px;font-weight:800;letter-spacing:.13em;text-transform:uppercase}h1{margin:3px 0;font-size:clamp(28px,3vw,38px);line-height:1.08;letter-spacing:-.045em}.muted{color:var(--muted)}.top-actions{display:flex;gap:8px}.btn{border:1px solid var(--line);background:var(--panel);color:var(--text);border-radius:11px;padding:9px 13px}.btn.primary{border-color:transparent;background:linear-gradient(135deg,#7c3aed,#06b6d4);font-weight:800}
.stats{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:10px;margin-bottom:22px}.stat{min-width:0;display:flex;align-items:center;gap:10px;padding:14px;background:linear-gradient(180deg,#111b2e,#0c1424);border:1px solid var(--line);border-radius:15px}.stat-icon{font-size:21px;line-height:1}.stat small{display:block;color:var(--muted);font-size:12px;white-space:nowrap}.stat strong{display:block;font-size:24px;line-height:1.05}
.workspace{display:grid;grid-template-columns:220px minmax(0,1fr);gap:13px;align-items:start}.panel{min-width:0;background:rgba(13,20,36,.92);border:1px solid var(--line);border-radius:var(--radius);box-shadow:0 20px 60px rgba(0,0,0,.2)}.categories{padding:10px;position:sticky;top:16px}.category{width:100%;display:flex;align-items:center;justify-content:space-between;gap:8px;border:0;background:transparent;color:#aeb9cf;text-align:left;padding:10px;border-radius:10px}.category:hover,.category.active{background:var(--panel3);color:#fff}.category .count{font-size:11px;color:#71809b}.content{overflow:hidden}.content-head{padding:18px 18px 13px}.content-head-row{display:flex;align-items:center;justify-content:space-between;gap:12px}.content-head h2{margin:2px 0 0;font-size:20px}.search{display:flex;gap:8px;margin-top:14px}.search input{width:100%;min-width:0;border:1px solid var(--line);background:#09111f;color:#fff;border-radius:11px;padding:11px 13px;outline:none}.locations{display:flex;gap:7px;overflow-x:auto;padding:2px 18px 13px}.tab{flex:0 0 auto;border:1px solid var(--line);background:#0a1220;color:#9da8c0;padding:8px 12px;border-radius:999px;white-space:nowrap}.tab.active{background:rgba(139,92,246,.18);border-color:rgba(139,92,246,.55);color:#fff}
.leads{padding:0 12px 14px}.lead{min-width:0;border:1px solid var(--line);background:linear-gradient(180deg,#101a2c,#0d1626);border-radius:14px;margin-top:8px;overflow:hidden}.lead.open{border-color:#5b4a87;box-shadow:0 14px 36px rgba(0,0,0,.22)}.lead-summary{min-width:0;min-height:58px;display:grid;grid-template-columns:minmax(150px,2fr) minmax(90px,1fr) 65px 65px minmax(100px,1fr) auto auto;align-items:center;gap:10px;padding:9px 11px;cursor:pointer}.lead-name,.lead-meta{min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.lead-name{font-weight:750}.lead-meta{color:#8f9ab4}.rating{color:#fcd34d;white-space:nowrap}.score{font-weight:850;white-space:nowrap}.score.hot{color:var(--orange)}.score.warm{color:var(--yellow)}.status-pill{justify-self:start;border:1px solid var(--line);padding:4px 8px;border-radius:999px;color:#c8d0df;font-size:11px;white-space:nowrap}.google{justify-self:end;border:1px solid #33405e;background:#151e33;color:#e8edff;border-radius:9px;padding:7px 9px;font-weight:700;white-space:nowrap}.chevron{color:#72809d;transition:.18s}.lead.open .chevron{transform:rotate(180deg)}
.details{display:none;border-top:1px solid var(--line);padding:14px}.lead.open .details{display:block}.detail-grid{display:grid;grid-template-columns:1.2fr 1fr;gap:12px}.section{min-width:0;background:#0b1322;border:1px solid #202c44;border-radius:12px;padding:13px}.section h3{margin:0 0 10px;font-size:11px;text-transform:uppercase;letter-spacing:.09em;color:#8490aa}.facts{display:grid;grid-template-columns:105px minmax(0,1fr);gap:7px;font-size:13px}.facts b{color:#7f8ba5}.facts span{overflow-wrap:anywhere}.links,.opps{display:flex;flex-wrap:wrap;gap:7px}.link{border:1px solid var(--line);padding:7px 9px;border-radius:9px;background:#131b2e;color:#dce3f3}.opp{padding:6px 8px;border-radius:8px;background:#172039;border:1px solid #273452;color:#cfd7e8;font-size:12px}.status-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px}.status-check{display:flex;align-items:center;gap:7px;padding:8px;border:1px solid #222d45;border-radius:9px;background:#111a2c;color:#9da8bf;cursor:pointer}.status-check.active{border-color:rgba(52,211,153,.4);background:rgba(52,211,153,.08);color:#dcfce7}.status-check input{accent-color:var(--green)}.activity{margin-top:8px;color:#8f9ab2;font-size:12px}.detail-actions{display:flex;justify-content:flex-end;gap:8px;margin-top:12px}.empty{padding:50px 20px;text-align:center;color:#7f8aa2}.empty strong{display:block;color:#dfe5f3;font-size:16px;margin-bottom:5px}.spinner{width:16px;height:16px;border:2px solid #53617b;border-top-color:#fff;border-radius:50%;animation:spin .7s linear infinite;display:inline-block;vertical-align:-3px}.toast{position:fixed;right:18px;bottom:18px;z-index:30;background:#151e33;border:1px solid #394866;color:#fff;padding:11px 14px;border-radius:11px;opacity:0;transform:translateY(10px);pointer-events:none;transition:.2s}.toast.show{opacity:1;transform:translateY(0)}.history{margin-top:20px;padding:18px;overflow:hidden}.history h2{margin:0 0 13px;font-size:18px}.table-wrap{overflow-x:auto}table{width:100%;min-width:520px;border-collapse:collapse}th,td{padding:10px 8px;text-align:left;border-bottom:1px solid var(--line);color:#b9c2d5}th{font-size:10px;text-transform:uppercase;letter-spacing:.08em;color:#727e98}@keyframes spin{to{transform:rotate(360deg)}}
@media(max-width:1100px){.stats{grid-template-columns:repeat(3,minmax(0,1fr))}.lead-summary{grid-template-columns:minmax(150px,2fr) 1fr 65px 65px auto auto}.status-pill{display:none}}
@media(max-width:820px){.app{display:block}.sidebar{position:relative;top:auto;height:auto;padding:10px 12px;border-right:0;border-bottom:1px solid var(--line)}.brand{padding:4px 4px 10px}.nav-label{display:none}.nav{display:flex;gap:4px;overflow-x:auto}.nav button{width:auto;flex:0 0 auto;white-space:nowrap}.workspace{grid-template-columns:1fr}.categories{position:relative;top:auto;display:flex;gap:5px;overflow-x:auto;padding:8px}.categories .nav-label{display:none}.category{width:auto;min-width:max-content;white-space:nowrap}.detail-grid{grid-template-columns:1fr}}
@media(max-width:620px){.main{padding:15px 10px 32px}.topbar{display:block;margin-bottom:17px}.topbar h1{font-size:30px}.top-actions{display:grid;grid-template-columns:1fr 1fr;margin-top:13px}.top-actions .btn{width:100%;padding:10px 7px}.stats{grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin-bottom:15px}.stat{padding:11px 9px;border-radius:14px}.stat-icon{font-size:19px}.stat small{font-size:10px}.stat strong{font-size:21px}.content-head{padding:14px 12px 10px}.content-head h2{font-size:18px}.search{margin-top:10px}.locations{padding-left:12px;padding-right:12px}.leads{padding:0 7px 9px}.lead-summary{grid-template-columns:minmax(0,1fr) auto auto;gap:7px;padding:10px;min-height:58px}.lead-meta,.rating,.status-pill{display:none}.lead-name{font-size:14px}.score{font-size:12px}.google{font-size:0;padding:7px 8px}.google:before{content:'🔎';font-size:14px}.details{padding:10px}.facts{grid-template-columns:80px minmax(0,1fr);font-size:12px}.status-grid{grid-template-columns:1fr}.detail-actions{justify-content:stretch}.detail-actions .btn{width:100%}.history{margin-top:14px;padding:12px}.history h2{font-size:16px}}
@media(max-width:380px){.stats{grid-template-columns:1fr}.top-actions{grid-template-columns:1fr}.main{padding-left:8px;padding-right:8px}}
@media(prefers-reduced-motion:reduce){*,*::before,*::after{animation-duration:.01ms!important;transition-duration:.01ms!important;scroll-behavior:auto!important}}
</style>
</head>
<body>
<div class="app">
<aside class="sidebar"><div class="brand"><div class="brand-mark">🚀</div><div><strong>LeadHunter</strong><small>Lead intelligence</small></div></div><nav class="nav"><div class="nav-label">Workspace</div><button class="active" type="button">🏠 Overview</button><button type="button" onclick="document.getElementById('leadWorkspace').scrollIntoView({behavior:'smooth'})">👥 Leads</button><button type="button" onclick="focusSearch()">🔎 Find / Filter</button><button type="button" onclick="document.getElementById('history').scrollIntoView({behavior:'smooth'})">📊 Analytics</button><button type="button">✉️ Outreach</button><button type="button">⚙️ Settings</button></nav></aside>
<main class="main">
<header class="topbar"><div><div class="eyebrow">Lead workspace</div><h1>Business leads</h1><div class="muted">Saved records · locations · research shortcuts</div></div><div class="top-actions"><button class="btn" type="button" onclick="loadLeads()">↻ Refresh</button><button class="btn primary" type="button" onclick="focusSearch()">＋ Search leads</button></div></header>
<section class="stats">__CARDS__</section>
<section class="workspace" id="leadWorkspace"><aside class="panel categories" id="categories"><div class="nav-label">Business types</div><div class="empty"><span class="spinner"></span></div></aside><section class="panel content"><div class="content-head"><div class="content-head-row"><div><div class="eyebrow" id="categoryEyebrow">All businesses</div><h2 id="categoryTitle">All leads</h2></div><span class="muted" id="leadCount"></span></div><div class="search"><input id="leadSearch" type="search" autocomplete="off" placeholder="Search business, city, phone or website…" oninput="render()"><button class="btn" type="button" onclick="clearSearch()">Clear</button></div></div><div class="locations" id="locations"></div><div class="leads" id="leads"><div class="empty"><span class="spinner"></span><strong>Loading saved leads…</strong></div></div></section></section>
<section class="panel history" id="history"><h2>📈 Recent activity</h2><div class="table-wrap"><table><thead><tr><th>Date</th><th>Leads</th><th>Contacted</th><th>Replies</th><th>Meetings</th><th>Won</th></tr></thead><tbody>__ROWS__</tbody></table></div></section>
</main></div><div class="toast" id="toast"></div>
<script>
const stages=__STAGES__;let leads=[];let selectedCategory='ALL';let selectedCity='ALL';let openLead=null;
const esc=s=>String(s??'').replace(/[&<>\'\"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));const norm=s=>String(s??'').trim().toLowerCase();
function toast(msg){const e=document.getElementById('toast');e.textContent=msg;e.classList.add('show');clearTimeout(window.__toast);window.__toast=setTimeout(()=>e.classList.remove('show'),2200)}
function googleUrl(l){return 'https://www.google.com/search?q='+encodeURIComponent([l.name,l.city,l.state].filter(Boolean).join(' '))}function mapsUrl(l){return 'https://www.google.com/maps/search/?api=1&query='+encodeURIComponent([l.name,l.city,l.state].filter(Boolean).join(' '))}
async function loadLeads(){document.getElementById('leads').innerHTML='<div class="empty"><span class="spinner"></span><strong>Loading saved leads…</strong></div>';try{const r=await fetch('/dashboard/api/leads?limit=500');if(!r.ok)throw Error('Failed to load leads');leads=await r.json();buildNavigation();render();toast('Lead database refreshed')}catch(e){document.getElementById('leads').innerHTML='<div class="empty"><strong>Could not load leads</strong><div>'+esc(e.message)+'</div></div>'}}
function buildNavigation(){const groups={};leads.forEach(l=>{const k=(l.industry||'Other').trim()||'Other';(groups[k]??=[]).push(l)});const cats=document.getElementById('categories');cats.innerHTML='<div class="nav-label">Business types</div>';const all=document.createElement('button');all.className='category '+(selectedCategory==='ALL'?'active':'');all.innerHTML='<span>✨ All businesses</span><span class="count">'+leads.length+'</span>';all.onclick=()=>{selectedCategory='ALL';selectedCity='ALL';buildNavigation();render()};cats.appendChild(all);Object.entries(groups).sort((a,b)=>a[0].localeCompare(b[0])).forEach(([cat,items])=>{const b=document.createElement('button');b.className='category '+(selectedCategory===cat?'active':'');b.innerHTML='<span>'+esc(cat)+'</span><span class="count">'+items.length+'</span>';b.onclick=()=>{selectedCategory=cat;selectedCity='ALL';buildNavigation();render()};cats.appendChild(b)});const locs=leads.filter(l=>selectedCategory==='ALL'||norm(l.industry)===norm(selectedCategory)).reduce((m,l)=>{const c=(l.city||'Unknown').trim()||'Unknown';m[c]=(m[c]||0)+1;return m},{});const locEl=document.getElementById('locations');locEl.innerHTML='';const at=document.createElement('button');at.className='tab '+(selectedCity==='ALL'?'active':'');at.textContent='ALL '+Object.values(locs).reduce((a,b)=>a+b,0);at.onclick=()=>{selectedCity='ALL';render()};locEl.appendChild(at);Object.entries(locs).sort((a,b)=>a[0].localeCompare(b[0])).forEach(([city,count])=>{const t=document.createElement('button');t.className='tab '+(selectedCity===city?'active':'');t.textContent=city+' '+count;t.onclick=()=>{selectedCity=city;render()};locEl.appendChild(t)})}
function filtered(){const q=norm(document.getElementById('leadSearch').value);return leads.filter(l=>(selectedCategory==='ALL'||norm(l.industry)===norm(selectedCategory))&&(selectedCity==='ALL'||norm(l.city)===norm(selectedCity))&&(!q||[l.name,l.city,l.industry,l.phone,l.website,l.email].some(v=>norm(v).includes(q))))}
function render(){const list=filtered();document.getElementById('categoryTitle').textContent=selectedCategory==='ALL'?'All leads':selectedCategory;document.getElementById('categoryEyebrow').textContent=selectedCity==='ALL'?'All locations':selectedCity;document.getElementById('leadCount').textContent=list.length+' saved lead'+(list.length===1?'':'s');const el=document.getElementById('leads');if(!list.length){el.innerHTML='<div class="empty"><strong>No leads in this view</strong><div>Run a search or choose another business type/location.</div></div>';return}el.innerHTML=list.map(leadCard).join('')}
function leadCard(l){const open=openLead===l.id?' open':'';const score=Number(l.score||0);const tone=score>=85?'hot':score>=60?'warm':'';const stage=stages.find(s=>s[0]===l.status)?.[1]||l.status||'🔎 Discovered';const services=(l.recommended_services||[]).slice(0,8).map(x=>'<span class="opp">'+esc(x)+'</span>').join('');const links=(l.website?'<a class="link" target="_blank" rel="noopener noreferrer" href="'+esc(l.website)+'">🌐 Website</a>':'')+'<a class="link" target="_blank" rel="noopener noreferrer" href="'+mapsUrl(l)+'">📍 Maps</a><a class="link" target="_blank" rel="noopener noreferrer" href="'+googleUrl(l)+'">🔎 Search</a>';const checks=stages.map(([key,label])=>'<label class="status-check '+(l.status===key?'active':'')+'"><input type="radio" name="status-'+l.id+'" '+(l.status===key?'checked':'')+' onchange="setStatus('+l.id+',\''+key+'\')">'+label+'</label>').join('');return '<article class="lead'+open+'"><div class="lead-summary" onclick="toggleLead('+l.id+')"><div class="lead-name">'+(l.industry?'🏢 ':'')+esc(l.name)+'</div><div class="lead-meta">📍 '+esc(l.city||'—')+'</div><div class="rating">⭐ '+esc(l.rating??'—')+'</div><div class="score '+tone+'">'+score+'/100</div><span class="status-pill">'+esc(stage)+'</span><button class="google" type="button" onclick="event.stopPropagation();window.open(googleUrl('+JSON.stringify(l)+'),\'_blank\',\'noopener,noreferrer\')">🔎 Google</button><span class="chevron">⌄</span></div><div class="details"><div class="detail-grid"><div class="section"><h3>Business information</h3><div class="facts"><b>Business</b><span>'+esc(l.name)+'</span><b>Category</b><span>'+esc(l.industry||'—')+'</span><b>Location</b><span>'+esc(l.city||'—')+'</span><b>Phone</b><span>'+esc(l.phone||'—')+'</span><b>Email</b><span>'+esc(l.email||'—')+'</span><b>Website</b><span>'+esc(l.website||'—')+'</span><b>Lead score</b><span><strong>'+score+'/100</strong> · '+esc(l.priority||'LOW')+'</span></div></div><div class="section"><h3>Quick research</h3><div class="links">'+links+'</div><div class="opps" style="margin-top:10px">'+(services||'<span class="muted">No recommended services yet</span>')+'</div></div><div class="section"><h3>Lead stage</h3><div class="status-grid">'+checks+'</div></div><div class="section"><h3>Notes & activity</h3><div class="muted">'+esc((l.problems||[]).slice(0,5).join(' · ')||'No problems recorded.')+'</div><div class="activity">'+esc(l.updated_at?'Last updated · '+new Date(l.updated_at).toLocaleString():'No recent update')+'</div><div class="detail-actions"><button class="btn" type="button" onclick="event.stopPropagation();window.open(googleUrl('+JSON.stringify(l)+'),\'_blank\',\'noopener,noreferrer\')">🔎 Research on Google</button></div></div></div></div></article>'}
function toggleLead(id){openLead=openLead===id?null:id;render()}
async function setStatus(id,status){try{const r=await fetch('/dashboard/api/leads/'+id+'/status',{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({status})});if(!r.ok)throw Error('Status update failed');const l=leads.find(x=>x.id===id);if(l)l.status=status;render();toast('Status updated')}catch(e){toast(e.message)}}
function focusSearch(){const i=document.getElementById('leadSearch');i.focus();i.scrollIntoView({behavior:'smooth',block:'center'})}function clearSearch(){document.getElementById('leadSearch').value='';render();focusSearch()}loadLeads();
</script>
</body></html>'''

    stage_json = "[" + ",".join("[" + repr(key) + "," + repr(label) + "]" for key, label in STAGES) + "]"
    return HTMLResponse(template.replace("__CARDS__", cards_html).replace("__ROWS__", rows).replace("__STAGES__", stage_json))


@router.get("/dashboard/api/leads")
async def dashboard_leads(authorization: str | None = Header(default=None), limit: int = Query(default=500, ge=1, le=1000)):
    require_dashboard(authorization)
    return await Database().list_leads(limit=limit)


@router.patch("/dashboard/api/leads/{business_id}/status")
async def dashboard_set_status(business_id: int, payload: StatusUpdate, authorization: str | None = Header(default=None)):
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
