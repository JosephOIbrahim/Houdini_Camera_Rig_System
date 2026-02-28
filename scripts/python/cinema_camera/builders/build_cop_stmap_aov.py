"""
Cinema Camera Rig v4.0 -- COP STMap AOV HDA Builder

Creates cinema::cop_stmap_aov::1.0
Nuke-ready STMap using libcinema_optics.h distortion model.

Executed through Synapse bridge in a live Houdini session.
"""

from __future__ import annotations

import os


# VEX: STMap generator using libcinema_optics.h
_STMAP_VEX = '''
#include <libcinema_optics.h>

float res_x = ch("../../resolution_x");
float res_y = ch("../../resolution_y");

// Normalized UV (0-1)
float u = (float(X) + 0.5) / res_x;
float v = (float(Y) + 0.5) / res_y;

// Center to -1..1 range for distortion math
float cx = u * 2.0 - 1.0;
float cy = v * 2.0 - 1.0;

// Build distortion coefficients from parameters
CO_DistortionCoeffs coeffs;
coeffs.k1 = ch("../../dist_k1");
coeffs.k2 = ch("../../dist_k2");
coeffs.k3 = ch("../../dist_k3");
coeffs.p1 = ch("../../dist_p1");
coeffs.p2 = ch("../../dist_p2");
coeffs.squeeze_uniformity = ch("../../dist_sq_uniformity");

vector2 uv_in = set(cx, cy);
vector2 uv_out;

int mode = chi("../../mode");
float squeeze = ch("../../effective_squeeze");

if (mode == 0) {
    // Undistort: map distorted coords to clean coords
    if (squeeze > 1.01) {
        uv_out = co_apply_anamorphic_distortion(uv_in, coeffs, squeeze);
    } else {
        uv_out = co_apply_distortion(uv_in, coeffs);
    }
} else {
    // Redistort: map clean coords to distorted coords (Newton-Raphson)
    uv_out = co_undistort(uv_in, coeffs);
}

// Back to 0-1 range
R = uv_out.x * 0.5 + 0.5;
G = uv_out.y * 0.5 + 0.5;
B = 0.0;
'''


def build_cop_stmap_aov_hda(
    save_dir: str = None,
    hda_name: str = "cinema_cop_stmap_aov_1.0.hda",
) -> str:
    """
    Build the COP STMap AOV HDA and save to disk.
    Returns absolute path to saved .hda file.
    """
    import hou

    if save_dir is None:
        cinema_path = os.environ.get("CINEMA_CAMERA_PATH", "")
        save_dir = os.path.join(cinema_path, "hda", "post")
    os.makedirs(save_dir, exist_ok=True)

    # ── Create temporary COP network ─────────────────────
    obj = hou.node("/obj")
    temp_cop = obj.createNode("cop2net", "__cinema_stmap_build")

    # Build inside a subnet
    sub = temp_cop.createNode("subnet", "__stmap_sub")

    # Optional resolution reference input
    in_ref = sub.createNode("null", "IN_resolution_ref")

    # STMap generator (vopcop2gen + snippet VOP)
    stmap_gen = sub.createNode("vopcop2gen", "stmap_generator")
    stmap_snippet = stmap_gen.createNode("snippet", "stmap_vex")
    stmap_snippet.parm("code").set(_STMAP_VEX)

    # Output
    out = sub.createNode("null", "OUT_stmap")
    out.setInput(0, stmap_gen)
    out.setDisplayFlag(True)

    sub.layoutChildren()

    # ── Convert subnet to HDA ──────────────────────────────
    hda_path = os.path.join(save_dir, hda_name)
    hda_node = sub.createDigitalAsset(
        name="cinema::cop_stmap_aov",
        hda_file_name=hda_path,
        description="Cinema STMap AOV",
        min_num_inputs=0,
        max_num_inputs=1,
        version="1.0",
    )
    hda_def = hda_node.type().definition()

    # ── Parameter interface ──────────────────────────────
    ptg = hda_node.parmTemplateGroup()

    # Folder: Resolution
    res_folder = hou.FolderParmTemplate("resolution_folder", "Resolution")
    res_folder.addParmTemplate(hou.IntParmTemplate(
        "resolution_x", "Resolution X", 1,
        default_value=(4608,), min=256, max=8192,
        help="Output STMap width. Match render resolution.",
    ))
    res_folder.addParmTemplate(hou.IntParmTemplate(
        "resolution_y", "Resolution Y", 1,
        default_value=(3164,), min=256, max=8192,
        help="Output STMap height. Match render resolution.",
    ))
    res_folder.addParmTemplate(hou.MenuParmTemplate(
        "mode", "Mode",
        menu_items=("undistort", "redistort"),
        menu_labels=("Undistort", "Redistort"),
        default_value=0,
        help="Undistort: distorted plate to clean. Redistort: clean CG to distorted.",
    ))
    ptg.append(res_folder)

    # Folder: Distortion Coefficients
    dist_folder = hou.FolderParmTemplate("distortion_folder", "Distortion Coefficients")
    dist_folder.addParmTemplate(hou.FloatParmTemplate(
        "dist_k1", "K1 (Radial)", 1,
        default_value=(0.0,),
        help="From LensSpec.distortion. Maps to CO_DistortionCoeffs.k1.",
    ))
    dist_folder.addParmTemplate(hou.FloatParmTemplate(
        "dist_k2", "K2 (Radial)", 1,
        default_value=(0.0,),
        help="Higher-order radial distortion.",
    ))
    dist_folder.addParmTemplate(hou.FloatParmTemplate(
        "dist_k3", "K3 (Radial)", 1,
        default_value=(0.0,),
        help="Highest-order radial distortion.",
    ))
    dist_folder.addParmTemplate(hou.FloatParmTemplate(
        "dist_p1", "P1 (Tangential)", 1,
        default_value=(0.0,),
        help="Tangential distortion.",
    ))
    dist_folder.addParmTemplate(hou.FloatParmTemplate(
        "dist_p2", "P2 (Tangential)", 1,
        default_value=(0.0,),
        help="Tangential distortion.",
    ))
    dist_folder.addParmTemplate(hou.FloatParmTemplate(
        "dist_sq_uniformity", "Squeeze Uniformity", 1,
        default_value=(1.0,), min=0.8, max=1.0,
        help="1.0=perfect, <1.0=squeeze varies across frame.",
    ))
    dist_folder.addParmTemplate(hou.FloatParmTemplate(
        "effective_squeeze", "Effective Squeeze", 1,
        default_value=(2.0,), min=1.0, max=2.5,
        help="Dynamic squeeze at current focus distance.",
    ))
    ptg.append(dist_folder)

    hda_def.setParmTemplateGroup(ptg)

    # ── HDA metadata ─────────────────────────────────────
    hda_def.setIcon("COP2_fetch")
    hda_def.setComment(
        "Nuke-ready STMap using libcinema_optics.h distortion model"
    )

    # ── Save and clean up ────────────────────────────────
    hda_def.updateFromNode(hda_node)
    hda_def.save(hda_path)
    hda_node.destroy()
    temp_cop.destroy()

    return hda_path
