"""Tests for src/scorer.py (mocked AI calls)."""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock

from src import database
from src.scorer import (
    normalize_title,
    title_similarity,
    cluster_articles,
    cluster_bonus,
    freshness_factor,
    quantitative_signal,
    ai_gamer_value_scores,
    _parse_ai_scores,
    compute_scores,
    score_recent_articles,
    NEUTRAL_AI_SCORE,
    FRESHNESS_FLOOR,
)


def _make_mock_response(text, input_tokens=100, output_tokens=20):
    response = MagicMock()
    response.content = [MagicMock(text=text)]
    response.usage.input_tokens = input_tokens
    response.usage.output_tokens = output_tokens
    return response


# === Title similarity & clustering ===

class TestTitleSimilarity:
    def test_normalize_strips_stopwords_and_case(self):
        tokens = normalize_title("The NEW Update is Here for Clash Royale!")
        assert 'clash' in tokens
        assert 'royale' in tokens
        assert 'the' not in tokens
        assert 'is' not in tokens

    def test_identical_titles(self):
        assert title_similarity("Clash Royale update", "Clash Royale update") == 1.0

    def test_unrelated_titles(self):
        sim = title_similarity(
            "Clash Royale removes card levels",
            "PUBG Mobile Naruto collab live"
        )
        assert sim < 0.2

    def test_similar_titles_cross_source(self):
        sim = title_similarity(
            "PUBG Mobile 4.5 Naruto Shippuden collab is live",
            "Naruto Shippuden collab goes live in PUBG Mobile 4.5"
        )
        assert sim >= 0.5

    def test_empty_titles(self):
        assert title_similarity("", "Something") == 0.0


class TestClustering:
    def test_cluster_sizes_for_same_story(self):
        articles = [
            {'title': "PUBG Mobile Naruto Shippuden collab live"},
            {'title': "Naruto Shippuden collab live in PUBG Mobile"},
            {'title': "Golden Lap releases on iOS"},
        ]
        sizes = cluster_articles(articles)
        assert sizes[0] == 2
        assert sizes[1] == 2
        assert sizes[2] == 1

    def test_empty_list(self):
        assert cluster_articles([]) == []

    def test_cluster_bonus_values(self):
        assert cluster_bonus(1) == 0.0
        assert cluster_bonus(2) > 0.0
        assert cluster_bonus(3) > cluster_bonus(2)


# === Freshness ===

class TestFreshness:
    def test_fresh_article_near_one(self):
        now = datetime.now(timezone.utc)
        article = {'date': now.isoformat()}
        assert freshness_factor(article, now) > 0.95

    def test_old_article_hits_floor(self):
        now = datetime.now(timezone.utc)
        article = {'date': (now - timedelta(days=60)).isoformat()}
        assert freshness_factor(article, now) == FRESHNESS_FLOOR

    def test_unknown_date_neutral(self):
        assert freshness_factor({'date': None}) == 0.7

    def test_falls_back_to_scraped_at(self):
        now = datetime.now(timezone.utc)
        article = {'date': None, 'scraped_at': now.strftime('%Y-%m-%d %H:%M:%S')}
        assert freshness_factor(article, now) > 0.9


# === Quantitative signal ===

class TestQuantitativeSignal:
    def test_reddit_score_used_when_present(self):
        low = quantitative_signal({'reddit_score': 5})
        high = quantitative_signal({'reddit_score': 5000})
        assert 0.0 < low < high <= 1.0

    def test_high_engagement_saturates(self):
        assert quantitative_signal({'reddit_score': 10_000_000}) == 1.0

    def test_content_proxies_without_engagement(self):
        rich = quantitative_signal({
            'content': 'x' * 1000, 'image_path': 'img.jpg', 'date': '2026-01-01'
        })
        poor = quantitative_signal({'content': ''})
        assert rich > poor

    def test_bounded_zero_to_one(self):
        assert 0.0 <= quantitative_signal({}) <= 1.0


# === AI scoring (mocked) ===

class TestAIScoring:
    @patch('src.summarizer.get_client')
    def test_scores_parsed_from_json_array(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _make_mock_response("[9, 2, 5]")
        mock_get_client.return_value = mock_client

        articles = [
            {'title': 'Big launch', 'content': 'c'},
            {'title': 'Studio funding round', 'content': 'c'},
            {'title': 'Minor patch', 'content': 'c'},
        ]
        scores = ai_gamer_value_scores(articles)
        assert scores == [9, 2, 5]

    @patch('src.summarizer.get_client')
    def test_malformed_response_falls_back_to_neutral(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _make_mock_response("no json here")
        mock_get_client.return_value = mock_client

        scores = ai_gamer_value_scores([{'title': 'A'}, {'title': 'B'}])
        assert scores == [NEUTRAL_AI_SCORE, NEUTRAL_AI_SCORE]

    def test_parse_clamps_out_of_range(self):
        assert _parse_ai_scores("[15, -3, 7]", 3) == [10, 0, 7]

    def test_parse_wrong_count_falls_back(self):
        assert _parse_ai_scores("[1, 2]", 3) == [NEUTRAL_AI_SCORE] * 3

    @patch('src.summarizer.get_client')
    def test_batching_splits_requests(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = [
            _make_mock_response(str(list(range(2)))),
            _make_mock_response("[5]"),
        ]
        mock_get_client.return_value = mock_client

        articles = [{'title': f'Article {i}'} for i in range(3)]
        scores = ai_gamer_value_scores(articles, batch_size=2)
        assert len(scores) == 3
        assert mock_client.messages.create.call_count == 2


# === Combined scoring ===

class TestComputeScores:
    def test_scores_in_range(self):
        now = datetime.now(timezone.utc).isoformat()
        articles = [
            {'title': 'Game launch', 'date': now, 'content': 'x' * 600},
            {'title': 'Completely different topic', 'date': now, 'content': ''},
        ]
        scores = compute_scores(articles, use_ai=False)
        assert len(scores) == 2
        assert all(0.0 <= s <= 100.0 for s in scores)

    def test_cross_source_story_scores_higher(self):
        now = datetime.now(timezone.utc).isoformat()
        articles = [
            {'title': 'PUBG Mobile Naruto collab live', 'date': now, 'content': 'x' * 600},
            {'title': 'Naruto collab live in PUBG Mobile', 'date': now, 'content': 'x' * 600},
            {'title': 'Some singleton unrelated story here', 'date': now, 'content': 'x' * 600},
        ]
        scores = compute_scores(articles, use_ai=False)
        assert scores[0] > scores[2]
        assert scores[1] > scores[2]

    def test_fresher_scores_higher(self):
        now = datetime.now(timezone.utc)
        articles = [
            {'title': 'Story one alpha beta', 'date': now.isoformat(), 'content': 'x' * 600},
            {'title': 'Unrelated gamma delta epsilon', 'date': (now - timedelta(days=6)).isoformat(),
             'content': 'x' * 600},
        ]
        scores = compute_scores(articles, use_ai=False)
        assert scores[0] > scores[1]

    @patch('src.scorer.ai_gamer_value_scores')
    def test_ai_score_dominates(self, mock_ai):
        mock_ai.return_value = [10, 0]
        now = datetime.now(timezone.utc).isoformat()
        articles = [
            {'title': 'Huge playable launch', 'date': now, 'content': 'x' * 600},
            {'title': 'Studio acquires other studio', 'date': now, 'content': 'x' * 600},
        ]
        scores = compute_scores(articles, use_ai=True)
        assert scores[0] > scores[1] + 30

    @patch('src.scorer.ai_gamer_value_scores')
    def test_ai_failure_falls_back_to_neutral(self, mock_ai):
        from src.summarizer import APIKeyError
        mock_ai.side_effect = APIKeyError("no key")
        articles = [{'title': 'A', 'date': None, 'content': ''}]
        scores = compute_scores(articles, use_ai=True)
        assert len(scores) == 1
        assert 0.0 <= scores[0] <= 100.0

    def test_empty_input(self):
        assert compute_scores([]) == []


# === Persistence (fake DB) ===

class TestScoreRecentArticles:
    @pytest.fixture
    def temp_db(self, tmp_path):
        db_path = tmp_path / "test.db"
        database.init_db(str(db_path))
        return str(db_path)

    def test_scores_persisted_to_importance_score(self, temp_db):
        database.insert_article({
            'url': 'https://example.com/1', 'title': 'Big game launch today',
            'content': 'x' * 600, 'date': datetime.now(timezone.utc).isoformat(),
        }, temp_db)

        stats = score_recent_articles(days=7, db_path=temp_db, use_ai=False)
        assert stats['scored'] == 1
        assert stats['failed'] == 0

        article = database.get_article_by_url('https://example.com/1', temp_db)
        assert article['importance_score'] is not None
        assert 0.0 <= article['importance_score'] <= 100.0

    def test_no_articles_is_noop(self, temp_db):
        stats = score_recent_articles(days=7, db_path=temp_db, use_ai=False)
        assert stats == {'total': 0, 'scored': 0, 'failed': 0}

    def test_top_scored_query_orders_desc(self, temp_db):
        now = datetime.now(timezone.utc).isoformat()
        for i, title in enumerate([
            'PUBG Mobile Naruto collab live',
            'Naruto collab live in PUBG Mobile',
            'Random unrelated one-off story',
        ]):
            database.insert_article({
                'url': f'https://example.com/{i}', 'title': title,
                'content': 'x' * 600, 'date': now,
            }, temp_db)

        score_recent_articles(days=7, db_path=temp_db, use_ai=False)
        top = database.get_top_scored_articles(days=7, limit=10, db_path=temp_db)
        assert len(top) == 3
        scores = [a['importance_score'] for a in top]
        assert scores == sorted(scores, reverse=True)
