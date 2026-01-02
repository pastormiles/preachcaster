# CW06 Summary: PreachCaster Embedding & Vector Search Scripts

**Context Window:** CW06  
**Date:** January 1, 2025  
**Focus:** Embedding generation and Pinecone upload for semantic search

---

## 1. Session Overview

This context window built the embedding and vector database scripts that complete the "intelligence layer" of the PreachCaster pipeline. These scripts enable semantic search across sermon content.

### Key Outcomes
- ✅ Created `05_generate_embeddings_v1.py` - OpenAI embedding generation
- ✅ Created `06_upload_pinecone_v1.py` - Pinecone vector database upload
- ✅ Comprehensive documentation following established patterns
- ✅ Full CLI interfaces with all required options
- ✅ Unit tests passing (13 tests for script 05, 17 tests for script 06)
- ✅ Dry-run mode for cost estimation
- ✅ Test query verification for Pinecone uploads

---

## 2. Scripts Created

### 05_generate_embeddings_v1.py

**Location:** `_templates/tools/05_generate_embeddings_v1.py`  
**Lines:** ~600  
**Purpose:** Generate vector embeddings from transcript chunks using OpenAI API

**Features:**
- OpenAI embedding generation (text-embedding-3-small by default)
- Batch API calls for efficiency (respects rate limits)
- Token counting with tiktoken (falls back to estimation)
- Cost tracking and estimation
- Support for incremental processing (skip existing)
- Dry-run mode for cost estimation without API calls
- JSON output for scripting/automation

**Output Files:**
- `data/embeddings/{video_id}_embeddings.json` - Chunks with embeddings
- `data/embeddings/embedding_report.json` - Batch processing report

**Usage Examples:**
```bash
# Generate embeddings for single video
python 05_generate_embeddings_v1.py --video-id abc123xyz

# Dry run to estimate cost
python 05_generate_embeddings_v1.py --all --dry-run

# Process from chunk report
python 05_generate_embeddings_v1.py --from-report data/chunks/chunk_report.json

# Custom model and batch size
python 05_generate_embeddings_v1.py --video-id abc123 --model text-embedding-3-large --batch-size 50
```

---

### 06_upload_pinecone_v1.py

**Location:** `_templates/tools/06_upload_pinecone_v1.py`  
**Lines:** ~650  
**Purpose:** Upload embeddings to Pinecone vector database for semantic search

**Features:**
- Batch upsert with progress tracking
- Namespace isolation for multi-tenant support
- Metadata truncation to respect Pinecone limits
- Delete-and-replace for re-indexing
- Test query verification after upload
- Dry-run mode for validation
- JSON output for automation

**Output Files:**
- `data/embeddings/pinecone_report.json` - Upload report with statistics
- Vectors uploaded to Pinecone index

**Usage Examples:**
```bash
# Upload single video embeddings
python 06_upload_pinecone_v1.py --video-id abc123xyz

# Replace existing vectors
python 06_upload_pinecone_v1.py --video-id abc123 --replace

# Test query after upload
python 06_upload_pinecone_v1.py --video-id abc123 --test-query "finding peace"

# Dry run to validate
python 06_upload_pinecone_v1.py --all --dry-run
```

---

## 3. Pipeline Integration

The intelligence layer is now complete:

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
03_fetch_transcript_v1.py
        │
        ▼
    data/transcripts/{video_id}.json
        │
        ▼
04_chunk_transcript_v1.py
        │
        ▼
    data/chunks/{video_id}_chunks.json
        │
        ▼
05_generate_embeddings_v1.py  ◄── CW06
        │
        ▼
    data/embeddings/{video_id}_embeddings.json
        │
        ▼
06_upload_pinecone_v1.py  ◄── CW06
        │
        ▼
    Pinecone Vector Database (searchable!)
```

---

## 4. Technical Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Embedding model | text-embedding-3-small | Best price/performance ($0.02/1M tokens) |
| Token counting | tiktoken with fallback | Accurate when available, degrades gracefully |
| Batch size (embeddings) | 100 default | Conservative for reliability |
| Batch size (Pinecone) | 100 default | Well under 1000 limit |
| Metadata text | 500 chars truncated | Preview in search results |
| Namespace | Church slug | Multi-tenant isolation |

---

## 5. Cost Analysis

### Embedding Costs (text-embedding-3-small)

| Model | Price per 1M tokens |
|-------|---------------------|
| text-embedding-3-small | $0.02 |
| text-embedding-3-large | $0.13 |
| text-embedding-ada-002 | $0.10 |

### Typical Costs

| Content | Tokens | Cost |
|---------|--------|------|
| 45-min sermon | ~9,000 | $0.0002 |
| 100 sermons | ~900,000 | $0.018 |
| 500 sermons | ~4,500,000 | $0.09 |

---

## 6. Output Formats

### Embedding JSON Structure
```json
{
  "video_id": "abc123xyz",
  "title": "Sunday Sermon: Finding Peace",
  "generated_at": "2025-01-01T10:00:00",
  "model": "text-embedding-3-small",
  "dimensions": 1536,
  "total_chunks": 24,
  "total_tokens": 12500,
  "estimated_cost_usd": 0.00025,
  "chunks": [
    {
      "chunk_id": "abc123xyz_chunk_000",
      "chunk_index": 0,
      "text": "Good morning everyone...",
      "start_time": 0.0,
      "end_time": 120.0,
      "timestamp_formatted": "0:00",
      "youtube_url": "https://youtube.com/watch?v=abc123xyz&t=0",
      "word_count": 245,
      "token_count": 312,
      "embedding": [0.0123, -0.0456, ...]
    }
  ]
}
```

### Pinecone Vector Format
```python
{
    "id": "abc123xyz_chunk_000",
    "values": [0.0123, -0.0456, ...],  # 1536 dimensions
    "metadata": {
        "video_id": "abc123xyz",
        "title": "Sunday Sermon: Finding Peace",
        "chunk_index": 0,
        "start_time": 0.0,
        "end_time": 120.0,
        "timestamp_formatted": "0:00",
        "youtube_url": "https://youtube.com/watch?v=abc123xyz&t=0",
        "text": "Good morning everyone...",  # Truncated to 500 chars
        "word_count": 245
    }
}
```

---

## 7. Testing Summary

### Script 05 Tests (13 tests)
- ✅ Token counting with estimation fallback
- ✅ Cost estimation for different models
- ✅ Cost formatting
- ✅ File loading/saving
- ✅ Directory scanning for chunk files
- ✅ Auto-detection of input sources
- ✅ CLI argument parsing

### Script 06 Tests (17 tests)
- ✅ Text truncation (short, long, exact limit)
- ✅ Metadata preparation with None handling
- ✅ Vector preparation with embedding validation
- ✅ Skipping chunks without embeddings
- ✅ File loading/saving
- ✅ Directory scanning for embedding files
- ✅ Auto-detection of input sources
- ✅ CLI argument parsing

---

## 8. Files Delivered

| File | Location | Purpose |
|------|----------|---------|
| `05_generate_embeddings_v1.py` | `_templates/tools/` | Embedding generation |
| `06_upload_pinecone_v1.py` | `_templates/tools/` | Pinecone upload |
| `config.py` | `test_project/config/` | Test configuration |
| `test123xyz_chunks.json` | `test_project/data/chunks/` | Sample chunk file |
| `test_script_05.py` | `test_project/` | Unit tests for script 05 |
| `test_script_06.py` | `test_project/` | Unit tests for script 06 |

---

## 9. Directory Structure

```
preachcaster/
├── _templates/
│   ├── config/
│   └── tools/
│       ├── 01_monitor_youtube_v1.py    (CW04)
│       ├── 02_extract_audio_v1.py      (CW04)
│       ├── 03_fetch_transcript_v1.py   (CW05)
│       ├── 04_chunk_transcript_v1.py   (CW05)
│       ├── 05_generate_embeddings_v1.py (CW06) ◄── NEW
│       ├── 06_upload_pinecone_v1.py    (CW06) ◄── NEW
│       └── versions/
│
└── test_project/
    ├── config/
    │   └── config.py
    ├── tools/
    │   ├── 05_generate_embeddings_v1.py
    │   └── 06_upload_pinecone_v1.py
    ├── data/
    │   ├── chunks/
    │   │   └── test123xyz_chunks.json
    │   └── embeddings/
    ├── test_script_05.py
    └── test_script_06.py
```

---

## 10. Success Criteria Status

| Criterion | Status |
|-----------|--------|
| Script 05 generates embeddings from chunk files | ✅ Complete |
| Script 05 tracks token usage and costs | ✅ Complete |
| Script 05 supports batch processing | ✅ Complete |
| Script 05 has dry-run mode for cost estimation | ✅ Complete |
| Script 06 uploads vectors to Pinecone | ✅ Complete |
| Script 06 uses namespace for church isolation | ✅ Complete |
| Script 06 includes test query verification | ✅ Complete |
| Script 06 truncates metadata appropriately | ✅ Complete |
| Both scripts follow documentation patterns | ✅ Complete |
| Both scripts have working CLI interfaces | ✅ Complete |

---

## 11. Local Testing Instructions

To test scripts in your local environment:

```bash
# Navigate to project and activate venv
cd ~/python/nomion/PreachCaster/[church_project]
source venv/bin/activate

# Test embedding generation (requires OpenAI API key)
export OPENAI_API_KEY="your-key-here"
python tools/05_generate_embeddings_v1.py --video-id [video_id] --dry-run
python tools/05_generate_embeddings_v1.py --video-id [video_id]

# Test Pinecone upload (requires Pinecone API key)
export PINECONE_API_KEY="your-key-here"
python tools/06_upload_pinecone_v1.py --video-id [video_id] --dry-run
python tools/06_upload_pinecone_v1.py --video-id [video_id] --test-query "hope"

# Run full intelligence pipeline
python tools/05_generate_embeddings_v1.py --from-report data/chunks/chunk_report.json
python tools/06_upload_pinecone_v1.py --from-report data/embeddings/embedding_report.json
```

---

## 12. Open Items for CW07

### To Build Next
1. `07_generate_ai_content_v1.py` - AI summaries, scripture extraction, topic tagging
2. `08_generate_discussion_guide_v1.py` - Small group study guide PDF

### Technical Considerations
- GPT-4o-mini for AI content generation (cost-effective)
- PDF generation library (ReportLab or WeasyPrint)
- Prompt engineering for consistent, high-quality outputs

---

## 13. Key Learnings

1. **Token counting fallback is essential** - tiktoken may not always be available
2. **Metadata None handling is critical** - Pinecone doesn't accept None values
3. **Dry-run mode saves money** - Always estimate costs before API calls
4. **Test queries verify success** - Essential for confirming semantic search works

---

*Document created: CW06*  
*Next context window: CW07 — AI Content Generation & Discussion Guides*
