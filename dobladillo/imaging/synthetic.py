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
from typing import Any, Final

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
    kind: str  # "rectangle" | "twisted" | "aggregate", or an ASSEMBLY_KINDS key

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


def _stamp_twisted(
    heights: np.ndarray,
    *,
    centre: tuple[float, float],
    length_px: float,
    width_px: float,
    height_nm: float,
    angle_deg: float,
    pixel_nm: float,
    tip_radius_nm: float,
    ridge_nm: float,
) -> None:
    """A sheet that did not lie flat: a rectangle with a ridge along it.

    What the twist experiment is actually looking for. A twisted rectangle
    adsorbed on mica is not a rectangle standing on edge -- the surface
    flattens what it adsorbs -- it is a sheet pressed down with a fold or roll
    left in it. So the footprint stays about right and the HEIGHT stops being
    uniform, which is why `roughness_nm` and not a dimension is the measure
    that separates them.

    The ridge runs along the long axis and is raised by `ridge_nm` over the
    plate, a half-cosine across the short one, so the particle keeps its
    outline and gains a spine.
    """
    rows, cols = heights.shape
    yy, xx = np.mgrid[0:rows, 0:cols]
    angle = np.deg2rad(angle_deg)
    dy, dx = yy - centre[0], xx - centre[1]
    across = -dx * np.sin(angle) + dy * np.cos(angle)

    before = heights.copy()
    _stamp_rectangle(
        heights,
        centre=centre,
        length_px=length_px,
        width_px=width_px,
        height_nm=height_nm,
        angle_deg=angle_deg,
        pixel_nm=pixel_nm,
        tip_radius_nm=tip_radius_nm,
    )
    added = heights - before
    inside = added > 0.5 * height_nm
    half = max(width_px / 2, 1e-6)
    ridge = ridge_nm * np.cos(np.clip(across / half, -1, 1) * np.pi / 2) ** 2
    heights[inside] += ridge[inside]


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


def _add_defects(
    heights: np.ndarray,
    rng: np.random.Generator,
    *,
    height_nm: float,
    tilt_nm: float,
    bow_nm: float,
    line_noise_nm: float,
    noise_nm: float,
    drift_shear: float,
    streak_lines: int,
) -> np.ndarray:
    """What a real scan does to the surface: drift, tilt, bow, lines, noise.

    Shared by every synthetic scan, and drawing from `rng` in one fixed order,
    so a scan made with a given seed is the same whichever function placed
    its particles.
    """
    size_px = heights.shape[0]
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

    return heights


def synthetic_scan(
    *,
    size_px: int = 512,
    scan_nm: float = 2000.0,
    n_rectangles: int = 40,
    length_nm: float = 191.0,
    width_nm: float = 36.0,
    height_nm: float = SHEET_HEIGHT_NM,
    n_aggregates: int = 4,
    n_twisted: int = 0,
    twist_ridge_nm: float = 1.2,
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

    for _ in range(n_twisted):
        centre = free_spot(length_px * 1.1)
        if centre is None:
            break
        angle = float(rng.uniform(0, 180))
        _stamp_twisted(
            heights,
            centre=centre,
            length_px=length_px,
            width_px=width_px,
            height_nm=height_nm,
            angle_deg=angle,
            pixel_nm=pixel_nm,
            tip_radius_nm=tip_radius_nm,
            ridge_nm=twist_ridge_nm,
        )
        placed.append(
            PlacedParticle(
                centre_px=centre,
                length_nm=length_nm,
                width_nm=width_nm,
                height_nm=height_nm + twist_ridge_nm,
                angle_deg=angle,
                kind="twisted",
            )
        )

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

    heights = _add_defects(
        heights,
        rng,
        height_nm=height_nm,
        tilt_nm=tilt_nm,
        bow_nm=bow_nm,
        line_noise_nm=line_noise_nm,
        noise_nm=noise_nm,
        drift_shear=drift_shear,
        streak_lines=streak_lines,
    )

    return SyntheticScan(
        image=HeightMap(heights_nm=heights, pixel_nm=pixel_nm, source="synthetic"),
        truth=tuple(placed),
    )


def _stamp_units(
    heights: np.ndarray,
    *,
    centres: list[tuple[float, float]],
    length_px: float,
    width_px: float,
    height_nm: float,
    angle_deg: float,
    pixel_nm: float,
    tip_radius_nm: float,
) -> None:
    """Several rectangles that touch, recorded as ONE tip would record them.

    Stamping each one additively would double the height wherever two tip
    ramps overlap -- in the few nanometres between two joined rectangles --
    and invent a ridge no instrument records. A tip rides the higher of the
    two surfaces, so the units are combined by their maximum.
    """
    combined = np.zeros_like(heights)
    for centre in centres:
        unit = np.zeros_like(heights)
        _stamp_rectangle(
            unit,
            centre=centre,
            length_px=length_px,
            width_px=width_px,
            height_nm=height_nm,
            angle_deg=angle_deg,
            pixel_nm=pixel_nm,
            tip_radius_nm=tip_radius_nm,
        )
        np.maximum(combined, unit, out=combined)
    heights += combined


#: The kinds `synthetic_assembly_scan` places, and how many rectangles each is.
ASSEMBLY_KINDS: Final = {
    "monomer": 1,
    "dimer": 2,
    "touching_end": 2,
    "side_by_side": 2,
    "aggregate": 0,
}


def synthetic_assembly_scan(
    *,
    monomers: int = 20,
    dimers: int = 10,
    touching_end: int = 0,
    side_by_side: int = 0,
    aggregates: int = 0,
    length_nm: float = 106.2,
    width_nm: float = 66.0,
    gap_nm: float = 4.0,
    height_nm: float = SHEET_HEIGHT_NM,
    size_px: int = 512,
    scan_nm: float = 2000.0,
    tip_radius_nm: float = 10.0,
    noise_nm: float = 0.12,
    tilt_nm: float = 6.0,
    line_noise_nm: float = 0.25,
    bow_nm: float = 0.0,
    drift_shear: float = 0.0,
    streak_lines: int = 0,
    seed: int = 0,
) -> SyntheticScan:
    """A scan of monomers and dimers in known numbers, for E9's analysis.

    Four kinds of particle besides aggregates, and two of them are traps:

    - `monomer`: one rectangle.
    - `dimer`: two rectangles in line, `gap_nm` apart -- the sticky-end bridge.
    - `touching_end`: two rectangles in line with no gap and no bond, as two
      monomers that happened to land end to end. By footprint this IS a
      dimer; it is here so a test can show that, rather than hope otherwise.
    - `side_by_side`: two rectangles touching along their long edges.

    Placement keeps every particle clear of every other, so what was placed is
    what should be found. `truth` records each particle's kind.
    """
    rng = np.random.default_rng(seed)
    pixel_nm = scan_nm / size_px
    heights = np.zeros((size_px, size_px))
    placed: list[PlacedParticle] = []
    length_px, width_px, gap_px = length_nm / pixel_nm, width_nm / pixel_nm, gap_nm / pixel_nm
    reach: list[tuple[tuple[float, float], float]] = []

    def free_spot(radius_px: float) -> tuple[float, float] | None:
        for _ in range(400):
            centre = (
                float(rng.uniform(radius_px, size_px - radius_px)),
                float(rng.uniform(radius_px, size_px - radius_px)),
            )
            if all(
                np.hypot(centre[0] - c[0], centre[1] - c[1]) > radius_px + r + 4 for c, r in reach
            ):
                return centre
        return None

    plan = (
        ["dimer"] * dimers
        + ["touching_end"] * touching_end
        + ["side_by_side"] * side_by_side
        + ["monomer"] * monomers
    )
    for kind in plan:
        if kind == "monomer":
            extent_px = np.hypot(length_px, width_px) / 2
        elif kind == "side_by_side":
            extent_px = np.hypot(length_px, 2 * width_px) / 2
        else:
            extent_px = np.hypot(2 * length_px + gap_px, width_px) / 2
        # A tip's ramp reaches a few nm past the edge; keep it off neighbours.
        radius = extent_px + 3 * tip_radius_nm / pixel_nm
        centre = free_spot(radius)
        if centre is None:
            break
        reach.append((centre, radius))
        angle = float(rng.uniform(0, 180))
        theta = np.deg2rad(angle)
        along = np.array([np.sin(theta), np.cos(theta)])  # (row, col)
        across = np.array([np.cos(theta), -np.sin(theta)])
        c = np.array(centre)
        if kind == "monomer":
            centres = [centre]
            shape = (length_nm, width_nm)
        elif kind == "side_by_side":
            half = width_px / 2
            centres = [tuple(c + half * across), tuple(c - half * across)]
            shape = (length_nm, 2 * width_nm)
        else:
            separation = length_px + (gap_px if kind == "dimer" else 0.0)
            half = separation / 2
            centres = [tuple(c + half * along), tuple(c - half * along)]
            shape = (2 * length_nm + (gap_nm if kind == "dimer" else 0.0), width_nm)
        _stamp_units(
            heights,
            centres=[(float(x), float(y)) for x, y in centres],
            length_px=length_px,
            width_px=width_px,
            height_nm=height_nm,
            angle_deg=angle,
            pixel_nm=pixel_nm,
            tip_radius_nm=tip_radius_nm,
        )
        placed.append(PlacedParticle(centre, shape[0], shape[1], height_nm, angle, kind))

    for _ in range(aggregates):
        radius = 2.5 * width_px + 3 * tip_radius_nm / pixel_nm
        centre = free_spot(radius)
        if centre is None:
            break
        reach.append((centre, radius))
        # The clump `synthetic_scan` draws, so both fixtures mean one thing.
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

    heights = _add_defects(
        heights,
        rng,
        height_nm=height_nm,
        tilt_nm=tilt_nm,
        bow_nm=bow_nm,
        line_noise_nm=line_noise_nm,
        noise_nm=noise_nm,
        drift_shear=drift_shear,
        streak_lines=streak_lines,
    )
    return SyntheticScan(
        image=HeightMap(heights_nm=heights, pixel_nm=pixel_nm, source="synthetic"),
        truth=tuple(placed),
    )
