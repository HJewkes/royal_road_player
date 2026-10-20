"""Chatterbox render worker: one loaded model, JSON lines in, JSON lines out.

Run as `python -I chatterbox_worker.py --reference REF` under the Chatterbox venv
(`make setup-chatterbox`). It imports nothing from `src`: that venv's
transformers, numpy and librosa conflict with the server's, so the server talks to
it over a pipe (ChatterboxEngine in chatterbox.py).

Protocol: once loaded it writes {"ready": true, "sample_rate": N}. Each request
line {"text", "out", "seed", "target_lufs", "trailing_pad_s", <generate kwargs>}
gets one reply, {"ok": true, "audio_s", "raw_lufs", "synth_s"} or
{"ok": false, "error"}. Replies go to a copy of the original stdout, and fd 1 is
pointed at stderr: the model libraries print ("loaded PerthNet") and those lines
would otherwise land in the protocol stream.
"""

import argparse
import importlib.util
import json
import os
import sys
import time
from pathlib import Path

GENERATE_KWARGS = ("exaggeration", "cfg_weight", "temperature", "min_p", "repetition_penalty", "top_p")


def _protocol_channel():
    sys.stdout.flush()
    channel = os.fdopen(os.dup(1), "w", buffering=1, encoding="utf-8")
    os.dup2(2, 1)
    sys.stdout = sys.stderr
    return channel


def _load_audio_helpers():
    path = Path(__file__).with_name("chatterbox_audio.py")
    spec = importlib.util.spec_from_file_location("chatterbox_audio", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ChatterboxRenderer:
    """The ported P4 render loop: seed, generate, normalise, pad, write PCM_16."""

    def __init__(self, args):
        import soundfile
        import torch
        from chatterbox.tts import ChatterboxTTS

        self._torch, self._soundfile = torch, soundfile
        self._audio = _load_audio_helpers()
        self._model = ChatterboxTTS.from_pretrained(device=args.device)
        self._model.prepare_conditionals(args.reference, exaggeration=args.exaggeration)
        self.sample_rate = self._model.sr

    def render(self, request: dict) -> dict:
        if request.get("seed") is not None:
            self._torch.manual_seed(int(request["seed"]))
        kwargs = {key: float(request[key]) for key in GENERATE_KWARGS}
        start = time.perf_counter()
        wav = self._model.generate(request["text"], **kwargs).squeeze(0).cpu().numpy()
        synth_s = time.perf_counter() - start
        wav, raw_lufs = self._audio.finish_take(
            wav, self.sample_rate, float(request["target_lufs"]), float(request["trailing_pad_s"])
        )
        _write_pcm16(self._soundfile, Path(request["out"]), wav, self.sample_rate)
        return {"audio_s": round(len(wav) / self.sample_rate, 3), "raw_lufs": raw_lufs, "synth_s": round(synth_s, 3)}


def _write_pcm16(soundfile, out: Path, wav, sample_rate: int) -> None:
    partial = out.with_name(out.stem + ".partial.wav")
    soundfile.write(partial, wav, sample_rate, subtype="PCM_16")
    os.replace(partial, out)


def _handle(renderer, line: str) -> dict:
    try:
        return {"ok": True, **renderer.render(json.loads(line))}
    except Exception as exc:  # one bad request must not take the loaded model down
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def serve(channel, renderer, requests) -> None:
    channel.write(json.dumps({"ready": True, "sample_rate": renderer.sample_rate}) + "\n")
    for line in requests:
        if line.strip():
            channel.write(json.dumps(_handle(renderer, line)) + "\n")


def _parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--reference", required=True, help="voice reference wav")
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--exaggeration", type=float, default=0.5)
    return parser.parse_args(argv)


def main(argv=None, renderer_factory=ChatterboxRenderer) -> None:
    channel = _protocol_channel()
    renderer = renderer_factory(_parse_args(argv))
    serve(channel, renderer, sys.stdin)


if __name__ == "__main__":
    main()
