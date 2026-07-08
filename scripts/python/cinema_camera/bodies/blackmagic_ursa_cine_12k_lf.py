"""
Blackmagic URSA Cine 12K LF camera body specification.

Sensor: 12K Large Format CMOS (Gen 5 color science)
Native ISO: 800 (with dual-gain readout for clean shadow lift)
Color Science: Blackmagic Wide Gamut Gen 5 / Blackmagic Film Gen 5
Body Weight: 4.5 kg (body + EVF + grip + battery, operational rig weight)

Notes:
  Blackmagic's 2024 flagship cine body; sees feature/indie adoption in 2026
  as a budget-tier LF alternative to ALEXA Mini LF and VENICE 2. LF sensor
  (35.64 x 23.32 mm active, per Blackmagic tech specs -- not the marketing
  "36 x 24") is close to VENICE 2's full-frame; pairs with Cooke Anamorphic/i
  FF+ at native readout, or with Cooke Anamorphic/i
  S35 via the S35 crop format below.

  Native BRAW 12-bit recording; integrated 24V power; PL/LPL/LF mount options.
"""

from __future__ import annotations

from ..protocols import CameraState, SensorSpec, FormatSpec
from ..registry import register_body


URSA_CINE_12K_SENSOR = SensorSpec(
    width_mm=35.64,
    height_mm=23.32,
    native_iso=800,
    color_science="Blackmagic Wide Gamut Gen 5",
    pixel_pitch_um=2.9,
)

# 12K/6:5 are native-pitch windows; 8K/UHD are full-width downsamples (retain
# FOV). active mm are the read sensor region, not px * pitch, for that reason.
URSA_CINE_12K_FORMATS = {
    "12K LF 3:2":         FormatSpec(12288, 8040, "12K LF 3:2", 35.64, 23.32),
    "12K LF 17:9":        FormatSpec(12288, 6480, "12K LF 17:9", 35.64, 18.79),
    "12K 6:5 (2x ana)":   FormatSpec(9648, 8040, "12K 6:5 (2x ana)", 27.98, 23.32),
    "8K LF 16:9":         FormatSpec(8192, 4608, "8K LF 16:9", 35.64, 20.05),
    "UHD 4K":             FormatSpec(3840, 2160, "UHD 4K", 35.64, 20.05),
}

BODY_WEIGHT_KG = 4.5


def create_ursa_cine_12k_lf(
    format_name: str = "12K LF 3:2",
    exposure_index: int = 800,
    shutter_angle_deg: float = 180.0,
) -> CameraState:
    """Factory: create a Blackmagic URSA Cine 12K LF camera state."""
    fmt = URSA_CINE_12K_FORMATS.get(format_name)
    if fmt is None:
        raise ValueError(
            f"Unknown format '{format_name}'. "
            f"Available: {list(URSA_CINE_12K_FORMATS.keys())}"
        )
    return CameraState(
        model="Blackmagic URSA Cine 12K LF",
        sensor=URSA_CINE_12K_SENSOR,
        format=fmt,
        exposure_index=exposure_index,
        shutter_angle_deg=shutter_angle_deg,
    )


register_body("blackmagic_ursa_cine_12k_lf", create_ursa_cine_12k_lf)
