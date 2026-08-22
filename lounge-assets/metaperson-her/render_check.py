import bpy, math
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath="avatar-her-real.glb")
cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
bpy.context.scene.collection.objects.link(cam)
cam.location = (0, -1.6, 1.35); cam.rotation_euler = (math.radians(87), 0, 0)
bpy.context.scene.camera = cam
sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN"))
bpy.context.scene.collection.objects.link(sun); sun.rotation_euler = (math.radians(45), 0, math.radians(20))
sun.data.energy = 4
s = bpy.context.scene
s.render.engine = "BLENDER_EEVEE"
s.render.resolution_x = 512; s.render.resolution_y = 640
s.render.filepath = "/tmp/jay-avatar-front.png"
bpy.ops.render.render(write_still=True)
cam.location = (1.4, -1.0, 1.35); cam.rotation_euler = (math.radians(87), 0, math.radians(54))
s.render.filepath = "/tmp/jay-avatar-side.png"
bpy.ops.render.render(write_still=True)
