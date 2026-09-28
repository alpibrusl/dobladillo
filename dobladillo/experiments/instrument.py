"""`during/instrument.json`, read into typed readings. The one boundary.

The session record is a JSON file a person fills in by hand, so everything in
it arrives as a bare number or a null. This is where those numbers become
`Measured` or `Nominal`, and it is the only place: a command that needs a tip
radius asks this module for one and receives either a `Measured` with its
provenance or None, never a float it could mistake for either.

The distinction is made by the field, not by the value. `tip.measured_radius_*`
is a measurement; `tip.nominal_radius_nm` is what the tip was sold as, and
comes back as a `Nominal` that nothing downstream will accept in its place.
A null is None -- absent, not zero, and not the nominal value.

The time a reading carries is when `instrument.json` entered the record:
its commit time where git tracks it, its modification time otherwise, and the
basis says which. The file records no per-reading times, and inventing them
would be exactly the kind of number this module exists to keep out.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from dobladillo.experiments.layout import recorded_at
from dobladillo.readings import Measured, Nominal, Quantity, When

#: Where each reading lives in the file. The tip is read before and after
#: every session, and between the two samples of a paired experiment (E2).
TIP_FIELDS: Final = {
    "before": ("tip", "measured_radius_before_nm"),
    "between": ("tip", "measured_radius_between_nm"),
    "after": ("tip", "measured_radius_after_nm"),
}
MAGNESIUM_FIELD: Final = ("buffer", "mgcl2_mm")
TEMPERATURE_FIELD: Final = ("temperature_c",)
NOMINAL_TIP_FIELD: Final = ("tip", "nominal_radius_nm")


@dataclass(frozen=True)
class InstrumentRecord:
    """A session's instrument record, with its readings typed."""

    path: Path
    data: dict[str, Any]
    #: Keyed "before", "between", "after"; None where the field is empty.
    tip: dict[str, Measured[float] | None]
    tip_nominal: Nominal[float] | None
    magnesium: Measured[float] | None
    temperature: Measured[float] | None


def _lookup(data: dict[str, Any], path: tuple[str, ...]) -> Any:
    value: Any = data
    for key in path:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)


def read_instrument(directory: Path) -> InstrumentRecord | None:
    """The folder's instrument record, or None if it has none.

    Raises ValueError for a reading that cannot be one -- a tip radius of zero
    or less -- rather than dropping it: a value someone wrote is not absent,
    and treating it as absent would hide the mistake behind a missing-field
    message.
    """
    path = directory / "during" / "instrument.json"
    if not path.is_file():
        return None
    data = json.loads(path.read_text())
    recorded = recorded_at(path)
    when = When(
        timestamp=recorded.timestamp or 0.0,
        basis="git" if recorded.source == "git" else "filesystem",
    )
    name = data.get("instrument")
    instrument = name.strip() or None if isinstance(name, str) else None

    def measured(quantity: Quantity, field: tuple[str, ...]) -> Measured[float] | None:
        value = _number(_lookup(data, field))
        if value is None:
            return None
        return Measured(
            value=value,
            quantity=quantity,
            source=f"during/instrument.json: {'.'.join(field)}",
            at=when,
            instrument=instrument,
        )

    nominal_value = _number(_lookup(data, NOMINAL_TIP_FIELD))
    return InstrumentRecord(
        path=path,
        data=data,
        tip={name: measured("tip_radius", field) for name, field in TIP_FIELDS.items()},
        tip_nominal=(
            None
            if nominal_value is None
            else Nominal(
                value=nominal_value,
                quantity="tip_radius",
                source=f"during/instrument.json: {'.'.join(NOMINAL_TIP_FIELD)}",
            )
        ),
        magnesium=measured("magnesium", MAGNESIUM_FIELD),
        temperature=measured("temperature", TEMPERATURE_FIELD),
    )
