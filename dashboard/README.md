# Dashboard

**Generated, not written.** `site/index.html` is produced by:

```bash
dobladillo dashboard --out dashboard/site
```

Every figure on the page is read from the toolchain at generation time —
construct counts and costs from `hamiltonian.experiments`, tip corrections from
`compare.corrections`, designed dimensions from the parts, and the lint state by
actually running the rules. Nothing is typed into the page.

That is the whole reason it exists in this form. The hand-written version it
replaced had to carry a note in its own README admitting it would go stale, and
it did: it was published claiming every part was clean, and an hour later the
six-helix bundle failed a new rule. The generated page reports that defect
because it runs the linter, and will stop reporting it when the routing is
fixed.

## Shape cards

With `--runs <dir>`, a part that has a finished oxDNA run there gets an outline
drawn against its design. That panel exists because of a specific failure: the
six-helix bundle came back at 328 × 70 nm against a design of 390 × 8 and
nothing in the numbers read as wrong — they are all plausible sizes. It was a
269 nm arc, invisible until somebody asked why the middle extent was 70 nm on
an 8 nm rod.

Each outline is labelled with **what it is**, because a designed rectangle, a
simulated envelope and a tip-broadened AFM footprint are three different
quantities. Drawing them on one axis without saying so would show a
disagreement that is mostly tip radius, which is exactly the error
`compare` refuses to make.

Each card also carries a **form deviation**, and size and form are measured
apart on purpose. A simulated length disagrees with its design by a few per
cent for reasons nobody needs to investigate — an idealised base count against
a thermally fluctuating object with ends — so `compare` makes a size difference
clear a 3% allowance before it means anything. A part designed straight has a
designed straightness of *exactly zero*, and nothing about thermal fluctuation
bends a rod one way and keeps it there. Any sustained deviation there is
unexplained by construction, which makes it the more sensitive measure despite
being the cruder one. It is reported in the part's own thickness, because
50 nm is nothing on a 400 nm plate and damning on an 8 nm rod.

The simulated outline is an envelope rather than a convex hull: a hull of a
bent rod is a lens, and the flat side hides how far the centreline went.
Frames are superimposed before averaging, because in the box frame a tumbling
object averages to a disc.

The scores in the experiment table are judgements and live in
`dobladillo/programme.py`, typed with the reasoning attached, because a number
like `0.35` with no rationale is unfalsifiable and reads as a calculation.
`experiments/ROADMAP.md` is the same programme as prose; a test asserts the two
list the same experiments, which is the only thing stopping them diverging.

The page is one self-contained file. No build step, no assets, no framework:
open it from a `file://` URL, serve the directory, or publish it. Its own state
is embedded as JSON in a `<script id="state">` tag so anything reading it
mechanically does not have to parse the presentation.

`site/` is committed so the current board is readable on GitHub without
running anything. Regenerate it in the same commit as any change that moves a
number.
