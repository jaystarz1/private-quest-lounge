# Converts penthouse-src.glb (Sketchfab "Luxury Penthouse", CC BY-NC-SA) into
# the Hubs-ready lounge environment: recentres the main floor onto the origin,
# decimates to a Quest-2 triangle budget, raycasts a walkable-grid NavMesh,
# and adds the Hubs anchor nodes (spawns, seats, TV/monitor screens, view
# backdrop). MOZ_hubs_components are injected afterwards by inject-hubs.mjs.
#
# Usage: blender -b --factory-startup -P build-penthouse.py -- <src.glb> <out.glb> <bake/day-pano.jpg>
import bpy, bmesh, sys, math, os
from mathutils import Vector

src, out, viewimg = sys.argv[-3], sys.argv[-2], sys.argv[-1]
SHIFT = Vector((-8.1, -1.0, -3.99))  # main floor -> z 0, apartment centred

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=src)
sc = bpy.context.scene

# --- Recentre: move every root object ---------------------------------------
for o in sc.collection.all_objects:
    if o.parent is None:
        o.location = o.location + SHIFT
bpy.context.view_layer.update()

# --- Remove the baked Rotterdam mural, backdrop card, and source piano --------
# Object_24 is a 22 m photo wall just inside the north glass (it hid our
# switchable view plane); Object_25 is a photo lying flat outside.
# Object_108 is the complete grand-piano case. Deleting the mesh as a unit
# avoids leaving long lid triangles whose centres fall outside a region box.
for name in ("Object_24", "Object_25", "Object_108"):
    ob = bpy.data.objects.get(name)
    if ob:
        bpy.data.objects.remove(ob, do_unlink=True)
bpy.context.view_layer.update()

# The mural hid a solid brick wall enclosing the patio/kitchen north face.
# Cut that band out (x -5.6..6.2 only — the lounge keeps its real glass wall)
# so the terrace opens onto the switchable skyline plane.
def region_delete(x1, x2, y1, y2, z1, z2):
    total = 0
    for ob in [o for o in sc.collection.all_objects if o.type == 'MESH']:
        mw = ob.matrix_world
        bmr = bmesh.new()
        bmr.from_mesh(ob.data)
        doomed = []
        for f in bmr.faces:
            c = mw @ f.calc_center_median()
            if x1 < c.x < x2 and y1 < c.y < y2 and z1 < c.z < z2:
                doomed.append(f)
        if doomed:
            bmesh.ops.delete(bmr, geom=doomed, context='FACES')
            bmr.to_mesh(ob.data)
            total += len(doomed)
        bmr.free()
    bpy.context.view_layer.update()
    print(f"REGION-DELETE ({x1},{y1})..({x2},{y2}): {total} faces")

region_delete(-5.6, 6.2, 9.68, 10.12, -0.3, 10.6)

def region_delete_mats(x1, x2, y1, y2, z1, z2, mats, label):
    total = 0
    for ob in [o for o in sc.collection.all_objects if o.type == 'MESH']:
        idx = {i for i, m in enumerate(ob.data.materials) if m and m.name in mats}
        if not idx:
            continue
        mw = ob.matrix_world
        bmr = bmesh.new()
        bmr.from_mesh(ob.data)
        doomed = []
        for f in bmr.faces:
            c = mw @ f.calc_center_median()
            if f.material_index in idx and x1 < c.x < x2 and y1 < c.y < y2 and z1 < c.z < z2:
                doomed.append(f)
        if doomed:
            bmesh.ops.delete(bmr, geom=doomed, context='FACES')
            bmr.to_mesh(ob.data)
            total += len(doomed)
        bmr.free()
    bpy.context.view_layer.update()
    print(f"REGION-DELETE-MATS {label}: {total} faces")

# --- Delete the two mannequin silhouettes (patio + front door) ---------------
# Down-cast a small disc around each figure; every hit face seeds a linked-
# island delete. Islands capped so a connected wall can never be nuked.
def delete_figure(cx, cy):
    removed = 0
    for _ in range(15):
        dgf = bpy.context.evaluated_depsgraph_get()
        hit = None
        for dx in (-0.25, -0.1, 0, 0.1, 0.25):
            for dy in (-0.25, -0.1, 0, 0.1, 0.25):
                ok, loc, nrm, fi, ob, mw = sc.ray_cast(dgf, Vector((cx + dx, cy + dy, 1.95)), Vector((0, 0, -1)), distance=1.88)
                if ok and loc.z > 0.06:
                    hit = (ob, fi)
                    break
            if hit:
                break
        if not hit:
            break
        ob, fi = hit
        bmf = bmesh.new()
        bmf.from_mesh(ob.data)
        bmf.faces.ensure_lookup_table()
        if fi >= len(bmf.faces):
            bmf.free()
            break
        seed = bmf.faces[fi]
        stack, seen = [seed], {seed}
        while stack and len(seen) < 20000:
            f = stack.pop()
            for e in f.edges:
                for lf in e.link_faces:
                    if lf not in seen:
                        seen.add(lf)
                        stack.append(lf)
        if len(seen) >= 20000:
            print(f"FIGURE at ({cx},{cy}): island too big, skipped")
            bmf.free()
            break
        bmesh.ops.delete(bmf, geom=list(seen), context='FACES')
        bmf.to_mesh(ob.data)
        bmf.free()
        removed += len(seen)
        bpy.context.view_layer.update()
    print(f"FIGURE at ({cx},{cy}): removed {removed} faces")

delete_figure(2.5, 5.7)      # patio mannequin
delete_figure(-0.95, -7.75)  # front-door mannequin

# The mannequins' shoes are separate low islands the leg rays skim past:
# scan ankle height around each spot and delete only SMALL islands (<800
# faces), so chairs and furniture can never be caught.
def scrub_debris(x1, x2, y1, y2, cast_z=0.5, zmin=0.03, zmax=0.35):
    removed = 0
    skip = set()
    for _ in range(40):
        dgs = bpy.context.evaluated_depsgraph_get()
        hit = None
        xi = x1
        while xi < x2 and not hit:
            yi = y1
            while yi < y2 and not hit:
                ok, loc, nrm, fi, ob, mw = sc.ray_cast(dgs, Vector((xi, yi, cast_z)), Vector((0, 0, -1)), distance=cast_z - zmin + 0.01)
                if ok and zmin < loc.z < zmax and (ob.name, fi) not in skip:
                    hit = (ob, fi)
                yi += 0.06
            xi += 0.06
        if not hit:
            break
        ob, fi = hit
        bms = bmesh.new()
        bms.from_mesh(ob.data)
        bms.faces.ensure_lookup_table()
        if fi >= len(bms.faces):
            bms.free()
            break
        seed = bms.faces[fi]
        stack, seen = [seed], {seed}
        while stack and len(seen) < 800:
            f = stack.pop()
            for e in f.edges:
                for lf in e.link_faces:
                    if lf not in seen:
                        seen.add(lf)
                        stack.append(lf)
        if len(seen) >= 800:
            for f in seen:
                skip.add((ob.name, f.index))
            bms.free()
            continue
        bmesh.ops.delete(bms, geom=list(seen), context='FACES')
        bms.to_mesh(ob.data)
        bms.free()
        removed += len(seen)
        bpy.context.view_layer.update()
    print(f"DEBRIS ({x1},{y1}): removed {removed} faces")

scrub_debris(2.0, 3.6, 4.8, 6.3)     # patio shoes
scrub_debris(-1.6, -0.3, -8.4, -7.1) # front-door shoes, if any
scrub_debris(2.0, 3.8, 4.4, 6.3, cast_z=1.35, zmin=0.5, zmax=1.25)     # patio hands on chair backs
scrub_debris(-1.8, -0.2, -8.5, -7.0, cast_z=1.35, zmin=0.5, zmax=1.25) # front-door hands, if any

# --- Open the windows ---------------------------------------------------------
# The model ships every pane backed by CLOSED BLINDS (near-black rollers, beige
# panels) plus the building's black exterior shell — that is the "black
# windows" look. Ray-scan each perimeter wall from inside; wherever a
# sightline passes glass, delete blocker faces hugging that pane so the
# wrap-around skyline planes show through every window.
GLASS_MAT = 'fake_mat_255_255_255_32'
BLOCKER_MATS = {'fake_mat_6_5_5_255', 'noir_001_Wall_Entity_Material',
                'fake_mat_230_220_187_255', 'fake_mat_251_251_251_255'}
# Structural surfaces: a sightline that hits one of these first is a real wall,
# not a window — leave it alone.
SOLID_PREFIXES = ('blanc_001', 'enduit', 'beige_006', 'gris_00', 'bois_003',
                  'tex_', 'faience', 'papier', '20')

def clear_blocked_glass(origins, d, along_axis, a1, a2, z1=0.15, z2=6.25, astep=0.13, zstep=0.16):
    doomed = {}
    dgv = bpy.context.evaluated_depsgraph_get()
    dvec = Vector(d)
    a = a1
    while a <= a2:
        z = z1
        while z <= z2:
            for o0 in origins:
                origin = Vector((o0, a, z)) if along_axis == 'y' else Vector((a, o0, z))
                o = origin
                chain = []
                for _ in range(8):
                    left = 2.0 - (o - origin).length
                    if left <= 0:
                        break
                    ok, loc, nrm, fi, ob, mw = sc.ray_cast(dgv, o + dvec * 0.015, dvec, distance=left)
                    if not ok:
                        break
                    mats = ob.data.materials
                    mi = ob.data.polygons[fi].material_index if fi < len(ob.data.polygons) else 0
                    mnm = mats[mi].name if mats and len(mats) > mi and mats[mi] else ''
                    chain.append((ob, fi, mnm, (loc - origin).length))
                    o = loc
                if any(c[2] == GLASS_MAT for c in chain):
                    gd = min(c[3] for c in chain if c[2] == GLASS_MAT)
                    for ob, fi, mnm, dist in chain:
                        if mnm in BLOCKER_MATS and abs(dist - gd) < 0.75:
                            doomed.setdefault(ob.name, set()).add(fi)
                else:
                    # Glassless opening: blinds/sheers straight onto the black
                    # shell. If the sightline reaches the shell or a backdrop
                    # plane with no structural wall first, it is a window —
                    # clear every treatment layer in front of it.
                    shell_i = None
                    for i, (ob, fi, mnm, dist) in enumerate(chain):
                        if mnm.startswith(SOLID_PREFIXES) and mnm != 'noir_001_Wall_Entity_Material':
                            break
                        if mnm == 'noir_001_Wall_Entity_Material' or ob.name.startswith('View') or mnm == 'RockiesBackdrop':
                            shell_i = i
                            break
                    if shell_i is not None:
                        for ob, fi, mnm, dist in chain[:shell_i + 1]:
                            if mnm in BLOCKER_MATS:
                                doomed.setdefault(ob.name, set()).add(fi)
            z += zstep
        a += astep
    total = 0
    for obname, fis in doomed.items():
        ob = bpy.data.objects[obname]
        bmc = bmesh.new()
        bmc.from_mesh(ob.data)
        bmc.faces.ensure_lookup_table()
        gone = [bmc.faces[i] for i in fis if i < len(bmc.faces)]
        bmesh.ops.delete(bmc, geom=gone, context='FACES')
        bmc.to_mesh(ob.data)
        bmc.free()
        total += len(gone)
    bpy.context.view_layer.update()
    print(f"GLASS-CLEAR {along_axis}{d}: {total} blocker faces")

clear_blocked_glass((10.6, 11.05), (1, 0, 0), 'y', -9.6, 9.6)     # east wall
clear_blocked_glass((-10.55, -10.95), (-1, 0, 0), 'y', -9.6, 9.6)  # west wall
clear_blocked_glass((-8.95, -9.35), (0, -1, 0), 'x', -11.0, 11.3)  # south wall
clear_blocked_glass((8.95, 9.35), (0, 1, 0), 'x', -11.0, -5.7)     # north, west of patio
clear_blocked_glass((8.95, 9.35), (0, 1, 0), 'x', 6.3, 11.3)       # north, east of patio

# --- Deep stately palette: recolor the flat white/grey wall materials --------
def srgb(hexstr):
    v = [int(hexstr[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(c ** 2.2 for c in v) + (1.0,)

WALL_COLORS = {
    "blanc_001_Wall_Entity_Material": srgb("1E3255"),   # royal navy
    "enduit_004_Wall_Entity_Material": srgb("5C1F26"),  # oxblood
    "enduit_054": srgb("1E3255"),                       # navy (kitchen divider)
    "beige_006_Wall_Entity_Material": srgb("24463B"),   # hunter green
    "gris_004_Wall_Entity_Material": srgb("3B2A4F"),    # aubergine
    "gris_002_Wall_Entity_Material": srgb("23262B"),    # graphite
    "gris_006_Wall_Entity_Material": srgb("6E5423"),    # antique gold
    "fake_mat_251_251_251_255": srgb("A67C4A"),         # white round couch/rug -> camel
    "canape_015___mat_tissus095_bissg": srgb("8A4B2A"), # lounge sofa -> cognac
    "fake_mat_224_230_228_255": srgb("EFE4CD"),         # linens/curtains -> warm ivory
    "moquette_004_ovcol1c1c1ccolpic12contpic07": srgb("6E2B33"),  # lounge rug -> wine
    "fake_mat_104_101_99_255": srgb("3A2A1E"),          # stools/side pieces -> espresso
    "fake_mat_196_192_184_255": srgb("55603E"),         # patio bench/cushion greys -> olive
    "fake_mat_157_154_155_255": srgb("2F5D5A"),         # media sofa greys -> deep teal
    # Closed-blind rollers/valances (Object_69/70) were near-black boxes at
    # every window head and read as unfinished; finish them as espresso wood.
    "fake_mat_6_5_5_255": srgb("3A2A1E"),
}
for mname, col in WALL_COLORS.items():
    m = bpy.data.materials.get(mname)
    if not m:
        print("RECOLOR miss:", mname)
        continue
    if m.use_nodes and 'Principled BSDF' in m.node_tree.nodes:
        m.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = col
    else:
        m.diffuse_color = col

# --- Realistic foliage: per-island natural green variation ------------------
# Flat single-tone leaves read as plastic. Split every foliage mesh into
# connected face-islands (fronds/leaf clusters) and deal each island one of
# five muted living greens — mimics real leaf-age variation without textures.
# The bouquet gets a dried-floral palette instead of staying blue/white.
import zlib
FOLIAGE_MATS = {
    "pack_003_salon_plante___material__144",
    "pack_003_salon_plante___material__143",
    "pack_004_chambre_001_plante___nopaint_base",
    "fake_mat_51_142_39_255",
    "plante_vase_off_001___phong37",
}
FLORAL_MATS = {"vase_fleur_off___phong94"}

def jitter_islands(targets, palette, rough, label):
    pal = []
    for i, hexcol in enumerate(palette):
        nm = bpy.data.materials.new(f"{label}_{i}")
        nm.use_nodes = True
        b = nm.node_tree.nodes['Principled BSDF']
        b.inputs['Base Color'].default_value = srgb(hexcol)
        b.inputs['Roughness'].default_value = rough
        pal.append(nm)
    islands_total = 0
    for ob in [o for o in sc.collection.all_objects if o.type == 'MESH']:
        names = [m.name if m else '' for m in ob.data.materials]
        tset = {i for i, n in enumerate(names) if n in targets}
        if not tset:
            continue
        for nm in pal:
            if nm.name not in names:
                ob.data.materials.append(nm)
        names = [m.name if m else '' for m in ob.data.materials]
        pidx = [names.index(nm.name) for nm in pal]
        bmj = bmesh.new()
        bmj.from_mesh(ob.data)
        bmj.faces.ensure_lookup_table()
        seen = set()
        assign = {}
        for f in bmj.faces:
            if f.material_index not in tset or f in seen:
                continue
            stack, island = [f], [f]
            seen.add(f)
            while stack:
                g = stack.pop()
                for e in g.edges:
                    for lf in e.link_faces:
                        if lf not in seen and lf.material_index in tset:
                            seen.add(lf)
                            stack.append(lf)
                            island.append(lf)
            seed = (min(fc.index for fc in island) * 2654435761 + zlib.crc32(ob.name.encode())) & 0xffffffff
            mi = pidx[seed % len(pidx)]
            for fc in island:
                assign[fc.index] = mi
            islands_total += 1
        bmj.free()
        for fi2, mi in assign.items():
            ob.data.polygons[fi2].material_index = mi
    print(f"FOLIAGE {label}: {islands_total} islands")

jitter_islands(FOLIAGE_MATS, ["2F5233", "3E6B40", "566F3F", "6B8A4F", "42714A"], 0.65, "Foliage")
jitter_islands(FLORAL_MATS, ["EDE6D6", "C9B7A0", "8A9B7A", "9A7E85"], 0.7, "Floral")

# --- Fireplaces: the model textures them with POOL WATER (turquoise flames).
# Strip the texture and make the fire strip a warm glowing ember panel.
for fm in ("texture_eau_piscine", "texture_eau_piscine_ovcolffffffcolpic12contpic05"):
    m = bpy.data.materials.get(fm)
    if not m or not m.use_nodes:
        print("FIRE miss:", fm)
        continue
    bb = m.node_tree.nodes.get('Principled BSDF')
    if bb:
        for l in list(bb.inputs['Base Color'].links):
            m.node_tree.links.remove(l)
        bb.inputs['Base Color'].default_value = (0.05, 0.02, 0.01, 1)
        ec = bb.inputs.get('Emission Color')
        if ec:
            for l in list(ec.links):
                m.node_tree.links.remove(l)
            ec.default_value = (1.0, 0.35, 0.08, 1)
        es = bb.inputs.get('Emission Strength')
        if es:
            es.default_value = 1.0
        print("FIRE ember:", fm)

# Qing chairs in the upstairs hall: lacquer red if their color is flat.
qm = bpy.data.materials.get('qing_style_chair___qing_style_chairmaterial__28')
if qm and qm.use_nodes and 'Principled BSDF' in qm.node_tree.nodes:
    qb = qm.node_tree.nodes['Principled BSDF']
    if not qb.inputs['Base Color'].links:
        qb.inputs['Base Color'].default_value = srgb("8E1F1F")

# --- Region painter: split faces inside a box onto a new colored material ----
# (Material-level recolors bleed across the model's heavily shared materials —
# the piano turning the round couch black proved it. Paint by volume instead.)
def face_normal_ok(m3, p, normal):
    if normal is None:
        return True
    n = (m3 @ p.normal).normalized()
    if normal == 'up':
        return n.z > 0.7
    if normal == 'down':
        return n.z < -0.7
    if normal == 'side':
        return abs(n.z) < 0.5
    return n.dot(Vector(normal)) > 0.7

REGION_MATS = {}
def recolor_region(x1, x2, y1, y2, z1, z2, hexcol, rough=0.85, metal=0.0, label=None, only_mats=None, normal=None, min_area=0.0):
    key = (hexcol, rough, metal)
    nm = REGION_MATS.get(key)
    if nm is None:
        nm = bpy.data.materials.new(label or f"Styled_{hexcol}")
        nm.use_nodes = True
        b = nm.node_tree.nodes['Principled BSDF']
        b.inputs['Base Color'].default_value = srgb(hexcol)
        b.inputs['Roughness'].default_value = rough
        b.inputs['Metallic'].default_value = metal
        REGION_MATS[key] = nm
    total = 0
    for ob in [o for o in sc.collection.all_objects if o.type == 'MESH']:
        mw = ob.matrix_world
        names = [m.name if m else '' for m in ob.data.materials]
        # never repaint the styled foliage/floral islands
        okidx = {i for i, n in enumerate(names)
                 if not n.startswith(("Foliage_", "Floral_"))
                 and (only_mats is None or n in only_mats)}
        m3 = mw.to_3x3()
        sel = [p.index for p in ob.data.polygons
               if p.material_index in okidx
               and x1 < (mw @ p.center).x < x2 and y1 < (mw @ p.center).y < y2 and z1 < (mw @ p.center).z < z2
               and face_normal_ok(m3, p, normal) and p.area >= min_area]
        if not sel:
            continue
        if nm.name not in names:
            ob.data.materials.append(nm)
            names.append(nm.name)
        midx = names.index(nm.name)
        for pi in sel:
            ob.data.polygons[pi].material_index = midx
        total += len(sel)
    print(f"STYLE {label or hexcol}: {total} faces")

# The source piano is not salvageable at headset distance. Mark only its
# faces for removal and leave the floor, rug, walls and nearby art untouched.
def delete_linked_islands_in_region(object_name, x1, x2, y1, y2, z1, z2, label):
    ob = bpy.data.objects.get(object_name)
    if not ob or ob.type != 'MESH':
        raise RuntimeError(f"{label}: source mesh {object_name} missing")
    mesh = bmesh.new()
    mesh.from_mesh(ob.data)
    mesh.faces.ensure_lookup_table()
    remaining = set(mesh.faces)
    doomed = []
    islands = 0
    while remaining:
        seed = remaining.pop()
        island = {seed}
        stack = [seed]
        while stack:
            face = stack.pop()
            for edge in face.edges:
                for linked in edge.link_faces:
                    if linked in remaining:
                        remaining.remove(linked)
                        island.add(linked)
                        stack.append(linked)
        if any(x1 < (ob.matrix_world @ face.calc_center_median()).x < x2
               and y1 < (ob.matrix_world @ face.calc_center_median()).y < y2
               and z1 < (ob.matrix_world @ face.calc_center_median()).z < z2
               for face in island):
            doomed.extend(island)
            islands += 1
    if doomed:
        bmesh.ops.delete(mesh, geom=doomed, context='FACES')
        mesh.to_mesh(ob.data)
    mesh.free()
    bpy.context.view_layer.update()
    print(f"DELETE-ISLAND {label}: {islands} islands, {len(doomed)} faces")

# The keyboard/case accents live as disconnected islands inside Object_60,
# a mesh shared with unrelated furniture. A seed in the piano footprint
# removes each whole island, including long triangles outside the seed box.
delete_linked_islands_in_region("Object_60", -10.0, -7.0, -3.5, -2.0, 0.30, 2.50,
                                "piano-shared-mesh")
recolor_region(-10.4, -6.7, -2.8, 0.6, 0.055, 2.35, "0A0A0C", rough=0.16, label="PianoRemoval")

def add_box(name, x, y, z, sx, sy, sz, mat):
    bpy.ops.mesh.primitive_cube_add(location=(x, y, z))
    bx = bpy.context.active_object
    bx.name = name
    bx.scale = (sx, sy, sz)
    bx.data.materials.append(mat)

def delete_material_faces(material_names, label):
    total = 0
    for ob in [o for o in sc.collection.all_objects if o.type == 'MESH']:
        indices = {i for i, mat in enumerate(ob.data.materials) if mat and mat.name in material_names}
        if not indices:
            continue
        bm_del = bmesh.new()
        bm_del.from_mesh(ob.data)
        doomed = [face for face in bm_del.faces if face.material_index in indices]
        if doomed:
            total += len(doomed)
            bmesh.ops.delete(bm_del, geom=doomed, context='FACES')
            bm_del.to_mesh(ob.data)
        bm_del.free()
    bpy.context.view_layer.update()
    print(f"DELETE-MATERIAL {label}: {total} faces")
delete_material_faces({'PianoRemoval'}, 'entire-piano')
# Remove the remaining case and lid footprint. The source grand piano spans a
# second, offset volume that the original keyboard-only box did not cover.
region_delete(-9.4, -4.8, -4.1, -1.8, 0.055, 3.40)
region_delete(-10.4, -6.7, -2.8, 0.6, 2.30, 2.62)

# Bedrooms: crisp warm-ivory duvets on all three beds (only the duvet/linen
# material is repainted, so frames, throws and pillows keep their colors).
DUVET = {"fake_mat_251_251_251_255"}
recolor_region(-10.6, -8.4, 6.0, 8.6, 3.68, 4.24, "EFE4CD", rough=0.8, label="BedIvory", only_mats=DUVET)
recolor_region(7.6, 10.1, 5.2, 8.6, 3.68, 4.24, "EFE4CD", rough=0.8, label="BedIvory", only_mats=DUVET)
recolor_region(-10.0, -7.8, -5.1, -2.6, 3.68, 4.24, "EFE4CD", rough=0.8, label="BedIvory", only_mats=DUVET)
# NW bedroom: the black wall panel behind the headboard sits on a solid wall
# (not a window) — restyle it as a deep-teal upholstered headboard feature.
recolor_region(-10.99, -10.84, 5.7, 8.8, 4.25, 6.2, "2F5D5A", rough=0.85,
               label="HeadboardTeal", only_mats={'fake_mat_6_5_5_255'})

# --- West-wall coplanar shells ----------------------------------------------
# Every source material is doubleSided, so back faces pressed flat against a
# wall z-fight it in the headset (the strobing band above/behind the TV). The
# probes in probe-niche.py located each coincident pair; delete the hidden
# back-facing member of every pair, leaving the wall itself intact.
def delete_directional_faces(object_name, x1, x2, y1, y2, z1, z2, nx_lo, nx_hi, label):
    ob = bpy.data.objects.get(object_name)
    if not ob or ob.type != 'MESH':
        raise RuntimeError(f"{label}: source mesh {object_name} missing")
    mw = ob.matrix_world
    nmat = mw.to_3x3()
    bmn = bmesh.new()
    bmn.from_mesh(ob.data)
    doomed = []
    for f in bmn.faces:
        c = mw @ f.calc_center_median()
        if not (x1 < c.x < x2 and y1 < c.y < y2 and z1 < c.z < z2):
            continue
        n = (nmat @ f.normal).normalized()
        if nx_lo <= n.x <= nx_hi:
            doomed.append(f)
    if doomed:
        bmesh.ops.delete(bmn, geom=doomed, context='FACES')
        bmn.to_mesh(ob.data)
    bmn.free()
    bpy.context.view_layer.update()
    print(f"DELETE-DIRECTIONAL {label}: {len(doomed)} faces")

# TV niche back panel (lounge, in direct view from the whole great room).
delete_directional_faces("Object_43", -11.00, -10.90, 5.4, 7.5, 1.0, 2.2,
                         -1.0, -0.7, "tv-niche-backface")
# Upstairs NW band directly above the lounge wall.
delete_directional_faces("Object_62", -11.03, -10.93, 6.0, 8.6, 3.45, 4.8,
                         -1.0, -0.7, "nw-wall-backface")
# Small duvet/cushion faces pressed into the NW headboard trim.
delete_directional_faces("Object_60", -10.99, -10.90, 6.6, 8.2, 4.15, 4.6,
                         -1.0, -0.7, "nw-duvet-backface")
delete_directional_faces("Object_45", -10.76, -10.69, 6.9, 8.1, 4.2, 4.5,
                         -1.0, -0.7, "nw-cushion-backface")

# The source model hangs a 2.0 x 1.2 picture frame on the west wall exactly
# where the TVScreen mounts (frame front at x=-10.897, panel at -10.923), so
# the empty frame renders over the TV. Remove the whole frame: Object_64 holds
# the front border + outer bevel, Object_69 the inner lip. Normal range -1..1
# matches every face inside the box; both objects have nothing else there.
delete_directional_faces("Object_64", -10.94, -10.885, 5.35, 7.55, 0.95, 2.30,
                         -1.0, 1.0, "tv-picture-frame")
delete_directional_faces("Object_69", -10.94, -10.885, 5.35, 7.55, 0.95, 2.30,
                         -1.0, 1.0, "tv-picture-lip")

# --- Styled furniture accents (by region, so shared materials stay put) ------
# Lounge sofa throw pillows: teal / mustard / rust blocks at the corners.
recolor_region(-10.1, -9.3, 8.3, 9.3, 0.32, 0.78, "2E6E6A", label="PillowTeal")
recolor_region(-6.6, -5.7, 8.3, 9.3, 0.32, 0.78, "C99A3C", label="PillowMustard")
recolor_region(-10.1, -9.3, 4.6, 5.5, 0.32, 0.78, "B0562F", label="PillowRust")
# Patio planters: matte black; patio bench cushions: olive.
recolor_region(1.2, 3.4, 8.3, 9.6, 0.1, 1.1, "1E2021", rough=0.75, label="PatioPlanters")

# ===================== ARRIVAL LEVEL + SKY DEN BUILD-OUT ======================
# The source model leaves everything south of the apartment as bare black roof
# slab: the walkway outside the front door, both corner slabs, and an empty
# glass room upstairs. Build them out (elevator lobby, two view terraces, sky
# den). This runs BEFORE navmesh generation, so new walls and furniture carve
# walkability automatically.

def mk(name, hexcol, rough, metal=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = srgb(hexcol)
    b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metal
    return m

M_WALL   = mk('LobbyWall',  'A08B6F', 0.85)          # warm plaster
M_STONE  = mk('LobbyStone', '8F8578', 0.38)          # honed stone floor
M_DARK   = mk('TrimDark',   '2A2320', 0.5)
# Metallic 0.9 renders near-black in the headset (no environment map), so the
# lift doors and brass read as unfinished voids. Mid metallic + lighter base
# keeps a brushed look under the point lights.
M_BRASS  = mk('LobbyBrass', 'B08A45', 0.35, 0.45)
M_STEEL  = mk('LiftSteel', '9A958C', 0.32, 0.35)
M_DECK   = mk('DeckWood',   '6E4E32', 0.68)
M_RAIL   = mk('RailDark',   '23262B', 0.4, 0.25)
M_CUSH   = mk('LoungeCush', '3E5C54', 0.85)
M_OAK    = mk('DenOak',     '5C4630', 0.6)
M_WINE   = mk('RugWine',    '6E2B33', 0.95)
M_GLOW   = mk('WarmGlow',   '2A2320', 0.5)
_gb = M_GLOW.node_tree.nodes['Principled BSDF']
if _gb.inputs.get('Emission Color'):
    _gb.inputs['Emission Color'].default_value = (1.0, 0.82, 0.55, 1)
    _gb.inputs['Emission Strength'].default_value = 1.4
M_GLASSP = bpy.data.materials.get('fake_mat_255_255_255_32')  # model's own glass

# --- Copy a box-region of the source model into a reusable mesh -------------
# Used to instance real furniture/plants (with their styled materials) where
# the build previously stood crude primitives.
def copy_region_to_object(name, x1, x2, y1, y2, z1, z2, only_mats=None,
                          exclude_prefix=("Object_32", "NavMesh", "Art_", "View", "Lobby", "Terr", "Ledge")):
    me = bpy.data.meshes.new(name)
    bmc = bmesh.new()
    uv_layer = bmc.loops.layers.uv.new("UVMap")
    slots = []
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    faces_n = 0
    for ob in [o for o in sc.collection.all_objects if o.type == 'MESH' and not o.name.startswith(exclude_prefix)]:
        mw = ob.matrix_world
        mats = ob.data.materials
        src_uv = ob.data.uv_layers.active.data if ob.data.uv_layers.active else None
        for poly in ob.data.polygons:
            c = mw @ poly.center
            if not (x1 < c.x < x2 and y1 < c.y < y2 and z1 < c.z < z2):
                continue
            m = mats[poly.material_index] if mats and poly.material_index < len(mats) else None
            if only_mats is not None and (m is None or m.name not in only_mats):
                continue
            if m is None:
                m = M_DARK
            if m not in slots:
                slots.append(m)
            vs = []
            for vi in poly.vertices:
                wv = mw @ ob.data.vertices[vi].co
                vs.append(bmc.verts.new((wv.x - cx, wv.y - cy, wv.z - z1)))
            try:
                fc = bmc.faces.new(vs)
                fc.material_index = slots.index(m)
                # keep the source UVs so textured pots/soil/frames still sample
                if src_uv is not None:
                    for loop, li in zip(fc.loops, poly.loop_indices):
                        loop[uv_layer].uv = src_uv[li].uv
                faces_n += 1
            except ValueError:
                pass
    # Do not weld: merged vertices would smear UV seams across the copy.
    bmc.to_mesh(me)
    bmc.free()
    for m in slots:
        me.materials.append(m)
    print(f"COPY {name}: {faces_n} faces, {len(slots)} materials")
    if faces_n < 20:
        raise RuntimeError(f"COPY {name}: region is empty ({faces_n} faces)")
    return me

def place_copy(name, me, x, y, z, yaw=0.0, scale=1.0):
    o = bpy.data.objects.new(name, me)
    o.location = (x, y, z)
    o.rotation_euler = (0, 0, yaw)
    o.scale = (scale, scale, scale)
    sc.collection.objects.link(o)
    return o

# The ivory-planter shrub on the patio (foliage islands already jittered
# green + soil + pot) becomes the house plant for every former cube hedge.
PLANT_ME = copy_region_to_object("PlantSrc", 6.10, 6.80, 9.05, 9.70, 0.02, 1.0)
# The copy box also catches a sliver of the patio curtain (fake_mat_224),
# which read as an ivory wrap around every planter: strip it once here.
_bp = bmesh.new()
_bp.from_mesh(PLANT_ME)
bmesh.ops.delete(_bp, geom=[f for f in _bp.faces if PLANT_ME.materials[f.material_index].name.startswith('fake_mat_224')],
                 context='FACES')
_bp.to_mesh(PLANT_ME)
_bp.free()
def plant(name, x, y, z, scale=1.25, yaw=0.0):
    return place_copy(name, PLANT_ME, x, y, z, yaw, scale)

# --- Textured finishes cloned from the model's own image maps -----------------
# (No new textures: reusing the imported images costs no extra GPU memory.)
def texmat_from(src_name, new_name, rough=0.7, metal=0.0):
    src = bpy.data.materials.get(src_name)
    img = next((n.image for n in src.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image), None) if src else None
    if img is None:
        raise RuntimeError(f"texmat_from: {src_name} has no image texture")
    m = bpy.data.materials.new(new_name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes['Principled BSDF']
    t = nt.nodes.new('ShaderNodeTexImage')
    t.image = img
    nt.links.new(t.outputs['Color'], b.inputs['Base Color'])
    b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metal
    return m

def artmat(file_name, new_name, rough=0.9):
    """Textured material from a tile in art/ (make-furniture-textures.py)."""
    m = mk(new_name, "FFFFFF", rough)
    nt = m.node_tree
    t = nt.nodes.new('ShaderNodeTexImage')
    t.image = bpy.data.images.load(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'art', file_name))
    nt.links.new(t.outputs['Color'], nt.nodes['Principled BSDF'].inputs['Base Color'])
    return m

def retex_region(x1, x2, y1, y2, z1, z2, mat, label, only_mats=None, only_objects=None, normal=None, scale=1.0, rot=0.0):
    """Give faces inside the box an existing textured material with planar UVs
    in world metres (the model's own maps tile once per metre), so a flat
    colour slab becomes a properly scaled stone/wood surface."""
    total = 0
    cr, sr = math.cos(rot), math.sin(rot)
    for ob in [o for o in sc.collection.all_objects if o.type == 'MESH']:
        if ob.name.startswith(("NavMesh", "View", "Art_", "Spawn", "Seat_")):
            continue
        if only_objects is not None and not ob.name.startswith(tuple(only_objects)):
            continue
        mw = ob.matrix_world
        m3 = mw.to_3x3()
        names = [m.name if m else '' for m in ob.data.materials]
        okidx = {i for i, n in enumerate(names)
                 if not n.startswith(("Foliage_", "Floral_")) and (only_mats is None or n in only_mats)}
        if only_mats is not None and not okidx:
            continue
        sel = [p for p in ob.data.polygons
               if (only_mats is None or p.material_index in okidx)
               and x1 < (mw @ p.center).x < x2 and y1 < (mw @ p.center).y < y2 and z1 < (mw @ p.center).z < z2
               and face_normal_ok(m3, p, normal)]
        if not sel:
            continue
        if mat.name not in names:
            ob.data.materials.append(mat)
            names.append(mat.name)
        midx = names.index(mat.name)
        if not ob.data.uv_layers:
            ob.data.uv_layers.new(name="UVMap")
        uv = ob.data.uv_layers.active.data
        for p in sel:
            p.material_index = midx
            n = (m3 @ p.normal).normalized()
            for li, vi in zip(p.loop_indices, p.vertices):
                w = mw @ ob.data.vertices[vi].co
                if abs(n.z) > 0.5:
                    u, v = w.x, w.y
                elif abs(n.x) > abs(n.y):
                    u, v = w.y, w.z
                else:
                    u, v = w.x, w.z
                uv[li].uv = ((u * cr - v * sr) / scale, (u * sr + v * cr) / scale)
        total += len(sel)
    print(f"RETEX {label}: {total} faces -> {mat.name}")
    return total

def tex_box(name, x, y, z, sx, sy, sz, mat, scale=1.0, rot=0.0):
    add_box(name, x, y, z, sx, sy, sz, mat)
    bpy.context.view_layer.update()
    retex_region(x - sx - 0.02, x + sx + 0.02, y - sy - 0.02, y + sy + 0.02, z - sz - 0.02, z + sz + 0.02,
                 mat, name, only_objects=(name,), scale=scale, rot=rot)

# Preserve the source door slabs, frames and surrounding walls. Movement uses
# the navigation links below and does not require visually carving the model.

FACADE = {'noir_001_Wall_Entity_Material', 'noir_001_Room_Entity_Material'}
# Black building faces bordering the new spaces -> warm limestone facade.
recolor_region(-11.65, -7.45, -10.3, -4.15, -0.3, 6.6, "8A8378", rough=0.85, label="FacadeSW", only_mats=FACADE)
recolor_region(7.3, 11.65, -10.3, -4.15, -0.3, 6.6, "8A8378", rough=0.85, label="FacadeSE", only_mats=FACADE)
recolor_region(0.3, 7.45, -10.3, -6.1, -0.3, 3.45, "8A8378", rough=0.85, label="FacadeWalk", only_mats=FACADE)
recolor_region(-7.7, 7.6, -10.3, -7.15, 2.9, 6.7, "8A8378", rough=0.85, label="FacadeUpper", only_mats=FACADE)
recolor_region(0.6, 7.6, -7.15, -5.9, 2.9, 6.7, "8A8378", rough=0.85, label="FacadeWalkUp", only_mats=FACADE)
recolor_region(4.35, 7.7, -7.3, -4.1, -0.4, 6.8, "8A8378", rough=0.85, label="FacadeSEcorner", only_mats=FACADE)
# The upper volume over the walk is clad in charcoal (not noir) — same warm
# facade treatment, tightly scoped to the exterior south band.
recolor_region(3.8, 7.7, -10.3, -6.0, 2.55, 6.8, "8A8378", rough=0.85, label="FacadeCharcoal",
               only_mats={'fake_mat_35_32_34_255', 'fake_mat_6_5_5_255'})
# Finish the remaining source black shell inside the occupied building.
# Purpose-built dark furniture and trim use new materials and are unaffected.
recolor_region(-14.0, 14.0, -11.0, 10.6, -0.3, 7.2, "8A8378", rough=0.85,
               label="LegacyBlackFinish", only_mats=FACADE)

# Teal mannequin hands still float by the vestibule glass door: delete small
# islands of that (recolored) material only, so no furniture can be caught.
def scrub_mats(x1, x2, y1, y2, z1, z2, mats, cap=600):
    removed = 0
    for ob in [o for o in sc.collection.all_objects if o.type == 'MESH']:
        names = [m.name if m else '' for m in ob.data.materials]
        tset = {i for i, n in enumerate(names) if n in mats}
        if not tset:
            continue
        mw = ob.matrix_world
        bmx = bmesh.new()
        bmx.from_mesh(ob.data)
        bmx.faces.ensure_lookup_table()
        seen = set()
        doom = []
        for f in bmx.faces:
            if f in seen or f.material_index not in tset:
                continue
            stack, island = [f], [f]
            seen.add(f)
            while stack:
                g = stack.pop()
                for e in g.edges:
                    for lf in e.link_faces:
                        if lf not in seen and lf.material_index in tset:
                            seen.add(lf)
                            stack.append(lf)
                            island.append(lf)
            if len(island) >= cap:
                continue
            inside = True
            for fc in island:
                c = mw @ fc.calc_center_median()
                if not (x1 < c.x < x2 and y1 < c.y < y2 and z1 < c.z < z2):
                    inside = False
                    break
            if inside:
                doom.extend(island)
        if doom:
            bmesh.ops.delete(bmx, geom=doom, context='FACES')
            bmx.to_mesh(ob.data)
            removed += len(doom)
        bmx.free()
    bpy.context.view_layer.update()
    print(f"SCRUB-MATS ({x1},{y1}): removed {removed} faces")

scrub_mats(-2.2, 0.6, -8.9, -7.1, 0.9, 2.2, {'fake_mat_157_154_155_255'})
# Gray utility hut on the lobby footprint: remove it outright, plus the tall
# noir/beige wall fin at x=-3.17 that would slice through the lobby.
region_delete(-3.62, -2.05, -9.85, -7.68, 0.02, 2.78)
region_delete(-3.35, -2.88, -9.85, -6.72, 0.02, 3.10)

# --- Elevator lobby (x -7.62..-0.58, y -6.62..-9.76) --------------------------
# The source vestibule's west wall (green plaster + the glass front door,
# x -1.3..-1.1) is the lobby's east boundary; everything the lobby adds stops
# at x = -1.32 so nothing pokes through into the vestibule.
add_box("LobbyFloor", -4.47, -8.19, 0.02, 3.15, 1.57, 0.02, M_STONE)
add_box("LobbyCeil",  -4.47, -8.19, 2.98, 3.15, 1.57, 0.04, M_WALL)
add_box("LobbyGlow",  -4.47, -8.19, 2.93, 1.30, 0.45, 0.015, M_GLOW)
# North wall: solid runs with one doorway aligned to the real passage between
# the library block's west end and the piano room (open x -6.9..-5.3). Wall
# face sits just south of the noir library face and hides it.
add_box("LobbyWallN1", -7.11, -6.57, 1.475, 0.51, 0.03, 1.475, M_WALL)
add_box("LobbyWallN2", -3.41, -6.57, 1.475, 2.09, 0.03, 1.475, M_WALL)
add_box("LobbyDoorHead", -6.05, -6.57, 2.775, 0.55, 0.03, 0.175, M_WALL)
# South wall (elevator bank), full run.
add_box("LobbyWallS", -4.47, -9.73, 1.475, 3.15, 0.03, 1.475, M_WALL)
# The apartment's real front door is the glass leaf in the vestibule wall at
# y -8.05..-6.95 (frame Object_67, pane Object_61). A previous build stood a
# plaster wall + oak door 0.6 m INSIDE the vestibule, hiding it, and bridged
# the nav mesh straight through the glass. Remove the pane so the framed
# opening is a walkable doorway between the lobby and the vestibule.
region_delete_mats(-1.28, -1.12, -8.08, -6.92, 0.02, 2.5, {'fake_mat_255_255_255_32'}, "front-door-pane")
# The source's front-door canopy (a sloped camel slab on an olive/grey post
# and beam, with green side panels) stands inside the lobby's east end and
# showed as coloured wedges at the ceiling corner and a post in front of the
# gallery wall. Its slab triangles are large, so delete any face of those
# materials that TOUCHES the lobby volume (x < -1.33 keeps the vestibule's
# green wall and the front-door frame at x >= -1.3 intact).
def region_delete_mats_touch(x1, x2, y1, y2, z1, z2, mats, label):
    total = 0
    for ob in [o for o in sc.collection.all_objects if o.type == 'MESH' and not o.name.startswith(("Lobby", "Lift", "Art_", "Plant"))]:
        idx = {i for i, m in enumerate(ob.data.materials) if m and m.name in mats}
        if not idx:
            continue
        mw = ob.matrix_world
        bmr = bmesh.new()
        bmr.from_mesh(ob.data)
        doomed = []
        for f in bmr.faces:
            if f.material_index not in idx:
                continue
            # vertices, edge midpoints and the centre: a tall sliver whose
            # vertices straddle the box still counts as touching it
            samples = [v.co for v in f.verts] + [(e.verts[0].co + e.verts[1].co) * 0.5 for e in f.edges] + [f.calc_center_median()]
            for co in samples:
                w = mw @ co
                if x1 < w.x < x2 and y1 < w.y < y2 and z1 < w.z < z2:
                    doomed.append(f)
                    break
        if doomed:
            bmesh.ops.delete(bmr, geom=doomed, context='FACES')
            bmr.to_mesh(ob.data)
            total += len(doomed)
        bmr.free()
    bpy.context.view_layer.update()
    print(f"REGION-DELETE-TOUCH {label}: {total} faces")

region_delete_mats_touch(-3.6, -1.33, -9.9, -6.3, 0.03, 3.05,
                         {'fake_mat_251_251_251_255', 'fake_mat_196_192_184_255',
                          'fake_mat_69_64_65_255', 'fake_mat_230_220_187_255'}, "lobby-canopy")
region_delete_mats(-3.6, -1.33, -9.9, -6.3, 1.90, 3.05, {'beige_006_Wall_Entity_Material'}, "lobby-canopy-green")
# The former elevator lobby is now the covered half of the beach-club spa.
# Its west wall and short north return are deliberately absent: the entire
# deck, former pocket and lounge join without a door-sized bottleneck.
for nm in ("LobbyWallN1", "LobbyDoorHead"):
    bpy.data.objects.remove(bpy.data.objects[nm], do_unlink=True)
add_box("LobbyBaseN", -3.135, -6.605, 0.16, 1.815, 0.012, 0.06, M_DARK)
add_box("LobbyBaseS", -4.47, -9.695, 0.16, 3.15, 0.012, 0.06, M_DARK)

# --- SW terrace: accessible four-person hot tub ------------------------------
add_box("DeckSW", -9.57, -7.48, 0.07, 1.85, 2.28, 0.03, M_DECK)   # y -9.76..-5.20; the sill band continues to the wall
if M_GLASSP:
    add_box("ParaSWglassW", -11.40, -7.10, 0.625, 0.015, 2.66, 0.525, M_GLASSP)
    add_box("ParaSWglassS", -9.57, -9.74, 0.625, 1.85, 0.015, 0.525, M_GLASSP)
add_box("ParaSWrailW", -11.40, -7.10, 1.17, 0.03, 2.66, 0.025, M_RAIL)
add_box("ParaSWrailS", -9.57, -9.74, 1.17, 1.85, 0.03, 0.025, M_RAIL)
add_box("ParaSWcurbW", -11.40, -7.10, 0.07, 0.03, 2.66, 0.035, M_RAIL)
add_box("ParaSWcurbS", -9.57, -9.74, 0.07, 1.85, 0.03, 0.035, M_RAIL)
M_TUB = mk('HotTubShell', 'E8E1D4', 0.38)
M_TUB_INNER = mk('HotTubInner', '24444A', 0.48)
M_WATER = mk('HotTubWater', '5CC6D2', 0.06, 0.05)
water_bsdf = M_WATER.node_tree.nodes['Principled BSDF']
water_bsdf.inputs['Alpha'].default_value = 0.70
M_WATER.surface_render_method = 'DITHERED'

tub_x, tub_y = -9.75, -7.15
add_box("HotTubBasin", tub_x, tub_y, 0.18, 1.22, 1.27, 0.08, M_TUB_INNER)
add_box("HotTubWallN", tub_x, -5.70, 0.42, 1.40, 0.16, 0.30, M_TUB)
add_box("HotTubWallS", tub_x, -8.60, 0.42, 1.40, 0.16, 0.30, M_TUB)
add_box("HotTubWallW", -11.15, tub_y, 0.42, 0.16, 1.29, 0.30, M_TUB)
# East wall is split to leave a visible, walkable entry in the middle.
add_box("HotTubWallENE", -8.35, -6.14, 0.42, 0.16, 0.44, 0.30, M_TUB)
add_box("HotTubWallESE", -8.35, -8.16, 0.42, 0.16, 0.44, 0.30, M_TUB)
add_box("HotTubWater", tub_x, tub_y, 0.555, 1.20, 1.25, 0.015, M_WATER)
# Four real pads and backrests remain visible through the water.
for i, (sx, sy, back_y) in enumerate(((-10.28, -6.15, -5.92), (-9.22, -6.15, -5.92),
                                      (-10.28, -8.15, -8.38), (-9.22, -8.15, -8.38))):
    add_box(f"HotTubSeatPad_{i}", sx, sy, 0.36, 0.38, 0.28, 0.08, M_TUB_INNER)
    add_box(f"HotTubSeatBack_{i}", sx, back_y, 0.49, 0.38, 0.07, 0.17, M_TUB_INNER)
# Two physical steps through the east-wall opening.
add_box("HotTubStepOuter", -8.10, tub_y, 0.18, 0.24, 0.38, 0.12, M_TUB)
add_box("HotTubStepInner", -8.56, tub_y, 0.29, 0.20, 0.34, 0.08, M_TUB_INNER)
for i, (dx, dy, rr) in enumerate(((-0.42, 0.18, 0.035), (-0.12, -0.31, 0.025),
                                  (0.22, 0.28, 0.030), (0.48, -0.10, 0.022),
                                  (-0.30, -0.45, 0.026), (0.05, 0.02, 0.020))):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=8, ring_count=4, radius=rr,
                                        location=(tub_x + dx, tub_y + dy, 0.595))
    bpy.context.active_object.name = f"HotTubBubble_{i}"
    bpy.context.active_object.data.materials.append(M_TUB)
# (The first build stood these two INSIDE the wall cavity at y -4.75, where
# they showed through the piano-room niche instead of on the deck.)
plant("TerrSWplant1", -5.90, -5.60, 0.10, 1.0, 0.8)

for i, (bx, by) in enumerate(((-11.15, -9.45), (-7.95, -9.45), (-7.58, -6.42))):
    add_box(f"BollSW{i}", bx, by, 0.32, 0.045, 0.045, 0.32, M_RAIL)
    add_box(f"BollSWg{i}", bx, by, 0.60, 0.05, 0.05, 0.028, M_GLOW)

# --- SE terrace + covered walk: morning coffee -------------------------------
add_box("DeckSE", 9.21, -7.08, 0.07, 2.21, 2.68, 0.03, M_DECK)
add_box("DeckWalk", 4.775, -8.055, 0.07, 2.225, 1.705, 0.03, M_DECK)
if M_GLASSP:
    add_box("ParaSEglassE", 11.40, -7.08, 0.625, 0.015, 2.68, 0.525, M_GLASSP)
    add_box("ParaSEglassS", 6.985, -9.74, 0.625, 4.415, 0.015, 0.525, M_GLASSP)
add_box("ParaSErailE", 11.40, -7.08, 1.17, 0.03, 2.68, 0.025, M_RAIL)
add_box("ParaSErailS", 6.985, -9.74, 1.17, 4.415, 0.03, 0.025, M_RAIL)
add_box("ParaSEcurbE", 11.40, -7.08, 0.07, 0.03, 2.68, 0.035, M_RAIL)
add_box("ParaSEcurbS", 6.985, -9.74, 0.07, 4.415, 0.03, 0.035, M_RAIL)
bpy.ops.mesh.primitive_cylinder_add(radius=0.38, depth=0.035, location=(9.5, -7.3, 0.795))
bpy.context.active_object.name = "BistroTop"
bpy.context.active_object.data.materials.append(M_DARK)
bpy.ops.mesh.primitive_cylinder_add(radius=0.045, depth=0.70, location=(9.5, -7.3, 0.43))
bpy.context.active_object.name = "BistroStem"
bpy.context.active_object.data.materials.append(M_RAIL)
bpy.ops.mesh.primitive_cylinder_add(radius=0.20, depth=0.03, location=(9.5, -7.3, 0.095))
bpy.context.active_object.name = "BistroBase"
bpy.context.active_object.data.materials.append(M_RAIL)
for i, (cy2, backy) in enumerate(((-6.55, -6.28), (-8.05, -8.32))):
    add_box(f"BistroSeat{i}", 9.5, cy2, 0.47, 0.21, 0.21, 0.03, M_CUSH)
    add_box(f"BistroPlinth{i}", 9.5, cy2, 0.25, 0.17, 0.17, 0.19, M_DARK)
    add_box(f"BistroBack{i}", 9.5, backy, 0.67, 0.21, 0.025, 0.17, M_DARK)
plant("TerrSEplant1", 8.0, -4.75, 0.04, 1.5, 1.2)
plant("TerrSEplant2", 9.5, -4.75, 0.04, 1.5, 3.0)
plant("TerrSEplant3", 11.0, -4.75, 0.04, 1.5, 0.5)
for i, (bx, by) in enumerate(((11.15, -9.45), (3.3, -9.45), (11.15, -4.85))):
    add_box(f"BollSE{i}", bx, by, 0.32, 0.045, 0.045, 0.32, M_RAIL)
    add_box(f"BollSEg{i}", bx, by, 0.60, 0.05, 0.05, 0.028, M_GLOW)

# --- Sky den: the empty glass room above the vestibule ------------------------
DEN_Z = 3.51
add_box("DenFloor", 1.53, -8.465, DEN_Z, 2.15, 1.215, 0.02, M_OAK)
recolor_region(-0.78, 3.85, -9.85, -7.10, 3.45, 6.35, "A08B6F", rough=0.85,
               label="DenWalls", only_mats={'fake_mat_69_64_65_255'})
add_box("DenRug", 1.4, -8.5, DEN_Z + 0.028, 1.70, 0.90, 0.006, M_WINE)
add_box("DenSofaSeat", 1.4, -9.25, DEN_Z + 0.26, 1.35, 0.42, 0.10, M_CUSH)
add_box("DenSofaBack", 1.4, -9.58, DEN_Z + 0.62, 1.35, 0.09, 0.28, M_CUSH)
add_box("DenSofaArmW", -0.06, -9.25, DEN_Z + 0.44, 0.10, 0.42, 0.16, M_CUSH)
add_box("DenSofaArmE", 2.86, -9.25, DEN_Z + 0.44, 0.10, 0.42, 0.16, M_CUSH)
add_box("DenTable", 1.4, -8.35, DEN_Z + 0.17, 0.55, 0.30, 0.15, M_DARK)
cushA = mk('CushMustard', 'C99A3C', 0.9)
cushB = mk('CushRust', 'B0562F', 0.9)
add_box("DenCush1", 0.25, -7.95, DEN_Z + 0.07, 0.28, 0.28, 0.055, cushA)
add_box("DenCush2", 2.55, -7.95, DEN_Z + 0.07, 0.28, 0.28, 0.055, cushB)
add_box("DenGlow", 1.5, -8.45, 6.20, 0.55, 0.22, 0.014, M_GLOW)
# (The west ledge plant sat inside what is now the sauna; the finish pass
# rebuilds that room.)
# Move the east ledge plant into the room and replace the source planter's
# clipped wall/pot fragments with a complete freestanding ceramic vessel.
denplant=plant("LedgeE1", 3.40, -9.36, DEN_Z + .02, .7, 2.9)
denplant.data=denplant.data.copy()
bp=bmesh.new(); bp.from_mesh(denplant.data)
remove=[f for f in bp.faces if not denplant.data.materials[f.material_index].name.startswith('Foliage_') or f.calc_center_median().z < .82]
bmesh.ops.delete(bp,geom=remove,context='FACES');bp.to_mesh(denplant.data);bp.free()
M_DEN_POT=mk('DenIvoryPlanter','DCD3BE',.72)
bpy.ops.mesh.primitive_cone_add(vertices=32,radius1=.14,radius2=.16,depth=.56,location=(3.40,-9.36,DEN_Z+.30))
bpy.context.object.name='DenPlanterPot';bpy.context.object.data.materials.append(M_DEN_POT)
bpy.ops.mesh.primitive_cylinder_add(vertices=32,radius=.15,depth=.012,location=(3.40,-9.36,DEN_Z+.586))
bpy.context.object.name='DenPlanterSoil';bpy.context.object.data.materials.append(mk('DenPlanterSoil','332C25',1.0))

# ===================== FURNITURE: LIBRARY CHAIRS + GRAND PIANO ================
# Library: the "reading group" seats sat inside the bookshelves — the room has
# no chairs at all. Instance the dining room's Qing chair (charcoal frame, red
# seat) as a facing pair with a small side table.
QING_ME = copy_region_to_object("QingSrc", 7.55, 8.32, 4.35, 5.15, 0.02, 1.3,
                                only_mats={'fake_mat_35_32_34_255', 'qing_style_chair___qing_style_chairmaterial__28'})
place_copy("LibChairW", QING_ME, -4.55, -5.30, 0.0, 0.0)       # faces +x like the source chair
place_copy("LibChairE", QING_ME, -3.55, -5.30, 0.0, math.pi)   # faces -x
bpy.ops.mesh.primitive_cylinder_add(vertices=20, radius=0.24, depth=0.03, location=(-4.05, -5.82, 0.52))
bpy.context.active_object.name = "LibTableTop"
bpy.context.active_object.data.materials.append(M_DARK)
bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=0.03, depth=0.50, location=(-4.05, -5.82, 0.26))
bpy.context.active_object.name = "LibTableStem"
bpy.context.active_object.data.materials.append(M_RAIL)
bpy.ops.mesh.primitive_cylinder_add(vertices=20, radius=0.16, depth=0.02, location=(-4.05, -5.82, 0.02))
bpy.context.active_object.name = "LibTableBase"
bpy.context.active_object.data.materials.append(M_RAIL)

# Grand piano: the source piano was unusable and its corner was left as a bare
# white disc. A black-lacquer baby grand (propped lid, ivory keys, bench with
# a seat waypoint) rebuilt from a traced grand outline.
M_LACQ = mk('PianoLacquer', '0A0A0C', 0.16)
M_IVORY = mk('PianoIvory', 'EFE4CD', 0.5)
M_FELT = mk('PianoFelt', '6E2B33', 0.9)
recolor_region(-10.4, -5.8, -3.4, 1.4, 0.005, 0.07, "6E2B33", rough=0.95, label="PianoRug", only_mats={'moquette_019'})

def prism(name, pts, z0, h, mat, parent, loc=(0.0, 0.0, 0.0), rot=(0.0, 0.0, 0.0)):
    me = bpy.data.meshes.new(name)
    bp = bmesh.new()
    vs = [bp.verts.new((x, y, z0)) for x, y in pts]
    f = bp.faces.new(vs)
    r = bmesh.ops.extrude_face_region(bp, geom=[f])
    top = [g for g in r['geom'] if isinstance(g, bmesh.types.BMVert)]
    bmesh.ops.translate(bp, vec=(0, 0, h), verts=top)
    bmesh.ops.recalc_face_normals(bp, faces=bp.faces[:])
    bp.to_mesh(me)
    bp.free()
    me.materials.append(mat)
    o = bpy.data.objects.new(name, me)
    o.parent = parent
    o.location = loc
    o.rotation_euler = rot
    sc.collection.objects.link(o)
    return o

def part_box(name, parent, x, y, z, sx, sy, sz, mat):
    bpy.ops.mesh.primitive_cube_add(location=(0, 0, 0))
    o = bpy.context.active_object
    o.name = name
    o.scale = (sx, sy, sz)
    o.data.materials.append(mat)
    o.parent = parent
    o.location = (x, y, z)
    return o

def grand_outline(shrink=0.0):
    # keyboard edge along local y=0 (x -0.75..0.75), tail toward +y, treble +x
    pts = [(-0.75 + shrink, 0.0 + shrink), (0.75 - shrink, 0.0 + shrink), (0.75 - shrink, 0.6)]
    a, b = 0.80 - shrink, 1.25 - shrink
    for k in range(1, 13):
        th = math.radians(150 * k / 12)
        pts.append((-0.05 + a * math.cos(th), 0.6 + b * math.sin(th)))
    pts.append((-0.75 + shrink, 0.6 + b * math.sin(math.radians(150))))
    return pts

PIANO_X, PIANO_Y, PIANO_YAW = -8.05, -1.25, math.pi / 2   # keyboard east, tail to the window
pno = bpy.data.objects.new("Pno_Root", None)
pno.location = (PIANO_X, PIANO_Y, 0.0)
pno.rotation_euler = (0, 0, PIANO_YAW)
sc.collection.objects.link(pno)
prism("Pno_Body", grand_outline(), 0.66, 0.30, M_LACQ, pno)
prism("Pno_Soundboard", grand_outline(0.04), 0.90, 0.005, M_FELT, pno)
# Lid hinged on the bass (local -x) side, propped open 35 degrees.
lid_pts = [(x + 0.75, y) for x, y in grand_outline(0.02)]
prism("Pno_Lid", lid_pts, 0.0, 0.03, M_LACQ, pno, loc=(-0.75, 0.0, 0.965), rot=(0, math.radians(-35), 0))
part_box("Pno_LidProp", pno, 0.52, 0.85, 1.28, 0.012, 0.012, 0.33, M_LACQ)
part_box("Pno_KeyBed", pno, 0.0, -0.13, 0.80, 0.74, 0.14, 0.035, M_LACQ)
part_box("Pno_WhiteKeys", pno, 0.0, -0.14, 0.838, 0.68, 0.12, 0.006, M_IVORY)
part_box("Pno_BlackKeys", pno, 0.0, -0.075, 0.852, 0.66, 0.045, 0.009, M_LACQ)
part_box("Pno_CheekL", pno, -0.71, -0.13, 0.86, 0.035, 0.14, 0.06, M_LACQ)
part_box("Pno_CheekR", pno, 0.71, -0.13, 0.86, 0.035, 0.14, 0.06, M_LACQ)
part_box("Pno_Fallboard", pno, 0.0, -0.005, 0.90, 0.72, 0.045, 0.045, M_LACQ)
part_box("Pno_MusicDesk", pno, 0.0, 0.32, 1.08, 0.30, 0.012, 0.11, M_LACQ)
for i, (lx, ly) in enumerate(((0.60, 0.18), (-0.60, 0.18), (-0.45, 1.05))):
    part_box(f"Pno_Leg{i}", pno, lx, ly, 0.33, 0.045, 0.045, 0.33, M_LACQ)
part_box("Pno_Lyre", pno, 0.0, 0.25, 0.30, 0.02, 0.02, 0.30, M_LACQ)
part_box("Pno_Pedals", pno, 0.0, 0.20, 0.06, 0.12, 0.05, 0.015, M_BRASS)
# Bench: lacquer frame, wine felt top; the pianist's seat waypoint sits on it.
part_box("Pno_BenchTop", pno, 0.0, -0.62, 0.475, 0.46, 0.18, 0.025, M_FELT)
part_box("Pno_BenchFrame", pno, 0.0, -0.62, 0.44, 0.44, 0.16, 0.012, M_LACQ)
for i, (lx, ly) in enumerate(((0.40, -0.48), (-0.40, -0.48), (0.40, -0.76), (-0.40, -0.76))):
    part_box(f"Pno_BenchLeg{i}", pno, lx, ly, 0.215, 0.022, 0.022, 0.215, M_LACQ)
bpy.context.view_layer.update()
PIANO_SEAT = pno.matrix_world @ Vector((0.0, -0.62, 0.0))
print(f"PIANO at ({PIANO_X},{PIANO_Y}); bench seat at ({PIANO_SEAT.x:.2f},{PIANO_SEAT.y:.2f})")

# --- Decimate to budget ------------------------------------------------------
dg = bpy.context.evaluated_depsgraph_get()
def tri_count(o):
    m = o.evaluated_get(dg).to_mesh()
    m.calc_loop_triangles()
    return len(m.loop_triangles)

total_before = 0
for o in [o for o in sc.collection.all_objects if o.type == 'MESH']:
    t = tri_count(o)
    total_before += t
    if t > 8000:
        r = max(0.1, 7000.0 / t)
    elif t > 4000:
        r = 0.5
    else:
        continue
    mod = o.modifiers.new('dec', 'DECIMATE')
    mod.ratio = r
    bpy.context.view_layer.objects.active = o
    bpy.ops.object.modifier_apply(modifier='dec')

dg = bpy.context.evaluated_depsgraph_get()
total_after = sum(tri_count(o) for o in sc.collection.all_objects if o.type == 'MESH')
print(f"DECIMATE {total_before} -> {total_after}")

# --- Coplanar wall dedupe ----------------------------------------------------
# The source model overlays big merged wall shells (Object_32, Object_61, ...)
# on top of per-room wall objects, leaving many wall areas as two coplanar
# faces less than a millimetre apart. Every material is doubleSided, so those
# pairs z-fight as strobing patches. Generic pass: find near-exact coplanar
# overlapping axis-aligned wall faces inside the living volume, ray-probe which
# member is actually visible from open space, delete fully hidden members, and
# nudge apart back-to-back membranes that are visible from both sides.
def dedupe_coplanar_walls():
    from collections import defaultdict as dd
    ALIGN, GAPMAX, STEP = 0.985, 0.0012, 0.002
    IV = (-11.2, 11.8, -10.6, 10.1, -0.3, 7.2)  # interior volume
    SKIP = ("TVScreen", "NavMesh", "Spawn", "Seat_", "RockiesView", "ViewEast",
            "ViewWest", "ViewSouth", "Art_", "Monitor")
    dgl = bpy.context.evaluated_depsgraph_get()

    faces = []  # (axis, plane, umin, umax, vmin, vmax, obname, sign, fidx)
    for ob in [o for o in sc.collection.all_objects if o.type == 'MESH']:
        if ob.name.startswith(SKIP):
            continue
        mw = ob.matrix_world
        nmat = mw.to_3x3()
        for p in ob.data.polygons:
            n = nmat @ p.normal
            if n.length < 1e-6:
                continue
            n = n.normalized()
            axis = 0 if abs(n.x) >= ALIGN else (1 if abs(n.y) >= ALIGN else None)
            if axis is None:
                continue
            c = mw @ p.center
            if not (IV[0] < c.x < IV[1] and IV[2] < c.y < IV[3] and IV[4] < c.z < IV[5]):
                continue
            verts = [mw @ ob.data.vertices[vi].co for vi in p.vertices]
            u_ax, v_ax = [i for i in range(3) if i != axis]
            us = [v[u_ax] for v in verts]
            vs = [v[v_ax] for v in verts]
            if (max(us) - min(us)) * (max(vs) - min(vs)) < 0.0004:
                continue
            faces.append((axis, c[axis], min(us), max(us), min(vs), max(vs),
                          ob.name, 1 if n[axis] > 0 else -1, p.index))

    buckets = dd(list)
    for f in faces:
        buckets[(f[0], int(math.floor(f[1] / STEP)))].append(f)

    # cluster key -> {"members": {ob: set(face idx)}, sample data}
    clusters = dd(lambda: {"members": dd(set), "region": [1e9, -1e9, 1e9, -1e9],
                           "planes": {}, "signs": dd(set), "faces": set()})
    for (axis, b), lst in buckets.items():
        for nb in (b, b + 1):
            other = buckets.get((axis, nb), [])
            for i, f in enumerate(lst):
                cand = other[i + 1:] if nb == b else other
                for g in cand:
                    if f[6] == g[6] or abs(f[1] - g[1]) > GAPMAX:
                        continue
                    ou = min(f[3], g[3]) - max(f[2], g[2])
                    ov = min(f[5], g[5]) - max(f[4], g[4])
                    if ou <= 0.02 or ov <= 0.02 or ou * ov < 0.002:
                        continue
                    key = (axis, round(f[1] / 0.05) * 0.05, tuple(sorted((f[6], g[6]))))
                    cl = clusters[key]
                    for fc in (f, g):
                        cl["members"][fc[6]].add(fc[8])
                        cl["planes"][fc[6]] = fc[1]
                        cl["signs"][fc[6]].add(fc[7])
                        cl["faces"].add((fc[6], fc[8]))
                    r = cl["region"]
                    r[0] = min(r[0], max(f[2], g[2])); r[1] = max(r[1], min(f[3], g[3]))
                    r[2] = min(r[2], max(f[4], g[4])); r[3] = max(r[3], min(f[5], g[5]))

    doomed = dd(set)   # obname -> face indices
    nudged = dd(set)   # obname -> (vertex idx, Vector offset) via dict
    nudge_vec = {}
    for key, cl in sorted(clusters.items()):
        axis, plane, obs = key
        a_name, b_name = obs
        r = cl["region"]
        u_ax, v_ax = [i for i in range(3) if i != axis]
        # sample the overlap region: centre + quarters
        samples = []
        for fu, fv in ((0.5, 0.5), (0.25, 0.25), (0.75, 0.25), (0.25, 0.75), (0.75, 0.75)):
            p = [0.0, 0.0, 0.0]
            p[axis] = plane
            p[u_ax] = r[0] + fu * (r[1] - r[0])
            p[v_ax] = r[2] + fv * (r[3] - r[2])
            samples.append(Vector(p))
        n = Vector((0.0, 0.0, 0.0)); n[axis] = 1.0
        wins = {a_name: 0, b_name: 0}
        third = 0
        for p in samples:
            for sgn in (1, -1):
                origin = p + n * (0.12 * sgn)
                hit, loc, _nrm, _fi, ob_hit, _m = sc.ray_cast(dgl, origin, -n * sgn, distance=0.24)
                if not hit:
                    continue
                if ob_hit.name in wins:
                    wins[ob_hit.name] += 1
                else:
                    third += 1
        a_seen, b_seen = wins[a_name] > 0, wins[b_name] > 0
        area = (r[1] - r[0]) * (r[3] - r[2])
        if a_seen and not b_seen:
            doomed[b_name] |= cl["members"][b_name]
            print(f"DEDUPE delete {b_name} behind {a_name} "
                  f"{'XY'[axis]}~{plane:.2f} area~{area:.2f} faces={len(cl['members'][b_name])}")
        elif b_seen and not a_seen:
            doomed[a_name] |= cl["members"][a_name]
            print(f"DEDUPE delete {a_name} behind {b_name} "
                  f"{'XY'[axis]}~{plane:.2f} area~{area:.2f} faces={len(cl['members'][a_name])}")
        elif a_seen and b_seen:
            # visible from both sides: separate the membranes. Nudge the member
            # with fewer faces 2.5 mm along its own normal (into its own room).
            mover = a_name if len(cl["members"][a_name]) <= len(cl["members"][b_name]) else b_name
            sgns = cl["signs"][mover]
            sgn = 1 if 1 in sgns and -1 not in sgns else (-1 if -1 in sgns else 0)
            if sgn == 0:
                print(f"DEDUPE skip mixed-sign nudge {mover} {'XY'[axis]}~{plane:.2f}")
                continue
            off = Vector((0.0, 0.0, 0.0)); off[axis] = 0.0025 * sgn
            ob = bpy.data.objects[mover]
            inv = ob.matrix_world.to_3x3().inverted()
            for fi in cl["members"][mover]:
                for vi in ob.data.polygons[fi].vertices:
                    if (mover, vi) not in nudge_vec:
                        nudge_vec[(mover, vi)] = inv @ off
                        nudged[mover].add(vi)
            print(f"DEDUPE nudge {mover} {0.0025*sgn*1000:+.1f}mm {'XY'[axis]}~{plane:.2f} area~{area:.2f}")
        else:
            print(f"DEDUPE skip (occluded/inconclusive, third={third}) {a_name}x{b_name} {'XY'[axis]}~{plane:.2f}")

    for obname, fids in doomed.items():
        ob = bpy.data.objects.get(obname)
        if not ob or not fids:
            continue
        if len(fids) >= len(ob.data.polygons):
            print(f"DEDUPE refuse to delete ALL faces of {obname}")
            continue
        bmd = bmesh.new()
        bmd.from_mesh(ob.data)
        bmd.faces.ensure_lookup_table()
        geom = [bmd.faces[i] for i in fids if i < len(bmd.faces)]
        bmesh.ops.delete(bmd, geom=geom, context='FACES')
        bmd.to_mesh(ob.data)
        bmd.free()
        print(f"DEDUPE deleted {len(geom)} faces from {obname}")
    for obname, vids in nudged.items():
        ob = bpy.data.objects.get(obname)
        if not ob:
            continue
        if obname in doomed and doomed[obname]:
            # the face deletion above rebuilt this mesh, so the recorded vertex
            # indices are stale — skip rather than move the wrong vertices
            print(f"DEDUPE skip nudge on {obname} (had deletions)")
            continue
        for vi in vids:
            ob.data.vertices[vi].co += nudge_vec[(obname, vi)]
        print(f"DEDUPE nudged {len(vids)} verts in {obname}")
    bpy.context.view_layer.update()

# Three passes: pass 1 deletes laminated faces but must skip nudges on objects
# whose face indices it invalidated; pass 2 sees fresh indices, deletes faces
# newly laminated by the first round and separates surviving membranes; pass 3
# catches nudges deferred by pass 2 deletions.
dedupe_coplanar_walls()
dedupe_coplanar_walls()
dedupe_coplanar_walls()

# ===================== FINISH PASS: SPA TERRACE, GYM, CLOSET, ENSUITE ========
# Runs after decimation and the coplanar dedupe: decimation collapses faces
# across material boundaries and merged retextured floor faces back into their
# neighbours when this pass ran earlier.
M_TRAV = texmat_from('20210309-221754-cet_Wall_Entity_Material', 'Travertine', 0.72)
M_TEAK = texmat_from('20191115-193825-cet_Wall_Entity_Material', 'TeakPlank', 0.62)
M_OAKL = texmat_from('tex_bois_scan_blanc_002_Wall_Entity_Material', 'OakLight', 0.6)
M_PARQ = bpy.data.materials['20200606-02529-cest_Room_Entity_Material']   # herringbone (bedroom floors)
M_MARB = bpy.data.materials['20200606-32137-cest_Room_Entity_Material']   # white marble (ensuite)
M_MIRROR = mk('MirrorPanel', 'C9CDD1', 0.18, 0.35)
M_TOWEL = mk('TowelIvory', 'EFE4CD', 0.95)
M_OTTO = mk('OttomanLinen', 'C9B8A0', 0.9)

# --- SW spa terrace ----------------------------------------------------------
# Walls, in order from the tub: the door wall (travertine, y -5.14) with the
# glazed patio door, the piano room's west return (travertine), the upper
# storey above the fascia (board-marked concrete), the lobby block (dark
# timber cladding, west and north faces), and the pocket's east wall (brick).
# Each wall a different material so the enclosure reads as separate planes.
M_CONC = texmat_from('20200612-21477-cest', 'ConcreteRender', 0.92)
M_WENGE = texmat_from('bois_003_Wall_Entity_Material', 'WengeCladding', 0.55)
M_BRICK = texmat_from('brique_009_Wall_Entity_Material', 'BrickWall', 0.95)
M_BRONZE = mk('DoorBronze', '2A2622', 0.45, 0.3)
WALLMATS = {'FacadeSW', 'noir_001_Wall_Entity_Material', 'noir_001_Room_Entity_Material', 'fake_mat_251_251_251_255',
            'blanc_001_Wall_Entity_Material', 'Travertine', 'gris_004_Wall_Entity_Material', 'LobbyWall'}

def cut_opening(x1, x2, y1, y2, z1, z2, label, name_prefix=("Object_",), horizontal_at=None):
    """Carve a rectangular hole through source wall sheets: bisect every face
    that straddles the box (plus its edge neighbours, so the cut edge is
    shared) on the box's x/y/z bounds, then delete the pieces inside.
    horizontal_at=z limits the cut to flat faces at that height (a floor
    patch), leaving the walls and furniture standing on it untouched."""
    def flat_ok(ws):
        return horizontal_at is None or all(abs(w.z - horizontal_at) < 0.01 for w in ws)
    planes = ((Vector((x1, 0, 0)), Vector((1, 0, 0))), (Vector((x2, 0, 0)), Vector((1, 0, 0))),
              (Vector((0, 0, z1)), Vector((0, 0, 1))), (Vector((0, 0, z2)), Vector((0, 0, 1))),
              (Vector((0, y1, 0)), Vector((0, 1, 0))), (Vector((0, y2, 0)), Vector((0, 1, 0))))
    total = 0
    for ob in [o for o in sc.collection.all_objects if o.type == 'MESH' and o.name.startswith(name_prefix)]:
        mw = ob.matrix_world
        inv = mw.inverted()
        m3t = mw.to_3x3().transposed()
        bmc = bmesh.new()
        bmc.from_mesh(ob.data)
        def straddling():
            out = []
            for f in bmc.faces:
                ws = [mw @ v.co for v in f.verts]
                if (flat_ok(ws) and max(w.x for w in ws) > x1 and min(w.x for w in ws) < x2 and max(w.y for w in ws) > y1
                        and min(w.y for w in ws) < y2 and max(w.z for w in ws) > z1 and min(w.z for w in ws) < z2):
                    out.append(f)
            return out
        if not straddling():
            bmc.free()
            continue
        for co, no in planes:
            cand = straddling()
            if not cand:
                break
            faces = set(cand)
            for f in cand:
                for e in f.edges:
                    faces.update(e.link_faces)
            verts = {v for f in faces for v in f.verts}
            edges = {e for f in faces for e in f.edges}
            bmesh.ops.bisect_plane(bmc, geom=list(verts) + list(edges) + list(faces), dist=1e-4,
                                   plane_co=inv @ co, plane_no=(m3t @ no).normalized(),
                                   use_snap_center=False, clear_outer=False, clear_inner=False)
        doomed = []
        for f in bmc.faces:
            c = mw @ f.calc_center_median()
            if x1 < c.x < x2 and y1 < c.y < y2 and z1 < c.z < z2 and flat_ok([mw @ v.co for v in f.verts]):
                doomed.append(f)
        if doomed:
            bmesh.ops.delete(bmc, geom=doomed, context='FACES')
            total += len(doomed)
        bmc.to_mesh(ob.data)
        bmc.free()
        print(f"CUT {label}: {ob.name} -{len(doomed)} faces")
    bpy.context.view_layer.update()
    print(f"CUT {label}: {total} faces removed")

# Patio door. The source piano room has a 4.2 m sliding-door opening in its
# south wall (frame Object_67: posts x -10.33..-10.13 and -6.29..-6.09, head
# z 2.70..2.81) that led into a 0.5 m cavity closed by two solid exterior
# sheets (y -4.94 and -5.14), so from the piano it read as a navy niche.
# Carve both sheets between the posts, line the reveal with travertine and
# glaze the frame: a fixed pane at each end with a leaf slid open against it,
# leaving a 1.9 m walkable gap onto the deck.
DOOR_X1, DOOR_X2, DOOR_Z = -10.13, -6.29, 2.70
DOOR_CX = (DOOR_X1 + DOOR_X2) / 2
cut_opening(DOOR_X1, DOOR_X2, -5.25, -4.405, 0.05, DOOR_Z, "patio-door")
tex_box("PatioJambW", DOOR_X1 - 0.10, -4.82, 1.42, 0.10, 0.36, 1.42, M_TRAV)
tex_box("PatioJambE", DOOR_X2 + 0.10, -4.82, 1.42, 0.10, 0.36, 1.42, M_TRAV)
tex_box("PatioHead", DOOR_CX, -4.82, DOOR_Z + 0.07, (DOOR_X2 - DOOR_X1) / 2 + 0.10, 0.36, 0.07, M_TRAV)
# Threshold band along the whole wall foot at deck height (y -5.20..-4.40).
tex_box("PatioSill", -8.47, -4.80, 0.05, 2.95, 0.40, 0.05, M_TRAV)
PANE_W = (DOOR_X2 - DOOR_X1) / 4
def door_panel(name, x0, y, z_top):
    cx = x0 + PANE_W / 2
    add_box(f"{name}Rail0", cx, y, 0.14, PANE_W / 2, 0.022, 0.04, M_BRONZE)
    add_box(f"{name}Rail1", cx, y, z_top - 0.035, PANE_W / 2, 0.022, 0.035, M_BRONZE)
    add_box(f"{name}StileW", x0 + 0.022, y, (0.10 + z_top) / 2, 0.022, 0.022, (z_top - 0.10) / 2, M_BRONZE)
    add_box(f"{name}StileE", x0 + PANE_W - 0.022, y, (0.10 + z_top) / 2, 0.022, 0.022, (z_top - 0.10) / 2, M_BRONZE)
    if M_GLASSP:
        add_box(f"{name}Glass", cx, y, (0.18 + z_top - 0.07) / 2, PANE_W / 2 - 0.04, 0.004, (z_top - 0.07 - 0.18) / 2, M_GLASSP)
door_panel("PatioPaneW", DOOR_X1, -4.40, DOOR_Z)                     # fixed, outer track
door_panel("PatioLeafW", DOOR_X1 + 0.02, -4.33, DOOR_Z)              # slid open against it
door_panel("PatioPaneE", DOOR_X2 - PANE_W, -4.40, DOOR_Z)
door_panel("PatioLeafE", DOOR_X2 - PANE_W - 0.02, -4.33, DOOR_Z)
add_box("PatioTrack", DOOR_CX, -4.365, DOOR_Z - 0.012, (DOOR_X2 - DOOR_X1) / 2, 0.06, 0.012, M_BRONZE)
for nm, hx in (("PatioHandleW", DOOR_X1 + PANE_W + 0.02 - 0.045), ("PatioHandleE", DOOR_X2 - PANE_W - 0.02 + 0.045)):
    add_box(nm, hx, -4.33, 1.05, 0.012, 0.035, 0.16, M_BRONZE)

# Door wall and the piano room's west return: travertine over every layer
# (decimated triangles whose centres fell outside the first build's box
# stayed khaki, which showed as a diagonal seam).
retex_region(-11.5, -5.3, -5.4, -4.9, -0.3, 3.24, M_TRAV, "TerraceWallN", only_mats=WALLMATS, normal=(0, -1, 0))
retex_region(-11.3, -11.0, -5.5, -1.5, -0.3, 3.24, M_TRAV, "TerraceWallNW", only_mats=WALLMATS, normal=(-1, 0, 0))
# Chamfer slivers at the wall's west end (no dominant normal), plus a source
# facade fin (dark window-frame material, x -11.8, outside the parapet) that
# read as a dark wedge from the tub's north-west corner.
retex_region(-11.5, -10.9, -5.6, -4.3, -0.3, 3.24, M_TRAV, "TerraceWallWEnd", only_mats=WALLMATS)
region_delete_mats(-12.6, -11.45, -6.0, -3.5, -0.3, 3.6, {'fake_mat_6_5_5_255', 'fake_mat_69_64_65_255', 'noir_001_Wall_Entity_Material', 'noir_001_Room_Entity_Material'}, "west-facade-fin")
# Underside of the upper slab's 16 cm overhang, right above the fascia: teak to match.
retex_region(-11.4, -5.3, -5.45, -4.95, 3.20, 3.30, M_TEAK, "SlabEdgeSW", only_mats={'enduit_004_Room_Entity_Material', 'enduit_004_Wall_Entity_Material', 'blanc_001_ovcol565656colpic12contpic10_Room_Entity_Material'}, normal='down', scale=0.6, rot=math.pi / 2)
# Upper storey: board-marked concrete on every south-side facade face above
# the ground-floor walls (the SW bedroom wall over the fascia, the wall above
# the lobby and the covered walk, the SE terrace's upper faces).
retex_region(-11.6, -5.3, -5.6, -5.0, 3.24, 6.8, M_CONC, "FacadeSWUpper", only_mats=WALLMATS, normal=(0, -1, 0), scale=2.0)
retex_region(-11.6, 11.7, -10.6, -4.9, 3.24, 6.8, M_CONC, "FacadeSouthUpper", only_mats={'FacadeSW'}, normal='side', scale=2.0)
# Lobby block: dark timber cladding on its west face and on the north face
# that closes the pocket (walls, door head, the floor and ceiling slab edges).
retex_region(-7.72, -7.50, -9.9, -6.5, -0.1, 3.1, M_WENGE, "LobbyWestClad", only_objects=("Lobby",), normal=(-1, 0, 0))
retex_region(-7.72, -5.40, -6.70, -6.45, -0.1, 3.1, M_WENGE, "LobbyNorthClad", only_objects=("Lobby",), normal=(0, 1, 0))
# Pocket east wall (the library block's west face, x -5.48): brick.
retex_region(-5.6, -5.3, -6.7, -5.0, -0.3, 3.24, M_BRICK, "PocketBrick", only_mats=WALLMATS, normal=(-1, 0, 0), scale=0.8)
# Teak deck continues into the pocket so the terrace is one L-shaped floor.
add_box("DeckSWpocket", -6.62, -5.90, 0.07, 1.10, 0.70, 0.03, M_DECK)
# Fascia strip with downlights across the whole door wall (the lights sat
# inside the wall before, y -4.86, and never showed).
tex_box("SoffitSW", -8.47, -4.86, 3.20, 2.95, 0.40, 0.025, M_TEAK, scale=0.6, rot=math.pi / 2)
for i, x in enumerate((-10.75, -9.6, -8.47, -7.35, -6.2)):
    add_box(f"SoffitLightSW{i}", x, -5.205, 3.163, 0.07, 0.045, 0.012, M_GLOW)
for nm, rot in (("DeckSW", math.pi / 2), ("DeckSE", 0.0), ("DeckWalk", 0.0)):
    retex_region(-14, 14, -11, 0, -0.1, 0.2, M_TEAK, f"{nm}-teak", only_objects=(nm,), scale=0.75, rot=rot)
for nm in ("HotTubWallN", "HotTubWallS", "HotTubWallW", "HotTubWallENE", "HotTubWallESE", "HotTubStepOuter"):
    retex_region(-12, -7, -10, -4, -0.1, 1.0, M_TEAK, f"{nm}-teak", only_objects=(nm,), scale=0.5)
for nm, (cx, cy, hx, hy) in {"TubCopN": (tub_x, -5.70, 1.48, 0.20), "TubCopS": (tub_x, -8.60, 1.48, 0.20),
                             "TubCopW": (-11.15, tub_y, 0.20, 1.29), "TubCopENE": (-8.35, -6.14, 0.20, 0.44),
                             "TubCopESE": (-8.35, -8.16, 0.20, 0.44)}.items():
    tex_box(nm, cx, cy, 0.735, hx, hy, 0.018, M_TRAV)
# Rolled towels on the north-east coping (the south coping holds the hot tub
# regulars' drinks, rovers_figures.TUB_SPOT).
for i, (tx, ty) in enumerate(((-8.35, -5.95), (-8.35, -6.12))):
    bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=0.065, depth=0.30, location=(tx, ty, 0.82), rotation=(0, math.pi / 2, 0))
    bpy.context.active_object.name = f"TowelSW{i}"
    bpy.context.active_object.data.materials.append(M_TOWEL)
for i, (px, py) in enumerate(((-10.85, -9.40), (-8.45, -9.40))):
    tex_box(f"PlanterSW{i}", px, py, 0.27, 0.28, 0.22, 0.24, M_TRAV)
    plant(f"PlanterSWplant{i}", px, py, 0.50, 1.0, 0.6 + i)
# Sconces on the travertine piers either side of the door.
for i, x in enumerate((-10.75, -5.80)):
    add_box(f"SconceSW{i}", x, -5.15, 2.05, 0.05, 0.03, 0.14, M_GLOW)

# Every add_box is its own draw call on the Quest; fold the door's parts and the
# terrace glow bits into one mesh per material (world positions are kept).
def join_objects(name, prefixes):
    obs = [o for o in sc.collection.all_objects if o.type == 'MESH' and o.name.startswith(tuple(prefixes))]
    if len(obs) < 2:
        return
    bpy.ops.object.select_all(action='DESELECT')
    for o in obs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = obs[0]
    bpy.ops.object.join()
    bpy.context.active_object.name = name
    bpy.ops.object.select_all(action='DESELECT')
    print(f"JOIN {name}: {len(obs)} objects -> 1")

join_objects("PatioGlass", ("PatioPaneWGlass", "PatioPaneEGlass", "PatioLeafWGlass", "PatioLeafEGlass"))
join_objects("PatioFrame", ("PatioPane", "PatioLeaf", "PatioTrack", "PatioHandle"))
join_objects("PatioStone", ("PatioJamb", "PatioHead", "PatioSill"))
join_objects("TerraceGlowSW", ("SoffitLightSW", "SconceSW"))

# --- Patio sectional: woven cushion fabric and dark resin wicker frame -------
# Flat ivory on flat charcoal read as one blob against the grey patio tiles.
# Scoped to the sectional's box so the shared linen/frame materials elsewhere
# (curtains, bedding, the piano-room door frame) are untouched.
PATIO_SOFA = (-4.3, -0.6, 4.9, 8.6, 0.05, 1.2)
M_PATIO_FABRIC = artmat('fabric-oatmeal.png', 'PatioCushionCanvas', 0.95)
M_PATIO_WICKER = artmat('wicker-espresso.png', 'PatioResinWicker', 0.7)
retex_region(*PATIO_SOFA, M_PATIO_FABRIC, "PatioSofaCushions", only_objects=("Object_54",),
             only_mats={"fake_mat_224_230_228_255"}, scale=0.25)
retex_region(*PATIO_SOFA, M_PATIO_WICKER, "PatioSofaFrame", only_objects=("Object_67",),
             only_mats={"fake_mat_69_64_65_255"}, scale=0.3)

# --- Capri beach club: open spa and conversation lounge ---------------------
exec(compile(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "build-spa.py")).read(), "build-spa.py", "exec"))

# --- Parisian coffee terrace: an architectural shopfront, not a scenery card.
# This is the kitchen's SOUTH wall. Keep the working base counter; remove
# backsplash, upper cupboards and all exterior wall sheets through the hatch.
cut_opening(8.12, 10.78, -4.52, -3.03, 1.12, 2.62, "cafe-serving-window")
M_CAFE_GREEN = mk("CafeBottleGreen", "183D32", .62)
M_CAFE_CREAM = mk("CafeCanvas", "E9DDC2", .95)
M_CAFE_BRASS = mk("CafeAgedBrass", "A8894F", .4, .65)
M_CAFE_STONE = texmat_from('20210309-221754-cet_Wall_Entity_Material', 'CafeLimestone', .88)
M_CAFE_GROUT = mk("CafeGrout", "888275", .95)
M_CAFE_RATTAN = mk("CafeRattan", "AA8152", .85)

# Replace the over-sized source planters and block-chair bases, retaining the
# two seat anchors and a clear 1.2 m approach from the covered walk.
for nm in ("TerrSEplant1", "TerrSEplant2", "TerrSEplant3", "BistroPlinth0", "BistroPlinth1",
           "BistroBack0", "BistroBack1"):
    ob = bpy.data.objects.get(nm)
    if ob:
        bpy.data.objects.remove(ob, do_unlink=True)
for nm in ("DeckSE", "DeckWalk"):
    ob = bpy.data.objects[nm]
    ob.location.z -= .015  # bedding below the flags, never coplanar with them
    ob.data.materials.clear()
    ob.data.materials.append(M_CAFE_GROUT)
    for f in ob.data.polygons:
        f.material_index = 0
# Flush limestone flags with staggered joints continue to the existing lobby.
# Their highest point stays at .10, identical to the previous deck/nav level.
for row in range(9):
    y0, y1 = -9.72 + row * .59, min(-4.42, -9.72 + (row + 1) * .59)
    left = 2.58 if y1 <= -6.35 else 6.12
    x = left - (.45 if row % 2 else 0)
    col = 0
    while x < 11.36:
        lo, hi = max(left, x), min(11.36, x + .9)
        if hi - lo > .03:
            tex_box(f"CafePaving_{row}_{col}", (lo+hi)/2, (y0+y1)/2, .093,
                    (hi-lo)/2-.005, (y1-y0)/2-.005, .007, M_CAFE_STONE, scale=.65)
        x += .9
        col += 1
# Shopfront piers, low panels and continuous cornice share one datum; the
# limestone reveals line the full wall cavity rather than exposing cut edges.
# The west return is x=6.086, not the old deck edge x=7.0. Wrap the
# stone around that actual wall and fill the previously bare floor strip.
tex_box("CafeStoneReturn",6.115,-5.42,1.61,.025,.98,1.51,M_CAFE_STONE,scale=.7)
tex_box("CafeStoneReturnCornice",6.15,-5.42,3.235,.07,.98,.035,M_CAFE_STONE)
add_box("CafeJoineryReturnFrieze",6.145,-5.42,3.02,.025,.98,.19,M_CAFE_GREEN)
for i, (x, hx) in enumerate(((6.30,.20),(7.94,.18),(11.02,.24))):
    tex_box(f"CafeStonePier{i}", x,-4.49,1.45,hx,.06,1.35,M_CAFE_STONE,scale=.7)
# Stone lines only the wall's own thickness (exterior face y -4.52 to the
# kitchen backsplash at -4.20). The cut through the upper cupboards behind it
# (fronts at y -3.72) is closed with cabinet-finish cheeks and a soffit, so
# from inside the kitchen the hatch reads as a cupboard-framed window, not a
# stone tunnel standing in the room.
M_KCAB = bpy.data.materials['fake_mat_69_64_65_255']   # the kitchen's own cabinet grey
for x in (8.10,10.80):
    add_box("CafeJoineryJamb",x,-4.53,1.83,.055,.075,.79,M_CAFE_GREEN)
    tex_box("CafeStoneReveal",x,-4.36,1.87,.025,.16,.75,M_CAFE_STONE)
    add_box("KitchenHatchCheek",x,-3.96,1.87,.025,.24,.75,M_KCAB)
tex_box("CafeStoneLintelReveal",9.45,-4.36,2.62,1.36,.16,.025,M_CAFE_STONE)
add_box("KitchenHatchSoffit",9.45,-3.96,2.62,1.36,.24,.025,M_KCAB)
tex_box("CafeStoneServingCounter",9.45,-4.47,1.10,1.31,.29,.04,M_MARB)
add_box("CafeJoineryLower",9.45,-4.51,.57,1.35,.06,.47,M_CAFE_GREEN)
for x in (8.57,9.45,10.33):
    for z in (.20,.93):
        add_box("CafeBrassPanelRail",x,-4.577,z,.37,.009,.009,M_CAFE_BRASS)
    for xx in (x-.37,x+.37):
        add_box("CafeBrassPanelStile",xx,-4.577,.565,.009,.009,.365,M_CAFE_BRASS)
add_box("CafeJoineryFascia",8.71,-4.53,3.02,2.61,.085,.19,M_CAFE_GREEN)
tex_box("CafeStoneCornice",8.71,-4.53,3.235,2.67,.14,.035,M_CAFE_STONE)
for x,hx in ((6.30,.20),(9.54,1.83)):
    tex_box("CafeStonePlinth",x,-4.53,.17,hx,.10,.07,M_CAFE_STONE)
# A striped retractable-style canopy is attached below the cornice, with no
# posts in the circulation path. Modest depth preserves the skyline outlook.
for i in range(20):
    x=6.10+(i+.5)*.261
    add_box("CafeCanvasCanopy",x,-5.05,2.72,.1305,.62,.014,
            M_CAFE_CREAM if i%2 == 0 else M_CAFE_GREEN)
    bpy.context.object.rotation_euler.x=math.radians(12)
    add_box("CafeCanvasValance",x,-5.65,2.52,.1305,.018,.075,
            M_CAFE_CREAM if i%2 == 0 else M_CAFE_GREEN)

def cafe_text(name, body, pos, size, material):
    bpy.ops.object.text_add(location=pos, rotation=(math.pi/2,0,0))
    ob=bpy.context.object
    ob.name=name
    ob.data.body=body
    ob.data.align_x='CENTER'
    ob.data.size=size
    ob.data.extrude=.001
    ob.data.materials.append(material)
    bpy.ops.object.convert(target='MESH')
cafe_text("CafeLetteringName", "CAFÉ DU PARC", (8.71,-4.624,2.97), .19, M_CAFE_CREAM)
# A real open door beside the hatch, through every wall/cabinet layer.
# The leaf is parked outward against the west jamb, clear of the 1.1 m route.
cut_opening(6.52, 7.72, -4.62, -2.70, .105, 2.66, "cafe-outside-door")
# As at the hatch: stone through the wall (y -4.62..-4.20), cabinet-finish
# end panels across the cut cupboard run (-4.20..-3.72), and nothing beyond
# the cupboard fronts. The old 1.9 m stone reveals stood a metre proud of the
# cabinets inside the kitchen.
for x in (6.49,7.75):
    tex_box("CafeStoneDoorReveal",x,-4.41,1.38,.03,.21,1.28,M_CAFE_STONE)
    add_box("KitchenDoorCheek",x,-3.96,1.38,.03,.24,1.28,M_KCAB)
    add_box("CafeJoineryDoorJamb",x,-4.57,1.38,.045,.045,1.28,M_CAFE_GREEN)
tex_box("CafeStoneDoorHead",7.12,-4.41,2.68,.66,.21,.025,M_CAFE_STONE)
add_box("KitchenDoorSoffit",7.12,-3.96,2.68,.66,.24,.025,M_KCAB)
tex_box("CafeStoneDoorThreshold",7.12,-4.17,.077,.60,.45,.023,M_CAFE_STONE)
# Glazed leaf, opened ninety degrees; slim brass pull on its free end.
for y in (-4.59,-5.59):
    add_box("CafeJoineryDoorLeafStile",6.44,y,1.34,.035,.04,1.23,M_CAFE_GREEN)
for z in (.15,.70,2.53):
    add_box("CafeJoineryDoorLeafRail",6.44,-5.09,z,.035,.54,.04,M_CAFE_GREEN)
add_box("CafeJoineryDoorLeafLower",6.44,-5.09,.43,.026,.50,.24,M_CAFE_GREEN)
if M_GLASSP:
    add_box("CafeDoorGlass",6.44,-5.09,1.62,.008,.49,.87,M_GLASSP)
add_box("CafeBrassDoorPull",6.38,-5.43,1.10,.03,.015,.14,M_CAFE_BRASS)
# Finish the covered-walk wall and cut interior surfaces as continuous plaster.
M_CAFE_PLASTER = mk("CafeWarmPlaster", "E9DDC8", .94)
retex_region(2.55,6.14,-6.45,-6.1,.11,3.23,M_CAFE_PLASTER,"CafeWalkPlaster",only_mats=WALLMATS,normal=(0,-1,0))
retex_region(6.1,11.35,-4.55,-2.95,1.15,3.23,M_CAFE_PLASTER,"CafeKitchenPlaster",only_mats=WALLMATS)
for x in (7.95,11.02):
    add_box("CafeBrassLanternMount",x,-4.58,2.32,.06,.025,.12,M_CAFE_BRASS)
    add_box("CafeJoineryLanternCap",x,-4.72,2.45,.09,.10,.025,M_CAFE_GREEN)
    add_box("CafeGlowLantern",x,-4.72,2.30,.06,.065,.12,M_GLOW)
    add_box("CafeJoineryLanternBase",x,-4.72,2.16,.09,.09,.025,M_CAFE_GREEN)
# Slim café chairs: keep the proven seat position and height exactly intact.
for i,(cy,backy) in enumerate(((-6.55,-6.28),(-8.05,-8.32))):
    ob=bpy.data.objects[f"BistroSeat{i}"]
    ob.data.materials.clear()
    ob.data.materials.append(M_CAFE_RATTAN)
    for dx in (-.18,.18):
        for dy in (-.17,.17):
            add_box("CafeJoineryChairLeg",9.5+dx,cy+dy,.275,.018,.018,.175,M_CAFE_GREEN)
        add_box("CafeJoineryChairBackPost",9.5+dx,backy,.70,.018,.018,.25,M_CAFE_GREEN)
    for z in (.68,.76,.84,.92):
        add_box("CafeRattanChairBack",9.5,backy,z,.20,.018,.023,M_CAFE_RATTAN)
retex_region(9,10,-8,-6,0,1,M_MARB,"cafe-marble-table",only_objects=("BistroTop",),scale=1)
# Draped square gingham linen over the round bistro table, with a soft hem.
import os
M_GINGHAM = mk("CafeGingham", "FFFFFF", .95)
nt = M_GINGHAM.node_tree
tex = nt.nodes.new('ShaderNodeTexImage')
tex.image = bpy.data.images.load(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'art', 'gingham.png'))
nt.links.new(tex.outputs['Color'], nt.nodes['Principled BSDF'].inputs['Base Color'])
vs, fs, uvcoords = [], [], []
N=40
for j in range(N+1):
    for i in range(N+1):
        u,v=(i/N-.5)*.96,(j/N-.5)*.96
        r=math.hypot(u,v)
        a=math.atan2(v,u)
        over=max(0,r-.386)
        rr=min(r,.386)+over*.17
        z=.819-over*.93 + (math.sin(a*16)*.008*min(1,over/.05) if over else 0)
        vs.append((9.5+rr*math.cos(a),-7.3+rr*math.sin(a),z))
        uvcoords.append((i/N,j/N))
for j in range(N):
    for i in range(N):
        k=j*(N+1)+i
        fs.append((k,k+1,k+N+2,k+N+1))
me=bpy.data.meshes.new('CafeTablecloth'); me.from_pydata(vs,[],fs); me.materials.append(M_GINGHAM)
uv=me.uv_layers.new()
for f in me.polygons:
    f.use_smooth=True
    for loop in f.loop_indices: uv.data[loop].uv=uvcoords[me.loops[loop].vertex_index]
o=bpy.data.objects.new('CafeTablecloth',me); sc.collection.objects.link(o)
# Small glazed ivory bud vase with five dimensional roses and green stems.
M_VASE=mk('CafeIvoryCeramic','EEE6D4',.24)
M_ROSE=mk('CafeRosePetal','A62943',.72)
M_ROSE_LIGHT=mk('CafeRosePetalLight','D45E70',.78)
M_STEM=mk('CafeRoseGreen','36543A',.85)
profile=[(.0,.052),(.02,.074),(.11,.065),(.17,.033),(.205,.036),(.21,.028),(.18,.026)]
vv=[]; ff=[]
for z,r in profile:
    for i in range(24):
        a=i*math.tau/24; vv.append((9.5+r*math.cos(a),-7.3+r*math.sin(a),.824+z))
for j in range(len(profile)-1):
    for i in range(24):
        k=j*24+i; ff.append((k,j*24+(i+1)%24,(j+1)*24+(i+1)%24,k+24))
me=bpy.data.meshes.new('CafeRoseVase'); me.from_pydata(vv,[],ff); me.materials.append(M_VASE)
o=bpy.data.objects.new('CafeRoseVase',me); sc.collection.objects.link(o)
for f in me.polygons:f.use_smooth=True
for n,(dx,dy,z) in enumerate(((0,0,1.24),(.07,.025,1.19),(-.065,.025,1.20),(.018,-.07,1.17),(-.03,.075,1.16))):
    base=Vector((9.5,-7.3,1.00)); tip=Vector((9.5+dx,-7.3+dy,z))
    bpy.ops.mesh.primitive_cylinder_add(vertices=8,radius=.003,depth=(tip-base).length,location=(tip+base)/2)
    ob=bpy.context.object; ob.name='CafeRoseStem'; ob.rotation_euler=(tip-base).to_track_quat('Z','Y').to_euler(); ob.data.materials.append(M_STEM)
    for ring in range(3):
        count=5 if ring else 3
        for k in range(count):
            angle=math.tau*k/count+ring*.65+n
            radius=.010+ring*.010
            bpy.ops.mesh.primitive_uv_sphere_add(segments=8,ring_count=4,radius=1,location=(tip.x+radius*math.cos(angle),tip.y+radius*math.sin(angle),z+.02-ring*.011))
            ob=bpy.context.object; ob.name='CafeRosePetal'; ob.scale=(.022,.010,.024); ob.rotation_euler=(.2,ring*.3,angle+math.pi/2); ob.data.materials.append(M_ROSE_LIGHT if ring==2 else M_ROSE)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=8,ring_count=4,radius=1,location=(tip.x+.025,tip.y,z-.11))
    ob=bpy.context.object; ob.name='CafeRoseLeaf'; ob.scale=(.038,.014,.005); ob.rotation_euler.y=-.45; ob.data.materials.append(M_STEM)
join_objects('CafeRoseBouquet',('CafeRosePetal','CafeRoseStem','CafeRoseLeaf'))

# --- The café's regulars (cafe_figures.py): a second bistro table for the
# couple, both chairs on its south side facing the café front (Paris style);
# the mime's rattan chair by the café front; an espresso machine at the east
# end of the marble serving counter (the chef pulls the couple's espressos
# there); an espresso and a slice of cake at each place on the visitors' table.
if os.path.dirname(os.path.abspath(__file__)) not in sys.path:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dinner_figures as _DF  # noqa: F401  (cafe_figures imports it; load order)
import cafe_figures as CFG


def cafe_cloth(name, cx, cy):
    """The gingham square draped over a round bistro top (as CafeTablecloth)."""
    vs, fs, uvs = [], [], []
    n = 40
    for j in range(n + 1):
        for i in range(n + 1):
            u, v = (i / n - .5) * .96, (j / n - .5) * .96
            r = math.hypot(u, v)
            a = math.atan2(v, u)
            over = max(0, r - .386)
            rr = min(r, .386) + over * .17
            z = .819 - over * .93 + (math.sin(a * 16) * .008 * min(1, over / .05) if over else 0)
            vs.append((cx + rr * math.cos(a), cy + rr * math.sin(a), z))
            uvs.append((i / n, j / n))
    for j in range(n):
        for i in range(n):
            k = j * (n + 1) + i
            fs.append((k, k + 1, k + n + 2, k + n + 1))
    me = bpy.data.meshes.new(name)
    me.from_pydata(vs, [], fs)
    me.materials.append(M_GINGHAM)
    uv = me.uv_layers.new()
    for f in me.polygons:
        f.use_smooth = True
        for loop in f.loop_indices:
            uv.data[loop].uv = uvs[me.loops[loop].vertex_index]
    o = bpy.data.objects.new(name, me)
    sc.collection.objects.link(o)
    return o


def cafe_chair(prefix, x, y, yaw_deg):
    """A slim café chair (rattan seat and back, green legs) facing yaw (rovers_figures: 0 faces +y)."""
    a = math.radians(yaw_deg)
    fwd, rgt = Vector((-math.sin(a), math.cos(a))), Vector((math.cos(a), math.sin(a)))
    parts = []

    def box(name, lx, ly, z, hx, hy, hz, mat):
        p = Vector((x, y)) + rgt * lx + fwd * ly
        add_box(name, p.x, p.y, z, hx, hy, hz, mat)
        ob = bpy.context.active_object
        ob.rotation_euler.z = a
        parts.append(ob)
    box(f"{prefix}Seat", 0, 0, .47, .21, .21, .03, M_CAFE_RATTAN)
    for lx in (-.18, .18):
        for ly in (-.17, .17):
            box("CafeJoineryChairLeg", lx, ly, .275, .018, .018, .175, M_CAFE_GREEN)
        box("CafeJoineryChairBackPost", lx, -.27, .70, .018, .018, .25, M_CAFE_GREEN)
    for z in (.68, .76, .84, .92):
        box("CafeRattanChairBack", 0, -.27, z, .20, .018, .023, M_CAFE_RATTAN)
    return parts


tx, ty = CFG.TABLE
bpy.ops.mesh.primitive_cylinder_add(radius=0.38, depth=0.035, location=(tx, ty, 0.795))
bpy.context.active_object.name = "CafeCoupleTop"
bpy.context.active_object.data.materials.append(M_MARB)
bpy.ops.mesh.primitive_cylinder_add(radius=0.045, depth=0.70, location=(tx, ty, 0.43))
bpy.context.active_object.name = "CafeCoupleStem"
bpy.context.active_object.data.materials.append(M_RAIL)
bpy.ops.mesh.primitive_cylinder_add(radius=0.20, depth=0.03, location=(tx, ty, 0.095))
bpy.context.active_object.name = "CafeCoupleBase"
bpy.context.active_object.data.materials.append(M_RAIL)
cafe_cloth("CafeCoupleCloth", tx, ty)
for who, (sx, sy) in CFG.SEAT.items():
    cafe_chair(f"CafeCoupleChair{who}", sx, sy, 0.0)
cafe_chair("CafeMimeChair", CFG.MIME_CHAIR[0], CFG.MIME_CHAIR[1], CFG.MIME_CHAIR_YAW)
# Espresso machine: a polished steel body, brass group head and cup rail, cups warming on top.
mx, my, mz = CFG.MACHINE
M_ESP_STEEL = mk("CafeEspressoSteel", "C9CCD0", .22, .85)
M_ESP_BLACK = mk("CafeEspressoBlack", "1C1C1E", .4)
add_box("CafeEspressoBody", mx, my + .03, mz + .19, .17, .14, .19, M_ESP_STEEL)
add_box("CafeEspressoPanel", mx, my - .113, mz + .25, .15, .006, .09, M_ESP_BLACK)
add_box("CafeEspressoTray", mx, my - .13, mz + .012, .16, .07, .012, M_ESP_STEEL)
bpy.ops.mesh.primitive_cylinder_add(radius=0.035, depth=0.06, location=(CFG.SPOUT.x, CFG.SPOUT.y + .02, mz + .15))
bpy.context.active_object.name = "CafeEspressoGroup"
bpy.context.active_object.data.materials.append(M_CAFE_BRASS)
bpy.ops.mesh.primitive_cylinder_add(radius=0.012, depth=0.16, location=(CFG.SPOUT.x, CFG.SPOUT.y - .04, mz + .12),
                                    rotation=(math.pi / 2, 0, 0))
bpy.context.active_object.name = "CafeEspressoHandle"
bpy.context.active_object.data.materials.append(M_ESP_BLACK)
bpy.ops.mesh.primitive_cylinder_add(radius=0.006, depth=0.14, location=(mx + .14, my - .12, mz + .16),
                                    rotation=(0.35, 0, 0))
bpy.context.active_object.name = "CafeEspressoWand"
bpy.context.active_object.data.materials.append(M_ESP_STEEL)
M_CUP = mk("CafeCupChina", "F6F3EC", .3)
M_COFFEE = mk("CafeCoffee", "3A2214", .25)
for i in range(4):
    bpy.ops.mesh.primitive_cylinder_add(radius=0.028, depth=0.045, location=(mx - .11 + i * .073, my + .05, mz + .405))
    bpy.context.active_object.name = "CafeEspressoWarmCup"
    bpy.context.active_object.data.materials.append(M_CUP)
join_objects("CafeEspresso", ("CafeEspresso",))
# The visitors' table: an espresso and a slice of strawberry gâteau at each place.
M_SPONGE = mk("CafeCakeSponge", "E8C890", .8)
M_CREAM = mk("CafeCakeCream", "F6EFE4", .7)
M_BERRY = mk("CafeCakeBerry", "C0283A", .35)
for side, (cup, cake) in CFG.JAY_SETS.items():
    z0 = cup.z
    bpy.ops.mesh.primitive_cylinder_add(radius=0.058, depth=0.008, location=(cup.x, cup.y, z0 + .004))
    bpy.context.active_object.name = "CafeSetSaucer"
    bpy.context.active_object.data.materials.append(M_CUP)
    bpy.ops.mesh.primitive_cone_add(radius1=0.026, radius2=0.034, depth=0.05, location=(cup.x, cup.y, z0 + .035))
    bpy.context.active_object.name = "CafeSetCup"
    bpy.context.active_object.data.materials.append(M_CUP)
    bpy.ops.mesh.primitive_cylinder_add(radius=0.030, depth=0.004, location=(cup.x, cup.y, z0 + .054))
    bpy.context.active_object.name = "CafeSetCoffee"
    bpy.context.active_object.data.materials.append(M_COFFEE)
    bpy.ops.mesh.primitive_cylinder_add(radius=0.085, depth=0.008, location=(cake.x, cake.y, z0 + .004))
    bpy.context.active_object.name = "CafeSetPlate"
    bpy.context.active_object.data.materials.append(M_CUP)
    # a wedge of gâteau, its point towards the table centre
    d = Vector((9.50 - cake.x, -7.30 - cake.y, 0)).normalized()
    pp = Vector((-d.y, d.x, 0))
    toward = math.atan2(d.y, d.x)
    c0 = Vector((cake.x, cake.y, 0))
    cb = bmesh.new()
    for zz in (z0 + .008, z0 + .058):
        for q in (c0 + d * .055, c0 - d * .045 + pp * .042, c0 - d * .045 - pp * .042):
            cb.verts.new((q.x, q.y, zz))
    cb.verts.ensure_lookup_table()
    v = cb.verts
    for f in ((0, 2, 1), (3, 4, 5), (0, 1, 4, 3), (1, 2, 5, 4), (2, 0, 3, 5)):
        cb.faces.new([v[i] for i in f])
    me = bpy.data.meshes.new("CafeSetCake")
    cb.to_mesh(me)
    cb.free()
    me.materials.append(M_SPONGE)
    ob = bpy.data.objects.new("CafeSetCake", me)
    sc.collection.objects.link(ob)
    add_box("CafeSetCakeCream", cake.x - .01 * math.cos(toward), cake.y - .01 * math.sin(toward), z0 + .062,
            .045, .045, .004, M_CREAM)
    bpy.context.active_object.rotation_euler.z = toward
    bpy.ops.mesh.primitive_uv_sphere_add(segments=8, ring_count=5, radius=0.012,
                                         location=(cake.x - .02 * math.cos(toward), cake.y - .02 * math.sin(toward), z0 + .072))
    bpy.context.active_object.name = "CafeSetBerry"
    bpy.context.active_object.data.materials.append(M_BERRY)
join_objects("CafeSet", ("CafeSet",))

# Low planting defines the frontage without blocking the hatch or chairs.
for x in (10.95,):
    tex_box("CafeStonePlanter",x,-4.98,.32,.24,.24,.22,M_CAFE_STONE)
    plant("CafePlant",x,-4.98,.46,.42,.5)
join_objects("CafeStonework", ("CafeStone", "CafePaving"))
join_objects("CafeJoinery", ("CafeJoinery",))
join_objects("CafeMetalwork", ("CafeBrass",))
join_objects("CafeAwning", ("CafeCanvas",))
join_objects("CafeLettering", ("CafeLettering",))
join_objects("CafeChairWeave", ("CafeRattan",))
join_objects("CafeLanternGlow", ("CafeGlow",))
join_objects("KitchenCutFinish", ("KitchenHatch", "KitchenDoor"))

# --- Gym: the global palette spilled navy, teal and espresso into this room.
# Warm white walls, mirror panels, herringbone floor.
GYM = (-4.65, -0.95, -6.85, -1.70)  # room continues to the north wall at y=-1.80
recolor_region(*GYM, 3.45, 6.35, "E6DFD3", rough=0.9, label="GymWall",
               only_mats={'blanc_001_Wall_Entity_Material', 'beige_006_Wall_Entity_Material',
                          'enduit_004_Wall_Entity_Material', 'gris_002_Wall_Entity_Material', 'FacadeSW'})
recolor_region(*GYM, 4.75, 6.35, "E6DFD3", rough=0.9, label="GymWallUpper", only_mats={'fake_mat_35_32_34_255'}, normal='side')
recolor_region(*GYM, 3.45, 6.35, "E6DFD3", rough=0.9, label="GymWallPanels", only_mats={'fake_mat_35_32_34_255'}, normal='side', min_area=0.15)
recolor_region(*GYM, 3.45, 6.35, "C9CDD1", rough=0.18, metal=0.35, label="GymMirror", only_mats={'fake_mat_157_154_155_255'})
# West wall of the gym/hall: full-height espresso panels (the blind material) at x -5.3.
recolor_region(-5.6, -5.0, -7.0, -1.7, 3.45, 6.4, "E6DFD3", rough=0.9, label="GymWallWest",
               only_mats={'fake_mat_6_5_5_255'}, normal='side', min_area=1.0)
# The open gym/hall floor is one large slab that reaches under the north wall
# and out to the west facade, so the floor box is wider than the room.
retex_region(-5.5, -0.95, -6.85, -3.9, 3.45, 3.62, M_PARQ, "GymFloor",
             only_mats={'fake_mat_6_5_5_255', '20200803-11010-cest_Room_Entity_Material',
                        'enduit_004_Room_Entity_Material', 'parquet_022_Room_Entity_Material'}, normal='up')

# --- NW bedroom walk-in closet: a bare dark-grey wardrobe carcass with a
# black floor behind a closed glass door. Open the door, lay the bedroom's
# herringbone, plaster the walls, light-oak shelves, rails, mirror, ottoman,
# ceiling light.
CL = (-11.15, -7.30, 0.85, 3.45)
region_delete_mats(-10.05, -8.03, 3.40, 3.65, 3.55, 5.72, {GLASS_MAT}, "closet-door-panes")
retex_region(*CL, 3.45, 3.62, M_PARQ, "ClosetFloor",
             only_mats={'fake_mat_6_5_5_255', 'fake_mat_35_32_34_255', 'gris_006_Room_Entity_Material',
                        'enduit_004_Room_Entity_Material'}, normal='up')
recolor_region(*CL, 6.0, 6.45, "F1ECE4", rough=0.9, label="ClosetCeil", only_mats={'fake_mat_35_32_34_255'}, normal='down')
retex_region(*CL, 3.62, 6.0, M_OAKL, "ClosetShelvesUp", only_mats={'fake_mat_35_32_34_255'}, normal='up', scale=0.8)
retex_region(*CL, 3.62, 6.0, M_OAKL, "ClosetShelvesDown", only_mats={'fake_mat_35_32_34_255'}, normal='down', scale=0.8)
recolor_region(*CL, 3.45, 6.45, "E7E0D4", rough=0.9, label="ClosetWall", only_mats={'fake_mat_35_32_34_255'}, normal='side')
recolor_region(*CL, 3.45, 6.45, "B9B3AA", rough=0.4, metal=0.3, label="ClosetRail", only_mats={'fake_mat_196_192_184_255'})
add_box("ClosetLight", -9.2, 2.45, 6.22, 0.9, 0.35, 0.015, M_GLOW)
# Full-length reflecting mirror on the bedroom's south wall (navy run between
# the closet opening and the entry door, wall face y 3.63). The empty is tagged
# `mirror` by inject-hubs.mjs; the client puts a Reflector plane on it, sized by
# the node's scale (Blender x = width, z = height) and facing the node's -y.
# Rotated 180 degrees so it faces north into the room. Dark frame behind it.
# (The room is on the +y side of this wall: the first placement put both
# inside the wall and nothing showed.)
add_box("MirrorFrameNW", -7.45, 3.647, 4.50, 0.50, 0.014, 1.00, M_DARK)
_mir = bpy.data.objects.new("Mirror_NW", None)
_mir.location = (-7.45, 3.668, 4.50)
_mir.rotation_euler = (0.0, 0.0, math.pi)
_mir.scale = (0.92, 1.0, 1.92)
sc.collection.objects.link(_mir)
add_box("ClosetMirror", -9.2, 1.432, 4.80, 0.55, 0.006, 1.05, M_MIRROR)
add_box("ClosetOttoman", -9.2, 2.30, 3.70, 0.45, 0.22, 0.19, M_OTTO)

# --- Ensuite behind the closet: the camel recolour hit its white fixtures ----
EN = (-11.15, -7.30, -1.75, 0.80)
recolor_region(*EN, 3.45, 6.45, "F0ECE6", rough=0.85, label="EnsuiteWhite", only_mats={'fake_mat_251_251_251_255'})
recolor_region(*EN, 3.45, 6.45, "F0ECE6", rough=0.85, label="EnsuiteWalls",
               only_mats={'fake_mat_35_32_34_255', 'beige_006_Wall_Entity_Material'}, normal='side', min_area=0.15)
# Inner faces of the ensuite's north (wardrobe back) and south walls sit just
# outside the room box; pick them by facing direction so the closet and the
# SW bedroom sides of those walls keep their own colours.
recolor_region(-11.4, -7.2, 0.75, 0.92, 3.45, 6.45, "F0ECE6", rough=0.85, label="EnsuiteWallN",
               only_mats={'fake_mat_35_32_34_255', 'beige_006_Wall_Entity_Material'}, normal=(0, -1, 0), min_area=0.15)
recolor_region(-11.4, -7.2, -2.0, -1.5, 3.45, 6.45, "F0ECE6", rough=0.85, label="EnsuiteWallS",
               only_mats={'fake_mat_35_32_34_255', 'beige_006_Wall_Entity_Material'}, normal=(0, 1, 0), min_area=0.15)
retex_region(*EN, 3.45, 3.62, M_MARB, "EnsuiteFloor", only_mats={'fake_mat_6_5_5_255', 'fake_mat_35_32_34_255'}, normal='up')

# --- Sky den: drop the two source tub chairs (Object_56 shells, Object_65
# pillows) that jammed the room against the sofa. The den is entered from the
# hall through its north double door (x 0.0..1.45): take the closed glass
# leaves and their meeting stile out so the doorway reads open.
for _nm in ("Object_56", "Object_65"):
    _ob = bpy.data.objects.get(_nm)
    _bmd = bmesh.new(); _bmd.from_mesh(_ob.data)
    _doomed = [f for f in _bmd.faces if 1.6 < (_ob.matrix_world @ f.calc_center_median()).x < 3.75
               and -9.35 < (_ob.matrix_world @ f.calc_center_median()).y < -7.22
               and 3.45 < (_ob.matrix_world @ f.calc_center_median()).z < 4.35]
    bmesh.ops.delete(_bmd, geom=_doomed, context='FACES'); _bmd.to_mesh(_ob.data); _bmd.free()
    print(f"DEN CHAIRS {_nm}: -{len(_doomed)} faces")
region_delete_mats(0.02, 1.43, -7.30, -7.05, 3.52, 5.80, {GLASS_MAT}, "den-door-panes")
region_delete_mats(0.55, 0.85, -7.30, -7.05, 3.52, 5.60, {'fake_mat_35_32_34_255'}, "den-door-stile")
cut_opening(0.70, 0.80, -7.25, -7.10, 3.52, 5.60, "den-door-mullion")   # the stile's DenWalls-recoloured core

# --- Sauna: the tiered-bench room west of the den (x -3.0..-0.70, y -9.68..
# -6.70, floor 3.50, ceiling 6.27) was only reachable through the den's glass
# west door. Seal that side, open a doorway from the gym through the mirrored
# south wall, strip the source benches and line the room in cedar.
M_CEDAR = artmat('sauna-cedar.png', 'SaunaCedar', 0.78)
M_STOVE = mk('SaunaStove', '2B2A28', 0.5, 0.4)
M_STONE_S = mk('SaunaStone', '6E6A64', 0.95)
M_EMBER = mk('SaunaEmber', '3A1A08', 0.6)
_eb = M_EMBER.node_tree.nodes['Principled BSDF']
if _eb.inputs.get('Emission Color'):
    _eb.inputs['Emission Color'].default_value = (1.0, 0.38, 0.08, 1)
    _eb.inputs['Emission Strength'].default_value = 2.2
M_DENPLASTER = mk('DenEndWall', 'E9E2D6', 0.9)
region_delete_mats(-3.4, -0.6, -9.9, -6.3, 3.4, 4.5, {'fake_mat_170_128_59_255'}, "sauna-source-benches")
# Everything else of the source inside the room volume (its own white lining
# panels, a shelf ledge, the den door's frame, glass and handles) sat in
# front of the new cedar and showed as white strips and grey brackets. Wall
# faces lie on their planes, outside these inset boxes, and survive; large
# decimated faces that reach in are bisected at the box and trimmed.
cut_opening(-2.986, -0.60, -9.665, -7.305, 3.53, 6.262, "sauna-volume")
cut_opening(-2.986, -1.815, -7.305, -6.715, 3.53, 6.262, "sauna-alcove-volume")
SD_X1, SD_X2, SD_Z = -2.58, -1.92, 5.55          # gym -> sauna doorway
cut_opening(SD_X1, SD_X2, -6.85, -6.20, 3.52, SD_Z, "sauna-door")
# Floor: cedar duckboard over the main room, the entry alcove and the sill.
tex_box("SaunaFloor", -1.85, -8.48, 3.515, 1.15, 1.20, 0.012, M_CEDAR, scale=0.6)
tex_box("SaunaFloorAlcove", -2.405, -6.99, 3.515, 0.585, 0.29, 0.012, M_CEDAR, scale=0.6)
tex_box("SaunaSill", (SD_X1 + SD_X2) / 2, -6.49, 3.51, (SD_X2 - SD_X1) / 2, 0.21, 0.012, M_CEDAR, scale=0.6)
# Wall and ceiling lining, a few mm proud of the source faces. The east panel
# closes the den's glass wall; the den gets a plaster face on its side.
Z_MID, Z_HALF = (3.50 + 6.27) / 2, (6.27 - 3.50) / 2
tex_box("SaunaLineW", -2.985, -8.19, Z_MID, 0.006, 1.49, Z_HALF, M_CEDAR, rot=0.0)
tex_box("SaunaLineS", -1.845, -9.674, Z_MID, 1.145, 0.006, Z_HALF, M_CEDAR)
tex_box("SaunaLineE", -0.695, -8.48, Z_MID, 0.008, 1.20, Z_HALF, M_CEDAR)
# The north lining fills the 20 cm wall cavity: nav cells centred mid-wall
# passed the 0.08 m wall probe and walked the hall straight into the sauna.
tex_box("SaunaLineN", -1.25, -7.198, Z_MID, 0.55, 0.098, Z_HALF, M_CEDAR)
tex_box("SaunaLineAlcoveE", -1.806, -6.99, Z_MID, 0.005, 0.29, Z_HALF, M_CEDAR)
tex_box("SaunaLineAlcoveNW", (-2.99 + SD_X1 - 0.06) / 2, -6.705, Z_MID, (SD_X1 - 0.06 + 2.99) / 2, 0.005, Z_HALF, M_CEDAR)
tex_box("SaunaLineAlcoveNE", (SD_X2 + 0.06 - 1.81) / 2, -6.705, Z_MID, (-1.81 - SD_X2 - 0.06) / 2, 0.005, Z_HALF, M_CEDAR)
tex_box("SaunaLineAlcoveHead", (SD_X1 + SD_X2) / 2, -6.705, (SD_Z + 6.27) / 2, (SD_X2 - SD_X1) / 2 + 0.06, 0.005, (6.27 - SD_Z) / 2, M_CEDAR)
tex_box("SaunaCeil", -1.845, -8.48, 6.262, 1.145, 1.20, 0.006, M_CEDAR)
tex_box("SaunaCeilAlcove", -2.40, -6.99, 6.262, 0.59, 0.29, 0.006, M_CEDAR)
add_box("DenEndWall", -0.635, -8.49, 4.88, 0.010, 1.23, 1.37, M_DENPLASTER)
add_box("DenEndBase", -0.618, -8.49, 3.58, 0.008, 1.23, 0.06, M_DARK)
# Doorway: cedar jambs and head through the wall on both faces; the glass
# leaf opens outward (as sauna doors do), parked against the gym mirror wall.
for _nm, _x in (("SaunaJambW", SD_X1 - 0.03), ("SaunaJambE", SD_X2 + 0.03)):
    tex_box(_nm, _x, -6.49, (3.50 + SD_Z) / 2, 0.03, 0.23, (SD_Z - 3.50) / 2, M_CEDAR, rot=math.pi / 2)
tex_box("SaunaHead", (SD_X1 + SD_X2) / 2, -6.49, SD_Z + 0.035, (SD_X2 - SD_X1) / 2 + 0.06, 0.23, 0.035, M_CEDAR)
if M_GLASSP:
    add_box("SaunaDoorGlass", SD_X1 - 0.36, -6.262, 4.52, 0.30, 0.006, 0.96, M_GLASSP)
tex_box("SaunaDoorEdge", SD_X1 - 0.68, -6.262, 4.52, 0.02, 0.012, 0.97, M_CEDAR, rot=math.pi / 2)
tex_box("SaunaDoorHandle", SD_X1 - 0.62, -6.235, 4.50, 0.02, 0.02, 0.16, M_CEDAR, rot=math.pi / 2)
# Main room x -2.99..-0.70, y -9.68..-7.30. Two-tier L bench on the south and
# east walls (upper seat 0.92 m, 0.45 m step bench in front), stove by the
# entry in the north-west corner, open floor between for the walk in.
tex_box("SaunaBenchUpS", -1.845, -9.38, 3.96, 1.145, 0.30, 0.46, M_CEDAR)
tex_box("SaunaBenchUpE", -1.00, -8.515, 3.96, 0.30, 0.565, 0.46, M_CEDAR, rot=math.pi / 2)
tex_box("SaunaBenchLoS", -2.145, -8.83, 3.725, 0.845, 0.25, 0.225, M_CEDAR)
tex_box("SaunaBenchLoE", -1.55, -8.265, 3.725, 0.25, 0.315, 0.225, M_CEDAR, rot=math.pi / 2)
# Backrest boards above the upper tier.
for _i, _z in enumerate((4.72, 4.92)):
    tex_box(f"SaunaBackS{_i}", -1.845, -9.645, _z, 1.145, 0.025, 0.045, M_CEDAR)
    tex_box(f"SaunaBackE{_i}", -0.73, -8.515, _z, 0.025, 0.565, 0.045, M_CEDAR, rot=math.pi / 2)
# Hidden warm LED under the upper bench nose, ceiling light.
add_box("SaunaGlowBenchS", -2.145, -9.075, 4.36, 0.845, 0.004, 0.012, M_GLOW)
add_box("SaunaGlowBenchE", -1.305, -8.515, 4.36, 0.004, 0.565, 0.012, M_GLOW)
add_box("SaunaGlowCeil", -1.85, -8.30, 6.25, 0.35, 0.12, 0.008, M_GLOW)
# Stove: steel body, ember window facing the room, rock basket, cedar guard
# on its two open sides.
STV_X, STV_Y = -2.78, -7.64
add_box("SaunaStoveBody", STV_X, STV_Y, 3.88, 0.19, 0.19, 0.35, M_STOVE)
add_box("SaunaStoveEmber", STV_X + 0.195, STV_Y, 3.78, 0.005, 0.09, 0.06, M_EMBER)
for _i, (_dx, _dy, _r) in enumerate(((-0.08, -0.07, 0.065), (0.07, -0.08, 0.06), (0.0, 0.07, 0.065),
                                     (-0.08, 0.08, 0.05), (0.08, 0.07, 0.055), (0.0, -0.01, 0.06),
                                     (-0.04, 0.0, 0.05), (0.05, 0.02, 0.05))):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=_r, location=(STV_X + _dx, STV_Y + _dy, 4.26 + _r * 0.6))
    bpy.context.active_object.name = f"SaunaRock{_i}"
    bpy.context.active_object.data.materials.append(M_STONE_S)
for _i in range(5):
    tex_box(f"SaunaGuardE{_i}", -2.52, STV_Y - 0.24 + _i * 0.12, 3.90, 0.012, 0.02, 0.38, M_CEDAR, rot=math.pi / 2)
    tex_box(f"SaunaGuardS{_i}", -2.96 + _i * 0.105, STV_Y - 0.27, 3.90, 0.02, 0.012, 0.38, M_CEDAR, rot=math.pi / 2)
# Bucket and ladle on the step bench nearest the stove; towels on the top
# tier; thermometer on the north wall.
bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=0.11, depth=0.17, location=(-2.80, -8.83, 4.035))
bpy.context.active_object.name = "SaunaBucket"
bpy.context.active_object.data.materials.append(M_CEDAR)
for _i, _z in enumerate((3.985, 4.085)):
    bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=0.113, depth=0.012, location=(-2.80, -8.83, _z))
    bpy.context.active_object.name = f"SaunaBucketBand{_i}"
    bpy.context.active_object.data.materials.append(M_DARK)
add_box("SaunaLadle", -2.67, -8.83, 4.15, 0.13, 0.012, 0.012, M_CEDAR)
add_box("SaunaTowel1", -2.30, -9.40, 4.44, 0.20, 0.16, 0.025, M_TOWEL)
add_box("SaunaTowel2", -1.00, -8.30, 4.44, 0.16, 0.20, 0.025, M_TOWEL)
bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=0.09, depth=0.02, location=(-1.20, -7.306, 5.05), rotation=(math.pi / 2, 0, 0))
bpy.context.active_object.name = "SaunaThermo"
bpy.context.active_object.data.materials.append(M_DARK)
join_objects("SaunaCedarJoined", ("SaunaLine", "SaunaCeil", "SaunaFloor", "SaunaSill", "SaunaJamb", "SaunaHead",
                                  "SaunaBench", "SaunaBack", "SaunaGuard", "SaunaDoorEdge", "SaunaDoorHandle",
                                  "SaunaBucket", "SaunaLadle"))
join_objects("SaunaGlow", ("SaunaGlow",))
join_objects("SaunaRocks", ("SaunaRock",))
join_objects("SaunaTowels", ("SaunaTowel",))

# --- Patio BBQ island: one flat grey slab with a flat espresso grill on top.
# Dry-stacked ledgestone sides, a flamed charcoal granite worktop and a
# brushed black-steel grill (the detail pass adds the brushing).
BBQ_XY = (0.10, 1.15, 5.95, 8.55)
M_LEDGE = artmat('ledgestone.png', 'BBQLedgestone', 0.95)
M_GRANITE = artmat('granite-charcoal.png', 'BBQGranite', 0.45)
M_BBQ_STEEL = mk('BBQSteel', '2E2F31', 0.42, 0.45)
retex_region(*BBQ_XY, -0.05, 0.84, M_LEDGE, "BBQIslandSides", only_mats={'fake_mat_69_64_65_255'}, normal='side')
retex_region(*BBQ_XY, 0.80, 0.95, M_GRANITE, "BBQIslandTop", only_mats={'fake_mat_69_64_65_255'}, normal='up', scale=0.6)
retex_region(*BBQ_XY, -0.05, 1.60, M_BBQ_STEEL, "BBQGrill", only_mats={'fake_mat_104_101_99_255'}, scale=0.5)

# --- Sky den coffee table: a flat near-black box. Wenge, like the cladding.
retex_region(0.8, 2.0, -8.7, -8.0, 3.5, 3.9, M_WENGE, "DenTableWenge", only_objects=("DenTable",), scale=0.6)

# --- Walk-in closet doors: the NW leaf lost its glass but kept its centre
# stile, two cross bars and handle across the doorway; the NE leaf was still
# fully glazed. Take both leaves out so the closets read as open rooms.
region_delete_mats(-9.12, -8.94, 3.45, 3.72, 3.52, 5.70, {'fake_mat_6_5_5_255'}, "closet-nw-stile")
region_delete_mats(-10.15, -7.90, 3.45, 3.75, 3.60, 5.70, {'fake_mat_35_32_34_255', 'fake_mat_69_64_65_255'}, "closet-nw-bars")
region_delete_mats(9.70, 10.90, 3.85, 4.15, 3.55, 5.92, {GLASS_MAT, 'fake_mat_35_32_34_255', 'fake_mat_69_64_65_255'}, "closet-ne-leaf")

# --- South balcony: one open run from the hot tub to the cafe --------------
# The Capri's south wall (the old lift bank) and the vestibule block between
# the Capri and the covered walk (front-door wall, south wall, the east wall
# with its fake door) blocked the view and pretended to be an entrance. Take
# every ground-storey wall out below the ceilings; the sky den and sauna
# above stay as a cantilevered roof. One glass balustrade joins the SW and
# SE runs along the whole edge.
for nm in ("LobbyWallS", "LobbyBaseS"):
    bpy.data.objects.remove(bpy.data.objects[nm], do_unlink=True)
# Vestibule west wall (front door + frame), south of the Capri's north wall.
cut_opening(-1.45, -0.98, -9.95, -6.62, 0.05, 3.24, "balcony-vestibule-west")
# Vestibule and covered-walk south wall, incl. the espresso fake lift panels.
cut_opening(-1.45, 3.70, -10.0, -9.40, 0.05, 3.24, "balcony-vestibule-south")
# Everything from the vestibule east wall (fake white door at x 2.2) to the
# covered walk's west end wall (facade + a second fake door at x 3.65..3.86),
# including the partition between them. The pocket's north wall (y -6.26)
# stays and takes the Great Wave.
cut_opening(1.95, 3.95, -9.95, -6.36, 0.05, 3.24, "balcony-walk-west-end")
# Level the old vestibule with the Capri and walk decks (both at 0.10).
tex_box("BalconyMidFloor", 0.615, -8.19, 0.07, 1.935, 1.57, 0.03, M_TRAV, scale=1.3)
if M_GLASSP:
    add_box("ParaMidGlassS", -2.575, -9.74, 0.625, 5.145, 0.015, 0.525, M_GLASSP)
add_box("ParaMidRailS", -2.575, -9.74, 1.17, 5.145, 0.03, 0.025, M_RAIL)
add_box("ParaMidCurbS", -2.575, -9.74, 0.07, 5.145, 0.03, 0.035, M_RAIL)
# The Capri sign hung on the removed wall. Rehang it at 60% over the Sunrise
# on the Capri's north wall (face y -6.60), turned to face the lounge (-y).
from mathutils import Matrix
# (Face y -7.12 since the office was deepened; see "Office" below.)
sign_move = (Matrix.Translation((-4.60, -7.152, 2.45)) @ Matrix.Rotation(math.pi, 4, 'Z')
             @ Matrix.Scale(0.6, 4) @ Matrix.Translation((4.65, 9.65, -1.94)))
for nm in ("SpaSignFrame", "SpaSignFace", "SpaSignCapri", "SpaSignClub"):
    ob = bpy.data.objects[nm]
    ob.matrix_world = sign_move @ ob.matrix_world
bpy.context.view_layer.update()
# The balcony's north wall east of the hallway was two source sheets (green
# x 2.23..3.65, plaster x 3.85..6.09, faces y -6.26) with a 20 cm slot between
# them into the sealed lift/service boxes behind (no door, never a room), and
# a 10 cm pit in front of the green run (hallway floor at z 0, decks at 0.10).
# Face the whole run with one solid wall 6 cm proud (front at y -6.32, flush
# with the ConcreteRender soffit edge above the open-roof part) and fill the
# pit; the gallery probe re-hangs the Wave and the Paris posters on it.
M_BAL_GREEN = mk("BalconyGreenWall", "24463B", 0.9)
# Under the covered walk the ceiling is at 3.25: run 5 cm into the slab.
add_box("BalconyWallGreen", (2.135 + 3.80) / 2, -6.21, 1.65, (3.80 - 2.135) / 2, 0.11, 1.65, M_BAL_GREEN)
# Open-roof part: stop at 3.25 under the ConcreteRender edge.
add_box("BalconyWallPlaster", (3.80 + 6.12) / 2, -6.21, 1.625, (6.12 - 3.80) / 2, 0.11, 1.625, M_CAFE_PLASTER)
tex_box("BalconyPitFloor", (2.135 + 2.55) / 2, -6.47, 0.07, (2.55 - 2.135) / 2, 0.15, 0.03, M_TRAV, scale=1.3)
tex_box("BalconyWallSill", (2.55 + 6.12) / 2, -6.335, 0.07, (6.12 - 2.55) / 2, 0.015, 0.03, M_TRAV, scale=1.3)
bpy.context.view_layer.update()

# --- Office and lift: the glass lift (ground x -1.10..0.26, y -4.36..-5.84;
# upstairs x -1.03..0.26, y -4.23..-5.58) goes on both storeys. Downstairs the
# library, the narrow teal room between them and the lift shaft become one
# office, and its back wall moves from y -6.33 to -6.98 (spa aisle keeps
# ~1.05 m to the loungers). Upstairs the shaft becomes hall floor. Source
# floors are UV-mapped u = x + 8.1, v = -y (1 tile/m), so patches laid with
# the same mapping continue the herringbone without a seam.
def flat_patch(name, x1, x2, y1, y2, z, mat, down=False):
    me = bpy.data.meshes.new(name)
    vs = [(x1, y1, z), (x2, y1, z), (x2, y2, z), (x1, y2, z)]
    me.from_pydata(vs, [], [(3, 2, 1, 0) if down else (0, 1, 2, 3)])
    uvl = me.uv_layers.new(name="UVMap")
    for li, lp in enumerate(me.loops):
        vx, vy, _ = vs[lp.vertex_index]
        uvl.data[li].uv = (vx + 8.1, -vy)
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    sc.collection.objects.link(ob)
    return ob

def move_faces(x1, x2, y1, y2, z1, z2, mat_prefixes, delta, label):
    """Detach source faces (centre in box, material by prefix) from their
    neighbours and translate them, keeping their materials and UVs."""
    total = 0
    for ob in [o for o in sc.collection.all_objects if o.type == 'MESH' and o.name.startswith("Object_")]:
        names = [m.name if m else '' for m in ob.data.materials]
        idx = {i for i, n in enumerate(names) if n.startswith(mat_prefixes)}
        if not idx:
            continue
        mw = ob.matrix_world
        bmm = bmesh.new()
        bmm.from_mesh(ob.data)
        sel = []
        for f in bmm.faces:
            c = mw @ f.calc_center_median()
            if f.material_index in idx and x1 < c.x < x2 and y1 < c.y < y2 and z1 < c.z < z2:
                sel.append(f)
        if sel:
            out = bmesh.ops.split(bmm, geom=sel, use_only_faces=True)
            faces = [g for g in out['geom'] if isinstance(g, bmesh.types.BMFace)] or sel
            verts = list({v for f in faces for v in f.verts})
            bmesh.ops.translate(bmm, vec=mw.to_3x3().inverted() @ Vector(delta), verts=verts)
            bmm.to_mesh(ob.data)
            total += len(faces)
        bmm.free()
    bpy.context.view_layer.update()
    print(f"MOVE {label}: {total} faces")

M_OFFICE_WALL = bpy.data.materials['gris_004_Wall_Entity_Material']
M_HALL_CEIL = next(m for m in bpy.data.materials if m.name.startswith('blanc_001_ovcol'))

# Floor first (flat faces only), then everything standing in the removed
# rooms: teal room, lift and the partitions (east rooms), the library's
# carcass bookcases and chairs (library interior), and the east bookcase
# carcass up to the glass door's east jamb at x -3.22.
cut_opening(-5.28, 0.23, -6.965, -4.42, -0.01, 0.01, "office-floor", horizontal_at=0.0)
cut_opening(-2.975, 0.44, -6.99, -4.33, -0.01, 3.245, "office-east-rooms")
cut_opening(-5.275, -2.975, -6.99, -4.52, -0.01, 3.245, "office-library-interior")
cut_opening(-3.215, -2.975, -6.14, -4.335, -0.01, 3.245, "office-library-east-case")
for nm in ("LibChairW", "LibChairE", "LibTableTop", "LibTableStem", "LibTableBase"):
    bpy.data.objects.remove(bpy.data.objects[nm], do_unlink=True)
# Lift call buttons on the hall wall (ground) and the gym niche end (upstairs).
region_delete_mats(-1.40, -1.15, -4.32, -4.20, 0.90, 1.30,
                   {'fake_mat_224_230_228_255', 'fake_mat_251_251_251_255'}, "lift-buttons-ground")
region_delete_mats(-1.40, -1.20, -4.30, -4.15, 4.40, 4.90,
                   {'fake_mat_224_230_228_255', 'fake_mat_251_251_251_255'}, "lift-buttons-upper")
# Spa-side pieces that stood on the old wall line, or under the new strip.
for nm in ("LobbyWallN2", "LobbyBaseN", "SpaNorthEnd", "LobbyFloor", "SpaFloor", "LobbyCeil", "BalconyMidFloor"):
    bpy.data.objects.remove(bpy.data.objects[nm], do_unlink=True)
tex_box("SpaFloor", -3.41, -8.44, .07, 2.09, 1.32, .03, M_TRAV, scale=1.3)          # x -5.50..-1.32, y -9.76..-7.12
tex_box("SpaFloorWest", -6.61, -8.18, .07, 1.11, 1.58, .03, M_TRAV, scale=1.3)      # x -7.72..-5.50, open to the pocket
add_box("LobbyCeil", -3.41, -8.44, 2.98, 2.09, 1.32, 0.04, M_SPA_CREAM)
add_box("LobbyCeilWest", -6.56, -8.19, 2.98, 1.06, 1.57, 0.04, M_SPA_CREAM)
tex_box("BalconyMidFloor", -0.4325, -8.44, 0.07, 0.8875, 1.32, 0.03, M_TRAV, scale=1.3)   # x -1.32..0.455
tex_box("BalconyMidFloorE", 1.5025, -8.19, 0.07, 1.0475, 1.57, 0.03, M_TRAV, scale=1.3)   # x 0.455..2.55
add_box("LobbyBaseN", -3.41, -7.132, 0.16, 2.09, 0.012, 0.06, M_SPA_BLUE)
# Structural walls (spa, hallway and hall faces). Room side is finished below.
add_box("OfficeWallS", -2.6275, -7.05, 1.625, 2.8725, 0.07, 1.625, M_SPA_CREAM)     # x -5.50..0.245, spa face -7.12
add_box("OfficeWallW", -5.39, -6.67, 1.625, 0.11, 0.31, 1.625, M_SPA_CREAM)         # x -5.50..-5.28, y -6.98..-6.36
tex_box("OfficeWallE", 0.35, -5.705, 1.625, 0.105, 1.415, 1.625, M_WENGE)            # x 0.245..0.455, y -7.12..-4.29
add_box("OfficeWallN", -1.4925, -4.365, 1.625, 1.7225, 0.055, 1.625, M_OFFICE_WALL)  # x -3.215..0.23, y -4.42..-4.31
tex_box("OfficeHallSkin", -1.4875, -4.30, 1.625, 1.7325, 0.01, 1.625, M_WENGE)      # x -3.22..0.245, hall face -4.29
join_objects("OfficeShell", ("OfficeWall", "OfficeHallSkin"))

# --- The den: a 19th-century industrialist's study, kept spare ---------------
# Room faces: north y -4.53 (glass entry doors x -4.84..-3.29, head 2.29),
# south -6.945, west x -5.26, east 0.21. Oak raised-panel wainscot to 1.0 m,
# deep green plaster above, oak crown; the wall behind the desk is a flat
# painted library (no depth). The banker's lamp carries the room's light.
DN, DS, DW, DE = -4.53, -6.945, -5.26, 0.21
ART_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'art')
M_DEN_GREEN = mk('DenWallsGreen', '23372B', 0.9)
M_DEN_OAK = artmat('den-oak.jpg', 'DenOakGrain', 0.55)
M_DEN_OAKDK = mk('DenOakDark', '2E1C10', 0.6)
M_DEN_WAINSCOT = artmat('den-wainscot.jpg', 'DenWainscot', 0.6)
M_DEN_LIBRARY = artmat('den-library.jpg', 'DenLibraryWall', 0.8)
M_DEN_RUG = artmat('den-rug.jpg', 'DenRugWool', 0.95)
M_DEN_CEIL = mk('DenCeilCream', 'E6DAC0', 0.9)
M_DEN_COGNAC = mk('DenLeatherCognac', '6A3517', 0.5)
M_DEN_OXBLOOD = mk('DenLeatherOxblood', '4A1512', 0.5)
M_DEN_BLOTTER = mk('DenDeskLeather', '1F3A2B', 0.55)
M_DEN_SHADE = mk('DenLampGreen', '0C4424', 0.12)
_sb = M_DEN_SHADE.node_tree.nodes['Principled BSDF']
_sb.inputs['Emission Color'].default_value = (0.03, 0.22, 0.09, 1)
_sb.inputs['Emission Strength'].default_value = 0.6
M_DEN_WHISKY = mk('DenWhisky', '7A3F0E', 0.1)
# Floor: the house herringbone, stained to a warm oak for this room only.
M_DEN_FLOOR = M_PARQ.copy()
M_DEN_FLOOR.name = 'DenFloorOak'
_nt = M_DEN_FLOOR.node_tree
_tx = next(n for n in _nt.nodes if n.type == 'TEX_IMAGE')
_bf = _nt.nodes['Principled BSDF']
_mx = _nt.nodes.new('ShaderNodeMix')
_mx.data_type, _mx.blend_type = 'RGBA', 'MULTIPLY'
_mx.inputs['Factor'].default_value = 1.0
_ms = {s_.identifier: s_ for s_ in _mx.inputs}
_ms['B_Color'].default_value = (0.42, 0.25, 0.13, 1.0)
_nt.links.new(_tx.outputs['Color'], _ms['A_Color'])
_nt.links.new(next(s_ for s_ in _mx.outputs if s_.identifier == 'Result_Color'), _bf.inputs['Base Color'])
flat_patch("OfficeFloor", -5.28, 0.23, -6.965, -4.42, 0.0, M_DEN_FLOOR)
flat_patch("OfficeCeiling", -5.28, 0.23, -6.965, -4.42, 3.24, M_DEN_CEIL, down=True)

def den_quad(name, left, right, z0, z1, mat, tile_w, tile_h, uv0=(0.0, 0.0)):
    """Vertical decal from left to right (as seen facing the wall); UVs in
    tiles of tile_w x tile_h metres, v = 0 at z0."""
    L = Vector((left[0], left[1], 0))
    R = Vector((right[0], right[1], 0))
    span = (R - L).length
    vs = [(L.x, L.y, z0), (R.x, R.y, z0), (R.x, R.y, z1), (L.x, L.y, z1)]
    uvs = [(uv0[0], uv0[1]), (uv0[0] + span / tile_w, uv0[1]), (uv0[0] + span / tile_w, uv0[1] + (z1 - z0) / tile_h),
           (uv0[0], uv0[1] + (z1 - z0) / tile_h)]
    me = bpy.data.meshes.new(name)
    me.from_pydata(vs, [], [(0, 1, 2, 3)])
    uvl = me.uv_layers.new(name="UVMap")
    for li, lp in enumerate(me.loops):
        uvl.data[li].uv = uvs[lp.vertex_index]
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    sc.collection.objects.link(ob)
    return ob

# Green plaster skins, full height, over whatever the old walls were.
add_box("DenSkinW", -5.27, (DS + DN) / 2, 1.62, 0.01, (DN - DS) / 2, 1.62, M_DEN_GREEN)
add_box("DenSkinS", (-5.28 + 0.23) / 2, (-6.98 + DS) / 2, 1.62, (0.23 + 5.28) / 2, (DS + 6.98) / 2, 1.62, M_DEN_GREEN)
add_box("DenSkinE", (DE + 0.245) / 2, (DS + DN) / 2, 1.62, (0.245 - DE) / 2, (DN - DS) / 2, 1.62, M_DEN_GREEN)
add_box("DenSkinNW", (DW - 4.91) / 2, (DN - 4.51) / 2, 1.62, (DW - (-4.91)) / -2, 0.01, 1.62, M_DEN_GREEN)   # x -5.26..-4.91
add_box("DenSkinNE", (-3.225 + DE) / 2, (DN - 4.42) / 2, 1.62, (DE + 3.225) / 2, (-4.42 - DN) / 2, 1.62, M_DEN_GREEN)  # x -3.225..0.21
add_box("DenSkinLintel", (-4.91 - 3.225) / 2, (DN - 4.51) / 2, 2.805, (-3.225 + 4.91) / 2, 0.01, 0.435, M_DEN_GREEN)  # z 2.37..3.24
# Wainscot (painted-on raised panels, 0.625 m module) with an oak cap rail.
WAIN = [("W", (DW + .006, DS), (DW + .006, DN)),
        ("S", (DE, DS + .006), (DW, DS + .006)),
        ("NW", (DW, DN - .006), (-4.91, DN - .006)),
        ("NE", (-3.225, DN - .006), (DE, DN - .006))]
for tag, lft, rgt in WAIN:
    den_quad(f"DenWainscot{tag}", lft, rgt, 0.0, 1.0, M_DEN_WAINSCOT, 0.625, 1.0)
tex_box("DenCapW", DW + 0.015, (DS + DN) / 2, 1.022, 0.015, (DN - DS) / 2, 0.022, M_DEN_OAK, scale=0.8)
tex_box("DenCapS", (DW + DE) / 2, DS + 0.015, 1.022, (DE - DW) / 2, 0.015, 0.022, M_DEN_OAK, scale=0.8)
tex_box("DenCapNW", (DW - 4.91) / 2, DN - 0.015, 1.022, (-4.91 - DW) / 2, 0.015, 0.022, M_DEN_OAK, scale=0.8)
tex_box("DenCapNE", (-3.225 + DE) / 2, DN - 0.015, 1.022, (DE + 3.225) / 2, 0.015, 0.022, M_DEN_OAK, scale=0.8)
# Oak crown on all four walls, over the library wall too.
tex_box("DenCrownW", DW + 0.02, (DS + DN) / 2, 3.19, 0.02, (DN - DS) / 2, 0.05, M_DEN_OAK, scale=0.8)
tex_box("DenCrownE", DE - 0.03, (DS + DN) / 2, 3.19, 0.03, (DN - DS) / 2, 0.05, M_DEN_OAK, scale=0.8)
tex_box("DenCrownS", (DW + DE) / 2, DS + 0.02, 3.19, (DE - DW) / 2, 0.02, 0.05, M_DEN_OAK, scale=0.8)
tex_box("DenCrownN", (DW + DE) / 2, DN - 0.02, 3.19, (DE - DW) / 2, 0.02, 0.05, M_DEN_OAK, scale=0.8)
# The library wall behind the desk: an image of cupboards and shelved books.
den_quad("DenLibraryWall", (DE - 0.006, DN), (DE - 0.006, DS), 0.0, 3.14, M_DEN_LIBRARY, DN - DS, 3.14)
_rm = bpy.data.meshes.new("DenRug")
_rv = [(-3.25, -6.66, 0.006), (-0.25, -6.66, 0.006), (-0.25, -4.76, 0.006), (-3.25, -4.76, 0.006)]
_rm.from_pydata(_rv, [], [(0, 1, 2, 3)])
_ru = _rm.uv_layers.new(name="UVMap")
for li, lp in enumerate(_rm.loops):
    _ru.data[li].uv = [(0, 0), (1, 0), (1, 1), (0, 1)][lp.vertex_index]
_rm.materials.append(M_DEN_RUG)
sc.collection.objects.link(bpy.data.objects.new("DenRug", _rm))

# Pedestal desk in oak with a green leather top, the sitter on the east side
# facing the room and the entry.
DX, DY = -1.20, (DN + DS) / 2
tex_box("DenDeskTop", DX, DY, 0.74, 0.43, 0.78, 0.02, M_DEN_OAK, scale=0.8)
add_box("DenDeskBlotter", DX, DY, 0.7615, 0.36, 0.66, 0.0015, M_DEN_BLOTTER)
for i, py in enumerate((DY + 0.57, DY - 0.57)):
    tex_box(f"DenDeskPed{i}", DX, py, 0.395, 0.40, 0.21, 0.325, M_DEN_OAK, scale=0.8)
    add_box(f"DenDeskPlinth{i}", DX, py, 0.035, 0.38, 0.19, 0.035, M_DEN_OAKDK)
    # visitor side: a raised panel; sitter side: three drawers with brass pulls
    tex_box(f"DenDeskPanel{i}", DX - 0.405, py, 0.40, 0.006, 0.15, 0.22, M_DEN_OAK, scale=0.8)
    for k, (zc, hz) in enumerate(((0.62, 0.075), (0.43, 0.095), (0.20, 0.12))):
        tex_box(f"DenDeskDrawer{i}{k}", DX + 0.404, py, zc, 0.005, 0.185, hz - 0.008, M_DEN_OAK, scale=0.8)
        add_box(f"DenDeskPull{i}{k}", DX + 0.415, py, zc, 0.008, 0.045, 0.008, M_BRASS)
tex_box("DenDeskModesty", DX - 0.37, DY, 0.46, 0.012, 0.36, 0.26, M_DEN_OAK, scale=0.8)
tex_box("DenDeskApron", DX + 0.39, DY, 0.675, 0.012, 0.36, 0.045, M_DEN_OAK, scale=0.8)
add_box("DenDeskApronPull", DX + 0.405, DY, 0.675, 0.008, 0.06, 0.008, M_BRASS)
# On the desk: a closed leather ledger and a pen.
add_box("DenLedger", DX + 0.12, DY - 0.36, 0.778, 0.15, 0.11, 0.015, M_DEN_OXBLOOD)
bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=0.005, depth=0.14, location=(DX + 0.14, DY - 0.12, 0.768),
                                    rotation=(math.pi / 2, 0, 0.3))
bpy.context.active_object.name = "DenDeskPen"
bpy.context.active_object.data.materials.append(M_DARK)

# Banker's lamp: brass base and stem, green glass half-cylinder shade lit
# from within. Light_H (the old lobby light) now sits here.
LX, LY = DX - 0.18, DY + 0.36
bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=0.075, depth=0.02, location=(LX, LY, 0.773))
bpy.context.active_object.name = "DenLampBase"
bpy.context.active_object.data.materials.append(M_BRASS)
bpy.ops.mesh.primitive_cylinder_add(vertices=10, radius=0.011, depth=0.26, location=(LX, LY, 0.913))
bpy.context.active_object.name = "DenLampStem"
bpy.context.active_object.data.materials.append(M_BRASS)
add_box("DenLampYoke", LX, LY, 1.045, 0.008, 0.12, 0.008, M_BRASS)
bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=0.078, depth=0.30, location=(LX, LY, 1.07),
                                    rotation=(math.pi / 2, 0, 0))
_sh = bpy.context.active_object
_sh.name = "DenLampShade"
bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
_bm = bmesh.new()
_bm.from_mesh(_sh.data)
bmesh.ops.delete(_bm, geom=[v for v in _bm.verts if v.co.z < -0.02], context='VERTS')
_bm.to_mesh(_sh.data)
_bm.free()
_sh.data.materials.append(M_DEN_SHADE)
_sh.modifiers.new('Shell', 'SOLIDIFY').thickness = 0.004
bpy.context.view_layer.objects.active = _sh
bpy.ops.object.modifier_apply(modifier='Shell')
add_box("DenLampGlow", LX, LY, 1.055, 0.055, 0.14, 0.002, M_GLOW)

# Executive chair behind the desk (oxblood), facing west.
def den_part(name, c, yaw, local, half, mat, bevel=0.0):
    ob = spa_box(name, (0, 0, local[2]), half, mat, bevel)
    ca, sa = math.cos(yaw), math.sin(yaw)
    ob.location = (c[0] + local[0] * ca - local[1] * sa, c[1] + local[0] * sa + local[1] * ca, local[2])
    ob.rotation_euler = (0, 0, yaw)
    return ob

EX = -0.36
for nm, loc, half, mat, bev in (
        ("Base", (0.03, 0, 0.27), (0.30, 0.31, 0.19), M_DEN_OXBLOOD, 0.03),
        ("Seat", (-0.02, 0, 0.495), (0.25, 0.25, 0.035), M_DEN_OXBLOOD, 0.03),
        ("Back", (-0.25, 0, 0.87), (0.08, 0.31, 0.42), M_DEN_OXBLOOD, 0.05),
        ("ArmN", (0.02, 0.29, 0.66), (0.26, 0.055, 0.09), M_DEN_OXBLOOD, 0.04),
        ("ArmS", (0.02, -0.29, 0.66), (0.26, 0.055, 0.09), M_DEN_OXBLOOD, 0.04)):
    den_part(f"DenExecChair{nm}", (EX, DY), math.pi, loc, half, mat, bev)
for i, (fx, fy) in enumerate(((0.26, 0.27), (0.26, -0.27), (-0.22, 0.27), (-0.22, -0.27))):
    den_part(f"DenExecChairFoot{i}", (EX, DY), math.pi, (fx, fy, 0.04), (0.025, 0.025, 0.04), M_DEN_OAKDK)

# Two cognac club chairs facing the desk, toed in a little.
CLUBS = ((-2.52, DY + 0.54, -math.radians(12)), (-2.52, DY - 0.54, math.radians(12)))
for j, (cx, cy, yaw) in enumerate(CLUBS):
    for nm, loc, half, bev in (
            ("Base", (0.0, 0, 0.22), (0.40, 0.42, 0.16), 0.04),
            ("Seat", (0.06, 0, 0.415), (0.30, 0.25, 0.045), 0.04),
            ("ArmL", (0.0, 0.335, 0.45), (0.40, 0.085, 0.16), 0.07),
            ("ArmR", (0.0, -0.335, 0.45), (0.40, 0.085, 0.16), 0.07),
            ("Back", (-0.31, 0, 0.58), (0.10, 0.42, 0.28), 0.07)):
        den_part(f"DenClub{j}{nm}", (cx, cy), yaw, loc, half, M_DEN_COGNAC, bev)
    for i, (fx, fy) in enumerate(((0.34, 0.36), (0.34, -0.36), (-0.34, 0.36), (-0.34, -0.36))):
        den_part(f"DenClub{j}Foot{i}", (cx, cy), yaw, (fx, fy, 0.03), (0.03, 0.03, 0.03), M_DEN_OAKDK)

# Oak credenza on the south wall, facing the entry, with a decanter set.
KX = -4.10
tex_box("DenCredenza", KX, DS + 0.225, 0.44, 0.75, 0.21, 0.36, M_DEN_OAK, scale=0.8)
tex_box("DenCredenzaTop", KX, DS + 0.235, 0.815, 0.77, 0.235, 0.015, M_DEN_OAK, scale=0.8)
add_box("DenCredenzaPlinth", KX, DS + 0.215, 0.04, 0.73, 0.19, 0.04, M_DEN_OAKDK)
for k in range(3):
    px = KX - 0.50 + k * 0.50
    tex_box(f"DenCredenzaDoor{k}", px, DS + 0.438, 0.44, 0.21, 0.004, 0.27, M_DEN_OAK, scale=0.8)
    add_box(f"DenCredenzaPull{k}", px + (0.15 if k < 2 else -0.15), DS + 0.446, 0.52, 0.008, 0.006, 0.04, M_BRASS)
add_box("DenTray", KX + 0.25, DS + 0.25, 0.834, 0.20, 0.13, 0.004, M_BRASS)
for nm, x, y, z, r, dz, mat in (
        ("DenDecanterWhisky", KX + 0.18, DS + 0.25, 0.895, 0.052, 0.11, M_DEN_WHISKY),
        ("DenDecanterGlass", KX + 0.18, DS + 0.25, 0.94, 0.060, 0.20, M_GLASSP),
        ("DenDecanterNeck", KX + 0.18, DS + 0.25, 1.07, 0.018, 0.06, M_GLASSP),
        ("DenTumblerA", KX + 0.33, DS + 0.30, 0.878, 0.034, 0.08, M_GLASSP),
        ("DenTumblerB", KX + 0.36, DS + 0.20, 0.878, 0.034, 0.08, M_GLASSP),
        ("DenTumblerAWhisky", KX + 0.33, DS + 0.30, 0.858, 0.030, 0.035, M_DEN_WHISKY)):
    bpy.ops.mesh.primitive_cylinder_add(vertices=20, radius=r, depth=dz, location=(x, y, z))
    bpy.context.active_object.name = nm
    bpy.context.active_object.data.materials.append(mat)
bpy.ops.mesh.primitive_uv_sphere_add(segments=12, ring_count=6, radius=0.028, location=(KX + 0.18, DS + 0.25, 1.12))
bpy.context.active_object.name = "DenDecanterStopper"
bpy.context.active_object.data.materials.append(M_GLASSP)

join_objects("DenRoom", ("DenSkin", "DenWainscot", "DenCap", "DenCrown", "DenLibraryWall"))
join_objects("DenDesk", ("DenDesk", "DenLedger", "DenLamp"))
join_objects("DenExecChair", ("DenExecChair",))
join_objects("DenClub0", ("DenClub0",))
join_objects("DenClub1", ("DenClub1",))
join_objects("DenCredenza", ("DenCredenza", "DenTray", "DenDecanter", "DenTumbler"))
bpy.context.view_layer.update()

# --- Dining room: English country house, not a white-marble showroom ---------
# (x 6.1..11.39, y 3.0..9.68; open to the kitchen on the south.) The marble
# slab table, the eight Qing chairs, the silver pendant cluster and the grey
# oval rug go. In their place: an oak refectory table, eight oak ladder-back
# chairs set back from it, two brass candelabras near the table ends (the
# middle pairs, D2/D6 and D3/D7, keep a clear sightline across), a brass candle
# chandelier, heritage red walls over oak wainscot and an oriental rug.
region_delete_mats(8.0, 9.6, 4.3, 7.9, -0.01, 0.95, {'20210310-165737-cet'}, "dining-marble-table")
region_delete_mats(7.6, 10.0, 4.2, 7.9, -0.01, 1.3,
                   {'fake_mat_35_32_34_255', 'qing_style_chair___qing_style_chairmaterial__28'}, "dining-qing-chairs")
region_delete(8.4, 9.05, 4.6, 7.25, 1.7, 3.08)                               # pendant cluster, cords, canopies
region_delete_mats(6.85, 10.75, 3.1, 8.85, -0.01, 0.04, {'moquette_019'}, "dining-oval-rug")
# The oval's dark border disc IS the floor inside the oval: replace it with
# herringbone continuing the room's world-planar floor.
region_delete_mats(6.85, 10.75, 3.1, 8.85, -0.01, 0.012, {'fake_mat_6_5_5_255'}, "dining-oval-border")
flat_patch("DiningFloor", 6.85, 10.75, 3.12, 8.85, 0.0, M_PARQ)

recolor_region(6.08, 11.55, 3.0, 9.72, -0.1, 3.4, "6B2323", rough=0.9, label="DiningWalls",
               only_mats={'blanc_001_Wall_Entity_Material'})
# The east window head runs y -1.70..3.83 as one decimated strip whose big
# triangle has its centre over the kitchen: finish the whole head red.
recolor_region(11.3, 11.55, -1.75, 3.9, 2.5, 3.3, "6B2323", rough=0.9, label="DiningWalls",
               only_mats={'blanc_001_Wall_Entity_Material'})
# Oak wainscot and cap rail on the east (picture) wall, which leans 2.3 cm
# over its run: face x 11.398 at y 4.62, 11.373 at y 9.55.
den_quad("DiningWainscot", (11.367, 9.55), (11.392, 4.62), 0.0, 1.0, M_DEN_WAINSCOT, 0.625, 1.0)
tex_box("DiningCapRail", 11.365, 7.085, 1.022, 0.02, 2.465, 0.022, M_DEN_OAK, scale=0.8)

# Rug: the den's oriental tile, long axis down the table (u runs along y).
_rm = bpy.data.meshes.new("DiningRug")
_rm.from_pydata([(7.40, 3.90, 0.006), (10.20, 3.90, 0.006), (10.20, 8.30, 0.006), (7.40, 8.30, 0.006)], [], [(0, 1, 2, 3)])
_ru = _rm.uv_layers.new(name="UVMap")
for li, lp in enumerate(_rm.loops):
    _ru.data[li].uv = [(0, 1), (0, 0), (1, 0), (1, 1)][lp.vertex_index]
_rm.materials.append(M_DEN_RUG)
sc.collection.objects.link(bpy.data.objects.new("DiningRug", _rm))

M_DINE_OAK = mk('DiningOak', '6B4224', 0.55)
M_DINE_SEAT = mk('DiningSeatGreen', '2E4A33', 0.8)
M_DINE_WAX = mk('DiningCandleWax', 'EDE6D3', 0.6)

def dine_cyl(name, x, y, z, r, depth, mat, verts=16, rot=(0.0, 0.0, 0.0)):
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=r, depth=depth, location=(x, y, z), rotation=rot)
    bpy.context.active_object.name = name
    bpy.context.active_object.data.materials.append(mat)
    return bpy.context.active_object

# Refectory table: oak top 1.05 x 3.0 m at 0.765 on four turned corner legs,
# centred where the marble slab stood. The dinner party (dinner_figures.py)
# sits at it, so the aprons are narrow (knees fit under), there is no long
# stretcher to trip the guests' feet and no middle leg between their knees.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dinner_figures as DF
TX, TY, TT = 8.80, 6.10, 0.765
assert (TX, TY, TT) == (DF.TX, DF.TY, DF.TT), "dinner_figures layout must match the table"
tex_box("DiningTableTop", TX, TY, TT - 0.025, 0.525, 1.50, 0.025, M_DEN_OAK, scale=0.8)
for i, sx in enumerate((-1, 1)):
    tex_box(f"DiningTableApronL{i}", TX + sx * 0.445, TY, 0.69, 0.012, 1.40, 0.025, M_DEN_OAK, scale=0.8)
    tex_box(f"DiningTableApronE{i}", TX, TY + sx * 1.40, 0.69, 0.445, 0.012, 0.025, M_DEN_OAK, scale=0.8)
    add_box(f"DiningTableStretcherE{i}", TX, TY + sx * 1.40, 0.08, 0.43, 0.018, 0.022, M_DINE_OAK)
for i, (lx, ly) in enumerate([(TX + a * 0.43, TY + b * 1.40) for a in (-1, 1) for b in (-1, 1)]):
    add_box(f"DiningTableLegBlock{i}", lx, ly, 0.69, 0.04, 0.04, 0.025, M_DINE_OAK)
    dine_cyl(f"DiningTableLegTop{i}", lx, ly, 0.60, 0.032, 0.12, M_DINE_OAK)
    dine_cyl(f"DiningTableLegNeck{i}", lx, ly, 0.535, 0.032, 0.06, M_DINE_OAK)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=10, radius=0.058, location=(lx, ly, 0.40))
    bpy.context.active_object.name = f"DiningTableLegBulb{i}"
    bpy.context.active_object.scale = (1.0, 1.0, 1.75)
    bpy.context.active_object.data.materials.append(M_DINE_OAK)
    dine_cyl(f"DiningTableLegRing{i}", lx, ly, 0.285, 0.045, 0.03, M_DINE_OAK)
    dine_cyl(f"DiningTableLegShaft{i}", lx, ly, 0.20, 0.03, 0.14, M_DINE_OAK)
    add_box(f"DiningTableLegFoot{i}", lx, ly, 0.065, 0.038, 0.038, 0.065, M_DINE_OAK)

# The eight ladder-back chairs are animated props (dinner_figures.CHAIR_PARTS):
# the guests draw them out to sit down and push them in when they leave.

# Candelabras: brass, three lights on an arm that runs down the table, near
# the thirds but in the gaps between place pairs (D1/D2, D3/D4), so neither
# stands between D3 and D7, the two free places facing each other.
for k, cy in enumerate((DF.GAPS[1], DF.GAPS[3])):
    c = f"DiningCandelabra{k}"
    dine_cyl(f"{c}Base", TX, cy, TT + 0.010, 0.075, 0.02, M_BRASS, 24)
    dine_cyl(f"{c}Step", TX, cy, TT + 0.0325, 0.048, 0.025, M_BRASS, 24)
    dine_cyl(f"{c}Stem", TX, cy, TT + 0.225, 0.012, 0.36, M_BRASS, 12)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=12, ring_count=6, radius=0.026, location=(TX, cy, TT + 0.16))
    bpy.context.active_object.name = f"{c}Knop"
    bpy.context.active_object.data.materials.append(M_BRASS)
    dine_cyl(f"{c}Arm", TX, cy, TT + 0.29, 0.009, 0.34, M_BRASS, 10, rot=(math.pi / 2, 0, 0))
    for dy, zc in ((-0.17, 0.365), (0.17, 0.365), (0.0, 0.415)):
        if dy:
            dine_cyl(f"{c}Riser{dy:+.2f}", TX, cy + dy, TT + 0.32, 0.009, 0.06, M_BRASS, 10)
        dine_cyl(f"{c}Cup{dy:+.2f}", TX, cy + dy, TT + zc, 0.022, 0.03, M_BRASS, 16)
        dine_cyl(f"{c}Candle{dy:+.2f}", TX, cy + dy, TT + zc + 0.10, 0.011, 0.17, M_DINE_WAX, 12)
        bpy.ops.mesh.primitive_cone_add(vertices=8, radius1=0.008, radius2=0.0, depth=0.03,
                                        location=(TX, cy + dy, TT + zc + 0.20))
        bpy.context.active_object.name = f"{c}Flame{dy:+.2f}"
        bpy.context.active_object.data.materials.append(M_GLOW)

# Six-light brass chandelier over the table centre, bottom at 2.2 m.
CZ = 3.08
dine_cyl("DiningChandelierRod", TX, TY, (CZ + 2.55) / 2, 0.008, CZ - 2.55, M_BRASS, 8)
dine_cyl("DiningChandelierCanopy", TX, TY, CZ - 0.015, 0.06, 0.03, M_BRASS, 16)
dine_cyl("DiningChandelierColumn", TX, TY, 2.40, 0.03, 0.30, M_BRASS, 16)
bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, radius=0.055, location=(TX, TY, 2.30))
bpy.context.active_object.name = "DiningChandelierBowl"
bpy.context.active_object.data.materials.append(M_BRASS)
bpy.ops.mesh.primitive_uv_sphere_add(segments=10, ring_count=6, radius=0.02, location=(TX, TY, 2.22))
bpy.context.active_object.name = "DiningChandelierFinial"
bpy.context.active_object.data.materials.append(M_BRASS)
for a in range(6):
    ang = a * math.pi / 3
    ax, ay = TX + 0.34 * math.cos(ang), TY + 0.34 * math.sin(ang)
    dine_cyl(f"DiningChandelierArm{a}", TX + 0.17 * math.cos(ang), TY + 0.17 * math.sin(ang), 2.32, 0.009, 0.34,
             M_BRASS, 8, rot=(math.pi / 2, 0, ang + math.pi / 2))
    dine_cyl(f"DiningChandelierRiser{a}", ax, ay, 2.355, 0.009, 0.07, M_BRASS, 8)
    dine_cyl(f"DiningChandelierCup{a}", ax, ay, 2.40, 0.035, 0.02, M_BRASS, 16)
    dine_cyl(f"DiningChandelierCandle{a}", ax, ay, 2.47, 0.011, 0.12, M_DINE_WAX, 12)
    bpy.ops.mesh.primitive_cone_add(vertices=8, radius1=0.008, radius2=0.0, depth=0.03, location=(ax, ay, 2.545))
    bpy.context.active_object.name = f"DiningChandelierFlame{a}"
    bpy.context.active_object.data.materials.append(M_GLOW)

# Sideboards (dinner_figures.SIDEBOARD): oak under the west window, a console
# under the east pictures. The waiters keep the wine and glass trays on them.
M_DINNER_CHINA = mk('DinnerSetChina', 'F4F1EA', 0.35)
M_DINNER_GOLD = mk('DinnerSetGold', 'B8954A', 0.35, 0.45)
M_DINNER_SILVER = mk('DinnerSetSilver', 'CFD1D5', 0.3, 0.5)
M_DINNER_BREAD = mk('DinnerSetBread', 'C98B4A', 0.8)
M_DINNER_WATER = mk('DinnerSetWater', 'C9D7DD', 0.1)
M_DINNER_COPPER = mk('DinnerSetCopper', 'A8623A', 0.35, 0.5)
M_DINNER_BOARD = mk('DinnerSetBoard', 'A87B4F', 0.7)
for w, (x0, x1, y0, y1) in DF.SIDEBOARD.items():
    cx, cy, hx, hy = (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2, (y1 - y0) / 2
    front = x1 if w == "W1" else x0
    sgn = 1 if w == "W1" else -1
    tex_box(f"DiningSideboard{w}Top", cx, cy, DF.SB_TOP - 0.02, hx + 0.015, hy + 0.015, 0.02, M_DEN_OAK, scale=0.8)
    add_box(f"DiningSideboard{w}Body", cx, cy, 0.52, hx, hy, 0.36, M_DEN_OAKDK)
    for j, dy in enumerate((-hy / 2, hy / 2)):
        add_box(f"DiningSideboard{w}Door{j}", front + sgn * 0.004, cy + dy, 0.50, 0.006, hy / 2 - 0.03, 0.30,
                M_DINE_OAK)
        dine_cyl(f"DiningSideboard{w}Knob{j}", front + sgn * 0.016, cy + dy - sgn * 0.0, 0.66, 0.012, 0.02,
                 M_BRASS, 10, rot=(0, math.pi / 2, 0))
    for j, (lx, ly) in enumerate([(x0 + 0.04, y0 + 0.04), (x0 + 0.04, y1 - 0.04), (x1 - 0.04, y0 + 0.04),
                                  (x1 - 0.04, y1 - 0.04)]):
        add_box(f"DiningSideboard{w}Leg{j}", lx, ly, 0.08, 0.025, 0.025, 0.08, M_DEN_OAKDK)

# Place settings that never move: a bread plate and roll and a water glass at
# all eight places, and the cutlery at the two places kept free for visitors
# (the guests' own knives, forks and spoons are animated props).
for k, pl in DF.PLACES.items():
    bx, by = pl["bread"].x, pl["bread"].y
    dine_cyl(f"DinnerSetBreadPlate{k}", bx, by, TT + 0.004, 0.075, 0.008, M_DINNER_CHINA, 16)
    dine_cyl(f"DinnerSetBreadRim{k}", bx, by, TT + 0.006, 0.076, 0.003, M_DINNER_GOLD, 16)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=10, ring_count=6, radius=0.032, location=(bx, by, TT + 0.03))
    bpy.context.active_object.name = f"DinnerSetRoll{k}"
    bpy.context.active_object.scale = (1.0, 0.8, 0.65)
    bpy.context.active_object.data.materials.append(M_DINNER_BREAD)
    wx, wy = pl["water"].x, pl["water"].y
    dine_cyl(f"DinnerSetWater{k}", wx, wy, TT + 0.035, 0.029, 0.068, M_DINNER_WATER, 12)
    dine_cyl(f"DinnerSetTumbler{k}", wx, wy, TT + 0.05, 0.033, 0.10, M_GLASSP, 12)
    if k in DF.EMPTY:
        yaw = math.radians(pl["yaw"])
        for nm, half in (("fork", (0.011, 0.10, 0.002)), ("knife", (0.008, 0.11, 0.003)),
                         ("spoon", (0.010, 0.10, 0.002))):
            p = pl[nm]
            ob = spa_box(f"DinnerSetCutlery{k}{nm}", (0, 0, 0), half, M_DINNER_SILVER, 0.0)
            ob.location = (p.x, p.y, TT + 0.003)
            ob.rotation_euler = (0, 0, yaw)
# Kitchen: the chef's warm plate stack, two copper pans at the stove end of the
# back counter and a chopping board (dinner_figures STACK / PANS / CHOP).
for i in range(DF.STACK_N):
    dine_cyl(f"DinnerSetStack{i}", DF.STACK.x, DF.STACK.y, DF.BACK_Z + 0.007 + i * 0.014, 0.125, 0.012,
             M_DINNER_CHINA, 20)
for j, pan in enumerate(DF.PANS):
    dine_cyl(f"DinnerSetPan{j}", pan.x, pan.y, DF.BACK_Z + 0.035, 0.10 if j == 0 else 0.085, 0.07, M_DINNER_COPPER, 20)
    add_box(f"DinnerSetPanHandle{j}", pan.x, pan.y + 0.17, DF.BACK_Z + 0.06, 0.012, 0.08, 0.008, M_DINNER_COPPER)
add_box("DinnerSetBoard", DF.CHOP.x, DF.CHOP.y, 0.91 + 0.012, 0.18, 0.12, 0.012, M_DINNER_BOARD)
for j, dy in enumerate((-0.38, 0.38)):                               # salt and pepper
    for i, dx in enumerate((-0.03, 0.03)):
        dine_cyl(f"DinnerSetCruet{j}{i}", TX + dx, TY + dy, TT + 0.035, 0.014, 0.07, M_DINNER_SILVER, 10)

join_objects("DiningRoom", ("DiningFloor", "DiningWainscot", "DiningCapRail"))
join_objects("DiningTable", ("DiningTable",))
join_objects("DiningCandelabras", ("DiningCandelabra",))
join_objects("DiningSideboards", ("DiningSideboard",))
join_objects("DinnerSettings", ("DinnerSet",))
join_objects("DiningChandelier", ("DiningChandelier",))
bpy.context.view_layer.update()

# Upstairs: shaft walls, glass doors, cab roof and its grey floor go; the
# gym-side face of the west wall (mirror in the niche) stays behind a walnut
# skin matching the hall cladding either side.
cut_opening(-1.02, 0.40, -5.66, -4.15, 3.49, 6.268, "lift-upper")
tex_box("HallSkinUpper", -1.0225, -4.905, 4.885, 0.0075, 0.695, 1.385, M_WENGE)   # x -1.03..-1.015, y -5.60..-4.21
# The gym niche behind it was open to the hall at its north end (x -1.59..-1.2,
# once half-hidden by the lift cladding and call-button plate): return the
# walnut to the hall wall at x -1.586.
tex_box("HallSkinUpperN", -1.3025, -4.22, 4.885, 0.2875, 0.01, 1.385, M_WENGE)     # x -1.59..-1.015, y -4.23..-4.21
flat_patch("HallFloorUpper", -1.02, 0.40, -5.66, -4.15, 3.50, M_PARQ)
flat_patch("HallCeilUpper", -1.02, 0.40, -5.66, -4.15, 6.262, M_HALL_CEIL, down=True)
bpy.context.view_layer.update()

# --- TV lounge: Charlie Harper's Malibu living room (Two and a Half Men) ------
# (west wall TV, x -10.95..-5.55, y 3.24..9.77; the piano sits south of it in
# the same room.) Set decorator's brief for the show: understated Spanish /
# Mediterranean, warm neutrals, "gnarly wood things and browns", kilim, Mexican
# tile, iron, big plants, taupe linen drapes. The white modular sofas, grey
# nesting tables, red bean ottoman and cube pouf, side tables, floor lamp and
# shag rug go. In their place: two olive chenille rolled-arm sofas in an L
# (one square to the TV), an iron-banded drum coffee table, a tan leather club
# chair and ottoman by the fire, rustic end tables with linen-shade lamps, a
# sisal rug, cream plaster walls, a beamed plank ceiling, Saltillo + Talavera
# tile on the fireplace ledge, iron sconces either side of the TV, and a jazz
# poster over the fire where the Jack Pine hung.
def recolor_mat_for(hexcol, rough=0.9, metal=0.0):
    return REGION_MATS[(hexcol, rough, metal)]

def delete_object_faces(names, x1, x2, y1, y2, z1, z2, label):
    total = 0
    for nm in names:
        ob = bpy.data.objects.get(nm)
        if not ob or ob.type != 'MESH':
            print(f"{label}: {nm} missing")
            continue
        mw = ob.matrix_world
        bmo = bmesh.new()
        bmo.from_mesh(ob.data)
        doomed = [f for f in bmo.faces
                  if x1 < (mw @ f.calc_center_median()).x < x2 and y1 < (mw @ f.calc_center_median()).y < y2
                  and z1 < (mw @ f.calc_center_median()).z < z2]
        if doomed:
            bmesh.ops.delete(bmo, geom=doomed, context='FACES')
            bmo.to_mesh(ob.data)
            total += len(doomed)
        bmo.free()
    bpy.context.view_layer.update()
    print(f"DELETE-OBJECT-FACES {label}: {total} faces")

delete_object_faces(("Object_36", "Object_100", "Object_98", "Object_84", "Object_82", "Object_102",
                     "Object_69", "Object_91", "Object_55", "Object_95", "Object_96", "Object_97",
                     "Object_107", "Object_14", "Object_94", "Object_67", "Object_61", "Object_60"),
                    -10.38, -5.62, 3.55, 9.55, -0.01, 1.0, "malibu-old-furniture")
delete_object_faces(("Object_43", "Object_60"), -10.95, -10.40, 8.80, 9.45, -0.01, 2.0, "malibu-floor-lamp")
delete_object_faces(("Object_8",), -10.75, -5.60, 3.25, 9.78, -0.01, 0.06, "malibu-shag-rug")

M_MAL_WALL = 'D8C7A6'
recolor_region(-11.15, -10.85, 3.0, 9.95, -0.1, 3.35, M_MAL_WALL, rough=0.9, label="MalibuWalls",
               only_mats={'blanc_001_Wall_Entity_Material'})
recolor_region(-11.15, -5.30, 9.60, 9.95, -0.1, 3.35, M_MAL_WALL, rough=0.9, label="MalibuWalls",
               only_mats={'blanc_001_Wall_Entity_Material'})
recolor_region(-10.97, -10.42, 3.25, 4.84, 1.1, 3.3, M_MAL_WALL, rough=0.9, label="MalibuWalls",
               only_mats={'fake_mat_69_64_65_255'})                                  # chimney breast
recolor_region(-5.56, -5.37, 3.30, 9.90, -0.1, 3.35, M_MAL_WALL, rough=0.9, label="MalibuWalls",
               only_mats={'blanc_001_Wall_Entity_Material'})                         # east window wall, lounge side
# The west wall's head band (one decimated strip y -1.99..9.77, z 2.54..3.25)
# stayed navy: skin it in plaster from the window jamb to the north corner.
add_box("MalibuSkinWestHead", -10.945, (1.26 + 9.77) / 2, (2.52 + 3.235) / 2, 0.004, (9.77 - 1.26) / 2,
        (3.235 - 2.52) / 2, recolor_mat_for(M_MAL_WALL))
# North window pelmet (camel) -> dark timber header like the beams.
recolor_region(-11.1, -5.35, 9.60, 9.85, 2.70, 3.30, "3B281A", rough=0.75, label="MalibuPelmet",
               only_mats={'fake_mat_251_251_251_255'})
recolor_region(-11.0, -5.30, -4.45, 9.95, 0.2, 3.3, "9C8B70", rough=0.9, label="MalibuDrapes",
               only_mats={'fake_mat_224_230_228_255'})                               # taupe linen

M_MAL_SISAL = artmat('malibu-sisal.jpg', 'MalibuSisal', 0.95)
M_MAL_CHENILLE = artmat('malibu-chenille.jpg', 'MalibuChenille', 0.95)
M_MAL_SALTILLO = artmat('malibu-saltillo.jpg', 'MalibuSaltillo', 0.75)
M_MAL_TALAVERA = artmat('malibu-talavera.jpg', 'MalibuTalavera', 0.3)
M_MAL_KILIM = artmat('malibu-kilim.jpg', 'MalibuKilim', 0.95)
M_MAL_CEIL = artmat('malibu-ceiling.jpg', 'MalibuCeilingPlank', 0.8)
M_MAL_BEAM = mk('MalibuBeam', '3B281A', 0.75)
M_MAL_WOOD = mk('MalibuWood', '3E2A1C', 0.6)
M_MAL_IRON = mk('MalibuIron', '1E1B19', 0.45, 0.35)
M_MAL_TAN = mk('MalibuLeatherTan', '9A6234', 0.5)
M_MAL_BINDING = mk('MalibuRugBinding', '3B2E22', 0.9)
M_MAL_TERRA = mk('MalibuTerracotta', 'A8573A', 0.8)
M_MAL_BLUE = mk('MalibuGlazeBlue', '27406E', 0.25)
M_MAL_SHADE = mk('MalibuLampShade', 'E8DCC0', 0.9)
_shb = M_MAL_SHADE.node_tree.nodes['Principled BSDF']
_shb.inputs['Emission Color'].default_value = (1.0, 0.86, 0.62, 1)
_shb.inputs['Emission Strength'].default_value = 0.5
M_MAL_BOOKS = [mk(f'MalibuBook{i}', h, 0.7) for i, h in enumerate(('6E2B23', '2E4A5E', 'B49A62', '3D4A2E'))]

def mal_quad(name, x1, x2, y1, y2, z, mat, tile, down=False, swap=False):
    """Flat quad with UVs in metres / tile (swap: u runs along y)."""
    me = bpy.data.meshes.new(name)
    vs = [(x1, y1, z), (x2, y1, z), (x2, y2, z), (x1, y2, z)]
    me.from_pydata(vs, [], [(3, 2, 1, 0) if down else (0, 1, 2, 3)])
    uvl = me.uv_layers.new(name="UVMap")
    for li, lp in enumerate(me.loops):
        vx, vy, _ = vs[lp.vertex_index]
        uvl.data[li].uv = (vy / tile, vx / tile) if swap else (vx / tile, vy / tile)
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    sc.collection.objects.link(ob)
    return ob

# Sisal rug with a dark linen binding, laid exactly over the old rug's footprint.
RX1, RX2, RY1, RY2 = -10.70, -5.66, 3.30, 9.73
mal_quad("MalibuRug", RX1, RX2, RY1, RY2, 0.045, M_MAL_SISAL, 0.5)
for nm, x, y, sx, sy in (("S", (RX1 + RX2) / 2, RY1 + 0.03, (RX2 - RX1) / 2, 0.03),
                         ("N", (RX1 + RX2) / 2, RY2 - 0.03, (RX2 - RX1) / 2, 0.03),
                         ("W", RX1 + 0.03, (RY1 + RY2) / 2, 0.03, (RY2 - RY1) / 2 - 0.06),
                         ("E", RX2 - 0.03, (RY1 + RY2) / 2, 0.03, (RY2 - RY1) / 2 - 0.06)):
    add_box(f"MalibuRugBind{nm}", x, y, 0.047, sx, sy, 0.0025, M_MAL_BINDING)

# Beamed plank ceiling over the lounge and the piano room: boards run
# north-south, dark beams run east-west every 1.1 m, and a girder finishes the
# piano room's open east edge (x -5.38, where the floor changes too).
mal_quad("MalibuCeiling", -10.95, -5.37, -4.41, 9.77, 3.235, M_MAL_CEIL, 1.0, down=True, swap=True)
tex_box("MalibuBeamGirder", -5.45, (-4.41 + 3.43) / 2, 3.11, 0.08, (3.43 + 4.41) / 2, 0.125, M_MAL_BEAM, scale=0.9)
for i, by in enumerate((-4.08, -2.98, -1.88, -0.78, 0.32, 1.42, 2.52, 3.62, 4.72, 5.82, 6.92, 8.02, 9.12)):
    tex_box(f"MalibuBeam{i}", (-10.95 - 5.36) / 2, by, 3.135, (10.95 - 5.36) / 2, 0.08, 0.10, M_MAL_BEAM, scale=0.9)

# Fireplace ledge: Saltillo on top, Talavera on the faces (the show's tiled
# step risers). Talavera band across the chimney breast over the opening.
retex_region(-11.10, -10.38, 3.20, 8.57, 0.40, 0.50, M_MAL_SALTILLO, "MalibuLedgeTop",
             only_objects=("Object_67",), normal='up')
retex_region(-11.10, -10.38, 3.20, 8.57, -0.01, 0.46, M_MAL_TALAVERA, "MalibuLedgeFace",
             only_objects=("Object_67",), normal='side')
tex_box("MalibuTalaveraBand", -10.434, 4.04, 1.28, 0.006, 0.78, 0.15, M_MAL_TALAVERA)

def mal_cyl(name, x, y, z, r, depth, mat, verts=24, rot=(0.0, 0.0, 0.0), r2=None):
    if r2 is None:
        bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=r, depth=depth, location=(x, y, z), rotation=rot)
    else:
        bpy.ops.mesh.primitive_cone_add(vertices=verts, radius1=r, radius2=r2, depth=depth, location=(x, y, z), rotation=rot)
    o = bpy.context.active_object
    o.name = name
    o.data.materials.append(mat)
    return o

def local_pt(c, yaw, lx, ly):
    ca, sa = math.cos(yaw), math.sin(yaw)
    return c[0] + lx * ca - ly * sa, c[1] + lx * sa + ly * ca

# Rolled-arm sofas (sitter faces local +x). Separate seat cushions with real
# gaps so snap_seat keeps each waypoint on its own cushion.
def mal_sofa(tag, c, yaw, L, n):
    Li = L - 0.48
    cw = (Li - 0.05 * (n - 1)) / n
    parts = [("Plinth", (0.0, 0, 0.21), (0.46, Li / 2, 0.10), 0.02),
             ("Back", (-0.365, 0, 0.58), (0.11, Li / 2, 0.27), 0.04)]
    for s, side in (("L", 1), ("R", -1)):
        parts.append((f"Arm{s}", (0.0, side * (L / 2 - 0.12), 0.355), (0.46, 0.12, 0.245), 0.03))
    seats = []
    for k in range(n):
        ly = -Li / 2 + cw / 2 + k * (cw + 0.05)
        parts.append((f"Cush{k}", (0.06, ly, 0.385), (0.37, cw / 2, 0.085), 0.03))
        parts.append((f"BackCush{k}", (-0.22, ly, 0.67), (0.08, cw / 2, 0.20), 0.05))
        seats.append(local_pt(c, yaw, 0.06, ly))
    for nm, loc, half, bev in parts:
        den_part(f"MalibuSofa{tag}{nm}", c, yaw, loc, half, M_MAL_CHENILLE, bev)
    for s, side in (("L", 1), ("R", -1)):
        x, y = local_pt(c, yaw, 0.0, side * (L / 2 - 0.11))
        mal_cyl(f"MalibuSofa{tag}Roll{s}", x, y, 0.60, 0.13, 0.94, M_MAL_CHENILLE, 24, rot=(0, math.pi / 2, yaw))
        x, y = local_pt(c, yaw, -0.10, side * (Li / 2 - 0.20))
        den_part(f"MalibuPillow{tag}{s}", (x, y), yaw + side * 0.25, (0, 0, 0.64), (0.07, 0.20, 0.18), M_MAL_KILIM, 0.04)
        for fx in (-0.40, 0.40):
            den_part(f"MalibuSofaFoot{tag}{s}{fx:+.1f}", c, yaw, (fx, side * (L / 2 - 0.08), 0.055),
                     (0.035, 0.035, 0.055), M_MAL_WOOD)
    bpy.context.view_layer.update()
    retex_region(-12, 0, 0, 12, -0.1, 1.5, M_MAL_CHENILLE, f"MalibuSofa{tag}Chenille",
                 only_objects=(f"MalibuSofa{tag}Plinth", f"MalibuSofa{tag}Back", f"MalibuSofa{tag}Arm",
                               f"MalibuSofa{tag}Cush", f"MalibuSofa{tag}Roll"), scale=0.25)
    retex_region(-12, 0, 0, 12, -0.1, 1.5, M_MAL_KILIM, f"MalibuPillow{tag}", only_objects=(f"MalibuPillow{tag}",), scale=0.5)
    return seats

SOFA_A = mal_sofa("A", (-7.28, 6.70), math.pi, 2.5, 3)          # square to the TV, back to the glass
SOFA_B = mal_sofa("B", (-8.95, 9.02), -math.pi / 2, 2.3, 3)     # north run, facing the fire
print("MALIBU sofa seats:", [(round(x, 2), round(y, 2)) for x, y in SOFA_A + SOFA_B])

# Drum coffee table: dark wood, two iron hoops, iron ring pulls, books, a bowl.
DX_, DY_ = -8.95, 6.70
mal_cyl("MalibuDrumBody", DX_, DY_, 0.20, 0.48, 0.40, M_MAL_WOOD, 40)
mal_cyl("MalibuDrumTop", DX_, DY_, 0.42, 0.52, 0.04, M_MAL_WOOD, 40)
for i, hz in enumerate((0.08, 0.32)):
    mal_cyl(f"MalibuDrumHoop{i}", DX_, DY_, hz, 0.488, 0.035, M_MAL_IRON, 40)
for i, a in enumerate((0.0, math.pi)):
    bpy.ops.mesh.primitive_torus_add(major_radius=0.055, minor_radius=0.008, major_segments=16, minor_segments=6,
                                     location=(DX_ + 0.495 * math.cos(a), DY_ + 0.495 * math.sin(a), 0.22),
                                     rotation=(math.pi / 2, 0, a + math.pi / 2))
    bpy.context.active_object.name = f"MalibuDrumRing{i}"
    bpy.context.active_object.data.materials.append(M_MAL_IRON)
for i, (bx, by, bz, sx, sy, sz, yaw, m) in enumerate((
        (-9.10, 6.50, 0.455, 0.13, 0.17, 0.015, 0.2, M_MAL_BOOKS[0]),
        (-9.10, 6.50, 0.484, 0.11, 0.15, 0.014, 0.35, M_MAL_BOOKS[1]),
        (-9.10, 6.50, 0.511, 0.12, 0.155, 0.013, 0.1, M_MAL_BOOKS[2]))):
    add_box(f"MalibuBook{i}", bx, by, bz, sx, sy, sz, m)
    bpy.context.active_object.rotation_euler = (0, 0, yaw)
mal_cyl("MalibuBowl", -8.78, 6.92, 0.485, 0.15, 0.09, M_MAL_TERRA, 32, r2=0.09)
mal_cyl("MalibuBowlGlaze", -8.78, 6.92, 0.5305, 0.135, 0.002, M_MAL_BLUE, 32)

# Charlie's tan leather club chair and ottoman by the fire, turned to the TV.
CLUB_C, CLUB_YAW = (-8.95, 4.20), math.radians(127.6)
for nm, loc, half, bev in (
        ("Base", (0.0, 0, 0.22), (0.42, 0.44, 0.16), 0.04),
        ("Seat", (0.06, 0, 0.43), (0.32, 0.28, 0.06), 0.03),
        ("Back", (-0.33, 0, 0.62), (0.10, 0.44, 0.28), 0.05),
        ("ArmL", (0.0, 0.36, 0.56), (0.42, 0.08, 0.14), 0.04),
        ("ArmR", (0.0, -0.36, 0.56), (0.42, 0.08, 0.14), 0.04),
        ("Ottoman", (0.78, 0, 0.21), (0.24, 0.27, 0.15), 0.03)):
    den_part(f"MalibuClub{nm}", CLUB_C, CLUB_YAW, loc, half, M_MAL_TAN, bev)
for i, (fx, fy) in enumerate(((0.36, 0.38), (0.36, -0.38), (-0.36, 0.38), (-0.36, -0.38),
                              (0.98, 0.22), (0.98, -0.22), (0.58, 0.22), (0.58, -0.22))):
    den_part(f"MalibuClubFoot{i}", CLUB_C, CLUB_YAW, (fx, fy, 0.03), (0.025, 0.025, 0.03), M_MAL_WOOD)
CLUB_SEAT = local_pt(CLUB_C, CLUB_YAW, 0.06, 0.0)

# Rustic end tables at both ends of the TV sofa, each with a dark bronze lamp
# and a glowing linen drum shade.
for i, (ex, ey) in enumerate(((-7.28, 5.10), (-7.28, 8.30))):
    add_box(f"MalibuEndTop{i}", ex, ey, 0.585, 0.25, 0.25, 0.025, M_MAL_WOOD)
    add_box(f"MalibuEndShelf{i}", ex, ey, 0.16, 0.22, 0.22, 0.015, M_MAL_WOOD)
    for j, (lx, ly) in enumerate(((-0.21, -0.21), (-0.21, 0.21), (0.21, -0.21), (0.21, 0.21))):
        add_box(f"MalibuEndLeg{i}{j}", ex + lx, ey + ly, 0.28, 0.03, 0.03, 0.28, M_MAL_WOOD)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=20, ring_count=10, radius=0.11, location=(ex, ey, 0.74))
    bpy.context.active_object.name = f"MalibuLampBody{i}"
    bpy.context.active_object.scale = (1, 1, 1.25)
    bpy.context.active_object.data.materials.append(M_MAL_IRON)
    mal_cyl(f"MalibuLampFoot{i}", ex, ey, 0.62, 0.07, 0.03, M_MAL_IRON, 20)
    mal_cyl(f"MalibuLampNeck{i}", ex, ey, 0.93, 0.012, 0.16, M_MAL_IRON, 10)
    mal_cyl(f"MalibuLampGlow{i}", ex, ey, 1.02, 0.05, 0.06, M_GLOW, 12)
    sh = mal_cyl(f"MalibuLampShade{i}", ex, ey, 1.06, 0.21, 0.27, M_MAL_SHADE, 32, r2=0.17)
    bmx = bmesh.new()
    bmx.from_mesh(sh.data)
    bmesh.ops.delete(bmx, geom=[f for f in bmx.faces if abs(f.normal.z) > 0.9], context='FACES')
    bmx.to_mesh(sh.data)
    bmx.free()

# Wrought-iron candle sconces either side of the TV (clear of its wall probes).
for i, sy in enumerate((5.15, 8.45)):
    add_box(f"MalibuSconcePlate{i}", -10.935, sy, 2.05, 0.008, 0.045, 0.11, M_MAL_IRON)
    mal_cyl(f"MalibuSconceArm{i}", -10.86, sy, 1.98, 0.009, 0.15, M_MAL_IRON, 8, rot=(0, math.pi / 2, 0))
    mal_cyl(f"MalibuSconceCup{i}", -10.79, sy, 2.00, 0.04, 0.03, M_MAL_IRON, 16)
    mal_cyl(f"MalibuSconceCandle{i}", -10.79, sy, 2.08, 0.016, 0.13, M_GLOW, 12)
    mal_cyl(f"MalibuSconceShade{i}", -10.79, sy, 2.10, 0.055, 0.17, M_GLASSP, 16, r2=0.045)

# Fire irons on the ledge beside the firebox, a Talavera-glazed urn at the
# ledge's north end, and big plants in terracotta.
add_box("MalibuIronsBase", -10.68, 5.02, 0.46, 0.09, 0.09, 0.01, M_MAL_IRON)
mal_cyl("MalibuIronsPost", -10.68, 5.02, 0.82, 0.01, 0.72, M_MAL_IRON, 8)
for i, (dx, dy) in enumerate(((-0.05, -0.04), (0.05, -0.04), (-0.05, 0.04), (0.05, 0.04))):
    mal_cyl(f"MalibuIron{i}", -10.68 + dx, 5.02 + dy, 0.80, 0.007, 0.66, M_MAL_IRON, 6)
    mal_cyl(f"MalibuIronHead{i}", -10.68 + dx, 5.02 + dy, 0.50, 0.022, 0.06, M_MAL_IRON, 8)
bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=12, radius=0.17, location=(-10.70, 8.20, 0.66))
bpy.context.active_object.name = "MalibuUrnBody"
bpy.context.active_object.scale = (1, 1, 1.2)
bpy.context.active_object.data.materials.append(M_MAL_BLUE)
mal_cyl("MalibuUrnNeck", -10.70, 8.20, 0.89, 0.07, 0.10, M_MAL_BLUE, 20, r2=0.09)
mal_cyl("MalibuUrnFoot", -10.70, 8.20, 0.47, 0.09, 0.04, M_MAL_BLUE, 20)
_pnw = plant("MalibuPlantNW", -10.55, 9.30, 0.0, 1.45, 0.6)
_pnw.data = _pnw.data.copy()
_pnw.data.materials.append(M_MAL_TERRA)
_bp = bmesh.new()
_bp.from_mesh(_pnw.data)
_pm = [m.name if m else '' for m in _pnw.data.materials]
# the house-plant copy drags a sliver of curtain along; the pot goes terracotta
bmesh.ops.delete(_bp, geom=[f for f in _bp.faces if _pm[f.material_index].startswith('fake_mat_224')], context='FACES')
# (jitter_islands dealt the pot a foliage green: it is everything below the soil)
for f in _bp.faces:
    if f.calc_center_median().z < 0.77 and not _pm[f.material_index].startswith('pack_004_chambre_001_plante___terreau'):
        f.material_index = _pm.index('MalibuTerracotta')
_bp.to_mesh(_pnw.data)
_bp.free()
retex_region(-6.7, -5.5, 8.80, 9.75, -0.01, 0.95, M_MAL_TERRA, "MalibuAgavePot", only_objects=("Object_22",))

# --- Piano room: the same Malibu house, south of the lounge -----------------
# (x -10.95..-5.38, y -4.41..3.24.) Navy/aubergine/oxblood walls to the same
# cream plaster; Saltillo terracotta across the whole west-end floor (one pair
# of source triangles, x -11.06..-5.38, y -4.41..9.87); a woven shade on the
# west window; the black paper-leaf vase becomes a terracotta potted plant;
# Charlie's bar cart in the south-west corner; the second jazz poster replaces
# Starry Night (gallery). The piano, its bench and rug stay.
recolor_region(-10.98, -5.26, -4.96, 3.24, -0.1, 3.35, M_MAL_WALL, rough=0.9, label="MalibuWalls",
               only_mats={'blanc_001_Wall_Entity_Material', 'gris_004_Wall_Entity_Material',
                          'enduit_004_Wall_Entity_Material'}, normal='side')
recolor_region(-5.34, -5.20, 3.24, 4.12, -0.1, 3.35, M_MAL_WALL, rough=0.9, label="MalibuWalls",
               only_mats={'blanc_001_Wall_Entity_Material'}, normal='side')        # pilaster by the lounge door
retex_region(-11.10, -5.37, -4.50, 9.90, -0.012, 0.012, M_MAL_SALTILLO, "MalibuFloor",
             only_objects=("Object_6",), normal='up')
delete_object_faces(("Object_70", "Object_114"), -10.95, -10.20, 1.80, 2.95, -0.01, 2.0, "piano-paper-vase")
delete_object_faces(("Object_47",), -9.30, -6.95, -2.75, -0.50, -0.01, 0.05, "piano-rug-debris")
# Woven shade, half lowered, across the west window (y -1.99..1.26, head 2.54).
tex_box("MalibuShade", -10.895, -0.46, 2.27, 0.012, 1.50, 0.27, M_MAL_SISAL, scale=0.5)
add_box("MalibuShadeRail", -10.88, -0.46, 2.035, 0.02, 1.50, 0.015, M_MAL_WOOD)
_ppw = plant("MalibuPlantPiano", -10.55, 2.42, 0.0, 1.35, 2.1)
_ppw.data = _ppw.data.copy()
_ppw.data.materials.append(M_MAL_TERRA)
_bp = bmesh.new()
_bp.from_mesh(_ppw.data)
_pm = [m.name if m else '' for m in _ppw.data.materials]
bmesh.ops.delete(_bp, geom=[f for f in _bp.faces if _pm[f.material_index].startswith('fake_mat_224')], context='FACES')
for f in _bp.faces:
    if f.calc_center_median().z < 0.77 and not _pm[f.material_index].startswith('pack_004_chambre_001_plante___terreau'):
        f.material_index = _pm.index('MalibuTerracotta')
_bp.to_mesh(_ppw.data)
_bp.free()

# Bar cart: oak shelves on an iron frame, whisky decanter, bottles, glasses,
# ice bucket. Corner of the west and south walls, clear of the poster.
BCX, BCY = -10.66, -3.95
for nm, z in (("Top", 0.80), ("Low", 0.30)):
    add_box(f"MalibuBar{nm}", BCX, BCY, z, 0.22, 0.38, 0.015, M_MAL_WOOD)
for j, (dx, dy) in enumerate(((-0.2, -0.36), (-0.2, 0.36), (0.2, -0.36), (0.2, 0.36))):
    mal_cyl(f"MalibuBarPost{j}", BCX + dx, BCY + dy, 0.41, 0.012, 0.82, M_MAL_IRON, 8)
    bpy.ops.mesh.primitive_torus_add(major_radius=0.035, minor_radius=0.012, major_segments=12, minor_segments=6,
                                     location=(BCX + dx, BCY + dy, 0.035), rotation=(0, math.pi / 2, 0))
    bpy.context.active_object.name = f"MalibuBarWheel{j}"
    bpy.context.active_object.data.materials.append(M_MAL_IRON)
for j, (dy, h, r, m) in enumerate(((-0.24, 0.30, 0.040, M_DEN_WHISKY), (-0.14, 0.28, 0.036, M_MAL_BLUE),
                                   (0.30, 0.32, 0.038, M_DEN_WHISKY))):
    mal_cyl(f"MalibuBarBottle{j}", BCX - 0.08, BCY + dy, 0.815 + h / 2, r, h, m, 16)
    mal_cyl(f"MalibuBarBottleNeck{j}", BCX - 0.08, BCY + dy, 0.815 + h + 0.04, 0.012, 0.08, m, 10)
mal_cyl("MalibuBarDecanter", BCX + 0.06, BCY + 0.05, 0.90, 0.07, 0.17, M_GLASSP, 20)
mal_cyl("MalibuBarDecanterWhisky", BCX + 0.06, BCY + 0.05, 0.87, 0.062, 0.10, M_DEN_WHISKY, 20)
mal_cyl("MalibuBarIce", BCX + 0.08, BCY - 0.22, 0.89, 0.08, 0.15, M_BRASS, 20)
for j, dy in enumerate((0.20, 0.28)):
    mal_cyl(f"MalibuBarGlass{j}", BCX + 0.12, BCY + dy, 0.855, 0.033, 0.08, M_GLASSP, 16)
for j, dy in enumerate((-0.2, 0.0, 0.2)):
    add_box(f"MalibuBarBook{j}", BCX, BCY + dy, 0.40, 0.12, 0.08, 0.085, M_MAL_BOOKS[j])

join_objects("MalibuPiano", ("MalibuShade", "MalibuBar"))
join_objects("MalibuSofaA", ("MalibuSofaA", "MalibuPillowA"))
join_objects("MalibuSofaB", ("MalibuSofaB", "MalibuPillowB"))
join_objects("MalibuClub", ("MalibuClub",))
join_objects("MalibuDrum", ("MalibuDrum", "MalibuBook", "MalibuBowl"))
join_objects("MalibuEndTables", ("MalibuEnd", "MalibuLamp"))
join_objects("MalibuFire", ("MalibuSconce", "MalibuIron", "MalibuTalaveraBand", "MalibuUrn"))
join_objects("MalibuRoom", ("MalibuRug", "MalibuBeam", "MalibuCeiling", "MalibuSkin"))
bpy.context.view_layer.update()

# --- Patio BBQ: glass balustrade along the open north edge ------------------
if M_GLASSP:
    add_box("ParaNglass", 0.325, 9.84, 0.56, 5.625, 0.015, 0.54, M_GLASSP)
add_box("ParaNrail", 0.325, 9.84, 1.12, 5.625, 0.03, 0.025, M_RAIL)
add_box("ParaNcurb", 0.325, 9.84, 0.035, 5.625, 0.03, 0.035, M_RAIL)

# --- Piano room west window: a closed roller blind (one 6 m espresso sheet at
# x -11.81, y -5.7..-0.57) hangs 0.78 m outside the glass, just past the
# glass-clear 0.75 m reach, and covered the south half of the window.
region_delete_mats(-11.9, -11.7, -5.8, -0.5, -0.1, 6.5, {'fake_mat_6_5_5_255'}, "piano-west-blind")
# Its curtain pelmet along the west wall (x -11.0..-10.85, y -4.44..3.36,
# z 2.74..3.25) has no front face: the bottom edge and the top (coplanar with
# the ceiling, so it strobes) read as two flickering orange lines over an open
# slot below the ceiling. Remove the box; the rod and curtains stay.
region_delete_mats(-11.01, -10.84, -4.45, 3.37, 2.73, 3.26, {'fake_mat_251_251_251_255'}, "piano-west-pelmet")

# --- Curtains and rods poke 2-3 cm through the ceilings (3.25 downstairs, 6.27
# upstairs); the pleat tops strobe against the ceiling along the wall line.
# Pull any vertex in that band back under the ceiling, but only where a
# ceiling is actually overhead (double-height drops pass through untouched).
def tuck_under_ceilings(obnames, ceilings=(3.25, 6.27), band=0.12, gap=0.03):
    dgc = bpy.context.evaluated_depsgraph_get()
    skip = set(obnames)
    def ceiling_above(x, y, c):
        o = Vector((x, y, c - 0.08))
        for _ in range(6):
            ok, loc, nrm, fi, ob, mw = sc.ray_cast(dgc, o, Vector((0, 0, 1)), distance=0.2)
            if not ok:
                return False
            if ob.name not in skip:
                return abs(loc.z - c) < 0.02
            o = loc + Vector((0, 0, 0.001))
        return False
    moves = []
    for name in obnames:
        ob = bpy.data.objects.get(name)
        if not ob:
            print("TUCK miss:", name)
            continue
        mw, mwi = ob.matrix_world, ob.matrix_world.inverted()
        for v in ob.data.vertices:
            w = mw @ v.co
            for c in ceilings:
                if c - gap < w.z < c + band and ceiling_above(w.x, w.y, c):
                    moves.append((ob, v, mwi @ Vector((w.x, w.y, c - gap))))
                    break
    for ob, v, co in moves:
        v.co = co
    for name in obnames:
        if bpy.data.objects.get(name):
            bpy.data.objects[name].data.update()
    bpy.context.view_layer.update()
    print(f"TUCK curtains/rods: {len(moves)} vertices")
tuck_under_ceilings(("Object_54", "Object_94"))

# --- Kitchen microwave left of the serving hatch: only its front panel and
# frame exist (y -3.79..-3.71, z 0.70..1.12), so it read as an open box.
# Close it with a body behind the panel, clear of the panel and the wall.
M_MICRO = mk('MicrowaveBody', 'E4E3DF', 0.4)
add_box("KitchenMicrowaveBody", 10.5025, -3.9975, 1.0175, 0.2725, 0.2025, 0.1025, M_MICRO)

# --- Closets: open every wardrobe run and fill it ---------------------------
# The walk-ins (NW, NE) and the SW bedroom's built-in were closed door fronts
# over empty carcasses. Cut each run out (fronts, handles, carcass), then
# rebuild it open: oak carcass and shelves, linen back lining, steel rails,
# and hanging clothes, folded stacks, shoes, boots, bags and boxes. All the
# contents share one material over a swatch atlas (art/closet-atlas.png), so
# every closet together costs three draw calls.
import random
M_KIT = artmat('closet-atlas.png', 'ClosetContents', 0.9)
M_BACK = mk('WardrobeBackLinen', 'E6DDCC', 0.92)
KIT = bmesh.new()
KIT_UV = KIT.loops.layers.uv.new("UVMap")
# Swatch indices into the 8x8 atlas (row * 8 + col); see make-furniture-textures.py.
SW_SHIRT = list(range(0, 8))
SW_SUIT = list(range(8, 16))
SW_DRESS = list(range(16, 24))
SW_COAT = list(range(24, 32))
SW_DENIM = list(range(32, 40))
SW_KNIT = list(range(40, 48))
SW_LEATHER = list(range(48, 55))
SW_CANVAS = 55
SW_KRAFT, SW_WICKER, SW_HANGER, SW_STEEL, SW_SOLE = 57, 58, 59, 60, 61

def kit_box(fr, u, d, z, hu, hd, hz, sw, top=(1.0, 1.0)):
    """Box centred on run-local (u along the run, d out from the back wall,
    z up), every face mapped onto one atlas swatch. `top` narrows the top
    face (u, d) for shoulders, shoe uppers and boot shafts."""
    vs = []
    for sz, (su, sd) in ((-1, (1.0, 1.0)), (1, top)):
        for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            vs.append(KIT.verts.new(fr(u + a * hu * su, d + b * hd * sd, z + sz * hz)))
    r, c = divmod(sw, 8)
    u0, v0, du = (c + .12) / 8, 1 - (r + .88) / 8, .76 / 8
    cuv = ((u0, v0), (u0 + du, v0), (u0 + du, v0 + du), (u0, v0 + du))
    for fi in ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
        f = KIT.faces.new([vs[i] for i in fi])
        for loop, uv in zip(f.loops, cuv):
            loop[KIT_UV].uv = uv

def run_box(fr, U, name, u, d, z, hu, hd, hz, mat, oak=False):
    c = fr(u, d, z)
    sx, sy = (hu, hd) if abs(U[0]) > 0.5 else (hd, hu)
    if oak:
        tex_box(name, c.x, c.y, c.z, sx, sy, hz, mat, scale=0.8, rot=(0.0 if abs(U[0]) > 0.5 else math.pi / 2))
    else:
        add_box(name, c.x, c.y, c.z, sx, sy, hz, mat)

def shoe_pair(fr, rng, u, depth, zs, boots=False):
    sw = rng.choice(SW_LEATHER)
    l, w = (.27, .095) if boots else (rng.uniform(.24, .27), rng.uniform(.08, .09))
    dc = depth - .04 - l / 2                  # toes to the front edge
    for du in (-.06, .06):
        kit_box(fr, u + du, dc, zs + .011, w / 2, l / 2, .011, SW_SOLE)
        kit_box(fr, u + du, dc - .02, zs + .022 + .033, w / 2 * .96, l * .4, .033, sw, top=(.85, .62))
        if boots:
            kit_box(fr, u + du, dc - l / 2 + .07, zs + .022 + .19, w / 2 * .9, .065, .19, sw, top=(1.0, .9))

def folded_stack(fr, rng, u, d, zs, hu, hd, zmax):
    pal = rng.choice((SW_KNIT, SW_DENIM, SW_SHIRT, SW_SUIT))
    base = rng.choice(pal)
    z = zs
    for _ in range(rng.randint(3, 7)):
        h = rng.uniform(.04, .06)
        if z + h > zmax:
            break
        sw = base if rng.random() < .55 else rng.choice(pal)
        kit_box(fr, u + rng.uniform(-.012, .012), d + rng.uniform(-.012, .012), z + h / 2, hu, hd, h / 2, sw)
        z += h

def hang(fr, rng, a, b, depth, rail_z, lengths, palettes):
    w = min(.46, depth - .08)
    kit_box(fr, (a + b) / 2, depth / 2, rail_z, (b - a) / 2 - .01, .011, .011, SW_STEEL)
    u = a + .06
    while u < b - .05:
        t = rng.uniform(.018, .04)
        ln = rng.uniform(*lengths)
        sw = rng.choice(rng.choice(palettes))
        kit_box(fr, u, depth / 2, rail_z - .035, .006, w / 2 * .92, .012, SW_HANGER)
        kit_box(fr, u, depth / 2, rail_z - .045 - ln / 2, t, w / 2, ln / 2, sw, top=(.7, .8))
        u += 2 * t + rng.uniform(.012, .035)

def fill_run(tag, P0, U, D, L, depth, z0, z1, sections, seed, fascia_to=None):
    rng = random.Random(seed)
    fr = lambda u, d, z: Vector((P0[0] + u * U[0] + d * D[0], P0[1] + u * U[1] + d * D[1], z))
    T = .018
    run_box(fr, U, f"ClosetBack{tag}", L / 2, .006, (z0 + z1) / 2, L / 2, .006, (z1 - z0) / 2, M_BACK)
    run_box(fr, U, f"ClosetOak{tag}Top", L / 2, depth / 2, z1 - T / 2, L / 2, depth / 2, T / 2, M_OAKL, oak=True)
    run_box(fr, U, f"ClosetOak{tag}Base", L / 2, depth / 2, z0 + .045, L / 2, depth / 2 - .01, .045, M_OAKL, oak=True)
    if fascia_to:
        run_box(fr, U, f"ClosetOak{tag}Fascia", L / 2, depth - T / 2, (z1 + fascia_to) / 2, L / 2, T / 2, (fascia_to - z1) / 2, M_OAKL, oak=True)
    edges = sorted({s for a, b, _ in sections for s in (a, b)})
    for i, s in enumerate(edges):
        s = min(max(s, T / 2), L - T / 2)
        run_box(fr, U, f"ClosetOak{tag}Div{i}", s, depth / 2, (z0 + z1) / 2, T / 2, depth / 2, (z1 - z0) / 2, M_OAKL, oak=True)
    floor = z0 + .09
    for k, (a, b, kind) in enumerate(sections):
        a, b = a + T / 2, b - T / 2
        mid, hu = (a + b) / 2, (b - a) / 2
        shelf = lambda z, n: run_box(fr, U, f"ClosetOak{tag}S{k}_{n}", mid, depth / 2, z, hu, depth / 2 - .01, T / 2, M_OAKL, oak=True)
        if kind in ('long', 'double'):
            top_rail = min(floor + 1.85, z1 - .40)
            shelf(top_rail + .16, 'top')
            if kind == 'long':
                hang(fr, rng, a, b, depth, top_rail, (.95, 1.30), (SW_COAT, SW_DRESS, SW_SUIT))
                u = a + .16
                while u < b - .14:
                    shoe_pair(fr, rng, u, depth, floor, boots=rng.random() < .7)
                    u += .27
            else:
                hang(fr, rng, a, b, depth, top_rail, (.70, .85), (SW_SHIRT, SW_SHIRT, SW_KNIT))
                hang(fr, rng, a, b, depth, floor + .93, (.52, .62), (SW_SUIT, SW_DENIM))
            # Above the top shelf: bags, boxes and a folded stack or two.
            zs, u = top_rail + .16 + T / 2, a + .05
            while u < b - .12:
                pick = rng.random()
                if pick < .35:
                    kit_box(fr, u + .15, depth / 2, zs + .11, .15, min(.13, depth / 2 - .04), .11, rng.choice((SW_KRAFT, SW_WICKER, SW_CANVAS)))
                    u += .34
                elif pick < .6:
                    kit_box(fr, u + .13, depth * .45, zs + .10, .13, .06, .10, rng.choice(SW_LEATHER), top=(.85, .7))
                    u += .30
                else:
                    folded_stack(fr, rng, u + .15, depth / 2, zs, .15, min(.13, depth / 2 - .04), z1 - .03)
                    u += .34
        else:
            step = .21 if kind == 'shoes' else .33
            zs, n = floor, 0
            while zs < z1 - .30:
                if n:
                    shelf(zs, n)
                zt = zs + (T / 2 if n else 0.0)
                u = a + .15
                shoes_here = kind == 'shoes' and zs < z0 + 1.7 or kind == 'shelves' and n < 2
                while u < b - .13:
                    if shoes_here:
                        shoe_pair(fr, rng, u, depth, zt, boots=(kind == 'shelves' and n == 0 and rng.random() < .5))
                        u += .27
                    elif zs > z1 - .75:
                        kit_box(fr, u + .01, depth / 2, zt + .11, .15, min(.14, depth / 2 - .04), .11, rng.choice((SW_KRAFT, SW_WICKER, SW_CANVAS)))
                        u += .34
                    else:
                        folded_stack(fr, rng, u, depth / 2, zt, .14, min(.13, depth / 2 - .04), zt + step - .04)
                        u += .32
                zs += step
                n += 1
    print(f"CLOSET {tag}: {len(sections)} sections over {L:.2f} m")

# NW walk-in (floor 3.50, carcass ceiling 5.82). The south run keeps its
# middle bay closed: the dressing mirror hangs on it.
for label, box in (("W", (-10.945, -10.33, 1.43, 3.42)), ("E", (-8.07, -7.405, 1.43, 3.42)),
                   ("SL", (-10.94, -9.80, 0.91, 1.47)), ("SR", (-8.60, -7.41, 0.91, 1.47))):
    cut_opening(*box, 3.53, 5.79, f"closet-nw-{label}")
fill_run("NW_W", (-10.955, 1.43), (0, 1), (1, 0), 1.99, .545, 3.50, 5.80, [(0, 1.0, 'long'), (1.0, 1.99, 'double')], 11)
fill_run("NW_E", (-7.395, 3.42), (0, -1), (-1, 0), 1.99, .605, 3.50, 5.80, [(0, 1.0, 'long'), (1.0, 1.99, 'shelves')], 12)
fill_run("NW_SL", (-10.945, .905), (1, 0), (0, 1), 1.145, .505, 3.50, 5.80, [(0, 1.145, 'shoes')], 13)
fill_run("NW_SR", (-8.60, .905), (1, 0), (0, 1), 1.19, .505, 3.50, 5.80, [(0, 1.19, 'shelves')], 14)
# NE walk-in (carpet 3.53, fronts ran to the 6.27 ceiling).
cut_opening(7.655, 8.35, 1.17, 3.86, 3.56, 6.25, "closet-ne-W")
cut_opening(8.30, 11.39, .675, 1.22, 3.56, 6.25, "closet-ne-S")
fill_run("NE_W", (7.645, 3.86), (0, -1), (1, 0), 2.69, .635, 3.53, 6.05,
         [(0, .95, 'double'), (.95, 1.75, 'shelves'), (1.75, 2.69, 'long')], 21, fascia_to=6.26)
fill_run("NE_S", (8.30, .665), (1, 0), (0, 1), 3.09, .485, 3.53, 6.05,
         [(0, 1.0, 'shoes'), (1.0, 2.05, 'double'), (2.05, 3.09, 'shelves')], 22, fascia_to=6.26)
add_box("ClosetBenchNE", 11.13, 2.55, 3.75, .20, .55, .22, M_OTTO)
# SW bedroom built-in on the gym wall (0.38 m deep, floor to ceiling).
cut_opening(-5.93, -5.495, -5.19, -1.82, 3.53, 6.25, "closet-sw")
fill_run("SW", (-5.485, -1.815), (0, -1), (-1, 0), 3.37, .38, 3.50, 6.05,
         [(0, 1.15, 'long'), (1.15, 2.25, 'shelves'), (2.25, 3.37, 'double')], 31, fascia_to=6.26)

bmesh.ops.recalc_face_normals(KIT, faces=KIT.faces[:])
_kit_me = bpy.data.meshes.new("ClosetKit")
KIT.to_mesh(_kit_me)
KIT.free()
_kit_me.materials.append(M_KIT)
sc.collection.objects.link(bpy.data.objects.new("ClosetKit", _kit_me))
print(f"CLOSET KIT: {len(_kit_me.polygons)} faces")
join_objects("ClosetJoinery", ("ClosetOak",))
join_objects("ClosetBackLining", ("ClosetBack",))

# --- The Rovers Return Inn: Coronation Street's corner pub, 1:1 ---------------
# Jay asked for the Rovers on the big two-storey south balcony: the pub's
# Coronation Street front stands on the balcony edge (entry from the ground
# storey through a recessed lobby door in that flat front) and its body runs
# south over the bare roof slab to the slab's edge. Its flat roof is a slab
# with a brick parapet: a roof terrace reached from upstairs through a new
# door in the sky den's south wall. Footprint x -4.0..7.0, y -16.85..-9.80
# (11 x 7 m, a real corner-pub size), floor 0.10 (deck level), ceiling 3.20,
# roof deck 3.53 (sky den floor). Plan from the set: Rosamund Street (the
# corner) on the LEFT as you come in, No.1's party wall on the right with the
# Gents and Ladies doors in it; the bar takes up the back of the room and the
# public space wraps it in an L; staff get behind through a lifting flap at
# the counter's end; the private door to the back room and the cellar
# trapdoor are behind the bar; alcoves under the front windows, the old snug
# corner by the side windows, darts at the rear of the right-hand wall, the
# piano. Finishes are the post-1986 single bar: mahogany counter and
# handpumps, back bar of mirrors and optics, red buttoned velour, claret
# carpet, oxblood damask over a mahogany dado, Betty's Hotpot on the board.
# Textures from make-rovers-textures.py. The skyline cylinder grows to 21 m.
RV_X1, RV_X2, RV_Y1, RV_Y2 = -4.0, 7.0, -16.85, -9.80
RV_T = 0.30
RV_IX1, RV_IX2, RV_IY1, RV_IY2 = RV_X1 + RV_T, RV_X2 - RV_T, RV_Y1 + RV_T, RV_Y2 - RV_T
RV_A, RV_B = (7.0, -10.75), (6.05, -9.80)            # outer corner chamfer (NE, Rosamund St)
RV_FZ, RV_CZ, RV_SLAB, RV_DECK = 0.10, 3.20, 3.50, 3.53
RV_OUTER = [(RV_X1, RV_Y1), (RV_X2, RV_Y1), RV_A, RV_B, (RV_X1, RV_Y2)]
# Inner chamfer line is the outer one (x + y = -3.75) moved 0.30 m inward.
_RV_CI = -3.75 - RV_T * math.sqrt(2)
RV_INNER = [(RV_IX1, RV_IY1), (RV_IX2, RV_IY1), (RV_IX2, _RV_CI - RV_IX2), (_RV_CI - RV_IY2, RV_IY2), (RV_IX1, RV_IY2)]
# Recessed lobby door in the flat front (clear opening x, lobby back line y).
RV_DOOR_X = (-1.30, 0.0)
RV_DOOR_Y = -10.70
RV_PORCH_Z = 2.60          # above the nav floor raycast origin (2.55)

M_RV_BRICK = artmat('rovers-brick.jpg', 'RoversBrick', 0.9)
M_RV_RISER = artmat('rovers-riser.jpg', 'RoversRiserTile', 0.25)
M_RV_DAMASK = artmat('rovers-damask.jpg', 'RoversDamask', 0.85)
M_RV_PANEL = artmat('rovers-panel.jpg', 'RoversPanel', 0.55)
M_RV_CARPET = artmat('rovers-carpet.jpg', 'RoversCarpet', 0.95)
M_RV_BOARDS = artmat('rovers-boards.jpg', 'RoversBoards', 0.7)
M_RV_CEIL = artmat('rovers-ceiling.jpg', 'RoversCeiling', 0.9)
M_RV_VELOUR = artmat('rovers-velour.jpg', 'RoversVelour', 0.95)
M_RV_ETCHED = artmat('rovers-etched.jpg', 'RoversEtchedGlass', 0.15)
M_RV_STAINED = artmat('rovers-stained.jpg', 'RoversStainedGlass', 0.2)
M_RV_FASCIA = artmat('rovers-fascia.jpg', 'RoversFascia', 0.4)
M_RV_NEWTON = artmat('rovers-newton.jpg', 'RoversNewtonBoard', 0.4)
M_RV_LICENSEE = artmat('rovers-licensee.jpg', 'RoversLicensee', 0.4)
M_RV_BACKBAR = artmat('rovers-backbar.jpg', 'RoversBackBar', 0.35)
M_RV_DART = artmat('rovers-dartboard.jpg', 'RoversDartboard', 0.8)
M_RV_HOTPOT = artmat('rovers-hotpot.jpg', 'RoversHotpotBoard', 0.9)
M_RV_POSTER = artmat('rovers-poster.jpg', 'RoversPoster', 0.8)
# Stained glass and the back-bar mirrors glow a little, as if lit from behind.
for _m, _s in ((M_RV_STAINED, 0.9), (M_RV_ETCHED, 0.35), (M_RV_BACKBAR, 0.25)):
    _nt = _m.node_tree
    _tx = next(n for n in _nt.nodes if n.type == 'TEX_IMAGE')
    _nt.links.new(_tx.outputs['Color'], _nt.nodes['Principled BSDF'].inputs['Emission Color'])
    _nt.nodes['Principled BSDF'].inputs['Emission Strength'].default_value = _s
M_RV_MAHOG = mk('RoversMahogany', '3E1E12', 0.5)
M_RV_CREAM = mk('RoversCreamPaint', 'E4D8B8', 0.6)
M_RV_STONE = mk('RoversStone', 'C9BC9C', 0.85)
M_RV_BLACK = mk('RoversGloss', '141414', 0.3)
M_RV_GREEN = mk('RoversGreenPaint', '1F3A2C', 0.45)
M_RV_BRASS = mk('RoversBrass', 'B08A45', 0.35, 0.45)
M_RV_IRON = mk('RoversIron', '1E1B19', 0.45, 0.35)
M_RV_COPPER = mk('RoversCopper', '9A5A34', 0.35, 0.4)
M_RV_ALE = mk('RoversAle', '8A4A16', 0.15)
M_RV_FROTH = mk('RoversFroth', 'EFE6CF', 0.8)
M_RV_GLOBE = mk('RoversGlobe', 'F2E6C8', 0.5)
_gbv = M_RV_GLOBE.node_tree.nodes['Principled BSDF']
_gbv.inputs['Emission Color'].default_value = (1.0, 0.84, 0.58, 1)
_gbv.inputs['Emission Strength'].default_value = 2.2

def rv_planar_uv(ob, scale):
    """World-planar UVs on every face of ob (u, v in metres / scale)."""
    bpy.context.view_layer.update()
    me = ob.data
    if not me.uv_layers:
        me.uv_layers.new(name="UVMap")
    uv = me.uv_layers.active.data
    mw = ob.matrix_world
    m3 = mw.to_3x3()
    for p in me.polygons:
        n = (m3 @ p.normal).normalized()
        for li, vi in zip(p.loop_indices, p.vertices):
            w = mw @ me.vertices[vi].co
            if abs(n.z) > 0.5:
                u, v = w.x, w.y
            elif abs(n.x) > abs(n.y):
                u, v = w.y, w.z
            else:
                u, v = w.x, w.z
            uv[li].uv = (u / scale, v / scale)

def rv_box(name, x1, x2, y1, y2, z1, z2, mat, scale=None):
    add_box(name, (x1 + x2) / 2, (y1 + y2) / 2, (z1 + z2) / 2, (x2 - x1) / 2, (y2 - y1) / 2, (z2 - z1) / 2, mat)
    ob = bpy.context.active_object
    if scale:
        rv_planar_uv(ob, scale)
    return ob

def rv_rbox(name, c, yaw, lx1, lx2, ly1, ly2, z1, z2, mat, scale=None):
    """Box in a frame centred on c turned by yaw (local x along the wall)."""
    lx, ly = (lx1 + lx2) / 2, (ly1 + ly2) / 2
    px, py = local_pt(c, yaw, lx, ly)
    add_box(name, px, py, (z1 + z2) / 2, (lx2 - lx1) / 2, (ly2 - ly1) / 2, (z2 - z1) / 2, mat)
    ob = bpy.context.active_object
    ob.rotation_euler = (0, 0, yaw)
    if scale:
        rv_planar_uv(ob, scale)
    return ob

def rv_quad(name, a, b, z0, z1, mat, ut=None, vt=None, u0=0.0):
    """Vertical quad from a to b (a = the viewer's left). Without ut/vt the
    image fills it once (UV 0..1); with them it tiles in metres."""
    L = math.hypot(b[0] - a[0], b[1] - a[1])
    me = bpy.data.meshes.new(name)
    vs = [(a[0], a[1], z0), (b[0], b[1], z0), (b[0], b[1], z1), (a[0], a[1], z1)]
    me.from_pydata(vs, [], [(0, 1, 2, 3)])
    uvl = me.uv_layers.new(name="UVMap")
    for li, (s, t) in enumerate(((0, 0), (1, 0), (1, 1), (0, 1))):
        if ut:
            uvl.data[li].uv = (u0 + s * L / ut, t * (z1 - z0) / vt)
        else:
            uvl.data[li].uv = (s, t)
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    sc.collection.objects.link(ob)
    return ob

def rv_band(name, a, b, z0, z1, holes, mat, ut, vt):
    """Wall skin from a to b over z0..z1, tiled in metres, with rectangular
    holes [(s1, s2, hz0, hz1)] measured along a->b. UVs stay continuous."""
    L = math.hypot(b[0] - a[0], b[1] - a[1])
    dx, dy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
    rects, s = [], 0.0
    for s1, s2, hz0, hz1 in sorted(holes):
        if s1 > s:
            rects.append((s, s1, z0, z1))
        if hz0 > z0:
            rects.append((s1, s2, z0, hz0))
        if hz1 < z1:
            rects.append((s1, s2, hz1, z1))
        s = s2
    if s < L:
        rects.append((s, L, z0, z1))
    for k, (s1, s2, za, zb) in enumerate(rects):
        pa = (a[0] + dx * s1, a[1] + dy * s1)
        pb = (a[0] + dx * s2, a[1] + dy * s2)
        ob = rv_quad(f"{name}{k}", pa, pb, za, zb, mat, ut, vt, u0=s1 / ut)
        uvl = ob.data.uv_layers.active.data
        for li in range(4):
            u, v = uvl[li].uv
            uvl[li].uv = (u, v + (za - z0) / vt)

def rv_poly(name, pts, z, mat, tile, down=False):
    me = bpy.data.meshes.new(name)
    vs = [(x, y, z) for x, y in pts]
    idx = list(range(len(vs)))
    me.from_pydata(vs, [], [tuple(reversed(idx)) if down else tuple(idx)])
    uvl = me.uv_layers.new(name="UVMap")
    for li, lp in enumerate(me.loops):
        vx, vy, _ = vs[lp.vertex_index]
        uvl.data[li].uv = (vx / tile, vy / tile)
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    sc.collection.objects.link(ob)
    return ob

def rv_prism(name, pts, z0, z1, mat, scale):
    me = bpy.data.meshes.new(name)
    n = len(pts)
    vs = [(x, y, z0) for x, y in pts] + [(x, y, z1) for x, y in pts]
    faces = [tuple(reversed(range(n))), tuple(range(n, 2 * n))]
    faces += [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
    me.from_pydata(vs, [], faces)
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    sc.collection.objects.link(ob)
    rv_planar_uv(ob, scale)
    return ob

def rv_cyl(name, x, y, z, r, depth, mat, verts=12, rot=(0.0, 0.0, 0.0)):
    return mal_cyl(name, x, y, z, r, depth, mat, verts=verts, rot=rot)

# Nothing may stand in the footprint before we build (the slab is bare roof).
_dg = bpy.context.evaluated_depsgraph_get()
for _x in (RV_X1 + 0.3, 1.5, RV_X2 - 0.3):
    for _y in (RV_Y2 - 0.7, -13.3, RV_Y1 + 0.3):
        _ok, _loc, *_ = sc.ray_cast(_dg, Vector((_x, _y, 3.1)), Vector((0, 0, -1)), distance=3.5)
        if not _ok or _loc.z > 0.02:
            raise RuntimeError(f"ROVERS GATE: footprint not bare slab at ({_x},{_y}): {_loc if _ok else None}")

# The balcony's glass edge stops at the pub: its north facade is the edge
# now. Keep the run west of the pub's west wall and east of its east wall.
for nm in ("ParaMidGlassS", "ParaMidRailS", "ParaMidCurbS", "ParaSEglassS", "ParaSErailS", "ParaSEcurbS"):
    ob = bpy.data.objects.get(nm)
    if ob:
        bpy.data.objects.remove(ob, do_unlink=True)
def rv_balustrade(tag, x1, x2, y1, y2):
    cx, cy, hx, hy = (x1 + x2) / 2, (y1 + y2) / 2, max((x2 - x1) / 2, 0.015), max((y2 - y1) / 2, 0.015)
    if M_GLASSP:
        add_box(f"RvRailGlass{tag}", cx, cy, 0.625, hx, hy, 0.525, M_GLASSP)
    add_box(f"RvRailTop{tag}", cx, cy, 1.17, hx + 0.015 * (hx < 0.02), hy + 0.015 * (hy < 0.02), 0.025, M_RAIL)
    add_box(f"RvRailCurb{tag}", cx, cy, 0.07, hx + 0.015 * (hx < 0.02), hy + 0.015 * (hy < 0.02), 0.035, M_RAIL)
rv_balustrade("MidS", -7.72, RV_X1, -9.74, -9.74)
rv_balustrade("SES", RV_X2, 11.40, -9.74, -9.74)
rv_balustrade("CornerE", RV_X2, RV_X2, RV_A[1], -9.74)
# Stone kerb along the front, and the corner's outside triangle at deck level.
rv_box("RvExtKerb", RV_X1, RV_X2, RV_Y2, -9.74, 0.0, RV_FZ, M_RV_STONE, 0.6)
rv_prism("RvExtCornerFlag", [RV_B, (RV_X2, RV_Y2), RV_A], 0.0, RV_FZ, M_RV_STONE, 0.6)

# --- Shell: brick walls with window and door openings -------------------------
WIN_N = ((-3.25, -1.95), (0.75, 2.45), (3.25, 4.95))     # north (Coronation St) front, x ranges
WIN_E = ((-14.10, -12.70), (-12.30, -11.00))             # east (Rosamund St) side, y ranges
WZ0, WZ1 = 1.20, 2.50
BRICK = 0.9
def rv_wall_run(tag, a1, a2, openings, make):
    """Solid wall from a1 to a2 along one axis with openings [(o1, o2, z0, z1)]:
    each span between breakpoints gets brick below and above its opening."""
    cuts = sorted({a1, a2, *[v for o in openings for v in o[:2]]})
    for k, (s1, s2) in enumerate(zip(cuts, cuts[1:])):
        o = next((o for o in openings if o[0] <= (s1 + s2) / 2 <= o[1]), None)
        for zk, (z0, z1) in enumerate(((0.0, RV_CZ),) if o is None else ((0.0, o[2]), (o[3], RV_CZ))):
            if z1 - z0 > 0.001:
                make(f"RvShell{tag}{k}_{zk}", s1, s2, z0, z1)
rv_wall_run("N", RV_X1, RV_B[0], [(w[0], w[1], WZ0, WZ1) for w in WIN_N] + [(*RV_DOOR_X, 0.0, RV_PORCH_Z)],
            lambda n, s1, s2, z0, z1: rv_box(n, s1, s2, RV_Y2 - RV_T, RV_Y2, z0, z1, M_RV_BRICK, BRICK))
rv_wall_run("E", RV_Y1, RV_A[1], [(w[0], w[1], WZ0, WZ1) for w in WIN_E],
            lambda n, s1, s2, z0, z1: rv_box(n, RV_X2 - RV_T, RV_X2, s1, s2, z0, z1, M_RV_BRICK, BRICK))
# West wall is the party wall with No.1: blind brick.
rv_box("RvShellW", RV_X1, RV_X1 + RV_T, RV_Y1, RV_Y2, 0.0, RV_CZ, M_RV_BRICK, BRICK)
rv_box("RvShellS", RV_X1, RV_X2, RV_Y1, RV_Y1 + RV_T, 0.0, RV_CZ, M_RV_BRICK, BRICK)
# Chamfer: local frame centred on the wall's centreline, local x from B to A,
# local +y outward (NE). One narrow etched window in it.
CH_YAW = math.radians(-45.0)
CH_HALF = math.hypot(RV_B[0] - RV_A[0], RV_B[1] - RV_A[1]) / 2
CH_C = ((RV_A[0] + RV_B[0]) / 2 - 0.15 / math.sqrt(2), (RV_A[1] + RV_B[1]) / 2 - 0.15 / math.sqrt(2))
CH_WIN = 0.30
for s, nm in ((-1, "L"), (1, "R")):
    lo, hi = sorted((s * CH_WIN, s * (CH_HALF + 0.12)))
    rv_rbox(f"RvShellC_{nm}", CH_C, CH_YAW, lo, hi, -0.15, 0.15, 0.0, RV_CZ, M_RV_BRICK, BRICK)
rv_rbox("RvShellC_lo", CH_C, CH_YAW, -CH_WIN, CH_WIN, -0.15, 0.15, 0.0, WZ0, M_RV_BRICK, BRICK)
rv_rbox("RvShellC_hi", CH_C, CH_YAW, -CH_WIN, CH_WIN, -0.15, 0.15, WZ1, RV_CZ, M_RV_BRICK, BRICK)

# Floor (carpet), boards behind the bar, ceiling, roof slab and deck.
rv_prism("RvShellFloor", RV_OUTER, 0.0, RV_FZ, M_RV_CARPET, 1.0)
# Bar: counter x 0.40..IX2 along y -14.30 (front) .. -14.85, a lifting-flap
# gap x -0.80..0.40 at its west end, and a short return x -1.30..-0.80 to the
# back wall closing the servers' side.
RV_BAR_Y = (-14.85, -14.30)
RV_FLAP_X = (-0.80, 0.40)
RV_RET_X = (-1.30, RV_FLAP_X[0])
rv_box("RvShellBoards", RV_FLAP_X[0], RV_IX2, RV_IY1, RV_BAR_Y[1], RV_FZ, RV_FZ + 0.006, M_RV_BOARDS, 1.0)
rv_poly("RvShellCeiling", RV_INNER, RV_CZ - 0.005, M_RV_CEIL, 0.6, down=True)
rv_prism("RvRoofSlab", RV_OUTER, RV_CZ, RV_SLAB, M_RV_BRICK, BRICK)
rv_prism("RvRoofDeck", RV_OUTER, RV_SLAB, RV_DECK, M_TEAK, 0.75)

# --- Front: Victorian pub frontage on the north and east faces + the corner ---
def rv_frontage(tag, a, b, holes, normal, sign_at=None, door=None):
    """Exterior dressing on a facade line a->b (a = viewer's left outside):
    green glazed stall riser, stone sills, cream surrounds, black fascia with
    the gilt name board, stone cornice. holes = window (s1, s2) along a->b;
    door = (s1, s2) the riser stops either side of."""
    L = math.hypot(b[0] - a[0], b[1] - a[1])
    dx, dy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
    nx, ny = normal
    def pt(s, off):
        return (a[0] + dx * s + nx * off, a[1] + dy * s + ny * off)
    def slab(name, s1, s2, off1, off2, z1, z2, mat, scale=None):
        c0 = pt((s1 + s2) / 2, (off1 + off2) / 2)
        yaw = math.atan2(dy, dx)
        rv_rbox(name, c0, yaw, -(s2 - s1) / 2, (s2 - s1) / 2, -(off2 - off1) / 2, (off2 - off1) / 2, z1, z2, mat, scale)
    for k, (r1, r2) in enumerate(((0, L),) if door is None else ((0, door[0]), (door[1], L))):
        slab(f"RvExt{tag}Riser{k}", r1, r2, 0.0, 0.03, RV_FZ, 0.75, M_RV_RISER, 0.6)
    slab(f"RvExt{tag}Fascia", 0, L, 0.0, 0.04, 2.62, 3.05, M_RV_BLACK)
    slab(f"RvExt{tag}Cornice", -0.04, L + 0.04, 0.0, 0.08, 3.05, RV_CZ, M_RV_STONE, 0.6)
    if sign_at is not None:
        s1, s2 = sign_at - 2.4, sign_at + 2.4
        rv_quad(f"RvExt{tag}Sign", pt(s1, 0.043), pt(s2, 0.043), 2.64, 3.03, M_RV_FASCIA)
    for k, (s1, s2) in enumerate(holes):
        slab(f"RvExt{tag}Sill{k}", s1 - 0.10, s2 + 0.10, -0.04, 0.06, WZ0 - 0.05, WZ0 + 0.02, M_RV_STONE, 0.6)
        slab(f"RvExt{tag}JambL{k}", s1 - 0.09, s1, 0.0, 0.04, WZ0, WZ1 + 0.09, M_RV_CREAM)
        slab(f"RvExt{tag}JambR{k}", s2, s2 + 0.09, 0.0, 0.04, WZ0, WZ1 + 0.09, M_RV_CREAM)
        slab(f"RvExt{tag}Head{k}", s1, s2, 0.0, 0.04, WZ1, WZ1 + 0.09, M_RV_CREAM)
        # Sash frame in the middle of the wall: etched lower lights, stained transom.
        mid = -RV_T / 2
        for nm, f1, f2, z1, z2 in (("FrL", s1, s1 + 0.05, WZ0, WZ1), ("FrR", s2 - 0.05, s2, WZ0, WZ1),
                                   ("FrB", s1, s2, WZ0, WZ0 + 0.05), ("FrT", s1, s2, WZ1 - 0.05, WZ1),
                                   ("FrM", (s1 + s2) / 2 - 0.03, (s1 + s2) / 2 + 0.03, WZ0, 2.13),
                                   ("FrX", s1, s2, 2.08, 2.15)):
            slab(f"RvExt{tag}{nm}{k}", f1, f2, mid - 0.04, mid + 0.04, z1, z2, M_RV_CREAM)
        cm = (s1 + s2) / 2
        rv_quad(f"RvExt{tag}EtchL{k}", pt(s1 + 0.05, mid), pt(cm - 0.03, mid), WZ0 + 0.05, 2.08, M_RV_ETCHED)
        rv_quad(f"RvExt{tag}EtchR{k}", pt(cm + 0.03, mid), pt(s2 - 0.05, mid), WZ0 + 0.05, 2.08, M_RV_ETCHED)
        rv_quad(f"RvExt{tag}Transom{k}", pt(s1 + 0.05, mid), pt(s2 - 0.05, mid), 2.15, WZ1 - 0.05, M_RV_STAINED)

# North face (Coronation St): viewed from the balcony (looking -y) the
# viewer's left is +x, so it runs from the corner B west to the party wall.
rv_frontage("N", RV_B, (RV_X1, RV_Y2), [(RV_B[0] - w[1], RV_B[0] - w[0]) for w in WIN_N], (0, 1),
            sign_at=RV_B[0] - 1.0, door=(RV_B[0] - RV_DOOR_X[1], RV_B[0] - RV_DOOR_X[0]))
# East face (Rosamund St): viewed looking -x the left is -y.
rv_frontage("E", (RV_X2, RV_Y1), RV_A, [(w[0] - RV_Y1, w[1] - RV_Y1) for w in WIN_E], (1, 0),
            sign_at=-13.55 - RV_Y1)
# Corner: riser, fascia with the Newton & Ridley board, cornice, and a narrow
# etched light in the middle of the wall.
def ch_pt(lx, off):  # lx along B->A, off outward from the outer face
    return local_pt(CH_C, CH_YAW, lx, 0.15 + off)
rv_rbox("RvExtCRiser", CH_C, CH_YAW, -CH_HALF, CH_HALF, 0.15, 0.18, RV_FZ, 0.75, M_RV_RISER, 0.6)
rv_rbox("RvExtCFascia", CH_C, CH_YAW, -CH_HALF, CH_HALF, 0.15, 0.19, 2.62, 3.05, M_RV_BLACK)
rv_rbox("RvExtCCornice", CH_C, CH_YAW, -CH_HALF - 0.06, CH_HALF + 0.06, 0.15, 0.23, 3.05, RV_CZ, M_RV_STONE, 0.6)
rv_quad("RvExtCNewton", ch_pt(CH_HALF - 0.07, 0.045), ch_pt(-CH_HALF + 0.07, 0.045), 2.65, 3.02, M_RV_NEWTON)
rv_rbox("RvExtCSill", CH_C, CH_YAW, -CH_WIN - 0.08, CH_WIN + 0.08, 0.11, 0.21, WZ0 - 0.05, WZ0 + 0.02, M_RV_STONE, 0.6)
for nm, l1, l2, z1, z2 in (("JambL", -CH_WIN - 0.07, -CH_WIN, WZ0, WZ1 + 0.07), ("JambR", CH_WIN, CH_WIN + 0.07, WZ0, WZ1 + 0.07),
                           ("Head", -CH_WIN, CH_WIN, WZ1, WZ1 + 0.07)):
    rv_rbox(f"RvExtC{nm}", CH_C, CH_YAW, l1, l2, 0.15, 0.19, z1, z2, M_RV_CREAM)
for nm, l1, l2, z1, z2 in (("FrB", -CH_WIN, CH_WIN, WZ0, WZ0 + 0.05), ("FrT", -CH_WIN, CH_WIN, WZ1 - 0.05, WZ1),
                           ("FrX", -CH_WIN, CH_WIN, 2.08, 2.15)):
    rv_rbox(f"RvExtC{nm}", CH_C, CH_YAW, l1, l2, -0.04, 0.04, z1, z2, M_RV_CREAM)
rv_quad("RvExtCEtch", local_pt(CH_C, CH_YAW, CH_WIN, 0.0), local_pt(CH_C, CH_YAW, -CH_WIN, 0.0), WZ0 + 0.05, 2.08, M_RV_ETCHED)
rv_quad("RvExtCTransom", local_pt(CH_C, CH_YAW, CH_WIN, 0.0), local_pt(CH_C, CH_YAW, -CH_WIN, 0.0), 2.15, WZ1 - 0.05, M_RV_STAINED)

# --- The front door: a recessed lobby in the flat front ----------------------
# The opening (x -1.30..0.0) goes through the wall; the lobby runs 0.9 m in
# from the face to the door line (y -10.70), boxed into the bar room by
# mahogany screens. Glazed green tiles to dado height and cream above line
# the reveals, York stone underfoot, licensee's board over the doors, and the
# two green leaves stand hooked back flat against the reveals.
PX1, PX2 = RV_DOOR_X
DOOR_Z = 2.40
for nm, x1, x2 in (("W", PX1 - 0.12, PX1), ("E", PX2, PX2 + 0.12)):
    rv_box(f"RvExtPorchScreen{nm}", x1, x2, RV_DOOR_Y - 0.12, RV_IY2, RV_FZ, RV_CZ - 0.005, M_RV_MAHOG)
rv_box("RvExtPorchHead", PX1, PX2, RV_DOOR_Y - 0.12, RV_DOOR_Y, DOOR_Z, RV_CZ - 0.005, M_RV_MAHOG)
rv_box("RvExtPorchSoffit", PX1, PX2, RV_DOOR_Y, RV_IY2, RV_PORCH_Z, RV_PORCH_Z + 0.03, M_RV_CREAM)
for nm, x1, x2 in (("W", PX1, PX1 + 0.01), ("E", PX2 - 0.01, PX2)):
    rv_box(f"RvExtPorchTile{nm}", x1, x2, RV_DOOR_Y, RV_Y2, RV_FZ, WZ0, M_RV_RISER, 0.6)
    rv_box(f"RvExtPorchCap{nm}", x1 - 0.005, x2 + 0.005, RV_DOOR_Y, RV_Y2, WZ0, WZ0 + 0.03, M_RV_STONE, 0.6)
    rv_box(f"RvExtPorchPlaster{nm}", x1, x2, RV_DOOR_Y, RV_Y2, WZ0 + 0.03, RV_PORCH_Z, M_RV_CREAM)
rv_box("RvExtPorchFloor", PX1, PX2, RV_DOOR_Y, RV_Y2, RV_FZ, RV_FZ + 0.006, M_RV_STONE, 0.6)
for nm, x1, x2 in (("W", PX1 + 0.01, PX1 + 0.04), ("E", PX2 - 0.04, PX2 - 0.01)):
    rv_box(f"RvExtPorchJamb{nm}", x1, x2, RV_DOOR_Y - 0.06, RV_DOOR_Y, RV_FZ, DOOR_Z, M_RV_CREAM)
rv_box("RvExtPorchDoorHead", PX1 + 0.01, PX2 - 0.01, RV_DOOR_Y - 0.06, RV_DOOR_Y, DOOR_Z - 0.05, DOOR_Z, M_RV_CREAM)
rv_quad("RvExtPorchLicensee", (PX2 - 0.15, RV_DOOR_Y + 0.005), (PX1 + 0.15, RV_DOOR_Y + 0.005),
        DOOR_Z + 0.015, DOOR_Z + 0.14, M_RV_LICENSEE)
# Leaves (0.62 m) hinged at the door line, folded flat onto the reveals.
LEAF = 0.62
for nm, x1, x2, gx in (("W", PX1 + 0.01, PX1 + 0.05, PX1 + 0.052), ("E", PX2 - 0.05, PX2 - 0.01, PX2 - 0.052)):
    rv_box(f"RvExtPorchLeaf{nm}", x1, x2, RV_DOOR_Y + 0.02, RV_DOOR_Y + 0.02 + LEAF, RV_FZ + 0.01, DOOR_Z - 0.06, M_RV_GREEN)
    g1, g2 = (RV_DOOR_Y + 0.10, RV_DOOR_Y + LEAF - 0.06)
    rv_quad(f"RvExtPorchLeafGlass{nm}", (gx, g1) if nm == "W" else (gx, g2), (gx, g2) if nm == "W" else (gx, g1),
            1.20, 2.10, M_RV_ETCHED)
    px = (x2, x2 + 0.006) if nm == "W" else (x1 - 0.006, x1)
    rv_box(f"RvExtPorchPlate{nm}", px[0], px[1], RV_DOOR_Y + LEAF - 0.06, RV_DOOR_Y + LEAF - 0.01, 1.00, 1.25, M_RV_BRASS)
# Brass coach lamps either side of the lobby.
for nm, lx in (("W", PX1 - 0.30), ("E", PX2 + 0.30)):
    ly = RV_Y2 + 0.07
    add_box(f"RvExtLampBracket{nm}", lx, ly, 2.38, 0.02, 0.02, 0.02, M_RV_IRON)
    add_box(f"RvExtLampCap{nm}", lx, ly, 2.53, 0.08, 0.08, 0.02, M_RV_IRON)
    add_box(f"RvGlowLamp{nm}", lx, ly, 2.40, 0.065, 0.065, 0.11, M_RV_GLOBE)

# --- Interior walls: mahogany dado to 1.20, oxblood damask above -------------
# North wall inside (viewer faces +y, left = -x): windows, and the lobby
# screens' full-height gap.
na, nb = (RV_IX1, RV_IY2 - 0.005), (RV_INNER[3][0], RV_IY2 - 0.005)
_porch_hole = (PX1 - 0.12 - na[0], PX2 + 0.12 - na[0], RV_FZ, RV_CZ)
rv_band("RvShellDadoN", na, nb, RV_FZ, WZ0, [_porch_hole], M_RV_PANEL, 1.2, 1.1)
rv_band("RvShellPaperN", na, nb, WZ0, RV_CZ - 0.005,
        [(w[0] - na[0], w[1] - na[0], WZ0, WZ1) for w in WIN_N] + [(_porch_hole[0], _porch_hole[1], WZ0, RV_CZ)],
        M_RV_DAMASK, 0.64, 0.64)
# Corner inside (viewer faces NE, left = the north end).
_ci = 0.005 / math.sqrt(2)
ca_, cb_ = (RV_INNER[3][0] - _ci, RV_IY2 - _ci), (RV_IX2 - _ci, RV_INNER[2][1] - _ci)
_cl = math.hypot(cb_[0] - ca_[0], cb_[1] - ca_[1])
rv_band("RvShellDadoC", ca_, cb_, RV_FZ, WZ0, [], M_RV_PANEL, 1.2, 1.1)
rv_band("RvShellPaperC", ca_, cb_, WZ0, RV_CZ - 0.005, [(_cl / 2 - CH_WIN, _cl / 2 + CH_WIN, WZ0, WZ1)], M_RV_DAMASK, 0.64, 0.64)
# East wall inside (viewer faces +x, left = +y): the Rosamund Street windows.
ea, eb = (RV_IX2 - 0.005, RV_INNER[2][1]), (RV_IX2 - 0.005, RV_IY1)
rv_band("RvShellDadoE", ea, eb, RV_FZ, WZ0, [], M_RV_PANEL, 1.2, 1.1)
rv_band("RvShellPaperE", ea, eb, WZ0, RV_CZ - 0.005, [(ea[1] - w[1], ea[1] - w[0], WZ0, WZ1) for w in WIN_E],
        M_RV_DAMASK, 0.64, 0.64)
# West (party) wall inside (viewer faces -x, left = -y): Gents and Ladies.
RV_DOORS_W = ((-12.15, -11.35, "Gents"), (-13.35, -12.55, "Ladies"))
wa, wb = (RV_IX1 + 0.005, RV_IY1), (RV_IX1 + 0.005, RV_IY2)
_w_holes = [(d[0] - wa[1], d[1] - wa[1]) for d in RV_DOORS_W]
rv_band("RvShellDadoW", wa, wb, RV_FZ, WZ0, [(h[0], h[1], RV_FZ, WZ0) for h in _w_holes], M_RV_PANEL, 1.2, 1.1)
rv_band("RvShellPaperW", wa, wb, WZ0, RV_CZ - 0.005, [(h[0], h[1], WZ0, 2.20) for h in _w_holes], M_RV_DAMASK, 0.64, 0.64)
# South wall inside (viewer faces -y, left = +x): the private door to the back
# room, behind the bar.
sa, sb = (RV_IX2, RV_IY1 + 0.005), (RV_IX1, RV_IY1 + 0.005)
RV_DOORS_S = ((4.60, 5.45, "Private"),)
_s_holes = [(RV_IX2 - d[1], RV_IX2 - d[0], RV_FZ, 2.20) for d in RV_DOORS_S]
rv_band("RvShellDadoS", sa, sb, RV_FZ, WZ0, [(h[0], h[1], RV_FZ, WZ0) for h in _s_holes], M_RV_PANEL, 1.2, 1.1)
rv_band("RvShellPaperS", sa, sb, WZ0, RV_CZ - 0.005, [(h[0], h[1], WZ0, 2.20) for h in _s_holes], M_RV_DAMASK, 0.64, 0.64)
# Dado cap, picture rail and cornice all round (thin boxes, 2.5 cm proud);
# the north runs stop at the lobby screens.
_runs = (("NW", RV_IX1, PX1 - 0.12, RV_IY2 - 0.025, RV_IY2), ("NE", PX2 + 0.12, RV_INNER[3][0], RV_IY2 - 0.025, RV_IY2),
         ("S", RV_IX1, RV_IX2, RV_IY1, RV_IY1 + 0.025), ("W", RV_IX1, RV_IX1 + 0.025, RV_IY1, RV_IY2),
         ("E", RV_IX2 - 0.025, RV_IX2, RV_IY1, RV_INNER[2][1]))
for nm, x1, x2, y1, y2 in _runs:
    rv_box(f"RvShellDadoCap{nm}", x1, x2, y1, y2, WZ0 - 0.02, WZ0 + 0.03, M_RV_MAHOG)
    rv_box(f"RvShellPictureRail{nm}", x1, x2, y1, y2, 2.62, 2.66, M_RV_MAHOG)
    rv_box(f"RvShellCornice{nm}", x1, x2, y1, y2, RV_CZ - 0.10, RV_CZ - 0.005, M_RV_CREAM)
for nm, z1, z2, mat in (("DadoCap", WZ0 - 0.02, WZ0 + 0.03, M_RV_MAHOG), ("PictureRail", 2.62, 2.66, M_RV_MAHOG),
                        ("Cornice", RV_CZ - 0.10, RV_CZ - 0.005, M_RV_CREAM)):
    _cc = local_pt(CH_C, CH_YAW, 0.0, -0.15 - 0.0125)
    rv_rbox(f"RvShell{nm}C", _cc, CH_YAW, -_cl / 2, _cl / 2, -0.0125, 0.0125, z1, z2, mat)
# Window stools inside (mahogany inner sills).
for k, (x1, x2) in enumerate(WIN_N):
    rv_box(f"RvShellStoolN{k}", x1 - 0.05, x2 + 0.05, RV_IY2 - 0.06, RV_Y2 - RV_T / 2 - 0.04, WZ0, WZ0 + 0.04, M_RV_MAHOG)
for k, (y1, y2) in enumerate(WIN_E):
    rv_box(f"RvShellStoolE{k}", RV_IX2 - 0.06, RV_X2 - RV_T / 2 + 0.04, y1 - 0.05, y2 + 0.05, WZ0, WZ0 + 0.04, M_RV_MAHOG)
# Closed doors: panelled mahogany in cream architraves, brass knobs.
for x1, x2, tag in RV_DOORS_S:
    rv_quad(f"RvShellDoor{tag}", (x2, RV_IY1 + 0.012), (x1, RV_IY1 + 0.012), RV_FZ, 2.20, M_RV_PANEL, 0.85, 1.05)
    rv_box(f"RvShellDoorArchL{tag}", x1 - 0.07, x1, RV_IY1, RV_IY1 + 0.04, RV_FZ, 2.27, M_RV_CREAM)
    rv_box(f"RvShellDoorArchR{tag}", x2, x2 + 0.07, RV_IY1, RV_IY1 + 0.04, RV_FZ, 2.27, M_RV_CREAM)
    rv_box(f"RvShellDoorArchT{tag}", x1 - 0.07, x2 + 0.07, RV_IY1, RV_IY1 + 0.04, 2.20, 2.27, M_RV_CREAM)
    rv_cyl(f"RvBarKnob{tag}", x1 + 0.08, RV_IY1 + 0.05, 1.02, 0.03, 0.06, M_RV_BRASS, verts=8, rot=(math.pi / 2, 0, 0))
for y1, y2, tag in RV_DOORS_W:
    rv_quad(f"RvShellDoor{tag}", (RV_IX1 + 0.012, y1), (RV_IX1 + 0.012, y2), RV_FZ, 2.20, M_RV_PANEL, 0.85, 1.05)
    rv_box(f"RvShellDoorArchL{tag}", RV_IX1, RV_IX1 + 0.04, y1 - 0.07, y1, RV_FZ, 2.27, M_RV_CREAM)
    rv_box(f"RvShellDoorArchR{tag}", RV_IX1, RV_IX1 + 0.04, y2, y2 + 0.07, RV_FZ, 2.27, M_RV_CREAM)
    rv_box(f"RvShellDoorArchT{tag}", RV_IX1, RV_IX1 + 0.04, y1 - 0.07, y2 + 0.07, 2.20, 2.27, M_RV_CREAM)
    rv_cyl(f"RvBarKnob{tag}", RV_IX1 + 0.05, y2 - 0.08, 1.02, 0.03, 0.06, M_RV_BRASS, verts=8, rot=(0, math.pi / 2, 0))
    rv_box(f"RvBarDoorPlate{tag}", RV_IX1 + 0.012, RV_IX1 + 0.02, (y1 + y2) / 2 - 0.16, (y1 + y2) / 2 + 0.16, 1.62, 1.72, M_RV_BRASS)

# --- The bar: across the back of the room, the public space an L around it --
BY1, BY2 = RV_BAR_Y
BX1, BX2 = RV_FLAP_X[1], RV_IX2
rv_box("RvBarBody", BX1, BX2, BY1, BY2, RV_FZ, 1.00, M_RV_MAHOG)
rv_quad("RvBarFront", (BX2, BY2 + 0.005), (BX1, BY2 + 0.005), RV_FZ, 1.00, M_RV_PANEL, 1.2, 1.1)
rv_box("RvBarTop", BX1, BX2, BY1 - 0.08, BY2 + 0.08, 1.00, 1.06, M_RV_MAHOG)
# Return to the back wall, panelled on the public (west) side.
RX1, RX2 = RV_RET_X
rv_box("RvBarReturn", RX1, RX2, RV_IY1, BY2, RV_FZ, 1.00, M_RV_MAHOG)
rv_quad("RvBarReturnFront", (RX1 - 0.005, BY2), (RX1 - 0.005, RV_IY1), RV_FZ, 1.00, M_RV_PANEL, 1.2, 1.1)
rv_box("RvBarReturnTop", RX1 - 0.08, RX2, RV_IY1, BY2 + 0.08, 1.00, 1.06, M_RV_MAHOG)
# The flap: hinged at the counter's end, lifted and standing up so the gap is
# open; a brass hook post on the return side.
rv_box("RvBarFlap", BX1 - 0.03, BX1, BY1 - 0.08, BY2 + 0.08, 1.06, 1.06 + (BX1 - RX2) * 0.5, M_RV_MAHOG)
rv_cyl("RvBarFlapHook", RX2 - 0.04, BY2 - 0.10, 1.12, 0.012, 0.12, M_RV_BRASS, verts=6)
# Brass foot rail along the public face.
rv_cyl("RvBarFootRail", (BX1 + BX2) / 2, BY2 + 0.14, 0.24, 0.025, BX2 - BX1, M_RV_BRASS, verts=8, rot=(0, math.pi / 2, 0))
for k, x in enumerate((BX1 + 0.3, (BX1 + BX2) / 2, BX2 - 0.3)):
    add_box(f"RvBarRailFoot{k}", x, BY2 + 0.07, 0.24, 0.012, 0.07, 0.012, M_RV_BRASS)
# Handpumps on the servers' edge, a drip tray in front of them.
# The fourth pump's handle (x 3.15) belongs to the barman rig (rovers_figures.py): it moves.
for k, x in enumerate((1.80, 2.25, 2.70, 3.15, 3.60)):
    add_box(f"RvBarPumpBody{k}", x, -14.66, 1.10, 0.035, 0.035, 0.04, M_RV_BRASS)
    if k == 3:
        continue
    rv_cyl(f"RvBarPumpHandle{k}", x, -14.66, 1.30, 0.022, 0.32, M_RV_BLACK, verts=8)
    rv_cyl(f"RvBarPumpKnob{k}", x, -14.66, 1.47, 0.03, 0.03, M_RV_BRASS, verts=8)
add_box("RvBarDripTray", 2.70, -14.52, 1.065, 0.98, 0.05, 0.006, M_RV_BRASS)
# A few pints on the bar, the tables and the drinking shelf.
# (The regulars in rovers_figures.py carry their own glasses, so the static
# pints by their stools, their table and the drinking shelf are gone.)
# (The reserved window table, TABLES_A[1], gets its red wine and pint from the
# barmaid in rovers_figures.py, so its static pint is gone too.)
RV_PINTS = [(5.20, -14.45, 1.06), (5.40, -12.05, RV_FZ + 0.75)]
for k, (x, y, z0) in enumerate(RV_PINTS):
    rv_cyl(f"RvBarPint{k}", x, y, z0 + 0.065, 0.038, 0.13, M_RV_ALE, verts=10)
    rv_cyl(f"RvBarFroth{k}", x, y, z0 + 0.14, 0.040, 0.02, M_RV_FROTH, verts=10)
# Back counter and the flat back bar (mirrors, shelves, optics) on the back wall.
BB1, BB2 = 0.0, 4.45
rv_box("RvBarBackCounter", BB1, BB2, RV_IY1, RV_IY1 + 0.45, RV_FZ, 0.95, M_RV_MAHOG)
rv_box("RvBarBackTop", BB1 - 0.03, BB2 + 0.03, RV_IY1, RV_IY1 + 0.48, 0.95, 0.99, M_RV_MAHOG)
rv_quad("RvBarBackBar", (BB2, RV_IY1 + 0.012), (BB1, RV_IY1 + 0.012), 1.02, 3.02, M_RV_BACKBAR)
rv_box("RvBarBackFrame", BB1 - 0.06, BB2 + 0.06, RV_IY1 + 0.006, RV_IY1 + 0.04, 3.02, 3.08, M_RV_MAHOG)
# Cellar trapdoor in the boards behind the bar: brass-edged, ring pull.
rv_box("RvBarTrapFrame", 2.20, 3.00, -15.95, -15.25, RV_FZ + 0.006, RV_FZ + 0.010, M_RV_BRASS)
rv_box("RvBarTrapLid", 2.24, 2.96, -15.91, -15.29, RV_FZ + 0.006, RV_FZ + 0.012, M_RV_MAHOG)
rv_cyl("RvBarTrapRing", 2.60, -15.36, RV_FZ + 0.014, 0.045, 0.004, M_RV_BRASS, verts=10)
# Bar lamps: two brass pendants over the counter.
for k, x in enumerate((1.80, 4.60)):
    rv_cyl(f"RvBarLampRod{k}", x, -14.57, (RV_CZ + 2.78) / 2, 0.008, RV_CZ - 2.78, M_RV_BRASS, verts=6)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=12, ring_count=6, radius=0.11, location=(x, -14.57, 2.70))
    bpy.context.active_object.name = f"RvGlowBar{k}"
    bpy.context.active_object.data.materials.append(M_RV_GLOBE)

# --- Seating: buttoned velour banquettes, cast-iron tables, stools ----------
def rv_banquette(tag, x1, x2, y1, y2, axis, back_side, n):
    """Bench along a wall. axis 'x' runs along x (back at y back_side), 'y'
    along y (back at x back_side). Cushions get 5 cm gaps for seat snapping."""
    rv_box(f"RvFurn{tag}Base", x1, x2, y1, y2, RV_FZ, 0.43, M_RV_MAHOG)
    centres = []
    if axis == 'x':
        L = x2 - x1
        cw = (L - 0.05 * (n - 1)) / n
        for k in range(n):
            cx1 = x1 + k * (cw + 0.05)
            rv_box(f"RvFurn{tag}Cush{k}", cx1, cx1 + cw, y1 + 0.02, y2 - 0.04, 0.43, 0.55, M_RV_VELOUR, 0.4)
            centres.append((cx1 + cw / 2, (y1 + y2) / 2))
        by = (back_side - 0.14, back_side) if back_side > (y1 + y2) / 2 else (back_side, back_side + 0.14)
        rv_box(f"RvFurn{tag}Back", x1, x2, by[0], by[1], 0.55, 1.15, M_RV_VELOUR, 0.4)
    else:
        L = y2 - y1
        cw = (L - 0.05 * (n - 1)) / n
        for k in range(n):
            cy1 = y1 + k * (cw + 0.05)
            rv_box(f"RvFurn{tag}Cush{k}", x1 + 0.04, x2 - 0.02, cy1, cy1 + cw, 0.43, 0.55, M_RV_VELOUR, 0.4)
            centres.append(((x1 + x2) / 2, cy1 + cw / 2))
        bx = (back_side, back_side + 0.14) if back_side < (x1 + x2) / 2 else (back_side - 0.14, back_side)
        rv_box(f"RvFurn{tag}Back", bx[0], bx[1], y1, y2, 0.55, 1.15, M_RV_VELOUR, 0.4)
    return centres

# Alcoves under the front windows: two booths, high mahogany ends with
# etched glass over, east of the lobby. Then the old snug corner along the
# Rosamund Street side, and stools along the bar.
BANQ_A = rv_banquette("BanqA", 0.30, 2.70, RV_IY2 - 0.52, RV_IY2, 'x', RV_IY2, 2)
BANQ_B = rv_banquette("BanqB", 2.95, 5.35, RV_IY2 - 0.52, RV_IY2, 'x', RV_IY2, 2)
for k, (x1, x2) in enumerate(((2.79, 2.86), (5.37, 5.44))):
    rv_box(f"RvFurnBooth{k}End", x1, x2, -11.45, RV_IY2, RV_FZ, 1.15, M_RV_MAHOG)
    rv_quad(f"RvFurnBooth{k}Glass", ((x1 + x2) / 2, -11.40), ((x1 + x2) / 2, RV_IY2 - 0.05), 1.15, 1.60, M_RV_ETCHED)
    rv_box(f"RvFurnBooth{k}Post", x1, x2, -11.45, -11.38, 1.15, 1.60, M_RV_MAHOG)
    rv_box(f"RvFurnBooth{k}Cap", x1 - 0.01, x2 + 0.01, -11.46, RV_IY2, 1.60, 1.64, M_RV_MAHOG)
# Four places: the dinner party sits here after dinner (dinner_figures SNUG_Y).
BANQ_E = rv_banquette("BanqE", RV_IX2 - 0.52, RV_IX2, -13.95, -11.10, 'y', RV_IX2, 4)
def rv_table(tag, x, y):
    rv_cyl(f"RvFurnTable{tag}Top", x, y, RV_FZ + 0.735, 0.34, 0.03, M_RV_COPPER, verts=16)
    rv_cyl(f"RvFurnTable{tag}Stem", x, y, RV_FZ + 0.37, 0.04, 0.70, M_RV_IRON, verts=8)
    rv_cyl(f"RvFurnTable{tag}Foot", x, y, RV_FZ + 0.02, 0.22, 0.04, M_RV_IRON, verts=12)
def rv_stool(tag, x, y, h, r=0.17):
    rv_cyl(f"RvFurnStool{tag}Seat", x, y, RV_FZ + h - 0.03, r, 0.06, M_RV_VELOUR, verts=12)
    rv_cyl(f"RvFurnStool{tag}Leg", x, y, RV_FZ + (h - 0.06) / 2, 0.03, h - 0.06, M_RV_MAHOG, verts=6)
    rv_cyl(f"RvFurnStool{tag}Ring", x, y, RV_FZ + 0.25, r * 0.8, 0.02, M_RV_BRASS, verts=10)
    rv_cyl(f"RvFurnStool{tag}Foot", x, y, RV_FZ + 0.015, r * 0.9, 0.03, M_RV_MAHOG, verts=10)
TABLES_A = [(1.50, -11.05), (4.15, -11.05)]
TABLES_E = [(5.35, -12.05), (5.35, -13.25)]       # dinner_figures SNUG_TABLE / STOOL_X
for k, (x, y) in enumerate(TABLES_A):
    rv_table(f"A{k}", x, y)
    rv_stool(f"A{k}", x, -11.78, 0.46)
for k, (x, y) in enumerate(TABLES_E):
    rv_table(f"E{k}", x, y)
    rv_stool(f"E{k}", 4.65, y, 0.46)
BAR_STOOLS = [(x, -13.92) for x in (1.0, 1.9, 2.8, 3.7, 4.6)]
# The end stool by the flap (k 0) is gone: that end of the bar is the barmaid's
# station in rovers_figures.py (tray, wine bottles, her glasses). So is the
# last one (k 4): that is where the dinner party's waiters stand, with their
# trays and bottles on the bar (dinner_figures PUB_STN).
for k, (x, y) in enumerate(BAR_STOOLS):
    if k in (0, 4):
        continue
    rv_stool(f"B{k}", x, y, 0.75, r=0.18)
# Drinking shelf under the window west of the lobby (the stand-up end).
rv_box("RvFurnShelf", -3.55, PX1 - 0.30, RV_IY2 - 0.28, RV_IY2, 1.05, 1.09, M_RV_MAHOG)
for k, x in enumerate((-3.35, -1.85)):
    rv_box(f"RvFurnShelfBracket{k}", x - 0.02, x + 0.02, RV_IY2 - 0.24, RV_IY2, 0.85, 1.05, M_RV_IRON)

# --- Darts at the rear of the right-hand wall, piano, boards, pendants -------
# Moved 0.45 m east of the piano stool so the throwing lane clears the pianist
# (rovers_figures.py DART_X must match).
DART_X = -1.85
rv_box("RvFurnDartCabinet", DART_X - 0.45, DART_X + 0.45, RV_IY1, RV_IY1 + 0.05, 1.35, 2.25, M_RV_MAHOG)
rv_quad("RvFurnDartboard", (DART_X + 0.27, RV_IY1 + 0.056), (DART_X - 0.27, RV_IY1 + 0.056), 1.53, 2.07, M_RV_DART)
add_box("RvFurnOche", DART_X, RV_IY1 + 2.37, RV_FZ + 0.003, 0.30, 0.02, 0.003, M_RV_BRASS)
# Chalk scoreboard west of the cabinet: the darts players chalk their scores
# on it and the last scorer wipes it (rovers_figures.py SCORE_*).
M_RV_CHALK = mk('RoversChalkboard', '1e2422', 0.92)
rv_box("RvFurnScoreFrame", -2.99, -2.41, RV_IY1, RV_IY1 + 0.02, 1.27, 2.01, M_RV_MAHOG)
rv_box("RvFurnScoreBoard", -2.96, -2.44, RV_IY1 + 0.004, RV_IY1 + 0.023, 1.30, 1.98, M_RV_CHALK)
# Upright piano against the party wall, keys facing the room, its stool.
PNO_Y = (-16.25, -14.75)
rv_box("RvFurnPianoCase", RV_IX1, RV_IX1 + 0.58, PNO_Y[0], PNO_Y[1], RV_FZ, 1.35, M_RV_MAHOG)
rv_box("RvFurnPianoKeyBed", RV_IX1 + 0.58, RV_IX1 + 0.80, PNO_Y[0] + 0.08, PNO_Y[1] - 0.08, 0.72, 0.78, M_RV_MAHOG)
rv_box("RvFurnPianoKeys", RV_IX1 + 0.62, RV_IX1 + 0.78, PNO_Y[0] + 0.12, PNO_Y[1] - 0.12, 0.78, 0.80, M_RV_FROTH)
rv_box("RvFurnPianoStool", RV_IX1 + 1.00, RV_IX1 + 1.30, -15.85, -15.15, RV_FZ, 0.58, M_RV_MAHOG)
rv_box("RvFurnPianoStoolTop", RV_IX1 + 1.00, RV_IX1 + 1.30, -15.85, -15.15, 0.58, 0.62, M_RV_VELOUR, 0.4)
rv_quad("RvFurnPoster", (RV_IX1 + 0.012, -15.78), (RV_IX1 + 0.012, -15.12), 1.55, 2.45, M_RV_POSTER)
rv_box("RvFurnPosterFrame", RV_IX1, RV_IX1 + 0.01, -15.82, -15.08, 1.51, 2.49, M_RV_MAHOG)
# Betty's Hotpot on the board behind the bar, east of the private door.
rv_quad("RvFurnHotpot", (6.25, RV_IY1 + 0.012), (5.65, RV_IY1 + 0.012), 1.38, 2.13, M_RV_HOTPOT)
for k, (x, y) in enumerate(((-2.30, -12.40), (1.50, -12.60), (4.20, -12.60), (-2.30, -15.20))):
    rv_cyl(f"RvBarLampRodHall{k}", x, y, (RV_CZ + 2.86) / 2, 0.008, RV_CZ - 2.86, M_RV_BRASS, verts=6)
    rv_cyl(f"RvBarLampGallery{k}", x, y, 2.88, 0.07, 0.04, M_RV_BRASS, verts=10)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=12, ring_count=6, radius=0.13, location=(x, y, 2.76))
    bpy.context.active_object.name = f"RvGlowHall{k}"
    bpy.context.active_object.data.materials.append(M_RV_GLOBE)

# --- Roof terrace: brick parapet with stone coping, door from the sky den ---
PAR_Z1, PAR_Z2, PAR_T = RV_SLAB, 4.55, 0.25
rv_box("RvRoofParS", RV_X1, RV_X2, RV_Y1, RV_Y1 + PAR_T, PAR_Z1, PAR_Z2, M_RV_BRICK, BRICK)
rv_box("RvRoofParE", RV_X2 - PAR_T, RV_X2, RV_Y1, RV_A[1], PAR_Z1, PAR_Z2, M_RV_BRICK, BRICK)
rv_box("RvRoofParW", RV_X1, RV_X1 + PAR_T, RV_Y1, RV_Y2, PAR_Z1, PAR_Z2, M_RV_BRICK, BRICK)
# North runs stop at the sky den (x -0.78..3.85), whose glass is the edge there.
rv_box("RvRoofParNW", RV_X1, -0.78, RV_Y2 - PAR_T, RV_Y2 - 0.10, PAR_Z1, PAR_Z2, M_RV_BRICK, BRICK)
rv_box("RvRoofParNE", 3.85, RV_B[0], RV_Y2 - PAR_T, RV_Y2 - 0.10, PAR_Z1, PAR_Z2, M_RV_BRICK, BRICK)
rv_rbox("RvRoofParC", CH_C, CH_YAW, -CH_HALF - 0.12, CH_HALF + 0.12, -0.10, 0.15, PAR_Z1, PAR_Z2, M_RV_BRICK, BRICK)
for nm, x1, x2, y1, y2 in (("S", RV_X1, RV_X2, RV_Y1, RV_Y1 + PAR_T), ("E", RV_X2 - PAR_T, RV_X2, RV_Y1, RV_A[1]),
                           ("W", RV_X1, RV_X1 + PAR_T, RV_Y1, RV_Y2), ("NW", RV_X1, -0.78, RV_Y2 - PAR_T, RV_Y2 - 0.10),
                           ("NE", 3.85, RV_B[0], RV_Y2 - PAR_T, RV_Y2 - 0.10)):
    rv_box(f"RvRoofCoping{nm}", x1 - 0.03, x2 + 0.03, y1 - 0.03, y2 + 0.03, PAR_Z2, PAR_Z2 + 0.06, M_RV_STONE, 0.6)
rv_rbox("RvRoofCopingC", CH_C, CH_YAW, -CH_HALF - 0.12, CH_HALF + 0.12, -0.13, 0.18, PAR_Z2, PAR_Z2 + 0.06, M_RV_STONE, 0.6)
# Two teak armchairs and a table looking out south-west, planters at the corners.
RV_ROOF_CHAIRS = [(-1.20, -15.20), (0.20, -15.20)]
for k, (x, y) in enumerate(RV_ROOF_CHAIRS):
    rv_box(f"RvRoofChair{k}Frame", x - 0.33, x + 0.33, y - 0.33, y + 0.33, RV_DECK, RV_DECK + 0.30, M_TEAK, 0.5)
    rv_box(f"RvRoofChair{k}Cush", x - 0.28, x + 0.28, y - 0.25, y + 0.30, RV_DECK + 0.30, RV_DECK + 0.42, M_CUSH)
    rv_box(f"RvRoofChair{k}Back", x - 0.33, x + 0.33, y + 0.30, y + 0.40, RV_DECK + 0.30, RV_DECK + 0.85, M_TEAK, 0.5)
    for s, nm in ((-1, "L"), (1, "R")):
        rv_box(f"RvRoofChair{k}Arm{nm}", x + s * 0.33 - 0.04, x + s * 0.33 + 0.04, y - 0.33, y + 0.40, RV_DECK + 0.30, RV_DECK + 0.62, M_TEAK, 0.5)
rv_cyl("RvRoofTable", -0.50, -14.55, RV_DECK + 0.45, 0.28, 0.03, M_TEAK, verts=14)
rv_cyl("RvRoofTableStem", -0.50, -14.55, RV_DECK + 0.22, 0.03, 0.44, M_RAIL, verts=6)
for k, (x, y) in enumerate(((RV_X1 + 0.65, RV_Y1 + 0.65), (RV_X2 - 0.65, RV_Y1 + 0.65), (RV_X1 + 0.65, RV_Y2 - 0.75))):
    rv_box(f"RvRoofPlanter{k}", x - 0.30, x + 0.30, y - 0.30, y + 0.30, RV_DECK, RV_DECK + 0.48, M_TRAV, 1.3)
    plant(f"RvPlantRoof{k}", x, y, RV_DECK + 0.48, 1.0, 0.8 * k)

# Sky den -> roof: a door through the den's south wall east of the sofa
# (x 2.98..3.80: glass, curtain stack, pier and outer render all go). The
# planter that stood there moves 1.16 m north, clear of the door and the art.
DEN_DOOR = (3.02, 3.80)
cut_opening(DEN_DOOR[0], DEN_DOOR[1], -9.95, -9.40, DEN_Z + 0.02, DEN_Z + 2.21, "den-roof-door")
for nm in ("LedgeE1", "DenPlanterPot", "DenPlanterSoil"):
    bpy.data.objects[nm].location.y += 1.16      # (3.40, -9.36) -> (3.40, -8.20)
for nm, x1, x2 in (("L", DEN_DOOR[0] - 0.06, DEN_DOOR[0]), ("R", DEN_DOOR[1], DEN_DOOR[1] + 0.05)):
    rv_box(f"RvDenDoorJamb{nm}", x1, x2, -9.92, -9.42, DEN_Z, DEN_Z + 2.27, M_RV_CREAM)
rv_box("RvDenDoorHead", DEN_DOOR[0] - 0.06, DEN_DOOR[1] + 0.05, -9.92, -9.42, DEN_Z + 2.21, DEN_Z + 2.27, M_RV_CREAM)
rv_box("RvDenDoorSill", DEN_DOOR[0], DEN_DOOR[1], -9.92, -9.42, DEN_Z, RV_DECK, M_TEAK, 0.75)
# Glazed leaf swung out and parked against the den's outside glass, west of
# the opening (inside, the sofa runs right up to the jamb).
rv_box("RvDenDoorLeaf", DEN_DOOR[0] - 0.84, DEN_DOOR[0] - 0.06, -9.97, -9.93, RV_DECK, DEN_Z + 2.18, M_RV_CREAM)
if M_GLASSP:
    rv_box("RvDenDoorLeafGlass", DEN_DOOR[0] - 0.78, DEN_DOOR[0] - 0.12, -9.98, -9.92, RV_DECK + 0.12, DEN_Z + 2.10, M_GLASSP)

join_objects("RoversShell", ("RvShell",))
join_objects("RoversFront", ("RvExt",))
join_objects("RoversBar", ("RvBar",))
join_objects("RoversFurniture", ("RvFurn",))
join_objects("RoversGlow", ("RvGlow",))
join_objects("RoversRoof", ("RvRoof", "RvDenDoor"))
join_objects("RoversRails", ("RvRail",))

# --- The old BBQ patio becomes a rooftop cocktail lounge, with a French door
# from the dining room (build-cocktail.py; dinner_figures.py COCKTAIL_*).
exec(compile(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "build-cocktail.py")).read(),
             "build-cocktail.py", "exec"))

# Seat waypoints (name, x, y, seat z, yaw: 0=-y 90=+x 180=+y -90=-x).
RV_SEATS = (
    [(f"Seat_RovA{k + 1}", x, y, 0.55, 0) for k, (x, y) in enumerate(BANQ_A + BANQ_B)] +
    [(f"Seat_RovSnug{k + 1}", x - 0.02, y, 0.55, -90) for k, (x, y) in enumerate(BANQ_E)] +
    [(f"Seat_RovBar{k + 1}", x, y, RV_FZ + 0.75, 0) for k, (x, y) in enumerate(BAR_STOOLS)] +
    [(f"Seat_RovTA{k + 1}", x, -11.78, RV_FZ + 0.46, 180) for k, (x, y) in enumerate(TABLES_A)] +
    [(f"Seat_RovTE{k + 1}", 4.65, y, RV_FZ + 0.46, 90) for k, (x, y) in enumerate(TABLES_E)] +
    [(f"Seat_RovRoof{k + 1}", x, y - 0.02, RV_DECK + 0.42, 0) for k, (x, y) in enumerate(RV_ROOF_CHAIRS)])
# Taken by the animated regulars (rovers_figures.py): three bar stools, the
# first booth cushion and the stool opposite it.
RV_TAKEN = {"Seat_RovBar1", "Seat_RovBar2", "Seat_RovBar3", "Seat_RovBar4", "Seat_RovA1", "Seat_RovTA1",
            "Seat_RovBar5"}
# After dinner the snug is the dinner party's (dinner_figures.py PUB_SEAT).
RV_TAKEN |= {f"Seat_RovSnug{k + 1}" for k in range(4)} | {"Seat_RovTE1", "Seat_RovTE2"}
RV_SEATS = tuple(s for s in RV_SEATS if s[0] not in RV_TAKEN)

# --- Seats: authored spots, snapped onto the real seat surfaces --------------
# name, x, y, expected seat-surface z, yaw_deg
# yaw: avatar facing after glTF export (empty -Y): 0=-y  90=+x  180=+y  -90=-x
# The waypoint is placed ON the cushion/mattress/pad surface; the client adds
# a 0.60 m seated eye height (0.70 in the tub) plus its 0.15 m occupied lift.
SEATS = [
    # Malibu lounge: north chenille sofa, facing south toward the fire
    ("Seat_A1", SOFA_B[0][0], SOFA_B[0][1], 0.47, 0),
    ("Seat_A2", SOFA_B[1][0], SOFA_B[1][1], 0.47, 0),
    ("Seat_A3", SOFA_B[2][0], SOFA_B[2][1], 0.47, 0),
    # Bar stools
    ("Seat_B1", 9.28, -0.41, 0.76, 0),
    ("Seat_B2", 9.88, -0.41, 0.76, 0),
    ("Seat_B3", 10.49, -0.41, 0.76, 0),
    # Malibu lounge: Charlie's tan club chair by the fire, turned to the TV
    ("Seat_Club", CLUB_SEAT[0], CLUB_SEAT[1], 0.49, -142),
    # Chenille sofa square to the wall TV (TV centre y 6.8), one per cushion.
    ("Seat_TV1", SOFA_A[2][0], SOFA_A[2][1], 0.47, -90),
    ("Seat_TV2", SOFA_A[1][0], SOFA_A[1][1], 0.47, -90),
    ("Seat_TV3", SOFA_A[0][0], SOFA_A[0][1], 0.47, -90),
    # Formal dining: the dinner party (dinner_figures.py) has six of the eight
    # chairs; D3 and D7, the middle pair facing each other, are kept free and
    # are served every course like the rest. The chairs are animated props, so
    # snap_seat finds no static seat here and keeps these authored spots.
    ("Seat_D3", DF.CHAIR_X["W"], DF.Y_OF[3], 0.47, 90),
    ("Seat_D7", DF.CHAIR_X["E"], DF.Y_OF[7], 0.47, -90),
    # Rooftop cocktail lounge on the old patio (build-cocktail.py): three bar
    # stools, the west sofa and chairs, the east loveseat and chairs.
    ("Seat_CkBar1", -1.05, 5.95, 0.77, 0),
    ("Seat_CkBar2", -0.25, 5.95, 0.77, 0),
    ("Seat_CkBar3", 0.55, 5.95, 0.77, 0),
    ("Seat_CkW1", -4.54, 5.99, 0.50, 90),
    ("Seat_CkW2", -4.54, 6.81, 0.50, 90),
    ("Seat_CkW3", -2.68, 5.95, 0.50, -90),
    ("Seat_CkW4", -2.68, 6.85, 0.50, -90),
    ("Seat_CkE1", 3.84, 4.80, 0.50, 180),
    ("Seat_CkE2", 4.56, 4.80, 0.50, 180),
    ("Seat_CkE3", 3.65, 6.22, 0.50, 0),
    ("Seat_CkE4", 4.75, 6.22, 0.50, 0),
    # Den: desk chair facing the room, two club chairs toed in to the desk
    ("Seat_Den_Desk", -0.36, -5.7375, 0.53, -90),
    ("Seat_Den_Club1", -2.46, -5.21, 0.46, 78),
    ("Seat_Den_Club2", -2.46, -6.27, 0.46, 102),
    # Beds: two upright seated spots each, on the mattress facing away from
    # the headboard (mattress surfaces from probe-mattress.py).
    ("Seat_Bed_NW1", -9.70, 6.90, 4.15, 90),
    ("Seat_Bed_NW2", -9.70, 7.85, 4.15, 90),
    ("Seat_Bed_NE1", 8.15, 7.40, 4.15, 180),
    ("Seat_Bed_NE2", 9.15, 7.40, 4.15, 180),
    ("Seat_Bed_SW1", -9.30, -3.60, 4.15, 180),
    ("Seat_Bed_SW2", -8.45, -3.60, 4.15, 180),
    # SW terrace hot tub: submerged seats (not snapped). Water surface is
    # z 0.555; with the client's 0.70 m tub eye height and 0.15 m occupied
    # lift the eye lands at 0.95, i.e. 0.40 m above the water, so the water
    # reaches a seated avatar's chest. The two south seats are the hot tub
    # regulars' (rovers_figures.TUB_HOME); visitors get the north pair, facing them.
    ("Seat_HotTub_N1", -10.28, -6.15, 0.10, 0),
    ("Seat_HotTub_N2", -9.22, -6.15, 0.10, 0),
    # Deep lounge chairs face one another across the spa drinks table.
    ("Seat_Spa_W", -6.15, -8.60, 0.54, 90),
    ("Seat_Spa_E", -3.15, -8.60, 0.54, -90),
    # SE terrace bistro pair
    ("Seat_E1", 9.50, -6.55, 0.50, 0),
    ("Seat_E2", 9.50, -8.05, 0.50, 180),
    # Sky den sofa
    ("Seat_S1", 0.60, -9.22, 3.87, 180),
    ("Seat_S2", 1.40, -9.22, 3.87, 180),
    ("Seat_S3", 2.20, -9.22, 3.87, 180),
    # Piano bench (pianist faces the keyboard, -x)
    ("Seat_Pno", PIANO_SEAT.x, PIANO_SEAT.y, 0.50, -90),
    # Sauna step bench (backs to the upper tier)
    ("Seat_Sauna1", -2.45, -8.86, 3.95, 180),
    ("Seat_Sauna2", -1.85, -8.86, 3.95, 180),
    ("Seat_Sauna3", -1.55, -8.00, 3.95, -90),
    # Walk-in closet ottoman, facing the mirror (-y)
    ("Seat_Closet", -9.2, 2.30, 3.89, 0),
]
SEATS += RV_SEATS
# The NE bed is taken by the animated couple (rovers_figures.py).
SEATS = [s for s in SEATS if s[0] not in ("Seat_Bed_NE1", "Seat_Bed_NE2")]

# Floors sit far below any expected seat height, so the z window already
# excludes them; only the (still unlinked) NavMesh needs a name filter. The
# ottoman is upholstered in the rug material, so materials must not be used.
FLOOR_MAT_KEYS = ("NavMat",)
def snap_seat(name, x, y, z_expect, radius=0.55, step=0.05):
    """Find the real seat surface near (x, y): a horizontal, non-floor surface
    within z_expect +/- 0.12. Returns the corrected (x, y, z)."""
    dgs = bpy.context.evaluated_depsgraph_get()
    pts = {}
    yy = y - radius
    while yy <= y + radius + 1e-6:
        xx = x - radius
        while xx <= x + radius + 1e-6:
            ok, loc, nrm, fi, ob, mw = sc.ray_cast(dgs, Vector((xx, yy, z_expect + 0.9)), Vector((0, 0, -1)), distance=1.2)
            if ok and abs(loc.z - z_expect) <= 0.12 and nrm.z > 0.7 and ob.name != "NavMesh":
                mats = ob.data.materials
                mi = ob.data.polygons[fi].material_index if fi < len(ob.data.polygons) else 0
                mn = mats[mi].name if mats and mi < len(mats) and mats[mi] else ''
                if not any(k in mn for k in FLOOR_MAT_KEYS):
                    pts[(round(xx, 2), round(yy, 2))] = loc.z
            xx += step
        yy += step
    if not pts:
        print(f"SEAT {name}: NO seat surface near ({x},{y}) z~{z_expect} — kept authored spot")
        return x, y, z_expect
    # cluster (8-neighbour) and take the cluster nearest to the authored point
    seen, clusters = set(), []
    for k in pts:
        if k in seen:
            continue
        stack, cl = [k], []
        seen.add(k)
        while stack:
            c = stack.pop()
            cl.append(c)
            for dx in (-step, 0, step):
                for dy in (-step, 0, step):
                    n = (round(c[0] + dx, 2), round(c[1] + dy, 2))
                    if n in pts and n not in seen:
                        seen.add(n)
                        stack.append(n)
        clusters.append(cl)
    def near_pt(cl):
        return min(cl, key=lambda c: (c[0] - x) ** 2 + (c[1] - y) ** 2)
    cl = min(clusters, key=lambda c: (near_pt(c)[0] - x) ** 2 + (near_pt(c)[1] - y) ** 2)
    cx, cy = sum(c[0] for c in cl) / len(cl), sum(c[1] for c in cl) / len(cl)
    nx, ny = near_pt(cl)
    vx, vy = cx - nx, cy - ny
    L = math.hypot(vx, vy)
    stepin = min(0.22, L)
    if L > 1e-6:
        nx, ny = nx + vx / L * stepin, ny + vy / L * stepin
    zc = sum(pts[c] for c in cl) / len(cl)
    moved = math.hypot(nx - x, ny - y)
    print(f"SEAT {name}: ({x:.2f},{y:.2f}) -> ({nx:.2f},{ny:.2f}) z={zc:.3f} (cluster {len(cl)} pts, moved {moved:.2f} m)")
    return nx, ny, zc

SNAPPED = []
for name, sx, sy, sz, yaw in SEATS:
    if name.startswith("Seat_HotTub_"):
        SNAPPED.append((name, sx, sy, sz, yaw))
        continue
    nx, ny, nz = snap_seat(name, sx, sy, sz)
    SNAPPED.append((name, nx, ny, nz, yaw))
SEATS = SNAPPED

if os.environ.get('LOUNGE_PRENAV_BLEND'):   # debug checkpoint for nav iteration
    bpy.ops.wm.save_as_mainfile(filepath=os.environ['LOUNGE_PRENAV_BLEND'])

# --- NavMesh: shared-lattice grid over the main floor ------------------------
# Cell walkable when a down-ray finds floor near z=0 and 1.7 m headroom above.
RES = 0.25
# Y1 reaches the Rovers' back wall on the same 0.25 m lattice (-9.8 - 31 * 0.25).
X1, X2, Y1, Y2 = -11.5, 11.5, -17.55, 9.8
nx = round((X2 - X1) / RES); ny = round((Y2 - Y1) / RES)
dg = bpy.context.evaluated_depsgraph_get()

DIRS = [Vector((1, 0, 0)), Vector((-1, 0, 0)), Vector((0, 1, 0)), Vector((0, -1, 0))]
# Three heightfield passes over ONE shared lattice: main floor, the staircase
# corridor (max-sampled so open risers read as a ramp), and the upper storey.
# Coincident lattice verts weld across passes, so the whole thing is one
# connected walkable surface — floor -> stairs -> upstairs.
STAIR = (-0.6, 3.6, -2.9, 2.0)  # x1,x2,y1,y2 corridor around the switchback
in_stair = lambda x, y: STAIR[0] < x < STAIR[1] and STAIR[2] < y < STAIR[3]

def hit_z(x, y, zcast, zlo, zhi, spread=0.0):
    best = None
    offs = [(0, 0)] if spread == 0 else [(0, 0), (spread, 0), (-spread, 0), (0, spread), (0, -spread)]
    for dx, dy in offs:
        ok, loc, *_ = sc.ray_cast(dg, Vector((x + dx, y + dy, zcast)), Vector((0, 0, -1)), distance=zcast - zlo + 0.05)
        if ok and zlo <= loc.z <= zhi and (best is None or loc.z > best):
            best = loc.z
    return best

def head_ok(x, y, z, need):
    ok2, *_ = sc.ray_cast(dg, Vector((x, y, z + 0.25)), Vector((0, 0, 1)), distance=need)
    return not ok2

def wall_ok(x, y, z):
    for h in (0.4, 1.3):
        o = Vector((x, y, z + h))
        for d in DIRS:
            # A 0.28 m inset erased both sides of ordinary doorways and split
            # rooms into separate pathfinding islands. The floor ray already
            # excludes the actual wall footprint, so only a small inset is
            # needed here.
            hh, *_ = sc.ray_cast(dg, o, d, distance=0.08)
            if hh:
                return False
    return True

bm = bmesh.new()
vcache = {}
def vert(i, j, z):
    k = (i, j, round(z, 1))
    if k not in vcache:
        vcache[k] = bm.verts.new((X1 + i * RES, Y1 + j * RES, z + 0.002))
    return vcache[k]

PASSES = [
    # (name, zcast, zlo, zhi, headroom, spread, stair_only, skip_stair)
    ("floor", 2.55, -0.08, 0.15, 1.6, 0.0, False, True),
    ("stair", 3.44, -0.08, 3.42, 1.0, 0.09, True, False),
    ("upper", 6.10, 3.26, 3.85, 1.6, 0.0, False, False),
]
faces_made = 0
for pname, zcast, zlo, zhi, need, spread, stair_only, skip_stair in PASSES:
    zs = {}
    for i in range(nx + 1):
        for j in range(ny + 1):
            x, y = X1 + i * RES, Y1 + j * RES
            if stair_only and not in_stair(x, y):
                continue
            if skip_stair and in_stair(x, y):
                continue
            zs[(i, j)] = hit_z(x, y, zcast, zlo, zhi, spread)
    made = 0
    for i in range(nx):
        for j in range(ny):
            c = [zs.get((i, j)), zs.get((i + 1, j)), zs.get((i + 1, j + 1)), zs.get((i, j + 1))]
            if any(v is None for v in c) or max(c) - min(c) > 0.45:
                continue
            cx, cy, cz = X1 + (i + 0.5) * RES, Y1 + (j + 0.5) * RES, sum(c) / 4
            if not head_ok(cx, cy, cz, need):
                continue
            if pname != "stair" and not wall_ok(cx, cy, cz):
                continue
            try:
                bm.faces.new((vert(i, j, c[0]), vert(i + 1, j, c[1]), vert(i + 1, j + 1, c[2]), vert(i, j + 1, c[3])))
                made += 1
            except ValueError:
                pass  # duplicate face across overlapping passes
    faces_made += made
    print(f"NAV {pname}: {made} cells")
print(f"NAV total {faces_made} cells")

# The source floor plates stop on opposite sides of several real door
# thresholds. A raycast-only grid therefore leaves rooms a fraction of a metre
# apart even though the visible doorway is open. Join the nearest boundary
# edges at each surveyed threshold. Sharing a full edge is required by the Hubs
# pathfinder; merely touching at one vertex is not connected.
def nav_face_components():
    remaining = set(bm.faces)
    components = []
    face_component = {}
    while remaining:
        seed = remaining.pop()
        todo = [seed]
        component = []
        while todo:
            face = todo.pop()
            component.append(face)
            for edge in face.edges:
                for neighbor in edge.link_faces:
                    if neighbor in remaining:
                        remaining.remove(neighbor)
                        todo.append(neighbor)
        ci = len(components)
        for face in component:
            face_component[face] = ci
        components.append(component)
    return components, face_component

def nearest_nav_face(point):
    target = Vector(point)
    return min(bm.faces, key=lambda face: (face.calc_center_median() - target).length_squared)

def connect_nav_regions(name, point_a, point_b, threshold, radius=1.0, optional=False):
    components, face_component = nav_face_components()
    ca = face_component[nearest_nav_face(point_a)]
    cb = face_component[nearest_nav_face(point_b)]
    if ca == cb:
        print(f"NAV LINK {name}: already connected")
        return
    target = Vector(threshold)
    def edge_center(edge):
        return (edge.verts[0].co + edge.verts[1].co) * 0.5
    def candidate_edges(component_id):
        edges = set()
        for face in components[component_id]:
            for edge in face.edges:
                if len(edge.link_faces) == 1 and (edge_center(edge) - target).length <= radius:
                    edges.add(edge)
        return edges
    edges_a = candidate_edges(ca)
    edges_b = candidate_edges(cb)
    if not edges_a or not edges_b:
        if optional:
            print(f"NAV LINK {name}: no boundary edges near {threshold} (optional, skipped)")
            return
        raise RuntimeError(f"NAV LINK {name} found no boundary edges near {threshold}")
    edge_a, edge_b = min(
        ((ea, eb) for ea in edges_a for eb in edges_b),
        key=lambda pair: (edge_center(pair[0]) - edge_center(pair[1])).length_squared,
    )
    a0, a1 = edge_a.verts
    b0, b1 = edge_b.verts
    if (a0.co - b0.co).length_squared + (a1.co - b1.co).length_squared > (a0.co - b1.co).length_squared + (a1.co - b0.co).length_squared:
        b0, b1 = b1, b0
    gap = (edge_center(edge_a) - edge_center(edge_b)).length
    # Edges that already touch at one vertex (a corner contact) bridge with a
    # triangle; a quad would reuse that vertex and fail.
    ring = []
    for v in (a0, a1, b1, b0):
        if v not in ring:
            ring.append(v)
    if len(ring) < 3:
        raise RuntimeError(f"NAV LINK {name}: boundary edges coincide, nothing to bridge")
    try:
        bm.faces.new(tuple(ring))
    except ValueError as exc:
        raise RuntimeError(f"NAV LINK {name} could not bridge boundary edges: {exc}")
    print(f"NAV LINK {name}: edge gap {gap:.2f} m ({'tri' if len(ring) == 3 else 'quad'})")

NAV_LINKS = [
    # name, side A probe, side B probe, doorway/landing threshold, search radius
    ("ground-lobby", (-7.5, 6.0, 0.0), (-4.5, -8.2, 0.05), (-1.2, -7.5, 0.02), 1.0),
    # Library: its door is the 0.7 m opening at the NE corner (x -3.2..-2.5,
    # y -4.5) and the bookcase end at x -3.1..-2.8 leaves a strip the 0.25 m
    # grid cannot fit. Bridge the strip.
    ("ground-library", (-7.5, 6.0, 0.0), (-4.0, -5.3, 0.0), (-3.18, -4.62, 0.02), 0.5),
    # Patio door: piano room -> SW deck through the open leaves (x -9.15..-7.27).
    ("ground-patio-door", (-8.2, -3.0, 0.02), (-7.95, -6.3, 0.07), (-8.2, -4.60, 0.10), 1.0),
    # NW dressing room: 0.6 m door at x -10.1..-9.6 through the y~-1.4 partition
    # to the vestibule north of the SW bedroom.
    ("upper-nw-dressing", (-8.0, -3.0, 3.5), (-9.2, -0.3, 3.5), (-9.88, -1.67, 3.52), 0.6),
    # East bathroom: 1.2 m door in the NE bedroom's south wall (x 7.4..8.6,
    # y 4.0) with a wardrobe column just inside; bridge past its east side.
    ("upper-east-bath", (8.0, 5.0, 3.5), (9.9, 2.6, 3.5), (8.45, 3.9, 3.5), 0.45),
    ("ground-stair-pad", (-7.5, 6.0, 0.0), (3.0, -1.0, 0.03), (3.62, -1.55, 0.03), 0.8),
    ("stair-pad-flight", (3.0, -1.0, 0.03), (2.0, -1.5, 0.30), (2.50, -1.55, 0.12), 0.8),
    ("stair-landing", (1.5, -2.05, 3.25), (0.0, -3.5, 3.50), (1.50, -2.05, 3.38), 0.8),
    ("upper-nw-bedroom", (0.0, -3.5, 3.50), (-8.0, 5.0, 3.53), (-5.75, 3.58, 3.52), 0.8),
    ("upper-ne-bedroom", (0.0, -3.5, 3.50), (8.0, 5.0, 3.50), (6.75, 3.95, 3.50), 0.8),
    ("upper-sw-bedroom", (0.0, -3.5, 3.50), (-8.0, -3.0, 3.50), (-7.10, -1.68, 3.50), 0.8),
    ("upper-gym", (0.0, -3.5, 3.50), (-1.5, -5.0, 3.54), (-1.62, -6.05, 3.52), 0.8),
    ("upper-east-suite", (0.0, -3.5, 3.50), (8.5, -2.8, 3.50), (7.50, 0.45, 3.50), 0.8),
    # Sky den: its north double door from the hall (x 0.0..1.45, y -7.18).
    ("upper-sky-den", (0.0, -3.5, 3.50), (1.5, -8.5, 3.53), (0.72, -7.18, 3.52), 0.45),
    # Sauna: doorway through the gym's south wall (x -2.58..-1.92, y -6.3..-6.7).
    # Radii are tight on purpose: the shortest gap otherwise bridges a wall.
    ("upper-sauna", (-1.5, -5.0, 3.54), (-1.3, -8.0, 3.53), (-2.25, -6.50, 3.52), 0.6),
    # Rovers: the recessed front door off the balcony, the lifting flap to
    # the servers' side, and the sky den's south door onto the roof terrace.
    ("ground-rovers-door", (0.2, -7.6, 0.10), (2.0, -12.9, 0.10), (-0.65, -10.45, 0.10), 1.0),
    ("rovers-bar-flap", (2.0, -12.9, 0.10), (2.5, -15.45, 0.106), (-0.20, -14.57, 0.106), 0.8),
    ("upper-rovers-roof", (1.5, -8.5, 3.53), (1.5, -14.0, 3.53), (3.41, -9.85, 3.53), 0.6),
]
for link_args in NAV_LINKS:
    connect_nav_regions(*link_args)
connect_nav_regions("ground-library-closet", (-1.6, -4.7, 0.0), (-2.0, -5.7, 0.0), (-1.62, -5.15, 0.02), 0.6, optional=True)
connect_nav_regions("upper-nw-closet", (-8.3, 5.5, 3.5), (-9.2, 2.6, 3.5), (-9.5, 3.52, 3.52), 0.7, optional=True)

# Everything that is not face-connected to the ground lounge is unreachable on
# foot (closets behind doors, showers behind glass, slivers between furniture
# and glass). The teleport arc must not be able to land there either.
_components, _face_component = nav_face_components()
_root = _face_component[nearest_nav_face((-7.5, 6.0, 0.0))]
_dropped = [f for f in bm.faces if _face_component[f] != _root]
if _dropped:
    _n_islands = len({_face_component[f] for f in _dropped})
    bmesh.ops.delete(bm, geom=_dropped, context='FACES')
    print(f"NAV prune: dropped {len(_dropped)} faces in {_n_islands} unreachable islands")

# Build gate: all occupied rooms must resolve to the same face-connected
# navigation component as the ground lounge. This catches missing thresholds
# and broken stair hand-offs before a GLB can be published.
bm.faces.ensure_lookup_table()
remaining = set(bm.faces)
nav_components = []
face_component = {}
while remaining:
    seed = remaining.pop()
    todo = [seed]
    component = []
    while todo:
        face = todo.pop()
        component.append(face)
        for edge in face.edges:
            for neighbor in edge.link_faces:
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    todo.append(neighbor)
    component_id = len(nav_components)
    for face in component:
        face_component[face] = component_id
    nav_components.append(component)

NAV_REQUIRED = {
    "ground lounge": (-7.5, 6.0, 0.0),
    "ground lobby": (-4.5, -8.2, 0.05),
    "upper hall": (0.0, -3.5, 3.50),
    "upper NW bedroom": (-8.0, 5.0, 3.53),
    "upper NE bedroom": (8.0, 5.0, 3.50),
    "upper SW bedroom": (-8.0, -3.0, 3.50),
    "upper gym": (-1.5, -5.0, 3.54),
    "upper east suite": (8.5, -2.8, 3.50),
    "upper sky den": (1.5, -8.5, 3.53),
    "upper sauna": (-1.3, -8.0, 3.53),
    "ground library": (-4.0, -5.3, 0.0),
    "ground patio": (0.0, 7.6, 0.0),
    "ground dining": (6.5, 6.0, 0.0),
    "ground vestibule": (0.2, -7.6, 0.10),
    "sw terrace deck": (-7.95, -6.3, 0.07),
    "sw terrace pocket": (-6.3, -6.1, 0.10),
    "spa open wall": (-7.62, -7.5, 0.10),
    "spa seating approach": (-4.6, -7.25, 0.10),
    "patio door threshold": (-8.2, -4.60, 0.10),
    "se terrace deck": (8.5, -6.0, 0.07),
    "upper NW dressing": (-9.2, -0.3, 3.5),
    "upper east bath": (9.9, 2.6, 3.5),
    "upper NW closet": (-9.2, 2.6, 3.5),
    "rovers bar room": (2.0, -12.9, 0.10),
    "rovers lobby": (-0.65, -10.40, 0.106),
    "rovers behind the bar": (2.5, -15.45, 0.106),
    "rovers darts": (-2.3, -14.0, 0.10),
    "rovers roof terrace": (1.5, -14.0, 3.53),
}
required_components = {}
for label, point in NAV_REQUIRED.items():
    target = Vector(point)
    nearest = min(bm.faces, key=lambda face: (face.calc_center_median() - target).length_squared)
    required_components[label] = face_component[nearest]
root_component = required_components["ground lounge"]
disconnected = {label: component for label, component in required_components.items() if component != root_component}
if disconnected:
    raise RuntimeError(f"NAV CONNECTIVITY GATE failed: root={root_component}, disconnected={disconnected}")
print(f"NAV CONNECTIVITY GATE passed: {len(NAV_REQUIRED)} occupied regions on component {root_component}")

bmesh.ops.triangulate(bm, faces=bm.faces[:])
navme = bpy.data.meshes.new('NavMesh')
bm.to_mesh(navme); bm.free()
nav = bpy.data.objects.new('NavMesh', navme)
navmat = bpy.data.materials.new('NavMat'); navmat.diffuse_color = (0, 1, 0, 1)
navme.materials.append(navmat)
sc.collection.objects.link(nav)

# --- Empties: spawns, seats, lights ------------------------------------------
def empty(name, x, y, z, yaw=0.0):
    o = bpy.data.objects.new(name, None)
    o.location = (x, y, z)
    o.rotation_euler = (0, 0, yaw)
    sc.collection.objects.link(o)
    return o

empty("Spawn_1", -4.0, 0.0, 0, math.pi / 2)   # hall west, facing +x
empty("Spawn_2", 4.5, 1.5, 0, -math.pi / 2)   # hall east, facing -x
for name, sx, sy, sz, yawdeg in SEATS:
    empty(name, sx, sy, sz, math.radians(yawdeg))
empty("AmbientLight", 0, 0, 2.8)
empty("Light_A", -7.5, 5.0, 2.4)   # over the lounge sofa
empty("Light_B", 9.9, -1.4, 2.2)   # over the bar
empty("Light_C", 1.5, 0.5, 5.9)    # upstairs landing
empty("Light_D", -8.8, 7.0, 5.8)   # NW bedroom
empty("Light_E", 8.8, 6.9, 5.8)    # NE bedroom
empty("Light_F", -8.8, -3.8, 5.8)  # SW bedroom
empty("Light_G", 1.5, -12.0, 3.0)    # Rovers bar + sky den + roof terrace (no shadows: passes the slab)
empty("Light_H", -1.38, -5.38, 1.30)  # den banker's lamp (was the spa lobby light)
empty("Light_I", -9.6, -7.0, 2.3)    # SW terrace
empty("Light_J", 9.3, -7.2, 2.3)     # SE terrace

# --- Screens + view backdrop -------------------------------------------------
def plane(name, w, h, x, y, z, rx, mat):
    me = bpy.data.meshes.new(name)
    b = bmesh.new()
    vs = [b.verts.new(p) for p in ((-w/2, 0, -h/2), (w/2, 0, -h/2), (w/2, 0, h/2), (-w/2, 0, h/2))]
    f = b.faces.new(vs)
    uv = b.loops.layers.uv.new()
    for loop, u in zip(f.loops, ((0, 0), (1, 0), (1, 1), (0, 1))):
        loop[uv].uv = u
    b.to_mesh(me); b.free()
    me.materials.append(mat)
    o = bpy.data.objects.new(name, me)
    o.location = (x, y, z)
    o.rotation_euler = (rx, 0, 0)
    sc.collection.objects.link(o)
    return o

dark = bpy.data.materials.new('ScreenDark')
dark.use_nodes = True
bsdf = dark.node_tree.nodes['Principled BSDF']
bsdf.inputs['Base Color'].default_value = (0.02, 0.027, 0.04, 1)
bsdf.inputs['Roughness'].default_value = 0.55  # 0.3 threw a hard point-light hot spot across the whole panel
# West-wall black panel, facing east into the lounge (rotate -y normal to +x).
# The wall face position drifts as the source mesh is edited, and an authored
# constant once left the whole TV buried 24 cm behind the wall — so probe the
# actual wall around the mount point and hang the panel 3 cm proud of it.
tv_dg = bpy.context.evaluated_depsgraph_get()
tv_wall_x = None
for py, pz in ((7.9, 2.5), (5.7, 2.5), (6.8, 2.4), (7.9, 1.3)):
    hit, loc, _, _, _, _ = sc.ray_cast(tv_dg, Vector((-8.0, py, pz)), Vector((-1, 0, 0)), distance=4.0)
    if hit and (tv_wall_x is None or loc.x > tv_wall_x):
        tv_wall_x = loc.x
if tv_wall_x is None:
    raise RuntimeError("TVScreen wall probe found no west wall")
tv = plane("TVScreen", 2.6, 1.5, tv_wall_x + 0.03, 6.8, 1.9, 0, dark)
tv.rotation_euler = (0, 0, math.pi / 2)
print(f"TVSCREEN wall at x={tv_wall_x:.3f}, panel at x={tv_wall_x + 0.03:.3f}")
# (The second screen-share display that stood on the kitchen counter behind the
# bar stools is gone at Jay's request, 2026-09-05; tv.js copes without it.)

# --- Gallery: public-domain masters on the perimeter walls -------------------
# (name, image, facing, wall coord, preferred centre, search min, search max, z, height)
# facing = the direction the canvas faces (into the room). "wall coord" is the
# x of a ±x wall or the y of a ±y wall; the canvas centre slides along the
# wall from the preferred spot outward until a slot is found where EVERY
# sample across the canvas hits the same flat, vertical, non-glass surface
# and nothing stands within 0.6 m in front of it.
import os
ART_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "art")
YAWS = {"+x": math.pi / 2, "-x": -math.pi / 2, "+y": math.pi, "-y": 0.0}
DIRV = {"+x": Vector((-1, 0, 0)), "-x": Vector((1, 0, 0)), "+y": Vector((0, -1, 0)), "-y": Vector((0, 1, 0))}
GALLERY = [
    # Charlie Harper's jazz poster over the lounge fireplace (chimney breast).
    ("Art_Jazz", "malibu-jazz.jpg", [("+x", -10.44, 4.04, 3.4, 4.7, 2.15)], 1.0),
    # Second jazz poster on the piano corner's west wall (first clean run).
    ("Art_JazzSunset", "malibu-jazz2.jpg", [("+x", -10.96, -2.9, -3.4, 0.6, 1.6)], 1.1),
    # Lobby north wall, both at eye level, either side of the runner.
    ("Art_Sunrise", "sunrise.jpg", [("-y", -7.12, -4.6, -5.25, -3.7, 1.6)], 0.95),
    ("Art_Moulin", "moulin.jpg", [("-y", -7.12, -2.55, -3.6, -1.42, 1.6)], 1.15),
    # West Wind on the lobby's west wall north of the terrace door, facing in.

    # The Great Wave's vestibule wall is now open balcony: bar wall north of
    # the island, else the dining wall.
    ("Art_Wave", "wave.jpg", [("-y", -6.30, 3.0, 2.3, 3.9, 1.6),
                              ("-y", -5.80, 1.2, -1.0, 2.2, 1.55),
                              ("-x", 11.18, 1.5, -0.2, 3.0, 1.5)], .9),
    ("Art_Paris1946", "paris-1946.png", [("-y", -6.30, 4.35, 3.4, 5.0, 1.65)], 1.14),
    ("Art_Paris1948", "paris-1948.png", [("-y", -6.30, 5.50, 4.95, 6.08, 1.65)], 1.14),
    # Dining + bar, east wall.
    # Dining, east wall: English country pictures over the oak wainscot.
    ("Art_HayWain", "haywain.jpg", [("-x", 11.18, 7.1, 6.1, 8.9, 1.75)], 1.0),
    ("Art_Andrews", "andrews.jpg", [("-x", 11.18, 5.29, 4.62, 5.95, 1.75)], 0.74),
    # Cafe Terrace: the bar's east wall is cabinets and blinds end to end, so
    # fall back to the bar wall north of the island, then the dining wall
    # between the Hay Wain and the north glass.
    ("Art_Cafe", "cafeterrace.jpg", [("-x", 10.85, -1.35, -2.0, -0.7, 1.55),   # kitchen, facing the cafe hatch side
                                     ("+y", -4.31, -2.15, -3.2, -1.1, 1.55),   # main hall, south wall
                                     ("-x", 11.18, -2.6, -4.3, -1.1, 1.5),
                                     ("-x", 11.18, 1.5, -0.2, 3.0, 1.5),
                                     ("-x", 11.18, 8.6, 7.9, 9.4, 1.6)], 1.3),
    # Den: Menzel's rolling mill facing the desk, Turner's Temeraire over the
    # credenza, Rain, Steam and Speed on the entry wall.
    ("Art_Menzel", "menzel.jpg", [("+x", -5.26, -5.74, -6.85, -4.62, 1.95)], 1.0),
    ("Art_Temeraire", "temeraire.jpg", [("+y", -6.945, -4.10, -4.95, -3.25, 1.95)], 0.78),
    ("Art_RainSteam", "rainsteam.jpg", [("-y", -4.53, -1.90, -3.10, 0.05, 1.95)], 0.84),
    # Tangled Garden in the sky den (north wall).
    ("Art_Tangled", "tangledgarden.jpg", [("-y", -7.10, 2.6, 0.3, 3.7, 5.05)], 0.85),
]
CENTRE_ON_WALL = {"Art_Jazz"}
framemat = mat_frame = bpy.data.materials.new('ArtFrame')
mat_frame.use_nodes = True
fb = mat_frame.node_tree.nodes['Principled BSDF']
fb.inputs['Base Color'].default_value = (0.02, 0.018, 0.015, 1)
fb.inputs['Roughness'].default_value = 0.4
dga = bpy.context.evaluated_depsgraph_get()

def art_slot(name, facing, wall_c, u_pref, u_min, u_max, z, w, h):
    d = DIRV[facing]
    horiz = facing in ("+x", "-x")
    def probe(u):
        depths = []
        for i in range(7):
            for j in range(5):
                uu = u + (i - 3) / 3.0 * (w / 2) * 0.97
                zz = z + (j - 2) / 2.0 * (h / 2) * 0.97
                origin = (Vector((wall_c, uu, zz)) if horiz else Vector((uu, wall_c, zz))) - d * 0.6
                ok, loc, nrm, fi, ob, mw = sc.ray_cast(dga, origin, d, distance=1.2)
                if not ok or ob.name.startswith(("Art_", "NavMesh", "View", "Spawn", "Seat_")):
                    return None
                mats = ob.data.materials
                mi = ob.data.polygons[fi].material_index if fi < len(ob.data.polygons) else 0
                mn = mats[mi].name if mats and mi < len(mats) and mats[mi] else ''
                if mn == GLASS_MAT or abs(nrm.z) > 0.3 or nrm.dot(-d) < 0.7:
                    return None
                depths.append((loc - origin).length)
        if max(depths) - min(depths) > 0.015:
            return None
        return sum(depths) / len(depths)
    def flat_extent(u0, depth):
        # Walk outward along the wall while the surface stays at the same
        # depth (a chimney breast, a pier): the run the piece should centre on.
        def same(uu):
            origin = (Vector((wall_c, uu, z)) if horiz else Vector((uu, wall_c, z))) - d * 0.6
            ok, loc, nrm, fi, ob, mw = sc.ray_cast(dga, origin, d, distance=1.2)
            if not ok or ob.name.startswith(("Art_", "NavMesh", "View", "Spawn", "Seat_")):
                return False
            mats = ob.data.materials
            mi = ob.data.polygons[fi].material_index if fi < len(ob.data.polygons) else 0
            mn = mats[mi].name if mats and mi < len(mats) and mats[mi] else ''
            return mn != GLASS_MAT and abs(nrm.z) <= 0.3 and nrm.dot(-d) >= 0.7 and abs((loc - origin).length - depth) <= 0.015
        lo = hi = u0
        while lo - 0.03 > u0 - 4.0 and same(lo - 0.03):
            lo -= 0.03
        while hi + 0.03 < u0 + 4.0 and same(hi + 0.03):
            hi += 0.03
        return lo, hi
    order = [u_pref]
    for k in range(1, 80):
        for u in (u_pref + 0.1 * k, u_pref - 0.1 * k):
            if u_min + w / 2 - 1e-6 <= u <= u_max - w / 2 + 1e-6:
                order.append(u)
    for u in order:
        depth = probe(u)
        if depth is not None:
            lo, hi = flat_extent(u, depth)
            print(f"GALLERY {name}: flat run u {lo:.2f}..{hi:.2f} ({hi - lo:.2f} m) around u={u:.2f}")
            if name in CENTRE_ON_WALL:
                uc = (lo + hi) / 2
                dc = probe(uc)
                if w + 0.1 <= hi - lo < 4.0 and dc is not None:
                    print(f"GALLERY {name}: centred on the run at u={uc:.2f} (was {u:.2f})")
                    u, depth = uc, dc
                else:
                    raise RuntimeError(f"GALLERY {name}: cannot centre on run {lo:.2f}..{hi:.2f}")
            origin = (Vector((wall_c, u, z)) if horiz else Vector((u, wall_c, z))) - d * 0.6
            surf = origin + d * depth
            pos = surf - d * 0.025
            print(f"GALLERY {name}: slot at u={u:.2f} (preferred {u_pref:.2f}, moved {abs(u - u_pref):.2f} m), surface {tuple(round(v, 3) for v in surf)}")
            return pos
    print(f"GALLERY {name}: NO clean {w:.2f}x{h:.2f} slot on {facing} wall {wall_c} in [{u_min},{u_max}] — SKIPPED")
    return None

hung = 0
for name, fn, cands, h in GALLERY:
    img = bpy.data.images.load(os.path.join(ART_DIR, fn))
    aspect = img.size[0] / img.size[1]
    w = h * aspect
    pos = None
    for facing, wall_c, u_pref, u_min, u_max, az in cands:
        pos = art_slot(name, facing, wall_c, u_pref, u_min, u_max, az, w, h)
        if pos is not None:
            break
    if pos is None:
        continue
    ax, ay = pos.x, pos.y
    am = bpy.data.materials.new(name + "_mat")
    am.use_nodes = True
    nt2 = am.node_tree
    bsdf2 = nt2.nodes['Principled BSDF']
    t2 = nt2.nodes.new('ShaderNodeTexImage')
    t2.image = img
    nt2.links.new(t2.outputs['Color'], bsdf2.inputs['Base Color'])
    bsdf2.inputs['Roughness'].default_value = 0.85
    yaw = YAWS[facing]
    p = plane(name, w, h, ax, ay, az, 0, am)
    p.rotation_euler = (0, 0, yaw)
    # frame: slim dark box just behind the canvas
    fw, fh = w + 0.08, h + 0.08
    fx, fy = ax, ay
    off = 0.035
    if facing == "+x": fx -= off
    elif facing == "-x": fx += off
    elif facing == "+y": fy -= off
    elif facing == "-y": fy += off
    bpy.ops.mesh.primitive_cube_add(location=(fx, fy, az))
    fr = bpy.context.active_object
    fr.name = name + "_frame"
    if facing in ("+x", "-x"):
        fr.scale = (0.025, fw / 2, fh / 2)
    else:
        fr.scale = (fw / 2, 0.025, fh / 2)
    fr.data.materials.append(mat_frame)
    # Re-evaluate before the next probe: until then the ray-cast scene still
    # holds the frame as an unscaled 2 m cube, which blocks nearby slots.
    bpy.context.view_layer.update()
    hung += 1
if hung < 8:
    raise RuntimeError(f"GALLERY: only {hung} of {len(GALLERY)} pieces found a clean wall slot")

# Emissive backdrop material: the runtime view switcher swaps its emissiveMap
# for the full-res day/dusk image.
def viewmat(mname, img_path):
    vm = bpy.data.materials.new(mname)
    vm.use_nodes = True
    vnt = vm.node_tree
    for n in list(vnt.nodes):
        vnt.nodes.remove(n)
    voutn = vnt.nodes.new('ShaderNodeOutputMaterial')
    vem = vnt.nodes.new('ShaderNodeEmission')
    vtex = vnt.nodes.new('ShaderNodeTexImage')
    vtex.image = bpy.data.images.load(img_path)
    vnt.links.new(vtex.outputs['Color'], vem.inputs['Color'])
    vnt.links.new(vem.outputs['Emission'], voutn.inputs['Surface'])
    return vm

BAKE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bake")

# Skyline: one cylindrical panorama (make-pano.py stitches the four
# directional photos with feathered seams, horizon at z 3.5) instead of four
# flat planes meeting at 90-degree corners. Radius 21 m clears the building's
# corners (15.4 m) and the Rovers' back corners (18.3 m); z -4..13 keeps the old planes' vertical coverage. UV u=0
# at the NW corner, increasing clockwise (north, east, south, west quadrants),
# so the panorama reads un-mirrored from inside. The bake texture is a 1024
# placeholder; the runtime view switcher swaps in the 8K day/dusk panorama.
def view_cylinder(name, mat, radius=21.0, z0=-4.0, z1=13.0, segs=72):
    me = bpy.data.meshes.new(name)
    bmv = bmesh.new()
    uvl = bmv.loops.layers.uv.new("UVMap")
    ring0, ring1 = [], []
    for i in range(segs):
        az = math.radians(-45.0 + 360.0 * i / segs)
        x, y = radius * math.sin(az), radius * math.cos(az)
        ring0.append(bmv.verts.new((x, y, z0)))
        ring1.append(bmv.verts.new((x, y, z1)))
    for i in range(segs):
        j = (i + 1) % segs
        f = bmv.faces.new((ring0[i], ring0[j], ring1[j], ring1[i]))
        u0, u1 = i / segs, (i + 1) / segs
        for loop, uv in zip(f.loops, ((u0, 0.0), (u1, 0.0), (u1, 1.0), (u0, 1.0))):
            loop[uvl].uv = uv
    bmv.to_mesh(me)
    bmv.free()
    me.materials.append(mat)
    o = bpy.data.objects.new(name, me)
    sc.collection.objects.link(o)
    return o

view_cylinder("ViewPano", viewmat('PanoBackdrop', viewimg))

# Sky dome: an emissive gradient sphere so the patio, terraces and sky den see
# sky above the backdrop planes instead of the renderer's black clear colour.
# The runtime view switcher swaps its emissiveMap with the day/dusk sky.
bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, radius=70, location=(0, 0, 0))
sky = bpy.context.active_object
sky.name = "ViewSky"
sky.data.materials.append(viewmat('SkyBackdrop', os.path.join(BAKE_DIR, 'day-sky.jpg')))
_bs = bmesh.new()
_bs.from_mesh(sky.data)
bmesh.ops.reverse_faces(_bs, faces=_bs.faces[:])
_bs.to_mesh(sky.data)
_bs.free()

# --- Detail pass: no flat-colour surface left ---------------------------------
# About two thirds of the materials were a single flat colour (the source's
# fake_mat_* / enduit / blanc families, the palette recolours, and everything
# this script builds with mk()), which reads as smooth plastic in the headset.
# Multiply a neutral grey detail tile (art/detail-*.jpg, mean 0.9, peak 1.0)
# into each one: glTF exports it as baseColorTexture x baseColorFactor, so
# every chosen colour is kept and only surface character is added. UVs are
# world-planar per face (the same projection retex_region uses), written only
# on faces of the materials being textured. Runs last, on final geometry.
DETAIL_MEAN = 0.9
DETAIL_TILES = {   # kind: (tile, metres per repeat)
    'plaster': ('detail-plaster.jpg', 2.0),
    'paint':   ('detail-paint.jpg', 1.0),
    'wood':    ('detail-wood.jpg', 0.9),
    'fabric':  ('detail-fabric.jpg', 0.22),
    'stone':   ('detail-stone.jpg', 1.0),
    'metal':   ('detail-metal.jpg', 0.5),
}
DETAIL_KIND = {
    'plaster': ('blanc_001', 'beige_006_Wall', 'enduit_', 'gris_00', 'noir_001', 'fake_mat_251_251_251_255',
                'papier_peint', '20210115-211826-cet', 'FacadeSW', 'SpaLimewash', 'SpaPocketLimewash',
                'CafeWarmPlaster', 'ClosetWall', 'ClosetCeil', 'DenEndWall', 'DenWalls', 'GymWall', 'LobbyWall', 'DiningWalls', 'MalibuWalls'),
    'wood':    ('fake_mat_6_5_5_255', 'fake_mat_104_101_99_255', 'fake_mat_170_128_59_255', 'fake_mat_87_43_28_255',
                'fake_mat_35_32_34_255', 'noguchi_sofa_ottoman____ottomanwood', 'qing_style_chair', 'ArtFrame',
                'TrimDark', 'DenOak', 'DeckWood', 'SpaHoneyTeak', 'DiningOak', 'MalibuWood', 'MalibuBeam', 'MalibuPelmet',
                'RoversMahogany', 'CockWood'),
    'fabric':  ('fake_mat_224_230_228_255', 'fake_mat_230_220_187_255', 'fake_mat_196_192_184_255',
                'fake_mat_157_154_155_255', 'moquette_', 'canape_', 'BedIvory', 'Pillow', 'Cush', 'LoungeCush',
                'OttomanLinen', 'TowelIvory', 'RugWine', 'PianoRug', 'PianoFelt', 'HeadboardTeal', 'SpaIvoryLinen',
                'SpaWovenSand', 'CafeCanvas', 'CafeRattan', 'WardrobeBackLinen', 'DiningSeat',
                'MalibuRugBinding', 'MalibuLeather', 'CockVelvet', 'CockLeather', 'CockRug'),
    'stone':   ('LobbyStone', 'CafeGrout', 'tex_plan_travail', 'cuisine_ilot_002___mat_marbre', 'graviers_003',
                'faience_028', 'SaunaStone'),
    'metal':   ('RailDark', 'DoorBronze', 'CafeAgedBrass', 'LobbyBrass', 'LiftSteel', 'SaunaStove', 'ClosetRail',
                'BBQSteel'),
}
# Deliberately smooth or not a surface: glass, glows, mirrors, water, screens,
# lacquer, glazed ceramics, food and flowers, foliage, art and backdrops.
DETAIL_SKIP = ('Foliage_', 'Floral_', 'CafeRose', 'CafeIvoryCeramic', 'CafeEspresso', 'CafeCupChina', 'CafeCoffee',
               'CafeCake', 'SpaAperol', 'SpaLemon', 'SpaTerracotta',
               'DenIvoryPlanter', 'DenPlanterSoil', 'WarmGlow', 'SaunaEmber', 'MirrorPanel', 'GymMirror',
               'HotTubWater', 'ScreenDark', 'PianoLacquer', 'PianoIvory', 'NavMat', 'Art', 'View', 'Sky',
               'Rockies', 'DiningCandleWax', 'MalibuGlazeBlue', 'RoversAle', 'RoversFroth', 'DinnerSet',
               'CockBottle', 'CockStoneBlack', GLASS_MAT)

def detail_kind(m):
    if m.name.startswith(DETAIL_SKIP) or not m.use_nodes:
        return None
    b = m.node_tree.nodes.get('Principled BSDF')
    if b is None or b.inputs['Base Color'].is_linked:
        return None
    if b.inputs['Alpha'].default_value < 0.999 or b.inputs['Alpha'].is_linked:
        return None
    if b.inputs['Emission Strength'].default_value > 0 and max(b.inputs['Emission Color'].default_value[:3]) > 0:
        return None
    for kind, prefixes in DETAIL_KIND.items():
        if m.name.startswith(prefixes):
            return kind
    return 'metal' if b.inputs['Metallic'].default_value >= 0.3 else 'paint'

_detail_imgs = {k: bpy.data.images.load(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'art', f))
                for k, (f, _s) in DETAIL_TILES.items()}
_used = set()
for ob in sc.collection.all_objects:
    if ob.type == 'MESH' and not ob.name.startswith(("NavMesh", "View", "Sky", "Art_", "Spawn", "Seat_")):
        _used.update(ob.data.materials[p.material_index] for p in ob.data.polygons
                     if ob.data.materials and p.material_index < len(ob.data.materials) and ob.data.materials[p.material_index])
DETAIL_PLAN = {}
for m in sorted(_used, key=lambda m: m.name):
    kind = detail_kind(m)
    if kind is None:
        continue
    nt = m.node_tree
    b = nt.nodes['Principled BSDF']
    col = b.inputs['Base Color'].default_value
    tex = nt.nodes.new('ShaderNodeTexImage')
    tex.image = _detail_imgs[kind]
    mix = nt.nodes.new('ShaderNodeMix')
    mix.data_type = 'RGBA'
    mix.blend_type = 'MULTIPLY'
    mix.inputs['Factor'].default_value = 1.0
    sock = {s.identifier: s for s in mix.inputs}
    sock['B_Color'].default_value = tuple(min(1.0, c / DETAIL_MEAN) for c in col[:3]) + (1.0,)
    nt.links.new(tex.outputs['Color'], sock['A_Color'])
    nt.links.new(next(s for s in mix.outputs if s.identifier == 'Result_Color'), b.inputs['Base Color'])
    DETAIL_PLAN[m.name] = kind
_counts = {}
for ob in sc.collection.all_objects:
    if ob.type != 'MESH' or ob.name.startswith(("NavMesh", "View", "Sky", "Art_", "Spawn", "Seat_")):
        continue
    me = ob.data
    kinds = [DETAIL_PLAN.get(m.name) if m else None for m in me.materials]
    if not any(kinds):
        continue
    if not me.uv_layers:
        me.uv_layers.new(name="UVMap")
    uv = me.uv_layers.active.data
    mw = ob.matrix_world
    m3 = mw.to_3x3()
    for p in me.polygons:
        if p.material_index >= len(kinds) or kinds[p.material_index] is None:
            continue
        kind = kinds[p.material_index]
        s = DETAIL_TILES[kind][1]
        n = (m3 @ p.normal).normalized()
        for li, vi in zip(p.loop_indices, p.vertices):
            w = mw @ me.vertices[vi].co
            if abs(n.z) > 0.5:
                u, v = w.x, w.y
            elif abs(n.x) > abs(n.y):
                u, v = w.y, w.z
            else:
                u, v = w.x, w.z
            uv[li].uv = (u / s, v / s)
        _counts[kind] = _counts.get(kind, 0) + 1
for kind in DETAIL_TILES:
    print(f"DETAIL {kind}: {sorted(n for n, k in DETAIL_PLAN.items() if k == kind)}")
print(f"DETAIL faces: {_counts}")

# --- Rovers regulars ---------------------------------------------------------
# Animated barman, bar regulars, table couple, shelf pair and pianist
# (rovers_figures.py). Added after the nav mesh and the detail pass so neither
# sees them; inject-hubs.mjs tags every Fig_* armature to loop its own clip.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if os.environ.get('LOUNGE_PREFIG_BLEND'):   # debug checkpoint: iterate the figure gates on real geometry
    bpy.ops.wm.save_as_mainfile(filepath=os.environ['LOUNGE_PREFIG_BLEND'], copy=True)
import rovers_figures
rovers_figures.build()
# Dinner party in the dining room (dinner_figures.py): six guests, two waiters
# and the chef on one 30-minute loop, plus the prop rig they pass between them.
# LOUNGE_LAX=1 exports even if the dinner gates fail (to iterate on renders); never deploy such a build.
DF.build(strict=os.environ.get("LOUNGE_LAX") != "1")

# --- Export ------------------------------------------------------------------
# Quest has a limited shared graphics-memory budget. Cap source, artwork and
# backdrop textures before export so rebuilding the lounge cannot silently
# restore the previous 295 MiB two-avatar texture footprint.
for image in bpy.data.images:
    width, height = image.size
    if width <= 1024 and height <= 1024:
        continue
    ratio = min(1024 / width, 1024 / height)
    image.scale(max(1, round(width * ratio)), max(1, round(height * ratio)))

# Unsampled: the Rovers regulars' actions are already thinned to the keys
# linear interpolation needs (rovers_figures.py); sampling would refill them.
bpy.ops.export_scene.gltf(filepath=out, export_format='GLB', export_yup=True,
                          export_apply=True, export_extras=False,
                          export_image_format='AUTO', export_force_sampling=False)
print("EXPORTED", out)
