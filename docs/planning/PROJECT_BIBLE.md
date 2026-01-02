# Project Bible: Cross Connection Church AI Content System

**Working Title:** CCChurch Content Intelligence Platform  
**Version:** 1.0  
**Created:** CW01  
**Last Updated:** CW01  

---

## 1. Project Overview

### 1.1 What Is This?

An automated content pipeline and intelligent search system for Cross Connection Church that:

- Automatically transforms YouTube sermon uploads into podcast episodes
- Publishes to a custom WordPress podcast system with bulletproof RSS feeds
- Indexes all content for semantic AI-powered search
- Requires zero manual intervention after initial YouTube upload

### 1.2 Who Is Building This?

**Primary Developer:** Pastor of Cross Connection Church  
**Roles:**
- Domain expert (pastoral content, congregation needs)
- AI developer (Nomion AI / SOMA Insights)
- AI ethicist (responsible implementation lens)

### 1.3 Why Does This Exist?

**Pain Points:**
- Current podcast plugins (e.g., Blubrry) are clunky, manual, and unreliable
- RSS feed management is fragile and frustrating
- No automation between YouTube uploads and podcast distribution
- Sermon content is hard to search and discover
- Staff time wasted on repetitive manual processes

**Opportunity:**
- Leverage existing POC work (OpenAI embeddings + Pinecone vector DB)
- Create a seamless, zero-touch content workflow
- Make sermon content genuinely findable and useful
- Potential to productize for other churches/creators

---

## 2. The Vision

### 2.1 The Dream Workflow

```
┌─────────────────────────────────────────────────────────────────┐
│                        AV TEAM ACTION                           │
│                   (Only human step required)                    │
│                                                                 │
│                    Upload video to YouTube                      │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    AUTOMATED PIPELINE                           │
│                                                                 │
│  1. Detect new YouTube upload                                   │
│  2. Extract audio (MP3)                                         │
│  3. Fetch transcript (YouTube Captions API)                     │
│  4. Extract/enrich metadata                                     │
│  5. Create WordPress "Podcast" post                             │
│  6. Generate embeddings from transcript                         │
│  7. Index in Pinecone vector database                           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    AUTOMATIC OUTPUTS                            │
│                                                                 │
│  • Podcast episode live on website                              │
│  • RSS feed updated (Apple, Spotify, Amazon, etc.)              │
│  • Content searchable via semantic AI search                    │
│  • Video + Audio + Transcript unified and linked                │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    CONGREGATION BENEFIT                         │
│                                                                 │
│  "I want to find that sermon where Pastor talked about..."      │
│                              │                                  │
│                              ▼                                  │
│                    Semantic search finds it                     │
│                    Links to video timestamp                     │
│                    Links to audio podcast                       │
│                    Shows relevant transcript                    │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 User Experience Goals

| User | Experience |
|------|------------|
| **AV Team** | No change to workflow. Upload to YouTube. Done. |
| **Church Staff** | No podcast management. No manual entry. |
| **Congregation** | Sermons appear in podcast apps automatically. Can search by topic/question. |
| **Pastor** | Content is discoverable, organized, and working harder for the ministry. |

---

## 3. System Architecture

### 3.1 Component Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     CONTENT INTELLIGENCE PLATFORM               │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                  1. INGEST PIPELINE                      │  │
│  │                                                          │  │
│  │  • YouTube monitoring (API/RSS/WebSub)                   │  │
│  │  • Audio extraction (yt-dlp)                             │  │
│  │  • Transcript retrieval (YouTube Captions API)           │  │
│  │  • Metadata extraction                                   │  │
│  └──────────────────────────────────────────────────────────┘  │
│                              │                                  │
│                              ▼                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                  2. PODCAST ENGINE                       │  │
│  │                                                          │  │
│  │  • Custom WordPress "Podcast" post type                  │  │
│  │  • Clean, spec-compliant RSS feed generator              │  │
│  │  • Audio file hosting/management                         │  │
│  │  • Transcript display                                    │  │
│  │  • Apple/Spotify/Amazon compatible                       │  │
│  └──────────────────────────────────────────────────────────┘  │
│                              │                                  │
│                              ▼                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              3. INTELLIGENCE LAYER                       │  │
│  │                                                          │  │
│  │  • OpenAI embeddings generation                          │  │
│  │  • Pinecone vector database storage                      │  │
│  │  • Semantic search API                                   │  │
│  │  • WordPress search UI integration                       │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 Component Details

#### Component 1: Ingest Pipeline

**Purpose:** Detect new YouTube content and extract all assets automatically.

**Inputs:**
- YouTube channel feed
- YouTube video ID

**Outputs:**
- MP3 audio file
- Transcript text (with timestamps if available)
- Metadata (title, description, date, duration, etc.)

**Technologies (Candidates):**
- YouTube Data API v3 (monitoring, metadata)
- YouTube Captions API (transcripts)
- yt-dlp (audio extraction)
- WebSub/RSS (push notifications)

**Hosting Options:**
- Serverless (AWS Lambda, Cloudflare Workers)
- Self-hosted microservice
- WordPress cron + external script

---

#### Component 2: Podcast Engine

**Purpose:** Replace Blubrry and other plugins with a clean, minimal, automated podcast system.

**Features:**
- Custom Post Type: "Podcast"
- Fields: audio file, transcript, YouTube link, duration, episode number, series/season
- RSS feed generator (Apple Podcasts spec compliant)
- Automatic feed updates on new post
- Player embed for website

**RSS Feed Requirements (Apple Podcasts Spec):**
- `<itunes:title>`
- `<itunes:author>`
- `<itunes:image>`
- `<itunes:category>`
- `<itunes:explicit>`
- `<enclosure>` with proper MIME type and length
- `<itunes:duration>`
- `<itunes:summary>`
- HTTPS audio URLs
- Proper XML escaping

**Technologies:**
- WordPress custom post type (PHP or via plugin framework)
- Custom RSS template
- Audio hosting (WordPress media library or external CDN)

---

#### Component 3: Intelligence Layer

**Purpose:** Make all content semantically searchable.

**Existing POC:**
- OpenAI embeddings (model TBD - likely text-embedding-ada-002 or newer)
- Pinecone vector database
- YouTube transcript corpus already indexed

**To Build:**
- Automatic embedding generation for new content
- Search API endpoint
- WordPress frontend search UI
- Results display (with timestamps, links to audio/video)

**Future Possibilities:**
- RAG (Retrieval Augmented Generation) for conversational Q&A
- "Ask Pastor" chatbot interface
- Topic clustering and browse UI
- Related sermon recommendations

---

## 4. Technical Stack

### 4.1 Confirmed/Existing

| Component | Technology |
|-----------|------------|
| Content Source | YouTube (existing channel) |
| Website | WordPress |
| Embeddings | OpenAI API |
| Vector Database | Pinecone |
| Existing POC | Semantic search on transcripts (working locally) |

### 4.2 To Be Determined

| Component | Options to Evaluate |
|-----------|---------------------|
| Pipeline Host | AWS Lambda, Cloudflare Workers, self-hosted, WP cron |
| Audio Extraction | yt-dlp (likely) |
| YouTube Monitoring | Data API polling, RSS, WebSub |
| Podcast Post Type | Custom PHP, ACF, Pods, or custom plugin |
| RSS Generation | Custom template vs. lightweight library |
| Search UI | React component, vanilla JS, or WP native |
| Audio Hosting | WP media library, S3, Cloudflare R2, Backblaze B2 |

---

## 5. Development Phases

### Phase 1: Foundation
- [ ] Define WordPress podcast post type structure
- [ ] Build RSS feed generator (spec-compliant)
- [ ] Test RSS with Apple Podcasts validator
- [ ] Manual episode creation working

### Phase 2: Automation Pipeline
- [ ] YouTube upload detection mechanism
- [ ] Audio extraction automation
- [ ] Transcript retrieval automation
- [ ] Auto-creation of WordPress posts

### Phase 3: Intelligence Integration
- [ ] Auto-generate embeddings for new content
- [ ] Auto-index in Pinecone
- [ ] Build/integrate search UI on WordPress
- [ ] Link search results to audio/video/transcript

### Phase 4: Polish & Optimization
- [ ] Error handling and monitoring
- [ ] Admin dashboard for oversight
- [ ] Performance optimization
- [ ] Documentation

### Phase 5: Future Enhancements (Optional)
- [ ] RAG conversational interface
- [ ] Topic clustering
- [ ] Related content recommendations
- [ ] Productization for other churches

---

## 6. Open Questions

### Technical Questions
1. **Where should the pipeline run?** (Serverless vs. self-hosted vs. WP-integrated)
2. **Audio hosting strategy?** (WP media library has limitations; external CDN?)
3. **How to handle YouTube processing delays?** (Captions may not be immediately available)
4. **Webhook vs. polling for YouTube detection?**
5. **How to handle failures gracefully?** (Retry logic, notifications)

### Content/Editorial Questions
6. **What metadata should be extracted/stored?** (Speaker, series, scripture references, topics)
7. **Should transcripts be editable?** (Correct auto-caption errors)
8. **Episode numbering scheme?**
9. **How to handle back-catalog?** (Batch import of existing content)

### UX Questions
10. **What should the search UI look like?**
11. **How prominent should semantic search be on the site?**
12. **Timestamp linking—how granular?** (Jump to exact moment in video/audio)

### Strategic Questions
13. **Is this also a Nomion AI showcase/product?**
14. **Licensing/open-source considerations?**
15. **Could this serve other churches? What would need to be configurable?**

---

## 7. Ethical Considerations

As an AI ethicist building AI-powered tools for a faith community:

### Transparency
- Be clear with congregation about what is AI-generated vs. human-created
- Explain how search/recommendations work if asked

### Authority & Interpretation
- AI should surface content, not interpret theological meaning
- Search results present what was said, not what AI thinks it means
- Avoid AI "summarizing" pastoral teaching in ways that could distort

### Data & Privacy
- What data is collected from search queries?
- How is it used? Who has access?
- Congregation should understand and consent

### Accuracy
- Auto-generated transcripts may have errors
- Consider review process or disclaimer
- Errors in transcript → errors in search results

### Dependency & Sustainability
- What happens if OpenAI/Pinecone pricing changes?
- What if services go away?
- Consider portability and exit strategies

---

## 8. Success Criteria

### Minimum Viable Product (MVP)
- [ ] New YouTube upload → podcast episode appears on WP site within [X hours]
- [ ] RSS feed validates and works with Apple Podcasts
- [ ] Transcript is stored and displayed with episode
- [ ] Semantic search finds relevant content

### Full Success
- [ ] Zero manual intervention required for weekly sermon workflow
- [ ] Congregation can search and find answers easily
- [ ] System is stable and maintainable
- [ ] RSS feed works reliably with all major podcast platforms

### Stretch Goals
- [ ] Conversational "Ask Pastor" interface
- [ ] Productized version for other churches
- [ ] Admin analytics dashboard

---

## 9. Glossary

| Term | Definition |
|------|------------|
| **Embeddings** | Numerical vector representations of text that capture semantic meaning |
| **Vector Database** | Database optimized for storing and searching embeddings (e.g., Pinecone) |
| **Semantic Search** | Search based on meaning rather than keyword matching |
| **RAG** | Retrieval Augmented Generation - combining search results with LLM generation |
| **RSS** | Really Simple Syndication - XML feed format used by podcast apps |
| **yt-dlp** | Open-source tool for downloading YouTube content |
| **WebSub** | Protocol for real-time notifications when content is published |
| **CPT** | Custom Post Type - WordPress content type beyond posts/pages |

---

## 10. Document History

| Version | Date | CW | Changes |
|---------|------|-----|---------|
| 1.0 | TBD | CW01 | Initial creation |

---

## 11. Next Steps (CW02)

1. Review and refine this Project Bible
2. Decide on project working name
3. Prioritize: Start with Podcast Engine or Pipeline first?
4. Begin technical spike on chosen component
5. Set up development environment

---

*This is a living document. It will be updated as the project evolves.*
