"""Which latches can actually be measured, and how to guarantee one of them is.

A bulk FRET experiment reports a probability. A probability near 0 or 1 carries
almost no information about the free energy behind it: p = 0.999 and p = 0.99999
are four kT apart and look the same through the noise. So a construct is
informative only in a narrow window of bias, and the window is narrow -- about
three kT wide.

The problem this creates for Stage 0 is not obvious from the prose. Stage 0
sweeps latch length and GC content, which moves the SEQUENCE part of the bias.
But the measurable bias also carries the conformational cost of closing the
hinge, which is not predictable, is the same for every construct sharing a
core, and is exactly what Stage 0 is there to measure. It therefore slides the
entire sweep bodily up or down by an unknown amount before any construct is
read.

Ten constructs spanning six kT, shifted by an unknown offset, can easily land
entirely outside a three kT window -- in which case every measurement returns
p = 0 or p = 1, and the stage produces no information at all for its EUR 1324.

The fix is a bracketing ladder: a small set of latches whose predicted fields
are spaced no wider than the window, so that whatever the offset turns out to
be, at least one rung lands inside it. That rung locates the offset, and the
real sweep is then placed around it.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final

from dobladilo.sequence.thermo import duplex, is_self_complementary, latch_field_kt

#: A measured probability is informative between these bounds. Outside them the
#: free energy is not recoverable to better than the width of the tail, and two
#: constructs kT apart are indistinguishable.
INFORMATIVE_PROBABILITY: Final = (0.05, 0.95)

#: Folding and imaging happen near room temperature, so bias is quoted there
#: rather than at the 37 C of a quoted dG.
DESIGN_TEMPERATURE_K: Final = 298.15

#: The folding buffer. See `constants.MGCL2_SCREEN_MM` for the screen around it.
DESIGN_MAGNESIUM_M: Final = 0.012

#: Longest run of one base allowed in a latch. Four or more is a synthesis and
#: secondary-structure liability, and a G-run is the worst of them.
MAX_HOMOPOLYMER_RUN: Final = 3


def informative_half_width_kt() -> float:
    """Half the window, in the field h. p(latched) = 1/(1 + exp(-2h))."""
    low, high = INFORMATIVE_PROBABILITY
    return 0.5 * math.log(high / (1.0 - high))


def informative_window_kt() -> float:
    """Full width of the window in h. About 2.9 kT."""
    return 2.0 * informative_half_width_kt()


def probability(field_kt: float) -> float:
    """p(latched) for a field, under this project's Ising convention."""
    return 1.0 / (1.0 + math.exp(-2.0 * field_kt))


def is_informative(field_kt: float) -> bool:
    low, high = INFORMATIVE_PROBABILITY
    return low <= probability(field_kt) <= high


def _acceptable(sequence: str) -> bool:
    if is_self_complementary(sequence):
        return False
    run = 1
    for a, b in zip(sequence, sequence[1:], strict=False):
        run = run + 1 if a == b else 1
        if run > MAX_HOMOPOLYMER_RUN:
            return False
    return True


def latch_sequence(*, length: int, gc: int) -> str:
    """A latch of this length and GC count, built deterministically.

    GC positions are spread as evenly as the counts allow, and G/C and A/T
    alternate within their own positions, so no sequence carries a homopolymer
    run. Deterministic rather than randomised: the set of candidates is then a
    function of the parameters, not of a seed nobody recorded.
    """
    if not 0 <= gc <= length:
        raise ValueError(f"cannot put {gc} G/C in {length} bases")
    strong = {round(i * length / gc) for i in range(gc)} if gc else set()
    letters, s_i, w_i = [], 0, 0
    for i in range(length):
        if i in strong:
            letters.append("GC"[s_i % 2])
            s_i += 1
        else:
            letters.append("AT"[w_i % 2])
            w_i += 1
    return "".join(letters)


def candidate_latches(*, lengths: range = range(4, 13)) -> tuple[str, ...]:
    """Every acceptable latch across length and GC content."""
    found: list[str] = []
    for length in lengths:
        for gc in range(length + 1):
            sequence = latch_sequence(length=length, gc=gc)
            if _acceptable(sequence) and sequence not in found:
                found.append(sequence)
    return tuple(found)


@dataclass(frozen=True)
class Rung:
    """One latch and the bias it is predicted to impose."""

    sequence: str
    field_kt: float

    @property
    def length_bp(self) -> int:
        return len(self.sequence)


@dataclass(frozen=True)
class Ladder:
    """A bracketing set, and the guarantee it does or does not provide."""

    rungs: tuple[Rung, ...]
    window_kt: float

    @property
    def span_kt(self) -> tuple[float, float]:
        fields = [r.field_kt for r in self.rungs]
        return (min(fields), max(fields))

    @property
    def offset_range_kt(self) -> tuple[float, float]:
        """Conformational offsets this ladder can measure. A rung of field f
        reads informatively when the offset c satisfies |f - c/2| <= half the
        window, so each rung covers a stretch of c twice the width it covers
        in f."""
        half = self.window_kt / 2.0
        fields = [r.field_kt for r in self.rungs]
        return (2.0 * (min(fields) - half), 2.0 * (max(fields) + half))

    @property
    def largest_gap_kt(self) -> float:
        fields = sorted(r.field_kt for r in self.rungs)
        return max((b - a for a, b in zip(fields, fields[1:], strict=False)), default=0.0)

    @property
    def covers_its_range(self) -> bool:
        """Whether no offset inside `offset_range_kt` can fall between rungs."""
        return self.largest_gap_kt <= self.window_kt

    def rung_for(self, conformational_kt: float) -> Rung | None:
        """Which rung reads as informative if the offset is this. None means
        the ladder does not reach that offset and the hinge geometry, not the
        latch, is what has to change."""
        for rung in self.rungs:
            if is_informative(rung.field_kt - conformational_kt / 2.0):
                return rung
        return None

    def summary(self) -> str:
        low, high = self.span_kt
        return (
            f"{len(self.rungs)} rungs spanning {low:.1f} to {high:.1f} kT of field, "
            f"measuring a conformational cost anywhere in "
            f"{self.offset_range_kt[0]:.1f} to {self.offset_range_kt[1]:.1f} kT; "
            f"largest gap {self.largest_gap_kt:.2f} against a {self.window_kt:.2f} kT "
            f"window: {'covered' if self.covers_its_range else 'GAPPED'}"
        )


def ladder(
    *,
    temperature_k: float = DESIGN_TEMPERATURE_K,
    magnesium_m: float = DESIGN_MAGNESIUM_M,
    lengths: range = range(4, 13),
) -> Ladder:
    """The smallest bracketing ladder that leaves no gap wider than the window.

    Greedy from the weakest latch upward: take the first candidate, then each
    next one whose field is the largest still within one window of the last.
    That is optimal here because the candidates are points on a line and the
    constraint is only on consecutive spacing.
    """
    window = informative_window_kt()
    scored = sorted(
        (
            Rung(
                sequence=s,
                field_kt=latch_field_kt(
                    duplex(s, magnesium_m=magnesium_m), temperature_k=temperature_k
                ),
            )
            for s in candidate_latches(lengths=lengths)
        ),
        key=lambda r: r.field_kt,
    )
    if not scored:
        raise ValueError("no acceptable latch sequences in that length range")

    # Standard covering greedy: from the current rung, step to the furthest
    # candidate still within one window, which is the fewest rungs that leaves
    # no gap. Taking the NEAREST instead would also cover, with more oligos.
    chosen = [scored[0]]
    i = 0
    while i < len(scored) - 1:
        reachable = [
            j
            for j in range(i + 1, len(scored))
            if scored[j].field_kt - chosen[-1].field_kt <= window
        ]
        if not reachable:
            i += 1
            chosen.append(scored[i])
            continue
        i = reachable[-1]
        chosen.append(scored[i])
    return Ladder(rungs=tuple(chosen), window_kt=window)
