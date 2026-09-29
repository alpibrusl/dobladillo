"""What each `calibrate` command reports, built in one place.

`calibrate lateral|tip|drift` take scan files; `calibrate report` finds the
same scans in an experiment folder. Both call these, so a folder's
`post/calibration.json` holds, per analysis, exactly the payload the
file-level command prints for the same files -- one shape, not two that
could drift apart.

Each function takes images already read, and raises the calibration's own
refusal (`CalibrationRefused`, or `ValueError` for parameters or frames that
cannot be used); the caller decides how to report it.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import numpy as np

    from dobladillo.calibration.lateral import LateralCalibration
    from dobladillo.calibration.reference import ReferenceGeometry
    from dobladillo.calibration.resolution import Noise, Resolution
    from dobladillo.calibration.tip import ApexRadius, TipEstimate
    from dobladillo.imaging.heightmap import HeightMap


def lateral_payload(
    images: Sequence[HeightMap],
    reference: ReferenceGeometry,
    *,
    fit_anisotropy: bool | None = None,
    bootstrap: int,
) -> tuple[dict[str, Any], LateralCalibration]:
    """`calibrate lateral`'s payload (without the file list) and the result."""
    from dobladillo.calibration.lateral import calibrate_lateral

    result, _ = calibrate_lateral(
        images, reference, fit_anisotropy=fit_anisotropy, bootstrap=bootstrap
    )
    return result.as_dict(), result


@dataclass(frozen=True)
class TipResult:
    """`calibrate tip`'s payload, and the pieces its human table is made of."""

    payload: dict[str, Any]
    heights_nm: list[Any]
    estimate: TipEstimate
    radius: ApexRadius
    resolution: Resolution
    noise: Noise
    sigma: float


def tip_payload(
    image: HeightMap,
    *,
    source: str,
    size_px: int,
    threshold_sigma: float | None,
    feature_height_nm: float,
) -> TipResult:
    """Blind tip, apex radius and resolution for one scan. Raises ValueError."""
    from dobladillo.calibration.resolution import lateral_resolution, pixel_noise
    from dobladillo.calibration.tip import THRESHOLD_SIGMA, blind_tip
    from dobladillo.imaging.flatten import flatten

    levelled, _ = flatten(image)
    noise = pixel_noise(levelled.heights_nm)
    sigma = THRESHOLD_SIGMA if threshold_sigma is None else threshold_sigma
    estimate = blind_tip(levelled, size_px, sigma * noise.sigma_nm)
    radius = estimate.apex_radius()
    resolution = lateral_resolution(
        estimate.heights_nm,
        estimate.pixel_nm,
        noise.sigma_nm,
        feature_height_nm=feature_height_nm,
        noise_uncertainty_nm=noise.uncertainty_nm,
    )
    tip = estimate.as_dict()
    heights = tip.pop("heights_nm")
    payload = {
        "scan": source,
        "noise": noise.as_dict(),
        "tip": tip,
        "apex_radius": radius.as_dict(),
        "resolution": resolution.as_dict(),
    }
    return TipResult(payload, heights, estimate, radius, resolution, noise, sigma)


def drift_payload(
    images: Sequence[HeightMap] | Sequence[np.ndarray], times_s: Sequence[float]
) -> dict[str, Any]:
    """`calibrate drift`'s payload (without the file list). Raises ValueError."""
    from dobladillo.calibration.drift import drift

    return drift(images, times_s).as_dict()
