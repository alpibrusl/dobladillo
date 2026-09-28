# Common techniques

Everything E1, E2 and E3 share. Each experiment's protocol refers back here
rather than repeating it.

Some steps are taken from the literature rather than from this project's own
bench experience, and are marked **[literature]**. If your lab has a validated
method for the same step, use yours and write which one you used in
`during/log.md`.

---

## 0. Safety

| hazard | where | what to do |
|---|---|---|
| DNA stains (SYBR Safe, SYBR Gold) | gels | gloves; SYBR Safe is less hazardous than ethidium bromide but still a nucleic-acid stain. Do not use ethidium bromide for these gels. |
| blue/UV light | gel imaging and band excision | blue-light transilluminator with the amber filter in place; eye protection; never cut bands under UV |
| ice bath + electrophoresis | gel | keep the power supply and cables dry; switch off before touching the tank |
| razor blades | band excision, mica | cut away from you; dispose in a sharps bin |
| compressed nitrogen | drying mica | eye protection; low flow; never point at anyone |
| AFM laser | imaging | follow the instrument's own safety induction |

Waste goes by your institution's rules. Stained gels are usually chemical waste.

**Nuclease-free technique throughout:** gloves, filter tips, nuclease-free water
and tubes. Nucleases chew the scaffold and the result looks like a failed fold.

---

## 1. Stocks

### Folding buffer, 10×, without magnesium

50 mM Tris, 10 mM EDTA, pH 8.0 (1× is 5 mM Tris, 1 mM EDTA). Magnesium is
added separately to each reaction, because the magnesium concentration is the
thing being screened.

> **Why EDTA matters for magnesium.** EDTA binds magnesium one to one. At 1×
> there is 1 mM EDTA in every reaction, so the *free* magnesium is roughly
> the nominal value minus 1 mM. Record the nominal value; the analysis knows
> about the offset. Do not "correct" it by adding more.

### MgCl₂, 100 mM

Make it from a 1 M stock. Use 100 mM rather than 1 M for the reactions:
pipetting 0.25 µL of 1 M is far less precise than 2.5 µL of 100 mM.

### Scaffold

M13mp18 single-stranded DNA, **p7249** (7,249 nt). Commercial stocks are
commonly 100 nM. If yours is a different concentration, recalculate volumes
(§2).

### Staples

Ordered as 96-well plates from the files in the experiment's `pre/order/`
(`*_plates.xlsx`). Standard desalting, 25 nmol scale, delivered normalised to
**100 µM** in water is what the volumes below assume.

**Making the staple pool.** Combine an equal volume of every well of every
plate for that design into one tube (for example 5 µL from each well). Mix well
by pipetting and a brief vortex; spin down. Label with design name, date, and
the number of staples. The concentration **of each staple** in the pool is:

```
C_each_in_pool = C_well / N_staples
```

| design | staples | each staple in pool (from 100 µM wells) |
|---|---:|---:|
| rectangle (E1) | 220 | 455 nM |
| twist pair, each arm (E2) | 216 | 463 nM |
| hinge (E3) | 132 | 758 nM |

Keep one pool per design. **For E2 the two arms must never be mixed.**

---

## 2. Calculating volumes

Every volume in these protocols comes from one formula:

```
V_stock = C_final × V_total / C_stock
```

The targets for every folding reaction:

| component | final concentration |
|---|---|
| scaffold | 10 nM |
| each staple | 50 nM (5× over scaffold) |
| folding buffer | 1× |
| MgCl₂ | the value being screened |
| total volume | 50 µL |

Worked example, rectangle, stocks as in §1: scaffold 10 × 50 / 100 = **5.0 µL**;
staple pool 50 × 50 / 455 = **5.5 µL**; 10× buffer **5.0 µL**; MgCl₂ at 13 mM
from 100 mM: 13 × 50 / 100 = **6.5 µL**; water to 50 µL = **28.0 µL**.

Each experiment's protocol has the full table. **If your stock concentrations
differ, recompute before you pipette, and write the stocks you used in the
log.**

### Use a master mix

Nine reactions differ only in MgCl₂ and water. Mix buffer, scaffold and staple
pool once for all of them plus one spare, aliquot, then add MgCl₂ and water per
tube. This removes most of the pipetting error between reactions, which is the
error you would otherwise be measuring.

---

## 3. Folding (annealing)

Program the thermocycler, heated lid on (about 105 °C):

| step | temperature | time |
|---|---|---|
| 1 | 65 °C | 15 min hold |
| 2 | 60 → 40 °C | 1 °C per minute (20 steps of −1 °C, 1 min each) |
| 3 | 4 °C | hold until you collect |

Total about 35 minutes. This is the fast ramp suitable for flat (2D) designs,
and it is what `pre/protocol.md` records. If a fold fails, a slower anneal is
the first thing to try (for example 80 → 20 °C over several hours) — but that
is a **deviation**: write it in the log, do not edit `pre/protocol.md`.

Use PCR strips or thin-walled tubes. Spin down before and after.

---

## 4. Agarose gel with magnesium

The gel picks which magnesium condition folded best. Magnesium is in the gel
and the running buffer because folded origami needs it to stay folded while it
runs.

**Gel:** 2% agarose in 0.5× TBE **plus 11 mM MgCl₂**. Add SYBR Safe at
1:10,000 to the molten agarose just before pouring (or post-stain afterwards —
pick one and record it).

**Running buffer:** 0.5× TBE plus 11 mM MgCl₂, pre-chilled.

**Samples:** 10 µL of each reaction plus 2 µL of 6× loading dye. Use an
**EDTA-free** loading dye (glycerol or Ficoll based): EDTA strips magnesium
from the sample right where you need it.

**Lanes, left to right:** 1 kb ladder · scaffold only (10 nM, same buffer, at a
mid-range magnesium) · the reactions in order of magnesium · ladder.

**Run:** 60–70 V for 2–3 hours, with the tank in an ice-water bath or in a
cold room. Magnesium makes the gel carry more current and heat up, and heat
unfolds origami. If the buffer gets warm to the touch, lower the voltage.

**Image** on a blue-light transilluminator.

### Reading the gel

| what you see | where | what it means |
|---|---|---|
| sharp band running **faster** than bare scaffold | mid-gel | **folded origami** — compact, so it runs ahead of the floppy scaffold |
| band at the same height as the scaffold lane | mid-gel | unfolded scaffold |
| smear between the folded band and the well | above the band | partially folded or misfolded structures |
| signal stuck in the well | top | aggregates; usually too much magnesium or too concentrated |
| bright diffuse band near the bottom | bottom | excess staples — expected, ignore |

**Pick the condition:** the **lowest** magnesium that gives a sharp, bright
folded band with the least smear above it. Write it in the log with a
photograph of the gel saved to `during/raw/`.

---

## 5. Purification

Removes excess staples, which otherwise coat the mica and look like noise.
Choose **one** method and record which. **[literature]**

### PEG precipitation (preferred)

After Stahl et al., 2014.

1. Mix the folded sample 1:1 with PEG buffer: 15% (w/v) PEG-8000, 5 mM Tris,
   1 mM EDTA, 505 mM NaCl.
2. Mix by gentle pipetting. Centrifuge **16,000 × g, 25 min, room
   temperature.**
3. Remove the supernatant carefully with a pipette. The pellet is often
   invisible; leave a few microlitres behind rather than risk it.
4. Redissolve in 1× folding buffer **with the chosen magnesium** to the
   original volume.
5. Shake gently at 30 °C for at least 1 hour (overnight is fine).

### 100 kDa spin filter (fallback)

Amicon Ultra-0.5, 100 kDa. Rinse the filter with buffer first. Load the sample,
spin at a moderate speed (for example 5,000 × g for 3–5 min — **use your lab's
validated setting**), refill with buffer at the chosen magnesium, and repeat
four to five times. Recover by inverting the filter into a clean tube and
spinning briefly.

### Gel extraction (cleanest, lowest yield)

Cut the folded band under blue light and recover it with a squeeze column.
Use when the other two leave too much misfolded material.

---

## 6. Quantification

Measure A260 on a NanoDrop. Folded origami is mostly double-stranded; using the
double-stranded conversion (1 A260 ≈ 50 µg/mL) and the design's molecular
mass:

| design | approx. mass | 1 A260 ≈ |
|---|---:|---:|
| rectangle | 4.7 MDa | 11 nM |
| twist pair arm | 4.7 MDa | 11 nM |
| hinge | 3.9 MDa | 13 nM |

This is approximate — the unpaired scaffold loop absorbs more per gram than
double-stranded DNA — and good enough for setting a deposition concentration.
Record the reading.

---

## 7. Depositing on mica

Cleave the mica with adhesive tape until the fresh surface is complete and
smooth (no torn flakes). Use it within minutes.

### Imaging dry (in air) **[literature]**

1. Dilute the purified origami to **1–2 nM** in 1× folding buffer with
   **10 mM MgCl₂**.
2. Place **10 µL** on the fresh mica. Wait **1–5 minutes**.
3. Rinse with about **200 µL ultrapure water**, applied gently from the side.
4. Dry under a gentle stream of **nitrogen** for 2–3 minutes.

Drying flattens soft structures. Expect heights of roughly 1–1.5 nm for a
single layer rather than the 2 nm of the model; this is why E1 measures the
reference height (see E1).

### Imaging in liquid (preferred if your AFM supports it) **[literature]**

1. As above, 5–10 µL at 1–2 nM on fresh mica, 2–5 minutes.
2. Without drying, add 40–80 µL of imaging buffer: 1× folding buffer with
   10–12.5 mM MgCl₂.
3. Some groups add 1–5 mM NiCl₂ to hold particles more firmly. It helps
   adsorption and can also distort soft objects: if you use it, record the
   concentration.

**Too few particles:** raise the concentration or the waiting time. **Too
crowded:** particles touch and cannot be measured; dilute. Aim for particles
that are clearly separated in a 2 × 2 µm image.

---

## 8. Measuring the tip radius

**This is not optional.** The AFM draws every particle wider than it is, by an
amount that depends on the tip radius R: about 8.7 nm on a 2 nm sheet for a
10 nm tip — a quarter of a 36 nm width. A nominal "10 nm" tip is routinely
8–20 nm in use. The analysis refuses to run without a measured value.

1. **Before imaging your sample**, image a tip characteriser (a sample with
   sharp features, such as a commercial tip-check sample) with the same tip.
2. In **Gwyddion**: *Data Process → SPM Modes → Tip → Blind Estimation*. This
   reconstructs the tip shape from the image. Fit or read off the apex radius.
3. Repeat **after** imaging. A tip that blunted during the session makes early
   and late scans differently wrong; the analysis uses both values and widens
   its uncertainty if they differ.
4. Write both radii into `during/instrument.json` → `tip.measured_radius_before_nm`
   and `tip.measured_radius_after_nm`. Also the tip part number and its
   nominal radius.

If your group has a validated method for tip radius, use it and record which.

---

## 9. Imaging settings

| image | size | pixels | used for |
|---|---|---|---|
| overview | 2 × 2 µm | 512 × 512 (≈ 3.9 nm/px) | counting and classifying |
| detail | 500 × 500 nm | 512 × 512 (≈ 1 nm/px) | dimensions |

Scan rate around 1 Hz. Keep the imaging force low (gentle setpoint) — pressing
hard compresses the sample and makes the height meaningless. Take images from
**several separate areas** of the mica, not adjacent ones, and note the
positions in the log.

---

## 10. Files, records and analysis

1. **Raw files** go in `during/raw/` exactly as the instrument wrote them. Do
   not rename, crop, convert or "clean up" them.
2. Until the toolchain reads native formats directly (planned), also export
   each image as **Gwyddion Simple Field**: open in Gwyddion, choose the
   **height** channel, *File → Save As* with the `.gsf` extension. Put the
   `.gsf` **next to** the native file, never instead of it.
3. Check each export before believing anything from it:

   ```bash
   uv run dobladillo afm read during/raw/scan-01.gsf
   ```

   The pixel size and scan size must match what you set on the instrument. If
   they do not, every dimension downstream is wrong by the same factor.
4. Fill in `during/instrument.json` completely: instrument, mode, tip, buffer
   **including the magnesium you actually used**, temperature, scan settings.
5. Keep `during/log.md` as you go (§11).
6. When imaging is finished:

   ```bash
   uv run dobladillo experiment check experiments/<folder>
   uv run dobladillo experiment report experiments/<folder>
   ```

   `check` must not report problems with the record. `report` writes `post/`.
7. Commit `during/` and `post/`.

---

## 11. What to write in the log

One entry per session, written during the session, not afterwards:

- date, your name, who else was present;
- **stocks used** and their concentrations (scaffold lot, staple plate lot);
- every **deviation** from `pre/protocol.md`, however small;
- the **gel**: which lane was which, which condition you picked, and why;
- purification method and the A260 reading;
- deposition: concentration, volume, time, air or liquid, any NiCl₂;
- AFM: instrument, tip, tip radius before and after, scan positions;
- anything odd you noticed.

---

## 12. Glossary

**Scaffold** — the long single strand (7,249 nt) that the design folds.
**Staples** — short strands (about 30–40 nt) that pin the scaffold into shape.
**Magnesium screen** — the same fold at a range of MgCl₂ concentrations, to
find which works. **Well-formed** — a particle of the right size and shape,
lying flat. **Tip broadening** — the AFM image of an object is wider than the
object, because the tip has a finite radius. **Gate** — the result, written in
advance, that would count as the experiment failing.
