"""LeadHunter Mobile Dashboard.

A mobile-first, app-like interface over the exact same /dashboard/api
contract used by the desktop dashboard. No business logic lives here:
this module only renders the mobile UI shell and consumes the public API.
"""

MOBILE_HTML = r'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#0b1220">
<title>LeadHunter — Mobile</title>
<style>
:root{
  --bg:#f2f5f9;--surface:#ffffff;--surface-2:#f8fafc;--ink:#101828;--muted:#667085;
  --line:#e4e7ec;--accent:#16a34a;--accent-2:#15803d;--accent-soft:#ecfdf3;
  --blue:#2563eb;--blue-soft:#eff6ff;--amber:#d97706;--amber-soft:#fffbeb;
  --red:#dc2626;--red-soft:#fef2f2;--shadow:0 8px 24px rgba(16,24,40,.07);
  --radius:16px;--radius-sm:12px;--tabbar-h:calc(64px + env(safe-area-inset-bottom))
}
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
html{scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.5 Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;min-height:100vh;padding-bottom:var(--tabbar-h);overscroll-behavior-y:contain}
button,input,select{font:inherit;color:inherit}
button{cursor:pointer;border:0;background:none}
a{color:inherit;text-decoration:none}

/* ---------- App bar ---------- */
.appbar{position:sticky;top:0;z-index:40;display:flex;align-items:center;justify-content:space-between;gap:10px;padding:calc(10px + env(safe-area-inset-top)) 14px 10px;background:rgba(255,255,255,.9);backdrop-filter:blur(14px);border-bottom:1px solid var(--line)}
.brand{display:flex;align-items:center;gap:10px;min-width:0}
.brand-mark{width:36px;height:36px;border-radius:11px;background:linear-gradient(135deg,#22c55e,#15803d);display:grid;place-items:center;color:#fff;font-weight:900;font-size:13px;box-shadow:0 6px 16px rgba(34,197,94,.25)}
.brand-text{font-weight:850;letter-spacing:.08em;font-size:13px;line-height:1.15}
.brand-text b{display:block;font-size:9px;color:var(--muted);letter-spacing:.2em;font-weight:800}
.app-actions{display:flex;align-items:center;gap:8px}
.dot{width:8px;height:8px;border-radius:50%;background:#98a2b3;box-shadow:0 0 0 4px rgba(152,162,179,.15)}
.dot.ok{background:#22c55e;box-shadow:0 0 0 4px rgba(34,197,94,.15)}
.dot.bad{background:#ef4444;box-shadow:0 0 0 4px rgba(239,68,68,.15)}
.icon-btn{width:36px;height:36px;border:1px solid var(--line);background:var(--surface);border-radius:10px;display:grid;place-items:center;font-size:15px}
.icon-btn:active{transform:scale(.94)}

/* ---------- Tabs / content ---------- */
.tab{display:none;padding:16px 14px 22px;animation:tabIn .2s ease}
.tab.active{display:block}
@keyframes tabIn{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}
.eyebrow{font-size:10px;letter-spacing:.16em;text-transform:uppercase;font-weight:850;color:var(--accent)}
h1{font-size:24px;line-height:1.2;margin:5px 0 4px;letter-spacing:-.02em}
h2{font-size:15px;margin:0}
.sub{margin:0;color:var(--muted);font-size:12.5px}
.section-head{display:flex;align-items:center;justify-content:space-between;gap:10px;margin:20px 0 10px}
.section-head h2{font-weight:800}
.link-btn{font-size:12px;font-weight:750;color:var(--accent)}
.card{background:var(--surface);border:1px solid var(--line);border-radius:var(--radius);box-shadow:var(--shadow);padding:15px}
.muted{color:var(--muted)}
.tiny{font-size:11px}

/* ---------- Metric chips ---------- */
.chips{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.chip-tile{background:var(--surface);border:1px solid var(--line);border-radius:var(--radius);box-shadow:var(--shadow);padding:13px 14px;position:relative;overflow:hidden;text-align:left}
.chip-tile:after{content:"";position:absolute;right:-20px;top:-20px;width:64px;height:64px;border-radius:50%;background:var(--accent-soft)}
.chip-tile .n{font-size:24px;font-weight:850;letter-spacing:-.03em;position:relative}
.chip-tile .l{font-size:10px;font-weight:800;letter-spacing:.08em;color:var(--muted);position:relative}
.chip-tile .d{font-size:10px;color:var(--muted);margin-top:1px;position:relative}
.chip-tile.gold:after{background:var(--amber-soft)}

/* ---------- Quick actions ---------- */
.quick{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:14px}
.qa{display:flex;align-items:center;justify-content:center;gap:8px;padding:13px 10px;border-radius:13px;font-weight:800;font-size:13px;border:1px solid var(--line);background:var(--surface);box-shadow:var(--shadow)}
.qa.primary{background:var(--accent);border-color:var(--accent);color:#fff;box-shadow:0 10px 22px rgba(22,163,74,.28)}
.qa:active{transform:scale(.97)}

/* ---------- Lists / rows ---------- */
.list{display:grid;gap:9px}
.row{display:flex;align-items:center;justify-content:space-between;gap:10px;border:1px solid var(--line);background:var(--surface);border-radius:13px;padding:12px 13px;text-align:left;width:100%}
.row:active{background:var(--surface-2)}
.row-title{font-weight:800;font-size:13.5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.row-sub{font-size:11px;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-top:2px}
.row-main{min-width:0;flex:1}
.chev{color:#98a2b3;font-size:15px}
.badge{display:inline-flex;align-items:center;gap:4px;border-radius:999px;padding:3px 8px;font-size:9.5px;font-weight:800;white-space:nowrap}
.badge.green{color:#15803d;background:var(--accent-soft)}
.badge.blue{color:#1d4ed8;background:var(--blue-soft)}
.badge.amber{color:#b45309;background:var(--amber-soft)}
.badge.red{color:#b91c1c;background:var(--red-soft)}
.badge.gray{color:#667085;background:#f2f4f7}
.meta-row{display:flex;gap:6px;flex-wrap:wrap;margin-top:7px}

/* ---------- Datasets chips (Leads) ---------- */
.ds-scroll{display:flex;gap:8px;overflow-x:auto;padding:2px 2px 8px;scrollbar-width:none;margin:0 -2px}
.ds-scroll::-webkit-scrollbar{display:none}
.ds-chip{flex:0 0 auto;display:flex;flex-direction:column;align-items:flex-start;gap:2px;border:1px solid var(--line);background:var(--surface);border-radius:12px;padding:8px 12px;max-width:230px}
.ds-chip b{font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:200px}
.ds-chip span{font-size:10px;color:var(--muted);white-space:nowrap}
.ds-chip.selected{border-color:#86efac;background:var(--accent-soft);box-shadow:0 0 0 2px rgba(34,197,94,.12)}

/* ---------- Lead search + filters ---------- */
.lead-tools{display:grid;gap:9px;margin-bottom:11px}
.search-box{position:relative}
.search-box input{width:100%;height:42px;border:1px solid #d0d5dd;border-radius:12px;background:var(--surface);padding:0 12px 0 38px;outline:none}
.search-box input:focus{border-color:#4ade80;box-shadow:0 0 0 3px rgba(34,197,94,.12)}
.search-box:before{content:"⌕";position:absolute;left:13px;top:50%;transform:translateY(-50%);color:var(--muted);font-size:15px}
.pills{display:flex;gap:7px}
.pill{flex:1;text-align:center;padding:8px 6px;border-radius:999px;border:1px solid var(--line);background:var(--surface);font-size:11.5px;font-weight:750;color:var(--muted)}
.pill.active{background:#111827;border-color:#111827;color:#fff}

/* ---------- Lead sheet (bottom sheet) ---------- */
.scrim{position:fixed;inset:0;background:rgba(15,23,42,.45);z-index:60;opacity:0;pointer-events:none;transition:.2s}
.scrim.show{opacity:1;pointer-events:auto}
.sheet{position:fixed;left:0;right:0;bottom:0;z-index:70;background:var(--surface);border-radius:22px 22px 0 0;box-shadow:0 -18px 50px rgba(16,24,40,.22);transform:translateY(105%);transition:transform .26s cubic-bezier(.2,.8,.25,1);max-height:86vh;display:flex;flex-direction:column}
.sheet.show{transform:none}
.sheet-grip{width:44px;height:5px;border-radius:99px;background:#d0d5dd;margin:9px auto 2px;flex:0 0 auto}
.sheet-head{display:flex;align-items:flex-start;justify-content:space-between;gap:10px;padding:6px 18px 12px;border-bottom:1px solid var(--line);flex:0 0 auto}
.sheet-body{overflow-y:auto;padding:14px 18px calc(20px + env(safe-area-inset-bottom))}
.sheet-title{font-size:16px;font-weight:850;letter-spacing:-.01em}
.sheet-sub{font-size:11.5px;color:var(--muted);margin-top:2px}
.kv-grid{display:grid;gap:8px}
.kv{border:1px solid var(--line);border-radius:11px;padding:9px 11px;background:var(--surface-2);display:flex;justify-content:space-between;align-items:center;gap:10px}
.kv .k{font-size:10px;font-weight:800;color:var(--muted);letter-spacing:.06em}
.kv .v{font-weight:700;font-size:12.5px;word-break:break-word;text-align:right}
.kv a.link{color:var(--blue);text-decoration:underline}
.act-row{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:13px}
.act-btn{display:flex;flex-direction:column;align-items:center;gap:4px;padding:11px 4px;border-radius:12px;border:1px solid var(--line);background:var(--surface);font-size:10.5px;font-weight:800;color:var(--ink)}
.act-btn em{font-style:normal;font-size:16px}
.act-btn.primary{background:var(--accent);border-color:var(--accent);color:#fff}
.act-btn:active{transform:scale(.96)}
.intel{margin-top:12px;border:1px solid var(--line);border-radius:13px;background:var(--surface-2);padding:12px}
.intel-head{display:flex;justify-content:space-between;align-items:center;gap:8px;margin-bottom:8px}
.intel-head b{font-size:12.5px}
.state-line{display:flex;justify-content:space-between;align-items:center;gap:8px;padding:6px 0;border-top:1px dashed var(--line);font-size:11.5px}
.state-line:first-of-type{border-top:0}
.pitch-out{margin-top:10px;background:var(--surface);border:1px dashed #c7cdd6;border-radius:11px;padding:11px;font-size:12.5px;white-space:pre-wrap;display:none}
.pitch-out.show{display:block}

/* ---------- Forms (Find) ---------- */
.field{margin-bottom:13px}
.field label{display:block;font-size:10.5px;font-weight:800;color:var(--muted);letter-spacing:.07em;margin-bottom:6px}
.select{width:100%;height:46px;border:1px solid #d0d5dd;border-radius:12px;background:var(--surface);padding:0 12px;outline:none;appearance:none;background-image:linear-gradient(45deg,transparent 49%,#98a2b3 50%),linear-gradient(-45deg,transparent 49%,#98a2b3 50%);background-position:calc(100% - 19px) 55%,calc(100% - 14px) 55%;background-size:5px 5px;background-repeat:no-repeat}
.select:focus{border-color:#4ade80;box-shadow:0 0 0 3px rgba(34,197,94,.12)}
.big-btn{width:100%;padding:14px;border-radius:13px;background:var(--accent);color:#fff;font-weight:850;font-size:14.5px;box-shadow:0 10px 22px rgba(22,163,74,.3);display:flex;align-items:center;justify-content:center;gap:8px}
.big-btn:disabled{opacity:.65;box-shadow:none}
.job{margin-top:14px;border:1px solid var(--line);border-radius:13px;padding:13px;background:var(--surface-2)}
.progress{height:8px;background:#e8edf2;border-radius:99px;overflow:hidden;margin-top:9px}
.progress i{display:block;width:0;height:100%;background:linear-gradient(90deg,#22c55e,#16a34a);transition:width .35s}

/* ---------- Stats ---------- */
.bar-row{display:grid;grid-template-columns:92px minmax(0,1fr) 30px;gap:8px;align-items:center;font-size:11px;margin-bottom:8px}
.bar-row span{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.bar-track{height:9px;border-radius:99px;background:#edf0f4;overflow:hidden}
.bar-track i{display:block;height:100%;background:var(--blue);border-radius:99px}
.bar-track i.g{background:var(--accent)}

/* ---------- States ---------- */
.empty,.loading,.error{padding:30px 14px;text-align:center;border:1.5px dashed var(--line);border-radius:14px;color:var(--muted);background:var(--surface-2);font-size:12.5px}
.empty b{display:block;font-size:13px;margin-bottom:3px;color:var(--ink)}
.empty-icon{font-size:24px;margin-bottom:6px}
.error{color:var(--red);background:var(--red-soft);border-color:#fecaca}
.skeleton{height:58px;border-radius:13px;border:1px solid var(--line);background:linear-gradient(90deg,#eef1f5,#f7f8fa,#eef1f5);background-size:200% 100%;animation:shine 1.2s infinite;margin-bottom:9px}
@keyframes shine{to{background-position:-200% 0}}

/* ---------- Tab bar ---------- */
.tabbar{position:fixed;left:0;right:0;bottom:0;z-index:50;display:grid;grid-template-columns:repeat(5,1fr);align-items:end;background:rgba(255,255,255,.94);backdrop-filter:blur(14px);border-top:1px solid var(--line);padding:6px 6px env(safe-area-inset-bottom);height:var(--tabbar-h)}
.tab-btn{display:flex;flex-direction:column;align-items:center;gap:2px;padding:7px 0 3px;color:#8b98a9;font-size:9.5px;font-weight:800;letter-spacing:.04em;border-radius:11px}
.tab-btn em{font-style:normal;font-size:17px;line-height:1}
.tab-btn.active{color:var(--accent-2)}
.tab-btn.active em{transform:translateY(-1px)}
.fab-wrap{display:flex;justify-content:center}
.fab{width:52px;height:52px;margin-top:-22px;border-radius:50%;background:linear-gradient(135deg,#22c55e,#15803d);color:#fff;font-size:22px;display:grid;place-items:center;box-shadow:0 12px 26px rgba(22,163,74,.42);border:3px solid var(--bg)}
.fab:active{transform:scale(.93)}

/* ---------- Toast ---------- */
.toast{position:fixed;left:50%;bottom:calc(var(--tabbar-h) + 14px);transform:translate(-50%,10px);z-index:90;background:#111827;color:#fff;padding:10px 15px;border-radius:11px;box-shadow:0 12px 35px rgba(0,0,0,.25);opacity:0;pointer-events:none;transition:.2s;font-size:12px;max-width:86vw;text-align:center}
.toast.show{opacity:1;transform:translate(-50%,0)}

/* ---------- Themes: dark + neo (same 4-theme system as desktop) ---------- */
body.dark{--bg:#0b1118;--surface:#121b26;--surface-2:#0f1722;--ink:#edf2f7;--muted:#9aa7b6;--line:#263342;--shadow:0 10px 26px rgba(0,0,0,.28);--accent-soft:#0f2b1c;--blue-soft:#0e2040;--amber-soft:#30230d;--red-soft:#351719}
body.dark .appbar{background:rgba(18,27,38,.92)}
body.dark .search-box input,body.dark .select{background-color:var(--surface);border-color:#344254}
body.dark .pill.active{background:#e7ecf3;border-color:#e7ecf3;color:#101828}
body.dark .bar-track,body.dark .progress{background:#263342}
body.dark .tabbar{background:rgba(18,27,38,.94)}
body.dark .badge.gray{background:#1d2939;color:#9aa7b6}
body.dark .kv,body.dark .intel,body.dark .job,body.dark .sheet-body .kv{background:var(--surface-2)}
body.neo{--radius:7px;--radius-sm:6px;--shadow:4px 4px 0 rgba(16,24,40,.18)}
body.neo .card,body.neo .chip-tile,body.neo .row,body.neo .ds-chip,body.neo .qa,body.neo .kv,body.neo .intel,body.neo .job,body.neo .act-btn{border:2px solid var(--ink);border-radius:6px;box-shadow:none}
body.neo .big-btn,body.neo .qa.primary{border:2px solid var(--ink)}
body.neo .badge{border:1.5px solid currentColor;border-radius:2px}
body.neo.dark{--shadow:5px 5px 0 #000}
body.neo.dark .card,body.neo.dark .chip-tile,body.neo.dark .row,body.neo.dark .ds-chip,body.neo.dark .qa,body.neo.dark .kv,body.neo.dark .intel,body.neo.dark .job,body.neo.dark .act-btn{border-color:#4b5b70}
</style>
</head>
<body>

<header class="appbar">
  <div class="brand">
    <div class="brand-mark">LH</div>
    <div class="brand-text">LEADHUNTER<b>MOBILE</b></div>
  </div>
  <div class="app-actions">
    <span class="dot" id="netDot" title="System status"></span>
    <button class="icon-btn" onclick="cycleTheme()" title="Switch theme">◐</button>
    <a class="icon-btn" href="/dashboard" title="Open full dashboard">⤢</a>
  </div>
</header>

<main id="view">

<!-- ================= HOME ================= -->
<section class="tab active" id="tab-home">
  <div class="eyebrow">COMMAND CENTER</div>
  <h1>Good leads start here.</h1>
  <p class="sub">Discover local businesses, qualify opportunities and act — all from your pocket.</p>

  <div class="chips" style="margin-top:16px">
    <button class="chip-tile" onclick="go('leads')"><div class="l">DATASETS</div><div class="n" id="hDatasets">—</div><div class="d">Completed searches</div></button>
    <button class="chip-tile gold" onclick="go('leads')"><div class="l">LEADS</div><div class="n" id="hLeads">—</div><div class="d">Businesses found</div></button>
    <button class="chip-tile" onclick="go('stats')"><div class="l">RESEARCHED</div><div class="n" id="hResearch">—</div><div class="d">Intelligence ready</div></button>
    <button class="chip-tile gold" onclick="go('stats')"><div class="l">READY</div><div class="n" id="hReady">—</div><div class="d">Qualified</div></button>
  </div>

  <div class="quick">
    <button class="qa primary" onclick="go('find')">⌕ Find leads</button>
    <button class="qa" onclick="go('act')">➤ My pipeline</button>
  </div>

  <div class="section-head"><h2>Recent datasets</h2><button class="link-btn" onclick="go('leads')">View all</button></div>
  <div class="list" id="recentList"><div class="skeleton"></div><div class="skeleton"></div><div class="skeleton"></div></div>

  <div class="section-head"><h2>System</h2><button class="link-btn" onclick="loadHome()">↻ Refresh</button></div>
  <div class="card" id="healthMini" style="padding:12px"><div class="tiny muted">Checking services…</div></div>
</section>

<!-- ================= LEADS ================= -->
<section class="tab" id="tab-leads">
  <div class="eyebrow">LEAD DATABASE</div>
  <h1>Pick a dataset.</h1>
  <p class="sub">Swipe the datasets, then tap any lead for the full record and actions.</p>

  <div class="ds-scroll" id="dsScroll" style="margin-top:14px"><div class="skeleton" style="width:150px"></div><div class="skeleton" style="width:150px"></div></div>

  <div class="lead-tools">
    <div class="search-box"><input id="leadSearch" type="search" placeholder="Search leads…" oninput="renderLeads()"></div>
    <div class="pills">
      <button class="pill active" data-f="all" onclick="setFilter('all')">All</button>
      <button class="pill" data-f="hot" onclick="setFilter('hot')">Hot</button>
      <button class="pill" data-f="researched" onclick="setFilter('researched')">Researched</button>
    </div>
  </div>

  <div class="tiny muted" id="leadMeta" style="margin:0 2px 9px">Select a dataset to load its leads.</div>
  <div class="list" id="leadList"></div>
</section>

<!-- ================= FIND ================= -->
<section class="tab" id="tab-find">
  <div class="eyebrow">DISCOVERY</div>
  <h1>Find new leads.</h1>
  <p class="sub">Completed searches are reused automatically unless you refresh.</p>

  <div class="card" style="margin-top:14px">
    <div class="field"><label for="mBusinessType">BUSINESS TYPE</label><select class="select" id="mBusinessType"><option value="">Choose business type</option></select></div>
    <div class="field"><label for="mCity">CITY</label><select class="select" id="mCity"><option value="">Choose city</option></select></div>
    <div class="field"><label for="mCount">LEADS</label><select class="select" id="mCount"><option value="10">10</option><option value="20" selected>20</option><option value="30">30</option><option value="50">50</option></select></div>
    <button class="big-btn" id="mFindBtn" onclick="startDiscovery()">⌕ Find Leads</button>
    <div class="tiny muted" style="margin-top:10px">Discovery runs server-side; you can keep using the app and return here for progress.</div>
  </div>

  <div class="job" id="mJobBox" style="display:none">
    <div style="display:flex;justify-content:space-between;align-items:center;gap:10px"><span class="tiny" id="mJobText" style="font-weight:750">Starting discovery…</span><b id="mJobPct">0%</b></div>
    <div class="progress"><i id="mJobBar"></i></div>
  </div>
</section>

<!-- ================= STATS ================= -->
<section class="tab" id="tab-stats">
  <div class="eyebrow">INTELLIGENCE</div>
  <h1>Where the opportunity is.</h1>
  <p class="sub">Lead volume, qualification and markets at a glance.</p>

  <div class="chips" style="margin-top:16px">
    <div class="chip-tile"><div class="l">TOTAL LEADS</div><div class="n" id="sLeads">—</div></div>
    <div class="chip-tile gold"><div class="l">HOT</div><div class="n" id="sHot">—</div></div>
    <div class="chip-tile"><div class="l">QUALIFIED</div><div class="n" id="sQualified">—</div></div>
    <div class="chip-tile gold"><div class="l">CONTACTED</div><div class="n" id="sContacted">—</div></div>
  </div>

  <div class="section-head"><h2>Leads by city</h2><button class="link-btn" onclick="loadStats()">↻</button></div>
  <div class="card" id="cityChart"></div>

  <div class="section-head"><h2>Services to sell</h2></div>
  <div class="card" id="serviceChart"></div>
</section>

<!-- ================= ACT ================= -->
<section class="tab" id="tab-act">
  <div class="eyebrow">ACT</div>
  <h1>Turn leads into conversations.</h1>
  <p class="sub">Saved opportunities and follow-ups, with the lead one tap away.</p>

  <div class="meta-row" id="actCounts" style="margin-top:14px"></div>

  <div class="section-head"><h2>Pipeline</h2><button class="link-btn" onclick="loadAct()">↻ Refresh</button></div>
  <div class="list" id="actList"></div>

  <div class="section-head" id="fuHead" style="display:none"><h2>Due follow-ups</h2></div>
  <div class="list" id="followups"></div>
</section>

</main>

<!-- ================= LEAD BOTTOM SHEET ================= -->
<div class="scrim" id="scrim" onclick="closeSheet()"></div>
<div class="sheet" id="sheet" role="dialog" aria-modal="true">
  <div class="sheet-grip"></div>
  <div class="sheet-head">
    <div style="min-width:0">
      <div class="sheet-title" id="sheetTitle">Lead</div>
      <div class="sheet-sub" id="sheetSub"></div>
    </div>
    <button class="icon-btn" onclick="closeSheet()">✕</button>
  </div>
  <div class="sheet-body" id="sheetBody"></div>
</div>

<nav class="tabbar">
  <button class="tab-btn active" data-tab="home" onclick="go('home')"><em>⌂</em>Home</button>
  <button class="tab-btn" data-tab="leads" onclick="go('leads')"><em>▤</em>Leads</button>
  <div class="fab-wrap"><button class="fab" onclick="go('find')" aria-label="Find leads">⌕</button></div>
  <button class="tab-btn" data-tab="stats" onclick="go('stats')"><em>◫</em>Stats</button>
  <button class="tab-btn" data-tab="act" onclick="go('act')"><em>➤</em>Act</button>
</nav>

<div class="toast" id="toast"></div>

<script>
const $=id=>document.getElementById(id);
let activeTab='home',datasets=[],selectedDataset=null,allLeads=[],leadFilter='all',jobTimer=null;
const stateClass=s=>({AVAILABLE:'green',NOT_FOUND:'red',NOT_CONFIGURED:'gray',FAILED:'amber'})[String(s||'').toUpperCase()]||'gray';
const esc=v=>String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
const api=async(path,opts={})=>{const r=await fetch('/dashboard/api'+path,opts);let x={};try{x=await r.json()}catch(e){}if(!r.ok)throw new Error(x.detail||x.message||('Request failed ('+r.status+')'));return x};
function toast(msg){const t=$('toast');t.textContent=msg;t.classList.add('show');clearTimeout(toast.t);toast.t=setTimeout(()=>t.classList.remove('show'),2400)}
function loading(id,text){if($(id))$(id).innerHTML='<div class="loading">'+esc(text||'Loading…')+'</div>'}
function emptyBox(id,icon,title,text){if($(id))$(id).innerHTML='<div class="empty"><div class="empty-icon">'+icon+'</div><b>'+esc(title)+'</b>'+esc(text)+'</div>'}
function errBox(id,e){if($(id))$(id).innerHTML='<div class="error">⚠ '+esc(e.message||e)+'</div>'}
function nameOf(x){return x.name||x.business_name||x.title||'Unnamed business'}
function cityOf(x){return x.city||x.location||x.town||'Unknown'}
function fmtDate(v){if(!v)return '—';const d=new Date(v);return isNaN(d)?String(v):d.toLocaleDateString([],{day:'2-digit',month:'short'})+' · '+d.toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'})}
function statusBadge(x){const s=String(x.status||'').toUpperCase();if(['QUALIFIED','READY','HOT'].includes(s))return '<span class="badge green">'+esc(s)+'</span>';if(['RESEARCHED','DONE','AVAILABLE'].includes(s))return '<span class="badge blue">'+esc(s)+'</span>';if(['FAILED','NOT_FOUND'].includes(s))return '<span class="badge red">'+esc(s)+'</span>';return '<span class="badge gray">'+esc(s||'NEW')+'</span>'}
function setNet(ok){const d=$('netDot');d.classList.toggle('ok',!!ok);d.classList.toggle('bad',!ok)}
function digits(v){return String(v||'').replace(/\D+/g,'')}
function waLink(phone,text){const d=digits(phone);if(!d)return '';const n=d.length===10?'91'+d:d;return 'https://wa.me/'+n+(text?'?text='+encodeURIComponent(text):'')}

/* ---------- navigation ---------- */
function go(tab){
  activeTab=tab;
  document.querySelectorAll('.tab').forEach(t=>t.classList.toggle('active',t.id==='tab-'+tab));
  document.querySelectorAll('.tab-btn').forEach(b=>b.classList.toggle('active',b.dataset.tab===tab));
  window.scrollTo({top:0,behavior:'smooth'});
  if(tab==='home')loadHome();
  if(tab==='leads')loadDatasets();
  if(tab==='stats')loadStats();
  if(tab==='act')loadAct();
}

/* ---------- home ---------- */
async function loadHome(){
  try{
    const x=await api('/overview'),m=x.metrics||{};
    $('hDatasets').textContent=m.datasets??0;
    $('hLeads').textContent=m.leads??0;
    $('hResearch').textContent=m.researched??0;
    $('hReady').textContent=m.ready??0;
    const recent=x.recent||[];
    $('recentList').innerHTML=recent.length?recent.map(d=>{
      const id=d.id??d.search_id??d.dataset_id;
      return '<button class="row" onclick="openDatasetFromHome('+Number(id)+')"><div class="row-main"><div class="row-title">'+esc(d.industry||d.category||'Business search')+'</div><div class="row-sub">'+esc(d.city||'—')+' · '+esc(d.result_count??d.lead_count??0)+' leads · '+esc(fmtDate(d.created_at))+'</div></div><span class="chev">›</span></button>';
    }).join(''):emptyBox('recentList','▤','No datasets yet','Run your first discovery to fill this list.');
    setNet(true);
    loadHealthMini();
  }catch(e){errBox('recentList',e);setNet(false)}
}
async function loadHealthMini(){
  try{
    const x=await api('/health'),s=x.services||{};
    const keys=Object.keys(s);
    $('healthMini').innerHTML=keys.length?keys.map(k=>{
      const v=s[k],ok=v===true||String(v).toLowerCase()==='true';
      return '<div class="state-line"><span style="text-transform:capitalize">'+esc(k.replaceAll('_',' '))+'</span><span class="badge '+(ok?'green':'amber')+'">'+esc(String(v))+'</span></div>';
    }).join(''):'<div class="tiny muted">No service details reported.</div>';
  }catch(e){$('healthMini').innerHTML='<div class="tiny" style="color:var(--red)">Health check failed</div>';setNet(false)}
}
async function openDatasetFromHome(id){selectedDataset=Number(id);go('leads')}

/* ---------- leads ---------- */
async function loadDatasets(){
  const wrap=$('dsScroll');
  try{
    const x=await api('/datasets?limit=50');
    datasets=Array.isArray(x.items)?x.items:[];
    if(!datasets.length){
      wrap.innerHTML='<div class="tiny muted" style="padding:4px">No datasets yet — use Find to create one.</div>';
      $('leadMeta').textContent='No datasets available.';
      emptyBox('leadList','⌕','No datasets','Create a dataset from the Find tab first.');
      return;
    }
    wrap.innerHTML=datasets.map(d=>{
      const id=d.id??d.search_id??d.dataset_id;
      const st=String(d.status||'DONE').toUpperCase();
      return '<button class="ds-chip'+(Number(selectedDataset)===Number(id)?' selected':'')+'" data-id="'+Number(id)+'" onclick="selectDataset('+Number(id)+')"><b>'+esc(d.industry||d.category||'Search')+'</b><span>'+esc(d.city||'—')+' · '+esc(d.result_count??d.lead_count??0)+' leads · '+esc(st)+'</span></button>';
    }).join('');
    const preferred=Number(selectedDataset||0);
    const match=datasets.find(d=>Number(d.id??d.search_id??d.dataset_id)===preferred)||datasets[0];
    await selectDataset(Number(match.id??match.search_id??match.dataset_id));
  }catch(e){wrap.innerHTML='';errBox('leadList',e)}
}
async function selectDataset(id){
  selectedDataset=Number(id);
  document.querySelectorAll('.ds-chip').forEach(c=>c.classList.toggle('selected',Number(c.dataset.id)===selectedDataset));
  const ds=datasets.find(d=>Number(d.id??d.search_id??d.dataset_id)===selectedDataset);
  $('leadMeta').textContent='Loading '+esc(ds?(ds.industry||'dataset'):'dataset')+'…';
  loading('leadList','Loading leads…');
  try{
    const x=await api('/datasets/'+selectedDataset+'/leads?limit=100');
    allLeads=x.items||[];
    const ds2=x.dataset||ds||{};
    $('leadMeta').textContent=allLeads.length+' leads · '+esc(ds2.city||'')+' · '+esc(ds2.industry||'');
    renderLeads();
  }catch(e){$('leadMeta').textContent='';errBox('leadList',e)}
}
function setFilter(f){
  leadFilter=f;
  document.querySelectorAll('.pill').forEach(p=>p.classList.toggle('active',p.dataset.f===f));
  renderLeads();
}
function renderLeads(){
  const q=($('leadSearch').value||'').trim().toLowerCase();
  let rows=allLeads;
  if(leadFilter==='hot')rows=rows.filter(x=>['QUALIFIED','READY','HOT'].includes(String(x.status||'').toUpperCase())||Number(x.score)>=70);
  if(leadFilter==='researched')rows=rows.filter(x=>x.research||x.score!=null||['RESEARCHED','QUALIFIED'].includes(String(x.status||'').toUpperCase()));
  if(q)rows=rows.filter(x=>(nameOf(x)+' '+cityOf(x)+' '+(x.industry||'')).toLowerCase().includes(q));
  if(!rows.length){emptyBox('leadList','⌕',allLeads.length?'No matching leads':'No leads here',allLeads.length?'Try another filter or search term.':'Pick a dataset to load its leads.');return}
  $('leadList').innerHTML=rows.map(x=>{
    const id=x.id??x.lead_id;
    const score=Number(x.score);
    return '<button class="row" onclick="openLeadSheet('+Number(id)+')"><div class="row-main"><div class="row-title">'+esc(nameOf(x))+'</div><div class="row-sub">'+esc(cityOf(x))+(x.industry?' · '+esc(x.industry):'')+'</div><div class="meta-row">'+statusBadge(x)+(Number.isFinite(score)?'<span class="badge gray">Score '+esc(Math.round(score))+'</span>':'')+'</div></div><span class="chev">›</span></button>';
  }).join('');
}

/* ---------- lead bottom sheet ---------- */
function openSheet(title,sub,bodyHtml){
  $('sheetTitle').textContent=title;
  $('sheetSub').textContent=sub||'';
  $('sheetBody').innerHTML=bodyHtml;
  $('scrim').classList.add('show');
  $('sheet').classList.add('show');
}
function closeSheet(){$('scrim').classList.remove('show');$('sheet').classList.remove('show')}
async function openLeadSheet(id){
  try{
    let lead=allLeads.find(v=>Number(v.id??v.lead_id)===Number(id));
    if(!lead){const x=await api('/leads/'+Number(id));lead=x.item}
    if(!lead)throw new Error('Lead not found');
    if(!lead.research){try{const d=await api('/leads/'+Number(id));lead.research=d.item&&d.item.research}catch(e2){}}
    renderLeadSheet(lead);
  }catch(e){toast(e.message||'Could not open lead')}
}
function renderLeadSheet(x){
  const id=Number(x.id??x.lead_id);
  const phone=x.phone||x.phone_number||'';
  const email=x.email||'';
  const website=x.website||x.url||x.domain||'';
  const research=x.research||null;
  const score=Number(x.score);
  const kv=(k,v)=>'<div class="kv"><span class="k">'+k+'</span><span class="v">'+(v||'—')+'</span></div>';
  const contactActions=
    '<div class="act-row">'
    +(phone?'<a class="act-btn" href="tel:'+esc(phone)+'"><em>📞</em>Call</a><a class="act-btn" target="_blank" rel="noopener" href="'+esc(waLink(phone,'Hi '+nameOf(x)+', quick question about your online presence.'))+'"><em>💬</em>WhatsApp</a>':'<button class="act-btn" disabled style="opacity:.5"><em>📞</em>No phone</button>')
    +(email?'<a class="act-btn" href="mailto:'+esc(email)+'"><em>✉️</em>Email</a>':'<button class="act-btn" disabled style="opacity:.5"><em>✉️</em>No email</button>')
    +(website?'<a class="act-btn" target="_blank" rel="noopener" href="'+esc(website)+'"><em>🌐</em>Website</a>':'')
    +'</div>'
    +'<div class="act-row">'
    +'<button class="act-btn primary" onclick="researchLead('+id+')"><em>⌕</em>Research</button>'
    +'<button class="act-btn" onclick="pitchLead('+id+')"><em>✦</em>Pitch</button>'
    +'<button class="act-btn" onclick="saveOutreach('+id+')"><em>➤</em>Save</button>'
    +'</div>'
    +'<div class="pitch-out" id="pitchOut"></div>';
  const researchBlock=research
    ? '<div class="intel"><div class="intel-head"><b>Research intelligence</b><span class="badge '+stateClass(research.research_status)+'">'+esc(research.research_status||'PARTIAL')+'</span></div>'
      +'<div class="state-line"><span>Website</span><span class="badge '+stateClass(research.website&&research.website.status)+'">'+esc(research.website&&research.website.status||'—')+'</span></div>'
      +'<div class="state-line"><span>Google Business</span><span class="badge '+stateClass(research.google&&research.google.status)+'">'+esc(research.google&&research.google.status||'—')+'</span></div>'
      +'<div class="state-line"><span>Search intel</span><span class="badge '+stateClass(research.search&&research.search.status)+'">'+esc(research.search&&research.search.status||'—')+'</span></div>'
      +((research.problems||[]).length?'<div class="tiny muted" style="margin-top:8px"><b>Verified gaps:</b> '+esc(research.problems.slice(0,3).join(' · '))+'</div>':'')
      +'</div>'
    : '<div class="intel"><div class="intel-head"><b>Research</b><span class="badge gray">Not loaded</span></div><div class="tiny muted">Tap Research to pull verified intelligence before outreach.</div></div>';
  openSheet(
    nameOf(x),
    cityOf(x)+(x.industry?' · '+x.industry:''),
    '<div class="meta-row" style="margin:0 0 12px">'+statusBadge(x)+(Number.isFinite(score)?'<span class="badge gray">Score '+esc(Math.round(score))+'</span>':'')+'</div>'
    +'<div class="kv-grid">'
    +kv('PHONE',phone?esc(phone):'')
    +kv('EMAIL',email?'<a class="link" href="mailto:'+esc(email)+'">'+esc(email)+'</a>':'')
    +kv('WEBSITE',website?'<a class="link" target="_blank" rel="noopener" href="'+esc(website)+'">'+esc(website)+'</a>':'')
    +kv('ADDRESS',esc(x.address||x.formatted_address||'—'))
    +'</div>'
    +contactActions
    +researchBlock
  );
}

/* ---------- lead actions ---------- */
async function researchLead(id){
  try{
    toast('Researching lead…');
    const x=await api('/leads/'+Number(id)+'/research',{method:'POST'});
    const lead=allLeads.find(v=>Number(v.id??v.lead_id)===Number(id));
    if(lead){
      lead.research=x.research||{};
      lead.score=x.score?.score??lead.score;
      lead.status=Number(x.score?.score??0)>=60?'QUALIFIED':'RESEARCHED';
    }else if(x.research){const d=await api('/leads/'+Number(id));if(d.item){d.item.research=x.research;renderLeadSheet(d.item);return}}
    if(lead)renderLeadSheet(lead);
    renderLeads();
    toast('Research complete · score '+esc(Math.round(Number(x.score?.score??0))));
  }catch(e){toast(e.message||'Research failed')}
}
async function pitchLead(id){
  try{
    toast('Generating pitch…');
    const x=await api('/leads/'+Number(id)+'/pitch',{method:'POST'});
    const out=$('pitchOut');
    if(out){out.textContent=x.pitch||'';out.classList.add('show')}
    try{if(navigator.clipboard)await navigator.clipboard.writeText(x.pitch||'');toast('Pitch ready · copied to clipboard')}catch(e2){toast('Pitch ready below')}
  }catch(e){toast(e.message||'Pitch failed')}
}
async function saveOutreach(id){
  try{
    await api('/outreach/'+Number(id),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({stage:'READY',notes:'Saved from mobile dashboard',services:[]})});
    toast('Saved to Act pipeline');
    closeSheet();
    go('act');
  }catch(e){toast(e.message||'Could not save')}
}

/* ---------- find / discovery ---------- */
async function startDiscovery(){
  const category=$('mBusinessType').value,city=$('mCity').value,max_results=Number($('mCount').value);
  if(!category||!city){toast('Choose a business type and city first');return}
  const btn=$('mFindBtn');
  btn.disabled=true;btn.textContent='Starting…';
  $('mJobBox').style.display='block';
  setJob(5,'Starting discovery for '+city+'…');
  try{
    const x=await api('/discover',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({category,city,max_results,refresh:false})});
    if(x.reused){setJob(100,'Existing completed dataset reused');toast('Existing dataset loaded');selectedDataset=Number(x.dataset_id);go('leads');btn.disabled=false;btn.textContent='⌕ Find Leads';return}
    setJob(8,'Discovery is running…');
    pollJob(Number(x.job_id),btn);
  }catch(e){
    $('mJobText').textContent=e.message;toast(e.message);
    btn.disabled=false;btn.textContent='⌕ Find Leads';
  }
}
function setJob(p,text){$('mJobPct').textContent=p+'%';$('mJobBar').style.width=p+'%';$('mJobText').textContent=text}
function pollJob(id,btn){
  clearInterval(jobTimer);
  jobTimer=setInterval(async()=>{
    try{
      const x=await api('/jobs/'+id),it=x.item||{};
      const p=Number(x.progress||0);
      const st=String(it.status||'').toUpperCase();
      setJob(p,st==='DONE'?'Discovery complete':st==='FAILED'?'Discovery failed':'Finding businesses… '+(x.businesses_found||0)+' found');
      if(st==='DONE'||st==='FAILED'){
        clearInterval(jobTimer);
        btn.disabled=false;btn.textContent='⌕ Find Leads';
        if(st==='DONE'){toast('Discovery complete');selectedDataset=id;go('leads')}else toast('Discovery failed');
      }
    }catch(e){clearInterval(jobTimer);btn.disabled=false;btn.textContent='⌕ Find Leads';$('mJobText').textContent=e.message}
  },1200);
}

/* ---------- stats ---------- */
async function loadStats(){
  try{
    const x=await api('/analytics');
    const t=x.totals||{};
    $('sLeads').textContent=t.leads??x.leads??0;
    $('sHot').textContent=t.hot??x.hot??0;
    $('sQualified').textContent=t.qualified??x.qualified??0;
    $('sContacted').textContent=t.contacted??x.contacted??0;
    renderBars('cityChart',x.cities||x.by_city||[],'No city data yet');
    renderBars('serviceChart',x.services||x.by_service||[],'No service data yet');
    setNet(true);
  }catch(e){errBox('cityChart',e);errBox('serviceChart',e);setNet(false)}
}
function renderBars(id,data,emptyText){
  const el=$(id);if(!el)return;
  let entries=Array.isArray(data)?data.map(x=>[x.name||x.city||x.service||'Unknown',x.count??x.value??0]):Object.entries(data||{});
  entries=entries.filter(x=>Number(x[1])>0).sort((a,b)=>Number(b[1])-Number(a[1])).slice(0,8);
  if(!entries.length){el.innerHTML='<div class="tiny muted" style="padding:12px 0;text-align:center">'+esc(emptyText)+'</div>';return}
  const max=Math.max.apply(null,entries.map(x=>Number(x[1])));
  el.innerHTML=entries.map((x,i)=>'<div class="bar-row"><span title="'+esc(x[0])+'">'+esc(x[0])+'</span><div class="bar-track"><i class="'+(id==='serviceChart'?'g':'')+'" style="width:'+Math.max(4,Number(x[1])/max*100)+'%"></i></div><b>'+esc(x[1])+'</b></div>').join('');
}

/* ---------- act ---------- */
async function loadAct(){
  loading('actList','Loading pipeline…');
  try{
    const x=await api('/outreach');
    const items=x.items||[];
    const counts=x.counts||{};
    $('actCounts').innerHTML=Object.entries(counts).map(([k,v])=>'<span class="badge blue">'+esc(k)+': '+esc(v)+'</span>').join('')||'<span class="badge gray">No stages yet</span>';
    $('actList').innerHTML=items.length?items.map(d=>{
      const id=Number(d.business_id||d.lead_id||0);
      const loc=[d.city,d.industry].filter(Boolean).join(' · ');
      const extra=[d.stage||'READY',loc,d.notes].filter(Boolean).join(' · ');
      return '<button class="row" onclick="openLeadSheet('+id+')"><div class="row-main"><div class="row-title">'+esc(d.name||d.business_name||('Lead #'+id))+'</div><div class="row-sub">'+esc(extra)+'</div></div><span class="chev">›</span></button>';
    }).join(''):emptyBox('actList','➤','No saved opportunities','Open a lead and tap Save to build your pipeline.');
    const fu=x.followups||[];
    if(fu.length){
      $('fuHead').style.display='flex';
      $('followups').innerHTML=fu.map(f=>'<div class="row" style="cursor:default"><div class="row-main"><div class="row-title">'+esc(f.name||f.business_name||('Lead #'+(f.business_id||'')))+'</div><div class="row-sub">'+esc(f.due_at||f.due||'Due')+'</div></div></div>').join('');
    }else{$('fuHead').style.display='none';$('followups').innerHTML=''}
    setNet(true);
  }catch(e){errBox('actList',e);setNet(false)}
}

/* ---------- theme (same 4-theme system as desktop) ---------- */
function applyTheme(mode,style){
  document.body.classList.toggle('dark',mode==='dark');
  document.body.classList.toggle('neo',style==='neo');
  localStorage.setItem('lh-theme',mode+'-'+style);
}
function cycleTheme(){
  const v=localStorage.getItem('lh-theme')||'light-modern';
  const map={'light-modern':'dark-modern','dark-modern':'light-neo','light-neo':'dark-neo','dark-neo':'light-modern'};
  const next=map[v]||'light-modern';
  const parts=next.split('-');
  applyTheme(parts[0],parts[1]);
  toast(next.replace('-',' · ').replace('light','Light').replace('dark','Dark').replace('modern','Modern').replace('neo','Neo'));
}
(function init(){
  const v=localStorage.getItem('lh-theme')||'light-modern';
  const parts=v.split('-');
  applyTheme(parts[0],parts[1]);
  loadHome();
})();
</script>
</body>
</html>'''
