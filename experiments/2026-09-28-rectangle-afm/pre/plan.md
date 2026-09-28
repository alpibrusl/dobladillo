# 2026-09-28-rectangle-afm

**Part.** `rectangle`

## What this is for

One paragraph. What question does this answer, and what would change if the
answer came back the other way? If nothing would change, the experiment is not
worth the oligos.

## The gate

**Write this before taking data.** What result makes this a failure?

A gate decided afterwards is a description of the data. This is the single
most important line in the folder, and it is the one most easily written last.

> criterion:

### Proposed, not adopted: the gate from `2026-09-22-rectangle-afm`

This folder replaces `2026-09-22-rectangle-afm`, which was scaffolded before the design
was re-tiled (its `pre/RETILED.md` explains why). Its gate is quoted below,
unchanged, as a starting point. **It is not this folder's gate.** An agent may
not write a gate, and one copied across unexamined is not a decision either.
The experimentalist decides, writes the gate into the `criterion:` line above
and commits `pre/`, all before taking data.

> **Fold.** A gel shows a dominant band at the expected mobility, distinct
> from free scaffold. Without this, nothing below is worth measuring.
>
> **Shape.** At least 50 particles clear of the frame edge, and the
> tip-corrected long and short edges within 10% of the predicted 106.2 and
> 66.0 nm. Ten per cent, not five: the tip radius alone carries more than
> five, and a tighter gate would be failing the tip rather than the design.
>
> **Flatness.** Height within 30% of 2.0 nm, and no systematic curvature
> across the sheet. This is the one the experiment is really for, and it is
> the one with no prior from this project at all.
>
> **Failure.** A well-formed fraction below 25% means the fold or the
> deposition is wrong, and the dimensions of the survivors do not say which.
> That is a result: it sends us back to the Mg screen, not onward.

### New in this folder: a positive-control arm

Fold a **known-good rectangle** alongside ours, in the same session, from the
same buffers, deposited and imaged the same way. If ours fails and the control
folds, the design pipeline is at fault. If both fail, it is the bench. E1 had
no way to tell those apart, and this project's designs have already been wrong
once without anyone noticing (`2026-09-22-rectangle-afm/pre/RETILED.md`).

The control is bought, not designed here, so choosing it is a purchase and the
supervisor's call. Either:

- a commercial rectangle kit, folded exactly to its supplier's protocol; or
- the published Rothemund (2006) rectangle, ordered like ours.

Record which in `during/log.md`, with its lot or order number. The control has
no prediction from this toolchain, and none should be invented. It either
folds into countable rectangles or it does not. A reasonable gate line to
consider: *the control shows at least 50 recognisable rectangles, or the
session is void and says nothing about our design.*

## What is predicted

From `pre/prediction.json`, recorded when this folder was made:

| quantity | predicted |
|---|---|
| length | 106.2 nm |
| width | 66.0 nm |
| height | 2.0 nm |

An AFM will not measure these directly. A half-height footprint is wider than
the object by twice `sqrt(R h - h^2/4)` for a tip of radius R -- about 8.7 nm
for a 10 nm tip on a 2 nm plate, which is a quarter of a 36 nm width. The
toolchain removes it in `post/`, using the tip radius from
`during/instrument.json`, which is why that field is not optional.

## Checklist before starting

- [ ] Gate written above
- [ ] `pre/` committed to git, so the prediction provably predates the data
- [ ] Oligos ordered from `pre/order/`
- [ ] Tip radius measured and written into `during/instrument.json`
