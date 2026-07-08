"""
Verify the Tier 2 pupil reference (polygonal iris, apodization, cat's-eye /
mechanical vignetting). Houdini-free -- the oracle the VEX must mirror.
"""

import math
import os
import sys

import pytest

_scripts_python = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "python")
)
if _scripts_python not in sys.path:
    sys.path.insert(0, _scripts_python)

from cinema_camera.pupil import (
    apodization_mean,
    apodization_weight,
    cats_eye_transmission,
    cats_eye_valid,
    polygon_remap,
)


# ── Polygonal iris ─────────────────────────────────────────

def test_polygon_edge_apothem_and_vertex():
    N = 6
    # edge midpoint (theta=0, sector=0) maps a unit sample to the apothem cos(pi/N)
    rx, ry = polygon_remap(1.0, 0.0, N)
    assert math.hypot(rx, ry) == pytest.approx(math.cos(math.pi / N), abs=1e-9)
    # vertex (theta=pi/N) maps a unit sample to radius 1
    a = math.pi / N
    rx, ry = polygon_remap(math.cos(a), math.sin(a), N)
    assert math.hypot(rx, ry) == pytest.approx(1.0, abs=1e-9)


def test_polygon_nfold_symmetry():
    N = 7
    ba = 2 * math.pi / N
    for base in (0.3, 1.1, 2.0):
        r1 = math.hypot(*polygon_remap(math.cos(base), math.sin(base), N))
        r2 = math.hypot(*polygon_remap(math.cos(base + ba), math.sin(base + ba), N))
        assert r1 == pytest.approx(r2, abs=1e-9)


def test_polygon_curvature_1_is_circle():
    for th in (0.0, 0.5, 1.2, 2.5):
        rx, ry = polygon_remap(math.cos(th), math.sin(th), 6, curvature=1.0)
        assert math.hypot(rx, ry) == pytest.approx(1.0, abs=1e-9)


def test_polygon_high_blade_count_near_circular():
    # 11-blade (Cooke) apothem cos(pi/11) ~= 0.9595 -> within ~4% of the circle,
    # so radial-remap density non-uniformity is negligible at cinema blade counts.
    assert (1.0 - math.cos(math.pi / 11)) < 0.05


# ── Apodization ────────────────────────────────────────────

def test_apodization_energy_neutral():
    for s in (-3.0, -1.0, 0.0, 0.5, 1.5):
        assert apodization_mean(s) == pytest.approx(1.0, abs=2e-3)


def test_apodization_direction():
    # creamy (strength > 0): edge dimmer than center
    assert apodization_weight(0.9, 1.0) < apodization_weight(0.1, 1.0)
    # nervous (strength < 0): edge brighter than center
    assert apodization_weight(0.9, -1.0) > apodization_weight(0.1, -1.0)


def test_apodization_zero_is_flat():
    for r in (0.0, 0.3, 0.7, 1.0):
        assert apodization_weight(r, 0.0) == pytest.approx(1.0, abs=1e-12)


# ── Cat's-eye / mechanical vignetting ──────────────────────

def test_catseye_center_full_transmission():
    t = cats_eye_transmission(0.0, 0.0, 2.0, 50.0, rv_rel=0.5, k_rel=0.2, image_circle=10.0)
    assert t == pytest.approx(1.0, abs=0.02)


def test_catseye_vignettes_off_axis():
    t = cats_eye_transmission(0.9, 0.0, 2.0, 50.0, rv_rel=0.28, k_rel=0.25, image_circle=10.0)
    assert t < 0.95


def test_catseye_stop_down_recovery():
    field = (0.8, 0.0)
    t_wide = cats_eye_transmission(*field, 2.0, 50.0, 0.28, 0.25, 10.0)
    t_stop = cats_eye_transmission(*field, 8.0, 50.0, 0.28, 0.25, 10.0)
    assert t_stop > t_wide + 0.05          # stopping down recovers the corner


def test_catseye_image_circle_cutoff():
    # field radius 1.0 outside an image circle of 0.8 -> rejected regardless of pupil
    assert not cats_eye_valid(0.0, 0.0, 1.0, 0.0, 2.0, 50.0, 0.5, 0.2, image_circle=0.8)
    assert cats_eye_valid(0.0, 0.0, 0.5, 0.0, 2.0, 50.0, 0.5, 0.2, image_circle=0.8)
