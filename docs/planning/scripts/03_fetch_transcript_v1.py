#!/usr/bin/env python3
"""
03_fetch_transcript_v1.py
Fetch transcripts from YouTube videos using the Captions API.

================================================================================
OVERVIEW
================================================================================
This script retrieves transcripts (captions) from YouTube videos using the
youtube-transcript-api library. It handles both auto-generated and manual
captions, storing results in structured JSON format with timestamps.

Part of the PreachCaster sermon automation pipeline.

================================================================================
FEATURES
================================================================================
- Fetch transcripts for single or multiple videos
- Auto-detect input from new_videos.json or extraction_report.json
- Prefer manual captions over auto-generated when available
- Support multiple languages with configurable preference
- Store both timestamped JSON and plain text versions
- Optional proxy support (Webshare) for reliability at scale
- Graceful handling of videos without captions
- Batch processing with detailed reports
- Incremental mode (skip existing transcripts)

================================================================================
INPUT SOURCES
================================================================================
The script accepts video IDs from multiple sources:

1. Single video:       --video-id abc123xyz
2. Multiple videos:    --video-ids abc123,def456,ghi789
3. From JSON file:     --from-file data/video_ids/new_videos.json
4. Auto-detect:        (no args) looks for new_videos.json or extraction_report.json

================================================================================
OUTPUT FILES
================================================================================
For each video:
  data/transcripts/{video_id}.json     - Full transcript with timestamps
  data/transcripts/{video_id}.txt      - Plain text version (no timestamps)

For batch processing:
  data/transcripts/transcript_report.json - Processing summary and stats

================================================================================
JSON OUTPUT FORMAT
================================================================================
{
  "video_id": "abc123xyz",
  "title": "Sunday Sermon: Finding Peace",
  "fetched_at": "2024-12-31T10:30:00",
  "language": "en",
  "language_code": "en",
  "is_generated": true,
  "is_translatable": true,
  "duration_seconds": 2700.5,
  "word_count": 4500,
  "character_count": 25000,
  "segment_count": 450,
  "segments": [
    {
      "start": 0.0,
      "duration": 4.5,
      "end": 4.5,
      "text": "Good morning everyone and welcome to Cross Connection Church."
    },
    ...
  ]
}

================================================================================
USAGE EXAMPLES
================================================================================
# Fetch single video transcript
python 03_fetch_transcript_v1.py --video-id abc123xyz

# Fetch from new_videos.json (output of script 01)
python 03_fetch_transcript_v1.py --from-file data/video_ids/new_videos.json

# Fetch from extraction_report.json (output of script 02)
python 03_fetch_transcript_v1.py --from-file data/episodes/extraction_report.json

# Auto-detect input file (checks standard locations)
python 03_fetch_transcript_v1.py

# Fetch multiple videos
python 03_fetch_transcript_v1.py --video-ids abc123,def456,ghi789

# Specify language preference (default: en)
python 03_fetch_transcript_v1.py --video-id abc123 --language es

# Use proxy for reliability (reads from config/env)
python 03_fetch_transcript_v1.py --video-id abc123 --use-proxy

# Force re-fetch (overwrite existing transcripts)
python 03_fetch_transcript_v1.py --video-id abc123 --force

# Output single video result as JSON to stdout
python 03_fetch_transcript_v1.py --video-id abc123 --json

# Quiet mode (minimal output, for automation)
python 03_fetch_transcript_v1.py --from-file new_videos.json --quiet

================================================================================
DEPENDENCIES
================================================================================
- youtube-transcript-api>=0.6.0
- python-dateutil>=2.8.0
- requests>=2.31.0 (for proxy support)

================================================================================
CONFIGURATION
================================================================================
Uses config/config.py for:
- TRANSCRIPTS_DIR: Output directory for transcript files
- VIDEO_IDS_DIR: Location of input files (new_videos.json)
- EPISODES_DIR: Location of extraction_report.json
- TRANSCRIPT_LANGUAGE: Default language preference
- TRANSCRIPT_PREFER_MANUAL: Prefer manual over auto captions
- WEBSHARE_PROXY_*: Proxy configuration

Can run without config using CLI overrides for testing.

================================================================================
ERROR HANDLING
================================================================================
- Videos without captions are logged and skipped (not failures)
- Network errors trigger retries with exponential backoff
- All errors are captured in transcript_report.json
- Exit code 0 if any transcripts succeeded, 1 if all failed

================================================================================
VERSION HISTORY
================================================================================
v1 - 2024-12-31 - Initial implementation
                - YouTube Transcript API integration
                - Multi-source input support
                - Proxy support
                - Batch processing with reports

================================================================================
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

# ============================================================================
# CONFIGURATION
# ============================================================================

# Try to import project config, fall back to defaults
try:
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from config.config import (
        TRANSCRIPTS_DIR,
        VIDEO_IDS_DIR,
        EPISODES_DIR,
        TRANSCRIPT_LANGUAGE,
        TRANSCRIPT_PREFER_MANUAL,
        WEBSHARE_PROXY_USER,
        WEBSHARE_PROXY_PASS,
        WEBSHARE_PROXY_HOST,
        WEBSHARE_PROXY_PORT,
        ensure_directories,
    )
    CONFIG_LOADED = True
except ImportError:
    CONFIG_LOADED = False
    TRANSCRIPTS_DIR = Path("data/transcripts")
    VIDEO_IDS_DIR = Path("data/video_ids")
    EPISODES_DIR = Path("data/episodes")
    TRANSCRIPT_LANGUAGE = "en"
    TRANSCRIPT_PREFER_MANUAL = True
    WEBSHARE_PROXY_USER = os.getenv("WEBSHARE_PROXY_USER")
    WEBSHARE_PROXY_PASS = os.getenv("WEBSHARE_PROXY_PASS")
    WEBSHARE_PROXY_HOST = "p.webshare.io"
    WEBSHARE_PROXY_PORT = "80"
    
    def ensure_directories():
        TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
        VIDEO_IDS_DIR.mkdir(parents=True, exist_ok=True)
        EPISODES_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================================
# LOGGING SETUP
# ============================================================================

def setup_logging(quiet: bool = False, verbose: bool = False) -> logging.Logger:
    """Configure logging based on verbosity settings."""
    logger = logging.getLogger("fetch_transcript")
    
    if quiet:
        level = logging.WARNING
    elif verbose:
        level = logging.DEBUG
    else:
        level = logging.INFO
    
    logger.setLevel(level)
    
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s",
            datefmt="%H:%M:%S"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
    return logger


# ============================================================================
# TRANSCRIPT FETCHING
# ============================================================================

def get_proxy_config(use_proxy: bool) -> Optional[dict]:
    """
    Build proxy configuration for youtube-transcript-api.
    
    Args:
        use_proxy: Whether to use proxy
        
    Returns:
        Proxy dict for requests, or None
    """
    if not use_proxy:
        return None
    
    if not WEBSHARE_PROXY_USER or not WEBSHARE_PROXY_PASS:
        return None
    
    proxy_url = f"http://{WEBSHARE_PROXY_USER}:{WEBSHARE_PROXY_PASS}@{WEBSHARE_PROXY_HOST}:{WEBSHARE_PROXY_PORT}"
    
    return {
        "http": proxy_url,
        "https": proxy_url
    }


def fetch_transcript(
    video_id: str,
    language: str = "en",
    prefer_manual: bool = True,
    use_proxy: bool = False,
    logger: Optional[logging.Logger] = None
) -> dict:
    """
    Fetch transcript for a single YouTube video.
    
    Supports youtube-transcript-api v0.6.x (class methods) and v1.x (instance methods).
    
    Args:
        video_id: YouTube video ID
        language: Preferred language code (default: en)
        prefer_manual: Prefer manual captions over auto-generated
        use_proxy: Use proxy configuration
        logger: Logger instance
        
    Returns:
        Dictionary with transcript data and metadata
    """
    if logger is None:
        logger = logging.getLogger("fetch_transcript")
    
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError:
        logger.error("youtube-transcript-api not installed. Run: pip install youtube-transcript-api")
        return {
            "video_id": video_id,
            "success": False,
            "error": "youtube-transcript-api not installed",
            "error_type": "dependency"
        }
    
    # Import error classes - handle different versions
    try:
        from youtube_transcript_api._errors import (
            TranscriptsDisabled,
            NoTranscriptFound,
            VideoUnavailable,
            NoTranscriptAvailable
        )
    except ImportError:
        # Fallback for different module structures
        TranscriptsDisabled = Exception
        NoTranscriptFound = Exception
        VideoUnavailable = Exception
        NoTranscriptAvailable = Exception
    
    result = {
        "video_id": video_id,
        "fetched_at": datetime.now().isoformat(),
        "language": language,
        "success": False
    }
    
    try:
        proxy_config = get_proxy_config(use_proxy)
        
        # Detect API version and get transcript list
        # v1.x uses instance methods, v0.6.x uses class methods
        api_instance = YouTubeTranscriptApi()
        
        # Check if we have the new v1.x API (instance method 'list')
        if hasattr(api_instance, 'list') and callable(getattr(api_instance, 'list')):
            # v1.x API - use instance methods
            logger.debug("Using youtube-transcript-api v1.x API")
            transcript_list = api_instance.list(video_id)
        else:
            # v0.6.x API - use class methods
            logger.debug("Using youtube-transcript-api v0.6.x API")
            if proxy_config:
                transcript_list = YouTubeTranscriptApi.list_transcripts(video_id, proxies=proxy_config)
            else:
                transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        
        # Find the best transcript
        transcript_obj = None
        is_generated = True
        actual_language = language
        is_translatable = False
        
        # Try to get transcript in preferred language
        try:
            if prefer_manual:
                # Try manual first
                try:
                    transcript_obj = transcript_list.find_manually_created_transcript([language])
                    is_generated = False
                    logger.debug(f"Found manual transcript in {language}")
                except (NoTranscriptFound, StopIteration, Exception) as e:
                    if "NoTranscriptFound" not in str(type(e)) and "StopIteration" not in str(type(e)):
                        # Only re-raise if it's not a "not found" type error
                        if "no transcript" not in str(e).lower():
                            raise
                    # Fall back to generated
                    transcript_obj = transcript_list.find_generated_transcript([language])
                    is_generated = True
                    logger.debug(f"Found auto-generated transcript in {language}")
            else:
                # Try generated first (some may prefer this for consistency)
                try:
                    transcript_obj = transcript_list.find_generated_transcript([language])
                    is_generated = True
                except (NoTranscriptFound, StopIteration, Exception):
                    transcript_obj = transcript_list.find_manually_created_transcript([language])
                    is_generated = False
                    
        except (NoTranscriptFound, StopIteration, Exception) as e:
            # Try any available transcript
            logger.debug(f"No {language} transcript, trying any available: {e}")
            try:
                available = list(transcript_list)
                if available:
                    transcript_obj = available[0]
                    is_generated = getattr(transcript_obj, 'is_generated', True)
                    actual_language = getattr(transcript_obj, 'language_code', language)
                    logger.info(f"Using available transcript: {actual_language} (generated={is_generated})")
            except Exception as list_error:
                logger.debug(f"Could not list transcripts: {list_error}")
        
        if transcript_obj is None:
            return {
                **result,
                "error": "No transcript available",
                "error_type": "no_captions"
            }
        
        # Check if translatable
        is_translatable = getattr(transcript_obj, 'is_translatable', False)
        actual_language = getattr(transcript_obj, 'language_code', language)
        
        # Fetch the actual transcript content
        # Handle both v0.6.x and v1.x fetch methods
        if hasattr(transcript_obj, 'fetch') and callable(getattr(transcript_obj, 'fetch')):
            if proxy_config and hasattr(transcript_obj.fetch, '__code__') and 'proxies' in transcript_obj.fetch.__code__.co_varnames:
                segments_raw = transcript_obj.fetch(proxies=proxy_config)
            else:
                segments_raw = transcript_obj.fetch()
        else:
            # Fallback - transcript_obj might already be the content
            segments_raw = transcript_obj
        
        # Convert to list if needed (v1.x returns FetchedTranscript object)
        if hasattr(segments_raw, 'to_raw_data'):
            segments = segments_raw.to_raw_data()
        elif hasattr(segments_raw, '__iter__') and not isinstance(segments_raw, (str, dict)):
            segments = list(segments_raw)
        else:
            segments = segments_raw if isinstance(segments_raw, list) else []
        
        # Process segments
        processed_segments = []
        total_duration = 0.0
        total_words = 0
        total_chars = 0
        
        for seg in segments:
            # Handle both dict and object formats
            if isinstance(seg, dict):
                start = seg.get("start", 0.0)
                duration = seg.get("duration", 0.0)
                text = seg.get("text", "").strip()
            else:
                start = getattr(seg, 'start', 0.0)
                duration = getattr(seg, 'duration', 0.0)
                text = getattr(seg, 'text', "").strip()
            
            processed_segments.append({
                "start": round(float(start), 2),
                "duration": round(float(duration), 2),
                "end": round(float(start) + float(duration), 2),
                "text": text
            })
            
            end_time = float(start) + float(duration)
            if end_time > total_duration:
                total_duration = end_time
            
            total_words += len(text.split())
            total_chars += len(text)
        
        result.update({
            "success": True,
            "language": actual_language,
            "language_code": actual_language,
            "is_generated": is_generated,
            "is_translatable": is_translatable,
            "duration_seconds": round(total_duration, 2),
            "word_count": total_words,
            "character_count": total_chars,
            "segment_count": len(processed_segments),
            "segments": processed_segments
        })
        
        logger.info(
            f"Fetched transcript for {video_id}: "
            f"{len(processed_segments)} segments, {total_words} words, "
            f"{'auto-generated' if is_generated else 'manual'}"
        )
        
    except TranscriptsDisabled:
        result["error"] = "Transcripts are disabled for this video"
        result["error_type"] = "disabled"
        logger.warning(f"Transcripts disabled for {video_id}")
        
    except NoTranscriptAvailable:
        result["error"] = "No transcript available for this video"
        result["error_type"] = "no_captions"
        logger.warning(f"No transcript available for {video_id}")
        
    except VideoUnavailable:
        result["error"] = "Video is unavailable"
        result["error_type"] = "unavailable"
        logger.warning(f"Video unavailable: {video_id}")
        
    except Exception as e:
        error_str = str(e).lower()
        if "proxy" in error_str or "connection" in error_str or "tunnel" in error_str:
            result["error"] = f"Network/proxy error: {e}"
            result["error_type"] = "network"
            logger.warning(f"Network error for {video_id}: {e}")
        elif "disabled" in error_str:
            result["error"] = "Transcripts are disabled for this video"
            result["error_type"] = "disabled"
            logger.warning(f"Transcripts disabled for {video_id}")
        elif "no transcript" in error_str or "not found" in error_str:
            result["error"] = "No transcript available for this video"
            result["error_type"] = "no_captions"
            logger.warning(f"No transcript available for {video_id}")
        else:
            result["error"] = str(e)
            result["error_type"] = "unknown"
            logger.error(f"Error fetching transcript for {video_id}: {e}")
    
    return result


def fetch_transcript_with_retry(
    video_id: str,
    language: str = "en",
    prefer_manual: bool = True,
    use_proxy: bool = False,
    max_retries: int = 3,
    logger: Optional[logging.Logger] = None
) -> dict:
    """
    Fetch transcript with retry logic and exponential backoff.
    
    Args:
        video_id: YouTube video ID
        language: Preferred language code
        prefer_manual: Prefer manual captions
        use_proxy: Use proxy configuration
        max_retries: Maximum retry attempts
        logger: Logger instance
        
    Returns:
        Dictionary with transcript data
    """
    if logger is None:
        logger = logging.getLogger("fetch_transcript")
    
    last_error = None
    
    for attempt in range(max_retries):
        result = fetch_transcript(
            video_id=video_id,
            language=language,
            prefer_manual=prefer_manual,
            use_proxy=use_proxy,
            logger=logger
        )
        
        if result.get("success"):
            return result
        
        error_type = result.get("error_type", "unknown")
        
        # Don't retry for permanent errors
        if error_type in ["no_captions", "disabled", "unavailable", "dependency"]:
            return result
        
        last_error = result.get("error")
        
        if attempt < max_retries - 1:
            wait_time = (2 ** attempt) + 1  # 2, 3, 5 seconds
            logger.debug(f"Retry {attempt + 1}/{max_retries} for {video_id} in {wait_time}s")
            time.sleep(wait_time)
    
    return {
        "video_id": video_id,
        "success": False,
        "error": f"Max retries exceeded: {last_error}",
        "error_type": "max_retries"
    }


# ============================================================================
# FILE OPERATIONS
# ============================================================================

def save_transcript(
    transcript_data: dict,
    output_dir: Path,
    logger: Optional[logging.Logger] = None
) -> tuple[Optional[Path], Optional[Path]]:
    """
    Save transcript to JSON and TXT files.
    
    Args:
        transcript_data: Transcript data dictionary
        output_dir: Output directory
        logger: Logger instance
        
    Returns:
        Tuple of (json_path, txt_path) or (None, None) on failure
    """
    if logger is None:
        logger = logging.getLogger("fetch_transcript")
    
    if not transcript_data.get("success"):
        return None, None
    
    video_id = transcript_data["video_id"]
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Save JSON (full transcript with metadata)
    json_path = output_dir / f"{video_id}.json"
    try:
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(transcript_data, f, indent=2, ensure_ascii=False)
        logger.debug(f"Saved JSON: {json_path}")
    except Exception as e:
        logger.error(f"Failed to save JSON for {video_id}: {e}")
        return None, None
    
    # Save TXT (plain text, no timestamps)
    txt_path = output_dir / f"{video_id}.txt"
    try:
        segments = transcript_data.get("segments", [])
        full_text = " ".join(seg["text"] for seg in segments)
        # Clean up extra whitespace
        full_text = " ".join(full_text.split())
        
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(full_text)
        logger.debug(f"Saved TXT: {txt_path}")
    except Exception as e:
        logger.error(f"Failed to save TXT for {video_id}: {e}")
        return json_path, None
    
    return json_path, txt_path


def load_video_ids_from_file(file_path: Path, logger: Optional[logging.Logger] = None) -> list[dict]:
    """
    Load video IDs from a JSON file (new_videos.json or extraction_report.json).
    
    Args:
        file_path: Path to JSON file
        logger: Logger instance
        
    Returns:
        List of video info dictionaries with at least 'video_id' key
    """
    if logger is None:
        logger = logging.getLogger("fetch_transcript")
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        logger.error(f"Failed to load file {file_path}: {e}")
        return []
    
    videos = []
    
    # Handle new_videos.json format
    if isinstance(data, dict) and "videos" in data:
        for v in data["videos"]:
            if isinstance(v, dict) and "video_id" in v:
                videos.append(v)
            elif isinstance(v, str):
                videos.append({"video_id": v})
    
    # Handle extraction_report.json format
    elif isinstance(data, dict) and "results" in data:
        for r in data["results"]:
            if isinstance(r, dict) and r.get("success") and "video_id" in r:
                videos.append(r)
    
    # Handle simple list format
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and "video_id" in item:
                videos.append(item)
            elif isinstance(item, str):
                videos.append({"video_id": item})
    
    logger.info(f"Loaded {len(videos)} video(s) from {file_path}")
    return videos


def find_input_file(logger: Optional[logging.Logger] = None) -> Optional[Path]:
    """
    Auto-detect input file from standard locations.
    
    Checks in order:
    1. data/video_ids/new_videos.json
    2. data/episodes/extraction_report.json
    
    Args:
        logger: Logger instance
        
    Returns:
        Path to input file or None
    """
    if logger is None:
        logger = logging.getLogger("fetch_transcript")
    
    candidates = [
        VIDEO_IDS_DIR / "new_videos.json",
        EPISODES_DIR / "extraction_report.json",
        Path("new_videos.json"),
        Path("extraction_report.json"),
    ]
    
    for path in candidates:
        if path.exists():
            logger.info(f"Auto-detected input file: {path}")
            return path
    
    logger.warning("No input file found in standard locations")
    return None


def transcript_exists(video_id: str, output_dir: Path) -> bool:
    """Check if transcript already exists for a video."""
    json_path = Path(output_dir) / f"{video_id}.json"
    return json_path.exists()


# ============================================================================
# BATCH PROCESSING
# ============================================================================

def process_videos(
    videos: list[dict],
    output_dir: Path,
    language: str = "en",
    prefer_manual: bool = True,
    use_proxy: bool = False,
    force: bool = False,
    logger: Optional[logging.Logger] = None
) -> dict:
    """
    Process multiple videos and generate a report.
    
    Args:
        videos: List of video info dictionaries
        output_dir: Output directory for transcripts
        language: Preferred language code
        prefer_manual: Prefer manual captions
        use_proxy: Use proxy configuration
        force: Force re-fetch existing transcripts
        logger: Logger instance
        
    Returns:
        Processing report dictionary
    """
    if logger is None:
        logger = logging.getLogger("fetch_transcript")
    
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    report = {
        "processed_at": datetime.now().isoformat(),
        "settings": {
            "language": language,
            "prefer_manual": prefer_manual,
            "use_proxy": use_proxy,
            "force": force
        },
        "summary": {
            "total": len(videos),
            "success": 0,
            "skipped": 0,
            "no_captions": 0,
            "failed": 0
        },
        "results": []
    }
    
    for i, video_info in enumerate(videos, 1):
        video_id = video_info.get("video_id")
        title = video_info.get("title", "Unknown")
        
        if not video_id:
            logger.warning(f"Skipping entry without video_id: {video_info}")
            continue
        
        logger.info(f"[{i}/{len(videos)}] Processing: {video_id}")
        
        # Check if already exists
        if not force and transcript_exists(video_id, output_dir):
            logger.info(f"  Skipping (already exists): {video_id}")
            report["summary"]["skipped"] += 1
            report["results"].append({
                "video_id": video_id,
                "title": title,
                "status": "skipped",
                "reason": "already_exists"
            })
            continue
        
        # Fetch transcript
        result = fetch_transcript_with_retry(
            video_id=video_id,
            language=language,
            prefer_manual=prefer_manual,
            use_proxy=use_proxy,
            logger=logger
        )
        
        # Add title if we have it
        if title and title != "Unknown":
            result["title"] = title
        
        if result.get("success"):
            # Save transcript files
            json_path, txt_path = save_transcript(result, output_dir, logger)
            
            if json_path:
                report["summary"]["success"] += 1
                report["results"].append({
                    "video_id": video_id,
                    "title": result.get("title", title),
                    "status": "success",
                    "language": result.get("language_code"),
                    "is_generated": result.get("is_generated"),
                    "word_count": result.get("word_count"),
                    "segment_count": result.get("segment_count"),
                    "json_path": str(json_path),
                    "txt_path": str(txt_path) if txt_path else None
                })
            else:
                report["summary"]["failed"] += 1
                report["results"].append({
                    "video_id": video_id,
                    "title": title,
                    "status": "failed",
                    "error": "Failed to save files"
                })
        else:
            error_type = result.get("error_type", "unknown")
            
            if error_type in ["no_captions", "disabled"]:
                report["summary"]["no_captions"] += 1
                status = "no_captions"
            else:
                report["summary"]["failed"] += 1
                status = "failed"
            
            report["results"].append({
                "video_id": video_id,
                "title": title,
                "status": status,
                "error": result.get("error"),
                "error_type": error_type
            })
        
        # Small delay between requests to be nice to YouTube
        if i < len(videos):
            time.sleep(0.5)
    
    return report


def save_report(report: dict, output_dir: Path, logger: Optional[logging.Logger] = None) -> Path:
    """Save processing report to JSON file."""
    if logger is None:
        logger = logging.getLogger("fetch_transcript")
    
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    report_path = output_dir / "transcript_report.json"
    
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    
    logger.info(f"Saved report: {report_path}")
    return report_path


# ============================================================================
# CLI INTERFACE
# ============================================================================

def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Fetch transcripts from YouTube videos",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --video-id abc123xyz              # Fetch single video
  %(prog)s --video-ids abc123,def456         # Fetch multiple videos
  %(prog)s --from-file new_videos.json       # Fetch from file
  %(prog)s                                   # Auto-detect input file
  %(prog)s --video-id abc123 --language es   # Fetch Spanish transcript
  %(prog)s --video-id abc123 --use-proxy     # Use proxy
  %(prog)s --video-id abc123 --force         # Re-fetch existing
  %(prog)s --video-id abc123 --json          # Output JSON to stdout
        """
    )
    
    # Input sources (mutually exclusive)
    input_group = parser.add_mutually_exclusive_group()
    input_group.add_argument(
        "--video-id",
        help="Single YouTube video ID"
    )
    input_group.add_argument(
        "--video-ids",
        help="Comma-separated list of video IDs"
    )
    input_group.add_argument(
        "--from-file",
        help="Path to JSON file with video IDs (new_videos.json or extraction_report.json)"
    )
    
    # Options
    parser.add_argument(
        "--language", "-l",
        default=TRANSCRIPT_LANGUAGE,
        help=f"Preferred language code (default: {TRANSCRIPT_LANGUAGE})"
    )
    parser.add_argument(
        "--prefer-generated",
        action="store_true",
        help="Prefer auto-generated captions over manual"
    )
    parser.add_argument(
        "--use-proxy",
        action="store_true",
        help="Use Webshare proxy for requests"
    )
    parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Force re-fetch (overwrite existing transcripts)"
    )
    
    # Output options
    parser.add_argument(
        "--output-dir", "-o",
        type=Path,
        default=TRANSCRIPTS_DIR,
        help=f"Output directory (default: {TRANSCRIPTS_DIR})"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output result as JSON to stdout (single video only)"
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Minimal output (warnings and errors only)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output (debug level)"
    )
    
    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()
    
    # Setup logging
    logger = setup_logging(quiet=args.quiet, verbose=args.verbose)
    
    # Ensure directories exist
    ensure_directories()
    
    # Determine prefer_manual setting
    prefer_manual = TRANSCRIPT_PREFER_MANUAL and not args.prefer_generated
    
    # Determine input source
    videos = []
    
    if args.video_id:
        # Single video
        videos = [{"video_id": args.video_id}]
        
    elif args.video_ids:
        # Multiple videos from comma-separated list
        video_ids = [v.strip() for v in args.video_ids.split(",") if v.strip()]
        videos = [{"video_id": vid} for vid in video_ids]
        
    elif args.from_file:
        # From specified file
        file_path = Path(args.from_file)
        if not file_path.exists():
            logger.error(f"File not found: {file_path}")
            sys.exit(1)
        videos = load_video_ids_from_file(file_path, logger)
        
    else:
        # Auto-detect input file
        input_file = find_input_file(logger)
        if input_file:
            videos = load_video_ids_from_file(input_file, logger)
        else:
            logger.error("No input specified. Use --video-id, --from-file, or place new_videos.json in data/video_ids/")
            sys.exit(1)
    
    if not videos:
        logger.error("No videos to process")
        sys.exit(1)
    
    logger.info(f"Processing {len(videos)} video(s)")
    
    # Single video with JSON output
    if len(videos) == 1 and args.json:
        result = fetch_transcript_with_retry(
            video_id=videos[0]["video_id"],
            language=args.language,
            prefer_manual=prefer_manual,
            use_proxy=args.use_proxy,
            logger=logger
        )
        print(json.dumps(result, indent=2))
        sys.exit(0 if result.get("success") else 1)
    
    # Batch processing
    report = process_videos(
        videos=videos,
        output_dir=args.output_dir,
        language=args.language,
        prefer_manual=prefer_manual,
        use_proxy=args.use_proxy,
        force=args.force,
        logger=logger
    )
    
    # Save report
    save_report(report, args.output_dir, logger)
    
    # Print summary
    summary = report["summary"]
    logger.info(
        f"\nComplete: {summary['success']} success, "
        f"{summary['skipped']} skipped, "
        f"{summary['no_captions']} no captions, "
        f"{summary['failed']} failed"
    )
    
    # Exit code based on success
    if summary["success"] > 0 or summary["skipped"] > 0:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
