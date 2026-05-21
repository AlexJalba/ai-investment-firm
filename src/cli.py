"""CLI entrypoint — run a trading day, start the dashboard, or run the eval."""
from __future__ import annotations

import typer
from rich.console import Console

app = typer.Typer(name="firm", help="AI Investment Firm CLI", add_completion=False)
console = Console()

DEFAULT_TICKERS = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA"]


@app.command()
def trade(
    tickers: list[str] = typer.Argument(None, help="Tickers to trade (default: tech mega-caps)"),
    date: str | None = typer.Option(None, "--date", "-d", help="Trade date YYYY-MM-DD (default: today)"),
    thread_id: str = typer.Option("default", "--thread", help="LangGraph thread ID for state persistence"),
):
    """Run one trading day end-to-end."""
    from src.graph.trading_graph import run_trading_day

    tickers = tickers or DEFAULT_TICKERS
    console.print(f"[bold blue]Starting trading day for {tickers}...[/bold blue]")
    state = run_trading_day(tickers, trade_date=date, thread_id=thread_id)
    console.print(f"[green]Done. Fills: {len(state.get('filled_trades', []))}[/green]")


@app.command()
def dashboard(
    host: str = typer.Option("0.0.0.0", "--host"),
    port: int = typer.Option(8080, "--port", "-p"),
):
    """Launch the web dashboard."""
    from src.reporting.dashboard import start_dashboard

    console.print(f"[bold blue]Dashboard at http://localhost:{port}[/bold blue]")
    start_dashboard(host=host, port=port)


@app.command()
def eval(
    tickers: list[str] = typer.Argument(None, help="Tickers to evaluate"),
    start: str = typer.Option(..., "--start", "-s", help="Start date YYYY-MM-DD"),
    end: str = typer.Option(..., "--end", "-e", help="End date YYYY-MM-DD"),
):
    """Run the eval harness over a historical date range."""
    from datetime import date as dt

    from eval.harness import run_eval

    tickers = tickers or DEFAULT_TICKERS
    run_eval(tickers, dt.fromisoformat(start), dt.fromisoformat(end))


@app.command()
def ingest(
    tickers: list[str] = typer.Argument(None, help="Tickers to ingest news for"),
):
    """Pre-populate the RAG store with news for the given tickers."""
    from src.market_data.news import fetch_all_news
    from src.rag.store import RAGStore

    tickers = tickers or DEFAULT_TICKERS
    rag = RAGStore()
    articles = fetch_all_news(tickers)
    count = rag.ingest(articles)
    console.print(f"[green]Ingested {count} articles for {tickers}[/green]")


if __name__ == "__main__":
    app()
