"""Self-healing synthesis: synthesize a chunk and re-roll if XTTS babbles.

XTTS occasionally injects a hallucinated outburst — phantom phonemes with no
matching source text, most often at the end of a short chunk. The defect is
stochastic, so re-synthesizing usually clears it. This wraps an engine's
``synthesize`` with a detect-and-retry loop: after each take a vocabulary-free
phoneme model (``PhonemeRecognizer``) checks for injected phones; a clean take is
kept immediately, otherwise it re-rolls up to ``retries`` times and keeps the
least-severe take. Used by the background processor so every rendered chunk
self-heals without a separate clean pass.

Engines with an early-stop threshold (Chatterbox) also re-roll a take whose
audio is too short for its text. Chatterbox is seeded, so each re-roll gets
its own seed; an identical seed would only reproduce the same defect.
"""

import logging
import os
import shutil
import tempfile
from pathlib import Path
from typing import Optional

from src.tts.early_stop import take_shortfall
from src.validation.phonemes import (
    detect_hallucinations,
    get_phoneme_recognizer,
    load_slice,
)

logger = logging.getLogger(__name__)

# Chunk seeds are consecutive (999 + chunk index), so a stride of 1 would replay
# the next chunk's first take; a large prime keeps every retake seed distinct.
SEED_STRIDE = 100_003


def _new_take_path() -> Path:
    """A path for one synthesis take.

    mkstemp hands back an ALREADY-OPEN descriptor alongside the path. Keeping
    only the path leaks that descriptor once per take, which is invisible until
    a long chapter exhausts the process limit mid-generation — so close it here
    and let the caller delete the file.
    """
    fd, name = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    return Path(name)


def synthesize_verified(
    tts,
    text: str,
    output_path: Path,
    recognizer=None,
    retries: int = 5,
    min_run: int = 5,
    seed: Optional[int] = None,
    **inference_kwargs,
) -> tuple[Path, float]:
    """Synthesize ``text`` to ``output_path``, re-rolling babbled or truncated takes.

    Returns (output_path, duration_seconds), matching ``tts.synthesize``. The first
    take with no hallucination and no early stop wins; if every attempt is flawed,
    the least-bad take is kept so a chunk is never dropped. Attempt n renders with
    ``seed + n * SEED_STRIDE``. Falls back to a plain single take if the phoneme
    recognizer can't be loaded.
    """
    if recognizer is None:
        try:
            recognizer = get_phoneme_recognizer()
        except Exception as exc:  # model/deps unavailable — degrade gracefully
            logger.warning(f"Verify unavailable ({exc}); single take.")
            return tts.synthesize(text, output_path, seed=seed, **inference_kwargs)

    best: Optional[tuple[tuple[float, float], Path, float]] = None
    takes: list[Path] = []
    try:
        for attempt in range(retries + 1):
            tmp = _new_take_path()
            takes.append(tmp)
            _, duration = tts.synthesize(text, tmp, seed=_take_seed(seed, attempt), **inference_kwargs)
            flaws = _take_flaws(tts, text, tmp, recognizer, min_run)
            if flaws is None:
                shutil.copy(tmp, output_path)
                if attempt:
                    logger.info(f"Verified-clean after {attempt} re-roll(s): {output_path.name}")
                return output_path, duration
            # WARNING, not INFO: pool workers are spawned without logging config,
            # and only WARNING and above reach their stderr.
            logger.warning(
                f"Flawed take {attempt} of {output_path.name}: early-stop shortfall "
                f"{flaws[0]:.2f}, hallucination severity {flaws[1]:.2f}"
            )
            if best is None or flaws < best[0]:
                best = (flaws, tmp, duration)

        (shortfall, severity), best_path, best_duration = best
        shutil.copy(best_path, output_path)
        logger.warning(
            f"No clean take after {retries} re-rolls (early-stop shortfall {shortfall:.2f}, "
            f"hallucination severity {severity:.2f}); kept least-bad take: {output_path.name}"
        )
        return output_path, best_duration
    finally:
        # Every take has been copied out by now; leaving them behind fills the
        # temp dir with one wav per chunk for the life of the machine.
        for take in takes:
            take.unlink(missing_ok=True)


def _take_seed(seed: Optional[int], attempt: int) -> Optional[int]:
    return None if seed is None else seed + attempt * SEED_STRIDE


def _take_flaws(tts, text: str, take: Path, recognizer, min_run: int) -> Optional[tuple[float, float]]:
    """None for a clean take, else (early-stop shortfall, hallucination severity).

    Lower is better, and the shortfall leads: any truncated take ranks below any
    babbling one, because truncation loses text outright.
    """
    shortfall = _early_stop(tts, text, take)
    halluc = detect_hallucinations(
        text, recognizer.recognize(load_slice(take, None, None)), min_run=min_run
    )
    if shortfall is None and not halluc:
        return None
    return shortfall or 0.0, max((h["severity"] for h in halluc), default=0.0)


def _early_stop(tts, text: str, take: Path) -> Optional[float]:
    """The take's early-stop shortfall under its engine's profile; XTTS has no guard."""
    return take_shortfall(text, take, getattr(tts, "profile", None))
