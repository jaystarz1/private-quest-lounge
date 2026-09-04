# Grid-scans each bedroom from above and prints the surface height map so the
# mattress rectangle (flat area z~3.9-4.3) can be located exactly.
# Usage: blender -b --factory-startup -P probe-mattress.py -- <model.glb>
import bpy, sys
from mathutils import Vector

src = sys.argv[-1]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=src)
sc = bpy.context.scene
dg = bpy.context.evaluated_depsgraph_get()

ROOMS = {
  "NW": (-11.0, -6.0, 4.5, 9.5),
  "NE": (6.5, 11.0, 4.0, 9.5),
  "SW": (-11.0, -6.0, -6.0, -1.5),
}
STEP = 0.25
for room, (x1, x2, y1, y2) in ROOMS.items():
    print(f"=== {room} height map (rows south->north, '.'=floor, '#'=mattress 3.85-4.35, '+'=mid, 'X'=tall) ===")
    y = y1
    rows = []
    while y <= y2:
        row = ""
        x = x1
        while x <= x2:
            hit, loc, _, _, ob, _ = sc.ray_cast(dg, Vector((x, y, 6.2)), Vector((0, 0, -1)), distance=3.5)
            if not hit:
                row += " "
            else:
                z = loc.z
                if z < 3.6: row += "."
                elif z < 3.85: row += "-"
                elif z <= 4.35: row += "#"
                elif z <= 5.0: row += "+"
                else: row += "X"
            x += STEP
        rows.append((y, row))
        y += STEP
    for y, row in reversed(rows):
        print(f"y={y:6.2f} {row}")
    print(f"        x from {x1} to {x2} step {STEP}")
