import bpy, sys
from mathutils import Vector
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=sys.argv[-1])
sc = bpy.context.scene
dg = bpy.context.evaluated_depsgraph_get()
def mn(ob, fi):
    try:
        return ob.data.materials[ob.data.polygons[fi].material_index].name
    except Exception:
        return "?"
print("== BLACK PANEL (west from x=-3 upstairs) ==")
for y in (0.0, 0.8, 1.6, 2.4, 3.2):
    ok, loc, n2, fi, ob, mw = sc.ray_cast(dg, Vector((-3.0, y, 5.1)), Vector((-1, 0, 0)), distance=9.0)
    print(f"  y={y}", f"x={loc.x:.2f} {ob.name} {mn(ob,fi)[:40]}" if ok else "MISS")
print("== NE-wall upstairs (east from x=3) ==")
for y in (0.0, 1.5, 3.0):
    ok, loc, n2, fi, ob, mw = sc.ray_cast(dg, Vector((3.0, y, 5.1)), Vector((1, 0, 0)), distance=9.0)
    print(f"  y={y}", f"x={loc.x:.2f} {ob.name} {mn(ob,fi)[:40]}" if ok else "MISS")
print("== FIREPLACES ==")
for org, d in ((( -9.5, 4.0, 0.6), (-1, 0, 0)), ((8.0, -3.95, 1.2), (1, 0, 0))):
    ok, loc, n2, fi, ob, mw = sc.ray_cast(dg, Vector(org), Vector(d), distance=3.0)
    print(" ", f"{ob.name} {mn(ob,fi)[:44]} at ({loc.x:.1f},{loc.y:.1f},{loc.z:.1f})" if ok else "MISS")
print("== HEIGHTS (down-rays) ==")
for x, y, zc in ((4.0,6.5,1.5),(5.5,6.5,1.5),(8.7,6.0,1.5),(-8.5,1.5,6.0),(-8.5,1.5,3.0),(0.6,0.2,1.6),(6.9,-8.3,5.6),(-8.6,4.85,5.2)):
    ok, loc, n2, fi, ob, mw = sc.ray_cast(dg, Vector((x, y, zc)), Vector((0, 0, -1)), distance=zc+0.4)
    print(f"  ({x},{y}) from z{zc}:", f"z={loc.z:.2f} {mn(ob,fi)[:40]}" if ok else "MISS")
print("MINIDONE")
