"""Main LangGraph trading day graph."""
from __future__ import annotations

import uuid
from datetime import date

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from src.agents.execution_agent import run_execution_agent
from src.agents.portfolio_manager_agent import run_portfolio_manager
from src.agents.reporting_agent import run_reporting_agent
from src.agents.research_agent import run_research_agent
from src.agents.risk_agent import run_risk_agent
from src.config import get_settings
from src.graph.state import TradingDayState
from src.hitl.risk_committee import run_risk_committee
from src.market_data.prices import get_prices
from src.observability.logger import audit, configure_logging, get_logger, get_tracer
from src.portfolio.engine import PaperTradingEngine
from src.portfolio.models import PortfolioSnapshot
from src.rag.store import RAGStore

logger = get_logger(__name__)
tracer = get_tracer("trading_graph")

# ── Node functions ─────────────────────────────────────────────────────────────

def node_fetch_prices(state: TradingDayState) -> dict:
    tickers = state["tickers"] + [get_settings().benchmark_ticker]
    prices = get_prices(tickers, trade_date=state["trade_date"])
    logger.info("node.fetch_prices", tickers=list(prices.keys()))
    return {
        "market_prices": prices,
        "messages": [AIMessage(content=f"Fetched prices for {list(prices.keys())}", name="system")],
    }


def node_research(state: TradingDayState) -> dict:
    rag = RAGStore()
    reports = []
    for ticker in state["tickers"]:
        report = run_research_agent(ticker, rag)
        reports.append(report)
    return {
        "research_reports": reports,
        "messages": [AIMessage(content=f"Research complete for {[r['ticker'] for r in reports]}", name="research_agent")],
    }


def node_portfolio_manager(state: TradingDayState) -> dict:
    engine = PaperTradingEngine()
    snapshot = engine.get_snapshot(state["market_prices"])
    proposals = run_portfolio_manager(state["research_reports"], snapshot, state["market_prices"])
    return {
        "portfolio_snapshot": snapshot.model_dump(),
        "trade_proposals": proposals,
        "messages": [AIMessage(content=f"Proposed {len(proposals)} trade(s)", name="portfolio_manager")],
    }


def node_risk(state: TradingDayState) -> dict:
    if not state.get("trade_proposals"):
        return {"pending_hitl": [], "trade_proposals": []}

    snap_data = state.get("portfolio_snapshot", {})
    snapshot = PortfolioSnapshot.model_validate(snap_data) if snap_data else PaperTradingEngine().get_snapshot()
    start_value = state.get("start_of_day_value", snapshot.total_value)

    approved, hitl_pending = run_risk_agent(
        state["trade_proposals"], snapshot, state["market_prices"], start_value
    )

    halt = not approved and not hitl_pending and bool(state.get("trade_proposals"))
    return {
        "trade_proposals": approved,
        "pending_hitl": hitl_pending,
        "halt": halt,
        "messages": [AIMessage(
            content=f"Risk: {len(approved)} approved, {len(hitl_pending)} pending HITL",
            name="risk_agent",
        )],
    }


def node_hitl(state: TradingDayState) -> dict:
    """Interrupt point — human reviews pending trades, then resumes."""
    pending = state.get("pending_hitl", [])
    if not pending:
        return {"hitl_decisions": []}

    approved = run_risk_committee(pending, state["market_prices"])
    # Merge HITL-approved trades back into the main approved list
    all_approved = list(state.get("trade_proposals", [])) + approved
    return {
        "trade_proposals": all_approved,
        "hitl_decisions": [{"count": len(approved)}],
        "messages": [AIMessage(
            content=f"Risk Committee approved {len(approved)}/{len(pending)} HITL trades",
            name="risk_committee",
        )],
    }


def node_execution(state: TradingDayState) -> dict:
    engine = PaperTradingEngine()
    trace_id = str(uuid.uuid4())[:8]
    fills = run_execution_agent(state.get("trade_proposals", []), state["market_prices"], engine, trace_id, trade_date=state["trade_date"])
    return {
        "filled_trades": fills,
        "messages": [AIMessage(content=f"Executed {len(fills)} fill(s)", name="execution_agent")],
    }


def node_reporting(state: TradingDayState) -> dict:
    engine = PaperTradingEngine()
    snapshot = engine.get_snapshot(state["market_prices"])

    cfg = get_settings()
    benchmark_ticker = cfg.benchmark_ticker
    prices = state["market_prices"]
    start = state.get("start_of_day_value", snapshot.total_value)

    # Simple benchmark return approximation using today's price movement
    benchmark_pct = None
    if benchmark_ticker in prices:
        pass  # Would need open price for accurate calc; omit for paper trading

    result = run_reporting_agent(
        trade_date=state["trade_date"],
        snapshot=snapshot,
        start_of_day_value=start,
        filled_trades=state.get("filled_trades", []),
        research_reports=state.get("research_reports", []),
        benchmark_pct=benchmark_pct,
    )
    return {
        "messages": [AIMessage(content=f"Reports generated: {result['excel']}", name="reporting_agent")],
    }


def should_halt(state: TradingDayState) -> str:
    if state.get("halt"):
        return "reporting"
    return "hitl"


# ── Graph assembly ─────────────────────────────────────────────────────────────

def build_graph(checkpointer=None):
    g = StateGraph(TradingDayState)

    g.add_node("fetch_prices", node_fetch_prices)
    g.add_node("research", node_research)
    g.add_node("portfolio_manager", node_portfolio_manager)
    g.add_node("risk", node_risk)
    g.add_node("hitl", node_hitl)
    g.add_node("execution", node_execution)
    g.add_node("reporting", node_reporting)

    g.set_entry_point("fetch_prices")
    g.add_edge("fetch_prices", "research")
    g.add_edge("research", "portfolio_manager")
    g.add_edge("portfolio_manager", "risk")
    g.add_conditional_edges("risk", should_halt, {"hitl": "hitl", "reporting": "reporting"})
    g.add_edge("hitl", "execution")
    g.add_edge("execution", "reporting")
    g.add_edge("reporting", END)

    return g.compile(checkpointer=checkpointer or MemorySaver(), interrupt_before=["hitl"])


def run_trading_day(
    tickers: list[str],
    trade_date: str | None = None,
    thread_id: str = "default",
) -> TradingDayState:
    cfg = get_settings()
    configure_logging(cfg.log_level, cfg.audit_log_path, cfg.otlp_endpoint)

    graph = build_graph()
    trade_date = trade_date or date.today().isoformat()

    engine = PaperTradingEngine()
    snapshot = engine.get_snapshot()

    initial_state: TradingDayState = {
        "trade_date": trade_date,
        "tickers": [t.upper() for t in tickers],
        "market_prices": {},
        "research_reports": [],
        "portfolio_snapshot": None,
        "start_of_day_value": snapshot.total_value,
        "trade_proposals": [],
        "pending_hitl": [],
        "hitl_decisions": [],
        "filled_trades": [],
        "messages": [HumanMessage(content=f"Start trading day {trade_date}")],
        "halt": False,
        "errors": [],
    }

    config = {"configurable": {"thread_id": thread_id}}

    with tracer.start_as_current_span("trading_day") as span:
        span.set_attribute("trade_date", trade_date)

        # Run until HITL interrupt point
        state = graph.invoke(initial_state, config)

        # Always resume — the graph always pauses at interrupt_before=["hitl"].
        # If there are pending HITL trades, the human reviews them first.
        # If there are none, we still need to resume so execution and reporting run.
        pending = state.get("pending_hitl", [])
        if pending:
            audit("hitl.paused", trade_date=trade_date, count=len(pending), audit_log_path=cfg.audit_log_path)
        state = graph.invoke(None, config)

    return state
