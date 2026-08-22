import bpy, sys
from mathutils import Vector
src = sys.argv[-1]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=src)
sc = bpy.context.scene
dg = bpy.context.evaluated_depsgraph_get()
def matname(ob, fi):
    try:
        me = ob.data; mi = me.polygons[fi].material_index
        return me.materials[mi].name if me.materials and me.materials[mi] else "?"
    except Exception:
        return "?"
def ray(label, ox, oy, oz, tx, ty, tz, hops=3):
    o = Vector((ox, oy, oz)); d = (Vector((tx, ty, tz)) - o).normalized()
    for h in range(hops):
        ok, loc, nrm, fi, ob, mw = sc.ray_cast(dg, o + d * 0.02, d, distance=12)
        if not ok:
            print(f"{label} {h} OPEN"); return
        print(f"{label} {h} ({loc.x:5.2f},{loc.y:5.2f},{loc.z:4.2f}) {ob.name[:26]} :: {matname(ob,fi)[:40]}")
        o = loc
print("-- lobby doorway contents (from v13 cam) --")
ray("grid", -6.9, -7.0, 1.5, -4.8, -6.3, 1.5)
ray("art ", -6.9, -7.0, 1.5, -4.3, -6.2, 1.8)
ray("wallN2", -6.9, -7.0, 1.5, -2.5, -6.45, 1.5)
ray("darkpanelN1", -6.9, -7.0, 1.5, -6.8, -6.5, 1.9, hops=1)
print("-- deck gray patches: straight down --")
for x, y in ((9.0, -6.5), (9.8, -7.8), (5.5, -8.5), (4.0, -8.8), (-9.0, -6.0), (-10.0, -8.5)):
    o = Vector((x, y, 2.0)); d = Vector((0, 0, -1))
    for h in range(4):
        ok, loc, nrm, fi, ob, mw = sc.ray_cast(dg, o + d * 0.005, d, distance=3)
        if not ok: break
        mn = matname(ob, fi)
        print(f"down({x},{y}) {h} z={loc.z:5.3f} {ob.name[:24]} :: {mn[:36]}")
        if ob.name == 'NavMesh':
            o = loc; continue
        break
print("-- black pillar SE --")
ray("pillar", 10.9, -5.1, 1.6, 7.6, -5.8, 2.5)
ray("pillar2", 10.9, -5.1, 1.6, 7.4, -6.2, 4.5)
ray("blackTop", 10.9, -5.1, 1.6, 7.8, -6.6, 5.5)
print("DONE")
