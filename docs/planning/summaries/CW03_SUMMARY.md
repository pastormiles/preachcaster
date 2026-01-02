# CW03 Summary: PreachCaster Project Foundation

**Context Window:** CW03  
**Date:** December 31, 2024  
**Focus:** Architecture decisions, setup script creation, project scaffolding

---

## 1. Session Overview

This context window established the foundation for PreachCaster, focusing on architectural decisions and creating the project setup infrastructure. We analyzed existing YouTube AI Search pipeline code and adapted patterns for PreachCaster's automated sermon podcasting use case.

### Key Outcomes
- ✅ Decided on Python monolith architecture (vs Node.js or hybrid)
- ✅ Created comprehensive `preachcaster_setup_v1.sh` setup script
- ✅ Established directory structure and configuration patterns
- ✅ Defined 9-script pipeline for sermon processing
- ✅ Added YouTube playlist/podcast source flexibility

---

## 2. Architecture Decision: Python Monolith

### Options Evaluated

| Approach | Pros | Cons |
|----------|------|------|
| **Python Monolith** | Reuses existing code, single language, AI ecosystem | Slightly slower cold starts |
| **Node.js** | Fast async, quick cold starts | Rewrite everything, weaker AI libs |
| **Hybrid (Node + Python)** | Best of both worlds | Two codebases, complex communication |

### Decision: Python Monolith

**Rationale:**
1. Miles has working, tested Python code for transcripts, chunking, embeddings, Pinecone
2. AI/ML ecosystem is Python-first (OpenAI, Pinecone, LangChain)
3. Single language reduces maintenance burden for solo developer
4. Can refactor to hybrid later if scale demands it

**Design for Future Separation:**
- Services layer (`services/`) isolates business logic
- Could wrap in separate API and add Node.js frontend later
- Current workload (~200 sermons/month at 50 churches) doesn't justify complexity

---

## 3. YouTube Source Flexibility

Added support for three content source types:

| Source Type | Use Case | Configuration |
|-------------|----------|---------------|
| **Channel** | Monitor all uploads | Just channel ID |
| **Playlist** | Specific playlist (e.g., "Sunday Sermons") | Playlist ID + name |
| **Podcast** | YouTube's podcast feature | Podcast playlist ID |

This addresses the real-world need where churches may not want ALL YouTube videos converted to podcasts—only their sermon playlist.

---

## 4. Setup Script Created

### File: `preachcaster_setup_v1.sh`

**Location:** `~/python/nomion/PreachCaster/preachcaster_setup_v1.sh`

**Features:**
- Interactive prompts with sensible defaults
- YouTube source type selection (channel/playlist/podcast)
- Complete podcast metadata collection (for RSS feeds)
- Optional WordPress integration
- Generates all configuration files
- Creates venv and installs dependencies
- Checks for yt-dlp and ffmpeg

**Command-line Options:**
```bash
-h, --help          Show help
-n, --name          Church name (skip prompt)
-t, --templates     Templates directory
-f, --force         Overwrite existing files
-s, --skip-venv     Skip virtual environment
```

**Steps Performed:**
1. Church configuration (name, slug)
2. YouTube source configuration (channel/playlist/podcast)
3. Pinecone configuration (index, namespace)
4. Server configuration (port)
5. Podcast metadata (title, author, description, artwork, category)
6. WordPress integration (optional)
7. Create directory structure
8. Generate `config/config.py`
9. Generate `.env` and `.env.template`
10. Generate `requirements.txt`
11. Generate `.gitignore`
12. Generate `README.md`
13. Copy tools from `_templates/tools/`
14. Create virtual environment
15. Check external dependencies (yt-dlp, ffmpeg)

---

## 5. Directory Structure

```
~/python/nomion/PreachCaster/
├── preachcaster_setup_v1.sh          # Main setup script
├── _templates/
│   ├── config/                        # Config templates
│   └── tools/                         # Pipeline scripts
│       └── versions/                  # Archived old versions
│
└── [Generated Church Project]/        # e.g., Cross_Connection_Church/
    ├── config/
    │   └── config.py                  # All project settings
    ├── tools/                         # Pipeline scripts (copied from _templates)
    │   └── versions/
    ├── data/
    │   ├── video_ids/
    │   ├── metadata/
    │   ├── transcripts/
    │   ├── chunks/
    │   ├── embeddings/
    │   └── episodes/                  # Final episode packages
    ├── audio/                         # Extracted MP3 files
    ├── guides/                        # Discussion guide outputs
    ├── logs/
    ├── server/                        # Flask API (generated later)
    ├── wp-plugin/                     # WordPress plugin (generated later)
    ├── .env
    ├── requirements.txt
    ├── README.md
    └── venv/
```

---

## 6. Pipeline Scripts Defined

| # | Script | Purpose | Based On |
|---|--------|---------|----------|
| 01 | `01_monitor_youtube_v1.py` | RSS feed monitoring, detect new videos | New |
| 02 | `02_extract_audio_v1.py` | Extract MP3 via yt-dlp | New |
| 03 | `03_fetch_transcript_v1.py` | Get YouTube captions | Adapted from v10 |
| 04 | `04_chunk_transcript_v1.py` | Split into searchable chunks | Adapted from v2 |
| 05 | `05_generate_embeddings_v1.py` | Create OpenAI embeddings | Adapted from v2 |
| 06 | `06_upload_pinecone_v1.py` | Store in vector database | Adapted from v2 |
| 07 | `07_generate_ai_content_v1.py` | Summaries, scriptures, topics | New |
| 08 | `08_generate_discussion_guide_v1.py` | Small group study guide | New |
| 09 | `09_full_pipeline_v1.py` | Orchestrate all steps for one video | New |

---

## 7. Configuration Generated

### config/config.py Sections

| Section | Contents |
|---------|----------|
| Church Settings | Name, slug |
| YouTube Settings | Channel ID, source type, playlist/podcast IDs, RSS feed URL |
| Pinecone Settings | Index, namespace, batch size |
| Podcast Metadata | Title, author, description, artwork, category, language |
| WordPress Settings | URL, API key |
| Server Settings | Port, API keys, admin credentials, CORS |
| API Keys | YouTube, OpenAI, Pinecone, Webshare (from .env) |
| Directory Paths | All data directories as Path objects |
| Processing Settings | Chunking params, embedding model, AI model |
| Helper Functions | `ensure_directories()`, `validate_api_keys()`, `get_log_file()` |

---

## 8. Dependencies

### requirements.txt

```
# YouTube & Audio Processing
google-api-python-client>=2.100.0
youtube-transcript-api>=0.6.0
yt-dlp>=2024.1.0

# AI & Embeddings
openai>=1.0.0
pinecone>=5.0.0

# Data Processing
pandas>=2.0.0
python-dotenv>=1.0.0
tqdm>=4.65.0
feedparser>=6.0.0

# Server
flask>=3.0.0
flask-cors>=4.0.0
gunicorn>=21.0.0

# Utilities
requests>=2.31.0
python-dateutil>=2.8.0
```

### External Dependencies
- **yt-dlp**: Audio extraction from YouTube
- **ffmpeg**: Audio processing/conversion

---

## 9. Cross Connection Church Configuration

For initial testing:

| Setting | Value |
|---------|-------|
| Church Name | Cross Connection Church |
| Church Slug | crossconnection |
| YouTube Channel ID | UCDWgXIoyH3WNRxlB9N-gCOg |
| Pinecone Index | crossconnection-sermons |
| Server Port | 5005 |

---

## 10. Files Created This Session

| File | Location | Purpose |
|------|----------|---------|
| `preachcaster_setup_v1.sh` | `/PreachCaster/` | Main setup script |
| `_templates/tools/` | `/PreachCaster/_templates/` | Directory for tool scripts |
| `_templates/config/` | `/PreachCaster/_templates/` | Directory for config templates |

---

## 11. Existing Code Reviewed

Scripts from Miles' YouTube AI Search projects that will be adapted:

| Script | Key Patterns to Reuse |
|--------|----------------------|
| `01_extract_video_ids_v3.py` | Channel ID handling, video categorization, progress saving |
| `03_extract_transcripts_v10.py` | Webshare proxy integration, retry logic, progress tracking |
| `04_chunk_transcripts_v2.py` | Duration-based chunking, timestamp formatting, metadata enrichment |
| `05_generate_embeddings_v2.py` | Batch processing, cost estimation, incremental mode |
| `06_upload_to_pinecone_v2.py` | Namespace handling, metadata truncation, test search |
| `07_local_POC_v1.py` | Flask server generation, search API, admin dashboard |

---

## 12. Open Items for CW04

### To Build
1. `01_monitor_youtube_v1.py` - RSS feed monitoring
2. `02_extract_audio_v1.py` - yt-dlp audio extraction
3. Test scripts with Cross Connection Church channel

### Questions to Resolve
1. Should RSS monitoring support WebSub push notifications?
2. What audio quality/format is best for podcast distribution?
3. How to handle videos without captions (Whisper fallback)?

---

## 13. Key Learnings

1. **Playlist filtering is essential** - Churches don't want ALL videos, just sermons
2. **Python is the right choice** - Reuse existing code, stay in AI ecosystem
3. **Comprehensive setup pays off** - One script creates everything needed
4. **Documentation patterns matter** - Detailed headers make scripts self-documenting

---

## 14. Next Context Window (CW04)

**Focus:** Begin building pipeline scripts, starting with `01_monitor_youtube_v1.py`

**Goals:**
- Create YouTube RSS monitoring script
- Create audio extraction script  
- Test with Cross Connection Church channel
- Validate the full directory structure works

---

*Document created: CW03*  
*Next context window: CW04 — Pipeline Script Development*
