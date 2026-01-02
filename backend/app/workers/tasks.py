"""
Background Tasks for Sermon Processing
Uses Redis Queue (RQ) for async task execution.

Pipeline Steps:
1. Extract audio from YouTube
2. Fetch transcript from YouTube
3. Format transcript with AI
4. Generate AI content (summary, discussion guide, etc.)
5. Generate PDF discussion guide
6. Update database with results
"""

import logging
from datetime import datetime
from typing import Optional

from redis import Redis
from rq import Queue
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.database import SessionLocal
from app.models import Sermon, SermonStatus
from app.services.audio_processor import process_sermon_audio, AudioProcessorError
from app.services.transcript_service import get_sermon_transcript, TranscriptError
from app.services.ai_extractor import (
    process_sermon_ai_content,
    format_transcript,
    AIExtractorError
)
from app.services.pdf_generator import create_discussion_guide

logger = logging.getLogger(__name__)
settings = get_settings()

# Redis connection
redis_conn = Redis.from_url(settings.redis_url)

# Task queues with different priorities
high_priority_queue = Queue("high", connection=redis_conn)
default_queue = Queue("default", connection=redis_conn)
low_priority_queue = Queue("low", connection=redis_conn)


def get_db() -> Session:
    """Get database session for worker tasks."""
    return SessionLocal()


def update_sermon_status(
    sermon_id: int,
    status: SermonStatus,
    error_message: Optional[str] = None,
    **kwargs
):
    """Update sermon status in database."""
    db = get_db()
    try:
        sermon = db.query(Sermon).filter(Sermon.id == sermon_id).first()
        if sermon:
            sermon.status = status.value
            if error_message:
                sermon.error_message = error_message
            for key, value in kwargs.items():
                if hasattr(sermon, key):
                    setattr(sermon, key, value)
            db.commit()
    finally:
        db.close()


def process_sermon_pipeline(sermon_id: int):
    """
    Full sermon processing pipeline.
    
    This is the main task that orchestrates all processing steps.
    Called when a new sermon is detected or manually triggered.
    
    Steps:
    1. Extract audio from YouTube → upload to GCS
    2. Fetch transcript from YouTube
    3. Format transcript with AI (punctuation, paragraphs)
    4. Generate AI content (summary, discussion guide content)
    5. Generate PDF discussion guide → upload to GCS
    6. Update sermon record with all results
    """
    db = get_db()
    
    try:
        # Get sermon record
        sermon = db.query(Sermon).filter(Sermon.id == sermon_id).first()
        if not sermon:
            logger.error(f"Sermon {sermon_id} not found")
            return
        
        video_id = sermon.youtube_video_id
        church = sermon.church
        
        logger.info(f"Starting pipeline for sermon {sermon_id} (video: {video_id})")
        
        # Update status to processing
        sermon.status = SermonStatus.PROCESSING.value
        sermon.processing_started_at = datetime.utcnow()
        db.commit()
        
        # Step 1: Extract audio
        logger.info(f"Step 1: Extracting audio for {video_id}")
        try:
            audio_result = process_sermon_audio(video_id, church.slug)
            sermon.audio_url = audio_result["audio_url"]
            sermon.duration_seconds = audio_result["duration_seconds"]
            db.commit()
            logger.info(f"Audio extracted: {audio_result['audio_url']}")
        except AudioProcessorError as e:
            logger.error(f"Audio extraction failed: {e}")
            sermon.status = SermonStatus.FAILED.value
            sermon.error_message = f"Audio extraction failed: {e}"
            db.commit()
            return
        
        # Step 2: Fetch transcript
        logger.info(f"Step 2: Fetching transcript for {video_id}")
        try:
            transcript_result = get_sermon_transcript(video_id)
            raw_transcript = transcript_result["full_text"]
            sermon.transcript_json = transcript_result["entries_json"]
            db.commit()
            logger.info(f"Transcript fetched: {transcript_result['word_count']} words")
        except TranscriptError as e:
            logger.warning(f"Transcript fetch failed: {e}")
            raw_transcript = None
            # Continue without transcript - audio is still valuable
        
        # Step 3: Format transcript with AI
        if raw_transcript:
            logger.info(f"Step 3: Formatting transcript for {video_id}")
            try:
                formatted_transcript = format_transcript(raw_transcript)
                # Store formatted version
                sermon.formatted_transcript = formatted_transcript
                db.commit()
                logger.info("Transcript formatted")
            except Exception as e:
                logger.warning(f"Transcript formatting failed: {e}")
                formatted_transcript = raw_transcript
        else:
            formatted_transcript = None
        
        # Step 4: Generate AI content
        if formatted_transcript:
            logger.info(f"Step 4: Generating AI content for {video_id}")
            try:
                ai_content = process_sermon_ai_content(
                    transcript_text=formatted_transcript,
                    title=sermon.title,
                    video_id=video_id
                )
                sermon.summary = ai_content.get("summary")
                sermon.big_idea = ai_content.get("big_idea")
                sermon.primary_scripture = ai_content.get("primary_scripture")
                sermon.topics = ai_content.get("topics", [])
                sermon.discussion_guide_json = ai_content.get("discussion_guide")
                sermon.ai_content_json = ai_content
                db.commit()
                logger.info("AI content generated")
            except AIExtractorError as e:
                logger.warning(f"AI content generation failed: {e}")
                ai_content = None
        else:
            ai_content = None
        
        # Step 5: Generate PDF discussion guide
        if ai_content and ai_content.get("discussion_guide"):
            logger.info(f"Step 5: Generating discussion guide PDF for {video_id}")
            try:
                pdf_result = create_discussion_guide(
                    ai_content=ai_content,
                    church_name=church.name,
                    church_slug=church.slug,
                    sermon_title=sermon.title,
                    video_id=video_id,
                    sermon_date=sermon.sermon_date.strftime("%B %d, %Y") if sermon.sermon_date else None,
                    speaker=sermon.speaker
                )
                sermon.discussion_guide_url = pdf_result["pdf_url"]
                db.commit()
                logger.info(f"Discussion guide created: {pdf_result['pdf_url']}")
            except Exception as e:
                logger.warning(f"Discussion guide generation failed: {e}")
        
        # Mark as published
        sermon.status = SermonStatus.PUBLISHED.value
        sermon.published_at = datetime.utcnow()
        db.commit()
        
        logger.info(f"Sermon {sermon_id} processing complete!")
        
    except Exception as e:
        logger.exception(f"Pipeline failed for sermon {sermon_id}: {e}")
        try:
            sermon = db.query(Sermon).filter(Sermon.id == sermon_id).first()
            if sermon:
                sermon.status = SermonStatus.FAILED.value
                sermon.error_message = str(e)
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


def enqueue_sermon_processing(sermon_id: int, priority: str = "default"):
    """
    Add sermon to processing queue.
    
    Args:
        sermon_id: Database ID of sermon to process
        priority: Queue priority (high, default, low)
    """
    queue = {
        "high": high_priority_queue,
        "default": default_queue,
        "low": low_priority_queue
    }.get(priority, default_queue)
    
    job = queue.enqueue(
        process_sermon_pipeline,
        sermon_id,
        job_timeout="30m",  # 30 minute timeout
        result_ttl=86400,   # Keep result for 24 hours
        failure_ttl=604800  # Keep failures for 7 days
    )
    
    logger.info(f"Enqueued sermon {sermon_id} for processing (job: {job.id})")
    return job.id


def reprocess_failed_sermon(sermon_id: int):
    """
    Requeue a failed sermon for reprocessing.
    Resets status and enqueues again.
    """
    db = get_db()
    try:
        sermon = db.query(Sermon).filter(Sermon.id == sermon_id).first()
        if sermon:
            sermon.status = SermonStatus.PENDING.value
            sermon.error_message = None
            db.commit()
            return enqueue_sermon_processing(sermon_id)
    finally:
        db.close()
