# Global coplanar-overlap probe: finds clusters of faces that lie in (almost)
# the same axis-aligned plane and overlap in area, i.e. z-fighting candidates.
# Every source material is doubleSided, so ANY two coplanar overlapping faces
# strobe against each other regardless of winding.
# Usage: blender -b --factory-startup -P probe-coplanar-global.py -- <model.glb>
import bpy, sys, math
from collections import defaultdict
from mathutils import Vector

src = sys.argv[-1]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=src)
sc = bpy.context.scene

AXES = [Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))]
AXIS_NAMES = "XYZ"
ALIGN_DOT = 0.985       # face normal within ~10 deg of an axis
PLANE_STEP = 0.004      # 4 mm plane-offset buckets
GAP_MAX = 0.006         # faces within 6 mm along the normal can strobe
MIN_FACE_AREA = 0.0004  # ignore specks under 4 cm^2

# Ignore authored planes that intentionally sit proud of walls.
SKIP_PREFIXES = ("TVScreen", "NavMesh", "Spawn", "Seat_", "RockiesView",
                 "ViewEast", "ViewWest", "ViewSouth", "RockiesBackdrop",
                 "Art_", "Monitor")

faces = []  # (axis, offset, umin, umax, vmin, vmax, area, objname, matname, center)
for ob in [o for o in sc.collection.all_objects if o.type == 'MESH']:
    if ob.name.startswith(SKIP_PREFIXES):
        continue
    mw = ob.matrix_world
    nmat = mw.to_3x3()
    mats = [m.name if m else '?' for m in ob.data.materials] or ['?']
    for p in ob.data.polygons:
        n = (nmat @ p.normal)
        if n.length < 1e-6:
            continue
        n = n.normalized()
        axis = None
        for ai, av in enumerate(AXES):
            if abs(n.dot(av)) >= ALIGN_DOT:
                axis = ai
                break
        if axis is None:
            continue
        c = mw @ p.center
        verts = [mw @ ob.data.vertices[vi].co for vi in p.vertices]
        # in-plane 2D extents (the two axes other than `axis`)
        u_ax, v_ax = [i for i in range(3) if i != axis]
        us = [v[u_ax] for v in verts]
        vs = [v[v_ax] for v in verts]
        umin, umax, vmin, vmax = min(us), max(us), min(vs), max(vs)
        area = (umax - umin) * (vmax - vmin)
        if area < MIN_FACE_AREA:
            continue
        faces.append((axis, c[axis], umin, umax, vmin, vmax, area, ob.name, mats[min(p.material_index, len(mats)-1)], (round(c.x,2), round(c.y,2), round(c.z,2))))

# Bucket by (axis, plane offset). Compare each bucket against itself and the
# next bucket so pairs straddling a bucket edge are still found.
buckets = defaultdict(list)
for f in faces:
    buckets[(f[0], int(math.floor(f[1] / PLANE_STEP)))].append(f)

def overlap_1d(a1, a2, b1, b2):
    return min(a2, b2) - max(a1, b1)

clusters = defaultdict(lambda: [0.0, set(), set(), [1e9,1e9,1e9,-1e9,-1e9,-1e9], 0])
for (axis, b), lst in buckets.items():
    for nb in (b, b + 1):
        other = buckets.get((axis, nb), [])
        for i, f in enumerate(lst):
            start = i + 1 if nb == b else 0
            for g in (other[start:] if nb == b else other):
                if f[7] == g[7] and abs(f[1] - g[1]) < 1e-9 and f[9] == g[9]:
                    continue
                if abs(f[1] - g[1]) > GAP_MAX:
                    continue
                ou = overlap_1d(f[2], f[3], g[2], g[3])
                ov = overlap_1d(f[4], f[5], g[4], g[5])
                if ou <= 0.01 or ov <= 0.01:
                    continue
                oarea = ou * ov
                if oarea < 0.001:  # <10 cm^2 overlap: ignore
                    continue
                # cluster key: axis + coarse plane position (2 cm)
                key = (axis, round(f[1] / 0.02) * 0.02)
                cl = clusters[key]
                cl[0] += oarea
                cl[1].add(f[7]); cl[1].add(g[7])
                cl[2].add(f[8]); cl[2].add(g[8])
                for fc in (f, g):
                    bb = cl[3]
                    bb[0] = min(bb[0], fc[2]); bb[1] = min(bb[1], fc[4])
                    bb[3] = max(bb[3], fc[3]); bb[4] = max(bb[4], fc[5])
                    # store plane coord range in z slots
                    bb[2] = min(bb[2], fc[1]); bb[5] = max(bb[5], fc[1])
                cl[4] += 1

print("=== COPLANAR OVERLAP CLUSTERS (axis, plane, overlap m^2, pairs) ===")
for key in sorted(clusters, key=lambda k: -clusters[k][0]):
    axis, plane = key
    total, obs, mats, bb, pairs = clusters[key]
    if total < 0.01:
        continue
    u_ax, v_ax = [i for i in range(3) if i != axis]
    print(f"{AXIS_NAMES[axis]}={plane:7.2f}  overlap={total:7.3f} m2  pairs={pairs:5d}  "
          f"{AXIS_NAMES[u_ax]}[{bb[0]:6.2f},{bb[3]:6.2f}] {AXIS_NAMES[v_ax]}[{bb[1]:6.2f},{bb[4]:6.2f}]  "
          f"plane-range[{bb[2]:.3f},{bb[5]:.3f}]")
    print(f"    objects: {sorted(obs)}")
    print(f"    materials: {sorted(mats)}")
