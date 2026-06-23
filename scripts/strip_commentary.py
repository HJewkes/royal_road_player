"""Strip author commentary from Patreon chapter chunks.

Handles three cases:
1. Pure commentary chunks at the end — auto-detected and deleted
2. Sign-off text appended to the last story chunk — stripped, wav deleted for regen
3. Trailing content after ellipsis/dot separator — stripped

Usage:
  python strip_commentary.py [--dry-run] [--fiction-id ID] [--book BOOK]

Without --book, processes all books for the fiction ID.
"""

import argparse
import re
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data" / "books"

# Pattern matches everything from the ellipsis separator to end of text
TRAILING_PATTERN = re.compile(
    r'\n\s*[…]+\s*\n'
    r'.*$',
    re.DOTALL
)

# Alt pattern: single dot used as separator
DOT_SEPARATOR_PATTERN = re.compile(
    r'\n\s*\.\s*\n'
    r'.*$',
    re.DOTALL
)

# Fallback: "Thanks for your support!" without a preceding separator
SIGNOFF_ONLY_PATTERN = re.compile(
    r'\n\s*Thanks\s+for\s+your\s+su[po]+[rt]+!?'
    r'.*$',
    re.DOTALL | re.IGNORECASE
)

# Patterns that indicate a chunk is pure commentary (not story content)
COMMENTARY_PATTERNS = [
    # Pure sign-off
    re.compile(r'^Thanks\s+for\s+your\s+su[po]+[rt]+!?', re.IGNORECASE),
    # Scheduling notes
    re.compile(r'^SCHEDULING\s+NOTE', re.IGNORECASE),
    # "Next chapter" / "Next:" teasers
    re.compile(r'^Next\s*(chapter|:)', re.IGNORECASE),
    # "Probably Tuesday" etc.
    re.compile(r'^Probably\s+(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)', re.IGNORECASE),
    # Game/link plugs
    re.compile(r"^(I'm on|If you want to play|That will be the end of)", re.IGNORECASE),
    # Word count notes
    re.compile(r'^Book\s+\d+\s+was\s+', re.IGNORECASE),
    # "How not to sign" style reference links (short chunks after sign-off)
    re.compile(r"^(How\s+not\s+to|Max's\s+inspiration)", re.IGNORECASE),
    # Discord/community instructions
    re.compile(r"^(Please\s+note|Copy\s+paste|Go\s+to\s+the|Thanks\s+to\s+\w+\s+for)", re.IGNORECASE),
    # Reference links / "more about" recommendations
    re.compile(r"^(A\s+real-life|More\s+about|Here'?s?\s+a\s+link|Check\s+out)", re.IGNORECASE),
    # Discord invite links
    re.compile(r"^A\s+new\s+Discord\s+link", re.IGNORECASE),
    # Author asides asking readers for input
    re.compile(r"^If\s+anyone\s+has\s+any\s+ideas", re.IGNORECASE),
]


def strip_trailing(text: str) -> str:
    """Remove trailing commentary after the ellipsis/dot separator."""
    cleaned = TRAILING_PATTERN.sub('', text)
    cleaned = DOT_SEPARATOR_PATTERN.sub('', cleaned)
    cleaned = SIGNOFF_ONLY_PATTERN.sub('', cleaned)
    return cleaned.rstrip() + '\n'


def is_pure_commentary(text: str) -> bool:
    """Check if a chunk is entirely non-story content."""
    stripped = text.strip()
    if not stripped:
        return True
    for pattern in COMMENTARY_PATTERNS:
        if pattern.match(stripped):
            return True
    # Very short chunks (< 80 chars) after the sign-off are likely commentary
    # But we only call this on trailing chunks, so length alone isn't enough
    return False


def delete_chunk_files(chunks_dir: Path, index: int) -> list[str]:
    """Delete all files for a chunk index. Returns list of deleted files."""
    deleted = []
    for ext in ['.txt', '.wav', '.error']:
        path = chunks_dir / f"{index:03d}{ext}"
        if path.exists():
            path.unlink()
            deleted.append(path.name)
    return deleted


def process_chapter(fiction_id: str, book_num: int, chapter_num: int, dry_run: bool = False):
    """Process a single chapter: strip sign-offs and delete commentary chunks."""
    chunks_dir = (
        DATA_DIR / fiction_id / f"book_{book_num}"
        / "chapters" / f"chapter_{chapter_num}" / "chunks"
    )
    if not chunks_dir.exists():
        return

    txt_files = sorted(chunks_dir.glob("*.txt"), key=lambda p: int(p.stem))
    if not txt_files:
        return

    deleted_indices = set()
    changes = False

    # 1a. Signoff cascade: if a chunk contains "Thanks for your support!",
    # every chunk after it is post-chapter author commentary regardless of content.
    signoff_re = re.compile(r'Thanks\s+for\s+your\s+su[po]+[rt]+!?', re.IGNORECASE)
    signoff_idx = None
    for i, txt in enumerate(txt_files):
        if signoff_re.search(txt.read_text()):
            signoff_idx = i
            break

    if signoff_idx is not None:
        for txt in txt_files[signoff_idx + 1:]:
            idx = int(txt.stem)
            deleted_indices.add(idx)
            changes = True
            if dry_run:
                preview = txt.read_text().strip()[:60]
                print(f"  DELETE chunk {idx:03d} (after signoff: {preview!r})")
            else:
                deleted = delete_chunk_files(chunks_dir, idx)
                if deleted:
                    print(f"  DELETE chunk {idx:03d} (after signoff): {', '.join(deleted)}")
        remaining = list(txt_files[:signoff_idx + 1])
    else:
        remaining = list(txt_files)

    # 1b. Walk backwards from the last remaining chunk, removing pure commentary
    while remaining:
        last_txt = remaining[-1]
        text = last_txt.read_text()
        if is_pure_commentary(text):
            idx = int(last_txt.stem)
            deleted_indices.add(idx)
            changes = True
            if dry_run:
                preview = text.strip()[:60]
                print(f"  DELETE chunk {idx:03d} (auto-detected commentary: {preview!r})")
            else:
                deleted = delete_chunk_files(chunks_dir, idx)
                if deleted:
                    print(f"  DELETE chunk {idx:03d}: {', '.join(deleted)}")
            remaining.pop()
        else:
            break

    if not remaining:
        return

    # 2. Strip trailing commentary from the last story chunk
    last_txt = remaining[-1]
    text = last_txt.read_text()
    cleaned = strip_trailing(text)
    if cleaned.strip() != text.strip():
        changes = True
        if dry_run:
            removed_start = len(cleaned.rstrip())
            removed_text = text[removed_start:].strip()[:100]
            print(f"  STRIP trailing from chunk {last_txt.stem}")
            print(f"    Removing: {removed_text!r}")
        else:
            last_txt.write_text(cleaned)
            wav = last_txt.with_suffix('.wav')
            if wav.exists():
                wav.unlink()
                print(f"  STRIP trailing from chunk {last_txt.stem}, deleted .wav for regen")
            else:
                print(f"  STRIP trailing from chunk {last_txt.stem} (no .wav to delete)")

    # 3. Delete chapter-level audio.wav so export is recreated
    if changes:
        chapter_dir = chunks_dir.parent
        audio_wav = chapter_dir / "audio.wav"
        if audio_wav.exists():
            if dry_run:
                print(f"  DELETE chapter audio.wav for re-export")
            else:
                audio_wav.unlink()
                print(f"  DELETE chapter audio.wav for re-export")


def main():
    parser = argparse.ArgumentParser(description="Strip author commentary from chapter chunks")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without applying")
    parser.add_argument("--fiction-id", default="124774", help="Fiction ID (default: 124774)")
    parser.add_argument("--book", type=int, help="Specific book number (default: all books)")
    args = parser.parse_args()

    if args.dry_run:
        print("=== DRY RUN (no changes) ===\n")

    fiction_dir = DATA_DIR / args.fiction_id
    if not fiction_dir.exists():
        print(f"Fiction directory not found: {fiction_dir}")
        return

    # Find book directories
    if args.book:
        book_dirs = [fiction_dir / f"book_{args.book}"]
    else:
        book_dirs = sorted(
            [d for d in fiction_dir.iterdir() if d.is_dir() and d.name.startswith("book_")],
            key=lambda d: int(d.name.replace("book_", ""))
        )

    for book_dir in book_dirs:
        if not book_dir.exists():
            continue
        book_num = int(book_dir.name.replace("book_", ""))
        chapters_dir = book_dir / "chapters"
        if not chapters_dir.exists():
            continue

        chapter_dirs = sorted(
            [d for d in chapters_dir.iterdir() if d.is_dir() and d.name.startswith("chapter_")],
            key=lambda d: int(d.name.replace("chapter_", ""))
        )

        for ch_dir in chapter_dirs:
            chapter_num = int(ch_dir.name.replace("chapter_", ""))
            print(f"B{book_num} Ch{chapter_num}:")
            process_chapter(args.fiction_id, book_num, chapter_num, dry_run=args.dry_run)

    if args.dry_run:
        print("\nRe-run without --dry-run to apply changes.")
    else:
        print("\nDone. Trigger audio generation for modified chunks, then re-export chapters.")


if __name__ == "__main__":
    main()
