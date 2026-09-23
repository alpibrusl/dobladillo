# 2026-09-23-twist-pair

**Part.** `twist-corrected`

Full design: `docs/TWIST_PAIR_EXPERIMENT.md`, and the PDF in `docs/pdf/`.

## What this is for

The square lattice calls 32 bp three turns, which implies 10.67 bp/turn against
B-DNA's relaxed 10.5. Every square-lattice design in this project deletes one
base every 64 to cancel the resulting twist. It works exactly on paper.

Two arms, identical but for those deletions. The uncorrected one is predicted
to carry 309 degrees of twist and be unable to lie flat.

**What changes if it comes back the other way:** if both arms lie flat equally
often, the correction is unnecessary and comes out of every design on this
lattice. If the corrected arm is worse, something about the deletions is
wrong and `constants.SQUARE_TWIST_CORRECTION_PERIOD_BP` needs revisiting —
along with everything built on it.

## The gate

**Write this before taking data.** What result makes this a failure?

A gate decided afterwards is a description of the data. This is the single
most important line in the folder, and it is the one most easily written last.

> **Both arms, same session, same tip, randomised order.** The measurement is
> a difference between two constructs, so anything that drifts between them
> becomes the result.
>
> **At least 50 particles clear of the frame edge per arm.** The readout is a
> proportion; 50 gives a Wilson interval around 12 points wide, which is
> narrower than the difference worth acting on.
>
> **Pass.** The corrected arm's flat fraction exceeds the uncorrected arm's by
> more than 10 points, with a 95% Newcombe interval on the difference that
> excludes zero.
>
> **Also a pass, and the more useful one if it happens.** The two arms are
> indistinguishable. Then the twist correction is unnecessary, and we stop
> deleting one base in every 64 from every square-lattice design — which is
> most of them. This is a result, not a failed experiment.
>
> **Fail.** Fewer than 50 countable particles in either arm, or the two arms
> differ in something other than the deletions.

## What is predicted

From `pre/prediction.json`, recorded when this folder was made:

| quantity | predicted |
|---|---|
| length | 191.2 nm |
| width | 36.0 nm |
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
