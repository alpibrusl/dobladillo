# dobladilo

A scriptable toolchain for DNA origami **bricks**: reusable parts with typed
interfaces, composed into larger assemblies and simple stochastic mechanisms,
with predicted properties, everything the lab needs to build them, and an
image-ingest path that closes the loop between prediction and experiment.

The gap it fills: existing tools design single structures (caDNAno, scadnano,
ATHENA) or simulate them (oxDNA, CanDo). None offers a parts library with
characterised, composable interfaces and measured assembly yields.

Design document: `docs/DESIGN.pdf`. Roadmap status: `docs/STATUS.md`.
Working rules for coding agents: `AGENTS.md`.

## Install

```bash
uv sync --extra dev --extra design
```

## Principles

- **Wrap, don't rewrite.** scadnano is the design data model, oxDNA the
  physics, NUPACK/ViennaRNA the thermodynamics.
- **Everything is code.** A design is a Python script producing a
  deterministic artefact. No hand-edited design files in the repo.
- **Every prediction carries a comparison hook.** Any simulated observable
  must have a defined experimental counterpart.
- **Reproduce before inventing.** Each tier starts by reproducing a published
  result.
- **Human gates are explicit.** The toolchain never assumes a simulation was
  run or a structure folded; it consumes result files placed in `data/`.
