"""
Cinema Camera Rig v4.0 — Protocol Conformance Tests

Tests all v3.0 foundation + v4.0 mechanical/dynamic dataclasses.
"""

import math
import sys
import os
import pytest
from pathlib import Path

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
    OpticalResult,
    SensorSpec,
    SqueezeBreathingCurve,
)


# ── Fixtures ───────────────────────────────────────────────

@pytest.fixture
def focus_ring():
    return GearRingSpec(rotation_deg=300.0, gear_teeth=140, gear_module=0.8)


@pytest.fixture
def iris_ring():
    return GearRingSpec(rotation_deg=90.0, gear_teeth=134, gear_module=0.8)


@pytest.fixture
def mechanical_spec(focus_ring, iris_ring):
    return MechanicalSpec(
        weight_kg=3.6,
        length_mm=205.0,
        front_diameter_mm=110.0,
        filter_thread="M105x0.75",
        focus_ring=focus_ring,
        iris_ring=iris_ring,
        entrance_pupil_offset_mm=125.0,
    )


@pytest.fixture
def squeeze_curve():
    return SqueezeBreathingCurve(
        points=(
            (0.85, 1.85),
            (1.5, 1.92),
            (3.0, 1.97),
            (10.0, 1.99),
            (1e10, 2.0),
        ),
        nominal_squeeze=2.0,
    )


@pytest.fixture
def lens_spec_v4(mechanical_spec, squeeze_curve):
    return LensSpec(
        lens_id="cooke_ana_i_s35_50mm",
        manufacturer="Cooke",
        series="Anamorphic/i S35",
        focal_length_mm=50.0,
        t_stop_min=2.3,
        t_stop_max=22.0,
        iris_blades=11,
        close_focus_m=0.85,
        image_circle_mm=31.1,
        squeeze_ratio=2.0,
        distortion=DistortionModel(k1=-0.015, k2=0.002, squeeze_uniformity=0.94),
        breathing=BreathingCurve(((0.85, 3.2), (2.0, 1.1), (1e10, 0.0))),
        mechanics=mechanical_spec,
        squeeze_breathing=squeeze_curve,
    )


@pytest.fixture
def lens_spec_v3():
    """v3.0 LensSpec without mechanical data -- backwards compat."""
    return LensSpec(
        lens_id="test_spherical_50mm",
        manufacturer="Test",
        series="Spherical",
        focal_length_mm=50.0,
        t_stop_min=1.4,
        t_stop_max=22.0,
        iris_blades=9,
        close_focus_m=0.45,
        image_circle_mm=43.3,
        squeeze_ratio=1.0,
        distortion=DistortionModel(k1=-0.01),
        breathing=BreathingCurve(),
    )


@pytest.fixture
def camera_state():
    return CameraState(
        model="ARRI ALEXA 35",
        sensor=SensorSpec(width_mm=27.99, height_mm=19.22, native_iso=800),
        format=FormatSpec(4608, 3164),
        exposure_index=800,
        shutter_angle_deg=180.0,
    )


# ── GearRingSpec Tests ─────────────────────────────────────

class TestGearRingSpec:
    def test_pitch_circle_diameter(self, focus_ring):
        """140 teeth x 0.8 module = 112mm PCD."""
        assert focus_ring.pitch_circle_diameter_mm == pytest.approx(112.0)

    def test_degrees_per_tooth(self, focus_ring):
        assert focus_ring.degrees_per_tooth == pytest.approx(300.0 / 140.0)

    def test_rejects_zero_rotation(self):
        with pytest.raises(ValueError, match="Invalid gear rotation"):
            GearRingSpec(rotation_deg=0, gear_teeth=100)

    def test_rejects_negative_teeth(self):
        with pytest.raises(ValueError, match="Invalid gear tooth count"):
            GearRingSpec(rotation_deg=300, gear_teeth=-1)

    def test_rejects_zero_module(self):
        with pytest.raises(ValueError, match="Invalid gear module"):
            GearRingSpec(rotation_deg=300, gear_teeth=100, gear_module=0)


# ── MechanicalSpec Tests ───────────────────────────────────

class TestMechanicalSpec:
    def test_valid_construction(self, mechanical_spec):
        assert mechanical_spec.weight_kg == 3.6
        assert mechanical_spec.entrance_pupil_offset_mm == 125.0

    def test_entrance_pupil_offset_cm(self, mechanical_spec):
        assert mechanical_spec.entrance_pupil_offset_cm == pytest.approx(12.5)

    def test_weight_lbs(self, mechanical_spec):
        assert mechanical_spec.weight_lbs == pytest.approx(3.6 * 2.20462)

    def test_rejects_zero_weight(self, focus_ring, iris_ring):
        with pytest.raises(ValueError, match="Invalid weight"):
            MechanicalSpec(
                weight_kg=0, length_mm=200, front_diameter_mm=110,
                filter_thread="M105x0.75", focus_ring=focus_ring,
                iris_ring=iris_ring, entrance_pupil_offset_mm=100,
            )

    def test_rejects_negative_offset(self, focus_ring, iris_ring):
        with pytest.raises(ValueError, match="Invalid entrance pupil offset"):
            MechanicalSpec(
                weight_kg=3.0, length_mm=200, front_diameter_mm=110,
                filter_thread="M105x0.75", focus_ring=focus_ring,
                iris_ring=iris_ring, entrance_pupil_offset_mm=-10,
            )


# ── SqueezeBreathingCurve Tests ────────────────────────────

class TestSqueezeBreathingCurve:
    def test_evaluate_at_mod(self, squeeze_curve):
        """50mm: 1.85 at MOD (0.85m)."""
        assert squeeze_curve.evaluate(0.85) == pytest.approx(1.85)

    def test_evaluate_at_infinity(self, squeeze_curve):
        """2.0 at infinity."""
        assert squeeze_curve.evaluate(1e10) == pytest.approx(2.0)

    def test_evaluate_interpolation_mid(self, squeeze_curve):
        """Interpolation between 0.85m and 1.5m."""
        val = squeeze_curve.evaluate(1.175)  # midpoint
        assert 1.85 < val < 1.92

    def test_evaluate_below_mod(self, squeeze_curve):
        """Below MOD clamps to first point."""
        assert squeeze_curve.evaluate(0.5) == pytest.approx(1.85)

    def test_empty_curve_returns_nominal(self):
        curve = SqueezeBreathingCurve(points=(), nominal_squeeze=2.0)
        assert curve.evaluate(5.0) == pytest.approx(2.0)

    def test_sorts_points(self):
        """Points provided out of order get sorted."""
        curve = SqueezeBreathingCurve(
            points=((10.0, 1.99), (0.85, 1.85), (3.0, 1.97)),
            nominal_squeeze=2.0,
        )
        assert curve.points[0][0] == 0.85
        assert curve.points[-1][0] == 10.0

    def test_rejects_invalid_squeeze(self):
        with pytest.raises(ValueError, match="Invalid squeeze"):
            SqueezeBreathingCurve(
                points=((1.0, 0.5),),  # squeeze below 1.0
                nominal_squeeze=2.0,
            )


# ── LensSpec v4.0 Tests ───────────────────────────────────

class TestLensSpec:
    def test_is_anamorphic(self, lens_spec_v4):
        assert lens_spec_v4.is_anamorphic is True

    def test_has_mechanics(self, lens_spec_v4):
        assert lens_spec_v4.has_mechanics is True

    def test_entrance_pupil_from_mechanics(self, lens_spec_v4):
        assert lens_spec_v4.entrance_pupil_offset_mm == pytest.approx(125.0)

    def test_effective_squeeze_at_focus(self, lens_spec_v4):
        """50mm: 1.85 at 0.85m, 2.0 at infinity."""
        assert lens_spec_v4.effective_squeeze(0.85) == pytest.approx(1.85)
        assert lens_spec_v4.effective_squeeze(1e10) == pytest.approx(2.0)

    def test_backfill_weight_from_mechanics(self, lens_spec_v4):
        """MechanicalSpec backfills v3.0 weight_kg field."""
        assert lens_spec_v4.weight_kg == pytest.approx(3.6)

    def test_backwards_compat_no_mechanics(self, lens_spec_v3):
        """v3.0 LensSpec without mechanics loads cleanly."""
        assert lens_spec_v3.has_mechanics is False
        assert lens_spec_v3.entrance_pupil_offset_mm == 0.0
        assert lens_spec_v3.effective_squeeze(5.0) == pytest.approx(1.0)
        assert lens_spec_v3.is_anamorphic is False

    def test_rejects_invalid_focal_length(self):
        with pytest.raises(ValueError, match="Invalid focal length"):
            LensSpec(
                lens_id="bad", manufacturer="", series="", focal_length_mm=-1,
                t_stop_min=2.0, t_stop_max=22.0, iris_blades=9,
                close_focus_m=0.5, image_circle_mm=30, squeeze_ratio=1.0,
                distortion=DistortionModel(), breathing=BreathingCurve(),
            )


# ── LensState v4.0 Tests ──────────────────────────────────

class TestLensState:
    def test_effective_squeeze(self, lens_spec_v4):
        state = LensState(spec=lens_spec_v4, t_stop=2.8, focus_distance_m=2.0)
        # At 2.0m, interpolated between 1.92 (1.5m) and 1.97 (3.0m)
        squeeze = state.effective_squeeze
        assert 1.92 < squeeze < 1.97

    def test_entrance_pupil_offset_cm(self, lens_spec_v4):
        state = LensState(spec=lens_spec_v4, t_stop=2.8, focus_distance_m=2.0)
        assert state.entrance_pupil_offset_cm == pytest.approx(12.5)

    def test_rig_weight(self, lens_spec_v4):
        state = LensState(spec=lens_spec_v4, t_stop=2.8, focus_distance_m=2.0)
        assert state.rig_weight_kg == pytest.approx(3.6)

    def test_to_usd_dict_has_mechanical_attrs(self, lens_spec_v4):
        state = LensState(spec=lens_spec_v4, t_stop=2.8, focus_distance_m=2.0)
        usd = state.to_usd_dict()
        assert "cinema:lens:entrancePupilOffsetMm" in usd
        assert usd["cinema:lens:weightKg"][1] == pytest.approx(3.6)

    def test_rejects_tstop_below_min(self, lens_spec_v4):
        with pytest.raises(ValueError, match="T-stop"):
            LensState(spec=lens_spec_v4, t_stop=1.0, focus_distance_m=2.0)

    def test_rejects_focus_below_close(self, lens_spec_v4):
        with pytest.raises(ValueError, match="Focus"):
            LensState(spec=lens_spec_v4, t_stop=2.8, focus_distance_m=0.5)


# ── CameraState Tests ─────────────────────────────────────

class TestCameraState:
    def test_active_dimensions(self, camera_state):
        assert camera_state.active_width_mm == pytest.approx(27.99)
        assert camera_state.active_height_mm == pytest.approx(19.22)

    def test_to_usd_dict(self, camera_state):
        usd = camera_state.to_usd_dict()
        assert usd["cinema:camera:model"][1] == "ARRI ALEXA 35"
        assert usd["cinema:camera:exposureIndex"][1] == 800


# ── JSON Round-trip Test ───────────────────────────────────

class TestJsonRoundtrip:
    def test_load_cooke_50mm(self):
        """Load Cooke 50mm v4.0 JSON and verify key values."""
        json_path = Path(__file__).parent.parent / "lenses" / "cooke_ana_i_s35_50mm.json"
        if not json_path.exists():
            pytest.skip("Cooke 50mm JSON not found")

        from cinema_camera.lenses.cooke_anamorphic import CookeAnamorphicLens
        lens = CookeAnamorphicLens.from_json(json_path)
        spec = lens.spec

        assert spec.lens_id == "cooke_ana_i_s35_50mm"
        assert spec.focal_length_mm == pytest.approx(50.0)
        assert spec.has_mechanics is True
        assert spec.mechanics.weight_kg == pytest.approx(3.6)
        assert spec.mechanics.entrance_pupil_offset_mm == pytest.approx(125.0)
        assert spec.effective_squeeze(0.85) == pytest.approx(1.85)
        assert spec.effective_squeeze(1e10) == pytest.approx(2.0)

    def test_load_cooke_300mm(self):
        """Load Cooke 300mm v4.0 JSON and verify key values."""
        json_path = Path(__file__).parent.parent / "lenses" / "cooke_ana_i_s35_300mm.json"
        if not json_path.exists():
            pytest.skip("Cooke 300mm JSON not found")

        from cinema_camera.lenses.cooke_anamorphic import CookeAnamorphicLens
        lens = CookeAnamorphicLens.from_json(json_path)
        spec = lens.spec

        assert spec.lens_id == "cooke_ana_i_s35_300mm"
        assert spec.focal_length_mm == pytest.approx(300.0)
        assert spec.has_mechanics is True
        assert spec.mechanics.weight_kg == pytest.approx(9.4)

    def test_load_v3_json_without_mechanics(self, tmp_path):
        """v3.0 JSON (no mechanics field) loads into v4.0 LensSpec."""
        import json
        v3_data = {
            "lens_id": "test_v3_lens",
            "manufacturer": "Test",
            "series": "TestSeries",
            "focal_length_mm": 85.0,
            "t_stop_range": [1.4, 22.0],
            "iris_blades": 9,
            "close_focus_m": 0.7,
            "image_circle_mm": 43.3,
            "squeeze_ratio": 1.0,
        }
        json_file = tmp_path / "test_v3.json"
        json_file.write_text(json.dumps(v3_data), encoding="utf-8")

        from cinema_camera.lenses.cooke_anamorphic import CookeAnamorphicLens
        lens = CookeAnamorphicLens.from_json(json_file)
        spec = lens.spec

        assert spec.has_mechanics is False
        assert spec.mechanics is None
        assert spec.squeeze_breathing is None
        assert spec.effective_squeeze(5.0) == pytest.approx(1.0)
