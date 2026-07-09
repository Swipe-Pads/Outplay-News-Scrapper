"""Tests for src/image_generator.py (real Pillow rendering, inspected PNG)."""

import pytest
from datetime import datetime, timezone
from PIL import Image

from src.image_generator import (
    generate_cover_image,
    extract_topic_tags,
    find_cover_for_digest,
    COVER_WIDTH,
    COVER_HEIGHT,
    COLOR_BACKGROUND,
    MAX_TAGS,
)


class TestGenerateCoverImage:
    def test_file_produced_with_date_name(self, tmp_path):
        date = datetime(2026, 7, 6, tzinfo=timezone.utc)
        path = generate_cover_image(date=date, tags=['COD MOBILE'], output_dir=tmp_path)

        assert path.exists()
        assert path.name == '2026-07-06-cover.png'

    def test_png_dimensions_1200x630(self, tmp_path):
        path = generate_cover_image(
            date=datetime(2026, 7, 6, tzinfo=timezone.utc),
            tags=['PUBG MOBILE', 'CLASH ROYALE', 'POKEMON GO'],
            output_dir=tmp_path,
        )
        with Image.open(path) as img:
            assert img.format == 'PNG'
            assert img.size == (COVER_WIDTH, COVER_HEIGHT)

    def test_background_brand_color(self, tmp_path):
        path = generate_cover_image(
            date=datetime(2026, 7, 6, tzinfo=timezone.utc), output_dir=tmp_path
        )
        with Image.open(path) as img:
            # Corner pixel (outside the card) must be the brand background
            expected = tuple(
                int(COLOR_BACKGROUND[i:i + 2], 16) for i in (1, 3, 5)
            )
            assert img.convert('RGB').getpixel((5, 5)) == expected

    def test_no_tags_still_renders(self, tmp_path):
        path = generate_cover_image(
            date=datetime(2026, 7, 6, tzinfo=timezone.utc), tags=[], output_dir=tmp_path
        )
        assert path.exists()

    def test_extra_tags_dropped(self, tmp_path):
        # More than MAX_TAGS + very long tags must not crash or overflow
        tags = [f'A VERY LONG TOPIC TAG NUMBER {i}' for i in range(6)]
        path = generate_cover_image(
            date=datetime(2026, 7, 6, tzinfo=timezone.utc), tags=tags, output_dir=tmp_path
        )
        assert path.exists()


class TestExtractTopicTags:
    def test_takes_lead_phrase_before_delimiter(self):
        articles = [
            {'title': 'PUBG Mobile 4.5 — Naruto collab is live'},
            {'title': 'Clash Royale: card levels removed'},
            {'title': 'Pokemon GO turns 10 | anniversary stream'},
        ]
        tags = extract_topic_tags(articles)
        assert tags[0].startswith('PUBG MOBILE')
        assert tags[1].startswith('CLASH ROYALE')
        assert tags[2].startswith('POKEMON GO')

    def test_caps_at_max_tags(self):
        articles = [{'title': f'Game {i} news'} for i in range(10)]
        assert len(extract_topic_tags(articles)) == MAX_TAGS

    def test_truncates_long_titles(self):
        articles = [{'title': 'An Extremely Long Game Title That Never Ends At All'}]
        tags = extract_topic_tags(articles)
        assert len(tags[0]) <= 23  # 22 chars + ellipsis

    def test_dedupes_and_skips_empty(self):
        articles = [
            {'title': 'Same Game: update one'},
            {'title': 'Same Game: update two'},
            {'title': ''},
        ]
        assert extract_topic_tags(articles) == ['SAME GAME']


class TestFindCoverForDigest:
    def test_finds_matching_cover(self, tmp_path):
        digest = tmp_path / '2026-07-06-digest.html'
        digest.write_text('<p>x</p>', encoding='utf-8')
        cover = tmp_path / '2026-07-06-cover.png'
        cover.write_bytes(b'png')

        assert find_cover_for_digest(digest) == cover

    def test_none_when_cover_missing(self, tmp_path):
        digest = tmp_path / '2026-07-06-digest.html'
        digest.write_text('<p>x</p>', encoding='utf-8')
        assert find_cover_for_digest(digest) is None

    def test_none_for_non_digest_file(self, tmp_path):
        other = tmp_path / 'random.html'
        other.write_text('x', encoding='utf-8')
        assert find_cover_for_digest(other) is None
