#!/bin/bash
set -e

export MOCK_LLM=true
export ANTHROPIC_API_KEY=mock-key
export PYTHONPATH=/Users/I074992/IdeaProjects/ai-investment-firm

echo "Seeding RAG store..."
.venv/bin/python scripts/seed_rag.py

echo "Wiping portfolio DB..."
rm -f data/portfolio.db

echo "Running trading day..."
.venv/bin/python -m src.cli trade AAPL MSFT GOOGL AMZN NVDA --date 2024-10-25
