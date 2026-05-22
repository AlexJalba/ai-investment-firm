"""LangGraph state schema for the trading day graph."""
from __future__ import annotations

from typing import Annotated

from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class TradingDayState(TypedDict):
    # ── Shared context ─────────────────────────────────────────────────────────
    trade_date: str                          # ISO date string
    tickers: list[str]                       # universe of tickers under consideration
    market_prices: dict[str, float]          # ticker → latest price

    # ── Research output ────────────────────────────────────────────────────────
    research_reports: list[dict]             # one per ticker

    # ── Portfolio state ────────────────────────────────────────────────────────
    portfolio_snapshot: dict | None       # serialized PortfolioSnapshot
    start_of_day_value: float

    # ── Proposed trades ────────────────────────────────────────────────────────
    trade_proposals: list[dict]              # list of TradeOrder dicts

    # ── Risk Committee ─────────────────────────────────────────────────────────
    pending_hitl: list[dict]                 # trades awaiting human approval
    hitl_decisions: list[dict]               # {"trade": ..., "decision": approve/reject/edit, "notes": ...}

    # ── Execution results ──────────────────────────────────────────────────────
    filled_trades: list[dict]                # list of FillResult dicts

    # ── Messages / audit trail ────────────────────────────────────────────────
    messages: Annotated[list, add_messages]

    # ── Control flow ──────────────────────────────────────────────────────────
    halt: bool                               # True if daily loss limit hit
    errors: list[str]
