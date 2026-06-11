"""
Cinema Camera Rig v4.0 -- Solaris/LOP HDA Builder

Creates cinema::camera_rig_lop::3.0 — a native Solaris LOP HDA that:
  - Authors the full nodal-parallax USD Xform hierarchy
  - Configures Karma RenderProduct with Cooke /i + ASWF EXR metadata
  - Binds the Karma CVEX lens shader (karma:camera:lensshader opdef)
  - Configures Karma render settings (camera relationship + resolution)
  - Exposes the same tabbed parameter interface as the OBJ version

Every Python Script LOP inside the HDA is a thin shim over
cinema_camera.hda_runtime -- ALL cook-time logic lives in the package
(usd_builder / optics_engine / biomechanics / karma_lens_shader), so the
tested code is the shipping code. Do not inline logic in these strings.
"""

from __future__ import annotations

import os
import textwrap

from .parm_templates import build_camera_rig_parm_templates


# ════════════════════════════════════════════════════════════
# EMBEDDED PYTHON SCRIPTS FOR LOP NODES (shims over hda_runtime)
# ════════════════════════════════════════════════════════════

_BOOTSTRAP = textwrap.dedent("""\
    # Shim over cinema_camera.hda_runtime -- logic lives in the package.
    import os, sys
    _repo = os.environ.get("CINEMA_CAMERA_REPO", "")
    if _repo:
        _sp = os.path.join(_repo, "scripts", "python")
        if _sp not in sys.path:
            sys.path.insert(0, _sp)
    from cinema_camera import hda_runtime
""")

_SCRIPT_BUILD_RIG = _BOOTSTRAP + "hda_runtime.author_camera_rig(hou.pwd())\n"
_SCRIPT_APPLY_BIOMECHANICS = _BOOTSTRAP + "hda_runtime.apply_biomechanics(hou.pwd())\n"
_SCRIPT_LENS_SHADER = _BOOTSTRAP + "hda_runtime.author_lens_shader(hou.pwd())\n"
_SCRIPT_RENDER_PRODUCT = _BOOTSTRAP + "hda_runtime.author_render_product(hou.pwd())\n"
_SCRIPT_RENDER_SETTINGS = _BOOTSTRAP + "hda_runtime.author_render_settings(hou.pwd())\n"


# ════════════════════════════════════════════════════════════
# LOP HDA BUILDER
# ════════════════════════════════════════════════════════════

def build_camera_rig_lop_hda(
    save_dir: str = None,
    hda_name: str = "cinema_camera_rig_lop_3.0.hda",
) -> str:
    """
    Build cinema::camera_rig_lop::3.0 LOP HDA in live Houdini session.

    Creates a Solaris-native camera rig that authors the full USD Xform
    hierarchy, Karma lens shader binding, RenderProduct with Cooke /i
    metadata, and RenderSettings.

    Internal LOP network (each node a shim over cinema_camera.hda_runtime):
      1. Python Script LOP -- builds USD camera rig hierarchy
      2. Python Script LOP -- applies biomechanics (spring/lag/shake)
      3. Python Script LOP -- binds Karma CVEX lens shader
      4. Python Script LOP -- configures RenderProduct with EXR metadata
      5. Python Script LOP -- configures Karma RenderSettings

    Returns: Absolute path to saved .hda file.
    """
    import hou

    if save_dir is None:
        # v3.0: consolidate into <repo>/otls/ (Houdini auto-scans).
        repo = os.environ.get("CINEMA_CAMERA_REPO")
        if repo:
            save_dir = os.path.join(repo, "otls")
        else:
            save_dir = os.path.join(os.environ["CINEMA_CAMERA_PATH"], "hda")
        os.makedirs(save_dir, exist_ok=True)

    hda_path = os.path.join(save_dir, hda_name)

    # ── 1. Create temporary LOP container ──────────────────
    # Find or create a lopnet to host the builder
    stage_net = hou.node("/stage")
    if stage_net is None:
        stage_net = hou.node("/obj").createNode("lopnet", "stage")

    temp_subnet = stage_net.createNode("subnet", "__cinema_rig_lop_builder")
    temp_subnet.moveToGoodPosition()

    # ── 2. Python Script LOP: Build USD camera rig ─────────
    ps_rig = temp_subnet.createNode("pythonscript", "build_camera_rig")
    # Wire the HDA's (optional) input into the chain head so an upstream
    # stage flows through -- without this, input_camera_path can never see
    # upstream prims and the HDA silently ignores its input.
    indirect = temp_subnet.indirectInputs()
    if indirect:
        ps_rig.setInput(0, indirect[0])
    ps_rig.parm("python").set(_SCRIPT_BUILD_RIG)
    ps_rig.setComment(
        "Cinema Camera Rig\n"
        "hda_runtime.author_camera_rig: Xform hierarchy\n"
        "RigRoot/FluidHead/Body/Sensor/EntrancePupil + cinema:* attrs"
    )
    ps_rig.setGenericFlag(hou.nodeFlag.DisplayComment, True)

    # ── 2b. Python Script LOP: Apply biomechanics ──────────
    ps_biomech = temp_subnet.createNode("pythonscript", "apply_biomechanics")
    ps_biomech.setInput(0, ps_rig)
    ps_biomech.parm("python").set(_SCRIPT_APPLY_BIOMECHANICS)
    ps_biomech.setComment(
        "Biomechanics Filter\n"
        "hda_runtime.apply_biomechanics: spring/lag/shake time samples\n"
        "on FluidHead (solver math: cinema_camera.biomechanics)"
    )
    ps_biomech.setGenericFlag(hou.nodeFlag.DisplayComment, True)

    # ── 3. Python Script LOP: Lens shader binding ──────────
    ps_shader = temp_subnet.createNode("pythonscript", "bind_lens_shader")
    ps_shader.setInput(0, ps_biomech)
    ps_shader.parm("python").set(_SCRIPT_LENS_SHADER)
    ps_shader.setComment(
        "Karma CVEX Lens Shader\n"
        "hda_runtime.author_lens_shader: karma:camera:lensshader opdef\n"
        "(cinema_lens_shader VOP; distortion + squeeze + pupil offset)"
    )
    ps_shader.setGenericFlag(hou.nodeFlag.DisplayComment, True)

    # ── 4. Python Script LOP: RenderProduct metadata ───────
    ps_product = temp_subnet.createNode("pythonscript", "render_product")
    ps_product.setInput(0, ps_shader)
    ps_product.parm("python").set(_SCRIPT_RENDER_PRODUCT)
    ps_product.setComment(
        "Render Product\n"
        "hda_runtime.author_render_product: Cooke /i + ASWF EXR metadata"
    )
    ps_product.setGenericFlag(hou.nodeFlag.DisplayComment, True)

    # ── 5. Python Script LOP: RenderSettings ───────────────
    ps_settings = temp_subnet.createNode("pythonscript", "render_settings")
    ps_settings.setInput(0, ps_product)
    ps_settings.parm("python").set(_SCRIPT_RENDER_SETTINGS)
    ps_settings.setComment(
        "Karma Render Settings\n"
        "hda_runtime.author_render_settings: resolution + camera REL"
    )
    ps_settings.setGenericFlag(hou.nodeFlag.DisplayComment, True)

    # ── 6. Wire into subnet output ────────────────────────
    # LOP subnets have an auto-created 'output0' node.
    # The chain MUST feed into output0 for the HDA to propagate
    # the authored stage to downstream nodes.
    output0 = temp_subnet.node("output0")
    if output0:
        output0.setInput(0, ps_settings)
    else:
        # Fallback: create output null with display flag
        out_null = temp_subnet.createNode("null", "OUT_cinema_rig")
        out_null.setInput(0, ps_settings)
        out_null.setDisplayFlag(True)

    # ── 7. Layout nodes ────────────────────────────────────
    temp_subnet.layoutChildren()

    # ── 8. Create HDA from subnet ──────────────────────────
    # Type name must include ::version explicitly. The `version` kwarg only sets
    # metadata; without ::3.0 in `name` Houdini registers the op as unversioned.
    hda_node = temp_subnet.createDigitalAsset(
        name="cinema::camera_rig_lop::3.0",
        hda_file_name=hda_path,
        description="Cinema Camera Rig LOP v3.0",
        min_num_inputs=0,
        max_num_inputs=1,  # Optional input: upstream stage to merge with
        version="3.0",
    )

    hda_type = hda_node.type()
    hda_def = hda_type.definition()

    # ── 9. Build HDA parameter interface ───────────────────
    ptg = hda_node.parmTemplateGroup()
    for folder in build_camera_rig_parm_templates(context="lop"):
        ptg.append(folder)
    hda_def.setParmTemplateGroup(ptg)

    # ── 10. Set HDA metadata ───────────────────────────────
    hda_def.setIcon("LOP_camera")
    hda_def.setComment(
        "Cinema Camera Rig LOP v3.0\n"
        "Solaris-native virtual cinematography rig\n"
        "Authors full USD hierarchy with nodal parallax correction"
    )
    hda_def.setExtraInfo(
        "Cinema Camera Rig v4.0 (LOP HDA v3.0)\n"
        "Pillars: B (Nodal Parallax), C (Biomechanics), D (CVEX Lens "
        "Shader), E (Pipeline Bridge)\n"
        "USD hierarchy: /CinemaRig/FluidHead/Body/Sensor/EntrancePupil\n"
        "Karma: karma:camera:lensshader opdef binding (cinema_lens_shader "
        "VOP, compiled from vex/include/karma_cinema_lens.vfl) + "
        "RenderProduct Cooke /i metadata. Karma CPU verified; XPU "
        "lens-shader support unverified -- STMap AOV is the renderer-"
        "agnostic distortion route.\n"
        "Cook-time logic: cinema_camera.hda_runtime (Python Script LOPs "
        "are shims)."
    )

    # ── 11. Push instance state into definition & save ─────
    hda_def.updateFromNode(hda_node)
    hda_def.save(hda_path)
    hda_node.matchCurrentDefinition()

    return hda_path
