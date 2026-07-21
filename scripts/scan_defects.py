#!/usr/bin/env python3
"""Scan generated chunk audio for likely TTS defects using Whisper STT.

For every chunk that has both source text and a rendered .wav, this transcribes
the audio with word timestamps + confidence, aligns it against the source at word
level, and reports suspected mangles: the expected word, what the audio actually
said, an audio timestamp to listen at, a severity, and a best-guess cause.

Run inside the TTS venv (has whisper + jellyfish):
  ./venv311/bin/python scripts/scan_defects.py                 # all chapters w/ audio
  ./venv311/bin/python scripts/scan_defects.py 124774 7 8      # one chapter
  ./venv311/bin/python scripts/scan_defects.py --min-severity 0.5 --limit 40
  ./venv311/bin/python scripts/scan_defects.py --json report.json
"""
import argparse
import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
BACKEND = SCRIPTS.parent / "backend"
sys.path.insert(0, str(BACKEND))

from src.config import get_settings  # noqa: E402
from src.discovery import ChunkDiscovery  # noqa: E402
from src.validation.defects import confirm_defects, detect_defects, tokenize  # noqa: E402
from src.validation.stt import get_stt_service  # noqa: E402


def _iter_chapters(books_dir: Path, only: tuple | None):
    """Yield (fiction_id, book, chapter) for chapter dirs that contain chunk wavs."""
    if only:
        yield only
        return
    for chunks_dir in sorted(books_dir.glob("*/book_*/chapters/chapter_*/chunks")):
        if not any(chunks_dir.glob("*.wav")):
            continue
        chapter = chunks_dir.parent
        fiction_id = chapter.parents[2].name
        book = int(chapter.parents[1].name.split("_")[1])
        ch = int(chapter.name.split("_")[1])
        yield fiction_id, book, ch


def _chunk_defects(chunk, base_stt, confirm_stt):
    """Two-stage detection for one chunk: cheap base pre-filter, then (only if it
    flagged anything) a stronger model confirms. Returns the surviving defects."""
    base_rich = base_stt.transcribe_rich(chunk.audio_path)
    if not base_rich:
        return []
    base = detect_defects(chunk.text, base_rich)
    if not base or confirm_stt is None:
        return base
    confirm_rich = confirm_stt.transcribe_rich(chunk.audio_path)
    if not confirm_rich:
        return base  # can't confirm -> keep base defects rather than lose signal
    return confirm_defects(base, chunk.text, confirm_rich)


def _content_words(expected: str) -> list[str]:
    """Distinct content words in a defect's expected text, for phoneme triage."""
    if expected.startswith("("):  # e.g. "(segment)" low-confidence markers
        return []
    seen, words = set(), []
    for tok in tokenize(expected):
        if tok.norm not in seen and not tok.norm.startswith("#"):
            seen.add(tok.norm)
            words.append(tok.original)
    return words


def _triage(chunk, defects, recognizer):
    """Attach a phoneme verdict (xtts-fault vs whisper-fault) to each defect by
    comparing the audio's phones at each defect word against its G2P."""
    from src.validation.phonemes import chunk_word_verdicts, detect_hallucinations
    if not defects:
        return {}, []
    phones = recognizer.recognize_wav(chunk.audio_path)
    annotations = {}
    for i, d in enumerate(defects):
        verdicts = chunk_word_verdicts(chunk.text, phones, targets=_content_words(d.expected))
        if verdicts:
            worst = max(verdicts, key=lambda v: v["distance"])
            annotations[i] = {"phoneme_source": worst["source"],
                              "phoneme_distance": worst["distance"],
                              "actual_phones": worst["actual_phones"],
                              "expected_phones": worst["expected_phones"]}
    # Hallucinated outbursts — audio phones with no source text. Detected here for
    # free (phones already computed); more disruptive than subtle mispronunciations.
    hallucinations = detect_hallucinations(chunk.text, phones)
    return annotations, hallucinations


def _scan_chapter(fiction_id, book, ch, base_stt, confirm_stt, discovery, min_sev, recognizer):
    """Transcribe + analyze every rendered chunk in one chapter."""
    findings = []
    chunks = [c for c in discovery.list_chunks(fiction_id, book, ch) if c.has_audio]
    for chunk in chunks:
        defects = [d for d in _chunk_defects(chunk, base_stt, confirm_stt) if d.severity >= min_sev]
        annotations, hallucinations = _triage(chunk, defects, recognizer) if recognizer else ({}, [])
        base = {"fiction_id": fiction_id, "book": book, "chapter": ch,
                "chunk": chunk.index, "wav": str(chunk.audio_path)}
        for i, d in enumerate(defects):
            findings.append({**base, **d.to_dict(), **annotations.get(i, {})})
        for h in hallucinations:
            if h["severity"] >= min_sev:
                findings.append({**base, "kind": "hallucination", "expected": "(no text)",
                                 "heard": f"/{h['phones']}/", "severity": h["severity"],
                                 "causes": ["hallucinated_outburst"], "audio_start": None,
                                 "audio_end": None, "context": "",
                                 "phoneme_source": "xtts", "phoneme_distance": None,
                                 "actual_phones": h["phones"], "position": h["position"]})
    return findings, len(chunks)


def _print_report(findings, limit):
    if not findings:
        print("\n✓ No defects above threshold.")
        return
    findings.sort(key=lambda f: f["severity"], reverse=True)
    print(f"\nTop {min(limit, len(findings))} of {len(findings)} suspected defects:\n")
    for f in findings[:limit]:
        ts = f"{f['audio_start']:.1f}s" if f["audio_start"] is not None else "?"
        loc = f"b{f['book']}/ch{f['chapter']}/chunk{f['chunk']:03d} @ {ts}"
        causes = ", ".join(f["causes"]) or "—"
        src = f"  [{f['phoneme_source']}, phon={f['phoneme_distance']:.2f}]" if "phoneme_source" in f else ""
        print(f"[{f['severity']:.2f}] {loc}  ({f['kind']}; {causes}){src}")
        print(f"        expected: {f['expected']!r}")
        print(f"        heard:    {f['heard']!r}")
        print(f"        context:  …{f['context']}…\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("target", nargs="*", help="fiction_id book chapter (default: all)")
    ap.add_argument("--min-severity", type=float, default=0.35)
    ap.add_argument("--limit", type=int, default=50, help="max rows to print")
    ap.add_argument("--json", type=Path, help="write full findings to this file")
    ap.add_argument("--confirm-model", default=None,
                    help="stronger model to confirm flagged chunks (default: config; "
                         "'none' for single-pass base only)")
    ap.add_argument("--phoneme-triage", action="store_true",
                    help="classify each defect as xtts-fault vs whisper-fault via phonemes")
    args = ap.parse_args()

    only = None
    if args.target:
        if len(args.target) != 3:
            ap.error("target must be exactly: fiction_id book chapter")
        only = (args.target[0], int(args.target[1]), int(args.target[2]))

    settings = get_settings()
    base_stt = get_stt_service()
    confirm_name = args.confirm_model or settings.whisper_confirm_model
    confirm_stt = None if confirm_name.lower() == "none" else get_stt_service(confirm_name)
    discovery = ChunkDiscovery()

    recognizer = None
    if args.phoneme_triage:
        from src.validation.phonemes import get_phoneme_recognizer
        recognizer = get_phoneme_recognizer()

    stage = "single-pass" if confirm_stt is None else f"{settings.whisper_model}→{confirm_name}"
    triage = " +phoneme-triage" if recognizer else ""
    print(f"Defect scan ({stage}{triage})")

    all_findings, chapters, chunks = [], 0, 0
    for fiction_id, book, ch in _iter_chapters(settings.books_dir, only):
        chapters += 1
        print(f"Scanning {fiction_id} book {book} chapter {ch} …", flush=True)
        found, n = _scan_chapter(fiction_id, book, ch, base_stt, confirm_stt,
                                 discovery, args.min_severity, recognizer)
        chunks += n
        all_findings.extend(found)

    print(f"\nScanned {chapters} chapter(s), {chunks} chunk(s) with audio.")
    if recognizer:
        xtts = sum(1 for f in all_findings if f.get("phoneme_source") == "xtts")
        whisper = sum(1 for f in all_findings if f.get("phoneme_source") == "whisper")
        print(f"Phoneme triage: {xtts} real XTTS-fault, {whisper} Whisper-fault "
              f"(audio OK), {len(all_findings) - xtts - whisper} unclassified.")
    _print_report(all_findings, args.limit)

    if args.json:
        args.json.write_text(json.dumps(all_findings, indent=2))
        print(f"Wrote {len(all_findings)} findings to {args.json}")


if __name__ == "__main__":
    main()
