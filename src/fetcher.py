"""RSS feed fetcher and article content scraper.

Uses stdlib xml.etree for RSS/Atom parsing instead of feedparser to avoid
the sgmllib3k build dependency.
"""

import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Optional

import requests
from bs4 import BeautifulSoup
from rich.console import Console

from src.config import (
    EUROPEAN_ENTITIES,
    INVESTMENT_KEYWORDS,
    MAX_ARTICLES_PER_FEED,
    MAX_CONTENT_LENGTH,
    REQUEST_HEADERS,
    REQUEST_TIMEOUT,
    RSS_FEEDS,
)
from src import database as db

console = Console()

# XML namespaces commonly found in feeds
_NS = {
    "atom":    "http://www.w3.org/2005/Atom",
    "content": "http://purl.org/rss/1.0/modules/content/",
    "dc":      "http://purl.org/dc/elements/1.1/",
    "media":   "http://search.yahoo.com/mrss/",
}


# ── Utility ────────────────────────────────────────────────────────────────────

def _parse_date(raw: str) -> str:
    """Parse RFC-2822 or ISO date string → ISO string, or return now."""
    if not raw:
        return datetime.now(timezone.utc).isoformat()
    try:
        return parsedate_to_datetime(raw).isoformat()
    except Exception:
        pass
    try:
        # ISO-8601 variants
        for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
            try:
                return datetime.strptime(raw.strip(), fmt).isoformat()
            except ValueError:
                continue
    except Exception:
        pass
    return datetime.now(timezone.utc).isoformat()


def _text(el: Optional[ET.Element]) -> str:
    return (el.text or "").strip() if el is not None else ""


def _is_investment_relevant(text: str) -> bool:
    lower = text.lower()
    has_investment = any(kw in lower for kw in INVESTMENT_KEYWORDS)
    has_europe = any(loc in lower for loc in EUROPEAN_ENTITIES)
    return has_investment and has_europe


def _clean_html(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "nav", "header", "footer",
                     "aside", "form", "button", "figure", "iframe"]):
        tag.decompose()
    text = soup.get_text(separator=" ")
    return re.sub(r"\s+", " ", text).strip()


# ── RSS / Atom parser ──────────────────────────────────────────────────────────

def _parse_feed_xml(xml_bytes: bytes, source_name: str) -> list[dict]:
    """Parse RSS 2.0 or Atom 1.0 bytes → list of article dicts."""
    articles = []
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        console.print(f"  [red]XML parse error ({source_name}): {exc}[/red]")
        return []

    tag = root.tag.lower()

    # ── Atom feed ──────────────────────────────────────────────────────────────
    if "atom" in tag or root.find("atom:entry", _NS) is not None:
        entries = root.findall("{http://www.w3.org/2005/Atom}entry") or root.findall("entry")
        for entry in entries[:MAX_ARTICLES_PER_FEED]:
            link_el = entry.find("{http://www.w3.org/2005/Atom}link") or entry.find("link")
            url = (link_el.attrib.get("href") or _text(link_el)) if link_el is not None else ""
            title_el = entry.find("{http://www.w3.org/2005/Atom}title") or entry.find("title")
            title = _text(title_el)
            summary_el = (
                entry.find("{http://www.w3.org/2005/Atom}summary")
                or entry.find("{http://www.w3.org/2005/Atom}content")
                or entry.find("summary")
            )
            summary_html = _text(summary_el)
            date_el = (
                entry.find("{http://www.w3.org/2005/Atom}published")
                or entry.find("{http://www.w3.org/2005/Atom}updated")
                or entry.find("published")
            )
            published_at = _parse_date(_text(date_el))
            articles.append({"url": url, "title": title,
                             "summary": _clean_html(summary_html) if summary_html else "",
                             "published_at": published_at})

    # ── RSS 2.0 / RSS 1.0 ─────────────────────────────────────────────────────
    else:
        # RSS 2.0: root → channel → item(s)
        # RSS 1.0 (RDF): root → item(s)
        items = root.findall(".//item")
        for item in items[:MAX_ARTICLES_PER_FEED]:
            url = _text(item.find("link"))
            if not url:
                guid = item.find("guid")
                if guid is not None and guid.attrib.get("isPermaLink", "true") == "true":
                    url = _text(guid)
            title = _text(item.find("title"))
            # Prefer content:encoded over description
            content_el = item.find("{http://purl.org/rss/1.0/modules/content/}encoded")
            desc_el = item.find("description")
            summary_html = _text(content_el) if content_el is not None else _text(desc_el)

            pub_el = item.find("pubDate") or item.find("{http://purl.org/dc/elements/1.1/}date")
            published_at = _parse_date(_text(pub_el))
            articles.append({"url": url, "title": title,
                             "summary": _clean_html(summary_html) if summary_html else "",
                             "published_at": published_at})

    return articles


def _fetch_feed_raw(feed_cfg: dict) -> list[dict]:
    """Fetch one RSS/Atom feed URL and return pre-filtered article dicts."""
    name = feed_cfg["name"]
    url = feed_cfg["url"]
    try:
        resp = requests.get(url, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        raw_articles = _parse_feed_xml(resp.content, name)
    except Exception as exc:
        console.print(f"  [red]Failed to fetch feed {name}: {exc}[/red]")
        return []

    relevant = []
    for art in raw_articles:
        if not art.get("url"):
            continue
        probe = (art["title"] + " " + art["summary"]).lower()
        if _is_investment_relevant(probe):
            art["source"] = name
            relevant.append(art)

    return relevant


# ── Article scraper ────────────────────────────────────────────────────────────

def _scrape_article(url: str) -> Optional[str]:
    """Fetch and extract full article body text."""
    try:
        resp = requests.get(url, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT,
                            allow_redirects=True)
        resp.raise_for_status()
        if "text/html" not in resp.headers.get("Content-Type", ""):
            return None
        soup = BeautifulSoup(resp.text, "lxml")
        body = None
        for sel in ["article", "[class*='article-body']", "[class*='post-content']",
                    "[class*='entry-content']", "[class*='story-body']",
                    "main", "[role='main']"]:
            body = soup.select_one(sel)
            if body:
                break
        if body is None:
            body = soup.find("body") or soup
        return _clean_html(str(body))[:MAX_CONTENT_LENGTH]
    except Exception as exc:
        console.print(f"  [dim]Scrape failed ({url[:60]}): {exc}[/dim]")
        return None


# ── Public API ─────────────────────────────────────────────────────────────────

def fetch_all_feeds(verbose: bool = True) -> dict:
    """
    Fetch all configured RSS feeds, scrape full content, persist new articles.
    Returns summary counts.
    """
    db.init_db()
    total_fetched = 0
    total_new = 0

    for feed_cfg in RSS_FEEDS:
        name = feed_cfg["name"]
        if verbose:
            console.print(f"\n[bold cyan]Fetching:[/bold cyan] {name}")

        raw_articles = _fetch_feed_raw(feed_cfg)
        if verbose:
            console.print(f"  {len(raw_articles)} relevant articles found")

        for art in raw_articles:
            total_fetched += 1
            # Try to get full content
            full = _scrape_article(art["url"])
            time.sleep(0.3)
            content = full or art["summary"]

            new_id = db.upsert_article(
                url=art["url"],
                title=art["title"],
                content=content,
                summary=art["summary"],
                source=art["source"],
                published_at=art["published_at"],
            )
            if new_id:
                total_new += 1
                if verbose:
                    console.print(f"  [green]+[/green] {art['title'][:80]}")
            else:
                if verbose:
                    console.print(f"  [dim]~ (dup) {art['title'][:70]}[/dim]")

    return {"total_fetched": total_fetched, "total_new": total_new}
