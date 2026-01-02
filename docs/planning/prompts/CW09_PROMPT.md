# CW09 Prompt: PreachCaster Search API & WordPress Plugin

**Context Window:** CW09  
**Prerequisites:** CW08_SUMMARY.md, PROJECT_BIBLE.md  
**Focus:** Flask search API server and WordPress plugin for semantic search integration

---

## 1. Session Objectives

Build the search interface layer that makes PreachCaster's semantic search accessible to church websites. This includes a backend API for search queries and a WordPress plugin for frontend integration.

### Deliverables
1. `11_search_api_v1.py` — Flask API server for semantic search
2. `preachcaster-search/` — WordPress plugin directory with all files
3. Unit tests for both components
4. CW09_SUMMARY.md

---

## 2. Context from Previous Sessions

### Completed Pipeline (CW04-CW08)
| Script | Purpose | Output |
|--------|---------|--------|
| 01 | YouTube monitoring | new_videos.json |
| 02 | Audio extraction | MP3 files |
| 03 | Transcript fetching | JSON transcripts |
| 04 | Transcript chunking | Searchable chunks |
| 05 | Embedding generation | Vector embeddings |
| 06 | Pinecone upload | Indexed vectors |
| 07 | AI content generation | Summaries, scriptures, topics |
| 08 | Discussion guide PDFs | Printable guides |
| 09 | Pipeline orchestration | Episode packages |
| 10 | WordPress publishing | Published posts |

### What's Indexed in Pinecone
Each sermon is chunked into ~2-minute segments with:
- `chunk_id`: Unique identifier (e.g., `abc123xyz_chunk_003`)
- `video_id`: Source YouTube video
- `title`: Sermon title
- `text`: Chunk text content (truncated to 500 chars in metadata)
- `start_time` / `end_time`: Timestamps
- `timestamp_formatted`: Human-readable timestamp
- `youtube_url`: Direct link with timestamp parameter
- `word_count`: Words in chunk

### Existing Pinecone Configuration
```python
PINECONE_INDEX = "crossconnection-sermons"
PINECONE_NAMESPACE = "crossconnection"  # Per-church isolation
EMBEDDING_MODEL = "text-embedding-3-small"  # 1536 dimensions
```

---

## 3. Script 11: Search API Server

### Purpose
Provide a REST API for semantic search queries against the Pinecone vector database.

### Endpoints

#### `GET /api/health`
Health check endpoint.
```json
{"status": "ok", "version": "1.0"}
```

#### `POST /api/search`
Main search endpoint.

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

#### `GET /api/sermons`
List all indexed sermons.
```json
{
  "sermons": [
    {
      "video_id": "abc123xyz",
      "title": "Finding Peace in Anxious Times",
      "chunk_count": 24,
      "topics": ["peace", "anxiety"]
    }
  ],
  "total": 52
}
```

#### `GET /api/sermons/{video_id}`
Get details for a specific sermon.

#### `GET /api/topics`
List all topics with counts.
```json
{
  "topics": [
    {"name": "faith", "count": 45},
    {"name": "prayer", "count": 38},
    {"name": "grace", "count": 32}
  ]
}
```

### Technical Requirements

1. **Authentication**: API key in header (`X-API-Key`) or query param
2. **CORS**: Configurable allowed origins for WordPress sites
3. **Rate Limiting**: Basic rate limiting (100 requests/minute default)
4. **Caching**: Optional Redis/in-memory caching for frequent queries
5. **Logging**: Request logging with timing metrics

### Configuration
```python
# Server settings
API_HOST = "0.0.0.0"
API_PORT = 5005
API_KEY = os.getenv("PREACHCASTER_API_KEY")
CORS_ORIGINS = ["https://crossconnectionchurch.com"]

# Pinecone settings (from existing config)
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX = "crossconnection-sermons"
PINECONE_NAMESPACE = "crossconnection"

# OpenAI for query embedding
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
EMBEDDING_MODEL = "text-embedding-3-small"
```

### CLI Interface
```bash
# Start server
python 11_search_api_v1.py

# With options
python 11_search_api_v1.py --port 8080 --host 127.0.0.1

# Debug mode
python 11_search_api_v1.py --debug

# Generate API key
python 11_search_api_v1.py --generate-key
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

#### `[preachcaster_search]`
Full search interface with input and results.
```
[preachcaster_search placeholder="Search sermons..." limit="10"]
```

#### `[preachcaster_topics]`
Display topic cloud or list.
```
[preachcaster_topics style="cloud" limit="20"]
```

#### `[preachcaster_recent]`
Show recently indexed sermons.
```
[preachcaster_recent count="5"]
```

### Admin Settings Page
Settings → PreachCaster Search

| Setting | Description |
|---------|-------------|
| API URL | Search API endpoint URL |
| API Key | Authentication key |
| Default Limit | Default results per search |
| Min Score | Minimum relevance score (0-1) |
| Cache Duration | Minutes to cache results |
| Custom CSS | Additional styling |

### JavaScript Functionality
- AJAX search (no page reload)
- Debounced input (300ms)
- Loading indicators
- Result highlighting
- "Load more" pagination
- Click-to-play video timestamps

### CSS Styling
- Clean, minimal default styles
- Customizable via admin settings
- Responsive design
- Dark mode support (optional)

### Search Results Display
Each result shows:
- Sermon title (linked to post or YouTube)
- Relevance indicator (stars or percentage)
- Text snippet with query highlighting
- Timestamp link to exact moment
- "Watch" and "Listen" buttons

---

## 5. Integration Flow

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
│           ▼                                                         │
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
│                     WORDPRESS SITE                                  │
│                                                                     │
│   ┌─────────────────────────────────────┐                          │
│   │      Search Results                 │                          │
│   │                                     │                          │
│   │  📺 Finding Peace (92% match)       │                          │
│   │     "When anxiety comes..."         │                          │
│   │     ▶ Watch at 12:34               │                          │
│   │                                     │                          │
│   │  📺 Trust in Hard Times (87%)       │                          │
│   │     "God promises to be with..."    │                          │
│   │     ▶ Watch at 8:21                │                          │
│   └─────────────────────────────────────┘                          │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 6. Technical Considerations

### API Security
- API key validation on every request
- Rate limiting to prevent abuse
- Input sanitization
- CORS restrictions

### Performance
- Query embedding caching (same query = same embedding)
- Result caching with TTL
- Connection pooling for Pinecone
- Async where beneficial

### Error Handling
- Graceful degradation if API unavailable
- User-friendly error messages
- Logging for debugging
- Retry logic for transient failures

### Multi-Church Support (Future)
- Namespace isolation already in Pinecone
- API key tied to namespace
- Plugin supports multiple API endpoints

---

## 7. Testing Requirements

### API Tests
- Health endpoint returns 200
- Search returns valid results
- Invalid API key returns 401
- Rate limiting works
- CORS headers present
- Empty query handling
- Filter validation

### WordPress Plugin Tests
- Shortcodes render correctly
- AJAX requests work
- Settings save/load
- API client handles errors
- CSS/JS enqueue properly

---

## 8. Files to Create

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
| `test_script_11.py` | `test_project/` | API unit tests |

---

## 9. Success Criteria

- [ ] API server starts and responds to health check
- [ ] Search endpoint returns relevant results from Pinecone
- [ ] API key authentication works
- [ ] WordPress plugin installs without errors
- [ ] Shortcode renders search interface
- [ ] AJAX search returns and displays results
- [ ] Settings page saves configuration
- [ ] Results link to correct video timestamps
- [ ] Error states handled gracefully
- [ ] Documentation complete

---

## 10. Open Questions

1. **Deployment:** Where will the API server run? (Same server as WordPress? Separate?)
2. **SSL:** Does the API need its own SSL certificate?
3. **Caching:** Redis available, or in-memory only?
4. **Analytics:** Track popular searches?
5. **Feedback:** Allow users to rate result relevance?

---

## 11. Reference: Previous Script Patterns

Follow the established documentation and CLI patterns from CW04-CW08:
- Comprehensive docstring header
- Type hints on functions
- Argparse CLI with examples
- Logging with configurable levels
- JSON output option
- Dry-run where applicable
- Unit test coverage

---

*Prompt created for CW09*  
*Previous: CW08 — Pipeline Orchestration & WordPress Publishing*  
*Next: CW10 — Production Hardening & Deployment*
