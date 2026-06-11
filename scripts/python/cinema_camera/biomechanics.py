"""
Operator biomechanics parameter derivation.
Converts physical rig properties into CHOPs solver parameters.

The key insight: rotational inertia scales with mass x distance^2.
A heavy lens pushes the center of mass forward, increasing the
moment arm and dramatically increasing rotational inertia.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .protocols import CameraState, LensState


@dataclass(frozen=True)
class BiomechanicsParams:
    """CHOPs solver parameters derived from physical rig properties."""
    # Spring solver
    spring_constant: float      # Higher = snappier response
    damping_ratio: float        # 0-1: 0=undamped, 1=critically damped

    # Lag solver
    lag_frames: float           # Operator reaction delay

    # Noise (handheld)
    handheld_amplitude_deg: float  # Peak random rotation
    handheld_frequency_hz: float   # Dominant shake frequency

    # Derived
    moment_of_inertia: float    # kg*cm^2 (for reference)
    combined_weight_kg: float


def auto_derive_from_weight(
    weight_kg: float,
    fluid_head_damping_base: float = 0.6,
) -> dict:
    """
    Weight-only auto-derive used by every HDA surface (chops HDA callback,
    LOP cook-time solver, derive_biomechanics). SINGLE SOURCE OF TRUTH for
    these formulas — do not duplicate them in builder/callback strings.
    """
    w = max(0.1, weight_kg)
    return {
        "spring_constant":     max(5.0, 25.0 - w * 1.3),
        "damping_ratio":       min(0.95, fluid_head_damping_base + w * 0.025),
        "lag_frames":          w * 0.3,
        "shake_amplitude_deg": max(0.05, 1.5 / w),
        "shake_frequency_hz":  max(2.0, 8.0 - w * 0.3),
    }


def solve_damped_spring(
    samples: list,
    dt: float,
    spring_k: float,
    damping_ratio: float,
    lag_frames: float,
) -> list:
    """
    Damped-spring filter over per-frame [rx, ry, rz] samples.

    ODE: x'' = -k*(x - target_lagged) - c*x'  with c = 2*sqrt(k)*zeta,
    discretized via symplectic Euler. Mirrors the chops HDA's Spring CHOP
    configuration (mass=1, dampingk = 2*sqrt(k)*zeta).
    """
    if not samples:
        return []
    c = 2.0 * math.sqrt(spring_k) * damping_ratio
    lag_int = max(0, int(round(lag_frames)))
    x = list(samples[0])
    v = [0.0, 0.0, 0.0]
    filtered = []
    for i in range(len(samples)):
        target = samples[max(0, i - lag_int)]
        for axis in range(3):
            accel = -spring_k * (x[axis] - target[axis]) - c * v[axis]
            v[axis] += accel * dt
            x[axis] += v[axis] * dt
        filtered.append(list(x))
    return filtered


def handheld_shake_offsets(
    frames: list,
    dt: float,
    amplitude_deg: float,
    frequency_hz: float,
) -> list:
    """
    Deterministic procedural handheld shake: per-frame [sx, sy, sz] degree
    offsets from a phase-offset sin sum. Same signal every cook (farm-safe).
    """
    two_pi = 2.0 * math.pi
    amp, freq = amplitude_deg, frequency_hz
    out = []
    for f in frames:
        t = f * dt
        sx = (math.sin(two_pi * freq * t)            * 0.7 +
              math.sin(two_pi * freq * 1.7 * t + 0.7) * 0.3) * amp
        sy = (math.sin(two_pi * freq * 1.13 * t + 1.7) * 0.7 +
              math.sin(two_pi * freq * 0.83 * t + 2.3) * 0.3) * amp * 0.7
        sz = (math.sin(two_pi * freq * 0.87 * t + 3.1) * 0.5 +
              math.sin(two_pi * freq * 1.4 * t + 0.4)  * 0.3) * amp * 0.4
        out.append([sx, sy, sz])
    return out


def derive_biomechanics(
    camera_state: CameraState,
    lens_state: LensState,
    body_weight_kg: float = 3.9,             # ARRI Alexa 35 body
    sensor_to_mounting_face_cm: float = 8.0,  # Distance sensor to mount
    fluid_head_damping_base: float = 0.6,     # OConnor 2575 baseline
) -> BiomechanicsParams:
    """
    Derive CHOPs parameters from physical rig properties.

    A 50mm Cooke at 3.6kg on an Alexa 35 (3.9kg) = 7.5kg rig.
    A 300mm at 9.4kg = 13.3kg rig. The 13.3kg rig has massive
    rotational inertia -- pans ease in slowly and coast to a stop.
    The 7.5kg rig is snappy and jittery.
    """
    lens_weight = lens_state.rig_weight_kg
    combined_weight = body_weight_kg + lens_weight

    # Moment arm: distance from tripod pivot to center of mass
    # Approximate: sensor offset + half lens length
    lens_half_length_cm = 0.0
    if lens_state.spec.has_mechanics:
        lens_half_length_cm = lens_state.spec.mechanics.length_mm / 20.0  # mm->cm/2

    moment_arm_cm = sensor_to_mounting_face_cm + lens_half_length_cm
    moment_of_inertia = combined_weight * (moment_arm_cm ** 2)

    # Weight-driven response curve (calibrated so 7.5kg rig ~ 15.0 spring,
    # 13.3kg rig ~ 8.0). Moment of inertia stored for reference. Formulas
    # live in auto_derive_from_weight() — shared with the HDA surfaces.
    derived = auto_derive_from_weight(combined_weight, fluid_head_damping_base)

    return BiomechanicsParams(
        spring_constant=derived["spring_constant"],
        damping_ratio=derived["damping_ratio"],
        lag_frames=derived["lag_frames"],
        handheld_amplitude_deg=derived["shake_amplitude_deg"],
        handheld_frequency_hz=derived["shake_frequency_hz"],
        moment_of_inertia=moment_of_inertia,
        combined_weight_kg=combined_weight,
    )


def derive_biomechanics_calibrated(
    camera_state: CameraState,
    lens_state: LensState,
    body_weight_kg: float = 3.9,
    sensor_to_mounting_face_cm: float = 8.0,
) -> BiomechanicsParams:
    """
    Wolfram-calibrated version of derive_biomechanics().

    Uses exact ODE-derived curves instead of hand-tuned linear
    approximations. Falls back to derive_biomechanics() if
    calibration file is missing.
    """
    import json
    import os

    cinema_path = os.environ.get("CINEMA_CAMERA_PATH", "")
    cal_path = os.path.join(cinema_path, "biomechanics_calibration.json")

    if not os.path.exists(cal_path):
        return derive_biomechanics(
            camera_state, lens_state, body_weight_kg,
            sensor_to_mounting_face_cm,
        )

    with open(cal_path, "r", encoding="utf-8") as f:
        cal = json.load(f)

    lens_weight = lens_state.rig_weight_kg
    combined_weight = body_weight_kg + lens_weight

    lens_half_length_cm = 0.0
    if lens_state.spec.has_mechanics:
        lens_half_length_cm = lens_state.spec.mechanics.length_mm / 20.0

    moment_arm_cm = sensor_to_mounting_face_cm + lens_half_length_cm
    inertia = combined_weight * (moment_arm_cm ** 2)

    spring_fn = eval(cal["spring_k_fit"]["python_lambda"])  # noqa: S307
    damp_fn = eval(cal["damping_ratio_fit"]["python_lambda"])  # noqa: S307

    spring_k = max(1.0, spring_fn(inertia))
    damping_ratio = max(0.1, min(0.99, damp_fn(inertia)))

    lag_frames = combined_weight * 0.3
    handheld_amp = max(0.05, 1.5 / combined_weight)
    handheld_freq = max(2.0, 8.0 - combined_weight * 0.3)

    return BiomechanicsParams(
        spring_constant=spring_k,
        damping_ratio=damping_ratio,
        lag_frames=lag_frames,
        handheld_amplitude_deg=handheld_amp,
        handheld_frequency_hz=handheld_freq,
        moment_of_inertia=inertia,
        combined_weight_kg=combined_weight,
    )
