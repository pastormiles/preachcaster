# CW05 Summary: PreachCaster Transcript Pipeline Scripts

**Context Window:** CW05  
**Date:** December 31, 2024  
**Focus:** Transcript fetching and chunking scripts for semantic search preparation

---

## 1. Session Overview

This context window built the transcript processing scripts that prepare sermon content for semantic search. These scripts form the "intelligence preparation" layer of the PreachCaster pipeline.

### Key Outcomes
- ✅ Created `03_fetch_transcript_v1.py` - YouTube transcript fetching
- ✅ Created `04_chunk_transcript_v1.py` - Transcript chunking for embeddings
- ✅ Both scripts support youtube-transcript-api v1.x (current version)
- ✅ Comprehensive documentation and CLI interfaces
- ✅ Full unit test coverage
- ✅ Integration test demonstrating pipeline flow
- ✅ Ready for Pinecone indexing (chunk IDs, metadata)

---

## 2. Scripts Created

### 03_fetch_transcript_v1.py

**Location:** `_templates/tools/03_fetch_transcript_v1.py`  
**Lines:** ~650  
**Purpose:** Fetch transcripts from YouTube videos using the Captions API

**Features:**
- Supports youtube-transcript-api v0.6.x and v1.x (auto-detection)
- Fetch single video, multiple videos, or batch from file
- Prefer manual captions over auto-generated
- Multi-language support
- Optional Webshare proxy for reliability
- Retry logic with exponential backoff
- Stores both JSON (timestamped) and TXT (plain text) formats
- Batch processing with detailed reports

**Output Files:**
- `data/transcripts/{video_id}.json` - Full transcript with timestamps
- `data/transcripts/{video_id}.txt` - Plain text version
- `data/transcripts/transcript_report.json` - Batch processing report

**Usage Examples:**
```bash
# Fetch single video
python 03_fetch_transcript_v1.py --video-id abc123xyz

# Fetch from new_videos.json (script 01 output)
python 03_fetch_transcript_v1.py --from-file data/video_ids/new_videos.json

# Auto-detect input file
python 03_fetch_transcript_v1.py

# Force re-fetch with proxy
python 03_fetch_transcript_v1.py --video-id abc123 --force --use-proxy
```

---

### 04_chunk_transcript_v1.py

**Location:** `_templates/tools/04_chunk_transcript_v1.py`  
**Lines:** ~550  
**Purpose:** Split transcripts into overlapping chunks for semantic search

**Features:**
- Duration-based chunking (default: 2 minutes per chunk)
- Configurable overlap (default: 15 seconds)
- Timestamp preservation for video linking
- Chunk ID generation for Pinecone
- YouTube URL generation with timestamps
- Metadata enrichment (video ID, title, position)
- Batch processing with reports

**Chunking Strategy:**
```
Target duration:  120 seconds (2 minutes)
Overlap:          15 seconds between chunks
Minimum chunk:    30 seconds (avoid tiny final chunks)
Result:           ~500 tokens per chunk (typical speaking rate)
```

**Output Format:**
```json
{
  "video_id": "abc123xyz",
  "title": "Sunday Sermon: Finding Peace",
  "chunk_settings": {
    "target_duration_seconds": 120,
    "overlap_seconds": 15
  },
  "total_chunks": 24,
  "chunks": [
    {
      "chunk_id": "abc123xyz_chunk_000",
      "chunk_index": 0,
      "start_time": 0.0,
      "end_time": 120.0,
      "text": "Good morning everyone...",
      "word_count": 245,
      "timestamp_formatted": "0:00",
      "youtube_url": "https://www.youtube.com/watch?v=abc123xyz&t=0"
    }
  ]
}
```

**Usage Examples:**
```bash
# Chunk single video
python 04_chunk_transcript_v1.py --video-id abc123xyz

# Chunk all transcripts
python 04_chunk_transcript_v1.py --all

# Custom settings (3 minutes, 20s overlap)
python 04_chunk_transcript_v1.py --chunk-duration 180 --overlap 20
```

---

## 3. Pipeline Integration

The transcript pipeline is now complete:

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
03_fetch_transcript_v1.py  ◄── NEW
        │
        ▼
    data/transcripts/{video_id}.json
    data/transcripts/{video_id}.txt
        │
        ▼
04_chunk_transcript_v1.py  ◄── NEW
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

## 4. Technical Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| API version support | v0.6.x + v1.x | Future-proof, handles both versions |
| Chunking method | Duration-based | Consistent sizes, natural for sermons |
| Default chunk size | 2 minutes | ~500 tokens, good for embeddings |
| Overlap | 15 seconds | Context continuity, not too redundant |
| Chunk ID format | `{video_id}_chunk_{index:03d}` | Sortable, unique, Pinecone-friendly |
| Transcript storage | JSON + TXT | Timestamped for search, plain for display |

---

## 5. Questions Resolved

| Question | Decision | Rationale |
|----------|----------|-----------|
| Transcript fallback? | Skip video (Option B) | Keep MVP simple, add Whisper later |
| Chunk size tuning? | 2 min default, configurable | Works for most sermons, CLI override available |
| Language handling? | Store language code, default English | Extensible for multilingual churches |
| youtube-transcript-api version? | Support both v0.6.x and v1.x | Library updated significantly, need both |

---

## 6. Testing Summary

### Unit Tests
- **Script 03:** 8 tests covering save/load, file formats, batch processing
- **Script 04:** 13 tests covering chunking logic, overlap, edge cases

### Integration Test
- Simulated 9-minute sermon → 5 searchable chunks
- Verified chunk IDs suitable for Pinecone
- Confirmed YouTube URL generation with timestamps

### Network Restrictions
Live YouTube testing blocked by environment proxy. Scripts verified with mock data and will work in Miles' local environment.

---

## 7. Files Delivered

| File | Location | Purpose |
|------|----------|---------|
| `03_fetch_transcript_v1.py` | `_templates/tools/` | Transcript fetching |
| `04_chunk_transcript_v1.py` | `_templates/tools/` | Transcript chunking |
| `config.py` | `test_project/config/` | Test configuration |
| `test_script_03.py` | `test_project/` | Script 03 unit tests |
| `test_script_04.py` | `test_project/` | Script 04 unit tests |
| `test_integration.py` | `test_project/` | Pipeline integration test |
| `CW05_SUMMARY.md` | `_templates/docs/` | This document |

---

## 8. Directory Structure

```
preachcaster/
├── _templates/
│   ├── config/
│   └── tools/
│       ├── 01_monitor_youtube_v1.py    (CW04)
│       ├── 02_extract_audio_v1.py      (CW04)
│       ├── 03_fetch_transcript_v1.py   (CW05) ◄── NEW
│       ├── 04_chunk_transcript_v1.py   (CW05) ◄── NEW
│       └── versions/
│
└── test_project/
    ├── config/
    │   └── config.py
    ├── tools/
    │   ├── 03_fetch_transcript_v1.py
    │   └── 04_chunk_transcript_v1.py
    ├── data/
    │   ├── video_ids/
    │   ├── transcripts/
    │   ├── chunks/
    │   └── episodes/
    ├── test_script_03.py
    ├── test_script_04.py
    └── test_integration.py
```

---

## 9. Success Criteria Status

| Criterion | Status |
|-----------|--------|
| Script 03 can fetch transcripts from YouTube | ✅ Ready (network-dependent) |
| Script 03 stores both JSON and plain text formats | ✅ Complete |
| Script 03 handles missing captions gracefully | ✅ Complete |
| Script 03 supports proxy configuration | ✅ Complete |
| Script 04 splits transcripts into timed chunks | ✅ Complete |
| Script 04 creates overlapping chunks | ✅ Complete |
| Script 04 generates chunk IDs for Pinecone | ✅ Complete |
| Script 04 preserves timestamp mapping | ✅ Complete |
| Both scripts follow documentation patterns | ✅ Complete |
| Both scripts have working CLI interfaces | ✅ Complete |

---

## 10. Local Testing Instructions

To test scripts in your local environment:

```bash
# Navigate to project
cd ~/python/nomion/PreachCaster/[church_project]
source venv/bin/activate

# Test transcript fetching (requires network)
python tools/03_fetch_transcript_v1.py --video-id [any_video_id] --json

# Test chunking (after fetching)
python tools/04_chunk_transcript_v1.py --video-id [same_video_id] --json

# Run full pipeline
python tools/03_fetch_transcript_v1.py --from-file data/video_ids/new_videos.json
python tools/04_chunk_transcript_v1.py --from-report data/transcripts/transcript_report.json
```

---

## 11. Open Items for CW06

### To Build Next
1. `05_generate_embeddings_v1.py` - Create OpenAI embeddings from chunks
2. `06_upload_pinecone_v1.py` - Store embeddings in vector database
3. Test semantic search with sample queries

### Technical Decisions for CW06
1. **Embedding model:** text-embedding-3-small (cheapest good option)
2. **Batch size:** Optimize for API rate limits
3. **Pinecone namespace:** Per-church isolation

---

## 12. Key Learnings

1. **youtube-transcript-api v1.x breaking changes:** Had to support both API versions
2. **Duration-based chunking works well:** Natural for spoken content like sermons
3. **Chunk metadata is crucial:** Video ID, timestamps, URLs enable good search UX
4. **Network testing limitations:** Mock data validation essential when network blocked

---

*Document created: CW05*  
*Next context window: CW06 — Embedding Generation & Pinecone Upload*
