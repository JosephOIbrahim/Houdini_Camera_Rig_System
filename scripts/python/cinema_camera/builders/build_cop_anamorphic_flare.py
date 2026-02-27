"""
Cinema Camera Rig v4.0 -- COP Anamorphic Flare HDA Builder

Creates cinema::cop_anamorphic_flare::2.0
FFT convolution lens flare with physically accurate iris patterns.

Executed through Synapse bridge in a live Houdini session.
"""

from __future__ import annotations

import os


# VEX: Threshold bright pixels for flare source
_THRESHOLD_VEX = '''
float lum = luminance(set(R, G, B));
float threshold = ch("../../threshold");
float mask = smooth(threshold - 0.1, threshold + 0.1, lum);
R *= mask;
G *= mask;
B *= mask;
'''

# VEX: Generate iris kernel for FFT convolution
_IRIS_KERNEL_VEX = '''
int blades = chi("../../iris_blades");
float squeeze = ch("../../squeeze_ratio");
float intensity = ch("../../intensity");

float cx = (float(X) / float(XRES)) * 2.0 - 1.0;
float cy = (float(Y) / float(YRES)) * 2.0 - 1.0;
cx /= max(squeeze, 0.01);

float r = sqrt(cx*cx + cy*cy);
float theta = atan2(cy, cx);

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


def build_cop_anamorphic_flare_hda(
    save_dir: str = None,
    hda_name: str = "cinema_cop_anamorphic_flare_2.0.hda",
) -> str:
    """
    Build the COP anamorphic flare HDA and save to disk.
    Returns absolute path to saved .hda file.
    """
    import hou

    if save_dir is None:
        cinema_path = os.environ.get("CINEMA_CAMERA_PATH", "")
        save_dir = os.path.join(cinema_path, "hda", "post")
    os.makedirs(save_dir, exist_ok=True)

    # ── Create temporary COP network ─────────────────────
    obj = hou.node("/obj")
    temp_cop = obj.createNode("cop2net", "__cinema_flare_build")

    # Build inside a subnet (subnet can be converted to HDA)
    sub = temp_cop.createNode("subnet", "__flare_sub")

    # Input image
    in_image = sub.createNode("null", "IN_image")

    # Bright pixel extraction (vopcop2filter + snippet VOP)
    bright_extract = sub.createNode("vopcop2filter", "bright_extract")
    bright_snippet = bright_extract.createNode("snippet", "threshold_vex")
    bright_snippet.parm("code").set(_THRESHOLD_VEX)
    bright_extract.setInput(0, in_image)

    # Iris kernel generation (vopcop2gen + snippet VOP)
    iris_kernel = sub.createNode("vopcop2gen", "iris_kernel")
    iris_snippet = iris_kernel.createNode("snippet", "iris_vex")
    iris_snippet.parm("code").set(_IRIS_KERNEL_VEX)

    # FFT convolution
    fft_convolve = sub.createNode("convolve", "fft_convolve")
    fft_convolve.setInput(0, bright_extract)
    fft_convolve.setInput(1, iris_kernel)

    # Anamorphic horizontal streak
    anamorphic_streak = sub.createNode("streak", "anamorphic_streak")
    anamorphic_streak.parm("size").set(50)
    anamorphic_streak.parm("rot").set(0)  # Horizontal
    anamorphic_streak.setInput(0, fft_convolve)

    # Composite flare over original (additive blend)
    flare_over = sub.createNode("add", "flare_add")
    flare_over.setInput(0, in_image)
    flare_over.setInput(1, anamorphic_streak)

    # Enable/disable switch
    enable_switch = sub.createNode("switch", "enable_switch")
    enable_switch.parm("index").setExpression('ch("../enable")')
    enable_switch.setInput(0, in_image)      # Off: passthrough
    enable_switch.setInput(1, flare_over)    # On: flare applied

    # Output
    out = sub.createNode("null", "OUT_flare")
    out.setInput(0, enable_switch)
    out.setDisplayFlag(True)

    sub.layoutChildren()

    # ── Convert subnet to HDA ──────────────────────────────
    hda_path = os.path.join(save_dir, hda_name)
    hda_node = sub.createDigitalAsset(
        name="cinema::cop_anamorphic_flare",
        hda_file_name=hda_path,
        description="Cinema Anamorphic Flare",
        min_num_inputs=1,
        max_num_inputs=1,
        version="2.0",
    )
    hda_def = hda_node.type().definition()

    # ── Parameter interface ──────────────────────────────
    ptg = hda_node.parmTemplateGroup()

    ptg.append(hou.ToggleParmTemplate(
        "enable", "Enable Flare", default_value=True,
    ))

    # Folder: Lens Properties
    lens_folder = hou.FolderParmTemplate("lens_folder", "Lens Properties")
    lens_folder.addParmTemplate(hou.IntParmTemplate(
        "iris_blades", "Iris Blades", 1,
        default_value=(11,), min=3, max=18,
        help="Number of iris diaphragm blades. Cooke: 11.",
    ))
    lens_folder.addParmTemplate(hou.FloatParmTemplate(
        "front_diameter_mm", "Front Diameter (mm)", 1,
        default_value=(110.0,), min=30.0, max=200.0,
        help="Front element diameter from MechanicalSpec.",
    ))
    lens_folder.addParmTemplate(hou.FloatParmTemplate(
        "squeeze_ratio", "Squeeze Ratio", 1,
        default_value=(2.0,), min=1.0, max=2.0,
        help="Effective anamorphic squeeze. Reads from cinema:rig:effectiveSqueeze.",
    ))
    ptg.append(lens_folder)

    # Folder: Flare Controls
    flare_folder = hou.FolderParmTemplate("flare_folder", "Flare Controls")
    flare_folder.addParmTemplate(hou.FloatParmTemplate(
        "threshold", "Threshold", 1,
        default_value=(3.0,), min=0.5, max=20.0,
        help="Minimum pixel luminance to trigger flare.",
    ))
    flare_folder.addParmTemplate(hou.FloatParmTemplate(
        "intensity", "Intensity", 1,
        default_value=(0.3,), min=0.0, max=2.0,
        help="Global flare strength multiplier.",
    ))
    flare_folder.addParmTemplate(hou.IntParmTemplate(
        "ghosting_rings", "Ghosting Rings", 1,
        default_value=(3,), min=0, max=8,
        help="Number of internal reflection ghost images.",
    ))
    flare_folder.addParmTemplate(hou.FloatParmTemplate(
        "streak_asymmetry", "Streak Asymmetry", 1,
        default_value=(0.8,), min=0.0, max=1.0,
        help="0=symmetric, 1=full anamorphic horizontal bias.",
    ))
    ptg.append(flare_folder)

    hda_node.setParmTemplateGroup(ptg)

    # ── HDA metadata ─────────────────────────────────────
    hda_def.setIcon("COP2_contrast")
    hda_def.setComment(
        "FFT convolution lens flare with physically accurate iris patterns"
    )

    # ── Save and clean up ────────────────────────────────
    hda_def.save(hda_path)
    hda_node.destroy()
    temp_cop.destroy()

    return hda_path
