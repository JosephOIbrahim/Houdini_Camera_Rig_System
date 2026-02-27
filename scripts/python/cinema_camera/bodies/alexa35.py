"""
ARRI ALEXA 35 camera body specification.

Sensor: 4.6K Super 35, ALEV-IV CMOS
Native ISO: 800 (dual-gain at 800 and 2560)
Color Science: ARRI LogC4 / ARRI Wide Gamut 4
Body Weight: 3.9 kg (body only, no lens or viewfinder)
"""

from __future__ import annotations

from ..protocols import CameraState, SensorSpec, FormatSpec
from ..registry import register_body


# ARRI ALEXA 35 sensor specification
ALEXA35_SENSOR = SensorSpec(
    width_mm=27.99,       # Active area width (Open Gate)
    height_mm=19.22,      # Active area height (Open Gate)
    native_iso=800,
    color_science="ARRI LogC4",
    pixel_pitch_um=6.075,
)

# Common recording formats
ALEXA35_FORMATS = {
    "4.6K 3:2 Open Gate": FormatSpec(4608, 3164, "4.6K 3:2 Open Gate"),
    "4K 16:9":            FormatSpec(4096, 2304, "4K 16:9"),
    "UHD":                FormatSpec(3840, 2160, "UHD"),
    "2K 16:9":            FormatSpec(2048, 1152, "2K 16:9"),
}

# Camera body weight (no accessories)
BODY_WEIGHT_KG = 3.9


def create_alexa35(
    format_name: str = "4.6K 3:2 Open Gate",
    exposure_index: int = 800,
    shutter_angle_deg: float = 180.0,
) -> CameraState:
    """Factory: create an ARRI ALEXA 35 camera state."""
    fmt = ALEXA35_FORMATS.get(format_name)
    if fmt is None:
        raise ValueError(
            f"Unknown format '{format_name}'. "
            f"Available: {list(ALEXA35_FORMATS.keys())}"
        )
    return CameraState(
        model="ARRI ALEXA 35",
        sensor=ALEXA35_SENSOR,
        format=fmt,
        exposure_index=exposure_index,
        shutter_angle_deg=shutter_angle_deg,
    )


# Auto-register on import
register_body("arri_alexa_35", create_alexa35)
