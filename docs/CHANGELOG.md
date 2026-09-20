# Changelog

## Unreleased

- Project skeleton: package layout per DESIGN.md section 6, `pyproject.toml`,
  ruff/pytest/mypy, CI.
- `constants.py`: geometry, lattice periodicity, scaffold lengths, staple
  rules, wet-lab defaults and the oxDNA salt proxy, each with its source.
- `units.py`: the single place an oxDNA length unit is converted.
- Tests pin the relationships between constants, not just their values.
- Design document transcribed as `docs/DESIGN.md`. Its collaborator section is
  omitted: that is strategy and personal information. Published work stays
  cited normally, including papers by people named there.
- Q1 complete. `_scadnano.py` adapter; `parts.rectangle` (square lattice,
  twist-corrected) and `parts.bundle` (honeycomb six-helix ring); design
  scripts; exports to scadnano, cadnano v2 and oxView.
- CLI with a `--json` mode and a `describe` command, so an agent can discover
  and call it without scraping `--help`.
- Q2 complete. Six composable design-rule checks with structured findings,
  `dobladilo lint` and `dobladilo rules`. Running them found a real defect in
  the rectangle, now fixed.
