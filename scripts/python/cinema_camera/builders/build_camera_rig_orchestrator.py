"""
Cinema Camera Rig v4.0 -- Orchestrator HDA Builder

Creates cinema::camera_rig::2.0 — the top-level LOP HDA that wires:
  - USD camera with nested Xform hierarchy (nodal parallax)
  - CHOPs biomechanics constraint
  - Lens shader binding
  - Post-processing pipeline (flare, noise, STMap)

Executed through Synapse bridge in a live Houdini session.
"""

from __future__ import annotations

import os


def build_camera_rig_orchestrator_hda(
    save_dir: str = None,
    hda_name: str = "cinema_camera_rig_2.0.hda",
) -> str:
    """
    Build cinema::camera_rig::2.0 top-level HDA in live Houdini session.

    This is a SOP-level HDA (Object context) that contains:
      1. Camera node with USD transform hierarchy
      2. CHOPs biomechanics subnet (references cinema::chops_biomechanics::1.0)
      3. Post-processing COP network references
      4. Parameter interface exposing all sub-HDA controls

    Returns: Absolute path to saved .hda file.
    """
    import hou

    if save_dir is None:
        save_dir = os.path.join(os.environ["CINEMA_CAMERA_PATH"], "hda")

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

    # ── 3. Null: Entrance Pupil Pivot ────────────────────
    # This null offsets the camera pivot to the entrance pupil
    # for parallax-correct panning (Pillar B)
    pupil_pivot = temp_subnet.createNode("null", "entrance_pupil_pivot")
    pupil_pivot.setComment(
        "Entrance Pupil Offset\n"
        "Shifts pivot to nodal point for parallax-correct pans"
    )
    pupil_pivot.setGenericFlag(hou.nodeFlag.DisplayComment, True)

    # ── 4. Null: Fluid Head Mount ────────────────────────
    # This is the attachment point for CHOPs biomechanics output
    fluid_head = temp_subnet.createNode("null", "fluid_head_mount")
    fluid_head.setComment(
        "Fluid Head Mount\n"
        "CHOPs biomechanics exports rotations here"
    )
    fluid_head.setGenericFlag(hou.nodeFlag.DisplayComment, True)

    # ── 5. CHOPs network: biomechanics ───────────────────
    chop_net = temp_subnet.createNode("chopnet", "biomechanics")
    chop_net.setComment("Biomechanics CHOPs\nSpring/Lag/Shake solver")
    chop_net.setGenericFlag(hou.nodeFlag.DisplayComment, True)

    # Inside CHOPs: fetch + biomechanics reference
    ch_fetch = chop_net.createNode("fetch", "camera_channels")
    ch_fetch.setComment("Fetch raw camera animation channels")
    ch_fetch.setGenericFlag(hou.nodeFlag.DisplayComment, True)

    # Output null for export
    ch_out = chop_net.createNode("null", "OUT_biomech")
    ch_out.setInput(0, ch_fetch)
    ch_out.setDisplayFlag(True)
    chop_net.layoutChildren()

    # ── 6. COP network: post pipeline ────────────────────
    cop_net = temp_subnet.createNode("copnet", "post_pipeline")
    cop_net.setComment(
        "Post-Processing Pipeline\n"
        "Flare -> Noise -> STMap AOV"
    )
    cop_net.setGenericFlag(hou.nodeFlag.DisplayComment, True)

    # Inside COP: input -> flare -> noise -> stmap -> output
    cop_in = cop_net.createNode("null", "IN_render")
    cop_in.setComment("INPUT: Rendered image from Karma")
    cop_in.setGenericFlag(hou.nodeFlag.DisplayComment, True)

    cop_flare_ref = cop_net.createNode("null", "flare_placeholder")
    cop_flare_ref.setInput(0, cop_in)
    cop_flare_ref.setComment(
        "cinema::cop_anamorphic_flare::2.0\n"
        "Replace with HDA instance"
    )
    cop_flare_ref.setGenericFlag(hou.nodeFlag.DisplayComment, True)

    cop_noise_ref = cop_net.createNode("null", "noise_placeholder")
    cop_noise_ref.setInput(0, cop_flare_ref)
    cop_noise_ref.setComment(
        "cinema::cop_sensor_noise::1.0\n"
        "Replace with HDA instance"
    )
    cop_noise_ref.setGenericFlag(hou.nodeFlag.DisplayComment, True)

    cop_stmap_ref = cop_net.createNode("null", "stmap_placeholder")
    cop_stmap_ref.setComment(
        "cinema::cop_stmap_aov::1.0\n"
        "Independent branch — generates STMap AOV"
    )
    cop_stmap_ref.setGenericFlag(hou.nodeFlag.DisplayComment, True)

    cop_out = cop_net.createNode("null", "OUT_composited")
    cop_out.setInput(0, cop_noise_ref)
    cop_out.setDisplayFlag(True)


    cop_net.layoutChildren()

    # ── 7. Layout all nodes ──────────────────────────────
    temp_subnet.layoutChildren()

    # ── 8. Create HDA from subnet ────────────────────────
    hda_node = temp_subnet.createDigitalAsset(
        name="cinema::camera_rig",
        hda_file_name=hda_path,
        description="Cinema Camera Rig v2.0",
        min_num_inputs=0,
        max_num_inputs=0,
        version="2.0",
    )

    hda_type = hda_node.type()
    hda_def = hda_type.definition()

    # ── 9. Build HDA parameter interface ─────────────────
    ptg = hda_node.parmTemplateGroup()

    # --- Lens tab ---
    lens_folder = hou.FolderParmTemplate(
        "lens_tab", "Lens",
        folder_type=hou.folderType.Tabs,
    )
    lens_folder.addParmTemplate(hou.StringParmTemplate(
        "lens_id", "Lens ID", 1,
        default_value=("cooke_ana_i_s35_50mm",),
        help="Lens identifier from registry. Used to load LensSpec JSON.",
    ))
    lens_folder.addParmTemplate(hou.FloatParmTemplate(
        "focal_length_mm", "Focal Length (mm)", 1,
        default_value=(50.0,), min=8.0, max=600.0,
        help="Read from LensSpec. Drives camera aperture.",
    ))
    lens_folder.addParmTemplate(hou.FloatParmTemplate(
        "t_stop", "T-Stop", 1,
        default_value=(2.8,), min=1.0, max=22.0,
    ))
    lens_folder.addParmTemplate(hou.FloatParmTemplate(
        "focus_distance_m", "Focus Distance (m)", 1,
        default_value=(3.0,), min=0.3, max=1000.0,
        help="Focus distance. Drives dynamic squeeze and DOF.",
    ))
    lens_folder.addParmTemplate(hou.FloatParmTemplate(
        "squeeze_ratio", "Squeeze Ratio", 1,
        default_value=(2.0,), min=1.0, max=2.0,
        help="Nominal anamorphic squeeze. Dynamic squeeze computed from focus distance.",
    ))
    lens_folder.addParmTemplate(hou.FloatParmTemplate(
        "effective_squeeze", "Effective Squeeze", 1,
        default_value=(2.0,), min=1.0, max=2.0,
        help="Focus-dependent squeeze (computed from SqueezeBreathingCurve).",
    ))
    lens_folder.addParmTemplate(hou.FloatParmTemplate(
        "entrance_pupil_offset_mm", "Entrance Pupil Offset (mm)", 1,
        default_value=(125.0,), min=0.0, max=500.0,
        help="Distance from sensor to nodal point. Critical for parallax-correct pans.",
    ))
    ptg.append(lens_folder)

    # --- Distortion tab ---
    dist_folder = hou.FolderParmTemplate(
        "distortion_tab", "Distortion",
        folder_type=hou.folderType.Tabs,
    )
    for parm_name, label, default in [
        ("dist_k1", "K1 (Radial)", 0.0),
        ("dist_k2", "K2 (Radial)", 0.0),
        ("dist_k3", "K3 (Radial)", 0.0),
        ("dist_p1", "P1 (Tangential)", 0.0),
        ("dist_p2", "P2 (Tangential)", 0.0),
        ("dist_sq_uniformity", "Squeeze Uniformity", 1.0),
    ]:
        dist_folder.addParmTemplate(hou.FloatParmTemplate(
            parm_name, label, 1,
            default_value=(default,),
            help=f"Distortion coefficient from LensSpec.",
        ))
    ptg.append(dist_folder)

    # --- Body / Sensor tab ---
    body_folder = hou.FolderParmTemplate(
        "body_tab", "Camera Body",
        folder_type=hou.folderType.Tabs,
    )
    body_folder.addParmTemplate(hou.StringParmTemplate(
        "body_id", "Body ID", 1,
        default_value=("alexa35",),
        help="Camera body identifier from registry.",
    ))
    body_folder.addParmTemplate(hou.FloatParmTemplate(
        "sensor_width_mm", "Sensor Width (mm)", 1,
        default_value=(28.25,),
        help="Active sensor width. ALEXA 35: 28.25mm (Open Gate).",
    ))
    body_folder.addParmTemplate(hou.FloatParmTemplate(
        "sensor_height_mm", "Sensor Height (mm)", 1,
        default_value=(18.17,),
        help="Active sensor height.",
    ))
    body_folder.addParmTemplate(hou.IntParmTemplate(
        "resolution_x", "Resolution X", 1,
        default_value=(4608,), min=256, max=8192,
    ))
    body_folder.addParmTemplate(hou.IntParmTemplate(
        "resolution_y", "Resolution Y", 1,
        default_value=(3164,), min=256, max=8192,
    ))
    body_folder.addParmTemplate(hou.IntParmTemplate(
        "exposure_index", "Exposure Index (EI)", 1,
        default_value=(800,), min=100, max=12800,
    ))
    body_folder.addParmTemplate(hou.IntParmTemplate(
        "native_iso", "Native ISO", 1,
        default_value=(800,), min=100, max=3200,
    ))
    ptg.append(body_folder)

    # --- Biomechanics tab ---
    bio_folder = hou.FolderParmTemplate(
        "biomechanics_tab", "Biomechanics",
        folder_type=hou.folderType.Tabs,
    )
    bio_folder.addParmTemplate(hou.ToggleParmTemplate(
        "enable_biomechanics", "Enable Biomechanics",
        default_value=True,
        help="When on, camera motion is filtered through spring/lag/shake solver.",
    ))
    bio_folder.addParmTemplate(hou.FloatParmTemplate(
        "combined_weight_kg", "Combined Weight (kg)", 1,
        default_value=(7.5,), min=1.0, max=30.0,
        help="Body + lens weight. Auto-computed from body_id + lens_id specs.",
    ))
    bio_folder.addParmTemplate(hou.FloatParmTemplate(
        "moment_arm_cm", "Moment Arm (cm)", 1,
        default_value=(18.0,), min=5.0, max=50.0,
    ))
    bio_folder.addParmTemplate(hou.FloatParmTemplate(
        "spring_constant", "Spring Constant", 1,
        default_value=(15.0,), min=1.0, max=30.0,
    ))
    bio_folder.addParmTemplate(hou.FloatParmTemplate(
        "damping_ratio", "Damping Ratio", 1,
        default_value=(0.5,), min=0.0, max=1.0,
    ))
    bio_folder.addParmTemplate(hou.FloatParmTemplate(
        "lag_frames", "Lag (frames)", 1,
        default_value=(2.25,), min=0.0, max=10.0,
    ))
    bio_folder.addParmTemplate(hou.ToggleParmTemplate(
        "enable_handheld", "Enable Handheld Shake",
        default_value=False,
    ))
    bio_folder.addParmTemplate(hou.FloatParmTemplate(
        "shake_amplitude_deg", "Shake Amplitude (deg)", 1,
        default_value=(0.2,), min=0.0, max=2.0,
    ))
    bio_folder.addParmTemplate(hou.FloatParmTemplate(
        "shake_frequency_hz", "Shake Frequency (Hz)", 1,
        default_value=(5.5,), min=1.0, max=15.0,
    ))
    bio_folder.addParmTemplate(hou.ToggleParmTemplate(
        "auto_derive", "Auto Derive from Weight",
        default_value=True,
        help="Auto-compute spring/damping/lag from combined weight.",
    ))
    ptg.append(bio_folder)

    # --- Post-Processing tab ---
    post_folder = hou.FolderParmTemplate(
        "post_tab", "Post-Processing",
        folder_type=hou.folderType.Tabs,
    )
    post_folder.addParmTemplate(hou.ToggleParmTemplate(
        "enable_flare", "Enable Anamorphic Flare",
        default_value=True,
    ))
    post_folder.addParmTemplate(hou.FloatParmTemplate(
        "flare_threshold", "Flare Threshold", 1,
        default_value=(3.0,), min=0.5, max=20.0,
    ))
    post_folder.addParmTemplate(hou.FloatParmTemplate(
        "flare_intensity", "Flare Intensity", 1,
        default_value=(0.3,), min=0.0, max=2.0,
    ))
    post_folder.addParmTemplate(hou.ToggleParmTemplate(
        "enable_sensor_noise", "Enable Sensor Noise",
        default_value=True,
    ))
    post_folder.addParmTemplate(hou.FloatParmTemplate(
        "photon_noise_amount", "Photon Noise", 1,
        default_value=(1.0,), min=0.0, max=3.0,
    ))
    post_folder.addParmTemplate(hou.FloatParmTemplate(
        "read_noise_amount", "Read Noise", 1,
        default_value=(1.0,), min=0.0, max=5.0,
    ))
    post_folder.addParmTemplate(hou.ToggleParmTemplate(
        "enable_stmap", "Generate STMap AOV",
        default_value=False,
    ))
    ptg.append(post_folder)

    # --- Pipeline / Metadata tab ---
    meta_folder = hou.FolderParmTemplate(
        "metadata_tab", "Pipeline",
        folder_type=hou.folderType.Tabs,
    )
    meta_folder.addParmTemplate(hou.ToggleParmTemplate(
        "write_cooke_i", "Write Cooke /i Metadata",
        default_value=True,
        help="Author Cooke /i Technology metadata on RenderProduct.",
    ))
    meta_folder.addParmTemplate(hou.ToggleParmTemplate(
        "write_aswf_exr", "Write ASWF EXR Headers",
        default_value=True,
        help="Author ASWF standard EXR metadata.",
    ))
    meta_folder.addParmTemplate(hou.StringParmTemplate(
        "usd_camera_path", "USD Camera Prim", 1,
        default_value=("/CinemaRig/Camera",),
        help="Prim path for the USD camera in the stage.",
    ))
    ptg.append(meta_folder)

    hda_def.setParmTemplateGroup(ptg)

    # ── 10. Wire internal camera parameters ──────────────
    cam_node = hda_node.node("cinema_camera")
    if cam_node:
        cam_node.parm("focal").setExpression('ch("../focal_length_mm")')
        cam_node.parm("aperture").setExpression('ch("../sensor_width_mm")')
        cam_node.parm("resx").setExpression('ch("../resolution_x")')
        cam_node.parm("resy").setExpression('ch("../resolution_y")')

    # Wire entrance pupil offset to pivot null
    pivot_node = hda_node.node("entrance_pupil_pivot")
    if pivot_node:
        # Offset along camera Z axis (negative = toward scene)
        pivot_node.parm("tz").setExpression(
            '-ch("../entrance_pupil_offset_mm") / 10.0'
        )

    # ── 11. Set HDA metadata ─────────────────────────────
    hda_def.setIcon("OBJ_camera")
    hda_def.setComment(
        "Cinema Camera Rig v2.0\n"
        "Virtual Cinematography Simulator\n"
        "Physically accurate lens behavior, biomechanics, and post-processing."
    )
    hda_def.setExtraInfo(
        "Cinema Camera Rig v4.0 (HDA v2.0)\n"
        "Sub-HDAs: chops_biomechanics, cop_anamorphic_flare, "
        "cop_sensor_noise, cop_stmap_aov\n"
        "Pillars: A (MechanicalSpec), B (Nodal Parallax), "
        "C (Biomechanics), D (CVEX Lens Shader), "
        "E (Pipeline Bridge), F (Dynamic Mumps), G (Copernicus 2.0)"
    )

    # ── 12. Push instance state into definition & save ───
    # Expressions set on instance children (step 10) must be
    # captured into the HDA definition before saving, otherwise
    # matchCurrentDefinition() will revert them to defaults.
    hda_def.updateFromNode(hda_node)
    hda_def.save(hda_path)
    hda_node.matchCurrentDefinition()

    return hda_path
