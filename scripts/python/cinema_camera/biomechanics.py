"""
Operator biomechanics parameter derivation.
Converts physical rig properties into CHOPs solver parameters.

The key insight: rotational inertia scales with mass x distance^2.
A heavy lens pushes the center of mass forward, increasing the
moment arm and dramatically increasing rotational inertia.
"""

from __future__ import annotations

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

    # Spring constant: inversely proportional to combined weight
    # Calibrated so 7.5kg rig ~ 15.0, 13.3kg rig ~ 8.0
    # Moment of inertia stored for reference but weight drives the response
    # curve to maintain differentiation across the full lens range.
    spring_k = max(5.0, 25.0 - combined_weight * 1.3)

    # Damping: heavier rigs are more critically damped
    damping = min(0.95, fluid_head_damping_base + combined_weight * 0.025)

    # Lag: heavier rigs have slower operator response
    lag_frames = combined_weight * 0.3

    # Handheld shake: inversely proportional to weight
    handheld_amp = max(0.05, 1.5 / combined_weight)
    handheld_freq = max(2.0, 8.0 - combined_weight * 0.3)

    return BiomechanicsParams(
        spring_constant=spring_k,
        damping_ratio=damping,
        lag_frames=lag_frames,
        handheld_amplitude_deg=handheld_amp,
        handheld_frequency_hz=handheld_freq,
        moment_of_inertia=moment_of_inertia,
        combined_weight_kg=combined_weight,
    )
