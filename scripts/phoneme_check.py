#!/usr/bin/env python3
"""Verdict each suspected mangle as XTTS-fault vs Whisper-fault via phonemes.

For each (word, chunk) it locates the word's audio (Whisper timestamp), transcribes
just that slice with a vocabulary-free phoneme model, and compares those phones to
the espeak-ng G2P of the intended word. Low distance => the audio is actually
correct and Whisper simply couldn't spell it (not a real defect). High distance =>
XTTS truly mispronounced it (real defect, worth a lexicon fix).

Run in the TTS venv (first run downloads the ~1GB phoneme model):
  ./venv311/bin/python scripts/phoneme_check.py            # built-in known cases
  ./venv311/bin/python scripts/phoneme_check.py Wrexham 124774 7 8 165
"""
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
BACKEND = SCRIPTS.parent / "backend"
sys.path.insert(0, str(BACKEND))

from src.discovery import ChunkDiscovery  # noqa: E402
from src.validation.defects import detect_defects, tokenize  # noqa: E402
from src.validation.phonemes import (  # noqa: E402
    XTTS_FAULT_THRESHOLD, chunk_word_verdicts, get_phoneme_recognizer, load_slice,
)
from src.validation.stt import get_stt_service  # noqa: E402

# (word, fiction, book, chapter, chunk) — seeded from the ch8 two-stage scan.
CASES = [
    ("Wythenshawe", "124774", 7, 8, 8),
    ("boshtastic", "124774", 7, 8, 67),
    ("enormo", "124774", 7, 8, 222),
    ("Wrexham", "124774", 7, 8, 165),
    ("Kisi", "124774", 7, 8, 220),
    ("Ghanaian", "124774", 7, 8, 411),
]

def _whisper_heard(word, chunk, stt):
    """What Whisper transcribed this word as (for reference/contrast only)."""
    rich = stt.transcribe_rich(chunk.audio_path)
    w = word.lower()
    for d in detect_defects(chunk.text, rich):
        if w in {t.norm for t in tokenize(d.expected)} or w in d.expected.lower():
            return d.heard
    return "(no defect)"


def _check(case, disc, stt, recog):
    word, fid, book, ch, idx = case
    chunk = disc.get_chunk(fid, book, ch, idx)
    if chunk is None or not chunk.has_audio:
        print(f"{word:<13} — chunk {idx} missing/no audio")
        return
    # Recognize phones for the WHOLE chunk, then align to place the word positionally.
    actual_full = recog.recognize(load_slice(chunk.audio_path, None, None))
    verdicts = chunk_word_verdicts(chunk.text, actual_full, targets={word.lower()})
    if not verdicts:
        print(f"{word:<13} — alignment unavailable (word/phone mismatch)\n")
        return
    v = verdicts[0]
    verdict = "XTTS mispronounced (REAL)" if v["source"] == "xtts" else "Whisper's fault (audio OK)"
    print(f"{word:<13} dist={v['distance']:.2f}  {verdict}")
    print(f"   expected(G2P):  {v['expected_phones']}")
    print(f"   actual(audio):  {v['actual_phones']}")
    print(f"   whisper heard:  {_whisper_heard(word, chunk, stt)!r}\n")


def main():
    if len(sys.argv) == 6:
        cases = [(sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5]))]
    else:
        cases = CASES

    disc = ChunkDiscovery()
    stt = get_stt_service()
    recog = get_phoneme_recognizer()
    print(f"Phoneme fidelity check ({len(cases)} case(s)); threshold={XTTS_FAULT_THRESHOLD}\n")
    for case in cases:
        _check(case, disc, stt, recog)


if __name__ == "__main__":
    main()
