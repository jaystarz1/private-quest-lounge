# Detail probe for vertical-wall z-fighting: for X- and Y-normal faces only,
# lists object pairs whose faces are within GAP of the same plane and overlap,
# with normal signs and tight in-plane overlap regions, so the build script can
# delete the hidden member surgically.
# Usage: blender -b --factory-startup -P probe-wall-tight.py -- <model.glb>
import bpy, sys, math
from collections import defaultdict
from mathutils import Vector

src = sys.argv[-1]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=src)
sc = bpy.context.scene

ALIGN_DOT = 0.985
GAP = 0.0008           # near-exact planes: guaranteed strobers
MIN_FACE_AREA = 0.0004
INTERIOR = (-11.2, 11.8, -10.6, 10.1, -0.3, 7.2)  # x1,x2,y1,y2,z1,z2 living volume
SKIP_PREFIXES = ("TVScreen", "NavMesh", "Spawn", "Seat_", "RockiesView",
                 "ViewEast", "ViewWest", "ViewSouth", "Art_", "Monitor")

faces = []
for ob in [o for o in sc.collection.all_objects if o.type == 'MESH']:
    if ob.name.startswith(SKIP_PREFIXES):
        continue
    mw = ob.matrix_world
    nmat = mw.to_3x3()
    for p in ob.data.polygons:
        n = (nmat @ p.normal)
        if n.length < 1e-6:
            continue
        n = n.normalized()
        axis = None
        if abs(n.x) >= ALIGN_DOT:
            axis = 0
        elif abs(n.y) >= ALIGN_DOT:
            axis = 1
        if axis is None:
            continue
        c = mw @ p.center
        if not (INTERIOR[0] < c.x < INTERIOR[1] and INTERIOR[2] < c.y < INTERIOR[3] and INTERIOR[4] < c.z < INTERIOR[5]):
            continue
        verts = [mw @ ob.data.vertices[vi].co for vi in p.vertices]
        u_ax, v_ax = [i for i in range(3) if i != axis]
        us = [v[u_ax] for v in verts]
        vs = [v[v_ax] for v in verts]
        umin, umax, vmin, vmax = min(us), max(us), min(vs), max(vs)
        if (umax - umin) * (vmax - vmin) < MIN_FACE_AREA:
            continue
        sign = 1 if n[axis] > 0 else -1
        faces.append((axis, c[axis], umin, umax, vmin, vmax, ob.name, sign))

buckets = defaultdict(list)
STEP = 0.002
for f in faces:
    buckets[(f[0], int(math.floor(f[1] / STEP)))].append(f)

pairs = defaultdict(lambda: [0.0, 0, [1e9, -1e9, 1e9, -1e9], set(), 1e9, -1e9])
for (axis, b), lst in buckets.items():
    for nb in (b, b + 1):
        other = buckets.get((axis, nb), [])
        for i, f in enumerate(lst):
            cand = other[i + 1:] if nb == b else other
            for g in cand:
                if abs(f[1] - g[1]) > GAP:
                    continue
                if f[6] == g[6]:
                    continue
                ou = min(f[3], g[3]) - max(f[2], g[2])
                ov = min(f[5], g[5]) - max(f[4], g[4])
                if ou <= 0.02 or ov <= 0.02 or ou * ov < 0.002:
                    continue
                key = (axis, round(f[1] / 0.05) * 0.05, tuple(sorted((f[6], g[6]))))
                pr = pairs[key]
                pr[0] += ou * ov
                pr[1] += 1
                bb = pr[2]
                bb[0] = min(bb[0], max(f[2], g[2])); bb[1] = max(bb[1], min(f[3], g[3]))
                bb[2] = min(bb[2], max(f[4], g[4])); bb[3] = max(bb[3], min(f[5], g[5]))
                pr[3].add((f[7], g[7]) if f[6] < g[6] else (g[7], f[7]))
                pr[4] = min(pr[4], f[1], g[1]); pr[5] = max(pr[5], f[1], g[1])

print("=== WALL FACE PAIRS (gap<3mm, interior volume) ===")
for key in sorted(pairs, key=lambda k: -pairs[k][0]):
    axis, plane, obs = key
    total, n, bb, signs, lo, hi = pairs[key]
    if total < 0.02:
        continue
    an = "XY"[axis]
    u_ax, v_ax = [i for i in range(3) if i != axis]
    un, vn = "XYZ"[u_ax], "XYZ"[v_ax]
    print(f"{an}~{plane:7.2f} [{lo:8.4f},{hi:8.4f}] {obs[0]:12s} x {obs[1]:12s} "
          f"overlap={total:6.2f} m2 pairs={n:4d} signs={sorted(signs)} "
          f"{un}[{bb[0]:6.2f},{bb[1]:6.2f}] {vn}[{bb[2]:6.2f},{bb[3]:6.2f}]")
