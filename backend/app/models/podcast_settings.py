from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text

from sqlalchemy.orm import relationship

from app.db.database import Base


class PodcastSettings(Base):
    __tablename__ = "podcast_settings"

    id = Column(Integer, primary_key=True, index=True)
    church_id = Column(Integer, ForeignKey("churches.id"), nullable=False, unique=True)

    # Podcast metadata (for RSS feed)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    author = Column(String(255), nullable=True)
    email = Column(String(255), nullable=True)
    artwork_url = Column(String(500), nullable=True)

    # iTunes/Apple Podcasts specific
    category = Column(String(100), default="Religion & Spirituality")
    subcategory = Column(String(100), default="Christianity")
    language = Column(String(10), default="en")
    explicit = Column(String(5), default="no")

    # Website
    website_url = Column(String(500), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    church = relationship("Church", back_populates="podcast_settings")
