#!/usr/bin/env python3
"""Pin spoken renderings for tables a deterministic converter can't handle.

Detects placeholder tables in a chapter and, for each one not already pinned,
asks a headless agent for narration that conveys what the table means in its
surrounding context. Results are written to renderings.json beside the chapter,
so the audio is reproducible and the wording is reviewable before it is spoken.

The agent sees the decomposed table and the prose on either side, because the
whole reason to involve it is judging what matters *here* — a template can
restate a row, but only a reader can decide 39 fields deserve one sentence.

Usage:
  render_spec_blocks.py <fiction_id> <book> <chapter> [options]

  --dry-run   show what would be rendered, write nothing
  --force     re-render blocks that are already pinned
  --skip      pin a fixed "see the text version" line instead of calling out
  --set TEXT  pin TEXT by hand (single block only)
"""
import json
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
BACKEND = SCRIPTS.parent / "backend"
sys.path.insert(0, str(BACKEND))

from src.config import get_settings  # noqa: E402
from src.text.renderings import RenderingStore, rendering_key  # noqa: E402
from src.text.spec_blocks import SpecBlock, find_spec_blocks  # noqa: E402

CONTEXT_LINES = 12
SKIP_TEXT = "(Interface reference — see the text version.)"
AGENT_TIMEOUT = 180


def build_prompt(block: SpecBlock, lines: list[str]) -> str:
    before = "\n".join(
        ln for ln in lines[max(0, block.start - CONTEXT_LINES):block.start] if ln.strip()
    )
    after = "\n".join(
        ln for ln in lines[block.end:block.end + CONTEXT_LINES] if ln.strip()
    )
    decomposed = "\n".join(
        " | ".join(f"{f.label}={f.value or '(no value)'}" for f in row)
        for row in block.rows
    )
    return f"""You are preparing an audiobook narration of a web-serial chapter.

A table was found in the text. Tables read terribly aloud, so it must be replaced
by spoken narration. This table's values are PLACEHOLDERS ("xx" means "a number
goes here") — it is a legend explaining an interface, not real data.

TEXT IMMEDIATELY BEFORE THE TABLE:
{before}

THE TABLE, decomposed into label=value pairs:
{decomposed}

TEXT IMMEDIATELY AFTER THE TABLE:
{after}

Write the narration that should replace the table. Requirements:
- It is heard, not read. No lists of dozens of items.
- Convey what the table MEANS for a listener following the story. Judge what
  matters; omit what doesn't.
- Do NOT restate anything the text before or after already says — the listener
  hears that too, and repeating it is worse than saying nothing.
- Invent NO facts, and assert NO counts or numbers that the table doesn't
  literally show. Vague is better than wrong.
- Match the surrounding prose's voice. Keep it light.
- 1-3 sentences. Output ONLY the narration, no preamble.
"""


def ask_agent(prompt: str) -> str:
    result = subprocess.run(
        ["claude", "-p", prompt, "--output-format", "text"],
        capture_output=True, text=True, timeout=AGENT_TIMEOUT,
    )
    text = result.stdout.strip()
    if not text:
        raise RuntimeError(f"agent returned nothing (stderr: {result.stderr[:200]})")
    return " ".join(text.split())


def chapter_dir(fiction_id: str, book: int, chapter: int) -> Path:
    return (get_settings().books_dir / fiction_id / f"book_{book}"
            / "chapters" / f"chapter_{chapter}")


def _render(block: SpecBlock, lines: list[str], argv: list[str]) -> tuple[str, str]:
    """Return (rendering, renderer_name) for one block."""
    if "--skip" in argv:
        return SKIP_TEXT, "skip"
    if "--set" in argv:
        return argv[argv.index("--set") + 1], "manual"
    return ask_agent(build_prompt(block, lines)), "agent"


def main() -> int:
    argv = sys.argv
    positional = [a for a in argv[1:] if not a.startswith("--")]
    if len(positional) < 3:
        raise SystemExit(__doc__)
    fiction_id, book, chapter = positional[0], int(positional[1]), int(positional[2])
    dry_run, force = "--dry-run" in argv, "--force" in argv

    directory = chapter_dir(fiction_id, book, chapter)
    raw = (directory / "raw.txt").read_text()
    lines = raw.split("\n")
    blocks = find_spec_blocks(raw)
    if not blocks:
        print("no tables detected — nothing to render")
        return 0

    store = RenderingStore(directory)
    pinned = 0
    for n, block in enumerate(blocks, 1):
        key = rendering_key(block)
        existing = store.get(key)
        if existing and not force:
            print(f"[{n}/{len(blocks)}] {key} already pinned: {existing[:70]}...")
            continue
        rendering, renderer = _render(block, lines, argv)
        print(f"[{n}/{len(blocks)}] {key} ({renderer}, {len(block.rows)} rows)")
        print(f"    {rendering}")
        if not dry_run:
            store.put(block, rendering, renderer)
            pinned += 1

    if dry_run:
        print("\n--dry-run: nothing written")
        return 0
    removed = store.prune({rendering_key(b) for b in blocks})
    store.save()
    print(f"\npinned {pinned}, pruned {removed} stale -> {store.path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
