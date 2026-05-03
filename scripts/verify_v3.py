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
                "/CinemaRig/FluidHead/Body/Sensor/CinemaLensShader",
                "/Render/Products/Sensor",
                "/Render/CinemaRigSettings",
            ]
            for p in expected_prims:
                prim = usd.GetPrimAtPath(p)
                if prim and prim.IsValid():
                    _ok(f"prim {p}")
                else:
                    _bad(f"prim missing: {p}")
    except Exception as e:
        _bad(f"LOP cook exception: {e}")
        traceback.print_exc()


# ──────────────────────────────────────────────────────────────────────────
# [5] Biomechanics LOP wiring: metadata attrs present + shake authors samples
# ──────────────────────────────────────────────────────────────────────────
print("\n[5] biomechanics LOP wiring (Mile 2)")
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
# [4] Lens registry loads a brand-new (post-v3.0) focal length
# ──────────────────────────────────────────────────────────────────────────
print("\n[4] Lens registry: brand-new 32mm Cooke (didn't exist pre-v3.0)")
try:
    from pathlib import Path
    from cinema_camera.registry import get_lens, list_lenses
    _row(INFO, f"registered providers: {list_lenses()}")
    lens_path = Path(os.environ["CINEMA_CAMERA_REPO"]) / "cinema_camera" / "lenses" / "cooke_ana_i_s35_32mm.json"
    spec = get_lens("cooke_ana_i_s35", lens_path)
    _ok(f"loaded {spec.lens_id}: f={spec.focal_length_mm}mm, T{spec.t_stop_min}-{spec.t_stop_max}, MOD={spec.close_focus_m}m")
    _ok(f"mechanics: w={spec.mechanics.weight_kg}kg, L={spec.mechanics.length_mm}mm, "
        f"pupil={spec.mechanics.entrance_pupil_offset_mm}mm")
    _ok(f"squeeze: @MOD={spec.effective_squeeze(spec.close_focus_m):.3f} "
        f"@infinity={spec.effective_squeeze(1e10):.3f}")
except Exception as e:
    _bad(f"lens load failed: {e}")
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
print("=" * 64)
