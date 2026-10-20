#!/usr/bin/env python3
"""Rebuild the cleaned Chatterbox reference voice (assets/voices/ref_p241_clean.wav).

  vits OUT        render the raw p241 sample with Coqui VITS on CPU. Not
                  deterministic: VITS samples noise, so every run differs. That
                  is why the checked-in p241_vits_source.wav is the stylize input.
  stylize IN OUT  flatten pitch with Praat PSOLA. Deterministic: on
                  assets/voices/p241_vits_source.wav at 0.5 semitones it
                  reproduces ref_p241_clean.wav byte for byte.

  python scripts/build_reference.py stylize assets/voices/p241_vits_source.wav /tmp/ref.wav
  CUDA_VISIBLE_DEVICES= python scripts/build_reference.py vits /tmp/p241.wav
"""
import argparse
import os

VITS_MODEL = "tts_models/en/vctk/vits"
VITS_SPEAKER = "p241"
VITS_TEXT = """
The morning sun cast long shadows across the empty street in Manchester.
James walked slowly, his footsteps echoing in the quiet neighbourhood.
He had been waiting for this moment for weeks, and now it was finally here.
The football match would begin in an hour, and he could already hear the crowd gathering.
"""

PITCH_FLOOR_HZ = 60
PITCH_CEILING_HZ = 300
TIME_STEP_S = 0.01
DEFAULT_SEMITONES = 0.5


def render_vits(out_path: str) -> None:
    os.environ["CUDA_VISIBLE_DEVICES"] = ""
    from TTS.api import TTS

    tts = TTS(VITS_MODEL)
    tts.tts_to_file(text=VITS_TEXT, speaker=VITS_SPEAKER, file_path=out_path)


def stylize(in_path: str, out_path: str, semitones: float = DEFAULT_SEMITONES) -> None:
    import parselmouth
    from parselmouth.praat import call

    sound = parselmouth.Sound(in_path)
    manipulation = call(sound, "To Manipulation", TIME_STEP_S, PITCH_FLOOR_HZ, PITCH_CEILING_HZ)
    tier = call(manipulation, "Extract pitch tier")
    call(tier, "Stylize...", semitones, "semitones")
    call([tier, manipulation], "Replace pitch tier")
    call(manipulation, "Get resynthesis (overlap-add)").save(out_path, "WAV")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    vits = sub.add_parser("vits", help="render the raw VITS p241 sample on CPU")
    vits.add_argument("out")
    style = sub.add_parser("stylize", help="PSOLA pitch-flatten a wav")
    style.add_argument("input")
    style.add_argument("out")
    style.add_argument("--semitones", type=float, default=DEFAULT_SEMITONES)
    args = parser.parse_args()
    if args.command == "vits":
        render_vits(args.out)
    else:
        stylize(args.input, args.out, args.semitones)


if __name__ == "__main__":
    main()
