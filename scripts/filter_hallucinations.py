#!/usr/bin/env python3
"""Post-filter the raw hallucination sweep into confidence tiers (the FP-tightening).

Operates purely on stored findings (logs/halluc/*.json) — no re-synthesis — so it is
cheap to tune and re-run. Each raw injected-phoneme finding is classified:

  confirmed    long run (>=8 phones) OR corroborated by Whisper hearing inserted words
  likely       6-7 phones, reliable-G2P text, not corroborated
  borderline   5 phones (near the noise floor)
  probable_fp  text espeak can't G2P (onomatopoeia / ALL-CAPS) so the "injection" is
               a G2P artifact, not real audio

--verify runs Whisper on the flagged chunks (cheap — only flagged ones) as an
independent oracle: a real outburst usually shows up as inserted words there too.

  ./venv311/bin/python scripts/filter_hallucinations.py [--verify]
"""
import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

from src.validation.defects import tokenize  # noqa: E402

HALLUC = BACKEND.parent / "logs" / "halluc"
OUT = BACKEND.parent / "logs" / "hallucinations_filtered.json"

_REPEATED = re.compile(r"([A-Za-z])\1\1")           # Dummm
_ALLCAPS = re.compile(r"\b[A-Z]{3,}\b")             # DUM
_HYPHEN_CHAIN = re.compile(r"(-[A-Za-z]{1,4}){2,}")  # dum-dum-dum


def _g2p_reliable(text: str) -> bool:
    """False when espeak can't faithfully G2P the text (onomatopoeia/caps), which
    makes any 'injection' a G2P artifact rather than real hallucinated audio."""
    return not (_REPEATED.search(text) or _ALLCAPS.search(text) or _HYPHEN_CHAIN.search(text))


def _whisper_insertion_chars(chunk_text, rich) -> int:
    """Chars of words Whisper INSERTED (aligned to no source position) — true
    insertions only, not substitutions, so clean chunks don't spuriously corroborate."""
    from difflib import SequenceMatcher
    exp = [t.norm for t in tokenize(chunk_text)]
    heard = [t.norm for w in rich.get("words", []) for t in tokenize(w.get("word", ""))]
    total = 0
    for tag, i1, i2, j1, j2 in SequenceMatcher(None, exp, heard).get_opcodes():
        if tag == "insert":
            total += sum(len(w) for w in heard[j1:j2] if len(w) >= 3)
    return total


def _classify(finding, corroborated=None):
    p = max(finding["phonetic"], key=lambda x: x["length"])
    # A long run is real babble regardless of the text — length overrides the
    # G2P-reliability check, so drum-vocalisation outbursts in onomatopoeia chunks
    # aren't wrongly dismissed as G2P artifacts.
    if p["length"] >= 10 or corroborated:
        return "confirmed", p
    if not _g2p_reliable(finding["text"]):
        return "probable_fp", p
    if p["length"] >= 8:
        return "confirmed", p
    if p["length"] >= 6:
        return "likely", p
    return "borderline", p


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--verify", action="store_true", help="Whisper cross-check on flagged chunks")
    args = ap.parse_args()

    files = sorted(HALLUC.glob("b*_ch*.json"))
    if not files:
        print("No sweep output in logs/halluc/ yet.")
        return
    findings = [f for path in files for f in json.loads(path.read_text()) if f["phonetic"]]

    stt = None
    if args.verify:
        from src.discovery import ChunkDiscovery
        from src.validation.stt import get_stt_service
        stt, disc = get_stt_service(), ChunkDiscovery()

    rows, tiers = [], Counter()
    for f in findings:
        corro = None
        if stt:
            chunk = disc.get_chunk("124774", f["book"], f["chapter"], f["chunk"])
            if chunk and chunk.has_audio:
                rich = stt.transcribe_rich(chunk.audio_path)
                corro = _whisper_insertion_chars(chunk.text, rich) >= 5
        tier, p = _classify(f, corro)
        tiers[tier] += 1
        rows.append({**{k: f[k] for k in ("book", "chapter", "chunk", "text")},
                     "phones": p["phones"], "length": p["length"], "position": p["position"],
                     "tier": tier, "whisper_corroborated": corro})

    real = tiers["confirmed"] + tiers["likely"]
    print(f"Raw injected-phoneme findings: {len(findings)}")
    for t in ("confirmed", "likely", "borderline", "probable_fp"):
        print(f"  {t:<12} {tiers[t]}")
    print(f"\nTightened (confirmed+likely): {real}  "
          f"({100*real/len(findings):.0f}% of raw kept)")

    # Per-chapter tightened rate + labeled dataset of the kept outbursts.
    kept = [r for r in rows if r["tier"] in ("confirmed", "likely")]
    per_ch = Counter((r["book"], r["chapter"]) for r in kept)
    books = BACKEND.parent / "data" / "books"
    print("\nPer chapter (tightened bad-audio-outburst rate):")
    total_chunks = 0
    for (book, ch), n in sorted(per_ch.items()):
        d = books / "124774" / f"book_{book}" / "chapters" / f"chapter_{ch}" / "chunks"
        nchunks = len(list(d.glob("*.wav"))) if d.exists() else 0
        total_chunks += nchunks
        rate = f"{100*n/nchunks:.2f}%" if nchunks else "?"
        print(f"  b{book}/ch{ch}: {n}/{nchunks} = {rate}")

    ds = BACKEND.parent / "data" / "test_set" / "hallucinations.jsonl"
    ds.write_text("\n".join(json.dumps(r) for r in kept) + "\n")
    OUT.write_text(json.dumps({"tiers": dict(tiers), "kept": real,
                               "raw": len(findings), "rows": rows}, indent=2))
    print(f"\nWrote {ds} ({len(kept)} labeled outbursts) and {OUT}")


if __name__ == "__main__":
    main()
