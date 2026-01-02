import re
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models import User, Church, PodcastSettings
from app.api.schemas import (
    UserCreate,
    UserLogin,
    Token,
    UserResponse,
    MeResponse,
    ChurchResponse,
    PodcastSettingsResponse,
)
from app.api.deps import get_current_user
from app.services.auth_service import (
    get_user_by_email,
    create_user,
    authenticate_user,
    create_access_token,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def generate_slug(name: str) -> str:
    """Generate a URL-friendly slug from a church name."""
    slug = name.lower()
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'[\s_]+', '-', slug)
    slug = re.sub(r'-+', '-', slug)
    return slug.strip('-')


@router.post("/register", response_model=Token)
def register(user_data: UserCreate, db: Session = Depends(get_db)):
    """Register a new user with their church."""
    # Check if user already exists
    existing_user = get_user_by_email(db, user_data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Create user
    user = create_user(db, user_data.email, user_data.password)

    # Create church for user
    slug = generate_slug(user_data.church_name)
    # Ensure slug is unique
    base_slug = slug
    counter = 1
    while db.query(Church).filter(Church.slug == slug).first():
        slug = f"{base_slug}-{counter}"
        counter += 1

    church = Church(
        owner_id=user.id,
        name=user_data.church_name,
        slug=slug
    )
    db.add(church)

    # Create default podcast settings
    podcast_settings = PodcastSettings(
        church_id=church.id,
        title=f"{user_data.church_name} Sermons",
        author=user_data.church_name,
    )
    db.add(podcast_settings)
    db.commit()

    # Generate access token
    access_token = create_access_token(data={"sub": user.id})
    return Token(access_token=access_token)


@router.post("/login", response_model=Token)
def login(credentials: UserLogin, db: Session = Depends(get_db)):
    """Login with email and password."""
    user = authenticate_user(db, credentials.email, credentials.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(data={"sub": user.id})
    return Token(access_token=access_token)


@router.get("/me", response_model=MeResponse)
def get_me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get the current user's profile, church, and podcast settings."""
    church = db.query(Church).filter(Church.owner_id == current_user.id).first()
    podcast_settings = None
    if church:
        podcast_settings = db.query(PodcastSettings).filter(
            PodcastSettings.church_id == church.id
        ).first()

    return MeResponse(
        user=UserResponse.model_validate(current_user),
        church=ChurchResponse.model_validate(church) if church else None,
        podcast_settings=PodcastSettingsResponse.model_validate(podcast_settings) if podcast_settings else None,
    )
