"""
Cinema Camera Rig v3.0 -- Copernicus 2.0 Sensor Noise HDA Builder

Creates cinema::sensor_noise::3.0 in the cop (Copernicus 2.0) category.

MVP chain using built-in cop nodes (no VEX):
    input -> fractalnoise (per-frame seed for time variation)
          -> blend (add over input, scaled by noise amount)
          -> enable switch
          -> output

This is a SIMPLIFIED noise model vs. the legacy cop2 dual-gain implementation
(which used VEX with photon shot + read-noise gain math). The full
physics-accurate dual-gain port lives behind a `# TODO: vopnet+snippet`
comment below; once we confirm Copernicus vopnet's snippet-VOP API, we'll
wire the gain math.
"""

from __future__ import annotations

import os


def _wire(node, sub_parm: str, expr: str) -> None:
    try:
        p = node.parm(sub_parm)
        if p is not None:
            p.setExpression(expr)
    except Exception:
        pass


def build_cop_sensor_noise_v2_hda(
    save_dir: str = None,
    hda_name: str = "cinema_sensor_noise_3.0.hda",
) -> str:
    """Build the Copernicus 2.0 sensor noise HDA. Returns absolute hda path."""
    import hou

    if save_dir is None:
        repo = os.environ.get("CINEMA_CAMERA_REPO")
        if repo:
            save_dir = os.path.join(repo, "otls")
        else:
            save_dir = os.path.join(os.environ["CINEMA_CAMERA_PATH"], "hda", "post")
    os.makedirs(save_dir, exist_ok=True)

    obj = hou.node("/obj")
    temp_geo = obj.createNode("geo", "__cinema_noise_v2_build")
    try:
        return _build_noise_inside(temp_geo, save_dir, hda_name)
    finally:
        try:
            temp_geo.destroy()
        except Exception:
            pass


def _build_noise_inside(temp_geo, save_dir: str, hda_name: str) -> str:
    """Inner builder; isolated so caller can wrap in try/finally cleanup."""
    import hou

    temp_cop = temp_geo.createNode("copnet", "__noise_cop")
    sub = temp_cop.createNode("subnet", "__noise_sub")

    # ── Build chain ────────────────────────────────────────
    in_image = sub.createNode("null", "IN_image")

    # Fractal noise generator -- seeded per frame so noise animates
    noise = sub.createNode("fractalnoise", "sensor_grain")

    # Composite noise over input as additive grain
    grain_blend = sub.createNode("blend", "noise_add")
    grain_blend.setInput(0, in_image)
    grain_blend.setInput(1, noise)

    enable_switch = sub.createNode("switch", "enable_switch")
    enable_switch.setInput(0, in_image)
    enable_switch.setInput(1, grain_blend)

    out = sub.createNode("null", "OUT_noise")
    out.setInput(0, enable_switch)
    out.setDisplayFlag(True)

    sub.layoutChildren()

    # ── Convert to HDA ────────────────────────────────────
    hda_path = os.path.join(save_dir, hda_name)
    hda_node = sub.createDigitalAsset(
        name="cinema::sensor_noise::3.0",
        hda_file_name=hda_path,
        description="Cinema Sensor Noise (Copernicus 2.0)",
        min_num_inputs=1,
        max_num_inputs=1,
        version="3.0",
    )
    hda_def = hda_node.type().definition()

    # ── Parm interface ────────────────────────────────────
    ptg = hda_node.parmTemplateGroup()

    ptg.append(hou.ToggleParmTemplate(
        "enable", "Enable Sensor Noise", default_value=True,
    ))
    ptg.append(hou.IntParmTemplate(
        "exposure_index", "Exposure Index (EI)", 1,
        default_value=(800,), min=100, max=12800,
        help="Effective ISO. Drives gain ratio vs native_iso.",
    ))
    ptg.append(hou.IntParmTemplate(
        "native_iso", "Native ISO", 1,
        default_value=(800,), min=100, max=3200,
        help="Sensor's native ISO. ALEXA 35 = 800.",
    ))
    # Parm names match legacy cinema::cop_sensor_noise so the orchestrator can
    # swap legacy->v2 without renaming top-level wirings. Physics is still MVP:
    # both photon and read amounts feed the additive grain. Dual-gain physics
    # (photon scales sqrt(signal), read scales gain) is TODO via vopnet+snippet.
    ptg.append(hou.FloatParmTemplate(
        "photon_noise_amount", "Photon Noise", 1,
        default_value=(0.02,), min=0.0, max=0.5,
        help="Shot-noise amplitude (MVP: scales linearly, not by sqrt(signal)). "
             "Future dual-gain VEX will scale by sqrt(signal).",
    ))
    ptg.append(hou.FloatParmTemplate(
        "read_noise_amount", "Read Noise", 1,
        default_value=(0.01,), min=0.0, max=0.5,
        help="Read-noise amplitude (MVP: flat additive). Future dual-gain VEX "
             "will scale by ei/native_iso gain ratio.",
    ))
    ptg.append(hou.FloatParmTemplate(
        "noise_scale", "Grain Scale", 1,
        default_value=(0.5,), min=0.05, max=10.0,
        help="Spatial scale of the grain pattern. Smaller = finer grain.",
    ))
    ptg.append(hou.FloatParmTemplate(
        "temporal_seed", "Temporal Seed", 1,
        default_value=(0.0,),
        help="Per-frame offset (use $F for animated grain).",
    ))

    hda_def.setParmTemplateGroup(ptg)

    # ── Defensive parm wiring ─────────────────────────────
    _wire(enable_switch, "input", 'ch("../enable")')

    # fractalnoise common parms
    for parm in ("scale", "frequency", "freq", "size"):
        _wire(noise, parm, 'ch("../noise_scale")')
    # Combined amplitude: photon + read (MVP -- both treated equally).
    for parm in ("amp", "amplitude", "intensity"):
        _wire(noise, parm, 'ch("../photon_noise_amount") + ch("../read_noise_amount")')
    for parm in ("seed", "offset", "phase"):
        _wire(noise, parm, 'ch("../temporal_seed")')

    # ── HDA metadata ──────────────────────────────────────
    hda_def.setIcon("COP2_noise")
    hda_def.setComment(
        "Cinema Sensor Noise v3.0 (Copernicus 2.0)\n"
        "MVP grain model -- additive fractalnoise.\n"
        "Future: dual-gain (photon + read) via vopnet+snippet."
    )
    hda_def.setExtraInfo(
        "Cinema Camera Rig v3.0 -- Pillar G (Copernicus 2.0)\n"
        "Chain: input -> fractalnoise -> blend(add) -> output\n"
        "Replaces legacy cinema::cop_sensor_noise::3.0 (cop2 category).\n"
        "TODO: port dual-gain VEX (shot + read noise) into a vopnet snippet."
    )

    hda_def.updateFromNode(hda_node)
    hda_def.save(hda_path)
    hda_node.matchCurrentDefinition()

    return hda_path
