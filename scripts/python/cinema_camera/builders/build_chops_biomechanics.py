"""
Cinema Camera Rig v4.0 -- CHOPs Biomechanics HDA Builder

Creates cinema::chops_biomechanics::1.0
Physically-based camera inertia: spring solver + lag + optional handheld shake.

Executed through Synapse bridge in a live Houdini session.
"""

from __future__ import annotations

import os


# Auto-derive callback script embedded in the HDA
_AUTO_DERIVE_CALLBACK = '''
node = kwargs["node"]
if node.parm("auto_derive").eval():
    weight = node.parm("combined_weight_kg").eval()

    # Mirrors biomechanics.py derivation (weight-driven, not inertia-driven)
    spring_k = max(5.0, 25.0 - weight * 1.3)
    damping = min(0.95, 0.6 + weight * 0.025)
    lag = weight * 0.3
    shake_amp = max(0.05, 1.5 / weight)
    shake_freq = max(2.0, 8.0 - weight * 0.3)

    node.parm("spring_constant").set(spring_k)
    node.parm("damping_ratio").set(damping)
    node.parm("lag_frames").set(lag)
    node.parm("shake_amplitude_deg").set(shake_amp)
    node.parm("shake_frequency_hz").set(shake_freq)
'''


def build_chops_biomechanics_hda(
    save_dir: str = None,
    hda_name: str = "cinema_chops_biomechanics_1.0.hda",
) -> str:
    """
    Build the CHOPs biomechanics HDA and save to disk.
    Returns absolute path to saved .hda file.
    """
    import hou

    if save_dir is None:
        cinema_path = os.environ.get("CINEMA_CAMERA_PATH", "")
        save_dir = os.path.join(cinema_path, "hda", "chops")
    os.makedirs(save_dir, exist_ok=True)

    # ── Create temporary CHOP network ────────────────────
    obj = hou.node("/obj")
    temp_net = obj.createNode("chopnet", "__cinema_chops_build")

    # Build inside a subnet (subnet can be converted to HDA)
    sub = temp_net.createNode("subnet", "__biomech_sub")

    # Raw camera input (user wires Pan/Tilt/Roll here)
    raw_input = sub.createNode("fetch", "raw_camera_input")

    # Solver parameters (constant node holding derived values)
    solver_params = sub.createNode("constant", "solver_params")
    solver_params.parm("name0").set("spring_k")
    solver_params.parm("value0").setExpression('ch("../../spring_constant")')
    solver_params.parm("name1").set("damping")
    solver_params.parm("value1").setExpression('ch("../../damping_ratio")')
    solver_params.parm("name2").set("lag_frames")
    solver_params.parm("value2").setExpression('ch("../../lag_frames")')
    solver_params.parm("name3").set("shake_amp")
    solver_params.parm("value3").setExpression('ch("../../shake_amplitude_deg")')
    solver_params.parm("name4").set("shake_freq")
    solver_params.parm("value4").setExpression('ch("../../shake_frequency_hz")')

    # Spring solver -- applies inertia dynamics
    inertia_solver = sub.createNode("spring", "inertia_solver")
    inertia_solver.parm("springk").setExpression('ch("../../spring_constant")')
    inertia_solver.parm("dampingk").setExpression('ch("../../damping_ratio")')
    inertia_solver.setInput(0, raw_input)

    # Operator delay
    operator_delay = sub.createNode("lag", "operator_delay")
    operator_delay.parm("lag1").setExpression('ch("../../lag_frames")')
    operator_delay.setInput(0, inertia_solver)

    # Handheld shake (sparse noise)
    handheld_shake = sub.createNode("noise", "handheld_shake")
    handheld_shake.parm("amp").setExpression('ch("../../shake_amplitude_deg")')
    # Period = 1/frequency (seconds per cycle)
    handheld_shake.parm("period").setExpression('1.0 / ch("../../shake_frequency_hz")')
    handheld_shake.parm("function").set(4)  # Sparse noise

    # Combine: spring+lag output + optional shake
    combine_motion = sub.createNode("math", "combine_motion")
    combine_motion.parm("chopop").set(1)  # Add
    combine_motion.setInput(0, operator_delay)
    combine_motion.setInput(1, handheld_shake)

    # Switch for handheld enable/disable
    handheld_enable = sub.createNode("switch", "handheld_enable")
    handheld_enable.parm("index").setExpression('ch("../../enable_handheld")')
    handheld_enable.setInput(0, operator_delay)   # Off: spring+lag only
    handheld_enable.setInput(1, combine_motion)   # On: spring+lag+shake

    # Output
    out = sub.createNode("null", "OUT_biomechanics")
    out.setInput(0, handheld_enable)
    out.setDisplayFlag(True)
    out.setExportFlag(True)

    # Layout
    sub.layoutChildren()

    # ── Convert subnet to HDA ──────────────────────────────
    hda_path = os.path.join(save_dir, hda_name)
    hda_node = sub.createDigitalAsset(
        name="cinema::chops_biomechanics",
        hda_file_name=hda_path,
        description="Cinema Biomechanics",
        min_num_inputs=1,
        max_num_inputs=1,
        version="1.0",
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

    hda_node.setParmTemplateGroup(ptg)

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
    hda_def.save(hda_path)
    hda_node.destroy()
    temp_net.destroy()

    return hda_path
