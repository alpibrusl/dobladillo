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
