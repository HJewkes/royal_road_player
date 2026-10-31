"""Audiobook's Python against the speech-vet conformance fixtures.

The packages ported this logic to TypeScript, and both sides must keep deciding
alike. fixtures/speech_conformance/ is a verbatim copy of speech-vet's
conformance/ directory: change it only by copying a newer release's files.
"""
import importlib.util
import json
from pathlib import Path

import pytest

from src.text.normalizer import TextNormalizer

_FIXTURES = Path(__file__).parent / "fixtures" / "speech_conformance"
TAKE_SELECTION = json.loads((_FIXTURES / "take-selection.json").read_text(encoding="utf-8"))
NORMALIZE = json.loads((_FIXTURES / "normalize.json").read_text(encoding="utf-8"))

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "fix_pass.py"
_spec = importlib.util.spec_from_file_location("fix_pass", _SCRIPT)
fix_pass = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fix_pass)


def _named(cases):
    return [pytest.param(case, id=case["name"]) for case in cases]


def _score(shape):
    return fix_pass.TakeScore(shape["brokeWords"], shape["strayLength"], shape["distance"])


def _word_map(take):
    return {word: (w["distance"], w["faulty"]) for word, w in take["words"].items()}


def _word_fault_distance(take):
    return max((w["distance"] for w in take["words"].values() if w["faulty"]), default=0)


def _better_take(best, take):
    """speech-vet's betterTake over audiobook's own regressions and keep rule."""
    best_severity = max(best["hallucinations"], default=0)
    take_severity = max(take["hallucinations"], default=0)
    if take_severity != best_severity:
        return take_severity < best_severity
    return fix_pass.keep_take(
        fix_pass.TakeScore(0, best["tail"] or 0, _word_fault_distance(best)),
        fix_pass.TakeScore(
            len(fix_pass._regressions(_word_map(best), _word_map(take))),
            take["tail"] or 0,
            _word_fault_distance(take),
        ),
    )


def test_margins_match_the_shared_value():
    assert fix_pass.MARGIN == TAKE_SELECTION["margin"]
    assert fix_pass.WORSE_MARGIN == TAKE_SELECTION["margin"]


@pytest.mark.parametrize("case", _named(TAKE_SELECTION["keepTake"]))
def test_keep_take_decides_like_speech_vet(case):
    assert fix_pass.keep_take(_score(case["shipped"]), _score(case["take"])) is case["kept"]


@pytest.mark.parametrize("case", _named(TAKE_SELECTION["betterTake"]))
def test_take_comparison_decides_like_speech_vet(case):
    assert _better_take(case["best"], case["take"]) is case["wins"]


@pytest.mark.parametrize("case", _named(NORMALIZE["cases"]))
def test_normalizer_agrees_with_speech_vet(case):
    assert getattr(TextNormalizer(), case["python"])(case["input"]) == case["expected"]
