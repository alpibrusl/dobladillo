"""A coupled lattice of switches, and how sharply it turns over.

A single two-state switch is a poor threshold: its occupancy goes from 0.1 to
0.9 over 2.2 kT, which at a latch's temperature sensitivity is about 14 C. No
product wants a threshold that vague.

Coupling sharpens it, and geometry matters more than coupling strength. A pair
reaches a Hill coefficient near 3.5; a 3x4 lattice reaches 25 and turns over
inside about 1 C. That is the difference between a gradual response and a
switch, and it is why the interesting object is a film rather than a molecule.

The result worth knowing, because it inverts the programme's own worry:
**the transition is almost immune to manufacturing scatter.** Stage 0 exists to
measure construct-to-construct spread and gates at 0.3 kT, because resolving an
individual coupling needs that. A film does not resolve individual couplings --
it averages over them -- so 0.3 kT of disorder in J moves the switching width
from 1.2 C to 1.3 C, and even 0.5 kT only reaches 1.5. It degrades at 1.0.

So a collective application tolerates roughly three times the manufacturing
noise that a single-coupling measurement does. That is a real hedge: the film
line survives a Stage 0 that fails its gate.
"""

from __future__ import annotations

import numpy as np

from dobladillo.hamiltonian.model import Ising, distribution

#: Occupancy bounds defining "switched". 0.1 to 0.9 rather than 0.05 to 0.95:
#: this is a product specification, not a measurement window.
SWITCH_BOUNDS = (0.1, 0.9)


def square_lattice(
    rows: int,
    cols: int,
    *,
    coupling_kt: float,
    field_kt: float = 0.0,
    coupling_scatter_kt: float = 0.0,
    field_scatter_kt: float = 0.0,
    seed: int = 0,
) -> Ising:
    """Nearest-neighbour square lattice, optionally disordered.

    Disorder is drawn once and belongs to the object. A film is one physical
    thing, so its defects do not resample as the temperature is swept, and
    averaging over realisations before sweeping would wash out exactly the
    effect being asked about.
    """
    rng = np.random.default_rng(seed)
    n = rows * cols
    J = np.zeros((n, n))
    for r in range(rows):
        for c in range(cols):
            i = r * cols + c
            for dr, dc in ((0, 1), (1, 0)):
                rr, cc = r + dr, c + dc
                if rr < rows and cc < cols:
                    j = rr * cols + cc
                    value = coupling_kt + rng.normal(0, coupling_scatter_kt)
                    J[i, j] = J[j, i] = value
    h = np.full(n, field_kt) + rng.normal(0, field_scatter_kt, n)
    return Ising(h=h, J=J)


def occupancy(model: Ising, field_kt: float = 0.0) -> float:
    """Mean fraction of switches in the +1 state, at an applied field."""
    shifted = Ising(h=model.h + field_kt, J=model.J)
    states, p = distribution(shifted)
    return float((p * (states.mean(axis=1) + 1) / 2).sum())


def switch_width_kt(model: Ising, *, span: float = 6.0, points: int = 241) -> float:
    """Applied field over which occupancy crosses `SWITCH_BOUNDS`."""
    grid = np.linspace(-span, span, points)
    values = np.array([occupancy(model, f) for f in grid])
    low, high = SWITCH_BOUNDS
    return float(np.interp(high, values, grid) - np.interp(low, values, grid))


def hill_coefficient(model: Ising, *, step_kt: float = 0.02) -> float:
    """Effective Hill coefficient from the slope at half occupancy."""
    low = occupancy(model, -step_kt)
    high = occupancy(model, step_kt)
    return float((high - low) / (2 * step_kt) * 4.0)
