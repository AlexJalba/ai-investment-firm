"""Tests for the paper trading engine."""
import os

import pytest

from src.portfolio.engine import PaperTradingEngine
from src.portfolio.models import Side, TradeOrder


@pytest.fixture
def engine(tmp_path):
    os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
    db = str(tmp_path / "test.db")
    import src.config as cfg_module
    import src.portfolio.database as db_module
    cfg_module._settings = None
    db_module._engine = None
    db_module._SessionLocal = None
    os.environ["STARTING_CAPITAL"] = "100000"
    return PaperTradingEngine(db_path=db)


def test_initial_state(engine):
    snap = engine.get_snapshot()
    assert snap.cash == 100_000.0
    assert snap.holdings == []
    assert snap.total_value == 100_000.0


def test_buy_creates_holding(engine):
    order = TradeOrder(ticker="AAPL", side=Side.BUY, shares=10, rationale="test")
    fill = engine.execute(order, market_price=150.0)

    assert fill.ticker == "AAPL"
    assert fill.shares == 10
    assert fill.fill_price > 150.0  # slippage applied on buy

    snap = engine.get_snapshot()
    assert len(snap.holdings) == 1
    assert snap.holdings[0].ticker == "AAPL"
    assert snap.holdings[0].shares == 10


def test_buy_then_sell(engine):
    buy = TradeOrder(ticker="AAPL", side=Side.BUY, shares=10, rationale="test")
    engine.execute(buy, market_price=150.0)

    sell = TradeOrder(ticker="AAPL", side=Side.SELL, shares=10, rationale="take profit")
    engine.execute(sell, market_price=160.0)

    snap = engine.get_snapshot()
    assert snap.holdings == []
    assert snap.realized_pnl > 0


def test_insufficient_cash_raises(engine):
    order = TradeOrder(ticker="AAPL", side=Side.BUY, shares=10_000, rationale="too big")
    with pytest.raises(ValueError, match="Insufficient cash"):
        engine.execute(order, market_price=150.0)


def test_sell_without_holding_raises(engine):
    order = TradeOrder(ticker="NVDA", side=Side.SELL, shares=5, rationale="short")
    with pytest.raises(ValueError):
        engine.execute(order, market_price=500.0)
