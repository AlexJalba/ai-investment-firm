"""Execution Agent — converts approved proposals to fills via the paper engine."""
from __future__ import annotations

from src.config import get_settings
from src.observability.logger import audit, get_logger, get_tracer
from src.portfolio.engine import PaperTradingEngine
from src.portfolio.models import FillResult, Side, TradeOrder

logger = get_logger(__name__)
tracer = get_tracer("execution_agent")


def run_execution_agent(
    approved_trades: list[dict],
    market_prices: dict[str, float],
    engine: PaperTradingEngine,
    trace_id: str = "",
) -> list[dict]:
    """Execute approved trades and return fill results."""
    cfg = get_settings()
    fills = []

    with tracer.start_as_current_span("execution_agent") as span:
        span.set_attribute("trade_count", len(approved_trades))

        for proposal in approved_trades:
            ticker = proposal["ticker"]
            price = market_prices.get(ticker)
            if price is None:
                logger.warning("execution.no_price", ticker=ticker)
                continue

            order = TradeOrder(
                ticker=ticker,
                side=Side(proposal["side"]),
                shares=float(proposal["shares"]),
                rationale=proposal.get("rationale", ""),
                agent_trace_id=trace_id,
            )

            try:
                fill = engine.execute(order, price)
                fills.append(fill.model_dump())
                logger.info(
                    "execution.filled",
                    ticker=ticker,
                    side=order.side.value,
                    shares=order.shares,
                    fill_price=fill.fill_price,
                )
            except Exception as e:
                logger.error("execution.failed", ticker=ticker, error=str(e))
                audit(
                    "execution.failed",
                    audit_log_path=cfg.audit_log_path,
                    ticker=ticker,
                    error=str(e),
                )

    return fills
