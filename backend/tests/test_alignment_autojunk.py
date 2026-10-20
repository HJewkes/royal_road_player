"""Regression tests: alignment must not collapse on 200+ element inputs (synthetic text).

difflib's autojunk heuristic treats any element over 1% of a 200+ element sequence as
junk, so small alphabets (characters, words from a tiny vocabulary) misalign.
"""
import importlib.util
import random
from pathlib import Path

from src.validation.comparison import compare_texts
from src.validation.defects import _char_distance, detect_defects

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "filter_hallucinations.py"
_spec = importlib.util.spec_from_file_location("filter_hallucinations", _SCRIPT)
filter_hallucinations = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(filter_hallucinations)

LONG_TEXT = "the cat sat on the mat and the dog ate the log " * 6
VOCAB = ["alpha", "beta", "gamma", "delta"]
SHUFFLED = random.Random(7).choices(VOCAB, k=240)  # aperiodic, so the alignment is unambiguous


def _rich(words):
    return {"text": " ".join(words), "segments": [],
            "words": [{"word": w, "start": i * 0.5, "end": i * 0.5 + 0.4, "probability": 0.99}
                      for i, w in enumerate(words)]}


def test_compare_texts_scores_a_one_word_change_in_a_long_chunk_as_near_identical():
    assert len(LONG_TEXT) > 200
    result = compare_texts(LONG_TEXT, LONG_TEXT.replace("cat", "hat", 1))
    assert result.similarity > 0.98
    assert result.passed


def test_char_distance_of_a_one_letter_change_in_long_text_is_small():
    assert _char_distance(LONG_TEXT, LONG_TEXT.replace("cat", "hat", 1)) < 0.02


def test_detect_defects_flags_only_the_omitted_word_in_a_long_run():
    heard = SHUFFLED[:100] + SHUFFLED[101:]
    defects = detect_defects(" ".join(SHUFFLED), _rich(heard))
    assert [d.kind for d in defects] == ["omission"]


def test_whisper_insertion_chars_counts_only_the_inserted_word():
    expected = " ".join(SHUFFLED)
    heard = SHUFFLED[:100] + ["extraneous"] + SHUFFLED[100:]
    total = filter_hallucinations._whisper_insertion_chars(expected, _rich(heard))
    assert total == len("extraneous")
