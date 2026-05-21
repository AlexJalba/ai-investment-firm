"""Loaders for bundled sample data — enables offline eval runs."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

_DATA_DIR = Path(__file__).parent / "sample_data"


def load_prices(csv_name: str = "close_prices_oct2024.csv") -> dict[str, dict[str, float]]:
    """
    Load bundled OHLCV close prices.
    Returns {ticker: {date_str: price}} for offline price lookups.
    """
    df = pd.read_csv(_DATA_DIR / csv_name, index_col=0, parse_dates=True)
    result: dict[str, dict[str, float]] = {}
    for ticker in df.columns:
        result[ticker] = {
            d.strftime("%Y-%m-%d"): float(v)
            for d, v in df[ticker].dropna().items()
        }
    return result


def load_news(json_name: str = "news_oct2024.json") -> list[dict]:
    """Load bundled news articles ready for rag_store.ingest()."""
    with open(_DATA_DIR / json_name) as f:
        return json.load(f)


def get_price_for_date(
    ticker: str,
    date_str: str,
    prices: dict[str, dict[str, float]] | None = None,
) -> float | None:
    """Look up the close price for a ticker on a specific date from the bundled data."""
    if prices is None:
        prices = load_prices()
    return prices.get(ticker, {}).get(date_str)
