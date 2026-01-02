# CW07 Prompt: PreachCaster AI Content & Discussion Guide Scripts

**Project:** PreachCaster  
**Context Window:** CW07  
**Objective:** Build AI content generation and small group discussion guide scripts

---

## Context for Claude

You are continuing development of PreachCaster, an automated sermon podcasting platform for churches. Review the Project Bible and previous CW summaries for full context.

**Quick Summary:**
- PreachCaster monitors YouTube for new sermon uploads
- Automatically extracts audio, processes transcripts, generates AI content
- Publishes to WordPress with RSS feeds for podcast platforms
- Enables semantic search across all sermon content

**Tech Stack:** Python, Flask, OpenAI, Pinecone, yt-dlp, WordPress

**CW06 Accomplishments:**
- Created `05_generate_embeddings_v1.py` (OpenAI embedding generation)
- Created `06_upload_pinecone_v1.py` (Pinecone vector database upload)
- Full unit test coverage (30 tests total)
- Dry-run mode for cost estimation
- Test query verification for semantic search

---

## CW07 Goal

Build the AI content generation scripts that create value-added content from sermon transcripts. By the end of this session, we should have working scripts for:

1. **07_generate_ai_content_v1.py** - Generate summaries, extract scriptures, tag topics
2. **08_generate_discussion_guide_v1.py** - Create small group study guide PDFs

These scripts complete the "Premium tier" features that differentiate PreachCaster.

---

## Script 7: 07_generate_ai_content_v1.py

### Purpose
Generate AI-powered content enhancements from sermon transcripts using GPT-4o-mini. This includes summaries for RSS feeds, scripture extraction, and topic tagging.

### Requirements

**Input:**
- Transcript JSON file (from script 03)
- Or directory of transcript files
- Or path to `transcript_report.json` for batch processing

**Output:**
- `data/ai_content/{video_id}_ai_content.json` - Generated AI content
- `data/ai_content/ai_content_report.json` - Batch processing report with costs

**Functionality:**
1. Load transcript text
2. Generate sermon summary (2-3 sentences for RSS feed)
3. Extract primary scripture passage
4. Identify supporting scripture references
5. Generate topic tags (3-5 themes)
6. Extract "big idea" (one memorable sentence)
7. Track token usage and estimate costs
8. Support incremental processing (skip existing)

**CLI Interface:**
```bash
# Generate AI content for single video
python 07_generate_ai_content_v1.py --video-id abc123xyz

# Generate from transcript report
python 07_generate_ai_content_v1.py --from-report data/transcripts/transcript_report.json

# Process all transcript files
python 07_generate_ai_content_v1.py --all

# Auto-detect input
python 07_generate_ai_content_v1.py

# Force re-generate
python 07_generate_ai_content_v1.py --video-id abc123 --force

# Dry run (estimate cost without calling API)
python 07_generate_ai_content_v1.py --all --dry-run

# Output JSON to stdout (single video)
python 07_generate_ai_content_v1.py --video-id abc123 --json
```

**Output Format (ai_content JSON):**
```json
{
  "video_id": "abc123xyz",
  "title": "Sunday Sermon: Finding Peace",
  "generated_at": "2025-01-01T12:00:00",
  "model": "gpt-4o-mini",
  "summary": "Pastor explores how to find lasting peace in anxious times by trusting God's sovereignty. Drawing from Philippians 4, he shares three practical steps for cultivating inner calm.",
  "big_idea": "Peace isn't the absence of storms, but the presence of God in the midst of them.",
  "primary_scripture": {
    "reference": "Philippians 4:6-7",
    "text": "Do not be anxious about anything, but in every situation, by prayer and petition, with thanksgiving, present your requests to God."
  },
  "supporting_scriptures": [
    {"reference": "Isaiah 26:3", "text": "You will keep in perfect peace those whose minds are steadfast..."},
    {"reference": "John 14:27", "text": "Peace I leave with you; my peace I give you..."}
  ],
  "topics": ["peace", "anxiety", "prayer", "trust", "sovereignty"],
  "tokens_used": {
    "prompt": 2500,
    "completion": 350,
    "total": 2850
  },
  "estimated_cost_usd": 0.0006
}
```

### Key Considerations

**OpenAI Model Selection:**
| Model | Input $/1M | Output $/1M | Best For |
|-------|------------|-------------|----------|
| gpt-4o-mini | $0.15 | $0.60 | Cost-effective, good quality |
| gpt-4o | $2.50 | $10.00 | Highest quality |
| gpt-3.5-turbo | $0.50 | $1.50 | Legacy, fast |

**Recommendation:** Use `gpt-4o-mini` - best cost/quality balance for structured extraction.

**Prompt Engineering:**
- Use system prompt to establish context (sermon analysis expert)
- Request JSON output format
- Include examples for consistent formatting
- Separate prompts for different tasks OR single comprehensive prompt

**Cost Estimation:**
- Typical sermon transcript: ~7,500 words → ~9,000 tokens input
- Expected output: ~500 tokens
- Cost per sermon: ~$0.0015 (gpt-4o-mini)

---

## Script 8: 08_generate_discussion_guide_v1.py

### Purpose
Generate printable PDF discussion guides for small groups from sermon content. This is a key Premium tier differentiator.

### Requirements

**Input:**
- AI content JSON file (from script 07)
- Transcript text for context
- Church branding info (logo, colors) from config

**Output:**
- `guides/{video_id}_discussion_guide.pdf` - Printable PDF
- `data/guides/guide_report.json` - Batch processing report

**Discussion Guide Contents:**
1. **Header** - Church logo, sermon title, date
2. **Opening** - Icebreaker question
3. **Scripture Focus** - Primary passage with text
4. **Sermon Summary** - 2-3 sentence overview
5. **Big Idea** - Key takeaway
6. **Discussion Questions** - 5 questions referencing sermon content
7. **Application** - Weekly challenge
8. **Prayer Focus** - Prayer points
9. **Going Deeper** - Additional scripture references

**CLI Interface:**
```bash
# Generate guide for single video
python 08_generate_discussion_guide_v1.py --video-id abc123xyz

# Generate from AI content report
python 08_generate_discussion_guide_v1.py --from-report data/ai_content/ai_content_report.json

# Process all AI content files
python 08_generate_discussion_guide_v1.py --all

# Auto-detect input
python 08_generate_discussion_guide_v1.py

# Custom branding
python 08_generate_discussion_guide_v1.py --video-id abc123 --logo path/to/logo.png

# Force re-generate
python 08_generate_discussion_guide_v1.py --video-id abc123 --force
```

**PDF Layout:**
```
┌─────────────────────────────────────────────────────────────┐
│  [LOGO]     CROSS CONNECTION CHURCH                         │
│             Small Group Discussion Guide                     │
├─────────────────────────────────────────────────────────────┤
│  SERMON: Finding Peace in Anxious Times                      │
│  DATE: January 5, 2025  |  PASTOR: [Name]                   │
├─────────────────────────────────────────────────────────────┤
│  ICEBREAKER                                                  │
│  What's one thing that helps you feel calm when stressed?   │
├─────────────────────────────────────────────────────────────┤
│  SCRIPTURE FOCUS                                             │
│  Philippians 4:6-7                                          │
│  "Do not be anxious about anything..."                      │
├─────────────────────────────────────────────────────────────┤
│  THE BIG IDEA                                                │
│  Peace isn't the absence of storms, but the presence of     │
│  God in the midst of them.                                  │
├─────────────────────────────────────────────────────────────┤
│  DISCUSSION QUESTIONS                                        │
│  1. What situations tend to make you most anxious?          │
│  2. How does prayer help you deal with anxiety?             │
│  3. ...                                                     │
├─────────────────────────────────────────────────────────────┤
│  THIS WEEK'S CHALLENGE                                       │
│  Each morning, spend 5 minutes in prayer before checking    │
│  your phone or email.                                       │
├─────────────────────────────────────────────────────────────┤
│  PRAYER FOCUS                                                │
│  • Thank God for His peace that surpasses understanding     │
│  • Ask for strength to trust Him in anxious moments         │
├─────────────────────────────────────────────────────────────┤
│  GOING DEEPER                                                │
│  Isaiah 26:3  |  John 14:27  |  Matthew 6:25-34             │
└─────────────────────────────────────────────────────────────┘
```

### Key Considerations

**PDF Generation Options:**
| Library | Pros | Cons |
|---------|------|------|
| ReportLab | Pure Python, powerful | Steeper learning curve |
| WeasyPrint | HTML/CSS to PDF | Requires system deps |
| FPDF2 | Simple, lightweight | Less features |
| pdfkit | wkhtmltopdf wrapper | External dependency |

**Recommendation:** Use `FPDF2` for simplicity, or `ReportLab` for more control.

**AI-Generated Content:**
The discussion questions and icebreaker should be generated by GPT-4o-mini as part of script 07 OR generated here. Consider:
- Option A: Add to script 07 output (one API call per sermon)
- Option B: Generate in script 08 (separate concern, but extra API call)

**Recommendation:** Add discussion guide content to script 07's AI generation.

**Updated Script 07 Output:**
```json
{
  "video_id": "abc123xyz",
  "...existing fields...",
  "discussion_guide": {
    "icebreaker": "What's one thing that helps you feel calm when life gets stressful?",
    "questions": [
      "What situations tend to make you most anxious? How do you typically respond?",
      "Read Philippians 4:6-7. What does Paul say is the antidote to anxiety?",
      "Pastor mentioned that peace comes from God's presence, not our circumstances. Do you agree?",
      "How can prayer with thanksgiving change our perspective on our problems?",
      "What's one area of your life where you need to experience more of God's peace?"
    ],
    "application": "Each morning this week, spend 5 minutes in prayer before checking your phone or email. Bring your anxieties to God with thanksgiving.",
    "prayer_points": [
      "Thank God for His peace that surpasses understanding",
      "Ask for strength to trust Him in anxious moments",
      "Pray for each other's specific concerns shared today"
    ]
  }
}
```

---

## Documentation Requirements

Follow the same comprehensive header documentation pattern from previous scripts:

```python
#!/usr/bin/env python3
"""
07_generate_ai_content_v1.py
Generate AI-powered content from sermon transcripts.

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
AI_CONTENT_DIR = DATA_DIR / "ai_content"
GUIDES_DIR = PROJECT_ROOT / "guides"

# OpenAI Settings
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
AI_MODEL = "gpt-4o-mini"

# Church Branding (for PDF)
CHURCH_NAME = "Cross Connection Church"
CHURCH_LOGO_PATH = PROJECT_ROOT / "assets" / "logo.png"
CHURCH_PRIMARY_COLOR = "#1a365d"  # Navy blue
CHURCH_SECONDARY_COLOR = "#2b6cb0"  # Lighter blue
```

---

## Dependencies to Add

```
# requirements.txt additions
fpdf2>=2.7.0  # PDF generation
# OR
reportlab>=4.0.0  # Alternative PDF library
```

---

## Success Criteria for CW07

By the end of this context window:

- [ ] `07_generate_ai_content_v1.py` generates summaries from transcripts
- [ ] `07_generate_ai_content_v1.py` extracts primary and supporting scriptures
- [ ] `07_generate_ai_content_v1.py` generates topic tags
- [ ] `07_generate_ai_content_v1.py` generates discussion guide content
- [ ] `07_generate_ai_content_v1.py` has dry-run mode for cost estimation
- [ ] `08_generate_discussion_guide_v1.py` creates formatted PDF guides
- [ ] `08_generate_discussion_guide_v1.py` includes all required sections
- [ ] `08_generate_discussion_guide_v1.py` supports church branding
- [ ] Both scripts follow established documentation patterns
- [ ] Both scripts have working CLI interfaces

---

## Pipeline Integration

After CW07, the complete content pipeline will be:

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
        ├──────────────────────────────────┐
        ▼                                  ▼
04_chunk_transcript_v1.py      07_generate_ai_content_v1.py  ◄── CW07
        │                                  │
        ▼                                  ▼
05_generate_embeddings_v1.py   08_generate_discussion_guide_v1.py  ◄── CW07
        │                                  │
        ▼                                  ▼
06_upload_pinecone_v1.py           guides/{video_id}.pdf
        │
        ▼
    Pinecone (searchable)

[CW08: 09_full_pipeline_v1.py - Orchestration]
[CW08: 10_wordpress_publish_v1.py - WordPress integration]
```

---

## Out of Scope for CW07

- Full pipeline orchestration - CW08
- WordPress publishing - CW08
- Flask search API - CW09+
- WordPress plugin development - CW09+

---

## Cost Estimates

For a typical 45-minute sermon using gpt-4o-mini:
- Input: ~9,000 tokens ($0.00135)
- Output: ~800 tokens ($0.00048)
- **Total per sermon: ~$0.002**

For 100 sermons:
- Total AI content cost: ~$0.20

---

## Prompt Templates

### System Prompt for AI Content Generation
```
You are an expert at analyzing Christian sermon content. Your task is to extract 
key information and generate helpful content for church communications and small 
group discussions.

Always respond in valid JSON format. Be accurate with scripture references - 
verify the book, chapter, and verse numbers are correct. Generate content that 
is theologically sound and practically applicable.
```

### User Prompt Template
```
Analyze this sermon transcript and generate the following:

1. SUMMARY: A 2-3 sentence summary suitable for a podcast description
2. BIG_IDEA: One memorable sentence capturing the main point
3. PRIMARY_SCRIPTURE: The main Bible passage referenced (book chapter:verses)
4. SUPPORTING_SCRIPTURES: Up to 3 additional passages mentioned
5. TOPICS: 3-5 theme tags (single words like "grace", "prayer", "anxiety")
6. ICEBREAKER: A casual opening question for small group discussion
7. DISCUSSION_QUESTIONS: 5 thoughtful questions that reference sermon content
8. APPLICATION: A specific, actionable challenge for the week
9. PRAYER_POINTS: 2-3 specific prayer focus items

TRANSCRIPT:
{transcript_text}

Respond with valid JSON only.
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
├── 07_generate_ai_content_v1.py     ◄── NEW
├── 08_generate_discussion_guide_v1.py  ◄── NEW
└── versions/
```

---

## How to Start

1. Create `07_generate_ai_content_v1.py` with comprehensive prompts
2. Test with sample transcript data
3. Create `08_generate_discussion_guide_v1.py` with PDF generation
4. Test PDF output with sample AI content
5. Verify both scripts integrate with existing pipeline

---

## Questions to Resolve in CW07

1. **Single prompt vs. multiple prompts?**
   - **Recommendation:** Single comprehensive prompt for efficiency

2. **PDF library choice?**
   - **Recommendation:** FPDF2 for simplicity, can upgrade to ReportLab later

3. **Where to store discussion guide content?**
   - **Recommendation:** In script 07 output (ai_content.json), consumed by script 08

4. **How to handle missing AI content?**
   - **Recommendation:** Script 08 should gracefully skip or generate minimal PDF

5. **Branding assets handling?**
   - **Recommendation:** Optional logo, fallback to text-only header

---

*Ready to begin AI content generation and discussion guide development.*
