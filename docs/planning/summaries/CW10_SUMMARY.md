# CW10 Summary: PreachCaster SaaS Architecture & Multi-Tenant Design

**Context Window:** CW10  
**Date:** January 1, 2025  
**Focus:** SaaS architecture ideation, subdomain routing, centralized hosting model

---

## 1. Session Overview

This context window was an ideation session exploring how to evolve PreachCaster from a per-church file-based system to a true multi-tenant SaaS platform. The discussion focused on centralized hosting, subdomain-per-church architecture, and a streamlined onboarding flow.

### Key Outcomes
- ✅ Defined centralized SaaS architecture on GCP
- ✅ Designed subdomain-per-church model (ccchurch.preachcaster.com)
- ✅ Decided audio hosting on Cloud Storage (not VM)
- ✅ Proposed static HTML landing pages for churches without WordPress
- ✅ Simplified WordPress plugin to display-only (fetches from API)
- ✅ Mapped full onboarding flow with Stripe integration
- ✅ Identified migration path for existing scripts (wrapper approach)

---

## 2. Architecture Evolution

### Previous Architecture (CW02-CW08)

Per-church, file-based system where each church has:
- Own directory with JSON files
- Local audio storage
- WordPress plugin generates RSS feed
- Scripts run in church-specific context

### New Architecture (CW10)

Centralized multi-tenant SaaS where PreachCaster owns:
- All RSS feeds (consistent, spec-compliant)
- All audio hosting (Cloud Storage)
- All episode data (PostgreSQL)
- All billing (Stripe subscriptions)

```
┌─────────────────────────────────────────────────────────────────────┐
│                    PREACHCASTER CENTRAL (GCP)                       │
│                                                                     │
│  Subdomains: *.preachcaster.com                                     │
│  ├── ccchurch.preachcaster.com                                      │
│  ├── firstbaptist.preachcaster.com                                  │
│  └── gracecommunity.preachcaster.com                                │
│                                                                     │
│  Endpoints per subdomain:                                           │
│  ├── /feed.xml     → RSS feed (Apple, Spotify, etc.)                │
│  ├── /feed.json    → JSON API (WordPress plugin)                    │
│  ├── /api/search   → Semantic search (Premium tier)                 │
│  └── /             → Static landing page (optional)                 │
│                                                                     │
│  Infrastructure:                                                    │
│  ├── GCP Compute Engine VM (Flask/FastAPI app)                      │
│  ├── Cloud SQL (PostgreSQL)                                         │
│  ├── Cloud Storage (audio files, PDFs, static sites)                │
│  └── Stripe (billing)                                               │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. Key Architectural Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Audio hosting | Cloud Storage buckets | VM never touches audio bytes; RSS points directly to storage URLs |
| Landing pages | Static HTML in Cloud Storage | Zero server load; nice for churches without WordPress |
| RSS ownership | PreachCaster serves all feeds | Consistency, reliability, analytics |
| WordPress plugin | Display-only (API consumer) | Simpler, fewer failure points |
| Database | PostgreSQL (Cloud SQL) | Multi-tenant, relational data fits well |
| Script migration | Wrapper approach (Option B) | Existing scripts work; wrap in job system |

---

## 4. Cloud Storage Structure

```
Cloud Storage Bucket: preachcaster-audio
├── ccchurch/
│   ├── abc123xyz.mp3
│   └── def456uvw.mp3
├── firstbaptist/
│   └── ...
└── ...

Cloud Storage Bucket: preachcaster-sites (website-enabled)
├── ccchurch/
│   ├── index.html              ← Episode listing
│   ├── episodes/
│   │   └── abc123xyz.html      ← Individual episode
│   └── assets/
│       └── style.css
├── firstbaptist/
│   └── ...
└── ...
```

**URL Patterns:**
- Audio: `https://storage.googleapis.com/preachcaster-audio/ccchurch/abc123xyz.mp3`
- Or via CDN: `https://audio.preachcaster.com/ccchurch/abc123xyz.mp3`

---

## 5. Subdomain Routing

```
ccchurch.preachcaster.com/feed.xml   → Flask app (dynamic RSS generation)
ccchurch.preachcaster.com/feed.json  → Flask app (dynamic JSON API)
ccchurch.preachcaster.com/api/*      → Flask app (search, etc.)
ccchurch.preachcaster.com/*          → Cloud Storage (static HTML pages)
```

Nginx handles routing:
- API/feed requests → Flask application
- Static requests → Cloud Storage bucket

---

## 6. Database Schema (Updated)

```sql
-- Churches with subdomain
CREATE TABLE churches (
    id UUID PRIMARY KEY,
    subdomain TEXT UNIQUE NOT NULL,      -- 'ccchurch'
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    api_key TEXT NOT NULL,               -- For WP plugin auth
    stripe_customer_id TEXT,
    stripe_subscription_id TEXT,
    tier TEXT DEFAULT 'core',            -- 'core', 'pro', 'premium'
    youtube_channel_id TEXT NOT NULL,
    podcast_title TEXT,
    podcast_author TEXT,
    podcast_description TEXT,
    podcast_artwork_url TEXT,
    active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Episodes owned by PreachCaster
CREATE TABLE episodes (
    id UUID PRIMARY KEY,
    church_id UUID REFERENCES churches(id),
    youtube_id TEXT NOT NULL,
    title TEXT,
    description TEXT,
    summary TEXT,                        -- AI-generated
    published_at TIMESTAMP,
    duration INTEGER,
    audio_url TEXT,                      -- Cloud Storage URL
    transcript TEXT,
    ai_content JSONB,
    guide_url TEXT,                      -- Cloud Storage URL
    status TEXT DEFAULT 'published',
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(church_id, youtube_id)
);
```

---

## 7. Onboarding Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│  1. DISCOVERY                                                       │
│     preachcaster.com → "Get Started" button                         │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│  2. REGISTRATION FORM                                               │
│                                                                     │
│     Church Name: [Cross Connection Church        ]                  │
│     Email:       [pastor@ccchurch.com            ]                  │
│     Subdomain:   [ccchurch    ].preachcaster.com  (availability ✓)  │
│     YouTube:     [UCDWgXIoyH3WNRxlB9N-gCOg       ] (validate ✓)     │
│                                                                     │
│     ○ Core ($99/mo)  ○ Pro ($149/mo)  ● Premium ($199/mo)           │
│                                                                     │
│     [Continue to Payment →]                                         │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│  3. STRIPE CHECKOUT                                                 │
│     Standard Stripe payment flow                                    │
│     Creates customer + subscription                                 │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│  4. WEBHOOK: payment_success                                        │
│                                                                     │
│     → Create church record in DB                                    │
│     → Generate API key                                              │
│     → Create subdomain routing                                      │
│     → Create storage folders (audio, site)                          │
│     → Queue: initial YouTube channel scan                           │
│     → Send welcome email with:                                      │
│         - API key                                                   │
│         - RSS feed URL for Apple/Spotify                            │
│         - WP plugin download + setup guide                          │
│         - Link to dashboard                                         │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│  5. BACKGROUND PROCESSING                                           │
│                                                                     │
│     For each video in initial scan:                                 │
│       → Extract audio → upload to Cloud Storage                     │
│       → Fetch transcript                                            │
│       → Generate AI content (if Pro/Premium)                        │
│       → Generate embeddings (if Premium)                            │
│       → Create episode record                                       │
│       → Generate static HTML page                                   │
│       → RSS feed auto-updates                                       │
│                                                                     │
│     Church gets email: "Your podcast is ready!"                     │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│  6. ONGOING AUTOMATION                                              │
│                                                                     │
│     Every 15 min: check YouTube RSS for new uploads                 │
│     New video detected → queue for processing                       │
│     Processing complete → episode live automatically                │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 8. WordPress Plugin Simplification

**Before (CW08 design):**
- Creates custom post type "Podcast"
- Generates RSS feed from posts
- Handles audio uploads
- Complex, many failure points

**After (CW10 design):**
- Display-only plugin
- Fetches JSON from PreachCaster API
- Renders episodes via shortcodes
- Search widget for Premium tier
- Much simpler, less can break

```php
// Settings
$subdomain = 'ccchurch';
$api_key = 'pk_xxxxxxxxxxxx';

// Shortcodes
[preachcaster_episodes]           // Episode listing
[preachcaster_episodes limit="5"] // Limited listing
[preachcaster_player id="123"]    // Single episode player
[preachcaster_search]             // Semantic search (Premium)

// Data source
https://ccchurch.preachcaster.com/feed.json?api_key={key}
```

---

## 9. Benefits of New Architecture

| Benefit | Description |
|---------|-------------|
| **RSS Ownership** | PreachCaster controls all feeds — no more broken feeds from WordPress issues |
| **Simpler WP Plugin** | Display-only means fewer bugs, easier support |
| **Platform Agnostic** | Churches can use WordPress, Squarespace, or just link to subdomain |
| **Better Analytics** | All traffic flows through PreachCaster — full visibility |
| **Easier Updates** | Change feed format once, all churches updated |
| **Scalable** | Static pages + CDN audio = minimal server load |

---

## 10. Migration Strategy for Existing Scripts

**Option B Selected: Wrapper Approach**

Keep existing scripts (01-10) mostly as-is. Create a job runner that:

1. Creates temporary working directory per job
2. Writes config/input files for the church
3. Runs scripts in that directory
4. Uploads results to Cloud Storage
5. Updates database records
6. Cleans up temp directory

This gets to market faster — scripts work, just need orchestration layer.

---

## 11. Open Questions for Future Context Windows

| Question | Status |
|----------|--------|
| Initial backfill count | TBD — Last 10? 50? All videos? |
| Church dashboard | Needed — edit titles, view stats, manage subscription |
| Tier enforcement | Skip steps or generate but hide? |
| Custom domains | Deferred — adds SSL complexity |
| Whisper fallback | TBD — for videos without captions |

---

## 12. Infrastructure Summary

| Component | Service | Purpose |
|-----------|---------|---------|
| Application | GCP Compute Engine | Flask/FastAPI, RSS generation, API |
| Database | Cloud SQL (PostgreSQL) | Churches, episodes, subscriptions |
| Audio Storage | Cloud Storage | MP3 files, direct URLs in RSS |
| Static Sites | Cloud Storage (website) | Landing pages per church |
| CDN | Cloud CDN (optional) | Audio delivery optimization |
| SSL | Let's Encrypt | Wildcard cert for *.preachcaster.com |
| Billing | Stripe | Subscriptions, webhooks |
| Email | SendGrid/Mailgun | Welcome emails, notifications |

---

## 13. Cost Implications

The centralized model changes cost structure slightly:

| Cost | Per-Church Model | Centralized SaaS |
|------|------------------|------------------|
| Audio storage | On church's hosting | PreachCaster pays (~$0.02/GB/mo) |
| Bandwidth | On church's hosting | PreachCaster pays (~$0.12/GB) |
| Processing | Same | Same |

Audio costs at scale (assuming 50MB/episode average):
- 10 churches × 4 episodes/month = 2GB storage, ~$0.50/month
- 100 churches × 4 episodes/month = 20GB storage, ~$5/month

Still well within profitable margins at $99-199/church/month.

---

## 14. Next Steps

### Immediate (CW11+)
1. Design Flask app structure for multi-tenant API
2. Implement subdomain routing with nginx
3. Build RSS feed generator endpoint
4. Build JSON API endpoint for WP plugin
5. Create Stripe integration for onboarding

### Near-term
6. Refactor scripts as job workers
7. Build job queue system (Cloud Tasks or Redis Queue)
8. Create simplified WordPress plugin
9. Build church dashboard

### Later
10. Static site generation for landing pages
11. Analytics dashboard
12. Custom domain support

---

## 15. Key Learnings

1. **Owning the RSS feed is crucial** — It's the product's core value; don't delegate to WordPress
2. **Static + dynamic hybrid works well** — API endpoints dynamic, landing pages static
3. **Wrapper approach enables speed** — Don't rewrite working code, just orchestrate it
4. **Subdomain model is clean** — Natural tenant isolation, good UX, simple routing

---

*Document created: CW10*  
*Focus: SaaS architecture ideation — no code written*  
*Next context window: TBD — Flask app structure or Stripe integration*
