"""
Cinema Camera Rig -- Karma Lens Shader Binding

Authors the camera-prim attributes Karma actually consumes for lens
shaders. Format verified empirically against Houdini 21.0.729 (this is
exactly what the Solaris Camera LOP authors when "Use lens shader" is on):

    karma:camera:use_lensshader  (bool)   = True
    karma:camera:lensshader      (string) = "opdef:/Vop/<op>?VflCode k v k v ..."

The shader itself is a VOP HDA compiled from vex/include/karma_cinema_lens.vfl
by builders/build_lens_shader_vop.py (vcc -O vop). The HDA lives in
<repo>/otls/ which Houdini auto-loads via the override package.

Verified on Karma CPU; Karma XPU lens-shader support is unverified -- the
STMap AOV path remains the renderer-agnostic distortion route.

Pillar D: Shader parameter binding layer.
"""

from __future__ import annotations

from typing import Any, Optional

from pxr import Sdf, Usd, UsdGeom

from .protocols import CameraState, LensState

# Operator type name of the compiled lens shader VOP (from the cvex function
# name in karma_cinema_lens.vfl; vcc -O vop names the op after the function).
LENS_SHADER_OP = "cinema_lens_shader"

# HDA section referenced by the opdef string. vcc -O vop emits the source
# into "CVexVflCode" -- and pointing the Camera LOP at our compiled VOP
# authors exactly 'opdef:/Vop/cinema_lens_shader?CVexVflCode k v ...'
# (verified empirically on 21.0.729). VOP-network HDAs use "VflCode"
# instead; build_lens_shader_vop.py asserts the section exists.
OPDEF_SECTION = "CVexVflCode"


def _fmt_value(value: Any) -> str:
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, float):
        return "%.9g" % value
    return str(value)


def build_lensshader_command(values: dict) -> str:
    """Encode shader argument values into the opdef command string."""
    args = " ".join(
        "%s %s" % (name, _fmt_value(value)) for name, value in values.items()
    )
    base = "opdef:/Vop/%s?%s" % (LENS_SHADER_OP, OPDEF_SECTION)
    return ("%s %s" % (base, args)) if args else base


def author_lens_shader(
    stage: Usd.Stage,
    camera_path: str,
    values: dict,
) -> str:
    """
    Author the Karma lens shader binding on the camera prim from a flat
    {shader_arg: value} dict. Returns the authored command string.
    """
    prim = stage.GetPrimAtPath(camera_path)
    if not prim or not prim.IsValid():
        raise ValueError(f"author_lens_shader: no prim at {camera_path}")

    command = build_lensshader_command(values)
    prim.CreateAttribute(
        "karma:camera:use_lensshader", Sdf.ValueTypeNames.Bool
    ).Set(True)
    prim.CreateAttribute(
        "karma:camera:lensshader", Sdf.ValueTypeNames.String
    ).Set(command)
    return command


def bind_lens_shader(
    stage: Usd.Stage,
    camera_path: str,
    camera_state: CameraState,
    lens_state: LensState,
    entrance_pupil_offset_cm: Optional[float] = None,
) -> str:
    """
    Typed-state wrapper: derive shader argument values from CameraState /
    LensState and author the binding. Returns the command string.

    The shader reads focal/aperture/aspect/focus/fstop from Karma directly,
    so only the cinema-specific arguments are encoded here. The entrance
    pupil offset is converted to STAGE UNITS using metersPerUnit (ray
    origins are in camera-space scene units).
    """
    pupil_cm = (entrance_pupil_offset_cm if entrance_pupil_offset_cm is not None
                else lens_state.entrance_pupil_offset_cm)
    meters_per_unit = UsdGeom.GetStageMetersPerUnit(stage) or 0.01
    pupil_units = (pupil_cm / 100.0) / meters_per_unit

    d = lens_state.spec.distortion
    values = {
        "effective_squeeze":     lens_state.effective_squeeze,
        "dist_sq_uniformity":    d.squeeze_uniformity,
        "entrance_pupil_offset": pupil_units,
        "dist_k1": d.k1,
        "dist_k2": d.k2,
        "dist_k3": d.k3,
        "dist_p1": d.p1,
        "dist_p2": d.p2,
        # Pupil / bokeh (Tier 2). iris_blades is real lens data; the bokeh
        # CHARACTER (apodization, blade curvature, mechanical-vignette Rv/k) is
        # a look default here until lens-schema-v5 carries measured per-lens
        # values. Polygonal iris is on by default (physically the lens has N
        # blades; near-circular for cinema counts >= 9). Vignette is opt-in.
        "enable_bokeh":      1,
        "iris_blades":       lens_state.spec.iris_blades,
        "iris_rotation_deg": 0.0,
        "blade_curvature":   0.0,
        "apodization":       0.0,
        "enable_vignette":   0,
        "vignette_rv":       0.5,
        "vignette_k":        0.2,
        "image_circle":      10.0,
    }
    return author_lens_shader(stage, camera_path, values)
