"""
Cinema Camera Rig v4.0 -- Wolfram Alpha Build-Time Upgrades

Run AFTER the main v4.0 build is complete.
Requires WOLFRAM_APP_ID environment variable.
"""

from .calibrate_biomechanics import calibrate_biomechanics
from .fit_pupil_shift import fit_pupil_shift_curves
from .fit_squeeze_breathing import fit_squeeze_curves, generate_vex_squeeze_function
from .validate_optics import validate_all_optics

__all__ = [
    "calibrate_biomechanics",
    "fit_pupil_shift_curves",
    "fit_squeeze_curves",
    "generate_vex_squeeze_function",
    "validate_all_optics",
]
