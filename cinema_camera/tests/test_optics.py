"""
Cinema Camera Rig — Optics / exposure / per-format ground-truth tests (Tier 0).

Houdini-free. These are the first "validation harness" goldens: they pin the
exposure metering, the geometric-f-number DoF split, the squeeze-aware FOV, and
the per-format active-sensor model against known values, so the metadata-only
exposure bug and the squeeze-blind FOV bug cannot silently regress.
"""

import os
import sys

import pytest

# Ensure the cinema_camera package is importable (mirror test_protocols.py).
_scripts_python = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "python")
)
if _scripts_python not in sys.path:
    sys.path.insert(0, _scripts_python)

from cinema_camera import optics_engine
from cinema_camera.protocols import (
    DEFAULT_TRANSMISSION,
    BreathingCurve,
    CameraState,
    DistortionModel,
    FormatSpec,
    LensSpec,
    LensState,
    SensorSpec,
)


def _spec(focal=50.0, squeeze=1.8, transmission=0.0):
    return LensSpec(
        lens_id="test",
        manufacturer="Test",
        series="Test",
        focal_length_mm=focal,
        t_stop_min=2.3,
        t_stop_max=22.0,
        iris_blades=11,
        close_focus_m=0.8,
        image_circle_mm=46.0,
        squeeze_ratio=squeeze,
        distortion=DistortionModel(),
        breathing=BreathingCurve(()),
        transmission=transmission,
    )


# ── Exposure metering ──────────────────────────────────────

def test_exposure_reference_is_zero():
    # T5.6 / 180deg / 24fps / ISO800 is the anchor -> 0 stops.
    assert optics_engine.compute_exposure_scalar(5.6, 180.0, 24.0, 800) == pytest.approx(0.0)


def test_exposure_two_stops_wider():
    # T2.8 is 2 stops more open than T5.6 -> +2.0.
    assert optics_engine.compute_exposure_scalar(2.8, 180.0, 24.0, 800) == pytest.approx(2.0)


def test_exposure_fps_shortens_time():
    # 48 fps halves the exposure time vs 24 (-1 stop): T2.8 -> +1.0 net.
    assert optics_engine.compute_exposure_scalar(2.8, 180.0, 48.0, 800) == pytest.approx(1.0)


def test_exposure_iso_doubling():
    # ISO 1600 is +1 stop vs 800 at the reference aperture/time.
    assert optics_engine.compute_exposure_scalar(5.6, 180.0, 24.0, 1600) == pytest.approx(1.0)


# ── Geometric f-number vs T-stop ───────────────────────────

def test_f_number_below_t_stop():
    ls = LensState(spec=_spec(), t_stop=2.8, focus_distance_m=3.0)
    assert ls.f_number == pytest.approx(2.8 * (DEFAULT_TRANSMISSION ** 0.5))
    assert ls.f_number < ls.t_stop


def test_f_number_uses_measured_transmission():
    ls = LensState(spec=_spec(transmission=0.95), t_stop=2.8, focus_distance_m=3.0)
    assert ls.f_number == pytest.approx(2.8 * (0.95 ** 0.5))


def test_geometric_f_gives_shallower_dof():
    coc = optics_engine.compute_circle_of_confusion(43.3)
    near_f, far_f = optics_engine.compute_dof(50.0, 2.8 * (0.85 ** 0.5), 3.0, coc)
    near_t, far_t = optics_engine.compute_dof(50.0, 2.8, 3.0, coc)
    # Smaller f-number -> shallower DoF: nearer near-limit pushed out, far pulled in.
    assert (far_f - near_f) < (far_t - near_t)


# ── Squeeze-aware FOV matches the datasheet ────────────────

def test_hfov_matches_anamorphic_datasheet():
    # Cooke Anamorphic/i FF+ 50mm on a 35.9mm-wide FF sensor, 1.8x squeeze:
    # datasheet max horizontal FOV ~= 65.7 deg.
    cam = CameraState(
        model="Test",
        sensor=SensorSpec(width_mm=35.9, height_mm=24.0),
        format=FormatSpec(width_px=8640, height_px=5760),
    )
    ls = LensState(spec=_spec(focal=50.0, squeeze=1.8), t_stop=2.8, focus_distance_m=1e6)
    res = optics_engine.compute_optics(cam, ls)
    assert res.hfov_deg == pytest.approx(65.7, abs=0.3)


def test_spherical_fov_unaffected_by_squeeze():
    cam = CameraState(
        model="Test",
        sensor=SensorSpec(width_mm=35.9, height_mm=24.0),
        format=FormatSpec(width_px=6000, height_px=4000),
    )
    ls = LensState(spec=_spec(focal=50.0, squeeze=1.0), t_stop=2.8, focus_distance_m=1e6)
    res = optics_engine.compute_optics(cam, ls)
    # 2*atan(35.9 / (2*50)) = 39.50 deg
    assert res.hfov_deg == pytest.approx(39.50, abs=0.2)


# ── Per-format active-sensor model ─────────────────────────

def test_active_width_reads_format():
    cam = CameraState(
        model="Test",
        sensor=SensorSpec(width_mm=54.12, height_mm=25.58, pixel_pitch_um=8.25),
        format=FormatSpec(3840, 2160, "4K UHD", 31.68, 17.82),
    )
    assert cam.active_width_mm == pytest.approx(31.68)
    assert cam.active_height_mm == pytest.approx(17.82)


def test_open_gate_falls_back_to_sensor():
    cam = CameraState(
        model="Test",
        sensor=SensorSpec(width_mm=27.99, height_mm=19.22),
        format=FormatSpec(1920, 1080, "HD"),  # no active mm -> open gate
    )
    assert cam.active_width_mm == pytest.approx(27.99)
    assert cam.active_height_mm == pytest.approx(19.22)


def test_photosite_ceiling_rejects_impossible_resolution():
    # 8192x5760 on a 40.96x21.60mm / 5.0um sensor: 5760 rows exceed photosites.
    with pytest.raises(ValueError):
        CameraState(
            model="Bad",
            sensor=SensorSpec(width_mm=40.96, height_mm=21.60, pixel_pitch_um=5.0),
            format=FormatSpec(8192, 5760, "impossible", 40.96, 21.60),
        )


def test_shutter_speed_uses_fps():
    cam = CameraState(
        model="Test",
        sensor=SensorSpec(width_mm=27.99, height_mm=19.22),
        format=FormatSpec(4608, 3164, "OG"),
        shutter_angle_deg=180.0,
        fps=48.0,
    )
    assert cam.shutter_speed_s == pytest.approx((180.0 / 360.0) / 48.0)
