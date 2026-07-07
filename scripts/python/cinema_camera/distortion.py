"""
Cinema Camera Rig -- dn-normalized 3DE Radial-Standard distortion (reference).

This is the REFERENCE / VALIDATION implementation of the lens-distortion model.
The RENDER path is the VEX in vex/include/libcinema_optics.h, which mirrors this
math exactly; this module exists to (a) verify the model headlessly (round-trip
+ analytic-Jacobian correctness, see tests/test_distortion.py), and (b) bake
ground-truth ST-maps offline. It is NOT used at COP cook time -- the Copernicus
ST-map generator must call the shared VEX so render and bake are byte-identical
(roadmap: stmap-roundtrip).

Model: 3DE4 "Radial - Standard, Degree 4" (Science-D-Visions LDPK), in
diagonally-normalized (dn) coordinates -- origin at the lens center, radius = 1
at the frame CORNER (unit = half the aspect-corrected image diagonal). This is
the convention 3DEqualizer / Nuke / SynthEyes use, so coefficients are portable.

Direction convention: g maps DISTORTED -> UNDISTORTED (the LDPK default). A lens
shader is handed the distorted raster sample and wants the ideal rectilinear
ray, so it applies g directly. The inverse gi (UNDISTORTED -> DISTORTED) has no
closed form and is solved by Newton iteration with the analytic Jacobian below;
it is what the ST-map "redistort" layer needs.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class DistortionCoeffs:
    """
    3DE Radial-Standard Deg-4 (+ optional Deg-6 radial c6) in dn coordinates.

    Radial:      c2 (deg-2), c4 (deg-4), c6 (deg-6, 0 for pure Deg-4).
    Decentering: u2, v2 (deg-2), u4, v4 (deg-4) -- linearized Brown tangential.
    Center:      cx, cy -- lens-center offset in dn units (usually ~0).

    Brown-Conrady bridge (so existing k1,k2,k3/p1,p2 data maps in):
      c2 = k1, c4 = k2, c6 = k3; u2 = p2, v2 = p1; u4 = v4 = 0.
    """
    c2: float = 0.0
    c4: float = 0.0
    c6: float = 0.0
    u2: float = 0.0
    v2: float = 0.0
    u4: float = 0.0
    v4: float = 0.0
    cx: float = 0.0
    cy: float = 0.0

    @classmethod
    def from_brown_conrady(cls, k1=0.0, k2=0.0, k3=0.0, p1=0.0, p2=0.0) -> "DistortionCoeffs":
        """Adopt existing Brown-Conrady coefficients as dn 3DE coefficients."""
        return cls(c2=k1, c4=k2, c6=k3, u2=p2, v2=p1)


def dn_norm(width_fb: float, height_fb: float) -> float:
    """Half the (aspect-corrected) image diagonal: the dn unit. r=1 at corner."""
    return 0.5 * math.sqrt(width_fb * width_fb + height_fb * height_fb)


def g(x: float, y: float, c: DistortionCoeffs) -> tuple[float, float]:
    """
    Distorted -> undistorted (LDPK g), evaluated at the distorted dn point.
    At zero coefficients this is the identity; g(center) = center.
    """
    x -= c.cx
    y -= c.cy
    s = x * x + y * y
    radial = 1.0 + c.c2 * s + c.c4 * s * s + c.c6 * s * s * s
    a = c.u2 + c.u4 * s          # x-decentering amplitude
    b = c.v2 + c.v4 * s          # y-decentering amplitude
    gx = x * radial + (s + 2.0 * x * x) * a + 2.0 * x * y * b
    gy = y * radial + (s + 2.0 * y * y) * b + 2.0 * x * y * a
    return gx + c.cx, gy + c.cy


def jacobian(x: float, y: float, c: DistortionCoeffs) -> tuple[float, float, float, float]:
    """
    Analytic Jacobian of g at the distorted dn point, returned as
    (dgx_dx, dgx_dy, dgy_dx, dgy_dy). Used by the Newton inverse.
    """
    x -= c.cx
    y -= c.cy
    s = x * x + y * y
    radial = 1.0 + c.c2 * s + c.c4 * s * s + c.c6 * s * s * s
    dradial = c.c2 + 2.0 * c.c4 * s + 3.0 * c.c6 * s * s     # d(radial)/ds
    a = c.u2 + c.u4 * s
    b = c.v2 + c.v4 * s

    # d(gx)/dx, d(gx)/dy  with gx = x*radial + (s+2x^2)*a + 2xy*b
    dgx_dx = (radial + 2.0 * x * x * dradial
              + 6.0 * x * a + 2.0 * x * c.u4 * (s + 2.0 * x * x)
              + 2.0 * y * b + 4.0 * x * x * y * c.v4)
    dgx_dy = (2.0 * x * y * dradial
              + 2.0 * y * a + 2.0 * y * c.u4 * (s + 2.0 * x * x)
              + 2.0 * x * b + 4.0 * x * y * y * c.v4)

    # d(gy)/dx, d(gy)/dy  with gy = y*radial + (s+2y^2)*b + 2xy*a
    dgy_dy = (radial + 2.0 * y * y * dradial
              + 6.0 * y * b + 2.0 * y * c.v4 * (s + 2.0 * y * y)
              + 2.0 * x * a + 4.0 * x * y * y * c.u4)
    dgy_dx = (2.0 * x * y * dradial
              + 2.0 * x * b + 2.0 * x * c.v4 * (s + 2.0 * y * y)
              + 2.0 * y * a + 4.0 * x * x * y * c.u4)
    return dgx_dx, dgx_dy, dgy_dx, dgy_dy


def g_inverse(qx: float, qy: float, c: DistortionCoeffs,
              iters: int = 12, tol: float = 1e-10) -> tuple[float, float]:
    """
    Undistorted -> distorted: solve g(p) = q for p by Newton iteration with the
    analytic Jacobian. Quadratic, edge-robust convergence. Seed p = q.
    """
    x, y = qx, qy
    for _ in range(iters):
        gx, gy = g(x, y, c)
        ex, ey = gx - qx, gy - qy
        if ex * ex + ey * ey < tol * tol:
            break
        j00, j01, j10, j11 = jacobian(x, y, c)
        det = j00 * j11 - j01 * j10
        if abs(det) < 1e-12:
            break
        # p <- p - J^-1 * e
        x -= (j11 * ex - j01 * ey) / det
        y -= (-j10 * ex + j00 * ey) / det
    return x, y


# ════════════════════════════════════════════════════════════
# ANAMORPHIC: 3DE "Anamorphic - Standard, Degree 4"
# ════════════════════════════════════════════════════════════
#
# A cylindrical front group distorts the two axes differently, so no isotropic
# radial polynomial can reproduce it. The 3DE Anamorphic-Standard model is a
# per-axis even polynomial in polar dn coords with cos2phi / cos4phi angular
# terms (10 distortion coeffs at degree 4). Expanded to Cartesian (no trig),
# with s = r^2, d = r^2*cos2phi = x^2 - y^2, and r^4*cos4phi = 2*d^2 - s^2:
#
#   gx = x * (1 + cx02*s + cx22*d + cx04*s^2 + cx24*s*d + cx44*(2*d^2 - s^2))
#   gy = y * (1 + cy02*s + cy22*d + cy04*s^2 + cy24*s*d + cy44*(2*d^2 - s^2))
#
# The ~2x anamorphic SQUEEZE is a SEPARATE filmback rescale (rpa) applied
# OUTSIDE this polynomial (in the lens shader's projection), NOT folded in --
# that is the fix over the old radial+X-stretch. When cx22=cy22=cx24=cy24=
# cx44=cy44=0 and cx0k==cy0k, this reduces exactly to the spherical radial g.


@dataclass(frozen=True)
class AnamorphicCoeffs:
    """3DE Anamorphic-Standard Deg-4 (10 coeffs) in dn coords + lens center."""
    cx02: float = 0.0
    cx22: float = 0.0
    cx04: float = 0.0
    cx24: float = 0.0
    cx44: float = 0.0
    cy02: float = 0.0
    cy22: float = 0.0
    cy04: float = 0.0
    cy24: float = 0.0
    cy44: float = 0.0
    cx: float = 0.0
    cy: float = 0.0

    @classmethod
    def from_radial(cls, c2=0.0, c4=0.0) -> "AnamorphicCoeffs":
        """Isotropic radial as an anamorphic coeff set (cos2phi terms 0)."""
        return cls(cx02=c2, cy02=c2, cx04=c4, cy04=c4)


def g_anamorphic(x: float, y: float, c: AnamorphicCoeffs) -> tuple[float, float]:
    """Distorted -> undistorted (per-axis cos2phi/cos4phi), at a dn point."""
    x -= c.cx
    y -= c.cy
    s = x * x + y * y
    d = x * x - y * y
    c4 = 2.0 * d * d - s * s
    rx = 1.0 + c.cx02 * s + c.cx22 * d + c.cx04 * s * s + c.cx24 * s * d + c.cx44 * c4
    ry = 1.0 + c.cy02 * s + c.cy22 * d + c.cy04 * s * s + c.cy24 * s * d + c.cy44 * c4
    return x * rx + c.cx, y * ry + c.cy


def jacobian_anamorphic(x: float, y: float, c: AnamorphicCoeffs):
    """Analytic Jacobian (dgx_dx, dgx_dy, dgy_dx, dgy_dy) of g_anamorphic."""
    x -= c.cx
    y -= c.cy
    s = x * x + y * y
    d = x * x - y * y
    c4 = 2.0 * d * d - s * s
    rx = 1.0 + c.cx02 * s + c.cx22 * d + c.cx04 * s * s + c.cx24 * s * d + c.cx44 * c4
    ry = 1.0 + c.cy02 * s + c.cy22 * d + c.cy04 * s * s + c.cy24 * s * d + c.cy44 * c4
    # d(rx)/dx = 2x[cx02 + cx22 + 2s*cx04 + cx24(d+s) + 2cx44(2d-s)]
    drx_dx = 2.0 * x * (c.cx02 + c.cx22 + 2.0 * s * c.cx04 + c.cx24 * (d + s) + 2.0 * c.cx44 * (2.0 * d - s))
    drx_dy = 2.0 * y * (c.cx02 - c.cx22 + 2.0 * s * c.cx04 + c.cx24 * (d - s) - 2.0 * c.cx44 * (2.0 * d + s))
    dry_dx = 2.0 * x * (c.cy02 + c.cy22 + 2.0 * s * c.cy04 + c.cy24 * (d + s) + 2.0 * c.cy44 * (2.0 * d - s))
    dry_dy = 2.0 * y * (c.cy02 - c.cy22 + 2.0 * s * c.cy04 + c.cy24 * (d - s) - 2.0 * c.cy44 * (2.0 * d + s))
    return (rx + x * drx_dx, x * drx_dy, y * dry_dx, ry + y * dry_dy)


def g_anamorphic_inverse(qx: float, qy: float, c: AnamorphicCoeffs,
                         iters: int = 14, tol: float = 1e-10) -> tuple[float, float]:
    """Undistorted -> distorted: Newton with the anamorphic analytic Jacobian."""
    x, y = qx, qy
    for _ in range(iters):
        gx, gy = g_anamorphic(x, y, c)
        ex, ey = gx - qx, gy - qy
        if ex * ex + ey * ey < tol * tol:
            break
        j00, j01, j10, j11 = jacobian_anamorphic(x, y, c)
        det = j00 * j11 - j01 * j10
        if abs(det) < 1e-12:
            break
        x -= (j11 * ex - j01 * ey) / det
        y -= (-j10 * ex + j00 * ey) / det
    return x, y
