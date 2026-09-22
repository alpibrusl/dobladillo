"""Outlines, and the one thing they have to do: make a bend visible."""

from __future__ import annotations

import numpy as np
import pytest

from dobladillo.dashboard.shapes import envelope, rectangle, svg


def _rod(length: float, width: float, sagitta: float, n: int = 4000) -> np.ndarray:
    """A rod of given length and thickness, bowed by `sagitta` at its middle."""
    rng = np.random.default_rng(3)
    s = rng.uniform(-length / 2, length / 2, n)
    bow = sagitta * (1 - (2 * s / length) ** 2)
    return np.stack(
        [s, bow + rng.uniform(-width / 2, width / 2, n), rng.uniform(-width / 2, width / 2, n)],
        axis=1,
    )


def _sagitta_of(outline) -> float:
    """Recover the centreline deviation from a closed outline."""
    pts = np.array(outline.points)
    half = len(pts) // 2
    mid = (pts[:half] + pts[half:][::-1]) / 2
    chord = mid[-1] - mid[0]
    chord = chord / np.linalg.norm(chord)
    off = mid - mid[0]
    return float(np.abs(off[:, 0] * -chord[1] + off[:, 1] * chord[0]).max())


def test_a_designed_rectangle_is_its_dimensions() -> None:
    outline = rectangle(390.4, 8.0)
    assert len(outline.points) == 4
    assert outline.extent_nm == pytest.approx((390.4, 8.0))
    assert outline.origin == "designed"


def test_a_straight_rod_traces_straight() -> None:
    outline = envelope(_rod(390, 8, sagitta=0.0), origin="simulated", definition="d")
    assert _sagitta_of(outline) < 2.0


def test_a_bent_rod_traces_bent() -> None:
    """The whole point. The bundle's 51 nm arc was invisible in a table of
    length, width and height -- every number was a plausible size."""
    outline = envelope(_rod(390, 8, sagitta=50.0), origin="simulated", definition="d")
    assert _sagitta_of(outline) > 40.0


def test_an_envelope_beats_a_hull_at_showing_a_bend() -> None:
    """A convex hull of a bent rod is a lens: its outline bulges on one side
    and is flat on the other, and the flat side hides how far the centreline
    actually went. The envelope follows the object."""
    points = _rod(390, 8, sagitta=50.0)
    traced = envelope(points, origin="simulated", definition="d")
    # A hull would put its widest transverse span at the sagitta; the envelope
    # keeps the body thin and moves it instead.
    pts = np.array(traced.points)
    half = len(pts) // 2
    thickness = float(np.abs(pts[:half][:, 1] - pts[half:][::-1][:, 1]).mean())
    assert thickness < 20.0
    assert _sagitta_of(traced) > 2 * thickness


def test_envelope_refuses_the_wrong_shape_of_input() -> None:
    with pytest.raises(ValueError, match=r"\(n, 3\)"):
        envelope(np.zeros((10, 2)), origin="simulated", definition="d")
    with pytest.raises(ValueError, match="too few"):
        envelope(np.zeros((4, 3)), origin="simulated", definition="d")


def test_svg_draws_every_outline_and_themes_with_the_page() -> None:
    """Colours come from the page's tokens rather than a palette of its own,
    so the drawing follows the reader's theme like everything else."""
    drawing = svg(
        [rectangle(390, 8), envelope(_rod(390, 8, 50), origin="simulated", definition="d")]
    )
    assert drawing.count("<polygon") == 2
    assert "var(--accent)" in drawing and "var(--faint)" in drawing
    assert "#" not in drawing, "a hard-coded colour would not follow the theme"
    assert 'role="img"' in drawing


def test_svg_of_nothing_is_nothing() -> None:
    assert svg([]) == ""


def test_superimposing_stops_tumbling_smearing_the_shape() -> None:
    """Averaged in the box frame, a tumbling object averages to a disc. The
    object's own frame is the only one in which a mean shape means anything."""
    from dobladillo.dashboard.shapes import from_trajectory

    base = _rod(390, 8, sagitta=50.0)

    class _Frame:
        def __init__(self, positions):
            self.positions_nm = positions

    rng = np.random.default_rng(1)
    frames = []
    for _ in range(12):
        angle = rng.uniform(0, 2 * np.pi)
        c, s = np.cos(angle), np.sin(angle)
        spin = np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])
        frames.append(_Frame(base @ spin.T))

    outline = from_trajectory(frames)
    assert _sagitta_of(outline) > 40.0, "the bend was averaged away"


# ------------------------------------------------------------- form deviation


def test_a_designed_rectangle_is_exactly_straight() -> None:
    """Not approximately. The designed value is the thing the measure is
    compared against, and it carries no allowance."""
    from dobladillo.dashboard.shapes import straightness

    bend = straightness(rectangle(390.4, 8.0))
    assert bend.max_nm == 0.0
    assert bend.rms_nm == 0.0
    assert bend.straight


def test_straightness_scales_with_the_bend_not_with_the_size() -> None:
    from dobladillo.dashboard.shapes import straightness

    for sagitta in (0.0, 10.0, 50.0):
        outline = envelope(_rod(390, 8, sagitta), origin="simulated", definition="d")
        assert straightness(outline).max_nm == pytest.approx(sagitta, abs=6.0)


def test_a_fat_part_is_not_a_bent_part() -> None:
    """The measure works on the centreline, so thickening a straight rod must
    not register as bending. Conflating them would make every wide object look
    defective."""
    from dobladillo.dashboard.shapes import straightness

    # The property, not a ratio of raw nanometres: a wider rod samples its own
    # centreline more noisily in absolute terms, and measuring that ratio would
    # be testing the noise rather than the measure.
    for width in (8, 60, 200):
        bend = straightness(envelope(_rod(390, width, 0.0), origin="simulated", definition="d"))
        assert bend.straight, f"a straight rod {width} nm wide read as bent"
        assert bend.in_body_widths < 0.25


def test_the_verdict_is_in_the_parts_own_thickness() -> None:
    """A 50 nm deviation is nothing on a 400 nm-wide plate and damning on an
    8 nm rod, so the readable form is body widths rather than nanometres."""
    from dobladillo.dashboard.shapes import straightness

    rod = straightness(envelope(_rod(390, 8, 50.0), origin="simulated", definition="d"))
    slab = straightness(envelope(_rod(390, 200, 50.0), origin="simulated", definition="d"))
    assert not rod.straight
    assert slab.straight
    assert rod.in_body_widths > slab.in_body_widths


def test_straightness_refuses_a_degenerate_outline() -> None:
    from dobladillo.dashboard.shapes import Outline, straightness

    with pytest.raises(ValueError, match="at least four points"):
        straightness(Outline(origin="designed", definition="d", points=((0.0, 0.0),)))
