# Published designs with measured shapes

Designs this project did not write, for which a shape was **measured** and
published. They score the shape predictor (`mechanics.beam`) against
experiment, which is what `reference_designs/` cannot do: those calibrate
routing, and none of them comes with a measured curvature.

Kept apart from `reference_designs/` on purpose. `tests/test_rules.py` asserts
that every file there passes `crossover_azimuth` with deletions counted, and a
design curved by deletions does not -- its crossovers are strained on purpose.
That conflict is recorded in the benchmark (`dobladillo benchmark`) as a
known failure, per AGENTS.md rule 8, rather than hidden by where the file sits.

| file | what it is | source | licence |
|---|---|---|---|
| `Science09_prot120_98_v3.json` | 3 x 6 honeycomb bundle programmed to bend 120 deg by a gradient of insertions (top row) and deletions (bottom row) | caDNAno 2.5, `cadnano/tests/data/`, commit `ce6ff019b8` (the same commit as `reference_designs/`) -- Dietz, Douglas & Shih, *Science* 325, 725 (2009) | BSD-3-Clause, copyright (c) 2018 Wyss Institute at Harvard University and University of California San Francisco (the repository's LICENSE file also carries GPL-3.0 text) |

sha256 `9659444180251d480bd11aa7f24ffbf52dbd020433a3bfed470903a00b5255b6`.

## The measured value

Dietz, Douglas & Shih 2009, Fig. 3K, read from the NIH author manuscript
(PMC2737683, openly accessible): seven 3 x 6 bundles programmed to bend from
0 to 180 deg in 30 deg steps, bend angles measured on TEM particles. For the
120 deg design, **121 deg, s.d. 8.4 deg, N = 212**.

Conditions: negative-stain TEM of particles folded and purified as in the
paper's methods; the buffer is not transcribed here. Only particles with
three clear stripes along their whole length were measured.

Two things are inferred, not stated by either source, and are said so:

- that this file is the 120 deg design of Fig. 3 -- from its name
  (`Science09_prot120`) and from its content, a 3 x 6 bundle with an
  insertion/deletion gradient across its short axis over the middle 105 bp.
  What `_98` and `v3` denote is not documented;
- which version was measured -- the paper does not name versions.

## Helix 19 is not part of the bundle

The file carries a nineteenth helix at lattice position (22, 9), not adjacent
to the 3 x 6 block. It holds the leftover scaffold loop (with a 27-base
insertion) and two staples, and is joined to the bundle only through
single-stranded scaffold. The beam model cannot hold a body that nothing
constrains, so the benchmark drops it before predicting (`exclude_helices` in
`known_answers.json`). Routing checks see the file as published.
