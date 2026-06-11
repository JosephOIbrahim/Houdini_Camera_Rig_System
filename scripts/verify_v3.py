"""
Verify the v3.0 build is wired correctly end-to-end inside Houdini.

Checks:
  [1] cinema::camera_rig::3.0 OBJ type registered, source file is the repo
  [2] Instance creates, sub-HDAs (biomech, flare, noise, stmap) resolve to ::3.0
      (not silently fell back to placeholder nulls)
  [3] Cooks without errors
  [4] cinema::camera_rig_lop::3.0 LOP type registered, instance authors expected USD prims
  [5] Lens registry loads a brand-new focal length (32mm Cooke, didn't exist pre-v3.0)

Paste in Houdini Python shell:
    exec(open(r"C:\\Users\\User\\Houdini_Camera_Rig_System\\scripts\\verify_v3.py").read())

Test nodes are left at /obj/__verify_v3_obj and /stage/__verify_v3_lop for inspection;
destroy them manually when you're done looking.
"""

import os
import sys
import traceback

import hou


def _row(tag: str, msg: str) -> None:
    print(f"  [{tag}] {msg}")


PASS, FAIL, INFO = "PASS", "FAIL", "INFO"
_pass_count = 0
_fail_count = 0


def _ok(msg: str) -> None:
    global _pass_count
    _pass_count += 1
    _row(PASS, msg)


def _bad(msg: str) -> None:
    global _fail_count
    _fail_count += 1
    _row(FAIL, msg)


print("=" * 64)
print("Cinema Camera Rig v3.0 -- verification")
print("=" * 64)


# ──────────────────────────────────────────────────────────────────────────
# [1] OBJ orchestrator type registered, sourced from the repo
# ──────────────────────────────────────────────────────────────────────────
print("\n[1] cinema::camera_rig::3.0 OBJ type")
obj_type = hou.nodeType(hou.objNodeTypeCategory(), "cinema::camera_rig::3.0")
if obj_type is None:
    _bad("type not registered (Tab>Cinema Camera Rig will not see ::3.0)")
else:
    src = obj_type.definition().libraryFilePath() or ""
    _ok(f"registered  source={src}")
    if "Houdini_Camera_Rig_System" in src.replace("/", "\\"):
        _ok("source is the repo (otls/)")
    else:
        _bad(f"source is NOT the repo (override may not be active)")


# ──────────────────────────────────────────────────────────────────────────
# [2] Instantiate orchestrator + verify sub-HDA wiring
# ──────────────────────────────────────────────────────────────────────────
print("\n[2] orchestrator instance + sub-HDA resolution")
obj_ctx = hou.node("/obj")
existing = obj_ctx.node("__verify_v3_obj")
if existing:
    existing.destroy()

instance = None
try:
    instance = obj_ctx.createNode("cinema::camera_rig", "__verify_v3_obj")
    _ok(f"created  type={instance.type().name()}")
except Exception as e:
    _bad(f"createNode failed: {e}")

if instance:
    expected = [
        ("biomechanics/biomech_solver",      "cinema::chops_biomechanics::3.0",
         "biomechanics/__placeholder_biomech"),
        ("post_pipeline/anamorphic_flare",   "cinema::cop_anamorphic_flare::3.0",
         "post_pipeline/flare_placeholder"),
        ("post_pipeline/sensor_noise",       "cinema::cop_sensor_noise::3.0",
         "post_pipeline/noise_placeholder"),
        ("post_pipeline/stmap_aov",          "cinema::cop_stmap_aov::3.0",
         "post_pipeline/stmap_placeholder"),
    ]
    for path, want_type, fallback_path in expected:
        n = instance.node(path)
        if n is None:
            fallback = instance.node(fallback_path)
            if fallback:
                _bad(f"{path} missing -- fallback null at {fallback_path} (sub-HDA not loaded at build time)")
            else:
                _bad(f"{path} missing AND no fallback (orchestrator broken)")
            continue
        got_type = n.type().name()
        if got_type == want_type:
            _ok(f"{path}: {got_type}")
        else:
            _bad(f"{path}: got {got_type}  expected {want_type}")

    # Camera-vs-null Display flag wiring (UX regression guard).
    # The rig should look like a camera in the viewport, not a yellow ring.
    cam_inner = instance.node("cinema_camera")
    if cam_inner is None:
        _bad("instance.node('cinema_camera') missing -- rig has no inner cam")
    elif cam_inner.isGenericFlagSet(hou.nodeFlag.Display):
        _ok("inner cinema_camera has Display flag (frustum visible)")
    else:
        _bad("inner cinema_camera missing Display flag (rig won't look like a camera)")

    pupil_null = instance.node("entrance_pupil_pivot")
    if pupil_null is None:
        _bad("instance.node('entrance_pupil_pivot') missing")
    elif pupil_null.evalParm("display") == 0:
        _ok("entrance_pupil_pivot hidden by default (show_nodal_guide=False)")
    else:
        _bad("entrance_pupil_pivot visible by default (expected hidden)")

    # Top-level Look-Through button + nodal-guide toggle present on the HDA.
    if instance.parm("look_through_camera") is not None:
        _ok("look_through_camera button parm present")
    else:
        _bad("look_through_camera button parm missing")
    if instance.parm("show_nodal_guide") is not None:
        _ok("show_nodal_guide toggle parm present")
    else:
        _bad("show_nodal_guide toggle parm missing")

    # v3.3 artist-friendly parms + v3.4 fluid-head targets / lens apply
    for parm_name, descr in (
        ("camera_preset",            "Preset tab camera dropdown"),
        ("focal_length_preset",      "Lens common-prime menu"),
        ("shutter_angle_deg",        "Lens shutter angle"),
        ("show_advanced_distortion", "Distortion advanced toggle"),
        ("handheld_style",           "Biomech handheld style menu"),
        ("apply_lens",               "Lens tab Apply Lens button"),
        ("lens_status",              "Lens tab status label"),
        ("target_pan_deg",           "Biomech keyframable pan target"),
        ("target_tilt_deg",          "Biomech keyframable tilt target"),
        ("target_roll_deg",          "Biomech keyframable roll target"),
    ):
        if instance.parm(parm_name) is not None:
            _ok(f"artist parm {parm_name} present ({descr})")
        else:
            _bad(f"artist parm {parm_name} MISSING ({descr})")

    # Cook
    try:
        instance.cook(force=True)
        errs = instance.errors()
        if errs:
            _bad(f"cook errors ({len(errs)}): {errs[0][:120]}...")
        else:
            _ok("cook clean")
    except Exception as e:
        _bad(f"cook exception: {e}")


# ──────────────────────────────────────────────────────────────────────────
# [3] LOP rig + USD prim authoring
# ──────────────────────────────────────────────────────────────────────────
print("\n[3] cinema::camera_rig_lop::3.0 LOP type + USD output")
lop_type = hou.nodeType(hou.lopNodeTypeCategory(), "cinema::camera_rig_lop::3.0")
if lop_type is None:
    _bad("LOP type not registered")
else:
    src = lop_type.definition().libraryFilePath() or ""
    _ok(f"LOP type registered  source={src}")

    stage_net = hou.node("/stage")
    if stage_net is None:
        stage_net = hou.node("/obj").createNode("lopnet", "stage")

    existing_lop = stage_net.node("__verify_v3_lop")
    if existing_lop:
        existing_lop.destroy()

    try:
        lop = stage_net.createNode("cinema::camera_rig_lop", "__verify_v3_lop")
        lop.cook(force=True)
        usd = lop.stage()
        if usd is None:
            _bad("no USD stage on cooked LOP")
        else:
            expected_prims = [
                "/CinemaRig",
                "/CinemaRig/FluidHead",
                "/CinemaRig/FluidHead/Body",
                "/CinemaRig/FluidHead/Body/Sensor",
                "/CinemaRig/FluidHead/Body/Sensor/EntrancePupil",
                "/Render/Products/Sensor",
                "/Render/CinemaRigSettings",
            ]
            for p in expected_prims:
                prim = usd.GetPrimAtPath(p)
                if prim and prim.IsValid():
                    _ok(f"prim {p}")
                else:
                    _bad(f"prim missing: {p}")

            # Karma lens shader binding: the attrs Karma actually consumes
            sensor = usd.GetPrimAtPath("/CinemaRig/FluidHead/Body/Sensor")
            if sensor and sensor.IsValid():
                use_attr = sensor.GetAttribute("karma:camera:use_lensshader")
                cmd_attr = sensor.GetAttribute("karma:camera:lensshader")
                if use_attr and use_attr.Get() is True:
                    _ok("karma:camera:use_lensshader = True")
                else:
                    _bad("karma:camera:use_lensshader missing/False")
                cmd = (cmd_attr.Get() or "") if cmd_attr else ""
                if cmd.startswith("opdef:/Vop/cinema_lens_shader?") and "dist_k1" in cmd:
                    _ok(f"karma:camera:lensshader opdef bound ({cmd[:60]}...)")
                else:
                    _bad(f"karma:camera:lensshader malformed: '{cmd[:80]}'")

                # Entrance pupil sign: toward the scene = negative Z
                from pxr import UsdGeom as _UsdGeom
                pupil = usd.GetPrimAtPath(
                    "/CinemaRig/FluidHead/Body/Sensor/EntrancePupil")
                ops = _UsdGeom.Xformable(pupil).GetOrderedXformOps()
                tz = ops[0].Get()[2] if ops else None
                if tz is not None and tz < 0:
                    _ok(f"EntrancePupil z = {tz:.2f}cm (negative: toward scene)")
                else:
                    _bad(f"EntrancePupil z = {tz} (expected negative)")

            # RenderSettings camera bound via RELATIONSHIP (not string attr)
            from pxr import UsdRender as _UsdRender
            settings_prim = usd.GetPrimAtPath("/Render/CinemaRigSettings")
            if settings_prim and settings_prim.IsValid():
                rel_targets = [str(t) for t in
                               _UsdRender.Settings(settings_prim).GetCameraRel().GetTargets()]
                if rel_targets == ["/CinemaRig/FluidHead/Body/Sensor"]:
                    _ok("RenderSettings camera REL -> Sensor")
                else:
                    _bad(f"RenderSettings camera rel targets: {rel_targets}")
    except Exception as e:
        _bad(f"LOP cook exception: {e}")
        traceback.print_exc()


# ──────────────────────────────────────────────────────────────────────────
# [4] Biomechanics LOP wiring: metadata attrs present + shake authors samples
# ──────────────────────────────────────────────────────────────────────────
print("\n[4] biomechanics LOP wiring (Mile 2)")
try:
    stage_net = hou.node("/stage")
    biomech_lop = stage_net.node("__verify_v3_biomech")
    if biomech_lop:
        biomech_lop.destroy()
    biomech_lop = stage_net.createNode("cinema::camera_rig_lop", "__verify_v3_biomech")
    biomech_lop.parm("enable_biomechanics").set(True)
    biomech_lop.parm("enable_handheld").set(True)
    biomech_lop.parm("auto_derive").set(True)
    biomech_lop.cook(force=True)

    usd = biomech_lop.stage()
    head = usd.GetPrimAtPath("/CinemaRig/FluidHead")
    if not head or not head.IsValid():
        _bad("/CinemaRig/FluidHead missing -- biomech can't apply")
    else:
        # Metadata attrs
        for attr_name in (
            "cinema:rig:biomech:enabled",
            "cinema:rig:biomech:springK",
            "cinema:rig:biomech:damping",
            "cinema:rig:biomech:lagFrames",
            "cinema:rig:biomech:handheldEnabled",
        ):
            attr = head.GetAttribute(attr_name)
            if attr and attr.HasValue():
                _ok(f"meta {attr_name} = {attr.Get()}")
            else:
                _bad(f"meta {attr_name} missing")

        # Time samples on rotateXYZ -- handheld is on, so we expect samples
        from pxr import UsdGeom
        head_xf = UsdGeom.Xformable(head)
        rot_op = None
        for op in head_xf.GetOrderedXformOps():
            if op.GetOpName() == "xformOp:rotateXYZ":
                rot_op = op
                break
        if rot_op is None:
            _bad("FluidHead has no xformOp:rotateXYZ op")
        else:
            n_samples = rot_op.GetNumTimeSamples()
            if n_samples >= 2:
                _ok(f"rotateXYZ has {n_samples} time samples (handheld shake authoring)")
            else:
                _bad(f"rotateXYZ has only {n_samples} time samples (expected >=2 with shake on)")
except Exception as e:
    _bad(f"biomech check failed: {e}")
    traceback.print_exc()


# ──────────────────────────────────────────────────────────────────────────
# [5] Lens registry loads a brand-new (post-v3.0) focal length
# ──────────────────────────────────────────────────────────────────────────
print("\n[5] Lens registry: Cooke S35 + Cooke FF+ skeleton")
try:
    from pathlib import Path
    from cinema_camera.registry import get_lens, list_lenses
    _row(INFO, f"registered providers: {list_lenses()}")

    # ── S35 line (PDF-authoritative datasheet 030623) ──
    lens_path = Path(os.environ["CINEMA_CAMERA_REPO"]) / "cinema_camera" / "lenses" / "cooke_ana_i_s35_32mm.json"
    spec = get_lens("cooke_ana_i_s35", lens_path)
    _ok(f"S35 32mm: f={spec.focal_length_mm}mm, T{spec.t_stop_min}-{spec.t_stop_max}, MOD={spec.close_focus_m}m, squeeze={spec.squeeze_ratio}")
    _ok(f"S35 mechanics: w={spec.mechanics.weight_kg}kg, L={spec.mechanics.length_mm}mm, pupil={spec.mechanics.entrance_pupil_offset_mm}mm")
    _ok(f"S35 squeeze: @MOD={spec.effective_squeeze(spec.close_focus_m):.3f} @infinity={spec.effective_squeeze(1e10):.3f}")

    # ── FF+ line (skeleton, datasheet pending; verify it loads cleanly) ──
    ff_plus_path = Path(os.environ["CINEMA_CAMERA_REPO"]) / "cinema_camera" / "lenses" / "cooke_ana_i_ff_plus_50mm.json"
    if ff_plus_path.exists():
        ff_spec = get_lens("cooke_ana_i_ff_plus", ff_plus_path)
        _ok(f"FF+ 50mm: f={ff_spec.focal_length_mm}mm, squeeze={ff_spec.squeeze_ratio} (1.8x for LF/VV bodies)")
        if abs(ff_spec.squeeze_ratio - 1.8) < 0.01:
            _ok("FF+ squeeze ratio is 1.8 (correct for full-frame anamorphic)")
        else:
            _bad(f"FF+ squeeze ratio is {ff_spec.squeeze_ratio} (expected 1.8)")
    else:
        _bad(f"FF+ skeleton JSON missing at {ff_plus_path}")
except Exception as e:
    _bad(f"lens load failed: {e}")
    traceback.print_exc()


# ──────────────────────────────────────────────────────────────────────────
# [6] Copernicus 2.0 satellite HDAs registered (Mile 3)
# ──────────────────────────────────────────────────────────────────────────
print("\n[6] Copernicus 2.0 satellite HDAs (cop category) -- registration")
_cop_cat = None
try:
    _cop_cat = hou.copNodeTypeCategory()
    for op_name in ("cinema::flare::3.0",
                    "cinema::sensor_noise::3.0",
                    "cinema::stmap_aov::3.0"):
        t = hou.nodeType(_cop_cat, op_name)
        if t is None:
            _bad(f"{op_name} not registered in cop category")
        else:
            src = t.definition().libraryFilePath() or ""
            _ok(f"{op_name}  source={os.path.basename(src)}")
except AttributeError as e:
    _bad(f"hou.copNodeTypeCategory() unavailable -- Copernicus may not be enabled: {e}")
except Exception as e:
    _bad(f"cop type check failed: {e}")
    traceback.print_exc()


# ──────────────────────────────────────────────────────────────────────────
# [7] Copernicus 2.0 cook smoke test: instantiate v2 chain and cook
# ──────────────────────────────────────────────────────────────────────────
print("\n[7] Copernicus 2.0 cook smoke test (v2 satellite chain)")
if _cop_cat is None:
    _row(INFO, "skipping -- cop category unavailable")
else:
    obj_ctx = hou.node("/obj")
    existing_cop_test = obj_ctx.node("__verify_v3_cop")
    if existing_cop_test:
        existing_cop_test.destroy()
    cop_test_geo = None
    try:
        # Copernicus 2.0 networks live inside SOP-category contexts in H21.
        # Spin up a host geo, drop a copnet, wire constant -> flare -> noise.
        cop_test_geo = obj_ctx.createNode("geo", "__verify_v3_cop")
        cop_net = cop_test_geo.createNode("copnet", "test_copnet")

        # Source image: constant
        src = cop_net.createNode("constant", "src")

        # Flare v2
        try:
            flare = cop_net.createNode("cinema::flare", "flare")
            flare.setInput(0, src)
            _ok("instantiated cinema::flare::3.0 in copnet")
        except Exception as e:
            _bad(f"cinema::flare::3.0 instantiation failed: {e}")
            flare = src

        # Sensor noise v2 (downstream of flare)
        try:
            noise = cop_net.createNode("cinema::sensor_noise", "noise")
            noise.setInput(0, flare)
            _ok("instantiated cinema::sensor_noise::3.0 in copnet")
        except Exception as e:
            _bad(f"cinema::sensor_noise::3.0 instantiation failed: {e}")
            noise = flare

        # STMap v2 (independent branch, pure generator)
        try:
            stmap = cop_net.createNode("cinema::stmap_aov", "stmap")
            _ok("instantiated cinema::stmap_aov::3.0 in copnet")
        except Exception as e:
            _bad(f"cinema::stmap_aov::3.0 instantiation failed: {e}")
            stmap = None

        # Cook main chain
        try:
            noise.cook(force=True)
            errs = noise.errors()
            if errs:
                _bad(f"v2 chain cook errors ({len(errs)}): {errs[0][:120]}...")
            else:
                _ok("v2 flare -> noise chain cooks clean")
        except Exception as e:
            _bad(f"v2 chain cook exception: {e}")

        # Cook stmap separately
        if stmap is not None:
            try:
                stmap.cook(force=True)
                errs = stmap.errors()
                if errs:
                    _bad(f"v2 stmap cook errors ({len(errs)}): {errs[0][:120]}...")
                else:
                    _ok("v2 stmap cooks clean")
            except Exception as e:
                _bad(f"v2 stmap cook exception: {e}")
    except Exception as e:
        _bad(f"cop cook smoke test setup failed: {e}")
        traceback.print_exc()


# ──────────────────────────────────────────────────────────────────────────
# [8] Wiring / units / parity audit (v3.4)
#     a) ch() expression survival on orchestrator sub-HDA instances
#     b) OBJ object-level parenting chain (the rig actually rigs)
#     c) entrance pupil units (/obj meters)
#     d) lens registry resolve + apply fills parms
#     e) OBJ-vs-LOP biomechanics step-response parity
# ──────────────────────────────────────────────────────────────────────────
print("\n[8] wiring / units / parity audit")

# -- [8a] expression survival ----------------------------------------------
try:
    inst = hou.node("/obj/__verify_v3_obj")
    if inst is None:
        _bad("[8a] orchestrator instance missing (section [2] failed?)")
    else:
        expr_expectations = [
            ("post_pipeline/anamorphic_flare", "threshold",   "flare_threshold"),
            ("post_pipeline/sensor_noise",     "native_iso",  "native_iso"),
            ("post_pipeline/stmap_aov",        "dist_k1",     "dist_k1"),
            ("biomechanics/biomech_solver",    "combined_weight_kg", "combined_weight_kg"),
            ("cinema_camera",                  "focal",       "focal_length_mm"),
            ("cinema_camera",                  "fstop",       "t_stop"),
        ]
        for node_path, parm_name, expected_ref in expr_expectations:
            n = inst.node(node_path)
            p = n.parm(parm_name) if n else None
            if p is None:
                _bad(f"[8a] {node_path}.{parm_name} missing")
                continue
            try:
                expr = p.expression()
            except hou.OperationFailed:
                expr = ""
            if expected_ref in expr:
                _ok(f"[8a] {node_path}.{parm_name} expr carries {expected_ref}")
            else:
                _bad(f"[8a] {node_path}.{parm_name} expr lost: '{expr}'")
except Exception as e:
    _bad(f"[8a] expression audit failed: {e}")
    traceback.print_exc()

# -- [8b] parenting chain + [8c] pupil units -------------------------------
try:
    inst = hou.node("/obj/__verify_v3_obj")
    if inst:
        cam_n = inst.node("cinema_camera")
        pivot_n = inst.node("entrance_pupil_pivot")
        head_n = inst.node("fluid_head_mount")
        if cam_n and pivot_n and head_n:
            cam_in = cam_n.inputs()[0] if cam_n.inputs() else None
            pivot_in = pivot_n.inputs()[0] if pivot_n.inputs() else None
            if cam_in == pivot_n and pivot_in == head_n:
                _ok("[8b] parenting: fluid_head -> pupil_pivot -> cam")
            else:
                _bad(f"[8b] parenting broken: cam<-{cam_in}, pivot<-{pivot_in}")
            tz = cam_n.evalParm("tz")
            if abs(tz - 0.125) < 1e-4:
                _ok(f"[8c] cam tz = {tz:.4f} m for 125mm pupil offset (/1000)")
            else:
                _bad(f"[8c] cam tz = {tz} (expected 0.125 m at default 125mm)")
        else:
            _bad("[8b] rig nodes missing inside orchestrator instance")
except Exception as e:
    _bad(f"[8b/8c] parenting/unit audit failed: {e}")
    traceback.print_exc()

# -- [8d] lens registry resolve + apply ------------------------------------
try:
    from cinema_camera.registry import resolve_lens
    from cinema_camera import hda_callbacks

    spec75 = resolve_lens("cooke_ana_i_s35_75mm")
    if abs(spec75.focal_length_mm - 75.0) < 0.01:
        _ok(f"[8d] resolve_lens: 75mm spec (T{spec75.t_stop_min}, "
            f"pupil={spec75.entrance_pupil_offset_mm}mm)")
    else:
        _bad(f"[8d] resolve_lens returned focal {spec75.focal_length_mm}")

    lop_inst = hou.node("/stage/__verify_v3_lop")
    if lop_inst is None:
        _bad("[8d] LOP instance missing for apply_lens check")
    else:
        lop_inst.parm("lens_id").set("cooke_ana_i_s35_75mm")
        hda_callbacks.apply_lens(lop_inst)
        checks = [
            ("focal_length_mm", spec75.focal_length_mm),
            ("dist_k1", spec75.distortion.k1),
            ("entrance_pupil_offset_mm", spec75.entrance_pupil_offset_mm),
        ]
        for parm_name, want in checks:
            got = lop_inst.evalParm(parm_name)
            if abs(got - want) < 1e-4:
                _ok(f"[8d] apply_lens set {parm_name} = {got:g}")
            else:
                _bad(f"[8d] apply_lens {parm_name} = {got} (want {want})")
        # cook-time effective squeeze follows the 75mm curve, not the parm
        lop_inst.cook(force=True)
        usd75 = lop_inst.stage()
        sq_attr = usd75.GetPrimAtPath("/CinemaRig/FluidHead/Body/Sensor") \
                       .GetAttribute("cinema:rig:effectiveSqueeze")
        sq = sq_attr.Get() if sq_attr else None
        want_sq = spec75.effective_squeeze(lop_inst.evalParm("focus_distance_m"))
        if sq is not None and abs(sq - want_sq) < 1e-3:
            _ok(f"[8d] cook-time effective squeeze = {sq:.4f} (lens curve)")
        else:
            _bad(f"[8d] effective squeeze {sq} != curve value {want_sq}")
except Exception as e:
    _bad(f"[8d] lens resolve/apply audit failed: {e}")
    traceback.print_exc()

# -- [8e] OBJ-vs-LOP biomechanics step-response parity ----------------------
try:
    STEP_DEG = 30.0
    F_START, F_STEP, F_END = 1, 5, 48

    # OBJ side: keyframe target_pan_deg as a step, sample fluid head ry.
    inst = hou.node("/obj/__verify_v3_obj")
    obj_val = None
    if inst and inst.parm("target_pan_deg") is not None:
        pan = inst.parm("target_pan_deg")
        pan.deleteAllKeyframes()
        for f, v in ((F_START, 0.0), (F_STEP - 1, 0.0), (F_STEP, STEP_DEG), (F_END, STEP_DEG)):
            k = hou.Keyframe()
            k.setFrame(f)
            k.setValue(v)
            k.setExpression("linear()", hou.exprLanguage.Hscript)
            pan.setKeyframe(k)
        head_n = inst.node("fluid_head_mount")
        if head_n is not None:
            obj_val = head_n.parm("ry").evalAtFrame(F_END)
            early = head_n.parm("ry").evalAtFrame(F_START)
            if abs(early) < 2.0 and abs(obj_val - STEP_DEG) < 0.25 * STEP_DEG:
                _ok(f"[8e] OBJ chop chain follows step: ry(f{F_END}) = {obj_val:.2f} "
                    f"(target {STEP_DEG})")
            else:
                _bad(f"[8e] OBJ chop response off: ry(f{F_START})={early:.2f}, "
                     f"ry(f{F_END})={obj_val}")
        pan.deleteAllKeyframes()
    else:
        _bad("[8e] target_pan_deg parm missing on orchestrator")

    # LOP side: author a step rotateXYZ input prim upstream, filter it.
    stage_net = hou.node("/stage")
    probe = stage_net.node("__verify_v3_biomech_src")
    if probe:
        probe.destroy()
    probe = stage_net.createNode("pythonscript", "__verify_v3_biomech_src")
    probe.parm("python").set(
        "from pxr import Gf, Usd, UsdGeom\n"
        "stage = hou.pwd().editableStage()\n"
        "xf = UsdGeom.Xform.Define(stage, '/BiomechProbe')\n"
        "op = xf.AddRotateXYZOp()\n"
        "for f in range(%d, %d + 1):\n"
        "    v = %g if f >= %d else 0.0\n"
        "    op.Set(Gf.Vec3f(0.0, v, 0.0), Usd.TimeCode(f))\n"
        % (F_START, F_END, STEP_DEG, F_STEP)
    )
    rig = stage_net.node("__verify_v3_biomech")
    lop_val = None
    if rig is not None:
        rig.setInput(0, probe)
        rig.parm("input_camera_path").set("/BiomechProbe")
        rig.parm("enable_biomechanics").set(True)
        rig.parm("enable_handheld").set(False)
        rig.parm("auto_derive").set(True)
        rig.cook(force=True)
        from pxr import Usd as _Usd, UsdGeom as _UsdGeom2
        usd_b = rig.stage()
        head = usd_b.GetPrimAtPath("/CinemaRig/FluidHead")
        rot_op = None
        for op in _UsdGeom2.Xformable(head).GetOrderedXformOps():
            if op.GetOpName() == "xformOp:rotateXYZ":
                rot_op = op
                break
        if rot_op is not None:
            v_end = rot_op.Get(_Usd.TimeCode(F_END))
            lop_val = float(v_end[1]) if v_end is not None else None
        if lop_val is not None and abs(lop_val - STEP_DEG) < 0.25 * STEP_DEG:
            _ok(f"[8e] LOP solver follows step: ry(f{F_END}) = {lop_val:.2f}")
        else:
            _bad(f"[8e] LOP solver response off: ry(f{F_END}) = {lop_val}")
    else:
        _bad("[8e] /stage/__verify_v3_biomech missing for parity check")

    # Parity: same step, same auto-derive weight -> comparable settling.
    if obj_val is not None and lop_val is not None:
        if abs(obj_val - lop_val) <= 0.15 * STEP_DEG:
            _ok(f"[8e] OBJ/LOP parity: |{obj_val:.2f} - {lop_val:.2f}| "
                f"<= {0.15 * STEP_DEG:.1f}deg")
        else:
            _bad(f"[8e] OBJ/LOP diverge: obj={obj_val:.2f} lop={lop_val:.2f}")
except Exception as e:
    _bad(f"[8e] step-response parity failed: {e}")
    traceback.print_exc()


# ──────────────────────────────────────────────────────────────────────────
# Summary
# ──────────────────────────────────────────────────────────────────────────
print()
print("=" * 64)
print(f"Verification: {_pass_count} pass, {_fail_count} fail")
if _fail_count == 0:
    print("RESULT: v3.0 override fully wired and working")
else:
    print("RESULT: ISSUES FOUND -- see [FAIL] lines above")
print()
print("Test nodes left for inspection (destroy when done):")
print("  /obj/__verify_v3_obj")
print("  /stage/__verify_v3_lop")
print("  /stage/__verify_v3_biomech")
print("  /stage/__verify_v3_biomech_src  (step-input probe for [8e])")
print("  /obj/__verify_v3_cop  (Copernicus 2.0 smoke test geo)")
print("=" * 64)
