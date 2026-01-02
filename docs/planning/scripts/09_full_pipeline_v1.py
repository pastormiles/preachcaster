#!/usr/bin/env python3
"""
================================================================================
PreachCaster Pipeline Orchestrator
================================================================================

Script: 09_full_pipeline_v1.py
Version: 1.0
Created: CW08
Purpose: Orchestrate complete processing pipeline for sermon videos

DESCRIPTION
-----------
Master orchestration script that coordinates all processing steps for converting
YouTube sermon videos into fully-indexed, AI-enriched podcast episodes. This
script runs steps 02-08 in sequence and generates a complete episode package.

PIPELINE STEPS
--------------
Step 1: Extract Audio (02_extract_audio_v1.py)
        └── Output: audio/{video_id}.mp3

Step 2: Fetch Transcript (03_fetch_transcript_v1.py)
        └── Output: data/transcripts/{video_id}.json

Step 3: Chunk Transcript (04_chunk_transcript_v1.py)
        └── Output: data/chunks/{video_id}_chunks.json

Step 4: Generate Embeddings (05_generate_embeddings_v1.py)
        └── Output: data/embeddings/{video_id}_embeddings.json

Step 5: Upload to Pinecone (06_upload_pinecone_v1.py)
        └── Output: Vectors in Pinecone

Step 6: Generate AI Content (07_generate_ai_content_v1.py)
        └── Output: data/ai_content/{video_id}_ai_content.json

Step 7: Generate Discussion Guide (08_generate_discussion_guide_v1.py)
        └── Output: guides/{video_id}_discussion_guide.pdf

USAGE
-----
# Process single video through full pipeline
python 09_full_pipeline_v1.py --video-id abc123xyz

# Process multiple videos
python 09_full_pipeline_v1.py --video-ids abc123,def456,ghi789

# Process from new_videos.json
python 09_full_pipeline_v1.py --from-file data/video_ids/new_videos.json

# Auto-detect input
python 09_full_pipeline_v1.py

# Run specific steps only (1-7)
python 09_full_pipeline_v1.py --video-id abc123 --steps 1,2,3

# Skip certain steps
python 09_full_pipeline_v1.py --video-id abc123 --skip-steps 4,5

# Resume from last failure
python 09_full_pipeline_v1.py --video-id abc123 --resume

# Dry run (show what would be done)
python 09_full_pipeline_v1.py --video-id abc123 --dry-run

# Force re-process all steps
python 09_full_pipeline_v1.py --video-id abc123 --force

# Parallel processing (multiple videos)
python 09_full_pipeline_v1.py --from-file new_videos.json --parallel 3

# JSON output
python 09_full_pipeline_v1.py --video-id abc123 --json

# Quiet mode
python 09_full_pipeline_v1.py --video-id abc123 --quiet

OUTPUT FILES
------------
- data/episodes/{video_id}_episode.json  : Complete episode package
- data/pipeline/{video_id}_state.json    : Pipeline state (for resume)
- data/pipeline/pipeline_report.json     : Batch processing report

DEPENDENCIES
------------
- All pipeline scripts (02-08) must be in same directory
- Python 3.8+
- See individual scripts for their dependencies

================================================================================
"""

import argparse
import json
import logging
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

try:
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from config.config import (
        VIDEO_IDS_DIR,
        TRANSCRIPTS_DIR,
        CHUNKS_DIR,
        EMBEDDINGS_DIR,
        AI_CONTENT_DIR,
        EPISODES_DIR,
        AUDIO_DIR,
        GUIDES_DIR,
        LOGS_DIR,
        DATA_DIR,
        PINECONE_NAMESPACE,
        CHURCH_NAME,
    )
    CONFIG_LOADED = True
except ImportError:
    CONFIG_LOADED = False
    # Defaults for standalone operation
    VIDEO_IDS_DIR = Path("data/video_ids")
    TRANSCRIPTS_DIR = Path("data/transcripts")
    CHUNKS_DIR = Path("data/chunks")
    EMBEDDINGS_DIR = Path("data/embeddings")
    AI_CONTENT_DIR = Path("data/ai_content")
    EPISODES_DIR = Path("data/episodes")
    AUDIO_DIR = Path("audio")
    GUIDES_DIR = Path("guides")
    LOGS_DIR = Path("logs")
    DATA_DIR = Path("data")
    PINECONE_NAMESPACE = "default"
    CHURCH_NAME = "Church"

# Pipeline directory for state files
PIPELINE_DIR = DATA_DIR / "pipeline" if CONFIG_LOADED else Path("data/pipeline")

# ---------------------------------------------------------------------------
# Logging Setup
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pipeline Step Definitions
# ---------------------------------------------------------------------------

PIPELINE_STEPS = {
    1: {
        "name": "audio",
        "script": "02_extract_audio_v1.py",
        "description": "Extract audio from YouTube",
        "output_check": lambda vid: AUDIO_DIR / f"{vid}.mp3",
        "args": lambda vid: ["--video-id", vid],
    },
    2: {
        "name": "transcript",
        "script": "03_fetch_transcript_v1.py",
        "description": "Fetch transcript from YouTube",
        "output_check": lambda vid: TRANSCRIPTS_DIR / f"{vid}.json",
        "args": lambda vid: ["--video-id", vid],
    },
    3: {
        "name": "chunks",
        "script": "04_chunk_transcript_v1.py",
        "description": "Chunk transcript for search",
        "output_check": lambda vid: CHUNKS_DIR / f"{vid}_chunks.json",
        "args": lambda vid: ["--video-id", vid],
    },
    4: {
        "name": "embeddings",
        "script": "05_generate_embeddings_v1.py",
        "description": "Generate embeddings",
        "output_check": lambda vid: EMBEDDINGS_DIR / f"{vid}_embeddings.json",
        "args": lambda vid: ["--video-id", vid],
    },
    5: {
        "name": "pinecone",
        "script": "06_upload_pinecone_v1.py",
        "description": "Upload to Pinecone",
        "output_check": None,  # No file output, check embeddings file
        "args": lambda vid: ["--video-id", vid],
    },
    6: {
        "name": "ai_content",
        "script": "07_generate_ai_content_v1.py",
        "description": "Generate AI content",
        "output_check": lambda vid: AI_CONTENT_DIR / f"{vid}_ai_content.json",
        "args": lambda vid: ["--video-id", vid],
    },
    7: {
        "name": "guide",
        "script": "08_generate_discussion_guide_v1.py",
        "description": "Generate discussion guide PDF",
        "output_check": lambda vid: GUIDES_DIR / f"{vid}_discussion_guide.pdf",
        "args": lambda vid: ["--video-id", vid],
    },
}

# ---------------------------------------------------------------------------
# Custom Exceptions
# ---------------------------------------------------------------------------

class PipelineError(Exception):
    """Exception raised when a pipeline step fails."""
    def __init__(self, step: int, step_name: str, video_id: str, error: str, returncode: int = 1):
        self.step = step
        self.step_name = step_name
        self.video_id = video_id
        self.error = error
        self.returncode = returncode
        super().__init__(f"Step {step} ({step_name}) failed for {video_id}: {error}")

# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------

def ensure_directories() -> None:
    """Create required directories if they don't exist."""
    dirs = [
        VIDEO_IDS_DIR, TRANSCRIPTS_DIR, CHUNKS_DIR, EMBEDDINGS_DIR,
        AI_CONTENT_DIR, EPISODES_DIR, AUDIO_DIR, GUIDES_DIR, 
        LOGS_DIR, PIPELINE_DIR
    ]
    for d in dirs:
        Path(d).mkdir(parents=True, exist_ok=True)


def get_script_path(script_name: str) -> Path:
    """Get the full path to a pipeline script."""
    script_dir = Path(__file__).parent
    return script_dir / script_name


def load_json_file(filepath: Path) -> Optional[dict]:
    """Load a JSON file, return None if not found."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def save_json_file(filepath: Path, data: dict) -> None:
    """Save data to a JSON file."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, default=str)


def format_duration(seconds: float) -> str:
    """Format seconds as MM:SS or HH:MM:SS."""
    seconds = int(seconds)
    if seconds >= 3600:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        return f"{hours}:{minutes:02d}:{secs:02d}"
    else:
        minutes = seconds // 60
        secs = seconds % 60
        return f"{minutes}:{secs:02d}"


def load_new_videos_file(filepath: Path) -> list[dict]:
    """Load videos from a new_videos.json file."""
    data = load_json_file(filepath)
    if not data:
        return []
    
    # Handle both list format and dict with 'videos' key
    if isinstance(data, list):
        return data
    elif isinstance(data, dict) and 'videos' in data:
        return data['videos']
    elif isinstance(data, dict) and 'new_videos' in data:
        return data['new_videos']
    return []


def get_video_metadata(video_id: str) -> dict:
    """Get video metadata from transcript or other sources."""
    metadata = {
        "video_id": video_id,
        "title": None,
        "published_at": None,
        "duration_seconds": None,
        "duration_formatted": None,
        "youtube_url": f"https://www.youtube.com/watch?v={video_id}",
    }
    
    # Try to get metadata from transcript file
    transcript_file = TRANSCRIPTS_DIR / f"{video_id}.json"
    transcript_data = load_json_file(transcript_file)
    if transcript_data:
        metadata["title"] = transcript_data.get("title")
        metadata["published_at"] = transcript_data.get("published_at")
        
        # Calculate duration from transcript entries
        entries = transcript_data.get("entries", transcript_data.get("transcript", []))
        if entries:
            last_entry = entries[-1]
            if isinstance(last_entry, dict):
                end_time = last_entry.get("start", 0) + last_entry.get("duration", 0)
                metadata["duration_seconds"] = int(end_time)
                metadata["duration_formatted"] = format_duration(end_time)
    
    # Try to get title from new_videos.json if not found
    if not metadata["title"]:
        new_videos_file = VIDEO_IDS_DIR / "new_videos.json"
        videos = load_new_videos_file(new_videos_file)
        for vid in videos:
            if vid.get("video_id") == video_id:
                metadata["title"] = vid.get("title")
                metadata["published_at"] = vid.get("published_at")
                break
    
    return metadata


def get_audio_duration(video_id: str) -> Optional[int]:
    """Get audio duration from extraction report or file."""
    # Try extraction report first
    report_file = EPISODES_DIR / "extraction_report.json"
    report = load_json_file(report_file)
    if report and "extractions" in report:
        for extraction in report["extractions"]:
            if extraction.get("video_id") == video_id:
                return extraction.get("duration_seconds")
    
    # Could also probe the MP3 file with ffprobe if needed
    return None

# ---------------------------------------------------------------------------
# Pipeline State Management
# ---------------------------------------------------------------------------

def get_state_file(video_id: str) -> Path:
    """Get the path to the pipeline state file for a video."""
    return PIPELINE_DIR / f"{video_id}_state.json"


def load_pipeline_state(video_id: str) -> Optional[dict]:
    """Load pipeline state for a video."""
    return load_json_file(get_state_file(video_id))


def save_pipeline_state(video_id: str, state: dict) -> None:
    """Save pipeline state for a video."""
    save_json_file(get_state_file(video_id), state)


def create_initial_state(video_id: str) -> dict:
    """Create initial pipeline state for a video."""
    return {
        "video_id": video_id,
        "status": "pending",
        "started_at": datetime.now().isoformat(),
        "completed_at": None,
        "completed_steps": [],
        "failed_step": None,
        "error": None,
        "step_timings": {},
        "costs": {
            "embeddings_usd": 0.0,
            "ai_content_usd": 0.0,
            "total_usd": 0.0,
        },
    }


def update_step_success(state: dict, step: int, step_name: str, duration: float) -> None:
    """Update state after successful step completion."""
    if step_name not in state["completed_steps"]:
        state["completed_steps"].append(step_name)
    state["step_timings"][step_name] = duration
    state["failed_step"] = None
    state["error"] = None


def update_step_failure(state: dict, step: int, step_name: str, error: str) -> None:
    """Update state after step failure."""
    state["status"] = "failed"
    state["failed_step"] = step_name
    state["error"] = error

# ---------------------------------------------------------------------------
# Step Execution
# ---------------------------------------------------------------------------

def check_step_output_exists(step: int, video_id: str) -> bool:
    """Check if a step's output already exists."""
    step_info = PIPELINE_STEPS.get(step)
    if not step_info:
        return False
    
    output_check = step_info.get("output_check")
    if output_check:
        output_path = output_check(video_id)
        return output_path.exists()
    
    # For Pinecone step, check if embeddings were uploaded
    # (We can't easily check Pinecone, so we'll rely on state)
    return False


def run_step(
    step: int,
    video_id: str,
    force: bool = False,
    dry_run: bool = False,
    quiet: bool = False
) -> tuple[bool, float, Optional[str]]:
    """
    Run a single pipeline step.
    
    Returns:
        tuple: (success, duration_seconds, error_message)
    """
    step_info = PIPELINE_STEPS.get(step)
    if not step_info:
        return False, 0.0, f"Unknown step: {step}"
    
    step_name = step_info["name"]
    script_name = step_info["script"]
    description = step_info["description"]
    
    # Check if output already exists (skip unless force)
    if not force and check_step_output_exists(step, video_id):
        if not quiet:
            logger.info(f"  Step {step} ({step_name}): Skipped (output exists)")
        return True, 0.0, None
    
    if dry_run:
        if not quiet:
            logger.info(f"  Step {step} ({step_name}): Would run {script_name}")
        return True, 0.0, None
    
    # Get script path
    script_path = get_script_path(script_name)
    if not script_path.exists():
        return False, 0.0, f"Script not found: {script_path}"
    
    # Build command
    args = step_info["args"](video_id)
    cmd = [sys.executable, str(script_path)] + args
    
    if force:
        cmd.append("--force")
    
    if not quiet:
        logger.info(f"  Step {step} ({step_name}): {description}...")
    
    # Run the script
    start_time = time.time()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,  # 10 minute timeout per step
        )
        duration = time.time() - start_time
        
        if result.returncode == 0:
            if not quiet:
                logger.info(f"  Step {step} ({step_name}): Completed in {duration:.1f}s")
            return True, duration, None
        else:
            error_msg = result.stderr.strip() or result.stdout.strip() or "Unknown error"
            # Truncate long error messages
            if len(error_msg) > 500:
                error_msg = error_msg[:500] + "..."
            return False, duration, error_msg
            
    except subprocess.TimeoutExpired:
        duration = time.time() - start_time
        return False, duration, "Step timed out after 10 minutes"
    except Exception as e:
        duration = time.time() - start_time
        return False, duration, str(e)


def get_steps_to_run(
    steps: Optional[str] = None,
    skip_steps: Optional[str] = None,
    resume_from: Optional[int] = None
) -> list[int]:
    """Determine which steps to run based on arguments."""
    all_steps = list(PIPELINE_STEPS.keys())
    
    if steps:
        # Run only specified steps
        try:
            return sorted([int(s.strip()) for s in steps.split(",")])
        except ValueError:
            logger.error(f"Invalid steps format: {steps}")
            return all_steps
    
    if skip_steps:
        # Skip specified steps
        try:
            skip = [int(s.strip()) for s in skip_steps.split(",")]
            return [s for s in all_steps if s not in skip]
        except ValueError:
            logger.error(f"Invalid skip-steps format: {skip_steps}")
            return all_steps
    
    if resume_from:
        # Resume from a specific step
        return [s for s in all_steps if s >= resume_from]
    
    return all_steps

# ---------------------------------------------------------------------------
# Episode Package Generation
# ---------------------------------------------------------------------------

def generate_episode_package(video_id: str, state: dict) -> dict:
    """Generate the complete episode package JSON."""
    metadata = get_video_metadata(video_id)
    
    # Get audio duration
    audio_duration = get_audio_duration(video_id)
    if audio_duration:
        metadata["duration_seconds"] = audio_duration
        metadata["duration_formatted"] = format_duration(audio_duration)
    
    # Load AI content
    ai_content_file = AI_CONTENT_DIR / f"{video_id}_ai_content.json"
    ai_content = load_json_file(ai_content_file) or {}
    
    # Load chunk count
    chunks_file = CHUNKS_DIR / f"{video_id}_chunks.json"
    chunks_data = load_json_file(chunks_file)
    chunk_count = chunks_data.get("total_chunks", 0) if chunks_data else 0
    
    # Load embeddings cost
    embeddings_file = EMBEDDINGS_DIR / f"{video_id}_embeddings.json"
    embeddings_data = load_json_file(embeddings_file)
    embeddings_cost = embeddings_data.get("estimated_cost_usd", 0) if embeddings_data else 0
    
    # Get AI content cost
    ai_cost = ai_content.get("estimated_cost_usd", 0)
    
    # Build file paths (relative)
    files = {
        "audio": f"audio/{video_id}.mp3",
        "transcript_json": f"data/transcripts/{video_id}.json",
        "transcript_txt": f"data/transcripts/{video_id}.txt",
        "chunks": f"data/chunks/{video_id}_chunks.json",
        "embeddings": f"data/embeddings/{video_id}_embeddings.json",
        "ai_content": f"data/ai_content/{video_id}_ai_content.json",
        "discussion_guide": f"guides/{video_id}_discussion_guide.pdf",
    }
    
    # Check which files actually exist
    files_exist = {}
    for key, path in files.items():
        files_exist[key] = Path(path).exists()
    
    # Build episode package
    episode = {
        "video_id": video_id,
        "title": metadata.get("title") or ai_content.get("title") or f"Episode {video_id}",
        "youtube_url": metadata["youtube_url"],
        "published_at": metadata.get("published_at"),
        "duration_seconds": metadata.get("duration_seconds"),
        "duration_formatted": metadata.get("duration_formatted"),
        
        "files": files,
        "files_exist": files_exist,
        
        "ai_content": {
            "summary": ai_content.get("summary"),
            "big_idea": ai_content.get("big_idea"),
            "primary_scripture": ai_content.get("primary_scripture"),
            "supporting_scriptures": ai_content.get("supporting_scriptures", []),
            "topics": ai_content.get("topics", []),
        },
        
        "search": {
            "indexed": "pinecone" in state.get("completed_steps", []),
            "pinecone_namespace": PINECONE_NAMESPACE if CONFIG_LOADED else "default",
            "chunk_count": chunk_count,
            "vector_count": chunk_count,  # Same as chunk count
        },
        
        "processing": {
            "started_at": state.get("started_at"),
            "completed_at": state.get("completed_at"),
            "duration_seconds": sum(state.get("step_timings", {}).values()),
            "steps_completed": state.get("completed_steps", []),
            "step_timings": state.get("step_timings", {}),
            "costs": {
                "embeddings_usd": embeddings_cost,
                "ai_content_usd": ai_cost,
                "total_usd": embeddings_cost + ai_cost,
            },
        },
        
        "wordpress": {
            "published": False,
            "post_id": None,
            "post_url": None,
        },
    }
    
    return episode


def save_episode_package(video_id: str, episode: dict) -> Path:
    """Save the episode package JSON file."""
    episode_file = EPISODES_DIR / f"{video_id}_episode.json"
    save_json_file(episode_file, episode)
    return episode_file

# ---------------------------------------------------------------------------
# Main Pipeline Processing
# ---------------------------------------------------------------------------

def process_video(
    video_id: str,
    steps: Optional[str] = None,
    skip_steps: Optional[str] = None,
    resume: bool = False,
    force: bool = False,
    dry_run: bool = False,
    quiet: bool = False
) -> dict:
    """
    Process a single video through the pipeline.
    
    Returns:
        dict: Processing result with status and details
    """
    result = {
        "video_id": video_id,
        "success": False,
        "steps_completed": [],
        "steps_failed": [],
        "duration_seconds": 0,
        "error": None,
        "episode_file": None,
    }
    
    # Load or create state
    state = None
    resume_from_step = None
    
    if resume:
        state = load_pipeline_state(video_id)
        if state and state.get("failed_step"):
            # Find the step number that failed
            for step_num, step_info in PIPELINE_STEPS.items():
                if step_info["name"] == state["failed_step"]:
                    resume_from_step = step_num
                    break
            if not quiet:
                logger.info(f"Resuming from step {resume_from_step}")
    
    if not state:
        state = create_initial_state(video_id)
    
    # Determine steps to run
    steps_to_run = get_steps_to_run(
        steps=steps,
        skip_steps=skip_steps,
        resume_from=resume_from_step
    )
    
    if not quiet:
        step_names = [PIPELINE_STEPS[s]["name"] for s in steps_to_run]
        logger.info(f"Processing {video_id}: steps {step_names}")
    
    if dry_run and not quiet:
        logger.info("  [DRY RUN - no actual processing]")
    
    # Run each step
    total_start = time.time()
    state["status"] = "processing"
    
    for step in steps_to_run:
        step_name = PIPELINE_STEPS[step]["name"]
        
        success, duration, error = run_step(
            step=step,
            video_id=video_id,
            force=force,
            dry_run=dry_run,
            quiet=quiet
        )
        
        if success:
            update_step_success(state, step, step_name, duration)
            result["steps_completed"].append(step_name)
        else:
            update_step_failure(state, step, step_name, error)
            result["steps_failed"].append({"step": step_name, "error": error})
            result["error"] = f"Step {step} ({step_name}) failed: {error}"
            
            # Save state for resume
            if not dry_run:
                save_pipeline_state(video_id, state)
            
            if not quiet:
                logger.error(f"  Step {step} ({step_name}): FAILED - {error}")
            
            # Stop pipeline on failure
            break
    
    # Calculate total duration
    total_duration = time.time() - total_start
    result["duration_seconds"] = total_duration
    
    # Check if all requested steps completed
    if not result["steps_failed"]:
        result["success"] = True
        state["status"] = "completed"
        state["completed_at"] = datetime.now().isoformat()
        
        if not dry_run:
            # Generate and save episode package
            episode = generate_episode_package(video_id, state)
            episode_file = save_episode_package(video_id, episode)
            result["episode_file"] = str(episode_file)
            
            # Update state costs from episode
            state["costs"] = episode["processing"]["costs"]
            
            # Save final state
            save_pipeline_state(video_id, state)
        
        if not quiet:
            logger.info(f"✓ {video_id} completed in {format_duration(total_duration)}")
    else:
        if not quiet:
            logger.error(f"✗ {video_id} failed at step {result['steps_failed'][0]['step']}")
    
    return result


def process_videos_parallel(
    video_ids: list[str],
    max_workers: int = 3,
    **kwargs
) -> list[dict]:
    """Process multiple videos in parallel."""
    results = []
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(process_video, vid, **kwargs): vid
            for vid in video_ids
        }
        
        for future in as_completed(futures):
            video_id = futures[future]
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                results.append({
                    "video_id": video_id,
                    "success": False,
                    "error": str(e),
                })
    
    return results


def generate_pipeline_report(results: list[dict]) -> dict:
    """Generate a summary report for batch processing."""
    successful = [r for r in results if r.get("success")]
    failed = [r for r in results if not r.get("success")]
    
    total_duration = sum(r.get("duration_seconds", 0) for r in results)
    
    report = {
        "generated_at": datetime.now().isoformat(),
        "summary": {
            "total_videos": len(results),
            "successful": len(successful),
            "failed": len(failed),
            "total_duration_seconds": total_duration,
            "total_duration_formatted": format_duration(total_duration),
        },
        "successful": [
            {
                "video_id": r["video_id"],
                "duration_seconds": r.get("duration_seconds", 0),
                "episode_file": r.get("episode_file"),
            }
            for r in successful
        ],
        "failed": [
            {
                "video_id": r["video_id"],
                "error": r.get("error"),
            }
            for r in failed
        ],
    }
    
    return report

# ---------------------------------------------------------------------------
# Input Detection
# ---------------------------------------------------------------------------

def detect_input() -> tuple[str, list[str]]:
    """
    Auto-detect input source and return video IDs.
    
    Returns:
        tuple: (source_description, list_of_video_ids)
    """
    # Check for new_videos.json
    new_videos_file = VIDEO_IDS_DIR / "new_videos.json"
    if new_videos_file.exists():
        videos = load_new_videos_file(new_videos_file)
        if videos:
            video_ids = [v.get("video_id") for v in videos if v.get("video_id")]
            if video_ids:
                return f"new_videos.json ({len(video_ids)} videos)", video_ids
    
    return "none", []

# ---------------------------------------------------------------------------
# CLI Interface
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="PreachCaster Pipeline Orchestrator - Process YouTube videos end-to-end",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --video-id abc123xyz           Process single video
  %(prog)s --video-ids a,b,c              Process multiple videos
  %(prog)s --from-file new_videos.json    Process from file
  %(prog)s                                Auto-detect input
  %(prog)s --video-id abc123 --steps 1,2  Run specific steps
  %(prog)s --video-id abc123 --resume     Resume from failure
  %(prog)s --video-id abc123 --dry-run    Preview without processing
        """
    )
    
    # Input options
    input_group = parser.add_argument_group("Input Options")
    input_group.add_argument(
        "--video-id",
        help="Single YouTube video ID to process"
    )
    input_group.add_argument(
        "--video-ids",
        help="Comma-separated list of video IDs"
    )
    input_group.add_argument(
        "--from-file",
        help="Path to JSON file with video list"
    )
    
    # Step control options
    step_group = parser.add_argument_group("Step Control")
    step_group.add_argument(
        "--steps",
        help="Comma-separated list of steps to run (1-7)"
    )
    step_group.add_argument(
        "--skip-steps",
        help="Comma-separated list of steps to skip"
    )
    step_group.add_argument(
        "--resume",
        action="store_true",
        help="Resume from last failed step"
    )
    
    # Processing options
    proc_group = parser.add_argument_group("Processing Options")
    proc_group.add_argument(
        "--force",
        action="store_true",
        help="Force re-process all steps (ignore existing outputs)"
    )
    proc_group.add_argument(
        "--parallel",
        type=int,
        metavar="N",
        help="Process N videos in parallel"
    )
    proc_group.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without processing"
    )
    
    # Output options
    output_group = parser.add_argument_group("Output Options")
    output_group.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON"
    )
    output_group.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Minimal output"
    )
    
    return parser.parse_args()


def main() -> int:
    """Main entry point."""
    args = parse_args()
    
    # Set up logging
    if args.quiet:
        logging.getLogger().setLevel(logging.WARNING)
    
    # Ensure directories exist
    ensure_directories()
    
    # Determine video IDs to process
    video_ids = []
    source = ""
    
    if args.video_id:
        video_ids = [args.video_id]
        source = "command line (single)"
    elif args.video_ids:
        video_ids = [v.strip() for v in args.video_ids.split(",")]
        source = f"command line ({len(video_ids)} videos)"
    elif args.from_file:
        filepath = Path(args.from_file)
        if not filepath.exists():
            logger.error(f"File not found: {filepath}")
            return 1
        videos = load_new_videos_file(filepath)
        video_ids = [v.get("video_id") for v in videos if v.get("video_id")]
        source = f"{filepath.name} ({len(video_ids)} videos)"
    else:
        source, video_ids = detect_input()
    
    if not video_ids:
        if args.json:
            print(json.dumps({"error": "No videos to process", "source": source}))
        else:
            logger.error("No videos to process. Specify --video-id, --video-ids, or --from-file")
        return 1
    
    if not args.quiet and not args.json:
        logger.info(f"PreachCaster Pipeline Orchestrator")
        logger.info(f"Source: {source}")
        logger.info(f"Videos: {len(video_ids)}")
        if args.dry_run:
            logger.info("[DRY RUN MODE]")
        print()
    
    # Process videos
    results = []
    
    if args.parallel and len(video_ids) > 1:
        # Parallel processing
        if not args.quiet and not args.json:
            logger.info(f"Processing {len(video_ids)} videos with {args.parallel} workers...")
        results = process_videos_parallel(
            video_ids=video_ids,
            max_workers=args.parallel,
            steps=args.steps,
            skip_steps=args.skip_steps,
            resume=args.resume,
            force=args.force,
            dry_run=args.dry_run,
            quiet=args.quiet or args.json,
        )
    else:
        # Sequential processing
        for video_id in video_ids:
            result = process_video(
                video_id=video_id,
                steps=args.steps,
                skip_steps=args.skip_steps,
                resume=args.resume,
                force=args.force,
                dry_run=args.dry_run,
                quiet=args.quiet or args.json,
            )
            results.append(result)
    
    # Generate report
    report = generate_pipeline_report(results)
    
    # Save report (unless dry run)
    if not args.dry_run:
        report_file = PIPELINE_DIR / "pipeline_report.json"
        save_json_file(report_file, report)
    
    # Output results
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print()
        logger.info("=" * 60)
        logger.info("Pipeline Summary")
        logger.info("=" * 60)
        logger.info(f"Total videos:  {report['summary']['total_videos']}")
        logger.info(f"Successful:    {report['summary']['successful']}")
        logger.info(f"Failed:        {report['summary']['failed']}")
        logger.info(f"Total time:    {report['summary']['total_duration_formatted']}")
        
        if report["failed"]:
            print()
            logger.warning("Failed videos:")
            for fail in report["failed"]:
                logger.warning(f"  {fail['video_id']}: {fail['error']}")
    
    # Return exit code
    if report["summary"]["failed"] > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
