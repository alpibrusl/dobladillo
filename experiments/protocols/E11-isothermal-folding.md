# E11 — How fast, and at what constant temperature, does the rectangle fold?

**Folder:** create it (step 0)
**Run after:** E1. You need E1's magnesium concentration, a successful fold, and E1's staple pool.
**Time:** 1 day at the bench, plus 1–2 hours of analysis
**Oligos:** none new. It uses E1's pool and scaffold.
**Read first:** [`common-techniques.md`](common-techniques.md), then E1

---

## What you are testing, and why it matters

E1 folds the rectangle with the standard anneal: a hold at 65 °C, then a slow
ramp from 60 to 40 °C. That ramp exists mainly because nobody knows at which
temperature the structure actually folds, so it sweeps through all of them.

Much of the folding happens in a fairly **narrow window of temperature**.
Sobczak et al. (*Science* 2012) folded many shapes in minutes by holding a
single constant temperature inside that window. Knowing the window for our
design matters for two reasons:

1. **Faster, better folds.** Minutes at the right temperature instead of a
   long ramp.
2. **Instruments where temperature cannot be steered**, such as a high-speed
   AFM cell. There, the only protocols that work are ones that fold at a
   temperature the instrument can hold.

The toolchain predicts where the window should be from each staple's melting
temperature (`dobladillo folding-window`). That prediction is deliberately
rough: folding is cooperative, and the real transition sits above the
isolated numbers. **E11 measures the window**, and the prediction is judged
against it.

## What you will measure

At each of 12 constant temperatures and 3 holding times (5, 15 and 60 min),
you measure how much correctly folded rectangle forms. Folded yield is read
from the gel band, relative to E1's standard ramp fold on the same gel.

## What is predicted

Get the prediction for the magnesium E1 chose:

```bash
uv run dobladillo folding-window rectangle --mg-mm <E1's magnesium>
```

At 12 mM it reads: staple melting temperatures with a median of 54 °C, the
10–90% range 45.5–66.5 °C, and a suggested isothermal screen of **40–72 °C**.
Three weak staples are named; they bind last. `experiment new` records this
prediction in `pre/prediction.json` (`folding_window`).

---

## 0. Create the folder and write the gate

```bash
uv run dobladillo experiment new 2026-MM-DD-isothermal-folding --part rectangle --root experiments
```

The folder gets an order file for the rectangle. **Do not order it**: E11
uses E1's pool.

Write the gate in `pre/plan.md` with your supervisor, then commit `pre/`.
A proposal to start from:

> **Pass.** At least one constant temperature gives a folded band of at least
> 80% of the ramp fold's within 15 minutes.
> **Also informative.** No temperature reaches 80% within 60 minutes. The
> rectangle then needs the ramp: record the best temperature and yield anyway.
> **Fail (of the experiment, not of the design).** The reference lane shows no
> clear band on a gel, so nothing on that gel can be normalised.

---

## Checklist before you start

- [ ] E1 finished; you know its magnesium (write it here: ____ mM).
- [ ] E1's staple pool: at least 100 µL left. Scaffold p7249, 100 nM: at
      least 90 µL.
- [ ] A thermocycler with a **gradient block**. Find out the widest gradient
      span it can hold (often 20–30 °C across 12 columns) and write it in the log.
- [ ] Gel equipment for three gels with at least 15 wells each (or six gels
      with 8 wells: see step 6).
- [ ] Fiji installed (open source, fiji.sc) for band quantification.
- [ ] Folder created, gate written, `pre/` committed.

---

## Day 1 — Fold at constant temperatures (about 3 hours), then gels

### 1. Set the gradient (10 min)

Use the predicted screen, for example 40–72 °C. If your cycler's gradient span
is narrower than that, centre it on the predicted median (for example
54 ± 12 °C) and write down what you did. **Record the actual temperature of
every column** as the cycler reports it, not the nominal range: gradient
blocks are not linear, and the analysis uses the actual values.

### 2. Master mix for 40 reactions of 20 µL (15 min)

That is 36 reactions (12 temperatures × 3 times) plus 4 spare. Everything is
on ice, and M is E1's magnesium in mM.

| component | stock | per reaction | master mix (× 40) |
|---|---|---:|---:|
| folding buffer | 10× | 2.0 µL | 80.0 µL |
| scaffold p7249 | 100 nM | 2.0 µL | 80.0 µL |
| staple pool (E1) | 455 nM each | 2.2 µL | 88.0 µL |
| MgCl₂ | 100 mM | 0.2 × M µL | 8 × M µL |
| water | — | 13.8 − 0.2 × M µL | 40 × (13.8 − 0.2 × M) µL |
| **total** | | **20.0 µL** | **800.0 µL** |

Worked example at M = 12 mM: MgCl₂ 2.4 µL per reaction (96.0 µL in the mix),
water 11.4 µL per reaction (456.0 µL in the mix). Final concentrations: 10 nM
scaffold and 50 nM of each staple, the same as E1.

Mix gently, spin down, and put **20 µL** into each of 36 tubes in three
labelled strips of 12: **A = 5 min, B = 15 min, C = 60 min**.

### 3. The reference: E1's standard fold (set up now, 40 min in its own cycler)

One 50 µL reaction exactly as E1's step 2, at the same magnesium: 5 µL buffer,
5 µL scaffold, 5.5 µL pool, 0.5 × M µL MgCl₂, water to 50 µL. Anneal it with
common-techniques §3 (65 °C 15 min, then 60 → 40 °C at 1 °C/min). You will
load 10 µL of it on every gel. **This lane is what every yield is measured
against**, so do not skip it.

Also make a **scaffold-only** control, separately. The master mix already
contains staples, so build it from stocks: 2 µL buffer, 2 µL scaffold,
0.2 × M µL MgCl₂, and water to 20 µL.

### 4. Run strip A, then B, then C (about 2 hours in total)

For each strip, on the gradient cycler, lid at 105 °C:

1. **80 °C for 5 min**, the same across the whole block. Everything melts.
2. **Gradient hold** for the strip's time: 5 min (A), 15 min (B) or 60 min (C).
3. **4 °C hold**. This stops the fold. Take the strip out as soon as it
   reaches 4 °C and keep it on ice.

Put the strip in the same columns every time, so tube 1 is always the coldest
column. Write the start and end times in the log.

### 5. Why not pull tubes out of one run at different times?

Opening the lid mid-run cools the block and changes every other tube's
temperature. Three separate runs are slower and correct.

### 6. Gels (about 3 hours, while the next strip runs)

Use common-techniques §4 exactly: 2% agarose in 0.5× TBE with 11 mM MgCl₂,
cold, 60–70 V, EDTA-free loading dye, 10 µL per lane.

**One gel per strip**, 15 lanes: ladder · scaffold only · reference (ramp) ·
tubes 1–12. If you only have 8-well combs, split each strip over two gels and
put a **reference lane on each gel**. Normalisation only works within a gel.

Photograph every gel with the **same exposure**, check the brightest band is
not saturated (use the imager's saturation display), and save uncompressed
TIFF files as `during/raw/gel-A.tif`, `gel-B.tif` and `gel-C.tif`.

---

## Analysis (1–2 hours)

### 7. Find the folded band

On each gel, the folded rectangle runs as a sharp band **ahead of** the
scaffold-only lane. The reference lane shows you where. Misfolded or
aggregated material smears above it or stays in the well. Only the sharp band
counts.

### 8. Quantify in Fiji

For each gel:

1. Open the TIFF. `Image > Type > 8-bit` only if it is not already greyscale.
   Do not change brightness or contrast before measuring.
2. Draw a rectangle around the folded band of the **reference** lane.
   `Analyze > Measure` gives the Integrated Density.
3. Move the **same rectangle** (same size) onto the folded band of each lane
   in turn and measure again.
4. Measure the same rectangle once on empty gel between lanes: that is the
   background. Subtract it from every value.

### 9. Write `during/gel_quant.csv`

One row per sample lane (36 in total), with the reference value of the same
gel on each row:

```
time_min,temperature_c,folded_band,reference_band
5,40.3,1520,8830
5,43.1,2210,8830
...
60,71.8,640,9120
```

`temperature_c` is the column's **actual** temperature from step 1.

### 10. Run the analysis

```bash
uv run dobladillo experiment folding-screen experiments/2026-MM-DD-isothermal-folding
```

It writes `post/folding_screen.json` and prints:

- for each holding time, the temperature with the best yield (as a fraction
  of the ramp fold) and the range of temperatures that reach at least 80% of
  it;
- the fastest good fold: the shortest time at which any temperature reaches
  80%;
- the predicted staple melting window next to it.

### 11. Judge against the gate, and commit

Write in `post/report.md`: the fastest good fold, the best temperature, and
where it sits relative to the predicted median. **A measured window above the
predicted one is expected**: folding is cooperative. The size of that offset
is itself the result the model needs. Commit.

---

## When it fails

| symptom | likely cause | what to do |
|---|---|---|
| the reference lane has no clean band | the fold failed, not the screen | repeat E1's fold first; nothing here can be normalised without it |
| no lane has any folded band | the melt step left staples bound to the wrong places, or the holds are too short | check the 80 °C step ran; extend the longest hold to 2 h |
| every lane is good, even at the extremes | the window is wider than the gradient | widen the gradient, or add a second run below and above |
| bands are saturated | the exposure is too long | re-image; a saturated band cannot be compared |
| lanes smear at the lowest temperatures | kinetic traps: staples bound before the structure could order | expected; that is the lower edge of the window |
| yield keeps rising with time at every temperature | folding is slower than 60 min here | record it; add a 180-min strip if the gate asks for it |

---

## What to hand over

- `pre/` committed before the session
- `during/log.md` with the actual column temperatures, the run times, and E1's magnesium
- `during/raw/gel-A.tif`, `gel-B.tif`, `gel-C.tif`, untouched
- `during/gel_quant.csv`
- `post/folding_screen.json` and `post/report.md` with your interpretation
