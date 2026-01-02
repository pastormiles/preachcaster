"""
Sermons API Endpoints
CRUD operations for sermons.
"""

from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.db.database import get_db
from app.models import User, Church, Sermon, SermonStatus
from app.api.deps import get_current_user
from app.workers.tasks import enqueue_sermon_processing

router = APIRouter(prefix="/sermons", tags=["sermons"])


class SermonCreate(BaseModel):
    """Request to create a sermon from YouTube video."""
    youtube_video_id: str
    title: Optional[str] = None
    description: Optional[str] = None
    speaker: Optional[str] = None
    sermon_date: Optional[datetime] = None


class SermonUpdate(BaseModel):
    """Request to update sermon metadata."""
    title: Optional[str] = None
    description: Optional[str] = None
    speaker: Optional[str] = None
    scripture_references: Optional[str] = None
    sermon_date: Optional[datetime] = None


class SermonResponse(BaseModel):
    """Sermon response model."""
    id: int
    youtube_video_id: str
    youtube_url: str
    title: str
    description: Optional[str]
    speaker: Optional[str]
    scripture_references: Optional[str]
    sermon_date: Optional[datetime]
    audio_url: Optional[str]
    duration_seconds: Optional[int]
    summary: Optional[str]
    big_idea: Optional[str]
    topics: Optional[List[str]]
    discussion_guide_url: Optional[str]
    status: str
    error_message: Optional[str]
    published_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class SermonListResponse(BaseModel):
    """Response with list of sermons."""
    sermons: List[SermonResponse]
    count: int
    total: int


@router.get("", response_model=SermonListResponse)
def list_sermons(
    status_filter: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List sermons for the current user's church."""
    church = db.query(Church).filter(Church.owner_id == current_user.id).first()
    if not church:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Church not found"
        )

    query = db.query(Sermon).filter(Sermon.church_id == church.id)

    if status_filter:
        query = query.filter(Sermon.status == status_filter)

    total = query.count()
    sermons = query.order_by(Sermon.sermon_date.desc()).offset(offset).limit(limit).all()

    return SermonListResponse(
        sermons=[SermonResponse.model_validate(s) for s in sermons],
        count=len(sermons),
        total=total
    )


@router.post("", response_model=SermonResponse, status_code=status.HTTP_201_CREATED)
def create_sermon(
    sermon_data: SermonCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new sermon from a YouTube video.
    
    The sermon will be queued for processing (audio extraction, transcript, AI content).
    """
    church = db.query(Church).filter(Church.owner_id == current_user.id).first()
    if not church:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Church not found"
        )

    # Check if sermon already exists
    existing = db.query(Sermon).filter(
        Sermon.church_id == church.id,
        Sermon.youtube_video_id == sermon_data.youtube_video_id
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sermon with this YouTube video already exists"
        )

    # Create sermon
    youtube_url = f"https://www.youtube.com/watch?v={sermon_data.youtube_video_id}"
    
    sermon = Sermon(
        church_id=church.id,
        youtube_video_id=sermon_data.youtube_video_id,
        youtube_url=youtube_url,
        title=sermon_data.title or f"Sermon {sermon_data.youtube_video_id}",
        description=sermon_data.description,
        speaker=sermon_data.speaker,
        sermon_date=sermon_data.sermon_date or datetime.utcnow(),
        status=SermonStatus.PENDING.value
    )

    db.add(sermon)
    db.commit()
    db.refresh(sermon)

    # Queue for processing
    try:
        enqueue_sermon_processing(sermon.id)
    except Exception as e:
        # Log error but don't fail - can be manually triggered later
        sermon.error_message = f"Failed to queue for processing: {e}"
        db.commit()

    return SermonResponse.model_validate(sermon)


@router.get("/{sermon_id}", response_model=SermonResponse)
def get_sermon(
    sermon_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific sermon."""
    church = db.query(Church).filter(Church.owner_id == current_user.id).first()
    if not church:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Church not found"
        )

    sermon = db.query(Sermon).filter(
        Sermon.id == sermon_id,
        Sermon.church_id == church.id
    ).first()

    if not sermon:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sermon not found"
        )

    return SermonResponse.model_validate(sermon)


@router.put("/{sermon_id}", response_model=SermonResponse)
def update_sermon(
    sermon_id: int,
    updates: SermonUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update sermon metadata."""
    church = db.query(Church).filter(Church.owner_id == current_user.id).first()
    if not church:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Church not found"
        )

    sermon = db.query(Sermon).filter(
        Sermon.id == sermon_id,
        Sermon.church_id == church.id
    ).first()

    if not sermon:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sermon not found"
        )

    # Update only provided fields
    update_data = updates.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if value is not None:
            setattr(sermon, field, value)

    db.commit()
    db.refresh(sermon)

    return SermonResponse.model_validate(sermon)


@router.delete("/{sermon_id}")
def delete_sermon(
    sermon_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a sermon."""
    church = db.query(Church).filter(Church.owner_id == current_user.id).first()
    if not church:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Church not found"
        )

    sermon = db.query(Sermon).filter(
        Sermon.id == sermon_id,
        Sermon.church_id == church.id
    ).first()

    if not sermon:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sermon not found"
        )

    db.delete(sermon)
    db.commit()

    return {"message": "Sermon deleted"}


@router.post("/{sermon_id}/reprocess")
def reprocess_sermon(
    sermon_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Requeue a sermon for processing (useful for failed sermons)."""
    church = db.query(Church).filter(Church.owner_id == current_user.id).first()
    if not church:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Church not found"
        )

    sermon = db.query(Sermon).filter(
        Sermon.id == sermon_id,
        Sermon.church_id == church.id
    ).first()

    if not sermon:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sermon not found"
        )

    # Reset status
    sermon.status = SermonStatus.PENDING.value
    sermon.error_message = None
    db.commit()

    # Queue for processing
    try:
        job_id = enqueue_sermon_processing(sermon.id)
        return {"message": "Sermon queued for reprocessing", "job_id": job_id}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to queue sermon: {e}"
        )
