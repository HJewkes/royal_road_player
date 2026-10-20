"""Per-chunk post-processing for Chatterbox takes: loudness, peak limit, trailing pad.

Imports nothing from `src`: the Chatterbox worker loads this file by path from
its own venv, and CI imports it from the main one.
"""

import numpy as np
import pyloudnorm

# pyloudnorm's gating needs at least one 400 ms block; under ~0.5 s it returns
# -inf, and normalising to that turns the clip into NaN.
MIN_NORMALISE_S = 0.5

# Raising a take to the target loudness lifts its peaks past full scale on about
# one chunk in six. The limiter holds them at -1 dBFS, which leaves headroom for
# the inter-sample overs a sample-peak ceiling cannot see.
PEAK_CEILING = 10 ** (-1.0 / 20)
# The gain starts falling this long before a peak and recovers over the same span
# after it: long enough that the ramp is not heard as a click, short enough that
# only the peak's own syllable is quieter.
LIMITER_RAMP_S = 0.005


def finish_take(
    wav: np.ndarray, sample_rate: int, target_lufs: float, pad_s: float
) -> tuple[np.ndarray, float | None]:
    """Return the take ready to write as float32, and its loudness before normalising."""
    wav = np.asarray(wav, dtype=np.float64)
    raw_lufs = None
    if len(wav) > sample_rate * MIN_NORMALISE_S:
        meter = pyloudnorm.Meter(sample_rate)
        measured = float(meter.integrated_loudness(wav))
        if np.isfinite(measured):  # a silent take measures -inf too
            raw_lufs = measured
            wav = _normalise_limited(wav, sample_rate, meter, raw_lufs, target_lufs)
    pad = np.zeros(round(pad_s * sample_rate))
    return np.clip(np.concatenate([wav, pad]), -1.0, 1.0).astype(np.float32), raw_lufs


def _normalise_limited(
    wav: np.ndarray, sample_rate: int, meter, lufs: float, target_lufs: float
) -> np.ndarray:
    """Gain `wav` to the target loudness with its peaks limited.

    Applies the gain itself rather than through pyloudnorm.normalize.loudness,
    whose clipping warning the limiter makes moot. Limiting costs a little
    loudness, so a second pass measures the result and makes the shortfall up.
    """
    for _ in range(2):
        wav = limit_peaks(wav * 10 ** ((target_lufs - lufs) / 20), sample_rate)
        lufs = float(meter.integrated_loudness(wav))
    return wav


def limit_peaks(wav: np.ndarray, sample_rate: int, ceiling: float = PEAK_CEILING) -> np.ndarray:
    """Scale `wav` down around every sample above `ceiling`, leaving the rest alone.

    Each sample's gain is the smallest gain any peak within one ramp of it needs,
    averaged over the same span. Every gain in a peak's average is at most the
    gain that peak needs, so the peak lands at or under the ceiling.
    """
    needed = np.minimum(1.0, ceiling / np.maximum(np.abs(wav), 1e-12))
    if needed.min() >= 1.0:
        return wav
    half = max(1, round(LIMITER_RAMP_S * sample_rate))
    gain = _moving_average(_running_min(needed, half), half)
    # The average can overshoot the needed gain by a rounding error.
    return np.clip(wav * gain, -ceiling, ceiling)


def _running_min(x: np.ndarray, half: int) -> np.ndarray:
    """Minimum of x over [i - half, i + half] for each i, in O(n) (van Herk)."""
    width = 2 * half + 1
    total = -(-(len(x) + 2 * half) // width) * width
    padded = np.ones(total)
    padded[half:half + len(x)] = x
    blocks = padded.reshape(-1, width)
    prefix = np.minimum.accumulate(blocks, axis=1).ravel()
    suffix = np.minimum.accumulate(blocks[:, ::-1], axis=1)[:, ::-1].ravel()
    starts = np.arange(len(x))
    return np.minimum(suffix[starts], prefix[starts + width - 1])


def _moving_average(x: np.ndarray, half: int) -> np.ndarray:
    """Mean of x over [i - half, i + half], treating samples off either end as 1."""
    padded = np.concatenate([np.ones(half), x, np.ones(half)])
    sums = np.concatenate([[0.0], np.cumsum(padded)])
    width = 2 * half + 1
    return (sums[width:] - sums[:-width]) / width
