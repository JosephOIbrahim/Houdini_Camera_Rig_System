"""
Cinema Camera Rig v3.0 -- in-Houdini direct HDA builder.

Run from Houdini's Python shell (NO Synapse needed):

    from cinema_camera.builders.build_all import build_all_v3
    build_all_v3()

Or paste-and-run:

    exec(open(r"C:\\Users\\User\\Houdini_Camera_Rig_System\\scripts\\python\\cinema_camera\\builders\\build_all.py").read())
    build_all_v3()

Build order (lens shader VOP + legacy satellites first, Copernicus 2.0
preview satellites next, orchestrators last; only the LEGACY satellites are
consumed by the orchestrator):
    1. cinema_lens_shader (VOP)             (vcc-compiled Karma lens shader)
    2. cinema::chops_biomechanics::3.0
    3. cinema::cop_anamorphic_flare::3.0    (cop2, consumed by orchestrator)
    4. cinema::cop_sensor_noise::3.0        (cop2, consumed by orchestrator)
    5. cinema::cop_stmap_aov::3.0           (cop2, consumed by orchestrator)
    6. cinema::flare::3.0                   (Copernicus 2.0 preview, INDEPENDENT)
    7. cinema::sensor_noise::3.0            (Copernicus 2.0 preview, INDEPENDENT)
    8. cinema::stmap_aov::3.0               (Copernicus 2.0 preview, INDEPENDENT)
    9. cinema::camera_rig_lop::3.0          (binds the lens shader from 1)
   10. cinema::camera_rig::3.0              (orchestrator -- references 2-5)

All HDAs save to $CINEMA_CAMERA_REPO/otls/ and auto-install in the live session.
"""

from __future__ import annotations

import os
import sys
import traceback


def build_all_v3(force_reimport: bool = True) -> dict:
    """
    Build all 10 v3.0 HDAs in dependency order, install each in the running session.

    Returns a dict: {op_name: hda_path | error_string}.
    Raises RuntimeError if CINEMA_CAMERA_REPO env is missing.
    """
    repo = os.environ.get("CINEMA_CAMERA_REPO")
    if not repo:
        raise RuntimeError(
            "CINEMA_CAMERA_REPO env var is not set. The package json did not load.\n"
            "Either restart Houdini (so packages/cinema_camera_rig.json is read), "
            "or set it manually first:\n"
            '    import os\n'
            '    os.environ["CINEMA_CAMERA_REPO"] = r"C:\\Users\\User\\Houdini_Camera_Rig_System"\n'
            '    sys.path.insert(0, os.path.join(os.environ["CINEMA_CAMERA_REPO"], "scripts", "python"))'
        )

    # Defensive: ensure scripts/python is on sys.path even if env didn't apply it
    scripts_path = os.path.join(repo, "scripts", "python")
    if scripts_path not in sys.path:
        sys.path.insert(0, scripts_path)

    # Always force reimport so the latest builder source is picked up
    if force_reimport:
        for mod in list(sys.modules.keys()):
            if mod.startswith("cinema_camera"):
                del sys.modules[mod]

    import hou
    from cinema_camera.builders.build_lens_shader_vop         import build_lens_shader_vop_hda
    from cinema_camera.builders.build_chops_biomechanics      import build_chops_biomechanics_hda
    from cinema_camera.builders.build_cop_anamorphic_flare    import build_cop_anamorphic_flare_hda
    from cinema_camera.builders.build_cop_sensor_noise        import build_cop_sensor_noise_hda
    from cinema_camera.builders.build_cop_stmap_aov           import build_cop_stmap_aov_hda
    from cinema_camera.builders.build_cop_flare_v2            import build_cop_flare_v2_hda
    from cinema_camera.builders.build_cop_sensor_noise_v2     import build_cop_sensor_noise_v2_hda
    from cinema_camera.builders.build_cop_stmap_aov_v2        import build_cop_stmap_aov_v2_hda
    from cinema_camera.builders.build_camera_rig_lop          import build_camera_rig_lop_hda
    from cinema_camera.builders.build_camera_rig_orchestrator import build_camera_rig_orchestrator_hda

    plan = [
        # Karma lens shader VOP (vcc-compiled; bound by the LOP rig)
        ("cinema_lens_shader (VOP)",            build_lens_shader_vop_hda),
        # Legacy cop2 satellites -- full-featured, consumed by the orchestrator
        ("cinema::chops_biomechanics::3.0",     build_chops_biomechanics_hda),
        ("cinema::cop_anamorphic_flare::3.0",   build_cop_anamorphic_flare_hda),
        ("cinema::cop_sensor_noise::3.0",       build_cop_sensor_noise_hda),
        ("cinema::cop_stmap_aov::3.0",          build_cop_stmap_aov_hda),
        # Copernicus 2.0 preview satellites -- independent of orchestrator (MVP)
        ("cinema::flare::3.0",                  build_cop_flare_v2_hda),
        ("cinema::sensor_noise::3.0",           build_cop_sensor_noise_v2_hda),
        ("cinema::stmap_aov::3.0",              build_cop_stmap_aov_v2_hda),
        # Orchestrator HDAs (consume the legacy cop2 satellites above)
        ("cinema::camera_rig_lop::3.0",         build_camera_rig_lop_hda),
        ("cinema::camera_rig::3.0",             build_camera_rig_orchestrator_hda),
    ]

    print("=" * 64)
    print(f"Cinema Camera Rig v3.0 -- in-Houdini build (target: {repo}/otls)")
    print("=" * 64)

    results = {}
    for i, (op_name, fn) in enumerate(plan, start=1):
        print(f"\n=== Mile {i} of {len(plan)}: {op_name} ===")
        try:
            hda_path = fn()
            hou.hda.installFile(hda_path)
            print(f"  OK    -> {hda_path}")
            results[op_name] = hda_path
        except Exception as e:
            tb = traceback.format_exc()
            print(f"  FAIL  {e}")
            print(tb)
            results[op_name] = f"ERROR: {e}"

    failures = [k for k, v in results.items() if isinstance(v, str) and v.startswith("ERROR:")]
    print("\n" + "=" * 64)
    if failures:
        print(f"RESULT: {len(failures)}/{len(plan)} failed:")
        for op in failures:
            print(f"  - {op}")
    else:
        print(f"RESULT: all {len(plan)} HDAs built and installed")
        print("Tab > Cinema Camera Rig now resolves to ::3.0")
    print("=" * 64)

    return results


if __name__ == "__main__":
    build_all_v3()
