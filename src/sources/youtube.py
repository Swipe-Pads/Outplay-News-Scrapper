"""
YouTube collector — fetches latest videos from gaming channels via Data API v3.

Uses playlistItems.list (1 unit/req) instead of search.list (100 units/req)
to minimize API quota usage.
"""

import logging
from typing import List, Optional, Dict

from src.sources.base import BaseCollector, CollectedItem
from src.config import Config

logger = logging.getLogger(__name__)

# Channel configs: name -> channel ID
# Prefer hardcoded channel IDs (fewer API units, no flaky handle resolution);
# handles (@name) are resolved to channel IDs at first use only when no ID is known.
#
# Removed: "MobileGameplay"/Powerbang (UCqSeA-rZs6GOfZrs9jZRXtA, dead since Nov 2025)
#          Pocket Gamer channel (UCJKOvdk-nVzDAFR_9MF64sw, dormant)
YOUTUBE_CHANNELS = {
    "Techzamazing": "UCyo4ROy9-8ymQTBWcPA5Fjg",
    "RiseofMobileGames": None,       # @RiseofMobileGames
    "DowntoTop": None,               # @DowntoTop
    "iFerg": None,                    # @iFerg
    "ParkerTheSlayer": None,          # @ParkerTheSlayer2nd
    "GamingMobileGM": "UCCLVf7wyOpUmB63mVpJmU5w",
    "CallOfDutyMobile": "UCj9bJX9hh3pXjktcsOLJdgw",
    "BobbyPlays": None,               # @BobbyPlays
    "SnapdragonProSeries": "UC3wGgfxWJiIquQtSWlYfZcQ",  # ex-ESL Mobile (ESL rebrand)
    "OrangeJuice": "UC3S6nIDGJ5OtpC-mbvFA8Ew",
    "MobileGamingNews": "UCRW7gbgekVjxUOmKHBdz8Og",
    "BenTimm": "UCMYdLBEudBeU-c0AguEaiHA",
}

YOUTUBE_HANDLES = {
    "RiseofMobileGames": "@RiseofMobileGames",
    "DowntoTop": "@DowntoTop",
    "iFerg": "@iFerg",
    "ParkerTheSlayer": "@ParkerTheSlayer2nd",
    "BobbyPlays": "@BobbyPlays",
}


def _get_youtube_service():
    """Initialize YouTube API client."""
    if not Config.YOUTUBE_API_KEY or 'your_' in Config.YOUTUBE_API_KEY.lower():
        raise ValueError("YOUTUBE_API_KEY not configured in .env")

    from googleapiclient.discovery import build
    return build('youtube', 'v3', developerKey=Config.YOUTUBE_API_KEY)


def _resolve_handle_to_channel_id(service, handle: str) -> Optional[str]:
    """Resolve a @handle to a channel ID. Costs 1 API unit."""
    try:
        # Try forHandle parameter (YouTube API v3)
        response = service.channels().list(
            part='id',
            forHandle=handle.lstrip('@')
        ).execute()

        if response.get('items'):
            return response['items'][0]['id']

        # Fallback: search
        response = service.search().list(
            part='id',
            q=handle,
            type='channel',
            maxResults=1
        ).execute()

        if response.get('items'):
            return response['items'][0]['id']['channelId']

        return None
    except Exception as e:
        logger.warning(f"Failed to resolve handle {handle}: {e}")
        return None


def _get_uploads_playlist_id(channel_id: str) -> str:
    """Convert channel ID to uploads playlist ID (UC... -> UU...)."""
    if channel_id.startswith('UC'):
        return 'UU' + channel_id[2:]
    return channel_id


class YouTubeCollector(BaseCollector):
    """Collects latest videos from a YouTube channel."""

    source_type = "youtube"

    def __init__(self, name: str, channel_id: str = None, handle: str = None):
        self.source_name = name
        self._channel_id = channel_id
        self._handle = handle
        self._service = None
        self._resolved = channel_id is not None

    def _get_service(self):
        if self._service is None:
            self._service = _get_youtube_service()
        return self._service

    def _ensure_channel_id(self):
        """Resolve handle to channel ID if needed."""
        if self._resolved:
            return

        if self._handle:
            service = self._get_service()
            self._channel_id = _resolve_handle_to_channel_id(service, self._handle)
            if self._channel_id:
                logger.info(f"[{self.source_name}] Resolved {self._handle} -> {self._channel_id}")
            else:
                logger.error(f"[{self.source_name}] Failed to resolve handle: {self._handle}")

        self._resolved = True

    def discover(self, limit: int = 10) -> List[str]:
        """Get latest video IDs from channel's uploads playlist."""
        self._ensure_channel_id()
        if not self._channel_id:
            return []

        try:
            service = self._get_service()
            playlist_id = _get_uploads_playlist_id(self._channel_id)

            response = service.playlistItems().list(
                part='contentDetails',
                playlistId=playlist_id,
                maxResults=min(limit, 50)  # API max is 50
            ).execute()

            video_ids = []
            for item in response.get('items', []):
                vid = item['contentDetails']['videoId']
                video_ids.append(vid)

            logger.info(f"[{self.source_name}] Discovered {len(video_ids)} videos")
            return video_ids

        except Exception as e:
            logger.error(f"[{self.source_name}] Failed to discover videos: {e}")
            return []

    def collect(self, video_id: str) -> Optional[CollectedItem]:
        """Fetch video details. Costs 1 API unit."""
        try:
            service = self._get_service()

            response = service.videos().list(
                part='snippet,contentDetails,statistics',
                id=video_id
            ).execute()

            if not response.get('items'):
                return None

            snippet = response['items'][0]['snippet']

            # Get best thumbnail
            thumbnails = snippet.get('thumbnails', {})
            image_url = None
            for quality in ['maxres', 'high', 'medium', 'default']:
                if quality in thumbnails:
                    image_url = thumbnails[quality]['url']
                    break

            return CollectedItem(
                url=f"https://www.youtube.com/watch?v={video_id}",
                title=snippet.get('title', ''),
                date=snippet.get('publishedAt'),
                author=snippet.get('channelTitle'),
                content=snippet.get('description', ''),
                image_url=image_url,
                source_type='youtube',
                source_name=self.source_name,
                content_id=video_id,
            )

        except Exception as e:
            logger.error(f"[{self.source_name}] Failed to collect video {video_id}: {e}")
            return None


def get_youtube_collectors() -> List[YouTubeCollector]:
    """Get collectors for all configured YouTube channels."""
    collectors = []
    for name, channel_id in YOUTUBE_CHANNELS.items():
        handle = YOUTUBE_HANDLES.get(name)
        collectors.append(YouTubeCollector(
            name=name,
            channel_id=channel_id,
            handle=handle
        ))
    return collectors
