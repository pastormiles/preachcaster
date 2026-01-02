# CW09 Summary: PreachCaster Search API & WordPress Plugin

**Context Window:** CW09  
**Date:** January 1, 2025  
**Focus:** Flask search API server and WordPress plugin for semantic search integration

---

## 1. Session Overview

This context window builds the search interface layer that makes PreachCaster's semantic search accessible to church websites. This completes the user-facing search functionality that allows congregation members to find relevant sermon content using natural language queries.

### Key Objectives
- [ ] Create `11_search_api_v1.py` — Flask API server for semantic search
- [ ] Create `preachcaster-search/` — WordPress plugin for frontend integration
- [ ] Unit tests for API endpoints
- [ ] Documentation following established patterns

---

## 2. Architecture Overview

### System Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                     WORDPRESS SITE                                  │
│                                                                     │
│   [preachcaster_search] shortcode                                   │
│           │                                                         │
│           ▼                                                         │
│   ┌─────────────────────────────────────┐                          │
│   │      Search Input Form              │                          │
│   │  "What does the Bible say about..." │                          │
│   └─────────────────────────────────────┘                          │
│           │                                                         │
│           │ AJAX POST                                               │
└───────────┼─────────────────────────────────────────────────────────┘
            │
            │ POST /api/search
            │ X-API-Key: xxx
            │ {"query": "..."}
            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     SEARCH API SERVER                               │
│                     11_search_api_v1.py                             │
│                                                                     │
│   1. Validate API key                                               │
│   2. Generate query embedding (OpenAI)                              │
│   3. Search Pinecone                                                │
│   4. Format results                                                 │
│   5. Return JSON                                                    │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
            │
            │ JSON Response
            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     SEARCH RESULTS                                  │
│                                                                     │
│   📺 Finding Peace in Anxious Times (92% match)                     │
│      "When anxiety comes, we need to remember..."                   │
│      ▶ Watch at 12:34                                              │
│                                                                     │
│   📺 Trust in Hard Times (87% match)                                │
│      "God promises to be with us..."                                │
│      ▶ Watch at 8:21                                               │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. Script 11: Search API Server

### Purpose
Provide a REST API for semantic search queries against the Pinecone vector database.

### Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/health` | GET | Health check |
| `/api/search` | POST | Main semantic search |
| `/api/sermons` | GET | List all indexed sermons |
| `/api/sermons/{video_id}` | GET | Get specific sermon details |
| `/api/topics` | GET | List topics with counts |

### Search Request/Response

**Request:**
```json
{
  "query": "How do I deal with anxiety?",
  "limit": 10,
  "min_score": 0.7,
  "filters": {
    "topics": ["anxiety", "peace"],
    "date_from": "2024-01-01",
    "date_to": "2024-12-31"
  }
}
```

**Response:**
```json
{
  "query": "How do I deal with anxiety?",
  "results": [
    {
      "score": 0.92,
      "video_id": "abc123xyz",
      "title": "Finding Peace in Anxious Times",
      "text": "When anxiety comes, we need to remember...",
      "timestamp": "12:34",
      "youtube_url": "https://youtube.com/watch?v=abc123xyz&t=754",
      "chunk_id": "abc123xyz_chunk_006"
    }
  ],
  "total_results": 5,
  "search_time_ms": 145
}
```

### Technical Features
- API key authentication (`X-API-Key` header)
- CORS configuration for WordPress sites
- Rate limiting (100 requests/minute default)
- Request logging with timing metrics
- Query embedding via OpenAI
- Pinecone vector search

### CLI Interface
```bash
python 11_search_api_v1.py                    # Start server
python 11_search_api_v1.py --port 8080        # Custom port
python 11_search_api_v1.py --debug            # Debug mode
python 11_search_api_v1.py --generate-key     # Generate API key
```

---

## 4. WordPress Plugin: preachcaster-search

### Plugin Structure
```
preachcaster-search/
├── preachcaster-search.php      # Main plugin file
├── includes/
│   ├── class-api-client.php     # API communication
│   ├── class-shortcodes.php     # Shortcode handlers
│   ├── class-settings.php       # Admin settings page
│   └── class-widget.php         # Search widget (optional)
├── assets/
│   ├── css/
│   │   └── preachcaster-search.css
│   └── js/
│       └── preachcaster-search.js
├── templates/
│   ├── search-form.php          # Search input template
│   └── search-results.php       # Results template
└── readme.txt                   # WordPress plugin readme
```

### Shortcodes

| Shortcode | Purpose | Example |
|-----------|---------|---------|
| `[preachcaster_search]` | Full search interface | `[preachcaster_search placeholder="Search sermons..." limit="10"]` |
| `[preachcaster_topics]` | Topic cloud/list | `[preachcaster_topics style="cloud" limit="20"]` |
| `[preachcaster_recent]` | Recent sermons | `[preachcaster_recent count="5"]` |

### Admin Settings (Settings → PreachCaster Search)

| Setting | Description |
|---------|-------------|
| API URL | Search API endpoint URL |
| API Key | Authentication key |
| Default Limit | Results per search |
| Min Score | Minimum relevance (0-1) |
| Cache Duration | Minutes to cache results |
| Custom CSS | Additional styling |

### JavaScript Features
- AJAX search (no page reload)
- Debounced input (300ms)
- Loading indicators
- Result highlighting
- "Load more" pagination
- Click-to-play video timestamps

---

## 5. Configuration

### API Server Configuration
```python
# Server settings
API_HOST = "0.0.0.0"
API_PORT = 5005
API_KEY = os.getenv("PREACHCASTER_API_KEY")
CORS_ORIGINS = ["https://crossconnectionchurch.com"]

# Pinecone settings
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX = "crossconnection-sermons"
PINECONE_NAMESPACE = "crossconnection"

# OpenAI for query embedding
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
EMBEDDING_MODEL = "text-embedding-3-small"
```

### WordPress Plugin Settings
Configured via admin dashboard:
- API URL: `https://api.crossconnectionchurch.com` or `http://localhost:5005`
- API Key: Generated by `--generate-key`
- Default limit: 10
- Minimum score: 0.7

---

## 6. Security Considerations

| Concern | Solution |
|---------|----------|
| API Authentication | API key required on all requests |
| Rate Limiting | 100 requests/minute per key |
| Input Sanitization | Query validation and escaping |
| CORS | Restrict to configured origins |
| Data Exposure | Only return necessary metadata |

---

## 7. Files to Create

| File | Location | Purpose |
|------|----------|---------|
| `11_search_api_v1.py` | `_templates/tools/` | Flask API server |
| `preachcaster-search.php` | `_templates/wordpress/preachcaster-search/` | Main plugin file |
| `class-api-client.php` | `includes/` | API communication |
| `class-shortcodes.php` | `includes/` | Shortcode handlers |
| `class-settings.php` | `includes/` | Admin settings |
| `preachcaster-search.css` | `assets/css/` | Plugin styles |
| `preachcaster-search.js` | `assets/js/` | Search functionality |
| `search-form.php` | `templates/` | Form template |
| `search-results.php` | `templates/` | Results template |
| `readme.txt` | Plugin root | WordPress readme |
| `test_script_11.py` | `test_project/` | API unit tests |

---

## 8. Dependencies

### Python (API Server)
```
flask>=3.0.0
flask-cors>=4.0.0
flask-limiter>=3.0.0
openai>=1.0.0
pinecone>=5.0.0
python-dotenv>=1.0.0
gunicorn>=21.0.0
```

### WordPress Plugin
- WordPress 5.6+ (for REST API improvements)
- PHP 7.4+
- jQuery (bundled with WordPress)

---

## 9. Success Criteria

| Criterion | Status |
|-----------|--------|
| API server starts and responds to health check | ⬜ |
| Search endpoint returns relevant results from Pinecone | ⬜ |
| API key authentication works | ⬜ |
| Rate limiting prevents abuse | ⬜ |
| CORS headers present for WordPress | ⬜ |
| WordPress plugin installs without errors | ⬜ |
| Shortcode renders search interface | ⬜ |
| AJAX search returns and displays results | ⬜ |
| Settings page saves configuration | ⬜ |
| Results link to correct video timestamps | ⬜ |
| Error states handled gracefully | ⬜ |
| Unit tests passing | ⬜ |
| Documentation complete | ⬜ |

---

## 10. Pipeline Integration

After CW09, the complete PreachCaster system:

```
┌─────────────────────────────────────────────────────────────────────┐
│                        CONTENT PIPELINE                             │
│                                                                     │
│  YouTube → Audio → Transcript → Chunks → Embeddings → Pinecone     │
│                                    ↓                                │
│                           AI Content → PDF Guide                    │
│                                    ↓                                │
│                           WordPress Post → RSS Feed                 │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        SEARCH INTERFACE (CW09)                      │
│                                                                     │
│  WordPress Plugin ←→ Flask API ←→ Pinecone Vector DB               │
│        ↓                                                            │
│  Congregation searches "What about forgiveness?"                    │
│        ↓                                                            │
│  Results: Sermon clips with timestamps + YouTube links              │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 11. Open Questions

1. **Deployment:** Where will the API server run? (Same server as WordPress? Separate VPS? Cloud Run?)
2. **SSL:** Does the API need its own SSL certificate or share with main domain?
3. **Caching:** Redis available, or in-memory only?
4. **Analytics:** Track popular searches for insights?
5. **Feedback:** Allow users to rate result relevance?

---

## 12. Next Steps

1. Build `11_search_api_v1.py` with all endpoints
2. Test API against Pinecone with real queries
3. Build WordPress plugin structure
4. Implement shortcodes and AJAX search
5. Create admin settings page
6. Write unit tests
7. Document deployment process

---

## 13. Milestone Status

| Milestone | Status | CW |
|-----------|--------|-----|
| YouTube monitoring | ✅ | CW04 |
| Audio extraction | ✅ | CW04 |
| Transcript fetching | ✅ | CW05 |
| Transcript chunking | ✅ | CW05 |
| Embedding generation | ✅ | CW06 |
| Pinecone indexing | ✅ | CW06 |
| AI content generation | ✅ | CW07 |
| Discussion guide PDFs | ✅ | CW07 |
| Pipeline orchestration | ✅ | CW08 |
| WordPress publishing | ✅ | CW08 |
| **Search API** | 🔄 | **CW09** |
| **WordPress search plugin** | 🔄 | **CW09** |

---

*Document created: CW09*  
*Next context window: CW10 — Production Hardening & Deployment*
