"""The worker's per-take post-processing, on synthetic sines (no model, no torch)."""

import numpy as np
import pyloudnorm

from src.tts.chatterbox_audio import finish_take

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


def test_output_is_clipped_float32():
    wav, _ = finish_take(_sine(0.3, amplitude=1.5), SR, target_lufs=-20.0, pad_s=0.0)

    assert wav.dtype == np.float32
    assert wav.max() <= 1.0 and wav.min() >= -1.0
