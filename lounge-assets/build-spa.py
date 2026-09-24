# Executed by build-penthouse.py after architectural cuts, before seat/nav bake.
# Dimensions are Blender world metres; no additional image textures required.
M_SPA_CREAM = mk('SpaLimewash', 'F1E9D7', .94)
M_SPA_BLUE = mk('SpaCapriBlue', '24619B', .73)
M_SPA_LINEN = mk('SpaIvoryLinen', 'FFF3DB', .98)
M_SPA_WOOD = mk('SpaHoneyTeak', 'AA784B', .69)
M_SPA_SAND = mk('SpaWovenSand', 'C6AE81', 1.0)
M_SPA_LEMON = mk('SpaLemon', 'F7CE46', .6)
M_SPA_CLAY = mk('SpaTerracotta', 'BF7251', .9)
M_SPA_GLASS = mk('SpaAperolGlass', 'E6F0F8', .24)
M_SPA_APEROL = mk('SpaAperol', 'E7A84E', .5)

# Replace the mismatched enclosure finishes with one plaster treatment.
for nm in ('LobbyWallS', 'LobbyWallN2', 'LobbyCeil'):
    ob = bpy.data.objects[nm]
    ob.data.materials.clear()
    ob.data.materials.append(M_SPA_CREAM)
for nm in ('LobbyBaseS', 'LobbyBaseN'):
    ob = bpy.data.objects[nm]
    ob.data.materials.clear()
    ob.data.materials.append(M_SPA_BLUE)
recolor_region(-5.65, -5.25, -6.7, -5.0, .1, 3.24, 'F1E9D7', rough=.94,
               label='SpaPocketLimewash', only_mats={'BrickWall'})
retex_region(-1.35, -1.05, -9.75, -6.6, .1, 2.95, M_SPA_CREAM,
             'SpaEntryPlaster', only_objects=('Object_',), normal=(-1,0,0))
# Finish the entire remaining north wall, including its newly exposed end.
add_box('SpaNorthEnd', -5.51, -6.57, 1.48, .018, .035, 1.38, M_SPA_CREAM)
# Equal floor height across the removed partition; no hidden step or trench.
tex_box('SpaFloor', -4.52, -8.18, .07, 3.20, 1.58, .03, M_TRAV, scale=1.3)
tex_box('SpaPocketFloor', -6.62, -5.90, .07, 1.10, .70, .03, M_TRAV, scale=1.3)
tex_box('SpaDeckFloor', -9.57, -7.48, .07, 1.85, 2.28, .03, M_TRAV, scale=1.3)
# Remove coincident old floor sheets. They otherwise shimmer in a headset.
for nm in ('DeckSW', 'DeckSWpocket'):
    bpy.data.objects.remove(bpy.data.objects[nm], do_unlink=True)

def spa_box(name, location, halfsize, material, bevel=0):
    add_box(name, *location, *halfsize, material)
    ob = bpy.context.object
    if bevel:
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        mod=ob.modifiers.new('Soft edges', 'BEVEL')
        mod.width=bevel
        mod.segments=3
        bpy.ops.object.modifier_apply(modifier=mod.name)
        ob.modifiers.new('Weighted corner normals', 'WEIGHTED_NORMAL')
    return ob

def spa_cylinder(name, x,y,z,r,depth,mat):
    bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=r, depth=depth, location=(x,y,z))
    ob=bpy.context.object
    ob.name=name
    ob.data.materials.append(mat)
    return ob

# Low, generous lounge chairs. The local front is -Y, matching Hubs seats.
# Back and foot cushions give a reclined silhouette while the hip pad remains
# horizontal for a seated avatar. Rotation also applies to the striped panels.
def spa_chair(name, cx, cy, yaw):
    before=set(sc.objects)
    spa_box(name+'Seat', (0,0,.465), (.43,.39,.075), M_SPA_LINEN, .055)
    spa_box(name+'Frame', (0,0,.35), (.47,.43,.045), M_SPA_WOOD, .025)
    back=spa_box(name+'Back', (0,.40,.79), (.43,.075,.35), M_SPA_LINEN, .06)
    back.rotation_euler.x=math.radians(-16)
    for ix in range(5):
        x=-.34+ix*.17
        spa_box(name+f'StripeSeat{ix}', (x,-.015,.542), (.035,.32,.002), M_SPA_BLUE)
        strip=spa_box(name+f'StripeBack{ix}', (x,.322,.812), (.035,.002,.285), M_SPA_BLUE)
        strip.rotation_euler.x=math.radians(-16)
    for x in (-.49,.49):
        spa_box(name+'Arm', (x,0,.67), (.045,.44,.04), M_SPA_WOOD, .025)
        for y in (-.28,.28):
            spa_box(name+'Leg', (x,y,.34), (.033,.04,.24), M_SPA_WOOD, .012)
    spa_box(name+'FootFrame', (0,-.70,.29), (.39,.23,.035), M_SPA_WOOD, .025)
    spa_box(name+'FootCushion', (0,-.70,.365), (.37,.22,.045), M_SPA_BLUE, .035)
    for x in (-.31,.31):
        spa_box(name+'FootLeg', (x,-.72,.19), (.03,.16,.09), M_SPA_WOOD, .01)
    bpy.context.view_layer.update()
    from mathutils import Matrix
    rot=Matrix.Rotation(math.radians(yaw),4,'Z')
    transform=Matrix.Translation((cx,cy,0)) @ rot
    for ob in set(sc.objects)-before:
        ob.matrix_world=transform @ ob.matrix_world

spa_box('SpaRugBorder', (-4.65,-8.6,.108), (2.28,.83,.007), M_SPA_BLUE, .04)
spa_box('SpaRug', (-4.65,-8.6,.117), (2.23,.78,.003), M_SPA_SAND, .03)
spa_chair('SpaChairW', -6.15,-8.60,90)
spa_chair('SpaChairE', -3.15,-8.60,-90)

# Woven linen, blue twill and teak grain on the chairs: the flat colours made
# cushion, stripe and frame hard to tell apart in the headset.
CAPRI_CHAIRS = (-7.3, -2.0, -9.6, -7.6, 0.0, 1.4)
for file_name, mat_name, rough, src, scale in (
        ('linen-ivory.png', 'SpaLinenWeave', .95, 'SpaIvoryLinen', .25),
        ('canvas-capri-blue.png', 'SpaBlueCanvas', .85, 'SpaCapriBlue', .25),
        ('teak-grain.png', 'SpaTeakGrain', .6, 'SpaHoneyTeak', 1.0)):
    retex_region(*CAPRI_CHAIRS, artmat(file_name, mat_name, rough), 'Capri' + mat_name,
                 only_objects=('SpaChairW', 'SpaChairE'), only_mats={src}, scale=scale)

# Small ceramic drinks table. Clear eye-to-eye sightline above the low top.
spa_cylinder('SpaTableBase',-4.65,-8.60,.14,.28,.06,M_SPA_BLUE)
spa_cylinder('SpaTableStem',-4.65,-8.60,.34,.075,.38,M_SPA_BLUE)
spa_cylinder('SpaTableRim',-4.65,-8.60,.565,.41,.045,M_SPA_BLUE)
spa_cylinder('SpaTableTop',-4.65,-8.60,.590,.375,.01,M_SPA_LINEN)
for i,(x,y) in enumerate(((-4.65,-8.83),(-4.65,-8.37))):
    spa_cylinder(f'SpaAperolGlass{i}',x,y,.66,.045,.12,M_SPA_GLASS)
    spa_cylinder(f'SpaAperol{i}',x,y+.005,.70,.038,.09,M_SPA_APEROL)
    for j in range(3):
        bpy.ops.mesh.primitive_uv_sphere_add(
            segments=14,
            ring_count=7,
            radius=.008,
            location=(x-0.008+j*.008, y+.011, .72)
        )
        ob=bpy.context.object
        ob.name=f'SpaAperolSlice{i}_{j}'
        ob.scale=(1.2,.8,.25)
        ob.data.materials.append(M_SPA_LEMON)
        ob.rotation_euler.x=math.radians(80)
    rim=spa_cylinder(f'SpaAperolRim{i}',x,y,.72,.047,.006,M_SPA_CLAY)
    rim.rotation_euler.x=math.radians(90)
spa_cylinder('SpaFruitPlate',-4.65,-8.60,.606,.11,.018,M_SPA_BLUE)
for i,(x,y) in enumerate(((-4.69,-8.59),(-4.62,-8.62))):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=12, ring_count=6, radius=.04, location=(x,y,.65))
    ob=bpy.context.object
    ob.name=f'SpaTableLemon{i}'
    ob.scale=(1.3,.8,.8)
    ob.data.materials.append(M_SPA_LEMON)

# Blue-and-ivory awning over the open edge, high above the walking route.
# Scallops are shallow half-discs in the same mesh, not dangling obstacles.
for i in range(16):
    y=-9.66+(i+.5)*.19
    mat=M_SPA_BLUE if i%2==0 else M_SPA_LINEN
    spa_box(f'SpaAwning{i}',(-7.17,y,2.86),(.53,.095,.018),mat)
    spa_box(f'SpaValance{i}',(-7.70,y,2.76),(.018,.095,.10),mat)
    verts=[(-7.72,y,2.66)]
    verts += [(-7.72,y+.095*math.cos(math.pi*j/12),2.66-.095*math.sin(math.pi*j/12)) for j in range(13)]
    me=bpy.data.meshes.new('Scallop')
    me.from_pydata(verts,[],[(0,j,j+1) for j in range(1,13)])
    me.materials.append(mat)
    ob=bpy.data.objects.new(f'SpaScallop{i}',me)
    sc.collection.objects.link(ob)

# The old steel door wall becomes a quiet club sign with a ceramic blue frame.
spa_box('SpaSignFrame',(-4.65,-9.67,1.94),(1.03,.025,.43),M_SPA_BLUE,.055)
spa_box('SpaSignFace',(-4.65,-9.638,1.94),(.98,.012,.38),M_SPA_LINEN,.04)
def spa_text(name, body, x,z,size):
    bpy.ops.object.text_add(location=(x,-9.619,z),rotation=(math.pi/2,0,math.pi))
    ob=bpy.context.object
    ob.name=name
    ob.data.body=body
    ob.data.align_x='CENTER'
    ob.data.size=size
    ob.data.extrude=.0007
    ob.data.materials.append(M_SPA_BLUE)
    bpy.ops.object.convert(target='MESH')
spa_text('SpaSignCapri','C A P R I',-4.65,1.94,.29)
spa_text('SpaSignClub','B A G N O   P R I V A T O',-4.65,1.72,.095)
plant('SpaPlantEast',-1.85,-9.25,.10,1.1,.8)
spa_cylinder('SpaTowelBasket',-7.03,-9.29,.29,.23,.38,M_SPA_SAND)
for i in range(3):
    ob=spa_cylinder(f'SpaRolledTowel{i}',-7.03+(i-1)*.12,-9.29,.54,.062,.29,M_SPA_LINEN)
    ob.rotation_euler.x=math.pi/2

# Tub skin uses glazed blue; warm travertine coping and clear water stay.
for nm in ('HotTubWallN','HotTubWallS','HotTubWallW','HotTubWallENE','HotTubWallESE'):
    ob=bpy.data.objects[nm]
    ob.data.materials.clear()
    ob.data.materials.append(M_SPA_BLUE)
ob=bpy.data.objects['HotTubStepOuter']
ob.data.materials.clear()
ob.data.materials.append(M_SPA_CREAM)
# Consolidate decorative parts; chairs stay separate for seat verification.
join_objects('SpaAwning',('SpaAwning','SpaValance','SpaScallop'))
join_objects('SpaChairW',('SpaChairW',))
join_objects('SpaChairE',('SpaChairE',))
