#!/usr/bin/env python3
"""Does feeding XTTS phonemes help? Compare input encodings empirically.

For each hard word, synthesize several INPUT encodings (orthographic word, raw
IPA, bracketed/slashed IPA, and grapheme respellings) in one XTTS load, transcribe
each result with the phoneme model, and score how close the produced pronunciation
lands to the word's correct phones (espeak G2P). Lower = better. Answers whether
XTTS can be driven by phonemes or only by respelling.

  ./venv311/bin/python scripts/phoneme_input_test.py
"""
import sys
import tempfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

from src.text.lexicon import generate_candidates  # noqa: E402
from src.tts import get_tts_engine  # noqa: E402
from src.validation.phonemes import (  # noqa: E402
    clean_ipa, g2p, get_phoneme_recognizer, load_slice, phoneme_distance,
)

WORDS = ["Ghanaian", "Bochum", "match"]


def _encodings(word):
    ipa = g2p(word)  # espeak reference phones (cleaned)
    enc = [("orthographic", word), ("raw-IPA", ipa),
           ("slashed-IPA", f"/{ipa}/"), ("bracketed-IPA", f"[{ipa}]")]
    enc += [(f"respell:{c}", c) for c in generate_candidates(word)[:3]]
    return ipa, enc


def main():
    tts = get_tts_engine()
    recog = get_phoneme_recognizer()
    for word in WORDS:
        ref, enc = _encodings(word)
        print(f"\n{word}  (correct phones /{ref}/)")
        rows = []
        for label, text in enc:
            wav = Path(tempfile.mkstemp(suffix=".wav")[1])
            tts.synthesize(text, wav)
            heard = recog.recognize(load_slice(wav, None, None))
            dist = phoneme_distance(ref, heard)
            rows.append((dist, label, text, heard))
        for dist, label, text, heard in sorted(rows):
            print(f"  {dist:.2f}  {label:<18} in={text!r:<20} -> heard /{heard}/")


if __name__ == "__main__":
    main()
