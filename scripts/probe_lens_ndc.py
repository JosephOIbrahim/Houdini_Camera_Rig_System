"""
Karma lens-shader NDC probe (Tier 1 empirical gate) -- in-process LOP render.

Run from a terminal with Houdini's hython:

    hython scripts/probe_lens_ndc.py

Compiles a throwaway probe lens shader that printf's the (x, y) Karma hands it
plus `aspect`, then renders a NON-SQUARE frame through Karma CPU using
Houdini's own Karma Render Settings LOP (so the AOV/render-var schema is
correct) with the probe shader HDA installed and bound on the camera. CVEX
printf is captured off file-descriptor 1. Reports the x/y range, aspect, and
the exact NDC->dn normalization the shader should use.
"""

from __future__ import annotations

import os
import sys
import tempfile

import hou
from pxr import Gf, Sdf, Usd, UsdGeom, UsdLux


PROBE_VFL = """\
#pragma opname  probe_lens_shader
#pragma oplabel "Probe Lens Shader"
cvex
probe_lens_shader(
    float x = 0; float y = 0; float Time = 0;
    float dofx = 0; float dofy = 0;
    float aspect = 1; float focus = 1; float focal = 1;
    float fstop = 0; float aperture = 1; int isRHS = 0;
    export vector P = {0,0,0}; export vector I = {0,0,0}; export int valid = 1)
{
    printf("PROBE x=%g y=%g aspect=%g aperture=%g focal=%g isRHS=%d\\n",
           x, y, aspect, aperture, focal, isRHS);
    I = set(x * aperture * 0.5 * aspect / focal, y * aperture * 0.5 / focal, -1.0);
    P = set(dofx, dofy, 0.0);
    I *= focus; I -= P;
    if (!isRHS) { P.z = -P.z; I.z = -I.z; }
    valid = 1;
}
"""

RES_X, RES_Y = 24, 14                  # small, non-square (~1.71)
APERTURE_W, APERTURE_H = 36.0, 20.25   # 16:9 filmback


def _tool(name):
    hfs = hou.getenv("HFS") or os.environ.get("HFS", "")
    exe = name + (".exe" if os.name == "nt" else "")
    p = os.path.join(hfs, "bin", exe)
    if not os.path.isfile(p):
        raise RuntimeError(f"{name} not found at {p} (run via hython)")
    return p


def _set_first(node, names, value):
    for n in names:
        p = node.parm(n)
        if p is not None:
            try:
                p.set(value)
                return n
            except Exception:
                pass
    return None


def main():
    import subprocess
    tmp = tempfile.mkdtemp(prefix="cinema_ndc_probe_")
    vfl = os.path.join(tmp, "probe.vfl")
    hda = os.path.join(tmp, "probe_lens_shader.hda")
    usd = os.path.join(tmp, "scene.usda")
    log = os.path.join(tmp, "render.log")

    open(vfl, "w").write(PROBE_VFL)

    # 1) Compile + install the probe lens shader VOP.
    r = subprocess.run([_tool("vcc"), "-O", "vop", "-l", hda, vfl],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print("vcc failed:\n", r.stdout, r.stderr); return 1
    hou.hda.installFile(hda)
    os.environ["HOUDINI_OTLSCAN_PATH"] = tmp + (";" if os.name == "nt" else ":") + "&"
    print(f"[probe] compiled + installed {hda}")

    # 2) Minimal scene layer: camera (bound to the probe lens shader) + sphere + light.
    stage = Usd.Stage.CreateNew(usd)
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)
    cam = UsdGeom.Camera.Define(stage, "/cam")
    cam.AddTranslateOp().Set(Gf.Vec3d(0, 0, 6))
    cam.CreateFocalLengthAttr(35.0)
    cam.CreateHorizontalApertureAttr(APERTURE_W)
    cam.CreateVerticalApertureAttr(APERTURE_H)
    cam.CreateFocusDistanceAttr(6.0)
    cam.CreateClippingRangeAttr(Gf.Vec2f(0.01, 10000.0))
    cp = cam.GetPrim()
    cp.CreateAttribute("karma:camera:use_lensshader", Sdf.ValueTypeNames.Bool).Set(True)
    cp.CreateAttribute("karma:camera:lensshader", Sdf.ValueTypeNames.String).Set(
        "opdef:/Vop/probe_lens_shader?CVexVflCode")
    UsdGeom.Sphere.Define(stage, "/geo/sphere").CreateRadiusAttr(1.5)
    UsdLux.DomeLight.Define(stage, "/lights/dome").CreateIntensityAttr(1.0)
    stage.GetRootLayer().Save()
    print(f"[probe] wrote {usd}")

    # 3) LOP graph: sublayer the scene -> Karma Render Settings (authors the correct
    #    render var/AOV) -> USD Render ROP. Render in-process; capture fd 1.
    lopnet = hou.node("/obj").createNode("lopnet", "probe_render")
    sub = lopnet.createNode("sublayer")
    _set_first(sub, ("filepath1", "soppath", "filelist"), usd)
    krs = lopnet.createNode("karmarendersettings")
    krs.setInput(0, sub)
    _set_first(krs, ("camera",), "/cam")
    _set_first(krs, ("resolutionx", "res_overridex", "resx"), RES_X)
    _set_first(krs, ("resolutiony", "res_overridey", "resy"), RES_Y)
    _set_first(krs, ("samplesperpixel", "karma_samplesperpixel"), 1)
    rop = lopnet.createNode("usdrender_rop")
    rop.setInput(0, krs)
    _set_first(rop, ("renderer",), "BRAY_HdKarma")
    _set_first(rop, ("rendersettings", "settingspath"), "/Render/rendersettings")
    print(f"[probe] rendering {RES_X}x{RES_Y} in-process ...")

    sys.stdout.flush()
    saved = os.dup(1)
    fd = os.open(log, os.O_WRONLY | os.O_CREAT | os.O_TRUNC)
    os.dup2(fd, 1)
    try:
        rop.render(verbose=False)
    except Exception as e:
        os.dup2(saved, 1)
        print("[probe] render raised:", e)
    finally:
        sys.stdout.flush()
        os.dup2(saved, 1)
        os.close(saved)
        os.close(fd)
    blob = open(log, errors="replace").read()

    # 4) Parse PROBE lines.
    xs, ys, asp = [], [], []
    for line in blob.splitlines():
        if "PROBE" not in line:
            continue
        try:
            kv = dict(t.split("=") for t in line.split() if "=" in t)
            xs.append(float(kv["x"])); ys.append(float(kv["y"])); asp.append(float(kv["aspect"]))
        except Exception:
            pass

    if not xs:
        print("\n[probe] No PROBE samples captured.")
        tail = "\n".join(l for l in blob.splitlines()
                         if any(k in l.lower() for k in
                                ("error", "warning", "unsupported", "plane",
                                 "lens", "ray", "render", "aov", "primary")))
        print("----- render log (filtered) -----\n", tail[-3000:])
        return 2

    xmin, xmax, ymin, ymax = min(xs), max(xs), min(ys), max(ys)
    a = asp[0]
    ax, ay = max(abs(xmin), abs(xmax)), max(abs(ymin), abs(ymax))
    ratio = ax / ay if ay else float("nan")
    print("\n================= LENS-SHADER NDC PROBE RESULT =================")
    print(f"samples captured : {len(xs)}")
    print(f"aspect (input)   : {a:.6g}   (render {RES_X}x{RES_Y}, aperture {APERTURE_W}/{APERTURE_H}={APERTURE_W/APERTURE_H:.4g})")
    print(f"x range          : [{xmin:.5g}, {xmax:.5g}]   max|x| = {ax:.5g}")
    print(f"y range          : [{ymin:.5g}, {ymax:.5g}]   max|y| = {ay:.5g}")
    print(f"max|x| / max|y|  : {ratio:.5g}   (1.0 => square NDC; {a:.3g} => x pre-scaled by aspect)")
    print("---------------------------------------------------------------")
    if abs(ratio - 1.0) < 0.06:
        print("=> SQUARE [-1,1] NDC, aspect applied in-projection. NDC->dn:")
        print("     e = sqrt(aspect^2 + 1);  dn = ( x*aspect/e , y/e )   # r=1 at corner")
    elif abs(ratio - a) < 0.06 * max(1.0, a):
        print("=> x PRE-SCALED by aspect. NDC->dn:")
        print("     e = sqrt(aspect^2 + 1);  dn = ( x/e , y/e )")
    else:
        print("=> unrecognized; paste this block and I'll derive the mapping.")
    print("   (max is at pixel CENTERS; true edge ~ *N/(N-1).)")
    print("===============================================================")
    print(f"\n[probe] artifacts in {tmp}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
