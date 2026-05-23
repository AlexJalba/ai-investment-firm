# AI Investment Firm

A production-grade multi-agent AI system that operates a simulated US equity investment firm. Built as a Cato Networks home assignment.

## Architecture

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                          LangGraph Orchestration                             ║
║                                                                              ║
║   ┌─────────────┐   ┌──────────┐   ┌──────────────────┐   ┌─────────────┐  ║
║   │ fetch_prices│──▶│ research │──▶│ portfolio_manager │──▶│    risk     │  ║
║   └─────────────┘   └────┬─────┘   └──────────────────┘   └──────┬──────┘  ║
║                           │    TradingDayState flows               │         ║
║                           │    through every node                 ▼         ║
║   ┌───────────────────┐   │                              approved / hitl?    ║
║   │   RAG Store       │   │                                       │         ║
║   │  (ChromaDB)       │◀──┘  query per ticker                     │         ║
║   │  cosine similarity│      metadata filter                  ┌───▼──────┐  ║
║   │  384-dim MiniLM   │                                        │   hitl   │  ║
║   └───────────────────┘                              ┌─ halt ──┴──────────┘  ║
║                                                      │         │             ║
║                                                      │    Risk Committee     ║
║                                                      │    (human CLI prompt) ║
║                                                      │         │             ║
║                                                      │    ┌────▼──────────┐  ║
║                                                      │    │   execution   │  ║
║                                                      │    └────┬──────────┘  ║
║                                                      │         │             ║
║                                                      └────▶┌───▼──────────┐  ║
║                                                            │  reporting   │  ║
║                                                            └──────────────┘  ║
╚══════════════════════════════════════════════════════════════════════════════╝

╔══════════════════════════════════════════════════════════════════════════════╗
║                             Persistence Layer                                ║
║                                                                              ║
║   SQLite (WAL)          ChromaDB               JSONL audit log               ║
║   ├── holdings          ├── embeddings         └── every trade, risk         ║
║   ├── cash              └── metadata               decision, HITL event      ║
║   └── trade history         (ticker filter)        and report — immutable    ║
╚══════════════════════════════════════════════════════════════════════════════╝

╔══════════════════════════════════════════════════════════════════════════════╗
║                            Observability                                     ║
║                                                                              ║
║   structlog → stdout (JSON)      OpenTelemetry spans (OTLP, optional)        ║
║   FastAPI dashboard → http://localhost:8080  (audit log + portfolio state)   ║
╚══════════════════════════════════════════════════════════════════════════════╝

╔══════════════════════════════════════════════════════════════════════════════╗
║                              Deployment                                      ║
║                                                                              ║
║   Single Docker container                                                    ║
║   └── ./data mounted as volume                                               ║
║       ├── portfolio.db      (SQLite)                                         ║
║       ├── chroma/           (ChromaDB)                                       ║
║       ├── audit.jsonl                                                        ║
║       └── reports/          (.xlsx per trading day)                          ║
╚══════════════════════════════════════════════════════════════════════════════╝
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

### Option A — Zero API key (offline demo, under 10 minutes)

No Anthropic key required. All LLM calls are replaced by deterministic fixtures.

```bash
git clone https://github.com/AlexJalba/ai-investment-firm.git
cd ai-investment-firm
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env          # no key needed for mock mode

# Seed ChromaDB from committed sample news, wipe portfolio DB, run trading day
bash scripts/seed_and_trade.sh
```

The script will pause at the **Risk Committee** step — one trade (AAPL, ~$57k notional) exceeds the $50k HITL threshold. Approve or reject it in the terminal, then execution and reporting complete automatically.

```bash
# Open the dashboard to see portfolio state, daily narrative, and audit log
python -m src.cli dashboard
# http://localhost:8080
```

The committed sample run is already visible in the dashboard at startup (`sample_run/2024-10-31/`).

---

### Option B — Live API key

```bash
cp .env.example .env
# Edit .env: set ANTHROPIC_API_KEY=sk-ant-...

# Seed RAG from committed news corpus
python scripts/seed_rag.py

# Run a trading day
python -m src.cli trade AAPL MSFT GOOGL AMZN NVDA --date 2024-10-25

# Start dashboard
python -m src.cli dashboard
```

### Run the eval harness

```bash
python -m src.cli eval AAPL MSFT GOOGL --start 2024-10-01 --end 2024-10-31
```

Outputs `data/eval/eval_report.json` with portfolio return vs SPY, grounding score, and HITL decision breakdown.

### Docker

```bash
cp .env.example .env  # set your API key (or leave blank for mock mode)
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
Trades above the `TRADE_NOTIONAL_HITL_THRESHOLD` (default $50k) pause the graph within the same process. The Risk Agent flags them, the CLI prompts the human to approve, reject, or resize each trade, and then execution resumes. The decision is written to the audit log. If the process crashes mid-run, the trading day is re-run from scratch — market data and news are re-fetched, ensuring analysis is always based on current information.

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
