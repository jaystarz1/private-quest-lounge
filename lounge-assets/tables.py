# The café mime among the tables after his finale (the lounge loop, cafe_figures
# author_lounge). Each round of the room (a PHASE) he goes from the front of the
# stage to the café couple's table, round the end of the booths' partition to
# Jay's, on to the dinner party in the snug, back across to the booth couple
# at the table by the stage and along to the shelf couple at the far end, and
# home. At every table a little chat, two close-up tricks (three in the snug)
# and a bow; which tricks changes every round (VISITS: no table sees the same
# one twice in the loop's four rounds). The booth regulars watch him at their
# tables at the same marks of every round (rovers_figures TABLE_VISITS: their
# After clip is one PHASE long).
import math
import random

import numpy as np
from mathutils import Vector

import rovers_figures as RF
import dinner_figures as DF
import cafe_figures as CF
from nights import P, pose, squat, stand_up, Q_ID

V = Vector
HR = CF.HR
F_Z = RF.CARPET                                     # the Rovers floor
TOP = RF.TABLE_Z                                    # a booth table's top (world z)

# --- Where he stands -------------------------------------------------------------------------
C_SPOT = (2.56, -11.56)                             # at the café couple's table (their booth's open corner)
J_SPOT = (3.06, -11.52)                             # at Jay's (the other side of the booths' partition)
TT_SPOT = RF.TABLE_VISITS["tt"][0]
ST_SPOT = RF.TABLE_VISITS["st"][0]
VENUE = {
    "couple": dict(spot=C_SPOT, table=RF.BOOTH_TABLES["CT"], who=[RF.CAB_SEATS["A"][:2], RF.CAB_SEATS["B"][:2]]),
    "jay": dict(spot=J_SPOT, table=RF.BOOTH_TABLES["JT"], who=[(3.54, RF.BENCH_Y), (3.54, RF.BOOTH_STOOL_Y)]),
    "snug": dict(spot=CF.SNUG_SPOT, table=None, who=[DF.PUB[k]["root"] for k in DF.GUESTS]),
    "tt": dict(spot=TT_SPOT, table=RF.BOOTH_TABLES["TT"], who=list(RF.TABLE_VISITS["tt"][4])),
    "st": dict(spot=ST_SPOT, table=RF.BOOTH_TABLES["ST"], who=list(RF.TABLE_VISITS["st"][4])),
}
AISLE = -12.36                                      # the way along the room, south of the stools
HOME_TO_C = CF.DOWN_STEP + [(C_SPOT[0], AISLE), C_SPOT]
C_TO_J = [C_SPOT, (2.83, -11.70), J_SPOT]          # (round the end of the partition)
J_TO_SNUG = [J_SPOT, (J_SPOT[0], AISLE), (3.90, -12.40), DF.SNUG_IN, (4.75, DF.GAP_Y), CF.SNUG_SPOT]
SNUG_TO_TT = [CF.SNUG_SPOT, (4.75, DF.GAP_Y), DF.SNUG_IN, (3.90, -12.40), (TT_SPOT[0], AISLE), TT_SPOT]
TT_TO_ST = [TT_SPOT, (TT_SPOT[0], AISLE), (4.00, AISLE), (4.05, ST_SPOT[1]), ST_SPOT]
ST_TO_HOME = [ST_SPOT, (4.05, ST_SPOT[1]), (4.00, AISLE), CF.DOWN_STEP[-1]] + list(reversed(CF.DOWN_STEP[:-1])) + \
    [CF.MINGLE_HOME]
# Round marks (seconds into the round): when each visit is over (its bow taken).
END = {"couple": 76.0, "jay": 124.0, "snug": 226.0, "tt": RF.TABLE_VISITS["tt"][2], "st": RF.TABLE_VISITS["st"][2]}
START = {"tt": RF.TABLE_VISITS["tt"][1], "st": RF.TABLE_VISITS["st"][1]}   # (not there before: they are away)


# --- Little helpers -----------------------------------------------------------------------------
def _hold(m, t):
    f = m.f
    for k in (f.L, f.R):
        DF.hold_live(k, t)
    for k in (f.lean, f.pitch, f.yaw, f.twist):
        k.hold(t)


def _rest(m, t, dur=0.8):
    pose(m, t + dur, HR["L"].copy(), HR["R"].copy(), 3, 3, 0)
    return t + dur


def _fw(m):
    a = math.radians(m.yaw)
    return V((-math.sin(a), math.cos(a), 0.0))


def _rt(m):
    a = math.radians(m.yaw)
    return V((math.cos(a), math.sin(a), 0.0))


def _top(m, ven, inset=0.20, side=0.0, up=0.0):
    """A point on the table top, toward him (inset from the edge), side metres to his right."""
    tx, ty = ven["table"]
    d = V((m.x - tx, m.y - ty, 0.0))
    d.normalize()
    p = V((tx, ty, TOP + up)) + d * (0.34 - inset) + _rt(m) * side
    return p


def _who(ven, rng):
    return rng.choice(ven["who"])


def _blow_up(m, t, breaths=3):
    """A long balloon out of his pocket, blown up in breaths and twisted."""
    f = m.f
    pose(m, t + 0.8, R=P(0.12, 0.10, 1.00))
    m.scale("LBal", t, 0.05, t + 0.1, 0.05)
    m.prop("LBal", t + 0.9, ("hand", "L", np.zeros(3), DF.qx(-90.0)), 0)
    pose(m, t + 1.4, L=P(-0.02, 0.18, 1.50), R=P(0.04, 0.22, 1.48), pitch=-4)
    m.prop("LBal", t + 1.4, ("hand", "L", np.zeros(3), DF.qx(-90.0)), 6)
    step = 0.95 / breaths
    for k in range(breaths):
        tb = t + 1.8 + 1.4 * k
        m.scale("LBal", tb, 0.05 + step * k, tb + 1.0, 0.05 + step * (k + 1))
        f.lean.add(tb, 2).add(tb + 0.5, -6).add(tb + 1.0, 2)
        f.pitch.add(tb + 0.5, -10).add(tb + 1.2, -2)
    t1 = t + 1.8 + 1.4 * breaths
    pose(m, t1 + 0.4, L=P(-0.10, 0.36, 1.30), R=P(0.10, 0.36, 1.30), pitch=8)
    for k in range(4):
        pose(m, t1 + 0.8 + 0.6 * k, L=P(-0.08 + 0.03 * (k % 2), 0.36, 1.30), R=P(0.08 - 0.03 * (k % 2), 0.36, 1.32))
    t = t1 + 3.4
    m.scale("LBal", t - 0.4, 1.0, t, 0.001)
    m.prop("LBal", t + 0.05, ("hide",), 0)
    return t


# --- The tricks ------------------------------------------------------------------------------------
# Each: (m, t, ven, rng) -> end time, hands empty and at rest. TABLE: the ones
# done on a table top (not in the snug, where he stands between two tables).
def pluck_ball(m, t, ven, rng):
    """A ball found in the air by someone's head, vanished, and out of his own mouth."""
    f = m.f
    who = _who(ven, rng)
    m.look_at(t, who)
    d = V((who[0] - m.x, who[1] - m.y, 0.0))
    d.normalize()
    ear = V((m.x, m.y, F_Z + 1.42)) + d * 0.48
    f.R.add(t + 1.2, f.at_world(ear))
    f.lean.add(t + 1.2, 16)
    m.prop("MBall", t + 1.3, ("hand", "R", np.array((0, 0, CF.BALL_R)), Q_ID), 0)
    m.scale("MBall", t + 1.3, 0.001, t + 1.45, 1.0)
    pose(m, t + 2.4, R=P(0.16, 0.36, 1.32), lean=4, yaw=0)
    pose(m, t + 3.2, L=P(-0.03, 0.36, 1.30), R=P(0.05, 0.36, 1.30))
    m.prop("MBall", t + 3.4, ("hide",), 0)
    pose(m, t + 4.2, L=P(-0.28, 0.36, 1.38), R=HR["R"].copy())
    f.L.add(t + 5.2, P(-0.28, 0.36, 1.38))
    f.pitch.add(t + 4.4, 16).add(t + 5.2, 16)
    f.L.add(t + 5.8, HR["L"].copy())
    pose(m, t + 6.2, R=P(0.04, 0.13, 1.52), pitch=8)          # out of his own mouth
    m.prop("MBall", t + 6.3, ("hand", "R", np.array((0, 0, CF.BALL_R)), Q_ID), 0)
    m.scale("MBall", t + 6.3, 0.001, t + 6.45, 1.0)
    pose(m, t + 7.2, R=P(0.22, 0.40, 1.34), pitch=0)
    m.scale("MBall", t + 8.0, 1.0, t + 8.2, 0.001)
    m.prop("MBall", t + 8.25, ("hide",), 0)
    return _rest(m, t + 8.4)


def heart(m, t, ven, rng):
    """His heart thumping out of his chest at someone; taken out, offered, a kiss blown."""
    f = m.f
    who = _who(ven, rng)
    m.look_at(t, who)
    pose(m, t + 0.8, R=P(-0.06, 0.16, 1.30), pitch=-2)
    for k in range(7):
        pose(m, t + 1.1 + 0.36 * k, R=P(-0.06, 0.24 if k % 2 == 0 else 0.15, 1.30))
        f.lean.add(t + 1.1 + 0.36 * k, -3 if k % 2 == 0 else 2)
    t += 1.1 + 0.36 * 7
    pose(m, t + 0.6, L=P(-0.10, 0.20, 1.28), R=P(-0.02, 0.20, 1.28))       # cupped, taken out
    pose(m, t + 1.6, L=P(-0.06, 0.48, 1.32), R=P(0.06, 0.48, 1.32), lean=12)
    f.L.add(t + 2.8, P(-0.06, 0.48, 1.32))
    f.R.add(t + 2.8, P(0.06, 0.48, 1.32))
    pose(m, t + 3.4, L=HR["L"].copy(), R=P(0.04, 0.12, 1.52), lean=3)        # a kiss blown
    pose(m, t + 4.1, R=P(0.32, 0.50, 1.56), lean=6)
    return _rest(m, t + 4.6)


def piano(m, t, ven, rng):
    """The table played like a piano: scales, a run along the edge, big chords."""
    f = m.f
    m.look_at(t, ven["table"])
    f.yaw.add(t + 0.6, 0)
    a = lambda s: f.at_world(_top(m, ven, 0.06, s, 0.03))
    pose(m, t + 1.0, L=a(-0.14), R=a(0.14), lean=24, pitch=22)
    t += 1.0
    for k in range(10):                                  # scales: hands rippling
        s = 0.04 * (k % 5)
        tk = t + 0.25 * k
        f.L.add(tk, f.at_world(_top(m, ven, 0.06, -0.20 + s, 0.03 + 0.03 * (k % 2))))
        f.R.add(tk, f.at_world(_top(m, ven, 0.06, 0.08 + s, 0.03 + 0.03 * ((k + 1) % 2))))
    t += 2.5
    f.L.add(t + 0.4, f.at_world(_top(m, ven, 0.02, -0.25, 0.12)))
    for k in range(6):                                   # the run: right hand along the edge
        f.R.add(t + 0.2 + 0.2 * k, f.at_world(_top(m, ven, 0.04, 0.24 - 0.08 * k, 0.03)))
    f.twist.add(t + 0.6, -10).add(t + 1.4, 8)
    t += 1.6
    for k in range(2):                                   # chords: up, and down
        pose(m, t + 0.5, L=f.at_world(_top(m, ven, 0.06, -0.14, 0.30)),
             R=f.at_world(_top(m, ven, 0.06, 0.14, 0.30)), pitch=-6, twist=0)
        pose(m, t + 0.8, L=a(-0.14), R=a(0.14), pitch=26)
        f.L.add(t + 1.3, a(-0.14))
        f.R.add(t + 1.3, a(0.14))
        t += 1.3
    pose(m, t + 0.8, L=P(-0.34, 0.30, 1.56), R=P(0.34, 0.30, 1.56), lean=-4, pitch=-12)   # ta-da
    f.L.add(t + 1.8, P(-0.34, 0.30, 1.56))
    f.R.add(t + 1.8, P(0.34, 0.30, 1.56))
    return _rest(m, t + 1.8)


def cascade(m, t, ven, rng):
    """Three balls out of his pockets, a low cascade for them, a flash, gone."""
    f = m.f
    t = m.appear_balls(t)
    f.pitch.add(t, 10)
    t = CF.cascade(m, "ball", t + 0.2, 24, 0.30) + 0.3
    t = CF.flash(m, "ball", t + 0.3, T=0.85, b=0.2, pirouette=False) + 0.3
    t = CF.cascade(m, "ball", t + 0.2, 13, 0.30) + 0.3
    t = m.vanish_balls(t)
    f.pitch.add(t, 3)
    return _rest(m, t)


def fan(m, t, ven, rng):
    """A fan of cards shown round the table, sprung from hand to hand, gone with a snap."""
    f = m.f
    pose(m, t + 0.8, R=P(0.20, 0.38, 1.40))
    m.prop("Fan", t + 0.9, ("hand", "R", np.array((0.0, 0.0, 0.03)), Q_ID), 0)
    m.scale("Fan", t + 0.9, 0.001, t + 1.2, 1.0)
    f.yaw.add(t + 1.4, 32).add(t + 3.4, 32).add(t + 4.4, -32).add(t + 6.4, -32).add(t + 7.0, 0)
    f.R.add(t + 2.2, P(0.06, 0.44, 1.40)).add(t + 4.6, P(0.30, 0.40, 1.40))
    t += 7.4
    pose(m, t + 0.6, L=P(-0.18, 0.36, 1.26), R=P(0.18, 0.36, 1.32))
    m.prop("Fan", t + 0.8, ("hide",), 0)
    for i in range(8):
        ts = t + 0.8 + i * 0.12
        m.prop(f"Card{i}", ts, ("fly", "R", ts, "L", ts + 0.42, "card", 0), 0)
        m.prop(f"Card{i}", ts + 0.42, ("hand", "L", np.array((0.0, 0.0, 0.03 + 0.002 * i)), Q_ID), 0)
    t += 2.4
    f.L.add(t + 0.6, P(-0.20, 0.40, 1.40))
    for i in range(8):
        m.scale(f"Card{i}", t + 0.7, 1.0, t + 0.9, 0.001)
        m.prop(f"Card{i}", t + 0.95, ("hide",), 0)
    return _rest(m, t + 1.0)


def invisible_ball(m, t, ven, rng):
    """An invisible ball bounced, thrown to someone; it comes back hard, then
    up in the air, and down on his head."""
    f = m.f
    who = _who(ven, rng)
    for k in range(3):                                   # bounced
        pose(m, t + 0.4 + 0.6 * k, R=P(0.20, 0.36, 1.00), pitch=24)
        pose(m, t + 0.7 + 0.6 * k, R=P(0.20, 0.36, 1.18), pitch=18)
    t += 2.2
    m.look_at(t, who)
    pose(m, t + 0.8, R=P(0.30, -0.06, 1.46), lean=-4, pitch=0)        # wound up
    pose(m, t + 1.5, R=P(0.24, 0.52, 1.36), lean=12)                  # thrown
    pose(m, t + 2.2, L=P(-0.10, 0.40, 1.18), R=P(0.10, 0.40, 1.18), lean=6)     # waiting for it back
    f.L.add(t + 3.4, P(-0.10, 0.40, 1.18))
    f.R.add(t + 3.4, P(0.10, 0.40, 1.18))
    pose(m, t + 3.7, L=P(-0.08, 0.16, 1.10), R=P(0.08, 0.16, 1.10), lean=34, pitch=24)   # oof
    f.lean.add(t + 5.0, 30)
    t += 5.4
    pose(m, t + 0.8, L=P(-0.10, 0.30, 1.30), R=P(0.10, 0.30, 1.30), lean=3, pitch=4, yaw=0)
    pose(m, t + 1.3, L=P(-0.10, 0.34, 1.62), R=P(0.10, 0.34, 1.62), pitch=-30)        # up it goes
    f.pitch.add(t + 2.4, -36)
    pose(m, t + 2.8, L=P(-0.08, 0.04, 1.84), R=P(0.08, 0.04, 1.84), pitch=14)         # on his head
    squat(m, t + 2.8, 0.08, 0.25)
    stand_up(m, t + 3.2, 0.4)
    pose(m, t + 3.9, L=HR["L"].copy(), R=HR["R"].copy(), yaw=40, pitch=-6)           # off it bounces
    f.yaw.add(t + 4.8, 40)
    return _rest(m, t + 4.8)


def two_balls(m, t, ven, rng):
    """A ball plucked out of the air; closed in the hand and opened: two;
    the hands passed over each other: none."""
    f = m.f
    pose(m, t + 0.8, R=P(0.28, 0.26, 1.70), pitch=-12)
    m.prop("MBall", t + 0.9, ("hand", "R", np.array((0, 0, CF.BALL_R)), Q_ID), 0)
    m.scale("MBall", t + 0.9, 0.001, t + 1.05, 1.0)
    pose(m, t + 1.6, R=P(0.16, 0.38, 1.32), pitch=10)
    pose(m, t + 2.4, L=P(0.06, 0.40, 1.42))                  # a hand over it
    pose(m, t + 3.0, L=P(-0.20, 0.38, 1.30))
    m.prop("ZBall", t + 2.9, ("hand", "L", np.array((0, 0, CF.BALL_R)), Q_ID), 0)
    m.scale("ZBall", t + 2.9, 0.001, t + 3.05, 1.0)
    f.yaw.add(t + 3.6, 25).add(t + 4.6, -25).add(t + 5.4, 0)
    f.L.add(t + 5.4, P(-0.20, 0.38, 1.30))
    f.R.add(t + 5.4, P(0.16, 0.38, 1.32))
    pose(m, t + 6.0, L=P(0.02, 0.40, 1.36), R=P(-0.02, 0.38, 1.30))       # passed over each other
    pose(m, t + 6.6, L=P(-0.24, 0.38, 1.34), R=P(0.24, 0.38, 1.34))
    for n_ in ("MBall", "ZBall"):
        m.scale(n_, t + 6.0, 1.0, t + 6.2, 0.001)
        m.prop(n_, t + 6.25, ("hide",), 0)
    f.L.add(t + 7.6, P(-0.24, 0.38, 1.34))
    f.R.add(t + 7.6, P(0.24, 0.38, 1.34))
    f.pitch.add(t + 6.8, 2)
    return _rest(m, t + 7.6)


def magnet(m, t, ven, rng):
    """His hand stuck fast to the table top: tugged, pulled with the other
    hand, it comes free and he staggers back; it is poked again, gingerly."""
    f = m.f
    on = f.at_world(_top(m, ven, 0.10, 0.06, 0.02))
    pose(m, t + 1.0, R=on, lean=24, pitch=24)
    t += 1.2
    for k in range(3):                                    # stuck
        f.R.add(t + 0.5 * k, on)
        f.twist.add(t + 0.5 * k + 0.25, 10 if k % 2 == 0 else -10)
        f.lean.add(t + 0.5 * k + 0.25, 20 if k % 2 == 0 else 26)
    t += 1.5
    pose(m, t + 0.5, L=f.at_world(_top(m, ven, 0.06, 0.04, 0.14)), R=on, pitch=30, twist=0)   # both hands
    for k in range(4):
        f.lean.add(t + 0.8 + 0.4 * k, 18 if k % 2 == 0 else 24)
        f.R.add(t + 0.8 + 0.4 * k, on)
    t += 2.4
    pose(m, t + 0.35, L=P(-0.22, 0.24, 1.40), R=P(0.26, 0.24, 1.46), lean=-8, pitch=-8)     # free!
    f.lean.add(t + 0.7, -10).add(t + 1.0, 2)
    t += 1.0
    for k in range(4):                                   # the hand shaken out, blown on
        pose(m, t + 0.3 * k, R=P(0.24, 0.30, 1.26 + 0.06 * (k % 2)))
    pose(m, t + 1.6, R=P(0.06, 0.24, 1.48), lean=3, pitch=6)
    t += 2.2
    pose(m, t + 1.2, R=f.at_world(_top(m, ven, 0.04, 0.10, 0.04)), lean=24, pitch=26)       # a poke
    pose(m, t + 2.0, R=P(0.24, 0.30, 1.30), lean=4, pitch=10)
    f.yaw.add(t + 2.2, 0)
    return _rest(m, t + 2.4)


def card_rise(m, t, ven, rng):
    """A card out of nowhere, held flat between his palms; it rises up between
    his hands as they part, hangs in the air, and is gone."""
    f = m.f
    pose(m, t + 0.8, R=P(0.26, 0.28, 1.62), pitch=-10)
    m.prop("Card0", t + 0.9, ("hand", "R", np.array((0.0, 0.0, 0.03)), Q_ID), 0)
    m.scale("Card0", t + 0.9, 0.001, t + 1.05, 1.0)
    pose(m, t + 1.8, L=P(0.0, 0.38, 1.20), R=P(0.02, 0.38, 1.32), pitch=16)
    t += 2.0
    rise = V((0.0, 0.38, 1.25))
    path = CF.Keys().add(t, rise.copy()).add(t + 2.4, rise + V((0, 0, 0.24)))
    m.prop("Card0", t, ("local", path, Q_ID), 4)
    pose(m, t + 2.4, L=P(0.0, 0.38, 1.18), R=P(0.0, 0.38, 1.60), pitch=4)
    t += 2.6
    w = V((m.x, m.y, F_Z)) + _fw(m) * 0.38 + V((0, 0, 1.49))           # hanging there
    m.prop("Card0", t, ("spot", w.copy(), DF.qyaw(m.yaw)), 4)
    pose(m, t + 0.8, L=P(-0.16, 0.36, 1.49), R=P(0.16, 0.36, 1.49))
    pose(m, t + 1.8, L=P(-0.10, 0.36, 1.62), R=P(0.10, 0.36, 1.36))
    pose(m, t + 2.8, L=P(-0.10, 0.36, 1.36), R=P(0.10, 0.36, 1.62))
    pose(m, t + 3.6, R=P(0.03, 0.38, 1.47))
    m.prop("Card0", t + 3.7, ("hand", "R", np.array((0.0, 0.0, 0.03)), Q_ID), 4)
    pose(m, t + 4.3, R=P(0.24, 0.40, 1.40))
    m.scale("Card0", t + 4.4, 1.0, t + 4.6, 0.001)
    m.prop("Card0", t + 4.65, ("hide",), 0)
    pose(m, t + 5.0, L=P(-0.26, 0.36, 1.36), R=P(0.26, 0.36, 1.36))
    return _rest(m, t + 5.6)


def balloon_dog(m, t, ven, rng):
    """A balloon dog twisted for them, stood on their table, told to sit,
    patted; picked up, it pops: gone."""
    f = m.f
    t = _blow_up(m, t, 3)
    m.prop("BDog", t, ("hand", "R", np.array((0.0, -0.03, -0.20)), Q_ID), 0)
    m.scale("BDog", t, 0.001, t + 0.3, 0.62)
    pose(m, t + 0.6, R=P(0.20, 0.42, 1.42), pitch=-4)
    f.yaw.add(t + 1.2, 25).add(t + 2.0, -25).add(t + 2.6, 0)
    t += 2.8
    spot = _top(m, ven, 0.16, 0.0, 0.0)
    pose(m, t + 0.9, R=f.at_world(spot + V((0, 0, 0.20))), lean=24, pitch=24)
    m.prop("BDog", t + 1.0, ("spot", spot.copy(), DF.qyaw(m.yaw + 150.0)), 4)
    pose(m, t + 1.6, R=P(0.24, 0.40, 1.10), lean=6)                   # "sit"
    pose(m, t + 2.4, R=P(0.24, 0.34, 1.22))
    pose(m, t + 3.2, R=f.at_world(spot + V((0, 0, 0.32))), lean=20)   # a pat or two
    pose(m, t + 3.5, R=f.at_world(spot + V((0, 0, 0.27))))
    pose(m, t + 3.8, R=f.at_world(spot + V((0, 0, 0.32))))
    pose(m, t + 4.1, R=f.at_world(spot + V((0, 0, 0.27))))
    pose(m, t + 4.8, R=f.at_world(spot + V((0, 0, 0.22))))
    m.prop("BDog", t + 4.9, ("hand", "R", np.array((0.0, -0.03, -0.20)), Q_ID), 6)
    pose(m, t + 5.8, R=P(0.10, 0.38, 1.30), L=P(-0.08, 0.38, 1.32), lean=4)     # a squeeze: pop
    m.scale("BDog", t + 6.0, 0.62, t + 6.08, 0.001)
    m.prop("BDog", t + 6.12, ("hide",), 0)
    pose(m, t + 6.3, L=P(-0.24, 0.30, 1.56), R=P(0.24, 0.30, 1.56), lean=-10, pitch=-10)
    pose(m, t + 7.4, L=P(-0.24, 0.30, 1.30), R=P(0.24, 0.30, 1.30), lean=3, pitch=12)     # a sad look at nothing
    f.L.add(t + 8.4, P(-0.24, 0.30, 1.30))
    f.R.add(t + 8.4, P(0.24, 0.30, 1.30))
    return _rest(m, t + 8.4)


def windup(m, t, ven, rng):
    """Frozen like a statue; he runs down; a key in his back turned; back to
    life a jerk at a time, a robot, until he's himself again."""
    f = m.f
    pose(m, t + 1.1, L=P(-0.22, 0.12, 1.08), R=P(0.42, 0.30, 1.56), lean=4, pitch=-4, yaw=15)
    for k in (f.L, f.R, f.lean, f.pitch, f.yaw):
        k.hold(t + 3.2)
    t += 3.2
    pose(m, t + 2.6, L=P(-0.20, 0.10, 0.92), R=P(0.28, 0.26, 1.10), lean=12, pitch=30, yaw=0)   # running down
    squat(m, t, 0.10, 2.6)
    for k in (f.L, f.R, f.lean, f.pitch):
        k.hold(t + 3.2)
    t += 3.2
    pose(m, t + 0.8, L=P(-0.10, -0.16, 1.18))                         # the key in his back
    for k in range(3):
        pose(m, t + 1.2 + 0.6 * k, L=P(-0.04, -0.17, 1.24))
        pose(m, t + 1.5 + 0.6 * k, L=P(-0.10, -0.16, 1.14))
        f.lean.add(t + 1.2 + 0.6 * k, 8).add(t + 1.5 + 0.6 * k, 11)
    t += 3.0
    stand_up(m, t, 0.3)
    steps = [dict(L=P(-0.17, 0.06, 0.87), pitch=10), dict(R=P(0.30, 0.30, 1.30), pitch=0),
             dict(R=P(0.30, 0.30, 1.42), L=P(-0.24, 0.20, 1.08)), dict(L=P(-0.30, 0.30, 1.28)),
             dict(L=P(-0.30, 0.30, 1.42), yaw=40), dict(yaw=-40), dict(L=P(-0.30, 0.30, 1.24), R=P(0.30, 0.30, 1.24), yaw=0),
             dict(L=P(-0.30, 0.30, 1.08), R=P(0.30, 0.30, 1.08))]
    for k, st in enumerate(steps):                       # a jerk at a time
        tk = t + 0.6 * k
        for kk in (f.L, f.R, f.lean, f.pitch, f.yaw):
            DF.hold_live(kk, tk)
        pose(m, tk + (0.5 if k == 0 else 0.3), **st)
    t += 0.6 * len(steps)
    for kk in (f.L, f.R, f.lean, f.pitch, f.yaw):
        kk.hold(t)
    return _rest(m, t, 1.0)


def sip(m, t, ven, rng):
    """A drink off their table (one nobody can see), sipped: far too strong.
    Coughing, a thump on the chest, put back with a wagging finger."""
    f = m.f
    m.look_at(t, ven["table"])
    f.pitch.add(t + 0.6, 24)
    glass = f.at_world(_top(m, ven, 0.12, 0.10, 0.06))
    pose(m, t + 1.4, R=glass, lean=22)
    pose(m, t + 2.4, R=P(0.06, 0.20, 1.46), lean=3, pitch=0, yaw=0)
    pose(m, t + 3.0, R=P(0.05, 0.14, 1.52), pitch=-22)                 # a sip
    f.R.add(t + 4.0, P(0.05, 0.14, 1.52))
    f.pitch.add(t + 4.0, -24)
    pose(m, t + 4.7, R=P(0.28, 0.40, 1.30), pitch=6)                   # !!
    for k in range(3):                                   # cough, thump
        pose(m, t + 4.8 + 0.5 * k, L=P(-0.06, 0.20, 1.32), lean=14)
        pose(m, t + 5.05 + 0.5 * k, L=P(-0.06, 0.14, 1.30), lean=2)
    f.yaw.add(t + 6.6, 12).add(t + 6.9, -12).add(t + 7.2, 12).add(t + 7.5, 0)
    pose(m, t + 8.4, R=glass, L=HR["L"].copy(), lean=22, pitch=22)      # back on the table
    pose(m, t + 9.2, R=P(0.20, 0.36, 1.50), lean=4, pitch=4)
    for k in range(3):                                   # tut tut
        pose(m, t + 9.5 + 0.3 * k, R=P(0.16 + 0.06 * (k % 2), 0.36, 1.50))
    pose(m, t + 10.8, R=P(0.10, 0.30, 1.40))
    for k in range(3):                                   # fanning his mouth
        pose(m, t + 11.0 + 0.25 * k, R=P(0.10, 0.18 + 0.06 * (k % 2), 1.52))
    return _rest(m, t + 11.8)


def balloon_sword(m, t, ven, rng):
    """A long blue balloon twisted into a sword, a salute and a flourish,
    then swallowed, all of it, a gulp."""
    f = m.f
    t = _blow_up(m, t, 3)
    m.prop("BSword", t, ("hand", "R", np.zeros(3), DF.qx(-70.0)), 0)
    m.scale("BSword", t, 0.001, t + 0.3, 1.0)
    pose(m, t + 0.8, R=P(0.10, 0.22, 1.30), L=P(-0.30, 0.0, 1.50), lean=4)        # salute
    pose(m, t + 1.6, R=P(0.22, 0.42, 1.24))
    pose(m, t + 2.2, R=P(0.30, 0.50, 1.36), lean=10)                              # flourishes
    pose(m, t + 2.6, R=P(0.10, 0.44, 1.24))
    pose(m, t + 3.0, R=P(0.30, 0.50, 1.40))
    pose(m, t + 3.6, R=P(0.20, 0.30, 1.24), L=HR["L"].copy(), lean=3)
    t += 3.8
    pose(m, t + 1.0, R=P(0.04, 0.13, 2.34), pitch=-34)                 # blade down over his open mouth
    m.prop("BSword", t + 1.0, ("hand", "R", np.zeros(3), DF.qx(180.0)), 6)
    t += 1.6
    n = 6
    for k in range(1, n + 1):                            # down it goes
        s = 1.0 - 0.85 * k / n
        pose(m, t + 0.6 * k, R=P(0.04, 0.13, 1.52 + 0.82 * s))
        m.scale("BSword", t + 0.6 * (k - 1), 1.0 - 0.85 * (k - 1) / n, t + 0.6 * k, s)
    t += 0.6 * n
    m.scale("BSword", t, 0.15, t + 0.15, 0.001)
    m.prop("BSword", t + 0.2, ("hide",), 0)
    pose(m, t + 0.6, R=P(0.10, 0.16, 1.20), L=P(-0.06, 0.16, 1.16), pitch=10)       # gulp: tummy patted
    f.pitch.add(t + 1.0, 2).add(t + 1.4, 10)
    pose(m, t + 1.6, R=P(0.10, 0.18, 1.14))
    pose(m, t + 2.0, R=P(0.10, 0.16, 1.20))
    return _rest(m, t + 2.6)


def box(m, t, ven, rng):
    """Trapped in an invisible box: its walls felt, the lid pressing him down;
    a handle found, a door opened, out; a brow wiped."""
    f = m.f
    for k, (x, z) in enumerate(((0.0, 1.30), (-0.16, 1.48), (0.16, 1.12))):     # the front
        pose(m, t + 0.6 + 0.7 * k, L=P(x - 0.14, 0.36, z), R=P(x + 0.14, 0.36, z + 0.04), pitch=4)
    t += 2.8
    pose(m, t + 0.6, L=P(-0.10, 0.30, 1.30), R=P(0.38, 0.12, 1.30), yaw=40)        # the right wall
    pose(m, t + 1.2, R=P(0.38, 0.12, 1.56))
    pose(m, t + 1.9, L=P(-0.38, 0.12, 1.30), R=P(0.10, 0.30, 1.30), yaw=-40)       # the left
    pose(m, t + 2.5, L=P(-0.38, 0.12, 1.56))
    t += 2.8
    pose(m, t + 0.6, L=P(-0.14, 0.10, 1.92), R=P(0.14, 0.10, 1.92), yaw=0, pitch=-20)    # the lid
    squat(m, t + 0.6, 0.06, 0.6)
    squat(m, t + 1.4, 0.14, 0.8)
    pose(m, t + 2.2, L=P(-0.14, 0.10, 1.80), R=P(0.14, 0.10, 1.80))
    f.yaw.add(t + 2.6, 30).add(t + 3.0, -30).add(t + 3.4, 0)                     # panic
    t += 3.6
    stand_up(m, t, 0.6)
    pose(m, t + 0.8, L=HR["L"].copy(), R=P(0.20, 0.36, 1.10), pitch=10)          # a handle
    pose(m, t + 1.3, R=P(0.24, 0.34, 1.08))
    pose(m, t + 2.2, R=P(0.46, 0.16, 1.10), lean=6, pitch=0)                      # the door swung open
    pose(m, t + 3.0, R=P(0.10, 0.10, 1.66), lean=3)                               # phew
    pose(m, t + 3.5, R=P(-0.04, 0.10, 1.66))
    return _rest(m, t + 3.8)


def crystal(m, t, ven, rng):
    """A crystal ball out of nowhere rolls round his palms, then hangs over
    the table on its own while his hands slide round it; gone."""
    f = m.f
    pose(m, t + 0.8, R=P(0.30, 0.26, 1.72), pitch=-10)
    m.prop("Crystal", t + 1.4, ("hand", "R", np.array((0, 0, 0.068)), Q_ID), 0)
    m.scale("Crystal", t + 1.4, 0.001, t + 1.8, 1.0)
    pose(m, t + 1.4, R=P(0.20, 0.40, 1.36), pitch=4)
    t += 1.9
    pose(m, t + 0.6, P(-0.06, 0.34, 1.20), P(0.06, 0.34, 1.20), 6, 18)
    path = CF.Keys()
    t1 = t + 0.6
    for k in range(13):
        a = 2 * math.pi * k / 8
        path.add(t1 + 0.45 * k, P(0.07 * math.cos(a), 0.36 + 0.03 * math.sin(a), 1.27 + 0.03 * math.sin(2 * a)))
        pose(m, t1 + 0.45 * k, P(-0.06 + 0.03 * math.cos(a), 0.34, 1.20 + 0.02 * math.sin(a)),
             P(0.06 + 0.03 * math.cos(a), 0.34, 1.20 - 0.02 * math.sin(a)))
    m.prop("Crystal", t1, ("local", path, Q_ID), 6)
    t = t1 + 0.45 * 12
    fw, rt = _fw(m), _rt(m)
    ball = V((m.x, m.y, F_Z + 1.27)) + fw * 0.36
    m.prop("Crystal", t, ("spot", ball.copy(), Q_ID), 0)
    for k in range(9):
        a = 2 * math.pi * k / 8
        off = rt * (0.075 * math.cos(a)) + V((0, 0, 0.075 * math.sin(a)))
        f.L.add(t + 0.6 + 0.6 * k, f.at_world(ball + off - fw * 0.02))
        f.R.add(t + 0.6 + 0.6 * k, f.at_world(ball - off - fw * 0.02))
    t += 5.4
    f.L.add(t + 0.6, f.at_world(ball + rt * 0.09))
    f.R.add(t + 0.6, f.at_world(ball - rt * 0.09))
    f.pitch.add(t + 0.6, 14)
    pose(m, t + 1.4, P(-0.20, 0.30, 1.20), P(0.18, 0.38, 1.30))
    m.prop("Crystal", t + 1.4, ("hand", "R", np.array((0, 0, 0.068)), Q_ID), 6)
    pose(m, t + 1.9, R=P(0.22, 0.38, 1.40))
    m.scale("Crystal", t + 1.9, 1.0, t + 2.15, 0.001)
    m.prop("Crystal", t + 2.2, ("hide",), 0)
    pose(m, t + 2.7, P(-0.30, 0.34, 1.36), P(0.30, 0.34, 1.36))
    return _rest(m, t + 3.0)


def string(m, t, ven, rng):
    """An invisible string through his head, ear to ear: pulled one way and
    the other (his head goes with it), sawed, snipped."""
    f = m.f
    pose(m, t + 0.8, L=P(-0.11, 0.02, 1.60), R=P(0.11, 0.02, 1.60), pitch=2)
    t += 1.0
    for k in range(4):                                   # pulled: the head follows
        sgn = 1 if k % 2 == 0 else -1
        pose(m, t + 0.9, L=P(-0.11 + 0.24 * sgn, 0.02, 1.60), R=P(0.11 + 0.24 * sgn, 0.02, 1.60), yaw=-30 * sgn)
        f.yaw.add(t + 1.4, -30 * sgn)
        t += 1.4
    pose(m, t + 0.6, L=P(-0.11, 0.02, 1.60), R=P(0.11, 0.02, 1.60), yaw=0)
    for k in range(6):                                   # sawing
        d = 0.06 if k % 2 == 0 else -0.06
        pose(m, t + 0.8 + 0.25 * k, L=P(-0.11 + d, 0.02, 1.60), R=P(0.11 + d, 0.02, 1.60))
    t += 2.4
    pose(m, t + 0.5, L=P(-0.30, 0.10, 1.60), R=P(0.04, 0.24, 1.62))              # snip
    pose(m, t + 0.9, R=P(0.06, 0.24, 1.60))
    pose(m, t + 1.4, L=P(-0.30, 0.10, 1.20), pitch=10)                           # the end falls
    return _rest(m, t + 1.8)


TRICKS = {fn.__name__: fn for fn in (pluck_ball, heart, piano, cascade, fan, invisible_ball, two_balls, magnet,
                                     card_rise, balloon_dog, windup, sip, balloon_sword, box, crystal, string)}
TABLE = ("piano", "magnet", "balloon_dog", "sip")
# Which tricks where, round by round (no table sees one twice in a loop; none
# is done twice in a round).
VISITS = (
    {"couple": ("balloon_dog", "two_balls"), "jay": ("piano", "cascade"),
     "snug": ("fan", "invisible_ball", "heart"), "tt": ("magnet", "card_rise"), "st": ("windup", "pluck_ball")},
    {"couple": ("balloon_sword", "string"), "jay": ("box", "heart"),
     "snug": ("crystal", "cascade", "two_balls"), "tt": ("sip", "fan"), "st": ("piano", "invisible_ball")},
    {"couple": ("crystal", "magnet"), "jay": ("string", "two_balls"),
     "snug": ("balloon_sword", "windup", "pluck_ball"), "tt": ("box", "invisible_ball"), "st": ("cascade", "heart")},
    {"couple": ("sip", "windup"), "jay": ("balloon_dog", "pluck_ball"),
     "snug": ("box", "string", "card_rise"), "tt": ("crystal", "two_balls"), "st": ("magnet", "fan")},
)
DUR = {}                                                # a trick's length (measured once, below)


def _check_visits():
    for n, r in enumerate(VISITS):
        flat = [x for v in r.values() for x in v]
        if len(flat) != len(set(flat)):
            raise RuntimeError(f"tables: round {n} repeats a trick")
        if any(x in TABLE for x in r["snug"]):
            raise RuntimeError(f"tables: round {n} has a table-top trick in the snug")
    for ven in VENUE:
        seen = [x for r in VISITS for x in r[ven]]
        if len(seen) != len(set(seen)):
            raise RuntimeError(f"tables: {ven} sees a trick twice")


def _measure():
    """Each trick's length (they don't depend on where or when)."""
    for name, fn in TRICKS.items():
        m = CF.Mime(DF.LOOP, (C_SPOT[0], C_SPOT[1], 90.0))
        DUR[name] = fn(m, 10.0, VENUE["couple"], random.Random(0)) - 10.0


# --- A visit ------------------------------------------------------------------------------------------
def visit(m, t, venue, n, t_end):
    """At venue: a chat, the round's tricks, a bow, done by t_end."""
    ven = VENUE[venue]
    f = m.f
    rng = random.Random(f"table-{venue}-{n}")
    t0 = t
    if venue == "snug":
        t = m.turn(t, -90.0)
    else:
        t = m.face(t, ven["table"])
    tricks = VISITS[n % len(VISITS)][venue]
    need = sum(DUR[k] + 1.0 for k in tricks) + 5.0
    room = t_end - t - need
    if room < 3.0:
        legs = [(round(a - n * CF.CYCLE, 1), round(b - n * CF.CYCLE, 1), w) for a, b, w in m.legs if w.startswith(f"m{n}_")]
        raise RuntimeError(f"tables: {venue} round {n}: {room:.1f}s short (there at {t - n * CF.CYCLE:.1f}s; {legs})")
    gaps = len(tricks) + 1
    chat = [room * (0.45 if venue == "snug" else 0.6)] + [room * (0.55 if venue == "snug" else 0.4) / (gaps - 1)] * \
        (gaps - 1)
    for k, name in enumerate(tricks):
        if chat[k] >= 4.0:
            t = CF.mime_chat(m, t, chat[k], ven["who"], random.Random(f"chat-{venue}-{n}-{k}"))
        else:
            m.stay(t + chat[k])
            t += chat[k]
        _hold(m, t)
        t = TRICKS[name](m, t, ven, rng) + 1.0
        m.stay(t)
    t_bow = t_end - 4.8
    if t_bow - t >= 5.0:
        t = CF.mime_chat(m, t, t_bow - t - 1.2, ven["who"], random.Random(f"chat-{venue}-{n}-end"))
    _hold(m, t)
    t = _rest(m, t, 0.8)
    m.stay(t_bow)
    if venue == "snug":
        f.yaw.add(t_bow, 0)
    t = m.bow(t_bow, 30, venue)
    f.yaw.add(t, 0)
    m.audience.append((t0, t, venue, None))
    m.acts.append((t0, t, f"tables {venue}", venue))
    return t


def mingle_round(m, c0, t, n, cr, rng, t_end=None):
    """One round of the room from the front of the stage, back by c0 + CYCLE."""
    t_end = c0 + CF.CYCLE - 1.6 if t_end is None else t_end
    t = CF.home_bits(m, t, max(t, c0 + 14.0), rng)
    t = m.leg(t, [(m.x, m.y)] + HOME_TO_C[1:], f"m{n}_couple")
    t = visit(m, t, "couple", n, c0 + END["couple"])
    t = m.leg(t, [(m.x, m.y)] + C_TO_J[1:], f"m{n}_jay")
    t = visit(m, t, "jay", n, c0 + END["jay"])
    t = m.leg(t, [(m.x, m.y)] + J_TO_SNUG[1:], f"m{n}_snug", juggle=True)
    t = visit(m, t, "snug", n, c0 + END["snug"])
    t = m.leg(t, [(m.x, m.y)] + SNUG_TO_TT[1:], f"m{n}_tt")
    t = visit(m, t, "tt", n, c0 + END["tt"])
    t = m.leg(t, [(m.x, m.y)] + TT_TO_ST[1:], f"m{n}_st")
    t = visit(m, t, "st", n, c0 + END["st"])
    t = m.leg(t, [(m.x, m.y)] + ST_TO_HOME[1:], f"m{n}_home", juggle=True)
    t = m.turn(t, CF.FIN_FACE)
    t = CF.home_bits(m, t, t_end, rng)
    m.overrun = max(m.overrun, t - t_end)
    return t


_check_visits()
_measure()
