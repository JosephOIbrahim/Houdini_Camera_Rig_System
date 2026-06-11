"""
Cinema Camera Rig v4.0 -- Shared Parameter Templates

Builds the HDA parameter interface used by both the OBJ orchestrator
(cinema::camera_rig::3.0) and the LOP builder (cinema::camera_rig_lop::3.0).

Extracted from build_camera_rig_orchestrator.py to avoid duplication.

All script callbacks are thin shims over cinema_camera.hda_callbacks --
logic baked into HDA callback strings cannot be hot-fixed, package code
can. Keep the shims dumb.
"""

from __future__ import annotations


def _callback_shim(function_name: str) -> str:
    """Build the standard bootstrap-and-dispatch callback string."""
    return (
        "import os, sys\n"
        "repo = os.environ.get('CINEMA_CAMERA_REPO', '')\n"
        "sp = os.path.join(repo, 'scripts', 'python')\n"
        "if repo and sp not in sys.path:\n"
        "    sys.path.insert(0, sp)\n"
        "from cinema_camera import hda_callbacks\n"
        "hda_callbacks.{fn}(kwargs.get('node'))\n"
    ).format(fn=function_name)


def build_camera_rig_parm_templates(context: str = "obj"):
    """
    Build the full tabbed parameter interface for the cinema camera rig.

    context: "obj" for the OBJ orchestrator (adds keyframable fluid-head
    target pan/tilt/roll that drive the CHOP biomechanics chain), "lop"
    for the Solaris rig (adds input_camera_path for the USD spring filter).

    Returns a list of parm templates (top-level controls + one
    FolderParmTemplate per tab) to append to an HDA's parmTemplateGroup.

    Must be called inside a live Houdini session (imports hou).
    """
    import hou

    # ═══════════════════════════════════════════════════════
    # TOP-LEVEL CONTROLS (sit above the tab folders)
    # ═══════════════════════════════════════════════════════
    look_through = hou.ButtonParmTemplate(
        "look_through_camera", "Look Through Camera",
        script_callback=_callback_shim("look_through"),
        script_callback_language=hou.scriptLanguage.Python,
        join_with_next=True,
        help="Lock the active SceneViewer to this rig's camera. Works in /obj "
             "(inner cinema_camera) and /stage (USD camera prim).",
    )

    show_nodal_guide = hou.ToggleParmTemplate(
        "show_nodal_guide", "Show Nodal Point Guide",
        default_value=False,
        help="Draw the small yellow-orange ring at the entrance pupil "
             "(nodal point) for parallax-correct pan setup. /obj rig only -- "
             "the LOP rig uses a USD guide-purpose Xform that Solaris "
             "controls separately via the viewport Guide-purpose toggle.",
    )

    top_level = [look_through, show_nodal_guide]

    folders = []

    # ═══════════════════════════════════════════════════════
    # TAB 0: PRESET -- 2026 professional cinema body presets
    # ═══════════════════════════════════════════════════════
    # Preset data lives in cinema_camera.presets.CAMERA_PRESETS; the apply
    # logic in cinema_camera.hda_callbacks.apply_preset (which chains
    # apply_lens, so lens-derived parms follow the preset's lens pairing).
    preset_folder = hou.FolderParmTemplate(
        "preset_tab", "Preset",
        folder_type=hou.folderType.Tabs,
    )

    preset_folder.addParmTemplate(hou.MenuParmTemplate(
        "camera_preset", "Camera Preset",
        menu_items=(
            "alexa_35",
            "alexa_mini_lf",
            "alexa_65",
            "sony_venice_2",
            "red_v_raptor_8k_vv",
            "blackmagic_ursa_cine_12k_lf",
        ),
        menu_labels=(
            "ARRI ALEXA 35 (S35, 4.6K Open Gate)",
            "ARRI ALEXA Mini LF (LF, 4.5K Open Gate)",
            "ARRI ALEXA 65 (65mm, 6.5K Open Gate)",
            "Sony VENICE 2 (FF, 8.6K)",
            "RED V-RAPTOR 8K VV (Vista Vision)",
            "Blackmagic URSA Cine 12K LF",
        ),
        default_value=0,
        help="Top 6 professional cinema bodies in 2026 use, paired with "
             "the Cooke anamorphic family. S35 bodies pair with Cooke "
             "Anamorphic/i S35 (2.0x); LF/VV/65 bodies pair with Cooke "
             "Anamorphic/i Full Frame Plus (1.8x).",
    ))

    preset_folder.addParmTemplate(hou.ButtonParmTemplate(
        "apply_preset", "Apply Preset",
        script_callback=_callback_shim("apply_preset"),
        script_callback_language=hou.scriptLanguage.Python,
        help="Bulk-fill body + lens parms from the selected preset, then "
             "load the paired lens spec (distortion, pupil offset, rig "
             "weight). After applying you can override any individual parm "
             "on the other tabs.",
    ))

    preset_folder.addParmTemplate(hou.StringParmTemplate(
        "preset_status", "Last Applied", 1,
        default_value=("(no preset applied yet)",),
        help="Read-only label confirming which preset was last applied.",
    ))

    preset_folder.addParmTemplate(hou.SeparatorParmTemplate("preset_sep"))

    preset_folder.addParmTemplate(hou.LabelParmTemplate(
        "preset_doc",
        "Lens-family pairing: ALEXA 35 -> Cooke Anamorphic/i S35 (2.0x squeeze). "
        "All other bodies -> Cooke Anamorphic/i FF+ (1.8x squeeze).",
    ))

    folders.append(preset_folder)

    # ═══════════════════════════════════════════════════════
    # TAB 1: LENS
    # ═══════════════════════════════════════════════════════
    lens_folder = hou.FolderParmTemplate(
        "lens_tab", "Lens",
        folder_type=hou.folderType.Tabs,
    )
    # Common cinema prime focal lengths. Picking one auto-fills
    # focal_length_mm AND retargets lens_id to the family's prime at that
    # focal length when one exists (hda_callbacks.focal_preset_changed).
    lens_folder.addParmTemplate(hou.MenuParmTemplate(
        "focal_length_preset", "Common Prime",
        menu_items=(
            "custom", "18", "21", "25", "32", "35", "40", "50", "65",
            "75", "85", "100", "135", "180", "200", "300",
        ),
        menu_labels=(
            "Custom (use slider below)",
            "18mm (ultra-wide)", "21mm (wide)", "25mm (wide)", "32mm",
            "35mm", "40mm", "50mm (normal)", "65mm",
            "75mm", "85mm", "100mm (portrait)", "135mm",
            "180mm (tele)", "200mm (tele)", "300mm (long tele)",
        ),
        default_value=7,   # 50mm
        script_callback=_callback_shim("focal_preset_changed"),
        script_callback_language=hou.scriptLanguage.Python,
        help="Pick from common cinema prime focal lengths -- fills the "
             "Focal Length slider and, when the current lens family has a "
             "prime at that length, switches Lens ID to it (loading its "
             "distortion + squeeze curves). 'Custom' frees the slider.",
    ))
    lens_folder.addParmTemplate(hou.StringParmTemplate(
        "lens_id", "Lens ID", 1,
        default_value=("cooke_ana_i_s35_50mm",),
        script_callback=_callback_shim("apply_lens"),
        script_callback_language=hou.scriptLanguage.Python,
        help="Lens identifier resolved through cinema_camera.registry "
             "(JSON spec under cinema_camera/lenses/). Editing it loads "
             "the spec; the Preset tab fills it automatically.",
    ))
    lens_folder.addParmTemplate(hou.ButtonParmTemplate(
        "apply_lens", "Apply Lens",
        script_callback=_callback_shim("apply_lens"),
        script_callback_language=hou.scriptLanguage.Python,
        join_with_next=True,
        help="Re-load the LensSpec for the current Lens ID: fills focal "
             "length, squeeze, Brown-Conrady distortion, entrance pupil "
             "offset, and combined rig weight.",
    ))
    lens_folder.addParmTemplate(hou.StringParmTemplate(
        "lens_status", "Lens Status", 1,
        default_value=("(lens spec not loaded yet -- click Apply Lens)",),
        help="Read-only label for the last lens-spec load.",
    ))
    lens_folder.addParmTemplate(hou.FloatParmTemplate(
        "focal_length_mm", "Focal Length (mm)", 1,
        default_value=(50.0,), min=8.0, max=600.0,
        help="Lens focal length in millimeters. Drives camera aperture and FOV. "
             "Common cinema primes: 25, 32, 50, 75, 100, 135 mm.",
    ))
    lens_folder.addParmTemplate(hou.FloatParmTemplate(
        "t_stop", "T-Stop", 1,
        default_value=(2.8,), min=1.0, max=22.0,
        help="T-stop = f-stop / lens transmission. Lower = more light, shallower DOF. "
             "Unlike f-stop, T-stop accounts for light lost in glass elements. "
             "Cooke anamorphic primes: T2.3 wide-open, T22 stopped down. "
             "Clamped to the loaded lens's physical range at cook time.",
    ))
    lens_folder.addParmTemplate(hou.FloatParmTemplate(
        "shutter_angle_deg", "Shutter Angle (deg)", 1,
        default_value=(180.0,), min=1.0, max=360.0,
        help="Camera shutter angle. Cinema standard is 180 degrees (1/48s "
             "exposure at 24fps). 90 = sharper motion (Saving Private Ryan), "
             "270-360 = motion-blurred (dream/dance sequences). Drives motion "
             "blur and the cinema:camera:shutterAngleDeg USD attribute.",
    ))
    lens_folder.addParmTemplate(hou.FloatParmTemplate(
        "focus_distance_m", "Focus Distance (m)", 1,
        default_value=(3.0,), min=0.3, max=1000.0,
        script_callback=_callback_shim("focus_changed"),
        script_callback_language=hou.scriptLanguage.Python,
        help="Focus distance. Drives dynamic squeeze and DOF. Clamped to "
             "the loaded lens's close focus (MOD) at cook time. Editing it "
             "refreshes Effective Squeeze from the lens breathing curve.",
    ))
    lens_folder.addParmTemplate(hou.FloatParmTemplate(
        "squeeze_ratio", "Squeeze Ratio", 1,
        default_value=(2.0,), min=1.0, max=2.0,
        help="Nominal anamorphic squeeze. Dynamic squeeze computed from focus distance.",
    ))
    eff_squeeze_pt = hou.FloatParmTemplate(
        "effective_squeeze", "Effective Squeeze", 1,
        default_value=(2.0,), min=1.0, max=2.0,
        help="Focus-dependent squeeze (mumps). When the Lens ID resolves, "
             "the LOP rig computes this AT COOK TIME from the lens's "
             "squeeze-breathing curve and Focus Distance (so animated "
             "focus pulls breathe correctly); this parm then only feeds "
             "the OBJ post satellites. Without a resolved lens, this "
             "manual value is used everywhere.",
    )
    eff_squeeze_pt.setConditional(
        hou.parmCondType.DisableWhen, '{ lens_id != "" }'
    )
    lens_folder.addParmTemplate(eff_squeeze_pt)
    lens_folder.addParmTemplate(hou.FloatParmTemplate(
        "entrance_pupil_offset_mm", "Entrance Pupil Offset (mm)", 1,
        default_value=(125.0,), min=0.0, max=500.0,
        help="Distance from sensor to nodal point (toward the scene). "
             "Critical for parallax-correct pans. Auto-filled from the "
             "lens spec by Apply Lens.",
    ))
    folders.append(lens_folder)

    # ═══════════════════════════════════════════════════════
    # TAB 2: DISTORTION
    # ═══════════════════════════════════════════════════════
    dist_folder = hou.FolderParmTemplate(
        "distortion_tab", "Distortion",
        folder_type=hou.folderType.Tabs,
    )

    dist_folder.addParmTemplate(hou.LabelParmTemplate(
        "label_distortion",
        "Distortion values load from the lens spec via Apply Lens / Apply "
        "Preset. Use Squeeze Uniformity for anamorphic edge falloff -- the "
        "most common artist-facing tweak. Enable 'Show Advanced' below to "
        "edit raw Brown-Conrady coefficients directly.",
    ))

    dist_folder.addParmTemplate(hou.FloatParmTemplate(
        "dist_sq_uniformity", "Squeeze Uniformity", 1,
        default_value=(1.0,), min=0.8, max=1.0,
        help="Anamorphic squeeze uniformity across the field. 1.0 = perfectly "
             "uniform squeeze (modern Cooke). 0.92-0.97 = vintage anamorphic "
             "with squeeze falloff toward edges -- the 'oval bokeh' look.",
    ))

    dist_folder.addParmTemplate(hou.SeparatorParmTemplate("sep_dist_advanced"))

    dist_folder.addParmTemplate(hou.ToggleParmTemplate(
        "show_advanced_distortion", "Show Advanced (Brown-Conrady)",
        default_value=False,
        help="Reveal raw Brown-Conrady distortion coefficients (K1, K2, K3, "
             "P1, P2). Normally loaded from the lens spec; expose for "
             "manual override during plate-matching or pre-vis-to-comp work.",
    ))

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
    ]:
        pt = hou.FloatParmTemplate(
            parm_name, label, 1,
            default_value=(default,),
            help=parm_help,
        )
        pt.setConditional(
            hou.parmCondType.HideWhen,
            "{ show_advanced_distortion == 0 }",
        )
        dist_folder.addParmTemplate(pt)
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
        default_value=(27.99,),
        help="Active sensor width. ALEXA 35: 27.99mm (4.6K 3:2 Open Gate).",
    ))
    body_folder.addParmTemplate(hou.FloatParmTemplate(
        "sensor_height_mm", "Sensor Height (mm)", 1,
        default_value=(19.22,),
        help="Active sensor height. ALEXA 35: 19.22mm (4.6K 3:2 Open Gate).",
    ))
    body_folder.addParmTemplate(hou.IntParmTemplate(
        "resolution_x", "Resolution X", 1,
        default_value=(4608,), min=256, max=16384,
        help="Horizontal pixel count. ALEXA 35 4.6K Open Gate: 4608. "
             "Drives Karma render resolution.",
    ))
    body_folder.addParmTemplate(hou.IntParmTemplate(
        "resolution_y", "Resolution Y", 1,
        default_value=(3164,), min=256, max=16384,
        help="Vertical pixel count. ALEXA 35 4.6K Open Gate: 3164. "
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

    if context == "obj":
        # Keyframable fluid-head targets: the operator's intended pan/tilt/
        # roll. The CHOP chain fetches these, applies lag -> spring (+
        # optional shake), and the filtered result drives the fluid_head
        # null inside the rig. Keyframe THESE, not the HDA transform (the
        # HDA transform is tripod placement).
        bio_folder.addParmTemplate(hou.LabelParmTemplate(
            "label_targets",
            "Keyframe the targets below for pan/tilt/roll moves; the "
            "biomechanics filter drives the fluid head from them. The "
            "node transform places the tripod.",
        ))
        for parm_name, label, parm_help in (
            ("target_pan_deg", "Target Pan (deg)",
             "Operator's intended pan (Y rotation). Filtered through the "
             "spring/lag solver onto the fluid head."),
            ("target_tilt_deg", "Target Tilt (deg)",
             "Operator's intended tilt (X rotation). Filtered through the "
             "spring/lag solver onto the fluid head."),
            ("target_roll_deg", "Target Roll (deg)",
             "Dutch/roll (Z rotation). Filtered through the spring/lag "
             "solver onto the fluid head."),
        ):
            bio_folder.addParmTemplate(hou.FloatParmTemplate(
                parm_name, label, 1,
                default_value=(0.0,), min=-180.0, max=180.0,
                help=parm_help,
            ))
    else:
        bio_folder.addParmTemplate(hou.StringParmTemplate(
            "input_camera_path", "Input Camera Prim", 1,
            default_value=("",),
            help="USD prim path with xformOp:rotateXYZ animation to filter through "
                 "the spring/lag solver. Output is written to /CinemaRig/FluidHead. "
                 "Leave empty to skip the spring filter (handheld shake still applies "
                 "if enabled). Common pattern: point at a Houdini-authored cam prim.",
        ))

    bio_folder.addParmTemplate(hou.FloatParmTemplate(
        "combined_weight_kg", "Combined Weight (kg)", 1,
        default_value=(7.5,), min=1.0, max=30.0,
        help="Body + lens weight. Filled by Apply Preset / Apply Lens "
             "(body weight from presets + lens weight from the spec).",
    ))
    bio_folder.addParmTemplate(hou.FloatParmTemplate(
        "moment_arm_cm", "Moment Arm (cm)", 1,
        default_value=(18.0,), min=5.0, max=50.0,
        help="Distance from fluid head pivot to camera CG in cm. "
             "Longer arms (big lenses) increase rotational inertia and lag.",
    ))
    bio_folder.addParmTemplate(hou.ToggleParmTemplate(
        "auto_derive", "Auto-Derive from Rig Weight",
        default_value=True,
        help="Compute spring constant, damping, lag, and handheld shake from "
             "combined_weight_kg using physically-grounded formulas "
             "(cinema_camera.biomechanics.auto_derive_from_weight). "
             "Turn off to reveal manual sliders for spring/damping/lag/shake.",
    ))

    _spring_pt = hou.FloatParmTemplate(
        "spring_constant", "Spring Constant", 1,
        default_value=(15.0,), min=1.0, max=30.0,
        help="Fluid head spring stiffness. Higher = snappier pan/tilt response. "
             "Lower = mushier, more cinematic drift.",
    )
    _spring_pt.setConditional(hou.parmCondType.HideWhen, "{ auto_derive == 1 }")
    bio_folder.addParmTemplate(_spring_pt)

    _damping_pt = hou.FloatParmTemplate(
        "damping_ratio", "Damping Ratio", 1,
        default_value=(0.5,), min=0.0, max=1.0,
        help="Fluid head damping. 0 = undamped (oscillates), 1 = critically "
             "damped (no overshoot). Typical fluid heads: 0.4-0.7.",
    )
    _damping_pt.setConditional(hou.parmCondType.HideWhen, "{ auto_derive == 1 }")
    bio_folder.addParmTemplate(_damping_pt)

    _lag_pt = hou.FloatParmTemplate(
        "lag_frames", "Lag (frames)", 1,
        default_value=(2.25,), min=0.0, max=10.0,
        help="Operator reaction delay in frames. Heavier rigs have more lag. "
             "Simulates the human response time when following action.",
    )
    _lag_pt.setConditional(hou.parmCondType.HideWhen, "{ auto_derive == 1 }")
    bio_folder.addParmTemplate(_lag_pt)

    bio_folder.addParmTemplate(hou.SeparatorParmTemplate("sep_handheld"))
    bio_folder.addParmTemplate(hou.LabelParmTemplate(
        "label_handheld", "Handheld Shake",
    ))
    bio_folder.addParmTemplate(hou.ToggleParmTemplate(
        "enable_handheld", "Enable Handheld Shake",
        default_value=False,
        help="Add procedural handheld camera shake on top of any spring/lag "
             "filtering. Picks a style preset below or set amplitude/frequency "
             "manually (only visible when Auto-Derive is off).",
    ))

    bio_folder.addParmTemplate(hou.MenuParmTemplate(
        "handheld_style", "Handheld Style",
        menu_items=("custom", "tripod", "steadicam", "operator", "handheld", "verite"),
        menu_labels=(
            "Custom (set sliders manually)",
            "Tripod (locked-off, ~0.05deg / 3Hz)",
            "Steadicam (smooth float, ~0.10deg / 4Hz)",
            "Operator (pro handheld, ~0.20deg / 5.5Hz)",
            "Handheld (typical handheld, ~0.40deg / 6.5Hz)",
            "Verite (agitated documentary, ~0.80deg / 8Hz)",
        ),
        default_value=3,  # "operator" -- matches the amp/freq defaults below
        script_callback=_callback_shim("handheld_style_changed"),
        script_callback_language=hou.scriptLanguage.Python,
        help="Pick a handheld shooting style -- fills shake amplitude + "
             "frequency below. Choose Custom to set sliders manually. "
             "Selecting a non-Custom style also flips Enable Handheld on.",
    ))

    _shake_amp_pt = hou.FloatParmTemplate(
        "shake_amplitude_deg", "Shake Amplitude (deg)", 1,
        default_value=(0.2,), min=0.0, max=2.0,
        help="Peak random rotation in degrees. Lighter rigs shake more. "
             "0.1-0.3 = subtle handheld, 0.5+ = agitated/run-and-gun.",
    )
    _shake_amp_pt.setConditional(hou.parmCondType.HideWhen, "{ auto_derive == 1 }")
    bio_folder.addParmTemplate(_shake_amp_pt)

    _shake_freq_pt = hou.FloatParmTemplate(
        "shake_frequency_hz", "Shake Frequency (Hz)", 1,
        default_value=(5.5,), min=1.0, max=15.0,
        help="Dominant shake frequency in Hz. Human handheld typically 4-7 Hz. "
             "Lower = slow sway, higher = jittery vibration.",
    )
    _shake_freq_pt.setConditional(hou.parmCondType.HideWhen, "{ auto_derive == 1 }")
    bio_folder.addParmTemplate(_shake_freq_pt)
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
             "Uses cinema::cop_anamorphic_flare::3.0 in the COP pipeline.",
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
             "post-production. Uses cinema::cop_stmap_aov::3.0.",
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

    return top_level + folders
