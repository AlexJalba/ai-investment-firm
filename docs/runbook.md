# Operational Runbook

## Starting the System

### Offline demo (no API key)
```bash
bash scripts/seed_and_trade.sh
python -m src.cli dashboard   # http://localhost:8080
```

### Live trading (API key required)
```bash
# 1. Seed RAG store (once, or when news corpus changes)
python scripts/seed_rag.py

# 2. Run a trading day
python -m src.cli trade AAPL MSFT GOOGL AMZN NVDA --date 2024-10-25

# 3. Start dashboard
python -m src.cli dashboard --host 0.0.0.0 --port 8080
```

### Docker
```bash
cp .env.example .env   # fill in ANTHROPIC_API_KEY
docker compose up      # dashboard at http://localhost:8080

# Run a trading day inside the container
docker compose run firm python -m src.cli trade AAPL MSFT GOOGL AMZN NVDA
```

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | Required for live mode. Leave blank with `MOCK_LLM=true`. |
| `MOCK_LLM` | `false` | `true` replaces all LLM calls with deterministic fixtures |
| `RESEARCH_MODEL` | `claude-haiku-4-5-20251001` | Model for Research + Reporting agents |
| `PM_MODEL` | `claude-sonnet-4-6` | Model for Portfolio Manager agent |
| `RISK_MODEL` | `claude-sonnet-4-6` | Model for Risk agent |
| `STARTING_CAPITAL` | `1000000.0` | Initial portfolio cash |
| `BENCHMARK_TICKER` | `SPY` | Benchmark for alpha calculation |
| `MAX_SINGLE_POSITION_PCT` | `0.10` | Hard cap per ticker (10% of portfolio) |
| `MAX_SECTOR_CONCENTRATION` | `0.30` | Hard cap per GICS sector (30%) |
| `DAILY_LOSS_LIMIT_PCT` | `0.02` | Halt trading at 2% daily drawdown |
| `TRADE_NOTIONAL_HITL_THRESHOLD` | `50000.0` | Trades above this require human approval |
| `SLIPPAGE_BPS` | `5` | Simulated slippage in basis points |
| `COMMISSION_PER_SHARE` | `0.005` | Simulated commission per share (USD) |
| `CHROMA_PERSIST_DIR` | `./data/chroma` | ChromaDB persistence path |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG / INFO / WARNING / ERROR) |
| `AUDIT_LOG_PATH` | `./data/audit.jsonl` | Append-only audit log path |
| `OTLP_ENDPOINT` | `` | Optional OTLP endpoint for trace export |
| `REPORTS_DIR` | `./data/reports` | Directory for Excel + JSON reports |

---

## Human-in-the-Loop (Risk Committee)

When a trade exceeds the `TRADE_NOTIONAL_HITL_THRESHOLD`, the terminal pauses:

```
═══════════════════════════════════════
 RISK COMMITTEE — Trade Review
═══════════════════════════════════════
 Ticker : AAPL
 Side   : BUY
 Shares : 250
 Price  : $229.00
 Notional: $57,250.00
 Rationale: Apple Q4 beat: revenue $94.9B...
 Risk flags: []

 [a] Approve   [r] Reject   [e] Edit shares   [s] Skip
```

- **Approve** — trade proceeds as proposed
- **Reject** — trade is dropped, logged to audit
- **Edit** — enter a new share count; notional is recalculated
- **Skip** — treated as reject for this session

All decisions are written to `data/audit.jsonl` with a timestamp.

---

## Resetting State

```bash
# Wipe portfolio (start fresh with $1M cash)
rm -f data/portfolio.db

# Wipe RAG store (re-seed after)
rm -rf data/chroma

# Clear audit log
> data/audit.jsonl

# Wipe all data
rm -rf data/portfolio.db data/chroma data/audit.jsonl data/reports/
```

---

## Running the Eval Harness

```bash
python -m src.cli eval AAPL MSFT GOOGL AMZN NVDA --start 2024-10-25 --end 2024-10-31
```

Output: `data/eval/eval_report.json`

The harness automatically:
- Wipes and recreates the portfolio DB for each run
- Uses mock LLM fixtures (no API key needed)
- Reports portfolio return vs SPY, grounding score, HITL breakdown, per-day P&L

---

## Running Tests

```bash
pytest tests/ -v --cov=src --cov-report=term-missing
```

Tests use mock fixtures — no API key or network access required.

---

## Monitoring

**Dashboard:** `http://localhost:8080` — auto-refreshes every 30 seconds.
Shows: portfolio value, holdings, filled trades, daily narrative, audit log.

**Audit log:** `data/audit.jsonl` — one JSON line per event. Key events:
- `trading_day.start` / `trading_day.end`
- `research.completed` — per ticker, with confidence and citation count
- `risk.approved` / `risk.rejected` / `risk.hitl_required` / `risk.sector_halt` / `risk.daily_loss_halt`
- `hitl.paused` / `hitl.decision`
- `trade.filled` / `execution.failed`
- `report.generated`

**Structured logs:** JSON to stdout via `structlog`. Each line includes `event`, `level`, `timestamp`, and context fields.

**OpenTelemetry:** Set `OTLP_ENDPOINT=http://localhost:4317` to export spans to any OTLP-compatible backend (Jaeger, Grafana Tempo, etc.).

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `0 fills` after trading day | Stale portfolio DB from previous run | `rm -f data/portfolio.db` |
| Dashboard shows old data | SQLAlchemy singleton cached old connection | Restart dashboard process |
| `ModuleNotFoundError: eval` | PYTHONPATH not set | `export PYTHONPATH=$(pwd)` |
| ChromaDB empty on fresh clone | RAG store not seeded | `python scripts/seed_rag.py` |
| HITL prompt doesn't appear | All trades below $50k threshold | Lower `TRADE_NOTIONAL_HITL_THRESHOLD` or use fixtures with 250 AAPL shares |
| `AuthenticationError` | Invalid API key | Check `ANTHROPIC_API_KEY` in `.env`, or use `MOCK_LLM=true` |

---

## Recovery After Crash

The trading day is designed to be re-run from scratch. There is no partial resume:

1. `rm -f data/portfolio.db` — wipe any half-written portfolio state
2. Re-run `bash scripts/seed_and_trade.sh` (or the live trade command)

Portfolio state in SQLite is transactional — a crash mid-fill will not leave the DB in an inconsistent state.
