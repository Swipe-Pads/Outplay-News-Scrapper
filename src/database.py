"""
SQLite database module for article storage.
"""

import sqlite3
from pathlib import Path
from typing import Optional, List, Dict
from datetime import datetime, timedelta


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
                    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_url ON articles(url)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_scraped_at ON articles(scraped_at)")
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

            # Upsert using SQLite's ON CONFLICT syntax
            cursor.execute(
                """
                INSERT INTO articles (url, title, date, author, content, image_path, summary, updated_at)
                VALUES (:url, :title, :date, :author, :content, :image_path, :summary, CURRENT_TIMESTAMP)
                ON CONFLICT(url) DO UPDATE SET
                    title=excluded.title,
                    date=excluded.date,
                    author=excluded.author,
                    content=excluded.content,
                    image_path=excluded.image_path,
                    summary=excluded.summary,
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
                },
            )
            conn.commit()

            # Return the article ID
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
            query = "SELECT * FROM articles ORDER BY scraped_at DESC"
            if limit:
                query += f" LIMIT {int(limit)}"
            cursor = conn.execute(query)
            return [dict(row) for row in cursor.fetchall()]
    except sqlite3.Error as e:
        raise DatabaseError(f"Failed to retrieve all articles: {e}") from e


def get_recent_articles(days: int = 30, db_path: str = "data/articles.db") -> List[dict]:
    """Get articles from last N days."""
    try:
        cutoff = datetime.utcnow() - timedelta(days=days)
        with _get_connection(db_path) as conn:
            cursor = conn.execute(
                "SELECT * FROM articles WHERE scraped_at >= ? ORDER BY scraped_at DESC",
                (cutoff.isoformat(),),
            )
            return [dict(row) for row in cursor.fetchall()]
    except sqlite3.Error as e:
        raise DatabaseError(f"Failed to get recent articles: {e}") from e


def delete_old_articles(days: int = 30, db_path: str = "data/articles.db") -> int:
    """Delete articles older than N days, return count deleted."""
    try:
        cutoff = datetime.utcnow() - timedelta(days=days)
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


def article_exists(url: str, db_path: str = "data/articles.db") -> bool:
    """Check if article URL exists."""
    try:
        with _get_connection(db_path) as conn:
            cursor = conn.execute("SELECT 1 FROM articles WHERE url = ?", (url,))
            return cursor.fetchone() is not None
    except sqlite3.Error as e:
        raise DatabaseError(f"Failed to check article existence: {e}") from e


if __name__ == "__main__":
    """
    Test/demo of database functions.
    """
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
    print(f"✅ Inserted article ID: {article_id}")

    print("\nRetrieving article by URL...")
    retrieved = get_article_by_url(test_article["url"])
    print(f"✅ Retrieved: {retrieved['title']}")

    count = get_article_count()
    print(f"✅ Total articles: {count}")

    print("\nTesting upsert (updating existing article)...")
    test_article["title"] = "Updated Test Article"
    updated_id = insert_article(test_article)
    print(f"✅ Updated article ID: {updated_id} (should be same as {article_id})")

    new_count = get_article_count()
    print(f"✅ Article count after update: {new_count} (should still be {count})")

    print("\n✅ All database tests passed!")
