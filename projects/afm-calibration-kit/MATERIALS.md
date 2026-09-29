# Materials for the calibration kit (K1–K8)

Everything to buy or prepare for the K series. Where an item is already
specified in an existing protocol, this file points to it rather than
restating it. Two descriptions of the same buffer drift apart, and a fold that
fails because two documents disagreed fails for a reason nobody can name.

- **Generic recipes:** [`common-techniques.md`](../../experiments/protocols/common-techniques.md)
  (§1 stocks, §2 volumes, §4 gel, §5 purification, §7 deposition).
- **The tile's pooling:** [E8](../../experiments/protocols/E8-patterned-rectangle.md), step 1.
- **The six-helix bundle's buffers:** [E10](../../experiments/protocols/E10-six-helix-bundle.md),
  step 2. The bundle follows **one published protocol, whole**. Do not fold it
  in common-techniques' buffer.

Marked **[literature]**: taken from published work, not from this project's
bench. **[typical]**: a common range, to be confirmed against the
instrument's or supplier's own documentation. No catalogue numbers are given
here: none has been checked, and a wrong one is worse than none.

Everything bought is a purchase. The supervisor approves it first.

---

## 1. Nucleic acids

### Scaffold

M13mp18 single-stranded DNA, **p7249** (7,249 nt), the same stock as E1, E8
and E10 (common-techniques §1). Commercial stocks are commonly 100 nM.

How much the K series uses, from the reaction counts in its protocols (50 µL
reactions; 5 µL of 100 nM per reaction at 10 nM, or 10 µL at the bundle's
20 nM):

| experiment | reactions | scaffold, 100 nM |
|---|---|---:|
| K2 — tile ×3, E1 control, scaffold-only, isothermal ×2 (optional) | 7 | 35 µL |
| K3/K4 — the bundle, E10's protocol, 3 reactions (only if E10 passed and none is left) | 3 | 30 µL |
| K5 — two independent fold batches of 3 | 6 | 30 µL |
| K6 — one batch of 3 | 3 | 15 µL |
| K7 — one large batch of 10 (see §7) | 10 | 50 µL |
| **total, with no spare** | | **160 µL** |

Order with a margin. A failed fold is repeated, not skipped.

### Staples: what to order, and how to generate the order

Three parts are involved. Two of them already exist as orders:

| part | what | order with | oligos | estimate |
|---|---|---|---:|---:|
| `rectangle` | E1's plates. **Reuse E1's if your lab has them.** Every tile staple that is not marked is one of these. | `uv run dobladillo lab order rectangle --out <dir>` | 220 on 3 plates | €693 |
| `calibration-tile` | only the **marked** staples: E1's staple plus the hairpin | `uv run dobladillo lab order calibration-tile --out <dir>` (48 marker staples, 2,561 bases; the other 172 are E1's) | about 4 per marked cell | about €21.5 per marked cell |
| `bundle` | E10's plates. **Reuse E10's if your lab has them.** | `uv run dobladillo lab order bundle --out <dir>` | 168 on 2 plates | €706 |

The estimates are what `lab order` prints. Its assumptions are 0.10 per base,
plate format, 25 nmol scale, standard desalting, list price before any
discount, and synthesis only (no shipping, tax or handling). The tile's
per-cell figure is derived from E8's order: 28 oligos, 1,502 nt, €150.20 for
7 cells. The real figure is whatever `lab order calibration-tile` prints once
the part exists.

**In practice, order from the experiment folder, not by hand.** `experiment
new <slug> --part calibration-tile` is
expected to write the order into `pre/order/` as `--part pattern` does for E8.
Then the order is recorded next to the prediction it belongs to.

What E8's `pattern` order contains, and what the tile's should contain once it
exists. Check this against the files when they are written:

- `<part>_plates.xlsx` and `<part>_bulk.csv`: the marked staples only, on a
  plate named `marker1`, each named `st_hHH_oOOOO_hp` so the marked staple
  and E1's plain one are never confused in the freezer;
- `<part>_reuse.json`: under `omit_from_base`, **the wells of E1's plates to
  leave out** of the pool, one for each marked staple.

Order like E1's: standard desalting, 25 nmol, normalised to **100 µM** in
water (common-techniques §1).

**Cells shared with E8's F.** A marked cell of the tile that is also a cell of
E8's F carries the same oligos. Whether E8's marker plate can stand in for
part of the tile's order depends on the pattern the part chooses. Read it off
the two `_reuse.json` files. Do not work it out by hand.

### Pooling the tile: E8's method

The tile is pooled like E8, **never from E1's finished pool**. E1's pool
contains the plain version of every marked staple, and the plain and marked
versions compete for the same place on the scaffold.

- 5 µL from every well of E1's plates **except** the wells in
  `pre/order/calibration-tile_reuse.json` → `omit_from_base`;
- 5 µL from every well of the marker plate.

That is 220 staples again, so each is at **100 µM / 220 = 455 nM**, the same as
E1's and E8's pools, and every volume in E1's reaction table applies unchanged.
Use the tip-box trick (E8, step 1) to skip the omitted wells. If an omitted
well is pipetted by mistake, start the pool again.

One pool (220 × 5 µL = 1.1 mL) is enough for about 200 reactions at 5.5 µL
each, which covers the whole K series. Each pool takes 5 µL from every well
of E1's plates. Check what is left in the wells against the delivery sheet
before you plan a second pool.

### The six-helix bundle

E10's pool: 168 staples, 5 µL each, **595 nM** each (E10, step 1). E10's
buffers and anneal only.

### Optional: a streptavidin-marked comparator for K6

K6 compares the tile's all-DNA hairpins with streptavidin markers (Kielar et
al. 2020 report that the tip strips streptavidin). That needs biotinylated
staples at the tile's marked cells: part `calibration-tile-biotin`, the same 48
staple ends as the hairpin tile with a TT spacer and a 3' biotin (IDT `/3Bio/`),
ordered with `uv run dobladillo lab order calibration-tile-biotin --out <dir>`
(pool E1's plates except the same 48 wells, as for the hairpin tile). The cost
estimate excludes the vendor's per-modification surcharge and says so. IDT also
sells a TEG-spaced biotin that may bind streptavidin more readily; choosing it is
a one-line change in `parts/pattern.py` and the experimentalist's call. K6's
arm A runs without any of this.

---

## 2. Buffers and chemicals

| stock | recipe | from | used in |
|---|---|---|---|
| 10× folding buffer, no Mg | 50 mM Tris, 10 mM EDTA, pH 8.0 | common-techniques §1 | K2, K5–K7 folds |
| MgCl₂, 1 M and 100 mM | 100 mM from 1 M | common-techniques §1 | everything |
| **NiCl₂, 100 mM** | from solid NiCl₂ (anhydrous or hexahydrate: record which and correct the mass) in ultrapure water, filtered | new here | K5 (Ni²⁺ deposition), K6 if the HS-AFM lab uses it |
| deposition buffer, Mg | 1× folding buffer + 10 mM MgCl₂ | common-techniques §7 | all depositions unless K5 varies it |
| deposition buffer, Ni | deposition buffer, Mg + NiCl₂ at **one** value from the 1–5 mM range in common-techniques §7, fixed in K5's `pre/plan.md` | common-techniques §7 | K5 |
| imaging buffer, liquid | 1× folding buffer + 10–12.5 mM MgCl₂ (fix one value per experiment) | common-techniques §7 | K3–K7 liquid imaging |
| imaging buffer, HS-AFM | as above, **unless** the HS-AFM operator has a validated buffer; theirs wins, and is recorded | common-techniques §7 | K6 |
| PEG buffer | 15% (w/v) PEG-8000, 5 mM Tris, 1 mM EDTA, 505 mM NaCl | common-techniques §5 | tile purification |
| bundle buffers | 10× TAE, 1× FOB (1× TAE + 12.5 mM MgCl₂), the source's PEG buffer | E10 step 2 | bundle only |
| gel | 2% agarose, 0.5× TBE + 11 mM MgCl₂, SYBR Safe, EDTA-free loading dye, 1 kb ladder | common-techniques §4 | K2, K5, K7 |
| ultrapure water, nuclease-free water | — | — | everything |
| compressed nitrogen | low flow | common-techniques §0, §7 | dry depositions |
| streptavidin | only if K6's arm B is decided; concentration from the protocol chosen then | — | K6 arm B |

**Nickel.** Nickel salts are toxic and skin sensitisers, and are classified
as carcinogens. Wear gloves, avoid dust when weighing, and collect nickel
waste separately by your institution's rules. Add it to your lab's copy of
common-techniques §0.

**EDTA and nickel.** EDTA binds Ni²⁺ as it binds Mg²⁺ (common-techniques §1).
The deposition buffer carries 1 mM EDTA from the 1× folding buffer, so record
the **nominal** NiCl₂ and MgCl₂, not a corrected value.

---

## 3. Purification

As common-techniques §5: **PEG precipitation** preferred; **100 kDa
centrifugal filters** (Amicon Ultra-0.5, the fallback named there) or **gel
extraction** as alternatives. K2 records the recovery (A260 before and after),
because the kit's yield per fold depends on it. The bundle is purified with
E10's recipe.

---

## 4. Mica and substrates

| item | spec | note |
|---|---|---|
| muscovite mica discs | grade V1, freshly cleaved (E10's source uses 15 × 15 mm) | one per deposition; the size must fit your sample holder |
| mica for HS-AFM | small discs glued to the scanner's sample stage, as the instrument requires | instrument-specific; the operator's procedure |
| AFM sample pucks or discs, adhesive | as your instrument uses | — |
| adhesive tape for cleaving | — | common-techniques §7 |
| liquid-cell consumables | as your instrument uses | K3–K7 liquid arms |

Rough count, from the protocols: about 10 discs for K2–K4, about 25 for K5,
about 60 for K7 (dry format: one disc per time point per replicate), plus spares.

---

## 5. Tips

Specs are **generic and [typical]**. Confirm every number against your
instrument's documentation and the tip supplier's data sheet. The nominal
radius on the box never enters an analysis. Every experiment measures the tip
before and after (common-techniques §8), and K4 reconstructs it.

| use | cantilever | tip | typical spec **[typical]** | used in |
|---|---|---|---|---|
| **air**, intermittent contact | silicon, stiff | sharpened silicon, nominal apex radius ≲ 10 nm | spring constant tens of N/m, resonance a few hundred kHz | K3 air arm, K5 dry arm, K7 dry format |
| **air or liquid**, force-controlled off-resonance modes | silicon nitride, soft | sharpened tip, nominal apex radius ≲ 10 nm | spring constant of order 0.1–0.5 N/m | K3–K5, if your instrument images DNA this way |
| **liquid**, intermittent contact | short, soft, made for fluid | sharpened, nominal apex radius ≲ 10 nm | resonance in fluid of order tens of kHz | K3 liquid arm, K4, K5, K7 |
| **HS-AFM** | small cantilevers made for the instrument | electron-beam-deposited tip, sharpened **[literature]** | length of order 10 µm, resonance in liquid of order 1 MHz, spring constant of order 0.1 N/m **[literature, typical]** | K6; the HS-AFM operator chooses |

Buy the tips for K4 and K5 **from one lot**, and record part number and lot in
`during/instrument.json` (`tip.part_number`) and `during/log.md`. Tip-to-tip
variation is something K5 should not be measuring. Budget at least one fresh
tip per session, and spares.

A **tip characteriser** (common-techniques §8) is still needed for the before
and after radius in every experiment. The GATTA-AFM 3D staircase (§6) can
serve as one in K4.

---

## 6. Reference samples: purchases

| item | what | price as listed 2026-09-29 | used in | note |
|---|---|---:|---|---|
| **GATTA-AFM** (GATTAquant) | DNA-origami rectangle, about 90 × 70 nm, with a 6 nm line ladder | EUR 350 | K4 (a second origami reference), K5 (comparator), K1 (declared-geometry test, if images are made) | no certified values |
| **GATTA-AFM 3D** (GATTAquant) | a 4-step staircase, about 2.5 / 5 / 12.5 / 20 nm, for blind tip reconstruction (Kolbeck et al., Nano Lett. 2023) | EUR 450 | K4 | no certified values |
| **traceable lateral calibration grating** | a pitch grating with a certificate stating pitch, uncertainty and traceability | not stated here | K3, K5 (instrument-stability check), K7 | use your lab's if it has one; see K3 for the pitch it needs |

For both GATTAquant products, read the product sheet before the session:
whether the sample arrives in solution or already on a substrate, its
deposition and imaging conditions, its storage, and how many depositions one
unit gives. Follow **their** protocol for their sample, as E1 does for its
positive control. Do not mix parameters.

Their geometry, as `calibrate` needs it declared, comes from the supplier's
documentation or Kolbeck et al. Nothing in this repository states it beyond
the approximate figures above, and those are not to be typed in as a declared
geometry.

---

## 7. Storage and aliquoting (K7 formats)

| item | spec |
|---|---|
| low-binding microcentrifuge tubes or PCR strips | for aliquots |
| −20 °C freezer, non-frost-free if available | frozen format; frost-free freezers cycle temperature |
| −80 °C freezer | optional comparison arm in K7 |
| 4 °C fridge | liquid format |
| desiccator with fresh desiccant, and clean closed mica boxes | dried-on-mica format (Korpelainen et al. report dry samples stable for at least 12 months) |
| freezer-proof labels | batch, date, concentration, buffer, Mg, **freeze-thaw count** |

**Aliquot size (a proposal for K7's plan).** A deposition uses 10 µL at
1–2 nM, which is 10–20 fmol. A **5 µL aliquot at 10 nM** (50 fmol) gives two
to five depositions after dilution. It is single-use: whatever is not
deposited is discarded, not refrozen.

**How much tile K7 needs.** Three liquid formats × six time points × two
replicates is 36 aliquots. The freeze-thaw series takes 8 more, and the 12
dried discs are made at t0 from a few more. That is about 48 aliquots, about
2.4 pmol (K7, *The formats*). A 50 µL fold at 10 nM holds 500 fmol before
purification, so K7 folds one batch of **10 reactions** (5 pmol in). That is
enough if purification recovers about half. K2 measures the actual recovery;
scale the batch by it.

---

## 8. Equipment

As E1 and E11: thermocycler (a gradient block for K2's isothermal arm, as
E11), gel tank on ice or in a cold room, blue-light transilluminator,
centrifuge (16,000 × g), NanoDrop, AFM with liquid cell, and Gwyddion (the
independent check for tip reconstruction, common-techniques §8). HS-AFM for K6
only. Fiji for gel quantification (E11 §8).

---

## 9. Cost: only what can be derived

| item | cost | source |
|---|---:|---|
| E1's rectangle plates, if not already in the lab | €693 | `lab order rectangle` |
| the tile's marker plate | about €21.5 × (marked cells) | E8's order, until `lab order calibration-tile` exists |
| E10's bundle plates, if not already in the lab | €706 | `lab order bundle` |
| GATTA-AFM | EUR 350 | GATTAquant list, 2026-09-29 |
| GATTA-AFM 3D | EUR 450 | GATTAquant list, 2026-09-29 |

The oligo figures are list-price estimates with the assumptions `lab order`
prints (§1). Not derivable here, and not estimated: scaffold, tips,
the grating, mica, chemicals, HS-AFM time, and anything a partner charges.
