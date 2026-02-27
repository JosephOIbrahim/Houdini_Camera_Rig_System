# Cinema Camera Rig v4.0 — Claude Code Agent Team Handoff

## CLAUDE.md (Place in project root)

```
# Cinema Camera Rig v4.0 — Wolfram Integration
# Claude Code Agent Team Configuration

## IDENTITY
You are an autonomous agent team managing a Houdini 21 VFX pipeline through Synapse WebSocket bridge.
You have DIRECT file system access and can execute Python commands inside Houdini remotely.

## CRITICAL PATHS (Windows)
HOUDINI_PREFS  = C:\Users\User\houdini21.0\
ONEDRIVE_DOCS  = C:\Users\User\OneDrive\Documents\houdini21.0\
SYNAPSE_CLIENT = C:\Users\User\.synapse\agent\synapse_ws.py
HOUDINI_PYTHON = C:\Users\User\houdini21.0\scripts\python\
CINEMA_CAMERA  = C:\Users\User\houdini21.0\scripts\python\cinema_camera\
LENS_SPECS     = C:\Users\User\OneDrive\Documents\houdini21.0\cinema_camera\lenses\
WOLFRAM_APP_ID = LKY2AG-QX3G7VW7YR

## DUAL-PATH WARNING
Files exist in TWO locations. Houdini loads from HOUDINI_PREFS.
OneDrive has source/specs. ALWAYS sync edits to BOTH paths.

## SYNAPSE PROTOCOL
Port: 9999 (WebSocket at ws://localhost:9999/synapse)
Start in Houdini Python Shell: from synapse.server import SynapseServer; s = SynapseServer(port=9999); s.start()
Client: python -c "from synapse_ws import SynapseClient; ..."
```

---

## AGENT TEAM ARCHITECTURE

### Overview: MOE (Mixture of Experts) via Synapse

Claude Code orchestrates 5 specialist roles. Each role has a Synapse interaction pattern.
The key insight: **Synapse is the bridge between Claude Code's file system and Houdini's live runtime.**

```
┌─────────────────────────────────────────────────┐
│                 ORCHESTRATOR                      │
│         (Claude Code main session)                │
│                                                   │
│  Reads state → Routes to specialist → Validates   │
└──────────┬────────────┬───────────┬──────────────┘
           │            │           │
     ┌─────▼──┐   ┌─────▼──┐  ┌────▼───┐
     │  ENV   │   │  CODE  │  │  TEST  │
     │ Agent  │   │ Agent  │  │ Agent  │
     └────────┘   └────────┘  └────────┘
           │            │           │
           └────────────┼───────────┘
                        │
              ┌─────────▼─────────┐
              │   SYNAPSE BRIDGE   │
              │  ws://localhost:9999│
              └─────────┬─────────┘
                        │
              ┌─────────▼─────────┐
              │   HOUDINI 21.0    │
              │  Python 3.11.7    │
              │  haio event loop  │
              └───────────────────┘
                        │
           ┌────────────┼────────────┐
     ┌─────▼──┐                ┌─────▼──┐
     │ BUILD  │                │  USD   │
     │ Agent  │                │ Agent  │
     └────────┘                └────────┘
```

### Role Definitions

#### 1. ENV Agent — Environment & Dependencies
**Trigger:** Import errors, path issues, missing modules, sys.path debugging
**Capabilities:**
- Direct file copy/move between HOUDINI_PREFS and ONEDRIVE_DOCS
- pip install with --target to HOUDINI_PYTHON
- sys.path inspection via Synapse
- .pyc cache cleanup
- Process management (netstat, taskkill for port conflicts)

**Synapse Pattern:**
```python
# ENV Agent: Verify environment inside Houdini
await client.execute_python("""
import sys
result = {
    'python_version': sys.version,
    'sys_path': sys.path,
    'has_wolframalpha': 'wolframalpha' in sys.modules or __import__('importlib').util.find_spec('wolframalpha') is not None,
    'has_httpx': __import__('importlib').util.find_spec('httpx') is not None,
    'houdini_prefs': __import__('hou').homeHoudiniDirectory(),
}
print(result)
""")
```

#### 2. CODE Agent — Python/VEX Code Editing
**Trigger:** SyntaxError, logic bugs, feature implementation, file patching
**Capabilities:**
- Direct file read/write on both paths
- AST-aware Python editing
- VEX code generation
- Indentation/encoding validation before write

**Critical Rule:** After ANY edit, sync to both paths:
```bash
# Always dual-write
cp "$ONEDRIVE_DOCS/scripts/python/cinema_camera/wolfram_oracle.py" \
   "$HOUDINI_PREFS/scripts/python/cinema_camera/wolfram_oracle.py"
```

#### 3. TEST Agent — Synapse Test Runner
**Trigger:** After any code change, validation needed, phase execution
**Capabilities:**
- Execute upgrade scripts (W1-W6) via Synapse
- Parse error tracebacks and route to CODE Agent
- Verify HDA existence and parameter states
- Run integration tests

**Synapse Pattern:**
```python
# TEST Agent: Run a Wolfram phase inside Houdini
await client.execute_python("""
import sys, json
sys.path.insert(0, r'C:\\Users\\User\\OneDrive\\Documents\\houdini21.0\\scripts\\python')
from cinema_camera.wolfram_upgrades.validate_optics import validate_all_optics
result = validate_all_optics()
print(json.dumps(result, default=str))
""")
```

#### 4. BUILD Agent — HDA Construction
**Trigger:** All Wolfram phases pass, HDA creation needed
**Capabilities:**
- Create HDAs via Synapse (hou.node, hou.HDADefinition)
- Set parameters, create VOP/VEX networks
- Install HDAs to otls/ directory
- Wire node connections

**Synapse Pattern:**
```python
# BUILD Agent: Create an HDA inside Houdini
await client.execute_python("""
import hou
obj = hou.node('/obj')
geo = obj.createNode('geo', 'camera_rig_build')
# ... build node network ...
# Save as HDA
subnet = geo.collapseIntoSubnet()
hda = subnet.createDigitalAsset(
    name='cinema::lens_distortion',
    hda_file_name=hou.homeHoudiniDirectory() + '/otls/cinema_camera_rig.hda',
    description='Cinema Lens Distortion'
)
print('HDA created:', hda.type().name())
""")
```

#### 5. USD Agent — Solaris/USD Pipeline
**Trigger:** USD composition, Karma setup, render delegate config
**Capabilities:**
- Solaris LOP network construction
- USD layer/sublayer composition
- MaterialX shader binding
- Karma XPU render settings

---

## SYNAPSE CLIENT WRAPPER

Create this file for Claude Code to use:

### `synapse_runner.py`
```python
"""
Synapse Runner — Claude Code ↔ Houdini bridge
Usage: python synapse_runner.py <command_file.py> [--port 9999] [--timeout 30]
"""
import asyncio
import sys
import json

# Add synapse client to path
sys.path.insert(0, r'C:\Users\User\.synapse\agent')

async def run_in_houdini(code: str, port: int = 9999, timeout: int = 30):
    """Execute Python code inside Houdini via Synapse, return result."""
    from synapse_ws import SynapseClient
    async with SynapseClient(port=port) as client:
        result = await client.execute_python(code, timeout=timeout)
        return result

async def run_file_in_houdini(filepath: str, port: int = 9999, timeout: int = 30):
    """Read a Python file and execute it inside Houdini."""
    with open(filepath, 'r') as f:
        code = f.read()
    return await run_in_houdini(code, port, timeout)

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('command_file', help='Python file to execute in Houdini')
    parser.add_argument('--port', type=int, default=9999)
    parser.add_argument('--timeout', type=int, default=30)
    args = parser.parse_args()
    
    result = asyncio.run(run_file_in_houdini(args.command_file, args.port, args.timeout))
    print(json.dumps(result, indent=2, default=str))
```

### `synapse_check.py` — Health check
```python
"""Quick Synapse health check"""
import asyncio, sys
sys.path.insert(0, r'C:\Users\User\.synapse\agent')

async def check():
    from synapse_ws import SynapseClient
    try:
        async with SynapseClient(port=9999) as c:
            r = await c.execute_python("import hou; print(hou.applicationVersionString())", timeout=5)
            print(f"✓ Houdini connected: {r}")
            return True
    except Exception as e:
        print(f"✗ Synapse down: {e}")
        return False

asyncio.run(check())
```

---

## CURRENT PROJECT STATE (60% complete)

### What's Done ✓
- [x] Amendment A spec complete (8 files, 941 lines)
- [x] wolfram_oracle.py written
- [x] 4 upgrade scripts: validate_optics, fit_squeeze_breathing, fit_pupil_shift, calibrate_biomechanics
- [x] Updated protocols.py with PupilShiftFit
- [x] Updated biomechanics.py with derive_biomechanics_calibrated()
- [x] All Wolfram dependencies installed in Houdini Python
- [x] `import wolframalpha` works in Houdini
- [x] Synapse server starts on port 9999
- [x] W4 (pupil shift fitting) PASSES
- [x] jaraco/context indentation fixed in both locations
- [x] fit_squeeze_breathing.py dict key fix applied

### What's Blocking ✗
- [ ] **asyncio conflict**: wolframalpha.Client.query() calls asyncio.run() internally
  - Houdini's HoudiniEventLoop blocks asyncio.run()
  - nest_asyncio can't patch HoudiniEventLoop
  - **FIX NEEDED**: Monkey-patch wolframalpha.Client.query to use ThreadPoolExecutor + asyncio.new_event_loop()
  - The patch is IN wolfram_oracle.py but references nest_asyncio.py which must be DELETED
  - DELETE: C:\Users\User\houdini21.0\scripts\python\nest_asyncio.py (and all .pyc)
  - Current wolfram_oracle.py has the ThreadPoolExecutor patch already applied

### What's Remaining
- [ ] **Phase W1**: validate_optics — needs asyncio fix
- [ ] **Phase W2-W3**: fit_squeeze_breathing — needs asyncio fix  
- [ ] **Phase W5**: calibrate_biomechanics — needs asyncio fix
- [ ] **Phase W6**: VEX header generation (depends on W2-W3)
- [ ] **Step 3**: Build lens_distortion HDA via Synapse
- [ ] **Step 4**: Build focus_breathing HDA via Synapse
- [ ] **Step 5**: Build biomechanics HDA via Synapse
- [ ] **Step 6**: Build lens_shader HDA via Synapse
- [ ] **Step 7**: Build orchestrator cinema::camera_rig::2.0 HDA
- [ ] **Step 8**: Integration test with animated focus pull

---

## IMMEDIATE EXECUTION PLAN

### Phase 1: Fix asyncio (ENV Agent + CODE Agent)
```
1. Delete nest_asyncio.py and all cached .pyc from HOUDINI_PREFS
2. Verify wolfram_oracle.py has ThreadPoolExecutor patch (not nest_asyncio)
3. Restart Houdini (taskkill + relaunch)
4. Start Synapse on port 9999
5. Run synapse_check.py to verify connection
```

### Phase 2: Execute W1-W6 (TEST Agent)
```
6. Run W1 validate_optics via Synapse
7. Run W2-W3 fit_squeeze_breathing via Synapse
8. Run W5 calibrate_biomechanics via Synapse
9. Verify W6 VEX header generated
10. Collect all results, verify all PASS
```

### Phase 3: Build HDAs (BUILD Agent)
```
11. Create cinema::lens_distortion::2.0 HDA
12. Create cinema::focus_breathing::2.0 HDA
13. Create cinema::biomechanics::2.0 HDA  
14. Create cinema::lens_shader::2.0 HDA
15. Wire VEX includes, set parameter defaults from Wolfram results
```

### Phase 4: Orchestrator + Integration (BUILD Agent + USD Agent)
```
16. Create cinema::camera_rig::2.0 top-level HDA
17. Wire sub-HDAs into orchestrator
18. Create test scene with animated focus pull
19. Verify Karma XPU renders correctly
20. Final validation
```

---

## KEY FILE MANIFEST

### Source Files (OneDrive — edit here first)
```
C:\Users\User\OneDrive\Documents\houdini21.0\
├── cinema_camera\
│   ├── README.md
│   ├── CINEMA_CAMERA_RIG_v4_PHYSICAL_ARCHITECTURE.md
│   ├── CINEMA_CAMERA_RIG_v4_SYNAPSE_REFACTOR.md
│   ├── CINEMA_CAMERA_RIG_v4_AMENDMENT_A_WOLFRAM.md
│   ├── lenses\
│   │   ├── cooke_ana_i_s35_50mm.json
│   │   ├── cooke_ana_i_s35_300mm.json
│   │   └── _schema_v4.json
│   └── tests\
├── scripts\python\cinema_camera\
│   ├── __init__.py
│   ├── protocols.py
│   ├── biomechanics.py
│   ├── wolfram_oracle.py
│   ├── wolfram_upgrades\
│   │   ├── __init__.py
│   │   ├── validate_optics.py
│   │   ├── fit_squeeze_breathing.py
│   │   ├── fit_pupil_shift.py
│   │   └── calibrate_biomechanics.py
│   ├── karma_lens_shader.py
│   ├── usd_builder.py
│   ├── registry.py
│   └── synapse_preflight.py
├── run_wolfram_check.py
└── run_steps_8_10.py
```

### Houdini Runtime (auto-loaded — sync copies here)
```
C:\Users\User\houdini21.0\
├── otls\                              ← HDAs go here
├── vex\include\                       ← VEX headers
├── scripts\python\cinema_camera\      ← Mirror of OneDrive source
├── scripts\python\wolframalpha\       ← Wolfram package
├── scripts\python\httpx\              ← HTTP client
├── scripts\python\httpcore\           ← HTTP transport
├── scripts\python\jaraco\             ← jaraco utilities (PATCHED)
├── scripts\python\xmltodict.py        ← XML parser
├── packages\
│   ├── cinema_camera_rig.json         ← env vars (WOLFRAM_APP_ID)
│   └── Synapse\python\synapse\        ← Synapse bridge
└── [NO nest_asyncio.py — DELETED]
```

---

## KNOWN GOTCHAS

1. **Dual-path sync**: Every edit must go to BOTH OneDrive and houdini21.0
2. **Module caching**: Houdini caches Python imports for process lifetime — restart required after file changes
3. **Port conflicts**: Old Houdini processes hold port 9999 — taskkill before restart
4. **asyncio.run()**: NEVER use inside Houdini — use ThreadPoolExecutor + new_event_loop
5. **nest_asyncio**: MUST NOT EXIST in houdini21.0/scripts/python/ — it poisons HoudiniEventLoop
6. **.pyc files**: Python 3.14 .pyc files incompatible with Houdini's Python 3.11 — delete on sight
7. **OneDrive locking**: Can lock files during sync — retry or use local path
8. **CMD paste**: User sometimes pastes markdown into CMD — only raw commands work
9. **jaraco/context**: Line 18-22 must have correct indentation for try/except/import tarfile

---

## WOLFRAM ORACLE asyncio PATCH (Current state in wolfram_oracle.py)

The monkey-patch that SHOULD be at the top of wolfram_oracle.py (after `from __future__ import annotations`):

```python
from __future__ import annotations

import asyncio, concurrent.futures

def _patch_wolframalpha():
    try:
        import wolframalpha as _wa
        _orig = _wa.Client.query
        def _sync_query(self, input, params=None, **kwargs):
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None
            if loop and loop.is_running():
                def _run_in_new_loop(coro):
                    loop = asyncio.new_event_loop()
                    try:
                        return loop.run_until_complete(coro)
                    finally:
                        loop.close()
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    fut = pool.submit(_run_in_new_loop, self.aquery(input, params, **kwargs))
                    return fut.result(timeout=30)
            return _orig(self, input, params, **kwargs)
        _wa.Client.query = _sync_query
    except ImportError:
        pass

_patch_wolframalpha()

"""
Cinema Camera Rig v4.0 — Wolfram Alpha Oracle
...rest of file...
"""
```

---

## AGENT TEAM WORKFLOW PROTOCOL

### Error Routing Table

| Error Type | Route To | Action |
|---|---|---|
| ImportError / ModuleNotFoundError | ENV Agent | Install/copy dependency |
| SyntaxError / IndentationError | CODE Agent | Fix source, sync both paths |
| asyncio / event loop conflict | CODE Agent | ThreadPoolExecutor pattern |
| SynapseConnectionError | ENV Agent | Check port, restart Houdini |
| Wolfram API timeout | TEST Agent | Retry with longer timeout |
| HDA build failure | BUILD Agent | Debug node network |
| USD composition error | USD Agent | Check LIVRPS, layer stack |
| .pyc incompatibility | ENV Agent | Delete __pycache__ dirs |
| Port in use | ENV Agent | netstat → taskkill → retry |

### Validation Gates

Each phase has a gate. Don't proceed until gate passes.

| Gate | Condition | Verify Via |
|---|---|---|
| G1: Environment | `import wolframalpha` succeeds in Houdini | Synapse execute |
| G2: Asyncio | Wolfram query returns result (not error) | W1 passes |
| G3: All Wolfram | W1-W6 all return success: True | run_wolfram_check.py |
| G4: HDAs Built | 4 HDAs exist in otls/ | hou.hda.loadedFiles() |
| G5: Orchestrator | camera_rig::2.0 creates without error | Synapse execute |
| G6: Integration | Animated focus pull renders in Karma | Visual check |

---

## QUICK START (Copy-paste into Claude Code)

```bash
# 1. Verify Synapse is up
python synapse_check.py

# 2. If down, user must start Houdini and run in Python shell:
#    from synapse.server import SynapseServer; s = SynapseServer(port=9999); s.start()

# 3. Delete nest_asyncio poison
del "C:\Users\User\houdini21.0\scripts\python\nest_asyncio.py" 2>nul
del /S /Q "C:\Users\User\houdini21.0\scripts\python\__pycache__\nest_asyncio*" 2>nul

# 4. Run Wolfram check
python "C:\Users\User\OneDrive\Documents\houdini21.0\run_wolfram_check.py"

# 5. If all pass, proceed to HDA build phase
python synapse_runner.py build_hdas.py
```
