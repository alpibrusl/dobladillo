# K5 — Preparation sensitivity: how much do the tile's dimensions move, and why?

**Project:** [open AFM calibration kit](../../projects/afm-calibration-kit/PROJECT.md), phase 3
**Folder:** create it (step 0): `experiments/<YYYY-MM-DD>-k5-preparation/`
**Run after:** K3. Its liquid settings are this experiment's centre point, and
its grating routine checks the instrument. K2's pool and method
**Time:** two bench days (two fold batches, on different days), three AFM days,
one day of analysis
**Cost:** no new oligos. NiCl₂, about 25 mica discs, tips from one lot
**People:** you, plus **one other person** to code the samples (as E2)
**Read first:** [K2](K2-calibration-tile-fold.md), [K3](K3-lateral-calibration.md),
[E2](E2-twist-pair.md) (*Blinding: why, and how*), common-techniques §7.
Materials: [`MATERIALS.md`](../../projects/afm-calibration-kit/MATERIALS.md) §2, §4

---

## What you are testing, and why it matters

A reference is only as good as its reproducibility. Origami dimensions are
reported to move by **3–10% with preparation**. Magnesium changes the
spacing between helices. Nickel binds the sheet harder to the mica and can
distort it. Drying flattens and may shrink it. How long it sits on the mica
before imaging changes how it spreads. If the tile's pitch moves by 5% between
two labs' preparations, a calibration from it is worth no more than 5%,
whatever the software's precision.

K5 measures that spread for our tile, factor by factor, on **one instrument,
with one tip lot and one analysis**, so that what varies is the preparation.
**The spread becomes the uncertainty** attached to the tile's value: once for a
tightly declared kit preparation, and once for "any reasonable preparation".

## What it decides

- The tile's uncertainty under the kit's declared preparation (the centre
  point), from replicate depositions and independent fold batches.
- Which factors matter, and by how much. That tells the kit protocol what it
  must fix, and what it can leave to the user.
- Whether the along-helix and across-helix directions respond differently.
  Magnesium is expected to act on the spacing between helices, not on the
  rise along them.
- Whether the uncertainty is small enough for a reference. **That judgement is
  the maintainer's.** K5 supplies the number.

## The matrix

**The centre point (C)** is K3's liquid condition: Mg deposition buffer
(10 mM MgCl₂, common-techniques §7), liquid imaging, the deposition time and
imaging buffer K3 used. Each other condition changes **one** factor from C:

| code | factor changed | level | why |
|---|---|---|---|
| C | — | K3's liquid condition | the kit's declared preparation |
| Mg-lo | MgCl₂ in the deposition buffer | 5 mM | the bottom of E1's screen |
| Mg-hi | MgCl₂ in the deposition buffer | 20 mM | the top of E1's screen |
| Ni | NiCl₂ added to the deposition buffer | one value from 1–5 mM (common-techniques §7), fixed in `pre/plan.md` | firmer adsorption; possible distortion |
| dry | medium | dried and imaged in air, common-techniques §7 | the kit's dry option; Korpelainen et al.'s tile was dry |
| t-short | deposition time | 1 min | |
| t-long | deposition time | 15 min | |

The levels are **proposals**. Write the ones you use into `pre/plan.md` before
committing. A full crossing (3 × 2 × 2 × 3 = 36 conditions) is not proposed:
it costs about three times as much, and one factor at a time answers the
question the kit asks, *which of these must the protocol fix?* A factor that
matters can be crossed with another in a follow-up.

**Replicates and batches:**

| | batch 1 (day A) | batch 2 (day B) |
|---|---:|---:|
| C | 2 depositions | 2 depositions |
| every other condition | 2 depositions | — |

That is 16 depositions. The two batches are independent folds from the same
pool, on different days. C in both batches gives the batch-to-batch term.
**Include C on every AFM day**, so a day-to-day drift in the instrument is not
mistaken for a condition.

**Optional comparator:** GATTA-AFM (rectangle) under C and under Ni, per its
supplier's protocol otherwise. Does a commercial origami show the same spread?

## What is predicted

| quantity | predicted |
|---|---|
| along-helix pitch, across conditions | **not predicted**. The literature's 3–10% is the range; rise per base pair is not expected to depend much on Mg |
| across-helix pitch, across conditions | **not predicted**. `constants.py` says the effective spacing depends on Mg (2.25–2.6 nm) |
| dry against liquid | **not predicted**. Heights fall when dry (E1); lateral change unknown |

## The gate

Copied into `pre/plan.md` and written there by the experimentalist before the
first fold:

> criterion:

### Proposed, not adopted

> **The experiment is valid if:** the grating's overlap scale at the start and
> end of every AFM day agrees within its uncertainty (the instrument held
> still); each deposition gives at least **50** face-up tile particles with at
> least three marks found; and C agrees with itself across AFM days within
> its uncertainty.
> **The result**, reported whatever it is: for along- and across-helix pitch
> and skew, the between-deposition, between-batch and between-day spread at C,
> and the shift from C for each factor, each with a 95% interval.
> **Fail (of the tile as a reference, not of the experiment).** The spread at
> C alone, between replicate depositions and batches, is larger than the
> shift any factor produces. The preparation is then not controlled even with
> every factor fixed, and declaring a tighter protocol would not help.
> **The acceptable spread** for a calibration reference is not proposed here.
> It is the maintainer's decision, written before the data exist.

---

## 0. Create the folder

```bash
uv run dobladillo experiment new <YYYY-MM-DD>-k5-preparation --part calibration-tile --root experiments
```

(`--part calibration-tile` is being implemented.) Do not order: K5 uses K2's
pool. Write the levels, the gate and who holds the key in `pre/plan.md`, and
commit `pre/`.

## Checklist before you start

- [ ] K3 finished: its liquid centre-point settings and its grating routine.
- [ ] K2's tile pool: at least 50 µL (six reactions at 5.5 µL, plus spare).
- [ ] Scaffold, 100 nM: at least 30 µL.
- [ ] NiCl₂ 100 mM made (MATERIALS §2), and its safety note read.
- [ ] Deposition buffers for C, Mg-lo, Mg-hi, Ni, made **once**, labelled,
      and used for all depositions.
- [ ] Tips from one lot; grating; tip characteriser.
- [ ] A second person to code the samples.
- [ ] Gate written; `pre/` committed.

---

## Bench days A and B — two independent fold batches

On each day, fold three tile reactions at E1's magnesium **M** exactly as K2's
steps 2–7: the base mix for N = 4 (3 plus a spare), 5.5 µL of the tile pool
each, common-techniques §3 anneal, a gel against a scaffold-only lane
(`during/raw/gel-A.tif`, `gel-B.tif`), PEG purification into 1× folding
buffer at M, A260. Keep the batches in **separate tubes, labelled A and B**.
Aliquot each as K2 step 12. Freeze at −20 °C.

The same pool and the same buffers are used on both days. The batch term is
then the fold and the purification, not the oligos.

## Coding the samples (the second person)

For each AFM day, the second person:

1. takes the worksheet of depositions for that day from `pre/plan.md`, and
   **randomises their order** (for example by shuffling numbered cards);
2. deposits each one on fresh mica, per its condition, and labels the disc
   with a **code** only (K-01, K-02, …);
3. writes the key (code → condition, batch, deposition time, order) on paper
   or in a message to the supervisor. **Not in the repository.**

You image and analyse knowing only the codes. The dry samples cannot be
hidden, because they are imaged in air. Record that. The Mg, Ni, time and
batch codes can be hidden.

## AFM days 1–3 (a full day each)

Each day:

1. **Grating, start**: K3 step 1, overlap scans only (2 images, 2 µm, 1024 px),
   to `during/raw/grating/`, named `day1-start-01`, and so on.
2. **Tip, before**: common-techniques §8. One tip per day, from the lot.
3. **Each coded disc**, in the second person's order: detail scans **1 × 1 µm,
   512 px**, as K3 step 4, until at least **50** face-up particles with marks,
   plus 2 overlap scans (2 µm, 1024 px). Setpoint, rate and imaging buffer as
   K3. Files to `during/raw/<code>/`, named `pattern-01`, …
4. **Tip, after**, and **grating, end**.

About five or six discs a day. If a disc gives too few particles, say so in
the log and move on. Do not re-deposit out of order.

---

## Unblinding, and what to record

- `during/scans.csv`: as K3's, one row per image, with the **code** as the
  sample.
- `during/log.md`: the second person's name; per day, the grating and tip
  records, room temperature, and anything unusual per code.
- `during/instrument.json`: as common-techniques §10. Its tip record holds
  day 1's tip. Every day's radii go in the log and `scans.csv`.

**After** `post/` is written and committed blind, the second person gives you
the key. Transcribe it into `during/conditions.csv` and commit it on its own:

```
code,batch,condition,deposition_mgcl2_mm,nicl2_mm,medium,deposition_min,day,order
K-01,A,C,10,0,liquid,5,1,3
...
```

(the rows show the format only). `instrument.json` has no NiCl₂ field, which
is one reason this file exists. The format is this protocol's proposal. If
`calibrate report` defines another when it lands, that one wins and this is
converted. The two commits, blind and unblinded, show the analysis was done
blind, as in E2.

## Readout

Blind, per code:

```bash
uv run dobladillo afm read experiments/<folder>/during/raw/K-01/pattern-01.<ext>
uv run dobladillo experiment check experiments/<folder>
uv run dobladillo calibrate lateral experiments/<folder>    # (being implemented)
uv run dobladillo experiment report experiments/<folder> --scan experiments/<folder>/during/raw/K-01/pattern-01.<ext> --scan ...
```

`experiment report` with `--scan`, **one code at a time**, gives each code's
outline and well-formed fraction. It needs E1's reference height and a
measured tip in `instrument.json`, as in K2.

After unblinding:

```bash
uv run dobladillo calibrate report experiments/<folder>     # (being implemented)
```

It reads `conditions.csv` and reports the spread at C (between depositions,
batches and days), each factor's shift from C, for along- and across-helix
pitch and skew, with intervals. Nothing in `post/` is edited by hand.

## When it fails

| symptom | likely cause | what to do |
|---|---|---|
| the grating moves between start and end of a day | thermal drift or creep | that day's C and factors are compared only with each other; report it |
| C differs between days | instrument or tip, not preparation | the day term; that is why C runs every day |
| Ni discs: particles distorted or torn | Ni binds too hard | a result about Ni; report the fraction |
| dry discs: no marks | drying flattens the hairpins (K3's air arm) | a result. Lateral dimensions from the outline only (`experiment report`) |
| t-short: too few particles | too little adsorbed in 1 min | raise the concentration for that code only; record it as a deviation |
| batch B folds poorly | a bench problem on day B | the gel says so; fold again rather than analyse a bad batch as "batch spread" |
| the key is lost | — | the analysis is then not blind. Say so in `post/`; do not reconstruct the key from the data |

## What to hand over

- `pre/` committed before the first fold
- `during/raw/gel-A.tif`, `gel-B.tif`, `during/raw/grating/`, `during/raw/<code>/`, untouched
- `during/scans.csv`, `during/log.md`, `during/instrument.json`
- `post/` committed blind, then `during/conditions.csv` committed after
- the spread at C, and each factor's shift: the numbers K7 and K8 build on
