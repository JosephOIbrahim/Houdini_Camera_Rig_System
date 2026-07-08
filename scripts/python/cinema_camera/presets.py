"""
Cinema Camera Rig v3.2 -- Preset registry.

Six factory presets pairing the top 2026 professional cinema bodies with
the Cooke anamorphic lens family. Used by the HDA "Preset" tab to bulk-fill
body + lens parameters when a preset is selected.

Lens-family mapping:
  - S35 sensors (or S35 crop modes on LF/VV bodies) -> cooke_ana_i_s35 (2.0x squeeze)
  - LF / VV / 65mm full-readout sensors             -> cooke_ana_i_ff_plus (1.8x squeeze)

The body specs here intentionally mirror the SensorSpec / FormatSpec data
in cinema_camera/bodies/*.py but in a flat dict for direct parm-callback
consumption (HDA callbacks can't easily import dataclasses at parm-set time).
"""

from __future__ import annotations


# Ordered tuple of preset keys -- preserves UI display order in the menu parm.
CAMERA_PRESET_ORDER = (
    "alexa_35",
    "alexa_mini_lf",
    "alexa_65",
    "sony_venice_2",
    "red_v_raptor_8k_vv",
    "blackmagic_ursa_cine_12k_lf",
)


CAMERA_PRESETS: dict[str, dict] = {
    # ─────────────────────────────────────────────────────────────────
    # ARRI ALEXA 35 -- Super 35 narrative workhorse (2026 default rig)
    # ─────────────────────────────────────────────────────────────────
    "alexa_35": {
        "label":                    "ARRI ALEXA 35 (S35, 4.6K Open Gate)",
        "body_id":                  "alexa35",
        "model":                    "ARRI ALEXA 35",
        "sensor_width_mm":          27.99,
        "sensor_height_mm":         19.22,
        "resolution_x":             4608,
        "resolution_y":             3164,
        "native_iso":               800,
        "body_weight_kg":           3.9,
        "lens_family":              "cooke_ana_i_s35",
        "default_focal_length_mm":  50.0,
        "default_t_stop":           2.8,
        "squeeze_ratio":            2.0,
        "color_science":            "ARRI LogC4",
    },

    # ─────────────────────────────────────────────────────────────────
    # ARRI ALEXA Mini LF -- Large Format (Deakins's go-to 2019-onwards)
    # ─────────────────────────────────────────────────────────────────
    "alexa_mini_lf": {
        "label":                    "ARRI ALEXA Mini LF (LF, 4.5K Open Gate)",
        "body_id":                  "alexa_mini_lf",
        "model":                    "ARRI ALEXA Mini LF",
        "sensor_width_mm":          36.70,
        "sensor_height_mm":         25.54,
        "resolution_x":             4448,
        "resolution_y":             3096,
        "native_iso":               800,
        "body_weight_kg":           3.5,
        "lens_family":              "cooke_ana_i_ff_plus",
        "default_focal_length_mm":  50.0,
        "default_t_stop":           2.8,
        "squeeze_ratio":            1.8,
        "color_science":            "ARRI LogC3",
    },

    # ─────────────────────────────────────────────────────────────────
    # ARRI ALEXA 65 -- 65mm ultra-premium (Fraser, Deakins BR2049)
    # ─────────────────────────────────────────────────────────────────
    "alexa_65": {
        "label":                    "ARRI ALEXA 65 (65mm, 6.5K Open Gate)",
        "body_id":                  "alexa_65",
        "model":                    "ARRI ALEXA 65",
        "sensor_width_mm":          54.12,
        "sensor_height_mm":         25.58,
        "resolution_x":             6560,
        "resolution_y":             3100,
        "native_iso":               800,
        "body_weight_kg":           11.2,
        "lens_family":              "cooke_ana_i_ff_plus",
        "default_focal_length_mm":  75.0,
        "default_t_stop":           2.8,
        "squeeze_ratio":            1.8,
        "color_science":            "ARRI LogC3",
    },

    # ─────────────────────────────────────────────────────────────────
    # Sony VENICE 2 -- 8.6K Full Frame, dual-native ISO
    # ─────────────────────────────────────────────────────────────────
    "sony_venice_2": {
        "label":                    "Sony VENICE 2 (FF, 8.6K)",
        "body_id":                  "sony_venice_2",
        "model":                    "Sony VENICE 2 (8.6K)",
        "sensor_width_mm":          35.9,
        "sensor_height_mm":         24.0,
        "resolution_x":             8640,
        "resolution_y":             5760,
        "native_iso":               800,
        "body_weight_kg":           4.5,
        "lens_family":              "cooke_ana_i_ff_plus",
        "default_focal_length_mm":  50.0,
        "default_t_stop":           2.8,
        "squeeze_ratio":            1.8,
        "color_science":            "Sony S-Log3 / S-Gamut3.Cine",
    },

    # ─────────────────────────────────────────────────────────────────
    # RED V-RAPTOR 8K VV -- VistaVision flagship
    # ─────────────────────────────────────────────────────────────────
    "red_v_raptor_8k_vv": {
        "label":                    "RED V-RAPTOR 8K VV (Vista Vision)",
        "body_id":                  "red_v_raptor_8k_vv",
        "model":                    "RED V-RAPTOR 8K VV",
        "sensor_width_mm":          40.96,
        "sensor_height_mm":         21.60,
        "resolution_x":             8192,
        "resolution_y":             4320,
        "native_iso":               800,
        "body_weight_kg":           2.5,
        "lens_family":              "cooke_ana_i_ff_plus",
        "default_focal_length_mm":  50.0,
        "default_t_stop":           2.8,
        "squeeze_ratio":            1.8,
        "color_science":            "REDWideGamutRGB / Log3G10",
    },

    # ─────────────────────────────────────────────────────────────────
    # Blackmagic URSA Cine 12K LF -- 12K LF budget-tier flagship
    # ─────────────────────────────────────────────────────────────────
    "blackmagic_ursa_cine_12k_lf": {
        "label":                    "Blackmagic URSA Cine 12K LF",
        "body_id":                  "blackmagic_ursa_cine_12k_lf",
        "model":                    "Blackmagic URSA Cine 12K LF",
        "sensor_width_mm":          35.64,
        "sensor_height_mm":         23.32,
        "resolution_x":             12288,
        "resolution_y":             8040,
        "native_iso":               800,
        "body_weight_kg":           4.5,
        "lens_family":              "cooke_ana_i_ff_plus",
        "default_focal_length_mm":  50.0,
        "default_t_stop":           2.8,
        "squeeze_ratio":            1.8,
        "color_science":            "Blackmagic Wide Gamut Gen 5",
    },
}


# ─────────────────────────────────────────────────────────────────
# Sensor-plane mount offsets (cm): y above the tripod plate, z behind
# the operator handle. Single source of truth — consumed by
# usd_builder.build_usd_camera_rig (and through it the LOP HDA).
# Keyed by body_id; model-name and pre-v3.2 legacy keys kept as aliases.
# ─────────────────────────────────────────────────────────────────
MOUNT_OFFSETS_CM: dict[str, dict[str, float]] = {
    # 2026 factory presets (body_id keys)
    "alexa35":                     {"y": 5.0, "z": -8.0},
    "alexa_mini_lf":               {"y": 4.5, "z": -7.0},
    "alexa_65":                    {"y": 7.0, "z": -12.5},
    "sony_venice_2":               {"y": 5.5, "z": -9.0},
    "red_v_raptor_8k_vv":          {"y": 3.5, "z": -5.5},
    "blackmagic_ursa_cine_12k_lf": {"y": 5.5, "z": -9.0},
    # Model-name aliases (pure-pxr usd_builder path keys by CameraState.model)
    "ARRI ALEXA 35":               {"y": 5.0, "z": -8.0},
    "RED KOMODO":                  {"y": 3.5, "z": -5.0},
    "SONY VENICE 2":               {"y": 5.5, "z": -9.0},
    # Legacy ids (pre-v3.2 scenes)
    "red_komodo":                  {"y": 3.5, "z": -5.0},
    "sony_venice2":                {"y": 5.5, "z": -9.0},
}

DEFAULT_MOUNT_OFFSET_CM: dict[str, float] = {"y": 4.0, "z": -7.0}


def mount_offset_for(*keys: str) -> dict[str, float]:
    """First MOUNT_OFFSETS_CM hit among the given keys (body_id, model...),
    else the default offset."""
    for key in keys:
        if key and key in MOUNT_OFFSETS_CM:
            return MOUNT_OFFSETS_CM[key]
    return DEFAULT_MOUNT_OFFSET_CM


def body_weight_for(body_id: str) -> float | None:
    """Operational body weight (kg) for a body_id, or None if unknown."""
    for p in CAMERA_PRESETS.values():
        if p["body_id"] == body_id:
            return p["body_weight_kg"]
    return None


def model_for(body_id: str) -> str | None:
    """Human-readable model string for a body_id, or None if unknown."""
    for p in CAMERA_PRESETS.values():
        if p["body_id"] == body_id:
            return p["model"]
    return None


def get_preset(preset_key: str) -> dict:
    """Lookup preset by key; raises KeyError if unknown."""
    if preset_key not in CAMERA_PRESETS:
        raise KeyError(
            f"Unknown preset '{preset_key}'. "
            f"Available: {list(CAMERA_PRESET_ORDER)}"
        )
    return CAMERA_PRESETS[preset_key]


def list_presets() -> list[str]:
    """Return ordered list of preset keys."""
    return list(CAMERA_PRESET_ORDER)


def list_preset_labels() -> list[tuple[str, str]]:
    """Return ordered list of (key, label) tuples for menu UI."""
    return [(k, CAMERA_PRESETS[k]["label"]) for k in CAMERA_PRESET_ORDER]
