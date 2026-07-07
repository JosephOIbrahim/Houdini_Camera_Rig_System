"""
RED V-RAPTOR 8K VV camera body specification.

Sensor: 8K Vista Vision CMOS (Monstro derivative)
Native ISO: 800
Color Science: REDWideGamutRGB / Log3G10 (IPP2 pipeline)
Body Weight: 2.5 kg (body + RED touch LCD + V-mount battery, operational rig weight)

Notes:
  RED's flagship VistaVision format body. 8192 x 4320 full VV readout (35.4 MP;
  lower resolutions are center-crop windows, not downsamples). VV sensor
  (40.96 x 21.60 mm) covers Cooke S35 anamorphic with mild vignetting; use the
  6K S35 crop format for clean S35 anamorphic coverage. Pair with Cooke
  Anamorphic/i Full Frame Plus line for full VV anamorphic at native readout.

  RF mount native, with EF / V-Mount / B4 / PL adapters available. Compact
  body (2.5 kg) makes it gimbal- and Steadicam-friendly.
"""

from __future__ import annotations

from ..protocols import CameraState, SensorSpec, FormatSpec
from ..registry import register_body


V_RAPTOR_8K_VV_SENSOR = SensorSpec(
    width_mm=40.96,
    height_mm=21.60,
    native_iso=800,
    color_science="REDWideGamutRGB / Log3G10",
    pixel_pitch_um=5.0,
)

# Center-crop windows (native 5.0um pitch). The fabricated "8K VV 3:2 Full"
# 8192x5760 exceeded the VV sensor's 4320 physical rows -- dropped.
V_RAPTOR_8K_VV_FORMATS = {
    "8K VV 17:9":              FormatSpec(8192, 4320, "8K VV 17:9", 40.96, 21.60),
    "6K S35 Anamorphic crop":  FormatSpec(6144, 3240, "6K S35 Anamorphic crop", 30.72, 16.20),
    "4K S35 16:9":             FormatSpec(4096, 2160, "4K S35 16:9", 20.48, 10.80),
}

BODY_WEIGHT_KG = 2.5


def create_red_v_raptor_8k_vv(
    format_name: str = "8K VV 17:9",
    exposure_index: int = 800,
    shutter_angle_deg: float = 180.0,
) -> CameraState:
    """Factory: create a RED V-RAPTOR 8K VV camera state."""
    fmt = V_RAPTOR_8K_VV_FORMATS.get(format_name)
    if fmt is None:
        raise ValueError(
            f"Unknown format '{format_name}'. "
            f"Available: {list(V_RAPTOR_8K_VV_FORMATS.keys())}"
        )
    return CameraState(
        model="RED V-RAPTOR 8K VV",
        sensor=V_RAPTOR_8K_VV_SENSOR,
        format=fmt,
        exposure_index=exposure_index,
        shutter_angle_deg=shutter_angle_deg,
    )


register_body("red_v_raptor_8k_vv", create_red_v_raptor_8k_vv)
