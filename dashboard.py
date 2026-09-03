"""LeadHunter dashboard.

Single canonical dashboard surface. The dashboard owns its page, API routes,
responsive frontend, discovery orchestration and Telegram handoff. Discovery,
research, scoring and persistence remain in their dedicated modules.
"""
import base64
import html
import json
import logging
import os
import secrets
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from ai import generate_whatsapp_message
from database import Database
from constants import BUSINESS_TYPES as CANONICAL_BUSINESS_TYPES, CITIES as CANONICAL_CITIES, PIPELINE_STATUSES
from config import APP_VERSION
from lead_workflow import run_discovery_job

log = logging.getLogger(__name__)
router = APIRouter()

BUSINESS_TYPES = CANONICAL_BUSINESS_TYPES
CITIES = CANONICAL_CITIES
STAGES = PIPELINE_STATUSES

def auth(value: str | None) -> None:
    user = os.getenv("DASHBOARD_USER", "").strip()
    password = os.getenv("DASHBOARD_PASSWORD", "").strip()
    if not user or not password or not value or not value.startswith("Basic "):
        raise HTTPException(401, "Dashboard authentication required", headers={"WWW-Authenticate": "Basic"})
    try:
        decoded = base64.b64decode(value[6:]).decode("utf-8")
        supplied_user, supplied_password = decoded.split(":", 1)
    except Exception:
        raise HTTPException(401, "Invalid dashboard credentials", headers={"WWW-Authenticate": "Basic"})
    if not (secrets.compare_digest(supplied_user, user) and secrets.compare_digest(supplied_password, password)):
        raise HTTPException(401, "Invalid dashboard credentials", headers={"WWW-Authenticate": "Basic"})


class DiscoveryRequest(BaseModel):
    business_type: str
    city: str
    limit: int = 20


class StatusRequest(BaseModel):
    status: str


def mutation_guard(request: Request) -> None:
    origin = request.headers.get("origin") or request.headers.get("referer")
    if not origin:
        return
    allowed = request.base_url.netloc
    from urllib.parse import urlparse
    if urlparse(origin).netloc != allowed:
        raise HTTPException(403, "Cross-origin state change blocked")


async def _run_discovery(job_id: int, city: str, industry: str, limit: int) -> None:
    await run_discovery_job(job_id, city, industry, limit)


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(authorization: str | None = Header(default=None)):
    auth(authorization)
    return HTMLResponse(PAGE)


@router.get("/dashboard/api/leads")
async def leads(
    authorization: str | None = Header(default=None),
    priority: str | None = None,
    limit: int = Query(100, ge=1, le=300),
    offset: int = Query(0, ge=0),
):
    auth(authorization)
    db = Database()
    rows = await db.list_leads_with_research(priority, limit, offset)
    return {"ok": True, "leads": rows, "count": len(rows)}


@router.get("/dashboard/api/leads/{business_id}")
async def lead_detail(business_id: int, authorization: str | None = Header(default=None)):
    auth(authorization)
    db = Database()
    lead = await db.get_lead(business_id)
    if not lead:
        raise HTTPException(404, "Lead not found")
    return {
        "ok": True,
        "lead": lead,
        "research": await db.get_research(business_id),
        "activities": await db.activities(business_id, 30),
    }


@router.get("/dashboard/api/searches")
async def searches(
    authorization: str | None = Header(default=None),
    limit: int = Query(30, ge=1, le=100),
):
    auth(authorization)
    return {"ok": True, "searches": await Database().list_searches(limit)}


@router.get("/dashboard/api/searches/{search_id}/leads")
async def search_leads(
    search_id: int,
    authorization: str | None = Header(default=None),
    limit: int = Query(100, ge=1, le=300),
):
    auth(authorization)
    db = Database()
    search = await db.get_search(search_id)
    if not search:
        raise HTTPException(404, "Search not found")
    rows = await db.list_search_results(search_id, limit)
    return {"ok": True, "search": search, "leads": rows, "count": len(rows)}


@router.post("/dashboard/api/discover")
async def discover(
    payload: DiscoveryRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    authorization: str | None = Header(default=None),
):
    auth(authorization)
    mutation_guard(request)
    allowed_types = {value for _, value in BUSINESS_TYPES}
    if payload.business_type not in allowed_types:
        raise HTTPException(400, "Unsupported business type")
    if payload.city not in CITIES:
        raise HTTPException(400, "Unsupported Madhya Pradesh city")
    limit = min(max(int(payload.limit), 1), 50)
    db = Database()
    job_id = await db.create_job("DISCOVERY", payload.city, payload.business_type)
    if not job_id:
        raise HTTPException(503, "Could not create discovery job")
    background_tasks.add_task(_run_discovery, job_id, payload.city, payload.business_type, limit)
    return {"ok": True, "job_id": job_id, "status": "RUNNING", "city": payload.city, "business_type": payload.business_type, "limit": limit}


@router.get("/dashboard/api/jobs/{job_id}")
async def job_status(job_id: int, authorization: str | None = Header(default=None)):
    auth(authorization)
    row = Database().client.table("jobs").select("*").eq("id", job_id).limit(1).execute()
    return {"ok": True, "job": row.data[0] if row.data else None}


@router.get("/dashboard/api/analytics")
async def analytics(authorization: str | None = Header(default=None)):
    auth(authorization)
    data = await Database().analytics()
    return {"ok": True, **data}


@router.get("/dashboard/api/outreach")
async def outreach(
    authorization: str | None = Header(default=None),
    limit: int = Query(30, ge=1, le=100),
):
    auth(authorization)
    rows = [x for x in await Database().list_leads(None, 1000, 0) if x.get("status") in {"NEW", "RESEARCHED", "QUALIFIED"}]
    rows.sort(key=lambda x: (0 if x.get("priority") == "HOT" else 1 if x.get("priority") == "HIGH" else 2, -int(x.get("score", 0) or 0)))
    return {"ok": True, "leads": rows[:limit]}


@router.post("/dashboard/api/leads/{business_id}/message")
async def pitch_message(business_id: int, request: Request, authorization: str | None = Header(default=None)):
    auth(authorization)
    mutation_guard(request)
    db = Database()
    lead = await db.get_lead(business_id)
    if not lead:
        raise HTTPException(404, "Lead not found")
    message = await generate_whatsapp_message(lead, await db.get_research(business_id))
    await db.record_activity(business_id, "MESSAGE_GENERATED", "dashboard", "Pitch message generated")
    return {"ok": True, "message": message}


@router.patch("/dashboard/api/leads/{business_id}/status")
async def set_lead_status(
    business_id: int,
    payload: StatusRequest,
    request: Request,
    authorization: str | None = Header(default=None),
):
    auth(authorization)
    mutation_guard(request)
    if payload.status not in STAGES:
        raise HTTPException(400, "Invalid status")
    db = Database()
    if not await db.get_lead(business_id):
        raise HTTPException(404, "Lead not found")
    await db.set_status(business_id, payload.status)
    await db.record_activity(business_id, "STATUS_" + payload.status, "dashboard", "Status changed from dashboard")
    return {"ok": True, "status": payload.status}


@router.post("/dashboard/api/leads/{business_id}/telegram")
async def send_lead_to_telegram(business_id: int, request: Request, authorization: str | None = Header(default=None)):
    auth(authorization)
    mutation_guard(request)
    admin = os.getenv("ADMIN_TELEGRAM_ID", "").strip()
    if not admin:
        raise HTTPException(503, "ADMIN_TELEGRAM_ID is not configured")
    db = Database()
    lead = await db.get_lead(business_id)
    if not lead:
        raise HTTPException(404, "Lead not found")
    research = await db.get_research(business_id)
    google = research.get("google") or {}
    local = research.get("local") or {}
    phone = lead.get("phone") or ((local.get("phones") or [None])[0] if isinstance(local.get("phones"), list) else None)
    email = lead.get("email") or ((local.get("emails") or [None])[0] if isinstance(local.get("emails"), list) else None)
    score = int(lead.get("score", 0) or 0)
    problems = lead.get("problems") or research.get("problems") or []
    services = lead.get("recommended_services") or []
    breakdown = research.get("score_breakdown") or []
    lines = [
        "📤 <b>LEADHUNTER · LEAD HANDOFF</b>",
        "━━━━━━━━━━━━━━━━━━━━",
        f"🏢 <b>{html.escape(str(lead.get('name') or 'Unnamed Business'))}</b>",
        f"📍 {html.escape(str(lead.get('city') or '—'))} · {html.escape(str(lead.get('industry') or '—'))}",
        "",
        f"🎯 <b>Opportunity:</b> {score}/100",
        f"🔥 <b>Priority:</b> {html.escape(str(lead.get('priority') or '—'))}",
        f"🧭 <b>Status:</b> {html.escape(str(lead.get('status') or 'NEW'))}",
        "",
        f"🌐 <b>Website:</b> {html.escape(str(lead.get('website') or 'Not found'))}",
        f"📞 <b>Phone:</b> {html.escape(str(phone or 'Not found'))}",
        f"✉️ <b>Email:</b> {html.escape(str(email or 'Not found'))}",
        f"📍 <b>Provider position:</b> #{html.escape(str(google.get('local_rank'))) if google.get('local_rank') else 'Not measured'}",
        f"⭐ <b>Rating:</b> {html.escape(str(google.get('rating') or 'Not found'))} · 💬 {html.escape(str(google.get('review_count') or '0'))} reviews",
        "",
        "⚠️ <b>PROBLEMS / OPPORTUNITY</b>",
    ]
    lines += [f"• {html.escape(str(x))}" for x in problems[:8]] or ["• No major problem recorded."]
    lines += ["", "🛠️ <b>RECOMMENDED SERVICES</b>"]
    lines += [f"• {html.escape(str(x))}" for x in services[:8]] or ["• Audit first"]
    if breakdown:
        lines += ["", "💡 <b>WHY THIS LEAD</b>"]
        lines += [f"• {html.escape(str(k))}: <b>+{html.escape(str(v))}</b>" for k, v in breakdown if v]
    maps_url = google.get("maps_url") or lead.get("google_maps_url")
    website = lead.get("website")
    if maps_url or website:
        lines += ["", "🔗 <b>LINKS</b>"]
        if maps_url and str(maps_url).startswith("http"):
            lines.append(f'<a href="{html.escape(str(maps_url), quote=True)}">📍 Google Maps</a>')
        if website and str(website).startswith("http"):
            lines.append(f'<a href="{html.escape(str(website), quote=True)}">🌐 Website</a>')
    bot_app = getattr(getattr(request.app, "state", None), "bot", None)
    if not bot_app or not getattr(bot_app, "bot", None):
        raise HTTPException(503, "Telegram bot is not ready")
    try:
        sent = await bot_app.bot.send_message(chat_id=int(admin), text="\n".join(lines), parse_mode="HTML", disable_web_page_preview=True)
    except Exception as exc:
        raise HTTPException(502, f"Telegram send failed: {str(exc)[:300]}")
    await db.record_activity(business_id, "TELEGRAM_SENT", "dashboard", "Lead details sent to Telegram")
    await db.record_telegram_event(business_id, "LEAD_HANDOFF", getattr(sent, "message_id", None))
    return {"ok": True, "business_id": business_id, "telegram_message_id": getattr(sent, "message_id", None)}


PAGE = r'''<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#f6f7fb"><meta name="color-scheme" content="light dark">
<title>LeadHunter · Lead Intelligence</title>
<style>
:root{--bg:#f6f7fb;--surface:#fff;--surface2:#f1f3f8;--text:#151821;--muted:#737b8c;--line:#e1e5ee;--accent:#655cf6;--accent2:#16a6b6;--good:#16845b;--warn:#a66a00;--bad:#c43c52;--shadow:0 12px 35px rgba(25,30,50,.07);--r:18px}*{box-sizing:border-box}html,body{margin:0;min-height:100%;background:var(--bg);color:var(--text);font:14px/1.5 Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif}button,input,select{font:inherit}button{cursor:pointer}a{color:inherit}.shell{max-width:1380px;margin:auto;padding:18px 22px 42px}.topbar{height:62px;display:flex;align-items:center;justify-content:space-between;gap:16px}.brand{display:flex;align-items:center;gap:11px}.logo{width:43px;height:43px;border-radius:14px;display:grid;place-items:center;background:#e9e7ff;font-size:21px}.brand b{display:block;font-size:17px;letter-spacing:-.02em}.brand small{display:block;color:var(--muted);font-size:9px;text-transform:uppercase;letter-spacing:.15em}.desktop-nav{display:flex;gap:4px;padding:5px;background:var(--surface);border:1px solid var(--line);border-radius:14px;box-shadow:var(--shadow)}.desktop-nav button,.bottom button{border:0;background:transparent;color:var(--muted);font-weight:750;border-radius:10px;padding:9px 11px}.desktop-nav button.active{background:#efeeff;color:var(--accent)}.version{font-size:10px;color:var(--muted)}.view{display:none}.view.active{display:block}.herohead{display:flex;align-items:flex-end;justify-content:space-between;gap:20px;margin:45px 0 22px}.eyebrow{font-size:10px;letter-spacing:.18em;text-transform:uppercase;color:var(--accent);font-weight:850}.herohead h1{font-size:clamp(36px,5.5vw,58px);line-height:.96;letter-spacing:-.06em;margin:7px 0 10px}.herohead p{margin:0;color:var(--muted);font-size:15px;max-width:720px}.metrics{display:grid;grid-template-columns:repeat(5,1fr);gap:10px}.metric,.panel,.lead,.theme{background:var(--surface);border:1px solid var(--line);border-radius:var(--r);box-shadow:var(--shadow)}.metric{padding:15px;min-height:104px}.metric small{display:block;color:var(--muted);font-size:9px;text-transform:uppercase;letter-spacing:.12em;font-weight:850}.metric strong{display:block;font-size:29px;line-height:1.1;margin-top:8px}.metric span{font-size:11px;color:var(--muted)}.panel{padding:16px;margin-top:13px}.panelhead{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;margin-bottom:12px}.panelhead h2{margin:0;font-size:17px;letter-spacing:-.02em}.panelhead p{margin:3px 0 0;color:var(--muted);font-size:12px}.searches{display:grid;gap:7px}.searchrow{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:12px 13px;border:1px solid var(--line);border-radius:13px;background:var(--surface2);cursor:pointer}.searchrow:hover{border-color:#c9c5ff}.searchrow b{font-size:13px}.searchrow small{display:block;color:var(--muted);font-size:10px;margin-top:2px}.searchcount{text-align:right;font-weight:900}.searchcount small{font-weight:500}.leadlist{display:grid;gap:8px}.lead{overflow:hidden;box-shadow:none}.lead.open{box-shadow:var(--shadow)}.summary{display:grid;grid-template-columns:minmax(0,1fr) 70px auto 20px;align-items:center;gap:10px;padding:13px;min-height:68px;cursor:pointer}.summary:hover{background:#fafbfe}.name{font-weight:850;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.subline{color:var(--muted);font-size:11px;margin-top:2px}.score{font-weight:950;text-align:center}.priority{font-size:9px;font-weight:850;padding:5px 8px;border-radius:99px;background:var(--surface2);color:var(--muted)}.priority.hot{background:#fff0f3;color:var(--bad)}.priority.high{background:#fff7e8;color:var(--warn)}.details{border-top:1px solid var(--line);padding:14px}.leadhero{padding:15px;border-radius:14px;background:linear-gradient(135deg,#f4f2ff,#eefafa);border:1px solid #dedcff}.leadhero h2{margin:0;font-size:22px;letter-spacing:-.03em}.badges,.chips,.actions,.links{display:flex;flex-wrap:wrap;gap:6px}.badges{margin-top:8px}.badge,.chip,.service,.link{font-size:10px;padding:6px 8px;border-radius:9px}.badge{background:var(--surface);border:1px solid var(--line);color:var(--muted)}.signals{display:grid;grid-template-columns:repeat(4,1fr);gap:7px;margin-top:9px}.signal{border:1px solid var(--line);border-radius:12px;padding:10px}.signal b{display:block;color:var(--muted);font-size:8px;text-transform:uppercase;letter-spacing:.1em}.signal strong{display:block;margin-top:4px;font-size:13px;overflow-wrap:anywhere}.signal.good{border-color:#b9e6d2}.signal.warn{border-color:#efd39a}.detailgrid{display:grid;grid-template-columns:1fr 1fr;gap:8px}.block{border:1px solid var(--line);border-radius:13px;padding:12px;margin-top:8px}.block h3{margin:0 0 8px;font-size:9px;text-transform:uppercase;letter-spacing:.14em}.chip{background:#fff1f4;color:#71303b}.service{background:#eaf8f2;color:#08734b}.facts{display:grid;grid-template-columns:100px 1fr;gap:6px;font-size:11px}.facts b{color:var(--muted)}.facts span{overflow-wrap:anywhere}.link{background:var(--surface2);text-decoration:none;border:1px solid var(--line)}.pitch{background:#fff8e9;border-color:#efd79d}.pitch p{margin:0;font-size:11px;white-space:pre-wrap}.btn{border:1px solid var(--line);background:var(--surface);color:var(--text);border-radius:11px;min-height:42px;padding:9px 13px;font-weight:800}.btn.primary{background:var(--accent);border-color:var(--accent);color:#fff}.btn:disabled{opacity:.55;cursor:not-allowed}.findgrid{display:grid;grid-template-columns:1fr 1fr 160px;gap:10px}.field label{display:block;color:var(--muted);font-size:9px;text-transform:uppercase;letter-spacing:.12em;font-weight:850;margin-bottom:5px}.field select{width:100%;min-height:44px;border:1px solid var(--line);border-radius:11px;background:var(--surface);color:var(--text);padding:8px 10px}.statusbox{margin-top:10px}.analyticsgrid,.settingsgrid{display:grid;grid-template-columns:1fr 1fr;gap:10px}.rank{display:flex;justify-content:space-between;gap:12px;padding:8px 10px;background:var(--surface2);border-radius:9px;margin-top:5px;font-size:11px}.empty{padding:25px;text-align:center;color:var(--muted);border:1px dashed var(--line);border-radius:13px;background:var(--surface2)}.theme{padding:16px;cursor:pointer;box-shadow:none}.theme.active{border-color:var(--accent);box-shadow:inset 0 0 0 1px var(--accent);background:#f3f2ff}.theme b{display:block}.theme span{font-size:11px;color:var(--muted)}.bottom{display:none}.toast{position:fixed;right:18px;bottom:18px;background:#171a24;color:#fff;border-radius:12px;padding:10px 13px;opacity:0;transform:translateY(8px);transition:.2s;z-index:80;font-size:11px;pointer-events:none}.toast.show{opacity:1;transform:none}body.dark{--bg:#0b1017;--surface:#121923;--surface2:#18212c;--text:#f3f6fa;--muted:#9aa7b6;--line:#283443;--accent:#8b80ff;--accent2:#2ad3dc;--good:#3cdaa0;--warn:#ffd166;--bad:#ff7485}body.dark .leadhero{background:linear-gradient(135deg,#1d1a35,#10272a)}body.dark .theme.active{background:#1b1a32}body.neo{--bg:#eeeae2;--surface:#fffdf8;--surface2:#e6e0d6;--line:#24282d;--shadow:5px 6px 0 #24282d22}body.dark.neo{--bg:#090c11;--surface:#121720;--surface2:#1b232d;--line:#e4e9ef;--accent:#ffd34f;--shadow:5px 6px 0 #000}.skeleton{height:11px;background:var(--surface2);border-radius:6px;animation:pulse 1.2s infinite alternate}@keyframes pulse{to{opacity:.45}}@media(max-width:900px){.shell{padding:10px 10px 92px}.topbar{height:52px}.desktop-nav{display:none}.version{display:none}.brand small{display:none}.logo{width:40px;height:40px}.herohead{margin:28px 0 17px}.herohead h1{font-size:36px}.herohead p{font-size:13px}.metrics{grid-template-columns:1fr 1fr;gap:7px}.metric{padding:11px;min-height:91px}.metric strong{font-size:23px}.metric:last-child{grid-column:span 2}.panel{padding:12px;margin-top:9px}.signals{grid-template-columns:1fr 1fr}.detailgrid,.analyticsgrid,.settingsgrid,.findgrid{grid-template-columns:1fr}.summary{grid-template-columns:minmax(0,1fr) 52px 18px;gap:7px}.summary .priority{display:none}.summary{padding:12px}.details{padding:9px}.facts{grid-template-columns:82px 1fr}.actions .btn{flex:1 1 145px}.bottom{position:fixed;display:grid;grid-template-columns:repeat(5,1fr);left:6px;right:6px;bottom:6px;z-index:60;padding:5px;background:color-mix(in srgb,var(--surface) 94%,transparent);backdrop-filter:blur(18px);border:1px solid var(--line);border-radius:16px;box-shadow:0 12px 35px rgba(0,0,0,.12)}.bottom button{min-height:49px;padding:4px 2px;font-size:9px}.bottom button span{display:block;font-size:16px;line-height:18px}.searchrow{padding:11px}.searchcount{font-size:14px}}@media(max-width:420px){.shell{padding-left:8px;padding-right:8px}.herohead h1{font-size:34px}.panelhead p{font-size:11px}.btn{min-height:44px}.leadhero h2{font-size:19px}}
</style></head>
<body><div class="shell"><header class="topbar"><div class="brand"><div class="logo">🎯</div><div><b>LeadHunter</b><small>Lead intelligence workspace</small></div></div><nav class="desktop-nav" id="desktop-nav"></nav><span class="version">v__VERSION__</span></header>
<main>
<section class="view active" id="leads"><div class="herohead"><div><div class="eyebrow">Workspace</div><h1>Your leads.</h1><p>Saved opportunities, previous searches and your next best prospects — without starting a new search every time.</p></div><button class="btn primary" data-go="find">🔎 Find new leads</button></div>
<div class="metrics"><div class="metric"><small>Total</small><strong id="m-total">—</strong><span>Saved businesses</span></div><div class="metric"><small>Hot</small><strong id="m-hot">—</strong><span>Highest priority</span></div><div class="metric"><small>Qualified</small><strong id="m-qualified">—</strong><span>Ready to pitch</span></div><div class="metric"><small>Contacted</small><strong id="m-contacted">—</strong><span>Outreach started</span></div><div class="metric"><small>Won</small><strong id="m-won">—</strong><span>Closed deals</span></div></div>
<section class="panel"><div class="panelhead"><div><h2>Saved searches</h2><p>Your discovery history. Open one to see the leads it produced.</p></div></div><div id="searches" class="searches"><div class="empty">Loading saved searches…</div></div></section>
<section class="panel"><div class="panelhead"><div><h2>Lead pipeline</h2><p>Open a lead for verified research, Google context, opportunity reasons and actions.</p></div></div><div id="lead-list" class="leadlist"><div class="empty">Loading your leads…</div></div></section></section>
<section class="view" id="find"><div class="herohead"><div><div class="eyebrow">Discovery</div><h1>Find new leads.</h1><p>Choose a business type and Madhya Pradesh city. Results are saved automatically.</p></div></div><section class="panel"><div class="findgrid"><div class="field"><label>Business type</label><select id="find-type"></select></div><div class="field"><label>City</label><select id="find-city"></select></div><div class="field"><label>Lead count</label><select id="find-limit"><option>10</option><option selected>20</option><option>30</option><option>50</option></select></div></div><div class="actions" style="margin-top:10px"><button class="btn primary" id="find-btn">🔎 Start discovery</button></div><div id="find-status" class="statusbox"></div></section></section>
<section class="view" id="analytics"><div class="herohead"><div><div class="eyebrow">Sales intelligence</div><h1>Know where to focus.</h1><p>Understand your pipeline, strongest markets and the services your leads need.</p></div></div><div class="analyticsgrid"><section class="panel"><div class="panelhead"><div><h2>Pipeline</h2><p>Current conversion picture.</p></div></div><div id="a-total"><div class="empty">Loading…</div></div></section><section class="panel"><div class="panelhead"><div><h2>Best cities</h2><p>Where your lead volume is concentrated.</p></div></div><div id="a-cities"><div class="empty">Loading…</div></div></section><section class="panel"><div class="panelhead"><div><h2>Business types</h2><p>Which markets you are finding most.</p></div></div><div id="a-industries"><div class="empty">Loading…</div></div></section><section class="panel"><div class="panelhead"><div><h2>Recommended services</h2><p>Common sales opportunities.</p></div></div><div id="a-services"><div class="empty">Loading…</div></div></section></div></section>
<section class="view" id="outreach"><div class="herohead"><div><div class="eyebrow">Next action</div><h1>Who should you contact?</h1><p>High-priority leads that have not moved into outreach yet.</p></div></div><section class="panel"><div id="outreach-list"><div class="empty">Loading outreach queue…</div></div></section></section>
<section class="view" id="settings"><div class="herohead"><div><div class="eyebrow">Preferences</div><h1>Make it yours.</h1><p>Choose a visual system. Your choice stays on this device.</p></div></div><div class="settingsgrid"><div class="theme" data-theme="light"><b>☀️ Light Modern</b><span>Clean SaaS workspace, soft surfaces and quiet borders.</span></div><div class="theme" data-theme="dark"><b>🌙 Dark Modern</b><span>Graphite surfaces with subtle purple/cyan accents.</span></div><div class="theme" data-theme="neo"><b>✦ Light Neo</b><span>Stronger borders and tactile controls.</span></div><div class="theme" data-theme="darkneo"><b>⚡ Dark Neo</b><span>High contrast with heavier tactile styling.</span></div></div></section>
</main></div><nav class="bottom" id="bottom"></nav><div class="toast" id="toast"></div>
<script>
(function(){
const NAV=[['leads','📋','Leads'],['find','🔎','Find'],['analytics','📊','Analytics'],['outreach','✉️','Outreach'],['settings','⚙️','Settings']];
const TYPES=__TYPES__;
const CITIES=__CITIES__;
const STAGES=__STAGES__;
const state={page:'leads',leads:[],searchLeads:null};
const $=s=>document.querySelector(s), esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function toast(v){const t=$('#toast');t.textContent=v;t.classList.add('show');clearTimeout(window.__toast);window.__toast=setTimeout(()=>t.classList.remove('show'),2600)}
async function api(url,opt={}){const r=await fetch(url,{credentials:'same-origin',...opt,headers:{Accept:'application/json',...(opt.headers||{})}});let j={};try{j=await r.json()}catch{}if(!r.ok)throw Error(j.detail||'Request failed ('+r.status+')');return j}
function pageFromHash(){const p=location.hash.replace('#','');return NAV.some(x=>x[0]===p)?p:'leads'}
function nav(){const p=state.page;$('#desktop-nav').innerHTML=NAV.map(x=>`<button class="${p===x[0]?'active':''}" data-page="${x[0]}">${x[1]} ${x[2]}</button>`).join('');$('#bottom').innerHTML=NAV.map(x=>`<button class="${p===x[0]?'active':''}" data-page="${x[0]}"><span>${x[1]}</span>${x[2]}</button>`).join('');document.querySelectorAll('[data-page]').forEach(b=>b.onclick=()=>go(b.dataset.page))}
function go(p){state.page=NAV.some(x=>x[0]===p)?p:'leads';history.replaceState(null,'','#'+state.page);document.querySelectorAll('.view').forEach(v=>v.classList.toggle('active',v.id===state.page));nav();window.scrollTo(0,0);if(state.page==='analytics')loadAnalytics();if(state.page==='outreach')loadOutreach()}
function renderMetrics(){const a=state.leads;$('#m-total').textContent=a.length;$('#m-hot').textContent=a.filter(x=>x.priority==='HOT').length;$('#m-qualified').textContent=a.filter(x=>['RESEARCHED','QUALIFIED','CONTACTED','RESPONDED','MEETING','PROPOSAL','NEGOTIATION','WON'].includes(x.status)).length;$('#m-contacted').textContent=a.filter(x=>['CONTACTED','RESPONDED','MEETING','PROPOSAL','NEGOTIATION','WON'].includes(x.status)).length;$('#m-won').textContent=a.filter(x=>x.status==='WON').length}
function leadCard(l){const r=l.research||{},g=r.google||{},w=r.website||{},local=r.local||{};const problems=(r.problems||l.problems||[]).slice(0,5).map(x=>`<span class="chip">${esc(typeof x==='string'?x:x.problem||x.title||JSON.stringify(x))}</span>`).join('');const services=(l.recommended_services||[]).slice(0,6).map(x=>`<span class="service">${esc(x)}</span>`).join('');const rank=g.local_rank?'#'+esc(g.local_rank):'Not measured';return `<article class="lead"><div class="summary" data-open="${l.id}"><div><div class="name">${esc(l.name||'Unnamed business')}</div><div class="subline">${esc(l.industry||'Business')} · ${esc(l.city||'')}</div></div><div class="score">${esc(l.score??'—')}</div><span class="priority ${String(l.priority||'').toLowerCase()}">${esc(l.priority||'LOW')}</span><span>›</span></div><div class="details" id="detail-${l.id}" hidden><div class="leadhero"><h2>${esc(l.name||'Unnamed business')}</h2><div class="badges"><span class="badge">🎯 ${esc(l.score??'—')}/100</span><span class="badge">🔥 ${esc(l.priority||'LOW')}</span><span class="badge">🧭 ${esc(l.status||'NEW')}</span></div><div class="signals"><div class="signal ${g.local_rank?'good':'warn'}"><b>Provider position</b><strong>${rank}</strong></div><div class="signal ${w.exists?'good':'warn'}"><b>Website</b><strong>${w.exists?'Verified':'Missing'}</strong></div><div class="signal ${local.phone_found?'good':'warn'}"><b>Phone</b><strong>${local.phone_found?'Available':'Missing'}</strong></div><div class="signal ${local.email_found?'good':'warn'}"><b>Email</b><strong>${local.email_found?'Available':'Missing'}</strong></div></div></div><div class="detailgrid"><div class="block"><h3>Why this is an opportunity</h3><div class="chips">${problems||'<span class="badge">No major problem recorded.</span>'}</div></div><div class="block"><h3>Recommended services</h3><div class="badges">${services||'<span class="badge">Audit first</span>'}</div></div></div><div class="block"><h3>Verified contact & local data</h3><div class="facts"><b>Phone</b><span>${esc(l.phone||local.phones?.[0]||'Not available')}</span><b>Email</b><span>${esc(l.email||local.emails?.[0]||'Not available')}</span><b>Rating</b><span>${g.rating?esc(g.rating)+' / 5':'Not available'}${g.review_count?' · '+esc(g.review_count)+' reviews':''}</span><b>Website</b><span>${w.url?`<a href="${esc(w.url)}" target="_blank" rel="noopener">Open website ↗</a>`:(l.website?`<a href="${esc(l.website)}" target="_blank" rel="noopener">Open website ↗</a>`:'Not available')}</span><b>Search</b><span>${esc((r.search||{}).query||'—')}</span></div></div><div class="actions" style="margin-top:9px"><button class="btn primary" data-telegram="${l.id}">📨 Send to Telegram</button><button class="btn" data-pitch="${l.id}">✍️ Generate pitch</button><select class="fieldselect btn" data-status="${l.id}">${STAGES.map(s=>`<option ${s===l.status?'selected':''}>${s}</option>`).join('')}</select></div><div class="pitch block" id="pitch-${l.id}" hidden><h3>Recommended pitch</h3><p></p></div></div></article>`}
function bindLeads(root=document){root.querySelectorAll('[data-open]').forEach(x=>x.onclick=()=>{const d=$('#detail-'+x.dataset.open);const open=d.hidden;d.hidden=!open;x.closest('.lead').classList.toggle('open',open)});root.querySelectorAll('[data-telegram]').forEach(b=>b.onclick=async e=>{e.stopPropagation();b.disabled=true;try{await api('/dashboard/api/leads/'+b.dataset.telegram+'/telegram',{method:'POST'});toast('✅ Lead sent to Telegram')}catch(x){toast('⚠️ '+x.message)}finally{b.disabled=false}});root.querySelectorAll('[data-pitch]').forEach(b=>b.onclick=async e=>{e.stopPropagation();const box=$('#pitch-'+b.dataset.pitch);try{const j=await api('/dashboard/api/leads/'+b.dataset.pitch+'/message',{method:'POST'});box.querySelector('p').textContent=j.message||'No message returned';box.hidden=false}catch(x){toast('⚠️ '+x.message)}});root.querySelectorAll('[data-status]').forEach(s=>s.onchange=async()=>{try{await api('/dashboard/api/leads/'+s.dataset.status+'/status',{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({status:s.value})});const l=state.leads.find(x=>String(x.id)===String(s.dataset.status));if(l)l.status=s.value;renderMetrics();toast('✅ Status updated')}catch(x){toast('⚠️ '+x.message)}})}
function renderLeads(){const list=$('#lead-list');list.innerHTML=state.leads.length?state.leads.map(leadCard).join(''):'<div class="empty">📭 No leads yet. Use Find to discover your first businesses.</div>';renderMetrics();bindLeads(list)}
async function loadLeads(){try{const j=await api('/dashboard/api/leads?limit=100');state.leads=j.leads||[];renderLeads()}catch(e){$('#lead-list').innerHTML='<div class="empty">⚠️ '+esc(e.message)+'</div>'}}
async function loadSearches(){try{const j=await api('/dashboard/api/searches?limit=30');const a=j.searches||[];$('#searches').innerHTML=a.length?a.map(s=>`<div class="searchrow" data-search="${s.id}"><div><b>${esc(s.industry||'Business')} · ${esc(s.city||'')}</b><small>${esc(s.status||'')} · ${esc(s.created_at||'')}</small></div><div class="searchcount">${esc(s.result_count??s.succeeded??0)}<small>results</small></div></div>`).join(''):'<div class="empty">🗂️ No saved searches yet. Use Find to create one.</div>';document.querySelectorAll('[data-search]').forEach(x=>x.onclick=async()=>{try{const j=await api('/dashboard/api/searches/'+x.dataset.search+'/leads?limit=100');state.leads=j.leads||[];renderLeads();go('leads');toast('📂 Opened saved search')}catch(e){toast('⚠️ '+e.message)}})}catch(e){$('#searches').innerHTML='<div class="empty">⚠️ '+esc(e.message)+'</div>'}}
function fillFind(){const t=$('#find-type'),c=$('#find-city');t.innerHTML=TYPES.map(x=>`<option value="${esc(x[1])}">${esc(x[0])}</option>`).join('');c.innerHTML=CITIES.map(x=>`<option>${esc(x)}</option>`).join('');c.value='Jabalpur'}
async function discover(){const b=$('#find-btn'),s=$('#find-status');b.disabled=true;s.innerHTML='<div class="empty">🔄 Starting discovery…</div>';try{const j=await api('/dashboard/api/discover',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({business_type:$('#find-type').value,city:$('#find-city').value,limit:Number($('#find-limit').value)})});const id=j.job_id;s.innerHTML='<div class="empty">🔎 Discovery started · job #'+esc(id)+'<br>Results are being saved as they arrive.</div>';let tries=0;const poll=async()=>{if(tries++>120)return;try{const q=await api('/dashboard/api/jobs/'+id),job=q.job||{};const done=job.status==='DONE'||job.status==='FAILED';s.innerHTML='<div class="empty">'+(done?(job.status==='DONE'?'✅ Discovery complete · '+esc(job.succeeded||0)+' leads saved.':'⚠️ Discovery failed · '+esc(job.error||'Unknown error')):'🔎 Discovery running · '+esc(job.succeeded||0)+' saved so far…')+'</div>';if(done){await loadLeads();await loadSearches();return}setTimeout(poll,1500)}catch(e){s.innerHTML='<div class="empty">⚠️ '+esc(e.message)+'</div>'}};poll()}catch(e){s.innerHTML='<div class="empty">⚠️ '+esc(e.message)+'</div>'}finally{b.disabled=false}}
function rankList(items){return (items||[]).map(x=>`<div class="rank"><span>${esc(x.name)}</span><b>${esc(x.count)}</b></div>`).join('')||'<div class="empty">No data yet.</div>'}
async function loadAnalytics(){try{const j=await api('/dashboard/api/analytics');$('#a-total').innerHTML=`<div class="rank"><span>Total leads</span><b>${esc(j.totals.leads)}</b></div><div class="rank"><span>Qualified</span><b>${esc(j.totals.qualified)}</b></div><div class="rank"><span>Contacted</span><b>${esc(j.totals.contacted)}</b></div><div class="rank"><span>Won</span><b>${esc(j.totals.won)}</b></div><div class="rank"><span>Qualified rate</span><b>${esc(j.conversion.qualified_rate)}%</b></div><div class="rank"><span>Contact rate</span><b>${esc(j.conversion.contact_rate)}%</b></div><div class="rank"><span>Win rate</span><b>${esc(j.conversion.win_rate)}%</b></div>`;$('#a-cities').innerHTML=rankList(j.cities);$('#a-industries').innerHTML=rankList(j.industries);$('#a-services').innerHTML=rankList(j.services)}catch(e){toast('⚠️ '+e.message)}}
async function loadOutreach(){try{const j=await api('/dashboard/api/outreach?limit=30');const a=j.leads||[];$('#outreach-list').innerHTML=a.length?a.map(leadCard).join(''):'<div class="empty">🎉 No untouched qualified leads right now.</div>';bindLeads($('#outreach-list'))}catch(e){$('#outreach-list').innerHTML='<div class="empty">⚠️ '+esc(e.message)+'</div>'}}
function theme(){const x=localStorage.lh_theme||'light';document.body.classList.toggle('dark',x==='dark'||x==='darkneo');document.body.classList.toggle('neo',x==='neo'||x==='darkneo');document.querySelectorAll('.theme').forEach(t=>t.classList.toggle('active',t.dataset.theme===x));const meta=document.querySelector('meta[name=theme-color]');if(meta)meta.content=(x==='dark'||x==='darkneo')?'#0b1017':'#f6f7fb'}
function boot(){state.page=pageFromHash();nav();fillFind();theme();document.querySelectorAll('[data-go]').forEach(b=>b.onclick=()=>go(b.dataset.go));document.querySelectorAll('.theme').forEach(t=>t.onclick=()=>{localStorage.lh_theme=t.dataset.theme;theme()});$('#find-btn').onclick=discover;window.addEventListener('hashchange',()=>go(pageFromHash()));loadLeads();loadSearches()}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot);else boot();
})();
</script></body></html>'''

PAGE = (PAGE.replace("__TYPES__", json.dumps(BUSINESS_TYPES, ensure_ascii=False))
           .replace("__CITIES__", json.dumps(CITIES, ensure_ascii=False))
           .replace("__STAGES__", json.dumps(STAGES, ensure_ascii=False))
           .replace("__VERSION__", APP_VERSION))
