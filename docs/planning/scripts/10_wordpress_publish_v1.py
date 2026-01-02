#!/usr/bin/env python3
"""
================================================================================
PreachCaster WordPress Publisher
================================================================================

Script: 10_wordpress_publish_v1.py
Version: 1.0
Created: CW08
Purpose: Publish podcast episodes to WordPress via REST API

DESCRIPTION
-----------
Publishes processed sermon episodes to WordPress. Uploads audio files to the
media library, creates/updates podcast posts with all content sections, and
updates the episode package with WordPress post information.

WORDPRESS REQUIREMENTS
----------------------
1. WordPress 5.6+ (for Application Passwords)
2. REST API enabled (default in modern WordPress)
3. User with 'upload_files' and 'publish_posts' capabilities
4. Application Password generated for the user

AUTHENTICATION
--------------
Uses WordPress Application Passwords (not regular password).
Generate at: Users → Your Profile → Application Passwords

Store credentials in .env:
    WORDPRESS_USERNAME=your_username
    WORDPRESS_APP_PASSWORD=xxxx xxxx xxxx xxxx xxxx xxxx

USAGE
-----
# Publish single episode
python 10_wordpress_publish_v1.py --video-id abc123xyz

# Publish from episode.json
python 10_wordpress_publish_v1.py --episode-file data/episodes/abc123_episode.json

# Publish all unprocessed episodes
python 10_wordpress_publish_v1.py --all

# Update existing post
python 10_wordpress_publish_v1.py --video-id abc123 --update

# Dry run (test without publishing)
python 10_wordpress_publish_v1.py --video-id abc123 --dry-run

# Publish as draft
python 10_wordpress_publish_v1.py --video-id abc123 --status draft

# Custom post type
python 10_wordpress_publish_v1.py --video-id abc123 --post-type podcast

# Skip audio upload (use external URL)
python 10_wordpress_publish_v1.py --video-id abc123 --audio-url https://cdn.example.com/audio.mp3

# JSON output
python 10_wordpress_publish_v1.py --video-id abc123 --json

OUTPUT FILES
------------
- data/wordpress/publish_report.json  : Publishing report
- Episode JSON updated with post ID and URL

WORDPRESS POST STRUCTURE
------------------------
The published post includes:
- Title: Sermon title
- Content: Full HTML with sections
- Excerpt: AI-generated summary
- Categories: Podcast category
- Tags: AI-generated topics
- Custom Fields: Audio URL, duration, scripture, etc.

DEPENDENCIES
------------
- requests (HTTP client)
- python-dotenv (environment variables)

================================================================================
"""

import argparse
import base64
import json
import logging
import mimetypes
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urljoin

try:
    import requests
except ImportError:
    print("Error: requests library required. Install with: pip install requests")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

try:
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from config.config import (
        EPISODES_DIR,
        AUDIO_DIR,
        GUIDES_DIR,
        DATA_DIR,
        WORDPRESS_URL,
        WORDPRESS_USERNAME,
        WORDPRESS_APP_PASSWORD,
        WORDPRESS_POST_TYPE,
        PODCAST_CATEGORY_ID,
        PODCAST_AUTHOR_ID,
        CHURCH_NAME,
    )
    CONFIG_LOADED = True
except ImportError:
    CONFIG_LOADED = False
    # Defaults for standalone operation
    EPISODES_DIR = Path("data/episodes")
    AUDIO_DIR = Path("audio")
    GUIDES_DIR = Path("guides")
    DATA_DIR = Path("data")
    WORDPRESS_URL = os.getenv("WORDPRESS_URL", "")
    WORDPRESS_USERNAME = os.getenv("WORDPRESS_USERNAME", "")
    WORDPRESS_APP_PASSWORD = os.getenv("WORDPRESS_APP_PASSWORD", "")
    WORDPRESS_POST_TYPE = os.getenv("WORDPRESS_POST_TYPE", "post")
    PODCAST_CATEGORY_ID = int(os.getenv("PODCAST_CATEGORY_ID", "1"))
    PODCAST_AUTHOR_ID = int(os.getenv("PODCAST_AUTHOR_ID", "1"))
    CHURCH_NAME = os.getenv("CHURCH_NAME", "Church")

# WordPress directory for reports
WORDPRESS_DIR = DATA_DIR / "wordpress" if CONFIG_LOADED else Path("data/wordpress")

# ---------------------------------------------------------------------------
# Logging Setup
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Custom Exceptions
# ---------------------------------------------------------------------------

class WordPressError(Exception):
    """Exception raised for WordPress API errors."""
    def __init__(self, endpoint: str, status_code: int, message: str):
        self.endpoint = endpoint
        self.status_code = status_code
        self.message = message
        super().__init__(f"WordPress API error ({status_code}) at {endpoint}: {message}")

# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------

def ensure_directories() -> None:
    """Create required directories if they don't exist."""
    Path(WORDPRESS_DIR).mkdir(parents=True, exist_ok=True)
    Path(EPISODES_DIR).mkdir(parents=True, exist_ok=True)


def load_json_file(filepath: Path) -> Optional[dict]:
    """Load a JSON file, return None if not found."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def save_json_file(filepath: Path, data: dict) -> None:
    """Save data to a JSON file."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, default=str)


def format_duration(seconds: int) -> str:
    """Format seconds as MM:SS or HH:MM:SS."""
    if not seconds:
        return "00:00"
    if seconds >= 3600:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        return f"{hours}:{minutes:02d}:{secs:02d}"
    else:
        minutes = seconds // 60
        secs = seconds % 60
        return f"{minutes}:{secs:02d}"


def sanitize_filename(filename: str) -> str:
    """Sanitize a filename for WordPress upload."""
    # Remove or replace problematic characters
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)
    filename = re.sub(r'\s+', '_', filename)
    return filename

# ---------------------------------------------------------------------------
# WordPress API Client
# ---------------------------------------------------------------------------

class WordPressClient:
    """Client for WordPress REST API interactions."""
    
    def __init__(
        self,
        url: str,
        username: str,
        app_password: str,
        post_type: str = "post"
    ):
        self.base_url = url.rstrip('/')
        self.api_url = f"{self.base_url}/wp-json/wp/v2"
        self.username = username
        self.app_password = app_password
        self.post_type = post_type
        self.session = requests.Session()
        
        # Set up authentication
        credentials = f"{username}:{app_password}"
        token = base64.b64encode(credentials.encode()).decode()
        self.session.headers.update({
            "Authorization": f"Basic {token}",
            "Content-Type": "application/json",
        })
    
    def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[dict] = None,
        files: Optional[dict] = None,
        params: Optional[dict] = None
    ) -> dict:
        """Make a request to the WordPress API."""
        url = f"{self.api_url}/{endpoint}"
        
        # Remove Content-Type header for file uploads
        headers = dict(self.session.headers)
        if files:
            del headers["Content-Type"]
        
        try:
            response = self.session.request(
                method=method,
                url=url,
                json=data if not files else None,
                files=files,
                params=params,
                headers=headers,
                timeout=120,  # 2 minutes for large uploads
            )
            
            if response.status_code >= 400:
                error_message = response.text
                try:
                    error_data = response.json()
                    error_message = error_data.get("message", error_message)
                except json.JSONDecodeError:
                    pass
                raise WordPressError(endpoint, response.status_code, error_message)
            
            return response.json()
            
        except requests.RequestException as e:
            raise WordPressError(endpoint, 0, str(e))
    
    def test_connection(self) -> bool:
        """Test the WordPress connection and authentication."""
        try:
            # Try to get current user info
            result = self._request("GET", "users/me")
            return True
        except WordPressError:
            return False
    
    def get_user_info(self) -> dict:
        """Get information about the authenticated user."""
        return self._request("GET", "users/me")
    
    def upload_media(
        self,
        filepath: Path,
        title: Optional[str] = None,
        alt_text: Optional[str] = None
    ) -> dict:
        """
        Upload a file to the WordPress media library.
        
        Returns:
            dict: Media object with id, source_url, etc.
        """
        if not filepath.exists():
            raise FileNotFoundError(f"File not found: {filepath}")
        
        # Determine MIME type
        mime_type, _ = mimetypes.guess_type(str(filepath))
        if not mime_type:
            mime_type = "application/octet-stream"
        
        # Prepare file for upload
        filename = sanitize_filename(filepath.name)
        
        with open(filepath, 'rb') as f:
            files = {
                'file': (filename, f, mime_type)
            }
            
            # Set headers for file upload
            headers = {
                "Authorization": self.session.headers["Authorization"],
                "Content-Disposition": f'attachment; filename="{filename}"',
            }
            
            url = f"{self.api_url}/media"
            
            response = requests.post(
                url,
                files=files,
                headers=headers,
                timeout=300,  # 5 minutes for large files
            )
            
            if response.status_code >= 400:
                error_message = response.text
                try:
                    error_data = response.json()
                    error_message = error_data.get("message", error_message)
                except json.JSONDecodeError:
                    pass
                raise WordPressError("media", response.status_code, error_message)
            
            media = response.json()
        
        # Update title and alt text if provided
        if title or alt_text:
            update_data = {}
            if title:
                update_data["title"] = title
            if alt_text:
                update_data["alt_text"] = alt_text
            
            media = self._request("POST", f"media/{media['id']}", data=update_data)
        
        return media
    
    def get_post_endpoint(self) -> str:
        """Get the correct endpoint for the post type."""
        if self.post_type == "post":
            return "posts"
        elif self.post_type == "page":
            return "pages"
        else:
            # Custom post type
            return self.post_type
    
    def create_post(
        self,
        title: str,
        content: str,
        excerpt: str = "",
        status: str = "publish",
        categories: list[int] = None,
        tags: list[str] = None,
        author: int = None,
        meta: dict = None,
        featured_media: int = None,
    ) -> dict:
        """
        Create a new post.
        
        Returns:
            dict: Created post object
        """
        endpoint = self.get_post_endpoint()
        
        data = {
            "title": title,
            "content": content,
            "status": status,
        }
        
        if excerpt:
            data["excerpt"] = excerpt
        
        if categories:
            data["categories"] = categories
        
        if tags:
            # Tags need to be created/looked up first, or we can use tag names
            # For simplicity, we'll skip tags for now (would need additional API calls)
            pass
        
        if author:
            data["author"] = author
        
        if meta:
            data["meta"] = meta
        
        if featured_media:
            data["featured_media"] = featured_media
        
        return self._request("POST", endpoint, data=data)
    
    def update_post(self, post_id: int, **kwargs) -> dict:
        """Update an existing post."""
        endpoint = f"{self.get_post_endpoint()}/{post_id}"
        return self._request("POST", endpoint, data=kwargs)
    
    def get_post(self, post_id: int) -> dict:
        """Get a post by ID."""
        endpoint = f"{self.get_post_endpoint()}/{post_id}"
        return self._request("GET", endpoint)
    
    def find_post_by_meta(self, meta_key: str, meta_value: str) -> Optional[dict]:
        """Find a post by custom field value."""
        endpoint = self.get_post_endpoint()
        params = {
            "meta_key": meta_key,
            "meta_value": meta_value,
            "per_page": 1,
        }
        
        try:
            results = self._request("GET", endpoint, params=params)
            if results and len(results) > 0:
                return results[0]
        except WordPressError:
            pass
        
        return None

# ---------------------------------------------------------------------------
# Post Content Generation
# ---------------------------------------------------------------------------

def generate_post_content(episode: dict) -> str:
    """
    Generate the HTML content for a podcast post.
    
    Includes:
    - Audio player embed
    - Summary
    - Scripture focus
    - Big idea
    - Discussion questions
    - YouTube video embed
    - Download links
    """
    video_id = episode.get("video_id", "")
    title = episode.get("title", "Sermon")
    ai_content = episode.get("ai_content", {})
    
    # Get content fields
    summary = ai_content.get("summary", "")
    big_idea = ai_content.get("big_idea", "")
    primary_scripture = ai_content.get("primary_scripture", {})
    supporting_scriptures = ai_content.get("supporting_scriptures", [])
    topics = ai_content.get("topics", [])
    
    # Get discussion guide content if available
    discussion = {}
    ai_content_file = Path(f"data/ai_content/{video_id}_ai_content.json")
    if ai_content_file.exists():
        full_ai_content = load_json_file(ai_content_file)
        if full_ai_content:
            discussion = full_ai_content.get("discussion_guide", {})
    
    # Build HTML content
    sections = []
    
    # Audio player placeholder (will be replaced with actual URL)
    sections.append(f"""
<!-- Audio Player -->
<div class="podcast-audio-player">
    [audio_player]
</div>
""")
    
    # Summary
    if summary:
        sections.append(f"""
<!-- Summary -->
<div class="podcast-summary">
    <p>{summary}</p>
</div>
""")
    
    # Scripture Focus
    if primary_scripture:
        ref = primary_scripture.get("reference", "")
        text = primary_scripture.get("text", "")
        if ref:
            sections.append(f"""
<!-- Scripture Focus -->
<div class="podcast-scripture">
    <h3>📖 Scripture Focus</h3>
    <blockquote>
        <strong>{ref}</strong>
        {f'<p>{text}</p>' if text else ''}
    </blockquote>
</div>
""")
    
    # Big Idea
    if big_idea:
        sections.append(f"""
<!-- The Big Idea -->
<div class="podcast-big-idea">
    <h3>💡 The Big Idea</h3>
    <p><em>{big_idea}</em></p>
</div>
""")
    
    # Discussion Questions
    questions = discussion.get("questions", [])
    if questions:
        questions_html = "\n".join([f"    <li>{q}</li>" for q in questions])
        sections.append(f"""
<!-- Discussion Questions -->
<div class="podcast-discussion">
    <h3>💬 Discussion Questions</h3>
    <ol>
{questions_html}
    </ol>
</div>
""")
    
    # Application
    application = discussion.get("application", "")
    if application:
        sections.append(f"""
<!-- This Week's Challenge -->
<div class="podcast-application">
    <h3>🎯 This Week's Challenge</h3>
    <p>{application}</p>
</div>
""")
    
    # Prayer Points
    prayer_points = discussion.get("prayer_points", [])
    if prayer_points:
        prayer_html = "\n".join([f"    <li>{p}</li>" for p in prayer_points])
        sections.append(f"""
<!-- Prayer Focus -->
<div class="podcast-prayer">
    <h3>🙏 Prayer Focus</h3>
    <ul>
{prayer_html}
    </ul>
</div>
""")
    
    # Supporting Scriptures
    if supporting_scriptures:
        refs = ", ".join([s.get("reference", "") for s in supporting_scriptures if s.get("reference")])
        if refs:
            sections.append(f"""
<!-- Going Deeper -->
<div class="podcast-deeper">
    <h3>📚 Going Deeper</h3>
    <p>Related passages: {refs}</p>
</div>
""")
    
    # YouTube Video Embed
    youtube_url = episode.get("youtube_url", "")
    if youtube_url and video_id:
        sections.append(f"""
<!-- Video -->
<div class="podcast-video">
    <h3>🎬 Watch</h3>
    <iframe width="560" height="315" 
            src="https://www.youtube.com/embed/{video_id}" 
            frameborder="0" 
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" 
            allowfullscreen>
    </iframe>
</div>
""")
    
    # Discussion Guide Download
    guide_file = Path(f"guides/{video_id}_discussion_guide.pdf")
    if guide_file.exists():
        sections.append(f"""
<!-- Discussion Guide -->
<div class="podcast-guide">
    <h3>📄 Discussion Guide</h3>
    <p><a href="[discussion_guide_url]" class="button" download>Download Discussion Guide (PDF)</a></p>
</div>
""")
    
    # Topics/Tags
    if topics:
        topics_html = ", ".join(topics)
        sections.append(f"""
<!-- Topics -->
<div class="podcast-topics">
    <p><strong>Topics:</strong> {topics_html}</p>
</div>
""")
    
    return "\n".join(sections)


def generate_excerpt(episode: dict) -> str:
    """Generate post excerpt from AI summary."""
    ai_content = episode.get("ai_content", {})
    summary = ai_content.get("summary", "")
    
    if summary:
        return summary
    
    # Fallback to title
    return episode.get("title", "Sermon episode")

# ---------------------------------------------------------------------------
# Publishing Logic
# ---------------------------------------------------------------------------

def publish_episode(
    episode: dict,
    client: WordPressClient,
    status: str = "publish",
    update: bool = False,
    audio_url: Optional[str] = None,
    guide_url: Optional[str] = None,
    dry_run: bool = False,
    quiet: bool = False,
) -> dict:
    """
    Publish a single episode to WordPress.
    
    Returns:
        dict: Publishing result with post info
    """
    video_id = episode.get("video_id", "")
    title = episode.get("title", f"Sermon {video_id}")
    
    result = {
        "video_id": video_id,
        "success": False,
        "post_id": None,
        "post_url": None,
        "audio_uploaded": False,
        "audio_url": None,
        "guide_uploaded": False,
        "guide_url": None,
        "error": None,
    }
    
    if not quiet:
        logger.info(f"Publishing: {title}")
    
    if dry_run:
        if not quiet:
            logger.info("  [DRY RUN] Would upload audio and create post")
        result["success"] = True
        return result
    
    try:
        # Step 1: Upload audio file (if not using external URL)
        if not audio_url:
            audio_file = AUDIO_DIR / f"{video_id}.mp3"
            if audio_file.exists():
                if not quiet:
                    logger.info(f"  Uploading audio: {audio_file.name}")
                
                media = client.upload_media(
                    filepath=audio_file,
                    title=f"{title} - Audio",
                )
                audio_url = media.get("source_url")
                result["audio_uploaded"] = True
                result["audio_url"] = audio_url
                
                if not quiet:
                    logger.info(f"  Audio uploaded: {audio_url}")
            else:
                if not quiet:
                    logger.warning(f"  Audio file not found: {audio_file}")
        else:
            result["audio_url"] = audio_url
        
        # Step 2: Upload discussion guide PDF
        if not guide_url:
            guide_file = GUIDES_DIR / f"{video_id}_discussion_guide.pdf"
            if guide_file.exists():
                if not quiet:
                    logger.info(f"  Uploading guide: {guide_file.name}")
                
                media = client.upload_media(
                    filepath=guide_file,
                    title=f"{title} - Discussion Guide",
                )
                guide_url = media.get("source_url")
                result["guide_uploaded"] = True
                result["guide_url"] = guide_url
            else:
                if not quiet:
                    logger.info(f"  No discussion guide found")
        else:
            result["guide_url"] = guide_url
        
        # Step 3: Generate post content
        content = generate_post_content(episode)
        
        # Replace placeholders with actual URLs
        if audio_url:
            # Create audio player HTML
            audio_player = f'<audio controls src="{audio_url}" preload="metadata"></audio>'
            content = content.replace("[audio_player]", audio_player)
        else:
            content = content.replace("[audio_player]", "<p><em>Audio coming soon</em></p>")
        
        if guide_url:
            content = content.replace("[discussion_guide_url]", guide_url)
        
        # Generate excerpt
        excerpt = generate_excerpt(episode)
        
        # Build custom meta fields
        meta = {
            "video_id": video_id,
            "youtube_url": episode.get("youtube_url", ""),
            "duration_seconds": episode.get("duration_seconds", 0),
            "duration_formatted": episode.get("duration_formatted", ""),
        }
        
        if audio_url:
            meta["audio_url"] = audio_url
        
        # Add scripture reference
        ai_content = episode.get("ai_content", {})
        primary_scripture = ai_content.get("primary_scripture", {})
        if primary_scripture:
            meta["primary_scripture"] = primary_scripture.get("reference", "")
        
        # Step 4: Create or update post
        if update and episode.get("wordpress", {}).get("post_id"):
            # Update existing post
            post_id = episode["wordpress"]["post_id"]
            if not quiet:
                logger.info(f"  Updating post {post_id}...")
            
            post = client.update_post(
                post_id=post_id,
                title=title,
                content=content,
                excerpt=excerpt,
                status=status,
                meta=meta,
            )
        else:
            # Create new post
            if not quiet:
                logger.info(f"  Creating post...")
            
            post = client.create_post(
                title=title,
                content=content,
                excerpt=excerpt,
                status=status,
                categories=[PODCAST_CATEGORY_ID] if PODCAST_CATEGORY_ID else None,
                author=PODCAST_AUTHOR_ID if PODCAST_AUTHOR_ID else None,
                meta=meta,
            )
        
        result["success"] = True
        result["post_id"] = post.get("id")
        result["post_url"] = post.get("link")
        
        if not quiet:
            logger.info(f"  ✓ Published: {result['post_url']}")
        
    except WordPressError as e:
        result["error"] = str(e)
        if not quiet:
            logger.error(f"  ✗ Failed: {e}")
    except Exception as e:
        result["error"] = str(e)
        if not quiet:
            logger.error(f"  ✗ Error: {e}")
    
    return result


def update_episode_with_wordpress(episode_file: Path, publish_result: dict) -> None:
    """Update the episode JSON file with WordPress post information."""
    episode = load_json_file(episode_file)
    if not episode:
        return
    
    episode["wordpress"] = {
        "published": publish_result.get("success", False),
        "post_id": publish_result.get("post_id"),
        "post_url": publish_result.get("post_url"),
        "audio_url": publish_result.get("audio_url"),
        "guide_url": publish_result.get("guide_url"),
        "published_at": datetime.now().isoformat() if publish_result.get("success") else None,
    }
    
    save_json_file(episode_file, episode)

# ---------------------------------------------------------------------------
# Input Handling
# ---------------------------------------------------------------------------

def find_episode_file(video_id: str) -> Optional[Path]:
    """Find the episode JSON file for a video ID."""
    episode_file = EPISODES_DIR / f"{video_id}_episode.json"
    if episode_file.exists():
        return episode_file
    return None


def find_unpublished_episodes() -> list[Path]:
    """Find all episode files that haven't been published to WordPress."""
    unpublished = []
    
    for episode_file in EPISODES_DIR.glob("*_episode.json"):
        episode = load_json_file(episode_file)
        if episode:
            wordpress = episode.get("wordpress", {})
            if not wordpress.get("published"):
                unpublished.append(episode_file)
    
    return unpublished


def generate_publish_report(results: list[dict]) -> dict:
    """Generate a summary report for publishing."""
    successful = [r for r in results if r.get("success")]
    failed = [r for r in results if not r.get("success")]
    
    report = {
        "generated_at": datetime.now().isoformat(),
        "summary": {
            "total": len(results),
            "successful": len(successful),
            "failed": len(failed),
        },
        "published": [
            {
                "video_id": r["video_id"],
                "post_id": r.get("post_id"),
                "post_url": r.get("post_url"),
            }
            for r in successful
        ],
        "failed": [
            {
                "video_id": r["video_id"],
                "error": r.get("error"),
            }
            for r in failed
        ],
    }
    
    return report

# ---------------------------------------------------------------------------
# CLI Interface
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="PreachCaster WordPress Publisher - Publish podcast episodes to WordPress",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --video-id abc123xyz              Publish single episode
  %(prog)s --episode-file episode.json       Publish from episode file
  %(prog)s --all                             Publish all unpublished episodes
  %(prog)s --video-id abc123 --update        Update existing post
  %(prog)s --video-id abc123 --dry-run       Test without publishing
  %(prog)s --video-id abc123 --status draft  Publish as draft

WordPress credentials should be set in environment or .env file:
  WORDPRESS_URL=https://your-site.com
  WORDPRESS_USERNAME=your_username
  WORDPRESS_APP_PASSWORD=xxxx xxxx xxxx xxxx
        """
    )
    
    # Input options
    input_group = parser.add_argument_group("Input Options")
    input_group.add_argument(
        "--video-id",
        help="Video ID to publish"
    )
    input_group.add_argument(
        "--episode-file",
        help="Path to episode JSON file"
    )
    input_group.add_argument(
        "--all",
        action="store_true",
        help="Publish all unpublished episodes"
    )
    
    # WordPress options
    wp_group = parser.add_argument_group("WordPress Options")
    wp_group.add_argument(
        "--wordpress-url",
        help="WordPress site URL (overrides config)"
    )
    wp_group.add_argument(
        "--post-type",
        default="post",
        help="WordPress post type (default: post)"
    )
    wp_group.add_argument(
        "--status",
        choices=["publish", "draft", "pending", "private"],
        default="publish",
        help="Post status (default: publish)"
    )
    wp_group.add_argument(
        "--update",
        action="store_true",
        help="Update existing post instead of creating new"
    )
    
    # Media options
    media_group = parser.add_argument_group("Media Options")
    media_group.add_argument(
        "--audio-url",
        help="External audio URL (skip upload)"
    )
    media_group.add_argument(
        "--guide-url",
        help="External discussion guide URL (skip upload)"
    )
    
    # Output options
    output_group = parser.add_argument_group("Output Options")
    output_group.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without publishing"
    )
    output_group.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON"
    )
    output_group.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Minimal output"
    )
    
    return parser.parse_args()


def main() -> int:
    """Main entry point."""
    args = parse_args()
    
    # Set up logging
    if args.quiet:
        logging.getLogger().setLevel(logging.WARNING)
    
    # Ensure directories exist
    ensure_directories()
    
    # Get WordPress configuration
    wp_url = args.wordpress_url or WORDPRESS_URL
    wp_username = WORDPRESS_USERNAME
    wp_password = WORDPRESS_APP_PASSWORD
    wp_post_type = args.post_type or WORDPRESS_POST_TYPE
    
    # Validate WordPress credentials
    if not wp_url or not wp_username or not wp_password:
        if args.json:
            print(json.dumps({
                "error": "WordPress credentials not configured",
                "help": "Set WORDPRESS_URL, WORDPRESS_USERNAME, WORDPRESS_APP_PASSWORD"
            }))
        else:
            logger.error("WordPress credentials not configured")
            logger.error("Set environment variables: WORDPRESS_URL, WORDPRESS_USERNAME, WORDPRESS_APP_PASSWORD")
        return 1
    
    # Create WordPress client
    client = WordPressClient(
        url=wp_url,
        username=wp_username,
        app_password=wp_password,
        post_type=wp_post_type,
    )
    
    # Test connection (unless dry run)
    if not args.dry_run:
        if not args.quiet and not args.json:
            logger.info(f"Connecting to {wp_url}...")
        
        if not client.test_connection():
            if args.json:
                print(json.dumps({"error": "WordPress authentication failed"}))
            else:
                logger.error("WordPress authentication failed")
                logger.error("Check username and application password")
            return 1
        
        if not args.quiet and not args.json:
            logger.info("✓ Connected to WordPress")
    
    # Determine episodes to publish
    episodes_to_publish = []
    
    if args.video_id:
        episode_file = find_episode_file(args.video_id)
        if episode_file:
            episodes_to_publish.append(episode_file)
        else:
            # Try to build minimal episode from available data
            episode = {
                "video_id": args.video_id,
                "title": f"Sermon {args.video_id}",
                "youtube_url": f"https://www.youtube.com/watch?v={args.video_id}",
                "ai_content": {},
            }
            episodes_to_publish.append(("inline", episode))
    
    elif args.episode_file:
        episode_file = Path(args.episode_file)
        if episode_file.exists():
            episodes_to_publish.append(episode_file)
        else:
            if args.json:
                print(json.dumps({"error": f"Episode file not found: {episode_file}"}))
            else:
                logger.error(f"Episode file not found: {episode_file}")
            return 1
    
    elif args.all:
        episodes_to_publish = find_unpublished_episodes()
        if not episodes_to_publish:
            if args.json:
                print(json.dumps({"message": "No unpublished episodes found"}))
            else:
                logger.info("No unpublished episodes found")
            return 0
    
    else:
        if args.json:
            print(json.dumps({"error": "No input specified. Use --video-id, --episode-file, or --all"}))
        else:
            logger.error("No input specified. Use --video-id, --episode-file, or --all")
        return 1
    
    if not args.quiet and not args.json:
        logger.info(f"Publishing {len(episodes_to_publish)} episode(s)")
        if args.dry_run:
            logger.info("[DRY RUN MODE]")
        print()
    
    # Publish episodes
    results = []
    
    for item in episodes_to_publish:
        if isinstance(item, tuple) and item[0] == "inline":
            # Inline episode data
            episode = item[1]
            episode_file = None
        else:
            # Load from file
            episode_file = item
            episode = load_json_file(episode_file)
            if not episode:
                results.append({
                    "video_id": episode_file.stem.replace("_episode", ""),
                    "success": False,
                    "error": "Failed to load episode file",
                })
                continue
        
        result = publish_episode(
            episode=episode,
            client=client,
            status=args.status,
            update=args.update,
            audio_url=args.audio_url,
            guide_url=args.guide_url,
            dry_run=args.dry_run,
            quiet=args.quiet or args.json,
        )
        results.append(result)
        
        # Update episode file with WordPress info
        if episode_file and result["success"] and not args.dry_run:
            update_episode_with_wordpress(episode_file, result)
    
    # Generate report
    report = generate_publish_report(results)
    
    # Save report (unless dry run)
    if not args.dry_run:
        report_file = WORDPRESS_DIR / "publish_report.json"
        save_json_file(report_file, report)
    
    # Output results
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print()
        logger.info("=" * 60)
        logger.info("Publishing Summary")
        logger.info("=" * 60)
        logger.info(f"Total:      {report['summary']['total']}")
        logger.info(f"Successful: {report['summary']['successful']}")
        logger.info(f"Failed:     {report['summary']['failed']}")
        
        if report["published"]:
            print()
            logger.info("Published posts:")
            for pub in report["published"]:
                logger.info(f"  {pub['video_id']}: {pub['post_url']}")
        
        if report["failed"]:
            print()
            logger.warning("Failed:")
            for fail in report["failed"]:
                logger.warning(f"  {fail['video_id']}: {fail['error']}")
    
    # Return exit code
    if report["summary"]["failed"] > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
