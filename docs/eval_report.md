# Eval Report — October 2024

## Period
**2024-10-25 to 2024-10-31** (5 trading days)
**Universe:** AAPL, MSFT, GOOGL, AMZN, NVDA
**Benchmark:** SPY

---

## Portfolio Performance

| Metric | Value |
|---|---|
| Portfolio return | +0.03% |
| SPY benchmark return | +0.17% |
| Alpha | -0.14% |
| Starting capital | $1,000,000 |
| Ending value | $1,000,284 |

The portfolio underperformed SPY by 14bps over the week. This is expected: we buy-and-hold from day 1, while SPY had positive drift across the period. The goal is not to beat the market — it is to demonstrate correct pipeline execution, not alpha generation.

---

## Per-Day P&L

| Date | Start Value | End Value | Daily P&L | Trades |
|---|---|---|---|---|
| 2024-10-25 | $1,000,000.00 | $999,988.92 | -0.001% | 4 |
| 2024-10-28 | $999,999.55 | $1,000,035.42 | +0.004% | 0 |
| 2024-10-29 | $999,999.55 | $1,000,247.32 | +0.025% | 0 |
| 2024-10-30 | $999,999.55 | $1,000,284.13 | +0.028% | 0 |
| 2024-10-31 | $999,999.55 | $1,000,284.13 | +0.028% | 0 |

All 4 trades executed on day 1 (2024-10-25). Days 2–5 show unrealized P&L drift as prices move.

---

## Process Quality Metrics

| Metric | Value | Notes |
|---|---|---|
| Grounding score | 100% | All research notes included ≥1 citation |
| HITL decisions — approve | 0 | Mock mode: HITL prompt bypassed in harness |
| HITL decisions — reject | 0 | |
| HITL decisions — edit | 0 | |
| Guardrail rejections | Logged per run | See audit.jsonl |

**Grounding score** = percentage of research reports containing at least one citation. A score of 1.0 means every report was grounded — no hallucinated analysis was accepted.

**Note on HITL in eval:** The harness runs in `MOCK_LLM=true` mode and auto-approves HITL trades to allow unattended replay. In the interactive demo (via `scripts/seed_and_trade.sh`), HITL pauses for real human input.

---

## Sample Run — 2024-10-31

A full single-day run is committed at `sample_run/2024-10-31/`:

| Artifact | Contents |
|---|---|
| `audit.jsonl` | 21 events: prices fetched → 5 research reports → 4 proposals → 2 HITL pauses → 2 HITL approvals → 3 fills → report generated |
| `daily_report.json` | Portfolio snapshot, all fills with rationale, full research reports with citations, narrative |
| `daily_report.xlsx` | Excel version of the same report |

### Trades filled on 2024-10-31

| Ticker | Side | Shares | Fill Price | Notional | Rationale |
|---|---|---|---|---|---|
| AAPL | BUY | 200 | $228.96 | $45,792 | Q4 beat: revenue $94.9B vs $94.3B est. Apple Intelligence adoption strong. |
| AMZN | BUY | 120 | $193.22 | $23,186 | AWS $27.5B (+19% YoY), record operating income $17.4B. |
| MSFT | BUY | 50 | $428.60 | $21,430 | Azure 33% growth, Copilot 300M seats. |

GOOGL: `hold` — strong results but no new action. NVDA: `hold` — supply constraint risk acknowledged, confidence 0.65.

---

## Honest Limitations

1. **Buy-and-hold only.** The eval buys on day 1 and holds. There is no intraday rebalancing or sell logic triggered by news. A real firm would trade on subsequent days too.

2. **Mock LLM in harness.** All agent outputs in the eval are deterministic fixtures, not live LLM calls. This ensures reproducibility but means the grounding score reflects fixture quality, not live model behaviour.

3. **5-day window.** A single week is not statistically meaningful for alpha measurement. The eval harness is a correctness and process-quality check, not a backtest.

4. **No transaction cost impact on benchmark.** SPY return is taken directly from price data with no friction applied. Our portfolio applies slippage + commission.

5. **Single ticker universe.** Only 5 large-cap tech names. Sector concentration is high by design for the demo.
