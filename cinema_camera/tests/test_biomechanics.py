"""
Cinema Camera Rig v4.0 — Biomechanics Tests

Validates derive_biomechanics() produces correct solver parameters
for different rig weights.
"""

import sys
import os
import pytest

# Ensure cinema_camera package is importable
_scripts_python = os.path.join(
    os.path.dirname(__file__), "..", "..", "scripts", "python"
)
_scripts_python = os.path.normpath(_scripts_python)
if _scripts_python not in sys.path:
    sys.path.insert(0, _scripts_python)

from cinema_camera.protocols import (
    BreathingCurve,
    CameraState,
    DistortionModel,
    FormatSpec,
    GearRingSpec,
    LensSpec,
    LensState,
    MechanicalSpec,
    SensorSpec,
    SqueezeBreathingCurve,
)
from cinema_camera.biomechanics import BiomechanicsParams, derive_biomechanics


@pytest.fixture
def camera_state():
    return CameraState(
        model="ARRI ALEXA 35",
        sensor=SensorSpec(width_mm=27.99, height_mm=19.22, native_iso=800),
        format=FormatSpec(4608, 3164),
    )


def _make_lens_state(focal_mm, weight_kg, length_mm, close_focus_m=0.85):
    """Helper: create a LensState with mechanical data."""
    spec = LensSpec(
        lens_id=f"test_{focal_mm}mm",
        manufacturer="Cooke",
        series="Anamorphic/i S35",
        focal_length_mm=focal_mm,
        t_stop_min=2.3,
        t_stop_max=22.0,
        iris_blades=11,
        close_focus_m=close_focus_m,
        image_circle_mm=31.1,
        squeeze_ratio=2.0,
        distortion=DistortionModel(),
        breathing=BreathingCurve(),
        mechanics=MechanicalSpec(
            weight_kg=weight_kg,
            length_mm=length_mm,
            front_diameter_mm=110.0,
            filter_thread="M105x0.75",
            focus_ring=GearRingSpec(rotation_deg=300, gear_teeth=140),
            iris_ring=GearRingSpec(rotation_deg=90, gear_teeth=134),
            entrance_pupil_offset_mm=focal_mm * 2.5,
        ),
    )
    return LensState(spec=spec, t_stop=2.8, focus_distance_m=2.0)


class TestBiomechanics50mm:
    """50mm Cooke at 3.6kg on Alexa 35 (3.9kg) = 7.5kg rig."""

    def test_combined_weight(self, camera_state):
        lens_state = _make_lens_state(50.0, 3.6, 205.0)
        params = derive_biomechanics(camera_state, lens_state)
        assert params.combined_weight_kg == pytest.approx(7.5)

    def test_spring_constant(self, camera_state):
        lens_state = _make_lens_state(50.0, 3.6, 205.0)
        params = derive_biomechanics(camera_state, lens_state)
        # Light rig: spring_k should be relatively high (~15)
        assert 10.0 < params.spring_constant < 20.0

    def test_damping_ratio(self, camera_state):
        lens_state = _make_lens_state(50.0, 3.6, 205.0)
        params = derive_biomechanics(camera_state, lens_state)
        # Light rig: moderate damping
        assert 0.4 < params.damping_ratio < 0.8

    def test_handheld_amplitude(self, camera_state):
        lens_state = _make_lens_state(50.0, 3.6, 205.0)
        params = derive_biomechanics(camera_state, lens_state)
        # Lighter rig = more shake
        assert params.handheld_amplitude_deg > 0.1


class TestBiomechanics300mm:
    """300mm Cooke at 9.4kg on Alexa 35 (3.9kg) = 13.3kg rig."""

    def test_combined_weight(self, camera_state):
        lens_state = _make_lens_state(300.0, 9.4, 460.0, close_focus_m=1.83)
        params = derive_biomechanics(camera_state, lens_state)
        assert params.combined_weight_kg == pytest.approx(13.3)

    def test_spring_constant_lower_than_50mm(self, camera_state):
        light = derive_biomechanics(
            camera_state, _make_lens_state(50.0, 3.6, 205.0)
        )
        heavy = derive_biomechanics(
            camera_state, _make_lens_state(300.0, 9.4, 460.0, close_focus_m=1.83)
        )
        # Heavy rig has lower spring constant (slower response)
        assert heavy.spring_constant < light.spring_constant

    def test_damping_higher_than_50mm(self, camera_state):
        light = derive_biomechanics(
            camera_state, _make_lens_state(50.0, 3.6, 205.0)
        )
        heavy = derive_biomechanics(
            camera_state, _make_lens_state(300.0, 9.4, 460.0, close_focus_m=1.83)
        )
        # Heavy rig has more damping
        assert heavy.damping_ratio > light.damping_ratio

    def test_handheld_less_than_50mm(self, camera_state):
        light = derive_biomechanics(
            camera_state, _make_lens_state(50.0, 3.6, 205.0)
        )
        heavy = derive_biomechanics(
            camera_state, _make_lens_state(300.0, 9.4, 460.0, close_focus_m=1.83)
        )
        # Heavy rig = less shake
        assert heavy.handheld_amplitude_deg < light.handheld_amplitude_deg

    def test_lag_higher_than_50mm(self, camera_state):
        light = derive_biomechanics(
            camera_state, _make_lens_state(50.0, 3.6, 205.0)
        )
        heavy = derive_biomechanics(
            camera_state, _make_lens_state(300.0, 9.4, 460.0, close_focus_m=1.83)
        )
        # Heavy rig = more lag
        assert heavy.lag_frames > light.lag_frames
