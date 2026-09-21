# Stages 2–4, and where the inverse solver actually bites

The roadmap's seven experiments stop at Stage 1. This is what comes after, and
why the inverse Ising machinery — which is built, tested and exact — is not
used by a single experiment in that roadmap.

## The awkward fact

| stage | spins | who recovers the Hamiltonian |
|---|---:|---|
| Stage 0 (E5) | 1 | nobody: it is one probability |
| Stage 1 (E6) | 2 | a closed form — `model.two_spin_coupling`, J = ¼ln[p(++)p(--)/p(+-)p(-+)] |
| **Stage 2** | **4–6** | **the inverse solver, finally** |
| Stage 3 | 25–100 | nothing we have |
| Stage 4 | — | physics only this substrate gives |

`hamiltonian/inverse.py` exists because the programme ends at 25–100 spins.
Everything on the current roadmap is one or two. The solver is not
over-engineering — it is correctly aimed at Stage 2 and beyond — but it should
be said plainly that **E1 through E7 will not exercise it at all.**

## What it can do

Exact, on synthetic data where the answer was chosen. Recovery of every field
to four decimal places at every size tested, and the cost:

| spins | states | solve |
|---:|---:|---:|
| 12 | 4 096 | 0.2 s |
| 14 | 16 384 | 1.6 s |
| 16 | 65 536 | 12.9 s |

About **8× per two spins**, which is what exact enumeration over 2ⁿ states
costs. Stage 2's four to six spins are instant.

## What it cannot do, and the gap is not close

Extrapolating that measured factor:

| spins | projected solve |
|---:|---:|
| 22 (`MAX_EXACT_SPINS`) | 1.8 h |
| 25 (Stage 3 begins) | 2 days |
| 30 | 313 days |
| 100 (Stage 3 ends) | — |

Stage 3 is **not slow, it is unreachable**. The declared cap of 22 spins sits
three below where Stage 3 starts, and the curve past it is not something a
faster machine fixes.

`model.py` already says so — *"Use sampling, and carry its error"* — and does
not implement it. That is the honest state: the limitation is documented at
the point of failure, and the replacement is unwritten.

### What Stage 3 would need

A **sampling-based inverse solver**: pseudolikelihood, or MCMC with error bars
that are carried rather than assumed away. Both are standard; neither is
small; and both introduce an error of their own that has to be distinguished
from the modelling error the whole exercise is trying to measure. That
distinction is exactly why exact enumeration was chosen first — with no
sampling error there is nothing to confuse a modelling error with, which makes
the synthetic-data gate meaningful.

So the order is right. It is the *scale* of what remains that the roadmap
should not hide.

## A trap that was live until today

`fit.nested_models(n)` builds M1 (nearest-neighbour pairwise), M2 (+
next-nearest) and M3 (+ three-body) for the BIC comparison.

At **n = 2 they are the same model** — no next-nearest neighbour exists, no
triple exists, all three hold the same three terms. `compare` would have run,
reported that the extra terms buy nothing, and that result would have been
true by construction rather than by data.

Stage 1 is two spins. This was not a hypothetical trap; it was the shape of
the next experiment somebody would have pointed it at. It now raises, and
points at `two_spin_coupling` instead.

## Why these are not epics

`docs/STATUS.md` records the reason and it still holds: Stages 2–4 are gated on
wet-lab results **and** on a molecular-biology partner for the ligation
chemistry, who `HAMILTONIAN.md` itself says should be recruited during Stage 1.
Opening them now would schedule work behind a person who has not been asked.

What can be done before then, and is not blocked by anyone:

- the sampling-based solver, which is pure software and the long pole for
  Stage 3;
- the readout change. FRET covers Stages 0–2 only; Stage 3 needs proximity
  ligation and sequencing, and `fit.py` already carries `count_by_umi` and the
  nested-model comparison for it.
