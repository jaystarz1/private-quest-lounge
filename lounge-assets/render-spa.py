import bpy, sys, os
from mathutils import Vector
src, dest = sys.argv[-2:]
os.makedirs(dest, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=src)
sc=bpy.context.scene
sc.render.engine='CYCLES'
sc.cycles.samples=8
sc.render.resolution_x=1200
sc.render.resolution_y=800
sc.render.resolution_percentage=100
sc.world=bpy.data.worlds.new('ReviewWorld')
sc.world.use_nodes=True
sc.world.node_tree.nodes['Background'].inputs['Color'].default_value=(.65,.7,.8,1)
sc.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.8
for o in sc.objects:
    if o.name.startswith(('NavMesh','View','Sky','Seat','Spawn')): o.hide_render=True
bpy.ops.object.light_add(type='AREA', location=(-6,-8,7))
bpy.context.object.data.energy=1800
bpy.context.object.data.shape='DISK'
bpy.context.object.data.size=8
for pos in ((2,-8.5,5.8),(2.6,-8.5,2.5)):
    bpy.ops.object.light_add(type='POINT', location=pos)
    bpy.context.object.data.energy=100
    bpy.context.object.data.shadow_soft_size=.5
bpy.ops.object.camera_add()
cam=bpy.context.object
sc.camera=cam
cam.data.lens=22
for name, pos, target in [
    ('entry',(-2.3,-8.2,1.7),(-8.3,-7.5,1.0)),
    ('tub',(-10.1,-6.45,1.35),(-5.8,-8.1,1.2)),
    ('pocket',(-7.9,-5.7,1.7),(-6.0,-8.2,1.2)),
    ('lounge',(-7.9,-8.7,1.65),(-4.2,-8.8,1.2))]:
    cam.location=pos
    cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler()
    sc.render.filepath=dest+'/'+name+'.png'
    bpy.ops.render.render(write_still=True)
