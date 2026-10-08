# Dinner party in the dining room (the table, chairs, sideboards and static
# place settings are built in build-penthouse.py's dining section from the
# layout constants below).
#
# Six guests in evening dress (men in black tie, women in gowns) sit at the oak
# refectory table. The two middle chairs facing each other (D3 west, D7 east)
# are left free for visitors and are served like every other place. One shared
# 45-minute loop:
#   champagne on the patio by the BBQ -> they walk in, pull out their chairs,
#   sit, draw in and set their flutes down -> toast -> seven courses (salmon,
#   soup, sole, sorbet, beef, cheese,
#   pudding) -> a fresh glass and a pour for each wine (white with the fish,
#   red with the beef and cheese, sweet with the pudding) -> after the pudding
#   the flutes come back and are poured, the guests take them, push back,
#   stand, push their chairs in and walk back out to the patio.
# The chef takes plates from the warm stack, sets them on the island pass and
# plates the food; two waiters (west side, east side) carry them two at a time
# to the table, clear them to the island, and the chef takes the dirty ones to
# the sink. Wine lives on the two sideboards: each waiter changes his side's
# glasses from a tray and pours from the bottle. Guests eat (fork in the left
# hand), sip, talk with their neighbours and across the table, laugh, and turn
# to whoever sits in the empty chairs.
#
# Figures reuse rovers_figures (rig, mesh, IK). Everything that moves between
# people (plates, glasses, bottles, trays, cutlery) is one prop armature,
# Fig_DinProps, keyed from the solved hands: a held prop follows its holder's
# palm frame by frame, so it can never lag the hand. Pick-ups and put-downs
# blend over 0.35 s, which hides the few centimetres an IK hand misses by.
#
# Channels are presampled on the frame grid (one pointer pass per channel) and
# thinned with a numpy Ramer-Douglas-Peucker; rovers_figures' per-frame track()
# scan and pure-Python thinning are quadratic at 21,600 frames.
import bpy
import math
import random
import numpy as np
from mathutils import Matrix, Vector, Quaternion
from bpy_extras import anim_utils
import rovers_figures as RF
from rovers_figures import Figure, Keys, heading

FPS = RF.FPS
LOOP = 2700.0
EPS = 1.0 / FPS
N = int(round(LOOP * FPS))
DEBUG = False
MISSES = []
TURN_RATE = 240.0
TOL_LOC, TOL_ROT = 0.005, 0.010            # thinning tolerances (m, quaternion component)                           # deg/s: nobody spins round with a plate
BLEND = 4                                   # frames a handover blends over (0.33 s)

# --- Layout -------------------------------------------------------------------
TX, TY, TT = 8.80, 6.10, 0.765              # table centre, top surface
TABLE_HALF = (0.525, 1.50)
CHAIR_X = {"W": 7.97, "E": 9.63}            # chair centres, pulled in to dine
CHAIR_Y = (4.97, 5.72, 6.48, 7.23)
SEAT_TOP = 0.47
EMPTY = (3, 7)                              # the free pair, facing each other
GUESTS = (1, 2, 4, 5, 6, 8)
SIDE_OF = {k: ("W" if k <= 4 else "E") for k in range(1, 9)}
Y_OF = {k: CHAIR_Y[(k - 1) % 4] for k in range(1, 9)}
FWD = {"W": Vector((1, 0, 0)), "E": Vector((-1, 0, 0))}
RIGHT = {"W": Vector((0, -1, 0)), "E": Vector((0, 1, 0))}
YAW = {"W": -90.0, "E": 90.0}               # rovers_figures yaw: 0 faces +y, +90 faces -x
Z_SEATED = SEAT_TOP + 0.08 - 0.93
SEAT_FEET = ((-0.11, 0.47, 0.47), (0.11, 0.49, 0.47))
FLOOR = 0.0


def place(k):
    s, y = SIDE_OF[k], Y_OF[k]
    f, r = FWD[s], RIGHT[s]
    root = Vector((CHAIR_X[s], y, 0.0)) - f * 0.05
    edge = TX - TABLE_HALF[0] if s == "W" else TX + TABLE_HALF[0]
    plate = Vector((edge, y, TT)) + f * 0.165

    def at(df, dr, dz=0.0):
        return plate + f * df + r * dr + Vector((0, 0, dz))
    return dict(k=k, side=s, y=y, f=f, r=r, root=root, plate=plate, yaw=YAW[s],
                glass=at(0.17, 0.20), glass2=at(0.22, 0.09), fork=at(0.0, -0.19, 0.004), knife=at(0.0, 0.19, 0.004),
                spoon=at(0.0, 0.26, 0.004), water=at(0.20, 0.33), bread=at(0.14, -0.30))


PLACES = {k: place(k) for k in range(1, 9)}

# Kitchen: the island's south edge is the pass; the back counter has the warm
# plate stack, the stove (two pans) and the sink.
ISLAND_Z, BACK_Z = 0.89, 0.92
PASS = {"W1": (Vector((8.32, -1.86, ISLAND_Z)), Vector((8.60, -1.86, ISLAND_Z))),
        "W2": (Vector((9.32, -1.86, ISLAND_Z)), Vector((9.60, -1.86, ISLAND_Z)))}
DIRTY = {"W1": (Vector((10.05, -1.86, ISLAND_Z)), Vector((10.33, -1.86, ISLAND_Z))),
         "W2": (Vector((10.62, -1.86, ISLAND_Z)), Vector((10.90, -1.86, ISLAND_Z)))}
W_PASS = {w: ((a.x + b.x) / 2, -2.40) for w, (a, b) in PASS.items()}
W_DIRTY = {w: ((a.x + b.x) / 2, -2.40) for w, (a, b) in DIRTY.items()}
C_PASS = {w: (x, -2.36) for w, (x, _y) in W_PASS.items()}
C_DIRTY = {w: (x, -2.36) for w, (x, _y) in W_DIRTY.items()}
STACK_N = 6                                 # static plates in the warm stack
STACK = Vector((8.72, -3.86, BACK_Z + 0.014 * STACK_N))
PANS = (Vector((8.26, -3.88, BACK_Z)), Vector((8.50, -3.90, BACK_Z)))
SINK = Vector((9.60, -3.90, BACK_Z - 0.004))
BACK_LINE = -3.45                           # the chef moves along the back counter, crossing
                                            # the waiters' lane (y -2.95) only square on
C_STACK, C_STOVE, C_SINK, C_CHOP = (8.72, BACK_LINE), (8.38, BACK_LINE), (9.60, BACK_LINE), (9.02, BACK_LINE)
CHOP = Vector((9.02, -3.86, BACK_Z))

# Sideboards: west under the window, east console below the pictures.
SIDEBOARD = {"W1": (6.15, 6.60, 5.30, 6.90), "W2": (10.95, 11.35, 5.30, 6.90)}   # x0, x1, y0, y1
SB_TOP = 0.90
SB_X = {w: (b[0] + b[1]) / 2 for w, b in SIDEBOARD.items()}
SB_STANCE_X = {"W1": 6.95, "W2": 10.60}
SB_FACE = {"W1": 90.0, "W2": -90.0}
TRAY_Y = 5.62
BOTTLE_Y = {"champ": 6.22, "white": 6.38, "red": 6.54, "sweet": 6.70, "cognac": 5.92, "whisky": 6.06}

AISLE_X = {"W1": 7.25, "W2": 10.35}
GAP_X = {"W": 7.86, "E": 9.74}
GAPS = (4.60, 5.345, 6.10, 6.855, 7.60)
SERVE_GAP = {1: 0, 2: 1, 3: 2, 4: 3, 5: 1, 6: 2, 7: 3, 8: 4}      # each guest from their right
SIDE_PLACES = {"W1": (1, 2, 3, 4), "W2": (5, 6, 7, 8)}
# Standby by the room's south corners: the north aisle is the way in from the
# cocktail lounge's French door (build-cocktail.py) now.
STANDBY = {"W1": (6.70, 4.35, -90.0), "W2": (10.80, 4.35, 90.0)}
SPINE = {
    "W1": [(10.19, -2.95), (7.12, -2.95), (7.12, 4.20), (7.25, 4.55), (7.25, 7.95)],
    "W2": [(10.76, -2.95), (7.65, -2.95), (7.65, 4.05), (10.35, 4.05), (10.35, 7.95)],
}
CHEF_START = (C_STOVE[0], C_STOVE[1], 180.0)

# --- The cocktail lounge (the old BBQ patio, build-cocktail.py) --------------
# Its French door is the north leaf of the dining room's west window (glass
# y 7.35..8.35 at x 5.96): guests and waiters go through it, round the north
# end of the table to the east side, never through a wall or a pane.
CK_DOOR_OUT, CK_DOOR_IN = (5.50, 7.85), (6.62, 7.85)
CK_NORTH_AISLE = 8.20                        # dining room, north of the chairs
CK_POSEUR = {1: (-2.90, 8.75), 2: (0.30, 8.85), 3: (3.20, 8.75)}   # high marble tables
CK_BAR_Z = 1.08
CK_TRAY = Vector((1.85, 5.28, CK_BAR_Z))       # waiters' pick-up at the east end of the counter
CK_PICKUP = (1.85, 5.86)                     # the floor waiter's stance at it (facing the bar)
CK_BARTENDER = (1.40, 4.78)                  # behind the counter (aisle y 4.39..5.0)
CK_UNDER = Vector((1.55, 5.02, 0.86))        # glasses come from the shelf under the counter
CK_BOTTLE = {"red": Vector((1.32, 5.44, CK_BAR_Z)), "white": Vector((1.47, 5.44, CK_BAR_Z)),
             "whisky": Vector((2.10, 5.44, CK_BAR_Z)), "cognac": Vector((2.10, 5.28, CK_BAR_Z))}
CK_W1_POST = (2.45, 6.40, 40.0)              # the floor waiter between rounds, watching the room
# Obstacles for the patio route planner: circles (x, y, r) and boxes
# (x1, x2, y1, y2), already grown by a body's half width.
CK_BLOCK_C = [(x, y, 0.30 + 0.24) for x, y in CK_POSEUR.values()] + \
             [(x, 5.95, 0.20 + 0.20) for x in (-1.05, -0.25, 0.55)] + [(-2.00, 4.40, 0.26 + 0.22)]
CK_BLOCK_B = [(-1.62, 2.42, 4.97 - 0.02, 5.60 + 0.24),         # the counter and its foot rail
              (-1.62, 2.42, 4.00, 4.39 + 0.05),                # the back bar
              (-5.30, -2.0, 5.10, 7.50),                       # west sofa, chairs, table
              (3.05, 5.60, 4.20, 6.95)]                        # east loveseat, chairs, table
CK_LANE = [(-3.80, 7.65), (-1.50, 7.65), (0.30, 7.65), (1.70, 7.65), (2.60, 7.65), (4.40, 7.65),
           CK_DOOR_OUT, (2.70, 6.90), (2.70, 5.10), (2.60, 4.78), CK_BARTENDER, CK_PICKUP, CK_W1_POST[:2],
           (-1.50, 6.60), (0.30, 6.60), (-5.00, 4.70)]

# Before dinner: champagne in the lounge, two groups of three at the high
# tables nearest the door, standing on the south side of each (facing the
# table and, past it, the view). Group B (by the door) goes in first.
PATIO_GROUPS = {"A": (CK_POSEUR[2], {6: -20, 4: -90, 8: -160}),
                "B": (CK_POSEUR[3], {1: -20, 5: -90, 2: -160})}
# In through the door as one loose file, the farthest seat first on each side
# (the south end now: west 1, 2, 4; east 5, 6, 8), so nobody passes someone
# pulling a chair; out again nearest the door first.
ARRIVE_ORDER = (1, 5, 2, 6, 4, 8)
PATIO = {}
for _g, (_c, _m) in PATIO_GROUPS.items():
    for _k, _a in _m.items():
        _p = (_c[0] + 0.56 * math.cos(math.radians(_a)), _c[1] + 0.56 * math.sin(math.radians(_a)))
        PATIO[_k] = (_p[0], _p[1], heading(_p, _c), _g)
GUEST_SPEED = 0.95

# After the pudding they linger at the table over the sweet wine, then go out
# through the house and across the ground balcony to the Rovers Return and
# sit in the snug on the left as you come in (the bench along the Rosamund
# Street wall, four places, and the two stools facing it across the two
# tables). Each waiter brings their side's drinks over on a tray, sets the tray
# down at the near end of the bar and stays there; the lounge clip loops from
# then on: rounds of top-ups from the bottles on the bar, and every guest off to
# the Gents or the Ladies on the party wall once a loop.
#
# Phase: the Rovers regulars loop on server time modulo rovers_figures.LOOP
# (PHASE). The client skips part of the LINGER window (cross-fading 2 s) so the
# dinner clip always ends on a PHASE boundary; with the clip padded to a whole
# number of PHASEs, clip time after the window equals the regulars' time
# modulo PHASE, and so does lounge time (LOUNGE_LOOP is a multiple of PHASE).
# That is what lets the scheduler keep this party out of the regulars' way.
LINGER = 360.0
PHASE = 360.0
LA_TARGET = 2530.0                           # pudding cleared (the old dinner's pace)
LOUNGE_LOOP = 1440.0                          # 24 min: the café mime's three acts and three rests
LOUNGE_DRINK = {1: "red", 2: "white", 5: "red", 4: "whisky", 6: "whisky", 8: "whisky"}
LOUNGE_POUR = {"red": 0.58, "white": 0.62, "whisky": 0.55}
SERVES = {"W1": (1, 2, 4), "W2": (5, 6, 8)}  # whose drinks each waiter carries over (their side of the table)
ROUNDS = {"W1": [(80.0, "red", (1, 5)), (100.0, "white", (2,)), (440.0, "red", (1, 5)), (460.0, "white", (2,))],
          "W2": [(260.0, "whisky", (4, 6, 8)), (620.0, "whisky", (4, 6, 8))]}
WC_PLAN = [(4, 15.0), (6, 40.0), (1, 150.0), (5, 290.0), (8, 410.0), (2, 520.0)]
# (the 12-minute pattern twice over the 24-minute loop)
ROUNDS = {w: r + [(t + 720.0, wn, ks) for t, wn, ks in r] for w, r in ROUNDS.items()}
WC_PLAN = WC_PLAN + [(k, t + 720.0) for k, t in WC_PLAN]
RV_FLOOR = 0.10                              # ground balcony and pub floor (the house is at 0)
STEP_Y = -3.70                               # on the way south, where the floor steps up to it
SNUG_X = 6.45                                # bench cushion centres (build-penthouse BanqE, 4 cushions)
SNUG_Y = (-13.6125, -12.8875, -12.1625, -11.4375)
SNUG_TABLE = {"N": (5.35, -12.05), "S": (5.35, -13.25)}
# Off to the loo, a guest leaves their glass on their table's edge by the gap
# between the tables, standing in the gap (GAP_STAND) facing it.
GAP_STAND = (5.40, -12.65)
GLASS_DOWN = {"N": Vector((5.38, -12.30, 0.85)), "S": Vector((5.38, -13.00, 0.85))}
STOOL_X = 4.65
STRIP_X = 5.92                               # between the snug tables and the bench
GAP_Y = -12.65                               # between the two tables (and their stools)
HALL_Y = -12.85                              # rovers_figures.CY: the pub's walking line
WC_DOOR = {"m": -11.75, "f": -12.95}         # Gents / Ladies door centres on the party wall (x -3.70)
PUB_ORDER = (1, 5, 2, 6, 4, 8)               # leaving the table = arriving in the snug: far seats first
PUB_SEAT = {1: ("bench", 3, "N"), 2: ("bench", 2, "N"), 4: ("stool", -12.05, "N"),
            5: ("bench", 0, "S"), 6: ("bench", 1, "S"), 8: ("stool", -13.25, "S")}
# The way there: the west side of the kitchen, the step up, the ground
# balcony, the Rovers' front door, the pub's hall line to the snug.
HOUSE_SPINE = [(7.05, 3.70), (7.05, -3.55), (7.05, -3.85), (7.05, -6.90), (6.20, -7.75), (0.40, -7.75),
               (-0.65, -9.30), (-0.65, -11.10), (0.30, HALL_Y), (3.90, HALL_Y), (4.25, GAP_Y)]
SNUG_IN = (4.25, GAP_Y)
# The waiters' end of the bar (where the last bar stool was): trays and bottles
# on the counter top (z 1.06), where each stands to reach them and waits
# between rounds, looking out over the room.
BAR_Z = 1.06
PUB_STN = {"W1": (4.75, -13.92), "W2": (5.55, -13.92)}
PUB_POST = {"W1": (4.75, -13.92, 10.0), "W2": (5.55, -13.92, -25.0)}
PUB_TRAY = {"W1": Vector((4.80, -14.47, BAR_Z)), "W2": Vector((5.55, -14.47, BAR_Z))}
PUB_BOTTLE = {"red": Vector((4.55, -14.40, BAR_Z)), "white": Vector((4.98, -14.40, BAR_Z)),
              "whisky": Vector((5.80, -14.40, BAR_Z))}
BOTTLE_STN = {"red": "W1", "white": "W1", "whisky": "W2"}
# Where a waiter stands to hand a drink to / top up a seated guest.
SERVE_AT = {1: (STRIP_X, -11.85), 2: (STRIP_X, -12.52), 4: (4.70, -12.55),
            5: (STRIP_X, -13.25), 6: (STRIP_X, -12.78), 8: (4.70, -12.75)}


def floor_z(x, y):
    return RV_FLOOR if y < STEP_Y else FLOOR


def pub_seat(k):
    """root (x, y), yaw, root z, feet, the floor spot in front and the way in
    from SNUG_IN."""
    kind, v, tb = PUB_SEAT[k]
    if kind == "bench":
        y = SNUG_Y[v]
        root, yaw, top = (SNUG_X - 0.03, y), 90.0, 0.55
        feet = ((-0.11, 0.43, 0.42), (0.11, 0.43, 0.42))
        front = (STRIP_X, y)
        way = [SNUG_IN, (STRIP_X, GAP_Y), front]
    else:
        y = v
        root, yaw, top = (STOOL_X, y), -90.0, 0.56
        feet = ((-0.12, 0.42, 0.42), (0.12, 0.40, 0.42))
        front = (STOOL_X, y + (-0.42 if y > GAP_Y else 0.42))     # beside the stool, in the gap
        way = [SNUG_IN, front]
    return dict(root=root, yaw=yaw, z=top + 0.08 - 0.93, feet=feet, front=front, way=way, table=tb, kind=kind)


PUB = {k: pub_seat(k) for k in GUESTS}


def house_way(a):
    """From a spot in the dining room (an aisle or a sideboard) to the snug."""
    x, y = a[:2]
    if x > 8.8:                                  # east side: round the south end of the table
        return [(x, y), (10.35, y), (10.35, 4.15), (7.70, 3.85)] + HOUSE_SPINE
    return [(x, y), (7.25, y), (7.25, 4.25)] + HOUSE_SPINE


def to_wc(k):
    d = WC_DOOR[LOOKS[k]["sex"]]
    return [SNUG_IN, (3.90, HALL_Y), (-2.75, HALL_Y), (-3.15, d)], (-4.05, d)


ARRIVE_T0, ARRIVE_GAP = 75.0, 1.8            # moving as a group: about 1.7 m apart
CHAIR_OUT = 0.40                            # how far a chair is drawn back to sit down / get up

COURSES = [
    dict(key="salmon", util="fk", eat=1.00, r=0.115),
    dict(key="soup", util="s", eat=0.95, r=0.12),
    dict(key="sole", util="fk", eat=1.10, r=0.135),
    dict(key="sorbet", util="s", eat=0.55, r=0.09),
    dict(key="beef", util="fk", eat=1.45, r=0.14),
    dict(key="cheese", util="fk", eat=0.90, r=0.125),
    dict(key="pudding", util="s", eat=1.00, r=0.115),
]
WINES = ("champ", "white", "red", "sweet")
# The white glass stays out through the beef and cheese, the red set just inside
# it, so a guest can have either; guests 2 and 6 take white.
GLASS_SPOT = {"champ": "glass", "white": "glass", "red": "glass2", "sweet": "glass2"}
WHITE_DRINKERS = (2, 6)
POUR = {"champ": 0.66, "white": 0.62, "red": 0.58, "sweet": 0.60}

# --- Looks --------------------------------------------------------------------
TUX = dict(top="f3f1ec", jacket="16161a", lapel="2c2c33", bowtie="0d0d0f", legs="16161a", shoes="0b0b0c",
           sleeves="long", cuffs="f3f1ec")
LOOKS = {
    1: dict(sex="m", skin="e3b393", hair="b9b4ad", moustache=True, **TUX),
    2: dict(sex="f", skin="eac2a3", hair="8a3b1e", hair_style="updo", top="1f5e3f", gown="1f5e3f",
            legs="1f5e3f", shoes="1f5e3f", sleeves="none", neckline=True, collar=False, necklace="efe9dc",
            earrings="efe9dc", lips="a8454b"),
    4: dict(sex="m", skin="c8916e", hair="1a1411", hair_style="slick", **TUX),
    5: dict(sex="f", skin="f0cfb3", hair="d8b56c", hair_style="chignon", top="1c2a4f", gown="1c2a4f",
            legs="1c2a4f", shoes="1c2a4f", sleeves="none", neckline=True, collar=False, necklace="c9a24a",
            earrings="c9a24a", lips="b04a55"),
    6: dict(sex="m", skin="8d5a3b", hair="2a221d", hair_style="bald", beard=True, glasses="1e1e1e", **TUX),
    8: dict(sex="f", skin="d29e7c", hair="1b1512", hair_style="bun", top="6a1424", gown="6a1424",
            legs="6a1424", shoes="6a1424", sleeves="none", neckline=True, collar=False, necklace="d9d4ca",
            earrings="c9a24a", lips="8e2a3a"),
}
TAGS = {1: "DinGa", 2: "DinGb", 4: "DinGd", 5: "DinGe", 6: "DinGf", 8: "DinGh"}
WAITER_LOOK = {
    "W1": dict(sex="m", skin="dcae92", hair="5a4030", top="f4f2ee", vest="141418", bowtie="0d0d0f",
               legs="141418", sleeves="long", apron="f2efe8", gloves="f6f6f2"),
    "W2": dict(sex="f", skin="e8bb9a", hair="3a261a", hair_style="bun", top="f4f2ee", vest="141418",
               bowtie="0d0d0f", legs="141418", sleeves="long", apron="f2efe8", gloves="f6f6f2", lips="a8454b"),
}
WAITER_TAG = {"W1": "DinWa", "W2": "DinWb"}
CHEF_LOOK = dict(sex="m", skin="d39b78", hair="3b2b22", top="f6f4ef", legs="55565c", sleeves="long",
                 buttons="2a2a2a", toque="f7f6f2", neckerchief="b3262e", apron="f2f0ea", collar=True)
CHEF_TAG = "DinChef"

# Waiter hand poses (wrist targets, figure-local).
HAND_REST = {"L": Vector((-0.17, 0.06, 0.87)), "R": Vector((0.17, 0.06, 0.87))}
HAND_CARRY = {"plate": {"L": Vector((-0.17, 0.30, 1.03)), "R": Vector((0.17, 0.30, 1.03))},
              "tray": {"L": Vector((-0.10, 0.28, 1.10))},
              "bottle": {"R": Vector((0.16, 0.24, 1.00))}}
TRAY_CENTRE = Vector((-0.06, 0.39, 1.09))   # tray centre (local) when carried on the left palm
TRAY_DROP = 0.15                             # lowered to a seated guest
TRAY_LOW = Vector((-0.10, 0.30, 1.10 - TRAY_DROP))
TRAY_SLOTS = [Vector((0.13 * math.cos(math.radians(a)), 0.13 * math.sin(math.radians(a)), 0.012))
              for a in (200, 240, 280, 320, 20, 60, 100, 140)]

# Guest poses (wrist targets, figure-local; plate centre is at about (0, 0.52, 1.145)).
REST_G = {"L": Vector((-0.16, 0.33, 1.175)), "R": Vector((0.16, 0.33, 1.175))}
HOLD_G = {"L": Vector((-0.10, 0.37, 1.20)), "R": Vector((0.10, 0.37, 1.20))}
FORK_AT = Vector((-0.05, 0.40, 1.215))
KNIFE_AT = Vector((0.06, 0.40, 1.21))
MOUTH_W = {"L": Vector((-0.06, 0.16, 1.53)), "R": Vector((0.06, 0.16, 1.53))}
MOUTH_SIP = Vector((0.05, 0.20, 1.50))
TOAST_UP = Vector((0.10, 0.44, 1.46))
GESTURE = (Vector((-0.12, 0.38, 1.28)), Vector((-0.08, 0.41, 1.35)))
MOUTH_LOCAL = Vector((0.0, 0.10, 1.665))
STAND_REST = {"L": Vector((-0.17, 0.06, 0.87)), "R": Vector((0.17, 0.06, 0.87))}
FLUTE_STAND = Vector((0.15, 0.24, 1.12))     # flute held at the waist, standing
FLUTE_SEAT = Vector((0.15, 0.30, 1.30))      # and seated (local frame drops with the root)
STAND_GESTURE = (Vector((-0.14, 0.30, 1.22)), Vector((-0.10, 0.34, 1.30)))
LAP = {"L": Vector((-0.14, 0.30, 1.12)), "R": Vector((0.14, 0.30, 1.12))}   # hands in the lap on a sofa
LOUNGE_HOLD = Vector((0.15, 0.30, 1.24))     # a drink held on the sofa
REC_NOW = {}                                 # build(): every figure's solved record, for cross-figure contacts


# --- Corrected targets ----------------------------------------------------------
class CT:
    """A wrist target that build() nudges between solves until the palm lands
    where the handover needs it (want(REC, fi) -> world palm)."""
    __slots__ = ("base", "corr", "tag", "side", "t", "want")

    def __init__(self, base, tag, side, t, want):
        self.base, self.tag, self.side, self.t, self.want = base, tag, side, t, want
        self.corr = Vector((0.0, 0.0, 0.0))

    def __call__(self, t):
        b = self.base(t) if callable(self.base) else self.base
        return b + self.corr


CONTACTS = []


def palm_for(how, spot, grip=0.0):
    """World palm position that puts a prop of this kind on spot."""
    spot = Vector(spot)
    if how == "plate":
        return lambda R, fi: spot - _fwd(R["yaw"][fi]) * 0.07 + Vector((0, 0, 0.016))
    if how == "tray":
        return lambda R, fi: spot - _fwd(R["yaw"][fi]) * 0.06 + Vector((0, 0, 0.014))
    if how == "cutlery":
        return lambda R, fi: spot + Vector((0, 0, 0.004))
    return lambda R, fi: spot + Vector((0, 0, grip))


def palm_on_tray(slot, grip):
    """Palm for a glass on a tray slot while the tray is on this figure's left palm."""
    def f(R, fi):
        rot = Matrix.Rotation(math.radians(R["yaw"][fi]), 3, 'Z')
        tray = Vector(R["palm"]["L"][fi]) + rot @ Vector((0, 0.06, -0.014))
        return tray + rot @ TRAY_SLOTS[slot] + Vector((0, 0, grip))
    return f


def hold_live(keys, t):
    """hold(t), except straight after a corrected (callable) target: repeat the
    callable so the hold follows its corrections."""
    if keys and keys[-1][0] <= t + 1e-9 and callable(keys[-1][1]):
        keys.add(t, keys[-1][1])
    else:
        keys.hold(t)


def _fwd(yaw_deg):
    a = math.radians(yaw_deg)
    return Vector((-math.sin(a), math.cos(a), 0.0))


# --- Sampling and maths -------------------------------------------------------
def sample(keys, n=None, step=None):
    """Value of a Keys track at every frame (or every `step` seconds), one
    pointer pass: the same semantics as rovers_figures.track."""
    n = N if n is None else n
    dt = step or (1.0 / FPS)
    out = [None] * (n + 1)
    m = len(keys)
    i = 1
    k0 = keys[0]
    for fi in range(n + 1):
        t = fi * dt
        if t <= k0[0]:
            v = k0[1]
            out[fi] = v(t) if callable(v) else v
            continue
        while i < m and t > keys[i][0]:
            i += 1
        if i >= m:
            v = keys[-1][1]
            out[fi] = v(t) if callable(v) else v
            continue
        a, b = keys[i - 1], keys[i]
        vb = b[1](t) if callable(b[1]) else b[1]
        if b[0] <= a[0]:
            out[fi] = vb
            continue
        va = a[1](t) if callable(a[1]) else a[1]
        s = (t - a[0]) / (b[0] - a[0])
        if len(a) < 3:
            s = 0.5 - 0.5 * math.cos(math.pi * s)
        out[fi] = va + (vb - va) * s
    return out


def thin(rows, tol):
    """Indices to keep so linear interpolation stays within tol on every row."""
    n = rows.shape[1]
    keep = np.zeros(n, bool)
    keep[0] = keep[-1] = True
    stack = [(0, n - 1)]
    while stack:
        a, b = stack.pop()
        if b - a < 2:
            continue
        s = (np.arange(a + 1, b) - a) / (b - a)
        lin = rows[:, a:a + 1] + (rows[:, b:b + 1] - rows[:, a:a + 1]) * s
        e = np.abs(rows[:, a + 1:b] - lin).max(axis=0)
        j = int(np.argmax(e))
        if e[j] > tol:
            w = a + 1 + j
            keep[w] = True
            stack += [(a, w), (w, b)]
    return np.nonzero(keep)[0]


def qyaw(deg):
    a = np.radians(np.asarray(deg, float)) / 2
    z = np.zeros_like(a)
    return np.stack([np.cos(a), z, z, np.sin(a)], -1)


def qx(deg):
    a = np.radians(np.asarray(deg, float)) / 2
    z = np.zeros_like(a)
    return np.stack([np.cos(a), np.sin(a), z, z], -1)


def qmul(a, b):
    w1, x1, y1, z1 = np.moveaxis(a, -1, 0)
    w2, x2, y2, z2 = np.moveaxis(b, -1, 0)
    return np.stack([w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2, w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
                     w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2, w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2], -1)


def qrot(q, v):
    w = q[..., :1]
    u = q[..., 1:]
    v = np.broadcast_to(np.asarray(v, float), u.shape)
    t = 2 * np.cross(u, v)
    return v + w * t + np.cross(u, t)


def nlerp(a, b, w):
    d = (a * b).sum(-1, keepdims=True)
    b = np.where(d < 0, -b, b)
    q = a + (b - a) * w[..., None]
    return q / np.linalg.norm(q, axis=-1, keepdims=True)


def ease_np(s):
    return 0.5 - 0.5 * np.cos(np.pi * np.clip(s, 0, 1))


class Spine:
    """A waiter's walking line; destinations hang off it on short spurs."""

    def __init__(self, pts):
        self.p = [Vector(p) for p in pts]
        self.L = [0.0]
        for a, b in zip(self.p, self.p[1:]):
            self.L.append(self.L[-1] + (b - a).length)

    def project(self, q):
        q = Vector(q)
        best = None
        for i, (a, b) in enumerate(zip(self.p, self.p[1:])):
            d = b - a
            u = max(0.0, min(1.0, (q - a).dot(d) / d.length_squared))
            c = a + d * u
            e = (q - c).length
            if best is None or e < best[0] - 1e-9:
                best = (e, self.L[i] + u * d.length, c)
        return best[1], best[2]

    def between(self, s0, s1):
        idx = [i for i, L in enumerate(self.L) if min(s0, s1) + 1e-6 < L < max(s0, s1) - 1e-6]
        if s1 < s0:
            idx.reverse()
        return [self.p[i] for i in idx]


SPINES = {w: Spine(p) for w, p in SPINE.items()}


def route(w, a, b):
    sp = SPINES[w]
    s0, p0 = sp.project(a)
    s1, p1 = sp.project(b)
    pts = [Vector(a), p0] + sp.between(s0, s1) + [p1, Vector(b)]
    out = [pts[0]]
    for p in pts[1:-1]:
        if (p - out[-1]).length > 0.15:
            out.append(p)
    if (pts[-1] - out[-1]).length > 0.02:
        out.append(pts[-1])
    elif len(out) > 1:
        out[-1] = pts[-1]
    return [(p.x, p.y) for p in out]


def walk_time(pts, speed):
    if len(pts) < 2:
        return 0.0
    return 0.5 + sum((Vector(b) - Vector(a)).length for a, b in zip(pts, pts[1:])) / speed


# --- The cocktail lounge: route planner and where the guests stand ------------
def _seg_clear(a, b, extra=()):
    """Is the straight walk a->b clear of the lounge furniture (and of any
    extra (x, y, r) circles: people standing about)?"""
    a, b = Vector((a[0], a[1])), Vector((b[0], b[1]))
    d = b - a
    L = d.length
    if L < 1e-6:
        return True
    for x, y, r in list(CK_BLOCK_C) + list(extra):
        c = Vector((x, y))
        u = max(0.0, min(1.0, (c - a).dot(d) / (L * L)))
        if (a + d * u - c).length < r - 1e-6:
            return False
    n = max(2, int(L / 0.05))
    for i in range(1, n):
        p = a + d * (i / n)
        for x1, x2, y1, y2 in CK_BLOCK_B:
            if x1 < p.x < x2 and y1 < p.y < y2:
                return False
    return True


def patio_path(a, b, extra=()):
    """Shortest walk between two points in the cocktail lounge round the
    furniture (a small visibility graph over CK_LANE)."""
    a, b = tuple(a[:2]), tuple(b[:2])
    if _seg_clear(a, b, extra):
        return [a, b]
    nodes = [a, b] + [tuple(p) for p in CK_LANE]
    n = len(nodes)
    dist = [math.inf] * n
    prev = [None] * n
    dist[0] = 0.0
    todo = set(range(n))
    while todo:
        i = min(todo, key=lambda q: dist[q])
        todo.discard(i)
        if i == 1 or dist[i] == math.inf:
            break
        for j in todo:
            if _seg_clear(nodes[i], nodes[j], extra):
                dd = dist[i] + (Vector(nodes[i]) - Vector(nodes[j])).length
                if dd < dist[j]:
                    dist[j], prev[j] = dd, i
    if dist[1] == math.inf:
        raise RuntimeError(f"cocktail lounge: no way from {a} to {b}")
    out, i = [], 1
    while i is not None:
        out.append(nodes[i])
        i = prev[i]
    return list(reversed(out))


# --- The Rovers snug: route planner ---------------------------------------------
# Obstacles already grown by about a body's half width: the two snug tables,
# their stools, the reserved window table's stool, the end bar stool, the bench
# and the bar.
SNUG_BLOCK_C = [(5.35, -12.05, 0.34 + 0.16), (5.35, -13.25, 0.34 + 0.16), (STOOL_X, -12.05, 0.17 + 0.18),
                (STOOL_X, -13.25, 0.17 + 0.18), (4.15, -11.78, 0.17 + 0.18), (3.70, -13.92, 0.18 + 0.20)]
SNUG_BLOCK_B = [(6.02, 7.0, -14.20, -10.9), (0.40, 7.0, -15.0, -14.00)]
SNUG_LANE = [SNUG_IN, (4.75, GAP_Y), GAP_STAND, (STRIP_X, GAP_Y), (STRIP_X, -13.70), (5.65, -13.88),
             (STRIP_X, -11.75), (4.10, -13.40), (4.25, -13.75), (3.90, HALL_Y)]


def _snug_clear(a, b, extra=()):
    a, b = Vector((a[0], a[1])), Vector((b[0], b[1]))
    d = b - a
    L = d.length
    if L < 1e-6:
        return True
    for x, y, r in list(SNUG_BLOCK_C) + list(extra):
        c = Vector((x, y))
        u = max(0.0, min(1.0, (c - a).dot(d) / (L * L)))
        if (a + d * u - c).length < r - 1e-6:
            return False
    n = max(2, int(L / 0.05))
    for i in range(1, n):
        p = a + d * (i / n)
        for x1, x2, y1, y2 in SNUG_BLOCK_B:
            if x1 < p.x < x2 and y1 < p.y < y2:
                return False
    return True


def snug_path(a, b, extra=()):
    """Shortest walk between two spots in and around the snug (a small
    visibility graph over SNUG_LANE); a point inside an obstacle (a seat front,
    a serving spot) is only left or reached along its first/last leg."""
    a, b = tuple(a[:2]), tuple(b[:2])
    if (Vector(a) - Vector(b)).length < 0.03:
        return [a, b]
    if _snug_clear(a, b, extra):
        return [a, b]
    nodes = [a, b] + [tuple(p) for p in SNUG_LANE]
    n = len(nodes)
    dist = [math.inf] * n
    prev = [None] * n
    dist[0] = 0.0
    todo = set(range(n))
    while todo:
        i = min(todo, key=lambda q: dist[q])
        todo.discard(i)
        if i == 1 or dist[i] == math.inf:
            break
        for j in todo:
            if _snug_clear(nodes[i], nodes[j], extra):
                dd = dist[i] + (Vector(nodes[i]) - Vector(nodes[j])).length
                if dd < dist[j]:
                    dist[j], prev[j] = dd, i
    if dist[1] == math.inf:
        raise RuntimeError(f"snug: no way from {a} to {b}")
    out, i = [], 1
    while i is not None:
        out.append(nodes[i])
        i = prev[i]
    return list(reversed(out))


# --- Props --------------------------------------------------------------------
class Prop:
    """Holder events: ("spot", pos, yaw) | ("hand", tag, side, how[, aim]) |
    ("on", tray_prop, slot) | ("hidden",). Child track (food/liquid) and tilt."""

    def __init__(self, name, kind, sub=None):
        self.name, self.kind, self.sub = name, kind, sub
        self.ev = []
        self.fills = []                     # (t0, t1, value) ramps, applied in time order
        self.fill0 = 1.0
        self.tilt = Keys()
        self.grip = 0.0

    def at(self, t, holder):
        self.ev.append((t, holder))

    def ramp(self, t0, t1, v):
        self.fills.append((t0, t1, v))

    def fill_keys(self):
        k = Keys()
        cur = self.fill0
        k.add(0.0, cur, lin=True)
        for t0, t1, v in sorted(self.fills, key=lambda e: e[0]):
            if callable(v):
                v = v(cur)
            k.add(t0, cur, lin=True).add(max(t1, t0 + EPS), v, lin=True)
            cur = v
        k.add(LOOP, cur, lin=True)
        return k.done(), cur

    def holder_at(self, t):
        h = None
        for te, he in sorted(self.ev, key=lambda e: e[0]):
            if te <= t + 1e-9:
                h = he
        return h


GLASS_GRIP = {"champ": 0.10, "white": 0.09, "red": 0.09, "sweet": 0.07, "cognac": 0.05, "whisky": 0.05}
LIQUID = {"champ": "e6cf7e", "white": "e2d68a", "red": "4e0c18", "sweet": "c47a20", "cognac": "a35a18",
          "whisky": "b87a2a"}


class PropSet:
    def __init__(self):
        self.all = []
        self.plates = {}                    # (course, place) -> Prop
        self.glasses = {}                   # (wine, place) -> Prop
        self.cutlery = {}                   # (kind, place) -> Prop
        self.trays = {}
        self.bottles = {}                   # (wine, waiter) -> Prop
        for k in range(1, 9):
            for c in range(len(COURSES)):
                p = self.add(Prop(f"C{c}P{k}", "plate", ("food", COURSES[c]["key"])))
                p.fill0 = 0.0
                self.plates[(c, k)] = p
            for wn in WINES:
                g = self.add(Prop(f"G{wn}{k}", "glass", ("liquid", wn)))
                g.fill0 = 0.0
                g.grip = GLASS_GRIP[wn]
                self.glasses[(wn, k)] = g
        for k in GUESTS:
            for kind in ("fork", "knife", "spoon"):
                self.cutlery[(kind, k)] = self.add(Prop(f"{kind}{k}", "cutlery", kind))
        self.chairs = {k: self.add(Prop(f"Chair{k}", "chair")) for k in range(1, 9)}
        for w in ("W1", "W2"):
            self.trays[w] = self.add(Prop(f"Tray{w}", "tray"))
            for wn in WINES + ("cognac", "whisky"):
                b = self.add(Prop(f"B{wn}{w}", "bottle", wn))
                b.grip = 0.11
                self.bottles[(wn, w)] = b
        # The party's bottles at the waiters' end of the Rovers bar, for top-ups.
        for wn in PUB_BOTTLE:
            b = self.add(Prop(f"B{wn}Pub", "bottle", wn))
            b.grip = 0.11
            self.bottles[(wn, "Pub")] = b
        CF.add_props(self)                  # the café: cups, the chef's café tray, the mime's red
        self.lounge = {}                    # each guest's after-dinner glass
        for k in GUESTS:
            wn = LOUNGE_DRINK[k]
            g = self.add(Prop(f"L{wn}{k}", "glass", ("liquid", wn)))
            g.fill0 = 0.0
            g.grip = GLASS_GRIP[wn]
            self.lounge[k] = g

    def add(self, p):
        self.all.append(p)
        return p


# --- Actors -------------------------------------------------------------------
class Staff:
    def __init__(self, tag, look, start, speed=1.4, z=FLOOR):
        f = Figure(tag, look, loop=LOOP)
        f.twist = Keys()
        f.bow = Keys()
        f.bow.add(0.0, 0.0).add(LOOP, 0.0)
        self.f, self.speed = f, speed
        self.x, self.y, self.yaw = start
        self.t = 0.0
        self.hold = {"L": None, "R": None}
        f.put(0.0, self.x, self.y, self.yaw)
        f.zk.add(0.0, z)
        f.fL.add(0.0, Vector(RF.STAND_FEET[0]))
        f.fR.add(0.0, Vector(RF.STAND_FEET[1]))
        f.vis.add(0.0, 1.0).add(LOOP, 1.0)
        f.twist.add(0.0, 0.0).add(LOOP, 0.0)
        self.hands(0.0)
        self.head(0.0)
        self.tasks = []                     # (t0, t1, label) for the clash scheduler

    def hand_target(self, side):
        return HAND_CARRY.get(self.hold[side], {}).get(side, HAND_REST[side])

    def hands(self, t):
        self.f.L.add(t, self.hand_target("L"))
        self.f.R.add(t, self.hand_target("R"))

    def head(self, t, lean=3, pitch=3, yaw=0):
        self.f.lean.add(t, lean)
        self.f.pitch.add(t, pitch)
        self.f.yaw.add(t, yaw)

    def stay(self, t):
        f = self.f
        f.put(t, self.x, self.y, self.yaw)

    def walk(self, t, pts):
        f = self.f

        def put(tt, x, y, yaw, lin=False):
            f.put(tt, x, y, yaw, lin=lin)
            f.zk.add(tt, floor_z(x, y), lin=True)       # the floor steps up on the way to the pub
        pts = [tuple(p) for p in pts]
        clean = [pts[0]]
        for p in pts[1:]:
            if (Vector(p) - Vector(clean[-1])).length > 0.02:
                clean.append(p)
        pts = clean
        if len(pts) < 2:
            return t
        hs = [heading(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
        put(t, pts[0][0], pts[0][1], self.yaw)
        self.head(t)
        self.hands(t)
        t += max(0.3, abs(((hs[0] - self.yaw) + 180) % 360 - 180) / TURN_RATE)
        put(t, pts[0][0], pts[0][1], hs[0], lin=True)
        cut_prev = 0.0
        sp = self.speed
        for i in range(1, len(pts)):
            a, b = Vector(pts[i - 1]), Vector(pts[i])
            d = (b - a).length
            if i < len(pts) - 1:
                c = Vector(pts[i + 1])
                cut = min(0.3, d / 2, (c - b).length / 2)
                din, dout = (b - a).normalized(), (c - b).normalized()
                t += max(0.05, d - cut_prev - cut) / sp
                pa = b - din * cut
                put(t, pa.x, pa.y, hs[i - 1], lin=True)
                t += max(2 * cut / sp, abs(((hs[i] - hs[i - 1]) + 180) % 360 - 180) / TURN_RATE)
                pb = b + dout * cut
                put(t, pb.x, pb.y, hs[i], lin=True)
                cut_prev = cut
            else:
                t += max(0.05, d - cut_prev) / sp
                put(t, b.x, b.y, hs[i - 1])
        self.x, self.y, self.yaw = pts[-1][0], pts[-1][1], f._yaw
        self.head(t)
        self.hands(t)
        return t

    def turn(self, t, yaw, dur=0.4):
        f = self.f
        dur = max(dur, abs(((yaw - self.yaw) + 180) % 360 - 180) / TURN_RATE)
        f.put(t, self.x, self.y, self.yaw)
        f.put(t + dur, self.x, self.y, yaw)
        self.yaw = f._yaw
        return t + dur

    def face(self, t, pt, dur=0.4):
        return self.turn(t, heading((self.x, self.y), (pt[0], pt[1])), dur)

    def reach(self, t, side, target, dur=0.75, lean=24, pitch=20, bow=0.0):
        keys = self.f.L if side == "L" else self.f.R
        hold_live(keys, t)
        keys.add(t + dur, target)
        self.f.lean.hold(t).add(t + dur, lean)
        self.f.pitch.hold(t).add(t + dur, pitch)
        self.f.bow.hold(t).add(t + dur, bow)
        return t + dur

    def back(self, t, side, dur=0.55, lean=3, pitch=3):
        keys = self.f.L if side == "L" else self.f.R
        keys.add(t + dur, self.hand_target(side))
        self.f.lean.add(t + dur, lean)
        self.f.pitch.add(t + dur, pitch)
        self.f.bow.add(t + dur, 0.0)
        return t + dur

    def contact(self, t, side, base, want):
        ct = CT(base, self.f.tag, side, t, want)
        CONTACTS.append(ct)
        return ct

    def fwd(self):
        a = math.radians(self.yaw)
        return Vector((-math.sin(a), math.cos(a), 0.0))

    def world_wrist(self, spot, lift, reach=0.115):
        d = Vector((spot.x - self.x, spot.y - self.y, 0.0))
        d = d.normalized() if d.length > 1e-6 else self.fwd()
        return Vector((spot.x - d.x * reach, spot.y - d.y * reach, spot.z + lift))

    def take(self, t, side, prop, spot, how, lift=0.05, reach=0.115, lean=26, dur=0.75, bow=0.0):
        ct = self.contact(t + dur, side, self.f.at_world(self.world_wrist(spot, lift, reach)),
                          palm_for(how, spot, prop.grip))
        tc = self.reach(t, side, ct, dur, lean, bow=bow)
        prop.at(tc, ("hand", self.f.tag, side, how))
        self.hold[side] = how
        return tc

    def put_down(self, t, side, prop, spot, yaw, lift=0.05, reach=0.115, lean=26, dur=0.75, bow=0.0, how=None):
        how = how or self.hold[side] or "plate"
        ct = self.contact(t + dur, side, self.f.at_world(self.world_wrist(spot, lift, reach)),
                          palm_for(how, spot, prop.grip))
        tc = self.reach(t, side, ct, dur, lean, bow=bow)
        prop.at(tc, ("spot", spot.copy(), yaw))
        self.hold[side] = None
        return tc


def gaze_yaw(k, target):
    """Total gaze yaw (deg, + = left) from guest k toward a seat or point."""
    pl = PLACES[k]
    if isinstance(target, int):
        tp = PLACES[target]["root"]
    else:
        tp = Vector(target)
    d = Vector((tp.x - pl["root"].x, tp.y - pl["root"].y, 0.0))
    return math.degrees(math.atan2(-d.dot(pl["r"]), d.dot(pl["f"])))


def lounge_pose(k, t=0.0):
    """(root xy, z, yaw, seated) of guest k in their seat in the Rovers snug."""
    pb = PUB[k]
    return pb["root"], pb["z"], pb["yaw"], True


class Guest:
    """Starts on the patio holding a flute; walks in, sits, dines, then goes
    through to the lounge for drinks."""
    stay, walk, turn, face = Staff.stay, Staff.walk, Staff.turn, Staff.face

    def __init__(self, k, rng, lounge=False):
        self.k, self.pl, self.rng = k, PLACES[k], rng
        f = Figure(TAGS[k], LOOKS[k], loop=LOOP)
        f.twist = Keys()
        self.f = f
        self.speed = GUEST_SPEED
        self.seated = [0.0, 0.0]            # at the table (t_down, t_up)
        self.patio = []                     # standing-on-the-patio spans
        self.lounge_t = None
        self.vis_keys = f.vis
        self.walks = []                     # (t0, t1) on their feet in the pub (out to the loo and back)
        self.pub = []                       # (t0, t1) seated in the snug
        self.away = []                      # (t0, t1) out of sight in the loo
        self.drink = False                  # holding the after-dinner drink
        if lounge:                          # the lounge loop: where the dinner left them, drink in hand
            pb = PUB[k]
            (x, y), z, yaw = pb["root"], pb["z"], pb["yaw"]
            self.x, self.y, self.yaw, self.group = x, y, yaw, None
            self.flute = False
            self.drink = True
            self.lounge_t = 0.0
            self.pub.append((0.0, LOOP))
            f.put(0.0, x, y, yaw)
            f.zk.add(0.0, z)
            f.fL.add(0.0, Vector(pb["feet"][0]))
            f.fR.add(0.0, Vector(pb["feet"][1]))
            f.L.add(0.0, LAP["L"].copy())
            f.R.add(0.0, LOUNGE_HOLD.copy())
            f.vis.add(0.0, 1.0)
        else:                               # the dinner: on the patio with a flute
            f.vis.add(0.0, 1.0)
            self.x, self.y, self.yaw, self.group = PATIO[k]
            self.flute = True
            f.put(0.0, self.x, self.y, self.yaw)
            f.zk.add(0.0, FLOOR)
            f.fL.add(0.0, Vector(RF.STAND_FEET[0]))
            f.fR.add(0.0, Vector(RF.STAND_FEET[1]))
            f.L.add(0.0, STAND_REST["L"].copy())
            f.R.add(0.0, FLUTE_STAND.copy())
        self.busy = {"L": [], "R": []}
        self.over = []                      # (t0, t1, yaw_total|None, pitch, lean, prio)
        self.waiter_at = []                 # (t0, t1) a waiter is working at this place
        self.eat_windows = []
        self.bites = 0
        self.tasks = []

    def posture(self, t):
        """'table', 'sofa', 'stand' (patio or by the fire) or 'walk' at time t."""
        a, b = self.seated
        if a <= t < b:
            return "table"
        if any(p0 <= t < p1 for p0, p1 in self.patio):
            return "stand"
        if any(p0 <= t < p1 for p0, p1 in self.pub):
            return "sofa" if PUB[self.k]["kind"] == "bench" else "stool"
        return "walk"

    # Walking (Staff.walk calls these).
    def head(self, t, **kw):
        pass

    def hands(self, t):
        self.f.L.add(t, STAND_REST["L"].copy())
        self.f.R.add(t, FLUTE_STAND.copy() if (self.flute or self.drink) else STAND_REST["R"].copy())

    # The chair and where to stand round it.
    def chair_pos(self, out):
        pl = self.pl
        return Vector((CHAIR_X[pl["side"]], pl["y"], 0.0)) - pl["f"] * (CHAIR_OUT if out else 0.0)

    def spots(self):
        """behind the chair (in), behind it once drawn out, round its south
        side, and in front of the drawn-out seat."""
        pl = self.pl
        cx, y, fx = CHAIR_X[pl["side"]], pl["y"], pl["f"].x
        return dict(behind=(cx - fx * 0.64, y), behind_out=(cx - fx * 1.04, y),
                    side=(cx - fx * 0.72, y - 0.40), side2=(cx - fx * 0.02, y - 0.38), front=(cx - fx * 0.02, y))

    def dining_part(self):
        """From inside the French door to this guest's side of the table: the
        west aisle, or round the north end of the table to the east aisle."""
        pl = self.pl
        if pl["side"] == "W":
            return [CK_DOOR_IN, (7.25, 7.90), (7.25, pl["y"])]
        return [CK_DOOR_IN, (7.30, CK_NORTH_AISLE), (10.35, CK_NORTH_AISLE), (10.35, pl["y"])]

    def route_in(self):
        """Patio spot -> the French door -> the guest's aisle, level with their chair."""
        x, y = PATIO[self.k][:2]
        return patio_path((x, y), CK_DOOR_OUT, self.others()) + self.dining_part()

    def others(self):
        """Everyone else's spot before dinner, to keep a walk clear of."""
        return [(p[0], p[1], 0.45) for q, p in PATIO.items() if q != self.k]

    def route_out(self, dest, extra=()):
        """From level with the chair (in the aisle) out to a spot in the lounge."""
        return list(reversed(self.dining_part())) + patio_path(CK_DOOR_OUT, dest, extra)

    def rail_local(self, out):
        """Wrist target on the chair's top rail, from where the guest stands
        behind it (same relative spot before and after the pull)."""
        return Vector((-0.10, 0.42, 0.90))

    def sit(self, t, chair):
        """In front of the drawn-out chair, facing the table: lower onto the
        seat, then draw in with the chair."""
        f, pl = self.f, self.pl
        sp = self.spots()
        seat_out = self.chair_pos(True) - pl["f"] * 0.05
        seat_in = self.chair_pos(False) - pl["f"] * 0.05
        f.put(t, sp["front"][0], sp["front"][1], self.yaw)
        f.zk.add(t, FLOOR)
        f.fL.add(t, Vector(RF.STAND_FEET[0]))
        f.fR.add(t, Vector(RF.STAND_FEET[1]))
        f.L.hold(t)
        f.R.hold(t)
        t1 = t + 1.5
        f.put(t1, seat_out.x, seat_out.y, self.yaw)
        f.zk.add(t1, Z_SEATED)
        f.fL.add(t1, Vector(SEAT_FEET[0]))
        f.fR.add(t1, Vector(SEAT_FEET[1]))
        f.L.add(t + 0.8, Vector((-0.22, -0.02, 1.05))).add(t1, Vector((-0.22, 0.10, 1.00)))
        f.R.add(t1, FLUTE_SEAT.copy())
        self.over.append((t, t + 0.8, 0.0, 14, 24, 2))
        self.over.append((t + 0.8, t1 + 0.4, 0.0, 8, 12, 2))
        t2 = t1 + 0.4
        chair.at(t2, ("glide", self.chair_pos(True), self.chair_pos(False), t2, t2 + 1.2, pl["yaw"]))
        chair.at(t2 + 1.2, ("spot", self.chair_pos(False), pl["yaw"]))
        f.put(t2, seat_out.x, seat_out.y, self.yaw)
        f.put(t2 + 1.2, seat_in.x, seat_in.y, self.yaw)
        f.L.add(t2, Vector((-0.22, 0.10, 1.00))).add(t2 + 1.2, Vector((-0.22, 0.10, 1.00)))
        f.L.add(t2 + 1.8, REST_G["L"].copy())
        self.over.append((t2, t2 + 1.2, 0.0, 10, 14, 2))
        return t2 + 1.8

    def stand(self, t, chair):
        """Push back with the chair, rise to stand in front of it."""
        f, pl = self.f, self.pl
        sp = self.spots()
        seat_out = self.chair_pos(True) - pl["f"] * 0.05
        seat_in = self.chair_pos(False) - pl["f"] * 0.05
        f.put(t, seat_in.x, seat_in.y, self.yaw)
        f.zk.add(t, Z_SEATED)
        f.fL.add(t, Vector(SEAT_FEET[0]))
        f.fR.add(t, Vector(SEAT_FEET[1]))
        f.L.hold(t).add(t + 0.6, REST_G["L"] + Vector((0.0, 0.03, 0.0)))
        t1 = t + 0.6
        chair.at(t1, ("glide", self.chair_pos(False), self.chair_pos(True), t1, t1 + 1.2, pl["yaw"]))
        chair.at(t1 + 1.2, ("spot", self.chair_pos(True), pl["yaw"]))
        f.put(t1, seat_in.x, seat_in.y, self.yaw)
        f.put(t1 + 1.2, seat_out.x, seat_out.y, self.yaw)
        f.zk.add(t1 + 1.2, Z_SEATED)
        f.fL.add(t1 + 1.2, Vector(SEAT_FEET[0]))
        f.fR.add(t1 + 1.2, Vector(SEAT_FEET[1]))
        f.L.add(t1 + 1.2, Vector((-0.20, 0.10, 1.02)))
        self.over.append((t, t1 + 1.2, 0.0, 10, 14, 2))
        t2 = t1 + 1.4
        f.put(t2 + 1.5, sp["front"][0], sp["front"][1], self.yaw)
        f.zk.add(t2 + 1.5, FLOOR)
        f.fL.add(t2 + 1.5, Vector(RF.STAND_FEET[0]))
        f.fR.add(t2 + 1.5, Vector(RF.STAND_FEET[1]))
        f.L.add(t2 + 0.7, Vector((-0.22, -0.02, 1.05))).add(t2 + 1.5, STAND_REST["L"].copy())
        f.R.add(t2 + 1.5, FLUTE_STAND.copy() if self.flute else STAND_REST["R"].copy())
        self.over.append((t2, t2 + 0.8, 0.0, 14, 24, 2))
        self.over.append((t2 + 0.8, t2 + 1.5, 0.0, 6, 3, 2))
        self.x, self.y = sp["front"]
        return t2 + 1.5

    def pull(self, t, chair, out):
        """Hold the top rail and draw the chair out (or push it in), the
        guest stepping back (or forward) with it."""
        f, pl = self.f, self.pl
        sp = self.spots()
        a, b = (sp["behind"], sp["behind_out"]) if out else (sp["behind_out"], sp["behind"])
        p0, p1 = self.chair_pos(not out), self.chair_pos(out)
        rail = self.rail_local(out)
        f.L.hold(t).add(t + 0.7, rail)
        self.over.append((t, t + 2.6, 0.0, 26, 18, 2))
        t1 = t + 0.7
        chair.at(t1, ("glide", p0, p1, t1, t1 + 1.1, pl["yaw"]))
        chair.at(t1 + 1.1, ("spot", p1, pl["yaw"]))
        f.put(t1, a[0], a[1], self.yaw)
        f.put(t1 + 1.1, b[0], b[1], self.yaw)
        f.L.add(t1 + 1.1, rail).add(t1 + 1.7, STAND_REST["L"].copy())
        self.x, self.y = b
        return t1 + 1.7

    def arrive(self, t, P):
        """Patio to seated with the flute set down. Returns the time."""
        k, pl = self.k, self.pl
        chair = P.chairs[k]
        t0 = t
        self.stay(t)
        sp = self.spots()
        t = self.walk(t, self.route_in() + [sp["behind"]])
        t = self.turn(t, pl["yaw"])
        t = self.pull(t, chair, True)
        t = self.walk(t, [sp["behind_out"], sp["side"], sp["side2"], sp["front"]])
        t = self.turn(t, pl["yaw"])
        t = self.sit(t, chair)
        self.seated = [t, None]
        self.mark("L", t0, t)
        self.mark("R", t0, t)
        # Set the flute at the place.
        gp = pl["glass"]
        flute = P.glasses[("champ", k)]
        grip = self.loc(gp) + Vector((-0.02, -0.06, flute.grip - 0.01))
        self.f.R.hold(t).add(t + 1.0, self.contact(t + 1.0, "R", grip, palm_for("glass", gp, flute.grip)))
        flute.at(t + 1.0, ("spot", gp.copy(), pl["yaw"]))
        self.f.R.add(t + 1.7, REST_G["R"].copy())
        self.over.append((t, t + 1.2, gaze_yaw(k, gp), 16, 17, 3))
        self.flute = False
        self.mark("R", t, t + 1.8)
        self.patio.append((0.0, t0))
        self.tasks.append((t0, t + 1.8, "arrive"))
        return t + 1.8

    def depart(self, t, P):
        """Take the flute, get up, push the chair in, walk out to the group."""
        k, pl = self.k, self.pl
        chair = P.chairs[k]
        t0 = t
        gp = pl["glass"]
        flute = P.glasses[("champ", k)]
        grip = self.loc(gp) + Vector((-0.02, -0.06, flute.grip - 0.01))
        self.f.R.hold(t).add(t + 1.0, self.contact(t + 1.0, "R", grip, palm_for("glass", gp, flute.grip)))
        flute.at(t + 1.0, ("hand", self.f.tag, "R", "glass"))
        self.f.R.add(t + 1.7, FLUTE_SEAT.copy())
        self.over.append((t, t + 1.2, gaze_yaw(k, gp), 16, 17, 3))
        self.flute = True
        self.seated[1] = t
        t += 1.9
        self.yaw = self.f._yaw
        t = self.stand(t, chair)
        sp = self.spots()
        t = self.walk(t, [sp["front"], sp["side2"], sp["side"], sp["behind_out"]])
        t = self.turn(t, pl["yaw"])
        t = self.pull(t, chair, False)
        px, py, pyaw, _g = PATIO[k]
        t = self.walk(t, [(self.x, self.y)] + self.route_out((px, py)))
        t = self.turn(t, pyaw)
        self.mark("L", t0, t)
        self.mark("R", t0, t)
        self.patio.append((t, LOOP))
        self.tasks.append((t0, t, "depart"))
        return t

    # --- After dinner: the lounge ---------------------------------------------
    def lounge_pose(self, t=0.0):
        return lounge_pose(self.k, t)

    def lounge_hold(self):
        return LOUNGE_HOLD

    world_wrist, fwd = Staff.world_wrist, Staff.fwd

    def to_pub(self, t, P):
        """Get up, push the chair in, walk out through the house and across the
        balcony to the Rovers, and sit in the snug. Returns the time settled."""
        k, pl = self.k, self.pl
        chair = P.chairs[k]
        t0 = t
        self.seated[1] = t
        self.yaw = self.f._yaw
        t = self.stand(t, chair)
        sp = self.spots()
        t = self.walk(t, [sp["front"], sp["side2"], sp["side"], sp["behind_out"]])
        t = self.turn(t, pl["yaw"])
        t = self.pull(t, chair, False)
        t = self.walk(t, house_way((self.x, self.y)) + PUB[k]["way"][1:])
        t = self.pub_sit(t)
        self.mark("L", t0, t)
        self.mark("R", t0, t)
        self.tasks.append((t0, t, "to pub"))
        self.lounge_t = t
        return t

    def pub_sit(self, t):
        """From the floor spot in front of (or beside) the seat: lower onto it."""
        f, pb = self.f, PUB[self.k]
        yaw = pb["yaw"]
        t = self.turn(t, yaw)
        (fx, fy), (rx, ry) = pb["front"], pb["root"]
        f.put(t, fx, fy, yaw)
        f.zk.add(t, RV_FLOOR)
        f.fL.add(t, Vector(RF.STAND_FEET[0]))
        f.fR.add(t, Vector(RF.STAND_FEET[1]))
        f.L.hold(t)
        f.R.hold(t)
        t1 = t + 1.7
        f.put(t1, rx, ry, yaw)
        f.zk.add(t1, pb["z"])
        f.fL.add(t1, Vector(pb["feet"][0]))
        f.fR.add(t1, Vector(pb["feet"][1]))
        f.L.add(t + 0.9, Vector((-0.24, -0.04, 1.02))).add(t1 + 0.4, LAP["L"].copy())
        if self.drink:
            f.R.add(t1 + 0.4, LOUNGE_HOLD.copy())
        else:
            f.R.add(t + 0.9, Vector((0.24, -0.04, 1.02))).add(t1 + 0.4, LAP["R"].copy())
        self.over.append((t, t + 0.9, 0.0, 12, 22, 2))
        self.over.append((t + 0.9, t1 + 0.6, 0.0, 6, -2, 2))
        self.x, self.y, self.yaw = rx, ry, yaw
        self.pub.append((t1, LOOP))
        return t1 + 0.6

    def pub_stand(self, t):
        """Up off the seat onto the floor spot in front of (or beside) it."""
        f, pb = self.f, PUB[self.k]
        yaw = pb["yaw"]
        (fx, fy), (rx, ry) = pb["front"], pb["root"]
        p0, _p1 = self.pub[-1]
        self.pub[-1] = (p0, t)
        f.put(t, rx, ry, yaw)
        f.zk.add(t, pb["z"])
        f.fL.add(t, Vector(pb["feet"][0]))
        f.fR.add(t, Vector(pb["feet"][1]))
        f.L.hold(t)
        f.R.hold(t)
        t1 = t + 1.6
        f.put(t1, fx, fy, yaw)
        f.zk.add(t1, RV_FLOOR)
        f.fL.add(t1, Vector(RF.STAND_FEET[0]))
        f.fR.add(t1, Vector(RF.STAND_FEET[1]))
        f.L.add(t + 0.7, Vector((-0.24, -0.04, 1.02))).add(t1, STAND_REST["L"].copy())
        f.R.add(t1, FLUTE_STAND.copy() if self.drink else STAND_REST["R"].copy())
        self.over.append((t, t + 0.7, 0.0, 12, 20, 2))
        self.over.append((t + 0.7, t1, 0.0, 6, 3, 2))
        self.x, self.y, self.yaw = fx, fy, yaw
        return t1 + 0.2

    def glass_to(self, t, glass, spot, down):
        """Standing, facing a table: set the drink on spot (down) or pick it up."""
        f = self.f
        f.R.hold(t)
        tc = t + 0.9
        f.R.add(tc, self.contact(tc, "R", f.at_world(self.world_wrist(spot, glass.grip, 0.05)),
                                 palm_for("glass", spot, glass.grip)))
        if down:
            glass.at(tc, ("spot", spot.copy(), self.yaw))
            self.drink = False
        else:
            glass.at(tc, ("hand", f.tag, "R", "glass"))
            self.drink = True
        f.R.add(tc + 0.8, FLUTE_STAND.copy() if self.drink else STAND_REST["R"].copy())
        self.over.append((t, tc + 0.5, 0.0, 26, 18, 3))
        return tc + 0.9

    def wc_trip(self, t, P, away):
        """Up from the snug, glass down on the table by the gap, out along the
        hall line to the Gents or the Ladies (through the door into the wall,
        out of sight), back, glass up, sit. Returns the time they are back."""
        k, pb = self.k, PUB[self.k]
        glass = P.lounge[k]
        f = self.f
        t0 = t
        self.stay(t)
        t = self.pub_stand(t)
        out1 = [pb["front"], (STRIP_X, GAP_Y), GAP_STAND] if pb["kind"] == "bench" else [pb["front"], GAP_STAND]
        t = self.walk(t, out1)
        face = 0.0 if pb["table"] == "N" else 180.0
        t = self.turn(t, face)
        t = self.glass_to(t, glass, GLASS_DOWN[pb["table"]], True)
        out, door = to_wc(k)
        w0 = t
        t = self.walk(t, [GAP_STAND] + out)
        t = self.walk(t, [out[-1], door])
        f.vis.add(t, 1.0).add(t + 0.1, 0.001)
        self.away.append((t, t + away))
        t += away
        f.vis.add(t - 0.1, 0.001).add(t, 1.0)
        t = self.walk(t, [door] + list(reversed(out)) + [GAP_STAND])
        t = self.turn(t, face)
        self.walks.append((w0, t))
        t = self.glass_to(t, glass, GLASS_DOWN[pb["table"]], False)
        back = [GAP_STAND, (STRIP_X, GAP_Y), pb["front"]] if pb["kind"] == "bench" else [GAP_STAND, pb["front"]]
        t = self.walk(t, back)
        t = self.pub_sit(t)
        self.walks[-1] = (w0 - 6.0, t)
        self.mark("L", t0, t)
        self.mark("R", t0, t)
        self.tasks.append((t0, t, "wc"))
        return t

    def out_of_seat(self, t):
        """Is this guest up and about (not in their seat) at t?"""
        return not any(p0 <= t < p1 for p0, p1 in self.pub)

    def local_at(self, w, t=0.0):
        """World point -> local, for the guest where they stand in the lounge."""
        (x, y), z, yaw, _seated = self.lounge_pose(t)
        d = Vector((w[0] - x, w[1] - y, 0.0))
        loc = Matrix.Rotation(-math.radians(yaw), 3, 'Z') @ d
        return Vector((loc.x, loc.y, w[2] - z))

    def take_from_tray(self, t, drink, staff, slot, drop=0.0):
        """Reach for a drink standing on the waiter's tray (held drop lower than
        carried). Returns the contact time."""
        a = math.radians(staff.yaw)
        rot = Matrix.Rotation(a, 3, 'Z')
        est = Vector((staff.x, staff.y, floor_z(staff.x, staff.y) - drop)) + rot @ (TRAY_CENTRE + TRAY_SLOTS[slot]) + \
            Vector((0, 0, drink.grip))
        wtag = staff.f.tag

        def want(R, fi, wtag=wtag, slot=slot, grip=drink.grip):
            W = REC_NOW[wtag]
            r = Matrix.Rotation(math.radians(W["yaw"][fi]), 3, 'Z')
            tray = Vector(W["palm"]["L"][fi]) + r @ Vector((0, 0.06, -0.014))
            return tray + r @ TRAY_SLOTS[slot] + Vector((0, 0, grip))
        keys = self.f.R
        keys.hold(t)
        tc = t + 1.0
        keys.add(tc, self.contact(tc, "R", self.local_at(est, t) + Vector((-0.02, -0.05, -0.01)), want))
        keys.add(tc + 1.0, self.lounge_hold().copy())
        drink.at(tc, ("hand", self.f.tag, "R", "glass"))
        self.over.append((t, tc + 0.6, self.yaw_to((staff.x, staff.y), t), 16, None, 3))
        self.mark("R", t, tc + 1.0)
        return tc

    def yaw_to(self, pt, t=0.0):
        (x, y), _z, yaw, _s = self.lounge_pose(t)
        d = Vector((pt[0] - x, pt[1] - y, 0))
        f = _fwd(yaw)
        r = Vector((f.y, -f.x, 0))
        return math.degrees(math.atan2(-d.dot(r), d.dot(f)))

    def offer(self, t, staff_xy, dur):
        """Hold the glass out toward the waiter for a top-up (t .. t + dur)."""
        (x, y), z, _yaw, seated = self.lounge_pose(t)
        d = Vector((staff_xy[0] - x, staff_xy[1] - y, 0)).normalized()
        w = Vector((x, y, 0)) + d * 0.36 + Vector((0, 0, 0.95 if seated else 1.15))
        hold = self.lounge_hold()
        self.f.R.hold(t).add(t + 0.8, self.local_at(w, t)).add(t + dur - 0.6, self.local_at(w, t)) \
            .add(t + dur + 0.2, hold.copy())
        self.over.append((t, t + dur, self.yaw_to(staff_xy, t), 14, None, 3))
        self.mark("R", t, t + dur + 0.2)
        return w

    def sip_held(self, t, glass, amount, hold=None):
        """With a glass in hand (patio flute, lounge drink): a sip."""
        hold = hold if hold is not None else FLUTE_STAND
        keys = self.f.R
        keys.hold(t).add(t + 0.9, MOUTH_SIP.copy()).add(t + 2.2, MOUTH_SIP.copy()).add(t + 3.1, hold.copy())
        glass.tilt.add(t + 0.7, 0).add(t + 1.2, 50).add(t + 1.9, 50).add(t + 2.4, 0)
        glass.ramp(t + 1.2, t + 1.9, lambda cur, a=amount: max(0.08, cur - a))
        self.over.append((t + 0.9, t + 2.2, None, -12, 2, 3))
        self.mark("R", t, t + 3.2)
        return t + 3.2

    def hk(self, side):
        return self.f.L if side == "L" else self.f.R

    def loc(self, w):
        d = Vector(w) - self.pl["root"]
        return Vector((d.dot(self.pl["r"]), d.dot(self.pl["f"]), w[2] - Z_SEATED))

    def free(self, side, t0, t1):
        return all(t1 <= a or t0 >= b for a, b in self.busy[side])

    def contact(self, t, side, base, want):
        ct = CT(base, self.f.tag, side, t, want)
        CONTACTS.append(ct)
        return ct

    def mark(self, side, t0, t1):
        self.busy[side].append((t0, t1))

    def mouth_world(self):
        m = MOUTH_LOCAL
        return self.pl["root"] + self.pl["r"] * m.x + self.pl["f"] * m.y + Vector((0, 0, Z_SEATED + m.z))

    def cutlery_hand(self, side, prop, plate_pt):
        return ("hand", self.f.tag, side, "cutlery", (plate_pt.copy(), self.mouth_world()))

    def eat(self, P, c, t0, t1):
        """One course from picking up the cutlery at t0 to putting it down by t1."""
        rng = self.rng
        k = self.k
        util = COURSES[c]["util"]
        plate = P.plates[(c, k)]
        pp = self.pl["plate"]
        food_pt = pp + Vector((0, 0, 0.10 if COURSES[c]["key"] == "sorbet" else 0.03))
        uts = [("L", P.cutlery[("fork", k)]), ("R", P.cutlery[("knife", k)])] if util == "fk" else \
            [("R", P.cutlery[("spoon", k)])]
        rest = {"fork": self.pl["fork"], "knife": self.pl["knife"], "spoon": self.pl["spoon"]}
        for side, u in uts:
            keys = self.hk(side)
            keys.hold(t0)
            spot = rest[u.sub]
            keys.add(t0 + 0.8, self.contact(t0 + 0.8, side, self.loc(spot) + Vector((0.0, -0.07, 0.05)),
                                            palm_for("cutlery", spot)))
            u.at(t0 + 0.8, self.cutlery_hand(side, u, food_pt))
            keys.add(t0 + 1.5, HOLD_G[side].copy())
            self.mark(side, t0, t1)
        if util == "s":
            self.hk("L").hold(t0).add(t0 + 1.0, REST_G["L"] + Vector((0.02, 0.02, 0)))
            self.mark("L", t0, t1)                   # its keys at both ends: no gestures in between
        self.over.append((t0, t0 + 1.2, 0.0, 20, 14, 2))
        t = t0 + 2.4
        bite_times = []
        sorbet = COURSES[c]["key"] == "sorbet"
        td = t1 - 2.4
        while True:
            cut = util == "fk" and rng.random() < 0.5
            if t + (2.3 if cut else 0.0) + 2.9 > td - 0.2:
                break
            if cut:
                kk = self.hk("R")
                kk.hold(t).add(t + 0.5, KNIFE_AT.copy())
                for q in range(4):
                    kk.add(t + 0.75 + q * 0.3, KNIFE_AT + Vector((0, 0.025 if q % 2 == 0 else -0.02, 0)))
                kk.add(t + 2.1, HOLD_G["R"].copy())
                self.hk("L").hold(t).add(t + 0.5, FORK_AT.copy()).add(t + 1.8, FORK_AT.copy()) \
                    .add(t + 2.1, HOLD_G["L"].copy())
                self.over.append((t, t + 2.1, 0.0, 26, 17, 2))
                t += 2.3
            side = "L" if util == "fk" else "R"
            kk = self.hk(side)
            at = FORK_AT.copy() if side == "L" else KNIFE_AT + Vector((-0.04, 0.0, 0.03 + (0.06 if sorbet else 0)))
            kk.hold(t).add(t + 0.5, at).add(t + 0.85, at + Vector((0, -0.012, 0.012)))
            kk.add(t + 1.65, MOUTH_W[side].copy()).add(t + 2.1, MOUTH_W[side].copy()).add(t + 2.8, HOLD_G[side].copy())
            self.over.append((t, t + 0.95, 0.0, 26, 17, 2))
            self.over.append((t + 0.95, t + 2.2, 0.0, 4, 13, 2))
            bite_times.append(t + 0.85)
            t += 2.8 + rng.uniform(4.0, 7.5)
        n = max(1, len(bite_times))
        for i, tb in enumerate(bite_times):
            plate.ramp(tb, tb + 0.25, lambda cur, n=n: max(0.12, cur - 0.88 / n))
        self.bites += len(bite_times)
        for side, u in uts:
            keys = self.hk(side)
            keys.hold(td)
            spot = rest[u.sub]
            keys.add(td + 0.8, self.contact(td + 0.8, side, self.loc(spot) + Vector((0.0, -0.07, 0.05)),
                                            palm_for("cutlery", spot)))
            u.at(td + 0.8, ("spot", spot.copy(), self.pl["yaw"]))
            keys.add(td + 1.6, REST_G[side].copy())
        if util == "s":
            self.hk("L").add(td + 1.6, REST_G["L"].copy())
        self.over.append((td, td + 1.4, 0.0, 22, 14, 2))
        self.eat_windows.append((t0, t1))

    def sip(self, t, glass, amount, toast=False):
        keys = self.hk("R")
        gp = self.pl[GLASS_SPOT[glass.sub[1]]]
        grip = self.loc(gp) + Vector((-0.02, -0.06, glass.grip - 0.01))
        keys.hold(t)
        tc = t + 0.9
        keys.add(tc, self.contact(tc, "R", grip, palm_for("glass", gp, glass.grip)))
        glass.at(tc, ("hand", self.f.tag, "R", "glass"))
        if toast:
            keys.add(tc + 0.9, TOAST_UP.copy()).add(tc + 2.6, TOAST_UP.copy())
            t2 = tc + 2.6
            self.over.append((tc + 0.6, tc + 2.6, gaze_yaw(self.k, (TX, TY)) * 0.6, -6, 14, 3))
        else:
            t2 = tc
        keys.add(t2 + 0.9, MOUTH_SIP.copy()).add(t2 + 2.2, MOUTH_SIP.copy()) \
            .add(t2 + 3.1, self.contact(t2 + 3.1, "R", grip, palm_for("glass", gp, glass.grip)))
        glass.tilt.add(t2 + 0.7, 0).add(t2 + 1.2, 50).add(t2 + 1.9, 50).add(t2 + 2.4, 0)
        glass.ramp(t2 + 1.2, t2 + 1.9, lambda cur, a=amount: max(0.08, cur - a))
        glass.at(t2 + 3.1, ("spot", gp.copy(), self.pl["yaw"]))
        keys.add(t2 + 3.8, REST_G["R"].copy())
        gy = gaze_yaw(self.k, gp)
        self.over.append((t, tc, gy, 18, 18, 3))
        self.over.append((t2 + 0.9, t2 + 2.2, 0.0, -12, 8, 3))
        self.over.append((t2 + 2.2, t2 + 3.3, gy, 15, 17, 3))
        self.mark("R", t, t2 + 3.8)
        return t2 + 3.8


# --- Conversation -------------------------------------------------------------
EDGES = ([((1, 2), 3.0), ((2, 3), 3.0), ((3, 4), 3.0), ((5, 6), 3.0), ((6, 7), 3.0), ((7, 8), 3.0),
          ((1, 5), 3.0), ((2, 6), 3.0), ((4, 8), 3.0),
          ((1, 6), 1.4), ((2, 5), 1.4), ((2, 7), 1.4), ((3, 6), 1.4), ((3, 8), 1.4), ((4, 7), 1.4)])


def patio_talk(rng, t0, t1):
    """Per guest: group chat on the patio (targets ("patio", k))."""
    segs = {k: [] for k in GUESTS}
    for gname, (_c, members) in PATIO_GROUPS.items():
        ms = list(members)
        t = t0
        while t < t1 - 1.0:
            dur = min(rng.uniform(3.0, 6.0), t1 - t)
            spk = rng.choice(ms)
            for k in ms:
                if k == spk:
                    segs[k].append((t, t + dur, ("patio", rng.choice([m for m in ms if m != k])), "talk"))
                else:
                    segs[k].append((t, t + dur, ("patio", spk), "listen"))
            if rng.random() < 0.15 and t + dur + 2.0 < t1:
                for k in ms:
                    segs[k].append((t + dur, t + dur + 2.0, ("patio", spk if k != spk else ms[0]), "laugh"))
                dur += 2.0
            t += dur
    return segs


def conversation(rng, t_start, t_end):
    """Per guest at the table: [(t0, t1, target, role)], role in talk/listen/laugh."""
    segs = {k: [] for k in GUESTS}
    t = t_start
    moment = t + rng.uniform(70, 110)
    while t < t_end - 4.0:
        if t >= moment:
            spk = rng.choice(GUESTS)
            dur = rng.uniform(9, 13)
            end = min(t + dur, t_end - 4.0)
            for k in GUESTS:
                if k == spk:
                    sub = t
                    while sub < end - 0.5:
                        tgt = rng.choice([g for g in range(1, 9) if g != k])
                        segs[k].append((sub, min(sub + 2.5, end), tgt, "talk"))
                        sub += 2.5
                else:
                    segs[k].append((t, end, spk, "listen"))
            if end + 2.2 < t_end - 4.0:
                for k in GUESTS:
                    segs[k].append((end, end + 2.2, spk if k != spk else rng.choice(GUESTS), "laugh"))
                end += 2.2
            t = end
            moment = t + rng.uniform(80, 130)
            continue
        dur = rng.uniform(7, 13)
        end = min(t + dur, t_end - 4.0)
        order = sorted(EDGES, key=lambda e: -rng.random() ** (1.0 / (e[1] * (0.8 if set(e[0]) & set(EMPTY) else 1))))
        used, pairs = set(), []
        for (a, b), _w in order:
            if a in used or b in used:
                continue
            pairs.append((a, b))
            used |= {a, b}
        for a, b in pairs:
            first = rng.random() < 0.5
            sub = t
            while sub < end - 0.4:
                ln = min(rng.uniform(2.5, 4.5), end - sub)
                for g, other, talking in ((a, b, first), (b, a, not first)):
                    if g in segs:
                        segs[g].append((sub, sub + ln, other, "talk" if talking else "listen"))
                first = not first
                sub += ln
            if rng.random() < 0.3 and end + 1.8 < t_end - 4.0:
                for g, other in ((a, b), (b, a)):
                    if g in segs:
                        segs[g].append((end - 1.8, end, other, "laugh"))
        for g in GUESTS:
            if g not in used:                        # listen in on a neighbouring pair
                near = min((p for p in pairs if g not in p),
                           key=lambda p: min((PLACES[g]["root"] - PLACES[q]["root"]).length for q in p))
                tgt = min(near, key=lambda q: (PLACES[g]["root"] - PLACES[q]["root"]).length)
                segs[g].append((t, end, tgt, "listen"))
        t = end
    return segs


def target_yaw(k, tgt, g=None, t=0.0):
    if isinstance(tgt, tuple) and tgt[0] == "pos":
        return g.yaw_to(tgt[1], t)
    if isinstance(tgt, tuple) and tgt[0] == "patio":
        x, y, yw, _g = PATIO[k]
        tx, ty = PATIO[tgt[1]][:2]
        d = Vector((tx - x, ty - y, 0))
        f = _fwd(yw)
        r = Vector((f.y, -f.x, 0))
        return math.degrees(math.atan2(-d.dot(r), d.dot(f)))
    if tgt == "all":
        return 0.0
    return gaze_yaw(k, tgt)


POSTURE_LEAN = {"table": 10.0, "sofa": -2.0, "stool": 4.0, "stand": 3.0, "walk": 3.0}


def build_gaze(g, segs, t_end=None):
    """Head yaw/pitch, torso twist and lean keys from the conversation and the
    action overrides, sampled at 0.1 s and keyed at changes. Neutral at 0 and
    from t_end (the loop seam, or the end of the dinner) on."""
    rng = random.Random(f"gaze{g.k}{LOOP}")
    t_end = LOOP if t_end is None else t_end
    n = int(LOOP * 10) + 1
    yaw = np.zeros(n)
    pitch = np.full(n, 4.0)
    lean = np.array([POSTURE_LEAN[g.posture(i / 10.0)] for i in range(n)])
    base_lean = lean.copy()
    prio = np.full(n, -1, int)

    def put(t0, t1, y, p, l, pr):
        i0, i1 = max(0, int(round(t0 * 10))), min(n, int(round(t1 * 10)))
        if i1 <= i0:
            return
        m = prio[i0:i1] <= pr
        if y is not None:
            yaw[i0:i1][m] = y
        pitch[i0:i1][m] = p
        lean[i0:i1][m] = l if l is not None else base_lean[i0:i1][m]
        prio[i0:i1][m] = pr
    for t0, t1, tgt, role in sorted(segs, key=lambda s: s[0]):
        y = target_yaw(g.k, tgt, g, t0)
        sit = g.posture(t0) in ("table", "sofa", "stool")
        if role == "talk":
            sub = t0
            while sub < t1:
                put(sub, min(t1, sub + 2.4), y + rng.uniform(-6, 6), rng.choice([0, 2, 4]), 12 if sit else 4, 0)
                sub += 2.4
        elif role == "listen":
            sub = t0
            nod = False
            while sub < t1:
                put(sub, min(t1, sub + 2.6), y, 9 if nod else 4, 10 if sit else 3, 0)
                nod = not nod
                sub += 2.6
        else:
            put(t0, t1, y * 0.7, -11, 6 if sit else 0, 0)
    for t0, t1, y, p, l, pr in g.over:
        put(t0, t1, y, p, l, pr + 1)
    for i0, i1 in ((0, 10), (int(t_end * 10) - 12, n)):   # neutral at the seams
        yaw[i0:i1], pitch[i0:i1], lean[i0:i1] = 0.0, 4.0, base_lean[i0:i1]
    yaw = np.clip(yaw, -85, 85)
    twist = np.clip(yaw * 0.35, -28, 28)
    head = yaw - twist
    vals = np.stack([head, pitch, twist, lean], 1)
    f = g.f
    chans = (f.yaw, f.pitch, f.twist, f.lean)
    prev = vals[0]
    for c, v in zip(chans, prev):
        c.add(0.0, float(v))
    last = -1.0
    for i in range(1, n):
        v = vals[i]
        if np.max(np.abs(v - prev)) < 0.6:
            continue
        t = i / 10.0
        if t < last + 0.45:
            continue
        for c, a, b in zip(chans, prev, v):
            c.add(t, float(a)).add(t + 0.4, float(b))
        prev = v.copy()
        last = t
    for c, v in zip(chans, vals[-1]):
        c.add(LOOP, float(v))


def gestures(g, segs, rng):
    for t0, t1, _tgt, role in segs:
        if role != "talk" or t1 - t0 < 3.2 or rng.random() > 0.35:
            continue
        if not g.free("L", t0, t0 + 3.1):
            continue
        pz = g.posture(t0)
        if pz != g.posture(t0 + 3.1) or pz == "walk":
            continue
        G, rest = {"table": (GESTURE, REST_G["L"]), "sofa": (GESTURE, LAP["L"]), "stool": (GESTURE, LAP["L"]),
                   "stand": (STAND_GESTURE, STAND_REST["L"])}[pz]
        k = g.hk("L")
        k.hold(t0 + 0.1).add(t0 + 0.8, G[0].copy()).add(t0 + 1.5, G[1].copy()) \
            .add(t0 + 2.2, G[0].copy()).add(t0 + 3.0, rest.copy())
        g.mark("L", t0, t0 + 3.1)


# --- The waiters' and chef's work ---------------------------------------------
class Crew:
    """Shared state for one authoring pass."""

    def __init__(self, delays):
        self.delays = delays
        self.P = PropSet()
        self.rng = random.Random("dinner")
        self.guests = {k: Guest(k, random.Random(f"guest{k}")) for k in GUESTS}
        self.W = {w: Staff(WAITER_TAG[w], WAITER_LOOK[w], STANDBY[w]) for w in ("W1", "W2")}
        self.chef = Staff(CHEF_TAG, CHEF_LOOK, CHEF_START, speed=1.15)
        self.n_task = {"W1": 0, "W2": 0, "chef": 0, **{f"G{k}": 0 for k in GUESTS}}
        self.glass_on = {k: [] for k in range(1, 9)}        # (t0, t1, wine) glass on the table
        self.rovers_from = 1e9                               # set once the linger window is known
        CF.add_actors(self, CF.DINNER_DUE)

    def delay(self, who):
        i = self.n_task[who]
        self.n_task[who] += 1
        return self.delays.get((who, i), 0.0), i

    # waiter helpers ---------------------------------------------------------
    def goto(self, w, t, dest, face=None):
        s = self.W[w]
        pts = route(w, (s.x, s.y), dest[:2])
        t = s.walk(t, pts)
        if face is not None:
            t = s.turn(t, face)
        elif len(dest) > 2:
            t = s.turn(t, dest[2])
        return t

    def gap_stance(self, k):
        side = SIDE_OF[k]
        return (GAP_X[side], GAPS[SERVE_GAP[k]])

    def into_gap(self, w, t, k):
        s = self.W[w]
        st = self.gap_stance(k)
        t = self.goto(w, t, st)
        t = s.face(t, PLACES[k]["plate"])
        return t

    def out_of_gap(self, w, t):
        s = self.W[w]
        return s.walk(t, [(s.x, s.y), (AISLE_X[w], s.y)])

    def mark_place(self, k, t0, t1):
        if k in self.guests:
            self.guests[k].waiter_at.append((t0, t1))

    # tasks ------------------------------------------------------------------
    def serve_trip(self, w, t_avail, ready, ks, c):
        s = self.W[w]
        d, i = self.delay(w)
        pts = route(w, (s.x, s.y), W_PASS[w])
        t0 = max(t_avail, ready + 2.6 - walk_time(pts, s.speed)) + d
        s.stay(t0)
        t = s.walk(t0, pts)
        t = s.turn(t, 0.0)
        a, b = PASS[w]
        pa, pb = self.P.plates[(c, ks[0])], self.P.plates[(c, ks[1])]
        t = s.take(max(t, ready + 2.6), "L", pa, a, "plate") + 0.1
        t = s.back(t, "L", 0.4)
        t = s.take(t, "R", pb, b, "plate") + 0.1
        t = s.back(t, "R", 0.4)
        t_pick = t
        for side, k, p in (("L", ks[0], pa), ("R", ks[1], pb)):
            t = self.into_gap(w, t, k)
            tc = s.put_down(t, side, p, PLACES[k]["plate"], PLACES[k]["yaw"], lean=22, bow=34, dur=0.9)
            self.mark_place(k, tc - 1.2, tc + 0.6)
            self.served[(c, k)] = tc
            t = s.back(tc + 0.1, side)
            t = self.out_of_gap(w, t)
        s.tasks.append((t0, t, f"serve{c}"))
        s.t = t
        return t_pick, t

    def clear_trip(self, w, t_avail, ks, c, dirty_free=0.0):
        s = self.W[w]
        d, i = self.delay(w)
        t0 = t_avail + d
        s.stay(t0)
        t = t0
        plates = []
        for side, k in zip(("L", "R"), ks):
            t = self.into_gap(w, t, k)
            p = self.P.plates[(c, k)]
            tc = s.take(t, side, p, PLACES[k]["plate"], "plate", lean=22, bow=34, dur=0.9)
            self.mark_place(k, tc - 1.2, tc + 0.6)
            t = s.back(tc + 0.1, side)
            t = self.out_of_gap(w, t)
            plates.append((side, p))
        sp = SPINES[w]
        lane = sp.project(W_DIRTY[w])[1]
        t = self.goto(w, t, (lane.x, lane.y))
        s.stay(max(t, dirty_free))                   # the chef has the last pair off the island
        t = self.goto(w, max(t, dirty_free), W_DIRTY[w], 0.0)
        for (side, p), spot in zip(plates, DIRTY[w]):
            tc = s.put_down(t, side, p, spot, 0.0)
            t = s.back(tc + 0.1, side, 0.4)
        s.tasks.append((t0, t, f"clear{c}"))
        s.t = t
        return t

    def pub_go(self, w, t, dest, face=None):
        """Walk about the snug, round the other waiter's post."""
        s = self.W[w]
        o = PUB_POST["W2" if w == "W1" else "W1"]
        t = s.walk(t, snug_path((s.x, s.y), dest[:2], [(o[0], o[1], 0.46)]))
        return s.turn(t, face) if face is not None else t

    def pub_serve(self, w, t_avail, there):
        """Take the tray of after-dinner drinks off the sideboard, carry it over to
        the Rovers, hand each of this side's guests their drink in the snug
        (tray lowered to them), set the tray down at the end of the bar."""
        s = self.W[w]
        d, i = self.delay(w)
        t0 = t_avail + d
        s.stay(t0)
        P = self.P
        tray = P.trays[w]
        t = self.sideboard(w, t0, TRAY_Y)
        tc = s.take(t, "L", tray, self.sb_spot(w, TRAY_Y), "tray", lift=0.04, reach=0.105)
        t = s.back(tc + 0.1, "L", 0.5)
        t = s.walk(t, house_way((s.x, s.y)))
        for j, k in enumerate(SERVES[w]):
            g = self.guests[k]
            st = SERVE_AT[k]
            t = self.pub_go(w, t, st)
            t = max(t, there[k] + 0.5)
            s.stay(t)
            t = s.face(t, PUB[k]["root"])
            s.f.L.hold(t).add(t + 0.6, TRAY_LOW.copy())
            s.f.lean.hold(t).add(t + 0.6, 12)
            tc = g.take_from_tray(t + 0.7, P.lounge[k], s, j, drop=TRAY_DROP)
            g.drink = True
            t = tc + 1.3
            s.f.L.add(t + 0.5, HAND_CARRY["tray"]["L"].copy())
            s.f.lean.add(t + 0.5, 3)
            t += 0.5
        t = self.pub_go(w, t, PUB_STN[w], 180.0)
        tc = s.put_down(t, "L", tray, PUB_TRAY[w], 180.0, lift=0.04, reach=0.105, how="tray")
        t = s.back(tc + 0.1, "L", 0.5)
        t = s.turn(t + 0.2, PUB_POST[w][2])
        s.tasks.append((t0, t, "pub serve"))
        s.t = t
        return t

    def pub_pour(self, w, t_avail, wine, ks):
        """The bottle off the bar; each guest holds their glass out from their
        seat and is topped up; the bottle back on the bar."""
        s = self.W[w]
        d, i = self.delay(w)
        t0 = t_avail + d
        P = self.P
        for k in ks:                                  # nobody served while they're up
            for a, b in self.guests[k].walks:
                if a - 25.0 < t0 < b + 2.0:
                    t0 = b + 2.0
        s.stay(t0)
        b = P.bottles[(wine, "Pub")]
        spot = PUB_BOTTLE[wine]
        t = self.pub_go(w, t0, PUB_STN[w], 180.0)
        tc = s.take(t, "R", b, spot, "bottle", lift=b.grip, reach=0.05)
        s.hold["R"] = "bottle"
        t = s.back(tc + 0.1, "R", 0.5)
        top_h = GLASS_SHAPE[wine][2][2]
        for k in ks:
            st = SERVE_AT[k]
            t = self.pub_go(w, t, st, heading(st, PUB[k]["root"]))
            g = self.guests[k]
            glass = P.lounge[k]
            w_pt = g.offer(t, st, 4.4)
            tr = t + 0.9
            fwd = _fwd(s.yaw)
            est = w_pt + Vector((0, 0, top_h - glass.grip + 0.093)) - fwd * 0.187 - fwd * 0.045
            gtag = g.f.tag

            def want(R, fi, gtag=gtag, top_h=top_h, grip=glass.grip):
                G = REC_NOW[gtag]
                top = Vector(G["palm"]["R"][fi]) + Vector((0, 0, top_h - grip))
                return top + Vector((0, 0, 0.093)) - _fwd(R["yaw"][fi]) * 0.187
            ct = s.contact(tr + 0.8, "R", s.f.at_world(est), want)
            t = s.reach(tr, "R", ct, 0.8, 16, 24, bow=10)
            b.tilt.add(t - 0.1, 0).add(t + 0.5, -100).add(t + 1.7, -100).add(t + 2.2, 0)
            glass.ramp(t + 0.5, t + 1.7, LOUNGE_POUR[wine])
            self.last_pour[k] = t + 1.7
            t = s.back(t + 2.3, "R", 0.6)
        t = self.pub_go(w, t, PUB_STN[w], 180.0)
        tc = s.put_down(t, "R", b, spot, 180.0, lift=b.grip, reach=0.05, how="bottle")
        t = s.back(tc + 0.1, "R", 0.5)
        t = s.turn(t + 0.2, PUB_POST[w][2])
        s.tasks.append((t0, t, f"pub {wine}"))
        s.t = t
        return t

    def post_idle(self, w, t0, t1):
        """At the end of the bar between jobs: looks round the room."""
        s = self.W[w]
        rng = random.Random(f"post{w}{int(t0)}")
        t = t0 + rng.uniform(2.0, 5.0)
        while t < t1 - 6.0:
            dur = rng.uniform(2.5, 5.0)
            s.head(t, yaw=rng.uniform(-45, 45), pitch=rng.choice([0, 3, 6]))
            s.head(t + dur, yaw=0)
            t += dur + rng.uniform(3.0, 9.0)

    def standby(self, w, t):
        s = self.W[w]
        t = self.goto(w, t, STANDBY[w])
        s.t = t
        return t

    def sideboard(self, w, t, y):
        return self.goto(w, t, (SB_STANCE_X[w], y), SB_FACE[w])

    def sb_spot(self, w, y, z=SB_TOP):
        return Vector((SB_X[w], y, z))

    def cupboard(self, w):
        s = self.W[w]
        return Vector((0.12, 0.30, 0.50))

    def glass_change(self, w, t_avail, old, new, restock):
        """Tray from the sideboard (new glasses on it); at each of this side's
        places take the old glass (if any) and set the new one (if any); back to
        the sideboard, used glasses away, the next wine's glasses on the tray."""
        s = self.W[w]
        d, i = self.delay(w)
        t0 = t_avail + d
        s.stay(t0)
        P = self.P
        tray = P.trays[w]
        t = self.sideboard(w, t0, TRAY_Y)
        tc = s.take(t, "L", tray, self.sb_spot(w, TRAY_Y), "tray", lift=0.04, reach=0.105)
        t = s.back(tc + 0.1, "L", 0.5)
        for j, k in enumerate(SIDE_PLACES[w]):
            t = self.into_gap(w, t, k)
            tm0 = t
            if old:
                gold = P.glasses[(old, k)]
                gp = PLACES[k][GLASS_SPOT[old]]
                tc = s.take(t, "R", gold, gp, "glass", lift=gold.grip, reach=0.05, lean=22, dur=0.9, bow=34)
                slot_old = TRAY_SLOTS[4 + j]
                t = s.reach(tc + 0.1, "R", s.contact(tc + 0.7, "R",
                                                     TRAY_CENTRE + slot_old + Vector((0, -0.05, gold.grip)),
                                                     palm_on_tray(4 + j, gold.grip)), 0.6, 18)
                gold.at(t, ("on", tray, 4 + j))
                s.hold["R"] = None
                for q, rec in enumerate(self.glass_on[k]):
                    if rec[2] == old and rec[1] is None:
                        self.glass_on[k][q] = (rec[0], t, old)
                tc = t
            if new:
                gnew = P.glasses[(new, k)]
                gp = PLACES[k][GLASS_SPOT[new]]
                slot_new = TRAY_SLOTS[j]
                t = s.reach(t + 0.1, "R", s.contact(t + 0.6, "R", TRAY_CENTRE + slot_new + Vector((0, -0.05, gnew.grip)),
                                                    palm_on_tray(j, gnew.grip)), 0.5, 18)
                gnew.at(t, ("hand", s.f.tag, "R", "glass"))
                s.hold["R"] = "glass"
                tc = s.put_down(t + 0.1, "R", gnew, gp, PLACES[k]["yaw"], lift=gnew.grip, reach=0.05, lean=22,
                                dur=0.9, bow=34, how="glass")
                self.glass_on[k].append((tc, None, new))
            self.mark_place(k, tm0, tc + 0.5)
            t = s.back(tc + 0.1, "R", 0.9)              # from the far glass spot: not a snatch
            t = self.out_of_gap(w, t)
        t = self.sideboard(w, t, TRAY_Y)
        tc = s.put_down(t, "L", tray, self.sb_spot(w, TRAY_Y), SB_FACE[w], lift=0.04, reach=0.105, how="tray")
        t = s.back(tc + 0.1, "L", 0.5)
        low = self.cupboard(w)
        for j, k in enumerate(SIDE_PLACES[w] if old else ()):   # used glasses into the cupboard
            g = P.glasses[(old, k)]
            t = s.reach(t, "R", s.contact(t + 0.85, "R", self._tray_slot_local(w, 4 + j, g),
                                          palm_for("glass", self._tray_slot_world(w, 4 + j), g.grip)), 0.85, 20)
            g.at(t, ("hand", s.f.tag, "R", "glass"))
            t = s.reach(t + 0.05, "R", low, 0.85, 30, 30)
            g.at(t, ("hidden",))
            g.ramp(t, t + EPS, 0.0)
        if isinstance(restock, list):
            rprops = restock
        else:
            rprops = [P.glasses[(restock, k)] for k in SIDE_PLACES[w]] if restock else []
        for j, g in enumerate(rprops):                   # next glasses onto the tray
            g.at(t, ("hidden",))
            g.at(t + 0.02, ("hand", s.f.tag, "R", "glass"))
            if g.name.startswith("L"):                   # after-dinner drinks come out poured
                g.ramp(t, t + EPS, LOUNGE_POUR[g.sub[1]])
            t = s.reach(t + 0.05, "R", s.contact(t + 0.9, "R", self._tray_slot_local(w, j, g),
                                                 palm_for("glass", self._tray_slot_world(w, j), g.grip)), 0.85, 20)
            g.at(t, ("on", tray, j))
            t = s.reach(t + 0.05, "R", low, 0.85, 30, 30) if j < len(rprops) - 1 else t
        t = s.back(t + 0.1, "R")
        s.hold["R"] = None
        s.tasks.append((t0, t, f"glasses{old}>{new}"))
        s.t = t
        return t

    def _tray_slot_world(self, w, slot):
        return self.sb_spot(w, TRAY_Y) + Matrix.Rotation(math.radians(SB_FACE[w]), 3, 'Z') @ TRAY_SLOTS[slot]

    def _tray_slot_local(self, w, slot, g):
        """Wrist target (waiter-local) for a glass standing on the tray where it
        rests on the sideboard (waiter at the tray stance)."""
        s = self.W[w]
        tray = self.sb_spot(w, TRAY_Y)
        a = math.radians(SB_FACE[w])
        rot = Matrix.Rotation(a, 3, 'Z')
        wpos = tray + rot @ TRAY_SLOTS[slot]
        d = Vector((wpos.x - s.x, wpos.y - s.y, 0))
        loc = Matrix.Rotation(-math.radians(s.yaw), 3, 'Z') @ Vector((wpos.x - s.x, wpos.y - s.y, wpos.z - FLOOR))
        return loc + Vector((0, -0.05, g.grip))

    def pour(self, w, t_avail, wine, level, places=None):
        s = self.W[w]
        d, i = self.delay(w)
        t0 = t_avail + d
        s.stay(t0)
        P = self.P
        b = P.bottles[(wine, w)]
        by = BOTTLE_Y[wine]
        t = self.sideboard(w, t0, by)
        tc = s.take(t, "R", b, self.sb_spot(w, by), "bottle", lift=b.grip, reach=0.05)
        s.hold["R"] = "bottle"
        t = s.back(tc + 0.1, "R", 0.5)
        for k in (places or SIDE_PLACES[w]):
            g = P.glasses[(wine, k)]
            gp = PLACES[k][GLASS_SPOT[wine]]
            t = self.into_gap(w, t, k)
            tm0 = t
            d2 = Vector((gp.x - s.x, gp.y - s.y, 0)).normalized()
            palm = gp + Vector((0, 0, 0.25)) - d2 * 0.19
            wrist = palm - d2 * 0.045
            t = s.reach(t, "R", s.f.at_world(wrist), 0.8, 20, 28, bow=22)
            b.tilt.add(t - 0.1, 0).add(t + 0.5, -100).add(t + 2.1, -100).add(t + 2.6, 0)
            g.ramp(t + 0.5, t + 2.1, level)
            self.mark_place(k, tm0, t + 2.8)
            t = s.back(t + 2.7, "R", 0.5)
            t = self.out_of_gap(w, t)
        t = self.sideboard(w, t, by)
        tc = s.put_down(t, "R", b, self.sb_spot(w, by), SB_FACE[w], lift=b.grip, reach=0.05, how="bottle")
        t = s.back(tc + 0.1, "R", 0.5)
        s.tasks.append((t0, t, f"pour{wine}"))
        s.t = t
        return t

    # chef -------------------------------------------------------------------
    def chef_go(self, t, dest, face):
        c = self.chef
        pts = [(c.x, c.y)]
        if abs(c.y - dest[1]) > 0.05:                 # square across the lane, along the back
            pts += [(c.x, BACK_LINE), (dest[0], BACK_LINE)]
        pts.append(dest)
        t = c.walk(t, pts)
        return c.turn(t, face)

    def plate_pair(self, t_avail, w, c, ks):
        ch = self.chef
        d, i = self.delay("chef")
        t0 = t_avail + d
        ch.stay(t0)
        P = self.P
        t = self.chef_go(t0, C_STACK, 180.0)
        plates = [P.plates[(c, k)] for k in ks]
        for side, p in zip(("L", "R"), plates):
            p.at(t + 0.75 - 2 * EPS, ("spot", STACK.copy(), 180.0))
            tc = ch.take(t, side, p, STACK, "plate", lean=22)
            t = ch.back(tc + 0.1, side, 0.4)
        t = self.chef_go(t, C_PASS[w], 0.0)
        for side, p, spot in zip(("L", "R"), plates, PASS[w]):
            tc = ch.put_down(t, side, p, spot, 0.0, lean=24)
            t = ch.back(tc + 0.1, side, 0.4)
        for p, spot in zip(plates, PASS[w]):             # plate the food: a spoon circling over it
            t1 = t + 2.6
            cx, cy = spot.x, spot.y

            def stir(tt, cx=cx, cy=cy, t=t):
                q = (tt - t) * 2 * math.pi / 1.3
                return ch.f.to_local(tt, Vector((cx + 0.05 * math.cos(q) - 0.05, cy - 0.10 + 0.04 * math.sin(q),
                                                 ISLAND_Z + 0.16)))
            ch.f.R.hold(t).add(t + 0.6, stir).add(t1 - 0.7, stir).add(t1, HAND_REST["R"].copy())
            ch.f.lean.hold(t).add(t + 0.5, 22).add(t1, 6)
            ch.f.pitch.hold(t).add(t + 0.5, 30).add(t1, 10)
            p.ramp(t + 0.5, t1 - 0.3, 1.0)
            t = t1
        ready = t
        t = self.chef_go(t + 0.2, C_STOVE, 180.0)
        ch.tasks.append((t0, t, f"plate{c}{w}"))
        ch.t = t
        return ready

    def dispose(self, t_avail, w):
        ch = self.chef
        d, i = self.delay("chef")
        t0 = t_avail + d
        ch.stay(t0)
        t = self.chef_go(t0, C_DIRTY[w], 0.0)
        plates = []
        for side, spot in zip(("L", "R"), DIRTY[w]):
            p = self.P_dirty[w].pop(0)
            tc = ch.take(t, side, p, spot, "plate", lean=24)
            t = ch.back(tc + 0.1, side, 0.4)
            plates.append((side, p))
        self.dirty_free[w] = t + 1.2
        t = self.chef_go(t, C_SINK, 180.0)
        for side, p in plates:
            tc = ch.put_down(t, side, p, SINK, 180.0, lean=22)
            p.at(tc + 0.5, ("hidden",))
            p.ramp(tc + 0.5, tc + 0.5 + EPS, 0.0)
            t = ch.back(tc + 0.1, side, 0.4)
        t = self.chef_go(t, C_STOVE, 180.0)
        ch.tasks.append((t0, t, f"dispose{w}"))
        ch.t = t
        return t

    def chef_idle(self, t0, t1, static=False):
        """Stir the pans, chop, glance at the pass, between jobs (static: only
        at the stove, never walking)."""
        ch = self.chef
        rng = random.Random(f"chefidle{int(t0 * 10)}")
        t = t0
        while t1 - t > 6.0:
            if not static:                           # an espresso round for the café, when one is due
                t2 = CF.maybe_coffee(self, t, t1)
                if t2 != t:
                    t = t2
                    continue
            kind = rng.choice(["stir", "look"] if static else ["stir", "chop", "look", "look"])
            dur = min(t1 - t - 0.5, rng.uniform(5, 12))
            if kind == "chop":
                t = self.chef_go(t, C_CHOP, 180.0)
                a = t + 0.6
                ch.f.L.hold(t).add(a, ch.f.at_world(CHOP + Vector((-0.08, 0.10, 0.06))))
                ch.f.R.hold(t)
                q = a
                while q < t + dur - 1.0:
                    ch.f.R.add(q, ch.f.at_world(CHOP + Vector((0.06, 0.12, 0.12)))) \
                        .add(q + 0.3, ch.f.at_world(CHOP + Vector((0.06, 0.12, 0.05))))
                    q += 0.6
                ch.f.lean.hold(t).add(a, 20).add(t + dur - 0.6, 20)
                ch.f.pitch.hold(t).add(a, 32).add(t + dur - 0.6, 32)
                t += dur
                ch.f.L.add(t, HAND_REST["L"].copy())
                ch.f.R.add(t, HAND_REST["R"].copy())
                ch.f.lean.add(t, 3)
                ch.f.pitch.add(t, 3)
            elif kind == "stir":
                t = self.chef_go(t, C_STOVE, 180.0)
                pan = PANS[rng.randrange(2)]
                ch.f.L.hold(t).add(t + 0.6, ch.f.at_world(pan + Vector((0.0, 0.17, 0.08))))

                def stir(tt, pan=pan, s0=t):
                    q = (tt - s0) * 2 * math.pi / 3.2
                    return ch.f.to_local(tt, pan + Vector((0.05 * math.cos(q), 0.10 + 0.05 * math.sin(q), 0.16)))
                ch.f.R.hold(t).add(t + 0.6, stir).add(t + dur - 0.6, stir)
                ch.f.lean.hold(t).add(t + 0.6, 16).add(t + dur - 0.6, 16)
                ch.f.pitch.hold(t).add(t + 0.6, 30).add(t + dur - 0.6, 30)
                t += dur
                ch.f.L.add(t, HAND_REST["L"].copy())
                ch.f.R.add(t, HAND_REST["R"].copy())
                ch.f.lean.add(t, 3)
                ch.f.pitch.add(t, 3)
            else:
                t = self.chef_go(t, C_STOVE, 180.0)
                tt = self.chef.turn(t, 20.0, 0.6)
                ch.f.yaw.add(tt, 15).add(tt + dur - 1.5, -10)
                ch.f.pitch.add(tt, 5).add(tt + dur - 1.5, 5)
                t = self.chef.turn(tt + dur - 1.2, 180.0, 0.6)
                ch.f.yaw.add(t, 0)
                ch.f.pitch.add(t, 3)
        if (ch.x, ch.y) != C_STOVE[:2]:
            t = self.chef_go(t, C_STOVE, 180.0)
        ch.t = max(t, ch.t)
        return ch.t


def author(delays, eat_scale):
    """One full authoring pass. Returns the crew and the time service ends."""
    CONTACTS.clear()
    cr = Crew(delays)
    P = cr.P
    cr.served = {}
    cr.P_dirty = {"W1": [], "W2": []}
    cr.dirty_free = {"W1": 0.0, "W2": 0.0}
    # Opening state: the guests on the patio with their flutes, flutes poured
    # at the two free places, chairs in, white glasses on the trays.
    for k in range(1, 9):
        pl = PLACES[k]
        for wn in WINES:
            g = P.glasses[(wn, k)]
            if wn == "champ" and k in GUESTS:
                g.at(0.0, ("hand", TAGS[k], "R", "glass"))
                g.fill0 = POUR["champ"]
            elif wn == "champ":
                g.at(0.0, ("spot", pl["glass"].copy(), pl["yaw"]))
                g.fill0 = POUR["champ"]
            else:
                g.at(0.0, ("hidden",))
        for c in range(len(COURSES)):
            P.plates[(c, k)].at(0.0, ("hidden",))
        P.chairs[k].at(0.0, ("spot", Vector((CHAIR_X[pl["side"]], pl["y"], 0.0)), pl["yaw"]))
    for w in ("W1", "W2"):
        P.trays[w].at(0.0, ("spot", cr.sb_spot(w, TRAY_Y), SB_FACE[w]))
        for j, k in enumerate(SIDE_PLACES[w]):
            P.glasses[("white", k)].at(0.0, ("on", P.trays[w], j))
        for wn in WINES + ("cognac", "whisky"):
            P.bottles[(wn, w)].at(0.0, ("spot", cr.sb_spot(w, BOTTLE_Y[wn]), SB_FACE[w]))
    for k in GUESTS:
        P.lounge[k].at(0.0, ("hidden",))
    for wn, spot in PUB_BOTTLE.items():
        P.bottles[(wn, "Pub")].at(0.0, ("spot", spot.copy(), 180.0))
    CF.initial_props(P)
    for k in GUESTS:
        pl = PLACES[k]
        for kind in ("fork", "knife", "spoon"):
            P.cutlery[(kind, k)].at(0.0, ("spot", pl[kind].copy(), pl["yaw"]))
    # In from the patio, then the toast.
    seated = {}
    for i, k in enumerate(ARRIVE_ORDER):
        d, _ = cr.delay(f"G{k}")
        seated[k] = cr.guests[k].arrive(ARRIVE_T0 + i * ARRIVE_GAP + d, P)
        cr.glass_on[k].append((seated[k] - 0.8, None, "champ"))
    t_toast = max(seated.values()) + 3.0
    cr.t_seated = t_toast
    for k in GUESTS:
        g = cr.guests[k]
        g.over.append((t_toast - 2.0, t_toast, gaze_yaw(k, 1) if k != 1 else 0.0, 4, 10, 1))
        g.sip(t_toast + 0.15 * GUESTS.index(k), P.glasses[("champ", k)], 0.10, toast=True)
    t_course = t_toast + 14.0
    eat_end = {}
    for c in range(len(COURSES)):
        chef_t = max(cr.chef.t, t_course - 34.0)
        cr.chef_idle(cr.chef.t, chef_t)
        # The chef plates both waiters' pairs, then they go out together.
        ra = max(cr.plate_pair(cr.chef.t, "W1", c, (1, 2)), cr.plate_pair(cr.chef.t, "W2", c, (5, 6)))
        p1a, _ = cr.serve_trip("W1", max(cr.W["W1"].t, t_course - 12.0), ra, (1, 2), c)
        p2a, _ = cr.serve_trip("W2", max(cr.W["W2"].t, t_course - 12.0), ra, (5, 6), c)
        rb = max(cr.plate_pair(max(cr.chef.t, p1a + 0.8), "W1", c, (3, 4)),
                 cr.plate_pair(max(cr.chef.t, p2a + 0.8), "W2", c, (7, 8)))
        cr.serve_trip("W1", cr.W["W1"].t, rb, (3, 4), c)
        cr.serve_trip("W2", cr.W["W2"].t, rb, (7, 8), c)
        all_served = max(cr.served[(c, k)] for k in range(1, 9))
        e0 = all_served + 2.0
        dur = 60.0 * COURSES[c]["eat"] * eat_scale
        finish = {}
        for k in GUESTS:
            g = cr.guests[k]
            u = g.rng.uniform(0.86, 1.0)
            finish[k] = e0 + dur * u
            g.eat(P, c, e0 + g.rng.uniform(0.0, 1.5), finish[k])
        # Wine work during the course.
        for w in ("W1", "W2"):
            t = cr.standby(w, cr.W[w].t)
            reds = [k for k in SIDE_PLACES[w] if k not in WHITE_DRINKERS]
            whites = [k for k in SIDE_PLACES[w] if k in WHITE_DRINKERS]
            if c == 2:
                t = cr.pour(w, t + 1.0, "white", POUR["white"])
            if c in (4, 5):                          # red, or white for those who prefer it
                t = cr.pour(w, t + 1.0, "red", POUR["red"], reds)
                if whites:
                    t = cr.pour(w, t + 1.0, "white", POUR["white"], whites)
            if c == 6:
                t = cr.pour(w, t + 1.0, "sweet", POUR["sweet"])
                t = cr.glass_change(w, t + 1.0, "white", None,                # the white glasses go;
                                    [P.lounge[k] for k in SERVES[w]])           # the drinks for the pub
            if c == 1:
                t = cr.glass_change(w, max(t, e0 + 4.0), "champ", "white", "red")
            if c == 3:
                t = cr.glass_change(w, max(t, e0 + 2.0), None, "red", "sweet")
            cr.standby(w, t)
        last = max(finish.values())
        eat_end[c] = last
        # Clear.
        tc = last + 5.0
        for w, off in (("W1", 0.0), ("W2", 0.0)):
            ks = SIDE_PLACES[w]
            t = cr.clear_trip(w, max(cr.W[w].t, tc + off), ks[:2], c, cr.dirty_free[w])
            cr.P_dirty[w] += [cr.P.plates[(c, k)] for k in ks[:2]]
            cr.chef_idle(cr.chef.t, max(cr.chef.t, t + 0.5))
            cr.dispose(max(cr.chef.t, t + 1.5), w)
            t = cr.clear_trip(w, cr.W[w].t, ks[2:], c, cr.dirty_free[w])
            cr.P_dirty[w] += [cr.P.plates[(c, k)] for k in ks[2:]]
            cr.standby(w, t)                         # never wait about in the kitchen
        for w in ("W1", "W2"):
            cr.chef_idle(cr.chef.t, max(cr.chef.t, cr.W[w].tasks[-1][1] + 1.5))
            cr.dispose(cr.chef.t, w)
        for w in ("W1", "W2"):
            t = cr.W[w].t
            if c == 5:
                t = cr.glass_change(w, t, "red", "sweet", None)
            cr.standby(w, t)
        t_course = max(cr.W["W1"].t, cr.W["W2"].t) + 4.0
    # They linger over the sweet wine (LINGER: the window the client cuts short
    # to land the evening on the pub's phase; nobody walks in it), then get up
    # and go over to the Rovers, the far seats of the snug first. Each waiter
    # follows with their side's drinks on the tray (loaded at the pudding).
    La = max(cr.W["W1"].t, cr.W["W2"].t) + 6.0
    cr.chef_idle(cr.chef.t, La)
    La = max(La, cr.chef.t + 1.0)
    cr.La = La
    cr.rovers_from = La + LINGER
    cr.chef_idle(La, La + LINGER, static=True)
    t_up = La + LINGER + 3.0
    cr.t_first_up = t_up
    there = {}
    for i, k in enumerate(PUB_ORDER):
        d, _ = cr.delay(f"G{k}")
        t_k = t_up + i * ARRIVE_GAP + d
        for j, rec in enumerate(cr.glass_on[k]):
            if rec[1] is None:
                cr.glass_on[k][j] = (rec[0], t_k, rec[2])
        there[k] = cr.guests[k].to_pub(t_k, P)
    for w, lag in (("W1", 8.0), ("W2", 4.0)):
        cr.pub_serve(w, t_up + lag, there)
    end = max(list(there.values()) + [cr.W["W1"].t, cr.W["W2"].t]) + 20.0
    cr.D = math.ceil(end / PHASE) * PHASE
    for w in ("W1", "W2"):
        cr.post_idle(w, cr.W[w].t, cr.D)
    cr.chef_idle(cr.chef.t, cr.D - 3.0)
    if (cr.chef.x, cr.chef.y) != C_STOVE[:2] or cr.chef.t > cr.D - 0.5:
        raise RuntimeError("chef not back at the stove when the dinner ends")
    CF.author_dinner(cr, La, cr.D, random.Random("mime-dinner"))
    return cr, La


def hold_end(f):
    """Every channel keeps its last pose to the end of the timeline."""
    for k in (f.zk, f.fL, f.fR, f.L, f.R):
        k.hold(LOOP)


def finish(cr):
    """Close every track at the loop seam and write the guests' sips, gestures
    and gaze around what the crew did."""
    P = cr.P
    # Glass on the table per place over time (for sips).
    for k, g in cr.guests.items():
        rng = random.Random(f"sips{k}")
        spans = []
        for t0, t1, wn in cr.glass_on[k]:
            spans.append((t0, t1 if t1 is not None else LOOP, wn))
        t = g.seated[0] + 20.0
        while t < g.seated[1] - 12.0:
            t += rng.uniform(45, 95)
            cand = [s for s in spans if s[0] + 3.0 < t < s[1] - 8.0]
            if not cand or t > g.seated[1] - 8.0:
                continue
            whites = [s for s in cand if s[2] == "white"]
            wn = whites[0][2] if (k in WHITE_DRINKERS and whites) else max(cand, key=lambda s: s[0])[2]
            glass = P.glasses[(wn, k)]
            if any(a - 2.0 < t + 6.0 and t - 1.0 < b for a, b in g.waiter_at):
                continue
            if not g.free("R", t - 0.3, t + 5.0):
                continue
            if cr.La - 6.0 < t < cr.La + LINGER + 2.0:      # no glass in hand where the client cuts
                continue
            g.sip(t, glass, 0.08)
        flute = P.glasses[("champ", k)]
        for p0, p1 in g.patio:                       # champagne on the patio
            t = p0 + rng.uniform(4, 15)
            while t < p1 - 6.0:
                if g.free("R", t - 0.3, t + 3.4):
                    g.sip_held(t, flute, 0.06)
                t += rng.uniform(22, 40)
    segs = conversation(cr.rng, cr.t_seated + 12.0, cr.t_first_up)
    for k, g in cr.guests.items():
        segs[k] = [sg for sg in segs[k] if g.seated[0] + 1.0 < sg[0] and sg[1] < g.seated[1] - 0.5]
    pt = patio_talk(random.Random("patio"), 0.0, LOOP)
    pubt = pub_talk(random.Random("pubdinner"), min(g.pub[0][0] for g in cr.guests.values()), cr.D, cr.guests)
    for k, g in cr.guests.items():
        segs[k] += [sg for sg in pt[k] if any(p0 + 1.0 < sg[0] and sg[1] < p1 - 0.5 for p0, p1 in g.patio)]
        segs[k] += pubt[k]
        gestures(g, segs[k], g.rng)
        build_gaze(g, segs[k], cr.D)
        hold_end(g.f)
        g.f.put(LOOP, g.x, g.y, g.f._yaw)
    CF.author_couple(cr, cr.D, (cr.La - 6.0, cr.La + LINGER + 6.0))
    CF.close_mime(cr.mime, cr.D)
    for s in list(cr.W.values()) + [cr.chef]:
        f = s.f
        f.put(LOOP, s.x, s.y, s.yaw)            # where the dinner leaves them (the lounge starts there)
        s.hands(LOOP)
        f.lean.add(LOOP, f.lean[0][1])
        f.pitch.add(LOOP, f.pitch[0][1])
        f.yaw.add(LOOP, f.yaw[0][1])
        f.twist.add(LOOP, 0.0)


# --- The lounge loop (the Rovers snug) --------------------------------------------
class LCrew(Crew):
    """The after-dinner loop: everyone where the dinner left them."""

    def __init__(self, delays):
        self.delays = delays
        self.P = PropSet()
        self.rng = random.Random("lounge")
        self.guests = {k: Guest(k, random.Random(f"lounge{k}"), lounge=True) for k in GUESTS}
        self.W = {w: Staff(WAITER_TAG[w], WAITER_LOOK[w], PUB_POST[w], z=RV_FLOOR) for w in ("W1", "W2")}
        self.chef = Staff(CHEF_TAG, CHEF_LOOK, CHEF_START, speed=1.15)
        self.n_task = {"W1": 0, "W2": 0, "chef": 0, **{f"G{k}": 0 for k in GUESTS}}
        self.glass_on = {k: [] for k in range(1, 9)}
        self.last_pour = {}
        self.rovers_from = 0.0
        CF.add_actors(self, CF.LOUNGE_DUE)


def pub_talk(rng, t0, t1, guests):
    """Per guest in the snug: chat round their own table (north 1, 2, 4; south
    5, 6, 8), now and then across to the other one, and a laugh; nobody talks
    to someone who is up and about."""
    segs = {k: [] for k in GUESTS}
    tables = {"N": [k for k in GUESTS if PUB[k]["table"] == "N"], "S": [k for k in GUESTS if PUB[k]["table"] == "S"]}

    def seated(k, a, b):
        g = guests[k]
        return any(p0 + 0.5 <= a and b <= p1 - 0.5 for p0, p1 in g.pub)
    for tb, ms in tables.items():
        other = [k for k in GUESTS if k not in ms]
        t = t0
        while t < t1 - 1.0:
            dur = min(rng.uniform(3.0, 6.0), t1 - t)
            here = [k for k in ms if seated(k, t, t + dur)]
            if len(here) < 2 or rng.random() < 0.08:          # across to the other table
                there = [q for q in other if seated(q, t, t + dur)]
                for k in here:
                    if there:
                        segs[k].append((t, t + dur, ("pos", PUB[rng.choice(there)]["root"]), "listen"))
                t += dur
                continue
            spk = rng.choice(here)
            for k in here:
                if k == spk:
                    tgt = rng.choice([q for q in here if q != k])
                    segs[k].append((t, t + dur, ("pos", PUB[tgt]["root"]), "talk"))
                else:
                    segs[k].append((t, t + dur, ("pos", PUB[spk]["root"]), "listen"))
            if rng.random() < 0.15 and t + dur + 2.0 < t1 and all(seated(k, t, t + dur + 2.0) for k in here):
                for k in here:
                    segs[k].append((t + dur, t + dur + 2.0, ("pos", PUB[spk if k != spk else here[0]]["root"]),
                                    "laugh"))
                dur += 2.0
            t += dur
    return segs


def author_lounge(delays, crd):
    """The snug loop, starting from where the dinner ends."""
    CONTACTS.clear()
    cr = LCrew(delays)
    P = cr.P
    by_name = {pr.name: pr for pr in crd.P.all}
    for pr in P.all:                         # every prop as the dinner leaves it
        pd = by_name[pr.name]
        h = pd.holder_at(crd.D)
        if h[0] == "on":
            h = ("on", P.trays[h[1].name[4:]], h[2])
        pr.at(0.0, h)
        fk, _ = pd.fill_keys()
        pr.fill0 = float(sample(fk, 1, crd.D)[1]) if pr.kind in ("plate", "glass") else pr.fill0
        pr.grip = pd.grip
    # Each guest off to the loo once a loop.
    for k, t_w in WC_PLAN:
        d, _ = cr.delay(f"G{k}")
        g = cr.guests[k]
        cr.guests[k].wc_trip(t_w + d, P, g.rng.uniform(40.0, 55.0))
    # The waiters' rounds of top-ups (each waits for anyone who is up); W1
    # also pours the café mime his red when he comes over, and clears his
    # empty after.
    t_arr = CF.author_lounge_until_rovers(cr, random.Random("mime-lounge"))
    jobs = {w: sorted([(t_r, "round", (wine, ks)) for t_r, wine, ks in r], key=lambda j: j[0])
            for w, r in ROUNDS.items()}
    jobs["W1"].append((t_arr - 12.0, "mime", None))
    jobs["W1"].append((CF.WAITER_DUE, "coffee", None))          # a round of espressos for the café couple
    jobs["W1"].sort(key=lambda j: j[0])
    for w in ("W2", "W1"):
        q = list(jobs[w])
        while q:
            t_r, kind, arg = q.pop(0)
            if kind == "round":
                cr.pub_pour(w, max(cr.W[w].t, t_r), *arg)
            elif kind == "mime":
                t_pour = CF.waiter_pour_for_mime(cr, max(cr.W[w].t, t_r))
                t_glass = CF.author_lounge_from_rovers(cr, t_pour)
                q.append((t_glass + 12.0, "stash", None))
                q.sort(key=lambda j: j[0])
            elif kind == "coffee":                          # the second round: the chef's pair goes back
                CF.coffee_run(cr, max(cr.W[w].t, t_r), w, old=3 - cr.cafe_on)
            else:
                CF.waiter_stash_glass(cr, max(cr.W[w].t, t_r))
    end = max(s.t for s in cr.W.values())
    end = max([end] + [g.walks[-1][1] for g in cr.guests.values() if g.walks])
    for w in ("W1", "W2"):
        s = cr.W[w]
        gaps = sorted(s.tasks)
        t = 0.0
        for t0, t1, _l in gaps:
            cr.post_idle(w, t, t0)
            t = t1
        cr.post_idle(w, t, LOOP - 1.0)
    cr.chef_idle(0.0, LOOP - 1.0)
    return cr, end


def finish_lounge(cr, crd):
    P = cr.P
    for k, g in cr.guests.items():           # sips: never after a guest's last top-up, never while up
        rng = random.Random(f"lsips{k}")
        glass = P.lounge[k]
        t = rng.uniform(8, 20)
        while t < cr.last_pour[k] - 8.0:
            if g.free("R", t - 0.3, t + 3.4) and not any(a - 2.0 < t + 3.4 and t < b + 2.0 for a, b in g.walks):
                g.sip_held(t, glass, 0.05, LOUNGE_HOLD)
            t += rng.uniform(25, 45)
    segs = pub_talk(cr.rng, 2.0, LOOP, cr.guests)
    for k, g in cr.guests.items():
        segs[k] = [sg for sg in segs[k] if not any(w0 - 1.0 < sg[1] and sg[0] < w1 + 1.0 for w0, w1 in g.walks)]
        gestures(g, segs[k], g.rng)
        build_gaze(g, segs[k])
        g.f.L.add(LOOP, g.f.L[0][1])
        g.f.R.add(LOOP, g.f.R[0][1])
        hold_end(g.f)
        g.f.put(LOOP, g.x, g.y, g.f._yaw)
    CF.author_couple(cr, LOOP)
    CF.close_mime(cr.mime)
    for s in list(cr.W.values()) + [cr.chef]:
        f = s.f
        f.put(LOOP, *f.root[0][1][:2], f.root[0][1][2])
        s.hands(LOOP)
        f.lean.add(LOOP, f.lean[0][1])
        f.pitch.add(LOOP, f.pitch[0][1])
        f.yaw.add(LOOP, f.yaw[0][1])
        f.twist.add(LOOP, 0.0)


def plan_lounge(report, crd):
    delays = {}
    for attempt in range(300):
        cr, end = author_lounge(delays, crd)
        if end > LOOP - 8.0:
            raise RuntimeError(f"lounge overruns the loop ({end:.1f}s)")
        cl = clashes(cr)
        if not cl:
            report(f"LOUNGE SCHEDULE: work ends {end:.1f}s, {len(delays)} delays after {attempt} passes")
            return cr
        t, a, b = cl[0]
        if "M" in (a, b) and (a.startswith("R:") or b.startswith("R:")):
            leg = CF.leg_at(cr.mime, t)               # the café mime in the regulars' way: he waits a bit
            if leg is None:
                raise RuntimeError(f"lounge: the mime and {a if b == 'M' else b} clash at {t:.1f}s off his Rovers legs")
            CF.LEG_WAIT[leg] += 2.0
            continue
        cand = [(task_at(cr, m, t), m) for m in (a, b) if not m.startswith("R:")]
        cand = [(i, m) for i, m in cand if i is not None]
        if not cand:
            raise RuntimeError(f"lounge: {a} and {b} clash at {t:.1f}s outside any task")
        i, m = max(cand, key=lambda im: actor(cr, im[1]).tasks[im[0]][0])
        delays[(m, i)] = delays.get((m, i), 0.0) + 2.0
    raise RuntimeError("lounge schedule did not settle")


# --- Scheduler ----------------------------------------------------------------
def _roots(fig, step=0.25):
    n = int(LOOP / step)
    fig.root.done()
    return [Vector((v.x, v.y)) for v in sample(fig.root, n, step)]


def _vis(fig, step=0.25):
    n = int(LOOP / step)
    if not fig.vis:
        return np.ones(n + 1, bool)
    fig.vis.done()
    return np.array(sample(fig.vis, n, step)) > 0.5


def actor(cr, who):
    if who == "chef":
        return cr.chef
    if who == "M":
        return cr.mime
    if who in ("CA", "CB"):
        return cr.couple[who[1]]
    if who.startswith("G"):
        return cr.guests[int(who[1:])]
    return cr.W[who]


ROVERS = {}


def rovers_tracks(step=0.25):
    """The Rovers regulars' roots on their own (PHASE) timeline: [(tag, xy, vis)]."""
    if step not in ROVERS:
        figs = getattr(RF, "PLANNED", None)
        if figs is None:
            cast, pours, _pat = RF._plan(RF.PATTERN, lambda *a: None)
            figs = [m.f for m in cast.values()] + [RF._barman(pours)]
        n = int(round(PHASE / step))
        out = []
        for f in figs:
            if f.tag.startswith("Bed") or abs(f.loop - PHASE) > 1e-6:
                continue
            f.root.done()
            r = sample(f.root, n - 1, step)
            if f.vis:
                f.vis.done()
                v = np.array(sample(f.vis, n - 1, step)) > 0.5
            else:
                v = np.ones(n, bool)
            out.append((f.tag, np.array([(q.x, q.y) for q in r]), v))
        ROVERS[step] = out
    return ROVERS[step]


def clashes(cr, step=0.25):
    """Glide-path clashes between anyone (roots only, while visible), and with
    the Rovers regulars from cr.rovers_from on (their time is ours modulo PHASE)."""
    who = ["W1", "W2", "chef"] + [f"G{k}" for k in GUESTS] + ["M", "CA", "CB"]
    tr = np.array([[(v.x, v.y) for v in _roots(actor(cr, w).f, step)] for w in who])   # (A, n, 2)
    vs = np.array([_vis(actor(cr, w).f, step) for w in who])
    out = []
    for a in range(len(who)):
        for b in range(a + 1, len(who)):
            if who[a] in ("CA", "CB") and who[b] in ("CA", "CB"):
                continue                                     # the café couple, side by side at their table
            ga, gb = who[a][0] in "GMC" and who[a] != "chef", who[b][0] in "GMC" and who[b] != "chef"
            thr = 0.40 if (ga and gb) else 0.36 if (ga or gb) else 0.46
            d = np.linalg.norm(tr[a] - tr[b], axis=1)
            for i in np.nonzero((d < thr) & vs[a] & vs[b])[0]:
                out.append((i * step, who[a], who[b]))
    rv = rovers_tracks(step)
    nt = tr.shape[1]
    times = np.arange(nt) * step
    idx = np.round((times % PHASE) / step).astype(int) % int(round(PHASE / step))
    live = times >= getattr(cr, "rovers_from", 0.0)
    for a in range(len(who)):
        for tag, xy, v in rv:
            d = np.linalg.norm(tr[a] - xy[idx], axis=1)
            for i in np.nonzero((d < 0.42) & vs[a] & v[idx] & live)[0]:
                out.append((i * step, who[a], "R:" + tag))
    out.sort(key=lambda c: c[0])
    return out


def task_at(cr, who, t):
    s = actor(cr, who)
    for i, (t0, t1, _l) in enumerate(s.tasks):
        if t0 - 0.5 <= t <= t1 + 0.5:
            return i
    return None


def plan(report, verbose=False):
    delays = {}
    scale = 1.0
    base = sum(c["eat"] for c in COURSES) * 60.0
    target = LA_TARGET                               # the pudding cleared (then the linger, the pub)
    for attempt in range(12):                        # fit the eating time
        cr, end = author(delays, scale)
        if abs(end - target) < 4.0:
            break
        scale = max(0.3, scale + (target - end) / base * 0.9)
    for attempt in range(800):
        cr, end = author(delays, scale)
        if verbose:
            report(f"  pass {attempt}: end {end:.1f} scale {scale:.3f}")
        if end > target + 60.0:
            scale -= (end - target) / base
            continue
        if cr.D > LOOP:
            raise RuntimeError(f"dinner runs past the authoring timeline ({cr.D:.0f}s > {LOOP:.0f}s)")
        cl = clashes(cr)
        if verbose:
            report(f"  pass {attempt}: end {end:.1f} scale {scale:.3f} clashes {len(cl)} first {cl[:1]}")
        if not cl:
            report(f"DINNER SCHEDULE: pudding cleared at {end:.1f}s, in the pub at {cr.D:.0f}s, eat scale "
                   f"{scale:.2f}, {len(delays)} delays after {attempt} passes")
            return cr
        t, a, b = cl[0]
        movers = [m for m in (a, b) if not m.startswith("R:")]
        if verbose:
            report(f"     clash {a} / {b} at {t:.1f}s")
            i0 = int(t / 0.25)
            for who in movers:
                pp = _roots(actor(cr, who).f)[i0]
                ti = task_at(cr, who, t)
                lab = actor(cr, who).tasks[ti][2] if ti is not None else "-"
                report(f"     {who} at ({pp.x:.2f},{pp.y:.2f}) task {lab}")
        cand = [(task_at(cr, m, t), m) for m in movers]
        cand = [(i, m) for i, m in cand if i is not None]
        if not cand:
            raise RuntimeError(f"dinner: {a} and {b} clash at {t:.1f}s outside any task")
        # Delay the task that started later.
        def start(im):
            i, m = im
            return actor(cr, m).tasks[i][0]

        def moving(m):
            f = actor(cr, m).f
            tr = _roots(f)
            i0 = int(t / 0.25)
            return (tr[min(len(tr) - 1, i0 + 2)] - tr[max(0, i0 - 2)]).length > 0.05
        mv = [im for im in cand if moving(im[1])]
        i, m = (mv[0] if len(mv) == 1 else max(cand, key=start))
        delays[(m, i)] = delays.get((m, i), 0.0) + 2.0
    raise RuntimeError("dinner schedule did not settle")


# --- Realise ------------------------------------------------------------------
IK_BONES = ("UpperArm.L", "UpperArm.R", "Forearm.L", "Forearm.R", "Hand.L", "Hand.R",
            "Thigh.L", "Thigh.R", "Shin.L", "Shin.R", "Foot.L", "Foot.R")
BASIS_BONES = ("Root", "Hips", "Spine", "Chest", "Head")


def done_all(fig):
    for k in (fig.root, fig.zk, fig.vis, fig.lean, fig.pitch, fig.yaw, fig.twist, fig.L, fig.R, fig.fL, fig.fR,
              getattr(fig, "bow", None)):
        if k:
            k.done()


def solve(fig, arm, poles):
    sc = bpy.context.scene
    pb = arm.pose.bones
    p = fig.tag + "_"
    objs, cons = [], []

    def ik(bone, side, pole_angle):
        tg = bpy.data.objects.new(f"DinTgt{bone}{side}", None)
        pl = bpy.data.objects.new(f"DinPole{bone}{side}", None)
        sc.collection.objects.link(tg)
        sc.collection.objects.link(pl)
        objs.extend((tg, pl))
        c = pb[p + f"{bone}.{side}"].constraints.new('IK')
        c.target, c.pole_target, c.pole_angle, c.chain_count = tg, pl, pole_angle, 2
        cons.append((pb[p + f"{bone}.{side}"], c))
        return tg, pl
    arms = {s: ik("Forearm", s, poles[s]) for s in ("L", "R")}
    legs = {s: ik("Shin", s, poles["leg"]) for s in ("L", "R")}
    S = {name: sample(getattr(fig, name)) for name in ("root", "zk")}
    rs, zs = S["root"], S["zk"]

    def root_at(t):                         # frame-grid lookups for the at_world/to_local callables
        i = min(N, max(0, int(round(t * FPS))))
        return Vector((rs[i].x, rs[i].y, zs[i])), math.radians(rs[i].z)

    def rot_at(t):
        i = min(N, max(0, int(round(t * FPS))))
        return Matrix.Rotation(math.radians(rs[i].z), 3, 'Z')
    fig.root_at, fig.rot_at = root_at, rot_at
    for name in ("lean", "pitch", "yaw", "twist", "L", "R", "fL", "fR"):
        S[name] = sample(getattr(fig, name))
    S["bow"] = sample(fig.bow) if getattr(fig, "bow", None) else [0.0] * (N + 1)
    M = {p + b: np.empty((N + 1, 4, 4)) for b in IK_BONES + BASIS_BONES}
    rec = dict(palm={"L": np.empty((N + 1, 3)), "R": np.empty((N + 1, 3))},
               hand={"L": np.empty((N + 1, 3, 3)), "R": np.empty((N + 1, 3, 3))},
               yaw=np.empty(N + 1), pos=np.empty((N + 1, 3)), target={"L": np.empty((N + 1, 3)), "R": np.empty((N + 1, 3))},
               vis=np.array(sample(fig.vis), float) if fig.vis else np.ones(N + 1))
    R0 = fig.R0
    for fi in range(N + 1):
        r = S["root"][fi]
        pos = Vector((r.x, r.y, S["zk"][fi]))
        R3 = Matrix.Rotation(math.radians(r.z), 3, 'Z')
        pb[p + "Root"].matrix_basis = Matrix.Translation(pos - R0) @ R3.to_4x4()
        lean = math.radians(S["lean"][fi])
        tw = math.radians(S["twist"][fi])
        pb[p + "Hips"].matrix_basis = Matrix.Rotation(-math.radians(S["bow"][fi]), 4, 'X')
        pb[p + "Spine"].matrix_basis = Matrix.Rotation(0.4 * tw, 4, 'Y') @ Matrix.Rotation(-0.4 * lean, 4, 'X')
        pb[p + "Chest"].matrix_basis = Matrix.Rotation(0.6 * tw, 4, 'Y') @ Matrix.Rotation(-0.6 * lean, 4, 'X')
        pb[p + "Head"].matrix_basis = (Matrix.Rotation(math.radians(S["yaw"][fi]), 4, 'Y') @
                                       Matrix.Rotation(-math.radians(S["pitch"][fi]), 4, 'X'))
        for side, key, sx in (("L", "L", -1), ("R", "R", 1)):
            tgt = pos + R3 @ S[key][fi]
            arms[side][0].location = tgt
            arms[side][1].location = pos + R3 @ Vector((sx * 0.45, -0.35, 1.0))
            rec["target"][side][fi] = S[key][fi]
        for side, key, sx in (("L", "fL", -1), ("R", "fR", 1)):
            legs[side][0].location = pos + R3 @ S[key][fi]
            legs[side][1].location = pos + R3 @ Vector((sx * 0.12, 1.2, 0.9))
        bpy.context.view_layer.update()
        right = R3 @ Vector((1.0, 0.0, 0.0))
        for side, toward in (("L", 1), ("R", -1)):
            hand = pb[p + f"Hand.{side}"].matrix
            raw = hand.translation + hand.col[1].xyz.normalized() * 0.045
            rec["palm"][side][fi] = raw + right * (0.052 * toward)
            rec["hand"][side][fi] = np.array(hand.to_3x3())
        rec["yaw"][fi] = r.z
        rec["pos"][fi] = pos
        for b in IK_BONES:
            bone = pb[p + b]
            M[p + b][fi] = np.array(arm.convert_space(pose_bone=bone, matrix=bone.matrix, from_space='POSE',
                                                      to_space='LOCAL'))
        for b in BASIS_BONES:
            M[p + b][fi] = np.array(pb[p + b].matrix_basis)
    for bone, c in cons:
        bone.constraints.remove(c)
    for o in objs:
        bpy.data.objects.remove(o)
    for b in arm.pose.bones:
        b.matrix_basis = Matrix.Identity(4)
    return M, rec


def mats_to_quats(m):
    """(n,3,3) rotation matrices -> (n,4) wxyz quaternions."""
    out = np.empty((len(m), 4))
    for i in range(len(m)):
        out[i] = Matrix(m[i].tolist()).to_quaternion()
    return out


def _channelbag(arm, name):
    act = bpy.data.actions.new(name)
    arm.animation_data_create()
    arm.animation_data.action = act
    slot = arm.animation_data.action_slot
    if slot is None:
        slot = act.slots.new(id_type='OBJECT', name=arm.name)
        arm.animation_data.action_slot = slot
    return anim_utils.action_ensure_channelbag_for_slot(act, slot)


def _write_rows(cb, bone, path, rows, tol, default):
    """rows: (width, n). Skips a channel that never leaves its default."""
    if np.all(np.abs(rows - np.asarray(default)[:, None]) < 1e-6):
        return 0
    keep = thin(rows, tol)
    dp = f'pose.bones["{bone}"].{path}'
    for i in range(rows.shape[0]):
        fc = cb.fcurves.new(dp, index=i, group_name=bone)
        fc.keyframe_points.add(len(keep))
        co = np.empty(2 * len(keep))
        co[0::2] = keep
        co[1::2] = rows[i, keep]
        fc.keyframe_points.foreach_set("co", co.tolist())
        for kp in fc.keyframe_points:
            kp.interpolation = 'LINEAR'
        fc.update()
    return len(keep)


def write_fig(fig, arm, M, clip, vis=None):
    cb = _channelbag(arm, f"Fig_{fig.tag}{clip}")
    kept = 0
    per = {}
    if vis is not None:                          # out of sight (the loo): the whole figure scaled away
        kept += _write_rows(cb, f"{fig.tag}_Root", "scale", np.repeat(np.asarray(vis, float)[None, :], 3, 0),
                            0.002, (1, 1, 1))
    for name, mats in M.items():
        locs = mats[:, :3, 3]
        q = mats_to_quats(mats[:, :3, :3])
        for i in range(1, len(q)):
            if np.dot(q[i], q[i - 1]) < 0:
                q[i] = -q[i]
        a = _write_rows(cb, name, "location", locs.T.copy(), TOL_LOC, (0, 0, 0))
        b = _write_rows(cb, name, "rotation_quaternion", q.T.copy(), TOL_ROT, (1, 0, 0, 0))
        per[name.split("_", 1)[1]] = (a, b)
        kept += a + b
    if DEBUG:
        print(f"  {fig.tag} keys per bone (loc, rot): {per}")
    return kept


# --- Prop rig -----------------------------------------------------------------
CHINA, GOLD, SILVER = "f4f1ea", "b8954a", "cfd1d5"


def _plate_mesh(P, b, food, r, course):
    P.seg(b, (0, 0, 0), (0, 0, 0.006), r * 0.62, r * 0.66, CHINA, segs=12, caps=False)
    P.seg(b, (0, 0, 0.007), (0, 0, 0.0115), r * 1.012, r * 1.012, GOLD, segs=18, caps=False)
    P.seg(b, (0, 0, 0.006), (0, 0, 0.014), r * 0.97, r, CHINA, segs=18)
    z = 0.014
    rng = random.Random(course)
    if course == "salmon":
        for x in (-0.035, 0.0, 0.035):
            P.seg(food, (x, -0.03, z + 0.013), (x, 0.03, z + 0.013), 0.014, 0.014, "e9846b", segs=10)
        for _ in range(5):
            P.box(food, (rng.uniform(-0.05, 0.05), rng.uniform(0.035, 0.06), z + 0.004), (0.02, 0.012, 0.006), "4f7a2a")
        P.box(food, (0.06, -0.04, z + 0.008), (0.03, 0.012, 0.014), "f2d64b")
    elif course == "soup":
        P.seg(b, (0, 0, 0.014), (0, 0, 0.056), 0.058, 0.086, CHINA, segs=14)
        P.seg(food, (0, 0, 0.056), (0, 0, 0.058), 0.076, 0.076, "d6a443", segs=14)
        P.ball(food, (0.0, 0.01, 0.059), 0.014, "f2ead2", scale=(1.6, 1, 0.25), segs=10, rings=4)
        P.box(food, (0.012, 0.014, 0.061), (0.012, 0.006, 0.003), "3f7a2c")
    elif course == "sole":
        P.seg(food, (0, 0, z), (0, 0, z + 0.002), 0.075, 0.075, "e6cf72", segs=18)
        P.box(food, (0, 0.005, z + 0.012), (0.13, 0.055, 0.02), "f1ebe0")
        for i in range(5):
            P.box(food, (-0.03 + i * 0.014, -0.06, z + 0.006), (0.008, 0.06, 0.008), "3f7a2c")
        P.box(food, (0.07, 0.04, z + 0.008), (0.03, 0.012, 0.014), "f2d64b")
    elif course == "sorbet":
        P.seg(b, (0, 0, z), (0, 0, z + 0.006), 0.03, 0.03, SILVER, segs=14)
        P.seg(b, (0, 0, z + 0.006), (0, 0, z + 0.065), 0.006, 0.006, SILVER, segs=8)
        P.seg(b, (0, 0, z + 0.065), (0, 0, z + 0.10), 0.02, 0.055, SILVER, segs=16)
        P.ball(food, (0, 0, z + 0.115), 0.032, "f3edb4", segs=12, rings=8)
        P.box(food, (0.012, 0.0, z + 0.148), (0.016, 0.008, 0.004), "4f8a3a")
    elif course == "beef":
        P.seg(food, (0, 0, z), (0, 0, z + 0.002), 0.08, 0.08, "4a2414", segs=18)
        P.box(food, (-0.015, 0.0, z + 0.024), (0.085, 0.055, 0.045), "c4893e")
        P.box(food, (-0.015, -0.0285, z + 0.024), (0.06, 0.002, 0.03), "b3424a")
        for i in range(3):
            P.ball(food, (0.06, -0.035 + i * 0.03, z + 0.016), 0.018, "e0c068", segs=8, rings=6)
        for i in range(3):
            P.seg(food, (-0.07 + i * 0.03, 0.05, z + 0.008), (-0.06 + i * 0.03, 0.09, z + 0.008), 0.008, 0.003, "e07a2a", segs=6)
        P.box(food, (0.0, 0.06, z + 0.006), (0.05, 0.02, 0.01), "3f7a2c")
    elif course == "cheese":
        P.box(food, (-0.04, 0.02, z + 0.015), (0.06, 0.035, 0.03), "f0c24a")
        P.box(food, (0.03, 0.03, z + 0.013), (0.055, 0.03, 0.026), "f3ead2")
        P.box(food, (0.0, -0.035, z + 0.014), (0.05, 0.035, 0.028), "d8d8c8")
        for i in range(3):
            P.box(food, (-0.01 + i * 0.01, -0.035, z + 0.029), (0.006, 0.006, 0.002), "3c5a8a")
        for i in range(5):
            P.ball(food, (0.06 + (i % 2) * 0.014, -0.03 + i * 0.012, z + 0.01), 0.009, "5a2a5a", segs=6, rings=4)
        for i in range(3):
            P.seg(food, (-0.075, -0.04 + i * 0.03, z), (-0.075, -0.04 + i * 0.03, z + 0.004), 0.016, 0.016, "d9b77a", segs=10)
    else:                                            # chocolate torte, raspberries, cream
        P.seg(food, (0, 0, z), (0, 0, z + 0.002), 0.07, 0.07, "8a1a2a", segs=18)
        P.box(food, (-0.01, 0.0, z + 0.022), (0.08, 0.045, 0.04), "3a1f14")
        P.box(food, (-0.01, 0.0, z + 0.043), (0.08, 0.045, 0.004), "24120c")
        for i in range(3):
            P.ball(food, (0.055, -0.03 + i * 0.025, z + 0.012), 0.011, "c0233b", segs=8, rings=6)
        P.ball(food, (-0.01, 0.05, z + 0.016), 0.018, "f6f0e2", scale=(1.4, 1, 0.8), segs=10, rings=6)
        P.box(food, (0.0, 0.055, z + 0.034), (0.016, 0.008, 0.003), "4f8a3a")


GLASS_SHAPE = {   # foot r, stem top, bowl (z0, r0, z1, r1), liquid (z0, r0, z1, r1)
    "champ": (0.032, 0.104, (0.104, 0.012, 0.25, 0.026), (0.110, 0.011, 0.235, 0.024)),
    "white": (0.034, 0.085, (0.088, 0.030, 0.20, 0.036), (0.094, 0.028, 0.19, 0.034)),
    "red": (0.038, 0.075, (0.078, 0.044, 0.21, 0.042), (0.084, 0.041, 0.195, 0.040)),
    "sweet": (0.028, 0.060, (0.062, 0.025, 0.135, 0.028), (0.067, 0.023, 0.125, 0.026)),
    "cognac": (0.034, 0.035, (0.038, 0.044, 0.120, 0.030), (0.042, 0.040, 0.085, 0.042)),   # snifter
    "whisky": (0.036, 0.004, (0.004, 0.036, 0.095, 0.038), (0.008, 0.033, 0.055, 0.034)),   # tumbler
}


def _glass_mesh(P, b, liq, wine):
    fr, st, (bz0, br0, bz1, br1), (lz0, lr0, lz1, lr1) = GLASS_SHAPE[wine]
    P.seg(b, (0, 0, 0), (0, 0, 0.004), fr, fr, "e8e4dc", segs=14, mat=1)
    P.seg(b, (0, 0, 0.004), (0, 0, st), 0.004, 0.004, "e8e4dc", segs=8, mat=1)
    P.seg(b, (0, 0, bz0), (0, 0, bz1), br0, br1, "e8e4dc", segs=12, caps=False, mat=1)
    P.seg(b, (0, 0, bz0), (0, 0, bz0 + 0.004), br0, br0, "e8e4dc", segs=16, mat=1)
    P.seg(liq, (0, 0, lz0), (0, 0, lz1), lr0, lr1, LIQUID[wine], segs=14)


BOTTLE = {"champ": ("1f3a24", "c9a24a"), "white": ("5a7a3a", "e8e0c8"), "red": ("2a0e12", "8a1a2a"),
          "sweet": ("7a4614", "d8c08a"), "cognac": ("6e3a12", "c9a24a"), "whisky": ("b0702a", "e8e0d0")}


def _bottle_mesh(P, b, wine):
    body, foil = BOTTLE[wine]
    s = 0.85 if wine == "sweet" else 1.0
    P.seg(b, (0, 0, 0), (0, 0, 0.20 * s), 0.038, 0.038, body, segs=14)
    P.seg(b, (0, 0, 0.20 * s), (0, 0, 0.25 * s), 0.038, 0.014, body, segs=14)
    P.seg(b, (0, 0, 0.25 * s), (0, 0, 0.31 * s), 0.014, 0.014, foil if wine == "champ" else body, segs=10)
    P.seg(b, (0, 0, 0.29 * s), (0, 0, 0.315 * s), 0.0155, 0.0155, foil, segs=10)
    P.seg(b, (0, 0, 0.07 * s), (0, 0, 0.15 * s), 0.0395, 0.0395, "efe6cf", segs=14)


def _cutlery_mesh(P, b, kind):
    if kind == "fork":
        P.box(b, (0, -0.02, 0), (0.012, 0.11, 0.004), SILVER)
        P.box(b, (0, 0.05, 0), (0.02, 0.03, 0.003), SILVER)
        P.box(b, (0, 0.08, 0), (0.018, 0.035, 0.002), SILVER)
    elif kind == "knife":
        P.box(b, (0, -0.025, 0), (0.014, 0.10, 0.006), SILVER)
        P.box(b, (0, 0.075, 0), (0.017, 0.10, 0.002), "e2e4e7")
    else:
        P.box(b, (0, -0.01, 0), (0.011, 0.12, 0.004), SILVER)
        P.ball(b, (0, 0.075, 0.002), 0.022, SILVER, scale=(0.8, 1.3, 0.3), segs=10, rings=5)


CHAIR_OAK, CHAIR_PAD = "5a381e", "2e4a33"
CHAIR_PARTS = [  # centre (x forward, y left, z), half size, colour: build-penthouse's ladder-back
    ((0.0, 0, 0.42), (0.215, 0.225, 0.03), CHAIR_OAK), ((0.01, 0, 0.46), (0.20, 0.205, 0.012), CHAIR_PAD),
    ((-0.19, 0, 0.90), (0.016, 0.19, 0.05), CHAIR_OAK), ((-0.19, 0, 0.75), (0.013, 0.18, 0.035), CHAIR_OAK),
    ((-0.19, 0, 0.61), (0.013, 0.18, 0.035), CHAIR_OAK), ((0.19, 0, 0.22), (0.012, 0.19, 0.015), CHAIR_OAK),
    ((-0.19, 0, 0.13), (0.012, 0.19, 0.012), CHAIR_OAK)] + [
    part for s in (1, -1) for part in (
        ((0.19, s * 0.20, 0.205), (0.02, 0.02, 0.205), CHAIR_OAK),
        ((-0.19, s * 0.20, 0.50), (0.022, 0.022, 0.50), CHAIR_OAK),
        ((0.0, s * 0.20, 0.13), (0.19, 0.012, 0.012), CHAIR_OAK))]


def _chair_mesh(P, b):
    for (x, y, z), (hx, hy, hz), col in CHAIR_PARTS:   # prop frame: +Y is the sitter's forward
        P.box(b, (-y, x, z), (2 * hy, 2 * hx, 2 * hz), col)


def _tray_mesh(P, b):
    P.seg(b, (0, 0, 0), (0, 0, 0.012), 0.20, 0.20, "c4c6ca", segs=20)
    P.seg(b, (0, 0, 0.008), (0, 0, 0.02), 0.205, 0.205, "aeb1b6", segs=20, caps=False)


def smooth(me, deg=35.0):
    """Smooth by angle: round parts share vertices on export (flat faces each
    carry their own), boxes and caps keep hard edges."""
    me.shade_smooth()
    me.set_sharp_from_angle(angle=math.radians(deg))


class LowParts(RF._Parts):
    """Props are small: cap the tessellation by size (plates stay round)."""

    def seg(self, bone, p0, p1, r0, r1, colour, segs=10, squash=1.0, caps=True, mat=0):
        r = max(r0, r1)
        cap = 16 if r > 0.08 else 12 if r > 0.03 else 8 if r > 0.012 else 6
        super().seg(bone, p0, p1, r0, r1, colour, min(segs, cap), squash, caps, mat)

    def ball(self, bone, c, r, colour, scale=(1, 1, 1), segs=10, rings=6):
        super().ball(bone, c, r, colour, scale, min(segs, 8 if r > 0.02 else 6), min(rings, 5 if r > 0.02 else 4))


def build_props(props, report):
    sc = bpy.context.scene
    arm_data = bpy.data.armatures.new("Fig_DinPropsRig")
    arm = bpy.data.objects.new("Fig_DinProps", arm_data)
    sc.collection.objects.link(arm)
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode='EDIT')
    eb = arm_data.edit_bones
    child_h = {}
    for pr in props.all:
        b = eb.new(f"DinProps_{pr.name}")
        b.head, b.tail = Vector((0, 0, 0)), Vector((0, 0.1, 0))
        if pr.kind in ("plate", "glass"):
            h0 = 0.014 if pr.kind == "plate" else GLASS_SHAPE[pr.sub[1]][3][0]
            cb = eb.new(f"DinProps_{pr.name}Sub")
            cb.head, cb.tail = Vector((0, 0, h0)), Vector((0, 0, h0 + 0.1))
            cb.parent = b
            child_h[pr.name] = h0
    bpy.ops.object.mode_set(mode='OBJECT')
    for pbn in arm.pose.bones:
        pbn.rotation_mode = 'QUATERNION'
    P = LowParts("DinProps_")
    for pr in props.all:
        b, sub = pr.name, pr.name + "Sub"
        if pr.kind == "plate":
            _plate_mesh(P, b, sub, COURSES[[c["key"] for c in COURSES].index(pr.sub[1])]["r"], pr.sub[1])
        elif pr.kind == "glass":
            _glass_mesh(P, b, sub, pr.sub[1])
        elif pr.kind == "bottle":
            _bottle_mesh(P, b, pr.sub)
        elif pr.kind == "cutlery":
            _cutlery_mesh(P, b, pr.sub)
        elif pr.kind == "chair":
            _chair_mesh(P, b)
        elif pr.kind == "cup":
            CF.cup_mesh(P, b)
        else:
            _tray_mesh(P, b)
    me = bpy.data.meshes.new("Fig_DinPropsMesh")
    P.bm.to_mesh(me)
    attr = me.color_attributes.new("Col", 'BYTE_COLOR', 'CORNER')
    cols = [RF._rgba(c) for c in P.cols]
    data = []
    for poly, face in zip(me.polygons, P.bm.faces):
        data.extend(cols[face[P.col]] * poly.loop_total)
    attr.data.foreach_set("color_srgb", data)
    me.color_attributes.active_color = attr
    smooth(me)
    ob = bpy.data.objects.new("Fig_DinPropsBody", me)
    sc.collection.objects.link(ob)
    groups = {}
    for v, bone in P.bone_of_vert.items():
        groups.setdefault(bone, []).append(v.index)
    for bone, verts in groups.items():
        ob.vertex_groups.new(name=bone).add(verts, 1.0, 'REPLACE')
    P.bm.free()
    body, glass = RF._materials()
    me.materials.append(body)
    me.materials.append(glass)
    ob.parent = arm
    ob.modifiers.new("Armature", 'ARMATURE').object = arm
    report(f"PROPS: {len(props.all)} props, {len(me.vertices)} verts")
    return arm


def _segments(pr):
    ev = sorted(pr.ev, key=lambda e: e[0])
    segs = []
    for i, (t, h) in enumerate(ev):
        f0 = int(round(t * FPS))
        f1 = int(round(ev[i + 1][0] * FPS)) if i + 1 < len(ev) else N + 1
        f1 = min(f1, N + 1)
        if segs and f0 <= segs[-1][0]:
            segs[-1][2] = h                  # same frame: the later holder wins
            segs[-1][1] = f1
            continue
        if segs:
            segs[-1][1] = f0
        segs.append([f0, f1, h])
    if not segs or segs[0][0] != 0:
        raise RuntimeError(f"prop {pr.name} has no state at t=0")
    return segs


def resolve(pr, REC, done):
    """(P (N+1,3), Q (N+1,4), S (N+1)) for one prop."""
    segs = _segments(pr)
    P = np.zeros((N + 1, 3))
    Q = np.zeros((N + 1, 4))
    Q[:, 0] = 1.0
    S = np.ones(N + 1)
    tilt_all = None

    def tilt(a, b):
        nonlocal tilt_all
        if not pr.tilt:
            return np.zeros(b - a)
        if tilt_all is None:
            tilt_all = np.array(sample(pr.tilt), float)
        return tilt_all[a:b]

    def pose(h, a, b):
        n = b - a
        kind = h[0]
        if kind == "spot":
            return np.tile(np.array(h[1][:]), (n, 1)), np.tile(qyaw(h[2]), (n, 1))
        if kind == "glide":                         # a chair drawn out or pushed in
            p0, p1, t0, t1, yaw = h[1:6]
            w = ease_np((np.arange(a, b) / FPS - t0) / (t1 - t0))[:, None]
            p0, p1 = np.array(p0[:]), np.array(p1[:])
            return p0 + (p1 - p0) * w, np.tile(qyaw(yaw), (n, 1))
        if kind == "on":
            tp, tq, _ts = done[h[1].name]
            slot = TRAY_SLOTS[h[2]]
            return tp[a:b] + qrot(tq[a:b], slot), tq[a:b].copy()
        if kind == "hand":
            R = REC[h[1]]
            side, how = h[2], h[3]
            palm, yaw = R["palm"][side][a:b], R["yaw"][a:b]
            qy = qyaw(yaw)
            if how == "plate":
                return palm + qrot(qy, (0, 0.07, -0.016)), qy
            if how == "tray":
                return palm + qrot(qy, (0, 0.06, -0.014)), qy
            if how in ("glass", "bottle"):
                q = qmul(qy, qx(tilt(a, b)))
                return palm - qrot(q, (0, 0, pr.grip)), q
            if how == "cutlery":
                plate_pt, mouth = h[4]
                pz = palm[:, 2]
                w = np.clip((pz - (mouth.z - 0.30)) / 0.15, 0, 1)[:, None]
                d = (np.array(plate_pt[:]) - palm) * (1 - w) + (np.array(mouth[:]) - palm) * w
                d /= np.linalg.norm(d, axis=1, keepdims=True) + 1e-9
                x = np.cross(d, (0, 0, 1))
                x /= np.linalg.norm(x, axis=1, keepdims=True) + 1e-9
                z = np.cross(x, d)
                m = np.stack([x, d, z], -1)
                return palm - d * 0.01, mats_to_quats(m)
        raise ValueError(h)
    for f0, f1, h in segs:
        if h[0] == "hidden":
            S[f0:f1] = 0.001
            continue
        pp, qq = pose(h, f0, f1)
        P[f0:f1], Q[f0:f1] = pp, qq
    # Blends at hand <-> spot/tray handovers.
    for i in range(1, len(segs)):
        a, b = segs[i - 1], segs[i]
        if a[2][0] == "hidden" or b[2][0] == "hidden":
            continue
        ha, hb = a[2][0] == "hand", b[2][0] == "hand"
        if hb and not ha:                          # pick: slide from the spot into the hand
            f0, f1 = b[0], min(b[1], b[0] + BLEND)
            other = a[2]
        elif ha and not hb:                        # place: slide from the hand onto the spot
            f0, f1 = max(a[0], b[0] - BLEND), b[0]
            other = b[2]
        else:
            continue
        if f1 <= f0:
            continue
        op, oq = pose(other, f0, f1)
        w = ease_np((np.arange(f0, f1) - f0 + 1) / (f1 - f0 + 1))
        if not hb:
            P[f0:f1] = P[f0:f1] + (op - P[f0:f1]) * w[:, None]
            Q[f0:f1] = nlerp(Q[f0:f1], oq, w)
        else:
            P[f0:f1] = op + (P[f0:f1] - op) * w[:, None]
            Q[f0:f1] = nlerp(oq, Q[f0:f1], w)
    # Hidden spans wait where the prop next appears, wrapping round the loop
    # (no streak on the toggle, and the seam matches).
    vis = [(f0, f1) for f0, f1, h in segs if h[0] != "hidden"]
    for f0, f1, h in reversed(segs):
        if h[0] != "hidden" or not vis:
            continue
        nxt = [a for a, _b in vis if a >= f1]
        j = nxt[0] if nxt else vis[0][0]
        P[f0:f1], Q[f0:f1] = P[j], Q[j]
    return P, Q, S


def write_props(props, arm, REC, report, clip):
    cb = _channelbag(arm, f"Fig_DinProps{clip}")
    done = {}
    order = [p for p in props.all if p.kind == "tray"] + [p for p in props.all if p.kind != "tray"]
    kept = 0
    kinds = {}
    for pr in order:
        k_before = kept
        P, Q, S = resolve(pr, REC, done)
        done[pr.name] = (P, Q, S)
        for i in range(1, N + 1):
            if np.dot(Q[i], Q[i - 1]) < 0:
                Q[i] = -Q[i]
        bn = f"DinProps_{pr.name}"
        kept += _write_rows(cb, bn, "location", P.T.copy(), 0.006, (0, 0, 0))
        kept += _write_rows(cb, bn, "rotation_quaternion", Q.T.copy(), 0.012, (1, 0, 0, 0))
        kept += _write_rows(cb, bn, "scale", np.tile(S, (3, 1)), 0.002, (1, 1, 1))
        if pr.kind in ("plate", "glass"):
            fk, _end = pr.fill_keys()
            fv = np.array(sample(fk), float)
            if pr.kind == "plate":
                rows = np.tile(np.maximum(fv, 0.001), (3, 1))
            else:
                rows = np.stack([np.ones(N + 1), np.maximum(fv, 0.001), np.ones(N + 1)])
            kept += _write_rows(cb, bn + "Sub", "scale", rows, 0.002, (1, 1, 1))
        kinds[pr.kind] = kinds.get(pr.kind, 0) + kept - k_before
    report(f"FIGURE DinProps{clip}: {len(props.all)} props, {kept} keys {kinds}")
    return done


# --- Gates --------------------------------------------------------------------
def gate_targets(recs, report):
    """A hand target that jumps in one frame means two actions overlap."""
    ok = True
    for tag, R in recs.items():
        for side in ("L", "R"):
            d = np.linalg.norm(np.diff(R["target"][side], axis=0), axis=1)
            if d.max() > 0.15:
                report(f"DINNER TARGET GATE: {tag}.{side} target jumps {d.max():.2f} m at {d.argmax() / FPS:.1f}s")
                ok = False
    return ok


def gate_spacing(recs, report, rovers_from=None):
    """Nobody too close to anyone (while both are visible); with rovers_from,
    nobody within 0.40 m of a Rovers regular from then on (phase-locked)."""
    staff = [t for t in recs if t in (WAITER_TAG["W1"], WAITER_TAG["W2"], CHEF_TAG)]
    guests = [t for t in recs if t not in staff]
    vis = {t: recs[t]["vis"] > 0.5 for t in recs}
    bad = {}
    for fi in range(0, N + 1, 3):
        for i, a in enumerate(staff):
            pa = recs[a]["pos"][fi, :2]
            for b in staff[i + 1:]:
                d = np.linalg.norm(pa - recs[b]["pos"][fi, :2])
                if d < 0.45:
                    bad.setdefault((a, b), (fi / FPS, d))
            for b in guests:
                d = np.linalg.norm(pa - recs[b]["pos"][fi, :2])
                if d < 0.34 and vis[b][fi]:
                    bad.setdefault((a, b), (fi / FPS, d))
        for i, a in enumerate(guests):
            for b in guests[i + 1:]:
                d = np.linalg.norm(recs[a]["pos"][fi, :2] - recs[b]["pos"][fi, :2])
                if d < 0.38 and vis[a][fi] and vis[b][fi]:
                    bad.setdefault((a, b), (fi / FPS, d))
    if rovers_from is not None:
        step = 1.0 / FPS
        rv = rovers_tracks(step)
        n_ph = int(round(PHASE / step))
        for fi in range(int(math.ceil(rovers_from * FPS)), N + 1, 3):
            j = int(round((fi / FPS) % PHASE / step)) % n_ph
            for tag, xy, v in rv:
                if not v[j]:
                    continue
                for a in recs:
                    if not vis[a][fi]:
                        continue
                    d = np.linalg.norm(recs[a]["pos"][fi, :2] - xy[j])
                    if d < 0.40:
                        bad.setdefault((a, "Rovers " + tag), (fi / FPS, d))
    for (a, b), (t, d) in bad.items():
        report(f"DINNER SPACING GATE: {a} and {b} {d:.2f} m apart at {t:.1f}s")
    return not bad


def gate_routes(recs, report):
    sc = bpy.context.scene
    if not bpy.data.objects.get("DiningTable"):
        report("DINNER ROUTE GATE: skipped (no dining room geometry in this scene)")
        return True
    hidden = []
    for o in sc.objects:
        if o.name.startswith(("Fig_", "NavMesh", "Seat_", "Spawn_")) and not o.hide_viewport:
            o.hide_viewport = True
            hidden.append(o)
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    bad = {}
    for tag in recs:
        pos = recs[tag]["pos"]
        for fi in range(2, N + 1, 2):
            a, b = pos[fi - 2], pos[fi]
            fz = floor_z(b[0], b[1])
            if np.linalg.norm(b[:2] - a[:2]) < 0.004 or abs(b[2] - fz) > 0.012 or abs(a[2] - b[2]) > 0.02:
                continue
            if recs[tag]["vis"][fi] < 0.5 or (b[1] < -9.8 and min(a[0], b[0]) < -3.3):
                continue
            for off in ((0, 0), (0.12, 0), (-0.12, 0), (0, 0.12), (0, -0.12)):
                o = Vector((b[0] + off[0], b[1] + off[1], 1.6))
                hit, loc, _n, _i, ob, _m = sc.ray_cast(dg, o, Vector((0, 0, -1)))
                if hit and loc.z > max(fz, floor_z(o.x, o.y)) + 0.08:      # (the step up is floor)
                    bad.setdefault(tag, (fi / FPS, ob.name, tuple(round(c, 2) for c in loc)))
            # Walls and glass: a down-cast starting inside a thin sheet misses
            # it, so also look along the step at hip and chest height.
            d = Vector((b[0] - a[0], b[1] - a[1], 0.0))
            for z in (0.9, 1.4):
                hit, loc, _n, _i, ob, _m = sc.ray_cast(dg, Vector((a[0], a[1], z)), d.normalized(), distance=d.length)
                if hit:
                    bad.setdefault(tag, (fi / FPS, ob.name, tuple(round(c, 2) for c in loc)))
    for o in hidden:
        o.hide_viewport = False
    for tag, (t, ob, loc) in bad.items():
        report(f"DINNER ROUTE GATE: {tag} walks into {ob} at {loc} ({t:.1f}s)")
    return not bad


def gate_props(props, done, REC, report, seam=True):
    """Handovers within reach, no visible prop jumping, seam continuous."""
    ok = True
    worst = (0.0, None)
    for pr in props.all:
        P, Q, S = done[pr.name]
        vis = S > 0.5
        jump = np.linalg.norm(np.diff(P, axis=0), axis=1)
        jump[~(vis[1:] & vis[:-1])] = 0
        if jump.max() > 0.30:
            fi = int(jump.argmax())
            report(f"DINNER PROP GATE: {pr.name} jumps {jump.max():.2f} m at {fi / FPS:.1f}s")
            if DEBUG:
                for sg in _segments(pr):
                    if sg[0] - 30 <= fi <= sg[1] + 30:
                        report(f"    seg {sg[0]}..{sg[1]} {sg[2][:4] if sg[2][0] != 'on' else ('on', sg[2][2])}")
                for q in range(fi - 3, fi + 4):
                    report(f"    f{q} P {np.round(P[q], 3)} S {S[q]:.3f}")
            ok = False
        if seam and (np.linalg.norm(P[0] - P[N]) > 0.003 or abs(S[0] - S[N]) > 1e-3):
            report(f"DINNER PROP GATE: {pr.name} not continuous across the loop seam")
            ok = False
        fk, end = pr.fill_keys()
        if seam and pr.kind in ("plate", "glass") and abs(end - pr.fill0) > 1e-3:
            report(f"DINNER PROP GATE: {pr.name} fill {pr.fill0:.2f} at 0 but {end:.2f} at the seam")
            ok = False
        segs = _segments(pr)
        for i in range(1, len(segs)):
            a, b = segs[i - 1][2], segs[i][2]
            if (a[0] == "hand") == (b[0] == "hand") or "hidden" in (a[0], b[0]):
                continue
            h, other, fi = (b, a, segs[i][0]) if b[0] == "hand" else (a, b, segs[i][0] - 1)
            R = REC[h[1]]
            palm = R["palm"][h[2]][fi]
            if other[0] == "spot":
                op = np.array(other[1][:])
            else:
                op = done[other[1].name][0][fi] + qrot(done[other[1].name][1][fi], TRAY_SLOTS[other[2]])
            want = {"plate": np.array((0, 0, 0.016)), "tray": np.array((0, 0, 0.014))}.get(h[3], np.array((0, 0, pr.grip)))
            e = np.linalg.norm(op + want - palm) - (0.07 if h[3] == "plate" else 0.06 if h[3] == "tray" else 0.0)
            if DEBUG:
                MISSES.append((e, pr.kind, h[3], h[1], f"{pr.name} {h[1]}.{h[2]} at {fi / FPS:.1f}s"))
            if e > worst[0]:
                worst = (e, f"{pr.name} {h[1]}.{h[2]} at {fi / FPS:.1f}s")
    report(f"DINNER REACH: worst handover miss {worst[0] * 100:.0f} cm ({worst[1]})")
    if worst[0] > 0.16:
        ok = False
    return ok


# --- Build --------------------------------------------------------------------
def set_clip(length):
    global LOOP, N
    LOOP = float(length)
    N = int(round(LOOP * FPS))


def solve_clip(figs, rigs, label, report):
    """Solve every figure, correcting handover targets over up to four passes."""
    REC_NOW.clear()
    MATS = {}
    todo = {f.tag for f in figs}
    for it in range(4):
        for fig in figs:
            if fig.tag in todo:
                arm, poles = rigs[fig.tag]
                M, rec = solve(fig, arm, poles)
                MATS[fig.tag] = {k: v.astype(np.float32) for k, v in M.items()}
                REC_NOW[fig.tag] = rec
                del M
        todo = set()
        errs = []
        for c in CONTACTS:
            R = REC_NOW[c.tag]
            fi = min(N, int(round(c.t * FPS)))
            err = c.want(R, fi) - Vector(R["palm"][c.side][fi])
            errs.append(err.length)
            if err.length > 0.012 and it < 3:
                c.corr += Matrix.Rotation(-math.radians(R["yaw"][fi]), 3, 'Z') @ err
                if err.length > 0.025:
                    todo.add(c.tag)
        e = np.array(errs) if errs else np.zeros(1)
        report(f"{label} CONTACTS pass {it}: {len(errs)} handovers, median {np.median(e) * 100:.1f} cm, "
               f"95% {np.percentile(e, 95) * 100:.1f} cm, worst {e.max() * 100:.1f} cm; re-solve {sorted(todo)}")
        if not todo:
            break
    return dict(REC_NOW), MATS


def gate_switch(md, ml, dd, dl, report):
    """The lounge loop must start exactly where the dinner ends."""
    wf, wp = (0.0, None), (0.0, None)
    for tag, bones in md.items():
        for b, m in bones.items():
            e = float(np.abs(m - ml[tag][b][0]).max())
            if e > wf[0]:
                wf = (e, b)
    for name, (P, Q, S) in dd.items():
        P2, Q2, S2 = dl[name]
        if S[-1] < 0.5 and S2[0] < 0.5:               # hidden in both: where it waits doesn't show
            continue
        e = max(float(np.abs(P[-1] - P2[0]).max()), float(abs(S[-1] - S2[0])),
                float(min(np.abs(Q[-1] - Q2[0]).max(), np.abs(Q[-1] + Q2[0]).max())))
        if e > wp[0]:
            wp = (e, name)
    # Hands and bodies are placed exactly (targets match); from a cold solver
    # start an elbow can settle a few degrees differently for the same hand,
    # a ~2 cm shift once per session, so bones get 0.1 (about 6 degrees).
    ok = wf[0] < 0.10 and wp[0] < 0.02
    report(f"DINNER SWITCH GATE: dinner end vs lounge start, figures {wf[0]:.4f} ({wf[1]}), "
           f"props {wp[0]:.4f} ({wp[1]}) {'ok' if ok else 'JUMPS'}")
    return ok


def to_nla(arm, names):
    """Both clips as NLA tracks (each exports as its own glTF animation)."""
    ad = arm.animation_data
    ad.action = None
    for nm in names:
        act = bpy.data.actions[nm]
        tr = ad.nla_tracks.new()
        tr.name = nm
        st = tr.strips.new(nm, 0, act)
        if act.slots:
            st.action_slot = act.slots[0]


def build(report=print, strict=True):
    import time
    t_start = time.time()
    sc = bpy.context.scene
    sc.render.fps = FPS
    sc.render.fps_base = 1.0
    # --- Dinner: once per session (authored on a long timeline, cut to D).
    set_clip(11 * PHASE)
    crd = plan(report)
    finish(crd)
    figs_d = [g.f for g in crd.guests.values()] + [crd.W["W1"].f, crd.W["W2"].f, crd.chef.f] + \
        [crd.mime.f, crd.couple["A"].f, crd.couple["B"].f]
    RIGS = {}
    for fig in figs_d:
        done_all(fig)
        arm = RF._build_armature(fig)
        smooth(RF._build_mesh(fig, arm).data)
        RIGS[fig.tag] = (arm, RF._pick_poles(fig, arm))
    D = crd.D
    set_clip(D)
    for fig in figs_d:
        fig.loop = D
    REC_D, MATS = solve_clip(figs_d, RIGS, "DINNER", report)
    end_tgt = {t: (REC_D[t]["target"]["L"][-1].copy(), REC_D[t]["target"]["R"][-1].copy(),
                   REC_D[t]["palm"]["R"][-1].copy()) for t in REC_D}
    total = 0
    last_d = {}
    for fig in figs_d:
        M = {k: v.astype(np.float64) for k, v in MATS[fig.tag].items()}
        kept = write_fig(fig, RIGS[fig.tag][0], M, "Dinner", REC_D[fig.tag]["vis"])
        last_d[fig.tag] = {k: v[-1] for k, v in M.items()}
        total += kept
        report(f"FIGURE {fig.tag}Dinner: {N + 1} frames -> {kept} keys")
    MATS.clear()
    parm = build_props(crd.P, report)
    done_d = write_props(crd.P, parm, REC_D, report, "Dinner")
    carm = CF.build_rig(report)
    cafe_d = CF.write_clip(carm, crd.mime, REC_D[CF.TAGS["M"]], "Dinner", report)
    ok = (gate_targets(REC_D, report) & gate_spacing(REC_D, report, crd.La + LINGER) & gate_routes(REC_D, report) &
          gate_props(crd.P, done_d, REC_D, report, seam=False))
    end_d = {k: (v[0][-1:], v[1][-1:], v[2][-1:]) for k, v in done_d.items()}
    del done_d, REC_D
    report(f"DINNER: {D:.0f}s once per session, {sum(g.bites for g in crd.guests.values())} bites, "
           f"{total} figure keys")
    # --- Lounge: loops after the dinner.
    set_clip(LOUNGE_LOOP)
    crl = plan_lounge(report, crd)
    finish_lounge(crl, crd)
    figs_l = [g.f for g in crl.guests.values()] + [crl.W["W1"].f, crl.W["W2"].f, crl.chef.f] + \
        [crl.mime.f, crl.couple["A"].f, crl.couple["B"].f]
    R0 = {f.tag: f.R0 for f in figs_d}
    for fig in figs_l:
        done_all(fig)
        fig.R0 = R0[fig.tag]
    REC_L, MATS = solve_clip(figs_l, RIGS, "LOUNGE", report)
    first_l = {}
    for fig in figs_l:
        M = {k: v.astype(np.float64) for k, v in MATS[fig.tag].items()}
        kept = write_fig(fig, RIGS[fig.tag][0], M, "Lounge", REC_L[fig.tag]["vis"])
        first_l[fig.tag] = {k: v[:1] for k, v in M.items()}
        total += kept
        report(f"FIGURE {fig.tag}Lounge: {N + 1} frames -> {kept} keys")
    MATS.clear()
    done_l = write_props(crl.P, parm, REC_L, report, "Lounge")
    cafe_l = CF.write_clip(carm, crl.mime, REC_L[CF.TAGS["M"]], "Lounge", report)
    ok &= CF.gate(cafe_d, cafe_l, report)
    ok &= (gate_targets(REC_L, report) & gate_spacing(REC_L, report, 0.0) & gate_routes(REC_L, report) &
           gate_props(crl.P, done_l, REC_L, report, seam=True))
    ok &= gate_switch(last_d, first_l, end_d, done_l, report)
    for t in REC_L:
        a, b = end_tgt[t], (REC_L[t]["target"]["L"][0], REC_L[t]["target"]["R"][0], REC_L[t]["palm"]["R"][0])
        e = [float(np.linalg.norm(x - y)) for x, y in zip(a, b)]
        if max(e) > 0.005:
            report(f"  switch {t}: target L {e[0]:.3f} R {e[1]:.3f} palm R {e[2]:.3f}; dinner R {np.round(a[1], 3)} "
                   f"lounge R {np.round(b[1], 3)}")
    for fig in figs_d:
        to_nla(RIGS[fig.tag][0], [f"Fig_{fig.tag}Dinner", f"Fig_{fig.tag}Lounge"])
    to_nla(parm, ["Fig_DinPropsDinner", "Fig_DinPropsLounge"])
    to_nla(carm, ["Fig_DinCafePropsDinner", "Fig_DinCafePropsLounge"])
    # The client's cut: inject-hubs reads the linger window off this empty's name.
    if crd.D % PHASE > 1e-6 or LOUNGE_LOOP % PHASE > 1e-6:
        raise RuntimeError(f"dinner {crd.D}s / lounge {LOUNGE_LOOP}s not whole PHASEs")
    meta = bpy.data.objects.new(f"DinnerMeta_L{int(round(crd.La * 1000))}_W{int(LINGER)}_P{int(PHASE)}", None)
    sc.collection.objects.link(meta)
    report(f"DINNER LINGER: {crd.La:.1f}s + {LINGER:.0f}s, dinner {crd.D:.0f}s, phase {PHASE:.0f}s")
    report(f"DINNER: {total} figure keys, {time.time() - t_start:.0f}s")
    report(f"DINNER GATE {'passed' if ok else 'FAILED'}")
    if strict and not ok:
        raise RuntimeError("DINNER GATE failed")
    sc.frame_set(0)
    return crd


import cafe_figures as CF                    # noqa: E402  (the café; it imports this module)
