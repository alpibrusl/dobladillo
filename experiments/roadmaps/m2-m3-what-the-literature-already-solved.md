# M2 and M3: read this before writing either

Both were named on the roadmap as if they were software to invent. They are
not. Each is a studied problem with a name, a complexity result and existing
algorithms, and the useful thing this note does is say which — so whoever picks
them up starts from the literature rather than from a blank file.

Neither blocks E1–E7. This is preparation, not a task.

---

## First, the analogy that does and does not hold

Ports and shared cores make this look like LEGO, and for *design* it is:
discrete units, standard interfaces, a core with swappable modules.

**The verb is where it breaks.** In LEGO somebody places bricks in sequence. In
origami everything goes in one tube and anneals — there is no placement
operator. The assembly plan is not an order of operations; it is a set of
components whose only low-energy configuration is the target. That is a
different problem, not a variant of the same one.

The exception is real and published: **hierarchical assembly**, folding
sub-units separately and combining them in stages, which *is* sequential and
*is* LEGO-like. Wagenbauer, Sigl and Dietz build gigadalton objects that way,
and it is already in `DESIGN.md`'s reference list.

---

## M3 — assembly composition and stage planning

### What it actually is

Demaine, Demaine, Fekete, Ishaque, Rafalin, Schweller and Souvaine, *Staged
Self-Assembly: Nanomanufacture of Arbitrary Shapes with O(1) Glues* (Natural
Computing, 2008). <https://www.cs.tufts.edu/r/geometry/pdf/NACO-2007.pdf>

Its central move is the one this roadmap item needs and did not know it wanted:
**encode the shape in the staging algorithm rather than in the tiles.** With a
constant number of glues, one-pot assembly cannot make an n×n square at all.
Staged assembly can make arbitrary shapes.

The model allows three operations, and they map onto bench steps directly:

| model | bench |
|---|---|
| **mix** two populations | combine two annealed pots |
| **split** / filter a population | purify — gel, PEG, spin column |
| **store** a population between stages | keep an intermediate in the fridge |

### The numbers worth knowing before designing anything

| target | one pot | staged |
|---|---|---|
| 1×n line | Θ(n) glues | **constant**, independent of n |
| n×n square | Θ(n) glues | **O(log n)**, by their Jigsaw technique |
| arbitrary shape | — | O(log n) glues at scale factor 2; constant glues at logarithmic scale factor |

For this project, "glue" reads as *orthogonal interface* — the thing M2 has to
supply and the thing that costs money and design effort. An exponential saving
in interfaces is the entire argument for staging, and it is why M3 is worth
doing before any assembly larger than one scaffold.

### The assumptions, which are the experimentalist's problem

The paper assumes perfect mixing and separation between stages, no errors
carried forward from intermediates, reliable storage, and precise control of
timing. None of those is free at a bench. **Every stage is a purification step
with a yield**, so a plan with many stages trades interface count against
recovery, and that trade is not in the model.

That is the gap between the theory and a protocol, and it is where this
project's own contribution would sit: the model counts glues, the bench counts
yields, and nobody has reconciled them for origami.

---

## M2 — interface library and orthogonality

### What it actually is

The **DNA word design problem**: find a set of fixed-length words over
{A,C,G,T} that are pairwise distinguishable. It has decades of literature,
standard constraints and known constructions.

The usual constraint set:

- **minimum Hamming distance** — every pair differs in at least *d* positions;
- **fixed GC content** — so the set is thermodynamically comparable, which
  matters here because `sequence.thermo` shows GC moves ΔG by several kT;
- **reverse-complement distance** — a word must not be close to another
  word's complement, which is the constraint that actually encodes "A binds A′
  and not B′";
- **no long homopolymer runs** — already enforced in `hamiltonian.bracket`.

It is typically formulated as a **maximum independent set** problem, and there
are both linear/algebraic constructions and constraint-solver approaches.

### The catch, and why not to stop at Hamming distance

Hamming distance is a *combinatorial* proxy. Two words can be far apart in
Hamming terms and still cross-hybridise, because binding is thermodynamic and
graded. There is published work replacing or supplementing the distance
constraint with a **free-energy gap** between intended and unintended pairings,
which is the right criterion for us — it is the same quantity
`sequence.thermo` already computes.

So M2 should design against a ΔG gap and use Hamming distance only as a cheap
pre-filter.

### What M1 already settled, and what it did not

`interfaces.crosstalk` answers the **structural** half without a single base:
two ports that share a signature and oppose in polarity are the same interface,
and no sequence design rescues that. A film of twelve hinges on one latch was
caught that way.

What M2 adds is the **sequence** half: given twelve channels that are
structurally distinct, assign twelve sequences whose unintended pairings are
weaker than the intended ones by a stated margin.

---

## What none of it solves

Every algorithm above goes from a **shape** to components — DAEDALUS, vHelix,
PERDIX and TALOS from a polyhedral mesh via A-trail routing; PATS from a target
pattern to a tile set, which is NP-hard even in its binary form.

This project does not want a shape. It wants an **energy landscape**: a hinge
up 30% of the time, two coupled with J constant under varying bias. No
published algorithm goes from function to components.

That gap is where the Hamiltonian programme sits, and it is worth stating
plainly in any proposal: the routing problem is solved, the pattern problem is
NP-hard and heuristically attacked, and the *inverse design of a landscape* is
neither.

## References, to fetch and verify rather than trust from here

- Demaine et al., *Staged Self-Assembly*, Natural Computing 2008.
  <https://www.cs.tufts.edu/r/geometry/pdf/NACO-2007.pdf>
- Veneziano et al., *Designer nanoscale DNA assemblies programmed from the top
  down*, Science 2016 (DAEDALUS).
  <https://www.science.org/doi/10.1126/science.aaf4388>
- Jun et al., automated 2D wireframe with honeycomb edges (PERDIX/TALOS
  family), Nature Communications 2019.
  <https://www.nature.com/articles/s41467-019-13457-y>
- 2-PATS is NP-hard.
  <https://link.springer.com/chapter/10.1007/978-3-662-47672-7_83>
- A free-energy-gap constraint for DNA sequence design, PLOS One 2013.
  <https://journals.plos.org/plosone/article?id=10.1371%2Fjournal.pone.0072180>
- The DNA word design problem as a constraint model, IJCAI 2017.
  <https://mlanthology.org/ijcai/2017/codish2017ijcai-dna/>
