"""Profile thresholds and how a chapter stamp resolves to one."""

from src.tts.engines import render_profile
from src.tts.profiles import P4, T1


def test_t1_threshold_is_ten_percent_over_the_ch18_vllm_max():
    assert T1.max_letters_per_sec == 20.4


def test_t1_stamp_resolves_to_t1():
    assert render_profile("chatterbox", "t1") is T1


def test_p4_and_unprofiled_chatterbox_resolve_to_p4():
    assert render_profile("chatterbox", "p4") is P4
    assert render_profile("chatterbox") is P4


def test_xtts_has_no_profile():
    assert render_profile("xtts", "t1") is None
