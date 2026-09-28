"""Render the gathered state as one self-contained HTML page.

No template engine and no build step: the page is a string, the only external
request is Google Fonts, and the output opens from a file:// URL. That is a
deliberate constraint rather than laziness -- a dashboard somebody has to build
before they can read it is a dashboard nobody reads.
"""

from __future__ import annotations

import html
import json
from typing import Any

from dobladillo.dashboard.state import FILM_THICKNESS_NM, State

_CSS = """
:root{--ground:#EDF1F4;--surface:#FFF;--sunk:#E2E8ED;--raise:#F7F9FA;--ink:#131B23;
--muted:#5B6874;--faint:#8A97A3;--rule:#CCD6DE;--accent:#1B6C88;--accent-soft:#DCEBF0;
--ready:#2C7A4B;--ready-soft:#DDEDE3;--blocked:#9C6A14;--blocked-soft:#F3E8D2;
--bad:#9B3A38;--bad-soft:#F2DEDD;--bar:#B6C4CE;
--fd:"Archivo",system-ui,sans-serif;--fb:"Source Sans 3",system-ui,sans-serif;
--fm:"JetBrains Mono",ui-monospace,monospace}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
--ground:#0D1318;--surface:#141C23;--sunk:#101820;--raise:#1A242C;--ink:#E4EAEF;
--muted:#94A3AF;--faint:#6B7885;--rule:#243039;--accent:#5FB6D1;--accent-soft:#122A33;
--ready:#63C08A;--ready-soft:#12251A;--blocked:#D7A44A;--blocked-soft:#2A2113;
--bad:#E08480;--bad-soft:#2B1615;--bar:#33424E}}
:root[data-theme="dark"]{--ground:#0D1318;--surface:#141C23;--sunk:#101820;--raise:#1A242C;
--ink:#E4EAEF;--muted:#94A3AF;--faint:#6B7885;--rule:#243039;--accent:#5FB6D1;
--accent-soft:#122A33;--ready:#63C08A;--ready-soft:#12251A;--blocked:#D7A44A;
--blocked-soft:#2A2113;--bad:#E08480;--bad-soft:#2B1615;--bar:#33424E}
*{box-sizing:border-box}
body{margin:0;background:var(--ground);color:var(--ink);font-family:var(--fb);font-size:16px;
line-height:1.55;-webkit-font-smoothing:antialiased}
.wrap{max-width:70rem;margin:0 auto;padding:clamp(1.5rem,4vw,3rem) clamp(1rem,3vw,2rem) 4rem;
display:flex;flex-direction:column;gap:1.5rem}
h1,h2{font-family:var(--fd);margin:0;text-wrap:balance}
h1{font-size:clamp(1.75rem,1.3rem + 2vw,2.6rem);font-weight:700;letter-spacing:-.02em;line-height:1.05}
h2{font-size:1.15rem;font-weight:600}
p{margin:0}
.mono,td.num,.stat .v{font-family:var(--fm);font-variant-numeric:tabular-nums}
.eyebrow{font-family:var(--fm);font-size:.68rem;letter-spacing:.13em;text-transform:uppercase;
color:var(--faint);font-weight:500}
header{display:flex;flex-direction:column;gap:.6rem;padding-bottom:1.25rem;border-bottom:2px solid var(--ink)}
.lede{color:var(--muted);max-width:56ch;font-size:1.05rem}
.strip{display:grid;gap:.75rem;grid-template-columns:repeat(auto-fit,minmax(11rem,1fr))}
.stat{background:var(--surface);border:1px solid var(--rule);border-radius:4px;padding:.8rem .9rem;
display:flex;flex-direction:column;gap:.15rem}
.stat .v{font-size:1.5rem;font-weight:500;line-height:1.1}
.stat .k{font-size:.78rem;color:var(--muted)}
.stat.go{border-left:3px solid var(--ready)}.stat.go .v{color:var(--ready)}
.stat.bad{border-left:3px solid var(--bad)}.stat.bad .v{color:var(--bad)}
.panel{background:var(--surface);border:1px solid var(--rule);border-radius:4px;overflow:hidden}
.panel>.head{padding:.85rem 1rem;border-bottom:1px solid var(--rule);background:var(--raise);
display:flex;justify-content:space-between;align-items:baseline;gap:1rem;flex-wrap:wrap}
.panel>.body{padding:1rem;display:flex;flex-direction:column;gap:.9rem}
.scroll{overflow-x:auto}
table{width:100%;border-collapse:collapse;font-size:.88rem}
th{font-family:var(--fm);font-size:.64rem;letter-spacing:.09em;text-transform:uppercase;
color:var(--faint);font-weight:500;text-align:left;padding:.5rem .7rem;white-space:nowrap;
border-bottom:1px solid var(--rule)}
td{padding:.55rem .7rem;border-bottom:1px solid var(--rule);vertical-align:middle}
tbody tr:last-child td{border-bottom:0}
td.num{white-space:nowrap}
.id{font-family:var(--fm);font-weight:500;color:var(--accent)}
.pill{display:inline-block;font-family:var(--fm);font-size:.66rem;letter-spacing:.05em;
text-transform:uppercase;padding:.16rem .45rem;border-radius:3px;white-space:nowrap;font-weight:500}
.p-ready{background:var(--ready-soft);color:var(--ready)}
.p-blocked{background:var(--blocked-soft);color:var(--blocked)}
.p-bad{background:var(--bad-soft);color:var(--bad)}
.bar{display:inline-flex;gap:2px;vertical-align:middle}
.bar i{width:6px;height:13px;background:var(--bar);border-radius:1px;display:block}
.bar i.on{background:var(--accent)}
.bar.risk i.on{background:var(--blocked)}
.cols{display:grid;gap:1.5rem;grid-template-columns:repeat(auto-fit,minmax(20rem,1fr));align-items:start}
.note{background:var(--sunk);border-left:3px solid var(--accent);padding:.85rem 1rem;
display:flex;flex-direction:column;gap:.45rem;border-radius:0 3px 3px 0}
.note.warn{border-left-color:var(--blocked)}
.note.bad{border-left-color:var(--bad)}
.note p{font-size:.92rem;max-width:62ch}
pre{margin:0;background:var(--sunk);border:1px solid var(--rule);border-radius:3px;
padding:.75rem .85rem;overflow-x:auto;font-family:var(--fm);font-size:.8rem;line-height:1.7}
ol{margin:0;padding-left:1.15rem;display:flex;flex-direction:column;gap:.4rem;font-size:.93rem}
strong{font-weight:600}
footer{color:var(--muted);font-size:.85rem;border-top:1px solid var(--rule);padding-top:1.25rem;
display:flex;flex-direction:column;gap:.5rem}
:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
"""

_FONTS = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
    "family=Archivo:wght@500;600;700&family=JetBrains+Mono:wght@400;500"
    '&family=Source+Sans+3:wght@400;500;600&display=swap">'
)


def _e(text: Any) -> str:
    return html.escape(str(text), quote=True)


def _bars(value: int, *, risk: bool = False) -> str:
    cells = "".join('<i class="on"></i>' if i < value else "<i></i>" for i in range(5))
    return f'<span class="bar{" risk" if risk else ""}">{cells}</span>'


def _experiments(state: State) -> str:
    rows = []
    for experiment in state.experiments:
        if experiment.ready:
            badge = '<span class="pill p-ready">ready</span>'
        else:
            badge = f'<span class="pill p-blocked">{_e(experiment.blocked_by)}</span>'
        rows.append(
            f'<tr><td class="id">{_e(experiment.id)}</td>'
            f"<td>{_e(experiment.title)}</td>"
            f"<td>{_bars(experiment.relevance)}</td>"
            f"<td>{_bars(experiment.difficulty, risk=True)}</td>"
            f'<td class="num">{experiment.success:.2f}</td>'
            f"<td>{badge}</td></tr>"
        )
    return (
        '<div class="scroll"><table><thead><tr><th></th><th>experiment</th>'
        "<th>relevance</th><th>difficulty</th><th>P(success)</th><th>state</th>"
        f"</tr></thead><tbody>{''.join(rows)}</tbody></table></div>"
    )


def _shapes(state: State) -> str:
    """One outline card per part that has something to draw.

    Each outline is labelled with what it is, because a designed rectangle, a
    simulated envelope and a tip-broadened footprint are three different
    quantities and overlaying them silently is the error `compare` exists to
    prevent.
    """
    from dobladillo.dashboard.shapes import svg

    cards = []
    for part in state.parts:
        if len(part.outlines) < 2:
            continue
        drawing = svg(list(part.outlines))
        notes = "".join(
            f'<p style="font-size:.82rem;color:var(--muted)">'
            f"<strong>{_e(o.origin)}</strong> — {_e(o.definition)}</p>"
            for o in part.outlines
        )
        from dobladillo.dashboard.shapes import straightness

        verdicts = []
        for outline in part.outlines:
            if outline.origin == "designed":
                continue
            bend = straightness(outline)
            tone = "p-ready" if bend.straight else "p-bad"
            word = "straight" if bend.straight else "BENT"
            verdicts.append(
                f'<p style="font-size:.85rem"><span class="pill {tone}">{word}</span> '
                f"&nbsp;{_e(outline.origin)} centreline departs by "
                f'<span class="mono">{bend.max_nm:.0f} nm</span> '
                f'(<span class="mono">{bend.rms_nm:.0f}</span> rms), which is '
                f'<span class="mono">{bend.in_body_widths:.1f}×</span> its own thickness '
                f'and <span class="mono">{100 * bend.relative:.0f}%</span> of its length.</p>'
            )
        extents = " &nbsp;·&nbsp; ".join(
            f'{_e(o.origin)} <span class="mono">{o.extent_nm[0]:.0f} × '
            f"{o.extent_nm[1]:.0f} nm</span>"
            for o in part.outlines
        )
        cards.append(
            f'<div style="display:flex;flex-direction:column;gap:.5rem">'
            f'<h3 style="font-family:var(--fd);font-size:.95rem;margin:0">{_e(part.name)}</h3>'
            f"{drawing}"
            f'<p style="font-size:.85rem">{extents}</p>'
            f"{''.join(verdicts)}{notes}</div>"
        )
    if not cards:
        return ""
    return (
        '<section class="panel"><div class="head"><h2>Shape</h2>'
        '<span class="eyebrow">drawn to scale, on one pair of axes</span></div>'
        f'<div class="body">{"".join(cards)}'
        '<div class="note"><span class="eyebrow">Why this is here</span>'
        "<p>The six-helix bundle came back from oxDNA at 328 × 70 nm against a design of "
        "390 × 8, and nothing in the numbers read as wrong — they are all plausible sizes. "
        "It was a 269 nm arc, and it stayed invisible until somebody asked why the middle "
        "extent was 70 nm on an 8 nm rod. An outline shows a banana immediately.</p>"
        "<p><strong>Size and form are measured apart on purpose.</strong> A simulated "
        "length disagrees with its design by a few per cent for reasons nobody needs to "
        "investigate — an idealised base count against a fluctuating object with ends — "
        "so a size difference has to clear a 3% allowance before it means anything. A "
        "part designed straight has a designed straightness of <em>exactly zero</em>, and "
        "nothing about thermal fluctuation bends a rod one way and keeps it there. Any "
        "sustained deviation here is unexplained by construction.</p></div>"
        "</div></section>"
    )


def _parts(state: State) -> str:
    rows = []
    for part in state.parts:
        size = " x ".join(f"{v:g}" for v in part.dimensions_nm.values())
        if part.clean:
            badge = '<span class="pill p-ready">clean</span>'
        else:
            badge = f'<span class="pill p-bad">{part.violations} x {_e(part.worst)}</span>'
        if not part.has_run:
            run = ""
        elif part.run_matches is None:
            run = ' <span class="pill p-blocked">run: no design hash</span>'
        elif part.run_matches:
            run = ' <span class="pill p-ready">run: same design</span>'
        else:
            run = (
                f' <span class="pill p-bad">run: design {_e(_short(part.run_design_sha256))}</span>'
            )
        rows.append(
            f"<tr><td>{_e(part.name)}</td>"
            f'<td class="num">{_e(size)} nm</td>'
            f'<td class="num">{part.staples}</td>'
            f'<td><span class="mono">{_e(_short(part.design_sha256))}</span>{run}</td>'
            f"<td>{badge}</td></tr>"
        )
    return (
        '<div class="scroll"><table><thead><tr><th>part</th><th>size</th>'
        f"<th>staples</th><th>design</th><th>lint</th></tr></thead><tbody>{''.join(rows)}</tbody>"
        "</table></div>"
    )


def _tips(state: State) -> str:
    head = "".join(f"<th>{h:g} nm film</th>" for h in FILM_THICKNESS_NM)
    rows = []
    for entry in state.tip_table:
        cells = "".join(
            f'<td class="num">+{entry["widening_nm"][h]} nm</td>' for h in FILM_THICKNESS_NM
        )
        rows.append(f'<tr><td class="num">{entry["radius_nm"]:g} nm</td>{cells}</tr>')
    return (
        f'<div class="scroll"><table><thead><tr><th>tip radius</th>{head}</tr></thead>'
        f"<tbody>{''.join(rows)}</tbody></table></div>"
    )


def _folders(state: State) -> str:
    if not state.folders:
        return (
            '<p style="color:var(--muted);font-size:.92rem">No experiment folders yet. '
            '<span class="mono">dobladillo experiment new</span> scaffolds one.</p>'
        )
    rows = []
    for folder in state.folders:
        if folder["problems"]:
            badge = '<span class="pill p-bad">record problem</span>'
        elif folder["ready_for"] is None:
            badge = '<span class="pill p-ready">complete</span>'
        else:
            badge = f'<span class="pill p-blocked">next: {_e(folder["ready_for"])}</span>'
        phases = " ".join(
            f'<span class="pill {"p-ready" if ok else "p-blocked"}">{_e(name)}</span>'
            for name, ok in folder["phases"].items()
        )
        rows.append(
            f"<tr><td>{_e(folder['name'])}</td><td>{phases}</td>"
            f"<td>{_chain(folder.get('provenance'))}</td><td>{badge}</td></tr>"
        )
    return (
        '<div class="scroll"><table><thead><tr><th>folder</th><th>phases</th>'
        "<th>provenance</th>"
        f"<th>state</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>"
    )


def _short(digest: str | None) -> str:
    return digest[:8] if digest else "none"


def _chain(summary: dict[str, Any] | None) -> str:
    """design → order → scans, each named by its hash, and whether they agree.

    A legacy folder says so in words rather than showing an empty chain,
    because "no design hash recorded" is the finding, not a blank.
    """
    if not summary or summary.get("legacy"):
        return '<span class="pill p-bad">no design hash recorded</span>'
    design = summary.get("design_sha256")
    ordered = summary.get("ordered_designs") or []
    order_text = ", ".join(_short(d) for d in ordered) if ordered else "no manifest"
    tone = "p-ready" if summary.get("verified") else "p-bad"
    word = "chain holds" if summary.get("verified") else "chain broken"
    return (
        f'<span class="mono">design {_e(_short(design))} → order {_e(order_text)} → '
        f"{int(summary.get('scans', 0))} scan(s)</span> "
        f'<span class="pill {tone}">{word}</span>'
    )


def render(state: State, *, generated: str = "") -> str:
    """The whole page, as a string."""
    ready = [e for e in state.experiments if e.ready]
    first = ready[0] if ready else None
    broken = [p for p in state.parts if not p.clean]
    cost = state.programme_cost

    stat_ready = (
        f'<div class="stat go"><span class="v">{_e(first.id)}</span>'
        f'<span class="k">ready to run now</span></div>'
        if first
        else '<div class="stat bad"><span class="v">0</span>'
        '<span class="k">nothing is ready</span></div>'
    )
    stat_parts = (
        f'<div class="stat bad"><span class="v">{len(broken)}</span>'
        f'<span class="k">part{"s" if len(broken) != 1 else ""} failing lint</span></div>'
        if broken
        else f'<div class="stat go"><span class="v">{len(state.parts)}</span>'
        '<span class="k">parts, all lint clean</span></div>'
    )

    first_block = ""
    if first:
        first_block = f"""
<section class="panel"><div class="head"><h2>Start here — {_e(first.id)}, {_e(first.title)}</h2>
<span class="pill p-ready">ready</span></div>
<div class="body"><p>{_e(first.why)}</p>
<pre>dobladillo experiment check experiments/&lt;folder&gt;</pre></div></section>"""

    broken_block = ""
    if broken:
        items = "".join(
            f"<p><strong>{_e(p.name)}</strong> — {p.violations} hard violation"
            f'{"s" if p.violations != 1 else ""}, worst <span class="mono">'
            f"{_e(p.worst)}</span>.</p>"
            for p in broken
        )
        broken_block = f"""
<div class="note bad"><span class="eyebrow">A part does not satisfy its own rules</span>
{items}<p>Generated by running the rules, not recorded by hand — so this clears itself
when the routing is fixed.</p></div>"""

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Dobladillo experiment board</title>{_FONTS}
<style>{_CSS}</style></head><body><div class="wrap">

<header><span class="eyebrow">Dobladillo {_e(state.version)} &middot; design → simulate → fold → measure → compare</span>
<h1>Experiment board</h1>
<p class="lede">A toolchain for DNA origami that predicts what a structure should measure,
then checks itself against what the instrument says. Every number on this page is read
from the toolchain when the page is generated.</p></header>

<div class="strip">{stat_ready}
<div class="stat"><span class="v">{len(state.experiments)}</span><span class="k">experiments planned</span></div>
<div class="stat"><span class="v">&euro;{cost["total_eur"]:,.0f}</span><span class="k">all Hamiltonian stages</span></div>
{stat_parts}</div>
{first_block}
<section class="panel"><div class="head"><h2>The sequence</h2>
<span class="eyebrow">scores are judgements, not calculations</span></div>
{_experiments(state)}
<div class="body"><div class="note warn">
<span class="eyebrow">The critical path multiplies to {state.critical_probability:.0%}</span>
<p>{" → ".join(_e(i) for i in state.critical_path)}. A product of independent judgements,
which is crude — and stated anyway, because it locates the value in the early, cheap
experiments and depends on <strong>failure being informative at every stage</strong>.</p>
</div></div></section>

{_shapes(state)}
<div class="cols">
<section class="panel"><div class="head"><h2>Parts</h2></div>
{_parts(state)}<div class="body">{broken_block}</div></section>

<section class="panel"><div class="head"><h2>At the bench</h2></div>
<div class="body"><div class="note warn">
<span class="eyebrow">Measure the tip. Before and after.</span>
<p>A half-height footprint is wider than the object by twice
<span class="mono">&radic;(R&middot;h &minus; h&sup2;/4)</span>. A nominal 10 nm tip is
routinely 8&ndash;20 nm in use, and the correction goes as &radic;R, so the tooling
<strong>refuses to run</strong> without a measured value rather than substituting the
nominal one.</p></div>
{_tips(state)}</div></section>
</div>

<section class="panel"><div class="head"><h2>Experiment folders</h2></div>
<div class="body">{_folders(state)}
<div class="note"><span class="eyebrow">Commit <span class="mono">pre/</span> before the session</span>
<p>The comparison will reconcile a measurement with whatever is predicted. A prediction
adjusted after seeing a scan produces output <em>identical</em> to one made in advance, so
the distinction lives in the record and the tooling checks the timestamps.</p>
<p>The provenance column names the design the prediction is of and the design the
oligos were ordered from, by content hash. <span class="mono">experiment report</span>
refuses when they differ: a prediction tested against a different object is not a test.</p></div>
<pre>dobladillo afm read     during/raw/scan.gsf
dobladillo experiment report  &lt;folder&gt;</pre></div></section>

<footer><p><strong>Regenerate:</strong> <span class="mono">dobladillo dashboard --out site/</span>.
Nothing here is edited by hand; every figure is read from the toolchain at generation time.</p>
<p>{_e(generated) if generated else "Generated from the working tree."}
Start at <span class="mono">experiments/README.md</span>;
<span class="mono">experiments/AGENTS.md</span> is the brief for an AI assistant.</p></footer>
</div>
<script id="state" type="application/json">{json.dumps(state.as_dict())}</script>
</body></html>"""
