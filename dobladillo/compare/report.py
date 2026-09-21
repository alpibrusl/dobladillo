"""Putting design, simulation and measurement of one quantity side by side.

The closed loop the project is for. What makes it worth a module rather than a
subtraction is that a disagreement has at least four possible authors, and only
the last one is interesting:

1. The two numbers are not the same quantity (a footprint is not an extent).
2. They were produced under conditions that cannot be reconciled.
3. They agree within their uncertainties and the difference is noise.
4. The design is wrong, or the model is, or the fold is.

`Comparison` answers 1 by refusing to compare unreconciled definitions, 2 by
carrying the mismatch into every report rather than dropping it, and 3 with a
combined standard error. What is left is 4, which is the result.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final

from dobladillo.compare.observation import Observation, definitions_comparable

#: Multiples of the combined standard error at which a difference stops being
#: attributable to noise. Two, not three: this is a screen for "look at this",
#: not a significance test, and the systematics are larger than the statistics
#: anyway.
AGREEMENT_SIGMA: Final = 2.0

#: Fallback uncertainty when neither side states one, as a fraction of the
#: larger value. Without it a designed number and a single-frame simulation
#: would appear to disagree infinitely. Flagged in the report whenever used.
ASSUMED_RELATIVE_UNCERTAINTY: Final = 0.05


@dataclass(frozen=True)
class Pair:
    """Two observations of one quantity, and what their difference means."""

    a: Observation
    b: Observation
    caveats: tuple[str, ...]
    assumed_uncertainty: bool

    #: Systematic difference expected between these two definitions, as a
    #: fraction. See `observation.Reconciliation`.
    expected_relative: float = 0.0

    @property
    def difference_nm(self) -> float:
        return self.b.value_nm - self.a.value_nm

    @property
    def combined_error_nm(self) -> float:
        errors = [o.standard_error_nm for o in (self.a, self.b)]
        known = [e for e in errors if e is not None and e > 0]
        if not known:
            return ASSUMED_RELATIVE_UNCERTAINTY * max(
                abs(self.a.value_nm), abs(self.b.value_nm), 1e-9
            )
        return float(sum(e**2 for e in known) ** 0.5)

    @property
    def sigma(self) -> float:
        return abs(self.difference_nm) / self.combined_error_nm

    @property
    def tolerance_nm(self) -> float:
        """How large a difference is explained before it is interesting.

        The larger of what noise explains and what the known systematic
        explains. Using only the first calls every expected end effect a
        catastrophe; using only the second hides a genuine drift inside a
        generous allowance.
        """
        return max(
            AGREEMENT_SIGMA * self.combined_error_nm,
            self.expected_relative * abs(self.a.value_nm),
        )

    @property
    def agrees(self) -> bool:
        return abs(self.difference_nm) <= self.tolerance_nm

    @property
    def explained_by(self) -> str:
        if not self.agrees:
            return "neither"
        if abs(self.difference_nm) <= AGREEMENT_SIGMA * self.combined_error_nm:
            return "noise"
        return "the expected systematic"

    @property
    def relative(self) -> float:
        base = abs(self.a.value_nm) or 1e-9
        return self.difference_nm / base

    def as_dict(self) -> dict[str, Any]:
        return {
            "from": self.a.origin,
            "to": self.b.origin,
            "values_nm": [round(self.a.value_nm, 2), round(self.b.value_nm, 2)],
            "difference_nm": round(self.difference_nm, 2),
            "relative": round(self.relative, 4),
            "combined_error_nm": round(self.combined_error_nm, 3),
            "sigma": round(self.sigma, 2),
            "tolerance_nm": round(self.tolerance_nm, 3),
            "expected_relative": self.expected_relative,
            "agrees": self.agrees,
            "explained_by": self.explained_by,
            "uncertainty_assumed": self.assumed_uncertainty,
            "caveats": list(self.caveats),
        }


@dataclass(frozen=True)
class Comparison:
    """Every pairing of one quantity's observations."""

    quantity: str
    observations: tuple[Observation, ...]
    pairs: tuple[Pair, ...]
    refused: tuple[str, ...]

    @property
    def agrees(self) -> bool:
        """False when nothing could be compared.

        `all([])` is True, so a comparison in which every pairing was refused
        would otherwise report agreement -- the most misleading answer
        available, since it is indistinguishable from a real one.
        """
        return bool(self.pairs) and all(p.agrees for p in self.pairs)

    @property
    def compared_anything(self) -> bool:
        return bool(self.pairs)

    @property
    def caveats(self) -> tuple[str, ...]:
        seen: list[str] = []
        for pair in self.pairs:
            for caveat in pair.caveats:
                if caveat not in seen:
                    seen.append(caveat)
        return tuple(seen)

    def as_dict(self) -> dict[str, Any]:
        return {
            "quantity": self.quantity,
            "agrees": self.agrees,
            "compared_anything": self.compared_anything,
            "observations": [o.as_dict() for o in self.observations],
            "pairs": [p.as_dict() for p in self.pairs],
            "refused": list(self.refused),
            "caveats": list(self.caveats),
        }

    def summary(self) -> str:
        verdict = "agrees" if self.agrees else "DISAGREES"
        lines = [f"{self.quantity}: {verdict if self.pairs else 'NOTHING COMPARED'}"]
        for observation in self.observations:
            error = observation.standard_error_nm
            spread = f" +- {error:.2f}" if error else ""
            lines.append(
                f"  {observation.origin:<10}{observation.value_nm:>8.1f}{spread} nm"
                + (f"   ({observation.note})" if observation.note else "")
            )
        for pair in self.pairs:
            verdict = f"ok, {pair.explained_by}" if pair.agrees else "DISAGREES"
            lines.append(
                f"  {pair.a.origin} -> {pair.b.origin}: {pair.difference_nm:+.1f} nm "
                f"({100 * pair.relative:+.1f}%), {pair.sigma:.1f} sigma, {verdict}"
            )
        for refusal in self.refused:
            lines.append(f"  refused: {refusal}")
        for caveat in self.caveats:
            lines.append(f"  caveat: {caveat}")
        return "\n".join(lines)


def compare(quantity: str, observations: list[Observation]) -> Comparison:
    """Pair up observations of one quantity.

    Observations whose definitions differ are refused rather than compared --
    that is what `corrections` is for, and doing it silently here would hide
    an 8 nm tip artefact inside a 3 nm disagreement.
    """
    if len({o.quantity for o in observations}) > 1:
        raise ValueError("every observation in a comparison must be of the same quantity")

    pairs, refused = [], []
    for i, a in enumerate(observations):
        for b in observations[i + 1 :]:
            allowed, terms = definitions_comparable(a.definition, b.definition)
            if not allowed:
                refused.append(
                    f"{a.origin} is {a.definition} and {b.origin} is {b.definition}; "
                    "these are different measurements of the same word and were not "
                    "reconciled, so they are not compared"
                )
                continue
            # A design is a specification, not a measurement: it has no salt
            # and no temperature, and demanding them would refuse every
            # comparison involving one -- which is most of the interesting
            # ones, since "does the model reproduce the design" is the
            # question the simulation exists to answer.
            condition_caveats: tuple[str, ...] = ()
            if "designed" in (a.origin, b.origin):
                comparable = True
            else:
                comparable, condition_caveats = a.conditions.comparable_with(b.conditions)
            if not comparable:
                reason = condition_caveats[0] if condition_caveats else "conditions differ"
                refused.append(f"{a.origin} against {b.origin}: {reason}")
                continue
            caveats = ((terms.caveat,) if terms else ()) + condition_caveats
            assumed = not any(
                o.standard_error_nm for o in (a, b) if o.standard_error_nm is not None
            )
            pairs.append(
                Pair(
                    a=a,
                    b=b,
                    caveats=caveats,
                    assumed_uncertainty=assumed,
                    expected_relative=terms.expected_relative if terms else 0.0,
                )
            )

    return Comparison(
        quantity=quantity,
        observations=tuple(observations),
        pairs=tuple(pairs),
        refused=tuple(refused),
    )
