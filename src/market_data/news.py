"""News ingestion — yfinance news for RAG grounding."""
from __future__ import annotations

from datetime import datetime

import yfinance as yf

from src.observability.logger import get_logger

logger = get_logger(__name__)


def fetch_ticker_news(ticker: str, max_items: int = 10) -> list[dict]:
    """Fetch recent news for a ticker via yfinance."""
    items = []
    try:
        news = yf.Ticker(ticker).news or []
        for article in news[:max_items]:
            items.append(
                {
                    "ticker": ticker,
                    "title": article.get("title", ""),
                    "summary": article.get("summary", article.get("title", "")),
                    "url": article.get("link", ""),
                    "published": datetime.fromtimestamp(article.get("providerPublishTime", 0)).isoformat(),
                    "source": article.get("publisher", ""),
                }
            )
    except Exception as e:
        logger.warning("news.fetch_failed", ticker=ticker, error=str(e))
    return items


def fetch_all_news(tickers: list[str]) -> list[dict]:
    """Aggregate news from all sources for a list of tickers."""
    articles = []
    for ticker in tickers:
        articles.extend(fetch_ticker_news(ticker))
    return articles
