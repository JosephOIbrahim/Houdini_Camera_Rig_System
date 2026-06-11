"""
Cinema Camera Rig -- HDA cook-time runtime.

Single source of truth for everything cinema::camera_rig_lop::3.0's
Python Script LOPs do. Each embedded script inside the HDA is a thin shim:

    import os, sys
    repo = os.environ.get("CINEMA_CAMERA_REPO", "")
    if repo: sys.path.insert(0, os.path.join(repo, "scripts", "python"))
    from cinema_camera import hda_runtime
    hda_runtime.author_camera_rig(hou.pwd())

Every public function takes the Python Script LOP node (hou.pwd()); the
HDA is its parent and the editable stage comes from the script node.
All optics / USD / biomechanics math is delegated to the tested package
modules (optics_engine, usd_builder, biomechanics, karma_lens_shader) --
do not re-inline it here or in builder strings.
"""

from __future__ import annotations

import dataclasses

from . import optics_engine, registry, usd_builder
from .biomechanics import (
    auto_derive_from_weight,
    handheld_shake_offsets,
    solve_damped_spring,
)
from .karma_lens_shader import bind_lens_shader
from .presets import model_for
from .protocols import (
    BreathingCurve,
    CameraState,
    DistortionModel,
    FormatSpec,
    LensSpec,
    LensState,
    SensorSpec,
    SqueezeBreathingCurve,
)


# ════════════════════════════════════════════════════════════
# PARM -> TYPED-STATE RESOLUTION
# ════════════════════════════════════════════════════════════

def rig_path_from(hda) -> str:
    """Normalized rig root path (legacy default '/CinemaRig/Camera' maps
    to '/CinemaRig')."""
    rig_path = hda.evalParm("usd_camera_path")
    if not rig_path or rig_path == "/CinemaRig/Camera":
        rig_path = "/CinemaRig"
    return rig_path


def camera_path_from(hda) -> str:
    return rig_path_from(hda) + "/FluidHead/Body/Sensor"


def resolve_states(hda):
    """
    Build (CameraState, LensState, lens_resolved) from the HDA's parms.

    Parm values are the override layer and win for every directly-authored
    number (focal, distortion, pupil offset...). The resolved LensSpec
    contributes what parms can't express: the squeeze-breathing curve
    (focus-dependent, animatable), FOV-breathing curve, T-stop limits and
    close focus. When lens_id doesn't resolve, a synthetic parm-driven
    spec is built so the rest of the pipeline stays fully typed.
    """
    focal = hda.evalParm("focal_length_mm") or 50.0
    t_stop = hda.evalParm("t_stop") or 2.8
    focus = hda.evalParm("focus_distance_m") or 3.0
    squeeze = max(1.0, hda.evalParm("squeeze_ratio") or 1.0)
    eff_squeeze_parm = hda.evalParm("effective_squeeze") or squeeze

    distortion = DistortionModel(
        k1=hda.evalParm("dist_k1"),
        k2=hda.evalParm("dist_k2"),
        k3=hda.evalParm("dist_k3"),
        p1=hda.evalParm("dist_p1"),
        p2=hda.evalParm("dist_p2"),
        squeeze_uniformity=min(1.0, max(0.8, hda.evalParm("dist_sq_uniformity") or 1.0)),
    )

    body_id = hda.evalParm("body_id") or ""
    camera_state = CameraState(
        model=model_for(body_id) or body_id or "Custom",
        sensor=SensorSpec(
            width_mm=hda.evalParm("sensor_width_mm") or 27.99,
            height_mm=hda.evalParm("sensor_height_mm") or 19.22,
            native_iso=hda.evalParm("native_iso") or 800,
        ),
        format=FormatSpec(
            width_px=hda.evalParm("resolution_x") or 4608,
            height_px=hda.evalParm("resolution_y") or 3164,
        ),
        exposure_index=hda.evalParm("exposure_index") or 800,
        shutter_angle_deg=hda.evalParm("shutter_angle_deg") or 180.0,
    )

    spec = None
    lens_id = (hda.evalParm("lens_id") or "").strip()
    if lens_id:
        try:
            spec = registry.resolve_lens(lens_id)
        except (KeyError, OSError, ValueError):
            spec = None

    resolved = spec is not None
    if resolved:
        # Parm overrides onto the resolved spec; curves stay lens-true.
        spec = dataclasses.replace(
            spec,
            focal_length_mm=focal if focal > 0 else spec.focal_length_mm,
            distortion=distortion,
        )
        # A real lens can't exceed its physical limits: clamp.
        t_stop = min(max(t_stop, spec.t_stop_min), spec.t_stop_max)
        focus = max(focus, spec.close_focus_m)
    else:
        # Synthetic parm-driven spec. The single-point squeeze curve makes
        # LensState.effective_squeeze return the parm value at any focus.
        eff = min(max(eff_squeeze_parm, 1.0), squeeze + 0.1)
        spec = LensSpec(
            lens_id=lens_id or "parm_driven",
            manufacturer="Custom",
            series="Parm-Driven",
            focal_length_mm=focal,
            t_stop_min=1.0,
            t_stop_max=32.0,
            iris_blades=11,
            close_focus_m=0.01,
            image_circle_mm=46.0,
            squeeze_ratio=squeeze,
            distortion=distortion,
            breathing=BreathingCurve(()),
            squeeze_breathing=SqueezeBreathingCurve(
                points=((1.0, eff),), nominal_squeeze=squeeze,
            ),
        )
        t_stop = min(max(t_stop, spec.t_stop_min), spec.t_stop_max)
        focus = max(focus, spec.close_focus_m)

    lens_state = LensState(spec=spec, t_stop=t_stop, focus_distance_m=focus)
    return camera_state, lens_state, resolved


# ════════════════════════════════════════════════════════════
# COOK-TIME AUTHORING ENTRY POINTS (one per Python Script LOP)
# ════════════════════════════════════════════════════════════

def author_camera_rig(script_node) -> None:
    """Author the Xform hierarchy + camera + cinema:* attrs."""
    hda = script_node.parent()
    stage = script_node.editableStage()
    camera_state, lens_state, _ = resolve_states(hda)
    optics = optics_engine.compute_optics(camera_state, lens_state)

    usd_builder.build_usd_camera_rig(
        stage,
        rig_path_from(hda),
        camera_state,
        lens_state,
        optics,
        body_id=hda.evalParm("body_id") or "",
        entrance_pupil_offset_cm=(hda.evalParm("entrance_pupil_offset_mm") or 0.0) / 10.0,
        combined_weight_kg=hda.evalParm("combined_weight_kg") or None,
    )


def apply_biomechanics(script_node) -> None:
    """
    Damped-spring filter on the input prim's rotateXYZ animation plus
    procedural handheld shake, written as time samples on FluidHead.
    Solver math lives in cinema_camera.biomechanics.
    """
    import hou
    from pxr import Gf, Sdf, Usd, UsdGeom

    hda = script_node.parent()
    if not hda.evalParm("enable_biomechanics"):
        return
    stage = script_node.editableStage()

    head_path = rig_path_from(hda) + "/FluidHead"
    head_prim = stage.GetPrimAtPath(head_path)
    if not head_prim or not head_prim.IsValid():
        return

    # ── Solver parameters (auto-derive or manual parms) ───────
    weight = hda.evalParm("combined_weight_kg")
    if hda.evalParm("auto_derive"):
        derived = auto_derive_from_weight(weight)
        spring_k = derived["spring_constant"]
        damping = derived["damping_ratio"]
        lag_frames = derived["lag_frames"]
        shake_amp = derived["shake_amplitude_deg"]
        shake_freq = derived["shake_frequency_hz"]
    else:
        spring_k = hda.evalParm("spring_constant")
        damping = hda.evalParm("damping_ratio")
        lag_frames = hda.evalParm("lag_frames")
        shake_amp = hda.evalParm("shake_amplitude_deg")
        shake_freq = hda.evalParm("shake_frequency_hz")

    enable_handheld = hda.evalParm("enable_handheld")
    input_path = (hda.evalParm("input_camera_path") or "").strip()

    fstart, fend = hou.playbar.frameRange()
    fstart, fend = int(fstart), int(fend)
    fps = hou.fps() or 24.0
    dt = 1.0 / fps

    # ── Get or create FluidHead's xformOp:rotateXYZ ───────────
    head_xformable = UsdGeom.Xformable(head_prim)
    rotate_op = None
    for op in head_xformable.GetOrderedXformOps():
        if op.GetOpName() == "xformOp:rotateXYZ":
            rotate_op = op
            break
    if rotate_op is None:
        rotate_op = head_xformable.AddRotateXYZOp()

    # ── Read input rotation animation (xformOp:rotateXYZ) ─────
    input_rotations = []
    if input_path:
        input_prim = stage.GetPrimAtPath(input_path)
        if input_prim and input_prim.IsValid():
            input_xf = UsdGeom.Xformable(input_prim)
            src_rot_op = None
            for op in input_xf.GetOrderedXformOps():
                if op.GetOpName() == "xformOp:rotateXYZ":
                    src_rot_op = op
                    break
            if src_rot_op is not None:
                for f in range(fstart, fend + 1):
                    v = src_rot_op.Get(Usd.TimeCode(f))
                    if v is not None:
                        input_rotations.append([float(v[0]), float(v[1]), float(v[2])])
                    else:
                        input_rotations.append([0.0, 0.0, 0.0])

    # ── Filter + shake (math from cinema_camera.biomechanics) ─
    filtered = solve_damped_spring(input_rotations, dt, spring_k, damping, lag_frames)

    shake = None
    if enable_handheld and shake_amp > 0:
        shake = handheld_shake_offsets(
            list(range(fstart, fend + 1)), dt, shake_amp, shake_freq)

    # ── Author USD time samples on FluidHead's rotateXYZ ──────
    n_frames = fend - fstart + 1
    for i, f in enumerate(range(fstart, fend + 1)):
        base = filtered[i] if filtered else [0.0, 0.0, 0.0]
        s = shake[i] if shake else [0.0, 0.0, 0.0]
        total = Gf.Vec3f(base[0] + s[0], base[1] + s[1], base[2] + s[2])
        rotate_op.Set(total, Usd.TimeCode(f))

    # ── Author solver metadata on FluidHead ───────────────────
    def _meta(name, sdf_t, val):
        head_prim.CreateAttribute(name, sdf_t).Set(val)

    _meta("cinema:rig:biomech:enabled",         Sdf.ValueTypeNames.Bool,  True)
    _meta("cinema:rig:biomech:springK",         Sdf.ValueTypeNames.Float, spring_k)
    _meta("cinema:rig:biomech:damping",         Sdf.ValueTypeNames.Float, damping)
    _meta("cinema:rig:biomech:lagFrames",       Sdf.ValueTypeNames.Float, lag_frames)
    _meta("cinema:rig:biomech:handheldEnabled", Sdf.ValueTypeNames.Bool,  bool(enable_handheld))
    _meta("cinema:rig:biomech:handheldAmpDeg",  Sdf.ValueTypeNames.Float, shake_amp)
    _meta("cinema:rig:biomech:handheldFreqHz",  Sdf.ValueTypeNames.Float, shake_freq)
    _meta("cinema:rig:biomech:filteredFrames",  Sdf.ValueTypeNames.Int,   len(filtered))
    _meta("cinema:rig:biomech:totalFrames",     Sdf.ValueTypeNames.Int,   n_frames)


def author_lens_shader(script_node) -> None:
    """Bind the Karma CVEX lens shader (karma:camera:lensshader opdef)."""
    hda = script_node.parent()
    stage = script_node.editableStage()
    camera_state, lens_state, _ = resolve_states(hda)
    bind_lens_shader(
        stage,
        camera_path_from(hda),
        camera_state,
        lens_state,
        entrance_pupil_offset_cm=(hda.evalParm("entrance_pupil_offset_mm") or 0.0) / 10.0,
    )


def author_render_product(script_node) -> None:
    """RenderProduct with Cooke /i + ASWF EXR metadata."""
    hda = script_node.parent()
    if not (hda.evalParm("write_cooke_i") or hda.evalParm("write_aswf_exr")):
        return
    stage = script_node.editableStage()
    camera_state, lens_state, _ = resolve_states(hda)
    usd_builder.configure_render_product(
        stage,
        camera_path_from(hda),
        "cinema_rig_render.exr",
        camera_state,
        lens_state,
    )


def author_render_settings(script_node) -> None:
    """RenderSettings: resolution + camera RELATIONSHIP + products link."""
    hda = script_node.parent()
    stage = script_node.editableStage()
    camera_state, _, _ = resolve_states(hda)
    usd_builder.configure_render_settings(
        stage,
        camera_path_from(hda),
        camera_state,
    )
