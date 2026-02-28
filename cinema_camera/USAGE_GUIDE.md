# Cinema Camera Rig v4.0 -- Usage Guide

The Cinema Camera Rig is a physically accurate virtual cinematography system for Houdini 21 Solaris. It simulates real-world camera and lens behavior -- anamorphic squeeze breathing, entrance pupil parallax, fluid head biomechanics, and sensor-accurate post-processing -- so renders match what a physical camera would produce.

## Quick Start

1. **Install the HDA**: Copy `cinema_camera_rig_2.0.hda` (and sub-HDAs) into your `$HOUDINI_OTLSCAN_PATH` or install via Synapse.
2. **Drop into scene**: In an Object context, **Tab > Cinema Camera Rig**. The node appears at `/obj/cinema_camera_rig1`.
3. **Select a lens**: Set **Lens ID** to a registry key (e.g., `cooke_ana_i_s35_50mm`). Focal length, distortion, and squeeze load automatically.
4. **Set focus**: Keyframe **Focus Distance (m)** for rack focus. Watch **Effective Squeeze** change as focus breathes.
5. **Render**: Point a Karma render node at the rig's camera. Cooke /i metadata is written to EXR automatically.

## Parameter Reference

### Lens Tab

| Parameter | Description |
|-----------|-------------|
| **Lens ID** | Registry key for the lens. Loads LensSpec JSON with all optical data. |
| **Focal Length (mm)** | Lens focal length. Drives camera horizontal aperture. |
| **T-Stop** | Transmission stop. T-stop = f-stop / lens transmission. Lower = more light. |
| **Focus Distance (m)** | Focus distance in meters. Drives dynamic squeeze (mumps) and depth of field. |
| **Squeeze Ratio** | Nominal anamorphic squeeze (1.0 = spherical, 2.0 = 2x anamorphic). |
| **Effective Squeeze** | *Read-only.* Focus-dependent squeeze computed from the breathing curve. Changes as you rack focus. |
| **Entrance Pupil Offset (mm)** | Distance from sensor plane to nodal point (entrance pupil). Critical for parallax-correct panning. The yellow circle guide in the viewport marks this position. |

### Distortion Tab

| Parameter | Description |
|-----------|-------------|
| **K1 (Radial)** | 2nd-order barrel/pincushion distortion. Primary term. |
| **K2 (Radial)** | 4th-order correction. Refines K1. |
| **K3 (Radial)** | 6th-order correction. Extreme corners on wide lenses. |
| **P1 (Tangential)** | Horizontal decentering distortion. |
| **P2 (Tangential)** | Vertical decentering distortion. |
| **Squeeze Uniformity** | 1.0 = uniform squeeze. <1.0 = squeeze varies across the field. |

All distortion coefficients are loaded from the LensSpec. Override manually for custom lenses.

### Camera Body Tab

| Parameter | Description |
|-----------|-------------|
| **Body ID** | Camera body registry key (e.g., `alexa35`). |
| **Sensor Width/Height (mm)** | Active sensor dimensions. ALEXA 35 Open Gate: 28.25 x 18.17mm. |
| **Resolution X/Y** | Pixel dimensions. Drives Karma render resolution. |
| **Exposure Index (EI)** | ISO-equivalent sensitivity. Higher = brighter + noisier. |
| **Native ISO** | Sensor's base ISO. Noise model scales relative to this. ALEXA 35: 800. |

### Biomechanics Tab

Simulates the physical behavior of a camera operator with a fluid head tripod.

| Parameter | Description |
|-----------|-------------|
| **Enable Biomechanics** | Master toggle for the spring/lag/shake solver. |
| **Combined Weight (kg)** | Body + lens weight. Auto-computed from specs. |
| **Moment Arm (cm)** | Pivot-to-CG distance. Longer = more rotational inertia. |
| **Spring Constant** | Fluid head stiffness. Higher = snappier. |
| **Damping Ratio** | 0 = oscillates, 1 = critically damped. Typical: 0.4-0.7. |
| **Lag (frames)** | Operator reaction delay. |
| **Auto Derive from Weight** | When on, spring/damping/lag are computed from weight. |

**Handheld Shake** (sub-group):

| Parameter | Description |
|-----------|-------------|
| **Enable Handheld Shake** | Add procedural shake noise. |
| **Shake Amplitude (deg)** | Peak rotation. 0.1-0.3 = subtle, 0.5+ = agitated. |
| **Shake Frequency (Hz)** | Dominant frequency. Human handheld: 4-7 Hz. |

### Post-Processing Tab

| Parameter | Description |
|-----------|-------------|
| **Enable Anamorphic Flare** | Horizontal streak flares from bright sources. |
| **Flare Threshold** | Luminance cutoff for flare generation. |
| **Flare Intensity** | Streak intensity multiplier. |

**Sensor Noise** (sub-group):

| Parameter | Description |
|-----------|-------------|
| **Enable Sensor Noise** | Physically-modeled photon + read noise. |
| **Photon Noise** | Shot noise multiplier. 1.0 = accurate. |
| **Read Noise** | Electronic noise multiplier. 1.0 = accurate. |
| **Generate STMap AOV** | Output distortion ST map for Nuke/Flame. |

### Pipeline Tab

| Parameter | Description |
|-----------|-------------|
| **Write Cooke /i Metadata** | Author Cooke /i Technology fields on RenderProduct. |
| **Write ASWF EXR Headers** | Author ASWF-standard EXR metadata headers. |
| **USD Camera Prim** | Prim path for the USD camera in the stage. |

## Animated Focus Pull Workflow

1. Go to frame 1. Set **Focus Distance (m)** to your starting focus (e.g., 10.0). Right-click > **Keyframe**.
2. Go to your target frame (e.g., 96). Set **Focus Distance (m)** to end focus (e.g., 0.5). Keyframe again.
3. Watch **Effective Squeeze** animate automatically -- this is the anamorphic "mumps" breathing effect. Close focus = less squeeze.
4. Open the animation editor to adjust the interpolation curve (ease in/out for cinematic feel).

## Cooke /i Metadata

When **Write Cooke /i Metadata** is enabled, the following fields are authored on the RenderProduct prim and embedded in EXR headers:

- Camera model, sensor dimensions, exposure index, shutter angle, color science
- Lens manufacturer, series, focal length, T-stop, focus distance, iris blades
- Distortion coefficients (K1-K3, P1-P2)
- Entrance pupil offset, lens weight (if MechanicalSpec available)
- Effective squeeze at current focus distance

This allows downstream tools (Nuke, Flame, SynthEyes) to apply matching distortion/undistortion without manual data entry.

## Entrance Pupil Viewport Guide

The yellow circle visible in the viewport marks the entrance pupil (nodal point) position. This is the correct pivot for parallax-free panning -- essential for VFX plate matching, HDRI capture, and nodal pan shots. The pivot null automatically offsets along the camera Z axis based on the lens's entrance pupil offset specification.

## Known Limitations

- **Sub-HDAs are placeholders**: The COP network nodes (flare, noise, STMap) are currently null placeholders with comments indicating which sub-HDA to instance. Replace with actual HDA instances when the sub-HDAs are installed.
- **CHOPs biomechanics**: The biomechanics CHOPs network is a skeleton (fetch + output null). The actual `cinema::chops_biomechanics::1.0` HDA must be instanced inside.
- **No live lens swap**: Changing `lens_id` does not auto-reload lens parameters. Currently requires a Python callback or Synapse bridge to re-populate from registry.
- **Squeeze breathing curve**: The `effective_squeeze` parameter requires an external driver (Python SOP or expression) to evaluate the SqueezeBreathingCurve at the current focus distance. Without it, the value stays at the default.
- **Single camera body**: Only ALEXA 35 is fully specified in the registry. Other bodies can be added via `bodies/` module.
- **Distortion is metadata-only**: The distortion coefficients are written to metadata and available for the CVEX lens shader, but do not affect the Houdini camera frustum directly. Apply distortion in comp or via the STMap AOV.
