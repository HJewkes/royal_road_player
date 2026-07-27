#!/usr/bin/env python3
"""Show what the spec-block detector finds in a chapter, and how it reads.

Detection-only dry run: prints each placeholder table it locates, the fields it
decomposed, and the candidate spoken renderings side by side. Touches no audio
and rewrites no files — it exists to make the "what should we say instead?"
decision on real text before anything is regenerated.

Usage:
  preview_spec_blocks.py <fiction_id> <book> <chapter>
  preview_spec_blocks.py --file <path>
"""
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
BACKEND = SCRIPTS.parent / "backend"
sys.path.insert(0, str(BACKEND))

from src.text.spec_blocks import SpecBlock, find_spec_blocks  # noqa: E402


def render_skip(block: SpecBlock) -> str:
    """Drop the table, leaving a single spoken breadcrumb."""
    return "(Interface reference — see the text version.)"


def _named_fields(block: SpecBlock) -> list[str]:
    """Labels that actually head a value — a trailing bare code row like
    "Gk DLRC M F" is a column key, not a field, and reads as noise."""
    return [f.label for f in block.fields if f.value and f.label]


def render_summary(block: SpecBlock) -> str:
    """One sentence naming the shape of the table, not its contents."""
    labels = _named_fields(block)
    if not labels:
        return render_skip(block)
    return f"The profile lists {len(labels)} fields, from {labels[0]} to {labels[-1]}."


def render_labels(block: SpecBlock) -> str:
    """Read the field names, dropping the placeholder values."""
    labels = _named_fields(block)
    if len(labels) < 2:
        return render_skip(block)
    return ", ".join(labels[:-1]) + f", and {labels[-1]}."


RENDERERS = {
    "skip": render_skip,
    "summary": render_summary,
    "labels": render_labels,
}


def _load_text(argv: list[str]) -> tuple[str, str]:
    if len(argv) == 3 and argv[1] == "--file":
        path = Path(argv[2])
    elif len(argv) == 4:
        fiction, book, chapter = argv[1:4]
        path = (BACKEND.parent / "data" / "books" / fiction / f"book_{book}"
                / "chapters" / f"chapter_{chapter}" / "raw.txt")
    else:
        raise SystemExit(__doc__)
    return path.read_text(), str(path)


def main() -> int:
    text, source = _load_text(sys.argv)
    blocks = find_spec_blocks(text)
    print(f"source: {source}")
    print(f"detected {len(blocks)} spec block(s)\n")

    for n, block in enumerate(blocks, 1):
        print(f"=== block {n}: source lines {block.start}-{block.end}, "
              f"{len(block.rows)} rows, {len(block.fields)} fields, "
              f"{block.placeholder_count} placeholders ===\n")
        print("--- verbatim (what TTS was given) ---")
        for line in block.lines:
            print(f"  {line}")
        print("\n--- decomposed ---")
        for row in block.rows:
            cells = [f"{f.label}={f.value or '∅'}" for f in row]
            print("  " + " | ".join(cells))
        print("\n--- candidate renderings ---")
        for name, fn in RENDERERS.items():
            print(f"  [{name}] {fn(block)}")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
