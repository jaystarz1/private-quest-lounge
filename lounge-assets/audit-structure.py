# Audits the exported lounge rather than trusting the build script. Reports
# connected navmesh islands, maps named room probes and waypoints to islands,
# and checks whether expected circulation routes cross visible geometry.
# Usage: blender -b --factory-startup -P audit-structure.py -- <lounge.glb>
import bpy, sys, math
from collections import defaultdict, deque
from mathutils import Vector

src = sys.argv[-1]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=src)
sc = bpy.context.scene
dg = bpy.context.evaluated_depsgraph_get()
nav = bpy.data.objects.get("NavMesh")
if not nav:
    raise RuntimeError("NavMesh missing")

print("=== LEGACY STRUCTURAL MATERIALS ===")
for material in sorted(bpy.data.materials, key=lambda item: item.name.lower()):
    lowered = material.name.lower()
    if any(token in lowered for token in ("porte", "door", "gris_")):
        users = sum(1 for ob in sc.objects if ob.type == "MESH" and material.name in ob.data.materials)
        print(f"{material.name}: objects={users}")

print("=== ART SUPPORT SURFACES ===")
for artwork in sorted((ob for ob in sc.objects if ob.name.startswith("Art_") and not ob.name.endswith("_frame")), key=lambda ob: ob.name):
    normal = (artwork.matrix_world.to_3x3() @ Vector((0, -1, 0))).normalized()
    origin = artwork.matrix_world.translation + normal * 0.08
    hit_desc = "none"
    for _ in range(8):
        hit, loc, _nrm, fi, ob, _matrix = sc.ray_cast(dg, origin, -normal, distance=1.0)
        if not hit:
            break
        if not ob.name.startswith("Art_"):
            mat = ob.data.materials[ob.data.polygons[fi].material_index] if ob.type == "MESH" else None
            hit_desc = f"{ob.name}:{mat.name if mat else '?'}"
            break
        origin = loc - normal * 0.02
    p = artwork.matrix_world.translation
    print(f"{artwork.name:18s} ({p.x:5.2f},{p.y:5.2f},{p.z:4.2f}) -> {hit_desc}")

print("=== FEATURE GEOMETRY ===")
piano_parts = sorted(ob.name for ob in sc.objects if ob.name.startswith(("Piano", "Seat_Pno")))
hot_tub_parts = sorted(ob.name for ob in sc.objects if ob.name.startswith("HotTub"))
hot_tub_seats = sorted(ob.name for ob in sc.objects if ob.name.startswith("Seat_HotTub_"))
hot_tub_pads = sorted(ob.name for ob in sc.objects if ob.name.startswith("HotTubSeatPad_"))
hot_tub_backs = sorted(ob.name for ob in sc.objects if ob.name.startswith("HotTubSeatBack_"))
print(f"former piano space: residual named parts={len(piano_parts)}")
print(f"hot tub: parts={len(hot_tub_parts)} seats={len(hot_tub_seats)}")
if piano_parts:
    raise RuntimeError(f"PIANO REMOVAL GATE failed: {piano_parts}")
piano_residual_faces = []
for ob in (item for item in sc.objects if item.type == "MESH" and item.name != "NavMesh"):
    mw_ob = ob.matrix_world
    for polygon in ob.data.polygons:
        center = mw_ob @ polygon.center
        in_keyboard_volume = -10.4 < center.x < -6.7 and -2.8 < center.y < 0.6 and 0.055 < center.z < 2.62
        in_case_volume = -9.4 < center.x < -4.8 and -4.1 < center.y < -1.8 and 0.055 < center.z < 3.40
        in_shared_mesh_volume = -10.0 < center.x < -7.0 and -3.5 < center.y < -2.0 and 0.30 < center.z < 2.50
        if in_keyboard_volume or in_case_volume or in_shared_mesh_volume:
            piano_residual_faces.append((ob.name, polygon.index))
if piano_residual_faces:
    raise RuntimeError(f"PIANO EMPTY-SPACE GATE failed: residual faces={len(piano_residual_faces)}")
if len(hot_tub_parts) < 20 or len(hot_tub_seats) != 4 or len(hot_tub_pads) != 4 or len(hot_tub_backs) != 4:
    raise RuntimeError(
        f"HOT TUB GATE failed: parts={len(hot_tub_parts)} seats={len(hot_tub_seats)} "
        f"pads={len(hot_tub_pads)} backs={len(hot_tub_backs)}"
    )
for seat_name in hot_tub_seats:
    seat = bpy.data.objects[seat_name]
    seated_eye_z = seat.matrix_world.translation.z + 0.70 + 0.15
    print(f"{seat_name}: target={seat.matrix_world.translation.z:.3f} seated-eye={seated_eye_z:.3f}")
    if not 1.08 <= seated_eye_z <= 1.12:
        raise RuntimeError(f"HOT TUB SEAT HEIGHT GATE failed: {seat_name} seated eye is {seated_eye_z:.3f}")

print("=== BED SEAT AXES ===")
bed_seats = sorted((ob for ob in sc.objects if ob.name.startswith("Seat_Bed_")), key=lambda ob: ob.name)
if len(bed_seats) != 6:
    raise RuntimeError(f"BED SEAT GATE failed: expected 6 upright seats, found {len(bed_seats)}")
for waypoint in bed_seats:
    body_axis = (waypoint.matrix_world.to_3x3() @ Vector((0, 0, 1))).normalized()
    print(f"{waypoint.name:10s}: body=({body_axis.x:5.2f},{body_axis.y:5.2f},{body_axis.z:5.2f})")
    if body_axis.z < 0.90:
        raise RuntimeError(f"BED SEAT AXIS GATE failed: {waypoint.name} is not upright")

# Connected components by shared geometric edge. glTF import can duplicate
# vertex indices at triangulation seams even when positions are coincident.
def vertex_key(index):
    p = mw @ nav.data.vertices[index].co
    return (round(p.x, 3), round(p.y, 3), round(p.z, 3))

mw = nav.matrix_world
edge_faces = defaultdict(list)
for poly in nav.data.polygons:
    verts = list(poly.vertices)
    for a, b in zip(verts, verts[1:] + verts[:1]):
        edge_faces[tuple(sorted((vertex_key(a), vertex_key(b))))].append(poly.index)
adj = defaultdict(set)
for faces in edge_faces.values():
    for a in faces:
        adj[a].update(f for f in faces if f != a)

components = []
face_component = {}
remaining = set(range(len(nav.data.polygons)))
while remaining:
    seed = remaining.pop()
    todo = [seed]
    faces = []
    while todo:
        fi = todo.pop()
        faces.append(fi)
        for ni in adj[fi]:
            if ni in remaining:
                remaining.remove(ni)
                todo.append(ni)
    ci = len(components)
    for fi in faces:
        face_component[fi] = ci
    components.append(faces)

centers = [mw @ p.center for p in nav.data.polygons]
print("=== NAV COMPONENTS ===")
for ci, faces in sorted(enumerate(components), key=lambda item: -len(item[1])):
    pts = [centers[fi] for fi in faces]
    print(
        f"component {ci:3d}: faces={len(faces):5d} "
        f"x={min(p.x for p in pts):6.2f}..{max(p.x for p in pts):6.2f} "
        f"y={min(p.y for p in pts):6.2f}..{max(p.y for p in pts):6.2f} "
        f"z={min(p.z for p in pts):5.2f}..{max(p.z for p in pts):5.2f}"
    )

def nearest_component(point, max_distance=2.0):
    p = Vector(point)
    best = min(range(len(centers)), key=lambda fi: (centers[fi] - p).length_squared)
    dist = (centers[best] - p).length
    return (face_component[best], dist, centers[best]) if dist <= max_distance else (None, dist, centers[best])

rooms = {
    "ground lounge": (-7.5, 6.0, 0.0),
    "ground piano": (-7.0, -1.0, 0.0),
    "ground library": (-4.2, -5.2, 0.0),
    "ground kitchen": (6.5, 1.5, 0.0),
    "ground dining": (9.0, 6.0, 0.0),
    "ground vestibule": (0.0, -7.8, 0.0),
    "ground lobby": (-4.5, -8.2, 0.0),
    "ground SW terrace": (-9.5, -7.0, 0.05),
    "ground SE terrace": (9.2, -7.0, 0.05),
    "upper landing": (2.0, 0.0, 3.5),
    "upper NW bed": (-9.2, 7.2, 3.5),
    "upper NE bed": (8.8, 6.8, 3.5),
    "upper SW bed": (-8.8, -3.8, 3.5),
    "upper gym": (-1.5, -5.0, 3.5),
    "upper east suite": (8.5, -2.8, 3.5),
    "upper sky den": (1.5, -8.5, 3.5),
}
print("=== ROOM TO NAV COMPONENT ===")
for name, point in rooms.items():
    ci, dist, near = nearest_component(point)
    print(f"{name:22s}: component={str(ci):>4s} distance={dist:4.2f} nearest=({near.x:5.2f},{near.y:5.2f},{near.z:4.2f})")

print("=== WAYPOINT TO NAV COMPONENT ===")
for ob in sorted((o for o in sc.objects if o.name.startswith(("Seat_Bed_", "Seat_NW", "Seat_NE", "Seat_SW"))), key=lambda o: o.name):
    ci, dist, near = nearest_component(ob.matrix_world.translation, max_distance=5.0)
    p = ob.matrix_world.translation
    print(f"{ob.name:10s}: component={str(ci):>4s} distance={dist:4.2f} point=({p.x:5.2f},{p.y:5.2f},{p.z:4.2f})")

# Report the exact shortest gaps between the circulation component and the
# occupied rooms. These coordinates are the doorway/landing thresholds the
# builder must join, and make this audit useful when the source model shifts.
component_vertices = defaultdict(set)
for poly in nav.data.polygons:
    ci = face_component[poly.index]
    component_vertices[ci].update(vertex_key(vi) for vi in poly.vertices)

def closest_component_gap(a, b):
    best = None
    for pa in component_vertices[a]:
        va = Vector(pa)
        for pb in component_vertices[b]:
            vb = Vector(pb)
            d = (va - vb).length
            if best is None or d < best[0]:
                best = (d, va, vb)
    return best

room_components = {name: nearest_component(point)[0] for name, point in rooms.items()}
gap_pairs = [
    ("ground main/lobby", room_components["ground lounge"], room_components["ground lobby"]),
    ("ground main/library", room_components["ground lounge"], room_components["ground library"]),
    ("ground main/stair", room_components["ground lounge"], room_components["upper landing"]),
    ("ground main/stair pad", room_components["ground lounge"], 9),
    ("stair pad/stair", 9, room_components["upper landing"]),
    ("stair/upper hall", room_components["upper landing"], 16),
    ("upper hall/NW bed", 16, room_components["upper NW bed"]),
    ("upper hall/NE bed", 16, room_components["upper NE bed"]),
    ("upper hall/SW bed", 16, room_components["upper SW bed"]),
    ("upper hall/gym", 16, room_components["upper gym"]),
    ("upper hall/east suite", 16, room_components["upper east suite"]),
    ("upper hall/sky den", 16, room_components["upper sky den"]),
]
print("=== REQUIRED NAV GAPS ===")
for name, a, b in gap_pairs:
    if a is None or b is None:
        print(f"{name:24s}: missing component")
        continue
    d, pa, pb = closest_component_gap(a, b)
    print(f"{name:24s}: gap={d:4.2f} {a}->{b} ({pa.x:5.2f},{pa.y:5.2f},{pa.z:4.2f}) to ({pb.x:5.2f},{pb.y:5.2f},{pb.z:4.2f})")

def material_name(ob, face_index):
    try:
        poly = ob.data.polygons[face_index]
        mat = ob.data.materials[poly.material_index]
        return mat.name if mat else "?"
    except Exception:
        return "?"

def first_blocker(start, end, height):
    a = Vector((start[0], start[1], height))
    b = Vector((end[0], end[1], height))
    direction = (b - a).normalized()
    remaining = (b - a).length
    origin = a
    for _ in range(20):
        hit, loc, _normal, fi, ob, _matrix = sc.ray_cast(dg, origin + direction * 0.015, direction, distance=remaining)
        if not hit:
            return None
        used = (loc - origin).length + 0.015
        remaining -= used
        if ob.name != "NavMesh" and not ob.name.startswith("View") and ob.name != "RockiesView":
            return (loc, ob.name, material_name(ob, fi))
        origin = loc
    return None

routes = {
    "landing to NW bed": ((-2.5, 0.0), (-8.4, 5.7)),
    "landing to NE bed": ((3.5, 0.0), (8.3, 5.4)),
    "landing to SW bed": ((-2.5, -2.5), (-7.8, -3.7)),
    "landing to gym": ((1.5, -2.5), (-1.2, -4.2)),
    "landing to east suite": ((4.0, -2.5), (8.0, -2.8)),
    "upper hall to sky den": ((2.3, -3.0), (1.5, -8.0)),
    "library to lobby": ((-5.8, -5.8), (-5.8, -7.3)),
    "vestibule to SE walk": ((2.6, -7.5), (5.0, -8.0)),
    "door lobby": ((-1.1, -8.15), (-0.2, -8.15)),
    "door upper NW": ((-5.75, 3.2), (-5.75, 4.1)),
    "door upper NE": ((6.75, 3.4), (6.75, 4.5)),
    "door upper SW": ((-6.7, -1.3), (-7.5, -2.1)),
    "door gym": ((-1.25, -6.05), (-2.1, -6.05)),
    "door east suite": ((7.0, 0.45), (8.0, 0.45)),
    "door sky den": ((-1.2, -8.05), (-0.25, -8.05)),
}
print("=== STRAIGHT ROUTE BLOCKERS ===")
for name, (start, end) in routes.items():
    floor = 3.5 if name.startswith(("landing", "upper", "door upper", "door gym", "door east", "door sky")) else 0.0
    hits = []
    for eye in (0.5, 1.2, 2.0):
        hit = first_blocker(start, end, floor + eye)
        hits.append("clear" if hit is None else f"{hit[1]}:{hit[2]}@({hit[0].x:.2f},{hit[0].y:.2f})")
    print(f"{name:25s}: knee={hits[0]} chest={hits[1]} head={hits[2]}")

# Doors and their surrounding walls must remain visually intact. Navigation
# links may cross them because the lounge intentionally permits pass-through.
restored_door_routes = {
    "lobby": ((-1.1, -8.15), (-0.2, -8.15), 1.2),
    "upper NW": ((-5.75, 3.2), (-5.75, 4.1), 4.7),
    "upper NE": ((6.75, 3.4), (6.75, 4.5), 4.7),
    "upper SW": ((-6.7, -1.3), (-7.5, -2.1), 4.7),
    "gym": ((-1.25, -6.05), (-2.1, -6.05), 4.7),
    "east suite": ((7.0, 0.45), (8.0, 0.45), 4.7),
    "sky den": ((-1.2, -8.05), (-0.25, -8.05), 4.7),
}
print("=== RESTORED DOOR SURFACES ===")
missing_doors = []
for name, (start, end, height) in restored_door_routes.items():
    hit = first_blocker(start, end, height)
    print(f"{name:12s}: {'missing' if hit is None else hit[1] + ':' + hit[2]}")
    if hit is None:
        missing_doors.append(name)
if missing_doors:
    raise RuntimeError(f"RESTORED DOOR GATE failed: missing visual surfaces at {missing_doors}")

print("DONE")
