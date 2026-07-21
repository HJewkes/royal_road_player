#!/usr/bin/env python3
"""Fix pass: regenerate problematic chunks (best-of-N with param perturbation) and
keep only the takes that measurably improve the flagged word's pronunciation.

For each bad chunk (an XTTS-fault from the phoneme-triaged test set) it re-synthesizes
the WHOLE chunk several times under different XTTS decoder settings, scores each take's
flagged-word phoneme distance, and picks the best. A regenerated chunk is kept only if
it beats the shipped audio by a margin; ties/worse are discarded (never ship a worse
concatenation-swap). Emits logs/fix_results.json with full-chunk before/after mp3 for
the demo and the overall improvement rate.

  ./venv311/bin/python scripts/fix_pass.py [--limit N] [--takes K]
"""
import argparse
import base64
import io
import json
import sys
import tempfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

from src.discovery import ChunkDiscovery  # noqa: E402
from src.tts import get_tts_engine  # noqa: E402
from src.validation.defects import tokenize  # noqa: E402
from src.validation.phonemes import (  # noqa: E402
    XTTS_FAULT_THRESHOLD, chunk_word_verdicts, get_phoneme_recognizer, load_slice,
)

DATASET = BACKEND.parent / "data" / "test_set" / "tts_defects.jsonl"
OUT = BACKEND.parent / "logs" / "fix_results.json"
MARGIN = 0.06  # after must beat before by this to count as an improvement

# Perturbed re-rolls: one reseed at defaults, then decoder variations that the
# param study found rescue stochastic mangles. First entry == checkpoint defaults.
PARAM_TAKES = [
    ("reseed", {}),
    ("temp0.85", {"temperature": 0.85}),
    ("rep2.0", {"repetition_penalty": 2.0}),
]

# Recurring proper nouns worth prioritising (from the 5-chapter audit).
PRIORITY = {"etihad", "bochum", "salerno", "lazaar", "fogerty", "miina", "heli",
            "hough", "match", "ghanaian", "croft"}


import re

_ELONGATED = re.compile(r"(.)\1\1", re.IGNORECASE)  # 3+ same char = stylized noise


def _content_words(expected):
    if expected.startswith("("):
        return []
    return [t.original for t in tokenize(expected)
            if not t.norm.startswith("#") and len(t.norm) >= 3
            and not _ELONGATED.search(t.original)]  # skip FWAAAAHHHH / Maaaxxx


def _select(limit):
    """Unique bad chunks: recurring proper nouns first, then by severity."""
    rows = [json.loads(l) for l in DATASET.read_text().splitlines() if l]
    by_chunk = {}
    for r in rows:
        if r["label"] != "bad":
            continue
        key = (r["book"], r["chapter"], r["chunk"])
        entry = by_chunk.setdefault(key, {"words": set(), "row": r})
        entry["words"].update(_content_words(r["expected"]))
    items = [(k, v) for k, v in by_chunk.items() if v["words"]]
    # Honest mix: half contextual (common words like 'match' — best-of-N should
    # rescue these), half intrinsic recurring proper nouns (the hard cases).
    contextual = [it for it in items if "match" in {w.lower() for w in it[1]["words"]}]
    proper = [it for it in items if {w.lower() for w in it[1]["words"]} & (PRIORITY - {"match"})]
    contextual.sort(key=lambda kv: -kv[1]["row"]["severity"])
    proper.sort(key=lambda kv: -kv[1]["row"]["severity"])
    half = max(1, limit // 3)
    mix = contextual[:half] + proper[:limit - half]
    return mix[:limit]


def _score(chunk_text, wav, words, recog):
    phones = recog.recognize_wav(wav) if isinstance(wav, Path) and wav.exists() else None
    if phones is None:
        return 1.0, {}
    verdicts = chunk_word_verdicts(chunk_text, phones, targets=words)
    if not verdicts:
        return 0.0, {}
    worst = max(verdicts, key=lambda v: v["distance"])
    return worst["distance"], worst


def _mp3(wav_path):
    from pydub import AudioSegment
    buf = io.BytesIO()
    AudioSegment.from_wav(str(wav_path)).export(buf, format="mp3", bitrate="48k")
    return base64.b64encode(buf.getvalue()).decode()


def _sentence(text, word):
    import re
    for s in re.split(r"(?<=[.!?])\s+", text.replace("\n", " ")):
        if word and re.search(rf"\b{re.escape(word)}\b", s, re.IGNORECASE):
            return s.strip()
    return " ".join(text.split())[:200]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=9, help="chunks to attempt")
    ap.add_argument("--takes", type=int, default=len(PARAM_TAKES), help="regeneration takes")
    args = ap.parse_args()

    disc, tts, recog = ChunkDiscovery(), get_tts_engine(), get_phoneme_recognizer()
    selected = _select(args.limit)
    print(f"Fix pass over {len(selected)} bad chunks, {args.takes} takes each\n")

    results, attempted, improved = [], 0, 0
    for (book, ch, idx), meta in selected:
        chunk = disc.get_chunk("124774", book, ch, idx)
        if not chunk or not chunk.has_audio:
            continue
        words = sorted(meta["words"])
        before, bworst = _score(chunk.text, chunk.audio_path, words, recog)
        if before < XTTS_FAULT_THRESHOLD:
            print(f"  b{book}/ch{ch}/{idx:03d} {words}: shipped already ok ({before:.2f}) — skip")
            continue
        attempted += 1
        takes = []
        for label, params in PARAM_TAKES[:args.takes]:
            wav = Path(tempfile.mkstemp(suffix=".wav")[1])
            tts.synthesize(chunk.text, wav, **params)
            score, worst = _score(chunk.text, wav, words, recog)
            takes.append((score, label, wav, worst))
        takes.sort(key=lambda t: t[0])
        after, blabel, bwav, aworst = takes[0]
        won = after < before - MARGIN
        improved += won
        focus = (bworst or {}).get("word") or words[0]
        print(f"  b{book}/ch{ch}/{idx:03d} {focus!r}: before={before:.2f} "
              f"after={after:.2f} [{blabel}] -> {'IMPROVED' if won else 'no gain (discard)'}")
        results.append({
            "book": book, "chapter": ch, "chunk": idx, "word": focus,
            "sentence": _sentence(chunk.text, focus),
            "before_dist": round(before, 3), "after_dist": round(after, 3),
            "improved": won, "take": blabel,
            "before_phones": (bworst or {}).get("actual_phones"),
            "after_phones": (aworst or {}).get("actual_phones"),
            "expected_phones": (bworst or {}).get("expected_phones"),
            "before_mp3": _mp3(chunk.audio_path),
            "after_mp3": _mp3(bwav) if won else None,
        })

    rate = (100 * improved / attempted) if attempted else 0
    OUT.write_text(json.dumps({"improvement_rate_pct": round(rate, 1),
                               "attempted": attempted, "improved": improved,
                               "results": results}, indent=2))
    print(f"\nImprovement rate: {improved}/{attempted} = {rate:.0f}%")
    print(f"Wrote {OUT} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
