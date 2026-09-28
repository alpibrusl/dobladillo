"""The experiment programme as data, so the roadmap and the dashboard agree.

`experiments/ROADMAP.md` is prose for a person. This is the same programme in a
form the toolchain can render and test against, and it is the source of truth
for anything a machine reads.

Scores are judgements. They are typed here with the reason attached, because a
number like "0.35" with no rationale is unfalsifiable and invites being taken
for a calculation. Nothing multiplies them for you except `critical_path`,
which says what it is doing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final


@dataclass(frozen=True)
class Experiment:
    """One experiment, its scores, and what it is waiting for."""

    id: str
    title: str
    epic: int | None
    relevance: int
    difficulty: int
    success: float
    blocked_by: str
    why: str
    on_critical_path: bool = True

    def __post_init__(self) -> None:
        for name, value in (("relevance", self.relevance), ("difficulty", self.difficulty)):
            if not 1 <= value <= 5:
                raise ValueError(f"{name} is 1..5, got {value}")
        if not 0.0 < self.success <= 1.0:
            raise ValueError(f"success is a probability, got {self.success}")

    @property
    def ready(self) -> bool:
        return not self.blocked_by

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "epic": self.epic,
            "relevance": self.relevance,
            "difficulty": self.difficulty,
            "success": self.success,
            "ready": self.ready,
            "blocked_by": self.blocked_by,
            "why": self.why,
            "on_critical_path": self.on_critical_path,
        }


EXPERIMENTS: Final[tuple[Experiment, ...]] = (
    Experiment(
        id="E1",
        title="Rothemund rectangle, AFM, with a positive control",
        epic=None,
        relevance=5,
        difficulty=1,
        success=0.90,
        blocked_by="",
        why="The most reproduced structure in the field. It gates everything: if it "
        "does not fold and image here, the problem is in our chain and every later "
        "result inherits it.",
    ),
    Experiment(
        id="E2",
        title="Twist pair",
        epic=None,
        relevance=4,
        difficulty=2,
        success=0.75,
        blocked_by="",
        why="Validates the twist correction that every square-lattice dimension "
        "rests on. Whether deleting one base every 64 cancels the twist in practice "
        "is visible in an AFM image and nowhere else.",
        on_critical_path=False,
    ),
    Experiment(
        id="E3",
        title="Single hinge, fold check",
        epic=2,
        relevance=5,
        difficulty=2,
        success=0.70,
        blocked_by="a folded-hinge footprint prediction",
        why="The cheapest thing that can invalidate the hinge line. One construct "
        "rather than eight, and the original plan went straight from 'no hinge has "
        "ever been folded' to an eight-construct ladder with a FRET readout.",
    ),
    Experiment(
        id="E4",
        title="Bracketing ladder, 8 latches + 2 locked references",
        epic=2,
        relevance=5,
        difficulty=3,
        success=0.60,
        blocked_by="hamiltonian/fret.py",
        why="Locates the conformational offset. Without it Stage 0 can return ten "
        "saturated measurements and no information, because a FRET probability is "
        "informative over only about 2.9 kT and the offset slides the whole sweep. "
        "The ladder's rungs are read against two locked references, open and "
        "latched (`bracket`), without which a bulk FRET efficiency cannot be "
        "turned into p(latched).",
    ),
    Experiment(
        id="E5",
        title="Stage 0, 10 constructs",
        epic=2,
        relevance=5,
        difficulty=3,
        success=0.55,
        blocked_by="hamiltonian/equilibrium.py",
        why="Measures the manufacturing noise floor, which sets the resolution of "
        "everything after it. Its intercept is also the only measurement of the "
        "conformational cost of closing.",
    ),
    Experiment(
        id="E6",
        title="Stage 1, 25 constructs",
        epic=2,
        relevance=5,
        difficulty=4,
        success=0.35,
        blocked_by="two-colour smFRET and joint-state ligation controls",
        why="The decision point. Is the coupling constant when the biases are "
        "varied? If not there is no Hamiltonian, only a coupled system — which is "
        "a real finding about molecular coupling and is publishable.",
    ),
    Experiment(
        id="E7",
        title="Thickness ladder, 4 plates",
        epic=3,
        relevance=3,
        difficulty=2,
        success=0.80,
        blocked_by="a multi-layer plate part",
        why="The offer to the AFM partner. A stiffness standard tests one number; a "
        "thickness ladder tests the whole inference chain, and needs no prior "
        "agreement on what DNA's modulus is.",
        on_critical_path=False,
    ),
)


def critical_path() -> tuple[tuple[Experiment, ...], float]:
    """The experiments that gate a validated Hamiltonian, and their product.

    A product of independent judgements, which is a crude thing to do and is
    reported as such. It is here because the number is decision-relevant and
    leaving it to be worked out privately is worse than stating it with its
    caveat attached.
    """
    chain = tuple(e for e in EXPERIMENTS if e.on_critical_path)
    product = 1.0
    for experiment in chain:
        product *= experiment.success
    return chain, product


def by_id(experiment_id: str) -> Experiment:
    for experiment in EXPERIMENTS:
        if experiment.id == experiment_id:
            return experiment
    raise KeyError(f"no experiment {experiment_id!r}")
