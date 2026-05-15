"""
Diagnostic: enumerate Copernicus 2.0 + Karma post-processing node types that
this Houdini build actually registers.

Use cases:
  * Confirming Copernicus 2.0 is enabled and discoverable from this Python env.
  * Cross-checking the cop node types referenced by the v2 satellite builders
    (cinema::flare / sensor_noise / stmap_aov) against what Houdini exposes.
  * Pre-flight check before running build_all_v3() on a new machine.

Paste in Houdini's Python shell:
    exec(open(r"C:\\Users\\User\\Houdini_Camera_Rig_System\\scripts\\probe_copernicus.py").read())

The script is read-only except for a /obj/__probe_copnet_parent scratch geo
that is created and destroyed in a single try/finally block. If you abort
mid-run, you may need to delete that geo manually.
"""

import hou


def _ok(s):  print(f"  [OK]   {s}")
def _miss(s): print(f"  [MISS] {s}")


print("=" * 64)
print("Copernicus 2.0 + Karma post-processing diagnostic")
print(f"Houdini: {hou.applicationVersionString()}")
print("=" * 64)

# ── 1. Categories ───────────────────────────────────────────────
print("\n[1] Available node categories")
for cat_name in ("Cop", "Cop2", "Lop", "Object", "Sop"):
    try:
        cat = getattr(hou, cat_name[0].lower() + cat_name[1:] + "NodeTypeCategory")()
        n = len(cat.nodeTypes())
        print(f"  {cat.name():30s}  {n} types")
    except Exception as e:
        print(f"  {cat_name:30s}  -- {e}")

# ── 2. COP container types (where do you create copnets?) ────────
print("\n[2] COP/Copernicus network container types")
for parent_cat_name in ("Object", "Sop", "Lop", "Manager"):
    try:
        cat = getattr(hou, parent_cat_name[0].lower() + parent_cat_name[1:] + "NodeTypeCategory")()
        for name in sorted(cat.nodeTypes().keys()):
            if "cop" in name.lower() and ("net" in name.lower() or "network" in name.lower()):
                _ok(f"{parent_cat_name}: {name}")
    except Exception:
        pass

# ── 3. Copernicus node types that might be useful for cinema post ──
print("\n[3] Copernicus 2.0 (cop) node types -- post-processing relevant")
try:
    cop_cat = hou.copNodeTypeCategory()
    types = sorted(cop_cat.nodeTypes().keys())
    print(f"  total cop types: {len(types)}")
    keywords = (
        "null", "snippet", "vop", "vex", "noise", "blur", "convolve",
        "threshold", "filter", "gen", "image", "file", "output", "streak",
        "add", "mix", "comp", "input", "math", "color", "warp", "fft",
        "karma", "render", "copy", "expression", "constant", "transform",
    )
    matches = []
    for name in types:
        lower = name.lower()
        for kw in keywords:
            if kw in lower:
                matches.append(name)
                break
    for name in matches:
        _ok(f"cop: {name}")
    if not matches:
        _miss("no cop node types matched -- Copernicus may not be enabled or named differently")
except Exception as e:
    _miss(f"hou.copNodeTypeCategory() failed: {e}")

# ── 4. Legacy COP2 types (existing builders use these) ─────────
print("\n[4] Legacy cop2 node types -- for reference")
try:
    cop2_cat = hou.cop2NodeTypeCategory()
    types = sorted(cop2_cat.nodeTypes().keys())
    print(f"  total cop2 types: {len(types)} (just the count)")
except Exception as e:
    _miss(f"cop2 not available: {e}")

# ── 5. Karma-related LOP types (output processor / post hooks) ──
print("\n[5] Karma + COP-related LOP types")
try:
    lop_cat = hou.lopNodeTypeCategory()
    for name in sorted(lop_cat.nodeTypes().keys()):
        lower = name.lower()
        if "karma" in lower or ("cop" in lower and "py" not in lower):
            _ok(f"lop: {name}")
except Exception as e:
    _miss(f"lop enumeration failed: {e}")

# ── 6. Try creating a copnet to confirm context works end-to-end ──
print("\n[6] Smoke test: create a copnet and list its createable children")
obj = hou.node("/obj")
# Pre-clean any leftover from an earlier aborted run
_leftover = obj.node("__probe_copnet_parent")
if _leftover:
    try:
        _leftover.destroy()
    except Exception:
        pass

test_parent = None
try:
    test_parent = obj.createNode("geo", "__probe_copnet_parent")
    cn = None
    for try_name in ("copnet", "cop2net"):
        try:
            cn = test_parent.createNode(try_name, "_test")
            _ok(f"created via {try_name}: {cn.type().name()}")
            child_types = sorted(cn.childTypeCategory().nodeTypes().keys())
            _ok(f"  children category: {cn.childTypeCategory().name()}")
            _ok(f"  children types ({len(child_types)} total) -- showing first 30:")
            for n in child_types[:30]:
                print(f"    {n}")
            break
        except Exception:
            pass
    if cn is None:
        _miss("could not create either copnet or cop2net at /obj level")
except Exception as e:
    _miss(f"smoke test failed: {e}")
finally:
    # Always clean up the scratch geo, even if exploration raised mid-way.
    if test_parent is not None:
        try:
            test_parent.destroy()
        except Exception:
            pass

print()
print("=" * 64)
print("Diagnostic complete.")
print("=" * 64)
