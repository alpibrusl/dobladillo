# K8 — Certification: a value, with a traceable uncertainty, for one batch

**Project:** [open AFM calibration kit](../../projects/afm-calibration-kit/PROJECT.md), phase 5
**Folder:** create it (step 1): `experiments/<YYYY-MM-DD>-k8-certification/`
**Run after:** K5 (the preparation spread) and K7 (the format and its shelf
life, at least to 6 months). K3's routine, and K1's validated range
**Needs a decision first.** Whether K8 happens, with whom, and on what terms is
**the maintainer's decision**. This protocol lists what would be asked of a
partner. It does not propose contacting anyone (`AGENTS.md`, standing
prohibitions).
**Time:** set by the partner. In-house: about two AFM days and a day of analysis
**Cost:** not derivable here. Whatever a partner charges is the maintainer's to agree
**Read first:** [PROJECT.md](../../projects/afm-calibration-kit/PROJECT.md),
[K3](K3-lateral-calibration.md), [K5](K5-preparation-sensitivity.md),
[K7](K7-kit-format-shelf-life.md)

---

## What you are testing, and why it matters

Until K8, the tile's size is its **design value**, with the design's
uncertainty. That is about 2.4% along the helices, and nothing usable across
them (PROJECT.md). K3 compared it with a grating, and K5 measured how much it
moves. None of that makes it a reference anyone else can rely on. K8
assigns a **value and an uncertainty** to one batch, traceable to the SI
metre through a measurement chain that is written down.

Certification is not a better measurement of one tile. What is certified is
a **population under a procedure**: tiles from this batch, prepared this way,
deposited this way, imaged in this medium, read by this software. So the
first thing K8 fixes is the measurand.

## What it decides

- Whether the kit can carry a value with a traceable uncertainty, and how
  large that uncertainty is.
- Which uncertainty components dominate, and so where improvement would pay:
  the instrument, the preparation, the stability, or the analysis.
- Whether the word "certified" is used. It is decided **after** K8, by the
  maintainer, not assumed here. Formal certification of a reference material
  is normally done by an accredited body. A value traceable through a partner's
  measurement is not the same claim, and must not be presented as one.

## 1. The measurand (write it first)

In `pre/plan.md`, before anything is measured, one paragraph of this shape:

> The mean centre-to-centre distance between designated marked cells of the
> calibration tile, **along** the helices (and separately **across** them),
> over face-up tiles from **batch ___**, stored as **format ___** for no longer
> than **___**, prepared by **K5's centre point**, deposited on freshly
> cleaved mica and imaged in **___** at **___ °C**, as read by `dobladillo
> calibrate lateral` **version ___**.

Every blank is filled from K3, K5 and K7. A value without this paragraph
attached is not a calibration value.

Create the folder, then write the measurand, the route and the gate, and commit:

```bash
uv run dobladillo experiment new <YYYY-MM-DD>-k8-certification --part calibration-tile --root experiments
```

(`--part calibration-tile` is being implemented.)

## 2. The route: two options, for the maintainer

| route | what it needs | what it gives | weakness |
|---|---|---|---|
| **A. a partner's traceable AFM** | an instrument whose lateral positions are measured traceably, and its operator | the tile measured directly against the metre | depends on a partner |
| **B. in-house, through the grating** | K3's overlap routine with a **certified** grating of ≤ 400 nm pitch | the tile measured at the scan size where the grating was, traceable to the grating's certificate | the scanner's linearity *within* a 2 µm field, between grating periods and tile spans, is not covered by the certificate. It enters as an uncertainty component that has to be estimated |

Route B can be done without anyone else, and K3 has already done most of it. It
gives a traceable value with a larger and less certain uncertainty. Route A is
what a certificate would normally rest on. Both can be run, and their
agreement is itself a check.

A fluorescence route (DNA-PAINT distances, as Raab et al. 2018) measures a
different quantity, dye positions rather than AFM mark centres. It is not
proposed here.

## 3. The uncertainty budget

Evaluated as in the GUM (JCGM 100:2008 **[literature]**). Every component comes
from an experiment already run, or is measured here:

| component | from | note |
|---|---|---|
| traceable measurement | the partner's budget (route A), or the grating's certificate plus within-field linearity (route B) | the partner's own figures, not ours |
| repeatability | the scatter between particles, over √N | measured here |
| homogeneity within the batch | several aliquots from one batch, measured in-house | measured here (step 4) |
| preparation | K5's spread **at the centre point**: between depositions and batches | not K5's full factor spread: the measurand fixes the preparation |
| stability | K7's drift over the stated shelf life, for the format | bounded by K7's time series |
| analysis | K1's bias bound and coverage at these settings | the software is part of the measurand |
| batch to batch | K5's two batches | applies only if the value is claimed for more than one batch. Proposed: it is not |

The expanded uncertainty is stated with its coverage factor.

## 4. Homogeneity, in-house (two AFM days)

From the batch to be certified, take **at least 6 aliquots at random**, and
measure each by K3's liquid routine (or its air routine, if the measurand says
air), with the grating at the start and end of each day. The analysis gives
the between-aliquot term. Raw files to `during/raw/homogeneity/<aliquot>/`.

## 5. What would be sent to a partner (route A)

For the maintainer to decide on, as a package:

- aliquots from the certified batch, in the kit format, with K7's storage and
  thawing instructions;
- the kit protocol: K5's centre-point preparation and K3's imaging settings;
- the software version, and the command that reads their files;
- **synthetic test images** first (K1's generator, or `dobladillo afm
  synthetic` for the outline). The partner runs them through their own
  pipeline before any real sample is imaged, so a disagreement between
  pipelines is found before it is attributed to the sample. `afm synthetic`'s
  own help describes this use;
- this protocol, the measurand paragraph, and the K5 and K7 results.

## 6. What would be asked for in return

- native instrument files, untouched, into `during/raw/partner/`;
- the instrument's description and its **uncertainty budget** for lateral
  position, with its traceability statement;
- their own reading of the images with their software, as an independent
  check, alongside ours;
- the tip and imaging conditions they used, filled into the same records as
  ours (`instrument.json`, `scans.csv`);
- the terms on which the result may be published. The maintainer agrees
  these.

---

## The gate

Copied into `pre/plan.md` and written there by the maintainer, before any
partner measurement or the homogeneity days:

> criterion:

### Proposed, not adopted

> **Complete.** A value and an expanded uncertainty for along-helix distance
> (and across-helix, if the partner's data support it), with every component
> of §3 either measured or bounded, and none left out because it was
> inconvenient.
> **Consistent.** If both routes are run, they agree within their combined
> uncertainty. If not, the disagreement is reported and no value is issued
> until it is understood.
> **Useful.** Not proposed. What expanded uncertainty makes the kit worth
> offering is the maintainer's judgement. K5 and the literature's 3–10% are
> the context.

## Readout

```bash
uv run dobladillo experiment check experiments/<folder>
uv run dobladillo calibrate lateral experiments/<folder>   # (being implemented)
uv run dobladillo calibrate report experiments/<folder>    # (being implemented)
```

`calibrate report` is expected to take the partner's budget, K5's and K7's
results and K1's bounds, and to write the value, the budget table and the
measurand into `post/`. Nothing in `post/` is edited by hand, and nothing in
the partner's raw files is touched.

## When it fails

| symptom | likely cause | what to do |
|---|---|---|
| the partner's value and route B disagree | within-field non-linearity (route B's weak point), or a pipeline difference | the synthetic test images locate a pipeline difference; report the rest |
| homogeneity term dominates | the batch is not uniform: aliquoting, or the purification | a result. Revisit K2's purification before certifying a batch |
| stability term dominates | the format drifts | certify for a shorter shelf life, per K7 |
| across-helix cannot be resolved by the partner | resolution or tip | certify along-helix only, and say so |
| no partner | — | route B alone, described as traceable to the grating's certificate, with its limitation stated. Not "certified" |

## What to hand over

- `pre/` with the measurand paragraph, committed first
- `during/raw/homogeneity/` and `during/raw/partner/`, untouched
- `during/log.md`: what was sent, when, to whom (by role), and what came back
- `post/` from `calibrate report`: value, expanded uncertainty, budget, measurand
- a note for the maintainer: whether to call it a certificate, and what that
  would require that K8 did not provide
