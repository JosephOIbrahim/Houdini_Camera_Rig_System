"""
Cinema Camera Rig v4.0 -- Shared Parameter Templates

Builds the HDA parameter interface used by both the OBJ orchestrator
(cinema::camera_rig::2.0) and the LOP builder (cinema::camera_rig_lop::1.0).

Extracted from build_camera_rig_orchestrator.py to avoid duplication.
"""

from __future__ import annotations


def build_camera_rig_parm_templates():
    """
    Build the full 5-tab parameter interface for the cinema camera rig.

    Returns a list of hou.FolderParmTemplate objects (one per tab) that can
    be appended to any HDA's parmTemplateGroup.

    Must be called inside a live Houdini session (imports hou).
    """
    import hou

    folders = []

    # ═══════════════════════════════════════════════════════
    # TAB 1: LENS
    # ═══════════════════════════════════════════════════════
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
        help="T-stop = f-stop / lens transmission. Lower = more light. "
             "Unlike f-stop, T-stop accounts for light lost in glass elements.",
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
    eff_squeeze_pt = hou.FloatParmTemplate(
        "effective_squeeze", "Effective Squeeze", 1,
        default_value=(2.0,), min=1.0, max=2.0,
        help="Focus-dependent squeeze (computed from SqueezeBreathingCurve). "
             "Read-only -- driven by focus_distance_m and squeeze breathing curve.",
    )
    eff_squeeze_pt.setConditional(
        hou.parmCondType.DisableWhen, '{ lens_id != "" }'
    )
    lens_folder.addParmTemplate(eff_squeeze_pt)
    lens_folder.addParmTemplate(hou.FloatParmTemplate(
        "entrance_pupil_offset_mm", "Entrance Pupil Offset (mm)", 1,
        default_value=(125.0,), min=0.0, max=500.0,
        help="Distance from sensor to nodal point. Critical for parallax-correct pans.",
    ))
    lens_folder.addParmTemplate(hou.LabelParmTemplate(
        "label_pupil_pivot", "Pivot Offset",
        column_labels=("Entrance pupil pivot visible on null in viewport",),
    ))
    folders.append(lens_folder)

    # ═══════════════════════════════════════════════════════
    # TAB 2: DISTORTION
    # ═══════════════════════════════════════════════════════
    dist_folder = hou.FolderParmTemplate(
        "distortion_tab", "Distortion",
        folder_type=hou.folderType.Tabs,
    )
    for parm_name, label, default, parm_help in [
        ("dist_k1", "K1 (Radial)", 0.0,
         "2nd-order radial distortion. Positive = barrel (edges bow out), "
         "negative = pincushion (edges bow in). Primary distortion term."),
        ("dist_k2", "K2 (Radial)", 0.0,
         "4th-order radial distortion. Higher-order correction that refines K1. "
         "Usually smaller magnitude than K1."),
        ("dist_k3", "K3 (Radial)", 0.0,
         "6th-order radial distortion. Fine correction for extreme corners. "
         "Typically near zero except on very wide or vintage lenses."),
        ("dist_p1", "P1 (Tangential)", 0.0,
         "Horizontal tangential distortion from lens element decentering. "
         "Causes asymmetric shift. Usually very small on modern lenses."),
        ("dist_p2", "P2 (Tangential)", 0.0,
         "Vertical tangential distortion from lens element decentering. "
         "Causes asymmetric shift. Usually very small on modern lenses."),
        ("dist_sq_uniformity", "Squeeze Uniformity", 1.0,
         "Anamorphic squeeze uniformity across the field. 1.0 = perfectly "
         "uniform squeeze. <1.0 = squeeze falls off toward edges (horizontal "
         "vs vertical stretching differs at periphery)."),
    ]:
        dist_folder.addParmTemplate(hou.FloatParmTemplate(
            parm_name, label, 1,
            default_value=(default,),
            help=parm_help,
        ))
    folders.append(dist_folder)

    # ═══════════════════════════════════════════════════════
    # TAB 3: CAMERA BODY
    # ═══════════════════════════════════════════════════════
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
        help="Horizontal pixel count. ALEXA 35 6K Open Gate: 4608. "
             "Drives Karma render resolution.",
    ))
    body_folder.addParmTemplate(hou.IntParmTemplate(
        "resolution_y", "Resolution Y", 1,
        default_value=(3164,), min=256, max=8192,
        help="Vertical pixel count. ALEXA 35 6K Open Gate: 3164. "
             "Drives Karma render resolution.",
    ))
    body_folder.addParmTemplate(hou.IntParmTemplate(
        "exposure_index", "Exposure Index (EI)", 1,
        default_value=(800,), min=100, max=12800,
        help="Camera sensitivity setting (ISO-equivalent). Higher EI = brighter "
             "image but more noise. Written to Cooke /i metadata.",
    ))
    body_folder.addParmTemplate(hou.IntParmTemplate(
        "native_iso", "Native ISO", 1,
        default_value=(800,), min=100, max=3200,
        help="Sensor's base ISO with optimal dynamic range. ALEXA 35: 800. "
             "Noise model scales relative to this value.",
    ))
    folders.append(body_folder)

    # ═══════════════════════════════════════════════════════
    # TAB 4: BIOMECHANICS
    # ═══════════════════════════════════════════════════════
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
        help="Distance from fluid head pivot to camera CG in cm. "
             "Longer arms (big lenses) increase rotational inertia and lag.",
    ))
    bio_folder.addParmTemplate(hou.FloatParmTemplate(
        "spring_constant", "Spring Constant", 1,
        default_value=(15.0,), min=1.0, max=30.0,
        help="Fluid head spring stiffness. Higher = snappier pan/tilt response. "
             "Lower = mushier, more cinematic drift. Auto-derived from weight.",
    ))
    bio_folder.addParmTemplate(hou.FloatParmTemplate(
        "damping_ratio", "Damping Ratio", 1,
        default_value=(0.5,), min=0.0, max=1.0,
        help="Fluid head damping. 0 = undamped (oscillates), 1 = critically "
             "damped (no overshoot). Typical fluid heads: 0.4-0.7.",
    ))
    bio_folder.addParmTemplate(hou.FloatParmTemplate(
        "lag_frames", "Lag (frames)", 1,
        default_value=(2.25,), min=0.0, max=10.0,
        help="Operator reaction delay in frames. Heavier rigs have more lag. "
             "Simulates the human response time when following action.",
    ))
    bio_folder.addParmTemplate(hou.SeparatorParmTemplate("sep_handheld"))
    bio_folder.addParmTemplate(hou.LabelParmTemplate(
        "label_handheld", "Handheld Shake",
    ))
    bio_folder.addParmTemplate(hou.ToggleParmTemplate(
        "enable_handheld", "Enable Handheld Shake",
        default_value=False,
        help="Add procedural handheld camera shake. Amplitude and frequency "
             "are derived from rig weight when auto-derive is on.",
    ))
    bio_folder.addParmTemplate(hou.FloatParmTemplate(
        "shake_amplitude_deg", "Shake Amplitude (deg)", 1,
        default_value=(0.2,), min=0.0, max=2.0,
        help="Peak random rotation in degrees. Lighter rigs shake more. "
             "0.1-0.3 = subtle handheld, 0.5+ = agitated/run-and-gun.",
    ))
    bio_folder.addParmTemplate(hou.FloatParmTemplate(
        "shake_frequency_hz", "Shake Frequency (Hz)", 1,
        default_value=(5.5,), min=1.0, max=15.0,
        help="Dominant shake frequency in Hz. Human handheld typically 4-7 Hz. "
             "Lower = slow sway, higher = jittery vibration.",
    ))
    bio_folder.addParmTemplate(hou.ToggleParmTemplate(
        "auto_derive", "Auto Derive from Weight",
        default_value=True,
        help="Auto-compute spring/damping/lag from combined weight.",
    ))
    folders.append(bio_folder)

    # ═══════════════════════════════════════════════════════
    # TAB 5: POST-PROCESSING
    # ═══════════════════════════════════════════════════════
    post_folder = hou.FolderParmTemplate(
        "post_tab", "Post-Processing",
        folder_type=hou.folderType.Tabs,
    )
    post_folder.addParmTemplate(hou.ToggleParmTemplate(
        "enable_flare", "Enable Anamorphic Flare",
        default_value=True,
        help="Apply horizontal anamorphic lens flare to bright sources. "
             "Uses cinema::cop_anamorphic_flare::2.0 in the COP pipeline.",
    ))
    post_folder.addParmTemplate(hou.FloatParmTemplate(
        "flare_threshold", "Flare Threshold", 1,
        default_value=(3.0,), min=0.5, max=20.0,
        help="Luminance threshold above which flare is generated. "
             "Lower = more flares from dimmer sources. 3.0 = bright highlights only.",
    ))
    post_folder.addParmTemplate(hou.FloatParmTemplate(
        "flare_intensity", "Flare Intensity", 1,
        default_value=(0.3,), min=0.0, max=2.0,
        help="Flare streak intensity multiplier. 0.3 = subtle, 1.0 = prominent. "
             "Follows intensity <= 1.0 lighting law for physical plausibility.",
    ))
    post_folder.addParmTemplate(hou.SeparatorParmTemplate("sep_noise"))
    post_folder.addParmTemplate(hou.LabelParmTemplate(
        "label_noise", "Sensor Noise",
    ))
    post_folder.addParmTemplate(hou.ToggleParmTemplate(
        "enable_sensor_noise", "Enable Sensor Noise",
        default_value=True,
        help="Apply physically-modeled sensor noise. Combines photon (shot) "
             "noise and electronic read noise based on EI and native ISO.",
    ))
    post_folder.addParmTemplate(hou.FloatParmTemplate(
        "photon_noise_amount", "Photon Noise", 1,
        default_value=(1.0,), min=0.0, max=3.0,
        help="Photon (shot) noise multiplier. Signal-dependent noise that "
             "increases in bright areas. 1.0 = physically accurate.",
    ))
    post_folder.addParmTemplate(hou.FloatParmTemplate(
        "read_noise_amount", "Read Noise", 1,
        default_value=(1.0,), min=0.0, max=5.0,
        help="Electronic read noise multiplier. Constant-level noise from "
             "sensor electronics. Visible in shadows. 1.0 = physically accurate.",
    ))
    post_folder.addParmTemplate(hou.ToggleParmTemplate(
        "enable_stmap", "Generate STMap AOV",
        default_value=False,
        help="Output an ST map AOV encoding lens distortion for Nuke/Flame "
             "post-production. Uses cinema::cop_stmap_aov::1.0.",
    ))
    folders.append(post_folder)

    # ═══════════════════════════════════════════════════════
    # TAB 6: PIPELINE / METADATA
    # ═══════════════════════════════════════════════════════
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
    folders.append(meta_folder)

    return folders
