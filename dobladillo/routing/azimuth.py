"""Crossover azimuth: does each crossover sit where its backbone faces the partner?

A crossover joins two helices at a single base pair, and it can only be made
without strain if, at that base pair, the backbone of each helix is pointing
at the other. The backbone rotates about 34.3 degrees per base pair, so the
*offset* of a crossover is an angle, and a crossover placed at the wrong offset
forces the helix to twist to reach its partner.

This module measures that, and it deliberately does not compute the geometry
itself. scadnano (MIT) already knows the backbone angle of every nucleotide
(`Helix.backbone_angle_at_offset`), the direction from one helix to another on
its lattice (`angle_from_helix_to_helix`), and the helix roll that minimises
crossover strain (`minimum_strain_angle`, used by `relax_helix_rolls`). The
earlier rule in this project, `crossover_phase`, computed phases by hand and
missed the defect it was written for.

One correction to scadnano, and only one: `backbone_angle_at_offset` uses the
offset, not the number of bases, so it cannot see deletions or insertions. On
a twist-corrected square design that is the whole point -- one base deleted
every 64 winds the helix back 34.3 degrees -- and without the correction the
measure reports scadnano's own twist-corrected rectangle as 66 degrees
strained instead of 31. Here each deletion before an offset subtracts one base
and each insertion adds its length.

Calibrated on designs this project did not write, which is the only reason to
trust it (`tests/data/reference_designs/`):

| design | lattice | raw rms | phasing rms | twist |
|---|---|---:|---:|---:|
| Nature 2009 monolith (caDNAno test data) | honeycomb | 20.5 | 20.1 | 15 deg |
| Nature 2009 square nut (caDNAno test data) | honeycomb | 20.9 | 20.4 | 20 deg |
| scadnano example 6-helix bundle | honeycomb | 22.3 | 22.3 | 0 deg |
| scadnano 16-helix rectangle, with deletions | square | 31.4 | 21.4 | 75 deg |
| scadnano 16-helix rectangle, no deletions | square | 66.4 | 18.7 | -216 deg |

"Raw" relaxes only the roll of each helix. "Phasing" also fits out one steady
twist rate for the whole design, which is what separates the two ways a
crossover can be strained: a tiling that puts it on the wrong face (a defect),
and a lattice that over-winds the helix (corrected by deletions, or intended,
as in E2's control arm). Without the split, an uncorrected square design
looks as bad as a misphased one -- 91 deg against 89 -- and they need
opposite verdicts. With it, the uncorrected arm scores 18 deg of phasing and
-310 deg of twist, which matches the 309 deg `parts.twist_pair` predicts from
the lattice alone. That agreement is an independent check on both.

Residual strain is not zero on good designs: scaffold and staple crossovers
sit in reference frames offset by about 5 bp, and one roll per helix cannot
satisfy both exactly. What matters is the distance from these numbers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Final

import numpy as np

if TYPE_CHECKING:
    import scadnano as sc

#: Above this, a single crossover is on the wrong face of its helix: the
#: backbone points more than a quarter-turn away from the partner. Published
#: designs have almost none; a tiling that repeats a partner 16 bp later has
#: half its crossovers here.
WRONG_FACE_DEG: Final = 90.0

#: Design-level ceiling on rms *phasing* strain -- what remains once each
#: helix's steady twist drift is removed. Published honeycomb designs sit at
#: 20-22 degrees and scadnano's twist-corrected square rectangle at 31; every
#: misphased design found here was 44 or worse. 40 separates them.
MAX_RMS_DEG: Final = 40.0

#: Above this much accumulated twist along a helix, the design is carrying
#: uncorrected twist. Not a defect in itself -- E2's control arm carries 309
#: degrees on purpose -- so it is reported, not refused.
TWIST_WARN_DEG: Final = 90.0

#: Twist rates tried when separating drift from phasing, degrees per base
#: pair. Square-lattice over-winding is about 0.54 deg/bp; the range covers it
#: several times over in both directions.
_TWIST_GRID: Final = tuple(i * 0.02 for i in range(-100, 101))


@dataclass(frozen=True)
class Crossover:
    helix: int
    partner: int
    offset: int
    forward: bool
    strain_deg: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "helix": self.helix,
            "partner": self.partner,
            "offset": self.offset,
            "forward": self.forward,
            "strain_deg": round(self.strain_deg, 1),
        }


@dataclass(frozen=True)
class AzimuthReport:
    """Strain per crossover, split into twist drift and phasing.

    `crossovers[i].strain_deg` is the phasing strain -- after each helix's roll
    AND its steady twist drift have been fitted out. The drift is reported
    separately in `twist_deg_per_bp` and `accumulated_twist_deg`, because the
    two call for opposite verdicts: phasing error is a tiling defect, while
    twist is either corrected by deletions or, in a twist control, intended.
    """

    crossovers: tuple[Crossover, ...] = field(default_factory=tuple)
    twist_deg_per_bp: float = 0.0
    accumulated_twist_deg: float = 0.0
    raw_rms_deg: float = 0.0

    @property
    def strains(self) -> np.ndarray:
        return np.array([c.strain_deg for c in self.crossovers])

    @property
    def rms_deg(self) -> float:
        s = self.strains
        return float(np.sqrt((s**2).mean())) if len(s) else 0.0

    @property
    def wrong_face(self) -> tuple[Crossover, ...]:
        return tuple(c for c in self.crossovers if c.strain_deg > WRONG_FACE_DEG)

    @property
    def acceptable(self) -> bool:
        return self.rms_deg <= MAX_RMS_DEG

    @property
    def carries_twist(self) -> bool:
        return abs(self.accumulated_twist_deg) > TWIST_WARN_DEG

    def as_dict(self) -> dict[str, Any]:
        return {
            "crossovers": len(self.crossovers),
            "rms_strain_deg": round(self.rms_deg, 1),
            "wrong_face": len(self.wrong_face),
            "wrong_face_fraction": (
                round(len(self.wrong_face) / len(self.crossovers), 3) if self.crossovers else 0.0
            ),
            "acceptable": self.acceptable,
            "raw_rms_strain_deg": round(self.raw_rms_deg, 1),
            "twist_deg_per_bp": round(self.twist_deg_per_bp, 3),
            "accumulated_twist_deg": round(self.accumulated_twist_deg, 1),
            "carries_twist": self.carries_twist,
            "thresholds": {
                "wrong_face_deg": WRONG_FACE_DEG,
                "max_rms_deg": MAX_RMS_DEG,
                "twist_warn_deg": TWIST_WARN_DEG,
            },
        }


def _skips(design: sc.Design) -> tuple[dict[int, set[int]], dict[int, dict[int, int]]]:
    """Deletions and insertions per helix, from every domain on it."""
    deletions: dict[int, set[int]] = {}
    insertions: dict[int, dict[int, int]] = {}
    for strand in design.strands:
        for domain in strand.domains:
            if not hasattr(domain, "helix"):
                continue  # extensions and loopouts sit on no helix
            deletions.setdefault(domain.helix, set()).update(domain.deletions)
            for offset, length in domain.insertions:
                insertions.setdefault(domain.helix, {})[offset] = length
    return deletions, insertions


def backbone_angle(
    helix: Any,
    offset: int,
    forward: bool,
    geometry: Any,
    deletions: set[int],
    insertions: dict[int, int],
) -> float:
    """scadnano's backbone angle, counting bases rather than offsets."""
    bases = (
        offset
        - sum(1 for x in deletions if x < offset)
        + sum(n for x, n in insertions.items() if x < offset)
    )
    angle = helix.roll + bases * 360.0 / geometry.bases_per_turn
    if not forward:
        angle += geometry.minor_groove_angle
    return float(angle % 360.0)


def _wrap(x: np.ndarray) -> np.ndarray:
    return np.abs((x + 180.0) % 360.0 - 180.0)


def _relax(actual: np.ndarray, target: np.ndarray) -> np.ndarray:
    """Strains left after the roll is chosen as scadnano's `relax_helix_rolls` chooses it."""
    from scadnano.scadnano import minimum_strain_angle

    delta = minimum_strain_angle(list(zip(actual % 360.0, target, strict=True)))
    return _wrap(actual + delta - target)


def measure(design: sc.Design) -> AzimuthReport:
    """Residual strain of every inter-helix crossover, split into twist and phasing.

    Twist is fitted as ONE rate for the whole design -- the lattice mismatch
    that causes it is the same on every helix -- and each helix then gets its
    own roll. A rate per helix was tried first and overfits: a helix with four
    crossovers can absorb a real phasing error into a "twist" of its own.
    """
    from scadnano.scadnano import angle_from_helix_to_helix

    geometry, grid, helices = design.geometry, design.grid, design.helices
    deletions, insertions = _skips(design)
    per_helix: list[tuple[int, list[tuple[int, int, bool]], np.ndarray, np.ndarray]] = []
    for helix in helices.values():
        addresses = helix.crossover_addresses(
            helices, allow_intrahelix=False, allow_intergroup=False
        )
        if not addresses:
            continue
        actual = np.array(
            [
                backbone_angle(
                    helix,
                    offset,
                    forward,
                    geometry,
                    deletions.get(helix.idx, set()),
                    insertions.get(helix.idx, {}),
                )
                for _, offset, forward in addresses
            ]
        )
        target = np.array(
            [angle_from_helix_to_helix(helix, helices[p], grid, geometry) for p, _, _ in addresses]
        )
        per_helix.append((helix.idx, list(addresses), actual, target))

    def strains_at(rate: float) -> list[np.ndarray]:
        return [
            _relax(actual + rate * np.array([o for _, o, _ in addresses], dtype=float), target)
            for _, addresses, actual, target in per_helix
        ]

    raw = strains_at(0.0)
    rate = min(_TWIST_GRID, key=lambda r: sum(float((x**2).sum()) for x in strains_at(r)))
    fitted = strains_at(rate)

    found = [
        Crossover(idx, partner, offset, forward, float(strain))
        for (idx, addresses, _, _), strains in zip(per_helix, fitted, strict=True)
        for (partner, offset, forward), strain in zip(addresses, strains, strict=True)
    ]
    spans = [max(o for _, o, _ in a) - min(o for _, o, _ in a) for _, a, _, _ in per_helix]
    raw_all = np.concatenate(raw) if raw else np.array([])
    return AzimuthReport(
        crossovers=tuple(found),
        twist_deg_per_bp=rate,
        accumulated_twist_deg=rate * float(np.median(spans)) if spans else 0.0,
        raw_rms_deg=float(np.sqrt((raw_all**2).mean())) if len(raw_all) else 0.0,
    )
