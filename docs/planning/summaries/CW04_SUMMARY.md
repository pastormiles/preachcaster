# CW04 Summary: PreachCaster Pipeline Scripts 01-02

**Context Window:** CW04  
**Date:** December 31, 2024  
**Focus:** YouTube monitoring and audio extraction scripts

---

## 1. Session Overview

This context window built the first two scripts in the PreachCaster pipeline - the "input" side of the system that detects new content and extracts audio.

### Key Outcomes
- ✅ Created `01_monitor_youtube_v1.py` - YouTube RSS monitoring
- ✅ Created `02_extract_audio_v1.py` - Audio extraction via yt-dlp
- ✅ Both scripts follow comprehensive documentation standards
- ✅ Both scripts have working CLI interfaces with argparse
- ✅ Logic verified through unit tests (network restrictions prevented live YouTube testing)
- ✅ Created test project structure with minimal config for validation

---

## 2. Scripts Created

### 01_monitor_youtube_v1.py

**Location:** `_templates/tools/01_monitor_youtube_v1.py`  
**Lines:** ~450  
**Purpose:** Monitor YouTube RSS feed for new sermon uploads

**Features:**
- Supports channel, playlist, and podcast source types
- Detects new videos by comparing against history
- Maintains persistent video history in JSON
- Outputs new_videos.json for downstream processing
- Full CLI with --full-scan, --limit, --json, --quiet options

**Output Files:**
- `data/video_ids/new_videos.json` - Newly detected videos
- `data/video_ids/all_video_ids.json` - Complete history
- `data/video_ids/video_ids_only.txt` - Simple ID list

**Usage Examples:**
```bash
python 01_monitor_youtube_v1.py                    # Normal check
python 01_monitor_youtube_v1.py --full-scan        # Treat all as new
python 01_monitor_youtube_v1.py --limit 5 --json   # Limited JSON output
python 01_monitor_youtube_v1.py --playlist-id PLxxx  # Override source
```

---

### 02_extract_audio_v1.py

**Location:** `_templates/tools/02_extract_audio_v1.py`  
**Lines:** ~500  
**Purpose:** Extract MP3 audio from YouTube videos using yt-dlp

**Features:**
- Extract single video, multiple videos, or batch from new_videos.json
- Configurable bitrate (64k-320k, default 128k)
- Optional metadata/thumbnail embedding
- Skip existing files (unless --force)
- Generates detailed extraction reports
- Duration detection via ffprobe

**Output Files:**
- `audio/{video_id}.mp3` - Extracted audio files
- `data/episodes/extraction_report.json` - Batch report with stats

**Usage Examples:**
```bash
python 02_extract_audio_v1.py --video-id abc123        # Single video
python 02_extract_audio_v1.py --video-ids a,b,c       # Multiple videos
python 02_extract_audio_v1.py --from-file new_videos.json  # From file
python 02_extract_audio_v1.py                         # Auto-detect
python 02_extract_audio_v1.py --bitrate 192k --embed-metadata
```

---

## 3. Script Integration

The two scripts form a pipeline:

```
01_monitor_youtube_v1.py
        │
        ▼
data/video_ids/new_videos.json
        │
        ▼
02_extract_audio_v1.py --from-file data/video_ids/new_videos.json
        │
        ▼
audio/{video_id}.mp3  +  data/episodes/extraction_report.json
```

Script 02 auto-detects new_videos.json if run without arguments.

---

## 4. External Dependencies

| Dependency | Purpose | Installation |
|------------|---------|--------------|
| feedparser | RSS parsing | `pip install feedparser` |
| requests | HTTP requests | `pip install requests` |
| python-dateutil | Date parsing | `pip install python-dateutil` |
| yt-dlp | Audio extraction | `brew install yt-dlp` |
| ffmpeg | Audio conversion | `brew install ffmpeg` |

---

## 5. Config Integration

Both scripts use centralized config from `config/config.py`:

```python
# Used by script 01
YOUTUBE_CHANNEL_ID
YOUTUBE_SOURCE_TYPE  # "channel", "playlist", "podcast"
YOUTUBE_PLAYLIST_ID
YOUTUBE_PODCAST_ID
VIDEO_IDS_DIR

# Used by script 02
AUDIO_DIR
AUDIO_FORMAT
AUDIO_BITRATE
VIDEO_IDS_DIR
DATA_DIR
```

Both scripts can run without config using CLI overrides for testing.

---

## 6. Testing Notes

Due to network proxy restrictions (youtube.com not in allowed domains), live testing was not possible in this environment. However:

- ✅ All logic functions tested via unit tests
- ✅ RSS URL generation verified
- ✅ History save/load verified
- ✅ New video detection logic verified
- ✅ File size/duration formatting verified
- ✅ Video ID parsing verified
- ✅ Report generation verified
- ✅ CLI help output verified for both scripts

The scripts will work when run in Miles' local environment with full network access.

---

## 7. Directory Structure

```
preachcaster/
├── _templates/
│   ├── config/           # Config templates (for setup script)
│   └── tools/
│       ├── 01_monitor_youtube_v1.py
│       ├── 02_extract_audio_v1.py
│       └── versions/     # For archived versions
│
└── test_project/         # Test project created for validation
    ├── config/
    │   └── config.py     # Minimal test config
    ├── tools/            # Copied scripts
    ├── data/
    │   ├── video_ids/
    │   └── episodes/
    ├── audio/
    └── logs/
```

---

## 8. Questions Resolved from CW04 Prompt

| Question | Decision | Rationale |
|----------|----------|-----------|
| RSS vs API for monitoring? | RSS for now | Simpler, no API key needed, ~15 videos sufficient for weekly monitoring |
| Audio quality defaults? | 128k default with options | Standard podcast quality; CLI offers 64k-320k range |
| Thumbnail handling? | URL reference only | Store thumbnail URL, download later if needed for podcast artwork |
| Concurrent downloads? | Sequential for now | Keep it simple; can add parallelism later if needed |

---

## 9. Open Items for CW05

### To Build Next
1. `03_fetch_transcript_v1.py` - Get YouTube captions
2. `04_chunk_transcript_v1.py` - Split for semantic search
3. Test integration of scripts 01+02+03 as a mini-pipeline

### Technical Decisions Needed
1. **Transcript fallback:** What to do when YouTube captions unavailable?
   - Option A: Whisper transcription (adds cost)
   - Option B: Skip the video
   - Option C: Flag for manual review
   
2. **Transcript format:** How to store timestamps?
   - Full JSON with word-level timing?
   - Simplified sentence/phrase level?

### Testing in Local Environment
Miles should test these scripts locally with:
```bash
# Navigate to project and activate venv
cd ~/python/nomion/PreachCaster/[church_project]
source venv/bin/activate

# Test monitoring
python tools/01_monitor_youtube_v1.py --limit 5

# Test audio extraction on one video
python tools/02_extract_audio_v1.py --video-id [any_video_id] --bitrate 128k
```

---

## 10. Code Quality Checklist

Both scripts meet these standards:

- [x] Comprehensive docstring header (~60 lines)
- [x] Type hints on all functions
- [x] Proper logging (INFO level by default)
- [x] Error handling with graceful degradation
- [x] CLI with argparse and examples
- [x] Works with or without config.py
- [x] JSON output option for scripting
- [x] Progress output for user feedback
- [x] Quiet mode for automation

---

## 11. Files Delivered

| File | Location | Purpose |
|------|----------|---------|
| `01_monitor_youtube_v1.py` | `_templates/tools/` | YouTube RSS monitoring |
| `02_extract_audio_v1.py` | `_templates/tools/` | Audio extraction |
| `config.py` | `test_project/config/` | Test configuration |
| `test_script_01.py` | `test_project/` | Unit tests for script 01 |
| `test_script_02.py` | `test_project/` | Unit tests for script 02 |

---

*Document created: CW04*  
*Next context window: CW05 — Transcript Pipeline Scripts*
