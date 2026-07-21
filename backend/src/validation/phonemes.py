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


def g2p(text: str, voice: str = "en-gb") -> str:
    """Expected phoneme string for a word via espeak-ng (British English default)."""
    try:
        out = subprocess.run(
            ["espeak-ng", "-q", "--ipa=3", "-v", voice, text],
            capture_output=True, text=True, timeout=10, check=True,
        ).stdout
        return clean_ipa(out)
    except (subprocess.SubprocessError, FileNotFoundError) as e:
        logger.error(f"espeak-ng G2P failed for {text!r}: {e}")
        return ""


def clean_ipa(ipa: str) -> str:
    """Drop stress/length/tie marks so only the phones themselves are compared."""
    return _IPA_NOISE.sub("", ipa.strip())


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
        import torch
        self._load()
        inputs = self._processor(
            samples_16k, sampling_rate=TARGET_SR, return_tensors="pt"
        )
        with torch.no_grad():
            logits = self._model(inputs.input_values).logits
        pred = torch.argmax(logits, dim=-1)
        return clean_ipa(self._processor.batch_decode(pred)[0])

    def recognize_wav(self, wav_path: Path, use_cache: bool = True) -> str:
        """Whole-file phoneme transcription, cached by file content hash."""
        import hashlib
        import json
        digest = hashlib.sha256(Path(wav_path).read_bytes()).hexdigest()[:16]
        cache = self.cache_dir / f"{digest}.json"
        if use_cache and cache.exists():
            try:
                return json.loads(cache.read_text())["phones"]
            except Exception:
                pass
        phones = self.recognize(load_slice(Path(wav_path), None, None))
        if use_cache:
            try:
                cache.write_text(json.dumps({"phones": phones}))
            except Exception as e:
                logger.warning(f"Phoneme cache write failed: {e}")
        return phones


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
# Phone edit distance is too coarse on very short words (a 1-2 phone word scores a
# binary 0/1), so we only trust an XTTS-fault verdict for words with enough phones.
MIN_PHONES_FOR_VERDICT = 3


def g2p_sentence(text: str, voice: str = "en-gb") -> list[str]:
    """Per-word phones for a whole sentence (context-correct), cleaned."""
    try:
        raw = subprocess.run(
            ["espeak-ng", "-q", "--ipa=3", "-v", voice, text],
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


def detect_hallucinations(chunk_text: str, actual_full: str, voice: str = "en-gb",
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


def chunk_word_verdicts(chunk_text: str, actual_full: str,
                        targets=None, voice: str = "en-gb") -> list[dict]:
    """Positional phoneme verdict for specific words in a chunk.

    Locates each target word's expected phones inside the chunk's full expected
    phone string, then reads the POSITIONALLY-aligned actual (audio) span — so a
    garbled word scores high even if its phones appear elsewhere. `targets` is an
    iterable of the actual words to score.
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
        actual_span = actual[a_lo:a_hi]
        dist = 1.0 - SequenceMatcher(None, exp_w, actual_span).ratio()
        # Only a long-enough word with a high distance is a trustworthy XTTS fault.
        is_xtts = dist >= XTTS_FAULT_THRESHOLD and len(exp_w) >= MIN_PHONES_FOR_VERDICT
        out.append({
            "word": word,
            "expected_phones": exp_w,
            "actual_phones": actual_span,
            "distance": round(dist, 3),
            "source": "xtts" if is_xtts else "whisper",
        })
    return out


_recognizer: Optional[PhonemeRecognizer] = None


def get_phoneme_recognizer() -> PhonemeRecognizer:
    global _recognizer
    if _recognizer is None:
        _recognizer = PhonemeRecognizer()
    return _recognizer
