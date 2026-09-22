"""The AFM pipeline is validated on images whose contents we chose.

There are no real AFM images yet and there will not be until somebody spends an
afternoon at a microscope. Writing the analysis against nothing and then
debugging it on that one irreplaceable dataset is the failure mode these tests
exist to avoid.

The synthetic instrument is not a simulator and makes no claim about what real
origami look like. It makes images with a known answer, including the defects
that make a real scan hard: a tilted plane, per-line offsets, noise, and a few
aggregates.
"""

from __future__ import annotations

import numpy as np
import pytest

from dobladillo.compare.corrections import half_height_broadening_nm
from dobladillo.imaging.classify import Fraction, classify, population
from dobladillo.imaging.flatten import flatten
from dobladillo.imaging.heightmap import HeightMap
from dobladillo.imaging.particles import find_particles
from dobladillo.imaging.synthetic import SHEET_HEIGHT_NM, synthetic_scan

TRUE_LENGTH_NM = 191.0
TRUE_WIDTH_NM = 36.0

#: The fixture now renders a finite tip, because a real scan is taken with one.
#: A raw half-height measurement therefore recovers the truth PLUS the
#: broadening, and only the deconvolved one recovers the truth. Both are
#: checked below: the first says the measurement is faithful to the image, the
#: second says the correction is faithful to the object.
FIXTURE_TIP_RADIUS_NM = 10.0
BROADENING_NM = 2 * half_height_broadening_nm(
    tip_radius_nm=FIXTURE_TIP_RADIUS_NM, feature_height_nm=SHEET_HEIGHT_NM
)


def _pipeline(seed: int, **kwargs):
    scan = synthetic_scan(seed=seed, n_rectangles=25, **kwargs)
    flat, background = flatten(scan.image)
    return scan, flat, background, find_particles(flat, background)


# ---------------------------------------------------------------- heightmap


def test_a_height_map_insists_on_being_an_image() -> None:
    with pytest.raises(ValueError, match="2D"):
        HeightMap(heights_nm=np.zeros(10), pixel_nm=1.0)
    with pytest.raises(ValueError, match="positive"):
        HeightMap(heights_nm=np.zeros((4, 4)), pixel_nm=0.0)


# ----------------------------------------------------------------- flatten


def test_flattening_removes_tilt_and_line_offsets() -> None:
    scan = synthetic_scan(seed=1, n_rectangles=0, n_aggregates=0, tilt_nm=8.0, line_noise_nm=0.4)
    assert np.ptp(scan.image.heights_nm) > 8.0  # ndarray.ptp() went in numpy 2
    flat, background = flatten(scan.image)
    assert abs(float(np.median(flat.heights_nm[background]))) < 0.05
    assert flat.heights_nm[background].std() < 0.2


def test_the_fit_excludes_the_particles() -> None:
    """The subtle one. A plane fitted through an image containing structures is
    pulled up towards them, and then subtracts height from exactly the things
    being measured. With 25 particles present the background must still come
    out at zero, and the sheets must still be their true height."""
    _, flat, background, particles = _pipeline(2)
    assert abs(float(np.median(flat.heights_nm[background]))) < 0.05
    heights = [p.height_nm for p in particles if p.aspect > 3]
    assert np.mean(heights) == pytest.approx(SHEET_HEIGHT_NM, rel=0.1)


# --------------------------------------------------------------- measuring


@pytest.mark.parametrize("seed", [1, 2, 3, 4, 5])
def test_dimensions_agree_with_the_truth_within_five_percent(seed: int) -> None:
    """M4's acceptance criterion, against a known answer rather than a manual
    measurement, since there is nothing yet to measure manually."""
    _, _, _, particles = _pipeline(seed)
    sheets = [p for p in particles if not p.touches_edge and 3 < p.aspect < 9]
    assert len(sheets) >= 15

    # What the image contains: the object, widened by the tip that recorded it.
    assert np.mean([p.length_nm for p in sheets]) == pytest.approx(
        TRUE_LENGTH_NM + BROADENING_NM, rel=0.05
    )
    assert np.mean([p.width_nm for p in sheets]) == pytest.approx(
        TRUE_WIDTH_NM + BROADENING_NM, rel=0.05
    )
    # Height is not broadened; a tip does not make a plate taller.
    assert np.mean([p.height_nm for p in sheets]) == pytest.approx(SHEET_HEIGHT_NM, rel=0.05)


@pytest.mark.parametrize("seed", [1, 2, 3, 4, 5])
def test_deconvolving_the_tip_recovers_the_object(seed: int) -> None:
    """The closed loop's one honest claim: put in a rectangle of known size,
    record it through a modelled tip, measure it, remove the tip, and get the
    rectangle back. The rendering and the correction are derived
    independently -- one in `imaging.synthetic`, one in `compare.corrections`
    -- so agreeing is evidence rather than a tautology."""
    _, _, _, particles = _pipeline(seed)
    sheets = [p for p in particles if not p.touches_edge and 3 < p.aspect < 9]
    length = np.mean([p.length_nm for p in sheets]) - BROADENING_NM
    width = np.mean([p.width_nm for p in sheets]) - BROADENING_NM
    assert length == pytest.approx(TRUE_LENGTH_NM, rel=0.03)
    assert width == pytest.approx(TRUE_WIDTH_NM, rel=0.05)


def test_a_wrong_tip_radius_shows_up_as_a_wrong_object(seed: int = 3) -> None:
    """Which is why a tip should be characterised at the start and end of a
    session. Assuming 20 nm for a 10 nm tip removes 12.5 nm instead of 8.7 and
    the width comes back 10% short."""
    _, _, _, particles = _pipeline(seed)
    sheets = [p for p in particles if not p.touches_edge and 3 < p.aspect < 9]
    wrong = 2 * half_height_broadening_nm(tip_radius_nm=20.0, feature_height_nm=SHEET_HEIGHT_NM)
    width = np.mean([p.width_nm for p in sheets]) - wrong
    assert width < 0.95 * TRUE_WIDTH_NM


def test_the_height_estimator_does_not_sample_the_noise_tail() -> None:
    """A high percentile of a particle's pixels looks robust and is not: with
    0.12 nm of noise the 90th percentile of a flat 2.00 nm plateau sits at
    2.15, and the estimator then reads 7% high on every particle in every
    image. Raising the noise must not raise the reported height."""
    quiet = [p.height_nm for p in _pipeline(3, noise_nm=0.05)[3] if p.aspect > 3]
    loud = [p.height_nm for p in _pipeline(3, noise_nm=0.30)[3] if p.aspect > 3]
    assert np.mean(loud) == pytest.approx(np.mean(quiet), abs=0.15)


def test_every_placed_particle_is_found() -> None:
    scan, _, _, particles = _pipeline(6)
    assert len(particles) == len(scan.truth)


def test_particles_are_measured_along_themselves_not_the_scan() -> None:
    """Objects lie at every angle; measuring along the scan direction would
    make a diagonal rectangle look square."""
    _, _, _, particles = _pipeline(4)
    sheets = [p for p in particles if not p.touches_edge and 3 < p.aspect < 9]
    angles = [p.angle_deg for p in sheets]
    assert max(angles) - min(angles) > 90  # they really are at many angles
    assert np.std([p.length_nm for p in sheets]) < 0.1 * TRUE_LENGTH_NM


# -------------------------------------------------------------- classifying


def test_aggregates_are_told_apart_from_sheets() -> None:
    scan, _, _, particles = _pipeline(7, n_aggregates=5)
    # Classified against what the image shows, which is the object plus the
    # tip. A classifier handed the true dimensions would be judging the sample
    # by measurements of the image, which is the mistake `compare` exists to
    # stop; here the expectation is broadened instead.
    pop = population(
        particles,
        length_nm=TRUE_LENGTH_NM + BROADENING_NM,
        width_nm=TRUE_WIDTH_NM + BROADENING_NM,
        height_nm=SHEET_HEIGHT_NM,
    )
    assert pop.counts["well_formed"] >= 0.8 * len(scan.rectangles)
    assert pop.counts["aggregate"] >= 1


def test_a_flat_sheet_of_the_wrong_shape_is_malformed_not_aggregate() -> None:
    """Where a partly flattened twisted rectangle should land: still one layer,
    no longer a rectangle. Keeping it out of 'aggregate' is what makes the
    twist experiment's readout mean anything."""
    from dobladillo.imaging.particles import Particle

    squashed = Particle(1, (50.0, 50.0), 120.0, 70.0, SHEET_HEIGHT_NM, 8400.0, 0.0, False)
    assert (
        classify(
            squashed, length_nm=TRUE_LENGTH_NM, width_nm=TRUE_WIDTH_NM, height_nm=SHEET_HEIGHT_NM
        )
        == "malformed"
    )


def test_particles_at_the_frame_edge_are_excluded_and_counted() -> None:
    """A rectangle half outside the scan measures short and would bias both the
    dimensions and the fraction."""
    _, _, _, particles = _pipeline(5)
    pop = population(
        particles, length_nm=TRUE_LENGTH_NM, width_nm=TRUE_WIDTH_NM, height_nm=SHEET_HEIGHT_NM
    )
    assert pop.excluded_at_edge == sum(1 for p in particles if p.touches_edge)
    assert pop.total + pop.excluded_at_edge == len(particles)


# ----------------------------------------------------------------- the yield


def test_the_interval_narrows_with_the_count() -> None:
    """The claim made to the microscope group: about +-9% at 100 particles and
    +-5% at 300. If that is wrong, the ask was wrong."""
    assert Fraction(70, 100).as_dict()["plus_minus"] == pytest.approx(0.09, abs=0.01)
    assert Fraction(210, 300).as_dict()["plus_minus"] == pytest.approx(0.05, abs=0.01)


def test_a_perfect_yield_does_not_get_a_zero_width_interval() -> None:
    """40 out of 40 is not 100% +- 0%, and the textbook normal approximation
    says it is. Wilson does not."""
    low, high = Fraction(40, 40).ci95
    assert high == pytest.approx(1.0, abs=0.001)
    assert low < 0.93


def test_an_empty_count_does_not_divide_by_zero() -> None:
    assert Fraction(0, 0).value == 0.0
    assert Fraction(0, 0).ci95 == (0.0, 0.0)


# ------------------------------------------------- artefacts a real scan has


def test_scanner_bow_is_removed_not_merely_tilt() -> None:
    """A piezo bows, so the background is parabolic. A plane fit removes tilt
    exactly and leaves bow untouched -- which is why this pipeline passed a
    tilted fixture at under 1% and then, on the first scan with 4 nm of bow,
    found 4 particles of 40 and measured them at 71 nm instead of 190.

    The fix is a quadratic background. This test is the thing that would have
    caught it, and it did not exist.
    """
    _, _, _, clean = _pipeline(5)
    _, _, _, bowed = _pipeline(5, bow_nm=10.0)
    keep = lambda ps: [p for p in ps if not p.touches_edge and 3 < p.aspect < 9]  # noqa: E731
    assert len(keep(bowed)) >= 0.9 * len(keep(clean))
    assert np.mean([p.length_nm for p in keep(bowed)]) == pytest.approx(
        np.mean([p.length_nm for p in keep(clean)]), rel=0.05
    )


def test_drift_shear_and_a_tip_streak_are_survived() -> None:
    """Neither breaks segmentation, but both are modelled: an artefact that is
    survived silently is still one the fixture should contain, or the next
    change to the pipeline is untested against it."""
    _, _, _, base = _pipeline(5)
    _, _, _, messy = _pipeline(5, drift_shear=0.05, streak_lines=12)
    keep = lambda ps: [p for p in ps if not p.touches_edge and 3 < p.aspect < 9]  # noqa: E731
    assert len(keep(messy)) >= 0.9 * len(keep(base))


def test_all_the_artefacts_at_once_still_recovers_the_truth() -> None:
    scan, _, _, particles = _pipeline(5, bow_nm=4.0, drift_shear=0.05, streak_lines=12)
    sheets = [p for p in particles if not p.touches_edge and 3 < p.aspect < 9]
    assert len(sheets) >= 0.8 * len(scan.rectangles)
    assert np.mean([p.length_nm for p in sheets]) == pytest.approx(
        TRUE_LENGTH_NM + BROADENING_NM, rel=0.06
    )
