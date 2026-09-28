# E3 — The single hinge: does it fold at all?

**Folder:** create it (step 0)
**Run after:** E1 — you need its magnesium and reference height
**Time:** about 3 working days plus oligo delivery
**People:** you plus **a second scorer** for the counting
**Read first:** [`common-techniques.md`](common-techniques.md), then E1

---

## What you are testing, and why it matters

The hinge is the first design in this project meant to **move**. Two flat arms
(each 12 helices, about 64 × 36 nm) are joined along one edge by a stretch of
unpaired scaffold — 8 bases per helix — that acts like the pin of a door hinge.
A short DNA "latch" (8 bases, `GCATGCAT` and its complement) sits on the outer
edges of the two arms and can zip them shut.

Later experiments (E4–E6) measure how often the hinge is open or closed. All of
them assume it folds. **Nobody has checked.** E3 is the cheapest possible check:
one design, one fold, one gel, one AFM session. If the hinge does not fold,
eight constructs' worth of later experiments cannot be ordered.

The riskiest part is the joint: eight unpaired bases across twelve helices is
a lot of unpaired scaffold, and unpaired scaffold is where origami misfolds.

## What to expect

| form on the mica | footprint | height |
|---|---|---|
| **closed** — arms stacked on each other | about 64 × 36 nm | about **twice** a flat sheet |
| **open** — both arms visible, at any angle | two joined lobes, each about 64 × 36 nm | one flat sheet |
| single sheet | one lobe, about 64 × 36 nm | one flat sheet |
| aggregate | large, irregular | tall |

Add the tip broadening to every width (about 9 nm on a 2 nm sheet with a 10 nm
tip — common-techniques §8).

**Also expect a halo.** The design uses 4,632 of the scaffold's 7,249 bases;
the other **2,617 bases stay unpaired** as a loop. On the AFM that loop can
appear as a low, fuzzy blob attached to a particle. It is expected. Do not
count it as a separate particle.

The latch is predicted to hold the hinge mostly closed in solution, but mica
can pry it open or flatten it. **Open versus closed is not the question here**
— E4 measures that properly. Record it anyway.

---

## 0. Create the experiment folder and write the gate

```bash
uv run dobladillo experiment new 2026-MM-DD-single-hinge --part hinge --root experiments
```

Replace the date. Then write the gate in `pre/plan.md` **with your
supervisor**. The roadmap proposes:

> **Fold.** A dominant gel band distinct from free scaffold.
> **Shape.** Among at least 100 counted particles, a majority show two arms
> (open or closed). Shape, not size: the angle of an open hinge on mica is
> unknown, so its footprint is not predicted.
> **Fail.** No distinct band, or two-armed objects are a small minority.

Agree on the numbers — what "a majority" and "a small minority" mean — before
the session, write them in, and commit `pre/`.

---

## Checklist before you start

- [ ] E1 finished; you have its magnesium and reference flat-sheet height.
- [ ] Folder created, gate written, `pre/` committed.
- [ ] Oligos ordered from the new folder's `pre/order/hinge_plates.xlsx`.
- [ ] A second scorer is available on Day 3 for about an hour.

---

## Day 1 — Fold and check (about 4 hours)

### 1. Staple pool

All **132** staples, equal volumes (common-techniques §1). With 100 µM wells,
each staple is **758 nM** in the pool.

### 2. Nine folding reactions

The hinge is a different shape from the rectangle, so screen the full range.

Master mix for 10 reactions, on ice:

| component | stock | per reaction | master mix (×10) |
|---|---|---:|---:|
| folding buffer | 10× | 5.0 µL | 50.0 µL |
| scaffold p7249 | 100 nM | 5.0 µL | 50.0 µL |
| staple pool | 758 nM each | 3.3 µL | 33.0 µL |
| **total** | | **13.3 µL** | **133.0 µL** |

Put **13.3 µL** in each of nine tubes, then add:

| tube | MgCl₂ final | 100 mM MgCl₂ | water | total |
|---:|---:|---:|---:|---:|
| 1 | 5 mM | 2.5 µL | 34.2 µL | 50 µL |
| 2 | 7 mM | 3.5 µL | 33.2 µL | 50 µL |
| 3 | 9 mM | 4.5 µL | 32.2 µL | 50 µL |
| 4 | 11 mM | 5.5 µL | 31.2 µL | 50 µL |
| 5 | 13 mM | 6.5 µL | 30.2 µL | 50 µL |
| 6 | 15 mM | 7.5 µL | 29.2 µL | 50 µL |
| 7 | 17 mM | 8.5 µL | 28.2 µL | 50 µL |
| 8 | 19 mM | 9.5 µL | 27.2 µL | 50 µL |
| 9 | 20 mM | 10.0 µL | 26.7 µL | 50 µL |

Plus a scaffold-only control at 13 mM.

### 3. Anneal

Common-techniques §3.

### 4. Gel

Common-techniques §4, lanes: ladder · scaffold only · tubes 1–9 · ladder.

**What is different from E1.** A hinge is floppier than a rectangle, so its
band may be broader. The 2,617-base unpaired loop makes it run slower than a
fully folded object of the same mass would. Unpaired scaffold is also sticky at
high magnesium — watch the wells in tubes 7–9.

### 5. Pick the condition

The lowest magnesium with a distinct, reasonably sharp band and little in the
well. Record it and why.

---

## Day 2 — Purify, deposit, image

Exactly as E1 steps 6–11: PEG purification at the chosen magnesium, A260
(**1 A260 ≈ 13 nM** for the hinge), tip radius before, deposit at 1–2 nM,
image, tip radius after.

Imaging: 2 × 2 µm overviews until you have **at least 100 particles**, and
500 × 500 nm details of 10 or more particles, which the scorers will use to
decide ambiguous cases. **Use the same imaging mode as E1** (dry or liquid),
so E1's reference height applies.

---

## Day 3 — Counting, by two people independently (about 1 hour each)

There is no automatic classifier for hinges yet (the software cannot predict
the footprint of an open hinge at an unknown angle). So two people count, and
their agreement tells you whether the categories are clear enough to trust.

### 6. Prepare the images

Export `.gsf` copies and check them with `dobladillo afm read`
(common-techniques §10). Open the overviews in Gwyddion with the same colour
scale for all.

### 7. The scoring rules — agree on them before scoring

| category | rule |
|---|---|
| **closed** | one lobe of hinge-arm size, clearly taller than E1's flat reference height |
| **open** | two lobes of arm size, joined at one edge, each at about the flat height |
| **single** | one lobe of arm size at flat height |
| **aggregate** | much larger than one hinge, or much taller than two layers |
| **unclear** | cannot decide — use this rather than guessing |

Particles touching the image edge are **not scored**. A fuzzy low blob attached
to a particle is the scaffold loop, not a separate particle.

### 8. Score independently

Each scorer fills in a copy of this table, **without looking at the other's**:

```
scorer,image,particle_id,x_px,y_px,category,note
```

Save as `during/raw/scores-<initials>.csv`. Number the particles on a printed or
annotated image first, so both scorers score the same particles.

### 9. Compare the two scorers

Agreement = the fraction of particles on which both chose the same category.

- **80% or more:** the categories are clear. Use the first scorer's counts.
- **Below 80%:** the rules are ambiguous. Look at the disagreements together,
  write the clarified rule into the log, and **both re-score** from scratch.

Record the agreement in the log. It is part of the result.

### 10. The number

Two-armed fraction = (open + closed) / (all scored, excluding "unclear"). Get
its 95% interval:

```bash
uv run python -c "from dobladillo.imaging.classify import Fraction; print(Fraction(COUNT, TOTAL).as_dict())"
```

Replace `COUNT` and `TOTAL`. Write the counts per category, the agreement, the
two-armed fraction and its interval into `post/report.md`, judge against the
gate, and commit.

---

## When it fails

| symptom | likely cause | what to try — record it as a deviation |
|---|---|---|
| no distinct band at any magnesium | the joint misfolds | a shorter joint (4 nt) is the first fallback — a new design; tell the project |
| everything in the wells | sticky unpaired scaffold at high Mg | use the low-magnesium tubes; fold at 5 nM scaffold |
| mostly single sheets | one arm not folding, or arms separating on mica | look at the detail images; try imaging in liquid |
| mostly closed, almost never open | the latch holds on mica | a result for E4 — record the ratio |
| scorers disagree badly even after re-scoring | the forms really are ambiguous at this resolution | take more 500 × 500 nm detail images and score from those |

---

## What to hand over

- `pre/` committed before the session, with the gate
- `during/raw/`: gel photo, native files, `.gsf` exports, **both score sheets**
- `during/instrument.json` and `during/log.md`, with the scorer agreement
- `post/report.md` with counts, agreement, the two-armed fraction and interval
