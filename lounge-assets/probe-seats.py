# Reports what geometry sits under each Seat_* empty and where nearby bed-size
# meshes actually are, to catch seat markers floating off the furniture.
# Usage: blender -b --factory-startup -P probe-seats.py -- <model.glb>
import bpy, sys
from mathutils import Vector

src = sys.argv[-1]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=src)
sc = bpy.context.scene
dg = bpy.context.evaluated_depsgraph_get()

seats = [o for o in sc.collection.all_objects if o.name.startswith("Seat_")]
print("=== SEAT DROP PROBES (cast down from seat + 0.6) ===")
for o in sorted(seats, key=lambda x: x.name):
    p = o.location
    hit, loc, _, _, obidx, _ = sc.ray_cast(dg, Vector((p.x, p.y, p.z + 0.6)), Vector((0, 0, -1)), distance=8.0)
    under = "NOTHING"
    if hit:
        ob = obidx.name if obidx else "?"
        under = f"{ob} at z={loc.z:.2f}"
    print(f"{o.name:16s} pos=({p.x:6.2f},{p.y:6.2f},{p.z:5.2f}) under: {under}")

print("\n=== UPPER-FLOOR MESH BOUNDING BOXES near bedrooms (z 3.4..4.6) ===")
for ob in sc.collection.all_objects:
    if ob.type != 'MESH':
        continue
    mw = ob.matrix_world
    bb = [mw @ Vector(c) for c in ob.bound_box]
    xs = [v.x for v in bb]; ys = [v.y for v in bb]; zs = [v.z for v in bb]
    # bed-ish: sizeable footprint whose top surface lands in the mattress band
    if max(zs) < 3.4 or min(zs) > 4.6:
        continue
    w = max(xs) - min(xs); d = max(ys) - min(ys)
    if w < 0.8 or d < 0.8 or w > 8 or d > 8:
        continue
    print(f"{ob.name:20s} x[{min(xs):6.2f},{max(xs):6.2f}] y[{min(ys):6.2f},{max(ys):6.2f}] ztop={max(zs):5.2f}")
