"""
Cooke Anamorphic/i S35 lens provider.

Parses v4.0 JSON with full mechanical + squeeze breathing data.
Backwards-compatible: v3.0 JSON (without mechanics) loads cleanly.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from ..protocols import (
    BreathingCurve,
    DistortionModel,
    GearRingSpec,
    LensSpec,
    LensState,
    MechanicalSpec,
    SqueezeBreathingCurve,
)
from ..registry import register_lens


class CookeAnamorphicLens:
    """Wrapper providing lens state management around a LensSpec."""

    def __init__(self, spec: LensSpec, node=None):
        self._spec = spec
        self._node = node  # Optional hou.Node reference

    @property
    def spec(self) -> LensSpec:
        return self._spec

    def create_state(self, t_stop: float, focus_distance_m: float) -> LensState:
        """Create a LensState at given T-stop and focus distance."""
        return LensState(
            spec=self._spec,
            t_stop=t_stop,
            focus_distance_m=focus_distance_m,
        )

    @classmethod
    def from_json(cls, json_path: Path, node=None) -> CookeAnamorphicLens:
        """
        Factory: load from v4.0 JSON with full validation.
        Backwards-compatible with v3.0 JSON.
        """
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # -- Parse breathing curve (v3.0) --
        breathing_points = []
        for bp in data.get("breathing", []):
            focus = bp["focus_m"]
            if isinstance(focus, str) and focus.lower() == "infinity":
                focus = 1e10
            breathing_points.append((float(focus), bp["fov_shift_pct"]))

        # -- Parse distortion (v3.0) --
        dist_data = data.get("distortion", {})

        # -- Parse mechanical spec (v4.0 -- optional) --
        mechanics = None
        mech_data = data.get("mechanics")
        if mech_data:
            focus_ring_data = mech_data.get("focus_ring", {})
            iris_ring_data = mech_data.get("iris_ring", {})
            mechanics = MechanicalSpec(
                weight_kg=mech_data["weight_kg"],
                length_mm=mech_data["length_mm"],
                front_diameter_mm=mech_data["front_diameter_mm"],
                filter_thread=mech_data.get("filter_thread", ""),
                focus_ring=GearRingSpec(
                    rotation_deg=focus_ring_data.get("rotation_deg", 300.0),
                    gear_teeth=focus_ring_data.get("gear_teeth", 140),
                    gear_module=focus_ring_data.get("gear_module", 0.8),
                ),
                iris_ring=GearRingSpec(
                    rotation_deg=iris_ring_data.get("rotation_deg", 90.0),
                    gear_teeth=iris_ring_data.get("gear_teeth", 134),
                    gear_module=iris_ring_data.get("gear_module", 0.8),
                ),
                entrance_pupil_offset_mm=mech_data.get("entrance_pupil_offset_mm", 0.0),
            )

        # -- Parse squeeze breathing (v4.0 -- optional) --
        squeeze_breathing = None
        squeeze_data = data.get("squeeze_breathing")
        if squeeze_data:
            sq_points = []
            for sp in squeeze_data:
                focus = sp["focus_m"]
                if isinstance(focus, str) and focus.lower() == "infinity":
                    focus = 1e10
                sq_points.append((float(focus), sp["effective_squeeze"]))
            squeeze_breathing = SqueezeBreathingCurve(
                tuple(sq_points),
                nominal_squeeze=data.get("squeeze_ratio", 2.0),
            )

        spec = LensSpec(
            lens_id=data["lens_id"],
            manufacturer=data["manufacturer"],
            series=data["series"],
            focal_length_mm=data["focal_length_mm"],
            t_stop_min=data["t_stop_range"][0],
            t_stop_max=data["t_stop_range"][1],
            iris_blades=data["iris_blades"],
            close_focus_m=data["close_focus_m"],
            image_circle_mm=data.get("image_circle_mm", 31.1),
            squeeze_ratio=data["squeeze_ratio"],
            distortion=DistortionModel(
                k1=dist_data.get("k1", 0),
                k2=dist_data.get("k2", 0),
                k3=dist_data.get("k3", 0),
                p1=dist_data.get("p1", 0),
                p2=dist_data.get("p2", 0),
                squeeze_uniformity=dist_data.get("squeeze_uniformity", 1.0),
            ),
            breathing=BreathingCurve(tuple(breathing_points)),
            lateral_ca_px_per_mm=data.get("chromatic_aberration", {}).get("lateral_ca_px_per_mm", 0),
            longitudinal_ca_stops=data.get("chromatic_aberration", {}).get("longitudinal_ca_stops", 0),
            mechanics=mechanics,
            squeeze_breathing=squeeze_breathing,
        )

        return cls(spec, node)


def _load_cooke_anamorphic(json_path: Path) -> LensSpec:
    """Registry-compatible loader returning just the LensSpec."""
    lens = CookeAnamorphicLens.from_json(json_path)
    return lens.spec


# Auto-register on import
register_lens("cooke_ana_i_s35", _load_cooke_anamorphic)
