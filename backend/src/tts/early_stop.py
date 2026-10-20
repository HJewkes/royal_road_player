"""Early-stop guard: flag a take whose audio is too short for its text.

Chatterbox's English model has no end-of-speech guard, so a take can stop
mid-chunk and still sound clean. Nothing in the take itself marks the missing
words, but its pace does: a truncated take reads its text faster than any full
take ever does. Stdlib only, so the scan and repair scripts can use it as well.
"""

import wave
from pathlib import Path
from typing import Optional


def spoken_letters(text: str) -> int:
    """Alphanumeric characters: steadier per second of speech than raw characters."""
    return sum(ch.isalnum() for ch in text)


def early_stop_shortfall(
    text: str, audio_s: float, max_letters_per_sec: float, min_letters: int
) -> Optional[float]:
    """The fraction of the shortest plausible take that is missing, or None if it is long enough.

    Texts under `min_letters` are never flagged: a few words have too little
    speech for their pace to mean anything.
    """
    letters = spoken_letters(text)
    if letters < min_letters:
        return None
    shortest_full_s = letters / max_letters_per_sec
    if audio_s >= shortest_full_s:
        return None
    return 1.0 - audio_s / shortest_full_s


def wav_duration(path: Path) -> float:
    """Audio seconds in a PCM wav, from its header."""
    with wave.open(str(path), "rb") as wav:
        return wav.getnframes() / wav.getframerate()
