"""Probe Karma's aperture-disc sample (dofx,dofy) scale vs f-stop, in-process."""
import os, sys, tempfile, math, subprocess
import hou
from pxr import Gf, Sdf, Usd, UsdGeom, UsdLux, UsdShade

TMP = tempfile.mkdtemp(prefix="dofprobe_")

PROBE_VFL = """\
#pragma opname  probe_dof_shader
#pragma oplabel "Probe DOF Shader"
cvex
probe_dof_shader(
    float x = 0; float y = 0; float Time = 0;
    float dofx = 0; float dofy = 0;
    float aspect = 1; float focus = 1; float focal = 1;
    float fstop = 0; float aperture = 1; int isRHS = 0;
    export vector P = {0,0,0}; export vector I = {0,0,0}; export int valid = 1)
{
    printf("DOF dofx=%g dofy=%g aperture=%g fstop=%g\\n", dofx, dofy, aperture, fstop);
    I = set(x * aperture * 0.5 * aspect / focal, y * aperture * 0.5 / focal, -1.0);
    P = set(dofx, dofy, 0.0);
    I *= focus; I -= P;
    if (!isRHS) { P.z = -P.z; I.z = -I.z; }
    valid = 1;
}
"""


def sfirst(node, names, value):
    for n in names:
        p = node.parm(n)
        if p is not None:
            try:
                p.set(value); return
            except Exception:
                pass


def main():
    vfl = os.path.join(TMP, "p.vfl"); hda = os.path.join(TMP, "probe_dof_shader.hda")
    open(vfl, "w").write(PROBE_VFL)
    hfs = hou.getenv("HFS")
    r = subprocess.run([os.path.join(hfs, "bin", "vcc.exe"), "-O", "vop", "-l", hda, vfl],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print("vcc failed:", r.stderr); return
    hou.hda.installFile(hda)
    os.environ["HOUDINI_OTLSCAN_PATH"] = TMP + ";&"
    print("[dof] shader compiled")

    def render(fstop):
        usd = os.path.join(TMP, f"s{int(fstop)}.usda")
        st = Usd.Stage.CreateNew(usd)
        UsdGeom.SetStageUpAxis(st, UsdGeom.Tokens.y); UsdGeom.SetStageMetersPerUnit(st, 1.0)
        cam = UsdGeom.Camera.Define(st, "/cam")
        cam.AddTranslateOp().Set(Gf.Vec3d(0, 0, 6))
        cam.CreateFocalLengthAttr(50.0)
        cam.CreateHorizontalApertureAttr(36.0); cam.CreateVerticalApertureAttr(20.25)
        cam.CreateFocusDistanceAttr(6.0); cam.CreateFStopAttr(fstop)
        cam.CreateClippingRangeAttr(Gf.Vec2f(0.01, 1e4))
        cp = cam.GetPrim()
        cp.CreateAttribute("karma:camera:use_lensshader", Sdf.ValueTypeNames.Bool).Set(True)
        cp.CreateAttribute("karma:camera:lensshader", Sdf.ValueTypeNames.String).Set(
            "opdef:/Vop/probe_dof_shader?CVexVflCode")
        sp = UsdGeom.Sphere.Define(st, "/geo/s"); sp.CreateRadiusAttr(1.0)
        mat = UsdShade.Material.Define(st, "/geo/m"); sh = UsdShade.Shader.Define(st, "/geo/m/s")
        sh.CreateIdAttr("UsdPreviewSurface")
        sh.CreateInput("emissiveColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(1, 1, 1))
        mat.CreateSurfaceOutput().ConnectToSource(sh.ConnectableAPI(), "surface")
        UsdShade.MaterialBindingAPI.Apply(sp.GetPrim()); UsdShade.MaterialBindingAPI(sp.GetPrim()).Bind(mat)
        UsdLux.DomeLight.Define(st, "/l").CreateIntensityAttr(0.1)
        st.GetRootLayer().Save()

        lop = hou.node("/obj").createNode("lopnet", f"r{int(fstop)}")
        sub = lop.createNode("sublayer"); sfirst(sub, ("filepath1",), usd)
        krs = lop.createNode("karmarendersettings"); krs.setInput(0, sub)
        sfirst(krs, ("camera",), "/cam")
        sfirst(krs, ("resolutionx", "resx"), 12); sfirst(krs, ("resolutiony", "resy"), 8)
        sfirst(krs, ("samplesperpixel",), 32)
        rop = lop.createNode("usdrender_rop"); rop.setInput(0, krs)
        sfirst(rop, ("renderer",), "BRAY_HdKarma")
        sfirst(rop, ("rendersettings",), "/Render/rendersettings")
        sfirst(rop, ("outputimage", "picture"), os.path.join(TMP, f"o{int(fstop)}.exr"))
        log = os.path.join(TMP, f"l{int(fstop)}.txt")
        sys.stdout.flush(); sv = os.dup(1); fd = os.open(log, os.O_WRONLY | os.O_CREAT | os.O_TRUNC); os.dup2(fd, 1)
        try:
            rop.render(verbose=False)
        finally:
            sys.stdout.flush(); os.dup2(sv, 1); os.close(sv); os.close(fd)
        rmax = 0.0; ap = 0.0; n = 0
        for line in open(log, errors="replace").read().splitlines():
            if line.startswith("DOF"):
                kv = dict(t.split("=") for t in line.split() if "=" in t)
                rr = math.hypot(float(kv["dofx"]), float(kv["dofy"])); rmax = max(rmax, rr)
                ap = float(kv["aperture"]); n += 1
        print(f"[dof] fstop={fstop}  samples={n}  max|dof|={rmax:.5g}  aperture_input={ap:.5g}")
        return rmax, ap

    r2, a2 = render(2.0)
    r8, a8 = render(8.0)
    if r8 > 0:
        print(f"[dof] max|dof| ratio f2/f8 = {r2/r8:.3g}  (physical DOF ~ 4.0)")
    print(f"[dof] aperture_input ratio f2/f8 = {a2/max(a8,1e-9):.3g}")


main()
