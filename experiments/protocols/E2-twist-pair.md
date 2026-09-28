# E2 — The twist pair: is the twist correction needed?

**Folder:** `experiments/2026-09-23-twist-pair/`
**Run after:** E1 — you need its magnesium and its reference height
**Time:** about 3 working days plus 3–5 days for oligo delivery
**Cost:** about €1,372 of staples for both arms
**People:** you, plus **one other person** to hold the blinding key
**Read first:** [`common-techniques.md`](common-techniques.md), then E1

---

## What you are testing, and why it matters

Every flat design in this project uses a *square lattice*, which winds DNA to
10.67 base pairs per turn. Relaxed DNA wants 10.5. The difference builds up
along the helix and twists the sheet. The fix used everywhere in this project
is to **delete one base every 64**, which cancels the twist exactly on paper.

E2 asks whether the fix is needed. It uses two constructs that are identical
except for those deletions:

| | arm A — corrected | arm B — uncorrected |
|---|---|---|
| deletions | 108, one every 64 | none |
| size | 191 × 36 nm, 12 helices | 191 × 36 nm, 12 helices |
| staples | 216 | 216 |
| predicted | lies flat | carries 309° of twist; cannot lie flat |

**Why a pair.** One measurement that agrees with a prediction can agree by
luck. A pair measures the *difference* between two constructs made and imaged
together, which cancels every shared source of error at once: the same
scaffold, buffer, anneal, operator, tip and session.

### The trap you must avoid

**Mica flattens what it adsorbs.** A twisted sheet stuck to mica is usually
pressed flat, not left standing on edge. So the question is *not* "does this
particle look twisted?" — it is **what fraction of particles lie flat as a
clean rectangle, in each arm.** A sheet that could not lie flat shows up as
rolled, folded or with a raised ridge: the right footprint, but taller than a
flat sheet. The analysis calls those *twisted*.

### Three outcomes, all of them results

| outcome | what it means |
|---|---|
| corrected arm lies flat much more often | the correction works and is needed |
| **the two arms are indistinguishable** | **the correction is unnecessary**, and it comes out of every square-lattice design — the most useful outcome if it happens |
| the uncorrected arm lies flat more often | something about the deletions is wrong; the constant they come from needs revisiting |

## The gate

Written in `pre/plan.md`; read it now. In short: both arms in the same session
with the same tip; **at least 100 counted particles per arm, 300 if cheap**; a
pass is a difference of more than 10 points in flat fraction with a 95%
interval excluding zero — *or* the two arms being indistinguishable.

---

## Blinding: why, and how

If you know which sample is which while you image and count, you will — without
meaning to — pick nicer fields for the arm you expect to be flat. Blinding
removes that.

1. After purification (Day 2, step 7), **hand both tubes to a second person.**
2. They relabel them **X** and **Y** by a coin flip, and write the key
   ("X = corrected" or "X = uncorrected") on a card, sealed in an envelope, or
   in a message to your supervisor. **Not in the repository.**
3. You deposit, image and analyse knowing only X and Y.
4. The key is opened **after** the analysis is written into `post/report.md`.

Write in the log who holds the key.

---

## Checklist before you start

- [ ] E1 finished; you have its **magnesium** and its **reference flat-sheet
      height**.
- [ ] `pre/plan.md` read; gate final; `pre/` committed:
      `git add experiments/2026-09-23-twist-pair/pre && git commit -m "E2: pre-register"`
- [ ] Both arms ordered: `pre/order/twist-corrected_plates.xlsx` **and**
      `pre/order/twist-uncorrected_plates.xlsx`. Keep the plates separate.
- [ ] A second person has agreed to hold the blinding key.
- [ ] AFM booked for a single session long enough for both samples.

---

## Day 1 — Fold both arms and check (about 4 hours)

### 1. Two staple pools (45 min)

Make **one pool per arm**, never mixed (common-techniques §1). With 216
staples at 100 µM, each staple is **463 nM** in its pool. Label them
"corrected" and "uncorrected" — the blinding comes later.

### 2. Fold at three magnesium concentrations around E1's (30 min)

Call E1's magnesium **M**. Fold both arms at **M − 2**, **M** and **M + 2** mM.
The arms have a different shape from E1's rectangle, so check that M still
works — and use **the same magnesium for both arms** in the end.

For each magnesium, make one **base mix** that both arms share. Sharing it is
what makes the pair a fair comparison: any error in the base is common to
both arms and cancels.

Base mix for one magnesium level (2 reactions + half spare = ×2.5), on ice:

| component | stock | per reaction | base mix (×2.5) |
|---|---|---:|---:|
| folding buffer | 10× | 5.0 µL | 12.5 µL |
| scaffold p7249 | 100 nM | 5.0 µL | 12.5 µL |
| MgCl₂ | 100 mM | V_Mg | 2.5 × V_Mg |
| water | — | 34.6 − V_Mg | 2.5 × (34.6 − V_Mg) |
| **total** | | **44.6 µL** | **111.5 µL** |

where `V_Mg = Mg_mM × 50 / 100` — for example 13 mM gives 6.5 µL of MgCl₂ and
28.1 µL of water per reaction.

Put **44.6 µL** of base mix into two tubes, then add **5.4 µL** of the
*corrected* pool to one and **5.4 µL** of the *uncorrected* pool to the other.
Total 50 µL each. Repeat for the other two magnesium levels: six reactions.

Also make one scaffold-only control at M.

### 3. Anneal (35 min)

The same program as E1 (common-techniques §3). All seven tubes in the **same
run**.

### 4. Gel — both arms on one gel (2.5–3 hours)

Common-techniques §4. Lane order: ladder · scaffold only · corrected at M−2, M,
M+2 · uncorrected at M−2, M, M+2 · ladder. Save the photo to
`during/raw/gel-day1.png`.

### 5. Pick one magnesium for both

The lowest magnesium at which **both** arms give a sharp folded band. Write it
in the log.

> **Look at the gel for the answer's first hint, and do not act on it.** If
> the uncorrected arm runs noticeably differently — slower, more smeared — that
> is consistent with it being twisted. Write it down. It does not replace the
> AFM count, and it must not change how you image.

---

## Day 2 — Purify, blind, image (about 2 hours plus the AFM session)

### 6. Purify both at the chosen magnesium

PEG precipitation (common-techniques §5), both tubes treated identically, side
by side.

### 7. Quantify, then blind

A260 of each (1 A260 ≈ 11 nM for each arm). **Dilute both to the same
concentration**, 1–2 nM in 1× buffer with 10 mM MgCl₂. Then hand both tubes to
the second person for relabelling as X and Y.

### 8. Tip radius — before

Common-techniques §8. Record in the log.

### 9. Image X, then Y — same tip, same settings

Flip a coin for which goes first. Deposit each on its own freshly cleaved mica,
**same method, same waiting time**. Image with **identical settings** (scan
size, pixels, rate, setpoint).

| image | size | pixels | per sample |
|---|---|---|---|
| overview | 2 × 2 µm | 512 | enough for **300 particles**, 100 as the floor |
| detail | 500 × 500 nm | 512 | 5 or more |

Name the files so the sample is obvious: `X-01.spm`, `Y-01.spm`, and so on.
Save them untouched to `during/raw/`.

**Measure the tip radius between the two samples** as well as before and after.
If the tip blunts during the session, X and Y were imaged with different tips
and each needs its own value.

### 10. Tip radius — after

Record it. You now have three values: before, between, after. Write all three,
and the order you imaged the samples in, into `during/instrument.json`:

```json
"tip": {
  "measured_radius_before_nm": 11.0,
  "measured_radius_between_nm": 12.4,
  "measured_radius_after_nm": 13.1
},
"imaging_order": ["Y", "X"]
```

(the numbers are an example of the shape, not values to copy). The radius for
each sample is the mean of the two readings on either side of it; the command
in step 12 works that out from the order, so write the readings, never the
means.

---

## Day 3 — Analysis (about 1 hour), still blind

### 11. Export and check every image

Export a `.gsf` of the height channel next to each native file, and run
`uv run dobladillo afm read <file>` on each (common-techniques §10).

### 12. Run the comparison

First write E1's reference flat-sheet height into `during/instrument.json`,
and say where it came from:

```json
"reference": {
  "flat_height_nm": 1.3,
  "from": "experiments/2026-09-22-rectangle-afm/post/report.md"
}
```

(again an example of the shape). Then:

```bash
uv run dobladillo experiment compare-arms experiments/2026-09-23-twist-pair
```

It reads everything from the folder — the scans `during/raw/X-*.gsf` and
`during/raw/Y-*.gsf`, the tip readings, the imaging order, the reference
height and the designed arm size from `pre/prediction.json` — and writes
`post/arms.json`. It prints the flat fraction of each sample, the difference
X − Y with its 95% interval, and **the verdict both ways** — "if X is the
corrected arm" and "if Y is". You do not need to know which is which to run
it, and there is no way to tell it.

If any of those values is missing it stops and says which. **Do not fill a
gap with the nominal tip radius, a neighbouring reading or the model's
2.0 nm** — measure it, or record that it was not measured.

**Why the reference height.** The analysis decides "twisted" by a particle
standing taller than a flat one. Dry imaging compresses everything, so the
model's 2.0 nm is the wrong yardstick; E1's measured flat height in the same
conditions is the right one.

If it warns **fewer than 100 particles**, image more before going further. The
command exits with an error in that case, on purpose.

### 13. Write the interpretation, then unblind

Write in `post/report.md`, *before* opening the key:

- the flat fraction of X and of Y, and the difference with its interval;
- which of the three outcomes each unblinding would mean;
- anything unusual in the images.

Commit. **Then** open the key, write which verdict applies, and say whether the
gate passed. Commit again. The two commits show the analysis was done blind.

---

## When it fails

| symptom | likely cause | what to do |
|---|---|---|
| neither arm folds at M ± 2 | the longer, narrower shape needs different magnesium | full nine-point screen on the corrected arm, then repeat step 2 |
| one arm folds, the other does not | a real difference, or a bad staple pool | re-pool that arm from the plates and refold once; if it still fails, that is a result — record it |
| fewer than 100 particles per arm | sparse deposition | more deposition time or concentration — **the same change for both samples** |
| X and Y look very different on the mica itself | deposition differed | redo both depositions identically; never "fix" only one |
| can't tell flat from twisted by eye | expected; that is the analysis's job | count with `experiment compare-arms`, not by eye |
| `compare-arms` calls almost everything twisted in *both* arms | reference height too low | check E1's reference height came from the same imaging mode (dry vs liquid) |

---

## What to hand over

- `pre/` committed before the session
- `during/raw/`: gel photo, native files named X-/Y-, `.gsf` exports
- `during/instrument.json` — all three tip radii, the imaging order and E1's
  reference height — and `during/log.md`, including who held the key
- `post/arms.json` and `post/report.md`, committed once blind and once after
  unblinding
