#!/usr/bin/env python3
"""Build the hallucination spot-check dataset: shipped audio + context for every flag.

For each flagged chunk in logs/hallucinations_filtered.json this extracts a focused
clip of the SHIPPED audio around the injected-phoneme position (so the reviewer hears
the babble in context), records the chunk text with the babble position marked, the
injected phones, the tier, and a numeric confidence for ranking. Output:
logs/spotcheck_data.json, consumed by render_hallucination_report.py.

No synthesis — reads existing chapter audio only. Fast.

  ./venv311/bin/python scripts/build_spotcheck.py
"""
import base64
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from src.discovery import ChunkDiscovery  # noqa: E402

FILTERED = ROOT / "logs" / "hallucinations_filtered.json"
OUT = ROOT / "logs" / "spotcheck_data.json"

PAD_S = 2.8  # seconds of context on each side of the babble position
TIER_SCORE = {"confirmed": 0.90, "likely": 0.70, "borderline": 0.45, "probable_fp": 0.20}


def _clip_b64(wav_path, position):
    """Return (base64 mp3, clip_seconds, full_seconds) windowed around `position` (0-1)."""
    from pydub import AudioSegment
    audio = AudioSegment.from_wav(str(wav_path)).set_channels(1).set_frame_rate(22050)
    dur = len(audio) / 1000.0
    center = (position or 0.5) * dur
    lo = max(0, int((center - PAD_S) * 1000))
    hi = min(len(audio), int((center + PAD_S) * 1000))
    if hi - lo < 3500:  # keep at least ~3.5s so short chunks stay intelligible
        lo, hi = 0, len(audio)
    buf = io.BytesIO()
    audio[lo:hi].export(buf, format="mp3", bitrate="48k")
    return base64.b64encode(buf.getvalue()).decode(), round((hi - lo) / 1000.0, 1), round(dur, 1)


def _confidence(row):
    """Rankable confidence: tier dominates, corroboration + longer runs break ties within tier."""
    base = TIER_SCORE.get(row["tier"], 0.3)
    bonus = 0.06 * (1 if row.get("whisper_corroborated") else 0) + 0.005 * min(row.get("length", 0), 12)
    return round(min(0.99, base + bonus), 3)


def _mark_text(text, position):
    """Insert a babble marker at the approximate character offset of the injected phones.

    `position` is the fraction of the *audio* phoneme string where the injected run
    starts, so everything before it is real speech. The marker therefore snaps
    FORWARD to the next word boundary (end of the last real word), and a late-position
    babble (the common trailing-quote case) lands at the very end of the chunk.
    """
    if position is None:
        return text
    text = text.rstrip()
    i = max(0, min(len(text), int(position * len(text))))
    j = text.find(" ", i)
    if j == -1 or len(text) - i <= 12:  # trailing babble → after everything
        return text + " ⟨▓⟩"
    return text[:j] + " ⟨▓⟩" + text[j:]


def main():
    rows = json.loads(FILTERED.read_text())["rows"]
    disc = ChunkDiscovery()
    out = []
    for k, r in enumerate(rows, 1):
        chunk = disc.get_chunk("124774", r["book"], r["chapter"], r["chunk"])
        if not chunk or not chunk.has_audio:
            continue
        b64, clip_s, full_s = _clip_b64(chunk.audio_path, r.get("position"))
        out.append({
            "book": r["book"], "chapter": r["chapter"], "chunk": r["chunk"],
            "tier": r["tier"], "confidence": _confidence(r),
            "phones": r["phones"], "length": r.get("length"),
            "position": r.get("position"), "whisper_corroborated": r.get("whisper_corroborated"),
            "clip_seconds": clip_s, "full_seconds": full_s,
            "text": _mark_text(chunk.text.strip(), r.get("position")),
            "mp3": b64,
        })
        if k % 20 == 0:
            print(f"  {k}/{len(rows)} clips…", flush=True)
    out.sort(key=lambda x: -x["confidence"])
    OUT.write_text(json.dumps(out, indent=2))
    size_mb = OUT.stat().st_size / 1e6
    print(f"Wrote {OUT} — {len(out)} spot-check cases, {size_mb:.1f} MB")


if __name__ == "__main__":
    main()
