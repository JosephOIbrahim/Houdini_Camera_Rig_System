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
