"""
Rebuild ALL Cinema Camera Rig HDAs (v3.0) via Synapse bridge.

Usage (from any shell, with Houdini running):
    python _rebuild_all_hdas.py

Build order (legacy satellites consumed by the orchestrator first; Copernicus
2.0 preview satellites are independent and ordered before orchestrators only
so a single full-rebuild loop is reproducible):
    1. cinema::chops_biomechanics::3.0          (CHOPs, consumed by orchestrator)
    2. cinema::cop_anamorphic_flare::3.0        (cop2, consumed by orchestrator)
    3. cinema::cop_sensor_noise::3.0            (cop2, consumed by orchestrator)
    4. cinema::cop_stmap_aov::3.0               (cop2, consumed by orchestrator)
    5. cinema::flare::3.0                       (cop preview, INDEPENDENT)
    6. cinema::sensor_noise::3.0                (cop preview, INDEPENDENT)
    7. cinema::stmap_aov::3.0                   (cop preview, INDEPENDENT)
    8. cinema::camera_rig_lop::3.0              (LOP-context Solaris-native rig)
    9. cinema::camera_rig::3.0                  (OBJ orchestrator, wires 1-4)

All HDAs land in $CINEMA_CAMERA_REPO/otls/ and are auto-installed in the
running Houdini session.
"""

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.expanduser("~/.synapse/agent"))
from synapse_ws import SynapseClient, SynapseConnectionError, SynapseExecutionError


# ── Build code template ───────────────────────────────────────────────────

_BUILD_TEMPLATE = r'''
import os, sys, traceback, json as _json

# Path setup -- prefer CINEMA_CAMERA_REPO, fall back to legacy OneDrive layout.
repo = os.environ.get("CINEMA_CAMERA_REPO")
legacy = r"C:\Users\User\OneDrive\Documents\houdini21.0"

if repo:
    scripts_path = os.path.join(repo, "scripts", "python")
else:
    scripts_path = os.path.join(legacy, "scripts", "python")

if scripts_path not in sys.path:
    sys.path.insert(0, scripts_path)

if "CINEMA_CAMERA_PATH" not in os.environ:
    os.environ["CINEMA_CAMERA_PATH"] = (
        os.path.join(repo, "cinema_camera") if repo
        else os.path.join(legacy, "cinema_camera")
    )

# Force reimport so latest builder code is picked up
for mod_name in list(sys.modules.keys()):
    if mod_name.startswith("cinema_camera"):
        del sys.modules[mod_name]

try:
    from cinema_camera.builders.{module} import {func}
    hda_path = {func}()
    import hou
    hou.hda.installFile(hda_path)
    result = _json.dumps({{"status": "built", "hda_path": hda_path, "op": "{op_name}"}})
except Exception as e:
    result = _json.dumps({{"status": "error", "op": "{op_name}",
                            "error": str(e), "traceback": traceback.format_exc()}})
'''


# Build sequence: (module, function, operator-name-for-log)
_BUILD_PLAN = [
    # Legacy cop2 satellites -- full-featured, consumed by the orchestrator
    ("build_chops_biomechanics",     "build_chops_biomechanics_hda",     "cinema::chops_biomechanics::3.0"),
    ("build_cop_anamorphic_flare",   "build_cop_anamorphic_flare_hda",   "cinema::cop_anamorphic_flare::3.0"),
    ("build_cop_sensor_noise",       "build_cop_sensor_noise_hda",       "cinema::cop_sensor_noise::3.0"),
    ("build_cop_stmap_aov",          "build_cop_stmap_aov_hda",          "cinema::cop_stmap_aov::3.0"),
    # Copernicus 2.0 preview satellites -- independent of orchestrator (MVP)
    ("build_cop_flare_v2",           "build_cop_flare_v2_hda",           "cinema::flare::3.0"),
    ("build_cop_sensor_noise_v2",    "build_cop_sensor_noise_v2_hda",    "cinema::sensor_noise::3.0"),
    ("build_cop_stmap_aov_v2",       "build_cop_stmap_aov_v2_hda",       "cinema::stmap_aov::3.0"),
    # Orchestrator HDAs (consume the legacy cop2 satellites above)
    ("build_camera_rig_lop",         "build_camera_rig_lop_hda",         "cinema::camera_rig_lop::3.0"),
    ("build_camera_rig_orchestrator","build_camera_rig_orchestrator_hda","cinema::camera_rig::3.0"),
]


async def main() -> int:
    print("=" * 64)
    print("Cinema Camera Rig v3.0 -- full HDA rebuild via Synapse")
    print("=" * 64)

    try:
        async with SynapseClient() as client:
            print(f"\n=== Mile 0 of {len(_BUILD_PLAN)}: pinging Synapse ===")
            ping = await client.ping()
            print(f"  connected: {ping}")

            failures = []
            for i, (module, func, op_name) in enumerate(_BUILD_PLAN, start=1):
                print(f"\n=== Mile {i} of {len(_BUILD_PLAN)}: building {op_name} ===")
                code = _BUILD_TEMPLATE.format(module=module, func=func, op_name=op_name)
                try:
                    raw = await client.execute_python(code, timeout=120.0)
                    res = json.loads(raw) if isinstance(raw, str) else raw
                    if res.get("status") == "built":
                        print(f"  OK    -> {res['hda_path']}")
                    else:
                        print(f"  FAIL  {res.get('error')}")
                        if res.get("traceback"):
                            print("  --- traceback ---")
                            print(res["traceback"])
                        failures.append(op_name)
                except SynapseExecutionError as e:
                    print(f"  EXEC FAIL: {e}")
                    failures.append(op_name)

            print("\n" + "=" * 64)
            if failures:
                print(f"RESULT: {len(failures)}/{len(_BUILD_PLAN)} failed:")
                for f in failures:
                    print(f"  - {f}")
                return 1
            print(f"RESULT: all {len(_BUILD_PLAN)} HDAs built and installed")
            print("Restart Houdini or run hou.hda.reloadAllFiles() to refresh tab menu.")
            print("=" * 64)
            return 0

    except SynapseConnectionError as e:
        print(f"\n[ERROR] Cannot connect to Synapse: {e}")
        print("Make sure Houdini is running with the Synapse server active on port 9999.")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
