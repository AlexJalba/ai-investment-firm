# AI Investment Firm

A production-grade multi-agent AI system that operates a simulated US equity investment firm. Built as a Cato Networks home assignment.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                       LangGraph Trading Day                      │
│                                                                   │
│  fetch_prices → research → portfolio_manager → risk              │
│                                                         ↓        │
│                                              ┌─ approved         │
│                                              └─ hitl_pending ──► │
│                                                      │           │
│                                              Risk Committee       │
│                                              (human CLI)         │
│                                                      │           │
│                                              execution → report  │
└─────────────────────────────────────────────────────────────────┘
```

### Agents

| Agent | Model | Role | Tools |
|-------|-------|------|-------|
| **Research** | claude-haiku-4-5 | Retrieves evidence via RAG, produces cited analysis per ticker | ChromaDB, yfinance news |
| **Portfolio Manager** | claude-sonnet-4-6 | Sizes and selects trades from research | Research reports, portfolio snapshot |
| **Risk** | claude-sonnet-4-6 | Validates proposals, applies guardrails, flags HITL | Position calculator, sector limits |
| **Execution** | — (deterministic) | Simulates fills with slippage + commission | Paper trading engine |
| **Reporting** | claude-haiku-4-5 | Generates daily reports + narrative | Excel writer, dashboard API |

### Key Design Decisions

- **LangGraph** for orchestration: native HITL interrupt support, persistent checkpoints, and graph-based state flow.
- **SQLite + WAL mode** for portfolio state: survives crashes and restarts, zero infrastructure overhead.
- **ChromaDB** for RAG: embedded vector store, no external service required.
- **Cost-aware model routing**: cheap Haiku for research/reporting, Sonnet for PM/Risk decisions.
- **Append-only JSONL audit log**: every event is immutable and replayable.

---

## Quick Start

### Prerequisites

- Python 3.11+
- An Anthropic API key

### Install

```bash
git clone https://github.com/AlexJalba/ai-investment-firm.git
cd ai-investment-firm
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
# Edit .env and set ANTHROPIC_API_KEY=sk-ant-...
```

### Run a trading day

```bash
# Trade the default tech universe (AAPL MSFT GOOGL AMZN NVDA)
python -m src.cli trade

# Trade specific tickers on a specific date
python -m src.cli trade AAPL TSLA NVDA --date 2024-11-01
```

When trades exceed $50,000 notional, the terminal pauses for **Risk Committee review**. You will be prompted to approve, reject, or resize each trade.

### Start the dashboard

```bash
python -m src.cli dashboard
# Open http://localhost:8080
```

The dashboard auto-refreshes every 30 seconds and shows live portfolio state, the latest daily narrative, and the audit log.

### Pre-populate the RAG store

```bash
python -m src.cli ingest AAPL MSFT GOOGL AMZN NVDA
```

### Run the eval harness

```bash
python -m src.cli eval AAPL MSFT GOOGL --start 2024-10-01 --end 2024-10-31
```

Outputs `data/eval/eval_report.json` with portfolio return vs SPY, grounding score, and HITL decision breakdown.

### Docker

```bash
cp .env.example .env  # set your API key
docker compose up
# Dashboard at http://localhost:8080
# Trade: docker compose run firm python -m src.cli trade
```

---

## Output Channels

| Channel | Format | Justification |
|---------|--------|---------------|
| **Web Dashboard** | FastAPI + HTML | Real-time portfolio visibility; reviewable without any tooling |
| **Excel Report** | `.xlsx` per trading day | Standard format for financial reporting; portable artifact for the repo |

---

## Production Readiness

### Persistent state
Portfolio cash, holdings, cost basis, and P&L are stored in SQLite with WAL mode. A restart re-reads the last state cleanly. Reconciliation is exact — no floating totals.

### RAG layer
ChromaDB with cosine similarity. Every research note must include at least one citation or it is downgraded to `hold` with `confidence < 0.4`. Web-sourced text is sanitized against prompt injection before ingestion.

### Human-in-the-Loop
Trades above the `TRADE_NOTIONAL_HITL_THRESHOLD` (default $50k) pause the graph. LangGraph persists the full state during the wait. The human can approve, reject, or resize each trade. The decision is written to the audit log.

### Observability
- **Structured logs**: every agent invocation emits JSON via `structlog`
- **OpenTelemetry traces**: spans for every graph node and agent call (OTLP export optional)
- **Audit log**: append-only JSONL at `data/audit.jsonl` — every trade, risk decision, HITL event, and report is recorded with a timestamp

### Guardrails
- Input: Pydantic v2 schemas on all agent outputs
- Prompt injection: regex sanitizer strips known injection patterns from web-sourced text before RAG ingestion
- Position size: hard cap at 10% of portfolio per ticker
- Sector concentration: 30% per GICS sector
- Daily loss: halt at 2% drawdown
- Hallucination check: citations required on every research note and trade proposal

### Eval harness
`eval/harness.py` replays any historical date window:
- Portfolio return vs SPY benchmark (alpha)
- Grounding score (% of research notes with citations)
- HITL decision breakdown (approved / rejected / edited)
- Per-day P&L table

---

## Repository Layout

```
ai-investment-firm/
├── src/
│   ├── agents/          # 5 specialized agents
│   ├── graph/           # LangGraph state + graph assembly
│   ├── portfolio/       # Models, SQLite engine, paper trading
│   ├── rag/             # ChromaDB store + citation formatter
│   ├── market_data/     # yfinance prices + news ingestion
│   ├── guardrails/      # Validators, injection defense, risk checks
│   ├── observability/   # structlog + OpenTelemetry + audit log
│   ├── reporting/       # FastAPI dashboard + Excel writer
│   ├── hitl/            # CLI-based Risk Committee
│   └── cli.py           # Typer entrypoint
├── eval/
│   └── harness.py       # Reproducible historical replay
├── tests/               # pytest unit tests
├── sample_run/          # Committed trading day artifacts
├── Dockerfile
├── docker-compose.yml
└── README.md
```

---

## Running Tests

```bash
pytest tests/ -v --cov=src --cov-report=term-missing
```

---

## What Would Break in Production (and What's Next)

1. **yfinance rate limits** — replace with a paid market data vendor (Polygon.io, Bloomberg B-PIPE) behind an abstraction layer.
2. **Single-process SQLite** — replace with PostgreSQL for horizontal scaling; the SQLAlchemy ORM makes this a one-line connection string change.
3. **ChromaDB in-process** — replace with a managed vector DB (Pinecone, Weaviate) for multi-process access and larger corpora.
4. **CLI-based HITL** — replace with a web-based Risk Committee UI or Slack slash command for remote approval.
5. **No real-time data streaming** — add a WebSocket feed (Alpaca, IEX Cloud) for intraday tick data rather than polling yfinance.

---

## Bonus: AWS Bedrock AgentCore

The model routing layer (`src/config.py`) is abstracted behind a settings interface. Replacing `ChatAnthropic` with `ChatBedrockConverse` requires changing three lines in each agent. A `MODEL_PROVIDER=bedrock` env var could dispatch at runtime.

---

## License

MIT
