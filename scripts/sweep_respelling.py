#!/usr/bin/env python3
"""Search for a respelling that makes XTTS pronounce a hard word correctly.

Manual respelling-guessing is unreliable (see the ch8 lexicon experiment: most
hand-guessed spellings did nothing or made XTTS worse). This automates the search:
it synthesizes the target word inside a short carrier phrase for many candidate
spellings in a SINGLE XTTS load, transcribes each, and scores each by how close
the audio lands to the correct word (lower = better). The winner — if it beats
saying the original spelling — is a proven lexicon entry.

Run in the TTS venv:
  ./venv311/bin/python scripts/sweep_respelling.py Wrexham
  ./venv311/bin/python scripts/sweep_respelling.py Wrexham --candidates Reksuhm,Rexsum
  ./venv311/bin/python scripts/sweep_respelling.py Wrexham --apply   # write winner to lexicon
"""
import argparse
import json
import sys
import tempfile
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
BACKEND = SCRIPTS.parent / "backend"
sys.path.insert(0, str(BACKEND))

import re  # noqa: E402

from src.config import get_settings  # noqa: E402
from src.discovery import ChunkDiscovery  # noqa: E402
from src.text.lexicon import generate_candidates  # noqa: E402
from src.tts import get_tts_engine  # noqa: E402
from src.validation.defects import detect_defects, tokenize  # noqa: E402
from src.validation.stt import get_stt_service  # noqa: E402


def _carrier_from_chunk(word, target):
    """Use the real chunk sentence containing `word` as the carrier so the sweep
    reproduces the actual failing context, not an artificially easy one."""
    fid, book, ch, idx = target
    chunk = ChunkDiscovery().get_chunk(fid, book, ch, idx)
    if chunk is None:
        raise SystemExit(f"chunk {target} not found")
    for sentence in re.split(r"(?<=[.!?])\s+", chunk.text.replace("\n", " ")):
        if re.search(rf"\b{re.escape(word)}\b", sentence, re.IGNORECASE):
            return re.sub(rf"\b{re.escape(word)}\b", "{}", sentence, count=1, flags=re.IGNORECASE)
    raise SystemExit(f"{word!r} not found in chunk {target}")


def _score(word, carrier_expected, rich):
    """Severity of the target word's defect in one synthesis (0.0 == clean)."""
    w = word.lower()
    worst, heard = 0.0, "(clean)"
    for d in detect_defects(carrier_expected, rich):
        if w in {t.norm for t in tokenize(d.expected)} or w in d.expected.lower():
            if d.severity >= worst:
                worst, heard = d.severity, d.heard
    return worst, heard


def _evaluate(spelling, word, carrier, tts, stt, repeats):
    """Synthesize the carrier with `spelling` `repeats` times and return the mean
    target-word severity (averaging tames XTTS's run-to-run stochasticity)."""
    expected = carrier.format(word)
    scores, heard = [], "(clean)"
    for _ in range(repeats):
        wav = Path(tempfile.mkstemp(suffix=".wav")[1])
        tts.synthesize(carrier.format(spelling), wav)
        rich = stt.transcribe_rich(wav, use_cache=False)
        if not rich:
            scores.append(1.0)
            continue
        sev, h = _score(word, expected, rich)
        scores.append(sev)
        if sev > 0:
            heard = h
    return sum(scores) / len(scores), heard


def _apply_to_lexicon(path, word, spelling):
    data = json.loads(path.read_text()) if path.exists() else {}
    data[word] = spelling
    path.write_text(json.dumps(data, indent=2) + "\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("word", help="the hard word to find a respelling for")
    ap.add_argument("--candidates", help="extra comma-separated spellings to try")
    ap.add_argument("--carrier", default="I travelled to {} last year.",
                    help="carrier sentence; {} is where the word goes")
    ap.add_argument("--chunk", nargs=4, metavar=("FID", "BOOK", "CH", "IDX"),
                    help="use the real failing sentence from this chunk as the carrier")
    ap.add_argument("--repeats", type=int, default=3,
                    help="syntheses per candidate, averaged (XTTS is stochastic)")
    ap.add_argument("--margin", type=float, default=0.1,
                    help="winner must beat the original spelling by at least this severity")
    ap.add_argument("--apply", action="store_true", help="write the winner into the lexicon")
    args = ap.parse_args()

    carrier = args.carrier
    if args.chunk:
        fid, book, ch, idx = args.chunk
        carrier = _carrier_from_chunk(args.word, (fid, int(book), int(ch), int(idx)))

    extra = [c.strip() for c in (args.candidates or "").split(",") if c.strip()]
    candidates = [args.word] + extra + generate_candidates(args.word)
    seen, ordered = set(), []
    for c in candidates:
        if c.lower() not in seen:
            seen.add(c.lower())
            ordered.append(c)

    print(f"Sweeping {len(ordered)} spellings for {args.word!r} × {args.repeats} "
          f"(carrier: {carrier!r})\n")
    tts = get_tts_engine()
    stt = get_stt_service()

    results = []
    for spelling in ordered:
        sev, heard = _evaluate(spelling, args.word, carrier, tts, stt, args.repeats)
        results.append((sev, spelling, heard))
        print(f"  {spelling:<16} score={sev:.2f}  heard->{heard!r}", flush=True)

    results.sort(key=lambda r: r[0])
    baseline = next(sev for sev, sp, _ in results if sp.lower() == args.word.lower())
    best_sev, best_sp, best_heard = results[0]

    print(f"\nBaseline (original spelling): {baseline:.2f}")
    if best_sp.lower() != args.word.lower() and best_sev <= baseline - args.margin:
        print(f"WINNER: {args.word} -> {best_sp}  (score {best_sev:.2f}, heard {best_heard!r})")
        if args.apply:
            _apply_to_lexicon(Path(get_settings().pronunciation_lexicon_path), args.word, best_sp)
            print(f"Applied to lexicon: {args.word} -> {best_sp}")
        else:
            print(f"Add with: sweep_respelling.py {args.word} --apply  (or edit the lexicon JSON)")
    else:
        print(f"No candidate beat the original spelling by {args.margin:.2f}. "
              f"XTTS may not render {args.word!r} reliably; leave it out.")


if __name__ == "__main__":
    main()
