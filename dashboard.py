from __future__ import annotations

import base64
import html
import json
import os
import secrets
from urllib.parse import urlparse

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from ai import generate_whatsapp_message
from constants import BUSINESS_TYPES, CITIES, PIPELINE_STATUSES
from database import Database
from lead_workflow import run_discovery_job

router = APIRouter()
STAGES = PIPELINE_STATUSES


def auth(value: str | None) -> None:
    user = os.getenv("DASHBOARD_USER", "").strip()
    password = os.getenv("DASHBOARD_PASSWORD", "").strip()
    if not user or not password or not value or not value.startswith("Basic "):
        raise HTTPException(401, "Dashboard authentication required",
                            headers={"WWW-Authenticate": "Basic"})
    try:
        decoded = base64.b64decode(value[6:]).decode()
        supplied_user, supplied_password = decoded.split(":", 1)
    except Exception:
        raise HTTPException(401, "Invalid dashboard credentials",
                            headers={"WWW-Authenticate": "Basic"})
    if not (secrets.compare_digest(supplied_user, user) and
            secrets.compare_digest(supplied_password, password)):
        raise HTTPException(401, "Invalid dashboard credentials",
                            headers={"WWW-Authenticate": "Basic"})


class DiscoveryRequest(BaseModel):
    business_type: str
    city: str
    limit: int = 20


class StatusRequest(BaseModel):
    status: str


def mutation_guard(request: Request) -> None:
    origin = request.headers.get("origin") or request.headers.get("referer")
    if origin and urlparse(origin).netloc != request.base_url.netloc:
        raise HTTPException(403, "Cross-origin state change blocked")


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(authorization: str | None = Header(default=None)):
    auth(authorization)
    return HTMLResponse(PAGE)


@router.get("/dashboard/api/leads")
async def leads(authorization: str | None = Header(default=None),
                priority: str | None = None,
                limit: int = Query(100, ge=1, le=300),
                offset: int = Query(0, ge=0)):
    auth(authorization)
    rows = await Database().list_leads_with_research(priority, limit, offset)
    return {"ok": True, "leads": rows, "count": len(rows)}


@router.get("/dashboard/api/leads/{business_id}")
async def lead_detail(business_id: int,
                      authorization: str | None = Header(default=None)):
    auth(authorization)
    db = Database()
    lead = await db.get_lead(business_id)
    if not lead:
        raise HTTPException(404, "Lead not found")
    return {"ok": True, "lead": lead,
            "research": await db.get_research(business_id),
            "activities": await db.activities(business_id, 30)}


@router.get("/dashboard/api/searches")
async def searches(authorization: str | None = Header(default=None),
                   limit: int = Query(30, ge=1, le=100)):
    auth(authorization)
    return {"ok": True, "searches": await Database().list_searches(limit)}


@router.get("/dashboard/api/searches/{search_id}/leads")
async def search_leads(search_id: int,
                       authorization: str | None = Header(default=None),
                       limit: int = Query(100, ge=1, le=300)):
    auth(authorization)
    db = Database()
    search = await db.get_search(search_id)
    if not search:
        raise HTTPException(404, "Search not found")
    rows = await db.list_search_results(search_id, limit)
    return {"ok": True, "search": search, "leads": rows, "count": len(rows)}


@router.post("/dashboard/api/discover")
async def discover(payload: DiscoveryRequest, background_tasks: BackgroundTasks,
                   request: Request,
                   authorization: str | None = Header(default=None)):
    auth(authorization)
    mutation_guard(request)
    allowed = {value for _, value in BUSINESS_TYPES}
    if payload.business_type not in allowed:
        raise HTTPException(400, "Unsupported business type")
    if payload.city not in CITIES:
        raise HTTPException(400, "Unsupported Madhya Pradesh city")
    limit = max(1, min(int(payload.limit), 50))
    db = Database()
    job_id = await db.create_job("DISCOVERY", payload.city, payload.business_type)
    if not job_id:
        raise HTTPException(503, "Could not create discovery job")
    background_tasks.add_task(run_discovery_job, job_id, payload.city,
                              payload.business_type, limit)
    return {"ok": True, "job_id": job_id, "status": "RUNNING",
            "city": payload.city, "business_type": payload.business_type,
            "limit": limit}


@router.get("/dashboard/api/jobs/{job_id}")
async def job_status(job_id: int,
                     authorization: str | None = Header(default=None)):
    auth(authorization)
    job = await Database().get_job(job_id)
    if not job:
        raise HTTPException(404, "Discovery job not found")
    return {"ok": True, "job": job}


@router.get("/dashboard/api/analytics")
async def analytics(authorization: str | None = Header(default=None)):
    auth(authorization)
    return {"ok": True, **await Database().analytics()}


@router.get("/dashboard/api/outreach")
async def outreach(authorization: str | None = Header(default=None),
                   limit: int = Query(30, ge=1, le=100)):
    auth(authorization)
    rows = [x for x in await Database().list_leads(None, 1000, 0)
            if x.get("status") in {"NEW", "RESEARCHED", "QUALIFIED"}]
    rows.sort(key=lambda x: (
        0 if x.get("priority") == "HOT" else
        1 if x.get("priority") == "HIGH" else 2,
        -int(x.get("score") or 0)))
    return {"ok": True, "leads": rows[:limit]}


@router.post("/dashboard/api/leads/{business_id}/message")
async def pitch_message(business_id: int, request: Request,
                        authorization: str | None = Header(default=None)):
    auth(authorization)
    mutation_guard(request)
    db = Database()
    lead = await db.get_lead(business_id)
    if not lead:
        raise HTTPException(404, "Lead not found")
    message = await generate_whatsapp_message(
        lead, await db.get_research(business_id))
    await db.record_activity(business_id, "MESSAGE_GENERATED", "dashboard",
                             "Pitch message generated")
    return {"ok": True, "message": message}


@router.patch("/dashboard/api/leads/{business_id}/status")
async def set_lead_status(business_id: int, payload: StatusRequest,
                          request: Request,
                          authorization: str | None = Header(default=None)):
    auth(authorization)
    mutation_guard(request)
    if payload.status not in STAGES:
        raise HTTPException(400, "Invalid status")
    db = Database()
    if not await db.get_lead(business_id):
        raise HTTPException(404, "Lead not found")
    try:
        await db.set_status(business_id, payload.status)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    await db.record_activity(business_id, "STATUS_" + payload.status,
                             "dashboard", "Status changed from dashboard")
    return {"ok": True, "status": payload.status}


@router.post("/dashboard/api/leads/{business_id}/telegram")
async def send_lead_to_telegram(
    business_id: int, request: Request,
    authorization: str | None = Header(default=None)):
    auth(authorization)
    mutation_guard(request)
    admin = os.getenv("ADMIN_TELEGRAM_ID", "").strip()
    if not admin:
        raise HTTPException(503, "ADMIN_TELEGRAM_ID is not configured")
    bot_app = getattr(getattr(request.app, "state", None), "bot", None)
    if not bot_app or not getattr(bot_app, "bot", None):
        raise HTTPException(503, "Telegram bot is not ready")

    db = Database()
    lead = await db.get_lead(business_id)
    if not lead:
        raise HTTPException(404, "Lead not found")
    research = await db.get_research(business_id)
    google = research.get("google") or {}
    problems = lead.get("problems") or research.get("problems") or []
    services = lead.get("recommended_services") or []
    rank = google.get("local_rank") or google.get("provider_rank")
    lines = [
        "📤 <b>LEADHUNTER · LEAD HANDOFF</b>",
        "━━━━━━━━━━━━━━━━━━━━",
        f"🏢 <b>{html.escape(str(lead.get('name') or 'Unnamed Business'))}</b>",
        f"📍 {html.escape(str(lead.get('city') or '—'))} · {html.escape(str(lead.get('industry') or '—'))}",
        "",
        f"🎯 <b>Opportunity:</b> {int(lead.get('score') or 0)}/100",
        f"🔥 <b>Priority:</b> {html.escape(str(lead.get('priority') or '—'))}",
        f"🧭 <b>Status:</b> {html.escape(str(lead.get('status') or 'NEW'))}",
        f"🌐 <b>Website:</b> {html.escape(str(lead.get('website') or 'Not found'))}",
        f"📞 <b>Phone:</b> {html.escape(str(lead.get('phone') or 'Not found'))}",
        f"✉️ <b>Email:</b> {html.escape(str(lead.get('email') or 'Not found'))}",
        f"🔎 <b>Search position:</b> #{html.escape(str(rank)) if rank else 'Not measured'}",
        "",
        "⚠️ <b>OPPORTUNITY SIGNALS</b>",
    ]
    lines += [f"• {html.escape(str(x))}" for x in problems[:8]] or [
        "• No major problem recorded."]
    lines += ["", "🛠️ <b>RECOMMENDED SERVICES</b>"]
    lines += [f"• {html.escape(str(x))}" for x in services[:8]] or ["• Audit first"]
    try:
        sent = await bot_app.bot.send_message(
            chat_id=int(admin), text="\n".join(lines),
            parse_mode="HTML", disable_web_page_preview=True)
    except Exception as exc:
        raise HTTPException(502, f"Telegram send failed: {str(exc)[:300]}") from exc
    await db.record_activity(business_id, "TELEGRAM_SENT", "dashboard",
                             "Lead details sent to Telegram")
    await db.record_telegram_event(
        business_id, "LEAD_HANDOFF", getattr(sent, "message_id", None))
    return {"ok": True, "business_id": business_id,
            "telegram_message_id": getattr(sent, "message_id", None)}


PAGE = r'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#f7f7fb">
<title>LeadHunter · Lead Intelligence</title>
<style>
:root{--bg:#f7f7fb;--s:#fff;--s2:#f1f2f6;--t:#151720;--m:#747988;--l:#e1e4eb;--a:#655cf5;--as:#eeecff;--g:#12845a;--gs:#e8f7ef;--r:#c43e54;--rs:#ffedf1;--w:#a56a00;--ws:#fff4dc;--sh:0 10px 34px rgba(20,25,45,.065);--rad:16px}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--bg);color:var(--t);font:14px/1.5 Inter,system-ui,-apple-system,"Segoe UI",sans-serif;-webkit-font-smoothing:antialiased}
button,input,select{font:inherit}button{cursor:pointer}.shell{max-width:1440px;margin:auto;padding:18px 24px 50px}
.top{height:60px;display:flex;align-items:center;justify-content:space-between;gap:18px}.brand{display:flex;align-items:center;gap:11px}.logo{width:42px;height:42px;border-radius:13px;display:grid;place-items:center;background:linear-gradient(135deg,#e8e5ff,#dff8fa);font-size:20px}.brand b{display:block;font-size:17px}.brand small{display:block;color:var(--m);font-size:9px;letter-spacing:.15em;text-transform:uppercase;font-weight:800}
.nav{display:flex;gap:4px;padding:5px;background:var(--s);border:1px solid var(--l);border-radius:14px;box-shadow:var(--sh)}.nav button,.bottom button{border:0;background:transparent;color:var(--m);font-weight:800;border-radius:10px;padding:9px 12px;transition:.18s}.nav button.active,.bottom button.active{background:var(--as);color:var(--a)}
.version{font-size:10px;color:var(--m)}.view{display:none;animation:in .2s ease}.view.active{display:block}@keyframes in{from{opacity:0;transform:translateY(5px)}to{opacity:1;transform:none}}
.hero{display:flex;align-items:flex-end;justify-content:space-between;gap:22px;padding:42px 0 22px}.eyebrow{font-size:10px;letter-spacing:.18em;text-transform:uppercase;color:var(--a);font-weight:900}.hero h1{font-size:clamp(34px,4.5vw,54px);line-height:.98;letter-spacing:-.055em;margin:7px 0 10px}.hero p{margin:0;color:var(--m);max-width:700px}
.metric-grid{display:grid;grid-template-columns:repeat(5,1fr);gap:9px}.metric,.panel,.lead{background:var(--s);border:1px solid var(--l);border-radius:var(--rad);box-shadow:var(--sh)}.metric{padding:15px;min-height:100px}.metric small{color:var(--m);font-size:9px;font-weight:900;text-transform:uppercase;letter-spacing:.12em}.metric strong{display:block;font-size:28px;line-height:1.1;margin-top:8px}.metric span{display:block;color:var(--m);font-size:10px;margin-top:4px}
.panel{padding:16px;margin-top:12px}.ph{display:flex;justify-content:space-between;gap:14px;margin-bottom:11px}.ph h2{margin:0;font-size:16px}.ph p{margin:3px 0 0;color:var(--m);font-size:11px}.btn{min-height:42px;border:1px solid var(--l);border-radius:11px;background:var(--s);color:var(--t);padding:9px 13px;font-weight:850;transition:.18s}.btn:hover{transform:translateY(-1px)}.primary{background:var(--a);border-color:var(--a);color:#fff;box-shadow:0 7px 18px rgba(101,92,245,.2)}
.searches,.leads{display:grid;gap:7px}.search{display:flex;justify-content:space-between;gap:12px;padding:12px 13px;background:var(--s2);border:1px solid transparent;border-radius:12px;cursor:pointer}.search:hover{border-color:#cbc7ff}.search b{font-size:12px}.search small{display:block;color:var(--m);font-size:10px}.search .count{text-align:right}.count strong{font-size:15px}
.filters{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:9px}.filter{border:1px solid var(--l);background:var(--s);color:var(--m);border-radius:10px;padding:8px 10px;font-size:11px;font-weight:800}.filter.active{background:var(--as);color:var(--a);border-color:#d5d1ff}
.lead{overflow:hidden;box-shadow:none}.lead.open{box-shadow:var(--sh)}.summary{display:grid;grid-template-columns:minmax(0,1fr) 60px auto 18px;align-items:center;gap:9px;min-height:70px;padding:12px 13px;cursor:pointer}.summary:hover{background:#fafaff}.name{font-weight:900;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.sub{color:var(--m);font-size:10px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.score{text-align:center;font-weight:950;font-size:16px}.prio{font-size:9px;font-weight:900;padding:5px 8px;border-radius:999px;background:var(--s2);color:var(--m)}.hot{background:var(--rs);color:var(--r)}.high{background:var(--ws);color:var(--w)}.chev{color:var(--m);transition:.18s}.open .chev{transform:rotate(180deg)}
.details{display:none;border-top:1px solid var(--l);padding:13px}.open .details{display:block;animation:in .18s}.detail-head{display:flex;justify-content:space-between;gap:15px;padding:13px;border-radius:13px;border:1px solid #dedbff;background:linear-gradient(135deg,#f5f3ff,#eefbfb)}.detail-head h3{margin:0;font-size:20px;letter-spacing:-.03em}.detail-head p{margin:3px 0;color:var(--m);font-size:10px}.bigscore{text-align:right}.bigscore strong{font-size:29px}.bigscore small{display:block;color:var(--m);font-size:9px}.badges,.chips,.actions{display:flex;flex-wrap:wrap;gap:6px;margin-top:7px}.badge,.chip,.service{font-size:9px;font-weight:800;padding:5px 7px;border-radius:8px}.badge{background:var(--s);border:1px solid var(--l);color:var(--m)}.chip{background:var(--rs);color:#763341}.service{background:var(--gs);color:#08734b}
.signals{display:grid;grid-template-columns:repeat(4,1fr);gap:7px;margin-top:8px}.signal,.block{border:1px solid var(--l);border-radius:11px;padding:10px}.signal small,.block h4{display:block;color:var(--m);font-size:8px;font-weight:900;text-transform:uppercase;letter-spacing:.1em}.signal b{display:block;font-size:11px;margin-top:3px;overflow-wrap:anywhere}.detail-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:8px}.block h4{margin:0 0 7px}.facts{display:grid;grid-template-columns:90px 1fr;gap:5px;font-size:10px}.facts b{color:var(--m)}.facts span{overflow-wrap:anywhere}.link{display:inline-block;background:var(--s2);border:1px solid var(--l);padding:4px 7px;border-radius:8px;text-decoration:none}.pitch{background:#fff9eb;border-color:#efdca9}.pitch pre{white-space:pre-wrap;margin:0;font:10px/1.55 inherit}
.find-grid{display:grid;grid-template-columns:1fr 1fr 150px;gap:9px}.field label{display:block;color:var(--m);font-size:9px;font-weight:900;text-transform:uppercase;letter-spacing:.11em;margin-bottom:5px}.field select{width:100%;min-height:44px;border:1px solid var(--l);border-radius:11px;background:var(--s);color:var(--t);padding:8px 10px}.status{margin-top:10px;padding:11px;border-radius:11px;background:var(--s2);color:var(--m);font-size:11px}.success{background:var(--gs);color:var(--g)}.error{background:var(--rs);color:var(--r)}
.analytics{display:grid;grid-template-columns:1fr 1fr;gap:10px}.rank{display:flex;justify-content:space-between;gap:12px;padding:8px 10px;background:var(--s2);border-radius:9px;margin-top:5px;font-size:10px}.rank strong{font-size:11px}.rank span{color:var(--m)}.bar{height:5px;background:var(--l);border-radius:99px;margin-top:5px;overflow:hidden}.bar i{display:block;height:100%;width:0;background:var(--a);border-radius:inherit;transition:.4s}
.themes{display:grid;grid-template-columns:repeat(4,1fr);gap:9px}.theme{padding:13px;cursor:pointer;box-shadow:none}.theme.active{border-color:var(--a);box-shadow:inset 0 0 0 1px var(--a);background:var(--as)}.theme b{display:block;font-size:12px}.theme span{font-size:10px;color:var(--m)}
.empty{padding:24px;text-align:center;color:var(--m);border:1px dashed var(--l);border-radius:12px;background:var(--s2);font-size:11px}
.toast{position:fixed;right:18px;bottom:18px;background:#171923;color:#fff;padding:10px 13px;border-radius:11px;font-size:11px;opacity:0;transform:translateY(8px);transition:.2s;z-index:100}.toast.show{opacity:1;transform:none}
.bottom{display:none}
body.dark{--bg:#0b1017;--s:#121923;--s2:#18212c;--t:#f3f6fa;--m:#9aa7b6;--l:#2a3543;--a:#8b80ff;--as:#211f42;--gs:#102c22;--rs:#301922;--ws:#302713;--sh:0 12px 35px rgba(0,0,0,.22)}body.dark .detail-head{background:linear-gradient(135deg,#1d1a35,#10272a)}body.dark .pitch{background:#292318;border-color:#5c4a24}
body.neo{--bg:#eeeae2;--s:#fffdf8;--s2:#e7e1d7;--l:#292d31;--sh:5px 6px 0 rgba(35,38,42,.12)}body.dark.neo{--bg:#090c11;--s:#121720;--s2:#1b232d;--l:#e5e9ef;--a:#ffd34f;--as:#332d16;--sh:5px 6px 0 rgba(0,0,0,.5)}
@media(max-width:980px){.shell{padding:10px 12px calc(88px + env(safe-area-inset-bottom))}.top{height:52px}.nav,.version{display:none}.brand small{display:none}.logo{width:39px;height:39px}.hero{padding:28px 0 17px;align-items:flex-start;flex-direction:column}.hero h1{font-size:36px}.hero p{font-size:12px}.hero>.btn{width:100%}.metric-grid{grid-template-columns:repeat(2,1fr);gap:7px}.metric{min-height:88px;padding:11px}.metric strong{font-size:23px}.metric:last-child{grid-column:1/-1}.panel{padding:12px;margin-top:9px}.find-grid,.analytics,.detail-grid{grid-template-columns:1fr}.signals{grid-template-columns:1fr 1fr}.summary{grid-template-columns:minmax(0,1fr) 52px 18px}.summary .prio{display:none}.details{padding:9px}.actions .btn{flex:1 1 145px}.themes{grid-template-columns:1fr 1fr}.bottom{position:fixed;display:grid;grid-template-columns:repeat(5,1fr);left:7px;right:7px;bottom:calc(6px + env(safe-area-inset-bottom));z-index:80;padding:5px;background:color-mix(in srgb,var(--s) 94%,transparent);backdrop-filter:blur(18px);border:1px solid var(--l);border-radius:16px;box-shadow:0 12px 35px rgba(0,0,0,.13)}.bottom button{min-height:49px;padding:3px 2px;font-size:9px}.bottom button span{display:block;font-size:16px;line-height:19px}.toast{left:12px;right:12px;bottom:calc(80px + env(safe-area-inset-bottom))}}
@media(max-width:430px){.shell{padding-left:8px;padding-right:8px}.hero h1{font-size:34px}.themes{grid-template-columns:1fr}.facts{grid-template-columns:76px 1fr}}
</style>
</head>
<body>
<div class="shell">
<header class="top"><div class="brand"><div class="logo">🎯</div><div><b>LeadHunter</b><small>Lead intelligence workspace</small></div></div><nav class="nav" id="nav"></nav><span class="version">v3.1.0</span></header>

<section class="view active" id="leads">
<div class="hero"><div><div class="eyebrow">Workspace</div><h1>Your leads.</h1><p>Find, understand and act on the businesses most worth your attention.</p></div><button class="btn primary" onclick="show('find')">🔎 Find new leads</button></div>
<div class="metric-grid"><div class="metric"><small>Total</small><strong id="mt">—</strong><span>Saved businesses</span></div><div class="metric"><small>Hot</small><strong id="mh">—</strong><span>Highest priority</span></div><div class="metric"><small>Qualified</small><strong id="mq">—</strong><span>Ready to pitch</span></div><div class="metric"><small>Contacted</small><strong id="mc">—</strong><span>Outreach started</span></div><div class="metric"><small>Won</small><strong id="mw">—</strong><span>Closed deals</span></div></div>
<section class="panel"><div class="ph"><div><h2>Saved searches</h2><p>Every discovery stays linked to its own result set.</p></div></div><div id="searches" class="searches"><div class="empty">Loading searches…</div></div></section>
<section class="panel"><div class="ph"><div><h2>Lead pipeline</h2><p>Compact cards stay scannable. Tap one to open the complete intelligence view.</p></div></div><div class="filters" id="filters"></div><div id="leads" class="leads"><div class="empty">Loading leads…</div></div></section>
</section>

<section class="view" id="find"><div class="hero"><div><div class="eyebrow">Discovery</div><h1>Find new leads.</h1><p>Choose a business type, city and result count. The search is persisted automatically.</p></div></div><section class="panel"><div class="find-grid"><div class="field"><label>Business type</label><select id="ft"></select></div><div class="field"><label>City</label><select id="fc"></select></div><div class="field"><label>Lead count</label><select id="fl"><option>10</option><option selected>20</option><option>30</option><option>50</option></select></div></div><div class="actions"><button class="btn primary" id="findbtn" onclick="discover()">🔎 Start discovery</button></div><div id="findstatus"></div></section><section class="panel"><div class="ph"><div><h2>Discovery workflow</h2><p>One continuous path from search to outreach.</p></div></div><div class="signals"><div class="signal"><small>01 · Discover</small><b>Find local prospects</b></div><div class="signal"><small>02 · Research</small><b>Inspect their presence</b></div><div class="signal"><small>03 · Score</small><b>Prioritize opportunity</b></div><div class="signal"><small>04 · Act</small><b>Pitch and hand off</b></div></div></section></section>

<section class="view" id="analytics"><div class="hero"><div><div class="eyebrow">Sales intelligence</div><h1>Know where to focus.</h1><p>See conversion, strongest markets and the services your leads are most likely to need.</p></div></div><div class="analytics"><section class="panel"><div class="ph"><div><h2>Conversion</h2><p>Current pipeline health.</p></div></div><div id="aconv"></div></section><section class="panel"><div class="ph"><div><h2>Best cities</h2><p>Opportunity concentration.</p></div></div><div id="acities"></div></section><section class="panel"><div class="ph"><div><h2>Business types</h2><p>Lead volume by category.</p></div></div><div id="atypes"></div></section><section class="panel"><div class="ph"><div><h2>Recommended services</h2><p>What to sell next.</p></div></div><div id="aservices"></div></section></div></section>

<section class="view" id="outreach"><div class="hero"><div><div class="eyebrow">Next actions</div><h1>Work the list.</h1><p>Start with the strongest leads that are not yet in active outreach.</p></div></div><section class="panel"><div class="ph"><div><h2>Ready for outreach</h2><p>Hot and qualified leads first.</p></div></div><div id="outreachlist" class="leads"><div class="empty">Loading outreach queue…</div></div></section></section>

<section class="view" id="settings"><div class="hero"><div><div class="eyebrow">Preferences</div><h1>Your workspace.</h1><p>Choose the presentation that works best for long research sessions.</p></div></div><section class="panel"><div class="ph"><div><h2>Appearance</h2><p>Saved locally on this device.</p></div></div><div class="themes" id="themes"><div class="theme" data-theme="light"><b>☀️ Light</b><span>Clean modern workspace</span></div><div class="theme" data-theme="dark"><b>🌙 Dark</b><span>Low-glare workspace</span></div><div class="theme" data-theme="light-neo"><b>✦ Light Neo</b><span>Sharper editorial feel</span></div><div class="theme" data-theme="dark-neo"><b>✦ Dark Neo</b><span>High-contrast power mode</span></div></div></section></section>
</div>
<div class="bottom" id="bottom"></div><div class="toast" id="toast"></div>

<script>
const C={types:[["Dental", "dental"], ["Hospital", "hospital"], ["Clinic", "clinic"], ["Restaurant", "restaurant"], ["Cafe", "cafe"], ["Bakery", "bakery"], ["Hotel", "hotel"], ["Resort", "resort"], ["School", "school"], ["College", "college"], ["University", "university"], ["Pharmacy", "pharmacy"], ["Gym", "gym"], ["Salon", "salon"], ["Beauty", "beauty"], ["Car Dealer", "car dealer"], ["Car Repair", "car repair"], ["Car Wash", "car wash"], ["Real Estate", "real estate"], ["Lawyer", "lawyer"], ["Accountant", "accountant"], ["Travel Agency", "travel agency"], ["Electronics", "electronics"], ["Clothing", "clothing"], ["Furniture", "furniture"], ["Jewellery", "jewellery"], ["Supermarket", "supermarket"], ["Hardware", "hardware"], ["Bank", "bank"], ["Insurance", "insurance"], ["Architect", "architect"], ["Construction", "construction"], ["Printing", "printing"], ["Photographer", "photographer"], ["Fuel", "fuel"], ["Veterinary", "veterinary"]],cities:["Jabalpur", "Bhopal", "Indore", "Gwalior", "Ujjain", "Sagar", "Rewa", "Satna", "Katni", "Chhindwara", "Dewas", "Ratlam", "Murwara", "Burhanpur", "Khandwa", "Bhind", "Morena", "Shivpuri", "Vidisha", "Damoh", "Mandsaur", "Neemuch", "Sehore", "Itarsi", "Betul", "Hoshangabad", "Singrauli", "Chhatarpur", "Tikamgarh", "Datia"]};
let S={view:"leads",leads:[],filter:"ALL"};
const $=x=>document.getElementById(x);
const esc=x=>{let d=document.createElement("div");d.textContent=x??"";return d.innerHTML};
async function api(url,opt={}){let r=await fetch(url,{credentials:"same-origin",headers:{"Accept":"application/json","Content-Type":"application/json"},...opt});let d=null;try{d=await r.json()}catch(e){}if(!r.ok)throw Error(d?.detail||`Request failed (${r.status})`);return d}
function toast(x){let e=$("toast");e.textContent=x;e.classList.add("show");clearTimeout(window.tt);window.tt=setTimeout(()=>e.classList.remove("show"),2300)}
const nav=[["leads","🏠","Leads"],["find","🔎","Find"],["analytics","▥","Analytics"],["outreach","↗","Outreach"],["settings","⚙","Settings"]];
function navs(){let h=nav.map(x=>`<button data-v="${x[0]}" class="${S.view===x[0]?"active":""}"><span>${x[1]}</span>${x[2]}</button>`).join("");$("nav").innerHTML=h;$("bottom").innerHTML=h;document.querySelectorAll("[data-v]").forEach(b=>b.onclick=()=>show(b.dataset.v))}
function show(v){S.view=v;navs();document.querySelectorAll(".view").forEach(x=>x.classList.toggle("active",x.id===v));if(v==="leads")load();if(v==="analytics")analytics();if(v==="outreach")outreach();scrollTo({top:0,behavior:"smooth"})}
function init(){ $("ft").innerHTML=C.types.map(x=>`<option value="${esc(x[1])}">${esc(x[0])}</option>`).join("");$("fc").innerHTML=C.cities.map(x=>`<option>${esc(x)}</option>`).join("");navs();theme(localStorage.getItem("lh-theme")||"light");load()}
function renderFilters(){$("filters").innerHTML=["ALL","HOT","QUALIFIED","CONTACTED"].map(x=>`<button class="filter ${S.filter===x?"active":""}" onclick="S.filter='${x}';renderFilters();renderLeads()">${x==="ALL"?"All":x[0]+x.slice(1).toLowerCase()}</button>`).join("")}
function rows(){return S.leads.filter(l=>S.filter==="ALL"||S.filter==="HOT"&&l.priority==="HOT"||S.filter==="QUALIFIED"&&["QUALIFIED","CONTACTED","RESPONDED","MEETING","PROPOSAL","NEGOTIATION","WON"].includes(l.status)||S.filter==="CONTACTED"&&["CONTACTED","RESPONDED","MEETING","PROPOSAL","NEGOTIATION","WON"].includes(l.status))}
function card(l){let r=l.research||{},g=r.google||{},p=l.problems||r.problems||[],sv=l.recommended_services||[],rank=l.search_result_rank||g.local_rank;return `<article class="lead" id="lead-${l.id}"><div class="summary" onclick="toggle(${l.id})"><div><div class="name">${esc(l.name||"Unnamed business")}</div><div class="sub">${esc(l.industry||"Business")} · ${esc(l.city||"—")} · ${rank?"Search #"+esc(rank):"Position not measured"}</div></div><div class="score">${esc(l.score??0)}</div><span class="prio ${l.priority==="HOT"?"hot":l.priority==="HIGH"?"high":""}">${esc(l.priority||"—")}</span><span class="chev">⌄</span></div><div class="details"><div class="detail-head"><div><h3>${esc(l.name||"Unnamed business")}</h3><p>${esc(l.city||"—")} · ${esc(l.industry||"—")}</p><div class="badges"><span class="badge">Status · ${esc(l.status||"NEW")}</span><span class="badge">Priority · ${esc(l.priority||"—")}</span>${rank?`<span class="badge">Search #${esc(rank)}</span>`:""}</div></div><div class="bigscore"><strong>${esc(l.score??0)}</strong><small>opportunity / 100</small></div></div><div class="signals"><div class="signal"><small>Website</small><b>${l.website?"Available":"Not found"}</b></div><div class="signal"><small>Phone</small><b>${l.phone?"Available":"Not found"}</b></div><div class="signal"><small>Google</small><b>${g.rating?esc(g.rating)+" ★":"Not found"}</b></div><div class="signal"><small>Reviews</small><b>${esc(g.review_count??"Not found")}</b></div></div><div class="detail-grid"><div class="block"><h4>Why this is an opportunity</h4>${p.length?p.slice(0,8).map(x=>`<span class="chip">${esc(x)}</span>`).join(" "):`<span class="badge">No major problem recorded.</span>`}</div><div class="block"><h4>Recommended services</h4>${sv.length?sv.slice(0,8).map(x=>`<span class="service">${esc(x)}</span>`).join(" "):`<span class="badge">Audit first</span>`}</div></div><div class="block" style="margin-top:8px"><h4>Verified contact & location</h4><div class="facts"><b>Address</b><span>${esc(l.address||"Not found")}</span><b>Phone</b><span>${esc(l.phone||"Not found")}</span><b>Email</b><span>${esc(l.email||"Not found")}</span><b>Website</b>${l.website?`<a class="link" target="_blank" rel="noopener" href="${esc(l.website)}">Open ↗</a>`:"<span>Not found</span>"}<b>Maps</b>${g.maps_url?`<a class="link" target="_blank" rel="noopener" href="${esc(g.maps_url)}">Open ↗</a>`:"<span>Not found</span>"}</div></div><div class="block" style="margin-top:8px"><h4>Score evidence</h4>${(r.score_breakdown||[]).length?(r.score_breakdown||[]).map(x=>`<div class="rank"><strong>${esc(x[0]??x.name??"Signal")}</strong><span>+${esc(x[1]??x.value??0)}</span></div>`).join(""):"<span class='badge'>No scoring evidence stored.</span>"}</div><div class="block pitch" id="pitch-${l.id}" style="display:none;margin-top:8px"><h4>Generated pitch</h4><pre></pre></div><div class="actions"><button class="btn primary" onclick="pitch(event,${l.id})">✍️ Generate pitch</button><button class="btn" onclick="telegram(event,${l.id})">📤 Send to Telegram</button><button class="btn" onclick="contact(event,${l.id})">✓ Mark contacted</button></div></div></article>`}
function renderLeads(){let x=rows();$("leads").innerHTML=x.length?x.map(card).join(""):`<div class="empty">No leads match this filter.</div>`}
function toggle(id){$("lead-"+id).classList.toggle("open")}
async function load(){try{let [a,b]=await Promise.all([api("/dashboard/api/leads?limit=300"),api("/dashboard/api/searches?limit=30")]);S.leads=a.leads||[];renderFilters();renderLeads();$("searches").innerHTML=b.searches?.length?b.searches.map(s=>`<div class="search" onclick="openSearch(${s.id})"><div><b>${esc(s.industry||"Business")} · ${esc(s.city||"—")}</b><small>${esc(s.status||"UNKNOWN")} · ${s.created_at?new Date(s.created_at).toLocaleString():"—"}</small></div><div class="count"><strong>${esc(s.result_count??s.succeeded??0)}</strong><small>leads</small></div></div>`).join(""):`<div class="empty">No searches yet. Start your first discovery.</div>`;let m=await api("/dashboard/api/analytics");$("mt").textContent=m.totals?.leads??0;$("mh").textContent=m.totals?.hot??0;$("mq").textContent=m.totals?.qualified??0;$("mc").textContent=m.totals?.contacted??0;$("mw").textContent=m.totals?.won??0}catch(e){$("leads").innerHTML=`<div class="empty">Couldn't load leads. ${esc(e.message)}<br><button class="btn" onclick="load()">Retry</button></div>`}}
async function openSearch(id){try{let d=await api(`/dashboard/api/searches/${id}/leads?limit=300`);S.leads=d.leads||[];S.filter="ALL";renderFilters();renderLeads();show("leads");toast("Search loaded")}catch(e){toast(e.message)}}
async function pitch(e,id){e.stopPropagation();let b=e.currentTarget;b.disabled=true;try{let d=await api(`/dashboard/api/leads/${id}/message`,{method:"POST",body:"{}"});let x=$("pitch-"+id);x.style.display="block";x.querySelector("pre").textContent=d.message||"";toast("Pitch generated")}catch(x){toast(x.message)}finally{b.disabled=false}}
async function telegram(e,id){e.stopPropagation();let b=e.currentTarget;b.disabled=true;try{await api(`/dashboard/api/leads/${id}/telegram`,{method:"POST",body:"{}"});toast("Lead sent to Telegram")}catch(x){toast(x.message)}finally{b.disabled=false}}
async function contact(e,id){e.stopPropagation();try{await api(`/dashboard/api/leads/${id}/status`,{method:"PATCH",body:JSON.stringify({status:"CONTACTED"})});toast("Marked contacted");load()}catch(x){toast(x.message)}}
async function discover(){let b=$("findbtn");b.disabled=true;b.textContent="Starting…";$("findstatus").className="status";$("findstatus").textContent="Creating discovery job…";try{let d=await api("/dashboard/api/discover",{method:"POST",body:JSON.stringify({business_type:$("ft").value,city:$("fc").value,limit:Number($("fl").value)})});for(let i=0;i<120;i++){await new Promise(r=>setTimeout(r,1200));let j=(await api(`/dashboard/api/jobs/${d.job_id}`)).job||{};$("findstatus").textContent=`Discovery #${d.job_id}: ${j.status||"RUNNING"} · ${j.succeeded??0} saved · ${j.failed??0} failed`;if(j.status==="DONE"){ $("findstatus").className="status success";$("findstatus").textContent=`✓ Discovery complete — ${j.succeeded??0} leads saved.`;load();break}if(j.status==="FAILED"){ $("findstatus").className="status error";$("findstatus").textContent=`Discovery failed: ${j.error||"Unknown error"}`;break}}}catch(e){$("findstatus").className="status error";$("findstatus").textContent=e.message}finally{b.disabled=false;b.textContent="🔎 Start discovery"}}
function ranks(id,items){if(!items?.length){$(id).innerHTML='<div class="empty">No data yet.</div>';return}let max=Math.max(...items.map(x=>Number(x.count||0)),1);$(id).innerHTML=items.map(x=>`<div class="rank"><div><strong>${esc(x.name)}</strong><div class="bar"><i style="width:${Math.round(Number(x.count||0)/max*100)}%"></i></div></div><span>${esc(x.count)}</span></div>`).join("")}
async function analytics(){try{let a=await api("/dashboard/api/analytics"),c=a.conversion||{},t=a.totals||{};$("aconv").innerHTML=[["Qualified",t.qualified,c.qualified_rate],["Contacted",t.contacted,c.contact_rate],["Won",t.won,c.win_rate]].map(x=>`<div class="rank"><strong>${x[0]}</strong><span>${x[1]??0} · ${x[2]??0}%</span></div>`).join("");ranks("acities",a.cities);ranks("atypes",a.industries);ranks("aservices",a.services)}catch(e){toast(e.message)}}
async function outreach(){try{let d=await api("/dashboard/api/outreach?limit=50");$("outreachlist").innerHTML=d.leads?.length?d.leads.map(card).join(""):`<div class="empty">No outreach-ready leads right now.</div>`}catch(e){$("outreachlist").innerHTML=`<div class="empty">Couldn't load outreach queue. ${esc(e.message)}</div>`}}
function theme(x){document.body.classList.toggle("dark",x==="dark"||x==="dark-neo");document.body.classList.toggle("neo",x==="light-neo"||x==="dark-neo");document.querySelectorAll(".theme").forEach(t=>t.classList.toggle("active",t.dataset.theme===x));localStorage.setItem("lh-theme",x)}
document.querySelectorAll(".theme").forEach(x=>x.onclick=()=>theme(x.dataset.theme));
init();
</script>
</body></html>'''
