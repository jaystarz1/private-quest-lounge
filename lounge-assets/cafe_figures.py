# Café du Parc, the Paris café on the ground balcony: a couple at a bistro
# table, the empty table for two (where visitors sit, an espresso and a slice
# of cake set at each place), the dinner party's chef bringing the couple their
# espressos, and a mime who never stops entertaining.
#
# It runs on the dinner party's session clock (dinner_figures): the chef is
# one rig with a Dinner clip and a Lounge loop, so the people he serves have
# to share both. Every rig here is a Fig_Din* rig with those two clips.
#
# The mime (Bip: white face, Breton jersey, battered opera hat with a flower,
# white gloves) goes from one audience to the next on his unicycle, juggling
# as he rides, and does an act wherever he stops. His three acts:
#   fire: three torches out of the quiver on his hip, lit by a flame he snaps
#     onto his fingertip, juggled high and fast with flashes and pirouettes,
#     blown out;
#   clubs: three clubs out of the quiver, slow and high, fast, flashes;
#   magic: a ball from the air, the floating silver ball, silks from his fist,
#     a fan of cards sprung hand to hand and thrown up, a bouquet from nowhere;
# and at the café the rola bola: up on a board across a roller, finding his
# balance, then juggling clubs up there.
# Every PHASE (six minutes) from the first second of a session is a round:
# an act at the café (or a ride round the house), one on the Rovers' floor and
# one at the hot tub, the last two at fixed marks of the Rovers regulars' loop
# (rovers_figures.SHOW) so the regulars watch (the client starts each session
# on their beat). During dinner the head of the dinner table takes the hot
# tub's place three times; after it the dinner party come out of the snug and
# stand round him in the Rovers. The rounds turn the acts round, so every
# audience sees all of them.
#
# The couple watch him at the café (applauding each bow), talk to each other
# when he is away, and sip their espressos. The chef makes two espressos at the
# machine on the back counter, carries them out on a small tray and swaps them
# for the empties.
#
# Everything he handles is one prop rig (Fig_DinCafeProps), keyed per frame
# from his solved hands and root, like the dinner's prop rig.
import math
import random
import numpy as np
import bpy
import bmesh
from mathutils import Vector, Matrix
import rovers_figures as RF
from rovers_figures import Figure, Keys, heading
import dinner_figures as DF

V = Vector
FPS = RF.FPS
Z0 = DF.RV_FLOOR                                  # the balcony and café paving

# --- Layout -------------------------------------------------------------------
TABLE = V((7.95, -8.25))                          # the couple's bistro table (build-penthouse CafeCouple*)
TABLE_TOP = 0.8125
TABLE_R = 0.38
SEAT_TOP = 0.50
CHAIR_Y = -8.95                                   # both chairs on the south side, facing the café
SEAT = {"A": (7.68, CHAIR_Y), "B": (8.22, CHAIR_Y)}
CUP = {"A": V((7.72, -8.45, TABLE_TOP)), "B": V((8.18, -8.45, TABLE_TOP))}
JAY_TABLE = V((9.50, -7.30))                      # the visitors' table (Seat_E1 / Seat_E2)
JAY_SETS = {"N": (V((9.50, -7.08, TABLE_TOP + 0.006)), V((9.66, -7.12, TABLE_TOP + 0.006))),
            "S": (V((9.50, -7.52, TABLE_TOP + 0.006)), V((9.34, -7.48, TABLE_TOP + 0.006)))}   # cup, cake
STAGE = (9.60, -5.60)                             # in front of the café, facing the tables
MIME_CHAIR = (11.02, -5.85)                       # his rattan chair by the café front
MIME_CHAIR_YAW = 80.0
MIME_SEAT_TOP = 0.50
UNI_PARK = V((11.18, -6.70))                      # leaning on the east parapet glass
UNI_PARK_YAW = 0.0
COUNTER_Z = 1.14                                  # the café's marble serving counter (CafeStoneServingCounter)
MACHINE = V((10.70, -4.50, COUNTER_Z))            # espresso machine at its east end (build-penthouse CafeEspresso*)
SPOUT = V((10.68, -4.66, COUNTER_Z + 0.02))       # where a cup stands under the group head
C_MACHINE = (10.36, -4.98)                        # the chef's stance at the counter, facing it
CAFE_TRAY = V((10.33, -4.56, COUNTER_Z))          # the little café tray, on the counter, right in front of him
CHEF_OUT = [(7.05, DF.BACK_LINE), (7.05, -5.00), C_MACHINE]   # out through the café door to the counter
SERVE = {"A": ((7.32, -8.40), CUP["A"]), "B": ((8.58, -8.40), CUP["B"])}
ROUND_TABLE = [(7.32, -7.62), (8.58, -7.62)]      # north of the couple's table, between the two stops

MIME_LOOK = dict(sex="m", skin="f6f2ec", hair="1a1a1a", top="f4f2ec", stripes="1d2a48", legs="f0ece4",
                 shoes="141414", gloves="fafafa", sleeves="long", collar=False, tophat="1c1c1e", hatband="1c1c1e",
                 flower="d4283a", lips="c0283a", brow="141414", tears="1d2a48")
COUPLE_LOOK = {
    "A": dict(sex="f", skin="eec3a4", hair="2a1a12", hair_style="bob", top="1f2f52", legs="1f2f52",
              skirt="1f2f52", sleeves="long", lips="b03a48", beret="a8202e", necklace="e8e0d0"),
    "B": dict(sex="m", skin="d7a383", hair="5a4030", top="e8e2d6", jacket="5a4a3a", legs="3a3a40",
              sleeves="long", glasses="2a2a2a"),
}
TAGS = {"M": "DinMime", "A": "DinCafA", "B": "DinCafB"}
CUP_GRIP = 0.035


def floor_z(x, y):
    return DF.floor_z(x, y)


# --- Props (dinner prop rig: cups and the chef's café tray) --------------------
def add_props(P):
    """Called from dinner_figures.PropSet: the couple's cups (two sets, so a
    fresh pair can be carried out while the old pair is on the table) and the
    chef's tray."""
    P.cafe_cups = {}
    for who in ("A", "B"):
        for j in (1, 2):
            c = P.add(DF.Prop(f"Cafe{who}{j}", "cup"))
            c.grip = CUP_GRIP
            P.cafe_cups[(who, j)] = c
    P.cafe_tray = P.add(DF.Prop("CafeTray", "tray"))
    # Their glass of wine in the Rovers (white for her, red for him), brought
    # by the Rovers' second barmaid and topped up.
    P.cafe_wine = {}
    for who, wn in (("A", "white"), ("B", "red")):
        g = P.add(DF.Prop(f"CW{wn}{who}", "glass", ("liquid", wn)))
        g.fill0 = 0.0
        g.grip = DF.GLASS_GRIP[wn]
        P.cafe_wine[who] = g


def cup_mesh(P, b):
    """A white espresso cup on its saucer (base at the bone head)."""
    P.seg(b, (0, 0, 0), (0, 0, 0.008), 0.058, 0.062, "f6f3ec", segs=14)
    P.seg(b, (0, 0, 0.008), (0, 0, 0.012), 0.024, 0.026, "f6f3ec", segs=10)
    P.seg(b, (0, 0, 0.012), (0, 0, 0.060), 0.026, 0.034, "f6f3ec", segs=12, caps=False)
    P.seg(b, (0, 0, 0.052), (0, 0, 0.056), 0.031, 0.031, "3a2214", segs=12)
    P.seg(b, (0.034, 0, 0.040), (0.050, 0, 0.040), 0.006, 0.006, "f6f3ec", segs=6)


def initial_props(P):
    """Opening state of the dinner clip."""
    for who in ("A", "B"):
        P.cafe_cups[(who, 1)].at(0.0, ("spot", CUP[who].copy(), 0.0))
        P.cafe_cups[(who, 2)].at(0.0, ("hidden",))
        P.cafe_wine[who].at(0.0, ("hidden",))
    P.cafe_tray.at(0.0, ("spot", CAFE_TRAY.copy(), 0.0))


# --- The couple ---------------------------------------------------------------
Z_SEATED = SEAT_TOP + 0.08 - 0.93
FEET = ((-0.11, 0.46, 0.54), (0.11, 0.48, 0.54))
REST = {"L": V((-0.16, 0.33, 1.175)), "R": V((0.16, 0.33, 1.175))}
LAPH = {"L": V((-0.14, 0.28, 1.11)), "R": V((0.14, 0.28, 1.11))}
MOUTH = V((0.05, 0.20, 1.50))
CLAP = (V((-0.05, 0.33, 1.32)), V((0.05, 0.33, 1.32)))


# In the Rovers they have the table beside the blonde lady's in the first booth
# (Jay: not in the middle of the floor): she on the stool, facing the window,
# he on the cushion opposite; their glasses on the table's west side, where the
# Rovers barmaid reaches them from the gap between the tables. She drinks with
# her left hand, he with his right.
CAB_Z = {w: RF.CAB_SEAT[w] + 0.08 - 0.93 for w in "AB"}       # seated root z on the stool / the cushion
CAB_FEET = {"A": RF.SEAT_FEET["stool"], "B": RF.SEAT_FEET["bench"]}
WINE_SPOT = {"A": V((RF.CAB_TABLE[0] - 0.16, -11.24, RF.CAB_TOP)),
             "B": V((RF.CAB_TABLE[0] - 0.16, -10.90, RF.CAB_TOP))}
SIP_SIDE = {"A": "L", "B": "R"}
CAFE_UP = {"A": (7.30, -9.00), "B": (8.60, -9.00)}  # where each stands up to, beside their café chair
# Over to the Rovers once the dinner party has gone in: past the café, along the
# balcony, in at the front door, along the floor behind the booth stools: she
# to the back of her stool, he up the gap between the two tables to the end of
# the cushion (he sits there and slides along).
TO_ROVERS = {"A": [(7.32, -8.40), (7.32, -7.62), (6.20, -7.75), (0.40, -7.75), (-0.65, -9.30), (-0.65, -11.10),
                   (0.30, -12.40), (1.60, -12.40)],
             "B": [(8.58, -8.40), (8.58, -7.62), (7.32, -7.62), (6.20, -7.75), (0.40, -7.75), (-0.65, -9.30),
                   (-0.65, -11.10), (0.30, -12.40), (1.52, -12.40), (1.52, -11.40)]}


def cab_side(who):
    """Where each stands to sit down (and stands up to)."""
    return RF.CAB_STAND[who]


def cab_root(who):
    x, y, _yaw = RF.CAB_SEATS[who]
    return V((x, y, CAB_Z[who]))


def bouquet_down():
    """Where the café lady sets his bouquet: lying on their table."""
    return ("spot", BOUQUET_SPOT + V((0, 0, 0.03)), DF.qmul(DF.qyaw(30.0), _qy(88.0)))


class Patron:
    """One of the café couple: seated at the café until the dinner party have
    gone into the Rovers, then over to their table in front of the stage (the
    lounge loop: there all clip long)."""
    stay, walk, turn, face = DF.Staff.stay, DF.Staff.walk, DF.Staff.turn, DF.Staff.face

    def __init__(self, who, loop, where="cafe"):
        self.who = who
        f = Figure(TAGS[who], COUPLE_LOOK[who], loop=loop)
        f.twist = Keys()
        f.bow = Keys()
        self.f = f
        self.speed = DF.GUEST_SPEED
        self.hold = {"L": None, "R": None}
        self.where = where
        if where == "cafe":
            x, y = SEAT[who]
            self.root = V((x, y - 0.05, Z_SEATED))
            self.yaw = 0.0
            self.cafe = (0.0, loop)                   # seated at the café
            self.rovers = None                        # seated in the Rovers
        else:
            self.root = cab_root(who)
            self.yaw = RF.CAB_YAW[who]
            self.cafe = None
            self.rovers = (0.0, loop)
        self.x, self.y = self.root.x, self.root.y
        f.put(0.0, self.x, self.y, self.yaw)
        f.zk.add(0.0, self.root.z)
        feet = FEET if where == "cafe" else CAB_FEET[who]
        f.fL.add(0.0, V(feet[0]))
        f.fR.add(0.0, V(feet[1]))
        f.L.add(0.0, self.rest("L"))
        f.R.add(0.0, self.rest("R"))
        f.vis.add(0.0, 1.0)
        self.busy = []
        self.tasks = []
        self.served = []                          # (t0, t1, server xy): someone at their place
        self.wine = None                          # (t from, glass) their glass of wine on the Rovers table

    def rest(self, side):
        return (REST if self.where == "cafe" else LAPH)[side].copy()

    def head(self, t, lean=3, pitch=3, yaw=0):
        self.f.lean.add(t, lean)
        self.f.pitch.add(t, pitch)
        self.f.yaw.add(t, yaw)

    def hands(self, t):
        self.f.L.add(t, DF.HAND_REST["L"].copy())
        self.f.R.add(t, DF.HAND_REST["R"].copy())

    def loc(self, w, where=None):
        """World -> their seated frame (where: "cafe"/"rovers", else the seat they are in now)."""
        if where == "cafe":
            x, y = SEAT[self.who]
            root, yaw = V((x, y - 0.05, Z_SEATED)), 0.0
        elif where == "rovers":
            root, yaw = cab_root(self.who), RF.CAB_YAW[self.who]
        else:
            root, yaw = self.root, self.yaw
        d = V((w[0] - root.x, w[1] - root.y))
        a = math.radians(-yaw)
        return V((d.x * math.cos(a) - d.y * math.sin(a), d.x * math.sin(a) + d.y * math.cos(a), w[2] - root.z))

    def free(self, t0, t1):
        return all(t1 <= a or t0 >= b for a, b in self.busy)

    def seated_at(self, t):
        if self.cafe and self.cafe[0] <= t < self.cafe[1]:
            return "cafe"
        if self.rovers and self.rovers[0] <= t < self.rovers[1]:
            return "rovers"
        return None

    def to_rovers(self, t):
        """Up from the café chair, across to the Rovers, down into their chair
        at the table in front of the stage. Returns when seated."""
        f = self.f
        t0 = t
        self.cafe = (self.cafe[0], t)
        sx, sy = CAFE_UP[self.who]
        f.put(t, self.root.x, self.root.y, self.yaw)
        f.zk.add(t, self.root.z)
        f.fL.add(t, V(FEET[0]))
        f.fR.add(t, V(FEET[1]))
        f.L.hold(t).add(t + 0.7, V((-0.22, 0.02, 1.02)))
        f.R.hold(t).add(t + 0.7, V((0.22, 0.02, 1.02)))
        f.lean.hold(t).add(t + 0.7, 20).add(t + 1.6, 3)
        t1 = t + 1.6
        f.put(t1, sx, sy, self.yaw)
        f.zk.add(t1, floor_z(sx, sy))
        f.fL.add(t1, V(RF.STAND_FEET[0]))
        f.fR.add(t1, V(RF.STAND_FEET[1]))
        self.x, self.y = sx, sy
        self.where = "walk"
        t = self.walk(t1 + 0.2, [(sx, sy)] + TO_ROVERS[self.who] + [cab_side(self.who)])
        yaw = RF.CAB_YAW[self.who]
        t = self.turn(t, yaw)
        # Down onto the stool (her) or onto the end of the cushion and along it
        # to his place (him), as the regulars do.
        root = cab_root(self.who)
        feet = CAB_FEET[self.who]
        f.put(t, self.x, self.y, yaw)
        f.zk.add(t, floor_z(self.x, self.y))
        f.fL.add(t, V(RF.STAND_FEET[0]))
        f.fR.add(t, V(RF.STAND_FEET[1]))
        f.L.hold(t)
        f.R.hold(t)
        f.lean.add(t, 3).add(t + 0.6, 24)
        t1 = t + 1.2
        sx, sy = RF.CAB_SLIDE.get(self.who, (root.x, root.y))
        f.put(t1, sx, sy, yaw)
        f.zk.add(t1, root.z)
        f.fL.add(t1, V(feet[0]))
        f.fR.add(t1, V(feet[1]))
        if self.who in RF.CAB_SLIDE:
            t1 += 1.0
            f.put(t1, root.x, root.y, yaw)
            f.zk.add(t1, root.z)
        f.lean.add(t1 + 0.4, 6)
        self.root, self.yaw = root, RF.CAB_YAW[self.who]
        self.x, self.y = root.x, root.y
        self.where = "rovers"
        f.L.add(t1 + 0.4, self.rest("L"))
        f.R.add(t1 + 0.4, self.rest("R"))
        self.rovers = (t1 + 0.4, DF.LOOP)
        self.tasks.append((t0, t1 + 0.4, "to the rovers"))
        self.walked = (t0, t1 + 0.4)
        return t1 + 0.4

    def sip(self, t, cup, spot=None, grip=CUP_GRIP, tilt=38, mouth=None):
        """Cup (or glass) up off the table, a sip, down again (at the café with
        the right hand; in the Rovers with the hand on the glass's side)."""
        f = self.f
        where = self.seated_at(t) or "rovers"
        side = "R" if where == "cafe" else SIP_SIDE[self.who]
        keys = f.R if side == "R" else f.L
        sx = 1.0 if side == "R" else -1.0
        spot = spot if spot is not None else CUP[self.who]
        g = self.loc(spot, where) + V((-0.02 * sx, -0.06, grip - 0.01))
        keys.hold(t)
        tc = t + 0.9
        ct = DF.CT(g, f.tag, side, tc, DF.palm_for("glass", spot, grip))
        DF.CONTACTS.append(ct)
        keys.add(tc, ct)
        cup.at(tc, ("hand", f.tag, side, "glass"))
        mo = (mouth or MOUTH).copy()
        mo.x *= sx
        keys.add(tc + 0.9, mo).add(tc + 2.1, mo.copy())
        cup.tilt.add(tc + 0.7, 0).add(tc + 1.2, tilt).add(tc + 1.8, tilt).add(tc + 2.3, 0)
        ct2 = DF.CT(g, f.tag, side, tc + 3.0, DF.palm_for("glass", spot, grip))
        DF.CONTACTS.append(ct2)
        keys.add(tc + 3.0, ct2)
        cup.at(tc + 3.0, ("spot", spot.copy(), 0.0 if where == "cafe" else RF.CAB_YAW[self.who]))
        keys.add(tc + 3.7, (REST if where == "cafe" else LAPH)[side].copy())
        self.busy.append((t, tc + 3.8))
        return tc + 3.8

    def clap(self, t, n=8):
        f = self.f
        f.L.hold(t).add(t + 0.5, CLAP[0] + V((-0.06, 0, 0)))
        f.R.hold(t).add(t + 0.5, CLAP[1] + V((0.06, 0, 0)))
        tt = t + 0.5
        for q in range(n):
            f.L.add(tt + 0.12, CLAP[0]).add(tt + 0.26, CLAP[0] + V((-0.06, 0, 0)))
            f.R.add(tt + 0.12, CLAP[1]).add(tt + 0.26, CLAP[1] + V((0.06, 0, 0)))
            tt += 0.28
        f.L.add(tt + 0.6, self.rest("L"))
        f.R.add(tt + 0.6, self.rest("R"))
        self.busy.append((t, tt + 0.7))
        return tt + 0.7





# --- The mime -----------------------------------------------------------------
# He is never idle: an act at one place after another, riding his unicycle
# between them (juggling as he rides). Every act keys his figure and writes its
# props into m.pt (prop name -> [(t, state, blend frames)]); _prop_tracks turns
# the states into per-frame transforms from his solved palms.
HR = {"L": V((-0.17, 0.06, 0.87)), "R": V((0.17, 0.06, 0.87))}
CARRY = {"L": V((-0.19, 0.24, 0.98)), "R": V((0.19, 0.24, 0.98))}
OTHER = {"L": "R", "R": "L"}

# Where he plays: the stage, the way he faces, the turns that play to either
# side of the crowd, and how long a flash may hang (the dining room is low).
TUB_STAGE = RF.MIME_TUB                             # north of the hot tub, facing the bathers
PUB_STAGE = RF.MIME_PUB                             # on the Rovers' stage
DINING_STAGE = (8.80, 8.35)                        # the head of the dinner table
VENUES = {
    "cafe": dict(xy=STAGE, face=180.0, sides=(30.0, -30.0), flash=1.15),
    # (on the stage under the Rovers' 3.2 m ceiling: lower flashes, quicker high throws)
    "pub": dict(xy=PUB_STAGE, face=RF.MIME_PUB_FACE, sides=(32.0, -32.0), flash=0.88, hb=0.86),
    "tub": dict(xy=TUB_STAGE, face=180.0, sides=(28.0, -28.0), flash=1.10),
    "dining": dict(xy=DINING_STAGE, face=180.0, sides=(35.0, -35.0), flash=0.90),
}
CAFE_TO_DINING = [(8.80, -5.30), (7.05, -5.00), (7.05, -3.85), (7.05, -3.55), (7.05, 3.70), (7.25, 4.55),
                  (7.25, 7.95), (7.95, 8.35)]
WALKABOUT = [STAGE, (8.85, -6.55), (8.55, -7.55), (9.20, -8.85), (10.40, -8.40), (10.45, -6.40), STAGE]
LEG_WAIT = {}                                      # walking and riding legs the planners hold back (name -> s)

# His quiver: a leather tube on his left hip with the three clubs and the three
# torches standing in it, handles up (his local frame: the mouth of it).
QUIVER = V((-0.30, -0.05, 1.00))
STORED = {}
for _i, _a in enumerate((90.0, 210.0, 330.0)):
    _r = math.radians(_a)
    STORED[f"Club{_i}"] = QUIVER + V((0.030 * math.cos(_r), 0.030 * math.sin(_r), 0.09))
    _r = math.radians(_a + 60.0)
    STORED[f"Torch{_i}"] = QUIVER + V((0.034 * math.cos(_r), 0.034 * math.sin(_r), 0.08))

# Juggling: hand stations (his local frame) per prop kind; how a club or torch
# sits in the hand (handle at the palm, tilted forward; a second one in the
# same hand lies flatter beside it) and where its centre of mass is.
JUG = {"ball": ({"L": V((-0.07, 0.32, 1.04)), "R": V((0.07, 0.32, 1.04))},
                {"L": V((-0.21, 0.30, 1.12)), "R": V((0.21, 0.30, 1.12))}),
       "club": ({"L": V((-0.09, 0.30, 0.99)), "R": V((0.09, 0.30, 0.99))},
                {"L": V((-0.24, 0.27, 1.06)), "R": V((0.24, 0.27, 1.06))})}
JUG["torch"] = JUG["club"]
BALLISH = ("ball", "glow")                         # kinds thrown and held like balls
POCKET = {"L": V((-0.20, 0.10, 0.95)), "R": V((0.20, 0.10, 0.95))}
NAMES = {"ball": ("Ball0", "Ball1", "Ball2"), "club": ("Club0", "Club1", "Club2"),
         "torch": ("Torch0", "Torch1", "Torch2")}
COM = {"ball": np.zeros(3), "club": np.array((0.0, 0.0, 0.22)), "torch": np.array((0.0, 0.0, 0.20)),
       "knife": np.array((0.0, 0.0, 0.07))}
Q_ID = np.array((1.0, 0.0, 0.0, 0.0))
Q_HELD = (DF.qx(-50.0), DF.qx(-78.0))
Q_STORED = DF.qx(180.0)                            # handle up, in the quiver
TORCH_HEAD = 0.35
BALL_R = 0.034
MAGIC = ("MBall", "ZBall", "Fan", "Bouquet") + tuple(f"Silk{i}" for i in range(6)) + tuple(f"Card{i}" for i in range(8))
# The finale's props, set out on the stage for him (rest poses below): three
# knives standing in the block on his prop table, a second rola bola leaning on
# the drapes, the bubble wands in the bucket, the bubbles, the fireball, the
# spotlight's beam and the bone that drives the house lights (the client reads
# DinCafeProps_Show: its scale is how far down the lights are, its position
# where the spotlight hangs).
NAMES["knife"] = ("Knife0", "Knife1", "Knife2")
JUG["knife"] = JUG["club"]
BUBBLES = tuple(f"Bubble{i}" for i in range(24))
GIANTS = ("Giant0", "Giant1", "Giant2")
STAGE_PROPS = NAMES["knife"] + ("Rola2Board", "Rola2Tube", "WandL", "WandR", "WandS", "FireBall") + GIANTS + BUBBLES
DYNAMIC = ("Quiver",) + NAMES["ball"] + NAMES["club"] + NAMES["torch"] + MAGIC + ("RolaBoard", "RolaTube") + \
    STAGE_PROPS + ("Beam", "Show")


def held(kind, side, slot):
    """(offset from the palm in his body frame, orientation in his body frame)."""
    if kind == "card":
        return np.array((0.0, 0.0, 0.03)), Q_ID
    if kind in ("ball", "glow"):
        return np.array((0.0, 0.0, BALL_R + 0.004 + 0.065 * slot)), Q_ID
    s = 1.0 if side == "R" else -1.0
    off = np.zeros(3) if slot == 0 else np.array((s * 0.025, -0.03, -0.035))
    return off, Q_HELD[slot]


def hand_state(kind, side, slot):
    off, q = held(kind, side, slot)
    return ("hand", side, off, q)


STAGE_CLEAR = 0.18                                 # his root never nearer the trunk or the drapes than this


def stage_clear(xy):
    """A spot on the stage moved clear of the trunk (west or south of it,
    whichever is nearer: it stands in the back corner by the lobby wall) and of
    the drapes at the back and sides."""
    x, y = xy
    xs = [p[0] for p in RF.STAGE_POLY]
    x = min(max(x, min(xs) + STAGE_CLEAR), max(xs) - STAGE_CLEAR)
    y = min(y, max(p[1] for p in RF.STAGE_POLY) - STAGE_CLEAR)
    tx, ty = RF.TRUNK
    hx, hy = RF.TRUNK_SIZE[0] / 2 + STAGE_CLEAR, RF.TRUNK_SIZE[1] / 2 + STAGE_CLEAR
    if abs(x - tx) < hx and abs(y - ty) < hy:
        if x - (tx - hx) < y - (ty - hy):
            x = tx - hx
        else:
            y = ty - hy
    return (x, y)


def trunk_corner(a, b):
    """The corner of the trunk's keep-out (stage_clear) to go round on the way
    from a to b on the stage, or None when the straight way is clear."""
    tx, ty = RF.TRUNK
    hx, hy = RF.TRUNK_SIZE[0] / 2 + STAGE_CLEAR, RF.TRUNK_SIZE[1] / 2 + STAGE_CLEAR
    for k in range(1, 20):
        u = k / 20
        x, y = a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u
        if abs(x - tx) < hx - 0.01 and abs(y - ty) < hy - 0.01:
            return (tx - hx, ty - hy)
    return None


class Mime(DF.Staff):
    def __init__(self, loop, start=None):
        x, y, yaw = start or (STAGE[0], STAGE[1], 180.0)
        super().__init__(TAGS["M"], MIME_LOOK, (x, y, yaw), speed=1.05, z=floor_z(x, y))
        self.f.loop = loop
        self.pt = {}
        self.sc = {}
        self.lit = {i: Keys().add(0.0, 0.0) for i in range(3)}
        self.fire = Keys().add(0.0, 0.0)            # the flame on his fingertip
        self.silk_out = Keys().add(0.0, 0.0)
        self.uni = []
        self.audience = []                        # (t0, t1, venue, what): who should be watching him
        self.bows = []                            # (t, venue)
        self.acts = []                            # (t0, t1, name, venue)
        self.legs = []                            # (t0, t1, leg name)
        self.late = []                            # (venue, s) an act started after its mark
        self.overrun = 0.0
        self.holding = {"ball": {}, "club": {}, "torch": {}}
        self._store = {n: Keys().add(0.0, STORED[n].copy()) for n in STORED}
        self.prop("Quiver", 0.0, ("local", Keys().add(0.0, QUIVER.copy()), Q_ID), 0)
        for name in DYNAMIC[1:]:
            st = self.stored(name) if name in STORED else rola_rest(name) if name.startswith("Rola") else \
                stage_rest(name) if name in STAGE_REST else ("hide",)
            self.prop(name, 0.0, st, 0)
        self.dim = Keys().add(0.0, 0.001)            # house lights: 0.001 up .. 1 down (the Show bone's scale x)
        self.beam = Keys().add(0.0, 0.0)             # the spotlight's beam: 0 off .. 1 on
        self.spot = Keys().add(0.0, 1.0)             # the spotlight's light on him: 0 .. 1 (scale y, times dim)
        self.black = Keys().add(0.0, 0.0)            # blackout: the rest of the room right down, 0 .. 1 (scale z)
        self.spot_free = Keys().add(0.0, 0.0)        # 0: the spot on him .. 1: on spot_at (world xy) instead
        self.spot_at = Keys().add(0.0, V((RF.MIME_PUB[0], RF.MIME_PUB[1], 0.0)))
        self.uni_at = {}                          # venue -> (where he stood, his yaw, the pose it lies in)

    def stored(self, name):
        return ("local", self._store[name], Q_STORED)

    def hand_target(self, side):
        h = self.hold[side]
        if h == "glass":
            return DF.FLUTE_STAND.copy()
        if h == "uni":
            return UNI_HAND.copy()
        if h:
            return CARRY[side].copy()
        return HR[side].copy()

    def prop(self, name, t, state, blend=4):
        self.pt.setdefault(name, []).append((t, state, blend))

    def scale(self, name, t0, v0, t1, v1):
        self.sc.setdefault(name, Keys().add(0.0, 1.0)).add(t0, v0).add(t1, v1)

    def leg(self, t, pts, name, juggle=False):
        """A walk the planner may hold back at its start (LEG_WAIT[name])."""
        t0 = t
        t += LEG_WAIT.setdefault(name, 0.0)
        self.stay(t)
        t = juggle_walk(self, t, pts) if juggle else self.walk(t, pts)
        self.legs.append((t0, t, name))
        return t

    # -- basic moves -----------------------------------------------------------
    def bow(self, t, deep=40, venue=None, hat=True):
        """A hat tip and a deep bow."""
        f = self.f
        if hat:
            f.R.hold(t).add(t + 1.1, V((0.08, 0.12, 1.92))).add(t + 2.0, V((0.40, 0.34, 1.25)))
            f.L.hold(t).add(t + 1.2, V((-0.08, 0.10, 1.00)))
            f.R.add(t + 3.6, V((0.40, 0.34, 1.25))).add(t + 4.6, self.hand_target("R"))
            f.L.add(t + 4.6, self.hand_target("L"))
        f.lean.hold(t).add(t + 1.4, 3).add(t + 2.4, deep).add(t + 3.6, deep).add(t + 4.6, 3)
        f.pitch.hold(t).add(t + 2.4, 20).add(t + 4.6, 3)
        self.bows.append((t + 2.4, venue))
        return t + 4.8

    def look_at(self, t, xy, dur=0.5):
        rel = ((heading((self.x, self.y), xy) - self.yaw) + 180) % 360 - 180
        self.f.yaw.add(t + dur, max(-70.0, min(70.0, rel)))

    def slide(self, t, xy, dur, yaw=None):
        """Root glides to xy over dur (no turn into it). On the stage: kept
        clear of the trunk and the drapes (stage_clear)."""
        f = self.f
        if RF.on_stage(self.x, self.y) and RF.on_stage(*xy):
            xy = stage_clear(xy)
            c = trunk_corner((self.x, self.y), xy)
            if c is not None:                        # (round the trunk's corner, not through it)
                a_ = (V(c) - V((self.x, self.y))).length
                b_ = (V(xy) - V(c)).length
                t = self.slide(t, c, dur * a_ / max(1e-6, a_ + b_))
                dur = dur * b_ / max(1e-6, a_ + b_)
        f.put(t, self.x, self.y, self.yaw)
        y = self.yaw if yaw is None else yaw
        f.put(t + dur, xy[0], xy[1], y)
        f.zk.add(t, floor_z(self.x, self.y)).add(t + dur, floor_z(*xy))
        self.x, self.y, self.yaw = xy[0], xy[1], f._yaw
        return t + dur

    def to_stage(self, t, spot=STAGE, face=180.0):
        t = self.walk(t, [(self.x, self.y), spot])
        return self.turn(t, face) if isinstance(face, (int, float)) else self.face(t, face)

    def draw(self, t, side, name, kind, slot):
        """One out of the quiver on his left hip, by the handle (the right hand
        reaches across, the body turned into it)."""
        f = self.f
        keys = f.L if side == "L" else f.R
        DF.hold_live(keys, t)
        at = STORED[name] + V((0.03 if side == "R" else 0.0, 0.03, 0.03))
        keys.add(t + 0.55, at)
        f.pitch.hold(t).add(t + 0.55, 16)
        if side == "R":
            f.twist.hold(t).add(t + 0.45, 24)
        self.prop(name, t + 0.6, hand_state(kind, side, slot), 6)
        self.holding[kind][NAMES[kind].index(name)] = (side, slot)
        self.hold[side] = kind
        keys.add(t + 1.15, CARRY[side].copy())
        f.pitch.add(t + 1.15, 4)
        if side == "R":
            f.twist.add(t + 1.15, 0.0)
        return t + 1.2

    def sheath(self, t, side, name, kind):
        """One back into the quiver."""
        f = self.f
        keys = f.L if side == "L" else f.R
        DF.hold_live(keys, t)
        keys.add(t + 0.55, STORED[name] + V((0.03 if side == "R" else 0.0, 0.03, 0.03)))
        f.pitch.hold(t).add(t + 0.55, 16)
        if side == "R":
            f.twist.hold(t).add(t + 0.45, 24)
        self.prop(name, t + 0.6, self.stored(name), 6)
        del self.holding[kind][NAMES[kind].index(name)]
        if not any(s == side for s, _sl in self.holding[kind].values()):
            self.hold[side] = None
        keys.add(t + 1.15, self.hand_target(side))
        f.pitch.add(t + 1.15, 4)
        if side == "R":
            f.twist.add(t + 1.15, 0.0)
        return t + 1.2

    def appear_balls(self, t):
        """Three balls out of his pockets (two in the right hand, one in the left)."""
        f = self.f
        f.L.hold(t).add(t + 0.8, POCKET["L"]).add(t + 1.6, JUG["ball"][1]["L"])
        f.R.hold(t).add(t + 0.8, POCKET["R"]).add(t + 1.6, JUG["ball"][0]["R"])
        for i, (side, slot) in enumerate((("R", 0), ("L", 0), ("R", 1))):
            self.prop(NAMES["ball"][i], t + 0.8, hand_state("ball", side, slot), 0)
            self.holding["ball"][i] = (side, slot)
        return t + 1.8

    def vanish_balls(self, t):
        f = self.f
        f.L.hold(t).add(t + 0.8, POCKET["L"]).add(t + 1.6, HR["L"])
        f.R.hold(t).add(t + 0.8, POCKET["R"]).add(t + 1.6, HR["R"])
        for i in range(3):
            self.prop(NAMES["ball"][i], t + 0.85, ("hide",), 0)
        self.holding["ball"] = {}
        for side in "LR":
            if self.hold[side] == "ball":
                self.hold[side] = None
        return t + 1.7


# --- Juggling ----------------------------------------------------------------------
def cascade(m, kind, t0, n, b, d=None, style="plain", spins=1):
    """n throws of a three-object cascade from t0 at beat b (dwell d), starting
    from the hand holding two. Returns the end time (last catch made)."""
    f = m.f
    IN, OUT = JUG[kind]
    d = d if d is not None else (0.14 if kind in BALLISH else 0.19)
    H = m.holding[kind]
    S = "R" if sum(1 for v in H.values() if v[0] == "R") == 2 else "L"
    O = OTHER[S]
    two = sorted([i for i, v in H.items() if v[0] == S], key=lambda i: H[i][1])
    one = [i for i, v in H.items() if v[0] == O]
    obj = []
    for k in range(n):
        o = (two[0], one[0], two[1])[k] if k < 3 else obj[k - 3]
        obj.append(o)
        side = S if k % 2 == 0 else O
        tt = t0 + k * b
        tc = tt + 3 * b - d
        m.prop(NAMES[kind][o], tt, ("fly", side, tt, OTHER[side], tc, kind, spins if kind not in BALLISH else 0), 0)
        m.prop(NAMES[kind][o], tc, hand_state(kind, OTHER[side], 0), 0)
    lift = V((0, 0, 0.04)) if style == "high" else V()
    for side, first in ((S, 0), (O, 1)):
        keys = f.L if side == "L" else f.R
        DF.hold_live(keys, t0 - 0.35)
        k = first
        while k < n + 3:
            tt = t0 + k * b
            if k < n:
                if k > 0:                          # (the first throw has nothing to catch first)
                    keys.add(tt - d, OUT[side] + lift)
                keys.add(tt, IN[side].copy())
            elif k >= 3:
                keys.add(tt - d, OUT[side] + V((0, 0, -0.02)))
            k += 2
    # Who holds what now: the hand catching two keeps the later one as its second.
    m.holding[kind] = {}
    for k in range(max(0, n - 3), n):
        side = OTHER[S if k % 2 == 0 else O]
        slot = 1 if any(s == side for s, _sl in m.holding[kind].values()) else 0
        m.holding[kind][obj[k]] = (side, slot)
        if slot:
            m.prop(NAMES[kind][obj[k]], t0 + k * b + 3 * b - d, hand_state(kind, side, 1), 0)
    for side in "LR":
        m.hold[side] = kind if any(s == side for s, _sl in m.holding[kind].values()) else None
    return t0 + (n + 2) * b


def flash(m, kind, t0, T=1.15, b=0.22, spins=2, pirouette=True):
    """All three thrown high in quick succession, a pirouette under them, and
    caught again (the hand that threw two ends up holding one)."""
    f = m.f
    IN, OUT = JUG[kind]
    H = m.holding[kind]
    S = "R" if sum(1 for v in H.values() if v[0] == "R") == 2 else "L"
    O = OTHER[S]
    two = sorted([i for i, v in H.items() if v[0] == S], key=lambda i: H[i][1])
    one = [i for i, v in H.items() if v[0] == O]
    order = [(two[0], S), (one[0], O), (two[1], S)]
    new = {}
    for k, (o, side) in enumerate(order):
        tt = t0 + k * b
        tc = tt + T
        m.prop(NAMES[kind][o], tt, ("fly", side, tt, OTHER[side], tc, kind, spins if kind not in BALLISH else 0), 0)
        to = OTHER[side]
        slot = 1 if any(s == to for s, _sl in new.values()) else 0
        new[o] = (to, slot)
        m.prop(NAMES[kind][o], tc, hand_state(kind, to, slot), 0)
    up = V((0, 0.02, 0.10))
    for side, throws in ((S, (0, 2)), (O, (1,))):
        keys = f.L if side == "L" else f.R
        DF.hold_live(keys, t0 - 0.35)
        for k in throws:
            if k:
                keys.add(t0 + k * b - 0.22, OUT[side] + V((0, 0, -0.04)))
            keys.add(t0 + k * b, IN[side] + up)
        keys.add(t0 + 2 * b + 0.25, OUT[side] + V((0, 0, 0.18)))        # arms up, open, while they fly
    t_spin0, t_spin1 = t0 + 2 * b + 0.10, t0 + T - 0.05
    if pirouette and t_spin1 - t_spin0 >= 0.45:      # (no time to turn under a low flash)                                  # (straight onto the root track: put() unwraps turns)
        f.put(t_spin0, m.x, m.y, m.yaw, lin=True)
        f.root.add(0.5 * (t_spin0 + t_spin1), V((m.x, m.y, m.yaw + 180.0)), True)
        f.root.add(t_spin1, V((m.x, m.y, m.yaw + 360.0)))
        f._yaw = m.yaw = m.yaw + 360.0
    for k, (o, side) in enumerate(order):
        to = OTHER[side]
        keys = f.L if to == "L" else f.R
        keys.add(t0 + k * b + T - 0.02, OUT[to] + V((0, 0, -0.02)))
    m.holding[kind] = new
    for side in "LR":
        m.hold[side] = kind if any(s == side for s, _sl in new.values()) else None
    t1 = t0 + 2 * b + T + 0.3
    for side in "LR":
        keys = f.L if side == "L" else f.R
        keys.add(t1, CARRY[side].copy() if kind not in BALLISH else OUT[side].copy())
    return t1


def juggle_walk(m, t, pts):
    """Walk the way juggling three balls out of the pockets the whole time."""
    t0 = t
    t1 = m.walk(t, pts)
    if t1 - t0 < 6.0:
        return t1
    f = m.f
    ta = m.appear_balls(t0 + 0.4)
    n = int((t1 - 2.4 - ta) / 0.32) - 2
    if n < 6:
        return t1
    te = cascade(m, "ball", ta + 0.2, n, 0.32)
    m.vanish_balls(te)
    f.pitch.add(ta, 10).add(te, 10).add(te + 1.6, 3)
    return max(t1, te + 1.8)


def fill(m, kind, t, t_to, b=0.34):
    """Keep the cascade going until t_to (when there is room for one)."""
    n = int((t_to - t - 0.4) / b) - 2
    if n >= 6:
        return cascade(m, kind, t + 0.4, n, b)
    return max(t, t_to)


def draw3(m, t, kind):
    """All three out of the quiver: one in the left hand, two in the right."""
    f = m.f
    names = NAMES[kind]
    t = m.draw(t, "L", names[1], kind, 0)
    f.L.add(t + 0.4, V((-0.34, 0.28, 1.14)))               # out of the way of the right hand
    t = m.draw(t + 0.1, "R", names[0], kind, 0)
    t = m.draw(t, "R", names[2], kind, 1)
    f.L.add(t + 0.4, CARRY["L"].copy())
    return t + 0.5


def sheath3(m, t, kind):
    """Back into the quiver, the right hand's first."""
    for side in ("R", "L"):
        for i, (s, slot) in sorted(m.holding[kind].items(), key=lambda kv: -kv[1][1]):
            if s == side:
                t = m.sheath(t, side, NAMES[kind][i], kind)
    return t


def _stage(m, t, venue):
    v = VENUES[venue]
    if (V(v["xy"]) - V((m.x, m.y))).length > 0.05:
        t = m.walk(t, [(m.x, m.y), v["xy"]])
    return m.turn(t, v["face"])


def _side(m, t, venue, k):
    """Turn to play to one side of the crowd (k 0 or 1), or back to the front."""
    v = VENUES[venue]
    return m.turn(t, v["face"] + (v["sides"][k] if k is not None else 0.0), 0.6)


# --- The acts -----------------------------------------------------------------------
# Each takes the venue and when its last bow must end (t_end; None: its own
# length) and pads or trims its middle to land there.
def act_clubs(m, t, venue, t_end=None):
    """Three clubs out of the quiver: a slow high cascade, fast, a flash with a
    pirouette, a run to each side of the crowd, high again, back in the
    quiver, a bow."""
    f = m.f
    t0 = t
    t = _stage(m, t, venue)
    t_end = t + 92.0 if t_end is None else t_end
    T = VENUES[venue]["flash"]
    hb = VENUES[venue].get("hb", 1.0)
    FIN = 16.5
    t = draw3(m, t, "club")
    t = m.bow(t, 18, venue, hat=False)
    f.pitch.add(t + 0.5, 12)
    t = cascade(m, "club", t + 0.8, 18, 0.42 * hb, 0.22, style="high") + 0.6
    t = cascade(m, "club", t, 32, 0.34) + 0.4
    t = flash(m, "club", t + 0.4, T=T) + 0.6
    for k in (0, 1):
        if t + 17.0 + FIN > t_end:
            break
        t = _side(m, t, venue, k)
        t = cascade(m, "club", t + 0.4, 30, 0.35) + 0.4
        t = flash(m, "club", t + 0.4, T=T) + 0.4
    t = _side(m, t, venue, None)
    t = fill(m, "club", t, t_end - FIN)
    t = cascade(m, "club", t + 0.4, 14, 0.44 * hb, 0.24, style="high") + 0.6
    f.pitch.add(t, 3)
    t = sheath3(m, t, "club")
    t = m.bow(t, 45, venue)
    m.audience.append((t0, t, venue, None))
    m.acts.append((t0, t, "clubs", venue))
    return t


def light_torches(m, t):
    """The first torch out and held up; a snap of his fingers lights a flame
    on his fingertip, which lights it; the other two out and lit from it."""
    f = m.f
    t = m.draw(t, "L", "Torch1", "torch", 0)
    up = V((-0.10, 0.34, 1.22))
    f.L.add(t + 0.6, up)
    f.R.add(t + 0.6, V((0.18, 0.30, 1.38)))
    f.pitch.add(t + 0.6, 8)
    f.R.add(t + 0.85, V((0.16, 0.33, 1.42))).add(t + 1.0, V((0.17, 0.31, 1.39)))     # the snap
    m.fire.add(t + 0.95, 0.0).add(t + 1.15, 1.0)
    head = up + V((0.0, 0.27, 0.22))
    f.R.add(t + 1.9, head + V((0.05, -0.08, -0.05))).add(t + 2.5, head + V((0.05, -0.08, -0.05)))
    m.lit[1].add(t + 2.0, 0.0).add(t + 2.5, 1.0)
    f.R.add(t + 3.0, V((0.10, 0.22, 1.50)))                 # blows the fingertip out
    m.fire.add(t + 2.9, 1.0).add(t + 3.15, 0.0)
    f.pitch.add(t + 2.6, 8).add(t + 3.0, -4).add(t + 3.4, 6)
    f.R.add(t + 3.6, HR["R"].copy())
    t += 3.7
    t = m.draw(t, "R", "Torch0", "torch", 0)
    t = m.draw(t, "R", "Torch2", "torch", 1)
    f.R.add(t + 0.9, up + V((0.12, 0.0, -0.02))).add(t + 1.8, up + V((0.12, 0.0, -0.02)))   # heads together
    m.lit[0].add(t + 1.0, 0.0).add(t + 1.5, 1.0)
    m.lit[2].add(t + 1.1, 0.0).add(t + 1.6, 1.0)
    f.R.add(t + 2.4, CARRY["R"].copy())
    f.L.add(t + 2.4, CARRY["L"].copy())
    f.pitch.add(t + 2.4, 4)
    return t + 2.5


def blow_out(m, t):
    """Each hand's torches held up in front in turn, a puff each."""
    f = m.f
    for side in ("L", "R"):
        keys = f.L if side == "L" else f.R
        sx = -1 if side == "L" else 1
        keys.add(t + 0.7, V((sx * 0.08, 0.36, 1.30)))
        f.pitch.add(t + 0.7, 8).add(t + 1.3, 14).add(t + 2.0, 6)
        f.lean.add(t + 0.7, 4).add(t + 1.3, 12).add(t + 2.0, 4)
        for i, (s, _sl) in m.holding["torch"].items():
            if s == side:
                m.lit[i].add(t + 1.2, 1.0).add(t + 1.8, 0.0)
        keys.add(t + 2.4, CARRY[side].copy())
        t += 2.6
    f.pitch.add(t, 3)
    return t


def act_torches(m, t, venue, t_end=None):
    """Fire: three torches out of the quiver and lit, juggled high and fast,
    flashes with a pirouette, a run to each side of the crowd, blown out, back
    in the quiver, a bow."""
    f = m.f
    t0 = t
    t = _stage(m, t, venue)
    t_end = t + 95.0 if t_end is None else t_end
    T = VENUES[venue]["flash"]
    hb = VENUES[venue].get("hb", 1.0)
    FIN = 21.7
    t = light_torches(m, t)
    t = m.bow(t, 15, venue, hat=False)
    f.pitch.add(t + 0.5, 14)
    t = cascade(m, "torch", t + 0.8, 16, 0.44 * hb, 0.24, style="high") + 0.6
    t = cascade(m, "torch", t, 30, 0.36) + 0.4
    t = flash(m, "torch", t + 0.4, T=T) + 0.6
    for k in (0, 1):
        if t + 13.5 + FIN > t_end:
            break
        t = _side(m, t, venue, k)
        t = cascade(m, "torch", t + 0.4, 24, 0.36) + 0.4
        t = flash(m, "torch", t + 0.4, T=T) + 0.4
    t = _side(m, t, venue, None)
    t = fill(m, "torch", t, t_end - FIN, 0.36)
    t = cascade(m, "torch", t + 0.4, 14, 0.44 * hb, 0.24, style="high") + 0.6
    t = blow_out(m, t)
    t = sheath3(m, t, "torch")
    t = m.bow(t, 45, venue)
    m.audience.append((t0, t, venue, None))
    m.acts.append((t0, t, "torches", venue))
    return t


def act_balls(m, t, venue, t_end=None):
    """Balls on the spot: high and slow, fast, flashes, a run to each side."""
    f = m.f
    t0 = t
    t = _stage(m, t, venue)
    t_end = t + 80.0 if t_end is None else t_end
    FIN = 0.4 + 26 * 0.42 + 0.4 + 1.7 + 4.8
    hb = VENUES[venue].get("hb", 1.0)
    t = m.bow(t, 22, venue)
    t = m.appear_balls(t)
    f.pitch.add(t, 12)
    t = cascade(m, "ball", t + 0.2, 24, 0.40 * hb, style="high") + 0.6
    t = cascade(m, "ball", t, 50, 0.30) + 0.4
    t = flash(m, "ball", t + 0.3, T=1.0, b=0.2) + 0.4
    for k in (0, 1):
        if t + 14.0 + FIN > t_end:
            break
        t = _side(m, t, venue, k)
        t = cascade(m, "ball", t + 0.4, 30, 0.30) + 0.4
        t = flash(m, "ball", t + 0.3, T=1.0, b=0.2) + 0.4
    t = _side(m, t, venue, None)
    t = fill(m, "ball", t, t_end - FIN, 0.30)
    t = cascade(m, "ball", t + 0.4, 24, 0.42 * hb, style="high") + 0.4
    t = m.vanish_balls(t)
    f.pitch.add(t, 3)
    t = m.bow(t, 45, venue)
    m.audience.append((t0, t, venue, None))
    m.acts.append((t0, t, "balls", venue))
    return t


def act_magic(m, t, venue, t_end=None, look=None):
    """A ball from the air, vanished and found at his ear and mouth; the
    floating silver ball; silks from his fist; a fan of cards sprung hand to
    hand and thrown up; a bouquet from nowhere."""
    f = m.f
    t0 = t
    t = _stage(m, t, venue)
    short = t_end is not None and t_end - t < 88.5
    t = m.bow(t, 25, venue)
    # Empty hands.
    f.L.add(t + 0.8, V((-0.26, 0.34, 1.32))).add(t + 2.2, V((-0.30, 0.30, 1.28)))
    f.R.add(t + 0.8, V((0.26, 0.34, 1.32))).add(t + 2.2, V((0.30, 0.30, 1.28)))
    f.yaw.add(t + 1.0, -25).add(t + 2.4, 25).add(t + 3.4, 0)
    t += 3.6
    # A ball out of the air.
    f.R.add(t + 0.9, V((0.32, 0.30, 1.78)))
    f.pitch.add(t + 0.9, -18)
    ta = t + 1.0
    m.prop("MBall", ta, ("hand", "R", np.array((0, 0, BALL_R)), Q_ID), 0)
    m.scale("MBall", ta, 0.001, ta + 0.15, 1.0)
    f.R.add(t + 1.9, V((0.14, 0.36, 1.32)))
    f.pitch.add(t + 1.9, 6)
    t += 3.0
    finds = ((V((0.13, 0.04, 1.63)), -4),) if short else ((V((0.13, 0.04, 1.63)), -4), (V((0.04, 0.13, 1.52)), 10))
    for q, (where, pitch) in enumerate(finds):
        f.L.add(t + 0.7, V((-0.03, 0.36, 1.30)))           # the left hand takes it (it doesn't)
        f.R.add(t + 0.7, V((0.05, 0.36, 1.30)))
        m.prop("MBall", t + 0.9, ("hide",), 0)
        f.L.add(t + 1.6, V((-0.28, 0.36, 1.38))).add(t + 2.6, V((-0.28, 0.36, 1.38)))
        f.R.add(t + 1.6, HR["R"].copy())
        f.pitch.add(t + 1.8, 18).add(t + 2.6, 18)          # looks: gone
        f.L.add(t + 3.2, HR["L"].copy())
        f.R.add(t + 3.6, where.copy())
        f.pitch.add(t + 3.6, pitch)
        f.yaw.add(t + 3.6, 20 if q == 0 else 0)
        m.prop("MBall", t + 3.7, ("hand", "R", np.array((0, 0, BALL_R)), Q_ID), 0)
        m.scale("MBall", t + 3.7, 0.001, t + 3.85, 1.0)
        f.R.add(t + 4.6, V((0.20, 0.40, 1.36)))
        f.yaw.add(t + 4.6, 0)
        f.pitch.add(t + 4.6, 4)
        t += 5.6
    # Tossed up, it never comes down.
    f.R.add(t + 0.4, V((0.14, 0.34, 1.20))).add(t + 0.7, V((0.12, 0.30, 1.45)))
    m.prop("MBall", t + 0.7, ("fn", _toss_up(t + 0.7)), 0)
    m.prop("MBall", t + 1.25, ("hide",), 0)
    f.pitch.add(t + 1.0, -30).add(t + 2.6, -30).add(t + 3.4, 4)
    f.R.add(t + 1.6, HR["R"].copy())
    f.L.add(t + 2.2, V((-0.30, 0.25, 1.15))).add(t + 3.0, V((-0.30, 0.25, 1.15))).add(t + 3.6, HR["L"].copy())
    f.R.add(t + 2.2, V((0.30, 0.25, 1.15))).add(t + 3.0, V((0.30, 0.25, 1.15))).add(t + 3.6, HR["R"].copy())
    t += 4.0
    # The floating ball: it rises off his palm, wanders, tugs him a step, goes
    # over his head and settles back, then it's gone.
    zk = Keys()
    path = [(0.0, (-0.02, 0.34, 1.26)), (1.2, (-0.02, 0.34, 1.26)), (3.0, (0.0, 0.36, 1.52)), (5.0, (0.24, 0.40, 1.46)),
            (7.0, (-0.22, 0.38, 1.40)), (9.0, (0.0, 0.42, 1.62)), (11.0, (0.02, 0.60, 1.50)), (13.5, (0.0, 0.62, 1.48)),
            (15.5, (0.0, 0.30, 1.95)), (17.5, (0.10, 0.36, 1.58)), (19.5, (-0.02, 0.34, 1.26))]
    for dt, p in path:
        zk.add(t + dt, V(p))
    m.prop("ZBall", t, ("local", zk, Q_ID), 0)
    m.scale("ZBall", t, 0.001, t + 0.3, 1.0)
    for dt, p in path:
        p = V(p)
        f.L.add(t + dt, p + V((-0.10, -0.01, -0.06)) if dt not in (0.0, 1.2, 19.5) else p + V((0, 0, -0.06)))
        f.R.add(t + dt, p + V((0.10, -0.01, 0.06)) if dt > 0.0 else HR["R"].copy())
        f.pitch.add(t + dt, max(-30, min(20, (1.45 - p.z) * 60)))
    fw = DF._fwd(m.yaw)
    m.slide(t + 11.0, (m.x + 0.25 * fw.x, m.y + 0.25 * fw.y), 2.0)            # it tugs him a step
    m.slide(t + 15.5, (m.x - 0.25 * fw.x, m.y - 0.25 * fw.y), 2.0)
    t += 19.5
    m.prop("ZBall", t + 0.5, ("hide",), 0)
    f.R.add(t + 0.5, V((-0.02, 0.34, 1.30)))
    f.L.add(t + 1.2, V((-0.26, 0.32, 1.32)))
    f.R.add(t + 1.2, V((0.26, 0.32, 1.32)))
    f.L.add(t + 2.0, HR["L"].copy())
    f.R.add(t + 2.0, HR["R"].copy())
    f.pitch.add(t + 1.2, 4)
    t += 2.4
    # Silks: drawn out of his left fist, one knotted to the next, waved, and
    # pushed back into the fist.
    fist = V((-0.05, 0.32, 1.24))
    f.L.add(t + 0.7, fist.copy())
    f.R.add(t + 0.7, fist + V((0.06, 0.0, 0.03)))
    pulls = [(t + 1.6, (0.14, 0.34, 1.42)), (t + 3.0, (0.22, 0.34, 1.58)), (t + 4.4, (0.30, 0.34, 1.74)),
             (t + 5.8, (0.36, 0.30, 1.90))]
    for tt, p in pulls:
        f.R.add(tt, V(p))
    m.silk_out.add(t + 0.9, 0.0).add(t + 5.8, 6.0)
    for i in range(6):
        m.prop(f"Silk{i}", t + 0.9, ("fn", _silk(i)), 0)
    f.pitch.add(t + 3.0, -10).add(t + 5.8, -20)
    t += 5.8
    for q in range(3):                                  # waving them about
        f.R.add(t + 0.6, V((0.10, 0.32, 1.92))).add(t + 1.2, V((0.40, 0.30, 1.86)))
        t += 1.2
    f.R.add(t + 1.0, fist + V((0.04, 0.0, 0.10)))
    f.pitch.add(t + 1.0, 8)
    m.silk_out.add(t + 1.0, 6.0).add(t + 3.4, 0.0)
    f.R.add(t + 3.4, fist + V((0.03, 0.0, 0.05)))
    for i in range(6):
        m.prop(f"Silk{i}", t + 3.5, ("hide",), 0)
    f.L.add(t + 4.2, V((-0.30, 0.34, 1.36)))           # open: empty
    f.R.add(t + 4.2, V((0.30, 0.34, 1.36)))
    f.L.add(t + 5.4, HR["L"].copy())
    f.R.add(t + 5.4, HR["R"].copy())
    f.pitch.add(t + 4.2, 4)
    t += 5.8
    # Cards: a fan out of nowhere, shown round, sprung into the other hand, and
    # thrown up in a shower that is gone before it lands.
    f.R.add(t + 0.8, V((0.20, 0.38, 1.40)))
    m.prop("Fan", t + 0.9, ("hand", "R", np.array((0.0, 0.0, 0.03)), Q_ID), 0)
    m.scale("Fan", t + 0.9, 0.001, t + 1.2, 1.0)
    f.R.add(t + 2.2, V((-0.05, 0.42, 1.44))).add(t + 3.6, V((0.32, 0.36, 1.42)))
    f.yaw.add(t + 2.2, -20).add(t + 3.6, 20).add(t + 4.2, 0)
    t += 4.4
    f.R.add(t + 0.6, V((0.18, 0.36, 1.32)))
    f.L.add(t + 0.6, V((-0.18, 0.36, 1.26)))
    m.prop("Fan", t + 0.8, ("hide",), 0)
    for i in range(8):
        ts = t + 0.8 + i * 0.12
        m.prop(f"Card{i}", ts, ("fly", "R", ts, "L", ts + 0.42, "card", 0), 0)
        m.prop(f"Card{i}", ts + 0.42, ("hand", "L", np.array((0.0, 0.0, 0.03 + 0.002 * i)), Q_ID), 0)
    t += 2.4
    f.L.add(t + 0.5, V((-0.12, 0.34, 1.10))).add(t + 1.3, V((-0.08, 0.36, 1.62)))
    f.pitch.add(t + 1.3, -24).add(t + 3.3, -24).add(t + 3.9, 6)
    for i in range(8):                                  # (not so high under the Rovers' ceiling)
        m.prop(f"Card{i}", t + 1.3, ("fn", _card_shower(i, t + 1.3, 0.78 if venue == "pub" else 1.0)), 0)
        m.prop(f"Card{i}", t + 2.9 + 0.06 * i, ("hide",), 0)
    f.L.add(t + 2.4, HR["L"].copy())
    f.R.add(t + 2.4, HR["R"].copy())
    t += 4.2
    # The bouquet.
    f.R.add(t + 0.8, V((0.36, 0.20, 1.70))).add(t + 1.4, V((0.22, 0.42, 1.38)))
    m.prop("Bouquet", t + 1.4, ("hand", "R", np.array((0.0, 0.0, 0.02)), Q_ID), 0)
    m.scale("Bouquet", t + 1.4, 0.001, t + 1.8, 1.0)
    f.lean.add(t + 2.4, 18).add(t + 4.6, 18).add(t + 5.4, 3)
    f.R.add(t + 2.4, V((0.14, 0.62, 1.30))).add(t + 4.6, V((0.14, 0.62, 1.30)))
    if look is not None:
        m.look_at(t + 2.0, look)
    f.R.add(t + 5.6, V((0.06, 0.20, 1.58)))             # a sniff, delighted
    f.pitch.add(t + 5.6, -10).add(t + 6.8, -10).add(t + 7.4, 4)
    f.yaw.add(t + 5.6, 0)
    f.R.add(t + 7.4, V((0.22, 0.36, 1.48)))
    m.scale("Bouquet", t + 7.6, 1.0, t + 7.9, 0.001)
    m.prop("Bouquet", t + 7.95, ("hide",), 0)
    f.R.add(t + 8.4, HR["R"].copy())
    t += 8.6
    if t_end is not None and t_end - 4.8 > t + 0.5:     # a beat, arms open, to the crowd
        f.L.add(t + 0.6, V((-0.36, 0.26, 1.30))).add(t_end - 5.4, V((-0.36, 0.26, 1.30)))
        f.R.add(t + 0.6, V((0.36, 0.26, 1.30))).add(t_end - 5.4, V((0.36, 0.26, 1.30)))
        f.L.add(t_end - 4.8, HR["L"].copy())
        f.R.add(t_end - 4.8, HR["R"].copy())
        t = t_end - 4.8
    t = m.bow(t, 45, venue)
    m.audience.append((t0, t, venue, None))
    m.acts.append((t0, t, "magic", venue))
    return t


def _toss_up(t0):
    def fn(fis, C):
        tt = fis / FPS - t0
        p0 = C["palm"]["R"][C["fi"](t0)] + np.array((0, 0, BALL_R))
        P = p0 + np.outer(4.0 * tt - 0.5 * G * tt * tt, (0, 0, 1))
        return P, np.tile(Q_ID, (len(fis), 1))
    return fn


def _silk(i):
    """Silk i of the chain between the right hand (top) and the left fist."""
    def fn(fis, C):
        n_out = C["silk_out"][fis]
        R, L = C["palm"]["R"][fis], C["palm"]["L"][fis]
        n = np.maximum(n_out, 1e-3)
        s = np.clip((i + 0.5) / n, 0.0, 1.0)[:, None]
        span = np.linalg.norm(R - L, axis=1)
        sag = 0.5 * np.sqrt(np.maximum(0.0, (n * 0.20) ** 2 - span ** 2))[:, None]
        P = R + (L - R) * s - np.array((0, 0, 1.0)) * sag * 4 * s * (1 - s) - np.array((0, 0, 0.09)) * (s < 0.5)
        Q = DF.qmul(C["qb"][fis], _QSILK)
        vis = n_out > i + 0.15
        return P, Q, np.where(vis, 1.0, 0.001)
    return fn


def _card_shower(i, t0, k=1.0):
    rs = random.Random(f"card{i}")
    v = np.array((rs.uniform(-0.8, 0.8), rs.uniform(0.2, 1.0), rs.uniform(3.4, 4.2) * k))
    spin = rs.uniform(-400, 400)

    def fn(fis, C):
        tt = (fis / FPS - t0)[:, None]
        f0 = C["fi"](t0)
        p0 = C["palm"]["L"][f0] + np.array((0, 0, 0.03))
        vw = DF.qrot(C["qb"][f0], v)
        drag = np.minimum(tt, 0.5) + np.maximum(tt - 0.5, 0) * 0.35       # paper: slows and flutters down
        P = p0 + vw * np.array((1, 1, 0)) * drag + np.array((0, 0, 1)) * (v[2] * np.minimum(tt, 0.55) -
                                                                         0.5 * G * np.minimum(tt, 0.55) ** 2 -
                                                                         0.9 * np.maximum(tt - 0.55, 0))
        P[:, 2] = np.maximum(P[:, 2], Z0 + 0.01)
        Q = DF.qmul(C["qb"][f0], DF.qmul(DF.qyaw(spin * tt[:, 0]), DF.qx(spin * 0.7 * tt[:, 0])))
        return P, Q
    return fn


_QSILK = np.array((math.cos(math.radians(22.5)), 0.0, math.sin(math.radians(22.5)), 0.0))   # a diamond to the audience


def num_balls_cafe(m, t, rng, P=None, couple=None):
    """The café juggling act: a cascade high and slow, fast, a dropped ball
    chased across the paving, a run in front of each table, a lap past both."""
    f = m.f
    t0 = t
    t = m.to_stage(t)
    t = m.bow(t, 25, "cafe")
    t = m.appear_balls(t)
    f.pitch.add(t, 14)
    t = cascade(m, "ball", t + 0.2, 24, 0.40, style="high") + 0.6
    f.pitch.add(t, 10)
    t = cascade(m, "ball", t + 0.4, 60, 0.30) + 0.4
    t = flash(m, "ball", t + 0.3, T=1.0, b=0.2) + 0.4
    t = cascade(m, "ball", t, 36, 0.42, style="high") + 0.4
    # The drop: one sails off; he stares, then fetches it.
    te = cascade(m, "ball", t + 0.2, 12, 0.30)
    spot = V((m.x + 0.75, m.y - 0.95, Z0 + BALL_R))
    tdrop = t + 0.2 + 11 * 0.30
    dropped = None
    for i in range(3):
        for j, (tt, st, bl) in enumerate(m.pt[NAMES["ball"][i]]):
            if st[0] == "fly" and abs(tt - tdrop) < 1e-6:
                dropped = i
                m.pt[NAMES["ball"][i]][j] = (tt, ("fn", _ball_fall(tt, st[1], spot)), 0)
                # its catch never happens
                m.pt[NAMES["ball"][i]] = [e for e in m.pt[NAMES["ball"][i]] if not (e[0] > tt and e[0] < tt + 1.5 and
                                                                                    e[1][0] == "hand")]
    t = te
    f.yaw.add(t, 0).add(t + 0.5, -35)
    f.pitch.add(t + 0.5, 38)
    f.L.add(t + 1.0, V((-0.10, 0.12, 1.62)))
    f.R.add(t + 1.0, V((0.10, 0.12, 1.62)))                  # hands to the cheeks
    f.lean.add(t + 1.0, -6)
    f.L.add(t + 2.4, V((-0.10, 0.12, 1.62)))
    f.R.add(t + 2.4, V((0.10, 0.12, 1.62)))
    f.L.add(t + 3.2, HR["L"].copy())
    f.R.add(t + 3.2, HR["R"].copy())
    f.lean.add(t + 3.2, 3)
    f.yaw.add(t + 3.2, 0)
    f.pitch.add(t + 3.2, 10)
    t += 3.4
    near = (m.x + 0.55, m.y - 0.70)
    t = m.walk(t, [(m.x, m.y), near])
    t = m.face(t, spot)
    rest = spot + V((0.18, -0.22, 0))
    f.lean.add(t, 3).add(t + 0.9, 62).add(t + 1.8, 62).add(t + 2.8, 3)
    f.bow.add(t, 0).add(t + 0.9, 20).add(t + 1.8, 20).add(t + 2.8, 0)
    f.R.add(t, HR["R"].copy()).add(t + 1.0, f.at_world(V((rest.x - 0.02, rest.y + 0.04, Z0 + 0.12))))
    m.prop(NAMES["ball"][dropped], t + 1.1, hand_state("ball", "R", 1), 6)
    f.R.add(t + 1.4, f.at_world(V((rest.x - 0.02, rest.y + 0.04, Z0 + 0.12))))
    f.R.add(t + 2.8, HR["R"].copy())
    t = m.vanish_balls(t + 2.9)
    ways = {"couple": [(10.0, -5.90), (8.60, -5.90), (8.40, -6.60), (7.95, -7.50)],
            "jay": [(8.40, -6.60), (8.60, -5.90), (10.30, -5.90), (10.32, -7.30)]}
    for way, face_to in (("couple", TABLE), ("jay", JAY_TABLE)):
        t = m.walk(t, [(m.x, m.y)] + ways[way])
        t = m.face(t, face_to)
        t = m.appear_balls(t)
        f.pitch.add(t, 12)
        t = cascade(m, "ball", t + 0.2, 48, 0.31) + 0.3
        t = flash(m, "ball", t + 0.3, T=1.0, b=0.2) + 0.4
        t = m.vanish_balls(t)
        f.pitch.add(t, 3)
        t = m.bow(t + 0.2, 30, "cafe")
    t = m.walk(t, [(m.x, m.y), (10.30, -5.90), STAGE])
    t = m.turn(t, 180.0)
    t = m.appear_balls(t)
    f.pitch.add(t, 12)
    t0j = t + 0.2
    t = cascade(m, "ball", t0j, 42, 0.32)
    path = [STAGE, (8.85, -6.55), (8.55, -7.55), (9.20, -8.85), (10.40, -8.40), (10.45, -6.40), STAGE]
    _glide_path(m, t0j + 0.5, t - 0.6, path)
    t = m.vanish_balls(t + 0.2)
    f.pitch.add(t, 3)
    t = m.turn(t, 180.0)
    t = m.bow(t, 45, "cafe")
    m.audience.append((t0, t, "cafe", None))
    m.acts.append((t0, t, "balls", "cafe"))
    return t


def _ball_fall(t0, side, spot):
    """Off the hand in a low arc to the paving, a bounce or two, rolling to rest."""
    def fn(fis, C):
        f0 = C["fi"](t0)
        p0 = C["palm"][side][f0] + np.array((0, 0, BALL_R + 0.004))
        p1 = np.array(spot[:]) + np.array((0, 0, 0.0))
        tt = fis / FPS - t0
        P = np.empty((len(fis), 3))
        T = 0.75
        for j, s in enumerate(tt):
            if s < T:
                u = s / T
                P[j] = p0 + (p1 - p0) * u + np.array((0, 0, 0.5 * G * T * T * u * (1 - u) * 0.6))
            else:
                b = s - T
                h = 0.22 * 4 * (b / 0.45) * (1 - b / 0.45) if b < 0.45 else \
                    (0.06 * 4 * ((b - 0.45) / 0.25) * (1 - (b - 0.45) / 0.25) if b < 0.7 else 0.0)
                w = min(1.0, b / 1.6)
                P[j] = p1 + np.array((0.18, -0.22, 0.0)) * (1 - (1 - w) ** 2) + np.array((0, 0, h))
        return P, np.tile(Q_ID, (len(fis), 1))
    return fn


def _glide_path(m, t0, t1, path):
    """Root along a path between t0 and t1 (facing the way he goes; each
    corner turned on the spot, quickly, so the quiver on his hip swings round
    rather than jumping)."""
    f = m.f
    pts = [V(p) for p in path]
    lens = [(pts[i + 1] - pts[i]).length for i in range(len(pts) - 1)]
    hs = [heading(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
    turns = [abs(((hs[i] - (hs[i - 1] if i else m.yaw)) + 180) % 360 - 180) / 380.0 for i in range(len(hs))]
    move = (t1 - t0) - sum(turns)
    total = sum(lens)
    f.put(t0, m.x, m.y, m.yaw)
    t = t0
    for i in range(1, len(pts)):
        f.put(t + max(0.01, turns[i - 1]), pts[i - 1].x, pts[i - 1].y, hs[i - 1], lin=True)
        t += max(0.01, turns[i - 1]) + move * lens[i - 1] / total
        f.put(t, pts[i].x, pts[i].y, hs[i - 1], lin=True)
        f.zk.add(t, floor_z(pts[i].x, pts[i].y))
    m.x, m.y, m.yaw = pts[-1].x, pts[-1].y, f._yaw
    return t


def walkabout(m, t, t_end, rng):
    """Juggling his way round past both café tables until t_end, then a bow at
    the stage (the filler that lands the schedule on its mark)."""
    f = m.f
    t0 = t
    t = m.to_stage(t)
    lap = _walk_len(WALKABOUT) / m.speed
    if t_end - t > lap + 14.0:
        t = m.appear_balls(t)
        f.pitch.add(t, 10)
        laps = int((t_end - t - 10.0) / (lap + 2.0))
        if laps >= 1:
            t1 = t + laps * (lap + 2.0)
            n = int((t1 - t - 0.6) / 0.32) - 2
            te = cascade(m, "ball", t + 0.2, n, 0.32)
            _glide_path(m, t + 0.5, te - 0.6, WALKABOUT * laps)
            t = te
        t = m.vanish_balls(t + 0.1)
        f.pitch.add(t, 3)
        t = m.turn(t, 180.0)
    if t_end - t > 6.0:
        t = m.bow(t, 40, "cafe")
        m.audience.append((t0, t, "cafe", None))
    return t


# --- The rola bola ------------------------------------------------------------
# A board across a roller: he sets it up on his spot, steps up, finds his
# balance (the roller rolling under him, the board seesawing, his arms out),
# draws three clubs from the quiver and juggles up there, high, fast, a flash,
# with a big wobble saved in the middle; down with a hop for the bow, and the
# kit back against the parapet glass. Board and roller stand there, between
# the planter at the counter's end and his chair, between times.
ROLA_R = 0.06                                      # roller radius
ROLA_BOARD = (0.70, 0.22, 0.025)                   # board length (his left-right), width, thickness
ROLA_TOP = 2 * ROLA_R + ROLA_BOARD[2]              # board top over the floor, level
ROLA_FOOT = 0.22                                   # feet this far out along the board
ROLA_AT = (10.80, -5.38)                           # where he stands (facing east) to take the kit
ROLA_REST = {"RolaBoard": (V((11.25, -5.48, Z0 + 0.36)), "board"),      # against the parapet glass
             "RolaTube": (V((11.22, -5.30, Z0 + 0.20)), "tube")}


def _qy(deg):
    a = np.radians(np.asarray(deg, float)) / 2
    z = np.zeros_like(a)
    return np.stack([np.cos(a), z, np.sin(a), z], -1)


Q_BOARD_REST = DF.qmul(DF.qyaw(0.0), _qy(-80.0))      # stood on end, the top leaning on the café front
Q_TUBE_REST = DF.qx(90.0)                            # stood on end
Q_BOARD_CARRY = _qy(-90.0)                           # (body frame) on end at his right side
Q_TUBE_CARRY = DF.qx(90.0)


def rola_rest(name):
    if name in STAGE_REST:
        return stage_rest(name)
    p, _k = ROLA_REST[name]
    return ("spot", p, Q_BOARD_REST if name == "RolaBoard" else Q_TUBE_REST)


# Where the finale's props wait on the stage (and go back to).
_KZ = RF.STAGE_TABLE_TOP + 0.11 + 0.035              # a knife's grip, blade down in the block
_tx, _ty = RF.STAGE_TABLE
_bx, _by = RF.BUCKET
STAGE_REST = {
    "Knife0": (V((_tx - 0.035, _ty, _KZ)), DF.qx(180.0)),
    "Knife1": (V((_tx, _ty, _KZ)), DF.qx(180.0)),
    "Knife2": (V((_tx + 0.035, _ty, _KZ)), DF.qx(180.0)),
    "Rola2Board": (V((-3.56, -11.02, RF.STAGE_TOP + 0.35)), None),
    "Rola2Tube": (V((-3.43, -11.14, RF.STAGE_TOP + 0.21)), DF.qx(90.0)),
    "WandL": (V((_bx - 0.025, _by + 0.01, RF.BUCKET_TOP + 0.18)), DF.qx(180.0)),     # sticks: the string end down
    "WandR": (V((_bx + 0.02, _by - 0.01, RF.BUCKET_TOP + 0.18)), DF.qx(180.0)),      # in the soap
    "WandS": (V((_bx + 0.04, _by - 0.06, RF.BUCKET_TOP + 0.20)), DF.qx(180.0)),
}


def stage_rest(name):
    p, q = STAGE_REST[name]
    if q is None:
        q = DF.qmul(DF.qyaw(180.0), _qy(-80.0))        # on end, the top against the drapes
    return ("spot", p.copy(), q)


_SAMPLES = {}


def _samp(keys):
    if id(keys) not in _SAMPLES or _SAMPLES[id(keys)][0] != DF.N:
        keys.done()
        _SAMPLES[id(keys)] = (DF.N, np.array(DF.sample(keys), float))
    return _SAMPLES[id(keys)][1]


def _rola_board(W, yaw, PHI):
    """The board over the roller at W (floor level), seesawing by PHI (deg)."""
    def fn(fis, C):
        ph = _samp(PHI)[fis]
        n = len(fis)
        P = np.tile(np.array((W[0], W[1], W[2] + 2 * ROLA_R + ROLA_BOARD[2] / 2)), (n, 1))
        Q = DF.qmul(np.tile(DF.qyaw(yaw), (n, 1)), _qy(ph))
        return P, Q
    return fn


def _rola_tube(W, yaw, U):
    """The roller under the board, rolled U (m) to his right."""
    def fn(fis, C):
        u = _samp(U)[fis]
        n = len(fis)
        q0 = np.tile(DF.qyaw(yaw), (n, 1))
        off = np.stack([u, np.zeros(n), np.full(n, ROLA_R)], 1)
        P = np.array(W, float) + DF.qrot(q0, off)
        Q = DF.qmul(q0, _qy(np.degrees(-u / ROLA_R)))
        return P, Q
    return fn


def _rola_keys(m, t0, t1, amp, f_hz=0.75, arms=True, flail=None):
    """Balancing from t0 to t1: the roller rolls amp (m) either way, the board
    tips with it, his feet ride the board ends; arms out (and flailing in a
    big wobble at `flail`)."""
    f = m.f
    U, PHI = m.rola
    t = t0
    def env(tt):                                   # the big wobble swells and dies away
        if flail is None:
            return 0.0
        x = (tt - flail + 0.6) / 3.0
        return math.sin(math.pi * x) ** 2 if 0.0 < x < 1.0 else 0.0
    while t <= t1 + 1e-6:
        a = amp(t) if callable(amp) else amp
        a *= 1.0 + 1.4 * env(t)
        u = a * math.sin(2 * math.pi * f_hz * (t - t0))
        ph = -110.0 * u
        U.add(t, u, lin=True)
        PHI.add(t, ph, lin=True)
        s = math.sin(math.radians(ph))
        f.fL.add(t, V((-ROLA_FOOT, 0.02, 0.09 + ROLA_FOOT * s)), lin=True)
        f.fR.add(t, V((ROLA_FOOT, 0.02, 0.09 - ROLA_FOOT * s)), lin=True)
        if arms:
            w = 0.10 * u / 0.06
            e = env(t)
            f.L.add(t, V((-0.50, 0.10, 1.30 + w + 0.14 * e * math.sin(t * 5.0))), lin=True)
            f.R.add(t, V((0.50, 0.10, 1.30 - w + 0.14 * e * math.cos(t * 5.0))), lin=True)
        f.lean.add(t, 4 + 7 * env(t) * math.sin(t * 4.0), lin=True)
        t += 1.0 / 6.0
    return t1


def act_rola(m, t, venue="cafe", t_end=None):
    """The rola bola at the café (see above)."""
    f = m.f
    t0 = t
    t_end = t + 92.0 if t_end is None else t_end
    # The kit off the café front.
    t = m.leg(t, [(m.x, m.y), ROLA_AT], f"r{int(t0)}_kit")
    t = m.turn(t, -90.0)
    pb, pt = ROLA_REST["RolaBoard"][0], ROLA_REST["RolaTube"][0]
    DF.hold_live(f.R, t)
    DF.hold_live(f.L, t)
    f.R.add(t + 0.8, f.at_world(V((pb.x - 0.08, pb.y - 0.10, pb.z + 0.12))))
    f.L.add(t + 0.8, f.at_world(V((pt.x - 0.08, pt.y + 0.04, pt.z + 0.10))))
    f.lean.hold(t).add(t + 0.8, 26).add(t + 1.8, 4)
    f.pitch.hold(t).add(t + 0.8, 20).add(t + 1.8, 4)
    m.prop("RolaBoard", t + 0.85, ("hand", "R", np.array((0.02, 0.0, 0.0)), Q_BOARD_CARRY), 8)
    m.prop("RolaTube", t + 0.85, ("hand", "L", np.array((0.0, 0.0, 0.0)), Q_TUBE_CARRY), 8)
    m.hold["R"], m.hold["L"] = "rola", "rola"
    f.R.add(t + 1.8, V((0.24, 0.10, 0.95)))
    f.L.add(t + 1.8, V((-0.24, 0.10, 0.95)))
    t += 2.0
    t = m.to_stage(t)
    # Set up in front of him: the roller across his line, the board on it.
    fw = DF._fwd(m.yaw)
    W = V((m.x + 0.35 * fw.x, m.y + 0.35 * fw.y, floor_z(m.x, m.y)))
    yaw0 = m.yaw
    U, PHI = Keys().add(0.0, 0.0), Keys().add(0.0, 0.0)
    m.rola = (U, PHI)
    f.L.add(t + 0.9, V((-0.05, 0.42, 0.40)))
    f.lean.add(t + 0.9, 46).add(t + 2.6, 46).add(t + 3.4, 4)
    f.pitch.add(t + 0.9, 30).add(t + 2.6, 30).add(t + 3.4, 4)
    m.prop("RolaTube", t + 0.95, ("fn", _rola_tube(W, yaw0, U)), 6)
    f.L.add(t + 1.5, V((-0.24, 0.10, 0.95)))
    f.R.add(t + 1.4, V((0.08, 0.42, 0.50))).add(t + 2.3, V((0.08, 0.44, 0.48)))
    m.prop("RolaBoard", t + 2.3, ("fn", _rola_board(W, yaw0, PHI)), 6)
    f.R.add(t + 3.0, HR["R"].copy())
    f.L.add(t + 3.0, HR["L"].copy())
    m.hold["R"], m.hold["L"] = None, None
    t += 3.4
    # Up onto it.
    x0, y0 = m.x, m.y
    f.put(t, x0, y0, yaw0)
    f.zk.add(t, floor_z(x0, y0))
    f.fL.add(t, V(RF.STAND_FEET[0])).add(t + 0.6, V((-ROLA_FOOT, 0.10, 0.30)))
    f.fR.add(t, V(RF.STAND_FEET[1]))
    f.L.add(t + 0.8, V((-0.50, 0.10, 1.30)))
    f.R.add(t + 0.8, V((0.50, 0.10, 1.30)))
    f.put(t + 1.4, W.x, W.y, yaw0)
    f.zk.add(t + 1.4, W.z + ROLA_TOP)
    m.x, m.y = W.x, W.y
    t += 1.4
    U.add(t, 0.0)
    PHI.add(t, 0.0)
    f.fL.add(t, V((-ROLA_FOOT, 0.02, 0.09)))
    f.fR.add(t, V((ROLA_FOOT, 0.02, 0.09)))
    m.audience.append((t0, t, "cafe", None))
    # Finding his balance: a wobble that nearly has him, saved.
    t = _rola_keys(m, t, t + 9.0, lambda tt: 0.05, flail=t + 4.0)
    # The clubs out of the quiver, still balancing (arms busy: the board carries on).
    f.L.add(t + 0.6, HR["L"].copy())                  # arms in, then the clubs
    f.R.add(t + 0.6, HR["R"].copy())
    tb = t
    t = draw3(m, t + 0.7, "club")
    t = _rola_keys(m, tb, t, 0.025, arms=False)
    f.pitch.add(t + 0.3, 12)
    FIN = 0.4 + 16 * 0.44 + 0.6 + 3.6 + 0.4 + 4.0 + 1.4 + 4.8 + 9.5
    tj = t
    t = cascade(m, "club", t + 0.6, 16, 0.44, 0.22, style="high") + 0.6
    t = cascade(m, "club", t, 30, 0.34) + 0.4
    t = flash(m, "club", t + 0.4, T=1.15, pirouette=False) + 0.6
    t = fill(m, "club", t, t_end - FIN)
    t = cascade(m, "club", t + 0.4, 14, 0.44, 0.22, style="high") + 0.6
    _rola_keys(m, tj, t, lambda tt: 0.022 + 0.018 * math.sin(0.4 * (tt - tj)) ** 2, arms=False)
    f.pitch.add(t, 3)
    ts = t
    t = sheath3(m, t, "club")
    _rola_keys(m, ts, t, 0.02, arms=False)
    t = _rola_keys(m, t + 0.7, t + 4.5, 0.035)          # (arms out again first)
    # A hop down off the back, a bow.
    U.add(t + 0.1, 0.0)
    PHI.add(t + 0.1, 0.0)
    f.put(t, m.x, m.y, yaw0)
    f.zk.add(t, W.z + ROLA_TOP).add(t + 0.5, W.z + ROLA_TOP + 0.12).add(t + 1.2, floor_z(x0, y0))
    f.put(t + 1.2, x0, y0, yaw0)
    m.x, m.y = x0, y0
    f.fL.add(t + 1.2, V(RF.STAND_FEET[0]))
    f.fR.add(t + 1.2, V(RF.STAND_FEET[1]))
    f.L.add(t + 1.2, HR["L"].copy())
    f.R.add(t + 1.2, HR["R"].copy())
    f.lean.add(t + 1.2, 3)
    t += 1.4
    t = m.bow(t, 45, "cafe")
    # Packed away.
    f.L.hold(t).add(t + 0.9, V((-0.05, 0.42, 0.40)))
    f.R.hold(t).add(t + 0.9, V((0.08, 0.44, 0.48)))
    f.lean.add(t + 0.9, 46).add(t + 1.8, 4)
    f.pitch.add(t + 0.9, 30).add(t + 1.8, 4)
    m.prop("RolaBoard", t + 0.95, ("hand", "R", np.array((0.02, 0.0, 0.0)), Q_BOARD_CARRY), 8)
    m.prop("RolaTube", t + 0.95, ("hand", "L", np.array((0.0, 0.0, 0.0)), Q_TUBE_CARRY), 8)
    m.hold["R"], m.hold["L"] = "rola", "rola"
    f.R.add(t + 1.8, V((0.24, 0.10, 0.95)))
    f.L.add(t + 1.8, V((-0.24, 0.10, 0.95)))
    t += 2.0
    t = m.leg(t, [(m.x, m.y), ROLA_AT], f"r{int(t0)}_kit_back")
    t = m.turn(t, -90.0)
    DF.hold_live(f.R, t)
    DF.hold_live(f.L, t)
    f.R.add(t + 0.8, f.at_world(V((pb.x - 0.08, pb.y - 0.10, pb.z + 0.12))))
    f.L.add(t + 0.8, f.at_world(V((pt.x - 0.08, pt.y + 0.04, pt.z + 0.10))))
    f.lean.add(t + 0.8, 26).add(t + 1.8, 4)
    f.pitch.add(t + 0.8, 20).add(t + 1.8, 4)
    m.prop("RolaBoard", t + 0.85, rola_rest("RolaBoard"), 8)
    m.prop("RolaTube", t + 0.85, rola_rest("RolaTube"), 8)
    m.hold["R"], m.hold["L"] = None, None
    f.R.add(t + 1.8, HR["R"].copy())
    f.L.add(t + 1.8, HR["L"].copy())
    t += 2.0
    t = m.to_stage(t)
    m.audience.append((t0, t, "cafe", None))
    m.acts.append((t0, t, "rola", "cafe"))
    return t



# --- The unicycle ---------------------------------------------------------------
# It lives leaning on the café's east parapet glass. He wheels it off by the
# saddle, rides it from place to place (juggling as he rides) and lays it down
# on its side where he plays: outside the Rovers' front door, beside the hot
# tub stage.
WHEEL_R = 0.24
CRANK = 0.12
HUB_Z = Z0 + WHEEL_R
SADDLE_Z = HUB_Z + 0.53
RIDE_Z = SADDLE_Z + 0.07 - 0.93                     # root z on the saddle (balcony floor)


def ride_z(x, y):
    """Root z on the saddle over the floor at (x, y) (the house is 0.10 lower)."""
    return RIDE_Z + floor_z(x, y) - Z0
UNI_LED = V((0.20, 0.35))                          # where the unicycle stands when he wheels it (his local xy)
UNI_HAND = V((0.20, 0.33, 0.82))                  # his right hand on the saddle then
ARMS = {"L": V((-0.45, 0.10, 1.30)), "R": V((0.45, 0.10, 1.30))}
UNI_TILT = 12.0                                   # leaning on the parapet glass
LAY_TILT = 100.0                                  # on its side, saddle and pedal on the floor
LAY_HUB = 0.155
CAFE_PARK = ("lean", (UNI_PARK.x, UNI_PARK.y, HUB_Z), UNI_PARK_YAW, UNI_TILT)
CAFE_LIFT = (UNI_PARK.x - 0.45, UNI_PARK.y)       # where he stands to take it off the glass (facing east)
PUB_LAY = (1.00, -8.67)                           # outside the Rovers, east of the porch (he faces east)
PUB_DOOR = [(-0.65, -9.30), (-0.65, -11.10)]
PUB_ROUND = list(RF.STAGE_WAY)                     # from the door past the café couple's table, up the step
TUB_LAY_FACE = 0.0
# The ways he rides (from wherever he mounts): along the balcony past the
# café tables and the Rovers' windows, round the spa lounge to the hot tub.
RIDE = {
    "cafe_pub": [(10.05, -5.95), (9.10, -5.92), (7.70, -6.35), (6.20, -7.55), (3.50, -7.65), (1.40, -7.75),
                 (1.05, -8.30), (1.00, -9.05)],
    "pub_tub": [(0.55, -8.15), (-0.40, -7.55), (-1.20, -7.45), (-4.00, -7.42), (-6.30, -7.40), (-6.60, -6.60),
                (-6.75, -5.55), (-7.60, -5.25), (-8.70, -5.25)],
    "cafe_tub": [(10.05, -5.95), (9.10, -5.92), (7.70, -6.35), (6.20, -7.55), (3.50, -7.65), (0.40, -7.70),
                 (-1.20, -7.45), (-4.00, -7.42), (-6.30, -7.40), (-6.60, -6.60), (-6.75, -5.55), (-7.60, -5.25),
                 (-8.70, -5.25)],
    # Into the house: across the café, in at its back door, up the kitchen
    # corridor, across the hall and up the dining room's west aisle to the
    # head of the table (and back).
    "cafe_dining": [(10.05, -5.95), (9.10, -5.80), (8.30, -5.25), (7.15, -4.75), (7.05, -3.90), (7.05, -2.50), (7.05, 0.60),
                    (7.20, 2.20), (7.25, 4.40), (7.25, 7.60), (7.70, 8.55), (8.60, 8.95), (9.40, 8.95)],
    "dining_cafe": [(8.30, 8.85), (7.55, 8.40), (7.25, 7.60), (7.25, 4.40), (7.15, 2.20), (7.05, 0.60),
                    (7.05, -2.50), (7.05, -3.90), (7.30, -4.80), (8.40, -5.40), (9.40, -5.95), (10.20, -5.95)],
    # Round the house: up the corridor, the length of the hall and back, a lap
    # round the dinner table, down the corridor home.
    "house": [(10.05, -5.95), (9.10, -5.80), (8.30, -5.25), (7.15, -4.75), (7.05, -3.90), (7.05, -2.50), (7.05, 0.60),
              (6.40, 1.85), (3.00, 1.90), (-1.00, 1.90), (-4.30, 1.95), (-4.85, 2.55), (-4.30, 3.15), (-1.00, 3.15),
              (3.00, 3.15), (6.30, 3.20), (7.25, 4.40), (7.25, 7.60), (7.70, 8.55), (8.80, 8.80), (9.90, 8.55),
              (10.35, 7.60), (10.35, 4.40), (9.40, 3.40), (7.60, 2.40), (7.05, 0.60), (7.05, -2.50),
              (7.05, -3.90), (7.30, -4.80), (8.40, -5.40), (9.40, -5.95), (10.20, -5.95)],
    # From outside the Rovers along the balcony and in at the café's back door
    # to the dinner table.
    "pub_dining": [(2.00, -7.95), (3.50, -7.65), (6.20, -7.55), (7.10, -6.60), (7.20, -5.50), (7.10, -4.60),
                   (7.05, -3.90), (7.05, -2.50), (7.05, 0.60), (7.20, 2.20), (7.25, 4.40), (7.25, 7.60), (7.70, 8.55),
                   (8.60, 8.95), (9.40, 8.95)],
    "tub_cafe": [(-6.85, -5.50), (-6.60, -6.40), (-6.35, -7.30), (-4.00, -7.45), (-1.20, -7.47), (0.40, -7.72),
                 (3.50, -7.70), (6.20, -7.70), (7.50, -6.55), (8.80, -6.00), (10.20, -5.95)],
    # From the hot tub back to the Rovers' front (the night's last ride: the
    # finale is next), dismounting where he always lays it outside the pub.
    "tub_pub": [(-6.85, -5.50), (-6.60, -6.40), (-6.35, -7.30), (-4.00, -7.45), (-1.20, -7.47), (0.40, -7.72),
                (1.05, -8.30), (1.00, -9.05)],
}


def _spline_open(pts, step=0.12):
    """Catmull-Rom through pts (open, end tangents mirrored) -> dense polyline."""
    P = [V(p) for p in pts]
    P = [P[0] * 2 - P[1]] + P + [P[-1] * 2 - P[-2]]
    out = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        n = max(2, int((p2 - p1).length / step))
        for j in range(n):
            s = j / n
            s2, s3 = s * s, s * s * s
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * s + (2 * p0 - 5 * p1 + 4 * p2 - p3) * s2 +
                              (-p0 + 3 * p1 - 3 * p2 + p3) * s3))
    out.append(P[-2].copy())
    return out


def _plen(pts):
    return sum((b - a).length for a, b in zip(pts, pts[1:]))


def _led_xy(m):
    a = math.radians(m.yaw)
    off = Matrix.Rotation(a, 2) @ UNI_LED
    return (m.x + off.x, m.y + off.y)


def _lay_pose(m):
    """Laid down on its side where he holds it now."""
    x, y = _led_xy(m)
    return ("lay", (x, y, floor_z(x, y) + LAY_HUB), m.yaw, LAY_TILT)


def uni_lift(m, t, pose):
    """Take hold of it (off the glass, or up off the floor) by the saddle."""
    f = m.f
    if pose[0] == "lay":
        f.R.add(t + 0.7, V((0.26, 0.38, 0.52)))
        f.lean.hold(t).add(t + 0.7, 38).add(t + 1.7, 4)
        f.pitch.hold(t).add(t + 0.7, 26).add(t + 1.7, 4)
        m.uni.append(("lift", t + 0.6, t + 1.5, pose))
        f.R.add(t + 1.6, UNI_HAND.copy())
        t1 = t + 1.8
    else:
        f.R.add(t + 0.6, UNI_HAND.copy())
        m.uni.append(("lift", t + 0.4, t + 1.6, pose))
        t1 = t + 1.6
    m.hold["R"] = "uni"
    return t1


def uni_park(m, t, pose):
    """Let go of it: back against the glass, or laid down on the floor."""
    f = m.f
    if pose[0] == "lay":
        m.uni.append(("park", t + 0.2, t + 1.2, pose))
        f.R.add(t + 0.9, V((0.26, 0.38, 0.54)))
        f.lean.hold(t).add(t + 0.9, 38).add(t + 1.9, 4)
        f.pitch.hold(t).add(t + 0.9, 26).add(t + 1.9, 4)
        m.hold["R"] = None
        f.R.add(t + 1.9, HR["R"].copy())
        t1 = t + 2.0
    else:
        m.uni.append(("park", t, t + 1.2, pose))
        m.hold["R"] = None
        f.R.add(t + 1.2, HR["R"].copy())
        t1 = t + 1.4
    return t1


def ride(m, t, way, name, speed=1.15, juggle=True):
    """Mount the unicycle he is holding (turned the way he will go), ride the
    way juggling three balls, rock to a stop and get off, holding it. A leg the
    planner may hold back at its start: he waits up on the unicycle, rocking on
    the spot and juggling."""
    t0 = t
    wait = LEG_WAIT.setdefault(name, 0.0)
    m.stay(t)
    t = m.turn(t, heading(_led_xy(m), way[0]))
    path = _spline_open([_led_xy(m)] + list(way))
    h = heading(path[0], path[1])
    m.uni.append(("under", t, t + 0.9, 0.0))
    m.hold["R"] = None
    _mount(m, t, 0.9, (path[0].x, path[0].y), h)
    t += 1.0
    m.uni.append(("ride", t, None))
    theta = 0.0
    if wait > 0.0:
        t, theta = _wait_up(m, t, theta, wait)
    t, theta = _ride_seq(m, t, theta, [(path, speed)], juggle=juggle and _plen(path) / speed > 8.0)
    t, theta = _rock(m, t, theta, 1.4)
    m.uni.append(("stop", t, theta))
    _dismount(m, t, 0.9)
    m.uni.append(("off", t, t + 0.9))
    m.hold["R"] = "uni"
    t += 1.0
    m.legs.append((t0, t, name))
    return t


def _wait_up(m, t, theta, dur):
    """Held up: rocking on the spot on the unicycle, juggling when there is
    time for it, arms out again before he rides on."""
    f = m.f
    if dur < 7.0:
        return _rock(m, t, theta, dur)
    t0 = t
    ta = m.appear_balls(t)
    n = max(6, int((t0 + dur - 2.6 - ta) / 0.30) - 2)
    te = cascade(m, "ball", ta + 0.2, n, 0.30)
    tv = m.vanish_balls(te)
    f.L.add(tv + 0.7, ARMS["L"].copy())
    f.R.add(tv + 0.7, ARMS["R"].copy())
    return _rock(m, t0, theta, max(dur, tv + 0.8 - t0), hands=False)


def _ride_seq(m, t, theta, seq, juggle):
    """Ride paths back to back; with juggle, three balls out of the pockets
    for the whole of it."""
    f = m.f
    ts = t
    for path, speed in seq:
        t, theta = _ride_path(m, t, theta, path, speed, hands=not juggle)
    if juggle:
        ta = m.appear_balls(ts + 0.1)
        n = int((t - 3.0 - ta) / 0.32) - 2
        te = cascade(m, "ball", ta + 0.2, n, 0.32)
        tv = m.vanish_balls(te)
        f.L.add(tv + 0.7, ARMS["L"].copy())
        f.R.add(tv + 0.7, ARMS["R"].copy())
        f.pitch.add(ta, 10).add(te, 10).add(tv, 3)
    return t, theta


def _pedals(theta):
    """Local foot targets on the pedals for wheel angle theta (forward = +y)."""
    hub = V((0.0, 0.0, HUB_Z - RIDE_Z))
    r = V((0.11, -CRANK * math.sin(theta), -CRANK * math.cos(theta) + 0.075))
    l = V((-0.11, CRANK * math.sin(theta), CRANK * math.cos(theta) + 0.075))
    return hub + l, hub + r


def _mount(m, t, dur, xy, yaw):
    f = m.f
    f.put(t, m.x, m.y, m.yaw)
    f.zk.add(t, floor_z(m.x, m.y))
    f.put(t + dur, xy[0], xy[1], yaw)
    f.zk.add(t + dur, ride_z(*xy))
    l, r = _pedals(0.0)
    f.fL.add(t, V(RF.STAND_FEET[0])).add(t + dur, l)
    f.fR.add(t, V(RF.STAND_FEET[1])).add(t + dur, r)
    f.L.add(t + dur, ARMS["L"].copy())
    f.R.add(t + dur, ARMS["R"].copy())
    m.x, m.y, m.yaw = xy[0], xy[1], f._yaw


def _dismount(m, t, dur):
    f = m.f
    a = math.radians(m.yaw)
    back = (m.x + 0.38 * math.sin(a), m.y - 0.38 * math.cos(a))
    f.put(t, m.x, m.y, m.yaw)
    f.zk.add(t, ride_z(m.x, m.y))
    f.put(t + dur, back[0], back[1], m.yaw)
    f.zk.add(t + dur, floor_z(*back))
    f.fL.add(t + dur, V(RF.STAND_FEET[0]))
    f.fR.add(t + dur, V(RF.STAND_FEET[1]))
    f.L.add(t + dur, HR["L"].copy())
    f.R.add(t + dur, UNI_HAND.copy())
    m.x, m.y = back


def _ride_path(m, t, theta, pts, speed, hands=True):
    """Along a path at speed (m/s), pedals turning with the wheel."""
    f = m.f
    for i in range(1, len(pts)):
        a, b = pts[i - 1], pts[i]
        d = (b - a).length
        if d < 1e-4:
            continue
        dt = d / speed
        h = heading(a, b)
        f.put(t, a.x, a.y, h, lin=True)
        f.zk.add(t, ride_z(a.x, a.y), lin=True)
        steps = max(1, int(dt * 6))
        for q in range(steps):
            tt = t + dt * q / steps
            th = theta + (d * q / steps) / WHEEL_R
            l, r = _pedals(th)
            f.fL.add(tt, l, lin=True)
            f.fR.add(tt, r, lin=True)
            wob = math.sin(tt * 2.3) * 4.0
            f.lean.add(tt, 6 + wob, lin=True)
            if hands:
                f.L.add(tt, V((-0.45, 0.10 + 0.04 * math.sin(tt * 3.1), 1.30 + 0.05 * math.sin(tt * 2.7))), lin=True)
                f.R.add(tt, V((0.45, 0.10 + 0.04 * math.cos(tt * 2.9), 1.30 + 0.05 * math.cos(tt * 2.5))), lin=True)
        theta += d / WHEEL_R
        m.uni.append(("roll", t, t + dt, theta - d / WHEEL_R, theta))
        t += dt
    m.x, m.y, m.yaw = pts[-1].x, pts[-1].y, f._yaw
    f.put(t, m.x, m.y, f._yaw)
    return t, theta


def _rock(m, t, theta, dur, wave=None, hands=True, turn=0.0):
    """Idling on the spot: a little back and forth, the pedals rocking (and
    turning by `turn` degrees on the way)."""
    f = m.f
    steps = max(2, int(dur * 6))
    yaw0 = m.yaw
    x0, y0 = m.x, m.y
    th0 = theta
    for q in range(steps + 1):
        tt = t + dur * q / steps
        yq = yaw0 + turn * (0.5 - 0.5 * math.cos(math.pi * q / steps))
        a = math.radians(yq)
        fwd = V((-math.sin(a), math.cos(a)))
        s = math.sin(2 * math.pi * (tt - t) / 1.4)
        dth = 0.6 * s
        dx = fwd * (dth * WHEEL_R)
        f.put(tt, x0 + dx.x, y0 + dx.y, yq, lin=True)
        f.zk.add(tt, ride_z(x0, y0), lin=True)
        l, r = _pedals(th0 + dth)
        f.fL.add(tt, l, lin=True)
        f.fR.add(tt, r, lin=True)
        f.lean.add(tt, 4 + 6 * s, lin=True)
        if hands and wave is None:
            f.L.add(tt, V((-0.45, 0.12, 1.30 + 0.04 * s)), lin=True)
            f.R.add(tt, V((0.45, 0.12, 1.30 - 0.04 * s)), lin=True)
        elif wave is not None:
            f.L.add(tt, V((-0.45, 0.12, 1.30 + 0.04 * s)), lin=True)
            if q == 0:
                f.R.add(tt, V((0.45, 0.12, 1.30)))
            elif tt - t >= 0.7 and tt < t + dur - 0.7:
                f.R.add(tt, V((0.30 + 0.08 * math.sin(tt * 9.0), 0.20, 1.80)), lin=True)
            elif tt >= t + dur - 0.05:
                f.R.add(tt, V((0.45, 0.12, 1.30)))
    if wave is not None:
        rel = ((heading((x0, y0), wave[:2]) - m.yaw) + 180) % 360 - 180
        f.yaw.add(t + 0.4, max(-70, min(70, rel))).add(t + dur - 0.3, max(-70, min(70, rel))).add(t + dur, 0)
    f.put(t + dur, x0, y0, yaw0 + turn)
    m.yaw = f._yaw
    m.uni.append(("rock", t, t + dur, th0))
    return t + dur, th0


# --- From place to place ----------------------------------------------------------
def cafe_out(m, t, name):
    """From the café stage: the unicycle off the parapet glass."""
    t = m.leg(t, [(m.x, m.y), CAFE_LIFT], name)
    t = m.turn(t, -90.0)
    return uni_lift(m, t, CAFE_PARK)


def cafe_in(m, t, name):
    """Off the unicycle by the café: wheeled to the glass, left leaning on it,
    back to the stage."""
    t = m.leg(t, [(m.x, m.y), CAFE_LIFT], name)
    t = m.turn(t, -90.0)
    t = uni_park(m, t, CAFE_PARK)
    t = m.walk(t, [(m.x, m.y), STAGE])
    return m.turn(t, 180.0)


def lay_here(m, t, venue, face):
    """Turned to `face`, the unicycle laid down beside him (remembered for later)."""
    t = m.turn(t, face)
    pose = _lay_pose(m)
    m.uni_at[venue] = ((m.x, m.y), m.yaw, pose)
    return uni_park(m, t, pose)


def pick_up(m, t, venue, name):
    """Back to where he laid it down, and up off the floor."""
    at, yaw, pose = m.uni_at[venue]
    t = m.leg(t, [(m.x, m.y), at], name)
    t = m.turn(t, yaw)
    return uni_lift(m, t, pose)


def to_pub(m, t, n):
    """Café -> the Rovers: ride along the balcony, the unicycle laid down
    outside, in at the front door to his spot on the floor."""
    t = cafe_out(m, t, f"{n}_lift")
    t = ride(m, t, RIDE["cafe_pub"], f"{n}_ride_pub")
    t = lay_here(m, t, "pub", -90.0)
    t = m.leg(t, [(m.x, m.y)] + PUB_DOOR + PUB_ROUND + [PUB_STAGE], f"{n}_pub_in")
    return m.turn(t, VENUES["pub"]["face"])


def pub_to_tub(m, t, n):
    t = m.leg(t + 1.0, [(m.x, m.y)] + list(reversed(PUB_ROUND)) + list(reversed(PUB_DOOR)), f"{n}_pub_out")
    t = pick_up(m, t, "pub", f"{n}_pub_uni")
    t = ride(m, t, RIDE["pub_tub"], f"{n}_ride_tub")
    t = lay_here(m, t, "tub", TUB_LAY_FACE)
    t = m.walk(t, [(m.x, m.y), TUB_STAGE])
    return m.turn(t, VENUES["tub"]["face"])


def pub_to_dining(m, t, n):
    t = m.leg(t + 1.0, [(m.x, m.y)] + list(reversed(PUB_ROUND)) + list(reversed(PUB_DOOR)), f"{n}_pub_out")
    t = pick_up(m, t, "pub", f"{n}_pub_uni")
    t = ride(m, t, RIDE["pub_dining"], f"{n}_ride_dining")
    t = lay_here(m, t, "dining", 0.0)
    t = m.leg(t, [(m.x, m.y), DINING_STAGE], f"{n}_dining_in")
    return m.turn(t, VENUES["dining"]["face"])


def tub_to_pub(m, t, n):
    """After the last round's hot tub act: back to the Rovers on the unicycle,
    laid down outside, in at the front door and up onto the stage, to wait in
    the dark by his table for the finale."""
    t = pick_up(m, t, "tub", f"{n}_tub_uni")
    t = ride(m, t, RIDE["tub_pub"], f"{n}_ride_back")
    t = lay_here(m, t, "pub", -90.0)
    t = m.leg(t, [(m.x, m.y)] + PUB_DOOR + PUB_ROUND + [FIN_WAIT], f"{n}_to_stage")
    return m.turn(t, FIN_FACE)


def cafe_to_tub(m, t, n):
    t = cafe_out(m, t, f"{n}_lift")
    t = ride(m, t, RIDE["cafe_tub"], f"{n}_ride_tub")
    t = lay_here(m, t, "tub", TUB_LAY_FACE)
    t = m.walk(t, [(m.x, m.y), TUB_STAGE])
    return m.turn(t, VENUES["tub"]["face"])


def tub_to_cafe(m, t, n):
    t = pick_up(m, t, "tub", f"{n}_tub_uni")
    t = ride(m, t, RIDE["tub_cafe"], f"{n}_ride_cafe")
    return cafe_in(m, t, f"{n}_park")


def to_dining(m, t, n):
    """Café -> the head of the dinner table on the unicycle, laid down by the
    dining room's north wall."""
    t = cafe_out(m, t, f"{n}_lift")
    t = ride(m, t, RIDE["cafe_dining"], f"{n}_ride_dining")
    t = lay_here(m, t, "dining", 0.0)
    t = m.leg(t, [(m.x, m.y), DINING_STAGE], f"{n}_dining_in")
    return m.turn(t, VENUES["dining"]["face"])


def from_dining(m, t, n):
    t = pick_up(m, t, "dining", f"{n}_dining_uni")
    t = ride(m, t, RIDE["dining_cafe"], f"{n}_ride_dined")
    return cafe_in(m, t, f"{n}_park")


def house_ride(m, t, n, t_end=None):
    """Round the house on the unicycle, juggling: the hall, the dining room,
    home to the café; then juggling round the café tables until t_end."""
    t0 = t
    t = cafe_out(m, t, f"{n}_lift")
    t = ride(m, t, RIDE["house"], f"{n}_ride_house")
    t = cafe_in(m, t, f"{n}_park")
    m.acts.append((t0, t, "house", "house"))
    if t_end is not None and t_end - t > 16.0:
        t = walkabout(m, t, t_end, None)
    return t


# --- The chef's espresso runs ---------------------------------------------------
def _on_counter_slot(slot, grip):
    """Palm for a cup on tray slot `slot` while the tray rests on the counter."""
    rot = Matrix.Rotation(math.radians(0.0), 3, 'Z')
    w = CAFE_TRAY + rot @ DF.TRAY_SLOTS[slot] + V((0, 0, grip))
    return lambda R, fi, w=w: w


WAITER_OUT = [(4.25, DF.HALL_Y), (0.30, DF.HALL_Y), (-0.65, -11.10), (-0.65, -9.30), (0.40, -7.75), (6.20, -7.75),
              (7.05, -6.90), (7.05, -5.00), C_MACHINE]     # from the Rovers to the café counter (behind the stage)


def coffee_run(cr, t_avail, who="chef", old=None, home=None):
    """Two espressos at the café counter, out on the tray, swapped for the
    couple's empties, the empties back to the counter and under it. who:
    the chef (from the kitchen) or a waiter ("W1", over from the Rovers)."""
    ch = cr.chef if who == "chef" else cr.W[who]
    P = cr.P
    d, _i = cr.delay(who)
    t0 = t_avail + d
    ch.stay(t0)
    track = old is None                               # (an explicit pair: authored out of time order)
    old = cr.cafe_on if track else old
    new = 3 - old
    tray = P.cafe_tray
    if who == "chef":
        t = ch.walk(t0, [(ch.x, ch.y), (7.05, DF.BACK_LINE)] + CHEF_OUT[1:])
    else:
        t = cr.pub_go(who, t0, WAITER_OUT[0])
        t = ch.walk(t, WAITER_OUT)
    t = ch.turn(t, 0.0)
    for j, pw in enumerate(("A", "B")):               # a cup under the spout, then onto the tray
        cup = P.cafe_cups[(pw, new)]
        t = ch.reach(t, "R", ch.f.at_world(V((SPOUT.x - 0.05, SPOUT.y - 0.16, SPOUT.z + 0.10))), 0.7, 14, 22)
        cup.at(t, ("hand", ch.f.tag, "R", "glass"))
        ch.hold["R"] = "glass"
        t += 1.8                                        # the shot runs
        tw = CAFE_TRAY + DF.TRAY_SLOTS[j]
        ct = ch.contact(t + 0.7, "R", ch.f.at_world(V((tw.x - 0.04, tw.y - 0.10, tw.z + CUP_GRIP + 0.04))),
                        _on_counter_slot(j, CUP_GRIP))
        t = ch.reach(t, "R", ct, 0.7, 16, 22)
        cup.at(t, ("on", tray, j))
        ch.hold["R"] = None
        t = ch.back(t + 0.1, "R", 0.8)
    tc = ch.take(t, "L", tray, CAFE_TRAY, "tray", lift=0.04, reach=0.105)
    t = ch.back(tc + 0.1, "L", 0.5)
    stops = {"A": SERVE["A"], "B": SERVE["B"]}
    path_a = [(ch.x, ch.y), (9.10, -5.05), (7.45, -6.30), ROUND_TABLE[0], stops["A"][0]]
    t = ch.walk(t, path_a)
    for pw, slot_old, slot_new, way in (("A", 2, 0, None), ("B", 3, 1, [ROUND_TABLE[0], ROUND_TABLE[1]])):
        if way:
            t = ch.walk(t, [(ch.x, ch.y)] + way + [stops[pw][0]])
        spot = CUP[pw]
        t = ch.face(t, spot)
        mark = t
        cold, cnew = P.cafe_cups[(pw, old)], P.cafe_cups[(pw, new)]
        tc = ch.take(t, "R", cold, spot, "glass", lift=CUP_GRIP, reach=0.05, lean=22, dur=0.9, bow=30)
        t = ch.reach(tc + 0.1, "R", ch.contact(tc + 0.7, "R", DF.TRAY_CENTRE + DF.TRAY_SLOTS[slot_old] +
                                               V((0, -0.05, CUP_GRIP)), DF.palm_on_tray(slot_old, CUP_GRIP)),
                     0.6, 18)
        cold.at(t, ("on", tray, slot_old))
        ch.hold["R"] = None
        t = ch.reach(t + 0.1, "R", ch.contact(t + 0.6, "R", DF.TRAY_CENTRE + DF.TRAY_SLOTS[slot_new] +
                                              V((0, -0.05, CUP_GRIP)), DF.palm_on_tray(slot_new, CUP_GRIP)),
                     0.5, 18)
        cnew.at(t, ("hand", ch.f.tag, "R", "glass"))
        ch.hold["R"] = "glass"
        tc = ch.put_down(t + 0.1, "R", cnew, spot, 0.0, lift=CUP_GRIP, reach=0.05, lean=22, dur=0.9, bow=30,
                         how="glass")
        cr.cafe_sets[pw].append((tc, new))
        t = ch.back(tc + 0.1, "R", 0.6)
        cr.couple[pw].busy.append((mark - 3.0, t + 1.5))
        cr.couple[pw].served.append((mark, t, (ch.x, ch.y)))
    t = ch.walk(t, [(ch.x, ch.y), ROUND_TABLE[1], (9.10, -6.30), (9.10, -5.05), C_MACHINE])
    t = ch.turn(t, 0.0)
    tc = ch.put_down(t, "L", tray, CAFE_TRAY, 0.0, lift=0.04, reach=0.105, how="tray")
    t = ch.back(tc + 0.1, "L", 0.5)
    for slot, pw in ((2, "A"), (3, "B")):             # empties under the counter
        cup = P.cafe_cups[(pw, old)]
        tw = CAFE_TRAY + DF.TRAY_SLOTS[slot]
        ct = ch.contact(t + 0.75, "R", ch.f.at_world(V((tw.x - 0.04, tw.y - 0.10, tw.z + CUP_GRIP + 0.04))),
                        _on_counter_slot(slot, CUP_GRIP))
        t = ch.reach(t, "R", ct, 0.75, 16, 22)
        cup.at(t, ("hand", ch.f.tag, "R", "glass"))
        t = ch.reach(t + 0.05, "R", V((0.14, 0.30, 0.62)), 0.8, 30, 30)
        cup.at(t, ("hidden",))
    t = ch.back(t + 0.1, "R")
    ch.hold["R"] = None
    if who == "chef" and home:
        t = ch.walk(t, [(ch.x, ch.y), (7.05, -5.00), (7.05, DF.BACK_LINE)] + DF.KIT_WEST + [home])
        t = ch.turn(t, DF.KIT_FACE)
    elif who == "chef":
        t = ch.walk(t, [(ch.x, ch.y), (7.05, -5.00), (7.05, DF.BACK_LINE), DF.C_STOVE])
        t = ch.turn(t, 180.0)
    else:
        t = ch.walk(t, list(reversed(WAITER_OUT)))
        t = cr.pub_go(who, t, DF.PUB_STN[who], DF.PUB_POST[who][2])
    ch.tasks.append((t0, t, "coffee"))
    ch.t = t
    if track:
        cr.cafe_on = new
    return t


KIT_COFFEE = (200.0, 920.0)                       # the lounge loop's espresso rounds (from the kitchen)


def coffee_from_kitchen(cr, t_avail):
    """The chef puts his glass down on the island, takes the café couple a round
    of espressos and comes back to it."""
    ch = cr.chef
    g = cr.P.kit["chef"]
    at = cr.kit_at("chef")
    d, _i = cr.delay("chef")
    t0 = t_avail + d
    ch.stay(t0)
    t = ch.walk(t0, [(ch.x, ch.y), at])
    t = ch.turn(t, DF.KIT_FACE)
    tc = ch.put_down(t, "R", g, DF.KIT_GLASS["chef"], DF.KIT_FACE, lift=g.grip, reach=0.05, how="glass")
    t = ch.back(tc + 0.1, "R", 0.5)
    t = ch.walk(t, [(ch.x, ch.y)] + list(reversed(DF.KIT_WEST)))
    ch.tasks.append((t0, t, "glass down"))
    t = coffee_run(cr, t, "chef", home=at)
    t1 = t
    tc = ch.take(t, "R", g, DF.KIT_GLASS["chef"], "glass", lift=g.grip, reach=0.05)
    ch.hold["R"] = "drink"
    t = ch.back(tc + 0.1, "R", 0.6)
    x, y, yaw = DF.kit_spot("chef")
    t = ch.walk(t, [(ch.x, ch.y), (x, y)])
    t = ch.turn(t, yaw)
    ch.tasks.append((t1, t, "glass up"))
    ch.t = t
    return t


def maybe_coffee(cr, t0, t1):
    """chef_idle hook: run the next due espresso round if it fits here."""
    due = getattr(cr, "cafe_due", None)
    if not due:
        return t0
    if t1 - t0 < 75.0 or due[0] > t1 - 75.0:
        return t0
    t = coffee_run(cr, max(t0, due[0]))
    due.pop(0)
    return t



# --- The finale ----------------------------------------------------------------
# Jay: once the dinner party and the café couple are in the Rovers, the mime
# runs a string of acts on the stage as the finale to the night, the pub
# lights down and him in a spotlight: things nobody has seen from him yet
# (knives, one-handed juggling, fire on the rola bola, fire eating and fire
# breathing, bubbles: giant ones off a string wand and a stream of small ones,
# only ever here) among his other numbers (the box, the silks and the bouquet,
# which he gives the café lady). Then he steps down and mingles. The acts land
# their bows on the regulars' marks (rovers_figures.FINALE_BOWS: they applaud
# each), the regulars turn to the stage from FINALE_WATCH; everything here is
# in session seconds, the finale starting at rovers_figures.FINALE_AT.
FIN_SPOT = RF.MIME_PUB                              # centre stage
FIN_FACE = RF.MIME_PUB_FACE                         # to the room
FIN_WAIT = (-3.12, -10.52)                          # upstage by his table, where he waits in the dark
LIGHTS_DOWN = (20.0, 26.0)                          # finale seconds: house lights going down
BEAM_ON = 26.0
LIGHTS_UP = (576.0, 584.0)
BEAM_OFF = (579.0, 581.5)
ROLA2_W_OUT = 0.10                                  # the stage rola bola is set this far in front of his spot
ROLA2_BACK = 0.30                                   # and he steps up onto it from this far behind it
Q_WAND = DF.qx(-35.0)                               # a wand in the hand: the stick up and forward
Q_EAT = DF.qx(165.0)                                # a torch held over his face, its flame down into his mouth
MOUTH_UP = V((0.0, 0.14, 1.64))                     # his mouth, head tilted back (his frame)
BOUQUET_SPOT = V((RF.CAB_TABLE[0] + 0.02, RF.CAB_TABLE[1] - 0.14, RF.CAB_TOP))
# The bouquet is given to the café lady from beside her stool (her left: the
# gap behind the stools between her table and the blonde lady's), along the
# floor from the step and back; every night the same way at the same times
# (her part is in the one dinner clip).
GIFT_AT = (1.50, -12.00)
GIFT_HAND = V((1.84, -11.76, 0.98))                 # where his hand meets hers
GIFT_WAY = [(-1.90, -10.85), (-1.55, -11.10), (-1.10, -11.30), (0.20, -12.30), (1.50, -12.30), GIFT_AT]


def _fwd_xy(yaw):
    a = math.radians(yaw)
    return V((-math.sin(a), math.cos(a)))


def _step_to(m, t, xy, face=None, dur=None):
    """A few steps on the stage: a glide to xy (and a turn)."""
    d = (V(xy) - V((m.x, m.y))).length
    if d > 0.02:
        t = m.slide(t, xy, dur or max(0.6, d / 0.6))
    if face is not None:
        t = m.turn(t, face)
    return t


def _land(m, t, t_bow, what):
    """Wait (a bright little pose, arms open to the crowd) until the bow that
    must reach its bottom at t_bow; note it if the act ran over."""
    t_go = t_bow - 2.4
    if t > t_go + 0.05:
        m.late.append((what, round(t - t_go, 1)))
        return t
    f = m.f
    m.stay(t)
    if t_go - t > 2.2:
        for side, sx in (("L", -1), ("R", 1)):
            keys = f.L if side == "L" else f.R
            if m.hold[side] is None:
                keys.hold(t).add(t + 0.8, V((sx * 0.34, 0.26, 1.34))).add(t_go - 0.6, V((sx * 0.34, 0.26, 1.34)))
                keys.add(t_go, HR[side].copy())
    m.stay(t_go)
    return t_go


def _reach_to(m, t, side, world, dur=0.8, lean=24, pitch=22):
    f = m.f
    if lean >= 34:                              # (right down to the bucket: not a snatch)
        dur = max(dur, 1.2)
    keys = f.L if side == "L" else f.R
    DF.hold_live(keys, t)
    keys.add(t + dur, f.at_world(world))
    f.lean.hold(t).add(t + dur, lean)
    f.pitch.hold(t).add(t + dur, pitch)
    return t + dur


def _take_prop(m, t, side, name, state, grip, dur=0.8, lean=24, pitch=22):
    """Hand to a prop where it stands (grip: the world point to reach) and into the hand."""
    t = _reach_to(m, t, side, grip + V((0, 0, 0.03)), dur, lean, pitch)
    m.prop(name, t, state, 6)
    return t + 0.1


def _put_prop(m, t, side, name, grip, dur=0.8, lean=24, pitch=22):
    """The prop back where it lives (its stage rest)."""
    t = _reach_to(m, t, side, grip + V((0, 0, 0.03)), dur, lean, pitch)
    m.prop(name, t, stage_rest(name), 6)
    m.hold[side] = None
    return t + 0.1


def _back(m, t, dur=0.6):
    f = m.f
    f.L.add(t + dur, m.hand_target("L"))
    f.R.add(t + dur, m.hand_target("R"))
    f.lean.add(t + dur, 3)
    f.pitch.add(t + dur, 3)
    return t + dur


def one_hand(m, kind, side, t0, n, b, d=None, other=None):
    """n throws all from one hand (a fountain: thrown from the inside, caught
    on the outside), with what that hand holds; the other hand shows off
    (other: its pose). Returns when the last is caught and carried."""
    f = m.f
    IN, OUT = JUG[kind]
    if kind in BALLISH:                          # (one hand's loop is tighter than a cascade's)
        OUT = {k: IN[k] + 0.6 * (OUT[k] - IN[k]) for k in OUT}
    d = d if d is not None else (0.15 if kind in BALLISH else 0.20)
    H = m.holding[kind]
    mine = sorted([i for i, v in H.items() if v[0] == side], key=lambda i: H[i][1])
    k = len(mine)
    keys = f.L if side == "L" else f.R
    DF.hold_live(keys, t0 - 0.35)
    lift = V((0, 0, 0.03))
    order = [mine[i % k] for i in range(n)]
    last_catch = {}
    for i, o in enumerate(order):
        tt = t0 + i * b
        tc = tt + k * b - d
        m.prop(NAMES[kind][o], tt, ("fly", side, tt, side, tc, kind, 1 if kind not in BALLISH else 0), 0)
        m.prop(NAMES[kind][o], tc, hand_state(kind, side, 0), 0)
        last_catch[o] = tc
    for i in range(n + k):
        tt = t0 + i * b
        if i >= k:
            keys.add(tt - d, OUT[side] + lift)
        if i < n:
            keys.add(tt, IN[side].copy())
    end = max(last_catch.values())
    # The last ones caught sit beside the one caught before (slots).
    for j, o in enumerate(sorted(last_catch, key=lambda o: last_catch[o], reverse=True)):
        H[o] = (side, j)
        if j:
            m.prop(NAMES[kind][o], last_catch[o], hand_state(kind, side, j), 0)
    m.hold[side] = kind
    if other is not None:
        okeys = f.R if side == "L" else f.L
        okeys.hold(t0 - 0.6).add(t0 + 0.5, other.copy()).add(end, other.copy())   # (up slowly: it may have just caught)
    keys.add(end + 0.6, (CARRY if kind not in BALLISH else OUT)[side].copy())
    if other is not None:                       # (down from showing off: not a snatch)
        okeys.add(end + 1.0, (CARRY if kind not in BALLISH else OUT)[OTHER[side]].copy())
    return end + 1.4


def pass_over(m, kind, obj, frm, t, T=0.55):
    """One tossed across from one hand to the other."""
    f = m.f
    IN, OUT = JUG[kind]
    to = OTHER[frm]
    H = m.holding[kind]
    slot = sum(1 for v in H.values() if v[0] == to)
    fk, tk = (f.L if frm == "L" else f.R), (f.L if to == "L" else f.R)
    DF.hold_live(fk, t - 0.35)
    DF.hold_live(tk, t - 0.35)
    fk.add(t, IN[frm].copy())
    tk.add(t + T - 0.02, OUT[to].copy())
    m.prop(NAMES[kind][obj], t, ("fly", frm, t, to, t + T, kind, 1 if kind not in BALLISH else 0), 0)
    m.prop(NAMES[kind][obj], t + T, hand_state(kind, to, slot), 0)
    H[obj] = (to, slot)
    for side in (frm, to):
        mine = sorted([i for i, v in H.items() if v[0] == side], key=lambda i: H[i][1])
        for j, i in enumerate(mine):
            if H[i][1] != j:
                H[i] = (side, j)
                m.prop(NAMES[kind][i], t + T + 0.05, hand_state(kind, side, j), 4)
        m.hold[side] = kind if mine else None
    fk.add(t + T + 0.4, (CARRY if kind not in BALLISH else OUT)[frm].copy())
    tk.add(t + T + 0.4, (CARRY if kind not in BALLISH else OUT)[to].copy())
    return t + T + 0.4


def two_side(m, kind):
    """The hand holding two (cascades start from it)."""
    H = m.holding[kind]
    return "R" if sum(1 for v in H.values() if v[0] == "R") >= 2 else "L"


SHOW_OFF = {"L": V((-0.30, 0.30, 1.66)), "R": V((0.30, 0.30, 1.66))}      # the free hand up, palm out


def fin_box(m, t, t_bow):
    """Act 0, in the first light: the statue comes alive, finds himself in a
    glass box (walls, then the lid), finds the handle, steps out."""
    f = m.f
    t0 = t
    P = lambda x, y, z: V((x, y, z))
    f.pitch.add(t + 0.8, 3).add(t + 1.4, -8).add(t + 2.0, 4)           # eyes open
    f.L.add(t + 3.0, P(-0.16, 0.40, 1.36))
    f.R.add(t + 3.0, P(0.16, 0.40, 1.36))                               # palms flat on the glass
    f.L.add(t + 4.0, P(-0.26, 0.40, 1.18)).add(t + 5.0, P(-0.10, 0.40, 1.56))
    f.R.add(t + 4.0, P(0.08, 0.40, 1.52)).add(t + 5.0, P(0.26, 0.40, 1.22))
    f.yaw.add(t + 5.4, 40)
    f.L.add(t + 6.2, P(-0.42, 0.12, 1.36))
    f.R.add(t + 6.2, P(-0.30, 0.26, 1.46))                              # the wall on his left
    f.yaw.add(t + 7.2, -40)
    f.R.add(t + 8.0, P(0.42, 0.12, 1.36))
    f.L.add(t + 8.0, P(0.30, 0.26, 1.46))                               # and on his right
    f.yaw.add(t + 8.8, 0)
    f.L.add(t + 9.4, P(-0.16, 0.10, 1.98))
    f.R.add(t + 9.4, P(0.16, 0.10, 1.98))                               # the lid
    f.lean.add(t + 9.4, -4).add(t + 10.4, 8).add(t + 11.0, 3)
    f.L.add(t + 10.4, P(-0.16, 0.12, 1.88))
    f.R.add(t + 10.4, P(0.16, 0.12, 1.88))                              # it won't budge
    f.pitch.add(t + 10.4, -20).add(t + 11.2, 6)
    f.L.add(t + 11.4, HR["L"].copy())
    f.R.add(t + 11.6, P(0.22, 0.42, 1.10)).add(t + 12.2, P(0.25, 0.40, 1.08))   # a handle: he turns it
    f.R.add(t + 13.0, P(0.34, 0.20, 1.10))                                       # and pulls the door open
    fw = _fwd_xy(m.yaw)
    t = m.slide(t + 13.2, (FIN_SPOT[0] + 0.14 * fw.x, FIN_SPOT[1] + 0.14 * fw.y), 0.9)   # out of the box
    f.R.add(t + 0.2, HR["R"].copy())
    for q in range(3):                                                # shakes his hands out
        f.L.add(t + 0.4 + q * 0.3, P(-0.24, 0.20, 1.02 + 0.06 * (q % 2)))
        f.R.add(t + 0.4 + q * 0.3, P(0.24, 0.20, 1.02 + 0.06 * ((q + 1) % 2)))
    f.L.add(t + 1.5, HR["L"].copy())
    f.R.add(t + 1.5, HR["R"].copy())
    t = _land(m, t + 1.6, t_bow, "box")
    t = m.bow(t, 30, "pub")
    t = _step_to(m, t, FIN_SPOT, FIN_FACE)
    m.acts.append((t0, t, "box", "pub"))
    return t


_kd = V(FIN_SPOT) - V(RF.STAGE_TABLE)
KNIFE_AT = tuple(V(RF.STAGE_TABLE) + _kd.normalized() * 0.55)   # in front of his prop table, the block in reach


def fin_knives(m, t, t_bow):
    """Act 1: three knives out of the block on his table; juggled slow and
    high, fast, a flash with a pirouette; then one-handed, two in a hand while
    the other holds the third up in the light (both hands in turn); high again;
    back in the block."""
    f = m.f
    t0 = t
    hb = VENUES["pub"]["hb"]
    to_block = heading(KNIFE_AT, RF.STAGE_TABLE)
    t = m.turn(t, heading((m.x, m.y), KNIFE_AT))
    t = _step_to(m, t, KNIFE_AT, to_block)
    grip = lambda name: STAGE_REST[name][0] + V((0, 0, 0.04))
    # The middle one out with the right hand and over to the left, then the other two.
    t = _take_prop(m, t, "R", "Knife1", hand_state("knife", "R", 0), grip("Knife1"), lean=30, pitch=28)
    f.R.add(t + 0.6, V((0.04, 0.34, 1.08)))
    f.L.add(t + 0.6, V((-0.02, 0.32, 1.08)))
    m.prop("Knife1", t + 0.65, hand_state("knife", "L", 0), 4)
    t += 0.8
    f.L.add(t + 0.4, CARRY["L"].copy())
    t = _take_prop(m, t, "R", "Knife0", hand_state("knife", "R", 0), grip("Knife0"), lean=30, pitch=28)
    t = _take_prop(m, t, "R", "Knife2", hand_state("knife", "R", 1), grip("Knife2"), lean=30, pitch=28)
    m.holding["knife"] = {1: ("L", 0), 0: ("R", 0), 2: ("R", 1)}
    m.hold["L"] = m.hold["R"] = "knife"
    f.R.add(t + 0.5, CARRY["R"].copy())
    f.lean.add(t + 0.5, 3)
    f.pitch.add(t + 0.5, 3)
    t = m.turn(t + 0.5, heading(KNIFE_AT, FIN_SPOT))
    t = _step_to(m, t, FIN_SPOT, FIN_FACE)
    # The left one up into the light, turned so the blade flashes.
    f.L.add(t + 0.8, V((-0.22, 0.34, 1.72))).add(t + 2.6, V((-0.18, 0.36, 1.76)))
    f.pitch.add(t + 0.8, -18).add(t + 2.6, -18).add(t + 3.2, 10)
    f.yaw.add(t + 1.0, 18).add(t + 2.0, 10).add(t + 2.6, 0)
    f.L.add(t + 3.4, CARRY["L"].copy())
    t += 3.6
    t = cascade(m, "knife", t + 0.4, 12, 0.42 * hb, 0.22, style="high") + 0.5
    t = cascade(m, "knife", t, 24, 0.36) + 0.4
    t = flash(m, "knife", t + 0.4, T=VENUES["pub"]["flash"], b=0.24) + 0.5
    for q in range(2):                                   # one-handed: the hand with two, the other shows its knife
        side = two_side(m, "knife")
        f.pitch.add(t + 0.3, 10)
        t = one_hand(m, "knife", side, t + 0.6, 12, 0.42, 0.22, other=SHOW_OFF[OTHER[side]]) + 0.4
        t = cascade(m, "knife", t + 0.4, 15 if q == 0 else 9, 0.36) + 0.4
    t = cascade(m, "knife", t + 0.4, 10, 0.42 * hb, 0.22, style="high") + 0.5
    f.pitch.add(t, 3)
    # Back in the block.
    t = m.turn(t, heading((m.x, m.y), KNIFE_AT))
    t = _step_to(m, t, KNIFE_AT, to_block)
    H = m.holding["knife"]
    for side in ("R", "L"):
        for i in sorted([i for i, v in H.items() if v[0] == side], key=lambda i: -H[i][1]):
            t = _put_prop(m, t, side, NAMES["knife"][i], grip(NAMES["knife"][i]), lean=30, pitch=28)
            m.hold[side] = "knife" if any(v[0] == side and j != i for j, v in H.items()) else None
            del H[i]
            t = _back(m, t, 0.5)
    m.holding["knife"] = {}
    t = m.turn(t, heading(KNIFE_AT, FIN_SPOT))
    t = _step_to(m, t, FIN_SPOT, FIN_FACE)
    t = _land(m, t, t_bow, "knives")
    t = m.bow(t, 40, "pub")
    m.acts.append((t0, t, "knives", "pub"))
    return t


def fin_one_hand(m, t, t_bow):
    """Act 2: three balls out of his pockets and juggled with one hand, the
    other on his hip; then two in the left while the right holds one up."""
    f = m.f
    t0 = t
    t = m.appear_balls(t)
    f.pitch.add(t, 12)
    t = cascade(m, "ball", t + 0.2, 15, 0.30) + 0.3
    side = two_side(m, "ball")
    lone = next(i for i, v in m.holding["ball"].items() if v[0] != side)
    t = pass_over(m, "ball", lone, OTHER[side], t + 0.2)           # all three in one hand
    hip = {"L": V((-0.24, 0.02, 1.02)), "R": V((0.24, 0.02, 1.02))}
    t = one_hand(m, "ball", side, t + 0.4, 21, 0.30, 0.15, other=hip[OTHER[side]]) + 0.2
    for q in range(2):                                              # two over to the other hand
        mine = [i for i, v in m.holding["ball"].items() if v[0] == side]
        t = pass_over(m, "ball", mine[-1], side, t + 0.4)          # (after the last is carried)
        side_now = side
    t = one_hand(m, "ball", OTHER[side_now], t + 0.4, 12, 0.36, 0.18, other=SHOW_OFF[side_now]) + 0.2
    t = cascade(m, "ball", t + 0.3, 12, 0.30) + 0.3
    t = m.vanish_balls(t)
    f.pitch.add(t, 3)
    t = _land(m, t, t_bow, "one hand")
    t = m.bow(t, 35, "pub")
    m.acts.append((t0, t, "one hand", "pub"))
    return t


def _rola2_set(m, t):
    """The stage rola bola from the drapes, set up in front of his spot (he
    ends behind it). Returns (t, W, his spot behind it, its yaw)."""
    f = m.f
    pb, pt = STAGE_REST["Rola2Board"][0], STAGE_REST["Rola2Tube"][0]
    near = (-3.18, -10.86)
    t = _step_to(m, t, near, heading(near, (pt.x - 0.05, pt.y + 0.05)))
    DF.hold_live(f.R, t)
    DF.hold_live(f.L, t)
    f.R.add(t + 0.8, f.at_world(V((pb.x + 0.06, pb.y + 0.02, pb.z + 0.10))))
    f.L.add(t + 0.8, f.at_world(V((pt.x + 0.04, pt.y + 0.06, pt.z + 0.10))))
    f.lean.hold(t).add(t + 0.8, 30).add(t + 1.8, 4)
    f.pitch.hold(t).add(t + 0.8, 22).add(t + 1.8, 4)
    m.prop("Rola2Board", t + 0.85, ("hand", "R", np.array((0.02, 0.0, 0.0)), Q_BOARD_CARRY), 8)
    m.prop("Rola2Tube", t + 0.85, ("hand", "L", np.array((0.0, 0.0, 0.0)), Q_TUBE_CARRY), 8)
    m.hold["R"], m.hold["L"] = "rola", "rola"
    f.R.add(t + 1.8, V((0.24, 0.10, 0.95)))
    f.L.add(t + 1.8, V((-0.24, 0.10, 0.95)))
    t += 2.0
    fw = _fwd_xy(FIN_FACE)
    W2 = (FIN_SPOT[0] + ROLA2_W_OUT * fw.x, FIN_SPOT[1] + ROLA2_W_OUT * fw.y)
    behind = (W2[0] - ROLA2_BACK * fw.x, W2[1] - ROLA2_BACK * fw.y)
    t = _step_to(m, t, behind, FIN_FACE)
    W = V((W2[0], W2[1], floor_z(*W2)))
    U, PHI = Keys().add(0.0, 0.0), Keys().add(0.0, 0.0)
    m.rola = (U, PHI)
    m.rola2 = (W, FIN_FACE)
    f.L.add(t + 0.9, V((-0.05, 0.30, 0.40)))
    f.lean.add(t + 0.9, 46).add(t + 2.6, 46).add(t + 3.4, 4)
    f.pitch.add(t + 0.9, 30).add(t + 2.6, 30).add(t + 3.4, 4)
    m.prop("Rola2Tube", t + 0.95, ("fn", _rola_tube(W, FIN_FACE, U)), 6)
    f.L.add(t + 1.5, V((-0.24, 0.10, 0.95)))
    f.R.add(t + 1.4, V((0.08, 0.30, 0.50))).add(t + 2.3, V((0.08, 0.32, 0.48)))
    m.prop("Rola2Board", t + 2.3, ("fn", _rola_board(W, FIN_FACE, PHI)), 6)
    f.R.add(t + 3.0, HR["R"].copy())
    f.L.add(t + 3.0, HR["L"].copy())
    m.hold["R"], m.hold["L"] = None, None
    return t + 3.4, W, behind


def _rola2_away(m, t):
    """The stage rola bola back against the drapes."""
    f = m.f
    W, yaw = m.rola2
    pb, pt = STAGE_REST["Rola2Board"][0], STAGE_REST["Rola2Tube"][0]
    f.L.hold(t).add(t + 0.9, V((-0.05, 0.30, 0.40)))
    f.R.hold(t).add(t + 0.9, V((0.08, 0.32, 0.48)))
    f.lean.add(t + 0.9, 46).add(t + 1.8, 4)
    f.pitch.add(t + 0.9, 30).add(t + 1.8, 4)
    m.prop("Rola2Board", t + 0.95, ("hand", "R", np.array((0.02, 0.0, 0.0)), Q_BOARD_CARRY), 8)
    m.prop("Rola2Tube", t + 0.95, ("hand", "L", np.array((0.0, 0.0, 0.0)), Q_TUBE_CARRY), 8)
    m.hold["R"], m.hold["L"] = "rola", "rola"
    f.R.add(t + 1.8, V((0.24, 0.10, 0.95)))
    f.L.add(t + 1.8, V((-0.24, 0.10, 0.95)))
    t += 2.0
    near = (-3.18, -10.86)
    t = _step_to(m, t, near, heading(near, (pt.x - 0.05, pt.y + 0.05)))
    DF.hold_live(f.R, t)
    DF.hold_live(f.L, t)
    f.R.add(t + 0.8, f.at_world(V((pb.x + 0.06, pb.y + 0.02, pb.z + 0.10))))
    f.L.add(t + 0.8, f.at_world(V((pt.x + 0.04, pt.y + 0.06, pt.z + 0.10))))
    f.lean.add(t + 0.8, 30).add(t + 1.8, 4)
    f.pitch.add(t + 0.8, 22).add(t + 1.8, 4)
    m.prop("Rola2Board", t + 0.85, stage_rest("Rola2Board"), 8)
    m.prop("Rola2Tube", t + 0.85, stage_rest("Rola2Tube"), 8)
    m.hold["R"], m.hold["L"] = None, None
    f.R.add(t + 1.8, HR["R"].copy())
    f.L.add(t + 1.8, HR["L"].copy())
    t += 2.0
    t = _step_to(m, t, FIN_SPOT, FIN_FACE)
    return t


def fin_rola_fire(m, t, t_bow):
    """Act 3: the stage rola bola set up, the torches lit, and up he goes with
    fire in both hands: balanced, then three burning torches juggled on the
    board in the dark, a big wobble saved, a flash; down with a hop."""
    f = m.f
    t0 = t
    hb = VENUES["pub"]["hb"]
    t, W, behind = _rola2_set(m, t)
    t = light_torches(m, t)
    x0, y0, yaw0 = m.x, m.y, m.yaw
    U, PHI = m.rola
    # Up onto it, a torch in the left hand, two in the right, arms out.
    f.put(t, x0, y0, yaw0)
    f.zk.add(t, floor_z(x0, y0))
    f.fL.add(t, V(RF.STAND_FEET[0])).add(t + 0.6, V((-ROLA_FOOT, 0.10, 0.30)))
    f.fR.add(t, V(RF.STAND_FEET[1]))
    f.L.add(t + 0.8, V((-0.50, 0.10, 1.30)))
    f.R.add(t + 0.8, V((0.50, 0.10, 1.30)))
    f.put(t + 1.4, W.x, W.y, yaw0)
    f.zk.add(t + 1.4, W.z + ROLA_TOP)
    m.x, m.y = W.x, W.y
    t += 1.4
    U.add(t, 0.0)
    PHI.add(t, 0.0)
    f.fL.add(t, V((-ROLA_FOOT, 0.02, 0.09)))
    f.fR.add(t, V((ROLA_FOOT, 0.02, 0.09)))
    t = _rola_keys(m, t, t + 8.0, lambda tt: 0.05, flail=t + 3.5)
    f.L.add(t + 0.9, CARRY["L"].copy())                    # arms in, torches ready
    f.R.add(t + 0.9, CARRY["R"].copy())
    tj = t
    t = cascade(m, "torch", t + 1.6, 12, 0.44 * hb, 0.24, style="high") + 0.5
    t = cascade(m, "torch", t, 30, 0.36) + 0.4
    t = flash(m, "torch", t + 0.4, T=VENUES["pub"]["flash"], pirouette=False) + 0.5
    FIN = 0.4 + 12 * 0.38 + 0.5 + 8.0 + 1.6 + 2.4
    t = fill(m, "torch", t, t_bow - FIN, 0.36)
    t = cascade(m, "torch", t + 0.4, 12, 0.44 * hb, 0.24, style="high") + 0.5
    amp = lambda tt: 0.022 + 0.020 * math.sin(0.35 * (tt - tj)) ** 2
    _rola_keys(m, tj, t, amp, arms=False)
    f.pitch.add(t, 3)
    t = _rola_keys(m, t + 0.6, t + 6.0, 0.04, flail=t + 3.0)       # arms out again, a last big wobble
    U.add(t + 0.1, 0.0)
    PHI.add(t + 0.1, 0.0)
    f.put(t, m.x, m.y, yaw0)
    f.zk.add(t, W.z + ROLA_TOP).add(t + 0.5, W.z + ROLA_TOP + 0.12).add(t + 1.2, floor_z(x0, y0))
    f.put(t + 1.2, x0, y0, yaw0)
    m.x, m.y = x0, y0
    f.fL.add(t + 1.2, V(RF.STAND_FEET[0]))
    f.fR.add(t + 1.2, V(RF.STAND_FEET[1]))
    f.L.add(t + 1.2, CARRY["L"].copy())
    f.R.add(t + 1.2, CARRY["R"].copy())
    f.lean.add(t + 1.2, 3)
    t += 1.4
    t = _land(m, t, t_bow, "rola fire")
    t = m.bow(t, 30, "pub", hat=False)
    m.acts.append((t0, t, "rola fire", "pub"))
    return t


def _fireball(t0, side, T=1.3, up=6.0):
    """A breath of fire: from his mouth through the torch flame, out over the
    room and up a little, swelling and gone."""
    def fn(fis, C):
        f0 = C["fi"](t0)
        qb0 = C["qb"][f0]
        mouth = C["pos"][f0] + DF.qrot(qb0, (0.0, 0.16, 1.50))
        a = math.radians(up)
        d = DF.qrot(qb0, (0.0, math.cos(a), math.sin(a)))
        u = np.clip((fis / FPS - t0) / T, 0.0, 1.0)[:, None]
        reach = 0.25 + 1.30 * (1.0 - (1.0 - u) ** 2)
        P = mouth + d * reach
        grow = np.minimum(1.0, u / 0.35)
        fade = np.clip((1.0 - u) / 0.35, 0.0, 1.0)
        k = (0.6 + 2.6 * grow) * fade
        S = np.concatenate([k * 1.15, k * 1.15, k * 0.95], 1)
        Q = DF.qmul(DF.qyaw(C["yaw"][fis]), DF.qx(-80.0 + 0 * u[:, 0]))      # flame lying along the breath
        return P, Q, np.maximum(S, 0.001)
    return fn


def fin_fire_eat(m, t, t_bow):
    """Act 4: a torch's flame put out in his mouth, the torch lit again from
    another; two breaths of fire over the room; the torches blown out."""
    f = m.f
    t0 = t
    H = m.holding["torch"]
    if sum(1 for v in H.values() if v[0] == "R") >= 2:              # one in the right hand, two in the left
        mine = sorted([i for i, v in H.items() if v[0] == "R"], key=lambda i: H[i][1])
        t = pass_over(m, "torch", mine[-1], "R", t + 0.2, T=0.6)
    ir = next(i for i, v in H.items() if v[0] == "R")
    il = sorted([i for i, v in H.items() if v[0] == "L"], key=lambda i: H[i][1])
    name = NAMES["torch"][ir]
    fw = _fwd_xy(FIN_FACE)
    t = _step_to(m, t, (FIN_SPOT[0] - 0.10 * fw.x, FIN_SPOT[1] - 0.10 * fw.y), FIN_FACE)
    # Eaten: head back, the torch over his face, the flame down into his mouth.
    f.pitch.add(t + 0.4, 3).add(t + 1.4, -38)
    f.lean.add(t + 1.4, -8)
    palm = MOUTH_UP + V((0.0, 0.10, 0.37))
    f.R.add(t + 1.0, V((0.10, 0.30, 1.70))).add(t + 1.8, palm).add(t + 2.6, palm)
    m.prop(name, t + 1.0, ("hand", "R", np.array((0.0, 0.0, 0.0)), Q_EAT), 8)
    m.lit[ir].add(t + 2.0, 1.0).add(t + 2.4, 0.0)
    f.R.add(t + 3.4, V((0.26, 0.36, 1.40)))
    m.prop(name, t + 3.2, hand_state("torch", "R", 0), 8)
    f.pitch.add(t + 3.4, 6).add(t + 4.0, -6).add(t + 4.6, 4)             # a smile to the crowd
    f.lean.add(t + 3.4, 3)
    t += 4.8
    # Lit again from one in the left hand, heads together.
    f.L.add(t + 0.8, V((-0.06, 0.36, 1.26))).add(t + 1.8, V((-0.06, 0.36, 1.26)))
    f.R.add(t + 0.8, V((0.06, 0.36, 1.26))).add(t + 1.8, V((0.06, 0.36, 1.26)))
    m.lit[ir].add(t + 1.0, 0.0).add(t + 1.5, 1.0)
    f.L.add(t + 2.4, CARRY["L"].copy())
    f.R.add(t + 2.4, CARRY["R"].copy())
    t += 2.6
    m.breaths = getattr(m, "breaths", [])
    for q in range(2):                                              # fire breathing
        f.R.add(t + 0.8, V((0.05, 0.43, 1.19)))                      # the flame just in front of his mouth
        m.prop(name, t + 0.8, ("hand", "R", np.array((0.0, 0.0, 0.0)), DF.qx(-20.0)), 8)
        f.pitch.add(t + 0.8, -10).add(t + 1.6, -14)
        f.lean.add(t + 1.2, -6).add(t + 1.8, 8).add(t + 3.2, 3)
        tb = t + 1.8
        m.prop("FireBall", tb, ("fn", _fireball(tb, "R")), 0)
        m.prop("FireBall", tb + 1.3, ("hide",), 0)
        m.breaths.append(tb)
        f.pitch.add(tb + 0.2, 4).add(tb + 1.4, 4)
        f.R.add(t + 3.4, CARRY["R"].copy())
        m.prop(name, t + 3.2, hand_state("torch", "R", 0), 8)
        f.pitch.add(t + 3.6, 3)
        t += 4.4
    t = blow_out(m, t)
    t = sheath3(m, t, "torch")
    t = _land(m, t, t_bow, "fire eating")
    t = m.bow(t, 45, "pub")
    t = _rola2_away(m, t)
    m.acts.append((t0, t, "fire", "pub"))
    return t


def prod_silks(m, t):
    """The gift, its making (one night's way): silks out of his fist, then a
    bouquet out of the air. Ends with the bouquet in his right hand."""
    f = m.f
    fist = V((-0.05, 0.32, 1.24))
    f.L.add(t + 0.7, fist.copy())
    f.R.add(t + 0.7, fist + V((0.06, 0.0, 0.03)))
    pulls = [(t + 1.6, (0.14, 0.34, 1.42)), (t + 3.0, (0.22, 0.34, 1.58)), (t + 4.4, (0.30, 0.34, 1.74)),
             (t + 5.8, (0.34, 0.30, 1.86))]
    for tt, p in pulls:
        f.R.add(tt, V(p))
    m.silk_out.add(t + 0.9, 0.0).add(t + 5.8, 6.0)
    for i in range(6):
        m.prop(f"Silk{i}", t + 0.9, ("fn", _silk(i)), 0)
    f.pitch.add(t + 3.0, -10).add(t + 5.8, -18)
    t += 5.8
    for q in range(3):
        f.R.add(t + 0.6, V((0.10, 0.32, 1.86))).add(t + 1.2, V((0.40, 0.30, 1.80)))
        t += 1.2
    f.R.add(t + 1.0, fist + V((0.04, 0.0, 0.10)))
    f.pitch.add(t + 1.0, 8)
    m.silk_out.add(t + 1.0, 6.0).add(t + 3.4, 0.0)
    f.R.add(t + 3.4, fist + V((0.03, 0.0, 0.05)))
    for i in range(6):
        m.prop(f"Silk{i}", t + 3.5, ("hide",), 0)
    f.L.add(t + 4.2, V((-0.30, 0.34, 1.36)))
    f.R.add(t + 4.2, V((0.30, 0.34, 1.36)))
    t += 4.6
    # The bouquet out of the air.
    f.R.add(t + 0.8, V((0.36, 0.20, 1.70))).add(t + 1.4, V((0.22, 0.42, 1.38)))
    f.L.add(t + 0.8, HR["L"].copy())
    m.prop("Bouquet", t + 1.4, ("hand", "R", np.array((0.0, 0.0, 0.02)), Q_ID), 0)
    m.scale("Bouquet", t + 1.4, 0.001, t + 1.8, 1.0)
    m.hold["R"] = "bouquet"
    return t + 2.0


GIFT_LEAVE = 381.0                                   # finale seconds: he sets off to the café lady, every night
GIFT_HOLD = V((0.22, 0.42, 1.38))                    # (the bouquet held out while he waits for it)


def gift_walk(m, t, t_bow):
    """Every night the same: the bouquet in his right hand on his spot, down
    off the stage to the café lady at GIFT_LEAVE (her part is in the one
    dinner clip): she takes it, smells it and sets it down; back up for his bow."""
    f = m.f
    t0 = t
    t_go = m.F0 + GIFT_LEAVE
    if t > t_go - 1.2:
        m.late.append(("gift", round(t - (t_go - 1.2), 1)))
    t = _step_to(m, t, FIN_SPOT)
    t = m.turn(t, FIN_FACE)
    m.stay(t)
    f.R.hold(t).add(t_go - 1.4, GIFT_HOLD.copy())
    f.L.hold(t).add(t_go - 1.4, HR["L"].copy())
    lady = RF.CAB_SEATS["A"][:2]
    m.look_at(t_go - 1.4, lady)
    t = t_go
    m.stay(t)
    t = m.leg(t, [(m.x, m.y)] + GIFT_WAY, "gift_to")
    t = m.face(t, (lady[0], lady[1] + 0.05))
    # Offered low, with a bow; she takes it.
    f.lean.hold(t).add(t + 1.2, 26)
    f.pitch.hold(t).add(t + 1.2, 18)
    f.R.hold(t).add(t + 1.2, f.at_world(GIFT_HAND))
    t_offer = t + 1.2
    t_take = t_offer + 1.6
    m.prop("Bouquet", t_take, ("hand2", TAGS["A"], "L", np.array((0.0, 0.0, 0.02)), Q_ID), 6)
    m.hold["R"] = None
    m.gift = (t_offer, t_take)
    f.R.add(t_take + 0.6, V((0.10, 0.30, 1.30)))                       # hand on his heart
    f.lean.add(t_take + 0.8, 34).add(t_take + 2.2, 34).add(t_take + 3.0, 3)
    f.pitch.add(t_take + 3.0, 3)
    f.R.add(t_take + 3.0, HR["R"].copy())
    t = t_take + 3.2
    m.bouquet_down = t_take + 6.0                                     # (she sets it on the table)
    t = m.leg(t, [(m.x, m.y)] + list(reversed(GIFT_WAY[:-1])) + [FIN_SPOT], "gift_back")
    t = m.turn(t, FIN_FACE)
    t = _land(m, t, t_bow, "bouquet")
    t = m.bow(t, 45, "pub")
    m.acts.append((t0, t, "bouquet", "pub"))
    return t


def bouquet_props(m):
    """Her side of it in his prop rig: the bouquet down on their table."""
    m.prop("Bouquet", m.bouquet_down, bouquet_down(), 6)


def _wand_tip(C, side, fis, q_hold=Q_WAND):
    """World position of a wand's string end in his hand."""
    qb = C["qb"][fis]
    return C["palm"][side][fis] + DF.qrot(DF.qmul(qb, q_hold), (0.0, 0.0, 0.43))


def _giant(t_open, t_close, life, drift, seed, big=1.0, lift=None):
    """A giant bubble between the two wand tips: it fills as he opens the
    string loop, comes free as he closes it, then floats off wobbling over
    the room (drift: m/s, his frame) and pops. lift: (t0, t1) he raises it
    first on the wand ends."""
    rs = random.Random(seed)
    ph = rs.uniform(0, 6.28)

    def fn(fis, C):
        tt = fis / FPS
        tl, tr = _wand_tip(C, "L", fis), _wand_tip(C, "R", fis)
        mid = 0.5 * (tl + tr)
        span = np.linalg.norm(tl - tr, axis=1)
        u = np.clip((tt - t_open) / max(0.1, t_close - t_open), 0.0, 1.0)
        grow = (0.25 + 0.75 * u) * big
        f_c = C["fi"](t_close)
        qb = C["qb"][f_c]
        c0 = mid[np.searchsorted(fis, f_c)] if f_c in fis else _wand_mid(C, f_c)
        P = mid + np.array((0.0, 0.0, -0.20)) * grow[:, None]
        rx = 0.5 * span
        ry = 0.22 * grow
        rz = 0.30 * grow
        free = tt >= t_close
        if free.any():
            dt = (tt - t_close)[free]
            dv = DF.qrot(qb, drift)
            r0 = 0.55 * big
            P[free] = c0 + np.array((0.0, 0.0, -0.20 * big)) + np.outer(dt, dv) + \
                np.stack([0.03 * np.sin(1.7 * dt + ph), 0.03 * np.cos(1.3 * dt + ph), 0.04 * np.sin(2.1 * dt)], 1)
            wob = 1.0 + 0.10 * np.sin(5.0 * dt + ph)
            settle = np.minimum(1.0, dt / 1.2)[:, None]
            start = np.stack([rx[free], ry[free], rz[free]], 1)
            sph = np.stack([r0 * wob, r0 / wob, r0 * (2.0 - wob)], 1)
            R = start + (sph - start) * settle
            pop = np.clip((t_close + life - tt[free]) / 0.15, 0.0, 1.0)[:, None]
            R = R * pop
            top = P[free][:, 2] + R[:, 2]
            P[free, 2] -= np.maximum(0.0, top - 3.12)                # (under the ceiling)
            S = np.empty((len(fis), 3))
            S[~free] = np.stack([rx, ry, rz], 1)[~free]
            S[free] = R
        else:
            S = np.stack([rx, ry, rz], 1)
        Q = DF.qmul(DF.qyaw(C["yaw"][fis]), np.tile(Q_ID, (len(fis), 1)))
        return P, Q, np.maximum(S, 0.001)
    return fn


def _wand_mid(C, fi):
    fis = np.array([fi])
    return (0.5 * (_wand_tip(C, "L", fis) + _wand_tip(C, "R", fis)))[0]


def _small_bubble(i, ts, side, seed, spin=0.0):
    """A small bubble blown off the ring wand at ts: it drifts out over the
    room, rising a little and wobbling, and pops."""
    rs = random.Random(seed)
    v = np.array((rs.uniform(-0.22, 0.22), rs.uniform(0.30, 0.55), rs.uniform(0.02, 0.16)))
    r = rs.uniform(0.028, 0.06)
    life = rs.uniform(3.5, 8.5)
    ph = rs.uniform(0, 6.28)

    def fn(fis, C):
        f0 = C["fi"](ts)
        qb0 = C["qb"][f0]
        ring = C["palm"][side][f0] + DF.qrot(DF.qmul(qb0, Q_WAND), (0.0, 0.0, 0.225))
        tt = fis / FPS - ts
        vw = DF.qrot(DF.qmul(qb0, DF.qyaw(spin)), v)
        drag = np.minimum(tt, 1.0) + np.maximum(tt - 1.0, 0) * 0.55
        P = ring + np.outer(drag, vw) + np.stack([0.02 * np.sin(2.3 * tt + ph), 0.02 * np.cos(1.9 * tt + ph),
                                                 0.015 * np.sin(1.4 * tt)], 1)
        P[:, 2] = np.minimum(P[:, 2], 3.10)
        grow = np.clip(tt / 0.25, 0.2, 1.0)
        pop = np.clip((life - tt) / 0.12, 0.0, 1.0)
        k = r * grow * pop * (1.0 + 0.06 * np.sin(6.0 * tt + ph))
        return P, np.tile(Q_ID, (len(fis), 1)), np.maximum(k, 0.001)
    return fn, life


def fin_bubbles(m, t, t_bow):
    """Act 6, the last: the string wand out of the bucket, giant bubbles drawn
    off it to float out over the room; the ring wand, a stream of small
    bubbles into the light, then a spin and a swirl of them; the biggest giant
    of all raised up into the spotlight, and it pops on his bow."""
    f = m.f
    t0 = t
    bucket = V((RF.BUCKET[0], RF.BUCKET[1], RF.BUCKET_TOP))
    at_bucket = (-3.22, -10.72)
    face_b = heading(at_bucket, RF.BUCKET)
    t = _step_to(m, t, at_bucket, face_b)
    grip = lambda name: STAGE_REST[name][0] + V((0, 0, 0.02))
    t = _take_prop(m, t, "L", "WandL", ("hand", "L", np.zeros(3), Q_WAND), grip("WandL"), lean=36, pitch=30)
    t = _take_prop(m, t, "R", "WandR", ("hand", "R", np.zeros(3), Q_WAND), grip("WandR"), lean=36, pitch=30)
    m.hold["L"] = m.hold["R"] = "wand"
    f.L.add(t + 0.6, V((-0.10, 0.30, 1.05)))
    f.R.add(t + 0.6, V((0.10, 0.30, 1.05)))
    f.lean.add(t + 0.6, 4)
    f.pitch.add(t + 0.6, 6)
    t += 0.8
    drifts = ((0.05, 0.42, 0.04), (-0.18, 0.38, 0.05), (0.20, 0.36, 0.03))
    for g in range(2):
        t = _step_to(m, t, FIN_SPOT, FIN_FACE)
        f.L.add(t + 1.8, V((-0.48, 0.42, 1.28)))                  # the loop opened: the bubble fills
        f.R.add(t + 1.8, V((0.48, 0.42, 1.28)))
        f.lean.add(t + 1.8, 6)
        f.pitch.add(t + 1.0, -4)
        t_open = t + 0.6
        f.L.add(t + 3.6, V((-0.50, 0.50, 1.22)))                  # drawn forward through the air
        f.R.add(t + 3.6, V((0.50, 0.50, 1.22)))
        t_close = t + 4.6
        f.L.add(t_close, V((-0.06, 0.52, 1.14)))                   # closed: it comes free
        f.R.add(t_close, V((0.06, 0.52, 1.14)))
        life = 7.5 + 1.5 * g
        m.prop(GIANTS[g], t_open, ("fn", _giant(t_open, t_close, life, drifts[g], f"giant{g}")), 0)
        m.prop(GIANTS[g], t_close + life + 0.2, ("hide",), 0)
        m.look_at(t_close + 0.4, (FIN_SPOT[0] + 2.0, FIN_SPOT[1] - 1.6))
        f.pitch.add(t_close + 1.5, -12).add(t_close + 4.0, -6)
        f.L.add(t_close + 1.0, V((-0.12, 0.30, 1.10)))
        f.R.add(t_close + 1.0, V((0.12, 0.30, 1.10)))
        t = t_close + 4.5
        f.yaw.add(t, 0)
        f.pitch.add(t, 4)
        t = _step_to(m, t, at_bucket, face_b)                       # dipped again
        DF.hold_live(f.L, t)
        DF.hold_live(f.R, t)
        f.L.add(t + 1.3, f.at_world(bucket + V((-0.06, 0.0, 0.22))))
        f.R.add(t + 1.3, f.at_world(bucket + V((0.06, 0.0, 0.22))))
        f.lean.add(t + 1.3, 38).add(t + 2.6, 4)
        f.pitch.add(t + 1.3, 30).add(t + 2.6, 6)
        f.L.add(t + 2.6, V((-0.10, 0.30, 1.05)))
        f.R.add(t + 2.6, V((0.10, 0.30, 1.05)))
        t += 2.8
    # The string wand back in the bucket; the ring wand out.
    t = _put_prop(m, t, "L", "WandL", grip("WandL"), lean=36, pitch=30)
    t = _put_prop(m, t, "R", "WandR", grip("WandR"), lean=36, pitch=30)
    t = _take_prop(m, t, "R", "WandS", ("hand", "R", np.zeros(3), Q_WAND), grip("WandS"), lean=36, pitch=30)
    m.hold["R"] = "wand"
    t = _back(m, t)
    t = _step_to(m, t, FIN_SPOT, FIN_FACE)
    k = 0
    for blow in range(2):
        f.R.add(t + 0.8, V((0.02, 0.36, 1.52)))                     # the ring before his lips
        f.pitch.add(t + 0.8, -2)
        f.lean.add(t + 1.0, -4).add(t + 3.6, 6)
        tb = t + 1.2
        turn = 0.0
        if blow == 1:                                               # the second with a slow spin
            f.put(tb, m.x, m.y, m.yaw, lin=True)
            f.root.add(tb + 1.6, V((m.x, m.y, m.yaw + 180.0)), True)
            f.root.add(tb + 3.2, V((m.x, m.y, m.yaw + 360.0)))
            f._yaw = m.yaw = m.yaw + 360.0
            f.R.add(tb + 1.0, V((0.30, 0.42, 1.44))).add(tb + 2.2, V((0.36, 0.30, 1.56)))
        for j in range(12):
            ts = tb + 0.22 * j
            name = BUBBLES[k]
            fn, life = _small_bubble(k, ts, "R", f"bubble{k}", spin=0.0)
            m.prop(name, ts, ("fn", fn), 0)
            m.prop(name, ts + life + 0.1, ("hide",), 0)
            k += 1
        f.R.add(tb + 3.4, V((0.20, 0.32, 1.20)))
        f.pitch.add(tb + 3.6, -8)
        m.look_at(tb + 3.8, (FIN_SPOT[0] + 1.8, FIN_SPOT[1] - 1.8))
        t = tb + 7.0
        f.yaw.add(t, 0)
        f.pitch.add(t, 4)
    t = _step_to(m, t, at_bucket, face_b)
    t = _put_prop(m, t, "R", "WandS", grip("WandS"), lean=36, pitch=30)
    # The biggest of all: drawn, then lifted high on the wand ends, let go
    # into the spotlight; it floats over him and pops as he bows.
    t = _take_prop(m, t, "L", "WandL", ("hand", "L", np.zeros(3), Q_WAND), grip("WandL"), lean=36, pitch=30)
    t = _take_prop(m, t, "R", "WandR", ("hand", "R", np.zeros(3), Q_WAND), grip("WandR"), lean=36, pitch=30)
    m.hold["L"] = m.hold["R"] = "wand"
    f.L.add(t + 0.6, V((-0.10, 0.30, 1.05)))
    f.R.add(t + 0.6, V((0.10, 0.30, 1.05)))
    t += 0.8
    t = _step_to(m, t, FIN_SPOT, FIN_FACE)
    t_open = t + 0.6
    f.L.add(t + 2.4, V((-0.56, 0.40, 1.30)))
    f.R.add(t + 2.4, V((0.56, 0.40, 1.30)))
    f.L.add(t + 4.6, V((-0.52, 0.30, 1.86)))                      # raised up into the light
    f.R.add(t + 4.6, V((0.52, 0.30, 1.86)))
    f.pitch.add(t + 3.0, -20).add(t + 5.6, -30)
    t_close = t + 5.4
    f.L.add(t_close, V((-0.08, 0.28, 1.92)))
    f.R.add(t_close, V((0.08, 0.28, 1.92)))
    life = max(3.0, t_bow + 0.3 - t_close)
    m.prop(GIANTS[2], t_open, ("fn", _giant(t_open, t_close, life, (0.0, 0.05, 0.02), "giant2", big=1.25)), 0)
    m.prop(GIANTS[2], t_close + life + 0.2, ("hide",), 0)
    f.L.add(t_close + 1.0, V((-0.36, 0.20, 1.40)))
    f.R.add(t_close + 1.0, V((0.36, 0.20, 1.40)))
    t = _land(m, t_close + 1.2, t_bow, "bubbles")
    t = m.bow(t, 55, "pub", hat=False)
    m.acts.append((t0, t, "bubbles", "pub"))
    return t


def tidy_wands(m, t):
    """(The bubbles night) the string wands back in the bucket."""
    at_bucket = (-3.22, -10.72)
    t = _step_to(m, t, at_bucket, heading(at_bucket, RF.BUCKET))
    grip = lambda name: STAGE_REST[name][0] + V((0, 0, 0.02))
    t = _put_prop(m, t, "L", "WandL", grip("WandL"), dur=1.3, lean=36, pitch=30)
    t = _put_prop(m, t, "R", "WandR", grip("WandR"), dur=1.3, lean=36, pitch=30)
    return _back(m, t, 1.0)


def fin_ovation(m, t, F0, tidy=None):
    """The ovation: bows to each side of the room, the night's kit put away,
    the lights up, a last hat-tip bow (every night ending at the same moment)."""
    f = m.f
    for k in (0, 1):
        t = _side(m, t, "pub", k)
        t = m.bow(t, 35, "pub", hat=False)
    t = _side(m, t, "pub", None)
    if tidy is not None:
        t = tidy(m, t)
    t = _step_to(m, t, FIN_SPOT, FIN_FACE)
    t_up = F0 + LIGHTS_UP[1] - 1.0
    if t > t_up:
        m.late.append(("ovation", round(t - t_up, 1)))
    t = max(t, t_up)
    m.stay(t)
    t = m.bow(t, 60, "pub")                                          # the hat, in the house lights
    return t


# The night's programme (Jay: a different big show every night of the week):
# seven numbers, each landing its bow on the regulars' marks (FINALE_BOWS), the
# sixth the gift (its making, then gift_walk), and what the ovation puts away.
NIGHTS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
BASE_NIGHT = "fri"                                    # the one the dinner is planned and solved with
PROGRAMS = {}


def _programme(night):
    if night in PROGRAMS:
        return PROGRAMS[night]
    return ((fin_box, fin_knives, fin_one_hand, fin_rola_fire, fin_fire_eat, prod_silks, fin_bubbles), tidy_wands)


def finale(m, cr, F0, t, rng, night=BASE_NIGHT):
    """The whole finale, from F0 (he is waiting upstage in the dark from t)."""
    f = m.f
    m.F0 = F0
    m.night = night
    B = [F0 + b for b in RF.FINALE_BOWS]
    t_spot = F0 + BEAM_ON
    # Lights.
    m.dim.add(F0 + LIGHTS_DOWN[0], 0.001).add(F0 + LIGHTS_DOWN[1], 1.0)
    m.dim.add(F0 + LIGHTS_UP[0], 1.0).add(F0 + LIGHTS_UP[1], 0.001)
    m.beam.add(t_spot - 0.01, 0.0).add(t_spot + 0.3, 1.0)
    m.beam.add(F0 + BEAM_OFF[0], 1.0).add(F0 + BEAM_OFF[1], 0.0)
    # Into the light: a few steps down from his table to centre stage, frozen.
    m.stay(t)
    t = max(t, t_spot - 6.0)
    t = _step_to(m, t, FIN_SPOT, FIN_FACE, 1.6)
    f.L.add(t + 0.8, V((-0.34, 0.18, 1.42)))
    f.R.add(t + 0.8, V((0.12, 0.30, 1.72)))                         # the statue's pose
    f.lean.add(t + 0.8, 6)
    f.pitch.add(t + 0.8, -10)
    m.stay(t_spot + 0.6)
    for k in (f.fL, f.fR, f.zk, f.twist, f.yaw, f.lean):    # (every night the same up to here)
        k.hold(t_spot + 0.6)
    f.L.add(t_spot + 0.6, V((-0.34, 0.18, 1.42)))
    f.R.add(t_spot + 0.6, V((0.12, 0.30, 1.72)))
    f.pitch.add(t_spot + 0.6, -10)
    m.audience.append((F0, F0 + RF.FINALE_WATCH[1], "pub", None))
    acts, tidy = _programme(night)
    t = acts[0](m, t_spot + 0.6, B[0])
    for k in (1, 2, 3, 4):
        t = acts[k](m, t + 0.4, B[k])
    t = acts[5](m, t + 0.4)
    t = gift_walk(m, t, B[5])
    t = acts[6](m, t + 0.4, B[6])
    t = fin_ovation(m, t, F0, tidy)
    return t


# --- Schedules ----------------------------------------------------------------------
def leg_at(m, t):
    """The leg to hold back for a clash at t: the one under way, or else the
    last one before it (holding it back moves everything after)."""
    best = None
    for t0, t1, name in getattr(m, "legs", []):
        if t0 - 0.5 <= t:
            if best is None or t0 >= best[0]:
                best = (t0, name)
    return best[1] if best else None


def _walk_len(pts):
    return sum((V(b) - V(a)).length for a, b in zip(pts, pts[1:])) + 0.6 * len(pts)


def do_act(m, t, venue, act, t_end, cr, rng):
    if act == "house":
        return house_ride(m, t, f"h{int(t)}", t_end)
    if act == "rola":
        return act_rola(m, t, venue, t_end)
    if act == "magic":
        look = (cr.couple["A"].x, cr.couple["A"].y) if venue == "cafe" else None
        return act_magic(m, t, venue, t_end, look)
    if act == "balls" and venue == "cafe" and t_end is None:
        return num_balls_cafe(m, t, rng)
    return {"clubs": act_clubs, "torches": act_torches, "balls": act_balls}[act](m, t, venue, t_end)


def hold_until(m, t, t_go, venue):
    """Ready on his spot: wait for his mark (shaking out his hands), or note
    how late he is."""
    if t > t_go + 0.05:
        m.late.append((venue, round(t - t_go, 1)))
        return t
    f = m.f
    m.stay(t)
    if t_go - t > 2.5:
        f.L.hold(t).add(t + 0.6, V((-0.24, 0.20, 1.05))).add(t_go - 0.8, V((-0.24, 0.20, 1.05)))
        f.R.hold(t).add(t + 0.6, V((0.24, 0.20, 1.05))).add(t_go - 0.8, V((0.24, 0.20, 1.05)))
        f.L.add(t_go, m.hand_target("L"))
        f.R.add(t_go, m.hand_target("R"))
    m.stay(t_go)
    return t_go


# Every PHASE seconds, from the end of the dinner's linger on (the Rovers
# regulars' time then is ours modulo PHASE), one round: an act at the café, an
# act in the Rovers and one at the hot tub at fixed marks (rovers_figures.SHOW:
# the regulars watch then), riding between. The four rounds of the lounge loop
# turn the acts round so every audience sees all three (and the rola bola).
CYCLE = DF.PHASE
LOUNGE_ACTS = (("rola", "torches", ("tub", "magic")), ("magic", "clubs", ("tub", "torches")),
               ("torches", "magic", ("tub", "clubs")), ("house", "torches", ("tub", "balls")))
# The dinner: the same rounds from its first second (the client starts the
# session on the regulars' beat), the head of the dinner table in place of the
# hot tub three times while the table is laid.
DIN_ACTS = (("rola", "torches", ("tub", "magic")), ("clubs", "clubs", ("dining", "torches")),
            ("house", "magic", ("dining", "clubs")), ("torches", "torches", ("tub", "torches")),
            ("magic", "clubs", ("dining", "balls")), ("clubs", "magic", ("tub", "clubs")),
            ("house", "torches", ("tub", "magic")), ("rola", "clubs", ("tub", "torches")),
            ("balls", "magic", ("tub", "clubs")))
DINING_END = 330.0                                 # his act at the dinner table ends by here (into the round)
T_TO_PUB = 28.0                                    # café act's end -> on his spot in the Rovers
MIN_ACT = {"clubs": 62.0, "torches": 72.0, "magic": 83.0, "balls": 55.0, "rola": 80.0, "house": 72.0}


def cycle(m, c0, t, acts, n, cr, rng, last=False):
    """One round, its start (phase 0: on the café stage) at c0; he is on the
    café stage at t. acts: (café act, Rovers act, (where, act) after the
    Rovers: the hot tub at its mark, or the head of the dinner table). Ends
    back on the café stage: before c0 + CYCLE from the tub; a little into the
    next round from the dinner table (its café act is shorter for it)."""
    cafe, pub, (where, act_last) = acts
    S_pub, S_tub = RF.SHOW["pub"], RF.SHOW["tub"]
    end_cafe = c0 + S_pub[0] - T_TO_PUB
    if end_cafe - t >= MIN_ACT[cafe]:
        t = do_act(m, t, "cafe", cafe, end_cafe, cr, rng)
    elif end_cafe - t > 16.0:
        t = walkabout(m, t, end_cafe, rng)
    t = to_pub(m, t, f"c{n}")
    t = hold_until(m, t, c0 + S_pub[0], "pub")
    t = do_act(m, t, "pub", pub, c0 + S_pub[1], cr, rng)
    if where == "dining":
        t = pub_to_dining(m, t, f"c{n}")
        t = do_act(m, t, "dining", act_last, max(t + MIN_ACT[act_last], c0 + DINING_END), cr, rng)
        return from_dining(m, t, f"c{n}")
    t = pub_to_tub(m, t, f"c{n}")
    t = hold_until(m, t, c0 + S_tub[0], "tub")
    t = do_act(m, t, "tub", act_last, c0 + S_tub[1], cr, rng)
    if last:                                         # (the finale is next: back to the Rovers' stage)
        t = tub_to_pub(m, t, f"c{n}")
        m.overrun = max(m.overrun, t - (c0 + CYCLE - 1.0))
        return t
    t = tub_to_cafe(m, t, f"c{n}")
    m.overrun = max(m.overrun, t - (c0 + CYCLE - 1.6))
    return t


def pub_acts(m):
    """(t0, t1) of every act in the Rovers."""
    return [(a, b) for a, b, _n, v in m.acts if v == "pub"]


def add_actors(cr, dues, lounge=False):
    """The mime and the café couple; in the lounge loop (after the finale) he
    starts at the front of the stage and they at their table in the Rovers."""
    cr.mime = Mime(DF.LOOP, (MINGLE_HOME[0], MINGLE_HOME[1], FIN_FACE) if lounge else None)
    if lounge:
        cr.mime.prop("Bouquet", 0.0, bouquet_down(), 0)
    cr.couple = {w: Patron(w, DF.LOOP, "rovers" if lounge else "cafe") for w in ("A", "B")}
    cr.cafe_on = getattr(cr, "cafe_on", 1)
    cr.cafe_sets = {w: [(0.0, cr.cafe_on)] for w in ("A", "B")}
    cr.cafe_due = list(dues)


def author_dinner(cr, La, D, rng, night=None):
    """The mime over the dinner clip: a round every PHASE from the start (see
    DIN_ACTS), on the regulars' beat; the last round ends on the Rovers'
    stage, the finale from rovers_figures.FINALE_AT, then he mingles."""
    m = cr.mime
    F0 = RF.FINALE_AT
    rounds = int(round(F0 / CYCLE))
    t = 0.5
    for k in range(rounds):
        c0 = k * CYCLE
        t = cycle(m, c0, max(t, c0 + 0.5), DIN_ACTS[k % len(DIN_ACTS)], f"d{k}", cr, rng, last=k == rounds - 1)
    if t > F0 + 4.0:
        m.late.append(("into the finale", round(t - F0, 1)))
    t = finale(m, cr, F0, t, rng, night or BASE_NIGHT)
    t = after_show(m, t, D)
    m.overrun = max(m.overrun, t - (D - 1.6))
    return m


# --- Mingling ------------------------------------------------------------------
# His last bow taken, he steps down among the crowd and stays there the rest of
# the night (the lounge loop): to the café couple's table for a little close
# magic, across to the dinner party in the snug with his cards and his balls,
# and back to the front of the stage, where he leans on an invisible lamp post,
# downs an invisible pint, hauls on an invisible rope, waves people over.
MINGLE_HOME = (-2.30, -11.05)                        # at the front of the stage, facing the room
COUPLE_SPOT = GIFT_AT                                # beside the café lady's stool, facing their table
DOWN_STEP = GIFT_WAY[:4]                             # from the stage down the step to the floor
TO_COUPLE = GIFT_WAY[3:]
SNUG_SPOT = DF.GAP_STAND                              # between the snug's two tables
TO_SNUG = [(1.50, -12.40), (3.90, -12.40), DF.SNUG_IN, (4.75, DF.GAP_Y)]


def _home_bit(m, t, kind):
    """A little mime at the front of the stage."""
    f = m.f
    P = lambda x, y, z: V((x, y, z))
    if kind == "lamppost":                           # leaning on one, whistling, one foot crossed
        f.R.add(t + 0.8, P(0.30, 0.10, 1.48)).add(t + 9.0, P(0.30, 0.10, 1.48))
        f.L.add(t + 1.2, P(-0.16, 0.10, 0.96)).add(t + 9.0, P(-0.16, 0.10, 0.96))
        f.lean.add(t + 1.0, -2).add(t + 9.0, -2)
        f.yaw.add(t + 2.0, 30).add(t + 5.0, -30).add(t + 8.0, 0)
        f.pitch.add(t + 2.0, -10).add(t + 8.0, -10)
        f.R.add(t + 9.4, P(0.36, 0.30, 1.30))         # it isn't there: he stumbles
        f.lean.add(t + 9.4, 16).add(t + 10.4, 3)
        f.pitch.add(t + 9.6, 20).add(t + 10.6, 4)
        f.L.add(t + 10.4, HR["L"].copy())
        f.R.add(t + 10.6, HR["R"].copy())
        return t + 11.0
    if kind == "pint":                               # an invisible pint, downed, a wipe of the lips
        f.R.add(t + 0.8, P(0.18, 0.36, 1.16)).add(t + 1.4, P(0.18, 0.36, 1.20))
        f.R.add(t + 2.4, P(0.06, 0.20, 1.54)).add(t + 5.0, P(0.06, 0.18, 1.60))
        f.pitch.add(t + 2.4, -24).add(t + 5.0, -34).add(t + 5.6, 4)
        f.R.add(t + 6.0, P(0.18, 0.36, 1.16)).add(t + 6.6, P(0.06, 0.18, 1.48)).add(t + 7.2, P(0.20, 0.30, 1.40))
        f.L.add(t + 6.0, P(-0.10, 0.12, 1.30)).add(t + 7.6, HR["L"].copy())   # (patting his tummy)
        f.R.add(t + 8.0, HR["R"].copy())
        f.lean.add(t + 6.6, -6).add(t + 8.0, 3)
        return t + 8.4
    if kind == "rope":                               # hauling on a rope, hand over hand, dragged forward
        for q in range(5):
            a, b = ("R", "L") if q % 2 == 0 else ("L", "R")
            ka, kb = (f.R, f.L) if a == "R" else (f.L, f.R)
            sa = 1 if a == "R" else -1
            ka.add(t + 0.6 + q * 1.1, P(sa * 0.04, 0.50, 1.30))
            ka.add(t + 1.2 + q * 1.1, P(sa * 0.06, 0.12, 1.20))
        f.lean.add(t + 1.0, -14).add(t + 5.6, -14).add(t + 6.4, 18).add(t + 7.4, 3)
        f.R.add(t + 7.2, HR["R"].copy())
        f.L.add(t + 7.2, HR["L"].copy())
        return t + 7.6
    # "wave": to someone across the room, then a hat tip
    f.R.add(t + 0.6, P(0.30, 0.20, 1.80))
    for q in range(4):
        f.R.add(t + 0.9 + q * 0.35, P(0.36 + 0.06 * (q % 2), 0.20, 1.82))
    f.yaw.add(t + 0.6, 25).add(t + 2.6, 25).add(t + 3.0, 0)
    f.R.add(t + 3.0, HR["R"].copy())
    return m.bow(t + 3.2, 18, "home")


def home_bits(m, t, t_to, rng):
    """At the front of the stage, little bits of business until t_to."""
    kinds = ["lamppost", "pint", "rope", "wave"]
    m.stay(t)
    while t_to - t > 13.0:
        t = _home_bit(m, t + rng.uniform(1.5, 4.0), rng.choice(kinds))
        m.stay(t)
    m.stay(t_to)
    return max(t, t_to)


def mime_chat(m, t, dur, xys, rng):
    """Silent conversation: he 'talks' with his hands (a story told in the
    air, a shrug, a hand to his heart), listens with his head on one side,
    laughs without a sound, turning from one to another of xys."""
    f = m.f
    P = lambda x, y, z: V((x, y, z))
    end = t + dur
    while t < end - 3.0:
        who = rng.choice(xys)
        m.look_at(t, who, 0.4)
        kind = rng.choice(["tell", "tell", "listen", "laugh", "shrug"])
        if kind == "tell":
            for q in range(4):
                f.R.add(t + 0.5 + q * 0.6, P(0.16 + 0.10 * rng.random(), 0.36, 1.28 + 0.16 * rng.random()))
                f.L.add(t + 0.8 + q * 0.6, P(-0.16 - 0.10 * rng.random(), 0.34, 1.24 + 0.14 * rng.random()))
            t += 3.2
        elif kind == "listen":
            f.L.add(t + 0.6, P(-0.06, 0.22, 1.14))                # hand to his chin
            f.R.add(t + 0.6, P(0.06, 0.20, 1.06))
            f.pitch.add(t + 0.6, 10).add(t + 3.0, 10)
            f.lean.add(t + 0.6, 10).add(t + 3.0, 10)
            t += 3.4
        elif kind == "laugh":
            f.pitch.add(t + 0.3, -16).add(t + 1.0, -6).add(t + 1.4, -16).add(t + 2.2, 4)
            f.lean.add(t + 0.5, -6).add(t + 1.6, 12).add(t + 2.4, 3)
            f.R.add(t + 0.5, P(0.10, 0.18, 1.08)).add(t + 2.2, HR["R"].copy())       # holding his sides
            f.L.add(t + 0.5, P(-0.10, 0.18, 1.08)).add(t + 2.2, HR["L"].copy())
            t += 2.6
        else:
            f.L.add(t + 0.5, P(-0.28, 0.22, 1.30)).add(t + 1.5, P(-0.28, 0.22, 1.30))
            f.R.add(t + 0.5, P(0.28, 0.22, 1.30)).add(t + 1.5, P(0.28, 0.22, 1.30))
            f.pitch.add(t + 0.8, 8).add(t + 1.5, 8)
            t += 2.0
        f.L.add(t, HR["L"].copy())
        f.R.add(t, HR["R"].copy())
        f.pitch.add(t, 3)
        f.lean.add(t, 3)
        t += rng.uniform(0.3, 1.0)
    f.yaw.add(t, 0)
    return max(t, end)


def mingle_couple(m, t, cr):
    """At the café couple's table: a ball found behind her ear, vanished,
    found in his own mouth; three balls juggled low for them; a bow to each."""
    f = m.f
    t0 = t
    lady, man = RF.CAB_SEATS["A"][:2], RF.CAB_SEATS["B"][:2]
    t = m.face(t, RF.CAB_TABLE)
    t = mime_chat(m, t, 22.0, [lady, man], random.Random(f"chat-couple{int(t)}"))
    m.look_at(t, lady)
    ear = V((lady[0] - 0.08, lady[1] - 0.02, RF.CAB_SEAT["A"] + 0.72))
    f.R.hold(t).add(t + 1.2, f.at_world(ear))
    f.lean.hold(t).add(t + 1.2, 22)
    m.prop("MBall", t + 1.3, ("hand", "R", np.array((0, 0, BALL_R)), Q_ID), 0)
    m.scale("MBall", t + 1.3, 0.001, t + 1.45, 1.0)
    f.R.add(t + 2.4, V((0.16, 0.36, 1.32)))
    f.lean.add(t + 2.4, 4)
    f.L.add(t + 3.2, V((-0.03, 0.36, 1.30)))
    f.R.add(t + 3.2, V((0.05, 0.36, 1.30)))
    m.prop("MBall", t + 3.4, ("hide",), 0)
    f.L.add(t + 4.2, V((-0.28, 0.36, 1.38))).add(t + 5.2, V((-0.28, 0.36, 1.38)))
    f.R.add(t + 4.2, HR["R"].copy())
    f.pitch.add(t + 4.4, 16).add(t + 5.2, 16)
    f.L.add(t + 5.8, HR["L"].copy())
    f.R.add(t + 6.2, V((0.04, 0.13, 1.52)))           # out of his own mouth
    f.pitch.add(t + 6.2, 8)
    m.prop("MBall", t + 6.3, ("hand", "R", np.array((0, 0, BALL_R)), Q_ID), 0)
    m.scale("MBall", t + 6.3, 0.001, t + 6.45, 1.0)
    f.R.add(t + 7.2, V((0.22, 0.40, 1.34)))
    m.scale("MBall", t + 8.0, 1.0, t + 8.2, 0.001)
    m.prop("MBall", t + 8.25, ("hide",), 0)
    f.R.add(t + 8.6, HR["R"].copy())
    t += 9.0
    f.yaw.add(t, 0)
    t = m.appear_balls(t)
    f.pitch.add(t, 10)
    t = cascade(m, "ball", t + 0.2, 40, 0.30) + 0.3
    t = m.vanish_balls(t)
    f.pitch.add(t, 3)
    for who in (lady, man):
        m.look_at(t, who)
        t = m.bow(t + 0.2, 26, "couple")
    f.yaw.add(t, 0)
    m.audience.append((t0, t, "couple", None))
    m.acts.append((t0, t, "mingle couple", "couple"))
    return t


def mingle_snug(m, t):
    """In the snug between its tables: the fan of cards shown round both
    tables and sprung from hand to hand, then juggling for them, a bow."""
    f = m.f
    t0 = t
    t = m.turn(t, -90.0)                                 # to the bench
    seats = [DF.PUB[k]["root"] for k in DF.GUESTS]
    t = mime_chat(m, t, 30.0, seats, random.Random(f"chat-snug{int(t)}"))
    f.R.add(t + 0.8, V((0.20, 0.38, 1.40)))
    m.prop("Fan", t + 0.9, ("hand", "R", np.array((0.0, 0.0, 0.03)), Q_ID), 0)
    m.scale("Fan", t + 0.9, 0.001, t + 1.2, 1.0)
    f.yaw.add(t + 1.4, 40).add(t + 3.4, 40).add(t + 4.4, -40).add(t + 6.4, -40).add(t + 7.0, 0)
    f.R.add(t + 2.2, V((0.06, 0.44, 1.40))).add(t + 4.6, V((0.30, 0.40, 1.40)))
    t += 7.4
    f.R.add(t + 0.6, V((0.18, 0.36, 1.32)))
    f.L.add(t + 0.6, V((-0.18, 0.36, 1.26)))
    m.prop("Fan", t + 0.8, ("hide",), 0)
    for i in range(8):
        ts = t + 0.8 + i * 0.12
        m.prop(f"Card{i}", ts, ("fly", "R", ts, "L", ts + 0.42, "card", 0), 0)
        m.prop(f"Card{i}", ts + 0.42, ("hand", "L", np.array((0.0, 0.0, 0.03 + 0.002 * i)), Q_ID), 0)
    t += 2.4
    f.L.add(t + 0.6, V((-0.20, 0.40, 1.40)))
    for i in range(8):                                   # gone, with a snap
        m.scale(f"Card{i}", t + 0.7, 1.0, t + 0.9, 0.001)
        m.prop(f"Card{i}", t + 0.95, ("hide",), 0)
    f.L.add(t + 1.4, HR["L"].copy())
    f.R.add(t + 1.4, HR["R"].copy())
    t += 1.8
    t = m.appear_balls(t)
    f.pitch.add(t, 10)
    t = cascade(m, "ball", t + 0.2, 30, 0.30) + 0.3
    t = flash(m, "ball", t + 0.3, T=0.85, b=0.2, pirouette=False) + 0.3
    t = cascade(m, "ball", t + 0.2, 24, 0.30) + 0.3
    t = m.vanish_balls(t)
    f.pitch.add(t, 3)
    t = mime_chat(m, t, 26.0, seats, random.Random(f"chat-snug2{int(t)}"))
    for k in (40, -40):
        f.yaw.add(t + 0.5, k)
        t = m.bow(t + 0.5, 30, "snug")
    f.yaw.add(t, 0)
    m.audience.append((t0, t, "snug", None))
    m.acts.append((t0, t, "mingle snug", "snug"))
    return t


def mingle_round(m, c0, t, n, cr, rng, t_end=None):
    """One round of the room (from and back to the front of the stage), the
    rest of the time spent there. Ends by c0 + CYCLE (or t_end)."""
    t_end = c0 + CYCLE - 1.6 if t_end is None else t_end
    t = home_bits(m, t, max(t, c0 + 16.0), rng)
    t = m.leg(t, [(m.x, m.y)] + DOWN_STEP + TO_COUPLE[1:], f"m{n}_couple")
    t = mingle_couple(m, t, cr)
    t = m.leg(t, [(m.x, m.y)] + TO_SNUG + [SNUG_SPOT], f"m{n}_snug", juggle=True)
    t = mingle_snug(m, t)
    t = m.leg(t, [(m.x, m.y)] + list(reversed(TO_SNUG)) + list(reversed(TO_COUPLE[:-1])) +
              list(reversed(DOWN_STEP[:-1])) + [MINGLE_HOME], f"m{n}_home", juggle=True)
    t = m.turn(t, FIN_FACE)
    t = home_bits(m, t, t_end, rng)
    m.overrun = max(m.overrun, t - t_end)
    return t


def after_show(m, t, D):
    """His last bow taken: down off the stage to thank the café couple, then
    out among the crowd until the dinner clip ends (at the front of the stage,
    as the lounge loop begins)."""
    rng = random.Random("after-show")
    t = m.leg(t, [(m.x, m.y)] + DOWN_STEP + TO_COUPLE[1:], "a_couple")
    t = m.face(t, RF.CAB_TABLE)
    lady, man = RF.CAB_SEATS["A"][:2], RF.CAB_SEATS["B"][:2]
    for who in (lady, man):
        m.look_at(t, who)
        t = m.bow(t + 0.3, 32, "couple")
    m.f.yaw.add(t, 0)
    t = m.leg(t, [(m.x, m.y)] + list(reversed(TO_COUPLE[:-1])) + list(reversed(DOWN_STEP[:-1])) + [MINGLE_HOME],
              "a_home")
    t = m.turn(t, FIN_FACE)
    return home_bits(m, t, D - 1.6, rng)


DINNER_DUE = [300.0, 1150.0, 2000.0]              # espresso rounds (the chef, when he is free)
LOUNGE_DUE = []                                   # (the lounge's rounds are KIT_COFFEE: an even number a loop,
#                                                   so the same cups are out at the seam)


def author_lounge(cr, rng):
    """The lounge loop: after the finale he mingles, a round of the tables each
    PHASE (tables.mingle_round)."""
    m = cr.mime
    t = 0.5
    for n in range(int(round(DF.LOOP / CYCLE))):
        t = tables.mingle_round(m, n * CYCLE, max(t, n * CYCLE + 0.5), n, cr, rng)
    if m.overrun > 0.0:
        raise RuntimeError(f"mime: a lounge round overruns by {m.overrun:.1f}s")
    return t


def watching(m, venue):
    """(t0, t1, where he is) spans an audience at venue should watch."""
    out = []
    for t0, t1, v, what in m.audience:
        if v == venue:
            out.append((t0, t1))
    out.sort()
    merged = []
    for a, b in out:
        if merged and a <= merged[-1][1] + 1.0:
            merged[-1] = (merged[-1][0], max(merged[-1][1], b))
        else:
            merged.append((a, b))
    return merged


# --- The couple -------------------------------------------------------------------
def author_couple(cr, t_end, calm=None):
    """Sips, applause, gaze and a little talk, around what the mime and the
    staff do: at the café (cr.cafe_sets[who]: [(t, set)], which cup is at the
    place from t), then in the Rovers (their wine, his shows, the bouquet)."""
    m = cr.mime
    LOOPLEN = DF.LOOP
    big = RF.FINALE_AT + RF.FINALE_BOWS[-1]
    if getattr(m, "gift", None):
        _bouquet_lady(cr)
    for who, g in cr.couple.items():
        rng = random.Random(f"cafe{who}{int(LOOPLEN)}")
        f = g.f
        for tb, venue in m.bows:                  # applause after each of his bows they see
            where = g.seated_at(tb)
            if not ((where == "cafe" and venue == "cafe") or (where == "rovers" and venue in ("pub", "couple", "jay"))):
                continue
            if tb < t_end - 6 and not (calm and calm[0] - 5 < tb < calm[1] + 5) and g.free(tb, tb + 3.5):
                g.clap(tb + 0.4 + rng.uniform(0, 0.4), 16 if abs(tb - big) < 3.0 else rng.randint(6, 10))
        t = rng.uniform(15, 30)
        while t < t_end - 12.0:
            ok = g.free(t - 0.5, t + 5.0) and not (calm and calm[0] - 6 < t < calm[1] + 2)
            where = g.seated_at(t)
            if ok and where == "cafe" and g.seated_at(t + 5.0) == "cafe":
                cup_set = [s for tt, s in sorted(cr.cafe_sets[who]) if tt <= t][-1]
                g.sip(t, cr.P.cafe_cups[(who, cup_set)])
            elif ok and where == "rovers" and g.wine and t > g.wine[0] + 8.0 and t < g.wine[1] - 8.0:
                glass = cr.P.cafe_wine[who]
                g.sip(t, glass, WINE_SPOT[who], glass.grip, tilt=50)
            t += rng.uniform(40, 80)
        for tt in (t_end, LOOPLEN):
            f.L.add(tt, g.rest("L"))
            f.R.add(tt, g.rest("R"))
            f.put(tt, g.root.x, g.root.y, g.yaw)
            f.zk.add(tt, g.root.z)
        _couple_gaze(cr, who, g, calm, t_end)


def _bouquet_lady(cr):
    """The café lady takes his bouquet, smells it, sets it on their table; her
    partner applauds him."""
    m = cr.mime
    A, B = cr.couple["A"], cr.couple["B"]
    t_offer, t_take = m.gift
    f = A.f
    mt = TAGS["M"]
    est = GIFT_HAND + V((0, 0, 0.08))
    # (She sits facing the window; he comes up on her left, so the left hand.)

    def want(R, fi, mt=mt):                           # her palm on the stem, above his hand
        G = DF.REC_NOW[mt]
        return V(G["palm"]["R"][fi]) + V((0, 0, 0.08))
    f.L.hold(t_take - 1.4)
    ct = DF.CT(A.loc(est, "rovers"), f.tag, "L", t_take, want)
    DF.CONTACTS.append(ct)
    f.L.add(t_take, ct)
    f.R.hold(t_take - 1.0).add(t_take + 0.2, V((0.06, 0.24, 1.30)))    # a hand to her heart
    nose = V((-0.06, 0.22, 1.52))
    f.L.add(t_take + 1.4, nose).add(t_take + 3.0, nose)
    f.pitch.add(t_take + 1.4, -6).add(t_take + 3.0, -6)
    t_down = m.bouquet_down
    spot = bouquet_down()[1]
    ct2 = DF.CT(A.loc(spot + V((0, 0, 0.05)), "rovers"), f.tag, "L", t_down, lambda R, fi, w=spot + V((0, 0, 0.05)): w)
    DF.CONTACTS.append(ct2)
    f.L.add(t_down - 1.0, V((-0.10, 0.36, 1.18))).add(t_down, ct2)
    bouquet_props(m)
    f.R.add(t_down + 0.8, A.rest("R"))
    f.L.add(t_down + 0.8, A.rest("L"))
    A.busy.append((t_offer - 1.5, t_down + 1.0))
    A.served.append((t_offer - 1.0, t_take + 1.0, (m.x, m.y)))
    B.clap(t_take + 0.6, 10)


def _couple_gaze(cr, who, g, calm, t_end):
    m = cr.mime
    f = g.f
    rng = random.Random(f"gaze{who}{int(DF.LOOP)}")
    m.f.root.done()
    other = cr.couple["B" if who == "A" else "A"]
    n = int(DF.LOOP * 2)
    roots = DF.sample(m.f.root, n, 0.5)
    seats = {"cafe": ((SEAT[who][0], SEAT[who][1] - 0.05), 0.0),
             "rovers": ((cab_root(who).x, cab_root(who).y), RF.CAB_YAW[who])}
    oseats = {"cafe": (SEAT["B" if who == "A" else "A"][0], SEAT["B" if who == "A" else "A"][1]),
              "rovers": tuple(cab_root("B" if who == "A" else "A")[:2])}
    venues = {"cafe": ("cafe",), "rovers": ("pub", "couple", "snug", "jay", "tt", "st")}

    def rel(where, xy):
        (x, y), yaw = seats[where]
        a = heading((x, y), xy) - yaw
        return ((a + 180.0) % 360.0) - 180.0
    t = 1.0                                       # (both clips start and end looking ahead)
    keys = []
    while t < t_end - 2.5:
        dur = rng.uniform(1.8, 3.6)
        where = g.seated_at(t)
        if where is None or g.seated_at(t + dur) != where:
            t += dur
            continue
        i = min(n, int(round(t * 2)))
        live = [w for a, b, v, w in m.audience if a <= t < b and v in venues[where]]
        served = [p for a, b, p in g.served if a - 2.0 <= t < b + 1.0]
        pitch, lean = rng.choice([2, 4, 6]), 8
        mime_xy = (roots[i].x, roots[i].y)
        if served:
            y = rel(where, served[0])
        elif live and rng.random() < 0.9:
            y = rel(where, mime_xy)
        else:
            r = rng.random()
            if r < 0.55:
                y = rel(where, oseats[where]) + rng.uniform(-8, 8)
            elif r < 0.75:
                y = rel(where, mime_xy)
            elif r < 0.85:
                y, pitch, lean = rel(where, oseats[where]) * 0.6, -12, 4          # a laugh
            else:
                y = rng.uniform(-60, 60)
        if calm and calm[0] - 3 < t < calm[1] + 3:
            y, pitch, lean = rel(where, oseats[where]) * 0.8, 4, 8
        y = max(-85.0, min(85.0, y))
        tw = max(-28.0, min(28.0, y * 0.35))
        keys.append((t, y - tw, pitch, tw, lean))
        t += dur
    for t, hy, p, tw, ln in keys:
        f.yaw.add(t, hy).add(t + 0.4, hy)
        f.pitch.add(t, p).add(t + 0.4, p)
        f.twist.add(t, tw).add(t + 0.4, tw)
        f.lean.add(t, ln).add(t + 0.4, ln)
    for c in (f.yaw, f.pitch, f.twist):
        c.add(0.0, 0.0)
        c.add(t_end, 0.0)
        c.add(DF.LOOP, 0.0)
    f.lean.add(0.0, 8).add(t_end, 8).add(DF.LOOP, 8)
    f.bow.add(0.0, 0.0).add(DF.LOOP, 0.0)


def close_mime(m, t_end=None):
    """End of a clip (t_end, and the authoring timeline's end): standing at the
    front of the stage, hands down, exactly as the lounge loop begins."""
    f = m.f
    x, y = MINGLE_HOME
    for L in sorted({DF.LOOP if t_end is None else t_end, DF.LOOP}):
        f.put(L - 1.5, x, y, FIN_FACE)
        f.put(L, x, y, FIN_FACE)
        f.zk.add(L - 1.5, floor_z(x, y)).add(L, floor_z(x, y))
        f.fL.add(L - 1.5, V(RF.STAND_FEET[0])).add(L, V(RF.STAND_FEET[0]))
        f.fR.add(L - 1.5, V(RF.STAND_FEET[1])).add(L, V(RF.STAND_FEET[1]))
        f.L.add(L - 1.5, HR["L"].copy()).add(L, HR["L"].copy())
        f.R.add(L - 1.5, HR["R"].copy()).add(L, HR["R"].copy())
        for k, v in ((f.lean, 3.0), (f.pitch, 3.0), (f.yaw, 0.0), (f.twist, 0.0), (f.bow, 0.0)):
            k.add(L - 1.5, v).add(L, v)



# --- Prop rig: the quiver, balls, clubs, torches and their flames, the magic, the unicycle
BALL_COL = ("d83a2a", "f2c430", "2a6ad8")
CLUB_COL = ("d8283a", "2a5ad8", "f2b818")
G = 9.81
SILK_COL = ("e0202e", "f4c414", "1e9a4a", "2a5ad8", "8a2ab8", "f47a14")
FLAMES = ("Flame0", "Flame1", "Flame2", "Flame3")   # the torches' and the one on his fingertip


def _flame_mat():
    m = bpy.data.materials.get("FigFlame")
    if m:
        return m
    m = bpy.data.materials.new("FigFlame")
    m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (1.0, 0.55, 0.12, 1.0)
    if b.inputs.get('Emission Color'):
        b.inputs['Emission Color'].default_value = (1.0, 0.42, 0.06, 1.0)
        b.inputs['Emission Strength'].default_value = 1.0          # (any stronger and it clips to white)
    return m


def _see_through(name, base, alpha, emit, strength):
    """Bubbles and the beam: blended, both sides, a little light of their own."""
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = base + (1.0,)
    b.inputs['Alpha'].default_value = alpha
    b.inputs['Roughness'].default_value = 0.05
    if b.inputs.get('Emission Color'):
        b.inputs['Emission Color'].default_value = emit + (1.0,)
        b.inputs['Emission Strength'].default_value = strength
    m.use_backface_culling = False
    try:
        m.surface_render_method = 'BLENDED'
    except AttributeError:
        m.blend_method = 'BLEND'
    return m


def _sphere(P, bone, r, colour, mat, segs=10, rings=6):
    g = bmesh.ops.create_uvsphere(P.bm, u_segments=segs, v_segments=rings, radius=r)
    P._tag(g['verts'], bone, colour, mat)


def _rbox(P, bone, M, size, colour, mat=0):
    """A box with an arbitrary placement matrix."""
    g = bmesh.ops.create_cube(P.bm, size=1.0, matrix=M @ Matrix.Diagonal(tuple(size) + (1.0,)))
    P._tag(g['verts'], bone, colour, mat)


def _club_mesh(P, b, col):
    P.ball(b, (0, 0, -0.095), 0.021, "f4f4f0", segs=8, rings=4)
    P.seg(b, (0, 0, -0.09), (0, 0, 0.10), 0.013, 0.017, col, segs=8)
    P.seg(b, (0, 0, 0.10), (0, 0, 0.23), 0.017, 0.044, "f4f4f0", segs=10)
    P.seg(b, (0, 0, 0.23), (0, 0, 0.255), 0.0445, 0.0455, col, segs=10)
    P.seg(b, (0, 0, 0.255), (0, 0, 0.36), 0.0455, 0.040, "f4f4f0", segs=10)
    P.seg(b, (0, 0, 0.36), (0, 0, 0.42), 0.040, 0.016, col, segs=10)


def _torch_mesh(P, b):
    P.seg(b, (0, 0, -0.20), (0, 0, 0.30), 0.013, 0.013, "5a3a22", segs=8)
    P.seg(b, (0, 0, -0.21), (0, 0, -0.19), 0.016, 0.016, "1c1c1e", segs=8)
    P.seg(b, (0, 0, 0.29), (0, 0, 0.40), 0.030, 0.026, "1e1c1a", segs=10)


def _flame_mesh(P, b, o=V((0, 0, 0)), s=1.0):
    P.seg(b, o + V((0, 0, -0.03 * s)), o + V((0, 0, 0.05 * s)), 0.034 * s, 0.048 * s, "ffb030", segs=8, mat=1)
    P.seg(b, o + V((0, 0, 0.05 * s)), o + V((0, 0, 0.24 * s)), 0.048 * s, 0.004 * s, "ffb030", segs=8, mat=1)


MESH_HOOKS = []                                       # fn(P): more kit on the rig (nights.py)
FAST = ("Bubble",)                                    # name prefixes that move like thrown things (nights.py adds)
EXTRA_MATS = []                                       # fn() -> material, slots 4.. (nights.py)


def build_rig(report):
    sc = bpy.context.scene
    arm_data = bpy.data.armatures.new("Fig_DinCafePropsRig")
    arm = bpy.data.objects.new("Fig_DinCafeProps", arm_data)
    sc.collection.objects.link(arm)
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode='EDIT')
    eb = arm_data.edit_bones
    hub = V((UNI_PARK.x, UNI_PARK.y, HUB_Z))
    for name in DYNAMIC + FLAMES:          # (Show: no mesh, just the bone the client reads for the lights)
        b = eb.new(f"DinCafeProps_{name}")
        b.head, b.tail = V((0, 0, 0)), V((0, 0.1, 0))         # identity rest: keys are world transforms
    u = eb.new("DinCafeProps_Uni")
    u.head, u.tail = hub, hub + V((0, 0, 0.1))
    w = eb.new("DinCafeProps_UniWheel")
    w.head, w.tail = hub, hub + V((0.1, 0, 0))
    w.parent = u
    bpy.ops.object.mode_set(mode='OBJECT')
    for pb in arm.pose.bones:
        pb.rotation_mode = 'QUATERNION'
    P = RF._Parts("DinCafeProps_")
    for i in range(3):
        P.ball(f"Ball{i}", (0, 0, 0), BALL_R, BALL_COL[i], segs=10, rings=6)
        _club_mesh(P, f"Club{i}", CLUB_COL[i])
        _torch_mesh(P, f"Torch{i}")
        _flame_mesh(P, f"Flame{i}")
    _flame_mesh(P, "Flame3", V((0, 0, 0)), 0.45)
    # The quiver: a leather tube, its mouth at the bone, a rim and a buckle.
    P.seg("Quiver", (0, 0, -0.36), (0, 0, -0.02), 0.070, 0.082, "6a4026", segs=12)
    P.seg("Quiver", (0, 0, -0.38), (0, 0, -0.36), 0.066, 0.070, "4a2c1a", segs=12)
    P.seg("Quiver", (0, 0, -0.03), (0, 0, 0.0), 0.086, 0.088, "3a2216", segs=12, caps=False)
    P.box("Quiver", (0.0, 0.08, -0.12), (0.05, 0.012, 0.035), "c8a050")
    P.ball("MBall", (0, 0, 0), 0.030, "d8203a", segs=10, rings=6)
    P.ball("ZBall", (0, 0, 0), 0.048, "d8dade", segs=12, rings=8)
    for i in range(6):
        _rbox(P, f"Silk{i}", Matrix(), (0.15, 0.003, 0.15), SILK_COL[i])
    for k in range(9):                              # the fan: cards spread from a pivot at the bottom
        a = math.radians(-44 + 11 * k)
        M = Matrix.Rotation(-a, 4, 'Y') @ Matrix.Translation(V((0.0, -0.001 * k, 0.045)))
        _rbox(P, "Fan", M, (0.062, 0.0015, 0.088), "f6f4ee" if k % 2 else "c8202e")
    for i in range(8):
        _rbox(P, f"Card{i}", Matrix(), (0.062, 0.0015, 0.088), "f6f4ee" if i % 2 else "c8202e")
    P.seg("Bouquet", (0, 0, -0.06), (0, 0, 0.13), 0.010, 0.065, "efe6d2", segs=10, caps=False)
    for k, (dx, dy, dz, c) in enumerate(((0, 0, 0.17, "d8203a"), (0.05, 0.01, 0.15, "f2a6c0"), (-0.05, 0.0, 0.15, "f4d020"),
                                         (0.02, 0.05, 0.155, "ffffff"), (-0.02, -0.05, 0.155, "d8203a"),
                                         (0.03, -0.035, 0.18, "f2a6c0"), (-0.03, 0.035, 0.18, "e86a20"))):
        P.ball("Bouquet", (dx, dy, dz), 0.028, c, segs=8, rings=5)
    P.seg("Bouquet", (0.03, 0, 0.11), (0.08, 0.01, 0.16), 0.004, 0.012, "2e7a32", segs=5)
    # The rola bola: a plywood board with grip pads at the ends, a red roller.
    _rbox(P, "RolaBoard", Matrix(), ROLA_BOARD, "9a6a36")
    for sx in (-0.24, 0.24):
        _rbox(P, "RolaBoard", Matrix.Translation(V((sx, 0.0, ROLA_BOARD[2] / 2 + 0.001))), (0.16, 0.20, 0.002), "1c1c1e")
    P.seg("RolaTube", (0, -0.20, 0), (0, 0.20, 0), ROLA_R, ROLA_R, "c0282e", segs=14)
    for sy in (-0.20, 0.20):
        P.seg("RolaTube", (0, sy - 0.006, 0), (0, sy + 0.006, 0), ROLA_R + 0.004, ROLA_R + 0.004, "c8ccd2", segs=14)
    # The stage's rola bola (black board, gold roller).
    _rbox(P, "Rola2Board", Matrix(), ROLA_BOARD, "2a2420")
    for sx in (-0.24, 0.24):
        _rbox(P, "Rola2Board", Matrix.Translation(V((sx, 0.0, ROLA_BOARD[2] / 2 + 0.001))), (0.16, 0.20, 0.002), "c8a040")
    P.seg("Rola2Tube", (0, -0.20, 0), (0, 0.20, 0), ROLA_R, ROLA_R, "d4a830", segs=14)
    for sy in (-0.20, 0.20):
        P.seg("Rola2Tube", (0, sy - 0.006, 0), (0, sy + 0.006, 0), ROLA_R + 0.004, ROLA_R + 0.004, "2a2420", segs=14)
    # Knives: black handle in the palm (the bone), steel bolster and blade.
    for i in range(3):
        b = f"Knife{i}"
        P.seg(b, (0, 0, -0.10), (0, 0, 0.02), 0.012, 0.014, "161616", segs=8)
        _rbox(P, b, Matrix.Translation(V((0, 0, 0.0275))), (0.034, 0.016, 0.015), "c8ccd2")
        _rbox(P, b, Matrix.Translation(V((0, 0, 0.13))), (0.026, 0.004, 0.19), "dfe3e8")
        P.seg(b, (0, 0, 0.225), (0, 0, 0.255), 0.013, 0.002, "dfe3e8", segs=4, squash=0.15)
    # Bubble wands: two sticks with the string loop between their tips, and a
    # ring on a stick (the bone is the grip; the string end is at +z).
    for b in ("WandL", "WandR"):
        P.seg(b, (0, 0, -0.06), (0, 0, 0.42), 0.009, 0.008, "b98a52", segs=6)
        P.seg(b, (0, 0, -0.06), (0, 0, 0.07), 0.013, 0.013, "1c1c1e", segs=6)
        P.ball(b, (0, 0, 0.43), 0.012, "f2f0ea", segs=6, rings=4)
    P.seg("WandS", (0, 0, -0.06), (0, 0, 0.17), 0.007, 0.006, "e0507e", segs=6)
    for k in range(12):
        a0, a1 = 2 * math.pi * k / 12, 2 * math.pi * (k + 1) / 12
        P.seg("WandS", (0.055 * math.cos(a0), 0, 0.225 + 0.055 * math.sin(a0)),
              (0.055 * math.cos(a1), 0, 0.225 + 0.055 * math.sin(a1)), 0.005, 0.005, "e0507e", segs=4)
    # Bubbles (unit spheres, sized per frame) and the fireball he breathes.
    for b in BUBBLES:
        _sphere(P, b, 1.0, "e8f4ff", 2, segs=10, rings=6)
    for b in GIANTS:
        _sphere(P, b, 1.0, "e8f4ff", 2, segs=16, rings=10)
    _flame_mesh(P, "FireBall", V((0, 0, -0.10)), 1.0)
    # The spotlight's beam: a long cone from the lens (the bone) along +z.
    P.seg("Beam", (0, 0, 0.02), (0, 0, 3.2), 0.07, 0.55, "fff0d0", segs=18, caps=False, mat=3)
    # The unicycle.
    o = lambda x, y, z: hub + V((x, y, z))
    for sg in (1, -1):
        P.seg("Uni", o(sg * 0.045, 0, 0), o(sg * 0.035, 0, 0.30), 0.009, 0.009, "1c1c1e", segs=6)
    P.seg("Uni", o(-0.04, 0, 0.30), o(0.04, 0, 0.30), 0.012, 0.012, "1c1c1e", segs=6)
    P.seg("Uni", o(0, 0, 0.30), o(0, 0, 0.50), 0.012, 0.012, "b8bcc2", segs=6)
    P.ball("Uni", o(0, 0.01, 0.53), 0.06, "c0283a", scale=(0.8, 1.9, 0.45), segs=10, rings=5)
    n = 20
    for k in range(n):
        a0, a1 = 2 * math.pi * k / n, 2 * math.pi * (k + 1) / n
        P.seg("UniWheel", o(0, WHEEL_R * math.cos(a0), WHEEL_R * math.sin(a0)),
              o(0, WHEEL_R * math.cos(a1), WHEEL_R * math.sin(a1)), 0.022, 0.022, "1a1a1a", segs=6)
        P.seg("UniWheel", o(0, 0.205 * math.cos(a0), 0.205 * math.sin(a0)),
              o(0, 0.205 * math.cos(a1), 0.205 * math.sin(a1)), 0.008, 0.008, "c8ccd2", segs=5)
    for k in range(6):
        a = 2 * math.pi * k / 6
        P.seg("UniWheel", o(0, 0, 0), o(0, 0.205 * math.cos(a), 0.205 * math.sin(a)), 0.003, 0.003, "c8ccd2", segs=4)
    P.seg("UniWheel", o(-0.05, 0, 0), o(0.05, 0, 0), 0.018, 0.018, "c8ccd2", segs=8)
    for sg in (1, -1):
        P.seg("UniWheel", o(sg * 0.06, 0, 0), o(sg * 0.075, 0, -sg * CRANK), 0.009, 0.009, "8a8e94", segs=5)
        P.box("UniWheel", o(sg * 0.105, 0, -sg * CRANK), (0.06, 0.09, 0.018), "1c1c1e")
    for hook in MESH_HOOKS:                     # (the nightly finales' kit: nights.py)
        hook(P)
    me = bpy.data.meshes.new("Fig_DinCafePropsMesh")
    P.bm.to_mesh(me)
    attr = me.color_attributes.new("Col", 'BYTE_COLOR', 'CORNER')
    cols = [RF._rgba(c) for c in P.cols]
    data = []
    for poly, face in zip(me.polygons, P.bm.faces):
        data.extend(cols[face[P.col]] * poly.loop_total)
    attr.data.foreach_set("color_srgb", data)
    me.color_attributes.active_color = attr
    DF.smooth(me)
    ob = bpy.data.objects.new("Fig_DinCafePropsBody", me)
    sc.collection.objects.link(ob)
    groups = {}
    for v, bone in P.bone_of_vert.items():
        groups.setdefault(bone, []).append(v.index)
    for bone, verts in groups.items():
        ob.vertex_groups.new(name=bone).add(verts, 1.0, 'REPLACE')
    P.bm.free()
    body, _glass = RF._materials()
    me.materials.append(body)
    me.materials.append(_flame_mat())
    me.materials.append(_see_through("FigBubble", (0.86, 0.94, 1.0), 0.20, (0.55, 0.72, 0.95), 0.25))
    me.materials.append(_see_through("FigBeam", (1.0, 0.93, 0.76), 0.07, (1.0, 0.86, 0.6), 0.6))
    for make in EXTRA_MATS:                     # slots 4 and on (nights.py)
        me.materials.append(make())
    ob.parent = arm
    ob.modifiers.new("Armature", 'ARMATURE').object = arm
    report(f"CAFE PROPS: {len(arm.data.bones)} bones, {len(me.vertices)} verts")
    return arm


def _ctx(m, R, recs=None):
    N = DF.N
    yaw = np.asarray(R["yaw"], float)
    C = dict(palm=R["palm"], yaw=yaw, pos=np.asarray(R["pos"], float), qb=DF.qyaw(yaw),
             fi=lambda t: min(N, max(0, int(round(t * FPS)))), recs=recs or {})
    so = m.silk_out
    so.done()
    C["silk_out"] = np.array(DF.sample(so), float)
    cache = {}

    def local(keys):
        if id(keys) not in cache:
            keys.done()
            cache[id(keys)] = np.array([(v.x, v.y, v.z) for v in DF.sample(keys)])
        return cache[id(keys)]
    C["local"] = local
    return C


def _eval(st, fis, C):
    """(P, Q, S or None) for a state over frames fis; P None when hidden."""
    k = st[0]
    n = len(fis)
    if k == "hide":
        return None, None, None
    if k == "spot":
        return np.tile(np.asarray(st[1][:], float), (n, 1)), np.tile(np.asarray(st[2], float), (n, 1)), None
    qb = C["qb"][fis]
    if k == "hand":
        _k, side, off, q = st
        return C["palm"][side][fis] + DF.qrot(qb, off), DF.qmul(qb, q), None
    if k == "hand2":                                   # in someone else's hand (the café couple)
        _k, tag, side, off, q = st
        R2 = C["recs"][tag]
        q2 = DF.qyaw(np.asarray(R2["yaw"], float)[fis])
        return np.asarray(R2["palm"][side], float)[fis] + DF.qrot(q2, off), DF.qmul(q2, q), None
    if k == "local":
        _k, keys, q = st
        return C["pos"][fis] + DF.qrot(qb, C["local"](keys)[fis]), DF.qmul(qb, q), None
    if k == "fn":
        r = st[1](fis, C)
        return (r[0], r[1], r[2] if len(r) > 2 else None)
    if k == "wkeys":                                    # along a world path (Keys of points), q fixed or a fn of t
        _k, keys, q = st
        P = C["local"](keys)[fis]
        Q = q(fis / FPS) if callable(q) else np.tile(np.asarray(q, float), (n, 1))
        return P, Q, None
    if k == "throw":                                    # out of a hand to a world point (it sticks there)
        _k, s0, t0, target, t1, kind, spins, q1 = st
        f0, f1 = C["fi"](t0), max(C["fi"](t1), C["fi"](t0) + 1)
        off0, qh = held(kind, s0, 0)
        qb0 = C["qb"][f0]
        c0 = C["palm"][s0][f0] + DF.qrot(qb0, off0)
        c1 = np.asarray(target[:], float)
        u = np.clip((fis - f0) / (f1 - f0), 0.0, 1.0)
        T = (f1 - f0) / FPS
        P = c0 + (c1 - c0) * u[:, None]
        P[:, 2] += 0.5 * G * T * T * u * (1 - u) * 0.6
        Q = DF.qmul(DF.qyaw(C["yaw"][f0]), DF.qmul(DF.qx(-360.0 * spins * u), qh))
        Q = np.where((u >= 1.0)[:, None], np.asarray(q1, float), Q)
        return P, Q, None
    _k, s0, t0, s1, t1, kind, spins = st
    f0, f1 = C["fi"](t0), C["fi"](t1)
    f1 = max(f1, f0 + 1)
    off0, qh = held(kind, s0, 0)
    off1, _q = held(kind, s1, 0)
    com = COM.get(kind, np.zeros(3))
    qb0, qb1 = C["qb"][f0], C["qb"][f1]
    c0 = C["palm"][s0][f0] + DF.qrot(qb0, off0) + DF.qrot(DF.qmul(qb0, qh), com)
    c1 = C["palm"][s1][f1] + DF.qrot(qb1, off1) + DF.qrot(DF.qmul(qb1, qh), com)
    u = (fis - f0) / (f1 - f0)
    T = (f1 - f0) / FPS
    Pc = c0 + (c1 - c0) * u[:, None]
    Pc[:, 2] += 0.5 * G * T * T * u * (1 - u) * (1.0 if kind != "card" else 0.35)
    y0, y1 = C["yaw"][f0], C["yaw"][f1]
    yi = y0 + (((y1 - y0) + 180.0) % 360.0 - 180.0) * u
    Q = DF.qmul(DF.qyaw(yi), DF.qmul(DF.qx(-360.0 * spins * u), qh))
    return Pc - DF.qrot(Q, com), Q, None


def _prop_tracks(m, R, recs=None, frames=None):
    """{name: (P (N+1,3), Q (N+1,4), S (N+1,3))} for every moving prop
    (frames: (first, last): only those are evaluated)."""
    N = DF.N
    lo, hi = frames or (0, N)
    C = _ctx(m, R, recs)
    out = {}
    for name in DYNAMIC:
        ev = sorted(m.pt.get(name, []), key=lambda e: e[0])
        P = np.full((N + 1, 3), np.nan)
        Q = np.tile(Q_ID, (N + 1, 1))
        S = np.full((N + 1, 3), 0.001)
        for j, (t0, st, bl) in enumerate(ev):
            f0 = C["fi"](t0)
            f1 = C["fi"](ev[j + 1][0]) if j + 1 < len(ev) else N + 1
            if f1 <= lo or f0 > hi:
                continue
            cut = f0 < lo                          # (begun before the window: no blend in at its edge)
            f0, f1 = max(f0, lo), min(f1, hi + 1)
            if f1 <= f0:
                continue
            fis = np.arange(f0, f1)
            p, q, s = _eval(st, fis, C)
            if p is None:
                continue
            if bl and j > 0 and not cut and ev[j - 1][1][0] in ("spot", "hand", "local", "fn", "wkeys", "hand2"):
                nb = min(bl, len(fis))
                pp, qq, _s = _eval(ev[j - 1][1], fis[:nb], C)
                if pp is not None:
                    w = DF.ease_np((np.arange(nb) + 1) / (nb + 1))
                    p[:nb] = pp + (p[:nb] - pp) * w[:, None]
                    q[:nb] = DF.nlerp(qq, q[:nb], w)
            P[fis] = p
            Q[fis] = q
            if s is None:
                S[fis] = 1.0
            else:
                s = np.asarray(s, float)
                S[fis] = s if s.ndim == 2 else np.repeat(s[:, None], 3, 1)
        if name in m.sc:
            keys = m.sc[name]
            keys.done()
            sc = np.array(DF.sample(keys), float)
            S = np.where(S > 0.5, np.maximum(0.001, S * sc[:, None]), S)
        vis = ~np.isnan(P[:, 0])
        if vis.any():                             # hidden spans wait where they next appear
            idx = np.nonzero(vis)[0]
            nxt = np.searchsorted(idx, np.arange(N + 1))
            nxt = np.where(nxt >= len(idx), len(idx) - 1, nxt)
            fill = idx[nxt]
            P[~vis] = P[fill[~vis]]
            Q[~vis] = Q[fill[~vis]]
        else:
            P[:] = 0.0
        S[~vis] = 0.001
        out[name] = (P, Q, S)
    # Flames ride the torch heads; lit is keyed 0..1, a flicker on top.
    tt = np.arange(N + 1) / FPS
    w = 2 * np.pi / DF.PHASE                      # (flicker periods divide the phase: seamless at the seams)
    for i in range(3):
        P, Q, S = out[f"Torch{i}"]
        keys = m.lit[i]
        keys.done()
        lit = np.array(DF.sample(keys), float) * (S[:, 0] > 0.5)
        head = P + DF.qrot(Q, (0.0, 0.0, TORCH_HEAD + 0.03))
        fl = 1.0 + 0.10 * np.sin(w * 1013 * tt + i) + 0.06 * np.sin(w * 1867 * tt + 2 * i)
        fz = 1.0 + 0.18 * np.sin(w * 1201 * tt + 3 * i) + 0.08 * np.sin(w * 2333 * tt + i)
        Sf = np.stack([lit * fl, lit * fl, lit * fz], 1)
        Sf = np.maximum(Sf, 0.001)
        out[f"Flame{i}"] = (head, np.tile(Q_ID, (N + 1, 1)), Sf)
    keys = m.fire                                 # on his fingertip, lighting the first torch
    keys.done()
    on = np.array(DF.sample(keys), float)
    tip = C["palm"]["R"] + DF.qrot(C["qb"], (0.0, 0.035, 0.05))
    fl = 1.0 + 0.10 * np.sin(w * 997 * tt) + 0.05 * np.sin(w * 1709 * tt)
    fz = 1.0 + 0.16 * np.sin(w * 1153 * tt) + 0.07 * np.sin(w * 2203 * tt)
    out["Flame3"] = (tip, np.tile(Q_ID, (N + 1, 1)), np.maximum(np.stack([on * fl, on * fl, on * fz], 1), 0.001))
    out["Beam"], out["Show"] = _spot_tracks(m, C)
    for name, src, delay, k in getattr(m, "trails", []):     # (light trails: where src was a moment ago)
        P, Q, S = out[src]
        d = int(round(delay * FPS))
        Pt = np.concatenate([np.repeat(P[:1], d, 0), P[:-d]]) if d else P.copy()
        St = np.concatenate([np.repeat(S[:1], d, 0), S[:-d]]) if d else S.copy()
        Ss = np.minimum(S, St)
        out[name] = (Pt, Q, np.where(Ss > 0.002, Ss * k, 0.001))
    return out


SPOT_UP = 2.10                                        # the light hangs this far over the floor he stands on
SPOT_OUT = 0.60                                       # and this far in front of him


def _spot_tracks(m, C):
    """The finale's light: the beam from the lantern on the ceiling to him (on
    while m.beam is), or to m.spot_at as m.spot_free says; and the Show bone,
    over and in front of the lit spot, its scale (x) how far down the house
    lights are (m.dim), (y) how much spotlight there is on that spot (m.spot),
    (z) how black the rest of the room goes (m.black)."""
    N = DF.N
    pos, yaw = C["pos"], C["yaw"]
    sample = lambda keys: np.array(DF.sample(keys), float)
    for k in (m.beam, m.dim, m.spot, m.black, m.spot_free, m.spot_at):
        k.done()
    on = np.clip(sample(m.beam), 0.0, 1.0)
    dim = np.clip(sample(m.dim), 0.001, 1.0)
    spot = np.clip(sample(m.spot), 0.0, 1.0)
    black = np.clip(sample(m.black), 0.0, 1.0)
    free = np.clip(sample(m.spot_free), 0.0, 1.0)[:, None]
    at = np.array([(v.x, v.y, v.z) for v in DF.sample(m.spot_at)], float)
    floor = np.array([RF.stage_z(x, y) for x, y in at[:, :2]]) if free.any() else np.zeros(N + 1)
    at[:, 2] = floor
    lit = pos * (1.0 - free) + at * free                  # the spot on the floor (his feet, or spot_at)
    lamp = np.array(RF.SPOT_LAMP[:], float)
    chest = lit + np.array((0.0, 0.0, 1.15))
    d = chest - lamp
    d /= np.linalg.norm(d, axis=1, keepdims=True)
    # Shortest-arc rotation of +z onto d.
    z = np.array((0.0, 0.0, 1.0))
    axis = np.cross(np.tile(z, (N + 1, 1)), d)
    w = 1.0 + d[:, 2]
    Qb = np.concatenate([w[:, None], axis], 1)
    Qb /= np.linalg.norm(Qb, axis=1, keepdims=True)
    reach = (lamp[2] - lit[:, 2]) / np.maximum(0.2, -d[:, 2])        # lens to the floor under the spot
    Sb = np.stack([on, on, np.maximum(0.001, on * reach / 3.2)], 1)
    Sb = np.maximum(Sb, 0.001)
    yaw_l = np.where(free[:, 0] > 0.5, np.degrees(np.arctan2(-(lit[:, 0] - lamp[0]), lit[:, 1] - lamp[1])), yaw)
    fw = np.stack([-np.sin(np.radians(yaw_l)), np.cos(np.radians(yaw_l)), np.zeros(N + 1)], 1)
    Ps = lit + fw * SPOT_OUT * (1.0 - free) + np.array((0.0, 0.0, SPOT_UP))
    Ps[:, 2] = np.minimum(Ps[:, 2], RF.CARPET + 2.95)
    Ss = np.stack([dim, np.maximum(0.001, dim * spot), np.maximum(0.001, black)], 1)
    # (Off, both hold still: no keys spent following him round the house.)
    idle_q = Qb[np.argmax(on > 0.001)] if (on > 0.001).any() else Qb[0]
    Qb = np.where((on > 0.001)[:, None], Qb, idle_q)
    home = np.array((RF.MIME_PUB[0], RF.MIME_PUB[1], RF.STAGE_TOP + SPOT_UP))
    Ps = np.where((dim > 0.002)[:, None], Ps, home)
    return ((np.tile(lamp, (N + 1, 1)), Qb, Sb), (Ps, np.tile(Q_ID, (N + 1, 1)), Ss))


def _uni_track(m, R):
    """(N+1, 3) hub position, (N+1,) yaw deg, (N+1,) tilt deg, (N+1,) wheel angle."""
    N = DF.N
    pos, yaw = R["pos"], R["yaw"]
    H = np.zeros((N + 1, 3))
    Y = np.zeros(N + 1)
    T = np.zeros(N + 1)
    W = np.zeros(N + 1)
    fi_of = lambda t: min(N, max(0, int(round(t * FPS))))

    def led(fi):
        a = math.radians(yaw[fi])
        off = Matrix.Rotation(a, 2) @ UNI_LED
        x, y = pos[fi][0] + off.x, pos[fi][1] + off.y
        return np.array((x, y, floor_z(x, y) + WHEEL_R)), yaw[fi], 0.0

    def under(fi):
        return np.array((pos[fi][0], pos[fi][1], floor_z(pos[fi][0], pos[fi][1]) + WHEEL_R)), yaw[fi], 0.0

    def parked(pose):
        return np.array(pose[1], float), pose[2], pose[3]

    wrap = lambda a: (a + math.pi) % (2 * math.pi) - math.pi
    ev = list(m.uni)
    marks = sorted(((fi_of(e[1]), i, e) for i, e in enumerate(ev)), key=lambda x: (x[0], x[1]))
    roll = [e for e in ev if e[0] in ("roll", "rock")]
    park = getattr(m, "uni_park0", CAFE_PARK)          # (the lounge loop: laid down outside the Rovers)
    cur = "park"
    blend = None
    theta = 0.0
    th_from = 0.0
    for fi in range(N + 1):
        t = fi / FPS
        while marks and marks[0][0] <= fi:
            _f, _i, e = marks.pop(0)
            k = e[0]
            if k in ("lift", "park"):
                park = e[3]
                blend = (k, fi_of(e[1]), fi_of(e[2]), None)
            elif k in ("under", "off"):
                th_from = theta
                blend = (k, fi_of(e[1]), fi_of(e[2]), e[3] if k == "under" else None)
            elif k == "walk":
                cur = "led"
            elif k == "ride":
                cur = "ride"
            elif k == "stop":
                theta = e[2]
                cur = "stopped"
        if blend and fi > blend[2]:
            cur = {"lift": "led", "under": "ride", "off": "led", "park": "park"}[blend[0]]
            blend = None
        pose_of = lambda kind: led(fi) if kind == "led" else under(fi) if kind == "under" else parked(park)
        if blend:
            k, a, b, th0 = blend
            w = (fi - a) / max(1, b - a)
            w = max(0.0, min(1.0, w))
            w = w * w * (3 - 2 * w)
            src = {"lift": "park", "under": "led", "off": "under", "park": "led"}[k]
            dst = {"lift": "led", "under": "under", "off": "led", "park": "park"}[k]
            ps, ys, ts = pose_of(src)
            pd, yd, td = pose_of(dst)
            yd = ys + (((yd - ys) + 180) % 360 - 180)
            H[fi] = ps + (pd - ps) * w
            Y[fi] = ys + (yd - ys) * w
            T[fi] = ts + (td - ts) * w
            if k == "under":
                theta = th_from + wrap(th0 - th_from) * w
            elif fi:
                theta += np.linalg.norm(H[fi][:2] - H[fi - 1][:2]) / WHEEL_R * (1.0 - T[fi] / LAY_TILT)
        elif cur == "led":
            H[fi], Y[fi], T[fi] = led(fi)
            if fi:
                theta += np.linalg.norm(H[fi][:2] - H[fi - 1][:2]) / WHEEL_R
        elif cur in ("ride", "stopped"):
            H[fi], Y[fi], T[fi] = under(fi)
            for e in roll:
                if e[1] <= t < e[2]:
                    if e[0] == "roll":
                        u = (t - e[1]) / (e[2] - e[1])
                        theta = e[3] + (e[4] - e[3]) * u
                    else:
                        theta = e[3] + 0.6 * math.sin(2 * math.pi * (t - e[1]) / 1.4)
                    break
        else:
            H[fi], Y[fi], T[fi] = parked(park)
        W[fi] = theta
    return H, Y, T, W


def write_clip(arm, m, R, clip, report, recs=None, frames=None):
    """Key every moving café prop for one clip from the mime's record (and the
    couple's, for what he hands them). frames: (first, last): only those, the
    clip starting at the first."""
    N = DF.N
    lo, hi = frames or (0, N)
    cb = DF._channelbag(arm, f"Fig_DinCafeProps{clip}")
    rest = {b.name: b.matrix_local.copy() for b in arm.data.bones}
    kept = 0
    tracks = _prop_tracks(m, R, recs, frames)
    if frames:
        tracks = {k: (P[lo:hi + 1], Q[lo:hi + 1], S[lo:hi + 1]) for k, (P, Q, S) in tracks.items()}
    for name, (P, Q, S) in tracks.items():
        bn = f"DinCafeProps_{name}"
        if P is not None:
            locs = P - np.array(rest[bn].translation[:])
            kept += DF._write_rows(cb, bn, "location", locs.T.copy(), 0.002, (0, 0, 0))
            Qc = Q.copy()
            for i in range(1, len(Qc)):
                if np.dot(Qc[i], Qc[i - 1]) < 0:
                    Qc[i] = -Qc[i]
            kept += DF._write_rows(cb, bn, "rotation_quaternion", Qc.T.copy(), 0.003, (1, 0, 0, 0))
        kept += DF._write_rows(cb, bn, "scale", S.T.copy(), 0.004 if "Flame" in name else 0.002, (1, 1, 1))
    H, Y, T, W = _uni_track(m, R)
    if frames:
        H, Y, T, W = H[lo:hi + 1], Y[lo:hi + 1], T[lo:hi + 1], W[lo:hi + 1]
    n = len(H)
    name = "DinCafeProps_Uni"
    rs = rest[name]
    locs = np.empty((n, 3))
    quats = np.empty((n, 4))
    for fi in range(n):
        want = (Matrix.Translation(V(H[fi])) @ Matrix.Rotation(math.radians(Y[fi]), 4, 'Z') @
                Matrix.Rotation(math.radians(T[fi]), 4, 'Y') @ rs.to_3x3().to_4x4())
        mm = rs.inverted() @ want
        locs[fi] = mm.to_translation()
        q = mm.to_quaternion()
        quats[fi] = (q.w, q.x, q.y, q.z)
    for i in range(1, n):
        if np.dot(quats[i], quats[i - 1]) < 0:
            quats[i] = -quats[i]
    kept += DF._write_rows(cb, name, "location", locs.T.copy(), 0.002, (0, 0, 0))
    kept += DF._write_rows(cb, name, "rotation_quaternion", quats.T.copy(), 0.002, (1, 0, 0, 0))
    wq = np.empty((n, 4))
    for fi in range(n):
        q = Matrix.Rotation(-W[fi], 4, 'Y').to_quaternion()
        wq[fi] = (q.w, q.x, q.y, q.z)
    for i in range(1, n):
        if np.dot(wq[i], wq[i - 1]) < 0:
            wq[i] = -wq[i]
    kept += DF._write_rows(cb, "DinCafeProps_UniWheel", "rotation_quaternion", wq.T.copy(), 0.003, (1, 0, 0, 0))
    vis = {n: (S[:, 0] > 0.5).sum() / FPS for n, (P, Q, S) in tracks.items()}
    report(f"FIGURE DinCafeProps{clip}: {kept} keys; seconds in view: " +
           ", ".join(f"{k} {v:.0f}" for k, v in vis.items() if k[:-1] in ("Ball", "Club", "Torch", "Flame")
                     or k in ("ZBall", "Bouquet", "Fan")))
    return tracks, H


def gate_seam(a, b, label, report):
    """Props rig: clip b starts exactly where clip a ends (scale, and place
    where visible; the unicycle wherever it is)."""
    (Ta, Ha), (Tb, Hb) = a, b
    ok = True
    for name in Tb:
        Pa, Qa, Sa = Ta[name]
        Pb, Qb, Sb = Tb[name]
        if np.abs(Sa[-1] - Sb[0]).max() > 0.02:
            report(f"CAFE PROPS GATE: {name} scale differs at the {label}")
            ok = False
        if Pb is not None and Sa[-1][0] > 0.5 and np.abs(Pa[-1] - Pb[0]).max() > 0.01:
            report(f"CAFE PROPS GATE: {name} moves at the {label}")
            ok = False
    if np.abs(Ha[-1] - Hb[0]).max() > 0.01:
        report(f"CAFE PROPS GATE: the unicycle moves at the {label}")
        ok = False
    return ok


def gate_clip(T, H, clip, report):
    """Nothing jumps (beyond what a fast throw covers in a frame), sinks through
    the floor or rises into the Rovers' ceiling; the unicycle never jumps."""
    ok = True
    for name, (P, Q, S) in T.items():
        if P is None:
            continue
        v = S[:, 0] > 0.5
        if v.any() and P[v][:, 2].min() < Z0 - 0.01:
            report(f"CAFE PROPS GATE: {clip} {name} below the floor")
            ok = False
        if name in ("Show", "Beam"):                  # (the light's bone snaps to him as the lights go)
            continue
        j = np.linalg.norm(np.diff(P, axis=0), axis=1)
        j[~(v[1:] & v[:-1])] = 0
        lim = 0.75 if name[:-1] in ("Ball", "Club", "Torch", "Flame", "Knife") or name.startswith(FAST) else 0.40
        if j.max() > lim:
            report(f"CAFE PROPS GATE: {clip} {name} jumps {j.max():.2f} m at {j.argmax() / FPS:.1f}s")
            ok = False
        inside = v & (P[:, 0] > -3.75) & (P[:, 0] < 6.75) & (P[:, 1] > -16.6) & (P[:, 1] < -10.05)
        if inside.any() and P[inside][:, 2].max() > 3.05:
            k = np.nonzero(inside)[0][np.argmax(P[inside][:, 2])]
            report(f"CAFE PROPS GATE: {clip} {name} at {P[k, 2]:.2f} m under the Rovers ceiling at {k / FPS:.1f}s")
            ok = False
    j = np.linalg.norm(np.diff(H, axis=0), axis=1)
    if j.max() > 0.30:
        report(f"CAFE PROPS GATE: {clip} unicycle jumps {j.max():.2f} m at {j.argmax() / FPS:.1f}s")
        ok = False
    return ok


def gate(dinner, lounge, report, fins=None):
    """Props rig: every clip sound (gate_clip); the lounge loop closes on itself
    and starts where the dinner (or each night's finale, fins) ends."""
    ok = gate_clip(*dinner, "dinner", report) & gate_clip(*lounge, "lounge", report)
    for night, fk in (fins or {}).items():
        ok &= gate_clip(*fk, f"finale {night}", report)
        ok &= gate_seam(fk, lounge, f"finale {night} end / lounge start", report)
    if not fins:
        ok &= gate_seam(dinner, lounge, "dinner end / lounge start", report)
    ok &= gate_seam(lounge, lounge, "lounge seam", report)
    report(f"CAFE PROPS GATE {'passed' if ok else 'FAILED'}")
    return ok


import nights  # noqa: E402,F401  (the other nights' finales: their kit and programmes)
import tables  # noqa: E402  (after the finale: his round of the tables)
