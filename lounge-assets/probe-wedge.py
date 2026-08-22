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
cam = Vector((-6.9, -7.0, 1.5))
for name, tgt in [("A", (-5.0, -7.6, 2.2)), ("B", (-4.5, -7.8, 1.5)), ("C", (-4.2, -8.0, 0.8)),
                  ("D", (-5.5, -7.4, 2.6)), ("E", (-3.8, -8.3, 1.2)), ("F", (-5.8, -7.2, 1.8))]:
    d = (Vector(tgt) - cam).normalized()
    o = cam
    for hop in range(4):
        ok, loc, nrm, fi, ob, mw = sc.ray_cast(dg, o + d * 0.02, d, distance=8)
        if not ok:
            print(name, hop, "OPEN"); break
        mn = matname(ob, fi)
        print(f"{name} {hop} hit ({loc.x:5.2f},{loc.y:5.2f},{loc.z:4.2f}) {ob.name[:24]} :: {mn[:44]}")
        if 'noir' in mn or 'Nav' not in ob.name and hop >= 0:
            break
print("DONE")
