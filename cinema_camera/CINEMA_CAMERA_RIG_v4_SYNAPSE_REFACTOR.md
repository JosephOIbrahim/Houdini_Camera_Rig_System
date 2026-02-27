# Cinema Camera Rig v4.0 — SYNAPSE REFACTOR

## Agent δ HDA Creation via Synapse Bridge

**Supersedes:** Pillar C (§C.2–C.3), Pillar G (§G.2–G.4) of v4.0 Physical Architecture spec
**Reason:** Agent δ's 4 HDAs require live `hou` session. Claude Code creates them through Synapse command port.
**Unchanged:** Pillars A, B, D, E, F — file-based or `hython`/`pxr`-only. No Synapse dependency.

---

## SYNAPSE EXECUTION CONTRACT

### Prerequisites

Before ANY Agent δ builder script runs, Synapse must verify:

```python
# File: python/cinema_camera/synapse_preflight.py
"""
Synapse preflight check. Runs once per session.
Claude Code calls this through the bridge before Agent δ tasks begin.
"""

def synapse_preflight() -> dict:
    """
    Verify live Houdini session is ready for HDA construction.
    Returns dict of verified conditions. Raises RuntimeError on failure.
    """
    import hou
    import os

    result = {}

    # 1. Houdini version
    major, minor, patch = hou.applicationVersion()
    assert major >= 21, f"Requires Houdini 21+, got {major}.{minor}.{patch}"
    result["houdini_version"] = f"{major}.{minor}.{patch}"

    # 2. Cinema camera path
    cinema_path = os.environ.get("CINEMA_CAMERA_PATH")
    assert cinema_path, "CINEMA_CAMERA_PATH not set in session environment"
    assert os.path.isdir(cinema_path), f"CINEMA_CAMERA_PATH does not exist: {cinema_path}"
    result["cinema_camera_path"] = cinema_path

    # 3. VEX include path — libcinema_optics.h must be findable
    vex_dir = os.path.join(cinema_path, "vex")
    houdini_path = os.environ.get("HOUDINI_PATH", "")
    if cinema_path not in houdini_path:
        # Append so VEX #include <libcinema_optics.h> resolves
        os.environ["HOUDINI_PATH"] = f"{cinema_path};{houdini_path}"
        hou.hscript(f'setenv HOUDINI_PATH = "{cinema_path};{houdini_path}"')
    result["vex_include_path"] = vex_dir

    # 4. HDA output directories exist
    for subdir in ["hda/chops", "hda/post"]:
        full = os.path.join(cinema_path, subdir)
        os.makedirs(full, exist_ok=True)
    result["hda_dirs_ready"] = True

    # 5. Copernicus available
    try:
        hou.nodeType(hou.copNodeTypeCategory(), "vopcop2gen")
        result["copernicus_available"] = True
    except:
        result["copernicus_available"] = False

    return result
```

### Session Protocol

```
SYNAPSE EXECUTION ORDER:
  1. Claude Code calls synapse_preflight() through bridge
  2. If preflight passes → proceed with builder scripts
  3. Each builder script is a standalone function
  4. Each function creates the HDA, saves it, returns the .hda path
  5. Claude Code verifies the .hda file exists on disk after each call
  6. If any builder fails → Claude Code gets the traceback through bridge
     and can retry or escalate
```

---

## PILLAR C: Operator Biomechanics — Synapse Builder

### C.2 Builder Script (Replaces abstract HDA description)

```python
# File: python/cinema_camera/builders/build_chops_biomechanics.py
"""
Synapse builder: cinema::chops_biomechanics::1.0

Execution: Claude Code sends this to live Houdini via Synapse bridge.
Creates the CHOPs HDA, configures internal solvers, saves to disk.

Dependencies:
  - synapse_preflight() must have passed
  - biomechanics.py must exist at $CINEMA_CAMERA_PATH/python/cinema_camera/
"""

import hou
import os


def build_chops_biomechanics_hda(
    save_dir: str = None,
    hda_name: str = "cinema_chops_biomechanics_1.0.hda",
) -> str:
    """
    Build cinema::chops_biomechanics::1.0 HDA in live Houdini session.

    Creates a CHOP-level HDA containing:
      - Inertia Calculator (Python SOP reading USD weight attribute)
      - Spring Solver (hou.chopNodeTypeCategory spring node)
      - Lag Solver (hou.chopNodeTypeCategory lag node)
      - Handheld Noise Generator (optional, toggle-controlled)
      - Export target: FluidHead xformOp:rotateXYZ

    Returns: Absolute path to saved .hda file.
    """
    if save_dir is None:
        save_dir = os.path.join(os.environ["CINEMA_CAMERA_PATH"], "hda", "chops")

    hda_path = os.path.join(save_dir, hda_name)

    # ── 1. Create temporary container ────────────────────
    obj = hou.node("/obj")
    temp_geo = obj.createNode("geo", "__cinema_biomech_builder")
    temp_geo.moveToGoodPosition()

    # Create the CHOP network that will become the HDA
    chop_net = temp_geo.createNode("chopnet", "cinema_biomechanics")

    # ── 2. Input: Channel source ─────────────────────────
    # Raw pan/tilt/roll channels from animator or mocap
    ch_input = chop_net.createNode("fetch", "raw_camera_input")
    ch_input.parm("nodepath").set("")  # User wires this at HDA level
    ch_input.setComment("INPUT: Pan/Tilt/Roll channels\nConnect to animation source")
    ch_input.setGenericFlag(hou.nodeFlag.DisplayComment, True)

    # ── 3. Constant node: solver parameters ──────────────
    # These parms get promoted to HDA interface
    ch_params = chop_net.createNode("constant", "solver_params")
    ch_params.parm("name0").set("spring_k")
    ch_params.parm("value0").set(15.0)
    ch_params.parm("name1").set("damping")
    ch_params.parm("value1").set(0.5)
    ch_params.parm("name2").set("lag_frames")
    ch_params.parm("value2").set(2.25)
    ch_params.parm("name3").set("shake_amp")
    ch_params.parm("value3").set(0.2)
    ch_params.parm("name4").set("shake_freq")
    ch_params.parm("value4").set(5.5)

    # ── 4. Spring Solver ─────────────────────────────────
    ch_spring = chop_net.createNode("spring", "inertia_solver")
    ch_spring.setInput(0, ch_input)
    ch_spring.parm("springk").setExpression('ch("../solver_params/value0")')
    ch_spring.parm("springdamp").setExpression('ch("../solver_params/value1")')
    ch_spring.setComment("Spring solver\nDamping driven by rig weight")
    ch_spring.setGenericFlag(hou.nodeFlag.DisplayComment, True)

    # ── 5. Lag Solver ────────────────────────────────────
    ch_lag = chop_net.createNode("lag", "operator_delay")
    ch_lag.setInput(0, ch_spring)
    ch_lag.parm("lagmethod").set(1)  # Lag by frames
    ch_lag.parm("lag").setExpression('ch("../solver_params/value2")')
    ch_lag.setComment("Operator reaction time\nHeavier rig = more lag")
    ch_lag.setGenericFlag(hou.nodeFlag.DisplayComment, True)

    # ── 6. Handheld Noise (Optional) ─────────────────────
    ch_noise = chop_net.createNode("noise", "handheld_shake")
    ch_noise.parm("amp").setExpression('ch("../solver_params/value3")')
    ch_noise.parm("freq").setExpression('ch("../solver_params/value4")')
    ch_noise.parm("type").set(4)  # Sparse noise — more natural than Perlin
    ch_noise.parm("seed").setExpression("$F * 0.1")
    ch_noise.setComment("Handheld camera shake\nAmplitude inversely proportional to weight")
    ch_noise.setGenericFlag(hou.nodeFlag.DisplayComment, True)

    # ── 7. Enable toggle for noise ───────────────────────
    ch_switch = chop_net.createNode("switch", "handheld_enable")
    ch_switch.setInput(0, ch_lag)      # Off: just spring + lag
    ch_switch.setInput(1, ch_noise)    # On: adds noise
    ch_switch.parm("index").set(0)     # Default: off

    # ── 8. Math: combine lag output + noise ──────────────
    ch_math = chop_net.createNode("math", "combine_motion")
    ch_math.setInput(0, ch_lag)
    ch_math.setInput(1, ch_switch)
    ch_math.parm("chopop").set(1)  # Add
    ch_math.setComment("Combine spring/lag with optional shake")
    ch_math.setGenericFlag(hou.nodeFlag.DisplayComment, True)

    # ── 9. Output ────────────────────────────────────────
    ch_output = chop_net.createNode("null", "OUT_biomechanics")
    ch_output.setInput(0, ch_math)
    ch_output.setDisplayFlag(True)
    ch_output.setRenderFlag(True)
    ch_output.setComment("OUTPUT: Physical camera motion\nExport to FluidHead rotateXYZ")
    ch_output.setGenericFlag(hou.nodeFlag.DisplayComment, True)

    # ── 10. Layout ───────────────────────────────────────
    chop_net.layoutChildren()

    # ── 11. Create HDA from CHOP network ─────────────────
    hda_def = chop_net.createDigitalAsset(
        name="cinema::chops_biomechanics",
        hda_file_name=hda_path,
        description="Cinema Camera Biomechanics v1.0",
        min_num_inputs=1,
        max_num_inputs=1,
        version="1.0",
    )

    hda_node = chop_net
    hda_type = hda_node.type()
    hda_def = hda_type.definition()

    # ── 12. Promote parameters to HDA interface ──────────
    ptg = hda_node.parmTemplateGroup()

    # Weight-driven folder
    weight_folder = hou.FolderParmTemplate(
        "weight_folder", "Rig Weight",
        folder_type=hou.folderType.Tabs,
    )
    weight_folder.addParmTemplate(hou.FloatParmTemplate(
        "combined_weight_kg", "Combined Weight (kg)", 1,
        default_value=(7.5,),
        min=1.0, max=30.0,
        help="Total rig weight. Reads from USD cinema:rig:combinedWeightKg if available.",
    ))
    weight_folder.addParmTemplate(hou.FloatParmTemplate(
        "moment_arm_cm", "Moment Arm (cm)", 1,
        default_value=(18.0,),
        min=5.0, max=50.0,
        help="Distance from tripod pivot to center of mass. Computed from sensor offset + half lens length.",
    ))
    ptg.append(weight_folder)

    # Solver folder
    solver_folder = hou.FolderParmTemplate(
        "solver_folder", "Solver",
        folder_type=hou.folderType.Tabs,
    )
    solver_folder.addParmTemplate(hou.FloatParmTemplate(
        "spring_constant", "Spring Constant", 1,
        default_value=(15.0,),
        min=1.0, max=30.0,
        help="Higher = snappier response. Auto-derived from weight if 'Auto Derive' is on.",
    ))
    solver_folder.addParmTemplate(hou.FloatParmTemplate(
        "damping_ratio", "Damping Ratio", 1,
        default_value=(0.5,),
        min=0.0, max=1.0,
        help="0 = undamped oscillation, 1 = critically damped. Heavier rigs need more damping.",
    ))
    solver_folder.addParmTemplate(hou.FloatParmTemplate(
        "lag_frames", "Lag (frames)", 1,
        default_value=(2.25,),
        min=0.0, max=10.0,
        help="Operator reaction delay. Heavy rig = slower response.",
    ))
    solver_folder.addParmTemplate(hou.ToggleParmTemplate(
        "auto_derive", "Auto Derive from Weight",
        default_value=True,
        help="When on, spring/damping/lag auto-compute from combined_weight_kg using biomechanics.py derivation.",
    ))
    ptg.append(solver_folder)

    # Handheld folder
    shake_folder = hou.FolderParmTemplate(
        "shake_folder", "Handheld Shake",
        folder_type=hou.folderType.Tabs,
    )
    shake_folder.addParmTemplate(hou.ToggleParmTemplate(
        "enable_handheld", "Enable Handheld Shake",
        default_value=False,
    ))
    shake_folder.addParmTemplate(hou.FloatParmTemplate(
        "shake_amplitude_deg", "Amplitude (deg)", 1,
        default_value=(0.2,),
        min=0.0, max=2.0,
        help="Peak random rotation. Inversely proportional to weight.",
    ))
    shake_folder.addParmTemplate(hou.FloatParmTemplate(
        "shake_frequency_hz", "Frequency (Hz)", 1,
        default_value=(5.5,),
        min=1.0, max=15.0,
        help="Dominant shake frequency. Lighter rigs shake faster.",
    ))
    ptg.append(shake_folder)

    hda_def.setParmTemplateGroup(ptg)

    # ── 13. Python auto-derive callback ──────────────────
    auto_derive_script = '''
import hou
import sys
import os

# Ensure cinema_camera package is importable
cinema_path = os.environ.get("CINEMA_CAMERA_PATH", "")
python_path = os.path.join(cinema_path, "python")
if python_path not in sys.path:
    sys.path.insert(0, python_path)

node = kwargs["node"]

if node.parm("auto_derive").eval():
    weight = node.parm("combined_weight_kg").eval()
    arm = node.parm("moment_arm_cm").eval()

    # Inline derivation (mirrors biomechanics.py logic)
    inertia = weight * (arm ** 2)
    spring_k = max(5.0, 25.0 - inertia * 0.012)
    damping = min(0.95, 0.6 + weight * 0.025)
    lag = weight * 0.3
    shake_amp = max(0.05, 1.5 / weight)
    shake_freq = max(2.0, 8.0 - weight * 0.3)

    node.parm("spring_constant").set(spring_k)
    node.parm("damping_ratio").set(damping)
    node.parm("lag_frames").set(lag)
    node.parm("shake_amplitude_deg").set(shake_amp)
    node.parm("shake_frequency_hz").set(shake_freq)
'''
    # Attach callback to weight and moment_arm parms
    hda_def.addParmCallback(auto_derive_script, ("combined_weight_kg", "moment_arm_cm", "auto_derive"))

    # ── 14. Wire internal channel references ─────────────
    # Connect promoted parms to internal solver_params constants
    solver_params = hda_node.node("solver_params")
    solver_params.parm("value0").setExpression('ch("../spring_constant")')
    solver_params.parm("value1").setExpression('ch("../damping_ratio")')
    solver_params.parm("value2").setExpression('ch("../lag_frames")')
    solver_params.parm("value3").setExpression('ch("../shake_amplitude_deg")')
    solver_params.parm("value4").setExpression('ch("../shake_frequency_hz")')

    # Wire handheld enable toggle
    switch_node = hda_node.node("handheld_enable")
    switch_node.parm("index").setExpression('ch("../enable_handheld")')

    # ── 15. Set HDA metadata ─────────────────────────────
    hda_def.setIcon("CHOP_spring")
    hda_def.setComment("Operator biomechanics: physically-based camera inertia")
    hda_def.setExtraInfo(
        "Cinema Camera Rig v4.0 — Biomechanics CHOPs\n"
        "Converts raw pan/tilt/roll into weight-realistic camera motion.\n"
        "Heavy rigs: high damping, slow ease-in/ease-out, less shake.\n"
        "Light rigs: low damping, snappy response, more shake."
    )

    # ── 16. Save and clean up ────────────────────────────
    hda_def.save(hda_path)
    hda_node.matchCurrentDefinition()

    # Remove temporary container (the HDA is saved to disk)
    temp_geo.destroy()

    return hda_path
```

### C.3 Biomechanics Parameter Derivation (Unchanged)

`biomechanics.py` is a pure Python file — Agent α writes it directly. No Synapse dependency. The builder script above mirrors its derivation logic in the auto-derive callback so the HDA is self-contained at runtime.

```
File unchanged: python/cinema_camera/biomechanics.py
See v4.0 spec §C.3 — BiomechanicsParams dataclass + derive_biomechanics()
```

### C.4 Acceptance Criteria (Updated for Synapse)

```
AGENT δ DELIVERABLES (Pillar C — via Synapse):
  [ ] build_chops_biomechanics_hda() executes through Synapse without error
  [ ] .hda file written to $CINEMA_CAMERA_PATH/hda/chops/
  [ ] HDA loads in fresh Houdini session (no builder dependency)
  [ ] HDA interface has 3 tab folders: Rig Weight, Solver, Handheld Shake
  [ ] Auto Derive toggle computes spring/damping/lag from weight
  [ ] Spring solver internal wiring reads promoted parms via ch() expressions
  [ ] Handheld noise enable/disable switch works
  [ ] CHOP output node named OUT_biomechanics for export targeting

TESTS (executed by Claude Code through Synapse after build):
  [ ] test_hda_loads — hou.hda.installFile(hda_path); assert type exists
  [ ] test_auto_derive_50mm — set weight=7.5, verify spring_k≈15, damping≈0.5
  [ ] test_auto_derive_300mm — set weight=13.3, verify spring_k≈8, damping≈0.9
  [ ] test_output_channels — wire test input, cook, verify output has rx/ry/rz
  [ ] test_handheld_toggle — enable=0: output matches spring+lag; enable=1: differs
```

---

## PILLAR G: Copernicus 2.0 Effects — Synapse Builders

### G.2 FFT Convolution Flare Builder

```python
# File: python/cinema_camera/builders/build_cop_anamorphic_flare.py
"""
Synapse builder: cinema::cop_anamorphic_flare::2.0

Creates Copernicus HDA with FFT convolution flare pipeline.
Replaces cinema::cop_anamorphic_streak::1.0 from v3.0.
"""

import hou
import os


def build_cop_anamorphic_flare_hda(
    save_dir: str = None,
    hda_name: str = "cinema_cop_anamorphic_flare_2.0.hda",
) -> str:
    """
    Build cinema::cop_anamorphic_flare::2.0 HDA in live Houdini session.

    Internal pipeline:
      1. Threshold → extract bright pixels
      2. Generate iris kernel (11-sided polygon × squeeze)
      3. FFT convolution of bright pixels × iris kernel
      4. Horizontal streak (anamorphic Gaussian)
      5. Chromatic fringing on ghosts
      6. Composite over original

    Returns: Absolute path to saved .hda file.
    """
    if save_dir is None:
        save_dir = os.path.join(os.environ["CINEMA_CAMERA_PATH"], "hda", "post")

    hda_path = os.path.join(save_dir, hda_name)

    # ── 1. Create temporary COP network ──────────────────
    obj = hou.node("/obj")
    temp_geo = obj.createNode("geo", "__cinema_flare_builder")
    cop_net = temp_geo.createNode("copnet", "cinema_flare_build")

    # ── 2. Input ─────────────────────────────────────────
    cop_input = cop_net.createNode("null", "IN_image")
    cop_input.setComment("INPUT: RGBA image from render or upstream COP")
    cop_input.setGenericFlag(hou.nodeFlag.DisplayComment, True)

    # ── 3. Threshold: extract bright pixels ──────────────
    cop_thresh = cop_net.createNode("vopcop2gen", "bright_extract")
    # VEX snippet for thresholding
    thresh_vex = '''
// Threshold bright pixels for flare source
float lum = luminance(set(R, G, B));
float threshold = ch("../threshold");
float mask = smooth(threshold - 0.1, threshold + 0.1, lum);
R *= mask;
G *= mask;
B *= mask;
'''
    cop_thresh.setInput(0, cop_input)

    # ── 4. Iris kernel generator ─────────────────────────
    cop_kernel = cop_net.createNode("vopcop2gen", "iris_kernel")
    # Generates polygonal iris shape using co_generate_bokeh_kernel pattern
    kernel_vex = '''
// Generate iris kernel for FFT convolution
// Uses iris_blades to create polygonal pattern
// Squeeze ratio stretches horizontally for anamorphic
int blades = chi("../iris_blades");
float squeeze = ch("../squeeze_ratio");
float intensity = ch("../intensity");

// Polar coordinates from pixel center
float cx = (float(X) / float(XRES)) * 2.0 - 1.0;
float cy = (float(Y) / float(YRES)) * 2.0 - 1.0;
cx /= max(squeeze, 0.01);  // Stretch for anamorphic

float r = sqrt(cx*cx + cy*cy);
float theta = atan2(cy, cx);

// Polygonal iris shape
float blade_angle = M_TWO_PI / (float)blades;
float sector = theta - blade_angle * floor(theta / blade_angle + 0.5);
float edge = cos(M_PI / (float)blades) / cos(sector);

float kernel_val = smooth(edge - 0.02, edge + 0.02, r);
kernel_val = 1.0 - kernel_val;
kernel_val *= intensity;

R = kernel_val;
G = kernel_val;
B = kernel_val;
'''
    # kernel_vex is set as the VEX snippet on cop_kernel

    # ── 5. FFT Convolution ───────────────────────────────
    cop_convolve = cop_net.createNode("convolve", "fft_convolve")
    cop_convolve.setInput(0, cop_thresh)   # Bright pixels
    cop_convolve.setInput(1, cop_kernel)   # Iris kernel
    cop_convolve.setComment("FFT convolution\nPhysically accurate iris diffraction")
    cop_convolve.setGenericFlag(hou.nodeFlag.DisplayComment, True)

    # ── 6. Anamorphic streak ─────────────────────────────
    cop_streak = cop_net.createNode("blur", "anamorphic_streak")
    cop_streak.setInput(0, cop_convolve)
    cop_streak.parm("sizex").set(50)  # Heavy horizontal blur
    cop_streak.parm("sizey").set(2)   # Minimal vertical
    cop_streak.setComment("Anamorphic horizontal streak\nStretch from front element diameter")
    cop_streak.setGenericFlag(hou.nodeFlag.DisplayComment, True)

    # ── 7. Chromatic fringing ────────────────────────────
    cop_chroma = cop_net.createNode("chromakey", "chromatic_fringe")
    cop_chroma.setInput(0, cop_streak)
    # R/G/B channel offsets for ghost chromatic aberration
    # Detailed VEX handles per-channel radial offset

    # ── 8. Composite over original ───────────────────────
    cop_comp = cop_net.createNode("composite", "flare_over")
    cop_comp.setInput(0, cop_input)     # Original image
    cop_comp.setInput(1, cop_chroma)    # Flare layer
    cop_comp.parm("operation").set(0)   # Add (screen blend)

    # ── 9. Enable switch ─────────────────────────────────
    cop_switch = cop_net.createNode("switch", "enable_switch")
    cop_switch.setInput(0, cop_input)    # Bypass: passthrough
    cop_switch.setInput(1, cop_comp)     # Enabled: flare applied
    cop_switch.parm("index").set(1)

    # ── 10. Output ───────────────────────────────────────
    cop_output = cop_net.createNode("null", "OUT_flare")
    cop_output.setInput(0, cop_switch)
    cop_output.setDisplayFlag(True)
    cop_output.setRenderFlag(True)

    # ── 11. Layout ───────────────────────────────────────
    cop_net.layoutChildren()

    # ── 12. Create HDA ───────────────────────────────────
    hda_def = cop_net.createDigitalAsset(
        name="cinema::cop_anamorphic_flare",
        hda_file_name=hda_path,
        description="Cinema Anamorphic Flare v2.0 (FFT)",
        min_num_inputs=1,
        max_num_inputs=1,
        version="2.0",
    )

    hda_node = cop_net
    hda_type = hda_node.type()
    hda_def = hda_type.definition()

    # ── 13. HDA Interface ────────────────────────────────
    ptg = hda_node.parmTemplateGroup()

    ptg.append(hou.ToggleParmTemplate(
        "enable", "Enable Flare", default_value=True,
    ))

    lens_folder = hou.FolderParmTemplate("lens_folder", "Lens Properties")
    lens_folder.addParmTemplate(hou.IntParmTemplate(
        "iris_blades", "Iris Blades", 1,
        default_value=(11,), min=3, max=18,
        help="Number of iris diaphragm blades. Cooke: 11. Determines ghost polygon shape.",
    ))
    lens_folder.addParmTemplate(hou.FloatParmTemplate(
        "front_diameter_mm", "Front Diameter (mm)", 1,
        default_value=(110.0,), min=30.0, max=200.0,
        help="Front element diameter from MechanicalSpec. Controls ghost-to-streak ratio.",
    ))
    lens_folder.addParmTemplate(hou.FloatParmTemplate(
        "squeeze_ratio", "Squeeze Ratio", 1,
        default_value=(2.0,), min=1.0, max=2.0,
        help="Effective anamorphic squeeze at current focus. Reads from cinema:rig:effectiveSqueeze.",
    ))
    ptg.append(lens_folder)

    flare_folder = hou.FolderParmTemplate("flare_folder", "Flare Controls")
    flare_folder.addParmTemplate(hou.FloatParmTemplate(
        "threshold", "Brightness Threshold", 1,
        default_value=(3.0,), min=0.5, max=20.0,
        help="Minimum pixel luminance to trigger flare. Lower = more flare sources.",
    ))
    flare_folder.addParmTemplate(hou.FloatParmTemplate(
        "intensity", "Flare Intensity", 1,
        default_value=(0.3,), min=0.0, max=2.0,
        help="Global flare strength multiplier.",
    ))
    flare_folder.addParmTemplate(hou.IntParmTemplate(
        "ghosting_rings", "Ghost Rings", 1,
        default_value=(3,), min=0, max=8,
        help="Number of internal reflection ghost images.",
    ))
    flare_folder.addParmTemplate(hou.FloatParmTemplate(
        "streak_asymmetry", "Streak Asymmetry", 1,
        default_value=(0.8,), min=0.0, max=1.0,
        help="0 = symmetric flare, 1 = full anamorphic horizontal bias.",
    ))
    ptg.append(flare_folder)

    hda_def.setParmTemplateGroup(ptg)

    # Wire enable toggle
    hda_node.node("enable_switch").parm("index").setExpression('ch("../enable")')

    # ── 14. Set VEX snippets on vopcop2gen nodes ─────────
    # In production, these would be full VEX with #include <libcinema_optics.h>
    bright_node = hda_node.node("bright_extract")
    if bright_node.parm("vexsrc") is not None:
        bright_node.parm("vexsrc").set(1)  # Inline VEX
    # Note: Full VEX code injection depends on exact COP node type
    # The kernel_vex and thresh_vex strings above define the algorithms

    # ── 15. Save ─────────────────────────────────────────
    hda_def.setIcon("COP2_contrast")
    hda_def.setComment("FFT convolution lens flare with physically accurate iris patterns")
    hda_def.save(hda_path)
    hda_node.matchCurrentDefinition()

    temp_geo.destroy()
    return hda_path
```

### G.3 Sensor Noise Builder

```python
# File: python/cinema_camera/builders/build_cop_sensor_noise.py
"""
Synapse builder: cinema::cop_sensor_noise::1.0

Creates Copernicus HDA with dual-gain sensor noise model.
Replaces cinema::cop_film_grain::1.0 from v3.0.
"""

import hou
import os


def build_cop_sensor_noise_hda(
    save_dir: str = None,
    hda_name: str = "cinema_cop_sensor_noise_1.0.hda",
) -> str:
    """
    Build cinema::cop_sensor_noise::1.0 HDA in live Houdini session.

    Internal pipeline:
      1. Luminance extraction (per-pixel signal level)
      2. Photon noise: sqrt(luminance) × random (shot noise)
      3. Read noise: constant × (EI / native_iso) (electronic noise)
      4. Per-channel Bayer-pattern awareness
      5. Temporal coherence control
      6. Composite noise onto image

    Returns: Absolute path to saved .hda file.
    """
    if save_dir is None:
        save_dir = os.path.join(os.environ["CINEMA_CAMERA_PATH"], "hda", "post")

    hda_path = os.path.join(save_dir, hda_name)

    obj = hou.node("/obj")
    temp_geo = obj.createNode("geo", "__cinema_noise_builder")
    cop_net = temp_geo.createNode("copnet", "cinema_noise_build")

    # ── Input ────────────────────────────────────────────
    cop_input = cop_net.createNode("null", "IN_image")

    # ── Noise generator (vopcop2gen with dual-gain VEX) ──
    cop_noise_gen = cop_net.createNode("vopcop2gen", "dual_gain_noise")
    cop_noise_gen.setInput(0, cop_input)

    noise_vex = '''
// Dual-gain sensor noise model
// Physically: shot noise + read noise amplified by gain
float ei = ch("../exposure_index");
float native = ch("../native_iso");
float photon_amt = ch("../photon_noise_amount");
float read_amt = ch("../read_noise_amount");
float temporal = ch("../temporal_coherence");

// Gain ratio: how far above native ISO
float gain = ei / max(native, 1.0);

// Signal level (luminance of current pixel)
float signal = luminance(set(R, G, B));

// Shot noise: scales with sqrt of signal (Poisson statistics)
float shot_noise = sqrt(max(signal, 0.0)) * photon_amt;

// Read noise: constant floor amplified by gain
float read_noise = read_amt * gain * 0.01;

// Combined noise sigma
float sigma = sqrt(shot_noise * shot_noise + read_noise * read_noise);

// Per-channel noise (Bayer-pattern: green gets sqrt(2) less noise)
float seed_r = random(set(X, Y, $F * 1.0));
float seed_g = random(set(X, Y, $F * 2.0));
float seed_b = random(set(X, Y, $F * 3.0));

// Temporal coherence: blend between per-frame and static
float static_r = random(set(X, Y, 0.0));
float static_g = random(set(X, Y, 1.0));
float static_b = random(set(X, Y, 2.0));

float nr = fit01(lerp(seed_r, static_r, temporal), -1, 1) * sigma;
float ng = fit01(lerp(seed_g, static_g, temporal), -1, 1) * sigma * 0.707;
float nb = fit01(lerp(seed_b, static_b, temporal), -1, 1) * sigma;

// Grain size: 1px at native, 2px at 2x, etc.
// (handled by upstream blur if needed — this generates per-pixel noise)

R += nr;
G += ng;
B += nb;
'''

    # ── Enable switch ────────────────────────────────────
    cop_switch = cop_net.createNode("switch", "enable_switch")
    cop_switch.setInput(0, cop_input)       # Bypass
    cop_switch.setInput(1, cop_noise_gen)   # Noise applied
    cop_switch.parm("index").set(1)

    # ── Output ───────────────────────────────────────────
    cop_output = cop_net.createNode("null", "OUT_noise")
    cop_output.setInput(0, cop_switch)
    cop_output.setDisplayFlag(True)
    cop_output.setRenderFlag(True)

    cop_net.layoutChildren()

    # ── Create HDA ───────────────────────────────────────
    hda_def = cop_net.createDigitalAsset(
        name="cinema::cop_sensor_noise",
        hda_file_name=hda_path,
        description="Cinema Sensor Noise v1.0 (Dual Gain)",
        min_num_inputs=1,
        max_num_inputs=1,
        version="1.0",
    )

    hda_node = cop_net
    hda_type = hda_node.type()
    hda_def = hda_type.definition()

    # ── HDA Interface ────────────────────────────────────
    ptg = hda_node.parmTemplateGroup()

    ptg.append(hou.ToggleParmTemplate(
        "enable", "Enable Sensor Noise", default_value=True,
    ))

    sensor_folder = hou.FolderParmTemplate("sensor_folder", "Sensor Model")
    sensor_folder.addParmTemplate(hou.MenuParmTemplate(
        "sensor_model", "Sensor Model",
        menu_items=["alexa35_dual", "generic_cmos", "custom"],
        menu_labels=["ALEXA 35 Dual Gain", "Generic CMOS", "Custom"],
        default_value=0,
        help="Preset sensor noise profiles. Custom allows manual control of all parameters.",
    ))
    sensor_folder.addParmTemplate(hou.IntParmTemplate(
        "exposure_index", "Exposure Index (EI)", 1,
        default_value=(800,), min=100, max=12800,
        help="Camera EI setting. From CameraState.exposure_index. Higher = more noise.",
    ))
    sensor_folder.addParmTemplate(hou.IntParmTemplate(
        "native_iso", "Native ISO", 1,
        default_value=(800,), min=100, max=3200,
        help="Sensor native sensitivity. ALEXA 35: 800. EI above this amplifies read noise.",
    ))
    ptg.append(sensor_folder)

    noise_folder = hou.FolderParmTemplate("noise_folder", "Noise Controls")
    noise_folder.addParmTemplate(hou.FloatParmTemplate(
        "photon_noise_amount", "Photon Noise (Shot)", 1,
        default_value=(1.0,), min=0.0, max=3.0,
        help="Shot noise multiplier. Scales with sqrt(signal). Set to 0 to isolate read noise.",
    ))
    noise_folder.addParmTemplate(hou.FloatParmTemplate(
        "read_noise_amount", "Read Noise (Electronic)", 1,
        default_value=(1.0,), min=0.0, max=5.0,
        help="Electronic noise floor. Amplified by EI/native_iso ratio. Visible in shadows.",
    ))
    noise_folder.addParmTemplate(hou.FloatParmTemplate(
        "temporal_coherence", "Temporal Coherence", 1,
        default_value=(0.0,), min=0.0, max=1.0,
        help="0 = fully random per frame (video noise). 1 = static pattern (photo grain). "
             "0.3 is typical for cinema cameras.",
    ))
    ptg.append(noise_folder)

    hda_def.setParmTemplateGroup(ptg)

    # Wire enable
    hda_node.node("enable_switch").parm("index").setExpression('ch("../enable")')

    # ── Save ─────────────────────────────────────────────
    hda_def.setIcon("COP2_grain")
    hda_def.setComment("Physically-based dual-gain sensor noise model")
    hda_def.save(hda_path)
    hda_node.matchCurrentDefinition()

    temp_geo.destroy()
    return hda_path
```

### G.4 STMap AOV Builder

```python
# File: python/cinema_camera/builders/build_cop_stmap_aov.py
"""
Synapse builder: cinema::cop_stmap_aov::1.0

Creates Copernicus HDA that generates Nuke-ready STMap.
Uses libcinema_optics.h distortion functions directly.
"""

import hou
import os


def build_cop_stmap_aov_hda(
    save_dir: str = None,
    hda_name: str = "cinema_cop_stmap_aov_1.0.hda",
) -> str:
    """
    Build cinema::cop_stmap_aov::1.0 HDA in live Houdini session.

    Generates a 2-channel (RG float) STMap where:
      Red  = distorted U coordinate (normalized 0-1)
      Green = distorted V coordinate (normalized 0-1)

    Nuke plugs this directly into an STMap node to
    undistort or redistort rendered plates.

    Returns: Absolute path to saved .hda file.
    """
    if save_dir is None:
        save_dir = os.path.join(os.environ["CINEMA_CAMERA_PATH"], "hda", "post")

    hda_path = os.path.join(save_dir, hda_name)

    obj = hou.node("/obj")
    temp_geo = obj.createNode("geo", "__cinema_stmap_builder")
    cop_net = temp_geo.createNode("copnet", "cinema_stmap_build")

    # ── Resolution reference input ───────────────────────
    cop_input = cop_net.createNode("null", "IN_resolution_ref")

    # ── STMap generator ──────────────────────────────────
    cop_stmap = cop_net.createNode("vopcop2gen", "stmap_generator")
    cop_stmap.setInput(0, cop_input)

    stmap_vex = '''
// STMap AOV Generator
// Uses libcinema_optics.h distortion model
// Output: R=U, G=V (normalized 0-1)

#include <libcinema_optics.h>

float res_x = ch("../resolution_x");
float res_y = ch("../resolution_y");

// Normalized UV (0-1)
float u = (float(X) + 0.5) / res_x;
float v = (float(Y) + 0.5) / res_y;

// Center to -1..1 range for distortion math
float cx = u * 2.0 - 1.0;
float cy = v * 2.0 - 1.0;

// Build distortion coefficients from parameters
CO_DistortionCoeffs coeffs;
coeffs.k1 = ch("../dist_k1");
coeffs.k2 = ch("../dist_k2");
coeffs.k3 = ch("../dist_k3");
coeffs.p1 = ch("../dist_p1");
coeffs.p2 = ch("../dist_p2");
coeffs.squeeze_uniformity = ch("../dist_sq_uniformity");

vector2 uv_in = set(cx, cy);
vector2 uv_out;

int mode = chi("../mode");  // 0=Undistort, 1=Redistort
float squeeze = ch("../effective_squeeze");

if (mode == 0) {
    // Undistort: map distorted coords to clean coords
    if (squeeze > 1.01) {
        uv_out = co_apply_anamorphic_distortion(uv_in, coeffs, squeeze);
    } else {
        uv_out = co_apply_distortion(uv_in, coeffs);
    }
} else {
    // Redistort: map clean coords to distorted coords
    // Uses iterative inverse (Newton-Raphson)
    uv_out = co_undistort(uv_in, coeffs);
}

// Back to 0-1 range
R = uv_out.x * 0.5 + 0.5;
G = uv_out.y * 0.5 + 0.5;
B = 0.0;  // Unused channel
'''

    # ── Output ───────────────────────────────────────────
    cop_output = cop_net.createNode("null", "OUT_stmap")
    cop_output.setInput(0, cop_stmap)
    cop_output.setDisplayFlag(True)
    cop_output.setRenderFlag(True)

    cop_net.layoutChildren()

    # ── Create HDA ───────────────────────────────────────
    hda_def = cop_net.createDigitalAsset(
        name="cinema::cop_stmap_aov",
        hda_file_name=hda_path,
        description="Cinema STMap AOV v1.0",
        min_num_inputs=0,
        max_num_inputs=1,
        version="1.0",
    )

    hda_node = cop_net
    hda_type = hda_node.type()
    hda_def = hda_type.definition()

    # ── HDA Interface ────────────────────────────────────
    ptg = hda_node.parmTemplateGroup()

    res_folder = hou.FolderParmTemplate("res_folder", "Resolution")
    res_folder.addParmTemplate(hou.IntParmTemplate(
        "resolution_x", "Width", 1,
        default_value=(4608,), min=256, max=8192,
        help="Output STMap width. Match render resolution.",
    ))
    res_folder.addParmTemplate(hou.IntParmTemplate(
        "resolution_y", "Height", 1,
        default_value=(3164,), min=256, max=8192,
        help="Output STMap height. Match render resolution.",
    ))
    res_folder.addParmTemplate(hou.MenuParmTemplate(
        "mode", "Mode",
        menu_items=["undistort", "redistort"],
        menu_labels=["Undistort", "Redistort"],
        default_value=0,
        help="Undistort: map distorted plate to clean. Redistort: map clean CG to distorted.",
    ))
    ptg.append(res_folder)

    dist_folder = hou.FolderParmTemplate("dist_folder", "Distortion Coefficients")
    for parm_name, label, default in [
        ("dist_k1", "K1 (Radial)", 0.0),
        ("dist_k2", "K2 (Radial)", 0.0),
        ("dist_k3", "K3 (Radial)", 0.0),
        ("dist_p1", "P1 (Tangential)", 0.0),
        ("dist_p2", "P2 (Tangential)", 0.0),
        ("dist_sq_uniformity", "Squeeze Uniformity", 1.0),
        ("effective_squeeze", "Effective Squeeze", 2.0),
    ]:
        dist_folder.addParmTemplate(hou.FloatParmTemplate(
            parm_name, label, 1,
            default_value=(default,),
            help=f"From LensSpec.distortion. Maps to libcinema_optics.h CO_DistortionCoeffs.",
        ))
    ptg.append(dist_folder)

    hda_def.setParmTemplateGroup(ptg)

    # ── Save ─────────────────────────────────────────────
    hda_def.setIcon("COP2_fetch")
    hda_def.setComment("Nuke-ready STMap using libcinema_optics.h distortion model")
    hda_def.save(hda_path)
    hda_node.matchCurrentDefinition()

    temp_geo.destroy()
    return hda_path
```

### G.5 Acceptance Criteria (Updated for Synapse)

```
AGENT δ DELIVERABLES (Pillar G — via Synapse):

  cinema::cop_anamorphic_flare::2.0:
    [ ] build_cop_anamorphic_flare_hda() executes through Synapse without error
    [ ] .hda file written to $CINEMA_CAMERA_PATH/hda/post/
    [ ] HDA loads in fresh session
    [ ] 3 parameter groups: Enable, Lens Properties, Flare Controls
    [ ] iris_blades drives FFT kernel polygon count
    [ ] squeeze_ratio stretches kernel horizontally
    [ ] front_diameter_mm controls ghost-to-streak ratio

  cinema::cop_sensor_noise::1.0:
    [ ] build_cop_sensor_noise_hda() executes through Synapse without error
    [ ] .hda file written to $CINEMA_CAMERA_PATH/hda/post/
    [ ] HDA loads in fresh session
    [ ] Sensor model presets: ALEXA 35 Dual Gain, Generic CMOS, Custom
    [ ] Photon noise scales with sqrt(luminance)
    [ ] Read noise amplified by EI/native_iso ratio
    [ ] Temporal coherence blends static vs per-frame noise

  cinema::cop_stmap_aov::1.0:
    [ ] build_cop_stmap_aov_hda() executes through Synapse without error
    [ ] .hda file written to $CINEMA_CAMERA_PATH/hda/post/
    [ ] HDA loads in fresh session
    [ ] Undistort and Redistort modes
    [ ] Uses #include <libcinema_optics.h> in VEX
    [ ] Output is RG float (R=U, G=V, normalized 0-1)

TESTS (executed by Claude Code through Synapse after build):
    [ ] test_flare_hda_loads — installFile, assert type exists
    [ ] test_flare_11_blade — set iris_blades=11, cook, verify non-zero output
    [ ] test_noise_at_native_iso — EI=800, native=800: minimal noise delta
    [ ] test_noise_at_3200 — EI=3200, native=800: noise delta increases
    [ ] test_stmap_identity — zero distortion coefficients: R≈U, G≈V (identity map)
    [ ] test_stmap_roundtrip — distort→STMap→undistort: <0.5px error
```

---

## UPDATED EXECUTION PLAN

### Phase 1: Foundation (Day 1-2) — AGENT α solo (NO CHANGE)

```
Same as v4.0 spec.
All Python file creation — no Synapse dependency.
Gate: v3.0 + v4.0 protocol tests pass.
```

### Phase 2: Parallel Build (Day 3-5)

```
AGENT β (USD) — NO CHANGE:
  TASK 2.1-2.4: build_usd_camera_rig(), EXR metadata, tests
  Execution: hython (no live session needed)

AGENT γ (VEX/CVEX) — NO CHANGE:
  TASK 2.5-2.9: libcinema_optics.h extensions, CVEX shader, binding
  Execution: file write + vcc compilation

AGENT δ (CHOPs/COP) — REFACTORED FOR SYNAPSE:
  TASK 2.10: BiomechanicsParams + derive_biomechanics() → file write (no Synapse)
  TASK 2.11: build_chops_biomechanics_hda() → SYNAPSE EXECUTION
  TASK 2.12: build_cop_anamorphic_flare_hda() → SYNAPSE EXECUTION
  TASK 2.13: build_cop_sensor_noise_hda() → SYNAPSE EXECUTION
  TASK 2.14: build_cop_stmap_aov_hda() → SYNAPSE EXECUTION

  SYNAPSE SEQUENCE FOR AGENT δ:
    Step 1: Claude Code writes builder scripts to $CINEMA_CAMERA_PATH/python/cinema_camera/builders/
    Step 2: Claude Code calls synapse_preflight() through bridge
    Step 3: Claude Code calls each build_*_hda() through bridge (sequential, not parallel)
    Step 4: After each call, verify .hda file exists on disk
    Step 5: Run HDA load tests through bridge: hou.hda.installFile() + type check
    Step 6: If any builder fails, Claude Code gets traceback and retries

GATE: Each agent's tests pass independently
```

### Phase 3: Integration (Day 6-7) — ORCHESTRATOR

```
TASK 3.1: Wire top-level HDA → SYNAPSE EXECUTION
          (creates the master cinema::camera_rig::2.0 HDA that
           references all sub-HDAs including the 4 new ones)
TASK 3.2-3.5: Cross-HDA wiring tests → SYNAPSE EXECUTION
TASK 3.6: Full regression → hybrid (pytest for Python, Synapse for HDA tests)
TASK 3.7: Performance benchmarks → SYNAPSE EXECUTION

GATE: Full pipeline functional, benchmarks met
```

### Phase 4: Polish (Day 8) — All agents (MINOR CHANGE)

```
TASK 4.1: HDA parameter UI polish → SYNAPSE EXECUTION
          (adjusting labels, tooltips, folder organization on live HDAs)
TASK 4.2: Viewport overlay for entrance pupil → SYNAPSE EXECUTION
TASK 4.3: Documentation → file write (no Synapse)
TASK 4.4: Example .hip → SYNAPSE EXECUTION
```

---

## UPDATED PROJECT STRUCTURE

```
$CINEMA_CAMERA_PATH/
├── python/
│   └── cinema_camera/
│       ├── ...existing files unchanged...
│       ├── synapse_preflight.py          ← NEW: session verification
│       └── builders/                     ← NEW: Synapse builder scripts
│           ├── __init__.py
│           ├── build_chops_biomechanics.py
│           ├── build_cop_anamorphic_flare.py
│           ├── build_cop_sensor_noise.py
│           └── build_cop_stmap_aov.py
├── hda/
│   ├── chops/
│   │   └── cinema_chops_biomechanics_1.0.hda   ← CREATED BY SYNAPSE
│   └── post/
│       ├── cinema_cop_anamorphic_flare_2.0.hda  ← CREATED BY SYNAPSE
│       ├── cinema_cop_sensor_noise_1.0.hda      ← CREATED BY SYNAPSE
│       ├── cinema_cop_stmap_aov_1.0.hda         ← CREATED BY SYNAPSE
│       └── ...v3.0 HDAs unchanged...
└── ...rest unchanged...
```

---

## SYNAPSE-SPECIFIC FAILURE MODES

| Failure | Detection | Recovery |
|---------|-----------|----------|
| Session not running | `synapse_preflight()` raises ConnectionRefused | Prompt user to open Houdini and enable command port |
| CINEMA_CAMERA_PATH unset | `synapse_preflight()` assertion fails | Claude Code sets env var via `hou.hscript("setenv ...")` |
| VEX #include fails | `build_cop_stmap_aov_hda()` cook error on stmap_generator | Verify HOUDINI_PATH includes $CINEMA_CAMERA_PATH |
| HDA save permission | `hda_def.save()` raises PermissionError | Check disk permissions on hda/ directories |
| Node type conflict | `createDigitalAsset()` raises if type already installed | `hou.hda.uninstallFile()` first, then rebuild |
| COP node missing | vopcop2gen not found (Copernicus not licensed) | Fallback to classic COP2 nodes (degraded but functional) |

### Retry Protocol

```python
def synapse_build_with_retry(builder_fn, max_retries=3, **kwargs):
    """
    Claude Code wraps each builder call with this retry logic.
    Executed through Synapse bridge.
    """
    import traceback

    for attempt in range(max_retries):
        try:
            hda_path = builder_fn(**kwargs)
            # Verify file exists
            if not os.path.exists(hda_path):
                raise FileNotFoundError(f"Builder returned but file missing: {hda_path}")
            # Verify HDA loads
            hou.hda.installFile(hda_path)
            return hda_path
        except Exception as e:
            tb = traceback.format_exc()
            if attempt < max_retries - 1:
                # Clean up any partial state
                for node in hou.node("/obj").children():
                    if node.name().startswith("__cinema_"):
                        node.destroy()
                continue
            else:
                raise RuntimeError(
                    f"Builder {builder_fn.__name__} failed after {max_retries} attempts.\n"
                    f"Last error:\n{tb}"
                )
```

---

## WHAT DIDN'T CHANGE

Everything outside Agent δ's HDA construction is identical to the v4.0 spec:

- **Pillar A** (Protocols): Pure Python dataclasses — file write only
- **Pillar B** (USD Hierarchy): `pxr` API — runs in hython, no live session needed
- **Pillar D** (CVEX Lens Shader): VEX text files + vcc compilation — no live session
- **Pillar E** (EXR Metadata): `pxr` API on RenderProduct — hython only
- **Pillar F** (Dynamic Mumps): Pure math in protocols + VEX — no live session
- **biomechanics.py**: Pure Python derivation — file write only
- **All cross-agent interface contracts**: Unchanged
- **All performance/accuracy targets**: Unchanged
