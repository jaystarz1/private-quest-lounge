# Seat-pad probe: dense down-ray scan in furniture regions, clustered into
# seat candidates with centre + top height. Plus ID rays for the upstairs
# black panel. Usage: blender -b --factory-startup -P probe-seats.py -- <in.glb>
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

def scan(label, x1, x2, y1, y2, zcast, zlo, zhi, step=0.1):
    pts = []
    xi = x1
    while xi <= x2:
        yi = y1
        while yi <= y2:
            ok, loc, nrm, fi, ob, mw = sc.ray_cast(dg, Vector((xi, yi, zcast)), Vector((0, 0, -1)), distance=zcast - zlo + 0.05)
            if ok and zlo < loc.z < zhi and nrm.z > 0.6:
                pts.append((xi, yi, loc.z, matname(ob, fi)))
            yi += step
        xi += step
    # greedy cluster by 0.42 m radius
    clusters = []
    for x, y, z, mn in pts:
        for c in clusters:
            if abs(c[0] / c[3] - x) < 0.42 and abs(c[1] / c[3] - y) < 0.42:
                c[0] += x; c[1] += y; c[2] = max(c[2], z); c[3] += 1
                break
        else:
            clusters.append([x, y, z, 1, mn])
    print(f"== {label} ==")
    for c in sorted(clusters, key=lambda c: -c[3]):
        if c[3] >= 3:
            print(f"  seat ({c[0]/c[3]:6.2f},{c[1]/c[3]:6.2f}) top={c[2]:4.2f} n={c[3]:3d} {c[4][:40]}")

scan("qing-dining", 7.6, 11.4, 4.4, 7.8, 1.1, 0.35, 0.60)
scan("outdoor-dining", 2.4, 7.0, 5.2, 8.8, 1.1, 0.33, 0.60)
scan("patio-sofa", -3.9, -0.7, 5.2, 8.4, 1.2, 0.42, 0.80)
scan("piano-bench", -10.4, -6.8, -3.2, 0.8, 1.0, 0.32, 0.62)
scan("round-daybed", -1.6, 2.0, -0.9, 2.4, 1.2, 0.30, 0.60)
scan("lounge-ottoman", -10.3, -8.6, 3.9, 5.4, 1.0, 0.28, 0.55)
scan("library", -5.6, -1.8, -7.2, -3.3, 1.1, 0.32, 0.62)
scan("bed-NW", -10.6, -6.8, 5.2, 9.2, 5.6, 3.85, 4.45, step=0.15)
scan("bed-NE", 7.4, 11.2, 4.8, 9.2, 5.6, 3.85, 4.45, step=0.15)
scan("bed-SW", -10.6, -7.2, -5.6, -2.4, 5.6, 3.85, 4.45, step=0.15)
scan("nook-chair", -9.6, -7.4, -3.4, -1.2, 5.3, 3.75, 4.25)
scan("beanbag-NW", -9.6, -7.6, 4.2, 5.6, 5.3, 3.7, 4.2)
scan("egg-chair-SE", 5.8, 8.4, -9.4, -7.2, 5.6, 3.8, 4.5)
scan("gym-bench", -3.6, 0.8, -7.6, -3.6, 5.2, 3.7, 4.2)

print("== BLACK PANEL rays (upstairs west wall) ==")
for y in (0.5, 1.0, 1.5, 2.0, 2.5, 3.0):
    ok, loc, nrm, fi, ob, mw = sc.ray_cast(dg, Vector((-3.0, y, 5.0)), Vector((-1, 0, 0)), distance=3.0)
    if ok:
        print(f"  y={y} hit x={loc.x:5.2f} {ob.name[:20]} {matname(ob, fi)[:44]}")
print("== FIREPLACE check (lounge west wall) ==")
ok, loc, nrm, fi, ob, mw = sc.ray_cast(dg, Vector((-9.5, 4.0, 0.6)), Vector((-1, 0, 0)), distance=2.0)
if ok:
    print(f"  hit x={loc.x:5.2f} {ob.name[:20]} {matname(ob, fi)[:44]}")
print("DONE")
