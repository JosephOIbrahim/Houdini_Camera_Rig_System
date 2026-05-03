"""
Cinema Camera Rig v4.0 — Python Package

Virtual cinematography simulator for Houdini 21 / USD / Solaris / Karma XPU.
Physically-based camera rig with typed protocols, optical calculations,
biomechanics simulation, and Copernicus 2.0 post-processing.
"""

__version__ = "4.0.0"

from .protocols import (
    BreathingCurve,
    CameraState,
    DistortionModel,
    FormatSpec,
    GearRingSpec,
    LensSpec,
    LensState,
    MechanicalSpec,
    OpticalResult,
    SensorSpec,
    SqueezeBreathingCurve,
)

__all__ = [
    "BreathingCurve",
    "CameraState",
    "DistortionModel",
    "FormatSpec",
    "GearRingSpec",
    "LensSpec",
    "LensState",
    "MechanicalSpec",
    "OpticalResult",
    "SensorSpec",
    "SqueezeBreathingCurve",
]

# Side-effect imports: trigger lens / body provider registration on package import
# so cinema_camera.registry.list_lenses() returns the bundled providers.
from . import lenses  # noqa: F401  -- registers "cooke_ana_i_s35"
from . import bodies  # noqa: F401  -- registers built-in camera bodies
