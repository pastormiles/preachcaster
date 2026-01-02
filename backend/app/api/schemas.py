from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr


# ============== Auth Schemas ==============

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    church_name: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: int
    email: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ============== Church Schemas ==============

class ChurchResponse(BaseModel):
    id: int
    name: str
    slug: str
    youtube_channel_id: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ChurchUpdate(BaseModel):
    name: Optional[str] = None


# ============== Podcast Settings Schemas ==============

class PodcastSettingsCreate(BaseModel):
    title: str
    description: Optional[str] = None
    author: Optional[str] = None
    email: Optional[EmailStr] = None
    category: str = "Religion & Spirituality"
    subcategory: str = "Christianity"
    language: str = "en"
    website_url: Optional[str] = None


class PodcastSettingsResponse(BaseModel):
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

    class Config:
        from_attributes = True


# ============== Sermon Schemas ==============

class SermonCreate(BaseModel):
    youtube_url: str


class SermonUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    speaker: Optional[str] = None
    scripture_references: Optional[str] = None
    sermon_date: Optional[datetime] = None


class SermonResponse(BaseModel):
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
    status: str
    published_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class SermonDetailResponse(SermonResponse):
    transcript_json: Optional[List[dict]] = None
    summary: Optional[str] = None
    discussion_guide: Optional[str] = None


# ============== Combined Response ==============

class MeResponse(BaseModel):
    user: UserResponse
    church: Optional[ChurchResponse] = None
    podcast_settings: Optional[PodcastSettingsResponse] = None
