"""
Audio Processor Service
Extracts audio from YouTube videos using yt-dlp and normalizes with ffmpeg.

Adapted from CWI script 02_extract_audio_v1.py for SaaS architecture.
"""

import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from google.cloud import storage

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Audio extraction settings
AUDIO_FORMAT = "mp3"
AUDIO_BITRATE = "128k"
AUDIO_CHANNELS = 1  # Mono for speech
SAMPLE_RATE = 44100


class AudioProcessorError(Exception):
    """Exception raised when audio processing fails."""
    pass


def check_dependencies() -> dict:
    """
    Check if required tools (yt-dlp, ffmpeg) are available.

    Returns:
        dict with 'yt_dlp' and 'ffmpeg' boolean status
    """
    result = {"yt_dlp": False, "ffmpeg": False}

    try:
        subprocess.run(
            ["yt-dlp", "--version"],
            capture_output=True,
            check=True
        )
        result["yt_dlp"] = True
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    try:
        subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            check=True
        )
        result["ffmpeg"] = True
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    return result


def extract_audio_from_youtube(
    video_id: str,
    output_dir: Optional[Path] = None
) -> dict:
    """
    Extract audio from a YouTube video.

    Args:
        video_id: YouTube video ID
        output_dir: Directory for output file (uses temp dir if not specified)

    Returns:
        dict with:
            - file_path: Path to extracted audio file
            - duration_seconds: Audio duration
            - file_size_bytes: File size

    Raises:
        AudioProcessorError: If extraction fails
    """
    youtube_url = f"https://www.youtube.com/watch?v={video_id}"

    if output_dir is None:
        output_dir = Path(tempfile.mkdtemp())
    else:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / f"{video_id}.{AUDIO_FORMAT}"

    # yt-dlp options for audio extraction
    yt_dlp_cmd = [
        "yt-dlp",
        "--extract-audio",
        "--audio-format", AUDIO_FORMAT,
        "--audio-quality", "0",  # Best quality before conversion
        "--output", str(output_dir / f"{video_id}.%(ext)s"),
        "--no-playlist",
        "--no-warnings",
        "--quiet",
        youtube_url
    ]

    logger.info(f"Extracting audio from {video_id}")

    try:
        result = subprocess.run(
            yt_dlp_cmd,
            capture_output=True,
            text=True,
            timeout=600  # 10 minute timeout
        )

        if result.returncode != 0:
            error_msg = result.stderr or result.stdout or "Unknown error"
            raise AudioProcessorError(f"yt-dlp failed: {error_msg}")

    except subprocess.TimeoutExpired:
        raise AudioProcessorError("Audio extraction timed out after 10 minutes")
    except FileNotFoundError:
        raise AudioProcessorError("yt-dlp not found. Install with: pip install yt-dlp")

    # Check if file was created
    if not output_file.exists():
        # yt-dlp might have created file with different extension
        possible_files = list(output_dir.glob(f"{video_id}.*"))
        if possible_files:
            # Convert to MP3 if needed
            source_file = possible_files[0]
            if source_file.suffix != f".{AUDIO_FORMAT}":
                output_file = convert_to_mp3(source_file, output_file)
                source_file.unlink()  # Remove original
        else:
            raise AudioProcessorError(f"Audio file not created for {video_id}")

    # Normalize audio with ffmpeg
    normalized_file = normalize_audio(output_file)

    # Get duration and file size
    duration = get_audio_duration(normalized_file)
    file_size = normalized_file.stat().st_size

    logger.info(f"Audio extracted: {normalized_file} ({duration}s, {file_size} bytes)")

    return {
        "file_path": normalized_file,
        "duration_seconds": duration,
        "file_size_bytes": file_size
    }


def convert_to_mp3(input_file: Path, output_file: Path) -> Path:
    """
    Convert audio file to MP3 format.

    Args:
        input_file: Source audio file
        output_file: Destination MP3 file

    Returns:
        Path to converted file
    """
    ffmpeg_cmd = [
        "ffmpeg",
        "-i", str(input_file),
        "-codec:a", "libmp3lame",
        "-b:a", AUDIO_BITRATE,
        "-ac", str(AUDIO_CHANNELS),
        "-ar", str(SAMPLE_RATE),
        "-y",  # Overwrite output
        str(output_file)
    ]

    try:
        subprocess.run(
            ffmpeg_cmd,
            capture_output=True,
            check=True,
            timeout=300
        )
    except subprocess.CalledProcessError as e:
        raise AudioProcessorError(f"FFmpeg conversion failed: {e.stderr}")
    except FileNotFoundError:
        raise AudioProcessorError("ffmpeg not found")

    return output_file


def normalize_audio(input_file: Path) -> Path:
    """
    Normalize audio levels using ffmpeg loudnorm filter.

    Args:
        input_file: Audio file to normalize

    Returns:
        Path to normalized file (replaces original)
    """
    temp_file = input_file.with_suffix(".normalized.mp3")

    # Two-pass loudness normalization for broadcast standards
    # Target: -16 LUFS (podcast standard)
    ffmpeg_cmd = [
        "ffmpeg",
        "-i", str(input_file),
        "-af", "loudnorm=I=-16:LRA=11:TP=-1.5",
        "-codec:a", "libmp3lame",
        "-b:a", AUDIO_BITRATE,
        "-ac", str(AUDIO_CHANNELS),
        "-ar", str(SAMPLE_RATE),
        "-y",
        str(temp_file)
    ]

    try:
        subprocess.run(
            ffmpeg_cmd,
            capture_output=True,
            check=True,
            timeout=300
        )

        # Replace original with normalized version
        temp_file.replace(input_file)

    except subprocess.CalledProcessError as e:
        # If normalization fails, keep original
        logger.warning(f"Audio normalization failed: {e.stderr}")
        if temp_file.exists():
            temp_file.unlink()
    except FileNotFoundError:
        logger.warning("ffmpeg not found, skipping normalization")

    return input_file


def get_audio_duration(audio_file: Path) -> int:
    """
    Get audio duration in seconds using ffprobe.

    Args:
        audio_file: Path to audio file

    Returns:
        Duration in seconds (integer)
    """
    ffprobe_cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(audio_file)
    ]

    try:
        result = subprocess.run(
            ffprobe_cmd,
            capture_output=True,
            text=True,
            check=True
        )
        return int(float(result.stdout.strip()))
    except (subprocess.CalledProcessError, ValueError, FileNotFoundError):
        return 0


def upload_to_gcs(
    local_file: Path,
    church_slug: str,
    video_id: str
) -> str:
    """
    Upload audio file to Google Cloud Storage.

    Args:
        local_file: Path to local audio file
        church_slug: Church slug for organization
        video_id: YouTube video ID

    Returns:
        Public URL of uploaded file
    """
    if not settings.gcs_bucket_name:
        raise AudioProcessorError("GCS bucket not configured")

    try:
        client = storage.Client(project=settings.gcs_project_id)
        bucket = client.bucket(settings.gcs_bucket_name)

        # Organize by church: audio/{church_slug}/{video_id}.mp3
        blob_name = f"audio/{church_slug}/{video_id}.{AUDIO_FORMAT}"
        blob = bucket.blob(blob_name)

        # Upload with content type
        blob.upload_from_filename(
            str(local_file),
            content_type="audio/mpeg"
        )

        # Make publicly accessible
        blob.make_public()

        logger.info(f"Uploaded to GCS: {blob.public_url}")
        return blob.public_url

    except Exception as e:
        raise AudioProcessorError(f"GCS upload failed: {e}")


async def process_sermon_audio(
    video_id: str,
    church_slug: str
) -> dict:
    """
    Full audio processing pipeline for a sermon.

    1. Extract audio from YouTube
    2. Normalize audio levels
    3. Upload to cloud storage
    4. Clean up local files

    Args:
        video_id: YouTube video ID
        church_slug: Church slug for storage organization

    Returns:
        dict with audio_url, duration_seconds, file_size_bytes
    """
    temp_dir = None

    try:
        # Extract audio to temp directory
        temp_dir = Path(tempfile.mkdtemp())
        extraction_result = extract_audio_from_youtube(video_id, temp_dir)

        local_file = extraction_result["file_path"]

        # Upload to cloud storage
        audio_url = upload_to_gcs(local_file, church_slug, video_id)

        return {
            "audio_url": audio_url,
            "duration_seconds": extraction_result["duration_seconds"],
            "file_size_bytes": extraction_result["file_size_bytes"]
        }

    finally:
        # Clean up temp files
        if temp_dir and temp_dir.exists():
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
