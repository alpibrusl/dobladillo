# Bench protocols

> ## ⚠ Do not order oligos for E1, E2 or E3 yet — 2026-09-28
>
> The square-lattice designs these experiments use (the rectangle, both
> twist-pair arms, the hinge) place **half their staple crossovers on the wrong
> face of the helix**: two crossovers to the same neighbour 16 bp apart, where
> the backbone has turned about 180°. Measured with scadnano's own geometry
> against published designs, they score as randomly phased (≈90° rms strain)
> where published square designs score ≈31°. The designs are being re-tiled;
> the order files in each experiment's `pre/order/` are wrong until then.
> The protocols themselves stand — only the oligos change.

Step-by-step protocols for running this project's experiments, written for a
student who has basic molecular-biology bench experience (pipetting, gels, a
thermocycler) but has never folded DNA origami or used this toolchain.

| protocol | experiment | status |
|---|---|---|
| [`common-techniques.md`](common-techniques.md) | shared by all | read first |
| [`E1-rectangle-afm.md`](E1-rectangle-afm.md) | E1 — does our first design fold? | **blocked: re-tiling** |
| [`E2-twist-pair.md`](E2-twist-pair.md) | E2 — is the twist correction needed? | **blocked: re-tiling** |
| [`E3-single-hinge.md`](E3-single-hinge.md) | E3 — does the hinge fold at all? | **blocked: re-tiling** |

E4–E7 need software that does not exist yet; their protocols will be written
when it does. See `../ROADMAP.md`.

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
