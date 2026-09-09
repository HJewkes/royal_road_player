"""Phoneme-level fidelity check: is a TTS mangle really bad audio, or just Whisper?

Whisper is a *word* recognizer biased toward known vocabulary, so a rare proper
noun can be transcribed wrong even when the audio is fine. This module sidesteps
that by comparing pronunciation directly at the phoneme level:

  expected phonemes  = espeak-ng G2P of the intended word (any word, incl. coined)
  actual phonemes    = a wav2vec2 *phoneme* model run on the audio (vocab-free)

A small phoneme distance means the audio matches the intended pronunciation, so a
Whisper mismatch there is Whisper's fault (suppress it). A large distance means
XTTS genuinely mispronounced the word — a real defect worth fixing. Both sides use
the espeak phoneme inventory, so they are directly comparable.
"""

import logging
import re
import subprocess
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# wav2vec2 model whose output phoneme set matches espeak-ng's G2P output.
PHONEME_MODEL = "facebook/wav2vec2-lv-60-espeak-cv-ft"
TARGET_SR = 16000

# Stress, length, tie-bar and separator marks stripped before comparing phones.
_IPA_NOISE = re.compile(r"[ˈˌːˑ‍͡\s'_]")

# Allophones the two sides disagree on for free: espeak writes the American flap
# as ɾ and the pre-syllabic /t/ as a glottal stop, where the recognizer hears a
# plain t; it also splits schwa into ə/ɐ. None of ɾ, ʔ contrast with t in English,
# so folding both sides costs no recall and removed 13 false faults from the ch2 scan.
_ALLOPHONE_FOLD = str.maketrans({"ɾ": "t", "ʔ": "t", "ɐ": "ə"})
# espeak writes a syllabic nasal or lateral (n̩ in "certain", l̩ in "bottle") where
# the recognizer always emits the schwa spelled out. Rewriting espeak's form to the
# recognizer's takes those words from 0.46 (a fault) to 0.09.
_SYLLABIC = re.compile("([nlm])̩")


def g2p_voice(voice: Optional[str] = None) -> str:
    """The espeak accent used to predict pronunciation, from settings unless given."""
    if voice is not None:
        return voice
    from src.config import get_settings
    return get_settings().phoneme_g2p_voice


def g2p(text: str, voice: Optional[str] = None) -> str:
    """Expected phoneme string for a word via espeak-ng."""
    try:
        out = subprocess.run(
            ["espeak-ng", "-q", "--ipa=3", "-v", g2p_voice(voice), text],
            capture_output=True, text=True, timeout=10, check=True,
        ).stdout
        return clean_ipa(out)
    except (subprocess.SubprocessError, FileNotFoundError) as e:
        logger.error(f"espeak-ng G2P failed for {text!r}: {e}")
        return ""


def clean_ipa(ipa: str) -> str:
    """Drop stress/length/tie marks and fold allophones, so only the phones the two
    sides could genuinely disagree about are compared."""
    folded = _SYLLABIC.sub(r"ə\1", _IPA_NOISE.sub("", ipa.strip()))
    return folded.translate(_ALLOPHONE_FOLD)


def phoneme_distance(expected: str, actual: str) -> float:
    """Normalized phone edit distance in [0,1]; 0 == identical pronunciation."""
    a, b = clean_ipa(expected), clean_ipa(actual)
    if not a and not b:
        return 0.0
    return 1.0 - SequenceMatcher(None, a, b).ratio()


def phone_match_distance(expected: str, actual_full: str) -> float:
    """Best distance of `expected` phones against any window of a full-chunk phone
    string. Locates a word acoustically without Whisper timestamps, so adjacent
    words can't contaminate the score. Returns 1.0 if the word isn't found at all.
    """
    exp, full = clean_ipa(expected), clean_ipa(actual_full)
    if not exp:
        return 0.0
    if not full:
        return 1.0
    m = len(exp)
    best = 1.0
    # SequenceMatcher already finds the best-matching block; scan a few window
    # sizes around the expected length to bound the local alignment tightly.
    for length in {max(1, m - 2), m, m + 2, m + 4}:
        for start in range(0, max(1, len(full) - length + 1)):
            window = full[start:start + length]
            best = min(best, 1.0 - SequenceMatcher(None, exp, window).ratio())
            if best == 0.0:
                return 0.0
    return best


class PhonemeRecognizer:
    """Vocabulary-free phoneme transcription of audio via wav2vec2 CTC."""

    def __init__(self, model_name: str = PHONEME_MODEL):
        self.model_name = model_name
        self._model = None
        self._processor = None
        from src.config import get_settings
        self.cache_dir = get_settings().cache_dir / "phonemes"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _load(self):
        if self._model is None:
            import torch  # noqa: F401
            from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor
            logger.info(f"Loading phoneme model: {self.model_name}")
            self._processor = Wav2Vec2Processor.from_pretrained(self.model_name)
            self._model = Wav2Vec2ForCTC.from_pretrained(self.model_name)
            self._model.eval()

    def recognize(self, samples_16k) -> str:
        """Transcribe a 16kHz mono float array to an espeak-style phoneme string."""
        return clean_ipa(self._recognize_raw(samples_16k))

    def _recognize_raw(self, samples_16k) -> str:
        """The model's own decode, before any cleaning or allophone folding."""
        import torch
        self._load()
        inputs = self._processor(
            samples_16k, sampling_rate=TARGET_SR, return_tensors="pt"
        )
        with torch.no_grad():
            logits = self._model(inputs.input_values).logits
        pred = torch.argmax(logits, dim=-1)
        return self._processor.batch_decode(pred)[0]

    def recognize_wav(self, wav_path: Path, use_cache: bool = True) -> str:
        """Whole-file phoneme transcription, cached by file content hash.

        The cache holds the raw decode and `clean_ipa` runs on read, so changing
        what the fold covers re-scores old entries instead of needing a wipe.
        """
        import hashlib
        import json
        digest = hashlib.sha256(Path(wav_path).read_bytes()).hexdigest()[:16]
        cache = self.cache_dir / f"{digest}.json"
        if use_cache and cache.exists():
            try:
                return clean_ipa(json.loads(cache.read_text())["phones"])
            except Exception:
                pass
        phones = self._recognize_raw(load_slice(Path(wav_path), None, None))
        if use_cache:
            try:
                cache.write_text(json.dumps({"phones": phones}))
            except Exception as e:
                logger.warning(f"Phoneme cache write failed: {e}")
        return clean_ipa(phones)


def load_slice(wav_path: Path, start: Optional[float], end: Optional[float],
               pad: float = 0.12):
    """Load a wav (optionally just the [start,end] window), mono @ 16kHz float."""
    import torchaudio
    wave, sr = torchaudio.load(str(wav_path))
    if wave.shape[0] > 1:
        wave = wave.mean(dim=0, keepdim=True)
    if start is not None and end is not None:
        lo = max(0, int((start - pad) * sr))
        hi = min(wave.shape[1], int((end + pad) * sr))
        wave = wave[:, lo:hi]
    if sr != TARGET_SR:
        import torchaudio.functional as AF
        wave = AF.resample(wave, sr, TARGET_SR)
    return wave.squeeze(0).numpy()


# Above this phone distance the audio genuinely mispronounces the word (XTTS's
# fault); below it the audio is correct and any text mismatch is Whisper's fault.
XTTS_FAULT_THRESHOLD = 0.45
# Proper nouns and coinages need a bigger gap, because on those the *expected*
# side is the unreliable one: espeak anglicizes "Bochum" to /bɒtʃəm/, so the
# German-correct renderings the audio actually produces score 0.455 (/bɒkʌm/) to
# 0.667 (/boʊxʊm/) against it — all past 0.45, all false faults. Genuine mangles
# sit far higher: 0.882 for a wholly different word, 1.0 for garble (see the
# fixtures in tests/test_phonemes.py). 0.70 clears the worst G2P disagreement
# and still leaves the real-mangle band untouched.
XTTS_FAULT_THRESHOLD_UNUSUAL = 0.70
# Phone edit distance is too coarse on very short words (a 1-2 phone word scores a
# binary 0/1), so we only trust an XTTS-fault verdict for words with enough phones.
MIN_PHONES_FOR_VERDICT = 3
# Distance is quantized by phone count: on a 3-4 phone word ONE recognizer slip
# already costs 0.33-0.5, which the ordinary threshold reads as a fault. Every hit
# in that band on DoF book 8 ch 2 was the recognizer clipping a coda — /bɔl/ read
# back as /boʊ/, /dɔɹ/ as /doʊ/ — so short words must break further to count.
SHORT_WORD_MAX_PHONES = 4
XTTS_FAULT_THRESHOLD_SHORT = 0.70
# A genuinely-pronounced word — however garbled — still produces roughly its
# expected phone count. A mapped span far shorter than that means `_index_map`'s
# alignment degenerated rather than that the audio is bad: confirmed on a real
# chunk where the source text repeated a near-duplicate prefix nearby ("Oka
# Okafor") and the global diff collapsed the second word's mapped span down to a
# single stray phone from the *next* word. Below this ratio, don't trust either
# verdict — report "inconclusive" instead of a confident (and here, wrong) "xtts".
MIN_SPAN_RATIO_FOR_VERDICT = 0.5


# espeak predicts one citation pronunciation per word, but English function words
# have well-attested weak forms in connected speech and the narrator uses them:
# "our" is read /ɑɹ/ on 27 of its 38 occurrences in DoF book 8 ch2 and never the
# citation /aʊɚ/, so every one scored 1.0 and was called an XTTS fault. These are
# the reductions we additionally accept as correct, written in espeak's own en-us
# inventory. The class is deliberately closed and function-word-only: a content
# word or name XTTS mispronounces must still flag, so nothing here has a variant
# that could mask one.
#
# Every entry is a weak form from the standard English list. Measured on ch2, the
# ones that actually beat the citation are could (26/28), our (27/40), her (17/26),
# but (57/142), for (55/113), and, can, had, has, have, him, his, should, some,
# that, their, them, were, would, your. XTTS renders does/from/there/was at full
# strength there, so those four never fire yet; they stay because they are standard
# and cost nothing. Add an entry only if it is a documented weak form — "than" was
# dropped because clean_ipa already yields ðən, and just/must/what/because were
# dropped as non-canonical and never observed.
_WEAK_FORMS: dict[str, tuple[str, ...]] = {
    "and": ("ənd", "ən"),
    "are": ("ɚ",),
    "but": ("bət",),
    "can": ("kən",),
    "could": ("kəd",),
    "does": ("dəz",),
    "for": ("fɚ",),
    "from": ("fɹəm",),
    "had": ("həd", "əd"),
    "has": ("həz", "əz"),
    "have": ("həv", "əv"),
    "her": ("ɚ",),
    "him": ("ɪm",),
    "his": ("ɪz",),
    "our": ("ɑɹ",),
    "should": ("ʃəd",),
    "some": ("səm",),
    "that": ("ðət",),
    "their": ("ðɚ",),
    "them": ("ðəm", "əm"),
    "there": ("ðɚ",),
    "was": ("wəz",),
    "were": ("wɚ",),
    "would": ("wəd",),
    "your": ("jɚ",),
}


def admissible_phones(word: str, citation: str) -> tuple[str, ...]:
    """Every pronunciation we accept as correct for `word`: espeak's citation form
    plus any documented weak form, so connected-speech reduction isn't a defect."""
    key = word.lower().strip(".,!?;:\"'()[]…—-")
    return (citation, *(clean_ipa(v) for v in _WEAK_FORMS.get(key, ())))


def g2p_sentence(text: str, voice: Optional[str] = None) -> list[str]:
    """Per-word phones for a whole sentence (context-correct), cleaned."""
    try:
        raw = subprocess.run(
            ["espeak-ng", "-q", "--ipa=3", "-v", g2p_voice(voice), text],
            capture_output=True, text=True, timeout=15, check=True,
        ).stdout
    except (subprocess.SubprocessError, FileNotFoundError) as e:
        logger.error(f"espeak-ng sentence G2P failed: {e}")
        return []
    return [clean_ipa(w) for w in raw.split() if clean_ipa(w)]


def _index_map(expected: str, actual: str) -> list[int]:
    """For each index in `expected`, the aligned index in `actual` (monotonic).

    A global phone alignment, so each word maps to its POSITIONALLY-correct actual
    span — a garbled word gets its garbled region, not a lucky match elsewhere.
    """
    mapping = [0] * len(expected)
    for tag, i1, i2, j1, j2 in SequenceMatcher(None, expected, actual).get_opcodes():
        for i in range(i1, i2):
            frac = (i - i1) / (i2 - i1) if i2 > i1 else 0.0
            mapping[i] = j1 + (int(frac * (j2 - j1)) if j2 > j1 else 0)
    return mapping


# A run of audio phones this long with no matching source text is a hallucinated
# outburst (babble XTTS emits at sentence/quote/paragraph boundaries), not STT noise.
HALLUCINATION_MIN_PHONES = 5

# XTTS also appends a phantom syllable AFTER the last word of a chunk, heard as a
# click or a "tsch": ch2 chunk 387 ends "...here ASAP." but reads back /ɛsæp/ + /ku/,
# and the same shape recurs as /taɪp/, /tdɔɡ/, /tɔtʃ/ on 33 of ch2's 760 chunks. The
# general hallucination rule misses all of them because it needs 5 phones and these
# run 2-4. A stray run at the very end earns a lower bar than a mid-utterance one:
# there is no following speech for the recognizer to have smeared into, so a run
# that survives to the end of the audio is real.
#
# One phone is enough. This started at 2 on the assumption that a single trailing
# phone was recognizer noise; listening to ch11's single-phone cases disproved that.
# All were audible, including /l/ after "football" and /ɹ/ after "here", where the
# stray repeats the last word's own final phone — the cases most likely to be a
# double-count were the clearest strays by ear. So there is deliberately no rule
# excluding a stray that echoes the preceding phone.
TAIL_STRAY_MIN_PHONES = 1


def detect_hallucinations(chunk_text: str, actual_full: str,
                          voice: Optional[str] = None,
                          min_run: int = HALLUCINATION_MIN_PHONES) -> list[dict]:
    """Find runs of audio phones that correspond to NO source text — the phantom
    babble XTTS injects (usually at boundaries). These are insertions the
    word-level mispronunciation detector deliberately ignores. Each result gives
    the stray phones, their length, and position (0..1 through the audio)."""
    expected = clean_ipa(g2p(chunk_text, voice))
    actual = clean_ipa(actual_full)
    if not actual:
        return []
    out = []
    for tag, i1, i2, j1, j2 in SequenceMatcher(None, expected, actual).get_opcodes():
        if tag == "insert":
            run, start = actual[j1:j2], j1
        elif tag == "replace" and (j2 - j1) - (i2 - i1) >= min_run:
            run, start = actual[j1:j2], j1  # audio far longer than text = net babble
        else:
            continue
        if len(run) >= min_run:
            out.append({
                "phones": run, "length": len(run),
                "position": round(start / len(actual), 2),
                "severity": round(min(1.0, 0.5 + 0.06 * (len(run) - min_run)), 3),
            })
    return out


def detect_tail_artifact(chunk_text: str, actual_full: str,
                         voice: Optional[str] = None,
                         min_phones: int = TAIL_STRAY_MIN_PHONES) -> Optional[dict]:
    """Phantom phones appended after a chunk's last expected phone, or None.

    Only the final alignment opcode is considered, so this fires on audio that runs
    past the text and not on a mispronounced last word: the stray run must be longer
    than whatever expected phones it displaced, which keeps "paths" read as /ɑðz/
    (a substitution the word detector already reports) out of the results.
    """
    expected = clean_ipa(g2p(chunk_text, voice))
    actual = clean_ipa(actual_full)
    if not expected or not actual:
        return None
    tag, i1, i2, j1, j2 = SequenceMatcher(None, expected, actual).get_opcodes()[-1]
    stray, displaced = actual[j1:j2], expected[i1:i2]
    if tag == "equal" or len(stray) < min_phones or len(stray) <= len(displaced):
        return None
    return {
        "phones": stray,
        "length": len(stray),
        "displaced": displaced,
        "severity": round(min(1.0, 0.4 + 0.1 * len(stray)), 3),
    }


def _locate(sub: str, full: str) -> tuple:
    """Best [lo,hi) window of `full` matching `sub` (both from the same G2P engine,
    so the match is near-exact and gives the word's position in the phone string)."""
    m = len(sub)
    if not m or not full:
        return (0, 0)
    best_start, best_d = 0, 1.0
    for start in range(0, max(1, len(full) - m + 1)):
        d = 1.0 - SequenceMatcher(None, sub, full[start:start + m]).ratio()
        if d < best_d:
            best_start, best_d = start, d
            if d == 0.0:
                break
    return (best_start, best_start + m)


def _fault_threshold(word: str, expected_phones: str, unusual) -> float:
    """Distance at which we blame the audio rather than the G2P, for one word."""
    if unusual and word in unusual:
        return XTTS_FAULT_THRESHOLD_UNUSUAL
    if len(expected_phones) <= SHORT_WORD_MAX_PHONES:
        return XTTS_FAULT_THRESHOLD_SHORT
    return XTTS_FAULT_THRESHOLD


def chunk_word_verdicts(chunk_text: str, actual_full: str, targets=None,
                        voice: Optional[str] = None, unusual=None) -> list[dict]:
    """Positional phoneme verdict for specific words in a chunk.

    Locates each target word's expected phones inside the chunk's full expected
    phone string, then reads the POSITIONALLY-aligned actual (audio) span — so a
    garbled word scores high even if its phones appear elsewhere. `targets` is an
    iterable of the actual words to score; `unusual` is the subset of them judged
    against XTTS_FAULT_THRESHOLD_UNUSUAL.
    """
    actual = clean_ipa(actual_full)
    expected_full = clean_ipa(g2p(chunk_text, voice))
    if not expected_full or not actual or targets is None:
        return []
    mapping = _index_map(expected_full, actual)

    out = []
    for word in targets:
        exp_w = clean_ipa(g2p(word, voice))
        lo, hi = _locate(exp_w, expected_full)
        if hi <= lo:
            continue
        a_lo = mapping[lo]
        a_hi = (mapping[hi - 1] + 1) if hi - 1 < len(mapping) else len(actual)
        out.append(_word_verdict(word, exp_w, actual[a_lo:a_hi], unusual))
    return out


def _word_verdict(word: str, exp_w: str, actual_span: str, unusual) -> dict:
    """Verdict for one located word, scored against its best admissible form.

    A word matching any pronunciation we accept is correct, so the distance is the
    minimum over the citation form and the word's weak forms.
    """
    dist, best = min(
        (1.0 - SequenceMatcher(None, form, actual_span).ratio(), form)
        for form in admissible_phones(word, exp_w)
    )
    # The span guard stays keyed on espeak's predicted length: it detects a
    # degenerate alignment, not a short pronunciation, and a weak form's smaller
    # phone count would quietly weaken it.
    if len(actual_span) < MIN_SPAN_RATIO_FOR_VERDICT * len(exp_w):
        source = "inconclusive"
    elif (dist >= _fault_threshold(word, exp_w, unusual)
          and len(exp_w) >= MIN_PHONES_FOR_VERDICT):
        source = "xtts"
    else:
        source = "whisper"
    return {"word": word, "expected_phones": best, "actual_phones": actual_span,
            "distance": round(dist, 3), "source": source}


_recognizer: Optional[PhonemeRecognizer] = None


def get_phoneme_recognizer() -> PhonemeRecognizer:
    global _recognizer
    if _recognizer is None:
        _recognizer = PhonemeRecognizer()
    return _recognizer
