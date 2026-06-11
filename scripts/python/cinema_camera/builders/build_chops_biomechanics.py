"""
Cinema Camera Rig v4.0 -- CHOPs Biomechanics HDA Builder

Creates cinema::chops_biomechanics::3.0
Physically-based camera inertia: spring solver + lag + optional handheld shake.

Executed through Synapse bridge in a live Houdini session.
"""

from __future__ import annotations

import os

from .parm_templates import _callback_shim

# Auto-derive callback: shim over cinema_camera.hda_callbacks (formulas
# live in biomechanics.auto_derive_from_weight -- single source).
_AUTO_DERIVE_CALLBACK = _callback_shim("auto_derive_chops")


def build_chops_biomechanics_hda(
    save_dir: str = None,
    hda_name: str = "cinema_chops_biomechanics_3.0.hda",
) -> str:
    """
    Build the CHOPs biomechanics HDA and save to disk.
    Returns absolute path to saved .hda file.
    """
    import hou

    if save_dir is None:
        # v3.0: consolidate into <repo>/otls/ (Houdini auto-scans).
        repo = os.environ.get("CINEMA_CAMERA_REPO")
        if repo:
            save_dir = os.path.join(repo, "otls")
        else:
            cinema_path = os.environ.get("CINEMA_CAMERA_PATH", "")
            save_dir = os.path.join(cinema_path, "hda", "chops")
    os.makedirs(save_dir, exist_ok=True)

    # ── Create temporary CHOP network ────────────────────
    obj = hou.node("/obj")
    temp_net = obj.createNode("chopnet", "__cinema_chops_build")

    # Build inside a subnet (subnet can be converted to HDA)
    sub = temp_net.createNode("subnet", "__biomech_sub")

    # The HDA's input connector, visible inside the subnet. (The previous
    # build used an unconfigured Fetch CHOP here, so the HDA silently
    # ignored whatever was wired into it.)
    subnet_input = sub.indirectInputs()[0]

    # Operator delay FIRST (the solver springs toward the lagged target --
    # same order as the LOP solver in cinema_camera.biomechanics).
    # Lag CHOP works in SECONDS; the parm is in frames.
    operator_delay = sub.createNode("lag", "operator_delay")
    operator_delay.parm("lag1").setExpression('ch("../../lag_frames") / $FPS')
    if operator_delay.parm("lag2") is not None:
        operator_delay.parm("lag2").setExpression('ch("../../lag_frames") / $FPS')
    operator_delay.setInput(0, subnet_input)

    # Spring solver -- applies inertia dynamics.
    # Spring CHOP's dampingk is a damping CONSTANT, not a ratio:
    # critical damping at c = 2*sqrt(k*m). With mass=1, c = 2*sqrt(k)*zeta.
    inertia_solver = sub.createNode("spring", "inertia_solver")
    inertia_solver.parm("springk").setExpression('ch("../../spring_constant")')
    inertia_solver.parm("mass").set(1.0)
    inertia_solver.parm("dampingk").setExpression(
        '2 * sqrt(ch("../../spring_constant")) * ch("../../damping_ratio")'
    )
    inertia_solver.setInput(0, operator_delay)

    # Handheld shake (per-channel noise; Math CHOP combines by index)
    handheld_shake = sub.createNode("noise", "handheld_shake")
    handheld_shake.parm("channelname").set("shake1 shake2 shake3")
    handheld_shake.parm("seed").set(7)
    handheld_shake.parm("amp").setExpression('ch("../../shake_amplitude_deg")')
    # Period = 1/frequency (seconds per cycle)
    handheld_shake.parm("period").setExpression('1.0 / ch("../../shake_frequency_hz")')
    handheld_shake.parm("function").set(4)  # Sparse noise

    # Combine: lag+spring output + optional shake (match by index -- the
    # shake channels are named shake*, the motion channels keep the
    # caller's names)
    combine_motion = sub.createNode("math", "combine_motion")
    combine_motion.parm("chopop").set(1)  # Add
    if combine_motion.parm("match") is not None:
        combine_motion.parm("match").set("index")
    combine_motion.setInput(0, inertia_solver)
    combine_motion.setInput(1, handheld_shake)

    # Switch for handheld enable/disable
    handheld_enable = sub.createNode("switch", "handheld_enable")
    handheld_enable.parm("index").setExpression('ch("../../enable_handheld")')
    handheld_enable.setInput(0, inertia_solver)   # Off: lag+spring only
    handheld_enable.setInput(1, combine_motion)   # On: lag+spring+shake

    # Output (pull-based consumers use chop() on this node's channels)
    out = sub.createNode("null", "OUT_biomechanics")
    out.setInput(0, handheld_enable)
    out.setDisplayFlag(True)

    # Layout
    sub.layoutChildren()

    # ── Convert subnet to HDA ──────────────────────────────
    hda_path = os.path.join(save_dir, hda_name)
    # Type name must include ::version explicitly (the `version` kwarg only sets metadata).
    hda_node = sub.createDigitalAsset(
        name="cinema::chops_biomechanics::3.0",
        hda_file_name=hda_path,
        description="Cinema Biomechanics",
        min_num_inputs=1,
        max_num_inputs=1,
        version="3.0",
        ignore_external_references=True,
    )
    hda_def = hda_node.type().definition()

    # ── Parameter interface ──────────────────────────────
    ptg = hda_node.parmTemplateGroup()

    # Folder 1: Rig Weight
    rig_folder = hou.FolderParmTemplate("rig_weight_folder", "Rig Weight")
    rig_folder.addParmTemplate(hou.FloatParmTemplate(
        "combined_weight_kg", "Combined Weight (kg)", 1,
        default_value=(7.5,), min=1.0, max=30.0,
        help="Total rig weight. Reads from USD cinema:rig:combinedWeightKg.",
        script_callback=_AUTO_DERIVE_CALLBACK,
        script_callback_language=hou.scriptLanguage.Python,
    ))
    rig_folder.addParmTemplate(hou.FloatParmTemplate(
        "moment_arm_cm", "Moment Arm (cm)", 1,
        default_value=(18.0,), min=5.0, max=50.0,
        help="Distance from tripod pivot to center of mass.",
    ))
    ptg.append(rig_folder)

    # Folder 2: Solver
    solver_folder = hou.FolderParmTemplate("solver_folder", "Solver")
    solver_folder.addParmTemplate(hou.ToggleParmTemplate(
        "auto_derive", "Auto Derive from Weight",
        default_value=True,
        help="Compute spring/damping/lag from combined_weight_kg.",
        script_callback=_AUTO_DERIVE_CALLBACK,
        script_callback_language=hou.scriptLanguage.Python,
    ))
    solver_folder.addParmTemplate(hou.FloatParmTemplate(
        "spring_constant", "Spring Constant", 1,
        default_value=(15.0,), min=1.0, max=30.0,
        help="Higher = snappier response. Auto-derived from weight.",
    ))
    solver_folder.addParmTemplate(hou.FloatParmTemplate(
        "damping_ratio", "Damping Ratio", 1,
        default_value=(0.5,), min=0.0, max=1.0,
        help="Velocity damping. 0=undamped, 1=critically damped.",
    ))
    solver_folder.addParmTemplate(hou.FloatParmTemplate(
        "lag_frames", "Lag (frames)", 1,
        default_value=(2.25,), min=0.0, max=20.0,
        help="Operator reaction delay in frames.",
    ))
    ptg.append(solver_folder)

    # Folder 3: Handheld Shake
    shake_folder = hou.FolderParmTemplate("handheld_folder", "Handheld Shake")
    shake_folder.addParmTemplate(hou.ToggleParmTemplate(
        "enable_handheld", "Enable Handheld Shake",
        default_value=False,
    ))
    shake_folder.addParmTemplate(hou.FloatParmTemplate(
        "shake_amplitude_deg", "Amplitude (deg)", 1,
        default_value=(0.2,), min=0.0, max=2.0,
        help="Peak random rotation. Inversely proportional to weight.",
    ))
    shake_folder.addParmTemplate(hou.FloatParmTemplate(
        "shake_frequency_hz", "Frequency (Hz)", 1,
        default_value=(5.5,), min=1.0, max=15.0,
        help="Dominant shake frequency. Lighter rigs shake faster.",
    ))
    ptg.append(shake_folder)

    hda_def.setParmTemplateGroup(ptg)

    # ── HDA metadata ─────────────────────────────────────
    hda_def.setIcon("CHOP_spring")
    hda_def.setComment(
        "Operator biomechanics: physically-based camera inertia"
    )
    hda_def.setExtraInfo(
        "Cinema Camera Rig v4.0 -- Pillar C: Biomechanics\n"
        "Spring+lag solver driven by physical rig weight.\n"
        "Auto-derives spring_k, damping, lag from combined_weight_kg."
    )

    # ── Save and clean up ────────────────────────────────
    hda_def.updateFromNode(hda_node)
    hda_def.save(hda_path)
    hda_node.destroy()
    temp_net.destroy()

    return hda_path
