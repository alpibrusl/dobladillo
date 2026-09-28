"""Equilibrium shape of a design from a beam finite-element model, in seconds.

oxDNA answers shape questions in 7 to 18 hours on this machine. Every fast
predictor that exists is excluded by the project's licence rule (VISION.md
section 0): CanDo runs on commercial Abaqus behind a web server, SNUPI is a
non-commercial binary, NADOC's model has no licence, mrDNA needs CUDA. The
method is published, so it is implemented here -- from the papers, not from
anyone's code:

- Castro et al., *Nature Methods* 8, 221 (2011) and Kim et al., *NAR* 40, 2862
  (2012): helices as elastic beams on their lattice positions, crossovers as
  rigid connections, and stress from the difference between what DNA wants
  and what the lattice imposes.
- Gore et al., *Nature* 442, 836 (2006): DNA overwinds when stretched; the
  twist-stretch coupling term.
- Textbook linear Euler-Bernoulli beam elements (Przemieniecki, *Theory of
  Matrix Structural Analysis*).

**The model.** One node per base pair on each helix axis, six degrees of
freedom each, at its lattice position. Between consecutive base pairs sits a
beam element: stretch, bend, twist, and the twist-stretch coupling. A
crossover is a stiff link between the two axis nodes it joins. The reference
geometry is the lattice, and it is not stress-free, for two reasons:

1. **twist.** The lattice turns a helix at its own rate -- 10.5 bp/turn on
   honeycomb, 10.67 on square -- and relaxed DNA turns at 10.5. On square
   lattice every element wants 0.54 deg/bp more twist than it has, and the
   object twists;
2. **deletions and insertions.** An element spanning a deleted base covers
   two lattice positions with one base pair: it wants to be half as long and
   to turn half as far. Deletions on one side of a bundle and insertions on
   the other are how curved shapes are designed (Dietz et al., *Science* 2009).

One linear solve, K u = F, gives the displacement. That is accurate for
curvature and twist rate -- local, small-strain quantities -- even when the
total bend angle is large; shapes where the structure folds over itself are
outside it.

**What this class of model cannot see: misphased crossovers.** It puts every
crossover where the lattice says one can go, so a crossover made on the wrong
face of its helix looks exactly like one made on the right face. This was
measured, not assumed: an earlier version here modelled crossovers as springs
between backbone points at their azimuth, and it predicted the two misphased
bundles in `tests/data/our_designs`, which bend to 269 and 347 nm radius in
oxDNA, as straight to within tens of microns. Those springs also distorted
correctly phased designs, because every published design leaves 17-22 deg
of residual azimuth strain that a spring treats as real. Misphasing belongs to
the `crossover_azimuth` rule, which catches it; this model answers what that
rule cannot: how far a correctly phased design twists and bends.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING, Any

import numpy as np

from dobladillo.constants import RISE_PER_BP_NM
from dobladillo.routing.azimuth import duplexes_by_helix, skips

if TYPE_CHECKING:
    import scadnano as sc


@dataclass(frozen=True)
class BeamParameters:
    """Elastic constants of a DNA helix, and of the connections between them.

    Units: nm, pN, radians. Defaults are literature values, each with its source.
    """

    #: Stretch modulus, pN. Smith, Cui, Bustamante, *Science* 1996; Castro 2011.
    stretch_pn: float = 1100.0
    #: Bending rigidity EI, pN nm^2 -- a persistence length of ~56 nm. Castro 2011.
    bend_pn_nm2: float = 230.0
    #: Torsional rigidity GJ, pN nm^2. Castro 2011.
    twist_pn_nm2: float = 460.0
    #: Twist-stretch coupling, pN nm. Negative: DNA overwinds when stretched.
    #: Gore et al. 2006, -90 +- 20.
    twist_stretch_pn_nm: float = -90.0
    #: A crossover's translational stiffness, pN/nm. CanDo treats crossovers
    #: as rigid; this is stiff enough to behave so (see the sensitivity test).
    crossover_pn_per_nm: float = 1.0e4
    #: A crossover's rotational stiffness, pN nm/rad.
    crossover_pn_nm_per_rad: float = 1.0e4
    #: Entropic spring across an unpaired stretch on one helix, pN/nm. Holds a
    #: hinge's arms together without transmitting stress.
    single_strand_pn_per_nm: float = 0.01
    #: Rise per base pair, nm.
    rise_nm: float = RISE_PER_BP_NM
    #: Relaxed DNA, bp per turn.
    helical_repeat_bp: float = 10.5
    #: Axis-to-axis distance of neighbouring helices, nm.
    interhelix_nm: float = 2.5


#: Below this curvature a design is reported as straight: a radius of 1 mm.
STRAIGHT_BELOW_PER_NM = 1.0e-6

#: Base pairs per turn each lattice imposes: 21 bp = 2 turns on honeycomb,
#: 32 bp = 3 turns on square.
LATTICE_REPEAT_BP = {"honeycomb": 21 / 2, "square": 32 / 3}


@dataclass(frozen=True)
class ShapePrediction:
    """What the solve says the design does, in numbers a comparison can use."""

    curvature_per_nm: float
    radius_nm: float
    bend_direction_deg: float
    sagitta_nm: float
    length_nm: float
    twist_deg: float
    nodes: int
    crossovers: int
    unconstrained_crossovers: int
    seconds: float
    parameters: BeamParameters = field(default_factory=BeamParameters)

    @property
    def straight(self) -> bool:
        """Curvature below one per millimetre: nothing an AFM or TEM resolves."""
        return self.curvature_per_nm < STRAIGHT_BELOW_PER_NM

    def as_dict(self) -> dict[str, Any]:
        out = asdict(self)
        out["straight"] = self.straight
        if self.straight:
            out["radius_nm"] = out["bend_direction_deg"] = None
        else:
            out["radius_nm"] = round(self.radius_nm, 1)
            out["bend_direction_deg"] = round(self.bend_direction_deg, 1)
        for key in ("sagitta_nm", "length_nm", "twist_deg", "seconds"):
            out[key] = round(out[key], 2)
        return out


def _skew(v: np.ndarray) -> np.ndarray:
    return np.array([[0.0, -v[2], v[1]], [v[2], 0.0, -v[0]], [-v[1], v[0], 0.0]])


def _axis_positions(design: sc.Design, spacing_nm: float) -> dict[int, np.ndarray]:
    """Helix axes in the x-y plane, rescaled so neighbours sit `spacing_nm` apart."""
    import scadnano as sc

    native = 2 * design.geometry.helix_radius + design.geometry.inter_helix_gap
    out = {}
    for idx, helix in design.helices.items():
        pos = sc.grid_position_to_position(helix.grid_position, design.grid, design.geometry)
        out[idx] = np.array([pos.x, pos.y]) * (spacing_nm / native)
    return out


def _crossover_ends(design: sc.Design) -> list[tuple[tuple[int, int], tuple[int, int]]]:
    """Every helix change in every strand, as the (helix, offset) pair it joins."""
    found = []
    for strand in design.strands:
        for before, after in zip(strand.domains, strand.domains[1:], strict=False):
            if not (hasattr(before, "helix") and hasattr(after, "helix")):
                continue
            if before.helix == after.helix:
                continue
            end = before.end - 1 if before.forward else before.start
            start = after.start if after.forward else after.end - 1
            found.append(((before.helix, end), (after.helix, start)))
    return found


@dataclass
class _System:
    """The assembled problem: K u = F over one node per base pair."""

    K: Any
    F: np.ndarray
    node: dict[tuple[int, int], int]
    X: np.ndarray
    crossovers: int
    unconstrained: int

    def solve(self) -> np.ndarray:
        from scipy.sparse.linalg import spsolve

        return np.asarray(spsolve(self.K, self.F)).reshape(len(self.X), 6)


def predict(design: sc.Design, parameters: BeamParameters | None = None) -> ShapePrediction:
    """Solve for the equilibrium shape of `design`."""
    started = time.perf_counter()
    p = parameters or BeamParameters()
    system = assemble(design, p)
    shape = _shape(design, system.node, system.X, system.solve())
    return ShapePrediction(
        **shape,
        nodes=len(system.X),
        crossovers=system.crossovers,
        unconstrained_crossovers=system.unconstrained,
        seconds=time.perf_counter() - started,
        parameters=p,
    )


def assemble(design: sc.Design, p: BeamParameters) -> _System:
    """Build K and F. Separate from `predict` so tests can check the matrix
    itself -- symmetry, rigid-body modes -- and not only its answers."""
    from scipy.sparse import coo_matrix

    lattice = getattr(design.grid, "value", str(design.grid))
    if lattice not in LATTICE_REPEAT_BP:
        raise ValueError(f"no lattice twist for grid {lattice!r}; square or honeycomb only")
    lattice_rad_per_offset = 2 * np.pi / LATTICE_REPEAT_BP[lattice]
    natural_rad_per_bp = 2 * np.pi / p.helical_repeat_bp

    deletions, insertions = skips(design)
    runs = duplexes_by_helix(design)
    axes = _axis_positions(design, p.interhelix_nm)

    node: dict[tuple[int, int], int] = {}
    positions: list[np.ndarray] = []
    pieces: dict[int, list[list[int]]] = {}
    for helix, helix_runs in sorted(runs.items()):
        for lo, hi in helix_runs:
            offsets = [o for o in range(lo, hi) if o not in deletions.get(helix, set())]
            for o in offsets:
                node[(helix, o)] = len(positions)
                positions.append(np.array([*axes[helix], o * p.rise_nm]))
            if offsets:
                pieces.setdefault(helix, []).append(offsets)
    n = len(positions)
    X = np.array(positions)

    rows: list[int] = []
    cols: list[int] = []
    vals: list[float] = []
    F = np.zeros(6 * n)

    def add_block(dofs: list[int], block: np.ndarray) -> None:
        nz = np.nonzero(block)
        for a, b in zip(*nz, strict=True):
            rows.append(dofs[a])
            cols.append(dofs[b])
            vals.append(float(block[a, b]))

    # -------------------------------------------------------- beam elements
    S, EI, C, g = p.stretch_pn, p.bend_pn_nm2, p.twist_pn_nm2, p.twist_stretch_pn_nm
    axial_twist = np.array([[S, g], [g, C]])
    ends = np.array([[1.0, -1.0], [-1.0, 1.0]])
    flip = np.diag([1.0, -1.0, 1.0, -1.0])  # du_y/dz = -phi_x
    for helix, helix_pieces in pieces.items():
        ins = insertions.get(helix, {})
        for offsets in helix_pieces:
            for o1, o2 in zip(offsets, offsets[1:], strict=False):
                i, j = node[(helix, o1)], node[(helix, o2)]
                L = (o2 - o1) * p.rise_nm
                bases = 1 + ins.get(o1, 0)
                # What this element wants, relative to what the lattice gives it.
                stretch0 = bases * p.rise_nm - L
                twist0 = bases * natural_rad_per_bp - (o2 - o1) * lattice_rad_per_offset
                k2 = axial_twist / L
                add_block([6 * i + 2, 6 * j + 2, 6 * i + 5, 6 * j + 5], np.kron(k2, ends))
                force = k2 @ np.array([stretch0, twist0])  # on (uz, phz) of node j; minus on i
                F[[6 * j + 2, 6 * j + 5]] += force
                F[[6 * i + 2, 6 * i + 5]] -= force
                m = (EI / L**3) * np.array(
                    [
                        [12, 6 * L, -12, 6 * L],
                        [6 * L, 4 * L * L, -6 * L, 2 * L * L],
                        [-12, -6 * L, 12, -6 * L],
                        [6 * L, 2 * L * L, -6 * L, 4 * L * L],
                    ]
                )
                add_block([6 * i + 0, 6 * i + 4, 6 * j + 0, 6 * j + 4], m)  # u_x, phi_y
                add_block([6 * i + 1, 6 * i + 3, 6 * j + 1, 6 * j + 3], flip @ m @ flip)
        # unpaired stretches on this helix: a weak translational tether
        tether = p.single_strand_pn_per_nm * np.kron(ends, np.eye(3))
        for left, right in zip(helix_pieces, helix_pieces[1:], strict=False):
            i, j = node[(helix, left[-1])], node[(helix, right[0])]
            add_block([6 * i, 6 * i + 1, 6 * i + 2, 6 * j, 6 * j + 1, 6 * j + 2], tether)

    # ----------------------------------------------------------- crossovers
    # A rigid link between two axis nodes, stress-free on the lattice: the
    # far node moves as if attached to the near one by a rigid arm, and the
    # two rotate together. Linearised about the mid-point so neither end is
    # privileged.
    crossovers = unconstrained = 0
    kt, kr = p.crossover_pn_per_nm, p.crossover_pn_nm_per_rad
    for a, b in _crossover_ends(design):
        ia, ib = node.get(a), node.get(b)
        if ia is None or ib is None:
            unconstrained += 1  # made from unpaired bases: no lattice constraint
            continue
        crossovers += 1
        d = X[ib] - X[ia]
        # delta_u = u_b - u_a - ((phi_a + phi_b) / 2) x d
        #         = [-I, +[d]x/2, I, +[d]x/2] . (u_a, phi_a, u_b, phi_b)
        half = 0.5 * _skew(d)
        Bu = np.hstack([-np.eye(3), half, np.eye(3), half])
        Br = np.hstack([np.zeros((3, 3)), -np.eye(3), np.zeros((3, 3)), np.eye(3)])
        block = kt * Bu.T @ Bu + kr * Br.T @ Br
        add_block(list(range(6 * ia, 6 * ia + 6)) + list(range(6 * ib, 6 * ib + 6)), block)

    # rigid-body modes: pin every degree of freedom of one node
    pin = 10.0 * max(abs(v) for v in vals)
    for dof in range(6):
        rows.append(dof)
        cols.append(dof)
        vals.append(pin)

    K = coo_matrix((vals, (rows, cols)), shape=(6 * n, 6 * n)).tocsc()
    return _System(K, F, node, X, crossovers, unconstrained)


def _shape(
    design: sc.Design, node: dict[tuple[int, int], int], X: np.ndarray, u: np.ndarray
) -> dict[str, float]:
    """Curvature, bend direction and twist of the centroid axis.

    Only offsets where every helix has a base pair are used, so the centroid
    is always taken over the same cross-section.
    """
    helices = sorted(design.helices)
    offsets = sorted({o for (_, o) in node})
    full = [o for o in offsets if all((h, o) in node for h in helices)]
    if len(full) < 3:
        raise ValueError("no stretch of the design has every helix paired; nothing to fit")
    z = np.array([X[node[(helices[0], o)], 2] for o in full])
    z0 = z - z.mean()
    idx = np.array([[node[(h, o)] for h in helices] for o in full])
    deformed = (X[:, :3] + u[:, :3])[idx].mean(axis=1)
    kx = 2 * np.polyfit(z0, deformed[:, 0], 2)[0]
    ky = 2 * np.polyfit(z0, deformed[:, 1], 2)[0]
    kappa = float(np.hypot(kx, ky))
    length = float(z[-1] - z[0])

    # Twist: rotation of the cross-section about its centroid, per offset,
    # from how far each helix moved round it.
    centre = X[idx[0], :2].mean(axis=0)
    r = X[idx, :2] - centre  # (offsets, helices, 2)
    du = u[idx, :2]
    r2 = (r**2).sum(axis=2)
    use = r2 > 1e-9
    per = np.where(use, (r[..., 0] * du[..., 1] - r[..., 1] * du[..., 0]) / np.where(use, r2, 1), 0)
    twist = per.sum(axis=1) / np.maximum(use.sum(axis=1), 1)
    rate = np.polyfit(z0, twist, 1)[0]

    return {
        "curvature_per_nm": kappa,
        "radius_nm": 1.0 / kappa if kappa > 0 else float("inf"),
        "bend_direction_deg": float(np.degrees(np.arctan2(ky, kx)) % 360.0),
        "sagitta_nm": kappa * length**2 / 8.0,
        "length_nm": length,
        "twist_deg": float(np.degrees(rate * length)),
    }
