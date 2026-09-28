"""Folding protocols taken whole from one publication, for parts that need one.

The generic sheet in `lab.protocol` is assembled from defaults in
`constants.py`, each with its own citation. That is fine for a flat sheet,
where the field's conditions are forgiving and E1 screens magnesium anyway.
It is not fine for a 3D object: buffer, magnesium, scaffold and staple
concentrations, the anneal, the gel and the purification were validated
**together**, on one object, by one group, and a protocol stitched from
several papers is a protocol nobody has run. The project's roadmap says it
directly: exact folding, Mg2+, concentration, purification and AFM-preparation
conditions must follow the chosen protocol, and parameters from different
publications are not mixed without validation.

So a part with a published protocol carries the whole record here, as one
object with one citation, and nothing in it is filled from memory. A
parameter the source does not state is recorded as `None` with the words "not
stated in the source -- confirm with the lab", and that is what the bench sheet
says too. Rule 6 of AGENTS.md puts physical constants in `constants.py`; these
are not constants but one paper's method, and keeping them together is the
point.

**The quotes** were read from the article's open-access HTML through a text
extraction, and are normalised to ASCII: degree signs dropped, the
multiplication sign as x, micro as u, minus as a hyphen, and "..." where
words between two fragments of one sentence are left out. Check them against
the published PDF before the session; a quote that does not match is a
finding, not a typo to fix quietly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

NOT_STATED: Final = "not stated in the source -- confirm with the lab"


@dataclass(frozen=True)
class Step:
    """One parameter: its value as the source gives it, or None and why."""

    what: str
    value: str | None
    #: The source's own words, where the value was read. Empty for a value this
    #: project chose (and says so in `note`).
    quote: str = ""
    note: str = ""

    @property
    def stated(self) -> bool:
        return self.value is not None


@dataclass(frozen=True)
class PublishedProtocol:
    part: str
    citation: str
    doi: str
    licence: str
    read_at: str
    read_on: str
    object_in_source: str
    fold: tuple[Step, ...]
    anneal: tuple[Step, ...]
    gel: tuple[Step, ...]
    purification: tuple[Step, ...]
    deposition: tuple[Step, ...]
    caveats: tuple[str, ...]

    def markdown(self) -> str:
        def table(steps: tuple[Step, ...]) -> list[str]:
            rows = ["| parameter | value | source |", "|---|---|---|"]
            for s in steps:
                value = s.value if s.stated else f"**{NOT_STATED}**"
                where = f'"{s.quote}"' if s.quote else (s.note or "")
                if s.quote and s.note:
                    where += f" -- {s.note}"
                rows.append(f"| {s.what} | {value} | {where} |")
            return rows

        lines = [
            f"# {self.part}: folding protocol",
            "",
            "Generated when this experiment was created, from ONE published protocol,",
            "taken whole. If you change anything, record it in `during/log.md` as a",
            "deviation rather than editing here -- this file is what was *meant* to happen.",
            "Do not substitute values from `experiments/protocols/common-techniques.md`:",
            "its buffer, gel and PEG recipe are a different protocol's.",
            "",
            f"**Source.** {self.citation} doi:{self.doi} ({self.licence}). Read at",
            f"{self.read_at} on {self.read_on}.",
            "",
            f"**Object in the source.** {self.object_in_source}",
            "",
            "## Folding mixture",
            "",
            *table(self.fold),
            "",
            "## Anneal",
            "",
            *table(self.anneal),
            "",
            "## Gel -- before any AFM",
            "",
            *table(self.gel),
            "",
            "## Purification",
            "",
            *table(self.purification),
            "",
            "## Deposition on mica",
            "",
            *table(self.deposition),
            "",
            "## Caveats",
            "",
            *[f"- {c}" for c in self.caveats],
            "",
        ]
        return "\n".join(lines)


#: Enlund, Julin, Linko, Kostiainen 2024: a six-helix bundle folded on the
#: p7249 scaffold, checked on a Mg gel, PEG-purified and imaged dry by AFM on
#: mica. Every quoted value below was read from the open-access article
#: (PMC11256221) on 2026-09-28.
BUNDLE_ENLUND_2024: Final = PublishedProtocol(
    part="bundle",
    citation=(
        "Enlund E, Julin S, Linko V, Kostiainen MA. Structural stability of DNA origami "
        "nanostructures in organic solvents. Nanoscale 16, 13407-13415 (2024)."
    ),
    doi="10.1039/D4NR02185A",
    licence="CC BY",
    read_at="https://pmc.ncbi.nlm.nih.gov/articles/PMC11256221/",
    read_on="2026-09-28",
    object_in_source=(
        "their six-helix bundle, whose design they cite to Bui et al., Nano Lett. 10, "
        "3367-3372 (2010), on the same 7,249-nt p7249 scaffold -- NOT this project's "
        "routing. Same lattice, scaffold and staple chemistry; a different staple set."
    ),
    fold=(
        Step(
            "scaffold",
            "p7249, 20 nM final",
            quote="circular p7249 scaffold (final concentration of 20 nM)",
        ),
        Step("each staple", "10x over scaffold = 200 nM", quote="10x excess of staple strands"),
        Step(
            "folding buffer (FOB)",
            "1x TAE + 12.5 mM MgCl2",
            quote="FOB, 1x TAE, 12.5 mM MgCl2 for the triangle and the 6HB",
        ),
        Step(
            "magnesium screen",
            None,
            note="the source folds at one magnesium, 12.5 mM; it reports no screen",
        ),
        Step("reaction volume", None, note="50 ul is this protocol's choice, not the source's"),
        Step(
            "scaffold supplier",
            "Tilibit",
            quote="the scaffolds were purchased from Tilibit Nanosystems",
        ),
        Step(
            "staple supplier",
            "Integrated DNA Technologies",
            quote="staple strands were purchased from Integrated DNA Technologies",
        ),
    ),
    anneal=(
        Step("initial denaturation hold", None, note="the ramp starts at 90 C; no hold is stated"),
        Step(
            "1",
            "90 -> 70 C at -0.2 C per 8 s",
            quote="cooling from 90 to 70 C at a rate of -0.2 C/8 s",
        ),
        Step("2", "70 -> 60 C at -0.1 C per 8 s", quote="from 70 to 60 C at a rate of -0.1 C/8 s"),
        Step(
            "3", "60 -> 27 C at -0.1 C per 2 min", quote="from 60 to 27 C at a rate of -0.1 C/2 min"
        ),
        Step(
            "4",
            "to 20 C, hold until stopped",
            quote="cooling down to 20 C and stored until the program was manually stopped",
        ),
        Step("thermocycler", "ProFlex PCR system", quote="ProFlex PCR system"),
        Step(
            "total",
            "about 11.5 h (13.3 + 13.3 min + 11 h + the last step)",
            note="arithmetic from the steps above",
        ),
    ),
    gel=(
        Step("agarose", "2% (w/v) in 1x TAE + 11 mM MgCl2", quote="2% (w/v) agarose gel"),
        Step("running buffer", "1x TAE + 11 mM MgCl2", quote="1x TAE and 11 mM MgCl2"),
        Step(
            "stain",
            "ethidium bromide 0.46 ug/mL in the gel",
            quote="0.46 ug mL-1 ethidium bromide",
            note="common-techniques.md section 0 says no EtBr; SYBR Safe instead is a "
            "DEVIATION from the source -- decide with the lab before pre/ is committed",
        ),
        Step(
            "run",
            "90 V constant, 45 min, on an ice bath",
            quote="run for 45 min ... constant voltage of 90 V ... while kept on an ice bath",
        ),
        Step(
            "sample",
            "20 ul at 5 nM origami + 4 ul loading dye",
            quote="volume of 20 uL, c_origami = 5 nM",
        ),
        Step(
            "loading dye",
            "0.0083% bromophenol blue, 0.0083% xylene cyanol, 40% sucrose",
            quote="0.0083% bromophenol blue, 0.0083% xylene cyanol, 40% sucrose",
        ),
        Step("ladder", None),
        Step("imaging", "UV, Bio-Rad Gel Doc XR+", quote="visualized by ultraviolet light"),
    ),
    purification=(
        Step("method", "PEG precipitation", quote="PEG precipitation buffer"),
        Step("dilute first", "4-fold with 1x FOB", quote="diluted 4-fold with 1x FOB"),
        Step(
            "PEG buffer, mixed 1:1",
            "15% PEG 8000, 1x TAE, 505 mM NaCl",
            quote="15% PEG 8000, 1x TAE, 505 mM NaCl",
        ),
        Step(
            "spin",
            "14,000 g, 30 min, room temperature",
            quote="centrifuged at 14 000g for 30 min at room temperature",
        ),
        Step(
            "resuspend",
            "1x FOB to 0.25-1x the initial reaction volume",
            quote="resuspended in 1x FOB to 0.25-1x of the initial reaction volume",
        ),
        Step(
            "redissolve",
            "overnight, 30 C, shaking 600 rpm",
            quote="overnight at 30 C under continuous shaking at 600 rpm",
        ),
    ),
    deposition=(
        Step(
            "sample",
            "20 ul at about 1-2 nM",
            quote="20 uL of the sample solution (c_origami ~ 1-2 nM)",
        ),
        Step("dilution buffer", None, note="the source deposits 'the sample solution'"),
        Step(
            "mica",
            "freshly cleaved, 15 x 15 mm, grade V1",
            quote="freshly cleaved mica surface (15 mm x 15 mm, grade V1",
        ),
        Step(
            "incubate", "1 min, room temperature", quote="incubated for 1 min at room temperature"
        ),
        Step(
            "rinse",
            "3 x 100 ul deionized water",
            quote="washed three times with 100 uL of deionized water",
        ),
        Step("dry", "direct nitrogen flow", quote="dried thoroughly using direct nitrogen flow"),
        Step(
            "AFM",
            "Bruker Dimension Icon, ScanAsyst in Air, ScanAsyst-Air probes",
            quote="Dimension Icon AFM (Bruker) using ScanAsyst in Air Mode",
        ),
        Step(
            "scan size and pixels",
            None,
            note="E10 asks for 2 x 2 um at 1024 px, from its own synthetic calibration",
        ),
    ),
    caveats=(
        "The source's object is a different six-helix bundle on the same scaffold. Its "
        "conditions are the closest validated starting point found, not a validation of "
        "this design; the gel is what validates the fold here.",
        "The source reports no magnesium screen. E10 folds at the source's 12.5 mM; any "
        "other magnesium is a choice the experimentalist makes and records before pre/ is "
        "committed.",
        "TAE contains EDTA, which binds magnesium one to one; record the nominal MgCl2, as for E1.",
        "E1's magnesium does NOT carry over: E1 folds a different object in a different "
        "buffer (Tris-EDTA). E10 depends on E1 for technique and the reference height only.",
    ),
)

#: Parts whose folding protocol is a publication's, taken whole.
PUBLISHED: Final = {"bundle": BUNDLE_ENLUND_2024}


def published_protocol(part: str) -> PublishedProtocol | None:
    return PUBLISHED.get(part)
