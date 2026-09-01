import base64
import os
import secrets

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import HTMLResponse

from database import Database

router = APIRouter()


def authorized(auth: str | None) -> bool:
    user, password = os.getenv("DASHBOARD_USER"), os.getenv("DASHBOARD_PASSWORD")
    if not user or not password or not auth or not auth.startswith("Basic "): return False
    try:
        decoded = base64.b64decode(auth[6:]).decode("utf-8"); supplied_user, supplied_password = decoded.split(":", 1)
        return secrets.compare_digest(supplied_user, user) and secrets.compare_digest(supplied_password, password)
    except Exception: return False


@router.get("/dashboard", response_class=HTMLResponse)
async def home(authorization: str | None = Header(default=None)):
    if not authorized(authorization):
        raise HTTPException(status_code=401, detail="Dashboard authentication required", headers={"WWW-Authenticate": "Basic"})
    db = Database(); stats = await db.today_stats(); history = await db.history(14)
    rows = "".join(f"<tr><td>{r.get('date','')}</td><td>{r.get('leads_found',0)}</td><td>{r.get('contacted',0)}</td><td>{r.get('replies',0)}</td><td>{r.get('meetings',0)}</td><td>{r.get('won',0)}</td></tr>" for r in history)
    cards = [("🔎", "New leads", stats["leads_found"]), ("🎯", "Qualified", stats["qualified"]), ("🔥", "Hot", stats["hot_leads"]), ("📞", "Calls", stats["calls"]), ("💬", "Contacted", stats["contacted"]), ("💬", "Replies", stats["replies"]), ("📅", "Meetings", stats["meetings"]), ("📄", "Proposals", stats["proposals"]), ("💰", "Won", stats["won"]), ("❌", "Lost", stats["lost"])]
    cards_html = "".join(f'<div class="card">{i} {label}<div class="num">{value}</div></div>' for i, label, value in cards)
    return HTMLResponse(f'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>LeadHunter</title><style>body{{font-family:Arial,sans-serif;max-width:1100px;margin:28px auto;padding:0 16px;background:#f5f7fb;color:#172033}}.muted{{color:#687386}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:20px 0}}.card{{background:white;border-radius:14px;padding:18px;box-shadow:0 2px 12px rgba(0,0,0,.06)}}.num{{font-size:30px;font-weight:700;margin-top:6px}}table{{width:100%;background:white;border-collapse:collapse}}th,td{{padding:12px;border-bottom:1px solid #eef0f4;text-align:left}}</style></head><body><h1>🚀 LeadHunter</h1><div class="muted">Private daily sales history</div><div class="grid">{cards_html}</div><h2>📈 Recent history</h2><table><thead><tr><th>Date</th><th>Leads</th><th>Contacted</th><th>Replies</th><th>Meetings</th><th>Won</th></tr></thead><tbody>{rows or '<tr><td colspan="6">No history yet.</td></tr>'}</tbody></table><p class="muted">Telegram is the primary operating interface. This dashboard is intentionally minimal.</p></body></html>''')
