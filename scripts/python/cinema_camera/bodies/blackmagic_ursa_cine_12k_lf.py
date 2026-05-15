"""
Blackmagic URSA Cine 12K LF camera body specification.

Sensor: 12K Large Format CMOS (Gen 5 color science)
Native ISO: 800 (with dual-gain readout for clean shadow lift)
Color Science: Blackmagic Wide Gamut Gen 5 / Blackmagic Film Gen 5
Body Weight: 4.5 kg (body + EVF + grip + battery, operational rig weight)

Notes:
  Blackmagic's 2024 flagship cine body; sees feature/indie adoption in 2026
  as a budget-tier LF alternative to ALEXA Mini LF and VENICE 2. LF sensor
  (36.0 x 24.0 mm) is the same physical size as VENICE 2's full-frame; pairs
  with Cooke Anamorphic/i FF+ at native readout, or with Cooke Anamorphic/i
  S35 via the S35 crop format below.

  Native BRAW 12-bit recording; integrated 24V power; PL/LPL/LF mount options.
"""

from __future__ import annotations

from ..protocols import CameraState, SensorSpec, FormatSpec
from ..registry import register_body


URSA_CINE_12K_SENSOR = SensorSpec(
    width_mm=36.0,
    height_mm=24.0,
    native_iso=800,
    color_science="Blackmagic Wide Gamut Gen 5",
    pixel_pitch_um=2.93,
)

URSA_CINE_12K_FORMATS = {
    "12K LF 3:2":               FormatSpec(12288, 8064, "12K LF 3:2"),
    "12K LF 17:9":              FormatSpec(12288, 6480, "12K LF 17:9"),
    "8K LF 16:9":               FormatSpec(8192, 4608, "8K LF 16:9"),
    "S35 6K Anamorphic crop":   FormatSpec(6144, 5120, "S35 6K Anamorphic crop"),
    "UHD 4K":                   FormatSpec(3840, 2160, "UHD 4K"),
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
