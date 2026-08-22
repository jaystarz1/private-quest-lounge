# Reports every exported face remaining in the former piano volume.
# Usage: blender -b --factory-startup -P probe-piano.py -- <lounge.glb>
import bpy, sys

src = sys.argv[-1]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=src)

hits = {}
for ob in bpy.context.scene.objects:
    if ob.type != 'MESH':
        continue
    names = [mat.name if mat else '?' for mat in ob.data.materials]
    mw = ob.matrix_world
    for poly in ob.data.polygons:
        points = [mw @ ob.data.vertices[index].co for index in poly.vertices]
        center = mw @ poly.center
        if -9.4 < center.x < -4.8 and -4.1 < center.y < -1.8 and 0.055 < center.z < 3.4:
            key = (ob.name, names[poly.material_index])
            data = hits.setdefault(key, [0, 1e9, 1e9, 1e9, -1e9, -1e9, -1e9])
            data[0] += 1
            for point in points:
                data[1] = min(data[1], point.x); data[2] = min(data[2], point.y); data[3] = min(data[3], point.z)
                data[4] = max(data[4], point.x); data[5] = max(data[5], point.y); data[6] = max(data[6], point.z)

for (object_name, material_name), data in sorted(hits.items(), key=lambda item: -item[1][0]):
    print(f"REMAIN {data[0]:5d} {object_name}:{material_name} bbox={tuple(round(v, 3) for v in data[1:])}")
