"""
Cinema Camera Rig -- pupil / bokeh reference (Tier 2).

Reference / validation implementation of the lens-shader pupil operations. The
RENDER path is the VEX in vex/include/libcinema_optics.h (co_pupil_* / the
karma_cinema_lens.vfl pupil block), which mirrors this math; this module exists
to verify it headless (tests/test_pupil.py).

Empirically grounded (Houdini 21.0.765, scratchpad/probe_pupil.py): Karma hands
the CVEX lens shader a UNIFORM sample on the NORMALIZED unit disc (|dof| <= 1),
f-stop-INDEPENDENT. So f-stop-dependent effects (mechanical-vignette stop-down
recovery) must scale the sample into PHYSICAL pupil units in the shader:
    R_ap = focal / (2 * fstop)         # entrance-pupil radius, shrinks with f
    physical_sample = (dofx, dofy) * R_ap
"""

from __future__ import annotations

import math


# ── Polygonal iris (blade shape) ───────────────────────────

def polygon_remap(dx: float, dy: float, blades: int,
                  rotation_deg: float = 0.0, curvature: float = 0.0) -> tuple[float, float]:
    """
    Reshape a UNIT-DISC sample (dx,dy) into an N-gon iris by radial scaling.
    R_poly(theta) = cos(pi/N)/cos(sector): vertices at radius 1, edges (apothem)
    at cos(pi/N), inscribed in the unit disc. curvature in [0,1] bows the edges
    toward the circle (1 = round). Density is mildly non-uniform (~1/R_poly^2);
    negligible for cinema blade counts (>=9) which are near-circular.
    """
    if blades < 3:
        return dx, dy
    theta = math.atan2(dy, dx) + math.radians(rotation_deg)
    ba = 2.0 * math.pi / blades
    sector = theta - ba * round(theta / ba)          # fold to [-ba/2, ba/2]
    r_poly = math.cos(math.pi / blades) / math.cos(sector)
    r_poly = (1.0 - curvature) * r_poly + curvature   # blend toward the unit circle
    return dx * r_poly, dy * r_poly


# ── Spherical-aberration apodization (bokeh intensity profile) ──

def apodization_weight(r: float, strength: float) -> float:
    """
    Radial pupil weight w(r), r = |sample|/aperture_radius in [0,1], normalized
    so the mean over the UNIFORM disc is 1 (integral of w(r)*2r dr, 0..1, == 1).
    That keeps IN-FOCUS points exposure-neutral (their pupil samples average to
    mean=1) while shaping OUT-OF-FOCUS discs.
        strength > 0 -> creamy (edges dimmer, Cooke roll-off)
        strength < 0 -> nervous / soap-bubble (rim-boosted)
    w(r) = (1 - a r^2) / (1 - a/2), a = strength (clamped so w stays positive).
    """
    a = max(-4.0, min(1.9, strength))
    denom = 1.0 - a * 0.5
    return (1.0 - a * r * r) / denom


def apodization_mean(strength: float, n: int = 20000) -> float:
    """Numerical mean of w over the uniform disc (should be ~1 for any strength)."""
    total = 0.0
    for i in range(n):
        r = math.sqrt((i + 0.5) / n)                 # uniform-area radial samples
        total += apodization_weight(r, strength)
    return total / n


# ── Cat's-eye / mechanical vignetting (field-dependent pupil clip) ──

def cats_eye_valid(dx: float, dy: float, x: float, y: float,
                   fstop: float, focal: float,
                   rv_rel: float, k_rel: float, image_circle: float) -> bool:
    """
    True if the unit-disc pupil sample (dx,dy) survives the mechanical-vignette
    clip at field (x,y). The effective off-axis pupil is the intersection of the
    aperture-stop disc with a field-offset occlusion disc (fixed in PHYSICAL
    pupil units) -> cat's-eye shape + darkening (rejected samples average toward
    black) + automatic stop-down recovery (R_ap shrinks with f while the
    occlusion is fixed). Reject (return False), never renormalize.

    rv_rel, k_rel are the occlusion radius and offset-per-field as fractions of
    the focal length. image_circle is a hard field-radius cutoff (NDC).
    """
    rho = math.hypot(x, y)
    if rho > image_circle:
        return False                                  # outside image circle
    r_ap = focal / (2.0 * fstop) if fstop > 0 else focal * 0.5
    px, py = dx * r_ap, dy * r_ap                     # physical pupil sample
    # occlusion center = -k*focal*(x,y): the minus puts the clipped/flat side on
    # the OUTER (corner) side -> physically-correct cat's-eye orientation.
    cx, cy = -k_rel * focal * x, -k_rel * focal * y
    rv = rv_rel * focal
    return math.hypot(px - cx, py - cy) <= rv


def cats_eye_transmission(x: float, y: float, fstop: float, focal: float,
                          rv_rel: float, k_rel: float, image_circle: float,
                          n: int = 4000) -> float:
    """Fraction of uniform-disc samples that survive at field (x,y) = the
    mechanical-vignetting transmission (Monte-Carlo-free low-discrepancy grid)."""
    valid = 0
    total = 0
    m = int(math.sqrt(n))
    for i in range(m):
        for j in range(m):
            dx = 2.0 * (i + 0.5) / m - 1.0
            dy = 2.0 * (j + 0.5) / m - 1.0
            if dx * dx + dy * dy > 1.0:
                continue                              # only the unit disc
            total += 1
            if cats_eye_valid(dx, dy, x, y, fstop, focal, rv_rel, k_rel, image_circle):
                valid += 1
    return valid / total if total else 0.0
