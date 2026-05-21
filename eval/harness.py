"""Eval harness — replays a historical date window and reports performance + process quality."""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import yfinance as yf

from src.config import get_settings
from src.graph.trading_graph import run_trading_day
from src.observability.logger import configure_logging, get_logger

logger = get_logger(__name__)


def daterange(start: date, end: date):
    d = start
    while d <= end:
        if d.weekday() < 5:
            yield d
        d += timedelta(days=1)


def compute_portfolio_return(start_value: float, end_value: float) -> float:
    return (end_value - start_value) / start_value if start_value else 0.0


def compute_benchmark_return(ticker: str, start: date, end: date) -> float:
    df = yf.download(ticker, start=start, end=end + timedelta(days=1), progress=False, auto_adjust=True)
    if df.empty or len(df) < 2:
        return 0.0
    return float((df["Close"].iloc[-1] - df["Close"].iloc[0]) / df["Close"].iloc[0])


def compute_grounding_score(reports_dir: Path) -> float:
    """
    Ratio of research reports that have ≥1 citation.
    A proxy for grounded decision-making.
    """
    total, grounded = 0, 0
    for json_file in reports_dir.glob("*/daily_report.json"):
        try:
            data = json.loads(json_file.read_text())
            for r in data.get("research_reports", []):
                total += 1
                if r.get("citations"):
                    grounded += 1
        except Exception:
            pass
    return grounded / total if total else 0.0


def compute_hitl_rate(audit_log_path: str) -> dict:
    """Fraction of HITL trades that were approved vs rejected."""
    decisions = {"approve": 0, "reject": 0, "edit": 0}
    try:
        with open(audit_log_path) as f:
            for line in f:
                event = json.loads(line)
                if event.get("event") == "hitl.decision":
                    decisions[event.get("decision", "approve")] += 1
    except FileNotFoundError:
        pass
    return decisions


def run_eval(
    tickers: list[str],
    start_date: date,
    end_date: date,
    eval_dir: str = "./data/eval",
) -> dict:
    cfg = get_settings()
    configure_logging(cfg.log_level, cfg.audit_log_path, cfg.otlp_endpoint)

    eval_path = Path(eval_dir)
    eval_path.mkdir(parents=True, exist_ok=True)

    # Override data dir for eval isolation
    reports_dir = eval_path / "reports"
    reports_dir.mkdir(exist_ok=True)

    trading_days = list(daterange(start_date, end_date))
    logger.info("eval.start", days=len(trading_days), start=start_date.isoformat(), end=end_date.isoformat())

    daily_results = []
    portfolio_values = []

    for d in trading_days:
        date_str = d.isoformat()
        logger.info("eval.trading_day", date=date_str)
        try:
            state = run_trading_day(tickers, trade_date=date_str, thread_id=f"eval-{date_str}")
            snap = state.get("portfolio_snapshot") or {}
            end_val = snap.get("total_value", cfg.starting_capital)
            start_val = state.get("start_of_day_value", cfg.starting_capital)

            daily_results.append({
                "date": date_str,
                "start_value": start_val,
                "end_value": end_val,
                "pnl_pct": compute_portfolio_return(start_val, end_val),
                "trades": len(state.get("filled_trades", [])),
            })
            portfolio_values.append(end_val)
        except Exception as e:
            logger.error("eval.day_failed", date=date_str, error=str(e))

    # ── Performance metrics ────────────────────────────────────────────────────
    if portfolio_values:
        total_return = compute_portfolio_return(cfg.starting_capital, portfolio_values[-1])
    else:
        total_return = 0.0

    benchmark_return = compute_benchmark_return(cfg.benchmark_ticker, start_date, end_date)
    alpha = total_return - benchmark_return

    grounding_score = compute_grounding_score(eval_path / "reports")
    hitl_stats = compute_hitl_rate(cfg.audit_log_path)

    report = {
        "period": {"start": start_date.isoformat(), "end": end_date.isoformat()},
        "tickers": tickers,
        "trading_days": len(trading_days),
        "portfolio_return_pct": round(total_return * 100, 2),
        "benchmark_return_pct": round(benchmark_return * 100, 2),
        "alpha_pct": round(alpha * 100, 2),
        "grounding_score": round(grounding_score, 3),
        "hitl_decisions": hitl_stats,
        "daily_results": daily_results,
    }

    out_path = eval_path / "eval_report.json"
    out_path.write_text(json.dumps(report, indent=2))
    logger.info("eval.complete", report=str(out_path))
    _print_summary(report)
    return report


def _print_summary(r: dict) -> None:
    print("\n" + "=" * 60)
    print(f"EVAL REPORT  {r['period']['start']} → {r['period']['end']}")
    print("=" * 60)
    print(f"Portfolio return : {r['portfolio_return_pct']:+.2f}%")
    print(f"Benchmark (SPY)  : {r['benchmark_return_pct']:+.2f}%")
    print(f"Alpha            : {r['alpha_pct']:+.2f}%")
    print(f"Grounding score  : {r['grounding_score']:.1%}")
    print(f"HITL decisions   : {r['hitl_decisions']}")
    print("=" * 60 + "\n")
