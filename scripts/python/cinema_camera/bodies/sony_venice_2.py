"""
Sony VENICE 2 (8.6K) camera body specification.

Sensor: 8.6K Full Frame CMOS
Dual-Native ISO: 800 / 3200
Color Science: S-Cinetone, S-Log3 / S-Gamut3.Cine
Body Weight: 4.5 kg (body + EVF + battery, operational rig weight)

Notes:
  Sony's flagship 2026 full-frame cine camera. Used by Erik Messerschmidt,
  Ben Davis, Greig Fraser (some commercials). Native sensor (35.9 x 24.0 mm)
  vignettes Cooke S35 anamorphic glass at full readout -- use the S35 4K
  crop format below for S35 anamorphic glass, or the Cooke Anamorphic/i FF+
  line at full FF readout.

  Dual-native ISO is a key Sony differentiator: clean output at both 800
  and 3200 base sensitivities (compared to ALEXA's single-native 800).
"""

from __future__ import annotations

from ..protocols import CameraState, SensorSpec, FormatSpec
from ..registry import register_body


VENICE_2_SENSOR = SensorSpec(
    width_mm=35.9,
    height_mm=24.0,
    native_iso=800,           # Dual-native: 800 / 3200. Default to low-ISO base.
    color_science="Sony S-Log3 / S-Gamut3.Cine",
    pixel_pitch_um=4.16,
)

VENICE_2_FORMATS = {
    "8.6K 3:2 Full Frame":    FormatSpec(8640, 5760, "8.6K 3:2 Full Frame", 35.90, 24.00),
    "8.2K 17:9 Full Frame":   FormatSpec(8192, 4320, "8.2K 17:9 Full Frame", 34.10, 18.00),
    "6K Full Frame":          FormatSpec(6048, 4032, "6K Full Frame", 35.90, 23.93),
    "S35 5.8K 17:9 crop":     FormatSpec(5792, 3056, "S35 5.8K 17:9 crop", 24.10, 12.70),
    "S35 5.8K 6:5 (2x ana)":  FormatSpec(5792, 4854, "S35 5.8K 6:5 (2x ana)", 24.10, 20.20),
}

BODY_WEIGHT_KG = 4.5

# Sony VENICE 2 second native ISO (high-gain stage)
SECOND_NATIVE_ISO = 3200


def create_sony_venice_2(
    format_name: str = "8.6K 3:2 Full Frame",
    exposure_index: int = 800,
    shutter_angle_deg: float = 180.0,
) -> CameraState:
    """Factory: create a Sony VENICE 2 camera state."""
    fmt = VENICE_2_FORMATS.get(format_name)
    if fmt is None:
        raise ValueError(
            f"Unknown format '{format_name}'. "
            f"Available: {list(VENICE_2_FORMATS.keys())}"
        )
    return CameraState(
        model="Sony VENICE 2 (8.6K)",
        sensor=VENICE_2_SENSOR,
        format=fmt,
        exposure_index=exposure_index,
        shutter_angle_deg=shutter_angle_deg,
    )


register_body("sony_venice_2", create_sony_venice_2)
