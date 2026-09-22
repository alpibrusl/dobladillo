"""Outlines: what was designed, what was simulated, what was measured.

The argument for drawing these is a mistake this project made. The six-helix
bundle came back from oxDNA at 328 x 70 x 17.7 nm against a design of
390 x 8, and the table said nothing that read as wrong -- the numbers are all
plausible sizes. It was a 269 nm arc, and it stayed invisible until somebody
asked why the middle extent was 70 nm on an 8 nm rod. An outline shows a
banana immediately.

The reason to be careful is the same one `compare` exists for: the three
outlines are not the same quantity. A designed outline is an idealised
rectangle. A simulated one is the envelope of a thermally fluctuating cloud of
nucleotides. A measured one is a tip-broadened footprint at half height. Drawn
on one axis without saying so, they would show a disagreement that is mostly
tip radius -- exactly the error the comparison machinery refuses to make.

So every outline carries its definition, the renderer labels each, and the
measured one is drawn tip-deconvolved or not drawn at all.

An envelope rather than a convex hull: a hull of a bent rod is a lens, which
hides the bend. Binning along the long axis and taking the transverse extremes
per bin traces the actual centreline, which is what makes a curve visible.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

import numpy as np

Origin = Literal["designed", "simulated", "measured"]

#: Bins along the long axis. Enough to show curvature, few enough that each bin
#: holds sample points at the scale of one frame of a trajectory.
BINS = 32


@dataclass(frozen=True)
class Outline:
    """A closed 2-D outline in nanometres, and what it is an outline of."""

    origin: Origin
    definition: str
    points: tuple[tuple[float, float], ...]

    @property
    def extent_nm(self) -> tuple[float, float]:
        xs = [p[0] for p in self.points]
        ys = [p[1] for p in self.points]
        return (max(xs) - min(xs), max(ys) - min(ys))

    def as_dict(self) -> dict[str, Any]:
        return {
            "origin": self.origin,
            "definition": self.definition,
            "points": [[round(x, 2), round(y, 2)] for x, y in self.points],
        }


def rectangle(length_nm: float, width_nm: float) -> Outline:
    """The designed outline: an idealised box, centred."""
    half_l, half_w = length_nm / 2, width_nm / 2
    return Outline(
        origin="designed",
        definition="base count times rise, as an idealised rectangle",
        points=(
            (-half_l, -half_w),
            (half_l, -half_w),
            (half_l, half_w),
            (-half_l, half_w),
        ),
    )


def envelope(
    positions_nm: np.ndarray, *, origin: Origin, definition: str, bins: int = BINS
) -> Outline:
    """Trace the transverse extremes of a point cloud along its own long axis.

    A convex hull of a bent rod is a lens and hides the bend. This follows the
    object instead: bin along the principal axis, take the highest and lowest
    transverse point in each bin, and join the two runs into a closed loop.
    """
    if positions_nm.ndim != 2 or positions_nm.shape[1] != 3:
        raise ValueError(f"expected an (n, 3) array, got {positions_nm.shape}")
    if len(positions_nm) < bins:
        raise ValueError(f"{len(positions_nm)} points is too few for {bins} bins")

    centred = positions_nm - positions_nm.mean(axis=0)
    _, _, axes = np.linalg.svd(centred, full_matrices=False)
    projected = centred @ axes.T
    along, across = projected[:, 0], projected[:, 1]

    edges = np.linspace(along.min(), along.max(), bins + 1)
    index = np.clip(np.digitize(along, edges) - 1, 0, bins - 1)
    upper: list[tuple[float, float]] = []
    lower: list[tuple[float, float]] = []
    for b in range(bins):
        here = index == b
        if not here.any():
            continue
        centre = float((edges[b] + edges[b + 1]) / 2)
        upper.append((centre, float(across[here].max())))
        lower.append((centre, float(across[here].min())))
    return Outline(origin=origin, definition=definition, points=tuple(upper + lower[::-1]))


def from_trajectory(frames: Any, *, skip: int = 0) -> Outline:
    """The simulated outline, averaged over frames.

    Each frame is superimposed on the first before averaging, so tumbling does
    not smear the shape into a disc -- the object's own frame is the only one
    in which an average shape means anything.
    """
    from dobladillo.analysis.observables import _kabsch

    kept = list(frames)[skip:]
    if not kept:
        raise ValueError("no frames")
    reference = kept[0].positions_nm - kept[0].positions_nm.mean(axis=0)
    stacked = np.zeros_like(reference)
    for frame in kept:
        centred = frame.positions_nm - frame.positions_nm.mean(axis=0)
        stacked += centred @ _kabsch(centred, reference)
    return envelope(
        stacked / len(kept),
        origin="simulated",
        definition=f"envelope of nucleotide positions, mean of {len(kept)} superimposed frames",
    )


def svg(outlines: list[Outline], *, width: int = 420, height: int = 150) -> str:
    """Draw the outlines on one pair of axes, to scale, with a legend.

    Returns an inline SVG using the page's own colour tokens, so it themes with
    everything else rather than carrying its own palette.
    """
    if not outlines:
        return ""
    pad = 8
    xs = [p[0] for o in outlines for p in o.points]
    ys = [p[1] for o in outlines for p in o.points]
    span_x = max(max(xs) - min(xs), 1e-6)
    span_y = max(max(ys) - min(ys), 1e-6)
    scale = min((width - 2 * pad) / span_x, (height - 2 * pad) / span_y)
    mid_x, mid_y = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2

    def place(point: tuple[float, float]) -> str:
        x = width / 2 + (point[0] - mid_x) * scale
        y = height / 2 - (point[1] - mid_y) * scale
        return f"{x:.1f},{y:.1f}"

    styles = {
        "designed": ("var(--faint)", "4 3", "none"),
        "simulated": ("var(--accent)", "none", "var(--accent-soft)"),
        "measured": ("var(--blocked)", "none", "none"),
    }
    shapes, legend = [], []
    for i, outline in enumerate(outlines):
        stroke, dash, fill = styles[outline.origin]
        points = " ".join(place(p) for p in outline.points)
        shapes.append(
            f'<polygon points="{points}" fill="{fill}" fill-opacity="0.35" '
            f'stroke="{stroke}" stroke-width="1.4" stroke-dasharray="{dash}"/>'
        )
        legend.append(
            f'<text x="{pad}" y="{pad + 11 + i * 13}" font-size="9" '
            f'font-family="var(--fm)" fill="{stroke}">{outline.origin}</text>'
        )
    return (
        f'<svg viewBox="0 0 {width} {height}" width="100%" '
        f'style="max-width:{width}px;height:auto" role="img" '
        f'aria-label="designed against simulated outline">'
        f"{''.join(shapes)}{''.join(legend)}</svg>"
    )
