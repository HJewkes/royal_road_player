#!/usr/bin/env python3
"""Render the fix-pass before/after demo from logs/fix_results.json.

Shows FULL chunk-vs-chunk audio (the real concatenation swap) for every chunk the
fix pass measurably improved, plus the overall improvement rate. Discarded (no-gain)
chunks are listed honestly but carry no swap. Self-contained; open via file://.
"""
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "logs" / "fix_results.json"
OUT = ROOT / "demo" / "tts_fix_demo.html"


def _mark(sentence, word):
    esc = html.escape(sentence or "")
    low, w = esc.lower(), (word or "").lower()
    i = low.find(w)
    if i < 0 or not w:
        return esc
    return esc[:i] + f"<mark>{esc[i:i+len(word)]}</mark>" + esc[i+len(word):]


def _audio(b64, label):
    if not b64:
        return ""
    return (f'<div class="clip"><span class="clip-label">{label}</span>'
            f'<audio controls preload="none" src="data:audio/mp3;base64,{b64}"></audio></div>')


def _phon_row(r):
    if not r.get("expected_phones"):
        return ""
    return (f'<div class="phon"><span>should sound like</span><code>/{html.escape(r["expected_phones"])}/</code>'
            f'<span>before</span><code class="bad">/{html.escape(r.get("before_phones") or "")}/</code>'
            f'<span>after</span><code class="good">/{html.escape(r.get("after_phones") or "")}/</code></div>')


def _card(r):
    drop = round((r["before_dist"] - r["after_dist"]), 2)
    return f'''<article class="card win">
  <header>
    <h2>{html.escape(r["word"])}</h2>
    <span class="badge win">fixed · distance {r["before_dist"]:.2f} → {r["after_dist"]:.2f}
      <b>(−{drop:.2f})</b></span>
  </header>
  <p class="loc">book {r["book"]} · chapter {r["chapter"]} · chunk {r["chunk"]:03d}
     · winning take <code>{html.escape(r["take"])}</code></p>
  <p class="sentence">{_mark(r["sentence"], r["word"])}</p>
  {_phon_row(r)}
  <div class="clips">
    {_audio(r["before_mp3"], "Before · shipped chunk")}
    {_audio(r["after_mp3"], "After · regenerated chunk")}
  </div>
</article>'''


def _discarded_row(r):
    return (f'<li><span>{html.escape(r["word"])}</span> '
            f'<code>b{r["book"]}/ch{r["chapter"]}/{r["chunk"]:03d}</code> '
            f'— stayed {r["before_dist"]:.2f} → {r["after_dist"]:.2f}, no gain (kept shipped)</li>')


def main():
    data = json.loads(DATA.read_text())
    results = data["results"]
    wins = [r for r in results if r["improved"]]
    losses = [r for r in results if not r["improved"]]
    wins.sort(key=lambda r: (r["before_dist"] - r["after_dist"]), reverse=True)

    cards = "\n".join(_card(r) for r in wins) or \
        '<p class="empty">No chunk beat its shipped take this run.</p>'
    discarded = "\n".join(_discarded_row(r) for r in losses) or "<li>none</li>"

    page = (TEMPLATE
            .replace("{{RATE}}", f'{data["improvement_rate_pct"]:.0f}')
            .replace("{{IMPROVED}}", str(data["improved"]))
            .replace("{{ATTEMPTED}}", str(data["attempted"]))
            .replace("{{CARDS}}", cards)
            .replace("{{DISCARDED}}", discarded))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(page)
    print(f"Wrote {OUT} ({OUT.stat().st_size // 1024} KB) — {data['improved']}/{data['attempted']} improved")


TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Fix pass — regenerate-and-pick results</title>
<style>
  :root {
    --paper:#f4f1ea; --raised:#fbf9f4; --ink:#211d18; --muted:#6c6559; --line:#e0dacf;
    --accent:#3a5f8a; --ok:#2e7d5b; --ok-bg:#e6f0ea; --real:#b4522a; --real-bg:#f6e9e1;
    --shadow:0 1px 2px rgba(33,29,24,.05), 0 8px 24px rgba(33,29,24,.06);
    --serif:"Iowan Old Style","Palatino Linotype",Palatino,Georgia,serif;
    --sans:system-ui,-apple-system,"Segoe UI",sans-serif;
    --mono:"SF Mono","JetBrains Mono",ui-monospace,Menlo,monospace;
  }
  @media (prefers-color-scheme: dark) { :root {
    --paper:#16141a; --raised:#1e1b22; --ink:#ece6da; --muted:#9c948a; --line:#302c36;
    --accent:#8fb4e0; --ok:#6cc79b; --ok-bg:#1c2a24; --real:#e08a5f; --real-bg:#2c2019;
    --shadow:0 1px 2px rgba(0,0,0,.3), 0 10px 30px rgba(0,0,0,.35); } }
  :root[data-theme="light"] { --paper:#f4f1ea; --raised:#fbf9f4; --ink:#211d18; --muted:#6c6559;
    --line:#e0dacf; --accent:#3a5f8a; --ok:#2e7d5b; --ok-bg:#e6f0ea; --real:#b4522a; --real-bg:#f6e9e1; }
  :root[data-theme="dark"] { --paper:#16141a; --raised:#1e1b22; --ink:#ece6da; --muted:#9c948a;
    --line:#302c36; --accent:#8fb4e0; --ok:#6cc79b; --ok-bg:#1c2a24; --real:#e08a5f; --real-bg:#2c2019; }

  * { box-sizing:border-box; }
  body { margin:0; background:var(--paper); color:var(--ink); font-family:var(--sans); line-height:1.6; }
  .wrap { max-width:920px; margin:0 auto; padding:clamp(1.5rem,4vw,4rem) clamp(1rem,4vw,2rem); }
  .eyebrow { font-family:var(--mono); font-size:.72rem; letter-spacing:.18em; text-transform:uppercase;
    color:var(--accent); margin:0 0 1rem; }
  h1 { font-family:var(--serif); font-weight:600; font-size:clamp(1.9rem,5vw,2.9rem); line-height:1.1;
    letter-spacing:-.01em; text-wrap:balance; margin:0 0 1.5rem; }

  .hero { display:flex; align-items:baseline; gap:1.5rem; flex-wrap:wrap; border:1px solid var(--line);
    border-radius:14px; background:var(--raised); padding:1.5rem 1.8rem; box-shadow:var(--shadow);
    margin-bottom:2.5rem; }
  .hero .rate { font-family:var(--serif); font-size:4rem; font-weight:600; line-height:.9; color:var(--ok);
    font-variant-numeric:tabular-nums; }
  .hero .rate::after { content:"%"; font-size:2rem; vertical-align:super; }
  .hero .cap { color:var(--muted); font-size:1.02rem; max-width:42ch; }
  .hero .cap b { color:var(--ink); }

  h3 { font-family:var(--serif); font-size:1.35rem; font-weight:600; margin:2.5rem 0 1.1rem; }
  .cards { display:flex; flex-direction:column; gap:1.25rem; }
  .card { background:var(--raised); border:1px solid var(--line); border-radius:14px;
    padding:1.4rem clamp(1.1rem,3vw,1.6rem); box-shadow:var(--shadow); border-left:4px solid var(--ok); }
  .card header { display:flex; align-items:center; justify-content:space-between; gap:1rem;
    flex-wrap:wrap; margin-bottom:.25rem; }
  .card h2 { font-family:var(--serif); font-size:1.6rem; font-weight:600; margin:0; }
  .badge { font-size:.76rem; font-weight:600; padding:.28rem .7rem; border-radius:999px;
    background:var(--ok-bg); color:var(--ok); white-space:nowrap; }
  .badge b { font-weight:700; }
  .loc { font-size:.82rem; color:var(--muted); margin:.1rem 0 .6rem; }
  .loc code { font-family:var(--mono); font-size:.9em; }
  .sentence { font-family:var(--serif); font-size:1.1rem; margin:.3rem 0 1rem; max-width:64ch; }
  mark { background:transparent; box-shadow:inset 0 -.5em 0 color-mix(in srgb,var(--accent) 22%,transparent);
    font-style:italic; padding:0 .05em; }
  .phon { display:grid; grid-template-columns:auto 1fr; gap:.25rem 1rem; align-items:baseline;
    margin:.4rem 0 1rem; padding:.7rem .9rem; background:color-mix(in srgb,var(--ink) 3%,transparent);
    border-radius:8px; }
  .phon span { color:var(--muted); font-size:.72rem; text-transform:uppercase; letter-spacing:.05em; }
  .phon code { font-family:var(--mono); font-size:1rem; }
  .phon code.bad { color:var(--real); } .phon code.good { color:var(--ok); }
  .clips { display:flex; flex-wrap:wrap; gap:1rem; }
  .clip { flex:1; min-width:250px; display:flex; flex-direction:column; gap:.4rem; }
  .clip-label { font-size:.76rem; color:var(--muted); font-weight:600; }
  .clip audio { width:100%; height:36px; }
  .discarded { color:var(--muted); font-size:.9rem; }
  .discarded li { margin:.3rem 0; } .discarded code { font-family:var(--mono); font-size:.85em; }
  .discarded span { color:var(--ink); font-weight:600; }
  .empty { color:var(--muted); font-style:italic; }
  footer { margin-top:3rem; padding-top:1.4rem; border-top:1px solid var(--line); color:var(--muted);
    font-size:.85rem; }
  footer code { font-family:var(--mono); font-size:.82em; }
  audio:focus-visible { outline:2px solid var(--accent); outline-offset:2px; }
</style>
</head>
<body>
<div class="wrap">
  <p class="eyebrow">Audiobook pipeline · regenerate-and-pick fix pass</p>
  <h1>Re-rolling the dice fixes the chunks that broke by chance.</h1>
  <div class="hero">
    <div class="rate">{{RATE}}</div>
    <div class="cap"><b>{{IMPROVED}} of {{ATTEMPTED}}</b> problematic chunks improved. Each was
      re-synthesized a few times under varied XTTS decoder settings; the phoneme-closest take
      replaced the shipped chunk — but only when it actually beat it. Listen to the whole-chunk
      swaps below.</div>
  </div>

  <h3>Improved chunks — full before/after swap</h3>
  <div class="cards">
{{CARDS}}
  </div>

  <h3>No gain — kept the shipped take</h3>
  <ul class="discarded">
{{DISCARDED}}
  </ul>

  <footer>
    <p>Score = phoneme distance between the flagged word's audio (vocab-free <code>wav2vec2</code>)
      and its correct pronunciation (<code>espeak-ng</code> G2P); lower is better. A regenerated
      chunk is kept only if it beats the shipped take by ≥0.06. Context-dependent slips on common
      words rescue readily; intrinsically hard rare names often don't — those need a pronunciation
      lexicon, not a re-roll.</p>
  </footer>
</div>
</body>
</html>"""


if __name__ == "__main__":
    main()
