"""
Cinema Camera Rig v4.0 — Optics Engine

Pure-math optical calculations: FOV, DOF, hyperfocal distance.
No Houdini dependency -- usable standalone for validation.
"""

from __future__ import annotations

import math

from .protocols import CameraState, LensState, OpticalResult


# Reference exposure anchor: a "normal" cinema setup renders exposure == 0,
# so the log2 scalar reads as relative stops (T5.6 / 180deg / 24fps / ISO800).
_EXPOSURE_REF_T = 5.6
_EXPOSURE_REF_ANGLE_DEG = 180.0
_EXPOSURE_REF_FPS = 24.0
_EXPOSURE_REF_ISO = 800


def compute_exposure_scalar(
    t_stop: float,
    shutter_angle_deg: float,
    fps: float,
    exposure_index: int,
) -> float:
    """
    Scalar log2 value for UsdGeomCamera.exposure -- the one exposure control
    Karma honors on both CPU and XPU.

    Uses the T-stop (transmission-corrected) because this is the EXPOSURE
    aperture; the geometric f-number is for depth of field only. Photometric
    exposure H = t_shutter * (ISO/100) / T^2, with t_shutter = (angle/360)/fps.
    Returned value is log2(H / H_ref), anchored so the reference setup = 0.
    """
    def _h(t: float, angle: float, f: float, iso: float) -> float:
        if t <= 0 or f <= 0:
            return 0.0
        t_shutter = (angle / 360.0) / f
        return t_shutter * (iso / 100.0) / (t * t)

    h = _h(t_stop, shutter_angle_deg, fps, exposure_index)
    h_ref = _h(_EXPOSURE_REF_T, _EXPOSURE_REF_ANGLE_DEG,
               _EXPOSURE_REF_FPS, _EXPOSURE_REF_ISO)
    if h <= 0 or h_ref <= 0:
        return 0.0
    return math.log2(h / h_ref)


def compute_circle_of_confusion(sensor_diagonal_mm: float) -> float:
    """
    Standard circle of confusion for acceptable sharpness.
    Industry standard: sensor diagonal / 1500.
    """
    return sensor_diagonal_mm / 1500.0


def compute_fov(
    focal_length_mm: float,
    aperture_mm: float,
    breathing_shift_pct: float = 0.0,
) -> float:
    """
    Field of view in degrees for a given focal length and aperture dimension.
    Accounts for breathing shift (FOV change with focus distance).
    """
    if focal_length_mm <= 0 or aperture_mm <= 0:
        return 0.0
    base_fov = 2.0 * math.degrees(math.atan(aperture_mm / (2.0 * focal_length_mm)))
    # Apply breathing: positive shift = wider FOV
    return base_fov * (1.0 + breathing_shift_pct / 100.0)


def compute_hyperfocal(
    focal_length_mm: float,
    f_number: float,
    coc_mm: float,
) -> float:
    """
    Hyperfocal distance in meters.
    H = f^2 / (N * c) + f
    where f = focal length, N = f-number, c = circle of confusion.
    """
    if f_number <= 0 or coc_mm <= 0:
        return float('inf')
    h_mm = (focal_length_mm ** 2) / (f_number * coc_mm) + focal_length_mm
    return h_mm / 1000.0  # mm -> m


def compute_dof(
    focal_length_mm: float,
    f_number: float,
    focus_distance_m: float,
    coc_mm: float,
) -> tuple[float, float]:
    """
    Depth of field near and far limits in meters.

    Returns (dof_near_m, dof_far_m).
    dof_far_m = float('inf') when focus is at or beyond hyperfocal.
    """
    if focus_distance_m <= 0:
        return (0.0, 0.0)

    hyperfocal_m = compute_hyperfocal(focal_length_mm, f_number, coc_mm)
    focus_mm = focus_distance_m * 1000.0
    focal_mm = focal_length_mm

    # Near limit
    denom_near = hyperfocal_m * 1000.0 + focus_mm - 2.0 * focal_mm
    if denom_near <= 0:
        dof_near_m = 0.0
    else:
        dof_near_m = (focus_mm * (hyperfocal_m * 1000.0 - focal_mm)) / denom_near / 1000.0

    # Far limit
    denom_far = hyperfocal_m * 1000.0 - focus_mm
    if denom_far <= 0:
        dof_far_m = float('inf')
    else:
        dof_far_m = (focus_mm * (hyperfocal_m * 1000.0 - focal_mm)) / denom_far / 1000.0

    return (max(0.0, dof_near_m), dof_far_m)


def compute_optics(
    camera_state: CameraState,
    lens_state: LensState,
) -> OpticalResult:
    """
    Compute all optical parameters for a given camera+lens state.

    This is the main entry point used by the USD builder and HDA callbacks.
    """
    coc_mm = compute_circle_of_confusion(camera_state.sensor.diagonal_mm)

    breathing = lens_state.breathing_shift_pct

    # Horizontal FOV widens by the nominal anamorphic squeeze (a 2x front
    # anamorphic captures ~2x the horizontal angle); vertical stays spherical.
    # Spherical lenses (squeeze_ratio 1.0) are unaffected.
    squeeze = lens_state.spec.squeeze_ratio
    hfov = compute_fov(
        lens_state.spec.focal_length_mm,
        camera_state.active_width_mm * squeeze,
        breathing,
    )
    vfov = compute_fov(
        lens_state.spec.focal_length_mm,
        camera_state.active_height_mm,
        breathing,
    )

    # Depth of field is geometric: driven by the f-number, not the T-stop.
    hyperfocal = compute_hyperfocal(
        lens_state.spec.focal_length_mm,
        lens_state.f_number,
        coc_mm,
    )

    dof_near, dof_far = compute_dof(
        lens_state.spec.focal_length_mm,
        lens_state.f_number,
        lens_state.focus_distance_m,
        coc_mm,
    )

    return OpticalResult(
        hfov_deg=hfov,
        vfov_deg=vfov,
        dof_near_m=dof_near,
        dof_far_m=dof_far,
        hyperfocal_m=hyperfocal,
        coc_mm=coc_mm,
    )
