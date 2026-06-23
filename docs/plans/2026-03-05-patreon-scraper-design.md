# Patreon Scraper Integration - Design

## Goal

Add a Patreon content source to pull Soccer Supremo chapters (book 5+) into the existing audiobook pipeline. Session cookie auth, minimal generalization — built for the tedsteel Patreon feed.

## Constraints & Decisions

- **Auth**: Session cookie only (`session_id` from browser, ~1 month expiry)
- **Campaign ID**: Auto-resolved from creator page HTML (e.g., `patreon.com/c/tedsteel/posts` -> campaign `9319026`)
- **Scope**: Soccer Supremo-specific. No multi-creator generalization.
- **No `start_from` filtering**: Per-book download is sufficient (book number encoded in post titles)
- **Tier tags**: Stripped from titles, not persisted. Subscription covers all content.
- **Post title format**: `<book>.<chapter> - <title> [<tier>]` e.g., `6.2 - Staggered [T3]`
- **Title regex**: `^(\d+)\.(\d+)\s*-\s*(.+?)(?:\s*\[.*\])?$` captures (book, chapter, title)

## Architecture

The existing pipeline separation is preserved. Scrapers produce `raw.txt`, everything downstream is source-agnostic.

```
Content Sources          Shared Pipeline
--------------          ---------------
RoyalRoadScraper --\
                    +--> raw.txt -> normalize -> chunk -> TTS -> export
PatreonScraper  --/
```

Filesystem identity uses prefixed IDs to avoid collisions:
- Royal Road: `data/books/58187/book_1/...`
- Patreon: `data/books/patreon_9319026/book_5/...`

## Changes

### 1. PatreonScraper (`backend/src/scraper/patreon.py`) - NEW

Core class with session cookie auth. Hits Patreon's internal JSON API.

**Auth**: `Cookie: session_id=<value>` header on all requests.

**Campaign ID resolution**: Fetch creator page HTML, extract campaign_id from embedded page data. Cached after first lookup.

**Post fetching**: Patreon's internal API returns JSON with cursor-based pagination (~20 posts per page). Filter by:
- `is_by_creator=true`
- Title matches chapter pattern regex
- Sort by `published_at` ascending

**Methods** (matching RoyalRoadScraper interface):
- `get_fiction_info(fiction_id)` - Fetch campaign metadata (title, creator name)
- `get_chapter_list(fiction_id, book_number)` - Fetch posts, filter by pattern, group by book, return chapter list
- `download_chapter_text(post_id)` - Fetch single post, extract text from HTML `content` field
- `download_book(fiction_id, book_number, ...)` - Iterate chapters, save `raw.txt`, return `BookMetadata`

**HTML to text**: Patreon `content` field is HTML. Reuse same approach as Royal Road's `_html_to_text`.

**Error handling**: Clear error on 401/403 (expired cookie). Retry with backoff on transient errors. Rate limiting delays between requests.

### 2. Scraper Protocol (`backend/src/scraper/__init__.py`) - MODIFY

```python
@runtime_checkable
class Scraper(Protocol):
    def get_fiction_info(self, fiction_id: str) -> dict: ...
    def get_chapter_list(self, fiction_id: str, book_number: int | None = None) -> list[dict]: ...
    def download_chapter_text(self, chapter_ref: str) -> str: ...
    def download_book(self, fiction_id: str, book_number: int, delay: float = 1.0,
                      on_progress=None) -> BookMetadata: ...

def get_scraper(source: str = "royal_road") -> Scraper:
    if source == "patreon":
        return PatreonScraper()
    return RoyalRoadScraper()
```

### 3. Config (`backend/src/config.py`) - MODIFY

Add to `Settings`:
- `patreon_session_id: str = ""`
- `patreon_chapter_pattern: str = r"^(\d+)\.(\d+)\s*-\s*(.+?)(?:\s*\[.*\])?$"`

No campaign_id in config — resolved from URL at runtime.

### 4. API Routes (`backend/src/api/routes.py`) - MODIFY

- Extend URL detection: `patreon.com/c/<slug>` -> source = "patreon"
- `fiction_id` for Patreon = `patreon_<campaign_id>` (resolved from creator page)
- Scraper selection via `get_scraper(source)` in preview/add/download
- Skip `get_all_books_in_series()` for Patreon — derive book list from chapter title patterns
- Download processor picks scraper based on fiction_id prefix

### 5. Request Models (`backend/src/api/requests.py`) - MODIFY

- Make `chapters_on_royal_road` field nullable/generic for Patreon sources

### 6. Frontend (`frontend/src/Dashboard.tsx`) - MODIFY

- URL input placeholder: "Royal Road or Patreon URL"
- Handle Patreon preview (book list from post titles, not series page)
- Conditional label for chapter count source

### 7. `.env.example` - MODIFY

Add `AUDIOBOOK_PATREON_SESSION_ID=`

## Out of Scope

- Username/password automated login
- `start_from` cutoff filtering
- Multi-creator / general Patreon support
- Incremental sync / new chapter detection
- Campaign ID in config (auto-resolved instead)

## Risks

- **Cookie expiry**: Session cookies last ~1 month. Scraper returns clear error when expired.
- **API changes**: Using undocumented internal API. Could break without notice.
- **Rate limiting**: Use 1s delay between requests (same as Royal Road).
- **Post content format**: Some posts may have images/embeds. HTML-to-text gracefully skips non-text.
