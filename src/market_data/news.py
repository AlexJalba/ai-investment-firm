"""News ingestion — RSS feeds and yfinance news for RAG grounding."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

import feedparser
import yfinance as yf

from src.observability.logger import get_logger

logger = get_logger(__name__)

RSS_FEEDS = [
    "https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US",
    "https://www.marketwatch.com/rss/topstories",
]


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


def fetch_rss_news(feed_url: str, max_items: int = 20) -> list[dict]:
    """Fetch and parse an RSS feed."""
    items = []
    try:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries[:max_items]:
            items.append(
                {
                    "ticker": None,
                    "title": entry.get("title", ""),
                    "summary": entry.get("summary", entry.get("title", "")),
                    "url": entry.get("link", ""),
                    "published": entry.get("published", ""),
                    "source": feed.feed.get("title", feed_url),
                }
            )
    except Exception as e:
        logger.warning("rss.fetch_failed", url=feed_url, error=str(e))
    return items


def fetch_all_news(tickers: list[str]) -> list[dict]:
    """Aggregate news from all sources for a list of tickers."""
    articles = []
    for ticker in tickers:
        articles.extend(fetch_ticker_news(ticker))
    return articles
