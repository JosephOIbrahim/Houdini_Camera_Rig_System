"""
Cinema Camera Rig v4.0 — Protocol Dataclasses

Typed data contracts for the entire camera rig pipeline.
v3.0 foundation types + v4.0 mechanical/dynamic extensions.

All dataclasses are frozen (immutable after creation) for thread safety
and to enforce the data-flows-forward architecture.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Optional


# ════════════════════════════════════════════════════════════
# RIG-WIDE CONVENTIONS
# ════════════════════════════════════════════════════════════

# Entrance pupil sign convention (single source of truth).
#
# Camera space looks down -Z. The entrance pupil (nodal point) sits IN FRONT
# of the sensor, toward the scene, i.e. at NEGATIVE Z in camera/sensor space.
#
# Offsets (entrance_pupil_offset_mm/cm) are stored and passed everywhere as
# UNSIGNED MAGNITUDES; the sign is applied at each authoring site:
#   - usd_builder.py        EntrancePupil xform: translate z = SIGN * offset_cm
#   - karma_cinema_lens.vfl ray origin:          P.z = -offset (literal negation,
#                           equivalent to SIGN * offset for positive offsets)
#   - OBJ orchestrator      the INVERSE: the cam sits BEHIND the pivot, so the
#                           cam child gets tz = -SIGN * offset (positive Z).
ENTRANCE_PUPIL_Z_SIGN = -1.0


# Default lens transmission (tau) used to derive a geometric f-number from a
# published T-stop when the lens spec carries no measured transmission.
# HEURISTIC: typical cine glass tau ~ 0.80-0.90. The geometric f-number
# (N = T * sqrt(tau)) is the correct aperture for DEPTH OF FIELD / bokeh;
# the T-stop remains correct for EXPOSURE. See LensState.f_number.
DEFAULT_TRANSMISSION = 0.85


# ════════════════════════════════════════════════════════════
# v3.0 FOUNDATION TYPES
# ════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class DistortionModel:
    """Brown-Conrady distortion coefficients + anamorphic squeeze uniformity."""
    k1: float = 0.0          # Radial distortion (barrel/pincushion)
    k2: float = 0.0          # Higher-order radial
    k3: float = 0.0          # Highest-order radial
    p1: float = 0.0          # Tangential distortion
    p2: float = 0.0          # Tangential distortion
    squeeze_uniformity: float = 1.0  # 1.0 = perfect, <1.0 = squeeze varies across frame

    def __post_init__(self):
        if not (0.8 <= self.squeeze_uniformity <= 1.0):
            raise ValueError(
                f"squeeze_uniformity must be 0.8-1.0, got {self.squeeze_uniformity}"
            )


@dataclass(frozen=True)
class BreathingCurve:
    """
    Focus-dependent FOV shift (breathing).

    Points: ((focus_m, fov_shift_pct), ...) sorted by focus_m ascending.
    At infinity focus, shift is 0%. At close focus, shift is positive (wider FOV).
    """
    points: tuple[tuple[float, float], ...] = ()

    def __post_init__(self):
        if self.points:
            sorted_pts = tuple(sorted(self.points, key=lambda p: p[0]))
            object.__setattr__(self, 'points', sorted_pts)

    def evaluate(self, focus_distance_m: float) -> float:
        """Linear interpolation of FOV shift at given focus distance."""
        if not self.points:
            return 0.0
        if focus_distance_m <= self.points[0][0]:
            return self.points[0][1]
        if focus_distance_m >= self.points[-1][0]:
            return self.points[-1][1]
        for i in range(len(self.points) - 1):
            f0, s0 = self.points[i]
            f1, s1 = self.points[i + 1]
            if f0 <= focus_distance_m <= f1:
                t = (focus_distance_m - f0) / (f1 - f0) if f1 != f0 else 0
                return s0 + t * (s1 - s0)
        return 0.0


@dataclass(frozen=True)
class SensorSpec:
    """Physical sensor specification."""
    width_mm: float
    height_mm: float
    native_iso: int = 800
    color_science: str = "ARRI LogC4"
    pixel_pitch_um: float = 0.0  # 0 = unknown/not specified

    def __post_init__(self):
        if self.width_mm <= 0 or self.height_mm <= 0:
            raise ValueError(
                f"Invalid sensor dimensions: {self.width_mm}x{self.height_mm}mm"
            )

    @property
    def diagonal_mm(self) -> float:
        return math.sqrt(self.width_mm ** 2 + self.height_mm ** 2)

    @property
    def aspect_ratio(self) -> float:
        return self.width_mm / self.height_mm


@dataclass(frozen=True)
class FormatSpec:
    """
    Recording format / resolution.

    active_width_mm / active_height_mm are the physical sensor SUB-REGION the
    format reads (0.0 = open gate, i.e. use the full SensorSpec dimensions).
    Stored EXPLICITLY, not derived from width_px * pixel_pitch: window modes
    shrink at native pitch while downsample modes keep the full width at a
    reduced resolution, and the two cannot be told apart from resolution alone.
    """
    width_px: int
    height_px: int
    name: str = ""
    active_width_mm: float = 0.0
    active_height_mm: float = 0.0

    def __post_init__(self):
        if self.width_px <= 0 or self.height_px <= 0:
            raise ValueError(
                f"Invalid resolution: {self.width_px}x{self.height_px}"
            )
        if self.active_width_mm < 0 or self.active_height_mm < 0:
            raise ValueError(
                f"Invalid active area: "
                f"{self.active_width_mm}x{self.active_height_mm}mm"
            )

    @property
    def aspect_ratio(self) -> float:
        return self.width_px / self.height_px


@dataclass(frozen=True)
class CameraState:
    """
    Camera body state at a single frame.
    Combines sensor, format, and exposure settings.
    """
    model: str
    sensor: SensorSpec
    format: FormatSpec
    exposure_index: int = 800
    shutter_angle_deg: float = 180.0
    white_balance_k: int = 5600
    fps: float = 24.0

    def __post_init__(self):
        if self.exposure_index <= 0:
            raise ValueError(f"Invalid exposure index: {self.exposure_index}")
        if not (0 < self.shutter_angle_deg <= 360):
            raise ValueError(f"Invalid shutter angle: {self.shutter_angle_deg}")
        if self.fps <= 0:
            raise ValueError(f"Invalid fps: {self.fps}")
        # Photosite-ceiling guard: recorded rows/cols cannot exceed the physical
        # photosites in the active sensor region. Fires only when both the pixel
        # pitch and the format's active area are known. Catches fabricated specs
        # (e.g. a resolution taller than the sensor can physically resolve).
        pitch = self.sensor.pixel_pitch_um
        aw, ah = self.format.active_width_mm, self.format.active_height_mm
        if pitch > 0 and aw > 0 and self.format.width_px > (aw * 1000.0 / pitch) * 1.02:
            raise ValueError(
                f"{self.format.name or 'format'}: {self.format.width_px}px exceeds "
                f"photosites in {aw}mm active width @ {pitch}um pitch"
            )
        if pitch > 0 and ah > 0 and self.format.height_px > (ah * 1000.0 / pitch) * 1.02:
            raise ValueError(
                f"{self.format.name or 'format'}: {self.format.height_px}px exceeds "
                f"photosites in {ah}mm active height @ {pitch}um pitch"
            )

    @property
    def active_width_mm(self) -> float:
        """Active sensor width for the current format (falls back to open gate)."""
        return self.format.active_width_mm or self.sensor.width_mm

    @property
    def active_height_mm(self) -> float:
        """Active sensor height for the current format (falls back to open gate)."""
        return self.format.active_height_mm or self.sensor.height_mm

    @property
    def shutter_speed_s(self) -> float:
        """Exposure time in seconds: (shutter_angle / 360) / fps."""
        return self.shutter_angle_deg / (360.0 * self.fps)

    def to_usd_dict(self) -> dict[str, tuple[str, Any]]:
        """Flat dictionary for USD attribute authoring."""
        prefix = "cinema:camera"
        return {
            f"{prefix}:model":           ("String", self.model),
            f"{prefix}:sensorWidthMm":   ("Float",  self.sensor.width_mm),
            f"{prefix}:sensorHeightMm":  ("Float",  self.sensor.height_mm),
            f"{prefix}:exposureIndex":   ("Int",    self.exposure_index),
            f"{prefix}:shutterAngleDeg": ("Float",  self.shutter_angle_deg),
            f"{prefix}:colorScience":    ("String", self.sensor.color_science),
            f"{prefix}:resolutionX":     ("Int",    self.format.width_px),
            f"{prefix}:resolutionY":     ("Int",    self.format.height_px),
        }


@dataclass(frozen=True)
class OpticalResult:
    """Computed optical parameters for a given camera+lens state."""
    hfov_deg: float
    vfov_deg: float
    dof_near_m: float
    dof_far_m: float
    hyperfocal_m: float
    coc_mm: float


# ════════════════════════════════════════════════════════════
# v4.0 MECHANICAL VALUE TYPES
# ════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class GearRingSpec:
    """Physical gear ring on a cinema lens barrel."""
    rotation_deg: float         # Total rotation travel
    gear_teeth: int             # Tooth count for follow-focus motors
    gear_module: float = 0.8   # Standard cine gear module (0.8mm pitch)

    def __post_init__(self):
        if self.rotation_deg <= 0 or self.rotation_deg > 360:
            raise ValueError(f"Invalid gear rotation: {self.rotation_deg}")
        if self.gear_teeth <= 0:
            raise ValueError(f"Invalid gear tooth count: {self.gear_teeth}")
        if self.gear_module <= 0:
            raise ValueError(f"Invalid gear module: {self.gear_module}")

    @property
    def pitch_circle_diameter_mm(self) -> float:
        """PCD = module x teeth. Used for follow-focus motor compatibility."""
        return self.gear_module * self.gear_teeth

    @property
    def degrees_per_tooth(self) -> float:
        """Angular resolution of the gear ring."""
        return self.rotation_deg / self.gear_teeth


@dataclass(frozen=True)
class MechanicalSpec:
    """
    Physical dimensions and mechanics of a cinema lens.
    Required for biomechanics simulation and nodal parallax.
    """
    weight_kg: float
    length_mm: float
    front_diameter_mm: float
    filter_thread: str                              # e.g. "M105x0.75"
    focus_ring: GearRingSpec
    iris_ring: GearRingSpec
    entrance_pupil_offset_mm: float                 # Distance from sensor plane
                                                    # to nodal point. CRITICAL for
                                                    # parallax-correct panning.

    def __post_init__(self):
        if self.weight_kg <= 0:
            raise ValueError(f"Invalid weight: {self.weight_kg}kg")
        if self.length_mm <= 0:
            raise ValueError(f"Invalid length: {self.length_mm}mm")
        if self.front_diameter_mm <= 0:
            raise ValueError(f"Invalid front diameter: {self.front_diameter_mm}mm")
        if self.entrance_pupil_offset_mm < 0:
            raise ValueError(
                f"Invalid entrance pupil offset: {self.entrance_pupil_offset_mm}mm"
            )

    @property
    def weight_lbs(self) -> float:
        return self.weight_kg * 2.20462

    @property
    def entrance_pupil_offset_cm(self) -> float:
        """USD uses centimeters for transforms."""
        return self.entrance_pupil_offset_mm / 10.0


@dataclass(frozen=True)
class PupilShiftFit:
    """Wolfram-fitted entrance pupil position as function of focus distance."""
    coefficients: dict[str, float]  # {a0, a1, b1}
    r_squared: float

    def evaluate(self, focus_m: float) -> float:
        """Returns entrance_pupil_offset_mm at given focus distance."""
        f = max(0.3, focus_m)
        a0 = self.coefficients.get("a0", 0.0)
        a1 = self.coefficients.get("a1", 0.0)
        b1 = self.coefficients.get("b1", 0.0)
        denom = 1.0 + b1 * f
        if abs(denom) < 1e-8:
            return a0
        return (a0 + a1 * f) / denom


@dataclass(frozen=True)
class SqueezeBreathingCurve:
    """
    Focus-dependent anamorphic squeeze variation ("Mumps").

    Front-anamorphic lenses like Cooke Anamorphic/i only achieve their
    nominal squeeze ratio at infinity focus. As focus distance decreases
    toward MOD (Minimum Object Distance), the effective squeeze drops.

    This creates the characteristic "mumps" effect -- actors' faces appear
    wider at close focus distances.

    Points: ((focus_m, effective_squeeze), ...) sorted by focus_m ascending.
    """
    points: tuple[tuple[float, float], ...]  # ((focus_m, squeeze), ...)
    nominal_squeeze: float = 2.0

    def __post_init__(self):
        sorted_pts = tuple(sorted(self.points, key=lambda p: p[0]))
        object.__setattr__(self, 'points', sorted_pts)
        # Validate squeeze values are physically reasonable
        for focus_m, squeeze in self.points:
            if squeeze < 1.0 or squeeze > self.nominal_squeeze + 0.1:
                raise ValueError(
                    f"Invalid squeeze {squeeze} at {focus_m}m "
                    f"(nominal: {self.nominal_squeeze})"
                )

    def evaluate(self, focus_m: float) -> float:
        """
        Linear interpolation of effective squeeze at given focus distance.
        Returns nominal_squeeze if no curve data or beyond curve range.
        """
        if not self.points:
            return self.nominal_squeeze
        if focus_m <= self.points[0][0]:
            return self.points[0][1]
        if focus_m >= self.points[-1][0]:
            return self.points[-1][1]
        for i in range(len(self.points) - 1):
            f0, s0 = self.points[i]
            f1, s1 = self.points[i + 1]
            if f0 <= focus_m <= f1:
                t = (focus_m - f0) / (f1 - f0) if f1 != f0 else 0
                return s0 + t * (s1 - s0)
        return self.nominal_squeeze


# ════════════════════════════════════════════════════════════
# v4.0 EXTENDED LENS TYPES
# ════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class LensSpec:
    """
    Complete lens specification -- v4.0 with mechanical data.
    BACKWARDS COMPATIBLE: mechanics and squeeze_breathing are Optional
    with sensible defaults so v3.0 JSON files still load.
    """
    # -- v3.0 fields (unchanged) --
    lens_id: str
    manufacturer: str
    series: str
    focal_length_mm: float
    t_stop_min: float
    t_stop_max: float
    iris_blades: int
    close_focus_m: float
    image_circle_mm: float
    squeeze_ratio: float          # Nominal squeeze (1.0 spherical, 2.0 anamorphic)
    distortion: DistortionModel
    breathing: BreathingCurve
    lateral_ca_px_per_mm: float = 0.0
    longitudinal_ca_stops: float = 0.0
    transmission: float = 0.0     # Measured tau; 0 = unknown -> DEFAULT_TRANSMISSION

    # -- v3.0 physical fields (now superseded by MechanicalSpec) --
    weight_kg: float = 0.0
    length_mm: float = 0.0
    front_diameter_mm: float = 0.0

    # -- v4.0 additions --
    mechanics: Optional[MechanicalSpec] = None
    squeeze_breathing: Optional[SqueezeBreathingCurve] = None

    def __post_init__(self):
        if self.focal_length_mm <= 0:
            raise ValueError(f"Invalid focal length: {self.focal_length_mm}mm")
        if self.t_stop_min <= 0 or self.t_stop_max <= self.t_stop_min:
            raise ValueError(f"Invalid T-stop range: {self.t_stop_min}-{self.t_stop_max}")
        if self.squeeze_ratio < 1.0:
            raise ValueError(f"Invalid squeeze ratio: {self.squeeze_ratio}")
        # Backfill v3.0 physical fields from MechanicalSpec if available
        if self.mechanics and self.weight_kg == 0.0:
            object.__setattr__(self, 'weight_kg', self.mechanics.weight_kg)
            object.__setattr__(self, 'length_mm', self.mechanics.length_mm)
            object.__setattr__(self, 'front_diameter_mm', self.mechanics.front_diameter_mm)

    @property
    def is_anamorphic(self) -> bool:
        return self.squeeze_ratio > 1.01

    @property
    def has_mechanics(self) -> bool:
        return self.mechanics is not None

    @property
    def entrance_pupil_offset_mm(self) -> float:
        """Returns entrance pupil offset, or 0 if no mechanical data."""
        return self.mechanics.entrance_pupil_offset_mm if self.mechanics else 0.0

    def effective_squeeze(self, focus_distance_m: float) -> float:
        """
        Dynamic squeeze at given focus distance.
        Returns nominal squeeze_ratio if no breathing curve.
        """
        if self.squeeze_breathing:
            return self.squeeze_breathing.evaluate(focus_distance_m)
        return self.squeeze_ratio


@dataclass(frozen=True)
class LensState:
    """Lens state at a single frame -- v4.0 with dynamic squeeze."""
    spec: LensSpec
    t_stop: float
    focus_distance_m: float

    def __post_init__(self):
        if self.t_stop < self.spec.t_stop_min or self.t_stop > self.spec.t_stop_max:
            raise ValueError(
                f"T-stop {self.t_stop} outside range "
                f"[{self.spec.t_stop_min}, {self.spec.t_stop_max}]"
            )
        if self.focus_distance_m < self.spec.close_focus_m:
            raise ValueError(
                f"Focus {self.focus_distance_m}m below close focus {self.spec.close_focus_m}m"
            )

    @property
    def breathing_shift_pct(self) -> float:
        return self.spec.breathing.evaluate(self.focus_distance_m)

    @property
    def f_number(self) -> float:
        """
        Geometric f-number (focal / entrance-pupil diameter) for DEPTH OF FIELD
        and bokeh size. Derived N = T * sqrt(tau); tau from the spec or the
        heuristic DEFAULT_TRANSMISSION. Exposure uses the T-stop, not this.
        """
        tau = self.spec.transmission or DEFAULT_TRANSMISSION
        return self.t_stop * math.sqrt(tau)

    @property
    def effective_squeeze(self) -> float:
        """Dynamic squeeze ratio at current focus distance (Mumps)."""
        return self.spec.effective_squeeze(self.focus_distance_m)

    @property
    def entrance_pupil_offset_cm(self) -> float:
        """Entrance pupil offset in USD centimeters."""
        return self.spec.entrance_pupil_offset_mm / 10.0

    @property
    def rig_weight_kg(self) -> float:
        """Total lens weight (body weight added at assembly level)."""
        return self.spec.weight_kg

    def to_usd_dict(self) -> dict[str, tuple[str, Any]]:
        """Flat dictionary for USD attribute authoring -- v4.0 extended."""
        prefix = "cinema:lens"
        d = self.spec.distortion
        result = {
            f"{prefix}:manufacturer":        ("String", self.spec.manufacturer),
            f"{prefix}:series":              ("String", self.spec.series),
            f"{prefix}:focalLengthMm":       ("Float",  self.spec.focal_length_mm),
            f"{prefix}:squeezeRatioNominal": ("Float",  self.spec.squeeze_ratio),
            f"{prefix}:squeezeRatioEffective": ("Float", self.effective_squeeze),
            f"{prefix}:tStop":               ("Float",  self.t_stop),
            f"{prefix}:focusDistanceM":      ("Float",  self.focus_distance_m),
            f"{prefix}:irisBlades":          ("Int",    self.spec.iris_blades),
            f"{prefix}:distortion:k1":       ("Float",  d.k1),
            f"{prefix}:distortion:k2":       ("Float",  d.k2),
            f"{prefix}:distortion:k3":       ("Float",  d.k3),
            f"{prefix}:distortion:p1":       ("Float",  d.p1),
            f"{prefix}:distortion:p2":       ("Float",  d.p2),
            f"{prefix}:distortion:sqUniformity": ("Float", d.squeeze_uniformity),
        }
        # v4.0 mechanical attributes
        if self.spec.has_mechanics:
            m = self.spec.mechanics
            result.update({
                f"{prefix}:weightKg":            ("Float", m.weight_kg),
                f"{prefix}:lengthMm":            ("Float", m.length_mm),
                f"{prefix}:frontDiameterMm":     ("Float", m.front_diameter_mm),
                f"{prefix}:entrancePupilOffsetMm": ("Float", m.entrance_pupil_offset_mm),
                f"{prefix}:focusRingRotationDeg":  ("Float", m.focus_ring.rotation_deg),
                f"{prefix}:irisRingRotationDeg":   ("Float", m.iris_ring.rotation_deg),
            })
        return result
