"""Portfolio Manager Agent — translates research into sized trade proposals."""
from __future__ import annotations

import json

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from src.config import get_settings
from src.guardrails.validators import TradeProposal, check_position_size
from src.observability.logger import audit, get_logger, get_tracer
from src.portfolio.models import PortfolioSnapshot

logger = get_logger(__name__)
tracer = get_tracer("portfolio_manager")

SYSTEM_PROMPT = """You are the Portfolio Manager of an AI-run investment firm.
Given research reports and the current portfolio state, decide which trades to make.

Rules:
- Propose only trades that are supported by research evidence.
- Respect position sizing: no single position should exceed 10% of total portfolio value.
- Size positions based on confidence: high confidence (>0.7) → up to 5% of portfolio; medium → up to 3%.
- You must cite the research reports when proposing a trade.
- Return a JSON array of trade proposals. Each element:
  {
    "ticker": "AAPL",
    "side": "BUY" or "SELL",
    "shares": <integer>,
    "rationale": "...",
    "citations": ["research source 1", ...],
    "confidence": 0.0-1.0
  }
- Return an empty array [] if there are no conviction trades today.
"""


def run_portfolio_manager(
    research_reports: list[dict],
    snapshot: PortfolioSnapshot,
    market_prices: dict[str, float],
) -> list[dict]:
    cfg = get_settings()

    if cfg.mock_llm:
        from eval.fixtures import TRADE_PROPOSALS
        tickers_in_research = {r["ticker"] for r in research_reports}
        proposals = []
        for p in TRADE_PROPOSALS:
            if p["ticker"] not in tickers_in_research:
                continue
            price = market_prices.get(p["ticker"], 0)
            if price:
                try:
                    check_position_size(p["ticker"], p["shares"], price, snapshot.total_value)
                    proposals.append(p)
                except Exception:
                    pass
        audit("pm.proposals_generated", audit_log_path=cfg.audit_log_path,
              count=len(proposals), tickers=[p["ticker"] for p in proposals])
        return proposals

    with tracer.start_as_current_span("portfolio_manager"):
        # Build context for the PM
        portfolio_context = _format_portfolio(snapshot, market_prices)
        research_context = json.dumps(research_reports, indent=2)

        llm = ChatAnthropic(
            model=cfg.pm_model,
            api_key=cfg.anthropic_api_key,
            max_tokens=2048,
        )

        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(
                content=(
                    f"Portfolio state:\n{portfolio_context}\n\n"
                    f"Research reports:\n{research_context}\n\n"
                    f"Market prices: {json.dumps(market_prices)}\n\n"
                    "Propose trades as a JSON array."
                )
            ),
        ]

        response = llm.invoke(messages)
        raw = response.content

        try:
            if "```" in raw:
                raw = raw.split("```")[1].lstrip("json").strip()
            proposals_raw = json.loads(raw)
            if not isinstance(proposals_raw, list):
                proposals_raw = [proposals_raw]
        except Exception as e:
            logger.warning("pm.parse_failed", error=str(e))
            return []

        proposals = []
        for p in proposals_raw:
            try:
                tp = TradeProposal.model_validate(p)
                # Apply position-size guardrail
                price = market_prices.get(tp.ticker, 0)
                if price:
                    check_position_size(tp.ticker, tp.shares, price, snapshot.total_value)
                proposals.append(tp.model_dump())
            except Exception as e:
                logger.warning("pm.proposal_rejected", error=str(e), proposal=p)

        audit(
            "pm.proposals_generated",
            audit_log_path=cfg.audit_log_path,
            count=len(proposals),
            tickers=[p["ticker"] for p in proposals],
        )
        return proposals


def _format_portfolio(snapshot: PortfolioSnapshot, prices: dict[str, float]) -> str:
    lines = [
        f"Cash: ${snapshot.cash:,.2f}",
        f"Total value: ${snapshot.total_value:,.2f}",
        f"Realized P&L: ${snapshot.realized_pnl:,.2f}",
        "Holdings:",
    ]
    for h in snapshot.holdings:
        price = prices.get(h.ticker, h.cost_basis)
        mv = h.shares * price
        pnl = (price - h.cost_basis) * h.shares
        lines.append(
            f"  {h.ticker}: {h.shares:.0f} sh @ ${h.cost_basis:.2f} cost | "
            f"mkt ${price:.2f} | MV ${mv:,.0f} | P&L ${pnl:+,.0f}"
        )
    return "\n".join(lines)
