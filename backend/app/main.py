from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.api import auth

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description="Convert YouTube sermons to podcasts automatically",
    version="0.1.0",
)

# CORS - allow frontend to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Next.js dev server
        "https://preachcaster.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"message": "Welcome to PreachCaster API"}


@app.get("/health")
async def health_check():
    return {"status": "healthy", "app": settings.app_name}


# Include routers
app.include_router(auth.router, prefix="/api")
