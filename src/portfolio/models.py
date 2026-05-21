"""Domain models for the paper portfolio."""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator
from sqlalchemy import Column, Date, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# ── SQLAlchemy ORM ─────────────────────────────────────────────────────────────

class PortfolioStateORM(Base):
    __tablename__ = "portfolio_state"
    id = Column(Integer, primary_key=True)
    as_of = Column(DateTime, nullable=False)
    cash = Column(Float, nullable=False)
    total_value = Column(Float, nullable=False)
    realized_pnl = Column(Float, default=0.0)
    unrealized_pnl = Column(Float, default=0.0)


class HoldingORM(Base):
    __tablename__ = "holdings"
    id = Column(Integer, primary_key=True)
    ticker = Column(String(16), nullable=False, index=True)
    shares = Column(Float, nullable=False)
    cost_basis = Column(Float, nullable=False)  # average cost per share
    sector = Column(String(64))


class TradeORM(Base):
    __tablename__ = "trades"
    id = Column(Integer, primary_key=True)
    executed_at = Column(DateTime, nullable=False)
    ticker = Column(String(16), nullable=False)
    side = Column(String(4), nullable=False)  # BUY / SELL
    shares = Column(Float, nullable=False)
    price = Column(Float, nullable=False)       # fill price (after slippage)
    notional = Column(Float, nullable=False)
    commission = Column(Float, nullable=False)
    slippage = Column(Float, nullable=False)
    rationale = Column(Text)
    agent_trace_id = Column(String(64))


class DailyPnLORM(Base):
    __tablename__ = "daily_pnl"
    id = Column(Integer, primary_key=True)
    trade_date = Column(Date, nullable=False, unique=True)
    start_value = Column(Float, nullable=False)
    end_value = Column(Float, nullable=False)
    pnl = Column(Float, nullable=False)
    pnl_pct = Column(Float, nullable=False)
    benchmark_pct = Column(Float)


# ── Pydantic schemas ────────────────────────────────────────────────────────────

class Side(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


class TradeOrder(BaseModel):
    ticker: str
    side: Side
    shares: float = Field(gt=0)
    limit_price: float | None = None
    rationale: str = ""
    agent_trace_id: str = ""

    @model_validator(mode="after")
    def ticker_upper(self) -> TradeOrder:
        self.ticker = self.ticker.upper()
        return self


class FillResult(BaseModel):
    ticker: str
    side: Side
    shares: float
    fill_price: float
    notional: float
    commission: float
    slippage: float
    executed_at: datetime


class Holding(BaseModel):
    ticker: str
    shares: float
    cost_basis: float
    sector: str = "Unknown"

    @property
    def market_value(self) -> float:
        return self.shares * self.cost_basis  # overridden with live price elsewhere


class PortfolioSnapshot(BaseModel):
    as_of: datetime
    cash: float
    holdings: list[Holding]
    realized_pnl: float
    unrealized_pnl: float
    total_value: float

    @property
    def invested_value(self) -> float:
        return self.total_value - self.cash
