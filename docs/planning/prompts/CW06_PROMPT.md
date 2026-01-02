# CW06 Prompt: PreachCaster Embedding & Vector Search Scripts

**Project:** PreachCaster  
**Context Window:** CW06  
**Objective:** Build embedding generation and Pinecone upload scripts for semantic search

---

## Context for Claude

You are continuing development of PreachCaster, an automated sermon podcasting platform for churches. Review the Project Bible and previous CW summaries for full context.

**Quick Summary:**
- PreachCaster monitors YouTube for new sermon uploads
- Automatically extracts audio, processes transcripts, generates AI content
- Publishes to WordPress with RSS feeds for podcast platforms
- Enables semantic search across all sermon content

**Tech Stack:** Python, Flask, OpenAI, Pinecone, yt-dlp, WordPress

**CW05 Accomplishments:**
- Created `03_fetch_transcript_v1.py` (YouTube transcript fetching)
- Created `04_chunk_transcript_v1.py` (Transcript chunking for embeddings)
- Chunks include: chunk_id, timestamps, YouTube URLs, word counts
- Output format ready for Pinecone indexing

---

## CW06 Goal

Build the embedding and vector database scripts that enable semantic search. By the end of this session, we should have working scripts for:

1. **05_generate_embeddings_v1.py** - Generate OpenAI embeddings from chunks
2. **06_upload_pinecone_v1.py** - Upload embeddings to Pinecone vector database

These scripts complete the "intelligence layer" - making sermon content semantically searchable.

---

## Script 5: 05_generate_embeddings_v1.py

### Purpose
Generate vector embeddings from transcript chunks using OpenAI's embedding API. These embeddings capture semantic meaning for similarity search.

### Requirements

**Input:**
- Chunk JSON file (from script 04)
- Or directory of chunk files
- Or path to `chunk_report.json` for batch processing

**Output:**
- `data/embeddings/{video_id}_embeddings.json` - Chunks with embeddings
- `data/embeddings/embedding_report.json` - Batch processing report with costs

**Functionality:**
1. Load chunk JSON files
2. Extract text from each chunk
3. Generate embeddings via OpenAI API (text-embedding-3-small)
4. Batch API calls for efficiency (respect rate limits)
5. Track token usage and estimate costs
6. Store embeddings with chunk metadata
7. Support incremental processing (skip existing)

**CLI Interface:**
```bash
# Generate embeddings for single video
python 05_generate_embeddings_v1.py --video-id abc123xyz

# Generate from chunk report
python 05_generate_embeddings_v1.py --from-report data/chunks/chunk_report.json

# Process all chunk files
python 05_generate_embeddings_v1.py --all

# Auto-detect input
python 05_generate_embeddings_v1.py

# Custom batch size
python 05_generate_embeddings_v1.py --video-id abc123 --batch-size 50

# Force re-generate
python 05_generate_embeddings_v1.py --video-id abc123 --force

# Dry run (estimate cost without calling API)
python 05_generate_embeddings_v1.py --all --dry-run

# Output JSON to stdout (single video)
python 05_generate_embeddings_v1.py --video-id abc123 --json
```

**Output Format (embeddings JSON):**
```json
{
  "video_id": "abc123xyz",
  "title": "Sunday Sermon: Finding Peace",
  "generated_at": "2024-12-31T11:00:00",
  "model": "text-embedding-3-small",
  "dimensions": 1536,
  "total_chunks": 24,
  "total_tokens": 12500,
  "estimated_cost_usd": 0.00025,
  "chunks": [
    {
      "chunk_id": "abc123xyz_chunk_001",
      "chunk_index": 0,
      "text": "Good morning everyone...",
      "start_time": 0.0,
      "end_time": 120.0,
      "timestamp_formatted": "0:00",
      "youtube_url": "https://www.youtube.com/watch?v=abc123xyz&t=0",
      "word_count": 245,
      "token_count": 312,
      "embedding": [0.0123, -0.0456, 0.0789, ...]
    }
  ]
}
```

### Key Considerations

**OpenAI Embedding Models:**
| Model | Dimensions | Price per 1M tokens |
|-------|------------|---------------------|
| text-embedding-3-small | 1536 | $0.02 |
| text-embedding-3-large | 3072 | $0.13 |
| text-embedding-ada-002 | 1536 | $0.10 |

**Recommendation:** Use `text-embedding-3-small` - best price/performance ratio.

**Batch Processing:**
- OpenAI allows up to 2048 embeddings per request
- Recommend batch size of 100 for reliability
- Implement retry logic for rate limits

**Token Estimation:**
- ~4 characters per token (rough estimate)
- Or use tiktoken library for accurate counts

### Existing Code Reference
Miles has working embedding code in `05_generate_embeddings_v2.py` with:
- Batch processing with progress tracking
- Cost estimation before and after
- Incremental mode (skip existing)
- Rate limit handling

Adapt patterns from this existing code.

---

## Script 6: 06_upload_pinecone_v1.py

### Purpose
Upload embeddings to Pinecone vector database, enabling semantic search queries. Each church gets its own namespace for data isolation.

### Requirements

**Input:**
- Embedding JSON file (from script 05)
- Or directory of embedding files
- Or path to `embedding_report.json` for batch processing

**Output:**
- Vectors uploaded to Pinecone
- `data/embeddings/pinecone_report.json` - Upload report with stats

**Functionality:**
1. Load embedding JSON files
2. Connect to Pinecone index
3. Format vectors with metadata
4. Upsert in batches (respect Pinecone limits)
5. Use church namespace for isolation
6. Verify upload with test query
7. Support incremental uploads (detect existing)

**CLI Interface:**
```bash
# Upload single video embeddings
python 06_upload_pinecone_v1.py --video-id abc123xyz

# Upload from embedding report
python 06_upload_pinecone_v1.py --from-report data/embeddings/embedding_report.json

# Upload all embedding files
python 06_upload_pinecone_v1.py --all

# Auto-detect input
python 06_upload_pinecone_v1.py

# Specify namespace (override config)
python 06_upload_pinecone_v1.py --video-id abc123 --namespace crossconnection

# Delete before upload (replace existing)
python 06_upload_pinecone_v1.py --video-id abc123 --replace

# Test query after upload
python 06_upload_pinecone_v1.py --video-id abc123 --test-query "finding peace"

# Dry run (validate without uploading)
python 06_upload_pinecone_v1.py --all --dry-run
```

**Pinecone Vector Format:**
```python
{
    "id": "abc123xyz_chunk_001",
    "values": [0.0123, -0.0456, ...],  # 1536 dimensions
    "metadata": {
        "video_id": "abc123xyz",
        "title": "Sunday Sermon: Finding Peace",
        "chunk_index": 0,
        "start_time": 0.0,
        "end_time": 120.0,
        "timestamp_formatted": "0:00",
        "youtube_url": "https://www.youtube.com/watch?v=abc123xyz&t=0",
        "text": "Good morning everyone...",  # Truncated for metadata limits
        "word_count": 245
    }
}
```

### Key Considerations

**Pinecone Limits:**
- Max 1000 vectors per upsert
- Metadata: 40KB per vector
- Text in metadata should be truncated (~500 chars)

**Namespace Strategy:**
- Each church gets own namespace: `crossconnection`, `firstbaptist`, etc.
- Enables multi-tenant architecture
- Easy to delete/reset per church

**Test Query:**
After upload, run a simple semantic search to verify:
```python
results = index.query(
    namespace="crossconnection",
    vector=embed("What does the Bible say about anxiety?"),
    top_k=3,
    include_metadata=True
)
```

### Existing Code Reference
Miles has working Pinecone code in `06_upload_to_pinecone_v2.py` with:
- Batch upsert with progress
- Namespace handling
- Metadata truncation
- Test search verification

Adapt patterns from this existing code.

---

## Documentation Requirements

Follow the same comprehensive header documentation pattern from CW04/CW05:

```python
#!/usr/bin/env python3
"""
05_generate_embeddings_v1.py
Generate OpenAI embeddings from transcript chunks.

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
CHUNKS_DIR = DATA_DIR / "chunks"
EMBEDDINGS_DIR = DATA_DIR / "embeddings"

# OpenAI Settings
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536
EMBEDDING_BATCH_SIZE = 100

# Pinecone Settings
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX = "crossconnection-sermons"
PINECONE_NAMESPACE = CHURCH_SLUG
PINECONE_BATCH_SIZE = 100
```

---

## Dependencies to Add

```
# requirements.txt additions
openai>=1.0.0
pinecone>=5.0.0
tiktoken>=0.5.0  # For accurate token counting
```

---

## Success Criteria for CW06

By the end of this context window:

- [ ] `05_generate_embeddings_v1.py` generates embeddings from chunk files
- [ ] `05_generate_embeddings_v1.py` tracks token usage and costs
- [ ] `05_generate_embeddings_v1.py` supports batch processing
- [ ] `05_generate_embeddings_v1.py` has dry-run mode for cost estimation
- [ ] `06_upload_pinecone_v1.py` uploads vectors to Pinecone
- [ ] `06_upload_pinecone_v1.py` uses namespace for church isolation
- [ ] `06_upload_pinecone_v1.py` includes test query verification
- [ ] `06_upload_pinecone_v1.py` truncates metadata appropriately
- [ ] Both scripts follow established documentation patterns
- [ ] Both scripts have working CLI interfaces

---

## Pipeline Integration

After CW06, the complete intelligence pipeline will be:

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
        │
        ▼
[CW07: 07_generate_ai_content_v1.py - summaries, scriptures, topics]
[CW07: 08_generate_discussion_guide_v1.py - small group PDF]
[CW08: 09_full_pipeline_v1.py - orchestration]
```

---

## Out of Scope for CW06

- AI content generation (summaries, scriptures) - CW07
- Discussion guide PDF generation - CW07
- Full pipeline orchestration - CW08
- Search API endpoint - CW08+
- Flask server
- WordPress plugin

---

## Cost Estimates

For a typical 45-minute sermon:
- ~7,500 words → ~9,000 tokens
- ~23 chunks (2 min each)
- Embedding cost: ~$0.0002 (text-embedding-3-small)

For 100 sermons (2 years of weekly content):
- Total embedding cost: ~$0.02
- Pinecone: Free tier (up to 100K vectors)

---

## File Locations

Scripts should be created in:
```
/home/claude/preachcaster/_templates/tools/
├── 01_monitor_youtube_v1.py   (exists)
├── 02_extract_audio_v1.py     (exists)
├── 03_fetch_transcript_v1.py  (exists)
├── 04_chunk_transcript_v1.py  (exists)
├── 05_generate_embeddings_v1.py  ◄── NEW
├── 06_upload_pinecone_v1.py      ◄── NEW
└── versions/
```

---

## How to Start

1. Review existing embedding/Pinecone code patterns from Miles' YouTube AI Search project
2. Create `05_generate_embeddings_v1.py` with full documentation
3. Test with sample chunk data (may need mock data if API keys unavailable)
4. Create `06_upload_pinecone_v1.py` with full documentation
5. Test Pinecone upload with sample embeddings
6. Verify test query returns expected results

---

## Questions to Resolve in CW06

1. **Token counting:** Use tiktoken for accuracy or estimate from character count?
   - **Recommendation:** Include tiktoken but fall back to estimation if unavailable

2. **Metadata text truncation:** How much text to store in Pinecone metadata?
   - **Recommendation:** First 500 characters (for preview in search results)

3. **Vector deletion strategy:** How to handle re-indexing?
   - **Recommendation:** Delete by video_id prefix before re-uploading

4. **Error recovery:** What if upload fails mid-batch?
   - **Recommendation:** Track uploaded chunk IDs, resume from last success

---

*Ready to begin embedding and vector search development.*
