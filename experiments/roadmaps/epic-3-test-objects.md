# Epic 3 — calibrated nanomechanical test objects

[Issue #3](https://github.com/alpibrupa/dobladillo/issues/3). One experiment,
**E7**, and it is the only one that is not on the critical path.

---

## E7 — the thickness ladder

**Relevance 3 to the programme, 5 to the partnership. Difficulty 2.
P(success) 0.80.**

Four plates — 1, 2, 3 and 6 layers — one footprint, one lattice, one staple
core. Force curves on all four with the same tip in one session, Hertz fitted
to each in the partner's own pipeline, apparent modulus plotted against plate
thickness.

**DNA does not become stiffer because fewer layers were stacked.** Any rise in
apparent modulus as the plate thins is the substrate, its functional form is
known in advance, and so the artefact *is* the calibration:

| layers | h | χ | a Hertz fit reads |
|---:|---:|---:|---:|
| 1 | 2 nm | 1.00 | **5.06×** the true modulus |
| 2 | 4 nm | 0.50 | 2.15× |
| 3 | 6 nm | 0.33 | 1.61× |
| 6 | 12 nm | 0.17 | 1.23× |

The correction is **exactly modulus-independent** — verified to five digits at
100, 300 and 900 MPa — which is what makes a plate of designed thickness a
calibration object: its correction is known before anyone measures its
stiffness. See `docs/PLATE_INDENTATION.md`.

**Why this is a better offer than a stiffness standard.** A standard tests one
number. A thickness ladder tests the whole inference chain — tip radius, spring
constant, contact point, contact model — and needs no prior agreement on what
DNA's modulus is.

**Gate.** Apparent modulus rises as the plate thins, following the table within
the bracket set by the bonded/unbonded ambiguity. A flat line means the
partner's pipeline is already applying a bottom-effect correction, which is
also a useful thing to learn.

**P(success) 0.80.** The physics is settled and the instrument stack exists in
`LorenaRedondo/nanoindent`. The risk is not the analysis: it is whether a
single-layer origami plate survives indentation at all, and whether it stays
adsorbed. Neither is predictable from here.

**Open.** The bonded/unbonded bracket is a factor of two — 5.06× against 2.49×
for a single layer — and which one a Mg²⁺-pinned plate obeys is not
established. Mg²⁺ is already swept in Stage 0's protocol, so the two can share
a sample set.

### Software needed first

**A multi-layer plate part.** `dobladillo/parts/` has a rectangle, a six-helix
bundle, a twist pair and a hinge — all single-layer or bundled, none stacked.
The ladder needs 1/2/3/6 layers on one footprint, which means out-of-plane
stacking that no current part does.

This shares machinery with the hinge's arms, so doing it while that code is
fresh is cheaper than doing it cold. It is the single largest software item in
this epic and the only thing between the design and the experiment.

The mechanics side needs nothing: `dobladillo/mechanics/` bridges to
nanoindent, which already carries Hertz, the Dimitriadis and Garcia
bottom-effect corrections, Chadwick, and a mixed finite-element solver that
handles ν = 0.5 without locking. A solve takes about a second.
