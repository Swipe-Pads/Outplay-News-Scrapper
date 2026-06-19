"""Tests for src/sources/youtube.py"""

import pytest
from unittest.mock import patch, MagicMock

from src.sources.youtube import (
    YouTubeCollector,
    _get_uploads_playlist_id,
    _resolve_handle_to_channel_id,
    YOUTUBE_CHANNELS,
    YOUTUBE_HANDLES,
    get_youtube_collectors,
)


class TestUploadsPlaylistId:
    def test_converts_uc_to_uu(self):
        assert _get_uploads_playlist_id("UCyo4ROy9-8ymQTBWcPA5Fjg") == "UUyo4ROy9-8ymQTBWcPA5Fjg"

    def test_non_uc_prefix_unchanged(self):
        assert _get_uploads_playlist_id("PLsomething") == "PLsomething"


class TestResolveHandle:
    @patch('src.sources.youtube._get_youtube_service')
    def test_resolve_via_for_handle(self, mock_svc_factory):
        mock_service = MagicMock()
        mock_channels = MagicMock()
        mock_channels.list.return_value.execute.return_value = {
            'items': [{'id': 'UC_RESOLVED'}]
        }
        mock_service.channels.return_value = mock_channels

        result = _resolve_handle_to_channel_id(mock_service, "@TestHandle")
        assert result == "UC_RESOLVED"

    @patch('src.sources.youtube._get_youtube_service')
    def test_resolve_fallback_to_search(self, mock_svc_factory):
        mock_service = MagicMock()

        mock_channels = MagicMock()
        mock_channels.list.return_value.execute.return_value = {'items': []}
        mock_service.channels.return_value = mock_channels

        mock_search = MagicMock()
        mock_search.list.return_value.execute.return_value = {
            'items': [{'id': {'channelId': 'UC_SEARCH'}}]
        }
        mock_service.search.return_value = mock_search

        result = _resolve_handle_to_channel_id(mock_service, "@Unknown")
        assert result == "UC_SEARCH"

    def test_resolve_returns_none_on_error(self):
        mock_service = MagicMock()
        mock_service.channels.return_value.list.side_effect = Exception("API error")
        result = _resolve_handle_to_channel_id(mock_service, "@Broken")
        assert result is None


class TestYouTubeCollector:
    def test_init_with_channel_id(self):
        c = YouTubeCollector("Test", channel_id="UC123")
        assert c.source_type == "youtube"
        assert c.source_name == "Test"
        assert c._resolved is True

    def test_init_with_handle(self):
        c = YouTubeCollector("Test", handle="@test")
        assert c._resolved is False

    @patch('src.sources.youtube._get_youtube_service')
    def test_discover_returns_video_ids(self, mock_svc_factory):
        mock_service = MagicMock()
        mock_svc_factory.return_value = mock_service
        mock_service.playlistItems.return_value.list.return_value.execute.return_value = {
            'items': [
                {'contentDetails': {'videoId': 'vid1'}},
                {'contentDetails': {'videoId': 'vid2'}},
            ]
        }

        c = YouTubeCollector("Test", channel_id="UCabc")
        ids = c.discover(limit=10)
        assert ids == ['vid1', 'vid2']

    def test_discover_without_channel_id(self):
        c = YouTubeCollector("Test", channel_id=None, handle=None)
        c._resolved = True
        ids = c.discover(limit=5)
        assert ids == []

    @patch('src.sources.youtube._get_youtube_service')
    def test_collect_returns_item(self, mock_svc_factory):
        mock_service = MagicMock()
        mock_svc_factory.return_value = mock_service
        mock_service.videos.return_value.list.return_value.execute.return_value = {
            'items': [{
                'snippet': {
                    'title': 'Video Title',
                    'publishedAt': '2025-01-01T00:00:00Z',
                    'channelTitle': 'Channel',
                    'description': 'Description',
                    'thumbnails': {'high': {'url': 'https://img.com/thumb.jpg'}},
                }
            }]
        }

        c = YouTubeCollector("Test", channel_id="UCabc")
        item = c.collect("vid1")
        assert item is not None
        assert item.title == 'Video Title'
        assert item.source_type == 'youtube'
        assert 'vid1' in item.url
        assert item.content_id == 'vid1'

    @patch('src.sources.youtube._get_youtube_service')
    def test_collect_returns_none_on_empty(self, mock_svc_factory):
        mock_service = MagicMock()
        mock_svc_factory.return_value = mock_service
        mock_service.videos.return_value.list.return_value.execute.return_value = {
            'items': []
        }

        c = YouTubeCollector("Test", channel_id="UCabc")
        assert c.collect("missing") is None


class TestGetYouTubeCollectors:
    def test_returns_all_channels(self):
        collectors = get_youtube_collectors()
        assert len(collectors) == len(YOUTUBE_CHANNELS)
        for c in collectors:
            assert c.source_type == 'youtube'
