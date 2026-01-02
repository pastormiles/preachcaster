#!/usr/bin/env python3
"""
07_generate_ai_content_v1.py
Generate AI-powered content from sermon transcripts.

================================================================================
OVERVIEW
================================================================================
This script uses OpenAI's GPT models to generate value-added content from sermon
transcripts. It extracts key information and creates content for podcast feeds,
website displays, and small group discussions.

This is a core Premium tier feature of PreachCaster that differentiates the
product from basic podcast automation tools.

================================================================================
GENERATED CONTENT
================================================================================
For each sermon transcript, this script generates:

1. SUMMARY
   - 2-3 sentence description for RSS feed/podcast apps
   - Captures the essence of the sermon
   - Written in third person

2. BIG IDEA
   - One memorable sentence capturing the main point
   - Quotable, shareable format
   - Think "Twitter-ready"

3. PRIMARY SCRIPTURE
   - The main Bible passage the sermon is based on
   - Includes reference (e.g., "Philippians 4:6-7")
   - Includes the text of the passage

4. SUPPORTING SCRIPTURES
   - Up to 3 additional passages mentioned
   - Helps with cross-referencing and study

5. TOPICS
   - 3-5 theme tags (single words)
   - Used for filtering and discovery
   - Examples: "grace", "prayer", "anxiety", "forgiveness"

6. DISCUSSION GUIDE CONTENT
   - Icebreaker question for small groups
   - 5 discussion questions referencing sermon content
   - Weekly application challenge
   - 2-3 prayer focus points

================================================================================
INPUT/OUTPUT
================================================================================
INPUT:
  - Transcript JSON file from script 03 (data/transcripts/{video_id}.json)
  - Or transcript_report.json for batch processing
  - Or --all flag to process all transcripts

OUTPUT:
  - data/ai_content/{video_id}_ai_content.json (per video)
  - data/ai_content/ai_content_report.json (batch report)

================================================================================
USAGE
================================================================================
# Generate AI content for single video
python 07_generate_ai_content_v1.py --video-id abc123xyz

# Generate from transcript report
python 07_generate_ai_content_v1.py --from-report data/transcripts/transcript_report.json

# Process all transcript files
python 07_generate_ai_content_v1.py --all

# Auto-detect input
python 07_generate_ai_content_v1.py

# Force re-generate existing
python 07_generate_ai_content_v1.py --video-id abc123 --force

# Dry run (estimate cost without API calls)
python 07_generate_ai_content_v1.py --all --dry-run

# JSON output for single video
python 07_generate_ai_content_v1.py --video-id abc123 --json

# Custom model
python 07_generate_ai_content_v1.py --video-id abc123 --model gpt-4o

================================================================================
COST ESTIMATION
================================================================================
Using gpt-4o-mini (recommended):
  - Input: $0.15 per 1M tokens
  - Output: $0.60 per 1M tokens
  - Typical sermon: ~9,000 input tokens, ~800 output tokens
  - Cost per sermon: ~$0.002

Using gpt-4o (highest quality):
  - Input: $2.50 per 1M tokens
  - Output: $10.00 per 1M tokens
  - Cost per sermon: ~$0.03

================================================================================
DEPENDENCIES
================================================================================
pip install openai tiktoken python-dotenv tqdm

================================================================================
VERSION HISTORY
================================================================================
v1 (2025-01-01): Initial implementation
  - Single comprehensive prompt approach
  - Support for gpt-4o-mini and gpt-4o
  - Dry-run cost estimation
  - Batch processing with reports

================================================================================
"""

import argparse
import json
import logging
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

# Third-party imports
try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

try:
    import tiktoken
    HAS_TIKTOKEN = True
except ImportError:
    HAS_TIKTOKEN = False

try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False

# Try to import config
try:
    sys.path.insert(0, str(Path(__file__).parent.parent / "config"))
    from config import (
        TRANSCRIPTS_DIR, AI_CONTENT_DIR, OPENAI_API_KEY,
        AI_MODEL, ensure_directories
    )
    HAS_CONFIG = True
except ImportError:
    HAS_CONFIG = False
    TRANSCRIPTS_DIR = Path("data/transcripts")
    AI_CONTENT_DIR = Path("data/ai_content")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    AI_MODEL = "gpt-4o-mini"

# =============================================================================
# Configuration
# =============================================================================

# Model pricing (per 1M tokens)
MODEL_PRICING = {
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
}

# Default model
DEFAULT_MODEL = AI_MODEL if HAS_CONFIG else "gpt-4o-mini"

# System prompt for sermon analysis
SYSTEM_PROMPT = """You are an expert at analyzing Christian sermon content. Your task is to extract key information and generate helpful content for church communications and small group discussions.

IMPORTANT GUIDELINES:
1. Be accurate with scripture references - verify book, chapter, and verse numbers are correct
2. Generate content that is theologically sound and practically applicable
3. Maintain the speaker's tone and intent in summaries
4. Create discussion questions that encourage genuine reflection, not just yes/no answers
5. Make application challenges specific and actionable

Always respond in valid JSON format with no markdown formatting or code blocks. Just raw JSON."""

# User prompt template
USER_PROMPT_TEMPLATE = """Analyze this sermon transcript and generate the following content:

1. SUMMARY: A 2-3 sentence summary suitable for a podcast description (third person)
2. BIG_IDEA: One memorable sentence capturing the main point (quotable format)
3. PRIMARY_SCRIPTURE: The main Bible passage referenced
   - Include "reference" (e.g., "Philippians 4:6-7") 
   - Include "text" (the actual verse text, abbreviated if long)
4. SUPPORTING_SCRIPTURES: Up to 3 additional passages mentioned (array of objects with reference and text)
5. TOPICS: 3-5 single-word theme tags (lowercase, e.g., "grace", "prayer", "anxiety")
6. ICEBREAKER: A casual, non-threatening opening question for small group discussion
7. DISCUSSION_QUESTIONS: 5 thoughtful questions that reference specific sermon content
8. APPLICATION: A specific, actionable challenge for the week ahead
9. PRAYER_POINTS: 2-3 specific prayer focus items (array of strings)

SERMON TITLE: {title}

TRANSCRIPT:
{transcript_text}

Respond with valid JSON only, using this exact structure:
{{"summary": "...", "big_idea": "...", "primary_scripture": {{"reference": "...", "text": "..."}}, "supporting_scriptures": [{{"reference": "...", "text": "..."}}], "topics": ["...", "..."], "discussion_guide": {{"icebreaker": "...", "questions": ["...", "...", "...", "...", "..."], "application": "...", "prayer_points": ["...", "..."]}}}}"""

# =============================================================================
# Logging Setup
# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


# =============================================================================
# Token Counting
# =============================================================================

def count_tokens(text: str, model: str = "gpt-4o-mini") -> int:
    """
    Count tokens in text using tiktoken if available, otherwise estimate.
    
    Args:
        text: Text to count tokens for
        model: Model name for tokenizer selection
        
    Returns:
        Token count (exact or estimated)
    """
    if HAS_TIKTOKEN:
        try:
            # GPT-4 and GPT-4o use cl100k_base
            encoding = tiktoken.get_encoding("cl100k_base")
            return len(encoding.encode(text))
        except Exception:
            pass
    
    # Fallback: estimate ~4 characters per token
    return len(text) // 4


def estimate_cost(input_tokens: int, output_tokens: int, model: str) -> float:
    """
    Estimate API cost based on token counts.
    
    Args:
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
        model: Model name
        
    Returns:
        Estimated cost in USD
    """
    pricing = MODEL_PRICING.get(model, MODEL_PRICING["gpt-4o-mini"])
    input_cost = (input_tokens / 1_000_000) * pricing["input"]
    output_cost = (output_tokens / 1_000_000) * pricing["output"]
    return input_cost + output_cost


def format_cost(cost: float) -> str:
    """Format cost as currency string."""
    if cost < 0.01:
        return f"${cost:.6f}"
    elif cost < 1:
        return f"${cost:.4f}"
    else:
        return f"${cost:.2f}"


# =============================================================================
# File Operations
# =============================================================================

def load_transcript(video_id: str, transcripts_dir: Path) -> Optional[dict]:
    """
    Load transcript JSON file for a video.
    
    Args:
        video_id: YouTube video ID
        transcripts_dir: Directory containing transcript files
        
    Returns:
        Transcript data dict or None if not found
    """
    transcript_file = transcripts_dir / f"{video_id}.json"
    
    if not transcript_file.exists():
        logger.warning(f"Transcript not found: {transcript_file}")
        return None
    
    try:
        with open(transcript_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in {transcript_file}: {e}")
        return None
    except Exception as e:
        logger.error(f"Error loading {transcript_file}: {e}")
        return None


def get_transcript_text(transcript_data: dict) -> str:
    """
    Extract plain text from transcript data.
    
    Args:
        transcript_data: Transcript JSON data
        
    Returns:
        Plain text transcript
    """
    # Check for different transcript formats
    if "text" in transcript_data:
        return transcript_data["text"]
    
    if "transcript" in transcript_data:
        transcript = transcript_data["transcript"]
        if isinstance(transcript, str):
            return transcript
        if isinstance(transcript, list):
            # List of segments with 'text' field
            return " ".join(seg.get("text", "") for seg in transcript)
    
    if "segments" in transcript_data:
        return " ".join(seg.get("text", "") for seg in transcript_data["segments"])
    
    logger.warning("Could not extract text from transcript data")
    return ""


def save_ai_content(ai_content: dict, video_id: str, output_dir: Path) -> Path:
    """
    Save AI content to JSON file.
    
    Args:
        ai_content: Generated AI content
        video_id: YouTube video ID
        output_dir: Output directory
        
    Returns:
        Path to saved file
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"{video_id}_ai_content.json"
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(ai_content, f, indent=2, ensure_ascii=False)
    
    return output_file


def save_report(report: dict, output_dir: Path) -> Path:
    """
    Save batch processing report.
    
    Args:
        report: Report data
        output_dir: Output directory
        
    Returns:
        Path to saved report
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    report_file = output_dir / "ai_content_report.json"
    
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    return report_file


def load_report(report_path: Path) -> Optional[dict]:
    """Load a processing report file."""
    try:
        with open(report_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading report {report_path}: {e}")
        return None


def find_transcript_files(transcripts_dir: Path) -> list[Path]:
    """Find all transcript JSON files in directory."""
    if not transcripts_dir.exists():
        return []
    return sorted(transcripts_dir.glob("*.json"))


def ai_content_exists(video_id: str, output_dir: Path) -> bool:
    """Check if AI content already exists for a video."""
    output_file = output_dir / f"{video_id}_ai_content.json"
    return output_file.exists()


# =============================================================================
# OpenAI API Integration
# =============================================================================

def generate_ai_content(
    transcript_text: str,
    title: str,
    video_id: str,
    model: str = DEFAULT_MODEL,
    api_key: Optional[str] = None
) -> tuple[Optional[dict], dict]:
    """
    Generate AI content from transcript using OpenAI API.
    
    Args:
        transcript_text: Plain text transcript
        title: Sermon title
        video_id: YouTube video ID
        model: OpenAI model to use
        api_key: OpenAI API key (uses env var if not provided)
        
    Returns:
        Tuple of (generated content dict or None, usage stats dict)
    """
    if not HAS_OPENAI:
        logger.error("OpenAI library not installed. Run: pip install openai")
        return None, {"error": "openai not installed"}
    
    api_key = api_key or OPENAI_API_KEY or os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.error("OPENAI_API_KEY not set")
        return None, {"error": "API key not set"}
    
    # Truncate very long transcripts (most models have ~128k context)
    max_chars = 100000  # ~25k tokens, leaving room for prompt and response
    if len(transcript_text) > max_chars:
        logger.warning(f"Truncating transcript from {len(transcript_text)} to {max_chars} chars")
        transcript_text = transcript_text[:max_chars] + "\n\n[Transcript truncated...]"
    
    # Build the prompt
    user_prompt = USER_PROMPT_TEMPLATE.format(
        title=title,
        transcript_text=transcript_text
    )
    
    # Count input tokens
    full_prompt = SYSTEM_PROMPT + user_prompt
    input_tokens = count_tokens(full_prompt, model)
    
    try:
        client = OpenAI(api_key=api_key)
        
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            max_tokens=2000,
            response_format={"type": "json_object"}
        )
        
        # Extract response
        content = response.choices[0].message.content
        
        # Get actual usage
        usage = {
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
            "total_tokens": response.usage.total_tokens
        }
        
        # Parse JSON response
        try:
            ai_content = json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response as JSON: {e}")
            logger.debug(f"Response content: {content[:500]}...")
            return None, {"error": f"JSON parse error: {e}", **usage}
        
        # Add metadata
        ai_content["video_id"] = video_id
        ai_content["title"] = title
        ai_content["generated_at"] = datetime.now().isoformat()
        ai_content["model"] = model
        ai_content["tokens_used"] = usage
        ai_content["estimated_cost_usd"] = estimate_cost(
            usage["prompt_tokens"],
            usage["completion_tokens"],
            model
        )
        
        return ai_content, usage
        
    except Exception as e:
        logger.error(f"OpenAI API error: {e}")
        return None, {"error": str(e)}


def dry_run_estimate(
    transcript_text: str,
    model: str = DEFAULT_MODEL
) -> dict:
    """
    Estimate tokens and cost without making API call.
    
    Args:
        transcript_text: Plain text transcript
        model: Model to estimate for
        
    Returns:
        Estimation dict with tokens and cost
    """
    # Build prompt for estimation
    user_prompt = USER_PROMPT_TEMPLATE.format(
        title="[Sermon Title]",
        transcript_text=transcript_text
    )
    full_prompt = SYSTEM_PROMPT + user_prompt
    
    input_tokens = count_tokens(full_prompt, model)
    
    # Estimate output tokens (typically 600-1000 for this prompt)
    estimated_output = 800
    
    estimated_cost = estimate_cost(input_tokens, estimated_output, model)
    
    return {
        "input_tokens": input_tokens,
        "estimated_output_tokens": estimated_output,
        "estimated_total_tokens": input_tokens + estimated_output,
        "estimated_cost_usd": estimated_cost,
        "model": model
    }


# =============================================================================
# Batch Processing
# =============================================================================

def process_video(
    video_id: str,
    transcripts_dir: Path,
    output_dir: Path,
    model: str = DEFAULT_MODEL,
    force: bool = False,
    dry_run: bool = False,
    api_key: Optional[str] = None
) -> dict:
    """
    Process a single video transcript.
    
    Args:
        video_id: YouTube video ID
        transcripts_dir: Directory containing transcripts
        output_dir: Output directory for AI content
        model: OpenAI model to use
        force: Force regeneration even if exists
        dry_run: Only estimate cost, don't call API
        api_key: OpenAI API key
        
    Returns:
        Result dict with status and details
    """
    result = {
        "video_id": video_id,
        "status": "pending",
        "output_file": None,
        "tokens_used": None,
        "cost_usd": None,
        "error": None
    }
    
    # Check if already exists
    if not force and ai_content_exists(video_id, output_dir):
        result["status"] = "skipped"
        result["output_file"] = str(output_dir / f"{video_id}_ai_content.json")
        return result
    
    # Load transcript
    transcript_data = load_transcript(video_id, transcripts_dir)
    if not transcript_data:
        result["status"] = "failed"
        result["error"] = "Transcript not found"
        return result
    
    # Extract text
    transcript_text = get_transcript_text(transcript_data)
    if not transcript_text:
        result["status"] = "failed"
        result["error"] = "Could not extract transcript text"
        return result
    
    title = transcript_data.get("title", f"Video {video_id}")
    
    # Dry run - just estimate
    if dry_run:
        estimation = dry_run_estimate(transcript_text, model)
        result["status"] = "estimated"
        result["tokens_used"] = {
            "prompt": estimation["input_tokens"],
            "completion": estimation["estimated_output_tokens"],
            "total": estimation["estimated_total_tokens"]
        }
        result["cost_usd"] = estimation["estimated_cost_usd"]
        return result
    
    # Generate AI content
    ai_content, usage = generate_ai_content(
        transcript_text, title, video_id, model, api_key
    )
    
    if ai_content is None:
        result["status"] = "failed"
        result["error"] = usage.get("error", "Unknown error")
        return result
    
    # Save output
    output_file = save_ai_content(ai_content, video_id, output_dir)
    
    result["status"] = "success"
    result["output_file"] = str(output_file)
    result["tokens_used"] = usage
    result["cost_usd"] = ai_content.get("estimated_cost_usd", 0)
    
    return result


def process_batch(
    video_ids: list[str],
    transcripts_dir: Path,
    output_dir: Path,
    model: str = DEFAULT_MODEL,
    force: bool = False,
    dry_run: bool = False,
    api_key: Optional[str] = None,
    quiet: bool = False
) -> dict:
    """
    Process multiple videos.
    
    Args:
        video_ids: List of video IDs to process
        transcripts_dir: Directory containing transcripts
        output_dir: Output directory
        model: OpenAI model to use
        force: Force regeneration
        dry_run: Only estimate costs
        api_key: OpenAI API key
        quiet: Suppress progress output
        
    Returns:
        Batch report dict
    """
    report = {
        "generated_at": datetime.now().isoformat(),
        "model": model,
        "dry_run": dry_run,
        "total_videos": len(video_ids),
        "results": {
            "success": 0,
            "skipped": 0,
            "failed": 0,
            "estimated": 0
        },
        "total_tokens": {
            "prompt": 0,
            "completion": 0,
            "total": 0
        },
        "total_cost_usd": 0.0,
        "videos": []
    }
    
    # Progress iterator
    if HAS_TQDM and not quiet:
        iterator = tqdm(video_ids, desc="Generating AI content")
    else:
        iterator = video_ids
    
    for video_id in iterator:
        result = process_video(
            video_id, transcripts_dir, output_dir,
            model, force, dry_run, api_key
        )
        
        report["results"][result["status"]] = report["results"].get(result["status"], 0) + 1
        report["videos"].append(result)
        
        if result["tokens_used"]:
            tokens = result["tokens_used"]
            report["total_tokens"]["prompt"] += tokens.get("prompt", tokens.get("prompt_tokens", 0))
            report["total_tokens"]["completion"] += tokens.get("completion", tokens.get("completion_tokens", 0))
            report["total_tokens"]["total"] += tokens.get("total", tokens.get("total_tokens", 0))
        
        if result["cost_usd"]:
            report["total_cost_usd"] += result["cost_usd"]
        
        if not quiet and not HAS_TQDM:
            status_symbol = {"success": "✓", "skipped": "○", "failed": "✗", "estimated": "~"}
            print(f"  {status_symbol.get(result['status'], '?')} {video_id}: {result['status']}")
    
    return report


# =============================================================================
# Input Detection
# =============================================================================

def get_video_ids_from_input(args, transcripts_dir: Path) -> list[str]:
    """
    Determine video IDs to process based on CLI arguments.
    
    Args:
        args: Parsed CLI arguments
        transcripts_dir: Transcripts directory
        
    Returns:
        List of video IDs to process
    """
    video_ids = []
    
    # Single video ID
    if args.video_id:
        return [args.video_id]
    
    # Multiple video IDs
    if args.video_ids:
        return [v.strip() for v in args.video_ids.split(",") if v.strip()]
    
    # From report file
    if args.from_report:
        report_path = Path(args.from_report)
        report = load_report(report_path)
        if report:
            # Handle different report formats
            if "videos" in report:
                video_ids = [v["video_id"] for v in report["videos"] if v.get("status") == "success"]
            elif "processed" in report:
                video_ids = [v["video_id"] for v in report["processed"] if v.get("status") == "success"]
        return video_ids
    
    # All transcript files
    if args.all:
        transcript_files = find_transcript_files(transcripts_dir)
        return [f.stem for f in transcript_files if not f.stem.endswith("_report")]
    
    # Auto-detect: check for transcript_report.json
    report_file = transcripts_dir / "transcript_report.json"
    if report_file.exists():
        report = load_report(report_file)
        if report and "videos" in report:
            return [v["video_id"] for v in report["videos"] if v.get("status") == "success"]
    
    # Fallback: all transcript files
    transcript_files = find_transcript_files(transcripts_dir)
    return [f.stem for f in transcript_files if not f.stem.endswith("_report")]


# =============================================================================
# CLI Interface
# =============================================================================

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Generate AI-powered content from sermon transcripts",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --video-id abc123xyz
  %(prog)s --from-report data/transcripts/transcript_report.json
  %(prog)s --all --dry-run
  %(prog)s --video-id abc123 --model gpt-4o --force
  %(prog)s --json
        """
    )
    
    # Input options
    input_group = parser.add_argument_group("Input Options")
    input_group.add_argument(
        "--video-id",
        help="Process single video by ID"
    )
    input_group.add_argument(
        "--video-ids",
        help="Process multiple videos (comma-separated)"
    )
    input_group.add_argument(
        "--from-report",
        help="Process videos from a report file"
    )
    input_group.add_argument(
        "--all",
        action="store_true",
        help="Process all transcript files"
    )
    
    # Processing options
    proc_group = parser.add_argument_group("Processing Options")
    proc_group.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        choices=list(MODEL_PRICING.keys()),
        help=f"OpenAI model to use (default: {DEFAULT_MODEL})"
    )
    proc_group.add_argument(
        "--force",
        action="store_true",
        help="Force regeneration even if output exists"
    )
    proc_group.add_argument(
        "--dry-run",
        action="store_true",
        help="Estimate cost without making API calls"
    )
    
    # Output options
    output_group = parser.add_argument_group("Output Options")
    output_group.add_argument(
        "--json",
        action="store_true",
        help="Output JSON to stdout (single video only)"
    )
    output_group.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress progress output"
    )
    
    # Directory overrides
    dir_group = parser.add_argument_group("Directory Overrides")
    dir_group.add_argument(
        "--transcripts-dir",
        type=Path,
        default=TRANSCRIPTS_DIR,
        help="Transcripts directory"
    )
    dir_group.add_argument(
        "--output-dir",
        type=Path,
        default=AI_CONTENT_DIR,
        help="Output directory for AI content"
    )
    
    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()
    
    # Set up logging
    if args.quiet:
        logging.getLogger().setLevel(logging.WARNING)
    
    # Ensure directories exist
    if HAS_CONFIG:
        try:
            ensure_directories()
        except Exception:
            pass
    args.output_dir.mkdir(parents=True, exist_ok=True)
    
    # Get video IDs to process
    video_ids = get_video_ids_from_input(args, args.transcripts_dir)
    
    if not video_ids:
        if not args.quiet:
            print("No videos to process.")
            print(f"  Transcripts directory: {args.transcripts_dir}")
            print("  Provide --video-id, --from-report, or ensure transcripts exist")
        sys.exit(1)
    
    # Single video with JSON output
    if args.json and len(video_ids) == 1:
        result = process_video(
            video_ids[0],
            args.transcripts_dir,
            args.output_dir,
            args.model,
            args.force,
            args.dry_run
        )
        
        if result["status"] == "success" and result["output_file"]:
            with open(result["output_file"], 'r') as f:
                print(json.dumps(json.load(f), indent=2))
        else:
            print(json.dumps(result, indent=2))
        sys.exit(0 if result["status"] in ("success", "skipped") else 1)
    
    # Batch processing
    if not args.quiet:
        mode = "DRY RUN" if args.dry_run else "Processing"
        print(f"\n{mode}: {len(video_ids)} video(s) with {args.model}")
        print(f"  Transcripts: {args.transcripts_dir}")
        print(f"  Output: {args.output_dir}")
        print()
    
    report = process_batch(
        video_ids,
        args.transcripts_dir,
        args.output_dir,
        args.model,
        args.force,
        args.dry_run,
        quiet=args.quiet
    )
    
    # Save report
    report_file = save_report(report, args.output_dir)
    
    # Print summary
    if not args.quiet:
        print(f"\n{'='*60}")
        print("SUMMARY")
        print(f"{'='*60}")
        
        results = report["results"]
        print(f"  Success:   {results.get('success', 0)}")
        print(f"  Skipped:   {results.get('skipped', 0)}")
        print(f"  Failed:    {results.get('failed', 0)}")
        if args.dry_run:
            print(f"  Estimated: {results.get('estimated', 0)}")
        
        print(f"\nTokens Used:")
        tokens = report["total_tokens"]
        print(f"  Prompt:     {tokens['prompt']:,}")
        print(f"  Completion: {tokens['completion']:,}")
        print(f"  Total:      {tokens['total']:,}")
        
        cost = report["total_cost_usd"]
        print(f"\n{'Estimated' if args.dry_run else 'Total'} Cost: {format_cost(cost)}")
        
        print(f"\nReport saved: {report_file}")
    
    # Exit code based on results
    if report["results"].get("failed", 0) > 0:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
