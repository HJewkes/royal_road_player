"""Append-only pipeline event store.

Events are appended one JSON object per line to ``logs/events.jsonl``. The
integer ``id`` (1-based, equal to the line number) is the poll cursor: consumers
pass ``since=<id>`` and receive events with a greater id. The backend process is
the only writer; external producers (e.g. ``autopull.sh``) emit via
``POST /api/events`` so all writes funnel through this single writer.
"""

import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from src.config import get_settings

logger = logging.getLogger(__name__)


class EventStore:
    """Thread-safe append-only JSONL event log."""

    def __init__(self, path: Optional[Path] = None):
        self._path = path or get_settings().events_log
        self._lock = threading.Lock()
        self._last_id = self._recover_last_id()

    def _recover_last_id(self) -> int:
        """Recover the trailing id so ids stay monotonic across restarts."""
        if not self._path.exists():
            return 0
        last = 0
        try:
            with self._path.open("r", encoding="utf-8") as f:
                for line in f:
                    stripped = line.strip()
                    if not stripped:
                        continue
                    try:
                        last = json.loads(stripped).get("id", last)
                    except json.JSONDecodeError:
                        continue
        except OSError as e:
            logger.warning(f"Could not read event log {self._path}: {e}")
        return last

    def emit(
        self,
        type: str,
        *,
        fiction_id: Optional[str] = None,
        book: Optional[int] = None,
        chapter: Optional[int] = None,
        severity: str = "info",
        detail: Optional[dict[str, Any]] = None,
    ) -> dict:
        """Append one event and return it with its assigned id and timestamp."""
        with self._lock:
            self._last_id += 1
            event = {
                "id": self._last_id,
                "ts": datetime.now(timezone.utc).isoformat(),
                "type": type,
                "fiction_id": fiction_id,
                "book": book,
                "chapter": chapter,
                "severity": severity,
                "detail": detail or {},
            }
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(event) + "\n")
        return event

    def read(
        self,
        since: int = 0,
        type: Optional[str] = None,
        limit: int = 200,
    ) -> list[dict]:
        """Return events with ``id > since``, optionally filtered by type."""
        if not self._path.exists():
            return []
        out: list[dict] = []
        try:
            with self._path.open("r", encoding="utf-8") as f:
                for line in f:
                    stripped = line.strip()
                    if not stripped:
                        continue
                    try:
                        event = json.loads(stripped)
                    except json.JSONDecodeError:
                        continue
                    if event.get("id", 0) <= since:
                        continue
                    if type and event.get("type") != type:
                        continue
                    out.append(event)
                    if len(out) >= limit:
                        break
        except OSError as e:
            logger.warning(f"Could not read event log {self._path}: {e}")
        return out


_store: Optional[EventStore] = None


def get_event_store() -> EventStore:
    """Get the event store singleton."""
    global _store
    if _store is None:
        _store = EventStore()
    return _store
