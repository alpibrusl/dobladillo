"""Ports: the declared places where one brick may attach to another.

M1. The abstraction is borrowed from mechanical CAD, where reuse comes from
parts declaring *mates* rather than absolute coordinates — and, more to the
point, from the 3D-printing ecosystems where it actually works. LEGO studs and
Gridfinity baseplates are reusable not because the modelling is clever but
because the interface is frozen, dimensioned, versioned and testable.

This project already found the mechanism once without naming it. Stage 0 costs
EUR 1324 instead of EUR 7000 because ten constructs share one staple core and
swap only their latches: the core is a frozen interface and the latches are
modules. Generalising that is what this module is for.

**Where the CAD analogy breaks, and it matters.** In CAD a mate is enforced by
the software and then by rigidity — two parts either fit or they do not. A
port here is a thermodynamic equilibrium, and the thing that makes it hard is
not that the right pair might fail to bind. It is that the *wrong* pair will
bind anyway, at some rate, because complementarity is graded rather than
boolean.

So a port carries a `channel`, and two ports mate only when their channels
agree. Whether distinct channels are actually orthogonal *as sequences* is M2's
problem and needs thermodynamics. What is checkable here, without a single
base, is the structural half: that an assembly does not contain two pairs which
would mate when only one was intended. `crosstalk` reports exactly that, and a
design with cross-talk cannot be rescued by better sequences.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from typing import Any, Final, Literal

#: What a port is for. `edge` joins two bricks side by side on the lattice;
#: `stack` puts one on top of another, which is what a multi-layer plate needs;
#: `latch` is a switchable bond, the hinge's kind.
Kind = Literal["edge", "stack", "latch"]

KINDS: Final[tuple[Kind, ...]] = ("edge", "stack", "latch")

#: Which half of a mating pair. Deliberately not "male"/"female": a DNA
#: interface is a sequence and its complement, and there is no protrusion.
Polarity = Literal["a", "b"]

OPPOSITE: Final[dict[Polarity, Polarity]] = {"a": "b", "b": "a"}


@dataclass(frozen=True)
class Port:
    """One declared interface on a brick."""

    name: str
    kind: Kind
    polarity: Polarity
    #: Which helices the port spans. Its length is the port's width, and two
    #: ports of different widths cannot mate however well their channels agree.
    helices: tuple[int, ...]
    #: Where along the helices the port sits.
    offset: int
    #: Identity of the interface. Ports mate only within a channel, which is
    #: what lets one brick carry several ports of the same kind.
    channel: int = 0

    def __post_init__(self) -> None:
        if self.kind not in KINDS:
            raise ValueError(f"unknown port kind {self.kind!r}; expected one of {KINDS}")
        if self.polarity not in OPPOSITE:
            raise ValueError(f"polarity is 'a' or 'b', got {self.polarity!r}")
        if not self.helices:
            raise ValueError(f"port {self.name!r} spans no helices")
        if len(set(self.helices)) != len(self.helices):
            raise ValueError(f"port {self.name!r} lists a helix twice: {self.helices}")
        if self.channel < 0:
            raise ValueError(f"channel is not negative, got {self.channel}")

    @property
    def width(self) -> int:
        return len(self.helices)

    @property
    def signature(self) -> tuple[Kind, int, int]:
        """What a port must match to mate, ignoring polarity."""
        return (self.kind, self.channel, self.width)

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "polarity": self.polarity,
            "helices": list(self.helices),
            "offset": self.offset,
            "channel": self.channel,
            "width": self.width,
        }


def can_mate(one: Port, other: Port) -> bool:
    """Whether two ports would bind.

    Deliberately symmetric and total: it answers for any pair, including pairs
    nobody intended, because the unintended ones are the whole problem.
    """
    return one.signature == other.signature and one.polarity == OPPOSITE[other.polarity]


@dataclass(frozen=True)
class Brick:
    """A part, and the interfaces it offers."""

    name: str
    ports: tuple[Port, ...] = ()

    def __post_init__(self) -> None:
        names = [p.name for p in self.ports]
        if len(set(names)) != len(names):
            raise ValueError(f"{self.name} declares a port name twice: {sorted(names)}")

    def port(self, name: str) -> Port:
        for candidate in self.ports:
            if candidate.name == name:
                return candidate
        raise KeyError(f"{self.name} has no port {name!r}")

    def of_kind(self, kind: Kind) -> tuple[Port, ...]:
        return tuple(p for p in self.ports if p.kind == kind)

    def as_dict(self) -> dict[str, Any]:
        return {"name": self.name, "ports": [p.as_dict() for p in self.ports]}


@dataclass(frozen=True)
class Bond:
    """An intended mating between two bricks' ports."""

    left: str
    left_port: str
    right: str
    right_port: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "left": f"{self.left}.{self.left_port}",
            "right": f"{self.right}.{self.right_port}",
        }


@dataclass(frozen=True)
class Crosstalk:
    """A pair that would mate and was not asked to."""

    left: str
    left_port: str
    right: str
    right_port: str
    signature: tuple[Kind, int, int]

    def as_dict(self) -> dict[str, Any]:
        kind, channel, width = self.signature
        return {
            "left": f"{self.left}.{self.left_port}",
            "right": f"{self.right}.{self.right_port}",
            "kind": kind,
            "channel": channel,
            "width": width,
        }


def crosstalk(bricks: dict[str, Brick], intended: tuple[Bond, ...] = ()) -> tuple[Crosstalk, ...]:
    """Every pair of ports that would mate but was not asked to.

    The structural half of orthogonality, and the half that can be settled
    without a single base of sequence. If two unintended ports share a
    signature and oppose in polarity, no amount of sequence design fixes it --
    they are the same interface, and the assembly has asked for one interface
    to mean two things.

    Bricks appearing more than once in an assembly are not modelled here: a
    port on brick X mates with a port on brick Y, and X against a second copy
    of X is a separate question about stoichiometry.
    """
    wanted = {frozenset(((b.left, b.left_port), (b.right, b.right_port))) for b in intended}
    found = []
    for (name_a, brick_a), (name_b, brick_b) in itertools.combinations(bricks.items(), 2):
        for port_a, port_b in itertools.product(brick_a.ports, brick_b.ports):
            if not can_mate(port_a, port_b):
                continue
            if frozenset(((name_a, port_a.name), (name_b, port_b.name))) in wanted:
                continue
            found.append(
                Crosstalk(
                    left=name_a,
                    left_port=port_a.name,
                    right=name_b,
                    right_port=port_b.name,
                    signature=port_a.signature,
                )
            )
    return tuple(found)


def unsatisfied(bricks: dict[str, Brick], intended: tuple[Bond, ...]) -> tuple[str, ...]:
    """Intended bonds whose ports do not actually mate.

    The complement of `crosstalk`: one reports interfaces that bind and should
    not, this reports ones that should and will not.
    """
    problems = []
    for bond in intended:
        try:
            left = bricks[bond.left].port(bond.left_port)
            right = bricks[bond.right].port(bond.right_port)
        except KeyError as exc:
            problems.append(f"{bond.as_dict()}: {exc}")
            continue
        if not can_mate(left, right):
            reason = (
                "different signatures" if left.signature != right.signature else "same polarity"
            )
            problems.append(
                f"{bond.left}.{bond.left_port} and {bond.right}.{bond.right_port} "
                f"do not mate: {reason}"
            )
    return tuple(problems)
