#!/usr/bin/env python3
"""Export all available chapters for a book."""

import json
import subprocess
import sys
from pathlib import Path

BASE_URL = "http://localhost:8000"


def get_chapters(fiction_id: str, book_number: int):
    """Get list of chapters for a book."""
    url = f"{BASE_URL}/api/books/{fiction_id}/{book_number}/chapters"
    result = subprocess.run(
        ["curl", "-s", url],
        capture_output=True,
        text=True,
    )
    result.check_returncode()
    return json.loads(result.stdout)


def export_chapter(fiction_id: str, book_number: int, chapter_number: int, format: str = "mp3"):
    """Export a single chapter."""
    url = f"{BASE_URL}/api/export"
    payload = {
        "fiction_id": fiction_id,
        "book_number": book_number,
        "chapter_number": chapter_number,
        "format": format,
    }
    result = subprocess.run(
        ["curl", "-s", "-X", "POST", url, "-H", "Content-Type: application/json", "-d", json.dumps(payload)],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        try:
            response = json.loads(result.stdout)
            if "data" in response and "path" in response["data"]:
                print(f"✅ Chapter {chapter_number}: {response['data']['path']}")
                return True
            else:
                print(f"❌ Chapter {chapter_number}: {result.stdout}")
                return False
        except json.JSONDecodeError:
            print(f"❌ Chapter {chapter_number}: {result.stdout}")
            return False
    else:
        print(f"❌ Chapter {chapter_number}: {result.stderr}")
        return False


def main():
    if len(sys.argv) < 3:
        print("Usage: export_book.py <fiction_id> <book_number> [format]")
        print("  format: mp3 (default), m4b, or wav")
        sys.exit(1)

    fiction_id = sys.argv[1]
    book_number = int(sys.argv[2])
    format = sys.argv[3] if len(sys.argv) > 3 else "mp3"

    print(f"Exporting book {book_number} for fiction {fiction_id}...")
    print(f"Format: {format}\n")

    # Get chapters
    chapters = get_chapters(fiction_id, book_number)

    # Export chapters that have at least some audio
    exported = 0
    skipped = 0

    for chapter in chapters:
        ch_num = chapter["chapter_number"]
        chunks_completed = chapter.get("chunks_completed", 0)
        is_audio_complete = chapter.get("is_audio_complete", False)
        is_exported = chapter.get("is_exported", False)

        if is_exported:
            print(f"⏭️  Chapter {ch_num}: Already exported")
            skipped += 1
            continue

        if chunks_completed == 0:
            print(f"⏭️  Chapter {ch_num}: No audio chunks available")
            skipped += 1
            continue

        # Try to export (works even if partial)
        if export_chapter(fiction_id, book_number, ch_num, format):
            exported += 1
        else:
            skipped += 1

    print(f"\n✅ Exported: {exported}")
    print(f"⏭️  Skipped: {skipped}")


if __name__ == "__main__":
    main()
