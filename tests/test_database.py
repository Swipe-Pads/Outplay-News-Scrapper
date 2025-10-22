"""
Automated tests for src/database.py
Run with: pytest -v
"""

import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path
import pytest
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src import database


@pytest.fixture(scope="function")
def temp_db(tmp_path):
    """Create a temporary database for each test."""
    db_path = tmp_path / "articles.db"
    database.init_db(str(db_path))
    yield str(db_path)
    # Cleanup handled by tmp_path fixture


def test_init_db_creates_file(temp_db):
    assert Path(temp_db).exists()


def test_insert_and_get_article(temp_db):
    article = {
        "url": "https://example.com/one",
        "title": "First Article",
        "date": "2025-10-22T10:00:00Z",
        "author": "Alice",
        "content": "Content here",
        "image_path": "images/one.jpg",
    }
    article_id = database.insert_article(article, temp_db)
    assert isinstance(article_id, int)

    fetched = database.get_article_by_url(article["url"], temp_db)
    assert fetched is not None
    assert fetched["title"] == article["title"]


def test_upsert_updates_existing(temp_db):
    article = {"url": "https://example.com/upsert", "title": "Old Title"}
    first_id = database.insert_article(article, temp_db)
    article["title"] = "New Title"
    second_id = database.insert_article(article, temp_db)
    assert first_id == second_id

    fetched = database.get_article_by_url(article["url"], temp_db)
    assert fetched["title"] == "New Title"

    count = database.get_article_count(temp_db)
    assert count == 1


def test_article_exists(temp_db):
    url = "https://example.com/exist"
    article = {"url": url, "title": "Exists Test"}
    database.insert_article(article, temp_db)

    assert database.article_exists(url, temp_db)
    assert not database.article_exists("https://example.com/none", temp_db)


def test_get_all_and_recent_articles(temp_db):
    # Insert several articles
    now = datetime.utcnow()
    articles = [
        {"url": f"https://example.com/{i}", "title": f"Article {i}"} for i in range(5)
    ]
    for a in articles:
        database.insert_article(a, temp_db)

    all_articles = database.get_all_articles(db_path=temp_db)
    assert len(all_articles) == 5

    recent_articles = database.get_recent_articles(30, temp_db)
    assert len(recent_articles) == 5

    # Manually backdate one article's scraped_at to 60 days ago
    with database._get_connection(temp_db) as conn:
        conn.execute(
            "UPDATE articles SET scraped_at = ? WHERE url = ?",
            ((now - timedelta(days=60)).isoformat(), articles[0]["url"]),
        )
        conn.commit()

    recent_articles = database.get_recent_articles(30, temp_db)
    assert len(recent_articles) == 4  # one should be excluded


def test_delete_old_articles(temp_db):
    # Insert two articles: one old, one recent
    old_url = "https://example.com/old"
    new_url = "https://example.com/new"
    database.insert_article({"url": old_url, "title": "Old"}, temp_db)
    database.insert_article({"url": new_url, "title": "New"}, temp_db)

    with database._get_connection(temp_db) as conn:
        conn.execute(
            "UPDATE articles SET scraped_at = ? WHERE url = ?",
            ((datetime.utcnow() - timedelta(days=40)).isoformat(), old_url),
        )
        conn.commit()

    deleted = database.delete_old_articles(30, temp_db)
    assert deleted == 1
    assert not database.article_exists(old_url, temp_db)
    assert database.article_exists(new_url, temp_db)


def test_missing_required_fields(temp_db):
    bad_article = {"url": "https://example.com/missing-title"}
    with pytest.raises(database.DatabaseError):
        database.insert_article(bad_article, temp_db)

    bad_article = {"title": "Missing URL"}
    with pytest.raises(database.DatabaseError):
        database.insert_article(bad_article, temp_db)
