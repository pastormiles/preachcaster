#!/usr/bin/env python3
"""
05_generate_embeddings_v1.py
Generate OpenAI embeddings from transcript chunks for semantic search.

================================================================================
OVERVIEW
================================================================================
This script generates vector embeddings from transcript chunks using OpenAI's
embedding API. These embeddings capture semantic meaning, enabling similarity
search across sermon content.

Part of the PreachCaster pipeline:
  01_monitor_youtube     -> Detect new videos
  02_extract_audio       -> Download MP3
  03_fetch_transcript    -> Get captions
  04_chunk_transcript    -> Split for search
  05_generate_embeddings -> THIS SCRIPT (Create vectors)
  06_upload_pinecone     -> Store in vector DB

================================================================================
FEATURES
================================================================================
- Generate embeddings via OpenAI API (text-embedding-3-small by default)
- Batch API calls for efficiency (respects rate limits)
- Track token usage and estimate costs
- Support incremental processing (skip existing files)
- Dry-run mode for cost estimation without API calls
- Accurate token counting with tiktoken (falls back to estimation)

================================================================================
REQUIREMENTS
================================================================================
- Python 3.8+
- openai>=1.0.0
- tiktoken>=0.5.0 (optional, for accurate token counting)
- Valid OPENAI_API_KEY in environment or .env file

================================================================================
INPUT
================================================================================
Chunk JSON files from script 04, containing:
{
  "video_id": "abc123xyz",
  "title": "Sermon Title",
  "chunks": [
    {
      "chunk_id": "abc123xyz_chunk_000",
      "text": "Good morning everyone...",
      "start_time": 0.0,
      "end_time": 120.0,
      ...
    }
  ]
}

================================================================================
OUTPUT
================================================================================
Embedding JSON files in data/embeddings/:
{
  "video_id": "abc123xyz",
  "title": "Sermon Title",
  "model": "text-embedding-3-small",
  "dimensions": 1536,
  "total_chunks": 24,
  "total_tokens": 12500,
  "estimated_cost_usd": 0.00025,
  "chunks": [
    {
      "chunk_id": "abc123xyz_chunk_000",
      "text": "Good morning everyone...",
      "embedding": [0.0123, -0.0456, ...],
      ...
    }
  ]
}

================================================================================
USAGE EXAMPLES
================================================================================
# Generate embeddings for single video
python 05_generate_embeddings_v1.py --video-id abc123xyz

# Generate from chunk report (batch mode)
python 05_generate_embeddings_v1.py --from-report data/chunks/chunk_report.json

# Process all chunk files in directory
python 05_generate_embeddings_v1.py --all

# Auto-detect input (looks for chunk_report.json or chunks directory)
python 05_generate_embeddings_v1.py

# Custom batch size for API calls
python 05_generate_embeddings_v1.py --video-id abc123 --batch-size 50

# Force re-generate existing embeddings
python 05_generate_embeddings_v1.py --video-id abc123 --force

# Dry run - estimate cost without calling API
python 05_generate_embeddings_v1.py --all --dry-run

# Output JSON to stdout (single video)
python 05_generate_embeddings_v1.py --video-id abc123 --json

# Quiet mode (minimal output)
python 05_generate_embeddings_v1.py --all --quiet

================================================================================
OPENAI EMBEDDING MODELS
================================================================================
Model                    | Dimensions | Price per 1M tokens
-------------------------|------------|--------------------
text-embedding-3-small   | 1536       | $0.02
text-embedding-3-large   | 3072       | $0.13
text-embedding-ada-002   | 1536       | $0.10

Default: text-embedding-3-small (best price/performance ratio)

================================================================================
COST ESTIMATES
================================================================================
Typical 45-minute sermon:
- ~7,500 words → ~9,000 tokens
- ~23 chunks (2 min each)
- Embedding cost: ~$0.0002

100 sermons (2 years weekly):
- Total cost: ~$0.02

================================================================================
CONFIGURATION
================================================================================
Uses config/config.py for:
- CHUNKS_DIR: Input directory for chunk files
- EMBEDDINGS_DIR: Output directory for embedding files
- OPENAI_API_KEY: API authentication
- EMBEDDING_MODEL: Model name (default: text-embedding-3-small)
- EMBEDDING_BATCH_SIZE: Texts per API call (default: 100)

Can run without config using CLI overrides for testing.

================================================================================
VERSION HISTORY
================================================================================
v1.0 - 2024-12-31 - Initial version for PreachCaster
  - OpenAI embedding generation with batching
  - Token counting and cost estimation
  - Incremental processing support
  - Comprehensive CLI interface

================================================================================
"""

import os
import sys
import json
import argparse
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Any, Tuple

# Optional: accurate token counting
try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False

# Try to import OpenAI
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

# Try to import config
try:
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from config.config import (
        CHUNKS_DIR,
        EMBEDDINGS_DIR,
        OPENAI_API_KEY,
        EMBEDDING_MODEL,
        EMBEDDING_DIMENSIONS,
        EMBEDDING_BATCH_SIZE,
        ensure_directories,
    )
    CONFIG_AVAILABLE = True
except ImportError:
    CONFIG_AVAILABLE = False
    # Defaults when config not available
    CHUNKS_DIR = Path("data/chunks")
    EMBEDDINGS_DIR = Path("data/embeddings")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    EMBEDDING_MODEL = "text-embedding-3-small"
    EMBEDDING_DIMENSIONS = 1536
    EMBEDDING_BATCH_SIZE = 100

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# ============================================================================
# CONSTANTS
# ============================================================================

# Pricing per 1M tokens (as of Dec 2024)
MODEL_PRICING = {
    "text-embedding-3-small": 0.02,
    "text-embedding-3-large": 0.13,
    "text-embedding-ada-002": 0.10,
}

MODEL_DIMENSIONS = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
}

# Rate limiting
MAX_BATCH_SIZE = 2048  # OpenAI limit
DEFAULT_BATCH_SIZE = 100  # Conservative default
CHARS_PER_TOKEN_ESTIMATE = 4  # For fallback estimation


# ============================================================================
# TOKEN COUNTING
# ============================================================================

def get_token_encoder(model: str):
    """Get tiktoken encoder for the embedding model."""
    if not TIKTOKEN_AVAILABLE:
        return None
    
    try:
        # Embedding models use cl100k_base encoding
        return tiktoken.get_encoding("cl100k_base")
    except Exception as e:
        logger.warning(f"Could not load tiktoken encoder: {e}")
        return None


def count_tokens(text: str, encoder=None) -> int:
    """
    Count tokens in text.
    
    Uses tiktoken if available, otherwise estimates from character count.
    
    Args:
        text: Text to count tokens for
        encoder: Optional tiktoken encoder
        
    Returns:
        Token count (exact if tiktoken available, estimated otherwise)
    """
    if encoder is not None:
        try:
            return len(encoder.encode(text))
        except Exception:
            pass
    
    # Fallback: estimate from character count
    return len(text) // CHARS_PER_TOKEN_ESTIMATE


def count_tokens_batch(texts: List[str], encoder=None) -> List[int]:
    """Count tokens for a batch of texts."""
    return [count_tokens(text, encoder) for text in texts]


# ============================================================================
# COST ESTIMATION
# ============================================================================

def estimate_cost(total_tokens: int, model: str) -> float:
    """
    Estimate cost for embedding generation.
    
    Args:
        total_tokens: Total number of tokens to embed
        model: Embedding model name
        
    Returns:
        Estimated cost in USD
    """
    price_per_million = MODEL_PRICING.get(model, 0.02)
    return (total_tokens / 1_000_000) * price_per_million


def format_cost(cost: float) -> str:
    """Format cost for display."""
    if cost < 0.01:
        return f"${cost:.6f}"
    elif cost < 1.0:
        return f"${cost:.4f}"
    else:
        return f"${cost:.2f}"


# ============================================================================
# FILE OPERATIONS
# ============================================================================

def load_chunk_file(file_path: Path) -> Optional[Dict[str, Any]]:
    """
    Load a chunk JSON file.
    
    Args:
        file_path: Path to chunk JSON file
        
    Returns:
        Chunk data dict or None if error
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading {file_path}: {e}")
        return None


def save_embedding_file(data: Dict[str, Any], output_path: Path) -> bool:
    """
    Save embedding data to JSON file.
    
    Args:
        data: Embedding data dict
        output_path: Path to save to
        
    Returns:
        True if successful
    """
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"Error saving {output_path}: {e}")
        return False


def load_chunk_report(report_path: Path) -> Optional[Dict[str, Any]]:
    """Load chunk processing report."""
    try:
        with open(report_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading report {report_path}: {e}")
        return None


def find_chunk_files(chunks_dir: Path) -> List[Path]:
    """Find all chunk JSON files in directory."""
    if not chunks_dir.exists():
        return []
    return sorted(chunks_dir.glob("*_chunks.json"))


def get_output_path(video_id: str, embeddings_dir: Path) -> Path:
    """Get output path for embedding file."""
    return embeddings_dir / f"{video_id}_embeddings.json"


# ============================================================================
# EMBEDDING GENERATION
# ============================================================================

def create_openai_client(api_key: Optional[str] = None) -> Optional['OpenAI']:
    """
    Create OpenAI client.
    
    Args:
        api_key: API key (uses env var if not provided)
        
    Returns:
        OpenAI client or None if unavailable
    """
    if not OPENAI_AVAILABLE:
        logger.error("OpenAI library not installed. Run: pip install openai")
        return None
    
    key = api_key or OPENAI_API_KEY or os.getenv("OPENAI_API_KEY")
    if not key:
        logger.error("OPENAI_API_KEY not found in environment")
        return None
    
    return OpenAI(api_key=key)


def generate_embeddings_batch(
    client: 'OpenAI',
    texts: List[str],
    model: str = EMBEDDING_MODEL
) -> Tuple[List[List[float]], int]:
    """
    Generate embeddings for a batch of texts.
    
    Args:
        client: OpenAI client
        texts: List of texts to embed
        model: Embedding model name
        
    Returns:
        Tuple of (embeddings list, total tokens used)
    """
    try:
        response = client.embeddings.create(
            model=model,
            input=texts
        )
        
        # Extract embeddings in order
        embeddings = [item.embedding for item in response.data]
        total_tokens = response.usage.total_tokens
        
        return embeddings, total_tokens
        
    except Exception as e:
        logger.error(f"Error generating embeddings: {e}")
        raise


def generate_embeddings_for_chunks(
    chunks: List[Dict[str, Any]],
    client: 'OpenAI',
    model: str = EMBEDDING_MODEL,
    batch_size: int = DEFAULT_BATCH_SIZE,
    quiet: bool = False
) -> Tuple[List[Dict[str, Any]], int]:
    """
    Generate embeddings for all chunks.
    
    Args:
        chunks: List of chunk dicts with 'text' field
        client: OpenAI client
        model: Embedding model name
        batch_size: Number of texts per API call
        quiet: Suppress progress output
        
    Returns:
        Tuple of (chunks with embeddings, total tokens used)
    """
    total_tokens = 0
    enriched_chunks = []
    
    # Process in batches
    num_batches = (len(chunks) + batch_size - 1) // batch_size
    
    for i in range(0, len(chunks), batch_size):
        batch_chunks = chunks[i:i + batch_size]
        batch_texts = [chunk['text'] for chunk in batch_chunks]
        batch_num = (i // batch_size) + 1
        
        if not quiet:
            logger.info(f"Processing batch {batch_num}/{num_batches} ({len(batch_texts)} chunks)")
        
        try:
            embeddings, tokens = generate_embeddings_batch(client, batch_texts, model)
            total_tokens += tokens
            
            # Add embeddings to chunks
            for chunk, embedding in zip(batch_chunks, embeddings):
                enriched_chunk = chunk.copy()
                enriched_chunk['embedding'] = embedding
                enriched_chunks.append(enriched_chunk)
                
        except Exception as e:
            logger.error(f"Batch {batch_num} failed: {e}")
            # Add chunks without embeddings (marked as failed)
            for chunk in batch_chunks:
                enriched_chunk = chunk.copy()
                enriched_chunk['embedding'] = None
                enriched_chunk['error'] = str(e)
                enriched_chunks.append(enriched_chunk)
    
    return enriched_chunks, total_tokens


# ============================================================================
# PROCESSING
# ============================================================================

def process_video(
    video_id: str,
    chunks_dir: Path,
    embeddings_dir: Path,
    client: Optional['OpenAI'] = None,
    model: str = EMBEDDING_MODEL,
    batch_size: int = DEFAULT_BATCH_SIZE,
    force: bool = False,
    dry_run: bool = False,
    quiet: bool = False
) -> Dict[str, Any]:
    """
    Process a single video - generate embeddings for its chunks.
    
    Args:
        video_id: YouTube video ID
        chunks_dir: Directory containing chunk files
        embeddings_dir: Directory to save embedding files
        client: OpenAI client (None for dry run)
        model: Embedding model name
        batch_size: API batch size
        force: Overwrite existing files
        dry_run: Estimate cost without generating
        quiet: Suppress progress output
        
    Returns:
        Result dict with status and statistics
    """
    result = {
        "video_id": video_id,
        "status": "pending",
        "chunks": 0,
        "tokens": 0,
        "estimated_cost": 0.0,
        "output_file": None,
        "error": None
    }
    
    # Find chunk file
    chunk_file = chunks_dir / f"{video_id}_chunks.json"
    if not chunk_file.exists():
        result["status"] = "error"
        result["error"] = f"Chunk file not found: {chunk_file}"
        return result
    
    # Check if output exists
    output_path = get_output_path(video_id, embeddings_dir)
    if output_path.exists() and not force:
        result["status"] = "skipped"
        result["error"] = "Output file exists (use --force to overwrite)"
        return result
    
    # Load chunks
    chunk_data = load_chunk_file(chunk_file)
    if not chunk_data:
        result["status"] = "error"
        result["error"] = "Failed to load chunk file"
        return result
    
    chunks = chunk_data.get("chunks", [])
    if not chunks:
        result["status"] = "error"
        result["error"] = "No chunks found in file"
        return result
    
    result["chunks"] = len(chunks)
    
    # Count tokens
    encoder = get_token_encoder(model)
    texts = [chunk['text'] for chunk in chunks]
    token_counts = count_tokens_batch(texts, encoder)
    total_tokens = sum(token_counts)
    
    result["tokens"] = total_tokens
    result["estimated_cost"] = estimate_cost(total_tokens, model)
    
    # Add token counts to chunks
    for chunk, tokens in zip(chunks, token_counts):
        chunk['token_count'] = tokens
    
    if not quiet:
        logger.info(f"Video {video_id}: {len(chunks)} chunks, ~{total_tokens:,} tokens, "
                   f"est. cost: {format_cost(result['estimated_cost'])}")
    
    # Dry run - stop here
    if dry_run:
        result["status"] = "dry_run"
        return result
    
    # Generate embeddings
    if client is None:
        result["status"] = "error"
        result["error"] = "OpenAI client not available"
        return result
    
    try:
        enriched_chunks, actual_tokens = generate_embeddings_for_chunks(
            chunks, client, model, batch_size, quiet
        )
        
        # Build output data
        output_data = {
            "video_id": video_id,
            "title": chunk_data.get("title", "Unknown"),
            "generated_at": datetime.now().isoformat(),
            "model": model,
            "dimensions": MODEL_DIMENSIONS.get(model, 1536),
            "total_chunks": len(enriched_chunks),
            "total_tokens": actual_tokens,
            "estimated_cost_usd": estimate_cost(actual_tokens, model),
            "source_file": str(chunk_file),
            "chunks": enriched_chunks
        }
        
        # Save output
        if save_embedding_file(output_data, output_path):
            result["status"] = "success"
            result["tokens"] = actual_tokens
            result["estimated_cost"] = output_data["estimated_cost_usd"]
            result["output_file"] = str(output_path)
        else:
            result["status"] = "error"
            result["error"] = "Failed to save output file"
            
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
    
    return result


def process_batch(
    video_ids: List[str],
    chunks_dir: Path,
    embeddings_dir: Path,
    client: Optional['OpenAI'] = None,
    model: str = EMBEDDING_MODEL,
    batch_size: int = DEFAULT_BATCH_SIZE,
    force: bool = False,
    dry_run: bool = False,
    quiet: bool = False
) -> Dict[str, Any]:
    """
    Process multiple videos.
    
    Returns:
        Batch report dict
    """
    results = []
    total_chunks = 0
    total_tokens = 0
    total_cost = 0.0
    success_count = 0
    
    for i, video_id in enumerate(video_ids, 1):
        if not quiet:
            logger.info(f"\n[{i}/{len(video_ids)}] Processing {video_id}")
        
        result = process_video(
            video_id, chunks_dir, embeddings_dir,
            client, model, batch_size, force, dry_run, quiet
        )
        results.append(result)
        
        total_chunks += result.get("chunks", 0)
        total_tokens += result.get("tokens", 0)
        total_cost += result.get("estimated_cost", 0)
        
        if result["status"] == "success":
            success_count += 1
    
    report = {
        "generated_at": datetime.now().isoformat(),
        "model": model,
        "dry_run": dry_run,
        "total_videos": len(video_ids),
        "successful": success_count,
        "skipped": sum(1 for r in results if r["status"] == "skipped"),
        "failed": sum(1 for r in results if r["status"] == "error"),
        "total_chunks": total_chunks,
        "total_tokens": total_tokens,
        "total_cost_usd": total_cost,
        "results": results
    }
    
    return report


# ============================================================================
# INPUT DETECTION
# ============================================================================

def get_video_ids_from_report(report_path: Path) -> List[str]:
    """Extract video IDs from chunk report."""
    report = load_chunk_report(report_path)
    if not report:
        return []
    
    results = report.get("results", report.get("videos", []))
    return [r.get("video_id") for r in results if r.get("video_id") and r.get("status") == "success"]


def get_video_ids_from_directory(chunks_dir: Path) -> List[str]:
    """Get video IDs from chunk files in directory."""
    files = find_chunk_files(chunks_dir)
    video_ids = []
    for f in files:
        # Extract video_id from filename: {video_id}_chunks.json
        video_id = f.stem.replace("_chunks", "")
        video_ids.append(video_id)
    return video_ids


def auto_detect_input(chunks_dir: Path) -> Tuple[str, List[str]]:
    """
    Auto-detect input source.
    
    Returns:
        Tuple of (source description, list of video IDs)
    """
    # Check for chunk_report.json
    report_path = chunks_dir / "chunk_report.json"
    if report_path.exists():
        video_ids = get_video_ids_from_report(report_path)
        if video_ids:
            return f"chunk_report.json ({len(video_ids)} videos)", video_ids
    
    # Check for chunk files in directory
    video_ids = get_video_ids_from_directory(chunks_dir)
    if video_ids:
        return f"chunks directory ({len(video_ids)} files)", video_ids
    
    return "no input found", []


# ============================================================================
# CLI
# ============================================================================

def create_parser() -> argparse.ArgumentParser:
    """Create argument parser."""
    parser = argparse.ArgumentParser(
        description="Generate OpenAI embeddings from transcript chunks",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --video-id abc123xyz            # Single video
  %(prog)s --from-report chunk_report.json # From report
  %(prog)s --all                           # All chunk files
  %(prog)s                                 # Auto-detect
  %(prog)s --all --dry-run                 # Estimate cost
  %(prog)s --video-id abc123 --json        # JSON output
        """
    )
    
    # Input options
    input_group = parser.add_argument_group("Input Options")
    input_group.add_argument(
        "--video-id", "-v",
        help="Process single video by ID"
    )
    input_group.add_argument(
        "--video-ids",
        help="Process multiple videos (comma-separated)"
    )
    input_group.add_argument(
        "--from-report", "-r",
        type=Path,
        help="Process videos from chunk report JSON"
    )
    input_group.add_argument(
        "--all", "-a",
        action="store_true",
        help="Process all chunk files in directory"
    )
    
    # Processing options
    proc_group = parser.add_argument_group("Processing Options")
    proc_group.add_argument(
        "--model", "-m",
        default=EMBEDDING_MODEL,
        choices=list(MODEL_PRICING.keys()),
        help=f"Embedding model (default: {EMBEDDING_MODEL})"
    )
    proc_group.add_argument(
        "--batch-size", "-b",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=f"Texts per API call (default: {DEFAULT_BATCH_SIZE}, max: {MAX_BATCH_SIZE})"
    )
    proc_group.add_argument(
        "--force", "-f",
        action="store_true",
        help="Overwrite existing embedding files"
    )
    proc_group.add_argument(
        "--dry-run", "-d",
        action="store_true",
        help="Estimate cost without generating embeddings"
    )
    
    # Path options
    path_group = parser.add_argument_group("Path Options")
    path_group.add_argument(
        "--chunks-dir",
        type=Path,
        default=CHUNKS_DIR,
        help=f"Input chunks directory (default: {CHUNKS_DIR})"
    )
    path_group.add_argument(
        "--embeddings-dir",
        type=Path,
        default=EMBEDDINGS_DIR,
        help=f"Output embeddings directory (default: {EMBEDDINGS_DIR})"
    )
    
    # Output options
    output_group = parser.add_argument_group("Output Options")
    output_group.add_argument(
        "--json", "-j",
        action="store_true",
        help="Output results as JSON to stdout"
    )
    output_group.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Minimal output (errors only)"
    )
    output_group.add_argument(
        "--save-report",
        type=Path,
        help="Save batch report to file"
    )
    
    return parser


def main():
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()
    
    # Set logging level
    if args.quiet:
        logging.getLogger().setLevel(logging.ERROR)
    
    # Validate batch size
    if args.batch_size > MAX_BATCH_SIZE:
        logger.warning(f"Batch size {args.batch_size} exceeds max {MAX_BATCH_SIZE}, using max")
        args.batch_size = MAX_BATCH_SIZE
    
    # Ensure directories exist
    args.chunks_dir.mkdir(parents=True, exist_ok=True)
    args.embeddings_dir.mkdir(parents=True, exist_ok=True)
    
    # Determine video IDs to process
    video_ids = []
    source = None
    
    if args.video_id:
        video_ids = [args.video_id]
        source = "command line (single)"
    elif args.video_ids:
        video_ids = [v.strip() for v in args.video_ids.split(",")]
        source = f"command line ({len(video_ids)} videos)"
    elif args.from_report:
        video_ids = get_video_ids_from_report(args.from_report)
        source = f"report: {args.from_report}"
    elif args.all:
        video_ids = get_video_ids_from_directory(args.chunks_dir)
        source = f"all files in {args.chunks_dir}"
    else:
        source, video_ids = auto_detect_input(args.chunks_dir)
    
    if not video_ids:
        if args.json:
            print(json.dumps({"error": "No videos to process", "source": source}))
        else:
            logger.error(f"No videos to process. Source: {source}")
            logger.info("Use --video-id, --from-report, or --all to specify input")
        sys.exit(1)
    
    if not args.quiet:
        logger.info(f"Input: {source}")
        logger.info(f"Videos to process: {len(video_ids)}")
        logger.info(f"Model: {args.model}")
        if args.dry_run:
            logger.info("DRY RUN - no embeddings will be generated")
    
    # Create OpenAI client (unless dry run)
    client = None
    if not args.dry_run:
        client = create_openai_client()
        if client is None and not args.dry_run:
            if args.json:
                print(json.dumps({"error": "OpenAI client not available"}))
            sys.exit(1)
    
    # Process videos
    if len(video_ids) == 1 and not args.save_report:
        # Single video mode
        result = process_video(
            video_ids[0],
            args.chunks_dir,
            args.embeddings_dir,
            client,
            args.model,
            args.batch_size,
            args.force,
            args.dry_run,
            args.quiet
        )
        
        if args.json:
            print(json.dumps(result, indent=2))
        elif not args.quiet:
            if result["status"] == "success":
                logger.info(f"\n✓ Generated embeddings: {result['output_file']}")
                logger.info(f"  Chunks: {result['chunks']}, Tokens: {result['tokens']:,}")
                logger.info(f"  Cost: {format_cost(result['estimated_cost'])}")
            elif result["status"] == "dry_run":
                logger.info(f"\n✓ Dry run complete")
                logger.info(f"  Chunks: {result['chunks']}, Tokens: {result['tokens']:,}")
                logger.info(f"  Estimated cost: {format_cost(result['estimated_cost'])}")
            elif result["status"] == "skipped":
                logger.info(f"\n⊘ Skipped: {result['error']}")
            else:
                logger.error(f"\n✗ Failed: {result['error']}")
        
        sys.exit(0 if result["status"] in ("success", "dry_run", "skipped") else 1)
    
    else:
        # Batch mode
        report = process_batch(
            video_ids,
            args.chunks_dir,
            args.embeddings_dir,
            client,
            args.model,
            args.batch_size,
            args.force,
            args.dry_run,
            args.quiet
        )
        
        # Save report
        report_path = args.save_report or args.embeddings_dir / "embedding_report.json"
        save_embedding_file(report, report_path)
        
        if args.json:
            print(json.dumps(report, indent=2))
        elif not args.quiet:
            print("\n" + "=" * 60)
            print("EMBEDDING GENERATION REPORT")
            print("=" * 60)
            print(f"Model:      {args.model}")
            print(f"Dry run:    {args.dry_run}")
            print(f"Videos:     {report['total_videos']}")
            print(f"Successful: {report['successful']}")
            print(f"Skipped:    {report['skipped']}")
            print(f"Failed:     {report['failed']}")
            print("-" * 60)
            print(f"Total chunks:  {report['total_chunks']:,}")
            print(f"Total tokens:  {report['total_tokens']:,}")
            print(f"Total cost:    {format_cost(report['total_cost_usd'])}")
            print("-" * 60)
            print(f"Report saved: {report_path}")
        
        sys.exit(0 if report['failed'] == 0 else 1)


if __name__ == "__main__":
    main()
