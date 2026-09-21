---
name: dobladillo
description: "Design, simulate and order DNA origami bricks. Commands: build, lint, lab, sim, analyse…"
---

# dobladillo

> Auto-generated skill file for dobladillo v0.0.1
> Re-generate with: `dobladillo skill > SKILL.md`

A scriptable toolchain for DNA origami bricks: design a structure, check it
against the design rules, produce what the lab needs to order and fold it,
bundle an oxDNA job, and turn a finished run into observables that have
experimental counterparts.

## Available commands

- `dobladillo afm measure` — Flatten, segment, measure and classify a scan, and report the yield.
- `dobladillo afm read` — Read a scan and report what it is. Measures nothing.
- `dobladillo afm synthetic` — Write a synthetic scan of known contents, as a .gsf.
- `dobladillo analyse` — Turn a finished run into observables with experimental counterparts.
- `dobladillo bracket` — The latch ladder that guarantees Stage 0 lands in its measurement window.
- `dobladillo build bundle` — A six-helix bundle on the honeycomb lattice.
- `dobladillo build hinge` — A bistable hinge: two arms, a single-stranded joint, and a latch.
- `dobladillo build pair` — Both arms of the twist pair, written side by side.
- `dobladillo build rectangle` — A Rothemund-style rectangle on the square lattice.
- `dobladillo compare` — Design against simulation against measurement: the closed loop.
- `dobladillo dashboard` — Generate the shareable board. Reads every figure from the toolchain.
- `dobladillo describe` — Emit the command surface, for an agent to read instead of `--help`.
- `dobladillo experiment check` — What is missing, and whether the results can be believed.
- `dobladillo experiment new` — Scaffold an experiment, with its predictions recorded up front.
- `dobladillo experiment report` — Measure the scans and compare them against what was predicted.
- `dobladillo geometry` — Show the geometry constants, and where this project disagrees.
- `dobladillo lab order` — Plates, pooling map and cost for ordering a part's staples.
- `dobladillo lab protocol` — The folding protocol sheet, with the magnesium screen laid out.
- `dobladillo lint` — Check a design against the rules. Exits non-zero on a hard violation.
- `dobladillo rules` — List the design rules, and what is knowingly not checked.
- `dobladillo scaffolds` — List the scaffold strands available, asked of scadnano directly.
- `dobladillo sim bundle` — Write a self-contained oxDNA job bundle. Runs nothing.
- `dobladillo sim check` — Is this run something whose numbers mean anything? Exits non-zero if not.
- `dobladillo sim enqueue` — Add bundles to the queue. Starts nothing; `sim run` does that.
- `dobladillo sim run` — Run queued bundles, several at a time. Blocks; launch it with nohup.
- `dobladillo sim status` — What the queue is doing.
- `dobladillo sim sweep` — Build one hinge bundle per joint length, and queue them.
- `dobladillo skill` — Print a SKILL.md for this tool, generated from its own commands.
- `dobladillo twist-pair` — The matched pair that tests whether the twist correction does anything.
- `dobladillo version` — Print the version.

Every command accepts `--json`. Start with `dobladillo describe --json`, which
emits the whole surface with options, types and defaults.

## Working rules

These matter more than the command list. The toolchain is built so that a
mistake here is refused rather than absorbed, but an agent that fights the
refusals can still produce nonsense.

1. **Never present a generated artefact as a result.** A job bundle is not a
   simulation; an order file is not a folded sample. Every bundle's metadata
   says `status: not run`, and `analyse` refuses a run that has not passed
   `sim check`. Do not pass `--allow-test-mode` to get a number.
2. **Every command takes `--json`.** Use it. stdout is then exactly one JSON
   object, failures included, with a stable `error.kind` and a non-zero exit.
3. **Conditions travel with numbers.** oxDNA2 has no explicit magnesium, so a
   prediction made at one proxy salt is not comparable to one made at another,
   nor directly to a measurement in a magnesium buffer. Never join two
   observables without checking their conditions.
4. **Respect the human gates.** Folding and imaging happen in a lab, and no
   amount of software substitutes for them. If `data/` lacks what a task
   needs, produce the bundle or request sheet and stop with a clear note of
   what is owed. Simulation is no longer one of these gates: oxDNA's CPU
   backend is single-threaded, so `sim sweep` and `sim run` execute bundles
   several at a time on whatever machine you are on. A CUDA build is faster,
   not required.
5. **Physical constants live in `dobladillo/constants.py`**, each with its
   source. Do not inline a number; if one is wrong, change it there.
6. **Run `dobladillo lint` before anything expensive.** Hard violations block
   ordering and simulating for a reason: both cost money or days.

## Where things are

- `docs/DESIGN.md` — the design document: what this is for and why.
- `docs/STATUS.md` — roadmap state and known gaps.
- `docs/PIPELINE.md` — how design, simulation, assembly, imaging and analysis fit.
- `AGENTS.md` — the same working rules, in the repository.
