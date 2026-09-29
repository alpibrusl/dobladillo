# dobladillo

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
uv sync --extra dev --extra design --extra imaging --extra mcp
```

The extras, if you want less (generated from `pyproject.toml`):

<!-- generated:extras -->
| extra | for | installs |
|---|---|---|
| `design` | scadnano, the design data model: build, lint, order, simulate | `scadnano==0.21.1` |
| `imaging` | read and measure AFM scans; `calibrate` | `scipy>=1.11`, `afmreader==0.0.7`, `scikit-image>=0.22` |
| `mechanics` | indentation mechanics; declares a private dependency it cannot install | nothing (see pyproject.toml) |
| `dev` | tests, lint, format and type checks | `pytest>=8.0`, `ruff>=0.6`, `mypy>=1.11`, `scipy>=1.11` |
| `mcp` | the MCP server (`dobladillo mcp`) | `mcp>=2.2,<3` |
<!-- /generated:extras -->

oxDNA is not a Python dependency: point `$OXDNA` at a CPU build, and on
Apple Silicon `$OXDNA_METAL` at the pinned Metal fork (see `AGENTS.md`,
rule 4).

## Use

Every command, generated from the code by `uv run dobladillo readme` (a test
fails if this list drifts from what the tool accepts). Each takes `--help` and
`--json`; arguments in CAPITALS are required, `[BRACKETED]` ones optional.

<!-- generated:commands -->
**(top level)**

| command | what it does |
|---|---|
| `dobladillo analyse RUN_DIR` | Turn a finished run into observables with experimental counterparts. |
| `dobladillo benchmark` | Score routing and shape prediction against known answers. Exits non-zero on a miss. |
| `dobladillo bracket` | The latch ladder that guarantees Stage 0 lands in its measurement window. |
| `dobladillo compare PART` | Design against simulation against measurement: the closed loop. |
| `dobladillo dashboard` | Generate the shareable board. Reads every figure from the toolchain. |
| `dobladillo describe` | Emit the command surface, for an agent to read instead of `--help`. |
| `dobladillo export PART` | Write a local archive of a part in Nanobase's layout. Never uploads. |
| `dobladillo export-check ARCHIVE` | Validate an export archive against its layout. Exits non-zero if it departs. |
| `dobladillo folding-window PART` | Where this design should fold: staple melting temperatures, weak staples, a screen. |
| `dobladillo geometry` | Show the geometry constants, and where this project disagrees. |
| `dobladillo lint DESIGN_FILE` | Check a design against the rules. Exits non-zero on a hard violation. |
| `dobladillo mcp` | Serve the parts, rules, queue and experiments to an agent over MCP (stdio). |
| `dobladillo predict TARGET` | Predict a design's equilibrium bend and twist in seconds (beam model). |
| `dobladillo readme` | Rewrite the README's generated sections (commands, extras, MCP tools) from the code. |
| `dobladillo rules` | List the design rules, and what is knowingly not checked. |
| `dobladillo scaffolds` | List the scaffold strands available, asked of scadnano directly. |
| `dobladillo skill` | Print a SKILL.md for this tool, generated from its own commands. |
| `dobladillo twist-pair` | The matched pair that tests whether the twist correction does anything. |
| `dobladillo version` | Print the version. |

**afm**

| command | what it does |
|---|---|
| `dobladillo afm measure SCAN` | Flatten, segment, measure and classify a scan, and report the yield. |
| `dobladillo afm read SCAN` | Read a scan and report what it is. Measures nothing. |
| `dobladillo afm synthetic` | Write a synthetic scan of known contents, as a .gsf. |

**build**

| command | what it does |
|---|---|
| `dobladillo build bundle` | A six-helix bundle on the honeycomb lattice. |
| `dobladillo build hinge` | A bistable hinge: two arms, a single-stranded joint, and a latch. |
| `dobladillo build pair` | Both arms of the twist pair, written side by side. |
| `dobladillo build rectangle` | A Rothemund-style rectangle on the square lattice. |

**calibrate**

| command | what it does |
|---|---|
| `dobladillo calibrate drift FRAMES...` | Drift between frames: displacement per frame and a velocity with its standard error. |
| `dobladillo calibrate lateral SCANS...` | The scanner's X and Y scale and skew, from reference particles at random angles. |
| `dobladillo calibrate reference` | Write the calibration tile's reference geometry: its marks, in nm, with uncertainty. |
| `dobladillo calibrate tip SCAN` | The tip, reconstructed blind from the scan, its apex radius, and the resolution it allows. |

**experiment**

| command | what it does |
|---|---|
| `dobladillo experiment assembly DIRECTORY` | Count assembly states per sample, against the controls. Writes post/assembly.json. |
| `dobladillo experiment check DIRECTORY` | What is missing, and whether the results can be believed. |
| `dobladillo experiment compare-arms DIRECTORY` | Compare two blinded arms by flat fraction, and state the verdict both ways. |
| `dobladillo experiment folding-screen DIRECTORY` | E11: yield against temperature and time, from gel band intensities. |
| `dobladillo experiment new SLUG` | Scaffold an experiment, with its predictions recorded up front. |
| `dobladillo experiment pattern DIRECTORY` | Read the designed pattern off every well-formed particle, and say which way round. |
| `dobladillo experiment report DIRECTORY` | Measure the scans and compare them against what was predicted. |
| `dobladillo experiment rods DIRECTORY` | Trace every rod, check its length, and ask whether the population is straight. |

**lab**

| command | what it does |
|---|---|
| `dobladillo lab order PART` | Plates, pooling map and cost for ordering a part's staples. |
| `dobladillo lab protocol PART` | The folding protocol sheet, with the magnesium screen laid out. |

**sim**

| command | what it does |
|---|---|
| `dobladillo sim bundle PART` | Write a self-contained oxDNA job bundle. Runs nothing. |
| `dobladillo sim check RUN_DIR` | Is this run something whose numbers mean anything? Exits non-zero if not. |
| `dobladillo sim enqueue BUNDLES...` | Add bundles to the queue. Starts nothing; `sim run` does that. |
| `dobladillo sim run` | Run queued bundles, several at a time. Blocks; launch it with nohup. |
| `dobladillo sim status` | What the queue is doing. |
| `dobladillo sim sweep` | Build one hinge bundle per joint length, and queue them. |
<!-- /generated:commands -->

### For agents

There are three ways in, and they say the same thing: the skill and the MCP
server are both generated from, or run, the CLI below.

The lists below are generated from the code; the prose around them is not.

**1. The CLI with `--json`.** Every command takes `--json`, and with it
stdout carries exactly one JSON object: no banners, no colour, no progress.
Failures are JSON too, with a stable `error.kind`, and exit non-zero, so a
caller never has to tell a traceback from a result. Warnings go to stderr.
Start with `dobladillo describe --json`: the whole command surface --
commands, options, types, defaults -- generated by walking the app, so it
cannot fall out of date.

```bash
uv run dobladillo describe --json
uv run dobladillo build bundle --json | jq .scaffold
```

**2. The skill (Claude Code).** [`SKILL.md`](SKILL.md) is generated from the
command surface, and a test fails if the committed copy is stale. Claude Code
picks it up from a skills directory; install it for yourself with

```bash
mkdir -p ~/.claude/skills/dobladillo && uv run dobladillo skill > ~/.claude/skills/dobladillo/SKILL.md
```

or for everyone working in this checkout, as a project skill, with
`mkdir -p .claude/skills/dobladillo && uv run dobladillo skill > .claude/skills/dobladillo/SKILL.md`.
Regenerate it after the CLI changes.

**3. The MCP server.** `dobladillo mcp` serves typed tools over stdio (needs
the `mcp` extra). Each tool runs the matching CLI command with `--json`, so a
tool cannot say anything the command would not, and a refusal arrives with the
same `error.kind`. Register it with Claude Code:

```bash
claude mcp add dobladillo -- uv --directory /path/to/dobladillo run dobladillo mcp --root experiments
```

Add `--scope project` to share it through a `.mcp.json` in the checkout. Any
other MCP client takes the same command:

```json
{"mcpServers": {"dobladillo": {"command": "uv",
  "args": ["--directory", "/path/to/dobladillo", "run", "dobladillo", "mcp", "--root", "experiments"]}}}
```

The tools (generated from the running server). Experiment folders and scan
files are addressed relative to `--root`, and anything that resolves outside
it is refused.

<!-- generated:mcp-tools -->
| tool | what it returns |
|---|---|
| `build_part` | A part's accounting: helices, scaffold, staples, dimensions. |
| `calibrate_drift` | Drift between frames of the same field: per-frame displacement and a velocity with its standard error. |
| `calibrate_lateral` | Scanner x/y scale and skew, with k=2 intervals, from scans of reference particles at random angles. |
| `calibrate_reference` | The calibration tile's reference geometry: mark positions in nm with their relative uncertainty. |
| `calibrate_tip` | Blind tip reconstruction (an outer bound), its apex radius and the lateral resolution it allows. |
| `describe` | Every CLI command, its options and the conventions of its JSON output. |
| `experiment_assembly` | E9: monomer, dimer and larger fractions per sample, against the A-alone and B-alone controls. |
| `experiment_check` | What an experiment folder is missing, and whether its record holds. |
| `experiment_compare_arms` | E2's blinded two-arm comparison: fraction flat per arm, verdict both ways. |
| `experiment_folding_screen` | E11: folded yield against constant temperature and time, from the gel quantification, beside the predicted folding window. |
| `experiment_list` | Experiment folders under the root, by name. |
| `experiment_pattern` | E8: read the designed pattern off every well-formed particle, and which way round it lies. |
| `experiment_report` | Measure every raw scan, compare against the recorded prediction, write post/. |
| `experiment_rods` | E10: trace every rod, check its tip-corrected length, and tell a straight but flexible bundle from a systematically curved one. |
| `lint_part` | Check a part against every design rule, crossover phasing included. |
| `predict_shape` | Predicted bend and twist from the beam model, in seconds. |
| `queue_status` | What the oxDNA queue is doing: each job's state, stage and progress. |
| `rules` | The design rules, and what is knowingly not checked. |
<!-- /generated:mcp-tools -->

**What no route will do.** An agent may analyse, check and report. No tool
orders oligos, creates an experiment (pre-registration), writes a gate, or
touches `during/raw/`: those are the experimentalist's acts
(`experiments/AGENTS.md`). These commands exist in the CLI and are kept out of
the MCP server on purpose (generated from `mcp_server.FORBIDDEN_COMMANDS`; a
test checks no tool wraps them):

<!-- generated:mcp-forbidden -->
- `lab order`: an oligo order is a purchase, a human gate.
- `experiment new`: creating an experiment is pre-registration, the experimentalist's act.
<!-- /generated:mcp-forbidden -->

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
