"""Input/output validators, hallucination checks, and prompt-injection defenses."""
from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, field_validator

from src.config import get_settings
from src.observability.logger import audit, get_logger
from src.portfolio.models import Side, TradeOrder

logger = get_logger(__name__)

# ── Prompt injection defense ───────────────────────────────────────────────────

_INJECTION_PATTERNS = [
    r"ignore (all |previous |above |prior )?instructions",
    r"system prompt",
    r"you are now",
    r"disregard",
    r"do not follow",
    r"pretend (you are|to be)",
    r"jailbreak",
    r"<\|.*?\|>",          # token-like delimiters
    r"\{\{.*?\}\}",        # template injection
]

_INJECTION_RE = re.compile("|".join(_INJECTION_PATTERNS), re.IGNORECASE)


def sanitize_web_text(text: str) -> str:
    """Strip content that looks like prompt injection from web-sourced text."""
    if _INJECTION_RE.search(text):
        logger.warning("guardrail.injection_detected", snippet=text[:120])
        audit("guardrail.injection_blocked", snippet=text[:120], audit_log_path=get_settings().audit_log_path)
        # Remove the offending sentences rather than the whole document
        sentences = re.split(r"(?<=[.!?])\s+", text)
        clean = [s for s in sentences if not _INJECTION_RE.search(s)]
        return " ".join(clean)
    return text


# ── Output schema validator ────────────────────────────────────────────────────

class ResearchOutput(BaseModel):
    ticker: str
    summary: str
    sentiment: str          # bullish / bearish / neutral
    confidence: float       # 0–1
    citations: list[str]    # must be non-empty for grounded decisions
    recommendation: str     # buy / sell / hold

    @field_validator("ticker")
    @classmethod
    def ticker_upper(cls, v: str) -> str:
        return v.upper()

    @field_validator("confidence")
    @classmethod
    def clamp_confidence(cls, v: float) -> float:
        return max(0.0, min(1.0, v))

    @field_validator("citations")
    @classmethod
    def require_citations(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("Citations must be non-empty — no hallucinated claims allowed")
        return v

    @field_validator("sentiment")
    @classmethod
    def valid_sentiment(cls, v: str) -> str:
        if v.lower() not in {"bullish", "bearish", "neutral"}:
            raise ValueError(f"Invalid sentiment: {v}")
        return v.lower()


class TradeProposal(BaseModel):
    ticker: str
    side: Side
    shares: float
    rationale: str
    citations: list[str]
    confidence: float

    @field_validator("citations")
    @classmethod
    def require_citations(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("Trade proposals must cite evidence")
        return v


# ── Risk / position-size guardrails ───────────────────────────────────────────

class GuardrailViolation(Exception):
    pass


def check_position_size(
    ticker: str,
    shares: float,
    price: float,
    portfolio_value: float,
) -> None:
    cfg = get_settings()
    notional = shares * price
    pct = notional / portfolio_value if portfolio_value > 0 else 1.0
    if pct > cfg.max_single_position_pct:
        raise GuardrailViolation(
            f"Position size {pct:.1%} exceeds limit {cfg.max_single_position_pct:.1%} for {ticker}"
        )


def check_daily_loss(current_value: float, start_of_day_value: float) -> None:
    cfg = get_settings()
    loss_pct = (start_of_day_value - current_value) / start_of_day_value
    if loss_pct > cfg.daily_loss_limit_pct:
        raise GuardrailViolation(
            f"Daily loss {loss_pct:.1%} exceeds limit {cfg.daily_loss_limit_pct:.1%} — trading halted"
        )


def requires_hitl(shares: float, price: float) -> bool:
    cfg = get_settings()
    return (shares * price) > cfg.trade_notional_hitl_threshold
