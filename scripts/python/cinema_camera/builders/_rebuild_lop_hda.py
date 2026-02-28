"""
Rebuild Cinema Camera Rig LOP HDA via Synapse bridge.

Usage (from any shell):
    python _rebuild_lop_hda.py

Connects to running Houdini via ws://localhost:9999/synapse,
builds the LOP HDA, installs it, and runs verification.
"""

import asyncio
import json
import sys
import os

# Add synapse agent to path
sys.path.insert(0, os.path.expanduser("~/.synapse/agent"))

from synapse_ws import SynapseClient, SynapseConnectionError, SynapseExecutionError


# ── Step 1: Preflight + Build ─────────────────────────────

BUILD_CODE = r"""
import os, sys, traceback

# Ensure cinema_camera package is importable
scripts_path = r"C:\Users\User\OneDrive\Documents\houdini21.0\scripts\python"
if scripts_path not in sys.path:
    sys.path.insert(0, scripts_path)

# Set CINEMA_CAMERA_PATH if not already set
if "CINEMA_CAMERA_PATH" not in os.environ:
    os.environ["CINEMA_CAMERA_PATH"] = r"C:\Users\User\OneDrive\Documents\houdini21.0\scripts\python\cinema_camera"

cinema_path = os.environ["CINEMA_CAMERA_PATH"]
hda_dir = os.path.join(cinema_path, "hda")
os.makedirs(hda_dir, exist_ok=True)

# Force reimport to pick up latest code
for mod_name in list(sys.modules.keys()):
    if mod_name.startswith("cinema_camera"):
        del sys.modules[mod_name]

# Build
from cinema_camera.builders.build_camera_rig_lop import build_camera_rig_lop_hda

hda_path = build_camera_rig_lop_hda(save_dir=hda_dir)

# Install
import hou
hou.hda.installFile(hda_path)

import json as _json

# Debug: check HDA internals before returning
debug_node = None
for n in hou.node("/stage").children():
    if n.type().name() == "cinema::camera_rig_lop":
        debug_node = n
        break

debug_info = {}
if debug_node:
    debug_info["children_after_build"] = [c.name() for c in debug_node.children()]
    debug_info["node_type"] = debug_node.type().name()

result = _json.dumps({"status": "built", "hda_path": hda_path, "debug": debug_info})
"""


# ── Step 1b: Diagnose HDA internal structure ──────────────

DIAG_CODE = r"""
import hou, json

stage_net = hou.node("/stage")
if stage_net is None:
    stage_net = hou.node("/obj").createNode("lopnet", "stage")

old = stage_net.node("__diag_cinema_rig_lop")
if old:
    old.destroy()

# Try creating the node
diag_node = None
create_names = ["cinema::camera_rig_lop::1.0", "cinema::camera_rig_lop"]
for n in create_names:
    try:
        diag_node = stage_net.createNode(n, "__diag_cinema_rig_lop")
        break
    except Exception:
        pass

info = {"node_created": diag_node is not None}

if diag_node:
    info["node_type"] = diag_node.type().name()
    info["node_category"] = diag_node.type().category().name()

    # List children
    children = []
    for child in diag_node.children():
        child_info = {
            "name": child.name(),
            "type": child.type().name(),
        }
        # Check Python Script LOP parm names
        parm_names_list = [p.name() for p in child.parms()]
        child_info["parms"] = parm_names_list[:20]  # first 20

        # Check if pythonscript node has script content
        for pname in ["python", "pythoncode", "script"]:
            p = child.parm(pname)
            if p:
                val = p.eval()
                child_info[f"parm_{pname}_len"] = len(val) if val else 0
                child_info[f"parm_{pname}_first50"] = val[:50] if val else ""

        # Check cook errors
        try:
            child.cook(force=True)
            child_info["cook_ok"] = True
        except Exception as e:
            child_info["cook_ok"] = False
            child_info["cook_error"] = str(e)[:200]

        children.append(child_info)

    info["children"] = children

    # Now cook the whole HDA and check stage
    try:
        diag_node.cook(force=True)
        lop_stage = diag_node.stage()
        if lop_stage:
            prims = []
            for prim in lop_stage.Traverse():
                prims.append(str(prim.GetPath()))
            info["stage_prims"] = prims[:30]
        else:
            info["stage_prims"] = "NO_STAGE"
    except Exception as e:
        info["cook_error"] = str(e)[:300]

    # Check HDA-level parms
    hda_parms = [p.name() for p in diag_node.parms()]
    info["hda_parm_count"] = len(hda_parms)
    info["hda_parms_sample"] = hda_parms[:15]

    diag_node.destroy()

result = json.dumps(info)
"""

# ── Step 2: Verify USD hierarchy ──────────────────────────

VERIFY_CODE = r"""
import hou, os, sys

scripts_path = r"C:\Users\User\OneDrive\Documents\houdini21.0\scripts\python"
if scripts_path not in sys.path:
    sys.path.insert(0, scripts_path)

errors = []
warnings = []

# 1. Check HDA is installed -- try multiple lookup patterns
hda_type = None
lookup_names = [
    "cinema::camera_rig_lop::1.0",
    "cinema::camera_rig_lop",
    "camera_rig_lop",
]
for lookup_name in lookup_names:
    try:
        hda_type = hou.nodeType(hou.lopNodeTypeCategory(), lookup_name)
        if hda_type is not None:
            break
    except Exception:
        pass
# Also try listing installed HDAs for debugging
installed_cinema = []
try:
    for hda_file in hou.hda.loadedFiles():
        if "cinema" in hda_file.lower():
            installed_cinema.append(hda_file)
            for defn in hou.hda.definitionsInFile(hda_file):
                installed_cinema.append(f"  -> {defn.nodeTypeName()} (category: {defn.nodeTypeCategory().name()})")
except Exception:
    pass

# 2. Create test instance in /stage
stage_net = hou.node("/stage")
if stage_net is None:
    stage_net = hou.node("/obj").createNode("lopnet", "stage")

# Clean any previous test instance
old_test = stage_net.node("__test_cinema_rig_lop")
if old_test:
    old_test.destroy()

# Try multiple node type names (Houdini version-dependent)
test_node = None
create_names = [
    "cinema::camera_rig_lop::1.0",
    "cinema::camera_rig_lop",
]
for create_name in create_names:
    try:
        test_node = stage_net.createNode(create_name, "__test_cinema_rig_lop")
        test_node.moveToGoodPosition()
        break
    except Exception:
        pass

if test_node is None:
    # Debug: list all installed cinema HDA types
    all_lop_types = []
    try:
        for nt in hou.lopNodeTypeCategory().nodeTypes().values():
            name = nt.name()
            if "cinema" in name.lower():
                all_lop_types.append(name)
    except Exception:
        pass
    errors.append(
        f"Failed to create LOP HDA instance with any name. "
        f"Tried: {create_names}. "
        f"Cinema LOP types found: {all_lop_types}. "
        f"Installed cinema HDA files: {installed_cinema}"
    )

if test_node and not errors:
    # 3. Force cook to generate USD
    try:
        test_node.cook(force=True)
    except Exception as e:
        errors.append(f"Cook failed: {e}")

    # 4. Check USD hierarchy
    try:
        lop_stage = test_node.stage()
        if lop_stage is None:
            errors.append("No USD stage on cooked node")
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
            found_prims = []
            missing_prims = []
            for prim_path in expected_prims:
                prim = lop_stage.GetPrimAtPath(prim_path)
                if prim and prim.IsValid():
                    found_prims.append(prim_path)
                else:
                    missing_prims.append(prim_path)

            # 5. Check camera attributes
            camera_attrs = {}
            sensor_prim = lop_stage.GetPrimAtPath("/CinemaRig/FluidHead/Body/Sensor")
            if sensor_prim and sensor_prim.IsValid():
                for attr_name in [
                    "horizontalAperture", "verticalAperture", "focalLength",
                    "focusDistance", "fStop", "clippingRange",
                    "cinema:rig:entrancePupilOffsetCm",
                    "cinema:rig:effectiveSqueeze",
                    "cinema:optics:hfovDeg",
                    "cinema:lens:focalLengthMm",
                    "karma:lens:shader",
                ]:
                    attr = sensor_prim.GetAttribute(attr_name)
                    if attr and attr.HasValue():
                        val = attr.Get()
                        camera_attrs[attr_name] = str(val)
                    else:
                        warnings.append(f"Missing camera attr: {attr_name}")

            # 6. Check shader inputs
            shader_attrs = {}
            shader_prim = lop_stage.GetPrimAtPath("/CinemaRig/FluidHead/Body/Sensor/CinemaLensShader")
            if shader_prim and shader_prim.IsValid():
                for attr_name in [
                    "info:id",
                    "inputs:focal_length_mm",
                    "inputs:effective_squeeze",
                    "inputs:dist_k1",
                ]:
                    attr = shader_prim.GetAttribute(attr_name)
                    if attr and attr.HasValue():
                        shader_attrs[attr_name] = str(attr.Get())

            # 7. Check render product metadata
            product_attrs = {}
            product_prim = lop_stage.GetPrimAtPath("/Render/Products/Sensor")
            if product_prim and product_prim.IsValid():
                for attr_name in [
                    "driver:parameters:OpenEXR:lens:focalLengthMm",
                    "driver:parameters:OpenEXR:lens:tStop",
                    "driver:parameters:OpenEXR:camera:sensorWidthMm",
                ]:
                    attr = product_prim.GetAttribute(attr_name)
                    if attr and attr.HasValue():
                        product_attrs[attr_name] = str(attr.Get())

            # 8. Check parameter interface
            parm_names = [p.name() for p in test_node.parms()] if test_node else []
            expected_parms = [
                "focal_length_mm", "t_stop", "focus_distance_m",
                "squeeze_ratio", "effective_squeeze", "entrance_pupil_offset_mm",
                "sensor_width_mm", "sensor_height_mm", "resolution_x", "resolution_y",
                "dist_k1", "dist_k2", "dist_k3",
                "enable_biomechanics", "combined_weight_kg",
                "enable_flare", "flare_threshold",
                "write_cooke_i", "usd_camera_path",
            ]
            missing_parms = [p for p in expected_parms if p not in parm_names]

    except Exception as e:
        import traceback
        errors.append(f"Verification error: {e}\n{traceback.format_exc()}")

    # Clean up test node
    test_node.destroy()

import json as _json
result = _json.dumps({
    "status": "pass" if not errors else "fail",
    "errors": errors,
    "warnings": warnings,
    "found_prims": found_prims if 'found_prims' in dir() else [],
    "missing_prims": missing_prims if 'missing_prims' in dir() else [],
    "camera_attrs": camera_attrs if 'camera_attrs' in dir() else {},
    "shader_attrs": shader_attrs if 'shader_attrs' in dir() else {},
    "product_attrs": product_attrs if 'product_attrs' in dir() else {},
    "missing_parms": missing_parms if 'missing_parms' in dir() else [],
})
"""


async def main():
    print("=" * 60)
    print("Cinema Camera Rig LOP — Synapse Rebuild & Test")
    print("=" * 60)

    try:
        async with SynapseClient() as client:
            # Ping
            print("\n[1/3] Pinging Synapse...", flush=True)
            ping = await client.ping()
            print(f"  Connected: {ping}")

            # Build
            print("\n[2/3] Building cinema::camera_rig_lop::1.0...", flush=True)
            build_result = await client.execute_python(BUILD_CODE, timeout=60.0)
            if isinstance(build_result, str):
                build_result = json.loads(build_result)
            print(f"  Build result: {json.dumps(build_result, indent=2)}")

            # Diagnose internal structure
            print("\n[2b/3] Diagnosing HDA internal structure...", flush=True)
            diag_result = await client.execute_python(DIAG_CODE, timeout=30.0)
            if isinstance(diag_result, str):
                diag_result = json.loads(diag_result)
            print(f"  Diagnostics: {json.dumps(diag_result, indent=2)}")

            # Verify
            print("\n[3/3] Verifying USD hierarchy...", flush=True)
            verify_result = await client.execute_python(VERIFY_CODE, timeout=30.0)
            if isinstance(verify_result, str):
                vr = json.loads(verify_result)
            elif isinstance(verify_result, dict):
                vr = verify_result
            else:
                vr = {}

            print(f"\n  Status: {vr.get('status', 'unknown')}")

            if vr.get("found_prims"):
                print(f"\n  Found prims ({len(vr['found_prims'])}):")
                for p in vr["found_prims"]:
                    print(f"    [OK] {p}")

            if vr.get("missing_prims"):
                print(f"\n  Missing prims ({len(vr['missing_prims'])}):")
                for p in vr["missing_prims"]:
                    print(f"    [MISSING] {p}")

            if vr.get("camera_attrs"):
                print(f"\n  Camera attributes:")
                for k, v in vr["camera_attrs"].items():
                    print(f"    {k} = {v}")

            if vr.get("shader_attrs"):
                print(f"\n  Shader attributes:")
                for k, v in vr["shader_attrs"].items():
                    print(f"    {k} = {v}")

            if vr.get("product_attrs"):
                print(f"\n  RenderProduct metadata:")
                for k, v in vr["product_attrs"].items():
                    print(f"    {k} = {v}")

            if vr.get("missing_parms"):
                print(f"\n  Missing HDA parms: {vr['missing_parms']}")

            if vr.get("warnings"):
                print(f"\n  Warnings:")
                for w in vr["warnings"]:
                    print(f"    [WARN] {w}")

            if vr.get("errors"):
                print(f"\n  ERRORS:")
                for e in vr["errors"]:
                    print(f"    [ERROR] {e}")

            # Summary
            print("\n" + "=" * 60)
            if vr.get("status") == "pass":
                print("RESULT: ALL CHECKS PASSED")
            else:
                print("RESULT: ISSUES FOUND — see above")
            print("=" * 60)

    except SynapseConnectionError as e:
        print(f"\n[ERROR] Cannot connect to Synapse: {e}")
        print("Make sure Houdini is running with the Synapse server active.")
        return 1
    except SynapseExecutionError as e:
        print(f"\n[ERROR] Execution failed: {e}")
        if e.partial_result:
            print(f"  Partial result: {e.partial_result}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
