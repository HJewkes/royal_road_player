"""Assemble a chaptered ``.m4b`` audiobook from a folder of ordered audio files.

Used to package an externally-mastered release (e.g. a Patreon MP3 set) into a
single audiobook file with chapter markers, cover art, and audiobook metadata.
This is separate from the TTS pipeline's own export path.

Two output codecs:
  - ``mp3``: lossless remux. The source MP3 streams are stream-copied into an
    MP4/m4b container -- bit-identical audio, no re-encode. Plays in most
    audiobook apps, but Apple Books will NOT decode MP3-in-m4b (it shows the
    timeline but plays silent), so treat this as the non-Apple fallback.
  - ``aac``: transcode to AAC-LC, the codec Apple Books requires. AAC is more
    efficient than MP3, so 128k mono is transparent for spoken word.

Both outputs embed a cover image, one chapter marker per source file, and the
``media_type=2`` flag so players file it under Audiobooks. Chapter titles are
independent metadata, so :func:`restamp_titles` can relabel an existing file via
a fast stream copy without touching the audio.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Iterable, Optional, Sequence

AUDIO_GLOBS = ("*.mp3", "*.m4a", "*.aac", "*.wav")
IMAGE_GLOBS = ("*.jpg", "*.jpeg", "*.png")


# --------------------------------------------------------------------------- #
# Pure helpers (no ffmpeg / filesystem side effects) -- unit tested.
# --------------------------------------------------------------------------- #
def _escape_meta(value: str) -> str:
    """Escape the characters ffmetadata treats as special."""
    return (
        value.replace("\\", "\\\\")
        .replace("=", "\\=")
        .replace(";", "\\;")
        .replace("#", "\\#")
        .replace("\n", "\\\n")
    )


def default_titles(count: int) -> list[str]:
    """Fallback marker labels when no real titles are supplied."""
    return [f"Chapter {i}" for i in range(1, count + 1)]


def parse_titles_text(text: str, expected: int) -> list[str]:
    """Parse a titles file: one title per line, blanks and ``#`` comments ignored.

    Raises ValueError unless the count matches ``expected`` so a mismatched file
    fails loudly instead of silently mislabelling chapters.
    """
    titles = [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    if len(titles) != expected:
        raise ValueError(
            f"titles file has {len(titles)} entries but there are {expected} files"
        )
    return titles


def build_ffmetadata(
    durations_ms: Sequence[int],
    titles: Sequence[str],
    *,
    title: str,
    author: str,
    album: Optional[str] = None,
    genre: str = "Audiobook",
) -> str:
    """Build an FFMETADATA document with a chapter per file at cumulative offsets."""
    if len(durations_ms) != len(titles):
        raise ValueError(
            f"{len(durations_ms)} durations vs {len(titles)} titles"
        )
    lines = [
        ";FFMETADATA1",
        f"title={_escape_meta(title)}",
        f"album={_escape_meta(album or title)}",
        f"artist={_escape_meta(author)}",
        f"genre={_escape_meta(genre)}",
        "media_type=2",
    ]
    start = 0
    for dur, marker in zip(durations_ms, titles):
        end = start + int(dur)
        lines += [
            "[CHAPTER]",
            "TIMEBASE=1/1000",
            f"START={start}",
            f"END={end}",
            f"title={_escape_meta(marker)}",
        ]
        start = end
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- #
# ffprobe / discovery
# --------------------------------------------------------------------------- #
def _ffprobe_json(path: Path, *args: str) -> dict:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-of", "json", *args, str(path)],
        capture_output=True, text=True,
    )
    return json.loads(out.stdout or "{}")


def list_audio_files(folder: Path) -> list[Path]:
    """Return the folder's audio files, sorted by name (i.e. by leading index)."""
    files: list[Path] = []
    for pattern in AUDIO_GLOBS:
        files.extend(folder.glob(pattern))
    return sorted(files)


def find_cover(folder: Path) -> Optional[Path]:
    """Pick the largest image in the folder as cover art, if any."""
    images: list[Path] = []
    for pattern in IMAGE_GLOBS:
        images.extend(folder.glob(pattern))
    return max(images, key=lambda p: p.stat().st_size) if images else None


def probe_duration_ms(path: Path) -> int:
    data = _ffprobe_json(path, "-show_entries", "format=duration")
    return round(float(data["format"]["duration"]) * 1000)


def audio_stream_params(path: Path) -> dict:
    data = _ffprobe_json(
        path, "-select_streams", "a:0",
        "-show_entries", "stream=codec_name,sample_rate,channels",
    )
    stream = (data.get("streams") or [{}])[0]
    return {
        "codec": stream.get("codec_name"),
        "sample_rate": stream.get("sample_rate"),
        "channels": stream.get("channels"),
    }


def uniform_for_lossless(paths: Iterable[Path]) -> tuple[bool, str]:
    """Check every file shares codec/sample-rate/channels (needed to stream-copy).

    Returns (is_uniform, message). Non-uniform inputs can't be losslessly
    concatenated with ``-c copy``; the caller should fall back to AAC.
    """
    params = [audio_stream_params(p) for p in paths]
    if not params:
        return False, "no audio files"
    first = params[0]
    if first["codec"] != "mp3":
        return False, f"lossless remux needs mp3 sources, got {first['codec']}"
    for p in params[1:]:
        if p != first:
            return False, f"mixed formats: {first} vs {p}"
    return True, f"uniform {first['codec']} {first['sample_rate']}Hz {first['channels']}ch"


def count_chapters(m4b: Path) -> int:
    return len(_ffprobe_json(m4b, "-show_chapters").get("chapters", []))


# --------------------------------------------------------------------------- #
# ffmpeg assembly
# --------------------------------------------------------------------------- #
def _run(cmd: list[str]) -> None:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed:\n{result.stderr[-2000:]}")


def _write_concat_list(paths: Sequence[Path], dest: Path) -> None:
    # ffmpeg concat demuxer: single-quote paths, escape embedded quotes.
    lines = ["file '{}'".format(str(p).replace("'", r"'\''")) for p in paths]
    dest.write_text("\n".join(lines) + "\n")


def _assemble(
    paths: Sequence[Path],
    meta_path: Path,
    cover: Optional[Path],
    out: Path,
    work_dir: Path,
    codec_args: list[str],
) -> Path:
    concat_list = work_dir / "concat_list.txt"
    _write_concat_list(paths, concat_list)
    inputs = ["-f", "concat", "-safe", "0", "-i", str(concat_list),
              "-i", str(meta_path)]
    maps = ["-map", "0:a", "-map_metadata", "1", "-map_chapters", "1"]
    cover_args: list[str] = []
    if cover is not None:
        inputs += ["-i", str(cover)]
        maps += ["-map", "2:v", "-disposition:v:0", "attached_pic"]
        cover_args = ["-c:v", "copy"]
    cmd = ["ffmpeg", "-y", *inputs, *maps, *codec_args, *cover_args,
           "-movflags", "+faststart", "-f", "mp4", str(out)]
    _run(cmd)
    return out


def remux_lossless(
    paths: Sequence[Path], meta_path: Path, cover: Optional[Path],
    out: Path, work_dir: Path,
) -> Path:
    """Stream-copy MP3 sources into an m4b (bit-identical, no re-encode)."""
    return _assemble(paths, meta_path, cover, out, work_dir, ["-c:a", "copy"])


def transcode_aac(
    paths: Sequence[Path], meta_path: Path, cover: Optional[Path],
    out: Path, work_dir: Path, bitrate: str = "128k",
) -> Path:
    """Transcode sources to mono AAC-LC (the codec Apple Books requires)."""
    return _assemble(
        paths, meta_path, cover, out, work_dir,
        ["-c:a", "aac", "-b:a", bitrate, "-ar", "44100", "-ac", "1"],
    )


def restamp_titles(
    m4b: Path, meta_path: Path, cover: Optional[Path], work_dir: Path,
) -> Path:
    """Relabel chapters/metadata on an existing m4b via stream copy (no re-encode).

    ``-map_chapters 1`` is required so the new chapters come from ``meta_path``
    rather than the input file's existing (placeholder) chapters.
    """
    tmp = work_dir / (m4b.stem + ".retitle.m4b")
    inputs = ["-i", str(m4b), "-i", str(meta_path)]
    maps = ["-map", "0:a", "-map_metadata", "1", "-map_chapters", "1"]
    cover_args: list[str] = []
    if cover is not None:
        inputs += ["-i", str(cover)]
        maps += ["-map", "2:v", "-disposition:v:0", "attached_pic"]
        cover_args = ["-c:v", "copy"]
    else:
        maps += ["-map", "0:v?"]
        cover_args = ["-c:v", "copy"]
    _run(["ffmpeg", "-y", *inputs, *maps, "-c:a", "copy", *cover_args,
          "-movflags", "+faststart", "-f", "mp4", str(tmp)])
    tmp.replace(m4b)
    return m4b
