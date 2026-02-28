"""
Cinema Camera Rig v4.0 -- Focus Pull Example Scene Builder

Creates cinema_rig_focus_pull_example.hip with:
  - cinema::camera_rig::2.0 instance (Cooke 50mm on ALEXA 35)
  - Focus distance animated 10m -> 0.5m over 96 frames
  - Reference geometry: grid + sphere + torus at varying depths
  - Karma XPU render settings at 1920x1080
  - Sticky notes explaining the setup

Execute in a live Houdini session via Synapse or Python Shell.
"""

from __future__ import annotations

import os


def build_focus_pull_example(
    save_path: str = None,
) -> str:
    """
    Build the focus pull example .hip file.

    Returns: Absolute path to saved .hip file.
    """
    import hou

    if save_path is None:
        save_path = os.path.join(
            os.environ.get("CINEMA_CAMERA_PATH", ""),
            "examples",
            "cinema_rig_focus_pull_example.hip",
        )

    # Ensure directory exists
    os.makedirs(os.path.dirname(save_path), exist_ok=True)

    # ── 1. Clear scene ──────────────────────────────────
    hou.hipFile.clear(suppress_save_prompt=True)
    hou.setFps(24)
    hou.playbar.setFrameRange(1, 96)
    hou.playbar.setPlaybackRange(1, 96)

    # Ensure cinema camera HDA is loaded
    hda_file = os.path.join(
        os.environ.get("CINEMA_CAMERA_PATH", ""),
        "hda", "cinema_camera_rig_2.0.hda",
    )
    if os.path.isfile(hda_file):
        hou.hda.installFile(hda_file)

    obj = hou.node("/obj")

    # ── 2. Reference geometry ───────────────────────────
    # Grid (ground plane at z=0)
    geo_ground = obj.createNode("geo", "ground_plane")
    grid = geo_ground.createNode("grid", "ground")
    grid.parm("sizex").set(20)
    grid.parm("sizey").set(20)
    grid.parm("rows").set(20)
    grid.parm("cols").set(20)
    grid.setDisplayFlag(True)
    grid.setRenderFlag(True)
    geo_ground.parm("ty").set(-1)

    # Sphere (foreground subject at z=-2, close to camera)
    geo_sphere = obj.createNode("geo", "subject_sphere")
    sphere = geo_sphere.createNode("sphere", "sphere")
    sphere.parm("radx").set(0.5)
    sphere.parm("rady").set(0.5)
    sphere.parm("radz").set(0.5)
    sphere.parm("freq").set(4)
    sphere.setDisplayFlag(True)
    sphere.setRenderFlag(True)
    geo_sphere.parm("tz").set(-2)

    # Torus (background element at z=-10)
    geo_torus = obj.createNode("geo", "background_torus")
    torus = geo_torus.createNode("torus", "torus")
    torus.parm("radx").set(1.0)
    torus.parm("rady").set(0.3)
    torus.setDisplayFlag(True)
    torus.setRenderFlag(True)
    geo_torus.parm("tz").set(-10)
    geo_torus.parm("ty").set(0.5)

    # ── 3. Camera rig ──────────────────────────────────
    # Try to create cinema::camera_rig::2.0 if HDA is installed,
    # otherwise fall back to a standard cam with matching parms
    try:
        rig = obj.createNode("cinema::camera_rig", "camera_rig")
    except hou.OperationFailed:
        # HDA not installed -- use a standard camera as stand-in
        rig = obj.createNode("cam", "camera_rig")
        rig.parm("focal").set(50.0)
        rig.parm("aperture").set(28.0)
        rig.parm("resx").set(1920)
        rig.parm("resy").set(1080)
        rig.parm("near").set(0.1)
        rig.parm("far").set(100000)

    if rig.parm("tz"):
        rig.parm("tz").set(3)
    if rig.parm("ty"):
        rig.parm("ty").set(1)

    # ── 4. Animate focus distance ──────────────────────
    # Cooke 50mm defaults: start focused on background (10m),
    # pull to foreground (0.5m) over 96 frames
    focus_parm = None
    if rig.parm("focus_distance_m"):
        focus_parm = rig.parm("focus_distance_m")
    elif rig.parm("focus"):
        focus_parm = rig.parm("focus")

    if focus_parm:
        # Frame 1: focus at 10m (background torus)
        hou.setFrame(1)
        focus_parm.deleteAllKeyframes()
        k1 = hou.Keyframe()
        k1.setFrame(1)
        k1.setValue(10.0)
        k1.setSlopeAuto(True)
        focus_parm.setKeyframe(k1)

        # Frame 96: focus at 0.5m (foreground sphere)
        k2 = hou.Keyframe()
        k2.setFrame(96)
        k2.setValue(0.5)
        k2.setSlopeAuto(True)
        focus_parm.setKeyframe(k2)

    # ── 5. Karma XPU render settings ───────────────────
    # Create a ROP network with Karma XPU
    rop = hou.node("/out")
    try:
        karma = rop.createNode("karma", "karma_xpu")
        if karma.parm("renderer"):
            karma.parm("renderer").set("XPU")
        # Resolution override to 1920x1080
        if karma.parm("override_camerares"):
            karma.parm("override_camerares").set(True)
            karma.parm("res_overridex").set(1920)
            karma.parm("res_overridey").set(1080)
        elif karma.parm("res_fraction"):
            karma.parm("res_fraction").set("specific")
            if karma.parm("res_overridex"):
                karma.parm("res_overridex").set(1920)
                karma.parm("res_overridey").set(1080)
        # Point to our camera
        if karma.parm("camera"):
            karma.parm("camera").set(rig.path())
        # Frame range
        if karma.parm("trange"):
            karma.parm("trange").set(1)  # Render frame range
            karma.parm("f1").set(1)
            karma.parm("f2").set(96)
            karma.parm("f3").set(1)
    except hou.OperationFailed:
        pass  # Karma not available in this Houdini build

    # ── 6. Sticky notes ────────────────────────────────
    note_overview = obj.createStickyNote("note_overview")
    note_overview.setText(
        "CINEMA CAMERA RIG v4.0 -- Focus Pull Example\n"
        "=============================================\n\n"
        "This scene demonstrates anamorphic squeeze breathing\n"
        "(mumps effect) during a focus pull.\n\n"
        "- Cooke Anamorphic /i S35 50mm on ALEXA 35\n"
        "- Focus animated: 10m (background) -> 0.5m (foreground)\n"
        "- 96 frames at 24fps (4 seconds)\n\n"
        "Watch the Effective Squeeze parameter change as focus racks.\n"
        "Close focus = reduced squeeze = visible breathing."
    )
    note_overview.setPosition(hou.Vector2(-5, 3))
    note_overview.setSize(hou.Vector2(5, 3.5))
    note_overview.setColor(hou.Color(0.95, 0.9, 0.7))

    note_render = obj.createStickyNote("note_render")
    note_render.setText(
        "RENDERING\n"
        "=========\n\n"
        "Karma XPU configured at /out/karma_xpu\n"
        "Resolution: 1920x1080\n"
        "Frame range: 1-96\n\n"
        "Cooke /i metadata is written to EXR automatically."
    )
    note_render.setPosition(hou.Vector2(-5, -1))
    note_render.setSize(hou.Vector2(5, 2.5))
    note_render.setColor(hou.Color(0.8, 0.9, 0.95))

    # ── 7. Layout and save ─────────────────────────────
    obj.layoutChildren()
    hou.setFrame(1)
    hou.hipFile.save(save_path)

    return save_path


if __name__ == "__main__":
    result = build_focus_pull_example()
    print(f"Example scene saved: {result}")
