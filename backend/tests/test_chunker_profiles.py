"""Chunking profiles: XTTS output stays fixed, Chatterbox gets longer quote-aware chunks."""

import pytest

from src.text.chunker import (CHATTERBOX_CHUNKING, XTTS_CHUNKING, TextChunker,
                              chunking_for)

QUOTED_LINE = 'Tom said, "We go now. Bring the map."'
CARAVAN = ("The caravan crept along the ridge while the wind pushed grit into every fold of cloth. "
           "Mara counted the carts twice, then a third time, because the numbers never matched the ledger. "
           "By dusk the drivers had stopped talking, and the only sound was the creak of axles under load, "
           "steady as a heartbeat and twice as tiresome.")


def _texts(text, profile):
    return [c.text for c in TextChunker(profile).chunk(text)]


def _filler(length, word="lantern"):
    """A sentence of about `length` chars with no internal sentence end."""
    return " ".join([word] * length)[:length - 1].rstrip() + "."


def test_xtts_profile_output_is_unchanged():
    text = QUOTED_LINE + "\n\n" + CARAVAN + "\n\nThen he left."

    chunks = [(c.text, c.text_start, c.text_end) for c in TextChunker().chunk(text)]

    assert chunks == [
        ('Tom said, "We go now. Bring the map.', 0, 36),
        ("The caravan crept along the ridge while the wind pushed grit into every fold of cloth. "
         "Mara counted the carts twice, then a third time, because the numbers never matched the ledger.",
         36, 217),
        ("By dusk the drivers had stopped talking, and the only sound was the creak of axles under load, "
         "steady as a heartbeat and twice as tiresome.", 217, 356),
        ("Then he left.", 356, 369),
    ]


def test_chatterbox_keeps_trailing_quotes():
    assert _texts(QUOTED_LINE, CHATTERBOX_CHUNKING) == [QUOTED_LINE]


def test_long_paragraph_splits_at_sentence_end_outside_quotes():
    narration = _filler(200) + " She turned to the crew."
    speech = ' "' + " ".join(["Load the carts." for _ in range(17)]) + '"'
    paragraph = narration + speech + " Nobody argued with her."
    assert len(narration) < 450 < len(narration) + len(speech)

    chunks = _texts(paragraph, CHATTERBOX_CHUNKING)

    assert chunks[0] == narration
    assert all(c.count('"') % 2 == 0 for c in chunks)


def test_short_chunk_merges_across_paragraph_break():
    first, last = _filler(100), _filler(100, "harbour")

    chunks = _texts(f'{first}\n\n"Yes."\n\n{last}', CHATTERBOX_CHUNKING)

    assert chunks == [first + ' "Yes."', last]


def test_merge_never_exceeds_max():
    long_chunk, short_chunk = _filler(430), _filler(30, "harbour")
    assert len(long_chunk) + len(short_chunk) + 1 > 450

    chunks = _texts(f"{long_chunk}\n\n{short_chunk}", CHATTERBOX_CHUNKING)

    assert chunks == [long_chunk, short_chunk]


def test_merged_text_is_a_space_join():
    assert _texts("Hold.\n\nWait.", CHATTERBOX_CHUNKING) == ["Hold. Wait."]


def test_chunking_for_maps_engine_names_to_profiles():
    assert chunking_for("xtts") is XTTS_CHUNKING
    assert chunking_for("chatterbox") is CHATTERBOX_CHUNKING
    with pytest.raises(ValueError):
        chunking_for("unknown-engine")
