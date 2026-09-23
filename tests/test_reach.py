"""Latch reach: can the two extensions meet, and is the mapping to them right."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from dobladillo import _scadnano as ad
from dobladillo.analysis.observables import reach, separation_nm
from dobladillo.parts.hinge import bistable_hinge
from dobladillo.parts.rectangle import rothemund_rectangle


class _Frame:
    def __init__(self, positions):
        self.positions_nm = positions


def test_the_two_maps_partition_the_topology(tmp_path: Path) -> None:
    """The bug this found, and it was silent.

    `nucleotide_indices` skipped extensions WITHOUT advancing its counter, so
    every particle after one got an index too low. The hinge's two 8 nt
    latches left the map 16 short of the topology's 9184 — and `mutual_traps`
    builds its traps file from that map, so relaxation would have restrained
    the wrong nucleotides.
    """
    part = bistable_hinge()
    ad.write_oxdna_files(part.design, directory=tmp_path, name="h")
    particles = int((tmp_path / "h.top").read_text().splitlines()[0].split()[0])

    paired = set(ad.nucleotide_indices(part.design).values())
    unpaired = {i for _, idx in ad.extension_indices(part.design) for i in idx}

    assert paired & unpaired == set(), "a particle is in both maps"
    assert sorted(paired | unpaired) == list(range(particles)), "a particle is in neither"


def test_a_design_without_extensions_is_unaffected() -> None:
    """The rectangle has none, so the fix must be a no-op there -- otherwise it
    would have moved every pinned count in the project."""
    part = rothemund_rectangle()
    assert ad.extension_indices(part.design) == []
    mapped = ad.nucleotide_indices(part.design)
    assert len(mapped) == len(set(mapped.values())) == 13860


def test_the_latches_are_found_and_are_complementary() -> None:
    part = bistable_hinge()
    extensions = ad.extension_indices(part.design)
    assert len(extensions) == 2
    (seq_a, idx_a), (seq_b, idx_b) = extensions
    assert len(idx_a) == len(idx_b) == len(seq_a) == len(seq_b)
    from dobladillo.sequence.thermo import reverse_complement

    assert seq_b == reverse_complement(seq_a)


def _two_groups(separation: float, n: int = 8, frames: int = 20):
    """Two clusters a known distance apart, with noise."""
    rng = np.random.default_rng(0)
    out = []
    for _ in range(frames):
        a = rng.normal(0, 0.3, (n, 3))
        b = rng.normal(0, 0.3, (n, 3)) + np.array([separation, 0.0, 0.0])
        out.append(_Frame(np.vstack([a, b])))
    return out, list(range(n)), list(range(n, 2 * n))


def test_separation_recovers_a_known_distance() -> None:
    frames, a, b = _two_groups(30.0)
    assert separation_nm(frames, a, b).mean == pytest.approx(30.0, abs=0.5)


def test_separation_refuses_indices_from_another_design() -> None:
    """A silently wrong index is the failure mode this whole area has: the
    numbers come back plausible and describe the wrong particles."""
    frames, a, _ = _two_groups(30.0)
    with pytest.raises(ValueError, match="not the design these indices came from"):
        separation_nm(frames, a, [9999])


def test_reach_is_decisive_when_negative_and_permissive_when_positive() -> None:
    """A False means the mechanism cannot close. A True means it might, and the
    span is a contour length, so it is generous by construction."""
    close, a, b = _two_groups(4.0)
    far, _, _ = _two_groups(40.0)

    assert reach(close, a, b, bases=8).within_reach
    assert not reach(far, a, b, bases=8).within_reach
    # 8 bases each at 0.63 nm: 10.08 nm of combined contour.
    assert reach(close, a, b, bases=8).span_nm == pytest.approx(10.08)


def test_reach_reports_the_closest_approach_not_just_the_mean() -> None:
    """A latch binds when it gets close once, not on average. A mean that sits
    outside reach while the minimum sits inside is the interesting case."""
    frames, a, b = _two_groups(30.0, frames=19)
    rng = np.random.default_rng(1)
    n = 8
    frames.append(
        _Frame(
            np.vstack(
                [rng.normal(0, 0.3, (n, 3)), rng.normal(0, 0.3, (n, 3)) + np.array([3.0, 0.0, 0.0])]
            )
        )
    )
    found = reach(frames, a, b, bases=8)
    assert found.separation.mean > 20
    assert found.closest_nm < 5
    assert found.within_reach
