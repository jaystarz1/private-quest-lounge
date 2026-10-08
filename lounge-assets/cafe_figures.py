# Café du Parc, the Paris café on the ground balcony: a couple at a bistro
# table, a mime who entertains them and the empty table for two (where
# visitors sit, an espresso and a slice of cake set at each place), and the
# dinner party's chef bringing the couple their espressos.
#
# It runs on the dinner party's session clock (dinner_figures): the chef is
# one rig with a Dinner clip and a Lounge loop, so the people he serves have
# to share both. Every rig here is a Fig_Din* rig with those two clips.
#
# The mime (Bip: white face, Breton jersey, battered opera hat with a flower,
# white gloves) has three acts, each about three minutes, with a rest of five
# minutes between:
#   A  juggling: a three-ball cascade, high and slow, then fast, a dropped ball
#      chased across the paving, juggling his way past both tables, a bow;
#   B  mime: the wall, the box, the rope, walking against the wind, a flower
#      for the lady, a pretend coffee at the empty table, a bow;
#   C  the unicycle from where it leans by the parapet: laps round the
#      tables, rocking on the spot, a wave to each table, juggling on it, a bow.
# Rests are in his chair by the café front; once a lounge loop he goes over to
# the Rovers instead, where a waiter pours him a red at the end of the bar,
# and he drinks it with the couple at the drinking shelf in the corner by the
# washrooms (only after the dinner's linger window: before it, the session
# clock is not yet in step with the Rovers regulars).
#
# The couple watch him when he performs (applauding at the end of each act),
# talk to each other when he rests, and sip their espressos. The chef makes
# two espressos at the machine on the back counter, carries them out on a
# small tray and swaps them for the empties.
#
# Juggling balls and the unicycle are one prop rig (Fig_DinCafeProps) keyed
# from the mime's solved hands and root, like the dinner's prop rig.
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

# The Rovers: the drinking shelf in the corner by the washrooms (the shelf
# couple in rovers_figures stand at x -3.20 / -2.05).
SHELF_SPOT = (-2.62, -10.98)
SHELF_FACE = 0.0
SHELF_GLASS = V((-2.62, -10.26, RF.SHELF_Z))
BAR_SPOT = (4.15, -13.90)                         # at the bar beside the waiters' end
BAR_GLASS = V((4.25, -14.45, DF.BAR_Z))
TO_ROVERS = [(9.0, -6.40), (7.30, -6.90), (6.20, -7.75), (0.40, -7.75), (-0.65, -9.30), (-0.65, -11.10),
             (0.30, DF.HALL_Y)]

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
ACT_LEN = 180.0
REST_LEN = 300.0


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
    w = P.add(DF.Prop("CafeWine", "glass", ("liquid", "red")))     # the mime's red at the Rovers
    w.fill0 = 0.0
    w.grip = DF.GLASS_GRIP["red"]
    P.cafe_wine = w


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
    P.cafe_tray.at(0.0, ("spot", CAFE_TRAY.copy(), 0.0))
    P.cafe_wine.at(0.0, ("hidden",))


# --- The couple ---------------------------------------------------------------
Z_SEATED = SEAT_TOP + 0.08 - 0.93
FEET = ((-0.11, 0.46, 0.54), (0.11, 0.48, 0.54))
REST = {"L": V((-0.16, 0.33, 1.175)), "R": V((0.16, 0.33, 1.175))}
LAPH = {"L": V((-0.14, 0.28, 1.11)), "R": V((0.14, 0.28, 1.11))}
MOUTH = V((0.05, 0.20, 1.50))
CLAP = (V((-0.05, 0.33, 1.32)), V((0.05, 0.33, 1.32)))


class Patron:
    """One of the couple: seated all clip long."""

    def __init__(self, who, loop):
        self.who = who
        f = Figure(TAGS[who], COUPLE_LOOK[who], loop=loop)
        f.twist = Keys()
        f.bow = Keys()
        self.f = f
        x, y = SEAT[who]
        self.root = V((x, y - 0.05, Z_SEATED))
        self.yaw = 0.0
        f.put(0.0, x, y - 0.05, 0.0)
        f.zk.add(0.0, Z_SEATED)
        f.fL.add(0.0, V(FEET[0]))
        f.fR.add(0.0, V(FEET[1]))
        f.L.add(0.0, REST["L"].copy())
        f.R.add(0.0, REST["R"].copy())
        f.vis.add(0.0, 1.0)
        self.busy = []
        self.tasks = []
        self.served = []                          # (t0, t1, server xy): the chef at their place
        self.x, self.y = x, y - 0.05

    def loc(self, w):
        return V((w[0] - self.root.x, w[1] - self.root.y, w[2] - Z_SEATED))

    def free(self, t0, t1):
        return all(t1 <= a or t0 >= b for a, b in self.busy)

    def sip(self, t, cup):
        """Cup and saucer up off the table, a sip, down again."""
        f = self.f
        spot = CUP[self.who]
        grip = self.loc(spot) + V((-0.02, -0.06, CUP_GRIP - 0.01))
        f.R.hold(t)
        tc = t + 0.9
        ct = DF.CT(grip, f.tag, "R", tc, DF.palm_for("glass", spot, CUP_GRIP))
        DF.CONTACTS.append(ct)
        f.R.add(tc, ct)
        cup.at(tc, ("hand", f.tag, "R", "glass"))
        f.R.add(tc + 0.9, MOUTH.copy()).add(tc + 2.1, MOUTH.copy())
        cup.tilt.add(tc + 0.7, 0).add(tc + 1.2, 38).add(tc + 1.8, 38).add(tc + 2.3, 0)
        ct2 = DF.CT(grip, f.tag, "R", tc + 3.0, DF.palm_for("glass", spot, CUP_GRIP))
        DF.CONTACTS.append(ct2)
        f.R.add(tc + 3.0, ct2)
        cup.at(tc + 3.0, ("spot", spot.copy(), 0.0))
        f.R.add(tc + 3.7, REST["R"].copy())
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
        f.L.add(tt + 0.6, REST["L"].copy())
        f.R.add(tt + 0.6, REST["R"].copy())
        self.busy.append((t, tt + 0.7))
        return tt + 0.7


# --- The mime -----------------------------------------------------------------
HR = {"L": V((-0.17, 0.06, 0.87)), "R": V((0.17, 0.06, 0.87))}
SEATED_MIME_Z = MIME_SEAT_TOP + 0.08 - 0.93
MIME_SEAT_FEET = ((-0.13, 0.46, 0.49), (0.12, 0.50, 0.49))


class Mime(DF.Staff):
    def __init__(self, loop, start="chair"):
        x, y = MIME_CHAIR
        super().__init__(TAGS["M"], MIME_LOOK, (x, y, MIME_CHAIR_YAW), speed=1.05, z=SEATED_MIME_Z)
        f = self.f
        f.loop = loop
        f.fL[0] = (0.0, V(MIME_SEAT_FEET[0]))
        f.fR[0] = (0.0, V(MIME_SEAT_FEET[1]))
        self.seated = True
        self.juggle = []                          # ball script entries (see balls())
        self.uni = []                             # unicycle segments
        self.acts = []                            # (t0, t1, name)
        self.audience = []                        # (t0, t1, target xy) where the couple should look
        self.bows = []                            # end-of-act times (applause)
        self.f.L[0] = (0.0, LAPH["L"] + V((0.0, 0.0, -0.06)))
        self.f.R[0] = (0.0, LAPH["R"] + V((0.0, 0.0, -0.06)))

    def hand_target(self, side):
        h = self.hold[side]
        if h == "glass":
            return DF.FLUTE_STAND.copy()
        if h == "uni":
            return UNI_HAND.copy()
        return HR[side].copy()

    # -- basic moves -----------------------------------------------------------
    def sit(self, t):
        """From standing in front of the chair, down onto it."""
        f = self.f
        x, y = MIME_CHAIR
        t = self.walk(t, [(self.x, self.y), self.chair_front()])
        t = self.turn(t, MIME_CHAIR_YAW)
        f.put(t, self.x, self.y, MIME_CHAIR_YAW)
        f.zk.add(t, floor_z(self.x, self.y))
        f.fL.add(t, V(RF.STAND_FEET[0]))
        f.fR.add(t, V(RF.STAND_FEET[1]))
        f.L.hold(t)
        f.R.hold(t)
        t1 = t + 1.6
        f.put(t1, x, y, MIME_CHAIR_YAW)
        f.zk.add(t1, SEATED_MIME_Z)
        f.fL.add(t1, V(MIME_SEAT_FEET[0]))
        f.fR.add(t1, V(MIME_SEAT_FEET[1]))
        f.L.add(t1 + 0.3, LAPH["L"] + V((0, 0, -0.06)))
        f.R.add(t1 + 0.3, LAPH["R"] + V((0, 0, -0.06)))
        f.lean.hold(t).add(t + 0.8, 20).add(t1 + 0.4, -4)
        self.x, self.y, self.yaw = x, y, MIME_CHAIR_YAW
        self.seated = True
        return t1 + 0.5

    def chair_front(self):
        x, y = MIME_CHAIR
        a = math.radians(MIME_CHAIR_YAW)
        return (x - 0.42 * math.sin(a), y + 0.42 * math.cos(a))

    def stand(self, t):
        f = self.f
        x, y = MIME_CHAIR
        fx, fy = self.chair_front()
        f.put(t, x, y, MIME_CHAIR_YAW)
        f.zk.add(t, SEATED_MIME_Z)
        f.fL.add(t, V(MIME_SEAT_FEET[0]))
        f.fR.add(t, V(MIME_SEAT_FEET[1]))
        f.L.hold(t)
        f.R.hold(t)
        f.lean.hold(t).add(t + 0.7, 24)
        t1 = t + 1.5
        f.put(t1, fx, fy, MIME_CHAIR_YAW)
        f.zk.add(t1, floor_z(fx, fy))
        f.fL.add(t1, V(RF.STAND_FEET[0]))
        f.fR.add(t1, V(RF.STAND_FEET[1]))
        f.L.add(t1, HR["L"].copy())
        f.R.add(t1, HR["R"].copy())
        f.lean.add(t1, 3)
        self.x, self.y, self.yaw = fx, fy, MIME_CHAIR_YAW
        self.seated = False
        return t1 + 0.2

    def rest_in_chair(self, t0, t1, rng):
        """Sitting back: legs crossed now and then, a look round, a stretch."""
        f = self.f
        t = t0 + rng.uniform(4, 10)
        while t < t1 - 14.0:
            kind = rng.choice(["look", "look", "cross", "stretch", "watch"])
            dur = rng.uniform(6.0, 12.0)
            if kind == "cross":
                f.fR.add(t, V(MIME_SEAT_FEET[1])).add(t + 1.2, V((0.02, 0.52, 0.72))) \
                    .add(t + dur, V((0.02, 0.52, 0.72))).add(t + dur + 1.2, V(MIME_SEAT_FEET[1]))
                f.R.add(t, LAPH["R"] + V((0, 0, -0.06))).add(t + 1.2, V((0.06, 0.34, 1.18))) \
                    .add(t + dur, V((0.06, 0.34, 1.18))).add(t + dur + 1.2, LAPH["R"] + V((0, 0, -0.06)))
                f.yaw.add(t + 1.0, rng.uniform(-30, 30)).add(t + dur, rng.uniform(-30, 30))
            elif kind == "stretch":
                for side, sx in (("L", -1), ("R", 1)):
                    k = f.L if side == "L" else f.R
                    k.add(t, LAPH[side] + V((0, 0, -0.06))).add(t + 1.2, V((sx * 0.22, 0.05, 1.95))) \
                        .add(t + 2.6, V((sx * 0.22, 0.05, 1.95))).add(t + 3.8, LAPH[side] + V((0, 0, -0.06)))
                f.pitch.add(t + 1.2, -18).add(t + 2.6, -18).add(t + 3.8, 2)
                f.lean.add(t + 1.2, -12).add(t + 2.6, -12).add(t + 3.8, -4)
                dur = 4.0
            elif kind == "watch":
                f.yaw.add(t + 0.6, rng.choice([-40, 40])).add(t + dur, 0)
                f.pitch.add(t + 0.6, 6).add(t + dur, 2)
            else:
                f.yaw.add(t + 0.6, rng.uniform(-55, 55)).add(t + dur * 0.5, rng.uniform(-25, 25)).add(t + dur, 0)
                f.pitch.add(t + 0.6, rng.uniform(-6, 8)).add(t + dur, 2)
            t += dur + rng.uniform(3.0, 9.0)

    def to_stage(self, t, spot=STAGE, face=180.0):
        if self.seated:
            t = self.stand(t)
        t = self.walk(t, [(self.x, self.y), spot])
        return self.turn(t, face)

    def bow(self, t, deep=40):
        """A hat tip and a deep bow."""
        f = self.f
        f.R.hold(t).add(t + 1.1, V((0.08, 0.12, 1.92))).add(t + 2.0, V((0.40, 0.34, 1.25)))
        f.L.hold(t).add(t + 1.2, V((-0.08, 0.10, 1.00)))
        f.lean.hold(t).add(t + 1.4, 3).add(t + 2.4, deep).add(t + 3.6, deep).add(t + 4.6, 3)
        f.pitch.hold(t).add(t + 2.4, 20).add(t + 4.6, 3)
        f.R.add(t + 3.6, V((0.40, 0.34, 1.25))).add(t + 4.6, HR["R"].copy())
        f.L.add(t + 4.6, HR["L"].copy())
        self.bows.append(t + 2.4)
        return t + 4.8

    def look_at(self, t, xy, dur=0.5):
        rel = ((heading((self.x, self.y), xy) - self.yaw) + 180) % 360 - 180
        self.f.yaw.add(t + dur, max(-70.0, min(70.0, rel)))

    def slide(self, t, xy, dur, yaw=None):
        """Root glides to xy over dur (no turn into it)."""
        f = self.f
        f.put(t, self.x, self.y, self.yaw)
        y = self.yaw if yaw is None else yaw
        f.put(t + dur, xy[0], xy[1], y)
        f.zk.add(t, floor_z(self.x, self.y)).add(t + dur, floor_z(*xy))
        self.x, self.y, self.yaw = xy[0], xy[1], f._yaw
        return t + dur


# --- Act A: juggling ----------------------------------------------------------
JUG_IN = {"L": V((-0.07, 0.32, 1.04)), "R": V((0.07, 0.32, 1.04))}
JUG_OUT = {"L": V((-0.21, 0.30, 1.12)), "R": V((0.21, 0.30, 1.12))}
POCKET = {"L": V((-0.20, 0.10, 0.95)), "R": V((0.20, 0.10, 0.95))}


def cascade(m, t0, n, b, d=0.14, style="plain"):
    """n throws of a three-ball cascade from t0 at beat b (dwell d). Balls start
    two in the right hand, one in the left. Returns (end time, script)."""
    f = m.f
    script = []
    for k in range(n):
        side = "R" if k % 2 == 0 else "L"
        tt = t0 + k * b
        script.append(("throw", k % 3, side, tt, tt + 3 * b - d, "L" if side == "R" else "R"))
    # Hands: each throws on its beats (inside), catches d before its next throw (outside).
    for side, first in (("R", 0), ("L", 1)):
        keys = f.L if side == "L" else f.R
        k = first
        keys.add(t0 - 0.35, JUG_OUT[side] if side == "L" else JUG_IN[side])
        while k < n + 3:
            tt = t0 + k * b
            if k < n:
                keys.add(tt - d, JUG_OUT[side] + (V((0, 0, 0.04)) if style == "high" else V()))
                keys.add(tt, JUG_IN[side])
            elif k - 3 < n and k >= 3:                   # final catches: hold out there
                keys.add(tt - d, JUG_OUT[side] + V((0, 0, -0.02)))
            k += 2
    t_end = t0 + (n + 2) * b
    return t_end, script


def act_juggling(m, t0, rng, P):
    """Act A. Returns the end time."""
    f = m.f
    t = m.to_stage(t0)
    m.audience.append((t, t0 + ACT_LEN, None))
    t = m.bow(t, 25)
    # Balls out of the pockets.
    f.L.add(t + 0.8, POCKET["L"]).add(t + 1.8, JUG_OUT["L"])
    f.R.add(t + 0.8, POCKET["R"]).add(t + 1.8, JUG_IN["R"])
    m.juggle.append(("appear", t + 0.8))
    t += 2.4
    f.pitch.add(t, 14)
    # A slow, high cascade, then the usual pace, then slow again.
    t, s = cascade(m, t, 24, 0.40, style="high")
    m.juggle += s
    f.pitch.add(t, 10)
    t += 1.0
    t, s = cascade(m, t, 60, 0.30)
    m.juggle += s
    t += 1.2
    t, s = cascade(m, t, 36, 0.42, style="high")
    m.juggle += s
    t += 1.2
    # The drop: the last ball of a run sails off; he stares, then fetches it.
    t, s = cascade(m, t, 12, 0.30)
    k_drop = s[-1]
    spot = V((m.x + 0.75, m.y - 0.95, Z0 + 0.035))
    s[-1] = ("drop", k_drop[1], k_drop[2], k_drop[3], spot)
    m.juggle += s
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
    f.lean.add(t, 3).add(t + 0.9, 62).add(t + 1.8, 62).add(t + 2.8, 3)
    f.bow.add(t, 0).add(t + 0.9, 20).add(t + 1.8, 20).add(t + 2.8, 0)
    f.R.add(t, HR["R"].copy()).add(t + 1.0, f.at_world(V((spot.x - 0.02, spot.y + 0.04, Z0 + 0.12))))
    m.juggle.append(("pickup", t + 1.1, "R"))
    f.R.add(t + 1.4, f.at_world(V((spot.x - 0.02, spot.y + 0.04, Z0 + 0.12))))
    f.R.add(t + 2.8, HR["R"].copy())
    t += 3.0
    # For the couple: in front of their table, a run just for them.
    ways = {"couple": [(10.0, -5.90), (8.60, -5.90), (8.40, -6.60), (7.95, -7.50)],
            "jay": [(8.40, -6.60), (8.60, -5.90), (10.30, -5.90), (10.32, -7.30)]}
    for way, face_to in (("couple", TABLE), ("jay", JAY_TABLE)):
        t = m.walk(t, [(m.x, m.y)] + ways[way])
        t = m.face(t, face_to)
        f.L.add(t + 0.8, JUG_OUT["L"])
        f.R.add(t + 0.8, JUG_IN["R"])
        f.pitch.add(t + 0.8, 12)
        t, s = cascade(m, t + 1.4, 48, 0.31)
        m.juggle += s
        f.L.add(t + 0.9, HR["L"].copy())
        f.R.add(t + 0.9, HR["R"].copy())
        f.pitch.add(t + 0.9, 3)
        t = m.bow(t + 1.0, 30)
    t = m.walk(t, [(m.x, m.y), (10.30, -5.90), STAGE])
    t = m.turn(t, 180.0)
    # Juggling a slow lap past both tables, then balls away and a bow.
    f.L.add(t + 0.8, JUG_OUT["L"])
    f.R.add(t + 0.8, JUG_IN["R"])
    f.pitch.add(t + 0.8, 12)
    t0j = t + 1.4
    t, s = cascade(m, t0j, 42, 0.32)
    m.juggle += s
    path = [STAGE, (8.85, -6.55), (8.55, -7.55), (9.20, -8.85), (10.40, -8.40), (10.45, -6.40), STAGE]
    _glide_path(m, t0j + 0.5, t - 0.6, path, look=True)
    t += 0.6
    f.L.add(t + 0.8, POCKET["L"])
    f.R.add(t + 0.8, POCKET["R"])
    m.juggle.append(("vanish", t + 0.9))
    f.L.add(t + 1.6, HR["L"].copy())
    f.R.add(t + 1.6, HR["R"].copy())
    f.pitch.add(t + 1.6, 3)
    t = m.turn(t + 1.6, 180.0)
    t = m.bow(t, 45)
    return t


def _glide_path(m, t0, t1, path, look=False):
    """Root along a smooth path between t0 and t1 (facing the way he goes)."""
    f = m.f
    pts = [V(p) for p in path]
    lens = [(pts[i + 1] - pts[i]).length for i in range(len(pts) - 1)]
    total = sum(lens)
    f.put(t0, m.x, m.y, m.yaw)
    t = t0
    acc = 0.0
    for i in range(1, len(pts)):
        acc += lens[i - 1]
        tt = t0 + (t1 - t0) * acc / total
        h = heading(pts[i - 1], pts[i])
        f.put(t + 0.01, pts[i - 1].x, pts[i - 1].y, h, lin=True)
        f.put(tt, pts[i].x, pts[i].y, h, lin=True)
        f.zk.add(tt, floor_z(pts[i].x, pts[i].y))
        t = tt
    m.x, m.y, m.yaw = pts[-1].x, pts[-1].y, f._yaw
    return t


# --- Act B: the mime routines ---------------------------------------------------
def act_mime(m, t0, rng, P, couple):
    f = m.f
    t = m.to_stage(t0)
    m.audience.append((t, t0 + ACT_LEN, None))
    t = m.bow(t, 25)
    # The wall: palms flat on it, sliding along it, stop, the other way.
    W = 0.40
    for k, (dx, hands) in enumerate(((0.0, ((-0.22, W, 1.40), (0.22, W, 1.40))),
                                     (0.0, ((-0.30, W, 1.25), (0.14, W, 1.55))),
                                     (0.35, ((-0.18, W, 1.55), (0.26, W, 1.30))),
                                     (0.35, ((-0.26, W, 1.20), (0.20, W, 1.45))),
                                     (-0.35, ((-0.22, W, 1.45), (0.24, W, 1.20))),
                                     (-0.35, ((-0.20, W, 1.30), (0.20, W, 1.30))))):
        if dx:                                        # along the wall (his local x)
            a = math.radians(m.yaw)
            t = m.slide(t, (m.x + math.cos(a) * dx, m.y + math.sin(a) * dx), 1.6)
        lag = 0.9 if k == 0 else 0.45
        f.L.add(t + lag, V(hands[0]))
        f.R.add(t + lag, V(hands[1]))
        f.pitch.add(t + lag, rng.uniform(-6, 6))
        f.yaw.add(t + lag, rng.uniform(-25, 25))
        t += 2.2 + (0.5 if k == 0 else 0.0)
    f.lean.add(t, 3)
    # The box: the wall turns into a box; he turns inside it, the lid presses down.
    for k in range(4):
        t = m.turn(t, m.yaw + 90.0, 0.8)
        f.L.add(t + 0.4, V((-0.20, W, 1.35)))
        f.R.add(t + 0.4, V((0.20, W, 1.35)))
        f.yaw.add(t + 0.4, rng.choice([-20, 20]))
        t += 2.0
    f.L.add(t + 0.6, V((-0.16, 0.10, 1.92)))
    f.R.add(t + 0.6, V((0.16, 0.10, 1.92)))
    f.zk.add(t, floor_z(m.x, m.y)).add(t + 1.6, floor_z(m.x, m.y) - 0.22).add(t + 3.2, floor_z(m.x, m.y) - 0.22)
    f.fL.add(t, V(RF.STAND_FEET[0])).add(t + 1.6, V((-0.10, 0.02, 0.31))).add(t + 3.2, V((-0.10, 0.02, 0.31)))
    f.fR.add(t, V(RF.STAND_FEET[1])).add(t + 1.6, V((0.10, 0.02, 0.31))).add(t + 3.2, V((0.10, 0.02, 0.31)))
    f.L.add(t + 1.6, V((-0.16, 0.10, 1.72))).add(t + 3.2, V((-0.16, 0.10, 1.72)))
    f.R.add(t + 1.6, V((0.16, 0.10, 1.72))).add(t + 3.2, V((0.16, 0.10, 1.72)))
    f.pitch.add(t + 1.6, -20).add(t + 3.2, -20)
    t += 3.2
    f.zk.add(t + 1.4, floor_z(m.x, m.y))
    f.fL.add(t + 1.4, V(RF.STAND_FEET[0]))
    f.fR.add(t + 1.4, V(RF.STAND_FEET[1]))
    f.L.add(t + 1.4, HR["L"].copy())
    f.R.add(t + 1.4, HR["R"].copy())
    f.pitch.add(t + 1.4, 3)
    t = m.turn(t + 1.6, 180.0, 0.8)
    # The rope: hand over hand, leaning back, a step at a time towards the tables.
    for q in range(8):
        a, b = ("L", "R") if q % 2 == 0 else ("R", "L")
        ka, kb = (f.L, f.R) if a == "L" else (f.R, f.L)
        sx = -1 if a == "L" else 1
        ka.add(t + 0.4, V((sx * 0.02, 0.62, 1.38)))
        kb.add(t + 0.4, V((-sx * 0.02, 0.30, 1.18)))
        f.lean.add(t + 0.4, -14)
        t += 0.9
        if q % 2 == 1:                                # (short steps: the visitors' chair is behind)
            t = m.slide(t, (m.x, m.y - 0.07), 0.5)
    f.lean.add(t + 0.6, 3)
    f.L.add(t + 0.6, HR["L"].copy())
    f.R.add(t + 0.6, HR["R"].copy())
    t += 1.0
    # Walking against the wind: knees up, leaning into it, going nowhere.
    t = m.turn(t, 90.0, 0.7)
    f.lean.add(t + 0.6, 34)
    f.L.add(t + 0.6, V((-0.24, -0.10, 1.10)))
    f.R.add(t + 0.6, V((0.10, 0.10, 1.95)))                   # holding the hat on
    for q in range(14):
        up = V((0.0, 0.10, 0.30))
        if q % 2 == 0:
            f.fL.add(t + 0.6 + q * 0.6, V(RF.STAND_FEET[0]) + up).add(t + 0.9 + q * 0.6, V(RF.STAND_FEET[0]))
        else:
            f.fR.add(t + 0.6 + q * 0.6, V(RF.STAND_FEET[1]) + up).add(t + 0.9 + q * 0.6, V(RF.STAND_FEET[1]))
    t += 0.6 + 14 * 0.6
    # Blown back across the stage.
    t = m.slide(t, (m.x + 0.9, m.y), 1.4)
    f.lean.add(t, 3)
    f.L.add(t, HR["L"].copy())
    f.R.add(t, HR["R"].copy())
    t = m.turn(t + 0.3, 180.0, 0.7)
    # The balloon: blown up, tied, it lifts him onto his toes and drags him
    # sideways, he lets it go and waves it off into the sky.
    f.L.add(t + 0.8, V((-0.04, 0.22, 1.58)))
    f.R.add(t + 0.8, V((0.04, 0.22, 1.58)))
    for q in range(5):                                       # three big breaths, the hands drawing apart
        w = 0.05 + 0.05 * q
        f.L.add(t + 1.4 + q * 0.9, V((-w, 0.26 + 0.02 * q, 1.56)))
        f.R.add(t + 1.4 + q * 0.9, V((w, 0.26 + 0.02 * q, 1.56)))
        f.lean.add(t + 1.4 + q * 0.9, -4 if q % 2 else 4)
    t += 6.2
    f.L.add(t + 0.6, V((-0.02, 0.20, 1.40)))
    f.R.add(t + 0.9, V((0.06, 0.10, 1.90)))                   # holding the string up
    f.pitch.add(t + 0.9, -30)
    z = floor_z(m.x, m.y)
    f.zk.add(t, z).add(t + 1.6, z + 0.06)
    f.fL.add(t, V(RF.STAND_FEET[0])).add(t + 1.6, V((-0.10, 0.0, 0.03)))
    f.fR.add(t, V(RF.STAND_FEET[1])).add(t + 1.6, V((0.10, 0.0, 0.03)))
    t += 1.8
    t = m.slide(t, (m.x - 0.7, m.y), 2.6)
    f.zk.add(t, z + 0.06).add(t + 1.0, z)
    f.fL.add(t, V((-0.10, 0.0, 0.03))).add(t + 1.0, V(RF.STAND_FEET[0]))
    f.fR.add(t, V((0.10, 0.0, 0.03))).add(t + 1.0, V(RF.STAND_FEET[1]))
    f.R.add(t + 1.0, V((0.30, 0.20, 1.85)))
    for q in range(4):                                       # waving it off
        f.R.add(t + 1.3 + q * 0.4, V((0.22 + 0.10 * (q % 2), 0.20, 1.85)))
    f.pitch.add(t + 2.8, -35)
    t += 3.4
    f.R.add(t + 0.8, HR["R"].copy())
    f.L.add(t + 0.8, HR["L"].copy())
    f.pitch.add(t + 0.8, 3)
    t += 1.0
    # A tug of war with the gentleman across the way: the rope goes taut, he is
    # dragged a step towards him, digs in, wins.
    B = couple["B"]
    t = m.face(t, (B.x, B.y))
    for q in range(6):
        pull = q % 2 == 0
        f.L.add(t + 0.5, V((-0.04, 0.55 if pull else 0.42, 1.20)))
        f.R.add(t + 0.5, V((0.04, 0.38 if pull else 0.25, 1.15)))
        f.lean.add(t + 0.5, -18 if pull else 16)
        t += 1.2
        if q == 1:
            t = m.slide(t, (m.x + 0.25 * math.sin(math.radians(-m.yaw)), m.y + 0.25 * math.cos(math.radians(m.yaw))), 0.5)
    f.L.add(t + 0.6, HR["L"].copy())
    f.R.add(t + 0.8, V((0.30, 0.10, 1.75)))                   # a victory fist
    f.R.add(t + 2.0, HR["R"].copy())
    f.lean.add(t + 0.6, 3)
    t += 2.4
    # A flower for the lady at the couple's table.
    A = couple["A"]
    t = m.walk(t, [(m.x, m.y), (8.60, -5.90), (7.55, -7.62)])
    t = m.face(t, (A.x, A.y))
    f.lean.add(t + 0.6, 22)
    f.R.add(t, HR["R"].copy()).add(t + 1.0, V((0.14, 0.12, 1.92))).add(t + 1.9, V((0.12, 0.45, 1.25))) \
        .add(t + 4.5, V((0.12, 0.45, 1.25)))
    f.L.add(t + 1.9, V((-0.10, 0.10, 1.25)))
    m.audience.append((t, t + 5.0, "flower"))
    t += 4.8
    f.R.add(t + 0.8, V((0.06, 0.20, 1.62)))                 # he smells it himself, delighted
    f.pitch.add(t + 0.8, -10).add(t + 2.0, -10)
    f.lean.add(t + 0.8, -4)
    t += 2.4
    f.R.add(t + 0.6, HR["R"].copy())
    f.L.add(t + 0.6, HR["L"].copy())
    f.lean.add(t + 0.6, 3)
    f.pitch.add(t + 0.6, 3)
    # At the empty table: pulls out an invisible chair, sits on nothing,
    # an imaginary espresso, little finger out.
    t = m.walk(t + 0.6, [(m.x, m.y), (8.65, -7.30)])
    t = m.turn(t, -90.0)
    f.R.add(t + 0.6, V((0.15, 0.40, 1.00))).add(t + 1.4, V((0.15, 0.10, 1.00)))
    t += 1.6
    z = floor_z(m.x, m.y)
    f.zk.add(t, z).add(t + 1.3, z - 0.40)
    f.fL.add(t, V(RF.STAND_FEET[0])).add(t + 1.3, V((-0.12, 0.42, 0.49)))
    f.fR.add(t, V(RF.STAND_FEET[1])).add(t + 1.3, V((0.12, 0.44, 0.49)))
    f.lean.add(t + 1.3, 6)
    t += 1.6
    for q in range(2):
        f.R.add(t + 0.7, V((0.12, 0.36, 1.22))).add(t + 1.5, V((0.06, 0.20, 1.48))) \
            .add(t + 2.6, V((0.06, 0.20, 1.48))).add(t + 3.4, V((0.12, 0.36, 1.22)))
        f.L.add(t + 0.7, V((-0.10, 0.34, 1.18)))
        f.pitch.add(t + 1.5, -12).add(t + 2.6, -12).add(t + 3.4, 4)
        t += 3.6
    m.audience.append((t - 7.2, t, "jay"))
    f.zk.add(t + 1.2, z)
    f.fL.add(t + 1.2, V(RF.STAND_FEET[0]))
    f.fR.add(t + 1.2, V(RF.STAND_FEET[1]))
    f.L.add(t + 1.2, HR["L"].copy())
    f.R.add(t + 1.2, HR["R"].copy())
    f.lean.add(t + 1.2, 3)
    t += 1.4
    t = m.walk(t, [(m.x, m.y), (8.70, -6.30), STAGE])
    t = m.turn(t, 180.0)
    t = m.bow(t, 45)
    return t


# --- Act C: the unicycle -------------------------------------------------------
WHEEL_R = 0.24
CRANK = 0.12
HUB_Z = Z0 + WHEEL_R
SADDLE_Z = HUB_Z + 0.53
RIDE_Z = SADDLE_Z + 0.07 - 0.93                     # root z on the saddle
UNI_LED = V((0.20, 0.35))                          # where the unicycle stands when he wheels it (his local xy)
UNI_HAND = V((0.20, 0.33, 0.82))                  # his right hand on the saddle then
UNI_LOOP = [(9.60, -5.75), (10.85, -6.25), (10.95, -7.60), (10.40, -8.70), (9.50, -8.85), (8.70, -8.30),
            (8.62, -6.90), (8.95, -6.05), (9.60, -5.75)]


def _spline(pts, n=24):
    """Closed Catmull-Rom through pts (first == last) -> dense polyline."""
    P = [V(p) for p in pts[:-1]]
    k = len(P)
    out = []
    for i in range(k):
        p0, p1, p2, p3 = P[(i - 1) % k], P[i], P[(i + 1) % k], P[(i + 2) % k]
        for j in range(n):
            s = j / n
            s2, s3 = s * s, s * s * s
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * s + (2 * p0 - 5 * p1 + 4 * p2 - p3) * s2 +
                              (-p0 + 3 * p1 - 3 * p2 + p3) * s3))
    out.append(out[0].copy())
    return out


UNI_PATH = _spline(UNI_LOOP)


def act_unicycle(m, t0, rng, P):
    f = m.f
    t = m.to_stage(t0)
    m.audience.append((t, t0 + ACT_LEN, None))
    t = m.bow(t, 20)
    # Over to the unicycle by the parapet; it comes upright as he takes the saddle.
    stand_at = (UNI_PARK.x - 0.45, UNI_PARK.y)
    t = m.walk(t, [(m.x, m.y), stand_at])
    t = m.turn(t, -90.0)
    f.R.add(t + 0.6, UNI_HAND.copy())
    m.uni.append(("lift", t + 0.4, t + 1.6))
    m.hold["R"] = "uni"
    t += 1.6
    # Wheel it to the start of the loop, then hop on.
    start = UNI_PATH[0]
    m.uni.append(("walk", t, None))
    t = m.walk(t, [(m.x, m.y), (start.x + 0.35, start.y + 0.10), (start.x, start.y + 0.45)])
    t = m.turn(t, 180.0)
    m.uni.append(("under", t, t + 0.9))
    m.hold["R"] = None
    _mount(m, t, 0.9)
    t += 1.0
    theta = 0.0
    m.uni.append(("ride", t, None))
    # Laps, rocks on the spot, a wave to each table, juggling on it.
    laps = [("lap", 0.9), ("rock", 6.0), ("lap", 1.0), ("wave", JAY_TABLE), ("lap", 1.1), ("wave", TABLE),
            ("lap", 1.2), ("rock", 4.0), ("juggle", 36), ("lap", 1.0), ("lap", 1.25), ("rock", 5.0),
            ("juggle", 24), ("lap", 1.1), ("lap", 0.95), ("rock", 4.0)]
    for kind, arg in laps:
        if kind == "lap":
            t, theta = _ride_lap(m, t, theta, arg, rng)
        elif kind == "rock":
            t, theta = _rock(m, t, theta, arg)
        elif kind == "wave":
            t, theta = _rock(m, t, theta, 3.6, wave=arg)
        else:                                          # juggling on it
            t0j = t
            f.L.add(t, V((-0.45, 0.12, 1.30)))
            f.R.add(t, V((0.45, 0.12, 1.30)))
            f.L.add(t + 0.8, POCKET["L"])
            f.R.add(t + 0.8, POCKET["R"])
            m.juggle.append(("appear", t + 0.8))
            f.L.add(t + 1.5, JUG_OUT["L"])
            f.R.add(t + 1.5, JUG_IN["R"])
            t1, s = cascade(m, t + 2.0, arg, 0.30)
            m.juggle += s
            f.L.add(t1 + 0.7, POCKET["L"])
            f.R.add(t1 + 0.7, POCKET["R"])
            m.juggle.append(("vanish", t1 + 0.8))
            f.L.add(t1 + 1.5, V((-0.45, 0.12, 1.30)))
            f.R.add(t1 + 1.5, V((0.45, 0.12, 1.30)))
            t, theta = _rock(m, t0j, theta, t1 + 1.6 - t0j, hands=False)
    m.uni.append(("stop", t, theta))
    # Off at the start of the loop, wheel it back, lean it on the glass.
    _dismount(m, t, 0.9)
    m.uni.append(("off", t, t + 0.9))
    m.hold["R"] = "uni"
    t += 1.0
    m.uni.append(("walk", t, None))
    t = m.walk(t, [(m.x, m.y), (start.x + 0.35, start.y - 0.25), stand_at])
    t = m.turn(t, -90.0)
    m.uni.append(("park", t, t + 1.2))
    m.hold["R"] = None
    f.R.add(t + 1.2, HR["R"].copy())
    t += 1.4
    t = m.walk(t, [(m.x, m.y), STAGE])
    t = m.turn(t, 180.0)
    t = m.bow(t, 45)
    return t


def _pedals(theta):
    """Local foot targets on the pedals for wheel angle theta (forward = +y)."""
    hub = V((0.0, 0.0, HUB_Z - RIDE_Z))                       # hub height above the root
    r = V((0.11, -CRANK * math.sin(theta), -CRANK * math.cos(theta) + 0.075))      # forward roll: the
    l = V((-0.11, CRANK * math.sin(theta), CRANK * math.cos(theta) + 0.075))       # wheel turns by -theta
    return hub + l, hub + r


def _mount(m, t, dur):
    f = m.f
    f.put(t, m.x, m.y, m.yaw)
    f.zk.add(t, floor_z(m.x, m.y))
    p = UNI_PATH[0]
    f.put(t + dur, p.x, p.y, heading(UNI_PATH[0], UNI_PATH[1]))
    f.zk.add(t + dur, RIDE_Z)
    l, r = _pedals(0.0)
    f.fL.add(t, V(RF.STAND_FEET[0])).add(t + dur, l)
    f.fR.add(t, V(RF.STAND_FEET[1])).add(t + dur, r)
    f.L.add(t + dur, V((-0.45, 0.10, 1.30)))
    f.R.add(t + dur, V((0.45, 0.10, 1.30)))
    m.x, m.y, m.yaw = p.x, p.y, f._yaw


def _dismount(m, t, dur):
    f = m.f
    a = math.radians(m.yaw)
    back = (m.x + 0.38 * math.sin(a), m.y - 0.38 * math.cos(a))
    f.put(t, m.x, m.y, m.yaw)
    f.zk.add(t, RIDE_Z)
    f.put(t + dur, back[0], back[1], m.yaw)
    f.zk.add(t + dur, floor_z(*back))
    f.fL.add(t + dur, V(RF.STAND_FEET[0]))
    f.fR.add(t + dur, V(RF.STAND_FEET[1]))
    f.L.add(t + dur, HR["L"].copy())
    f.R.add(t + dur, UNI_HAND.copy())
    m.x, m.y = back


def _ride_lap(m, t, theta, speed, rng):
    """One lap of the loop at speed (m/s), pedals turning with the wheel."""
    f = m.f
    pts = UNI_PATH
    for i in range(1, len(pts)):
        a, b = pts[i - 1], pts[i]
        d = (b - a).length
        dt = d / speed
        h = heading(a, b)
        f.put(t, a.x, a.y, h, lin=True)
        f.zk.add(t, RIDE_Z, lin=True)
        steps = max(1, int(dt * 6))
        for q in range(steps):
            tt = t + dt * q / steps
            th = theta + (d * q / steps) / WHEEL_R
            l, r = _pedals(th)
            f.fL.add(tt, l, lin=True)
            f.fR.add(tt, r, lin=True)
            wob = math.sin(tt * 2.3) * 4.0
            f.lean.add(tt, 6 + wob, lin=True)
            f.L.add(tt, V((-0.45, 0.10 + 0.04 * math.sin(tt * 3.1), 1.30 + 0.05 * math.sin(tt * 2.7))), lin=True)
            f.R.add(tt, V((0.45, 0.10 + 0.04 * math.cos(tt * 2.9), 1.30 + 0.05 * math.cos(tt * 2.5))), lin=True)
        theta += d / WHEEL_R
        m.uni.append(("roll", t, t + dt, theta - d / WHEEL_R, theta))
        t += dt
    m.x, m.y, m.yaw = pts[-1].x, pts[-1].y, f._yaw
    f.put(t, m.x, m.y, heading(pts[-2], pts[-1]))
    return t, theta


def _rock(m, t, theta, dur, wave=None, hands=True):
    """Idling on the spot: a little back and forth, the pedals rocking."""
    f = m.f
    steps = max(2, int(dur * 6))
    a = math.radians(m.yaw)
    fwd = V((-math.sin(a), math.cos(a)))
    x0, y0 = m.x, m.y
    th0 = theta
    for q in range(steps + 1):
        tt = t + dur * q / steps
        s = math.sin(2 * math.pi * (tt - t) / 1.4)
        dth = 0.6 * s
        dx = fwd * (dth * WHEEL_R)
        f.put(tt, x0 + dx.x, y0 + dx.y, m.yaw, lin=True)
        f.zk.add(tt, RIDE_Z, lin=True)
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
    m.uni.append(("rock", t, t + dur, th0))
    return t + dur, th0


# --- The chef's espresso runs ---------------------------------------------------
def _on_counter_slot(slot, grip):
    """Palm for a cup on tray slot `slot` while the tray rests on the counter."""
    rot = Matrix.Rotation(math.radians(0.0), 3, 'Z')
    w = CAFE_TRAY + rot @ DF.TRAY_SLOTS[slot] + V((0, 0, grip))
    return lambda R, fi, w=w: w


WAITER_OUT = [(4.25, DF.HALL_Y), (0.30, DF.HALL_Y), (-0.65, -11.10), (-0.65, -9.30), (0.40, -7.75), (6.20, -7.75),
              (7.30, -6.90), (9.10, -5.40), C_MACHINE]     # from the Rovers to the café counter


def coffee_run(cr, t_avail, who="chef", old=None):
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
    if who == "chef":
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


# --- The mime's red at the Rovers (lounge loop) --------------------------------
BAR_G = V((4.45, -14.40, DF.BAR_Z))               # where the waiter pours it, between him and the mime
MIME_BAR = (4.25, -13.95)
SHELF_AT = (-2.62, -10.62)                        # between the shelf couple, at the shelf
SHELF_G = V((-2.62, -10.30, RF.SHELF_Z))
TO_BAR = [STAGE, (9.0, -6.40), (7.30, -6.90), (6.20, -7.75), (0.40, -7.75), (-0.65, -9.30), (-0.65, -11.10),
          (0.30, DF.HALL_Y), (4.25, DF.HALL_Y), MIME_BAR]
BAR_TO_SHELF = [MIME_BAR, (4.25, DF.HALL_Y), (0.30, DF.HALL_Y), (-0.65, -11.10), (-1.75, -11.45),
                (-2.62, -11.25), SHELF_AT]
SHELF_TO_BAR = list(reversed(BAR_TO_SHELF))
BAR_TO_STAGE = list(reversed(TO_BAR))


def waiter_pour_for_mime(cr, t_avail):
    """W1: a glass up from under the bar, onto it, a red poured from the
    party's bottle, the bottle back. Returns when the glass is ready."""
    w = "W1"
    s = cr.W[w]
    P = cr.P
    d, _i = cr.delay(w)
    t0 = t_avail + d
    s.stay(t0)
    t = cr.pub_go(w, t0, DF.PUB_STN[w], 180.0)
    g = P.cafe_wine
    t = s.reach(t, "R", V((0.12, 0.30, 0.62)), 0.7, 28, 28)
    g.at(t, ("hand", s.f.tag, "R", "glass"))
    s.hold["R"] = "glass"
    tc = s.put_down(t + 0.1, "R", g, BAR_G, 180.0, lift=g.grip, reach=0.05, how="glass")
    t = s.back(tc + 0.1, "R", 0.5)
    b = P.bottles[("red", "Pub")]
    spot = DF.PUB_BOTTLE["red"]
    tc = s.take(t, "R", b, spot, "bottle", lift=b.grip, reach=0.05)
    s.hold["R"] = "bottle"
    t = s.back(tc + 0.1, "R", 0.5)
    dv = Vector((BAR_G.x - s.x, BAR_G.y - s.y, 0)).normalized()
    palm = BAR_G + V((0, 0, 0.25)) - dv * 0.19
    t = s.reach(t, "R", s.f.at_world(palm - dv * 0.045), 0.8, 20, 28, bow=10)
    b.tilt.add(t - 0.1, 0).add(t + 0.5, -100).add(t + 2.0, -100).add(t + 2.5, 0)
    g.ramp(t + 0.5, t + 2.0, DF.LOUNGE_POUR["red"])
    t = s.back(t + 2.6, "R", 0.5)
    tc = s.put_down(t, "R", b, spot, 180.0, lift=b.grip, reach=0.05, how="bottle")
    t = s.back(tc + 0.1, "R", 0.5)
    t = s.turn(t + 0.2, DF.PUB_POST[w][2])
    s.tasks.append((t0, t, "mime red"))
    s.t = t
    return t


def waiter_stash_glass(cr, t_avail):
    """W1: the mime's empty off the bar and away under it."""
    w = "W1"
    s = cr.W[w]
    g = cr.P.cafe_wine
    d, _i = cr.delay(w)
    t0 = t_avail + d
    s.stay(t0)
    t = cr.pub_go(w, t0, DF.PUB_STN[w], 180.0)
    tc = s.take(t, "R", g, BAR_G, "glass", lift=g.grip, reach=0.05)
    t = s.reach(tc + 0.05, "R", V((0.12, 0.30, 0.62)), 0.8, 28, 28)
    g.at(t, ("hidden",))
    g.ramp(t, t + DF.EPS, 0.0)
    s.hold["R"] = None
    t = s.back(t + 0.1, "R", 0.6)
    t = s.turn(t + 0.2, DF.PUB_POST[w][2])
    s.tasks.append((t0, t, "mime glass"))
    s.t = t
    return t


LEG_WAIT = {"leave": 0.0, "shelf_go": 0.0, "shelf_leave": 0.0, "home": 0.0}   # plan_lounge's retries


def leg_at(m, t):
    for t0, t1, name in getattr(m, "legs", []):
        if t0 - 0.5 <= t <= t1 + 0.5:
            return name
    return None


def mime_rovers(m, t, t_ready, cr, rng, t_end):
    """At the bar until the red is poured, over to the shelf corner with it,
    chatting (silently, of course) with the shelf couple, the empty back on
    the bar, and away to the café for the next act at t_end."""
    f = m.f
    g = cr.P.cafe_wine
    m.legs = getattr(m, "legs", [])
    t = m.turn(t, 180.0)
    m.look_at(t, (DF.PUB_STN["W1"][0], DF.PUB_STN["W1"][1]))
    t = max(t + 0.5, t_ready + 0.6)
    tc = m.take(t, "R", g, BAR_G, "glass", lift=g.grip, reach=0.05, lean=22)
    m.hold["R"] = "glass"
    f.yaw.add(tc, 0)
    t = m.back(tc + 0.1, "R", 0.7)
    m.legs.append((m.t_bar, t + LEG_WAIT["shelf_go"], "leave"))
    t += LEG_WAIT["shelf_go"]
    m.stay(t)
    t1 = m.walk(t, BAR_TO_SHELF)
    m.legs.append((t, t1, "shelf_go"))
    t = m.turn(t1, SHELF_FACE)
    t_leave = t_end - (_walk_len(SHELF_TO_BAR) + _walk_len(BAR_TO_STAGE)) / m.speed - 14.0 \
        - LEG_WAIT["home"] + LEG_WAIT["shelf_leave"]
    t_chat = t
    # Chat: sips, big silent gestures, a laugh, looks from one to the other.
    sip_n = 0
    while t < t_leave - 8.0:
        kind = rng.choice(["sip", "gest", "gest", "listen", "laugh"])
        if kind == "sip" and sip_n < 6:
            f.R.add(t, DF.FLUTE_STAND.copy())
            f.R.add(t + 0.9, V((0.05, 0.20, 1.50))).add(t + 2.1, V((0.05, 0.20, 1.50))).add(t + 3.0, DF.FLUTE_STAND.copy())
            g.tilt.add(t + 0.7, 0).add(t + 1.2, 50).add(t + 1.8, 50).add(t + 2.3, 0)
            g.ramp(t + 1.2, t + 1.8, lambda cur: max(0.08, cur - 0.08))
            f.pitch.add(t + 0.9, -12).add(t + 2.1, -12).add(t + 3.0, 3)
            sip_n += 1
            t += 3.4
        elif kind == "gest":
            side = rng.choice([-1, 1])
            f.yaw.add(t + 0.4, side * rng.uniform(25, 45))
            f.L.add(t, HR["L"].copy())
            for q in range(3):
                f.L.add(t + 0.7 + q * 0.7, V((-0.22 + 0.08 * q, 0.30 + 0.05 * (q % 2), 1.30 + 0.15 * (q % 2))))
            f.L.add(t + 3.0, HR["L"].copy())
            f.lean.add(t + 1.0, 10).add(t + 2.6, 3)
            t += 3.4
        elif kind == "laugh":
            f.pitch.add(t + 0.4, -14).add(t + 1.4, -4).add(t + 2.0, 3)
            f.lean.add(t + 0.6, -6).add(t + 2.0, 3)
            t += 2.4
        else:
            side = rng.choice([-1, 1])
            f.yaw.add(t + 0.4, side * rng.uniform(25, 45)).add(t + 3.5, side * 20)
            f.pitch.add(t + 0.4, 6).add(t + 3.5, 4)
            t += 4.0
        t += rng.uniform(0.5, 2.0)
    f.yaw.add(t, 0)
    t = max(t, t_leave)
    m.stay(t)
    m.legs.append((t_chat, t, "shelf_go"))
    g.ramp(t, t + 0.1, lambda cur: 0.08)
    t1 = m.walk(t, SHELF_TO_BAR)
    t1 = m.turn(t1, 180.0)
    tc = m.put_down(t1, "R", g, BAR_G, 180.0, lift=g.grip, reach=0.05, lean=22, how="glass")
    m.hold["R"] = None
    t1 = m.back(tc + 0.1, "R", 0.7)
    m.legs.append((t, t1, "shelf_leave"))
    t_glass = t1
    t1 += LEG_WAIT["home"]
    m.stay(t1)
    t2 = m.walk(t1, BAR_TO_STAGE)
    m.legs.append((t_glass, t2, "home"))
    return t2, t_glass


def _walk_len(pts):
    return sum((V(b) - V(a)).length for a, b in zip(pts, pts[1:])) + 0.6 * len(pts)


# --- Schedules --------------------------------------------------------------------
ACTS = (act_juggling, act_mime, act_unicycle)


def _act(m, i, t, rng, P, couple):
    fn = ACTS[i % 3]
    t0 = t
    t = fn(m, t, rng, P, couple) if fn is act_mime else fn(m, t, rng, P)
    m.acts.append((t0, t, "ABC"[i % 3]))
    m.audience[-1:] = [(a, max(b, t), w) for a, b, w in m.audience[-1:]]
    return t


def _rest_chair(m, t, t_next, rng, calm=()):
    """Back to the chair, sit until it is time to get up for the next act."""
    t = m.walk(t, [(m.x, m.y), m.chair_front()]) if not m.seated else t
    if not m.seated:
        t = m.sit(t)
    m.rest_in_chair(t, t_next - 2.0, rng) if not calm else _calm_rest(m, t, t_next - 2.0, rng, calm)
    return t


def _calm_rest(m, t0, t1, rng, calm):
    """rest_in_chair, but only glances inside the calm window (the dinner's
    linger, where the client may cut)."""
    c0, c1 = calm
    if t0 < c0 - 20:
        m.rest_in_chair(t0, c0 - 6, rng)
    if t1 > c1 + 20:
        m.rest_in_chair(c1 + 6, t1, rng)


def author_dinner(cr, La, D, rng):
    """The mime over the dinner clip: acts at a steady pace until the linger
    window, then resting in his chair to the end of the clip (where the lounge
    loop starts)."""
    m = cr.mime
    calm = (La - 6.0, La + DF.LINGER + 6.0)
    n = 6
    first = 30.0
    rest = max(240.0, (La - 25.0 - first - n * ACT_LEN) / (n - 1))
    while n > 1 and first + n * ACT_LEN + (n - 1) * rest > La - 25.0:
        n -= 1
        rest = max(240.0, (La - 25.0 - first - n * ACT_LEN) / (n - 1))
    t = 0.0
    m.rest_in_chair(0.0, first - 3.0, rng)
    starts = [first + i * (ACT_LEN + rest) for i in range(n)]
    for i, ts in enumerate(starts):
        t = _act(m, i, max(t, ts), rng, cr.P, cr.couple)
        nxt = starts[i + 1] if i + 1 < n else D
        t = _rest_chair(m, t, nxt, rng, calm if nxt == D else ())
    m.last_act = n % 3
    return m


LOUNGE_PLAN = ((60.0, 0, "rovers"), (540.0, 1, "chair"), (1020.0, 2, "chair"))   # act start, act, then rest
DINNER_DUE = [300.0, 1150.0, 2000.0]              # espresso rounds (the chef, when he is free)
LOUNGE_DUE = [200.0]                              # the chef's; W1 brings the other round (WAITER_DUE)
WAITER_DUE = 920.0                                # an even number of rounds a loop: the same cups out at the seam


def add_actors(cr, dues):
    cr.mime = Mime(DF.LOOP)
    cr.couple = {w: Patron(w, DF.LOOP) for w in ("A", "B")}
    cr.cafe_on = getattr(cr, "cafe_on", 1)
    cr.cafe_sets = {w: [(0.0, cr.cafe_on)] for w in ("A", "B")}
    cr.cafe_due = list(dues)


def author_lounge_until_rovers(cr, rng):
    """The lounge loop up to the mime's arrival at the Rovers bar (returns it)."""
    m = cr.mime
    cr.mime_rng = rng
    on = None
    for pr in cr.P.cafe_cups.values():               # which pair the dinner left on the table
        h = pr.holder_at(0.0)
        if h and h[0] == "spot":
            on = int(pr.name[-1])
    cr.cafe_on = on or 1
    cr.cafe_sets = {w: [(0.0, cr.cafe_on)] for w in ("A", "B")}
    m.rest_in_chair(0.0, LOUNGE_PLAN[0][0] - 3.0, rng)
    t = _act(m, LOUNGE_PLAN[0][1], LOUNGE_PLAN[0][0], rng, cr.P, cr.couple)
    t += LEG_WAIT["leave"]
    m.stay(t)
    m.legs = []
    t1 = m.walk(t, TO_BAR)
    m.legs.append((t, t1, "leave"))
    m.t_bar = t1
    return t1


def author_lounge_from_rovers(cr, t_pour):
    """From the red being poured: the Rovers, then the other two acts and rests."""
    m = cr.mime
    rng = cr.mime_rng
    nxt = LOUNGE_PLAN[1][0]
    t, t_glass = mime_rovers(m, m.t_bar, t_pour, cr, rng, nxt)
    m.f.yaw.add(t, 0)
    t = m.turn(t, 180.0)
    for j in (1, 2):
        ts, act, _after = LOUNGE_PLAN[j]
        t = _act(m, act, max(t, ts), rng, cr.P, cr.couple)
        nxt = LOUNGE_PLAN[j + 1][0] if j + 1 < len(LOUNGE_PLAN) else DF.LOOP
        t = _rest_chair(m, t, nxt, rng)
    return t_glass


# --- The couple -------------------------------------------------------------------
def author_couple(cr, t_end, calm=None):
    """Sips, applause, gaze and a little talk, around what the mime and the
    chef do (cr.cafe_sets[who]: [(t, set)], which cup is at the place from t)."""
    m = cr.mime
    LOOPLEN = DF.LOOP
    for who, g in cr.couple.items():
        rng = random.Random(f"cafe{who}{int(LOOPLEN)}")
        f = g.f
        for tb in m.bows:                         # applause after each bow
            if tb < LOOPLEN - 6 and not (calm and calm[0] - 5 < tb < calm[1] + 5) and g.free(tb, tb + 3.5):
                g.clap(tb + 0.4 + rng.uniform(0, 0.4), rng.randint(6, 10))
        t = rng.uniform(15, 30)
        while t < t_end - 12.0:
            ok = g.free(t - 0.5, t + 5.0) and not (calm and calm[0] - 6 < t < calm[1] + 2)
            if ok:
                cup_set = [s for tt, s in sorted(cr.cafe_sets[who]) if tt <= t][-1]
                g.sip(t, cr.P.cafe_cups[(who, cup_set)])
            t += rng.uniform(40, 80)
        for tt in (t_end, LOOPLEN):
            f.L.add(tt, REST["L"].copy())
            f.R.add(tt, REST["R"].copy())
            f.put(tt, g.x, g.y, 0.0)
            f.zk.add(tt, Z_SEATED)
        _couple_gaze(cr, who, g, calm, t_end)


def _couple_gaze(cr, who, g, calm, t_end):
    m = cr.mime
    f = g.f
    rng = random.Random(f"gaze{who}{int(DF.LOOP)}")
    m.f.root.done()
    other = cr.couple["B" if who == "A" else "A"]
    n = int(DF.LOOP * 2)
    roots = DF.sample(m.f.root, n, 0.5)

    def rel(xy):
        a = heading((g.x, g.y), xy)
        return ((a + 180.0) % 360.0) - 180.0
    perform = [(a, b, w) for a, b, w in m.audience]
    t = 1.0                                       # (both clips start and end looking ahead)
    keys = []
    while t < t_end - 2.5:
        dur = rng.uniform(1.8, 3.6)
        i = min(n, int(round(t * 2)))
        live = [w for a, b, w in perform if a <= t < b]
        served = [p for a, b, p in g.served if a - 2.0 <= t < b + 1.0]
        pitch, lean = rng.choice([2, 4, 6]), 8
        if served:
            y = rel(served[0])
        elif live and rng.random() < 0.88:
            y = rel((roots[i].x, roots[i].y))
            if live[0] == "flower":
                y = rel((roots[i].x, roots[i].y)) if who == "A" else rel((other.x, other.y))
                pitch = -6
        else:
            r = rng.random()
            if r < 0.55:
                y = rel((other.x, other.y)) + rng.uniform(-8, 8)
            elif r < 0.75:
                y = rel((roots[i].x, roots[i].y))
            elif r < 0.85:
                y, pitch, lean = rel((other.x, other.y)) * 0.6, -12, 4          # a laugh
            else:
                y = rng.uniform(-60, 60)
        if calm and calm[0] - 3 < t < calm[1] + 3:
            y, pitch, lean = rel((other.x, other.y)) * 0.8, 4, 8
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


# --- Prop rig: juggling balls and the unicycle --------------------------------------
BALL_R = 0.034
BALL_COL = ("d83a2a", "f2c430", "2a6ad8")
G = 9.81
UNI_TILT = 12.0                                   # leaning on the parapet glass


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
    for i in range(3):
        b = eb.new(f"DinCafeProps_Ball{i}")
        b.head, b.tail = V((0, 0, 0)), V((0, 0.1, 0))         # identity rest: keys are world positions
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
    o = lambda x, y, z: hub + V((x, y, z))
    for s in (1, -1):                              # the fork, up to the crown
        P.seg("Uni", o(s * 0.045, 0, 0), o(s * 0.035, 0, 0.30), 0.009, 0.009, "1c1c1e", segs=6)
    P.seg("Uni", o(-0.04, 0, 0.30), o(0.04, 0, 0.30), 0.012, 0.012, "1c1c1e", segs=6)
    P.seg("Uni", o(0, 0, 0.30), o(0, 0, 0.50), 0.012, 0.012, "b8bcc2", segs=6)
    P.ball("Uni", o(0, 0.01, 0.53), 0.06, "c0283a", scale=(0.8, 1.9, 0.45), segs=10, rings=5)
    n = 20
    for k in range(n):                             # the tyre (and rim) round the hub
        a0, a1 = 2 * math.pi * k / n, 2 * math.pi * (k + 1) / n
        p0 = o(0, WHEEL_R * math.cos(a0), WHEEL_R * math.sin(a0))
        p1 = o(0, WHEEL_R * math.cos(a1), WHEEL_R * math.sin(a1))
        P.seg("UniWheel", p0, p1, 0.022, 0.022, "1a1a1a", segs=6)
        q0 = o(0, 0.205 * math.cos(a0), 0.205 * math.sin(a0))
        q1 = o(0, 0.205 * math.cos(a1), 0.205 * math.sin(a1))
        P.seg("UniWheel", q0, q1, 0.008, 0.008, "c8ccd2", segs=5)
    for k in range(6):
        a = 2 * math.pi * k / 6
        P.seg("UniWheel", o(0, 0, 0), o(0, 0.205 * math.cos(a), 0.205 * math.sin(a)), 0.003, 0.003, "c8ccd2", segs=4)
    P.seg("UniWheel", o(-0.05, 0, 0), o(0.05, 0, 0), 0.018, 0.018, "c8ccd2", segs=8)
    for s in (1, -1):                              # cranks and pedals (right down, left up at rest)
        P.seg("UniWheel", o(s * 0.06, 0, 0), o(s * 0.075, 0, -s * CRANK), 0.009, 0.009, "8a8e94", segs=5)
        P.box("UniWheel", o(s * 0.105, 0, -s * CRANK), (0.06, 0.09, 0.018), "1c1c1e")
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
    ob.parent = arm
    ob.modifiers.new("Armature", 'ARMATURE').object = arm
    return arm


def _ball_tracks(m, R):
    """(3, N+1, 3) positions and (3, N+1) visibility for the juggling balls."""
    N = DF.N
    palm = R["palm"]
    up = np.array((0.0, 0.0, BALL_R + 0.004))
    P = np.zeros((3, N + 1, 3))
    S = np.full((3, N + 1), 0.001)
    ev = sorted(m.juggle, key=lambda e: e[1] if e[0] in ("appear", "vanish", "pickup") else e[3])
    fi_of = lambda t: min(N, max(0, int(round(t * FPS))))
    # Per ball: list of (f0, f1, kind, args)
    segs = {i: [] for i in range(3)}
    state = {i: ("hidden",) for i in range(3)}
    since = {i: 0 for i in range(3)}

    def close(i, f, nxt):
        segs[i].append((since[i], f, state[i]))
        since[i] = f
        state[i] = nxt
    for e in ev:
        if e[0] == "appear":
            f = fi_of(e[1])
            for i, side, slot in ((0, "R", 0), (1, "L", 0), (2, "R", 1)):
                close(i, f, ("hand", side, slot))
        elif e[0] == "vanish":
            f = fi_of(e[1])
            for i in range(3):
                close(i, f, ("hidden",))
        elif e[0] == "throw":
            _k, i, side, t0, t1, side2 = e
            f0, f1 = fi_of(t0), fi_of(t1)
            close(i, f0, ("fly", side, f0, side2, f1))
            close(i, f1, ("hand", side2, 0))
        elif e[0] == "drop":
            _k, i, side, t0, spot = e
            f0 = fi_of(t0)
            f1 = fi_of(t0 + 0.75)
            close(i, f0, ("fall", side, f0, f1, np.array(spot[:])))
            close(i, f1, ("bounce", np.array(spot[:]), f1))
            m.dropped = i
        elif e[0] == "pickup":
            f = fi_of(e[1])
            i = getattr(m, "dropped", 2)
            close(i, f, ("lift", e[2], f))
    for i in range(3):
        segs[i].append((since[i], N + 1, state[i]))
    # Second ball in a hand sits on top of the first.
    for i in range(3):
        for f0, f1, st in segs[i]:
            if f1 <= f0:
                continue
            k = st[0]
            if k == "hidden":
                continue
            S[i, f0:f1] = 1.0
            if k == "hand":
                P[i, f0:f1] = palm[st[1]][f0:f1] + up + np.array((0, 0, 0.065 * st[2]))
            elif k == "fly":
                _k, s0, a, s1, b = st
                p0 = palm[s0][a] + up
                p1 = palm[s1][min(N, b)] + up
                T = max(1e-3, (b - a) / FPS)
                for fi in range(f0, f1):
                    u = (fi - a) / max(1, b - a)
                    P[i, fi] = p0 + (p1 - p0) * u + np.array((0, 0, 0.5 * G * T * T * u * (1 - u)))
            elif k == "fall":
                _k, s0, a, b, spot = st
                p0 = palm[s0][a] + up
                p1 = spot + np.array((0, 0, BALL_R))
                T = (b - a) / FPS
                for fi in range(f0, f1):
                    u = (fi - a) / max(1, b - a)
                    P[i, fi] = p0 + (p1 - p0) * u + np.array((0, 0, 0.5 * G * T * T * u * (1 - u) * 0.6))
            elif k == "bounce":
                _k, spot, a = st
                roll = np.array((0.18, -0.22, 0.0))
                for fi in range(f0, f1):
                    tt = (fi - a) / FPS
                    h = 0.0
                    if tt < 0.45:
                        h = 0.22 * 4 * (tt / 0.45) * (1 - tt / 0.45)
                    elif tt < 0.7:
                        h = 0.06 * 4 * ((tt - 0.45) / 0.25) * (1 - (tt - 0.45) / 0.25)
                    w = min(1.0, tt / 1.6)
                    P[i, fi] = spot + roll * (1 - (1 - w) ** 2) + np.array((0, 0, BALL_R + h))
            elif k == "lift":
                _k, side, a = st
                rest = segs[i][[j for j, sg in enumerate(segs[i]) if sg[2] is st][0] - 1]
                spot = rest[2][1] + np.array((0.18, -0.22, BALL_R)) if rest[2][0] == "bounce" else P[i, a - 1]
                for fi in range(f0, f1):
                    w = min(1.0, (fi - a) / (0.35 * FPS))
                    w = w * w * (3 - 2 * w)
                    P[i, fi] = spot + (palm[side][fi] + up - spot) * w
    # Hidden spans wait where they next appear.
    for i in range(3):
        vis = np.nonzero(S[i] > 0.5)[0]
        if len(vis) == 0:
            continue
        for fi in range(N + 1):
            if S[i, fi] < 0.5:
                nxt = vis[vis >= fi]
                P[i, fi] = P[i, nxt[0] if len(nxt) else vis[0]]
    return P, S


def _uni_track(m, R):
    """(N+1, 3) hub position, (N+1,) yaw deg, (N+1,) tilt deg, (N+1,) wheel angle."""
    N = DF.N
    pos, yaw = R["pos"], R["yaw"]
    park = np.array((UNI_PARK.x, UNI_PARK.y, HUB_Z))
    H = np.tile(park, (N + 1, 1))
    Y = np.full(N + 1, UNI_PARK_YAW)
    T = np.full(N + 1, UNI_TILT)
    W = np.zeros(N + 1)
    fi_of = lambda t: min(N, max(0, int(round(t * FPS))))

    def led(fi):
        a = math.radians(yaw[fi])
        off = Matrix.Rotation(a, 2) @ UNI_LED
        return np.array((pos[fi][0] + off.x, pos[fi][1] + off.y, HUB_Z)), yaw[fi]

    def under(fi):
        return np.array((pos[fi][0], pos[fi][1], HUB_Z)), yaw[fi]
    ev = list(m.uni)
    mode, since, theta = "park", 0, 0.0
    marks = []
    for e in ev:
        marks.append((fi_of(e[1]), e))
    marks.sort(key=lambda x: x[0])
    cur = ("park",)
    blend = None
    roll = [e for e in ev if e[0] in ("roll", "rock")]
    for fi in range(N + 1):
        t = fi / FPS
        while marks and marks[0][0] <= fi:
            _f, e = marks.pop(0)
            k = e[0]
            if k in ("lift", "under", "off", "park"):
                blend = (k, fi_of(e[1]), fi_of(e[2]))
            elif k == "walk":
                cur = ("led",)
            elif k == "ride":
                cur = ("ride",)
            elif k == "stop":
                theta = e[2]
                cur = ("stopped",)
        if blend and fi > blend[2]:
            k = blend[0]
            cur = {"lift": ("led",), "under": ("ride",), "off": ("led",), "park": ("park",)}[k]
            blend = None
        if blend:
            k, a, b = blend
            w = (fi - a) / max(1, b - a)
            w = w * w * (3 - 2 * w)
            src = {"lift": "park", "under": "led", "off": "under", "park": "led"}[k]
            dst = {"lift": "led", "under": "under", "off": "led", "park": "park"}[k]
            ps, ys, ts = _uni_pose(src, fi, led, under, park)
            pd, yd, td = _uni_pose(dst, fi, led, under, park)
            yd = ys + (((yd - ys) + 180) % 360 - 180)
            H[fi] = ps + (pd - ps) * w
            Y[fi] = ys + (yd - ys) * w
            T[fi] = ts + (td - ts) * w
        elif cur[0] == "led":
            H[fi], Y[fi] = led(fi)
            T[fi] = 0.0
            if fi:
                theta += np.linalg.norm(H[fi][:2] - H[fi - 1][:2]) / WHEEL_R
        elif cur[0] in ("ride", "stopped"):
            H[fi], Y[fi] = under(fi)
            T[fi] = 0.0
            for e in roll:
                if e[1] <= t < e[2]:
                    if e[0] == "roll":
                        u = (t - e[1]) / (e[2] - e[1])
                        theta = e[3] + (e[4] - e[3]) * u
                    else:
                        theta = e[3] + 0.6 * math.sin(2 * math.pi * (t - e[1]) / 1.4)
                    break
        else:
            H[fi], Y[fi], T[fi] = park, UNI_PARK_YAW, UNI_TILT
        W[fi] = theta
    return H, Y, T, W


def _uni_pose(kind, fi, led, under, park):
    if kind == "led":
        p, y = led(fi)
        return p, y, 0.0
    if kind == "under":
        p, y = under(fi)
        return p, y, 0.0
    return park, UNI_PARK_YAW, UNI_TILT


def write_clip(arm, m, R, clip, report):
    """Key the balls and the unicycle for one clip from the mime's record."""
    N = DF.N
    cb = DF._channelbag(arm, f"Fig_DinCafeProps{clip}")
    rest = {b.name: b.matrix_local.copy() for b in arm.data.bones}
    kept = 0
    BP, BS = _ball_tracks(m, R)
    for i in range(3):
        name = f"DinCafeProps_Ball{i}"
        rs = rest[name]
        locs = BP[i] - np.array(rs.translation[:])
        kept += DF._write_rows(cb, name, "location", locs.T.copy(), 0.002, (0, 0, 0))
        kept += DF._write_rows(cb, name, "scale", np.repeat(BS[i][None, :], 3, 0), 0.002, (1, 1, 1))
    H, Y, T, W = _uni_track(m, R)
    name = "DinCafeProps_Uni"
    rs = rest[name]
    locs = np.empty((N + 1, 3))
    quats = np.empty((N + 1, 4))
    for fi in range(N + 1):
        want = (Matrix.Translation(V(H[fi])) @ Matrix.Rotation(math.radians(Y[fi]), 4, 'Z') @
                Matrix.Rotation(math.radians(T[fi]), 4, 'Y') @ rs.to_3x3().to_4x4())
        mm = rs.inverted() @ want
        locs[fi] = mm.to_translation()
        q = mm.to_quaternion()
        quats[fi] = (q.w, q.x, q.y, q.z)
    for i in range(1, N + 1):
        if np.dot(quats[i], quats[i - 1]) < 0:
            quats[i] = -quats[i]
    kept += DF._write_rows(cb, name, "location", locs.T.copy(), 0.002, (0, 0, 0))
    kept += DF._write_rows(cb, name, "rotation_quaternion", quats.T.copy(), 0.002, (1, 0, 0, 0))
    wq = np.empty((N + 1, 4))
    for fi in range(N + 1):
        q = Matrix.Rotation(-W[fi], 4, 'Y').to_quaternion()
        wq[fi] = (q.w, q.x, q.y, q.z)
    for i in range(1, N + 1):
        if np.dot(wq[i], wq[i - 1]) < 0:
            wq[i] = -wq[i]
    kept += DF._write_rows(cb, "DinCafeProps_UniWheel", "rotation_quaternion", wq.T.copy(), 0.003, (1, 0, 0, 0))
    vis = (BS > 0.5).sum()
    report(f"FIGURE DinCafeProps{clip}: {kept} keys, balls visible {vis / FPS / 3:.0f}s each on average")
    return BP, BS, H, W


def gate(dinner, lounge, report):
    """Props rig: the lounge loop starts where the dinner ends and closes on
    itself; the juggling balls never leave the mime's reach in flight by more
    than they should; the unicycle never sinks into the floor."""
    BPd, BSd, Hd, Wd = dinner
    BPl, BSl, Hl, Wl = lounge
    ok = True
    if np.abs(BSd[:, -1] - BSl[:, 0]).max() > 1e-3 or np.abs(Hd[-1] - Hl[0]).max() > 0.01:
        report("CAFE PROPS GATE: lounge does not start where the dinner ends")
        ok = False
    if np.abs(BSl[:, -1] - BSl[:, 0]).max() > 1e-3 or np.abs(Hl[-1] - Hl[0]).max() > 0.01:
        report("CAFE PROPS GATE: lounge loop not closed")
        ok = False
    for name, BP, BS in (("dinner", BPd, BSd), ("lounge", BPl, BSl)):
        for i in range(3):
            v = BS[i] > 0.5
            if v.any() and BP[i][v][:, 2].min() < Z0 + BALL_R - 0.01:
                report(f"CAFE PROPS GATE: {name} ball {i} below the floor")
                ok = False
            j = np.linalg.norm(np.diff(BP[i], axis=0), axis=1)
            j[~(v[1:] & v[:-1])] = 0
            if j.max() > 0.5:
                report(f"CAFE PROPS GATE: {name} ball {i} jumps {j.max():.2f} m at {j.argmax() / FPS:.1f}s")
                ok = False
        H = Hd if name == "dinner" else Hl
        j = np.linalg.norm(np.diff(H, axis=0), axis=1)
        if j.max() > 0.30:
            report(f"CAFE PROPS GATE: {name} unicycle jumps {j.max():.2f} m at {j.argmax() / FPS:.1f}s")
            ok = False
    report(f"CAFE PROPS GATE {'passed' if ok else 'FAILED'}")
    return ok


def close_mime(m, t_end=None):
    """End of a clip (t_end, and the authoring timeline's end): in his chair,
    exactly as both clips begin."""
    f = m.f
    x, y = MIME_CHAIR
    for L in sorted({DF.LOOP if t_end is None else t_end, DF.LOOP}):
        f.put(L - 1.5, x, y, MIME_CHAIR_YAW)
        f.put(L, x, y, MIME_CHAIR_YAW)
        f.zk.add(L, SEATED_MIME_Z)
        f.fL.add(L - 1.5, V(MIME_SEAT_FEET[0])).add(L, V(MIME_SEAT_FEET[0]))
        f.fR.add(L - 1.5, V(MIME_SEAT_FEET[1])).add(L, V(MIME_SEAT_FEET[1]))
        f.L.add(L - 1.5, LAPH["L"] + V((0, 0, -0.06))).add(L, LAPH["L"] + V((0, 0, -0.06)))
        f.R.add(L - 1.5, LAPH["R"] + V((0, 0, -0.06))).add(L, LAPH["R"] + V((0, 0, -0.06)))
        for k, v in ((f.lean, 3.0), (f.pitch, 3.0), (f.yaw, 0.0), (f.twist, 0.0)):
            k.add(L - 1.5, v).add(L, v)
