"""Calibrating an AFM against reference objects of known geometry.

An AFM number is only as good as the instrument that produced it, and the
instrument has at least five things wrong with it at once: the lateral scale
is off by a few percent, the axes are not quite perpendicular, the tip has a
finite and changing shape, noise sets how close two features can be and still
be told apart, and the sample drifts while it is being scanned. Each of those
is a number that should accompany every measurement, with an uncertainty, and
each can be read off images of an object whose geometry is known.

DNA-origami reference samples exist for exactly this, and are sold. What did
not exist was open software that turns images of them into calibration values
with uncertainties. This package is that, one quantity per module, each
tested against synthetic scans whose truth was put in by hand.
"""
