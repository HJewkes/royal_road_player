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
# 21.5 letters/s: full takes at cfg 0.5 peaked at 19.7 (median ~15, 764 chunks)
# and the one truncated take read at 25.6. cfg 0.3 speaks slower, so this is
# loose for P4 until it is recalibrated on a cfg 0.3 chapter.
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
    max_letters_per_sec=21.5,
    min_letters=40,
)
