"""Measured against nominal: the tip-radius rule, enforced at the type boundary.

The rule -- no defaults for measured quantities, refuse rather than substitute
-- used to live in each command. These tests pin it where it lives now: in
the types, statically for type-checked code and at run time for everything
else, and at the one place `during/instrument.json` is read.
"""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from dobladillo.compare import (
    NOMINAL_TIP_RADIUS,
    Conditions,
    Observation,
    deconvolve_tip,
)
from dobladillo.experiments import scaffold
from dobladillo.experiments.arms import measure_arm
from dobladillo.experiments.instrument import read_instrument
from dobladillo.readings import (
    Measured,
    Nominal,
    NotMeasured,
    When,
    combine,
    require_measured,
)

ROOT = Path(__file__).resolve().parent.parent
AFM = Conditions(temperature_c=23.0, magnesium_m=0.012, model="AFM")


def _tip(radius_nm: float, *, uncertainty: float | None = None) -> Measured[float]:
    return Measured(
        value=radius_nm,
        quantity="tip_radius",
        source="test fixture",
        at=When(timestamp=0.0, basis="stated"),
        instrument="test",
        uncertainty=uncertainty,
    )


def _width(value: float = 44.0) -> Observation:
    return Observation("width_nm", value, "afm_half_height", "measured", AFM, 3.0, 40)


# ----------------------------------------------------------------- run time


def test_deconvolve_tip_rejects_the_nominal_radius_at_run_time() -> None:
    """The case the issue exists for: an agent passing what the box says."""
    with pytest.raises(NotMeasured, match="NOMINAL") as caught:
        deconvolve_tip(_width(), feature_height_nm=2.0, tip_radius_nm=NOMINAL_TIP_RADIUS)  # type: ignore[arg-type]
    assert caught.value.kind == "not_measured"
    assert "8-20 nm" in str(caught.value)


def test_deconvolve_tip_rejects_a_bare_number() -> None:
    """A float carries no evidence it was measured, so it is refused too --
    otherwise the nominal value just arrives unwrapped."""
    with pytest.raises(NotMeasured, match="bare number"):
        deconvolve_tip(_width(), feature_height_nm=2.0, tip_radius_nm=10.0)  # type: ignore[arg-type]


def test_deconvolve_tip_has_no_default_radius() -> None:
    with pytest.raises(TypeError, match="tip_radius_nm"):
        deconvolve_tip(_width(), feature_height_nm=2.0)  # type: ignore[call-arg]


def test_a_measured_radius_is_accepted_and_travels_with_the_result() -> None:
    """Control for the three refusals above: the same call with a Measured
    goes through, and the result says where its radius came from."""
    fixed = deconvolve_tip(_width(), feature_height_nm=2.0, tip_radius_nm=_tip(10.0))
    assert fixed.observation.value_nm == pytest.approx(44.0 - 2 * 19**0.5)
    assert fixed.as_dict()["tip_radius"]["source"] == "test fixture"
    assert fixed.as_dict()["tip_radius"]["kind"] == "measured"


def test_a_measurement_of_the_wrong_quantity_is_refused() -> None:
    magnesium = Measured(
        value=12.0, quantity="magnesium", source="t", at=When(timestamp=0.0, basis="stated")
    )
    with pytest.raises(NotMeasured, match="measured magnesium"):
        deconvolve_tip(_width(), feature_height_nm=2.0, tip_radius_nm=magnesium)


def test_measure_arm_rejects_the_nominal_radius_before_reading_any_scan() -> None:
    """compare-arms' measurement is public too, and refuses the same way --
    before touching the (here nonexistent) scans."""
    with pytest.raises(NotMeasured):
        measure_arm(
            [Path("nonexistent.gsf")],
            tip_radius=NOMINAL_TIP_RADIUS,  # type: ignore[arg-type]
            reference_height_nm=2.0,
            length_nm=191.2,
            width_nm=36.0,
        )


def test_a_blunting_tip_widens_the_uncertainty_beyond_the_floor() -> None:
    """A tip that went from 10 to 16 nm is known to 60%, not the 40% floor."""
    steady = deconvolve_tip(_width(), feature_height_nm=2.0, tip_radius_nm=_tip(13.0))
    blunted = deconvolve_tip(
        _width(), feature_height_nm=2.0, tip_radius_nm=_tip(13.0, uncertainty=7.8)
    )
    assert blunted.observation.value_nm == pytest.approx(steady.observation.value_nm)
    assert blunted.observation.uncertainty_nm > steady.observation.uncertainty_nm  # type: ignore[operator]


def test_there_is_no_way_to_turn_a_nominal_into_a_measurement() -> None:
    assert not issubclass(Nominal, Measured)
    assert not issubclass(Measured, Nominal)
    assert not any(name.startswith(("as_measured", "to_measured")) for name in dir(Nominal))


def test_a_reading_must_be_a_number_with_a_source() -> None:
    with pytest.raises(ValueError, match="positive"):
        _tip(0.0)
    with pytest.raises(TypeError):
        _tip("10")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="where it was read from"):
        Measured(value=10.0, quantity="tip_radius", source="", at=When.now())
    with pytest.raises(ValueError, match="non-negative"):
        _tip(10.0, uncertainty=-1.0)


def test_combine_carries_the_spread_and_refuses_a_nominal() -> None:
    both = combine([_tip(10.0), _tip(14.0)], "tip_radius", source="mean")
    assert both.value == pytest.approx(12.0)
    assert both.uncertainty == pytest.approx(4.0)
    assert combine([_tip(10.0)], "tip_radius", source="one").uncertainty is None
    with pytest.raises(NotMeasured):
        combine([_tip(10.0), NOMINAL_TIP_RADIUS], "tip_radius", source="mixed")  # type: ignore[list-item]


def test_require_measured_passes_a_measurement_through() -> None:
    tip = _tip(11.0)
    assert require_measured(tip, "tip_radius", parameter="p") is tip


# -------------------------------------------------------------- statically


def test_mypy_rejects_a_nominal_or_a_float_where_a_measurement_is_required(
    tmp_path: Path,
) -> None:
    """The static half. The same calls are type-checked as the package is, and
    both wrong ones fail -- while the right one, in the same run, does not, so
    this cannot pass merely because mypy failed to import anything."""
    pytest.importorskip("mypy")
    snippet = tmp_path / "boundary.py"
    snippet.write_text(
        textwrap.dedent(
            """\
            from dobladillo.compare import (
                NOMINAL_TIP_RADIUS, Conditions, Observation, deconvolve_tip,
            )
            from dobladillo.readings import Measured, When

            obs = Observation(
                "width_nm", 44.0, "afm_half_height", "measured", Conditions(magnesium_m=0.012)
            )
            tip: Measured[float] = Measured(
                value=10.0, quantity="tip_radius", source="s", at=When.now()
            )
            deconvolve_tip(obs, feature_height_nm=2.0, tip_radius_nm=tip)
            deconvolve_tip(obs, feature_height_nm=2.0, tip_radius_nm=NOMINAL_TIP_RADIUS)
            deconvolve_tip(obs, feature_height_nm=2.0, tip_radius_nm=10.0)
            """
        )
    )
    run = subprocess.run(
        [
            sys.executable,
            "-m",
            "mypy",
            "--config-file",
            str(ROOT / "pyproject.toml"),
            "--cache-dir",
            str(tmp_path / "cache"),
            str(snippet),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    errors = [line for line in run.stdout.splitlines() if ": error:" in line]
    lines = sorted(int(line.split(":")[1]) for line in errors)
    assert lines == [13, 14], run.stdout
    assert '"Nominal[float]"; expected "Measured[float]"' in run.stdout
    assert '"float"; expected "Measured[float]"' in run.stdout


# ------------------------------------------------------------ the boundary


def _folder(tmp: Path, **fields: object) -> Path:
    directory = scaffold(
        tmp,
        slug="x",
        prediction={"part": "rectangle", "predicted_nm": {"length": 106.2, "width": 66.0}},
        plan="# p\n",
        protocol="# p\n",
    )
    path = directory / "during" / "instrument.json"
    record = json.loads(path.read_text())
    for dotted, value in fields.items():
        *parents, leaf = dotted.split("__")
        node = record
        for key in parents:
            node = node[key]
        node[leaf] = value
    path.write_text(json.dumps(record))
    return directory


def test_the_boundary_types_each_reading_by_its_field(tmp_path: Path) -> None:
    directory = _folder(
        tmp_path,
        instrument="Bruker Multimode 8",
        tip__nominal_radius_nm=10.0,
        tip__measured_radius_before_nm=12.5,
        buffer__mgcl2_mm=12.5,
        temperature_c=23.0,
    )
    record = read_instrument(directory)
    assert record is not None
    before = record.tip["before"]
    assert isinstance(before, Measured) and before.value == 12.5
    assert before.instrument == "Bruker Multimode 8"
    assert before.source == "during/instrument.json: tip.measured_radius_before_nm"
    assert before.at.basis == "filesystem", "an untracked file's time is not evidence"
    assert record.tip["after"] is None, "an empty field is absent, not zero"
    assert isinstance(record.tip_nominal, Nominal) and record.tip_nominal.value == 10.0
    assert record.magnesium is not None and record.magnesium.unit == "mM"
    assert record.temperature is not None and record.temperature.value == 23.0


def test_a_nominal_field_never_becomes_a_measured_one(tmp_path: Path) -> None:
    """The template's nominal field filled, the measured ones empty: the
    boundary must not promote the one to the other."""
    directory = _folder(tmp_path, tip__nominal_radius_nm=10.0)
    record = read_instrument(directory)
    assert record is not None
    assert all(value is None for value in record.tip.values())


def test_an_impossible_reading_is_an_error_not_an_absence(tmp_path: Path) -> None:
    directory = _folder(tmp_path, tip__measured_radius_before_nm=-3.0)
    with pytest.raises(ValueError, match="positive"):
        read_instrument(directory)


def _cli(*args: str):  # type: ignore[no-untyped-def]
    from typer.testing import CliRunner

    from dobladillo.cli import app

    return CliRunner().invoke(app, list(args))


def test_report_refuses_when_only_the_nominal_radius_is_recorded(tmp_path: Path) -> None:
    directory = _folder(tmp_path, tip__nominal_radius_nm=10.0)
    (directory / "during" / "raw" / "s.gsf").write_text("not really")
    result = _cli("experiment", "report", str(directory), "--json")
    assert result.exit_code != 0
    assert json.loads(result.stdout)["error"]["kind"] == "no_tip_radius"


def test_report_refuses_an_impossible_reading_with_a_structured_error(tmp_path: Path) -> None:
    directory = _folder(tmp_path, tip__measured_radius_before_nm=0)
    result = _cli("experiment", "report", str(directory), "--json")
    assert result.exit_code != 0
    assert json.loads(result.stdout)["error"]["kind"] == "invalid_reading"


def test_compare_arms_refuses_when_only_the_nominal_radius_is_recorded(tmp_path: Path) -> None:
    directory = _folder(
        tmp_path,
        tip__nominal_radius_nm=10.0,
        imaging_order=["X", "Y"],
        reference={"flat_height_nm": 2.0},
    )
    result = _cli("experiment", "compare-arms", str(directory), "--json")
    assert result.exit_code != 0
    assert json.loads(result.stdout)["error"]["kind"] == "no_tip_radius"
