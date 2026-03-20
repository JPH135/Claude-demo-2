# 🇪🇺 European Fintech Investment Tracker

Monitors fintech news across the web for venture and growth equity investment rounds in Europe. Uses **Claude Opus 4.6** to extract structured deal intelligence from each article.

## What it tracks

For every identified raise, Claude extracts:

| Field | Detail |
|---|---|
| **Company** | Name, summary, founding year, HQ location |
| **Deal** | Stage (Seed → PE), round type, amount raised in EUR/USD |
| **Valuation** | Pre/post-money valuation (where disclosed) |
| **Investors** | Lead investors, new investors, existing investors |
| **Metrics** | ARR, revenue, GMV, customers, employees (where stated) |
| **Use of funds** | Stated deployment plan |
| **Tech focus** | payments, lending, insurtech, wealthtech, regtech, etc. |
| **Notable details** | Regulatory context, partnerships, expansion plans |

## Architecture

```
RSS Feeds (11 sources)
     │
     ▼
src/fetcher.py      # stdlib XML RSS parser + BeautifulSoup article scraper
     │
     ▼
SQLite (articles)
     │
     ▼
src/analyzer.py     # Claude Opus 4.6 + Pydantic structured output
     │
     ▼
SQLite (investments)
     │
     ▼
src/report.py       # Self-contained HTML dashboard
```

## Quick start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure
cp .env.example .env
# Edit .env and set ANTHROPIC_API_KEY

# 3. Run full pipeline (fetch → analyze → report)
python main.py run

# 4. Open the dashboard
open report.html   # macOS
xdg-open report.html   # Linux
```

## Commands

```bash
python main.py run          # Full pipeline
python main.py fetch        # Fetch new articles from RSS feeds only
python main.py analyze      # Run Claude analysis on pending articles only
python main.py report       # Regenerate HTML dashboard only
python main.py stats        # Database statistics
python main.py list         # Print investment table in terminal
python main.py schedule --interval 60  # Run pipeline every 60 minutes
```

### Options

| Flag | Default | Description |
|---|---|---|
| `--limit N` | 50 | Max articles to analyze per run |
| `--output PATH` | `./report.html` | HTML report output path |
| `--quiet` | off | Suppress per-article output |
| `--interval N` | 60 | Minutes between scheduled runs |

## News sources monitored

- EU-Startups
- Sifted
- TechCrunch Fintech
- FinExtra
- The Paypers
- Fintech News Europe
- AltFi
- Google News (4 targeted searches for EU fintech deals)

## Dashboard features

- **Summary stats**: total rounds, capital raised, countries covered
- **Charts**: breakdown by stage, country, and technology focus
- **Filters**: stage, round type, country, technology, free-text search
- **Sortable table**: click any column header
- **Investment detail panel**: full analysis in a modal — click any row

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | *(required)* | Your Anthropic API key |
| `DB_PATH` | `./fintech_tracker.db` | SQLite database path |
| `REPORT_PATH` | `./report.html` | HTML output path |
| `MAX_ARTICLES_PER_FEED` | `20` | Articles fetched per source |
| `MAX_CONTENT_LENGTH` | `8000` | Max article chars sent to Claude |
| `API_DELAY_SECONDS` | `1` | Delay between Claude API calls |
