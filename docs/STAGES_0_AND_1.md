# Stages 0 and 1 — experiment design and materials

Companion to `HAMILTONIAN.md` §5. Every number below is produced by
`dobladilo.hamiltonian.experiments`, not typed here; regenerate with

    uv run python -c "from dobladilo.hamiltonian import experiments as e; \
                      [print(s.summary()) for s in e.all_series()]"

## What the two stages decide

**Stage 0** measures how reproducible a single designed hinge is — not its
free energy, but the *spread* across nominally identical constructs. That
spread is the manufacturing noise floor and sets the resolution of
everything downstream.

**Stage 1** is the decision point of the programme. It measures the coupling
between two hinges and asks whether that coupling is constant when the biases
are varied. If it is not, there is no Hamiltonian, only a coupled system, and
the programme stops. A negative result here is a real finding about molecular
coupling and is publishable.

## Three changes from HAMILTONIAN.md

All three came out of running the analysis pipeline on synthetic data before
ordering anything, which is what that pre-stage is for.

### 1. Stage 0's gate is three times too loose

§5.1 asks that construct-to-construct spread be "below ~1 kT". Simulated
(`discrepancy.noise_floor`): at 1 kT of spread a designed 1 kT coupling comes
back with a median error of 0.85 kT, and Stage 1 then cannot meet its own
requirement that J be constant to 0.3 kT at any sampling depth.

**The gate should be 0.3 kT.** A 1 kT result would read as a pass and would
have committed us to a stage that could not succeed.

`STAGE0_SCATTER_GATE_KT = 0.3` in `experiments.py`.

### 2. The ligation calibration is aimed at the wrong quantity

§6.4 warns that a state-dependent ligation efficiency "corrupts every fitted
parameter" and asks for locked constructs to measure efficiency per site.

It cannot corrupt J. A bias depending on each spin separately multiplies each
configuration's weight by a per-spin factor, which is algebraically a shift of
the bias fields — and fields do not enter J. Simulated at log-odds biases up
to 0.6, uniform or per-site: the recovered coupling moves by 0.001 kT.

What does reach J is an efficiency depending on the **joint** state. That
cannot be absorbed into fields, and it adds exactly half itself to the
apparent coupling (0.2 → +0.100, 0.5 → +0.250, 1.0 → +0.500).

**Lock the controls in all four joint states, not in the two states of one
spin.** Cheaper than the original control, not more expensive. See
`LIGATION_NOTE` and `test_discrepancy.py`.

### 3. Sampling depth is not the constraint

An undesigned three-body term of 0.4 kT is detectable at 1 000 molecules,
0.1 kT at 10 000, 0.05 kT at 100 000. Sequencing delivers ~10⁹ — four orders
of margin. Read depth is not worth optimising; the systematics are.

## Stage 0 — forward map, one spin

10 constructs on a shared staple core, so only the latch changes. Six latch
lengths at balanced composition, then four GC fractions at fixed 8 bp length:
the two axes swept separately, because swept together a change in free energy
could be attributed to either.

Readout: bulk FRET → p(up) vs temperature (25–45 °C) and Mg²⁺ (8, 12, 16 mM).
At least three independent folds per construct and two independent oligo
syntheses for a subset — without which folding variance and synthesis variance
cannot be separated, which is the point of the stage. AFM on each to confirm
it folded before its free energy is believed.

**Gate:** construct-to-construct spread at fixed design < 0.3 kT. Above it,
1–3 kT couplings are unresolvable and the mechanical route is dead.

## Stage 1 — two spins

25 constructs. The full factorial is 54; the grid is complete only where it
decides something. Six coupling mechanisms (three strut lengths, one steric,
two strand-mediated tether lengths), full 3×3 bias grid on the medium strut,
corners elsewhere.

Readout: two-colour smFRET → the full 2×2 joint distribution, from which J
follows exactly as a log-odds ratio. HS-AFM on the best variant for flipping
kinetics. oxDNA umbrella sampling on the same construct as an independent
third description.

The key plot is fitted J against applied bias. Horizontal is success; any
slope means the pairwise form is wrong.

**Controls, all three mandatory:**

- Uncoupled pair at every bias setting (two hinges far apart, no strut) —
  quantifies the background |J| must beat.
- Constructs locked in all four joint states (change 2 above).
- Two initial conditions per measurement — annealed from high temperature,
  and released from a locked state — confirming convergence. Otherwise the
  measurement is of kinetics, not of a Boltzmann distribution, and nothing in
  the numbers would say so.

**Gate:** |J| above the Stage 0 floor by 3σ; J constant across the bias grid
to 0.3 kT; uncoupled control below the floor.

## Oligos

| Stage | Constructs | Core staples | Variant staples | Modified | Cost |
|---|---:|---:|---:|---:|---:|
| 0 — one spin | 10 | 200 | 120 | 2 | €1324 |
| 1 — two spins | 25 | 380 | 800 | 4 | €4376 |
| **Both** | **35** | **580** | **920** | **6** | **€5700** |

As independent constructs the same two series cost €36 800. The shared core
is the entire economy of this.

The FRET pair sits *across the hinge joint* (§3.1), which is core geometry
rather than latch, so two modified oligos serve the whole series: €300
instead of €3000, which would otherwise have tripled Stage 0. Stage 1 needs
two colour pairs, because one cannot resolve which hinge flipped.

## Everything else

| Item | For | Note |
|---|---|---|
| M13mp18 scaffold | every fold | one prep covers both stages many times over |
| Tris, EDTA, MgCl₂ | folding buffer | 5 mM / 1 mM / screened 5–20 mM, pH 8 |
| Agarose, TBE, stain | fold check | every construct, before anything else is believed |
| PEG 8000 or 100 kDa spin filters | purification | free staples on mica make counting unreliable |
| Thermocycler, slow ramp | annealing | 2D folds at 1 °C/min; a hinge is 3D, 1 °C/h overnight |
| Fluorimeter or plate reader | Stage 0 readout | temperature control is the requirement, not sensitivity |
| smFRET / TIRF | Stage 1 readout | partner instrument |
| AFM, and HS-AFM | structure and kinetics | partner instrument |
| Mica, tape, ultrapure water, N₂ | AFM sample prep | cheap, and the step most likely to be wrong |

Budget real time for FRET calibration: donor-only and acceptor-only controls,
direct-excitation correction, the γ factor. Sloppy FRET calibration is the
commonest source of a wrong free energy, and Stage 0's entire output is a
free energy.
