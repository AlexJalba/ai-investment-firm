# Technical Overview

## System Summary

A multi-agent AI investment firm built on LangGraph. Five specialized agents collaborate to
research equities, size positions, validate risk, execute trades, and report results. All
decisions are grounded in retrieved evidence, bounded by hard guardrails, and audited
immutably.

---

## Agent Contracts

### 1. Research Agent
**Model:** `claude-haiku-4-5` (fast, cheap — one call per ticker)

| | Type |
|---|---|
| Input | `ticker: str`, RAG chunks from ChromaDB |
| Output | `ResearchReport` — `ticker`, `summary`, `sentiment`, `confidence: float`, `citations: list[str]`, `recommendation: buy/hold/sell` |
| Failure mode | If no citations found, returns `recommendation=hold`, `confidence<0.4`. Never fabricates. |

Citations are required by Pydantic schema — if the LLM returns a report without them, the output is rejected and the agent returns a safe `hold` default.

---

### 2. Portfolio Manager Agent
**Model:** `claude-sonnet-4-6`

| | Type |
|---|---|
| Input | `research_reports: list[ResearchReport]`, `portfolio_snapshot: PortfolioSnapshot`, `market_prices: dict` |
| Output | `list[TradeProposal]` — `ticker`, `side`, `shares`, `rationale`, `confidence` |
| Failure mode | If LLM output fails Pydantic validation, no proposals are emitted for that ticker. |

Sizes positions as a percentage of portfolio. Will not propose a trade without a cited rationale.

---

### 3. Risk Agent
**Model:** `claude-sonnet-4-6` (soft second opinion) + hard-coded guardrails

| | Type |
|---|---|
| Input | `proposals: list[TradeProposal]`, `snapshot`, `market_prices`, `start_of_day_value` |
| Output | `(approved: list, hitl_pending: list)` |
| Failure mode | LLM parse failure → proposal rejected (fail-safe). Hard guardrails run regardless of LLM output. |

**Hard guardrails (code, cannot be overridden by LLM):**
- Daily loss ≥ 2% → halt entire trading day
- Position size > 10% of portfolio → reject
- Sector concentration > 30% → reject
- Notional > $50k → route to HITL

**Soft guardrails (LLM second opinion):**
- Confidence < 0.3 with no strong evidence
- Vague or uncited rationale

---

### 4. Execution Agent
**Model:** Deterministic (no LLM)

| | Type |
|---|---|
| Input | `approved_trades: list`, `market_prices`, `engine: PaperTradingEngine`, `trade_date` |
| Output | `list[FillResult]` — `ticker`, `side`, `shares`, `fill_price`, `notional`, `commission`, `slippage`, `executed_at` |
| Failure mode | Per-trade exception caught and logged; other trades continue. |

Applies 5bps slippage and $0.005/share commission. Uses `trade_date` + current wall-clock time for timestamp.

---

### 5. Reporting Agent
**Model:** `claude-haiku-4-5`

| | Type |
|---|---|
| Input | `trade_date`, `snapshot`, `filled_trades`, `research_reports`, `start_of_day_value` |
| Output | `daily_report.xlsx` + `daily_report.json` + narrative text on dashboard |
| Failure mode | Excel/JSON write errors are logged; dashboard shows last successful report. |

---

## State Flow

```
TradingDayState (TypedDict) flows through every LangGraph node.

fetch_prices   → adds: market_prices
research       → adds: research_reports
portfolio_mgr  → adds: portfolio_snapshot, trade_proposals
risk           → mutates: trade_proposals (approved only), adds: pending_hitl, halt
hitl           → mutates: trade_proposals (merges HITL-approved), adds: hitl_decisions
execution      → adds: filled_trades
reporting      → writes reports (no state mutation)
```

State is held in `MemorySaver` (in-memory) between the two `graph.invoke` calls within a
single trading day run. There is no cross-run state persistence in the checkpointer — portfolio
state lives in SQLite.

---

## RAG Layer

**Store:** ChromaDB (embedded, cosine similarity, 384-dim MiniLM embeddings)

**Ingestion:** `scripts/seed_rag.py` loads `eval/sample_data/news_oct2024.json` (33 articles, 5 tickers). Each article is embedded with title + summary concatenated and stored with `ticker` metadata.

**Retrieval:** Each Research Agent call queries ChromaDB with `where={"ticker": ticker}` — the metadata filter is essential. Without it, ~40% of articles route to the wrong ticker at 33-article scale.

**Citation discipline:** Every retrieved chunk becomes a numbered citation in the prompt. The Pydantic output schema requires at least one citation. If ChromaDB returns nothing, the agent returns `hold` with `confidence=0.0`.

**Prompt injection defense:** Web-sourced text is passed through a regex sanitizer in `src/guardrails/validators.py` before ingestion — strips known injection patterns (`ignore previous instructions`, `system:`, etc.).

---

## Persistence

| Store | Technology | What it holds |
|---|---|---|
| Portfolio state | SQLite (WAL mode) | Cash, holdings, cost basis, trade history, P&L |
| Vector store | ChromaDB | Article embeddings + metadata |
| Audit log | Append-only JSONL | Every trade, risk decision, HITL event, report |
| Reports | `.xlsx` + `.json` | One file pair per trading day |

SQLite uses WAL mode — concurrent reads don't block writes, and a crash mid-write leaves the DB
in the last committed state. The `_engine` and `_SessionLocal` are module-level singletons;
reinitializing requires setting them to `None` (done in `eval/harness.py` between eval days).

---

## Partial Failure Behaviour

| Failure | Behaviour |
|---|---|
| Research agent LLM timeout | Ticker skipped, no proposal generated. Other tickers continue. |
| Portfolio manager parse failure | That ticker's proposal rejected. Others proceed. |
| Risk agent LLM failure | Hard guardrails still run. LLM soft checks skipped (fail-safe). |
| Execution fill error | Logged to audit log. Other fills continue. |
| Reporting write failure | Logged. Dashboard shows last successful report. |
| Process crash mid-run | Re-run the full trading day. No partial state is resumable — by design, since market data changes. |
| Daily loss limit hit | All trade proposals dropped. Graph routes directly to reporting with empty fills. |

---

## Cost-Aware Model Routing

| Agent | Model | Rationale |
|---|---|---|
| Research | Haiku 4.5 | High volume (one call per ticker), straightforward summarization |
| Portfolio Manager | Sonnet 4.6 | Complex multi-ticker sizing decisions |
| Risk | Sonnet 4.6 | High-stakes second opinion; errors are costly |
| Reporting | Haiku 4.5 | Templated narrative, low complexity |

With 5 tickers, a full trading day costs approximately $0.02–0.05 in API fees.

---

## Observability

Every agent emits structured JSON logs via `structlog`. Key fields: `event`, `ticker`, `timestamp`.

OpenTelemetry spans wrap each graph node and agent call. Spans are exported via OTLP when
`OTLP_ENDPOINT` is configured; otherwise silenced. The audit log (`data/audit.jsonl`) is the
primary replay artifact — it contains enough information to reconstruct every decision end-to-end.
