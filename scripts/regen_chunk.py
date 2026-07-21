#!/usr/bin/env python3
"""Verify a pronunciation-lexicon fix by regenerating a chunk and re-scanning it.

For each target chunk this reads the source text, applies the pronunciation
lexicon, and — if that changed anything — re-synthesizes the audio with XTTS and
re-runs the two-stage STT defect scan against the ORIGINAL word. It prints the
before/after so you can see whether the respelling actually fixed the mangle.

Non-destructive by default: the new audio goes to a temp file and the shipped
chunk .wav/.txt are left untouched (chapters here are already exported). Pass
--in-place to overwrite the real chunk once a respelling is proven.

Run in the TTS venv (needs XTTS + whisper):
  ./venv311/bin/python scripts/regen_chunk.py 124774 7 8 8          # one chunk
  ./venv311/bin/python scripts/regen_chunk.py 124774 7 8 8 102 165  # several
  ./venv311/bin/python scripts/regen_chunk.py --from-json logs/ch8_twostage.json
"""
import argparse
import json
import sys
import tempfile
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
BACKEND = SCRIPTS.parent / "backend"
sys.path.insert(0, str(BACKEND))

from src.config import get_settings  # noqa: E402
from src.discovery import ChunkDiscovery  # noqa: E402
from src.text.lexicon import get_lexicon  # noqa: E402
from src.tts import get_tts_engine  # noqa: E402
from src.validation.defects import confirm_defects, detect_defects  # noqa: E402
from src.validation.stt import get_stt_service  # noqa: E402


def _two_stage(text, wav, base_stt, confirm_stt):
    """Two-stage defect scan of one wav against `text`."""
    base_rich = base_stt.transcribe_rich(wav)
    if not base_rich:
        return []
    base = detect_defects(text, base_rich)
    if not base or confirm_stt is None:
        return base
    confirm_rich = confirm_stt.transcribe_rich(wav)
    return confirm_defects(base, text, confirm_rich) if confirm_rich else base


def _fmt(defects):
    if not defects:
        return "clean"
    return "; ".join(f"{d.expected!r}->{d.heard!r} [{d.severity:.2f}]" for d in defects[:4])


def _targets_from_json(path, lexicon):
    """Chunks in a scan whose flagged word the lexicon can respell."""
    rows = json.load(open(path))
    seen, out = set(), []
    for r in rows:
        if lexicon.apply(r["expected"]) == r["expected"]:
            continue  # lexicon wouldn't change this word
        key = (r["fiction_id"], r["book"], r["chapter"], r["chunk"])
        if key not in seen:
            seen.add(key)
            out.append(key)
    return out


def _process(target, disc, tts, base_stt, confirm_stt, lexicon, in_place):
    fiction_id, book, ch, idx = target
    chunk = disc.get_chunk(fiction_id, book, ch, idx)
    if chunk is None or not chunk.has_audio:
        print(f"  ch{idx:03d}: no chunk/audio — skip")
        return
    fixed = lexicon.apply(chunk.text)
    if fixed == chunk.text:
        print(f"  ch{idx:03d}: lexicon changes nothing — skip")
        return

    before = _two_stage(chunk.text, chunk.audio_path, base_stt, confirm_stt)
    out_wav = chunk.audio_path if in_place else Path(tempfile.mkstemp(suffix=".wav")[1])
    tts.synthesize(fixed, out_wav)
    after = _two_stage(chunk.text, out_wav, base_stt, confirm_stt)

    print(f"  ch{idx:03d}: {'overwrote' if in_place else 'temp'} {out_wav.name}")
    print(f"      before: {_fmt(before)}")
    print(f"      after:  {_fmt(after)}")
    if in_place:
        chunk.text_path.write_text(fixed)  # keep .txt consistent with new audio


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("target", nargs="*", help="fiction_id book chapter chunk [chunk ...]")
    ap.add_argument("--from-json", type=Path, help="regen every lexicon-fixable chunk in a scan")
    ap.add_argument("--in-place", action="store_true", help="overwrite the real chunk (default: temp)")
    args = ap.parse_args()

    settings = get_settings()
    lexicon = get_lexicon()
    disc = ChunkDiscovery()

    if args.from_json:
        targets = _targets_from_json(args.from_json, lexicon)
    elif len(args.target) >= 4:
        fid, book, ch = args.target[0], int(args.target[1]), int(args.target[2])
        targets = [(fid, book, ch, int(c)) for c in args.target[3:]]
    else:
        ap.error("give: fiction_id book chapter chunk [chunk ...]  (or --from-json)")

    if not targets:
        print("No lexicon-fixable chunks to regenerate.")
        return

    print(f"Regenerating {len(targets)} chunk(s){' IN PLACE' if args.in_place else ' (temp, non-destructive)'}\n")
    tts = get_tts_engine()
    base_stt = get_stt_service()
    confirm_stt = get_stt_service(settings.whisper_confirm_model)
    for target in targets:
        _process(target, disc, tts, base_stt, confirm_stt, lexicon, args.in_place)


if __name__ == "__main__":
    main()
