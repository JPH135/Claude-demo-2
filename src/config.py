"""Configuration: RSS feeds, keywords, and settings for the fintech tracker."""

import os
from dotenv import load_dotenv

load_dotenv()

# ── API & Storage ──────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
DB_PATH = os.getenv("DB_PATH", "./fintech_tracker.db")
REPORT_PATH = os.getenv("REPORT_PATH", "./report.html")
MAX_ARTICLES_PER_FEED = int(os.getenv("MAX_ARTICLES_PER_FEED", "20"))
MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", "8000"))
API_DELAY_SECONDS = float(os.getenv("API_DELAY_SECONDS", "1"))

CLAUDE_MODEL = "claude-opus-4-6"

# ── RSS Feeds ──────────────────────────────────────────────────────────────────
RSS_FEEDS = [
    {
        "name": "EU-Startups",
        "url": "https://eu-startups.com/feed/",
        "region": "Europe",
    },
    {
        "name": "Sifted",
        "url": "https://sifted.eu/feed/",
        "region": "Europe",
    },
    {
        "name": "TechCrunch Fintech",
        "url": "https://techcrunch.com/category/fintech/feed/",
        "region": "Global",
    },
    {
        "name": "FinExtra News",
        "url": "https://www.finextra.com/rss/finextra-news.xml",
        "region": "Global",
    },
    {
        "name": "The Paypers",
        "url": "https://thepaypers.com/feeds/rss",
        "region": "Global",
    },
    {
        "name": "Fintech News Europe",
        "url": "https://fintechnews.eu/feed/",
        "region": "Europe",
    },
    {
        "name": "AltFi",
        "url": "https://www.altfi.com/feed",
        "region": "Europe",
    },
    {
        "name": "Google News - EU Fintech Investment",
        "url": (
            "https://news.google.com/rss/search?"
            "q=fintech+investment+Europe+million&hl=en-US&gl=US&ceid=US:en"
        ),
        "region": "Europe",
    },
    {
        "name": "Google News - European Fintech Funding",
        "url": (
            "https://news.google.com/rss/search?"
            "q=European+fintech+funding+raised+series&hl=en-US&gl=US&ceid=US:en"
        ),
        "region": "Europe",
    },
    {
        "name": "Google News - Fintech VC Europe",
        "url": (
            "https://news.google.com/rss/search?"
            "q=fintech+venture+capital+growth+equity+Europe&hl=en-US&gl=US&ceid=US:en"
        ),
        "region": "Europe",
    },
    {
        "name": "Google News - Insurtech Europe",
        "url": (
            "https://news.google.com/rss/search?"
            "q=insurtech+wealthtech+regtech+Europe+funding&hl=en-US&gl=US&ceid=US:en"
        ),
        "region": "Europe",
    },
]

# ── Investment Keyword Filter ──────────────────────────────────────────────────
INVESTMENT_KEYWORDS = [
    "raises", "raised", "funding", "investment", "series a", "series b",
    "series c", "series d", "series e", "growth equity", "venture capital",
    " vc ", "million", "billion", "round", "backed by", "led by",
    "investors", "valuation", "seed round", "pre-seed", "growth round",
    "capital", "fintech", "startup", "scale-up",
]

# ── European Countries & Cities (for relevance filtering) ─────────────────────
EUROPEAN_ENTITIES = [
    # Countries
    "united kingdom", "uk", "germany", "france", "netherlands", "sweden",
    "switzerland", "spain", "italy", "denmark", "finland", "norway",
    "austria", "belgium", "ireland", "portugal", "poland", "czech republic",
    "romania", "hungary", "lithuania", "latvia", "estonia", "greece",
    "luxembourg", "malta", "cyprus", "slovakia", "slovenia", "croatia",
    "bulgaria", "serbia",
    # Key cities
    "london", "berlin", "paris", "amsterdam", "stockholm", "zurich",
    "madrid", "milan", "copenhagen", "helsinki", "oslo", "vienna",
    "brussels", "dublin", "lisbon", "warsaw", "prague", "bucharest",
    "budapest", "barcelona", "munich", "hamburg", "frankfurt", "rotterdam",
    "edinburgh", "manchester", "dublin", "tallinn", "riga", "vilnius",
    "helsinki", "gothenburg", "malmo", "antwerp", "ghent",
]

# ── HTTP Headers for scraping ──────────────────────────────────────────────────
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}
REQUEST_TIMEOUT = 15  # seconds
