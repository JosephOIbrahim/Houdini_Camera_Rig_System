"""
Cinema Camera Rig v4.0 -- Orchestrator HDA Builder

Creates cinema::camera_rig::3.0 — the top-level LOP HDA that wires:
  - USD camera with nested Xform hierarchy (nodal parallax)
  - CHOPs biomechanics constraint
  - Lens shader binding
  - Post-processing pipeline (flare, noise, STMap)

Executed through Synapse bridge in a live Houdini session.
"""

from __future__ import annotations

import os

from .parm_templates import build_camera_rig_parm_templates


def build_camera_rig_orchestrator_hda(
    save_dir: str = None,
    hda_name: str = "cinema_camera_rig_3.0.hda",
) -> str:
    """
    Build cinema::camera_rig::3.0 top-level HDA in live Houdini session.

    This is a SOP-level HDA (Object context) that contains:
      1. Camera node with USD transform hierarchy
      2. CHOPs biomechanics subnet (references cinema::chops_biomechanics)
      3. Post-processing COP network references
      4. Parameter interface exposing all sub-HDA controls

    Returns: Absolute path to saved .hda file.
    """
    import hou

    if save_dir is None:
        # v3.0: consolidate all HDAs into <repo>/otls/ (Houdini's canonical
        # auto-scan dir). CINEMA_CAMERA_REPO is set by packages/cinema_camera_rig.json.
        repo = os.environ.get("CINEMA_CAMERA_REPO")
        if repo:
            save_dir = os.path.join(repo, "otls")
        else:
            save_dir = os.path.join(os.environ["CINEMA_CAMERA_PATH"], "hda")
        os.makedirs(save_dir, exist_ok=True)

    hda_path = os.path.join(save_dir, hda_name)

    # ── 1. Create temporary container ────────────────────
    obj = hou.node("/obj")
    temp_subnet = obj.createNode("subnet", "__cinema_rig_builder")
    temp_subnet.moveToGoodPosition()

    # ── 2. Camera node ───────────────────────────────────
    cam = temp_subnet.createNode("cam", "cinema_camera")
    cam.parm("resx").set(4608)
    cam.parm("resy").set(3164)
    cam.parm("focal").set(50.0)
    cam.parm("aperture").set(28.0)  # Super 35 active width
    cam.parm("near").set(0.1)
    cam.parm("far").set(100000)
    cam.setComment("Cinema Camera\nDriven by LensSpec + CameraState")
    cam.setGenericFlag(hou.nodeFlag.DisplayComment, True)
    # Make the camera the displayed + renderable child of the wrapper subnet.
    # Without this, the viewport draws whatever else has Display=ON (the
    # entrance pupil null), and the rig "looks like a circle, not a camera".
    cam.setGenericFlag(hou.nodeFlag.Display, True)
    cam.setGenericFlag(hou.nodeFlag.Render, True)

    # ── 3. Null: Fluid Head Mount ────────────────────────
    # Carries the biomechanics-filtered pan/tilt/roll (pulled from the
    # CHOP chain via chop() expressions, wired in step 10c). Its origin
    # IS the rotation pivot of the rig.
    fluid_head = temp_subnet.createNode("null", "fluid_head_mount")
    fluid_head.setComment(
        "Fluid Head Mount\n"
        "Biomechanics-filtered pan/tilt/roll (chop() from biomechanics/OUT_biomech)"
    )
    fluid_head.setGenericFlag(hou.nodeFlag.DisplayComment, True)

    # ── 4. Null: Entrance Pupil Pivot ────────────────────
    # Sits AT the fluid-head origin = the entrance pupil (nodal point).
    # The camera is parented under it and offset BEHIND it (step 10), so
    # fluid-head rotations pivot about the pupil: parallax-correct pans
    # (Pillar B). The null itself is the visual guide ring.
    pupil_pivot = temp_subnet.createNode("null", "entrance_pupil_pivot")
    pupil_pivot.setComment(
        "Entrance Pupil Pivot\n"
        "Rotation pivot at the nodal point; camera hangs behind it"
    )
    pupil_pivot.setGenericFlag(hou.nodeFlag.DisplayComment, True)
    # Viewport overlay -- guide geometry at the nodal point
    pupil_pivot.parm("controltype").set(1)  # 1 = Circles
    pupil_pivot.parm("orientation").set(2)  # 2 = ZX plane (camera-facing)
    pupil_pivot.parm("dcolorr").set(1.0)
    pupil_pivot.parm("dcolorg").set(0.8)
    pupil_pivot.parm("dcolorb").set(0.0)  # Yellow-orange for visibility
    # Smaller default radius -- 5cm guide ring, not a meter-wide hoop.
    if pupil_pivot.parm("geoscale") is not None:
        pupil_pivot.parm("geoscale").set(0.05)
    # Display is driven by the top-level "show_nodal_guide" toggle (wired
    # after HDA parms are appended, step 10b). Default OFF: the camera frustum
    # is the only thing the user sees on instantiation.
    pupil_pivot.setGenericFlag(hou.nodeFlag.Display, False)

    # ── 4b. Object-level parenting ───────────────────────
    # fluid_head (rotations) -> pupil_pivot (pivot at nodal point) -> cam
    # (offset behind the pivot). Without these inputs the three nodes are
    # unrelated siblings and the "rig" doesn't rig.
    pupil_pivot.setFirstInput(fluid_head)
    cam.setFirstInput(pupil_pivot)

    # ── 5. CHOPs network: biomechanics ───────────────────
    chop_net = temp_subnet.createNode("chopnet", "biomechanics")
    chop_net.setComment("Biomechanics CHOPs\nSpring/Lag/Shake solver")
    chop_net.setGenericFlag(hou.nodeFlag.DisplayComment, True)

    # Inside CHOPs: fetch (HDA target parms) -> biomechanics HDA -> output
    ch_fetch = chop_net.createNode("fetch", "camera_channels")
    ch_fetch.setComment(
        "Fetch the HDA's keyframable target_pan/tilt/roll parms"
    )
    ch_fetch.setGenericFlag(hou.nodeFlag.DisplayComment, True)
    # Fetch the orchestrator's own target parms (two levels up).
    ch_fetch.parm("nodepath").set("../..")
    ch_fetch.parm("path").set(
        "target_pan_deg target_tilt_deg target_roll_deg"
    )

    # Biomechanics sub-HDA instance
    try:
        ch_biomech = chop_net.createNode(
            "cinema::chops_biomechanics", "biomech_solver"
        )
        ch_biomech.setInput(0, ch_fetch)
        ch_biomech.setComment("Spring/Lag/Shake solver\nDriven by top-level parms")
        ch_biomech.setGenericFlag(hou.nodeFlag.DisplayComment, True)
        biomech_out = ch_biomech
    except hou.OperationFailed:
        # Sub-HDA not installed -- keep placeholder
        biomech_out = ch_fetch

    # Output null for export
    ch_out = chop_net.createNode("null", "OUT_biomech")
    ch_out.setInput(0, biomech_out)
    ch_out.setDisplayFlag(True)
    chop_net.layoutChildren()

    # ── 6. COP network: post pipeline ────────────────────
    cop_net = temp_subnet.createNode("cop2net", "post_pipeline")
    cop_net.setComment(
        "Post-Processing Pipeline\n"
        "Flare -> Noise -> STMap AOV"
    )
    cop_net.setGenericFlag(hou.nodeFlag.DisplayComment, True)

    # Inside COP: input -> flare -> noise -> stmap -> output
    cop_in = cop_net.createNode("null", "IN_render")
    cop_in.setComment("INPUT: Rendered image from Karma")
    cop_in.setGenericFlag(hou.nodeFlag.DisplayComment, True)

    # Flare sub-HDA: cinema::cop_anamorphic_flare (1 input)
    try:
        cop_flare = cop_net.createNode(
            "cinema::cop_anamorphic_flare", "anamorphic_flare"
        )
        cop_flare.setInput(0, cop_in)
        cop_flare.setComment("Anamorphic Flare\nDriven by top-level parms")
        cop_flare.setGenericFlag(hou.nodeFlag.DisplayComment, True)
        flare_out = cop_flare
    except hou.OperationFailed:
        # Sub-HDA not installed -- fallback to passthrough null
        flare_out = cop_net.createNode("null", "flare_placeholder")
        flare_out.setInput(0, cop_in)
        flare_out.setComment("cinema::cop_anamorphic_flare not installed")
        flare_out.setGenericFlag(hou.nodeFlag.DisplayComment, True)

    # Noise sub-HDA: cinema::cop_sensor_noise (1 input)
    try:
        cop_noise = cop_net.createNode(
            "cinema::cop_sensor_noise", "sensor_noise"
        )
        cop_noise.setInput(0, flare_out)
        cop_noise.setComment("Sensor Noise\nDriven by top-level parms")
        cop_noise.setGenericFlag(hou.nodeFlag.DisplayComment, True)
        noise_out = cop_noise
    except hou.OperationFailed:
        noise_out = cop_net.createNode("null", "noise_placeholder")
        noise_out.setInput(0, flare_out)
        noise_out.setComment("cinema::cop_sensor_noise not installed")
        noise_out.setGenericFlag(hou.nodeFlag.DisplayComment, True)

    # STMap sub-HDA: cinema::cop_stmap_aov (independent branch, no main-chain input)
    try:
        cop_stmap = cop_net.createNode(
            "cinema::cop_stmap_aov", "stmap_aov"
        )
        cop_stmap.setComment("STMap AOV\nIndependent branch — driven by top-level parms")
        cop_stmap.setGenericFlag(hou.nodeFlag.DisplayComment, True)
    except hou.OperationFailed:
        cop_stmap = cop_net.createNode("null", "stmap_placeholder")
        cop_stmap.setComment("cinema::cop_stmap_aov not installed")
        cop_stmap.setGenericFlag(hou.nodeFlag.DisplayComment, True)

    # Main chain output: IN -> flare -> noise -> OUT
    cop_out = cop_net.createNode("null", "OUT_composited")
    cop_out.setInput(0, noise_out)
    cop_out.setDisplayFlag(True)


    cop_net.layoutChildren()

    # ── 7. Layout all nodes ──────────────────────────────
    temp_subnet.layoutChildren()

    # ── 8. Create HDA from subnet ────────────────────────
    # Type name must include ::version explicitly. The `version` kwarg only sets
    # metadata; without ::3.0 in `name` Houdini registers the op as unversioned.
    hda_node = temp_subnet.createDigitalAsset(
        name="cinema::camera_rig::3.0",
        hda_file_name=hda_path,
        description="Cinema Camera Rig v3.0",
        min_num_inputs=0,
        max_num_inputs=0,
        version="3.0",
    )

    hda_type = hda_node.type()
    hda_def = hda_type.definition()

    # ── 9. Build HDA parameter interface ─────────────────
    ptg = hda_node.parmTemplateGroup()
    for folder in build_camera_rig_parm_templates(context="obj"):
        ptg.append(folder)
    hda_def.setParmTemplateGroup(ptg)

    # ── 10. Wire internal camera parameters ──────────────
    cam_node = hda_node.node("cinema_camera")
    if cam_node:
        cam_node.parm("focal").setExpression('ch("../focal_length_mm")')
        cam_node.parm("aperture").setExpression('ch("../sensor_width_mm")')
        cam_node.parm("resx").setExpression('ch("../resolution_x")')
        cam_node.parm("resy").setExpression('ch("../resolution_y")')
        # Houdini cam shutter is a 0-1 fraction; convert from degrees:
        # shutter = shutter_angle_deg / 360
        if cam_node.parm("shutter") is not None:
            cam_node.parm("shutter").setExpression(
                'ch("../shutter_angle_deg") / 360.0'
            )
        # Viewport DOF: focus distance (meters = /obj scene units) + f-stop.
        if cam_node.parm("focus") is not None:
            cam_node.parm("focus").setExpression('ch("../focus_distance_m")')
        if cam_node.parm("fstop") is not None:
            cam_node.parm("fstop").setExpression('ch("../t_stop")')
        # The camera hangs BEHIND the pivot (pupil) by the pupil offset.
        # /obj works in meters: mm -> m is /1000. Sign: the pupil sits
        # toward the scene (-Z, protocols.ENTRANCE_PUPIL_Z_SIGN), so the
        # camera goes the other way (+Z).
        cam_node.parm("tz").setExpression(
            'ch("../entrance_pupil_offset_mm") / 1000.0'
        )

    # Entrance pupil pivot: sits AT the pivot (parent origin) -- it is
    # the guide ring, not an offset. Display driven by the top-level
    # "show_nodal_guide" toggle; hidden by default.
    pivot_node = hda_node.node("entrance_pupil_pivot")
    if pivot_node:
        pivot_node.parm("display").setExpression('ch("../show_nodal_guide")')

    # ── 10c. Fluid head driven by the biomechanics CHOP chain ──
    # Pull-based chop() references (no Export flag fragility): the
    # filtered target channels drive the fluid-head rotations.
    fluid_node = hda_node.node("fluid_head_mount")
    if fluid_node:
        for parm_name, channel in (
            ("rx", "target_tilt_deg"),
            ("ry", "target_pan_deg"),
            ("rz", "target_roll_deg"),
        ):
            fluid_node.parm(parm_name).setExpression(
                'chop("../biomechanics/OUT_biomech/{}")'.format(channel)
            )

    # ── 10b. Wire sub-HDA parameters to orchestrator ─────
    # Relative path from sub-HDA (2 levels deep) to orchestrator: ../../parm_name

    # Flare sub-HDA parms
    flare_node = hda_node.node("post_pipeline/anamorphic_flare")
    if flare_node:
        for sub_parm, top_parm in [
            ("enable", "enable_flare"),
            ("threshold", "flare_threshold"),
            ("intensity", "flare_intensity"),
            ("squeeze_ratio", "effective_squeeze"),
        ]:
            if flare_node.parm(sub_parm):
                flare_node.parm(sub_parm).setExpression(
                    'ch("../../{}")'.format(top_parm)
                )

    # Noise sub-HDA parms
    noise_node = hda_node.node("post_pipeline/sensor_noise")
    if noise_node:
        for sub_parm, top_parm in [
            ("enable", "enable_sensor_noise"),
            ("exposure_index", "exposure_index"),
            ("native_iso", "native_iso"),
            ("photon_noise_amount", "photon_noise_amount"),
            ("read_noise_amount", "read_noise_amount"),
        ]:
            if noise_node.parm(sub_parm):
                noise_node.parm(sub_parm).setExpression(
                    'ch("../../{}")'.format(top_parm)
                )

    # STMap sub-HDA parms
    stmap_node = hda_node.node("post_pipeline/stmap_aov")
    if stmap_node:
        for sub_parm, top_parm in [
            ("resolution_x", "resolution_x"),
            ("resolution_y", "resolution_y"),
            ("dist_k1", "dist_k1"),
            ("dist_k2", "dist_k2"),
            ("dist_k3", "dist_k3"),
            ("dist_p1", "dist_p1"),
            ("dist_p2", "dist_p2"),
            ("dist_sq_uniformity", "dist_sq_uniformity"),
            ("effective_squeeze", "effective_squeeze"),
        ]:
            if stmap_node.parm(sub_parm):
                stmap_node.parm(sub_parm).setExpression(
                    'ch("../../{}")'.format(top_parm)
                )

    # Biomechanics sub-HDA parms
    biomech_node = hda_node.node("biomechanics/biomech_solver")
    if biomech_node:
        for sub_parm, top_parm in [
            ("combined_weight_kg", "combined_weight_kg"),
            ("moment_arm_cm", "moment_arm_cm"),
            ("spring_constant", "spring_constant"),
            ("damping_ratio", "damping_ratio"),
            ("lag_frames", "lag_frames"),
            ("enable_handheld", "enable_handheld"),
            ("shake_amplitude_deg", "shake_amplitude_deg"),
            ("shake_frequency_hz", "shake_frequency_hz"),
            ("auto_derive", "auto_derive"),
        ]:
            if biomech_node.parm(sub_parm):
                biomech_node.parm(sub_parm).setExpression(
                    'ch("../../{}")'.format(top_parm)
                )

    # ── 11. Set HDA metadata ─────────────────────────────
    hda_def.setIcon("OBJ_camera")
    hda_def.setComment(
        "Cinema Camera Rig v3.0\n"
        "Virtual Cinematography Simulator\n"
        "Physically accurate lens behavior, biomechanics, and post-processing."
    )
    hda_def.setExtraInfo(
        "Cinema Camera Rig v4.0 (HDA v3.0)\n"
        "Sub-HDAs (cop2 category): chops_biomechanics, cop_anamorphic_flare, "
        "cop_sensor_noise, cop_stmap_aov\n"
        "Pillars wired in this orchestrator: A (MechanicalSpec), B (Nodal Parallax), "
        "C (Biomechanics), D (CVEX Lens Shader), E (Pipeline Bridge), "
        "F (Dynamic Mumps).\n"
        "Pillar G (Copernicus 2.0) lives in the cinema::flare::3.0 / "
        "sensor_noise::3.0 / stmap_aov::3.0 preview HDAs and is NOT wired into "
        "this orchestrator yet -- those are standalone for now."
    )

    # ── 12. Push instance state into definition & save ───
    # Expressions set on instance children (step 10) must be
    # captured into the HDA definition before saving, otherwise
    # matchCurrentDefinition() will revert them to defaults.
    hda_def.updateFromNode(hda_node)
    hda_def.save(hda_path)
    hda_node.matchCurrentDefinition()

    return hda_path
