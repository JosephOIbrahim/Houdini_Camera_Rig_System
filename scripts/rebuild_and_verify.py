"""
Cinema Camera Rig v3.0 -- single-paste rebuild + verify driver.

Paste this whole file into Houdini's Python shell, OR:

    exec(open(r"C:\\Users\\User\\Houdini_Camera_Rig_System\\scripts\\rebuild_and_verify.py").read())

Steps:
  Mile 0:   Bootstrap environment (CINEMA_CAMERA_REPO + CINEMA_CAMERA_PATH +
            sys.path) if not already set by packages/cinema_camera_rig.json.
  Mile 0.5: (Optional) Run probe_copernicus.py diagnostic. Set RUN_PROBE = True
            below to enable -- useful on a fresh machine to confirm which COP
            node types Houdini exposes before building the v2 satellites.
  Mile 1:   Build all 9 HDAs via build_all_v3()
            (legacy cop2 + Copernicus 2.0 preview + LOP + OBJ orchestrators).
  Mile 2:   Reload HDA files in the live session so the latest definitions
            are picked up by any already-loaded instances.
  Mile 3:   Run verify_v3.py (7 sections: registration, instance, LOP USD,
            biomech, lens registry, cop registration, cop cook smoke test).
  Mile 4:   Final tally and pointers to scratch nodes left for inspection.

Idempotent: re-running this overwrites the .hda files and reinstalls them.
Side effects: leaves /obj/__verify_v3_obj, /stage/__verify_v3_lop,
/stage/__verify_v3_biomech, /obj/__verify_v3_cop in the scene for inspection
(destroy them manually when done).
"""

import os
import sys
import traceback

import hou


# ──────────────────────────────────────────────────────────────────────
# Config -- tweak before pasting if your repo lives elsewhere
# ──────────────────────────────────────────────────────────────────────
_REPO_PATH = r"C:\Users\User\Houdini_Camera_Rig_System"
RUN_PROBE  = False   # True = run Copernicus probe diagnostic at Mile 0.5


def _banner(title: str) -> None:
    bar = "=" * 64
    print(f"\n{bar}\n{title}\n{bar}")


# ──────────────────────────────────────────────────────────────────────
# Mile 0: Bootstrap environment
# ──────────────────────────────────────────────────────────────────────
_banner("Mile 0 / 4: Bootstrapping environment")

if not os.environ.get("CINEMA_CAMERA_REPO"):
    os.environ["CINEMA_CAMERA_REPO"] = _REPO_PATH
    print(f"  CINEMA_CAMERA_REPO  -> {_REPO_PATH}  (set now)")
else:
    print(f"  CINEMA_CAMERA_REPO  = {os.environ['CINEMA_CAMERA_REPO']}  (already set)")

_repo = os.environ["CINEMA_CAMERA_REPO"]

if not os.path.isdir(_repo):
    raise RuntimeError(
        f"CINEMA_CAMERA_REPO path does not exist: {_repo}\n"
        "Edit _REPO_PATH at the top of this script before pasting."
    )

if not os.environ.get("CINEMA_CAMERA_PATH"):
    os.environ["CINEMA_CAMERA_PATH"] = os.path.join(_repo, "cinema_camera")
    print(f"  CINEMA_CAMERA_PATH  -> {os.environ['CINEMA_CAMERA_PATH']}  (set now)")
else:
    print(f"  CINEMA_CAMERA_PATH  = {os.environ['CINEMA_CAMERA_PATH']}  (already set)")

_scripts_python = os.path.join(_repo, "scripts", "python")
if _scripts_python not in sys.path:
    sys.path.insert(0, _scripts_python)
    print(f"  sys.path  += {_scripts_python}")
else:
    print(f"  sys.path  already contains {_scripts_python}")


# ──────────────────────────────────────────────────────────────────────
# Mile 0.5: Optional Copernicus probe diagnostic
# ──────────────────────────────────────────────────────────────────────
if RUN_PROBE:
    _banner("Mile 0.5 / 4: probe_copernicus diagnostic (optional)")
    _probe_path = os.path.join(_repo, "scripts", "probe_copernicus.py")
    try:
        with open(_probe_path, "r", encoding="utf-8") as _fh:
            _probe_code = _fh.read()
        exec(_probe_code, {"__name__": "__probe__"})
    except Exception as e:
        print(f"  [WARN] probe failed (non-fatal): {e}")
        traceback.print_exc()


# ──────────────────────────────────────────────────────────────────────
# Mile 1: Build all 9 HDAs
# ──────────────────────────────────────────────────────────────────────
_banner("Mile 1 / 4: Building all 9 HDAs via build_all_v3()")

_build_results = {}
try:
    # Force-reimport so any builder source edits since last session are picked up.
    for _mod in list(sys.modules.keys()):
        if _mod.startswith("cinema_camera"):
            del sys.modules[_mod]
    from cinema_camera.builders.build_all import build_all_v3
    _build_results = build_all_v3(force_reimport=True)
except Exception as e:
    print(f"  [FATAL] build_all_v3 raised: {e}")
    traceback.print_exc()
    _build_results = {}


# ──────────────────────────────────────────────────────────────────────
# Mile 2: Reload HDA files in live session
# ──────────────────────────────────────────────────────────────────────
_banner("Mile 2 / 4: Reloading HDA files in live session")

try:
    hou.hda.reloadAllFiles()
    print("  hou.hda.reloadAllFiles()  OK")
except Exception as e:
    print(f"  [WARN] reloadAllFiles failed (non-fatal): {e}")
    traceback.print_exc()


# ──────────────────────────────────────────────────────────────────────
# Mile 3: Run verify_v3 end-to-end checks
# ──────────────────────────────────────────────────────────────────────
_banner("Mile 3 / 4: Running verify_v3 end-to-end checks")

_verify_pass, _verify_fail = 0, -1
try:
    _verify_path = os.path.join(_repo, "scripts", "verify_v3.py")
    with open(_verify_path, "r", encoding="utf-8") as _fh:
        _verify_code = _fh.read()
    # exec into a private namespace so verify globals don't pollute shell scope.
    _verify_ns = {"__name__": "__verify__"}
    exec(_verify_code, _verify_ns)
    _verify_pass = _verify_ns.get("_pass_count", 0)
    _verify_fail = _verify_ns.get("_fail_count", 0)
except Exception as e:
    print(f"  [FATAL] verify_v3 raised: {e}")
    traceback.print_exc()


# ──────────────────────────────────────────────────────────────────────
# Mile 4: Final tally
# ──────────────────────────────────────────────────────────────────────
_banner("Mile 4 / 4: Final tally")

_build_failures = [
    k for k, v in _build_results.items()
    if isinstance(v, str) and v.startswith("ERROR:")
]
_build_ok = len(_build_results) - len(_build_failures)

print(f"  Build:  {_build_ok}/{len(_build_results)} HDAs OK")
for _op in _build_failures:
    print(f"    FAIL: {_op}  -> {_build_results[_op]}")

print(f"  Verify: {_verify_pass} pass, {_verify_fail} fail")
print()

if not _build_failures and _verify_fail == 0 and _build_ok > 0:
    print("  RESULT: SHIP IT -- all HDAs built and verified clean.")
elif _verify_fail < 0:
    print("  RESULT: VERIFY DID NOT RUN -- see traceback above.")
else:
    print("  RESULT: ISSUES FOUND -- see logs above.")

print()
print("  Scratch nodes left for inspection (destroy when done):")
print("    /obj/__verify_v3_obj         -- orchestrator instance")
print("    /stage/__verify_v3_lop       -- LOP rig instance")
print("    /stage/__verify_v3_biomech   -- biomechanics LOP instance")
print("    /obj/__verify_v3_cop         -- Copernicus 2.0 cop smoke test")
print("=" * 64)
