"""Market data via yfinance — prices, OHLCV, sector info."""
from __future__ import annotations

import functools
from datetime import date, datetime, timedelta
from typing import Optional

import pandas as pd
import yfinance as yf

from src.observability.logger import get_logger

logger = get_logger(__name__)

# Simple in-process price cache (TTL ~60s)
_price_cache: dict[str, tuple[float, datetime]] = {}
_CACHE_TTL = 60  # seconds


def get_current_price(ticker: str) -> float:
    """Return the latest available price for a ticker."""
    now = datetime.utcnow()
    if ticker in _price_cache:
        price, ts = _price_cache[ticker]
        if (now - ts).total_seconds() < _CACHE_TTL:
            return price

    try:
        t = yf.Ticker(ticker)
        info = t.fast_info
        price = float(info.last_price or info.previous_close)
        _price_cache[ticker] = (price, now)
        return price
    except Exception as e:
        logger.warning("price.fetch_failed", ticker=ticker, error=str(e))
        raise


def get_prices(tickers: list[str]) -> dict[str, float]:
    result = {}
    for ticker in tickers:
        try:
            result[ticker] = get_current_price(ticker)
        except Exception:
            pass
    return result


def get_historical_ohlcv(
    ticker: str,
    start: date,
    end: date,
    interval: str = "1d",
) -> pd.DataFrame:
    """Fetch OHLCV data for a date range. Returns a DataFrame with DatetimeIndex."""
    df = yf.download(ticker, start=start, end=end, interval=interval, progress=False, auto_adjust=True)
    if df.empty:
        logger.warning("historical.empty", ticker=ticker, start=start, end=end)
    return df


def get_sector(ticker: str) -> str:
    """Return the GICS sector for a ticker (cached per process)."""
    try:
        info = yf.Ticker(ticker).info
        return info.get("sector", "Unknown")
    except Exception:
        return "Unknown"


def is_market_open() -> bool:
    """Rough check — US equities trade 9:30–16:00 ET Mon–Fri."""
    from datetime import timezone
    import zoneinfo

    et = zoneinfo.ZoneInfo("America/New_York")
    now = datetime.now(et)
    if now.weekday() >= 5:  # Saturday or Sunday
        return False
    market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
    market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)
    return market_open <= now <= market_close
