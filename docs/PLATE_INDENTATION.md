# Plate indentation — epic #3's experiment

Epic #3 offers an AFM group *calibrated nanomechanical test objects*. This is
what makes them worth having, and it is not the thing the roadmap assumed.

Numbers here are produced by `dobladillo.mechanics`, which is a thin bridge to
`alpibrupa/nanoindent`. No contact mechanics are implemented in this project.

## The problem

An AFM indentation curve becomes a Young's modulus through a contact model,
and the default model is Hertz, which assumes an elastic half-space. A DNA
origami plate on mica is 2–12 nm of soft material bonded to something rigid.
The substrate carries load the half-space would have absorbed, the measured
force is higher than Hertz predicts, and the fitted modulus comes out too
large.

How much too large is set by the thin-film parameter `chi = sqrt(R·δ)/h` —
contact size measured in film thicknesses. Solved against nanoindent's
axisymmetric mixed finite-element model, bonded and incompressible, with a
10 nm tip at 0.4 nm indentation:

| layers | h | chi | Hertz fit reads | closed forms disagree by |
|---:|---:|---:|---:|---:|
| 1 | 2 nm | 1.00 | **5.06×** the true modulus | 31% |
| 2 | 4 nm | 0.50 | 2.15× | 8% |
| 3 | 6 nm | 0.33 | 1.61× | 4% |
| 6 | 12 nm | 0.17 | 1.23× | 1% |

Three things follow.

**No origami plate is a half-space.** The bottom effect only falls below 5% at
chi ≈ 0.04, which for this tip and depth means h ≈ 50 nm. The thickest plate
worth folding is a quarter of that and still inflates a Hertz fit by 23%.
`test_no_origami_plate_reaches_the_half_space_regime` asserts it.

**The correction is exactly modulus-independent.** Every model involved is
linear elastic, so force scales with E and the ratio does not — verified to
five digits at 100, 300 and 900 MPa. The factor is pure geometry, which is
precisely what makes a plate of *designed thickness* a calibration object: its
correction is known before anyone measures its stiffness, and stays known
whatever that stiffness turns out to be.

**A thin plate has no single Hertz modulus.** Hertz rises as δ^1.5 and a
confined film rises faster, so the inflation depends on how deep you pushed. On
the single-layer plate it runs 2.14, 3.12, 4.14, 5.06, 6.10 as indentation goes
0.1 → 0.5 nm. A published modulus for a thin origami plate is not merely
biased; without its indentation depth it is not defined.

## The experiment

One footprint, one lattice, one staple core; only the layer count changes —
1, 2, 3 and 6 layers. `mechanics.thickness_ladder()`.

Measure force curves on all four with the same tip in the same session, fit
Hertz to each in the group's own pipeline, and plot apparent modulus against
plate thickness.

**DNA does not become stiffer because fewer layers were stacked.** Any rise in
apparent modulus as the plate thins is the substrate, and its functional form
is known in advance from the table above. So the artefact *is* the calibration:
the group's pipeline either reproduces that curve, in which case their chain is
verified end to end against a known answer, or it does not, in which case the
discrepancy localises where — tip radius, spring constant, contact point, or
the contact model itself.

This is a better offer than a stiffness standard. A stiffness standard tests
one number. A thickness ladder tests the whole inference chain, and it does so
without anyone needing to agree beforehand on what DNA's modulus is.

### Controls

- **Same tip, same session, randomised order.** The factor is geometry, but the
  tip radius enters it, and a tip blunts. Randomised order separates drift
  from thickness.
- **A tip-radius measurement, before and after.** R enters as sqrt(R): a tip
  that blunts from 10 to 20 nm moves chi by 1.4× and the single-layer factor
  from 5.06 to well above it.
- **Both substrate conditions reported.** An unbonded single-layer plate reads
  2.49× rather than 5.06×, a factor of two. Whether a plate pinned to mica by
  Mg²⁺ is bonded or free to slide is not established here, and until it is the
  honest output is the bracket, not one number. Mg²⁺ concentration is the knob
  most likely to move it, and it is already swept in Stage 0.

### What this does not cover

Indentation past roughly a fifth of the plate thickness leaves the linear
elastic small-strain regime this rests on; what happens to individual duplexes
there is not described by any model here. Keep δ ≤ 0.2·h and say so.

## Why this was cheap

`nanoindent` already had all of it: Hertz, Dimitriadis and Garcia's
bottom-effect corrections, Chadwick's asymptotic, and a mixed Taylor–Hood
finite-element solver that handles nu = 0.5 without locking. An origami plate
is small enough that a solve takes about a second on a laptop.

`docs/methodology_msnl_bio_dc.md` in that repository is a Biophysical
Journal-style methods section for exactly this simulation on a 6.2 nm film —
close enough to a three-layer plate that it reads as a draft of our own methods
section with the geometry changed.
