# Precise geometry probe of the south band + corner slabs + upstairs deck.
# Usage: blender -b --factory-startup -P probe-south.py -- <final.glb>
import bpy, sys
from mathutils import Vector

src = sys.argv[-1]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=src)
sc = bpy.context.scene
dg = bpy.context.evaluated_depsgraph_get()

def matname(ob, fi):
    try:
        me = ob.data
        mi = me.polygons[fi].material_index
        return me.materials[mi].name if me.materials and me.materials[mi] else "?"
    except Exception:
        return "?"

def cast(origin, d, dist):
    o = Vector(origin); dv = Vector(d)
    for _ in range(8):
        ok, loc, nrm, fi, ob, mw = sc.ray_cast(dg, o + dv * 0.01, dv, distance=dist)
        if not ok:
            return None
        if ob.name == 'NavMesh' or ob.name.startswith('View') or ob.name == 'RockiesView':
            dist -= (loc - o).length + 0.01
            o = loc
            continue
        return (loc, ob, fi, matname(ob, fi))
    return None

print("== A. Floor extent map, ground level (z window -0.3..0.5), 0.5 m grid ==")
print("   symbols: '.' herringbone/wood  'c' concrete/gray  'n' noir  '?' other  ' ' none")
def floorch(x, y):
    h = cast((x, y, 2.6), (0, 0, -1), 3.2)
    if not h or h[0].z > 0.5:
        return ' ', None
    m = h[3]
    if 'noir' in m:
        return 'n', m
    if m.startswith(('moquette', 'parquet', 'bois')):
        return '.', m
    return ('c', m)
mats_seen = {}
for j in range(int((11.2 - 4.0) / 0.5) + 1):
    y = -4.0 - j * 0.5
    row = []
    for i in range(int(26 / 0.5) + 1):
        x = -13.0 + i * 0.5
        ch, m = floorch(x, y)
        row.append(ch)
        if m:
            mats_seen.setdefault(m, 0)
            mats_seen[m] += 1
    print(f"y={y:6.1f} |{''.join(row)}|")
print("   x from -13.0 to +13.0")
for m, n in sorted(mats_seen.items(), key=lambda kv: -kv[1]):
    print(f"   floor mat {n:5d}  {m[:60]}")

print("== B. South band cross-sections (walls crossing y -7.8..-10.6 at z=1.3) ==")
for x in [-10.5, -9.0, -7.6, -6.0, -4.5, -3.0, -1.5, -0.5, 0.5, 1.5, 2.5, 3.5, 4.5, 5.5, 6.5, 7.5, 8.5, 10.0]:
    hits = []
    yy = -7.6
    while yy > -10.8:
        h = cast((x, yy, 1.3), (0, -1, 0), 0.6)
        if h and abs(h[0].y - yy) < 0.55:
            hits.append((round(h[0].y, 2), h[3][:30]))
            yy = h[0].y - 0.15
        else:
            yy -= 0.4
    ceil = cast((x, -9.3, 0.4), (0, 0, 1), 8)
    cz = round(ceil[0].z, 2) if ceil else None
    cm = ceil[3][:24] if ceil else '-'
    print(f"  x={x:6.1f} ceil@-9.3={cz} ({cm})  walls:{hits}")

print("== C. Parapet: down-cast top heights along y=-9.6..-10.4 ==")
for x in [-10.5, -8.0, -5.0, -2.0, 0.0, 2.0, 4.0, 6.0, 8.0, 10.5]:
    tops = []
    for y in (-9.6, -9.8, -10.0, -10.2, -10.4):
        h = cast((x, y, 2.4), (0, 0, -1), 3.0)
        tops.append(round(h[0].z, 2) if h else None)
    print(f"  x={x:6.1f} tops y-9.6..-10.4: {tops}")

print("== D. West/east flank of corner slabs: wall x-positions at z=1.3 ==")
for y in [-5.0, -6.0, -7.0, -8.0, -9.0]:
    hw = cast((-9.5, y, 1.3), (-1, 0, 0), 4.0)
    he = cast((9.5, y, 1.3), (1, 0, 0), 4.0)
    print(f"  y={y:5.1f} westwall:{(round(hw[0].x,2), hw[3][:24]) if hw else None}  eastwall:{(round(he[0].x,2), he[3][:24]) if he else None}")

print("== E. Building south face: north-cast from y=-9.0 at z=1.3/3.0 (where is the apartment wall?) ==")
for x in [-10.8, -10.0, -9.2, -8.4, -7.6, -6.8, -6.0, -5.2, -4.4, -3.6, -2.8, -2.0, -1.2, -0.4, 0.4, 1.2, 2.0, 2.8, 3.6, 4.4, 5.2, 6.0, 6.8, 7.6, 8.4, 9.2, 10.0, 10.8]:
    r = []
    for z in (1.3, 3.0):
        h = cast((x, -9.55, z), (0, 1, 0), 3.5)
        r.append((round(h[0].y, 2), h[3][:20]) if h else None)
    print(f"  x={x:6.1f} z1.3:{r[0]}  z3.0:{r[1]}")

print("== F. Upstairs deck: floor z in 3.1..3.9 over x -4..8, y -10.4..-7.2 ==")
for j in range(int((10.4 - 7.2) / 0.4) + 1):
    y = -7.2 - j * 0.4
    row = []
    for i in range(int(12 / 0.4) + 1):
        x = -4.0 + i * 0.4
        h = cast((x, y, 5.6), (0, 0, -1), 2.6)
        if not h:
            row.append(' ')
        else:
            z = h[0].z
            if 3.1 < z < 3.9:
                row.append('n' if 'noir' in h[3] else '.')
            else:
                row.append(' ')
    print(f"y={y:6.1f} |{''.join(row)}|")
print("   x from -4.0 to +8.0 step 0.4")
print("== G. Upstairs deck surroundings at (0.0,-8.8,z=5.0): 8 rays ==")
for d, nm in [((1,0,0),'E'), ((-1,0,0),'W'), ((0,1,0),'N'), ((0,-1,0),'S')]:
    h = cast((0.0, -8.8, 5.0), d, 12)
    print(f"  {nm}: {(round((h[0]-Vector((0,-8.8,5.0))).length,2), h[1].name[:20], h[3][:26]) if h else 'OPEN'}")
h = cast((0.0, -8.8, 4.1), (0, 0, 1), 10)
print(f"  UP: {(round(h[0].z,2), h[3][:26]) if h else 'OPEN'}")
print("== H. Vestibule interior: what is at x -0.5..2.5, y -7.8..-9.6 (floor/ceiling/walls) ==")
for x in (0.0, 0.8, 1.6, 2.4):
    for y in (-8.2, -8.8, -9.4):
        f = cast((x, y, 2.0), (0, 0, -1), 2.4)
        c = cast((x, y, 1.6), (0, 0, 1), 6)
        print(f"  ({x},{y}) floor:{(round(f[0].z,2), f[3][:22]) if f else None} ceil:{(round(c[0].z,2), c[3][:22]) if c else None}")
print("DONE")
