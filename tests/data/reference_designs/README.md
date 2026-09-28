# Reference designs

Designs this project did not write, used to calibrate and test
`dobladillo.routing.azimuth`. A measure checked only against our own designs
would share their mistakes.

| file | source | licence |
|---|---|---|
| `Nature09_monolith.json` | caDNAno 2.5, `cadnano/tests/data/`, commit `ce6ff019b8` — Douglas et al., *Nature* 2009 | caDNAno licence (MIT-style) |
| `Nature09_squarenut.json` | same | same |
| `6_helix_bundle_honeycomb.sc` | scadnano-python-package, `examples/output_designs/`, commit `e7f2dcd39f` | MIT |
| `16_helix_origami_rectangle.sc` | same — square lattice, **no** twist-correcting deletions | MIT |
| `16_helix_origami_rectangle_no_twist.sc` | same — square lattice, **with** deletions, so no residual twist | MIT |

Note the scadnano naming: `_no_twist` is the file that *has* deletions.
