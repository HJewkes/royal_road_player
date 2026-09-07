"""Durable record of the author-commentary removed from a chapter.

Chunk filenames are derived from normalized.txt and shift on every re-chunk, so
a decision recorded by filename is worthless the moment the chapter is chunked
again. Decisions are therefore persisted as the exact text that was taken out,
and reapplied by substring match against the freshly normalized text.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Iterable

logger = logging.getLogger(__name__)

VERSION = 1
FILENAME = "commentary.json"

PREAMBLE = "preamble"
TRAILING = "trailing"
CHUNK = "chunk"


def commentary_path(chapter_dir: Path) -> Path:
    """Path to a chapter's commentary record, whether or not it exists."""
    return Path(chapter_dir) / FILENAME


def load_records(chapter_dir: Path) -> list[dict]:
    """Read the recorded removals for a chapter; empty when none are on disk."""
    path = commentary_path(chapter_dir)
    if not path.exists():
        return []
    try:
        with open(path) as f:
            return json.load(f).get("removed", [])
    except (OSError, json.JSONDecodeError, AttributeError) as e:
        logger.warning(f"Ignoring unreadable commentary record {path}: {e}")
        return []


def save_records(chapter_dir: Path, records: Iterable[dict], source: str = "claude") -> Path:
    """Write the removals for a chapter, replacing any earlier record."""
    path = commentary_path(chapter_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    document = {
        "version": VERSION,
        "detected_at": datetime.now().isoformat(),
        "source": source,
        "removed": [{"kind": r["kind"], "text": r["text"]} for r in records],
    }
    with open(path, "w") as f:
        json.dump(document, f, indent=2)
    return path


def apply_recorded_removals(text: str, records: Iterable[dict]) -> tuple[str, list[str]]:
    """Re-remove previously recorded commentary from freshly normalized text.

    Returns the cleaned text and the removals whose text was not found — running
    twice leaves the text alone and reports every record as missing.
    """
    missing = []
    changed = False
    for record in records:
        removed = record.get("text") or ""
        if not removed:
            continue
        index = _locate(text, removed, record.get("kind"))
        if index < 0:
            missing.append(removed)
            continue
        text = text[:index] + text[index + len(removed):]
        changed = True
    return (text.strip() + "\n" if changed else text), missing


def _locate(text: str, removed: str, kind: str | None) -> int:
    """Trailing commentary is matched from the end; anything else from the start."""
    return text.rfind(removed) if kind == TRAILING else text.find(removed)
