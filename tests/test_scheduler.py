"""Tests for src/scheduler.py"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.scheduler import (
    write_pid,
    remove_pid,
    scrape_job,
    export_job,
    cleanup_job,
    health_check,
    create_scheduler,
    PID_FILE,
)


# === PID management ===

class TestPidManagement:
    def test_write_and_remove_pid(self, tmp_path, monkeypatch):
        pid_file = tmp_path / "test.pid"
        monkeypatch.setattr('src.scheduler.PID_FILE', pid_file)

        write_pid()
        assert pid_file.exists()
        content = pid_file.read_text()
        assert content.isdigit()

        remove_pid()
        assert not pid_file.exists()

    def test_remove_nonexistent_pid(self, tmp_path, monkeypatch):
        pid_file = tmp_path / "nonexistent.pid"
        monkeypatch.setattr('src.scheduler.PID_FILE', pid_file)
        remove_pid()  # should not raise


# === scrape_job (now uses scrape_all_sources) ===

class TestScrapeJob:
    @patch('src.scheduler.scrape_all_sources')
    @patch('src.scheduler.init_db')
    def test_scrape_job_calls_all_sources(self, mock_init, mock_scrape):
        mock_scrape.return_value = {
            'total': 10, 'success': 8, 'skipped': 1, 'failed': 1
        }
        scrape_job(limit=10, summarize=False)

        mock_init.assert_called_once()
        mock_scrape.assert_called_once()
        call_kwargs = mock_scrape.call_args[1]
        assert call_kwargs['limit'] == 10
        assert call_kwargs['summarize'] is False

    @patch('src.scheduler.scrape_all_sources')
    @patch('src.scheduler.init_db')
    def test_scrape_job_handles_exception(self, mock_init, mock_scrape):
        mock_scrape.side_effect = RuntimeError("boom")
        scrape_job()  # should not raise


# === export_job ===

class TestExportJob:
    @patch('src.scheduler.export')
    def test_export_job_calls_export(self, mock_export):
        mock_export.return_value = {'article_count': 5}
        export_job(format='json')
        mock_export.assert_called_once_with(format='json', validate=True)

    @patch('src.scheduler.export')
    def test_export_job_handles_exception(self, mock_export):
        mock_export.side_effect = RuntimeError("fail")
        export_job()  # should not raise


# === cleanup_job ===

class TestCleanupJob:
    @patch('src.scheduler.run_cleanup')
    def test_cleanup_job_calls_cleanup(self, mock_cleanup):
        mock_cleanup.return_value = {
            'articles_deleted': 2, 'images_deleted': 1, 'orphans_deleted': 0
        }
        cleanup_job(days=30)
        mock_cleanup.assert_called_once_with(days=30, dry_run=False)

    @patch('src.scheduler.run_cleanup')
    def test_cleanup_job_handles_exception(self, mock_cleanup):
        mock_cleanup.side_effect = RuntimeError("fail")
        cleanup_job()  # should not raise


# === health_check ===

class TestHealthCheck:
    @patch('src.scheduler.get_article_count')
    @patch('src.scheduler.init_db')
    def test_health_check_ok(self, mock_init, mock_count, tmp_path, monkeypatch):
        from src.config import Config
        db_path = tmp_path / "data" / "articles.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        db_path.write_bytes(b"x" * 100)
        monkeypatch.setattr(Config, 'DATABASE_FULL_PATH', db_path)

        mock_count.return_value = 42
        result = health_check()
        assert result is True

    @patch('src.scheduler.init_db')
    def test_health_check_fail(self, mock_init):
        mock_init.side_effect = RuntimeError("db fail")
        result = health_check()
        assert result is False


# === create_scheduler ===

class TestCreateScheduler:
    def test_creates_scheduler_with_jobs(self):
        scheduler = create_scheduler(
            scrape_hours=6, scrape_limit=15,
            summarize=False, enable_export=True,
            enable_cleanup=True
        )
        jobs = scheduler.get_jobs()
        job_ids = [j.id for j in jobs]
        assert 'scrape_job' in job_ids
        assert 'export_job' in job_ids
        assert 'cleanup_job' in job_ids
        assert 'health_check' in job_ids

    def test_creates_scheduler_without_optional_jobs(self):
        scheduler = create_scheduler(
            enable_export=False, enable_cleanup=False
        )
        job_ids = [j.id for j in scheduler.get_jobs()]
        assert 'scrape_job' in job_ids
        assert 'export_job' not in job_ids
        assert 'cleanup_job' not in job_ids
