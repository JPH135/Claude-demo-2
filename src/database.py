"""SQLite database layer for storing articles and analyzed investments."""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Generator

from src.config import DB_PATH


# ── Schema ─────────────────────────────────────────────────────────────────────

SCHEMA = """
CREATE TABLE IF NOT EXISTS articles (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    url          TEXT    UNIQUE NOT NULL,
    title        TEXT,
    content      TEXT,
    summary      TEXT,
    source       TEXT,
    published_at TEXT,
    fetched_at   TEXT    NOT NULL,
    analyzed     INTEGER DEFAULT 0  -- 0=pending, 1=investment found, 2=not relevant, 3=error
);

CREATE TABLE IF NOT EXISTS investments (
    id                          INTEGER PRIMARY KEY AUTOINCREMENT,
    article_id                  INTEGER REFERENCES articles(id),

    -- Company
    company_name                TEXT    NOT NULL,
    company_summary             TEXT,
    founding_year               INTEGER,
    country                     TEXT,
    city                        TEXT,
    technology_focus            TEXT,   -- JSON array
    customer_segment            TEXT,   -- B2B / B2C / B2B2C

    -- Deal
    stage                       TEXT,   -- Seed, Series A … Growth, PE
    round_type                  TEXT,   -- Venture Capital, Growth Equity, Private Equity
    deal_date                   TEXT,
    amount_raised_original      TEXT,   -- raw string from article
    amount_raised_eur_millions  REAL,
    amount_raised_usd_millions  REAL,
    pre_money_valuation_eur_m   REAL,
    post_money_valuation_eur_m  REAL,
    valuation_stated            TEXT,

    -- Investors
    lead_investors              TEXT,   -- JSON array
    new_investors               TEXT,   -- JSON array
    existing_investors          TEXT,   -- JSON array

    -- Extra
    key_metrics                 TEXT,   -- JSON object {metric: value}
    use_of_funds                TEXT,
    notable_details             TEXT,

    -- Meta
    source_url                  TEXT,
    analyzed_at                 TEXT    NOT NULL
);
"""


# ── Connection helper ──────────────────────────────────────────────────────────

@contextmanager
def get_conn() -> Generator[sqlite3.Connection, None, None]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """Create tables if they don't exist."""
    with get_conn() as conn:
        conn.executescript(SCHEMA)


# ── Articles ───────────────────────────────────────────────────────────────────

def upsert_article(
    url: str,
    title: str,
    content: str,
    summary: str,
    source: str,
    published_at: str,
) -> int | None:
    """Insert article; skip if URL already exists.  Returns new rowid or None."""
    now = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO articles (url, title, content, summary, source, published_at, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(url) DO NOTHING
            """,
            (url, title, content, summary, source, published_at, now),
        )
        return cur.lastrowid if cur.lastrowid else None


def get_pending_articles(limit: int = 50) -> list[dict]:
    """Return articles not yet analyzed."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM articles WHERE analyzed = 0 ORDER BY fetched_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


def mark_article(article_id: int, status: int) -> None:
    """Update analyzed flag (1=investment, 2=not relevant, 3=error)."""
    with get_conn() as conn:
        conn.execute(
            "UPDATE articles SET analyzed = ? WHERE id = ?",
            (status, article_id),
        )


def article_count() -> dict:
    with get_conn() as conn:
        row = conn.execute(
            """SELECT
                COUNT(*) as total,
                SUM(CASE WHEN analyzed=0 THEN 1 ELSE 0 END) as pending,
                SUM(CASE WHEN analyzed=1 THEN 1 ELSE 0 END) as with_investment,
                SUM(CASE WHEN analyzed=2 THEN 1 ELSE 0 END) as not_relevant
               FROM articles"""
        ).fetchone()
        return dict(row)


# ── Investments ────────────────────────────────────────────────────────────────

def insert_investment(article_id: int, data: dict[str, Any]) -> int:
    """Persist an analyzed investment record."""

    def _j(v):
        return json.dumps(v) if isinstance(v, (list, dict)) else v

    now = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO investments (
                article_id, company_name, company_summary, founding_year,
                country, city, technology_focus, customer_segment,
                stage, round_type, deal_date,
                amount_raised_original, amount_raised_eur_millions, amount_raised_usd_millions,
                pre_money_valuation_eur_m, post_money_valuation_eur_m, valuation_stated,
                lead_investors, new_investors, existing_investors,
                key_metrics, use_of_funds, notable_details,
                source_url, analyzed_at
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                article_id,
                data.get("company_name", ""),
                data.get("company_summary", ""),
                data.get("founding_year"),
                data.get("country", ""),
                data.get("city", ""),
                _j(data.get("technology_focus", [])),
                data.get("customer_segment", ""),
                data.get("stage", ""),
                data.get("round_type", ""),
                data.get("deal_date", ""),
                data.get("amount_raised_original", ""),
                data.get("amount_raised_eur_millions"),
                data.get("amount_raised_usd_millions"),
                data.get("pre_money_valuation_eur_m"),
                data.get("post_money_valuation_eur_m"),
                data.get("valuation_stated", ""),
                _j(data.get("lead_investors", [])),
                _j(data.get("new_investors", [])),
                _j(data.get("existing_investors", [])),
                _j(data.get("key_metrics", {})),
                data.get("use_of_funds", ""),
                data.get("notable_details", ""),
                data.get("source_url", ""),
                now,
            ),
        )
        return cur.lastrowid


def get_all_investments() -> list[dict]:
    """Return all investments joined with their source article."""
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT i.*, a.title AS article_title, a.url AS article_url,
                   a.source AS article_source, a.published_at
            FROM investments i
            JOIN articles a ON a.id = i.article_id
            ORDER BY i.analyzed_at DESC
            """
        ).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            for field in ("technology_focus", "lead_investors", "new_investors",
                          "existing_investors", "key_metrics"):
                try:
                    d[field] = json.loads(d[field]) if d[field] else ([] if field != "key_metrics" else {})
                except (json.JSONDecodeError, TypeError):
                    d[field] = [] if field != "key_metrics" else {}
            results.append(d)
        return results


def investment_count() -> dict:
    with get_conn() as conn:
        row = conn.execute(
            """SELECT
                COUNT(*) as total,
                SUM(amount_raised_eur_millions) as total_eur_millions,
                COUNT(DISTINCT country) as countries
               FROM investments"""
        ).fetchone()
        return dict(row)
