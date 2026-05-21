"""Human-in-the-Loop Risk Committee — CLI prompt for approving/rejecting trades."""
from __future__ import annotations

import json
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.config import get_settings
from src.observability.logger import audit, get_logger

logger = get_logger(__name__)
console = Console()


def present_trade_for_review(trade: dict, market_price: float) -> dict:
    """
    Prompt a human Risk Committee member via CLI to approve, reject, or edit a trade.
    Returns a decision dict: {"trade": ..., "decision": "approve"|"reject"|"edit", "notes": str, "adjusted_shares": float|None}
    """
    cfg = get_settings()
    ticker = trade["ticker"]
    side = trade["side"]
    shares = float(trade["shares"])
    notional = shares * market_price

    table = Table(title=f"[bold red]RISK COMMITTEE REVIEW — {ticker}[/bold red]", show_header=True)
    table.add_column("Field", style="bold cyan")
    table.add_column("Value", style="white")

    table.add_row("Ticker", ticker)
    table.add_row("Side", f"[green]{side}[/green]" if side == "BUY" else f"[red]{side}[/red]")
    table.add_row("Shares", f"{shares:,.0f}")
    table.add_row("Market Price", f"${market_price:,.2f}")
    table.add_row("Notional", f"${notional:,.2f}")
    table.add_row("Rationale", trade.get("rationale", ""))
    table.add_row("Risk Flags", ", ".join(trade.get("risk_flags", [])) or "None")
    table.add_row("Citations", "\n".join(trade.get("citations", [])))

    console.print(table)
    console.print()

    while True:
        choice = console.input("[bold yellow]Decision — [A]pprove / [R]eject / [E]dit shares: [/bold yellow]").strip().upper()
        if choice in ("A", "APPROVE"):
            notes = console.input("Notes (optional): ").strip()
            decision = {"trade": trade, "decision": "approve", "notes": notes, "adjusted_shares": None}
            break
        elif choice in ("R", "REJECT"):
            notes = console.input("Reason for rejection: ").strip()
            decision = {"trade": trade, "decision": "reject", "notes": notes, "adjusted_shares": None}
            break
        elif choice in ("E", "EDIT"):
            try:
                new_shares = float(console.input(f"New share count (current: {shares:.0f}): ").strip())
                notes = console.input("Notes: ").strip()
                decision = {"trade": trade, "decision": "approve", "notes": notes, "adjusted_shares": new_shares}
                break
            except ValueError:
                console.print("[red]Invalid share count. Try again.[/red]")
        else:
            console.print("[red]Enter A, R, or E.[/red]")

    audit(
        "hitl.decision",
        audit_log_path=cfg.audit_log_path,
        ticker=ticker,
        decision=decision["decision"],
        notes=decision.get("notes", ""),
        adjusted_shares=decision.get("adjusted_shares"),
    )
    logger.info("hitl.decision", ticker=ticker, decision=decision["decision"])
    return decision


def run_risk_committee(pending_trades: list[dict], market_prices: dict[str, float]) -> list[dict]:
    """Process all HITL-pending trades. Returns list of approved (possibly edited) trades."""
    if not pending_trades:
        return []

    console.print(Panel(
        f"[bold]Risk Committee convened — {len(pending_trades)} trade(s) require approval[/bold]",
        style="bold red",
    ))

    approved = []
    for trade in pending_trades:
        price = market_prices.get(trade["ticker"], 0.0)
        decision = present_trade_for_review(trade, price)

        if decision["decision"] == "approve":
            final_trade = dict(trade)
            if decision["adjusted_shares"]:
                final_trade["shares"] = decision["adjusted_shares"]
            final_trade["hitl_notes"] = decision.get("notes", "")
            approved.append(final_trade)

    console.print(f"[green]Risk Committee approved {len(approved)}/{len(pending_trades)} trades.[/green]\n")
    return approved
