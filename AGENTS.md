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
   run` execute bundles several at a time on whatever machine you are on. A
   CUDA build is faster, not required.
5. **Record units and conditions** (salt, temperature, model version) in the
   metadata of every result file. A prediction made at one proxy salt is not
   comparable to one made at another.
6. **Physical constants and rule thresholds live in `dobladillo/constants.py`**,
   each with its literature citation. Nowhere else.
7. **Small, PR-sized changes.** Update `docs/CHANGELOG.md` and
   `docs/STATUS.md`.
8. **If a domain rule conflicts with a published reference design, flag it**
   rather than silently relaxing the rule.

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
