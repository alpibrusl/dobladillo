"""Assembly states from AFM footprints: monomer, dimer, larger, malformed.

E9 mixes two rectangles that join end to end. Its readout is a distribution
over assembly states, with an interval on each, and whether that distribution
is the same from one mix to the next. This module sorts particles by
footprint and counts; it knows nothing about DNA beyond the sizes it is given.

**The classes**, against what the IMAGE should show -- the object plus twice
the tip's half-height broadening, as in `experiment report`:

- **monomer**: one rectangle's footprint.
- **dimer**: twice the length plus the bridge, the same width. A dimer lying
  straight; the two halves are not resolved, because a 4 nm bridge is smaller
  than the tip.
- **larger**: taller than a single layer (`classify.AGGREGATE_HEIGHT_FACTOR`
  times the reference height), or covering the area of three or more
  rectangles, or longer than a dimer can be.
- **malformed**: a single layer that is none of the above. A dimer that lay
  down kinked lands here, and so does a torn or partly folded sheet; the
  report splits malformed particles by their area in rectangle units so the
  two can be told apart afterwards, without pretending the classifier can.

**Two rectangles that merely touch**, and this is a decision, not a detail:

- *end to end, in line*: indistinguishable from a dimer by footprint, at any
  tip radius, because the bond is thinner than the tip. It is counted as a
  dimer. What keeps that honest is the protocol, not the classifier: A alone
  and B alone are imaged the same way, and their "dimer" fraction is the
  false-positive rate -- coincidence plus any blunt-end stacking the tails
  failed to stop. The mixture is reported against it.
- *side by side*, long edges touching: one rectangle's length, twice its
  width. No designed interface makes that shape, so it is a deposition
  coincidence, not an assembly state. It is **excluded** from the counted
  total and reported separately, like particles cut by the frame edge. If
  there are many, the sample was too crowded, and the count says so.

**The yield.** The fraction of particles in each state, with a Wilson
interval each (`classify.Fraction`). And the one people quote: the fraction of
rectangles that are in a dimer, 2d / (m + 2d). Rectangles in one dimer are
not independent draws, so that fraction gets no Wilson interval of its own; it
is a monotone function of the dimer share among monomers and dimers,
p = d / (m + d), as 2p / (1 + p), so the interval on p maps to an interval on
it exactly.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final

from dobladillo.imaging.classify import AGGREGATE_HEIGHT_FACTOR, SHAPE_TOLERANCE, Fraction

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from dobladillo.imaging.particles import Particle

#: The counted states, in the order they are reported. Fixed, so a state that
#: happened not to occur reports zero rather than vanishing (see classify.py
#: for what forgetting that once cost).
STATES: Final = ("monomer", "dimer", "larger", "malformed")

#: Excluded from the total, and why.
SIDE_BY_SIDE: Final = "side_by_side"

#: Area, in rectangle footprints, from which a single-layer particle is more
#: than a dimer. Halfway between two and three.
LARGER_AREA_UNITS: Final = 2.5


@dataclass(frozen=True)
class Footprints:
    """What the design predicts, and what the tip adds to it."""

    monomer_length_nm: float
    width_nm: float
    dimer_length_nm: float
    #: Twice the half-height broadening per side, for this tip and height.
    widening_nm: float
    #: What a single flat layer measures in these imaging conditions (E1's).
    reference_height_nm: float
    tolerance: float = SHAPE_TOLERANCE

    @property
    def monomer_image(self) -> tuple[float, float]:
        return (self.monomer_length_nm + self.widening_nm, self.width_nm + self.widening_nm)

    @property
    def dimer_image(self) -> tuple[float, float]:
        return (self.dimer_length_nm + self.widening_nm, self.width_nm + self.widening_nm)

    @property
    def side_by_side_image(self) -> tuple[float, float]:
        """Longest extent first, as a particle is measured: for a rectangle
        whose sides are within a factor of two, the pair is longer across."""
        a = self.monomer_length_nm + self.widening_nm
        b = 2 * self.width_nm + self.widening_nm
        return (max(a, b), min(a, b))

    @property
    def unit_area_nm2(self) -> float:
        length, width = self.monomer_image
        return length * width

    def as_dict(self) -> dict[str, Any]:
        return {
            "monomer_nm": [round(self.monomer_length_nm, 1), round(self.width_nm, 1)],
            "dimer_length_nm": round(self.dimer_length_nm, 1),
            "widening_nm": round(self.widening_nm, 2),
            "reference_height_nm": self.reference_height_nm,
            "tolerance": self.tolerance,
            "image_nm": {
                "monomer": [round(v, 1) for v in self.monomer_image],
                "dimer": [round(v, 1) for v in self.dimer_image],
                "side_by_side": [round(v, 1) for v in self.side_by_side_image],
            },
        }


def _near(value: float, target: float, tolerance: float) -> bool:
    return abs(value - target) <= tolerance * target


def _fits(particle: Particle, image: tuple[float, float], tolerance: float) -> bool:
    return _near(particle.length_nm, image[0], tolerance) and _near(
        particle.width_nm, image[1], tolerance
    )


def area_units(particle: Particle, footprints: Footprints) -> float:
    """The particle's area in rectangle footprints, tip included."""
    return particle.area_nm2 / footprints.unit_area_nm2


def classify_assembly(particle: Particle, footprints: Footprints) -> str:
    """One of `STATES`, or `SIDE_BY_SIDE`.

    The windows cannot overlap at the default tolerance: a dimer is twice as
    long as a monomer, and 20% either side of each leaves a gap between them.
    `test_assembly` checks that for the E1 rectangle at every tip radius the
    protocol could meet.
    """
    f = footprints
    # Height and area first, and in that order. A particle can have a dimer's
    # two extents and cover three rectangles -- a clump that spread into an L,
    # whose principal axes are a dimer's bounding box -- and testing the
    # extents first called that a dimer. A real dimer covers 1.95 units.
    if particle.height_nm > AGGREGATE_HEIGHT_FACTOR * f.reference_height_nm:
        return "larger"
    if area_units(particle, f) >= LARGER_AREA_UNITS:
        return "larger"
    if _fits(particle, f.monomer_image, f.tolerance):
        return "monomer"
    if _fits(particle, f.dimer_image, f.tolerance):
        return "dimer"
    if _fits(particle, f.side_by_side_image, f.tolerance):
        return SIDE_BY_SIDE
    if particle.length_nm > (1 + f.tolerance) * f.dimer_image[0]:
        return "larger"
    return "malformed"


@dataclass(frozen=True)
class AssemblyPopulation:
    """A sample's particles, sorted into assembly states."""

    counts: dict[str, int]
    total: int
    excluded_at_edge: int
    excluded_side_by_side: int
    #: Malformed particles by area: about one rectangle, about two, other.
    malformed_by_area: dict[str, int]

    def fraction(self, state: str) -> Fraction:
        return Fraction(self.counts.get(state, 0), self.total)

    @property
    def dimer_share(self) -> Fraction:
        """Dimers among particles that are a clean monomer or a clean dimer."""
        paired = self.counts["monomer"] + self.counts["dimer"]
        return Fraction(self.counts["dimer"], paired)

    @property
    def rectangles_in_dimers(self) -> tuple[float, tuple[float, float]]:
        """2d / (m + 2d), and its interval mapped from `dimer_share`'s."""
        share = self.dimer_share

        def units(p: float) -> float:
            return 2 * p / (1 + p)

        low, high = share.ci95
        return units(share.value), (units(low), units(high))

    def as_dict(self) -> dict[str, Any]:
        value, (low, high) = self.rectangles_in_dimers
        return {
            "counted": self.total,
            "counts": dict(self.counts),
            "fractions": {s: self.fraction(s).as_dict() for s in STATES},
            "dimer_share_of_monomers_and_dimers": self.dimer_share.as_dict(),
            "rectangles_in_dimers": {
                "fraction": round(value, 4),
                "ci95": [round(low, 4), round(high, 4)],
                "note": "2d/(m+2d); interval mapped from the dimer share's Wilson interval",
            },
            "excluded_touching_edge": self.excluded_at_edge,
            "excluded_side_by_side": self.excluded_side_by_side,
            "malformed_by_area_units": dict(self.malformed_by_area),
        }


def assembly_population(
    particles: Sequence[Particle], footprints: Footprints
) -> AssemblyPopulation:
    """Classify everything clear of the frame edge and count the states."""
    inside = [p for p in particles if not p.touches_edge]
    labels = [(p, classify_assembly(p, footprints)) for p in inside]
    counted = Counter(label for _, label in labels if label != SIDE_BY_SIDE)
    by_area: Counter[str] = Counter()
    for particle, label in labels:
        if label != "malformed":
            continue
        units = area_units(particle, footprints)
        if units < 1.5:
            by_area["about_1"] += 1
        elif units < LARGER_AREA_UNITS:
            by_area["about_2"] += 1
        else:
            by_area["other"] += 1
    side = sum(1 for _, label in labels if label == SIDE_BY_SIDE)
    return AssemblyPopulation(
        counts={s: counted.get(s, 0) for s in STATES},
        total=len(inside) - side,
        excluded_at_edge=len(particles) - len(inside),
        excluded_side_by_side=side,
        malformed_by_area={k: by_area.get(k, 0) for k in ("about_1", "about_2", "other")},
    )


@dataclass(frozen=True)
class Reproducibility:
    """Whether several samples share one distribution of assembly states."""

    samples: tuple[str, ...]
    chi2: float
    dof: int
    p_value: float
    #: The largest spread in any one state's fraction across the samples.
    largest_spread: tuple[str, float]

    def as_dict(self) -> dict[str, Any]:
        state, spread = self.largest_spread
        return {
            "samples": list(self.samples),
            "test": "chi-square test of homogeneity over the counted states "
            "(states no sample has are dropped)",
            "chi2": round(self.chi2, 3),
            "dof": self.dof,
            "p_value": round(self.p_value, 4),
            "largest_spread": {"state": state, "fraction_points": round(spread, 4)},
            "reading": "a small p-value says the replicates differ by more than "
            "counting noise; a large one says the counts cannot tell them apart, "
            "which is not proof they are the same",
        }


def reproducibility(populations: Mapping[str, AssemblyPopulation]) -> Reproducibility:
    """Chi-square homogeneity across replicate samples.

    Two or more samples, each with a counted particle. States that no sample
    has are dropped, since a column of zeros has no expected count.
    """
    from scipy.stats import chi2_contingency

    names = tuple(populations)
    if len(names) < 2:
        raise ValueError("reproducibility needs at least two samples")
    if any(populations[n].total == 0 for n in names):
        raise ValueError("every replicate needs at least one counted particle")
    states = [s for s in STATES if any(populations[n].counts[s] for n in names)]
    spread = max(
        (
            (
                s,
                max(populations[n].fraction(s).value for n in names)
                - min(populations[n].fraction(s).value for n in names),
            )
            for s in STATES
        ),
        key=lambda item: item[1],
    )
    if len(states) < 2:
        # Every replicate is entirely one state: identical, nothing to test.
        return Reproducibility(names, 0.0, 0, 1.0, spread)
    table = [[populations[n].counts[s] for s in states] for n in names]
    result = chi2_contingency(table)
    return Reproducibility(
        samples=names,
        chi2=float(result.statistic),
        dof=int(result.dof),
        p_value=float(result.pvalue),
        largest_spread=spread,
    )
