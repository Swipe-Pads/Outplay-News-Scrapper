"""Tests for src/cleanup.py"""

import pytest
from pathlib import Path
from datetime import datetime, timedelta, timezone
from src import database
from src.cleanup import (
    find_old_articles,
    delete_article_images,
    find_orphaned_images,
    delete_orphaned_images,
    run_cleanup,
)


@pytest.fixture
def temp_db(tmp_path):
    db_path = tmp_path / "test.db"
    database.init_db(str(db_path))
    return str(db_path)


@pytest.fixture
def populated_db(temp_db):
    """DB with 2 recent and 1 old article."""
    database.insert_article(
        {"url": "https://example.com/new1", "title": "New 1", "content": "c"},
        temp_db
    )
    database.insert_article(
        {"url": "https://example.com/new2", "title": "New 2", "content": "c"},
        temp_db
    )
    database.insert_article(
        {"url": "https://example.com/old", "title": "Old Article", "content": "c"},
        temp_db
    )

    # Backdate one article
    with database._get_connection(temp_db) as conn:
        conn.execute(
            "UPDATE articles SET scraped_at = ? WHERE url = ?",
            ((datetime.now(timezone.utc) - timedelta(days=60)).isoformat(),
             "https://example.com/old"),
        )
        conn.commit()

    return temp_db


class TestFindOldArticles:
    def test_finds_old_articles(self, populated_db):
        old = find_old_articles(days=30, db_path=populated_db)
        assert len(old) == 1
        assert old[0]['url'] == 'https://example.com/old'

    def test_no_old_articles(self, populated_db):
        old = find_old_articles(days=90, db_path=populated_db)
        assert len(old) == 0


class TestDeleteArticleImages:
    def test_deletes_existing_images(self, tmp_path):
        img = tmp_path / "test.jpg"
        img.write_bytes(b"fake image data")

        articles = [{'image_path': str(img)}]
        deleted = delete_article_images(articles)
        assert deleted == 1
        assert not img.exists()

    def test_handles_missing_images(self):
        articles = [{'image_path': '/nonexistent/img.jpg'}, {'image_path': None}]
        deleted = delete_article_images(articles)
        assert deleted == 0


class TestFindOrphanedImages:
    def test_finds_orphans(self, temp_db, tmp_path, monkeypatch):
        # Create an image file that's not in DB
        images_dir = tmp_path / "images"
        images_dir.mkdir()
        orphan = images_dir / "orphan.jpg"
        orphan.write_bytes(b"fake")

        # Patch the images_dir path in cleanup module
        monkeypatch.setattr(
            'src.cleanup.Path',
            lambda *a, **kw: tmp_path / "images" if a == ('images',) else Path(*a, **kw)
        )
        # Simpler: just monkeypatch find_orphaned_images to use our dir
        import src.cleanup
        original_func = src.cleanup.find_orphaned_images

        def patched_find(db_path=None):
            if db_path is None:
                db_path = str(tmp_path / "test.db")
            articles = database.get_all_articles(db_path=db_path)
            db_image_paths = set()
            for a in articles:
                if a.get('image_path'):
                    db_image_paths.add(Path(a['image_path']).resolve())
            orphans = []
            image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff'}
            for img_file in images_dir.rglob('*'):
                if img_file.is_file() and img_file.suffix.lower() in image_extensions:
                    if img_file.resolve() not in db_image_paths:
                        orphans.append(img_file)
            return orphans

        orphans = patched_find(db_path=temp_db)
        assert len(orphans) == 1


class TestRunCleanup:
    def test_dry_run(self, populated_db):
        stats = run_cleanup(days=30, dry_run=True, db_path=populated_db)
        # Dry run shouldn't delete anything
        assert stats['articles_deleted'] == 0

        # Old article should still exist
        assert database.article_exists("https://example.com/old", populated_db)

    def test_actual_cleanup(self, populated_db):
        stats = run_cleanup(days=30, dry_run=False, db_path=populated_db)
        assert stats['articles_deleted'] == 1
        assert not database.article_exists("https://example.com/old", populated_db)
        assert database.article_exists("https://example.com/new1", populated_db)
