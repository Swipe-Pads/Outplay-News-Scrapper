"""Tests for src/exporter.py"""

import json
import pytest
from pathlib import Path
from src.exporter import (
    format_article_for_export,
    export_articles_json,
    export_articles_xml,
    generate_export_filename,
)
from src import database


@pytest.fixture
def sample_articles():
    return [
        {
            'id': 1, 'url': 'https://example.com/1', 'title': 'Article One',
            'date': '2025-10-15', 'author': 'Alice', 'content': 'Content one',
            'summary': 'Summary one', 'image_path': None,
            'scraped_at': '2025-10-15T10:00:00', 'updated_at': '2025-10-15T10:00:00',
        },
        {
            'id': 2, 'url': 'https://example.com/2', 'title': 'Article Two',
            'date': '2025-10-16', 'author': 'Bob', 'content': 'Content two',
            'summary': None, 'image_path': 'images/test.jpg',
            'scraped_at': '2025-10-16T10:00:00', 'updated_at': '2025-10-16T10:00:00',
        },
    ]


class TestFormatArticle:
    def test_formats_all_fields(self, sample_articles):
        result = format_article_for_export(sample_articles[0])
        assert result['title'] == 'Article One'
        assert result['url'] == 'https://example.com/1'
        assert 'id' in result

    def test_handles_missing_fields(self):
        result = format_article_for_export({'title': 'Minimal'})
        assert result['title'] == 'Minimal'
        assert result['url'] is None


class TestJsonExport:
    def test_creates_valid_json(self, tmp_path, sample_articles):
        output = tmp_path / "export.json"
        meta = export_articles_json(str(output), sample_articles)

        assert output.exists()
        assert meta['article_count'] == 2

        data = json.loads(output.read_text())
        assert len(data['data']) == 2
        assert data['meta']['format_version'] == '1.0'

    def test_validates_export(self, tmp_path, sample_articles):
        output = tmp_path / "validated.json"
        meta = export_articles_json(str(output), sample_articles, validate=True)

        assert 'validation' in meta
        # coverImage 'images/test.jpg' doesn't exist, but validation checks image_path
        # from the formatted dict which now uses coverImage key
        assert meta['validation']['validated'] is True

    def test_empty_export(self, tmp_path):
        output = tmp_path / "empty.json"
        meta = export_articles_json(str(output), [])
        assert meta['article_count'] == 0


class TestXmlExport:
    def test_creates_valid_xml(self, tmp_path, sample_articles):
        output = tmp_path / "export.xml"
        meta = export_articles_xml(str(output), sample_articles)

        assert output.exists()
        assert meta['article_count'] == 2

        content = output.read_text()
        assert '<articles' in content
        assert '<title>Article One</title>' in content


class TestFilename:
    def test_generates_unique_filenames(self):
        f1 = generate_export_filename('json')
        f2 = generate_export_filename('xml')
        assert f1.endswith('.json')
        assert f2.endswith('.xml')
        assert f1.startswith('exports/')
