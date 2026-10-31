#!/usr/bin/env python3
"""Speak the audiobook voice over the speech-tts command contract.

Reads one JSON request from stdin ({"version": 1, "voice", "text", "speed"?,
"language"?, "outDir"?, "out"?}), renders it through the same verified synthesis
as a chapter chunk, and answers on stdout:

  --output stdout-wav   RIFF bytes and nothing else, so ssh can carry the audio
  --output json         {"wav": "<bare filename in outDir>", "durationS": n}

Without --output the request decides: commandTts sends outDir only in json mode
and passes no flag of its own, so a profile needs no extra argv.

The voice "narrator" is the engine in settings; "xtts" and "chatterbox" name one.
Exit 0 on success, 69 when the engine cannot run on this host, 2 for a request
this voice cannot honour, 1 for a failed render.

  echo '{"version": 1, "voice": "narrator", "text": "Hello."}' \\
    | ./venv311/bin/python scripts/tts_cli.py --output stdout-wav > hello.wav
"""
import argparse
import json
import os
import sys
import tempfile
import wave
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

from src.config import get_settings  # noqa: E402
from src.text.normalizer import TextNormalizer  # noqa: E402
from src.tts import get_tts_engine  # noqa: E402
from src.tts.chatterbox import ChatterboxUnavailable  # noqa: E402
from src.tts.engines import ENGINES  # noqa: E402
from src.tts.verified import synthesize_verified  # noqa: E402

EX_BAD_REQUEST = 2
EX_UNAVAILABLE = 69
DEFAULT_VOICE = "narrator"
VOICES = (DEFAULT_VOICE, *ENGINES)


class BadRequest(ValueError):
    """The request breaks the contract or asks for what this voice cannot do."""


def parse_request(raw: bytes) -> dict:
    try:
        request = json.loads(raw)
    except ValueError as exc:
        raise BadRequest(f"request is not JSON: {exc}") from exc
    if not isinstance(request, dict) or request.get("version") != 1:
        raise BadRequest("expected a version 1 request object")
    if "tokens" in request:
        raise BadRequest("phoneme tokens are not supported; send text")
    text = request.get("text")
    if not isinstance(text, str) or not text.strip():
        raise BadRequest("text must be a non-empty string")
    if request.get("voice") not in VOICES:
        raise BadRequest(f"unknown voice {request.get('voice')!r}; expected one of {VOICES}")
    if str(request.get("language", "en")).split("-")[0].lower() != "en":
        raise BadRequest(f"unsupported language {request['language']!r}; this voice speaks en")
    return request


def render(request: dict, path: Path) -> None:
    """Render the request to `path`, spelling initialisms as a chapter's text is."""
    voice = request["voice"]
    tts = get_tts_engine(None if voice == DEFAULT_VOICE else voice)
    text = TextNormalizer().normalize_acronyms(request["text"])
    speed = request.get("speed", 1)
    params = {} if speed == 1 else {"speed": speed}
    settings = get_settings()
    if settings.verify_synthesis:
        synthesize_verified(tts, text, path, retries=settings.verify_max_retries, **params)
    else:
        tts.synthesize(text, path, **params)


def _wav_seconds(path: Path) -> float:
    """The file's length; raises unless an engine really wrote a RIFF/WAVE file."""
    with wave.open(str(path), "rb") as wav:
        return wav.getnframes() / wav.getframerate()


def answer_stdout_wav(request: dict, answer) -> None:
    with tempfile.TemporaryDirectory() as scratch:
        path = Path(scratch) / "out.wav"
        render(request, path)
        _wav_seconds(path)
        answer.write(path.read_bytes())


def answer_json(request: dict, answer) -> None:
    out_dir = request.get("outDir")
    if not out_dir:
        raise BadRequest("json output needs outDir in the request")
    path = Path(out_dir) / Path(request.get("out", "out.wav")).name
    render(request, path)
    answer.write(json.dumps({"wav": path.name, "durationS": _wav_seconds(path)}).encode())


ANSWERS = {"stdout-wav": answer_stdout_wav, "json": answer_json}


def _claim_stdout() -> int:
    """Keep stdout for the answer and send fd 1 to stderr.

    At the descriptor, not sys.stdout: Coqui prints progress and native libraries
    write to fd 1, and one stray byte corrupts the answer.
    """
    sys.stdout.flush()
    answer_fd = os.dup(1)
    os.dup2(2, 1)
    return answer_fd


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--output", choices=sorted(ANSWERS), help="default: json if the request has outDir")
    args = ap.parse_args(argv)

    with os.fdopen(_claim_stdout(), "wb") as answer:
        try:
            request = parse_request(sys.stdin.buffer.read())
            mode = args.output or ("json" if "outDir" in request else "stdout-wav")
            ANSWERS[mode](request, answer)
        except BadRequest as exc:
            print(f"tts_cli: {exc}", file=sys.stderr)
            return EX_BAD_REQUEST
        except (ChatterboxUnavailable, ImportError) as exc:
            print(f"tts_cli: engine unavailable: {exc}", file=sys.stderr)
            return EX_UNAVAILABLE
    return 0


if __name__ == "__main__":
    sys.exit(main())
