# Sample Data

Pre-bundled data for reproducible eval runs and CI — no external API calls needed.

## Files

| File | Description |
|------|-------------|
| `close_prices_oct2024.csv` | Real daily close prices for AAPL, MSFT, GOOGL, AMZN, NVDA, SPY — October 2024 (22 trading days, sourced from Yahoo Finance) |
| `news_oct2024.json` | 13 realistic news articles covering Q3/Q4 earnings season for the default ticker universe |

## Usage

```python
from eval.data_loader import load_prices, load_news

prices = load_prices()      # returns {ticker: {date: price}}
articles = load_news()      # returns list[dict] ready for rag_store.ingest()
```

## Historical context (October 2024)

This period covers a major earnings week (Oct 28–31) where:
- **Apple** beat Q4 FY2024 estimates; Services hit a record $24.97B
- **Microsoft** reported Azure acceleration to 33% YoY growth
- **Alphabet** beat on Search (+12%) and Cloud (+35%)
- **Amazon** reported record AWS margins and operating income
- **Nvidia** confirmed Blackwell GPU shipments with >12-month demand backlog

S&P 500 (SPY) returned +0.48% on October 31 and approximately +2.2% for the full month.
