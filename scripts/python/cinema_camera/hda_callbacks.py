"""
Cinema Camera Rig -- HDA parameter callbacks.

Single source of truth for every script_callback on the rig HDAs. The
parm-template callback strings (builders/parm_templates.py) are 6-line
shims that bootstrap sys.path from $CINEMA_CAMERA_REPO and call into here:

    from cinema_camera import hda_callbacks
    hda_callbacks.apply_preset(kwargs.get('node'))

Keep ALL logic here -- callback strings baked into shipped HDAs cannot be
hot-fixed, a package module can.
"""

from __future__ import annotations

import re

from .biomechanics import auto_derive_from_weight
from .presets import body_weight_for, get_preset
from .registry import lens_json_dir, resolve_lens


# Handheld style presets: style -> (shake_amplitude_deg, shake_frequency_hz)
HANDHELD_STYLES = {
    "tripod":    (0.05, 3.0),
    "steadicam": (0.10, 4.0),
    "operator":  (0.20, 5.5),
    "handheld":  (0.40, 6.5),
    "verite":    (0.80, 8.0),
}


def _warn(message: str) -> None:
    import hou
    if hou.isUIAvailable():
        hou.ui.displayMessage(message)
    else:
        print("[cinema_camera]", message)


def _set(node, parm_name: str, value) -> None:
    parm = node.parm(parm_name)
    if parm is not None:
        parm.set(value)


# ════════════════════════════════════════════════════════════
# LENS
# ════════════════════════════════════════════════════════════

def apply_lens(node) -> None:
    """
    Load the LensSpec for the node's lens_id and fill every lens-derived
    parm: focal, squeeze, effective squeeze (at current focus), Brown-
    Conrady coefficients, entrance pupil offset, and combined rig weight
    (body weight from presets + lens weight from the spec).
    """
    if node is None:
        return
    lens_id = (node.evalParm("lens_id") or "").strip()
    if not lens_id:
        _set(node, "lens_status", "(no lens_id set)")
        return
    try:
        spec = resolve_lens(lens_id)
    except (KeyError, ValueError, OSError) as exc:
        # KeyError: unknown id/missing JSON; ValueError: malformed spec
        # (protocol validation); OSError: unreadable file.
        _set(node, "lens_status", "FAILED: " + str(exc))
        _warn(str(exc))
        return

    focus = node.evalParm("focus_distance_m") or 3.0
    focus = max(focus, spec.close_focus_m)

    d = spec.distortion
    values = {
        "focal_length_mm":     spec.focal_length_mm,
        "squeeze_ratio":       spec.squeeze_ratio,
        "effective_squeeze":   spec.effective_squeeze(focus),
        "dist_k1":             d.k1,
        "dist_k2":             d.k2,
        "dist_k3":             d.k3,
        "dist_p1":             d.p1,
        "dist_p2":             d.p2,
        "dist_sq_uniformity":  d.squeeze_uniformity,
        # Always written (0.0 when the spec has no mechanics) so switching
        # lenses never leaves a stale offset from the previous lens.
        "entrance_pupil_offset_mm": spec.entrance_pupil_offset_mm,
    }

    body_weight = body_weight_for(node.evalParm("body_id") or "")
    if body_weight is not None and spec.weight_kg > 0:
        values["combined_weight_kg"] = body_weight + spec.weight_kg

    for parm_name, value in values.items():
        _set(node, parm_name, value)

    # Keep the Common Prime menu coherent with the loaded lens.
    menu_parm = node.parm("focal_length_preset")
    if menu_parm is not None:
        token = "%g" % spec.focal_length_mm
        tokens = menu_parm.parmTemplate().menuItems()
        menu_parm.set(token if token in tokens else "custom")

    _set(node, "lens_status",
         "Loaded: %s (f=%gmm T%g-%g, %gx)" % (
             spec.lens_id, spec.focal_length_mm,
             spec.t_stop_min, spec.t_stop_max, spec.squeeze_ratio))


def focus_changed(node) -> None:
    """
    Focus Distance callback: refresh effective_squeeze from the lens's
    squeeze-breathing curve so the OBJ post satellites track focus pulls.
    (The LOP rig recomputes effective squeeze at cook time regardless.)
    Touches ONLY effective_squeeze -- manual distortion tweaks survive.
    """
    if node is None:
        return
    lens_id = (node.evalParm("lens_id") or "").strip()
    if not lens_id:
        return
    try:
        spec = resolve_lens(lens_id)
    except (KeyError, ValueError, OSError):
        return
    focus = max(node.evalParm("focus_distance_m") or 3.0, spec.close_focus_m)
    _set(node, "effective_squeeze", spec.effective_squeeze(focus))


def focal_preset_changed(node) -> None:
    """
    Common Prime menu callback. Sets the focal slider; if the current lens
    family has a prime at that focal length, retargets lens_id to it and
    re-applies the lens so curves/coefficients follow the focal choice.
    """
    if node is None:
        return
    token = node.parm("focal_length_preset").evalAsString()
    if token == "custom":
        return
    try:
        focal = float(token)
    except ValueError:
        return
    _set(node, "focal_length_mm", focal)

    lens_id = (node.evalParm("lens_id") or "").strip()
    match = re.match(r"^(.*)_(\d+)mm(_.*)?$", lens_id)
    if not match:
        return
    family_prefix = match.group(1)
    candidates = sorted(lens_json_dir().glob(
        "%s_%dmm*.json" % (family_prefix, int(focal))))
    if candidates:
        _set(node, "lens_id", candidates[0].stem)
        apply_lens(node)
    else:
        _set(node, "lens_status",
             "(no %s prime at %gmm -- custom focal, curves from %s)" % (
                 family_prefix, focal, lens_id))


# ════════════════════════════════════════════════════════════
# PRESET
# ════════════════════════════════════════════════════════════

def apply_preset(node) -> None:
    """
    Bulk-fill body + lens parms from the selected camera preset, then run
    apply_lens() so lens-derived parms (distortion, pupil, weight) follow.
    """
    if node is None:
        return
    key = node.parm("camera_preset").evalAsString()
    try:
        preset = get_preset(key)
    except KeyError as exc:
        _warn(str(exc))
        return

    for parm_name, value in (
        ("body_id",            preset["body_id"]),
        ("sensor_width_mm",    preset["sensor_width_mm"]),
        ("sensor_height_mm",   preset["sensor_height_mm"]),
        ("resolution_x",       preset["resolution_x"]),
        ("resolution_y",       preset["resolution_y"]),
        ("native_iso",         preset["native_iso"]),
        ("exposure_index",     preset["native_iso"]),
        ("combined_weight_kg", preset["body_weight_kg"]),
        ("focal_length_mm",    preset["default_focal_length_mm"]),
        ("t_stop",             preset["default_t_stop"]),
        ("squeeze_ratio",      preset["squeeze_ratio"]),
        ("effective_squeeze",  preset["squeeze_ratio"]),
    ):
        _set(node, parm_name, value)

    lens_id = "%s_%dmm" % (preset["lens_family"],
                           int(preset["default_focal_length_mm"]))
    _set(node, "lens_id", lens_id)
    _set(node, "preset_status", "Applied: " + preset["label"])

    # parm.set() does not fire parm callbacks -- chain the lens load.
    apply_lens(node)


# ════════════════════════════════════════════════════════════
# BIOMECHANICS
# ════════════════════════════════════════════════════════════

def handheld_style_changed(node) -> None:
    """Handheld Style menu: fill amp/freq and enable handheld."""
    if node is None:
        return
    style = node.parm("handheld_style").evalAsString()
    values = HANDHELD_STYLES.get(style)
    if values is None:  # "custom"
        return
    amp, freq = values
    _set(node, "shake_amplitude_deg", amp)
    _set(node, "shake_frequency_hz", freq)
    _set(node, "enable_handheld", True)


def auto_derive_chops(node) -> None:
    """
    cinema::chops_biomechanics callback: derive solver parms from rig
    weight (formulas: biomechanics.auto_derive_from_weight).
    """
    if node is None or not node.parm("auto_derive").eval():
        return
    derived = auto_derive_from_weight(node.parm("combined_weight_kg").eval())
    for parm_name, value in derived.items():
        _set(node, parm_name, value)


# ════════════════════════════════════════════════════════════
# VIEWPORT
# ════════════════════════════════════════════════════════════

def look_through(node) -> None:
    """Lock the active SceneViewer to this rig's camera (OBJ or LOP)."""
    import hou
    if node is None:
        return
    viewer = hou.ui.paneTabOfType(hou.paneTabType.SceneViewer)
    if viewer is None:
        return
    viewport = viewer.curViewport()
    category = node.type().category().name()
    if category == "Object":
        inner = node.node("cinema_camera")
        if inner is not None:
            viewport.setCamera(inner)
    elif category == "Lop":
        rig = node.evalParm("usd_camera_path") or "/CinemaRig"
        if rig == "/CinemaRig/Camera":
            rig = "/CinemaRig"
        viewer.setPwd(node)
        viewport.setCamera(rig + "/FluidHead/Body/Sensor")
