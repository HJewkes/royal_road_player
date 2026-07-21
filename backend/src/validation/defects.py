"""Detect likely TTS defects by aligning chunk audio (STT) against source text.

Unlike the chapter-level similarity score in ``comparison.py``, this operates at
word granularity so a single mangled word in a long chunk is surfaced with its
location, what the audio actually said, an audio timestamp to listen at, and a
best-guess cause. Three independent signals are combined:

  A. Whisper's own per-segment confidence (avg_logprob / compression_ratio) --
     directly measures "did this region sound like clean speech".
  B. Word-level alignment + phonetic distance -- pinpoints the exact word and
     distinguishes real mangles from benign homophones (their/there).
  C. Heuristic cause attribution -- numbers, stylized elongation, smushed tokens,
     unusual/OOV words, chunk-boundary cuts.
"""

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Optional

try:
    import jellyfish
except ImportError:  # phonetic classification degrades gracefully
    jellyfish = None

# Whisper segment thresholds. avg_logprob is per-token log-probability; clean
# TTS speech sits well above -1.0, garbled audio drops below it. compression_ratio
# above ~2.4 signals repetitive/looping hallucinated output.
LOW_LOGPROB = -1.0
HIGH_COMPRESSION = 2.4

_WORD_RE = re.compile(r"[a-z0-9]+(?:'[a-z]+)?", re.IGNORECASE)

# Single-token number words, so a digit spoken as its word form ("50" -> "fifty")
# is recognised as a correct reading rather than a substitution defect.
_ONES = "zero one two three four five six seven eight nine ten eleven twelve " \
    "thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split()
_TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
         "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90}
_NUMBER_WORDS = {w: i for i, w in enumerate(_ONES)}
_NUMBER_WORDS.update(_TENS)


_NUM_UNITS = {w: i for i, w in enumerate(_ONES)}  # zero..nineteen
_NUM_SCALES = {"thousand": 1000, "million": 1_000_000}


def _numeric_value(word: str) -> Optional[int]:
    """Canonical integer for a single number token ('fifty' or '50'), else None."""
    if word.isdigit():
        return int(word)
    return _NUMBER_WORDS.get(word)


def _scan_number(norms: list, i: int) -> tuple:
    """Parse an English cardinal starting at norms[i] following number grammar.

    Returns (value, end_index); (None, i) if norms[i] does not begin a number.
    Grammar-aware so "one thirty six" splits into [1, 36] (as in "1 36"), not 37.
    """
    if norms[i].isdigit():
        return int(norms[i]), i + 1
    total, group, prev, used, j = 0, 0, None, False, i
    while j < len(norms):
        w = norms[j]
        if w in _NUM_UNITS:
            v = _NUM_UNITS[w]
            if v == 0:
                if used:
                    break
                return 0, j + 1
            if v < 10 and prev in ("unit", "teen"):
                break
            if v >= 10 and prev in ("unit", "teen", "ten"):
                break
            group += v
            prev = "unit" if v < 10 else "teen"
        elif w in _TENS:
            if prev in ("unit", "teen", "ten"):
                break
            group += _TENS[w]
            prev = "ten"
        elif w == "hundred":
            if not used or prev == "hundred":
                break
            group = (group or 1) * 100
            prev = "hundred"
        elif w in _NUM_SCALES:
            if not used:
                break
            total += (group or 1) * _NUM_SCALES[w]
            group, prev = 0, None
        else:
            break
        used = True
        j += 1
    return (total + group, j) if used else (None, i)


# Accepted spoken-name spellings for single letters, so "C" read as "see" is a
# correct rendering rather than a substitution defect.
_LETTER_NAMES = {
    "a": {"ay", "eh"}, "b": {"bee"}, "c": {"see", "sea", "cee"}, "d": {"dee"},
    "e": {"ee"}, "f": {"ef", "eff"}, "g": {"gee"}, "i": {"eye", "aye"},
    "j": {"jay"}, "k": {"kay"}, "l": {"el", "ell"}, "m": {"em"}, "n": {"en"},
    "o": {"oh", "owe"}, "p": {"pee"}, "q": {"cue", "queue"}, "r": {"are"},
    "s": {"es", "ess"}, "t": {"tee", "tea"}, "u": {"you", "yew"}, "v": {"vee"},
    "x": {"ex"}, "y": {"why"}, "z": {"zee", "zed"},
}


def _is_letter_reading(letter: str, heard: str) -> bool:
    """True when a single source letter was correctly spoken as its name."""
    return len(letter) == 1 and letter.isalpha() and heard in _LETTER_NAMES.get(letter, ())

_ELONGATION = re.compile(r"(.)\1{2,}")
_SMUSH = re.compile(r"[a-z]{2,}[-–—/][a-z]{2,}", re.IGNORECASE)


@dataclass
class Token:
    """A source word: original form, match-normalized form, char offset."""
    original: str
    norm: str
    start: int


@dataclass
class Defect:
    """A single suspected defect located in one chunk."""
    kind: str  # substitution | omission | insertion | low_confidence
    expected: str
    heard: str
    severity: float
    causes: list[str] = field(default_factory=list)
    audio_start: Optional[float] = None
    audio_end: Optional[float] = None
    context: str = ""

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "expected": self.expected,
            "heard": self.heard,
            "severity": round(self.severity, 3),
            "causes": self.causes,
            "audio_start": self.audio_start,
            "audio_end": self.audio_end,
            "context": self.context,
        }


def _collapse_elongation(word: str) -> str:
    """'deaaaaar' -> 'dear' so stylized stretches still align to clean speech."""
    return _ELONGATION.sub(r"\1", word)


def tokenize(text: str) -> list[Token]:
    """Split text into match tokens, preserving original form and offset."""
    tokens = []
    for m in _WORD_RE.finditer(text):
        original = m.group(0)
        norm = _collapse_elongation(original.lower())
        tokens.append(Token(original=original, norm=norm, start=m.start()))
    return tokens


def phonetic_distance(a: str, b: str) -> float:
    """Normalized phonetic distance in [0,1]; 0 == homophone, 1 == unrelated.

    Falls back to raw character distance when jellyfish is unavailable.
    """
    if jellyfish is None:
        return _char_distance(a, b)
    ca, cb = jellyfish.metaphone(a), jellyfish.metaphone(b)
    if not ca or not cb:
        return _char_distance(a, b)  # numbers/symbols have no phonetic code
    if ca == cb:
        return 0.0
    dist = jellyfish.levenshtein_distance(ca, cb)
    return min(1.0, dist / max(len(ca), len(cb), 1))


def _char_distance(a: str, b: str) -> float:
    return 1.0 - SequenceMatcher(None, a, b).ratio()


def _causes_for(token: Token, at_boundary: bool) -> list[str]:
    """Heuristic reasons a source word might trip up TTS -> guides the fix."""
    causes = []
    orig = token.original
    if any(c.isdigit() for c in orig):
        causes.append("number")
    if _ELONGATION.search(orig):
        causes.append("stylized_elongation")
    if _SMUSH.search(orig):
        causes.append("smushed")
    if len(orig) > 3 and orig[:1].isupper() and not at_boundary:
        causes.append("unusual_word")  # candidate for pronunciation lexicon
    if at_boundary:
        causes.append("chunk_boundary")
    return causes


# Function words whose omission/insertion is usually a benign STT artifact, not
# a TTS defect worth chasing.
_STOPWORDS = frozenset(
    "a an the of to in on at and or but is it as be by for with that this his her "
    "he she they i you we".split()
)


@dataclass
class HypWord:
    """A transcribed word with its audio timestamp and Whisper confidence."""
    norm: str
    original: str
    start: Optional[float]
    end: Optional[float]
    probability: Optional[float]


def _build_hyp_words(rich: dict) -> list[HypWord]:
    """Extract timestamped hypothesis words, falling back to plain text."""
    words = []
    for w in rich.get("words") or []:
        m = _WORD_RE.search(w.get("word", ""))
        if not m:
            continue
        words.append(HypWord(
            norm=_collapse_elongation(m.group(0).lower()),
            original=m.group(0),
            start=w.get("start"),
            end=w.get("end"),
            probability=w.get("probability"),
        ))
    if not words:  # no word timestamps -> degrade to text-only tokens
        for tok in tokenize(rich.get("text", "")):
            words.append(HypWord(tok.norm, tok.original, None, None, None))
    return words


def _low_confidence_boost(hyps: list[HypWord]) -> float:
    """Severity boost from Whisper's own uncertainty about the heard words."""
    probs = [h.probability for h in hyps if h.probability is not None]
    if not probs:
        return 0.0
    return max(0.0, (0.6 - min(probs))) * 0.8  # low prob (<0.6) adds up to ~0.48


def _context_snippet(text: str, offset: int, width: int = 40) -> str:
    lo, hi = max(0, offset - width), offset + width
    return re.sub(r"\s+", " ", text[lo:hi]).strip()


def _canon_tokens(exp: list[Token]) -> list[Token]:
    """Collapse number runs into one canonical '#<value>' token so a digit and
    its spoken word form ('250' vs 'two hundred fifty') align as identical."""
    norms, out, i = [t.norm for t in exp], [], 0
    while i < len(exp):
        val, j = _scan_number(norms, i)
        if val is not None:
            group = exp[i:j]
            out.append(Token(" ".join(t.original for t in group), f"#{val}", group[0].start))
            i = j
        else:
            out.append(exp[i])
            i += 1
    return out


def _canon_hyps(hyp: list[HypWord]) -> list[HypWord]:
    """Number-canonicalize heard words, preserving the merged audio timespan."""
    norms, out, i = [h.norm for h in hyp], [], 0
    while i < len(hyp):
        val, j = _scan_number(norms, i)
        if val is not None:
            g = hyp[i:j]
            probs = [h.probability for h in g if h.probability is not None]
            out.append(HypWord(f"#{val}", " ".join(h.original for h in g),
                               g[0].start, g[-1].end, min(probs) if probs else None))
            i = j
        else:
            out.append(hyp[i])
            i += 1
    return out


def _substitution_defects(exp, hyps, expected_text, n_exp) -> list[Defect]:
    """Expected words heard as different words. When the source and heard word
    counts match we emit one precise defect per word; otherwise the whole span
    is one garbled event, reported as a single grouped defect."""
    conf = _low_confidence_boost(hyps)
    if len(exp) == len(hyps):
        out = [_one_sub(tok, h, expected_text, n_exp, conf) for tok, h in zip(exp, hyps)]
        return [d for d in out if d]
    d = _grouped_sub(exp, hyps, expected_text, n_exp, conf)
    return [d] if d else []


def _span(hyps) -> tuple:
    """(start, end) audio timestamps spanning a group of heard words."""
    ts0 = next((h.start for h in hyps if h.start is not None), None)
    ts1 = next((h.end for h in reversed(hyps) if h.end is not None), None)
    return ts0, ts1


def _boundary(tok: Token, n_exp: int) -> bool:
    return tok.start == 0 or (tok.start + len(tok.original)) >= n_exp


def _one_sub(tok: Token, h: HypWord, expected_text, n_exp, conf) -> Optional[Defect]:
    """A single expected word aligned 1:1 to a single heard word."""
    exp_num, mate_num = _numeric_value(tok.norm), _numeric_value(h.norm)
    if exp_num is not None and exp_num == mate_num:
        return None  # digit correctly spoken as its word form
    if _is_letter_reading(tok.norm, h.norm):
        return None  # single letter correctly spoken as its name ("C" -> "see")
    pdist = phonetic_distance(tok.norm, h.norm)
    if pdist == 0.0 and conf < 0.2:
        return None  # confident homophone -> benign
    return Defect(
        kind="substitution", expected=tok.original, heard=h.original or "∅",
        severity=min(1.0, pdist * 0.7 + conf), causes=_causes_for(tok, _boundary(tok, n_exp)),
        audio_start=h.start, audio_end=h.end,
        context=_context_snippet(expected_text, tok.start),
    )


def _grouped_sub(exp, hyps, expected_text, n_exp, conf) -> Optional[Defect]:
    """A run of source words garbled into a differently-sized run of heard words."""
    exp_phrase = " ".join(t.norm for t in exp)
    heard_phrase = " ".join(h.norm for h in hyps)
    pdist = phonetic_distance(exp_phrase.replace(" ", ""), heard_phrase.replace(" ", ""))
    if pdist == 0.0 and conf < 0.2:
        return None
    ts0, ts1 = _span(hyps)
    causes = sorted({c for t in exp for c in _causes_for(t, _boundary(t, n_exp))})
    return Defect(
        kind="substitution", expected=" ".join(t.original for t in exp),
        heard=" ".join(h.original for h in hyps) or "∅",
        severity=min(1.0, pdist * 0.7 + conf), causes=causes,
        audio_start=ts0, audio_end=ts1,
        context=_context_snippet(expected_text, exp[0].start),
    )


def _omission_defect(exp, expected_text, n_exp, near_ts) -> Optional[Defect]:
    """Expected words with no matching audio (dropped by TTS)."""
    content = [t for t in exp if t.norm not in _STOPWORDS]
    if not content:
        return None
    tok = content[0]
    boundary = tok.start == 0 or (tok.start + len(tok.original)) >= n_exp
    return Defect(
        kind="omission", expected=" ".join(t.original for t in exp), heard="∅",
        severity=0.5 + (0.2 if len(content) > 1 else 0.0),
        causes=_causes_for(tok, boundary), audio_start=near_ts, audio_end=near_ts,
        context=_context_snippet(expected_text, tok.start),
    )


def detect_defects(expected_text: str, rich: dict) -> list[Defect]:
    """Align chunk source text against its rich STT result and return defects,
    sorted most-severe first."""
    exp = _canon_tokens(tokenize(expected_text))
    hyp = _canon_hyps(_build_hyp_words(rich))
    n_exp = len(expected_text)
    matcher = SequenceMatcher(None, [t.norm for t in exp], [h.norm for h in hyp])
    defects: list[Defect] = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        if tag == "replace":
            defects.extend(_substitution_defects(exp[i1:i2], hyp[j1:j2], expected_text, n_exp))
        elif tag == "delete":
            near = next((h.start for h in hyp[j1:j1 + 1]), None)
            d = _omission_defect(exp[i1:i2], expected_text, n_exp, near)
            if d:
                defects.append(d)
        # insertions (extra audio words) are almost always benign STT noise; skip.

    defects.extend(_confidence_defects(rich, expected_text, defects))
    defects.sort(key=lambda d: d.severity, reverse=True)
    return defects


def _confidence_defects(rich: dict, expected_text: str, existing: list[Defect]) -> list[Defect]:
    """Flag whole segments Whisper transcribed with low confidence, even where
    the words happened to still align (catches muddy audio the alignment missed)."""
    covered = {round(d.audio_start, 1) for d in existing if d.audio_start is not None}
    out = []
    for seg in rich.get("segments") or []:
        logprob, cratio = seg.get("avg_logprob"), seg.get("compression_ratio")
        bad_logprob = logprob is not None and logprob < LOW_LOGPROB
        bad_ratio = cratio is not None and cratio > HIGH_COMPRESSION
        if not (bad_logprob or bad_ratio):
            continue
        start = seg.get("start")
        if start is not None and round(start, 1) in covered:
            continue  # already reported via a word-level defect here
        sev = 0.5 + (min(0.4, (LOW_LOGPROB - logprob)) if bad_logprob else 0.2)
        out.append(Defect(
            kind="low_confidence", expected="(segment)", heard=seg.get("text", ""),
            severity=min(1.0, sev), causes=["muddy_audio"],
            audio_start=start, audio_end=seg.get("end"),
            context=seg.get("text", ""),
        ))
    return out


def _content_tokens(text: str) -> set:
    """Non-stopword source tokens used to match a defect across STT passes."""
    return {t.norm for t in tokenize(text) if t.norm not in _STOPWORDS} or {
        t.norm for t in tokenize(text)
    }


def _windows_overlap(a_start, a_end, windows) -> bool:
    """True if [a_start, a_end] overlaps any (start, end) window (0.5s tolerance)."""
    if a_start is None:
        return False
    a_end = a_end if a_end is not None else a_start
    for b_start, b_end in windows:
        if b_start is None:
            continue
        b_end = b_end if b_end is not None else b_start
        if a_start - 0.5 <= b_end and b_start - 0.5 <= a_end:
            return True
    return False


def confirm_defects(base_defects: list[Defect], expected_text: str, confirm_rich: dict) -> list[Defect]:
    """Second stage: keep only base-model defects a stronger STT pass agrees on.

    Runs detection on the confirmation transcript and returns those confirmed
    defects that overlap a base-flagged word (or, for low-confidence regions, a
    base-flagged time window). A base defect the stronger model doesn't reproduce
    was the base model's own STT error and is dropped. The returned defects carry
    the more accurate model's heard text and severity.
    """
    if not base_defects:
        return []
    confirm = detect_defects(expected_text, confirm_rich)
    base_words = set().union(*(_content_tokens(d.expected) for d in base_defects))
    base_windows = [(d.audio_start, d.audio_end) for d in base_defects]

    kept = []
    for c in confirm:
        if c.kind == "low_confidence":
            if _windows_overlap(c.audio_start, c.audio_end, base_windows):
                kept.append(c)
        elif _content_tokens(c.expected) & base_words:
            kept.append(c)
    return kept

