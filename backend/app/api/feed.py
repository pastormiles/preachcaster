"""
Public Feed Endpoints
Serves RSS feeds for podcast distribution.
These endpoints are PUBLIC (no authentication required).
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models import Church, PodcastSettings, Sermon, SermonStatus
from app.services.rss_generator import generate_rss_feed
from app.config import get_settings

router = APIRouter(prefix="/feed", tags=["feed"])
settings = get_settings()


@router.get("/{church_slug}.xml")
def get_podcast_feed(
    church_slug: str,
    db: Session = Depends(get_db)
):
    """
    Get the RSS feed for a church's podcast.
    
    This is the URL that Apple Podcasts, Spotify, etc. will use.
    Example: https://preachcaster.com/feed/cross-connection.xml
    """
    # Find church by slug
    church = db.query(Church).filter(Church.slug == church_slug).first()
    if not church:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Church not found"
        )
    
    # Get podcast settings
    podcast_settings = db.query(PodcastSettings).filter(
        PodcastSettings.church_id == church.id
    ).first()
    
    if not podcast_settings:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Podcast not configured"
        )
    
    # Get published sermons with audio
    sermons = db.query(Sermon).filter(
        Sermon.church_id == church.id,
        Sermon.status == SermonStatus.PUBLISHED.value,
        Sermon.audio_url.isnot(None)
    ).order_by(Sermon.sermon_date.desc()).limit(500).all()
    
    # Generate RSS feed
    base_url = settings.frontend_url or "https://preachcaster.com"
    feed_xml = generate_rss_feed(church, podcast_settings, sermons, base_url)
    
    return Response(
        content=feed_xml,
        media_type="application/rss+xml",
        headers={
            "Content-Type": "application/rss+xml; charset=utf-8",
            "Cache-Control": "public, max-age=3600"  # Cache for 1 hour
        }
    )


@router.get("/{church_slug}.json")
def get_podcast_json(
    church_slug: str,
    db: Session = Depends(get_db)
):
    """
    Get podcast info as JSON (for embeds/widgets).
    """
    church = db.query(Church).filter(Church.slug == church_slug).first()
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
            detail="Podcast not configured"
        )
    
    sermons = db.query(Sermon).filter(
        Sermon.church_id == church.id,
        Sermon.status == SermonStatus.PUBLISHED.value,
        Sermon.audio_url.isnot(None)
    ).order_by(Sermon.sermon_date.desc()).limit(50).all()
    
    base_url = settings.frontend_url or "https://preachcaster.com"
    
    return {
        "podcast": {
            "title": podcast_settings.title,
            "description": podcast_settings.description,
            "author": podcast_settings.author,
            "artwork_url": podcast_settings.artwork_url,
            "feed_url": f"{base_url}/feed/{church.slug}.xml",
            "website_url": podcast_settings.website_url or f"{base_url}/{church.slug}"
        },
        "episodes": [
            {
                "id": sermon.id,
                "title": sermon.title,
                "summary": sermon.summary,
                "audio_url": sermon.audio_url,
                "duration_seconds": sermon.duration_seconds,
                "published_at": sermon.sermon_date.isoformat() if sermon.sermon_date else None,
                "url": f"{base_url}/{church.slug}/sermons/{sermon.slug}"
            }
            for sermon in sermons
        ],
        "episode_count": len(sermons)
    }
