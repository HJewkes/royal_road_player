"""Self-healing synthesis: synthesize a chunk and re-roll if XTTS babbles.

XTTS occasionally injects a hallucinated outburst — phantom phonemes with no
matching source text, most often at the end of a short chunk. The defect is
stochastic, so re-synthesizing usually clears it. This wraps an engine's
``synthesize`` with a detect-and-retry loop: after each take a vocabulary-free
phoneme model (``PhonemeRecognizer``) checks for injected phones; a clean take is
kept immediately, otherwise it re-rolls up to ``retries`` times and keeps the
least-severe take. Used by the background processor so every rendered chunk
self-heals without a separate clean pass.
"""

import logging
import os
import shutil
import tempfile
from pathlib import Path
from typing import Optional

from src.validation.phonemes import (
    detect_hallucinations,
    get_phoneme_recognizer,
    load_slice,
)

logger = logging.getLogger(__name__)


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
    **inference_kwargs,
) -> tuple[Path, float]:
    """Synthesize ``text`` to ``output_path``, re-rolling babbled takes.

    Returns (output_path, duration_seconds), matching ``tts.synthesize``. The first
    hallucination-free take wins; if every attempt babbles, the least-severe take is
    kept so a chunk is never dropped. Falls back to a plain single take if the
    phoneme recognizer can't be loaded.
    """
    if recognizer is None:
        try:
            recognizer = get_phoneme_recognizer()
        except Exception as exc:  # model/deps unavailable — degrade gracefully
            logger.warning(f"Verify unavailable ({exc}); single take.")
            return tts.synthesize(text, output_path, **inference_kwargs)

    best_path: Optional[Path] = None
    best_sev = float("inf")
    best_duration = 0.0
    takes: list[Path] = []

    try:
        for attempt in range(retries + 1):
            tmp = _new_take_path()
            takes.append(tmp)
            _, duration = tts.synthesize(text, tmp, **inference_kwargs)
            halluc = detect_hallucinations(
                text, recognizer.recognize(load_slice(tmp, None, None)), min_run=min_run
            )
            if not halluc:
                shutil.copy(tmp, output_path)
                if attempt:
                    logger.info(f"Verified-clean after {attempt} re-roll(s): {output_path.name}")
                return output_path, duration
            sev = max(h["severity"] for h in halluc)
            if sev < best_sev:
                best_path, best_sev, best_duration = tmp, sev, duration

        shutil.copy(best_path, output_path)
        logger.warning(
            f"Still babbling after {retries} re-rolls (severity {best_sev:.2f}); "
            f"kept least-bad take: {output_path.name}"
        )
        return output_path, best_duration
    finally:
        # Every take has been copied out by now; leaving them behind fills the
        # temp dir with one wav per chunk for the life of the machine.
        for take in takes:
            take.unlink(missing_ok=True)
