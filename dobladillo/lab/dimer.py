"""The order for E9's rectangle dimer: E1's plates, plus 44 oligos.

A and B each use 198 of E1's 220 staples unchanged and replace the other 22,
the edge staples, with extended ones. So the order is two small plates of
extras, and the pooling instructions say which E1 wells to take and -- the
part that goes wrong -- which to leave out. See `lab.shared_pool`.

Each component's pool is made exactly like E1's: equal volumes of 220 wells at
100 uM, so every staple is at 455 nM and E1's pipetting table applies to A
and B unchanged. Only where the 22 edge wells come from differs.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

from dobladillo import _scadnano as ad
from dobladillo.lab import plates as lab
from dobladillo.lab.shared_pool import SharedPool, label_extras, shared_pool, write_labelled_order

if TYPE_CHECKING:
    from dobladillo.parts.dimer import Component, Dimer, EdgeStaple

#: What `lab order dimer` and `experiment new --part dimer` call the order.
ORDER_NAME: Final = "dimer"

#: Staple concentration in each plate well, as ordered (common-techniques s1).
WELL_UM: Final = 100.0

POOL_WARNING: Final = (
    "Do NOT fold A or B from E1's pooled tube. It contains E1's plain edge staples, "
    "which compete with the extended ones for the same scaffold sites and leave part "
    "of the mating edge blunt. Make a new pool per component from E1's plates, "
    "skipping the listed wells, plus that component's extras plate."
)


def extra_name(staple: EdgeStaple) -> str:
    """`A_sticky_h01_end`: component, role, the helix its 3' end is on, edge."""
    role = {"sticky": "sticky", "passivated": "polyT", "plain": "plain"}[staple.role]
    return f"{staple.component}_{role}_h{staple.helix_3p:02d}_{staple.edge}"


def _extension_strands(component: Component) -> list[Any]:
    """The component's strands that carry an extension, bottom helix first."""
    found = []
    for strand in ad.staples(component.design):
        if any(not hasattr(d, "helix") for d in strand.domains):
            found.append(strand)
    by_sequence = {s.dna_sequence: s for s in found}
    ordered = [by_sequence[s.sequence] for s in component.extra]
    if len(ordered) != len(found):
        raise AssertionError(
            f"{component.name}: {len(found)} extended strands in the design but "
            f"{len(component.extra)} recorded as extra"
        )
    return ordered


def pool_plan(dimer: Dimer) -> tuple[SharedPool, lab.PlateLayout]:
    """E1's plate layout, and what each component takes from it."""
    layout = lab.name_and_assign_wells(dimer.base.design)
    pool = shared_pool(
        "rectangle",
        layout,
        {"A": dimer.a.staple_sequences, "B": dimer.b.staple_sequences},
    )
    return pool, layout


def order(dimer: Dimer, *, directory: Path | None = None) -> dict[str, Any]:
    """The order and pooling plan; with `directory`, the files and a manifest.

    Returns a JSON-ready payload. Every extra is listed with its role, so the
    order says which staples are extra and why each one is.
    """
    pool, _ = pool_plan(dimer)
    components: dict[str, Any] = {}
    files: dict[str, str] = {}
    problems: list[lab.OrderProblem] = []
    for component in (dimer.a, dimer.b):
        variant = pool.variant(component.name)
        if sorted(variant.extra) != sorted(s.sequence for s in component.extra):
            raise AssertionError(
                f"{component.name}: the staples missing from E1's plates are not the "
                "extended staples; the component differs from E1 somewhere else"
            )
        strands = _extension_strands(component)
        placed = label_extras(
            strands,
            names=[extra_name(s) for s in component.extra],
            plate_prefix=f"dimer{component.name}-plate",
        )
        n_pool = variant.staples
        components[component.name] = {
            "mating_edge": component.mating_edge,
            "outer_edge": component.outer_edge,
            "pool": {
                "staples": n_pool,
                "from_e1_plates": len(variant.from_base),
                "from_extras_plate": len(variant.extra),
                "each_staple_in_pool_nm": round(WELL_UM * 1000.0 / n_pool, 1),
                "how": "equal volume of every listed well, as for E1's pool",
            },
            "skip_e1_wells": variant.as_dict()["skip_base_wells"],
            "extra": [
                {
                    "name": name,
                    "plate": plate,
                    "well": well,
                    **{
                        k: v
                        for k, v in spec.as_dict().items()
                        if k in ("role", "edge", "helix_3p", "pair", "sequence", "length_nt")
                    },
                    "why": (
                        "sticky end: joins A to B"
                        if spec.role == "sticky"
                        else "4-T tails: stop this edge stacking (Rothemund 2006 S5.7)"
                    ),
                }
                for spec, (name, plate, well) in zip(component.extra, placed, strict=True)
            ],
        }
        if directory is not None:
            written, found = write_labelled_order(
                component.design,
                directory=directory,
                name=f"{ORDER_NAME}-{component.name.lower()}_extra",
            )
            problems += found
            files.update({f"{component.name}_{k}": str(v) for k, v in written.items()})

    core = [{"plate": w.plate, "well": w.well, "staple": w.name} for w in pool.core]
    payload: dict[str, Any] = {
        "part": ORDER_NAME,
        "design_sha256": dimer.design_hash(),
        "base": {
            "part": "rectangle",
            "plates": "E1's order: experiments/2026-09-22-rectangle-afm/pre/order/"
            "rectangle_plates.xlsx, or `dobladillo lab order rectangle`",
            "wells": pool.base_wells,
        },
        "core_wells": len(core),
        "extra_oligos": sum(len(c.extra) for c in (dimer.a, dimer.b)),
        "extra_nt": sum(len(s.sequence) for c in (dimer.a, dimer.b) for s in c.extra),
        "components": components,
        "core": core,
        "warning": POOL_WARNING,
    }
    cost = lab.DEFAULT_PRICE_PER_BASE * payload["extra_nt"]
    payload["cost"] = {
        "extra_nt": payload["extra_nt"],
        "price_per_base": lab.DEFAULT_PRICE_PER_BASE,
        "estimated_total": round(cost, 2),
        "assumptions": [
            "extras only: E1's 198 shared staples are already on its plates",
            f"{lab.DEFAULT_PRICE_PER_BASE} per base, plate format, list price",
        ],
    }
    payload["problems"] = [p.as_dict() for p in problems]
    if directory is not None:
        from dobladillo import provenance

        pools = directory / f"{ORDER_NAME}_pools.json"
        record = {k: v for k, v in payload.items() if k != "problems"}
        pools.write_text(json.dumps(record, indent=2) + "\n")
        files["pools"] = str(pools)
        manifest = provenance.write_order_manifest(
            directory,
            name=ORDER_NAME,
            part=ORDER_NAME,
            design_hash=payload["design_sha256"],
            files=[Path(p) for p in files.values()],
        )
        payload["files"] = files
        payload["manifest"] = str(manifest)
    payload["valid"] = not problems
    return payload
