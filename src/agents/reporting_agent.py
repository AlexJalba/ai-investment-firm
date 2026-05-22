"""Reporting Agent — generates daily reports via web dashboard + Excel."""
from __future__ import annotations

import json
from pathlib import Path

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from src.config import get_settings
from src.observability.logger import audit, get_logger, get_tracer
from src.portfolio.models import PortfolioSnapshot
from src.reporting.excel_report import write_excel_report

logger = get_logger(__name__)
tracer = get_tracer("reporting_agent")

SYSTEM_PROMPT = """You are the Reporting Officer of an AI investment firm.
Write a concise daily trading summary based on the data provided.
Format: plain text, max 300 words. Include:
- Key market observations
- Trades executed today and their rationale
- End-of-day portfolio value vs start-of-day
- P&L vs SPY benchmark
- One risk note or observation
"""


def run_reporting_agent(
    trade_date: str,
    snapshot: PortfolioSnapshot,
    start_of_day_value: float,
    filled_trades: list[dict],
    research_reports: list[dict],
    benchmark_pct: float | None,
) -> dict:
    """Generate and persist daily reports. Returns paths to generated files."""
    cfg = get_settings()

    with tracer.start_as_current_span("reporting_agent") as span:
        span.set_attribute("trade_date", trade_date)

        pnl = snapshot.total_value - start_of_day_value
        pnl_pct = pnl / start_of_day_value if start_of_day_value else 0

        # ── LLM narrative ────────────────────────────────────────────────────
        if cfg.mock_llm:
            from eval.fixtures import DAILY_NARRATIVE
            narrative = DAILY_NARRATIVE
        else:
            llm = ChatAnthropic(
                model=cfg.research_model,  # cheap model — narrative only
                api_key=cfg.anthropic_api_key,
                max_tokens=512,
            )

            context = (
                f"Date: {trade_date}\n"
                f"Start value: ${start_of_day_value:,.2f}\n"
                f"End value: ${snapshot.total_value:,.2f}\n"
                f"P&L: ${pnl:+,.2f} ({pnl_pct:+.2%})\n"
                f"Benchmark (SPY): {benchmark_pct:+.2%}\n" if benchmark_pct is not None else ""
                f"Trades executed: {len(filled_trades)}\n"
                f"Trades: {json.dumps(filled_trades, default=str)}\n"
                f"Research: {json.dumps([{k: r[k] for k in ('ticker','recommendation','sentiment')} for r in research_reports])}"
            )

            messages = [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=context)]
            narrative = llm.invoke(messages).content

        # ── Excel report ─────────────────────────────────────────────────────
        reports_dir = Path(cfg.reports_dir) / trade_date
        reports_dir.mkdir(parents=True, exist_ok=True)

        excel_path = str(reports_dir / "daily_report.xlsx")
        write_excel_report(
            path=excel_path,
            trade_date=trade_date,
            snapshot=snapshot,
            start_of_day_value=start_of_day_value,
            filled_trades=filled_trades,
            research_reports=research_reports,
            benchmark_pct=benchmark_pct,
            narrative=narrative,
        )

        # ── JSON artifact (consumed by dashboard) ────────────────────────────
        report_data = {
            "trade_date": trade_date,
            "start_value": start_of_day_value,
            "end_value": snapshot.total_value,
            "pnl": pnl,
            "pnl_pct": pnl_pct,
            "benchmark_pct": benchmark_pct,
            "cash": snapshot.cash,
            "holdings": [h.model_dump() for h in snapshot.holdings],
            "filled_trades": filled_trades,
            "research_reports": research_reports,
            "narrative": narrative,
        }

        json_path = str(reports_dir / "daily_report.json")
        with open(json_path, "w") as f:
            json.dump(report_data, f, indent=2, default=str)

        audit(
            "report.generated",
            audit_log_path=cfg.audit_log_path,
            trade_date=trade_date,
            excel=excel_path,
            json=json_path,
        )
        logger.info("report.generated", trade_date=trade_date)
        return {"excel": excel_path, "json": json_path, "narrative": narrative}
