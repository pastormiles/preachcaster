# CW07 Summary: PreachCaster AI Content & Discussion Guide Scripts

**Context Window:** CW07  
**Date:** January 1, 2025  
**Focus:** AI content generation and PDF discussion guide creation

---

## 1. Session Overview

This context window built the Premium tier AI features that transform basic transcript data into value-added content for churches. These scripts complete the "intelligence layer" of PreachCaster.

### Key Outcomes
- ✅ Created `07_generate_ai_content_v1.py` - AI content generation from transcripts
- ✅ Created `08_generate_discussion_guide_v1.py` - PDF discussion guide generation
- ✅ Comprehensive documentation following established patterns
- ✅ Full CLI interfaces with all required options
- ✅ Unit tests: 31 tests for script 07, 35 tests for script 08 (66 total)
- ✅ Integration test demonstrating full workflow
- ✅ Dry-run mode for cost estimation
- ✅ Church branding support for PDFs

---

## 2. Scripts Created

### 07_generate_ai_content_v1.py

**Location:** `_templates/tools/07_generate_ai_content_v1.py`  
**Lines:** ~600  
**Purpose:** Generate AI-powered content from sermon transcripts using OpenAI GPT models

**Features:**
- Comprehensive prompt engineering for sermon analysis
- Single API call generates all content types
- Support for gpt-4o-mini, gpt-4o, gpt-3.5-turbo
- Token counting with tiktoken (fallback estimation)
- Cost tracking and estimation
- Dry-run mode for cost preview
- Batch processing with detailed reports
- Incremental processing (skip existing)

**Generated Content:**
| Content Type | Description |
|--------------|-------------|
| Summary | 2-3 sentence description for RSS feeds |
| Big Idea | One memorable, quotable sentence |
| Primary Scripture | Main Bible passage with text |
| Supporting Scriptures | Up to 3 additional passages |
| Topics | 3-5 theme tags for filtering |
| Icebreaker | Opening question for small groups |
| Discussion Questions | 5 thoughtful questions |
| Application | Weekly challenge |
| Prayer Points | 2-3 prayer focus items |

**Output Files:**
- `data/ai_content/{video_id}_ai_content.json` - Generated content
- `data/ai_content/ai_content_report.json` - Batch report with costs

**Usage Examples:**
```bash
# Generate AI content for single video
python 07_generate_ai_content_v1.py --video-id abc123xyz

# Dry run to estimate cost
python 07_generate_ai_content_v1.py --all --dry-run

# Process from transcript report
python 07_generate_ai_content_v1.py --from-report data/transcripts/transcript_report.json

# Custom model
python 07_generate_ai_content_v1.py --video-id abc123 --model gpt-4o
```

---

### 08_generate_discussion_guide_v1.py

**Location:** `_templates/tools/08_generate_discussion_guide_v1.py`  
**Lines:** ~650  
**Purpose:** Generate printable PDF discussion guides for small groups

**Features:**
- Professional PDF layout with sections
- Church branding support (name, logo, colors)
- Scripture focus box with highlighting
- Big idea callout box
- Numbered discussion questions
- Prayer focus bullet points
- Going deeper section with scripture references
- Batch processing with reports

**PDF Sections:**
1. Header (church name, logo, sermon title, date)
2. Scripture Focus (primary passage in styled box)
3. The Big Idea (highlighted callout)
4. Icebreaker
5. Discussion Questions (numbered list)
6. This Week's Challenge
7. Prayer Focus (bullet points)
8. Going Deeper (supporting scriptures)

**Output Files:**
- `guides/{video_id}_discussion_guide.pdf` - Printable PDF
- `data/guides/guide_report.json` - Batch report

**Usage Examples:**
```bash
# Generate guide for single video
python 08_generate_discussion_guide_v1.py --video-id abc123xyz

# Custom branding
python 08_generate_discussion_guide_v1.py --video-id abc123 --church-name "My Church" --logo logo.png

# Process all AI content files
python 08_generate_discussion_guide_v1.py --all

# Custom colors
python 08_generate_discussion_guide_v1.py --video-id abc123 --primary-color "#ff0000"
```

---

## 3. Pipeline Integration

The AI content pipeline is now complete:

```
03_fetch_transcript_v1.py
        │
        ▼
    data/transcripts/{video_id}.json
        │
        ├──────────────────────────────┐
        ▼                              ▼
04_chunk_transcript_v1.py    07_generate_ai_content_v1.py  ◄── CW07
        │                              │
        ▼                              ▼
05_generate_embeddings_v1.py data/ai_content/{video_id}_ai_content.json
        │                              │
        ▼                              ▼
06_upload_pinecone_v1.py     08_generate_discussion_guide_v1.py  ◄── CW07
        │                              │
        ▼                              ▼
    Pinecone (searchable)      guides/{video_id}_discussion_guide.pdf
```

---

## 4. Technical Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| AI Model | gpt-4o-mini default | Best cost/quality balance at $0.002/sermon |
| Prompt Strategy | Single comprehensive prompt | More efficient than multiple API calls |
| PDF Library | FPDF2 | Pure Python, no system deps, simple API |
| Bullet Character | Dash (-) | Universal font support |
| Content Scope | All content in one JSON | Easier downstream processing |

---

## 5. Cost Analysis

### AI Content Generation (gpt-4o-mini)

| Model | Input $/1M | Output $/1M |
|-------|------------|-------------|
| gpt-4o-mini | $0.15 | $0.60 |
| gpt-4o | $2.50 | $10.00 |
| gpt-3.5-turbo | $0.50 | $1.50 |

**Typical Costs:**
| Content | Tokens | Cost |
|---------|--------|------|
| 45-min sermon (input) | ~9,000 | $0.00135 |
| Generated content (output) | ~800 | $0.00048 |
| **Total per sermon** | ~9,800 | **~$0.002** |
| 100 sermons | ~980,000 | ~$0.20 |

---

## 6. Output Formats

### AI Content JSON Structure
```json
{
  "video_id": "abc123xyz",
  "title": "Finding Peace in Anxious Times",
  "generated_at": "2025-01-01T12:00:00",
  "model": "gpt-4o-mini",
  "summary": "Pastor explores how to find lasting peace...",
  "big_idea": "Peace isn't the absence of storms...",
  "primary_scripture": {
    "reference": "Philippians 4:6-7",
    "text": "Do not be anxious about anything..."
  },
  "supporting_scriptures": [
    {"reference": "Isaiah 26:3", "text": "..."}
  ],
  "topics": ["peace", "anxiety", "prayer", "trust"],
  "discussion_guide": {
    "icebreaker": "What helps you feel calm when stressed?",
    "questions": ["Q1?", "Q2?", "Q3?", "Q4?", "Q5?"],
    "application": "Each morning, spend 5 minutes in prayer...",
    "prayer_points": ["Thank God for...", "Ask for..."]
  },
  "tokens_used": {
    "prompt_tokens": 2500,
    "completion_tokens": 450,
    "total_tokens": 2950
  },
  "estimated_cost_usd": 0.00065
}
```

---

## 7. Testing Summary

### Script 07 Tests (31 tests)
- ✅ Token counting with estimation fallback
- ✅ Cost estimation for different models
- ✅ Cost formatting
- ✅ File loading/saving
- ✅ Transcript text extraction (multiple formats)
- ✅ Dry-run estimation
- ✅ AI content existence checking
- ✅ File discovery
- ✅ CLI argument parsing
- ✅ Model pricing configuration

### Script 08 Tests (35 tests)
- ✅ Color conversion (hex to RGB)
- ✅ File loading operations
- ✅ AI content file discovery
- ✅ Guide existence checking
- ✅ Report saving/loading
- ✅ PDF generation (success, minimal content, custom colors)
- ✅ Process video (missing content, skip existing, missing discussion guide)
- ✅ Input detection (single, multiple, all)
- ✅ CLI argument parsing
- ✅ PDF class methods (sections, scripture box, big idea box)
- ✅ Batch processing

### Integration Test
- ✅ Load transcript → estimate cost → load AI content → generate PDF
- ✅ Generated PDF: 2,599 bytes

---

## 8. Files Delivered

| File | Location | Purpose |
|------|----------|---------|
| `07_generate_ai_content_v1.py` | `_templates/tools/` | AI content generation |
| `08_generate_discussion_guide_v1.py` | `_templates/tools/` | PDF guide generation |
| `config.py` | `test_project/config/` | Test configuration |
| `test123xyz.json` | `test_project/data/transcripts/` | Sample transcript |
| `test123xyz_ai_content.json` | `test_project/data/ai_content/` | Sample AI content |
| `test123xyz_discussion_guide.pdf` | `test_project/guides/` | Sample PDF guide |
| `test_script_07.py` | `test_project/` | Unit tests (31 tests) |
| `test_script_08.py` | `test_project/` | Unit tests (35 tests) |

---

## 9. Directory Structure

```
preachcaster/
├── _templates/
│   ├── config/
│   └── tools/
│       ├── 01_monitor_youtube_v1.py     (CW04)
│       ├── 02_extract_audio_v1.py       (CW04)
│       ├── 03_fetch_transcript_v1.py    (CW05)
│       ├── 04_chunk_transcript_v1.py    (CW05)
│       ├── 05_generate_embeddings_v1.py (CW06)
│       ├── 06_upload_pinecone_v1.py     (CW06)
│       ├── 07_generate_ai_content_v1.py    (CW07) ◄── NEW
│       ├── 08_generate_discussion_guide_v1.py (CW07) ◄── NEW
│       └── versions/
│
└── test_project/
    ├── config/
    │   └── config.py
    ├── tools/
    │   ├── 07_generate_ai_content_v1.py
    │   └── 08_generate_discussion_guide_v1.py
    ├── data/
    │   ├── transcripts/
    │   │   └── test123xyz.json
    │   ├── ai_content/
    │   │   └── test123xyz_ai_content.json
    │   └── guides/
    ├── guides/
    │   └── test123xyz_discussion_guide.pdf
    ├── test_script_07.py
    └── test_script_08.py
```

---

## 10. Success Criteria Status

| Criterion | Status |
|-----------|--------|
| Script 07 generates summaries from transcripts | ✅ Complete |
| Script 07 extracts primary and supporting scriptures | ✅ Complete |
| Script 07 generates topic tags | ✅ Complete |
| Script 07 generates discussion guide content | ✅ Complete |
| Script 07 has dry-run mode for cost estimation | ✅ Complete |
| Script 08 creates formatted PDF guides | ✅ Complete |
| Script 08 includes all required sections | ✅ Complete |
| Script 08 supports church branding | ✅ Complete |
| Both scripts follow documentation patterns | ✅ Complete |
| Both scripts have working CLI interfaces | ✅ Complete |

---

## 11. Dependencies Added

```
# requirements.txt additions
fpdf2>=2.7.0          # PDF generation
pillow>=10.0.0        # Image processing (for logos)
tiktoken>=0.5.0       # Token counting (optional)
```

---

## 12. Local Testing Instructions

```bash
# Navigate to project
cd ~/python/nomion/PreachCaster/[church_project]
source venv/bin/activate

# Test AI content generation (requires OpenAI API key)
export OPENAI_API_KEY="your-key-here"
python tools/07_generate_ai_content_v1.py --video-id [video_id] --dry-run
python tools/07_generate_ai_content_v1.py --video-id [video_id]

# Test discussion guide generation
python tools/08_generate_discussion_guide_v1.py --video-id [video_id]

# Run full content pipeline
python tools/07_generate_ai_content_v1.py --from-report data/transcripts/transcript_report.json
python tools/08_generate_discussion_guide_v1.py --from-report data/ai_content/ai_content_report.json
```

---

## 13. Open Items for CW08

### To Build Next
1. `09_full_pipeline_v1.py` - Orchestrate all scripts for single video
2. `10_wordpress_publish_v1.py` - Publish episode to WordPress

### Technical Considerations
- Pipeline orchestration with error handling
- WordPress REST API integration
- RSS feed generation
- Retry logic for failed steps

---

## 14. Key Learnings

1. **Single prompt is more efficient** - One comprehensive prompt cheaper than multiple calls
2. **Font compatibility matters** - Use standard characters for PDF generation
3. **FPDF2 is lightweight but capable** - Good balance for simple PDF needs
4. **Token estimation works well** - ~4 chars/token is reasonable fallback
5. **Dry-run is essential** - Always estimate costs before API calls

---

*Document created: CW07*  
*Next context window: CW08 — Pipeline Orchestration & WordPress Publishing*
