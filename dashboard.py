import os
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse
from database import Database

app = FastAPI(title="LeadHunter Dashboard")

def _authorized(token: str | None) -> bool:
    expected = os.getenv("DASHBOARD_TOKEN")
    return bool(expected and token == expected)


def create_app(db: Database | None = None):
    database = db or Database()

    @app.get("/health")
    async def health():
        return {"ok": True}

    @app.get("/", response_class=HTMLResponse)
    async def home(x_dashboard_token: str | None = Header(default=None)):
        if not _authorized(x_dashboard_token):
            raise HTTPException(status_code=401, detail="Dashboard authentication required")
        stats = await database.today_stats()
        history = await database.history(days=14)
        rows = "".join(
            f"<tr><td>{r.get('date','')}</td><td>{r.get('leads_found',0)}</td><td>{r.get('contacted',0)}</td><td>{r.get('replies',0)}</td><td>{r.get('meetings',0)}</td><td>{r.get('won',0)}</td></tr>"
            for r in history
        )
        return HTMLResponse(f"""
<!doctype html>
<html><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>LeadHunter</title>
<style>
body{{font-family:Inter,Arial,sans-serif;max-width:1100px;margin:28px auto;padding:0 16px;background:#f5f7fb;color:#172033}}
h1{{margin-bottom:4px}} .muted{{color:#687386}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:20px 0}}
.card{{background:white;border-radius:14px;padding:18px;box-shadow:0 2px 12px #00000010}}
.num{{font-size:30px;font-weight:700;margin-top:6px}}
table{{width:100%;background:white;border-collapse:collapse;border-radius:14px;overflow:hidden}}
th,td{{padding:12px;border-bottom:1px solid #eef0f4;text-align:left}}
th{{font-size:13px;color:#687386}}
</style></head><body>
<h1>🚀 LeadHunter</h1><div class="muted">Private daily sales history</div>
<div class="grid">
<div class="card">🔎 New leads<div class="num">{stats['leads_found']}</div></div>
<div class="card">🎯 Qualified<div class="num">{stats['qualified']}</div></div>
<div class="card">🔥 Hot<div class="num">{stats['hot_leads']}</div></div>
<div class="card">📞 Calls<div class="num">{stats['calls']}</div></div>
<div class="card">💬 Contacted<div class="num">{stats['contacted']}</div></div>
<div class="card">💬 Replies<div class="num">{stats['replies']}</div></div>
<div class="card">📅 Meetings<div class="num">{stats['meetings']}</div></div>
<div class="card">💰 Won<div class="num">{stats['won']}</div></div>
</div>
<h2>📈 Recent history</h2>
<table><thead><tr><th>Date</th><th>Leads</th><th>Contacted</th><th>Replies</th><th>Meetings</th><th>Won</th></tr></thead><tbody>{rows or '<tr><td colspan="6">No history yet.</td></tr>'}</tbody></table>
<p class="muted">Telegram is the operating interface. The dashboard is intentionally minimal.</p>
</body></html>
""")

    return app

# Render can import this as `dashboard:app`.
