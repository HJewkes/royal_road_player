#!/usr/bin/env python3
"""Package a folder of ordered audio files into a chaptered .m4b audiobook.

For turning an externally-mastered release (e.g. a Patreon MP3 set with a cover)
into an audiobook file with per-file chapter markers, cover art, and audiobook
metadata. See ``backend/src/export/m4b.py`` for the codec trade-offs.

Typical workflow
----------------
1. Propose chapter titles by transcribing the start of each file (the narrator
   usually announces the title), then eyeball / edit the result::

     ./venv311/bin/python scripts/mp3s_to_m4b.py titles "/path/to/Book" -o titles.txt

2. Build both formats (AAC for Apple Books, lossless MP3 remux as fallback)::

     ./venv311/bin/python scripts/mp3s_to_m4b.py build "/path/to/Book" \
         --title "Soccer Supremo 1" --author "Ted Steel" --titles titles.txt

3. Relabel chapters later without re-encoding (fast, metadata only)::

     ./venv311/bin/python scripts/mp3s_to_m4b.py restamp "Book (AAC).m4b" --titles titles.txt

Apple Books note: it cannot decode MP3-inside-m4b (plays silent), so the AAC
output is the one to test there; the MP3 remux is for other players.
"""
import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from src.export import m4b  # noqa: E402


def _fmt_ts(ms: int) -> str:
    s = ms // 1000
    return f"{s // 60}:{s % 60:02d}"


def _propose_title(heard: str) -> str:
    """Best-effort chapter label from noisy ASR of a file's opening seconds."""
    text = re.sub(r"\s+", " ", heard).strip()
    m = re.match(r"(?i)chapter\s+([\w-]+)[\s.,:-]+(.+)", text)
    if m:
        rest = re.split(r"[.]", m.group(2), maxsplit=1)[0].strip()
        return f"Chapter {m.group(1)} - {rest}"[:80]
    return (re.split(r"[.]", text, maxsplit=1)[0].strip() or "Untitled")[:80]


def _transcribe_head(path: Path, seconds: int, stt) -> str:
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
        wav = Path(tf.name)
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-t", str(seconds), "-i", str(path),
             "-ar", "16000", "-ac", "1", str(wav)],
            capture_output=True,
        )
        return (stt.transcribe(wav, use_cache=False) or "").strip()
    finally:
        wav.unlink(missing_ok=True)


def cmd_titles(args) -> None:
    folder = Path(args.folder)
    files = m4b.list_audio_files(folder)
    if not files:
        sys.exit(f"No audio files in {folder}")
    from src.validation.stt import get_stt_service
    stt = get_stt_service(args.model)
    lines: list[str] = [
        "# One chapter title per line, in file order. '#' lines are ignored.",
        "# Each proposal below is a best guess from the file's opening audio --",
        "# edit freely, then pass this file to `build --titles` or `restamp`.",
        "",
    ]
    for f in files:
        heard = _transcribe_head(f, args.head_seconds, stt)
        dur = _fmt_ts(m4b.probe_duration_ms(f))
        lines.append(f"# {f.name}  [{dur}]  heard: {heard[:110]!r}")
        lines.append(_propose_title(heard))
        print(f"  {f.name}: {_propose_title(heard)!r}", flush=True)
    out = Path(args.output) if args.output else folder / "titles.txt"
    out.write_text("\n".join(lines) + "\n")
    print(f"\nWrote {len(files)} proposed titles -> {out}\n(review/edit, then use --titles)")


def _resolve_titles(files: list[Path], titles_path: str | None) -> list[str]:
    if not titles_path:
        return m4b.default_titles(len(files))
    return m4b.parse_titles_text(Path(titles_path).read_text(), len(files))


def cmd_build(args) -> None:
    folder = Path(args.folder)
    files = m4b.list_audio_files(folder)
    if not files:
        sys.exit(f"No audio files in {folder}")
    cover = Path(args.cover) if args.cover else m4b.find_cover(folder)
    titles = _resolve_titles(files, args.titles)
    out_dir = Path(args.output_dir) if args.output_dir else folder
    formats = {"aac", "mp3"} if args.format == "both" else {args.format}

    durations = [m4b.probe_duration_ms(f) for f in files]
    meta = m4b.build_ffmetadata(
        durations, titles, title=args.title, author=args.author)
    print(f"{len(files)} files, {sum(durations)/3.6e6:.2f} h, cover="
          f"{cover.name if cover else 'none'}")

    if "mp3" in formats:
        ok, msg = m4b.uniform_for_lossless(files)
        if not ok:
            print(f"  ! skipping lossless mp3 remux: {msg}")
            formats.discard("mp3")
        else:
            print(f"  lossless remux ok: {msg}")

    suffix = {"aac": " (AAC)", "mp3": " (MP3)"} if len(formats) > 1 else {"aac": "", "mp3": ""}
    with tempfile.TemporaryDirectory() as td:
        work = Path(td)
        meta_path = work / "chapters.txt"
        meta_path.write_text(meta)
        for fmt in ("aac", "mp3"):
            if fmt not in formats:
                continue
            out = out_dir / f"{args.title}{suffix[fmt]}.m4b"
            print(f"  building {fmt} -> {out.name} ...", flush=True)
            if fmt == "aac":
                m4b.transcode_aac(files, meta_path, cover, out, work, args.bitrate)
            else:
                m4b.remux_lossless(files, meta_path, cover, out, work)
            print(f"    done: {out.stat().st_size/1e6:.0f} MB, "
                  f"{m4b.count_chapters(out)} chapters")


def cmd_restamp(args) -> None:
    target = Path(args.m4b)
    if not target.exists():
        sys.exit(f"Not found: {target}")
    n = m4b.count_chapters(target)
    titles = m4b.parse_titles_text(Path(args.titles).read_text(), n)
    cover = Path(args.cover) if args.cover else None
    durations = _chapter_durations_ms(target)
    meta = m4b.build_ffmetadata(
        durations, titles, title=args.title or target.stem, author=args.author or "")
    with tempfile.TemporaryDirectory() as td:
        work = Path(td)
        meta_path = work / "chapters.txt"
        meta_path.write_text(meta)
        m4b.restamp_titles(target, meta_path, cover, work)
    print(f"Restamped {n} chapters on {target.name}")


def _chapter_durations_ms(m4b_path: Path) -> list[int]:
    import json
    data = json.loads(subprocess.run(
        ["ffprobe", "-v", "error", "-of", "json", "-show_chapters", str(m4b_path)],
        capture_output=True, text=True).stdout)
    out = []
    for c in data["chapters"]:
        out.append(round((float(c["end_time"]) - float(c["start_time"])) * 1000))
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    t = sub.add_parser("titles", help="transcribe file heads -> editable titles.txt")
    t.add_argument("folder")
    t.add_argument("-o", "--output")
    t.add_argument("--head-seconds", type=int, default=30)
    t.add_argument("--model", default="base", help="whisper model size")
    t.set_defaults(func=cmd_titles)

    b = sub.add_parser("build", help="build chaptered m4b(s)")
    b.add_argument("folder")
    b.add_argument("--title", required=True)
    b.add_argument("--author", default="")
    b.add_argument("--cover", help="cover image (default: largest image in folder)")
    b.add_argument("--titles", help="titles file (default: Chapter N)")
    b.add_argument("--format", choices=["both", "aac", "mp3"], default="both")
    b.add_argument("--bitrate", default="128k")
    b.add_argument("--output-dir")
    b.set_defaults(func=cmd_build)

    r = sub.add_parser("restamp", help="relabel chapters on an existing m4b (no re-encode)")
    r.add_argument("m4b")
    r.add_argument("--titles", required=True)
    r.add_argument("--title")
    r.add_argument("--author")
    r.add_argument("--cover")
    r.set_defaults(func=cmd_restamp)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
