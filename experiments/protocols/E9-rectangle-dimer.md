# E9 — The rectangle dimer: do two origami assemble as designed?

**Folder:** make it with `dobladillo experiment new <date>-rectangle-dimer --part dimer`
**Run after:** E1 — you need its **magnesium**, its **reference height** and its **plates**
**Time:** about 4 working days plus 3–5 days for oligo delivery
**Cost:** about €198 of extra staples, if your lab already has E1's plates
**Read first:** [`common-techniques.md`](common-techniques.md), then [E1](E1-rectangle-afm.md)

---

## What you are testing, and why it matters

Everything folded in this project so far is one object from one tube. E9 is the
first experiment where **two separately folded origami have to find each other
and join** — which is what every larger structure is made of, and the step
where published yields stop being near 100%.

Two rectangles, A and B. Each is E1's rectangle, folded on its own. A's right
edge carries eleven single-stranded "sticky ends"; B's left edge carries their
complements. Mixed, an A and a B should join end to end and appear on the AFM
as one sheet twice as long and the same width.

The readout is not one number. It is a **distribution over assembly states** —
monomer, dimer, larger aggregate, malformed — measured on each sample, with an
interval on each fraction, and the question is whether that distribution comes
out the same from one mix to the next.

### What makes this hard, and what the design does about it

**Blunt-ended helices stick together.** A rectangle's edges are 22 helix ends,
and Rothemund (2006, Supplementary Note S5.7) found that rectangles stack "so
strongly that they may form long chains over 5 microns in length". Liber et al.
(2018) measured dimerisation yields that never exceeded 86% and traced the
ceiling to monomers self-dimerising through exactly this. So in our design:

- the **outer** edges (A's left, B's right) carry a **TTTT tail on every staple
  end that sits on the edge** — Rothemund's own fix, which on 3-hole disks
  "almost completely abolishes stacking and aggregation";
- the **mating** edges carry a TTTT tail on one end and a sticky end on the
  other, so no helix end anywhere is left blunt.

**Excess staples cap the ends.** Every sticky end has a free complement in the
folding reaction — as a staple, or as its own partner if you mixed the pools.
Unpurified, those cap the edge and the dimer cannot form. Purification before
mixing is not a tidying step here; it is the experiment.

**Two monomers that land end to end look exactly like a dimer.** A 4 nm bridge
is smaller than the AFM tip, so no footprint can tell them apart, and the
analysis does not pretend to. That is why **A alone and B alone are imaged in
the same session**: their apparent dimer fraction is the false-positive rate,
and every mixture is reported against it.

## What is predicted

| property | predicted | on the AFM |
|---|---|---|
| monomer | 106.2 × 66.0 nm | wider by the tip broadening |
| dimer | 216.5 × 66.0 nm | twice as long, no wider |
| height | about 2 nm (E1's measured reference height) | lower if imaged dry |
| gap between the two | 4.0 nm | not resolved |
| **yield** | **not predicted** | this experiment measures it |

Nothing in the toolchain predicts how many dimers form. The published range for
sticky-end dimerisation of rectangles is wide and design-dependent: 7–23% for
short (5-nt) sticky ends (Zou 2023), 75–80% (Zenk & Schulman 2016), up to 86%
(Liber 2018), 81–92% for 11-nt connectors (Wang 2025), and 98.6–99.6% with
gel-purified monomers against 88.7–96.7% with PEG (Sheheade 2019). Ours has
eleven 12-nt sticky ends. Write down what you expect **before** you look.

## A gate proposal

**You write the gate**, in `pre/plan.md`, before the session. This is a
proposal to argue with, not the gate:

- **controls:** A alone and B alone each report a dimer fraction of **10% or
  less**. Above that, the tails are not holding or the sample is too crowded,
  and no yield from the mixture means anything.
- **assembly:** the mixture's dimer fraction is above the controls' with a 95%
  interval excluding zero.
- **reproducibility:** three replicate mixes share one distribution of states
  (the chi-square test the analysis reports, p > 0.05), and no state's fraction
  spreads by more than 10 points across them.
- **counting:** at least **100 counted particles per sample**, 300 if the AFM
  session allows. The analysis exits non-zero below 100.
- **failure:** a mixture indistinguishable from the controls means the
  interface did not work — that is a result, and the first suspects are the
  purification and the mixing temperature, not the sequences.

> **Decide the control threshold before the session.** 10% is a judgement. If
> your imaging is crowded, coincidence alone can exceed it; if you image
> sparsely, 5% may be the right number. Agree it with your supervisor, write it
> in `pre/plan.md`, and commit.

---

## Checklist before you start

- [ ] E1 finished: you have its **magnesium (M)**, its **reference flat-sheet
      height**, and its **staple plates**.
- [ ] `pre/plan.md` read; the gate is written and final; `pre/` committed:
      `git add experiments/<folder>/pre && git commit -m "E9: pre-register"`
- [ ] Extras ordered from `pre/order/dimer-a_extra_plates.xlsx` and
      `dimer-b_extra_plates.xlsx` (44 oligos; supervisor approved).
- [ ] `pre/order/dimer_pools.json` printed or open: it lists, per component,
      which E1 wells to pool and **which to skip**.
- [ ] Scaffold p7249 in stock; its concentration known.
- [ ] AFM booked for a single session long enough for **all** samples, with the
      same tip.
- [ ] A tip-characteriser sample available.

---

## Day 1 — Two pools, two folds, one gel (about 5 hours)

### 1. Make two pools — and skip the right wells (1 h)

This is the step where E9 goes wrong. A pool made for E1 contains E1's **plain
edge staples**. Fold A from it and the plain staple competes with the extended
one for the same site: part of A's mating edge comes out blunt, capped, and
ready to stack instead of to bind.

**Do not use an existing E1 pool.** For each component, pool fresh from E1's
plates:

1. Open `pre/order/dimer_pools.json`. For component A it lists 198 wells to
   take and **22 wells to skip**, by plate and well; the same for B.
2. Pool an equal volume (for example 5 µL) from each of the 198 listed E1
   wells.
3. Add the same volume from each of the 22 wells of that component's extras
   plate.
4. Mix by pipetting, brief vortex, spin down. Label **"dimer A"** or
   **"dimer B"**, with the date and "220 staples".

Each pool then holds 220 staples, so with 100 µM wells each staple is
**455 nM** — the same as E1's pool, and E1's volumes below apply unchanged.

> **Keep the two pools apart.** A's extras are not B's. A drop of B's pool in
> A's puts both halves of a bond on one edge, which is a designed
> self-dimeriser.

### 2. Fold A and B separately, at three magnesium concentrations (45 min)

Call E1's magnesium **M**. Fold both components at **M − 2**, **M** and
**M + 2** mM, then use **the same magnesium for both**. The shape is E1's, so M
should work; the extensions are new, and this checks it cheaply.

As in E2, make one **base mix per magnesium** that both components share — any
error in the base is then common to both and cancels:

| component | stock | per reaction | base mix (×2.5) |
|---|---|---:|---:|
| folding buffer | 10× | 5.0 µL | 12.5 µL |
| scaffold p7249 | 100 nM | 5.0 µL | 12.5 µL |
| MgCl₂ | 100 mM | V_Mg | 2.5 × V_Mg |
| water | — | 34.5 − V_Mg | 2.5 × (34.5 − V_Mg) |
| **total** | | **44.5 µL** | **111.3 µL** |

where `V_Mg = Mg_mM × 50 / 100` — at 13 mM, 6.5 µL of MgCl₂ and 28.0 µL of
water per reaction.

Put **44.5 µL** of base mix in two tubes; add **5.5 µL** of the *dimer A* pool
to one and **5.5 µL** of *dimer B* to the other. 50 µL each. Repeat for the
other two magnesium levels: six reactions. Also one scaffold-only control at M.

If your stocks differ, recompute with `V = C_final × V_total / C_stock`
(common-techniques §2) and write the stocks in the log.

### 3. Anneal (35 min)

Common-techniques §3, all seven tubes in the **same** run: 65 °C for 15 min,
60 → 40 °C at 1 °C/min, hold at 4 °C.

### 4. Gel — both components on one gel (2.5–3 h)

Common-techniques §4. Lanes: ladder · scaffold only · A at M−2, M, M+2 · B at
M−2, M, M+2 · ladder. Save the photograph to `during/raw/gel-day1.png`.

### 5. Pick one magnesium for both

The **lowest** at which both give a sharp folded band with little smear. Write
it in the log.

> **A monomer band in this gel is what you want.** If a folding lane already
> shows a band running slower than the monomer, the components are dimerising
> during the anneal — most likely the pools were crossed. Note it; it changes
> how Day 3's gel reads.

---

## Day 2 — Purify, quantify, mix (about 3 hours plus the incubation)

### 6. Purify both, at the chosen magnesium (1.5 h + ≥1 h)

**PEG precipitation** (common-techniques §5), both tubes treated identically,
side by side. Redissolve in 1× folding buffer with the chosen magnesium.

> **Why this step is the experiment.** The staples left in solution include
> every sticky end's complement. Leave them and they cap the edges; then no
> dimer forms and the result looks like a failed interface. Sheheade et al.
> (2019) measured this: heterodimerisation yields were 88.7–96.7% after PEG,
> and 98.6–99.6% after gel purification in 100 mM NaCl, which also breaks up
> the monomers that had already stacked.
>
> **One round of PEG is the minimum. Two is better** (Sheheade found each round
> cuts the incorrect structures further), and a **100 kDa spin filter with
> four to five buffer exchanges** (common-techniques §5) is an equivalent
> fallback — Wang et al. (2025) used four. If your controls come back with a
> high dimer fraction, purification is the first thing to change. Record which
> method and how many rounds.

### 7. Quantify (15 min)

A260 on the NanoDrop, each component. **1 A260 ≈ 11 nM** (common-techniques
§6). Dilute both to the **same** concentration. Write both readings in the log.

### 8. Set up the mixtures (30 min)

Mix **A and B at 1:1 by moles**, at **2 nM each**, in 1× folding buffer with
the chosen magnesium. 1:1 matters: an excess of either caps the other's ends
with half-formed pairs.

The sticky ends were designed for this buffer and this concentration — eleven
12-nt bonds, each melting near 30–37 °C at 2 nM in 11 mM free magnesium — so
changing the concentration changes the design's own predictions. If you must
change it, say so in the log.

Prepare, in parallel:

| sample | what it is | why |
|---|---|---|
| **A** | purified A alone, 2 nM | control: false-positive dimers |
| **B** | purified B alone, 2 nM | control: the same, for B |
| **R1, R2, R3** | three independent A + B mixes | the reproducible distribution |
| **T15m, T1h, T4h, T24h** | one mix, sampled over time | the time series (step 9) |

The three replicates are **separate mixes**, not three aliquots of one: three
aliquots measure the imaging, not the assembly.

### 9. Incubate — and take a time series (24 h)

Hold the mixtures at **25 °C**. Take the time-series aliquots at **15 min,
1 h, 4 h and 24 h**, and put each on mica (step 11) or keep it at 4 °C until
you image, noting which.

> **Why a series at all.** "A reproducible distribution" needs something for
> the distribution to be reproducible *about*. A time course shows assembly
> rising towards a plateau, so three replicates agreeing at the plateau means
> something; three replicates agreeing at 15 minutes might just mean nothing
> had happened yet.
>
> **Choose one series.** A **magnesium series** (8, 12, 16 mM at fixed time)
> is the alternative and is just as good — magnesium sets both the folding and
> the interaction — but do not run both in one session. Name those samples
> `Mg08`, `Mg12`, `Mg16`.

Isothermal at 25 °C is the published condition for sticky-end dimerisation
(Zou et al. 2023: 25 °C for 12 h at 4 nM). **Do not re-anneal the mixture.**
Wang et al. (2025) annealed 45 → 25 °C over 12 h, which works, but a ramp past
the monomers' own folding range risks re-opening them, and this experiment
cannot separate that from a failed interface.

---

## Day 3 — Gel, then image (about 1 hour plus the AFM session)

### 10. Gel the mixtures (2.5–3 h)

Common-techniques §4. Lanes: ladder · A · B · R1 · the time points in order ·
ladder.

| what you see | what it means |
|---|---|
| a band **above** the monomer band, in the mixes only | the dimer — what you are looking for |
| that band also in the A or B lane | self-dimerisation: purification or crossed pools |
| the upper band growing along the time series | assembly proceeding |
| everything in the well | aggregation; lower the magnesium or dilute |

Photograph it to `during/raw/gel-day3.png`. **The gel is a hint, not the
readout** — it cannot tell a dimer from two stacked monomers, and the AFM count
is what the gate is written against.

### 11. Tip radius — before (20 min)

Common-techniques §8. Write it into `during/instrument.json` as
`tip.measured_radius_before_nm`. **The analysis refuses to run without it**,
and here it is not only the dimensions: the monomer and dimer footprint
windows are set by the tip radius, so a guess moves the classification itself.

### 12. Deposit and image every sample — same tip, same settings

Each sample on its own freshly cleaved mica, **the same method and the same
waiting time for all of them** (common-techniques §7). Dilute to 1–2 nM in 1×
buffer with 10 mM MgCl₂.

Image the **controls first**, while the tip is sharpest: they set the
false-positive rate everything else is compared against.

| image | size | pixels | per sample |
|---|---|---|---|
| overview | 2 × 2 µm | 512 | enough for **300 particles**, 100 as the floor |
| detail | 500 × 500 nm | 512 | 3 or more |

**Name the files by sample**, because that is how the analysis finds them:
`A-01.spm`, `B-01.spm`, `R1-01.spm`, `R2-01.spm`, `T15m-01.spm`, … — the sample
name, a hyphen, a two-digit number. Save every native file to `during/raw/`
untouched.

> **Deposit sparsely.** Crowding is this experiment's worst enemy: two monomers
> that land end to end are counted as a dimer. Aim for particles clearly
> separated in a 2 × 2 µm image, and if the controls come back crowded, dilute
> and redo **every** sample the same way.

### 13. Tip radius — after (20 min)

Repeat step 11 into `tip.measured_radius_after_nm`. If the tip blunted a lot,
say so in the log: the analysis widens its uncertainty accordingly.

---

## Day 4 — Analysis (about 1 hour)

### 14. Check every file

```bash
uv run dobladillo afm read experiments/<folder>/during/raw/A-01.spm
```

Pixel size and scan size must match the instrument. If a format is not read,
export a `.gsf` of the **height** channel from Gwyddion **next to** the native
file (never instead of it); exports beside native files are ignored, so nothing
is counted twice.

### 15. Fill in the record

In `during/instrument.json`:

- both tip radii;
- `buffer.mgcl2_mm` — the magnesium that actually went on the mica;
- E1's reference height, and where it came from:

```json
"reference": {
  "flat_height_nm": 1.3,
  "from": "experiments/2026-09-22-rectangle-afm/post/report.md"
}
```

(an example of the shape, not a value to copy). And `during/log.md` complete:
pools, purification method **and number of rounds**, the mixing concentration,
the incubation temperature, every time point.

### 16. Run the analysis

```bash
uv run dobladillo experiment check experiments/<folder>
uv run dobladillo experiment assembly experiments/<folder>
```

It writes `post/assembly.json` and prints, per sample: the counts of monomer,
dimer, larger and malformed with 95% Wilson intervals; each mixture's dimer
fraction **above the controls**, with a 95% interval; and a chi-square test of
whether the replicates share one distribution.

If it stops and says the tip radius or the reference height is missing,
**measure it** — do not type in the nominal value. If it says there are no
controls, image A and B alone; without them a dimer fraction cannot be told
from background.

It **exits non-zero** when a sample has fewer than 100 counted particles. That
is not a warning to ignore: image more.

> `experiment check` will report `post` as incomplete for this folder — it
> looks for E1's `measurements.json`, and E9's output is `assembly.json`. E2 is
> the same. Everything it says about `pre`, `during` and the provenance chain
> applies normally.

### 17. Write the interpretation, and judge the gate

In `post/report.md`, in your own words:

- the controls' dimer fraction, and whether it met your threshold;
- each mixture's dimer fraction and how far above the controls it sits;
- the three replicates: do they agree? What does the chi-square say?
- the series: does assembly rise and plateau?
- the classes nobody wants: how many *larger* particles, how many *malformed*,
  how many excluded as side-by-side pairs. A rising *larger* count along the
  series is polymerisation, which means the tails are not enough.

Then read the gate in `pre/plan.md` and say, criterion by criterion, whether it
passed. Commit `during/` and `post/`.

---

## Before the session: walk it through on synthetic data

The whole chain runs on scans of known contents, so you can see what a good
result looks like — and check your own commands — before a pipette is touched:

```bash
uv run python experiments/protocols/e9_dryrun.py --dimer-fraction 0.6
```

It builds a complete folder in a temporary directory, renders controls, three
replicates and a time series with a dimer fraction you choose, runs the real
analysis over them, and prints what was recovered against what was put in. Add
`--out <dir>` to keep the folder and look at it. It accepts no real data and
marks everything it writes as synthetic.

Worth trying: `--dimer-fraction 0`, where the replicates come out
indistinguishable from the controls and that gate criterion fails — which is
what a failed interface looks like; and `--touching 4`, which places unbonded
monomers end to end until the controls themselves break the 10% threshold,
showing you the false-positive rate no footprint can remove.

---

## When it fails

| symptom | likely cause | what to try — record it as a deviation |
|---|---|---|
| no dimer band, few dimers on the AFM | excess staples still capping the ends | purify again: a second PEG round, or gel purification in 100 mM NaCl (Sheheade 2019) |
| the same, after purification | mixing too cold or too short | hold 25 °C longer; check the 24 h point before concluding |
| controls show many dimers | blunt-end stacking, or crowding | check the pools were made skipping the right wells; deposit more dilutely; purify again |
| a dimer band in a *folding* lane on Day 1 | the two pools were crossed | remake both pools from the plates |
| many *larger* particles, rising with time | polymerisation: the outer edges are stacking | note it; the design has a `blunt` and an `omit` variant of the outer edge, and this is the result that decides between them |
| many particles excluded as side-by-side | too concentrated on the mica | dilute 2–5× and redo every sample identically |
| monomers look right, dimers are kinked or L-shaped | the joint is flexible; they land bent | expected in part; they count as *malformed*, and the report splits them by area so a two-rectangle kink is visible |
| fewer than 100 particles per sample | sparse deposition | longer incubation or higher concentration — **the same change for every sample** |
| `experiment assembly` says no controls | the files are not named `A-*` / `B-*` | pass the right folder; do **not** rename raw files — copy the naming next time |

**A failure, properly recorded, is a result.** A mixture that does not
assemble, with clean controls and a purification you can describe, is a real
measurement of this interface.

---

## What to hand over

- `pre/` committed before the session, gate filled in
- `during/raw/`: both gel photographs, native AFM files named by sample
- `during/instrument.json`: both tip radii, the magnesium used, E1's reference
  height and where it came from
- `during/log.md`: pools (including the wells skipped), purification method and
  rounds, mixing concentration and ratio, incubation temperature, time points
- `post/assembly.json` and `post/report.md` with your interpretation
- for whoever comes next: the **dimer fraction of the controls**, and the
  purification method that produced it. That number is what any later
  multi-origami experiment in this project will be measured against.

---

## References

Read, not cited from memory:

- Rothemund, *Nature* **440**, 297 (2006), and its Supplementary Notes — §5.7
  on blunt-end stacking, the 4-T tails, and omitting edge staples.
- Woo & Rothemund, *Nature Chemistry* **3**, 620 (2011) — stacking bonds as
  programmable interfaces; the alternative to sticky ends.
- Zenk, Tuntivate & Schulman, *JACS* **138**, 3346 (2016) — sticky-end
  dimerisation of rectangles: linker number, sticky-end length, 75–80% yields.
- Liber, Tomov, Tsukanov, Berger, Popov, Khara & Nir, *Small* **14**, e1800218
  (2018) — yields never above 86%; self-dimerisation via blunt ends.
- Sheheade, Liber, Popov, Berger, Khara, Jopp & Nir, *Small* **15**, e1902979
  (2019) — purification decides the yield: 98.6–99.6% gel-purified against
  88.7–96.7% PEG.
- Zou & Clark, *ACS Nano* **17**, 752 (2023) — the DNA-only control: 5-nt
  sticky ends, 25 °C, 12 h, 4 nM, 7–23% dimers.
- Wang, Xie, Ouyang, Li, Wang, Fan & Chao, *Nature Communications* **16**, 263
  (2025) — 11-nt sticky ends on a Rothemund rectangle, 81–92% dimers by AFM.
