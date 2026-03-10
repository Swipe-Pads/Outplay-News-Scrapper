"""
SQLite database module for article storage.
Supports migration to add new columns for Strapi integration.
"""

import sqlite3
from pathlib import Path
from typing import Optional, List, Dict
from datetime import datetime, timedelta


class DatabaseError(Exception):
    """Base exception for database operations."""
    pass


def _get_connection(db_path: str = "data/articles.db"):
    """Return SQLite connection with dict-like row access."""
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        raise DatabaseError(f"Failed to connect to database: {e}") from e


def init_db(db_path: str = "data/articles.db") -> None:
    """Initialize database with full schema including new columns."""
    try:
        db_file = Path(db_path)
        db_file.parent.mkdir(parents=True, exist_ok=True)

        with _get_connection(db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS articles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT UNIQUE NOT NULL,
                    title TEXT NOT NULL,
                    date TEXT,
                    author TEXT,
                    content TEXT,
                    image_path TEXT,
                    summary TEXT,
                    source_name TEXT DEFAULT 'Unknown',
                    content_type TEXT DEFAULT 'news',
                    game_slug TEXT,
                    body_rewritten TEXT,
                    relevance_score REAL DEFAULT 0.0,
                    strapi_id INTEGER,
                    strapi_synced_at TEXT,
                    video_url TEXT,
                    image_url TEXT,
                    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_url ON articles(url)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_scraped_at ON articles(scraped_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_game_slug ON articles(game_slug)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_strapi_id ON articles(strapi_id)")
            conn.commit()

            # Run migration for existing databases
            _migrate(conn)
    except sqlite3.Error as e:
        raise DatabaseError(f"Database initialization failed: {e}") from e


def _migrate(conn):
    """Add new columns to existing tables (backward compatible)."""
    new_columns = [
        ("source_name", "TEXT DEFAULT 'Unknown'"),
        ("content_type", "TEXT DEFAULT 'news'"),
        ("game_slug", "TEXT"),
        ("body_rewritten", "TEXT"),
        ("relevance_score", "REAL DEFAULT 0.0"),
        ("strapi_id", "INTEGER"),
        ("strapi_synced_at", "TEXT"),
        ("video_url", "TEXT"),
        ("image_url", "TEXT"),
    ]

    # Get existing columns
    cursor = conn.execute("PRAGMA table_info(articles)")
    existing = {row[1] for row in cursor.fetchall()}

    for col_name, col_type in new_columns:
        if col_name not in existing:
            try:
                conn.execute(f"ALTER TABLE articles ADD COLUMN {col_name} {col_type}")
                conn.commit()
            except sqlite3.OperationalError:
                pass  # Column already exists


def insert_article(article: dict, db_path: str = "data/articles.db") -> int:
    """Insert or update article (upsert by URL)."""
    if not article.get("url") or not article.get("title"):
        raise DatabaseError("Missing required fields: 'url' and 'title'")

    try:
        with _get_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO articles (url, title, date, author, content, image_path,
                    summary, source_name, content_type, game_slug, body_rewritten,
                    relevance_score, video_url, image_url, updated_at)
                VALUES (:url, :title, :date, :author, :content, :image_path,
                    :summary, :source_name, :content_type, :game_slug, :body_rewritten,
                    :relevance_score, :video_url, :image_url, CURRENT_TIMESTAMP)
                ON CONFLICT(url) DO UPDATE SET
                    title=excluded.title,
                    date=excluded.date,
                    author=excluded.author,
                    content=excluded.content,
                    image_path=COALESCE(excluded.image_path, articles.image_path),
                    summary=COALESCE(excluded.summary, articles.summary),
                    source_name=COALESCE(excluded.source_name, articles.source_name),
                    content_type=COALESCE(excluded.content_type, articles.content_type),
                    game_slug=COALESCE(excluded.game_slug, articles.game_slug),
                    body_rewritten=COALESCE(excluded.body_rewritten, articles.body_rewritten),
                    relevance_score=COALESCE(excluded.relevance_score, articles.relevance_score),
                    video_url=COALESCE(excluded.video_url, articles.video_url),
                    image_url=COALESCE(excluded.image_url, articles.image_url),
                    updated_at=CURRENT_TIMESTAMP
            """, {
                "url": article.get("url"),
                "title": article.get("title"),
                "date": article.get("date"),
                "author": article.get("author"),
                "content": article.get("content"),
                "image_path": article.get("image_path"),
                "summary": article.get("summary"),
                "source_name": article.get("source_name", "Unknown"),
                "content_type": article.get("content_type", "news"),
                "game_slug": article.get("game_slug"),
                "body_rewritten": article.get("body_rewritten"),
                "relevance_score": article.get("relevance_score", 0.0),
                "video_url": article.get("video_url"),
                "image_url": article.get("image_url"),
            })
            conn.commit()

            cursor.execute("SELECT id FROM articles WHERE url = ?", (article["url"],))
            row = cursor.fetchone()
            return row["id"] if row else None

    except sqlite3.Error as e:
        raise DatabaseError(f"Failed to insert/update article: {e}") from e


def get_article_by_url(url: str, db_path: str = "data/articles.db") -> Optional[dict]:
    """Get article by URL."""
    try:
        with _get_connection(db_path) as conn:
            cursor = conn.execute("SELECT * FROM articles WHERE url = ?", (url,))
            row = cursor.fetchone()
            return dict(row) if row else None
    except sqlite3.Error as e:
        raise DatabaseError(f"Failed to retrieve article: {e}") from e


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
        raise DatabaseError(f"Failed to retrieve articles: {e}") from e


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


def get_unsummarized_articles(limit: int = 50, db_path: str = "data/articles.db") -> List[dict]:
    """Get articles that haven't been AI-summarized yet."""
    try:
        with _get_connection(db_path) as conn:
            cursor = conn.execute(
                "SELECT * FROM articles WHERE summary IS NULL AND content IS NOT NULL "
                "ORDER BY scraped_at DESC LIMIT ?",
                (limit,),
            )
            return [dict(row) for row in cursor.fetchall()]
    except sqlite3.Error as e:
        raise DatabaseError(f"Failed to get unsummarized articles: {e}") from e


def get_unsynced_articles(limit: int = 50, db_path: str = "data/articles.db") -> List[dict]:
    """Get articles not yet pushed to Strapi."""
    try:
        with _get_connection(db_path) as conn:
            cursor = conn.execute(
                "SELECT * FROM articles WHERE strapi_id IS NULL AND summary IS NOT NULL "
                "ORDER BY relevance_score DESC, scraped_at DESC LIMIT ?",
                (limit,),
            )
            return [dict(row) for row in cursor.fetchall()]
    except sqlite3.Error as e:
        raise DatabaseError(f"Failed to get unsynced articles: {e}") from e


def mark_synced_to_strapi(article_url: str, strapi_id: int, db_path: str = "data/articles.db") -> None:
    """Mark article as synced to Strapi."""
    try:
        with _get_connection(db_path) as conn:
            conn.execute(
                "UPDATE articles SET strapi_id = ?, strapi_synced_at = CURRENT_TIMESTAMP WHERE url = ?",
                (strapi_id, article_url),
            )
            conn.commit()
    except sqlite3.Error as e:
        raise DatabaseError(f"Failed to mark article synced: {e}") from e


def update_article_summary(url: str, summary_data: dict, db_path: str = "data/articles.db") -> None:
    """Update article with AI-generated summary data."""
    try:
        with _get_connection(db_path) as conn:
            conn.execute("""
                UPDATE articles SET
                    title = COALESCE(?, title),
                    summary = ?,
                    body_rewritten = ?,
                    content_type = COALESCE(?, content_type),
                    relevance_score = COALESCE(?, relevance_score),
                    updated_at = CURRENT_TIMESTAMP
                WHERE url = ?
            """, (
                summary_data.get("title"),
                summary_data.get("summary"),
                summary_data.get("body"),
                summary_data.get("content_type"),
                summary_data.get("relevance_score"),
                url,
            ))
            conn.commit()
    except sqlite3.Error as e:
        raise DatabaseError(f"Failed to update summary: {e}") from e


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
        raise DatabaseError(f"Failed to check existence: {e}") from e


if __name__ == "__main__":
    print("Initializing database...")
    init_db()
    count = get_article_count()
    print(f"✅ Database ready. {count} articles.")
