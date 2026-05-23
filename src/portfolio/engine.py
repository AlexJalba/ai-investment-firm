"""Paper trading engine — fills orders with slippage + commission, updates state."""
from __future__ import annotations

from datetime import UTC, datetime, timezone, timedelta

from src.config import get_settings
from src.observability.logger import audit, get_logger
from src.portfolio.database import get_session
from src.portfolio.models import (
    FillResult,
    Holding,
    HoldingORM,
    PortfolioSnapshot,
    PortfolioStateORM,
    Side,
    TradeOrder,
    TradeORM,
)

logger = get_logger(__name__)


class PaperTradingEngine:
    """Executes paper trades with slippage/commission simulation and SQLite persistence."""

    def __init__(self, db_path: str = "./data/portfolio.db") -> None:
        self.db_path = db_path
        self.cfg = get_settings()
        self._ensure_initial_state()

    def _ensure_initial_state(self) -> None:
        with get_session(self.db_path) as session:
            if session.query(PortfolioStateORM).count() == 0:
                session.add(
                    PortfolioStateORM(
                        as_of=datetime.now(UTC),
                        cash=self.cfg.starting_capital,
                        total_value=self.cfg.starting_capital,
                    )
                )
                session.commit()
                logger.info("portfolio.initialized", cash=self.cfg.starting_capital)

    def get_snapshot(self, market_prices: dict[str, float] | None = None) -> PortfolioSnapshot:
        with get_session(self.db_path) as session:
            state = session.query(PortfolioStateORM).order_by(PortfolioStateORM.id.desc()).first()
            holdings_orm = session.query(HoldingORM).all()

        holdings = [
            Holding(
                ticker=h.ticker,
                shares=h.shares,
                cost_basis=h.cost_basis,
                sector=h.sector or "Unknown",
            )
            for h in holdings_orm
        ]

        # Recompute unrealized P&L with live prices if provided
        unrealized = 0.0
        total_market_value = state.cash
        for h in holdings:
            price = (market_prices or {}).get(h.ticker, h.cost_basis)
            mv = h.shares * price
            unrealized += (price - h.cost_basis) * h.shares
            total_market_value += mv

        return PortfolioSnapshot(
            as_of=state.as_of,
            cash=state.cash,
            holdings=holdings,
            realized_pnl=state.realized_pnl,
            unrealized_pnl=unrealized,
            total_value=total_market_value,
        )

    def execute(self, order: TradeOrder, market_price: float, trade_date: str | None = None) -> FillResult:
        """Simulate a fill with slippage and commission, then persist."""
        # Use trade_date for the date part, current wall-clock time (UTC+2) for the time part
        il_tz = timezone(timedelta(hours=2))
        now_il = datetime.now(il_tz)
        if trade_date:
            from datetime import date as date_type
            d = date_type.fromisoformat(trade_date)
            as_of = datetime(d.year, d.month, d.day, now_il.hour, now_il.minute, now_il.second, tzinfo=il_tz)
        else:
            as_of = now_il
        slippage_mult = 1 + (self.cfg.slippage_bps / 10_000) * (1 if order.side == Side.BUY else -1)
        fill_price = market_price * slippage_mult
        slippage_amt = abs(fill_price - market_price) * order.shares
        commission = order.shares * self.cfg.commission_per_share
        notional = fill_price * order.shares

        with get_session(self.db_path) as session:
            state = session.query(PortfolioStateORM).order_by(PortfolioStateORM.id.desc()).first()

            if order.side == Side.BUY:
                cost = notional + commission
                if state.cash < cost:
                    raise ValueError(f"Insufficient cash: need {cost:.2f}, have {state.cash:.2f}")
                state.cash -= cost
                self._update_holding(session, order.ticker, order.shares, fill_price)
            else:
                realized = self._close_holding(session, order.ticker, order.shares, fill_price)
                state.cash += notional - commission
                state.realized_pnl += realized

            state.as_of = as_of
            state.total_value = state.cash + self._holdings_value(session, {order.ticker: fill_price})

            session.add(
                TradeORM(
                    executed_at=as_of,
                    ticker=order.ticker,
                    side=order.side.value,
                    shares=order.shares,
                    price=fill_price,
                    notional=notional,
                    commission=commission,
                    slippage=slippage_amt,
                    rationale=order.rationale,
                    agent_trace_id=order.agent_trace_id,
                )
            )
            session.commit()

        fill = FillResult(
            ticker=order.ticker,
            side=order.side,
            shares=order.shares,
            fill_price=fill_price,
            notional=notional,
            commission=commission,
            slippage=slippage_amt,
            executed_at=as_of,
        )
        audit(
            "trade.filled",
            audit_log_path=self.cfg.audit_log_path,
            ticker=order.ticker,
            side=order.side.value,
            shares=order.shares,
            fill_price=fill_price,
            notional=notional,
            commission=commission,
            rationale=order.rationale,
            agent_trace_id=order.agent_trace_id,
        )
        logger.info("trade.filled", **fill.model_dump())
        return fill

    def _update_holding(self, session, ticker: str, shares: float, price: float) -> None:
        h = session.query(HoldingORM).filter_by(ticker=ticker).first()
        if h:
            total_cost = (h.shares * h.cost_basis) + (shares * price)
            h.shares += shares
            h.cost_basis = total_cost / h.shares
        else:
            session.add(HoldingORM(ticker=ticker, shares=shares, cost_basis=price))

    def _close_holding(self, session, ticker: str, shares: float, fill_price: float) -> float:
        h = session.query(HoldingORM).filter_by(ticker=ticker).first()
        if not h or h.shares < shares:
            raise ValueError(f"Cannot sell {shares} shares of {ticker}: only have {getattr(h, 'shares', 0)}")
        realized = (fill_price - h.cost_basis) * shares
        h.shares -= shares
        if h.shares < 1e-6:
            session.delete(h)
        return realized

    def _holdings_value(self, session, prices: dict[str, float]) -> float:
        total = 0.0
        for h in session.query(HoldingORM).all():
            total += h.shares * prices.get(h.ticker, h.cost_basis)
        return total
