"""
Cinema Camera Rig v3.0 -- Copernicus 2.0 STMap AOV HDA Builder

Creates cinema::stmap_aov::3.0 in the cop (Copernicus 2.0) category.
Generates a Nuke/Flame-ready STMap encoding lens distortion.

SUPERSEDED / DO NOT WIRE. This Copernicus preview reimplements the distortion
math in a pure-Python per-pixel snippet (_STMAP_PYTHON) that DIVERGED from the
render: it centered each axis independently (no aspect/dn normalization) and
used the old forward Brown-Conrady, so a plate undistorted with it would not
re-register on the Karma render. The authoritative, dn-consistent ST-map is
now the cop2 builder (build_cop_stmap_aov.py -> cinema::cop_stmap_aov), which
calls the SHARED co_stmap_pixel from libcinema_optics.h -- byte-identical to
karma_cinema_lens.vfl. That is the node wired into the orchestrator.

To revive this as the Copernicus path, rebuild it as a VEX Copernicus node
(vopnet + snippet) that #includes libcinema_optics.h and calls co_stmap_pixel
/ co_stmap_pixel_anamorphic (the builder's original TODO) -- do NOT re-port the
math to Python. The _STMAP_PYTHON below is retained only as the historical MVP.
"""

from __future__ import annotations

import os
import textwrap


# Python pixel script (executed by the pythonsnippet COP).
# Fills R, G with normalized UV coords after distortion; B = 0.
# Reads HDA parms via direct parent walk: snippet -> subnet -> HDA.
_STMAP_PYTHON = textwrap.dedent("""\
    # Cinema STMap (Copernicus 2.0 pythonsnippet)
    #
    # Standard pythonsnippet provides per-pixel access to the framebuffer.
    # Variables: x, y, R, G, B, A, width, height, frame
    # Reads HDA-level parms via direct ancestor walk.
    import math

    # Direct ancestor walk: pythonsnippet sits inside the subnet that *is* the
    # HDA contents. Walk up to the first node whose type is the HDA op type.
    # Sentinel via type name -- safer than matching on a parm name (which any
    # ancestor could spoof) and bounded (no risk of walking past the HDA).
    hda = hou.pwd().parent()
    while hda is not None and "stmap_aov" not in hda.type().name():
        hda = hda.parent()

    if hda is None:
        # Defensive fallback -- pass-through identity STMap
        u = (x + 0.5) / max(width, 1)
        v = (y + 0.5) / max(height, 1)
        R = u
        G = v
        B = 0.0
    else:
        k1 = hda.evalParm("dist_k1") or 0.0
        k2 = hda.evalParm("dist_k2") or 0.0
        k3 = hda.evalParm("dist_k3") or 0.0
        p1 = hda.evalParm("dist_p1") or 0.0
        p2 = hda.evalParm("dist_p2") or 0.0
        sq_uniformity = hda.evalParm("dist_sq_uniformity")
        if sq_uniformity is None:
            sq_uniformity = 1.0
        squeeze = hda.evalParm("effective_squeeze") or 1.0

        u = (x + 0.5) / max(width, 1)
        v = (y + 0.5) / max(height, 1)

        # Center to -1..1
        cx = u * 2.0 - 1.0
        cy = v * 2.0 - 1.0

        # Squeeze uniformity: squeeze relaxes toward edges when uniformity<1.
        # 1.0 = perfectly uniform squeeze; <1.0 = squeeze magnitude decreases
        # with radial distance from center (linear in r^2 falloff approximation).
        r2_pre = cx*cx + cy*cy
        local_squeeze = 1.0 + (squeeze - 1.0) * (1.0 - (1.0 - sq_uniformity) * r2_pre)

        # Anamorphic squeeze applied to X
        if local_squeeze > 1.01:
            cx_sq = cx / local_squeeze
        else:
            cx_sq = cx

        # Brown-Conrady forward distortion
        r2 = cx_sq*cx_sq + cy*cy
        r4 = r2*r2
        r6 = r4*r2
        radial = 1.0 + k1*r2 + k2*r4 + k3*r6

        x_dist = cx_sq * radial + 2.0*p1*cx_sq*cy + p2*(r2 + 2.0*cx_sq*cx_sq)
        y_dist = cy     * radial + p1*(r2 + 2.0*cy*cy) + 2.0*p2*cx_sq*cy

        # Reapply local squeeze on output X
        if local_squeeze > 1.01:
            x_dist = x_dist * local_squeeze

        # Back to 0..1
        R = x_dist * 0.5 + 0.5
        G = y_dist * 0.5 + 0.5
        B = 0.0
""")


def _wire(node, sub_parm: str, expr: str) -> None:
    try:
        p = node.parm(sub_parm)
        if p is not None:
            p.setExpression(expr)
    except Exception:
        pass


def build_cop_stmap_aov_v2_hda(
    save_dir: str = None,
    hda_name: str = "cinema_stmap_aov_3.0.hda",
) -> str:
    """Build the Copernicus 2.0 STMap AOV HDA. Returns absolute hda path."""
    import hou

    if save_dir is None:
        repo = os.environ.get("CINEMA_CAMERA_REPO")
        if repo:
            save_dir = os.path.join(repo, "otls")
        else:
            save_dir = os.path.join(os.environ["CINEMA_CAMERA_PATH"], "hda", "post")
    os.makedirs(save_dir, exist_ok=True)

    obj = hou.node("/obj")
    temp_geo = obj.createNode("geo", "__cinema_stmap_v2_build")
    try:
        return _build_stmap_inside(temp_geo, save_dir, hda_name)
    finally:
        try:
            temp_geo.destroy()
        except Exception:
            pass


def _build_stmap_inside(temp_geo, save_dir: str, hda_name: str) -> str:
    """Inner builder; isolated so caller can wrap in try/finally cleanup."""
    import hou

    temp_cop = temp_geo.createNode("copnet", "__stmap_cop")
    sub = temp_cop.createNode("subnet", "__stmap_sub")

    # ── Build chain ────────────────────────────────────────
    # STMap is a pure GENERATOR -- no upstream input is read. Resolution is
    # driven by resolution_x / resolution_y parms, which feed the constant bg.
    # Constant background seeds image dims for the snippet to write into.
    bg = sub.createNode("constant", "stmap_bg")

    # Python snippet generator: writes per-pixel STMap values
    snippet = sub.createNode("pythonsnippet", "stmap_python")
    snippet.setInput(0, bg)

    # Try to set the python code on the snippet
    for parm_name in ("python", "code", "snippet", "script"):
        try:
            p = snippet.parm(parm_name)
            if p is not None:
                p.set(_STMAP_PYTHON)
                break
        except Exception:
            pass

    out = sub.createNode("null", "OUT_stmap")
    out.setInput(0, snippet)
    out.setDisplayFlag(True)

    sub.layoutChildren()

    # ── Convert to HDA ────────────────────────────────────
    # max_num_inputs=0 -- STMap is a pure generator; no upstream is used.
    hda_path = os.path.join(save_dir, hda_name)
    hda_node = sub.createDigitalAsset(
        name="cinema::stmap_aov::3.0",
        hda_file_name=hda_path,
        description="Cinema STMap AOV (Copernicus 2.0)",
        min_num_inputs=0,
        max_num_inputs=0,
        version="3.0",
    )
    hda_def = hda_node.type().definition()

    # ── Parm interface ────────────────────────────────────
    ptg = hda_node.parmTemplateGroup()

    res_folder = hou.FolderParmTemplate("resolution_folder", "Resolution")
    res_folder.addParmTemplate(hou.IntParmTemplate(
        "resolution_x", "Resolution X", 1,
        default_value=(4608,), min=256, max=8192,
    ))
    res_folder.addParmTemplate(hou.IntParmTemplate(
        "resolution_y", "Resolution Y", 1,
        default_value=(3164,), min=256, max=8192,
    ))
    ptg.append(res_folder)

    dist_folder = hou.FolderParmTemplate("distortion_folder", "Distortion")
    for parm_name, label, default in [
        ("dist_k1", "K1 (Radial)", 0.0),
        ("dist_k2", "K2 (Radial)", 0.0),
        ("dist_k3", "K3 (Radial)", 0.0),
        ("dist_p1", "P1 (Tangential)", 0.0),
        ("dist_p2", "P2 (Tangential)", 0.0),
        ("dist_sq_uniformity", "Squeeze Uniformity", 1.0),
    ]:
        dist_folder.addParmTemplate(hou.FloatParmTemplate(
            parm_name, label, 1, default_value=(default,),
        ))
    ptg.append(dist_folder)

    aname_folder = hou.FolderParmTemplate("anamorphic_folder", "Anamorphic")
    aname_folder.addParmTemplate(hou.FloatParmTemplate(
        "effective_squeeze", "Effective Squeeze", 1,
        default_value=(2.0,), min=1.0, max=2.0,
        help="Effective squeeze ratio (focus-dependent). Drives the "
             "horizontal pre/post-multiplication around the distortion.",
    ))
    ptg.append(aname_folder)

    hda_def.setParmTemplateGroup(ptg)

    # ── Wire constant bg dimensions to HDA resolution parms ──
    for parm_pair in (("imgsizex", "resolution_x"),
                      ("imgsizey", "resolution_y"),
                      ("sizex",    "resolution_x"),
                      ("sizey",    "resolution_y")):
        _wire(bg, parm_pair[0], 'ch("../{}")'.format(parm_pair[1]))

    # ── HDA metadata ──────────────────────────────────────
    hda_def.setIcon("COP2_optics")
    hda_def.setComment(
        "Cinema STMap AOV v3.0 (Copernicus 2.0)\n"
        "Brown-Conrady distortion + anamorphic squeeze, per-pixel Python.\n"
        "Output: R = distorted_u, G = distorted_v, B = 0."
    )
    hda_def.setExtraInfo(
        "Cinema Camera Rig v3.0 -- Pillar G (Copernicus 2.0)\n"
        "Chain: constant -> pythonsnippet (STMap math) -> output\n"
        "Pure generator (no upstream input). Resolution driven by parms.\n"
        "Preview MVP: parity with legacy cinema::cop_stmap_aov::3.0 except\n"
        "redistort/Newton-Raphson mode not yet ported.\n"
        "TODO: port to vopnet+snippet for GPU acceleration."
    )

    hda_def.updateFromNode(hda_node)
    hda_def.save(hda_path)
    hda_node.matchCurrentDefinition()

    return hda_path
