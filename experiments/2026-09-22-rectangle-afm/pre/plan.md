# 2026-09-22-rectangle-afm

**Part.** `rectangle`

Full design: `docs/AFM_FIRST_TRIAL.md`, and the PDF in `docs/pdf/`.

## What this is for

The first structure this toolchain has designed, imaged. Long edge, short
edge, height and well-formed fraction all have predicted counterparts already
computed, so they test the pipeline rather than the design.

The one thing we are genuinely unsure of is **flatness**. The square lattice
implies 10.67 bp/turn against a relaxed 10.5 and would twist the sheet; we
cancel it by deleting one base every 64, which works exactly on paper.
Whether it cancels in practice is visible in an AFM image and nowhere else.

If the sheets come back visibly twisted, the twist correction is wrong and
`constants.SQUARE_TWIST_CORRECTION_PERIOD_BP` and everything built on it need
revisiting -- which is most of the design side.

## The gate

**Write this before taking data.** What result makes this a failure?

A gate decided afterwards is a description of the data. This is the single
most important line in the folder, and it is the one most easily written last.

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
