#!/usr/bin/env python3
"""
01_monitor_youtube_v1.py
Monitor YouTube RSS feed for new sermon uploads.

================================================================================
OVERVIEW
================================================================================

This script is the first step in the PreachCaster pipeline. It monitors a 
YouTube channel, playlist, or podcast RSS feed for new video uploads and 
identifies which videos need to be processed.

YouTube provides public RSS feeds for channels and playlists that contain 
the ~15 most recent videos. This script:
- Fetches and parses the RSS feed
- Compares against previously seen videos
- Outputs a list of new videos for downstream processing
- Maintains a history file to track all seen videos

================================================================================
HOW IT WORKS
================================================================================

1. Load configuration (channel ID, source type, etc.)
2. Construct the appropriate RSS feed URL based on source type
3. Fetch and parse the RSS feed using feedparser
4. Load the history of previously seen video IDs
5. Compare feed entries against history to find new videos
6. Save new videos to new_videos.json for pipeline processing
7. Update the all_video_ids.json history file
8. Optionally output results to stdout as JSON

================================================================================
INPUT/OUTPUT
================================================================================

INPUTS:
  - config/config.py: YouTube channel/playlist configuration
  - data/video_ids/all_video_ids.json: History of seen videos (if exists)

OUTPUTS:
  - data/video_ids/new_videos.json: Newly detected videos for processing
    {
      "check_time": "2024-12-31T10:30:00",
      "source_type": "channel",
      "source_id": "UCDWgXIoyH3WNRxlB9N-gCOg",
      "new_count": 2,
      "videos": [...]
    }
    
  - data/video_ids/all_video_ids.json: Complete video history
    {
      "last_updated": "2024-12-31T10:30:00",
      "source_type": "channel",
      "source_id": "UCDWgXIoyH3WNRxlB9N-gCOg",
      "video_count": 150,
      "videos": {"video_id": {...metadata...}, ...}
    }
    
  - data/video_ids/video_ids_only.txt: Simple list of all video IDs

================================================================================
USAGE
================================================================================

# Check for new videos (normal operation)
python 01_monitor_youtube_v1.py

# Force re-check all videos (ignore history, treat all as new)
python 01_monitor_youtube_v1.py --full-scan

# Limit results (useful for testing)
python 01_monitor_youtube_v1.py --limit 5

# Output JSON to stdout (for piping to other tools)
python 01_monitor_youtube_v1.py --json

# Quiet mode (suppress progress output)
python 01_monitor_youtube_v1.py --quiet

# Combine options
python 01_monitor_youtube_v1.py --full-scan --limit 3 --json

================================================================================
REQUIREMENTS
================================================================================

Dependencies (in requirements.txt):
  - feedparser>=6.0.0
  - requests>=2.31.0
  - python-dateutil>=2.8.0

No API key required - YouTube RSS feeds are public.

================================================================================
CONFIG IMPORTS USED
================================================================================

From config/config.py:
  - CHURCH_NAME, CHURCH_SLUG
  - YOUTUBE_CHANNEL_ID
  - YOUTUBE_SOURCE_TYPE ("channel", "playlist", or "podcast")
  - YOUTUBE_PLAYLIST_ID (if source type is playlist)
  - YOUTUBE_PODCAST_ID (if source type is podcast)
  - VIDEO_IDS_DIR
  - ensure_directories()
  - get_log_file()

================================================================================
VERSION HISTORY
================================================================================

v1 (2024-12-31): Initial version
  - RSS feed parsing for channel/playlist/podcast
  - New video detection with history tracking
  - CLI interface with argparse
  - JSON output support

================================================================================
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse, parse_qs

import feedparser
import requests
from dateutil import parser as date_parser

# Add project root to path for config imports
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from config.config import (
        CHURCH_NAME,
        CHURCH_SLUG,
        YOUTUBE_CHANNEL_ID,
        YOUTUBE_SOURCE_TYPE,
        YOUTUBE_PLAYLIST_ID,
        YOUTUBE_PODCAST_ID,
        VIDEO_IDS_DIR,
        ensure_directories,
        get_log_file,
    )
    CONFIG_LOADED = True
except ImportError:
    # Allow running without config for testing
    CONFIG_LOADED = False
    CHURCH_NAME = "Test Church"
    CHURCH_SLUG = "test"
    YOUTUBE_CHANNEL_ID = None
    YOUTUBE_SOURCE_TYPE = "channel"
    YOUTUBE_PLAYLIST_ID = None
    YOUTUBE_PODCAST_ID = None
    VIDEO_IDS_DIR = Path("./data/video_ids")


# ============================================================================
# CONSTANTS
# ============================================================================

YOUTUBE_RSS_BASE = "https://www.youtube.com/feeds/videos.xml"
YOUTUBE_WATCH_URL = "https://www.youtube.com/watch?v="
YOUTUBE_THUMBNAIL_URL = "https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg"
YOUTUBE_THUMBNAIL_FALLBACK = "https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"

# Output file names
NEW_VIDEOS_FILE = "new_videos.json"
ALL_VIDEOS_FILE = "all_video_ids.json"
VIDEO_IDS_ONLY_FILE = "video_ids_only.txt"


# ============================================================================
# RSS FEED FUNCTIONS
# ============================================================================

def get_rss_url(source_type: str, source_id: str) -> str:
    """
    Construct the YouTube RSS feed URL based on source type.
    
    Args:
        source_type: One of "channel", "playlist", or "podcast"
        source_id: The channel ID, playlist ID, or podcast ID
        
    Returns:
        The complete RSS feed URL
    """
    if source_type == "channel":
        return f"{YOUTUBE_RSS_BASE}?channel_id={source_id}"
    elif source_type in ("playlist", "podcast"):
        return f"{YOUTUBE_RSS_BASE}?playlist_id={source_id}"
    else:
        raise ValueError(f"Unknown source type: {source_type}")


def extract_video_id(entry) -> Optional[str]:
    """
    Extract video ID from a feedparser entry.
    
    The video ID can be found in:
    - entry.yt_videoid (YouTube's namespace)
    - entry.link (as a query parameter)
    - entry.id (as yt:video:VIDEO_ID)
    """
    # Try yt:videoid first (most reliable)
    if hasattr(entry, 'yt_videoid'):
        return entry.yt_videoid
    
    # Try parsing from link
    if hasattr(entry, 'link'):
        parsed = urlparse(entry.link)
        params = parse_qs(parsed.query)
        if 'v' in params:
            return params['v'][0]
    
    # Try parsing from id
    if hasattr(entry, 'id'):
        if entry.id.startswith('yt:video:'):
            return entry.id.replace('yt:video:', '')
    
    return None


def parse_published_date(entry) -> Optional[str]:
    """
    Parse the published date from a feedparser entry.
    
    Returns ISO format string or None if parsing fails.
    """
    # Try published_parsed first
    if hasattr(entry, 'published_parsed') and entry.published_parsed:
        try:
            dt = datetime(*entry.published_parsed[:6])
            return dt.isoformat() + "Z"
        except (TypeError, ValueError):
            pass
    
    # Try published string
    if hasattr(entry, 'published') and entry.published:
        try:
            dt = date_parser.parse(entry.published)
            return dt.isoformat()
        except (ValueError, TypeError):
            pass
    
    return None


def get_thumbnail_url(video_id: str, check_exists: bool = False) -> str:
    """
    Get the thumbnail URL for a video.
    
    Args:
        video_id: YouTube video ID
        check_exists: If True, verify the maxres thumbnail exists
        
    Returns:
        URL to the best available thumbnail
    """
    maxres_url = YOUTUBE_THUMBNAIL_URL.format(video_id=video_id)
    
    if check_exists:
        try:
            response = requests.head(maxres_url, timeout=5)
            if response.status_code == 200:
                return maxres_url
        except requests.RequestException:
            pass
        return YOUTUBE_THUMBNAIL_FALLBACK.format(video_id=video_id)
    
    return maxres_url


def fetch_rss_feed(rss_url: str, logger: logging.Logger) -> Optional[feedparser.FeedParserDict]:
    """
    Fetch and parse an RSS feed.
    
    Args:
        rss_url: URL of the RSS feed
        logger: Logger instance
        
    Returns:
        Parsed feed or None if fetch failed
    """
    logger.info(f"Fetching RSS feed: {rss_url}")
    
    try:
        feed = feedparser.parse(rss_url)
        
        # Check for errors
        if feed.bozo and feed.bozo_exception:
            logger.warning(f"Feed parsing warning: {feed.bozo_exception}")
        
        if not feed.entries:
            logger.warning("No entries found in RSS feed")
            return feed
        
        logger.info(f"Found {len(feed.entries)} entries in feed")
        return feed
        
    except Exception as e:
        logger.error(f"Failed to fetch RSS feed: {e}")
        return None


def parse_feed_entries(feed: feedparser.FeedParserDict, logger: logging.Logger) -> list[dict]:
    """
    Parse feed entries into standardized video dictionaries.
    
    Args:
        feed: Parsed feedparser feed
        logger: Logger instance
        
    Returns:
        List of video dictionaries
    """
    videos = []
    
    for entry in feed.entries:
        video_id = extract_video_id(entry)
        
        if not video_id:
            logger.warning(f"Could not extract video ID from entry: {entry.get('title', 'Unknown')}")
            continue
        
        # Build video dictionary
        video = {
            "video_id": video_id,
            "title": entry.get('title', '').strip(),
            "published_at": parse_published_date(entry),
            "description": "",
            "url": f"{YOUTUBE_WATCH_URL}{video_id}",
            "thumbnail_url": get_thumbnail_url(video_id),
        }
        
        # Try to get description from various fields
        if hasattr(entry, 'media_group') and entry.media_group:
            for item in entry.media_group:
                if hasattr(item, 'media_description'):
                    video["description"] = item.media_description.strip()
                    break
        elif hasattr(entry, 'summary'):
            video["description"] = entry.summary.strip()
        
        videos.append(video)
    
    return videos


# ============================================================================
# HISTORY MANAGEMENT
# ============================================================================

def load_video_history(history_file: Path, logger: logging.Logger) -> dict:
    """
    Load the video history from disk.
    
    Args:
        history_file: Path to all_video_ids.json
        logger: Logger instance
        
    Returns:
        History dictionary with video data
    """
    if not history_file.exists():
        logger.info("No history file found, starting fresh")
        return {"videos": {}}
    
    try:
        with open(history_file, 'r', encoding='utf-8') as f:
            history = json.load(f)
        logger.info(f"Loaded history with {len(history.get('videos', {}))} videos")
        return history
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Failed to load history file: {e}")
        logger.info("Starting with empty history")
        return {"videos": {}}


def save_video_history(
    history_file: Path,
    videos: dict,
    source_type: str,
    source_id: str,
    logger: logging.Logger
) -> None:
    """
    Save the video history to disk.
    
    Args:
        history_file: Path to all_video_ids.json
        videos: Dictionary of video_id -> video data
        source_type: Source type (channel/playlist/podcast)
        source_id: Source ID
        logger: Logger instance
    """
    history = {
        "last_updated": datetime.now().isoformat(),
        "source_type": source_type,
        "source_id": source_id,
        "video_count": len(videos),
        "videos": videos
    }
    
    try:
        with open(history_file, 'w', encoding='utf-8') as f:
            json.dump(history, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved history with {len(videos)} videos")
    except IOError as e:
        logger.error(f"Failed to save history file: {e}")


def save_video_ids_only(ids_file: Path, video_ids: list[str], logger: logging.Logger) -> None:
    """
    Save a simple text file with just video IDs, one per line.
    
    Args:
        ids_file: Path to video_ids_only.txt
        video_ids: List of video IDs
        logger: Logger instance
    """
    try:
        with open(ids_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(video_ids))
        logger.info(f"Saved {len(video_ids)} video IDs to text file")
    except IOError as e:
        logger.error(f"Failed to save video IDs file: {e}")


def save_new_videos(
    new_videos_file: Path,
    videos: list[dict],
    source_type: str,
    source_id: str,
    logger: logging.Logger
) -> None:
    """
    Save the list of new videos for pipeline processing.
    
    Args:
        new_videos_file: Path to new_videos.json
        videos: List of new video dictionaries
        source_type: Source type (channel/playlist/podcast)
        source_id: Source ID
        logger: Logger instance
    """
    output = {
        "check_time": datetime.now().isoformat(),
        "source_type": source_type,
        "source_id": source_id,
        "new_count": len(videos),
        "videos": videos
    }
    
    try:
        with open(new_videos_file, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved {len(videos)} new videos to {new_videos_file.name}")
    except IOError as e:
        logger.error(f"Failed to save new videos file: {e}")


# ============================================================================
# MAIN MONITORING FUNCTION
# ============================================================================

def monitor_youtube(
    source_type: str,
    source_id: str,
    output_dir: Path,
    full_scan: bool = False,
    limit: Optional[int] = None,
    quiet: bool = False
) -> dict:
    """
    Main function to monitor YouTube for new videos.
    
    Args:
        source_type: One of "channel", "playlist", or "podcast"
        source_id: The channel ID, playlist ID, or podcast ID
        output_dir: Directory to save output files
        full_scan: If True, treat all videos as new (ignore history)
        limit: Maximum number of new videos to return
        quiet: If True, suppress progress output
        
    Returns:
        Dictionary with monitoring results
    """
    # Set up logging
    log_level = logging.WARNING if quiet else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )
    logger = logging.getLogger(__name__)
    
    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Define output file paths
    history_file = output_dir / ALL_VIDEOS_FILE
    new_videos_file = output_dir / NEW_VIDEOS_FILE
    ids_only_file = output_dir / VIDEO_IDS_ONLY_FILE
    
    # Fetch RSS feed
    rss_url = get_rss_url(source_type, source_id)
    feed = fetch_rss_feed(rss_url, logger)
    
    if feed is None:
        return {
            "success": False,
            "error": "Failed to fetch RSS feed",
            "new_count": 0,
            "videos": []
        }
    
    # Parse entries
    feed_videos = parse_feed_entries(feed, logger)
    
    if not feed_videos:
        logger.warning("No videos found in feed")
        return {
            "success": True,
            "new_count": 0,
            "videos": []
        }
    
    # Load history (unless doing full scan)
    if full_scan:
        logger.info("Full scan mode: treating all videos as new")
        history = {"videos": {}}
    else:
        history = load_video_history(history_file, logger)
    
    seen_ids = set(history.get("videos", {}).keys())
    
    # Find new videos
    new_videos = []
    for video in feed_videos:
        if video["video_id"] not in seen_ids:
            new_videos.append(video)
    
    # Apply limit if specified
    if limit and len(new_videos) > limit:
        logger.info(f"Limiting results to {limit} videos")
        new_videos = new_videos[:limit]
    
    # Update history with all videos from feed
    all_videos = history.get("videos", {})
    for video in feed_videos:
        all_videos[video["video_id"]] = video
    
    # Save outputs
    save_video_history(history_file, all_videos, source_type, source_id, logger)
    save_video_ids_only(ids_only_file, list(all_videos.keys()), logger)
    save_new_videos(new_videos_file, new_videos, source_type, source_id, logger)
    
    # Summary
    logger.info(f"\n{'='*60}")
    logger.info(f"MONITORING COMPLETE")
    logger.info(f"{'='*60}")
    logger.info(f"Source: {source_type} ({source_id})")
    logger.info(f"Videos in feed: {len(feed_videos)}")
    logger.info(f"Previously seen: {len(seen_ids)}")
    logger.info(f"New videos: {len(new_videos)}")
    logger.info(f"Total tracked: {len(all_videos)}")
    
    if new_videos:
        logger.info(f"\nNew videos:")
        for v in new_videos:
            logger.info(f"  - {v['title'][:60]}... ({v['video_id']})")
    
    return {
        "success": True,
        "check_time": datetime.now().isoformat(),
        "source_type": source_type,
        "source_id": source_id,
        "feed_count": len(feed_videos),
        "new_count": len(new_videos),
        "total_tracked": len(all_videos),
        "videos": new_videos
    }


# ============================================================================
# CLI INTERFACE
# ============================================================================

def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Monitor YouTube RSS feed for new sermon uploads.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                          # Check for new videos
  %(prog)s --full-scan              # Treat all videos as new
  %(prog)s --limit 5                # Limit to 5 results
  %(prog)s --json                   # Output JSON to stdout
  %(prog)s --channel-id UC12345     # Override channel ID
        """
    )
    
    parser.add_argument(
        '--full-scan',
        action='store_true',
        help='Ignore history and treat all videos as new'
    )
    
    parser.add_argument(
        '--limit',
        type=int,
        default=None,
        help='Maximum number of new videos to return'
    )
    
    parser.add_argument(
        '--json',
        action='store_true',
        help='Output results as JSON to stdout'
    )
    
    parser.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='Suppress progress output (only errors)'
    )
    
    # Override options
    parser.add_argument(
        '--channel-id',
        type=str,
        default=None,
        help='Override YouTube channel ID from config'
    )
    
    parser.add_argument(
        '--playlist-id',
        type=str,
        default=None,
        help='Use playlist ID instead of channel'
    )
    
    parser.add_argument(
        '--output-dir',
        type=str,
        default=None,
        help='Override output directory'
    )
    
    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()
    
    # Determine source type and ID
    if args.playlist_id:
        source_type = "playlist"
        source_id = args.playlist_id
    elif args.channel_id:
        source_type = "channel"
        source_id = args.channel_id
    elif CONFIG_LOADED:
        source_type = YOUTUBE_SOURCE_TYPE
        if source_type == "channel":
            source_id = YOUTUBE_CHANNEL_ID
        elif source_type == "playlist":
            source_id = YOUTUBE_PLAYLIST_ID
        elif source_type == "podcast":
            source_id = YOUTUBE_PODCAST_ID
        else:
            source_id = YOUTUBE_CHANNEL_ID
    else:
        print("Error: No YouTube source configured.")
        print("Use --channel-id or --playlist-id to specify source.")
        sys.exit(1)
    
    if not source_id:
        print(f"Error: No {source_type} ID configured.")
        sys.exit(1)
    
    # Determine output directory
    if args.output_dir:
        output_dir = Path(args.output_dir)
    elif CONFIG_LOADED:
        output_dir = VIDEO_IDS_DIR
    else:
        output_dir = Path("./data/video_ids")
    
    # Run monitoring
    results = monitor_youtube(
        source_type=source_type,
        source_id=source_id,
        output_dir=output_dir,
        full_scan=args.full_scan,
        limit=args.limit,
        quiet=args.quiet or args.json
    )
    
    # Output JSON if requested
    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    
    # Exit with appropriate code
    if not results["success"]:
        sys.exit(1)
    
    return results


if __name__ == "__main__":
    main()
