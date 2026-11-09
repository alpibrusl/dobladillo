# Pipeline proposal

How design, simulation, assembly, imaging and analysis should fit together.
This is a proposal, written after building Q1 to Q4, and it argues with the
straight-line reading of DESIGN.md section 4 in one specific way.

## It is not a chain

"Design → simulation → assembly → AFM → analysis" reads as one line, but the
middle of it is two independent branches that have to **meet**:

```
                    design artefact (one identity)
                     /                         \
        in silico   /                           \   in vitro
                   v                             v
            job bundle                    order files + protocol
                   |  [HUMAN GATE: GPU]          |  [HUMAN GATE: wet lab]
                   v                             v
            trajectory                    folded sample
                   |                             |  [HUMAN GATE: microscope]
                   v                             v
        predicted observables           measured observables
                    \                         /
                     v                       v
                          compare  ->  registry
```

The two branches only meet if both carry the conditions they were produced
under. That constraint decides most of what follows.

## Five decisions

### 1. One identity, derived from content

Every artefact references a **design id**: a hash of the scadnano design plus
the generator call that produced it. Two things both called "the rectangle"
that hash differently are different things, and the compare step must treat
them as such.

Without this the registry accumulates measurements of an unknown number of
slightly different objects. With it, "we measured the rectangle" becomes a
checkable claim.

### 2. Conditions are part of the observable, not metadata beside it

A length predicted at 0.5 M Na+ and a length measured in 12 mM Mg are **not
the same observable**. oxDNA2 has no explicit magnesium, so this mismatch is
permanent and structural, not a detail to tidy up later.

So an observable is `(design_id, name, value, uncertainty, conditions)`, and
`compare` joins on `(design_id, name)` while **reporting the condition gap
rather than hiding it**. A comparison whose conditions differ is still worth
making; one that pretends they do not is worse than none.

### 3. Human gates are typed hand-offs, not pauses

Each gate has three parts, and today only the first exists:

| | what it is | state |
|---|---|---|
| **outbox** | what the toolchain hands over | done: job bundle, order files, protocol |
| **inbox** | what must come back, with a schema | **missing** |
| **receipt** | validation before anything consumes it | **missing** |

The inbox is the half worth building next. For the GPU gate it is: the
trajectory, *and the input files that produced it*, and the stage logs. For the
wet-lab gate: the reaction record saying which magnesium, which anneal, which
plate lot. For the microscope: native instrument files and the acquisition
settings.

Asking for the inputs back alongside the results is not bureaucracy. It is the
only way to know that the trajectory being analysed came from the protocol that
was sent, rather than from a rerun with a tweaked parameter.

### 4. Nothing downstream may read a raw result

Analysis reads only **ingested** results: ones that passed their receipt. That
is what stops a half-finished trajectory, or images from the wrong reaction,
from quietly becoming a data point.

Every receipt should carry at least one cheap check that is independent of the
thing it is checking. Building Q1 to Q4 produced three worth copying:

- the nucleotide mapping was confirmed by checking that base-paired positions
  hold **complementary bases** -- a property that has nothing to do with how
  the mapping was derived;
- the routers are checked by **mass balance**: every scaffold base paired
  exactly once means staples must sum to the same total;
- the cost estimate is checked against the **order of magnitude** the design
  document expects for a brick.

For an ingested trajectory the equivalent is: does its topology match the
design's, did all four stages complete, and is the final structure still
base-paired where the design says it should be.

### 5. The registry records disagreement, and disagreement is the product

When a prediction and a measurement disagree, that is the finding. The registry
is append-only; a later, better measurement does not overwrite an earlier one,
it supersedes it and both stay. Yield decay with assembly size is the
fundamental limit of this whole idea, and the project's value depends on
measuring it honestly rather than on tuning it out of sight.

## What this means per stage

**Design.** `designs/*.py` emit a design, its id, and its lint report. A design
with hard rule violations does not get an id: it cannot be ordered or
simulated, because both are expensive and the rules are cheap.

**Simulation.** The bundle is already self-contained and says `status: not
run`. What is missing is `sim ingest`: point it at a returned directory, check
the receipt, and only then compute observables. Today's work showed why the
check matters -- stages 1 to 3 completing tells you nothing about stage 4, and
an under-relaxed structure produces a trajectory that exists and means nothing.

**Assembly.** The outbox exists. The inbox is a **reaction record**, one row
per magnesium condition, carrying what was actually used and what the gel
showed. This is the single highest-value artefact in the wet-lab branch,
because without it every downstream measurement is of an unknown sample.

**AFM.** Needs an outbox of its own that does not exist yet: an **imaging
request** stating what to image, at what scale, and **how many particles** are
needed for the statistic to mean anything. Sending a sample without a stated
particle count is how you get beautiful images that cannot support a yield
number. Item M4 is deliberately a standalone module, so its inbox should read
native instrument files rather than exported images.

**Analysis and compare.** Joins the two branches by `(design_id, observable)`,
states the condition gap, propagates uncertainty from both sides, and writes to
the registry. It must be able to answer "why do these disagree" with a list of
candidates -- different salt, surface immobilisation, insufficient relaxation --
rather than a single number.

## Order of work

Priority stays Q1-Q5 plus M4, per the design document. Within that:

1. **Q5 baseline analysis**, which turns a trajectory into observables. Nothing
   else in the pipeline is useful until one branch produces a number.
2. **The simulation inbox and receipt.** Cheap, and it is what makes Q5's
   output trustworthy rather than merely computed.
3. **M4 AFM ingest**, the other branch's numbers.
4. **The reaction record**, which can be a YAML file a human fills in; it needs
   no code to be valuable, only a schema and somewhere to live.
5. **M5 compare**, which is the first point where the whole thing pays off.

The compare step is deliberately last. Building it earlier would mean building
a join over two things that do not yet exist, and the join is the easy part.

## Running jobs: the queue

`write_job_bundle` used to say executing a bundle was the human's job, on a
machine with the backend it asks for. That was written expecting a GPU
elsewhere. On this machine the backend is a CPU, and **oxDNA's CPU backend is
single-threaded** — a production run holds 99% of one core and 43 MB, and
leaves the other fifteen idle for six and a half hours.

So `dobladillo sim` gained a queue:

```bash
dobladillo sim sweep --joint 4,8,16,32 --out runs --root oxqueue
nohup dobladillo sim run --root oxqueue --oxdna path/to/oxDNA &
dobladillo sim status --root oxqueue
```

Each bundle's four stages run strictly in order, because every stage starts
from the previous one's last configuration. Across bundles there is no
dependency at all, and that is where the parallelism is. Four jobs at once
turns a joint sweep from a week into one night on hardware already here.

Three things worth knowing:

- **It restarts.** A bundle whose first three stages finished before the runner
  was killed resumes at production rather than redoing six hours. Completion is
  read from each stage's energy trace against the step count its own input file
  asks for.
- **Progress comes from the bundle, not from stdout.** `sim status` works for a
  run somebody else launched, in another shell, yesterday.
- **One file per job.** Adding work is creating a file and updating status is
  writing that job's own file, so the runner and a caller never write the same
  file and there is no lock to get wrong.

There is no daemon and no supervision. A supervisor that can silently restart a
six-hour job is a thing to want after something has gone wrong in a way that
restarting would have fixed, and nothing has.

Defaults: workers is cores minus four, because the machine is somebody's
desktop. Relaxation is 100k steps per stage rather than the library's million —
100k is what the six-helix run that actually completed here used, and at a
million the relaxation alone would be thirteen hours a job.

## Getting a scan in

`dobladillo afm read` to check a file, `dobladillo afm measure` to run the
whole measurement, `dobladillo afm synthetic` to generate one of known
contents.

**Native instrument files are read directly.** Bruker `.spm` (and Nanoscope's
numbered `.001`, `.002`), JPK `.jpk`, Asylum `.ibw`, Gwyddion `.gwy` and WSXM
`.stp` go straight into `afm read`, `afm measure`, `compare --scan` and
`experiment report`, through AFMReader -- the file layer under TopoStats,
maintained by the AFM-SPM group and tested against real instrument files. There
is no export step, and the instruction to a partner is: send the files the
instrument wrote.

*This section used to say the opposite* -- that native formats could not be
read and every partner should export Gwyddion Simple Field. That was wrong.
The earlier plan had been to reuse `LorenaRedondo/nanoindent`'s readers, which
turned out to read only the topography recorded alongside a *force volume*
(`jpk-force-map`, `jpk-qi-data`, Nanoscope FV offsets), not a plain
tapping-mode scan, and from there the conclusion was generalised to "no native
reader exists" without checking. AFMReader existed.

What the adapter adds on top of AFMReader, each found by reading its source or
running its fixtures rather than assumed:

- **The height channel by default, and no fallback.** A channel that is not in
  the file is an error listing the ones that are (`--channel` picks another).
- **Square pixels.** AFMReader returns one pitch, from one axis. For JPK the
  second is read from the same TIFF tags and a mismatch is refused, as it is
  for GSF. Bruker, Asylum and Gwyddion files give one pitch only; `afm read`
  says square pixels were assumed rather than checked.
- **WSXM `.top` is refused.** AFMReader 0.0.7 rescales its heights to the
  integer part of the header's Z amplitude (4.53 nm becomes 4, 12% low), found
  by reading the `.stp` of the same acquisition beside it. WSXM saves both; the
  `.stp` is read.
- **A truncated Bruker file fails instead of hanging.** pySPM, which AFMReader
  reads Bruker through, loops forever on a header with no end marker.
- **High-speed stacks** (`.asd`, `.h5-jpk`) are refused: this measures single
  images.

GSF stays: `afm synthetic` writes it, it is fully specified and tested exactly,
and it is the way in for an instrument AFMReader does not cover (Park,
Nanosurf) -- export the height channel from Gwyddion. Native force maps are
still read through pyfmreader when it is installed.

`experiment report` reads the native files in `during/raw` and, when there are
any, ignores `.gsf` files beside them: an export is a copy of an image already
there, and reading both would count every particle twice.

**Still open:** no partner file has been committed as a fixture. The native
tests run on AFMReader's own sample files (`tests/data/afm_native/`), with
pixel sizes checked against the values AFMReader's tests state. A real file
from a partner instrument, with its pixel size known independently, needs no
code when it arrives: a line in `tests/data/afm_native/README.md` and a row in
the parametrised test.

**Send the partner a synthetic scan first.** `afm synthetic` writes a `.gsf`
whose contents are known. Asking what they measure from it locates a
disagreement before it can be attributed to the chemistry, and costs nothing.


## Testing the analysis with a realistic scan

`dobladillo afm synthetic --realistic` adds the artefacts a working instrument
leaves: scanner bow, thermal drift shear, and one tip-change streak. Use it to
*test* an analysis, not to demonstrate one.

**It broke this pipeline the first time it ran.** With 4 nm of bow, 40 placed
particles came back as 4 found, all misclassified, measured at 71 nm against a
true 190. The cause: `flatten` fitted a plane, and a piezo scanner bows. A
plane fit removes tilt exactly and leaves a parabola untouched, so a pipeline
validated on a fixture that only tilts looks perfect and fails on the first
real scan.

The background is a full quadratic now — both axes plus a cross term, still
fitted to the background mask only — and the same scan recovers 40 of 40 at
10 nm of bow with all three artefacts together.

Drift and streaks were survived without changes. They are modelled anyway: an
artefact that is survived silently is still one the fixture should contain, or
the next change to the pipeline is untested against it.

### On native instrument formats

`afm synthetic` writes `.gsf`, not a vendor format, and the reason is that
nothing here can make one honestly: producing a mock `.spm` or `.jpk` would
mean writing an encoder for the format, and the test would then exercise the
encoder rather than the reader. Native reading is tested on real vendor files
instead -- AFMReader's own fixtures, for now, and a partner's file when there
is one.
