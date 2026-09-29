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


# ------------------------------------------------ calibration conditions (#28)
#
# A calibration is of the instrument in one configuration, of a reference in
# one preparation. The K protocols (experiments/protocols/K*.md) first wrote
# these into CSVs of their own because the record had no place for them. They
# are not readings with a quantity and a time, so they are parsed here into
# plain values, each either recorded, missing or invalid -- never defaulted.

#: Written where a value is deliberately withheld from the analyst: K5 codes
#: its depositions and gives the key only after `post/` is committed blind.
BLINDED: Final = "blinded"

#: The scan directions a line is recorded in.
DIRECTIONS: Final = ("trace", "retrace")


@dataclass(frozen=True)
class ConditionField:
    """One condition: where it lives, what it means, what may be written."""

    path: tuple[str, ...]
    meaning: str
    allowed: str
    #: The refusal kind when a command needs it and it is not recorded.
    kind: str

    @property
    def name(self) -> str:
        return ".".join(self.path)


#: The conditions every calibration-tile (K) experiment records, in the order
#: `experiment check` lists them. Which analyses need which is
#: `experiments.calibration.REQUIRES`.
CALIBRATION_CONDITIONS: Final = (
    ConditionField(
        ("deposition", "mgcl2_mm"),
        "MgCl2 in the deposition buffer, mM (Mg2+ bridges DNA to mica). Not the folding "
        "buffer's, which is buffer.mgcl2_mm",
        f'a number >= 0, or "{BLINDED}" while the analysis is blind to it (K5)',
        "no_deposition_cations",
    ),
    ConditionField(
        ("deposition", "nicl2_mm"),
        "NiCl2 added to the deposition buffer, mM (Ni2+ holds particles harder and can "
        "distort them, K5). 0 when none was added: empty means not recorded",
        f'a number >= 0, or "{BLINDED}"',
        "no_deposition_cations",
    ),
    ConditionField(
        ("scan", "angle_deg"),
        "the scan rotation, degrees. The image's x is the fast axis whatever the stage "
        "does, so a scale x at 90 degrees is the scanner's other piezo",
        "a number for every scan, or an object from file (its path under during/raw, "
        "* and ? allowed, first match wins) to a number",
        "no_scan_angle",
    ),
    ConditionField(
        ("scan", "direction"),
        "the line direction the analysed images were recorded in. Hysteresis makes trace "
        "and retrace differently wrong",
        '"trace" or "retrace". A retrace analysis of a multi-channel native file also '
        "names its channel in scan.channel",
        "no_scan_direction",
    ),
    ConditionField(
        ("scan", "closed_loop"),
        "whether the scanner's position sensors were in the feedback loop. Its scale, "
        "creep and drift differ between the two, so a calibration holds only for the one "
        "it was measured in",
        "true or false",
        "no_closed_loop",
    ),
)


@dataclass(frozen=True)
class Conditions:
    """The calibration conditions of a record: values, and what is missing or wrong.

    A missing value is None in `values` and its dotted path is in `missing`;
    an unusable one is None too, and in `invalid` with the reason. Nothing is
    filled in.
    """

    values: dict[str, Any]
    missing: tuple[str, ...]
    invalid: tuple[str, ...]

    def get(self, name: str) -> Any:
        return self.values.get(name)

    def as_dict(self) -> dict[str, Any]:
        return {"values": dict(self.values), "missing": list(self.missing)}


def _empty(value: Any) -> bool:
    return value is None or value == "" or value == {} or value == []


def _check_condition(name: str, value: Any) -> str | None:
    """Why `value` cannot be the condition `name`, or None when it can."""
    if name in ("deposition.mgcl2_mm", "deposition.nicl2_mm"):
        if value == BLINDED:
            return None
        number = _number(value)
        return None if number is not None and number >= 0 else f"not a concentration: {value!r}"
    if name == "scan.angle_deg":
        if isinstance(value, dict):
            bad = [k for k, v in value.items() if not isinstance(k, str) or _number(v) is None]
            return f"not an angle for {bad}" if bad else None
        return None if _number(value) is not None else f"not an angle: {value!r}"
    if name == "scan.direction":
        return None if value in DIRECTIONS else f"not one of {', '.join(DIRECTIONS)}: {value!r}"
    if name == "scan.closed_loop":
        return None if isinstance(value, bool) else f"not true or false: {value!r}"
    return None


def read_conditions(data: dict[str, Any]) -> Conditions:
    """The calibration conditions in an instrument record's data."""
    values: dict[str, Any] = {}
    missing: list[str] = []
    invalid: list[str] = []
    for field in CALIBRATION_CONDITIONS:
        value = _lookup(data, field.path)
        if _empty(value):
            values[field.name] = None
            missing.append(field.name)
            continue
        why = _check_condition(field.name, value)
        if why is not None:
            values[field.name] = None
            invalid.append(f"{field.name}: {why}")
            continue
        number = _number(value)
        values[field.name] = value if number is None else number
    return Conditions(values=values, missing=tuple(missing), invalid=tuple(invalid))


def angle_for(angle: Any, relative: str) -> float | None:
    """The scan angle recorded for a file (its path under during/raw), or None."""
    from fnmatch import fnmatchcase

    if isinstance(angle, dict):
        for pattern, value in angle.items():
            if fnmatchcase(relative, pattern):
                return _number(value)
        return None
    return _number(angle)
