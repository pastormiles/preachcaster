# CW02 Summary: PreachCaster Architecture & Business Model

**Context Window:** CW02  
**Date:** December 31, 2024  
**Focus:** Feasibility analysis, architecture design, pricing tiers, feature specification

---

## 1. Project Identity

**Name:** PreachCaster  
**Domain:** PreachCaster.com  
**Tagline:** *Automated sermon podcasting for churches*

**What It Does:**
- Monitors YouTube channels for new sermon uploads
- Automatically extracts audio and creates podcast episodes
- Publishes to WordPress with RSS feeds for all major podcast platforms
- (Premium) Adds AI-powered search, transcripts, and small group discussion guides

---

## 2. Business Model

### Pricing Tiers

| Tier | Price | Target Customer |
|------|-------|-----------------|
| **Core** | $99/month | Small church, wants automation |
| **Pro** | $149/month | Medium church, wants visibility |
| **Premium** | $199/month | Larger church, wants AI intelligence |

### Feature Matrix

| Feature | Core ($99) | Pro ($149) | Premium ($199) |
|---------|:----------:|:----------:|:--------------:|
| YouTube channel monitoring | ✅ | ✅ | ✅ |
| Audio extraction & hosting | ✅ | ✅ | ✅ |
| WordPress auto-publishing | ✅ | ✅ | ✅ |
| RSS feed (Apple, Spotify, etc.) | ✅ | ✅ | ✅ |
| Transcript display | ❌ | ✅ | ✅ |
| Timestamped video links | ❌ | ✅ | ✅ |
| Admin dashboard | ❌ | ✅ | ✅ |
| Episode management | ❌ | ✅ | ✅ |
| Semantic search | ❌ | ❌ | ✅ |
| AI sermon summaries | ❌ | ❌ | ✅ |
| Scripture extraction | ❌ | ❌ | ✅ |
| Topic tagging | ❌ | ❌ | ✅ |
| Small group discussion guide (PDF) | ❌ | ❌ | ✅ |
| Search analytics | ❌ | ❌ | ✅ |
| Priority processing | ❌ | ❌ | ✅ |

### Custom Add-Ons (Future)

| Add-On | Price |
|--------|-------|
| "Ask Pastor" RAG chatbot | +$100/month + $500 setup |
| Multiple YouTube channels | +$50/month per additional channel |
| Custom integrations | Custom quote |
| White-label | +$100/month |

### Profit Analysis

| Churches | Revenue | Fixed Costs | Variable Costs | Profit | Margin |
|----------|---------|-------------|----------------|--------|--------|
| 5 | $495 | $32 | $2.50 | $460 | 93% |
| 10 | $990 | $32 | $5 | $953 | 96% |
| 25 | $2,475 | $50 | $12.50 | $2,412 | 97% |
| 50 | $4,950 | $75 | $25 | $4,850 | 98% |
| 100 | $9,900 | $150 | $50 | $9,700 | 98% |

**Variable cost per church:** ~$0.50/month (Core) to ~$1.50/month (Premium)

---

## 3. Technical Architecture

### Infrastructure (GCP)

| Component | GCP Service | Est. Cost |
|-----------|-------------|-----------|
| Backend Hosting | Cloud Run | $5-15/mo |
| Database | Cloud SQL (Postgres) | $10-15/mo |
| Job Queue | Cloud Tasks | $0.50/mo |
| Scheduler | Cloud Scheduler | $0.10/mo |
| Storage (Audio) | Cloud Storage | $2-5/mo |
| **Total Fixed** | | **~$20-35/mo** |

### External Services

| Service | Purpose | Cost |
|---------|---------|------|
| OpenAI | Embeddings + AI features | ~$5-20/mo at scale |
| Pinecone | Vector search | Free tier, then ~$20/mo |
| Stripe | Payments | 2.9% + $0.30/transaction |

### System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     CHURCH'S WORDPRESS                           │
│                                                                  │
│   PreachCaster Plugin                                            │
│   • Podcast post type + RSS feed                                 │
│   • Receives webhooks from backend                               │
│   • Search UI (Premium tier)                                     │
│   • Settings: API key, podcast branding                          │
│                                                                  │
└──────────────────────────▲───────────────────────────────────────┘
                           │
            Webhook: POST /wp-json/preachcaster/v1/episodes
                           │
┌──────────────────────────│───────────────────────────────────────┐
│                 PREACHCASTER BACKEND (GCP)                        │
│                                                                   │
│   ┌─────────────────────────────────────────────────────────┐    │
│   │  Cloud Run API                                          │    │
│   │  • /api/churches - CRUD for church accounts             │    │
│   │  • /api/search - Semantic search (Premium)              │    │
│   │  • /internal/process - Called by Cloud Tasks            │    │
│   └─────────────────────────────────────────────────────────┘    │
│                                                                   │
│   ┌─────────────────────────────────────────────────────────┐    │
│   │  Cloud Scheduler (every 15 min) → Watcher               │    │
│   │  • Fetch YouTube RSS for each active church             │    │
│   │  • Queue new videos to Cloud Tasks                      │    │
│   └─────────────────────────────────────────────────────────┘    │
│                                                                   │
│   ┌─────────────────────────────────────────────────────────┐    │
│   │  Cloud Tasks → Worker                                   │    │
│   │  1. Download audio (yt-dlp)                             │    │
│   │  2. Upload to Cloud Storage                             │    │
│   │  3. Fetch transcript (YouTube Captions API)             │    │
│   │  4. Generate AI content (Premium): summaries, guides    │    │
│   │  5. Generate embeddings → Pinecone (Premium)            │    │
│   │  6. POST to church's WordPress                          │    │
│   └─────────────────────────────────────────────────────────┘    │
│                                                                   │
│   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│   │   Cloud     │  │  Cloud SQL  │  │  Pinecone   │              │
│   │  Storage    │  │  (Postgres) │  │ (Premium)   │              │
│   └─────────────┘  └─────────────┘  └─────────────┘              │
│                                                                   │
└───────────────────────────────────────────────────────────────────┘
```

### Database Schema

```sql
-- Churches
CREATE TABLE churches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    stripe_customer_id TEXT,
    tier TEXT DEFAULT 'core', -- 'core', 'pro', 'premium'
    youtube_channel_id TEXT NOT NULL,
    wordpress_url TEXT NOT NULL,
    wordpress_api_key TEXT NOT NULL,
    podcast_title TEXT NOT NULL,
    podcast_author TEXT,
    podcast_description TEXT,
    podcast_artwork_url TEXT,
    pinecone_namespace TEXT,
    active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Episodes
CREATE TABLE episodes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    church_id UUID REFERENCES churches(id),
    youtube_id TEXT NOT NULL,
    title TEXT,
    description TEXT,
    published_at TIMESTAMP,
    duration INTEGER,
    audio_url TEXT,
    transcript JSONB,
    ai_summary TEXT,
    ai_scriptures JSONB,
    ai_topics JSONB,
    discussion_guide_url TEXT,
    status TEXT DEFAULT 'pending',
    error_message TEXT,
    attempts INTEGER DEFAULT 0,
    wordpress_post_id INTEGER,
    created_at TIMESTAMP DEFAULT NOW(),
    processed_at TIMESTAMP,
    UNIQUE(church_id, youtube_id)
);
```

---

## 4. Key Features Specification

### Small Group Discussion Guide (Premium)

Auto-generated PDF for each sermon containing:
- Key scriptures (primary + supporting)
- Sermon summary (2-3 sentences)
- Big idea (one memorable sentence)
- Opening icebreaker question
- 5 discussion questions (referencing sermon content)
- Weekly application challenge
- Prayer focus points
- Going deeper resources

**Generation:** GPT-4o-mini from transcript (~$0.02-0.05 per guide)
**Output:** Branded PDF with church logo

### Semantic Search (Premium)

- Transcript chunked into ~500 token segments with overlap
- Embeddings via OpenAI text-embedding-3-small
- Stored in Pinecone with church namespace isolation
- Search returns relevant moments with timestamps
- Links directly to YouTube video at specific time

### AI Content Generation (Premium)

All generated during episode processing:
- **Summary:** 2-3 sentence description for RSS feed
- **Scriptures:** Primary passage + supporting references
- **Topics:** Theme tags (grace, prayer, anxiety, etc.)

---

## 5. Project Structure

```
preachcaster/
├── backend/                    # Cloud Run service
│   ├── src/
│   │   ├── index.js           # Entry point
│   │   ├── api/               # REST endpoints
│   │   ├── workers/           # Watcher + processor
│   │   ├── services/          # YouTube, audio, storage, etc.
│   │   ├── db/                # Postgres queries
│   │   └── config.js
│   ├── Dockerfile
│   └── package.json
│
├── wordpress-plugin/           # PreachCaster WP plugin
│   ├── preachcaster.php
│   ├── includes/
│   │   ├── class-post-type.php
│   │   ├── class-rss-feed.php
│   │   ├── class-api.php
│   │   ├── class-search.php
│   │   └── class-settings.php
│   ├── templates/
│   └── assets/
│
├── website/                    # PreachCaster.com
│
└── docs/
```

---

## 6. Development Phases

### Phase 1: Local POC (CW03-CW05)
- [ ] YouTube RSS feed parsing
- [ ] Audio extraction with yt-dlp
- [ ] Transcript fetching
- [ ] Basic embedding generation
- [ ] Manual WordPress post creation

### Phase 2: WordPress Plugin Foundation (CW06-CW08)
- [ ] Custom post type for episodes
- [ ] RSS feed generator (Apple Podcasts spec)
- [ ] REST API endpoint for receiving episodes
- [ ] Settings page with setup wizard

### Phase 3: Backend Service (CW09-CW12)
- [ ] GCP project setup
- [ ] Cloud Run deployment
- [ ] YouTube watcher (Cloud Scheduler)
- [ ] Processing worker (Cloud Tasks)
- [ ] Cloud Storage integration

### Phase 4: Pro Tier Features (CW13-CW15)
- [ ] Transcript display on episode pages
- [ ] Admin dashboard
- [ ] Episode management UI

### Phase 5: Premium Tier Features (CW16-CW18)
- [ ] Semantic search implementation
- [ ] AI content generation (summaries, scriptures, topics)
- [ ] Discussion guide PDF generation
- [ ] Search analytics

### Phase 6: Production Launch (CW19-CW21)
- [ ] Stripe integration
- [ ] Customer onboarding flow
- [ ] Marketing website
- [ ] Beta testing with 3-5 churches

---

## 7. Key Decisions Made

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Hosting platform | GCP | Existing experience, integrated services |
| Backend runtime | Node.js on Cloud Run | Familiar, good ecosystem, scales to zero |
| Database | Cloud SQL (Postgres) | Reliable, relational data fits well |
| Audio storage | Cloud Storage | Integrated with GCP, cheap |
| Vector database | Pinecone | Free tier, simple, battle-tested |
| Embeddings | OpenAI text-embedding-3-small | Cheapest good option |
| AI generation | GPT-4o-mini | Cheap, fast, good enough quality |
| WordPress integration | Custom plugin | Full control, no dependencies |
| Audio extraction | yt-dlp | Industry standard, works |

---

## 8. Open Questions for CW03

1. **Local dev environment:** Docker or native Node.js + local Postgres?
2. **YouTube channel for testing:** Use Cross Connection Church channel?
3. **WordPress test site:** Local (wp-env, Local by Flywheel) or staging server?
4. **GCP project:** Create now or wait until backend is ready?

---

## 9. Risks & Mitigations

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| yt-dlp breaks | Medium | Monitor, update quickly, have alerts |
| YouTube captions delayed | Common | Retry logic (up to 6 hours), Whisper fallback |
| WordPress compatibility issues | Medium | Test with popular themes/hosts |
| Pinecone downtime | Rare | Graceful degradation, show message |
| OpenAI pricing increases | Low | Margins absorb 10x increase easily |

---

## 10. Next Steps (CW03)

Begin local proof of concept development:
1. Set up Node.js project structure
2. Implement YouTube RSS feed parsing
3. Test yt-dlp audio extraction
4. Fetch YouTube transcripts
5. Generate embeddings with OpenAI
6. Test Pinecone storage and retrieval

---

*Document created: CW02*  
*Next context window: CW03 — Local POC Development*
