"""
Google Trends API client for auto-discovery and prioritisation.

Uses the Google Trends API (v1alpha) to:
- Run daily pulse checks on all tracked games
- Detect search interest spikes (potential news events)
- Prioritise which games to scrape harder
- Support auto-discovery of trending games

The API is async (long-running operations) — all requests return an Operation
that must be polled via operations.get until done.

Requires OAuth2 with scope: https://www.googleapis.com/auth/searchtrends
"""

import json
import logging
import os
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from dotenv import load_dotenv

logger = logging.getLogger(__name__)
load_dotenv()

# API constants
API_BASE_URL = "https://searchtrends.googleapis.com/v1alpha"
SCOPES = ["https://www.googleapis.com/auth/searchtrends"]
API_SERVICE_NAME = "searchtrends"
API_VERSION = "v1alpha"

# Quota limits (alpha)
DAILY_REQUEST_LIMIT = 100
DAILY_POINTS_LIMIT = 10000
POLL_INTERVAL = 1.0  # seconds between operation polls
MAX_POLL_ATTEMPTS = 15

# Spike detection thresholds
SPIKE_THRESHOLD_PCT = 30  # % increase week-over-week to flag as spike
HIGH_SPIKE_THRESHOLD_PCT = 80  # % increase for high-priority spike


class TrendsError(Exception):
    """Base error for Trends API operations."""
    pass


class TrendsQuotaError(TrendsError):
    """Raised when quota limits are exceeded."""
    pass


class TrendsClient:
    """
    Google Trends API v1alpha client.

    Handles OAuth2 authentication, async operation polling, and provides
    high-level methods for game trend analysis.

    Auth options (in priority order):
    1. Service account JSON file (GOOGLE_TRENDS_SERVICE_ACCOUNT_PATH)
    2. OAuth2 credentials file (GOOGLE_TRENDS_CREDENTIALS_PATH) + token cache
    3. Application Default Credentials (gcloud auth application-default login)
    """

    def __init__(self):
        """Initialize Trends client with Google API credentials."""
        self.service = None
        self.requests_used = 0
        self.points_used = 0
        self._init_service()

    def _init_service(self):
        """Build the Google API service client."""
        try:
            import googleapiclient.discovery

            # Try service account first (best for automation)
            sa_path = os.getenv("GOOGLE_TRENDS_SERVICE_ACCOUNT_PATH")
            if sa_path and os.path.exists(sa_path):
                from google.oauth2 import service_account
                credentials = service_account.Credentials.from_service_account_file(
                    sa_path, scopes=SCOPES
                )
                self.service = googleapiclient.discovery.build(
                    API_SERVICE_NAME, API_VERSION, credentials=credentials
                )
                logger.info("Trends client initialised with service account")
                return

            # Try OAuth2 credentials file + cached token
            creds_path = os.getenv("GOOGLE_TRENDS_CREDENTIALS_PATH")
            token_path = os.getenv(
                "GOOGLE_TRENDS_TOKEN_PATH",
                os.path.join(os.path.dirname(__file__), "..", "data", "trends_token.json")
            )

            if creds_path and os.path.exists(creds_path):
                from google.oauth2.credentials import Credentials
                from google_auth_oauthlib.flow import InstalledAppFlow

                creds = None
                if os.path.exists(token_path):
                    creds = Credentials.from_authorized_user_file(token_path, SCOPES)

                if not creds or not creds.valid:
                    if creds and creds.expired and creds.refresh_token:
                        from google.auth.transport.requests import Request
                        creds.refresh(Request())
                    else:
                        flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
                        creds = flow.run_local_server(port=0)

                    # Cache the token
                    os.makedirs(os.path.dirname(token_path), exist_ok=True)
                    with open(token_path, "w") as f:
                        f.write(creds.to_json())

                self.service = googleapiclient.discovery.build(
                    API_SERVICE_NAME, API_VERSION, credentials=creds
                )
                logger.info("Trends client initialised with OAuth2 credentials")
                return

            # Fall back to Application Default Credentials
            import google.auth
            credentials, project = google.auth.default(scopes=SCOPES)
            self.service = googleapiclient.discovery.build(
                API_SERVICE_NAME, API_VERSION, credentials=credentials
            )
            logger.info("Trends client initialised with ADC")

        except ImportError as e:
            raise TrendsError(
                f"Missing Google API dependencies. Install with: "
                f"pip install google-api-python-client google-auth-oauthlib google-auth-httplib2\n"
                f"Error: {e}"
            )
        except Exception as e:
            raise TrendsError(f"Failed to initialise Trends client: {e}")

    def _check_quota(self, points: int = 0):
        """Check if we have quota remaining."""
        if self.requests_used >= DAILY_REQUEST_LIMIT:
            raise TrendsQuotaError(
                f"Daily request limit reached ({DAILY_REQUEST_LIMIT})"
            )
        if self.points_used + points > DAILY_POINTS_LIMIT:
            raise TrendsQuotaError(
                f"Would exceed daily points limit ({self.points_used + points}/{DAILY_POINTS_LIMIT})"
            )

    def _poll_operation(self, operation: dict) -> dict:
        """
        Poll a long-running operation until complete.

        Args:
            operation: Initial operation response from fetchTimeSeries/fetchGeoBreakdown.

        Returns:
            Completed operation response with data.

        Raises:
            TrendsError: If operation fails or times out.
        """
        op_name = operation.get("name", "")
        if not op_name:
            raise TrendsError("Operation has no name field")

        # Prefix with operations/ if needed
        if not op_name.startswith("operations/"):
            op_name = f"operations/{op_name}"

        for attempt in range(MAX_POLL_ATTEMPTS):
            try:
                result = self.service.operations().get(name=op_name).execute()

                if result.get("done"):
                    if "error" in result:
                        error = result["error"]
                        raise TrendsError(
                            f"Operation failed: {error.get('message', str(error))}"
                        )
                    return result

                time.sleep(POLL_INTERVAL)

            except TrendsError:
                raise
            except Exception as e:
                logger.warning(f"Poll attempt {attempt + 1} failed: {e}")
                time.sleep(POLL_INTERVAL * 2)

        raise TrendsError(f"Operation timed out after {MAX_POLL_ATTEMPTS} attempts")

    # ─── CORE API METHODS ────────────────────────────────────────

    def fetch_time_series(
        self,
        term: str,
        geo_code: str = "US",
        days: int = 30,
        resolution: str = "WEEK",
        term_type: str = "BROAD",
    ) -> List[dict]:
        """
        Fetch time series of search interest for a term.

        Args:
            term: Search term (e.g., "PUBG Mobile").
            geo_code: ISO 3166-1 country code (e.g., "US", "GB").
            days: How many days back to query (max 1800).
            resolution: DAY, WEEK, MONTH, or YEAR.
            term_type: BROAD, ORDERED, or EXACT.

        Returns:
            List of time series points with searchInterest and scaledSearchInterest.
        """
        self._check_quota()

        end_time = datetime.utcnow() - timedelta(days=2)  # API lag
        start_time = end_time - timedelta(days=days)

        request = {
            "spec": {
                "expression": {
                    "terms": [{"value": term, "type": term_type}]
                },
                "geo": {
                    "type": "GEO_TYPE_COUNTRY_OR_REGION",
                    "code": geo_code,
                },
                "timeRange": {
                    "startTime": start_time.strftime("%Y-%m-%dT00:00:00Z"),
                    "endTime": end_time.strftime("%Y-%m-%dT00:00:00Z"),
                },
                "timeResolution": resolution,
            }
        }

        try:
            operation = self.service.v1alpha().fetchTimeSeries(body=request).execute()
            self.requests_used += 1

            result = self._poll_operation(operation)
            points = result.get("response", {}).get("timeSeries", {}).get("points", [])

            # Track quota
            self.points_used += len(points)
            logger.info(f"Fetched {len(points)} time series points for '{term}' ({geo_code})")

            return points

        except TrendsError:
            raise
        except Exception as e:
            raise TrendsError(f"fetchTimeSeries failed for '{term}': {e}")

    def fetch_geo_breakdown(
        self,
        term: str,
        geo_code: str = "US",
        days: int = 30,
        breakdown: str = "GEO_TYPE_ADMINISTRATIVE_AREA1",
        term_type: str = "BROAD",
    ) -> List[dict]:
        """
        Fetch geographical breakdown of search interest.

        Args:
            term: Search term.
            geo_code: Top-level geo to break down.
            days: How many days back.
            breakdown: Resolution for sub-geos.
            term_type: BROAD, ORDERED, or EXACT.

        Returns:
            List of geo breakdown points.
        """
        self._check_quota()

        end_time = datetime.utcnow() - timedelta(days=2)
        start_time = end_time - timedelta(days=days)

        request = {
            "spec": {
                "expression": {
                    "terms": [{"value": term, "type": term_type}]
                },
                "geo": {
                    "type": "GEO_TYPE_COUNTRY_OR_REGION",
                    "code": geo_code,
                },
                "timeRange": {
                    "startTime": start_time.strftime("%Y-%m-%dT00:00:00Z"),
                    "endTime": end_time.strftime("%Y-%m-%dT00:00:00Z"),
                },
                "breakdownResolution": breakdown,
                "zeroOutNoisyResults": True,
            }
        }

        try:
            operation = self.service.v1alpha().fetchGeoBreakdown(body=request).execute()
            self.requests_used += 1

            result = self._poll_operation(operation)
            points = result.get("response", {}).get("geoBreakdown", {}).get("points", [])

            self.points_used += len(points)
            logger.info(f"Fetched {len(points)} geo breakdown points for '{term}' ({geo_code})")

            return points

        except TrendsError:
            raise
        except Exception as e:
            raise TrendsError(f"fetchGeoBreakdown failed for '{term}': {e}")

    # ─── HIGH-LEVEL GAME ANALYSIS ────────────────────────────────

    def get_game_pulse(
        self,
        game_names: List[str],
        geo_code: str = "US",
    ) -> List[dict]:
        """
        Run a weekly pulse check on multiple games.

        Fetches last 4 weeks of weekly data for each game and calculates
        week-over-week change to detect spikes.

        Args:
            game_names: List of game names to check.
            geo_code: Country to check trends in.

        Returns:
            List of dicts sorted by spike magnitude (highest first):
            [
                {
                    "game": "Free Fire",
                    "current_interest": 72.5,
                    "previous_interest": 45.0,
                    "change_pct": 61.1,
                    "is_spike": True,
                    "priority": "high",
                    "raw_points": [...],
                },
                ...
            ]
        """
        results = []

        for game in game_names:
            try:
                self._check_quota()

                points = self.fetch_time_series(
                    term=game,
                    geo_code=geo_code,
                    days=28,  # 4 weeks
                    resolution="WEEK",
                )

                if len(points) < 2:
                    logger.warning(f"Not enough data points for '{game}', skipping")
                    results.append({
                        "game": game,
                        "current_interest": 0,
                        "previous_interest": 0,
                        "change_pct": 0,
                        "is_spike": False,
                        "priority": "normal",
                        "raw_points": points,
                    })
                    continue

                # Get last two complete weeks
                # Filter out partial points
                complete = [p for p in points if not p.get("isPartial", False)]
                if len(complete) < 2:
                    complete = points[-2:]

                current = complete[-1].get("searchInterest", 0)
                previous = complete[-2].get("searchInterest", 0)

                # Calculate week-over-week change
                if previous > 0:
                    change_pct = ((current - previous) / previous) * 100
                elif current > 0:
                    change_pct = 100.0  # From zero to something = spike
                else:
                    change_pct = 0.0

                # Classify spike
                is_spike = change_pct >= SPIKE_THRESHOLD_PCT
                if change_pct >= HIGH_SPIKE_THRESHOLD_PCT:
                    priority = "high"
                elif change_pct >= SPIKE_THRESHOLD_PCT:
                    priority = "elevated"
                else:
                    priority = "normal"

                results.append({
                    "game": game,
                    "current_interest": round(current, 2),
                    "previous_interest": round(previous, 2),
                    "change_pct": round(change_pct, 1),
                    "is_spike": is_spike,
                    "priority": priority,
                    "raw_points": points,
                })

                logger.info(
                    f"  {game}: interest={current:.1f} "
                    f"(change={change_pct:+.1f}%, priority={priority})"
                )

            except TrendsQuotaError:
                logger.warning(f"Quota exhausted, stopping pulse check at '{game}'")
                break
            except TrendsError as e:
                logger.error(f"Failed to check trends for '{game}': {e}")
                results.append({
                    "game": game,
                    "current_interest": 0,
                    "previous_interest": 0,
                    "change_pct": 0,
                    "is_spike": False,
                    "priority": "normal",
                    "raw_points": [],
                    "error": str(e),
                })

        # Sort by change magnitude (biggest spikes first)
        results.sort(key=lambda r: abs(r["change_pct"]), reverse=True)

        return results

    def get_scraping_priorities(
        self,
        game_names: List[str],
        geo_code: str = "US",
        base_limit: int = 10,
        spike_limit: int = 25,
        high_spike_limit: int = 40,
    ) -> Dict[str, dict]:
        """
        Get scraping priorities based on trends data.

        Returns a dict mapping game names to their scraping parameters:
        - limit: how many articles to scrape
        - priority: normal/elevated/high
        - reason: why this priority was assigned

        Args:
            game_names: Games to check.
            geo_code: Country for trends check.
            base_limit: Default article limit per game.
            spike_limit: Article limit for spiking games.
            high_spike_limit: Article limit for high-spike games.

        Returns:
            Dict mapping game name to priority config.
        """
        logger.info(f"Calculating scraping priorities for {len(game_names)} games...")

        pulse = self.get_game_pulse(game_names, geo_code)

        priorities = {}
        for result in pulse:
            game = result["game"]

            if result["priority"] == "high":
                priorities[game] = {
                    "limit": high_spike_limit,
                    "priority": "high",
                    "change_pct": result["change_pct"],
                    "reason": f"High spike: {result['change_pct']:+.1f}% WoW",
                }
            elif result["priority"] == "elevated":
                priorities[game] = {
                    "limit": spike_limit,
                    "priority": "elevated",
                    "change_pct": result["change_pct"],
                    "reason": f"Spike: {result['change_pct']:+.1f}% WoW",
                }
            else:
                priorities[game] = {
                    "limit": base_limit,
                    "priority": "normal",
                    "change_pct": result["change_pct"],
                    "reason": "Baseline",
                }

        return priorities

    def get_quota_status(self) -> dict:
        """Get current quota usage."""
        return {
            "requests_used": self.requests_used,
            "requests_remaining": DAILY_REQUEST_LIMIT - self.requests_used,
            "points_used": self.points_used,
            "points_remaining": DAILY_POINTS_LIMIT - self.points_used,
        }


def get_trends_client() -> Optional[TrendsClient]:
    """
    Convenience function to create a Trends client.

    Returns None if credentials are not configured (graceful degradation).
    """
    try:
        return TrendsClient()
    except TrendsError as e:
        logger.warning(f"Trends client not available: {e}")
        return None


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    client = get_trends_client()
    if not client:
        print("Trends client not available. Check credentials.")
        exit(1)

    print("Running pulse check on Outplay games...")
    games = [
        "Call of Duty Mobile",
        "Free Fire",
        "Brawl Stars",
        "Mobile Legends",
        "PUBG Mobile",
        "Wild Rift",
    ]

    pulse = client.get_game_pulse(games)

    print("\n" + "=" * 60)
    print("GAME PULSE REPORT")
    print("=" * 60)
    for r in pulse:
        spike_flag = " *** SPIKE ***" if r["is_spike"] else ""
        print(
            f"  {r['game']:30s}  interest={r['current_interest']:6.1f}  "
            f"change={r['change_pct']:+6.1f}%  [{r['priority']}]{spike_flag}"
        )

    print(f"\nQuota: {client.get_quota_status()}")
