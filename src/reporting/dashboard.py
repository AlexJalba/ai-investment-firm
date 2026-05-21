"""FastAPI web dashboard — serves live portfolio state and historical reports."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse

from src.config import get_settings
from src.market_data.prices import get_prices
from src.portfolio.engine import PaperTradingEngine

app = FastAPI(title="AI Investment Firm Dashboard", version="0.1.0")


@app.get("/", response_class=HTMLResponse)
async def index():
    return _render_dashboard()


@app.get("/api/portfolio")
async def portfolio():
    engine = PaperTradingEngine()
    tickers = [h.ticker for h in engine.get_snapshot().holdings]
    prices = get_prices(tickers) if tickers else {}
    snap = engine.get_snapshot(prices)
    return {
        "as_of": snap.as_of.isoformat(),
        "cash": snap.cash,
        "total_value": snap.total_value,
        "realized_pnl": snap.realized_pnl,
        "unrealized_pnl": snap.unrealized_pnl,
        "holdings": [h.model_dump() for h in snap.holdings],
    }


@app.get("/api/reports")
async def list_reports():
    cfg = get_settings()
    reports_path = Path(cfg.reports_dir)
    if not reports_path.exists():
        return []
    dates = sorted(
        [d.name for d in reports_path.iterdir() if d.is_dir()],
        reverse=True,
    )
    return dates


@app.get("/api/reports/{trade_date}")
async def get_report(trade_date: str):
    cfg = get_settings()
    report_file = Path(cfg.reports_dir) / trade_date / "daily_report.json"
    if not report_file.exists():
        raise HTTPException(404, f"No report for {trade_date}")
    return json.loads(report_file.read_text())


@app.get("/api/reports/{trade_date}/excel")
async def download_excel(trade_date: str):
    cfg = get_settings()
    excel_file = Path(cfg.reports_dir) / trade_date / "daily_report.xlsx"
    if not excel_file.exists():
        raise HTTPException(404, f"No Excel report for {trade_date}")
    return FileResponse(
        str(excel_file),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=f"report_{trade_date}.xlsx",
    )


@app.get("/api/audit")
async def audit_log(limit: int = 100):
    cfg = get_settings()
    log_path = Path(cfg.audit_log_path)
    if not log_path.exists():
        return []
    lines = log_path.read_text().strip().split("\n")[-limit:]
    return [json.loads(l) for l in lines if l]


def _render_dashboard() -> str:
    return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AI Investment Firm Dashboard</title>
  <style>
    :root { --blue: #1F4E79; --light: #D6E4F0; --green: #006100; --red: #9C0006; }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
           background: #f4f6f9; color: #333; }
    header { background: var(--blue); color: white; padding: 1rem 2rem;
             display: flex; justify-content: space-between; align-items: center; }
    header h1 { font-size: 1.4rem; }
    .subtitle { font-size: 0.85rem; opacity: 0.7; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 1rem; padding: 1.5rem 2rem; }
    .card { background: white; border-radius: 8px; padding: 1.2rem;
            box-shadow: 0 1px 4px rgba(0,0,0,.1); }
    .card h3 { font-size: 0.75rem; text-transform: uppercase; color: #888;
               letter-spacing: .05em; margin-bottom: .5rem; }
    .card .value { font-size: 1.8rem; font-weight: 700; color: var(--blue); }
    .card .value.pos { color: var(--green); }
    .card .value.neg { color: var(--red); }
    section { padding: 0 2rem 2rem; }
    section h2 { font-size: 1rem; color: var(--blue); margin-bottom: .8rem;
                 padding-bottom: .3rem; border-bottom: 2px solid var(--light); }
    table { width: 100%; border-collapse: collapse; background: white;
            border-radius: 8px; overflow: hidden; box-shadow: 0 1px 4px rgba(0,0,0,.1); }
    th { background: var(--blue); color: white; padding: .6rem 1rem;
         text-align: left; font-size: .8rem; }
    td { padding: .6rem 1rem; border-bottom: 1px solid #f0f0f0; font-size: .9rem; }
    tr:last-child td { border-bottom: none; }
    tr:nth-child(even) td { background: var(--light); }
    .tag-buy { color: var(--green); font-weight: 600; }
    .tag-sell { color: var(--red); font-weight: 600; }
    #narrative { background: white; border-radius: 8px; padding: 1.2rem;
                 box-shadow: 0 1px 4px rgba(0,0,0,.1); white-space: pre-wrap;
                 line-height: 1.6; font-size: .9rem; }
    .spinner { display: inline-block; border: 3px solid #ddd;
               border-top-color: var(--blue); border-radius: 50%;
               width: 24px; height: 24px; animation: spin .7s linear infinite; }
    @keyframes spin { to { transform: rotate(360deg); } }
  </style>
</head>
<body>
  <header>
    <div>
      <h1>AI Investment Firm</h1>
      <div class="subtitle" id="as-of">Loading...</div>
    </div>
    <div id="refresh-btn" style="cursor:pointer;opacity:.8;" onclick="loadAll()">&#x21bb; Refresh</div>
  </header>

  <div class="grid" id="metrics">
    <div class="card"><h3>Total Value</h3><div class="value" id="total-value">—</div></div>
    <div class="card"><h3>Cash</h3><div class="value" id="cash">—</div></div>
    <div class="card"><h3>Unrealized P&L</h3><div class="value" id="upnl">—</div></div>
    <div class="card"><h3>Realized P&L</h3><div class="value" id="rpnl">—</div></div>
  </div>

  <section>
    <h2>Holdings</h2>
    <table id="holdings-table">
      <thead><tr><th>Ticker</th><th>Shares</th><th>Cost Basis</th><th>Sector</th></tr></thead>
      <tbody id="holdings-body"><tr><td colspan="4"><div class="spinner"></div></td></tr></tbody>
    </table>
  </section>

  <section style="margin-top:1.5rem;">
    <h2>Latest Daily Report</h2>
    <div id="narrative">Loading...</div>
  </section>

  <section style="margin-top:1.5rem;">
    <h2>Recent Audit Events</h2>
    <table id="audit-table">
      <thead><tr><th>Time</th><th>Event</th><th>Details</th></tr></thead>
      <tbody id="audit-body"></tbody>
    </table>
  </section>

  <script>
    const fmt = (n, decimals=2) => n == null ? '—' : new Intl.NumberFormat('en-US',{
      style:'currency', currency:'USD', minimumFractionDigits:decimals}).format(n);
    const pct = n => n == null ? '—' : (n>=0?'+':'')+( n*100).toFixed(2)+'%';
    const colorClass = n => n >= 0 ? 'pos' : 'neg';

    async function loadPortfolio() {
      const r = await fetch('/api/portfolio').then(r=>r.json());
      document.getElementById('as-of').textContent = 'As of ' + r.as_of;
      document.getElementById('total-value').textContent = fmt(r.total_value);
      document.getElementById('cash').textContent = fmt(r.cash);
      const upnl = document.getElementById('upnl');
      upnl.textContent = fmt(r.unrealized_pnl);
      upnl.className = 'value ' + colorClass(r.unrealized_pnl);
      const rpnl = document.getElementById('rpnl');
      rpnl.textContent = fmt(r.realized_pnl);
      rpnl.className = 'value ' + colorClass(r.realized_pnl);

      const tbody = document.getElementById('holdings-body');
      if (!r.holdings.length) {
        tbody.innerHTML = '<tr><td colspan="4" style="color:#888;text-align:center">No holdings yet</td></tr>';
        return;
      }
      tbody.innerHTML = r.holdings.map(h => `
        <tr>
          <td><strong>${h.ticker}</strong></td>
          <td>${h.shares.toLocaleString()}</td>
          <td>${fmt(h.cost_basis)}</td>
          <td>${h.sector}</td>
        </tr>`).join('');
    }

    async function loadLatestReport() {
      const dates = await fetch('/api/reports').then(r=>r.json());
      if (!dates.length) { document.getElementById('narrative').textContent='No reports yet.'; return; }
      const report = await fetch('/api/reports/'+dates[0]).then(r=>r.json());
      document.getElementById('narrative').textContent = report.narrative || 'No narrative available.';
    }

    async function loadAudit() {
      const events = await fetch('/api/audit?limit=20').then(r=>r.json());
      const tbody = document.getElementById('audit-body');
      tbody.innerHTML = events.reverse().map(e => {
        const {ts, event, ...rest} = e;
        return `<tr>
          <td style="white-space:nowrap;font-size:.8rem">${(ts||'').substring(0,19)}</td>
          <td><strong>${event}</strong></td>
          <td style="font-size:.8rem;color:#555">${JSON.stringify(rest).substring(0,120)}</td>
        </tr>`;
      }).join('');
    }

    async function loadAll() {
      await Promise.all([loadPortfolio(), loadLatestReport(), loadAudit()]);
    }

    loadAll();
    setInterval(loadAll, 30000);
  </script>
</body>
</html>"""


def start_dashboard(host: str = "0.0.0.0", port: int = 8080):
    import uvicorn
    uvicorn.run(app, host=host, port=port)
