#!/usr/bin/env python3
"""
02_extract_audio_v1.py
Extract MP3 audio from YouTube videos using yt-dlp.

================================================================================
OVERVIEW
================================================================================

This script is the second step in the PreachCaster pipeline. It extracts 
podcast-ready MP3 audio from YouTube videos using yt-dlp, a powerful 
open-source tool for downloading YouTube content.

The script can process:
- A single video by ID
- Multiple videos by ID
- All videos from new_videos.json (output from script 01)

================================================================================
HOW IT WORKS
================================================================================

1. Accept video ID(s) as input (CLI args or from new_videos.json)
2. For each video:
   a. Check if audio already exists (skip if present, unless --force)
   b. Call yt-dlp to download audio-only stream
   c. Convert to MP3 at specified bitrate (default 128k)
   d. Optionally embed thumbnail and metadata
   e. Save to audio directory with naming: {video_id}.mp3
3. Generate extraction report with file sizes, durations
4. Output summary of successful/failed extractions

================================================================================
INPUT/OUTPUT
================================================================================

INPUTS:
  - Video ID(s) via CLI arguments
  - Or path to new_videos.json from script 01
  - config/config.py for default settings

OUTPUTS:
  - audio/{video_id}.mp3: Extracted audio files
  - data/episodes/{video_id}_audio_meta.json: Audio metadata
  - data/episodes/extraction_report.json: Batch extraction report
    {
      "extraction_time": "2024-12-31T10:35:00",
      "videos_processed": 2,
      "successful": 2,
      "failed": 0,
      "total_duration_seconds": 5400,
      "total_file_size_mb": 64.5,
      "results": [...]
    }

================================================================================
USAGE
================================================================================

# Extract single video
python 02_extract_audio_v1.py --video-id abc123xyz

# Extract multiple videos (comma-separated)
python 02_extract_audio_v1.py --video-ids abc123,def456,ghi789

# Extract from new_videos.json (from script 01)
python 02_extract_audio_v1.py --from-file data/video_ids/new_videos.json

# Auto-detect: use new_videos.json if no args provided
python 02_extract_audio_v1.py

# Custom output directory
python 02_extract_audio_v1.py --video-id abc123 --output-dir ./custom/

# Custom quality (64k, 128k, 192k, 256k, 320k)
python 02_extract_audio_v1.py --video-id abc123 --bitrate 192k

# Force re-download (overwrite existing)
python 02_extract_audio_v1.py --video-id abc123 --force

# Include metadata and thumbnail in MP3
python 02_extract_audio_v1.py --video-id abc123 --embed-metadata

# Quiet mode (less output)
python 02_extract_audio_v1.py --video-id abc123 --quiet

================================================================================
REQUIREMENTS
================================================================================

External tools (must be installed on system):
  - yt-dlp: `brew install yt-dlp` or `pip install yt-dlp`
  - ffmpeg: `brew install ffmpeg` (for audio conversion)

Python dependencies (in requirements.txt):
  - yt-dlp>=2024.1.0 (optional, can use system install)

================================================================================
CONFIG IMPORTS USED
================================================================================

From config/config.py:
  - AUDIO_DIR: Output directory for MP3 files
  - AUDIO_FORMAT: Output format (default: mp3)
  - AUDIO_BITRATE: Bitrate (default: 128k)
  - VIDEO_IDS_DIR: Location of new_videos.json
  - DATA_DIR: For extraction reports
  - ensure_directories()
  - get_log_file()

================================================================================
VERSION HISTORY
================================================================================

v1 (2024-12-31): Initial version
  - yt-dlp audio extraction
  - MP3 conversion with configurable bitrate
  - Batch processing from new_videos.json
  - Extraction reports with metadata

================================================================================
"""

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional
import re

# Add project root to path for config imports
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from config.config import (
        AUDIO_DIR,
        AUDIO_FORMAT,
        AUDIO_BITRATE,
        VIDEO_IDS_DIR,
        DATA_DIR,
        ensure_directories,
        get_log_file,
    )
    CONFIG_LOADED = True
except ImportError:
    # Allow running without config for testing
    CONFIG_LOADED = False
    AUDIO_DIR = Path("./audio")
    AUDIO_FORMAT = "mp3"
    AUDIO_BITRATE = "128k"
    VIDEO_IDS_DIR = Path("./data/video_ids")
    DATA_DIR = Path("./data")


# ============================================================================
# CONSTANTS
# ============================================================================

YOUTUBE_URL_TEMPLATE = "https://www.youtube.com/watch?v={video_id}"

# Default new_videos.json filename
NEW_VIDEOS_FILE = "new_videos.json"

# Valid bitrate options
VALID_BITRATES = ["64k", "96k", "128k", "160k", "192k", "256k", "320k"]


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def check_yt_dlp_installed() -> bool:
    """Check if yt-dlp is installed and accessible."""
    return shutil.which("yt-dlp") is not None


def check_ffmpeg_installed() -> bool:
    """Check if ffmpeg is installed and accessible."""
    return shutil.which("ffmpeg") is not None


def format_duration(seconds: int) -> str:
    """Format seconds as HH:MM:SS or MM:SS."""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def format_file_size(bytes_size: int) -> str:
    """Format bytes as human-readable size."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_size < 1024:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024
    return f"{bytes_size:.1f} TB"


def get_youtube_url(video_id: str) -> str:
    """Construct YouTube watch URL from video ID."""
    return YOUTUBE_URL_TEMPLATE.format(video_id=video_id)


def parse_video_ids_from_arg(video_ids_arg: str) -> list[str]:
    """Parse comma-separated video IDs from CLI argument."""
    return [vid.strip() for vid in video_ids_arg.split(",") if vid.strip()]


def load_videos_from_file(file_path: Path, logger: logging.Logger) -> list[dict]:
    """
    Load videos from a JSON file (new_videos.json format).
    
    Returns list of video dictionaries with at least 'video_id' key.
    """
    if not file_path.exists():
        logger.error(f"File not found: {file_path}")
        return []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Handle new_videos.json format
        if isinstance(data, dict) and "videos" in data:
            videos = data["videos"]
            logger.info(f"Loaded {len(videos)} videos from {file_path.name}")
            return videos
        
        # Handle simple list of dicts
        if isinstance(data, list):
            logger.info(f"Loaded {len(data)} videos from {file_path.name}")
            return data
        
        logger.error(f"Unexpected format in {file_path}")
        return []
        
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Failed to load {file_path}: {e}")
        return []


# ============================================================================
# AUDIO EXTRACTION
# ============================================================================

def extract_audio(
    video_id: str,
    output_dir: Path,
    bitrate: str = "128k",
    embed_metadata: bool = False,
    force: bool = False,
    quiet: bool = False,
    logger: Optional[logging.Logger] = None
) -> dict:
    """
    Extract audio from a YouTube video using yt-dlp.
    
    Args:
        video_id: YouTube video ID
        output_dir: Directory to save the MP3 file
        bitrate: Audio bitrate (e.g., "128k", "192k")
        embed_metadata: If True, embed thumbnail and metadata in MP3
        force: If True, overwrite existing files
        quiet: If True, suppress yt-dlp output
        logger: Logger instance
        
    Returns:
        Dictionary with extraction results
    """
    if logger is None:
        logger = logging.getLogger(__name__)
    
    output_file = output_dir / f"{video_id}.mp3"
    url = get_youtube_url(video_id)
    
    result = {
        "video_id": video_id,
        "url": url,
        "status": "pending",
        "audio_file": None,
        "title": None,
        "duration_seconds": None,
        "file_size_bytes": None,
        "bitrate": bitrate,
        "error": None
    }
    
    # Check if already exists
    if output_file.exists() and not force:
        logger.info(f"Audio already exists: {output_file.name} (use --force to overwrite)")
        result["status"] = "skipped"
        result["audio_file"] = str(output_file)
        result["file_size_bytes"] = output_file.stat().st_size
        return result
    
    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Build yt-dlp command
    cmd = [
        "yt-dlp",
        "-x",  # Extract audio only
        "--audio-format", "mp3",
        "--audio-quality", bitrate.replace("k", "K"),  # yt-dlp uses uppercase K
        "-o", str(output_file),
        "--no-playlist",  # Don't download playlist if URL is part of one
    ]
    
    # Add metadata embedding if requested
    if embed_metadata:
        cmd.extend([
            "--embed-thumbnail",
            "--add-metadata",
            "--embed-metadata"
        ])
    
    # Add quiet flag if requested
    if quiet:
        cmd.append("--quiet")
    else:
        cmd.extend(["--progress", "--newline"])
    
    # Add URL last
    cmd.append(url)
    
    logger.info(f"Extracting audio: {video_id}")
    logger.debug(f"Command: {' '.join(cmd)}")
    
    try:
        # Run yt-dlp
        process = subprocess.run(
            cmd,
            capture_output=not quiet,
            text=True,
            timeout=600  # 10 minute timeout
        )
        
        if process.returncode != 0:
            error_msg = process.stderr if process.stderr else "Unknown error"
            logger.error(f"yt-dlp failed for {video_id}: {error_msg}")
            result["status"] = "failed"
            result["error"] = error_msg[:500]  # Truncate long errors
            return result
        
        # Verify file was created
        if not output_file.exists():
            # yt-dlp might add extension, look for any matching file
            possible_files = list(output_dir.glob(f"{video_id}.*"))
            if possible_files:
                output_file = possible_files[0]
            else:
                logger.error(f"Output file not found after extraction: {video_id}")
                result["status"] = "failed"
                result["error"] = "Output file not found"
                return result
        
        # Get file metadata
        result["status"] = "success"
        result["audio_file"] = str(output_file)
        result["file_size_bytes"] = output_file.stat().st_size
        
        # Try to get duration using ffprobe
        duration = get_audio_duration(output_file)
        if duration:
            result["duration_seconds"] = duration
        
        # Try to get title from yt-dlp output
        if not quiet and process.stdout:
            title_match = re.search(r'\[download\] Destination: .*/(.+)\.mp3', process.stdout)
            if title_match:
                result["title"] = title_match.group(1)
        
        logger.info(f"Successfully extracted: {output_file.name} ({format_file_size(result['file_size_bytes'])})")
        
    except subprocess.TimeoutExpired:
        logger.error(f"Timeout extracting {video_id}")
        result["status"] = "failed"
        result["error"] = "Extraction timeout (10 minutes)"
        
    except Exception as e:
        logger.error(f"Error extracting {video_id}: {e}")
        result["status"] = "failed"
        result["error"] = str(e)
    
    return result


def get_audio_duration(audio_file: Path) -> Optional[int]:
    """
    Get audio duration in seconds using ffprobe.
    
    Returns None if duration cannot be determined.
    """
    if not shutil.which("ffprobe"):
        return None
    
    try:
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(audio_file)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0 and result.stdout.strip():
            return int(float(result.stdout.strip()))
            
    except (subprocess.TimeoutExpired, ValueError):
        pass
    
    return None


def get_video_metadata(video_id: str, quiet: bool = False) -> Optional[dict]:
    """
    Get video metadata from YouTube using yt-dlp.
    
    Returns dict with title, duration, description, etc.
    """
    url = get_youtube_url(video_id)
    
    cmd = [
        "yt-dlp",
        "--dump-json",
        "--no-download",
        url
    ]
    
    if quiet:
        cmd.append("--quiet")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
        if result.returncode == 0 and result.stdout:
            return json.loads(result.stdout)
            
    except (subprocess.TimeoutExpired, json.JSONDecodeError):
        pass
    
    return None


# ============================================================================
# BATCH PROCESSING
# ============================================================================

def extract_batch(
    videos: list[dict],
    output_dir: Path,
    bitrate: str = "128k",
    embed_metadata: bool = False,
    force: bool = False,
    quiet: bool = False,
    logger: Optional[logging.Logger] = None
) -> list[dict]:
    """
    Extract audio from a batch of videos.
    
    Args:
        videos: List of video dicts (must have 'video_id' key)
        output_dir: Directory to save MP3 files
        bitrate: Audio bitrate
        embed_metadata: If True, embed metadata in MP3
        force: If True, overwrite existing files
        quiet: If True, reduce output
        logger: Logger instance
        
    Returns:
        List of result dictionaries
    """
    if logger is None:
        logger = logging.getLogger(__name__)
    
    results = []
    total = len(videos)
    
    for i, video in enumerate(videos, 1):
        video_id = video.get("video_id")
        title = video.get("title", "Unknown")
        
        if not video_id:
            logger.warning(f"Skipping video without ID: {video}")
            continue
        
        logger.info(f"\n[{i}/{total}] Processing: {title[:50]}...")
        
        result = extract_audio(
            video_id=video_id,
            output_dir=output_dir,
            bitrate=bitrate,
            embed_metadata=embed_metadata,
            force=force,
            quiet=quiet,
            logger=logger
        )
        
        # Add original video info to result
        result["title"] = result.get("title") or video.get("title")
        
        results.append(result)
    
    return results


def generate_extraction_report(
    results: list[dict],
    output_file: Path,
    logger: logging.Logger
) -> dict:
    """
    Generate and save extraction report.
    
    Args:
        results: List of extraction result dicts
        output_file: Path to save report
        logger: Logger instance
        
    Returns:
        Report dictionary
    """
    successful = [r for r in results if r["status"] == "success"]
    failed = [r for r in results if r["status"] == "failed"]
    skipped = [r for r in results if r["status"] == "skipped"]
    
    total_duration = sum(r.get("duration_seconds", 0) or 0 for r in successful + skipped)
    total_size = sum(r.get("file_size_bytes", 0) or 0 for r in successful + skipped)
    
    report = {
        "extraction_time": datetime.now().isoformat(),
        "videos_processed": len(results),
        "successful": len(successful),
        "failed": len(failed),
        "skipped": len(skipped),
        "total_duration_seconds": total_duration,
        "total_duration_formatted": format_duration(total_duration),
        "total_file_size_bytes": total_size,
        "total_file_size_formatted": format_file_size(total_size),
        "results": results
    }
    
    # Save report
    try:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved extraction report: {output_file}")
    except IOError as e:
        logger.error(f"Failed to save report: {e}")
    
    return report


# ============================================================================
# CLI INTERFACE
# ============================================================================

def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Extract MP3 audio from YouTube videos using yt-dlp.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --video-id abc123xyz           # Single video
  %(prog)s --video-ids abc123,def456      # Multiple videos
  %(prog)s --from-file new_videos.json    # From file
  %(prog)s                                # Auto-detect new_videos.json
  %(prog)s --bitrate 192k --embed-metadata  # High quality with metadata
        """
    )
    
    # Input options (mutually exclusive)
    input_group = parser.add_mutually_exclusive_group()
    
    input_group.add_argument(
        '--video-id',
        type=str,
        help='Single YouTube video ID to extract'
    )
    
    input_group.add_argument(
        '--video-ids',
        type=str,
        help='Comma-separated list of video IDs'
    )
    
    input_group.add_argument(
        '--from-file',
        type=str,
        help='Path to JSON file with videos (new_videos.json format)'
    )
    
    # Output options
    parser.add_argument(
        '--output-dir',
        type=str,
        default=None,
        help='Directory to save MP3 files (default: audio/)'
    )
    
    parser.add_argument(
        '--bitrate',
        type=str,
        default="128k",
        choices=VALID_BITRATES,
        help='Audio bitrate (default: 128k)'
    )
    
    # Processing options
    parser.add_argument(
        '--embed-metadata',
        action='store_true',
        help='Embed thumbnail and metadata in MP3'
    )
    
    parser.add_argument(
        '--force',
        action='store_true',
        help='Overwrite existing files'
    )
    
    parser.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='Suppress yt-dlp progress output'
    )
    
    parser.add_argument(
        '--json',
        action='store_true',
        help='Output results as JSON to stdout'
    )
    
    parser.add_argument(
        '--skip-checks',
        action='store_true',
        help='Skip dependency checks (yt-dlp, ffmpeg)'
    )
    
    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()
    
    # Set up logging
    log_level = logging.WARNING if args.quiet else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )
    logger = logging.getLogger(__name__)
    
    # Check dependencies
    if not args.skip_checks:
        if not check_yt_dlp_installed():
            logger.error("yt-dlp not found. Install with: brew install yt-dlp")
            sys.exit(1)
        
        if not check_ffmpeg_installed():
            logger.warning("ffmpeg not found. Install with: brew install ffmpeg")
            logger.warning("Some features (duration detection, format conversion) may not work.")
    
    # Determine output directory
    if args.output_dir:
        output_dir = Path(args.output_dir)
    elif CONFIG_LOADED:
        output_dir = AUDIO_DIR
    else:
        output_dir = Path("./audio")
    
    # Determine input videos
    videos = []
    
    if args.video_id:
        videos = [{"video_id": args.video_id}]
        
    elif args.video_ids:
        video_ids = parse_video_ids_from_arg(args.video_ids)
        videos = [{"video_id": vid} for vid in video_ids]
        
    elif args.from_file:
        videos = load_videos_from_file(Path(args.from_file), logger)
        
    else:
        # Auto-detect: look for new_videos.json
        if CONFIG_LOADED:
            default_file = VIDEO_IDS_DIR / NEW_VIDEOS_FILE
        else:
            default_file = Path("./data/video_ids") / NEW_VIDEOS_FILE
        
        if default_file.exists():
            logger.info(f"Auto-detected: {default_file}")
            videos = load_videos_from_file(default_file, logger)
        else:
            logger.error("No input specified. Use --video-id, --video-ids, or --from-file")
            logger.error(f"Or create {default_file} using 01_monitor_youtube_v1.py")
            sys.exit(1)
    
    if not videos:
        logger.error("No videos to process")
        sys.exit(1)
    
    logger.info(f"\n{'='*60}")
    logger.info(f"AUDIO EXTRACTION")
    logger.info(f"{'='*60}")
    logger.info(f"Videos to process: {len(videos)}")
    logger.info(f"Output directory: {output_dir}")
    logger.info(f"Bitrate: {args.bitrate}")
    logger.info(f"Embed metadata: {args.embed_metadata}")
    logger.info(f"{'='*60}\n")
    
    # Extract audio
    results = extract_batch(
        videos=videos,
        output_dir=output_dir,
        bitrate=args.bitrate,
        embed_metadata=args.embed_metadata,
        force=args.force,
        quiet=args.quiet,
        logger=logger
    )
    
    # Generate report
    if CONFIG_LOADED:
        report_dir = DATA_DIR / "episodes"
    else:
        report_dir = Path("./data/episodes")
    
    report_file = report_dir / "extraction_report.json"
    report = generate_extraction_report(results, report_file, logger)
    
    # Print summary
    logger.info(f"\n{'='*60}")
    logger.info("EXTRACTION COMPLETE")
    logger.info(f"{'='*60}")
    logger.info(f"Successful: {report['successful']}")
    logger.info(f"Failed: {report['failed']}")
    logger.info(f"Skipped: {report['skipped']}")
    logger.info(f"Total duration: {report['total_duration_formatted']}")
    logger.info(f"Total size: {report['total_file_size_formatted']}")
    
    # Show failures if any
    failed = [r for r in results if r["status"] == "failed"]
    if failed:
        logger.warning("\nFailed extractions:")
        for r in failed:
            logger.warning(f"  - {r['video_id']}: {r.get('error', 'Unknown error')}")
    
    # Output JSON if requested
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    
    # Exit with appropriate code
    if report['failed'] > 0 and report['successful'] == 0:
        sys.exit(1)
    
    return report


if __name__ == "__main__":
    main()
