"""Pinned spoken renderings for tables that no deterministic converter handles.

A legend or novel table shape can't be restated mechanically — deciding what
matters is a reading task, so it is handed to an agent (see
``scripts/render_spec_blocks.py``). Agent output must not reach TTS live: the
narration would drift between runs, which breaks re-rendering a chapter or a
single chunk, and nobody would ever review it.

So renderings are *pinned* — written to ``renderings.json`` beside the chapter,
keyed by a hash of the exact table text. Regeneration then reproduces identical
audio, the rendering is reviewable and editable before it is ever spoken, and
editing the table upstream invalidates its key so the stale narration is caught
rather than silently reused.

Anything still unrendered at normalize time raises: a table that reaches TTS
unrendered becomes a minute of "Acceleration ex-ex", so the chapter stops
instead.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from src.text.spec_blocks import SpecBlock, find_spec_blocks

RENDERINGS_FILE = "renderings.json"
SCHEMA_VERSION = 1


class UnrenderedSpecBlockError(RuntimeError):
    """A detected table has no pinned rendering, so it cannot be spoken."""

    def __init__(self, blocks: list[SpecBlock]):
        self.blocks = blocks
        preview = "; ".join(b.lines[0][:60] for b in blocks[:3])
        super().__init__(
            f"{len(blocks)} table(s) detected with no pinned rendering: {preview}. "
            f"Run scripts/render_spec_blocks.py to render them."
        )


def rendering_key(block: SpecBlock) -> str:
    """Stable id for a block's exact text — edits upstream change the key."""
    body = "\n".join(line.strip() for line in block.lines)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()[:12]


class RenderingStore:
    """The pinned renderings for one chapter."""

    def __init__(self, chapter_dir: Path):
        self.path = Path(chapter_dir) / RENDERINGS_FILE
        self._blocks: dict[str, dict] = {}
        if self.path.exists():
            data = json.loads(self.path.read_text())
            self._blocks = data.get("blocks", {})

    def get(self, key: str) -> str | None:
        entry = self._blocks.get(key)
        return entry.get("rendering") if entry else None

    def put(self, block: SpecBlock, rendering: str, renderer: str) -> str:
        key = rendering_key(block)
        self._blocks[key] = {
            "source": block.lines,
            "rendering": rendering,
            "renderer": renderer,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        return key

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"version": SCHEMA_VERSION, "blocks": self._blocks}
        self.path.write_text(json.dumps(payload, indent=2))

    def prune(self, keys_in_use: set[str]) -> int:
        """Drop renderings whose table no longer appears — they are stale."""
        stale = set(self._blocks) - keys_in_use
        for key in stale:
            del self._blocks[key]
        return len(stale)


def apply_renderings(text: str, store: RenderingStore) -> tuple[str, list[SpecBlock]]:
    """Substitute pinned renderings into ``text``.

    Returns the rewritten text and any blocks left unrendered. Blocks are
    replaced back-to-front so earlier line offsets stay valid.
    """
    blocks = find_spec_blocks(text)
    if not blocks:
        return text, []

    lines = text.split("\n")
    unrendered: list[SpecBlock] = []
    for block in reversed(blocks):
        rendering = store.get(rendering_key(block))
        if rendering is None:
            unrendered.append(block)
            continue
        lines[block.start:block.end] = [rendering]
    unrendered.reverse()
    return "\n".join(lines), unrendered


def render_or_raise(text: str, chapter_dir: Path) -> str:
    """Apply pinned renderings, refusing to pass an unrendered table to TTS."""
    text, unrendered = apply_renderings(text, RenderingStore(chapter_dir))
    if unrendered:
        raise UnrenderedSpecBlockError(unrendered)
    return text
