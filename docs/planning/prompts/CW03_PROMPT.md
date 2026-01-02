# CW03 Prompt: PreachCaster Local Proof of Concept

**Project:** PreachCaster  
**Context Window:** CW03  
**Objective:** Build a working local proof of concept that demonstrates the core pipeline

---

## Context for Claude

You are continuing development of PreachCaster, an automated sermon podcasting service for churches. Review the Project Bible (PROJECT_BIBLE.md) and CW02 Summary (CW02_SUMMARY.md) for full context.

**Quick Summary:**
- PreachCaster monitors YouTube channels and automatically creates podcast episodes
- Three pricing tiers: Core ($99), Pro ($149), Premium ($199)
- Tech stack: Node.js, GCP (Cloud Run, Cloud SQL, Cloud Storage), Pinecone, OpenAI
- WordPress plugin receives episodes and generates RSS feeds

---

## CW03 Goal

Build a **local proof of concept** that demonstrates the entire pipeline works before deploying to GCP. By the end of this session, we should be able to:

1. Give the script a YouTube video URL
2. Have it extract audio, fetch transcript, generate embeddings
3. Output everything needed to create a podcast episode

This is **not** about WordPress integration or GCP deployment yet. It's about proving the core automation works.

---

## Deliverables for CW03

### 1. Project Scaffolding
```
preachcaster/
├── poc/                        # Proof of concept scripts
│   ├── package.json
│   ├── .env.example
│   ├── 01-fetch-youtube-rss.js    # Test YouTube feed parsing
│   ├── 02-extract-audio.js        # Test yt-dlp extraction
│   ├── 03-fetch-transcript.js     # Test transcript retrieval
│   ├── 04-generate-embeddings.js  # Test OpenAI embeddings
│   ├── 05-store-pinecone.js       # Test Pinecone storage
│   ├── 06-search-pinecone.js      # Test semantic search
│   ├── 07-generate-ai-content.js  # Test summaries, scriptures, topics
│   ├── 08-generate-discussion-guide.js  # Test guide generation
│   └── full-pipeline.js           # Run complete pipeline on a video
├── docs/
│   ├── PROJECT_BIBLE.md
│   ├── CW02_SUMMARY.md
│   └── CW03_SUMMARY.md           # To be created at end of session
└── README.md
```

### 2. Individual Component Tests

Each numbered script should work independently:

**01-fetch-youtube-rss.js**
- Input: YouTube channel ID
- Output: List of recent videos with IDs, titles, dates
- Proves: We can detect new uploads

**02-extract-audio.js**
- Input: YouTube video URL
- Output: MP3 file in local directory
- Proves: yt-dlp works, audio extraction works

**03-fetch-transcript.js**
- Input: YouTube video ID
- Output: Transcript JSON with timestamps
- Proves: We can get captions programmatically

**04-generate-embeddings.js**
- Input: Transcript text
- Output: Array of embedding vectors
- Proves: OpenAI embeddings work, chunking works

**05-store-pinecone.js**
- Input: Embeddings with metadata
- Output: Confirmation of upsert
- Proves: Pinecone storage works

**06-search-pinecone.js**
- Input: Search query string
- Output: Relevant transcript chunks with timestamps
- Proves: Semantic search works end-to-end

**07-generate-ai-content.js**
- Input: Transcript text
- Output: Summary, scriptures, topics (JSON)
- Proves: GPT-4o-mini content generation works

**08-generate-discussion-guide.js**
- Input: Transcript + metadata
- Output: Discussion guide JSON (or PDF if time permits)
- Proves: Guide generation works

### 3. Full Pipeline Script

**full-pipeline.js**
- Input: YouTube video URL
- Process: Runs all steps in sequence
- Output: Complete episode data package ready for WordPress

```javascript
// Example output structure
{
  youtube_id: "abc123xyz",
  title: "Finding Peace in the Storm",
  published_at: "2024-03-10T14:00:00Z",
  duration: 2520,
  audio: {
    local_path: "./output/abc123xyz.mp3",
    file_size: 42300000
  },
  transcript: [
    { start: 0, end: 5.2, text: "Good morning everyone..." },
    // ...
  ],
  embeddings_stored: true,
  pinecone_namespace: "test-church",
  ai_content: {
    summary: "Pastor John explores...",
    scriptures: {
      primary: "Mark 4:35-41",
      supporting: ["Philippians 4:6-7", "Isaiah 26:3"]
    },
    topics: ["peace", "anxiety", "faith", "trust"]
  },
  discussion_guide: {
    // Full guide structure
  }
}
```

---

## Technical Requirements

### Environment Variables (.env)

```
# YouTube (optional - RSS feed is public)
YOUTUBE_API_KEY=your_key_here

# OpenAI
OPENAI_API_KEY=sk-your-key-here

# Pinecone
PINECONE_API_KEY=your-key-here
PINECONE_INDEX=preachcaster-poc

# Test data
TEST_YOUTUBE_CHANNEL_ID=UCxxxxxxxxxx
TEST_YOUTUBE_VIDEO_ID=xxxxxxxxxxx
```

### Dependencies

```json
{
  "dependencies": {
    "rss-parser": "^3.13.0",
    "youtube-transcript": "^1.2.1",
    "openai": "^4.0.0",
    "@pinecone-database/pinecone": "^2.0.0",
    "dotenv": "^16.0.0"
  }
}
```

**Note:** yt-dlp must be installed separately on the system:
```bash
# macOS
brew install yt-dlp ffmpeg

# Ubuntu/Debian
sudo apt install yt-dlp ffmpeg

# Or via pip
pip install yt-dlp
```

---

## Testing Approach

### Use a Real Sermon Video

For testing, use an actual sermon from a public YouTube channel. Suggestions:
- Cross Connection Church channel (if available)
- Any public church sermon with auto-generated captions

### Pinecone Setup

Create a free Pinecone account and index:
- Index name: `preachcaster-poc`
- Dimensions: 1536 (for text-embedding-3-small)
- Metric: cosine

### Local Output

Store all generated files in `./output/` directory:
```
poc/output/
├── abc123xyz.mp3
├── abc123xyz-transcript.json
├── abc123xyz-embeddings.json
├── abc123xyz-ai-content.json
└── abc123xyz-guide.json
```

---

## Success Criteria for CW03

By the end of this context window:

- [ ] Can parse YouTube RSS feed and list recent videos
- [ ] Can extract MP3 audio from a YouTube video
- [ ] Can fetch transcript with timestamps
- [ ] Can chunk transcript and generate embeddings
- [ ] Can store embeddings in Pinecone
- [ ] Can perform semantic search and get relevant results
- [ ] Can generate AI summary, scriptures, and topics
- [ ] Can generate discussion guide content
- [ ] Full pipeline runs end-to-end on a test video

---

## Out of Scope for CW03

- WordPress plugin (CW06+)
- GCP deployment (CW09+)
- Admin dashboard
- Stripe integration
- PDF generation (JSON output is fine for now)
- Error handling and retry logic (keep it simple)
- Multi-church support (test with single namespace)

---

## Questions to Resolve in CW03

1. Which YouTube video should we use for testing?
2. Should we use youtube-transcript npm package or YouTube Data API for captions?
3. What chunk size and overlap works best for sermon content?
4. Should discussion guide be JSON only or attempt PDF generation?

---

## How to Start

Begin by creating the project structure and implementing the scripts in order (01 through 08). Test each one individually before moving to the full pipeline script.

Start with:
```bash
mkdir -p preachcaster/poc
cd preachcaster/poc
npm init -y
npm install rss-parser youtube-transcript openai @pinecone-database/pinecone dotenv
```

Then implement `01-fetch-youtube-rss.js` first to verify YouTube integration works.

---

## End of Session

At the end of CW03, create:
- CW03_SUMMARY.md documenting what was built and any issues encountered
- CW04_PROMPT.md for the next session (likely continuing POC or starting WordPress plugin)

---

*Ready to begin local POC development.*
