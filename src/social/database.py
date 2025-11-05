"""
Database operations for social media posts.
"""

import sqlite3
from pathlib import Path
from typing import Optional, List, Dict
from datetime import datetime


class SocialDatabaseError(Exception):
    """Base exception for social database operations."""
    pass


def _get_connection(db_path: str):
    """Return SQLite connection with dict-like row access."""
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        raise SocialDatabaseError(f"Failed to connect to database: {e}") from e


def init_social_db(db_path: str = "data/articles.db") -> None:
    """
    Initialize social media tables in the database.

    Creates two tables:
    - social_posts: Main table for Twitter/Facebook posts
    - post_media: Table for media attachments (images, videos, etc.)
    """
    try:
        db_file = Path(db_path)
        db_file.parent.mkdir(parents=True, exist_ok=True)

        with _get_connection(db_path) as conn:
            # Social posts table
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS social_posts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    post_id TEXT UNIQUE NOT NULL,
                    platform TEXT NOT NULL,
                    game_name TEXT NOT NULL,
                    post_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    author TEXT,
                    author_handle TEXT,
                    post_url TEXT,
                    posted_at TIMESTAMP NOT NULL,

                    -- Engagement metrics
                    likes INTEGER DEFAULT 0,
                    retweets INTEGER DEFAULT 0,
                    comments INTEGER DEFAULT 0,
                    views INTEGER DEFAULT 0,

                    -- AI Processing
                    ai_summary TEXT,
                    ai_category TEXT,

                    -- Metadata
                    hashtags TEXT,
                    mentions TEXT,
                    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            # Post media table
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS post_media (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    post_id TEXT NOT NULL,
                    media_type TEXT NOT NULL,
                    media_url TEXT NOT NULL,
                    local_path TEXT,
                    youtube_id TEXT,
                    media_order INTEGER DEFAULT 0,
                    width INTEGER,
                    height INTEGER,
                    duration INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                    FOREIGN KEY (post_id) REFERENCES social_posts(post_id)
                )
                """
            )

            # Create indexes
            conn.execute("CREATE INDEX IF NOT EXISTS idx_post_id ON social_posts(post_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_platform ON social_posts(platform)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_game_name ON social_posts(game_name)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_posted_at ON social_posts(posted_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_media_post_id ON post_media(post_id)")

            conn.commit()
            print("✅ Social media database tables initialized")

    except sqlite3.Error as e:
        raise SocialDatabaseError(f"Failed to initialize database: {e}") from e


def insert_social_post(
    post_data: Dict,
    db_path: str = "data/articles.db"
) -> Optional[int]:
    """
    Insert or update a social media post.

    Args:
        post_data: Dictionary with post information
        db_path: Path to database file

    Returns:
        Post ID if successful, None otherwise
    """
    required_fields = ['post_id', 'platform', 'game_name', 'post_type', 'content', 'posted_at']
    for field in required_fields:
        if field not in post_data:
            raise ValueError(f"Missing required field: {field}")

    try:
        with _get_connection(db_path) as conn:
            cursor = conn.execute(
                """
                INSERT INTO social_posts (
                    post_id, platform, game_name, post_type, content,
                    author, author_handle, post_url, posted_at,
                    likes, retweets, comments, views,
                    hashtags, mentions
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(post_id) DO UPDATE SET
                    content = excluded.content,
                    likes = excluded.likes,
                    retweets = excluded.retweets,
                    comments = excluded.comments,
                    views = excluded.views,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    post_data['post_id'],
                    post_data['platform'],
                    post_data['game_name'],
                    post_data['post_type'],
                    post_data['content'],
                    post_data.get('author'),
                    post_data.get('author_handle'),
                    post_data.get('post_url'),
                    post_data['posted_at'],
                    post_data.get('likes', 0),
                    post_data.get('retweets', 0),
                    post_data.get('comments', 0),
                    post_data.get('views', 0),
                    post_data.get('hashtags'),
                    post_data.get('mentions')
                )
            )
            conn.commit()
            return cursor.lastrowid

    except sqlite3.IntegrityError as e:
        print(f"⚠️  Post already exists: {post_data['post_id']}")
        return None
    except sqlite3.Error as e:
        raise SocialDatabaseError(f"Failed to insert post: {e}") from e


def insert_post_media(
    media_data: Dict,
    db_path: str = "data/articles.db"
) -> Optional[int]:
    """
    Insert media attachment for a post.

    Args:
        media_data: Dictionary with media information
        db_path: Path to database file

    Returns:
        Media ID if successful, None otherwise
    """
    required_fields = ['post_id', 'media_type', 'media_url']
    for field in required_fields:
        if field not in media_data:
            raise ValueError(f"Missing required field: {field}")

    try:
        with _get_connection(db_path) as conn:
            cursor = conn.execute(
                """
                INSERT INTO post_media (
                    post_id, media_type, media_url, local_path,
                    youtube_id, media_order, width, height, duration
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    media_data['post_id'],
                    media_data['media_type'],
                    media_data['media_url'],
                    media_data.get('local_path'),
                    media_data.get('youtube_id'),
                    media_data.get('media_order', 0),
                    media_data.get('width'),
                    media_data.get('height'),
                    media_data.get('duration')
                )
            )
            conn.commit()
            return cursor.lastrowid

    except sqlite3.Error as e:
        raise SocialDatabaseError(f"Failed to insert media: {e}") from e


def get_social_posts(
    game_name: Optional[str] = None,
    platform: Optional[str] = None,
    limit: int = 50,
    db_path: str = "data/articles.db"
) -> List[Dict]:
    """
    Retrieve social media posts from database.

    Args:
        game_name: Filter by game name
        platform: Filter by platform ('twitter' or 'facebook')
        limit: Maximum number of posts to return
        db_path: Path to database file

    Returns:
        List of post dictionaries
    """
    try:
        with _get_connection(db_path) as conn:
            query = "SELECT * FROM social_posts WHERE 1=1"
            params = []

            if game_name:
                query += " AND game_name = ?"
                params.append(game_name)

            if platform:
                query += " AND platform = ?"
                params.append(platform)

            query += " ORDER BY posted_at DESC LIMIT ?"
            params.append(limit)

            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    except sqlite3.Error as e:
        raise SocialDatabaseError(f"Failed to retrieve posts: {e}") from e


def get_post_media(
    post_id: str,
    db_path: str = "data/articles.db"
) -> List[Dict]:
    """
    Retrieve media attachments for a specific post.

    Args:
        post_id: Post ID to get media for
        db_path: Path to database file

    Returns:
        List of media dictionaries
    """
    try:
        with _get_connection(db_path) as conn:
            cursor = conn.execute(
                """
                SELECT * FROM post_media
                WHERE post_id = ?
                ORDER BY media_order
                """,
                (post_id,)
            )
            return [dict(row) for row in cursor.fetchall()]

    except sqlite3.Error as e:
        raise SocialDatabaseError(f"Failed to retrieve media: {e}") from e


def get_post_count(
    game_name: Optional[str] = None,
    platform: Optional[str] = None,
    db_path: str = "data/articles.db"
) -> int:
    """Get count of social posts."""
    try:
        with _get_connection(db_path) as conn:
            query = "SELECT COUNT(*) as count FROM social_posts WHERE 1=1"
            params = []

            if game_name:
                query += " AND game_name = ?"
                params.append(game_name)

            if platform:
                query += " AND platform = ?"
                params.append(platform)

            cursor = conn.execute(query, params)
            return cursor.fetchone()['count']

    except sqlite3.Error as e:
        raise SocialDatabaseError(f"Failed to count posts: {e}") from e


def delete_old_social_posts(
    days: int = 30,
    db_path: str = "data/articles.db"
) -> int:
    """
    Delete social posts older than specified days.

    Args:
        days: Delete posts older than this many days
        db_path: Path to database file

    Returns:
        Number of posts deleted
    """
    try:
        with _get_connection(db_path) as conn:
            # First get post_ids to delete their media
            cursor = conn.execute(
                """
                SELECT post_id FROM social_posts
                WHERE posted_at < datetime('now', '-' || ? || ' days')
                """,
                (days,)
            )
            post_ids = [row['post_id'] for row in cursor.fetchall()]

            # Delete media for these posts
            if post_ids:
                placeholders = ','.join('?' * len(post_ids))
                conn.execute(
                    f"DELETE FROM post_media WHERE post_id IN ({placeholders})",
                    post_ids
                )

            # Delete the posts
            cursor = conn.execute(
                """
                DELETE FROM social_posts
                WHERE posted_at < datetime('now', '-' || ? || ' days')
                """,
                (days,)
            )

            deleted = cursor.rowcount
            conn.commit()
            return deleted

    except sqlite3.Error as e:
        raise SocialDatabaseError(f"Failed to delete old posts: {e}") from e
