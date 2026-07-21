"""Tests for the pronunciation lexicon and its normalizer integration."""

from src.text.lexicon import PronunciationLexicon, generate_candidates
from src.text.normalizer import TextNormalizer


def test_apply_replaces_whole_words_case_insensitively():
    lex = PronunciationLexicon({"Wythenshawe": "Withenshaw", "Kisi": "Keesee"})
    out = lex.apply("From wythenshawe, Kisi wrote to Wythenshawe again.")
    assert out == "From Withenshaw, Keesee wrote to Withenshaw again."


def test_apply_does_not_match_substrings():
    lex = PronunciationLexicon({"art": "arrt"})
    assert lex.apply("The cart and the artist") == "The cart and the artist"


def test_apply_is_idempotent():
    lex = PronunciationLexicon({"Bochum": "Bokum"})
    once = lex.apply("a match in Bochum tonight")
    assert lex.apply(once) == once  # respelling is not itself a key


def test_reserved_comment_key_is_ignored():
    lex = PronunciationLexicon({"_comment": "docs", "Wrexham": "Rexum"})
    assert "_comment" not in lex.entries
    assert lex.apply("Wrexham") == "Rexum"


def test_empty_lexicon_is_a_noop():
    lex = PronunciationLexicon({})
    assert lex.apply("nothing to change here") == "nothing to change here"


def test_generate_candidates_excludes_original_and_dedups():
    cands = generate_candidates("Wrexham")
    assert "Wrexham" not in cands
    assert len(cands) == len(set(c.lower() for c in cands))
    assert cands  # produced at least one variant


def test_generate_candidates_applies_known_rewrites():
    cands = [c.lower() for c in generate_candidates("Wythenshawe")]
    assert any("with" in c for c in cands)  # y->i rewrite
    cands_x = [c.lower() for c in generate_candidates("Wrexham")]
    assert any(c.startswith("r") for c in cands_x)  # wr->r rewrite


def test_generate_candidates_respects_limit():
    assert len(generate_candidates("Wythenshawe", limit=3)) <= 3


def test_normalizer_applies_lexicon(monkeypatch):
    import src.text.normalizer as norm
    monkeypatch.setattr(norm, "get_lexicon",
                        lambda: PronunciationLexicon({"Ghanaian": "Ganayan"}))
    result = TextNormalizer().normalize("A Ghanaian striker signed today.")
    assert "Ganayan" in result and "Ghanaian" not in result
