# Cinema Camera Rig v4.0 — Setup Guide

**Target:** `C:\Users\User\OneDrive\Documents\houdini21.0\`
**Tools:** Claude Code + Synapse (Houdini command port bridge)
**Time:** ~2 hours hands-on, spread across the 8-day build

---

## BEFORE YOU START

You need three things running:

1. **Houdini 21** installed and launchable
2. **Claude Code** installed and working in your terminal
3. **Synapse bridge** configured (your existing Claude Code ↔ Houdini command port setup)

Everything below assumes your Houdini user prefs live at:
```
C:\Users\User\OneDrive\Documents\houdini21.0\
```

If yours is different, replace this path everywhere.

---

## STEP 1: Create the folder structure

Open a terminal. Run these commands:

```powershell
# Base paths inside Houdini ecosystem
$H21 = "C:\Users\User\OneDrive\Documents\houdini21.0"

# Houdini auto-scanned directories (may already exist)
New-Item -ItemType Directory -Force -Path "$H21\otls"
New-Item -ItemType Directory -Force -Path "$H21\vex\include"
New-Item -ItemType Directory -Force -Path "$H21\scripts\python\cinema_camera"
New-Item -ItemType Directory -Force -Path "$H21\scripts\python\cinema_camera\builders"
New-Item -ItemType Directory -Force -Path "$H21\scripts\python\cinema_camera\bodies"
New-Item -ItemType Directory -Force -Path "$H21\scripts\python\cinema_camera\lenses"

# Project-specific files (not auto-scanned, just organized here)
New-Item -ItemType Directory -Force -Path "$H21\cinema_camera\lenses"
New-Item -ItemType Directory -Force -Path "$H21\cinema_camera\tests"
```

After this you should see:

```
houdini21.0\
├── otls\                          ← HDAs go here (auto-loaded)
├── vex\
│   └── include\                   ← VEX headers go here (auto-included)
├── scripts\
│   └── python\
│       └── cinema_camera\         ← Python package (auto-importable)
│           ├── builders\
│           ├── bodies\
│           └── lenses\
├── cinema_camera\                 ← JSON data, tests, docs
│   ├── lenses\
│   └── tests\
└── packages\                      ← optional, created in Step 2
```

---

## STEP 2: Create the Houdini package descriptor (optional but recommended)

This tells Houdini about the `CINEMA_CAMERA_PATH` environment variable so all scripts can find the project data files (JSON lens specs, test .hip files, etc).

Create this file:

```
C:\Users\User\OneDrive\Documents\houdini21.0\packages\cinema_camera_rig.json
```

With this content:

```json
{
    "env": [
        {
            "CINEMA_CAMERA_PATH": "C:/Users/User/OneDrive/Documents/houdini21.0/cinema_camera"
        }
    ]
}
```

That's it. Next time Houdini starts, `$CINEMA_CAMERA_PATH` is set automatically. Every Python script and VEX shader can find the lens JSON files without hardcoded paths.

If the `packages\` folder doesn't exist yet:

```powershell
New-Item -ItemType Directory -Force -Path "$H21\packages"
```

---

## STEP 3: Open Claude Code and set the working paths

In your Claude Code terminal, start a session and give it context:

```
You are building the Cinema Camera Rig v4.0 for Houdini 21.

File locations:
  Python package:  C:\Users\User\OneDrive\Documents\houdini21.0\scripts\python\cinema_camera\
  VEX headers:     C:\Users\User\OneDrive\Documents\houdini21.0\vex\include\
  HDAs:            C:\Users\User\OneDrive\Documents\houdini21.0\otls\
  Lens JSON data:  C:\Users\User\OneDrive\Documents\houdini21.0\cinema_camera\lenses\
  Tests:           C:\Users\User\OneDrive\Documents\houdini21.0\cinema_camera\tests\

Environment variable CINEMA_CAMERA_PATH = C:\Users\User\OneDrive\Documents\houdini21.0\cinema_camera
```

Then paste the v4.0 Physical Architecture spec and the Synapse Refactor spec.

---

## STEP 4: Build Phase 1 — Python protocols (no Houdini needed)

Tell Claude Code:

```
Build Phase 1. Write all protocol files.
```

Claude Code creates these files:

```
scripts\python\cinema_camera\__init__.py
scripts\python\cinema_camera\protocols.py        ← dataclasses: LensSpec, CameraState, etc.
scripts\python\cinema_camera\biomechanics.py     ← BiomechanicsParams + derive_biomechanics()
scripts\python\cinema_camera\registry.py         ← lens/body registry
scripts\python\cinema_camera\optics_engine.py    ← FOV, DOF, hyperfocal calculations
scripts\python\cinema_camera\lenses\__init__.py
scripts\python\cinema_camera\lenses\cooke_anamorphic.py  ← JSON parser
scripts\python\cinema_camera\bodies\__init__.py
scripts\python\cinema_camera\bodies\alexa35.py   ← ARRI Alexa 35 spec

cinema_camera\lenses\cooke_ana_i_s35_50mm.json   ← v4.0 JSON with mechanics
cinema_camera\lenses\cooke_ana_i_s35_300mm.json
cinema_camera\lenses\_schema_v4.json

cinema_camera\tests\test_protocols.py
cinema_camera\tests\test_biomechanics.py
```

**Verify it worked:**

```powershell
cd "C:\Users\User\OneDrive\Documents\houdini21.0"
hython -c "from cinema_camera.protocols import LensSpec; print('protocols OK')"
hython -c "from cinema_camera.biomechanics import derive_biomechanics; print('biomechanics OK')"
```

Both should print OK. If `hython` can't find `cinema_camera`, the `scripts\python\` path isn't being scanned — check that the folder exists and restart hython.

---

## STEP 5: Build Phase 2a — VEX files (no Houdini needed)

Tell Claude Code:

```
Build the VEX files: libcinema_optics.h and karma_cinema_lens.vfl.
```

Claude Code creates:

```
vex\include\libcinema_optics.h      ← optical math library + dynamic squeeze functions
vex\include\karma_cinema_lens.vfl   ← CVEX lens shader source
```

**Verify VEX compiles:**

```powershell
vcc -e cvex "C:\Users\User\OneDrive\Documents\houdini21.0\vex\include\karma_cinema_lens.vfl"
```

Should compile without errors. If it can't find `libcinema_optics.h`, the `vex\include\` path isn't being picked up — this is unusual since Houdini scans `$HOUDINI_USER_PREF_DIR/vex/include/` by default.

---

## STEP 6: Build Phase 2b — USD builder and shader binding (no Houdini needed)

Tell Claude Code:

```
Build the USD builder, shader binding, and EXR metadata pipeline.
```

Claude Code creates:

```
scripts\python\cinema_camera\usd_builder.py         ← build_usd_camera_rig() + configure_render_product()
scripts\python\cinema_camera\karma_lens_shader.py    ← CVEX shader binding
scripts\python\cinema_camera\i_technology.py         ← Cooke /i metadata
scripts\python\cinema_camera\post_pipeline.py        ← v4.0 effect chain

cinema_camera\tests\test_usd_rig_hierarchy.py
cinema_camera\tests\test_exr_metadata.py
cinema_camera\tests\test_cvex_lens_shader.py
```

**Verify USD builder:**

```powershell
hython -c "
from cinema_camera.usd_builder import build_usd_camera_rig
from pxr import Usd
stage = Usd.Stage.CreateInMemory()
print('usd_builder OK')
"
```

---

## STEP 7: Build Phase 2c — Synapse builder scripts (no Houdini yet)

Tell Claude Code:

```
Write the Synapse builder scripts and preflight check.
```

Claude Code creates:

```
scripts\python\cinema_camera\synapse_preflight.py
scripts\python\cinema_camera\builders\__init__.py
scripts\python\cinema_camera\builders\build_chops_biomechanics.py
scripts\python\cinema_camera\builders\build_cop_anamorphic_flare.py
scripts\python\cinema_camera\builders\build_cop_sensor_noise.py
scripts\python\cinema_camera\builders\build_cop_stmap_aov.py
```

These are just Python files on disk. Nothing has run in Houdini yet. Claude Code writes them, you can read them, they're ready to execute.

---

## STEP 8: Open Houdini and enable the command port

1. Launch Houdini 21
2. Go to **Edit → Preferences → Network** (or Scripting, depending on build)
3. Enable **Command Port** on port **12345**
4. Alternatively, add to your `houdini.env`:
   ```
   HOUDINI_SCRIPT_PORT = 12345
   ```

Verify the port is open. In Houdini's Python shell:

```python
import hou
print(hou.applicationVersionString())
# Should print 21.x.x
```

If Synapse is already configured from your previous bridge work, the command port is probably already on. Confirm Claude Code can reach it.

---

## STEP 9: Run the Synapse preflight

Tell Claude Code:

```
Run synapse_preflight() through the bridge.
```

Claude Code sends this to your live Houdini session:

```python
import sys
sys.path.insert(0, r"C:\Users\User\OneDrive\Documents\houdini21.0\scripts\python")
from cinema_camera.synapse_preflight import synapse_preflight
result = synapse_preflight()
print(result)
```

You should see output like:

```python
{
    'houdini_version': '21.0.xxx',
    'cinema_camera_path': 'C:/Users/User/OneDrive/Documents/houdini21.0/cinema_camera',
    'vex_include_path': 'C:/Users/User/OneDrive/Documents/houdini21.0/vex/include',
    'hda_dirs_ready': True,
    'copernicus_available': True
}
```

If anything fails, fix it before continuing. Common issues:

- `CINEMA_CAMERA_PATH not set` → restart Houdini so it reads the package descriptor from Step 2
- `copernicus_available: False` → you're on a Houdini license without COPs GPU. The builders will fall back to classic COP2 nodes

---

## STEP 10: Build the HDAs through Synapse

Tell Claude Code:

```
Execute the Synapse builders. Build all 4 HDAs.
```

Claude Code sends each builder function to your live Houdini session in sequence:

```python
from cinema_camera.builders.build_chops_biomechanics import build_chops_biomechanics_hda
from cinema_camera.builders.build_cop_anamorphic_flare import build_cop_anamorphic_flare_hda
from cinema_camera.builders.build_cop_sensor_noise import build_cop_sensor_noise_hda
from cinema_camera.builders.build_cop_stmap_aov import build_cop_stmap_aov_hda

# Each call creates nodes in your session, wraps them as HDA, saves to otls\
path1 = build_chops_biomechanics_hda(
    save_dir=r"C:\Users\User\OneDrive\Documents\houdini21.0\otls"
)
path2 = build_cop_anamorphic_flare_hda(
    save_dir=r"C:\Users\User\OneDrive\Documents\houdini21.0\otls"
)
path3 = build_cop_sensor_noise_hda(
    save_dir=r"C:\Users\User\OneDrive\Documents\houdini21.0\otls"
)
path4 = build_cop_stmap_aov_hda(
    save_dir=r"C:\Users\User\OneDrive\Documents\houdini21.0\otls"
)
```

**What you'll see in Houdini during this step:**

Temporary geometry nodes appear at `/obj/__cinema_biomech_builder`, `/obj/__cinema_flare_builder`, etc. Inside each, the builder creates the CHOP/COP network, wires the nodes, promotes parameters, wraps the network as an HDA, saves the `.hda` file, then destroys the temporary container. Each builder takes a few seconds.

**After this step, your `otls\` folder contains:**

```
otls\
├── cinema_chops_biomechanics_1.0.hda
├── cinema_cop_anamorphic_flare_2.0.hda
├── cinema_cop_sensor_noise_1.0.hda
└── cinema_cop_stmap_aov_1.0.hda
```

**Verify they loaded:**

In Houdini's Python shell:

```python
import hou
print(hou.nodeType(hou.chopNodeTypeCategory(), "cinema::chops_biomechanics::1.0"))
print(hou.nodeType(hou.cop2NodeTypeCategory(), "cinema::cop_anamorphic_flare::2.0"))
print(hou.nodeType(hou.cop2NodeTypeCategory(), "cinema::cop_sensor_noise::1.0"))
print(hou.nodeType(hou.cop2NodeTypeCategory(), "cinema::cop_stmap_aov::1.0"))
```

All four should return node type objects, not None.

---

## STEP 11: Integration testing

Tell Claude Code:

```
Run integration tests through Synapse.
```

Claude Code executes the test suite through the bridge. The tests verify:

- Protocol dataclasses instantiate correctly
- USD camera rig hierarchy builds with all expected prims
- Biomechanics auto-derive produces correct values for 50mm and 300mm lenses
- HDA parameters promote and wire correctly
- VEX compiles and produces expected outputs
- EXR metadata attributes author correctly

If tests fail, Claude Code gets the tracebacks through the bridge and can fix and retry.

---

## STEP 12: Build the top-level orchestrator HDA

Tell Claude Code:

```
Build the top-level cinema::camera_rig::2.0 HDA that wires everything together.
```

This is another Synapse builder call. It creates the master LOP HDA that:

- References the body HDA (Alexa 35)
- References the lens HDA (Cooke Anamorphic)
- Runs the optics engine
- Binds the CVEX lens shader
- Connects biomechanics CHOPs
- Chains the Copernicus post effects
- Configures the render product with EXR metadata

Saved to `otls\cinema_camera_rig_2.0.hda`.

---

## STEP 13: Test the rig

1. Open a new Houdini scene
2. Create a LOP network
3. TAB → search "cinema" → you should see `cinema::camera_rig::2.0`
4. Drop it in
5. In the parameter interface:
   - Set Body to "ARRI ALEXA 35"
   - Set Lens to "Cooke Anamorphic /i S35 50mm"
   - Set focus distance to 2.0m
   - Set T-stop to 2.8
6. View in Solaris viewport — you have a camera with physically correct FOV
7. Animate the focus distance — watch the effective squeeze change (Mumps)
8. Check the Scene Graph — verify the FluidHead/Body/Sensor/EntrancePupil hierarchy
9. Render with Karma — the CVEX lens shader applies distortion at ray level

---

## FINAL STATE

After all steps, your Houdini 21 ecosystem looks like this:

```
C:\Users\User\OneDrive\Documents\houdini21.0\
│
├── otls\                                    ← Auto-loaded by Houdini
│   ├── cinema_camera_rig_2.0.hda           ← Master orchestrator
│   ├── cinema_chops_biomechanics_1.0.hda   ← Built by Synapse
│   ├── cinema_cop_anamorphic_flare_2.0.hda ← Built by Synapse
│   ├── cinema_cop_sensor_noise_1.0.hda     ← Built by Synapse
│   ├── cinema_cop_stmap_aov_1.0.hda        ← Built by Synapse
│   └── ...any v3.0 HDAs if upgrading...
│
├── vex\include\                             ← Auto-included by VEX
│   ├── libcinema_optics.h                   ← Written by Claude Code
│   └── karma_cinema_lens.vfl               ← Written by Claude Code
│
├── scripts\python\cinema_camera\            ← Auto-importable
│   ├── __init__.py
│   ├── protocols.py
│   ├── biomechanics.py
│   ├── registry.py
│   ├── optics_engine.py
│   ├── usd_builder.py
│   ├── karma_lens_shader.py
│   ├── i_technology.py
│   ├── post_pipeline.py
│   ├── synapse_preflight.py
│   ├── builders\
│   │   ├── __init__.py
│   │   ├── build_chops_biomechanics.py
│   │   ├── build_cop_anamorphic_flare.py
│   │   ├── build_cop_sensor_noise.py
│   │   └── build_cop_stmap_aov.py
│   ├── bodies\
│   │   ├── __init__.py
│   │   └── alexa35.py
│   └── lenses\
│       ├── __init__.py
│       └── cooke_anamorphic.py
│
├── cinema_camera\                           ← Project data + tests
│   ├── lenses\
│   │   ├── cooke_ana_i_s35_50mm.json
│   │   ├── cooke_ana_i_s35_300mm.json
│   │   └── _schema_v4.json
│   ├── tests\
│   │   ├── test_protocols.py
│   │   ├── test_biomechanics.py
│   │   ├── test_usd_rig_hierarchy.py
│   │   ├── test_exr_metadata.py
│   │   └── test_cvex_lens_shader.py
│   └── README.md
│
└── packages\
    └── cinema_camera_rig.json               ← Sets CINEMA_CAMERA_PATH
```

---

## TROUBLESHOOTING

**"cinema_camera" not importable in Houdini Python shell**
→ `scripts\python\` must be directly inside `houdini21.0\`. Houdini adds `$HOUDINI_USER_PREF_DIR/scripts/python/` to `sys.path` automatically. Verify with: `import sys; print([p for p in sys.path if 'scripts' in p])`

**HDAs don't appear in TAB menu**
→ `otls\` must be directly inside `houdini21.0\`. Houdini scans `$HOUDINI_USER_PREF_DIR/otls/` on startup. If you added HDAs after startup, run: `hou.hda.installFile(r"C:\...\otls\cinema_chops_biomechanics_1.0.hda")`

**VEX can't find libcinema_optics.h**
→ File must be at `vex\include\libcinema_optics.h` (not `vex\libcinema_optics.h`). The `include` subfolder matters.

**Synapse can't connect**
→ Verify command port is on: Houdini → Edit → Preferences → look for port 12345. Or check `hou.hscript("commandportinfo")` in the Python shell.

**CINEMA_CAMERA_PATH not set**
→ Restart Houdini after creating the package descriptor in Step 2. Verify with: `import os; print(os.environ.get("CINEMA_CAMERA_PATH"))`

**OneDrive sync conflicts**
→ OneDrive can lock `.hda` files during sync. If a builder fails with a permission error, pause OneDrive sync, run the builder, then resume sync. Alternatively, set OneDrive to "Files On-Demand" and keep the `otls\` folder set to "Always keep on this device."

**Builder creates nodes but HDA save fails**
→ Usually a name conflict. Run `hou.hda.uninstallFile()` on the existing HDA first, then retry the builder. The retry protocol in the Synapse Refactor spec handles this automatically.
