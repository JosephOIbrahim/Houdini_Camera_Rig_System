"""
Cinema Camera Rig -- Karma Lens Shader VOP Builder

Compiles vex/include/karma_cinema_lens.vfl into a VOP HDA via vcc
(`vcc -O vop -l <out>.hda <src>.vfl`), per the Houdini 21 Karma lens
shader workflow. The resulting cinema_lens_shader VOP is what the
karma:camera:lensshader opdef string on the rig camera references.

Run inside a live Houdini session (uses $HFS to find vcc).
"""

from __future__ import annotations

import os
import subprocess


def build_lens_shader_vop_hda(
    save_dir: str = None,
    hda_name: str = "cinema_lens_shader.hda",
) -> str:
    """
    Compile the Karma CVEX lens shader into a VOP HDA and install it.

    Returns: Absolute path to the built .hda file.
    Raises RuntimeError with vcc's stderr on compile failure.
    """
    import hou

    repo = os.environ.get("CINEMA_CAMERA_REPO")
    if not repo:
        # Derive from this file: <repo>/scripts/python/cinema_camera/builders/
        repo = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))

    if save_dir is None:
        save_dir = os.path.join(repo, "otls")
    os.makedirs(save_dir, exist_ok=True)

    hda_path = os.path.join(save_dir, hda_name)
    include_dir = os.path.join(repo, "vex", "include")
    src_path = os.path.join(include_dir, "karma_cinema_lens.vfl")
    if not os.path.isfile(src_path):
        raise RuntimeError(f"lens shader source missing: {src_path}")

    hfs = hou.getenv("HFS") or os.environ.get("HFS", "")
    vcc = os.path.join(hfs, "bin", "vcc.exe" if os.name == "nt" else "vcc")
    if not os.path.isfile(vcc):
        raise RuntimeError(f"vcc not found at {vcc}")

    result = subprocess.run(
        [vcc, "-O", "vop", "-l", hda_path, "-I", include_dir, src_path],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "vcc failed (%d):\n%s\n%s"
            % (result.returncode, result.stdout, result.stderr)
        )

    hou.hda.installFile(hda_path)

    # Sanity: the opdef section referenced by karma:camera:lensshader must
    # exist on the built definition (karma_lens_shader.OPDEF_SECTION).
    from ..karma_lens_shader import LENS_SHADER_OP, OPDEF_SECTION
    vop_type = hou.nodeType(hou.vopNodeTypeCategory(), LENS_SHADER_OP)
    if vop_type is None:
        raise RuntimeError(
            f"vcc built {hda_path} but VOP type '{LENS_SHADER_OP}' did not register")
    sections = vop_type.definition().sections()
    if OPDEF_SECTION not in sections:
        raise RuntimeError(
            f"VOP '{LENS_SHADER_OP}' lacks section '{OPDEF_SECTION}' "
            f"(has: {sorted(sections)}) -- update karma_lens_shader.OPDEF_SECTION")

    return hda_path
