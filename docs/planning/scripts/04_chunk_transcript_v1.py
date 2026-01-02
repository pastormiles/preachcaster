#!/usr/bin/env python3
"""
04_chunk_transcript_v1.py
Split transcripts into searchable chunks for semantic search.

================================================================================
OVERVIEW
================================================================================
This script processes transcript JSON files and splits them into overlapping
chunks optimized for semantic search and embedding generation. Each chunk
includes timestamps, metadata, and YouTube links for direct navigation.

Part of the PreachCaster sermon automation pipeline.

================================================================================
FEATURES
================================================================================
- Duration-based chunking (default: 2 minutes per chunk)
- Configurable overlap between chunks (default: 15 seconds)
- Timestamp preservation for video linking
- Chunk ID generation for Pinecone indexing
- Metadata enrichment (video ID, title, position, URLs)
- Batch processing with detailed reports
- Incremental mode (skip existing chunks)
- Multiple input formats (single file, directory, report)

================================================================================
CHUNKING STRATEGY
================================================================================
Duration-based chunking works well for sermons because:
- Sermons have natural speaking rhythm
- Consistent chunk sizes improve embedding quality
- Easy timestamp linking back to video
- ~500 tokens per 2-minute chunk (typical speaking rate)

Default parameters:
- Target duration: 120 seconds (2 minutes)
- Overlap: 15 seconds between chunks
- Minimum chunk: 30 seconds (avoid tiny final chunks)

================================================================================
INPUT SOURCES
================================================================================
1. Single transcript:  --video-id abc123xyz
2. All transcripts:    --all (processes entire transcripts directory)
3. From report:        --from-report data/transcripts/transcript_report.json
4. Auto-detect:        (no args) processes transcript_report.json if present

================================================================================
OUTPUT FILES
================================================================================
For each video:
  data/chunks/{video_id}_chunks.json - Chunked transcript with metadata

For batch processing:
  data/chunks/chunk_report.json - Processing summary and stats

================================================================================
CHUNK JSON FORMAT
================================================================================
{
  "video_id": "abc123xyz",
  "title": "Sunday Sermon: Finding Peace",
  "chunked_at": "2024-12-31T10:35:00",
  "source_transcript": "data/transcripts/abc123xyz.json",
  "chunk_settings": {
    "target_duration_seconds": 120,
    "overlap_seconds": 15,
    "min_chunk_seconds": 30
  },
  "total_chunks": 24,
  "total_duration_seconds": 2700.5,
  "total_words": 4500,
  "chunks": [
    {
      "chunk_id": "abc123xyz_chunk_001",
      "chunk_index": 0,
      "start_time": 0.0,
      "end_time": 120.0,
      "duration_seconds": 120.0,
      "text": "Good morning everyone...",
      "word_count": 245,
      "timestamp_formatted": "0:00",
      "youtube_url": "https://www.youtube.com/watch?v=abc123xyz&t=0"
    },
    ...
  ]
}

================================================================================
USAGE EXAMPLES
================================================================================
# Chunk single transcript
python 04_chunk_transcript_v1.py --video-id abc123xyz

# Chunk all transcripts in directory
python 04_chunk_transcript_v1.py --all

# Chunk from transcript report
python 04_chunk_transcript_v1.py --from-report data/transcripts/transcript_report.json

# Auto-detect and process transcript report
python 04_chunk_transcript_v1.py

# Custom chunk settings (3 minutes, 20 second overlap)
python 04_chunk_transcript_v1.py --video-id abc123 --chunk-duration 180 --overlap 20

# Force re-chunk existing
python 04_chunk_transcript_v1.py --video-id abc123 --force

# Output single video chunks as JSON to stdout
python 04_chunk_transcript_v1.py --video-id abc123 --json

# Quiet mode (minimal output)
python 04_chunk_transcript_v1.py --all --quiet

================================================================================
DEPENDENCIES
================================================================================
- No external dependencies (uses standard library only)
- Requires transcript JSON files from script 03

================================================================================
CONFIGURATION
================================================================================
Uses config/config.py for:
- TRANSCRIPTS_DIR: Location of transcript files
- CHUNKS_DIR: Output directory for chunk files
- CHUNK_DURATION_SECONDS: Target chunk duration (default: 120)
- CHUNK_OVERLAP_SECONDS: Overlap between chunks (default: 15)
- CHUNK_MIN_SECONDS: Minimum chunk size (default: 30)

Can run without config using CLI overrides.

================================================================================
PINECONE METADATA
================================================================================
Each chunk includes metadata suitable for Pinecone vector storage:
- video_id: For filtering by video
- chunk_id: Unique identifier
- chunk_index: Position in video
- start_time: For timestamp linking
- title: For display
- text: For embedding generation

================================================================================
VERSION HISTORY
================================================================================
v1 - 2024-12-31 - Initial implementation
                - Duration-based chunking
                - Overlap support
                - Metadata enrichment
                - Batch processing

================================================================================
"""

import argparse
import json
import logging
import os
import sys
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
        CHUNKS_DIR,
        CHUNK_DURATION_SECONDS,
        CHUNK_OVERLAP_SECONDS,
        CHUNK_MIN_SECONDS,
        ensure_directories,
    )
    CONFIG_LOADED = True
except ImportError:
    CONFIG_LOADED = False
    TRANSCRIPTS_DIR = Path("data/transcripts")
    CHUNKS_DIR = Path("data/chunks")
    CHUNK_DURATION_SECONDS = 120
    CHUNK_OVERLAP_SECONDS = 15
    CHUNK_MIN_SECONDS = 30
    
    def ensure_directories():
        TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
        CHUNKS_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================================
# LOGGING SETUP
# ============================================================================

def setup_logging(quiet: bool = False, verbose: bool = False) -> logging.Logger:
    """Configure logging based on verbosity settings."""
    logger = logging.getLogger("chunk_transcript")
    
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
# TIME FORMATTING
# ============================================================================

def format_timestamp(seconds: float) -> str:
    """
    Format seconds as human-readable timestamp (M:SS or H:MM:SS).
    
    Args:
        seconds: Time in seconds
        
    Returns:
        Formatted timestamp string
    """
    seconds = int(seconds)
    
    if seconds < 3600:
        minutes = seconds // 60
        secs = seconds % 60
        return f"{minutes}:{secs:02d}"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        return f"{hours}:{minutes:02d}:{secs:02d}"


def get_youtube_url(video_id: str, start_time: float) -> str:
    """
    Generate YouTube URL with timestamp.
    
    Args:
        video_id: YouTube video ID
        start_time: Start time in seconds
        
    Returns:
        YouTube URL with timestamp parameter
    """
    start_seconds = int(start_time)
    return f"https://www.youtube.com/watch?v={video_id}&t={start_seconds}"


# ============================================================================
# CHUNKING LOGIC
# ============================================================================

def chunk_transcript(
    transcript_data: dict,
    target_duration: float = 120.0,
    overlap: float = 15.0,
    min_duration: float = 30.0,
    logger: Optional[logging.Logger] = None
) -> dict:
    """
    Split a transcript into overlapping chunks.
    
    Args:
        transcript_data: Transcript JSON data with segments
        target_duration: Target duration per chunk in seconds
        overlap: Overlap between chunks in seconds
        min_duration: Minimum chunk duration in seconds
        logger: Logger instance
        
    Returns:
        Dictionary with chunk data and metadata
    """
    if logger is None:
        logger = logging.getLogger("chunk_transcript")
    
    video_id = transcript_data.get("video_id", "unknown")
    title = transcript_data.get("title", "")
    segments = transcript_data.get("segments", [])
    
    if not segments:
        logger.warning(f"No segments in transcript for {video_id}")
        return {
            "video_id": video_id,
            "title": title,
            "chunked_at": datetime.now().isoformat(),
            "success": False,
            "error": "No segments in transcript",
            "total_chunks": 0,
            "chunks": []
        }
    
    # Calculate total duration from segments
    total_duration = 0.0
    for seg in segments:
        end = seg.get("end", seg.get("start", 0) + seg.get("duration", 0))
        if end > total_duration:
            total_duration = end
    
    chunks = []
    chunk_index = 0
    current_start = 0.0
    step = target_duration - overlap  # How much to advance each chunk
    
    while current_start < total_duration:
        chunk_end = min(current_start + target_duration, total_duration)
        
        # Collect segments that fall within this chunk
        chunk_segments = []
        for seg in segments:
            seg_start = seg.get("start", 0)
            seg_end = seg.get("end", seg_start + seg.get("duration", 0))
            
            # Include segment if it overlaps with chunk window
            if seg_end > current_start and seg_start < chunk_end:
                chunk_segments.append(seg)
        
        if chunk_segments:
            # Build chunk text
            chunk_text = " ".join(seg.get("text", "") for seg in chunk_segments)
            chunk_text = " ".join(chunk_text.split())  # Normalize whitespace
            
            # Calculate actual timing from included segments
            actual_start = min(seg.get("start", 0) for seg in chunk_segments)
            actual_end = max(
                seg.get("end", seg.get("start", 0) + seg.get("duration", 0))
                for seg in chunk_segments
            )
            actual_duration = actual_end - actual_start
            
            # Count words
            word_count = len(chunk_text.split())
            
            # Generate chunk ID (zero-padded for sorting)
            chunk_id = f"{video_id}_chunk_{chunk_index:03d}"
            
            chunk = {
                "chunk_id": chunk_id,
                "chunk_index": chunk_index,
                "start_time": round(actual_start, 2),
                "end_time": round(actual_end, 2),
                "duration_seconds": round(actual_duration, 2),
                "text": chunk_text,
                "word_count": word_count,
                "timestamp_formatted": format_timestamp(actual_start),
                "youtube_url": get_youtube_url(video_id, actual_start)
            }
            
            chunks.append(chunk)
            chunk_index += 1
        
        # Move to next chunk position
        current_start += step
        
        # If remaining duration is less than minimum, extend previous chunk
        remaining = total_duration - current_start
        if 0 < remaining < min_duration and chunks:
            # Don't create a tiny final chunk - the last chunk will naturally
            # extend to include remaining content
            break
    
    # Calculate totals
    total_words = sum(c["word_count"] for c in chunks)
    
    result = {
        "video_id": video_id,
        "title": title,
        "chunked_at": datetime.now().isoformat(),
        "success": True,
        "source_transcript": str(TRANSCRIPTS_DIR / f"{video_id}.json"),
        "chunk_settings": {
            "target_duration_seconds": target_duration,
            "overlap_seconds": overlap,
            "min_chunk_seconds": min_duration
        },
        "total_chunks": len(chunks),
        "total_duration_seconds": round(total_duration, 2),
        "total_words": total_words,
        "avg_words_per_chunk": round(total_words / len(chunks), 1) if chunks else 0,
        "chunks": chunks
    }
    
    logger.info(
        f"Chunked {video_id}: {len(chunks)} chunks, "
        f"{total_words} words, avg {result['avg_words_per_chunk']} words/chunk"
    )
    
    return result


# ============================================================================
# FILE OPERATIONS
# ============================================================================

def load_transcript(video_id: str, transcripts_dir: Path, logger: Optional[logging.Logger] = None) -> Optional[dict]:
    """
    Load transcript JSON for a video.
    
    Args:
        video_id: YouTube video ID
        transcripts_dir: Directory containing transcripts
        logger: Logger instance
        
    Returns:
        Transcript data dictionary or None
    """
    if logger is None:
        logger = logging.getLogger("chunk_transcript")
    
    transcript_path = Path(transcripts_dir) / f"{video_id}.json"
    
    if not transcript_path.exists():
        logger.warning(f"Transcript not found: {transcript_path}")
        return None
    
    try:
        with open(transcript_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # Verify it's a successful transcript
        if not data.get("success", True):  # Default True for older format
            logger.warning(f"Transcript marked as failed: {video_id}")
            return None
        
        if not data.get("segments"):
            logger.warning(f"Transcript has no segments: {video_id}")
            return None
        
        return data
        
    except Exception as e:
        logger.error(f"Failed to load transcript {video_id}: {e}")
        return None


def save_chunks(chunk_data: dict, output_dir: Path, logger: Optional[logging.Logger] = None) -> Optional[Path]:
    """
    Save chunks to JSON file.
    
    Args:
        chunk_data: Chunk data dictionary
        output_dir: Output directory
        logger: Logger instance
        
    Returns:
        Path to saved file or None on failure
    """
    if logger is None:
        logger = logging.getLogger("chunk_transcript")
    
    if not chunk_data.get("success"):
        return None
    
    video_id = chunk_data["video_id"]
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    output_path = output_dir / f"{video_id}_chunks.json"
    
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(chunk_data, f, indent=2, ensure_ascii=False)
        
        logger.debug(f"Saved chunks: {output_path}")
        return output_path
        
    except Exception as e:
        logger.error(f"Failed to save chunks for {video_id}: {e}")
        return None


def chunks_exist(video_id: str, output_dir: Path) -> bool:
    """Check if chunks already exist for a video."""
    chunk_path = Path(output_dir) / f"{video_id}_chunks.json"
    return chunk_path.exists()


def load_video_ids_from_report(report_path: Path, logger: Optional[logging.Logger] = None) -> list[dict]:
    """
    Load video IDs from transcript_report.json.
    
    Args:
        report_path: Path to report file
        logger: Logger instance
        
    Returns:
        List of video info dictionaries
    """
    if logger is None:
        logger = logging.getLogger("chunk_transcript")
    
    try:
        with open(report_path, "r", encoding="utf-8") as f:
            report = json.load(f)
    except Exception as e:
        logger.error(f"Failed to load report {report_path}: {e}")
        return []
    
    videos = []
    
    # Handle transcript_report.json format
    if "results" in report:
        for r in report["results"]:
            if r.get("status") == "success" and "video_id" in r:
                videos.append({
                    "video_id": r["video_id"],
                    "title": r.get("title", "")
                })
    
    logger.info(f"Loaded {len(videos)} video(s) from report")
    return videos


def get_all_transcripts(transcripts_dir: Path, logger: Optional[logging.Logger] = None) -> list[dict]:
    """
    Get all transcript video IDs from directory.
    
    Args:
        transcripts_dir: Directory containing transcripts
        logger: Logger instance
        
    Returns:
        List of video info dictionaries
    """
    if logger is None:
        logger = logging.getLogger("chunk_transcript")
    
    transcripts_dir = Path(transcripts_dir)
    
    if not transcripts_dir.exists():
        logger.warning(f"Transcripts directory not found: {transcripts_dir}")
        return []
    
    videos = []
    
    for json_file in transcripts_dir.glob("*.json"):
        # Skip report files
        if json_file.name.endswith("_report.json"):
            continue
        
        video_id = json_file.stem
        
        # Try to get title from file
        title = ""
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                title = data.get("title", "")
                
                # Skip failed transcripts
                if not data.get("success", True):
                    continue
                if not data.get("segments"):
                    continue
        except:
            pass
        
        videos.append({
            "video_id": video_id,
            "title": title
        })
    
    logger.info(f"Found {len(videos)} transcript(s) in {transcripts_dir}")
    return videos


def find_transcript_report(logger: Optional[logging.Logger] = None) -> Optional[Path]:
    """
    Auto-detect transcript_report.json in standard locations.
    
    Args:
        logger: Logger instance
        
    Returns:
        Path to report file or None
    """
    if logger is None:
        logger = logging.getLogger("chunk_transcript")
    
    candidates = [
        TRANSCRIPTS_DIR / "transcript_report.json",
        Path("data/transcripts/transcript_report.json"),
        Path("transcript_report.json"),
    ]
    
    for path in candidates:
        if path.exists():
            logger.info(f"Auto-detected report: {path}")
            return path
    
    return None


# ============================================================================
# BATCH PROCESSING
# ============================================================================

def process_videos(
    videos: list[dict],
    transcripts_dir: Path,
    output_dir: Path,
    target_duration: float = 120.0,
    overlap: float = 15.0,
    min_duration: float = 30.0,
    force: bool = False,
    logger: Optional[logging.Logger] = None
) -> dict:
    """
    Process multiple videos and generate chunks.
    
    Args:
        videos: List of video info dictionaries
        transcripts_dir: Directory containing transcripts
        output_dir: Output directory for chunks
        target_duration: Target chunk duration in seconds
        overlap: Overlap between chunks in seconds
        min_duration: Minimum chunk duration in seconds
        force: Force re-chunk existing
        logger: Logger instance
        
    Returns:
        Processing report dictionary
    """
    if logger is None:
        logger = logging.getLogger("chunk_transcript")
    
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    report = {
        "processed_at": datetime.now().isoformat(),
        "settings": {
            "target_duration_seconds": target_duration,
            "overlap_seconds": overlap,
            "min_chunk_seconds": min_duration,
            "force": force
        },
        "summary": {
            "total": len(videos),
            "success": 0,
            "skipped": 0,
            "no_transcript": 0,
            "failed": 0,
            "total_chunks": 0,
            "total_words": 0
        },
        "results": []
    }
    
    for i, video_info in enumerate(videos, 1):
        video_id = video_info.get("video_id")
        title = video_info.get("title", "")
        
        if not video_id:
            logger.warning(f"Skipping entry without video_id")
            continue
        
        logger.info(f"[{i}/{len(videos)}] Processing: {video_id}")
        
        # Check if already exists
        if not force and chunks_exist(video_id, output_dir):
            logger.info(f"  Skipping (already exists): {video_id}")
            report["summary"]["skipped"] += 1
            report["results"].append({
                "video_id": video_id,
                "title": title,
                "status": "skipped",
                "reason": "already_exists"
            })
            continue
        
        # Load transcript
        transcript_data = load_transcript(video_id, transcripts_dir, logger)
        
        if transcript_data is None:
            report["summary"]["no_transcript"] += 1
            report["results"].append({
                "video_id": video_id,
                "title": title,
                "status": "no_transcript",
                "error": "Transcript not found or invalid"
            })
            continue
        
        # Add title if not in transcript
        if not transcript_data.get("title") and title:
            transcript_data["title"] = title
        
        # Chunk the transcript
        chunk_data = chunk_transcript(
            transcript_data=transcript_data,
            target_duration=target_duration,
            overlap=overlap,
            min_duration=min_duration,
            logger=logger
        )
        
        if chunk_data.get("success"):
            # Save chunks
            output_path = save_chunks(chunk_data, output_dir, logger)
            
            if output_path:
                report["summary"]["success"] += 1
                report["summary"]["total_chunks"] += chunk_data["total_chunks"]
                report["summary"]["total_words"] += chunk_data["total_words"]
                
                report["results"].append({
                    "video_id": video_id,
                    "title": chunk_data.get("title", title),
                    "status": "success",
                    "chunks": chunk_data["total_chunks"],
                    "words": chunk_data["total_words"],
                    "duration_seconds": chunk_data["total_duration_seconds"],
                    "output_path": str(output_path)
                })
            else:
                report["summary"]["failed"] += 1
                report["results"].append({
                    "video_id": video_id,
                    "title": title,
                    "status": "failed",
                    "error": "Failed to save chunks"
                })
        else:
            report["summary"]["failed"] += 1
            report["results"].append({
                "video_id": video_id,
                "title": title,
                "status": "failed",
                "error": chunk_data.get("error", "Unknown error")
            })
    
    return report


def save_report(report: dict, output_dir: Path, logger: Optional[logging.Logger] = None) -> Path:
    """Save processing report to JSON file."""
    if logger is None:
        logger = logging.getLogger("chunk_transcript")
    
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    report_path = output_dir / "chunk_report.json"
    
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
        description="Split transcripts into searchable chunks for semantic search",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --video-id abc123xyz              # Chunk single video
  %(prog)s --all                             # Chunk all transcripts
  %(prog)s --from-report transcript_report.json  # From report
  %(prog)s                                   # Auto-detect report
  %(prog)s --chunk-duration 180 --overlap 20 # Custom settings
  %(prog)s --video-id abc123 --force         # Re-chunk existing
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
        "--all",
        action="store_true",
        help="Process all transcripts in directory"
    )
    input_group.add_argument(
        "--from-report",
        help="Path to transcript_report.json"
    )
    
    # Chunking options
    parser.add_argument(
        "--chunk-duration", "-d",
        type=float,
        default=CHUNK_DURATION_SECONDS,
        help=f"Target chunk duration in seconds (default: {CHUNK_DURATION_SECONDS})"
    )
    parser.add_argument(
        "--overlap", "-o",
        type=float,
        default=CHUNK_OVERLAP_SECONDS,
        help=f"Overlap between chunks in seconds (default: {CHUNK_OVERLAP_SECONDS})"
    )
    parser.add_argument(
        "--min-duration",
        type=float,
        default=CHUNK_MIN_SECONDS,
        help=f"Minimum chunk duration in seconds (default: {CHUNK_MIN_SECONDS})"
    )
    
    # Directories
    parser.add_argument(
        "--transcripts-dir",
        type=Path,
        default=TRANSCRIPTS_DIR,
        help=f"Transcripts input directory (default: {TRANSCRIPTS_DIR})"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=CHUNKS_DIR,
        help=f"Chunks output directory (default: {CHUNKS_DIR})"
    )
    
    # Other options
    parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Force re-chunk (overwrite existing)"
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
    
    # Determine input source
    videos = []
    
    if args.video_id:
        # Single video
        videos = [{"video_id": args.video_id}]
        
    elif args.all:
        # All transcripts in directory
        videos = get_all_transcripts(args.transcripts_dir, logger)
        
    elif args.from_report:
        # From specified report
        report_path = Path(args.from_report)
        if not report_path.exists():
            logger.error(f"Report not found: {report_path}")
            sys.exit(1)
        videos = load_video_ids_from_report(report_path, logger)
        
    else:
        # Auto-detect transcript report
        report_path = find_transcript_report(logger)
        if report_path:
            videos = load_video_ids_from_report(report_path, logger)
        else:
            # Fall back to all transcripts
            logger.info("No report found, processing all transcripts")
            videos = get_all_transcripts(args.transcripts_dir, logger)
    
    if not videos:
        logger.error("No videos to process")
        sys.exit(1)
    
    logger.info(f"Processing {len(videos)} video(s)")
    
    # Single video with JSON output
    if len(videos) == 1 and args.json:
        video_id = videos[0]["video_id"]
        transcript_data = load_transcript(video_id, args.transcripts_dir, logger)
        
        if transcript_data is None:
            result = {
                "video_id": video_id,
                "success": False,
                "error": "Transcript not found"
            }
        else:
            result = chunk_transcript(
                transcript_data=transcript_data,
                target_duration=args.chunk_duration,
                overlap=args.overlap,
                min_duration=args.min_duration,
                logger=logger
            )
        
        print(json.dumps(result, indent=2))
        sys.exit(0 if result.get("success") else 1)
    
    # Batch processing
    report = process_videos(
        videos=videos,
        transcripts_dir=args.transcripts_dir,
        output_dir=args.output_dir,
        target_duration=args.chunk_duration,
        overlap=args.overlap,
        min_duration=args.min_duration,
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
        f"{summary['no_transcript']} no transcript, "
        f"{summary['failed']} failed"
    )
    
    if summary['success'] > 0:
        logger.info(
            f"Total: {summary['total_chunks']} chunks, "
            f"{summary['total_words']} words"
        )
    
    # Exit code based on success
    if summary["success"] > 0 or summary["skipped"] > 0:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
