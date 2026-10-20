"""Smoke-check Chatterbox on CUDA.

Without flags (`make check-chatterbox`, Chatterbox venv, gpu-jobs.slice): imports
what the render worker loads (chatterbox, Perth, pyloudnorm, soundfile) plus
parselmouth, and runs one op on the GPU. No model download, no audio.

With --render (main venv, which drives the worker the way the pool does):
renders a few synthetic sentences through ChatterboxEngine and checks each take
is 24 kHz PCM_16 at -20 LUFS and passes the early-stop guard. Prints sample
rate, LUFS, letters/s and realtime factor per take.

  ./venv-chatterbox/bin/python -I scripts/check_chatterbox.py
  AUDIOBOOK_CHATTERBOX_PYTHON=venv-chatterbox/bin/python \\
      ./venv-cu128/bin/python scripts/check_chatterbox.py --render

Exits non-zero on any failed check.
"""

import argparse
import importlib.metadata
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

SENTENCES = [
    "The lantern swung gently above the quiet harbour as the boats came home.",
    "She folded the map twice, tucked it into her coat, and walked toward the hills.",
    '"We leave at dawn," he said, "so pack light and sleep early tonight."',
]
SAMPLE_RATE = 24_000
LUFS_TOLERANCE = 0.5

# Run under the Chatterbox interpreter: the main venv has no pyloudnorm.
_LUFS_SCRIPT = """
import sys
import pyloudnorm
import soundfile
for path in sys.argv[1:]:
    audio, rate = soundfile.read(path)
    print(pyloudnorm.Meter(rate).integrated_loudness(audio))
"""


def check_imports() -> int:
    import parselmouth  # noqa: F401  (reference rebuild, scripts/build_reference.py)
    import perth  # noqa: F401
    import pyloudnorm  # noqa: F401
    import soundfile  # noqa: F401
    import torch
    import torchaudio
    from chatterbox.tts import ChatterboxTTS  # noqa: F401

    print("python", sys.version.split()[0], sys.executable)
    print("torch", torch.__version__, "torchaudio", torchaudio.__version__)
    print("chatterbox-tts", importlib.metadata.version("chatterbox-tts"))
    print("transformers", importlib.metadata.version("transformers"))
    if not torch.cuda.is_available():
        print("cuda unavailable", file=sys.stderr)
        return 1
    device = torch.cuda.get_device_name(0)
    capability = torch.cuda.get_device_capability(0)
    total = (torch.ones(1024, device="cuda") * 2).sum().item()
    print("cuda", torch.version.cuda, device, capability, "gpu op ok" if total == 2048 else "gpu op BAD")
    return 0 if total == 2048 else 1


def _lufs(python: str, paths: list[Path]) -> list[float]:
    result = subprocess.run(
        [python, "-I", "-c", _LUFS_SCRIPT, *map(str, paths)],
        capture_output=True, text=True, check=True,
    )
    return [float(line) for line in result.stdout.split()]


def _take_report(text: str, path: Path, elapsed: float, lufs: float, profile) -> tuple[str, bool]:
    from src.tts.early_stop import spoken_letters, take_shortfall, wav_duration

    with wave.open(str(path), "rb") as wav:
        rate, width = wav.getframerate(), wav.getsampwidth()
    audio_s = wav_duration(path)
    pace = spoken_letters(text) / (audio_s - profile.trailing_pad_s)
    shortfall = take_shortfall(text, path, profile)
    ok = (rate == SAMPLE_RATE and width == 2 and shortfall is None
          and abs(lufs - profile.target_lufs) <= LUFS_TOLERANCE)
    line = (f"{path.name}: {rate} Hz, {8 * width}-bit, {lufs:.1f} LUFS, {audio_s:.2f}s, "
            f"{pace:.1f} letters/s, RTF {elapsed / audio_s:.2f}, "
            f"guard {'pass' if shortfall is None else f'EARLY STOP {shortfall:.2f}'}")
    return line, ok


def check_render() -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
    from src.tts.chatterbox import ChatterboxEngine
    from src.tts.engines import chunk_seed

    engine = ChatterboxEngine()
    out_dir = Path(tempfile.mkdtemp(prefix="check_chatterbox_"))
    try:
        engine.load_model()
        takes = []
        for index, text in enumerate(SENTENCES):
            path, elapsed = engine.synthesize(text, out_dir / f"{index:03d}.wav", seed=chunk_seed(index))
            takes.append((text, path, elapsed))
    finally:
        engine.close()
    loudness = _lufs(engine.python, [path for _, path, _ in takes])
    failed = 0
    for (text, path, elapsed), lufs in zip(takes, loudness):
        line, ok = _take_report(text, path, elapsed, lufs, engine.profile)
        print(("ok   " if ok else "FAIL ") + line)
        failed += not ok
    print(f"{len(takes) - failed}/{len(takes)} takes passed; wavs in {out_dir}")
    return 1 if failed else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--render", action="store_true", help="render synthetic sentences through the engine")
    args = ap.parse_args()
    return check_render() if args.render else check_imports()


if __name__ == "__main__":
    sys.exit(main())
