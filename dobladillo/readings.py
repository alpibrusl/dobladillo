"""Measured against nominal: an instrument reading as a type.

The tip-radius rule -- no defaults, refuse rather than substitute -- used to be
enforced command by command. `experiment report` checked for a missing field,
`compare` made `--tip-radius` required, `afm measure` the same, and
`deconvolve_tip` quietly defaulted to 10 nm underneath all of them. Every new
command was one more place to remember the rule, and every helper function was
a place an agent could "helpfully" pass the number printed on the tip box.

So the rule lives here, once. A value that came off an instrument is a
`Measured`, and it carries what took it, when it entered the record, where in
the record it was read from, and how well it is known. A value from a
catalogue, a datasheet or a protocol's default is a `Nominal`. The two are
unrelated classes -- neither inherits from the other and there is no
conversion between them, on purpose -- so:

- **statically**, mypy rejects a `Nominal` (or a bare float) wherever a
  `Measured` is declared, before anything runs;
- **at run time**, `require_measured` raises `NotMeasured` for the same
  mistakes, because agents call Python dynamically and never see mypy.

What this does not do is make lying impossible. Anyone can construct a
`Measured` around a guess. What it does is make the claim explicit and
traceable: the reading names its source, so a guessed number has to be typed
in as a measurement *with a provenance*, and the provenance is written into
every result that used it. That is the difference between an accident and a
decision, and only the first was ever the problem.

Three quantities to start with -- the ones the experiment record holds and the
analysis consumes: tip radius, magnesium concentration and temperature. Tip
radius is the sharp one. A nominal 10 nm tip is routinely 8-20 nm in use, the
broadening goes as its square root, and a wrong value turns an agreement into
a disagreement or the reverse with nothing downstream able to tell.
"""

from __future__ import annotations

import statistics
import time
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Final, Generic, Literal, TypeVar

T = TypeVar("T")

Quantity = Literal["tip_radius", "magnesium", "temperature"]

#: The unit each quantity is carried in. Fixed per quantity, so a reading in
#: the wrong unit cannot be constructed without saying which unit it is in.
UNITS: Final[dict[Quantity, str]] = {
    "tip_radius": "nm",
    "magnesium": "mM",
    "temperature": "C",
}

#: How the time of a reading is known. `git` is a commit time and counts as
#: evidence; `filesystem` is a modification time, which a clone resets;
#: `stated` is the moment an operator typed the value into a command, which
#: says when it was asserted, not when it was measured.
TimeBasis = Literal["git", "filesystem", "stated"]


@dataclass(frozen=True)
class When:
    """When a reading entered the record, and how that is known."""

    timestamp: float
    basis: TimeBasis

    @classmethod
    def now(cls) -> When:
        return cls(timestamp=time.time(), basis="stated")

    def as_dict(self) -> dict[str, Any]:
        return {"at": self.timestamp, "basis": self.basis}


class NotMeasured(TypeError):
    """A value arrived where a measurement is required, and it is not one.

    A TypeError because that is what it is: the wrong kind of thing, not a
    wrong number. `kind` matches the CLI's structured failures.
    """

    kind: Final = "not_measured"


def _check_value(quantity: str, value: object, uncertainty: object) -> None:
    if quantity not in UNITS:
        raise ValueError(f"unknown quantity {quantity!r}; known: {', '.join(UNITS)}")
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TypeError(f"a {quantity} reading must be a number, got {value!r}")
    if quantity == "tip_radius" and value <= 0:
        raise ValueError(f"a tip radius must be positive, got {value}")
    if uncertainty is not None and (
        isinstance(uncertainty, bool) or not isinstance(uncertainty, int | float) or uncertainty < 0
    ):
        raise ValueError(f"uncertainty must be a non-negative number, got {uncertainty!r}")


@dataclass(frozen=True)
class Measured(Generic[T]):
    """A value an instrument produced, with the evidence that it did.

    `source` is where the reading was read from -- a field of
    `during/instrument.json`, or a command-line flag -- and is written into
    every result that used it. `instrument` is None when the record does not
    name one, which is itself worth seeing in a result.
    """

    value: T
    quantity: Quantity
    source: str
    at: When
    instrument: str | None = None
    uncertainty: T | None = None

    def __post_init__(self) -> None:
        _check_value(self.quantity, self.value, self.uncertainty)
        if not self.source:
            raise ValueError("a measurement must say where it was read from")

    @property
    def unit(self) -> str:
        return UNITS[self.quantity]

    @classmethod
    def stated(cls, value: T, quantity: Quantity, *, source: str) -> Measured[T]:
        """A value an operator typed into a command, asserting it was measured.

        The weakest provenance there is, and recorded as exactly that: no
        instrument, and a time that is when it was typed. It exists for the
        commands whose flag already demands a measured value; reading the
        record is always preferred.
        """
        return cls(value=value, quantity=quantity, source=source, at=When.now())

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": "measured",
            "quantity": self.quantity,
            "value": self.value,
            "unit": self.unit,
            "uncertainty": self.uncertainty,
            "instrument": self.instrument,
            "source": self.source,
            "recorded": self.at.as_dict(),
        }


@dataclass(frozen=True)
class Nominal(Generic[T]):
    """A value from a catalogue, a datasheet or a protocol default.

    Useful for display and for planning -- "a 10 nm tip would widen this by
    8.7 nm" -- and for nothing that turns an image into a result. It has no
    way to become a `Measured`.
    """

    value: T
    quantity: Quantity
    source: str

    def __post_init__(self) -> None:
        _check_value(self.quantity, self.value, None)

    @property
    def unit(self) -> str:
        return UNITS[self.quantity]

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": "nominal",
            "quantity": self.quantity,
            "value": self.value,
            "unit": self.unit,
            "source": self.source,
        }


def require_measured(value: object, quantity: Quantity, *, parameter: str) -> Measured[float]:
    """The run-time half of the type boundary.

    mypy stops a `Nominal` or a bare float at the call site, but only for code
    that is type-checked, and an agent calling a function from a REPL is not.
    So every function that needs a measurement calls this first. The message
    says what arrived and why it is not enough, because the likeliest caller
    is one trying to make an error go away.
    """
    if isinstance(value, Measured):
        if value.quantity != quantity:
            raise NotMeasured(
                f"{parameter} needs a measured {quantity}, got a measured {value.quantity}"
            )
        return value
    if isinstance(value, Nominal):
        raise NotMeasured(
            f"{parameter} needs a measured {quantity}; got a NOMINAL {value.value} "
            f"{value.unit} from {value.source}. A nominal value is what the part was sold "
            f"as, not what it was on the day: a nominal 10 nm tip is routinely 8-20 nm in "
            f"use. Measure it and record it in during/instrument.json."
        )
    raise NotMeasured(
        f"{parameter} needs a Measured {quantity} (dobladillo.readings.Measured), got "
        f"{type(value).__name__} {value!r}. A bare number carries no evidence that it "
        f"was measured, which is exactly how a nominal value gets in. Read it from "
        f"during/instrument.json, which records where it came from."
    )


def combine(
    readings: Sequence[Measured[float]], quantity: Quantity, *, source: str
) -> Measured[float]:
    """Several readings of one quantity, as one: their mean, with their spread.

    The spread (largest minus smallest) becomes the uncertainty rather than
    being averaged away: a tip that blunted from 10 to 14 nm across a session
    is known to 4 nm, not to the 12 nm mean's apparent precision. The time is
    the latest reading's, since the combination exists only once all of them
    do.
    """
    if not readings:
        raise ValueError("nothing to combine")
    checked = [require_measured(r, quantity, parameter=source) for r in readings]
    values = [r.value for r in checked]
    instruments = {r.instrument for r in checked}
    return Measured(
        value=statistics.fmean(values),
        quantity=quantity,
        source=source,
        at=max((r.at for r in checked), key=lambda w: w.timestamp),
        instrument=instruments.pop() if len(instruments) == 1 else None,
        uncertainty=max(values) - min(values) if len(values) > 1 else None,
    )
