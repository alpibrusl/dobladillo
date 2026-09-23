"""Flatness: telling a sheet that rolled from one that is the wrong size.

E2's question is not "does this look twisted". Mica flattens what it adsorbs,
so a twisted sheet is pressed down rather than standing on edge. The question
is *what fraction lies flat as a clean rectangle*, and the two failure modes --
rolled, and wrong-sized -- say opposite things about the design, so they have
to be counted apart.
"""

from __future__ import annotations

from collections import Counter

import numpy as np

from dobladillo.compare.corrections import half_height_broadening_nm
from dobladillo.imaging.classify import TWISTED_HEIGHT_FACTOR, classify, population
from dobladillo.imaging.flatten import flatten
from dobladillo.imaging.particles import find_particles
from dobladillo.imaging.synthetic import SHEET_HEIGHT_NM, synthetic_scan

BROADENING = 2 * half_height_broadening_nm(tip_radius_nm=10.0, feature_height_nm=SHEET_HEIGHT_NM)
LENGTH = 191.0 + BROADENING
WIDTH = 36.0 + BROADENING


def _counted(**kw):
    scan = synthetic_scan(seed=5, n_aggregates=0, **kw)
    flattened, background = flatten(scan.image)
    found = population(
        find_particles(flattened, background),
        length_nm=LENGTH,
        width_nm=WIDTH,
        height_nm=SHEET_HEIGHT_NM,
    )
    return Counter(t.kind for t in scan.truth), found


def test_a_flat_population_reads_flat() -> None:
    placed, found = _counted(n_rectangles=30, n_twisted=0)
    assert found.counts["well_formed"] == placed["rectangle"] == 30
    assert found.counts["twisted"] == 0


def test_a_rolled_population_reads_rolled_not_malformed() -> None:
    """The distinction E2 rests on. Rolled means the twist correction failed;
    wrong-sized means the design or the fold did. Lumping them together makes
    the experiment unable to answer its own question."""
    placed, found = _counted(n_rectangles=0, n_twisted=30)
    assert found.counts["twisted"] == placed["twisted"] == 30
    assert found.counts["malformed"] == 0
    assert found.counts["well_formed"] == 0


def test_a_mixed_population_splits_correctly() -> None:
    placed, found = _counted(n_rectangles=20, n_twisted=20)
    assert found.counts["well_formed"] == placed["rectangle"]
    assert found.counts["twisted"] == placed["twisted"]


def test_every_class_is_reported_even_at_zero() -> None:
    """A class missing from the fixed key list vanishes from the totals rather
    than reporting zero. Thirty twisted sheets once counted as nothing at all
    because `classify` knew the class and `population` did not."""
    _, found = _counted(n_rectangles=10, n_twisted=0)
    assert set(found.counts) == {"well_formed", "twisted", "malformed", "aggregate"}
    assert found.counts["twisted"] == 0
    assert found.total == sum(found.counts.values())


def test_height_is_the_stable_discriminator_and_roughness_is_not() -> None:
    """Worth pinning, because the intuitive ranking is wrong twice over.

    Roughness moves MORE in relative terms on a quiet image -- 3.8x against
    height's 1.5x at 0.06 nm of noise. But its baseline *is* the noise, so the
    separation collapses as the image gets worse: 3.80, 2.07, 1.20, 1.32 at
    0.06, 0.12, 0.30 and 0.50 nm. Height's baseline is the object, and its
    ratio holds at 1.49-1.51 throughout.

    So height decides the class and roughness is kept as a secondary signal
    for the case it alone can see: a fold or tear that does not lift the
    median.
    """

    def ratios(noise: float) -> tuple[float, float]:
        out = {}
        for key, kw in (
            ("flat", {"n_rectangles": 20, "n_twisted": 0}),
            ("roll", {"n_rectangles": 0, "n_twisted": 20}),
        ):
            scan = synthetic_scan(seed=5, n_aggregates=0, noise_nm=noise, **kw)
            flattened, background = flatten(scan.image)
            ps = [p for p in find_particles(flattened, background) if not p.touches_edge]
            out[key] = (
                float(np.mean([p.height_nm for p in ps])),
                float(np.mean([p.roughness_nm for p in ps])),
            )
        (fh, fr), (rh, rr) = out["flat"], out["roll"]
        return rh / fh, rr / fr

    quiet_h, quiet_r = ratios(0.06)
    noisy_h, noisy_r = ratios(0.30)

    assert quiet_r > quiet_h, "roughness should look better on a quiet image"
    assert noisy_r < 1.5, "roughness should stop separating as noise rises"
    assert 1.4 < noisy_h < 1.7, "height should not care"
    assert abs(noisy_h - quiet_h) < 0.1, "height's separation is noise-independent"


def test_the_twisted_threshold_sits_below_the_aggregate_one() -> None:
    """Otherwise the two classes would both claim the same particle, and which
    one won would depend on the order of the checks."""
    from dobladillo.imaging.classify import AGGREGATE_HEIGHT_FACTOR

    assert 1.0 < TWISTED_HEIGHT_FACTOR < AGGREGATE_HEIGHT_FACTOR


def test_a_wrong_sized_flat_sheet_is_malformed_not_twisted() -> None:
    from dobladillo.imaging.particles import Particle

    small = Particle(
        label=1,
        centre_px=(50.0, 50.0),
        length_nm=LENGTH * 0.5,
        width_nm=WIDTH,
        height_nm=SHEET_HEIGHT_NM,
        area_nm2=1.0,
        angle_deg=0.0,
        touches_edge=False,
    )
    assert (
        classify(small, length_nm=LENGTH, width_nm=WIDTH, height_nm=SHEET_HEIGHT_NM) == "malformed"
    )
