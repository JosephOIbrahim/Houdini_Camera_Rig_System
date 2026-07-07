"""
ARRI ALEXA 65 camera body specification.

Sensor: 6.5K 65mm format, ALEV-III CMOS (3x stitched ALEV silicon)
Native ISO: 800
Color Science: ARRI LogC3 / ARRI Wide Gamut 3
Body Weight: 11.2 kg (with hard mount + EVF + battery, operational rig weight)

Notes:
  Ultra-premium 65mm format. ARRI Rental house only -- not retail.
  Used by Greig Fraser (Dune, The Batman), Roger Deakins (Blade Runner 2049),
  Linus Sandgren. Sensor (54.12 x 25.58 mm Open Gate) vignettes S35 anamorphic
  glass entirely; pair with the S35 anamorphic crop format below for use with
  the Cooke Anamorphic/i S35 line, or with the Cooke Anamorphic/i Full Frame
  Plus line for full-frame anamorphic on the larger sensor area.

  The 11.2 kg weight is significant for biomechanics: spring constant and
  damping ratio auto-derive (see build_camera_rig_lop.py:188-192) yield a
  much heavier-feeling rig than the S35 ALEXA 35 (3.9 kg).
"""

from __future__ import annotations

from ..protocols import CameraState, SensorSpec, FormatSpec
from ..registry import register_body


ALEXA_65_SENSOR = SensorSpec(
    width_mm=54.12,
    height_mm=25.58,
    native_iso=800,
    color_science="ARRI LogC3",
    pixel_pitch_um=8.25,
)

# Real A65 modes (the fabricated "6K 16:9 Spherical" 6560x3694 exceeded the
# sensor's physical rows -- dropped). px + active mm (native 8.25um pitch).
ALEXA_65_FORMATS = {
    "6.5K Open Gate": FormatSpec(6560, 3100, "6.5K Open Gate", 54.12, 25.58),
    "5.1K 16:9":      FormatSpec(5120, 2880, "5.1K 16:9", 42.24, 23.76),
    "4.3K 16:9":      FormatSpec(4320, 2880, "4.3K 16:9", 35.64, 23.76),
    "4K UHD":         FormatSpec(3840, 2160, "4K UHD", 31.68, 17.82),
}

BODY_WEIGHT_KG = 11.2


def create_alexa_65(
    format_name: str = "6.5K Open Gate",
    exposure_index: int = 800,
    shutter_angle_deg: float = 180.0,
) -> CameraState:
    """Factory: create an ARRI ALEXA 65 camera state."""
    fmt = ALEXA_65_FORMATS.get(format_name)
    if fmt is None:
        raise ValueError(
            f"Unknown format '{format_name}'. "
            f"Available: {list(ALEXA_65_FORMATS.keys())}"
        )
    return CameraState(
        model="ARRI ALEXA 65",
        sensor=ALEXA_65_SENSOR,
        format=fmt,
        exposure_index=exposure_index,
        shutter_angle_deg=shutter_angle_deg,
    )


register_body("arri_alexa_65", create_alexa_65)
