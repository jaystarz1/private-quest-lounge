# Converts penthouse-src.glb (Sketchfab "Luxury Penthouse", CC BY-NC-SA) into
# the Hubs-ready lounge environment: recentres the main floor onto the origin,
# decimates to a Quest-2 triangle budget, raycasts a walkable-grid NavMesh,
# and adds the Hubs anchor nodes (spawns, seats, TV/monitor screens, view
# backdrop). MOZ_hubs_components are injected afterwards by inject-hubs.mjs.
#
# Usage: blender -b --factory-startup -P build-penthouse.py -- <src.glb> <out.glb> <viewimg>
import bpy, bmesh, sys, math
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
REGION_MATS = {}
def recolor_region(x1, x2, y1, y2, z1, z2, hexcol, rough=0.85, metal=0.0, label=None, only_mats=None):
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
        sel = [p.index for p in ob.data.polygons
               if p.material_index in okidx
               and x1 < (mw @ p.center).x < x2 and y1 < (mw @ p.center).y < y2 and z1 < (mw @ p.center).z < z2]
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
M_BRASS  = mk('LobbyBrass', '8C6F3F', 0.35, 0.9)
M_STEEL  = mk('LiftSteel',  '6E6A63', 0.3, 0.9)
M_DECK   = mk('DeckWood',   '6E4E32', 0.68)
M_RAIL   = mk('RailDark',   '23262B', 0.4, 0.6)
M_CUSH   = mk('LoungeCush', '3E5C54', 0.85)
M_OAK    = mk('DenOak',     '5C4630', 0.6)
M_WINE   = mk('RugWine',    '6E2B33', 0.95)
M_GLOW   = mk('WarmGlow',   '2A2320', 0.5)
_gb = M_GLOW.node_tree.nodes['Principled BSDF']
if _gb.inputs.get('Emission Color'):
    _gb.inputs['Emission Color'].default_value = (1.0, 0.82, 0.55, 1)
    _gb.inputs['Emission Strength'].default_value = 2.5
M_GLASSP = bpy.data.materials.get('fake_mat_255_255_255_32')  # model's own glass

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
recolor_region(-11.7, 11.7, -10.1, 10.1, -0.3, 6.7, "8A8378", rough=0.85,
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
add_box("LobbyFloor", -4.10, -8.19, 0.02, 3.52, 1.57, 0.02, M_STONE)
add_box("LobbyCeil",  -4.10, -8.19, 2.98, 3.52, 1.57, 0.04, M_WALL)
add_box("LobbyGlow",  -4.10, -8.19, 2.93, 1.30, 0.45, 0.015, M_GLOW)
# North wall: solid runs with one doorway aligned to the real passage between
# the library block's west end and the piano room (open x -6.9..-5.3). Wall
# face sits just south of the noir library face and hides it.
add_box("LobbyWallN1", -7.11, -6.57, 1.475, 0.51, 0.03, 1.475, M_WALL)
add_box("LobbyWallN2", -3.04, -6.57, 1.475, 2.46, 0.03, 1.475, M_WALL)
add_box("LobbyDoorHead", -6.05, -6.57, 2.775, 0.55, 0.03, 0.175, M_WALL)
# South wall (elevator bank), full run.
add_box("LobbyWallS", -4.10, -9.73, 1.475, 3.52, 0.03, 1.475, M_WALL)
# East wall against the vestibule; west wall with a doorway to the SW terrace.
# East wall has a real 1.26 m doorway into the vestibule.
add_box("LobbyWallE_N", -0.60, -7.07, 1.475, 0.03, 0.45, 1.475, M_WALL)
add_box("LobbyWallE_S", -0.60, -9.27, 1.475, 0.03, 0.49, 1.475, M_WALL)
add_box("LobbyWallE_Head", -0.60, -8.15, 2.785, 0.03, 0.63, 0.165, M_WALL)
# Complete wood door in the former lobby opening. It is intentionally visual
# only; the linked navigation surface preserves the lounge's pass-through.
add_box("LobbyDoorPanel", -0.60, -8.15, 1.20, 0.035, 0.58, 1.20, M_OAK)
add_box("LobbyDoorJambN", -0.62, -7.53, 1.32, 0.055, 0.045, 1.32, M_DARK)
add_box("LobbyDoorJambS", -0.62, -8.77, 1.32, 0.055, 0.045, 1.32, M_DARK)
add_box("LobbyDoorJambTop", -0.62, -8.15, 2.58, 0.055, 0.66, 0.06, M_DARK)
add_box("LobbyDoorHandle", -0.555, -7.72, 1.12, 0.025, 0.025, 0.07, M_BRASS)
add_box("LobbyWallW1", -7.62, -7.435, 1.475, 0.03, 0.815, 1.475, M_WALL)
add_box("LobbyWallW2", -7.62, -9.505, 1.475, 0.03, 0.255, 1.475, M_WALL)
add_box("LobbyWallWHead", -7.62, -8.775, 2.775, 0.03, 0.475, 0.175, M_WALL)
# Baseboards on the long walls.
add_box("LobbyBaseN", -2.765, -6.605, 0.10, 2.185, 0.012, 0.06, M_DARK)
add_box("LobbyBaseS", -4.10, -9.695, 0.10, 3.52, 0.012, 0.06, M_DARK)
# Elevator bank: two brass-framed cars with steel leaves + glow slits.
for i, ex in enumerate((-6.1, -3.9)):
    add_box(f"LiftFrame{i}", ex, -9.705, 1.18, 0.75, 0.022, 1.18, M_BRASS)
    add_box(f"LiftRecess{i}", ex, -9.72, 1.10, 0.62, 0.015, 1.10, M_DARK)
    add_box(f"LiftLeafL{i}", ex - 0.30, -9.70, 1.08, 0.285, 0.014, 1.08, M_STEEL)
    add_box(f"LiftLeafR{i}", ex + 0.30, -9.70, 1.08, 0.285, 0.014, 1.08, M_STEEL)
    add_box(f"LiftHall{i}", ex, -9.695, 2.46, 0.30, 0.014, 0.045, M_GLOW)
add_box("LiftCall", -5.0, -9.71, 1.08, 0.045, 0.014, 0.09, M_BRASS)
add_box("LiftCallDot", -5.0, -9.695, 1.08, 0.018, 0.012, 0.018, M_GLOW)
# Console + mirror on the north wall; runner on the stone.
add_box("LobbyConsole", -3.6, -6.85, 0.85, 0.50, 0.16, 0.018, M_DARK)
add_box("LobbyConsL", -4.02, -6.85, 0.425, 0.02, 0.13, 0.425, M_DARK)
add_box("LobbyConsR", -3.18, -6.85, 0.425, 0.02, 0.13, 0.425, M_DARK)
add_box("LobbyMirrorFrame", -3.6, -6.635, 1.72, 0.48, 0.012, 0.60, M_BRASS)
mirror = mk('MirrorGlass', '1A1D22', 0.05, 0.9)
add_box("LobbyMirror", -3.6, -6.62, 1.72, 0.44, 0.008, 0.56, mirror)
add_box("LobbyRug", -4.1, -8.19, 0.048, 2.60, 0.55, 0.008, M_WINE)
# Topiary pair in the lobby corners.
def hedge(name, hx, hy, hz):
    add_box(name + "Pot", hx, hy, hz + 0.20, 0.24, 0.24, 0.20, M_RAIL)
    fol = bpy.data.materials.get('Foliage_1') or M_CUSH
    add_box(name + "Top", hx, hy, hz + 0.60, 0.21, 0.21, 0.20, fol)
hedge("LobbyHedgeW", -7.15, -9.35, 0.04)
hedge("LobbyHedgeE", -1.15, -9.35, 0.04)

# --- SW terrace: accessible four-person hot tub ------------------------------
add_box("DeckSW", -9.57, -7.10, 0.07, 1.85, 2.66, 0.03, M_DECK)
if M_GLASSP:
    add_box("ParaSWglassW", -11.40, -7.10, 0.625, 0.015, 2.66, 0.525, M_GLASSP)
    add_box("ParaSWglassS", -9.57, -9.74, 0.625, 1.85, 0.015, 0.525, M_GLASSP)
add_box("ParaSWrailW", -11.40, -7.10, 1.17, 0.03, 2.66, 0.025, M_RAIL)
add_box("ParaSWrailS", -9.57, -9.74, 1.17, 1.85, 0.03, 0.025, M_RAIL)
add_box("ParaSWcurbW", -11.40, -7.10, 0.07, 0.03, 2.66, 0.035, M_RAIL)
add_box("ParaSWcurbS", -9.57, -9.74, 0.07, 1.85, 0.03, 0.035, M_RAIL)
M_TUB = mk('HotTubShell', 'E8E1D4', 0.38)
M_TUB_INNER = mk('HotTubInner', '24444A', 0.48)
M_WATER = mk('HotTubWater', '48B8C5', 0.08, 0.05)
water_bsdf = M_WATER.node_tree.nodes['Principled BSDF']
water_bsdf.inputs['Alpha'].default_value = 0.78
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
hedge("TerrSWhedge1", -8.2, -4.75, 0.04)
hedge("TerrSWhedge2", -11.0, -4.75, 0.04)
for i, (bx, by) in enumerate(((-11.15, -9.45), (-7.95, -9.45), (-11.15, -4.75))):
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
hedge("TerrSEhedge1", 8.0, -4.75, 0.04)
hedge("TerrSEhedge2", 9.5, -4.75, 0.04)
hedge("TerrSEhedge3", 11.0, -4.75, 0.04)
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
add_box("DenGlow", 1.5, -8.45, 6.20, 0.90, 0.35, 0.014, M_GLOW)
# Green on the flanking roof ledges, seen through the den's glass walls.
hedge("LedgeW1", -1.5, -7.8, DEN_Z)
hedge("LedgeW2", -1.5, -9.2, DEN_Z)
hedge("LedgeE1", 4.2, -8.5, DEN_Z)

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

def connect_nav_regions(name, point_a, point_b, threshold, radius=1.0):
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
    try:
        bm.faces.new((a0, a1, b1, b0))
    except ValueError as exc:
        raise RuntimeError(f"NAV LINK {name} could not bridge boundary edges: {exc}")
    print(f"NAV LINK {name}: edge gap {gap:.2f} m")

NAV_LINKS = [
    # name, side A probe, side B probe, doorway/landing threshold, search radius
    ("ground-lobby", (-7.5, 6.0, 0.0), (-4.5, -8.2, 0.05), (-0.64, -8.15, 0.03), 2.5),
    ("ground-stair-pad", (-7.5, 6.0, 0.0), (3.0, -1.0, 0.03), (3.62, -1.55, 0.03), 0.8),
    ("stair-pad-flight", (3.0, -1.0, 0.03), (2.0, -1.5, 0.30), (2.50, -1.55, 0.12), 0.8),
    ("stair-landing", (1.5, -2.05, 3.25), (0.0, -3.5, 3.50), (1.50, -2.05, 3.38), 0.8),
    ("upper-nw-bedroom", (0.0, -3.5, 3.50), (-8.0, 5.0, 3.53), (-5.75, 3.58, 3.52), 0.8),
    ("upper-ne-bedroom", (0.0, -3.5, 3.50), (8.0, 5.0, 3.50), (6.75, 3.95, 3.50), 0.8),
    ("upper-sw-bedroom", (0.0, -3.5, 3.50), (-8.0, -3.0, 3.50), (-7.10, -1.68, 3.50), 0.8),
    ("upper-gym", (0.0, -3.5, 3.50), (-1.5, -5.0, 3.54), (-1.62, -6.05, 3.52), 0.8),
    ("upper-east-suite", (0.0, -3.5, 3.50), (8.5, -2.8, 3.50), (7.50, 0.45, 3.50), 0.8),
    ("upper-sky-den", (0.0, -3.5, 3.50), (1.5, -8.5, 3.53), (-0.75, -8.05, 3.52), 0.8),
]
for link_args in NAV_LINKS:
    connect_nav_regions(*link_args)

# name, x, y, waypoint_z, yaw_deg, floor_z, island
# yaw: avatar facing after glTF export (empty -Y): 0=-y  90=+x  180=+y  -90=-x
SEATS = [
    # Lounge sofa (north arm, facing the room)
    ("Seat_A1", -9.6, 8.15, 0.75, 0, 0.0, True),
    ("Seat_A2", -8.6, 8.15, 0.75, 0, 0.0, True),
    ("Seat_A3", -7.6, 8.15, 0.75, 0, 0.0, True),
    # Bar stools
    ("Seat_B1", 9.28, -0.41, 0.95, 0, 0.0, True),
    ("Seat_B2", 9.88, -0.41, 0.95, 0, 0.0, True),
    ("Seat_B3", 10.49, -0.41, 0.95, 0, 0.0, True),
    # Lounge ottoman, facing the TV wall
    ("Seat_Ott", -9.40, 4.55, 0.65, -90, 0.0, True),
    # Formal dining — eight lacquer-red qing chairs
    ("Seat_D1", 7.98, 4.75, 0.75, 90, 0.0, True),
    ("Seat_D2", 7.98, 5.44, 0.75, 90, 0.0, True),
    ("Seat_D3", 7.98, 6.46, 0.75, 90, 0.0, True),
    ("Seat_D4", 7.98, 7.34, 0.75, 90, 0.0, True),
    ("Seat_D5", 9.62, 4.95, 0.75, -90, 0.0, True),
    ("Seat_D6", 9.62, 5.70, 0.75, -90, 0.0, True),
    ("Seat_D7", 9.62, 6.41, 0.75, -90, 0.0, True),
    ("Seat_D8", 9.62, 7.35, 0.75, -90, 0.0, True),
    # Terrace dining table
    ("Seat_T1", 4.66, 5.49, 0.78, -90, 0.0, True),
    ("Seat_T2", 4.66, 6.19, 0.78, -90, 0.0, True),
    ("Seat_T3", 4.66, 6.97, 0.78, -90, 0.0, True),
    ("Seat_T4", 4.66, 7.60, 0.78, -90, 0.0, True),
    ("Seat_T5", 3.40, 7.07, 0.78, 90, 0.0, True),
    ("Seat_T6", 3.40, 7.63, 0.78, 90, 0.0, True),
    ("Seat_T7", 3.40, 5.49, 0.78, 90, 0.0, True),
    ("Seat_T8", 3.40, 6.19, 0.78, 90, 0.0, True),
    # Terrace L-sofa (west arm faces the view band, south arm faces north)
    ("Seat_P1", -3.55, 5.80, 0.92, 90, 0.0, True),
    ("Seat_P2", -3.55, 6.90, 0.92, 90, 0.0, True),
    ("Seat_P3", -3.55, 7.95, 0.92, 90, 0.0, True),
    ("Seat_P4", -2.60, 5.50, 0.92, 180, 0.0, True),
    ("Seat_P5", -1.30, 5.50, 0.92, 180, 0.0, True),
    # Library reading group
    ("Seat_L1", -5.05, -4.85, 0.78, 90, 0.0, True),
    ("Seat_L2", -4.90, -5.90, 0.78, 90, 0.0, True),
    ("Seat_L3", -3.90, -6.10, 0.78, 180, 0.0, True),
    ("Seat_L4", -3.10, -4.95, 0.78, -90, 0.0, True),
    # Beds: two upright seated spots each plus a foot-edge seat. These use a
    # true seated eye height in the client and always preserve world-up.
    ("Seat_Bed_NW1", -8.65, 6.85, 4.30, 90, 3.52, False),
    ("Seat_Bed_NW2", -8.65, 7.75, 4.30, 90, 3.52, False),
    ("Seat_NW", -8.75, 7.30, 4.38, 90, 3.52, False),
    ("Seat_Bed_NE1", 8.35, 5.65, 4.30, 0, 3.52, False),
    ("Seat_Bed_NE2", 9.35, 5.65, 4.30, 0, 3.52, False),
    ("Seat_NE", 8.85, 5.75, 4.38, 0, 3.52, False),
    ("Seat_Bed_SW1", -8.15, -3.35, 4.30, 90, 3.52, False),
    ("Seat_Bed_SW2", -8.15, -4.20, 4.30, 90, 3.52, False),
    ("Seat_SW", -8.20, -3.80, 4.38, 90, 3.52, False),
    # SW terrace hot tub, four submerged seats facing the centre. The client
    # uses a 0.70 m seated eye height for these instead of its standing 1.60 m.
    ("Seat_HotTub_N1", -10.28, -6.15, 0.25, 0, 0.05, False),
    ("Seat_HotTub_N2", -9.22, -6.15, 0.25, 0, 0.05, False),
    ("Seat_HotTub_S1", -10.28, -8.15, 0.25, 180, 0.05, False),
    ("Seat_HotTub_S2", -9.22, -8.15, 0.25, 180, 0.05, False),
    # SE terrace bistro pair
    ("Seat_E1", 9.50, -6.55, 0.75, 0, 0.05, True),
    ("Seat_E2", 9.50, -8.05, 0.75, 180, 0.05, True),
    # Sky den sofa
    ("Seat_S1", 0.60, -9.22, 4.31, 180, 3.53, True),
    ("Seat_S2", 1.40, -9.22, 4.31, 180, 3.53, True),
    ("Seat_S3", 2.20, -9.22, 4.31, 180, 3.53, True),
]
for _, sx, sy, _, _, fz, isl in SEATS:  # floor-level landing islands inside seat footprints
    if not isl:
        continue
    h = 0.24
    vs = [bm.verts.new(p) for p in ((sx-h, sy-h, fz+0.002), (sx+h, sy-h, fz+0.002), (sx+h, sy+h, fz+0.002), (sx-h, sy+h, fz+0.002))]
    bm.faces.new(vs)

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
for name, sx, sy, sz, yawdeg, _, _ in SEATS:
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
bsdf.inputs['Roughness'].default_value = 0.3
# West-wall black panel, facing east into the lounge (rotate -y normal to +x)
tv = plane("TVScreen", 2.6, 1.5, -11.14, 6.8, 1.9, 0, dark)
tv.rotation_euler = (0, 0, math.pi / 2)
mon = plane("MonitorScreen", 1.06, 0.6, 9.9, -0.78, 1.25, 0, dark)
mon.rotation_euler = (0, 0, math.pi)  # flip to face +y (toward the bar stools)

# --- Gallery: public-domain masters on the perimeter walls -------------------
# (name, image, x, y, center z, height, facing) — facing: +x|-x|+y|-y
import os
ART_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "art")
YAWS = {"+x": math.pi / 2, "-x": -math.pi / 2, "+y": math.pi, "-y": 0.0}
GALLERY = [
    # Group of Seven — lounge, west wall
    ("Art_JackPine", "jackpine.jpg", -11.18, 9.3, 1.7, 1.3, "+x"),
    # West Wind: lobby east wall, facing the elevators
    ("Art_WestWind", "westwind.jpg", -0.64, -8.2, 1.55, 1.1, "-x"),
    # Sunrise + Tangled Garden: solid north wall of the arrival lobby. Their
    # former hall positions were patio glass, not a wall.
    ("Art_Sunrise", "sunrise.jpg", -4.70, -6.54, 2.08, 0.85, "-y"),
    ("Art_Starry", "starrynight.jpg", -11.18, -4.2, 1.6, 1.2, "+x"),
    # Lobby north wall + the covered walk's facade wall outside
    ("Art_Moulin", "moulin.jpg", -1.9, -6.66, 1.6, 1.15, "-y"),
    ("Art_Wave", "wave.jpg", 5.3, -6.30, 1.55, 1.1, "-y"),
    # Dining + bar, east wall
    ("Art_Kiss", "kiss.jpg", 11.18, 7.0, 1.7, 1.5, "-x"),
    ("Art_Sunflowers", "sunflowers.jpg", 11.18, 4.3, 1.6, 1.3, "-x"),
    ("Art_Cafe", "cafeterrace.jpg", 11.18, -2.6, 1.5, 1.3, "-x"),
    ("Art_Tangled", "tangledgarden.jpg", -4.70, -6.54, 0.92, 0.85, "-y"),
]
framemat = mat_frame = bpy.data.materials.new('ArtFrame')
mat_frame.use_nodes = True
fb = mat_frame.node_tree.nodes['Principled BSDF']
fb.inputs['Base Color'].default_value = (0.02, 0.018, 0.015, 1)
fb.inputs['Roughness'].default_value = 0.4
# Probe each wall spot from 3 m inside the room and hang the piece 4 cm in
# front of whatever surface is actually there (walls, panels, wardrobes).
DIRV = {"+x": Vector((-1, 0, 0)), "-x": Vector((1, 0, 0)), "+y": Vector((0, -1, 0)), "-y": Vector((0, 1, 0))}
dga = bpy.context.evaluated_depsgraph_get()
probed = []
for name, fn, ax, ay, az, h, facing in GALLERY:
    d = DIRV[facing]
    origin = Vector((ax, ay, az)) - d * 3.0
    ok, loc, nrm, fi, ob, mw = sc.ray_cast(dga, origin, d, distance=4.5)
    support_mat = None
    if ok and ob.type == 'MESH' and fi < len(ob.data.polygons):
        poly = ob.data.polygons[fi]
        if poly.material_index < len(ob.data.materials):
            support_mat = ob.data.materials[poly.material_index]
    if support_mat and support_mat.name == 'fake_mat_255_255_255_32':
        raise RuntimeError(f"GALLERY SUPPORT GATE failed: {name} resolves to glass on {ob.name}")
    # Accept the probed surface only if it is an actual vertical wall close to
    # the intended spot — otherwise art ends up floating on curtains/furniture.
    if ok and abs(nrm.z) < 0.4 and (loc - Vector((ax, ay, az))).length < 0.9:
        pos = loc - d * 0.025
        ax, ay = pos.x, pos.y
    probed.append((name, fn, ax, ay, az, h, facing))
GALLERY = probed
for name, fn, ax, ay, az, h, facing in GALLERY:
    img = bpy.data.images.load(os.path.join(ART_DIR, fn))
    aspect = img.size[0] / img.size[1]
    w = h * aspect
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

# Four directional backdrop planes, one emissive material each. The baked
# textures are 2048-wide placeholders from lounge-assets/bake/ — the runtime
# view switcher swaps every wall's emissiveMap to the matching full-res
# day/dusk view, so all windows stay in the same scene but each compass
# direction shows what it should: Central Park north, East River east,
# Hudson west, Midtown south.
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
plane("RockiesView", 26, 13, 0, 10.9, 4.0, 0, viewmat('RockiesBackdrop', viewimg))
for wname, wx, wy, wyaw, mname, img in (
        ("ViewEast", 13.0, 0.0, -math.pi / 2, 'EastBackdrop', 'day-east.jpg'),
        ("ViewWest", -13.0, 0.0, math.pi / 2, 'WestBackdrop', 'day-west.jpg'),
        ("ViewSouth", 0.0, -12.5, math.pi, 'SouthBackdrop', 'day-south.jpg')):
    wp = plane(wname, 30, 13, wx, wy, 4.0, 0,
               viewmat(mname, os.path.join(BAKE_DIR, img)))
    wp.rotation_euler = (0, 0, wyaw)

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
