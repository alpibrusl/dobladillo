"""Removing the instrument from the image.

A raw AFM scan is not a picture of the sample. It sits on a tilted plane
because the stage is never level, and each scan line carries its own offset
because the feedback loop drifts between lines. Both are artefacts, both are
far larger than the 2 nm object being measured, and both must go before
anything can be thresholded.

The subtlety worth stating: **the fit must exclude the particles.** Fitting a
plane through an image that contains the structures pulls the plane up towards
them, which then subtracts height from exactly the things being measured. So
the fit is iterated: level, find what stands proud, exclude it, level again.
"""

from __future__ import annotations

import numpy as np

from dobladillo.imaging.heightmap import HeightMap

#: Pixels this many standard deviations above the levelled background are taken
#: to be sample rather than surface, and left out of the next fit.
EXCLUDE_SIGMA = 2.0

#: Iterations of level-and-exclude. Two is enough: the first pass is biased by
#: the particles, the second is fitted to a mask that mostly excludes them, and
#: a third moves the result by less than the noise.
PASSES = 3


def _plane_fit(heights: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Least-squares quadratic surface through the masked background pixels.

    A plane is not enough, and this cost a working pipeline once. A piezo
    scanner bows: the background is parabolic, not flat. A plane fit removes
    tilt exactly and leaves the bow untouched, so a pipeline validated on a
    fixture that only tilts looks perfect and then fails on the first real
    scan -- measured here at 4 nm of bow, 40 placed particles became 4 found,
    all misclassified, with lengths of 71 nm against 190.

    Second order in both axes with a cross term, which is what a piezo
    actually does and what Gwyddion's own background removal offers. Still
    fitted only to the background mask, so particles do not pull the surface
    up around themselves.
    """
    rows, cols = heights.shape
    yy, xx = np.mgrid[0:rows, 0:cols]
    x, y = xx[mask].ravel(), yy[mask].ravel()
    design = np.column_stack([x, y, x * x, y * y, x * y, np.ones(x.size)])
    coefficients, *_ = np.linalg.lstsq(design, heights[mask].ravel(), rcond=None)
    surface: np.ndarray = (
        coefficients[0] * xx
        + coefficients[1] * yy
        + coefficients[2] * xx * xx
        + coefficients[3] * yy * yy
        + coefficients[4] * xx * yy
        + coefficients[5]
    )
    return surface


def _line_level(heights: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Subtract each scan line's own background offset.

    The median of the background pixels in that line, not the mean: a line
    crossing a particle would have its mean dragged upwards even after the
    particle pixels are excluded, because exclusion is never perfect at the
    edges.
    """
    levelled = heights.copy()
    for row in range(heights.shape[0]):
        background = heights[row][mask[row]]
        if background.size >= 8:
            levelled[row] -= np.median(background)
    return levelled


def flatten(image: HeightMap, *, passes: int = PASSES) -> tuple[HeightMap, np.ndarray]:
    """Level the image and return it with the background mask that was used.

    The mask comes back because the next step needs it: what the flattening
    decided was background is exactly what segmentation should call background,
    and deciding it twice with two thresholds invites the two to disagree.
    """
    heights = image.heights_nm
    mask = np.ones_like(heights, dtype=bool)

    for _ in range(passes):
        levelled = heights - _plane_fit(heights, mask)
        levelled = _line_level(levelled, mask)
        background = levelled[mask]
        cut = float(np.median(background) + EXCLUDE_SIGMA * background.std())
        new_mask = levelled < cut
        # Keep a floor of background: a scan crowded with particles could
        # otherwise mask away almost everything and fit to nothing.
        if new_mask.mean() < 0.2:
            break
        mask = new_mask

    return image.with_heights(levelled), mask
