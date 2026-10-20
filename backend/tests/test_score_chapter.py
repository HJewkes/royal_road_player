"""Tests for the chapter scoring maths in scripts/score_chapter.py (synthetic text, no models)."""
import importlib.util
from pathlib import Path

import pytest

from src.tts.profiles import P4

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "score_chapter.py"
_spec = importlib.util.spec_from_file_location("score_chapter", _SCRIPT)
score_chapter = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(score_chapter)

LONG_CHUNK = "the red fox ran over the hill and into the cold dark wood"
SHORT_CHUNK = "she waved back"


def test_recall_counts_words_missing_at_chunk_end():
    chunks = [LONG_CHUNK, SHORT_CHUNK]
    hyps = ["the red fox ran over the hill and", SHORT_CHUNK]

    report = score_chapter.recall_report(" ".join(chunks), chunks, hyps)

    # 5 of 16 words lost. A mean of per-chunk recalls would give (8/13 + 1) / 2 = 0.81.
    assert report["chapter_word_recall"] == pytest.approx(11 / 16, abs=1e-4)
    assert report["chunks_recall_lt_0.8"] == [0]
    assert report["chunks_missing_tail"] == [0]


def test_words_lost_mid_chunk_are_not_a_missing_tail():
    chunks = [LONG_CHUNK]
    hyps = ["the red into the cold dark wood"]

    report = score_chapter.recall_report(LONG_CHUNK, chunks, hyps)

    assert report["chunks_recall_lt_0.8"] == [0]
    assert report["chunks_missing_tail"] == []


def test_sim_is_duration_weighted():
    rows = [{"sim": 0.9, "dur_s": 30.0}, {"sim": 0.3, "dur_s": 1.0}, {"sim": 0.3, "dur_s": 1.0}]

    sim = score_chapter.duration_weighted_sim(rows)

    assert sim == pytest.approx((0.9 * 30 + 0.3 * 2) / 32)


def test_pace_report_recalibrates_from_the_fastest_full_take():
    text = "a" * 150
    pad = P4.trailing_pad_s
    durations = [10.0 + pad, 7.5 + pad, 1.0 + pad]  # 15, 20 and 150 letters/s
    texts = [text, text, "too short"]

    report = score_chapter.pace_report(texts, durations, P4)

    assert report["guarded_chunks"] == 2
    assert report["letters_per_s"]["max"] == pytest.approx(20.0)
    assert report["recalibrated_max_letters_per_sec"] == pytest.approx(22.0)
    assert report["early_stops"] == []
