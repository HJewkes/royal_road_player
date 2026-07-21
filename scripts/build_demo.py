#!/usr/bin/env python3
"""Assemble before/after demo data for the TTS-defect showcase.

For each curated case it extracts a short BEFORE audio clip around the target word
from the shipped chunk audio, runs the phoneme verdict (XTTS-fault vs Whisper-fault),
and — for cases with a candidate lexicon fix — regenerates the chunk with XTTS and
extracts an AFTER clip. Clips are embedded as base64 mp3. Output: logs/demo_data.json,
consumed by the HTML demo page.

Run in the TTS venv (loads XTTS + phoneme model):
  ./venv311/bin/python scripts/build_demo.py
"""
import base64
import io
import json
import sys
import tempfile
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
BACKEND = SCRIPTS.parent / "backend"
sys.path.insert(0, str(BACKEND))

from src.discovery import ChunkDiscovery  # noqa: E402
from src.text.lexicon import get_lexicon  # noqa: E402
from src.tts import get_tts_engine  # noqa: E402
from src.validation.defects import detect_defects, tokenize  # noqa: E402
from src.validation.phonemes import chunk_word_verdicts, get_phoneme_recognizer  # noqa: E402
from src.validation.stt import get_stt_service  # noqa: E402

# Curated ch8 cases. fix = candidate respelling to regenerate an AFTER clip.
CASES = [
    {"word": "Wrexham", "chunk": 165, "fix": None},
    {"word": "enormo", "chunk": 222, "fix": None},
    {"word": "boshtastic", "chunk": 67, "fix": None},
    {"word": "Kisi", "chunk": 220, "fix": None},
    {"word": "Wythenshawe", "chunk": 8, "fix": "Withenshaw"},
    {"word": "Ghanaian", "chunk": 411, "fix": "Gah-nay-un"},
    {"word": "Bochum", "chunk": 478, "fix": "Boakhum"},
    {"word": "match", "chunk": 56, "fix": None},
]
FID, BOOK, CH = "124774", 7, 8


def _clip_b64(wav_path, start, end, pad=0.45):
    """Extract [start-pad, end+pad] from a wav and return base64 mp3."""
    from pydub import AudioSegment
    audio = AudioSegment.from_wav(str(wav_path))
    lo = max(0, int((start - pad) * 1000)) if start is not None else 0
    hi = int((end + pad) * 1000) if end is not None else len(audio)
    buf = io.BytesIO()
    audio[lo:hi].export(buf, format="mp3", bitrate="64k")
    return base64.b64encode(buf.getvalue()).decode()


def _locate_word(word, chunk_text, wav, stt):
    """Return (start, end, whisper_heard) for `word` via its defect, else (None,None,'')."""
    rich = stt.transcribe_rich(wav)
    w = word.lower()
    for d in detect_defects(chunk_text, rich):
        if w in {t.norm for t in tokenize(d.expected)} or w in d.expected.lower():
            return d.audio_start, d.audio_end, d.heard
    return None, None, "(no defect)"


def _sentence(chunk_text, word):
    import re
    for s in re.split(r"(?<=[.!?])\s+", chunk_text.replace("\n", " ")):
        if re.search(rf"\b{re.escape(word)}\b", s, re.IGNORECASE):
            return s.strip()
    return chunk_text[:160].strip()


def _process(case, disc, stt, tts, recog):
    word, idx, fix = case["word"], case["chunk"], case["fix"]
    chunk = disc.get_chunk(FID, BOOK, CH, idx)
    start, end, heard = _locate_word(word, chunk.text, chunk.audio_path, stt)
    phones = recog.recognize_wav(chunk.audio_path)
    verdicts = chunk_word_verdicts(chunk.text, phones, targets=[word])
    v = verdicts[0] if verdicts else {}
    row = {
        "word": word, "chunk": idx, "sentence": _sentence(chunk.text, word),
        "whisper_heard": heard, "source": v.get("source", "?"),
        "distance": v.get("distance"), "expected_phones": v.get("expected_phones"),
        "actual_phones": v.get("actual_phones"),
        "before_mp3": _clip_b64(chunk.audio_path, start, end),
        "after_mp3": None, "fix": fix,
    }
    if fix:
        import re
        fixed = re.sub(rf"\b{re.escape(word)}\b", fix, chunk.text, flags=re.IGNORECASE)
        out = Path(tempfile.mkstemp(suffix=".wav")[1])
        tts.synthesize(fixed, out)
        a_start, a_end, _ = _locate_word(fix.replace("-", ""), fixed, out, stt)
        if a_start is None:
            a_start, a_end = start, end  # fall back to original window
        row["after_mp3"] = _clip_b64(out, a_start, a_end)
    print(f"  {word:<13} source={row['source']} dist={row['distance']} "
          f"{'(+after)' if row['after_mp3'] else ''}", flush=True)
    return row


def main():
    disc, stt = ChunkDiscovery(), get_stt_service()
    recog = get_phoneme_recognizer()
    tts = get_tts_engine() if any(c["fix"] for c in CASES) else None
    print(f"Building demo data for {len(CASES)} cases…")
    rows = [_process(c, disc, stt, tts, recog) for c in CASES]
    out = SCRIPTS.parent / "logs" / "demo_data.json"
    out.write_text(json.dumps(rows, indent=2))
    print(f"Wrote {out} ({out.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
