# K6 — High-speed AFM: scale, drift, and do all-DNA marks survive the tip?

**Project:** [open AFM calibration kit](../../projects/afm-calibration-kit/PROJECT.md), phase 3
**Folder:** create it (step 0): `experiments/<YYYY-MM-DD>-k6-hsafm/`
**Run after:** K3 (the tile's marks are found in liquid on a conventional AFM)
and K1 (its drift rows passed). **Blocked** until three things exist:

1. **HS-AFM time.** No instrument is lined up (`experiments/ROADMAP.md`,
   *Direction: high-speed AFM*). Arranging it is the maintainer's decision.
2. **The movie reader checked on a real file.** `calibrate drift` reads an
   `.asd` or `.h5-jpk` movie directly, through AFMReader, with the frame
   times from the file. It has only been tested on synthetic files written in
   the layout AFMReader parses, and it takes the `.asd` frame time as
   milliseconds, which AFMReader does not state. One file from the
   operator's instrument, read before the session (checklist), closes this.
3. For arm B only: **a biotinylated variant of the tile**, part
   `calibration-tile-biotin`: the same 48 staple ends as the hairpin tile, each
   with a TT spacer and a 3' biotin (IDT `/3Bio/`), ordered with
   `uv run dobladillo lab order calibration-tile-biotin --out <dir>`. Plus
   streptavidin (MATERIALS §1). Arm A runs without it.

**Time:** one or two HS-AFM days, plus a day of analysis
**Cost:** no new oligos for arm A. Arm B: 48 biotinylated staples (1,601
bases; the modification surcharge is the vendor's and is not in the estimate)
plus streptavidin
**Read first:** [K3](K3-lateral-calibration.md), [PROJECT.md](../../projects/afm-calibration-kit/PROJECT.md),
and the HS-AFM operator's own protocol for DNA origami, which wins wherever it
differs from this one. Materials: [`MATERIALS.md`](../../projects/afm-calibration-kit/MATERIALS.md) §2, §5

---

## What you are testing, and why it matters

An all-DNA reference makes most sense where commercial ones struggle:
**high-speed AFM in liquid**. HS-AFM scanners are small, fast and hard to
calibrate. Drift over a movie is part of every measurement, and the tip taps
each spot many times a second. Kielar et al. (*Angew. Chem.* 2020) used origami
to measure that invasiveness, and found that **streptavidin markers get
stripped off by the tip**. Streptavidin on biotin is the usual way to put a
visible mark on origami. The tile's marks are DNA hairpins, part of the
staples, with no protein to lose.

K6 asks three things of the tile on an HS-AFM:

1. **Scale.** The HS scanner's X/Y ratio and skew (from the tile alone,
   uncertified, as in K3), and its along-helix scale against K3's
   conventional-AFM result on the same batch.
2. **Drift.** The tile's marks are fiducials. Their centres, followed frame by
   frame, give the drift velocity through a movie. When two or more tiles are
   in the frame, instrument drift (all move together) can be told apart from a
   particle sliding on the mica (one moves).
3. **Marker survival.** The fraction of designed marks still found, against
   the number of frames the particle has been scanned. For hairpins (arm A)
   and, if arm B exists, streptavidin at the same cells.

The last needs a control that is easy to forget: **time in buffer is not the
same as time under the tip.** A mark can be lost because the tip removed it,
or because it came apart in the buffer. Fields that are scanned only at the
start and at the end separate the two.

## What it decides

- Whether the tile works as an HS-AFM reference: scale and drift from marks
  that last long enough to be followed.
- How long a movie can use the marks before too many are lost: the kit's
  stated working time under the tip.
- Whether all-DNA marks outlast streptavidin under the same imaging (arm B),
  which is the reason for an all-DNA design.

## What is predicted

| quantity | predicted |
|---|---|
| X/Y ratio, skew | **not predicted**; HS scanners vary |
| along-helix scale | the design within 2.4%, **and** K3's value on the same batch within their uncertainties |
| drift | **not predicted** |
| hairpin survival | **not predicted**. The expectation, not a prediction, is that it beats streptavidin (Kielar et al.) |

## The gate

Copied into `pre/plan.md` and written there by the experimentalist, with the
HS-AFM operator, before the session:

> criterion:

### Proposed, not adopted

> **Scale.** X/Y ratio and skew stated with 95% intervals, from at least
> **30** face-up tiles with at least three marks found. The along-helix scale
> is compared with K3's.
> **Drift.** A drift velocity with its interval, from movies with at least two
> tiles in the frame.
> **Survival.** At the operator's standard setpoint, at least **80%** of
> designed hairpin marks still found after the number of frames written in
> `pre/plan.md`, and the unscanned-control fields show no loss beyond that.
> **Arm B, if run.** Hairpin survival exceeds streptavidin's under the same
> imaging, or the difference is bounded.
> **Fail.** Hairpin marks lost within the first few frames at the standard
> setpoint. The tile is then not an HS-AFM reference as designed. That is a
> result, and it points at the mark's design.

---

## 0. Create the folder

```bash
uv run dobladillo experiment new <YYYY-MM-DD>-k6-hsafm --part calibration-tile --root experiments
```

Arm A uses K2's or K5's
aliquots of one named batch. Write in `pre/plan.md` the frame count for the
survival criterion, the two setpoints, and the operator's buffer. Commit `pre/`.

## Checklist before you start

- [ ] HS-AFM time arranged, by the maintainer's decision; the operator's
      protocol read.
- [ ] `calibrate drift` reads your instrument's movie format. Run
      `uv run dobladillo calibrate drift <operator-file>.asd --json` on one
      file from the operator **before** the session, and check two numbers
      against the operator's own: `file_frame_interval_s` against 1 / frame
      rate, and `pixel_nm` against frame size / pixels. If it does not read,
      or either disagrees, stop: there is no analysis to run until it does.
- [ ] K3's liquid result on the same batch, for the scale comparison.
- [ ] Tile aliquots of one batch, named. Arm B's samples, if decided.
- [ ] Imaging buffer: the operator's validated one, or MATERIALS §2's.
- [ ] Gate written; `pre/` committed.

---

## The session (per HS-AFM day)

### 1. Deposit (15 min)

As the operator's protocol, onto the instrument's small mica: 1–2 nM tile in
the Mg deposition buffer, then imaging buffer (common-techniques §7). NiCl₂
only if the operator's protocol requires it. Record it; K5 says what it does to
the tile.

### 2. Find and mark the control fields (15 min)

At low magnification, pick **three control fields** with tiles in them. Image
each **once** now, at the settings below, and record their positions. Do not
scan them again until step 5.

### 3. Movies at the standard setpoint (2–3 h)

Frame size of a few hundred nanometres, enough for **two or more tiles**,
with a pixel no larger than **2.6 nm** (the coarsest E8's analysis reads).
Frame rate as the operator's standard for origami. Continuous movies of the
length written in `pre/plan.md` (for example 10 minutes), each on a fresh
field. At least **5 movies**.

### 4. Movies at a harder setpoint (1–2 h)

As step 3, with a lower setpoint amplitude ratio (the operator's choice),
written in `pre/plan.md`. At least **3 movies**. Survival should fall faster.
If it does not, the loss in step 3 was not the tip.

### 5. Control fields, end (15 min)

Image the three control fields **once**, as in step 2. Marks lost here but not
under the tip are lost to time in buffer.

### Arm B, if decided

Steps 1–5 again with the streptavidin-marked tile, the same settings, the same
day, a fresh cantilever if the operator changes it. Record the streptavidin
concentration and incubation.

---

## What to record

`during/movies.csv`, one row per movie or control image:

```
file,arm,kind,field,setpoint_ratio,free_amplitude_nm,frame_rate_hz,frame_size_nm,pixels,start,frames,cantilever
hsafm/A/movie-01.asd,A,movie,F1,0.9,2.0,5,250,125,10:12,3000,<type>
hsafm/A/control-F3-start.asd,A,control,F3,...
...
```

(the rows show the format only; the numbers are not settings to copy). The
format is this protocol's proposal, and `calibrate`'s own wins when it lands.

`during/log.md`: the operator; instrument; cantilever type and lot; buffer
(MgCl₂, any NiCl₂); temperature; every tip change or cantilever swap, with
the time; anything that moved.

`during/instrument.json`: as far as it applies. HS-AFM tips are not measured
with common-techniques §8's characteriser in most setups. **Do not type in a
nominal radius.** Leave the field empty, and say in the log how, or whether,
the operator characterises the tip. Centre-to-centre distances are
first-order insensitive to the tip (PROJECT.md), so the scale and drift
readouts do not depend on it. Heights do, and they are not K6's result. Do
fill in the deposition cations (`deposition.mgcl2_mm`, `deposition.nicl2_mm`,
0 if none), `scan.angle_deg`, `scan.direction` and `scan.closed_loop`:
`calibrate report` refuses the scale and the drift without them.

**Raw files** go to `during/raw/hsafm/A/` and `during/raw/hsafm/B/`, native,
untouched. `calibrate drift` reads them as they are; `afm read` and the other
single-image commands refuse them. Do not convert them in place of the native
file: a per-frame export loses the frame times the drift analysis needs.

## Readout

```bash
uv run dobladillo experiment check experiments/<folder>
uv run dobladillo calibrate report experiments/<folder>
```

`calibrate report` reads every movie in `during/raw/hsafm/` as one drift
series, with the frame times from the file (`times_source` and
`file_times_note` in `post/calibration.json` say how they were read; check
them against the operator's frame rate, as the checklist asks). A movie whose
times cannot be trusted is refused, not guessed at.

From these: scale X, scale Y and skew with intervals; drift velocity against
time, with instrument drift separated from particle motion where two or more
tiles are in frame; per-arm survival (fraction of designed marks found)
against frames scanned, at each setpoint, and the control fields' start
against end.

## When it fails

| symptom | likely cause | what to do |
|---|---|---|
| `calibrate drift` cannot read the movies | the instrument's file differs from what AFMReader parses (the reader is untested on real files) | stop before the session (checklist); send the error to the maintainer; nothing else substitutes |
| the frame interval disagrees with the operator's frame rate | the `.asd` frame time is not in milliseconds on this instrument, or the file's times are otherwise wrong | give the operator's times with `--interval-s` or `--times`; `times_source` records that they replaced the file's |
| marks lost at once, at every setpoint | the marks do not survive HS-AFM tapping | a result. Report the frame count; it points at the mark design |
| marks lost in the control fields too | the tile or its marks come apart in the buffer | a result about the buffer and the time, not the tip |
| tiles slide between frames | adsorption too weak for HS-AFM | the operator's usual fix (often NiCl₂); record it as a deviation, and remember K5's Ni result |
| only one tile per frame | too dilute, or frame too small | drift and particle motion cannot be separated in those movies; report them apart |
| scale far from K3's | HS scanner calibration | a finding about the instrument; that is part of what K6 is for |

## What to hand over

- `pre/` committed before the session
- `during/raw/hsafm/`, native, untouched; `during/movies.csv`; `during/log.md`
- `post/` from `calibrate`, with the interpretation: scale, drift, survival per arm and setpoint, control fields
- the working time under the tip, which K7's kit protocol states
