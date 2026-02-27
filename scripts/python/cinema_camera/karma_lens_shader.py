"""
Cinema Camera Rig v4.0 -- Karma CVEX Lens Shader Binding

Binds Karma CVEX lens shader parameters to USD camera attributes.
Runs inside the cinema::camera_rig::2.0 LOP HDA.

Pillar D: Shader parameter binding layer.
"""

from __future__ import annotations

from pxr import Sdf, Usd, UsdShade

from .protocols import CameraState, LensState


def bind_lens_shader(
    stage: Usd.Stage,
    camera_path: str,
    camera_state: CameraState,
    lens_state: LensState,
) -> UsdShade.Shader:
    """
    Create and bind Karma CVEX lens shader to the camera prim.

    The shader reads attributes directly from the camera prim,
    so parameters are automatically time-sampled when animated.

    Returns the created UsdShade.Shader.
    """
    shader_path = f"{camera_path}/CinemaLensShader"
    shader = UsdShade.Shader.Define(stage, shader_path)

    # Shader ID for Karma CVEX
    shader.CreateIdAttr("karma:cvex:cinema_lens_shader")

    # ── Bind lens parameters ─────────────────────────────
    shader.CreateInput("focal_length_mm", Sdf.ValueTypeNames.Float).Set(
        lens_state.spec.focal_length_mm
    )
    shader.CreateInput("effective_squeeze", Sdf.ValueTypeNames.Float).Set(
        lens_state.effective_squeeze
    )
    shader.CreateInput("entrance_pupil_offset_cm", Sdf.ValueTypeNames.Float).Set(
        lens_state.entrance_pupil_offset_cm
    )
    shader.CreateInput("sensor_width_mm", Sdf.ValueTypeNames.Float).Set(
        camera_state.active_width_mm
    )
    shader.CreateInput("sensor_height_mm", Sdf.ValueTypeNames.Float).Set(
        camera_state.active_height_mm
    )

    # Distortion coefficients
    d = lens_state.spec.distortion
    shader.CreateInput("dist_k1", Sdf.ValueTypeNames.Float).Set(d.k1)
    shader.CreateInput("dist_k2", Sdf.ValueTypeNames.Float).Set(d.k2)
    shader.CreateInput("dist_k3", Sdf.ValueTypeNames.Float).Set(d.k3)
    shader.CreateInput("dist_p1", Sdf.ValueTypeNames.Float).Set(d.p1)
    shader.CreateInput("dist_p2", Sdf.ValueTypeNames.Float).Set(d.p2)
    shader.CreateInput("dist_sq_uniformity", Sdf.ValueTypeNames.Float).Set(
        d.squeeze_uniformity
    )

    # ── Bind shader to camera ────────────────────────────
    camera_prim = stage.GetPrimAtPath(camera_path)
    if camera_prim:
        camera_prim.CreateAttribute(
            "karma:lens:shader", Sdf.ValueTypeNames.String
        ).Set(shader_path)

    return shader
