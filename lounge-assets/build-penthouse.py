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

def cut_opening(x1, x2, y1, y2, z1, z2, label, name_prefix=("Object_",)):
    """Carve a rectangular hole through source wall sheets: bisect every face
    that straddles the box (plus its edge neighbours, so the cut edge is
    shared) on the box's x/y/z bounds, then delete the pieces inside."""
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
                if (max(w.x for w in ws) > x1 and min(w.x for w in ws) < x2 and max(w.y for w in ws) > y1
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
            if x1 < c.x < x2 and y1 < c.y < y2 and z1 < c.z < z2:
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
for i, (tx, ty) in enumerate(((-10.55, -8.60), (-10.15, -8.60))):
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
for x in (8.10,10.80):
    add_box("CafeJoineryJamb",x,-4.53,1.83,.055,.075,.79,M_CAFE_GREEN)
    tex_box("CafeStoneReveal",x,-3.80,1.87,.025,.72,.75,M_CAFE_STONE)
tex_box("CafeStoneLintelReveal",9.45,-3.80,2.62,1.36,.72,.025,M_CAFE_STONE)
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
for x in (6.49,7.75):
    tex_box("CafeStoneDoorReveal",x,-3.69,1.38,.03,.93,1.28,M_CAFE_STONE)
    add_box("CafeJoineryDoorJamb",x,-4.57,1.38,.045,.045,1.28,M_CAFE_GREEN)
tex_box("CafeStoneDoorHead",7.12,-3.69,2.68,.66,.93,.025,M_CAFE_STONE)
tex_box("CafeStoneDoorThreshold",7.12,-3.69,.077,.60,.93,.023,M_CAFE_STONE)
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

# --- Seats: authored spots, snapped onto the real seat surfaces --------------
# name, x, y, expected seat-surface z, yaw_deg
# yaw: avatar facing after glTF export (empty -Y): 0=-y  90=+x  180=+y  -90=-x
# The waypoint is placed ON the cushion/mattress/pad surface; the client adds
# a 0.60 m seated eye height (0.70 in the tub) plus its 0.15 m occupied lift.
SEATS = [
    # Lounge sofa (north arm, facing the room)
    ("Seat_A1", -9.6, 8.15, 0.43, 0),
    ("Seat_A2", -8.6, 8.15, 0.43, 0),
    ("Seat_A3", -7.6, 8.15, 0.43, 0),
    # Bar stools
    ("Seat_B1", 9.28, -0.41, 0.76, 0),
    ("Seat_B2", 9.88, -0.41, 0.76, 0),
    ("Seat_B3", 10.49, -0.41, 0.76, 0),
    # Lounge ottoman, facing the TV wall
    ("Seat_Ott", -9.40, 4.55, 0.36, -90),
    # Media sofa directly across from the wall TV (TV centre y 6.8), one spot
    # per cushion (seams at y ~5.7 and ~6.7), all facing the screen.
    ("Seat_TV1", -6.65, 5.20, 0.43, -90),
    ("Seat_TV2", -6.65, 6.20, 0.43, -90),
    ("Seat_TV3", -6.65, 7.20, 0.43, -90),
    # Formal dining — eight Qing chairs
    ("Seat_D1", 7.98, 4.75, 0.456, 90),
    ("Seat_D2", 7.98, 5.44, 0.456, 90),
    ("Seat_D3", 7.98, 6.46, 0.456, 90),
    ("Seat_D4", 7.98, 7.34, 0.456, 90),
    ("Seat_D5", 9.62, 4.95, 0.456, -90),
    ("Seat_D6", 9.62, 5.70, 0.456, -90),
    ("Seat_D7", 9.62, 6.41, 0.456, -90),
    ("Seat_D8", 9.62, 7.35, 0.456, -90),
    # Terrace dining table (eight wicker chairs)
    ("Seat_T1", 4.66, 5.49, 0.48, -90),
    ("Seat_T2", 4.66, 6.19, 0.48, -90),
    ("Seat_T3", 4.66, 6.97, 0.48, -90),
    ("Seat_T4", 4.66, 7.60, 0.48, -90),
    ("Seat_T5", 3.40, 7.07, 0.48, 90),
    ("Seat_T6", 3.40, 7.63, 0.48, 90),
    ("Seat_T7", 3.40, 5.49, 0.48, 90),
    ("Seat_T8", 3.40, 6.19, 0.48, 90),
    # Terrace L-sofa (west arm faces the view band, south arm faces north)
    ("Seat_P1", -3.55, 5.80, 0.36, 90),
    ("Seat_P2", -3.55, 6.90, 0.36, 90),
    ("Seat_P3", -3.55, 7.95, 0.36, 90),
    ("Seat_P4", -2.60, 5.50, 0.36, 180),
    ("Seat_P5", -1.30, 5.50, 0.36, 180),
    # Library reading pair (instanced Qing chairs)
    ("Seat_L1", -4.55, -5.30, 0.456, 90),
    ("Seat_L2", -3.55, -5.30, 0.456, -90),
    # Beds: two upright seated spots each, on the mattress facing away from
    # the headboard (mattress surfaces from probe-mattress.py).
    ("Seat_Bed_NW1", -9.70, 6.90, 4.15, 90),
    ("Seat_Bed_NW2", -9.70, 7.85, 4.15, 90),
    ("Seat_Bed_NE1", 8.15, 7.40, 4.15, 180),
    ("Seat_Bed_NE2", 9.15, 7.40, 4.15, 180),
    ("Seat_Bed_SW1", -9.30, -3.60, 4.15, 180),
    ("Seat_Bed_SW2", -8.45, -3.60, 4.15, 180),
    # SW terrace hot tub: four submerged seats facing the centre (not snapped).
    # Water surface is z 0.555; with the client's 0.70 m tub eye height and
    # 0.15 m occupied lift the eye lands at 0.95, i.e. 0.40 m above the water,
    # so the water reaches a seated avatar's chest.
    ("Seat_HotTub_N1", -10.28, -6.15, 0.10, 0),
    ("Seat_HotTub_N2", -9.22, -6.15, 0.10, 0),
    ("Seat_HotTub_S1", -10.28, -8.15, 0.10, 180),
    ("Seat_HotTub_S2", -9.22, -8.15, 0.10, 180),
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

# --- NavMesh: shared-lattice grid over the main floor ------------------------
# Cell walkable when a down-ray finds floor near z=0 and 1.7 m headroom above.
RES = 0.25
X1, X2, Y1, Y2 = -11.5, 11.5, -9.8, 9.8
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
    "ground vestibule": (0.2, -7.6, 0.0),
    "sw terrace deck": (-7.95, -6.3, 0.07),
    "sw terrace pocket": (-6.3, -6.1, 0.10),
    "spa open wall": (-7.62, -7.5, 0.10),
    "spa seating approach": (-4.6, -7.25, 0.10),
    "patio door threshold": (-8.2, -4.60, 0.10),
    "se terrace deck": (8.5, -6.0, 0.07),
    "upper NW dressing": (-9.2, -0.3, 3.5),
    "upper east bath": (9.9, 2.6, 3.5),
    "upper NW closet": (-9.2, 2.6, 3.5),
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
empty("Light_G", 1.5, -8.45, 5.85)   # sky den
empty("Light_H", -4.1, -8.15, 2.5)   # elevator lobby
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
    # Group of Seven: Jack Pine over the lounge fireplace (chimney breast).
    ("Art_JackPine", "jackpine.jpg", [("+x", -10.44, 4.04, 3.4, 4.7, 2.15)], 1.0),
    # Starry Night on the piano corner's west wall (first clean run).
    ("Art_Starry", "starrynight.jpg", [("+x", -10.96, -3.0, -5.6, 0.6, 1.6)], 1.2),
    # Lobby north wall, both at eye level, either side of the runner.
    ("Art_Sunrise", "sunrise.jpg", [("-y", -6.57, -4.6, -5.25, -3.7, 1.6)], 0.95),
    ("Art_Moulin", "moulin.jpg", [("-y", -6.57, -2.55, -3.6, -1.42, 1.6)], 1.15),
    # West Wind on the lobby's west wall north of the terrace door, facing in.

    # Covered walk facade wall outside.
    ("Art_Wave", "wave.jpg", [("+y", -9.55, 2.75, 1.95, 3.58, 1.55)], .9),
    ("Art_Paris1946", "paris-1946.png", [("-y", -6.30, 4.35, 3.4, 5.0, 1.65)], 1.14),
    ("Art_Paris1948", "paris-1948.png", [("-y", -6.30, 5.50, 4.95, 6.08, 1.65)], 1.14),
    # Dining + bar, east wall.
    ("Art_Kiss", "kiss.jpg", [("-x", 11.18, 7.0, 6.0, 8.6, 1.7)], 1.5),
    ("Art_Sunflowers", "sunflowers.jpg", [("-x", 11.18, 4.3, 2.8, 5.7, 1.6)], 1.3),
    # Cafe Terrace: the bar's east wall is cabinets and blinds end to end, so
    # fall back to the vestibule's south wall, then the bar wall north of the
    # island, then the dining wall between the Kiss and the north glass.
    ("Art_Cafe", "cafeterrace.jpg", [("-x", 11.18, -2.6, -4.3, -1.1, 1.5),
                                     ("+y", -9.55, 1.2, -0.2, 2.8, 1.55),
                                     ("-x", 11.18, 1.5, -0.2, 3.0, 1.5),
                                     ("-x", 11.18, 8.6, 7.9, 9.4, 1.6)], 1.3),
    # Tangled Garden in the sky den (north wall).
    ("Art_Tangled", "tangledgarden.jpg", [("-y", -7.10, 2.6, 0.3, 3.7, 5.05)], 0.85),
]
CENTRE_ON_WALL = {"Art_JackPine"}
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
# flat planes meeting at 90-degree corners. Radius 17 m clears the building's
# corners (15.4 m); z -4..13 keeps the old planes' vertical coverage. UV u=0
# at the NW corner, increasing clockwise (north, east, south, west quadrants),
# so the panorama reads un-mirrored from inside. The bake texture is a 1024
# placeholder; the runtime view switcher swaps in the 8K day/dusk panorama.
def view_cylinder(name, mat, radius=17.0, z0=-4.0, z1=13.0, segs=72):
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

bpy.ops.export_scene.gltf(filepath=out, export_format='GLB', export_yup=True,
                          export_apply=True, export_extras=False,
                          export_image_format='AUTO')
print("EXPORTED", out)
