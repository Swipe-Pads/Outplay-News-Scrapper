"""
SQLite database module for article storage.
"""

import json
import sqlite3
from pathlib import Path
from typing import Optional, List, Dict
from datetime import datetime, timedelta, timezone


class DatabaseError(Exception):
    """Base exception for database operations."""
    pass


def _get_connection(db_path: str):
    """Return SQLite connection with dict-like row access."""
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        raise DatabaseError(f"Failed to connect to database: {e}") from e


def init_db(db_path: str = "data/articles.db") -> None:
    """Initialize database and create tables if they don't exist."""
    try:
        db_file = Path(db_path)
        db_file.parent.mkdir(parents=True, exist_ok=True)

        with _get_connection(db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS articles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT UNIQUE NOT NULL,
                    title TEXT NOT NULL,
                    date TEXT,
                    author TEXT,
                    content TEXT,
                    image_path TEXT,
                    summary TEXT,
                    source_type TEXT DEFAULT 'website',
                    source_name TEXT DEFAULT 'pocketgamer',
                    content_id TEXT,
                    importance_score REAL,
                    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_url ON articles(url)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_scraped_at ON articles(scraped_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_source_type ON articles(source_type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_source_name ON articles(source_name)")

            # Migrate existing tables — add new columns if missing
            cursor = conn.execute("PRAGMA table_info(articles)")
            columns = {row[1] for row in cursor.fetchall()}
            if 'source_type' not in columns:
                conn.execute("ALTER TABLE articles ADD COLUMN source_type TEXT DEFAULT 'website'")
            if 'source_name' not in columns:
                conn.execute("ALTER TABLE articles ADD COLUMN source_name TEXT DEFAULT 'pocketgamer'")
            if 'content_id' not in columns:
                conn.execute("ALTER TABLE articles ADD COLUMN content_id TEXT")
            if 'strapi_id' not in columns:
                conn.execute("ALTER TABLE articles ADD COLUMN strapi_id INTEGER")
            if 'importance_score' not in columns:
                conn.execute("ALTER TABLE articles ADD COLUMN importance_score REAL")
            if 'entities' not in columns:
                # JSON blob: games, companies, platforms, event_type, release_date, price
                conn.execute("ALTER TABLE articles ADD COLUMN entities TEXT")

            conn.commit()
    except sqlite3.Error as e:
        raise DatabaseError(f"Database initialization failed: {e}") from e


def insert_article(article: dict, db_path: str = "data/articles.db") -> int:
    """Insert or update article (upsert by URL)."""
    if not article.get("url") or not article.get("title"):
        raise DatabaseError("Missing required fields: 'url' and 'title' are mandatory.")

    try:
        with _get_connection(db_path) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            cursor = conn.cursor()

            entities = article.get("entities")
            if isinstance(entities, dict):
                entities = json.dumps(entities, ensure_ascii=False) if entities else None

            cursor.execute(
                """
                INSERT INTO articles (url, title, date, author, content, image_path, summary,
                                      source_type, source_name, content_id, entities, updated_at)
                VALUES (:url, :title, :date, :author, :content, :image_path, :summary,
                        :source_type, :source_name, :content_id, :entities, CURRENT_TIMESTAMP)
                ON CONFLICT(url) DO UPDATE SET
                    title=excluded.title,
                    date=excluded.date,
                    author=excluded.author,
                    content=excluded.content,
                    image_path=excluded.image_path,
                    summary=excluded.summary,
                    source_type=excluded.source_type,
                    source_name=excluded.source_name,
                    content_id=excluded.content_id,
                    -- keep previously extracted facts when a re-scrape has none
                    entities=COALESCE(excluded.entities, articles.entities),
                    updated_at=CURRENT_TIMESTAMP
                """,
                {
                    "url": article.get("url"),
                    "title": article.get("title"),
                    "date": article.get("date"),
                    "author": article.get("author"),
                    "content": article.get("content"),
                    "image_path": article.get("image_path"),
                    "summary": article.get("summary"),
                    "source_type": article.get("source_type", "website"),
                    "source_name": article.get("source_name", "unknown"),
                    "content_id": article.get("content_id"),
                    "entities": entities,
                },
            )
            conn.commit()

            cursor.execute("SELECT id FROM articles WHERE url = ?", (article["url"],))
            row = cursor.fetchone()
            return row["id"] if row else None

    except sqlite3.Error as e:
        raise DatabaseError(f"Failed to insert or update article: {e}") from e


def get_article_by_url(url: str, db_path: str = "data/articles.db") -> Optional[dict]:
    """Get article by URL."""
    try:
        with _get_connection(db_path) as conn:
            cursor = conn.execute("SELECT * FROM articles WHERE url = ?", (url,))
            row = cursor.fetchone()
            return dict(row) if row else None
    except sqlite3.Error as e:
        raise DatabaseError(f"Failed to retrieve article by URL: {e}") from e


def get_all_articles(limit: int = None, db_path: str = "data/articles.db") -> List[dict]:
    """Get all articles, newest first."""
    try:
        with _get_connection(db_path) as conn:
            if limit:
                cursor = conn.execute(
                    "SELECT * FROM articles ORDER BY scraped_at DESC LIMIT ?",
                    (int(limit),)
                )
            else:
                cursor = conn.execute("SELECT * FROM articles ORDER BY scraped_at DESC")
            return [dict(row) for row in cursor.fetchall()]
    except sqlite3.Error as e:
        raise DatabaseError(f"Failed to retrieve all articles: {e}") from e


def get_articles_by_source(
    source_type: str = None, source_name: str = None,
    limit: int = None, db_path: str = "data/articles.db"
) -> List[dict]:
    """Get articles filtered by source_type and/or source_name."""
    try:
        with _get_connection(db_path) as conn:
            query = "SELECT * FROM articles WHERE 1=1"
            params = []
            if source_type:
                query += " AND source_type = ?"
                params.append(source_type)
            if source_name:
                query += " AND source_name = ?"
                params.append(source_name)
            query += " ORDER BY scraped_at DESC"
            if limit:
                query += " LIMIT ?"
                params.append(int(limit))
            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
    except sqlite3.Error as e:
        raise DatabaseError(f"Failed to retrieve articles by source: {e}") from e


def get_articles_without_summary(limit: int = None, db_path: str = "data/articles.db") -> List[dict]:
    """Get articles that don't have a summary yet."""
    try:
        with _get_connection(db_path) as conn:
            if limit:
                cursor = conn.execute(
                    "SELECT * FROM articles WHERE summary IS NULL AND content IS NOT NULL ORDER BY scraped_at DESC LIMIT ?",
                    (int(limit),)
                )
            else:
                cursor = conn.execute(
                    "SELECT * FROM articles WHERE summary IS NULL AND content IS NOT NULL ORDER BY scraped_at DESC"
                )
            return [dict(row) for row in cursor.fetchall()]
    except sqlite3.Error as e:
        raise DatabaseError(f"Failed to retrieve unsummarized articles: {e}") from e


def update_article_summary(
    url: str,
    summary: str,
    db_path: str = "data/articles.db",
    entities: dict = None,
) -> bool:
    """Update the summary field for an article, optionally with extracted entities."""
    try:
        with _get_connection(db_path) as conn:
            if entities:
                cursor = conn.execute(
                    "UPDATE articles SET summary = ?, entities = ?, "
                    "updated_at = CURRENT_TIMESTAMP WHERE url = ?",
                    (summary, json.dumps(entities, ensure_ascii=False), url)
                )
            else:
                cursor = conn.execute(
                    "UPDATE articles SET summary = ?, updated_at = CURRENT_TIMESTAMP WHERE url = ?",
                    (summary, url)
                )
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        raise DatabaseError(f"Failed to update article summary: {e}") from e


def update_article_score(url: str, score: float, db_path: str = "data/articles.db") -> bool:
    """Update the importance_score field for an article."""
    try:
        with _get_connection(db_path) as conn:
            cursor = conn.execute(
                "UPDATE articles SET importance_score = ?, updated_at = CURRENT_TIMESTAMP WHERE url = ?",
                (score, url)
            )
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        raise DatabaseError(f"Failed to update article score: {e}") from e


def get_top_scored_articles(
    days: int = 7, limit: int = 30, db_path: str = "data/articles.db"
) -> List[dict]:
    """Get highest-scored articles from the last N days (importance_score DESC)."""
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        with _get_connection(db_path) as conn:
            cursor = conn.execute(
                """
                SELECT * FROM articles
                WHERE scraped_at >= ? AND importance_score IS NOT NULL
                ORDER BY importance_score DESC, scraped_at DESC
                LIMIT ?
                """,
                (cutoff.strftime('%Y-%m-%d %H:%M:%S'), int(limit)),
            )
            return [dict(row) for row in cursor.fetchall()]
    except sqlite3.Error as e:
        raise DatabaseError(f"Failed to get top scored articles: {e}") from e


def get_recent_articles(days: int = 30, db_path: str = "data/articles.db") -> List[dict]:
    """Get articles from last N days."""
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        with _get_connection(db_path) as conn:
            cursor = conn.execute(
                "SELECT * FROM articles WHERE scraped_at >= ? ORDER BY scraped_at DESC",
                (cutoff.isoformat(),),
            )
            return [dict(row) for row in cursor.fetchall()]
    except sqlite3.Error as e:
        raise DatabaseError(f"Failed to get recent articles: {e}") from e


def get_old_articles(days: int = 30, db_path: str = "data/articles.db") -> List[dict]:
    """Get articles older than N days."""
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        with _get_connection(db_path) as conn:
            cursor = conn.execute(
                "SELECT * FROM articles WHERE scraped_at < ? ORDER BY scraped_at ASC",
                (cutoff.isoformat(),),
            )
            return [dict(row) for row in cursor.fetchall()]
    except sqlite3.Error as e:
        raise DatabaseError(f"Failed to get old articles: {e}") from e


def delete_old_articles(days: int = 30, db_path: str = "data/articles.db") -> int:
    """Delete articles older than N days, return count deleted."""
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        with _get_connection(db_path) as conn:
            cursor = conn.execute("DELETE FROM articles WHERE scraped_at < ?", (cutoff.isoformat(),))
            conn.commit()
            return cursor.rowcount
    except sqlite3.Error as e:
        raise DatabaseError(f"Failed to delete old articles: {e}") from e


def get_article_count(db_path: str = "data/articles.db") -> int:
    """Return total article count."""
    try:
        with _get_connection(db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) AS count FROM articles")
            row = cursor.fetchone()
            return row["count"] if row else 0
    except sqlite3.Error as e:
        raise DatabaseError(f"Failed to count articles: {e}") from e


def get_articles_not_synced(limit: int = None, db_path: str = "data/articles.db") -> List[dict]:
    """Get articles that haven't been synced to Strapi (strapi_id IS NULL)."""
    try:
        with _get_connection(db_path) as conn:
            query = "SELECT * FROM articles WHERE strapi_id IS NULL ORDER BY scraped_at DESC"
            if limit:
                query += " LIMIT ?"
                cursor = conn.execute(query, (int(limit),))
            else:
                cursor = conn.execute(query)
            return [dict(row) for row in cursor.fetchall()]
    except sqlite3.Error as e:
        raise DatabaseError(f"Failed to get unsynced articles: {e}") from e


def update_article_strapi_id(article_id: int, strapi_id: int, db_path: str = "data/articles.db") -> bool:
    """Set the strapi_id for a local article after successful sync."""
    try:
        with _get_connection(db_path) as conn:
            cursor = conn.execute(
                "UPDATE articles SET strapi_id = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (strapi_id, article_id)
            )
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        raise DatabaseError(f"Failed to update strapi_id: {e}") from e


def article_exists(url: str, db_path: str = "data/articles.db") -> bool:
    """Check if article URL exists."""
    try:
        with _get_connection(db_path) as conn:
            cursor = conn.execute("SELECT 1 FROM articles WHERE url = ?", (url,))
            return cursor.fetchone() is not None
    except sqlite3.Error as e:
        raise DatabaseError(f"Failed to check article existence: {e}") from e


if __name__ == "__main__":
    print("Initializing database...")
    init_db()

    test_article = {
        "url": "https://example.com/test-article",
        "title": "Test Article",
        "date": "2025-10-22T10:00:00Z",
        "author": "Test Author",
        "content": "This is test content for the article.",
        "image_path": "images/test.jpg",
    }

    print("Inserting test article...")
    article_id = insert_article(test_article)
    print(f"Inserted article ID: {article_id}")

    print("\nRetrieving article by URL...")
    retrieved = get_article_by_url(test_article["url"])
    print(f"Retrieved: {retrieved['title']}")

    count = get_article_count()
    print(f"Total articles: {count}")

    print("\nAll database tests passed!")
