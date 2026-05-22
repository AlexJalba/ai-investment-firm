"""Market data via yfinance — prices and sector info."""
from __future__ import annotations

from datetime import datetime

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


def get_prices(tickers: list[str], trade_date: str | None = None) -> dict[str, float]:
    from src.config import get_settings
    if get_settings().mock_llm and trade_date:
        from eval.data_loader import load_prices
        bundled = load_prices()
        result = {}
        for ticker in tickers:
            ticker_prices = bundled.get(ticker, {})
            # Use exact date or fall back to most recent available date
            price = ticker_prices.get(trade_date)
            if price is None:
                past_dates = sorted(d for d in ticker_prices if d <= trade_date)
                if past_dates:
                    price = ticker_prices[past_dates[-1]]
            if price:
                result[ticker] = price
        return result

    result = {}
    for ticker in tickers:
        try:
            result[ticker] = get_current_price(ticker)
        except Exception:
            pass
    return result


def get_sector(ticker: str) -> str:
    """Return the GICS sector for a ticker (cached per process)."""
    try:
        info = yf.Ticker(ticker).info
        return info.get("sector", "Unknown")
    except Exception:
        return "Unknown"
