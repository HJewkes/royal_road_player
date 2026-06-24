"""Audiobook MCP server.

A thin adapter exposing the audiobook FastAPI pipeline as MCP tools so a Claude
agent can observe and drive it with structured calls. It holds NO business logic
of its own — every tool is an HTTP call to the backend (default
http://localhost:8000), which must be running (`make dev`).

Env:
  AUDIOBOOK_API          backend base URL (default http://localhost:8000)
  AUDIOBOOK_FICTION_ID   default fiction id when a tool omits it (default 124774)
"""

import os
from typing import Optional

import httpx
from mcp.server.fastmcp import FastMCP

API = os.environ.get("AUDIOBOOK_API", "http://localhost:8000")
DEFAULT_FICTION = os.environ.get("AUDIOBOOK_FICTION_ID", "124774")

mcp = FastMCP("audiobook")


def _request(method: str, path: str, *, json: Optional[dict] = None, params: Optional[dict] = None):
    """Call the backend and return parsed JSON, or a structured error dict."""
    try:
        with httpx.Client(base_url=API, timeout=60.0) as client:
            resp = client.request(method, path, json=json, params=params)
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as e:
        return {"error": f"{e.response.status_code} {e.response.reason_phrase}", "body": e.response.text}
    except httpx.HTTPError as e:
        return {"error": f"backend unreachable at {API}: {e}"}


@mcp.tool()
def audiobook_books(fiction_id: str = DEFAULT_FICTION) -> dict:
    """List books for a fiction (use to discover the latest book number)."""
    return {"fiction_id": fiction_id, "books": _request("GET", f"/api/books/{fiction_id}")}


@mcp.tool()
def audiobook_status(book: int, fiction_id: str = DEFAULT_FICTION) -> dict:
    """Composite pipeline status for one book: per-chapter state + live queue +
    a rollup summary. Collapses the multi-call 'check on book' into one result."""
    chapters = _request("GET", f"/api/books/{fiction_id}/{book}/chapters")
    queue = _request("GET", "/api/queue/status")
    summary = {}
    if isinstance(chapters, list):
        summary = {
            "total": len(chapters),
            "exported": sum(1 for c in chapters if c.get("is_exported")),
            "audio_complete": sum(1 for c in chapters if c.get("is_audio_complete")),
            "pending": sum(1 for c in chapters if not c.get("is_exported")),
        }
    return {"fiction_id": fiction_id, "book": book, "summary": summary,
            "chapters": chapters, "queue": queue}


@mcp.tool()
def audiobook_pending(book: int, fiction_id: str = DEFAULT_FICTION) -> dict:
    """Chapters not yet exported, with their current pipeline stage."""
    chapters = _request("GET", f"/api/books/{fiction_id}/{book}/chapters")
    if not isinstance(chapters, list):
        return chapters
    pending = [
        {"chapter": c["chapter_number"], "status": c["status"],
         "is_normalized": c["is_normalized"], "is_chunked": c["is_chunked"],
         "is_audio_complete": c["is_audio_complete"],
         "progress_percent": c["progress_percent"]}
        for c in chapters if not c.get("is_exported")
    ]
    return {"fiction_id": fiction_id, "book": book, "pending": pending}


@mcp.tool()
def audiobook_queue() -> dict:
    """Current generation queue status (running job, pending chunks, queued chapters)."""
    return _request("GET", "/api/queue/status")


@mcp.tool()
def audiobook_events(since: int = 0, type: Optional[str] = None, limit: int = 200) -> dict:
    """Poll pipeline events with id > `since` (the reporting surface). Returns a
    `cursor` to pass as `since` next time. `type` filters e.g. 'chapter.completed',
    'run.error'."""
    params = {"since": since, "limit": limit}
    if type:
        params["type"] = type
    return _request("GET", "/api/events", params=params)


@mcp.tool()
def audiobook_process(book: int, chapters: list[int], fiction_id: str = DEFAULT_FICTION) -> dict:
    """Run normalize -> chunk -> generate for the given chapters (mirrors autopull's
    primitives; generation runs in the background queue). Does not strip commentary."""
    body = {"fiction_id": fiction_id, "book_number": book, "chapter_numbers": chapters}
    return {
        "normalize": _request("POST", "/api/normalize", json=body),
        "chunk": _request("POST", "/api/chunk", json=body),
        "generate": _request("POST", "/api/generate", json=body),
    }


@mcp.tool()
def audiobook_retry() -> dict:
    """Re-queue failed generation jobs."""
    return _request("POST", "/api/queue/retry")


if __name__ == "__main__":
    mcp.run()
