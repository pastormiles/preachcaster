#!/usr/bin/env python3
"""
06_upload_pinecone_v1.py
Upload embeddings to Pinecone vector database for semantic search.

================================================================================
OVERVIEW
================================================================================
This script uploads vector embeddings to Pinecone, enabling semantic search
across sermon content. Each church gets its own namespace for data isolation.

Part of the PreachCaster pipeline:
  01_monitor_youtube     -> Detect new videos
  02_extract_audio       -> Download MP3
  03_fetch_transcript    -> Get captions
  04_chunk_transcript    -> Split for search
  05_generate_embeddings -> Create vectors
  06_upload_pinecone     -> THIS SCRIPT (Store in vector DB)

================================================================================
FEATURES
================================================================================
- Upload embeddings to Pinecone with metadata
- Namespace isolation for multi-tenant support
- Batch upsert with progress tracking
- Metadata truncation to respect Pinecone limits
- Test query verification after upload
- Dry-run mode for validation without uploading
- Delete-and-replace for re-indexing videos

================================================================================
REQUIREMENTS
================================================================================
- Python 3.8+
- pinecone>=5.0.0
- Valid PINECONE_API_KEY in environment or .env file
- Existing Pinecone index with matching dimensions

================================================================================
INPUT
================================================================================
Embedding JSON files from script 05, containing:
{
  "video_id": "abc123xyz",
  "title": "Sermon Title",
  "model": "text-embedding-3-small",
  "dimensions": 1536,
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
OUTPUT
================================================================================
- Vectors uploaded to Pinecone index
- Upload report JSON with statistics
- Optional test query results

================================================================================
USAGE EXAMPLES
================================================================================
# Upload single video embeddings
python 06_upload_pinecone_v1.py --video-id abc123xyz

# Upload from embedding report (batch mode)
python 06_upload_pinecone_v1.py --from-report data/embeddings/embedding_report.json

# Upload all embedding files in directory
python 06_upload_pinecone_v1.py --all

# Auto-detect input
python 06_upload_pinecone_v1.py

# Specify namespace (override config)
python 06_upload_pinecone_v1.py --video-id abc123 --namespace crossconnection

# Delete before upload (replace existing)
python 06_upload_pinecone_v1.py --video-id abc123 --replace

# Test query after upload
python 06_upload_pinecone_v1.py --video-id abc123 --test-query "finding peace"

# Dry run - validate without uploading
python 06_upload_pinecone_v1.py --all --dry-run

# Quiet mode
python 06_upload_pinecone_v1.py --all --quiet

================================================================================
PINECONE CONFIGURATION
================================================================================
Index Requirements:
- Metric: cosine (recommended for semantic search)
- Dimensions: 1536 (for text-embedding-3-small)
- Pod type: Starter (free) or p1/s1 for production

Namespaces:
- Each church gets own namespace: "crossconnection", "firstbaptist", etc.
- Enables multi-tenant architecture
- Easy to delete/reset per church

================================================================================
METADATA LIMITS
================================================================================
Pinecone metadata limits:
- 40KB per vector total metadata
- Text truncated to 500 characters for preview in search results

Stored metadata:
- video_id, title, chunk_index
- start_time, end_time, timestamp_formatted
- youtube_url
- text (truncated)
- word_count

================================================================================
CONFIGURATION
================================================================================
Uses config/config.py for:
- EMBEDDINGS_DIR: Input directory for embedding files
- PINECONE_API_KEY: API authentication
- PINECONE_INDEX: Index name
- PINECONE_NAMESPACE: Namespace (usually church slug)
- PINECONE_BATCH_SIZE: Vectors per upsert (default: 100)

Can run without config using CLI overrides.

================================================================================
VERSION HISTORY
================================================================================
v1.0 - 2024-12-31 - Initial version for PreachCaster
  - Pinecone upload with namespace isolation
  - Batch upsert with progress tracking
  - Metadata truncation and test queries
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

# Try to import Pinecone
try:
    from pinecone import Pinecone
    PINECONE_AVAILABLE = True
except ImportError:
    PINECONE_AVAILABLE = False

# Try to import OpenAI for test queries
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

# Try to import config
try:
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from config.config import (
        EMBEDDINGS_DIR,
        PINECONE_API_KEY,
        PINECONE_INDEX,
        PINECONE_NAMESPACE,
        PINECONE_BATCH_SIZE,
        OPENAI_API_KEY,
        EMBEDDING_MODEL,
        ensure_directories,
    )
    CONFIG_AVAILABLE = True
except ImportError:
    CONFIG_AVAILABLE = False
    # Defaults when config not available
    EMBEDDINGS_DIR = Path("data/embeddings")
    PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
    PINECONE_INDEX = os.getenv("PINECONE_INDEX", "sermons")
    PINECONE_NAMESPACE = os.getenv("PINECONE_NAMESPACE", "default")
    PINECONE_BATCH_SIZE = 100
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    EMBEDDING_MODEL = "text-embedding-3-small"

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

# Pinecone limits
MAX_BATCH_SIZE = 1000  # Pinecone limit per upsert
DEFAULT_BATCH_SIZE = 100  # Conservative default
MAX_METADATA_SIZE = 40960  # 40KB per vector
TEXT_TRUNCATE_LENGTH = 500  # Characters for preview

# Default embedding dimensions
DEFAULT_DIMENSIONS = 1536


# ============================================================================
# FILE OPERATIONS
# ============================================================================

def load_embedding_file(file_path: Path) -> Optional[Dict[str, Any]]:
    """
    Load an embedding JSON file.
    
    Args:
        file_path: Path to embedding JSON file
        
    Returns:
        Embedding data dict or None if error
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading {file_path}: {e}")
        return None


def save_report(data: Dict[str, Any], output_path: Path) -> bool:
    """Save report to JSON file."""
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"Error saving {output_path}: {e}")
        return False


def load_embedding_report(report_path: Path) -> Optional[Dict[str, Any]]:
    """Load embedding processing report."""
    try:
        with open(report_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading report {report_path}: {e}")
        return None


def find_embedding_files(embeddings_dir: Path) -> List[Path]:
    """Find all embedding JSON files in directory."""
    if not embeddings_dir.exists():
        return []
    return sorted(embeddings_dir.glob("*_embeddings.json"))


def get_embedding_path(video_id: str, embeddings_dir: Path) -> Path:
    """Get path to embedding file for a video."""
    return embeddings_dir / f"{video_id}_embeddings.json"


# ============================================================================
# METADATA HANDLING
# ============================================================================

def truncate_text(text: str, max_length: int = TEXT_TRUNCATE_LENGTH) -> str:
    """
    Truncate text for metadata storage.
    
    Args:
        text: Text to truncate
        max_length: Maximum length
        
    Returns:
        Truncated text with ellipsis if needed
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."


def prepare_vector_metadata(chunk: Dict[str, Any], title: str) -> Dict[str, Any]:
    """
    Prepare metadata dict for Pinecone vector.
    
    Truncates text and ensures all values are Pinecone-compatible.
    
    Args:
        chunk: Chunk data with text, timestamps, etc.
        title: Video/episode title
        
    Returns:
        Metadata dict for Pinecone
    """
    # Build metadata, handling None values safely
    metadata = {}
    
    # String fields
    metadata["video_id"] = chunk.get("video_id") or ""
    metadata["title"] = (title[:200] if title else "")
    metadata["timestamp_formatted"] = chunk.get("timestamp_formatted") or "0:00"
    metadata["youtube_url"] = chunk.get("youtube_url") or ""
    metadata["text"] = truncate_text(chunk.get("text") or "")
    
    # Numeric fields - only add if not None
    chunk_index = chunk.get("chunk_index")
    if chunk_index is not None:
        metadata["chunk_index"] = int(chunk_index)
    else:
        metadata["chunk_index"] = 0
    
    start_time = chunk.get("start_time")
    if start_time is not None:
        metadata["start_time"] = float(start_time)
    
    end_time = chunk.get("end_time")
    if end_time is not None:
        metadata["end_time"] = float(end_time)
    
    word_count = chunk.get("word_count")
    if word_count is not None:
        metadata["word_count"] = int(word_count)
    
    # Remove any empty string values (but keep 0s)
    return {k: v for k, v in metadata.items() if v is not None and v != ""}


def prepare_vectors(
    embedding_data: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Prepare vectors for Pinecone upsert.
    
    Args:
        embedding_data: Full embedding data from script 05
        
    Returns:
        List of vector dicts with id, values, metadata
    """
    vectors = []
    title = embedding_data.get("title", "")
    video_id = embedding_data.get("video_id", "")
    
    for chunk in embedding_data.get("chunks", []):
        embedding = chunk.get("embedding")
        if embedding is None:
            continue  # Skip chunks without embeddings
        
        # Add video_id to chunk for metadata
        chunk_with_video = {**chunk, "video_id": video_id}
        
        vector = {
            "id": chunk.get("chunk_id", f"{video_id}_chunk_{chunk.get('chunk_index', 0):03d}"),
            "values": embedding,
            "metadata": prepare_vector_metadata(chunk_with_video, title)
        }
        vectors.append(vector)
    
    return vectors


# ============================================================================
# PINECONE OPERATIONS
# ============================================================================

def create_pinecone_client(api_key: Optional[str] = None) -> Optional['Pinecone']:
    """
    Create Pinecone client.
    
    Args:
        api_key: API key (uses env var if not provided)
        
    Returns:
        Pinecone client or None if unavailable
    """
    if not PINECONE_AVAILABLE:
        logger.error("Pinecone library not installed. Run: pip install pinecone")
        return None
    
    key = api_key or PINECONE_API_KEY or os.getenv("PINECONE_API_KEY")
    if not key:
        logger.error("PINECONE_API_KEY not found in environment")
        return None
    
    try:
        return Pinecone(api_key=key)
    except Exception as e:
        logger.error(f"Error creating Pinecone client: {e}")
        return None


def get_index(client: 'Pinecone', index_name: str):
    """
    Get Pinecone index.
    
    Args:
        client: Pinecone client
        index_name: Name of index
        
    Returns:
        Index object or None if not found
    """
    try:
        return client.Index(index_name)
    except Exception as e:
        logger.error(f"Error accessing index '{index_name}': {e}")
        return None


def delete_video_vectors(
    index,
    video_id: str,
    namespace: str
) -> int:
    """
    Delete all vectors for a video from Pinecone.
    
    Uses prefix filter on chunk IDs.
    
    Args:
        index: Pinecone index
        video_id: Video ID (prefix for chunk IDs)
        namespace: Namespace to delete from
        
    Returns:
        Number of vectors deleted (estimated)
    """
    try:
        # Delete by ID prefix using filter
        # Note: Pinecone serverless uses delete with filter
        prefix = f"{video_id}_chunk_"
        
        # For serverless/starter, we need to delete by ID pattern
        # First, query to find matching IDs
        # Then delete those IDs
        
        # Alternative: delete by metadata filter
        index.delete(
            filter={"video_id": {"$eq": video_id}},
            namespace=namespace
        )
        
        logger.info(f"Deleted vectors for video {video_id} from namespace {namespace}")
        return -1  # Unknown count
        
    except Exception as e:
        logger.warning(f"Error deleting vectors for {video_id}: {e}")
        # Try alternative method - delete by ID list
        try:
            # Generate expected IDs (assume up to 100 chunks)
            ids_to_delete = [f"{video_id}_chunk_{i:03d}" for i in range(100)]
            index.delete(ids=ids_to_delete, namespace=namespace)
            return -1
        except Exception as e2:
            logger.error(f"Failed to delete vectors: {e2}")
            return 0


def upsert_batch(
    index,
    vectors: List[Dict[str, Any]],
    namespace: str,
    batch_size: int = DEFAULT_BATCH_SIZE
) -> Tuple[int, int]:
    """
    Upsert vectors to Pinecone in batches.
    
    Args:
        index: Pinecone index
        vectors: List of vector dicts
        namespace: Namespace to upsert to
        batch_size: Vectors per batch
        
    Returns:
        Tuple of (successful count, failed count)
    """
    successful = 0
    failed = 0
    
    num_batches = (len(vectors) + batch_size - 1) // batch_size
    
    for i in range(0, len(vectors), batch_size):
        batch = vectors[i:i + batch_size]
        batch_num = (i // batch_size) + 1
        
        try:
            index.upsert(
                vectors=batch,
                namespace=namespace
            )
            successful += len(batch)
            logger.debug(f"Batch {batch_num}/{num_batches}: {len(batch)} vectors upserted")
            
        except Exception as e:
            failed += len(batch)
            logger.error(f"Batch {batch_num} failed: {e}")
    
    return successful, failed


def get_namespace_stats(index, namespace: str) -> Dict[str, Any]:
    """Get statistics for a namespace."""
    try:
        stats = index.describe_index_stats()
        ns_stats = stats.namespaces.get(namespace, {})
        return {
            "vector_count": getattr(ns_stats, 'vector_count', 0),
            "total_index_vectors": stats.total_vector_count
        }
    except Exception as e:
        logger.warning(f"Could not get namespace stats: {e}")
        return {"vector_count": 0}


# ============================================================================
# TEST QUERY
# ============================================================================

def create_openai_client(api_key: Optional[str] = None) -> Optional['OpenAI']:
    """Create OpenAI client for test queries."""
    if not OPENAI_AVAILABLE:
        return None
    
    key = api_key or OPENAI_API_KEY or os.getenv("OPENAI_API_KEY")
    if not key:
        return None
    
    return OpenAI(api_key=key)


def generate_query_embedding(
    client: 'OpenAI',
    query: str,
    model: str = EMBEDDING_MODEL
) -> Optional[List[float]]:
    """Generate embedding for a search query."""
    try:
        response = client.embeddings.create(
            model=model,
            input=query
        )
        return response.data[0].embedding
    except Exception as e:
        logger.error(f"Error generating query embedding: {e}")
        return None


def test_query(
    index,
    namespace: str,
    query: str,
    openai_client: Optional['OpenAI'] = None,
    top_k: int = 3
) -> Optional[Dict[str, Any]]:
    """
    Run a test query against the index.
    
    Args:
        index: Pinecone index
        namespace: Namespace to query
        query: Search query text
        openai_client: OpenAI client for embedding generation
        top_k: Number of results to return
        
    Returns:
        Query results or None if failed
    """
    if openai_client is None:
        openai_client = create_openai_client()
        if openai_client is None:
            logger.error("OpenAI client needed for test query")
            return None
    
    # Generate query embedding
    query_embedding = generate_query_embedding(openai_client, query)
    if query_embedding is None:
        return None
    
    try:
        results = index.query(
            vector=query_embedding,
            namespace=namespace,
            top_k=top_k,
            include_metadata=True
        )
        
        return {
            "query": query,
            "namespace": namespace,
            "matches": [
                {
                    "id": match.id,
                    "score": match.score,
                    "metadata": dict(match.metadata) if match.metadata else {}
                }
                for match in results.matches
            ]
        }
        
    except Exception as e:
        logger.error(f"Test query failed: {e}")
        return None


# ============================================================================
# PROCESSING
# ============================================================================

def process_video(
    video_id: str,
    embeddings_dir: Path,
    index,
    namespace: str,
    batch_size: int = DEFAULT_BATCH_SIZE,
    replace: bool = False,
    dry_run: bool = False,
    quiet: bool = False
) -> Dict[str, Any]:
    """
    Process a single video - upload its embeddings to Pinecone.
    
    Args:
        video_id: YouTube video ID
        embeddings_dir: Directory containing embedding files
        index: Pinecone index
        namespace: Namespace to upload to
        batch_size: Vectors per upsert
        replace: Delete existing vectors first
        dry_run: Validate without uploading
        quiet: Suppress progress output
        
    Returns:
        Result dict with status and statistics
    """
    result = {
        "video_id": video_id,
        "status": "pending",
        "vectors": 0,
        "uploaded": 0,
        "failed": 0,
        "namespace": namespace,
        "error": None
    }
    
    # Find embedding file
    embedding_file = get_embedding_path(video_id, embeddings_dir)
    if not embedding_file.exists():
        result["status"] = "error"
        result["error"] = f"Embedding file not found: {embedding_file}"
        return result
    
    # Load embeddings
    embedding_data = load_embedding_file(embedding_file)
    if not embedding_data:
        result["status"] = "error"
        result["error"] = "Failed to load embedding file"
        return result
    
    # Prepare vectors
    vectors = prepare_vectors(embedding_data)
    if not vectors:
        result["status"] = "error"
        result["error"] = "No valid vectors found in embedding file"
        return result
    
    result["vectors"] = len(vectors)
    
    if not quiet:
        logger.info(f"Video {video_id}: {len(vectors)} vectors to upload")
    
    # Dry run - stop here
    if dry_run:
        result["status"] = "dry_run"
        result["uploaded"] = len(vectors)
        return result
    
    # Delete existing vectors if replacing
    if replace:
        if not quiet:
            logger.info(f"Deleting existing vectors for {video_id}")
        delete_video_vectors(index, video_id, namespace)
    
    # Upload vectors
    try:
        successful, failed = upsert_batch(index, vectors, namespace, batch_size)
        result["uploaded"] = successful
        result["failed"] = failed
        
        if failed == 0:
            result["status"] = "success"
        elif successful > 0:
            result["status"] = "partial"
        else:
            result["status"] = "error"
            result["error"] = "All batches failed"
            
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
    
    return result


def process_batch(
    video_ids: List[str],
    embeddings_dir: Path,
    index,
    namespace: str,
    batch_size: int = DEFAULT_BATCH_SIZE,
    replace: bool = False,
    dry_run: bool = False,
    quiet: bool = False
) -> Dict[str, Any]:
    """
    Process multiple videos.
    
    Returns:
        Batch report dict
    """
    results = []
    total_vectors = 0
    total_uploaded = 0
    total_failed = 0
    success_count = 0
    
    for i, video_id in enumerate(video_ids, 1):
        if not quiet:
            logger.info(f"\n[{i}/{len(video_ids)}] Processing {video_id}")
        
        result = process_video(
            video_id, embeddings_dir, index, namespace,
            batch_size, replace, dry_run, quiet
        )
        results.append(result)
        
        total_vectors += result.get("vectors", 0)
        total_uploaded += result.get("uploaded", 0)
        total_failed += result.get("failed", 0)
        
        if result["status"] in ("success", "dry_run"):
            success_count += 1
    
    report = {
        "generated_at": datetime.now().isoformat(),
        "namespace": namespace,
        "dry_run": dry_run,
        "total_videos": len(video_ids),
        "successful": success_count,
        "partial": sum(1 for r in results if r["status"] == "partial"),
        "failed": sum(1 for r in results if r["status"] == "error"),
        "total_vectors": total_vectors,
        "total_uploaded": total_uploaded,
        "total_failed": total_failed,
        "results": results
    }
    
    return report


# ============================================================================
# INPUT DETECTION
# ============================================================================

def get_video_ids_from_report(report_path: Path) -> List[str]:
    """Extract video IDs from embedding report."""
    report = load_embedding_report(report_path)
    if not report:
        return []
    
    results = report.get("results", [])
    return [r.get("video_id") for r in results 
            if r.get("video_id") and r.get("status") == "success"]


def get_video_ids_from_directory(embeddings_dir: Path) -> List[str]:
    """Get video IDs from embedding files in directory."""
    files = find_embedding_files(embeddings_dir)
    video_ids = []
    for f in files:
        # Extract video_id from filename: {video_id}_embeddings.json
        video_id = f.stem.replace("_embeddings", "")
        video_ids.append(video_id)
    return video_ids


def auto_detect_input(embeddings_dir: Path) -> Tuple[str, List[str]]:
    """
    Auto-detect input source.
    
    Returns:
        Tuple of (source description, list of video IDs)
    """
    # Check for embedding_report.json
    report_path = embeddings_dir / "embedding_report.json"
    if report_path.exists():
        video_ids = get_video_ids_from_report(report_path)
        if video_ids:
            return f"embedding_report.json ({len(video_ids)} videos)", video_ids
    
    # Check for embedding files in directory
    video_ids = get_video_ids_from_directory(embeddings_dir)
    if video_ids:
        return f"embeddings directory ({len(video_ids)} files)", video_ids
    
    return "no input found", []


# ============================================================================
# CLI
# ============================================================================

def create_parser() -> argparse.ArgumentParser:
    """Create argument parser."""
    parser = argparse.ArgumentParser(
        description="Upload embeddings to Pinecone vector database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --video-id abc123xyz                 # Single video
  %(prog)s --from-report embedding_report.json  # From report
  %(prog)s --all                                # All embedding files
  %(prog)s                                      # Auto-detect
  %(prog)s --video-id abc123 --replace          # Replace existing
  %(prog)s --video-id abc123 --test-query "hope" # Test after upload
  %(prog)s --all --dry-run                      # Validate only
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
        help="Process videos from embedding report JSON"
    )
    input_group.add_argument(
        "--all", "-a",
        action="store_true",
        help="Process all embedding files in directory"
    )
    
    # Pinecone options
    pc_group = parser.add_argument_group("Pinecone Options")
    pc_group.add_argument(
        "--index", "-i",
        default=PINECONE_INDEX,
        help=f"Pinecone index name (default: {PINECONE_INDEX})"
    )
    pc_group.add_argument(
        "--namespace", "-n",
        default=PINECONE_NAMESPACE,
        help=f"Pinecone namespace (default: {PINECONE_NAMESPACE})"
    )
    pc_group.add_argument(
        "--batch-size", "-b",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=f"Vectors per upsert (default: {DEFAULT_BATCH_SIZE}, max: {MAX_BATCH_SIZE})"
    )
    
    # Processing options
    proc_group = parser.add_argument_group("Processing Options")
    proc_group.add_argument(
        "--replace",
        action="store_true",
        help="Delete existing vectors before uploading"
    )
    proc_group.add_argument(
        "--dry-run", "-d",
        action="store_true",
        help="Validate without uploading to Pinecone"
    )
    proc_group.add_argument(
        "--test-query", "-t",
        help="Run test query after upload"
    )
    
    # Path options
    path_group = parser.add_argument_group("Path Options")
    path_group.add_argument(
        "--embeddings-dir",
        type=Path,
        default=EMBEDDINGS_DIR,
        help=f"Input embeddings directory (default: {EMBEDDINGS_DIR})"
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
        help="Save upload report to file"
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
    
    # Ensure directory exists
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
        video_ids = get_video_ids_from_directory(args.embeddings_dir)
        source = f"all files in {args.embeddings_dir}"
    else:
        source, video_ids = auto_detect_input(args.embeddings_dir)
    
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
        logger.info(f"Index: {args.index}")
        logger.info(f"Namespace: {args.namespace}")
        if args.dry_run:
            logger.info("DRY RUN - no vectors will be uploaded")
    
    # Create Pinecone client and index (unless dry run)
    index = None
    if not args.dry_run:
        client = create_pinecone_client()
        if client is None:
            if args.json:
                print(json.dumps({"error": "Pinecone client not available"}))
            sys.exit(1)
        
        index = get_index(client, args.index)
        if index is None:
            if args.json:
                print(json.dumps({"error": f"Could not access index: {args.index}"}))
            sys.exit(1)
        
        # Show namespace stats
        if not args.quiet:
            stats = get_namespace_stats(index, args.namespace)
            logger.info(f"Namespace '{args.namespace}' current vectors: {stats.get('vector_count', 0)}")
    
    # Process videos
    if len(video_ids) == 1 and not args.save_report:
        # Single video mode
        result = process_video(
            video_ids[0],
            args.embeddings_dir,
            index,
            args.namespace,
            args.batch_size,
            args.replace,
            args.dry_run,
            args.quiet
        )
        
        # Run test query if requested
        test_result = None
        if args.test_query and result["status"] in ("success", "dry_run"):
            if not args.quiet:
                logger.info(f"\nRunning test query: '{args.test_query}'")
            test_result = test_query(index, args.namespace, args.test_query)
            result["test_query"] = test_result
        
        if args.json:
            print(json.dumps(result, indent=2))
        elif not args.quiet:
            if result["status"] == "success":
                logger.info(f"\n✓ Uploaded {result['uploaded']} vectors to '{args.namespace}'")
                if test_result and test_result.get("matches"):
                    logger.info(f"\nTest query results:")
                    for i, match in enumerate(test_result["matches"], 1):
                        score = match.get("score", 0)
                        text = match.get("metadata", {}).get("text", "")[:80]
                        logger.info(f"  {i}. [{score:.4f}] {text}...")
            elif result["status"] == "dry_run":
                logger.info(f"\n✓ Dry run complete: {result['vectors']} vectors validated")
            else:
                logger.error(f"\n✗ Failed: {result.get('error', 'Unknown error')}")
        
        sys.exit(0 if result["status"] in ("success", "dry_run") else 1)
    
    else:
        # Batch mode
        report = process_batch(
            video_ids,
            args.embeddings_dir,
            index,
            args.namespace,
            args.batch_size,
            args.replace,
            args.dry_run,
            args.quiet
        )
        
        # Run test query if requested
        if args.test_query and not args.dry_run and report["successful"] > 0:
            if not args.quiet:
                logger.info(f"\nRunning test query: '{args.test_query}'")
            test_result = test_query(index, args.namespace, args.test_query)
            report["test_query"] = test_result
        
        # Save report
        report_path = args.save_report or args.embeddings_dir / "pinecone_report.json"
        save_report(report, report_path)
        
        if args.json:
            print(json.dumps(report, indent=2))
        elif not args.quiet:
            print("\n" + "=" * 60)
            print("PINECONE UPLOAD REPORT")
            print("=" * 60)
            print(f"Index:      {args.index}")
            print(f"Namespace:  {args.namespace}")
            print(f"Dry run:    {args.dry_run}")
            print(f"Videos:     {report['total_videos']}")
            print(f"Successful: {report['successful']}")
            print(f"Partial:    {report['partial']}")
            print(f"Failed:     {report['failed']}")
            print("-" * 60)
            print(f"Total vectors:  {report['total_vectors']:,}")
            print(f"Uploaded:       {report['total_uploaded']:,}")
            print(f"Failed:         {report['total_failed']:,}")
            print("-" * 60)
            
            # Show test query results
            if report.get("test_query") and report["test_query"].get("matches"):
                print(f"\nTest query: '{args.test_query}'")
                for i, match in enumerate(report["test_query"]["matches"], 1):
                    score = match.get("score", 0)
                    text = match.get("metadata", {}).get("text", "")[:60]
                    logger.info(f"  {i}. [{score:.4f}] {text}...")
            
            print(f"\nReport saved: {report_path}")
            
            # Show updated namespace stats
            if not args.dry_run and index:
                stats = get_namespace_stats(index, args.namespace)
                print(f"Namespace total vectors: {stats.get('vector_count', 0)}")
        
        sys.exit(0 if report['failed'] == 0 else 1)


if __name__ == "__main__":
    main()
