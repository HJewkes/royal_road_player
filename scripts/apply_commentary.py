#!/usr/bin/env python3
"""Apply the commentary decisions autopull gets from Claude, and record them.

Applying to the chunk files alone is not durable: chunk_discovery.save_chunks
rewrites every NNN.txt from normalized.txt, so a re-chunk resurrects both the
deleted chunks and the stripped tail. So the same removals are also made in
normalized.txt and written to commentary.json as exact text, which is what
survives re-chunking and re-normalizing.

Usage:
  apply_commentary.py <chapter_dir> --preamble JSON --commentary JSON
"""
import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
BACKEND = SCRIPTS.parent / "backend"
sys.path.insert(0, str(BACKEND))

from src.text.commentary import (  # noqa: E402
    CHUNK,
    PREAMBLE,
    TRAILING,
    apply_recorded_removals,
    save_records,
)


@dataclass
class Decisions:
    """The two Claude answers, reduced to what apply needs."""
    preamble_deletes: list[str] = field(default_factory=list)
    strip_start: tuple[str, str] | None = None
    trailing_deletes: list[str] = field(default_factory=list)
    strip_trailing: tuple[str, str] | None = None


def parse_decisions(preamble_raw: str, commentary_raw: str) -> Decisions:
    """Read both answers leniently: malformed JSON means "nothing to remove"."""
    preamble = _load(preamble_raw)
    commentary = _load(commentary_raw)

    decisions = Decisions()
    if isinstance(preamble, list):
        decisions.preamble_deletes = [str(f) for f in preamble]
    elif isinstance(preamble, dict):
        decisions.strip_start = _pair(preamble, "strip_start", "remove_before")

    if isinstance(commentary, dict):
        decisions.trailing_deletes = [str(f) for f in commentary.get("delete_chunks", [])]
        trailing = commentary.get("strip_trailing")
        if isinstance(trailing, dict):
            decisions.strip_trailing = _pair(trailing, "file", "remove_from")
    return decisions


def _load(raw: str):
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None


def _pair(source: dict, file_key: str, text_key: str) -> tuple[str, str] | None:
    name, marker = source.get(file_key), source.get(text_key)
    return (str(name), str(marker)) if name and marker else None


def build_records(chunks_dir: Path, normalized: str, decisions: Decisions) -> list[dict]:
    """Resolve the decisions into the exact spans of normalized.txt they remove."""
    names = _by_index(p.name for p in chunks_dir.glob("*.txt"))
    records = []
    preamble = _preamble_record(chunks_dir, normalized, decisions, names)
    if preamble:
        records.append(preamble)
    records.extend(_trailing_records(chunks_dir, normalized, decisions, names))
    return records


def _preamble_record(
    chunks_dir: Path, normalized: str, decisions: Decisions, names: list[str]
) -> dict | None:
    """Everything before the first surviving story text is preamble."""
    end = -1
    if decisions.strip_start:
        name, marker = decisions.strip_start
        kept = _text_after(chunks_dir / name, marker)
        end = normalized.find(kept) if kept else -1
    elif _is_prefix(decisions.preamble_deletes, names):
        last = _read(chunks_dir / decisions.preamble_deletes[-1])
        found = normalized.find(last) if last else -1
        end = found + len(last) if found >= 0 else -1
    return {"kind": PREAMBLE, "text": normalized[:end]} if end > 0 else None


def _trailing_records(
    chunks_dir: Path, normalized: str, decisions: Decisions, names: list[str]
) -> list[dict]:
    """Everything after the last surviving story text is trailing commentary.

    Deletions that don't run to the end of the chapter can't be described that
    way, so each one is recorded on its own instead.
    """
    if decisions.trailing_deletes and not _is_suffix(decisions.trailing_deletes, names):
        return [
            {"kind": CHUNK, "text": text}
            for name in decisions.trailing_deletes
            if (text := _read(chunks_dir / name))
        ]

    start = _trailing_start(chunks_dir, normalized, decisions)
    return [{"kind": TRAILING, "text": normalized[start:]}] if start > 0 else []


def _trailing_start(chunks_dir: Path, normalized: str, decisions: Decisions) -> int:
    if decisions.strip_trailing:
        name, marker = decisions.strip_trailing
        kept = _text_before(chunks_dir / name, marker)
        found = normalized.rfind(kept) if kept else -1
        return found + len(kept) if found >= 0 else -1
    if decisions.trailing_deletes:
        first = _read(chunks_dir / _by_index(decisions.trailing_deletes)[0])
        return normalized.rfind(first) if first else -1
    return -1


def _by_index(names) -> list[str]:
    """Chunk order is numeric, and a name we can't read that way sorts last."""
    def key(name: str) -> int:
        stem = Path(name).stem
        return int(stem) if stem.isdigit() else sys.maxsize

    return sorted(names, key=key)


def _is_prefix(selected: list[str], names: list[str]) -> bool:
    return bool(selected) and set(selected) == set(names[: len(selected)])


def _is_suffix(selected: list[str], names: list[str]) -> bool:
    return bool(selected) and set(selected) == set(names[-len(selected):])


def apply_to_chunks(chunks_dir: Path, decisions: Decisions) -> list[str]:
    """Mutate the chunk files themselves so the current run doesn't speak them."""
    lines = []
    for name in decisions.preamble_deletes:
        if _delete_chunk(chunks_dir, name):
            lines.append(f"Deleted preamble chunk: {name}")
    for name in decisions.trailing_deletes:
        if _delete_chunk(chunks_dir, name):
            lines.append(f"Deleted commentary chunk: {name}")
    if decisions.strip_start:
        name, marker = decisions.strip_start
        lines.append(_rewrite(chunks_dir / name, _text_after(chunks_dir / name, marker), name))
    if decisions.strip_trailing:
        name, marker = decisions.strip_trailing
        kept = _text_before(chunks_dir / name, marker)
        lines.append(_rewrite(chunks_dir / name, kept + "\n" if kept else "", name))
    return [line for line in lines if line]


def _rewrite(path: Path, kept: str | None, name: str) -> str:
    if not kept:
        return f"WARNING: Could not find marker in {name}"
    path.write_text(kept)
    path.with_suffix(".wav").unlink(missing_ok=True)
    return f"Stripped {name} to {len(kept)} chars"


def _delete_chunk(chunks_dir: Path, name: str) -> bool:
    path = chunks_dir / name
    if not path.is_file():
        return False
    for suffix in (".txt", ".wav", ".error"):
        path.with_suffix(suffix).unlink(missing_ok=True)
    return True


def _read(path: Path) -> str:
    return path.read_text() if path.is_file() else ""


def _text_before(path: Path, marker: str) -> str:
    text = _read(path)
    index = text.find(marker)
    return text[:index].rstrip() if index > 0 else ""


def _text_after(path: Path, marker: str) -> str:
    text = _read(path)
    index = text.find(marker)
    return text[index:] if index > 0 else ""


def apply_commentary(chapter_dir: Path, preamble_raw: str, commentary_raw: str) -> list[str]:
    """Apply and persist one chapter's decisions. Returns lines for the log."""
    decisions = parse_decisions(preamble_raw, commentary_raw)
    chunks_dir = chapter_dir / "chunks"
    normalized_path = chapter_dir / "normalized.txt"
    normalized = _read(normalized_path)

    records = build_records(chunks_dir, normalized, decisions) if normalized else []
    lines = apply_to_chunks(chunks_dir, decisions)
    if not records:
        return lines

    normalized, missing = apply_recorded_removals(normalized, records)
    lines.extend(f"WARNING: not in normalized.txt: {text[:60]!r}" for text in missing)
    normalized_path.write_text(normalized)
    save_records(chapter_dir, records)
    lines.append(f"Recorded {len(records)} commentary removal(s) in commentary.json")
    return lines


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("chapter_dir", type=Path)
    parser.add_argument("--preamble", default="[]")
    parser.add_argument("--commentary", default="{}")
    args = parser.parse_args()

    for line in apply_commentary(args.chapter_dir, args.preamble, args.commentary):
        print(line)


if __name__ == "__main__":
    main()
