"""Where a design should fold: a predicted temperature window, and its weak staples.

Origami does not fold gradually over a whole anneal. Most of it happens in a
fairly narrow window of temperature, and Sobczak, Martin, Gerling and Dietz
(*Science* 338, 1458 (2012)) folded many shapes in minutes by holding a
constant temperature inside it. The slow ramp mostly exists to pass through
that window gently when nobody knows where it is. Know the window and the
fold can be fast -- which matters wherever temperature is hard to steer, as
in a high-speed AFM cell.

This module does not predict the window's exact position or the best
isothermal temperature. Folding is cooperative: a staple whose neighbours are
already bound binds more strongly than it does alone, so the real transition
sits above the isolated numbers here. What it gives is the distribution the
window is built from -- each staple's melting temperature against the
scaffold, in the folding buffer -- which says:

- where to point an isothermal screen (E11): around the bulk of that
  distribution, not in the 20-degree ramp a protocol inherited;
- which staples are weak: well below the rest, they bind last, bind least,
  and set how low the window reaches. Strengthening them narrows the window;
- how the window moves with magnesium, which is the easiest knob to turn when
  temperature cannot be.

**The staple's temperature is its STRONGEST domain's.** A staple nucleates on
its longest, most stable domain and is then held by the rest; domains a few
bases long have no meaningful melting temperature on their own. Each domain is
treated as a two-state duplex with the scaffold (primer3 thermodynamics,
`sequence.thermo`), with the staple in excess: Tm = dH / (dS + R ln(C_staple -
C_scaffold / 2)).

The measured window comes from E11's gradient screen, and it is what this
model should be judged against.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final

from dobladillo import _scadnano as ad
from dobladillo.sequence.thermo import R_KCAL, duplex

if TYPE_CHECKING:
    import scadnano as sc

#: Domains shorter than this have no melting temperature worth reporting on
#: their own; they are held by stacking and by the staple's other domains.
MIN_DOMAIN_FOR_TM_NT: Final = 7

#: A staple this far below the window's lower edge (the 10th percentile) is
#: flagged as weak: it binds last, if at all.
WEAK_MARGIN_C: Final = 5.0

#: The screen is padded this far beyond the 10th-90th percentile range: the
#: cooperative transition sits above the isolated numbers, and the screen
#: should bracket where the fold happens, not only where staples melt alone.
SCREEN_PAD_C: Final = 5.0


def domain_melting_c(
    sequence: str, *, magnesium_m: float, staple_m: float, scaffold_m: float, sodium_m: float = 0.0
) -> float:
    """Tm of one staple domain against the scaffold, the staple in excess."""
    d = duplex(sequence, sodium_m=sodium_m, magnesium_m=magnesium_m)
    effective = staple_m - scaffold_m / 2.0
    if effective <= 0:
        raise ValueError("the staple must be in excess over the scaffold")
    return d.dh_kcal * 1000.0 / (d.ds_cal + R_KCAL * 1000.0 * math.log(effective)) - 273.15


@dataclass(frozen=True)
class StapleMelting:
    helix: int
    offset: int
    length_nt: int
    strongest_domain_nt: int
    tm_c: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "helix": self.helix,
            "offset": self.offset,
            "length_nt": self.length_nt,
            "strongest_domain_nt": self.strongest_domain_nt,
            "tm_c": round(self.tm_c, 1),
        }


@dataclass(frozen=True)
class FoldingWindow:
    staples: tuple[StapleMelting, ...]
    magnesium_mm: float
    staple_nm: float
    scaffold_nm: float

    def _percentile(self, q: float) -> float:
        values = sorted(s.tm_c for s in self.staples)
        k = (len(values) - 1) * q
        lo, hi = math.floor(k), math.ceil(k)
        return values[lo] + (values[hi] - values[lo]) * (k - lo)

    @property
    def window_c(self) -> tuple[float, float]:
        """The bulk of the staples' melting temperatures: 10th to 90th percentile."""
        return (self._percentile(0.1), self._percentile(0.9))

    @property
    def median_c(self) -> float:
        return self._percentile(0.5)

    @property
    def weak(self) -> tuple[StapleMelting, ...]:
        floor = self.window_c[0] - WEAK_MARGIN_C
        return tuple(sorted((s for s in self.staples if s.tm_c < floor), key=lambda s: s.tm_c))

    @property
    def screen_c(self) -> tuple[int, int]:
        """A range for an isothermal gradient screen, in whole degrees."""
        low, high = self.window_c
        return (math.floor(low - SCREEN_PAD_C), math.ceil(high + SCREEN_PAD_C))

    def as_dict(self) -> dict[str, Any]:
        low, high = self.window_c
        return {
            "conditions": {
                "mgcl2_mm": self.magnesium_mm,
                "staple_nm_each": self.staple_nm,
                "scaffold_nm": self.scaffold_nm,
            },
            "staples": len(self.staples),
            "staple_tm_c": {
                "p10": round(low, 1),
                "median": round(self.median_c, 1),
                "p90": round(high, 1),
                "min": round(min(s.tm_c for s in self.staples), 1),
                "max": round(max(s.tm_c for s in self.staples), 1),
            },
            "isothermal_screen_c": list(self.screen_c),
            "weak_staples": [s.as_dict() for s in self.weak],
            "caveat": (
                "isolated staple melting temperatures; folding is cooperative and the real "
                "transition sits above them. Where the window actually is comes from the "
                "E11 gradient screen, not from this"
            ),
        }


def folding_window(
    design: sc.Design,
    *,
    magnesium_mm: float = 12.0,
    staple_nm: float = 50.0,
    scaffold_nm: float = 10.0,
) -> FoldingWindow:
    """Each staple's melting temperature against the scaffold, in the folding buffer.

    Defaults are E1's fold: 12 mM MgCl2, 10 nM scaffold, 50 nM of each staple
    (fivefold excess; E1's pool is 455 nM each, 5.5 uL in 50 uL). The design
    must carry sequences (`assign_scaffold_sequence`).
    """
    found: list[StapleMelting] = []
    for staple in ad.staples(design):
        domains = [d for d in staple.domains if hasattr(d, "helix")]
        if not domains or staple.dna_sequence is None:
            raise ValueError("the design has no sequences; assign the scaffold sequence first")
        scored = [
            (
                domain_melting_c(
                    d.dna_sequence,
                    magnesium_m=magnesium_mm / 1000.0,
                    staple_m=staple_nm * 1e-9,
                    scaffold_m=scaffold_nm * 1e-9,
                ),
                d,
            )
            for d in domains
            if d.dna_length() >= MIN_DOMAIN_FOR_TM_NT
        ]
        if not scored:
            continue  # every domain too short to have a Tm of its own
        tm, strongest = max(scored, key=lambda pair: pair[0])
        first = domains[0]
        found.append(
            StapleMelting(
                helix=first.helix,
                offset=first.start if first.forward else first.end - 1,
                length_nt=staple.dna_length(),
                strongest_domain_nt=strongest.dna_length(),
                tm_c=tm,
            )
        )
    if not found:
        raise ValueError("no staple has a domain long enough to melt on its own")
    return FoldingWindow(
        staples=tuple(found),
        magnesium_mm=magnesium_mm,
        staple_nm=staple_nm,
        scaffold_nm=scaffold_nm,
    )
