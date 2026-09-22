"""Ports, and the cross-talk check that is the point of having them."""

from __future__ import annotations

import pytest

from dobladillo.interfaces import Bond, Brick, Port, can_mate, crosstalk, unsatisfied


def _port(**kw) -> Port:
    base = dict(name="p", kind="latch", polarity="a", helices=(0,), offset=0, channel=0)
    return Port(**{**base, **kw})


def test_a_port_mates_only_with_its_opposite() -> None:
    assert can_mate(_port(polarity="a"), _port(polarity="b"))
    assert not can_mate(_port(polarity="a"), _port(polarity="a"))


def test_channels_separate_interfaces() -> None:
    """The whole mechanism: one brick can carry several ports of one kind, and
    they do not bind each other."""
    assert not can_mate(_port(polarity="a", channel=0), _port(polarity="b", channel=1))


def test_width_must_match() -> None:
    """Two ports of different widths are different interfaces however well
    their channels agree — a four-helix edge cannot join a six-helix one."""
    wide = _port(kind="edge", polarity="a", helices=(0, 1, 2, 3))
    narrow = _port(kind="edge", polarity="b", helices=(0, 1))
    assert not can_mate(wide, narrow)


def test_kinds_do_not_cross() -> None:
    assert not can_mate(_port(kind="edge", polarity="a"), _port(kind="latch", polarity="b"))


def test_a_port_rejects_nonsense() -> None:
    with pytest.raises(ValueError, match="unknown port kind"):
        _port(kind="glue")
    with pytest.raises(ValueError, match="spans no helices"):
        _port(helices=())
    with pytest.raises(ValueError, match="lists a helix twice"):
        _port(helices=(0, 0))


def test_a_brick_refuses_duplicate_port_names() -> None:
    with pytest.raises(ValueError, match="port name twice"):
        Brick(name="b", ports=(_port(name="x"), _port(name="x", polarity="b")))


def test_identical_latches_on_one_assembly_all_cross_bind() -> None:
    """The finding this module produced on its first run, and it invalidates an
    arithmetic done before it existed.

    A film of N hinges sharing one latch sequence is not N switches. Every
    latch binds every other latch, so it is one interface asked to mean N
    things, and no amount of sequence optimisation fixes that — they ARE the
    same sequence.
    """
    from dobladillo.parts.hinge import bistable_hinge

    film = {f"h{i}": bistable_hinge().brick(channel=0) for i in range(3)}
    found = crosstalk(film)
    assert len(found) == 6  # 3 pairs of bricks, 2 mating combinations each
    assert all(c.signature[0] == "latch" for c in found)


def test_one_channel_per_hinge_clears_it() -> None:
    from dobladillo.parts.hinge import bistable_hinge

    film = {f"h{i}": bistable_hinge().brick(channel=i) for i in range(3)}
    assert crosstalk(film) == ()


def test_an_intended_bond_is_not_reported_as_crosstalk() -> None:
    left = Brick(name="L", ports=(_port(name="out", polarity="a"),))
    right = Brick(name="R", ports=(_port(name="in", polarity="b"),))
    bricks = {"L": left, "R": right}
    assert len(crosstalk(bricks)) == 1
    intended = (Bond(left="L", left_port="out", right="R", right_port="in"),)
    assert crosstalk(bricks, intended) == ()


def test_unsatisfied_reports_a_bond_that_would_not_bind() -> None:
    """The complement of cross-talk: an interface that should bind and will
    not. Silence on this would let an assembly be specified that cannot form."""
    left = Brick(name="L", ports=(_port(name="out", polarity="a", channel=0),))
    right = Brick(name="R", ports=(_port(name="in", polarity="b", channel=1),))
    bonds = (Bond(left="L", left_port="out", right="R", right_port="in"),)
    problems = unsatisfied({"L": left, "R": right}, bonds)
    assert problems and "different signatures" in problems[0]


def test_unsatisfied_catches_a_bond_to_a_port_that_does_not_exist() -> None:
    left = Brick(name="L", ports=(_port(name="out"),))
    bonds = (Bond(left="L", left_port="nope", right="L", right_port="out"),)
    assert unsatisfied({"L": left}, bonds)


def test_real_parts_declare_ports() -> None:
    """An abstraction nothing implements is a wish. Both of these were already
    built around an interface before there was a word for it."""
    from dobladillo.parts.hinge import bistable_hinge
    from dobladillo.parts.rectangle import rothemund_rectangle

    hinge = bistable_hinge().brick()
    assert {p.name for p in hinge.of_kind("latch")} == {"latch-a", "latch-b"}
    assert can_mate(hinge.port("latch-a"), hinge.port("latch-b"))

    rectangle = rothemund_rectangle().brick()
    ends = rectangle.of_kind("edge")
    assert len(ends) == 2
    assert can_mate(*ends)
    assert ends[0].width == rothemund_rectangle().helices
