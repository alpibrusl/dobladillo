# Working rules for an implementing agent

Taken from DESIGN.md section 11. Read `docs/DESIGN.pdf` before starting; this
file is the short form, not a replacement.

1. **Work tier by tier, item by item, in the order given.** Do not start an
   item whose dependencies carry an unmet human gate (HG); pick the next
   independent one.
2. **Never rely on a remembered API.** Before using scadnano, oxpy, oat,
   NUPACK or ViennaRNA, read its current docs or source. scadnano's API drifts;
   every call goes through an adapter in `dobladillo/_scadnano.py` so the drift
   has one place to be absorbed.
3. **Every module ships with tests.** Every design script is deterministic
   (fixed seeds) and its key outputs are pinned in tests.
4. **Never fabricate simulation or experimental results.** If `data/` lacks
   what an item needs, produce the job bundle or request sheet and stop with a
   clear note of what the human must provide. Folding and imaging happen in a
   partner lab and nothing here substitutes for them. Simulation is no longer
   a gate: oxDNA's CPU backend is single-threaded, so `sim sweep` and `sim
   run` execute bundles several at a time on whatever machine you are on. On
   Apple Silicon, bundles default to the Metal backend (~100x the CPU) when
   `$OXDNA_METAL` points at the pinned fork's binary (`sim.jobs.METAL_FORK`);
   otherwise CPU. CUDA is used only when asked for.
5. **Record units and conditions** (salt, temperature, model version) in the
   metadata of every result file. A prediction made at one proxy salt is not
   comparable to one made at another.
6. **Physical constants and rule thresholds live in `dobladillo/constants.py`**,
   each with its literature citation. Nowhere else.
7. **Small, PR-sized changes.** Update `docs/CHANGELOG.md` and
   `docs/STATUS.md`.
8. **If a domain rule conflicts with a published reference design, flag it**
   rather than silently relaxing the rule.

## Using the tool, and keeping its agent interfaces in step

How to use the tool as an agent (the JSON CLI, the skill, the MCP server) is
in the README, *For agents*. When you change the tool:

- **Every command takes `--json`** and prints exactly one JSON object on
  stdout. A failure is `{"error": {"kind": ..., "message": ...}}` with a
  non-zero exit. A new command follows the same contract (`Emitter` in
  `cli.py`). Never let a traceback or a banner reach stdout.
- **Regenerate `SKILL.md`** after any change to the command surface:
  `uv run dobladillo skill > SKILL.md`. A test fails when the committed copy
  is stale.
- **Expose an analysis command over MCP** when an agent would call it: add a
  tool to `dobladillo/mcp_server.py` that runs the CLI command with `--json`
  and returns its payload. Never reimplement the command's logic there. Take
  folders and files as names relative to the server's root, through its
  `folder`/`scan_file` helpers, which refuse anything outside it.
- **Never expose a human gate.** No tool may order oligos, create an
  experiment, write a gate, or write under `during/raw/`.
  `FORBIDDEN_COMMANDS` lists them, and `tests/test_mcp_server.py` checks that
  no tool wraps one.
- **To check a change as CI does**, install the same extras
  (`uv sync --extra dev --extra design --extra imaging --extra mcp`) and run
  the suite with `GITHUB_ACTIONS=true`: the CLI's output changes under it.

## Two standing prohibitions

- **Do not contact anyone, and do not draft outreach.** The design document's
  section 9 names real researchers and sketches how and when to approach them.
  It is context for prioritisation, not a task list, and it says so
  explicitly. That section is deliberately **not in this repository** -- §9a is
  the placeholder where it would sit -- so nothing here should be read as a
  licence to act on it, and nothing here should reproduce it.
- **Keep this repository private.** Named collaborators are fine; public is
  not. Published literature is citable (see the design document's section 12);
  specific collaborations are not named anywhere.
