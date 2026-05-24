#!/bin/bash
set -e

cd "$(dirname "$0")/.."

export MOCK_LLM=true
export ANTHROPIC_API_KEY=mock-key

echo "Seeding RAG store..."
.venv/bin/python scripts/seed_rag.py

echo "Wiping portfolio DB..."
rm -f data/portfolio.db

echo "Running trading day..."
.venv/bin/python -m src.cli trade AAPL MSFT GOOGL AMZN NVDA --date 2024-10-25
