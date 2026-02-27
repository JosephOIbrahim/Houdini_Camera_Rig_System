"""
Cinema Camera Rig v4.0 -- COP Sensor Noise HDA Builder

Creates cinema::cop_sensor_noise::1.0
Physically-based dual-gain sensor noise model.

Executed through Synapse bridge in a live Houdini session.
"""

from __future__ import annotations

import os


# VEX: Dual-gain sensor noise model
_DUAL_GAIN_NOISE_VEX = '''
float ei = ch("../../exposure_index");
float native = ch("../../native_iso");
float photon_amt = ch("../../photon_noise_amount");
float read_amt = ch("../../read_noise_amount");
float temporal = ch("../../temporal_coherence");

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
float seed_r = random(set(X, Y, @Frame * 1.0));
float seed_g = random(set(X, Y, @Frame * 2.0));
float seed_b = random(set(X, Y, @Frame * 3.0));

// Temporal coherence: blend between per-frame and static
float static_r = random(set(X, Y, 0.0));
float static_g = random(set(X, Y, 1.0));
float static_b = random(set(X, Y, 2.0));

float nr = fit01(lerp(seed_r, static_r, temporal), -1, 1) * sigma;
float ng = fit01(lerp(seed_g, static_g, temporal), -1, 1) * sigma * 0.707;
float nb = fit01(lerp(seed_b, static_b, temporal), -1, 1) * sigma;

R += nr;
G += ng;
B += nb;
'''


def build_cop_sensor_noise_hda(
    save_dir: str = None,
    hda_name: str = "cinema_cop_sensor_noise_1.0.hda",
) -> str:
    """
    Build the COP sensor noise HDA and save to disk.
    Returns absolute path to saved .hda file.
    """
    import hou

    if save_dir is None:
        cinema_path = os.environ.get("CINEMA_CAMERA_PATH", "")
        save_dir = os.path.join(cinema_path, "hda", "post")
    os.makedirs(save_dir, exist_ok=True)

    # ── Create temporary COP network ─────────────────────
    obj = hou.node("/obj")
    temp_cop = obj.createNode("cop2net", "__cinema_noise_build")

    # Build inside a subnet
    sub = temp_cop.createNode("subnet", "__noise_sub")

    # Input image
    in_image = sub.createNode("null", "IN_image")

    # Dual-gain noise filter (vopcop2filter + snippet VOP)
    dual_gain_noise = sub.createNode("vopcop2filter", "dual_gain_noise")
    noise_snippet = dual_gain_noise.createNode("snippet", "noise_vex")
    noise_snippet.parm("code").set(_DUAL_GAIN_NOISE_VEX)
    dual_gain_noise.setInput(0, in_image)

    # Enable/disable switch
    enable_switch = sub.createNode("switch", "enable_switch")
    enable_switch.parm("index").setExpression('ch("../enable")')
    enable_switch.setInput(0, in_image)         # Off: passthrough
    enable_switch.setInput(1, dual_gain_noise)  # On: noise applied

    # Output
    out = sub.createNode("null", "OUT_noise")
    out.setInput(0, enable_switch)
    out.setDisplayFlag(True)

    sub.layoutChildren()

    # ── Convert subnet to HDA ──────────────────────────────
    hda_path = os.path.join(save_dir, hda_name)
    hda_node = sub.createDigitalAsset(
        name="cinema::cop_sensor_noise",
        hda_file_name=hda_path,
        description="Cinema Sensor Noise",
        min_num_inputs=1,
        max_num_inputs=1,
        version="1.0",
    )
    hda_def = hda_node.type().definition()

    # ── Parameter interface ──────────────────────────────
    ptg = hda_node.parmTemplateGroup()

    ptg.append(hou.ToggleParmTemplate(
        "enable", "Enable Noise", default_value=True,
    ))

    # Folder: Sensor Model
    sensor_folder = hou.FolderParmTemplate("sensor_folder", "Sensor Model")
    sensor_folder.addParmTemplate(hou.MenuParmTemplate(
        "sensor_model", "Sensor Model",
        menu_items=("alexa35_dual", "generic_cmos", "custom"),
        menu_labels=("ALEXA 35 Dual Gain", "Generic CMOS", "Custom"),
        default_value=0,
        help="Preset sensor noise profiles.",
    ))
    sensor_folder.addParmTemplate(hou.IntParmTemplate(
        "exposure_index", "Exposure Index", 1,
        default_value=(800,), min=100, max=12800,
        help="Camera EI setting. Higher = more noise.",
    ))
    sensor_folder.addParmTemplate(hou.IntParmTemplate(
        "native_iso", "Native ISO", 1,
        default_value=(800,), min=100, max=3200,
        help="Sensor native sensitivity. ALEXA 35: 800.",
    ))
    ptg.append(sensor_folder)

    # Folder: Noise Controls
    noise_folder = hou.FolderParmTemplate("noise_folder", "Noise Controls")
    noise_folder.addParmTemplate(hou.FloatParmTemplate(
        "photon_noise_amount", "Photon Noise", 1,
        default_value=(1.0,), min=0.0, max=3.0,
        help="Shot noise multiplier. Scales with sqrt(signal).",
    ))
    noise_folder.addParmTemplate(hou.FloatParmTemplate(
        "read_noise_amount", "Read Noise", 1,
        default_value=(1.0,), min=0.0, max=5.0,
        help="Electronic noise floor. Amplified by EI/native ratio.",
    ))
    noise_folder.addParmTemplate(hou.FloatParmTemplate(
        "temporal_coherence", "Temporal Coherence", 1,
        default_value=(0.0,), min=0.0, max=1.0,
        help="0=random per frame (video). 1=static (photo grain). 0.3=cinema.",
    ))
    ptg.append(noise_folder)

    hda_node.setParmTemplateGroup(ptg)

    # ── HDA metadata ─────────────────────────────────────
    hda_def.setIcon("COP2_grain")
    hda_def.setComment(
        "Physically-based dual-gain sensor noise model"
    )

    # ── Save and clean up ────────────────────────────────
    hda_def.save(hda_path)
    hda_node.destroy()
    temp_cop.destroy()

    return hda_path
