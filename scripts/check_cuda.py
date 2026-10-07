"""Smoke-check the TTS venv on CUDA: run by `make check-cuda` in gpu-jobs.slice.

Imports the stack the server loads (torch, torchaudio, Coqui XTTS, the MCP SDK)
and runs one op on the GPU. No model download, no audio. Exits non-zero if CUDA
is not usable.
"""

import importlib.util
import sys

import mcp  # noqa: F401  (the MCP server shares this venv)
import torch
import torchaudio
import transformers
from TTS.tts.models.xtts import Xtts  # noqa: F401


def main() -> int:
    print("python", sys.version.split()[0], sys.executable)
    print("torch", torch.__version__, "torchaudio", torchaudio.__version__)
    print("transformers", transformers.__version__)
    print("whisper", "installed" if importlib.util.find_spec("whisper") else "absent")
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
