"""
Tests for usd_builder.py and karma_lens_shader.py.

Validates:
- USD Xform hierarchy (Pillar B)
- EXR metadata pipeline (Pillar E)
- Shader parameter binding (Pillar D)
- Backwards-compatible build_usd_camera wrapper

These tests use the pxr module (USD) and require hython or a USD-enabled
Python environment. When run under standard pytest without pxr, they skip.
"""

from __future__ import annotations

import sys

import pytest

# Skip entire module if pxr is not available
pxr = pytest.importorskip("pxr", reason="pxr (USD) not available -- run with hython or USD-enabled Python")

from pxr import Gf, Sdf, Usd, UsdGeom, UsdRender, UsdShade

# Add scripts/python to path for cinema_camera imports
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "scripts" / "python"))

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
from cinema_camera.usd_builder import (
    _BODY_OFFSETS_CM,
    _DEFAULT_BODY_OFFSET,
    build_usd_camera,
    build_usd_camera_rig,
    configure_render_product,
)
from cinema_camera.karma_lens_shader import bind_lens_shader


# ════════════════════════════════════════════════════════════
# FIXTURES
# ════════════════════════════════════════════════════════════

@pytest.fixture
def alexa35_camera() -> CameraState:
    return CameraState(
        model="ARRI ALEXA 35",
        sensor=SensorSpec(width_mm=27.99, height_mm=19.22, native_iso=800,
                          color_science="ARRI LogC4", pixel_pitch_um=6.075),
        format=FormatSpec(width_px=4608, height_px=3164, name="4.6K 3:2 OG"),
        exposure_index=800,
        shutter_angle_deg=180.0,
    )


@pytest.fixture
def komodo_camera() -> CameraState:
    return CameraState(
        model="RED KOMODO",
        sensor=SensorSpec(width_mm=27.03, height_mm=14.26, native_iso=800,
                          color_science="REDWideGamutRGB"),
        format=FormatSpec(width_px=6144, height_px=3240, name="6K"),
        exposure_index=800,
    )


def _make_cooke_50mm_spec() -> LensSpec:
    return LensSpec(
        lens_id="cooke_ana_i_s35_50mm",
        manufacturer="Cooke",
        series="Anamorphic/i S35",
        focal_length_mm=50.0,
        t_stop_min=2.3,
        t_stop_max=22.0,
        iris_blades=11,
        close_focus_m=0.85,
        image_circle_mm=33.0,
        squeeze_ratio=2.0,
        distortion=DistortionModel(
            k1=-0.038, k2=0.012, k3=-0.001,
            p1=0.002, p2=-0.001, squeeze_uniformity=0.92,
        ),
        breathing=BreathingCurve(points=((0.85, 3.8), (10.0, 0.5), (1e6, 0.0))),
        mechanics=MechanicalSpec(
            weight_kg=3.6, length_mm=205.0, front_diameter_mm=110.0,
            filter_thread="M105x0.75",
            focus_ring=GearRingSpec(rotation_deg=300.0, gear_teeth=143, gear_module=0.8),
            iris_ring=GearRingSpec(rotation_deg=36.0, gear_teeth=119, gear_module=0.8),
            entrance_pupil_offset_mm=125.0,
        ),
        squeeze_breathing=SqueezeBreathingCurve(
            points=((0.85, 1.85), (2.0, 1.92), (5.0, 1.97), (20.0, 1.99), (1e6, 2.0)),
            nominal_squeeze=2.0,
        ),
    )


@pytest.fixture
def cooke_50mm_spec() -> LensSpec:
    return _make_cooke_50mm_spec()


@pytest.fixture
def lens_state_50mm(cooke_50mm_spec) -> LensState:
    return LensState(spec=cooke_50mm_spec, t_stop=2.8, focus_distance_m=3.0)


@pytest.fixture
def optical_result() -> OpticalResult:
    return OpticalResult(
        hfov_deg=30.5, vfov_deg=21.0,
        dof_near_m=2.5, dof_far_m=3.7,
        hyperfocal_m=53.2, coc_mm=0.0226,
    )


@pytest.fixture
def stage() -> Usd.Stage:
    return Usd.Stage.CreateInMemory()


# ════════════════════════════════════════════════════════════
# PILLAR B: USD RIG HIERARCHY
# ════════════════════════════════════════════════════════════

class TestRigHierarchy:
    """Validate USD Xform hierarchy structure."""

    def test_all_prim_paths_exist(self, stage, alexa35_camera, lens_state_50mm, optical_result):
        build_usd_camera_rig(stage, "/World/CameraRig", alexa35_camera, lens_state_50mm, optical_result)

        expected = [
            "/World/CameraRig",
            "/World/CameraRig/FluidHead",
            "/World/CameraRig/FluidHead/Body",
            "/World/CameraRig/FluidHead/Body/Sensor",
            "/World/CameraRig/FluidHead/Body/Sensor/EntrancePupil",
        ]
        for path in expected:
            assert stage.GetPrimAtPath(path).IsValid(), f"Missing: {path}"

    def test_sensor_is_camera(self, stage, alexa35_camera, lens_state_50mm, optical_result):
        cam = build_usd_camera_rig(stage, "/World/CameraRig", alexa35_camera, lens_state_50mm, optical_result)
        assert cam.GetPrim().GetTypeName() == "Camera"

    def test_fluid_head_has_rotate_op(self, stage, alexa35_camera, lens_state_50mm, optical_result):
        build_usd_camera_rig(stage, "/World/CameraRig", alexa35_camera, lens_state_50mm, optical_result)
        head = UsdGeom.Xform(stage.GetPrimAtPath("/World/CameraRig/FluidHead"))
        ops = head.GetOrderedXformOps()
        assert len(ops) >= 1
        assert "rotateXYZ" in ops[0].GetOpName()

    def test_entrance_pupil_is_guide(self, stage, alexa35_camera, lens_state_50mm, optical_result):
        build_usd_camera_rig(stage, "/World/CameraRig", alexa35_camera, lens_state_50mm, optical_result)
        pupil = stage.GetPrimAtPath("/World/CameraRig/FluidHead/Body/Sensor/EntrancePupil")
        purpose = UsdGeom.Imageable(pupil).GetPurposeAttr().Get()
        assert purpose == UsdGeom.Tokens.guide


class TestEntrancePupilOffset:
    """Validate entrance pupil offset is authored correctly."""

    def test_50mm_offset(self, stage, alexa35_camera, lens_state_50mm, optical_result):
        build_usd_camera_rig(stage, "/World/Rig", alexa35_camera, lens_state_50mm, optical_result)
        sensor = stage.GetPrimAtPath("/World/Rig/FluidHead/Body/Sensor")
        val = sensor.GetAttribute("cinema:rig:entrancePupilOffsetCm").Get()
        assert val == pytest.approx(12.5, abs=0.01)  # 125mm -> 12.5cm

    def test_pupil_xform_matches_offset(self, stage, alexa35_camera, lens_state_50mm, optical_result):
        build_usd_camera_rig(stage, "/World/Rig", alexa35_camera, lens_state_50mm, optical_result)
        pupil = UsdGeom.Xform(stage.GetPrimAtPath("/World/Rig/FluidHead/Body/Sensor/EntrancePupil"))
        ops = pupil.GetOrderedXformOps()
        translate = ops[0].Get()
        assert translate[2] == pytest.approx(12.5, abs=0.01)


class TestBodyOffset:
    """Validate per-camera body offsets."""

    def test_alexa35_offset(self, stage, alexa35_camera, lens_state_50mm, optical_result):
        build_usd_camera_rig(stage, "/World/Rig", alexa35_camera, lens_state_50mm, optical_result)
        body = UsdGeom.Xform(stage.GetPrimAtPath("/World/Rig/FluidHead/Body"))
        ops = body.GetOrderedXformOps()
        translate = ops[0].Get()
        assert translate[1] == pytest.approx(5.0)   # ARRI ALEXA 35 y=5.0
        assert translate[2] == pytest.approx(-8.0)   # z=-8.0

    def test_komodo_offset(self, stage, komodo_camera, lens_state_50mm, optical_result):
        build_usd_camera_rig(stage, "/World/Rig", komodo_camera, lens_state_50mm, optical_result)
        body = UsdGeom.Xform(stage.GetPrimAtPath("/World/Rig/FluidHead/Body"))
        ops = body.GetOrderedXformOps()
        translate = ops[0].Get()
        assert translate[1] == pytest.approx(3.5)    # RED KOMODO y=3.5
        assert translate[2] == pytest.approx(-5.0)

    def test_unknown_camera_uses_default(self, stage, lens_state_50mm, optical_result):
        unknown_cam = CameraState(
            model="Unknown Camera",
            sensor=SensorSpec(width_mm=24.0, height_mm=13.5),
            format=FormatSpec(width_px=1920, height_px=1080),
        )
        build_usd_camera_rig(stage, "/World/Rig", unknown_cam, lens_state_50mm, optical_result)
        body = UsdGeom.Xform(stage.GetPrimAtPath("/World/Rig/FluidHead/Body"))
        ops = body.GetOrderedXformOps()
        translate = ops[0].Get()
        assert translate[1] == pytest.approx(_DEFAULT_BODY_OFFSET["y"])
        assert translate[2] == pytest.approx(_DEFAULT_BODY_OFFSET["z"])


class TestCameraAttributes:
    """Validate USD camera attributes."""

    def test_core_camera_attrs(self, stage, alexa35_camera, lens_state_50mm, optical_result):
        cam = build_usd_camera_rig(stage, "/World/Rig", alexa35_camera, lens_state_50mm, optical_result)
        assert cam.GetHorizontalApertureAttr().Get() == pytest.approx(27.99)
        assert cam.GetVerticalApertureAttr().Get() == pytest.approx(19.22)
        assert cam.GetFocalLengthAttr().Get() == pytest.approx(50.0)
        assert cam.GetFStopAttr().Get() == pytest.approx(2.8)
        # Focus distance: 3.0m -> 300cm
        assert cam.GetFocusDistanceAttr().Get() == pytest.approx(300.0)

    def test_cinema_rig_attrs(self, stage, alexa35_camera, lens_state_50mm, optical_result):
        build_usd_camera_rig(stage, "/World/Rig", alexa35_camera, lens_state_50mm, optical_result)
        sensor = stage.GetPrimAtPath("/World/Rig/FluidHead/Body/Sensor")
        assert sensor.GetAttribute("cinema:rig:fluidHeadModel").Get() == "OConnor 2575"
        weight = sensor.GetAttribute("cinema:rig:combinedWeightKg").Get()
        assert weight == pytest.approx(3.6, abs=0.01)  # lens weight only (body added at assembly)

    def test_optics_attrs(self, stage, alexa35_camera, lens_state_50mm, optical_result):
        build_usd_camera_rig(stage, "/World/Rig", alexa35_camera, lens_state_50mm, optical_result)
        sensor = stage.GetPrimAtPath("/World/Rig/FluidHead/Body/Sensor")
        assert sensor.GetAttribute("cinema:optics:hfovDeg").Get() == pytest.approx(30.5)
        assert sensor.GetAttribute("cinema:optics:dofNearM").Get() == pytest.approx(2.5)

    def test_effective_squeeze_authored(self, stage, alexa35_camera, lens_state_50mm, optical_result):
        build_usd_camera_rig(stage, "/World/Rig", alexa35_camera, lens_state_50mm, optical_result)
        sensor = stage.GetPrimAtPath("/World/Rig/FluidHead/Body/Sensor")
        squeeze = sensor.GetAttribute("cinema:rig:effectiveSqueeze").Get()
        # At 3.0m focus: interpolated between (2.0, 1.92) and (5.0, 1.97)
        assert 1.9 < squeeze < 2.0


class TestBackwardsCompat:
    """Validate build_usd_camera() v3.0 wrapper still works."""

    def test_flat_camera_created(self, stage, alexa35_camera, lens_state_50mm, optical_result):
        cam = build_usd_camera(stage, "/World/Camera", alexa35_camera, lens_state_50mm, optical_result)
        assert cam.GetPrim().IsValid()
        assert cam.GetPrim().GetTypeName() == "Camera"
        assert cam.GetFocalLengthAttr().Get() == pytest.approx(50.0)

    def test_no_rig_hierarchy(self, stage, alexa35_camera, lens_state_50mm, optical_result):
        build_usd_camera(stage, "/World/Camera", alexa35_camera, lens_state_50mm, optical_result)
        # No FluidHead or Body prims should exist
        assert not stage.GetPrimAtPath("/World/Camera/FluidHead").IsValid()


# ════════════════════════════════════════════════════════════
# PILLAR E: EXR METADATA
# ════════════════════════════════════════════════════════════

class TestEXRMetadata:
    """Validate Render Product EXR metadata attributes."""

    def test_render_product_created(self, stage, alexa35_camera, lens_state_50mm):
        build_usd_camera_rig(stage, "/World/Rig", alexa35_camera, lens_state_50mm,
                              OpticalResult(30.5, 21.0, 2.5, 3.7, 53.2, 0.0226))
        product = configure_render_product(
            stage, "/World/Rig/FluidHead/Body/Sensor",
            "/renders/shot.exr", alexa35_camera, lens_state_50mm,
        )
        assert product.GetPrim().IsValid()

    def test_resolution(self, stage, alexa35_camera, lens_state_50mm):
        product = configure_render_product(
            stage, "/World/Camera", "/renders/shot.exr",
            alexa35_camera, lens_state_50mm,
        )
        res = product.GetResolutionAttr().Get()
        assert res == Gf.Vec2i(4608, 3164)

    def test_camera_metadata(self, stage, alexa35_camera, lens_state_50mm):
        product = configure_render_product(
            stage, "/World/Camera", "/renders/shot.exr",
            alexa35_camera, lens_state_50mm,
        )
        prim = product.GetPrim()
        assert prim.GetAttribute("driver:parameters:OpenEXR:camera:model").Get() == "ARRI ALEXA 35"
        assert prim.GetAttribute("driver:parameters:OpenEXR:camera:sensorWidthMm").Get() == pytest.approx(27.99)
        assert prim.GetAttribute("driver:parameters:OpenEXR:camera:exposureIndex").Get() == 800
        assert prim.GetAttribute("driver:parameters:OpenEXR:camera:colorScience").Get() == "ARRI LogC4"

    def test_lens_metadata(self, stage, alexa35_camera, lens_state_50mm):
        product = configure_render_product(
            stage, "/World/Camera", "/renders/shot.exr",
            alexa35_camera, lens_state_50mm,
        )
        prim = product.GetPrim()
        assert prim.GetAttribute("driver:parameters:OpenEXR:lens:manufacturer").Get() == "Cooke"
        assert prim.GetAttribute("driver:parameters:OpenEXR:lens:focalLengthMm").Get() == pytest.approx(50.0)
        assert prim.GetAttribute("driver:parameters:OpenEXR:lens:tStop").Get() == pytest.approx(2.8)
        assert prim.GetAttribute("driver:parameters:OpenEXR:lens:irisBlades").Get() == 11

    def test_distortion_metadata(self, stage, alexa35_camera, lens_state_50mm):
        product = configure_render_product(
            stage, "/World/Camera", "/renders/shot.exr",
            alexa35_camera, lens_state_50mm,
        )
        prim = product.GetPrim()
        assert prim.GetAttribute("driver:parameters:OpenEXR:lens:distortion:k1").Get() == pytest.approx(-0.038)
        assert prim.GetAttribute("driver:parameters:OpenEXR:lens:distortion:p2").Get() == pytest.approx(-0.001)

    def test_mechanical_metadata_present(self, stage, alexa35_camera, lens_state_50mm):
        product = configure_render_product(
            stage, "/World/Camera", "/renders/shot.exr",
            alexa35_camera, lens_state_50mm,
        )
        prim = product.GetPrim()
        assert prim.GetAttribute("driver:parameters:OpenEXR:lens:entrancePupilOffsetMm").Get() == pytest.approx(125.0)
        assert prim.GetAttribute("driver:parameters:OpenEXR:lens:weightKg").Get() == pytest.approx(3.6)

    def test_squeeze_reflects_focus_distance(self, stage, alexa35_camera):
        """Effective squeeze in metadata should reflect the focus distance, not nominal."""
        spec = _make_cooke_50mm_spec()
        ls_close = LensState(spec=spec, t_stop=2.8, focus_distance_m=0.85)
        ls_far = LensState(spec=spec, t_stop=2.8, focus_distance_m=1e6)

        prod_close = configure_render_product(
            stage, "/World/CamClose", "/renders/close.exr",
            alexa35_camera, ls_close,
        )
        prod_far = configure_render_product(
            stage, "/World/CamFar", "/renders/far.exr",
            alexa35_camera, ls_far,
        )

        sq_close = prod_close.GetPrim().GetAttribute(
            "driver:parameters:OpenEXR:lens:squeezeRatio"
        ).Get()
        sq_far = prod_far.GetPrim().GetAttribute(
            "driver:parameters:OpenEXR:lens:squeezeRatio"
        ).Get()

        assert sq_close == pytest.approx(1.85, abs=0.01)
        assert sq_far == pytest.approx(2.0, abs=0.01)
        assert sq_close < sq_far


# ════════════════════════════════════════════════════════════
# PILLAR D: SHADER BINDING
# ════════════════════════════════════════════════════════════

class TestShaderBinding:
    """Validate Karma CVEX lens shader binding."""

    def test_shader_created(self, stage, alexa35_camera, lens_state_50mm):
        UsdGeom.Camera.Define(stage, "/World/Camera")
        shader = bind_lens_shader(stage, "/World/Camera", alexa35_camera, lens_state_50mm)
        assert shader.GetPrim().IsValid()
        assert shader.GetIdAttr().Get() == "karma:cvex:cinema_lens_shader"

    def test_shader_inputs(self, stage, alexa35_camera, lens_state_50mm):
        UsdGeom.Camera.Define(stage, "/World/Camera")
        shader = bind_lens_shader(stage, "/World/Camera", alexa35_camera, lens_state_50mm)
        assert shader.GetInput("focal_length_mm").Get() == pytest.approx(50.0)
        assert shader.GetInput("sensor_width_mm").Get() == pytest.approx(27.99)
        assert shader.GetInput("dist_k1").Get() == pytest.approx(-0.038)
        assert shader.GetInput("dist_sq_uniformity").Get() == pytest.approx(0.92)

    def test_shader_squeeze_from_lens_state(self, stage, alexa35_camera, lens_state_50mm):
        UsdGeom.Camera.Define(stage, "/World/Camera")
        shader = bind_lens_shader(stage, "/World/Camera", alexa35_camera, lens_state_50mm)
        squeeze = shader.GetInput("effective_squeeze").Get()
        # At 3.0m focus, squeeze is interpolated (not nominal 2.0)
        assert 1.9 < squeeze < 2.0

    def test_shader_pupil_offset(self, stage, alexa35_camera, lens_state_50mm):
        UsdGeom.Camera.Define(stage, "/World/Camera")
        shader = bind_lens_shader(stage, "/World/Camera", alexa35_camera, lens_state_50mm)
        offset = shader.GetInput("entrance_pupil_offset_cm").Get()
        assert offset == pytest.approx(12.5, abs=0.01)

    def test_camera_shader_binding_attr(self, stage, alexa35_camera, lens_state_50mm):
        UsdGeom.Camera.Define(stage, "/World/Camera")
        bind_lens_shader(stage, "/World/Camera", alexa35_camera, lens_state_50mm)
        cam_prim = stage.GetPrimAtPath("/World/Camera")
        shader_path = cam_prim.GetAttribute("karma:lens:shader").Get()
        assert shader_path == "/World/Camera/CinemaLensShader"
