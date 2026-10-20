"""The torch-free bookkeeping behind the batched S3Gen: sub-batch plans, order, mel spans."""

import pytest

from src.tts.s3gen_batch import plan_sub_batches, restore_order, take_mel_spans

PROMPT = 250


def _padded_cost(group: list[int], lengths: list[int]) -> int:
    return len(group) * (PROMPT + max(lengths[i] for i in group))


def test_every_sub_batch_fits_the_budget_with_the_prompt_counted():
    lengths = [300, 120, 610, 66, 214, 400, 90, 250]

    groups = plan_sub_batches(lengths, PROMPT, max_padded_tokens=2000)

    assert all(_padded_cost(group, lengths) <= 2000 for group in groups)
    assert sorted(i for group in groups for i in group) == list(range(len(lengths)))


def test_takes_are_grouped_longest_first_so_padding_stays_small():
    lengths = [100, 600, 110, 590]

    groups = plan_sub_batches(lengths, PROMPT, max_padded_tokens=2 * (PROMPT + 600))

    assert groups == [[1, 3], [2, 0]]


def test_a_take_longer_than_the_budget_still_renders_alone():
    lengths = [50, 5000, 60]

    groups = plan_sub_batches(lengths, PROMPT, max_padded_tokens=1000)

    assert groups[0] == [1]
    assert sorted(i for group in groups for i in group) == [0, 1, 2]


def test_outputs_come_back_in_the_order_the_takes_went_in():
    groups = [[1, 3], [2, 0]]

    ordered = restore_order(groups, [["take1", "take3"], ["take2", "take0"]])

    assert ordered == ["take0", "take1", "take2", "take3"]


def test_a_sub_batch_missing_an_output_is_an_error_not_a_gap():
    with pytest.raises(ValueError, match="2 takes returned 1"):
        restore_order([[0, 1]], [["take0"]])


def test_each_take_keeps_its_own_frames_after_the_prompt_and_before_the_padding():
    spans = take_mel_spans([3, 7], prompt_mel_len=500)

    assert spans == [(500, 506), (500, 514)]
