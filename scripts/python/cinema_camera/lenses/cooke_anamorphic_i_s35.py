"""
Cooke Anamorphic/i S35 -- PDF-authoritative lens dataset (10 primes).

Source PDF: COOKE_Anamorphic-i-S35_Specification_030623.pdf
            https://cookeoptics.com -- Anamorphic/i S35 datasheet, version 030623.

This module is the SINGLE SOURCE OF TRUTH for the 10-lens lineup. The JSON files
under cinema_camera/lenses/cooke_ana_i_s35_*.json are derived artifacts emitted
by _emit_lens_jsons.py from this dataset.

PROVENANCE
----------
PDF-authoritative (do not edit without a newer datasheet):
  focal_length_mm, t_stop_range, close_focus_m, image_circle_mm, squeeze_ratio,
  mechanics.weight_kg, mechanics.length_mm, mechanics.front_diameter_mm,
  mechanics.filter_thread, mechanics.focus_ring (teeth, module, rotation),
  mechanics.iris_ring (teeth, module, rotation).

Heuristic (Cooke does not publish; replace via Wolfram fits when W2-W5 are healed):
  iris_blades                          -- industry standard for cine primes
  mechanics.entrance_pupil_offset_mm   -- length_mm * 0.5 (lens optical center)
  squeeze_breathing curve              -- focal-scaled mumps deficit at MOD
  breathing curve                      -- focal-scaled FOV shift at MOD
  distortion (k1, k2, squeeze_uniformity) -- focal-scaled mild barrel
"""

from __future__ import annotations

import math


COOKE_ANA_I_S35_PDF_VERSION = "030623"
COOKE_ANA_I_S35_PDF_FILE = "COOKE_Anamorphic-i-S35_Specification_030623.pdf"


# ── PDF-authoritative shared specifications ───────────────────────────────
_SHARED = {
    "manufacturer":              "Cooke",
    "series":                    "Anamorphic/i S35",
    "squeeze_ratio":             2.0,
    "image_circle_mm":           31.1,
    "iris_blades":               11,                # heuristic: industry standard
    "mount":                     "PL or LPL",
    "focus_drive_gear_teeth":    140,
    "focus_drive_gear_module":   0.8,
    "iris_drive_gear_teeth":     134,
    "iris_drive_gear_module":    0.8,
    "focus_rotation_deg":        300.0,
    "iris_rotation_deg":         90.0,
}


# ── PDF-authoritative per-prime table (transcribed from datasheet pages 1-2) ──
# Columns: focal_mm, t_min, t_max, mod_mm, length_mm, front_dia_mm, weight_kg,
#          filter_thread, hfov_deg, vfov_deg, lens_id_focal_label
_PRIMES = (
    (25.0,  2.3, 22.0, 1000.0, 204.0, 136.0, 4.2, "M131x0.75", 96.9, 41.0,  "25mm"),
    (32.0,  2.3, 22.0,  850.0, 198.0, 110.0, 3.2, "none",      77.5, 32.6,  "32mm"),
    (40.0,  2.3, 22.0,  850.0, 205.0, 110.0, 3.4, "M105x0.75", 62.8, 26.3,  "40mm"),
    (50.0,  2.3, 22.0,  850.0, 205.0, 110.0, 3.6, "M105x0.75", 50.7, 21.2,  "50mm"),
    (65.0,  2.6, 22.0,  440.0, 266.0, 136.0, 5.2, "M131x0.75", 36.9, 15.6,  "65mm_macro"),
    (75.0,  2.3, 22.0, 1000.0, 205.0, 110.0, 3.2, "M105x0.75", 34.1, 14.1,  "75mm"),
    (100.0, 2.3, 22.0, 1200.0, 205.0, 110.0, 3.4, "M105x0.75", 25.7, 10.7,  "100mm"),
    (135.0, 2.3, 22.0, 1400.0, 240.0, 110.0, 4.2, "M105x0.75", 19.1,  7.9,  "135mm"),
    (180.0, 2.8, 22.0, 2000.0, 302.0, 110.0, 5.8, "M105x0.75", 13.9,  5.7,  "180mm"),
    (300.0, 3.5, 22.0, 3000.0, 381.0, 136.0, 9.4, "M131x0.75",  8.5,  3.5,  "300mm"),
)


# ── Heuristic models (clearly named, easy to swap for Wolfram fits) ───────

def _heuristic_pupil_offset_mm(length_mm: float) -> float:
    """Lens optical center approximation. Replace via Wolfram W4."""
    return round(length_mm * 0.5, 1)


def _heuristic_squeeze_breathing(focal_mm: float, mod_m: float) -> list[dict]:
    """
    Anamorphic mumps: front-anamorphic primes lose squeeze toward MOD.
    Shorter focal length = larger deficit. deficit(focal) = 0.15 * sqrt(50/focal),
    clamped to [0.05, 0.20]. Five sample points spanning MOD -> infinity.
    Replace via Wolfram W2-W3 when asyncio bug is fixed.
    """
    deficit = 0.15 * math.sqrt(50.0 / focal_mm)
    deficit = max(0.05, min(0.20, deficit))
    sq_at_mod   = round(2.0 - deficit,        3)
    sq_at_close = round(2.0 - deficit * 0.40, 3)
    sq_at_mid   = round(2.0 - deficit * 0.15, 3)
    sq_at_far   = round(2.0 - deficit * 0.05, 3)
    return [
        {"focus_m": mod_m,                      "effective_squeeze": sq_at_mod},
        {"focus_m": round(mod_m * 1.8,  2),     "effective_squeeze": sq_at_close},
        {"focus_m": round(mod_m * 4.0,  2),     "effective_squeeze": sq_at_mid},
        {"focus_m": round(mod_m * 12.0, 2),     "effective_squeeze": sq_at_far},
        {"focus_m": "infinity",                 "effective_squeeze": 2.0},
    ]


def _heuristic_breathing(focal_mm: float, mod_m: float) -> list[dict]:
    """FOV shift % at MOD. Wider lenses breathe more."""
    shift = 4.0 * math.sqrt(50.0 / focal_mm)
    shift = max(0.5, min(5.0, shift))
    return [
        {"focus_m": mod_m,                  "fov_shift_pct": round(shift,        2)},
        {"focus_m": round(mod_m * 2.5, 2),  "fov_shift_pct": round(shift * 0.35, 2)},
        {"focus_m": "infinity",             "fov_shift_pct": 0.0},
    ]


def _heuristic_distortion(focal_mm: float) -> dict:
    """Mild barrel distortion that decreases with focal length."""
    k1 = round(-0.020 * math.sqrt(50.0 / focal_mm), 4)
    k2 = round( 0.0025 * (50.0 / focal_mm),         4)
    sq_uniformity = round(min(0.97, max(0.92, 0.92 + 0.0002 * focal_mm)), 3)
    return {
        "k1": k1, "k2": k2, "k3": 0.0, "p1": 0.0, "p2": 0.0,
        "squeeze_uniformity": sq_uniformity,
    }


# ── Builder ───────────────────────────────────────────────────────────────

def _build_lens_dict(prime_row: tuple) -> dict:
    """Convert one PDF row + heuristics into the v4 lens JSON dict."""
    (focal, tmin, tmax, mod_mm, length_mm, front_dia_mm, weight_kg,
     filter_thread, hfov, vfov, focal_label) = prime_row
    mod_m = round(mod_mm / 1000.0, 3)
    return {
        "lens_id":         f"cooke_ana_i_s35_{focal_label}",
        "manufacturer":    _SHARED["manufacturer"],
        "series":          _SHARED["series"],
        "focal_length_mm": focal,
        "t_stop_range":    [tmin, tmax],
        "iris_blades":     _SHARED["iris_blades"],
        "close_focus_m":   mod_m,
        "image_circle_mm": _SHARED["image_circle_mm"],
        "squeeze_ratio":   _SHARED["squeeze_ratio"],
        "mount":           _SHARED["mount"],
        "mechanics": {
            "weight_kg":         weight_kg,
            "length_mm":         length_mm,
            "front_diameter_mm": front_dia_mm,
            "filter_thread":     filter_thread,
            "focus_ring": {
                "rotation_deg": _SHARED["focus_rotation_deg"],
                "gear_teeth":   _SHARED["focus_drive_gear_teeth"],
                "gear_module":  _SHARED["focus_drive_gear_module"],
            },
            "iris_ring": {
                "rotation_deg": _SHARED["iris_rotation_deg"],
                "gear_teeth":   _SHARED["iris_drive_gear_teeth"],
                "gear_module":  _SHARED["iris_drive_gear_module"],
            },
            "entrance_pupil_offset_mm": _heuristic_pupil_offset_mm(length_mm),
        },
        "fov_pdf_reference": {
            "max_horizontal_deg": hfov,
            "max_vertical_deg":   vfov,
        },
        "squeeze_breathing": _heuristic_squeeze_breathing(focal, mod_m),
        "distortion":        _heuristic_distortion(focal),
        "breathing":         _heuristic_breathing(focal, mod_m),
        "_provenance": {
            "pdf_source":       COOKE_ANA_I_S35_PDF_FILE,
            "pdf_version":      COOKE_ANA_I_S35_PDF_VERSION,
            "pdf_authoritative": [
                "focal_length_mm", "t_stop_range", "close_focus_m",
                "image_circle_mm", "squeeze_ratio", "mount",
                "mechanics.weight_kg", "mechanics.length_mm",
                "mechanics.front_diameter_mm", "mechanics.filter_thread",
                "mechanics.focus_ring.rotation_deg",
                "mechanics.focus_ring.gear_teeth",
                "mechanics.focus_ring.gear_module",
                "mechanics.iris_ring.rotation_deg",
                "mechanics.iris_ring.gear_teeth",
                "mechanics.iris_ring.gear_module",
                "fov_pdf_reference.max_horizontal_deg",
                "fov_pdf_reference.max_vertical_deg",
            ],
            "heuristic": {
                "iris_blades":
                    "industry_standard (cine prime typical: 11)",
                "mechanics.entrance_pupil_offset_mm":
                    "optical_center (length_mm * 0.5) -- replace via Wolfram W4 fit_pupil_shift",
                "squeeze_breathing":
                    "focal_scaled (deficit_at_MOD = 0.15 * sqrt(50/focal), clamped [0.05, 0.20]) -- replace via Wolfram W2-W3 fit_squeeze_breathing",
                "breathing":
                    "focal_scaled (shift_at_MOD pct = 4.0 * sqrt(50/focal), clamped [0.5, 5.0])",
                "distortion.k1":
                    "focal_scaled (-0.020 * sqrt(50/focal))",
                "distortion.k2":
                    "focal_scaled (0.0025 * (50/focal))",
                "distortion.squeeze_uniformity":
                    "focal_scaled (0.92 + 0.0002*focal, clamped [0.92, 0.97])",
            },
        },
    }


# ── Public dataset ────────────────────────────────────────────────────────

COOKE_ANA_I_S35_LENSES: list[dict] = [_build_lens_dict(row) for row in _PRIMES]
COOKE_ANA_I_S35_BY_ID:  dict[str, dict] = {L["lens_id"]: L for L in COOKE_ANA_I_S35_LENSES}


__all__ = [
    "COOKE_ANA_I_S35_LENSES",
    "COOKE_ANA_I_S35_BY_ID",
    "COOKE_ANA_I_S35_PDF_VERSION",
    "COOKE_ANA_I_S35_PDF_FILE",
]
