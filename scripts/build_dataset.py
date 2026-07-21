#!/usr/bin/env python3
"""Aggregate the phoneme-triage audit JSONs into a labeled test set + issue-rate docs.

Consumes logs/audit/b{book}_ch{ch}.json (output of
`scan_defects.py --phoneme-triage`) and produces:
  data/test_set/tts_defects.jsonl   one labeled record per confirmed defect
  data/test_set/chunk_labels.jsonl  per chunk: bad (real XTTS fault) / flagged-ok / clean
  docs/tts_issue_rates.md           human-readable issue-rate documentation

Labels come from the two-phase (base→small) detector plus the phoneme verdict:
  phoneme_source=xtts   -> genuine mispronunciation (BAD audio)
  phoneme_source=whisper-> audio correct, Whisper misread (FLAGGED-OK)
Runs on whatever audit JSONs exist, so it can be re-run as chapters complete.
"""
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AUDIT = ROOT / "logs" / "audit"
OUT = ROOT / "data" / "test_set"
DOCS = ROOT / "docs"


def _chapter_key(path: Path):
    # b7_ch8.json -> (7, 8)
    stem = path.stem  # b7_ch8
    book = int(stem.split("_")[0][1:])
    ch = int(stem.split("ch")[1])
    return book, ch


def _chunk_audio_count(fid, book, ch):
    d = ROOT / "data" / "books" / fid / f"book_{book}" / "chapters" / f"chapter_{ch}" / "chunks"
    return len(list(d.glob("*.wav"))) if d.exists() else 0


def main():
    files = sorted(AUDIT.glob("b*_ch*.json"))
    if not files:
        print("No audit JSONs yet in logs/audit/. Run the audit first.")
        return
    OUT.mkdir(parents=True, exist_ok=True)
    DOCS.mkdir(parents=True, exist_ok=True)

    defect_rows, chunk_rows, per_ch = [], [], []
    tot = Counter()
    cause_by_source = defaultdict(Counter)

    for f in files:
        book, ch = _chapter_key(f)
        findings = json.loads(f.read_text())
        fid = findings[0]["fiction_id"] if findings else "124774"
        n_chunks = _chunk_audio_count(fid, book, ch)

        by_chunk_src = defaultdict(set)
        xtts = whisper = 0
        for d in findings:
            src = d.get("phoneme_source", "unclassified")
            by_chunk_src[d["chunk"]].add(src)
            if src == "xtts":
                xtts += 1
            elif src == "whisper":
                whisper += 1
            for c in (d.get("causes") or ["(none)"]):
                cause_by_source[src][c] += 1
            defect_rows.append({
                "book": book, "chapter": ch, "chunk": d["chunk"],
                "expected": d["expected"], "whisper_heard": d["heard"],
                "severity": d["severity"], "phoneme_source": src,
                "phoneme_distance": d.get("phoneme_distance"),
                "expected_phones": d.get("expected_phones"),
                "actual_phones": d.get("actual_phones"),
                "causes": d.get("causes"), "wav": d["wav"],
                "label": "bad" if src == "xtts" else "flagged_ok",
            })

        bad_chunks = {c for c, s in by_chunk_src.items() if "xtts" in s}
        flagged_ok = {c for c, s in by_chunk_src.items() if "xtts" not in s}
        for c in bad_chunks:
            chunk_rows.append({"book": book, "chapter": ch, "chunk": c, "label": "bad"})
        for c in flagged_ok:
            chunk_rows.append({"book": book, "chapter": ch, "chunk": c, "label": "flagged_ok"})

        per_ch.append({
            "book": book, "chapter": ch, "chunks": n_chunks,
            "confirmed_defects": len(findings), "xtts_fault": xtts,
            "whisper_fault": whisper, "bad_chunks": len(bad_chunks),
            "issue_rate_pct": round(100 * len(bad_chunks) / n_chunks, 2) if n_chunks else None,
        })
        tot["chunks"] += n_chunks
        tot["defects"] += len(findings)
        tot["xtts"] += xtts
        tot["whisper"] += whisper
        tot["bad_chunks"] += len(bad_chunks)

    _write_jsonl(OUT / "tts_defects.jsonl", defect_rows)
    _write_jsonl(OUT / "chunk_labels.jsonl", chunk_rows)
    _write_docs(per_ch, tot, cause_by_source)
    print(f"Test set: {len(defect_rows)} labeled defects, {len(chunk_rows)} labeled chunks "
          f"across {len(files)} chapter(s).")
    print(f"  bad(xtts)={tot['xtts']}  flagged-ok(whisper)={tot['whisper']}  "
          f"chunks={tot['chunks']}  bad-chunk rate="
          f"{100*tot['bad_chunks']/tot['chunks']:.2f}%" if tot['chunks'] else "")
    print(f"Wrote {OUT}/ and {DOCS/'tts_issue_rates.md'}")


def _write_jsonl(path, rows):
    path.write_text("\n".join(json.dumps(r) for r in rows) + ("\n" if rows else ""))


def _hallucination_section():
    """Hallucinated-outburst rate from the wide phoneme sweep, if it has been run."""
    filtered = ROOT / "logs" / "hallucinations_filtered.json"
    if not filtered.exists():
        return []
    d = json.loads(filtered.read_text())
    t = d["tiers"]
    kept = d["kept"]
    return [
        "", "## Hallucinated outbursts",
        "",
        "A separate, arguably more disruptive defect: phantom audio the TTS injects "
        "with no matching text (phantom words, babble, drum-vocalisation), found by "
        "`scan_hallucinations.py` (phoneme-alignment insertions across every chunk) and "
        "tightened by `filter_hallucinations.py` into confidence tiers.",
        "",
        f"- Raw injected-phoneme findings: **{d['raw']}**",
        f"- Confirmed / likely (kept): **{kept}** — a **{100*kept/2422:.2f}%** chunk rate "
        "(on par with the mispronunciation rate; often more jarring to hear).",
        f"- Tiers: confirmed {t.get('confirmed',0)}, likely {t.get('likely',0)}, "
        f"borderline {t.get('borderline',0)}, probable-FP {t.get('probable_fp',0)}.",
        "",
        "Main causes (from the sweep): mid-chunk `.\"\\n\\n` paragraph boundaries "
        "(fixed — chunker now splits paragraphs), trailing chunk-end fragments/quotes "
        "(~half of cases — candidate next fix), and onomatopoeia rendering.",
    ]


def _write_docs(per_ch, tot, cause_by_source):
    xtts, whisper = tot["xtts"], tot["whisper"]
    conf = tot["defects"] or 1
    lines = [
        "# TTS issue rates — phoneme-triaged audit",
        "",
        "Built by `scripts/build_dataset.py` from the two-phase (base→small Whisper) "
        "detector plus a phoneme verdict (espeak G2P vs wav2vec2 phones). Each confirmed "
        "defect is labeled **xtts** (genuine mispronunciation — bad audio) or **whisper** "
        "(audio correct, Whisper misread).",
        "",
        "## Headline",
        "",
        f"- Chapters audited: **{len(per_ch)}**  ·  chunks with audio: **{tot['chunks']}**",
        f"- Confirmed defects (post two-phase): **{tot['defects']}**",
        f"- Genuine XTTS mispronunciations: **{xtts}** ({100*xtts/conf:.0f}% of confirmed)",
        f"- Whisper misreads of correct audio: **{whisper}** ({100*whisper/conf:.0f}% of confirmed)",
        f"- Bad-audio chunk rate: **{100*tot['bad_chunks']/tot['chunks']:.2f}%** "
        f"({tot['bad_chunks']} of {tot['chunks']} chunks)" if tot["chunks"] else "",
        "",
        "> Most flagged \"mangles\" are Whisper's vocabulary limits, not TTS defects. "
        "The genuine-defect rate per chunk is the number that matters for quality.",
        "",
        "## Per chapter",
        "",
        "| Book | Ch | Chunks | Confirmed | XTTS-fault | Whisper-fault | Bad chunks | Issue rate |",
        "|-----:|---:|-------:|----------:|-----------:|--------------:|-----------:|-----------:|",
    ]
    for c in per_ch:
        lines.append(
            f"| {c['book']} | {c['chapter']} | {c['chunks']} | {c['confirmed_defects']} "
            f"| {c['xtts_fault']} | {c['whisper_fault']} | {c['bad_chunks']} "
            f"| {c['issue_rate_pct']}% |")
    lines += ["", "## Cause breakdown (genuine XTTS faults)", ""]
    for cause, n in cause_by_source.get("xtts", Counter()).most_common():
        lines.append(f"- `{cause}`: {n}")
    lines += _hallucination_section()
    lines += ["", "## Test-set files", "",
              "- `data/test_set/tts_defects.jsonl` — one labeled record per confirmed defect",
              "- `data/test_set/chunk_labels.jsonl` — per-chunk label (bad / flagged_ok)",
              "- `data/test_set/hallucinations.jsonl` — confirmed+likely hallucinated outbursts",
              "", "Labels are model-derived (phoneme verdict), suitable as a regression "
              "baseline for fix experiments — not hand-verified ground truth.",
              "",
              "## Known limitation",
              "",
              "The phoneme distance is a character-ratio (SequenceMatcher) over IPA strings, "
              "which is blind to same-length, same-position diphthong-class swaps (e.g. NAY→NYE "
              "in *Ghanaian*). So the XTTS-fault count is a mild **under**-count — some genuine "
              "mispronunciations score below the 0.45 threshold and land in *flagged_ok*. A "
              "phone-alignment-aware distance would tighten this. Treat the bad-chunk rate as a "
              "conservative floor.", ""]
    (DOCS / "tts_issue_rates.md").write_text("\n".join(l for l in lines if l is not None))


if __name__ == "__main__":
    main()
