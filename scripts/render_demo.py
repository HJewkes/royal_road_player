#!/usr/bin/env python3
"""Render the self-contained before/after TTS-defect demo page from demo_data.json.

Produces demo/tts_defect_demo.html with all audio and data inlined, openable
directly via file:// — no server, no external requests.
"""
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "logs" / "demo_data.json"
OUT = ROOT / "demo" / "tts_defect_demo.html"

# Funnel numbers from the chapter-8 two-stage + phoneme-triage audit.
FUNNEL = [
    ("495", "chunks of audio scanned"),
    ("257", "raw defect flags (base Whisper)"),
    ("108", "survive two-model confirmation"),
    ("20", "genuine XTTS mispronunciations"),
]
THRESHOLD = 0.45


def _mark(sentence: str, word: str) -> str:
    esc = html.escape(sentence)
    low = esc.lower()
    i = low.find(word.lower())
    if i < 0:
        return esc
    return esc[:i] + f'<mark>{esc[i:i+len(word)]}</mark>' + esc[i + len(word):]


def _audio(b64: str, label: str) -> str:
    if not b64:
        return ""
    return (f'<div class="clip"><span class="clip-label">{label}</span>'
            f'<audio controls preload="none" src="data:audio/mp3;base64,{b64}"></audio></div>')


def _card(row: dict) -> str:
    dist = row.get("distance")
    real = row.get("source") == "xtts"
    badge = ("Real TTS mispronunciation" if real else "Audio is correct — Whisper misread")
    cls = "real" if real else "ok"
    pct = min(100, round((dist or 0) * 100))
    thr = round(THRESHOLD * 100)
    after = _audio(row.get("after_mp3"), f'After · respelled "{html.escape(row["fix"])}"') if row.get("fix") else \
        '<div class="clip empty">no reliable respelling — see notes</div>' if real else \
        '<div class="clip empty">nothing to fix — audio already correct</div>'

    phon = ""
    if row.get("expected_phones") is not None:
        phon = (f'<div class="phon"><span>expected</span><code>/{html.escape(row["expected_phones"])}/</code>'
                f'<span>heard in audio</span><code>/{html.escape(row["actual_phones"])}/</code></div>')

    return f'''<article class="card {cls}">
  <header>
    <h2>{html.escape(row["word"])}</h2>
    <span class="badge {cls}">{badge}</span>
  </header>
  <p class="sentence">{_mark(row["sentence"], row["word"])}</p>
  <div class="evidence">
    <div class="row"><span class="k">Whisper transcribed</span>
      <span class="v strike">{html.escape(str(row["whisper_heard"]))}</span></div>
    {phon}
    <div class="meter" title="phoneme distance {dist}">
      <div class="fill {cls}" style="width:{pct}%"></div>
      <div class="thr" style="left:{thr}%"></div>
    </div>
    <div class="meter-cap"><span>0 · identical</span>
      <span>phoneme distance {dist:.2f}</span><span>1 · unrelated</span></div>
  </div>
  <div class="clips">
    {_audio(row["before_mp3"], "Before · shipped audio")}
    {after}
  </div>
</article>'''


def main():
    rows = sorted(json.loads(DATA.read_text()), key=lambda r: r.get("distance") or 0)
    cards = "\n".join(_card(r) for r in rows)
    funnel = "\n".join(
        f'<div class="stat"><span class="num">{n}</span><span class="lbl">{l}</span></div>'
        for n, l in FUNNEL)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(TEMPLATE.replace("{{FUNNEL}}", funnel).replace("{{CARDS}}", cards))
    print(f"Wrote {OUT} ({OUT.stat().st_size // 1024} KB)")


TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Is it the TTS, or is it Whisper? — Audiobook phoneme audit</title>
<style>
  :root {
    --paper:#f4f1ea; --raised:#fbf9f4; --ink:#211d18; --muted:#6c6559; --line:#e0dacf;
    --accent:#3a5f8a; --ok:#2e7d5b; --ok-bg:#e6f0ea; --real:#b4522a; --real-bg:#f6e9e1;
    --shadow:0 1px 2px rgba(33,29,24,.05), 0 8px 24px rgba(33,29,24,.06);
    --serif:"Iowan Old Style","Palatino Linotype",Palatino,Georgia,serif;
    --sans:system-ui,-apple-system,"Segoe UI",sans-serif;
    --mono:"SF Mono","JetBrains Mono",ui-monospace,"Cascadia Code",Menlo,monospace;
  }
  @media (prefers-color-scheme: dark) {
    :root { --paper:#16141a; --raised:#1e1b22; --ink:#ece6da; --muted:#9c948a; --line:#302c36;
      --accent:#8fb4e0; --ok:#6cc79b; --ok-bg:#1c2a24; --real:#e08a5f; --real-bg:#2c2019;
      --shadow:0 1px 2px rgba(0,0,0,.3), 0 10px 30px rgba(0,0,0,.35); }
  }
  :root[data-theme="light"] { --paper:#f4f1ea; --raised:#fbf9f4; --ink:#211d18; --muted:#6c6559;
    --line:#e0dacf; --accent:#3a5f8a; --ok:#2e7d5b; --ok-bg:#e6f0ea; --real:#b4522a; --real-bg:#f6e9e1;
    --shadow:0 1px 2px rgba(33,29,24,.05), 0 8px 24px rgba(33,29,24,.06); }
  :root[data-theme="dark"] { --paper:#16141a; --raised:#1e1b22; --ink:#ece6da; --muted:#9c948a;
    --line:#302c36; --accent:#8fb4e0; --ok:#6cc79b; --ok-bg:#1c2a24; --real:#e08a5f; --real-bg:#2c2019;
    --shadow:0 1px 2px rgba(0,0,0,.3), 0 10px 30px rgba(0,0,0,.35); }

  * { box-sizing:border-box; }
  body { margin:0; background:var(--paper); color:var(--ink); font-family:var(--sans);
    line-height:1.6; -webkit-font-smoothing:antialiased; }
  .wrap { max-width:940px; margin:0 auto; padding:clamp(1.5rem,4vw,4rem) clamp(1rem,4vw,2rem); }

  header.masthead { border-bottom:1px solid var(--line); padding-bottom:2rem; margin-bottom:2.5rem; }
  .eyebrow { font-family:var(--mono); font-size:.72rem; letter-spacing:.18em; text-transform:uppercase;
    color:var(--accent); margin:0 0 1rem; }
  h1 { font-family:var(--serif); font-weight:600; font-size:clamp(2rem,5vw,3.1rem); line-height:1.08;
    letter-spacing:-.01em; text-wrap:balance; margin:0 0 1rem; }
  .lede { font-size:1.12rem; color:var(--muted); max-width:60ch; margin:0; }
  .lede b { color:var(--ink); font-weight:600; }

  .funnel { display:grid; grid-template-columns:repeat(4,1fr); gap:1px; background:var(--line);
    border:1px solid var(--line); border-radius:12px; overflow:hidden; margin:2.5rem 0 0; }
  .stat { background:var(--raised); padding:1.1rem 1rem; display:flex; flex-direction:column; gap:.25rem; }
  .stat .num { font-family:var(--serif); font-size:1.9rem; font-weight:600; font-variant-numeric:tabular-nums;
    line-height:1; }
  .stat:last-child .num { color:var(--real); }
  .stat:first-child .num { color:var(--accent); }
  .stat .lbl { font-size:.78rem; color:var(--muted); line-height:1.35; }
  @media (max-width:640px){ .funnel{ grid-template-columns:repeat(2,1fr); } }

  .section-head { display:flex; align-items:baseline; gap:.75rem; margin:3rem 0 1.25rem; }
  .section-head h3 { font-family:var(--serif); font-size:1.4rem; font-weight:600; margin:0; }
  .section-head p { margin:0; color:var(--muted); font-size:.9rem; }

  .cards { display:flex; flex-direction:column; gap:1.25rem; }
  .card { background:var(--raised); border:1px solid var(--line); border-radius:14px;
    padding:1.4rem clamp(1.1rem,3vw,1.6rem); box-shadow:var(--shadow);
    border-left:4px solid var(--ok); }
  .card.real { border-left-color:var(--real); }
  .card header { display:flex; align-items:center; justify-content:space-between; gap:1rem;
    flex-wrap:wrap; margin-bottom:.4rem; }
  .card h2 { font-family:var(--serif); font-size:1.7rem; font-weight:600; margin:0; letter-spacing:-.01em; }
  .badge { font-size:.74rem; font-weight:600; padding:.28rem .7rem; border-radius:999px;
    background:var(--ok-bg); color:var(--ok); white-space:nowrap; }
  .badge.real { background:var(--real-bg); color:var(--real); }

  .sentence { font-family:var(--serif); font-size:1.12rem; color:var(--ink); margin:.5rem 0 1.1rem;
    max-width:64ch; }
  mark { background:transparent; color:inherit; box-shadow:inset 0 -.5em 0 color-mix(in srgb,var(--accent) 22%,transparent);
    padding:0 .05em; font-style:italic; }

  .evidence { border-top:1px solid var(--line); padding-top:1rem; margin-bottom:1.1rem; }
  .row { display:flex; gap:.6rem; align-items:baseline; font-size:.92rem; margin-bottom:.5rem; }
  .row .k { color:var(--muted); min-width:9.5rem; font-size:.8rem; text-transform:uppercase; letter-spacing:.05em; }
  .row .v.strike { font-family:var(--mono); }
  .strike { text-decoration:line-through; text-decoration-color:var(--real); text-decoration-thickness:1.5px; }
  .phon { display:grid; grid-template-columns:auto 1fr; gap:.3rem 1rem; align-items:baseline;
    margin:.6rem 0 1rem; }
  .phon span { color:var(--muted); font-size:.74rem; text-transform:uppercase; letter-spacing:.05em; }
  .phon code { font-family:var(--mono); font-size:1.02rem; color:var(--ink); }

  .meter { position:relative; height:8px; border-radius:99px; background:var(--line); overflow:hidden; }
  .meter .fill { height:100%; background:var(--ok); border-radius:99px; }
  .meter .fill.real { background:var(--real); }
  .meter .thr { position:absolute; top:-3px; bottom:-3px; width:2px; background:var(--ink); opacity:.45; }
  .meter-cap { display:flex; justify-content:space-between; font-size:.72rem; color:var(--muted);
    margin-top:.35rem; font-variant-numeric:tabular-nums; }
  .meter-cap span:nth-child(2){ font-weight:600; color:var(--ink); }

  .clips { display:flex; flex-wrap:wrap; gap:1rem; }
  .clip { flex:1; min-width:240px; display:flex; flex-direction:column; gap:.4rem; }
  .clip-label { font-size:.76rem; color:var(--muted); font-weight:600; }
  .clip audio { width:100%; height:36px; }
  .clip.empty { justify-content:center; color:var(--muted); font-size:.85rem; font-style:italic;
    border:1px dashed var(--line); border-radius:8px; padding:.6rem .8rem; min-height:36px; }

  footer { margin-top:3.5rem; padding-top:1.5rem; border-top:1px solid var(--line); color:var(--muted);
    font-size:.85rem; }
  footer code { font-family:var(--mono); font-size:.82em; background:color-mix(in srgb,var(--ink) 7%,transparent);
    padding:.1em .4em; border-radius:4px; }
  a { color:var(--accent); }
  audio:focus-visible { outline:2px solid var(--accent); outline-offset:2px; }
</style>
</head>
<body>
<div class="wrap">
  <header class="masthead">
    <p class="eyebrow">Audiobook pipeline · TTS quality audit</p>
    <h1>Most “mangled” audio isn’t mangled — it’s Whisper misreading correct speech.</h1>
    <p class="lede">A speech-to-text pass flags words where the audiobook’s narration doesn’t
      match the script. But Whisper is a <b>word</b> recognizer: on a rare place name or coined
      word it guesses wrong even when the audio is perfect. Comparing <b>phonemes</b> instead —
      what the voice actually said, versus how the word should sound — separates real
      mispronunciations from Whisper’s own limits. Listen for yourself.</p>
    <div class="funnel">{{FUNNEL}}</div>
  </header>

  <div class="section-head">
    <h3>Case by case</h3>
    <p>sorted by phoneme distance — audio-is-fine first, genuine defects last</p>
  </div>
  <div class="cards">
{{CARDS}}
  </div>

  <footer>
    <p>Each verdict compares the word’s expected pronunciation (<code>espeak-ng</code> G2P)
      against the phonemes a vocabulary-free <code>wav2vec2</code> model hears in the shipped
      audio. Distance below <b>0.45</b> means the narration is correct and the script mismatch
      is Whisper’s. “After” clips regenerate the chunk with a respelled pronunciation hint.
      Chapter 8, Book 7 — one representative chapter of the audit.</p>
  </footer>
</div>
</body>
</html>"""


if __name__ == "__main__":
    main()
