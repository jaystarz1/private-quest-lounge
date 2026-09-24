"""Blender geometry regression gate. Usage: blender -b -P verify-cafe.py -- scene.glb"""
import bpy
import sys
from mathutils import Vector
from mathutils.bvhtree import BVHTree

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=sys.argv[-1])
vertices, faces = [], []
for ob in bpy.context.scene.objects:
    if ob.type != 'MESH' or ob.name.startswith(('NavMesh', 'View', 'Sky', 'Seat', 'Spawn')):
        continue
    base = len(vertices)
    vertices.extend(ob.matrix_world @ v.co for v in ob.data.vertices)
    faces.extend(tuple(base + i for i in face.vertices) for face in ob.data.polygons)
tree = BVHTree.FromPolygons(vertices, faces)
checks = 0
def clear(origin, direction, distance, label):
    global checks
    hit = tree.ray_cast(Vector(origin), Vector(direction), distance)[0]
    assert hit is None, f'{label}: blocked at {hit}'
    checks += 1

# Check every layer, both directions, not just the exterior face of the hatch.
for x in (8.3, 8.8, 9.45, 10.0, 10.5):
    for z in (1.3, 1.8, 2.4):
        clear((x,-4.65,z),(0,1,0),1.63,'hatch into kitchen')
        clear((x,-3.02,z),(0,-1,0),1.63,'hatch onto patio')
for x in (8.5,9.45,10.4):
    hit = tree.ray_cast(Vector((x,-4.6,1.5)),Vector((0,0,-1)),.5)[0]
    assert hit is not None and abs(hit.z-1.14)<.005, f'counter height: {hit}'
    checks += 1
for x,y in ((6.5,-5.9),(7.2,-5.9),(8,-5.9),(8.7,-5.9),(7,-7),(8,-8.8),(5,-8)):
    hit = tree.ray_cast(Vector((x,y,2)),Vector((0,0,-1)),2)[0]
    assert hit is not None and abs(hit.z-.10)<.006, f'walkway obstruction/height at {(x,y)}: {hit}'
    checks += 1
for i,y in enumerate((-6.55,-8.05),1):
    ob=bpy.data.objects[f'Seat_E{i}']
    assert abs(ob.matrix_world.translation.z-.50)<.03, 'seat anchor height changed'
    hit=tree.ray_cast(Vector((9.5,y,.65)),Vector((0,0,-1)),.3)[0]
    assert hit is not None and abs(hit.z-.50)<.01, f'chair seat missing: {hit}'
    checks += 1
# Full human-height opening, independently raycast through the exported mesh.
for x in (6.65,7.12,7.58):
    for z in (.3,.9,1.6,2.3):
        clear((x,-5.7,z),(0,1,0),3.0,'cafe door to kitchen')
        clear((x,-2.7,z),(0,-1,0),3.0,'cafe door to terrace')
# Kitchen worktop must remain exposed below the separate serving ledge.
for x in (8.5,9.45,10.4):
    hit=tree.ray_cast(Vector((x,-3.9,1.5)),Vector((0,0,-1)),1.0)[0]
    assert hit is not None and .85 < hit.z < 1.08, f'worktop covered by serving counter: {hit}'
    checks += 1
nav=bpy.data.objects['NavMesh']
nv=[nav.matrix_world@v.co for v in nav.data.vertices]
nt=BVHTree.FromPolygons(nv,[tuple(f.vertices) for f in nav.data.polygons])
for y in (-5.5,-5.0,-4.5,-4.0,-3.5,-3.0,-2.75):
    hit=nt.ray_cast(Vector((7.12,y,.5)),Vector((0,0,-1)),.6)[0]
    assert hit is not None, f'cafe door navmesh gap at {y}'
    checks += 1
for name in ('Art_Paris1946','Art_Paris1948','CafeTablecloth','CafeRoseVase','CafeRoseBouquet'):
    assert bpy.data.objects.get(name), f'missing finish: {name}'
    checks += 1
wave=bpy.data.objects['Art_Wave']
assert wave.matrix_world.translation.y < -9.5, 'Japanese painting still outside cafe'
planter=bpy.data.objects['LedgeE1']
for corner in planter.bound_box:
    c=planter.matrix_world@Vector(corner)
    assert -.62 < c.x < 3.68 and -9.68 < c.y < -7.1, f'planter protrudes from den: {c}'
checks += 2
# The moved pot must clear furniture, not just fit inside the room bounds.
import math
pv,pf=[],[]
for ob in bpy.context.scene.objects:
    if ob.type!='MESH' or ob.name.startswith(('NavMesh','View','Sky','Seat','Spawn','LedgeE1','DenPlanter')):
        continue
    base=len(pv)
    pv.extend(ob.matrix_world@v.co for v in ob.data.vertices)
    pf.extend(tuple(base+i for i in f.vertices) for f in ob.data.polygons)
pt=BVHTree.FromPolygons(pv,pf)
for k in range(24):
    a=math.tau*k/24
    x,y=3.4+.16*math.cos(a),-9.36+.16*math.sin(a)
    hit=pt.ray_cast(Vector((x,y,4.4)),Vector((0,0,-1)),1.0)[0]
    assert hit is not None and hit.z<3.56, f'planter intersects furniture: {hit}'
    checks+=1
print(f'CAFE GEOMETRY GATE: {checks} checks passed')
