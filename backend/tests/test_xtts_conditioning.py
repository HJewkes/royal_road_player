"""Tests for memoized XTTS conditioning: computed once per voice, not per sentence.

A fake model stands in for XTTS so the cache's keying is tested without loading
any weights; the voice sample is a real temp file because its mtime is part of the key.
"""

import os

from src.tts.xtts import _memoize_conditioning


class FakeModel:
    def __init__(self):
        self.device = "cpu"
        self.computed = 0

    def get_conditioning_latents(self, audio_path, **params):
        self.computed += 1
        return ("gpt_latent", self.computed), ("speaker", self.computed)


def _memoized(tmp_path):
    sample = tmp_path / "voice.wav"
    sample.write_bytes(b"RIFF")
    model = FakeModel()
    _memoize_conditioning(model)
    return model, str(sample)


def test_repeated_sentences_reuse_one_computation(tmp_path):
    model, sample = _memoized(tmp_path)

    first = model.get_conditioning_latents(audio_path=sample, gpt_cond_len=30)
    second = model.get_conditioning_latents(audio_path=sample, gpt_cond_len=30)

    assert first == second
    assert model.computed == 1


def test_different_conditioning_settings_are_computed_separately(tmp_path):
    model, sample = _memoized(tmp_path)

    model.get_conditioning_latents(audio_path=sample, gpt_cond_len=30)
    model.get_conditioning_latents(audio_path=sample, gpt_cond_len=6)

    assert model.computed == 2


def test_replaced_voice_sample_is_recomputed(tmp_path):
    model, sample = _memoized(tmp_path)
    model.get_conditioning_latents(audio_path=sample)

    stat = os.stat(sample)
    os.utime(sample, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000_000))
    model.get_conditioning_latents(audio_path=sample)

    assert model.computed == 2


def test_device_move_does_not_reuse_tensors_from_the_old_device(tmp_path):
    model, sample = _memoized(tmp_path)
    model.get_conditioning_latents(audio_path=sample)

    model.device = "mps"
    model.get_conditioning_latents(audio_path=sample)

    assert model.computed == 2


def test_list_and_single_path_forms_share_the_cache(tmp_path):
    model, sample = _memoized(tmp_path)

    model.get_conditioning_latents(audio_path=[sample])
    model.get_conditioning_latents(audio_path=sample)

    assert model.computed == 1
