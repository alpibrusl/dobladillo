# The closed loop

M5. `dobladillo compare <part> --run <dir> --scan <file>`.

Design against simulation against measurement — which sounds like subtraction
and is not, because the three numbers are not the same quantity and the largest
difference between two of them is not about the structure at all.

## Three lengths of one rectangle

| | what it is | conditions |
|---|---|---|
| designed | base count times rise per base pair | none; a specification |
| simulated | principal extent of a nucleotide cloud, over frames | sodium proxy, oxDNA2 has no Mg²⁺ |
| measured | footprint at half height, widened by the tip | magnesium buffer |

`compare` refuses to put two definitions side by side unless they have been
reconciled. `afm_half_height` appears in no reconciliation, so an AFM footprint
must be tip-deconvolved before it can be compared with anything — which is how
an 8.7 nm artefact is kept from hiding inside a 3 nm disagreement.

## The tip correction, derived

A rigid sphere of radius R riding the top corner of a plateau of height h has
its apex at `z(x) = h - R + sqrt(R² - x²)`, x measured outward from the true
edge. The image reaches the substrate at `x = sqrt(2Rh - h²)`. At the
**half-height** contour — which is what `imaging.particles` measures, and this
is why —

    broadening per side = sqrt(R·h - h²/4)

For a 10 nm tip on a 2 nm plate that is 4.36 nm per side, 8.7 nm on a width.
Against a 36 nm rectangle that is **24%**; against its 191 nm length, 4.6%.
Tip radius is the dominant systematic in any width this project reports.

Height is deliberately **not** corrected. Origami on mica images lower than it
is, and there is no geometric correction for that, only a calibration.
Inventing one would turn an honest disagreement into an invisible one.

## What the loop found

Running it exposed a bug in this project's own AFM fixture. `imaging.synthetic`
drew rectangles with a ramp centred on the true edge, putting the half-height
contour exactly on it — a tip with *zero* half-height broadening. Deconvolving
an artefact that was never rendered returned both dimensions short by exactly
the amount removed.

The fixture now renders the real profile above. Independent derivation
(`compare.corrections`) and independent rendering (`imaging.synthetic`) agree
on the broadening to 2% across tip radii of 5, 10 and 20 nm, which is evidence
rather than a tautology.

So the validation M5 actually rests on: **put in a rectangle of known size,
record it through a modelled tip, measure it, remove the tip, get the rectangle
back.** 191.2 nm designed against 188.8 ± 1.5 measured; 36.0 against 36.5 ± 0.7.
Assume 20 nm for a 10 nm tip instead, and it disagrees — which is why a partner
should characterise the tip before and after a session.

## Two thresholds, not one

A difference is only worth attention when it exceeds **both** what noise
explains and what a known systematic explains.

With 200 frames the standard error on a simulated length is 0.15 nm, so a
2.6 nm end effect scores 17 sigma and reads as a catastrophe. It is not: a
designed length is an idealised base count and a simulated extent is of a
thermally fluctuating object with ends. That pair carries an expected 3%
systematic, and 1.4% falls inside it. An 8% shortfall does not, and still
disagrees.

## What cannot be fixed, only carried

oxDNA2 models monovalent salt only. A simulated dimension at a sodium proxy and
a measured one in a magnesium buffer differ by an unknown amount before
anything about the structure is considered. Refusing to compare across that
would make the module useless — nothing would ever compare. Ignoring it is the
bug. So it is named in every report that involves both, and never dropped.
