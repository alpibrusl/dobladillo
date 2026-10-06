# E1 — The rectangle: does our first design fold?

**Folder:** `experiments/2026-09-28-rectangle-afm/`
**Time:** about 3 working days plus 3–5 days for oligo delivery
**Cost:** about €693 of staples; scaffold and consumables on top
**Read first:** [`common-techniques.md`](common-techniques.md)

---

## What you are testing, and why it matters

This is a DNA origami rectangle: one long scaffold strand (7,249 nt) pinned into
a flat sheet of 22 parallel DNA helices by 220 short staple strands. The design
was produced by this project's software, and **it has never been folded.**

It is "Rothemund-style" — the rectangle is the most reproduced object in the
field — but it is *not* the published staple set. The routing and every staple
come from our code. So this experiment tests our code, not the chemistry. If
it does not fold here, the problem is in our design pipeline, and every later
experiment would inherit it. **That is why E1 gates everything.**

The one thing nobody knows is **flatness**. Our lattice winds the DNA slightly
tighter than it wants to go (10.67 base pairs per turn against a relaxed 10.5).
Left alone, that would twist the sheet. The design deletes one base every 64 to
cancel it. On paper that is exact. Whether it works is visible in an AFM image
and nowhere else.

E1 also gives you two numbers that E2 and E3 need:

1. the **magnesium concentration** that folds our designs best in your hands;
2. the **reference height** of a flat sheet in your imaging conditions.

## What is predicted

| property | predicted | how it will look on the AFM |
|---|---|---|
| long edge | 106.2 nm | wider, by the tip broadening (§ analysis) |
| short edge | 66.0 nm | wider, by the tip broadening |
| height | about 2 nm | lower if imaged dry, typically 1–1.5 nm |
| shape | flat rectangle | flat rectangle, if the twist correction works |

## The gate

**You write it, before the session**, in `pre/plan.md`'s `criterion:` line.
The folder was re-scaffolded on 2026-09-28 (the design was re-tiled), and the
gate from the earlier folder is quoted in `pre/plan.md` as a proposal. Adopt
it, change it or replace it with your supervisor, then commit `pre/`. The
proposal, in short:

- **Fold:** a dominant gel band, distinct from free scaffold.
- **Shape:** at least 50 particles clear of the image edge; tip-corrected
  edges within 10% of 106.2 × 66.0 nm.
- **Flatness:** height within 30% of 2.0 nm, and no systematic curvature.
- **Failure:** fewer than 25% well-formed means the fold or the deposition is
  wrong — that sends us back to the magnesium screen.
- **Control:** decide what the positive control must show, for example at
  least 50 recognisable rectangles, or the session is void. See below.

### The positive control

A **known-good rectangle** is folded, deposited and imaged alongside ours, in
the same session and from the same buffers. If ours fails and the control
folds, our design pipeline is at fault. If both fail, the bench is. Without
it the two cannot be told apart. This project's designs have already been
wrong once without anyone noticing.

The control is bought, so choosing it is your supervisor's decision, and
buying it is a purchase:

- a **commercial rectangle kit**, folded exactly to its supplier's protocol
  and not to ours (their buffer, their magnesium, their anneal — do not mix
  parameters); or
- the **published Rothemund (2006) rectangle**, ordered like ours and folded
  with our protocol at the magnesium you pick in step 5.

The control has no prediction from this toolchain, and none should be
invented for it. It either folds into countable rectangles or it does not.
Record which control you used, with its lot or order number, in
`during/log.md`.

> **A note on the height criterion, to settle before the session.** Imaging
> dry compresses DNA; 1.2 nm is common and would fail a 30% criterion for an
> imaging reason, not a design one. If you will image dry, discuss this with
> your supervisor and, if you agree, amend the gate **before** the session and
> commit the change. Do not amend it afterwards.

---

## Checklist before you start

- [ ] Read `pre/plan.md`; you understand the gate.
- [ ] The gate is final and `pre/` is committed:
      `git add experiments/2026-09-28-rectangle-afm/pre && git commit -m "E1: pre-register"`
- [ ] Oligos ordered from `pre/order/rectangle_plates.xlsx` (supervisor approved).
- [ ] Positive control in hand (kit or published staple set), and its
      protocol read.
- [ ] Scaffold p7249 in stock; its concentration known.
- [ ] Stocks made (common-techniques §1).
- [ ] Thermocycler, gel equipment, NanoDrop and AFM booked.
- [ ] A tip-characteriser sample is available for the AFM.

---

## Day 1 — Fold and check (about 4 hours)

### 1. Make the staple pool (30 min)

Pool equal volumes of all **220** staples from the plates (common-techniques
§1). With 100 µM wells, each staple is **455 nM** in the pool. Label it.

### 2. Set up nine folding reactions (30 min)

**Master mix** for 10 reactions (9 plus one spare), on ice:

| component | stock | per reaction | master mix (×10) |
|---|---|---:|---:|
| folding buffer | 10× | 5.0 µL | 50.0 µL |
| scaffold p7249 | 100 nM | 5.0 µL | 50.0 µL |
| staple pool | 455 nM each | 5.5 µL | 55.0 µL |
| **total** | | **15.5 µL** | **155.0 µL** |

Mix gently by pipetting; do not vortex hard. Put **15.5 µL** in each of nine
labelled tubes, then add:

| tube | MgCl₂ final | 100 mM MgCl₂ | water | total |
|---:|---:|---:|---:|---:|
| 1 | 5 mM | 2.5 µL | 32.0 µL | 50 µL |
| 2 | 7 mM | 3.5 µL | 31.0 µL | 50 µL |
| 3 | 9 mM | 4.5 µL | 30.0 µL | 50 µL |
| 4 | 11 mM | 5.5 µL | 29.0 µL | 50 µL |
| 5 | 13 mM | 6.5 µL | 28.0 µL | 50 µL |
| 6 | 15 mM | 7.5 µL | 27.0 µL | 50 µL |
| 7 | 17 mM | 8.5 µL | 26.0 µL | 50 µL |
| 8 | 19 mM | 9.5 µL | 25.0 µL | 50 µL |
| 9 | 20 mM | 10.0 µL | 24.5 µL | 50 µL |

If your stocks differ, recompute with `V = C_final × V_total / C_stock`
(common-techniques §2) and write the stocks in the log.

Also prepare a **scaffold-only control**: 5 µL buffer, 5 µL scaffold, 6.5 µL
MgCl₂ (13 mM), water to 50 µL. It shows where unfolded scaffold runs.

And fold the **positive control** (see "The positive control" above):

- **Kit:** exactly per its supplier's protocol, in its own tube. The
  Tilibit Flat sheet kit is walked through, with its volumes, in
  [`E1-flat-sheet-kit.md`](E1-flat-sheet-kit.md).
- **Published staple set:** one 50 µL reaction like tube 5 (13 mM), with its
  own pool in place of ours.

Label it `C`.

### 3. Anneal (35 min)

Spin down, put our nine tubes and the scaffold-only control in the
thermocycler, run the program in common-techniques §3: 65 °C for 15 min, then
60 → 40 °C at 1 °C/min, then hold at 4 °C.

**The kit control is annealed separately**, on its supplier's own program (the
Tilibit Flat sheet's ramp differs from ours: see
[`E1-flat-sheet-kit.md`](E1-flat-sheet-kit.md) §3). Run it straight after ours,
or in a second cycler, and keep it cold until the gel.

**Start the gel casting now** so it has set when the fold finishes.

### 4. Gel (2.5–3 hours)

Follow common-techniques §4 exactly: 2% agarose in 0.5× TBE **+ 11 mM MgCl₂**,
cold, 60–70 V, EDTA-free loading dye, 10 µL of each reaction.

Lane order: ladder · scaffold only · tubes 1–9 · control C · ladder.

If the control shows no folded band, **stop and record it**. The session is
testing the bench, not our design, until the control folds.

Photograph it and save the image to `during/raw/gel-day1.png`.

### 5. Pick the condition

The **lowest** magnesium that gives a sharp, bright band running ahead of the
scaffold-only lane, with little smear above it and little in the well.

Write in `during/log.md`: which tube you picked, and why, in one or two
sentences. If two look equally good, pick the lower magnesium.

**If nothing folded** — no band distinct from the scaffold lane — stop here and
go to *When it fails* below. That is a result, not a reason to skip ahead.

---

## Day 2 — Purify, deposit, image (about 2 hours plus the AFM session)

### 6. Purify the chosen reaction (1.5 h + ≥1 h waiting)

PEG precipitation (common-techniques §5). Redissolve in 1× folding buffer
**with the magnesium of the tube you picked**. Let it redissolve at least 1 h
at 30 °C.

**Keep the supernatant; do not discard it.** It holds the excess staples, about
four fifths of what was ordered, since the fold uses a 5× excess. Label the tube
(for example `E1-PEG-<date>`), freeze it at −20 °C, and record the label as
`purification.kept_as` (step 13). It changes nothing about E1: E1 itself is
folded with fresh staples only, and the kept pool is for later folds once reuse
has been checked (common-techniques §5, *Keeping the excess staples*).

### 7. Quantify (10 min)

A260 on the NanoDrop. For the rectangle, **1 A260 ≈ 11 nM**. Write the reading
and the concentration in the log.

### 8. Measure the tip — before (20 min)

Common-techniques §8. Image the tip characteriser, estimate the radius in
Gwyddion, and write it into `during/instrument.json` as
`tip.measured_radius_before_nm`. **Do not skip this.**

### 9. Deposit (15 min)

Dilute to **1–2 nM** in 1× buffer with 10 mM MgCl₂. Deposit on fresh mica,
dry or liquid (common-techniques §7). Record which.

### 10. Image (2–3 h on the AFM)

| image | size | pixels | how many |
|---|---|---|---|
| overview | 2 × 2 µm | 512 | enough for **300 particles**, 100 as the floor |
| detail | 500 × 500 nm | 512 | 5–10 images, several particles each |

**Why 300.** The yield is a proportion, and its precision depends only on how
many particles you count: at 100 particles a yield near 70% is ±9%, at 300 it
is ±5%. Below 100 you cannot tell a good fold from a mediocre one — which is
the whole question.

Take images from separate areas of the mica. Save every native file to
`during/raw/` untouched.

**Control:** deposit it on its own mica, in the same way, and take enough
overview images for about 50 particles. Save them to **`during/raw/control/`**,
never to `during/raw/` itself: the report reads only the top level, and
mixing the control into our rectangle's count would make the yield a blend
of two objects.

### 11. Measure the tip — after (20 min)

Repeat step 8 and write `tip.measured_radius_after_nm`.

---

## Day 3 — Analysis (about 1 hour)

### 12. Check the files

The native files are read directly; there is nothing to export
(common-techniques §10). Check each one:

```bash
uv run dobladillo afm read experiments/2026-09-28-rectangle-afm/during/raw/scan-01.spm
```

Pixel size and scan size must match what you set on the instrument. If your
instrument's format is not read (the command says so), export a `.gsf` of the
**height** channel from Gwyddion next to the native file and check that.

### 13. Fill in the record

- `during/instrument.json`: every field, **including `buffer.mgcl2_mm`** — the
  magnesium of the tube that went on the mica — and the staple record:
  `staples.source=fresh`, `purification.method=PEG precipitation`,
  `purification.excess_kept=true` and `purification.kept_as=<the tube's label>`
  (through `dobladillo experiment record`, or the web UI's instrument form).
- `during/log.md`: complete.

### 14. Run the report

```bash
uv run dobladillo experiment check experiments/2026-09-28-rectangle-afm
uv run dobladillo experiment report experiments/2026-09-28-rectangle-afm
```

If `report` stops and says the tip radius is missing, **measure it** — do not
type in the nominal value from the tip box. The whole correction depends on it.

The report tells you the measured size, the size after removing tip broadening,
and whether that agrees with 106.2 × 66.0 nm, plus the fraction of particles
that are well-formed, twisted, malformed or aggregated, with a 95% interval.

### 15. Record the two numbers E2 and E3 need

In `post/report.md`, under *Interpretation*, write:

- **Magnesium used:** the tube you picked.
- **Reference flat-sheet height:** the median height of the well-formed
  rectangles (the report gives it). This is the height E2 compares against.

### 16. Judge against the gate, and commit

Read the gate in `pre/plan.md` and say, in plain words, whether each criterion
passed. Then commit `during/` and `post/`.

---

## When it fails

| symptom | likely cause | what to try next — record it as a deviation |
|---|---|---|
| no band distinct from scaffold, at any magnesium | staple pool wrong, or anneal too fast | check the pool was mixed; try a slow anneal (80 → 20 °C over ~12 h) |
| everything in the well | magnesium too high, or too concentrated | use the lower-magnesium tubes; fold at 5 nM scaffold |
| heavy smear, weak band | misfolding | lower magnesium; slower anneal |
| gel fine, no particles on mica | deposition | more magnesium in the deposition buffer, longer incubation, higher concentration |
| particles broken or fragmented | drying damage | image in liquid |
| crowded, overlapping particles | too concentrated | dilute 2–5× |
| rectangles present but curved or twisted | **the twist correction may not work** | this is a real result — record it, image more, and tell the project |
| `afm read` shows the wrong pixel size | wrong channel, or a bad export | check `--channel`; for a `.gsf`, re-export from Gwyddion and check the units |

**A failure, properly recorded, is a result.** Write what you saw, what you
tried, and what you think it means. Do not tidy it away.

---

## What to hand over

- `pre/` (committed before the session)
- `during/raw/`: gel photo, native AFM files (and `.gsf` exports only for a format the toolchain does not read)
- `during/raw/control/`: the positive control's images, and in `during/log.md`
  which control it was, with its lot, and how many rectangles you counted
- `during/instrument.json` complete, including both tip radii
- `during/log.md`
- `post/` from `dobladillo experiment report`, with your interpretation
- the magnesium and reference height for E2 and E3
