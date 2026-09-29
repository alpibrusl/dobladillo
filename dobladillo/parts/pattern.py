"""E8's part: E1's rectangle with a pattern of hairpins, readable by AFM.

The method is Rothemund's (Nature 2006, Fig. 3; Supplementary Note S6):
selected staples carry a hairpin that stands above the sheet, and the
selected positions draw a picture an AFM can see. Everything else here is a
consequence of three constraints.

**1. Only the marked staples change.** The rectangle is `rothemund_rectangle()`
with its defaults -- E1's design, byte for byte -- and a marker is a 3'
extension appended to an existing staple. Every unmarked staple is E1's own
oligo, so E8 costs only the marked staples: pool E1's plates EXCEPT the wells
of the replaced staples, and add the marked versions. Not E1's finished pool:
that already contains the unmarked version of every marked staple, and the two
would compete for the same scaffold. Rothemund pooled exactly this way, from
matched plates of unmarked and marked strands (Supp. Note S6, Fig. S50).
`lab.plates.shared_pool` computes the wells to leave out.

**2. Every mark is on the same face -- and that face is measured, not
assumed.** A hairpin on a staple end points wherever that base's backbone
points. In this lattice staple crossovers sit on column boundaries, facing
their partner helix, and every staple end sits 8 bp (about three-quarters of
a turn) from one: out of the plane. Rothemund's Supplementary Fig. S12 draws
the two cases -- a staggered pattern of nicks puts every modification on one
face, a rectilinear one alternates faces by column. Which one this rectangle
is, is read from scadnano's own 3D model (`marker_faces`): the oxDNA
configuration it exports, each helix rolled so its staple crossovers face
their partners, and the backbone of each staple's 3' base projected on the
sheet normal. Every interior staple's 3' end points along +x cross +y, where
x runs along the helices (offset increasing) and y across them (helix index
increasing): one face, the staggered case. The edge staples' 3' ends lie in
the plane and are never marked.

So all marks are on one face, and the AFM sees them only on particles that
land marks-up. Rothemund reports that flipped structures, hairpins down,
"image poorly", and that 42% of rectangles carrying his 'DNA' pattern were
face-up (S = 55; Supp. Fig. S52); for rectangles in general "roughly 50%
appear flipped" (Supp. Fig. S44). E8 does not fight this, it uses it: a
face-down particle reads `blank`, and the blank fraction is a free internal
control -- the marks hide exactly when they should. That is why the readout is
the pattern among particles that show marks at all, and why the grid is drawn
as seen from the marked face.

**3. The pattern must be readable any way the particle lands.** The outline
fixes the long axis, so a particle is the design, a half turn of it, or one of
its two mirror images. The pattern is refused unless its four images differ
enough to be told apart with errors (`imaging.pattern`). The default is an "F"
four cells tall in the left third of the sheet: an F is chiral, and off-centre
it also tells a half turn from a mirror. Its images differ from it in at least
8 of the 50 cells, so up to 3 cells may be misread and the reading is still
unique.

**Cells, not single hairpins.** One cell is 32 bp by 4 helices -- about 10.5 x
12 nm -- and holds four staple ends. Rothemund resolved single hairpins 5.4 x
6 nm apart, but with "1 in 10" tips (Supp. Note S4.2), in liquid. A working
10 nm tip draws a 2 nm-tall mark about 6 nm in radius, so single pixels merge;
cells twice that size survive it. The outer helices and the first and last
columns are margin: their staple ends are edge staples lying in the plane.

**The hairpin.** 5'-TT-GAGAGATG-TTTT-CATCTCTC-3' on the staple's 3' end: a TT
spacer off the sheet, an 8 bp stem, a T4 loop. Not Rothemund's dumbbell (two
5 bp stems): primer3 folds one hairpin per strand and cannot check a dumbbell,
and Rothemund states he never tested plain hairpins and that "they might have
worked without difficulty" (Supp. Note S6). He chose the dumbbell against
dimers between hairpins; that risk is computed here instead of designed away
-- see `HairpinCheck`, and the E8 failure table for what to do if aggregates
appear. The stem was chosen from a seeded search (`hairpin_candidates`,
`choose_hairpin`): among 8 bp stems of 4-5 G/C with no homopolymer runs,
those whose every pairing with the scaffold or an E1 staple melts below room
temperature, then the one whose homodimer melts lowest. primer3's numbers
for it, at the ends of the 5-20 mM Mg screen: hairpin Tm 69.3 C at 5 mM
(above the 60 C start of the anneal ramp, so it is folded before any staple
binds); worst off-target Tm 23.9 C (the scaffold) at 20 mM; homodimer Tm
45.4 C at the fold's 1.4 uM of marker strands -- but against two folded
hairpins the dimer loses by 4.0 kcal/mol at 25 C. `tests/test_pattern.py`
pins every one of these.
"""

from __future__ import annotations

import copy
import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final

import numpy as np

from dobladillo import _scadnano as ad
from dobladillo.constants import (
    ANNEAL_RAMP_FROM_C,
    MGCL2_SCREEN_MM,
    SCAFFOLD_CONC_NM,
    STAPLE_EXCESS,
)
from dobladillo.imaging.pattern import GridCell, PatternGrid
from dobladillo.parts.rectangle import Rectangle, rothemund_rectangle
from dobladillo.sequence.thermo import (
    PRIMER3_MAX_LENGTH,
    R_KCAL,
    Structure,
    reverse_complement,
    secondary_structure,
)

if TYPE_CHECKING:
    import scadnano as sc

__all__ = [
    "BASE_PART",
    "DEFAULT_PATTERN",
    "MARKER_HAIRPIN",
    "HairpinCheck",
    "Marker",
    "PatternedRectangle",
    "check_hairpin",
    "marker_faces",
    "patterned_rectangle",
]

#: The part whose staple pool E8 reuses, by the name `dobladillo lab order` knows.
BASE_PART: Final = "rectangle"

#: Spacer, stem, loop, stem: see the module docstring.
MARKER_SPACER: Final = "TT"
MARKER_STEM: Final = "GAGAGATG"
MARKER_LOOP: Final = "TTTT"
MARKER_HAIRPIN: Final = MARKER_SPACER + MARKER_STEM + MARKER_LOOP + reverse_complement(MARKER_STEM)

#: What a marked staple carries. `hairpin` is E8's all-DNA mark, seen by AFM
#: as a bump on the sheet. `biotin` is a 3' biotin behind a short spacer on the
#: SAME staple ends, for marks made visible by binding streptavidin (K6 compares
#: the two under a high-speed AFM tip; Kielar et al. 2020 saw streptavidin
#: stripped by the tip). Same ends, same face, same cells: the tile's geometry
#: does not depend on the choice.
MARKERS: Final = ("hairpin", "biotin")

#: Unpaired bases between the staple's last paired base and the biotin, the
#: same TT that lifts E8's hairpin off the sheet. Chosen, not derived.
BIOTIN_SPACER: Final = "TT"

#: One cell of the pattern. 32 bp is two of the rectangle's 16 bp columns,
#: which holds exactly one staple end per helix; 4 helices is about 12 nm.
CELL_BP: Final = 32
CELL_HELICES: Final = 4

#: Helices left unmarked along each long edge.
MARGIN_HELICES: Final = 1

#: A cell with fewer out-of-plane staple ends than this cannot carry a mark
#: that the others would not outshine. The edge columns have two.
MIN_MARKS_PER_CELL: Final = 3

#: A staple end counts as pointing off the sheet when its backbone is within
#: 45 degrees of the normal. Interior staple ends measure cos 0.9-1.0 and edge
#: staple ends -0.4 to -0.2 (in the plane), so nothing sits near the line.
FACE_MIN_COS: Final = math.cos(math.radians(45.0))

#: The pattern, top row first, as seen from the marked face with the helices
#: running left to right. 'X' marks a cell. See the module docstring.
DEFAULT_PATTERN: Final = (
    ".XXX......",
    ".XX.......",
    ".X........",
    ".X........",
    "..........",
)

#: Each staple's final concentration in the fold, nM: the folding protocol's.
STAPLE_NM: Final = SCAFFOLD_CONC_NM[0] * STAPLE_EXCESS[0]


@dataclass(frozen=True)
class Marker:
    """One marked staple: where its 3' end is, and how squarely it faces up."""

    helix: int
    offset: int
    cell: tuple[int, int]
    face_cos: float
    unmarked_sequence: str
    sequence: str
    #: The vendor code of a 3' modification, e.g. IDT's "/3Bio/"; None for a hairpin.
    modification_3p: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "helix": self.helix,
            "offset_3p": self.offset,
            "cell": list(self.cell),
            "face_cos": round(self.face_cos, 3),
            "unmarked_sequence": self.unmarked_sequence,
            "sequence": self.sequence,
            "modification_3p": self.modification_3p,
        }


@dataclass(frozen=True)
class HairpinCheck:
    """What primer3 says about the marker hairpin, at the ends of the Mg screen.

    Each check is taken where it is hardest to pass: the hairpin's own
    stability at the LOWEST magnesium of the screen, the unwanted pairings at
    the HIGHEST. The homodimer is at the total concentration of marker
    strands in a fold (every marked staple carries the same hairpin), the
    others at one staple's.

    primer3's homodimer melting point is a dimer against two UNFOLDED strands,
    and says nothing about whether the dimer beats two folded hairpins -- the
    comparison that matters, because the hairpin forms first on the way down
    the ramp. `dimer_over_hairpins_kcal` makes it: the dimer's free energy at
    the fold's marker concentration minus two hairpins', both at the top of
    the screen. Positive means two hairpins are the more stable state. What
    no calculation here covers is two marks on the SAME particle, 5-6 nm
    apart, where the local concentration is far higher; that shows up as
    marks merging, not as aggregates, and the cells are larger than a pair.
    """

    sequence: str
    hairpin: Structure
    hairpin_high_mg: Structure
    homodimer: Structure
    scaffold: Structure
    worst_staple: Structure
    worst_staple_name: str

    @property
    def folds_before_staples_bind(self) -> bool:
        """The hairpin melts above the start of the anneal ramp, so it is
        already folded when the staples start to bind."""
        return self.hairpin.found and self.hairpin.tm_c > ANNEAL_RAMP_FROM_C

    @property
    def dimer_over_hairpins_kcal(self) -> float:
        rt = R_KCAL * (self.homodimer.temperature_c + 273.15)
        dimer = self.homodimer.dg_kcal + rt * math.log(1.0 / self.homodimer.strand_m)
        return dimer - 2.0 * self.hairpin_high_mg.dg_kcal

    def as_dict(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "stem_bp": len(MARKER_STEM) if self.sequence == MARKER_HAIRPIN else None,
            "hairpin": self.hairpin.as_dict(),
            "hairpin_at_top_of_screen": self.hairpin_high_mg.as_dict(),
            "homodimer": self.homodimer.as_dict(),
            "dimer_over_two_hairpins_kcal_per_mol": round(self.dimer_over_hairpins_kcal, 2),
            "against_scaffold": self.scaffold.as_dict(),
            "against_worst_e1_staple": {
                **self.worst_staple.as_dict(),
                "staple": self.worst_staple_name,
            },
            "folds_before_staples_bind": self.folds_before_staples_bind,
            "source": "primer3 thal (SantaLucia 1998 stacks, SantaLucia and Hicks 2004 loops, "
            "von Ahsen 2001 Mg equivalent); "
            "see sequence.thermo.SALT_NOTE for how far to trust the salt correction",
        }


def circular_scaffold(variant: str) -> str:
    """The whole scaffold, with its start repeated at the end so that a
    pairing across the circle's join is not missed. Every base of it, routed
    or not: see `_scadnano.scaffold_sequence`."""
    whole = ad.scaffold_sequence(variant)
    return whole + whole[: PRIMER3_MAX_LENGTH - 1]


def check_hairpin(
    sequence: str, *, scaffold: str, staples: dict[str, str], copies: int
) -> HairpinCheck:
    """Fold, dimer and off-target checks for a marker hairpin."""
    low, high = (m / 1000.0 for m in MGCL2_SCREEN_MM)
    one = STAPLE_NM * 1e-9
    hairpin = secondary_structure(sequence, kind="hairpin", magnesium_m=low)
    hairpin_high = secondary_structure(sequence, kind="hairpin", magnesium_m=high)
    homodimer = secondary_structure(
        sequence, kind="homodimer", magnesium_m=high, strand_m=one * copies
    )
    against_scaffold = secondary_structure(
        sequence, scaffold, kind="heterodimer", magnesium_m=high, strand_m=one
    )
    worst_name, worst = max(
        (
            (
                name,
                secondary_structure(
                    sequence, staple, kind="heterodimer", magnesium_m=high, strand_m=one
                ),
            )
            for name, staple in staples.items()
        ),
        key=lambda pair: pair[1].tm_c,
    )
    return HairpinCheck(
        sequence=sequence,
        hairpin=hairpin,
        hairpin_high_mg=hairpin_high,
        homodimer=homodimer,
        scaffold=against_scaffold,
        worst_staple=worst,
        worst_staple_name=worst_name,
    )


def hairpin_candidates(
    *, scaffold: str, staples: list[str], copies: int, seed: int = 8, tries: int = 400
) -> list[tuple[float, float, str]]:
    """The search MARKER_STEM came from, kept so it can be rerun.

    Random 8 bp stems with 4-5 G/C, no run of three identical bases, not
    self-complementary; the full extension (spacer, stem, T4 loop, stem') may
    not contain GGG, CCC or AAAA. For each: the highest melting point of the
    extension against the scaffold and every E1 staple, and of its homodimer,
    both at the top of the Mg screen (one staple's concentration, and
    `copies` staples' for the homodimer). Returns (off-target Tm, homodimer
    Tm, extension), sorted by off-target Tm. `choose_hairpin` picks from it.
    """
    import random
    import re

    rng = random.Random(seed)
    high = MGCL2_SCREEN_MM[1] / 1000.0
    one = STAPLE_NM * 1e-9
    ranked: list[tuple[float, float, str]] = []
    for _ in range(tries):
        stem = "".join(rng.choice("ACGT") for _ in range(8))
        gc = sum(b in "GC" for b in stem)
        if not 4 <= gc <= 5 or re.search(r"(.)\1\1", stem) or stem == reverse_complement(stem):
            continue
        extension = MARKER_SPACER + stem + MARKER_LOOP + reverse_complement(stem)
        if re.search(r"GGG|CCC|AAAA", extension):
            continue
        worst = max(
            secondary_structure(
                extension, partner, kind="heterodimer", magnesium_m=high, strand_m=one
            ).tm_c
            for partner in [scaffold, *staples]
        )
        homodimer = secondary_structure(
            extension, kind="homodimer", magnesium_m=high, strand_m=one * copies
        ).tm_c
        ranked.append((worst, homodimer, extension))
    return sorted(ranked)


#: Off-target pairings must melt below this: room temperature, where the
#: folded sample is purified, stored and imaged. A bench condition, not a
#: physical constant; it is the temperature every check here reports dG at.
ROOM_C: Final = 25.0


def choose_hairpin(candidates: list[tuple[float, float, str]]) -> str:
    """Among candidates whose off-target pairings all melt below room
    temperature, the one whose homodimer melts lowest.

    Off-target first, because an extension that pairs with the scaffold's
    unrouted loop (319 nt here) or a staple tethers things that should be
    free. The homodimer second, because it competes with a hairpin that has
    already formed, and `HairpinCheck.dimer_over_hairpins_kcal` shows the
    hairpins win that competition anyway.
    """
    cool = [c for c in candidates if c[0] < ROOM_C]
    if not cool:
        raise ValueError(f"no candidate has every off-target pairing melting below {ROOM_C} C")
    return min(cool, key=lambda c: c[1])[2]


def _configuration(design: sc.Design) -> np.ndarray:
    """scadnano's oxDNA configuration: one row per nucleotide, r | b | n."""
    dat, _ = ad.oxdna_text(design)
    rows = [line.split() for line in dat.splitlines()[3:] if line.strip()]
    return np.array([[float(v) for v in row[:9]] for row in rows])


def _unit(v: np.ndarray) -> np.ndarray:
    return v / float(np.linalg.norm(v))


def _end_offset(domain: Any, *, three_prime: bool) -> int:
    if three_prime:
        return int(domain.end - 1 if domain.forward else domain.start)
    return int(domain.start if domain.forward else domain.end - 1)


def marker_faces(design: sc.Design) -> dict[int, float]:
    """For every staple, the cosine between its 3' base's backbone and the sheet normal.

    Keyed by the staple's index in `ad.staples(design)`. The normal is x
    cross y, x along the helices in the direction of increasing offset and y
    from helix 0 towards helix 1. Read from scadnano's oxDNA export, not from
    its angle conventions: scadnano's own `relax_helix_rolls` disagrees with
    its oxDNA writer by about 90 degrees on this design (measured), so neither
    convention is trusted and the geometry is taken from the 3D coordinates.

    The export leaves every helix at roll 0. Each helix is rolled here so its
    staple crossovers face their partners -- the circular mean of their
    misalignments, as scadnano's `minimum_strain_angle` does -- and the
    residual is what `routing.azimuth` reports for published designs (about
    20 degrees rms on this one). A roll is a rigid rotation of the helix, so
    it moves every base on it by the same angle, staple ends included.
    """
    conf = _configuration(design)
    index = ad.nucleotide_indices(design)
    backbone = -conf[:, 3:6]  # b points backbone -> base; the axis is on the base side

    by_helix: dict[int, list[int]] = {}
    for (helix, _, _), i in index.items():
        by_helix.setdefault(helix, []).append(i)
    centroid = {h: conf[idx, :3].mean(axis=0) for h, idx in by_helix.items()}

    # x: along helix 0, from its low offsets to its high ones.
    offsets = sorted((o, i) for (h, o, f), i in index.items() if h == 0 and f)
    x = _unit(conf[offsets[-1][1], :3] - conf[offsets[0][1], :3])

    def perp(v: np.ndarray) -> np.ndarray:
        return _unit(v - x * float(x @ v))

    y = perp(centroid[1] - centroid[0])
    normal = np.cross(x, y)

    def signed(a: np.ndarray, b: np.ndarray) -> float:
        return float(np.arctan2(np.cross(a, b) @ x, a @ b))

    misalignment: dict[int, list[float]] = {}
    for strand in ad.staples(design):
        bound = [d for d in strand.domains if hasattr(d, "helix")]
        for a, b in zip(bound, bound[1:], strict=False):
            if a.helix == b.helix:
                continue
            for domain, partner, last in ((a, b, True), (b, a, False)):
                i = index[(domain.helix, _end_offset(domain, three_prime=last), domain.forward)]
                target = perp(centroid[partner.helix] - centroid[domain.helix])
                misalignment.setdefault(domain.helix, []).append(signed(target, perp(backbone[i])))
    roll = {
        h: -float(np.angle(np.mean(np.exp(1j * np.array(angles)))))
        for h, angles in misalignment.items()
    }

    def rotate(v: np.ndarray, angle: float) -> np.ndarray:
        c, s = math.cos(angle), math.sin(angle)
        return v * c + np.cross(x, v) * s + x * float(x @ v) * (1 - c)

    faces: dict[int, float] = {}
    for k, strand in enumerate(ad.staples(design)):
        bound = [d for d in strand.domains if hasattr(d, "helix")]
        last = bound[-1]
        i = index[(last.helix, _end_offset(last, three_prime=True), last.forward)]
        faces[k] = float(rotate(perp(backbone[i]), roll[last.helix]) @ normal)
    return faces


def _parse(pattern: tuple[str, ...], *, columns: int, rows: int) -> frozenset[tuple[int, int]]:
    if len(pattern) != rows or any(len(line) != columns for line in pattern):
        raise ValueError(
            f"a pattern for this rectangle is {rows} rows of {columns} cells, top row first; "
            f"got {len(pattern)} rows of {sorted({len(line) for line in pattern})}"
        )
    if any(set(line) - {"X", "."} for line in pattern):
        raise ValueError("a pattern is written with 'X' for a marked cell and '.' for an empty one")
    on = frozenset(
        (col, rows - 1 - i)
        for i, line in enumerate(pattern)
        for col, char in enumerate(line)
        if char == "X"
    )
    if not on:
        raise ValueError("a pattern with no marked cell is E1's rectangle; order that instead")
    return on


@dataclass(frozen=True)
class PatternedRectangle:
    """E1's rectangle with marker hairpins on the staples under a pattern."""

    design: sc.Design
    rectangle: Rectangle
    pattern: tuple[str, ...]
    grid: PatternGrid
    markers: tuple[Marker, ...]
    #: primer3's check of the hairpin; None when the marks are not hairpins.
    hairpin: HairpinCheck | None
    marker: str = "hairpin"

    @property
    def scaffold(self) -> ad.ScaffoldAccounting:
        return self.rectangle.scaffold

    @property
    def staple_count(self) -> int:
        return self.rectangle.staple_count

    @property
    def dimensions_nm(self) -> tuple[float, float]:
        return self.rectangle.dimensions_nm

    @property
    def base_part(self) -> str:
        return BASE_PART

    def order_design(self) -> sc.Design:
        """A copy holding only the marked staples (and the scaffold): what to order.

        Everything else is on E1's plates already. The scaffold stays so that
        the copy is still a design scadnano will write; it carries no vendor
        fields and so never reaches a plate.
        """
        marked = {m.sequence for m in self.markers}
        copied = copy.deepcopy(self.design)
        for strand in list(ad.staples(copied)):
            if strand.dna_sequence not in marked:
                copied.remove_strand(strand)
        return copied

    def as_dict(self) -> dict[str, Any]:
        base = self.rectangle.as_dict()
        lengths = ad.staple_lengths(self.design)
        return {
            **base,
            "part": "patterned_rectangle",
            "staple_length_nt": {
                "min": min(lengths),
                "max": max(lengths),
                "distinct": sorted(set(lengths)),
            },
            "reuses": {
                "part": BASE_PART,
                "unchanged_staples": self.staple_count - len(self.markers),
                "marked_staples": len(self.markers),
            },
            "pattern": {
                "rows_top_first": list(self.pattern),
                "cell_bp": CELL_BP,
                "cell_helices": CELL_HELICES,
                "marked_cells": len(self.grid.on),
                "marks": len(self.markers),
                "marked_face": "+x cross +y: x along the helices, offset increasing; "
                "y across them, helix index increasing",
                "grid": self.grid.as_dict(),
            },
            "marker": self.marker,
            "hairpin": self.hairpin.as_dict() if self.hairpin else None,
            "markers": [m.as_dict() for m in self.markers],
        }


def _x_nm(offset: int, deletions: list[int], rise: float) -> float:
    """Distance along a helix to `offset`, counting bases rather than offsets."""
    return (offset - sum(1 for d in deletions if d < offset)) * rise


def patterned_rectangle(
    pattern: tuple[str, ...] = DEFAULT_PATTERN,
    *,
    hairpin: str = MARKER_HAIRPIN,
    marker: str = "hairpin",
) -> PatternedRectangle:
    """Build E1's rectangle and mark the staples whose 3' ends fall in marked cells.

    Refuses a pattern that cannot be read unambiguously (see
    `imaging.pattern`), a marked cell with too few staple ends facing the
    marked face, and a hairpin that primer3 says is not folded by the time
    the staples bind.
    """
    if marker not in MARKERS:
        raise ValueError(f"marker must be one of {MARKERS}, got {marker!r}")
    rectangle = rothemund_rectangle()  # E1's defaults, deliberately not exposed
    design = rectangle.design
    helices, length = rectangle.helices, rectangle.length
    usable = helices - 2 * MARGIN_HELICES
    if usable % CELL_HELICES or length % CELL_BP:
        raise ValueError("the rectangle does not divide into whole pattern cells")
    columns, rows = length // CELL_BP, usable // CELL_HELICES
    on = _parse(tuple(pattern), columns=columns, rows=rows)

    hairpin = hairpin.upper().strip()
    unmarked = {k: s.dna_sequence or "" for k, s in enumerate(ad.staples(design))}
    from dobladillo.lab.plates import staple_name

    names = {k: staple_name(s) for k, s in enumerate(ad.staples(design))}

    # Where every staple end is, and which cell it would mark.
    faces = marker_faces(design)
    candidates: dict[tuple[int, int], list[tuple[int, int, int, float]]] = {}
    for k, strand in enumerate(ad.staples(design)):
        last = [d for d in strand.domains if hasattr(d, "helix")][-1]
        offset = _end_offset(last, three_prime=True)
        helix = int(last.helix)
        if not MARGIN_HELICES <= helix < helices - MARGIN_HELICES:
            continue
        if faces[k] < FACE_MIN_COS:
            continue
        cell = (offset // CELL_BP, (helix - MARGIN_HELICES) // CELL_HELICES)
        candidates.setdefault(cell, []).append((k, helix, offset, faces[k]))

    # Grid geometry, nm from the sheet's centre. Deletions are identical on
    # every helix here, so one helix's set places them all.
    rise = float(ad.GEOMETRY.rise_per_base_pair)
    spacing = ad.interhelix_spacing_nm()
    deletions = sorted(
        {
            x
            for d in ad.scaffold_strand(design).domains
            if getattr(d, "helix", None) == 0
            for x in d.deletions
        }
    )
    half_x = _x_nm(length, deletions, rise) / 2.0
    mid_helix = (helices - 1) / 2.0

    marks = [m for cell in sorted(on) for m in candidates.get(cell, [])]
    cells = []
    for col in range(columns):
        for row in range(rows):
            bottom = MARGIN_HELICES + row * CELL_HELICES - 0.5 - mid_helix
            cells.append(
                GridCell(
                    col=col,
                    row=row,
                    x_nm=(
                        _x_nm(col * CELL_BP, deletions, rise) - half_x,
                        _x_nm((col + 1) * CELL_BP, deletions, rise) - half_x,
                    ),
                    y_nm=(bottom * spacing, (bottom + CELL_HELICES) * spacing),
                    on=(col, row) in on,
                )
            )
    grid = PatternGrid(
        columns=columns,
        rows=rows,
        cells=tuple(cells),
        marks_nm=tuple(
            (_x_nm(offset, deletions, rise) + rise / 2.0 - half_x, (helix - mid_helix) * spacing)
            for _, helix, offset, _ in marks
        ),
    )
    if grid.min_distance < 3:
        raise ValueError(
            f"this pattern differs from one of its half-turn or mirror images in only "
            f"{grid.min_distance} cells, so a particle cannot be read with even one cell "
            "wrong. Make it less symmetric or move it off-centre.\n" + grid.render()
        )
    thin = {cell: len(candidates.get(cell, [])) for cell in on}
    thin = {cell: n for cell, n in thin.items() if n < MIN_MARKS_PER_CELL}
    if thin:
        raise ValueError(
            f"marked cells {sorted(thin)} have {sorted(set(thin.values()))} staple ends facing "
            f"the marked face, fewer than {MIN_MARKS_PER_CELL}; the first and last columns hold "
            "edge staples whose ends lie in the plane"
        )

    staples_by_index = ad.staples(design)
    extension = hairpin if marker == "hairpin" else BIOTIN_SPACER
    for k, _, _, _ in marks:
        ad.add_extension_3p(design, staples_by_index[k], num_bases=len(extension))
    placed = ad.assign_extension_sequence(
        design, min_offset=0, max_offset=length, sequence=extension
    )
    if placed != len(marks):
        raise AssertionError(
            f"expected {len(marks)} marker extensions, placed {placed}; the design would be "
            "ordered with marks missing"
        )

    check: HairpinCheck | None = None
    if marker == "hairpin":
        check = check_hairpin(
            hairpin,
            scaffold=circular_scaffold(rectangle.scaffold.variant),
            staples={names[k]: s for k, s in unmarked.items()},
            copies=len(marks),
        )
        if not check.folds_before_staples_bind:
            raise ValueError(
                f"primer3 puts the hairpin {hairpin} at Tm {check.hairpin.tm_c:.1f} C at "
                f"{MGCL2_SCREEN_MM[0]:g} mM MgCl2, below the {ANNEAL_RAMP_FROM_C:g} C start of "
                "the anneal ramp: it would still be single-stranded while the staples bind"
            )
    else:
        # scadnano's own 3' biotin, IDT code /3Bio/. IDT also sells a TEG-spaced
        # biotin that may bind streptavidin more readily; that is the
        # experimentalist's call, and swapping it is one line here.
        from scadnano import biotin_3p

        for k, _, _, _ in marks:
            staples_by_index[k].set_modification_3p(biotin_3p)

    after = ad.staples(design)
    markers = tuple(
        Marker(
            helix=helix,
            offset=offset,
            cell=(offset // CELL_BP, (helix - MARGIN_HELICES) // CELL_HELICES),
            face_cos=face,
            unmarked_sequence=unmarked[k],
            sequence=after[k].dna_sequence or "",
            modification_3p=(
                after[k].modification_3p.vendor_code if after[k].modification_3p else None
            ),
        )
        for k, helix, offset, face in marks
    )
    return PatternedRectangle(
        design=design,
        rectangle=rectangle,
        pattern=tuple(pattern),
        grid=grid,
        markers=markers,
        hairpin=check,
        marker=marker,
    )
