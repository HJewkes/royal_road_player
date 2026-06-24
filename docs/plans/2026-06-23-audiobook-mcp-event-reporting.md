# Audiobook MCP + Event Reporting — Phases 1 & 2

**Status:** Planned (2026-06-23) · **Owner:** @hjewkes · **Scope:** Phases 1–2 only

## Goal

Expose the audiobook pipeline to an automated **Claude agent** via two pieces:

1. **Event store** (backend) — an append-only, pollable log of pipeline events.
2. **MCP server** — a thin wrapper over the existing FastAPI so a Claude session/agent
   can observe and drive the pipeline with structured tool calls instead of
   `curl`/`autopull.log` parsing.

Primary consumer is a **pull/poll** agent (not human push). Phases 3 (validation
wiring) and 4 (scheduled poller) are out of scope here — see "Deferred".

## Context (current state)

- FastAPI backend (`backend/src`), single `app = FastAPI(...)` at `routes.py:82`; routes
  declared directly with `@app.<verb>` (no sub-`APIRouter`). 27 endpoints already exist.
- Filesystem-based state, **no DB**. Status is derived from which files exist.
- `scripts/autopull.sh` (LaunchAgent, every 4h) orchestrates per-chapter:
  `detect_commentary → generate_audio → export_chapter`. It already has a `cleanup()`
  EXIT trap that fires on non-zero exit (autopull.sh).
- Queue processor (`queue/processor.py`) has an `_on_chapter_complete` callback
  (processor.py:252) wired in `routes.py:119`, which **auto-exports** the chapter via
  `exporter.export_chapter(...)`. The manual `POST /api/export` handler (`routes.py:912`)
  calls the **same** exporter — so export-success is a single chokepoint.
- `config.py` uses `pydantic_settings.BaseSettings`, env prefix `AUDIOBOOK_`, paths
  relative to project root. `logs/` already exists (autopull writes there).

## Phase 1 — Event store (backend)

### Design decisions
- **Storage:** append-only `logs/events.jsonl`, one JSON object per line. Fits the
  no-DB/filesystem ethos; an event *history* is not file-derivable, so it is a
  legitimate new artifact (already covered by gitignore: `logs/*`).
- **Cursor:** monotonic integer `id` (= 1-based line number). Pollers pass `since=<id>`
  and get events with `id > since` plus the new max id. Reading from a line offset is
  cheap and needs no index.
- **Single writer:** only the **backend** appends to the file. `autopull.sh` never writes
  the file directly — it emits run-level events via `POST /api/events`. This avoids
  multi-process append races. Backend-internal appends are guarded by a process-local
  `asyncio.Lock` (and `O_APPEND` writes, which are atomic for small lines).

### Event schema
```json
{ "id": 42, "ts": "2026-06-23T21:05:00Z", "type": "chapter.completed",
  "fiction_id": "124774", "book": 7, "chapter": 10,
  "severity": "info", "detail": {"export_path": "...", "duration_s": 3120.4} }
```
Types emitted in this phase: `chapter.completed`, `run.error`.
(`validation.failed` deferred — see Deferred. `run.started`/`run.completed` optional,
cheap to add from autopull if useful.)

### New module: `backend/src/events.py`
- `EventStore` (singleton via `get_event_store()`, mirroring `get_job_queue()`):
  - `async def emit(type, *, fiction_id=None, book=None, chapter=None, severity="info", detail=None) -> dict`
    — assigns next id (max existing + 1, computed once at startup then in-memory counter),
    stamps `ts` (UTC ISO-8601), appends a line under the lock, returns the event.
  - `def read(since: int = 0, type: str | None = None, limit: int = 200) -> list[dict]`
    — streams lines, filters `id > since` and optional `type`, caps at `limit`.
  - On init, scan the file tail to recover the current max id (survives restarts).
- Path from settings: add `events_log: Path = data_dir.parent / "logs" / "events.jsonl"`
  to `config.py` Settings.

### New endpoints (in `routes.py`, `@app` style)
- `GET /api/events?since=<int>&type=<str>&limit=<int>` →
  `{ "events": [...], "cursor": <max_id_returned_or_since> }`.
- `POST /api/events` (body: `{type, fiction_id?, book?, chapter?, severity?, detail?}`)
  → emits and returns the event. Used by autopull for `run.error`.
- Add request/response pydantic models to `backend/src/api/requests.py` + `models.py`
  following existing conventions.

### Emission hook points
- **`chapter.completed`** — emit on **export success**. Cleanest chokepoint: inside the
  exporter success path (`export/concatenator.py`) OR at both call sites
  (`routes.py:122` auto-export and the `/api/export` handler `routes.py:912`). Prefer the
  exporter chokepoint so queue-driven and manual exports both emit exactly once.
- **`run.error`** — in `autopull.sh` `cleanup()`: on non-zero exit, in addition to the
  existing `notify()`, POST to `/api/events` (best-effort, `curl -sf … || true`; never let
  reporting failure mask the original exit code).

### Phase 1 acceptance
- `POST /api/events` then `GET /api/events?since=0` returns the event with a stable id.
- Completing/exporting a chapter appends one `chapter.completed` line.
- A forced autopull failure appends one `run.error` line.
- Concurrent emits (queue auto-export + a manual POST) never corrupt a line; ids are unique
  and monotonic. (Test with a small asyncio gather.)

## Phase 2 — MCP server

### Design
- **Thin** Python **FastMCP** server (`mcp/audiobook_mcp.py` or a new `mcp/` dir) that
  forwards to `http://localhost:8000`. **No business logic duplicated** — every tool is an
  HTTP call to an existing endpoint (or a small compose of 2–3).
- Runs in `venv` (general deps); add `mcp`/`fastmcp` + `httpx` to that venv's requirements.
  (Keep it out of `venv311`, which is TTS-only.)

### Tools
| Tool | Backing call(s) |
|------|-----------------|
| `audiobook_status(fiction_id?, book?)` | compose `GET /api/books/{f}/{b}/chapters` + `GET /api/queue/status` → per-chapter pipeline state + live queue. Collapses today's ~6-probe "check on book". |
| `audiobook_pending(fiction_id?, book?)` | derive new/incomplete chapters (raw without normalized, or chunks without audio). |
| `audiobook_events(since=0, type?)` | `GET /api/events` (the poll surface). |
| `audiobook_queue()` | `GET /api/queue/status`. |
| `audiobook_process(fiction_id, book, chapters[])` | `POST /api/normalize` → `/api/chunk` → `/api/generate` (mirror autopull's primitive sequence; do NOT reimplement commentary stripping). |
| `audiobook_retry(...)` | `POST /api/queue/retry`. |

### Registration
- Add to project `.mcp.json` (stdio server, command = `venv/bin/python mcp/audiobook_mcp.py`).
- Document the manual start path in README; the backend must be running (`make dev`).

### Phase 2 acceptance
- From a Claude session, `audiobook_status("124774", 7)` returns structured per-chapter
  state + queue in one call, matching what the manual bash probes showed.
- `audiobook_events(since=N)` returns Phase 1 events incrementally.
- `audiobook_process(...)` enqueues generation for the named chapters.

## Deferred (not this spec)
- **Phase 3** — wire `/api/validate` into autopull's per-chapter loop, persist
  `validation.json`, emit `validation.failed`. **Prerequisite** for validation reporting:
  autopull currently has **no validate step**, which is why no `validation.json` exists.
- **Phase 4** — scheduled poller agent (`schedule`/cron) that polls `audiobook_events`,
  bounded auto-retry of failures, pushes a digest.
- Commentary-detection events. Any broker/queue/cloud infra (contradicts single-user design).

## Risks / notes
- Defining "complete" at export-success (shippable) rather than chunks-done avoids
  premature events; the auto-export callback makes these coincide in the queue path.
- `logs/events.jsonl` growth is unbounded but tiny (one line/event); revisit rotation only
  if it matters.
- Keep the MCP a pure adapter — if orchestration logic starts leaking into it, that's a
  signal to lift it into the backend instead (a future `/api/pipeline/run`), not the MCP.
