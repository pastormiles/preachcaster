"""
Transcript Service
Fetches transcripts/captions from YouTube videos.

Adapted from CWI script 03_fetch_transcript_v1.py for SaaS architecture.
"""

import logging
from typing import Optional

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
)

logger = logging.getLogger(__name__)


class TranscriptError(Exception):
    """Exception raised when transcript fetching fails."""
    pass


class TranscriptEntry:
    """Represents a single transcript entry with timing."""

    def __init__(self, text: str, start: float, duration: float):
        self.text = text
        self.start = start  # Start time in seconds
        self.duration = duration  # Duration in seconds

    @property
    def end(self) -> float:
        """End time in seconds."""
        return self.start + self.duration

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "start": self.start,
            "duration": self.duration
        }


class Transcript:
    """Represents a full transcript with metadata."""

    def __init__(
        self,
        video_id: str,
        entries: list[TranscriptEntry],
        language: str = "en",
        is_generated: bool = True
    ):
        self.video_id = video_id
        self.entries = entries
        self.language = language
        self.is_generated = is_generated

    @property
    def full_text(self) -> str:
        """Get the full transcript as plain text."""
        return " ".join(entry.text for entry in self.entries)

    @property
    def duration_seconds(self) -> int:
        """Total duration based on last entry."""
        if not self.entries:
            return 0
        last_entry = self.entries[-1]
        return int(last_entry.end)

    @property
    def word_count(self) -> int:
        """Approximate word count."""
        return len(self.full_text.split())

    def to_dict(self) -> dict:
        return {
            "video_id": self.video_id,
            "language": self.language,
            "is_generated": self.is_generated,
            "duration_seconds": self.duration_seconds,
            "word_count": self.word_count,
            "entries": [entry.to_dict() for entry in self.entries],
            "text": self.full_text
        }

    def get_text_at_time(self, seconds: float, window: float = 30.0) -> str:
        """
        Get transcript text around a specific timestamp.

        Args:
            seconds: Target time in seconds
            window: Time window in seconds (before and after)

        Returns:
            Text within the time window
        """
        start_time = max(0, seconds - window)
        end_time = seconds + window

        relevant_entries = [
            entry for entry in self.entries
            if entry.start >= start_time and entry.start <= end_time
        ]

        return " ".join(entry.text for entry in relevant_entries)


def fetch_transcript(
    video_id: str,
    preferred_languages: Optional[list[str]] = None
) -> Transcript:
    """
    Fetch transcript for a YouTube video.

    Tries to get manual captions first, falls back to auto-generated.

    Args:
        video_id: YouTube video ID
        preferred_languages: List of language codes to try (default: ["en"])

    Returns:
        Transcript object with entries

    Raises:
        TranscriptError: If no transcript is available
    """
    if preferred_languages is None:
        preferred_languages = ["en", "en-US", "en-GB"]

    logger.info(f"Fetching transcript for {video_id}")

    try:
        # List available transcripts
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)

        # Try to get manually created transcript first
        transcript_data = None
        is_generated = False

        # Try manual transcripts
        try:
            for lang in preferred_languages:
                try:
                    transcript = transcript_list.find_manually_created_transcript([lang])
                    transcript_data = transcript.fetch()
                    is_generated = False
                    language = lang
                    logger.info(f"Found manual transcript in {lang}")
                    break
                except NoTranscriptFound:
                    continue
        except Exception:
            pass

        # Fall back to auto-generated
        if transcript_data is None:
            try:
                for lang in preferred_languages:
                    try:
                        transcript = transcript_list.find_generated_transcript([lang])
                        transcript_data = transcript.fetch()
                        is_generated = True
                        language = lang
                        logger.info(f"Found auto-generated transcript in {lang}")
                        break
                    except NoTranscriptFound:
                        continue
            except Exception:
                pass

        # Last resort: get any available transcript
        if transcript_data is None:
            try:
                for transcript in transcript_list:
                    transcript_data = transcript.fetch()
                    is_generated = transcript.is_generated
                    language = transcript.language_code
                    logger.info(f"Using available transcript in {language}")
                    break
            except Exception:
                pass

        if transcript_data is None:
            raise TranscriptError(f"No transcript available for {video_id}")

        # Convert to TranscriptEntry objects
        entries = [
            TranscriptEntry(
                text=item.get("text", ""),
                start=item.get("start", 0),
                duration=item.get("duration", 0)
            )
            for item in transcript_data
        ]

        return Transcript(
            video_id=video_id,
            entries=entries,
            language=language,
            is_generated=is_generated
        )

    except TranscriptsDisabled:
        raise TranscriptError(f"Transcripts are disabled for video {video_id}")
    except VideoUnavailable:
        raise TranscriptError(f"Video {video_id} is unavailable")
    except NoTranscriptFound:
        raise TranscriptError(f"No transcript found for video {video_id}")
    except Exception as e:
        raise TranscriptError(f"Failed to fetch transcript: {e}")


def format_timestamp(seconds: float) -> str:
    """
    Format seconds as HH:MM:SS or MM:SS timestamp.

    Args:
        seconds: Time in seconds

    Returns:
        Formatted timestamp string
    """
    seconds = int(seconds)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def transcript_to_timestamped_text(transcript: Transcript) -> str:
    """
    Convert transcript to text with timestamps.

    Useful for display and debugging.

    Args:
        transcript: Transcript object

    Returns:
        Text with [MM:SS] timestamps
    """
    lines = []
    for entry in transcript.entries:
        timestamp = format_timestamp(entry.start)
        lines.append(f"[{timestamp}] {entry.text}")
    return "\n".join(lines)


def transcript_to_srt(transcript: Transcript) -> str:
    """
    Convert transcript to SRT subtitle format.

    Args:
        transcript: Transcript object

    Returns:
        SRT formatted string
    """
    lines = []

    for i, entry in enumerate(transcript.entries, 1):
        start_time = _seconds_to_srt_time(entry.start)
        end_time = _seconds_to_srt_time(entry.end)

        lines.append(str(i))
        lines.append(f"{start_time} --> {end_time}")
        lines.append(entry.text)
        lines.append("")

    return "\n".join(lines)


def _seconds_to_srt_time(seconds: float) -> str:
    """Convert seconds to SRT time format (HH:MM:SS,mmm)."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


async def get_sermon_transcript(video_id: str) -> dict:
    """
    Fetch and process transcript for a sermon video.

    Args:
        video_id: YouTube video ID

    Returns:
        dict with transcript data ready for database storage
    """
    transcript = fetch_transcript(video_id)

    return {
        "video_id": video_id,
        "language": transcript.language,
        "is_auto_generated": transcript.is_generated,
        "duration_seconds": transcript.duration_seconds,
        "word_count": transcript.word_count,
        "full_text": transcript.full_text,
        "entries_json": [entry.to_dict() for entry in transcript.entries]
    }
