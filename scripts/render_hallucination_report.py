#!/usr/bin/env python3
"""Render the tabbed hallucination report: spot-check list + before/after + method.

Self-contained (all audio inlined as base64), openable via file://. Tabs:
  1. Spot-check   every flagged chunk, ranked by confidence, with the shipped audio
                  clip so a human can judge whether the flag is a real defect.
  2. Before / after   the rechunk/rebuild test — shipped (babbling) chunk vs the
                  rebuilt chunk, plus the aggregate hallucination-rate reduction.
  3. Method       how detection and the chunking fix work, and the honest caveats.

  ./venv311/bin/python scripts/render_hallucination_report.py
"""
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPOT = ROOT / "logs" / "spotcheck_data.json"
BA = ROOT / "logs" / "beforeafter_data.json"
OUT = ROOT / "demo" / "hallucination_report.html"

TIER_LABEL = {"confirmed": "Confirmed", "likely": "Likely",
              "borderline": "Borderline", "probable_fp": "Probable FP"}
TIER_ORDER = ["confirmed", "likely", "borderline", "probable_fp"]


def _audio(b64, label):
    if not b64:
        return ""
    return (f'<div class="clip"><span class="clip-label">{label}</span>'
            f'<audio controls preload="none" src="data:audio/mp3;base64,{b64}"></audio></div>')


def _mark_babble(text):
    esc = html.escape(text)
    return esc.replace("⟨▓⟩", '<span class="babble" title="injected babble here">babble</span>')


def _spot_row(r):
    tier = r["tier"]
    conf_pct = round(r["confidence"] * 100)
    corro = ('<span class="tag ok">Whisper-corroborated</span>'
             if r.get("whisper_corroborated") else '<span class="tag">phoneme-only</span>')
    return f'''<article class="case" data-tier="{tier}">
  <div class="case-head">
    <span class="pill {tier}">{TIER_LABEL.get(tier, tier)}</span>
    <span class="loc">book {r["book"]} · ch {r["chapter"]} · chunk {r["chunk"]:03d}</span>
    <span class="conf" title="ranking confidence">conf {conf_pct}</span>
  </div>
  <p class="text">{_mark_babble(r["text"])}</p>
  <div class="meta">
    <code class="phones" title="injected phones the model heard with no matching text">/{html.escape(r["phones"])}/</code>
    <span class="tag">{r["length"]} phones @ {int((r.get("position") or 0)*100)}%</span>
    {corro}
    <span class="tag dur">clip {r["clip_seconds"]}s of {r["full_seconds"]}s</span>
  </div>
  {_audio(r["mp3"], "Shipped audio — listen for the babble")}
</article>'''


def _filter_bar(rows):
    counts = {t: sum(1 for r in rows if r["tier"] == t) for t in TIER_ORDER}
    btns = [f'<button class="fbtn active" data-f="all">All <b>{len(rows)}</b></button>']
    for t in TIER_ORDER:
        if counts[t]:
            btns.append(f'<button class="fbtn" data-f="{t}">{TIER_LABEL[t]} <b>{counts[t]}</b></button>')
    return "".join(btns)


def _ba_cards(ba):
    if not ba:
        return ('<p class="pending">The rechunk/rebuild test is still running. This tab fills in '
                'with real before/after audio and the measured rate reduction once it finishes — '
                'rerun <code>render_hallucination_report.py</code> then.</p>')
    s = ba["summary"]
    hero = f'''<div class="ba-hero">
    <div class="ba-stat"><span class="big drop">{s["reduction_pct"]}<i>%</i></span>
      <span class="cap">fewer hallucinated takes after rechunking<br><b>{s["control_rate_pct"]}%</b>
      of control takes babbled → <b>{s["fix_rate_pct"]}%</b> after the fix
      (paired, {s["reps"]} reps × {s["n"]} chunks)</span></div>
    <div class="ba-stat"><span class="big">{s["fixed"]}<i>/{s["n"]}</i></span>
      <span class="cap">chunks that babbled every-or-some control reps came out
      <b>clean on all {s["reps"]}</b> fix reps</span></div>
  </div>'''
    cards = "\n".join(_ba_card(c) for c in ba["cases"])
    resid = ""
    if ba.get("residual"):
        from collections import Counter
        kinds = Counter(r["kind"] for r in ba["residual"])
        kind_line = " · ".join(f"{v} {k}" for k, v in kinds.most_common())
        resid = (f'<h3 class="sub">Still hallucinating after the fix ({len(ba["residual"])})</h3>'
                 f'<p class="note">These retain a babble the chunking fix does not remove. '
                 f'Ranked by how many of {ba["summary"]["reps"]} rebuild reps still babbled. '
                 f'Breakdown: {kind_line}.</p>'
                 '<div class="cases resid-cases">'
                 + "\n".join(_resid_card(r) for r in ba["residual"]) + '</div>')
    return hero + '<div class="cases ba">' + cards + '</div>' + resid


def _resid_card(r):
    src = r.get("audio_source", "")
    repro = r.get("reproduced")
    if src == "post-fix rebuild" and repro is False:
        label, note = ("Rebuilt chunk — clean this take (babble is intermittent)",
                       '<span class="tag ok">intermittent — clean in 6 tries</span>')
    elif src == "post-fix rebuild":
        label, note = "Rebuilt chunk — still babbles", ""
    else:
        label, note = ("Shipped audio (pre-fix reference)",
                       '<span class="tag">post-fix capture pending</span>')
    audio = _audio(r.get("audio"), label)
    return f'''<article class="case resid-case">
  <div class="case-head">
    <span class="pill resid">{html.escape(r["kind"])}</span>
    <span class="loc">book {r["book"]} · ch {r["chapter"]} · chunk {r["chunk"]:03d}</span>
    <span class="conf">still {r["fix_hits"]}/{r["reps"]}</span>
  </div>
  <p class="text">{_mark_babble(r["new_text"])}</p>
  <div class="meta"><code class="phones">/{html.escape(r["phones"])}/</code>
    <span class="tag">@ {int((r.get("position") or 0)*100)}%{"" if r["n_new"]==1 else " · "+str(r["n_new"])+" sub-chunks"}</span>
    {note}</div>
  {audio}
</article>'''


def _ba_card(c):
    splits = (f' · rebuilt as {c["n_new"]} chunks' if c["n_new"] > 1 else "")
    return f'''<article class="case ba-case">
  <div class="case-head">
    <span class="pill ok">fixed · control {c["control_hits"]}/{c["reps"]} → fix 0/{c["reps"]}</span>
    <span class="loc">book {c["book"]} · ch {c["chapter"]} · chunk {c["chunk"]:03d}{splits}</span>
  </div>
  <p class="text">{html.escape(c["old_text"][:220])}{"…" if len(c["old_text"])>220 else ""}</p>
  <div class="meta"><code class="phones">/{html.escape(c["phones"])}/</code>
    <span class="tag">babble removed</span></div>
  <div class="clips">
    {_audio(c.get("before_mp3"), "Before · shipped chunk (babbles)")}
    {_audio(c.get("after_mp3"), "After · rebuilt chunk (clean)")}
  </div>
</article>'''


def main():
    spot = json.loads(SPOT.read_text()) if SPOT.exists() else []
    ba = json.loads(BA.read_text()) if BA.exists() else None

    page = (TEMPLATE
            .replace("{{TOTAL}}", str(len(spot)))
            .replace("{{CONFIRMED}}", str(sum(1 for r in spot if r["tier"] == "confirmed")))
            .replace("{{FILTERS}}", _filter_bar(spot))
            .replace("{{SPOT_CASES}}", "\n".join(_spot_row(r) for r in spot))
            .replace("{{BA}}", _ba_cards(ba)))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(page)
    print(f"Wrote {OUT} ({OUT.stat().st_size // 1024} KB) — {len(spot)} spot-check cases, "
          f"before/after: {'ready' if ba else 'pending'}")


TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Hallucinated outbursts — audit &amp; spot-check</title>
<style>
  :root {
    --paper:#f4f1ea; --raised:#fbf9f4; --ink:#211d18; --muted:#6c6559; --line:#e0dacf;
    --accent:#3a5f8a; --ok:#2e7d5b; --ok-bg:#e6f0ea; --real:#b4522a; --real-bg:#f6e9e1;
    --warn:#9a7a1e; --warn-bg:#f3ecd8;
    --shadow:0 1px 2px rgba(33,29,24,.05), 0 8px 24px rgba(33,29,24,.06);
    --serif:"Iowan Old Style","Palatino Linotype",Palatino,Georgia,serif;
    --sans:system-ui,-apple-system,"Segoe UI",sans-serif;
    --mono:"SF Mono","JetBrains Mono",ui-monospace,"Cascadia Code",Menlo,monospace;
  }
  @media (prefers-color-scheme: dark) { :root {
    --paper:#16141a; --raised:#1e1b22; --ink:#ece6da; --muted:#9c948a; --line:#302c36;
    --accent:#8fb4e0; --ok:#6cc79b; --ok-bg:#1c2a24; --real:#e08a5f; --real-bg:#2c2019;
    --warn:#d4b25a; --warn-bg:#2a2413;
    --shadow:0 1px 2px rgba(0,0,0,.3), 0 10px 30px rgba(0,0,0,.35); } }
  :root[data-theme="light"] { --paper:#f4f1ea; --raised:#fbf9f4; --ink:#211d18; --muted:#6c6559;
    --line:#e0dacf; --accent:#3a5f8a; --ok:#2e7d5b; --ok-bg:#e6f0ea; --real:#b4522a; --real-bg:#f6e9e1;
    --warn:#9a7a1e; --warn-bg:#f3ecd8; }
  :root[data-theme="dark"] { --paper:#16141a; --raised:#1e1b22; --ink:#ece6da; --muted:#9c948a;
    --line:#302c36; --accent:#8fb4e0; --ok:#6cc79b; --ok-bg:#1c2a24; --real:#e08a5f; --real-bg:#2c2019;
    --warn:#d4b25a; --warn-bg:#2a2413; }

  * { box-sizing:border-box; }
  body { margin:0; background:var(--paper); color:var(--ink); font-family:var(--sans);
    line-height:1.6; -webkit-font-smoothing:antialiased; }
  .wrap { max-width:960px; margin:0 auto; padding:clamp(1.5rem,4vw,3.5rem) clamp(1rem,4vw,2rem); }

  header.masthead { border-bottom:1px solid var(--line); padding-bottom:1.6rem; margin-bottom:1.5rem; }
  .eyebrow { font-family:var(--mono); font-size:.72rem; letter-spacing:.18em; text-transform:uppercase;
    color:var(--accent); margin:0 0 1rem; }
  h1 { font-family:var(--serif); font-weight:600; font-size:clamp(1.9rem,5vw,2.9rem); line-height:1.09;
    letter-spacing:-.01em; text-wrap:balance; margin:0 0 1rem; }
  .lede { font-size:1.08rem; color:var(--muted); max-width:62ch; margin:0; }
  .lede b { color:var(--ink); font-weight:600; }

  .tabs { display:flex; gap:.4rem; border-bottom:1px solid var(--line); margin:0 0 2rem; flex-wrap:wrap; }
  .tab { font-family:var(--sans); font-size:.92rem; font-weight:600; color:var(--muted);
    background:none; border:none; border-bottom:2px solid transparent; padding:.7rem .9rem;
    margin-bottom:-1px; cursor:pointer; }
  .tab:hover { color:var(--ink); }
  .tab.active { color:var(--accent); border-bottom-color:var(--accent); }
  .panel { display:none; }
  .panel.active { display:block; animation:fade .2s ease; }
  @keyframes fade { from{opacity:0; transform:translateY(3px);} to{opacity:1;} }
  @media (prefers-reduced-motion:reduce){ .panel.active{ animation:none; } }

  .intro { color:var(--muted); font-size:.95rem; max-width:64ch; margin:0 0 1.4rem; }
  .intro b { color:var(--ink); }

  .filters { display:flex; gap:.5rem; flex-wrap:wrap; margin:0 0 1.4rem; position:sticky; top:0;
    background:var(--paper); padding:.6rem 0; z-index:5; }
  .fbtn { font-family:var(--sans); font-size:.82rem; color:var(--muted); background:var(--raised);
    border:1px solid var(--line); border-radius:999px; padding:.35rem .8rem; cursor:pointer; }
  .fbtn b { color:var(--ink); font-variant-numeric:tabular-nums; }
  .fbtn.active { border-color:var(--accent); color:var(--accent); background:color-mix(in srgb,var(--accent) 9%,var(--raised)); }
  .fbtn.active b { color:var(--accent); }

  .cases { display:flex; flex-direction:column; gap:1rem; }
  .case { background:var(--raised); border:1px solid var(--line); border-radius:12px;
    padding:1.1rem clamp(1rem,3vw,1.35rem); box-shadow:var(--shadow); border-left:4px solid var(--line); }
  .case[data-tier="confirmed"] { border-left-color:var(--real); }
  .case[data-tier="likely"] { border-left-color:var(--warn); }
  .case[data-tier="borderline"] { border-left-color:var(--muted); }
  .case[data-tier="probable_fp"] { border-left-color:var(--line); opacity:.9; }
  .ba-case { border-left-color:var(--ok); }
  .case-head { display:flex; align-items:center; gap:.7rem; flex-wrap:wrap; margin-bottom:.5rem; }
  .pill { font-size:.7rem; font-weight:700; letter-spacing:.03em; text-transform:uppercase;
    padding:.24rem .6rem; border-radius:999px; background:var(--line); color:var(--ink); }
  .pill.confirmed { background:var(--real-bg); color:var(--real); }
  .pill.likely { background:var(--warn-bg); color:var(--warn); }
  .pill.borderline { background:color-mix(in srgb,var(--muted) 18%,transparent); color:var(--muted); }
  .pill.probable_fp { background:transparent; border:1px solid var(--line); color:var(--muted); }
  .pill.ok { background:var(--ok-bg); color:var(--ok); }
  .pill.resid { background:var(--warn-bg); color:var(--warn); }
  .resid-case { border-left-color:var(--warn); }
  .loc { font-size:.82rem; color:var(--muted); }
  .conf { margin-left:auto; font-family:var(--mono); font-size:.76rem; color:var(--muted);
    font-variant-numeric:tabular-nums; }
  .text { font-family:var(--serif); font-size:1.08rem; color:var(--ink); margin:.2rem 0 .8rem;
    max-width:70ch; }
  .babble { background:var(--real-bg); color:var(--real); font-family:var(--sans); font-size:.72rem;
    font-weight:700; text-transform:uppercase; letter-spacing:.04em; padding:.05em .45em; border-radius:5px;
    vertical-align:.08em; }
  .meta { display:flex; align-items:center; gap:.5rem; flex-wrap:wrap; margin-bottom:.8rem; }
  .phones { font-family:var(--mono); font-size:.95rem; color:var(--real); background:color-mix(in srgb,var(--real) 8%,transparent);
    padding:.12em .45em; border-radius:5px; }
  .tag { font-size:.72rem; color:var(--muted); background:color-mix(in srgb,var(--ink) 5%,transparent);
    padding:.16em .5em; border-radius:5px; }
  .tag.ok { color:var(--ok); background:var(--ok-bg); }
  .tag.dur { margin-left:auto; }

  .clips { display:flex; flex-wrap:wrap; gap:1rem; }
  .clip { flex:1; min-width:240px; display:flex; flex-direction:column; gap:.35rem; }
  .clip-label { font-size:.74rem; color:var(--muted); font-weight:600; }
  .clip audio { width:100%; height:34px; }

  .ba-hero { display:flex; gap:1rem; flex-wrap:wrap; margin:0 0 2rem; }
  .ba-stat { flex:1; min-width:240px; background:var(--raised); border:1px solid var(--line);
    border-radius:12px; padding:1.3rem 1.4rem; box-shadow:var(--shadow); display:flex; gap:1rem;
    align-items:baseline; }
  .ba-stat .big { font-family:var(--serif); font-size:3rem; font-weight:600; line-height:.9;
    font-variant-numeric:tabular-nums; }
  .ba-stat .big.drop { color:var(--ok); }
  .ba-stat .big i { font-size:1.3rem; font-style:normal; color:var(--muted); }
  .ba-stat .cap { font-size:.9rem; color:var(--muted); } .ba-stat .cap b { color:var(--ink); }
  .pending { color:var(--muted); font-style:italic; background:var(--raised); border:1px dashed var(--line);
    border-radius:12px; padding:1.4rem 1.6rem; } .pending code { font-family:var(--mono); font-size:.85em; }
  .sub { font-family:var(--serif); font-size:1.25rem; margin:2.5rem 0 .4rem; }
  .note { color:var(--muted); font-size:.9rem; margin:.2rem 0 1rem; max-width:64ch; }
  .resid { color:var(--muted); font-size:.9rem; columns:2; gap:2rem; } .resid li{ margin:.25rem 0; }
  .resid code { font-family:var(--mono); font-size:.85em; }
  @media (max-width:640px){ .resid{ columns:1; } }

  .method { max-width:66ch; }
  .method h3 { font-family:var(--serif); font-size:1.3rem; margin:2rem 0 .6rem; }
  .method p, .method li { color:var(--ink); font-size:.98rem; }
  .method .muted { color:var(--muted); }
  .method code { font-family:var(--mono); font-size:.85em; background:color-mix(in srgb,var(--ink) 7%,transparent);
    padding:.1em .4em; border-radius:4px; }
  .steps { list-style:none; padding:0; counter-reset:s; }
  .steps li { position:relative; padding:.5rem 0 .5rem 2.4rem; border-top:1px solid var(--line); }
  .steps li::before { counter-increment:s; content:counter(s); position:absolute; left:0; top:.55rem;
    width:1.6rem; height:1.6rem; border-radius:50%; background:var(--accent); color:var(--paper);
    font-family:var(--mono); font-size:.8rem; display:flex; align-items:center; justify-content:center; }

  footer { margin-top:3rem; padding-top:1.4rem; border-top:1px solid var(--line); color:var(--muted);
    font-size:.85rem; }
  a { color:var(--accent); }
  audio:focus-visible, .tab:focus-visible, .fbtn:focus-visible { outline:2px solid var(--accent); outline-offset:2px; }
</style>
</head>
<body>
<div class="wrap">
  <header class="masthead">
    <p class="eyebrow">Audiobook pipeline · hallucinated-outburst audit</p>
    <h1>Where the voice babbles words that were never in the script.</h1>
    <p class="lede">Separate from mispronunciations, XTTS sometimes injects a burst of
      phantom phonemes — slurred non-speech between real words. A vocab-free phoneme model
      finds audio that aligns to <b>no source text</b>; across five chapters that flagged
      <b>{{TOTAL}}</b> chunks. Listen and judge them yourself, then hear what rechunking fixes.</p>
  </header>

  <nav class="tabs" role="tablist">
    <button class="tab active" data-p="spot" role="tab">Spot-check <b>{{TOTAL}}</b></button>
    <button class="tab" data-p="ba" role="tab">Before / after</button>
    <button class="tab" data-p="method" role="tab">Method</button>
  </nav>

  <section class="panel active" id="spot" role="tabpanel">
    <p class="intro">Every flagged chunk, ranked by <b>detection confidence</b>. The tier reflects how
      strongly the signal held up: <b>Confirmed</b> and <b>Likely</b> were corroborated by a second
      check; <b>Borderline</b>/<b>Probable&nbsp;FP</b> are shown so you can hear the weaker end.
      The <span class="babble">babble</span> marker is the approximate spot in the text where the
      phantom audio sits. Play each clip and decide if it is really a defect.</p>
    <div class="filters">{{FILTERS}}</div>
    <div class="cases" id="spot-list">
{{SPOT_CASES}}
    </div>
  </section>

  <section class="panel" id="ba" role="tabpanel">
    <p class="intro">The <b>rechunk/rebuild test</b>: each babbling chunk was regenerated a few times
      as-is (control) and again after re-chunking with the fix (paragraph split + trailing-quote
      strip). Because XTTS is stochastic, the control arm shows how often it babbles by chance;
      the fix arm shows the real reduction.</p>
    {{BA}}
  </section>

  <section class="panel method" id="method" role="tabpanel">
    <h3>What counts as a hallucination</h3>
    <p>The expected pronunciation of the chunk (<code>espeak-ng</code> grapheme-to-phoneme) is
      aligned against the phonemes a vocabulary-free <code>wav2vec2</code> model actually hears.
      A run of ≥5 audio phones that aligns to <b>no</b> source text is a phantom outburst — the
      model voicing something the script never asked for.</p>
    <h3>How a flag earns its tier</h3>
    <ol class="steps">
      <li>Wide scan over <b>every</b> rendered chunk finds injected-phoneme runs.</li>
      <li>A false-positive filter drops onomatopoeia and G2P-unreliable text, and cross-checks
        against Whisper word insertions; survivors are tiered <b>confirmed / likely / borderline</b>.</li>
      <li>The spot-check tab is that tiered list — model-derived, <span class="muted">not hand-verified</span>,
        which is exactly why it is here to be reviewed by ear.</li>
    </ol>
    <h3>The fix</h3>
    <p>Two triggers caused most outbursts: an internal <code>."\n\n</code> paragraph boundary inside
      a chunk, and a trailing closing quote at a chunk's end. The chunker now splits paragraphs and
      strips trailing quotes. The <b>Before / after</b> tab measures how much that actually removes.</p>
    <h3 class="muted" style="font-family:var(--serif)">Honest caveats</h3>
    <p class="muted">The tiers are model judgments, not ground truth. A residual set (mid-chunk babble,
      trailing proper nouns, onomatopoeia) is not addressed by the chunking fix. The per-chunk rate is
      a screen for review, not a precision quality metric.</p>
  </section>

  <footer>
    <p>Books 6–7, chapters 3/8/12/14/15. Detection: <code>scan_hallucinations.py</code> +
      <code>filter_hallucinations.py</code>. Rebuild test: <code>rechunk_rebuild_test.py</code>.
      All audio is the actual shipped narration (spot-check) or freshly rebuilt chunks (before/after).</p>
  </footer>
</div>
<script>
  const tabs = document.querySelectorAll('.tab');
  tabs.forEach(t => t.addEventListener('click', () => {
    tabs.forEach(x => x.classList.remove('active'));
    document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
    t.classList.add('active');
    document.getElementById(t.dataset.p).classList.add('active');
  }));
  document.querySelectorAll('.fbtn').forEach(b => b.addEventListener('click', () => {
    document.querySelectorAll('.fbtn').forEach(x => x.classList.remove('active'));
    b.classList.add('active');
    const f = b.dataset.f;
    document.querySelectorAll('#spot-list .case').forEach(c => {
      c.style.display = (f === 'all' || c.dataset.tier === f) ? '' : 'none';
    });
  }));
</script>
</body>
</html>"""


if __name__ == "__main__":
    main()
