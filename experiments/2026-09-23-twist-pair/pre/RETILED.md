# Re-tiled before any data — 2026-09-28

The oligos in `order/` were regenerated on 2026-09-28, before any order was
placed and before any sample existed. Only the order files changed.

**Why.** The first staple tiling put two crossovers to the same neighbouring
helix 16 bp apart. That is a turn and a half, so one crossover in each pair
sat on the far side of the helix from its partner. Measured against published
designs with `dobladillo.routing.azimuth`, it was randomly phased: 89° rms
phasing strain, against 18–22° for every reference design. Both arms are now
built by scadnano's `origami_rectangle.create`, which is Rothemund's pattern:
the crossover partner alternates every 16 bp. The corrected arm scores 21°.
The uncorrected arm scores 18° of phasing strain plus −310° of twist along its helices — the twist this experiment exists to
show, and within 1° of the 309° `parts.twist_pair` predicts.

**What did not change.** The helix count, the length, the scaffold and its
rotation, the routed scaffold length, the number of deletions and the number
of staples are the same. So `prediction.json`'s predicted dimensions still
hold. So does every volume in `order/pipetting.json` and in the student
protocol, because they depend only on the staple count.

**One stale field, left as it is.** `prediction.json` lists staple lengths
`[30, 32]`; the re-tiled design has `[30, 31, 32]`. Agents do not edit
`prediction.json` (see `../../AGENTS.md`). The experimentalist decides whether
to regenerate it. Staple lengths are not a prediction that `post/` compares
against.

To check the current design yourself:

```bash
uv run dobladillo lab order twist-corrected
uv run dobladillo lab order twist-uncorrected
uv run pytest tests/test_rules.py -k azimuth
```
