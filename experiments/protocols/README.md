# Bench protocols

> ## Re-scaffolded — 2026-09-28
>
> Every square-lattice design here first placed half its staple crossovers on
> the wrong face of the helix. All were re-tiled before any order was placed.
> E1 and E2 were then **re-scaffolded into new folders**
> (`experiments/2026-09-28-rectangle-afm`, `experiments/2026-09-28-twist-pair`),
> so their predictions, orders and provenance name the design that will
> actually be folded. The old folders are kept as records and marked
> `SUPERSEDED.md`. The gates are **not yet written**: each new `pre/plan.md`
> quotes the earlier gate as a proposal for the experimentalist to adopt.
> E1 now has a positive-control arm.

Step-by-step protocols for running this project's experiments, written for a
student who has basic molecular-biology bench experience (pipetting, gels, a
thermocycler) but has never folded DNA origami or used this toolchain.

| protocol | experiment | status |
|---|---|---|
| [`common-techniques.md`](common-techniques.md) | shared by all | read first |
| [`E1-rectangle-afm.md`](E1-rectangle-afm.md) | E1 — does our first design fold? (with a positive control) | ready once the gate is written |
| [`E2-twist-pair.md`](E2-twist-pair.md) | E2 — is the twist correction needed? | ready once the gate is written |
| [`E3-single-hinge.md`](E3-single-hinge.md) | E3 — does the hinge fold at all? | blocked: footprint prediction |
| [`E8-patterned-rectangle.md`](E8-patterned-rectangle.md) | E8 — can we put a detail where we want it? | ready once E1 has reported (its Mg, reference height and plates); dry-run on synthetic scans (`e8_dryrun.py`) |
| [`E9-rectangle-dimer.md`](E9-rectangle-dimer.md) | E9 — do two origami assemble? | ready once E1 has reported (its Mg, reference height and plates); dry-run on synthetic scans (`e9_dryrun.py`) |
| [`E10-six-helix-bundle.md`](E10-six-helix-bundle.md) | E10 — does the six-helix bundle fold, and is it straight? | blocked: oxDNA run 2026-09-28-bundle-6hb-unit |
| [`E11-isothermal-folding.md`](E11-isothermal-folding.md) | E11 — how fast, and at what constant temperature, does it fold? | ready once E1 has reported (its magnesium, a fold, and its pool) |

E4–E7 need software that does not exist yet; their protocols will be written
when it does. See `../ROADMAP.md`. E4's analysis chain can already be dry-run
on synthetic FRET data (`e4_dryrun.py`, no real data accepted), as E1 and E2
were on synthetic scans.

## The AFM calibration kit (K series)

A separate project, planned 2026-09-29: an open DNA-origami calibration kit
and method for AFM. See
[`projects/afm-calibration-kit/PROJECT.md`](../../projects/afm-calibration-kit/PROJECT.md)
for its goal, scope, prior art and phases, and
[`MATERIALS.md`](../../projects/afm-calibration-kit/MATERIALS.md) for what to
buy. **K** is for *kit*. The K numbers are their own series and depend on E
experiments where stated. The part `calibration-tile` and the commands
`dobladillo calibrate lateral|tip|drift|report` exist, validated on synthetic
scans only; `calibrate report` finds a K folder's scans by the names the
protocols give them and writes `post/calibration.json`.

| protocol | experiment | status |
|---|---|---|
| [`K1-software-validation.md`](K1-software-validation.md) | K1: does `calibrate` recover known scale, skew, tip and drift, with honest uncertainties? (no lab) | blocked: `calibrate` and the tile part being implemented |
| [`K2-calibration-tile-fold.md`](K2-calibration-tile-fold.md) | K2: does the tile fold, purify and show its marks, and how much do we get? | after E1 and E8; `calibrate` after K1 |
| [`K3-lateral-calibration.md`](K3-lateral-calibration.md) | K3: X, Y and skew on one instrument, air and liquid, against a traceable grating | after K1 and K2 (bundle arm: E10) |
| [`K4-tip-reconstruction.md`](K4-tip-reconstruction.md) | K4: do the tile and the bundle reconstruct the same tip as the GATTA-AFM 3D staircase? Tip wear | after K1, K2 and E10; a purchase |
| [`K5-preparation-sensitivity.md`](K5-preparation-sensitivity.md) | K5: how far do the tile's dimensions move with Mg, Ni, drying and deposition time? | after K3 |
| [`K6-hsafm-scale-drift-markers.md`](K6-hsafm-scale-drift-markers.md) | K6: HS-AFM scale, drift, and hairpin marks against streptavidin under the tip | blocked: HS-AFM access (the maintainer's decision), a movie reader |
| [`K7-kit-format-shelf-life.md`](K7-kit-format-shelf-life.md) | K7: frozen, freeze-thawed, 4 °C or dried on mica: which keeps, for how long? | after K3 and K5; 12 months |
| [`K8-certification.md`](K8-certification.md) | K8: a value with a traceable uncertainty for one batch | after K5 and K7; a partner is the maintainer's decision |

**The same rules apply.** The gate is written by the experimentalist before
the session. `pre/` is committed first. Raw files go in untouched. No number
an instrument should have produced is filled in. Each K protocol leaves its
`> criterion:` line empty and gives a proposal to start from.

## Run them in this order

**E1 first, always.** It tells you which magnesium concentration folds our
designs in your hands, and it gives you a *reference height* for a flat sheet
in your imaging conditions. E2 and E3 both use those two numbers. Running E2
without E1 means guessing both.

## How these protocols work with the toolchain

Each experiment lives in a folder under `experiments/` with three phases:

- `pre/` — the plan, the prediction and the protocol, **committed to git before
  you touch a pipette**;
- `during/` — your session log, the instrument settings, and the raw files;
- `post/` — written by `dobladillo experiment report`. Never edit it by hand.

The single most important habit: **write the gate in `pre/plan.md` and commit
`pre/` before the session.** The gate says what result would count as a
failure. If you write it after seeing data, it is a description of the data,
not a test — and the toolchain checks the commit timestamps and will say so.

If you are working with an AI assistant, it reads `experiments/AGENTS.md`. It
may run commands and draft the interpretation. It may not write the gate, edit
the prediction, touch raw files, or fill in a number an instrument should have
measured. If it tries to, stop it.

## Before your first session

- [ ] Read `common-techniques.md` end to end.
- [ ] Complete your institution's safety induction for the lab and the AFM.
- [ ] Get your supervisor's approval for the oligo order — it is a purchase.
- [ ] Book the AFM and a thermocycler; the gel needs a cold room or an ice bath.
- [ ] Clone the repository and run `uv sync`, then `uv run dobladillo --help`.

## When something goes wrong

Write it in `during/log.md` as it happens, including what you think caused it.
A deviation nobody recorded is indistinguishable from one that did not occur,
and deviations are usually where the interesting results come from. A failed
fold, properly recorded, is a result; an unrecorded success is not.
