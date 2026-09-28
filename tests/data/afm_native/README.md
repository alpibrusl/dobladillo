# Native AFM files, from AFMReader's own test suite

**These are not partner files.** Nobody imaged anything for this project to
produce them. They are the instrument files AFMReader tests itself against,
copied unchanged so this project's adapter is tested against real vendor
formats rather than against files it wrote itself. What they show is whatever
the AFMReader team imaged; no test here depends on the sample, only on the
file format, the pixel size and the height units.

The issue asking for native formats (#7) also asks for a real partner file
with a known pixel size. That part is still open: there are no partner files
yet.

| file | format | pixel size, nm | stated in |
|---|---|---|---|
| `sample_0.jpk` | JPK NanoWizard `.jpk`, `height_trace` channel, 256 x 256 | 1.2770176335964876 | AFMReader `tests/test_jpk.py` |
| `sample_0.jpk-qi-image` | JPK QI image, `height_trace`, 100 x 100 | 4.999999999999986 | AFMReader `tests/test_jpk.py` |
| `sample_0.stp` | WSXM `.stp`, 512 x 512, header `X Amplitude: 500 nm` | 0.9765625 | AFMReader `tests/test_stp.py`; also 500 / 512 from the header |
| `sample_0.top` | WSXM `.top` of the **same acquisition** as `sample_0.stp` | 0.9765625 | AFMReader `tests/test_top.py` |

`sample_0.top` is here as evidence, not as a supported input. AFMReader 0.0.7
rescales `.top` heights to the integer part of the header's `Z Amplitude`
(59.7449 nm is read as 59), which the `.stp` of the same acquisition shows: its
height range is 59.7449 nm exactly. `tests/test_readers.py` pins that, so the
day AFMReader fixes it the test says so and `.top` can be let in.

## Source and licence

- Repository: https://github.com/AFM-SPM/AFMReader, `tests/resources/`
- Copied at commit `caeecf32ac5900f99c0dfee4b49d27ba4ca0fd77`; all four files
  are byte-identical at tag `v0.0.7`, the version pinned in `pyproject.toml`.
- Licence: the repository's `COPYING` is the GNU GPL v3; its `CITATION.cff`
  says GPL-3.0-or-later. The files carry no separate licence, so they are
  under the repository's. GPL-3.0 is in EUPL-1.2's compatibility appendix.
  Like AFMReader itself, this matters the day the repository is distributed.

SHA-256:

```
7b1945c97936f005446b2d75be49643a364ecaf8798a2d2b97b092d40f21de2e  sample_0.jpk
af04539519c8a8a7d498148af7f61288d8f4434a5d8a750a2f47bff999c5d682  sample_0.jpk-qi-image
977569f7fdbdc5de92fd8b2172c9ff8fd38f3b8df6de0b4f95a547a8b12da8c5  sample_0.stp
861bc8ab110d9cb820971b23df77fffa1e746fe81464890e5f8787e2e291b174  sample_0.top
```

AFMReader's larger fixtures -- Bruker `.spm` (32 MB), Asylum `.ibw` (8 MB),
Gwyddion `.gwy` (16 MB) -- are not copied. `tests/test_readers.py` reads them
from a local AFMReader checkout when `AFMREADER_RESOURCES` points at its
`tests/resources` directory, and skips otherwise.
