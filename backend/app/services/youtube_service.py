"""
YouTube Service
Handles YouTube OAuth and channel operations.

Uses YouTube Data API v3 for:
- OAuth flow (channel connection)
- Channel info retrieval
- Video listing and polling
"""

import logging
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import urlencode

import requests
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# YouTube OAuth scopes
YOUTUBE_SCOPES = [
    "https://www.googleapis.com/auth/youtube.readonly"
]

# Google OAuth endpoints
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"


class YouTubeServiceError(Exception):
    """Exception raised for YouTube API errors."""
    pass


def get_oauth_url(redirect_uri: str, state: str) -> str:
    """
    Generate the Google OAuth authorization URL.

    Args:
        redirect_uri: URL to redirect to after authorization
        state: CSRF state token (should be stored in session)

    Returns:
        Authorization URL to redirect user to
    """
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(YOUTUBE_SCOPES),
        "access_type": "offline",  # Get refresh token
        "prompt": "consent",  # Always show consent screen
        "state": state
    }

    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


def exchange_code_for_tokens(code: str, redirect_uri: str) -> dict:
    """
    Exchange authorization code for access and refresh tokens.

    Args:
        code: Authorization code from OAuth callback
        redirect_uri: Same redirect URI used in authorization

    Returns:
        dict with access_token, refresh_token, expires_in

    Raises:
        YouTubeServiceError: If token exchange fails
    """
    data = {
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret,
        "code": code,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code"
    }

    response = requests.post(GOOGLE_TOKEN_URL, data=data)

    if response.status_code != 200:
        error = response.json().get("error_description", "Token exchange failed")
        raise YouTubeServiceError(f"OAuth token exchange failed: {error}")

    return response.json()


def refresh_access_token(refresh_token: str) -> dict:
    """
    Refresh an expired access token.

    Args:
        refresh_token: The refresh token

    Returns:
        dict with new access_token and expires_in

    Raises:
        YouTubeServiceError: If refresh fails
    """
    data = {
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token"
    }

    response = requests.post(GOOGLE_TOKEN_URL, data=data)

    if response.status_code != 200:
        error = response.json().get("error_description", "Token refresh failed")
        raise YouTubeServiceError(f"OAuth token refresh failed: {error}")

    return response.json()


def get_youtube_client(access_token: str):
    """
    Create a YouTube API client with the given access token.

    Args:
        access_token: Valid OAuth access token

    Returns:
        YouTube API client
    """
    credentials = Credentials(token=access_token)
    return build("youtube", "v3", credentials=credentials)


def get_channel_info(access_token: str) -> dict:
    """
    Get the authenticated user's YouTube channel info.

    Args:
        access_token: Valid OAuth access token

    Returns:
        dict with channel info (id, title, thumbnail_url, subscriber_count)

    Raises:
        YouTubeServiceError: If API call fails or no channel found
    """
    youtube = get_youtube_client(access_token)

    try:
        response = youtube.channels().list(
            part="snippet,statistics",
            mine=True
        ).execute()

        channels = response.get("items", [])
        if not channels:
            raise YouTubeServiceError("No YouTube channel found for this account")

        channel = channels[0]
        snippet = channel.get("snippet", {})
        statistics = channel.get("statistics", {})

        return {
            "channel_id": channel["id"],
            "title": snippet.get("title", ""),
            "description": snippet.get("description", ""),
            "thumbnail_url": snippet.get("thumbnails", {}).get("default", {}).get("url"),
            "subscriber_count": int(statistics.get("subscriberCount", 0)),
            "video_count": int(statistics.get("videoCount", 0))
        }

    except Exception as e:
        if "YouTubeServiceError" in str(type(e)):
            raise
        raise YouTubeServiceError(f"Failed to get channel info: {e}")


def list_channel_videos(
    access_token: str,
    channel_id: str,
    max_results: int = 50,
    published_after: Optional[datetime] = None
) -> list[dict]:
    """
    List videos from a YouTube channel.

    Args:
        access_token: Valid OAuth access token
        channel_id: YouTube channel ID
        max_results: Maximum number of videos to return
        published_after: Only return videos published after this date

    Returns:
        List of video dicts with id, title, description, published_at, thumbnail_url
    """
    youtube = get_youtube_client(access_token)

    try:
        # First, get the channel's uploads playlist
        channel_response = youtube.channels().list(
            part="contentDetails",
            id=channel_id
        ).execute()

        channels = channel_response.get("items", [])
        if not channels:
            return []

        uploads_playlist_id = channels[0]["contentDetails"]["relatedPlaylists"]["uploads"]

        # Get videos from uploads playlist
        videos = []
        next_page_token = None

        while len(videos) < max_results:
            playlist_response = youtube.playlistItems().list(
                part="snippet",
                playlistId=uploads_playlist_id,
                maxResults=min(50, max_results - len(videos)),
                pageToken=next_page_token
            ).execute()

            for item in playlist_response.get("items", []):
                snippet = item.get("snippet", {})
                published_at = snippet.get("publishedAt")

                # Parse publish date
                if published_at:
                    try:
                        pub_date = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
                        # Skip if before published_after filter
                        if published_after and pub_date < published_after:
                            continue
                    except ValueError:
                        pub_date = None
                else:
                    pub_date = None

                videos.append({
                    "video_id": snippet.get("resourceId", {}).get("videoId"),
                    "title": snippet.get("title", ""),
                    "description": snippet.get("description", ""),
                    "published_at": pub_date,
                    "thumbnail_url": snippet.get("thumbnails", {}).get("high", {}).get("url")
                })

            next_page_token = playlist_response.get("nextPageToken")
            if not next_page_token:
                break

        return videos

    except Exception as e:
        logger.error(f"Failed to list channel videos: {e}")
        return []


def get_video_details(access_token: str, video_id: str) -> Optional[dict]:
    """
    Get detailed information about a specific video.

    Args:
        access_token: Valid OAuth access token
        video_id: YouTube video ID

    Returns:
        dict with video details or None if not found
    """
    youtube = get_youtube_client(access_token)

    try:
        response = youtube.videos().list(
            part="snippet,contentDetails,statistics",
            id=video_id
        ).execute()

        items = response.get("items", [])
        if not items:
            return None

        video = items[0]
        snippet = video.get("snippet", {})
        content_details = video.get("contentDetails", {})
        statistics = video.get("statistics", {})

        # Parse duration (ISO 8601 format: PT1H2M3S)
        duration_str = content_details.get("duration", "PT0S")
        duration_seconds = parse_youtube_duration(duration_str)

        return {
            "video_id": video_id,
            "title": snippet.get("title", ""),
            "description": snippet.get("description", ""),
            "published_at": snippet.get("publishedAt"),
            "channel_id": snippet.get("channelId"),
            "channel_title": snippet.get("channelTitle"),
            "thumbnail_url": snippet.get("thumbnails", {}).get("high", {}).get("url"),
            "duration_seconds": duration_seconds,
            "view_count": int(statistics.get("viewCount", 0)),
            "like_count": int(statistics.get("likeCount", 0))
        }

    except Exception as e:
        logger.error(f"Failed to get video details for {video_id}: {e}")
        return None


def parse_youtube_duration(duration_str: str) -> int:
    """
    Parse YouTube ISO 8601 duration to seconds.

    Args:
        duration_str: Duration string like "PT1H2M3S"

    Returns:
        Duration in seconds
    """
    import re

    # Match hours, minutes, seconds
    pattern = r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?'
    match = re.match(pattern, duration_str)

    if not match:
        return 0

    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)

    return hours * 3600 + minutes * 60 + seconds


async def poll_channel_for_new_videos(
    church_id: int,
    access_token: str,
    refresh_token: str,
    channel_id: str,
    last_check: Optional[datetime] = None
) -> list[dict]:
    """
    Poll a YouTube channel for new videos since last check.

    Args:
        church_id: Database ID of the church
        access_token: OAuth access token
        refresh_token: OAuth refresh token
        channel_id: YouTube channel ID
        last_check: Last time we checked for new videos

    Returns:
        List of new video dicts
    """
    # Default to checking last 24 hours if no last_check
    if last_check is None:
        last_check = datetime.utcnow() - timedelta(hours=24)

    try:
        videos = list_channel_videos(
            access_token=access_token,
            channel_id=channel_id,
            max_results=20,
            published_after=last_check
        )
        return videos

    except YouTubeServiceError as e:
        if "invalid_grant" in str(e) or "Token" in str(e):
            # Try refreshing the token
            try:
                new_tokens = refresh_access_token(refresh_token)
                # Retry with new token
                videos = list_channel_videos(
                    access_token=new_tokens["access_token"],
                    channel_id=channel_id,
                    max_results=20,
                    published_after=last_check
                )
                return videos
            except Exception:
                pass
        raise
