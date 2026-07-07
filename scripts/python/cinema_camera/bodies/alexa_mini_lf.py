"""
ARRI ALEXA Mini LF camera body specification.

Sensor: 4.5K Large Format, ALEV-III CMOS (single-native ISO)
Native ISO: 800
Color Science: ARRI LogC3 / ARRI Wide Gamut 3
Body Weight: 3.5 kg (body + EVF + battery, operational rig weight)

Notes:
  Roger Deakins's go-to body for 1917 and Empire of Light. Large-format
  sensor (36.70 x 25.54 mm) vignettes Cooke S35 anamorphic glass at full
  readout -- pair with the S35 anamorphic crop format below, or with the
  Cooke Anamorphic/i Full Frame Plus line (1.8x squeeze) for full coverage.
"""

from __future__ import annotations

from ..protocols import CameraState, SensorSpec, FormatSpec
from ..registry import register_body


ALEXA_MINI_LF_SENSOR = SensorSpec(
    width_mm=36.70,
    height_mm=25.54,
    native_iso=800,
    color_science="ARRI LogC3",
    pixel_pitch_um=8.25,
)

ALEXA_MINI_LF_FORMATS = {
    "4.5K LF Open Gate":       FormatSpec(4448, 3096, "4.5K LF Open Gate", 36.70, 25.54),
    "4.3K LF 16:9":            FormatSpec(4320, 2430, "4.3K LF 16:9", 35.64, 20.05),
    "UHD LF 16:9":             FormatSpec(3840, 2160, "UHD LF 16:9", 31.68, 17.82),
    "S35 2.8K 4:3 (2x ana)":   FormatSpec(2880, 2160, "S35 2.8K 4:3 (2x ana)", 23.76, 17.82),
}

BODY_WEIGHT_KG = 3.5


def create_alexa_mini_lf(
    format_name: str = "4.5K LF Open Gate",
    exposure_index: int = 800,
    shutter_angle_deg: float = 180.0,
) -> CameraState:
    """Factory: create an ARRI ALEXA Mini LF camera state."""
    fmt = ALEXA_MINI_LF_FORMATS.get(format_name)
    if fmt is None:
        raise ValueError(
            f"Unknown format '{format_name}'. "
            f"Available: {list(ALEXA_MINI_LF_FORMATS.keys())}"
        )
    return CameraState(
        model="ARRI ALEXA Mini LF",
        sensor=ALEXA_MINI_LF_SENSOR,
        format=fmt,
        exposure_index=exposure_index,
        shutter_angle_deg=shutter_angle_deg,
    )


register_body("arri_alexa_mini_lf", create_alexa_mini_lf)
