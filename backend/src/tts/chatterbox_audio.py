"""Per-chunk post-processing for Chatterbox takes: loudness, clip, trailing pad.

Imports nothing from `src`: the Chatterbox worker loads this file by path from
its own venv, and CI imports it from the main one.
"""

import numpy as np
import pyloudnorm

# pyloudnorm's gating needs at least one 400 ms block; under ~0.5 s it returns
# -inf, and normalising to that turns the clip into NaN.
MIN_NORMALISE_S = 0.5


def finish_take(
    wav: np.ndarray, sample_rate: int, target_lufs: float, pad_s: float
) -> tuple[np.ndarray, float | None]:
    """Return the take ready to write as float32, and its loudness before normalising."""
    wav = np.asarray(wav, dtype=np.float64)
    raw_lufs = None
    if len(wav) > sample_rate * MIN_NORMALISE_S:
        measured = float(pyloudnorm.Meter(sample_rate).integrated_loudness(wav))
        if np.isfinite(measured):  # a silent take measures -inf too
            raw_lufs = measured
            wav = pyloudnorm.normalize.loudness(wav, raw_lufs, target_lufs)
    pad = np.zeros(round(pad_s * sample_rate))
    return np.clip(np.concatenate([wav, pad]), -1.0, 1.0).astype(np.float32), raw_lufs
