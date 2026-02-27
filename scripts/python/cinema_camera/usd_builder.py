"""
Cinema Camera Rig v4.0 -- USD Camera Rig Builder

Builds the nodal-parallax-correct USD Xform hierarchy and configures
Karma render products with ASWF/Cooke /i EXR metadata.

Pillars B + E: Transform hierarchy and pipeline bridge.
No Houdini GUI required -- uses pxr module only.
"""

from __future__ import annotations

from typing import Any

from pxr import Gf, Sdf, Usd, UsdGeom, UsdRender

from .protocols import CameraState, LensState, OpticalResult


# ════════════════════════════════════════════════════════════
# BODY OFFSET CONSTANTS (mm -> cm)
# ════════════════════════════════════════════════════════════

_BODY_OFFSETS_CM: dict[str, dict[str, float]] = {
    "ARRI ALEXA 35":  {"y": 5.0, "z": -8.0},
    "RED KOMODO":     {"y": 3.5, "z": -5.0},
    "SONY VENICE 2":  {"y": 5.5, "z": -9.0},
}
_DEFAULT_BODY_OFFSET: dict[str, float] = {"y": 4.0, "z": -7.0}


# ════════════════════════════════════════════════════════════
# USD ATTRIBUTE AUTHORING HELPERS
# ════════════════════════════════════════════════════════════

_SDF_TYPE_MAP = {
    "String": Sdf.ValueTypeNames.String,
    "Float":  Sdf.ValueTypeNames.Float,
    "Int":    Sdf.ValueTypeNames.Int,
}


def _author_attributes(
    prim: Usd.Prim,
    attrs: dict[str, tuple[str, Any]],
) -> None:
    """Author custom attributes from a {name: (type_name, value)} dict."""
    for attr_name, (type_name, value) in attrs.items():
        sdf_type = _SDF_TYPE_MAP.get(type_name)
        if sdf_type is None:
            continue
        attr = prim.CreateAttribute(attr_name, sdf_type)
        attr.Set(value)


# ════════════════════════════════════════════════════════════
# PILLAR B: NODAL PARALLAX USD HIERARCHY
# ════════════════════════════════════════════════════════════

def build_usd_camera_rig(
    stage: Usd.Stage,
    rig_path: str,
    camera_state: CameraState,
    lens_state: LensState,
    optical_result: OpticalResult,
    fluid_head_model: str = "OConnor 2575",
) -> UsdGeom.Camera:
    """
    Build a nodal-parallax-correct camera rig in USD.

    Xform hierarchy:
        /rig_path                          RIG ROOT (user transforms)
          /FluidHead                       PIVOT (pan/tilt origin)
            /Body                          CAMERA BODY (sensor plane)
              /Sensor                      UsdGeom.Camera
                /EntrancePupil             NODAL POINT (guide)

    Returns the UsdGeom.Camera at the Sensor prim.
    """
    # ── Xform: Rig Root ──────────────────────────────────
    rig_xform = UsdGeom.Xform.Define(stage, rig_path)

    # ── Xform: Fluid Head (pan/tilt pivot) ───────────────
    head_path = f"{rig_path}/FluidHead"
    head_xform = UsdGeom.Xform.Define(stage, head_path)
    head_xform.AddRotateXYZOp()  # tilt, pan, roll applied here

    # ── Xform: Camera Body ───────────────────────────────
    body_path = f"{head_path}/Body"
    body_xform = UsdGeom.Xform.Define(stage, body_path)
    offsets = _BODY_OFFSETS_CM.get(camera_state.model, _DEFAULT_BODY_OFFSET)
    body_xform.AddTranslateOp().Set(
        Gf.Vec3d(0.0, offsets["y"], offsets["z"])
    )

    # ── Camera: Sensor ───────────────────────────────────
    sensor_path = f"{body_path}/Sensor"
    camera = UsdGeom.Camera.Define(stage, sensor_path)

    # Core camera attributes (USD units: mm for aperture/focal, cm for focus)
    camera.CreateHorizontalApertureAttr().Set(camera_state.active_width_mm)
    camera.CreateVerticalApertureAttr().Set(camera_state.active_height_mm)
    camera.CreateFocalLengthAttr().Set(lens_state.spec.focal_length_mm)
    camera.CreateFocusDistanceAttr().Set(lens_state.focus_distance_m * 100.0)
    camera.CreateFStopAttr().Set(lens_state.t_stop)
    camera.CreateClippingRangeAttr().Set(Gf.Vec2f(0.01, 100000.0))

    # Cinema rig custom attributes
    sensor_prim = camera.GetPrim()
    rig_attrs = {
        "cinema:rig:entrancePupilOffsetCm": ("Float", lens_state.entrance_pupil_offset_cm),
        "cinema:rig:combinedWeightKg":      ("Float", lens_state.rig_weight_kg),
        "cinema:rig:effectiveSqueeze":      ("Float", lens_state.effective_squeeze),
        "cinema:rig:fluidHeadModel":        ("String", fluid_head_model),
    }
    _author_attributes(sensor_prim, rig_attrs)

    # Optics results
    optics_attrs = {
        "cinema:optics:hfovDeg":      ("Float", optical_result.hfov_deg),
        "cinema:optics:vfovDeg":      ("Float", optical_result.vfov_deg),
        "cinema:optics:dofNearM":     ("Float", optical_result.dof_near_m),
        "cinema:optics:dofFarM":      ("Float", optical_result.dof_far_m),
        "cinema:optics:hyperfocalM":  ("Float", optical_result.hyperfocal_m),
        "cinema:optics:cocMm":        ("Float", optical_result.coc_mm),
    }
    _author_attributes(sensor_prim, optics_attrs)

    # Lens state attributes
    _author_attributes(sensor_prim, camera_state.to_usd_dict())
    _author_attributes(sensor_prim, lens_state.to_usd_dict())

    # ── Xform: Entrance Pupil (guide visualization) ──────
    pupil_path = f"{sensor_path}/EntrancePupil"
    pupil_xform = UsdGeom.Xform.Define(stage, pupil_path)
    pupil_xform.AddTranslateOp().Set(
        Gf.Vec3d(0.0, 0.0, lens_state.entrance_pupil_offset_cm)
    )
    pupil_prim = pupil_xform.GetPrim()
    UsdGeom.Imageable(pupil_prim).CreatePurposeAttr().Set(
        UsdGeom.Tokens.guide
    )

    return camera


def build_usd_camera(
    stage: Usd.Stage,
    camera_path: str,
    camera_state: CameraState,
    lens_state: LensState,
    optical_result: OpticalResult,
) -> UsdGeom.Camera:
    """Backwards-compatible v3.0 wrapper. Builds flat camera without rig hierarchy."""
    camera = UsdGeom.Camera.Define(stage, camera_path)
    camera.CreateHorizontalApertureAttr().Set(camera_state.active_width_mm)
    camera.CreateVerticalApertureAttr().Set(camera_state.active_height_mm)
    camera.CreateFocalLengthAttr().Set(lens_state.spec.focal_length_mm)
    camera.CreateFocusDistanceAttr().Set(lens_state.focus_distance_m * 100.0)
    camera.CreateFStopAttr().Set(lens_state.t_stop)
    camera.CreateClippingRangeAttr().Set(Gf.Vec2f(0.01, 100000.0))

    prim = camera.GetPrim()
    _author_attributes(prim, camera_state.to_usd_dict())
    _author_attributes(prim, lens_state.to_usd_dict())

    optics_attrs = {
        "cinema:optics:hfovDeg":      ("Float", optical_result.hfov_deg),
        "cinema:optics:vfovDeg":      ("Float", optical_result.vfov_deg),
        "cinema:optics:dofNearM":     ("Float", optical_result.dof_near_m),
        "cinema:optics:dofFarM":      ("Float", optical_result.dof_far_m),
        "cinema:optics:hyperfocalM":  ("Float", optical_result.hyperfocal_m),
        "cinema:optics:cocMm":        ("Float", optical_result.coc_mm),
    }
    _author_attributes(prim, optics_attrs)

    return camera


# ════════════════════════════════════════════════════════════
# PILLAR E: PIPELINE BRIDGE -- EXR METADATA
# ════════════════════════════════════════════════════════════

def configure_render_product(
    stage: Usd.Stage,
    camera_path: str,
    output_path: str,
    camera_state: CameraState,
    lens_state: LensState,
    pixel_aspect: float = 1.0,
) -> UsdRender.Product:
    """
    Configure USD Render Product with Cooke /i + ASWF metadata.

    Bakes lens and camera metadata into OpenEXR headers so
    downstream compositors (Nuke, Resolve, Flame) can
    automatically extract match-move parameters.

    Metadata conforms to:
    - ASWF OpenEXR Technical Committee recommended attributes
    - Cooke /i Technology data stream format
    - ARRI camera metadata standard
    """
    cam_name = camera_path.split("/")[-1]
    product_path = f"/Render/Products/{cam_name}"
    product = UsdRender.Product.Define(stage, product_path)

    # ── Standard render product ──────────────────────────
    product.CreateResolutionAttr().Set(
        Gf.Vec2i(camera_state.format.width_px, camera_state.format.height_px)
    )
    product.CreatePixelAspectRatioAttr().Set(pixel_aspect)
    product.GetCameraRel().SetTargets([Sdf.Path(camera_path)])
    product.CreateProductNameAttr().Set(output_path)

    # ── ASWF / Cooke /i EXR Metadata ────────────────────
    prim = product.GetPrim()
    d = lens_state.spec.distortion

    exr_metadata: dict[str, tuple[str, Any]] = {
        # Camera identification
        "driver:parameters:OpenEXR:camera:model":
            ("String", camera_state.model),
        "driver:parameters:OpenEXR:camera:sensorWidthMm":
            ("Float", camera_state.active_width_mm),
        "driver:parameters:OpenEXR:camera:sensorHeightMm":
            ("Float", camera_state.active_height_mm),
        "driver:parameters:OpenEXR:camera:exposureIndex":
            ("Int", camera_state.exposure_index),
        "driver:parameters:OpenEXR:camera:shutterAngleDeg":
            ("Float", camera_state.shutter_angle_deg),
        "driver:parameters:OpenEXR:camera:colorScience":
            ("String", camera_state.sensor.color_science),

        # Lens identification (Cooke /i format)
        "driver:parameters:OpenEXR:lens:manufacturer":
            ("String", lens_state.spec.manufacturer),
        "driver:parameters:OpenEXR:lens:series":
            ("String", lens_state.spec.series),
        "driver:parameters:OpenEXR:lens:focalLengthMm":
            ("Float", lens_state.spec.focal_length_mm),
        "driver:parameters:OpenEXR:lens:tStop":
            ("Float", lens_state.t_stop),
        "driver:parameters:OpenEXR:lens:focusDistanceM":
            ("Float", lens_state.focus_distance_m),
        "driver:parameters:OpenEXR:lens:irisBlades":
            ("Int", lens_state.spec.iris_blades),
        "driver:parameters:OpenEXR:lens:squeezeRatio":
            ("Float", lens_state.effective_squeeze),

        # Distortion model (for Nuke STMap/LensDistortion nodes)
        "driver:parameters:OpenEXR:lens:distortion:k1": ("Float", d.k1),
        "driver:parameters:OpenEXR:lens:distortion:k2": ("Float", d.k2),
        "driver:parameters:OpenEXR:lens:distortion:k3": ("Float", d.k3),
        "driver:parameters:OpenEXR:lens:distortion:p1": ("Float", d.p1),
        "driver:parameters:OpenEXR:lens:distortion:p2": ("Float", d.p2),
    }

    # Mechanical metadata (if available)
    if lens_state.spec.has_mechanics:
        m = lens_state.spec.mechanics
        exr_metadata.update({
            "driver:parameters:OpenEXR:lens:entrancePupilOffsetMm":
                ("Float", m.entrance_pupil_offset_mm),
            "driver:parameters:OpenEXR:lens:weightKg":
                ("Float", m.weight_kg),
        })

    _author_attributes(prim, exr_metadata)

    return product
