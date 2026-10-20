#!/usr/bin/env python3
"""Score a rendered chapter: word recall, speaker similarity, pace and early stops.

Three steps, because the models live in different venvs:

  stt      Whisper (small.en) transcribes every chunk wav to a jsonl. Any venv
           with openai-whisper; GPU if there is one.
  consist  ECAPA speaker similarity to a reference wav, duration, LUFS and
           full-scale samples per chunk. A venv with speechbrain, librosa and
           pyloudnorm; CPU is enough.
  report   Chapter-wide numbers from the two jsonls, the chunk texts and the
           chapter's normalized.txt. The main venv.

Recall is aligned chapter-wide against normalized.txt, so a different chunking
scores on the same footing, and a word one chunk drops is not found in its
neighbour. Similarity is weighted by duration, so a long chunk counts for more
than a one-word line.

  python scripts/score_chapter.py stt CHUNKS_DIR OUT.jsonl
  python scripts/score_chapter.py consist CHUNKS_DIR REF.wav ECAPA_DIR OUT.jsonl
  python scripts/score_chapter.py report CHUNKS_DIR NORMALIZED.txt STT.jsonl CONSIST.jsonl
"""
import argparse
import difflib
import json
import re
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOW = 0.8
# A full-scale sample: the renderer clips after loudness normalisation.
FULL_SCALE = 0.999
CALIBRATION_MARGIN = 1.10


def words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _hits(ref: list[str], hyp: list[str]) -> list[bool]:
    """Which reference words the hypothesis contains, in order."""
    hit = [False] * len(ref)
    for block in difflib.SequenceMatcher(None, ref, hyp, autojunk=False).get_matching_blocks():
        hit[block.a:block.a + block.size] = [True] * block.size
    return hit


def _chunk_spans(ref: list[str], chunk_texts: list[str]) -> list[tuple[int, int]]:
    """Each chunk's [start, end) in the reference words, via an alignment of the chunk words.

    The chunk texts come from the reference, but the chunker may tidy a word or
    two, so positions are mapped rather than counted.
    """
    owner, flat = [], []
    for i, text in enumerate(chunk_texts):
        w = words(text)
        flat += w
        owner += [i] * len(w)
    spans = [[len(ref), 0] for _ in chunk_texts]
    for block in difflib.SequenceMatcher(None, flat, ref, autojunk=False).get_matching_blocks():
        for k in range(block.size):
            span = spans[owner[block.a + k]]
            span[0] = min(span[0], block.b + k)
            span[1] = max(span[1], block.b + k + 1)
    return [(s, e) if e > s else (0, 0) for s, e in spans]


def recall_report(ref_text: str, chunk_texts: list[str], hyps: list[str], tail_words: int = 3) -> dict:
    """Chapter-wide word recall, and the chunks that lose words, split by where they lose them."""
    ref = words(ref_text)
    hit = _hits(ref, [w for h in hyps for w in words(h)])
    low, tail = [], []
    for i, (start, end) in enumerate(_chunk_spans(ref, chunk_texts)):
        if end == start:
            continue
        if sum(hit[start:end]) / (end - start) < LOW:
            low.append(i)
            if not any(hit[max(start, end - tail_words):end]):
                tail.append(i)
    return {
        "chapter_word_recall": round(sum(hit) / max(len(ref), 1), 4),
        "chunks_recall_lt_0.8": low,
        "chunks_missing_tail": tail,
    }


def duration_weighted_sim(rows: list[dict]) -> float:
    total = sum(r["dur_s"] for r in rows)
    return sum(r["sim"] * r["dur_s"] for r in rows) / total


def pace_report(texts: list[str], durations: list[float], profile) -> dict:
    """Letters/s over the guarded chunks, early stops under `profile`, and a recalibrated threshold."""
    sys.path.insert(0, str(ROOT / "backend"))
    from src.tts.early_stop import early_stop_shortfall, spoken_letters

    speech = [d - profile.trailing_pad_s for d in durations]
    rates = sorted(
        spoken_letters(t) / s for t, s in zip(texts, speech) if spoken_letters(t) >= profile.min_letters
    )
    flagged = [
        i for i, (t, s) in enumerate(zip(texts, speech))
        if early_stop_shortfall(t, s, profile.max_letters_per_sec, profile.min_letters) is not None
    ]
    return {
        "guarded_chunks": len(rates),
        "letters_per_s": {
            "median": round(statistics.median(rates), 2),
            "p99": round(rates[min(len(rates) - 1, int(0.99 * len(rates)))], 2),
            "max": round(rates[-1], 2),
        },
        "early_stops": flagged,
        "recalibrated_max_letters_per_sec": round(rates[-1] * CALIBRATION_MARGIN, 1),
    }


def _load(path: Path) -> list[dict]:
    return sorted((json.loads(line) for line in path.open()), key=lambda r: r["chunk"])


def _wavs(chunks_dir: Path) -> list[Path]:
    return sorted(Path(chunks_dir).glob("[0-9]*.wav"))


def cmd_stt(args):
    import whisper

    model = whisper.load_model(args.model, device=args.device)
    with open(args.out, "w") as out:
        for wav in _wavs(args.chunks_dir):
            ref = words(wav.with_suffix(".txt").read_text())
            result = model.transcribe(str(wav), language="en", fp16=args.device == "cuda",
                                      condition_on_previous_text=False)
            hyp = words(result["text"])
            hit = sum(_hits(ref, hyp))
            out.write(json.dumps({
                "chunk": wav.stem, "ref_words": len(ref), "hyp_words": len(hyp),
                "recall": round(hit / max(len(ref), 1), 3),
                "precision": round(hit / max(len(hyp), 1), 3), "hyp": " ".join(hyp),
            }) + "\n")


def cmd_consist(args):
    import librosa
    import numpy as np
    import pyloudnorm
    import torch
    from speechbrain.inference.speaker import EncoderClassifier

    enc = EncoderClassifier.from_hparams("speechbrain/spkrec-ecapa-voxceleb", savedir=str(args.ecapa_dir))

    def embed(y16):
        e = enc.encode_batch(torch.from_numpy(y16).unsqueeze(0)).squeeze().numpy()
        return e / np.linalg.norm(e)

    ref = embed(librosa.load(str(args.ref), sr=16000)[0])
    with open(args.out, "w") as out:
        for wav in _wavs(args.chunks_dir):
            y, sr = librosa.load(str(wav), sr=None)
            lufs = pyloudnorm.Meter(sr).integrated_loudness(y) if len(y) > sr // 2 else None
            out.write(json.dumps({
                "chunk": wav.stem, "dur_s": round(len(y) / sr, 3),
                "sim": round(float(embed(librosa.resample(y, orig_sr=sr, target_sr=16000)) @ ref), 4),
                "lufs": lufs, "full_scale_samples": int((np.abs(y) >= FULL_SCALE).sum()),
            }) + "\n")


def cmd_report(args):
    sys.path.insert(0, str(ROOT / "backend"))
    from src.tts.profiles import P4

    stt, con = _load(args.stt), _load(args.consist)
    texts = [(Path(args.chunks_dir) / f"{r['chunk']}.txt").read_text() for r in con]
    report = {"chunks": len(con), **recall_report(args.normalized.read_text(), texts, [r["hyp"] for r in stt])}
    report["chunks_precision_lt_0.8"] = [i for i, r in enumerate(stt) if r["precision"] < LOW]
    report["sim_dur_weighted"] = round(duration_weighted_sim(con), 4)
    report["audio_min"] = round(sum(r["dur_s"] for r in con) / 60, 1)
    report["chunks_full_scale"] = [i for i, r in enumerate(con) if r["full_scale_samples"]]
    report.update(pace_report(texts, [r["dur_s"] for r in con], P4))
    stems = [r["chunk"] for r in con]
    for key in ("chunks_recall_lt_0.8", "chunks_missing_tail", "chunks_precision_lt_0.8",
                "chunks_full_scale", "early_stops"):
        report[key] = [stems[i] for i in report[key]]
    print(json.dumps(report, indent=2))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    stt = sub.add_parser("stt")
    stt.add_argument("chunks_dir", type=Path)
    stt.add_argument("out", type=Path)
    stt.add_argument("--model", default="small.en")
    stt.add_argument("--device", default="cuda")
    consist = sub.add_parser("consist")
    for name in ("chunks_dir", "ref", "ecapa_dir", "out"):
        consist.add_argument(name, type=Path)
    report = sub.add_parser("report")
    for name in ("chunks_dir", "normalized", "stt", "consist"):
        report.add_argument(name, type=Path)
    args = ap.parse_args()
    {"stt": cmd_stt, "consist": cmd_consist, "report": cmd_report}[args.cmd](args)


if __name__ == "__main__":
    main()
