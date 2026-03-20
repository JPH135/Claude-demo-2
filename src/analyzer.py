"""
Claude-powered investment analysis.

Sends article text to Claude Opus 4.6 and extracts structured deal data using
Pydantic structured outputs.
"""

import time
from typing import Optional

import anthropic
from pydantic import BaseModel, Field
from rich.console import Console
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config import API_DELAY_SECONDS, ANTHROPIC_API_KEY, CLAUDE_MODEL
from src import database as db

console = Console()

# ── Pydantic model ─────────────────────────────────────────────────────────────

class InvestmentDetails(BaseModel):
    """Structured representation of a European fintech investment raise."""

    is_european_fintech_investment: bool = Field(
        description=(
            "True if this article describes a genuine venture capital, growth equity, "
            "or private equity investment round in a European fintech / financial technology company. "
            "False for opinion pieces, product launches, acquisitions without disclosed deal value, "
            "or companies not headquartered in Europe."
        )
    )

    # Company
    company_name: str = Field(default="", description="Legal or trading name of the company")
    company_summary: str = Field(
        default="",
        description=(
            "2–3 sentence description: what the company does, its business model, "
            "target customers, and key differentiation."
        ),
    )
    founding_year: Optional[int] = Field(default=None, description="Year founded if mentioned")
    country: str = Field(default="", description="Country of headquarters (e.g. 'United Kingdom')")
    city: str = Field(default="", description="City of headquarters (e.g. 'London')")
    technology_focus: list[str] = Field(
        default_factory=list,
        description=(
            "List of fintech verticals. Choose from: payments, lending, insurance (insurtech), "
            "wealth management, banking-as-a-service, regtech, crypto/blockchain, "
            "open banking, SME finance, real estate finance, trade finance, "
            "embedded finance, buy-now-pay-later, savings, FX/remittances, data analytics, other."
        ),
    )
    customer_segment: str = Field(
        default="", description="Primary customer type: B2B, B2C, or B2B2C"
    )

    # Deal details
    stage: str = Field(
        default="",
        description=(
            "Funding stage: Pre-Seed, Seed, Series A, Series B, Series C, Series D, "
            "Series E+, Growth, Private Equity, Debt, Bridge, or Unknown."
        ),
    )
    round_type: str = Field(
        default="",
        description="Type of investment: Venture Capital, Growth Equity, or Private Equity.",
    )
    deal_date: str = Field(
        default="",
        description="Date the round was announced (YYYY-MM-DD or YYYY-MM or YYYY).",
    )
    amount_raised_original: str = Field(
        default="",
        description="Amount raised exactly as stated in the article (e.g. '€45 million', '$120M').",
    )
    amount_raised_eur_millions: Optional[float] = Field(
        default=None,
        description="Amount raised converted to EUR millions (use 1 USD = 0.92 EUR, 1 GBP = 1.17 EUR if needed).",
    )
    amount_raised_usd_millions: Optional[float] = Field(
        default=None,
        description="Amount raised converted to USD millions.",
    )
    pre_money_valuation_eur_m: Optional[float] = Field(
        default=None,
        description="Pre-money valuation in EUR millions, if stated.",
    )
    post_money_valuation_eur_m: Optional[float] = Field(
        default=None,
        description="Post-money valuation in EUR millions, if stated.",
    )
    valuation_stated: str = Field(
        default="",
        description="Valuation exactly as stated in the article (e.g. '$500M post-money').",
    )

    # Investors
    lead_investors: list[str] = Field(
        default_factory=list,
        description="Names of lead/co-lead investors in this round.",
    )
    new_investors: list[str] = Field(
        default_factory=list,
        description="All investors participating for the first time in this round.",
    )
    existing_investors: list[str] = Field(
        default_factory=list,
        description="Existing investors who participated in follow-on in this round.",
    )

    # Additional intelligence
    key_metrics: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Key company metrics mentioned (e.g. {\"ARR\": \"€12M\", \"customers\": \"5,000\", "
            "\"GMV\": \"€2B\", \"employees\": \"200\"}). Only include explicitly stated metrics."
        ),
    )
    use_of_funds: str = Field(
        default="",
        description="How the company plans to use the new capital.",
    )
    notable_details: str = Field(
        default="",
        description=(
            "Any other relevant context: regulatory licenses, partnerships, "
            "recent M&A activity, competitive positioning, geographic expansion plans, etc."
        ),
    )


# ── Claude client ──────────────────────────────────────────────────────────────

_client: Optional[anthropic.Anthropic] = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    return _client


SYSTEM_PROMPT = """You are a senior fintech investment analyst at a European venture capital fund.
Your job is to read news articles and extract precise, structured information about investment rounds
in European fintech companies.

Be meticulous about accuracy:
- Only extract information explicitly stated in the article; do not infer or fabricate.
- For currency conversions, use: 1 USD = 0.92 EUR, 1 GBP = 1.17 EUR.
- If information is not stated, leave the field empty or null.
- European fintech includes: UK, EU, EEA, and Switzerland-based companies.
- "Growth equity" typically refers to rounds above Series B where the company is profitable or near-profitable.
- Distinguish clearly between lead investors and participating investors.
"""


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    reraise=True,
)
def _call_claude(title: str, content: str, url: str) -> InvestmentDetails:
    """Call Claude and return structured investment data."""
    client = _get_client()

    user_message = f"""Analyse the following news article and extract investment information.

Article URL: {url}
Article Title: {title}

Article Content:
{content}

Extract all available investment details and populate the structured output fields.
"""

    response = client.messages.parse(
        model=CLAUDE_MODEL,
        max_tokens=4096,
        thinking={"type": "adaptive"},
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
        output_format=InvestmentDetails,
    )

    return response.parsed_output


# ── Public API ─────────────────────────────────────────────────────────────────

def analyze_pending(limit: int = 50, verbose: bool = True) -> dict:
    """
    Analyze all pending articles using Claude.

    Returns a summary with counts of investments found, skipped, errors.
    """
    if not ANTHROPIC_API_KEY:
        raise ValueError("ANTHROPIC_API_KEY is not set. Check your .env file.")

    articles = db.get_pending_articles(limit=limit)
    if not articles:
        if verbose:
            console.print("[yellow]No pending articles to analyze.[/yellow]")
        return {"analyzed": 0, "investments_found": 0, "not_relevant": 0, "errors": 0}

    counts = {"analyzed": 0, "investments_found": 0, "not_relevant": 0, "errors": 0}

    for article in articles:
        article_id = article["id"]
        title = article.get("title", "")
        content = article.get("content") or article.get("summary", "")
        url = article.get("url", "")

        if verbose:
            console.print(f"\n[bold]Analyzing:[/bold] {title[:80]}")

        try:
            result = _call_claude(title, content, url)
            counts["analyzed"] += 1

            if not result.is_european_fintech_investment:
                db.mark_article(article_id, status=2)  # not relevant
                counts["not_relevant"] += 1
                if verbose:
                    console.print("  [dim]→ Not a relevant investment article[/dim]")
            else:
                investment_data = result.model_dump()
                investment_data["source_url"] = url
                db.insert_investment(article_id, investment_data)
                db.mark_article(article_id, status=1)  # investment found
                counts["investments_found"] += 1
                if verbose:
                    eur = result.amount_raised_eur_millions
                    eur_str = f"€{eur:.0f}M" if eur else "undisclosed"
                    console.print(
                        f"  [green]✓[/green] {result.company_name} | "
                        f"{result.stage} | {eur_str} | {result.country}"
                    )

        except Exception as exc:
            db.mark_article(article_id, status=3)  # error
            counts["errors"] += 1
            if verbose:
                console.print(f"  [red]✗ Error: {exc}[/red]")

        time.sleep(API_DELAY_SECONDS)

    return counts
