# Our own designs, kept as test fixtures

Designs this project generated and has since replaced, kept because oxDNA
measured them. They are reference data now, not parts. Trajectories are not
committed (776 MB each).

| file | what it is | oxDNA result (1e6 steps, 200 frames, 20 °C, 0.5 M) |
|---|---|---|
| `bundle_21_21.sc` | first six-helix bundle: one 21-nt span for every pair | arc, radius 269 ± 11 nm, sagitta 50.2 nm, bend-direction order parameter 0.993 |
| `bundle_28_14.sc` | second: 28/14 spans | arc, radius 347 ± 51 nm, sagitta 49.9 nm, order parameter 0.995 |

Both are misphased (`routing.azimuth`: 62° and 44° rms against 19–22° for
published designs). See `docs/BUNDLE_BEND.md`.

They serve two tests. `crossover_azimuth` must reject them. The beam model
must predict them straight: it cannot see misphasing, and
`tests/test_beam.py` pins that blind spot so it stays documented.
