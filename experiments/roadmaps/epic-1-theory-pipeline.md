# Epic 1 — the theory pipeline and its synthetic-data gate

Tracking issue #1 (kept in the maintainers\' private tracker). **Mostly done, and
it has already paid for itself three times.**

No experiment of its own. It is the gate on tens of thousands of euros of
oligos, and its job is to be wrong on synthetic data before anyone is wrong on
real data.

## What it found

Three things that contradicted the source document, each caught by running the
analysis on data whose answer was chosen rather than measured:

1. **Stage 0's gate was three times too loose.** At the document's ~1 kT of
   scatter, a designed 1 kT coupling comes back with a median error of
   0.85 kT, and Stage 1 could not then meet its own requirement at any
   sampling depth. The gate is 0.3 kT.
2. **The ligation control was aimed at the wrong quantity.** A per-spin bias is
   algebraically a field shift and cannot touch J — measured drift 0.001 kT.
   Only a *joint*-state bias can, and it adds exactly half itself. So the
   locked controls go in all four joint states, which is cheaper than the
   original control.
3. **Sampling depth is not the constraint.** A 0.4 kT three-body term is
   detectable at 1 000 molecules, 0.05 kT at 100 000; sequencing delivers
   ~10⁹. Four orders of margin. The systematics are what will limit the
   result.

And a fourth, from building the hinge: **Stage 0's latch sweep could have
returned ten saturated measurements and no information.** That produced E4.

## What is left

Two modules, both of them controls the experiment documents call mandatory and
for which there is currently no code at all.

### `hamiltonian/fret.py` — blocks E4 and E5

Bulk FRET to p(latched), with the calibration that makes it mean anything:
donor-only and acceptor-only controls, direct excitation correction, the γ
factor.

`docs/STAGES_0_AND_1.md` says sloppy FRET calibration is the commonest source
of a wrong free energy, and that Stage 0's entire output *is* a free energy.
Shipping the protocol without the calibration code is the gap between a
document that says "calibrate carefully" and one that hands over the
calibration.

### `hamiltonian/equilibrium.py` — blocks E5

The two-initial-condition convergence test: annealed from high temperature,
and released from a locked state, confirming they converge. Without it the
measurement is of kinetics rather than of a Boltzmann distribution, and
nothing in the numbers would say so.

## Also outstanding, and cheaper than both

**A latch-reach observable** in `analysis.observables`: the distance between
the two latch extension anchor points over a trajectory.
`_scadnano.nucleotide_indices` already gives the design-position to
oxDNA-index mapping.

This is small, and it converts the finished joint sweep — four joint lengths,
200 frames each — from four numbers about bending into an answer about whether
the mechanism can close. It re-scores E3 and E4, so it is the highest
value-per-line item on the list.
