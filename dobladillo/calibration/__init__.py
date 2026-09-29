"""Calibrating an AFM against reference objects of known geometry.

From images of objects whose geometry is declared -- a DNA-origami tile
designed here, or any other sample whose datasheet gives positions -- report
what the instrument gets wrong: lateral scale in x and y, skew, tip,
resolution and drift, each with an uncertainty and a statement of what that
uncertainty does and does not include. No open software did this when the
module was started (2026-09-29): DNA-origami AFM standards exist, the
software to turn their images into calibration values with uncertainty did
not.
"""
