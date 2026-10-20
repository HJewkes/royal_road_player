"""Smoke-check the Chatterbox venv on CUDA: run by `make check-chatterbox` in gpu-jobs.slice.

Imports what the render worker loads (chatterbox, Perth, pyloudnorm, soundfile)
plus parselmouth, and runs one op on the GPU. No model download, no audio. Exits
non-zero if CUDA is not usable.
"""

import importlib.metadata
import sys

import parselmouth  # noqa: F401  (reference rebuild, scripts/build_reference.py)
import perth  # noqa: F401
import pyloudnorm  # noqa: F401
import soundfile  # noqa: F401
import torch
import torchaudio
from chatterbox.tts import ChatterboxTTS  # noqa: F401


def main() -> int:
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


if __name__ == "__main__":
    sys.exit(main())
