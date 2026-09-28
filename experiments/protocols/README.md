# Bench protocols

> ## Re-tiled designs — 2026-09-28
>
> Every square-lattice design here (rectangle, both twist-pair arms, hinge)
> first placed half its staple crossovers on the wrong face of the helix. All
> were re-tiled before any order was placed, and now score like published
> designs. E1's and E2's `pre/order/` files are current; each has a
> `pre/RETILED.md`. The hinge now has 132 staples, and E3's volumes below are
> updated. E3 still waits on its footprint prediction, not on the design.

Step-by-step protocols for running this project's experiments, written for a
student who has basic molecular-biology bench experience (pipetting, gels, a
thermocycler) but has never folded DNA origami or used this toolchain.

| protocol | experiment | status |
|---|---|---|
| [`common-techniques.md`](common-techniques.md) | shared by all | read first |
| [`E1-rectangle-afm.md`](E1-rectangle-afm.md) | E1 — does our first design fold? | ready (re-tiled 2026-09-28) |
| [`E2-twist-pair.md`](E2-twist-pair.md) | E2 — is the twist correction needed? | ready (re-tiled 2026-09-28) |
| [`E3-single-hinge.md`](E3-single-hinge.md) | E3 — does the hinge fold at all? | blocked: footprint prediction |

E4–E7 need software that does not exist yet; their protocols will be written
when it does. See `../ROADMAP.md`. E4's analysis chain can already be dry-run
on synthetic FRET data (`e4_dryrun.py`, no real data accepted), as E1 and E2
were on synthetic scans.

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
