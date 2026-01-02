from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship

from app.db.database import Base


class Church(Base):
    __tablename__ = "churches"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Basic info
    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, index=True, nullable=False)

    # YouTube connection
    youtube_channel_id = Column(String(100), nullable=True)
    youtube_access_token = Column(Text, nullable=True)
    youtube_refresh_token = Column(Text, nullable=True)
    youtube_token_expires_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    owner = relationship("User", back_populates="church")
    podcast_settings = relationship("PodcastSettings", back_populates="church", uselist=False)
    sermons = relationship("Sermon", back_populates="church", order_by="desc(Sermon.sermon_date)")
