#!/usr/bin/env python3
"""Build the before/after dataset for the report's second tab from rechunk_test.json.

For each chunk the rechunk/rebuild test fully fixed (control babbled, fix clean on
all reps) this makes a focused mp3 of the SHIPPED audio (before, babbling) and of the
REBUILT audio (after, clean), computes the aggregate rate reduction, and lists the
residual chunks the fix did not resolve. Output: logs/beforeafter_data.json.

  ./venv311/bin/python scripts/build_beforeafter.py [--max-cards 24]
"""
import argparse
import base64
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

TEST = ROOT / "logs" / "rechunk_test.json"
CAPTURE = ROOT / "logs" / "residual_capture.json"  # optional post-fix babble audio
OUT = ROOT / "logs" / "beforeafter_data.json"
PAD_S = 2.8


def _clip_b64(wav_path, position, window=True):
    from pydub import AudioSegment
    audio = AudioSegment.from_wav(str(wav_path)).set_channels(1).set_frame_rate(22050)
    if window:
        dur = len(audio)
        center = (position or 0.5) * dur
        lo = max(0, int(center - PAD_S * 1000))
        hi = min(dur, int(center + PAD_S * 1000))
        if hi - lo < 3500:
            lo, hi = 0, dur
        audio = audio[lo:hi]
    buf = io.BytesIO()
    audio.export(buf, format="mp3", bitrate="48k")
    return base64.b64encode(buf.getvalue()).decode()


def _classify_residual(r):
    """Rough bucket for why the fix didn't remove this one — to guide listening."""
    pos = r.get("position") or 0
    last = (r["new_texts"][-1].rstrip().split() or [""])[-1].strip('.,!?"\'’”')
    if pos >= 0.8 and last[:1].isupper():
        return "trailing proper noun"
    if pos >= 0.85:
        return "chunk-end"
    if pos <= 0.2:
        return "chunk-start"
    return "mid-chunk"


def _mark_babble(text, position):
    """Drop a ⟨babble⟩ marker at the approximate position in the new chunk text."""
    if position is None:
        return text
    text = text.rstrip()
    i = max(0, min(len(text), int(position * len(text))))
    j = text.find(" ", i)
    if j == -1 or len(text) - i <= 12:
        return text + " ⟨▓⟩"
    return text[:j] + " ⟨▓⟩" + text[j:]


def _residual_entry(r, reps, capture):
    """Rich residual record: diagnostics + audio (post-fix capture if available)."""
    new_joined = " ⟂ ".join(r["new_texts"]) if r["n_new"] > 1 else r["new_texts"][0]
    cap = capture.get(f"{r['book']}_{r['chapter']}_{r['chunk']}")
    reproduced = None
    if cap and Path(cap["wav"]).exists():
        clip = _clip_b64(cap["wav"], cap.get("position", r["position"]))
        source, heard = "post-fix rebuild", cap.get("phones", r["phones"])
        reproduced = cap.get("reproduced", True)
    else:
        clip = _clip_b64(r["shipped_wav"], r["position"])
        source, heard = "pre-fix shipped", r["phones"]
    return {
        "book": r["book"], "chapter": r["chapter"], "chunk": r["chunk"],
        "tier": r["tier"], "phones": heard, "position": r.get("position"),
        "fix_hits": r["fix_hits"], "reps": reps, "n_new": r["n_new"],
        "kind": _classify_residual(r), "reproduced": reproduced,
        "new_text": _mark_babble(new_joined, r.get("position")),
        "audio": clip, "audio_source": source,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--max-cards", type=int, default=24)
    args = ap.parse_args()

    data = json.loads(TEST.read_text())
    results = data["results"]
    reps = data["reps"]
    capture = json.loads(CAPTURE.read_text()) if CAPTURE.exists() else {}
    n = len(results)
    c_total = sum(r["control_hits"] for r in results)
    f_total = sum(r["fix_hits"] for r in results)
    denom = n * reps

    fixed = [r for r in results if r["fixed"] and r.get("after_wav")]
    fixed.sort(key=lambda r: (-r["control_hits"], -r.get("control_worst", 0)))
    residual = sorted((r for r in results if r["fix_hits"] > 0),
                      key=lambda r: -r["fix_hits"])

    cases = []
    for r in fixed[:args.max_cards]:
        cases.append({
            "book": r["book"], "chapter": r["chapter"], "chunk": r["chunk"],
            "tier": r["tier"], "phones": r["phones"], "old_text": r["old_text"],
            "n_new": r["n_new"], "control_hits": r["control_hits"], "reps": reps,
            "before_mp3": _clip_b64(r["shipped_wav"], r["position"]),
            "after_mp3": _clip_b64(r["after_wav"], r["position"]),
        })
        print(f"  card b{r['book']}/ch{r['chapter']}/{r['chunk']:03d} "
              f"control {r['control_hits']}/{reps}", flush=True)

    out = {
        "summary": {
            "n": n, "reps": reps,
            "control_rate_pct": round(100 * c_total / denom, 1) if denom else 0,
            "fix_rate_pct": round(100 * f_total / denom, 1) if denom else 0,
            "reduction_pct": round(100 * (c_total - f_total) / c_total) if c_total else 0,
            "fixed": sum(1 for r in results if r["fixed"]),
        },
        "cases": cases,
        "residual": [_residual_entry(r, reps, capture) for r in residual],
    }
    OUT.write_text(json.dumps(out, indent=2))
    captured = sum(1 for x in out["residual"] if x["audio_source"] == "post-fix rebuild")
    print(f"\nWrote {OUT} — {len(cases)} cards, {len(out['residual'])} residual "
          f"({captured} with post-fix audio), reduction {out['summary']['reduction_pct']}% "
          f"({OUT.stat().st_size//1024} KB)")


if __name__ == "__main__":
    main()
