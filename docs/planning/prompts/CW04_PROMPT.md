# CW04 Prompt: PreachCaster Pipeline Script Development

**Project:** PreachCaster  
**Context Window:** CW04  
**Objective:** Build the first pipeline scripts for YouTube monitoring and audio extraction

---

## Context for Claude

You are continuing development of PreachCaster, an automated sermon podcasting platform for churches. Review the Project Bible and CW03 Summary for full context.

**Quick Summary:**
- PreachCaster monitors YouTube for new sermon uploads
- Automatically extracts audio, processes transcripts, generates AI content
- Publishes to WordPress with RSS feeds for podcast platforms
- Enables semantic search across all sermon content

**Tech Stack:** Python, Flask, OpenAI, Pinecone, yt-dlp, WordPress

**CW03 Accomplishments:**
- Created `preachcaster_setup_v1.sh` (comprehensive project scaffolding)
- Established directory structure and configuration patterns
- Decided on Python monolith architecture
- Added YouTube playlist/podcast source flexibility

---

## CW04 Goal

Build the first pipeline scripts that will go in `_templates/tools/`. By the end of this session, we should have working scripts for:

1. **01_monitor_youtube_v1.py** - Monitor YouTube RSS feed for new videos
2. **02_extract_audio_v1.py** - Extract MP3 audio using yt-dlp

These are the first two scripts in the pipeline and handle the "input" side of the system.

---

## Script 1: 01_monitor_youtube_v1.py

### Purpose
Monitor a YouTube channel (or playlist/podcast) for new video uploads by parsing the RSS feed. This script detects new content that needs to be processed.

### Requirements

**Input:**
- YouTube channel ID (from config)
- Or playlist ID (from config, if source type is "playlist")
- Or podcast ID (from config, if source type is "podcast")

**Output:**
- `data/video_ids/new_videos.json` - List of newly detected videos
- `data/video_ids/all_video_ids.json` - Complete video history
- `data/video_ids/video_ids_only.txt` - Simple ID list

**Functionality:**
1. Fetch RSS feed based on source type:
   - Channel: `https://www.youtube.com/feeds/videos.xml?channel_id=XXXXX`
   - Playlist: `https://www.youtube.com/feeds/videos.xml?playlist_id=XXXXX`
2. Parse feed entries (title, video ID, published date, description)
3. Compare against previously seen videos
4. Output list of new videos for processing
5. Update tracking file with all seen videos

**CLI Interface:**
```bash
# Check for new videos
python 01_monitor_youtube_v1.py

# Force re-check all videos (ignore history)
python 01_monitor_youtube_v1.py --full-scan

# Limit results (for testing)
python 01_monitor_youtube_v1.py --limit 5

# Output as JSON to stdout (for piping)
python 01_monitor_youtube_v1.py --json
```

**Output Format (new_videos.json):**
```json
{
  "check_time": "2024-12-31T10:30:00",
  "source_type": "channel",
  "source_id": "UCDWgXIoyH3WNRxlB9N-gCOg",
  "new_count": 2,
  "videos": [
    {
      "video_id": "abc123xyz",
      "title": "Sunday Sermon: Finding Peace",
      "published_at": "2024-12-29T14:00:00Z",
      "description": "Pastor Miles teaches...",
      "url": "https://www.youtube.com/watch?v=abc123xyz",
      "thumbnail_url": "https://i.ytimg.com/vi/abc123xyz/maxresdefault.jpg"
    }
  ]
}
```

### Key Considerations
- YouTube RSS feeds are public (no API key needed)
- Feeds contain ~15 most recent videos
- Use `feedparser` library for RSS parsing
- Need to handle both channel and playlist RSS URL formats
- Store video history to detect truly "new" videos

---

## Script 2: 02_extract_audio_v1.py

### Purpose
Extract audio from YouTube videos as podcast-ready MP3 files using yt-dlp.

### Requirements

**Input:**
- Video ID (single video) or list of video IDs
- Or path to `new_videos.json` from script 01

**Output:**
- MP3 file(s) in `audio/` directory
- Extraction report with file sizes, durations

**Functionality:**
1. Accept video ID(s) as input
2. Use yt-dlp to download audio-only stream
3. Convert to MP3 (128kbps by default, configurable)
4. Save with consistent naming: `{video_id}.mp3`
5. Extract and return metadata (duration, file size)

**CLI Interface:**
```bash
# Extract single video
python 02_extract_audio_v1.py --video-id abc123xyz

# Extract from new_videos.json
python 02_extract_audio_v1.py --from-file data/video_ids/new_videos.json

# Extract multiple videos
python 02_extract_audio_v1.py --video-ids abc123,def456,ghi789

# Custom output directory
python 02_extract_audio_v1.py --video-id abc123 --output-dir ./custom/

# Custom quality
python 02_extract_audio_v1.py --video-id abc123 --bitrate 192k
```

**Output Format (extraction_report.json):**
```json
{
  "extraction_time": "2024-12-31T10:35:00",
  "videos_processed": 2,
  "total_duration_seconds": 5400,
  "total_file_size_mb": 64.5,
  "results": [
    {
      "video_id": "abc123xyz",
      "title": "Sunday Sermon: Finding Peace",
      "status": "success",
      "audio_file": "audio/abc123xyz.mp3",
      "duration_seconds": 2700,
      "file_size_bytes": 32400000,
      "bitrate": "128k"
    }
  ]
}
```

### Key Considerations
- yt-dlp must be installed on system (`brew install yt-dlp`)
- ffmpeg required for format conversion (`brew install ffmpeg`)
- Handle private/unavailable videos gracefully
- Show progress during download
- Consider adding metadata tags to MP3 (title, artist)

### yt-dlp Command Reference
```bash
# Basic audio extraction
yt-dlp -x --audio-format mp3 --audio-quality 128K -o "%(id)s.mp3" URL

# With metadata
yt-dlp -x --audio-format mp3 --audio-quality 128K \
  --embed-thumbnail --add-metadata \
  -o "%(id)s.mp3" URL
```

---

## Documentation Requirements

Each script MUST include comprehensive header documentation following the established pattern:

```python
#!/usr/bin/env python3
"""
01_monitor_youtube_v1.py
Monitor YouTube RSS feed for new sermon uploads.

================================================================================
OVERVIEW
================================================================================

[Why this script exists, what problem it solves]

================================================================================
HOW IT WORKS
================================================================================

[Numbered steps explaining the logic]

================================================================================
INPUT/OUTPUT
================================================================================

[Clear description of inputs and outputs with examples]

================================================================================
USAGE
================================================================================

[Command-line examples]

================================================================================
REQUIREMENTS
================================================================================

[Prerequisites, dependencies, API keys needed]

================================================================================
CONFIG IMPORTS USED
================================================================================

[List of imports from config.py]

================================================================================
"""
```

---

## Config Imports Available

From `config/config.py`, these values are available:

```python
# Church Settings
CHURCH_NAME, CHURCH_SLUG

# YouTube Settings
YOUTUBE_CHANNEL_ID
YOUTUBE_SOURCE_TYPE  # "channel", "playlist", or "podcast"
YOUTUBE_PLAYLIST_ID
YOUTUBE_PLAYLIST_NAME
YOUTUBE_PODCAST_ID
YOUTUBE_RSS_FEED

# Paths
PROJECT_ROOT, DATA_DIR, AUDIO_DIR, LOGS_DIR
VIDEO_IDS_DIR, VIDEO_IDS_FILE

# Audio Settings
AUDIO_FORMAT, AUDIO_BITRATE, AUDIO_SAMPLE_RATE

# Helper Functions
ensure_directories()
get_log_file(script_name)
```

---

## Test Data

**Cross Connection Church:**
- Channel ID: `UCDWgXIoyH3WNRxlB9N-gCOg`
- RSS Feed: `https://www.youtube.com/feeds/videos.xml?channel_id=UCDWgXIoyH3WNRxlB9N-gCOg`

Use this channel for testing the scripts.

---

## Success Criteria for CW04

By the end of this context window:

- [ ] `01_monitor_youtube_v1.py` can fetch and parse YouTube RSS feed
- [ ] `01_monitor_youtube_v1.py` correctly identifies new vs. seen videos
- [ ] `01_monitor_youtube_v1.py` supports channel, playlist, and podcast sources
- [ ] `02_extract_audio_v1.py` can extract MP3 from a YouTube video
- [ ] `02_extract_audio_v1.py` handles errors gracefully
- [ ] Both scripts follow established documentation patterns
- [ ] Both scripts use centralized config properly
- [ ] Both scripts have working CLI interfaces with argparse

---

## Out of Scope for CW04

- Transcript extraction (script 03)
- Chunking and embeddings (scripts 04-06)
- AI content generation (scripts 07-08)
- Full pipeline orchestration (script 09)
- Flask server
- WordPress plugin

---

## Questions to Resolve in CW04

1. **RSS vs API for monitoring:** RSS is simpler but limited to ~15 videos. Should we also support YouTube Data API for full history?

2. **Audio quality defaults:** 128kbps is standard for podcasts. Should we offer presets (low/medium/high)?

3. **Thumbnail handling:** Should we download video thumbnails for podcast artwork, or rely on URLs?

4. **Concurrent downloads:** Should audio extraction support parallel downloads for speed?

---

## File Locations

Scripts should be created in:
```
/home/claude/preachcaster/_templates/tools/
├── 01_monitor_youtube_v1.py
├── 02_extract_audio_v1.py
└── versions/
```

---

## How to Start

1. Review the config.py structure from CW03
2. Create `01_monitor_youtube_v1.py` with full documentation
3. Test with Cross Connection Church RSS feed
4. Create `02_extract_audio_v1.py` with full documentation
5. Test audio extraction on a sample video
6. Ensure both scripts integrate properly with config

---

*Ready to begin pipeline script development.*
