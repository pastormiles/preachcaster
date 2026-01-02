# CW05 Prompt: PreachCaster Transcript Pipeline Scripts

**Project:** PreachCaster  
**Context Window:** CW05  
**Objective:** Build transcript fetching and chunking scripts for semantic search preparation

---

## Context for Claude

You are continuing development of PreachCaster, an automated sermon podcasting platform for churches. Review the Project Bible and previous CW summaries for full context.

**Quick Summary:**
- PreachCaster monitors YouTube for new sermon uploads
- Automatically extracts audio, processes transcripts, generates AI content
- Publishes to WordPress with RSS feeds for podcast platforms
- Enables semantic search across all sermon content

**Tech Stack:** Python, Flask, OpenAI, Pinecone, yt-dlp, WordPress

**CW04 Accomplishments:**
- Created `01_monitor_youtube_v1.py` (YouTube RSS monitoring)
- Created `02_extract_audio_v1.py` (Audio extraction via yt-dlp)
- Both scripts tested and working with full CLI interfaces
- Established documentation standards for pipeline scripts

---

## CW05 Goal

Build the transcript processing scripts that prepare content for semantic search. By the end of this session, we should have working scripts for:

1. **03_fetch_transcript_v1.py** - Fetch transcripts from YouTube Captions API
2. **04_chunk_transcript_v1.py** - Split transcripts into searchable chunks

These scripts handle the "intelligence preparation" side - getting text ready for embeddings.

---

## Script 3: 03_fetch_transcript_v1.py

### Purpose
Fetch transcripts from YouTube videos using the YouTube Transcript API. This retrieves auto-generated or manual captions and stores them in a structured format.

### Requirements

**Input:**
- Video ID (single video) or list of video IDs
- Or path to `new_videos.json` from script 01
- Or path to `extraction_report.json` from script 02

**Output:**
- `data/transcripts/{video_id}.json` - Full transcript with timestamps
- `data/transcripts/{video_id}.txt` - Plain text version
- `data/transcripts/transcript_report.json` - Batch processing report

**Functionality:**
1. Accept video ID(s) as input
2. Use `youtube-transcript-api` library to fetch captions
3. Prefer manual captions over auto-generated when available
4. Support language selection (default: English)
5. Handle videos without captions gracefully
6. Store both timestamped JSON and plain text versions
7. Support proxy configuration (Webshare) for reliability

**CLI Interface:**
```bash
# Fetch single video transcript
python 03_fetch_transcript_v1.py --video-id abc123xyz

# Fetch from new_videos.json
python 03_fetch_transcript_v1.py --from-file data/video_ids/new_videos.json

# Fetch multiple videos
python 03_fetch_transcript_v1.py --video-ids abc123,def456,ghi789

# Specify language preference
python 03_fetch_transcript_v1.py --video-id abc123 --language en

# Use proxy (from config or override)
python 03_fetch_transcript_v1.py --video-id abc123 --use-proxy

# Force re-fetch (overwrite existing)
python 03_fetch_transcript_v1.py --video-id abc123 --force

# Output JSON to stdout
python 03_fetch_transcript_v1.py --video-id abc123 --json
```

**Output Format (transcript JSON):**
```json
{
  "video_id": "abc123xyz",
  "title": "Sunday Sermon: Finding Peace",
  "fetched_at": "2024-12-31T10:30:00",
  "language": "en",
  "is_generated": true,
  "duration_seconds": 2700,
  "word_count": 4500,
  "segments": [
    {
      "start": 0.0,
      "duration": 4.5,
      "end": 4.5,
      "text": "Good morning everyone and welcome to Cross Connection Church."
    },
    {
      "start": 4.5,
      "duration": 3.2,
      "end": 7.7,
      "text": "Today we're going to be talking about finding peace."
    }
  ]
}
```

### Key Considerations
- Use `youtube-transcript-api` library (already in requirements.txt)
- Auto-generated captions may have errors - store `is_generated` flag
- Some videos have no captions at all - handle gracefully
- Proxy support is important for reliability at scale
- Store timestamps for future video timestamp linking

### Existing Code Reference
Miles has working transcript code in `03_extract_transcripts_v10.py` with:
- Webshare proxy integration
- Retry logic with exponential backoff
- Progress tracking with incremental saves
- Language preference handling

Adapt patterns from this existing code.

---

## Script 4: 04_chunk_transcript_v1.py

### Purpose
Split transcripts into overlapping chunks optimized for semantic search. Chunks should be ~500 tokens with context overlap to ensure searchability.

### Requirements

**Input:**
- Transcript JSON file (from script 03)
- Or directory of transcript files
- Or path to `transcript_report.json` for batch processing

**Output:**
- `data/chunks/{video_id}_chunks.json` - Chunked transcript
- `data/chunks/chunk_report.json` - Batch processing stats

**Functionality:**
1. Load transcript JSON with timestamps
2. Split into chunks based on duration/token count
3. Add overlap between chunks for context continuity
4. Preserve timestamp mapping for each chunk
5. Enrich chunks with metadata (video ID, title, position)
6. Generate chunk IDs for Pinecone indexing

**CLI Interface:**
```bash
# Chunk single transcript
python 04_chunk_transcript_v1.py --video-id abc123xyz

# Chunk all transcripts in directory
python 04_chunk_transcript_v1.py --all

# Chunk from transcript report
python 04_chunk_transcript_v1.py --from-report data/transcripts/transcript_report.json

# Custom chunk settings
python 04_chunk_transcript_v1.py --video-id abc123 --chunk-duration 120 --overlap 15

# Force re-chunk
python 04_chunk_transcript_v1.py --video-id abc123 --force
```

**Output Format (chunks JSON):**
```json
{
  "video_id": "abc123xyz",
  "title": "Sunday Sermon: Finding Peace",
  "chunked_at": "2024-12-31T10:35:00",
  "chunk_settings": {
    "target_duration_seconds": 120,
    "overlap_seconds": 15,
    "min_chunk_seconds": 30
  },
  "total_chunks": 24,
  "chunks": [
    {
      "chunk_id": "abc123xyz_chunk_001",
      "chunk_index": 0,
      "start_time": 0.0,
      "end_time": 120.0,
      "duration_seconds": 120.0,
      "text": "Good morning everyone and welcome to Cross Connection Church. Today we're going to be talking about finding peace...",
      "word_count": 245,
      "timestamp_formatted": "0:00",
      "youtube_url": "https://www.youtube.com/watch?v=abc123xyz&t=0"
    },
    {
      "chunk_id": "abc123xyz_chunk_002",
      "chunk_index": 1,
      "start_time": 105.0,
      "end_time": 225.0,
      "duration_seconds": 120.0,
      "text": "...and that's why Paul tells us in Philippians chapter 4...",
      "word_count": 238,
      "timestamp_formatted": "1:45",
      "youtube_url": "https://www.youtube.com/watch?v=abc123xyz&t=105"
    }
  ]
}
```

### Chunking Strategy

**Duration-based chunking (recommended for sermons):**
- Target: ~2 minutes (120 seconds) per chunk
- Overlap: ~15 seconds between chunks
- Minimum chunk: 30 seconds (don't create tiny chunks at end)

**Why duration-based:**
- Sermons have natural speaking rhythm
- Consistent chunk sizes for embeddings
- Easy timestamp linking back to video
- ~500 tokens per 2-minute chunk (typical speaking rate)

**Chunk metadata for Pinecone:**
Each chunk needs metadata for filtering and display:
- `video_id`: For filtering by video
- `chunk_index`: For ordering
- `start_time`: For timestamp linking
- `title`: For display
- `timestamp_formatted`: Human-readable time

### Existing Code Reference
Miles has working chunking code in `04_chunk_transcripts_v2.py` with:
- Duration-based chunking with configurable parameters
- Timestamp formatting utilities
- Metadata enrichment
- Progress tracking

Adapt patterns from this existing code.

---

## Documentation Requirements

Follow the same comprehensive header documentation pattern from CW04:

```python
#!/usr/bin/env python3
"""
03_fetch_transcript_v1.py
Fetch transcripts from YouTube videos using the Captions API.

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
TRANSCRIPTS_DIR = DATA_DIR / "transcripts"
CHUNKS_DIR = DATA_DIR / "chunks"

# Transcript Settings
TRANSCRIPT_LANGUAGE = "en"
TRANSCRIPT_PREFER_MANUAL = True

# Chunking Settings
CHUNK_DURATION_SECONDS = 120  # 2 minutes
CHUNK_OVERLAP_SECONDS = 15
CHUNK_MIN_SECONDS = 30

# Proxy Settings (optional)
WEBSHARE_PROXY_USER = os.getenv("WEBSHARE_PROXY_USER")
WEBSHARE_PROXY_PASS = os.getenv("WEBSHARE_PROXY_PASS")
WEBSHARE_PROXY_HOST = "p.webshare.io"
WEBSHARE_PROXY_PORT = "80"
```

---

## Test Data

Use transcripts from Cross Connection Church videos tested in CW04, or create mock transcript data for testing chunking logic.

---

## Success Criteria for CW05

By the end of this context window:

- [ ] `03_fetch_transcript_v1.py` can fetch transcripts from YouTube
- [ ] `03_fetch_transcript_v1.py` stores both JSON and plain text formats
- [ ] `03_fetch_transcript_v1.py` handles missing captions gracefully
- [ ] `03_fetch_transcript_v1.py` supports proxy configuration
- [ ] `04_chunk_transcript_v1.py` splits transcripts into timed chunks
- [ ] `04_chunk_transcript_v1.py` creates overlapping chunks
- [ ] `04_chunk_transcript_v1.py` generates chunk IDs for Pinecone
- [ ] `04_chunk_transcript_v1.py` preserves timestamp mapping
- [ ] Both scripts follow established documentation patterns
- [ ] Both scripts have working CLI interfaces

---

## Pipeline Integration

After CW05, the pipeline will be:

```
01_monitor_youtube_v1.py
        │
        ▼
    new_videos.json
        │
        ▼
02_extract_audio_v1.py
        │
        ▼
    audio/{video_id}.mp3
        │
        ▼
03_fetch_transcript_v1.py  ◄── CW05
        │
        ▼
    data/transcripts/{video_id}.json
        │
        ▼
04_chunk_transcript_v1.py  ◄── CW05
        │
        ▼
    data/chunks/{video_id}_chunks.json
        │
        ▼
[CW06: 05_generate_embeddings_v1.py]
        │
        ▼
[CW06: 06_upload_pinecone_v1.py]
```

---

## Out of Scope for CW05

- Embedding generation (script 05) - CW06
- Pinecone upload (script 06) - CW06
- AI content generation (scripts 07-08) - CW07
- Full pipeline orchestration (script 09) - CW08
- Flask server
- WordPress plugin

---

## Questions to Resolve in CW05

1. **Transcript fallback strategy:** When YouTube captions unavailable:
   - Option A: Whisper transcription (~$0.006/min, requires audio file)
   - Option B: Skip video, mark as "no transcript"
   - Option C: Flag for manual review
   - **Recommendation:** Option B for MVP, add Whisper later as premium feature

2. **Chunk size tuning:** 2 minutes is a starting point. Should we:
   - Make it configurable per-church?
   - Adjust based on sermon length?
   - Use token count instead of duration?

3. **Language handling:** How to handle multilingual churches?
   - Store language code with transcript
   - Support fetching multiple language versions?

---

## File Locations

Scripts should be created in:
```
/home/claude/preachcaster/_templates/tools/
├── 01_monitor_youtube_v1.py   (exists)
├── 02_extract_audio_v1.py     (exists)
├── 03_fetch_transcript_v1.py  ◄── NEW
├── 04_chunk_transcript_v1.py  ◄── NEW
└── versions/
```

---

## How to Start

1. Review existing transcript code patterns from Miles' YouTube AI Search project
2. Create `03_fetch_transcript_v1.py` with full documentation
3. Test with sample video IDs (or mock data if network restricted)
4. Create `04_chunk_transcript_v1.py` with full documentation
5. Test chunking with sample transcript data
6. Verify both scripts integrate with existing pipeline

---

*Ready to begin transcript pipeline development.*
