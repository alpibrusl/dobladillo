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
    #: Rendered outlines, when a trajectory or a scan is available for this
    #: part. Empty is the normal case and is not a gap: a part that has never
    #: been simulated has nothing to draw against its design.
    outlines: tuple[Any, ...] = ()
    #: The design's content hash (`dobladillo.provenance`), and the hash the
    #: simulated run drawn on the shape card records, if one is there. A run
    #: of an older design drawn against the current one is the silent failure
    #: this is here to show.
    design_sha256: str = ""
    run_design_sha256: str | None = None
    has_run: bool = False

    @property
    def clean(self) -> bool:
        return self.violations == 0

    @property
    def run_matches(self) -> bool | None:
        """True or False when a run records its design; None when it cannot say."""
        if not self.has_run or self.run_design_sha256 is None:
            return None
        return self.run_design_sha256 == self.design_sha256

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "dimensions_nm": self.dimensions_nm,
            "staples": self.staples,
            "violations": self.violations,
            "clean": self.clean,
            "worst": self.worst,
            "outlines": [o.as_dict() for o in self.outlines],
            "design_sha256": self.design_sha256,
            "run": (
                None
                if not self.has_run
                else {"design_sha256": self.run_design_sha256, "matches": self.run_matches}
            ),
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


def _outlines(name: str, dimensions: dict[str, float], runs_root: Path) -> tuple[Any, ...]:
    """Designed outline always; simulated one when a trajectory is there.

    The designed one alone is worth drawing: it gives the scale that makes the
    others readable, and it costs nothing.
    """
    from dobladillo.dashboard.shapes import from_trajectory, rectangle

    sizes = sorted(dimensions.values(), reverse=True)
    out: list[Any] = [rectangle(sizes[0], sizes[-1])]

    run = runs_root / name
    if not run.is_dir():
        return tuple(out)
    trajectories = sorted(run.glob("traj_*production*.dat"))
    if not trajectories:
        return tuple(out)
    try:
        from dobladillo.analysis.trajectory import read_trajectory

        frames = list(read_trajectory(trajectories[-1]))
        # Drop a tenth as further equilibration, as `analyse` is asked to.
        out.append(from_trajectory(frames, skip=len(frames) // 10))
    except (OSError, ValueError):  # pragma: no cover - a partial run
        pass
    return tuple(out)


def _part_state(name: str, runs_root: Path) -> PartState:
    from dobladillo.parts.bundle import six_helix_bundle
    from dobladillo.parts.hinge import bistable_hinge
    from dobladillo.parts.rectangle import rothemund_rectangle
    from dobladillo.routing.rules import Severity, lint

    builders: dict[str, Callable[[], Any]] = {
        "rectangle": rothemund_rectangle,
        "bundle": six_helix_bundle,
        "hinge": bistable_hinge,
    }
    from dobladillo.provenance import design_sha256

    part = builders[name]()
    info = part.as_dict()
    run_meta = _run_metadata(runs_root / name)
    dimensions = info.get("approx_dimensions_nm") or info["approx_arm_dimensions_nm"]
    hard = [v for v in lint(part.design).violations if v.severity is Severity.VIOLATION]
    sizes = {k: round(float(v), 1) for k, v in dimensions.items()}
    return PartState(
        name=name,
        dimensions_nm=sizes,
        staples=int(info["staple_count"]),
        violations=len(hard),
        worst=hard[0].rule if hard else "",
        outlines=_outlines(name, sizes, runs_root),
        design_sha256=design_sha256(part.design),
        run_design_sha256=(run_meta.get("provenance") or {}).get("design_sha256"),
        has_run=bool(run_meta),
    )


def _run_metadata(run: Path) -> dict[str, Any]:
    """A run directory's metadata.json, or {} when there is no run to speak of."""
    import json

    path = run / "metadata.json"
    if not path.is_file():
        return {}
    try:
        loaded = json.loads(path.read_text())
    except (OSError, ValueError):  # pragma: no cover - a partial write
        return {}
    return loaded if isinstance(loaded, dict) else {}


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
                "provenance": _chain_summary(report.chain),
            }
        )
    return out


def _chain_summary(chain: Any) -> dict[str, Any]:
    """The part of a folder's provenance chain a person reads at a glance."""
    if chain is None:  # pragma: no cover - check() always reads one
        return {"legacy": True, "verified": False, "links": []}
    return {
        "legacy": chain.legacy,
        "verified": chain.verified,
        "design_sha256": chain.predicted_design,
        "order_design_sha256": chain.scan_design,
        "ordered_designs": sorted({o.design_sha256 or "" for o in chain.orders}),
        "scans": len(chain.scans),
        "links": [link.as_dict() for link in chain.links],
    }


def gather(*, experiments_root: Path | None = None, runs_root: Path | None = None) -> State:
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
        parts=[_part_state(name, runs_root or Path("runs")) for name in PARTS],
        folders=_folders(experiments_root or Path("experiments")),
    )
