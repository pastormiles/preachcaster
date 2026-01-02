"""
Podcast API Endpoints
Handles RSS feeds and podcast settings.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from app.db.database import get_db
from app.models import User, Church, PodcastSettings, Sermon, SermonStatus
from app.api.deps import get_current_user
from app.services.rss_generator import generate_rss_feed, validate_feed
from app.config import get_settings

router = APIRouter(prefix="/podcast", tags=["podcast"])
settings = get_settings()


class PodcastSettingsUpdate(BaseModel):
    """Request to update podcast settings."""
    title: Optional[str] = None
    description: Optional[str] = None
    author: Optional[str] = None
    email: Optional[str] = None
    artwork_url: Optional[str] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    language: Optional[str] = None
    website_url: Optional[str] = None


class PodcastSettingsResponse(BaseModel):
    """Response with podcast settings."""
    id: int
    title: str
    description: Optional[str]
    author: Optional[str]
    email: Optional[str]
    artwork_url: Optional[str]
    category: str
    subcategory: str
    language: str
    website_url: Optional[str]
    feed_url: str

    class Config:
        from_attributes = True


@router.get("/settings", response_model=PodcastSettingsResponse)
def get_podcast_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get podcast settings for the current user's church."""
    church = db.query(Church).filter(Church.owner_id == current_user.id).first()
    if not church:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Church not found"
        )

    podcast_settings = db.query(PodcastSettings).filter(
        PodcastSettings.church_id == church.id
    ).first()

    if not podcast_settings:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Podcast settings not found"
        )

    base_url = settings.app_url.replace("/api", "")
    feed_url = f"{base_url}/feed/{church.slug}.xml"

    return PodcastSettingsResponse(
        id=podcast_settings.id,
        title=podcast_settings.title,
        description=podcast_settings.description,
        author=podcast_settings.author,
        email=podcast_settings.email,
        artwork_url=podcast_settings.artwork_url,
        category=podcast_settings.category,
        subcategory=podcast_settings.subcategory,
        language=podcast_settings.language,
        website_url=podcast_settings.website_url,
        feed_url=feed_url
    )


@router.put("/settings", response_model=PodcastSettingsResponse)
def update_podcast_settings(
    updates: PodcastSettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update podcast settings."""
    church = db.query(Church).filter(Church.owner_id == current_user.id).first()
    if not church:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Church not found"
        )

    podcast_settings = db.query(PodcastSettings).filter(
        PodcastSettings.church_id == church.id
    ).first()

    if not podcast_settings:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Podcast settings not found"
        )

    # Update only provided fields
    update_data = updates.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if value is not None:
            setattr(podcast_settings, field, value)

    db.commit()
    db.refresh(podcast_settings)

    base_url = settings.app_url.replace("/api", "")
    feed_url = f"{base_url}/feed/{church.slug}.xml"

    return PodcastSettingsResponse(
        id=podcast_settings.id,
        title=podcast_settings.title,
        description=podcast_settings.description,
        author=podcast_settings.author,
        email=podcast_settings.email,
        artwork_url=podcast_settings.artwork_url,
        category=podcast_settings.category,
        subcategory=podcast_settings.subcategory,
        language=podcast_settings.language,
        website_url=podcast_settings.website_url,
        feed_url=feed_url
    )


@router.get("/validate-feed")
def validate_podcast_feed(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Validate the podcast RSS feed for issues."""
    church = db.query(Church).filter(Church.owner_id == current_user.id).first()
    if not church:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Church not found"
        )

    podcast_settings = db.query(PodcastSettings).filter(
        PodcastSettings.church_id == church.id
    ).first()

    if not podcast_settings:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Podcast settings not found"
        )

    # Get published sermons
    sermons = db.query(Sermon).filter(
        Sermon.church_id == church.id,
        Sermon.status == SermonStatus.PUBLISHED.value,
        Sermon.audio_url.isnot(None)
    ).order_by(Sermon.sermon_date.desc()).limit(100).all()

    # Generate feed
    base_url = settings.app_url.replace("/api", "")
    feed_xml = generate_rss_feed(church, podcast_settings, sermons, base_url)

    # Validate
    is_valid, issues = validate_feed(feed_xml)

    return {
        "valid": is_valid,
        "issues": issues,
        "episode_count": len(sermons)
    }
