#!/usr/bin/env python3
"""
European Fintech Investment Tracker
====================================
CLI entry point for fetching, analyzing, and reporting on European fintech
investment news.

Usage
-----
  python main.py run        # fetch + analyze + report (full pipeline)
  python main.py fetch      # pull new articles from RSS feeds
  python main.py analyze    # run Claude analysis on pending articles
  python main.py report     # regenerate the HTML dashboard
  python main.py stats      # print database statistics
  python main.py list       # print all tracked investments
  python main.py schedule   # run full pipeline on a schedule (--interval mins)
"""

import sys
import time
import argparse
from pathlib import Path

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).parent))

from src import database as db
from src.config import DB_PATH, REPORT_PATH
from src.fetcher import fetch_all_feeds
from src.analyzer import analyze_pending
from src.report import generate_report

console = Console()


# ── Commands ───────────────────────────────────────────────────────────────────

def cmd_fetch(args) -> None:
    console.print(Panel("[bold cyan]Fetching news from RSS feeds…[/bold cyan]", expand=False))
    db.init_db()
    result = fetch_all_feeds(verbose=not args.quiet)
    console.print(
        f"\n[green]Done.[/green] Fetched {result['total_fetched']} relevant articles, "
        f"{result['total_new']} new."
    )


def cmd_analyze(args) -> None:
    console.print(Panel("[bold magenta]Analyzing articles with Claude Opus 4.6…[/bold magenta]", expand=False))
    db.init_db()
    result = analyze_pending(limit=args.limit, verbose=not args.quiet)
    console.print(
        f"\n[green]Done.[/green] Analyzed {result['analyzed']} articles → "
        f"{result['investments_found']} investments, "
        f"{result['not_relevant']} not relevant, "
        f"{result['errors']} errors."
    )


def cmd_report(args) -> None:
    console.print(Panel("[bold yellow]Generating HTML report…[/bold yellow]", expand=False))
    db.init_db()
    path = generate_report(args.output)
    console.print(f"\n[green]Report saved to:[/green] {path}")


def cmd_run(args) -> None:
    """Full pipeline: fetch → analyze → report."""
    console.print(
        Panel(
            "[bold white]Running full pipeline: fetch → analyze → report[/bold white]",
            expand=False,
        )
    )
    db.init_db()

    # 1. Fetch
    console.rule("[cyan]Step 1: Fetch[/cyan]")
    fetch_result = fetch_all_feeds(verbose=not args.quiet)
    console.print(
        f"[green]✓[/green] {fetch_result['total_new']} new articles fetched."
    )

    # 2. Analyze
    console.rule("[magenta]Step 2: Analyze[/magenta]")
    analyze_result = analyze_pending(limit=args.limit, verbose=not args.quiet)
    console.print(
        f"[green]✓[/green] {analyze_result['investments_found']} investments found."
    )

    # 3. Report
    console.rule("[yellow]Step 3: Report[/yellow]")
    path = generate_report(args.output)
    console.print(f"[green]✓[/green] Report: {path}")

    # Summary
    inv_stats = db.investment_count()
    art_stats = db.article_count()
    _print_summary(inv_stats, art_stats)


def cmd_stats(args) -> None:
    db.init_db()
    inv_stats = db.investment_count()
    art_stats = db.article_count()
    _print_summary(inv_stats, art_stats)


def cmd_list(args) -> None:
    db.init_db()
    investments = db.get_all_investments()
    if not investments:
        console.print("[yellow]No investments in database yet. Run 'python main.py run' first.[/yellow]")
        return

    table = Table(
        title=f"European Fintech Investments ({len(investments)} total)",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan",
        border_style="slate_blue1",
    )
    table.add_column("Company", style="bold white", min_width=20)
    table.add_column("Country", style="dim", width=14)
    table.add_column("Stage", width=12)
    table.add_column("Raised (EUR)", justify="right", style="green", width=13)
    table.add_column("Lead Investors", max_width=35, overflow="fold")
    table.add_column("Date", width=12)
    table.add_column("Focus", max_width=25, overflow="fold")

    for inv in investments:
        eur = inv.get("amount_raised_eur_millions")
        eur_str = f"€{eur:.0f}M" if eur else "–"

        leads = ", ".join(inv.get("lead_investors") or inv.get("new_investors") or []) or "–"
        focus = ", ".join((inv.get("technology_focus") or [])[:2]) or "–"

        table.add_row(
            inv.get("company_name") or "–",
            inv.get("country") or "–",
            inv.get("stage") or "–",
            eur_str,
            leads,
            inv.get("deal_date") or "–",
            focus,
        )

    console.print(table)


def cmd_schedule(args) -> None:
    """Run the full pipeline repeatedly at a fixed interval."""
    interval_secs = args.interval * 60
    console.print(
        Panel(
            f"[bold white]Scheduled mode:[/bold white] running every [cyan]{args.interval}[/cyan] minutes.\n"
            "Press Ctrl+C to stop.",
            expand=False,
        )
    )
    run_count = 0
    while True:
        run_count += 1
        console.rule(f"[dim]Run #{run_count}[/dim]")
        try:
            db.init_db()
            fetch_all_feeds(verbose=not args.quiet)
            analyze_pending(limit=args.limit, verbose=not args.quiet)
            path = generate_report(args.output)
            console.print(f"[green]Report updated:[/green] {path}")
        except KeyboardInterrupt:
            raise
        except Exception as exc:
            console.print(f"[red]Pipeline error: {exc}[/red]")
        console.print(f"[dim]Next run in {args.interval} minutes…[/dim]")
        time.sleep(interval_secs)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _print_summary(inv_stats: dict, art_stats: dict) -> None:
    total_eur = inv_stats.get("total_eur_millions") or 0.0
    eur_str = (
        f"€{total_eur/1000:.2f}B" if total_eur >= 1000 else f"€{total_eur:.0f}M"
    )

    table = Table(box=box.SIMPLE_HEAVY, show_header=False, border_style="slate_blue1")
    table.add_column("Metric", style="dim")
    table.add_column("Value", style="bold white")

    table.add_row("Total investment rounds tracked", str(inv_stats.get("total", 0)))
    table.add_row("Total capital raised (disclosed)", eur_str)
    table.add_row("Countries represented", str(inv_stats.get("countries", 0)))
    table.add_row("Articles fetched", str(art_stats.get("total", 0)))
    table.add_row("Articles pending analysis", str(art_stats.get("pending", 0)))
    table.add_row("Articles with investments", str(art_stats.get("with_investment", 0)))
    table.add_row("Database path", DB_PATH)

    console.print(Panel(table, title="[bold]Tracker Statistics[/bold]", expand=False))


# ── Argument parser ────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fintech-tracker",
        description="European Fintech Investment Tracker — powered by Claude Opus 4.6",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Shared options
    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument(
        "--quiet", "-q", action="store_true", help="Suppress verbose article-level output"
    )
    shared.add_argument(
        "--limit", "-n", type=int, default=50,
        help="Max articles to analyze per run (default: 50)"
    )
    shared.add_argument(
        "--output", "-o", default=REPORT_PATH,
        help=f"HTML report output path (default: {REPORT_PATH})"
    )

    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("run",      parents=[shared], help="Full pipeline: fetch + analyze + report")
    sub.add_parser("fetch",    parents=[shared], help="Fetch new articles from RSS feeds")
    sub.add_parser("analyze",  parents=[shared], help="Analyze pending articles with Claude")
    sub.add_parser("report",   parents=[shared], help="Regenerate HTML report from DB")
    sub.add_parser("stats",    parents=[shared], help="Show database statistics")
    sub.add_parser("list",     parents=[shared], help="List all tracked investments")

    sched = sub.add_parser("schedule", parents=[shared], help="Run pipeline on a schedule")
    sched.add_argument(
        "--interval", type=int, default=60,
        help="Minutes between pipeline runs (default: 60)"
    )

    return parser


# ── Entry point ────────────────────────────────────────────────────────────────

COMMANDS = {
    "run":      cmd_run,
    "fetch":    cmd_fetch,
    "analyze":  cmd_analyze,
    "report":   cmd_report,
    "stats":    cmd_stats,
    "list":     cmd_list,
    "schedule": cmd_schedule,
}


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    console.print(
        "\n[bold]🇪🇺 European Fintech Investment Tracker[/bold]\n",
        style="bright_white",
    )

    try:
        COMMANDS[args.command](args)
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted.[/yellow]")
        sys.exit(0)
    except Exception as exc:
        console.print(f"\n[red]Fatal error:[/red] {exc}")
        raise


if __name__ == "__main__":
    main()
