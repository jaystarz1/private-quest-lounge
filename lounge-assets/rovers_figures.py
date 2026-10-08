# Rovers regulars: animated low-poly people in the Rovers Return.
#
# Everyone shares one master timeline (LOOP s), so their comings and goings
# can be coordinated and checked:
#   - three regulars on the bar stools drink their pints down and set the
#     empties on the drip tray; the barman collects each, refills it at the
#     fourth handpump (the handle moves, the glass fills) and serves it back;
#   - the pair at the drinking shelf by the door and the darts fan take their
#     empties up to the bar themselves, wait while the barman pours, and carry
#     the refill back;
#   - the barmaid works the room from her station at the end of the bar with a
#     tray: she clears the couple at the first booth table and brings them a
#     pint of bitter and a glass of white (the barman pulls her pints, she
#     pours the wine from the bottle), keeps the pianist's stout on the piano
#     topped up, and twice a loop brings the reserved table by the window a
#     fresh red wine and a pint (two sets, so that table is never empty);
#   - four people play darts the whole loop: step up, three darts, pull them,
#     chalk the score; now and then a player goes to the Gents/Ladies or up to
#     the bar for a refill straight after their turn, and is back for the next;
#   - about once a minute a regular goes to the Gents or the Ladies on the
#     party wall: they glide through the door into the wall, stay out of
#     sight for a while, and come back to their seat;
#   - between all that they chat, gesture, laugh, look round the room; the
#     barman wipes the bar, polishes a glass and leans on the bar chatting;
#     the pianist plays, stopping now and then for a drink.
#
# Glasses pass between figures by an invisible swap: the receiving figure's
# glass grows inside the giver's on the exact spot, then the giver's shrinks.
# Feet glide when people move (no walk cycle, by choice).
#
# Each figure is one armature ("Fig_<tag>", bones prefixed "<tag>_" because the
# Hubs client binds animation tracks by node name across the whole scene) with
# one skinned mesh (rigid weights, vertex colours; a second primitive for
# glass) and one action "Fig_<tag>Loop". Arms and legs are solved with Blender
# IK per frame; every channel is then thinned to the keys linear interpolation
# needs (build-penthouse exports unsampled). inject-hubs.mjs tags every Fig_*
# armature with loop-animation for its own clip.
#
# build() runs from build-penthouse.py after the nav mesh and detail passes and
# fails the build if two people come within 0.40 m of each other or a walking
# route crosses furniture. The scene's fourth pump handle, the static pints
# these people now own and the seats they occupy are left out of the scene.
import bpy
import bmesh
import math
import random
from mathutils import Matrix, Vector, Quaternion
from bpy_extras import anim_utils

FPS = 12                                   # one scene fps for every clip
LOOP = 360.0                               # the shared master timeline
CARPET = 0.10                              # Rovers public floor
BOARDS = 0.106                             # servers' boards behind the bar
PUMP = Vector((3.15, -14.66, 1.14))        # pivot of the fourth handle
HANDLE = 0.33
PUMP_SPOT = Vector((3.10, -14.77, 1.06))   # glass base under the spout
TRAY_Z = 1.071                             # drip tray top (public side of the pumps)
BACK_SPOT = Vector((2.95, -16.20, 0.99))   # back counter top
TABLE_Z = 0.85
SHELF_Z = 1.09
EPS = 1.0 / FPS                            # glass swap overlap
GLASS = {"pint": (0.038, 0.15), "half": (0.032, 0.12), "wine": (0.042, 0.20), "highball": (0.031, 0.16),
         "pineapple": (0.060, 0.17)}
ALE = {"bitter": ("b8650f", "f2ead8"), "lager": ("d6a531", "f6f0dc"), "stout": ("1a110c", "e8dcc0"),
       "cider": ("e2ad45", "f2e6c0"),                    # beer colour, head colour
       "sunrise": ("e8742a", "f6c24a"), "punch": ("e0506e", "f6a6b8"), "colada": ("f2ead2", "faf6ea")}
#                                                         (cocktails: drink colour, top layer)
WINE = {"red": "4e0c18", "white": "e2d68a"}
WINE_GLASS = (0.038, 0.075, (0.078, 0.044, 0.21, 0.042), 0.084, 0.150)   # foot r, stem top, bowl, poured level
BOTTLE = {"red": ("2a0e12", "8a1a2a"), "white": ("5a7a3a", "e8e0c8")}
BOTTLE_GRIP = 0.11
TRAY_R, TRAY_TOP = 0.16, 0.010
TRAY_SLOTS = [Vector((-0.075, 0.055, 0.0)), Vector((0.075, 0.055, 0.0)), Vector((-0.075, -0.06, 0.0)),
              Vector((0.075, -0.06, 0.0))]                # tray-local: +y away from the carrier
HOLD = object()                            # Keys value: hold the pose reached so far


def _rgba(hexstr):
    return tuple(int(hexstr[i:i + 2], 16) / 255 for i in (0, 2, 4)) + (1.0,)


# --- Interpolation ------------------------------------------------------------
def ease(s):
    return 0.5 - 0.5 * math.cos(math.pi * max(0.0, min(1.0, s)))


def track(keys, t):
    """keys: sorted [(time, value or fn(t)[, 'lin'])] -> value at t. A segment
    eases in and out unless its starting key is marked 'lin'."""
    def val(v):
        return v(t) if callable(v) else v
    if t <= keys[0][0]:
        return val(keys[0][1])
    for a, b in zip(keys, keys[1:]):
        if t <= b[0]:
            va, vb = val(a[1]), val(b[1])
            if b[0] <= a[0]:
                return vb
            s = (t - a[0]) / (b[0] - a[0])
            if len(a) < 3:
                s = ease(s)
            return va + (vb - va) * s
    return val(keys[-1][1])


class Keys(list):
    def add(self, t, v, lin=False):
        self.append((t, v, 'lin') if lin else (t, v))
        return self

    def hold(self, t):
        self.append((t, HOLD))
        return self

    def done(self):
        self.sort(key=lambda kv: kv[0])               # stable: same-time keys keep order
        for i, kv in enumerate(self):
            if kv[1] is HOLD:
                prev = self[:i]
                if prev:
                    v = track(prev, kv[0])
                else:
                    v = next(k[1] for k in self[i + 1:] if k[1] is not HOLD)
                    v = v(kv[0]) if callable(v) else v
                self[i] = (kv[0], v) + tuple(kv[2:])
        return self


# --- Figure -------------------------------------------------------------------
class Figure:
    def __init__(self, tag, look, loop=LOOP, legs=True):
        self.tag, self.look, self.loop, self.legs = tag, look, loop, legs
        self.root, self.zk, self.vis = Keys(), Keys(), Keys()
        self.lean, self.pitch, self.yaw = Keys(), Keys(), Keys()
        self.L, self.R, self.fL, self.fR = Keys(), Keys(), Keys(), Keys()
        self.glasses, self.wrist, self.contacts = [], {}, []
        self.pump = None
        self.cloth = look.get("cloth", False)
        self.busy = []              # (t0, t1): idle filler keeps out
        self.rq = Keys()            # optional full orientation (lying down)
        self.capsules = None        # bones to report per frame (duvet heightfield)
        self.hand = "L"             # the hand that sets glasses down (contacts)
        self.tray = None            # name of the tray prop glasses in mode "T" stand on
        self._yaw = None

    def put(self, t, x, y, yaw, lin=False):
        """Root key; yaw unwrapped to the nearest turn from the previous key."""
        if self._yaw is not None:
            while yaw - self._yaw > 180:
                yaw -= 360
            while yaw - self._yaw < -180:
                yaw += 360
        self._yaw = yaw
        self.root.add(t, Vector((x, y, yaw)), lin)

    def z_at(self, t):
        return track(self.zk, t)

    def root_at(self, t):
        r = track(self.root, t)
        return Vector((r.x, r.y, self.z_at(t))), math.radians(r.z)

    def rot_at(self, t):
        """Body orientation: yaw only, unless the figure has a full
        orientation channel (rq, quaternions) for lying down."""
        if self.rq:
            return track(self.rq, t).normalized().to_matrix()
        return Matrix.Rotation(math.radians(track(self.root, t).z), 3, 'Z')

    def to_world(self, t, local):
        p, _yaw = self.root_at(t)
        return p + self.rot_at(t) @ Vector(local)

    def to_local(self, t, world):
        p, _yaw = self.root_at(t)
        return self.rot_at(t).transposed() @ (Vector(world) - p)

    def at_world(self, w):
        w = Vector(w)
        return lambda t: self.to_local(t, w)

    def named(self, name):
        return lambda t: self.wrist[name]

    def glass(self, name, size="pint", drink=None):
        g = {"name": name, "kind": "glass", "size": size, "segs": [], "fill": Keys(), "tilt": Keys(),
             "events": [], "scale": Keys()}
        if size == "wine":
            g["ale"] = drink or "red"
            g["drink"] = WINE[g["ale"]]
        else:
            g["ale"] = drink or "bitter"
            g["drink"], g["head"] = ALE[g["ale"]]
        self.glasses.append(g)
        return g

    def prop(self, name, kind, rest, colour=None):
        """A dart (flies, sticks), a chalk mark (spot only, scale-keyed), a
        tray (carried flat on a palm; glasses ride on it) or a bottle."""
        g = {"name": name, "kind": kind, "size": None, "segs": [], "fill": Keys(), "tilt": Keys(),
             "events": [], "rest": Vector(rest), "colour": colour, "scale": Keys()}
        self.glasses.append(g)
        return g

    def free(self, t0, t1):
        return all(t1 <= a or t0 >= b for a, b in self.busy)


# --- Rig ----------------------------------------------------------------------
def _bones(look):
    f = look.get("sex") == "f"
    sh = 0.17 if f else 0.19
    b = [
        ("Root", (0, 0, 0), (0, 0.25, 0), None, False),
        ("Hips", (0, 0, 0.93), (0, 0, 1.05), "Root", False),
        ("Spine", (0, 0, 1.05), (0, 0, 1.28), "Hips", True),
        ("Chest", (0, 0, 1.28), (0, 0, 1.50), "Spine", True),
        ("Neck", (0, 0, 1.50), (0, 0, 1.61), "Chest", True),
        ("Head", (0, 0, 1.61), (0, 0, 1.85), "Neck", True),
    ]
    for side, s in (("R", 1), ("L", -1)):
        b += [
            (f"UpperArm.{side}", (s * sh, 0, 1.45), (s * (sh + .025), -0.03, 1.14), "Chest", False),
            (f"Forearm.{side}", (s * (sh + .025), -0.03, 1.14), (s * (sh + .03), 0.02, 0.87), f"UpperArm.{side}", True),
            (f"Hand.{side}", (s * (sh + .03), 0.02, 0.87), (s * (sh + .03), 0.03, 0.78), f"Forearm.{side}", True),
            (f"Thigh.{side}", (s * 0.10, 0, 0.93), (s * 0.10, 0.01, 0.50), "Hips", False),
            (f"Shin.{side}", (s * 0.10, 0.01, 0.50), (s * 0.10, 0, 0.09), f"Thigh.{side}", True),
            (f"Foot.{side}", (s * 0.10, 0, 0.09), (s * 0.10, 0.14, 0.03), f"Shin.{side}", True),
        ]
    return b


def _build_armature(fig):
    p = fig.tag + "_"
    p0, yaw0 = fig.root_at(0.0)
    R0 = p0                                 # rest root (the first key's spot)
    fig.R0 = R0
    arm_data = bpy.data.armatures.new(f"Fig_{fig.tag}Rig")
    arm = bpy.data.objects.new(f"Fig_{fig.tag}", arm_data)
    bpy.context.scene.collection.objects.link(arm)
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode='EDIT')
    eb = arm_data.edit_bones
    for name, h, t, parent, conn in _bones(fig.look):
        b = eb.new(p + name)
        b.head, b.tail = R0 + Vector(h), R0 + Vector(t)
        b.roll = 0.0
        if parent:
            b.parent = eb[p + parent]
            b.use_connect = conn
    for g in fig.glasses:
        if g["kind"] != "glass":
            b = eb.new(p + g["name"])
            b.head, b.tail = g["rest"], g["rest"] + Vector((0, 0, 0.1))
            continue
        r, h = GLASS[g["size"]]
        b = eb.new(p + g["name"])
        b.head, b.tail = R0 + Vector((0, 0.6, 1.0)), R0 + Vector((0, 0.6, 1.0 + h * 0.8))
        a = eb.new(p + g["name"] + "Ale")
        z0 = WINE_GLASS[3] if g["size"] == "wine" else 0.008     # the drink shrinks to the bottom
        a.head, a.tail = b.head + Vector((0, 0, z0)), b.head + Vector((0, 0, h * 0.85))
        a.parent = b
        g["rest"] = Vector(b.head)
    if fig.pump is not None:
        b = eb.new(p + "Pump")
        b.head, b.tail = PUMP, PUMP + Vector((0, 0, HANDLE))
    bpy.ops.object.mode_set(mode='OBJECT')
    for pb in arm.pose.bones:
        pb.rotation_mode = 'QUATERNION'
    return arm


# --- Mesh ---------------------------------------------------------------------
class _Parts:
    def __init__(self, prefix):
        self.p = prefix
        self.bm = bmesh.new()
        self.col = self.bm.faces.layers.int.new("col")
        self.cols = []
        self.bone_of_vert = {}

    def _tag(self, verts, bone, colour, mat=0):
        if colour not in self.cols:
            self.cols.append(colour)
        ci = self.cols.index(colour)
        for f in {f for v in verts for f in v.link_faces}:
            f[self.col] = ci
            f.material_index = mat
        for v in verts:
            self.bone_of_vert[v] = self.p + bone

    def seg(self, bone, p0, p1, r0, r1, colour, segs=10, squash=1.0, caps=True, mat=0):
        p0, p1 = Vector(p0), Vector(p1)
        d = p1 - p0
        rot = d.to_track_quat('Z', 'Y').to_matrix().to_4x4()
        m = Matrix.Translation((p0 + p1) / 2) @ rot @ Matrix.Diagonal((1.0, squash, 1.0, 1.0))
        g = bmesh.ops.create_cone(self.bm, cap_ends=caps, cap_tris=False, segments=segs,
                                  radius1=r0, radius2=r1, depth=d.length, matrix=m)
        self._tag(g['verts'], bone, colour, mat)

    def ball(self, bone, c, r, colour, scale=(1, 1, 1), segs=10, rings=6):
        m = Matrix.Translation(Vector(c)) @ Matrix.Diagonal(tuple(scale) + (1.0,))
        g = bmesh.ops.create_uvsphere(self.bm, u_segments=segs, v_segments=rings, radius=r, matrix=m)
        self._tag(g['verts'], bone, colour)

    def box(self, bone, c, size, colour):
        m = Matrix.Translation(Vector(c)) @ Matrix.Diagonal(tuple(size) + (1.0,))
        g = bmesh.ops.create_cube(self.bm, size=1.0, matrix=m)
        self._tag(g['verts'], bone, colour)


def _build_mesh(fig, arm):
    L = fig.look
    f = L.get("sex") == "f"
    P = _Parts(fig.tag + "_")
    R0 = fig.R0
    o = lambda x, y, z: R0 + Vector((x, y, z))
    sh = 0.17 if f else 0.19
    tw = 0.155 if f else 0.175                       # torso half width at the chest
    top, jacket, vest = L["top"], L.get("jacket"), L.get("vest")
    outer = jacket or vest or top
    legs, shoes, skin, hair = L["legs"], L.get("shoes", "1a1614"), L["skin"], L.get("hair", "3a2a20")
    # Legs and feet.
    for s, side in ((1, "R"), (-1, "L")):
        P.seg(f"Thigh.{side}", o(s * .10, 0, .95), o(s * .10, .01, .50), .085 if not f else .08, .066, legs)
        P.seg(f"Shin.{side}", o(s * .10, .01, .51), o(s * .10, 0, .07), .064, .052, legs)
        P.box(f"Foot.{side}", o(s * .10, .05, .04), (.09 if f else .10, .25 if f else .27, .075), shoes)
    P.seg("Hips", o(0, 0, .86), o(0, 0, 1.06), .175 if f else .17, .16, L.get("hips", legs), squash=.70, segs=12)
    if L.get("shorts"):                               # swim shorts / swimsuit over the top of the thighs
        for s, side in ((1, "R"), (-1, "L")):
            P.seg(f"Thigh.{side}", o(s * .10, 0, .95), o(s * .10, .005, .74), .089 if not f else .084, .078,
                  L["shorts"])
    if L.get("skirt"):
        P.seg("Hips", o(0, 0, 1.0), o(0, .01, .52), .16, .21, L["skirt"], squash=.8, segs=12)
    if L.get("gown"):                                 # floor length, drapes from the knees when seated
        g = L["gown"]
        P.seg("Hips", o(0, 0, 1.02), o(0, 0, .84), .17, .19, g, squash=.80, segs=14)
        for s, side in ((1, "R"), (-1, "L")):
            P.seg(f"Thigh.{side}", o(s * .09, 0, .92), o(s * .09, .01, .52), .10, .095, g, segs=12)
            P.seg(f"Shin.{side}", o(s * .09, .01, .52), o(s * .09, .02, .03), .095, .16, g, squash=.9, segs=12)
    if L.get("apron"):                                # waiter's long bistro apron / chef's apron
        P.box("Hips", o(0, .128, .66), (.34, .012, .72), L["apron"])
    # Torso.
    P.seg("Spine", o(0, 0, 1.04), o(0, 0, 1.30), tw - .01, tw, outer, squash=.66, segs=12)
    P.seg("Chest", o(0, 0, 1.29), o(0, 0, 1.49), tw + .005, tw + .015, outer, squash=.64, segs=12)
    P.seg("Chest", o(0, 0, 1.47), o(0, 0, 1.52), tw + .015, .09, skin if L.get("neckline") else outer,
          squash=.66, segs=12)
    if L.get("neckline"):                             # bare shoulders / decolletage above the bodice
        P.box("Chest", o(0, .100, 1.46), (.12, .012, .06), skin)
    if f:
        for s in (1, -1):
            P.ball("Chest", o(s * .055, .085, 1.37), .055, outer, scale=(1, .8, .9), segs=8, rings=5)
    if jacket or vest:                                # shirt/blouse showing in the V
        P.box("Chest", o(0, .108, 1.42), (.09, .012, .15), top)
        if jacket:                                    # lapels (satin on a dinner jacket)
            for s in (1, -1):
                P.box("Chest", o(s * .06, .112, 1.40), (.035, .012, .19), L.get("lapel", jacket))
    if L.get("tie"):
        P.box("Chest", o(0, .118, 1.40), (.032, .010, .16), L["tie"])
    if L.get("bowtie"):
        P.box("Chest", o(0, .112, 1.485), (.08, .015, .03), L["bowtie"])
    if L.get("collar", True):
        P.seg("Chest", o(0, 0, 1.48), o(0, 0, 1.53), .065, .058, top, segs=10)
    if L.get("buttons"):                              # double-breasted chef's jacket
        for z in (1.30, 1.38, 1.46):
            for s in (1, -1):
                P.ball("Chest", o(s * .05, .112, z), .009, L["buttons"], segs=6, rings=4)
    if L.get("neckerchief"):
        P.box("Neck", o(0, .035, 1.52), (.10, .06, .035), L["neckerchief"])
    if L.get("stripes"):                              # Breton stripes round the jersey
        for i, z in enumerate((1.08, 1.15, 1.22, 1.29, 1.36, 1.43)):
            bone = "Spine" if z < 1.28 else "Chest"
            P.seg(bone, o(0, 0, z), o(0, 0, z + .025), tw + .006, tw + .008, L["stripes"], squash=.68, segs=12,
                  caps=False)
    # Neck and head.
    hs = 0.95 if f else 1.0
    P.seg("Neck", o(0, 0, 1.49), o(0, 0, 1.64), .046 if f else .052, .044, skin, segs=8)
    P.ball("Head", o(0, .005, 1.725), .105 * hs, skin, scale=(1, 1.06, 1.16), segs=12, rings=8)
    if L.get("necklace"):
        for i in range(9):
            a = math.radians(-72 + i * 18)
            P.ball("Neck", o(.056 * math.sin(a), .048 * math.cos(a) + .004, 1.505), .0085, L["necklace"],
                   segs=6, rings=4)
    if L.get("earrings"):
        for s in (1, -1):
            P.ball("Head", o(s * .106 * hs, .0, 1.682), .009, L["earrings"], segs=6, rings=4)
    for s in (1, -1):
        P.ball("Head", o(s * .036, .100, 1.735), .011, "1a1410", segs=6, rings=4)
        P.box("Head", o(s * .038, .104, 1.760), (.032, .008, .007), L.get("brow", hair))
        P.ball("Head", o(s * .103 * hs, 0, 1.72), .02, skin, scale=(.5, 1, 1.3), segs=6, rings=4)
    P.box("Head", o(0, .115 * hs, 1.705), (.02, .028, .036), skin)
    if f or L.get("lips"):
        P.box("Head", o(0, .104, 1.672), (.04, .008, .010), L.get("lips", "9a4044"))
    if L.get("tears"):                                # the painted mime's teardrops
        for s in (1, -1):
            P.box("Head", o(s * .036, .102, 1.700), (.006, .006, .022), L["tears"])
    hstyle = L.get("hair_style", "short")
    if hstyle != "bald":
        P.ball("Head", o(0, -.02, 1.765), .108 * hs, hair, scale=(1.03, 1.05, .9), segs=12, rings=8)
    else:
        P.ball("Head", o(0, -.035, 1.70), .104, hair, scale=(1.04, 1.0, .55), segs=12, rings=6)
    if hstyle in ("bob", "long"):
        drop = 1.62 if hstyle == "bob" else 1.50
        P.seg("Head", o(0, -.035, 1.74), o(0, -.04, drop), .105, .10 if hstyle == "bob" else .085,
              hair, squash=.85, segs=12)
    if hstyle == "bun":
        P.ball("Head", o(0, -.10, 1.80), .05, hair, segs=10, rings=6)
    if hstyle == "updo":
        P.ball("Head", o(0, -.05, 1.85), .075, hair, scale=(1, .9, .8), segs=12, rings=6)
    if hstyle == "chignon":
        P.ball("Head", o(0, -.105, 1.67), .048, hair, segs=10, rings=6)
    if hstyle == "ponytail":
        P.seg("Head", o(0, -.10, 1.75), o(0, -.15, 1.56), .028, .02, hair, segs=8)
    if hstyle == "slick":
        P.box("Head", o(0, .02, 1.83), (.15, .14, .02), hair)
    if L.get("toque"):
        P.seg("Head", o(0, -.01, 1.80), o(0, -.01, 2.02), .102, .115, L["toque"], segs=14)
        P.ball("Head", o(0, -.01, 2.03), .115, L["toque"], scale=(1, 1, .45), segs=14, rings=6)
    if L.get("tophat"):                               # a battered opera hat with a flower in the band
        P.seg("Head", o(0, -.01, 1.80), o(0, -.01, 1.83), .17, .17, L["tophat"], segs=16)
        P.seg("Head", o(0, -.01, 1.82), o(0, -.01, 2.00), .105, .112, L["tophat"], segs=16)
        P.seg("Head", o(0, -.01, 1.84), o(0, -.01, 1.875), .108, .109, L.get("hatband", "1a1a1a"), segs=16,
              caps=False)
        if L.get("flower"):
            P.ball("Head", o(.075, .07, 1.86), .028, L["flower"], segs=8, rings=5)
            P.ball("Head", o(.085, .085, 1.835), .016, "3a7a2a", scale=(1, .4, 1.6), segs=6, rings=4)
    if L.get("beret"):
        P.ball("Head", o(-.01, -.01, 1.83), .118, L["beret"], scale=(1.08, 1.08, .32), segs=14, rings=6)
    if L.get("cap"):
        P.ball("Head", o(0, .0, 1.79), .112, L["cap"], scale=(1.03, 1.1, .55), segs=12, rings=6)
        P.box("Head", o(0, .10, 1.79), (.16, .07, .012), L["cap"])
    if L.get("beard"):
        P.ball("Head", o(0, .065, 1.655), .07, hair, scale=(1.05, .6, .75), segs=10, rings=6)
    if L.get("moustache"):
        P.box("Head", o(0, .108, 1.672), (.062, .014, .015), hair)
    if L.get("glasses"):
        for s in (1, -1):
            P.box("Head", o(s * .037, .113, 1.735), (.036, .006, .026), L["glasses"])
        P.box("Head", o(0, .113, 1.742), (.02, .006, .006), L["glasses"])
    # Arms.
    sleeve = skin if L.get("sleeves") == "none" else (jacket or top)
    hand_col = L.get("gloves", skin)
    for s, side in ((1, "R"), (-1, "L")):
        a = sh
        shp, el, wr, tip = (o(s * a, 0, 1.45), o(s * (a + .025), -.03, 1.14),
                            o(s * (a + .03), .02, .87), o(s * (a + .03), .03, .78))
        P.ball(f"UpperArm.{side}", shp, .058 if f else .062, sleeve)
        P.seg(f"UpperArm.{side}", shp, el, .05 if f else .055, .044, sleeve)
        if L.get("stripes"):
            for q in (.25, .55, .85):
                a0, a1 = shp.lerp(el, q), shp.lerp(el, q + .07)
                P.seg(f"UpperArm.{side}", a0, a1, .057 if not f else .052, .055 if not f else .05, L["stripes"],
                      segs=10, caps=False)
        P.ball(f"Forearm.{side}", el, .044, sleeve)
        if L.get("sleeves") == "rolled":
            P.seg(f"Forearm.{side}", el, el.lerp(wr, .22), .050, .048, sleeve)
            P.seg(f"Forearm.{side}", el.lerp(wr, .2), wr, .038, .031, skin, segs=8)
        else:
            P.seg(f"Forearm.{side}", el, wr.lerp(el, .08), .045, .038, sleeve)
            P.seg(f"Forearm.{side}", wr.lerp(el, .1), wr, .033, .030, hand_col, segs=8)
            if L.get("cuffs"):
                P.seg(f"Forearm.{side}", wr.lerp(el, .14), wr.lerp(el, .07), .039, .039, L["cuffs"], segs=8)
        P.box(f"Hand.{side}", wr.lerp(tip, .5), (.030 if f else .034, .068 if f else .075, .095), hand_col)
    if fig.cloth:
        P.box("Hand.R", o(sh + .03, .075, .79), (.05, .03, .13), "d8d0c0")
    # Glasses (shell + base, ale + head). Built at the bone's rest spot.
    for g in fig.glasses:
        b, n = g["rest"], g["name"]
        if g["kind"] == "dart":            # tip at the bone head, flights up the bone
            P.seg(n, b, b + Vector((0, 0, .03)), .0012, .0025, "c0c0c4", segs=6)
            P.seg(n, b + Vector((0, 0, .03)), b + Vector((0, 0, .075)), .0045, .0045, "7d7d84", segs=6)
            P.seg(n, b + Vector((0, 0, .075)), b + Vector((0, 0, .11)), .0018, .0018, "1a1a1a", segs=6)
            P.box(n, b + Vector((0, 0, .118)), (.034, .002, .034), g["colour"])
            P.box(n, b + Vector((0, 0, .118)), (.002, .034, .034), g["colour"])
            continue
        if g["kind"] == "mark":            # a chalk scrawl flat on the board
            rr = random.Random(n)
            for _q in range(rr.randint(2, 4)):
                c = b + Vector((rr.uniform(-.03, .03), 0, rr.uniform(-.012, .012)))
                if rr.random() < .5:
                    P.box(n, c, (rr.uniform(.018, .034), .003, .004), "e6e6dc")
                else:
                    P.box(n, c, (.004, .003, rr.uniform(.018, .03)), "e6e6dc")
            continue
        if g["kind"] == "tray":            # round bar tray: dark cork centre, steel rim
            P.seg(n, b, b + Vector((0, 0, TRAY_TOP)), TRAY_R, TRAY_R, "2b2622", segs=20)
            P.seg(n, b + Vector((0, 0, TRAY_TOP)), b + Vector((0, 0, .024)), TRAY_R, TRAY_R + .002, "b9b5ac",
                  segs=20, caps=False)
            continue
        if g["kind"] == "bottle":          # wine bottle with label and foil
            body, foil = BOTTLE[g["wine"]]
            P.seg(n, b, b + Vector((0, 0, .20)), .038, .038, body, segs=14)
            P.seg(n, b + Vector((0, 0, .20)), b + Vector((0, 0, .25)), .038, .014, body, segs=14)
            P.seg(n, b + Vector((0, 0, .25)), b + Vector((0, 0, .31)), .014, .014, body, segs=10)
            P.seg(n, b + Vector((0, 0, .29)), b + Vector((0, 0, .315)), .0155, .0155, foil, segs=10)
            P.seg(n, b + Vector((0, 0, .07)), b + Vector((0, 0, .15)), .0395, .0395, "efe6cf", segs=14)
            continue
        if g["size"] == "wine":            # stemmed wine glass, poured to the widest part of the bowl
            fr, st, (bz0, br0, bz1, br1), lz0, lz1 = WINE_GLASS
            P.seg(n, b, b + Vector((0, 0, .004)), fr, fr, "e8e4dc", segs=14, mat=1)
            P.seg(n, b + Vector((0, 0, .004)), b + Vector((0, 0, st)), .004, .004, "e8e4dc", segs=8, mat=1)
            P.seg(n, b + Vector((0, 0, bz0)), b + Vector((0, 0, bz1)), br0, br1, "e8e4dc", segs=12, caps=False,
                  mat=1)
            P.seg(n, b + Vector((0, 0, bz0)), b + Vector((0, 0, bz0 + .004)), br0, br0, "e8e4dc", segs=14, mat=1)
            P.seg(n + "Ale", b + Vector((0, 0, lz0)), b + Vector((0, 0, lz1)), br0 * .93, br0 * .96, g["drink"],
                  segs=12)
            continue
        if g["size"] == "pineapple":       # a hollowed pineapple: husk, crown, straw and a paper umbrella
            r, h = GLASS["pineapple"]
            P.seg(n, b, b + Vector((0, 0, .02)), r * .70, r, "a8741e", segs=12)
            for k in range(4):
                z0, z1 = .02 + k * .035, .02 + (k + 1) * .035
                P.seg(n, b + Vector((0, 0, z0)), b + Vector((0, 0, z1)), r * (1.0 - .02 * k), r * (1.0 - .02 * (k + 1)),
                      "c8922a" if k % 2 else "b07c22", segs=12, caps=False)
            P.seg(n, b + Vector((0, 0, h - .03)), b + Vector((0, 0, h)), r * .92, r * .80, "c8922a", segs=12,
                  caps=False)
            P.seg(n + "Ale", b + Vector((0, 0, .01)), b + Vector((0, 0, h - .012)), r * .78, r * .78, g["drink"], segs=12)
            rr = random.Random(n)
            for k in range(7):                         # the crown, set to one side of the cut top
                a = 2 * math.pi * k / 7
                c0 = b + Vector((-.02 + .016 * math.cos(a), .016 * math.sin(a), h - .005))
                tip = c0 + Vector((.05 * math.cos(a) - .02, .05 * math.sin(a), rr.uniform(.08, .12)))
                P.seg(n, c0, tip, .012, .002, "3f7a2a" if k % 2 else "2f6a22", segs=4)
            P.seg(n, b + Vector((.025, 0, h - .03)), b + Vector((.045, .01, h + .10)), .004, .004, "e8e8e0", segs=6)
            P.seg(n, b + Vector((-.02, .02, h + .06)), b + Vector((-.03, .025, h + .085)), .045, .002, "e83a6a", segs=8)
            P.seg(n, b + Vector((-.02, .02, h - .02)), b + Vector((-.02, .02, h + .06)), .002, .002, "d8c8a0", segs=4)
            continue
        r, h = GLASS[g["size"]]
        if g["size"] == "highball":        # a straw and a wheel of orange on the rim
            P.seg(n, b + Vector((.012, 0, .02)), b + Vector((.020, .008, h + .07)), .0035, .0035, "e8e8e0", segs=6)
            P.seg(n, b + Vector((-r * .9, 0, h - .035)), b + Vector((-r * .9 - .006, 0, h - .035)), .028, .028,
                  "f09a2a", segs=12)
        P.seg(n, b + Vector((0, 0, .004)), b + Vector((0, 0, h)), r * .92, r, "e8e4dc", segs=14,
              caps=False, mat=1)
        P.seg(n, b, b + Vector((0, 0, .008)), r * .92, r * .92, "e8e4dc", segs=14, mat=1)
        P.seg(n + "Ale", b + Vector((0, 0, .008)), b + Vector((0, 0, h * .85)), r * .86, r * .93,
              g.get("drink", "b8650f"), segs=12)
        P.seg(n + "Ale", b + Vector((0, 0, h * .85)), b + Vector((0, 0, h * .97)), r * .93, r * .95,
              g.get("head", "f2ead8"), segs=12)
    if fig.pump is not None:
        P.seg("Pump", PUMP, PUMP + Vector((0, 0, .32)), .022, .022, "151515", segs=8)
        P.seg("Pump", PUMP + Vector((0, 0, .315)), PUMP + Vector((0, 0, .345)), .03, .03, "b08d4a", segs=8)

    me = bpy.data.meshes.new(f"Fig_{fig.tag}Mesh")
    P.bm.to_mesh(me)
    attr = me.color_attributes.new("Col", 'BYTE_COLOR', 'CORNER')
    cols = [_rgba(c) for c in P.cols]
    data = []
    for poly, face in zip(me.polygons, P.bm.faces):
        data.extend(cols[face[P.col]] * poly.loop_total)
    attr.data.foreach_set("color_srgb", data)
    me.color_attributes.active_color = attr
    ob = bpy.data.objects.new(f"Fig_{fig.tag}Body", me)
    bpy.context.scene.collection.objects.link(ob)
    groups = {}
    for v, bone in P.bone_of_vert.items():
        groups.setdefault(bone, []).append(v.index)
    for bone, verts in groups.items():
        ob.vertex_groups.new(name=bone).add(verts, 1.0, 'REPLACE')
    P.bm.free()
    body, glass = _materials()
    me.materials.append(body)
    me.materials.append(glass)
    ob.parent = arm
    ob.modifiers.new("Armature", 'ARMATURE').object = arm
    return ob


_MATS = {}


def _materials():
    if not _MATS:
        body = bpy.data.materials.new("FigBody")
        body.use_nodes = True
        nt = body.node_tree
        bsdf = nt.nodes['Principled BSDF']
        ca = nt.nodes.new('ShaderNodeVertexColor')
        ca.layer_name = "Col"
        nt.links.new(ca.outputs['Color'], bsdf.inputs['Base Color'])
        bsdf.inputs['Roughness'].default_value = 0.75
        body.use_backface_culling = True
        glass = bpy.data.materials.new("FigGlass")
        glass.use_nodes = True
        gb = glass.node_tree.nodes['Principled BSDF']
        gb.inputs['Base Color'].default_value = (0.9, 0.95, 0.95, 1.0)
        gb.inputs['Alpha'].default_value = 0.12
        gb.inputs['Roughness'].default_value = 0.05
        glass.use_backface_culling = False
        try:
            glass.surface_render_method = 'BLENDED'
        except AttributeError:
            glass.blend_method = 'BLEND'
        _MATS["body"], _MATS["glass"] = body, glass
    return _MATS["body"], _MATS["glass"]



# --- Solve + write ------------------------------------------------------------
def _seg_at(g, t):
    for seg in g["segs"]:
        if seg[0] - 1e-6 <= t < seg[1] - 1e-6:
            return seg
    return g["segs"][-1]


def grip_of(g):
    """Palm height above the base of a glass or bottle held upright."""
    return BOTTLE_GRIP if g["kind"] == "bottle" else GLASS[g["size"]][1] * 0.47


def tray_on_palm(palm, yaw):
    """Tray base (underside centre) carried flat on a palm, 6 cm ahead of it."""
    return palm + Matrix.Rotation(yaw, 3, 'Z') @ Vector((0.0, 0.06, -0.014))


def _glass_state(g, t):
    seg = _seg_at(g, t)
    return seg[2], seg[3]


def _solve(fig, arm, poles):
    sc = bpy.context.scene
    pb = arm.pose.bones
    p = fig.tag + "_"
    objs, cons = [], []

    def ik(bone, side, pole_angle):
        tg = bpy.data.objects.new(f"FigTgt{bone}{side}", None)
        pl = bpy.data.objects.new(f"FigPole{bone}{side}", None)
        sc.collection.objects.link(tg)
        sc.collection.objects.link(pl)
        objs.extend((tg, pl))
        c = pb[p + f"{bone}.{side}"].constraints.new('IK')
        c.target, c.pole_target, c.pole_angle, c.chain_count = tg, pl, pole_angle, 2
        cons.append((pb[p + f"{bone}.{side}"], c))
        return tg, pl

    arms = {s: ik("Forearm", s, poles[s]) for s in ("L", "R")}
    legs = {s: ik("Shin", s, poles["leg"]) for s in ("L", "R")} if fig.legs else {}
    n = int(round(fig.loop * FPS))
    frames = []
    flight = {}
    for fi in range(n + 1):
        t = fi / FPS
        pos, yaw = fig.root_at(t)
        vis = track(fig.vis, t) if fig.vis else 1.0
        R3 = fig.rot_at(t)
        pb[p + "Root"].matrix_basis = (Matrix.Translation(pos - fig.R0) @ R3.to_4x4() @
                                       Matrix.Diagonal((vis, vis, vis, 1.0)))
        lean = math.radians(track(fig.lean, t))
        pb[p + "Spine"].matrix_basis = Matrix.Rotation(-0.4 * lean, 4, 'X')
        pb[p + "Chest"].matrix_basis = Matrix.Rotation(-0.6 * lean, 4, 'X')
        pb[p + "Head"].matrix_basis = (Matrix.Rotation(math.radians(track(fig.yaw, t)), 4, 'Y') @
                                       Matrix.Rotation(-math.radians(track(fig.pitch, t)), 4, 'X'))
        if fig.pump is not None:
            pb[p + "Pump"].matrix_basis = Matrix.Rotation(math.radians(track(fig.pump, t)), 4, 'X')
        for side, keys, sx in (("L", fig.L, -1), ("R", fig.R, 1)):
            arms[side][0].location = fig.to_world(t, track(keys, t))
            arms[side][1].location = fig.to_world(t, Vector((sx * 0.45, -0.35, 1.0)))
        for side, keys, sx in (("L", fig.fL, -1), ("R", fig.fR, 1)):
            if legs:
                legs[side][0].location = fig.to_world(t, track(keys, t))
                legs[side][1].location = fig.to_world(t, Vector((sx * 0.12, 1.2, 0.9)))
        bpy.context.view_layer.update()
        right = R3 @ Vector((1.0, 0.0, 0.0))
        rec = {"wrist": {}, "target": {}, "glass": {}, "pos": pos.copy(), "vis": vis, "palm": {}, "yaw": yaw}
        palms, raw = {}, {}
        for side, toward in (("L", 1), ("R", -1)):
            hand = pb[p + f"Hand.{side}"].matrix
            raw[side] = hand.translation + hand.col[1].xyz.normalized() * 0.045
            palms[side] = raw[side] + right * (0.052 * toward)
            rec["wrist"][side] = pb[p + f"Forearm.{side}"].tail.copy()
            rec["palm"][side] = palms[side].copy()
            rec["target"][side] = arms[side][0].location.copy()
        fwd = R3 @ Vector((0.0, 1.0, 0.0))
        trays = {}
        for g in sorted(fig.glasses, key=lambda g: g["kind"] != "tray"):
            if g["kind"] == "tray":
                t0, t1, mode, spot = _seg_at(g, t)
                if mode in ("L", "R"):
                    base, rot = tray_on_palm(palms[mode], yaw), Matrix.Rotation(yaw, 3, 'Z')
                else:
                    base, rot = Vector(spot[0]), spot[1]
                trays[g["name"]] = (base, rot)
                rec["glass"][g["name"]] = (base, rot, 0.001 if mode == "hidden" else 1.0, 1.0)
                continue
            if g["kind"] not in ("glass", "bottle"):
                t0, t1, mode, spot = _seg_at(g, t)
                st = flight.setdefault(g["name"], {})
                scale = 1.0
                if mode in ("L", "R"):
                    k = g.get("slot", 0)
                    base = raw[mode] + fwd * 0.05 + right * (0.012 * (k - 1)) + Vector((0, 0, 0.01 * k))
                    rot = Matrix.Rotation(yaw, 3, 'Z') @ Matrix.Rotation(math.radians(95), 3, 'X')
                    st["last"] = base.copy()
                    st.pop("start", None)
                elif mode == "fly":
                    tgt = spot[0]
                    start = st.setdefault("start", st.get("last", tgt).copy())
                    sfr = max(0.0, min(1.0, (t - t0) / max(1e-6, t1 - t0)))
                    base = start.lerp(tgt, sfr) + Vector((0, 0, 0.10 * math.sin(math.pi * sfr)))
                    vel = (tgt - start) + Vector((0, 0, 0.10 * math.pi * math.cos(math.pi * sfr)))
                    rot = (-vel).normalized().to_track_quat('Z', 'Y').to_matrix()
                else:
                    pos, rot = spot if isinstance(spot, tuple) else (Vector(spot), Matrix.Identity(3))
                    base = Vector(pos)
                    st["last"] = base.copy()
                    st.pop("start", None)
                    if mode == "hidden":
                        scale = 0.001
                    elif g["scale"]:
                        scale = max(0.001, track(g["scale"], t))
                rec["glass"][g["name"]] = (base, rot, scale, 1.0)
                continue
            mode, spot = _glass_state(g, t)
            tilt = math.radians(track(g["tilt"], t)) if g["tilt"] else 0.0
            rot = Matrix.Rotation(yaw, 3, 'Z') @ Matrix.Rotation(tilt, 3, 'X')
            if mode in ("L", "R"):
                base = palms[mode] - rot @ Vector((0, 0, grip_of(g)))
                scale = 1.0
            elif mode == "T":                 # standing on a tray slot
                tb, tr = trays[fig.tray]
                base, rot, scale = tb + tr @ (TRAY_SLOTS[spot] + Vector((0, 0, TRAY_TOP))), tr.copy(), 1.0
            else:
                base, rot = Vector(spot), Matrix.Identity(3)
                scale = 1.0 if mode == "spot" else 0.001
            fill = track(g["fill"], t) if g["kind"] == "glass" and g["fill"] else 1.0
            rec["glass"][g["name"]] = (base, rot, scale, fill)
        for b in pb:
            if b.name.endswith(("UpperArm.L", "UpperArm.R", "Forearm.L", "Forearm.R", "Hand.L", "Hand.R",
                                "Thigh.L", "Thigh.R", "Shin.L", "Shin.R", "Foot.L", "Foot.R")):
                rec[b.name] = arm.convert_space(pose_bone=b, matrix=b.matrix, from_space='POSE', to_space='LOCAL')
        for b in ("Root", "Spine", "Chest", "Head", "Pump"):
            if p + b in pb:
                rec[p + b] = pb[p + b].matrix_basis.copy()
        if fig.capsules:
            rec["caps"] = [(pb[p + bn].head.copy(), pb[p + bn].tail.copy(), r) for bn, r in fig.capsules]
        frames.append(rec)
    for bone, c in cons:
        bone.constraints.remove(c)
    for o in objs:
        bpy.data.objects.remove(o)
    return frames


def _thin(rows, tol):
    """Frames to keep so linear interpolation stays within tol on every row
    (Ramer-Douglas-Peucker on the joint channel)."""
    n = len(rows[0])
    keep = {0, n - 1}
    stack = [(0, n - 1)]
    while stack:
        a, b = stack.pop()
        if b - a < 2:
            continue
        worst, wi = 0.0, None
        for i in range(a + 1, b):
            s = (i - a) / (b - a)
            e = max(abs(r[i] - (r[a] + (r[b] - r[a]) * s)) for r in rows)
            if e > worst:
                worst, wi = e, i
        if worst > tol:
            keep.add(wi)
            stack += [(a, wi), (wi, b)]
    return sorted(keep)


def _write_action(fig, arm, frames):
    act = bpy.data.actions.new(f"Fig_{fig.tag}Loop")
    arm.animation_data_create()
    arm.animation_data.action = act
    slot = arm.animation_data.action_slot
    if slot is None:
        slot = act.slots.new(id_type='OBJECT', name=arm.name)
        arm.animation_data.action_slot = slot
    cb = anim_utils.action_ensure_channelbag_for_slot(act, slot)
    p = fig.tag + "_"
    rest = {b.name: b.matrix_local.copy() for b in arm.data.bones}
    glass_names = {p + g["name"]: g["name"] for g in fig.glasses}
    ale_names = {p + g["name"] + "Ale": g["name"] for g in fig.glasses if g["kind"] == "glass"}
    kept = 0
    for bone in arm.pose.bones:
        name = bone.name
        mats = []
        for rec in frames:
            if name in glass_names:
                base, rot, scale, _fill = rec["glass"][glass_names[name]]
                rs = rest[name]
                want = (Matrix.Translation(base) @ rot.to_4x4() @ rs.to_3x3().to_4x4() @
                        Matrix.Diagonal((scale, scale, scale, 1.0)))
                mats.append(rs.inverted() @ want)
            elif name in ale_names:
                fill = rec["glass"][ale_names[name]][3]
                mats.append(Matrix.Diagonal((1.0, max(0.001, fill), 1.0, 1.0)))
            else:
                mats.append(rec.get(name, Matrix.Identity(4)))
        if all(m == Matrix.Identity(4) for m in mats):
            continue
        locs = [m.to_translation() for m in mats]
        quats = []
        for m in mats:
            q = m.to_quaternion()
            if quats and quats[-1].dot(q) < 0:
                q.negate()
            quats.append(q)
        scales = [m.to_scale() for m in mats]
        for path, values, width, tol in (("location", locs, 3, 0.002), ("rotation_quaternion", quats, 4, 0.0015),
                                         ("scale", scales, 3, 0.002)):
            rows = [[v[i] for v in values] for i in range(width)]
            if all(max(r) - min(r) < 1e-6 for r in rows) and all(abs(r[0] - d) < 1e-6 for r, d in
                                                                  zip(rows, (0, 0, 0) if width == 3 and path == "location"
                                                                      else (1, 1, 1) if width == 3 else (1, 0, 0, 0))):
                continue
            keep = _thin(rows, tol)
            kept += len(keep)
            dp = f'pose.bones["{name}"].{path}'
            for i in range(width):
                fc = cb.fcurves.new(dp, index=i, group_name=name)
                fc.keyframe_points.add(len(keep))
                co = []
                for k in keep:
                    co += [k, rows[i][k]]
                fc.keyframe_points.foreach_set("co", co)
                for kp in fc.keyframe_points:
                    kp.interpolation = 'LINEAR'
                fc.update()
    return act, kept


def _pick_poles(fig, arm):
    saved = fig.loop
    fig.loop = 0.0
    best = {}
    try:
        for kind in ("L", "R") + (("leg",) if fig.legs else ()):
            scores = []
            for deg in (-90, 0, 90, 180):
                a = math.radians(deg)
                fr = _solve(fig, arm, {"L": a, "R": a, "leg": a})[0]
                pb = arm.pose.bones
                for b in pb:
                    if b.name in fr:
                        b.matrix_basis = fr[b.name]
                bpy.context.view_layer.update()
                bone = fig.tag + ("_Shin.L" if kind == "leg" else f"_Forearm.{kind}")
                joint = pb[bone].head
                if kind == "leg":
                    want = fig.to_world(0.0, Vector((-0.12, 1.2, 0.9)))
                else:
                    sx = -1 if kind == "L" else 1
                    want = fig.to_world(0.0, Vector((sx * 0.45, -0.35, 1.0)))
                scores.append(((joint - want).length, a))
            best[kind] = min(scores)[1]
    finally:
        fig.loop = saved
        for b in arm.pose.bones:
            b.matrix_basis = Matrix.Identity(4)
    return best


def _realise(fig, report):
    arm = _build_armature(fig)
    _build_mesh(fig, arm)
    poles = _pick_poles(fig, arm)
    worst = 0.0
    sizes = {g["name"]: GLASS[g["size"]][1] for g in fig.glasses if g["kind"] == "glass"}
    for it in range(8):
        frames = _solve(fig, arm, poles)
        errs = {}
        for c in fig.contacts:
            # Contact: the palm must be where the handover needs it. Legacy
            # tuples name a glass and the spot it stands on; ("palm", t, key,
            # side, want) give the palm position directly (or a function of the
            # frame, for a slot on a tray the other hand carries).
            if c[0] == "palm":
                _tag, t, key, side, want = c
            else:
                t, key, gname, spot = c
                side, want = fig.hand, Vector(spot) + Vector((0, 0, sizes[gname] * 0.47))
            fr = frames[int(round(t * FPS))]
            w = want(fr) if callable(want) else Vector(want)
            errs.setdefault(key, []).append((t, w, w - fr["palm"][side]))
        worst = max((e.length for v in errs.values() for _, _, e in v), default=0.0)
        if worst < 0.004 or it == 7:
            break
        for key, v in errs.items():
            t, _w, e = v[0]                   # correct on the first use; reuses share the pose
            fig.wrist[key] = fig.wrist[key] + fig.rot_at(t).transposed() @ e
    for key, v in errs.items():
        for t, _w, e in v:
            if e.length > 0.006:
                report(f"  {fig.tag} contact '{key}' at {t:.1f}s off by {e.length * 1000:.0f} mm")
    miss = max(((r["wrist"][s] - r["target"][s]).length, i / FPS, s)
               for i, r in enumerate(frames) for s in ("L", "R") if r["vis"] > 0.5)
    _act, kept = _write_action(fig, arm, frames)
    report(f"FIGURE {fig.tag}: {len(frames)} frames -> {kept} keys, contact error {worst * 1000:.1f} mm, "
           f"worst reach miss {miss[0] * 1000:.0f} mm at {miss[1]:.1f}s ({miss[2]})")
    for b in arm.pose.bones:
        b.matrix_basis = Matrix.Identity(4)
    return arm, frames, worst


# --- Choreography helpers -----------------------------------------------------
def segs_from(events, loop, start_mode, start_spot):
    """events: [(t, mode, spot)] -> [(t0, t1, mode, spot)] covering 0..loop. A
    hidden glass waits where it next appears so it never streaks across."""
    events = sorted(events, key=lambda e: e[0])
    out, t0, mode, spot = [], 0.0, start_mode, start_spot
    for t, m, s in events:
        if t > t0:
            out.append((t0, t, mode, spot))
        t0, mode, spot = t, m, (s if s is not None else spot)
    out.append((t0, loop + 1.0, mode, spot))
    for i, (a, b, m, s) in enumerate(out):
        if m == "hidden":
            nxt = [seg for seg in out[i + 1:] + out[:i] if seg[2] == "spot"]
            if nxt:
                out[i] = (a, b, m, nxt[0][3])
    return out


def heading(a, b):
    return math.degrees(math.atan2(-(b[0] - a[0]), b[1] - a[1]))


# Places (world). The corridor runs between the bar stools and the tables.
CY = -12.85
DOORS = {"G": -11.75, "L": -12.95}                 # Gents / Ladies door centres on x -3.70
O1 = Vector((1.45, -14.47, 1.06))                  # bar-top spot where takeaway rounds are poured
O1_STAND = (1.45, -13.98)
SERVE_DT = 8.4                                     # barman: collect -> serve
STAND_FEET = ((-0.10, 0.02, 0.09), (0.10, 0.02, 0.09))
REST = {"bar": ((-0.13, 0.40, 1.11), (0.12, 0.40, 1.11), 8),
        "table": ((-0.15, 0.33, 1.17), (0.15, 0.33, 1.17), 7),
        "stand": ((-0.17, 0.08, 0.86), (0.17, 0.08, 0.86), 3)}
CARRY = {"R": (0.13, 0.26, 1.02), "L": (-0.13, 0.26, 1.02)}


def V(t):
    return Vector(t)


class Mover:
    """A regular: home (seat or standing spot), glass, trips."""

    def __init__(self, tag, look, kind, home, spot, hand, size, door, partner_yaw, nbr_dirs,
                 seat_z=None, stand=None, slide=None, feet=None, lean_reach=16, routes=None, drink=None):
        self.f = Figure(tag, look)
        self.f.hand = hand
        self.kind, self.home, self.spot, self.hand = kind, home, V(spot), hand
        self.door, self.partner_yaw, self.nbr_dirs = door, partner_yaw, nbr_dirs
        self.seat_z, self.stand, self.slide, self.feet = seat_z, stand, slide, feet
        self.lean_reach = lean_reach
        self.seated = seat_z is not None
        self.z_home = (seat_z + 0.08 - 0.93) if self.seated else CARPET
        self.rest = REST["stand"] if not self.seated else REST[kind]
        self.routes = routes or {}
        self.g = self.f.glass("G", size, drink) if size else None
        self.held = False           # glass always in hand (darts players), never set down at home
        self.sip_every = 26.0       # seconds at home per sip
        self.refills, self.deadlines, self.away, self.trips = [], [], [], []
        self.f.wrist["spot"] = None

    def rest_of(self, side):
        """Hand pose at home: the glass hand of a player who holds their drink
        stays at the carry pose."""
        if self.held and side == self.hand:
            return V(CARRY[side])
        return V(self.rest[0] if side == "L" else self.rest[1])

    # pose at home ----------------------------------------------------------
    def at_home(self, t):
        f = self.f
        x, y, yaw = self.home
        f.put(t, x, y, yaw)
        f.zk.add(t, self.z_home)
        fl, fr = self.feet if self.seated else STAND_FEET
        f.fL.add(t, V(fl))
        f.fR.add(t, V(fr))
        f.L.add(t, self.rest_of("L"))
        f.R.add(t, self.rest_of("R"))
        f.lean.add(t, self.rest[2])
        f.vis.add(t, 1.0)

    def hand_keys(self):
        return self.f.R if self.hand == "R" else self.f.L

    def stand_up(self, t, carrying=False):
        f = self.f
        x, y, yaw = self.home
        f.put(t, x, y, yaw)
        f.zk.add(t, self.z_home)
        f.fL.add(t, V(self.feet[0]))
        f.fR.add(t, V(self.feet[1]))
        f.L.hold(t)
        f.R.hold(t)
        if self.slide:
            t += 1.0
            f.put(t, self.slide[0], self.slide[1], yaw)
            f.zk.add(t, self.z_home)
            f.fL.add(t, V(self.feet[0]))
            f.fR.add(t, V(self.feet[1]))
        f.lean.add(t, self.rest[2]).add(t + 0.6, 26).add(t + 1.2, 3)
        t += 1.2
        f.put(t, self.stand[0], self.stand[1], yaw)
        f.zk.add(t, CARPET)
        f.fL.add(t, V(STAND_FEET[0]))
        f.fR.add(t, V(STAND_FEET[1]))
        self._walk_hands(t, carrying)
        return t

    def sit_down(self, t, carrying=False):
        f = self.f
        x, y, yaw = self.home
        f.put(t, self.stand[0], self.stand[1], yaw)
        f.zk.add(t, CARPET)
        f.fL.add(t, V(STAND_FEET[0]))
        f.fR.add(t, V(STAND_FEET[1]))
        f.lean.add(t, 3).add(t + 0.6, 24)
        t += 1.2
        sx, sy = self.slide if self.slide else (x, y)
        f.put(t, sx, sy, yaw)
        f.zk.add(t, self.z_home)
        f.fL.add(t, V(self.feet[0]))
        f.fR.add(t, V(self.feet[1]))
        f.lean.add(t, self.rest[2])
        if self.slide:
            t += 1.0
            f.put(t, x, y, yaw)
            f.zk.add(t, self.z_home)
        if carrying:
            other = f.L if self.hand == "R" else f.R
            other.add(t, V(self.rest[0] if self.hand == "R" else self.rest[1]))
        else:
            f.L.add(t, V(self.rest[0]))
            f.R.add(t, V(self.rest[1]))
        return t

    def _walk_hands(self, t, carrying):
        f = self.f
        st = REST["stand"]
        if carrying or self.held:
            self.hand_keys().add(t, V(CARRY[self.hand]))
            (f.L if self.hand == "R" else f.R).add(t, V(st[0] if self.hand == "R" else st[1]))
        else:
            f.L.add(t, V(st[0]))
            f.R.add(t, V(st[1]))

    def walk(self, t, pts, carrying=False, speed=1.1):
        f = self.f
        pts = [tuple(p) for p in pts]
        hs = [heading(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
        f.put(t, pts[0][0], pts[0][1], f._yaw)
        f.lean.add(t, 3)
        f.pitch.add(t, 3)
        f.yaw.add(t, 0)
        self._walk_hands(t, carrying)
        t += 0.45
        f.put(t, pts[0][0], pts[0][1], hs[0], lin=True)
        cut_prev = 0.0
        for i in range(1, len(pts)):
            a, b = V(pts[i - 1]), V(pts[i])
            d = (b - a).length
            if i < len(pts) - 1:
                c = V(pts[i + 1])
                cut = min(0.3, d / 2, (c - b).length / 2)
                din, dout = (b - a).normalized(), (c - b).normalized()
                t += max(0.05, d - cut_prev - cut) / speed
                pa = b - din * cut
                f.put(t, pa.x, pa.y, hs[i - 1], lin=True)
                t += 2 * cut / speed
                pb = b + dout * cut
                f.put(t, pb.x, pb.y, hs[i], lin=True)
                cut_prev = cut
            else:
                t += max(0.05, d - cut_prev) / speed
                f.put(t, b.x, b.y, hs[i - 1])
        f.lean.add(t, 3)
        f.pitch.add(t, 3)
        f.yaw.add(t, 0)
        self._walk_hands(t, carrying)
        return t

    def turn(self, t, yaw, dur=0.5):
        f = self.f
        cur = f.root[-1][1]
        f.put(t, cur.x, cur.y, f._yaw)
        f.put(t + dur, cur.x, cur.y, yaw)
        return t + dur

    # routes ----------------------------------------------------------------
    def out_pts(self):
        """From the standing spot (or home if standing) to the corridor."""
        if self.kind == "shelf":
            return [self.home[:2]]
        return [self.stand, (self.stand[0], CY)]

    def door_route(self):
        d = DOORS[self.door]
        if self.kind == "shelf":
            mid = {"G": [], "L": [(-2.55, -11.95)]}[self.door]
            return [self.home[:2]] + mid + [(-3.15, d)]
        return self.out_pts() + [(-2.75, CY), (-3.15, d)]

    def bar_route(self):
        if "bar" in self.routes:
            return self.routes["bar"]
        if self.kind == "shelf":
            via = [(-2.55, -11.55), (-1.05, CY)] if self.home[0] < -2.6 else [(-1.75, -11.55), (-0.95, CY)]
            return [self.home[:2]] + via + [(O1_STAND[0], CY), O1_STAND]
        return self.out_pts() + [(O1_STAND[0], CY), O1_STAND]

    # trips -----------------------------------------------------------------
    def reach(self, t, key, spot, mode_after, lean):
        """Hand to the glass at spot by t+0.8 (contact); returns contact time."""
        keys = self.hand_keys()
        keys.hold(t)
        keys.add(t + 0.8, self.f.named(key))
        self.f.lean.hold(t).add(t + 0.8, lean)
        self.f.contacts.append((t + 0.8, key, "G", spot))
        self.g["events"].append((t + 0.8, mode_after, spot if mode_after == "spot" else None))
        return t + 0.8

    def bathroom(self, t, away):
        f = self.f
        t0 = t
        if self.seated:
            t = self.stand_up(t)
        route = self.door_route()
        t = self.walk(t, route)
        d = DOORS[self.door]
        t = self.walk(t, [(-3.15, d), (-4.05, d)], speed=1.0)
        f.vis.add(t, 1.0).add(t + 0.1, 0.001)
        t += away
        f.vis.add(t - 0.1, 0.001).add(t, 1.0)
        t = self.walk(t, [(-4.05, d), (-3.15, d)], speed=1.0)
        t = self.walk(t, list(reversed(route)))
        t = self.turn(t, self.home[2])
        if self.seated:
            t = self.sit_down(t)
        else:
            self.at_home(t)
        f.busy.append((t0 - 0.5, t + 0.8))
        self.away.append((t0, t))
        self.trips.append((t0, t, "wc"))
        return t

    def bar_run(self, t):
        """Take the empty to the bar, wait for the refill, bring it back.
        Returns (t_place, t_collect, t_serve)."""
        f = self.f
        t0 = t
        self.deadlines.append(t)
        tc = self.reach(t, "spot", self.spot, self.hand, self.lean_reach)
        self.hand_keys().add(tc + 0.8, V(CARRY[self.hand]))
        f.lean.add(tc + 0.8, self.rest[2])
        t = tc + 0.8
        if self.seated:
            t = self.stand_up(t, carrying=True)
        route = self.bar_route()
        t = self.walk(t, route, carrying=True)
        t = self.turn(t, 180)
        t_place = self.reach(t, "order", O1, "spot", 24)
        self.hand_keys().add(t_place + 0.8, V(REST["stand"][1 if self.hand == "R" else 0]))
        f.lean.add(t_place + 0.8, 3)
        t_c = t_place + 1.5
        t_s = t_c + SERVE_DT
        f.pitch.add(t_place + 1.0, 8).add(t_s - 2.0, 2).add(t_s, 10)
        f.yaw.add(t_place + 1.0, 0).add(t_place + 3.0, 25).add(t_place + 5.0, 25).add(t_place + 6.0, 0)
        self.g["events"] += [(t_c + EPS, "hidden", None), (t_s - EPS, "spot", O1)]
        self.refills.append(t_s)
        t_pick = self.reach(t_s + 0.4, "order", O1, self.hand, 24)
        self.hand_keys().add(t_pick + 0.8, V(CARRY[self.hand]))
        f.lean.add(t_pick + 0.8, 3)
        t = self.walk(t_pick + 0.8, list(reversed(route)), carrying=True)
        t = self.turn(t, self.home[2])
        if self.seated:
            t = self.sit_down(t, carrying=True)
        t_home = self.reach(t, "spot", self.spot, "spot", self.lean_reach)
        self.hand_keys().add(t_home + 0.8, V(self.rest[1 if self.hand == "R" else 0]))
        f.lean.add(t_home + 0.8, self.rest[2])
        f.busy.append((t0 - 0.5, t_home + 1.3))
        self.trips.append((t0, t_home + 1.3, "run"))
        return t_place, t_c, t_s


def sip(m, t, fill_from, fill_to, tilt=55):
    f, g = m.f, m.g
    keys = m.hand_keys()
    mouth = V((0.05 if m.hand == "R" else -0.05, 0.20, 1.50))
    m.reach(t, "spot", m.spot, m.hand, m.lean_reach)
    keys.add(t + 1.7, mouth).add(t + 3.0, mouth).add(t + 3.9, f.named("spot"))
    f.lean.add(t + 1.7, m.rest[2] - 4).add(t + 3.0, m.rest[2] - 4).add(t + 3.9, m.lean_reach)
    f.pitch.add(t + 1.7, -12).add(t + 3.0, -12)
    g["tilt"].add(t + 1.5, 0).add(t + 2.0, tilt).add(t + 2.7, tilt).add(t + 3.2, 0)
    g["fill"].add(t + 1.9, fill_from).add(t + 2.8, fill_to)
    f.contacts.append((t + 3.9, "spot", "G", m.spot))
    g["events"].append((t + 3.9, "spot", m.spot))
    keys.add(t + 4.5, V(m.rest[1 if m.hand == "R" else 0]))
    f.lean.add(t + 4.5, m.rest[2])


def sip_held(m, t, fill_from, fill_to, tilt=55):
    """A sip from a glass carried in the hand (no spot to pick it up from)."""
    f, g = m.f, m.g
    keys = m.hand_keys()
    hold = V(CARRY[m.hand])
    mouth = V((0.05 if m.hand == "R" else -0.05, 0.20, 1.50))
    keys.add(t, hold).add(t + 1.0, mouth).add(t + 2.3, mouth).add(t + 3.3, hold)
    f.pitch.add(t + 1.0, -12).add(t + 2.3, -12).add(t + 3.3, 3)
    g["tilt"].add(t + 0.8, 0).add(t + 1.3, tilt).add(t + 2.0, tilt).add(t + 2.5, 0)
    g["fill"].add(t + 1.2, fill_from).add(t + 2.1, fill_to)


def plan_sips(m, rng, blocked, sipper=None):
    """Sips between each refill and the next time the glass must be empty;
    the last sip of each pint empties it. Writes sips and fill keys."""
    sipper = sipper or (sip_held if m.held else sip)
    refills = sorted(m.refills)
    deadlines = sorted(m.deadlines)

    def ok(t):
        if t < 1.0 or t + 5.0 > LOOP - 1.0:
            return False
        if not m.f.free(t - 0.6, t + 5.0):
            return False
        return all(t + 5.0 <= a or t - 0.6 >= b for a, b in blocked)

    sips = []
    for i, r in enumerate(refills):
        nxt = [d for d in deadlines if d > r]
        d = nxt[0] if nxt else deadlines[0] + LOOP
        span = d - r
        # Size the pint by the time actually spent at home with it.
        home = sum(0.5 for q in range(int(span * 2)) if ok((r + q * 0.5) % LOOP))
        k = max(2, int(round(home / m.sip_every)))
        chosen = []
        for j in range(k):
            target = r + span * (j + 0.6) / (k + 0.2)
            best = None
            for step in range(0, 400):
                for sgn in (1, -1):
                    tt = target + sgn * step * 0.5
                    if not (r + 2.0 < tt < d - 5.5):
                        continue
                    tm = tt % LOOP
                    if ok(tm) and all(abs(((tm - c) + LOOP / 2) % LOOP - LOOP / 2) > 9.0 for c in chosen + sips):
                        best = tm
                        break
                if best is not None:
                    break
            if best is None:
                raise RuntimeError(f"{m.f.tag}: no room for sip {j + 1}/{k} of the pint poured at {r:.1f}")
            chosen.append(best)
        # Order the pint's sips in drinking order (unwrapped from the refill).
        chosen.sort(key=lambda tm: (tm - r) % LOOP)
        for j, tm in enumerate(chosen):
            sips.append(tm)
            m._pint = getattr(m, "_pint", [])
            m._pint.append((tm, 1.0 - j / k, max(0.001, 1.0 - (j + 1) / k)))
    for tm, a, b in sorted(m._pint):
        sipper(m, tm, a, b)
    # Fill between events: full at each refill, constant otherwise.
    for r in refills:
        m.g["fill"].add(r - 2 * EPS, 0.001).add(r - EPS, 1.0)
    # The level at the seam is whatever the last event of the loop left.
    evts = [(tm + 2.8, b) for tm, a, b in m._pint] + [(r, 1.0) for r in refills]
    level = max(evts)[1]
    m.g["fill"].add(0.0, level).add(LOOP, level)
    return sips


def idle(m, rng):
    """Chat, gesture, laugh, look round in every free gap at home."""
    f = m.f
    gaps = []
    marks = sorted(f.busy + [(s - 0.3, s + 4.8) for s, *_ in getattr(m, "_pint", [])])
    t = 0.3
    for a, b in marks:
        if a - t > 2.0:
            gaps.append((t, a))
        t = max(t, b)
    if LOOP - 0.3 - t > 2.0:
        gaps.append((t, LOOP - 0.3))
    gk = f.L if m.hand == "R" else f.R
    gs = -1 if m.hand == "R" else 1
    for a, b in gaps:
        cur = a
        while b - cur > 1.6:
            dur = min(b - cur, rng.uniform(2.0, 5.5))
            kind = rng.choice(m.kinds)
            m0, m1, mid = cur + 0.4, cur + dur - 0.4, cur + dur / 2
            if kind == "talk":
                d = rng.choice(m.nbr_dirs)
                f.yaw.add(m0, d)
                if m.kind == "bar":
                    gk.add(m0, V((gs * 0.10, 0.36, 1.18))).add(mid, V((gs * 0.04, 0.32, 1.26)))
                else:
                    gk.add(m0, V((gs * 0.16, 0.30, m.rest[0][2] + 0.04)))
                    gk.add(mid, V((gs * 0.10, 0.34, m.rest[0][2] + 0.12 + rng.uniform(-0.03, 0.05))))
                f.pitch.add(m0, 2).add(mid, 6).add(m1, 1)
            elif kind == "listen":
                d = rng.choice(m.nbr_dirs)
                f.yaw.add(m0, d).add(m1, d)
                f.pitch.add(m0, 4).add(mid, 9).add(m1, 4)
            elif kind == "laugh":
                f.yaw.add(m0, rng.choice(m.nbr_dirs) * 0.7)
                f.pitch.add(m0, -14).add(mid, -6).add(m1, 0)
                f.lean.add(mid, m.rest[2] - 5)
            elif kind == "room":
                d = rng.choice([60, -60])
                f.yaw.add(m0, d * 0.6).add(m1, d * 0.6)
                f.pitch.add(m0, -2).add(m1, -2)
            elif kind == "clap":
                f.yaw.add(m0, m.partner_yaw)
                for q in range(4):
                    tq = m0 + q * 0.3
                    if tq + 0.15 > m1:
                        break
                    f.L.add(tq, V((-0.07, 0.30, 1.22))).add(tq + 0.15, V((-0.025, 0.30, 1.22)))
                    f.R.add(tq, V((0.07, 0.30, 1.22))).add(tq + 0.15, V((0.025, 0.30, 1.22)))
                f.L.add(cur + dur, V(m.rest[0]))
                f.R.add(cur + dur, V(m.rest[1]))
                f.pitch.add(m0, 0).add(m1, 2)
            elif kind == "lean":
                f.lean.add(m0, 18).add(m1, 18)
                f.R.add(m0, V((0.10, 0.44, 1.10))).add(m1, V((0.10, 0.44, 1.10)))
                f.L.add(m0, V((-0.10, 0.44, 1.10))).add(m1, V((-0.10, 0.44, 1.10)))
                f.pitch.add(m0, 12).add(m1, 12)
            gk.add(cur + dur, V(m.rest[0] if m.hand == "R" else m.rest[1]))
            if kind == "lean":
                f.L.add(cur + dur, V(m.rest[0]))
                f.R.add(cur + dur, V(m.rest[1]))
            f.lean.add(cur + dur, m.rest[2])
            f.yaw.add(cur + dur, m.partner_yaw)
            cur += dur


# --- The cast -----------------------------------------------------------------
BAR_FEET = ((-0.12, 0.20, 0.36), (0.12, 0.22, 0.36))
STOOL_Y = -13.92
TF_SPOT = (1.25, -10.90, TABLE_Z)
TM_SPOT = (1.38, -11.28, TABLE_Z)


def _cast():
    A = Mover("BarA", dict(sex="m", skin="d7a07e", hair="8c8279", cap="5b4a3a", top="d9d2c3", jacket="6b5440",
                           legs="54524f", sleeves="long"), "bar", (1.90, STOOL_Y, 180), (1.90, -14.50, TRAY_Z),
              "R", "pint", "G", 0, [-35], seat_z=0.85, stand=(1.90, -13.45), feet=BAR_FEET)
    B = Mover("BarB", dict(sex="f", skin="e3b393", hair="8a3b1e", hair_style="bob", top="2f6b4f", legs="2b2b33",
                           sleeves="long", lips="a8454b"), "bar", (2.80, STOOL_Y, 180), (2.80, -14.50, TRAY_Z),
              "R", "half", "L", 0, [35, -35], seat_z=0.85, stand=(2.80, -13.45), feet=BAR_FEET)
    C = Mover("BarC", dict(sex="m", skin="b98563", hair="1e1612", beard=True, top="e6e1d6", jacket="3d5a80",
                           legs="2a2f3a", sleeves="long"), "bar", (3.70, STOOL_Y, 180), (3.62, -14.50, TRAY_Z),
              "R", "pint", "G", 0, [35], seat_z=0.85, stand=(3.70, -13.45), feet=BAR_FEET, drink="lager")
    # The booth table couple is served by the barmaid: a glass of white for
    # her, a pint of bitter for him (he drinks left-handed so both glasses sit
    # on the side she serves from).
    TF = Mover("TblF", dict(sex="f", skin="eec3a4", hair="d4b26a", hair_style="long", top="3a6fb0", legs="2d3550",
                            sleeves="long", lips="b04a55"), "table", (1.35, -10.40, 180),
               TF_SPOT, "R", "wine", "L", 6, [6], seat_z=0.55, stand=(0.85, -10.80),
               slide=(0.85, -10.40), feet=((-0.11, 0.43, 0.42), (0.11, 0.43, 0.42)), drink="white")
    TM = Mover("TblM", dict(sex="m", skin="e0b08f", hair="9a948c", top="283a5c", legs="3a3f4a", sleeves="long",
                            glasses="2a2a2a"), "table", (1.50, -11.78, 0), TM_SPOT, "L", "pint",
               "G", -6, [-6], seat_z=0.56, stand=(1.50, -12.18), feet=((-0.12, 0.42, 0.42), (0.12, 0.40, 0.42)))
    SM = Mover("ShfM", dict(sex="m", skin="c48b66", hair="2c2420", hair_style="bald", beard=True, top="8a2f2a",
                            legs="34404f", sleeves="rolled"), "shelf", (-3.20, -10.62, -55),
               (-2.95, -10.24, SHELF_Z), "L", "pint", "G", -30, [-30], lean_reach=14, drink="stout")
    SF = Mover("ShfF", dict(sex="f", skin="f0c7a8", hair="241a16", hair_style="ponytail", top="e6dfd2",
                            jacket="2a2422", legs="2a2a30", skirt="2a2a30", sleeves="long"), "shelf",
               (-2.05, -10.62, 55), (-2.35, -10.24, SHELF_Z), "R", "half", "L", 30, [30], lean_reach=14,
               drink="lager")
    # The darts fan by the end of the bar return; her way to the bar keeps
    # clear of the darts players' waiting row.
    DF = Mover("DtF", dict(sex="f", skin="f1c9ab", hair="a0402a", hair_style="long", top="c9a63a", legs="26263a",
                           skirt="26263a", sleeves="long", lips="b04a55"), "shelf", (-0.70, -13.95, 161),
               (-0.95, -14.30, 1.06), "R", "half", "L", 0, [0, 0, -25, 35], lean_reach=14, drink="cider",
               routes={"bar": [(-0.70, -13.95), (-0.45, -13.45), (1.20, -13.45), O1_STAND]})
    DF.kinds = ["listen", "listen", "clap", "talk", "room", "laugh"]
    for m in (A, B, C):
        m.kinds = ["talk", "talk", "listen", "laugh", "room", "lean"]
    for m in (TF, TM, SM, SF):
        m.kinds = ["talk", "talk", "listen", "listen", "laugh", "room"]
    return dict(A=A, B=B, C=C, TF=TF, TM=TM, SM=SM, SF=SF, DF=DF)




# --- The hot tub (SW terrace) ---------------------------------------------------
# Two friends in the water on the south seats (their backs to the deck, facing
# the two north seats left free for visitors) and a third sitting on the south
# coping between them with her feet in the water. Their cocktails stand on the
# coping behind them, where the barmaid can reach from the deck: a pina colada
# in a pineapple for her in the water, a tequila sunrise for him, a punch for
# the one on the side, highballs with a straw and a wheel of orange. Now and
# then one of them fishes the beach ball out of the water and they throw it
# round for a while, then it goes back in and floats.
TUB_WATER = 0.555
TUB_COPE = 0.753                                   # travertine coping top
TUB_LOOKS = {
    "TubA": dict(sex="f", skin="eec3a4", hair="5a3a24", hair_style="bun", top="1e7a8a", hips="1e7a8a",
                 legs="eec3a4", shoes="eec3a4", sleeves="none", collar=False, neckline=True, lips="b04a55",
                 shorts="1e7a8a"),
    "TubB": dict(sex="m", skin="d9a585", hair="2a211c", top="d9a585", hips="c8402a", shorts="c8402a",
                 legs="d9a585", shoes="d9a585", sleeves="none", collar=False),
    "TubS": dict(sex="f", skin="f0c7a8", hair="8a3b1e", hair_style="long", top="e04a6a", hips="e04a6a",
                 legs="f0c7a8", shoes="f0c7a8", sleeves="none", collar=False, neckline=True, lips="b03a48",
                 shorts="e04a6a", earrings="d8b450"),
}
# In the water: hips on the bench line (z 0.36), legs out along the floor.
TUB_IN_Z = 0.36 - 0.93
TUB_IN_FEET = ((-0.13, 0.74, 0.86), (0.13, 0.72, 0.86))
TUB_IN_REST = ((-0.44, -0.22, 1.33), (0.40, -0.24, 1.33), -10)       # arms along the coping behind
# On the coping: hips on the stone, feet in the water.
TUB_SIDE_Z = TUB_COPE + 0.08 - 0.93
TUB_SIDE_FEET = ((-0.12, 0.50, 0.48), (0.12, 0.52, 0.50))
TUB_SIDE_REST = ((-0.24, -0.02, 0.89), (0.24, -0.02, 0.89), 12)      # hands on the stone beside her
TUB_HOME = {"TubA": (-10.40, -8.10, 0.0), "TubB": (-9.10, -8.10, 0.0), "TubS": (-9.75, -8.55, 0.0)}
TUB_SPOT = {"TubA": (-10.68, -8.68, TUB_COPE), "TubB": (-8.82, -8.68, TUB_COPE),
            "TubS": (-9.38, -8.68, TUB_COPE)}
TUB_DRINK = {"TubA": ("pineapple", "colada", "L"), "TubB": ("highball", "sunrise", "R"),
             "TubS": ("highball", "punch", "R")}
BALL_R = 0.17
BALL_HOME = Vector((-9.75, -7.90, TUB_WATER + 0.12))     # where it floats between games
TUB_GAMES = (18.0, 104.0, 196.0)                   # first pick-up of each game (s)


def _tub_cast():
    out = {}
    for tag, (x, y, yaw) in TUB_HOME.items():
        size, drink, hand = TUB_DRINK[tag]
        side = tag == "TubS"
        m = Mover(tag, TUB_LOOKS[tag], "table", (x, y, yaw), TUB_SPOT[tag], hand, size, None, 0,
                  [40, -40] if side else ([-40, 30] if tag == "TubA" else [40, -30]),
                  seat_z=0.0, feet=TUB_SIDE_FEET if side else TUB_IN_FEET, lean_reach=10 if side else -6,
                  drink=drink)
        m.z_home = TUB_SIDE_Z if side else TUB_IN_Z
        m.rest = TUB_SIDE_REST if side else TUB_IN_REST
        m.sip_every = 40.0
        m.kinds = ["talk", "talk", "listen", "listen", "laugh", "room"]
        m.tub = True
        out[tag] = m
    return out


def _tub_local(m, world, turn=0.0):
    """World point -> m's body frame with the body turned `turn` degrees."""
    x, y, yaw = m.home
    p = Vector((x, y, m.z_home))
    return Matrix.Rotation(-math.radians(yaw + turn), 3, 'Z') @ (Vector(world) - p)


def _rel(m, xy):
    a = heading(m.home[:2], xy) - m.home[2]
    return (a + 180.0) % 360.0 - 180.0


def _aim(pose, ang):
    """A pair of local hand targets turned to face `ang` degrees."""
    r = Matrix.Rotation(math.radians(max(-75.0, min(75.0, ang))), 3, 'Z')
    return r @ V(pose)


def _ball_float(t):
    """Where the ball floats at time t: a slow drift round its home spot."""
    return BALL_HOME + Vector((0.10 * math.sin(t * 0.21), 0.07 * math.sin(t * 0.17 + 1.0),
                               0.012 * math.sin(t * 2.1)))


def _tub_games(tub, rng):
    """Author the ball games: hands, heads, body turns. Returns the ball's
    script [(kind, ...)] for the prop rig keyed after the solve."""
    tags = list(tub)
    ev = []
    HOLD_P = (0.15, 0.30, 1.28)
    WIND_P = (0.15, 0.10, 1.70)
    REL_P = (0.15, 0.42, 1.58)
    READY_P = (0.16, 0.42, 1.47)

    def pair(m, pose, ang, t, lean=None):
        lp = _aim(V((-pose[0], pose[1], pose[2])), ang)
        rp = _aim(V(pose), ang)
        m.f.L.add(t, lp)
        m.f.R.add(t, rp)
        if lean is not None:
            m.f.lean.add(t, lean)

    def rest(m, t):
        m.f.L.add(t, V(m.rest[0]))
        m.f.R.add(t, V(m.rest[1]))
        m.f.lean.add(t, m.rest[2])

    for gi, t0 in enumerate(TUB_GAMES):
        turn = {}
        for tag, m in tub.items():
            others = [tub[o].home[:2] for o in tags if o != tag]
            cx = sum(o[0] for o in others) / 2
            cy = sum(o[1] for o in others) / 2
            turn[tag] = max(-28.0, min(28.0, _rel(m, (cx, cy)) * 0.6))
        picker = tags[gi % 3] if tags[gi % 3] != "TubS" else "TubA"
        # Turn towards the game, the picker leans in for the ball.
        t = t0 - 1.6
        for tag, m in tub.items():
            x, y, yaw = m.home
            m.f.put(t, x, y, yaw)
            m.f.put(t + 0.8, x, y, yaw + turn[tag])
            m.f.L.hold(t)
            m.f.R.hold(t)
            m.f.lean.hold(t)
            m.f.yaw.add(t + 0.8, 0)
        P = tub[picker]
        F = _ball_float(t0)
        d = (F - V((P.home[0], P.home[1], F.z)))
        d.z = 0
        side = Vector((-d.y, d.x, 0)).normalized() * BALL_R
        for sgn, keys in ((1, P.f.L), (-1, P.f.R)):
            keys.add(t0, _tub_local(P, F + side * sgn, turn[picker]))
        P.f.lean.add(t0, 38)
        P.f.pitch.add(t0 - 0.8, 20).add(t0 + 0.6, 4)
        ev.append(("pick", picker, t0))
        pair(P, HOLD_P, 0.0, t0 + 0.8, P.rest[2])
        holder, t = picker, t0 + 0.8 + rng.uniform(0.6, 1.2)
        n = rng.randint(6, 9)
        for k in range(n):
            catcher = rng.choice([o for o in tags if o != holder])
            H, C = tub[holder], tub[catcher]
            dist = (V(H.home[:2]) - V(C.home[:2])).length
            fly = 0.85 + 0.18 * dist
            t_r = t + 0.55
            t_c = t_r + fly
            a_hc = _rel(H, C.home[:2]) - turn[holder]
            a_ch = _rel(C, H.home[:2]) - turn[catcher]
            pair(H, WIND_P, a_hc * 0.5, t + 0.1)
            pair(H, REL_P, a_hc, t_r)
            rest(H, t_r + 0.7)
            pair(C, READY_P, a_ch, t_c - 0.55)
            pair(C, READY_P, a_ch, t_c)
            pair(C, HOLD_P, 0.0, t_c + 0.55)
            ev.append(("throw", holder, catcher, t_r, t_c))
            for tag, m in tub.items():                 # everyone watches the ball
                look = lambda target: max(-70.0, min(70.0, _rel(m, target) - turn[tag]))
                if tag != holder:
                    m.f.yaw.add(t + 0.1, look(H.home[:2]))
                if tag != catcher:
                    m.f.yaw.add(t_r + fly * 0.6, look(C.home[:2]))
                else:
                    m.f.yaw.add(t_c - 0.5, look(H.home[:2]) * 0.6)
            if rng.random() < 0.35:                    # a laugh at a scrappy catch
                C.f.pitch.add(t_c + 0.3, 2).add(t_c + 0.8, -14).add(t_c + 1.6, 2)
            holder, t = catcher, t_c + rng.uniform(0.9, 2.2)
        # Back in the water it goes.
        H = tub[holder]
        F = _ball_float(t + 1.6)
        a = _rel(H, F.xy) - turn[holder]
        pair(H, WIND_P, a * 0.4, t + 0.1)
        pair(H, REL_P, a, t + 0.55)
        rest(H, t + 1.2)
        ev.append(("drop", holder, t + 0.55, t + 1.6))
        t_end = t + 2.2
        for tag, m in tub.items():
            x, y, yaw = m.home
            m.f.put(t_end, x, y, yaw + turn[tag])
            m.f.put(t_end + 0.8, x, y, yaw)
            rest(m, t_end + 0.8)
            m.f.yaw.add(t_end + 0.8, m.partner_yaw)
            m.f.pitch.add(t_end + 0.8, 4)
            m.f.busy.append((t0 - 2.2, t_end + 1.4))
            m.trips.append((t0 - 2.2, t_end + 1.4, "ball"))
    return ev

# --- Darts --------------------------------------------------------------------
# Board on the back wall at DART_X (bull 1.80 m), oche 2.37 m out, chalk
# scoreboard on the back wall west of the cabinet. Two teams of two play the
# whole loop: step up, three darts (each flies and sticks), walk up and pull
# them, chalk the score, walk back. The next player steps up only once the
# last is back (or gone off through the gap in the waiting row), so nobody
# crosses the lane during a throw. Each holds their drink in the left hand.
# Now and then a player heads off straight after chalking, to the Gents or the
# Ladies or up to the bar for a refill (the barman pulls it), and is back
# before their next turn. The last scorer wipes the board and the game
# restarts with the loop; turns are spread so there is no idle stretch.
DART_X = -1.85
BOARD_Y = -16.494
BULL = Vector((DART_X, BOARD_Y, 1.80))
OCHE = (DART_X, -14.15)
PULL_STAND = (DART_X, -16.12)
SCORE_STAND = (-2.70, -16.12)
SCORE_FACE_Y = -16.527
SCORE_X = {1: -2.82, 2: -2.58}
SCORE_TOP, SCORE_ROW = 1.88, 0.05
DART_COLOUR = {1: "b0202a", 2: "1f4fa8"}
DART_WAIT = {"DtA": (-3.35, -13.40), "DtC": (-2.85, -13.40), "DtB": (-1.70, -13.40), "DtD": (-1.25, -13.40)}
DART_LINE_Y = -13.95                 # walking line between the wait row and the oche
DART_TEAM = {"DtA": 1, "DtB": 2, "DtC": 1, "DtD": 2}
DART_BACK = [(-2.15, -16.12), (-2.15, -14.70), (-2.15, DART_LINE_Y)]   # clear of the piano stool
DART_GAP = (-2.20, -13.40)           # the gap in the waiting row, out to the hall
DART_HALL = (-2.20, CY)
DART_DRINK = {"DtA": ("pint", "bitter"), "DtC": ("pint", "lager")}     # the other two are not drinking
DART_TRIPS = {1: "wc", 4: "bar", 6: "bar", 11: "wc"}   # straight after turn i
DART_ORDER = ["DtA", "DtB", "DtC", "DtD"]


def path_len(pts):
    return sum((V(b) - V(a)).length for a, b in zip(pts, pts[1:]))


def walk_time(pts, speed=1.1):
    """Mover.walk's duration for a route (0.45 s to turn into it)."""
    return 0.45 + path_len(pts) / speed


def alloc_pour(pours, t_min, gap=5.0):
    """Earliest collect time >= t_min the barman can fit a pour (SERVE_DT
    long, gap seconds clear of every other pour)."""
    t = t_min
    for _ in range(4000):
        if all(t + SERVE_DT + gap <= p[0] or t >= p[1] + gap for p in pours):
            return t
        t += 0.25
    raise RuntimeError("barman fully booked")


def _dart_players():
    looks = {
        "DtA": dict(sex="m", skin="e2b08e", hair="b5532a", moustache=True, top="d8c9a8", legs="3b3b40",
                    sleeves="long"),
        "DtB": dict(sex="m", skin="c69070", hair="16110e", glasses="1a1a1a", top="2e5e3a", legs="35465e",
                    sleeves="rolled"),
        "DtC": dict(sex="m", skin="dcae92", hair="a3a3a3", hair_style="bald", top="6a2430", legs="2c2c30",
                    sleeves="long"),
        "DtD": dict(sex="f", skin="e9bc9c", hair="5a3a22", hair_style="bob", top="5b3a78", legs="25252b",
                    sleeves="long", lips="a8454b"),
    }
    out = {}
    for tag, (x, y) in DART_WAIT.items():
        yaw = heading((x, y), (BULL.x, BULL.y))
        size, drink = DART_DRINK.get(tag, (None, None))
        door = "L" if looks[tag]["sex"] == "f" else "G"
        m = Mover(tag, looks[tag], "stand", (x, y, yaw), O1, "L", size, door, 0, [0, 0, 35, -35], drink=drink)
        m.held = size is not None
        m.kinds = ["listen", "listen", "talk", "laugh", "room"]
        m.darts = []
        for k in range(3):
            d = m.f.prop(f"Dart{k}", "dart", V((x, y, 1.0)), DART_COLOUR[DART_TEAM[tag]])
            d["slot"] = k
            m.darts.append(d)
        out[tag] = m
    return out


def _dart_turn(m, T, mark, rng, wipe_marks=None, trip=None):
    """One turn from the wait spot. Returns (release, gone): the time the
    next player may step up, and whether this one went off through the gap
    (the caller then authors the trip)."""
    f = m.f
    hold = m.rest_of("L")
    t = m.walk(T, [m.home[:2], (m.home[0], DART_LINE_Y), (OCHE[0], DART_LINE_Y), OCHE])
    t = m.turn(t, 180, 0.4)
    aim, wind = V((0.14, 0.28, 1.58)), V((0.17, 0.08, 1.63))
    rel, fol = V((0.15, 0.47, 1.58)), V((0.13, 0.52, 1.42))
    f.R.add(t + 0.4, aim)
    f.L.add(t + 0.4, hold)
    f.lean.add(t + 0.4, 6)
    f.pitch.add(t + 0.4, -2)
    f.yaw.add(t + 0.4, 0)
    t += 1.0
    stuck = []
    for k, d in enumerate(m.darts):
        tk = t + k * 1.6
        f.R.add(tk - 0.5, aim).add(tk - 0.2, wind).add(tk, rel).add(tk + 0.18, fol).add(tk + 0.8, aim)
        f.lean.add(tk, 10).add(tk + 0.6, 6)
        hit = BULL + V((rng.uniform(-0.11, 0.11), 0, rng.uniform(-0.11, 0.11)))
        tip = V((hit.x, BOARD_Y + 0.004, hit.z))
        rot = (Matrix.Rotation(rng.uniform(-0.12, 0.12), 3, 'X') @ Matrix.Rotation(rng.uniform(-0.12, 0.12), 3, 'Z')
               @ V((0, 1, 0)).to_track_quat('Z', 'Y').to_matrix())
        d["events"] += [(tk, "fly", (tip, rot)), (tk + 0.3, "spot", (tip, rot))]
        stuck.append(tip)
    t += 2 * 1.6 + 0.9
    f.R.add(t, V(REST["stand"][1]))
    f.L.add(t, hold)
    f.lean.add(t, 3)
    t = m.walk(t, [OCHE, PULL_STAND])
    t = m.turn(t, 180, 0.4)
    f.pitch.add(t, -8)
    for k, d in enumerate(m.darts):
        tp = t + 0.5 + k * 0.55
        f.R.add(tp, f.at_world(stuck[k] + V((0.0, 0.14, -0.03))))
        d["events"].append((tp, "R", None))
    t += 0.5 + 3 * 0.55 + 0.2
    f.R.add(t, V(REST["stand"][1]))
    f.pitch.add(t, 3)
    t = m.walk(t, [PULL_STAND, SCORE_STAND])
    t = m.turn(t, 180, 0.4)
    w0 = t + 0.3

    def scribble(tt, mark=mark, w0=w0):
        q = tt - w0
        return f.to_local(tt, mark + V((0.012 * math.sin(q * 14), 0.11, -0.07 + 0.006 * math.cos(q * 9))))
    f.R.add(w0, scribble).add(w0 + 1.6, scribble)
    f.pitch.add(w0, 10).add(w0 + 1.6, 10)
    f.lean.add(w0, 5)
    m.writes.append((w0, w0 + 1.6))
    t = w0 + 1.9
    if wipe_marks:
        # Game over: rub the whole board out, top row to bottom.
        def rub(tt, t0=t):
            q = (tt - t0) / 3.0
            z = SCORE_TOP + 0.02 - q * (SCORE_TOP - (SCORE_TOP - 11 * SCORE_ROW) + 0.04)
            x = -2.70 + 0.16 * math.sin((tt - t0) * 7)
            return f.to_local(tt, V((x, SCORE_FACE_Y + 0.11, z - 0.07)))
        f.R.add(t, rub).add(t + 3.0, rub)
        for g, row_z in wipe_marks:
            th = t + 3.0 * (SCORE_TOP + 0.02 - row_z) / (11 * SCORE_ROW + 0.04)
            g["scale"].add(th, 1.0).add(th + 0.2, 0.001)
        t += 3.3
    f.R.add(t, V(REST["stand"][1]))
    f.pitch.add(t, 3)
    if trip:
        t = m.walk(t, [SCORE_STAND] + DART_BACK[:2] + [DART_GAP])
        f.busy.append((T - 0.3, t + 0.2))
        return t, True
    t = m.walk(t, [SCORE_STAND] + DART_BACK + [(m.home[0], DART_LINE_Y), m.home[:2]])
    t = m.turn(t, m.home[2])
    f.busy.append((T - 0.3, t + 0.4))
    return t, False


def _dart_back_home(m, t, pts):
    t = m.walk(t, pts + [(m.home[0], CY), m.home[:2]])
    return m.turn(t, m.home[2])


def _dart_wc(m, t, t_by):
    """From the gap to the toilets and back to the wait spot by t_by.
    Returns the end time, or None if there is no time for it."""
    f = m.f
    d = DOORS[m.door]
    out = [DART_GAP, DART_HALL, (-2.75, CY), (-3.15, d)]
    back = [(-3.15, d), (m.home[0], CY), m.home[:2]]
    travel = walk_time(out) + 2 * walk_time([(-3.15, d), (-4.05, d)], 1.0) + walk_time(back) + 0.5
    away = min(40.0, t_by - t - travel)
    if away < 10.0:
        return None
    t0 = t
    t = m.walk(t, out)
    t = m.walk(t, [(-3.15, d), (-4.05, d)], speed=1.0)
    f.vis.add(t, 1.0).add(t + 0.1, 0.001)
    t += away
    f.vis.add(t - 0.1, 0.001).add(t, 1.0)
    t = m.walk(t, [(-4.05, d), (-3.15, d)], speed=1.0)
    t = _dart_back_home(m, t, [(-3.15, d)])
    f.busy.append((t0, t + 0.8))
    m.away.append((t0, t))
    m.trips.append((t0, t, "dwc"))
    return t


def _dart_bar(m, t, t_by, pours):
    """From the gap up to the bar: hand the empty over, wait for the refill,
    back to the wait spot by t_by. Returns the end time, or None."""
    f = m.f
    out = [DART_GAP, DART_HALL, (O1_STAND[0], CY), O1_STAND]
    back = [O1_STAND, (O1_STAND[0], CY)]
    t_arr = t + walk_time(out) + 0.5
    t_c = alloc_pour(pours, t_arr + 2.3)
    t_s = t_c + SERVE_DT
    if t_s + 2.0 + walk_time(back + [(m.home[0], CY), m.home[:2]]) + 0.5 > t_by:
        return None
    t0 = t
    m.deadlines.append(t0)
    t = m.walk(t, out, carrying=True)
    t = m.turn(t, 180)
    if t_c - 2.3 - t > 6.0:                   # waiting for the barman: a look along the bar
        f.pitch.add(t + 0.5, 6).add(t_c - 2.3, 4)
        f.yaw.add(t + 0.5, 0).add(t + 2.0, -20).add(t + 4.0, -20).add(t + 5.0, 0)
    t_place = m.reach(t_c - 2.3, "order", O1, "spot", 24)
    m.hand_keys().add(t_place + 0.8, V(REST["stand"][0]))
    f.lean.add(t_place + 0.8, 3)
    f.pitch.add(t_place + 1.0, 8).add(t_s - 2.0, 2).add(t_s, 10)
    f.yaw.add(t_place + 1.0, 0).add(t_place + 3.0, 25).add(t_place + 5.0, 25).add(t_place + 6.0, 0)
    m.g["events"] += [(t_c + EPS, "hidden", None), (t_s - EPS, "spot", O1)]
    m.refills.append(t_s)
    pours.append((t_c, t_s, "sO1", O1, (m.g["size"], m.g["ale"])))
    t_pick = m.reach(t_s + 0.4, "order", O1, m.hand, 24)
    m.hand_keys().add(t_pick + 0.8, V(CARRY[m.hand]))
    f.lean.add(t_pick + 0.8, 3)
    t = _dart_back_home(m, t_pick + 0.8, back)
    f.busy.append((t0, t + 0.8))
    m.trips.append((t0, t, "dbar"))
    return t


def _dart_sequence(players, n, slack, pours=None, starts=None):
    """Lay n turns into the timeline from 0.3 s, `slack` seconds of waiting
    before each. With pours and the turn start times of a dry run, the trips
    are authored too. Returns (end, turn start times)."""
    rng = random.Random("darts")
    for m in players.values():
        m.writes = []
    rows = {1: 0, 2: 0}
    turns, marks = [], []
    for i in range(n):
        tag = DART_ORDER[i % 4]
        team = DART_TEAM[tag]
        row = rows[team]
        rows[team] += 1
        pos = V((SCORE_X[team], SCORE_FACE_Y, SCORE_TOP - row * SCORE_ROW))
        g = players[tag].f.prop(f"Mark{row:02d}", "mark", pos)
        g["segs"] = [(0.0, LOOP + 1.0, "spot", (pos, Matrix.Identity(3)))]
        marks.append((g, pos.z, tag))
        turns.append((tag, pos, g))
    T = 0.3
    out = []
    for i, (tag, pos, g) in enumerate(turns):
        m = players[tag]
        last = i == n - 1
        T += slack
        out.append(T)
        trip = DART_TRIPS.get(i) if i < n - 4 else None
        release, gone = _dart_turn(m, T, pos, rng, [(gg, z) for gg, z, _t in marks] if last else None, trip)
        w0, w1 = m.writes[-1]
        g["scale"].add(0.0, 0.001).add(w0, 0.001).add(w1, 1.0)
        if gone and pours is not None:
            t_by = starts[i + 4] - 0.5
            done = None
            if trip == "bar" and m.g:
                done = _dart_bar(m, release, t_by, pours)
            if done is None:
                done = _dart_wc(m, release, t_by)
            if done is None:
                done = _dart_back_home(m, release, [DART_GAP, DART_HALL])
        T = release + 0.3
    for g, _z, _t in marks:
        g["scale"].add(LOOP, 0.001)
        g["scale"].sort(key=lambda kv: kv[0])
    return T, out


def _darts_game(players, pours):
    """Author the whole game into the shared timeline: as many turns as fit,
    spread so the game fills the loop."""
    def scratch():
        ps = _dart_players()
        for m in ps.values():
            m.at_home(0.0)
        return ps
    n = None
    for k in range(22, 11, -1):
        end, _s = _dart_sequence(scratch(), k, 0.0)
        if end <= LOOP - 0.3:
            n, end0 = k, end
            break
    if n is None:
        raise RuntimeError("darts game does not fit the loop")
    slack = (LOOP - 0.3 - end0) / n
    _e, starts = _dart_sequence(scratch(), n, slack)
    starts = starts + [s + LOOP for s in starts]
    end, _s = _dart_sequence(players, n, slack, pours, starts)
    if end > LOOP + 1e-6:
        raise RuntimeError(f"darts game overruns the loop ({end:.1f}s)")
    for m in players.values():
        for d in m.darts:
            d["segs"] = segs_from(d["events"], LOOP, "R", None)
    return n, slack


# One pattern: bathroom trips (about one a minute), takeaway rounds, and the
# barman's refills for the three on the stools (collect times). The booth
# couple no longer fetch their own: the barmaid serves them.
PATTERN = dict(
    wc=[("A", 15, 70), ("SF", 70, 70), ("TM", 150, 70), ("C", 180, 70), ("TF", 240, 70), ("SM", 272, 70)],
    runs=[("SM", 112), ("SF", 210), ("DF", 290)],
    bar=[("C", 48), ("B", 92), ("A", 150), ("B", 255), ("C", 292), ("A", 320)],
)


# --- The barmaid ----------------------------------------------------------------
# Her station is the end of the bar by the lifted flap (the end stool is gone):
# the tray rests on the bar there, with the red and the white beside it. She
# pours the wine herself from the bottle into a glass standing on the tray;
# pints she sets on the bar at O2 for the barman, who pulls them at the fourth
# pump like any other refill. The reserved table by the front window (TABLES_A
# second table, seats Seat_RovA3/A4/TA2 left free for visitors) has two sets of
# a red wine and a pint of bitter: twice a loop she brings the fresh set, takes
# the old one back and parks it on the bar until the next round, so the table
# always has its drinks; they go down slowly between rounds.
STN = (0.95, -13.98)                               # where she stands at her station
TRAY_SPOT = Vector((0.95, -14.48, 1.06))
BOTTLE_SPOT = {"red": Vector((0.58, -14.42, 1.06)), "white": Vector((0.62, -14.28, 1.06))}
PARK = {"wine": Vector((0.72, -14.27, 1.06)), "pint": Vector((1.20, -14.27, 1.06))}
O2 = Vector((1.20, -14.47, 1.06))                  # where the barman fills her pints
JAY = {"wine": Vector((3.89, -10.95, TABLE_Z)), "pint": Vector((3.89, -11.22, TABLE_Z))}
JAY_TABLE = Vector((4.15, -11.05, 0.0))
LEFT_AT = 0.15                                     # what a round on the reserved table is down to
PNO_SPOT = Vector((-3.17, -15.05, 1.35))           # the pianist's stout, on top of the piano
PNO_SEAT = (-2.62, -15.50, 90)
TRAY_HOLD = Vector((-0.26, 0.24, 1.12))            # left wrist carrying the tray
WTR_STOPS = {                                      # stand, what she faces, route out from the station
    "JT": ((3.58, -11.00), (4.15, -11.02), [STN, (1.30, -12.90), (3.10, -11.95), (3.58, -11.00)]),
    "TT": ((1.00, -11.20), (1.25, -10.90), [STN, (0.80, -12.60), (1.00, -11.20)]),
    "PS": ((-2.82, -14.60), (-3.17, -15.05), [STN, (0.60, CY), DART_HALL, DART_GAP, (-2.55, -14.05),
                                              (-2.82, -14.60)]),
}
# Out of the Rovers' front door, west along the ground balcony past the spa
# lounge, round the towel basket and along the deck behind the hot tub.
WTR_TUB_ROUTE = [STN, (0.30, CY), (-0.65, -11.10), (-0.65, -9.30), (-1.20, -7.45), (-7.40, -7.45),
                 (-7.55, -8.95), (-8.82, -8.98)]
# She stands square behind each drink on the coping; from the one on the side
# to the far one she steps back to keep clear of her.
WTR_TUB_HOPS = {"TS": [(-8.82, -8.98), (-9.38, -8.98)],
                "TA": [(-9.38, -8.98), (-9.38, -9.08), (-10.55, -9.08), (-10.55, -8.98)]}
WTR_TUB_BACK = [(-10.55, -8.98), (-10.55, -9.08), (-9.38, -9.08), (-9.00, -8.98), (-7.55, -8.95)]   # (clear of
#                                                         the planter at the deck's south-east corner)
MIX_HAND = V((0.20, 0.30, 0.90))                   # down behind the counter front, where the glasses live
TUB_REACH = 45
TUB_DIP = 0.14
WTR_LOOK = dict(sex="f", skin="f2c6a6", hair="e3c27e", hair_style="updo", top="a8283a", legs="1e1e24",
                skirt="1e1e24", sleeves="long", lips="b03a48", earrings="d8b450")


def _rz(deg):
    return Matrix.Rotation(math.radians(deg), 3, 'Z')


class Waitress:
    def __init__(self):
        f = Figure("Wtr", WTR_LOOK)
        f.hand = "R"
        self.f = f
        self.trips = []
        self.x, self.y, self.yaw = STN[0], STN[1], 180.0
        self.n = 0
        self.tray = f.prop("Tray", "tray", TRAY_SPOT)
        f.tray = "Tray"
        self.tray_held = False
        self.dipped = 0.0
        self.tray_spot = (TRAY_SPOT.copy(), _rz(180))
        self.bottles = {}
        for w in ("red", "white"):
            b = f.prop("Bot" + w.capitalize(), "bottle", BOTTLE_SPOT[w])
            b["wine"] = w
            self.bottles[w] = b
        self.g = {}
        for name, size, drink in (("JRa", "wine", "red"), ("JPa", "pint", "bitter"), ("JRb", "wine", "red"),
                                  ("JPb", "pint", "bitter"), ("TFw", "wine", "white"), ("TMp", "pint", "bitter"),
                                  ("PNs", "pint", "stout"),
                                  ("TAf", "pineapple", "colada"), ("TBf", "highball", "sunrise"),
                                  ("TSf", "highball", "punch"), ("TAx", "pineapple", "colada"),
                                  ("TBx", "highball", "sunrise"), ("TSx", "highball", "punch")):
            self.g[name] = f.glass(name, size, drink)
        self.fills = {n: [] for n in self.g}           # (t0, t1, value): a step when t0 == t1
        self.drain = {}                                # reserved-table glass -> {"placed", "collected"}
        self.jobs = []                                 # (t0, t1, label)
        self.visits = []                               # (t0, t1, who) at a customer
        self.waits = []                                # how long each of her pints waited for the barman
        f.put(0.0, STN[0], STN[1], 180)
        f.zk.add(0.0, CARPET).add(LOOP, CARPET)
        f.fL.add(0.0, V(STAND_FEET[0]))
        f.fR.add(0.0, V(STAND_FEET[1]))
        f.vis.add(0.0, 1.0).add(LOOP, 1.0)
        self.hands(0.0)
        self.head(0.0)

    # pose ------------------------------------------------------------------
    def hand_rest(self, side):
        if side == "L":
            return TRAY_HOLD.copy() if self.tray_held else V(REST["stand"][0])
        return V(REST["stand"][1])

    def hands(self, t):
        self.f.L.add(t, self.hand_rest("L"))
        self.f.R.add(t, self.hand_rest("R"))

    def head(self, t, lean=3, pitch=3, yaw=0):
        self.f.lean.add(t, lean)
        self.f.pitch.add(t, pitch)
        self.f.yaw.add(t, yaw)

    def walk(self, t, pts, speed=1.0):
        f = self.f
        pts = [tuple(p) for p in pts]
        hs = [heading(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
        f.put(t, pts[0][0], pts[0][1], self.yaw)
        self.head(t)
        self.hands(t)
        t += 0.5
        f.put(t, pts[0][0], pts[0][1], hs[0], lin=True)
        cut_prev = 0.0
        for i in range(1, len(pts)):
            a, b = V(pts[i - 1]), V(pts[i])
            d = (b - a).length
            if i < len(pts) - 1:
                c = V(pts[i + 1])
                cut = min(0.3, d / 2, (c - b).length / 2)
                din, dout = (b - a).normalized(), (c - b).normalized()
                t += max(0.05, d - cut_prev - cut) / speed
                pa = b - din * cut
                f.put(t, pa.x, pa.y, hs[i - 1], lin=True)
                t += 2 * cut / speed
                pb = b + dout * cut
                f.put(t, pb.x, pb.y, hs[i], lin=True)
                cut_prev = cut
            else:
                t += max(0.05, d - cut_prev) / speed
                f.put(t, b.x, b.y, hs[i - 1])
        self.x, self.y, self.yaw = pts[-1][0], pts[-1][1], f._yaw
        self.head(t)
        self.hands(t)
        return t

    def turn(self, t, yaw, dur=0.5):
        f = self.f
        f.put(t, self.x, self.y, self.yaw)
        f.put(t + dur, self.x, self.y, yaw)
        self.yaw = f._yaw
        return t + dur

    def stay(self, t):
        self.f.put(t, self.x, self.y, self.yaw)

    def go(self, t, stop):
        stand, face, route = WTR_STOPS[stop]
        t = self.walk(t, route)
        return self.turn(t, heading(stand, face))

    def go_back(self, t, stop):
        stand, face, route = WTR_STOPS[stop]
        t = self.walk(t, list(reversed(route)))
        return self.turn(t, 180)

    def wait(self, t, until):
        """Stand at the station, looking round, until `until`."""
        self.stay(t)
        rng = random.Random(int(t * 10))
        tt = t + 0.6
        while tt < until - 1.2:
            self.f.yaw.add(tt, rng.uniform(-35, 35))
            self.f.pitch.add(tt, rng.choice([-2, 2, 6]))
            tt += rng.uniform(1.2, 2.2)
        until = max(until, t)
        self.head(until)
        self.stay(until)
        return until

    # hands -----------------------------------------------------------------
    def _key(self, t, side, est):
        self.n += 1
        k = f"w{self.n}"
        off = V((0.05 if side == "R" else -0.05, -0.03, 0.04))
        self.f.wrist[k] = self.f.to_local(t, est) + off
        return k

    def reach(self, t, side, want, est, lean=22, pitch=20, dur=0.8):
        f = self.f
        k = self._key(t + dur, side, est)
        keys = f.L if side == "L" else f.R
        keys.hold(t)
        keys.add(t + dur, f.named(k))
        f.lean.hold(t).add(t + dur, lean)
        f.pitch.hold(t).add(t + dur, pitch)
        f.contacts.append(("palm", t + dur, k, side, want))
        return t + dur

    def back(self, t, side, dur=0.5):
        keys = self.f.L if side == "L" else self.f.R
        keys.add(t + dur, self.hand_rest(side))
        self.f.lean.add(t + dur, 3)
        self.f.pitch.add(t + dur, 3)
        return t + dur

    def slot_world(self, slot):
        p, r = self.tray_spot
        return p + r @ (TRAY_SLOTS[slot] + V((0, 0, TRAY_TOP)))

    def want(self, g, where, t):
        """Palm position for a glass/bottle standing at `where` (a world spot
        or ("T", slot) on the tray), and a world estimate for the first guess."""
        grip = grip_of(g)
        if isinstance(where, tuple):
            slot = where[1]
            if self.tray_held:
                def f(rec, slot=slot, grip=grip):
                    return (tray_on_palm(rec["palm"]["L"], rec["yaw"]) +
                            Matrix.Rotation(rec["yaw"], 3, 'Z') @ (TRAY_SLOTS[slot] + V((0, 0, TRAY_TOP + grip))))
                est = self.f.to_world(t, TRAY_HOLD + V((0.03, 0.09, -0.03)) + TRAY_SLOTS[slot] +
                                      V((0, 0, TRAY_TOP + grip)))
                return f, est
            w = self.slot_world(slot) + V((0, 0, grip))
            return w, w
        w = V(where) + V((0, 0, grip))
        return w, w

    def take(self, t, g, where, side="R", lean=22):
        want, est = self.want(g, where, t + 0.8)
        tc = self.reach(t, side, want, est, lean)
        g["events"].append((tc, side, None))
        return tc

    def put(self, t, g, where, side="R", lean=22):
        want, est = self.want(g, where, t + 0.8)
        tc = self.reach(t, side, want, est, lean)
        if isinstance(where, tuple):
            g["events"].append((tc, "T", where[1]))
        else:
            g["events"].append((tc, "spot", V(where)))
        return tc

    def shift(self, t, g, a, b, side="R", lean=22, lean_b=None):
        """Pick g up at a, set it down at b; returns when the hand is back."""
        tc = self.take(t, g, a, side, lean)
        tp = self.put(tc + 0.15, g, b, side, lean if lean_b is None else lean_b)
        return self.back(tp, side)

    def tray_palm(self):
        p, _r = self.tray_spot
        return p - _rz(self.yaw) @ V((0.0, 0.06, -0.014))

    def lift_tray(self, t):
        w = self.tray_palm()
        tc = self.reach(t, "L", w, w, lean=18)
        self.tray["events"].append((tc, "L", None))
        self.tray_held = True
        return self.back(tc, "L", 0.6)

    def set_tray(self, t):
        self.tray_spot = (TRAY_SPOT.copy(), _rz(self.yaw))
        w = self.tray_palm()
        tc = self.reach(t, "L", w, w, lean=18)
        self.tray["events"].append((tc, "spot", self.tray_spot))
        self.tray_held = False
        return self.back(tc, "L")

    def step(self, g, t, v):
        self.fills[g["name"]].append((t, t, v))

    def pour(self, t, wine, slot, glass):
        """Pour from the bottle into the glass standing on tray slot `slot`
        (the tray on the bar)."""
        f = self.f
        b = self.bottles[wine]
        tc = self.take(t, b, BOTTLE_SPOT[wine], "R", 20)
        G = self.slot_world(slot)
        want = G + _rz(self.yaw) @ V((0.0, -0.217, 0.0)) + V((0, 0, 0.275))
        k = self._key(tc + 0.9, "R", want)
        f.R.add(tc + 0.9, f.named(k)).add(tc + 2.4, f.named(k))
        f.contacts.append(("palm", tc + 0.9, k, "R", want))
        b["tilt"].add(tc + 0.3, 0).add(tc + 1.0, -100).add(tc + 2.3, -100).add(tc + 2.9, 0)
        f.lean.add(tc + 0.9, 12).add(tc + 2.4, 12)
        f.pitch.add(tc + 0.9, 30).add(tc + 2.4, 30)
        self.fills[glass["name"]].append((tc + 1.1, tc + 2.2, 1.0))
        tp = self.put(tc + 2.6, b, BOTTLE_SPOT[wine], "R", 20)
        return self.back(tp, "R")

    def to_barman(self, t, g, where, pours, side="L"):
        """Set a pint on the bar at O2 for the barman. Returns (hand back, serve time)."""
        t = self.shift(t, g, where, O2, side, 20)
        t_put = [e[0] for e in g["events"] if e[1] == "spot"][-1]
        t_c = alloc_pour(pours, t_put + 1.5)
        self.waits.append(t_c - t_put - 1.5)
        t_s = t_c + SERVE_DT
        g["events"] += [(t_c + EPS, "hidden", None), (t_s - EPS, "spot", O2.copy())]
        self.step(g, t_s - EPS, 1.0)
        pours.append((t_c, t_s, "sO2", O2, (g["size"], g["ale"])))
        return t, t_s

    def collect(self, t, g, m, slot, lean=36):
        """Take a customer's empty (swap) and stand it on the tray."""
        S = V(m.spot)
        want, est = self.want(g, S, t + 0.8)
        tc = self.reach(t, "R", want, est, lean)
        g["events"] += [(tc - EPS, "spot", S.copy()), (tc, "R", None)]
        m.g["events"].append((tc + EPS, "hidden", None))
        m.deadlines.append(tc)
        self.step(g, tc - 2 * EPS, 0.001)
        tp = self.put(tc + 0.15, g, ("T", slot), "R")
        return self.back(tp, "R")

    def deliver(self, t, g, m, slot, lean=36):
        """Set a fresh drink at a customer's place (swap back to theirs)."""
        S = V(m.spot)
        tc = self.take(t, g, ("T", slot), "R")
        tp = self.put(tc + 0.15, g, S, "R", lean)
        g["events"].append((tp + EPS, "hidden", None))
        m.g["events"].append((tp - EPS, "spot", S.copy()))
        m.refills.append(tp)
        self.step(g, tp + 2 * EPS, 0.001)
        return self.back(tp, "R")

    # jobs ------------------------------------------------------------------
    def job_jay(self, t, pours, give, take):
        """Fresh set `give` to the reserved table, set `take` back to the bar."""
        gw, gp = self.g["JR" + give], self.g["JP" + give]
        ow, op = self.g["JR" + take], self.g["JP" + take]
        t, t_s = self.to_barman(t, gp, PARK["pint"], pours)
        t = self.shift(t, gw, PARK["wine"], ("T", 3))
        t = self.pour(t, "red", 3, gw)
        t = self.wait(t, t_s + 0.4)
        t = self.shift(t, gp, O2, ("T", 2), "L", 20)
        t = self.lift_tray(t)
        t = self.go(t, "JT")
        v0 = t
        t = self.shift(t, ow, JAY["wine"], ("T", 1), lean=36, lean_b=22)
        self.drain.setdefault(ow["name"], {})["collected"] = [e[0] for e in ow["events"] if e[1] == "R"][-1]
        self.drain.setdefault(op["name"], {})
        t = self.shift(t, gw, ("T", 3), JAY["wine"], lean=22, lean_b=30)
        self.drain.setdefault(gw["name"], {})["placed"] = [e[0] for e in gw["events"] if e[1] == "spot"][-1]
        t = self.shift(t, op, JAY["pint"], ("T", 0), lean=36, lean_b=22)
        self.drain[op["name"]]["collected"] = [e[0] for e in op["events"] if e[1] == "R"][-1]
        t = self.shift(t, gp, ("T", 2), JAY["pint"], lean=22, lean_b=30)
        self.drain.setdefault(gp["name"], {})["placed"] = [e[0] for e in gp["events"] if e[1] == "spot"][-1]
        self.visits.append((v0, t, "jay"))
        t = self.go_back(t, "JT")
        t = self.set_tray(t)
        t = self.shift(t, ow, ("T", 1), PARK["wine"])
        t = self.shift(t, op, ("T", 0), PARK["pint"], "L", 20)
        return t

    def job_table(self, t, pours, TF, TM):
        """Clear the booth couple, then bring her white and his bitter."""
        w, p = self.g["TFw"], self.g["TMp"]
        t = self.lift_tray(t)
        t = self.go(t, "TT")
        v0 = t
        t = self.collect(t, w, TF, 1)
        t = self.collect(t, p, TM, 0)
        self.visits.append((v0, t, "table"))
        t = self.go_back(t, "TT")
        t = self.set_tray(t)
        t, t_s = self.to_barman(t, p, ("T", 0), pours)
        t = self.pour(t, "white", 1, w)
        t = self.wait(t, t_s + 0.4)
        t = self.shift(t, p, O2, ("T", 0), "L", 20)
        t = self.lift_tray(t)
        t = self.go(t, "TT")
        v0 = t
        t = self.deliver(t, w, TF, 1)
        t = self.deliver(t, p, TM, 0)
        self.visits.append((v0, t, "table"))
        t = self.go_back(t, "TT")
        return self.set_tray(t)

    def job_piano(self, t, pours, P):
        """The pianist's empty off the piano, a fresh stout back on it."""
        s = self.g["PNs"]
        t = self.lift_tray(t)
        t = self.go(t, "PS")
        v0 = t
        t = self.collect(t, s, P, 0, lean=26)
        self.visits.append((v0, t, "piano"))
        t = self.go_back(t, "PS")
        t = self.set_tray(t)
        t, t_s = self.to_barman(t, s, ("T", 0), pours)
        t = self.wait(t, t_s + 0.4)
        t = self.shift(t, s, O2, ("T", 2), "L", 20)
        t = self.lift_tray(t)
        t = self.go(t, "PS")
        v0 = t
        t = self.deliver(t, s, P, 2, lean=26)
        self.visits.append((v0, t, "piano"))
        t = self.go_back(t, "PS")
        return self.set_tray(t)

    def mix(self, t, g, slot):
        """A cocktail up from behind the counter front (where the glasses
        and the mixers live), a stir and a shake of the glass, onto the tray."""
        f = self.f
        f.R.hold(t).add(t + 0.6, MIX_HAND)
        f.lean.hold(t).add(t + 0.6, 14)
        f.pitch.hold(t).add(t + 0.6, 24)
        g["events"].append((t + 0.6, "R", None))
        self.step(g, t + 0.6 - EPS, 1.0)
        for q in range(4):
            f.R.add(t + 1.0 + q * 0.3, V((0.12, 0.34, 1.10 + 0.04 * (q % 2))))
        g["tilt"].add(t + 0.9, 0).add(t + 1.2, 12).add(t + 1.8, -12).add(t + 2.2, 0)
        tp = self.put(t + 2.2, g, ("T", slot), "R", 26)
        return self.back(tp, "R")

    def stash(self, t, g, slot):
        """An empty off the tray and down behind the counter front."""
        f = self.f
        tc = self.take(t, g, ("T", slot), "R", 20)
        f.R.add(tc + 0.6, MIX_HAND)
        f.lean.add(tc + 0.6, 14)
        g["events"].append((tc + 0.6, "hidden", None))
        return self.back(tc + 0.6, "R")

    def dip(self, t, depth, dur=0.6):
        """Bend the knees by `depth` (feet stay on the floor)."""
        f = self.f
        f.zk.add(t, CARPET - self.dipped).add(t + dur, CARPET - depth)
        for keys, (x, y, z) in ((f.fL, STAND_FEET[0]), (f.fR, STAND_FEET[1])):
            keys.add(t, V((x, y, z + self.dipped))).add(t + dur, V((x, y, z + depth)))
        self.dipped = depth
        return t + dur

    def swap_at(self, t, old, new, m, slot_in, slot_out):
        """Squat a little at the coping: the empty onto the tray, the fresh
        one down in its place."""
        t = self.dip(t, TUB_DIP)
        t = self.collect(t, old, m, slot_in, lean=TUB_REACH)
        t = self.deliver(t, new, m, slot_out, lean=TUB_REACH)
        return self.dip(t, 0.0)

    def job_tub(self, t, tub):
        """Three cocktails out to the hot tub: swap each empty on the coping
        for a fresh one (the tray's spare slot takes the first empty)."""
        A, B, S = tub["TubA"], tub["TubB"], tub["TubS"]
        g = self.g
        t = self.mix(t, g["TSf"], 0)
        t = self.mix(t, g["TBf"], 1)
        t = self.mix(t, g["TAf"], 2)
        t = self.lift_tray(t)
        t = self.walk(t, WTR_TUB_ROUTE)
        t = self.turn(t, 0.0)
        v0 = t
        t = self.swap_at(t, g["TBx"], g["TBf"], B, 3, 1)
        t = self.walk(t, WTR_TUB_HOPS["TS"])
        t = self.turn(t, 0.0)
        t = self.swap_at(t, g["TSx"], g["TSf"], S, 1, 0)
        t = self.walk(t, WTR_TUB_HOPS["TA"])
        t = self.turn(t, 0.0)
        t = self.swap_at(t, g["TAx"], g["TAf"], A, 0, 2)
        self.visits.append((v0, t, "tub"))
        t = self.walk(t, WTR_TUB_BACK + list(reversed(WTR_TUB_ROUTE))[2:])
        t = self.turn(t, 180)
        t = self.set_tray(t)
        for name, slot in (("TBx", 3), ("TSx", 1), ("TAx", 0)):
            t = self.stash(t, g[name], slot)
        return t

    # finishing -------------------------------------------------------------
    def idle(self):
        """Station idles in the gaps between jobs: look round the room, and in
        a long gap turn to face it for a while."""
        f = self.f
        rng = random.Random("barmaid")
        marks = sorted((a, b) for a, b, _l in self.jobs)
        gaps, t = [], 0.3
        for a, b in marks:
            if a - t > 2.0:
                gaps.append((t, a))
            t = max(t, b)
        if LOOP - 0.3 - t > 2.0:
            gaps.append((t, LOOP - 0.3))
        for a, b in gaps:
            # Root keys written straight (not via put, which unwraps yaw against
            # the last key written, here the end of the last job).
            y0 = _sample(f.root, [a])[0].z
            at = lambda t, yaw: f.root.add(t, V((STN[0], STN[1], yaw)))
            at(a, y0)
            at(b, y0)
            if b - a > 20.0:
                m0 = a + rng.uniform(3.0, (b - a) * 0.4)
                m1 = min(b - 3.0, m0 + rng.uniform(6.0, 10.0))
                at(m0, y0)
                at(m0 + 0.8, y0 - 160)
                at(m1, y0 - 160)
                at(m1 + 0.8, y0)
                f.L.add(m0 + 0.8, V((-0.06, 0.16, 0.98))).add(m1, V((-0.06, 0.16, 0.98)))
                f.R.add(m0 + 0.8, V((0.06, 0.16, 0.98))).add(m1, V((0.06, 0.16, 0.98)))
                f.L.add(m1 + 0.8, V(REST["stand"][0]))
                f.R.add(m1 + 0.8, V(REST["stand"][1]))
            tt = a + 0.8
            while tt < b - 1.0:
                f.yaw.add(tt, rng.uniform(-40, 40))
                f.pitch.add(tt, rng.choice([-3, 0, 3, 6]))
                tt += rng.uniform(1.0, 2.4)
            self.head(b)
        for k in (f.yaw, f.pitch, f.lean):
            k.add(0.0, 3 if k is not f.yaw else 0).add(LOOP, 3 if k is not f.yaw else 0)
        f.root.add(LOOP, V((STN[0], STN[1], _sample(f.root, [LOOP])[0].z)))
        self.hands(LOOP)

    def finish(self):
        """Fill keys (with the reserved table's slow drain across the seam)
        and prop segments."""
        g = self.g
        for give, take in (("b", "a"), ("a", "b")):
            for kind in ("JR", "JP"):
                name = kind + give
                d = self.drain[name]
                placed = d["placed"]
                coll = self.drain[name].get("collected")
                if coll is None or coll < placed:      # on the table across the seam
                    coll = self.drain[name]["collected"]
                    span = coll + LOOP - placed
                    v_seam = 1.0 - (1.0 - LEFT_AT) * (LOOP - placed) / span
                    ev = [(0.0, coll, LEFT_AT)] + self.fills[name] + [(placed, LOOP, v_seam)]
                    g[name]["fill"] = _fill_keys(ev, v_seam)
                else:
                    ev = self.fills[name] + [(placed, coll, LEFT_AT)]
                    g[name]["fill"] = _fill_keys(ev, LEFT_AT)
        for name in ("TFw", "TMp", "PNs", "TAf", "TBf", "TSf", "TAx", "TBx", "TSx"):
            g[name]["fill"] = _fill_keys(self.fills[name], 0.001)
        start = {"JRa": ("spot", JAY["wine"]), "JPa": ("spot", JAY["pint"]), "JRb": ("spot", PARK["wine"]),
                 "JPb": ("spot", PARK["pint"])}
        for name, gg in g.items():
            mode, spot = start.get(name, ("hidden", None))
            gg["segs"] = segs_from(gg["events"], LOOP, mode, spot)
        self.tray["segs"] = segs_from(self.tray["events"], LOOP, "spot", (TRAY_SPOT.copy(), _rz(180)))
        for w, b in self.bottles.items():
            b["segs"] = segs_from(b["events"], LOOP, "spot", BOTTLE_SPOT[w])
            b["tilt"].add(0.0, 0).add(LOOP, 0)


def _fill_keys(events, v0):
    """events: (t0, t1, v): a step to v at t0 when t0 == t1, else a straight
    ramp to v over t0..t1. Starts (and ends) at v0 unless a ramp says otherwise."""
    k = Keys()
    cur = v0
    k.add(0.0, v0, lin=True)
    for t0, t1, v in sorted(events, key=lambda e: e[0]):
        if t1 - t0 < 1e-6:
            k.add(max(0.0, t0 - EPS), cur, lin=True).add(t0, v, lin=True)
        else:
            k.add(t0, cur, lin=True).add(t1, v, lin=True)
        cur = v
    k.add(LOOP, cur, lin=True)
    return k.done()


# --- The pianist ------------------------------------------------------------------
class Pianist:
    """Plays the upright on the master loop; a pint of stout stands on top of
    the piano, and now and then he stops for a drink. The barmaid replaces it."""

    def __init__(self):
        fig = Figure("Pno", dict(sex="m", skin="d8a584", hair="15110e", hair_style="slick", top="f2efe8",
                                 jacket="5e1d27", bowtie="111111", legs="18181c", sleeves="long"))
        fig.hand = "R"
        self.f = fig
        self.g = fig.glass("G", "pint", "stout")
        self.spot = PNO_SPOT
        self.deadlines, self.refills, self.trips = [], [], []
        self.z = 0.62 + 0.08 - 0.93
        fig.zk.add(0.0, self.z).add(LOOP, self.z)
        fig.put(0.0, PNO_SEAT[0], PNO_SEAT[1], PNO_SEAT[2])
        fig.put(LOOP, PNO_SEAT[0], PNO_SEAT[1], PNO_SEAT[2])
        fig.fL.add(0.0, V((-0.12, 0.40, 0.33)))
        fig.fR.add(0.0, V((0.12, 0.42, 0.33)))
        fig.vis.add(0.0, 1.0).add(LOOP, 1.0)

    def finish(self, visits):
        fig, g = self.f, self.g
        rng = random.Random("piano")
        key_z = 0.80 + 0.06 - self.z
        rest_l, rest_r = V((-0.16, 0.34, key_z)), V((0.16, 0.34, key_z))
        r, d = self.refills[0], self.deadlines[0]
        span = (d - r) % LOOP
        busy = [(a - 3.0, b + 3.0) for a, b in visits]

        def clear(t):
            tm = t % LOOP
            if tm < 1.5 or tm > LOOP - 7.0:
                return False
            return all(tm + 6.0 <= a or tm - 1.0 >= b for a, b in busy)
        k = 4
        sips = []
        for j in range(k):
            target = r + span * (j + 0.6) / (k + 0.2)
            for step in range(400):
                hit = None
                for sgn in (1, -1):
                    tt = target + sgn * step * 0.5
                    if r + 8.0 < tt < r + span - 8.0 and clear(tt) and \
                            all(abs(((tt % LOOP - c) + LOOP / 2) % LOOP - LOOP / 2) > 12.0 for c in sips):
                        hit = tt % LOOP
                        break
                if hit is not None:
                    sips.append(hit)
                    break
            else:
                raise RuntimeError("pianist: no room for a sip")
        sips.sort(key=lambda tm: (tm - r) % LOOP)
        lv = []
        for j, ts in enumerate(sips):
            a, b = 1.0 - j / k, max(0.001, 1.0 - (j + 1) / k)
            lv.append((ts, a, b))
            fig.R.add(ts, rest_r).add(ts + 0.8, fig.named("spot"))
            fig.contacts.append((ts + 0.8, "spot", "G", PNO_SPOT))
            g["events"].append((ts + 0.8, "R", None))
            mouth = V((0.05, 0.20, 1.50))
            fig.R.add(ts + 1.9, mouth).add(ts + 3.1, mouth).add(ts + 4.0, fig.named("spot")).add(ts + 4.8, rest_r)
            fig.contacts.append((ts + 4.0, "spot", "G", PNO_SPOT))
            g["events"].append((ts + 4.0, "spot", PNO_SPOT))
            fig.L.add(ts, rest_l).add(ts + 4.8, rest_l)
            fig.lean.add(ts, 14).add(ts + 0.8, 22).add(ts + 1.9, 8).add(ts + 3.1, 8).add(ts + 4.0, 22).add(ts + 4.8, 14)
            fig.pitch.add(ts, 15).add(ts + 0.8, 10).add(ts + 1.9, -12).add(ts + 3.1, -12).add(ts + 4.0, 10) \
                .add(ts + 4.8, 15)
            fig.yaw.add(ts, 0).add(ts + 0.7, 30).add(ts + 1.7, 0).add(ts + 3.4, 0).add(ts + 4.0, 30).add(ts + 4.8, 0)
            g["tilt"].add(ts + 1.7, 0).add(ts + 2.2, 55).add(ts + 2.9, 55).add(ts + 3.3, 0)
            g["fill"].add(ts + 2.1, a).add(ts + 3.0, b)
        g["fill"].add(r - 2 * EPS, 0.001).add(r - EPS, 1.0)
        evts = [(ts + 3.0, b) for ts, a, b in lv] + [(r, 1.0)]
        level = max(evts)[1]
        g["fill"].add(0.0, level).add(LOOP, level)
        side = V((0.06, 0.04, 0.07))
        fig.wrist["spot"] = fig.to_local(sips[0] + 0.8, PNO_SPOT + side)
        g["segs"] = segs_from(g["events"], LOOP, "spot", PNO_SPOT)
        # Playing fills everything else; he glances round at the barmaid.
        stops = sorted((ts - 0.6, ts + 5.4) for ts in sips)
        segs, t = [], 0.0
        for a, b in stops:
            if a - t > 1.0:
                segs.append((t, a))
            t = max(t, b)
        segs.append((t, LOOP))
        looks = [(a, b) for a, b in visits]
        for a, b in segs:
            fig.L.add(a, rest_l)
            fig.R.add(a, rest_r)
            t = a
            while t < b - 1.0:
                phrase = rng.uniform(3.0, 6.0)
                beat = rng.choice([0.33, 0.4, 0.5])
                lc, rc = rng.uniform(-0.30, -0.08), rng.uniform(0.06, 0.32)
                tt = t
                while tt < min(t + phrase, b - 1.0):
                    lx, rx = lc + rng.uniform(-0.05, 0.05), rc + rng.uniform(-0.07, 0.07)
                    fig.L.add(tt + 0.05, V((lx, 0.34, key_z + 0.035))).add(tt + beat * 0.5, V((lx, 0.35, key_z)))
                    fig.R.add(tt + 0.10, V((rx, 0.35, key_z + 0.03))).add(tt + beat * 0.55, V((rx, 0.36, key_z)))
                    tt += beat
                mid = t + phrase * 0.5
                if not any(la - 1.0 <= mid <= lb + 1.0 for la, lb in looks) and mid < b - 0.5:
                    fig.lean.add(mid, rng.uniform(10, 18))
                    fig.yaw.add(mid, rng.uniform(-12, 12))
                    fig.pitch.add(t + phrase * 0.4, rng.uniform(8, 22))
                    if rng.random() < 0.25 and t + phrase * 0.8 < b - 0.5:
                        fig.yaw.add(t + phrase * 0.8, 55)
                        fig.pitch.add(t + phrase * 0.8, 0)
                t += phrase
            fig.L.add(b, rest_l)
            fig.R.add(b, rest_r)
            fig.lean.add(b, 14)
            fig.yaw.add(b, 0)
            fig.pitch.add(b, 15)
        for la, lb in looks:                       # she is at his shoulder: a look and a word
            fig.yaw.add(la - 0.8, 0).add(la, 60).add(lb, 60).add(lb + 0.8, 0)
            fig.pitch.add(la, 2).add(lb, 2)
        for kk, v in ((fig.lean, 14), (fig.pitch, 15), (fig.yaw, 0)):
            kk.add(0.0, v).add(LOOP, v)


# --- Planning the barmaid ---------------------------------------------------------
def _sample(keys, times):
    """A Keys track (sorted copy, no HOLD markers) at each of `times`."""
    keys = sorted(keys, key=lambda kv: kv[0])
    out, i, m = [], 1, len(keys)
    for t in times:
        while i < m and t > keys[i][0]:
            i += 1
        if t <= keys[0][0]:
            v = keys[0][1]
        elif i >= m:
            v = keys[-1][1]
        else:
            a, b = keys[i - 1], keys[i]
            if b[0] <= a[0]:
                v = b[1]
            else:
                s = (t - a[0]) / (b[0] - a[0])
                if len(a) < 3:
                    s = ease(s)
                v = a[1] + (b[1] - a[1]) * s
        out.append(v)
    return out


GRID = 0.25


def _others(movers, extra=()):
    times = [i * GRID for i in range(int(LOOP / GRID) + 1)]
    out = []
    for f in movers:
        rs = _sample(f.root, times)
        vs = _sample(f.vis, times) if f.vis else [1.0] * len(times)
        out.append((f.tag, [(r.x, r.y) if v > 0.5 else None for r, v in zip(rs, vs)]))
    for tag, (x, y) in extra:
        out.append((tag, [(x, y)] * len(times)))
    return out


def _clash(f, others, t0, t1, d_min=0.50):
    i0, i1 = int(math.ceil(t0 / GRID)), int(min(LOOP, t1) / GRID)
    times = [i * GRID for i in range(i0, i1 + 1)]
    if not times:
        return None
    mine = _sample(f.root, times)
    for i, r in zip(range(i0, i1 + 1), mine):
        for tag, pts in others:
            p = pts[i]
            if p and (p[0] - r.x) ** 2 + (p[1] - r.y) ** 2 < d_min * d_min:
                return (i * GRID, tag)
    return None


class _Txn:
    """Snapshot of every list a job appends to, so a job that clashes can be
    undone and tried again later."""

    def __init__(self, lists, attrs):
        self.lens = [(lst, len(lst)) for lst in lists]
        self.attrs = [(o, a, getattr(o, a)) for o, a in attrs]

    def rollback(self):
        for lst, n in self.lens:
            del lst[n:]
        for o, a, v in self.attrs:
            setattr(o, a, v)


WTR_ORDERS = (("jay1", "table", "piano", "jay2", "tub"), ("jay1", "table", "tub", "piano", "jay2"),
              ("jay1", "tub", "table", "piano", "jay2"))


def _waitress(cast, P, pours, report=None, order=None):
    W = Waitress()
    TF, TM = cast["TF"], cast["TM"]
    tub = {k: m for k, m in cast.items() if getattr(m, "tub", False)}
    others = _others([m.f for m in cast.values()], [("Pno", PNO_SEAT[:2])])
    f = W.f

    def lists():
        out = [f.root, f.zk, f.vis, f.lean, f.pitch, f.yaw, f.L, f.R, f.fL, f.fR, f.contacts, pours, W.visits,
               W.waits]
        for g in f.glasses:
            out += [g["events"], g["tilt"]]
        out += list(W.fills.values())
        for m in (TF, TM, P) + tuple(tub.values()):
            out += [m.g["events"], m.deadlines, m.refills, m.f.busy, m.f.yaw]
        return out
    attrs = [(W, "x"), (W, "y"), (W, "yaw"), (W, "tray_held"), (W, "tray_spot"), (W, "n"), (f, "_yaw"), (W, "dipped")]
    tub = {k: m for k, m in cast.items() if getattr(m, "tub", False)}
    for m in tub.values():
        attrs.append((m.f, "_yaw"))
    every = {"jay1": (6.0, lambda t: W.job_jay(t, pours, "b", "a")),
             "table": (0.0, lambda t: W.job_table(t, pours, TF, TM)),
             "piano": (0.0, lambda t: W.job_piano(t, pours, P)),
             "jay2": (165.0, lambda t: W.job_jay(t, pours, "a", "b")),
             "tub": (0.0, lambda t: W.job_tub(t, tub))}
    jobs = [(label, *every[label]) for label in (order or WTR_ORDERS[0]) if label != "tub" or tub]
    t_prev = 0.0
    for label, earliest, fn in jobs:
        start = max(earliest, t_prev + 4.0)
        fails = []
        for attempt in range(400):
            drain = {k: dict(v) for k, v in W.drain.items()}
            tx = _Txn(lists(), attrs)
            n_vis, n_wait = len(W.visits), len(W.waits)
            W.stay(start)
            W.hands(start)
            end = fn(start)
            bad = end > LOOP - 3.0
            why = "past the loop" if bad else None
            if not bad and max(W.waits[n_wait:], default=0.0) > 10.0:
                bad, why = True, "barman busy"
            if not bad:
                hit = _clash(f, others, start, end)
                if hit:
                    bad, why = True, f"clash with {hit[1]} at {hit[0]:.1f}s"
            if not bad:
                for a, b, who in W.visits[n_vis:]:
                    for m in ((TF, TM) if who == "table" else tuple(tub.values()) if who == "tub" else ()):
                        if not m.f.free(a - 1.5, b + 1.0):
                            bad, why = True, f"{m.f.tag} away at {a:.1f}s"
            if not bad:
                break
            tx.rollback()
            W.drain = drain
            fails.append(why)
            start += 1.0
        else:
            from collections import Counter
            raise RuntimeError(f"barmaid: no slot for {label} ({Counter(w.split(' at ')[0] for w in fails).most_common(5)})")
        W.jobs.append((start, end, label))
        for a, b, who in W.visits[n_vis:]:
            if who in ("table", "tub"):                # they look up (round) at her
                for m in ((TF, TM) if who == "table" else tuple(tub.values())):
                    m.f.busy.append((a - 1.0, b + 0.5))
                    ang = heading(m.home[:2], (W.x, W.y))
                    rel = -(((ang - m.home[2]) + 180) % 360 - 180)
                    rel = max(-50.0, min(50.0, rel))
                    m.f.yaw.add(a - 0.6, rel).add(b, rel)
        t_prev = end
        if report:
            from collections import Counter
            report(f"BARMAID: {label} {start:.1f}-{end:.1f}s" +
                   (f" after {len(fails)} retries {Counter(w.split(' at ')[0] for w in fails).most_common(4)}"
                    if fails else ""))
    global _LAST_W
    _LAST_W = W
    W.idle()
    W.finish()
    P.finish([(a, b) for a, b, who in W.visits if who == "piano"])
    return W


def _people(pattern=None, report=None):
    pattern = pattern or PATTERN
    cast = _cast()
    players = _dart_players()
    cast.update(players)
    tub = _tub_cast()
    cast.update(tub)
    pours = []
    for m in cast.values():
        m.at_home(0.0)
    global BALL_SCRIPT
    BALL_SCRIPT = _tub_games(tub, random.Random("tubball"))
    # Author each person's trips in time order.
    plan = {}
    for key, t, away in pattern["wc"]:
        plan.setdefault(key, []).append((t, "wc", away))
    for key, t in pattern["runs"]:
        plan.setdefault(key, []).append((t, "run", None))
    for key, items in plan.items():
        m = cast[key]
        for t, kind, away in sorted(items):
            if kind == "wc":
                m.bathroom(t, away)
            else:
                t_place, t_c, t_s = m.bar_run(t)
                pours.append((t_c, t_s, "sO1", O1, (m.g["size"], m.g["ale"])))
    for key, t_c in pattern["bar"]:
        m = cast[key]
        t_s = t_c + SERVE_DT
        m.deadlines.append(t_c)
        m.refills.append(t_s)
        m.g["events"] += [(t_c + EPS, "hidden", None), (t_s - EPS, "spot", m.spot)]
        pours.append((t_c, t_s, "s" + m.f.tag, m.spot, (m.g["size"], m.g["ale"])))
    _darts_game(players, pours)
    P = Pianist()
    W = _waitress(cast, P, pours, report, pattern.get("wtr"))
    for m in cast.values():
        m.at_home(LOOP)
        rng = random.Random(m.f.tag)
        blocked = [(p[0] - 1.0, p[1] + 1.0) for p in pours if p[2] == "s" + m.f.tag]
        if m.g:
            if not m.refills:
                raise RuntimeError(f"{m.f.tag} never gets a refill")
            # Cocktails through a straw: hardly any tilt.
            plan_sips(m, rng, blocked, (lambda mm, t, a, b: sip(mm, t, a, b, tilt=12))
                      if getattr(m, "tub", False) else None)
        idle(m, rng)
        m.f.yaw.add(0.0, m.partner_yaw).add(LOOP, m.partner_yaw)
        m.f.pitch.add(0.0, 4).add(LOOP, 4)
        m.f.root.done()
        m.f.zk.done()
        if not m.g:
            continue
        m.g["segs"] = segs_from(m.g["events"], LOOP, m.hand if m.held else "spot", m.spot)
        side = V((0.06 if m.hand == "R" else -0.06, 0.04, 0.07))
        m.f.wrist["spot"] = m.f.to_local(0.0, m.spot + side)
        orders = [c[0] for c in m.f.contacts if c[1] == "order"]
        if orders:
            m.f.wrist["order"] = m.f.to_local(orders[0], O1 + side)
    cast["W"], cast["P"] = W, P
    return cast, sorted(pours, key=lambda p: p[0])


# --- Scheduler ----------------------------------------------------------------
def _root_clashes(cast):
    """Glide-path clashes from the root tracks alone (cheap: no IK)."""
    movers = list(cast.values())
    for m in movers:
        for k in (m.f.root, m.f.zk, m.f.vis):
            k.done()
    out = []
    t = 0.0
    while t <= LOOP:
        pts = []
        for m in movers:
            if track(m.f.vis, t) > 0.5:
                r = track(m.f.root, t)
                pts.append((m, Vector((r.x, r.y))))
        for i in range(len(pts)):
            for j in range(i + 1, len(pts)):
                if (pts[i][1] - pts[j][1]).length < 0.45:
                    out.append((t, pts[i][0], pts[j][0]))
        t += 0.25
    return out


def _barman_clash(pours):
    for (a0, a1, *_a), (b0, b1, *_b) in zip(pours, pours[1:]):
        if b0 - a1 < 5.0:
            return a1, b0
    return None


def _plan(pattern, report):
    """Shift trips until nobody's glide path clashes and the barman is never
    double-booked. Returns (cast, pours, pattern actually used)."""
    import copy
    pat = copy.deepcopy(pattern)

    def shift(key, t_active, kinds=("wc", "runs")):
        for kind in kinds:
            for i, item in enumerate(pat[kind]):
                if item[0] == key and abs(item[1] - t_active) < 1e-6:
                    nt = item[1] + 7.0
                    if nt > LOOP - (110.0 if kind == "wc" else 45.0):   # it must finish inside the loop
                        nt = 20.0 + (nt % 7.0)
                    pat[kind][i] = (item[0], nt) + tuple(item[2:])
                    return True
        return False

    orders = list(WTR_ORDERS)
    pat["wtr"] = orders.pop(0)
    for attempt in range(150):
        try:
            cast, pours = _people(pat, report if attempt == 0 else None)
        except RuntimeError as e:
            if str(e).startswith("barmaid") and orders:
                report(f"BARMAID: order {pat['wtr']} does not fit ({e}); trying {orders[0]}")
                pat["wtr"] = orders.pop(0)
                continue
            raise RuntimeError(f"schedule unplannable: {e}")
        bad = _barman_clash(pours)
        if bad:
            # Move the takeaway run whose pour starts at the clash.
            moved = False
            for key, t in pat["runs"]:
                m = cast[key]
                for t0, t1, kind in m.trips:
                    if kind == "run" and t0 <= bad[1] <= t1 + 30:
                        moved = shift(key, t, ("runs",))
                        break
                if moved:
                    break
            if not moved:
                raise RuntimeError(f"barman double-booked at {bad} and no run to move")
            continue
        clashes = _root_clashes(cast)
        if not clashes:
            if attempt:
                report(f"SCHEDULE: resolved after {attempt} shifts: wc {pat['wc']} runs {pat['runs']}")
            return cast, pours, pat
        t, a, b = clashes[0]
        key_of = {m.f.tag: k for k, m in cast.items()}
        cands = []
        for m in (a, b):
            for t0, t1, kind in m.trips:
                if kind in ("wc", "run") and t0 - 1 <= t <= t1 + 1:   # only the pattern's trips can move
                    cands.append((t0, key_of[m.f.tag], kind))
        if not cands:
            raise RuntimeError(f"{a.f.tag} and {b.f.tag} clash at {t:.1f}s with neither travelling")
        t0, key, kind = max(cands)
        shift(key, next(item[1] for item in pat["wc" if kind == "wc" else "runs"]
                        if item[0] == key and abs(item[1] - t0) < 1.0), ("wc",) if kind == "wc" else ("runs",))
    raise RuntimeError("schedule did not settle in 150 shifts")


def _barman(pours):
    fig = Figure("Bm", dict(sex="m", skin="d9a88a", hair="4a3a2e", moustache=True, top="e8e4dc", vest="3a2328",
                            tie="6e1420", legs="23232a", sleeves="rolled", cloth=True), legs=False)
    fig.pump = Keys()
    # One glass per drink he pours, so what he hands over matches what the
    # customer drinks (bitter, lager, stout, cider; pint or half).
    GL = {}
    for kind in sorted({p[4] for p in pours}):
        name = "G" if kind == ("pint", "bitter") else "G" + kind[0][0].upper() + kind[1].capitalize()
        GL[kind] = fig.glass(name, kind[0], kind[1])
    PG = fig.glass("PG")
    PG["drink"], PG["head"] = "e8e4dc", "e8e4dc"
    P = (3.05, -15.20, 0)
    BACK = (2.80, -15.74, 180)
    HOLDP = (2.80, -15.55, 180)
    hold, carry = V((-0.05, 0.27, 1.11)), V((-0.06, 0.30, 1.12))
    lowered, free = V((0.15, 0.20, 1.02)), V((-0.16, 0.12, 0.98))
    guess = V((-0.06, -0.04, 0.07))
    R, L, lean, pitch, yaw = fig.R, fig.L, fig.lean, fig.pitch, fig.yaw
    fig.zk.add(0.0, BOARDS).add(LOOP, BOARDS)
    gev, pgev = {k: [] for k in GL}, []

    def polish(t):
        w = 2 * math.pi * t
        return V((0.04 + 0.03 * math.cos(w), 0.30 + 0.025 * math.sin(w), 1.20))

    def wiper(cx):
        def wipe(t):
            w = 2 * math.pi * t / 1.25
            return fig.to_local(t, V((cx + 0.16 * math.sin(w), -14.72 + 0.045 * math.cos(w), 1.12)))
        return wipe

    def knob(t):
        a = math.radians(track(fig.pump, t))
        k = PUMP + V((0, -math.sin(a) * HANDLE, math.cos(a) * HANDLE))
        return fig.to_local(t, k + V((0.0, -0.075, -0.03)))

    def on_bar(x):
        return fig.at_world((x, -14.97, 1.11))

    def stance(spot):
        return (spot.x + 0.23, -15.04 if spot.z < 1.065 else -15.06, 0)

    def pour(t_c, t_s, key, spot, kind):
        G = GL[kind]
        key = key + G["name"]                 # glass heights differ: one reach pose per spot and glass
        st = stance(spot)
        fig.put(t_c - 0.8, *st)
        fig.put(t_c + 0.4, *st)
        lean.add(t_c - 0.8, 20).add(t_c, 26).add(t_c + 0.4, 22)
        pitch.add(t_c - 0.4, 22).add(t_c + 0.6, 18)
        yaw.add(t_c - 0.8, 0)
        L.add(t_c - 0.8, carry).add(t_c, fig.named(key)).add(t_c + 0.8, carry)
        R.add(t_c - 0.8, lowered).add(t_c + 0.8, lowered)
        fig.contacts.append((t_c, key, G["name"], spot))
        fig.wrist.setdefault(key, None)
        gev[kind].extend([(t_c - EPS, "spot", spot), (t_c, "L", None)])
        G["fill"].add(t_c - 2 * EPS, 0.001).add(t_c, 0.001)
        tp = t_c + 1.8
        fig.put(tp - 0.4, *P)
        fig.put(tp + 5.4, *P)
        lean.add(tp, 15).add(tp + 5.4, 15)
        pitch.add(tp, 22).add(tp + 5.4, 22)
        pk = "pump" + G["name"]                  # glass heights differ: one pump pose per glass
        L.add(tp, fig.named(pk)).add(tp + 5.4, fig.named(pk))
        R.add(tp, knob).add(tp + 5.0, knob)
        fig.contacts.append((tp, pk, G["name"], PUMP_SPOT))
        for k in range(3):
            fig.pump.add(tp + 0.2 + k * 1.6, 0).add(tp + 0.9 + k * 1.6, 40).add(tp + 1.8 + k * 1.6, 0)
        G["fill"].add(tp + 0.4, 0.001).add(tp + 1.9, 0.35).add(tp + 3.5, 0.70).add(tp + 5.0, 1.0)
        R.add(tp + 5.8, lowered)
        L.add(tp + 6.0, carry)
        fig.put(t_s - 0.8, *st)
        fig.put(t_s + 0.5, *st)
        lean.add(t_s - 0.8, 20).add(t_s, 26).add(t_s + 0.5, 22)
        L.add(t_s, fig.named(key)).add(t_s + 0.8, free)
        pitch.add(t_s, 18).add(t_s + 0.8, 5)
        yaw.add(t_s + 0.8, 0).add(t_s + 1.4, 15).add(t_s + 2.4, 0)
        fig.contacts.append((t_s, key, G["name"], spot))
        gev[kind].extend([(t_s, "spot", spot), (t_s + EPS, "hidden", None)])
        G["fill"].add(t_s + 2 * EPS, 1.0).add(t_s + 3 * EPS, 0.001)
        return st

    def lean_chat(t0, t1, x, look):
        st = (x, -15.15, 0)
        fig.put(t0, *st)
        fig.put(t1, *st)
        L.add(t0, free)
        R.add(t0, lowered)
        lean.add(t0 + 0.6, 17).add(t1 - 0.6, 17)
        L.add(t0 + 0.6, on_bar(x - 0.25)).add(t1 - 0.6, on_bar(x - 0.25))
        R.add(t0 + 0.6, on_bar(x + 0.25)).add(t1 - 0.6, on_bar(x + 0.25))
        rng = random.Random(int(t0 * 10))
        tt = t0 + 0.8
        while tt < t1 - 1.0:
            yaw.add(tt, look + rng.uniform(-8, 8))
            pitch.add(tt, rng.choice([-4, 0, 3, 6]))
            tt += rng.uniform(0.8, 1.6)
        yaw.add(t1 - 0.5, 0)
        L.add(t1, free)
        R.add(t1, lowered)

    def wipe_at(t0, t1, cx):
        st = (cx - 0.2, -15.18, 0)
        fig.put(t0, *st)
        fig.put(t1, *st)
        if t0 > 0.0:
            L.add(t0, free)
            R.add(t0, lowered)
        lean.add(t0 + 0.5, 18).add(t1 - 0.3, 18)
        R.add(t0 + 0.5, wiper(cx)).add(t1 - 0.4, wiper(cx))
        L.add(t0 + 0.5, on_bar(cx - 0.45)).add(t1 - 0.4, on_bar(cx - 0.45))
        pitch.add(t0 + 0.5, 25).add(t1 - 0.4, 25)
        if t1 < LOOP:
            L.add(t1, free)
            R.add(t1, lowered)

    def polish_at(t0, t1):
        fig.put(t0 - 1.0, *HOLDP)
        fig.put(t0, *BACK)
        lean.add(t0 - 0.6, 28).add(t0, 28)
        L.add(t0 - 0.6, fig.named("back")).add(t0, fig.named("back"))
        fig.contacts.append((t0, "back", "PG", BACK_SPOT))
        pgev.append((t0, "L", None))
        fig.put(t0 + 0.8, *HOLDP)
        fig.put(t1 - 0.8, *HOLDP)
        lean.add(t0 + 0.8, 6).add(t1 - 0.8, 6)
        L.add(t0 + 0.8, hold).add(t1 - 0.8, hold)
        R.add(t0 - 0.6, lowered).add(t0 + 1.2, polish).add(t1 - 1.0, polish).add(t1 - 0.6, lowered)
        pitch.add(t0 + 0.8, 22).add(t1 - 0.8, 22)
        fig.put(t1, *BACK)
        lean.add(t1, 28)
        L.add(t1, fig.named("back")).add(t1 + 0.6, free)
        fig.contacts.append((t1, "back", "PG", BACK_SPOT))
        pgev.append((t1, "spot", BACK_SPOT))
        lean.add(t1 + 0.6, 8)
        fig.put(t1 + 0.6, *BACK)

    # Pours must not overlap; fill the gaps with the bar chores.
    for (a0, a1, *_a), (b0, b1, *_b) in zip(pours, pours[1:]):
        if b0 - a1 < 5.0:
            raise RuntimeError(f"barman double-booked: serve {a1:.1f} then collect {b0:.1f}")
    rng = random.Random("barman")
    chores = []
    gaps = [(pours[i][1] + 2.6, pours[i + 1][0] - 2.4) for i in range(len(pours) - 1)]
    first, last = pours[0][0] - 2.4, pours[-1][1] + 2.6
    seam_x = 2.50
    items = []
    for t_c, t_s, key, spot, kind in pours:
        items.append((t_c - 0.8, "pour", (t_c, t_s, key, spot, kind)))
    items.append((0.0, "wipe", (0.0, first, seam_x)))
    items.append((last, "wipe", (last, LOOP, seam_x)))
    cycle = ["polish", "chat", "wipe", "chat", "polish", "wipe"]
    for i, (a, b) in enumerate(gaps):
        if b - a < 1.5:
            continue                       # too tight for a chore: he just moves on
        kind = cycle[i % len(cycle)]
        if b - a < 6.0:
            kind = "wipe"
        if kind == "polish" and b - a < 9.0:
            kind = "chat"
        if kind == "polish":
            items.append((a + 1.6, "polish", (a + 1.6, b)))
        elif kind == "chat":
            x = rng.choice([2.30, 2.80, 3.70])
            items.append((a, "chat", (a, b, x, -20 if x < 2.5 else 15)))
        else:
            items.append((a, "wipe", (a, b, rng.choice([2.0, 2.6, 4.2, 5.0]))))
    for _t, kind, args in sorted(items, key=lambda it: it[0]):
        if kind == "pour":
            pour(*args)
        elif kind == "wipe":
            wipe_at(*args)
        elif kind == "chat":
            lean_chat(*args)
        else:
            polish_at(*args)
    fig.pump.add(0.0, 0).add(LOOP, 0)
    for kind, G in GL.items():
        G["fill"].add(0.0, 0.001).add(LOOP, 0.001)
        G["segs"] = segs_from(gev[kind], LOOP, "hidden", next(p[3] for p in pours if p[4] == kind))
    PG["fill"].add(0.0, 0.001).add(LOOP, 0.001)
    PG["segs"] = segs_from(pgev, LOOP, "spot", BACK_SPOT)
    yaw.add(0.0, 0).add(LOOP, 0)
    pitch.add(0.0, 25).add(LOOP, 25)
    fig.vis.add(0.0, 1.0).add(LOOP, 1.0)
    fig.root.done()
    for t_c, t_s, key, spot, kind in pours:
        key = key + GL[kind]["name"]
        fig.wrist.setdefault(key, None)
        if fig.wrist[key] is None:
            fig.wrist[key] = fig.to_local(t_c, spot + guess)
    for kind, G in GL.items():
        t_first = next(p[0] for p in pours if p[4] == kind)
        fig.wrist["pump" + G["name"]] = fig.to_local(t_first + 1.8, PUMP_SPOT + guess)
    fig.wrist["back"] = None
    for t0, _m, _s in [e for e in pgev if e[1] == "L"][:1]:
        fig.wrist["back"] = fig.to_local(t0, BACK_SPOT + guess)
    return fig


# --- NE bedroom couple --------------------------------------------------------
# A couple in the NE bed on a 20-minute loop, under a duvet that drapes over
# whatever is beneath it. Implied, not shown: heads (and now and then a
# shoulder or an arm) above the cover. Lying side by side talking, turning in
# to kiss, him on top, rolling over with her on top, spooning, resting with
# her head on his chest, and back to talking. The duvet is its own armature
# (Fig_BedDuvet): an 11 x 15 grid of lift bones; every frame each rises to just
# above the bodies under it (capsules around the limbs and torso).
BED_LOOP = 1200.0
MZ = 4.14                                         # mattress / duvet top
BED_X = (7.66, 9.80)
BED_Y = (6.50, 8.45)                              # duvet head edge (shoulders) to foot


def orient(head, face):
    z = Vector(head).normalized()
    y = (Vector(face) - z * Vector(face).dot(z)).normalized()
    x = y.cross(z)
    return Matrix((x, y, z)).transposed().to_quaternion()


def _qkeys_fix(keys):
    """Keep quaternion keys in one hemisphere so nlerp takes the short way."""
    prev = None
    for i, kv in enumerate(keys):
        q = kv[1]
        if prev is not None and prev.dot(q) < 0:
            q = -q
            keys[i] = (kv[0], q) + tuple(kv[2:])
        prev = q


def _bed_pose(name, who):
    """(root xy, root z, orientation, lean, arms L/R local, feet L/R local)."""
    a = math.radians(2)                           # flat; the pillows lift the upper body via lean
    up_head = (0, -math.cos(a), math.sin(a))
    back = orient(up_head, (0, math.sin(a), math.cos(a)))
    rest_arms = (V((-0.12, 0.16, 1.02)), V((0.12, 0.16, 1.02)))
    straight = (V((-0.10, 0.0, 0.09)), V((0.10, 0.0, 0.09)))
    if name == "backs":
        x = 8.20 if who == "F" else 9.25
        return (x, 7.95), MZ + 0.11, back, 16, rest_arms, straight
    if name == "facing":                          # on their sides, face to face
        x = 8.56 if who == "F" else 8.84
        face = (1, 0, 0) if who == "F" else (-1, 0, 0)
        hug = (V((-0.05, 0.26, 1.30)), V((0.18, 0.22, 1.22)))
        knees = (V((-0.10, 0.12, 0.30)), V((0.10, 0.16, 0.34)))
        return (x, 7.92), MZ + 0.17, orient((0, -1.0, 0.03), face), 10, hug, knees
    if name in ("him_top", "her_top"):
        top = (name == "him_top") == (who == "M")
        if not top:                               # on the back, knees up
            hug = (V((-0.22, 0.30, 1.26)), V((0.22, 0.30, 1.26)))
            knees = (V((-0.24, -0.04, 0.40)), V((0.24, -0.04, 0.40)))
            return (8.70, 7.95), MZ + 0.11, back, 12, hug, knees
        head = V((0, -0.95, 0.30))
        hips = V((8.70, 7.95 - 0.93 + 0.03, MZ + 0.11 + 0.24))
        root = hips - head * 0.93
        arms = (V((-0.30, 0.25, 1.30)), V((0.30, 0.25, 1.30)))         # forearms down to the mattress
        feet = (V((-0.16, 0.30, 0.10)), V((0.16, 0.30, 0.10)))
        return (root.x, root.y), root.z, orient(head, (0, -0.30, -0.95)), 6, arms, feet
    if name == "spoon":                           # both on the left side, him behind
        x = 8.48 if who == "F" else 8.76
        face = (-1, 0, 0)
        arms = (V((-0.10, 0.18, 1.05)), V((0.12, 0.30, 1.15) if who == "M" else (0.10, 0.20, 1.05)))
        knees = (V((-0.10, 0.20, 0.30)), V((0.10, 0.22, 0.32)))
        return (x, 7.94), MZ + 0.18, orient((0, -1.0, 0.03), face), 8, arms, knees
    if name == "chest":                           # resting: he on his back, her head on his chest
        if who == "M":
            return (8.95, 7.95), MZ + 0.11, back, 16, (V((-0.25, 0.10, 1.25)), V((0.12, 0.16, 1.02))), straight
        return (8.62, 8.12), MZ + 0.17, orient((0.06, -1.0, 0.06), (1, 0, 0.15)), 10, \
            (V((-0.05, 0.22, 1.20)), V((0.15, 0.30, 1.25))), (V((-0.10, 0.12, 0.30)), V((0.10, 0.16, 0.34)))
    raise KeyError(name)


def _bed_set(fig, t, name, who):
    (x, y), z, q, lean, arms, feet = _bed_pose(name, who)
    fig.root.add(t, V((x, y, 0)))
    fig.zk.add(t, z)
    fig.rq.add(t, q)
    fig.lean.add(t, lean)
    fig.L.add(t, arms[0])
    fig.R.add(t, arms[1])
    fig.fL.add(t, feet[0])
    fig.fR.add(t, feet[1])


def _rhythm(fig, t0, t1, name, who, amp, f0, f1, axis, lean_amp=3.0, phase=0.0):
    """Rhythmic motion along the body axis, rate easing from f0 to f1 Hz."""
    (x, y), z, q, lean, arms, feet = _bed_pose(name, who)
    ax = Vector(axis).normalized() * amp
    D = t1 - t0

    def ph(t):
        u = max(0.0, min(D, t - t0))
        return 2 * math.pi * (f0 * u + (f1 - f0) * u * u / (2 * D)) + phase

    def env(t):                                   # fade in and out over 3 s
        return min(1.0, max(0.0, (t - t0) / 3.0), max(0.0, (t1 - t) / 3.0))

    rootf = lambda t: V((x + ax.x * env(t) * math.sin(ph(t)), y + ax.y * env(t) * math.sin(ph(t)), 0))
    zf = lambda t: z + ax.z * env(t) * math.sin(ph(t))
    leanf = lambda t: lean + lean_amp * env(t) * math.sin(ph(t) + 0.6)
    for tt in (t0, t1):
        fig.root.add(tt, rootf)
        fig.zk.add(tt, zf)
        fig.lean.add(tt, leanf)
        fig.rq.add(tt, q)


def _bedroom():
    her = Figure("BedF", dict(sex="f", skin="eec5a8", hair="6b3e26", hair_style="long", top="efe6da",
                              legs="eec5a8", shoes="eec5a8", sleeves="long", collar=False, lips="b04a55"),
                 loop=BED_LOOP)
    him = Figure("BedM", dict(sex="m", skin="d9a585", hair="2a211c", top="d9a585", legs="d9a585",
                              shoes="d9a585", sleeves="long", collar=False), loop=BED_LOOP)
    caps = [("Spine", 0.13), ("Chest", 0.13), ("Hips", 0.13), ("Thigh.L", 0.08), ("Thigh.R", 0.08),
            ("Shin.L", 0.06), ("Shin.R", 0.06), ("Foot.L", 0.06), ("Foot.R", 0.06),
            ("UpperArm.L", 0.055), ("UpperArm.R", 0.055), ("Forearm.L", 0.045), ("Forearm.R", 0.045),
            ("Hand.L", 0.05), ("Hand.R", 0.05)]
    for fig in (her, him):
        fig.capsules = caps
        fig.vis.add(0.0, 1.0).add(BED_LOOP, 1.0)
    rng = random.Random("bed")
    # (start, pose) sequence; transitions take 4 s.
    seq = [(0, "backs"), (150, "facing"), (330, "him_top"), (560, "her_top"), (720, "spoon"),
           (900, "chest"), (1080, "backs")]
    rhythm = {"him_top": (345, 540, "M", 0.045, 0.7, 1.15), "her_top": (575, 705, "F", 0.04, 0.8, 1.1),
              "spoon": (740, 880, "M", 0.03, 0.6, 0.9)}
    for fig, who in ((her, "F"), (him, "M")):
        for i, (t, name) in enumerate(seq):
            end = seq[i + 1][0] if i + 1 < len(seq) else BED_LOOP
            _bed_set(fig, t + (4.0 if t else 0.0), name, who)
            _bed_set(fig, end, name, who)
            if name in rhythm:
                r0, r1, mover, amp, f0, f1 = rhythm[name]
                _, _, q, *_ = _bed_pose(name, who)
                axis = q.to_matrix() @ V((0, 0, 1))
                if who == mover:
                    _rhythm(fig, r0, r1, name, who, amp, f0, f1, axis)
                else:                             # the partner moves a little in counterpoint
                    _rhythm(fig, r0, r1, name, who, amp * 0.3, f0, f1, axis, lean_amp=1.0, phase=math.pi)
        _bed_set(fig, BED_LOOP, "backs", who)
        fig.rq.done()
        _qkeys_fix(fig.rq)
    # Heads: talking (turn to each other), kissing, resting, glances.
    def heads(t0, t1, kind):
        tt = t0 + 4.5
        while tt < t1 - 1.0:
            for fig, side in ((her, 1), (him, -1)):
                if kind == "talk":
                    fig.yaw.add(tt, side * rng.uniform(25, 45))
                    fig.pitch.add(tt, rng.uniform(-6, 6))
                elif kind == "kiss":
                    fig.yaw.add(tt, rng.uniform(-10, 10))
                    fig.pitch.add(tt, rng.uniform(-8, 4))
                elif kind == "top":
                    fig.yaw.add(tt, rng.uniform(-20, 20))
                    fig.pitch.add(tt, rng.uniform(-15, 20))
                else:
                    fig.yaw.add(tt, rng.uniform(-8, 8) + side * 10)
                    fig.pitch.add(tt, rng.uniform(0, 8))
            tt += rng.uniform(1.2, 3.0)
    for i, (t, name) in enumerate(seq):
        end = seq[i + 1][0] if i + 1 < len(seq) else BED_LOOP
        kind = {"backs": "talk", "facing": "kiss", "him_top": "top", "her_top": "top", "spoon": "rest",
                "chest": "rest"}[name]
        heads(t, end, kind)
    for fig in (her, him):
        fig.yaw.add(0.0, 0).add(BED_LOOP, 0)
        fig.pitch.add(0.0, 0).add(BED_LOOP, 0)
    return [her, him]


def _bed_duvet(results, report):
    """Build Fig_BedDuvet: a grid of lift bones and a skinned sheet over the NE
    bed, keyed per frame to clear the couple's bodies."""
    sc = bpy.context.scene
    couple = [fr for fig, _a, fr, _e in results if fig.tag in ("BedF", "BedM")]
    if len(couple) != 2:
        return None
    dg = bpy.context.evaluated_depsgraph_get()
    hidden = []
    for o in sc.objects:
        if o.name.startswith(("Fig_", "NavMesh", "Seat_", "Spawn_")) and not o.hide_viewport:
            o.hide_viewport = True
            hidden.append(o)
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()

    def surface(x, y):
        hit, loc, *_ = sc.ray_cast(dg, Vector((x, y, MZ + 1.2)), Vector((0, 0, -1)))
        return (loc.z if hit and loc.z < MZ + 0.2 else MZ) + 0.02
    NX, NY = 11, 15
    gx = [BED_X[0] + (BED_X[1] - BED_X[0]) * i / (NX - 1) for i in range(NX)]
    gy = [BED_Y[0] + (BED_Y[1] - BED_Y[0]) * j / (NY - 1) for j in range(NY)]
    base = [[surface(x, y) for x in gx] for y in gy]
    for o in hidden:
        o.hide_viewport = False
    arm_data = bpy.data.armatures.new("Fig_BedDuvetRig")
    arm = bpy.data.objects.new("Fig_BedDuvet", arm_data)
    sc.collection.objects.link(arm)
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode='EDIT')
    for j, y in enumerate(gy):
        for i, x in enumerate(gx):
            b = arm_data.edit_bones.new(f"BedDuvet_{i}_{j}")
            b.head, b.tail = Vector((x, y, base[j][i])), Vector((x, y + 0.1, base[j][i]))
    bpy.ops.object.mode_set(mode='OBJECT')
    # Sheet: 25 x 31 vertices, bilinear weights to the four surrounding lift bones.
    me = bpy.data.meshes.new("Fig_BedDuvetMesh")
    SX, SY = 25, 31
    verts, faces, wts = [], [], []
    for jj in range(SY):
        v = jj / (SY - 1)
        y = BED_Y[0] + (BED_Y[1] - BED_Y[0]) * v
        for ii in range(SX):
            u = ii / (SX - 1)
            x = BED_X[0] + (BED_X[1] - BED_X[0]) * u
            fx, fy = u * (NX - 1), v * (NY - 1)
            i0, j0 = min(int(fx), NX - 2), min(int(fy), NY - 2)
            ax, ay = fx - i0, fy - j0
            ww = {(i0, j0): (1 - ax) * (1 - ay), (i0 + 1, j0): ax * (1 - ay), (i0, j0 + 1): (1 - ax) * ay,
                  (i0 + 1, j0 + 1): ax * ay}
            z = sum(w * base[j][i] for (i, j), w in ww.items())
            verts.append((x, y, z))
            wts.append(ww)
    for jj in range(SY - 1):
        for ii in range(SX - 1):
            a = jj * SX + ii
            faces.append((a, a + 1, a + SX + 1, a + SX))
    me.from_pydata(verts, [], faces)
    for poly in me.polygons:
        poly.use_smooth = True
    ob = bpy.data.objects.new("Fig_BedDuvetBody", me)
    sc.collection.objects.link(ob)
    groups = {}
    for vi, ww in enumerate(wts):
        for (i, j), w in ww.items():
            if w > 1e-4:
                groups.setdefault((i, j), []).append((vi, w))
    for (i, j), lst in groups.items():
        vg = ob.vertex_groups.new(name=f"BedDuvet_{i}_{j}")
        for vi, w in lst:
            vg.add([vi], w, 'REPLACE')
    mat = bpy.data.materials.get("FigDuvet") or bpy.data.materials.new("FigDuvet")
    mat.use_nodes = True
    bs = mat.node_tree.nodes['Principled BSDF']
    bs.inputs['Base Color'].default_value = (0.87, 0.78, 0.62, 1.0)    # warm ivory, as the beds
    bs.inputs['Roughness'].default_value = 0.85
    mat.use_backface_culling = False
    me.materials.append(mat)
    ob.parent = arm
    ob.modifiers.new("Armature", 'ARMATURE').object = arm

    import numpy as np
    # Lift bone heights: clear every body part within half a grid step of the
    # bone (so the bilinear sheet between bones stays above the bodies too).
    hx = (gx[1] - gx[0]) / 2
    hy = (gy[1] - gy[0]) / 2
    pts = []
    for j, y in enumerate(gy):
        for i, x in enumerate(gx):
            for dx, dy in ((0, 0), (hx, 0), (-hx, 0), (0, hy), (0, -hy), (hx, hy), (-hx, hy), (hx, -hy), (-hx, -hy)):
                pts.append((x + dx, y + dy))
    P2 = np.array(pts)                                    # (B*9, 2)
    nb = NX * NY
    basez = np.array([base[j][i] for j in range(NY) for i in range(NX)])
    n = len(couple[0])
    Z = np.zeros((nb, n))
    for fi in range(n):
        caps = couple[0][fi]["caps"] + couple[1][fi]["caps"]
        A = np.array([[c[0].x, c[0].y, c[0].z] for c in caps])
        Bc = np.array([[c[1].x, c[1].y, c[1].z] for c in caps])
        R = np.array([c[2] for c in caps])
        D = Bc - A
        L2 = D[:, 0] ** 2 + D[:, 1] ** 2
        L2s = np.where(L2 < 1e-9, 1.0, L2)
        sx = ((P2[:, None, 0] - A[None, :, 0]) * D[None, :, 0] + (P2[:, None, 1] - A[None, :, 1]) * D[None, :, 1]) / L2s
        sx = np.clip(np.where(L2[None, :] < 1e-9, 0.0, sx), 0.0, 1.0)
        C = A[None, :, :] + D[None, :, :] * sx[:, :, None]
        h2 = (P2[:, None, 0] - C[:, :, 0]) ** 2 + (P2[:, None, 1] - C[:, :, 1]) ** 2
        re = R + 0.07
        inside = h2 < re[None, :] ** 2
        top = np.where(inside, C[:, :, 2] + R[None, :] * np.sqrt(np.clip(1.0 - h2 / re[None, :] ** 2, 0, 1)) + 0.03, -1.0)
        best = top.max(axis=1).reshape(nb, 9).max(axis=1)
        Z[:, fi] = np.maximum(0.0, best - basez)
    act = bpy.data.actions.new("Fig_BedDuvetLoop")
    arm.animation_data_create()
    arm.animation_data.action = act
    slot = arm.animation_data.action_slot or act.slots.new(id_type='OBJECT', name=arm.name)
    arm.animation_data.action_slot = slot
    cb = anim_utils.action_ensure_channelbag_for_slot(act, slot)
    kept = 0
    for j in range(NY):
        for i in range(NX):
            zs = Z[j * NX + i].tolist()
            if max(zs) < 1e-4:
                continue
            # The lift bones point +y with roll 0, so their local Z is world up.
            keep = _thin([zs], 0.004)
            kept += len(keep)
            fc = cb.fcurves.new(f'pose.bones["BedDuvet_{i}_{j}"].location', index=2,
                                group_name=f"BedDuvet_{i}_{j}")
            fc.keyframe_points.add(len(keep))
            co = []
            for k in keep:
                co += [k, zs[k]]
            fc.keyframe_points.foreach_set("co", co)
            for kp in fc.keyframe_points:
                kp.interpolation = 'LINEAR'
            fc.update()
    report(f"FIGURE BedDuvet: {NX * NY} lift bones, {kept} keys")
    return arm


BALL_SCRIPT = None
BALL_GORES = ("e8302a", "f4f2ea", "2a6ad8", "f6c62a", "f4f2ea", "3aa84a")


def _tub_ball(results, report):
    """Fig_TubBall: one bone, keyed per frame from the hot tub's solved hands
    (held between the palms, an arc between thrower and catcher, floating on
    the water between games)."""
    if not BALL_SCRIPT:
        return None
    fr = {fig.tag: frames for fig, _a, frames, _e in results if fig.tag in TUB_HOME}
    if len(fr) != 3:
        return None
    sc = bpy.context.scene
    n = int(round(LOOP * FPS))

    def mid(tag, t):
        rec = fr[tag][min(n, int(round(t * FPS)))]
        return (rec["palm"]["L"] + rec["palm"]["R"]) / 2

    segs = []                                       # (t0, t1, kind, args)
    t_prev, state = 0.0, ("float",)
    for e in sorted(BALL_SCRIPT, key=lambda e: e[2] if e[0] == "pick" else e[3] if e[0] == "throw" else e[2]):
        if e[0] == "pick":                         # drawn in through the water to the hands
            segs.append((t_prev, e[2] - 0.6, "float", None))
            segs.append((e[2] - 0.6, e[2] + 0.3, "lift", e[1]))
            t_prev, state = e[2] + 0.3, ("held", e[1])
        elif e[0] == "throw":
            segs.append((t_prev, e[3], "held", e[1]))
            segs.append((e[3], e[4], "fly", (e[1], e[2])))
            t_prev = e[4]
            state = ("held", e[2])
        else:
            segs.append((t_prev, e[2], "held", e[1]))
            segs.append((e[2], e[3], "drop", e[1]))
            t_prev = e[3]
    segs.append((t_prev, LOOP + 1.0, "float", None))

    def pos(t):
        for t0, t1, kind, a in segs:
            if t0 - 1e-6 <= t < t1 - 1e-6 or (t1 > LOOP and t >= t0):
                if kind == "float":
                    return _ball_float(t), False
                if kind == "held":
                    return mid(a, t), False
                if kind == "lift":
                    s = ease((t - t0) / (t1 - t0))
                    return _ball_float(t).lerp(mid(a, t), s), False
                p0 = mid(a[0] if kind == "fly" else a, t0)
                p1 = mid(a[1], t1) if kind == "fly" else _ball_float(t1)
                s = (t - t0) / (t1 - t0)
                h = 0.35 + 0.12 * (p1 - p0).length
                return p0.lerp(p1, s) + Vector((0, 0, 4 * h * s * (1 - s))), True
        return _ball_float(t), False

    arm_data = bpy.data.armatures.new("Fig_TubBallRig")
    arm = bpy.data.objects.new("Fig_TubBall", arm_data)
    sc.collection.objects.link(arm)
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode='EDIT')
    b = arm_data.edit_bones.new("TubBall_Ball")
    b.head, b.tail = BALL_HOME.copy(), BALL_HOME + Vector((0, 0, 0.1))
    bpy.ops.object.mode_set(mode='OBJECT')
    me = bpy.data.meshes.new("Fig_TubBallMesh")
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=18, v_segments=10, radius=BALL_R,
                              matrix=Matrix.Translation(BALL_HOME))
    bm.to_mesh(me)
    bm.free()
    cols = []
    for poly in me.polygons:
        c = poly.center - BALL_HOME
        if abs(c.z) > BALL_R * 0.86:
            hexc = "f4f2ea"
        else:
            a = (math.atan2(c.y, c.x) + math.pi) / (2 * math.pi)
            hexc = BALL_GORES[int(a * 6) % 6]
        cols.extend(_rgba(hexc) * poly.loop_total)
        poly.use_smooth = True
    attr = me.color_attributes.new("Col", 'BYTE_COLOR', 'CORNER')
    attr.data.foreach_set("color_srgb", cols)
    me.color_attributes.active_color = attr
    body, _glass = _materials()
    me.materials.append(body)
    ob = bpy.data.objects.new("Fig_TubBallBody", me)
    sc.collection.objects.link(ob)
    ob.vertex_groups.new(name="TubBall_Ball").add(list(range(len(me.vertices))), 1.0, 'REPLACE')
    ob.parent = arm
    ob.modifiers.new("Armature", 'ARMATURE').object = arm
    rest = arm.data.bones["TubBall_Ball"].matrix_local.copy()
    q = Quaternion((1, 0, 0, 0))
    locs, quats = [], []
    prev = None
    low = 9.0
    for fi in range(n + 1):
        t = fi / FPS
        p, flying = pos(t)
        if prev is not None:
            d = p - prev
            if flying and d.length > 1e-5:
                axis = Vector((0, 0, 1)).cross(d)
                if axis.length > 1e-6:
                    q = Quaternion(axis.normalized(), d.length / BALL_R) @ q
            elif not flying:
                q = Quaternion((0, 0, 1), 0.02) @ q
        prev = p
        low = min(low, p.z)
        want = Matrix.Translation(p) @ q.to_matrix().to_4x4() @ rest.to_3x3().to_4x4()
        m = rest.inverted() @ want
        locs.append(m.to_translation())
        qq = m.to_quaternion()
        if quats and quats[-1].dot(qq) < 0:
            qq.negate()
        quats.append(qq)
    # Close the loop: the spin is unwound over the last second.
    act = bpy.data.actions.new("Fig_TubBallLoop")
    arm.animation_data_create()
    arm.animation_data.action = act
    slot = arm.animation_data.action_slot or act.slots.new(id_type='OBJECT', name=arm.name)
    arm.animation_data.action_slot = slot
    cb = anim_utils.action_ensure_channelbag_for_slot(act, slot)
    kept = 0
    seam = int(FPS * 1.0)
    q0, q1 = quats[0], quats[-1 - seam]
    for i in range(n + 1 - seam, n + 1):
        s = (i - (n - seam)) / seam
        quats[i] = q1.slerp(q0 if q1.dot(q0) >= 0 else -q0, s)
        if quats[i].dot(quats[i - 1]) < 0:
            quats[i].negate()
    for path, values, width, tol in (("location", locs, 3, 0.002), ("rotation_quaternion", quats, 4, 0.004)):
        rows = [[v[i] for v in values] for i in range(width)]
        keep = _thin(rows, tol)
        kept += len(keep)
        for i in range(width):
            fc = cb.fcurves.new(f'pose.bones["TubBall_Ball"].{path}', index=i, group_name="TubBall_Ball")
            fc.keyframe_points.add(len(keep))
            co = []
            for k in keep:
                co += [k, rows[i][k]]
            fc.keyframe_points.foreach_set("co", co)
            for kp in fc.keyframe_points:
                kp.interpolation = 'LINEAR'
            fc.update()
    for pb in arm.pose.bones:
        pb.rotation_mode = 'QUATERNION'
    report(f"FIGURE TubBall: {len(BALL_SCRIPT)} moves, {kept} keys, lowest centre z {low:.2f}")
    return arm

# --- Gates --------------------------------------------------------------------
def _gate_spacing(results, report):
    """No two people within 0.40 m (hips, horizontal) while both are visible."""
    walkers = [(fig, fr) for fig, _arm, fr, _e in results if fig.tag != "Bm" and not fig.tag.startswith("Bed")]
    bad = []
    n = int(round(LOOP * FPS))
    for fi in range(0, n + 1, 3):
        t = fi / FPS
        pts = []
        for fig, fr in walkers:
            rec = fr[int(round((t % fig.loop) * FPS))]
            if rec["vis"] > 0.5:
                pts.append((fig.tag, rec["pos"]))
        for i in range(len(pts)):
            for j in range(i + 1, len(pts)):
                d = (pts[i][1].xy - pts[j][1].xy).length
                if d < 0.40:
                    bad.append((t, pts[i][0], pts[j][0], d))
    seen = {}
    for t, a, b, d in bad:
        seen.setdefault((a, b), (t, d))
    for (a, b), (t, d) in seen.items():
        report(f"SPACING GATE: {a} and {b} {d:.2f} m apart at {t:.1f}s")
    return not seen


def _gate_routes(results, report):
    """Walking routes must be clear floor: rays down at the hips and 0.15 m
    around must reach the carpet (skipped without the Rovers geometry)."""
    sc = bpy.context.scene
    if not bpy.data.objects.get("RoversBar"):
        report("ROUTE GATE: skipped (no Rovers geometry in this scene)")
        return True
    hidden = []
    for o in sc.objects:
        if o.name.startswith(("Fig_", "NavMesh", "Seat_", "Spawn_")) and not o.hide_viewport:
            o.hide_viewport = True
            hidden.append(o)
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    bad = {}
    for fig, _arm, fr, _e in results:
        if fig.tag in ("Bm", "Pno"):
            continue
        for i in range(1, len(fr), 2):
            a, b = fr[i - 1]["pos"], fr[i]["pos"]
            # (x < -3.3 inside the pub is the glide through the toilet doors;
            # north of the pub's front wall is the barmaid's way to the hot tub.)
            if fr[i]["vis"] < 0.5 or (b - a).xy.length < 0.002 or abs(b.z - CARPET) > 1e-3 or \
                    (b.x < -3.3 and b.y < -9.8):
                continue
            for off in ((0, 0), (0.15, 0), (-0.15, 0), (0, 0.15), (0, -0.15)):
                o = Vector((b.x + off[0], b.y + off[1], 1.6))
                hit, loc, _n, _i, ob, _m = sc.ray_cast(dg, o, Vector((0, 0, -1)))
                if hit and loc.z > CARPET + 0.08:
                    bad.setdefault(fig.tag, (i / FPS, ob.name, tuple(round(c, 2) for c in loc)))
            d = Vector((b.x - a.x, b.y - a.y, 0.0))      # walls: along the step, not down
            for z in (1.0, 1.5):
                hit, loc, _n, _i, ob, _m = sc.ray_cast(dg, Vector((a.x, a.y, z)), d.normalized(), distance=d.length)
                if hit:
                    bad.setdefault(fig.tag, (i / FPS, ob.name, tuple(round(c, 2) for c in loc)))
    for o in hidden:
        o.hide_viewport = False
    for tag, (t, ob, loc) in bad.items():
        report(f"ROUTE GATE: {tag} walks into {ob} at {loc} ({t:.1f}s)")
    return not bad


# --- Build --------------------------------------------------------------------
def build(report=print, only=None, strict=True):
    sc = bpy.context.scene
    sc.render.fps = FPS
    sc.render.fps_base = 1.0
    global PLANNED
    cast, pours, _pat = _plan(PATTERN, report)
    figs = [m.f for m in cast.values()] + [_barman(pours)] + _bedroom()
    PLANNED = list(figs)                   # dinner_figures keeps its party out of their way (root tracks)
    if only:
        figs = [f for f in figs if f.tag in only]
    results = []
    for fig in figs:
        fig.root.done()
        fig.zk.done()
        fig.rq.done()
        for k in (fig.vis, fig.lean, fig.pitch, fig.yaw, fig.L, fig.R, fig.fL, fig.fR):
            if k:
                k.done()
        if fig.pump is not None:
            fig.pump.done()
        for g in fig.glasses:
            g["fill"].done()
            g["tilt"].done()
            g["scale"].done()
        arm, frames, err = _realise(fig, report)
        results.append((fig, arm, frames, err))
    _bed_duvet(results, report)
    _tub_ball(results, report)
    ok = _gate_spacing(results, report) & _gate_routes(results, report)
    worst = max(e for *_x, e in results)
    if worst > 0.006:
        report(f"CONTACT GATE: worst glass contact {worst * 1000:.1f} mm")
        ok = False
    report(f"FIGURES GATE {'passed' if ok else 'FAILED'}")
    if strict and not ok:
        raise RuntimeError("FIGURES GATE failed")
    sc.frame_set(0)
    return results
