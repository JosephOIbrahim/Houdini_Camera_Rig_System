"""
Cinema Camera Rig v4.0 -- Synapse Preflight Check

Verifies a live Houdini session is ready for HDA construction.
Runs through the Synapse bridge before any builder executes.
"""

from __future__ import annotations


def synapse_preflight() -> dict:
    """
    Verify live Houdini session is ready for HDA construction.
    Returns dict of verified conditions. Raises on failure.
    """
    import os

    import hou

    result = {}

    # 1. Houdini version
    major, minor, patch = hou.applicationVersion()
    assert major >= 21, f"Requires Houdini 21+, got {major}.{minor}.{patch}"
    result["houdini_version"] = f"{major}.{minor}.{patch}"

    # 2. Cinema camera path
    cinema_path = os.environ.get("CINEMA_CAMERA_PATH")
    assert cinema_path, "CINEMA_CAMERA_PATH not set in session environment"
    assert os.path.isdir(cinema_path), (
        f"CINEMA_CAMERA_PATH does not exist: {cinema_path}"
    )
    result["cinema_camera_path"] = cinema_path

    # 3. VEX include path -- libcinema_optics.h must be findable
    vex_dir = os.path.join(cinema_path, "vex")
    houdini_path = os.environ.get("HOUDINI_PATH", "")
    if cinema_path not in houdini_path:
        os.environ["HOUDINI_PATH"] = f"{cinema_path};{houdini_path}"
        hou.hscript(f'setenv HOUDINI_PATH = "{cinema_path};{houdini_path}"')
    result["vex_include_path"] = vex_dir

    # 4. HDA output directories exist
    for subdir in ("hda/chops", "hda/post"):
        full = os.path.join(cinema_path, subdir)
        os.makedirs(full, exist_ok=True)
    result["hda_dirs_ready"] = True

    # 5. Copernicus available
    try:
        hou.nodeType(hou.copNodeTypeCategory(), "vopcop2gen")
        result["copernicus_available"] = True
    except Exception:
        result["copernicus_available"] = False

    return result


def synapse_build_with_retry(builder_fn, max_retries=3, **kwargs):
    """
    Wraps each builder call with retry logic.
    Executed through Synapse bridge.
    """
    import os
    import traceback

    import hou

    for attempt in range(max_retries):
        try:
            hda_path = builder_fn(**kwargs)
            if not os.path.exists(hda_path):
                raise FileNotFoundError(
                    f"Builder returned but file missing: {hda_path}"
                )
            hou.hda.installFile(hda_path)
            return hda_path
        except Exception:
            tb = traceback.format_exc()
            if attempt < max_retries - 1:
                for node in hou.node("/obj").children():
                    if node.name().startswith("__cinema_"):
                        node.destroy()
                continue
            else:
                raise RuntimeError(
                    f"Builder {builder_fn.__name__} failed after "
                    f"{max_retries} attempts.\nLast error:\n{tb}"
                )
