"""Render profiles: the sampling and post-processing numbers each engine runs with.

They live in code, not env, so a chapter's sound is pinned by the commit that
rendered it.
"""

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ChatterboxProfile:
    """Chatterbox generate() kwargs plus the per-chunk post-processing."""

    name: str
    exaggeration: float
    cfg_weight: float
    temperature: float
    min_p: float
    repetition_penalty: float
    top_p: float
    target_lufs: float
    trailing_pad_s: float
    # Early-stop guard (tts/early_stop.py): a take reading faster than this is truncated.
    max_letters_per_sec: float
    min_letters: int

    def generate_kwargs(self) -> dict[str, float]:
        """Every sampling kwarg, explicit: generate()'s own cfg_weight default is 0.5, not P4's."""
        params = asdict(self)
        for key in ("name", "target_lufs", "trailing_pad_s", "max_letters_per_sec", "min_letters"):
            params.pop(key)
        return params


# P4: cfg 0.3 was chosen by ear over 0.5 on an 11-chunk passage (175 vs 184 wpm,
# recall 0.942). The 0.25 s pad is the gap the listening renders used.
# 20.7 letters/s = 1.10 x the fastest kept take of a cfg 0.3 chapter render
# (2026-10-20, 355 chunks, 330 of them >= min_letters): median 14.21, p99 17.67,
# max 18.84. The two truncated takes in that render read at ~26.2 and ~24.7.
P4 = ChatterboxProfile(
    name="p4",
    exaggeration=0.5,
    cfg_weight=0.3,
    temperature=0.8,
    min_p=0.05,
    repetition_penalty=1.2,
    top_p=1.0,
    target_lufs=-20.0,
    trailing_pad_s=0.25,
    max_letters_per_sec=20.7,
    min_letters=40,
)


@dataclass(frozen=True)
class VllmProfile:
    """chatterbox-vllm sampling kwargs plus post-processing; CFG and diffusion steps are settings."""

    name: str
    exaggeration: float
    temperature: float
    min_p: float
    top_p: float
    repetition_penalty: float
    target_lufs: float
    trailing_pad_s: float
    max_letters_per_sec: float
    min_letters: int

    def sampling_kwargs(self) -> dict[str, float]:
        """Every sampling kwarg, explicit: the port defaults to top_p 0.8 and repetition_penalty 2.0."""
        return {
            "exaggeration": self.exaggeration,
            "temperature": self.temperature,
            "min_p": self.min_p,
            "top_p": self.top_p,
            "repetition_penalty": self.repetition_penalty,
        }


# T1: the owner's chatterbox-vllm settings (2026-10-20), with CFG 0.5 set in
# Settings.chatterbox_vllm_cfg. vLLM speech is ~9-10% slower than stock, so its
# guard is calibrated on its own output: 18.7 letters/s = 1.10 x the fastest of
# 43 cfg 0.5 / rep 1.2 takes >= min_letters, measured after the 1.05 tempo step
# and without the pad (median 14.11, p90 16.04, max 16.96).
T1 = VllmProfile(
    name="t1",
    exaggeration=0.5,
    temperature=0.8,
    min_p=0.05,
    top_p=1.0,
    repetition_penalty=1.2,
    target_lufs=-20.0,
    trailing_pad_s=0.25,
    max_letters_per_sec=18.7,
    min_letters=40,
)
