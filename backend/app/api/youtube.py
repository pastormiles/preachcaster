"""
YouTube API Endpoints
Handles OAuth flow and channel management.
"""

import secrets
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.db.database import get_db
from app.models import User, Church
from app.api.deps import get_current_user
from app.config import get_settings
from app.services.youtube_service import (
    get_oauth_url,
    exchange_code_for_tokens,
    get_channel_info,
    list_channel_videos,
    YouTubeServiceError
)

router = APIRouter(prefix="/youtube", tags=["youtube"])
settings = get_settings()


class YouTubeConnectResponse(BaseModel):
    """Response with OAuth URL for YouTube connection."""
    auth_url: str
    state: str


class YouTubeChannelResponse(BaseModel):
    """Response with connected YouTube channel info."""
    channel_id: str
    title: str
    thumbnail_url: str | None
    subscriber_count: int
    video_count: int
    connected: bool


class YouTubeVideoResponse(BaseModel):
    """Response for a YouTube video."""
    video_id: str
    title: str
    description: str | None
    published_at: str | None
    thumbnail_url: str | None


class YouTubeVideosResponse(BaseModel):
    """Response with list of videos."""
    videos: list[YouTubeVideoResponse]
    count: int


@router.get("/connect", response_model=YouTubeConnectResponse)
def start_youtube_connect(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Start the YouTube OAuth flow.
    
    Returns a URL to redirect the user to for Google authorization.
    The state token should be stored in the frontend to verify the callback.
    """
    # Generate CSRF state token
    state = secrets.token_urlsafe(32)
    
    # Build redirect URI (adjust for production)
    redirect_uri = f"{settings.app_url}/api/youtube/callback"
    
    # Get authorization URL
    auth_url = get_oauth_url(redirect_uri, state)
    
    return YouTubeConnectResponse(auth_url=auth_url, state=state)


@router.get("/callback")
async def youtube_oauth_callback(
    code: str,
    state: str,
    db: Session = Depends(get_db)
):
    """
    Handle the OAuth callback from Google.
    
    This endpoint is called by Google after the user authorizes.
    It exchanges the code for tokens and stores the channel info.
    
    In production, this should redirect to the frontend with success/error.
    """
    try:
        # Build redirect URI (must match what was used in authorization)
        redirect_uri = f"{settings.app_url}/api/youtube/callback"
        
        # Exchange code for tokens
        tokens = exchange_code_for_tokens(code, redirect_uri)
        
        access_token = tokens.get("access_token")
        refresh_token = tokens.get("refresh_token")
        
        if not access_token:
            raise YouTubeServiceError("No access token received")
        
        # Get channel info
        channel_info = get_channel_info(access_token)
        
        # TODO: Store tokens and channel info in database
        # This requires knowing which user initiated the flow
        # In production, decode state token to get user_id
        
        # For now, redirect to frontend with success
        frontend_url = settings.frontend_url or "http://localhost:3000"
        return RedirectResponse(
            url=f"{frontend_url}/dashboard/settings?youtube=connected&channel={channel_info['title']}"
        )
        
    except YouTubeServiceError as e:
        frontend_url = settings.frontend_url or "http://localhost:3000"
        return RedirectResponse(
            url=f"{frontend_url}/dashboard/settings?youtube=error&message={str(e)}"
        )


@router.post("/connect/complete")
async def complete_youtube_connection(
    code: str,
    state: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Complete the YouTube OAuth flow (alternative to redirect callback).
    
    The frontend can call this with the code and state from the URL
    after the user is redirected back.
    """
    try:
        redirect_uri = f"{settings.app_url}/api/youtube/callback"
        
        # Exchange code for tokens
        tokens = exchange_code_for_tokens(code, redirect_uri)
        
        access_token = tokens.get("access_token")
        refresh_token = tokens.get("refresh_token")
        
        if not access_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No access token received from Google"
            )
        
        # Get channel info
        channel_info = get_channel_info(access_token)
        
        # Get user's church
        church = db.query(Church).filter(Church.owner_id == current_user.id).first()
        if not church:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Church not found"
            )
        
        # Update church with YouTube info
        church.youtube_channel_id = channel_info["channel_id"]
        church.youtube_access_token = access_token
        church.youtube_refresh_token = refresh_token
        
        db.commit()
        
        return YouTubeChannelResponse(
            channel_id=channel_info["channel_id"],
            title=channel_info["title"],
            thumbnail_url=channel_info.get("thumbnail_url"),
            subscriber_count=channel_info.get("subscriber_count", 0),
            video_count=channel_info.get("video_count", 0),
            connected=True
        )
        
    except YouTubeServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/channel", response_model=YouTubeChannelResponse)
def get_connected_channel(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get the currently connected YouTube channel info.
    """
    church = db.query(Church).filter(Church.owner_id == current_user.id).first()
    
    if not church:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Church not found"
        )
    
    if not church.youtube_channel_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No YouTube channel connected"
        )
    
    # Get fresh channel info
    try:
        channel_info = get_channel_info(church.youtube_access_token)
        
        return YouTubeChannelResponse(
            channel_id=channel_info["channel_id"],
            title=channel_info["title"],
            thumbnail_url=channel_info.get("thumbnail_url"),
            subscriber_count=channel_info.get("subscriber_count", 0),
            video_count=channel_info.get("video_count", 0),
            connected=True
        )
    except YouTubeServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to get channel info: {e}"
        )


@router.delete("/disconnect")
def disconnect_youtube(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Disconnect the YouTube channel from the church.
    """
    church = db.query(Church).filter(Church.owner_id == current_user.id).first()
    
    if not church:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Church not found"
        )
    
    church.youtube_channel_id = None
    church.youtube_access_token = None
    church.youtube_refresh_token = None
    
    db.commit()
    
    return {"message": "YouTube channel disconnected"}


@router.get("/videos", response_model=YouTubeVideosResponse)
def list_videos(
    max_results: int = 20,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List recent videos from the connected YouTube channel.
    """
    church = db.query(Church).filter(Church.owner_id == current_user.id).first()
    
    if not church:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Church not found"
        )
    
    if not church.youtube_channel_id or not church.youtube_access_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="YouTube channel not connected"
        )
    
    try:
        videos = list_channel_videos(
            access_token=church.youtube_access_token,
            channel_id=church.youtube_channel_id,
            max_results=max_results
        )
        
        return YouTubeVideosResponse(
            videos=[
                YouTubeVideoResponse(
                    video_id=v["video_id"],
                    title=v["title"],
                    description=v.get("description"),
                    published_at=v["published_at"].isoformat() if v.get("published_at") else None,
                    thumbnail_url=v.get("thumbnail_url")
                )
                for v in videos
            ],
            count=len(videos)
        )
    except YouTubeServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
