# CW08 Prompt: PreachCaster Pipeline Orchestration & WordPress Publishing

**Project:** PreachCaster  
**Context Window:** CW08  
**Objective:** Build pipeline orchestration and WordPress publishing scripts

---

## Context for Claude

You are continuing development of PreachCaster, an automated sermon podcasting platform for churches. Review the Project Bible and previous CW summaries for full context.

**Quick Summary:**
- PreachCaster monitors YouTube for new sermon uploads
- Automatically extracts audio, processes transcripts, generates AI content
- Publishes to WordPress with RSS feeds for podcast platforms
- Enables semantic search across all sermon content

**Tech Stack:** Python, Flask, OpenAI, Pinecone, yt-dlp, WordPress

**CW07 Accomplishments:**
- Created `07_generate_ai_content_v1.py` (AI content generation from transcripts)
- Created `08_generate_discussion_guide_v1.py` (PDF discussion guide generation)
- Full unit test coverage (66 tests total)
- Dry-run mode for cost estimation
- Church branding support for PDFs

---

## CW08 Goal

Build the orchestration and publishing scripts that tie everything together. By the end of this session, we should have working scripts for:

1. **09_full_pipeline_v1.py** - Orchestrate all scripts for single video end-to-end
2. **10_wordpress_publish_v1.py** - Publish podcast episodes to WordPress via REST API

These scripts complete the automation layer that makes PreachCaster "zero-touch" after YouTube upload.

---

## Script 9: 09_full_pipeline_v1.py

### Purpose
Orchestrate the complete processing pipeline for a single video, from YouTube detection through AI content generation. This is the "master" script that coordinates all individual processing steps.

### Requirements

**Input:**
- YouTube video ID (single video)
- Or list of video IDs
- Or path to `new_videos.json` from script 01

**Output:**
- All intermediate files from each pipeline step
- `data/episodes/{video_id}_episode.json` - Complete episode package
- `data/pipeline/pipeline_report.json` - Processing report with timing/status

**Pipeline Steps to Orchestrate:**
```
Step 1: Extract Audio (02_extract_audio_v1.py)
        └── Output: audio/{video_id}.mp3

Step 2: Fetch Transcript (03_fetch_transcript_v1.py)
        └── Output: data/transcripts/{video_id}.json

Step 3: Chunk Transcript (04_chunk_transcript_v1.py)
        └── Output: data/chunks/{video_id}_chunks.json

Step 4: Generate Embeddings (05_generate_embeddings_v1.py)
        └── Output: data/embeddings/{video_id}_embeddings.json

Step 5: Upload to Pinecone (06_upload_pinecone_v1.py)
        └── Output: Vectors in Pinecone

Step 6: Generate AI Content (07_generate_ai_content_v1.py)
        └── Output: data/ai_content/{video_id}_ai_content.json

Step 7: Generate Discussion Guide (08_generate_discussion_guide_v1.py)
        └── Output: guides/{video_id}_discussion_guide.pdf
```

**Functionality:**
1. Accept video ID(s) as input
2. Run each pipeline step in sequence
3. Track success/failure of each step
4. Support resuming from failed step (--resume)
5. Support running specific steps only (--steps 1,2,3)
6. Calculate total processing time
7. Generate comprehensive episode package JSON
8. Support dry-run mode (show what would be done)
9. Parallel processing option for multiple videos (--parallel)

**CLI Interface:**
```bash
# Process single video through full pipeline
python 09_full_pipeline_v1.py --video-id abc123xyz

# Process multiple videos
python 09_full_pipeline_v1.py --video-ids abc123,def456,ghi789

# Process from new_videos.json
python 09_full_pipeline_v1.py --from-file data/video_ids/new_videos.json

# Auto-detect input
python 09_full_pipeline_v1.py

# Run specific steps only
python 09_full_pipeline_v1.py --video-id abc123 --steps 1,2,3

# Skip certain steps
python 09_full_pipeline_v1.py --video-id abc123 --skip-steps 4,5

# Resume from last failure
python 09_full_pipeline_v1.py --video-id abc123 --resume

# Dry run
python 09_full_pipeline_v1.py --video-id abc123 --dry-run

# Force re-process all steps
python 09_full_pipeline_v1.py --video-id abc123 --force

# Parallel processing (multiple videos)
python 09_full_pipeline_v1.py --from-file new_videos.json --parallel 3

# JSON output
python 09_full_pipeline_v1.py --video-id abc123 --json
```

**Episode Package Format (episode.json):**
```json
{
  "video_id": "abc123xyz",
  "title": "Finding Peace in Anxious Times",
  "youtube_url": "https://www.youtube.com/watch?v=abc123xyz",
  "published_at": "2025-01-05T10:00:00Z",
  "duration_seconds": 2700,
  "duration_formatted": "45:00",
  
  "files": {
    "audio": "audio/abc123xyz.mp3",
    "transcript_json": "data/transcripts/abc123xyz.json",
    "transcript_txt": "data/transcripts/abc123xyz.txt",
    "chunks": "data/chunks/abc123xyz_chunks.json",
    "embeddings": "data/embeddings/abc123xyz_embeddings.json",
    "ai_content": "data/ai_content/abc123xyz_ai_content.json",
    "discussion_guide": "guides/abc123xyz_discussion_guide.pdf"
  },
  
  "ai_content": {
    "summary": "Pastor explores how to find lasting peace...",
    "big_idea": "Peace isn't the absence of storms...",
    "primary_scripture": {"reference": "Philippians 4:6-7", "text": "..."},
    "supporting_scriptures": [...],
    "topics": ["peace", "anxiety", "prayer"]
  },
  
  "search": {
    "indexed": true,
    "pinecone_namespace": "crossconnection",
    "chunk_count": 24,
    "vector_count": 24
  },
  
  "processing": {
    "started_at": "2025-01-05T12:00:00Z",
    "completed_at": "2025-01-05T12:05:30Z",
    "duration_seconds": 330,
    "steps_completed": ["audio", "transcript", "chunks", "embeddings", "pinecone", "ai_content", "guide"],
    "costs": {
      "embeddings_usd": 0.00025,
      "ai_content_usd": 0.002,
      "total_usd": 0.00225
    }
  },
  
  "wordpress": {
    "published": false,
    "post_id": null,
    "post_url": null
  }
}
```

### Key Considerations

**Error Handling:**
- Each step should be wrapped in try/except
- Failed steps should be logged with error details
- Pipeline should support resume from failure point
- Consider retry logic for transient failures (network, API rate limits)

**Step Dependencies:**
```
audio ─────────────────────────────────────────────────┐
                                                       │
transcript ──┬── chunks ── embeddings ── pinecone      │
             │                                         │
             └── ai_content ── discussion_guide        │
                                                       │
episode.json ◄─────────────────────────────────────────┘
```

**Performance:**
- Audio extraction: ~1-2 min for 45-min video
- Transcript fetch: ~5-10 sec
- Chunking: ~1 sec
- Embeddings: ~30 sec (API calls)
- Pinecone upload: ~5 sec
- AI content: ~10-30 sec (API call)
- PDF generation: ~1 sec
- **Total: ~3-5 minutes per video**

---

## Script 10: 10_wordpress_publish_v1.py

### Purpose
Publish processed podcast episodes to WordPress via the REST API. This creates the podcast post, uploads audio, and updates the RSS feed.

### Requirements

**Input:**
- Episode package JSON (from script 09)
- Or video ID (will look for episode.json)
- WordPress credentials from config

**Output:**
- WordPress post created/updated
- Audio file uploaded to WordPress media library
- Episode package updated with WordPress post info
- `data/wordpress/publish_report.json` - Publishing report

**Functionality:**
1. Load episode package JSON
2. Authenticate with WordPress REST API
3. Upload audio file to media library (if not already uploaded)
4. Create/update podcast post with:
   - Title, date, content
   - Audio file attachment
   - Transcript (in expandable section or separate tab)
   - YouTube video embed
   - AI-generated summary
   - Scripture references
   - Topic tags
   - Discussion guide download link
5. Verify RSS feed includes new episode
6. Update episode.json with WordPress post details

**CLI Interface:**
```bash
# Publish single episode
python 10_wordpress_publish_v1.py --video-id abc123xyz

# Publish from episode.json
python 10_wordpress_publish_v1.py --from-file data/episodes/abc123xyz_episode.json

# Publish multiple episodes
python 10_wordpress_publish_v1.py --video-ids abc123,def456

# Publish all unpublished episodes
python 10_wordpress_publish_v1.py --unpublished

# Update existing post
python 10_wordpress_publish_v1.py --video-id abc123 --update

# Dry run (validate without publishing)
python 10_wordpress_publish_v1.py --video-id abc123 --dry-run

# Custom post status
python 10_wordpress_publish_v1.py --video-id abc123 --status draft

# Skip audio upload (use existing URL)
python 10_wordpress_publish_v1.py --video-id abc123 --audio-url "https://..."

# JSON output
python 10_wordpress_publish_v1.py --video-id abc123 --json
```

**WordPress Post Structure:**
```html
<!-- Podcast Episode Post Content -->

<div class="sermon-player">
  [audio mp3="https://church.com/wp-content/uploads/abc123xyz.mp3"]
</div>

<div class="sermon-video">
  <iframe src="https://www.youtube.com/embed/abc123xyz" ...></iframe>
</div>

<div class="sermon-summary">
  <h3>Summary</h3>
  <p>Pastor explores how to find lasting peace in anxious times...</p>
</div>

<div class="sermon-scripture">
  <h3>Scripture Focus</h3>
  <p><strong>Philippians 4:6-7</strong></p>
  <blockquote>Do not be anxious about anything...</blockquote>
</div>

<div class="sermon-big-idea">
  <h3>The Big Idea</h3>
  <p class="big-idea">Peace isn't the absence of storms, but the presence of God...</p>
</div>

<div class="sermon-resources">
  <h3>Resources</h3>
  <ul>
    <li><a href="/guides/abc123xyz_discussion_guide.pdf">Small Group Discussion Guide (PDF)</a></li>
    <li><a href="https://youtube.com/watch?v=abc123xyz">Watch on YouTube</a></li>
  </ul>
</div>

<details class="sermon-transcript">
  <summary>Full Transcript</summary>
  <div class="transcript-content">
    [Full transcript text...]
  </div>
</details>
```

**WordPress REST API Endpoints:**
```
POST   /wp-json/wp/v2/posts          - Create post
POST   /wp-json/wp/v2/media          - Upload media
GET    /wp-json/wp/v2/posts/{id}     - Get post
PUT    /wp-json/wp/v2/posts/{id}     - Update post
GET    /wp-json/wp/v2/tags           - Get/create tags
POST   /wp-json/wp/v2/tags           - Create tag
```

### Key Considerations

**Authentication:**
- Use Application Passwords (WordPress 5.6+)
- Store credentials in .env file
- Support both basic auth and JWT if needed

**Custom Post Type:**
- If using custom "podcast" post type, endpoint changes to `/wp-json/wp/v2/podcast`
- May need to register REST API support in WordPress plugin

**Media Handling:**
- Audio files can be large (50-100MB for hour-long sermon)
- Consider chunked upload for reliability
- Store media ID for future reference
- Support external audio hosting (S3, CDN) as alternative

**RSS Feed:**
- Verify podcast RSS feed updates after publishing
- May need to trigger cache clear
- Consider RSS feed validation after publish

**Error Handling:**
- WordPress API errors (auth, permissions, validation)
- Network timeouts for large uploads
- Duplicate detection (don't re-publish same episode)

---

## Documentation Requirements

Follow the same comprehensive header documentation pattern from previous scripts:

```python
#!/usr/bin/env python3
"""
09_full_pipeline_v1.py
Orchestrate complete video processing pipeline.

================================================================================
OVERVIEW
================================================================================
[...]
"""
```

---

## Config Imports Available

From `config/config.py`, these values should be available:

```python
# Paths
DATA_DIR = PROJECT_ROOT / "data"
AUDIO_DIR = PROJECT_ROOT / "audio"
GUIDES_DIR = PROJECT_ROOT / "guides"
EPISODES_DIR = DATA_DIR / "episodes"
PIPELINE_DIR = DATA_DIR / "pipeline"

# WordPress Settings
WORDPRESS_URL = "https://crossconnectionchurch.com"
WORDPRESS_API_URL = f"{WORDPRESS_URL}/wp-json/wp/v2"
WORDPRESS_USERNAME = os.getenv("WORDPRESS_USERNAME")
WORDPRESS_APP_PASSWORD = os.getenv("WORDPRESS_APP_PASSWORD")
WORDPRESS_POST_TYPE = "podcast"  # or "post" for standard posts

# Podcast Settings
PODCAST_CATEGORY_ID = 5  # WordPress category ID for podcasts
PODCAST_AUTHOR_ID = 1    # WordPress user ID for post author
```

---

## Dependencies

No new dependencies required. Uses:
- `requests` - HTTP client for WordPress API
- `subprocess` - For calling other pipeline scripts
- Standard library modules

---

## Success Criteria for CW08

By the end of this context window:

- [ ] `09_full_pipeline_v1.py` orchestrates all 7 pipeline steps
- [ ] `09_full_pipeline_v1.py` generates complete episode.json packages
- [ ] `09_full_pipeline_v1.py` supports resume from failure
- [ ] `09_full_pipeline_v1.py` tracks timing and costs
- [ ] `09_full_pipeline_v1.py` has dry-run mode
- [ ] `10_wordpress_publish_v1.py` authenticates with WordPress API
- [ ] `10_wordpress_publish_v1.py` uploads audio to media library
- [ ] `10_wordpress_publish_v1.py` creates podcast posts
- [ ] `10_wordpress_publish_v1.py` includes all content sections
- [ ] `10_wordpress_publish_v1.py` updates episode.json with post info
- [ ] Both scripts follow established documentation patterns
- [ ] Both scripts have working CLI interfaces

---

## Pipeline Integration

After CW08, the complete automated pipeline will be:

```
┌─────────────────────────────────────────────────────────────────────┐
│                        AV TEAM ACTION                               │
│                    Upload video to YouTube                          │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  01_monitor_youtube_v1.py                                           │
│  Detect new video → new_videos.json                                 │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  09_full_pipeline_v1.py  ◄── CW08                                   │
│                                                                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                 │
│  │ 02: Audio   │→ │ 03: Trans   │→ │ 04: Chunk   │                 │
│  └─────────────┘  └─────────────┘  └─────────────┘                 │
│                          │                │                         │
│                          ▼                ▼                         │
│                   ┌─────────────┐  ┌─────────────┐                 │
│                   │ 07: AI Gen  │  │ 05: Embed   │                 │
│                   └─────────────┘  └─────────────┘                 │
│                          │                │                         │
│                          ▼                ▼                         │
│                   ┌─────────────┐  ┌─────────────┐                 │
│                   │ 08: PDF     │  │ 06: Pine    │                 │
│                   └─────────────┘  └─────────────┘                 │
│                                                                     │
│  Output: episode.json (complete package)                            │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  10_wordpress_publish_v1.py  ◄── CW08                               │
│                                                                     │
│  Upload audio → Create post → Update RSS                            │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      AUTOMATIC OUTPUTS                              │
│                                                                     │
│  • Podcast live on website                                          │
│  • RSS feed updated (Apple, Spotify, etc.)                          │
│  • Searchable via semantic search                                   │
│  • Discussion guide available for download                          │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Out of Scope for CW08

- Flask search API server - CW09
- WordPress plugin development - CW09+
- Admin dashboard UI - CW10+
- Automated scheduling (cron/scheduler) - CW10+
- Multi-church tenant management - Future

---

## Testing Approach

### Script 09 Testing
- Unit tests for step orchestration logic
- Mock subprocess calls to avoid running real pipeline
- Test resume functionality with simulated failures
- Test episode.json generation

### Script 10 Testing
- Mock WordPress API responses
- Test authentication handling
- Test post content generation
- Test error handling for API failures
- Integration test with local WordPress (if available)

---

## Error Handling Strategy

### Script 09: Pipeline Errors
```python
class PipelineError(Exception):
    def __init__(self, step: str, video_id: str, error: str):
        self.step = step
        self.video_id = video_id
        self.error = error

# Save state for resume
state = {
    "video_id": "abc123",
    "completed_steps": ["audio", "transcript"],
    "failed_step": "chunks",
    "error": "...",
    "timestamp": "..."
}
# Save to data/pipeline/{video_id}_state.json
```

### Script 10: WordPress Errors
```python
class WordPressError(Exception):
    def __init__(self, endpoint: str, status_code: int, message: str):
        self.endpoint = endpoint
        self.status_code = status_code
        self.message = message

# Common errors:
# 401 - Authentication failed
# 403 - Permission denied
# 404 - Endpoint not found (wrong post type?)
# 413 - File too large
# 500 - Server error
```

---

## File Locations

Scripts should be created in:
```
/home/claude/preachcaster/_templates/tools/
├── 01_monitor_youtube_v1.py      (CW04)
├── 02_extract_audio_v1.py        (CW04)
├── 03_fetch_transcript_v1.py     (CW05)
├── 04_chunk_transcript_v1.py     (CW05)
├── 05_generate_embeddings_v1.py  (CW06)
├── 06_upload_pinecone_v1.py      (CW06)
├── 07_generate_ai_content_v1.py  (CW07)
├── 08_generate_discussion_guide_v1.py (CW07)
├── 09_full_pipeline_v1.py           ◄── NEW
├── 10_wordpress_publish_v1.py       ◄── NEW
└── versions/
```

---

## How to Start

1. Create `09_full_pipeline_v1.py` with orchestration logic
2. Implement subprocess-based step execution
3. Add resume/state management
4. Test with sample video data
5. Create `10_wordpress_publish_v1.py` with REST API client
6. Implement authentication and post creation
7. Test with mock WordPress responses
8. Verify integration between scripts 09 and 10

---

## Questions to Resolve in CW08

1. **Subprocess vs. import for running steps?**
   - **Recommendation:** Subprocess for isolation, easier error handling

2. **Parallel vs. sequential for multiple videos?**
   - **Recommendation:** Sequential by default, --parallel flag for opt-in

3. **WordPress custom post type or standard posts?**
   - **Recommendation:** Support both, configurable

4. **Audio hosting: WordPress media vs. external?**
   - **Recommendation:** WordPress media by default, external URL option

5. **How to handle WordPress plugin dependency?**
   - **Recommendation:** Script 10 works with standard WordPress, plugin adds features

---

## WordPress Setup Prerequisites

For testing script 10, the WordPress site needs:

1. **Application Password** enabled (WordPress 5.6+)
   - Users → Profile → Application Passwords
   - Generate password, store in .env

2. **REST API** accessible
   - Test: `curl https://site.com/wp-json/wp/v2/posts`

3. **Media uploads** allowed for user
   - User must have upload_files capability

4. **Optional: Custom Post Type**
   - If using custom "podcast" post type, ensure REST API support registered

---

*Ready to begin pipeline orchestration and WordPress publishing development.*
