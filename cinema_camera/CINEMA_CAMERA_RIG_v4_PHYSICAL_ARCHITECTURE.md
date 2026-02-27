# Cinema Camera Rig v4.0 — Physical Architecture
## Houdini 21 • USD/Solaris • Karma XPU • CVEX Lens Shaders • CHOPs Biomechanics • Copernicus 2.0

---

## Preamble: v3.0 → v4.0 Thesis

v3.0 established the **Software Architecture**: typed protocols, validated data flow,
registry-based extensibility, standalone optics library, HDA-wrapped Copernicus kernels.

v4.0 adds the **Physical Architecture**. The camera rig stops being a "3D camera" and
becomes a **Virtual Cinematography Simulator** where every compositor, lighter, and layout
artist speaks the exact same language as a physical camera department.

### What v4.0 Adds

| Pillar | Problem v3.0 Doesn't Solve | v4.0 Solution |
|--------|---------------------------|---------------|
| **A. MechanicalSpec** | LensSpec has no physical dimensions | New `MechanicalSpec` dataclass + JSON schema evolution |
| **B. Nodal Parallax** | CG camera pivots at sensor plane | Nested USD Xform hierarchy with entrance pupil offset |
| **C. Operator Biomechanics** | Digital cameras have zero mass | CHOPs spring/lag solver driven by combined rig weight |
| **D. CVEX Lens Shader** | Post-process distortion ruins DOF/mblur | Karma CVEX shader warps rays before scene sampling |
| **E. Pipeline Bridge** | No downstream metadata for comp | Cooke /i + ASWF standard EXR header authoring |
| **F. Dynamic Mumps** | Static squeeze_ratio = 2.0 at all distances | Focus-dependent squeeze curve (SqueezeBreathingCurve) |
| **G. Copernicus 2.0** | Basic grain/flare effects | FFT convolution flares, sensor noise model, STMap AOV |

### Dependency Chain

```
MechanicalSpec (A)
    ├─→ Nodal Parallax (B)     — reads entrance_pupil_offset_mm
    ├─→ Biomechanics (C)       — reads weight_kg, length_mm
    └─→ CVEX Lens Shader (D)   — reads entrance_pupil_offset_mm
Dynamic Mumps (F)
    └─→ CVEX Lens Shader (D)   — reads dynamic squeeze at focus distance
Pipeline Bridge (E)
    └─→ depends on all above being authored to USD
Copernicus 2.0 (G)
    └─→ reads MechanicalSpec for FFT flare geometry
```

---

## Claude Code Agent Team — MOE Role Definitions

### Team Structure

```
┌─────────────────────────────────────────────────────────┐
│                    ORCHESTRATOR                          │
│  Owns: task sequencing, dependency resolution,          │
│        integration testing, v3.0 compatibility          │
├─────────────┬──────────────┬──────────────┬─────────────┤
│  AGENT α    │  AGENT β     │  AGENT γ     │  AGENT δ    │
│  PROTOCOLS  │  USD/SOLARIS │  VEX/CVEX    │  CHOPs/COP  │
│             │              │              │             │
│  Python     │  USD Schema  │  VEX Library │  CHOPs Net  │
│  Dataclass  │  Xform Hier  │  CVEX Shader │  Copernicus │
│  Registry   │  EXR Metadata│  STMap Gen   │  Biomech    │
│  JSON Schema│  Render Prod │  Distortion  │  Flare FFT  │
└─────────────┴──────────────┴──────────────┴─────────────┘
```

### Role Specifications

**ORCHESTRATOR** — Integration & Sequencing
- Resolves dependency chain: A → B,C,D → E → G
- Runs v3.0 regression suite after each agent completes
- Validates cross-agent interface contracts
- Owns final integration HDA wiring

**AGENT α (Protocols)** — Python Type System
- Extends `protocols.py` with new dataclasses
- Evolves JSON schema for mechanical data ingestion
- Updates registry for new provider capabilities
- Writes protocol conformance tests
- **Expertise:** Python 3.10+ dataclasses, frozen validation, Protocol typing

**AGENT β (USD/Solaris)** — Scene Description & Metadata
- Refactors `usd_builder.py` → nested Xform rig hierarchy
- Authors Cooke /i + ASWF EXR metadata on RenderProduct
- Designs USD attribute namespace evolution (`cinema:rig:*`)
- **Expertise:** pxr USD API, UsdGeom, UsdRender, Sdf, composition arcs

**AGENT γ (VEX/CVEX)** — Optical Engine & Render-Time Shaders
- Extends `libcinema_optics.h` with dynamic squeeze functions
- Implements Karma CVEX lens shader (ray-warping, not post-process)
- Builds STMap AOV generator using existing library
- **Expertise:** VEX/CVEX, Karma XPU shader pipeline, HDA VEX generators

**AGENT δ (CHOPs/Copernicus)** — Dynamics & Post-Processing
- Builds operator biomechanics CHOPs constraint layer
- Upgrades Copernicus effects: FFT flare, sensor noise, STMap output
- **Expertise:** CHOPs spring/lag solvers, Copernicus GPU kernels, FFT convolution

---

## PILLAR A: MechanicalSpec Protocol

**Owner:** AGENT α (Protocols)
**Depends on:** Nothing (foundation layer)
**Consumed by:** Pillars B, C, D, G

### A.1 New Dataclasses

```python
# File: python/cinema_camera/protocols.py  (ADDITIONS to v3.0)
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
            raise ValueError(f"Invalid gear rotation: {self.rotation_deg}°")
        if self.gear_teeth <= 0:
            raise ValueError(f"Invalid gear tooth count: {self.gear_teeth}")
        if self.gear_module <= 0:
            raise ValueError(f"Invalid gear module: {self.gear_module}")

    @property
    def pitch_circle_diameter_mm(self) -> float:
        """PCD = module × teeth. Used for follow-focus motor compatibility."""
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
```

### A.2 SqueezeBreathingCurve (Dynamic Mumps — Pillar F)

```python
@dataclass(frozen=True)
class SqueezeBreathingCurve:
    """
    Focus-dependent anamorphic squeeze variation ("Mumps").

    Front-anamorphic lenses like Cooke Anamorphic/i only achieve their
    nominal squeeze ratio at infinity focus. As focus distance decreases
    toward MOD (Minimum Object Distance), the effective squeeze drops.

    This creates the characteristic "mumps" effect — actors' faces appear
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
```

### A.3 Extended LensSpec (v4.0)

```python
@dataclass(frozen=True)
class LensSpec:
    """
    Complete lens specification — v4.0 with mechanical data.
    BACKWARDS COMPATIBLE: mechanics and squeeze_breathing are Optional
    with sensible defaults so v3.0 JSON files still load.
    """
    # ── v3.0 fields (unchanged) ──────────────────────────
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

    # ── v3.0 physical fields (now superseded by MechanicalSpec) ──
    weight_kg: float = 0.0
    length_mm: float = 0.0
    front_diameter_mm: float = 0.0

    # ── v4.0 additions ───────────────────────────────────
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
```

### A.4 Extended LensState (v4.0)

```python
@dataclass(frozen=True)
class LensState:
    """Lens state at a single frame — v4.0 with dynamic squeeze."""
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
        """Flat dictionary for USD attribute authoring — v4.0 extended."""
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
```

### A.5 Evolved JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "cinema_lens_v4.schema.json",
  "title": "Cinema Lens Specification v4.0",
  "type": "object",
  "required": [
    "lens_id", "manufacturer", "series", "focal_length_mm",
    "t_stop_range", "iris_blades", "close_focus_m",
    "image_circle_mm", "squeeze_ratio"
  ],
  "properties": {
    "lens_id": { "type": "string", "pattern": "^[a-z0-9_]+$" },
    "manufacturer": { "type": "string" },
    "series": { "type": "string" },
    "focal_length_mm": { "type": "number", "exclusiveMinimum": 0 },
    "t_stop_range": {
      "type": "array", "items": { "type": "number" },
      "minItems": 2, "maxItems": 2
    },
    "iris_blades": { "type": "integer", "minimum": 3 },
    "close_focus_m": { "type": "number", "exclusiveMinimum": 0 },
    "image_circle_mm": { "type": "number", "exclusiveMinimum": 0 },
    "squeeze_ratio": { "type": "number", "minimum": 1.0 },
    "mechanics": {
      "type": "object",
      "required": ["weight_kg", "length_mm", "front_diameter_mm", "entrance_pupil_offset_mm"],
      "properties": {
        "weight_kg": { "type": "number", "exclusiveMinimum": 0 },
        "length_mm": { "type": "number", "exclusiveMinimum": 0 },
        "front_diameter_mm": { "type": "number", "exclusiveMinimum": 0 },
        "filter_thread": { "type": "string", "pattern": "^M[0-9]+x[0-9.]+" },
        "focus_ring": {
          "type": "object",
          "required": ["rotation_deg", "gear_teeth"],
          "properties": {
            "rotation_deg": { "type": "number", "exclusiveMinimum": 0, "maximum": 360 },
            "gear_teeth": { "type": "integer", "minimum": 1 },
            "gear_module": { "type": "number", "default": 0.8 }
          }
        },
        "iris_ring": {
          "type": "object",
          "required": ["rotation_deg", "gear_teeth"],
          "properties": {
            "rotation_deg": { "type": "number", "exclusiveMinimum": 0, "maximum": 360 },
            "gear_teeth": { "type": "integer", "minimum": 1 },
            "gear_module": { "type": "number", "default": 0.8 }
          }
        },
        "entrance_pupil_offset_mm": { "type": "number", "minimum": 0 }
      }
    },
    "squeeze_breathing": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["focus_m", "effective_squeeze"],
        "properties": {
          "focus_m": { "oneOf": [
            { "type": "number", "exclusiveMinimum": 0 },
            { "type": "string", "enum": ["infinity"] }
          ]},
          "effective_squeeze": { "type": "number", "minimum": 1.0 }
        }
      }
    },
    "distortion": {
      "type": "object",
      "properties": {
        "k1": { "type": "number" },
        "k2": { "type": "number" },
        "k3": { "type": "number" },
        "p1": { "type": "number" },
        "p2": { "type": "number" },
        "squeeze_uniformity": { "type": "number", "minimum": 0.8, "maximum": 1.0 }
      }
    },
    "breathing": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["focus_m", "fov_shift_pct"],
        "properties": {
          "focus_m": { "oneOf": [
            { "type": "number", "exclusiveMinimum": 0 },
            { "type": "string", "enum": ["infinity"] }
          ]},
          "fov_shift_pct": { "type": "number" }
        }
      }
    }
  }
}
```

### A.6 Example: Cooke Anamorphic/i 50mm (Complete v4.0 JSON)

```json
{
  "lens_id": "cooke_ana_i_s35_50mm",
  "manufacturer": "Cooke",
  "series": "Anamorphic/i S35",
  "focal_length_mm": 50.0,
  "t_stop_range": [2.3, 22.0],
  "iris_blades": 11,
  "close_focus_m": 0.85,
  "image_circle_mm": 31.1,
  "squeeze_ratio": 2.0,
  "mechanics": {
    "weight_kg": 3.6,
    "length_mm": 205.0,
    "front_diameter_mm": 110.0,
    "filter_thread": "M105x0.75",
    "focus_ring": {
      "rotation_deg": 300.0,
      "gear_teeth": 140,
      "gear_module": 0.8
    },
    "iris_ring": {
      "rotation_deg": 90.0,
      "gear_teeth": 134,
      "gear_module": 0.8
    },
    "entrance_pupil_offset_mm": 125.0
  },
  "squeeze_breathing": [
    { "focus_m": 0.85, "effective_squeeze": 1.85 },
    { "focus_m": 1.5,  "effective_squeeze": 1.92 },
    { "focus_m": 3.0,  "effective_squeeze": 1.97 },
    { "focus_m": 10.0, "effective_squeeze": 1.99 },
    { "focus_m": "infinity", "effective_squeeze": 2.0 }
  ],
  "distortion": {
    "k1": -0.015,
    "k2": 0.002,
    "squeeze_uniformity": 0.94
  },
  "breathing": [
    { "focus_m": 0.85, "fov_shift_pct": 3.2 },
    { "focus_m": 2.0,  "fov_shift_pct": 1.1 },
    { "focus_m": "infinity", "fov_shift_pct": 0.0 }
  ]
}
```

### A.7 JSON Parser Update (from_json Factory)

```python
# File: python/cinema_camera/lenses/cooke_anamorphic.py (UPDATED from_json)

@classmethod
def from_json(cls, json_path: Path, node: Optional[hou.Node] = None) -> CookeAnamorphicLens:
    """Factory: load from v4.0 JSON with full validation. Backwards-compatible with v3.0 JSON."""
    with open(json_path, "r") as f:
        data = json.load(f)

    # ── Parse breathing curve (v3.0) ─────────────────────
    breathing_points = []
    for bp in data.get("breathing", []):
        focus = bp["focus_m"]
        if isinstance(focus, str) and focus.lower() == "infinity":
            focus = 1e10
        breathing_points.append((float(focus), bp["fov_shift_pct"]))

    # ── Parse distortion (v3.0) ──────────────────────────
    dist_data = data.get("distortion", {})

    # ── Parse mechanical spec (v4.0 — optional) ─────────
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

    # ── Parse squeeze breathing (v4.0 — optional) ───────
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
        # v4.0: MechanicalSpec handles these; backfill via __post_init__
        mechanics=mechanics,
        squeeze_breathing=squeeze_breathing,
    )

    return cls(spec, node)
```

### A.8 Acceptance Criteria

```
AGENT α DELIVERABLES:
  [ ] GearRingSpec frozen dataclass with validation + pitch_circle_diameter_mm
  [ ] MechanicalSpec frozen dataclass with entrance_pupil_offset_cm property
  [ ] SqueezeBreathingCurve frozen dataclass with evaluate() interpolation
  [ ] LensSpec extended with mechanics + squeeze_breathing (Optional, backwards-compat)
  [ ] LensState extended with effective_squeeze + entrance_pupil_offset_cm
  [ ] to_usd_dict() includes all v4.0 mechanical attributes
  [ ] JSON schema v4.0 validates both v3.0 and v4.0 JSON files
  [ ] from_json() parses v3.0 JSON without error (mechanics=None)
  [ ] from_json() parses v4.0 JSON with full mechanical + squeeze data
  [ ] Cooke 50mm and 300mm JSON data files created and validated

TESTS:
  [ ] test_mechanical_spec_validation — rejects weight_kg=0, negative offsets
  [ ] test_squeeze_breathing_interpolation — exact values at MOD, mid, infinity
  [ ] test_lens_spec_backwards_compat — v3.0 JSON loads into v4.0 LensSpec
  [ ] test_effective_squeeze_at_focus — 50mm: 1.85 at 0.85m, 2.0 at infinity
  [ ] test_gear_ring_pitch_circle — 140 teeth × 0.8 module = 112mm PCD
```

---

## PILLAR B: Nodal Parallax (USD Transform Hierarchy)

**Owner:** AGENT β (USD/Solaris)
**Depends on:** Pillar A (MechanicalSpec)
**Consumed by:** Pillar D (CVEX shader reads entrance pupil), Pillar E (metadata)

### B.1 The Problem

A CG camera rotates around its sensor plane origin. A physical camera on a tripod
rotates around the fluid head pivot point, while the entrance pupil (nodal point) sits
far ahead in the lens barrel. This mismatch causes CG elements to "slip" against
live-action plates during pan/tilt operations or heavy focus pulls.

### B.2 USD Xform Hierarchy

```
/World/CameraRig                              ← RIG ROOT (user transforms this)
  └─/World/CameraRig/FluidHead                ← PIVOT POINT (pan/tilt origin)
      ├─ xformOp:rotateXYZ = (tilt, pan, 0)
      │
      └─/World/CameraRig/FluidHead/Body       ← CAMERA BODY (sensor plane)
          ├─ xformOp:translate = (0, body_offset_y, -sensor_offset_z)
          │   body_offset_y: height from head baseplate to sensor center
          │   sensor_offset_z: distance from mounting face to sensor plane
          │
          └─/World/CameraRig/FluidHead/Body/Sensor  ← UsdGeom.Camera
              ├─ horizontalAperture, verticalAperture, focalLength ...
              ├─ cinema:rig:entrancePupilOffsetCm  (authored from MechanicalSpec)
              ├─ cinema:rig:combinedWeightKg       (body + lens)
              ├─ cinema:rig:fluidHeadModel         (e.g. "OConnor 2575")
              │
              └─/World/CameraRig/FluidHead/Body/Sensor/EntrancePupil  ← NODAL POINT
                  ├─ xformOp:translate = (0, 0, entrance_pupil_offset_cm)
                  └─ purpose = "guide"  (viewport visualization only)
```

### B.3 Refactored USD Builder

```python
# File: python/cinema_camera/usd_builder.py (v4.0 — REPLACES v3.0 build_usd_camera)

from __future__ import annotations
from pxr import Usd, UsdGeom, UsdRender, Sdf, Gf
from .protocols import CameraState, LensState, OpticalResult


# ── Attribute type mapping ────────────────────────────────
_USD_TYPE_MAP = {
    "String": Sdf.ValueTypeNames.String,
    "Float":  Sdf.ValueTypeNames.Float,
    "Int":    Sdf.ValueTypeNames.Int,
    "Bool":   Sdf.ValueTypeNames.Bool,
}


def _author_attributes(prim: Usd.Prim, attrs: dict[str, tuple[str, object]]) -> None:
    """Author a dict of {name: (type_str, value)} onto a USD prim."""
    for attr_name, (type_str, value) in attrs.items():
        sdf_type = _USD_TYPE_MAP.get(type_str)
        if sdf_type is None:
            continue
        attr = prim.GetAttribute(attr_name)
        if not attr:
            attr = prim.CreateAttribute(attr_name, sdf_type)
        attr.Set(value)


# ── Body offset constants (mm → cm) ─────────────────────
# Distance from tripod quick-release plate to sensor center
_BODY_OFFSETS_CM = {
    "ARRI ALEXA 35":   {"y": 5.0, "z": -8.0},   # 80mm mount-face to sensor
    "RED KOMODO":      {"y": 3.5, "z": -5.0},
    "SONY VENICE 2":   {"y": 5.5, "z": -9.0},
}
_DEFAULT_BODY_OFFSET = {"y": 4.0, "z": -7.0}


def build_usd_camera_rig(
    stage: Usd.Stage,
    rig_path: str,
    camera_state: CameraState,
    lens_state: LensState,
    optical_result: OpticalResult,
    fluid_head_model: str = "OConnor 2575",
) -> UsdGeom.Camera:
    """
    Build a physically-nested USD camera rig from typed state objects.

    Hierarchy:
      {rig_path}/FluidHead/Body/Sensor/EntrancePupil

    The FluidHead prim is the pan/tilt pivot.
    The Sensor prim is the UsdGeom.Camera.
    The EntrancePupil is a guide Xform for parallax visualization.

    Returns the UsdGeom.Camera (Sensor prim).
    """

    # ── 1. Rig Root ──────────────────────────────────────
    rig_root = UsdGeom.Xform.Define(stage, rig_path)

    # ── 2. Fluid Head (Pan/Tilt Pivot) ───────────────────
    head_path = f"{rig_path}/FluidHead"
    head = UsdGeom.Xform.Define(stage, head_path)
    head.GetPrim().CreateAttribute(
        "cinema:rig:fluidHeadModel", Sdf.ValueTypeNames.String
    ).Set(fluid_head_model)

    # ── 3. Camera Body (Offset from Head) ────────────────
    body_path = f"{head_path}/Body"
    body = UsdGeom.Xform.Define(stage, body_path)
    offsets = _BODY_OFFSETS_CM.get(camera_state.model, _DEFAULT_BODY_OFFSET)
    UsdGeom.XformCommonAPI(body).SetTranslate(
        Gf.Vec3d(0, offsets["y"], offsets["z"])
    )

    # ── 4. Sensor (UsdGeom.Camera) ───────────────────────
    sensor_path = f"{body_path}/Sensor"
    camera = UsdGeom.Camera.Define(stage, sensor_path)

    # Core USD camera attributes
    camera.CreateProjectionAttr().Set(UsdGeom.Tokens.perspective)
    camera.CreateHorizontalApertureAttr().Set(camera_state.active_width_mm)
    camera.CreateVerticalApertureAttr().Set(camera_state.active_height_mm)
    camera.CreateFocalLengthAttr().Set(lens_state.spec.focal_length_mm)
    camera.CreateFocusDistanceAttr().Set(lens_state.focus_distance_m * 100)  # m → cm
    camera.CreateFStopAttr().Set(lens_state.t_stop)
    camera.CreateClippingRangeAttr().Set(Gf.Vec2f(0.01, 100000.0))

    # Custom cinema attributes on camera prim
    prim = camera.GetPrim()
    _author_attributes(prim, camera_state.to_usd_dict())
    _author_attributes(prim, lens_state.to_usd_dict())
    _author_attributes(prim, {
        "cinema:optics:hfovDeg":     ("Float", optical_result.hfov_deg),
        "cinema:optics:vfovDeg":     ("Float", optical_result.vfov_deg),
        "cinema:optics:dofNearM":    ("Float", optical_result.dof_near_m),
        "cinema:optics:dofFarM":     ("Float", optical_result.dof_far_m),
        "cinema:optics:hyperfocalM": ("Float", optical_result.hyperfocal_m),
        "cinema:optics:cocMm":       ("Float", optical_result.coc_mm),
    })

    # Rig-level metadata on camera prim
    combined_weight = lens_state.rig_weight_kg
    # If camera body weight is known (could be added to CameraState in future)
    _author_attributes(prim, {
        "cinema:rig:entrancePupilOffsetCm": ("Float", lens_state.entrance_pupil_offset_cm),
        "cinema:rig:combinedWeightKg":      ("Float", combined_weight),
        "cinema:rig:effectiveSqueeze":       ("Float", lens_state.effective_squeeze),
    })

    # ── 5. Entrance Pupil (Guide Visualization) ──────────
    pupil_path = f"{sensor_path}/EntrancePupil"
    pupil = UsdGeom.Xform.Define(stage, pupil_path)
    UsdGeom.XformCommonAPI(pupil).SetTranslate(
        Gf.Vec3d(0, 0, lens_state.entrance_pupil_offset_cm)
    )
    pupil.GetPrim().CreateAttribute(
        "purpose", Sdf.ValueTypeNames.Token
    ).Set("guide")

    return camera


# ── Backwards-compatible wrapper ─────────────────────────
def build_usd_camera(
    stage: Usd.Stage,
    camera_path: str,
    camera_state: CameraState,
    lens_state: LensState,
    optical_result: OpticalResult,
) -> UsdGeom.Camera:
    """
    v3.0 compatible entry point. Delegates to build_usd_camera_rig
    with the camera_path as rig root. Returns UsdGeom.Camera.
    """
    return build_usd_camera_rig(
        stage, camera_path, camera_state, lens_state, optical_result
    )
```

### B.4 Acceptance Criteria

```
AGENT β DELIVERABLES (Pillar B):
  [ ] USD Xform hierarchy: FluidHead → Body → Sensor → EntrancePupil
  [ ] FluidHead is the pan/tilt pivot (pan/tilt keys applied here)
  [ ] Body offset from _BODY_OFFSETS_CM lookup (per-camera model)
  [ ] cinema:rig:entrancePupilOffsetCm authored from MechanicalSpec
  [ ] cinema:rig:combinedWeightKg authored for biomechanics CHOPs
  [ ] cinema:rig:effectiveSqueeze authored for dynamic mumps
  [ ] EntrancePupil Xform has purpose="guide" (viewport only)
  [ ] build_usd_camera() backwards-compatible wrapper preserved
  [ ] usdchecker validates generated stage with no errors

TESTS:
  [ ] test_rig_hierarchy_structure — validate all prim paths exist
  [ ] test_entrance_pupil_offset — 50mm: 12.5cm, 300mm: different value
  [ ] test_body_offset_per_model — ALEXA 35 vs RED KOMODO offsets differ
  [ ] test_backwards_compat — build_usd_camera() still works
```

---

## PILLAR C: Operator Biomechanics Engine (CHOPs)

**Owner:** AGENT δ (CHOPs/Copernicus)
**Depends on:** Pillar A (weight_kg), Pillar B (USD rig hierarchy)

### C.1 The Problem

A 50mm Cooke at 3.6kg on an Alexa 35 (3.9kg) = 7.5kg rig. A 300mm at 9.4kg = 13.3kg.
The 13.3kg rig has massive rotational inertia — pans ease in slowly and coast to a stop.
The 7.5kg rig is snappy and jittery. Digital cameras have none of this.

### C.2 CHOPs Constraint Architecture

```
cinema::chops_biomechanics::1.0  [CHOP Network inside top-level HDA]

    ┌───────────────┐
    │ Input: Raw     │ ← Pan/Tilt/Roll animation channels
    │ Camera Motion  │   from animator or mocap
    └───────┬───────┘
            │
    ┌───────▼───────────────┐
    │ Inertia Calculator    │ ← Reads cinema:rig:combinedWeightKg
    │                       │   from USD attribute via spare parm
    │ moment_of_inertia =   │
    │   weight_kg *         │
    │   (arm_length_cm)^2   │   arm_length = sensor_offset + pupil_offset
    └───────┬───────────────┘
            │
    ┌───────▼───────────────┐
    │ CHOP Spring Solver    │ ← spring_constant = fn(head_friction)
    │                       │   damping = fn(moment_of_inertia)
    │ Heavy rig:            │   = high damping, slow response
    │   spring_k = 8.0      │   
    │   damping = 0.85      │   
    │ Light rig:            │   = low damping, snappy
    │   spring_k = 15.0     │   
    │   damping = 0.4       │   
    └───────┬───────────────┘
            │
    ┌───────▼───────────────┐
    │ CHOP Lag Solver       │ ← Simulates operator reaction time
    │                       │   lag_frames = weight_kg * 0.3
    │ Adds onset delay      │   
    └───────┬───────────────┘
            │
    ┌───────▼───────────────┐
    │ High-Freq Noise       │ ← Handheld camera shake
    │ (Optional)            │   amplitude = fn(1/weight_kg)
    │                       │   Heavy rig = less shake
    │                       │   Light rig = more shake
    └───────┬───────────────┘
            │
    ┌───────▼───────┐
    │ Output: Phys   │ → Drives FluidHead xformOp:rotateXYZ
    │ Camera Motion  │   via CHOP export or LOP wrangle
    └───────────────┘
```

### C.3 Biomechanics Parameter Derivation

```python
# File: python/cinema_camera/biomechanics.py
"""
Operator biomechanics parameter derivation.
Converts physical rig properties into CHOPs solver parameters.
"""

from __future__ import annotations
from dataclasses import dataclass
from .protocols import CameraState, LensState


@dataclass(frozen=True)
class BiomechanicsParams:
    """CHOPs solver parameters derived from physical rig properties."""
    # Spring solver
    spring_constant: float      # Higher = snappier response
    damping_ratio: float        # 0-1: 0=undamped, 1=critically damped

    # Lag solver
    lag_frames: float           # Operator reaction delay

    # Noise (handheld)
    handheld_amplitude_deg: float  # Peak random rotation
    handheld_frequency_hz: float   # Dominant shake frequency

    # Derived
    moment_of_inertia: float    # kg·cm² (for reference)
    combined_weight_kg: float


def derive_biomechanics(
    camera_state: CameraState,
    lens_state: LensState,
    body_weight_kg: float = 3.9,             # ARRI Alexa 35 body
    sensor_to_mounting_face_cm: float = 8.0,  # Distance sensor to mount
    fluid_head_damping_base: float = 0.6,     # OConnor 2575 baseline
) -> BiomechanicsParams:
    """
    Derive CHOPs parameters from physical rig properties.

    The key insight: rotational inertia scales with mass × distance².
    A heavy lens pushes the center of mass forward, increasing the
    moment arm and dramatically increasing rotational inertia.
    """
    lens_weight = lens_state.rig_weight_kg
    combined_weight = body_weight_kg + lens_weight

    # Moment arm: distance from tripod pivot to center of mass
    # Approximate: sensor offset + half lens length
    lens_half_length_cm = 0.0
    if lens_state.spec.has_mechanics:
        lens_half_length_cm = lens_state.spec.mechanics.length_mm / 20.0  # mm→cm/2

    moment_arm_cm = sensor_to_mounting_face_cm + lens_half_length_cm
    moment_of_inertia = combined_weight * (moment_arm_cm ** 2)

    # Spring constant: inversely proportional to inertia
    # Calibrated so 7kg rig ≈ 15.0, 15kg rig ≈ 8.0
    spring_k = max(5.0, 25.0 - moment_of_inertia * 0.012)

    # Damping: heavier rigs are more critically damped
    damping = min(0.95, fluid_head_damping_base + combined_weight * 0.025)

    # Lag: heavier rigs have slower operator response
    lag_frames = combined_weight * 0.3

    # Handheld shake: inversely proportional to weight
    handheld_amp = max(0.05, 1.5 / combined_weight)
    handheld_freq = max(2.0, 8.0 - combined_weight * 0.3)

    return BiomechanicsParams(
        spring_constant=spring_k,
        damping_ratio=damping,
        lag_frames=lag_frames,
        handheld_amplitude_deg=handheld_amp,
        handheld_frequency_hz=handheld_freq,
        moment_of_inertia=moment_of_inertia,
        combined_weight_kg=combined_weight,
    )
```

### C.4 Acceptance Criteria

```
AGENT δ DELIVERABLES (Pillar C):
  [ ] BiomechanicsParams frozen dataclass with all solver params
  [ ] derive_biomechanics() function with calibrated constants
  [ ] CHOPs network HDA: cinema::chops_biomechanics::1.0
  [ ] Spring solver configured from BiomechanicsParams
  [ ] Lag solver with frame-based delay
  [ ] Handheld noise generator (optional toggle)
  [ ] CHOP export targets FluidHead rotateXYZ
  [ ] Weight-driven parameter lookup from USD attributes

TESTS:
  [ ] test_biomechanics_50mm — 7.5kg rig: spring_k≈15, damping≈0.5
  [ ] test_biomechanics_300mm — 13.3kg rig: spring_k≈8, damping≈0.9
  [ ] test_heavy_rig_slower_pan — animate 90° pan, heavy rig takes longer
  [ ] test_handheld_amplitude — heavy rig less shake, light rig more
```

---

## PILLAR D: Karma CVEX Lens Shader

**Owner:** AGENT γ (VEX/CVEX)
**Depends on:** Pillar A (MechanicalSpec for pupil offset), Pillar F (dynamic squeeze)

### D.1 The Problem

Applying distortion in Copernicus (post-process) stretches pixels. This destroys
depth-of-field accuracy, motion blur fidelity, and refractive caustics. The correct
approach is to warp the camera rays *before* they sample the scene.

### D.2 libcinema_optics.h Extensions (Dynamic Squeeze)

```c
// File: vex/libcinema_optics.h (v4.0 ADDITIONS)

// ── Dynamic Squeeze (Mumps) ────────────────────────────

// PERF: O(n) where n = curve points | <0.001ms | Memory: negligible
float co_evaluate_squeeze_curve(
    float focus_m;
    float curve_focus[];       // Sorted focus distances (m)
    float curve_squeeze[];     // Corresponding squeeze values
    float nominal_squeeze      // Fallback if arrays empty
) {
    int n = len(curve_focus);
    if (n == 0) return nominal_squeeze;
    if (n != len(curve_squeeze)) return nominal_squeeze;  // guard

    if (focus_m <= curve_focus[0]) return curve_squeeze[0];
    if (focus_m >= curve_focus[n-1]) return curve_squeeze[n-1];

    for (int i = 0; i < n - 1; i++) {
        if (curve_focus[i] <= focus_m && focus_m <= curve_focus[i+1]) {
            float t = (focus_m - curve_focus[i]) /
                      (curve_focus[i+1] - curve_focus[i]);
            return lerp(curve_squeeze[i], curve_squeeze[i+1], t);
        }
    }
    return nominal_squeeze;
}


// ── Anamorphic Distortion with Dynamic Squeeze ─────────

// PERF: O(1) per pixel | ~15ms @ 4K | Memory: negligible
vector2 co_apply_anamorphic_distortion(
    vector2 uv_centered;
    CO_DistortionCoeffs coeffs;
    float effective_squeeze     // Dynamic squeeze at current focus distance
) {
    float x = uv_centered.x;
    float y = uv_centered.y;

    float r2 = x*x + y*y;
    float r4 = r2 * r2;
    float r6 = r4 * r2;

    // Radial distortion (Brown-Conrady)
    float radial = 1.0 + coeffs.k1*r2 + coeffs.k2*r4 + coeffs.k3*r6;

    // Tangential
    float dx = 2.0*coeffs.p1*x*y + coeffs.p2*(r2 + 2.0*x*x);
    float dy = coeffs.p1*(r2 + 2.0*y*y) + 2.0*coeffs.p2*x*y;

    // Anamorphic squeeze non-uniformity (across frame)
    float sq_var = lerp(1.0, coeffs.squeeze_uniformity, r2);

    // Dynamic squeeze applied to X axis
    // Nominal 2.0x → effective 1.85x at MOD for front-anamorphic
    float distorted_x = (x * radial + dx) * effective_squeeze;
    float distorted_y = (y * radial + dy) * sq_var;

    return set(distorted_x, distorted_y);
}
```

### D.3 Karma CVEX Lens Shader

```c
// File: vex/karma_cinema_lens.vfl
// ═══════════════════════════════════════════════════════════
// KARMA CVEX LENS SHADER — Cinema Camera Rig v4.0
//
// Warps render rays BEFORE scene sampling.
// This preserves DOF, motion blur, and refraction fidelity.
//
// Compiles to: cvex_cinema_lens.vex
// Usage: Assign as lens shader on Karma render settings
//
// Parameters read from USD camera prim attributes at render time.
// ═══════════════════════════════════════════════════════════

#include <libcinema_optics.h>

cvex cinema_lens_shader(
    // ── Lens parameters (driven from USD attributes) ────
    float focal_length_mm = 50.0;
    float effective_squeeze = 2.0;         // cinema:rig:effectiveSqueeze
    float entrance_pupil_offset_cm = 12.5; // cinema:rig:entrancePupilOffsetCm
    float sensor_width_mm = 27.99;         // horizontalAperture
    float sensor_height_mm = 19.22;        // verticalAperture

    // Distortion coefficients (from cinema:lens:distortion:*)
    float dist_k1 = 0.0;
    float dist_k2 = 0.0;
    float dist_k3 = 0.0;
    float dist_p1 = 0.0;
    float dist_p2 = 0.0;
    float dist_sq_uniformity = 1.0;

    // Enable/disable controls
    int enable_distortion = 1;
    int enable_squeeze = 1;
    int enable_pupil_offset = 1;

    // ── Standard CVEX lens inputs ───────────────────────
    float x = 0.0;     // Screen-space X (-1 to 1)
    float y = 0.0;     // Screen-space Y (-1 to 1)
    float Time = 0.0;
    float sx = 0.0;    // Sub-pixel jitter X
    float sy = 0.0;    // Sub-pixel jitter Y

    // ── Standard CVEX lens outputs ──────────────────────
    export vector P = {0, 0, 0};    // Ray origin (camera space)
    export vector I = {0, 0, 1};    // Ray direction (camera space)
    export int valid = 1;           // 1 = valid ray, 0 = discard
) {
    // ── Apply sub-pixel jitter ──────────────────────────
    float jx = x + sx;
    float jy = y + sy;

    // ── Apply optical distortion to screen coordinates ──
    vector2 uv = set(jx, jy);

    if (enable_distortion) {
        CO_DistortionCoeffs coeffs;
        coeffs.k1 = dist_k1;
        coeffs.k2 = dist_k2;
        coeffs.k3 = dist_k3;
        coeffs.p1 = dist_p1;
        coeffs.p2 = dist_p2;
        coeffs.squeeze_uniformity = dist_sq_uniformity;

        if (enable_squeeze && effective_squeeze > 1.01) {
            // Dynamic anamorphic distortion with focus-dependent squeeze
            uv = co_apply_anamorphic_distortion(uv, coeffs, effective_squeeze);
        } else {
            // Standard spherical distortion
            uv = co_apply_distortion(uv, coeffs);
        }
    } else if (enable_squeeze && effective_squeeze > 1.01) {
        // Squeeze only, no distortion
        uv.x *= effective_squeeze;
    }

    // ── Convert screen UV to camera-space ray direction ─
    // Map [-1,1] screen coords to sensor plane coordinates
    float half_w = sensor_width_mm * 0.5;
    float half_h = sensor_height_mm * 0.5;

    float ray_x = uv.x * half_w;
    float ray_y = uv.y * half_h;
    float ray_z = focal_length_mm;

    I = normalize(set(ray_x, ray_y, ray_z));

    // ── Ray origin at entrance pupil ────────────────────
    // Physical rays originate at the nodal point, not sensor plane
    if (enable_pupil_offset) {
        // Entrance pupil is FORWARD from sensor (positive Z in camera space)
        // Convert cm to Houdini scene units (cm default in USD)
        P = set(0, 0, entrance_pupil_offset_cm);
    } else {
        P = set(0, 0, 0);
    }

    valid = 1;
}
```

### D.4 Shader Parameter Binding (LOP Python)

```python
# File: python/cinema_camera/karma_lens_shader.py
"""
Binds Karma CVEX lens shader parameters to USD camera attributes.
Runs inside the cinema::camera_rig::2.0 LOP HDA.
"""

from __future__ import annotations
from pxr import Usd, UsdShade, Sdf
from .protocols import LensState, CameraState, OpticalResult


def bind_lens_shader(
    stage: Usd.Stage,
    camera_path: str,
    camera_state: CameraState,
    lens_state: LensState,
) -> None:
    """
    Create and bind Karma CVEX lens shader to the camera prim.

    The shader reads attributes directly from the camera prim,
    so parameters are automatically time-sampled when animated.
    """
    shader_path = f"{camera_path}/CinemaLensShader"
    shader = UsdShade.Shader.Define(stage, shader_path)

    # Shader ID for Karma CVEX
    shader.CreateIdAttr("karma:cvex:cinema_lens_shader")

    # ── Bind lens parameters ─────────────────────────────
    shader.CreateInput("focal_length_mm", Sdf.ValueTypeNames.Float).Set(
        lens_state.spec.focal_length_mm
    )
    shader.CreateInput("effective_squeeze", Sdf.ValueTypeNames.Float).Set(
        lens_state.effective_squeeze
    )
    shader.CreateInput("entrance_pupil_offset_cm", Sdf.ValueTypeNames.Float).Set(
        lens_state.entrance_pupil_offset_cm
    )
    shader.CreateInput("sensor_width_mm", Sdf.ValueTypeNames.Float).Set(
        camera_state.active_width_mm
    )
    shader.CreateInput("sensor_height_mm", Sdf.ValueTypeNames.Float).Set(
        camera_state.active_height_mm
    )

    # Distortion coefficients
    d = lens_state.spec.distortion
    shader.CreateInput("dist_k1", Sdf.ValueTypeNames.Float).Set(d.k1)
    shader.CreateInput("dist_k2", Sdf.ValueTypeNames.Float).Set(d.k2)
    shader.CreateInput("dist_k3", Sdf.ValueTypeNames.Float).Set(d.k3)
    shader.CreateInput("dist_p1", Sdf.ValueTypeNames.Float).Set(d.p1)
    shader.CreateInput("dist_p2", Sdf.ValueTypeNames.Float).Set(d.p2)
    shader.CreateInput("dist_sq_uniformity", Sdf.ValueTypeNames.Float).Set(
        d.squeeze_uniformity
    )

    # ── Bind shader to camera ────────────────────────────
    camera_prim = stage.GetPrimAtPath(camera_path)
    if camera_prim:
        # Karma-specific lens shader binding
        camera_prim.CreateAttribute(
            "karma:lens:shader", Sdf.ValueTypeNames.String
        ).Set(shader_path)
```

### D.5 Acceptance Criteria

```
AGENT γ DELIVERABLES (Pillar D):
  [ ] co_evaluate_squeeze_curve() in libcinema_optics.h
  [ ] co_apply_anamorphic_distortion() with dynamic squeeze param
  [ ] karma_cinema_lens.vfl — complete CVEX lens shader
  [ ] Shader reads entrance pupil offset from USD attrib
  [ ] Shader applies dynamic squeeze (not static 2.0x)
  [ ] karma_lens_shader.py — LOP binding script
  [ ] Shader toggle controls: enable_distortion, enable_squeeze, enable_pupil_offset
  [ ] Compiles with vcc without errors

TESTS:
  [ ] test_cvex_identity — all toggles off: ray passes through unchanged
  [ ] test_squeeze_at_infinity — effective_squeeze=2.0: X doubled
  [ ] test_squeeze_at_mod — effective_squeeze=1.85: X scaled by 1.85
  [ ] test_pupil_offset — P.z = entrance_pupil_offset_cm
  [ ] test_distortion_matches_post — CVEX output matches COP STMap within 0.5px
```

---

## PILLAR E: Pipeline Bridge (EXR Metadata)

**Owner:** AGENT β (USD/Solaris)
**Depends on:** Pillars A-D (all metadata must be authored first)

### E.1 Extended configure_render_product()

```python
# File: python/cinema_camera/usd_builder.py (ADDITION)

def configure_render_product(
    stage: Usd.Stage,
    camera_path: str,
    output_path: str,
    camera_state: CameraState,
    lens_state: LensState,
    pixel_aspect: float = 1.0,
) -> UsdRender.Product:
    """
    Configure USD Render Product with Cooke /i + ASWF metadata.

    Bakes lens and camera metadata into OpenEXR headers so
    downstream compositors (Nuke, Resolve, Flame) can
    automatically extract match-move parameters.

    Metadata conforms to:
    - ASWF OpenEXR Technical Committee recommended attributes
    - Cooke /i Technology data stream format
    - ARRI camera metadata standard
    """
    cam_name = camera_path.split("/")[-1]
    product_path = f"/Render/Products/{cam_name}"
    product = UsdRender.Product.Define(stage, product_path)

    # ── Standard render product ──────────────────────────
    product.CreateResolutionAttr().Set(
        Gf.Vec2i(camera_state.format.width_px, camera_state.format.height_px)
    )
    product.CreatePixelAspectRatioAttr().Set(pixel_aspect)
    product.CreateCameraRel().SetTargets([Sdf.Path(camera_path)])
    product.CreateProductNameAttr().Set(output_path)

    # ── ASWF / Cooke /i EXR Metadata ────────────────────
    # These attributes bake into OpenEXR headers via Karma
    prim = product.GetPrim()
    d = lens_state.spec.distortion

    exr_metadata = {
        # Camera identification
        "driver:parameters:OpenEXR:camera:model":
            ("String", camera_state.model),
        "driver:parameters:OpenEXR:camera:sensorWidthMm":
            ("Float", camera_state.active_width_mm),
        "driver:parameters:OpenEXR:camera:sensorHeightMm":
            ("Float", camera_state.active_height_mm),
        "driver:parameters:OpenEXR:camera:exposureIndex":
            ("Int", camera_state.exposure_index),
        "driver:parameters:OpenEXR:camera:shutterAngleDeg":
            ("Float", camera_state.shutter_angle_deg),
        "driver:parameters:OpenEXR:camera:colorScience":
            ("String", camera_state.sensor.color_science),

        # Lens identification (Cooke /i format)
        "driver:parameters:OpenEXR:lens:manufacturer":
            ("String", lens_state.spec.manufacturer),
        "driver:parameters:OpenEXR:lens:series":
            ("String", lens_state.spec.series),
        "driver:parameters:OpenEXR:lens:focalLengthMm":
            ("Float", lens_state.spec.focal_length_mm),
        "driver:parameters:OpenEXR:lens:tStop":
            ("Float", lens_state.t_stop),
        "driver:parameters:OpenEXR:lens:focusDistanceM":
            ("Float", lens_state.focus_distance_m),
        "driver:parameters:OpenEXR:lens:irisBlades":
            ("Int", lens_state.spec.iris_blades),
        "driver:parameters:OpenEXR:lens:squeezeRatio":
            ("Float", lens_state.effective_squeeze),

        # Distortion model (for Nuke STMap/LensDistortion nodes)
        "driver:parameters:OpenEXR:lens:distortion:k1":
            ("Float", d.k1),
        "driver:parameters:OpenEXR:lens:distortion:k2":
            ("Float", d.k2),
        "driver:parameters:OpenEXR:lens:distortion:k3":
            ("Float", d.k3),
        "driver:parameters:OpenEXR:lens:distortion:p1":
            ("Float", d.p1),
        "driver:parameters:OpenEXR:lens:distortion:p2":
            ("Float", d.p2),
    }

    # Mechanical metadata (if available)
    if lens_state.spec.has_mechanics:
        m = lens_state.spec.mechanics
        exr_metadata.update({
            "driver:parameters:OpenEXR:lens:entrancePupilOffsetMm":
                ("Float", m.entrance_pupil_offset_mm),
            "driver:parameters:OpenEXR:lens:weightKg":
                ("Float", m.weight_kg),
        })

    _author_attributes(prim, exr_metadata)

    return product
```

### E.2 Acceptance Criteria

```
AGENT β DELIVERABLES (Pillar E):
  [ ] configure_render_product() extended with ASWF+Cooke/i metadata
  [ ] Camera metadata: model, sensor dims, EI, shutter, color science
  [ ] Lens metadata: manufacturer, series, focal length, T-stop, focus, iris
  [ ] Distortion coefficients baked for Nuke STMap reconstruction
  [ ] Mechanical metadata: entrance pupil offset, weight
  [ ] All metadata uses driver:parameters:OpenEXR:* namespace
  [ ] Time-sampled attributes for animated focus/t-stop

TESTS:
  [ ] test_exr_metadata_present — all expected attributes authored
  [ ] test_exr_metadata_values — spot-check Cooke 50mm values
  [ ] test_dynamic_squeeze_in_metadata — effective_squeeze reflects focus distance
```

---

## PILLAR G: Copernicus 2.0 Effects

**Owner:** AGENT δ (CHOPs/Copernicus)
**Depends on:** Pillar A (MechanicalSpec for flare geometry)

### G.1 Upgraded Effect Chain

```
EFFECT_CHAIN_V4 = [
    # ── v3.0 preserved ──────────────────────────────────
    "cinema::cop_distortion::1.0",        # Unchanged
    "cinema::cop_chromatic_ab::1.0",      # Unchanged
    "cinema::cop_vignette::1.0",          # Unchanged

    # ── v4.0 upgraded ───────────────────────────────────
    "cinema::cop_anamorphic_flare::2.0",  # REPLACES cop_anamorphic_streak::1.0
    "cinema::cop_sensor_noise::1.0",      # REPLACES cop_film_grain::1.0
    "cinema::cop_color_grade::1.0",       # Unchanged

    # ── v4.0 new ────────────────────────────────────────
    "cinema::cop_stmap_aov::1.0",         # NEW: generates STMap for Nuke
]
```

### G.2 FFT Convolution Flare (Replaces cop_anamorphic_streak)

```
cinema::cop_anamorphic_flare::2.0  [Copernicus HDA]
├── INPUT 0: Image (RGBA)
├── Parameters:
│   ├── enable (Toggle)
│   ├── iris_blades (Int, from LensState — e.g. 11 for Cooke)
│   ├── front_diameter_mm (Float, from MechanicalSpec — 110mm)
│   ├── squeeze_ratio (Float, effective squeeze at current focus)
│   ├── threshold (Float, flare trigger brightness)
│   ├── intensity (Float, global flare strength)
│   ├── ghosting_rings (Int, number of internal reflection ghosts)
│   └── streak_asymmetry (Float, 0=symmetric, 1=full anamorphic bias)
├── Internal VEX:
│   ├── Step 1: Threshold input → extract bright pixels
│   ├── Step 2: Generate iris kernel using co_generate_bokeh_kernel()
│   │           with iris_blades=11 and squeeze_ratio
│   ├── Step 3: FFT convolution of bright pixels × iris kernel
│   │           (produces physically accurate polygonal ghost patterns)
│   ├── Step 4: Anamorphic streak via horizontal Gaussian
│   │           stretched by front_diameter_mm / focal_length ratio
│   ├── Step 5: Chromatic fringing on ghosts (R/G/B offset)
│   └── Step 6: Composite flare over original
└── OUTPUT: Image with physically-based lens flare
```

### G.3 Sensor Noise Model (Replaces cop_film_grain)

```
cinema::cop_sensor_noise::1.0  [Copernicus HDA]
├── INPUT 0: Image (RGBA)
├── Parameters:
│   ├── enable (Toggle)
│   ├── exposure_index (Int, from CameraState — drives noise level)
│   ├── native_iso (Int, from SensorSpec — 800 for Alexa 35)
│   ├── sensor_model (Menu: "ALEXA 35 Dual Gain" / "Generic CMOS" / "Custom")
│   ├── photon_noise_amount (Float, shot noise — sqrt of signal)
│   ├── read_noise_amount (Float, electronic noise — constant floor)
│   └── temporal_coherence (Float, 0=fully random per frame, 1=static)
├── Internal VEX:
│   ├── Photon noise: sqrt(luminance) × random × photon_amount
│   │   (physically: shot noise scales with square root of exposure)
│   ├── Read noise: constant random × read_amount × (EI / native_iso)
│   │   (higher EI amplifies read noise — dual-gain model)
│   ├── Per-channel application (Bayer-pattern awareness)
│   ├── Temporal: lerp(random, cached_noise[frame], temporal_coherence)
│   └── Grain size: 1px at native_iso, 2px at 2× native, etc.
└── OUTPUT: Image with physically-modeled sensor noise
```

### G.4 STMap AOV Generator

```
cinema::cop_stmap_aov::1.0  [Copernicus HDA]
├── INPUT 0: Resolution reference (or explicit width/height params)
├── Parameters:
│   ├── resolution_x (Int, from CameraState.format.width_px)
│   ├── resolution_y (Int, from CameraState.format.height_px)
│   ├── distortion coefficients (all from LensState.spec.distortion)
│   ├── effective_squeeze (Float, dynamic squeeze)
│   └── mode (Menu: "Undistort" / "Redistort")
├── Internal VEX:
│   ├── For each pixel: compute co_apply_distortion() or co_undistort()
│   ├── Store result as Red=U, Green=V (normalized 0-1)
│   └── Uses libcinema_optics.h directly
├── OUTPUT 0: STMap image (RG float)
└── NOTE: Nuke compositor plugs this directly into STMap node
```

### G.5 Acceptance Criteria

```
AGENT δ DELIVERABLES (Pillar G):
  [ ] cinema::cop_anamorphic_flare::2.0 HDA with FFT convolution
  [ ] Flare kernel generated from iris_blades + squeeze_ratio
  [ ] Ghost patterns from front_diameter_mm ratio
  [ ] cinema::cop_sensor_noise::1.0 HDA with dual-gain model
  [ ] Photon noise scales with sqrt(luminance)
  [ ] Read noise amplified by EI/native_iso ratio
  [ ] cinema::cop_stmap_aov::1.0 HDA generating Nuke-ready STMap
  [ ] STMap uses libcinema_optics.h distortion functions directly
  [ ] All HDAs testable independently outside camera rig

TESTS:
  [ ] test_flare_11_blade — 11-sided polygonal ghost pattern visible
  [ ] test_noise_at_native_iso — minimal noise at EI 800
  [ ] test_noise_at_3200 — visible grain increase at 4× native
  [ ] test_stmap_roundtrip — distort→STMap→Nuke undistort: <0.5px error
```

---

## Integration: Updated Project Structure

```
$CINEMA_CAMERA_PATH/
├── hda/
│   ├── cinema_camera_rig_2.0.hda              # Top orchestrator (LOP) — UPDATED
│   ├── bodies/
│   │   └── cinema_alexa35_body_2.0.hda
│   ├── lenses/
│   │   └── cinema_cooke_anamorphic_2.0.hda
│   ├── render/
│   │   └── cinema_karma_setup_2.0.hda         # UPDATED: binds CVEX lens shader
│   ├── chops/                                  # ← NEW (v4.0)
│   │   └── cinema_chops_biomechanics_1.0.hda
│   └── post/
│       ├── cinema_cop_distortion_1.0.hda       # v3.0 (unchanged)
│       ├── cinema_cop_chromatic_ab_1.0.hda     # v3.0 (unchanged)
│       ├── cinema_cop_vignette_1.0.hda         # v3.0 (unchanged)
│       ├── cinema_cop_anamorphic_flare_2.0.hda # ← NEW (replaces streak)
│       ├── cinema_cop_sensor_noise_1.0.hda     # ← NEW (replaces grain)
│       ├── cinema_cop_color_grade_1.0.hda      # v3.0 (unchanged)
│       └── cinema_cop_stmap_aov_1.0.hda        # ← NEW
├── vex/
│   ├── libcinema_optics.h                      # EXTENDED: dynamic squeeze functions
│   └── karma_cinema_lens.vfl                   # ← NEW: CVEX lens shader source
├── python/
│   └── cinema_camera/
│       ├── __init__.py
│       ├── protocols.py                        # EXTENDED: MechanicalSpec, SqueezeBreathing
│       ├── registry.py                         # Unchanged
│       ├── optics_engine.py                    # Unchanged
│       ├── usd_builder.py                      # REFACTORED: nested Xform rig + EXR metadata
│       ├── karma_lens_shader.py                # ← NEW: CVEX shader binding
│       ├── biomechanics.py                     # ← NEW: CHOPs parameter derivation
│       ├── i_technology.py                     # Unchanged
│       ├── post_pipeline.py                    # UPDATED: v4.0 effect chain
│       ├── bodies/
│       │   ├── __init__.py
│       │   └── alexa35.py                      # Unchanged
│       └── lenses/
│           ├── __init__.py
│           └── cooke_anamorphic.py             # UPDATED: v4.0 JSON parser
├── lenses/
│   ├── cooke_ana_i_s35_50mm.json              # UPDATED: v4.0 JSON with mechanics
│   ├── cooke_ana_i_s35_300mm.json             # UPDATED: v4.0 JSON with mechanics
│   └── _schema_v4.json                         # ← NEW: v4.0 JSON schema
├── tests/
│   ├── test_protocols.py                       # EXTENDED: MechanicalSpec tests
│   ├── test_optics_engine.py                   # EXTENDED: dynamic squeeze tests
│   ├── test_registry.py                        # Unchanged
│   ├── test_biomechanics.py                    # ← NEW
│   ├── test_usd_rig_hierarchy.py               # ← NEW
│   ├── test_exr_metadata.py                    # ← NEW
│   ├── test_cvex_lens_shader.py                # ← NEW
│   ├── test_fov_accuracy.hip
│   ├── test_distortion_stmap.hip
│   └── test_dof_render.hip
└── README.md
```

---

## Execution Plan: Agent Team Task Sequencing

### Phase 1: Foundation (Day 1-2) — AGENT α solo

```
TASK 1.1: GearRingSpec + MechanicalSpec dataclasses
TASK 1.2: SqueezeBreathingCurve dataclass
TASK 1.3: LensSpec v4.0 extension (backwards-compatible)
TASK 1.4: LensState v4.0 extension (effective_squeeze property)
TASK 1.5: JSON schema v4.0 + Cooke 50mm/300mm data files
TASK 1.6: Updated from_json() parser
TASK 1.7: Protocol conformance tests

GATE: All v3.0 tests pass + new v4.0 protocol tests pass
```

### Phase 2: Parallel Build (Day 3-5) — All agents

```
AGENT β (USD):
  TASK 2.1: build_usd_camera_rig() with nested Xform hierarchy
  TASK 2.2: Backwards-compatible build_usd_camera() wrapper
  TASK 2.3: Extended configure_render_product() with EXR metadata
  TASK 2.4: USD hierarchy tests + usdchecker validation

AGENT γ (VEX/CVEX):
  TASK 2.5: co_evaluate_squeeze_curve() in libcinema_optics.h
  TASK 2.6: co_apply_anamorphic_distortion() with dynamic squeeze
  TASK 2.7: karma_cinema_lens.vfl — CVEX lens shader
  TASK 2.8: karma_lens_shader.py — USD binding
  TASK 2.9: vcc compilation test

AGENT δ (CHOPs/COP):
  TASK 2.10: BiomechanicsParams + derive_biomechanics()
  TASK 2.11: cinema::chops_biomechanics::1.0 HDA
  TASK 2.12: cinema::cop_anamorphic_flare::2.0 HDA (FFT convolution)
  TASK 2.13: cinema::cop_sensor_noise::1.0 HDA (dual-gain model)
  TASK 2.14: cinema::cop_stmap_aov::1.0 HDA

GATE: Each agent's tests pass independently
```

### Phase 3: Integration (Day 6-7) — ORCHESTRATOR

```
TASK 3.1: Wire top-level HDA — connect all v4.0 components
TASK 3.2: CVEX shader binds to USD attributes from build_usd_camera_rig()
TASK 3.3: CHOPs reads combinedWeightKg from USD → drives FluidHead
TASK 3.4: Copernicus pipeline reads effective_squeeze from USD
TASK 3.5: EXR metadata roundtrip test (render → read headers → validate)
TASK 3.6: Full regression: all v3.0 + v4.0 tests pass
TASK 3.7: Performance benchmarks vs targets

GATE: Full pipeline functional, benchmarks met
```

### Phase 4: Polish (Day 8) — All agents

```
TASK 4.1: HDA parameter UI polish (labels, tooltips, folders)
TASK 4.2: Viewport overlay for entrance pupil visualization
TASK 4.3: Documentation update
TASK 4.4: Example .hip file with animated focus pull showing Mumps
```

---

## Performance Targets

| Metric | v3.0 Target | v4.0 Target | Note |
|--------|-------------|-------------|------|
| Viewport | 60fps | 60fps | CHOPs must not drop frames |
| Optical calcs | <1ms | <1ms | Dynamic squeeze adds negligible cost |
| Bokeh map | <100ms | <100ms | Unchanged |
| STMap gen (4K) | <200ms | <200ms | Now also available as COP AOV |
| Karma preview | <30s | <35s | CVEX lens shader adds ~15% overhead |
| Post pipeline (4K) | <5s/frame | <8s/frame | FFT flare is more expensive |
| Biomechanics solve | N/A | <0.1ms/frame | CHOPs spring/lag is cheap |
| EXR metadata write | N/A | <1ms | Pure attribute authoring |

## Accuracy Targets

| Metric | v3.0 Target | v4.0 Target | Note |
|--------|-------------|-------------|------|
| FOV | ±0.1° vs ARRI sim | ±0.1° | Unchanged |
| DOF | ±5% vs ASC tables | ±5% | Unchanged |
| Distortion STMap | <0.5px error | <0.5px | Now validated CVEX↔COP |
| Color | ΔE < 1.0 ACES | ΔE < 1.0 | Unchanged |
| Dynamic squeeze | N/A | ±0.02 vs Cooke spec | New |
| Entrance pupil | N/A | ±1mm vs mfr spec | New |
| Noise at native ISO | N/A | SNR within 3dB of Alexa | New |

---

## Cross-Agent Interface Contracts

### Contract 1: AGENT α → AGENT β
```
LensState.entrance_pupil_offset_cm → USD cinema:rig:entrancePupilOffsetCm
LensState.effective_squeeze → USD cinema:rig:effectiveSqueeze
LensState.rig_weight_kg → USD cinema:rig:combinedWeightKg
LensState.to_usd_dict() → all cinema:lens:* attributes
```

### Contract 2: AGENT α → AGENT γ
```
LensSpec.squeeze_breathing.evaluate(focus_m) → effective_squeeze float
LensSpec.mechanics.entrance_pupil_offset_mm → entrance_pupil_offset_cm (÷10)
LensSpec.distortion → CO_DistortionCoeffs struct mapping
```

### Contract 3: AGENT β → AGENT γ
```
USD cinema:rig:effectiveSqueeze → CVEX shader effective_squeeze param
USD cinema:rig:entrancePupilOffsetCm → CVEX shader entrance_pupil_offset_cm
USD horizontalAperture → CVEX shader sensor_width_mm
USD cinema:lens:distortion:* → CVEX shader dist_* params
```

### Contract 4: AGENT β → AGENT δ
```
USD cinema:rig:combinedWeightKg → CHOPs spring/lag solver damping
USD FluidHead xformOp:rotateXYZ → CHOPs export target
```

### Contract 5: AGENT α → AGENT δ
```
MechanicalSpec.weight_kg → derive_biomechanics() lens_weight
MechanicalSpec.length_mm → moment arm calculation
LensSpec.iris_blades → FFT flare kernel shape
MechanicalSpec.front_diameter_mm → flare ghost scale
CameraState.exposure_index → sensor noise amplification
SensorSpec.native_iso → sensor noise baseline
```
