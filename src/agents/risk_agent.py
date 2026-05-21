"""Risk Agent — validates proposals against risk limits, flags HITL trades."""
from __future__ import annotations

import json

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from src.config import get_settings
from src.guardrails.validators import (
    GuardrailViolation,
    check_daily_loss,
    check_position_size,
    requires_hitl,
)
from src.observability.logger import audit, get_logger, get_tracer
from src.portfolio.models import PortfolioSnapshot

logger = get_logger(__name__)
tracer = get_tracer("risk_agent")

SYSTEM_PROMPT = """You are the Chief Risk Officer of an AI investment firm.
Review each proposed trade and assess its risk.

For each trade, return a JSON object:
{
  "ticker": "AAPL",
  "approved": true/false,
  "risk_flags": ["...", "..."],       // list of concerns, can be empty
  "requires_hitl": true/false,        // true if human approval needed
  "adjusted_shares": <number or null> // suggest a smaller size if you see concentration risk
}

Reject a trade (approved=false) if:
- It would push a single position over 10% of portfolio
- The firm would exceed 30% in one sector
- Confidence < 0.3 with no strong evidence
- The rationale is vague or uncited

Flag for human review (requires_hitl=true) if:
- Notional value > $50,000
- Confidence 0.3–0.5
- First trade in a new ticker with no prior holding
"""


class RiskAssessment:
    approved: bool
    risk_flags: list[str]
    requires_hitl: bool
    adjusted_shares: float | None


def run_risk_agent(
    proposals: list[dict],
    snapshot: PortfolioSnapshot,
    market_prices: dict[str, float],
    start_of_day_value: float,
) -> tuple[list[dict], list[dict]]:
    """Returns (approved_trades, hitl_pending_trades)."""
    cfg = get_settings()

    with tracer.start_as_current_span("risk_agent") as span:
        # Hard guardrail: daily loss limit
        try:
            check_daily_loss(snapshot.total_value, start_of_day_value)
        except GuardrailViolation as e:
            audit("risk.daily_loss_halt", reason=str(e), audit_log_path=cfg.audit_log_path)
            logger.error("risk.daily_loss_halt", reason=str(e))
            return [], []

        if not proposals:
            return [], []

        llm = ChatAnthropic(
            model=cfg.risk_model,
            api_key=cfg.anthropic_api_key,
            max_tokens=2048,
        )

        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(
                content=(
                    f"Portfolio value: ${snapshot.total_value:,.2f}\n"
                    f"Cash: ${snapshot.cash:,.2f}\n"
                    f"Holdings: {json.dumps([h.__dict__ if hasattr(h, '__dict__') else h for h in snapshot.holdings])}\n"
                    f"Market prices: {json.dumps(market_prices)}\n\n"
                    f"Proposed trades:\n{json.dumps(proposals, indent=2)}\n\n"
                    "Return a JSON array with one assessment per trade."
                )
            ),
        ]

        response = llm.invoke(messages)
        raw = response.content

        try:
            if "```" in raw:
                raw = raw.split("```")[1].lstrip("json").strip()
            assessments = json.loads(raw)
            if isinstance(assessments, dict):
                assessments = [assessments]
        except Exception as e:
            logger.warning("risk.parse_failed", error=str(e))
            assessments = []

        approved = []
        hitl_pending = []

        for proposal, assessment in zip(proposals, assessments):
            ticker = proposal["ticker"]
            price = market_prices.get(ticker, 0)
            shares = assessment.get("adjusted_shares") or proposal["shares"]

            # Hard-code notional check regardless of LLM output
            hitl_flag = requires_hitl(shares, price)

            if not assessment.get("approved", False):
                audit(
                    "risk.rejected",
                    audit_log_path=cfg.audit_log_path,
                    ticker=ticker,
                    flags=assessment.get("risk_flags", []),
                )
                logger.info("risk.rejected", ticker=ticker, flags=assessment.get("risk_flags", []))
                continue

            enriched = {**proposal, "shares": shares, "risk_flags": assessment.get("risk_flags", [])}

            if hitl_flag or assessment.get("requires_hitl", False):
                hitl_pending.append(enriched)
                audit("risk.hitl_required", audit_log_path=cfg.audit_log_path, ticker=ticker, notional=shares * price)
            else:
                approved.append(enriched)
                audit("risk.approved", audit_log_path=cfg.audit_log_path, ticker=ticker)

        logger.info("risk.summary", approved=len(approved), hitl=len(hitl_pending))
        return approved, hitl_pending
