#!/usr/bin/env python3
"""Prototype: phoneme-grounded respelling generator + isolation filter.

Standalone prototype for a research question: can we do better than the
ad-hoc grapheme-rewrite rules in `src/text/lexicon.py` (generate_candidates)
by generating respelling candidates FROM the word's target IPA instead of
guessing at English spelling irregularities?

Two independent pieces:

1. Phoneme-grounded candidate generation (`generate_phoneme_respellings`):
   espeak-ng G2P gives the target IPA for a word. We segment that IPA into
   phones and back-map each phone to the plain-English grapheme(s) XTTS is
   known to render reliably (see IPA_TO_GRAPHEME below). The primary mapping
   gives one candidate; single-phone substitutions using each phone's
   alternate grapheme(s) give a small, EXPLAINABLE candidate set — every
   candidate is traceable to "phone X was spelled as Y instead of Z", unlike
   the old rule-mutation approach which just chews on the orthography with no
   reference to the actual target pronunciation.

2. Isolation filter (`isolation_verdict`): many "mispronunciations" caught in
   a full chapter are CONTEXT-DEPENDENT (prosody/coarticulation from
   neighboring words), not word-intrinsic — a lexicon respelling cannot help
   those, and could regress a word that's actually fine alone. The filter
   synthesizes the bare word in a neutral carrier sentence and phoneme-scores
   it against espeak G2P; only an intrinsic (isolation-verdict "xtts") word is
   a legitimate lexicon-respelling candidate.

Run in the TTS venv (loads XTTS + the phoneme model — slow first call):
  ./venv311/bin/python scripts/prototype_phoneme_respell.py
"""
import sys
import tempfile
from pathlib import Path
from typing import Optional

SCRIPTS = Path(__file__).resolve().parent
BACKEND = SCRIPTS.parent / "backend"
sys.path.insert(0, str(BACKEND))

from src.discovery import ChunkDiscovery  # noqa: E402
from src.text.lexicon import generate_candidates as old_generate_candidates  # noqa: E402
from src.tts import get_tts_engine  # noqa: E402
from src.validation.phonemes import (  # noqa: E402
    XTTS_FAULT_THRESHOLD, chunk_word_verdicts, g2p, get_phoneme_recognizer, load_slice,
)

# ---------------------------------------------------------------------------
# 1. IPA -> grapheme back-mapping
# ---------------------------------------------------------------------------
# Keyed by the post-clean_ipa espeak-ng symbol (stress/length marks already
# stripped by g2p()). Each value is (primary_grapheme, [alternate_graphemes]).
# Primary = the spelling most likely to make XTTS produce that phone from
# plain English graphemes; alternates are the next-most-plausible spellings,
# used to generate single-substitution variants when the primary is wrong.
IPA_TO_GRAPHEME: dict[str, tuple[str, list[str]]] = {
    # --- monophthongs ---
    "i": ("ee", ["i"]),          # see
    "ɪ": ("i", ["ih"]),          # sit
    "ɛ": ("eh", ["e"]),          # set
    "e": ("eh", ["ay"]),         # (rare standalone; mostly in eɪ)
    "æ": ("a", ["ae"]),          # cat
    "a": ("ah", ["a"]),          # foreign/short open front (Ghanaian, sky's onset)
    "ɑ": ("ah", ["aa"]),         # father
    "ɒ": ("o", ["ah"]),          # hot
    "ɔ": ("aw", ["or"]),         # saw
    "ʊ": ("oo", ["u"]),          # put
    "u": ("oo", ["u"]),          # food
    "ʌ": ("uh", ["u"]),          # cup
    "ɜ": ("ur", ["er"]),         # bird
    "ə": ("uh", ["a", "e"]),     # schwa (about, -er)
    "ɐ": ("uh", ["a"]),          # near-open reduced vowel (about's 1st syllable)
    # --- diphthongs ---
    "eɪ": ("ay", ["ai"]),        # say
    "aɪ": ("y", ["eye", "igh"]),  # sky
    "ɔɪ": ("oy", ["oi"]),        # boy
    "əʊ": ("oh", ["o"]),         # go
    "aʊ": ("ow", ["ou"]),        # cow
    "ɪə": ("eer", ["ear"]),      # beer
    "eə": ("air", ["are"]),      # bear
    "ʊə": ("oor", ["ure"]),      # tour
    # --- consonants ---
    "p": ("p", []), "b": ("b", []), "t": ("t", []), "d": ("d", []),
    "k": ("k", ["c"]), "ɡ": ("g", []),
    "f": ("f", ["ph"]), "v": ("v", []),
    "s": ("s", ["c"]), "z": ("z", []),
    "h": ("h", []), "m": ("m", []), "n": ("n", []), "ŋ": ("ng", []),
    "l": ("l", []), "ɹ": ("r", []), "j": ("y", []), "w": ("w", []),
    "ʃ": ("sh", []), "ʒ": ("zh", ["si"]),
    "θ": ("th", []), "ð": ("th", []),       # NB: same grapheme both ways (see caveats)
    "tʃ": ("ch", ["tch"]), "dʒ": ("j", ["dge", "g"]),
    "x": ("ch", ["k"]),                     # loch-type velar fricative (foreign names)
}
# Longest phones first so segmentation greedily prefers e.g. "tʃ" over "t"+"ʃ".
_MULTI_PHONES = sorted((k for k in IPA_TO_GRAPHEME if len(k) > 1), key=len, reverse=True)


def segment_ipa(ipa: str) -> list[str]:
    """Greedy longest-match tokenization of a clean_ipa string into phones."""
    phones, i = [], 0
    while i < len(ipa):
        for m in _MULTI_PHONES:
            if ipa.startswith(m, i):
                phones.append(m)
                i += len(m)
                break
        else:
            phones.append(ipa[i])
            i += 1
    return phones


def _grapheme(phone: str) -> str:
    """Primary grapheme for a phone; unmapped phones fall back to themselves
    (visible in output as a non-ASCII residue, flagging a table gap)."""
    return IPA_TO_GRAPHEME.get(phone, (phone, []))[0]


def _match_case(variant: str, original: str) -> str:
    if original[:1].isupper() and variant:
        return variant[0].upper() + variant[1:]
    return variant


def generate_phoneme_respellings(word: str, voice: str = "en-gb", limit: int = 8) -> list[str]:
    """Phoneme-grounded respelling candidates for `word`.

    1. G2P the word to get its target IPA.
    2. Segment into phones, map each to its primary grapheme -> one baseline
       candidate.
    3. For each phone with an alternate grapheme, substitute just that one
       phone's spelling -> a small set of single-point-of-difference variants.
    4. Word-final schwa+n ("-ən") is an extremely common English orthographic
       ending spelled "-an"/"-en"/"-on" (African, garden, wagon) rather than
       "-uhn" — a generalizable ending-specific rule, not word-specific.

    Every candidate is directly traceable to which phone was respelled which
    way, unlike ad-hoc orthography mutation.
    """
    ipa = g2p(word, voice)
    if not ipa:
        return []
    phones = segment_ipa(ipa)
    graphemes = [_grapheme(p) for p in phones]

    out, seen = [], {word.lower()}

    def add(spelled_parts: list[str]):
        spelled = _match_case("".join(spelled_parts), word)
        if spelled.lower() not in seen:
            seen.add(spelled.lower())
            out.append(spelled)

    add(graphemes)  # primary/baseline candidate

    for i, phone in enumerate(phones):
        for alt in IPA_TO_GRAPHEME.get(phone, ("", []))[1]:
            variant = list(graphemes)
            variant[i] = alt
            add(variant)
            if len(out) >= limit:
                return out[:limit]

    if len(phones) >= 2 and phones[-2:] == ["ə", "n"]:
        for suffix in ("an", "en", "on"):
            variant = graphemes[:-2] + [suffix]
            add(variant)
            if len(out) >= limit:
                break

    return out[:limit]


# ---------------------------------------------------------------------------
# 2. Isolation filter
# ---------------------------------------------------------------------------
DEFAULT_CARRIER = "I travelled to {} last year."


def isolation_verdict(word: str, tts, recognizer, carrier: str = DEFAULT_CARRIER,
                       voice: str = "en-gb") -> dict:
    """Synthesize `word` alone in a neutral carrier and phoneme-score it.

    Returns the chunk_word_verdicts() dict for the word (distance, source =
    'xtts' if it mispronounces even in isolation, else 'whisper'/clean) plus
    the wav path used, so a caller can classify:
      - isolation source == 'xtts'  -> INTRINSIC: a real lexicon-respelling
        candidate (the word itself is broken, context can't be blamed).
      - isolation source != 'xtts'  -> the word is fine alone; if it *was*
        flagged as a mangle in its original chunk context, that mangle is
        CONTEXTUAL and a lexicon fix cannot help (and could regress this
        clean case elsewhere).
    """
    text = carrier.format(word)
    wav = Path(tempfile.mkstemp(suffix=".wav")[1])
    tts.synthesize(text, wav)
    actual_full = recognizer.recognize(load_slice(wav, None, None))
    verdicts = chunk_word_verdicts(text, actual_full, targets=[word.lower()], voice=voice)
    v = verdicts[0] if verdicts else {
        "word": word.lower(), "expected_phones": g2p(word, voice),
        "actual_phones": actual_full, "distance": 1.0, "source": "xtts",
    }
    v["wav"] = str(wav)
    return v


def context_verdict(word: str, fiction_id: str, book: int, chapter: int, chunk_idx: int,
                     recognizer, voice: str = "en-gb") -> Optional[dict]:
    """Phoneme verdict for `word` inside an ALREADY-GENERATED chunk (no new
    XTTS synthesis — reuses the wav already on disk from the real pipeline
    run) so we can show the in-context mangle for free."""
    chunk = ChunkDiscovery().get_chunk(fiction_id, book, chapter, chunk_idx)
    if chunk is None or not chunk.audio_path:
        return None
    actual_full = recognizer.recognize(load_slice(chunk.audio_path, None, None))
    verdicts = chunk_word_verdicts(chunk.text, actual_full, targets=[word.lower()], voice=voice)
    return verdicts[0] if verdicts else None


# ---------------------------------------------------------------------------
# 3. Candidate sweep (scores each spelling against the ORIGINAL word's target
#    phones, so "does this respelling make XTTS say the right thing" — not
#    whether it round-trips through G2P itself).
# ---------------------------------------------------------------------------
def sweep_candidates(word: str, candidates: list[str], tts, recognizer,
                      carrier: str = DEFAULT_CARRIER, voice: str = "en-gb") -> list[dict]:
    """Synthesize each candidate spelling in the carrier, phoneme-score the
    audio against the ORIGINAL word's expected phones (positionally located
    via the original word's text, since the carrier is fixed and only the
    target slot's spelling changes)."""
    results = []
    for spelling in candidates:
        wav = Path(tempfile.mkstemp(suffix=".wav")[1])
        tts.synthesize(carrier.format(spelling), wav)
        actual_full = recognizer.recognize(load_slice(wav, None, None))
        verdicts = chunk_word_verdicts(carrier.format(word), actual_full,
                                        targets=[word.lower()], voice=voice)
        v = verdicts[0] if verdicts else {
            "word": word.lower(), "expected_phones": g2p(word, voice),
            "actual_phones": actual_full, "distance": 1.0, "source": "xtts",
        }
        v["spelling"] = spelling
        results.append(v)
    return results


# ---------------------------------------------------------------------------
# Demonstration
# ---------------------------------------------------------------------------
def main():
    tts = get_tts_engine()
    recognizer = get_phoneme_recognizer()

    print("=" * 78)
    print("STEP 0: old vs new candidate generation for 'Ghanaian' (no synthesis)")
    print("=" * 78)
    old = old_generate_candidates("Ghanaian")
    new = generate_phoneme_respellings("Ghanaian")
    print(f"  espeak target IPA: {g2p('Ghanaian')!r} (Gha-NAY-an)")
    print(f"  old generate_candidates(): {old!r}")
    print(f"  new generate_phoneme_respellings(): {new!r}")

    print()
    print("=" * 78)
    print("STEP 1: context-mangle evidence, reused from ALREADY-GENERATED audio")
    print("(zero new XTTS synthesis)")
    print("=" * 78)
    for word, fid, book, ch, idx in [("Ghanaian", "124774", 7, 8, 411),
                                      ("match", "124774", 7, 8, 56)]:
        v = context_verdict(word, fid, book, ch, idx, recognizer)
        if v is None:
            print(f"  {word}: chunk audio not found, skipping")
            continue
        print(f"  {word:<10} in-context dist={v['distance']:.3f} source={v['source']} "
              f"expected={v['expected_phones']!r} actual={v['actual_phones']!r}")

    print()
    print("=" * 78)
    print("STEP 2: isolation filter (1 new XTTS synthesis per word)")
    print("=" * 78)
    isolation_results = {}
    for word in ["Ghanaian", "match"]:
        v = isolation_verdict(word, tts, recognizer)
        isolation_results[word] = v
        cls = "INTRINSIC (fixable)" if v["source"] == "xtts" else "clean-in-isolation"
        print(f"  {word:<10} isolation dist={v['distance']:.3f} -> {cls}  "
              f"expected={v['expected_phones']!r} actual={v['actual_phones']!r}")

    print()
    print("=" * 78)
    print("STEP 3: candidate sweep for 'Ghanaian' (phoneme-grounded candidates,"
          " 1 synthesis each)")
    print("=" * 78)
    baseline = isolation_results["Ghanaian"]
    print(f"  baseline (orthographic 'Ghanaian'): dist={baseline['distance']:.3f}")
    sweep_set = new[:4]  # keep total synthesis count small per the budget
    results = sweep_candidates("Ghanaian", sweep_set, tts, recognizer)
    for r in sorted(results, key=lambda r: r["distance"]):
        print(f"  {r['spelling']:<14} dist={r['distance']:.3f} source={r['source']:<8} "
              f"actual={r['actual_phones']!r}")

    best = min(results, key=lambda r: r["distance"])
    print()
    if best["distance"] < baseline["distance"]:
        print(f"WINNER: {best['spelling']!r} beats orthographic baseline "
              f"({best['distance']:.3f} < {baseline['distance']:.3f})")
    else:
        print(f"No candidate beat the orthographic baseline "
              f"({best['distance']:.3f} >= {baseline['distance']:.3f})")


if __name__ == "__main__":
    main()
