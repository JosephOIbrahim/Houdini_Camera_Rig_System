"""
Cinema Camera Rig v4.0 -- Solaris/LOP HDA Builder

Creates cinema::camera_rig_lop::1.0 — a native Solaris LOP HDA that:
  - Authors the full nodal-parallax USD Xform hierarchy via Python Script LOP
  - Configures Karma RenderProduct with Cooke /i + ASWF EXR metadata
  - Binds Karma CVEX lens shader
  - Configures Karma XPU render settings
  - Exposes the same 6-tab parameter interface as the OBJ version

Uses usd_builder.py (pure pxr) for all USD authoring.
Executed through Synapse bridge in a live Houdini session.
"""

from __future__ import annotations

import os
import textwrap

from .parm_templates import build_camera_rig_parm_templates


# ════════════════════════════════════════════════════════════
# EMBEDDED PYTHON SCRIPTS FOR LOP NODES
# ════════════════════════════════════════════════════════════

# Python Script LOP: Author USD camera rig hierarchy
# Reads HDA-level parms and calls usd_builder.build_usd_camera_rig()
_SCRIPT_BUILD_RIG = textwrap.dedent("""\
    import math
    from pxr import Gf, Sdf, Usd, UsdGeom

    node = hou.pwd()
    hda = node.parent()
    stage = hou.pwd().editableStage()

    # ── Read HDA parameters ──────────────────────────────
    rig_path = hda.evalParm("usd_camera_path")
    if not rig_path or rig_path == "/CinemaRig/Camera":
        rig_path = "/CinemaRig"

    focal_length_mm = hda.evalParm("focal_length_mm")
    t_stop = hda.evalParm("t_stop")
    focus_distance_m = hda.evalParm("focus_distance_m")
    sensor_width_mm = hda.evalParm("sensor_width_mm")
    sensor_height_mm = hda.evalParm("sensor_height_mm")
    resolution_x = hda.evalParm("resolution_x")
    resolution_y = hda.evalParm("resolution_y")
    squeeze_ratio = hda.evalParm("squeeze_ratio")
    effective_squeeze = hda.evalParm("effective_squeeze")
    entrance_pupil_offset_mm = hda.evalParm("entrance_pupil_offset_mm")
    body_id = hda.evalParm("body_id")
    exposure_index = hda.evalParm("exposure_index")

    # Distortion
    dist_k1 = hda.evalParm("dist_k1")
    dist_k2 = hda.evalParm("dist_k2")
    dist_k3 = hda.evalParm("dist_k3")
    dist_p1 = hda.evalParm("dist_p1")
    dist_p2 = hda.evalParm("dist_p2")
    dist_sq_uniformity = hda.evalParm("dist_sq_uniformity")

    # Biomechanics (weight for metadata)
    combined_weight_kg = hda.evalParm("combined_weight_kg")

    # ── Body offset lookup ───────────────────────────────
    _BODY_OFFSETS_CM = {
        "alexa35":      {"y": 5.0, "z": -8.0},
        "red_komodo":   {"y": 3.5, "z": -5.0},
        "sony_venice2": {"y": 5.5, "z": -9.0},
    }
    offsets = _BODY_OFFSETS_CM.get(body_id, {"y": 4.0, "z": -7.0})

    # ── Build Xform hierarchy ────────────────────────────
    # /RigRoot/FluidHead/Body/Sensor/EntrancePupil
    rig_xform = UsdGeom.Xform.Define(stage, rig_path)

    head_path = rig_path + "/FluidHead"
    head_xform = UsdGeom.Xform.Define(stage, head_path)
    head_xform.AddRotateXYZOp()

    body_path = head_path + "/Body"
    body_xform = UsdGeom.Xform.Define(stage, body_path)
    body_xform.AddTranslateOp().Set(Gf.Vec3d(0.0, offsets["y"], offsets["z"]))

    sensor_path = body_path + "/Sensor"
    camera = UsdGeom.Camera.Define(stage, sensor_path)

    # Core camera attributes (USD: mm for aperture/focal, cm for focus)
    camera.CreateHorizontalApertureAttr().Set(sensor_width_mm)
    camera.CreateVerticalApertureAttr().Set(sensor_height_mm)
    camera.CreateFocalLengthAttr().Set(focal_length_mm)
    camera.CreateFocusDistanceAttr().Set(focus_distance_m * 100.0)
    camera.CreateFStopAttr().Set(t_stop)
    camera.CreateClippingRangeAttr().Set(Gf.Vec2f(0.01, 100000.0))

    # Cinema rig custom attributes on sensor prim
    sensor_prim = camera.GetPrim()

    def _set_attr(prim, name, sdf_type, value):
        attr = prim.CreateAttribute(name, sdf_type)
        attr.Set(value)

    entrance_pupil_offset_cm = entrance_pupil_offset_mm / 10.0

    _set_attr(sensor_prim, "cinema:rig:entrancePupilOffsetCm",
              Sdf.ValueTypeNames.Float, entrance_pupil_offset_cm)
    _set_attr(sensor_prim, "cinema:rig:combinedWeightKg",
              Sdf.ValueTypeNames.Float, combined_weight_kg)
    _set_attr(sensor_prim, "cinema:rig:effectiveSqueeze",
              Sdf.ValueTypeNames.Float, effective_squeeze)

    # Optics: compute FOV and DOF inline (avoids import dependency)
    sensor_diag = math.sqrt(sensor_width_mm**2 + sensor_height_mm**2)
    coc_mm = sensor_diag / 1500.0
    hfov_deg = math.degrees(2.0 * math.atan(sensor_width_mm / (2.0 * focal_length_mm)))
    vfov_deg = math.degrees(2.0 * math.atan(sensor_height_mm / (2.0 * focal_length_mm)))
    hyperfocal_m = (focal_length_mm**2 / (t_stop * coc_mm) + focal_length_mm) / 1000.0
    focus_mm = focus_distance_m * 1000.0
    focal_mm = focal_length_mm
    hyp_mm = hyperfocal_m * 1000.0
    dof_near_m = (focus_mm * (hyp_mm - focal_mm)) / (hyp_mm + focus_mm - 2.0 * focal_mm)
    dof_near_m = max(0.0, dof_near_m / 1000.0)
    if focus_mm >= hyp_mm:
        dof_far_m = 1e12
    else:
        dof_far_m = (focus_mm * (hyp_mm - focal_mm)) / (hyp_mm - focus_mm)
        dof_far_m = dof_far_m / 1000.0

    _set_attr(sensor_prim, "cinema:optics:hfovDeg", Sdf.ValueTypeNames.Float, hfov_deg)
    _set_attr(sensor_prim, "cinema:optics:vfovDeg", Sdf.ValueTypeNames.Float, vfov_deg)
    _set_attr(sensor_prim, "cinema:optics:dofNearM", Sdf.ValueTypeNames.Float, dof_near_m)
    _set_attr(sensor_prim, "cinema:optics:dofFarM", Sdf.ValueTypeNames.Float, dof_far_m)
    _set_attr(sensor_prim, "cinema:optics:hyperfocalM", Sdf.ValueTypeNames.Float, hyperfocal_m)
    _set_attr(sensor_prim, "cinema:optics:cocMm", Sdf.ValueTypeNames.Float, coc_mm)

    # Lens state attributes
    _set_attr(sensor_prim, "cinema:lens:focalLengthMm", Sdf.ValueTypeNames.Float, focal_length_mm)
    _set_attr(sensor_prim, "cinema:lens:tStop", Sdf.ValueTypeNames.Float, t_stop)
    _set_attr(sensor_prim, "cinema:lens:focusDistanceM", Sdf.ValueTypeNames.Float, focus_distance_m)
    _set_attr(sensor_prim, "cinema:lens:squeezeRatioNominal", Sdf.ValueTypeNames.Float, squeeze_ratio)
    _set_attr(sensor_prim, "cinema:lens:squeezeRatioEffective", Sdf.ValueTypeNames.Float, effective_squeeze)
    _set_attr(sensor_prim, "cinema:lens:distortion:k1", Sdf.ValueTypeNames.Float, dist_k1)
    _set_attr(sensor_prim, "cinema:lens:distortion:k2", Sdf.ValueTypeNames.Float, dist_k2)
    _set_attr(sensor_prim, "cinema:lens:distortion:k3", Sdf.ValueTypeNames.Float, dist_k3)
    _set_attr(sensor_prim, "cinema:lens:distortion:p1", Sdf.ValueTypeNames.Float, dist_p1)
    _set_attr(sensor_prim, "cinema:lens:distortion:p2", Sdf.ValueTypeNames.Float, dist_p2)
    _set_attr(sensor_prim, "cinema:lens:distortion:sqUniformity", Sdf.ValueTypeNames.Float, dist_sq_uniformity)

    # Camera state attributes
    _set_attr(sensor_prim, "cinema:camera:sensorWidthMm", Sdf.ValueTypeNames.Float, sensor_width_mm)
    _set_attr(sensor_prim, "cinema:camera:sensorHeightMm", Sdf.ValueTypeNames.Float, sensor_height_mm)
    _set_attr(sensor_prim, "cinema:camera:exposureIndex", Sdf.ValueTypeNames.Int, exposure_index)
    _set_attr(sensor_prim, "cinema:camera:resolutionX", Sdf.ValueTypeNames.Int, resolution_x)
    _set_attr(sensor_prim, "cinema:camera:resolutionY", Sdf.ValueTypeNames.Int, resolution_y)

    # ── Entrance Pupil guide Xform ───────────────────────
    pupil_path = sensor_path + "/EntrancePupil"
    pupil_xform = UsdGeom.Xform.Define(stage, pupil_path)
    pupil_xform.AddTranslateOp().Set(Gf.Vec3d(0.0, 0.0, entrance_pupil_offset_cm))
    pupil_prim = pupil_xform.GetPrim()
    UsdGeom.Imageable(pupil_prim).CreatePurposeAttr().Set(UsdGeom.Tokens.guide)
""")

# Python Script LOP: Configure RenderProduct with Cooke /i metadata
_SCRIPT_RENDER_PRODUCT = textwrap.dedent("""\
    from pxr import Gf, Sdf, Usd, UsdRender

    node = hou.pwd()
    hda = node.parent()
    stage = hou.pwd().editableStage()

    write_cooke_i = hda.evalParm("write_cooke_i")
    write_aswf_exr = hda.evalParm("write_aswf_exr")

    if not (write_cooke_i or write_aswf_exr):
        # Nothing to write
        pass
    else:
        rig_path = hda.evalParm("usd_camera_path")
        if not rig_path or rig_path == "/CinemaRig/Camera":
            rig_path = "/CinemaRig"
        camera_path = rig_path + "/FluidHead/Body/Sensor"

        resolution_x = hda.evalParm("resolution_x")
        resolution_y = hda.evalParm("resolution_y")

        cam_name = camera_path.split("/")[-1]
        product_path = "/Render/Products/" + cam_name
        product = UsdRender.Product.Define(stage, product_path)

        product.CreateResolutionAttr().Set(Gf.Vec2i(resolution_x, resolution_y))
        product.CreatePixelAspectRatioAttr().Set(1.0)
        product.GetCameraRel().SetTargets([Sdf.Path(camera_path)])
        product.CreateProductNameAttr().Set("cinema_rig_render.exr")

        prim = product.GetPrim()

        def _set_attr(p, name, sdf_type, value):
            attr = p.CreateAttribute(name, sdf_type)
            attr.Set(value)

        if write_cooke_i or write_aswf_exr:
            # Camera identification
            _set_attr(prim, "driver:parameters:OpenEXR:camera:sensorWidthMm",
                      Sdf.ValueTypeNames.Float, hda.evalParm("sensor_width_mm"))
            _set_attr(prim, "driver:parameters:OpenEXR:camera:sensorHeightMm",
                      Sdf.ValueTypeNames.Float, hda.evalParm("sensor_height_mm"))
            _set_attr(prim, "driver:parameters:OpenEXR:camera:exposureIndex",
                      Sdf.ValueTypeNames.Int, hda.evalParm("exposure_index"))

            # Lens identification (Cooke /i format)
            _set_attr(prim, "driver:parameters:OpenEXR:lens:focalLengthMm",
                      Sdf.ValueTypeNames.Float, hda.evalParm("focal_length_mm"))
            _set_attr(prim, "driver:parameters:OpenEXR:lens:tStop",
                      Sdf.ValueTypeNames.Float, hda.evalParm("t_stop"))
            _set_attr(prim, "driver:parameters:OpenEXR:lens:focusDistanceM",
                      Sdf.ValueTypeNames.Float, hda.evalParm("focus_distance_m"))
            _set_attr(prim, "driver:parameters:OpenEXR:lens:squeezeRatio",
                      Sdf.ValueTypeNames.Float, hda.evalParm("effective_squeeze"))

            # Distortion model
            _set_attr(prim, "driver:parameters:OpenEXR:lens:distortion:k1",
                      Sdf.ValueTypeNames.Float, hda.evalParm("dist_k1"))
            _set_attr(prim, "driver:parameters:OpenEXR:lens:distortion:k2",
                      Sdf.ValueTypeNames.Float, hda.evalParm("dist_k2"))
            _set_attr(prim, "driver:parameters:OpenEXR:lens:distortion:k3",
                      Sdf.ValueTypeNames.Float, hda.evalParm("dist_k3"))
            _set_attr(prim, "driver:parameters:OpenEXR:lens:distortion:p1",
                      Sdf.ValueTypeNames.Float, hda.evalParm("dist_p1"))
            _set_attr(prim, "driver:parameters:OpenEXR:lens:distortion:p2",
                      Sdf.ValueTypeNames.Float, hda.evalParm("dist_p2"))

            # Mechanical metadata
            _set_attr(prim, "driver:parameters:OpenEXR:lens:entrancePupilOffsetMm",
                      Sdf.ValueTypeNames.Float, hda.evalParm("entrance_pupil_offset_mm"))
""")

# Python Script LOP: Bind Karma CVEX lens shader
_SCRIPT_LENS_SHADER = textwrap.dedent("""\
    from pxr import Sdf, UsdShade

    node = hou.pwd()
    hda = node.parent()
    stage = hou.pwd().editableStage()

    rig_path = hda.evalParm("usd_camera_path")
    if not rig_path or rig_path == "/CinemaRig/Camera":
        rig_path = "/CinemaRig"
    camera_path = rig_path + "/FluidHead/Body/Sensor"
    shader_path = camera_path + "/CinemaLensShader"

    shader = UsdShade.Shader.Define(stage, shader_path)
    shader.CreateIdAttr("karma:cvex:cinema_lens_shader")

    # Lens parameters
    shader.CreateInput("focal_length_mm", Sdf.ValueTypeNames.Float).Set(
        hda.evalParm("focal_length_mm"))
    shader.CreateInput("effective_squeeze", Sdf.ValueTypeNames.Float).Set(
        hda.evalParm("effective_squeeze"))
    shader.CreateInput("entrance_pupil_offset_cm", Sdf.ValueTypeNames.Float).Set(
        hda.evalParm("entrance_pupil_offset_mm") / 10.0)
    shader.CreateInput("sensor_width_mm", Sdf.ValueTypeNames.Float).Set(
        hda.evalParm("sensor_width_mm"))
    shader.CreateInput("sensor_height_mm", Sdf.ValueTypeNames.Float).Set(
        hda.evalParm("sensor_height_mm"))

    # Distortion coefficients
    shader.CreateInput("dist_k1", Sdf.ValueTypeNames.Float).Set(
        hda.evalParm("dist_k1"))
    shader.CreateInput("dist_k2", Sdf.ValueTypeNames.Float).Set(
        hda.evalParm("dist_k2"))
    shader.CreateInput("dist_k3", Sdf.ValueTypeNames.Float).Set(
        hda.evalParm("dist_k3"))
    shader.CreateInput("dist_p1", Sdf.ValueTypeNames.Float).Set(
        hda.evalParm("dist_p1"))
    shader.CreateInput("dist_p2", Sdf.ValueTypeNames.Float).Set(
        hda.evalParm("dist_p2"))
    shader.CreateInput("dist_sq_uniformity", Sdf.ValueTypeNames.Float).Set(
        hda.evalParm("dist_sq_uniformity"))

    # Bind shader to camera prim
    camera_prim = stage.GetPrimAtPath(camera_path)
    if camera_prim:
        camera_prim.CreateAttribute(
            "karma:lens:shader", Sdf.ValueTypeNames.String
        ).Set(shader_path)
""")

# Python Script LOP: Configure Karma XPU render settings
_SCRIPT_RENDER_SETTINGS = textwrap.dedent("""\
    from pxr import Gf, Sdf, Usd, UsdRender

    node = hou.pwd()
    hda = node.parent()
    stage = hou.pwd().editableStage()

    resolution_x = hda.evalParm("resolution_x")
    resolution_y = hda.evalParm("resolution_y")

    settings_path = "/Render/CinemaRigSettings"
    settings = UsdRender.Settings.Define(stage, settings_path)
    settings.CreateResolutionAttr().Set(Gf.Vec2i(resolution_x, resolution_y))

    # Point to the cinema camera as the render camera
    rig_path = hda.evalParm("usd_camera_path")
    if not rig_path or rig_path == "/CinemaRig/Camera":
        rig_path = "/CinemaRig"
    camera_path = rig_path + "/FluidHead/Body/Sensor"

    prim = settings.GetPrim()
    prim.CreateAttribute("camera", Sdf.ValueTypeNames.String).Set(camera_path)

    # Link to render product
    cam_name = camera_path.split("/")[-1]
    product_path = "/Render/Products/" + cam_name
    settings.GetProductsRel().SetTargets([Sdf.Path(product_path)])
""")


# ════════════════════════════════════════════════════════════
# LOP HDA BUILDER
# ════════════════════════════════════════════════════════════

def build_camera_rig_lop_hda(
    save_dir: str = None,
    hda_name: str = "cinema_camera_rig_lop_1.0.hda",
) -> str:
    """
    Build cinema::camera_rig_lop::1.0 LOP HDA in live Houdini session.

    Creates a Solaris-native camera rig that authors the full USD Xform
    hierarchy, Karma lens shader, RenderProduct with Cooke /i metadata,
    and RenderSettings for Karma XPU.

    Internal LOP network:
      1. Python Script LOP -- builds USD camera rig hierarchy
      2. Python Script LOP -- binds Karma CVEX lens shader
      3. Python Script LOP -- configures RenderProduct with EXR metadata
      4. Python Script LOP -- configures Karma RenderSettings

    Returns: Absolute path to saved .hda file.
    """
    import hou

    if save_dir is None:
        save_dir = os.path.join(os.environ["CINEMA_CAMERA_PATH"], "hda")

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
    ps_rig.parm("python").set(_SCRIPT_BUILD_RIG)
    ps_rig.setComment(
        "Cinema Camera Rig\n"
        "Authors Xform hierarchy: RigRoot/FluidHead/Body/Sensor/EntrancePupil\n"
        "All custom cinema: attributes authored here"
    )
    ps_rig.setGenericFlag(hou.nodeFlag.DisplayComment, True)

    # ── 3. Python Script LOP: Lens shader binding ──────────
    ps_shader = temp_subnet.createNode("pythonscript", "bind_lens_shader")
    ps_shader.setInput(0, ps_rig)
    ps_shader.parm("python").set(_SCRIPT_LENS_SHADER)
    ps_shader.setComment(
        "Karma CVEX Lens Shader\n"
        "Binds cinema_lens_shader with distortion + squeeze parameters"
    )
    ps_shader.setGenericFlag(hou.nodeFlag.DisplayComment, True)

    # ── 4. Python Script LOP: RenderProduct metadata ───────
    ps_product = temp_subnet.createNode("pythonscript", "render_product")
    ps_product.setInput(0, ps_shader)
    ps_product.parm("python").set(_SCRIPT_RENDER_PRODUCT)
    ps_product.setComment(
        "Render Product\n"
        "Cooke /i + ASWF EXR metadata on RenderProduct prim"
    )
    ps_product.setGenericFlag(hou.nodeFlag.DisplayComment, True)

    # ── 5. Python Script LOP: RenderSettings ───────────────
    ps_settings = temp_subnet.createNode("pythonscript", "render_settings")
    ps_settings.setInput(0, ps_product)
    ps_settings.parm("python").set(_SCRIPT_RENDER_SETTINGS)
    ps_settings.setComment(
        "Karma Render Settings\n"
        "Resolution + camera binding for Karma XPU"
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
    hda_node = temp_subnet.createDigitalAsset(
        name="cinema::camera_rig_lop",
        hda_file_name=hda_path,
        description="Cinema Camera Rig LOP v1.0",
        min_num_inputs=0,
        max_num_inputs=1,  # Optional input: upstream stage to merge with
        version="1.0",
    )

    hda_type = hda_node.type()
    hda_def = hda_type.definition()

    # ── 9. Build HDA parameter interface ───────────────────
    ptg = hda_node.parmTemplateGroup()
    for folder in build_camera_rig_parm_templates():
        ptg.append(folder)
    hda_def.setParmTemplateGroup(ptg)

    # ── 10. Set HDA metadata ───────────────────────────────
    hda_def.setIcon("LOP_camera")
    hda_def.setComment(
        "Cinema Camera Rig LOP v1.0\n"
        "Solaris-native virtual cinematography rig\n"
        "Authors full USD hierarchy with nodal parallax correction"
    )
    hda_def.setExtraInfo(
        "Cinema Camera Rig v4.0 (LOP HDA v1.0)\n"
        "Pillars: B (Nodal Parallax), D (CVEX Lens Shader), "
        "E (Pipeline Bridge)\n"
        "USD hierarchy: /CinemaRig/FluidHead/Body/Sensor/EntrancePupil\n"
        "Karma: CVEX lens shader + RenderProduct Cooke /i metadata"
    )

    # ── 11. Push instance state into definition & save ─────
    hda_def.updateFromNode(hda_node)
    hda_def.save(hda_path)
    hda_node.matchCurrentDefinition()

    return hda_path
