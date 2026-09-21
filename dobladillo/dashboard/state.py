"""Everything the dashboard shows, gathered from the toolchain that owns it.

The artifact this replaced was hand-written, and its own README had to admit
it would go stale. Nothing here is typed twice: construct counts and costs come
from `hamiltonian.experiments`, the tip corrections from `compare.corrections`,
the designed dimensions from the parts themselves, and the lint state by
running the rules. Regenerating is the only way to change the page.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dobladillo import __version__
from dobladillo.compare.corrections import half_height_broadening_nm
from dobladillo.hamiltonian import experiments as series
from dobladillo.programme import EXPERIMENTS, Experiment, critical_path

#: Tip radii and film thicknesses worth tabulating for somebody at a bench.
TIP_RADII_NM = (5.0, 10.0, 20.0)
FILM_THICKNESS_NM = (2.0, 4.0)

#: Parts whose lint state is worth showing. Kept small on purpose: a dashboard
#: that lists everything is a directory listing.
PARTS = ("rectangle", "bundle", "hinge")


@dataclass(frozen=True)
class PartState:
    name: str
    dimensions_nm: dict[str, float]
    staples: int
    violations: int
    worst: str = ""

    @property
    def clean(self) -> bool:
        return self.violations == 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "dimensions_nm": self.dimensions_nm,
            "staples": self.staples,
            "violations": self.violations,
            "clean": self.clean,
            "worst": self.worst,
        }


@dataclass(frozen=True)
class State:
    version: str
    experiments: tuple[Experiment, ...]
    critical_path: tuple[str, ...]
    critical_probability: float
    stages: list[dict[str, Any]]
    programme_cost: dict[str, Any]
    tip_table: list[dict[str, Any]]
    parts: list[PartState]
    folders: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "experiments": [e.as_dict() for e in self.experiments],
            "critical_path": list(self.critical_path),
            "critical_probability": round(self.critical_probability, 4),
            "stages": self.stages,
            "programme_cost": self.programme_cost,
            "tip_table": self.tip_table,
            "parts": [p.as_dict() for p in self.parts],
            "folders": self.folders,
        }


def _part_state(name: str) -> PartState:
    from dobladillo.parts.bundle import six_helix_bundle
    from dobladillo.parts.hinge import bistable_hinge
    from dobladillo.parts.rectangle import rothemund_rectangle
    from dobladillo.routing.rules import Severity, lint

    builders: dict[str, Callable[[], Any]] = {
        "rectangle": rothemund_rectangle,
        "bundle": six_helix_bundle,
        "hinge": bistable_hinge,
    }
    part = builders[name]()
    info = part.as_dict()
    dimensions = info.get("approx_dimensions_nm") or info["approx_arm_dimensions_nm"]
    hard = [v for v in lint(part.design).violations if v.severity is Severity.VIOLATION]
    return PartState(
        name=name,
        dimensions_nm={k: round(float(v), 1) for k, v in dimensions.items()},
        staples=int(info["staple_count"]),
        violations=len(hard),
        worst=hard[0].rule if hard else "",
    )


def _folders(root: Path) -> list[dict[str, Any]]:
    """Experiment folders and how far each has got. Absent root is not an error:
    the dashboard is also generated from a fresh clone."""
    from dobladillo.experiments import check

    if not root.is_dir():
        return []
    out = []
    for directory in sorted(p for p in root.iterdir() if (p / "pre").is_dir()):
        report = check(directory)
        out.append(
            {
                "name": directory.name,
                "ready_for": report.ready_for,
                "believable": report.results_believable,
                "problems": list(report.problems),
                "phases": {p.phase: p.complete for p in report.phases},
            }
        )
    return out


def gather(*, experiments_root: Path | None = None) -> State:
    """Build the whole state. Runs the rules and the cost model; no I/O beyond
    reading experiment folders."""
    chain, probability = critical_path()
    all_series = series.all_series()
    return State(
        version=__version__,
        experiments=EXPERIMENTS,
        critical_path=tuple(e.id for e in chain),
        critical_probability=probability,
        stages=[s.as_dict() for s in all_series],
        programme_cost=series.programme_cost_eur(all_series),
        tip_table=[
            {
                "radius_nm": radius,
                "widening_nm": {
                    h: round(
                        2 * half_height_broadening_nm(tip_radius_nm=radius, feature_height_nm=h), 1
                    )
                    for h in FILM_THICKNESS_NM
                },
            }
            for radius in TIP_RADII_NM
        ],
        parts=[_part_state(name) for name in PARTS],
        folders=_folders(experiments_root or Path("experiments")),
    )
