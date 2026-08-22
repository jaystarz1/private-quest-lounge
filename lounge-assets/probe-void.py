# Void probe: where can a user WALK (NavMesh) into space that has no real
# build around it? Prints ASCII occupancy maps for the ground + upper storeys
# with an enclosure classification per cell, plus perimeter door-gap scans.
# Usage: blender -b --factory-startup -P probe-void.py -- <final.glb>
import bpy, sys
from mathutils import Vector

src = sys.argv[-1]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=src)
sc = bpy.context.scene
dg = bpy.context.evaluated_depsgraph_get()

nav = bpy.data.objects.get('NavMesh')
if not nav:
    print("NO NAVMESH"); sys.exit(0)

def matname(ob, fi):
    try:
        me = ob.data
        mi = me.polygons[fi].material_index
        return me.materials[mi].name if me.materials and me.materials[mi] else "?"
    except Exception:
        return "?"

# ray that ignores the NavMesh and backdrop planes
def cast(origin, d, dist, skip_views=False):
    o = Vector(origin)
    dv = Vector(d)
    for _ in range(6):
        ok, loc, nrm, fi, ob, mw = sc.ray_cast(dg, o + dv * 0.01, dv, distance=dist)
        if not ok:
            return None
        if ob.name == 'NavMesh' or (skip_views and (ob.name.startswith('View') or ob.name == 'RockiesView')):
            used = (loc - o).length + 0.01
            dist -= used
            o = loc
            continue
        return (loc, ob, fi)
    return None

# occupancy from navmesh face centers
mw = nav.matrix_world
cells = {}  # (band, i, j) -> True
for p in nav.data.polygons:
    c = mw @ p.center
    band = 'G' if c.z < 2.0 else 'U'
    i = int((c.x + 11.5) / 0.5)
    j = int((c.y + 9.8) / 0.5)
    cells.setdefault((band, i, j), []).append(c)

DIRS8 = [(1,0),(0,1),(-1,0),(0,-1),(0.707,0.707),(-0.707,0.707),(0.707,-0.707),(-0.707,-0.707)]
def classify(c):
    # what floor is under this walkable cell?
    down = cast((c.x, c.y, c.z + 0.6), (0, 0, -1), 1.4)
    fmat = matname(down[1], down[2]) if down else "NOFLOOR"
    up = cast((c.x, c.y, c.z + 0.4), (0, 0, 1), 7.0, skip_views=True)
    walls = 0
    for dx, dy in DIRS8:
        h = cast((c.x, c.y, c.z + 1.3), (dx, dy, 0), 4.0, skip_views=True)
        if h:
            walls += 1
    return fmat, up is not None, walls

sus = {}
for band in ('G', 'U'):
    print(f"===== MAP {band} (top=+y north, left=-x west) =====")
    rows = []
    for j in range(40, -1, -1):
        row = []
        for i in range(0, 47):
            key = (band, i, j)
            if key not in cells:
                row.append(' ')
                continue
            c = cells[key][0]
            fmat, ceil, walls = classify(c)
            dark = ('noir' in fmat) or fmat == 'NOFLOOR'
            if dark and not ceil and walls <= 2:
                ch = 'X'   # walkable, black/absent floor, open, unwalled = VOID
            elif dark:
                ch = 'x'   # black floor but somewhat enclosed
            elif not ceil and walls <= 2:
                ch = 'o'   # open-air but real floor (terrace)
            else:
                ch = '.'
            row.append(ch)
            if ch in 'Xx':
                sus.setdefault(band, []).append((round(c.x, 1), round(c.y, 1), fmat[:34], ceil, walls))
        rows.append(''.join(row))
    for j, r in zip(range(40, -1, -1), rows):
        print(f"y={-9.8 + j * 0.5:5.1f} |{r}|")
    print("        " + "x=-11.5" + " " * 30 + "x=+11.5")

for band, pts in sus.items():
    print(f"===== SUSPECT CELLS {band}: {len(pts)} =====")
    # cluster crudely by proximity
    for p in pts[:80]:
        print("  ", p)

# Perimeter gap scan at standing height: from just inside each wall, cast out.
print("===== PERIMETER GAPS (no hit within 2.5 m at z=1.2 and z=2.0) =====")
def gapscan(label, fixed, axis, a1, a2, d):
    a = a1
    run = None
    while a <= a2:
        free_all = True
        for z in (1.2, 2.0):
            origin = (fixed, a, z) if axis == 'y' else (a, fixed, z)
            h = cast(origin, d, 2.5, skip_views=True)
            if h:
                free_all = False
                break
        if free_all:
            if run is None:
                run = a
        else:
            if run is not None and a - run > 0.3:
                print(f"  {label}: open {axis} {run:.2f}..{a:.2f}")
            run = None
        a += 0.15
    if run is not None and a2 - run > 0.3:
        print(f"  {label}: open {axis} {run:.2f}..{a2:.2f}")

gapscan("south wall", -8.0, 'x', -11.0, 11.0, (0, -1, 0))
gapscan("north wall", 8.6, 'x', -11.0, 11.0, (0, 1, 0))
gapscan("east wall", 10.0, 'y', -9.5, 9.5, (1, 0, 0))
gapscan("west wall", -10.0, 'y', -9.5, 9.5, (-1, 0, 0))
print("DONE")
