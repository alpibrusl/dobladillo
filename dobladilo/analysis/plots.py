"""Plots for a finished run.

Q5 asks for plots alongside the JSON, and the reason is not decoration: a
dimension that drifts across a trajectory and a dimension that fluctuates
around a mean give the same number and mean different things. Only one of them
is a measurement of an equilibrated object, and the difference is visible in a
line and invisible in a mean.

Rendered headless, so this works over ssh and in CI.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.axes import Axes  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402
import numpy as np  # noqa: E402

from dobladilo.analysis.observables import principal_extents_nm, rmsf_nm  # noqa: E402

if TYPE_CHECKING:
    from collections.abc import Sequence

    from dobladilo.analysis.trajectory import Frame

INK = "#151E1D"
MUTED = "#7A8A87"
ACCENT = "#9C5412"
COOL = "#2C635C"


def _style(ax: Axes) -> None:
    ax.set_facecolor("white")
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(MUTED)
    ax.tick_params(colors=MUTED, labelsize=8)
    ax.xaxis.label.set_color(INK)
    ax.yaxis.label.set_color(INK)
    ax.title.set_color(INK)


def structure_figure(frames: Sequence[Frame], *, title: str) -> Figure:
    """The object seen along its own axes, coloured by how much it moves.

    Two views because one is never enough: along the long axis you see the
    cross-section, across it you see the profile, and a structure that is
    subtly wrong is usually only wrong in one of them.
    """
    fluctuation, mean_structure = rmsf_nm(frames)
    extents, axes = principal_extents_nm(mean_structure)
    projected = (mean_structure - mean_structure.mean(axis=0)) @ axes.T

    fig, (side, cross) = plt.subplots(
        1, 2, figsize=(11, 4.2), gridspec_kw={"width_ratios": [2.4, 1]}
    )
    fig.patch.set_facecolor("white")

    order = np.argsort(fluctuation)
    for ax, (i, j), labels in (
        (side, (0, 1), ("long axis (nm)", "axis 2 (nm)")),
        (cross, (1, 2), ("axis 2 (nm)", "axis 3 (nm)")),
    ):
        dots = ax.scatter(
            projected[order, i],
            projected[order, j],
            c=fluctuation[order],
            s=1.6,
            cmap="copper_r",
            linewidths=0,
        )
        ax.set_xlabel(labels[0], fontsize=9)
        ax.set_ylabel(labels[1], fontsize=9)
        ax.set_aspect("equal", adjustable="datalim")
        _style(ax)

    side.set_title(f"{title}  ·  {extents[0]:.0f} nm long", fontsize=10, loc="left")
    cross.set_title(
        f"cross-section  ·  {extents[1]:.1f} × {extents[2]:.1f} nm", fontsize=10, loc="left"
    )
    bar = fig.colorbar(dots, ax=cross, fraction=0.046, pad=0.08)
    bar.set_label("RMSF (nm)", color=INK, fontsize=8)
    bar.ax.tick_params(colors=MUTED, labelsize=7)
    fig.tight_layout()
    return fig


def convergence_figure(frames: Sequence[Frame], *, title: str) -> Figure:
    """Dimensions and energy against simulation step.

    This is the plot that says whether the run is long enough. A dimension
    still climbing at the last frame has not equilibrated, and its mean is a
    number about the journey rather than the destination.
    """
    steps, longest, middle, shortest, energy = [], [], [], [], []
    for frame in frames:
        extents, _ = principal_extents_nm(frame.positions_nm)
        steps.append(frame.step)
        longest.append(extents[0])
        middle.append(extents[1])
        shortest.append(extents[2])
        energy.append(frame.energy[1])

    fig, (dims, en) = plt.subplots(2, 1, figsize=(8, 5.2), sharex=True)
    fig.patch.set_facecolor("white")

    dims.plot(steps, longest, color=ACCENT, marker="o", ms=3.5, lw=1.4, label="longest")
    twin = dims.twinx()
    twin.plot(steps, middle, color=COOL, marker="s", ms=3, lw=1.2, label="middle")
    twin.plot(steps, shortest, color=MUTED, marker="^", ms=3, lw=1.2, label="shortest")
    dims.set_ylabel("longest (nm)", fontsize=9)
    twin.set_ylabel("other axes (nm)", fontsize=9)
    twin.tick_params(colors=MUTED, labelsize=8)
    dims.set_title(title, fontsize=10, loc="left")
    handles = dims.get_legend_handles_labels()[0] + twin.get_legend_handles_labels()[0]
    labels = ["longest", "middle", "shortest"]
    dims.legend(handles, labels, fontsize=8, frameon=False, loc="center right")
    _style(dims)

    en.plot(steps, energy, color=INK, marker="o", ms=3, lw=1.2)
    en.set_xlabel("simulation step", fontsize=9)
    en.set_ylabel("potential energy\nper nucleotide", fontsize=9)
    _style(en)

    fig.tight_layout()
    return fig


def write_plots(frames: Sequence[Frame], *, directory: Path, title: str) -> dict[str, Path]:
    directory.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}

    structure = directory / "structure.png"
    structure_figure(frames, title=title).savefig(structure, dpi=180, facecolor="white")
    written["structure"] = structure

    if len(frames) > 1:
        convergence = directory / "convergence.png"
        convergence_figure(frames, title=title).savefig(convergence, dpi=180, facecolor="white")
        written["convergence"] = convergence

    plt.close("all")
    return written
