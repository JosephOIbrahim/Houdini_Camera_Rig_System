"""
Bootstrap + build all v3.0 HDAs from inside Houdini's Python shell.

Use when the local ~/houdini21.0/scripts/python/cinema_camera/ install
shadows the repo and you need to force-load the repo version, then build.

One-line paste:

    exec(open(r"C:\\Users\\User\\Houdini_Camera_Rig_System\\scripts\\bootstrap_v3_build.py").read())

What it does:
  1. Force <repo>/scripts/python/ to position 0 in sys.path
  2. Wipe sys.modules of all cinema_camera.* entries (drop stale cache)
  3. Set CINEMA_CAMERA_REPO env var
  4. Import cinema_camera from the repo (verify file path)
  5. Call build_all_v3() -- builds all 10 HDAs and installs them

Non-destructive: does not touch the local install on disk. Re-runnable.
"""

import os
import sys

REPO = r"C:\Users\User\Houdini_Camera_Rig_System"
REPO_PY = os.path.join(REPO, "scripts", "python")

# 1. Force repo to FRONT of sys.path (remove duplicates first, then insert at 0)
sys.path = [p for p in sys.path if os.path.normpath(p) != os.path.normpath(REPO_PY)]
sys.path.insert(0, REPO_PY)

# 2. Wipe stale cinema_camera modules so re-import walks sys.path again
_dropped = [m for m in list(sys.modules) if m.startswith("cinema_camera")]
for m in _dropped:
    del sys.modules[m]
if _dropped:
    print(f"[bootstrap] dropped {len(_dropped)} stale cinema_camera modules from cache")

# 3. Ensure env var is set
os.environ["CINEMA_CAMERA_REPO"] = REPO
os.environ.setdefault("CINEMA_CAMERA_PATH", os.path.join(REPO, "cinema_camera"))

# 4. Verify the import resolves to the repo
import cinema_camera
loaded_from = os.path.normpath(cinema_camera.__file__)
expected    = os.path.normpath(os.path.join(REPO_PY, "cinema_camera", "__init__.py"))
print(f"[bootstrap] cinema_camera loading from: {loaded_from}")
if loaded_from != expected:
    raise RuntimeError(
        f"Expected import from {expected}\n"
        f"        got import from {loaded_from}\n"
        "sys.path[0:5] = " + repr(sys.path[:5])
    )
print("[bootstrap] OK -- repo install active")
print()

# 5. Purge any previously-installed v3.0 HDA files (defensive: a prior broken
#    build may have registered unversioned types we want to drop). Idempotent.
import hou
_otls = os.path.join(REPO, "otls")
_purged = 0
if os.path.isdir(_otls):
    for _f in sorted(os.listdir(_otls)):
        if _f.endswith("_3.0.hda"):
            _path = os.path.join(_otls, _f)
            try:
                hou.hda.uninstallFile(_path)
                _purged += 1
                print(f"[bootstrap] uninstalled {_f}")
            except hou.OperationFailed:
                pass  # was not installed -- fine
if _purged:
    print(f"[bootstrap] purged {_purged} prior v3.0 HDA registrations")
print()

# 6. Build all 6 v3.0 HDAs (rebuilds files on disk + reinstalls in session)
from cinema_camera.builders.build_all import build_all_v3
build_all_v3()
