from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, JSON, Enum
from sqlalchemy.orm import relationship
import enum

from app.db.database import Base


class SermonStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    PUBLISHED = "published"
    FAILED = "failed"


class Sermon(Base):
    __tablename__ = "sermons"

    id = Column(Integer, primary_key=True, index=True)
    church_id = Column(Integer, ForeignKey("churches.id"), nullable=False)

    # YouTube source
    youtube_video_id = Column(String(20), nullable=False, index=True)
    youtube_url = Column(String(255), nullable=False)

    # Sermon metadata
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    speaker = Column(String(255), nullable=True)
    scripture_references = Column(String(500), nullable=True)  # e.g., "John 3:16, Romans 8:28"
    sermon_date = Column(DateTime, nullable=True)

    # Audio
    audio_url = Column(String(500), nullable=True)
    duration_seconds = Column(Integer, nullable=True)

    # Transcript (stored as JSON with timestamps)
    # Format: [{"start": 0.0, "duration": 5.2, "text": "Welcome everyone..."}, ...]
    transcript_json = Column(JSON, nullable=True)
    # AI-formatted transcript with proper punctuation and paragraphs
    formatted_transcript = Column(Text, nullable=True)

    # AI-generated content
    summary = Column(Text, nullable=True)  # 2-3 sentence podcast description
    big_idea = Column(Text, nullable=True)  # One memorable sentence
    primary_scripture = Column(JSON, nullable=True)  # {"reference": "...", "text": "..."}
    topics = Column(JSON, nullable=True)  # ["faith", "prayer", "grace"]
    discussion_guide_json = Column(JSON, nullable=True)  # Full discussion guide content
    ai_content_json = Column(JSON, nullable=True)  # Complete AI response for reference

    # Generated files
    discussion_guide_url = Column(String(500), nullable=True)  # PDF URL

    # Status
    status = Column(String(20), default=SermonStatus.PENDING.value)
    error_message = Column(Text, nullable=True)

    # Timestamps
    processing_started_at = Column(DateTime, nullable=True)
    published_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    church = relationship("Church", back_populates="sermons")

    @property
    def slug(self) -> str:
        """Generate URL-friendly slug from title."""
        import re
        slug = self.title.lower()
        slug = re.sub(r'[^a-z0-9\s-]', '', slug)
        slug = re.sub(r'[\s_]+', '-', slug)
        slug = re.sub(r'-+', '-', slug)
        return f"{slug}-{self.id}" if self.id else slug
