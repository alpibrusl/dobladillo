"""A measured quantity, and everything needed to know whether it is comparable.

The closed loop produces three numbers for the length of the same rectangle.
They disagree, and most of the disagreement is not about the rectangle:

- The **design** says 191 nm, which is a base count times a rise per base pair.
- The **simulation** says a principal extent of a cloud of nucleotide
  positions, averaged over frames, at a monovalent proxy salt because oxDNA2
  has no explicit magnesium.
- The **AFM** says a footprint at half height, in a magnesium buffer, widened
  by a tip of finite radius.

Subtracting any two of those without saying so is the mistake this module
exists to make impossible. An `Observation` therefore carries not just a value
and an uncertainty but *what was measured* and *under what conditions*, and
`compare.report` refuses to put two of them side by side silently when either
differs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final, Literal

#: How a length was arrived at. Not a label: `corrections` maps between these,
#: and a pair with no mapping cannot be compared at all.
Definition = Literal["design_geometry", "simulated_extent", "afm_half_height"]

DEFINITIONS: Final[dict[Definition, str]] = {
    "design_geometry": "base count times rise per base pair, from scadnano's geometry",
    "simulated_extent": "principal extent of nucleotide positions, averaged over frames",
    "afm_half_height": "footprint at half height, widened by the tip",
}

Origin = Literal["designed", "simulated", "measured"]


@dataclass(frozen=True)
class Reconciliation:
    """What it takes to compare two different definitions of one word.

    `expected_relative` is the systematic difference the pair has *before
    anything is wrong*, and it is not optional decoration. A simulation
    averaged over two hundred frames has a standard error near 0.15 nm, so a
    2.6 nm end effect scores seventeen sigma and reads as a catastrophe. The
    statistics are answering the wrong question: the difference is real,
    expected, and uninteresting. A difference is only worth attention when it
    exceeds both what noise explains and what the known systematic explains.
    """

    caveat: str
    expected_relative: float


#: Which pairs of definitions may be compared, and on what terms. Same
#: definition needs no entry. A pair absent from here is refused -- which is
#: how an 8 nm tip artefact is kept from hiding inside a 3 nm disagreement,
#: since `afm_half_height` appears in no entry and must be deconvolved first.
COMPARABLE: Final[dict[frozenset[Definition], Reconciliation]] = {
    frozenset({"design_geometry", "simulated_extent"}): Reconciliation(
        caveat=(
            "a designed length is an idealised base count times a rise; a simulated extent "
            "is of a thermally fluctuating object and includes its ends, so a few per cent "
            "of difference is expected before anything is wrong"
        ),
        expected_relative=0.03,
    ),
}


def definitions_comparable(a: Definition, b: Definition) -> tuple[bool, Reconciliation | None]:
    """Whether two definitions may be compared, and on what terms."""
    if a == b:
        return True, None
    terms = COMPARABLE.get(frozenset({a, b}))
    return (True, terms) if terms else (False, None)


@dataclass(frozen=True)
class Conditions:
    """What the number was produced under.

    `salt_note` exists because the mismatch it describes cannot be fixed. oxDNA2
    models monovalent salt only, so a simulation runs at a sodium proxy while
    the experiment is in magnesium. Refusing to compare across that would make
    the module useless -- nothing would ever compare -- and ignoring it is the
    bug. So it is carried, named in every report, and never silently dropped.
    """

    temperature_c: float | None = None
    sodium_m: float | None = None
    magnesium_m: float | None = None
    model: str = ""

    @property
    def ionic_basis(self) -> str:
        if self.magnesium_m:
            return "magnesium"
        if self.sodium_m:
            return "sodium"
        return "unstated"

    def comparable_with(self, other: Conditions) -> tuple[bool, tuple[str, ...]]:
        """Whether two sets of conditions can be compared, and what is owed.

        Returns (comparable, caveats). Comparable is False only when something
        makes the comparison meaningless rather than merely qualified.
        """
        caveats = []
        if self.ionic_basis != other.ionic_basis:
            if "unstated" in (self.ionic_basis, other.ionic_basis):
                return False, (
                    f"one side does not state its ionic conditions ({self.ionic_basis} "
                    f"against {other.ionic_basis}); the comparison cannot be qualified "
                    "because it is not known what would need qualifying",
                )
            caveats.append(
                f"{self.ionic_basis} against {other.ionic_basis}: oxDNA2 has no explicit "
                "magnesium, so a simulated dimension at a sodium proxy and a measured one "
                "in a magnesium buffer differ by an unknown amount before anything about "
                "the structure is considered"
            )
        elif (
            self.sodium_m
            and other.sodium_m
            and abs(self.sodium_m - other.sodium_m) > 0.01 * max(self.sodium_m, other.sodium_m)
        ):
            caveats.append(f"different proxy salt: {self.sodium_m} M against {other.sodium_m} M")
        if (
            self.temperature_c is not None
            and other.temperature_c is not None
            and abs(self.temperature_c - other.temperature_c) > 5.0
        ):
            caveats.append(f"{self.temperature_c:.0f} C against {other.temperature_c:.0f} C")
        return True, tuple(caveats)

    def as_dict(self) -> dict[str, Any]:
        return {
            "temperature_c": self.temperature_c,
            "sodium_m": self.sodium_m,
            "magnesium_m": self.magnesium_m,
            "ionic_basis": self.ionic_basis,
            "model": self.model,
        }


@dataclass(frozen=True)
class Observation:
    """One number, with enough around it to be used honestly."""

    quantity: str
    value_nm: float
    definition: Definition
    origin: Origin
    conditions: Conditions
    uncertainty_nm: float | None = None
    n: int | None = None
    note: str = ""

    def __post_init__(self) -> None:
        if self.uncertainty_nm is not None and self.uncertainty_nm < 0:
            raise ValueError(f"uncertainty cannot be negative, got {self.uncertainty_nm}")
        if self.definition not in DEFINITIONS:
            raise ValueError(f"unknown definition {self.definition!r}")

    @property
    def standard_error_nm(self) -> float | None:
        """Uncertainty on the MEAN, which is what a comparison needs.

        A spread across particles is not the uncertainty on their average, and
        conflating them makes every disagreement look significant. With n
        unknown the spread is returned unchanged, which is conservative.
        """
        if self.uncertainty_nm is None:
            return None
        if not self.n or self.n < 2:
            return self.uncertainty_nm
        return float(self.uncertainty_nm / self.n**0.5)

    def as_dict(self) -> dict[str, Any]:
        return {
            "quantity": self.quantity,
            "value_nm": round(self.value_nm, 2),
            "definition": self.definition,
            "definition_means": DEFINITIONS[self.definition],
            "origin": self.origin,
            "uncertainty_nm": (
                None if self.uncertainty_nm is None else round(self.uncertainty_nm, 3)
            ),
            "standard_error_nm": (
                None if self.standard_error_nm is None else round(self.standard_error_nm, 3)
            ),
            "n": self.n,
            "conditions": self.conditions.as_dict(),
            "note": self.note,
        }
