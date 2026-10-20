"""The worker's per-take post-processing, on synthetic sines (no model, no torch)."""

import numpy as np
import pyloudnorm

from src.tts.chatterbox_audio import PEAK_CEILING, finish_take, limit_peaks

SR = 24000


def _sine(seconds: float, amplitude: float = 0.05) -> np.ndarray:
    t = np.arange(int(seconds * SR)) / SR
    return amplitude * np.sin(2 * np.pi * 220 * t)


def test_loudness_normalises_to_minus_20_lufs():
    wav, raw_lufs = finish_take(_sine(3.0), SR, target_lufs=-20.0, pad_s=0.0)

    assert raw_lufs < -25
    assert abs(pyloudnorm.Meter(SR).integrated_loudness(wav.astype(np.float64)) - -20.0) < 0.5


def test_sub_half_second_audio_is_not_normalised():
    clip = _sine(0.3)

    wav, raw_lufs = finish_take(clip, SR, target_lufs=-20.0, pad_s=0.0)

    assert raw_lufs is None
    assert np.all(np.isfinite(wav))
    np.testing.assert_allclose(wav, clip.astype(np.float32))


def test_trailing_pad_is_appended():
    take = _sine(1.0)

    wav, _ = finish_take(take, SR, target_lufs=-20.0, pad_s=0.25)

    assert len(wav) == len(take) + SR // 4
    assert not np.any(wav[len(take):])


def _quiet_take_with_loud_burst() -> np.ndarray:
    """Three seconds whose 20 ms burst, once raised to -20 LUFS, lands past full scale.
    The burst must stay short: a long one sets the take's loudness itself."""
    take = _sine(3.0, amplitude=0.1)
    burst = slice(SR, SR + SR // 50)
    take[burst] = _sine(3.0, amplitude=1.0)[burst]
    return take


def test_normalised_burst_is_held_under_the_ceiling_at_target_loudness():
    take = _quiet_take_with_loud_burst()
    gain = 10 ** ((-20.0 - pyloudnorm.Meter(SR).integrated_loudness(take)) / 20)
    assert np.abs(take).max() * gain > 1.0

    wav, _ = finish_take(take, SR, target_lufs=-20.0, pad_s=0.0)

    assert np.abs(wav).max() <= PEAK_CEILING
    assert abs(pyloudnorm.Meter(SR).integrated_loudness(wav.astype(np.float64)) - -20.0) < 0.5


def test_limiter_scales_the_burst_rather_than_flattening_it():
    """Hard clipping would pin most of the burst's samples at the ceiling; a gain
    envelope leaves the sine's shape and touches the ceiling only at its crests."""
    take = _sine(0.2, amplitude=3.0)

    limited = limit_peaks(take, SR)

    assert np.abs(limited).max() <= PEAK_CEILING
    assert np.mean(np.abs(limited) >= PEAK_CEILING * 0.9999) < 0.05


def test_take_under_the_ceiling_is_untouched_by_the_limiter():
    take = _sine(1.0, amplitude=0.5)

    np.testing.assert_array_equal(limit_peaks(take, SR), take)


def test_output_is_clipped_float32():
    wav, _ = finish_take(_sine(0.3, amplitude=1.5), SR, target_lufs=-20.0, pad_s=0.0)

    assert wav.dtype == np.float32
    assert wav.max() <= 1.0 and wav.min() >= -1.0
