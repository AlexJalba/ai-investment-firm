"""Research Agent — retrieves evidence via RAG and produces cited analysis."""
from __future__ import annotations

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from src.config import get_settings
from src.guardrails.validators import ResearchOutput, sanitize_web_text
from src.market_data.news import fetch_all_news
from src.observability.logger import audit, get_logger, get_tracer
from src.rag.store import RAGStore

logger = get_logger(__name__)
tracer = get_tracer("research_agent")

SYSTEM_PROMPT = """You are a buy-side equity research analyst.
Your job is to analyze the latest news and market data for a given ticker and produce a structured research note.

Rules:
- Ground every claim in the provided evidence. Never invent numbers, dates, or quotes.
- If you don't have sufficient evidence, set confidence below 0.4 and recommend 'hold'.
- Return a JSON object matching this schema exactly:
  {
    "ticker": "AAPL",
    "summary": "...",
    "sentiment": "bullish|bearish|neutral",
    "confidence": 0.0-1.0,
    "citations": ["[1] source text...", "[2] source text..."],
    "recommendation": "buy|sell|hold"
  }
- citations must reference the numbered evidence blocks provided.
"""


def run_research_agent(ticker: str, rag_store: RAGStore) -> dict:
    """Produce a research report for a single ticker."""
    cfg = get_settings()

    with tracer.start_as_current_span("research_agent") as span:
        span.set_attribute("ticker", ticker)

        # Step 1: Freshen the RAG store with latest news
        articles = fetch_all_news([ticker])
        sanitized = [{**a, "summary": sanitize_web_text(a.get("summary", ""))} for a in articles]
        rag_store.ingest(sanitized)

        # Step 2: Retrieve relevant evidence
        chunks = rag_store.retrieve(f"{ticker} earnings revenue outlook", ticker=ticker, n_results=6)
        if not chunks:
            chunks = rag_store.retrieve(f"{ticker} stock price", n_results=4)

        evidence = rag_store.format_citations(chunks)

        # Step 3: Call the LLM
        llm = ChatAnthropic(
            model=cfg.research_model,
            api_key=cfg.anthropic_api_key,
            max_tokens=1024,
        )

        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(
                content=f"Ticker: {ticker}\n\nEvidence:\n{evidence}\n\nProduce the research note JSON."
            ),
        ]

        response = llm.invoke(messages)
        raw = response.content

        # Step 4: Parse and validate output
        try:
            # Extract JSON from potential markdown code block
            if "```" in raw:
                raw = raw.split("```")[1].lstrip("json").strip()
            report = ResearchOutput.model_validate_json(raw)
        except Exception as e:
            logger.warning("research.parse_failed", ticker=ticker, error=str(e), raw=raw[:200])
            # Safe fallback — insufficient evidence
            report = ResearchOutput(
                ticker=ticker,
                summary=f"Insufficient evidence to form a view on {ticker}.",
                sentiment="neutral",
                confidence=0.2,
                citations=["[1] No sufficient evidence retrieved."],
                recommendation="hold",
            )

        result = report.model_dump()
        audit(
            "research.completed",
            audit_log_path=cfg.audit_log_path,
            ticker=ticker,
            recommendation=result["recommendation"],
            confidence=result["confidence"],
            num_citations=len(result["citations"]),
        )
        logger.info("research.completed", ticker=ticker, recommendation=result["recommendation"])
        return result
