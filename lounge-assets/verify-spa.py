"""Raycast the exported spa, including walkable mesh and seated sightlines."""
import bpy, sys, math
from mathutils import Vector
from mathutils.bvhtree import BVHTree
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=sys.argv[-1])
sc=bpy.context.scene
def bvh(objects):
    v,f=[],[]
    for ob in objects:
        base=len(v)
        v.extend(ob.matrix_world@p.co for p in ob.data.vertices)
        f.extend(tuple(base+i for i in p.vertices) for p in ob.data.polygons)
    return BVHTree.FromPolygons(v,f)
tree=bvh([ob for ob in sc.objects if ob.type=='MESH' and not ob.name.startswith(('NavMesh','View','Sky','Seat','Spawn'))])
nav=bvh([bpy.data.objects['NavMesh']])
checks=0
def check(test,label):
    global checks
    assert test,label
    checks+=1
def clear(a,b,label):
    d=Vector(b)-Vector(a)
    check(tree.ray_cast(Vector(a),d.normalized(),d.length)[0] is None,label)

check(not any(ob.name.startswith(('Lift','LobbyWallW','LobbyWallN1','LobbyDoorHead','Art_WestWind')) for ob in sc.objects),'fake lift or partition remains')
# Former west partition, including both old door jambs and the north pocket.
for y in (-9.35,-8.7,-8.0,-7.3,-6.7):
    for z in (.3,.9,1.7,2.3):
        clear((-7.82,y,z),(-7.35,y,z),f'west wall at {y,z}')
for x in (-7.35,-6.85,-6.35,-5.8):
    for z in (.3,1.0,1.7,2.3):
        clear((x,-6.9,z),(x,-6.2,z),f'pocket opening at {x,z}')
# Walk the shared aisle from the vestibule to the pool, then up to the piano.
route=[(x,-7.35) for x in (-1.7,-2.2,-3,-4,-5,-6,-7,-7.6)]
route += [(-7.5,y) for y in (-7.1,-6.7,-6.4,-6.0,-5.6)]
for x,y in route:
    hit=tree.ray_cast(Vector((x,y,2.3)),Vector((0,0,-1)),2.5)[0]
    check(hit is not None and abs(hit.z-.1)<.012,f'floor/headroom at {x,y}: {hit}')
    hit=nav.ray_cast(Vector((x,y,.4)),Vector((0,0,-1)),.6)[0]
    check(hit is not None,f'nav gap at {x,y}')
for name in ('Seat_Spa_W','Seat_Spa_E'):
    ob=bpy.data.objects[name]
    p=ob.matrix_world.translation
    check(abs(p.z-.54)<.01,f'seat height {name}')
    hit=tree.ray_cast(p+Vector((0,0,.12)),Vector((0,0,-1)),.2)[0]
    check(hit is not None and abs(hit.z-p.z)<.012,f'seat lacks cushion {name}')
    front=ob.matrix_world.to_quaternion()@Vector((0,-1,0))
    other=bpy.data.objects['Seat_Spa_E' if name.endswith('W') else 'Seat_Spa_W'].matrix_world.translation
    check(front.dot((other-p).normalized())>.99,f'chairs face away {name}')
    clear(p+Vector((0,0,.75)),other+Vector((0,0,.75)),'seated eye-to-eye sightline')
for name in ('SpaChairW','SpaChairE','SpaTableTop','SpaAwning','SpaSignCapri','SpaAperolGlass0','SpaAperolGlass1'):
    check(name in bpy.data.objects,f'missing furnishing {name}')
# Sign must face into the room (+Y), not show mirrored lettering from its back.
ob=bpy.data.objects['SpaSignCapri']
check((ob.matrix_world.to_quaternion()@Vector((0,0,1))).y>.99,'sign faces wall')
print(f'SPA PASS: {checks} checks')
