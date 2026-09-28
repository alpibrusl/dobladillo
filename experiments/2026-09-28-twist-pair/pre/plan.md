# 2026-09-28-twist-pair

**Part.** `twist-corrected`

## What this is for

One paragraph. What question does this answer, and what would change if the
answer came back the other way? If nothing would change, the experiment is not
worth the oligos.

## The gate

**Write this before taking data.** What result makes this a failure?

A gate decided afterwards is a description of the data. This is the single
most important line in the folder, and it is the one most easily written last.

> criterion:

### Proposed, not adopted: the gate from `2026-09-23-twist-pair`

This folder replaces `2026-09-23-twist-pair`, which was scaffolded before the design
was re-tiled (its `pre/RETILED.md` explains why). Its gate is quoted below,
unchanged, as a starting point. **It is not this folder's gate.** An agent may
not write a gate, and one copied across unexamined is not a decision either.
The experimentalist decides, writes the gate into the `criterion:` line above
and commits `pre/`, all before taking data.

> **Both arms, same session, same tip, randomised order.** The measurement is
> a difference between two constructs, so anything that drifts between them
> becomes the result.
>
> **At least 100 particles clear of the frame edge per arm; 300 if cheap.**
> The readout is a proportion: at 100 a fraction near 70% carries about ±9%,
> at 300 about ±5%, and below 100 the arms could differ a lot and still not be
> distinguishable. (An earlier draft of this gate said 50; the design document
> says 100, and the design document wins.)
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
> **Fail.** Fewer than 100 countable particles in either arm, or the two arms
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
