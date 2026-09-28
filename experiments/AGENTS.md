# Working in `experiments/`

These rules replace the repository's top-level ones while you are in here. That
file is written for an agent changing the toolchain. This one is for an agent
helping somebody run an experiment, and the failure modes are different.

Start with `experiments/README.md`. It is written for a person and it is short.

## The one that matters

**Never write a number that an instrument or a person should have produced.**

If a command stops because a field is empty, that is the design working. Say
what is missing and stop. Do not fill it in from the nominal value, from a
similar experiment, from the protocol's default, or from anything you inferred.

The sharpest case is `during/instrument.json`'s tip radius. A nominal 10 nm tip
is routinely 8–20 nm in use; the correction goes as `sqrt(R)` and removes about
8.7 nm from every width on a 2 nm plate, which is a quarter of a 36 nm
rectangle. Guess it and you turn an agreement into a disagreement or the
reverse, and **nothing downstream can tell**. `experiment report` refuses
rather than substituting, and that refusal is the feature.

The same rule holds in Python. `deconvolve_tip` and the arm measurement take
a `Measured` tip radius (`dobladillo.readings`), read from
`during/instrument.json` by `dobladillo.experiments.instrument`; a `Nominal`
or a bare float raises `NotMeasured`. Do not construct a `Measured` around a
number you did not read from the record to make that error go away — the
reading's `source` is written into every result that uses it.

The same applies to the magnesium concentration, the temperature, the particle
counts, and anything in `during/log.md`.

## Do not touch

- **`pre/plan.md`'s gate.** The experimentalist writes it, before the session.
  A gate you wrote is not a prediction, and one written after data exists is a
  description of that data. You may format it, ask about it, or point out that
  it is still empty. You may not decide it.
- **`pre/prediction.json`.** Written when the folder was made. If it looks
  wrong, say so — do not correct it. `post/` compares against what was
  predicted, and editing it retroactively is the exact failure the folder
  layout exists to prevent.
- **Anything in `during/raw/`.** Do not rename, crop, convert, tidy or
  "clean up" a raw file. Export a `.gsf` copy alongside the native one if the
  toolchain needs it; never in place of it.

## The commands

```bash
dobladillo experiment check <folder>     # what is missing, and whether the record holds
dobladillo afm read <scan.gsf>           # did pixel size and height units survive the export?
dobladillo experiment report <folder>    # measure, compare, write post/
dobladillo experiment compare-arms <folder>  # E2: two blinded arms, verdict both ways
```

`experiment report` is the one to use. Do **not** hand-assemble the equivalent
out of `afm measure` and `compare` — `compare` takes `--tip-radius` as a
required argument precisely so it cannot be defaulted, and reaching for it
directly is how a guessed radius gets in.

Every command takes `--json`.

## Report the record, not just the result

`experiment check` and `experiment report` both flag problems with the
*record*: a missing prediction, one recorded after the first raw file,
timestamps that come from the filesystem rather than git. These are not
warnings to tidy away. If one fires, it belongs in what you tell the person,
in the same breath as the numbers. A result whose prediction was written
afterwards may still be good science, but it is no longer a test, and only the
record can say which it was.

## What a disagreement means

It has four possible authors and only the last is interesting:

1. the two numbers are not the same quantity — an AFM footprint is not a
   designed length;
2. the conditions cannot be reconciled — oxDNA2 has no explicit magnesium;
3. they agree within their uncertainties;
4. the design, the model or the fold is wrong.

`compare` handles the first three and says which applied. Do not skip to (4).

## If something is genuinely unclear

Ask. An experiment costs oligos and days, and a wrong assumption stated
confidently is worse than a question. `docs/AFM_FIRST_TRIAL.md`,
`docs/CLOSED_LOOP.md` and `docs/PIPELINE.md` are the background; the top-level
`SKILL.md` lists every command.
