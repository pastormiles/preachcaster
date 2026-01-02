# CW08 Summary: PreachCaster Pipeline Orchestration & WordPress Publishing

**Context Window:** CW08  
**Date:** January 1, 2025  
**Focus:** Pipeline orchestration and WordPress REST API publishing

---

## 1. Session Overview

This context window built the orchestration and publishing layer that completes the PreachCaster automation pipeline. These scripts tie together all previous work and enable true "zero-touch" operation after YouTube upload.

### Key Outcomes
- ✅ Created `09_full_pipeline_v1.py` - Master pipeline orchestrator
- ✅ Created `10_wordpress_publish_v1.py` - WordPress REST API publisher
- ✅ Comprehensive documentation following established patterns
- ✅ Full CLI interfaces with all required options
- ✅ Unit tests: 34 tests for script 09, 37 tests for script 10 (71 total)
- ✅ Dry-run mode for safe testing
- ✅ Resume capability for failed pipelines
- ✅ Episode package JSON generation

---

## 2. Scripts Created

### 09_full_pipeline_v1.py

**Location:** `_templates/tools/09_full_pipeline_v1.py`  
**Lines:** ~750  
**Purpose:** Orchestrate all 7 pipeline steps for sermon video processing

**Features:**
- Runs scripts 02-08 in sequence via subprocess
- Tracks timing and costs for each step
- Generates comprehensive episode.json packages
- Resume from failed step with --resume
- Run specific steps with --steps 1,2,3
- Skip steps with --skip-steps 4,5
- Parallel processing for multiple videos
- Dry-run mode for previewing actions
- Force re-processing with --force
- JSON output for automation

**Pipeline Steps:**
| Step | Script | Output |
|------|--------|--------|
| 1 | 02_extract_audio_v1.py | audio/{video_id}.mp3 |
| 2 | 03_fetch_transcript_v1.py | data/transcripts/{video_id}.json |
| 3 | 04_chunk_transcript_v1.py | data/chunks/{video_id}_chunks.json |
| 4 | 05_generate_embeddings_v1.py | data/embeddings/{video_id}_embeddings.json |
| 5 | 06_upload_pinecone_v1.py | Vectors in Pinecone |
| 6 | 07_generate_ai_content_v1.py | data/ai_content/{video_id}_ai_content.json |
| 7 | 08_generate_discussion_guide_v1.py | guides/{video_id}_discussion_guide.pdf |

**Output Files:**
- `data/episodes/{video_id}_episode.json` - Complete episode package
- `data/pipeline/{video_id}_state.json` - Pipeline state for resume
- `data/pipeline/pipeline_report.json` - Batch processing report

**Usage Examples:**
```bash
# Process single video through full pipeline
python 09_full_pipeline_v1.py --video-id abc123xyz

# Process from new_videos.json
python 09_full_pipeline_v1.py --from-file data/video_ids/new_videos.json

# Run specific steps only
python 09_full_pipeline_v1.py --video-id abc123 --steps 1,2,3

# Resume from failure
python 09_full_pipeline_v1.py --video-id abc123 --resume

# Parallel processing
python 09_full_pipeline_v1.py --from-file new_videos.json --parallel 3

# Dry run
python 09_full_pipeline_v1.py --video-id abc123 --dry-run
```

---

### 10_wordpress_publish_v1.py

**Location:** `_templates/tools/10_wordpress_publish_v1.py`  
**Lines:** ~700  
**Purpose:** Publish podcast episodes to WordPress via REST API

**Features:**
- WordPress REST API authentication (Application Passwords)
- Upload audio to WordPress media library
- Upload discussion guide PDFs
- Create/update podcast posts
- Rich post content with all sermon sections
- Support for custom post types
- Publish as draft, pending, or private
- Update existing posts
- External URL support (skip uploads)
- Dry-run mode for testing

**Post Content Includes:**
- Audio player embed
- AI-generated summary
- Scripture focus with styling
- Big idea callout
- Discussion questions
- Application challenge
- Prayer points
- YouTube video embed
- Discussion guide download link
- Topic tags

**Output Files:**
- `data/wordpress/publish_report.json` - Publishing report
- Episode JSON updated with post ID and URL

**Usage Examples:**
```bash
# Publish single episode
python 10_wordpress_publish_v1.py --video-id abc123xyz

# Publish from episode file
python 10_wordpress_publish_v1.py --episode-file data/episodes/abc123_episode.json

# Publish all unpublished episodes
python 10_wordpress_publish_v1.py --all

# Publish as draft
python 10_wordpress_publish_v1.py --video-id abc123 --status draft

# Update existing post
python 10_wordpress_publish_v1.py --video-id abc123 --update

# Dry run
python 10_wordpress_publish_v1.py --video-id abc123 --dry-run
```

---

## 3. Complete Pipeline Integration

After CW08, the full automated pipeline is:

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
│  Step 1: Extract Audio (02)    ──→ audio/{video_id}.mp3            │
│  Step 2: Fetch Transcript (03) ──→ data/transcripts/               │
│  Step 3: Chunk Transcript (04) ──→ data/chunks/                    │
│  Step 4: Generate Embeddings (05) ──→ data/embeddings/             │
│  Step 5: Upload to Pinecone (06)  ──→ Vector DB                    │
│  Step 6: Generate AI Content (07) ──→ data/ai_content/             │
│  Step 7: Generate Guide PDF (08)  ──→ guides/                      │
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

## 4. Episode Package Format

The `episode.json` generated by script 09:

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
    "step_timings": {...},
    "costs": {
      "embeddings_usd": 0.00025,
      "ai_content_usd": 0.002,
      "total_usd": 0.00225
    }
  },
  
  "wordpress": {
    "published": true,
    "post_id": 1234,
    "post_url": "https://church.com/podcast/finding-peace/",
    "audio_url": "https://church.com/wp-content/uploads/abc123xyz.mp3"
  }
}
```

---

## 5. WordPress Integration

### Authentication
Uses WordPress Application Passwords (not regular passwords):
- WordPress 5.6+ required
- Generate at: Users → Profile → Application Passwords

### Environment Variables
```bash
WORDPRESS_URL=https://crossconnectionchurch.com
WORDPRESS_USERNAME=your_username
WORDPRESS_APP_PASSWORD=xxxx xxxx xxxx xxxx xxxx xxxx
```

### Post Structure
The published post includes styled HTML sections:
1. Audio player with embedded MP3
2. Summary paragraph
3. Scripture focus (blockquote with reference)
4. Big idea callout
5. Discussion questions (numbered list)
6. Application challenge
7. Prayer focus (bullet points)
8. Supporting scriptures
9. YouTube video embed
10. Discussion guide download link
11. Topic tags

---

## 6. Testing Summary

### Script 09 Tests (34 tests)
- ✅ Helper functions (format_duration, load/save JSON)
- ✅ New videos file loading (list and dict formats)
- ✅ Pipeline state management (create, update success/failure)
- ✅ Step selection logic (all, specific, skip, resume)
- ✅ Pipeline step definitions (all 7 steps defined)
- ✅ Episode package generation
- ✅ Pipeline report generation
- ✅ CLI argument parsing
- ✅ Script path resolution
- ✅ PipelineError exception

### Script 10 Tests (37 tests)
- ✅ Helper functions (format_duration, sanitize_filename, load/save JSON)
- ✅ WordPressError exception
- ✅ WordPressClient initialization and auth
- ✅ Post endpoint resolution
- ✅ Post content generation
- ✅ Excerpt generation
- ✅ Episode file discovery
- ✅ Unpublished episode finding
- ✅ Publish report generation
- ✅ Episode update with WordPress info
- ✅ CLI argument parsing
- ✅ Dry run mode

---

## 7. Files Delivered

| File | Location | Purpose |
|------|----------|---------|
| `09_full_pipeline_v1.py` | `_templates/tools/` | Pipeline orchestrator |
| `10_wordpress_publish_v1.py` | `_templates/tools/` | WordPress publisher |
| `config.py` | `test_project/config/` | Test configuration |
| `new_videos.json` | `test_project/data/video_ids/` | Sample input |
| `test123xyz.json` | `test_project/data/transcripts/` | Sample transcript |
| `test123xyz_ai_content.json` | `test_project/data/ai_content/` | Sample AI content |
| `test123xyz_episode.json` | `test_project/data/episodes/` | Sample episode |
| `test_script_09.py` | `test_project/` | Unit tests (34 tests) |
| `test_script_10.py` | `test_project/` | Unit tests (37 tests) |

---

## 8. Directory Structure

```
preachcaster/
├── _templates/
│   └── tools/
│       ├── 01_monitor_youtube_v1.py     (CW04)
│       ├── 02_extract_audio_v1.py       (CW04)
│       ├── 03_fetch_transcript_v1.py    (CW05)
│       ├── 04_chunk_transcript_v1.py    (CW05)
│       ├── 05_generate_embeddings_v1.py (CW06)
│       ├── 06_upload_pinecone_v1.py     (CW06)
│       ├── 07_generate_ai_content_v1.py (CW07)
│       ├── 08_generate_discussion_guide_v1.py (CW07)
│       ├── 09_full_pipeline_v1.py       (CW08) ◄── NEW
│       ├── 10_wordpress_publish_v1.py   (CW08) ◄── NEW
│       └── versions/
│
└── test_project/
    ├── config/
    │   └── config.py
    ├── tools/
    │   ├── 09_full_pipeline_v1.py
    │   └── 10_wordpress_publish_v1.py
    ├── data/
    │   ├── video_ids/
    │   ├── transcripts/
    │   ├── chunks/
    │   ├── embeddings/
    │   ├── ai_content/
    │   ├── episodes/
    │   ├── pipeline/
    │   └── wordpress/
    ├── audio/
    ├── guides/
    ├── test_script_09.py
    └── test_script_10.py
```

---

## 9. Success Criteria Status

| Criterion | Status |
|-----------|--------|
| Script 09 orchestrates all 7 pipeline steps | ✅ Complete |
| Script 09 generates complete episode.json packages | ✅ Complete |
| Script 09 supports resume from failure | ✅ Complete |
| Script 09 tracks timing and costs | ✅ Complete |
| Script 09 has dry-run mode | ✅ Complete |
| Script 10 authenticates with WordPress API | ✅ Complete |
| Script 10 uploads audio to media library | ✅ Complete |
| Script 10 creates podcast posts | ✅ Complete |
| Script 10 includes all content sections | ✅ Complete |
| Script 10 updates episode.json with post info | ✅ Complete |
| Both scripts follow documentation patterns | ✅ Complete |
| Both scripts have working CLI interfaces | ✅ Complete |

---

## 10. Local Testing Instructions

```bash
# Navigate to project
cd ~/python/nomion/PreachCaster/[church_project]
source venv/bin/activate

# Test pipeline orchestration (dry run first)
python tools/09_full_pipeline_v1.py --video-id [video_id] --dry-run
python tools/09_full_pipeline_v1.py --video-id [video_id]

# Check episode package
cat data/episodes/[video_id]_episode.json

# Test WordPress publishing (dry run first)
export WORDPRESS_URL="https://your-site.com"
export WORDPRESS_USERNAME="your_user"
export WORDPRESS_APP_PASSWORD="xxxx xxxx xxxx xxxx"
python tools/10_wordpress_publish_v1.py --video-id [video_id] --dry-run
python tools/10_wordpress_publish_v1.py --video-id [video_id] --status draft
```

---

## 11. Open Items for CW09

### To Build Next
1. Flask search API server for semantic search
2. WordPress plugin for frontend integration
3. Search UI component

### Technical Considerations
- Flask API for semantic search queries
- WordPress shortcodes for search interface
- CORS configuration for cross-origin requests

---

## 12. Key Learnings

1. **Subprocess isolation works well** - Each step runs independently, easier error handling
2. **State management is crucial** - Pipeline state enables resume from failures
3. **Episode package is the contract** - Central data structure for all downstream uses
4. **Application Passwords are simpler** - No OAuth complexity for WordPress API
5. **Dry-run is essential** - Safe testing before real operations

---

## 13. Milestone Achieved: MVP Core Complete

With CW08, the core PreachCaster pipeline is functionally complete:

| Component | Status | CW |
|-----------|--------|-----|
| YouTube monitoring | ✅ | CW04 |
| Audio extraction | ✅ | CW04 |
| Transcript fetching | ✅ | CW05 |
| Transcript chunking | ✅ | CW05 |
| Embedding generation | ✅ | CW06 |
| Pinecone indexing | ✅ | CW06 |
| AI content generation | ✅ | CW07 |
| Discussion guide PDFs | ✅ | CW07 |
| Pipeline orchestration | ✅ | CW08 |
| WordPress publishing | ✅ | CW08 |

**Next: Search API and frontend integration (CW09)**

---

*Document created: CW08*  
*Next context window: CW09 — Search API & WordPress Plugin*
