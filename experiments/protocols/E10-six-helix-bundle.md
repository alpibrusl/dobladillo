# E10 — The six-helix bundle: our first 3D fold

**Folder:** create it when E10 is unblocked, not before:
`uv run dobladillo experiment new <YYYY-MM-DD>-bundle-6hb --part bundle`
**Status:** **blocked** until the oxDNA run `2026-09-28-bundle-6hb-unit`
shows the current design straight (see *Why it is blocked* below)
**Time:** about 4 working days plus 3–5 days for oligo delivery
**Cost:** about €706 of staples (168 × 42 nt at the list price `lab order`
assumes); scaffold and consumables on top
**Read first:** [`common-techniques.md`](common-techniques.md) — but see the
warning below about which of its sections apply
**Depends on:** E1, for bench technique, the tip-measurement routine and the
reference flat-sheet height. Independent of E2–E9.

---

> ### This experiment does NOT use common-techniques' folding recipe
>
> A 3D object's buffer, magnesium, concentrations, anneal, gel and
> purification were validated **together** by the group that published them.
> E10 follows **one** published protocol, whole (below), and its
> `pre/protocol.md` is written from that source, not from the generic sheet.
> From `common-techniques.md` use only: §0 safety, §1 *making the staple pool*,
> §2 the volume formula, §6 the A260 conversion, §8 the tip radius, §9–§11
> imaging, files and the log. **Do not** use its folding buffer (§1), anneal
> (§3), gel (§4), PEG recipe (§5) or deposition (§7): they are a different
> protocol's. Mixing them is how a fold fails for a reason nobody can name.

## The source

Enlund E, Julin S, Linko V, Kostiainen MA. *Structural stability of DNA
origami nanostructures in organic solvents.* **Nanoscale 16, 13407–13415
(2024)**, doi:10.1039/D4NR02185A, open access (CC BY), read at
<https://pmc.ncbi.nlm.nih.gov/articles/PMC11256221/> on 2026-09-28.

It folds a **six-helix bundle on the same p7249 scaffold**, checks it on a
magnesium agarose gel, PEG-purifies it and images it dry on mica by AFM —
every stage E10 needs, from one paper. Their bundle is *not* our routing (they
cite its design to Bui et al., Nano Lett. 10, 3367–3372, 2010); the lattice,
scaffold and staple chemistry are the same. `dobladillo/lab/published.py`
holds every value taken from it, with the sentence each came from, and marks
what the paper does not state as **"not stated in the source — confirm with
the lab"**. Those are listed in *Open with the lab* at the end. The quotes
came through a text extraction of the web page: check them against the
published PDF before the session.

---

## What you are testing, and why it matters

A six-helix bundle is six DNA helices packed in a hexagonal ring: a stiff rod,
about 390 nm long and 8 nm across, and the workhorse strut of 3D origami. It
is this project's **first 3D part**, and it has a history. The first two
routings our software produced put the staple crossovers on the wrong face of
the helices, and in oxDNA simulations those bundles did not come out straight:
they **bent into arcs of 269 and 347 nm radius**, always the same way
(`docs/BUNDLE_BEND.md`). The current routing tiles a published unit, scores
like published designs on the crossover-phasing check, and the beam model
predicts it straight. **Nobody has folded it.**

So E10 asks two things, in order, as the roadmap does:

1. **Does it fold at all?** A gel, before any AFM. A 3D object that does not
   fold is not worth depositing.
2. **Is it the right rod?** The right length, and — the real question —
   **straight**. Not "perfectly straight": a rod with a persistence length of
   a few microns bends visibly on mica from thermal motion alone. The question
   is whether it is *straight but flexible* (bends that go either way, and
   average out) or *systematically curved* (every rod bent the same amount,
   like the old routing). The analysis separates those two; the eye cannot.

## Why it is blocked

An oxDNA run of exactly this design, `2026-09-28-bundle-6hb-unit`, was still
relaxing when this protocol was written. `docs/BUNDLE_BEND.md` sets its bar:
the design is straight only if the run's bend order parameter falls **well
below 0.99** and its sagitta **well below 50 nm**. If it does not, the design
changes, the order changes, and this experiment would fold the wrong object.
Do not order oligos until the lead marks E10 unblocked.

## What is predicted

`experiment new` writes all of this into `pre/prediction.json` (the `rods`
block) when the folder is made. The numbers below are from that code.

| property | predicted | how it will look on the AFM |
|---|---|---|
| contour length | 390.4 nm | +2 × the tip broadening at each end: about 406 nm with a 10 nm tip on an 8 nm rod |
| width | 8.0 nm (ring diameter) | much wider: 17.9–26.5 nm for tips of 8–20 nm |
| height | 8.0 nm (ring diameter) | lower if dry, by an amount nobody here has measured — compare with E1's reference height, not with 8.0 |
| shape | straight, flexible | see the next table |

How straight. For a rod of 390 nm on a surface with persistence length Lp
(the constant's range, 1–3 µm), against the two old arcs:

| population | end-to-end / contour, median [95% range] | intrinsic curvature |
|---|---|---|
| straight, Lp 1.0 µm | 0.978 [0.893, 0.994] | 0 |
| straight, Lp 1.7 µm | 0.987 [0.935, 0.997] | 0 |
| straight, Lp 3.0 µm | 0.992 [0.963, 0.998] | 0 |
| old arc, 347 nm, Lp 1–3 µm | 0.937–0.944 [0.757, 0.992] | 1/347 nm⁻¹ |
| old arc, 269 nm, Lp 1–3 µm | 0.902–0.910 [0.691, 0.987] | 1/269 nm⁻¹ |

The end-to-end ratios **overlap**: a floppy straight rod and a stiff curved one
can have the same ratio. That is why the verdict does not come from that
column. It comes from how the bending grows along the rod: the variance of the
angle change between two points *s* apart grows as *s*/Lp for thermal bending,
and as (*s*/R)² for an arc of radius R. `experiment rods` fits both terms. A
straight bundle gives a curvature term consistent with zero; the old defect
gives 1/269–1/347 nm⁻¹.

**What it can resolve.** On synthetic populations of about 100 rods: for a
straight population, any intrinsic radius is bounded above roughly 0.65–1.2 µm;
a population curved at 1 µm radius was detected in 3 of 5 trials; the old
arcs (269, 347 nm) were detected in every trial, with their radius recovered
to ±20%, and never confused with a straight population (`tests/test_rods.py`).
The persistence length comes with an interval of roughly −25% to +40% at that
count.

**Two limits of the method**, to know before you look:

- An arc that lands on the mica bent *upwards* is pressed flat and reads as
  straight. Rods land either way, so a curved design still shows up in the
  population; but a curvature that only ever lands out of plane would be
  missed.
- Lp from one dry deposition is a property of that deposition as much as of
  the bundle. It is reported against 1–3 µm, not gated on.

## A gate to propose — you write the real one

The gate is the experimentalist's (see `experiments/AGENTS.md`). This is a
proposal to discuss with your supervisor, then write in your own words into
`pre/plan.md` **before** the session.

- **Fold (gel):** a sharp band clearly distinct from the scaffold-only lane,
  carrying most of the lane's signal. If there is none, stop: that is the
  result.
- **Count:** at least **100 rods** traced (`experiment rods` exits 1 below
  that and says so).
- **Length:** tip-corrected contour of the rods within **10%** of 390.4 nm.
- **Straightness — the point of E10:** `old_defect_excluded` is true
  (the 95% upper bound on intrinsic curvature is below 1/347 nm⁻¹) **and**
  `systematically_curved` is false.
- **Failure that matters:** `systematically_curved` true with a radius below
  about 1 µm. That would mean the design bends despite passing the phasing
  check — a real finding, not a failed session.
- **Yield:** decide a floor for `rod_fraction` together; nothing here predicts
  one.

---

## Checklist before you start

- [ ] E10 marked unblocked by the lead (the oxDNA run is in).
- [ ] E1 done: you know the tip routine, and you have E1's reference flat-sheet
      height.
- [ ] Folder created (`experiment new … --part bundle`); `pre/plan.md` gate
      written; `pre/protocol.md` read — it is the source's protocol, whole.
- [ ] The *Open with the lab* items below settled and, where they change
      `pre/`, written there **before** committing.
- [ ] `pre/` committed: `git add experiments/<folder>/pre && git commit -m "E10: pre-register"`
- [ ] Oligos ordered from `pre/order/bundle_plates.xlsx` (supervisor approved).
- [ ] Scaffold p7249 in stock, concentration known. 50× or 10× TAE, 100 mM
      MgCl₂, PEG 8000, 5 M NaCl.
- [ ] Thermocycler booked for ~12 h, gel on ice, centrifuge, AFM booked.

---

## Day 1 — Fold (1 hour at the bench, then about 11.5 hours in the thermocycler)

### 1. Make the staple pool (30 min)

Pool equal volumes of all **168** staples (common-techniques §1), for example
5 µL from each well: 840 µL. From 100 µM wells each staple is
100 µM / 168 = **595 nM** in the pool. Label it: *bundle, date, 168 staples*.

### 2. Stocks for this protocol

| stock | how | used for |
|---|---|---|
| 10× TAE | 1 part 50× TAE + 4 parts water | folding buffer, gel, PEG buffer |
| 100 mM MgCl₂ | from 1 M, as common-techniques §1 | everything with Mg |
| 1× FOB, 2 mL | 200 µL 10× TAE + 250 µL 100 mM MgCl₂ + 1,550 µL water | dilutions, gel samples, resuspension |
| PEG buffer, 1 mL | 0.15 g PEG 8000 + 100 µL 10× TAE + 101 µL 5 M NaCl, water to 1 mL | purification |

FOB is the source's folding buffer: **1× TAE + 12.5 mM MgCl₂**. The PEG
buffer is its **15% PEG 8000, 1× TAE, 505 mM NaCl**. The volumes above are
arithmetic from those; the 5 M NaCl stock is a convenience, not the source's.

### 3. Set up three folding reactions and one control (20 min)

The source folds at **20 nM scaffold, each staple 10× over it (200 nM), in
1× TAE + 12.5 mM MgCl₂**. The reaction volume is not stated there; 50 µL is
ours. All three reactions are identical, so everything goes in one master
mix for four (three plus a spare), on ice:

| component | stock | per reaction | master mix (×4) |
|---|---|---:|---:|
| TAE | 10× | 5.00 µL | 20.0 µL |
| scaffold p7249 | 100 nM | 10.00 µL | 40.0 µL |
| staple pool | 595 nM each | 16.80 µL | 67.2 µL |
| MgCl₂ | 100 mM | 6.25 µL | 25.0 µL |
| water | | 11.95 µL | 47.8 µL |
| **total** | | **50.00 µL** | **200.0 µL** |

Mix gently by pipetting. Put **50 µL** in each of three tubes, A, B, C.

**Scaffold-only control**, one tube: 5.00 µL 10× TAE, 10.00 µL scaffold,
6.25 µL MgCl₂, 28.75 µL water. It shows where unfolded scaffold runs.

If your stocks differ, recompute with `V = C_final × V_total / C_stock`
(common-techniques §2) and write the stocks in the log.

> **A magnesium screen is not in the source.** It folds at 12.5 mM only, and
> this protocol does the same. If you and your supervisor want a bracket
> (for example 10 and 15 mM: 5.00 and 7.50 µL MgCl₂, with 13.20 and 10.70 µL
> water), that is **your** decision, not the source's: write it into
> `pre/plan.md` before committing, and fold 12.5 mM alongside it so the
> source's condition is always there to compare against.

### 4. Anneal (about 11.5 h)

The source's program, on a thermocycler with a heated lid:

| step | temperature | rate | time |
|---|---|---|---|
| 1 | 90 → 70 °C | −0.2 °C per 8 s | 13.3 min |
| 2 | 70 → 60 °C | −0.1 °C per 8 s | 13.3 min |
| 3 | 60 → 27 °C | −0.1 °C per 2 min | 11 h |
| 4 | → 20 °C | hold until you stop it | — |

The source does not state an initial hold at 90 °C (see *Open with the lab*).
Most thermocyclers take a ramp as a series of small steps; program it as
many 0.1–0.2 °C steps of the stated duration.

---

## Day 2 — Gel check, BEFORE any AFM (about 2 hours)

### 5. The gel

The source's conditions, not common-techniques §4:

- **Gel:** 2% (w/v) agarose in **1× TAE + 11 mM MgCl₂**.
- **Running buffer:** **1× TAE + 11 mM MgCl₂**, cold.
- **Stain:** the source used **ethidium bromide, 0.46 µg/mL** in the gel.
  Common-techniques §0 says not to use EtBr. Using SYBR Safe instead is a
  **deviation from the source**: decide with the lab before `pre/` is
  committed and write down which.
- **Samples:** the source loads **20 µL at 5 nM** origami plus **4 µL**
  loading dye (0.0083% bromophenol blue, 0.0083% xylene cyanol, 40%
  sucrose — EDTA-free). Our folds are 20 nM: **5 µL fold + 15 µL 1× FOB**,
  then 4 µL dye. The same for the scaffold-only control.
- **Run:** **90 V, 45 min, the tank on an ice bath.**
- **Lanes:** ladder · scaffold only · A · B · C · ladder. The ladder is not
  stated in the source; use your lab's 1 kb ladder and record it.

Photograph it, save the image to `during/raw/gel-day2.png`.

### 6. Read the gel

What you want is a **sharp band clearly distinct from the scaffold-only
lane**, with little in the well and little smear. Note in the log **whether
the folded band runs faster or slower than the scaffold**: a 390 nm rod need
not run like a compact sheet does in E1, and this protocol does not predict
the direction. The source's own gel figure is the reference for what a
folded 6HB looks like in these conditions — look at it before the session.

If there is **no band distinct from the scaffold** in any of A–C: stop here.
That is the result; go to *When it fails*.

---

## Day 2–3 — Purify (1 hour, then overnight)

### 7. PEG precipitation (the source's recipe)

1. Pool two reactions, A + B (100 µL). Keep C as unpurified reference.
2. **Dilute 4-fold with 1× FOB**: 100 µL + 300 µL FOB = 400 µL.
3. **Mix 1:1 with PEG buffer**: + 400 µL. Mix by gentle pipetting.
4. Centrifuge **14,000 × g, 30 min, room temperature.**
5. Remove the supernatant carefully; the pellet is often invisible.
6. Resuspend in **1× FOB to 0.25–1× the initial reaction volume** — the
   source's range. With 100 µL of reaction, 25–100 µL; pick one and record
   it.
7. **Overnight at 30 °C, shaking at 600 rpm**, to redissolve fully.

### 8. Quantify

A260 on the NanoDrop. The bundle has 14,305 nucleotides (7,249 scaffold +
7,056 staple), the rectangle 14,179, so common-techniques §6's conversion
holds within 1%: **1 A260 ≈ 11 nM**. Write the reading and the concentration
in the log.

---

## Day 3 — Deposit and image (1 hour plus the AFM session)

### 9. Measure the tip — before (20 min)

Common-techniques §8, exactly as in E1. Write
`tip.measured_radius_before_nm` into `during/instrument.json`. **Do not
skip it:** each rod's length is corrected by the tip broadening at both ends,
and `experiment rods` refuses to run without a measured radius.

### 10. Deposit (the source's recipe, 10 min)

1. Dilute the purified bundle to **about 1–2 nM**. The source deposits "the
   sample solution" and does not name a dilution buffer; 1× FOB is the
   obvious choice — confirm it with the lab and record it.
2. **20 µL** onto **freshly cleaved mica** (the source's is 15 × 15 mm,
   grade V1). **1 min** at room temperature.
3. Wash **three times with 100 µL deionized water**.
4. Dry thoroughly with a **direct nitrogen flow**.

This is dry imaging, as in the source (Bruker Dimension Icon, ScanAsyst in
Air). Dry imaging compresses DNA, which is why the height is compared with
E1's reference height rather than with 8 nm.

### 11. Image (2–3 h on the AFM)

| image | size | pixels | how many |
|---|---|---|---|
| overview | 2 × 2 µm | **1024** (≈ 2 nm/px) | until **≥ 100 rods**, from separate areas |

The source does not give a scan size; this one is set by the analysis. A
390 nm rod spans about 200 pixels at 1024 px, enough to trace its bending;
512 px (3.9 nm/px) also works on synthetic data, and 1024 costs little. Rods
touching the frame edge are not counted, so do not zoom in on single rods.
Save every native file to `during/raw/` untouched.

### 12. Measure the tip — after (20 min)

Repeat step 9 and write `tip.measured_radius_after_nm`.

---

## Day 4 — Analysis (about 1 hour)

### 13. Check the files

```bash
uv run dobladillo afm read experiments/<folder>/during/raw/scan-01.spm
```

Pixel size and scan size must match what you set (common-techniques §10).

### 14. Fill in the record

- `during/instrument.json`: every field, including both tip radii,
  `buffer.mgcl2_mm` (12.5, or what you used), and — from E1 —
  `reference.flat_height_nm` with `reference.from` naming E1's folder.
- `during/log.md`: complete, including the gel reading from step 6.

### 15. Run the analysis

```bash
uv run dobladillo experiment check experiments/<folder>
uv run dobladillo experiment rods experiments/<folder>
```

`experiment rods` traces the backbone of every particle, sorts them into
`rod`, `short`, `long` (usually two rods end to end), `branched` (crossings),
`compact` and `aggregate`, and writes `post/rods.json` with:

- **rod fraction** with a 95% interval;
- **contour length**, raw and tip-corrected, against 390.4 nm;
- **width**, raw and corrected by two tip models — reported, not judged: they
  differ by more than the diameter's own uncertainty;
- **height** of the rods, and its ratio to E1's reference height;
- the **tangent fit**: persistence length with a 95% interval, the intrinsic
  curvature with its interval, `systematically_curved`, `old_defect_excluded`,
  and a one-line verdict;
- an **end-to-end cross-check** of Lp. If it comes out far below the tangent
  fit's Lp, that disagreement is itself a sign of an arc.

It exits 1 if fewer than 100 rods were counted. Image more; do not lower the
number.

### 16. Judge against the gate, and commit

Read your gate in `pre/plan.md`, say in plain words whether each criterion
passed, write it in `post/report.md` under *Interpretation*, and commit
`during/` and `post/`.

---

## When it fails

| symptom | likely cause | what to try next — record it as a deviation |
|---|---|---|
| no band distinct from scaffold | staple pool wrong, or scaffold degraded | check the pool was mixed and has 168 staples; run scaffold alone against a fresh stock |
| everything in the well | aggregation | check the Mg and concentrations were as written; discuss a lower-Mg fold with the lab — a change from the source is a deviation |
| strong smear, weak band | misfolding | same as above; a slower final ramp is a deviation from the source |
| gel fine, no rods on mica | deposition | longer incubation or higher concentration (deviation); check the mica was freshly cleaved |
| many `short` rods | breakage in drying, nucleases, or incomplete folding | image a second deposition; nuclease-free technique (common-techniques §0) |
| many `long` rods | rods joined end to end | note it; `long` rods are excluded from the shape fit |
| many `branched` | too concentrated: rods crossing | dilute 2–5× |
| `afm read` shows the wrong pixel size | wrong channel or bad export | check `--channel`; for a `.gsf`, re-export and check the units |
| **rods systematically curved** | **the design bends** | **a real result.** Record it, image more, and tell the project with the radius and its interval. Compare it with 269 and 347 nm (the old routings) and with the beam model (straight) |

**A failure, properly recorded, is a result.** A curved bundle here would be
the most informative outcome E10 can have.

---

## Dry run on synthetic data

Walked through on 2026-09-28 with scans rendered by the toolchain (a known
answer, not data; the tip radius written in was the rendered one):

```bash
uv run dobladillo experiment new 2026-09-28-bundle-6hb --part bundle --root <scratch>
for i in 1 2 3 4; do
  uv run dobladillo afm synthetic --part bundle --seed $i --rectangles 32 --realistic \
    --out <scratch>/2026-09-28-bundle-6hb/during/raw/scan-0$i.gsf
done
# experiment rods refused: kind no_tip_radius. Tip written into instrument.json, then:
uv run dobladillo experiment rods <scratch>/2026-09-28-bundle-6hb
```

| rendered | recovered |
|---|---|
| 128 rods, 8 half-length fragments, 8 aggregates | 126 rods, 8 short, 8 aggregate (2 rods lost to the frame edge) |
| contour 390.4 nm | 390.8 nm tip-corrected: agrees |
| straight, Lp 1500 nm | no arc detected, any intrinsic radius above 1.18 µm; Lp 1697 nm [1354, 2230]; old arcs excluded |
| the same, every rod curved at 347 nm | curved, radius 346–434 nm (95%); old arcs NOT excluded |

`lab order bundle` writes a valid order: 168 staples on two 96-well plates,
7,056 bases, files validated.

---

## Open with the lab — settle before `pre/` is committed

Each of these is **not stated in the source**; none is filled in here from
memory.

1. **Initial denaturation** before the 90 °C ramp: whether to hold, and how
   long.
2. **Magnesium screen**: the source has none. Fold at 12.5 mM only, or add a
   bracket (your decision, written in `pre/plan.md`).
3. **Gel stain**: the source's ethidium bromide or your lab's SYBR Safe (a
   deviation either way from one of the two documents; decide and record).
4. **Ladder** for the gel.
5. **Deposition dilution buffer** (1× FOB is the obvious reading).
6. **Resuspension volume** after PEG, within the source's 0.25–1×.
7. **AFM imaging mode and probe** on your instrument, if not the source's
   ScanAsyst in Air.

## What to hand over

- `pre/` (committed before the session, with the gate)
- `during/raw/`: the gel photo, native AFM files
- `during/instrument.json` complete: both tip radii, magnesium, E1's
  reference height
- `during/log.md`, including the gel reading and every item from *Open with
  the lab* as you settled it
- `post/rods.json` from `dobladillo experiment rods`, and `post/report.md`
  with your interpretation against the gate
