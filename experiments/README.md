# Experiments

**Running an experiment at the bench? Start with [`protocols/`](protocols/README.md)** —
step-by-step, written for students. For which experiment comes next and why,
see **[`ROADMAP.md`](ROADMAP.md)** for which experiment comes next and
why, and `roadmaps/` for the per-epic detail: what each one tests, what it is
scored at, and what has to be built before it can run.

One folder per experiment. Three phases, in order, and the order is the point.

```
experiments/
  2026-09-28-rectangle-afm/
    pre/       everything fixed before the first sample exists
    during/    what actually happened, and the raw files
    post/      produced by the toolchain; nothing here is edited by hand
```

## Start one

```bash
dobladillo experiment new 2026-09-28-rectangle-afm --part rectangle
```

That writes the plan, the protocol, the oligo order files, and — the
important one — `pre/prediction.json`, which records what the toolchain expects
before any data exists.

Then, in this order:

1. **Fill in the gate** in `pre/plan.md`. One line: *what result would make
   this experiment a failure?* It is the most important line in the folder and
   the easiest one to leave until last, at which point it has become a
   description of the data rather than a test of anything.
2. **Commit `pre/`.** On its own, before the session. That commit is what makes
   the ordering evidence instead of an assertion.
3. Order the oligos from `pre/order/`.
4. Measure the tip radius and write it into `during/instrument.json`.

## During

Keep `during/log.md` open and write in it as you go. A deviation nobody
recorded is indistinguishable from one that did not happen, and deviations are
usually where the interesting results come from.

Put raw files in `during/raw/` exactly as the instrument wrote them — no
cropping, renaming or converting. The toolchain reads Bruker, JPK, Asylum,
Gwyddion and WSXM `.stp` files directly, so there is nothing to export. For
any other instrument, export a `.gsf` copy from Gwyddion and put it
**alongside** the native file, not instead of it.

```bash
dobladillo afm read during/raw/scan.spm
```

Run that before believing anything: if the pixel size or height units did not
come through, every dimension downstream is wrong by the same factor and
nothing else in the chain can tell.

## After

```bash
dobladillo afm measure during/raw/scan.spm --tip-radius <measured>
dobladillo compare rectangle --scan during/raw/scan.spm --tip-radius <measured>
```

`post/` compares against `pre/prediction.json` — what was predicted at the
time — not against whatever the toolchain predicts today. An experiment from
March still reports what it actually predicted in March, even if a part's
defaults changed in April.

## Check it

```bash
dobladillo experiment check experiments/2026-09-28-rectangle-afm
```

Reports what is missing, and exits non-zero when something is wrong with the
**record** rather than with the science:

- no prediction, so there is nothing the experiment could fail against;
- a prediction recorded *after* the first raw file — still possibly good
  science, but its comparison is a description, not a prediction, and the
  report should say so;
- timestamps that come from the filesystem rather than from git, which prove
  nothing because cloning a repository resets them all.

## With an AI assistant

`experiments/AGENTS.md` is the brief for one. The short version: it may run
commands, read documents and draft the interpretation in `post/report.md`; it
may **not** write the gate in `pre/plan.md`, edit `pre/prediction.json`, touch
anything in `during/raw/`, or fill in a number an instrument should have
produced.

That last one is the one to watch. If `experiment report` stops because the
tip radius is missing, the right response is to go and measure it — not to put
the nominal value in so the command runs. The tooling refuses rather than
substituting, so an assistant that respects the refusal cannot get this wrong;
one that "helpfully" fills the field in produces a number that looks exactly
like a measurement.

## Why the fuss about ordering

`compare` will happily reconcile a measurement with whatever is predicted. If
the prediction was adjusted after seeing a scan, the output looks *identical*
to one that was predicted in advance. Nothing in the numbers distinguishes
them, so the distinction has to live in the record.

## What the AFM will not show you directly

A half-height footprint is wider than the object, by twice `sqrt(R·h − h²/4)`
for a tip of radius R on a feature of height h. For a 10 nm tip on a 2 nm
plate that is 8.7 nm — a quarter of a 36 nm width.

So `during/instrument.json` asks for the tip radius measured **before and
after**, and it is not an optional field. A tip that blunted mid-session makes
early and late scans differently wrong, and assuming 20 nm for a 10 nm tip
turns an agreement into a disagreement. See `docs/CLOSED_LOOP.md`.
