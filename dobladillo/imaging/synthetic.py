"""Images whose contents we chose, for testing measurement code.

There are no real AFM images yet, and there will not be until somebody spends
an afternoon at a microscope. Waiting for them to write the analysis would mean
writing it against no feedback at all, and then debugging it on the one
irreplaceable dataset.

So: render rectangles of known size, at known angles, in known numbers, with
the defects a real scan has -- tilted background, line noise, scanner drift,
a few aggregates. If the pipeline cannot recover what was put in, it will not
recover what it was not told.

This is a test instrument, not a simulator. It makes no claim about what real
origami look like; it makes images with a known answer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from dobladillo.imaging.heightmap import HeightMap

#: A single-layer origami sheet stands about this tall, dried on mica.
SHEET_HEIGHT_NM = 2.0


@dataclass(frozen=True)
class PlacedParticle:
    """What was put into the image, so it can be compared with what came out."""

    centre_px: tuple[float, float]
    length_nm: float
    width_nm: float
    height_nm: float
    angle_deg: float
    kind: str  # "rectangle" | "aggregate"

    def as_dict(self) -> dict[str, Any]:
        return {
            "centre_px": [round(v, 1) for v in self.centre_px],
            "length_nm": round(self.length_nm, 1),
            "width_nm": round(self.width_nm, 1),
            "height_nm": round(self.height_nm, 2),
            "angle_deg": round(self.angle_deg, 1),
            "kind": self.kind,
        }


@dataclass(frozen=True)
class SyntheticScan:
    image: HeightMap
    truth: tuple[PlacedParticle, ...] = field(default_factory=tuple)

    @property
    def rectangles(self) -> tuple[PlacedParticle, ...]:
        return tuple(p for p in self.truth if p.kind == "rectangle")


def _stamp_rectangle(
    heights: np.ndarray,
    *,
    centre: tuple[float, float],
    length_px: float,
    width_px: float,
    height_nm: float,
    angle_deg: float,
    pixel_nm: float,
    tip_radius_nm: float,
) -> None:
    """Draw one rotated rectangle as a finite tip would record it.

    The edge profile is the real one rather than a softening. A rigid sphere of
    radius R riding the top corner of a plateau of height h has its apex at

        z(x) = h - R + sqrt(R^2 - x^2)

    for x measured outward from the true edge, reaching the substrate at
    x = sqrt(2Rh - h^2). So the recorded feature is full height AT the true
    edge and the whole ramp lies OUTSIDE it.

    This replaced a symmetric ramp centred on the true edge, which put the
    half-height contour exactly on the true edge -- that is, modelled a tip
    with zero half-height broadening. The real contour sits
    sqrt(Rh - h^2/4) outside: 4.36 nm for a 10 nm tip on a 2 nm plate, which
    is 24% of a 36 nm width. The closed loop found it, by deconvolving a tip
    artefact that was never rendered and coming back short by exactly the
    amount removed.

    A product of two one-dimensional profiles is not the same as the
    morphological dilation a real tip performs, and at the corners it is
    wrong. It is right along each edge, which is where a half-height width is
    measured, and that is what this fixture is for.
    """
    rows, cols = heights.shape
    yy, xx = np.mgrid[0:rows, 0:cols]
    angle = np.deg2rad(angle_deg)
    dy, dx = yy - centre[0], xx - centre[1]
    along = dx * np.cos(angle) + dy * np.sin(angle)
    across = -dx * np.sin(angle) + dy * np.cos(angle)

    def profile(distance: np.ndarray, half_px: float) -> np.ndarray:
        """Fraction of full height recorded this far from the centre.

        Everything here is in nanometres: the tip radius and the feature
        height are, and mixing them with a pixel distance is the obvious way
        to get a fixture that is subtly wrong at one scan size and right at
        another.
        """
        outside_nm = (np.abs(distance) - half_px) * pixel_nm
        if tip_radius_nm <= 0:
            return (outside_nm <= 0).astype(float)
        x = np.clip(outside_nm, 0.0, tip_radius_nm)
        z = height_nm - tip_radius_nm + np.sqrt(np.maximum(tip_radius_nm**2 - x**2, 0.0))
        return np.clip(np.where(outside_nm <= 0, height_nm, z) / height_nm, 0.0, 1.0)

    heights += height_nm * profile(along, length_px / 2) * profile(across, width_px / 2)


def synthetic_scan(
    *,
    size_px: int = 512,
    scan_nm: float = 2000.0,
    n_rectangles: int = 40,
    length_nm: float = 191.0,
    width_nm: float = 36.0,
    height_nm: float = SHEET_HEIGHT_NM,
    n_aggregates: int = 4,
    tip_radius_nm: float = 10.0,
    noise_nm: float = 0.12,
    tilt_nm: float = 6.0,
    line_noise_nm: float = 0.25,
    bow_nm: float = 0.0,
    drift_shear: float = 0.0,
    streak_lines: int = 0,
    seed: int = 0,
) -> SyntheticScan:
    """One scan, with the defects that make a real one hard.

    The tilt and line noise are not decoration. A raw AFM scan sits on a tilted
    plane because the sample is never level, and each scan line has its own
    offset because the feedback loop drifts. Flattening is the step that
    removes them, and a test image without them would let a pipeline that
    cannot flatten still pass.
    """
    rng = np.random.default_rng(seed)
    pixel_nm = scan_nm / size_px
    heights = np.zeros((size_px, size_px))
    placed: list[PlacedParticle] = []

    def free_spot(footprint_px: float) -> tuple[float, float] | None:
        for _ in range(200):
            centre = (
                float(rng.uniform(footprint_px, size_px - footprint_px)),
                float(rng.uniform(footprint_px, size_px - footprint_px)),
            )
            if all(
                np.hypot(centre[0] - p.centre_px[0], centre[1] - p.centre_px[1]) > footprint_px
                for p in placed
            ):
                return centre
        return None

    length_px, width_px = length_nm / pixel_nm, width_nm / pixel_nm

    # Keep centres more than a full length apart, so two rectangles cannot
    # overlap whatever their angles. With a smaller margin they sometimes
    # merge, the pipeline correctly reports one particle, and the truth still
    # claims two -- which reads as a measurement error and is not one. Crowding
    # is worth testing, but as its own scenario rather than as noise in this
    # one.
    for _ in range(n_rectangles):
        centre = free_spot(length_px * 1.1)
        if centre is None:
            break
        angle = float(rng.uniform(0, 180))
        _stamp_rectangle(
            heights,
            centre=centre,
            length_px=length_px,
            width_px=width_px,
            height_nm=height_nm,
            angle_deg=angle,
            pixel_nm=pixel_nm,
            tip_radius_nm=tip_radius_nm,
        )
        placed.append(PlacedParticle(centre, length_nm, width_nm, height_nm, angle, "rectangle"))

    for _ in range(n_aggregates):
        centre = free_spot(length_px * 0.9)
        if centre is None:
            break
        # A clump: several overlapping blobs, taller and rounder than a sheet.
        for _ in range(rng.integers(3, 6)):
            offset = rng.normal(0, width_px * 0.6, 2)
            _stamp_rectangle(
                heights,
                centre=(centre[0] + offset[0], centre[1] + offset[1]),
                length_px=width_px * 1.4,
                width_px=width_px * 1.2,
                height_nm=height_nm * float(rng.uniform(1.8, 3.0)),
                angle_deg=float(rng.uniform(0, 180)),
                pixel_nm=pixel_nm,
                tip_radius_nm=tip_radius_nm,
            )
        placed.append(
            PlacedParticle(
                centre, width_nm * 1.8, width_nm * 1.6, height_nm * 2.4, 0.0, "aggregate"
            )
        )

    # The defects, added after the structures so they sit under everything.
    yy, xx = np.mgrid[0:size_px, 0:size_px]
    # Thermal drift shears the slow axis: a particle imaged over several
    # minutes is measured while the sample moves under the tip, so it comes out
    # skewed. Applied to the placed geometry rather than added afterwards,
    # because a shear is a coordinate change and not a height offset.
    if drift_shear:
        shift = (drift_shear * yy).astype(int)
        rows = np.arange(size_px)[:, None]
        heights = heights[rows, np.clip(xx + shift, 0, size_px - 1)]

    heights = heights + tilt_nm * (xx / size_px) + 0.6 * tilt_nm * (yy / size_px)

    # Scanner bow. The reason it is worth modelling separately from tilt: a
    # plane fit removes tilt exactly and leaves bow untouched, so a pipeline
    # that only plane-fits looks fine on a tilted fixture and fails on a real
    # scan. Parabolic in both axes, as a piezo actually bends.
    if bow_nm:
        u = 2 * xx / size_px - 1
        v = 2 * yy / size_px - 1
        heights = heights + bow_nm * (u**2 + 0.7 * v**2)

    heights = heights + rng.normal(0, line_noise_nm, (size_px, 1))  # per-line offset

    # The tip picks something up and drags it for a few lines. Real, common,
    # and the thing most likely to be mistaken for a row of particles.
    if streak_lines:
        first = int(rng.integers(0, max(1, size_px - streak_lines)))
        band = slice(first, first + streak_lines)
        heights[band, :] = heights[band, :] + height_nm * rng.uniform(0.6, 1.4)

    heights = heights + rng.normal(0, noise_nm, heights.shape)

    return SyntheticScan(
        image=HeightMap(heights_nm=heights, pixel_nm=pixel_nm, source="synthetic"),
        truth=tuple(placed),
    )
