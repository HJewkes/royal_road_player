#!/usr/bin/env python3
"""Probe what triggers XTTS's phantom-babble hallucination at chunk 419's boundary.

Chunk 419 hallucinates 'wʌnʃɹi' at a dialogue-close + paragraph-break junction
(perfect."\\n\\nHeli). This synthesizes several rewrites of the text a few times each
and measures how often a hallucinated outburst appears — isolating whether the
trailing quote, the paragraph break, or keeping both paragraphs in one chunk is the
cause, and therefore what chunking change would prevent it.

  ./venv311/bin/python scripts/hallucination_probe.py
"""
import sys
import tempfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

from src.tts import get_tts_engine  # noqa: E402
from src.validation.phonemes import (  # noqa: E402
    detect_hallucinations, get_phoneme_recognizer, load_slice,
)

FULL = ('Köngäs means king, right? He\'ll get back in the Finland team, become the '
        'biggest star in the country, make his son proud. Think of the marketing. '
        'The Return of the King! Absolutely perfect."\n\nHeli eyed me sharply. '
        '"That\'s his favourite movie."')
P2 = 'Heli eyed me sharply. "That\'s his favourite movie."'

VARIANTS = [
    ("as-is (baseline)", FULL, 3),
    ("split: 2nd paragraph alone", P2, 3),
    ("paragraph break -> space", FULL.replace("\n\n", " "), 2),
    ("closing quote removed", FULL.replace('perfect."\n\n', "perfect.\n\n"), 2),
]


def main():
    tts, recog = get_tts_engine(), get_phoneme_recognizer()
    print("Hallucination probe (higher = worse)\n")
    for name, text, reps in VARIANTS:
        hits, worst = 0, 0.0
        examples = []
        for _ in range(reps):
            wav = Path(tempfile.mkstemp(suffix=".wav")[1])
            tts.synthesize(text, wav)
            phones = recog.recognize(load_slice(wav, None, None))
            halluc = detect_hallucinations(text, phones)
            if halluc:
                hits += 1
                worst = max(worst, max(h["severity"] for h in halluc))
                examples.append("/" + max(halluc, key=lambda h: h["length"])["phones"] + "/")
        rate = f"{hits}/{reps}"
        print(f"  {name:<30} hallucinated in {rate}  worst_sev={worst:.2f}  {' '.join(examples[:3])}")


if __name__ == "__main__":
    main()
