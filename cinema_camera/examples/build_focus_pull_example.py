"""
Cinema Camera Rig v4.0 -- Focus Pull Demo Scene Builder

Creates cinema_rig_focus_pull_example.hip showcasing ALL rig features:

  1. SQUEEZE BREATHING -- Focus racks from 12m to 1.5m. Watch the
     Effective Squeeze parm shift as focus changes (mumps effect).
     Objects at 3 depth planes make the DOF shift visible.

  2. BIOMECHANICS -- Camera dollies forward and pans right. The
     spring/lag solver adds weight and subtle overshoot to the
     movement, making it feel like a real operator on a fluid head.

  3. HANDHELD SHAKE -- Subtle organic micro-tremor layered on top
     of the dolly/pan. Amplitude 0.15 deg at 5.5 Hz.

  4. ANAMORPHIC FLARE -- Bright emissive spheres at the far end of
     the scene create horizontal streak flares through the anamorphic
     front element.

  5. ENTRANCE PUPIL -- Yellow-orange guide visible in viewport at
     the nodal point during pan.

Scene layout (top view):

    [flare_L]       [flare_R]        z = -14
          \\         /
         [hero torus]                z = -8
              |
      [pillar]   [pillar]           z = -5
              |
        [foreground sphere]          z = -1.5
              |
         >>> CAMERA >>>              z = 4 -> 2  (dolly)
              |
    ========================         ground plane

Execute in a live Houdini session via Synapse or Python Shell.
"""

from __future__ import annotations

import os


def build_focus_pull_example(
    save_path: str = None,
) -> str:
    """
    Build the focus pull demo .hip file.

    Returns: Absolute path to saved .hip file.
    """
    import hou

    if save_path is None:
        save_path = os.path.join(
            os.environ.get("CINEMA_CAMERA_PATH", ""),
            "examples",
            "cinema_rig_focus_pull_example.hip",
        )

    os.makedirs(os.path.dirname(save_path), exist_ok=True)

    # ── 1. Scene setup ────────────────────────────────────
    hou.hipFile.clear(suppress_save_prompt=True)
    hou.setFps(24)
    hou.playbar.setFrameRange(1, 120)
    hou.playbar.setPlaybackRange(1, 120)

    # Load all cinema HDAs
    hda_base = os.environ.get("CINEMA_CAMERA_PATH", "")
    if hda_base:
        hda_dir = os.path.join(hda_base, "hda")
        for sub in ["", "chops", "post"]:
            d = os.path.join(hda_dir, sub) if sub else hda_dir
            if os.path.isdir(d):
                for f in os.listdir(d):
                    if f.endswith(".hda"):
                        try:
                            hou.hda.installFile(os.path.join(d, f))
                        except Exception:
                            pass

    obj = hou.node("/obj")

    # ── Helper: keyframe a parm ───────────────────────────
    def set_key(parm, frame, value):
        k = hou.Keyframe()
        k.setFrame(frame)
        k.setValue(value)
        k.setSlopeAuto(True)
        parm.setKeyframe(k)

    # ── 2. Ground plane ───────────────────────────────────
    # Large checker-pattern ground for spatial reference and
    # to show anamorphic distortion on straight lines
    geo_ground = obj.createNode("geo", "ground_plane")
    grid = geo_ground.createNode("grid", "ground")
    grid.parm("sizex").set(30)
    grid.parm("sizey").set(40)
    grid.parm("rows").set(60)
    grid.parm("cols").set(60)
    # Add color for checker pattern
    color_node = geo_ground.createNode("color", "checker_color")
    color_node.setInput(0, grid)
    color_node.parm("colorr").set(0.18)
    color_node.parm("colorg").set(0.18)
    color_node.parm("colorb").set(0.18)
    color_node.setDisplayFlag(True)
    color_node.setRenderFlag(True)
    geo_ground.parm("ty").set(-1.2)
    geo_ground.layoutChildren()

    # ── 3. Foreground subject (z = -1.5) ──────────────────
    # Close to camera -- the focus pull DESTINATION
    geo_fg = obj.createNode("geo", "foreground_sphere")
    fg_sphere = geo_fg.createNode("sphere", "sphere")
    fg_sphere.parm("radx").set(0.4)
    fg_sphere.parm("rady").set(0.4)
    fg_sphere.parm("radz").set(0.4)
    fg_sphere.parm("freq").set(5)
    fg_color = geo_fg.createNode("color", "warm_color")
    fg_color.setInput(0, fg_sphere)
    fg_color.parm("colorr").set(0.8)
    fg_color.parm("colorg").set(0.25)
    fg_color.parm("colorb").set(0.12)
    fg_color.setDisplayFlag(True)
    fg_color.setRenderFlag(True)
    geo_fg.parm("tz").set(-1.5)
    geo_fg.parm("tx").set(0.3)
    geo_fg.parm("ty").set(-0.4)
    geo_fg.layoutChildren()

    # ── 4. Mid-ground pillars (z = -5) ────────────────────
    # Two vertical tubes framing the composition -- creates
    # depth layering and shows bokeh at different distances
    for side, tx_val in [("left", -1.8), ("right", 1.8)]:
        geo_pillar = obj.createNode("geo", "pillar_" + side)
        tube = geo_pillar.createNode("tube", "tube")
        tube.parm("radscale").set(0.25)
        tube.parm("rad1").set(0.25)
        tube.parm("rad2").set(0.25)
        tube.parm("height").set(3.0)
        tube.parm("rows").set(2)
        tube.parm("cols").set(16)
        tube.parm("cap").set(True)
        pil_color = geo_pillar.createNode("color", "pillar_color")
        pil_color.setInput(0, tube)
        pil_color.parm("colorr").set(0.35)
        pil_color.parm("colorg").set(0.35)
        pil_color.parm("colorb").set(0.4)
        pil_color.setDisplayFlag(True)
        pil_color.setRenderFlag(True)
        geo_pillar.parm("tz").set(-5)
        geo_pillar.parm("tx").set(tx_val)
        geo_pillar.parm("ty").set(0.3)
        geo_pillar.layoutChildren()

    # ── 5. Hero object -- background torus (z = -8) ───────
    # The initial focus target. Torus shows anamorphic oval
    # bokeh beautifully when out of focus
    geo_hero = obj.createNode("geo", "hero_torus")
    torus = geo_hero.createNode("torus", "torus")
    torus.parm("radx").set(1.2)
    torus.parm("rady").set(0.35)
    torus.parm("rows").set(30)
    torus.parm("cols").set(30)
    hero_color = geo_hero.createNode("color", "hero_color")
    hero_color.setInput(0, torus)
    hero_color.parm("colorr").set(0.15)
    hero_color.parm("colorg").set(0.5)
    hero_color.parm("colorb").set(0.7)
    hero_color.setDisplayFlag(True)
    hero_color.setRenderFlag(True)
    geo_hero.parm("tz").set(-8)
    geo_hero.parm("ty").set(0.3)
    geo_hero.parm("ry").set(25)
    geo_hero.layoutChildren()

    # ── 6. Flare sources (z = -14) ────────────────────────
    # Bright emissive spheres that trigger the anamorphic
    # flare streak. Placed behind the hero torus so flare
    # streaks across the composition
    for side, tx_val in [("left", -2.0), ("right", 1.5)]:
        geo_light = obj.createNode("geo", "flare_source_" + side)
        light_sphere = geo_light.createNode("sphere", "emissive")
        light_sphere.parm("radx").set(0.15)
        light_sphere.parm("rady").set(0.15)
        light_sphere.parm("radz").set(0.15)
        light_sphere.parm("freq").set(3)
        # Bright emission color (will be > 1.0 in linear, triggering flare)
        light_color = geo_light.createNode("color", "bright")
        light_color.setInput(0, light_sphere)
        light_color.parm("colorr").set(1.0)
        light_color.parm("colorg").set(0.95)
        light_color.parm("colorb").set(0.85)
        light_color.setDisplayFlag(True)
        light_color.setRenderFlag(True)
        geo_light.parm("tz").set(-14)
        geo_light.parm("tx").set(tx_val)
        geo_light.parm("ty").set(0.8 if side == "left" else 0.4)
        geo_light.layoutChildren()

    # ── 7. Scene light ────────────────────────────────────
    # Key light -- warm, slightly above and to the right
    try:
        key_light = obj.createNode("hlight", "key_light")
        key_light.parm("tx").set(5)
        key_light.parm("ty").set(6)
        key_light.parm("tz").set(2)
        # Point at scene center
        if key_light.parm("lookatpath"):
            key_light.parm("lookatpath").set("")
        key_light.parm("rx").set(-35)
        key_light.parm("ry").set(25)
        # Warm color
        if key_light.parm("light_colorr"):
            key_light.parm("light_colorr").set(1.0)
            key_light.parm("light_colorg").set(0.92)
            key_light.parm("light_colorb").set(0.82)
        if key_light.parm("light_intensity"):
            key_light.parm("light_intensity").set(1.0)
    except hou.OperationFailed:
        pass

    # Fill light -- cooler, from the left
    try:
        fill_light = obj.createNode("hlight", "fill_light")
        fill_light.parm("tx").set(-4)
        fill_light.parm("ty").set(3)
        fill_light.parm("tz").set(-3)
        fill_light.parm("rx").set(-15)
        fill_light.parm("ry").set(-30)
        if fill_light.parm("light_colorr"):
            fill_light.parm("light_colorr").set(0.7)
            fill_light.parm("light_colorg").set(0.8)
            fill_light.parm("light_colorb").set(1.0)
        if fill_light.parm("light_intensity"):
            fill_light.parm("light_intensity").set(0.4)
    except hou.OperationFailed:
        pass

    # ── 8. Camera rig ─────────────────────────────────────
    try:
        rig = obj.createNode("cinema::camera_rig", "camera_rig")
    except hou.OperationFailed:
        rig = obj.createNode("cam", "camera_rig")
        rig.parm("focal").set(50.0)
        rig.parm("aperture").set(28.0)
        rig.parm("resx").set(1920)
        rig.parm("resy").set(1080)
        rig.parm("near").set(0.1)
        rig.parm("far").set(100000)

    # Starting position: slightly elevated, looking down corridor
    if rig.parm("ty"):
        rig.parm("ty").set(0.6)

    # ── 9. Animate camera -- dolly + pan ──────────────────
    # Dolly forward: z=4 -> z=2 over 120 frames (slow push)
    tz_parm = rig.parm("tz")
    if tz_parm:
        tz_parm.deleteAllKeyframes()
        set_key(tz_parm, 1, 4.0)
        set_key(tz_parm, 120, 2.0)

    # Subtle pan right: ry=0 -> ry=4 (reveals flare sources)
    ry_parm = rig.parm("ry")
    if ry_parm:
        ry_parm.deleteAllKeyframes()
        set_key(ry_parm, 1, 0.0)
        set_key(ry_parm, 120, 4.0)

    # ── 10. Animate focus -- rack far to near ─────────────
    # Three-beat focus rack:
    #   Frames 1-40:   Hold on background hero torus (12m)
    #   Frames 41-80:  Rack to foreground sphere (1.5m)
    #   Frames 81-120: Hold on foreground
    # The rack is where squeeze breathing becomes visible
    focus_parm = None
    if rig.parm("focus_distance_m"):
        focus_parm = rig.parm("focus_distance_m")
    elif rig.parm("focus"):
        focus_parm = rig.parm("focus")

    if focus_parm:
        focus_parm.deleteAllKeyframes()
        set_key(focus_parm, 1, 12.0)    # Hold on hero torus
        set_key(focus_parm, 40, 12.0)   # Still holding
        set_key(focus_parm, 80, 1.5)    # Racked to foreground
        set_key(focus_parm, 120, 1.5)   # Hold on foreground

    # ── 11. Enable all rig features ───────────────────────
    # Biomechanics: makes the dolly/pan feel like a real operator
    if rig.parm("enable_biomechanics"):
        rig.parm("enable_biomechanics").set(True)

    # Handheld shake: subtle organic tremor
    if rig.parm("enable_handheld"):
        rig.parm("enable_handheld").set(True)
    if rig.parm("shake_amplitude_deg"):
        rig.parm("shake_amplitude_deg").set(0.15)
    if rig.parm("shake_frequency_hz"):
        rig.parm("shake_frequency_hz").set(5.5)

    # Anamorphic flare: enabled by default, lower threshold
    # to catch our emissive spheres
    if rig.parm("enable_flare"):
        rig.parm("enable_flare").set(True)
    if rig.parm("flare_threshold"):
        rig.parm("flare_threshold").set(2.0)
    if rig.parm("flare_intensity"):
        rig.parm("flare_intensity").set(0.5)

    # Sensor noise: subtle, physically based
    if rig.parm("enable_sensor_noise"):
        rig.parm("enable_sensor_noise").set(True)

    # ── 12. Karma render settings ─────────────────────────
    rop = hou.node("/out")
    try:
        karma = rop.createNode("karma", "karma_xpu")
        if karma.parm("renderer"):
            karma.parm("renderer").set("XPU")
        if karma.parm("override_camerares"):
            karma.parm("override_camerares").set(True)
            karma.parm("res_overridex").set(1920)
            karma.parm("res_overridey").set(1080)
        elif karma.parm("res_fraction"):
            karma.parm("res_fraction").set("specific")
            if karma.parm("res_overridex"):
                karma.parm("res_overridex").set(1920)
                karma.parm("res_overridey").set(1080)
        # Point to our camera's internal cam node
        if karma.parm("camera"):
            internal_cam = rig.path() + "/cinema_camera"
            if hou.node(internal_cam):
                karma.parm("camera").set(internal_cam)
            else:
                karma.parm("camera").set(rig.path())
        if karma.parm("trange"):
            karma.parm("trange").set(1)
            karma.parm("f1").set(1)
            karma.parm("f2").set(120)
            karma.parm("f3").set(1)
    except hou.OperationFailed:
        pass

    # ── 13. Sticky notes ──────────────────────────────────
    note_overview = obj.createStickyNote("note_overview")
    note_overview.setText(
        "CINEMA CAMERA RIG v4.0 -- Anamorphic Demo\n"
        "==========================================\n\n"
        "Cooke Anamorphic /i S35 50mm on ALEXA 35\n"
        "120 frames at 24fps (5 seconds)\n\n"
        "WHAT TO WATCH FOR:\n\n"
        "1. SQUEEZE BREATHING (frames 41-80)\n"
        "   Watch 'Effective Squeeze' parm during the focus rack.\n"
        "   Close focus = reduced squeeze = visible horizontal\n"
        "   breathing on straight lines (mumps effect).\n\n"
        "2. BIOMECHANICS\n"
        "   The camera dollies forward and pans right.\n"
        "   Spring/lag solver adds weight and subtle overshoot.\n"
        "   Compare: disable 'Enable Biomechanics' to see the\n"
        "   difference between raw keyframes and filtered motion.\n\n"
        "3. HANDHELD SHAKE\n"
        "   Subtle 0.15-degree tremor at 5.5 Hz.\n"
        "   Toggle 'Enable Handheld Shake' to compare.\n\n"
        "4. ANAMORPHIC FLARE\n"
        "   Bright spheres at z=-14 trigger horizontal streaks.\n"
        "   Visible in rendered output (COP post-processing).\n\n"
        "5. ENTRANCE PUPIL\n"
        "   Yellow-orange circle guide visible on the null\n"
        "   inside the HDA. Shows the nodal point for\n"
        "   parallax-correct panning."
    )
    note_overview.setPosition(hou.Vector2(-8, 4))
    note_overview.setSize(hou.Vector2(6, 7))
    note_overview.setColor(hou.Color(0.95, 0.9, 0.7))

    note_scene = obj.createStickyNote("note_scene")
    note_scene.setText(
        "SCENE LAYOUT\n"
        "============\n\n"
        "Foreground sphere  z = -1.5  (focus destination)\n"
        "Mid-ground pillars z = -5.0  (depth framing)\n"
        "Hero torus         z = -8.0  (focus origin)\n"
        "Flare sources      z = -14.0 (bright highlights)\n\n"
        "Camera dollies z=4 -> z=2 with ry=0 -> ry=4 pan.\n"
        "Focus racks from 12m (hero) to 1.5m (foreground)\n"
        "between frames 41-80."
    )
    note_scene.setPosition(hou.Vector2(-8, -4))
    note_scene.setSize(hou.Vector2(6, 3.5))
    note_scene.setColor(hou.Color(0.8, 0.9, 0.95))

    note_render = obj.createStickyNote("note_render")
    note_render.setText(
        "RENDERING\n"
        "=========\n\n"
        "Karma XPU at /out/karma_xpu\n"
        "1920x1080, frames 1-120\n\n"
        "Camera points to internal cinema_camera node.\n"
        "Cooke /i metadata written to EXR automatically.\n\n"
        "For a quick preview: render frame 60\n"
        "(mid-rack, both planes partially in focus)."
    )
    note_render.setPosition(hou.Vector2(-8, -8))
    note_render.setSize(hou.Vector2(6, 2.8))
    note_render.setColor(hou.Color(0.85, 0.95, 0.85))

    # ── 14. Layout and save ───────────────────────────────
    obj.layoutChildren()
    hou.setFrame(1)
    hou.hipFile.save(save_path)

    return save_path


if __name__ == "__main__":
    result = build_focus_pull_example()
    print(f"Example scene saved: {result}")
