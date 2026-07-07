"""
Verify the dn-normalized 3DE Radial-Standard distortion reference (Tier 1).

Houdini-free. These pins are the oracle the VEX (libcinema_optics.h) must
mirror: they prove the model is invertible (g / g_inverse round-trip to
sub-pixel), that the analytic Jacobian matches finite differences (so the
Newton step is correct), and the identity/center/direction invariants.
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

from cinema_camera.distortion import (
    AnamorphicCoeffs,
    DistortionCoeffs,
    dn_norm,
    g,
    g_anamorphic,
    g_anamorphic_inverse,
    g_inverse,
    jacobian,
    jacobian_anamorphic,
)


# A realistic-ish anamorphic-ish coefficient set with decentering + deg-6.
COEFFS = DistortionCoeffs(c2=-0.08, c4=0.015, c6=-0.002, u2=0.004, v2=-0.003,
                          u4=0.001, v4=0.0006, cx=0.01, cy=-0.008)

# Sample grid across the dn frame incl. corners (r up to ~1).
GRID = [(x / 4.0, y / 4.0) for x in range(-4, 5) for y in range(-4, 5)]


def test_identity_at_zero_coeffs():
    zero = DistortionCoeffs()
    for x, y in GRID:
        gx, gy = g(x, y, zero)
        assert gx == pytest.approx(x, abs=1e-12)
        assert gy == pytest.approx(y, abs=1e-12)


def test_center_is_fixed_point():
    # g(lens center) == lens center for any coefficients.
    gx, gy = g(COEFFS.cx, COEFFS.cy, COEFFS)
    assert gx == pytest.approx(COEFFS.cx, abs=1e-12)
    assert gy == pytest.approx(COEFFS.cy, abs=1e-12)


def test_analytic_jacobian_matches_finite_difference():
    h = 1e-6
    for x, y in GRID:
        j00, j01, j10, j11 = jacobian(x, y, COEFFS)
        gx_px, gy_px = g(x + h, y, COEFFS)
        gx_mx, gy_mx = g(x - h, y, COEFFS)
        gx_py, gy_py = g(x, y + h, COEFFS)
        gx_my, gy_my = g(x, y - h, COEFFS)
        n00 = (gx_px - gx_mx) / (2 * h)   # dgx/dx
        n10 = (gy_px - gy_mx) / (2 * h)   # dgy/dx
        n01 = (gx_py - gx_my) / (2 * h)   # dgx/dy
        n11 = (gy_py - gy_my) / (2 * h)   # dgy/dy
        assert j00 == pytest.approx(n00, abs=2e-4)
        assert j01 == pytest.approx(n01, abs=2e-4)
        assert j10 == pytest.approx(n10, abs=2e-4)
        assert j11 == pytest.approx(n11, abs=2e-4)


def test_roundtrip_g_then_inverse_is_identity():
    # g_inverse(g(p)) == p to well under a pixel. On a 4608-wide frame the dn
    # unit is ~half-diagonal, so 1e-7 dn is ~4e-4 px -- comfortably sub-pixel.
    for x, y in GRID:
        qx, qy = g(x, y, COEFFS)
        px, py = g_inverse(qx, qy, COEFFS)
        assert px == pytest.approx(x, abs=1e-7)
        assert py == pytest.approx(y, abs=1e-7)


def test_roundtrip_inverse_then_g_is_identity():
    for x, y in GRID:
        dx, dy = g_inverse(x, y, COEFFS)   # undistort target -> distorted
        rx, ry = g(dx, dy, COEFFS)         # back to undistorted
        assert rx == pytest.approx(x, abs=1e-7)
        assert ry == pytest.approx(y, abs=1e-7)


def test_barrel_pincushion_direction():
    # Negative c2 (barrel) pulls a corner point inward under g (distorted->
    # undistorted maps the barrel-stretched edge back toward center-relative).
    barrel = DistortionCoeffs(c2=-0.1)
    gx, gy = g(0.7, 0.0, barrel)
    assert gx < 0.7                       # radial magnitude reduced
    pincushion = DistortionCoeffs(c2=0.1)
    px, py = g(0.7, 0.0, pincushion)
    assert px > 0.7


def test_dn_norm_unit_is_half_diagonal():
    # 4.6K Open Gate filmback 27.99 x 19.22 mm -> half-diagonal.
    r = dn_norm(27.99, 19.22)
    assert r == pytest.approx(0.5 * math.hypot(27.99, 19.22), abs=1e-9)


def test_brown_conrady_bridge_maps_fields():
    c = DistortionCoeffs.from_brown_conrady(k1=-0.02, k2=0.003, k3=1e-4, p1=0.001, p2=-0.002)
    assert (c.c2, c.c4, c.c6) == (-0.02, 0.003, 1e-4)
    assert (c.u2, c.v2) == (-0.002, 0.001)   # u2<-p2, v2<-p1


# ── Anamorphic 3DE model ───────────────────────────────────

ACOEFFS = AnamorphicCoeffs(cx02=-0.06, cx22=0.02, cx04=0.01, cx24=-0.004, cx44=0.002,
                           cy02=-0.09, cy22=-0.015, cy04=0.008, cy24=0.003, cy44=-0.001,
                           cx=0.012, cy=-0.007)


def test_anamorphic_identity_at_zero():
    z = AnamorphicCoeffs()
    for x, y in GRID:
        gx, gy = g_anamorphic(x, y, z)
        assert (gx, gy) == pytest.approx((x, y), abs=1e-12)


def test_anamorphic_reduces_to_radial():
    # cos2phi terms zero + cx0k==cy0k -> exactly the isotropic radial g (u2=v2=0).
    an = AnamorphicCoeffs.from_radial(c2=-0.05, c4=0.012)
    rad = DistortionCoeffs(c2=-0.05, c4=0.012)   # c6=0, no decentering
    for x, y in GRID:
        assert g_anamorphic(x, y, an) == pytest.approx(g(x, y, rad), abs=1e-12)


def test_anamorphic_is_non_radial():
    # Different per-axis coeffs give the two axes different radial factors:
    # gx/x != gy/y. A radial model (gx=x*R, gy=y*R, same R) forces them equal,
    # so this is exactly what a cylindrical anamorphic can do and radial cannot.
    c = AnamorphicCoeffs(cx02=-0.10, cy02=-0.04)
    x, y = 0.5, 0.4
    gx, gy = g_anamorphic(x, y, c)
    assert abs(gx / x - gy / y) > 1e-3


def test_anamorphic_analytic_jacobian_matches_fd():
    h = 1e-6
    for x, y in GRID:
        j00, j01, j10, j11 = jacobian_anamorphic(x, y, ACOEFFS)
        gpx = g_anamorphic(x + h, y, ACOEFFS); gmx = g_anamorphic(x - h, y, ACOEFFS)
        gpy = g_anamorphic(x, y + h, ACOEFFS); gmy = g_anamorphic(x, y - h, ACOEFFS)
        assert j00 == pytest.approx((gpx[0] - gmx[0]) / (2 * h), abs=2e-4)
        assert j10 == pytest.approx((gpx[1] - gmx[1]) / (2 * h), abs=2e-4)
        assert j01 == pytest.approx((gpy[0] - gmy[0]) / (2 * h), abs=2e-4)
        assert j11 == pytest.approx((gpy[1] - gmy[1]) / (2 * h), abs=2e-4)


def test_anamorphic_roundtrip():
    for x, y in GRID:
        qx, qy = g_anamorphic(x, y, ACOEFFS)
        px, py = g_anamorphic_inverse(qx, qy, ACOEFFS)
        assert (px, py) == pytest.approx((x, y), abs=1e-7)
