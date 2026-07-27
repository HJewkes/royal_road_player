"""Tests for pinned table renderings and the unrendered-table guardrail.

The point of pinning is that agent-written narration must behave like a
committed artifact: identical on every regeneration, reviewable before it is
spoken, and invalidated when the table it describes changes.
"""

import pytest

from src.text.renderings import (
    RenderingStore,
    UnrenderedSpecBlockError,
    apply_renderings,
    render_or_raise,
    rendering_key,
)
from src.text.spec_blocks import find_spec_blocks

CHAPTER = """Max opened the interface and sighed.

Born x.x.x (Age xx) Nationality

Acceleration xx Flair xx Set Pieces xx

Aggression xx Handling xx Stamina xx

CA xxx PA xxx

He closed it again and went back to the match.
"""

NARRATION = "A profile is a wall of numbers only Max can read."


@pytest.fixture
def block():
    return find_spec_blocks(CHAPTER)[0]


def test_unrendered_table_stops_the_chapter(tmp_path):
    """Spoken verbatim this is a minute of "Acceleration ex-ex"; STT validation
    would score it fine, so normalize is the only place to catch it."""
    with pytest.raises(UnrenderedSpecBlockError) as exc:
        render_or_raise(CHAPTER, tmp_path)
    assert "no pinned rendering" in str(exc.value)


def test_prose_without_tables_passes_through_untouched(tmp_path):
    prose = "Max walked to the touchline.\n\nThe crowd was restless.\n"
    assert render_or_raise(prose, tmp_path) == prose


def test_pinned_rendering_replaces_the_whole_block(tmp_path, block):
    store = RenderingStore(tmp_path)
    store.put(block, NARRATION, "agent")

    text, unrendered = apply_renderings(CHAPTER, store)

    assert unrendered == []
    assert NARRATION in text
    for leftover in ("Acceleration xx", "CA xxx", "Born x.x.x"):
        assert leftover not in text
    # surrounding prose survives
    assert "Max opened the interface" in text
    assert "He closed it again" in text


def test_rendering_survives_a_reload(tmp_path, block):
    """Pinning is worthless if it doesn't persist — regeneration must reuse it."""
    store = RenderingStore(tmp_path)
    store.put(block, NARRATION, "agent")
    store.save()

    assert render_or_raise(CHAPTER, tmp_path).count(NARRATION) == 1


def test_regeneration_is_byte_identical(tmp_path, block):
    """No drift between runs, so re-rendering a chapter is safe."""
    store = RenderingStore(tmp_path)
    store.put(block, NARRATION, "agent")
    store.save()

    assert render_or_raise(CHAPTER, tmp_path) == render_or_raise(CHAPTER, tmp_path)


def test_editing_the_table_invalidates_its_rendering(tmp_path, block):
    """An upstream edit must not silently keep narration describing the old
    table — the key changes, so the guardrail fires again."""
    store = RenderingStore(tmp_path)
    store.put(block, NARRATION, "agent")
    store.save()

    edited = CHAPTER.replace("Acceleration xx", "Acceleration xx Vision xx")
    with pytest.raises(UnrenderedSpecBlockError):
        render_or_raise(edited, tmp_path)


def test_key_is_stable_across_whitespace_only_changes(block):
    """A re-scrape that reindents shouldn't force a re-render."""
    respaced = find_spec_blocks(CHAPTER.replace("\n\n", "\n\n  "))[0]
    assert rendering_key(respaced) == rendering_key(block)


def test_prune_drops_renderings_whose_table_is_gone(tmp_path, block):
    store = RenderingStore(tmp_path)
    store.put(block, NARRATION, "agent")
    assert store.prune({"deadbeef1234"}) == 1
    assert store.get(rendering_key(block)) is None
