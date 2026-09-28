# Epic 4 — AFM ingest

[Issue #4](https://github.com/alpibrupa/dobladillo/issues/4). **Done.** No
experiment of its own; it is what makes E1, E2, E3 and E7 measurable.

## What it is

`dobladillo afm read | measure | synthetic`. Native instrument files --
Bruker `.spm`/`.001`, JPK `.jpk`, Asylum `.ibw`, Gwyddion `.gwy`, WSXM `.stp` --
are read directly through AFMReader (issue #7). **Gwyddion Simple Field**
(`.gsf`) is still read, and is the way in for any other instrument.

## Why not native readers (superseded)

*Superseded by #7: AFMReader reads the plain topography scans this section
says nothing could. What follows is kept as the record of why the export step
existed; the reasoning about pyfmreader still holds.*

This epic was scoped on a claim that turned out to be wrong.
`alpibrupa/nanoindent`'s `pyfmreader` was supposed to solve the file formats.
It does not: `loadJPKimg` accepts `jpk-force-map` and `jpk-qi-data` and returns
None otherwise, and `loadNANOSCimg` reads force-volume offsets out of a
Nanoscope header. Both extract the topography recorded *alongside a force
volume* — not a plain tapping-mode scan, which is what imaging origami on mica
produces. That repository also ships no sample files, so a parser written
against those formats could not have been tested against anything.

Gwyddion reads every native format a partner is likely to own and exports GSF,
which is fully specified. One reader, testable exactly, instead of several
written hopefully. Native force maps still go through pyfmreader when it is
installed.

## What to do with it before any real sample

`dobladillo afm synthetic --out s.gsf --part <part>` writes a scan of known
contents. Send it to the partner, ask what they measure from it, and a
disagreement is located before it can be attributed to the chemistry. It costs
nothing and it is the single cheapest de-risking step available for E1.

## The one thing that is still open

**A flatness observable.** `imaging.particles` measures length, width, height
and angle. It does not measure curvature across a sheet, and E2 — the twist
pair — is entirely a flatness comparison. The simulation side has
`planarity_nm`; the imaging side has no counterpart.

That is the gap between E2 being designed and E2 being runnable, and it
belongs to this epic rather than to the design side.
