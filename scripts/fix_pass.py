#!/usr/bin/env python3
"""Fix pass: regenerate problematic chunks (best-of-N with param perturbation) and
keep only the takes that measurably improve the flagged word's pronunciation.

For each bad chunk (an XTTS-fault from the phoneme-triaged test set) it re-synthesizes
the WHOLE chunk several times under different XTTS decoder settings, scores each take's
flagged-word phoneme distance, and picks the best. A regenerated chunk is kept only if
it beats the shipped audio by a margin; ties/worse are discarded (never ship a worse
concatenation-swap). Emits logs/fix_results.json with full-chunk before/after mp3 for
the demo and the overall improvement rate.

Every take re-renders with the engine the chapter's stamp names, so a repair never
mixes engines; a chapter whose engine cannot run on this host is refused.

  ./venv311/bin/python scripts/fix_pass.py [--limit N] [--takes K]
  ./venv311/bin/python scripts/fix_pass.py --early-stops --apply --book 8 --chapter 2
"""
import argparse
import base64
import io
import json
import os
import sys
import tempfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

from src.discovery import ChunkDiscovery  # noqa: E402
from src.tts import get_tts_engine  # noqa: E402
from src.tts.chatterbox import ChatterboxUnavailable  # noqa: E402
from src.tts.early_stop import take_shortfall  # noqa: E402
from src.tts.engines import chunk_seed, get_chapter_engine, render_profile  # noqa: E402
from src.tts.verified import SEED_STRIDE  # noqa: E402
from src.validation.defects import tokenize  # noqa: E402
from src.validation.phonemes import (  # noqa: E402
    XTTS_FAULT_THRESHOLD, chunk_word_verdicts, get_phoneme_recognizer, load_slice,
)

DATASET = BACKEND.parent / "data" / "test_set" / "tts_defects.jsonl"
OUT = BACKEND.parent / "logs" / "fix_results.json"
MARGIN = 0.06  # after must beat before by this to count as an improvement

# Perturbed re-rolls per engine. XTTS: one reseed at defaults, then decoder
# variations that the param study found rescue stochastic mangles; it is unseeded,
# so "reseed" relies on its randomness. Chatterbox is seeded, so a take only differs
# if its seed does: "seed" here is a retake number, resolved by _take_params.
PARAM_TAKES = {
    "xtts": [
        ("reseed", {}),
        ("temp0.85", {"temperature": 0.85}),
        ("rep2.0", {"repetition_penalty": 2.0}),
    ],
    "chatterbox": [
        ("seed+1", {"seed": 1}),
        ("seed+2", {"seed": 2}),
        ("temp0.7", {"seed": 3, "temperature": 0.7}),
    ],
}

# The render-time verify loop already tried retakes 0..retries of every chunk seed,
# and a seeded take is reproducible, so repair retakes start well past them.
REPAIR_RETAKE_BASE = 1000


def _take_params(engine, chunk_index, n):
    """The first `n` (label, synthesize kwargs) takes for `engine`, seeds made absolute."""
    out = []
    for label, params in PARAM_TAKES[engine][:n]:
        params = dict(params)
        if "seed" in params:
            retake = REPAIR_RETAKE_BASE + params["seed"]
            params["seed"] = chunk_seed(chunk_index) + retake * SEED_STRIDE
        out.append((label, params))
    return out


def _load_engine(disc, fiction_id, book, chapter):
    """(name, engine) for the chapter's stamp; exits if this host cannot run it."""
    try:
        return get_chapter_engine(disc, fiction_id, book, chapter, factory=get_tts_engine)
    except ChatterboxUnavailable as exc:
        sys.exit(f"Refusing to repair: {exc}")

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


def _select_tails(disc, recog, target, limit):
    """Chunks whose audio runs past the last word, from a live scan.

    The word-defect path reads a curated dataset; tail artifacts have no such
    dataset and no flagged word, so they are found by scanning the chapter.
    """
    from src.validation.phonemes import detect_tail_artifact
    fid, book, ch = target
    out = []
    for chunk in disc.list_chunks(fid, book, ch):
        if not chunk.has_audio:
            continue
        art = detect_tail_artifact(chunk.text, recog.recognize_wav(chunk.audio_path))
        if art:
            out.append((chunk, art))
    out.sort(key=lambda t: -t[1]["severity"])
    return out[:limit]


# How much further an ALREADY-faulty word must degrade to count as a regression.
# Only applied to words the take leaves over the fault threshold: a whole-chunk
# re-synthesis re-renders every word, so sub-threshold distances jitter freely and
# scoring that jitter rejects good takes. Measured — guarding every word at 0.06 cut
# the ch2 keep rate from 5/6 to 2/5, rejecting on words like "across" and "years"
# that were fine in both renderings.
WORSE_MARGIN = MARGIN


def _word_distances(text, wav, recog):
    """Per-word phone distance for this audio, keyed by word.

    Distances, not a set of over-threshold words: a word that was ALREADY faulty and
    then degrades further never enters or leaves such a set, so set membership cannot
    see it get worse. Measured on ch2, 1 of 35 tail-flagged chunks carries a
    pre-existing word fault, so that blind spot is narrow but real.
    """
    from src.validation.defects import is_unusual_word
    targets = [t.original for t in tokenize(text)
               if not t.norm.startswith("#") and len(t.norm) >= 3]
    if not targets:
        return {}
    phones = recog.recognize_wav(wav, use_cache=False)
    verdicts = chunk_word_verdicts(text, phones, targets=targets,
                                   unusual={w for w in targets if is_unusual_word(w)})
    return {v["word"]: (v["distance"], v["source"] == "xtts") for v in verdicts}


def _regressions(shipped, take):
    """Words this take actively damages.

    A word counts only if the take leaves it genuinely mispronounced AND it is worse
    than it shipped — either it was fine before, or it was already faulty and has
    degraded past WORSE_MARGIN. That is the union of the two failure modes: a good
    word breaking, and a bad word getting worse without ever leaving the fault set.
    """
    out = []
    for word, (dist, faulty) in take.items():
        if not faulty:
            continue
        was_dist, was_faulty = shipped.get(word, (0.0, False))
        if not was_faulty or dist > was_dist + WORSE_MARGIN:
            out.append(word)
    return sorted(out)


def _tail_take(chunk, wav, recog, shipped_dist):
    """Score one regenerated take: (words made worse, stray length)."""
    from src.validation.phonemes import detect_tail_artifact
    art = detect_tail_artifact(chunk.text, recog.recognize_wav(wav, use_cache=False))
    broke = _regressions(shipped_dist, _word_distances(chunk.text, wav, recog))
    return (len(broke), art["length"] if art else 0), art, broke


def _best_tail_take(chunk, before, args, tts, recog):
    """Regenerate one chunk and return the best take, plus whether to keep it.

    Asymmetric on purpose: a take that clears the stray but pronounces any word worse
    than the shipped audio is worse overall, so it is disqualified outright regardless
    of how good its tail is.
    """
    shipped_dist = _word_distances(chunk.text, chunk.audio_path, recog)
    takes = []
    for label, params in _take_params(args.engine, chunk.index, args.takes):
        wav = _new_take_path()
        tts.synthesize(chunk.text, wav, **params)
        key, art, broke = _tail_take(chunk, wav, recog, shipped_dist)
        takes.append((key, label, wav, art, broke))
    takes.sort(key=lambda t: t[0])
    (nbroke, nstray), label, wav, art, broke = takes[0]
    return {
        "chunk": chunk.index, "before_phones": before["phones"],
        "before_len": before["length"], "after_phones": art["phones"] if art else "",
        "after_len": nstray, "take": label, "broke_words": broke,
        "kept": nbroke == 0 and nstray < before["length"],
        "context": chunk.text[-60:].strip(), "wav": str(wav),
    }


def _select_early_stops(disc, target, profile, limit):
    """Chunks whose take is too short for their text, worst shortfall first."""
    out = []
    for chunk in disc.list_chunks(*target):
        if not chunk.has_audio:
            continue
        shortfall = take_shortfall(chunk.text, chunk.audio_path, profile)
        if shortfall is not None:
            out.append((chunk, shortfall))
    out.sort(key=lambda t: -t[1])
    return out[:limit]


def _best_early_stop_take(chunk, before, args, tts, recog, profile):
    """Regenerate one truncated chunk; keep the best take only if it is longer for
    its text and breaks no word, the same regression rule as the tail pass."""
    shipped_dist = _word_distances(chunk.text, chunk.audio_path, recog)
    takes = []
    for label, params in _take_params(args.engine, chunk.index, args.takes):
        wav = _new_take_path()
        tts.synthesize(chunk.text, wav, **params)
        shortfall = take_shortfall(chunk.text, wav, profile) or 0.0
        broke = _regressions(shipped_dist, _word_distances(chunk.text, wav, recog))
        takes.append(((len(broke), shortfall), label, wav, broke))
    takes.sort(key=lambda t: t[0])
    (nbroke, after), label, wav, broke = takes[0]
    return {
        "chunk": chunk.index, "before_shortfall": round(before, 3),
        "after_shortfall": round(after, 3), "take": label, "broke_words": broke,
        "kept": nbroke == 0 and after < before,
        "context": chunk.text[-60:].strip(), "wav": str(wav),
    }


def _new_take_path():
    fd, name = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    return Path(name)


def _apply_take(chunk, result):
    """Swap a winning take over the shipped chunk wav, atomically.

    Reuses export's own `_promote` rather than reimplementing it, so the temp file,
    both fsyncs (file and parent directory) and the rename stay identical to how
    audio.wav is published. Concatenation is keyed on chunk size and mtime, which
    os.replace updates, so the next export rebuilds without further bookkeeping.
    """
    import shutil
    from src.export.concatenator import _promote
    src, dst = Path(result["wav"]), Path(chunk.audio_path)
    tmp = dst.with_name(dst.name + ".tmp")
    try:
        shutil.copyfile(src, tmp)
        _promote(tmp, dst)
    except Exception:
        tmp.unlink(missing_ok=True)  # never leave a half-written .tmp behind
        raise


def _write_results(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))


def _run_tails(args, disc, tts, recog):
    """Regenerate tail-artifact chunks and keep only takes that are strictly better."""
    target = (args.fiction_id, args.book, args.chapter)
    selected = _select_tails(disc, recog, target, args.limit)
    print(f"Tail fix pass over {len(selected)} flagged chunks, {args.takes} takes each\n")

    results = []
    for chunk, before in selected:
        r = _best_tail_take(chunk, before, args, tts, recog)
        results.append(r)
        verdict = (("CLEAN" if r["after_len"] == 0 else f"shorter /{r['after_phones']}/")
                   if r["kept"] else
                   (f"rejected (broke {r['broke_words']})" if r["broke_words"] else "no gain"))
        if r["kept"] and args.apply:
            _apply_take(chunk, r)
            verdict += " [APPLIED]"
        print(f"  chunk {r['chunk']:3d} /{r['before_phones']}/ -> [{r['take']}] {verdict}")

    n, kept = len(results), sum(1 for r in results if r["kept"])
    cleared = sum(1 for r in results if r["kept"] and r["after_len"] == 0)
    print(f"\nCleared outright: {cleared}/{n}. Improved and kept: {kept}/{n}.")
    out = OUT.with_name("tail_fix_results.json")
    _write_results(out, {"attempted": n, "cleared": cleared, "kept": kept,
                         "results": results})
    print(f"Wrote {out}")


def _run_early_stops(args, disc, tts, recog):
    """Regenerate truncated chunks with new seeds and keep only takes that are longer."""
    target = (args.fiction_id, args.book, args.chapter)
    profile = render_profile(args.engine, args.profile)
    if profile is None:
        sys.exit(f"{args.engine} has no early-stop guard; nothing to repair")
    selected = _select_early_stops(disc, target, profile, args.limit)
    print(f"Early-stop fix pass over {len(selected)} truncated chunks, {args.takes} takes each\n")

    results = []
    for chunk, before in selected:
        r = _best_early_stop_take(chunk, before, args, tts, recog, profile)
        results.append(r)
        verdict = (("FULL" if r["after_shortfall"] == 0 else f"shortfall {r['after_shortfall']:.2f}")
                   if r["kept"] else
                   (f"rejected (broke {r['broke_words']})" if r["broke_words"] else "no gain"))
        if r["kept"] and args.apply:
            _apply_take(chunk, r)
            verdict += " [APPLIED]"
        print(f"  chunk {r['chunk']:3d} shortfall {r['before_shortfall']:.2f} -> [{r['take']}] {verdict}")

    n, kept = len(results), sum(1 for r in results if r["kept"])
    full = sum(1 for r in results if r["kept"] and r["after_shortfall"] == 0)
    print(f"\nRendered in full: {full}/{n}. Improved and kept: {kept}/{n}.")
    out = OUT.with_name("early_stop_fix_results.json")
    _write_results(out, {"attempted": n, "full": full, "kept": kept, "results": results})
    print(f"Wrote {out}")


def _run_words(args, disc, recog):
    """The original path: rescue a flagged WORD in a curated bad chunk."""
    selected = _select(args.limit)
    print(f"Fix pass over {len(selected)} bad chunks, {args.takes} takes each\n")

    results, attempted, improved = [], 0, 0
    for (book, ch, idx), meta in selected:
        chunk = disc.get_chunk("124774", book, ch, idx)
        if not chunk or not chunk.has_audio:
            continue
        engine, tts = _load_engine(disc, "124774", book, ch)
        words = sorted(meta["words"])
        before, bworst = _score(chunk.text, chunk.audio_path, words, recog)
        if before < XTTS_FAULT_THRESHOLD:
            print(f"  b{book}/ch{ch}/{idx:03d} {words}: shipped already ok ({before:.2f}) — skip")
            continue
        attempted += 1
        takes = []
        for label, params in _take_params(engine, idx, args.takes):
            wav = _new_take_path()
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
    _write_results(OUT, {"improvement_rate_pct": round(rate, 1),
                         "attempted": attempted, "improved": improved,
                         "results": results})
    print(f"\nImprovement rate: {improved}/{attempted} = {rate:.0f}%")
    print(f"Wrote {OUT} ({OUT.stat().st_size // 1024} KB)")




def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=9, help="chunks to attempt")
    ap.add_argument("--takes", type=int, default=3, help="regeneration takes")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--tails", action="store_true",
                      help="fix tail artifacts in a chapter instead of dataset word defects")
    mode.add_argument("--early-stops", action="store_true",
                      help="re-render chunks too short for their text (engines with a guard)")
    ap.add_argument("--apply", action="store_true",
                    help="with --tails or --early-stops, overwrite the chunk wav for kept "
                         "takes (default is report-only; re-export rebuilds audio.wav)")
    ap.add_argument("--fiction-id", default="124774")
    ap.add_argument("--book", type=int, default=8)
    ap.add_argument("--chapter", type=int, default=2)
    args = ap.parse_args()

    disc, recog = ChunkDiscovery(), get_phoneme_recognizer()
    if not (args.tails or args.early_stops):
        return _run_words(args, disc, recog)
    args.engine, tts = _load_engine(disc, args.fiction_id, args.book, args.chapter)
    args.profile = disc.read_engine_stamp(args.fiction_id, args.book, args.chapter).get("profile")
    run = _run_tails if args.tails else _run_early_stops
    return run(args, disc, tts, recog)


if __name__ == "__main__":
    main()
