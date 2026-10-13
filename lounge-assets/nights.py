# The mime's finale, a different big show every night of the week (Jay: "seven
# different big shows from the mime - one each night ... dig deep on what
# routines can be - the length was good"). Every night keeps the finale's frame
# (cafe_figures.finale): the lights down, the spotlight, seven numbers with
# their bows on the regulars' marks (rovers_figures.FINALE_BOWS), the sixth the
# gift to the café lady (each night made a different way, then gift_walk), the
# ovation and the lights up. Friday is the first finale he ever played
# (cafe_figures); the others are here:
#   mon  strings: the marionette, the diabolo, the crystal ball, trick roping,
#        the dancing cane, the cane that blooms, fire poi in the dark
#   tue  magic: levitation, the floating table, cards into the crowd, the
#        linking rings, the torn and restored paper, a paper cone of flowers,
#        the doves
#   wed  jugglers: the runaway spotlight, cigar boxes, five balls, devil sticks,
#        a chair balanced on his chin, balls into flowers, the spinning plates
#   thu  clown: the wind-up toy, knife throwing at balloons, the yo-yo, balloon
#        animals, walking into the wind, flowers out of a flame, the snowstorm
#   sat  lights: the invisible ladder, juggling in the dark with glowing balls
#        and clubs, the umbrella in the rain, the ribbon, the tug of war,
#        flowers out of his hat, the upside-down painting
#   sun  dance: the robot, the hat and cane, the butterfly, the hoops, the
#        invisible dog, the butterfly's flowers, the sparklers
# Each night's kit lives in his steamer trunk at the back of the stage
# (rovers_figures.TRUNK): out of it for a number, back in after.
import math
import random
import numpy as np
import bpy
import bmesh
from mathutils import Vector, Matrix
import rovers_figures as RF
import dinner_figures as DF
import cafe_figures as CF
from rovers_figures import Keys, heading

V = Vector
FPS = CF.FPS
G = CF.G
HR, CARRY, OTHER = CF.HR, CF.CARRY, CF.OTHER
Q_ID = CF.Q_ID
STAND = RF.STAND_FEET


def P(x, y, z):
    return V((x, y, z))


def floor_z(x, y):
    return CF.floor_z(x, y)


# --- Kit: bones and meshes -----------------------------------------------------------
KIT = []                                           # every new prop bone, in order
MESHES = []                                        # fn(P) building their meshes


def kit(*names):
    for n in names:
        if n not in KIT:
            KIT.append(n)


def mesh(fn):
    MESHES.append(fn)
    return fn


def _q_to(d):
    """(n, 4) wxyz quaternions turning +z onto the directions d (n, 3)."""
    d = d / np.maximum(1e-9, np.linalg.norm(d, axis=1, keepdims=True))
    z = np.array((0.0, 0.0, 1.0))
    axis = np.cross(np.tile(z, (len(d), 1)), d)
    w = 1.0 + d[:, 2]
    Q = np.concatenate([w[:, None], axis], 1)
    bad = w < 1e-6                                 # (straight down)
    Q[bad] = (0.0, 1.0, 0.0, 0.0)
    return Q / np.linalg.norm(Q, axis=1, keepdims=True)


def _qaxis(axis, deg):
    """(n, 4) rotations about a fixed axis by angles deg (n,)."""
    a = np.radians(np.asarray(deg, float)) / 2
    ax = np.asarray(axis, float) / np.linalg.norm(axis)
    return np.concatenate([np.cos(a)[:, None], np.sin(a)[:, None] * ax], 1)


def _palm_at(C, side, tt):
    """His palm at fractional times tt (s)."""
    fi = tt * FPS
    i0 = np.clip(np.floor(fi).astype(int), 0, DF.N)
    i1 = np.clip(i0 + 1, 0, DF.N)
    u = np.clip(fi - i0, 0.0, 1.0)[:, None]
    p = C["palm"][side]
    return p[i0] * (1 - u) + p[i1] * u


# --- Moves -----------------------------------------------------------------------------
def pose(m, t, L=None, R=None, lean=None, pitch=None, yaw=None, twist=None):
    f = m.f
    if L is not None:
        f.L.add(t, L if callable(L) else V(L))
    if R is not None:
        f.R.add(t, R if callable(R) else V(R))
    if lean is not None:
        f.lean.add(t, lean)
    if pitch is not None:
        f.pitch.add(t, pitch)
    if yaw is not None:
        f.yaw.add(t, yaw)
    if twist is not None:
        f.twist.add(t, twist)


def centre(m, t, face=None):
    t = CF._step_to(m, t, CF.FIN_SPOT)
    return turn_to(m, t, CF.FIN_FACE if face is None else face)


def ready(m, t, dur=0.8):
    """Hands down at his sides, standing tall."""
    pose(m, t + dur, HR["L"], HR["R"], 3, 3, 0)
    return t + dur


def finish(m, t, t_bow, name, deep=40, hat=True):
    """To the front, then his bow on the mark."""
    t = centre(m, t)
    t = CF._land(m, t, t_bow, name)
    t = m.bow(t, deep, "pub", hat=hat)
    m.acts.append((m.act_t0, t, name, "pub"))
    return t


def begin(m, t):
    m.act_t0 = t
    m.stay(t)
    return t


def turn_to(m, t, face):
    """A turn, slower the further round."""
    d = abs(((face - m.yaw) + 180.0) % 360.0 - 180.0)
    return m.turn(t, face, 0.4 + d / 180.0 * 0.9) if d > 1.0 else t


def to_trunk(m, t):
    tr = RF.TRUNK
    t = CF._step_to(m, t, RF.TRUNK_AT)
    return turn_to(m, t, heading(RF.TRUNK_AT, tr))


def trunk_point(dx=0.0, dz=0.05):
    return V((RF.TRUNK[0] + dx, RF.TRUNK[1] - 0.08, RF.TRUNK_TOP + dz))


def take(m, t, side, names, state=None, dx=0.0, dur=1.0):
    """A hand into the trunk; names (one or more) come up out of it in the hand."""
    f = m.f
    keys = f.L if side == "L" else f.R
    DF.hold_live(keys, t)
    keys.add(t + dur, f.at_world(trunk_point(dx)))
    f.lean.hold(t).add(t + dur, 32)
    f.pitch.hold(t).add(t + dur, 30)
    for n in ([names] if isinstance(names, str) else names):
        st = state(n) if callable(state) else (state or ("hand", side, np.zeros(3), Q_ID))
        m.prop(n, t + dur, st, 0)
        m.scale(n, t + dur, 0.001, t + dur + 0.35, 1.0)
    keys.add(t + dur + 0.9, CARRY[side].copy())
    f.lean.add(t + dur + 0.9, 3)
    f.pitch.add(t + dur + 0.9, 3)
    m.hold[side] = "kit"
    return t + dur + 1.0


def stow(m, t, side, names, dx=0.0, dur=1.0):
    """Into the trunk: gone."""
    f = m.f
    keys = f.L if side == "L" else f.R
    DF.hold_live(keys, t)
    keys.add(t + dur, f.at_world(trunk_point(dx)))
    f.lean.hold(t).add(t + dur, 32)
    f.pitch.hold(t).add(t + dur, 30)
    for n in ([names] if isinstance(names, str) else names):
        m.scale(n, t + dur - 0.1, 1.0, t + dur + 0.2, 0.001)
        m.prop(n, t + dur + 0.25, ("hide",), 0)
    keys.add(t + dur + 0.9, HR[side].copy())
    f.lean.add(t + dur + 0.9, 3)
    f.pitch.add(t + dur + 0.9, 3)
    m.hold[side] = None
    return t + dur + 1.0


def produce(m, t, name, side="R", up=P(0.30, 0.26, 1.72), at=P(0.20, 0.40, 1.36), off=(0, 0, 0.02), q=Q_ID):
    """Out of thin air into his hand (reached up, brought down)."""
    f = m.f
    keys = f.L if side == "L" else f.R
    keys.add(t + 0.8, up).add(t + 1.4, at)
    m.prop(name, t + 1.4, ("hand", side, np.array(off, float), q), 0)
    m.scale(name, t + 1.4, 0.001, t + 1.8, 1.0)
    return t + 1.9


def vanish(m, t, name, side="R"):
    """Gone from his hand (a flick, empty palms)."""
    f = m.f
    keys = f.L if side == "L" else f.R
    sx = -1 if side == "L" else 1
    keys.add(t + 0.5, P(sx * 0.22, 0.38, 1.40))
    m.scale(name, t + 0.5, 1.0, t + 0.75, 0.001)
    m.prop(name, t + 0.8, ("hide",), 0)
    pose(m, t + 1.3, P(-0.30, 0.34, 1.36), P(0.30, 0.34, 1.36))
    return t + 1.6


def hop(m, t, up=0.18, dur=0.7):
    f = m.f
    z = floor_z(m.x, m.y)
    f.zk.add(t, z).add(t + dur / 2, z + up).add(t + dur, z)
    for keys, (x, y, zz) in ((f.fL, STAND[0]), (f.fR, STAND[1])):
        keys.add(t, V((x, y, zz))).add(t + dur * 0.5, V((x, y + 0.05, zz + 0.06))).add(t + dur, V((x, y, zz)))
    return t + dur


def squat(m, t, depth, dur=0.6):
    """Knees bent by depth (feet stay put)."""
    f = m.f
    z = floor_z(m.x, m.y)
    for k in (f.zk, f.fL, f.fR):
        k.hold(t)
    f.zk.add(t + dur, z - depth)
    for keys, (x, y, zz) in ((f.fL, STAND[0]), (f.fR, STAND[1])):
        keys.add(t + dur, V((x, y + 0.6 * depth, zz + depth)))
    return t + dur


def stand_up(m, t, dur=0.6):
    return squat(m, t, 0.0, dur)


def lights(m, t, dur, black=None, spot=None):
    """The room darker (black 0..1) and/or the spot on him dimmer (spot 0..1)."""
    if black is not None:
        m.black.add(t, m.black[-1][1] if len(m.black) else 0.0).add(t + dur, black)
    if spot is not None:
        m.spot.add(t, m.spot[-1][1] if len(m.spot) else 1.0).add(t + dur, spot)


# =====================================================================================
# MONDAY: strings
# =====================================================================================
def mon_marionette(m, t, t_bow):
    """Opener: a puppet hanging on its strings in the light. The strings take
    him up limb by limb, he jigs on them, a knee, a kick, a little hop; then
    they are cut and he drops in a heap. He picks himself up, glares up at
    the flies, snips the last string, dusts himself off."""
    f = m.f
    t = begin(m, t)
    z0 = floor_z(m.x, m.y)
    sag = 0.07
    f.zk.add(t, z0).add(t + 1.2, z0 - sag)
    for keys, (x, y, zz) in ((f.fL, STAND[0]), (f.fR, STAND[1])):
        keys.add(t, V((x, y, zz))).add(t + 1.2, V((x, y + 0.04, zz + sag)))
    pose(m, t + 1.2, P(-0.16, 0.10, 0.80), P(0.16, 0.10, 0.80), 28, 36, 0)
    t += 1.8
    # Up, limb by limb (a jerk, then a sag on the string).
    for side in ("R", "L"):
        sx = 1 if side == "R" else -1
        keys = f.R if side == "R" else f.L
        keys.add(t + 0.45, P(sx * 0.28, 0.18, 1.62)).add(t + 0.9, P(sx * 0.30, 0.16, 1.54))
        keys.add(t + 1.5, P(sx * 0.24, 0.14, 1.12))
        f.yaw.add(t + 0.45, sx * 12).add(t + 1.4, 0)
        t += 1.5
    f.zk.add(t + 0.5, z0)
    for keys, (x, y, zz) in ((f.fL, STAND[0]), (f.fR, STAND[1])):
        keys.add(t + 0.5, V((x, y, zz)))
    pose(m, t + 0.5, lean=4, pitch=-6)
    t += 0.8
    # The jig: knees and arms on the strings, side to side.
    for q in range(3):
        side = "L" if q % 2 == 0 else "R"
        sx = -1 if side == "L" else 1
        foot = f.fL if side == "L" else f.fR
        arm = f.L if side == "L" else f.R
        oth = f.R if side == "L" else f.L
        foot.add(t + 0.15, V(STAND[0] if side == "L" else STAND[1]))
        foot.add(t + 0.5, P(sx * 0.10, 0.20, 0.42)).add(t + 0.95, V(STAND[0] if side == "L" else STAND[1]))
        arm.add(t + 0.5, P(sx * 0.32, 0.16, 1.58)).add(t + 0.95, P(sx * 0.22, 0.14, 1.12))
        oth.add(t + 0.5, P(-sx * 0.20, 0.16, 1.02))
        f.yaw.add(t + 0.5, -sx * 14)
        f.lean.add(t + 0.5, 6 + 3 * (q % 2))
        t += 1.0
    t = hop(m, t + 0.1, 0.16, 0.8)
    pose(m, t, yaw=0)
    # Cut: he drops in a heap.
    f.zk.add(t + 0.2, z0).add(t + 0.75, z0 - 0.46)
    for keys, (x, y, zz) in ((f.fL, STAND[0]), (f.fR, STAND[1])):
        keys.add(t + 0.2, V((x, y, zz))).add(t + 0.75, V((x * 1.4, y + 0.30, zz + 0.46)))
    pose(m, t + 0.75, P(-0.24, 0.30, 0.66), P(0.24, 0.30, 0.66), 52, 44, 0)
    t += 1.9
    # Up again, glaring at the flies, a snip of two fingers, dusting off.
    f.zk.add(t + 1.0, z0)
    for keys, (x, y, zz) in ((f.fL, STAND[0]), (f.fR, STAND[1])):
        keys.add(t + 1.0, V((x, y, zz)))
    pose(m, t + 1.0, P(-0.14, 0.18, 1.02), P(0.12, 0.26, 1.62), 2, -32, 0)
    pose(m, t + 1.6, R=P(0.10, 0.22, 1.94))
    for q in range(2):
        pose(m, t + 1.9 + q * 0.35, R=P(0.13, 0.22, 1.96))
        pose(m, t + 2.05 + q * 0.35, R=P(0.08, 0.22, 1.93))
    pose(m, t + 3.0, P(-0.10, 0.22, 1.16), P(0.10, 0.22, 1.30), 8, 18)
    pose(m, t + 3.3, P(0.02, 0.20, 1.06), P(0.06, 0.22, 1.20))
    t = ready(m, t + 3.4)
    return finish(m, t, t_bow, "marionette", 30)


# --- The diabolo -----------------------------------------------------------------------
STICK_L = 0.32
STRING = 1.10
Q_STICK = {"L": DF.qmul(DF.qyaw(14.0), DF.qx(-58.0)), "R": DF.qmul(DF.qyaw(-14.0), DF.qx(-58.0))}
kit("DiaHL", "DiaHR", "DiaSL", "DiaSR", "Dia")


@mesh
def _diabolo_mesh(Pt):
    for b in ("DiaHL", "DiaHR"):
        Pt.seg(b, (0, 0, -0.03), (0, 0, STICK_L), 0.008, 0.007, "c8a060", segs=6)
        Pt.seg(b, (0, 0, -0.03), (0, 0, 0.10), 0.013, 0.013, "1c1c1e", segs=6)
    for b in ("DiaSL", "DiaSR"):
        Pt.seg(b, (0, 0, 0), (0, 0, 1.0), 0.0025, 0.0025, "f2efe6", segs=4, caps=False)
    for sx in (-1, 1):                             # two cups on an axle (along x)
        Pt.seg("Dia", (sx * 0.012, 0, 0), (sx * 0.062, 0, 0), 0.014, 0.064, "d8283a", segs=14)
        Pt.seg("Dia", (sx * 0.058, 0, 0), (sx * 0.064, 0, 0), 0.0645, 0.0645, "f4f2ea", segs=14)
    Pt.seg("Dia", (-0.012, 0, 0), (0.012, 0, 0), 0.012, 0.012, "1c1c1e", segs=8)
    Pt.box("Dia", (0.04, 0.0, 0.05), (0.012, 0.03, 0.006), "f4f2ea")      # (a stripe: its spin shows)


class Diabolo:
    """The spool's life between t_on and t_off: hanging in the V of the string
    under the stick tips, flying (ballistic, between two hang points), or
    swung round in front of him; its spin (rev/s) keyed apart."""

    def __init__(self, t_on):
        self.t_on = t_on
        self.modes = [(t_on, "hang", None)]
        self.rps = Keys().add(0.0, 0.0)

    def fly(self, t0, t1):
        self.modes.append((t0, "fly", t1))
        self.modes.append((t1, "hang", None))

    def swing(self, t0, t1, turns, r=0.42):
        self.modes.append((t0, "swing", (t1, turns, r)))
        self.modes.append((t1, "hang", None))

    def tips(self, C, fis):
        qb = C["qb"][fis]
        return {s: C["palm"][s][fis] + DF.qrot(DF.qmul(qb, Q_STICK[s]), (0.0, 0.0, STICK_L)) for s in "LR"}

    def hang(self, C, fis):
        T = self.tips(C, fis)
        mid = 0.5 * (T["L"] + T["R"])
        span = np.linalg.norm(T["L"] - T["R"], axis=1)
        sag = np.sqrt(np.maximum(0.004, (STRING / 2) ** 2 - (span / 2) ** 2))
        return mid - np.outer(sag, (0.0, 0.0, 1.0)), T

    def spool(self, fis, C):
        """(P, T, taut) per frame: the spool, the tips, string taut (flying)."""
        tt = fis / FPS
        Pn, T = self.hang(C, fis)
        taut = np.zeros(len(fis), bool)
        modes = sorted(self.modes, key=lambda x: x[0])
        for j, (t0, mode, arg) in enumerate(modes):
            t1 = modes[j + 1][0] if j + 1 < len(modes) else 1e9
            sel = (tt >= t0) & (tt < t1)
            if not sel.any() or mode == "hang":
                continue
            if mode == "fly":
                a, b = np.array([C["fi"](t0)]), np.array([C["fi"](arg)])
                p0 = self.hang(C, a)[0][0]
                p1 = self.hang(C, b)[0][0]
                Tf = max(0.05, arg - t0)
                u = (tt[sel] - t0) / Tf
                Pn[sel] = p0 + np.outer(u, p1 - p0) + np.outer(0.5 * G * Tf * Tf * u * (1 - u), (0, 0, 1))
                taut[sel] = True
            else:
                t_end, turns, r = arg
                u = (tt[sel] - t0) / max(0.1, t_end - t0)
                ease = np.minimum(1.0, np.minimum(u, 1.0 - u) * 4.0)       # (in and out of the swing)
                ang = 2 * np.pi * turns * u
                mid = 0.5 * (T["L"][sel] + T["R"][sel]) - np.array((0, 0, 0.30))
                qb = C["qb"][fis[sel]]
                loc = np.stack([r * np.sin(ang), np.full_like(ang, 0.05), -r * np.cos(ang)], 1) * ease[:, None]
                Pn[sel] = (mid + DF.qrot(qb, loc)) * ease[:, None] + Pn[sel] * (1 - ease[:, None])
        return Pn, T, taut

    def spin(self, fis, C):
        self.rps.done()
        rps = np.array(DF.sample(self.rps), float)
        ang = np.cumsum(rps) / FPS * 360.0
        return ang[fis]

    def fn_spool(self):
        def fn(fis, C):
            Pn, T, taut = self.spool(fis, C)
            Q = DF.qmul(C["qb"][fis], DF.qx(self.spin(fis, C)))
            return Pn, Q
        return fn

    def fn_string(self, side):
        def fn(fis, C):
            Pn, T, taut = self.spool(fis, C)
            mid = 0.5 * (T["L"] + T["R"])
            end = np.where(taut[:, None], mid, Pn)
            d = end - T[side]
            L = np.linalg.norm(d, axis=1)
            return T[side], _q_to(d), np.stack([np.ones_like(L), np.ones_like(L), np.maximum(L, 0.01)], 1)
        return fn


DIA_BASE = {"L": P(-0.20, 0.36, 1.08), "R": P(0.20, 0.36, 1.08)}


def _dia_whips(m, t, n, period=0.55, amp=0.13):
    """Spinning it up: the right stick lifted sharply, the left down, again."""
    for q in range(n):
        tt = t + q * period
        pose(m, tt + period * 0.45, DIA_BASE["L"] + P(0, 0, -0.03), DIA_BASE["R"] + P(0.02, 0, amp))
        pose(m, tt + period, DIA_BASE["L"], DIA_BASE["R"])
    return t + n * period


def _dia_toss(m, d, t, T, spread=0.42):
    """Hands snap apart: the string throws it up; caught in the V again T later."""
    pose(m, t - 0.5, DIA_BASE["L"] + P(0.06, 0, -0.06), DIA_BASE["R"] + P(-0.06, 0, -0.06))
    pose(m, t, P(-spread, 0.34, 1.20), P(spread, 0.34, 1.20))
    pose(m, t + min(0.6, 0.45 * (T - 0.15)), P(-0.22, 0.38, 1.34), P(0.22, 0.38, 1.34))   # (a low one: no time to wait)
    pose(m, t + T - 0.15, DIA_BASE["L"] + P(0, 0.02, 0.06), DIA_BASE["R"] + P(0, 0.02, 0.06))
    pose(m, t + T + 0.5, DIA_BASE["L"], DIA_BASE["R"])
    d.fly(t, t + T)
    m.f.pitch.add(t + 0.2, -16).add(t + T * 0.5, -26).add(t + T + 0.4, 6)
    return t + T + 0.6


def mon_diabolo(m, t, t_bow):
    """The diabolo: the sticks out of the trunk with the spool on the string;
    spun up whip by whip; tossed and caught, higher each time; swung round in
    a great circle in front of him (the sun); a toss with a turn under it; the
    biggest toss, caught behind ... no: caught low with a bow of the knees; the
    kit back in the trunk."""
    f = m.f
    t = begin(m, t)
    t = to_trunk(m, t)
    d = Diabolo(t + 1.0)
    state = lambda n: (("hand", "L" if n.endswith("L") else "R", np.zeros(3), Q_STICK[n[-1]]) if n.startswith("DiaH")
                       else ("fn", d.fn_string(n[-1])) if n.startswith("DiaS") else ("fn", d.fn_spool()))
    f.L.hold(t).add(t + 1.0, f.at_world(trunk_point(-0.10)))
    t = take(m, t, "R", ["DiaHL", "DiaHR", "DiaSL", "DiaSR", "Dia"], state, dx=0.06)
    m.hold["L"] = "kit"
    t = centre(m, t)
    pose(m, t + 0.6, DIA_BASE["L"], DIA_BASE["R"], 6, 14)
    t += 0.8
    d.rps.add(t, 0.0).add(t + 6.0, 2.2)
    t = _dia_whips(m, t, 12)
    t += 0.4
    for T in (0.8, 0.95, 1.05, 1.15):
        t = _dia_toss(m, d, t + 0.6, T)
        t = _dia_whips(m, t, 3)
    # The sun: swung round in front of him, the arms going round with it.
    ts = t + 0.4
    turns, dur = 3, 4.2
    for k in range(13):
        a = 2 * math.pi * turns * k / 12
        pose(m, ts + dur * k / 12, P(-0.20 + 0.10 * math.sin(a), 0.38, 1.12 - 0.08 * math.cos(a)),
             P(0.20 + 0.10 * math.sin(a), 0.38, 1.12 - 0.08 * math.cos(a)))
    d.swing(ts, ts + dur, turns)
    f.pitch.add(ts, 10).add(ts + dur, 10)
    t = ts + dur + 0.4
    t = _dia_whips(m, t, 4)
    # Up, and a turn under it.
    tt = t + 0.6
    t = _dia_toss(m, d, tt, 1.08, spread=0.46)
    f.put(tt + 0.25, m.x, m.y, m.yaw, lin=True)
    f.root.add(tt + 0.75, V((m.x, m.y, m.yaw + 180.0)), True)
    f.root.add(tt + 1.25, V((m.x, m.y, m.yaw + 360.0)))
    f._yaw = m.yaw = m.yaw + 360.0
    t = _dia_whips(m, t, 4)
    for k in (0, 1):                                # to each side of the room
        t = CF._side(m, t, "pub", k)
        t = _dia_toss(m, d, t + 0.4, 1.1)
        t = _dia_whips(m, t, 3)
    t = CF._side(m, t, "pub", None)
    # The fill: whips and tosses until the end, the last the highest, caught
    # with a dip of the knees.
    while t + 3.4 + 8.0 < t_bow - 2.4:
        t = _dia_toss(m, d, t + 0.5, 1.0)
        t = _dia_whips(m, t, 2)
    tl = t + 0.6
    t = _dia_toss(m, d, tl, 1.12, spread=0.48)
    squat(m, tl + 1.0, 0.14, 0.3)
    stand_up(m, tl + 1.6, 0.5)
    d.rps.add(t, 2.2).add(t + 1.5, 0.0)
    t = to_trunk(m, t + 0.4)
    t = stow(m, t, "R", ["DiaHL", "DiaHR", "DiaSL", "DiaSR", "Dia"], dx=0.06)
    pose(m, t, L=HR["L"])
    m.hold["L"] = None
    return finish(m, t, t_bow, "diabolo")


# --- The crystal ball ------------------------------------------------------------------
kit("Crystal")
CRYSTAL_R = 0.068


def _crystal_mat():
    return CF._see_through("FigCrystal", (0.86, 0.93, 1.0), 0.66, (0.70, 0.84, 1.0), 1.1)


@mesh
def _crystal_mesh(Pt):
    CF._sphere(Pt, "Crystal", CRYSTAL_R, "e8f4ff", 4, segs=16, rings=10)


def mon_crystal(m, t, t_bow):
    """Contact juggling: a crystal ball out of nowhere rolls round his palms,
    then hangs in the air on its own while his hands slide round it and he
    steps from side to side under it (it never moves); it pulls him a step;
    rolls along his outstretched arms, across his chest, back to his hand;
    gone."""
    f = m.f
    t = begin(m, t)
    t = centre(m, t)
    t = produce(m, t, "Crystal", "R", off=(0, 0, CRYSTAL_R))
    # Round the palms: both hands together, the ball rolling over the backs.
    pose(m, t + 0.6, P(-0.06, 0.34, 1.20), P(0.06, 0.34, 1.20), 6, 18)
    path = Keys()
    t1 = t + 0.6
    for k in range(17):
        a = 2 * math.pi * k / 8
        path.add(t1 + 0.45 * k, P(0.07 * math.cos(a), 0.36 + 0.03 * math.sin(a), 1.27 + 0.03 * math.sin(2 * a)))
    m.prop("Crystal", t1, ("local", path, Q_ID), 6)
    for k in range(17):
        a = 2 * math.pi * k / 8
        pose(m, t1 + 0.45 * k, P(-0.06 + 0.03 * math.cos(a), 0.34, 1.20 + 0.02 * math.sin(a)),
             P(0.06 + 0.03 * math.cos(a), 0.34, 1.20 - 0.02 * math.sin(a)))
    t = t1 + 0.45 * 16
    # The isolation: it stays where it is.
    fw2 = CF._fwd_xy(m.yaw)
    fw = V((fw2.x, fw2.y, 0.0))
    ball = V((m.x + 0.36 * fw.x, m.y + 0.36 * fw.y, floor_z(m.x, m.y) + 1.27))
    m.prop("Crystal", t, ("spot", ball.copy(), Q_ID), 0)
    rt = V((-fw.y, fw.x, 0.0))                          # (his right? left: whichever, the ball's sideways)
    for k in range(9):
        a = 2 * math.pi * k / 8
        off = rt * (0.075 * math.cos(a)) + V((0, 0, 0.075 * math.sin(a)))
        f.L.add(t + 0.6 * k, f.at_world(ball + off * 1.0 - fw * 0.02))
        f.R.add(t + 0.6 * k, f.at_world(ball - off * 1.0 - fw * 0.02))
    t += 4.8
    for side_step in (0.22, -0.22, 0.0):               # he moves under it; it stays
        x, y = CF.FIN_SPOT[0] + rt.x * side_step, CF.FIN_SPOT[1] + rt.y * side_step
        m.slide(t, (x, y), 1.6)
        f.L.add(t + 0.8, f.at_world(ball + rt * 0.08)).add(t + 1.6, f.at_world(ball + rt * 0.08))
        f.R.add(t + 0.8, f.at_world(ball - rt * 0.08)).add(t + 1.6, f.at_world(ball - rt * 0.08))
        f.lean.add(t + 0.8, 8 + 6 * abs(side_step)).add(t + 1.6, 6)
        t += 2.2
    # It pulls him a step forward (it drifts; he follows, hands on it).
    drift = Keys()
    drift.add(t, ball.copy()).add(t + 1.6, ball + fw * 0.30).add(t + 3.4, ball + fw * 0.30 + V((0, 0, 0.16)))
    drift.add(t + 5.0, ball + V((0, 0, 0.04)))
    m.prop("Crystal", t, ("wkeys", drift, Q_ID), 0)
    for tt, w in ((t + 1.6, ball + fw * 0.30), (t + 3.4, ball + fw * 0.30 + V((0, 0, 0.16))), (t + 5.0, ball + V((0, 0, 0.04)))):
        f.L.add(tt, f.at_world(w + rt * 0.08))
        f.R.add(tt, f.at_world(w - rt * 0.08))
    m.slide(t + 0.4, (CF.FIN_SPOT[0] + 0.26 * fw.x, CF.FIN_SPOT[1] + 0.26 * fw.y), 1.4)
    m.slide(t + 3.4, CF.FIN_SPOT, 1.6)
    f.lean.add(t + 1.6, 14).add(t + 3.4, 6)
    t += 5.4
    # Along his arms, out wide: right hand, right arm, across the chest, left arm, left hand.
    pose(m, t + 0.8, P(-0.62, 0.14, 1.42), P(0.62, 0.14, 1.42), 3, 8)
    roll = Keys()
    pts = [(0.62, 0.14, 1.42 + CRYSTAL_R), (0.40, 0.12, 1.47), (0.18, 0.14, 1.50), (0.0, 0.17, 1.47),
           (-0.18, 0.14, 1.50), (-0.40, 0.12, 1.47), (-0.62, 0.14, 1.42 + CRYSTAL_R)]
    roll.add(t + 0.8, P(*pts[0]))
    for k, p in enumerate(pts):
        roll.add(t + 1.2 + 0.55 * k, P(*p))
    for k, p in enumerate(reversed(pts)):
        roll.add(t + 1.2 + 0.55 * (len(pts) + k), P(*p))
    m.prop("Crystal", t + 0.8, ("local", roll, Q_ID), 8)
    f.yaw.add(t + 1.2, -40).add(t + 1.2 + 0.55 * 6, 40).add(t + 1.2 + 0.55 * 13, -40).add(t + 1.2 + 0.55 * 14, 0)
    t += 1.2 + 0.55 * 14
    pose(m, t + 0.8, P(-0.20, 0.30, 1.20), P(0.18, 0.38, 1.30), 3, 10)
    m.prop("Crystal", t + 0.8, ("hand", "R", np.array((0, 0, CRYSTAL_R)), Q_ID), 8)
    t = vanish(m, t + 1.0, "Crystal")
    t = ready(m, t)
    return finish(m, t, t_bow, "crystal ball", 35)


# --- Trick roping ------------------------------------------------------------------------
kit("Loop", "Spoke", "Honda")


@mesh
def _rope_mesh(Pt):
    n = 36
    for k in range(n):                              # a unit ring in the xy plane, centre at the bone
        a0, a1 = 2 * math.pi * k / n, 2 * math.pi * (k + 1) / n
        Pt.seg("Loop", (math.cos(a0), math.sin(a0), 0), (math.cos(a1), math.sin(a1), 0), 0.008, 0.008, "e8d8a8",
               segs=4, caps=False)
    Pt.seg("Spoke", (0, 0, 0), (0, 0, 1.0), 0.007, 0.007, "e8d8a8", segs=5, caps=False)
    Pt.ball("Honda", (0, 0, 0), 0.016, "c8b078", segs=6, rings=4)


class Rope:
    """The spinning loop: centre (his frame, keyed), radius (keyed), the plane's
    normal (his frame, keyed), its spin (rev/s); the spoke from his right hand
    to the honda on the loop."""

    def __init__(self, t_on):
        self.c = Keys().add(0.0, P(0.0, 0.5, 0.5))
        self.r = Keys().add(0.0, 0.40)
        self.n = Keys().add(0.0, P(0.0, 0.0, 1.0))
        self.rps = Keys().add(0.0, 0.0)
        self.t_on = t_on

    def key(self, t, c=None, r=None, n=None, rps=None):
        if c is not None:
            self.c.add(t, V(c))
        if r is not None:
            self.r.add(t, r)
        if n is not None:
            self.n.add(t, V(n).normalized())
        if rps is not None:
            self.rps.add(t, rps)

    def _all(self, fis, C):
        for k in (self.c, self.r, self.n, self.rps):
            k.done()
        cl = np.array([(v.x, v.y, v.z) for v in DF.sample(self.c)], float)[fis]
        r = np.array(DF.sample(self.r), float)[fis]
        nl = np.array([(v.x, v.y, v.z) for v in DF.sample(self.n)], float)[fis]
        rps = np.array(DF.sample(self.rps), float)
        ang = (np.cumsum(rps) / FPS * 2 * np.pi)[fis]
        qb = C["qb"][fis]
        cw = C["pos"][fis] + DF.qrot(qb, cl)
        nw = DF.qrot(qb, nl)
        nw /= np.linalg.norm(nw, axis=1, keepdims=True)
        Qp = _q_to(nw)                                        # the loop's plane: +z of the ring onto the normal
        Qs = DF.qmul(Qp, _qaxis((0, 0, 1), np.degrees(ang)))  # spun in its plane
        honda = cw + DF.qrot(Qs, np.stack([r, np.zeros_like(r), np.zeros_like(r)], 1))
        return cw, r, Qs, honda

    def fn_loop(self):
        def fn(fis, C):
            cw, r, Qs, honda = self._all(fis, C)
            return cw, Qs, np.stack([r, r, np.ones_like(r)], 1)
        return fn

    def fn_honda(self):
        def fn(fis, C):
            cw, r, Qs, honda = self._all(fis, C)
            return honda, Qs
        return fn

    def fn_spoke(self):
        def fn(fis, C):
            cw, r, Qs, honda = self._all(fis, C)
            hand = C["palm"]["R"][fis]
            d = honda - hand
            L = np.linalg.norm(d, axis=1)
            return hand, _q_to(d), np.stack([np.ones_like(L), np.ones_like(L), np.maximum(L, 0.01)], 1)
        return fn


def _circle_hand(m, t, dur, c, rad, rps, side="R", plane="xy"):
    """The roping hand making small circles round c (his frame)."""
    keys = m.f.R if side == "R" else m.f.L
    n = max(4, int(dur * rps * 6))
    for k in range(n + 1):
        a = 2 * math.pi * rps * dur * k / n
        if plane == "xy":
            p = V(c) + V((rad * math.cos(a), rad * math.sin(a), 0.0))
        else:                                           # (in his side plane: y/z)
            p = V(c) + V((0.0, rad * math.cos(a), rad * math.sin(a)))
        keys.add(t + dur * k / n, p, lin=True)
    return t + dur


def mon_lasso(m, t, t_bow):
    """Trick roping: a coil of rope out of the trunk; a flat loop spinning at his
    knees, raised up over his head for a halo and lowered round him for the
    wedding ring; stood on edge at his side; the Texas skip, jumping through
    it and back; in to a little loop, the rope coiled."""
    f = m.f
    t = begin(m, t)
    t = to_trunk(m, t)
    rope = Rope(t + 1.0)
    st = {"Loop": ("fn", rope.fn_loop()), "Spoke": ("fn", rope.fn_spoke()), "Honda": ("fn", rope.fn_honda())}
    rope.key(t, c=P(0.18, 0.30, 1.00), r=0.08, n=P(0, 1, 0), rps=0.0)
    t = take(m, t, "R", ["Loop", "Spoke", "Honda"], lambda n: st[n])
    t = centre(m, t)
    # The flat loop: opened, spinning at his knees.
    rope.key(t, c=P(0.18, 0.30, 1.00), r=0.08, n=P(0, 1, 0), rps=0.0)
    rope.key(t + 1.6, c=P(0.10, 0.62, 0.55), r=0.42, n=P(0, 0, 1), rps=1.3)
    pose(m, t + 1.0, R=P(0.16, 0.48, 1.00), lean=10, pitch=24)
    t = _circle_hand(m, t + 1.6, 14.0, P(0.10, 0.50, 1.00), 0.06, 1.3)
    rope.key(t, r=0.42, rps=1.3)
    # Bigger, and a step round it.
    rope.key(t + 2.0, c=P(0.0, 0.70, 0.45), r=0.55)
    t = _circle_hand(m, t, 10.0, P(0.06, 0.52, 1.02), 0.07, 1.3)
    # Up overhead: the halo.
    rope.key(t + 2.0, c=P(0.0, 0.10, 2.10), r=0.55, n=P(0, 0, 1))
    pose(m, t + 1.8, R=P(0.05, 0.12, 2.00), lean=2, pitch=-24)
    t = _circle_hand(m, t + 2.0, 10.0, P(0.05, 0.12, 2.00), 0.06, 1.3)
    # Down round him: the wedding ring.
    rope.key(t + 2.2, c=P(0.0, 0.0, 1.05), r=0.72, rps=1.1)
    pose(m, t + 2.0, R=P(0.05, 0.10, 1.95), pitch=4)
    tw = t + 2.2
    t = _circle_hand(m, tw, 14.0, P(0.05, 0.10, 1.95), 0.07, 1.1)
    m.f.put(tw + 3.0, m.x, m.y, m.yaw, lin=True)              # a slow turn inside the ring
    m.f.root.add(tw + 7.0, V((m.x, m.y, m.yaw + 180.0)), True)
    m.f.root.add(tw + 11.0, V((m.x, m.y, m.yaw + 360.0)))
    m.f._yaw = m.yaw = m.yaw + 360.0
    rope.key(t + 1.4, c=P(0.0, 0.0, 1.10), r=0.72)
    # Back up and out to his right, stood on edge: the vertical.
    rope.key(t + 2.6, c=P(0.70, 0.10, 1.00), r=0.55, n=P(1, 0, 0), rps=1.2)
    pose(m, t + 2.2, R=P(0.36, 0.24, 1.30), pitch=6, yaw=-30)
    t = _circle_hand(m, t + 2.6, 10.0, P(0.36, 0.24, 1.30), 0.06, 1.2, plane="yz")
    # The Texas skip: swung across in front of him and he jumps through it, and back.
    for k in range(8):
        side = -1 if k % 2 == 0 else 1
        rope.key(t + 0.9, c=P(0.0, 0.25, 0.75), r=0.62)
        rope.key(t + 1.8, c=P(side * 0.70, 0.10, 1.00), r=0.55)
        pose(m, t + 0.9, R=P(0.05, 0.36, 1.45), yaw=0)
        pose(m, t + 1.8, R=P(side * 0.30, 0.24, 1.30), yaw=side * -30)
        hop(m, t + 0.55, 0.26, 0.75)
        t += 1.9
    # In to a little loop and coiled.
    rope.key(t + 1.6, c=P(0.18, 0.40, 1.05), r=0.10, n=P(0, 1, 0), rps=0.4)
    rope.key(t + 2.4, rps=0.0)
    pose(m, t + 1.6, P(-0.10, 0.34, 1.10), P(0.18, 0.36, 1.10), 3, 6, 0)
    t += 2.6
    t = to_trunk(m, t)
    t = stow(m, t, "R", ["Loop", "Spoke", "Honda"])
    return finish(m, t, t_bow, "lasso")


# --- The dancing cane ----------------------------------------------------------------------
kit("Cane")
CANE_L = 0.90


@mesh
def _cane_mesh(Pt):
    Pt.seg("Cane", (0, 0, -0.05), (0, 0, CANE_L - 0.10), 0.011, 0.011, "141414", segs=8)
    Pt.seg("Cane", (0, 0, -0.10), (0, 0, -0.05), 0.012, 0.012, "f4f2ea", segs=8)
    Pt.seg("Cane", (0, 0, CANE_L - 0.10), (0, 0, CANE_L - 0.04), 0.016, 0.014, "d8c070", segs=8)


CANE_GRIP = 0.80                                     # from its foot (the bone) up to his hand


def _cane_dance(t0, pts, T):
    """The cane on its own: through world points pts (one every T s), upright
    with a sway and a slow twirl about its middle, both dying away at the end."""
    keys = Keys()
    for k, p in enumerate(pts):
        keys.add(t0 + k * T, V(p))
    t1 = t0 + (len(pts) - 1) * T

    def q(tt):
        calm = np.clip((t1 - tt) / 1.5, 0.0, 1.0) * np.clip((tt - t0) / 1.0, 0.0, 1.0)
        sway = 18 * np.sin(2.1 * (tt - t0)) * calm
        twirl = 360.0 * np.round(120 * (t1 - t0) / 360.0) * 0 + 120 * (tt - t0) * calm
        return DF.qmul(_qaxis((0, 0, 1), twirl), _qaxis((1, 0, 0), sway))
    return keys, q


def mon_cane(m, t, t_bow):
    """The dancing cane: laid on the stage, it stands up by itself, floats up
    and dances round him in the spotlight; he grabs, it dodges; it leads him
    round the stage; drops into his hand at last, and he struts with it,
    twirling it."""
    f = m.f
    t = begin(m, t)
    t = centre(m, t)
    fw = CF._fwd_xy(m.yaw)
    rt = V((fw.y, -fw.x))
    base = V((m.x, m.y, floor_z(m.x, m.y)))
    lie = base + V((fw.x * 0.55, fw.y * 0.55, 0.012))
    q_lie = DF.qmul(DF.qyaw(m.yaw + 90.0), DF.qx(90.0))
    m.prop("Cane", t, ("spot", lie, q_lie), 0)
    m.scale("Cane", t, 0.001, t + 0.4, 1.0)
    pose(m, t + 0.6, P(-0.10, 0.20, 1.00), P(0.10, 0.20, 1.00), 14, 34)       # looks at it
    t += 1.2
    hold_at = base + V((fw.x * 0.40 + rt.x * 0.18, fw.y * 0.40 + rt.y * 0.18, 1.16 - CANE_GRIP))
    rel = ((0.55, 0.0, 0.0), (0.55, 0.0, 0.40), (0.45, 0.35, 0.70), (0.20, 0.55, 0.95), (-0.20, 0.55, 0.80),
           (-0.55, 0.20, 1.05), (-0.45, -0.25, 0.85), (0.15, -0.55, 1.10), (0.55, -0.20, 0.90), (0.70, 0.30, 0.80),
           (0.40, 0.60, 1.00), (0.10, 0.75, 0.85), (-0.35, 0.60, 0.95), (-0.60, 0.10, 0.80), (-0.30, -0.45, 1.00),
           (0.30, -0.60, 0.85), (0.60, -0.10, 0.70), (0.45, 0.25, 0.55))
    pts = [base + V((fw.x * a + rt.x * b, fw.y * a + rt.y * b, h)) for a, b, h in rel] + [hold_at]
    T = 1.15
    keys, q = _cane_dance(t, pts, T)
    m.prop("Cane", t, ("wkeys", keys, q), 8)
    for k in range(1, len(pts) - 1):
        tt = t + k * T
        w = pts[k]
        m.look_at(tt - 0.4, (w.x, w.y), 0.5)
        if k in (3, 6, 9, 13, 16):
            grab = w + V((0, 0, 0.40))
            side = "R" if k not in (6, 13) else "L"
            keys2 = f.R if side == "R" else f.L
            DF.hold_live(keys2, tt - 0.9)
            keys2.add(tt - 0.1, f.at_world(grab)).add(tt + 0.7, HR[side].copy())
            f.lean.add(tt - 0.1, 18).add(tt + 0.7, 4)
    t_end = t + (len(pts) - 1) * T
    f.yaw.add(t_end, 0)
    DF.hold_live(f.R, t_end - 1.0)
    f.R.add(t_end, P(0.18, 0.40, 1.16))
    m.prop("Cane", t_end, ("hand", "R", np.array((0, 0, -CANE_GRIP)), Q_ID), 6)
    m.hold["R"] = "cane"
    t = t_end + 0.4
    # The strut: across the stage and back with it, tapping, a twirl.
    for k, (dx, face) in enumerate(((0.45, -90.0), (-0.45, 90.0))):
        to = (CF.FIN_SPOT[0] + rt.x * dx, CF.FIN_SPOT[1] + rt.y * dx)
        t = CF._step_to(m, t, (m.x, m.y), m.yaw + 0.0)
        m.slide(t, to, 2.0)
        for q2 in range(3):
            pose(m, t + 0.35 + 0.66 * q2, R=P(0.20, 0.42, 1.10))
            pose(m, t + 0.66 + 0.66 * q2, R=P(0.20, 0.42, 1.18))
        f.yaw.add(t + 0.5, 20 if k == 0 else -20).add(t + 1.8, 0)
        t += 2.2
    t = centre(m, t)
    for q2 in range(2):                                 # the twirl: round his hand, twice
        for k in range(4):
            m.prop("Cane", t + 0.22 * k, ("hand", "R", np.array((0, 0, -0.42)), DF.qy(-90.0 * (k + 1)) if hasattr(DF, "qy") else
                                         DF.qmul(DF.qyaw(0.0), CF._qy(-90.0 * (k + 1)))), 2)
        t += 0.9
    m.prop("Cane", t, ("hand", "R", np.array((0, 0, -CANE_GRIP)), Q_ID), 4)
    pose(m, t, R=P(0.24, 0.30, 1.00), lean=3, pitch=4)
    t += 0.4
    return finish(m, t, t_bow, "dancing cane", 35)


def mon_bloom(m, t):
    """The gift (Monday): a little soft-shoe with the cane (taps, a heel and toe,
    the cane twirled), then it is tapped on the stage, raised, and its head
    bursts into a bouquet; the cane is gone."""
    f = m.f
    t = centre(m, t)
    fw = CF._fwd_xy(m.yaw)
    rt = V((fw.y, -fw.x))
    for k in range(6):                                  # side steps, tap, tap, a kick
        side = 1 if k % 2 == 0 else -1
        to = (CF.FIN_SPOT[0] + rt.x * 0.30 * side, CF.FIN_SPOT[1] + rt.y * 0.30 * side)
        m.slide(t, to, 1.0)
        foot = f.fR if side > 0 else f.fL
        sx = 0.10 if side > 0 else -0.10
        foot.hold(t + 1.0).add(t + 1.3, P(sx, 0.16, 0.22)).add(t + 1.6, P(sx, 0.02, 0.09))
        foot.add(t + 1.9, P(sx, 0.20, 0.30)).add(t + 2.3, P(sx, 0.02, 0.09))
        pose(m, t + 1.3, R=P(0.24, 0.40, 1.06), lean=4, yaw=side * 15)
        pose(m, t + 1.6, R=P(0.24, 0.40, 1.14))
        pose(m, t + 2.3, R=P(0.24, 0.32, 1.00), yaw=0)
        t += 2.5
    t = centre(m, t)
    pose(m, t + 0.8, R=P(0.30, 0.30, 0.92), lean=6)
    pose(m, t + 1.2, R=P(0.30, 0.30, 1.02))
    pose(m, t + 1.6, R=P(0.30, 0.30, 0.92))                 # tap, tap
    pose(m, t + 2.0, R=P(0.30, 0.30, 1.02))
    pose(m, t + 3.0, R=P(0.30, 0.20, 1.70), pitch=-20)      # raised high
    m.prop("Cane", t + 3.0, ("hand", "R", np.array((0, 0, -0.30)), Q_ID), 6)
    m.scale("Cane", t + 3.4, 1.0, t + 3.7, 0.001)
    m.prop("Cane", t + 3.75, ("hide",), 0)
    m.prop("Bouquet", t + 3.4, ("hand", "R", np.array((0.0, 0.0, 0.02)), Q_ID), 0)
    m.scale("Bouquet", t + 3.4, 0.001, t + 3.8, 1.0)
    pose(m, t + 4.4, R=P(0.22, 0.42, 1.38), pitch=4)
    m.hold["R"] = "bouquet"
    return t + 4.6


# --- Fire poi -------------------------------------------------------------------------------
POI_CHAIN = 0.52
kit("PoiL", "PoiR", "PoiFL", "PoiFR", "PoiCL", "PoiCR")
POI_TRAILS = [f"PoiT{s}{k}" for s in "LR" for k in range(1, 7)]
kit(*POI_TRAILS)


@mesh
def _poi_mesh(Pt):
    for s in "LR":
        Pt.ball(f"Poi{s}", (0, 0, 0), 0.045, "2a2420", segs=8, rings=5)
        CF._flame_mesh(Pt, f"PoiF{s}", V((0, 0, -0.02)), 0.95)
        Pt.seg(f"PoiC{s}", (0, 0, 0), (0, 0, 1.0), 0.004, 0.004, "9a9ea4", segs=4, caps=False)
        for k in range(1, 7):
            CF._flame_mesh(Pt, f"PoiT{s}{k}", V((0, 0, -0.02)), 0.8)


class Poi:
    """Both poi on their chains: each head goes round its hand in a plane at a
    rate (rev/s), keyed per hand: plane normals in his frame, the phase
    carried on; lit or not; their flames, and trails of flame behind them."""

    def __init__(self):
        self.n = {s: Keys().add(0.0, P(1.0, 0.0, 0.0)) for s in "LR"}
        self.rps = {s: Keys().add(0.0, 0.0) for s in "LR"}
        self.dirn = {"L": 1.0, "R": 1.0}
        self.lit = Keys().add(0.0, 0.0)
        self.phase0 = {"L": 0.0, "R": 180.0}

    def key(self, t, side, n=None, rps=None):
        for s in (side if side in ("LR", "RL") else side):
            if n is not None:
                self.n[s].add(t, V(n).normalized())
            if rps is not None:
                self.rps[s].add(t, rps)

    def heads(self, fis, C, side):
        for k in (self.n[side], self.rps[side]):
            k.done()
        nl = np.array([(v.x, v.y, v.z) for v in DF.sample(self.n[side])], float)[fis]
        rps = np.array(DF.sample(self.rps[side]), float)
        ang = (np.cumsum(rps) / FPS * 360.0 + self.phase0[side])[fis]
        qb = C["qb"][fis]
        nw = DF.qrot(qb, nl)
        nw /= np.linalg.norm(nw, axis=1, keepdims=True)
        Qp = DF.qmul(_q_to(nw), _qaxis((0, 0, 1), ang))
        hand = C["palm"][side][fis]
        head = hand + DF.qrot(Qp, np.tile((POI_CHAIN, 0.0, 0.0), (len(fis), 1)))
        return hand, head

    def fn_head(self, side):
        def fn(fis, C):
            hand, head = self.heads(fis, C, side)
            return head, np.tile(Q_ID, (len(fis), 1))
        return fn

    def fn_chain(self, side):
        def fn(fis, C):
            hand, head = self.heads(fis, C, side)
            d = head - hand
            L = np.linalg.norm(d, axis=1)
            return hand, _q_to(d), np.stack([np.ones_like(L), np.ones_like(L), np.maximum(L, 0.01)], 1)
        return fn

    def fn_flame(self, side):
        def fn(fis, C):
            hand, head = self.heads(fis, C, side)
            self.lit.done()
            lit = np.array(DF.sample(self.lit), float)[fis]
            fl = 1.0 + 0.12 * np.sin(fis * 1.7 + (1 if side == "L" else 0))
            S = np.stack([lit * fl, lit * fl, lit * fl * 1.1], 1)
            return head, np.tile(Q_ID, (len(fis), 1)), np.maximum(S, 0.001)
        return fn


def mon_poi(m, t, t_bow):
    """The finale: fire poi in the dark. Two wicks on chains out of the trunk,
    lit off his fingertip; the house goes black and the spot drops to a
    glow; wheels of fire at his sides, the butterfly in front of him, a
    halo spun over his head, the weave crossing in front, the windmill, a
    turn with them blazing, then the great circles out wide, slowing, still;
    blown out; the lights come back to a spot on him."""
    f = m.f
    t = begin(m, t)
    t = to_trunk(m, t)
    poi = Poi()
    st = lambda n: (("fn", poi.fn_head(n[-1])) if n in ("PoiL", "PoiR") else ("fn", poi.fn_chain(n[-1]))
                    if n.startswith("PoiC") else ("fn", poi.fn_flame(n[-1])))
    for s in "LR":
        poi.key(t, s, n=P(1, 0, 0), rps=0.0)
    f.L.hold(t).add(t + 1.0, f.at_world(trunk_point(-0.12)))
    t = take(m, t, "R", ["PoiL", "PoiR", "PoiCL", "PoiCR", "PoiFL", "PoiFR"], st)
    m.hold["L"] = "kit"
    m.trails = getattr(m, "trails", []) + [(f"PoiT{s}{k}", f"PoiF{s}", k / FPS, 0.92 - 0.12 * k)
                                          for s in "LR" for k in range(1, 7)]
    for n in POI_TRAILS:
        m.prop(n, t, ("spot", V((CF.FIN_SPOT[0], CF.FIN_SPOT[1], 0.5)), Q_ID), 0)   # (placeholders: trails copy)
    t = centre(m, t)
    # Lit off his fingertip, the poi hanging still.
    pose(m, t + 0.6, P(-0.24, 0.30, 1.30), P(0.24, 0.30, 1.30), 4, 20)
    pose(m, t + 1.2, R=P(0.10, 0.34, 1.10))
    m.fire.add(t + 1.2, 0.0).add(t + 1.4, 1.0)
    pose(m, t + 2.2, R=P(0.10, 0.40, 0.84), lean=20, pitch=36)
    poi.lit.add(t + 2.6, 0.0).add(t + 3.0, 1.0)
    m.fire.add(t + 3.0, 1.0).add(t + 3.2, 0.0)
    pose(m, t + 3.6, P(-0.22, 0.24, 1.10), P(0.22, 0.24, 1.10), 4, 6)
    t += 3.8
    lights(m, t, 3.0, black=0.85, spot=0.25)
    m.beam.add(t, 1.0).add(t + 3.0, 0.35)
    # Wheels at his sides (each poi in his forward-up plane, going forward).
    for s in "LR":
        poi.key(t, s, n=P(1, 0, 0), rps=0.0)
        poi.key(t + 2.0, s, rps=1.4)
    pose(m, t + 1.0, P(-0.30, 0.18, 1.02), P(0.30, 0.18, 1.02))
    for k in range(10):
        dz = 0.03 * math.sin(k)
        pose(m, t + 1.5 + 1.0 * k, P(-0.30, 0.18 + 0.03 * math.sin(k * 1.3), 1.02 + dz),
             P(0.30, 0.18 + 0.03 * math.cos(k * 1.3), 1.02 - dz))
    t += 11.0
    # The butterfly: hands together in front, poi in the wall plane, mirrored.
    poi.key(t, "L", n=P(1, 0, 0))
    poi.key(t + 1.2, "L", n=P(0, 1, 0), rps=1.2)
    poi.key(t, "R", n=P(1, 0, 0))
    poi.key(t + 1.2, "R", n=P(0, -1, 0), rps=1.2)
    pose(m, t + 1.2, P(-0.06, 0.38, 1.28), P(0.06, 0.38, 1.28), 6, 2)
    for k in range(10):
        pose(m, t + 2.0 + 1.0 * k, P(-0.06, 0.38, 1.28 + 0.04 * math.sin(k)), P(0.06, 0.38, 1.28 + 0.04 * math.sin(k)))
    t += 12.0
    # The halo: both overhead, spun flat.
    for s in "LR":
        poi.key(t + 1.4, s, n=P(0, 0, 1), rps=1.0)
    pose(m, t + 1.4, P(-0.10, 0.12, 2.00), P(0.10, 0.12, 2.00), 2, -26)
    t += 9.0
    # The weave: back to the sides and crossing in front (hands swapping over).
    for s in "LR":
        poi.key(t + 1.4, s, n=P(1, 0, 0), rps=1.3)
    for k in range(8):
        a = (k % 2) * 2 - 1
        pose(m, t + 1.4 + 1.1 * k, P(-0.18 + 0.14 * a, 0.34, 1.18), P(0.18 + 0.14 * a, 0.34, 1.18), 6, 4, yaw=8 * a)
    t += 1.4 + 1.1 * 8
    # The windmill: arms going round with them.
    for k in range(16):
        a = 2 * math.pi * k / 8
        pose(m, t + 0.55 * k, P(-0.26 - 0.08 * math.cos(a), 0.30, 1.32 + 0.18 * math.sin(a)),
             P(0.26 + 0.08 * math.cos(a + math.pi), 0.30, 1.32 + 0.18 * math.sin(a + math.pi)))
    t += 0.55 * 16
    # A turn with them blazing.
    f.put(t, m.x, m.y, m.yaw, lin=True)
    f.root.add(t + 2.0, V((m.x, m.y, m.yaw + 180.0)), True)
    f.root.add(t + 4.0, V((m.x, m.y, m.yaw + 360.0)))
    f._yaw = m.yaw = m.yaw + 360.0
    pose(m, t + 1.0, P(-0.40, 0.16, 1.30), P(0.40, 0.16, 1.30), 2, -6)
    t += 4.4
    # The great circles: arms wide, the poi going round them; slowing; still.
    for s in "LR":
        poi.key(t + 1.0, s, n=P(0, 1, 0) if s == "R" else P(0, -1, 0), rps=1.1)
    pose(m, t + 1.0, P(-0.56, 0.14, 1.44), P(0.56, 0.14, 1.44), 2, -8)
    t_fill = max(t + 10.0, t_bow - 2.4 - 14.0)
    for s in "LR":
        poi.key(t_fill, s, rps=1.1)
        poi.key(t_fill + 4.0, s, rps=0.0)
    pose(m, t_fill + 4.0, P(-0.40, 0.20, 1.40), P(0.40, 0.20, 1.40))
    t = t_fill + 4.4
    # Blown out, one then the other; the light back on him.
    pose(m, t + 0.8, P(-0.30, 0.26, 1.40), P(0.10, 0.40, 1.40), 6, 10)
    poi.lit.add(t + 1.4, 1.0).add(t + 2.2, 0.0)
    pose(m, t + 2.6, P(-0.24, 0.30, 1.20), P(0.24, 0.30, 1.20), 3, 4)
    lights(m, t + 1.0, 2.0, black=0.0, spot=1.0)
    m.beam.add(t + 1.0, 0.35).add(t + 3.0, 1.0)
    t += 3.0
    return finish(m, t, t_bow, "fire poi", 55, hat=False)


def mon_tidy(m, t):
    t = to_trunk(m, t)
    t = stow(m, t, "R", ["PoiL", "PoiR", "PoiCL", "PoiCR", "PoiFL", "PoiFR"] + POI_TRAILS)
    m.hold["L"] = None
    return CF._back(m, t, 0.8)



# =====================================================================================
# Shared: smooth world paths
# =====================================================================================
def spline(points, t0, dt):
    """Catmull-Rom through world points, one every dt s from t0: fn(tt) -> (n, 3)."""
    Pts = np.array([tuple(p) for p in points], float)
    Pts = np.vstack([Pts[:1], Pts, Pts[-1:]])

    def at(tt):
        u = np.clip((np.asarray(tt, float) - t0) / dt, 0.0, len(points) - 1 - 1e-9)
        i = np.floor(u).astype(int)
        s = (u - i)[:, None]
        p0, p1, p2, p3 = Pts[i], Pts[i + 1], Pts[i + 2], Pts[i + 3]
        return 0.5 * ((2 * p1) + (-p0 + p2) * s + (2 * p0 - 5 * p1 + 4 * p2 - p3) * s * s +
                      (-p0 + 3 * p1 - 3 * p2 + p3) * s * s * s)
    return at


def follow(f, path, off=V((0, 0, 0))):
    """A hand target riding on a moving world path (fn(tt) -> (n, 3))."""
    return lambda tt: f.to_local(tt, V(path(np.array([tt]))[0]) + off)




def run_events(ev, fis, evalf, blend=0.35):
    """Evaluate a prop's (t0, mode, arg) events over frames fis with evalf(mode,
    arg, fs, t0) -> (P, Q, extra); each change of mode blended in over blend s
    from where the last one would have been. Returns P, Q, extra, shown."""
    tt = fis / FPS
    n = len(fis)
    Pn = np.zeros((n, 3))
    Q = np.tile(Q_ID, (n, 1))
    X = np.zeros(n)
    shown = np.zeros(n, bool)
    ev = sorted(ev, key=lambda e: e[0])
    for j, (t0, mode, arg) in enumerate(ev):
        t1 = ev[j + 1][0] if j + 1 < len(ev) else 1e9
        sel = (tt >= t0) & (tt < t1)
        if not sel.any() or mode == "hide":
            continue
        fs = fis[sel]
        p, q, x = evalf(mode, arg, fs, t0)
        if j > 0 and ev[j - 1][1] != "hide":
            u = (tt[sel] - t0) / blend
            w = np.clip(u, 0.0, 1.0)
            if (w < 1.0).any():
                b = w < 1.0
                pp, pq, _x = evalf(ev[j - 1][1], ev[j - 1][2], fs[b], ev[j - 1][0])
                e = w[b] * w[b] * (3 - 2 * w[b])
                p[b] = pp + (p[b] - pp) * e[:, None]
                q[b] = DF.nlerp(pq, q[b], e)
        Pn[sel], Q[sel], X[sel] = p, q, x
        shown[sel] = True
    return Pn, Q, X, shown


# =====================================================================================
# TUESDAY: magic
# =====================================================================================
def tue_levitate(m, t, t_bow):
    """Opener: in the spotlight he rises slowly off the stage, feet dangling,
    arms floating out, turns round once in the air, and settles back down."""
    f = m.f
    t = begin(m, t)
    z0 = floor_z(m.x, m.y)
    pose(m, t + 1.0, P(-0.30, 0.18, 1.10), P(0.30, 0.18, 1.10), 4, -8, 0)
    for k in (f.zk, f.fL, f.fR):
        k.hold(t + 1.0)
    rise = 0.34
    f.zk.add(t + 4.5, z0 + rise).add(t + 10.5, z0 + rise + 0.04).add(t + 13.5, z0)
    f.fL.add(t + 4.5, P(-0.08, 0.05, 0.05)).add(t + 10.5, P(-0.08, 0.05, 0.05)).add(t + 13.5, V(STAND[0]))
    f.fR.add(t + 4.5, P(0.08, 0.07, 0.04)).add(t + 10.5, P(0.08, 0.07, 0.04)).add(t + 13.5, V(STAND[1]))
    pose(m, t + 4.5, P(-0.48, 0.14, 1.22), P(0.48, 0.14, 1.22), 2, -4)
    f.put(t + 5.0, m.x, m.y, m.yaw, lin=True)
    f.root.add(t + 7.5, V((m.x, m.y, m.yaw + 180.0)), True)
    f.root.add(t + 10.0, V((m.x, m.y, m.yaw + 360.0)))
    f._yaw = m.yaw = m.yaw + 360.0
    pose(m, t + 10.5, P(-0.40, 0.16, 1.16), P(0.40, 0.16, 1.16), 3, 6)
    squat(m, t + 13.5, 0.10, 0.3)
    stand_up(m, t + 14.1, 0.5)
    pose(m, t + 14.6, P(-0.34, 0.26, 1.32), P(0.34, 0.26, 1.32), 3, 2)
    t += 14.8
    return finish(m, t, t_bow, "levitation", 35)


# --- The floating table -----------------------------------------------------------------
TT_H = 0.74                                         # table top over the floor
kit("MTable", "MCloth")


@mesh
def _table_mesh(Pt):
    # Both bones sit at the middle of the table top; everything hangs from there.
    Pt.seg("MTable", (0, 0, -0.03), (0, 0, 0.0), 0.27, 0.27, "5a3418", segs=16)
    Pt.seg("MTable", (0, 0, -TT_H), (0, 0, -0.03), 0.02, 0.02, "1c1c1e", segs=6)
    for k in range(3):
        a = 2 * math.pi * k / 3
        Pt.seg("MTable", (0, 0, -TT_H + 0.02), (0.20 * math.cos(a), 0.20 * math.sin(a), -TT_H), 0.012, 0.012,
               "1c1c1e", segs=5)
    Pt.seg("MCloth", (0, 0, 0.002), (0, 0, 0.012), 0.33, 0.33, "f2ece0", segs=18)
    Pt.seg("MCloth", (0, 0, -0.30), (0, 0, 0.004), 0.42, 0.33, "f2ece0", segs=18, caps=False)
    Pt.seg("MCloth", (0, 0, -0.31), (0, 0, -0.29), 0.425, 0.425, "c8202e", segs=18, caps=False)


def tue_table(m, t, t_bow):
    """The floating table: out of the trunk comes a little round table (too big
    for it); a cloth over it; his fingertips on the cloth and it rises, tilts,
    tugs him across the stage and back, floats on its own while he walks round
    under it, comes to rest; the cloth whipped off: just a table. It floats
    back into the trunk."""
    f = m.f
    t = begin(m, t)
    t = to_trunk(m, t)
    fw = CF._fwd_xy(CF.FIN_FACE)
    rt = V((fw.y, -fw.x, 0))
    spot = V((CF.FIN_SPOT[0] + 0.55 * fw.x, CF.FIN_SPOT[1] + 0.55 * fw.y, 0.0))
    spot.z = floor_z(spot.x, spot.y) + TT_H
    tr = trunk_point(0.0, 0.10)
    # Out of the trunk: lifted up and out, set down on his mark.
    out = Keys()
    out.add(t + 1.0, tr + V((0, 0, -0.30))).add(t + 2.4, tr + V((0, 0, 0.55))).add(t + 4.6, spot)
    m.prop("MTable", t + 1.0, ("wkeys", out, DF.qyaw(CF.FIN_FACE)), 0)
    m.scale("MTable", t + 1.0, 0.001, t + 2.4, 1.0)
    path0 = lambda tt: np.array([tuple(RF.track(out, x)) for x in tt])
    out.done()
    f.L.hold(t).add(t + 1.0, f.at_world(tr + V((-0.20, 0, 0)))).add(t + 2.4, follow(f, path0, V((-0.26, 0, 0.02))))
    f.R.hold(t).add(t + 1.0, f.at_world(tr + V((0.20, 0, 0)))).add(t + 2.4, follow(f, path0, V((0.26, 0, 0.02))))
    f.lean.hold(t).add(t + 1.0, 34).add(t + 2.4, 10)
    f.L.add(t + 4.6, follow(f, path0, -rt * 0.26 + V((0, 0, 0.02))))
    f.R.add(t + 4.6, follow(f, path0, rt * 0.26 + V((0, 0, 0.02))))
    m.slide(t + 2.4, (spot.x - 0.42 * fw.x, spot.y - 0.42 * fw.y), 2.2, CF.FIN_FACE)
    pose(m, t + 5.4, HR["L"], HR["R"], 3, 20)
    t += 5.6
    # The cloth, out of his pocket (a big square of it), over the table.
    t = produce(m, t, "MCloth", "R", up=P(0.20, 0.30, 1.30), at=P(0.10, 0.40, 1.40), off=(0, 0, -0.20))
    m.prop("MCloth", t + 1.8, ("spot", spot.copy(), DF.qyaw(CF.FIN_FACE)), 10)
    pose(m, t + 1.8, P(-0.20, 0.46, 1.10), P(0.20, 0.46, 1.10), 18, 22)
    t += 2.2
    # It floats: a path over and round the stage (world), its tilt swaying.
    pts = [spot, spot + V((0, 0, 0.10)), spot + V((0, 0, 0.42)), spot + rt * 0.30 + V((0, 0, 0.50)),
           spot - rt * 0.35 + V((0, 0, 0.62)), spot + fw3(fw) * 0.20 + V((0, 0, 0.75)),
           spot - rt * 0.55 + V((0, 0, 0.55)), spot - rt * 0.70 + V((0, 0, 0.62)),
           spot + rt * 0.10 + V((0, 0, 0.70)), spot + rt * 0.60 + V((0, 0, 0.55)), spot + rt * 0.65 + V((0, 0, 0.80)),
           spot + V((0, 0, 0.95)), spot - rt * 0.30 + V((0, 0, 0.90)), spot + V((0, 0, 0.60)), spot + V((0, 0, 0.20)),
           spot]
    dt = 3.4
    path = spline(pts, t, dt)
    t_end = t + dt * (len(pts) - 1)

    def q_path(tt):
        w = np.clip((tt - t) / 2.0, 0, 1) * np.clip((t_end - tt) / 2.0, 0, 1)
        tilt = 9.0 * np.sin(1.3 * (tt - t)) * w
        roll = 7.0 * np.sin(0.9 * (tt - t) + 1.0) * w
        return DF.qmul(DF.qyaw(np.full(len(tt), CF.FIN_FACE)), DF.qmul(_qaxis((1, 0, 0), tilt), _qaxis((0, 1, 0), roll)))
    keys = Keys()                                   # (the same path for the cloth: sampled as keys)
    tts = np.arange(t, t_end + 0.01, 0.25)
    for tt, p in zip(tts, path(tts)):
        keys.add(tt, V(tuple(p)), lin=True)
    for n in ("MTable", "MCloth"):
        m.prop(n, t, ("wkeys", keys, q_path), 0)
    # His fingertips on the cloth at first; it pulls him along; he lets go and
    # walks round under it; hands on again to bring it down.
    hold_spans = [(t, t + 4 * dt), (t_end - 3 * dt, t_end)]
    for a, b in hold_spans:
        DF.hold_live(f.L, a - 1.4)
        DF.hold_live(f.R, a - 1.4)
        f.L.add(a, follow(f, path, -rt * 0.30 + V((0, 0, 0.03)))).add(b, follow(f, path, -rt * 0.30 + V((0, 0, 0.03))))
        f.R.add(a, follow(f, path, rt * 0.30 + V((0, 0, 0.03)))).add(b, follow(f, path, rt * 0.30 + V((0, 0, 0.03))))
    # His feet follow it while he holds on (he is pulled), then a walk round.
    for k in range(5):
        tt = t + k * dt
        p = path(np.array([tt]))[0]
        m.slide(tt, (p[0] - 0.42 * fw.x, p[1] - 0.42 * fw.y), dt * 0.9, CF.FIN_FACE)
    t_free = t + 4 * dt + 1.4
    pose(m, t_free, HR["L"], HR["R"], 3, -20)
    circle = [(CF.FIN_SPOT[0] + 0.55 * math.cos(a), CF.FIN_SPOT[1] + 0.55 * math.sin(a))
              for a in np.linspace(0, 2 * math.pi, 7)]
    tt = t_free + 0.5
    for k, xy in enumerate(circle):
        m.slide(tt, xy, 1.6)
        m.look_at(tt + 1.6, (spot.x, spot.y))
        f.pitch.add(tt + 1.6, -26)
        tt += 1.9
    f.yaw.add(tt, 0)
    p = path(np.array([t_end - 3 * dt]))[0]
    m.slide(tt, (p[0] - 0.42 * fw.x, p[1] - 0.42 * fw.y), max(0.8, t_end - 3 * dt - 0.6 - tt), CF.FIN_FACE)
    for k in range(1, 4):
        tt = t_end - (3 - k) * dt
        p = path(np.array([tt]))[0]
        m.slide(tt - dt, (p[0] - 0.42 * fw.x, p[1] - 0.42 * fw.y), dt * 0.9, CF.FIN_FACE)
    t = t_end
    m.x, m.y = spot.x - 0.42 * fw.x, spot.y - 0.42 * fw.y
    # The cloth whipped off and gone.
    pose(m, t + 0.6, P(-0.12, 0.46, 1.04), P(0.12, 0.46, 1.04), 20, 24)
    pose(m, t + 1.4, P(-0.30, 0.24, 1.60), P(0.30, 0.24, 1.60), 2, -4)
    m.prop("MCloth", t + 0.7, ("hand", "R", np.array((0.0, 0.0, -0.20)), Q_ID), 6)
    m.scale("MCloth", t + 1.2, 1.0, t + 1.5, 0.001)
    m.prop("MCloth", t + 1.55, ("hide",), 0)
    m.prop("MTable", t, ("spot", spot.copy(), DF.qyaw(CF.FIN_FACE)), 0)
    t += 2.2
    # Bow; the table floats back into the trunk behind him.
    back = Keys()
    back.add(t, spot.copy()).add(t + 2.5, spot + V((0, 0, 0.5))).add(t + 5.0, tr + V((0, 0, 0.5)))
    back.add(t + 6.0, tr + V((0, 0, -0.2)))
    m.prop("MTable", t, ("wkeys", back, DF.qyaw(CF.FIN_FACE)), 0)
    m.scale("MTable", t + 5.2, 1.0, t + 6.0, 0.001)
    m.prop("MTable", t + 6.1, ("hide",), 0)
    m.look_at(t + 1.0, (tr.x, tr.y))
    f.yaw.add(t + 6.0, 0)
    t = centre(m, t + 0.2)
    return finish(m, t, t_bow, "floating table")


def fw3(fw):
    return V((fw.x, fw.y, 0.0))


# --- Cards into the crowd ----------------------------------------------------------------
def tue_cards(m, t, t_bow):
    """A fan of cards out of the air; flicked out one at a time, spinning, far
    over the heads of the audience; one comes back like a boomerang and he
    catches it; the last sent up, caught behind his back. Gone."""
    f = m.f
    t = begin(m, t)
    t = centre(m, t)
    f.R.add(t + 0.8, P(0.20, 0.38, 1.40))
    m.prop("Fan", t + 0.9, ("hand", "R", np.array((0.0, 0.0, 0.03)), Q_ID), 0)
    m.scale("Fan", t + 0.9, 0.001, t + 1.2, 1.0)
    f.yaw.add(t + 1.4, 30).add(t + 2.6, -30).add(t + 3.4, 0)
    t += 3.6
    m.prop("Fan", t, ("hand", "L", np.array((0.0, 0.0, 0.03)), Q_ID), 6)
    pose(m, t, P(-0.18, 0.34, 1.30), P(0.10, 0.36, 1.32))
    fw = CF._fwd_xy(m.yaw)
    rt = V((fw.y, -fw.x, 0))
    base = V((m.x, m.y, floor_z(m.x, m.y)))
    targets = [base + fw3(fw) * d + rt * s + V((0, 0, -0.30)) for d, s in
               ((2.4, -1.2), (3.0, 0.2), (2.6, 1.3), (3.4, -0.4), (2.2, 0.9), (3.6, 1.0))]
    rng = random.Random("cards")
    for i, tgt in enumerate(targets):
        tgt.z = max(RF.CARPET + 0.02, tgt.z)
        ts = t + 1.1
        pose(m, ts - 0.55, R=P(-0.06, 0.36, 1.32), twist=10)
        pose(m, ts, R=P(0.30, 0.48, 1.38), twist=-12)
        m.prop(f"Card{i}", ts - 0.55, ("hand", "R", np.array((0, 0, 0.03)), Q_ID), 0)
        T = 0.9 + 0.12 * (tgt - base).length
        q_down = DF.qmul(DF.qyaw(rng.uniform(0, 360)), DF.qx(90.0))
        m.prop(f"Card{i}", ts, ("throw", "R", ts, tgt, ts + T, "card", 6, q_down), 0)
        m.scale(f"Card{i}", ts + T + 2.0, 1.0, ts + T + 2.6, 0.001)
        m.prop(f"Card{i}", ts + T + 2.7, ("hide",), 0)
        m.look_at(ts + 0.2, (tgt.x, tgt.y))
        t = ts + 1.4
    f.yaw.add(t, 0)
    pose(m, t, R=P(0.20, 0.34, 1.20), twist=0)
    # The boomerang: out in a long curve and back to his hand.
    ts = t + 1.2
    pose(m, ts - 0.55, R=P(-0.06, 0.36, 1.32))
    pose(m, ts, R=P(0.30, 0.48, 1.38))
    m.prop("Card6", ts - 0.55, ("hand", "R", np.array((0, 0, 0.03)), Q_ID), 0)
    loop = [base + V((0, 0, 1.36)) + fw3(fw) * 0.45 + rt * 0.25, base + fw3(fw) * 1.6 + rt * 0.9 + V((0, 0, 1.9)),
            base + fw3(fw) * 2.6 + V((0, 0, 2.2)), base + fw3(fw) * 1.6 - rt * 0.9 + V((0, 0, 1.9)),
            base + fw3(fw) * 0.45 + rt * 0.20 + V((0, 0, 1.40))]
    bpath = spline(loop, ts, 0.55)
    keys = Keys()
    for tt in np.arange(ts, ts + 2.2 + 0.01, 0.1):
        keys.add(tt, V(tuple(bpath(np.array([tt]))[0])), lin=True)
    m.prop("Card6", ts, ("wkeys", keys, lambda tt: DF.qmul(DF.qyaw(720.0 * (tt - ts)), DF.qx(np.full(len(tt), 80.0)))), 0)
    pose(m, ts + 2.0, R=P(0.24, 0.44, 1.40), pitch=-6)
    m.prop("Card6", ts + 2.2, ("hand", "R", np.array((0, 0, 0.03)), Q_ID), 4)
    f.yaw.add(ts + 0.4, 20).add(ts + 1.2, 0).add(ts + 1.8, -10).add(ts + 2.4, 0)
    t = ts + 2.8
    pose(m, t + 0.6, R=P(0.30, 0.30, 1.50), pitch=-14)
    pose(m, t + 1.4, R=P(0.10, 0.20, 1.20), pitch=4)
    t = vanish(m, t + 1.4, "Card6")
    t = vanish(m, t, "Fan", "L")
    t = ready(m, t)
    return finish(m, t, t_bow, "cards", 35)


# --- The linking rings -------------------------------------------------------------------
RING_R = 0.15
RINGS = ("Ring0", "Ring1", "Ring2", "Ring3")
kit(*RINGS)


@mesh
def _ring_mesh(Pt):
    n = 24
    for name in RINGS:
        for k in range(n):
            a0, a1 = 2 * math.pi * k / n, 2 * math.pi * (k + 1) / n
            Pt.seg(name, (RING_R * math.cos(a0), RING_R * math.sin(a0), 0), (RING_R * math.cos(a1), RING_R * math.sin(a1), 0),
                   0.007, 0.007, "dfe3e8", segs=6, caps=False)


class RingSet:
    """Each ring at each moment: held (a hand: the ring above the palm, facing
    the room), or hanging from another ring (through it, at right angles,
    swinging), or gone. Rings ride on their parents' poses."""

    def __init__(self):
        self.ev = {r: [(0.0, "hide", None)] for r in RINGS}

    def held(self, t, ring, side, lift=0.0):
        self.ev[ring].append((t, "hand", (side, lift)))

    def hang(self, t, ring, parent):
        self.ev[ring].append((t, "hang", parent))

    def pose(self, ring, fis, C, depth=0):
        def evalf(mode, arg, fs, t0):
            qb = C["qb"][fs]
            if mode == "hand":
                side, lift = arg
                return (C["palm"][side][fs] + DF.qrot(qb, (0.0, 0.0, RING_R + 0.01 + lift)),
                        DF.qmul(qb, DF.qx(-90.0)), np.zeros(len(fs)))
            pp, pq = self.pose(arg, fs, C, depth + 1)
            bottom = pp + DF.qrot(pq, np.tile((0.0, -RING_R, 0.0), (len(fs), 1)))
            tt = fs / FPS
            sway = 10.0 * np.sin(2.6 * (tt - t0)) * np.exp(-0.5 * np.maximum(0.0, tt - t0))
            qh = DF.qmul(qb, DF.qmul(DF.qyaw(90.0), DF.qx(-90.0)))           # at right angles to the room
            qh = DF.qmul(_qaxis(DF.qrot(qb, (0, 1, 0))[0], sway), qh)
            return bottom - np.outer(np.ones(len(fs)), (0.0, 0.0, RING_R - 0.012)), qh, np.zeros(len(fs))
        Pn, Q, _x, shown = run_events(self.ev[ring], fis, evalf)
        self._shown = shown
        return Pn, Q

    def fn(self, ring):
        def fn(fis, C):
            Pn, Q = self.pose(ring, fis, C)
            return Pn, Q, np.where(self._shown, 1.0, 0.001)
        return fn


def tue_rings(m, t, t_bow):
    """The linking rings: four steel rings out of the trunk, shown one by one
    (struck together: solid); two pass through each other and hang linked,
    swing, come apart; a chain of three held up high; all four linked and
    shaken loose again, and the last two, linked, drawn apart by a breath."""
    f = m.f
    rs = RingSet()
    t = begin(m, t)
    t = to_trunk(m, t)
    for r in RINGS:
        m.prop(r, t, ("fn", rs.fn(r)), 0)
    f.L.hold(t).add(t + 1.0, f.at_world(trunk_point(-0.10)))
    t = take(m, t, "R", [], dx=0.08)
    for k, r in enumerate(RINGS):
        rs.held(t - 1.0, r, "R" if k < 2 else "L", 0.012 * k)
    m.hold["L"] = m.hold["R"] = "rings"
    t = centre(m, t)
    up = {"L": P(-0.24, 0.36, 1.28), "R": P(0.24, 0.36, 1.28)}
    hi = {"L": P(-0.24, 0.30, 1.62), "R": P(0.24, 0.30, 1.62)}
    pose(m, t + 0.8, up["L"], up["R"], 4, 4)
    t += 1.0
    # One by one, shown: struck together, a clang.
    for k in range(2):
        pose(m, t + 0.6, P(-0.06, 0.38, 1.30), P(0.06, 0.38, 1.30))
        pose(m, t + 0.8, P(-0.10, 0.38, 1.30), P(0.10, 0.38, 1.30))
        pose(m, t + 1.0, P(-0.06, 0.38, 1.30), P(0.06, 0.38, 1.30))
        pose(m, t + 1.8, up["L"], up["R"])
        f.yaw.add(t + 1.0, 25 * (1 - 2 * k)).add(t + 2.4, 0)
        t += 2.6
    # Linked: Ring1 through Ring0 (both in his right hand), it drops and hangs.
    def link(t, child, parent, hand_parent, hand_child):
        kc = f.R if hand_child == "R" else f.L
        kp = f.R if hand_parent == "R" else f.L
        sx = 1 if hand_parent == "R" else -1
        kp.add(t + 0.6, P(sx * 0.10, 0.40, 1.42))
        kc.add(t + 0.6, P(-sx * 0.04, 0.40, 1.50)).add(t + 1.2, P(sx * 0.02, 0.40, 1.34))
        rs.hang(t + 1.2, child, parent)
        kc.add(t + 1.8, up[hand_child])
        kp.add(t + 1.8, hi[hand_parent])
        f.pitch.add(t + 0.6, 10).add(t + 1.8, -6)
        return t + 2.4

    def unlink(t, child, side):
        k = f.R if side == "R" else f.L
        sx = 1 if side == "R" else -1
        k.add(t + 0.6, P(sx * 0.12, 0.40, 1.24)).add(t + 1.0, P(sx * 0.12, 0.40, 1.24))
        rs.held(t + 1.0, child, side)
        k.add(t + 1.8, up[side])
        return t + 2.2
    rs.held(t, "Ring1", "L")
    rs.held(t, "Ring2", "L", 0.012)
    rs.held(t, "Ring3", "L", 0.024)
    t = link(t, "Ring1", "Ring0", "R", "L")
    for k in (0, 1):                                    # shown to each side, swinging
        t = CF._side(m, t, "pub", k)
        pose(m, t + 1.0, R=hi["R"] + P(0, 0, 0.06))
        t += 2.6
    t = CF._side(m, t, "pub", None)
    t = unlink(t, "Ring1", "L")
    pose(m, t + 0.6, R=up["R"])
    t += 1.0
    # A chain of three, raised high.
    t = link(t, "Ring1", "Ring0", "R", "L")
    t = link(t, "Ring2", "Ring1", "R", "L")
    pose(m, t + 1.2, R=P(0.10, 0.22, 1.96), pitch=-24)
    f.lean.add(t + 1.2, -4)
    t += 4.0
    pose(m, t + 1.0, R=hi["R"], pitch=4, lean=3)
    t += 1.4
    # All four, then shaken loose: they fall apart into his hands.
    t = link(t, "Ring3", "Ring2", "R", "L")
    pose(m, t + 1.0, R=P(0.12, 0.24, 2.00), pitch=-20)
    t += 3.0
    for k in range(3):                                  # the shake
        pose(m, t + 0.25, R=P(0.16, 0.24, 2.02))
        pose(m, t + 0.5, R=P(0.08, 0.24, 1.96))
        t += 0.5
    for k, r in enumerate(("Ring3", "Ring2", "Ring1")):
        rs.held(t + 0.3 + 0.25 * k, r, "L", 0.012 * k)
    pose(m, t + 0.4, L=P(-0.10, 0.40, 1.20))
    pose(m, t + 1.6, up["L"], up["R"], 3, 4)
    t += 2.2
    # Two linked again, and drawn apart by a breath.
    t = link(t, "Ring1", "Ring0", "R", "L")
    pose(m, t + 0.8, L=P(-0.06, 0.40, 1.22))
    rs.held(t + 1.0, "Ring1", "L")
    pose(m, t + 1.4, L=P(-0.04, 0.36, 1.42), R=P(0.04, 0.36, 1.50), pitch=6)
    f.pitch.add(t + 2.2, 12).add(t + 2.8, 2)
    pose(m, t + 3.2, up["L"], up["R"])
    t += 3.6
    t = CF._land(m, centre(m, t), t_bow - 9.0, "rings") if t < t_bow - 14.0 else t
    t = to_trunk(m, t)
    t = stow(m, t, "R", [])
    for r in RINGS:
        m.scale(r, t - 1.1, 1.0, t - 0.8, 0.001)
        rs.ev[r].append((t - 0.75, "hide", None))
    m.hold["L"] = None
    pose(m, t, L=HR["L"])
    return finish(m, t, t_bow, "linking rings")


# --- Torn and restored paper ------------------------------------------------------------------
kit("Paper", "PaperH0", "PaperH1", "Wad", "PCone")


@mesh
def _paper_mesh(Pt):
    def sheet(name, w, h):
        CF._rbox(Pt, name, Matrix.Translation(V((0, 0, h / 2))), (w, 0.002, h), "ecebe2")
        for k in range(5):                              # (print: dark lines)
            CF._rbox(Pt, name, Matrix.Translation(V((0, -0.0015, h * (0.18 + 0.15 * k)))), (w * 0.8, 0.0006, 0.012),
                     "4a4a4a")
    sheet("Paper", 0.46, 0.34)
    sheet("PaperH0", 0.23, 0.34)
    sheet("PaperH1", 0.23, 0.34)
    Pt.ball("Wad", (0, 0, 0.04), 0.045, "ecebe2", segs=7, rings=5)
    Pt.seg("PCone", (0, 0, 0), (0, 0, 0.28), 0.015, 0.10, "ecebe2", segs=12, caps=False)


Q_SHOW = DF.qx(0.0)                                   # a sheet held up facing the room (its plane x/z)


def tue_paper(m, t, t_bow):
    """The torn and restored paper: a newspaper out of his coat, shown front and
    back, torn in half, the halves together and torn again, and again,
    squeezed into a little wad; a puff on his fist, and it opens out whole."""
    f = m.f
    t = begin(m, t)
    t = centre(m, t)
    pose(m, t + 0.8, R=P(0.04, 0.20, 1.30), lean=3)            # into his coat
    m.prop("Paper", t + 0.9, ("hand", "R", np.array((0.0, 0.0, 0.0)), Q_SHOW), 0)
    m.scale("Paper", t + 0.9, 0.001, t + 1.1, 1.0)
    pose(m, t + 1.8, P(-0.21, 0.40, 1.36), P(0.21, 0.40, 1.36), 4, 6)
    m.prop("Paper", t + 1.8, ("hand", "R", np.array((-0.21, 0.0, 0.0)), Q_SHOW), 6)
    t += 2.2
    for k in range(2):                                  # front and back
        f.yaw.add(t + 0.6, 0)
        pose(m, t + 1.0, P(-0.21, 0.40, 1.36), P(0.21, 0.40, 1.36))
        t += 1.4
    # Torn: the halves apart.
    for k in range(3):
        pose(m, t + 0.4, P(-0.06, 0.40, 1.36), P(0.06, 0.40, 1.36), pitch=10)
        pose(m, t + 1.0, P(-0.22, 0.40, 1.30), P(0.22, 0.40, 1.42))
        if k == 0:
            m.prop("Paper", t + 0.6, ("hide",), 0)
        m.prop("PaperH0", t + 0.6, ("hand", "L", np.array((0.115 * 0.0, 0, 0)), Q_SHOW), 0)
        m.prop("PaperH1", t + 0.6, ("hand", "R", np.array((0.0, 0, 0)), Q_SHOW), 0)
        sc = 1.0 / (2 ** k)
        m.scale("PaperH0", t + 0.6, sc, t + 0.62, sc)
        m.scale("PaperH1", t + 0.6, sc, t + 0.62, sc)
        pose(m, t + 1.6, P(-0.04, 0.40, 1.36), P(0.04, 0.40, 1.36))          # together again
        m.prop("PaperH1", t + 1.6, ("hand", "L", np.array((0.0, -0.004, 0)), Q_SHOW), 4)
        t += 1.9
    # Squeezed into a wad.
    pose(m, t + 0.8, P(-0.03, 0.38, 1.30), P(0.03, 0.38, 1.32), pitch=12)
    for n in ("PaperH0", "PaperH1"):
        m.scale(n, t + 0.6, 0.25, t + 1.0, 0.001)
        m.prop(n, t + 1.05, ("hide",), 0)
    m.prop("Wad", t + 0.9, ("hand", "L", np.array((0, 0, 0)), Q_ID), 0)
    m.scale("Wad", t + 0.9, 0.001, t + 1.1, 1.0)
    pose(m, t + 1.6, L=P(-0.04, 0.34, 1.40), R=P(0.20, 0.30, 1.20), pitch=4)
    f.lean.add(t + 2.2, 8).add(t + 2.8, 3)                  # a puff on his fist
    f.pitch.add(t + 2.2, 14).add(t + 2.8, 2)
    t += 3.0
    m.scale("Wad", t + 0.3, 1.0, t + 0.5, 0.001)
    m.prop("Wad", t + 0.55, ("hide",), 0)
    m.prop("Paper", t + 0.4, ("hand", "R", np.array((-0.21, 0.0, 0.0)), Q_SHOW), 0)
    m.scale("Paper", t + 0.4, 0.2, t + 1.0, 1.0)
    pose(m, t + 1.0, P(-0.21, 0.40, 1.40), P(0.21, 0.40, 1.40), pitch=-4)
    m.hold["R"] = "paper"
    t += 1.8
    return finish(m, t, t_bow, "torn paper", 35)


def tue_cone(m, t):
    """The gift (Tuesday): the paper rolled into a cone, flowers pushed up out
    of the empty cone, plucked out; the cone crumpled and gone."""
    f = m.f
    t = centre(m, t)
    pose(m, t + 0.8, P(-0.10, 0.40, 1.30), P(0.10, 0.40, 1.30), pitch=10)
    m.scale("Paper", t + 0.8, 1.0, t + 1.6, 0.001)
    m.prop("Paper", t + 1.65, ("hide",), 0)
    m.prop("PCone", t + 0.9, ("hand", "L", np.array((0, 0, -0.04)), Q_ID), 0)
    m.scale("PCone", t + 0.9, 0.001, t + 1.6, 1.0)
    t += 2.0
    for k in range(2):                                  # shown empty: tipped, looked into
        pose(m, t + 0.6, L=P(-0.10, 0.44, 1.46), pitch=-6)
        pose(m, t + 1.4, L=P(-0.10, 0.40, 1.30), pitch=8)
        f.yaw.add(t + 0.8, 20 - 40 * k).add(t + 1.6, 0)
        t += 1.8
    # Filled from an invisible jug, swirled, sniffed: something's growing.
    pose(m, t + 0.8, R=P(0.10, 0.36, 1.62), pitch=-4)
    for k in range(3):
        pose(m, t + 1.4 + 0.8 * k, R=P(0.02, 0.38, 1.56))
        pose(m, t + 1.8 + 0.8 * k, R=P(0.06, 0.38, 1.60))
    pose(m, t + 4.2, R=P(0.24, 0.30, 1.20), L=P(-0.10, 0.42, 1.32))
    for k in range(4):
        pose(m, t + 4.6 + 0.5 * k, L=P(-0.14 + 0.04 * (k % 2), 0.42, 1.32))
    pose(m, t + 7.0, L=P(-0.06, 0.30, 1.50), pitch=-10)          # a sniff
    pose(m, t + 8.4, L=P(-0.10, 0.40, 1.30), pitch=8, yaw=20)
    f.yaw.add(t + 9.4, -20).add(t + 10.4, 0)
    t += 10.6
    # Waved over: blooms rise out of it.
    for k in range(3):
        pose(m, t + 0.4, R=P(0.02, 0.42, 1.52))
        pose(m, t + 0.8, R=P(0.14, 0.42, 1.48))
        t += 0.8
    m.prop("Bouquet", t, ("hand", "L", np.array((0, 0, 0.10)), Q_ID), 0)
    m.scale("Bouquet", t, 0.001, t + 1.2, 1.0)
    pose(m, t + 1.6, R=P(-0.06, 0.42, 1.44))
    m.prop("Bouquet", t + 1.7, ("hand", "R", np.array((0, 0, 0.02)), Q_ID), 6)
    pose(m, t + 2.6, P(-0.10, 0.36, 1.18), CF.GIFT_HOLD)
    m.scale("PCone", t + 2.4, 1.0, t + 2.8, 0.001)
    m.prop("PCone", t + 2.85, ("hide",), 0)
    m.hold["R"] = "bouquet"
    return t + 3.0


# --- The doves -----------------------------------------------------------------------------
DOVES = ("Dove0", "Dove1", "Dove2", "Dove3")
kit(*DOVES, *[f"{d}W{s}" for d in DOVES for s in "LR"], "DSilk")
PELMET = [V((x, RF.STAGE_POLY[0][1] - 0.10, 2.99)) for x in (-3.15, -2.70, -2.20, -1.70)]


@mesh
def _dove_mesh(Pt):
    for d in DOVES:
        Pt.ball(d, (0, 0, 0), 0.05, "f6f6f4", scale=(0.75, 1.6, 0.8), segs=10, rings=6)
        Pt.ball(d, (0, 0.085, 0.035), 0.028, "f6f6f4", segs=8, rings=5)
        Pt.seg(d, (0, 0.105, 0.035), (0, 0.125, 0.030), 0.006, 0.002, "e8a040", segs=5)
        Pt.seg(d, (0, -0.06, 0.0), (0, -0.13, 0.01), 0.022, 0.035, "f2f2f0", segs=6, squash=0.3)
        for s, sx in (("L", -1), ("R", 1)):
            CF._rbox(Pt, f"{d}W{s}", Matrix.Translation(V((sx * 0.06, -0.01, 0.0))), (0.12, 0.08, 0.008), "f2f2f0")
    CF._rbox(Pt, "DSilk", Matrix(), (0.45, 0.003, 0.45), "c81e2e")


class Dove:
    """A dove: perched (in his hand, on a world spot) with its wings folded,
    or flying a smooth world path with its wings beating."""

    def __init__(self, name):
        self.name = name
        self.ev = [(0.0, "hide", None)]

    def perch_hand(self, t, side, off=(0.0, 0.0, 0.05)):
        self.ev.append((t, "hand", (side, off)))

    def perch(self, t, w, yaw):
        self.ev.append((t, "spot", (V(w), yaw)))

    def fly(self, t, points, dt):
        self.ev.append((t, "fly", (spline(points, t, dt), len(points), dt)))

    def body(self, fis, C):
        def evalf(mode, arg, fs, t0):
            n = len(fs)
            if mode == "hand":
                side, off = arg
                qb = C["qb"][fs]
                return C["palm"][side][fs] + DF.qrot(qb, np.array(off, float)), qb, np.zeros(n)
            if mode == "body":                          # (on his shoulder: his frame)
                qb = C["qb"][fs]
                return C["pos"][fs] + DF.qrot(qb, np.array(arg, float)), qb, np.zeros(n)
            if mode == "spot":
                w, yaw = arg
                return np.tile(np.array(tuple(w)), (n, 1)), DF.qyaw(np.full(n, yaw)), np.zeros(n)
            if mode == "walk":                          # (along his arm: his frame, keyed)
                qb = C["qb"][fs]
                arg.done()
                loc = np.array([tuple(RF.track(arg, x)) for x in fs / FPS], float)
                return C["pos"][fs] + DF.qrot(qb, loc), DF.qmul(qb, DF.qyaw(-90.0)), np.zeros(n)
            path, k, dt = arg
            tp = fs / FPS
            v = path(tp + 0.05) - path(tp - 0.05)
            yaw = np.degrees(np.arctan2(-v[:, 0], v[:, 1] + 1e-9))
            pitch = np.degrees(np.arctan2(v[:, 2], np.linalg.norm(v[:, :2], axis=1) + 1e-6))
            return path(tp), DF.qmul(DF.qyaw(yaw), DF.qx(np.clip(pitch, -35, 35))), np.ones(n)
        Pn, Q, flap, shown = run_events(self.ev, fis, evalf)
        return Pn, Q, flap

    def shown(self, fis):
        tt = fis / FPS
        out = np.zeros(len(fis), bool)
        ev = sorted(self.ev, key=lambda e: e[0])
        for j, (t0, mode, arg) in enumerate(ev):
            t1 = ev[j + 1][0] if j + 1 < len(ev) else 1e9
            if mode != "hide":
                out |= (tt >= t0) & (tt < t1)
        return np.where(out, 1.0, 0.001)

    def fn_body(self):
        def fn(fis, C):
            Pn, Q, flap = self.body(fis, C)
            return Pn, Q, self.shown(fis)
        return fn

    def fn_wing(self, side):
        sx = -1.0 if side == "L" else 1.0

        def fn(fis, C):
            Pn, Q, flap = self.body(fis, C)
            beat = np.where(flap > 0.5, 55.0 * np.sin(2 * np.pi * 3.4 * fis / FPS), 78.0)
            Qw = DF.qmul(Q, _qaxis((0, 1, 0), sx * beat))
            root = Pn + DF.qrot(Q, np.tile((sx * 0.03, 0.0, 0.02), (len(fis), 1)))
            return root, Qw, self.shown(fis)
        return fn


def tue_doves(m, t, t_bow):
    """The finale: the doves. A red silk shaken out over his empty hand: a dove
    sits there; it flies up round the stage and settles on his shoulder. A
    second from under the silk, a third caught out of the air, a fourth from
    the crown of his hat. Then, on a lift of his arms, all four go up over the
    room in great loops under the ceiling, out over the tables and back, two to
    the pelmet over the stage, two to his hands, and he bows among them."""
    f = m.f
    t = begin(m, t)
    t = centre(m, t)
    doves = [Dove(d) for d in DOVES]
    for d in doves:
        m.prop(d.name, t, ("fn", d.fn_body()), 0)
        for s in "LR":
            m.prop(f"{d.name}W{s}", t, ("fn", d.fn_wing(s)), 0)
    fw = CF._fwd_xy(m.yaw)
    F = fw3(fw)
    rt = V((fw.y, -fw.x, 0))
    base = V((m.x, m.y, floor_z(m.x, m.y)))

    def silk_reveal(t, d, side):
        k = f.L if side == "L" else f.R
        o = f.R if side == "L" else f.L
        sx = -1 if side == "L" else 1
        k.add(t + 0.8, P(sx * 0.12, 0.40, 1.28))
        o.add(t + 0.8, P(-sx * 0.02, 0.40, 1.46))
        m.prop("DSilk", t + 0.9, ("hand", OTHER[side], np.array((0, 0, -0.18)), Q_ID), 0)
        m.scale("DSilk", t + 0.9, 0.001, t + 1.2, 1.0)
        o.add(t + 1.6, P(sx * 0.06, 0.42, 1.44)).add(t + 2.2, P(-sx * 0.30, 0.30, 1.50))   # whipped away
        m.scale("DSilk", t + 2.2, 1.0, t + 2.5, 0.001)
        m.prop("DSilk", t + 2.55, ("hide",), 0)
        d.perch_hand(t + 2.0, side)
        m.scale(d.name, t + 1.9, 0.001, t + 2.2, 1.0)
        for s in "LR":
            m.scale(f"{d.name}W{s}", t + 1.9, 0.001, t + 2.2, 1.0)
        f.pitch.add(t + 2.4, 18)
        return t + 3.0

    def fly_to_shoulder(t, d, side, loop):
        k = f.L if side == "L" else f.R
        sx = -1 if side == "L" else 1
        k.add(t + 0.5, P(sx * 0.20, 0.36, 1.60))           # tossed up
        start = None
        pts = [base + V((sx * 0.20 * rt.x + 0.36 * F.x, sx * 0.20 * rt.y + 0.36 * F.y, 1.75))] + loop + \
              [base + rt * (sx * 0.17) + V((0, 0, 1.55))]
        d.fly(t + 0.6, pts, 0.9)
        t_land = t + 0.6 + 0.9 * (len(pts) - 1)
        d.ev.append((t_land, "body", (sx * -0.17, 0.0, 1.50)))
        k.add(t + 1.4, HR[side].copy())
        m.look_at(t + 1.0, (pts[2].x, pts[2].y))
        f.pitch.add(t + 1.0, -26).add(t_land, 4)
        f.yaw.add(t_land, 30 * sx)
        return t_land

    # The first: from under the silk, up round the stage, onto his right shoulder.
    t = silk_reveal(t, doves[0], "L")
    loop0 = [base + F * 0.9 + rt * 0.8 + V((0, 0, 2.35)), base + F * 1.3 + V((0, 0, 2.45)),
             base + F * 0.9 - rt * 0.9 + V((0, 0, 2.35)), base - rt * 0.4 + F * 0.2 + V((0, 0, 2.15))]
    t_land = fly_to_shoulder(t, doves[0], "L", loop0)
    t = t_land + 0.6
    # The second: silk again, over the right hand; it flies up to the pelmet.
    t = silk_reveal(t, doves[1], "R")
    pose(m, t + 0.5, R=P(0.20, 0.36, 1.62))
    p1 = [base + rt * 0.20 + F * 0.36 + V((0, 0, 1.75)), base + F * 1.1 + rt * 0.6 + V((0, 0, 2.4)),
          base + F * 0.6 - rt * 0.4 + V((0, 0, 2.5)), PELMET[3]]
    doves[1].fly(t + 0.6, p1, 0.9)
    doves[1].perch(t + 0.6 + 0.9 * 3, PELMET[3], m.yaw + 180.0)
    pose(m, t + 1.4, R=HR["R"])
    m.look_at(t + 1.2, (PELMET[3].x, PELMET[3].y))
    f.pitch.add(t + 1.2, -30).add(t + 3.6, 4)
    t += 3.8
    f.yaw.add(t, 0)
    # The third: caught out of the air in his left.
    pose(m, t + 0.8, L=P(-0.26, 0.30, 1.86), pitch=-24)
    doves[2].perch_hand(t + 1.0, "L")
    m.scale(doves[2].name, t + 0.9, 0.001, t + 1.1, 1.0)
    for s_ in "LR":
        m.scale(f"{doves[2].name}W{s_}", t + 0.9, 0.001, t + 1.1, 1.0)
    pose(m, t + 1.8, L=P(-0.24, 0.36, 1.30), pitch=4)
    t += 2.4
    # The fourth: from the crown of his hat.
    pose(m, t + 0.8, R=P(0.10, 0.10, 1.95))
    doves[3].perch_hand(t + 1.0, "R", (0.0, 0.0, 0.05))
    for n in [doves[3].name] + [f"{doves[3].name}W{s_}" for s_ in "LR"]:
        m.scale(n, t + 0.9, 0.001, t + 1.2, 1.0)
    pose(m, t + 2.0, R=P(0.30, 0.34, 1.40), pitch=0)
    t += 3.0
    # The tour: one at a time out over the room to the tables (Jay's, the café
    # couple's, the blonde lady's), a moment there, and back.
    tables = [V((RF.BOOTH_TABLES[k][0] + dx, RF.BOOTH_TABLES[k][1] - 0.20, RF.TABLE_Z + 0.01))
              for k, dx in (("JT", -0.05), ("CT", 0.0), ("TT", 0.05))]
    hand_at = {"L": lambda: base + rt * -0.30 + F * 0.32 + V((0, 0, 1.36)),
               "R": lambda: base + rt * 0.30 + F * 0.32 + V((0, 0, 1.36))}
    where = {1: ("pelmet", PELMET[3]), 2: ("hand", "L"), 3: ("hand", "R")}
    for wave in range(2):
        for i, tab in zip((1, 2, 3), tables if wave == 0 else list(reversed(tables))):
            d = doves[i]
            kind, arg = where[i]
            p0 = arg if kind == "pelmet" else hand_at[arg]()
            if kind == "hand":
                k = f.L if arg == "L" else f.R
                sx = -1 if arg == "L" else 1
                k.add(t + 0.5, P(sx * 0.26, 0.30, 1.66)).add(t + 1.3, P(sx * 0.30, 0.34, 1.36))
            mid = (p0 + tab) * 0.5 + V((0, 0, 1.0))
            mid.z = min(mid.z, 2.40)
            d.fly(t + 0.6, [p0, mid, tab + V((0, 0, 0.35)), tab], 1.1)
            d.perch(t + 0.6 + 3.3, tab, heading((tab.x, tab.y), (base.x, base.y)))
            m.look_at(t + 1.0, (tab.x, tab.y))
            f.pitch.add(t + 1.0, -10).add(t + 3.6, 8)
            pose(m, t + 3.4, P(-0.40, 0.24, 1.40), P(0.40, 0.24, 1.40))       # a gesture: there!
            t += 4.6
        t += 2.0
        for i, tab in zip((1, 2, 3), tables if wave == 0 else list(reversed(tables))):
            d = doves[i]
            kind, arg = where[i]
            dest = arg if kind == "pelmet" else hand_at[arg]()
            if kind == "hand":
                k = f.L if arg == "L" else f.R
                sx = -1 if arg == "L" else 1
                k.add(t + 2.4, P(sx * 0.30, 0.34, 1.36))
            mid = (tab + dest) * 0.5 + V((0, 0, 1.1))
            mid.z = min(mid.z, 2.40)
            d.fly(t, [tab, tab + V((0, 0, 0.4)), mid, dest], 1.0)
            if kind == "pelmet":
                d.perch(t + 3.0, dest, m.yaw + 180.0)
            else:
                d.perch_hand(t + 3.0, arg)
            t += 2.2
        f.yaw.add(t, 0)
        t += 2.4
    # The one on his shoulder walks down his arm to his hand and back.
    pose(m, t + 1.0, R=P(0.55, 0.16, 1.40))
    walk = Keys()
    for k, p in enumerate(((0.17, 0.0, 1.50), (0.30, 0.06, 1.47), (0.45, 0.12, 1.45), (0.55, 0.16, 1.44))):
        walk.add(t + 1.2 + 0.9 * k, P(*p))
    for k, p in enumerate(((0.45, 0.12, 1.45), (0.30, 0.06, 1.47), (0.17, 0.0, 1.50))):
        walk.add(t + 5.0 + 0.9 * k, P(*p))
    doves[0].ev.append((t + 1.2, "walk", walk))
    doves[0].ev.append((t + 7.0, "body", (0.17, 0.0, 1.50)))
    pose(m, t + 7.4, R=P(0.30, 0.34, 1.36))
    t += 7.8
    # Up they all go: loops over the room, two to the pelmet, two to his hands.
    pose(m, t + 1.0, P(-0.40, 0.20, 1.90), P(0.40, 0.20, 1.90), 2, -30)
    t_go = t + 1.1
    plans = []
    for i, d in enumerate(doves):
        sgn = 1 if i % 2 == 0 else -1
        pts = [base + V((0, 0, 1.9)) + rt * (0.3 * sgn)]
        for k in range(3):
            a = 2 * math.pi * (k / 3.0) + i * 0.8
            pts.append(base + F * (2.6 + 1.2 * math.cos(a)) + rt * (1.8 * math.sin(a) * sgn) + V((0, 0, 2.35 + 0.15 * (k % 2))))
        if i < 2:
            pts += [base + F * 1.0 + V((0, 0, 2.45)), PELMET[i] if i == 0 else PELMET[3]]
        else:
            side = "L" if i == 2 else "R"
            pts += [base + F * 1.2 + V((0, 0, 2.3)), base + F * 0.30 + rt * (0.42 if side == "R" else -0.42) + V((0, 0, 1.75))]
        dt = 1.3 + 0.08 * i
        d.fly(t_go + 0.25 * i, pts, dt)
        t_end = t_go + 0.25 * i + dt * (len(pts) - 1)
        if i < 2:
            d.perch(t_end, pts[-1], m.yaw + 180.0)
        else:
            d.perch_hand(t_end, "L" if i == 2 else "R")
        plans.append(t_end)
    m.look_at(t_go + 1.0, (base.x + F.x * 2.5, base.y + F.y * 2.5))
    f.pitch.add(t_go + 1.0, -34)
    for k in range(5):
        f.yaw.add(t_go + 2.0 + 2.0 * k, 35 * math.sin(k * 1.4))
    t_back = max(plans[2], plans[3])
    pose(m, t_back - 1.2, P(-0.42, 0.30, 1.75), P(0.42, 0.30, 1.75), 2, -8)
    pose(m, t_back + 2.0, P(-0.40, 0.30, 1.40), P(0.40, 0.30, 1.40), 3, 4, 0)
    t = t_back + 2.4
    m.doves = doves
    return finish(m, t, t_bow, "doves", 50, hat=False)


def tue_tidy(m, t):
    """The doves off his hands to the pelmet with the others; at the lights up
    all four fly off behind the drapes."""
    f = m.f
    doves = m.doves
    pose(m, t + 0.8, P(-0.30, 0.26, 1.80), P(0.30, 0.26, 1.80), 2, -20)
    base = V((m.x, m.y, floor_z(m.x, m.y)))
    for i, d in enumerate(doves[2:]):
        to = PELMET[1 + i]
        d.fly(t + 1.0 + 0.3 * i, [base + V((0, 0, 1.95)), (base + to) * 0.5 + V((0, 0, 0.9)), to], 1.0)
        d.perch(t + 3.0 + 0.3 * i, to, m.yaw + 180.0)
    pose(m, t + 2.4, HR["L"], HR["R"], 3, -10)
    t += 3.6
    for i, d in enumerate(doves):                       # off behind the drapes, gone
        p0 = PELMET[0 if i == 0 else 3 if i == 1 else i - 1]
        d.fly(t + 0.4 * i, [p0, p0 + V((0, 0.25, 0.05)), p0 + V((0, 0.55, 0.0))], 0.8)
        for n in [d.name] + [f"{d.name}W{s}" for s in "LR"]:
            m.scale(n, t + 0.4 * i + 1.2, 1.0, t + 0.4 * i + 1.6, 0.001)
            m.prop(n, t + 0.4 * i + 1.7, ("hide",), 0)
    return t + 2.0



# =====================================================================================
# WEDNESDAY: jugglers
# =====================================================================================
def wed_chase(m, t, t_bow):
    """Opener: the spotlight wanders off him. He tiptoes after it; it jumps
    away to the other side; he runs; it jumps again; he stamps, points at his
    feet, and the spot creeps back to him, sheepish."""
    f = m.f
    t = begin(m, t)
    fw = CF._fwd_xy(m.yaw)
    rt = V((fw.y, -fw.x, 0))
    c = V((CF.FIN_SPOT[0], CF.FIN_SPOT[1], 0.0))
    spots = [c - rt * 0.75, c + rt * 0.70 + fw3(fw) * 0.10, c - rt * 0.30 + fw3(fw) * 0.35, c + rt * 0.45 - fw3(fw) * 0.30]
    m.spot_at.add(t, c.copy())
    m.spot_free.add(t, 0.0).add(t + 0.8, 1.0)
    m.spot_at.add(t + 0.8, spots[0])
    pose(m, t + 0.8, P(-0.10, 0.12, 0.98), P(0.10, 0.12, 0.98), 3, 10)
    m.look_at(t + 1.2, (spots[0].x, spots[0].y))
    t += 1.8
    for k, sp in enumerate(spots):
        dur = 2.2 if k == 0 else 1.2                    # (tiptoe first, then a dash)
        tgt = sp
        m.slide(t, (tgt.x, tgt.y), dur)
        if k == 0:
            pose(m, t + 0.6, P(-0.20, 0.10, 1.20), P(0.20, 0.10, 1.30), 10, 4)
            for q in range(3):
                f.fL.add(t + 0.3 + 0.7 * q, P(-0.10, 0.10, 0.16)).add(t + 0.65 + 0.7 * q, V(STAND[0]))
        else:
            pose(m, t + 0.4, P(-0.28, 0.30, 1.30), P(0.28, -0.10, 1.10), 14, 0)
        nxt = spots[k + 1] if k + 1 < len(spots) else None
        if nxt is not None:
            m.spot_at.add(t + dur - 0.1, sp).add(t + dur + 0.35, nxt)   # it jumps as he arrives
            m.look_at(t + dur + 0.3, (nxt.x, nxt.y))
            pose(m, t + dur + 0.3, P(-0.24, 0.20, 1.50), P(0.24, 0.20, 1.50), 2, -4)   # throws up his hands
        t += dur + 0.9
    # He stamps, points at his feet: it comes.
    f.fR.add(t + 0.3, P(0.10, 0.10, 0.25)).add(t + 0.55, V(STAND[1]))
    pose(m, t + 0.6, R=P(0.20, 0.30, 0.80), lean=18, pitch=30)
    m.spot_at.add(t + 1.2, m.spot_at[-1][1]).add(t + 3.2, V((m.x, m.y, 0.0)))
    m.spot_free.add(t + 3.2, 1.0).add(t + 3.6, 0.0)
    pose(m, t + 3.6, P(-0.30, 0.30, 1.40), P(0.30, 0.30, 1.40), 3, -2)
    f.yaw.add(t + 3.6, 0)
    t += 4.0
    return finish(m, t, t_bow, "runaway spotlight", 30)


# --- Cigar boxes -------------------------------------------------------------------------------
BOXES = ("Box0", "Box1", "Box2")
BOX = (0.20, 0.09, 0.07)
kit(*BOXES)


@mesh
def _box_mesh(Pt):
    for name, col in zip(BOXES, ("c8282e", "f2c430", "2a5ad8")):
        CF._rbox(Pt, name, Matrix(), BOX, col)
        for sx in (-1, 1):
            CF._rbox(Pt, name, Matrix.Translation(V((sx * (BOX[0] / 2 - 0.006), 0, 0))), (0.014, BOX[1] + 0.004, BOX[2] + 0.004), "1c1c1e")


class Boxes:
    """Three cigar boxes in a row across his front: the outer two in his hands
    (by their ends), the middle one squeezed between them; tossed up (spun or
    not) and caught between them again."""

    def __init__(self):
        self.tosses = []                                # (t0, t1, turns)

    def ends(self, fis, C):
        qb = C["qb"][fis]
        PL, PR = C["palm"]["L"][fis], C["palm"]["R"][fis]
        d = PR - PL
        d /= np.maximum(1e-6, np.linalg.norm(d, axis=1, keepdims=True))
        return PL, PR, d, qb

    def fn_outer(self, side):
        def fn(fis, C):
            PL, PR, d, qb = self.ends(fis, C)
            p = (PL + d * (BOX[0] / 2 + 0.005)) if side == "L" else (PR - d * (BOX[0] / 2 + 0.005))
            return p, qb
        return fn

    def fn_middle(self):
        def fn(fis, C):
            PL, PR, d, qb = self.ends(fis, C)
            mid = 0.5 * (PL + PR)
            Q = qb.copy()
            tt = fis / FPS
            for t0, t1, turns in self.tosses:
                sel = (tt >= t0) & (tt < t1)
                if not sel.any():
                    continue
                f0, f1 = C["fi"](t0), C["fi"](t1)
                a = 0.5 * (C["palm"]["L"][f0] + C["palm"]["R"][f0])
                b = 0.5 * (C["palm"]["L"][f1] + C["palm"]["R"][f1])
                T = t1 - t0
                u = (tt[sel] - t0) / T
                mid[sel] = a + np.outer(u, b - a) + np.outer(0.5 * G * T * T * u * (1 - u), (0, 0, 1))
                Q[sel] = DF.qmul(qb[sel], DF.qx(360.0 * turns * u))
            return mid, Q
        return fn


BOX_HOLD = {"L": P(-0.25, 0.36, 1.18), "R": P(0.25, 0.36, 1.18)}


def _box_toss(m, bx, t, T, turns=0, clap=True):
    """The middle one up; the outer two clapped together under it and apart."""
    pose(m, t - 0.4, BOX_HOLD["L"] + P(0, 0, -0.06), BOX_HOLD["R"] + P(0, 0, -0.06))
    pose(m, t, BOX_HOLD["L"] + P(0, 0, 0.04), BOX_HOLD["R"] + P(0, 0, 0.04))
    bx.tosses.append((t, t + T, turns))
    if clap and T > 0.6:
        pose(m, t + T * 0.5, P(-0.17, 0.36, 1.20), P(0.17, 0.36, 1.20))
    pose(m, t + T - 0.05, BOX_HOLD["L"], BOX_HOLD["R"])
    m.f.pitch.add(t + 0.1, -10).add(t + T, 6)
    return t + T + 0.35


def wed_boxes(m, t, t_bow):
    """Cigar boxes: three painted boxes out of the trunk, held end to end; the
    middle one popped up and caught between the others, over and over, faster;
    turned over in the air; tossed up high with a turn underneath; the outer
    two traded behind it; a last pop up, caught, bow."""
    f = m.f
    t = begin(m, t)
    t = to_trunk(m, t)
    bx = Boxes()
    st = {"Box0": ("fn", bx.fn_outer("L")), "Box1": ("fn", bx.fn_middle()), "Box2": ("fn", bx.fn_outer("R"))}
    f.L.hold(t).add(t + 1.0, f.at_world(trunk_point(-0.10)))
    t = take(m, t, "R", list(BOXES), lambda n: st[n])
    pose(m, t + 0.8, BOX_HOLD["L"], BOX_HOLD["R"])
    t += 0.8
    m.hold["L"] = m.hold["R"] = "boxes"
    t = centre(m, t)
    pose(m, t + 0.6, BOX_HOLD["L"], BOX_HOLD["R"], 6, 14)
    t += 1.0
    for k in range(6):                                  # pops, quickening
        t = _box_toss(m, bx, t + 0.5 - 0.05 * k, 0.70 - 0.03 * k)
    for k in range(4):                                  # turnovers
        t = _box_toss(m, bx, t + 0.5, 0.78, turns=1)
    for k in (0, 1):
        t = CF._side(m, t, "pub", k)
        for q in range(3):
            t = _box_toss(m, bx, t + 0.4, 0.66)
        t = _box_toss(m, bx, t + 0.4, 0.85, turns=1)
    t = CF._side(m, t, "pub", None)
    # High, with a turn under it.
    tt = t + 0.6
    t = _box_toss(m, bx, tt, 1.0, clap=False)
    f.put(tt + 0.15, m.x, m.y, m.yaw, lin=True)
    f.root.add(tt + 0.55, V((m.x, m.y, m.yaw + 180.0)), True)
    f.root.add(tt + 0.95, V((m.x, m.y, m.yaw + 360.0)))
    f._yaw = m.yaw = m.yaw + 360.0
    while t < t_bow - 2.4 - 12.0:                       # the fill: pops and turnovers
        t = _box_toss(m, bx, t + 0.45, 0.70)
        t = _box_toss(m, bx, t + 0.45, 0.80, turns=1)
    t = _box_toss(m, bx, t + 0.5, 1.0, turns=2, clap=False)
    t = to_trunk(m, t + 0.3)
    t = stow(m, t, "R", list(BOXES))
    m.hold["L"] = None
    pose(m, t, L=HR["L"])
    return finish(m, t, t_bow, "cigar boxes")


# --- Five balls -------------------------------------------------------------------------------
kit("Ball3", "Ball4")
FIVE = ("Ball0", "Ball1", "Ball2", "Ball3", "Ball4")


@mesh
def _ball_mesh(Pt):
    Pt.ball("Ball3", (0, 0, 0), CF.BALL_R, "2ab84a", segs=10, rings=6)
    Pt.ball("Ball4", (0, 0, 0), CF.BALL_R, "f2f2ee", segs=10, rings=6)


def cascade_k(m, names, t0, n, b, d=0.14, start_side="R"):
    """A cascade of len(names) balls (any odd number): throws alternate hands
    every b s, each caught by the other hand len(names)*b - d later."""
    f = m.f
    k = len(names)
    IN, OUT = CF.JUG["ball"]
    OUT = {sd: IN[sd] + 0.65 * (OUT[sd] - IN[sd]) for sd in OUT}      # (a tight, quick pattern)
    for i in range(n):
        o = names[i % k]
        side = start_side if i % 2 == 0 else OTHER[start_side]
        tt = t0 + i * b
        tc = tt + k * b - d
        m.prop(o, tt, ("fly", side, tt, OTHER[side], tc, "ball", 0), 0)
        m.prop(o, tc, CF.hand_state("ball", OTHER[side], 0), 0)
    for side, first in ((start_side, 0), (OTHER[start_side], 1)):
        keys = f.L if side == "L" else f.R
        DF.hold_live(keys, t0 - 0.4)
        i = first
        while i < n + k:
            tt = t0 + i * b
            if i < n:
                if i > 0:
                    keys.add(tt - d, OUT[side].copy())
                keys.add(tt, IN[side].copy())
            elif i >= k:
                keys.add(tt - d, OUT[side].copy())
            i += 2
    return t0 + (n + k - 1) * b


def wed_five(m, t, t_bow):
    """Five balls: three out of his pockets and two more out of his hat; three,
    then all five in a fast cascade, a run to each side, all five sent up in a
    flash and caught; back in his pockets."""
    f = m.f
    t = begin(m, t)
    t = centre(m, t)
    t = m.appear_balls(t)
    f.pitch.add(t, 12)
    t = CF.cascade(m, "ball", t + 0.2, 15, 0.30) + 0.3
    # Two more from his hat (one in each hand, on top of what they hold).
    pose(m, t + 0.8, P(-0.10, 0.10, 1.92), P(0.10, 0.10, 1.92), pitch=-6)
    m.prop("Ball3", t + 0.9, CF.hand_state("ball", "L", 1), 0)
    m.prop("Ball4", t + 0.9, CF.hand_state("ball", "R", 2), 0)
    m.scale("Ball3", t + 0.9, 0.001, t + 1.0, 1.0)
    m.scale("Ball4", t + 0.9, 0.001, t + 1.0, 1.0)
    IN, OUT = CF.JUG["ball"]
    pose(m, t + 1.8, OUT["L"], OUT["R"], pitch=14)
    t += 2.2
    for k in range(3):
        t = cascade_k(m, FIVE, t + 0.3, 25, 0.21) + 0.4
        if k < 2:
            t = CF._side(m, t, "pub", k)
    t = CF._side(m, t, "pub", None)
    # The flash: all five up, a clap, caught.
    t = cascade_k(m, FIVE, t + 0.3, 5, 0.18, d=-0.05) + 0.2
    pose(m, t + 0.6, P(-0.06, 0.34, 1.30), P(0.06, 0.34, 1.30))
    t += 1.0
    for n_ in FIVE:
        m.prop(n_, t, ("hide",), 0)
    m.holding["ball"] = {}
    m.hold["L"] = m.hold["R"] = None
    pose(m, t + 0.8, CF.POCKET["L"], CF.POCKET["R"], pitch=4)
    t = ready(m, t + 1.0)
    return finish(m, t, t_bow, "five balls", 35)


# --- Devil sticks -------------------------------------------------------------------------------
DEV_L = 0.62
HAND_STICK = 0.44
kit("DevC", "DevL", "DevR", "DevFA", "DevFB")


@mesh
def _devil_mesh(Pt):
    Pt.seg("DevC", (0, 0, -DEV_L / 2), (0, 0, DEV_L / 2), 0.016, 0.016, "f4f2ea", segs=8)
    for sz in (-1, 1):
        Pt.seg("DevC", (0, 0, sz * DEV_L / 2 * 0.55), (0, 0, sz * DEV_L / 2), 0.024, 0.026, "d8283a", segs=8)
        Pt.seg("DevC", (0, 0, sz * (DEV_L / 2 + 0.02)), (0, 0, sz * DEV_L / 2), 0.03, 0.026, "1c1c1e", segs=8)
    for b in ("DevL", "DevR"):
        Pt.seg(b, (0, 0, -0.02), (0, 0, HAND_STICK), 0.012, 0.012, "2a2420", segs=6)
    CF._flame_mesh(Pt, "DevFA", V((0, 0, 0)), 0.85)
    CF._flame_mesh(Pt, "DevFB", V((0, 0, 0)), 0.85)


Q_DSTICK = {"L": DF.qmul(DF.qyaw(28.0), DF.qx(-70.0)), "R": DF.qmul(DF.qyaw(-28.0), DF.qx(-70.0))}


class Devil:
    """The centre stick between the hand sticks' tips: rocking from one to the
    other (tilt keyed, his left/right), or spun like a propeller (rev/s keyed);
    its ends alight or not."""

    def __init__(self):
        self.tilt = Keys().add(0.0, 0.0)
        self.rps = Keys().add(0.0, 0.0)
        self.lit = Keys().add(0.0, 0.0)

    def centre(self, fis, C):
        qb = C["qb"][fis]
        tips = {s: C["palm"][s][fis] + DF.qrot(DF.qmul(qb, Q_DSTICK[s]), (0.0, 0.0, HAND_STICK)) for s in "LR"}
        mid = 0.5 * (tips["L"] + tips["R"]) + np.array((0.0, 0.0, 0.14))
        for k in (self.tilt, self.rps):
            k.done()
        tilt = np.array(DF.sample(self.tilt), float)[fis]
        spin = (np.cumsum(np.array(DF.sample(self.rps), float)) / FPS * 360.0)[fis]
        fwd = DF.qrot(qb, np.tile((0.0, 1.0, 0.0), (len(fis), 1)))
        Q = DF.qmul(_qaxis(fwd[0], tilt + spin) if len(fis) == 1 else
                    np.array([_qaxis(fwd[i], [tilt[i] + spin[i]])[0] for i in range(len(fis))]), qb)
        return mid, Q

    def fn_centre(self):
        def fn(fis, C):
            return self.centre(fis, C)
        return fn

    def fn_flame(self, end):
        def fn(fis, C):
            mid, Q = self.centre(fis, C)
            p = mid + DF.qrot(Q, np.tile((0.0, 0.0, end * (DEV_L / 2 + 0.03)), (len(fis), 1)))
            self.lit.done()
            lit = np.array(DF.sample(self.lit), float)[fis]
            return p, np.tile(Q_ID, (len(fis), 1)), np.maximum(0.001, np.stack([lit, lit, lit * 1.1], 1))
        return fn


DEV_HOLD = {"L": P(-0.20, 0.30, 1.02), "R": P(0.20, 0.30, 1.02)}


def _dev_rock(m, dv, t, n, period=0.62, amp=32.0):
    """Struck from side to side: the centre stick tilts one way, the other."""
    for q in range(n):
        side = "L" if q % 2 == 0 else "R"
        sgn = 1 if side == "L" else -1
        tq = t + q * period
        dv.tilt.add(tq + period * 0.5, sgn * amp)
        hk = DEV_HOLD[side] + P(0, 0.02, 0.10)
        pose(m, tq + period * 0.35, **{side: hk})
        pose(m, tq + period * 0.8, **{side: DEV_HOLD[side]})
    return t + n * period


def wed_devil(m, t, t_bow):
    """Devil sticks: the flower stick and its two hand sticks out of the trunk;
    tapped from side to side, faster; swung in a propeller, spun, caught on
    the tips; then its ends are lit (fire), and it all again blazing, a
    propeller of fire, blown out."""
    f = m.f
    t = begin(m, t)
    t = to_trunk(m, t)
    dv = Devil()
    st = {"DevC": ("fn", dv.fn_centre()), "DevL": ("hand", "L", np.zeros(3), Q_DSTICK["L"]),
          "DevR": ("hand", "R", np.zeros(3), Q_DSTICK["R"]), "DevFA": ("fn", dv.fn_flame(1)), "DevFB": ("fn", dv.fn_flame(-1))}
    f.L.hold(t).add(t + 1.0, f.at_world(trunk_point(-0.10)))
    t = take(m, t, "R", ["DevC", "DevL", "DevR", "DevFA", "DevFB"], lambda n: st[n])
    m.hold["L"] = "kit"
    t = centre(m, t)
    pose(m, t + 0.6, DEV_HOLD["L"], DEV_HOLD["R"], 6, 18)
    t += 1.0

    def routine(t, fire):
        t = _dev_rock(m, dv, t, 14)
        t = _dev_rock(m, dv, t, 14, 0.48, 40)
        # The propeller: spun round on one stick.
        dv.rps.add(t, 0.0).add(t + 1.0, 1.6).add(t + 7.0, 1.6).add(t + 8.0, 0.0)
        pose(m, t + 1.0, P(-0.06, 0.34, 1.10), P(0.24, 0.30, 0.98))
        for q in range(8):
            pose(m, t + 1.4 + 0.7 * q, L=P(-0.06, 0.34, 1.10 + 0.03 * (q % 2)))
        pose(m, t + 7.6, DEV_HOLD["L"], DEV_HOLD["R"])
        dv.tilt.add(t + 8.2, 0.0)
        t += 8.6
        for k in (0, 1):
            t = CF._side(m, t, "pub", k)
            t = _dev_rock(m, dv, t, 10, 0.5, 38)
        t = CF._side(m, t, "pub", None)
        return t

    t = routine(t, False)
    # Lit: each end touched to his fingertip flame.
    pose(m, t + 0.6, P(-0.10, 0.36, 1.20), P(0.10, 0.36, 1.20), 6, 10)
    m.fire.add(t + 0.8, 0.0).add(t + 1.0, 1.0)
    dv.lit.add(t + 1.6, 0.0).add(t + 2.0, 1.0)
    m.fire.add(t + 2.2, 1.0).add(t + 2.4, 0.0)
    pose(m, t + 2.8, DEV_HOLD["L"], DEV_HOLD["R"], 6, 18)
    lights(m, t, 2.0, black=0.6, spot=0.5)
    t += 3.2
    t_rest = t_bow - 2.4 - 9.0
    while t < t_rest - 9.0:
        t = _dev_rock(m, dv, t, 10, 0.5, 38)
        dv.rps.add(t, 0.0).add(t + 0.8, 1.8).add(t + 4.0, 1.8).add(t + 4.8, 0.0)
        pose(m, t + 0.8, P(-0.06, 0.34, 1.10), P(0.24, 0.30, 0.98))
        pose(m, t + 4.6, DEV_HOLD["L"], DEV_HOLD["R"])
        dv.tilt.add(t + 5.2, 0.0)
        t += 5.4
    # Blown out, lights back, into the trunk.
    pose(m, t + 0.8, P(-0.10, 0.40, 1.30), P(0.10, 0.40, 1.30), 10, 10)
    dv.lit.add(t + 1.4, 1.0).add(t + 2.0, 0.0)
    lights(m, t + 1.0, 1.5, black=0.0, spot=1.0)
    t += 2.4
    t = to_trunk(m, t)
    t = stow(m, t, "R", ["DevC", "DevL", "DevR", "DevFA", "DevFB"])
    m.hold["L"] = None
    pose(m, t, L=HR["L"])
    return finish(m, t, t_bow, "devil sticks")


# --- The chair on his chin -------------------------------------------------------------------
kit("BChair")
CHAIR_TILT = 34.0


@mesh
def _chair_mesh(Pt):
    # A bentwood café chair; the bone at the foot of its front left leg.
    o = V((0.17, -0.17, 0.0))
    for lx, ly in ((-0.17, 0.17), (0.17, 0.17), (-0.15, -0.15), (0.15, -0.15)):
        Pt.seg("BChair", o + V((lx, ly, 0.0)), o + V((lx * 0.95, ly * 0.95, 0.45)), 0.012, 0.012, "3a1c10", segs=6)
    Pt.seg("BChair", o + V((0, 0, 0.45)), o + V((0, 0, 0.47)), 0.20, 0.20, "6a3a1e", segs=14)
    for sx in (-1, 1):
        Pt.seg("BChair", o + V((sx * 0.15, -0.15, 0.45)), o + V((sx * 0.14, -0.18, 0.92)), 0.011, 0.011, "3a1c10", segs=6)
    Pt.seg("BChair", o + V((-0.15, -0.18, 0.88)), o + V((0.15, -0.18, 0.88)), 0.011, 0.011, "3a1c10", segs=6)


def wed_chair(m, t, t_bow):
    """A café chair out of the trunk (how?); stood on one leg on his chin, head
    back, arms out, little steps to keep it there as it sways; tipped off,
    caught, set down, and he sits on it, legs crossed, pleased with himself."""
    f = m.f
    t = begin(m, t)
    t = to_trunk(m, t)
    t = take(m, t, "R", ["BChair"], ("hand", "R", np.array((0.0, 0.0, -0.40)), DF.qyaw(90.0)))
    t = centre(m, t)
    # Up onto his chin: the chair's foot on it, tilted so it balances.
    pose(m, t + 1.0, P(-0.10, 0.26, 1.80), P(0.10, 0.26, 1.80), 2, -36)
    chin = Keys()

    def wob(tt):
        return V((0.05 * math.sin(1.7 * tt), 0.04 * math.sin(1.3 * tt + 1.0), 0.0))
    t_on = t + 1.4
    t_off = t + 17.5
    sway = Keys()
    for k in range(int((t_off - t_on) / 0.5) + 1):
        tt = t_on + 0.5 * k
        sway.add(tt, P(0.0, 0.07, 1.62) + wob(tt))
    m.prop("BChair", t_on, ("local", sway, DF.qmul(DF.qyaw(135.0), CF._qy(CHAIR_TILT))), 8)
    pose(m, t_on + 0.6, P(-0.55, 0.12, 1.42), P(0.55, 0.12, 1.42), -6, -40)
    for k in range(8):                                  # little steps under it
        dx = 0.10 * math.sin(1.7 * (t_on + 2.0 * k))
        fw = CF._fwd_xy(m.yaw)
        rt = V((fw.y, -fw.x))
        m.slide(t_on + 1.0 + 2.0 * k, (CF.FIN_SPOT[0] + rt.x * dx, CF.FIN_SPOT[1] + rt.y * dx), 1.4)
        pose(m, t_on + 1.6 + 2.0 * k, P(-0.55, 0.12, 1.42 + 0.08 * math.sin(k)), P(0.55, 0.12, 1.42 - 0.08 * math.sin(k)))
    t = t_off
    m.slide(t - 0.6, CF.FIN_SPOT, 0.5)
    # Tipped off his chin, caught, set down.
    pose(m, t + 0.6, P(-0.16, 0.40, 1.60), P(0.16, 0.40, 1.60), 4, 4)
    m.prop("BChair", t + 0.6, ("hand", "R", np.array((-0.10, 0.0, -0.55)), DF.qyaw(90.0)), 8)
    fw = CF._fwd_xy(m.yaw)
    seat = V((m.x + 0.05 * fw.x, m.y + 0.05 * fw.y, floor_z(m.x, m.y)))
    pose(m, t + 1.6, P(-0.20, 0.36, 0.90), P(0.20, 0.36, 0.90), 30, 30)
    put = V((m.x - 0.30 * fw.x, m.y - 0.30 * fw.y, floor_z(m.x, m.y)))
    m.prop("BChair", t + 1.6, ("spot", put + V((0, 0, 0)), DF.qyaw(m.yaw + 180.0)), 8)
    pose(m, t + 2.2, HR["L"], HR["R"], 3, 4)
    t += 2.4
    # Sits on it, legs crossed, a little wave.
    z0 = floor_z(m.x, m.y)
    m.slide(t, (m.x - 0.12 * fw.x, m.y - 0.12 * fw.y), 0.8)
    for k in (f.zk, f.fL, f.fR):
        k.hold(t + 0.8)
    f.zk.add(t + 1.6, z0 - 0.40)
    f.fL.add(t + 1.6, P(-0.10, 0.42, 0.49))
    f.fR.add(t + 1.6, P(0.06, 0.40, 0.70))
    pose(m, t + 1.6, P(-0.14, 0.30, 0.98), P(0.14, 0.30, 0.98), 4, 4)
    pose(m, t + 2.6, R=P(0.30, 0.20, 1.40))
    pose(m, t + 3.0, R=P(0.36, 0.20, 1.44))
    pose(m, t + 3.4, R=P(0.30, 0.20, 1.40))
    pose(m, t + 4.2, R=P(0.14, 0.30, 0.98))
    t += 5.0
    f.zk.add(t + 0.8, z0)
    f.fL.add(t + 0.8, V(STAND[0]))
    f.fR.add(t + 0.8, V(STAND[1]))
    m.slide(t + 0.8, CF.FIN_SPOT, 0.6)
    t += 1.6
    # Picked up, and back into the trunk (it shouldn't fit).
    t = turn_to(m, t, m.yaw + 180.0)
    pose(m, t + 1.0, R=f.at_world(put + V((0.0, 0.0, 0.80))), lean=30, pitch=26)
    m.prop("BChair", t + 1.1, ("hand", "R", np.array((0.0, 0.0, -0.40)), DF.qyaw(90.0)), 8)
    pose(m, t + 2.0, R=CARRY["R"], lean=3, pitch=3)
    t = to_trunk(m, t + 2.2)
    t = stow(m, t, "R", ["BChair"])
    return finish(m, t, t_bow, "chair balance", 35)


def wed_flowers(m, t):
    """The gift (Wednesday): three balls juggled, all sent up high: what comes
    down into his hand is a bouquet."""
    f = m.f
    t = centre(m, t)
    t = m.appear_balls(t)
    f.pitch.add(t, 12)
    t = CF.cascade(m, "ball", t + 0.2, 36, 0.30) + 0.3
    t = CF.cascade(m, "ball", t + 0.2, 15, 0.40, style="high") + 0.3
    t0 = t + 0.3
    t = CF.flash(m, "ball", t0, T=0.9, b=0.2, pirouette=False)
    for i in range(3):                                  # gone at the top
        m.scale(CF.NAMES["ball"][i], t0 + 0.2 * i + 0.40, 1.0, t0 + 0.2 * i + 0.50, 0.001)
        m.prop(CF.NAMES["ball"][i], t0 + 0.2 * i + 0.55, ("hide",), 0)
    m.holding["ball"] = {}
    m.hold["L"] = m.hold["R"] = None
    pose(m, t + 0.8, R=P(0.18, 0.40, 1.50), pitch=-20)
    m.prop("Bouquet", t + 0.9, ("hand", "R", np.array((0.0, 0.0, 0.02)), Q_ID), 0)
    m.scale("Bouquet", t + 0.9, 0.001, t + 1.05, 1.0)
    pose(m, t + 2.0, L=HR["L"], R=CF.GIFT_HOLD, pitch=4)
    m.hold["R"] = "bouquet"
    return t + 2.2


# --- Spinning plates -----------------------------------------------------------------------------
PLATES = ("Plate0", "Plate1", "Plate2", "Plate3", "Plate4")
POLE_X = (-3.02, -2.76, -2.50, -2.24, -1.98)
POLE_Y = -10.36
POLE_TOP = RF.STAGE_TOP + 1.12
kit("PStand", *PLATES)


@mesh
def _plates_mesh(Pt):
    # The stand: a low bench with five poles (the bone at the stage floor middle).
    xs = [x - 0.5 * (POLE_X[0] + POLE_X[-1]) for x in POLE_X]
    CF._rbox(Pt, "PStand", Matrix.Translation(V((0, 0, 0.10))), (xs[-1] - xs[0] + 0.24, 0.20, 0.06), "6a3a1e")
    for sx in (xs[0] - 0.08, xs[-1] + 0.08):
        CF._rbox(Pt, "PStand", Matrix.Translation(V((sx, 0, 0.035))), (0.05, 0.18, 0.07), "3a1c10")
    for x in xs:
        Pt.seg("PStand", (x, 0, 0.12), (x, 0, POLE_TOP - RF.STAGE_TOP), 0.006, 0.004, "c8ccd2", segs=5)
    for name, col in zip(PLATES, ("c8282e", "2a5ad8", "f2c430", "2ab84a", "8a2ab8")):
        Pt.seg(name, (0, 0, 0), (0, 0, 0.012), 0.06, 0.13, "f4f2ea", segs=16)
        Pt.seg(name, (0, 0, 0.012), (0, 0, 0.016), 0.13, 0.135, col, segs=16)
        CF._rbox(Pt, name, Matrix.Translation(V((0.08, 0, 0.015))), (0.07, 0.02, 0.004), col)    # (a stripe)


class Plates:
    """Each plate on its pole: spinning (rev/s keyed), and the slower it goes the
    more it wobbles (a precessing tilt)."""

    def __init__(self):
        self.rps = {p: Keys().add(0.0, 0.0) for p in PLATES}

    def fn(self, i):
        name = PLATES[i]
        tip = np.array((POLE_X[i], POLE_Y, POLE_TOP))

        def fn(fis, C):
            k = self.rps[name]
            k.done()
            rps = np.array(DF.sample(k), float)
            spin = (np.cumsum(rps) / FPS * 360.0)[fis]
            r = rps[fis]
            wob = np.clip(20.0 - 7.0 * r, 2.0, 20.0)
            prec = spin * 0.35
            axis = np.stack([np.cos(np.radians(prec)), np.sin(np.radians(prec)), np.zeros(len(fis))], 1)
            Qt = np.array([_qaxis(axis[j], [wob[j]])[0] for j in range(len(fis))])
            return np.tile(tip, (len(fis), 1)), DF.qmul(Qt, _qaxis((0, 0, 1), spin))
        return fn


def wed_plates(m, t, t_bow):
    """The finale: spinning plates. The stand of five poles brought out; a stack
    of plates out of the trunk; each set spinning on a pole in turn (a twirl of
    the wrist under it), and as the first ones slow and wobble he runs back
    to spin them up again, along the row and back; all five going, he juggles
    a little in front of them; then he takes them down one by one, still
    spinning, onto a stack in his arms."""
    f = m.f
    t = begin(m, t)
    stand_at = V((0.5 * (POLE_X[0] + POLE_X[-1]), POLE_Y, RF.STAGE_TOP))
    m.prop("PStand", t, ("spot", stand_at, Q_ID), 0)
    m.scale("PStand", t, 0.001, t + 1.0, 1.0)
    pl = Plates()
    t = to_trunk(m, t + 0.6)
    t = take(m, t, "L", list(PLATES), lambda n: ("hand", "L", np.array((0.0, 0.0, 0.02 + 0.016 * PLATES.index(n))), Q_ID))
    m.hold["L"] = "plates"
    def at_pole(i):
        return (POLE_X[i], POLE_Y - 0.42)

    def spin_up(t, i, first=False):
        """To pole i, (the plate onto it), a twirl of the wrist under it."""
        t = CF._step_to(m, t, at_pole(i), 0.0, dur=None)
        tip = V((POLE_X[i], POLE_Y, POLE_TOP))
        if first:
            pose(m, t + 0.7, R=f.at_world(V((stand_at.x, stand_at.y - 0.6, 1.4)) * 0.0 + tip + V((0, -0.04, 0.02))))
            m.prop(PLATES[i], t + 0.8, ("fn", pl.fn(i)), 6)
        for q in range(4):                              # the twirl
            a = math.pi * q / 2
            f.R.add(t + 0.9 + 0.3 * q, f.at_world(tip + V((0.05 * math.cos(a), -0.05 + 0.05 * math.sin(a), -0.06))))
        pl.rps[PLATES[i]].add(t + 0.9, pl_rate(i, t + 0.9)).add(t + 2.1, 3.0)
        f.R.add(t + 2.6, P(0.20, 0.30, 1.10))
        f.pitch.add(t + 0.6, -24).add(t + 2.4, -10)
        return t + 2.6

    def pl_rate(i, tt):
        k = pl.rps[PLATES[i]]
        k.done()
        return RF.track(k, tt)

    def decay(i, t0, t1):
        pl.rps[PLATES[i]].add(t0, 3.0).add(t1, 0.9)
    t_last = {}
    for i in range(5):                                  # set them going, one by one
        t = spin_up(t, i, first=True)
        t_last[i] = t
        decay(i, t, t + 16.0)
        pl.rps[PLATES[i]].add(t + 16.0, 0.9)
    m.hold["L"] = None
    pose(m, t, L=HR["L"])
    # Back along the row to whichever is wobbling most.
    order = [0, 1, 0, 2, 3, 1, 4, 2, 0, 3, 4, 1, 2, 0, 3]
    t_end = t_bow - 2.4 - 26.0
    q = 0
    while t < t_end:
        i = order[q % len(order)]
        q += 1
        k = pl.rps[PLATES[i]]
        k[:] = [kv for kv in k if kv[0] <= t]
        k.add(t, max(0.9, 3.0 - (t - t_last[i]) * 0.13))
        t = spin_up(t, i)
        t_last[i] = t
        k.add(t + 16.0, 0.9)
        m.look_at(t, (POLE_X[order[q % len(order)]], POLE_Y))
    # Down, one by one, onto a stack on his left arm.
    for i in range(5):
        t = CF._step_to(m, t, at_pole(i), 0.0)
        tip = V((POLE_X[i], POLE_Y, POLE_TOP))
        f.R.add(t + 0.8, f.at_world(tip + V((0, -0.02, 0.04))))
        k = pl.rps[PLATES[i]]
        k[:] = [kv for kv in k if kv[0] <= t]
        k.add(t, 2.0).add(t + 0.9, 0.0)
        m.prop(PLATES[i], t + 0.9, ("hand", "R", np.array((0.0, 0.0, 0.02)), Q_ID), 6)
        f.R.add(t + 1.7, P(0.0, 0.34, 1.16))
        f.L.add(t + 1.4, P(-0.04, 0.34, 1.10))
        m.prop(PLATES[i], t + 1.8, ("hand", "L", np.array((0.0, 0.0, 0.02 + 0.016 * i)), Q_ID), 6)
        t += 2.2
    m.hold["L"] = "plates"
    t = centre(m, t)
    pose(m, t + 0.6, P(-0.10, 0.36, 1.20), P(0.30, 0.30, 1.50), 3, 0)
    m.plates_on = True
    return finish(m, t + 1.0, t_bow, "spinning plates", 50, hat=False)


def wed_tidy(m, t):
    t = to_trunk(m, t)
    t = stow(m, t, "L", list(PLATES))
    m.scale("PStand", t, 1.0, t + 0.8, 0.001)
    m.prop("PStand", t + 0.85, ("hide",), 0)
    return CF._back(m, t, 0.8)



# =====================================================================================
# THURSDAY: the clown
# =====================================================================================
kit("WKey")


@mesh
def _key_mesh(Pt):
    Pt.seg("WKey", (0, 0, 0), (0, -0.07, 0), 0.008, 0.008, "c8a040", segs=6)
    for sx in (-1, 1):
        CF._rbox(Pt, "WKey", Matrix.Translation(V((sx * 0.045, -0.08, 0))), (0.07, 0.012, 0.05), "c8a040")


class Spinner:
    """A part of him that turns (the wind-up key): in his frame at off, spun
    about his back-front axis at rps (keyed)."""

    def __init__(self, off):
        self.off = off
        self.rps = Keys().add(0.0, 0.0)

    def fn(self):
        def fn(fis, C):
            self.rps.done()
            ang = (np.cumsum(np.array(DF.sample(self.rps), float)) / FPS * 360.0)[fis]
            qb = C["qb"][fis]
            return (C["pos"][fis] + DF.qrot(qb, np.tile(self.off, (len(fis), 1))),
                    DF.qmul(qb, _qaxis((0, 1, 0), ang)))
        return fn


def thu_windup(m, t, t_bow):
    """Opener: a clockwork toy. A key in his back turns and he jerks into life:
    stiff little steps, arms pumping, head clicking round; he runs down, slower,
    stuck mid-step; reaches round, winds himself up, and off again."""
    f = m.f
    t = begin(m, t)
    key = Spinner(np.array((0.0, -0.13, 1.22)))
    m.prop("WKey", t, ("fn", key.fn()), 0)
    m.scale("WKey", t, 0.001, t + 0.4, 1.0)
    pose(m, t + 0.6, lean=2, pitch=2, yaw=0)
    key.rps.add(t + 0.6, 0.0).add(t + 1.0, 1.2).add(t + 2.4, 1.2).add(t + 2.8, 0.3)
    pose(m, t + 1.2, P(-0.20, 0.20, 1.02), P(0.20, 0.20, 1.02))

    def tick(t, n, rate, rng=None):
        fw = CF._fwd_xy(m.yaw)
        for q in range(n):
            side = 1 if q % 2 == 0 else -1
            d = 0.07 * rate
            tt = t + q * (0.45 / rate)
            foot = f.fR if side > 0 else f.fL
            foot.add(tt, V(STAND[1] if side > 0 else STAND[0])).add(tt + 0.2 / rate, P(side * 0.10, 0.12, 0.20))
            foot.add(tt + 0.4 / rate, V(STAND[1] if side > 0 else STAND[0]))
            pose(m, tt + 0.2 / rate, P(-0.20, 0.20 + 0.10 * side, 1.02 + 0.06 * side), P(0.20, 0.20 - 0.10 * side, 1.02 - 0.06 * side))
            f.yaw.add(tt + 0.2 / rate, 25 * side * (q % 3 == 0)).add(tt + 0.35 / rate, 25 * side * (q % 3 == 0))
            m.slide(tt, (m.x + d * fw.x, m.y + d * fw.y), 0.4 / rate)
        return t + n * 0.45 / rate
    t = tick(t + 2.4, 8, 1.0)
    key.rps.add(t, 0.3).add(t + 3.0, 0.0)
    t = tick(t, 3, 0.7)
    t = tick(t, 2, 0.45)
    pose(m, t + 0.3, lean=8, pitch=12)                  # stuck
    t += 1.4
    pose(m, t + 0.9, R=P(0.02, -0.16, 1.20), lean=4)     # winds himself
    key.rps.add(t + 1.0, 0.0).add(t + 1.3, -1.0).add(t + 3.1, -1.0).add(t + 3.4, 0.0)
    for q in range(4):
        pose(m, t + 1.3 + 0.45 * q, R=P(0.05, -0.15, 1.23))
        pose(m, t + 1.5 + 0.45 * q, R=P(0.00, -0.17, 1.20))
    pose(m, t + 3.6, P(-0.30, 0.30, 1.40), P(0.30, 0.30, 1.40), 3, -4)
    m.scale("WKey", t + 3.8, 1.0, t + 4.1, 0.001)
    m.prop("WKey", t + 4.2, ("hide",), 0)
    t = centre(m, t + 4.0)
    return finish(m, t, t_bow, "wind-up toy", 30)


# --- Knife throwing ------------------------------------------------------------------------------
TKNIVES = tuple(f"TKnife{i}" for i in range(6))
BALLOONS = tuple(f"Bal{i}" for i in range(5))
BAL_COL = ("d8283a", "f2c430", "2a6ad8", "2ab84a", "e86a20")
BOARD_R = 0.42
kit("TBoard", *TKNIVES, *BALLOONS)
BOARD_AT = V((-3.38, -10.62, RF.STAGE_TOP + 1.25))     # its face's centre, facing east-ish
BOARD_YAW = -96.0                                      # (its +y, the face normal, toward the thrower)
THROW_AT = (-1.92, -10.94)


@mesh
def _board_mesh(Pt):
    # The bone at the centre of the face (the face is the xz plane at y 0, facing +y).
    for k, (r, col) in enumerate(((BOARD_R, "f4f2ea"), (0.32, "c8282e"), (0.22, "f4f2ea"), (0.12, "c8282e"), (0.04, "1c1c1e"))):
        Pt.seg("TBoard", (0, -0.03 + 0.002 * k, 0), (0, 0.002 * k, 0), r, r, col, segs=24)
    Pt.seg("TBoard", (0, -0.06, -1.20 + RF.STAGE_TOP * 0), (0, -0.06, -BOARD_R), 0.025, 0.025, "3a1c10", segs=6)
    for sx in (-1, 1):
        Pt.seg("TBoard", (0, -0.06, -1.25), (sx * 0.30, -0.25, -1.25), 0.02, 0.02, "3a1c10", segs=5)
    for i in range(6):
        b = f"TKnife{i}"
        Pt.seg(b, (0, 0, -0.10), (0, 0, 0.02), 0.012, 0.014, "161616", segs=8)
        CF._rbox(Pt, b, Matrix.Translation(V((0, 0, 0.12))), (0.026, 0.004, 0.19), "dfe3e8")
    for b, col in zip(BALLOONS, BAL_COL):
        Pt.ball(b, (0, 0, 0), 0.07, col, scale=(1.0, 1.0, 1.2), segs=12, rings=8)
        Pt.seg(b, (0, 0, -0.085), (0, 0, -0.07), 0.004, 0.012, col, segs=6)


def _on_board(u, v, out=0.0):
    """World point on the board's face (u right, v up, metres), out in front."""
    a = math.radians(BOARD_YAW)
    right = V((math.cos(a), math.sin(a), 0.0))
    normal = V((-math.sin(a), math.cos(a), 0.0))
    return BOARD_AT + right * u + V((0, 0, v)) + normal * out


def thu_knives(m, t, t_bow):
    """Knife throwing: a target board out of the trunk (!) to the far end of the
    stage, five balloons on it; six knives thrown from across the stage, one
    by one, sticking round the balloons; pulled out, and the balloons popped
    one by one, the last one thrown with his back turned."""
    f = m.f
    t = begin(m, t)
    t = to_trunk(m, t)
    tr = trunk_point(0.0, 0.10)
    q_board = DF.qyaw(BOARD_YAW)
    out = Keys()
    out.add(t + 1.0, tr).add(t + 2.6, tr + V((0, 0, 1.2))).add(t + 5.0, BOARD_AT)
    out.done()
    m.prop("TBoard", t + 1.0, ("wkeys", out, q_board), 0)
    m.scale("TBoard", t + 1.0, 0.001, t + 2.4, 1.0)
    pose(m, t + 1.0, R=f.at_world(tr + V((0, 0, 0.05))), lean=30, pitch=28)
    pose(m, t + 2.6, R=P(0.30, 0.30, 1.70), lean=3, pitch=-20)
    m.look_at(t + 3.4, (BOARD_AT.x, BOARD_AT.y))
    bal_spots = [(-0.22, 0.20), (0.20, 0.22), (0.0, 0.0), (-0.20, -0.20), (0.22, -0.18)]
    for b, (u, v) in zip(BALLOONS, bal_spots):
        m.prop(b, t + 5.0, ("spot", _on_board(u, v, 0.08), q_board), 0)
        m.scale(b, t + 5.0, 0.001, t + 5.6, 1.0)
    pose(m, t + 5.4, R=HR["R"], pitch=4)
    f.yaw.add(t + 5.6, 0)
    t += 5.8
    # Six knives from the trunk.
    t = take(m, t, "L", list(TKNIVES), lambda n: ("hand", "L", np.array((0.0, -0.01 * TKNIVES.index(n), 0.0)),
                                                  DF.qx(-60.0)))
    t = CF._step_to(m, t, THROW_AT)
    face = heading(THROW_AT, (BOARD_AT.x, BOARD_AT.y))
    t = turn_to(m, t, face)
    holes = [(-0.36, 0.05), (0.36, 0.0), (0.0, 0.36), (0.0, -0.34), (-0.26, -0.27), (0.27, 0.27)]

    def throw(t, name, uv, pop=None):
        pose(m, t + 0.3, L=P(-0.10, 0.36, 1.20), R=P(0.0, 0.36, 1.22))       # one into the right hand
        m.prop(name, t + 0.35, ("hand", "R", np.zeros(3), DF.qx(-60.0)), 4)
        pose(m, t + 1.1, R=P(0.24, -0.06, 1.64), twist=-14, lean=-4)      # back...
        ts = t + 1.85
        pose(m, ts, R=P(0.20, 0.52, 1.42), twist=10, lean=10)             # ...and away
        tgt = _on_board(uv[0], uv[1], 0.13)
        q_stuck = DF.qmul(DF.qyaw(BOARD_YAW + 180.0), DF.qx(-90.0))
        m.prop(name, ts, ("throw", "R", ts, tgt, ts + 0.42, "knife", 1.5, q_stuck), 0)
        if pop:
            m.scale(pop, ts + 0.40, 1.0, ts + 0.48, 0.001)
            m.prop(pop, ts + 0.5, ("hide",), 0)
        pose(m, ts + 0.9, R=CARRY["R"], twist=0, lean=3)
        return ts + 1.1
    for k, name in enumerate(TKNIVES):
        t = throw(t, name, holes[k])
        if k in (1, 3):
            t = CF._side(m, t, "pub", 0 if k == 1 else 1) if False else t
    m.hold["L"] = None
    pose(m, t + 0.6, L=HR["L"])
    # Fetched back out of the board.
    near = (BOARD_AT.x + 0.55, BOARD_AT.y - 0.30)
    t = CF._step_to(m, t + 0.6, near)
    t = turn_to(m, t, heading(near, (BOARD_AT.x, BOARD_AT.y)))
    for k, name in enumerate(TKNIVES):
        pose(m, t + 0.5, R=f.at_world(_on_board(holes[k][0], holes[k][1], 0.20)), lean=10)
        m.prop(name, t + 0.6, ("hand", "R", np.zeros(3), DF.qx(-60.0)), 4)
        pose(m, t + 0.9, L=P(-0.06, 0.36, 1.20), R=P(0.04, 0.36, 1.22))
        m.prop(name, t + 1.0, ("hand", "L", np.array((0.0, -0.01 * k, 0.0)), DF.qx(-60.0)), 3)
        t += 1.1
    pose(m, t + 0.4, R=HR["R"], lean=3)
    t = CF._step_to(m, t + 0.4, THROW_AT)
    t = turn_to(m, t, face)
    # The balloons: one knife each; the last thrown with his back to it.
    for k, b in enumerate(BALLOONS):
        u, v = bal_spots[k]
        if k == 4:
            t = turn_to(m, t, face + 180.0)
            pose(m, t + 0.6, pitch=-30, lean=-14)           # head back, looking at it upside down
            pose(m, t + 1.3, R=P(0.10, 0.10, 1.95))
            ts = t + 1.8
            pose(m, ts, R=P(0.0, -0.40, 1.75))
            m.prop(TKNIVES[k], t + 0.6, ("hand", "R", np.zeros(3), DF.qx(-60.0)), 4)
            m.prop(TKNIVES[k], ts, ("throw", "R", ts, _on_board(u, v, 0.13), ts + 0.45, "knife", 1.5,
                                    DF.qmul(DF.qyaw(BOARD_YAW + 180.0), DF.qx(-90.0))), 0)
            m.scale(b, ts + 0.43, 1.0, ts + 0.50, 0.001)
            m.prop(b, ts + 0.52, ("hide",), 0)
            pose(m, ts + 1.0, R=CARRY["R"], pitch=4, lean=3)
            t = turn_to(m, ts + 1.2, face)
        else:
            t = throw(t, TKNIVES[k], (u, v), pop=b)
    t = throw(t, TKNIVES[5], (0.06, 0.08))                 # and the last into the bull
    m.hold["L"] = None
    pose(m, t + 0.6, P(-0.34, 0.30, 1.40), P(0.34, 0.30, 1.40))
    t += 1.0
    # The board, knives and all, floats back into the trunk.
    back = Keys()
    back.add(t, BOARD_AT.copy()).add(t + 2.5, tr + V((0, 0, 1.2))).add(t + 4.0, tr)
    back.done()
    m.prop("TBoard", t, ("wkeys", back, q_board), 0)
    for k, name in enumerate(TKNIVES):
        u, v = bal_spots[k] if k < 5 else (0.06, 0.08)
        off = _on_board(u, v, 0.13) - BOARD_AT
        kk = Keys()
        kk.add(t, BOARD_AT + off).add(t + 2.5, tr + V((0, 0, 1.2)) + off).add(t + 4.0, tr + off)
        kk.done()
        m.prop(name, t, ("wkeys", kk, DF.qmul(DF.qyaw(BOARD_YAW + 180.0), DF.qx(-90.0))), 0)
    for n in ("TBoard",) + TKNIVES:
        m.scale(n, t + 3.4, 1.0, t + 4.0, 0.001)
        m.prop(n, t + 4.1, ("hide",), 0)
    m.look_at(t + 0.5, (tr.x, tr.y))
    f.yaw.add(t + 4.0, 0)
    t += 4.2
    return finish(m, t, t_bow, "knife throwing")


# --- The yo-yo -------------------------------------------------------------------------------------
kit("YoYo", "YoStr")
YO_LEN = 0.85


@mesh
def _yoyo_mesh(Pt):
    for sx in (-1, 1):
        Pt.seg("YoYo", (sx * 0.004, 0, 0), (sx * 0.026, 0, 0), 0.03, 0.03, "d8283a", segs=14)
    Pt.seg("YoStr", (0, 0, 0), (0, 0, 1.0), 0.0022, 0.0022, "f2efe6", segs=4, caps=False)


class YoYo:
    """The yo-yo on its string from his right hand: up in the hand, down
    (keyed fraction of the string), walking the dog along the floor ahead,
    or around the world (a circle in front of him)."""

    def __init__(self):
        self.out = Keys().add(0.0, 0.0)               # 0 in the hand .. 1 at the end of the string
        self.mode = [(0.0, "line", None)]
        self.spin = Keys().add(0.0, 0.0)

    def pos(self, fis, C):
        self.out.done()
        tt = fis / FPS
        out = np.array(DF.sample(self.out), float)[fis]
        hand = C["palm"]["R"][fis]
        qb = C["qb"][fis]
        P_ = hand - np.outer(out * YO_LEN, (0, 0, 1))
        for j, (t0, mode, arg) in enumerate(sorted(self.mode, key=lambda e: e[0])):
            nxt = [e[0] for e in self.mode if e[0] > t0]
            t1 = min(nxt) if nxt else 1e9
            sel = (tt >= t0) & (tt < t1)
            if not sel.any() or mode == "line":
                continue
            u = np.clip((tt[sel] - t0) / (arg[0] - 0.0001), 0, 1)
            if mode == "dog":                               # along the floor ahead and back
                d = arg[1] * np.sin(np.pi * u)
                fw = DF.qrot(qb[sel], np.tile((0.0, 1.0, 0.0), (sel.sum(), 1)))
                base = np.array([(x, y, floor_z(x, y) + 0.03) for x, y in C["pos"][fis[sel]][:, :2]])
                P_[sel] = base + fw * (0.35 + d)[:, None]
            elif mode == "around":                          # around the world: a circle in front, in his side plane
                a = 2 * np.pi * arg[1] * u
                loc = np.stack([np.zeros(sel.sum()), YO_LEN * np.sin(a), -YO_LEN * np.cos(a)], 1)
                P_[sel] = hand[sel] + DF.qrot(qb[sel], loc)
        return P_, hand

    def fn_yoyo(self):
        def fn(fis, C):
            P_, hand = self.pos(fis, C)
            self.spin.done()
            ang = (np.cumsum(np.array(DF.sample(self.spin), float)) / FPS * 360.0)[fis]
            return P_, DF.qmul(C["qb"][fis], DF.qx(ang))
        return fn

    def fn_string(self):
        def fn(fis, C):
            P_, hand = self.pos(fis, C)
            d = P_ - hand
            L = np.linalg.norm(d, axis=1)
            return hand, _q_to(d), np.stack([np.ones_like(L), np.ones_like(L), np.maximum(L, 0.005)], 1)
        return fn


def thu_yoyo(m, t, t_bow):
    """The yo-yo: thrown down and back, a sleeper, walking the dog along the
    stage and back, around the world twice, a last throw to each side."""
    f = m.f
    t = begin(m, t)
    t = centre(m, t)
    yo = YoYo()
    t = produce(m, t, "YoYo", "R", off=(0, 0, 0.03))
    m.prop("YoYo", t, ("fn", yo.fn_yoyo()), 4)
    m.prop("YoStr", t, ("fn", yo.fn_string()), 0)
    hand = P(0.20, 0.34, 1.30)
    pose(m, t + 0.6, R=hand, pitch=16)
    t += 0.8
    yo.spin.add(t, 0.0).add(t + 1.0, 3.0)
    for k in range(5):                                  # down and up
        pose(m, t + 0.25, R=hand + P(0, 0, 0.10))
        pose(m, t + 0.5, R=hand)
        yo.out.add(t + 0.25, 0.0).add(t + 0.85, 1.0).add(t + 1.45, 0.0)
        t += 1.6
    yo.out.add(t + 0.3, 0.0).add(t + 0.9, 1.0).add(t + 4.0, 1.0).add(t + 4.6, 0.0)      # the sleeper
    pose(m, t + 1.0, R=hand + P(0, 0.04, 0.02), pitch=24)
    t += 5.0
    # Walking the dog.
    yo.out.add(t + 0.3, 0.0).add(t + 0.9, 1.0)
    pose(m, t + 1.0, R=P(0.20, 0.40, 0.95), lean=16, pitch=30)
    yo.mode.append((t + 1.0, "dog", (6.0, 0.55)))
    yo.mode.append((t + 7.0, "line", None))
    m.slide(t + 1.0, (CF.FIN_SPOT[0] + 0.35 * CF._fwd_xy(m.yaw).x, CF.FIN_SPOT[1] + 0.35 * CF._fwd_xy(m.yaw).y), 3.0)
    m.slide(t + 4.0, CF.FIN_SPOT, 3.0)
    pose(m, t + 7.0, R=hand, lean=3, pitch=16)
    yo.out.add(t + 7.0, 1.0).add(t + 7.6, 0.0)
    t += 8.0
    # Around the world.
    yo.out.add(t + 0.3, 0.0).add(t + 0.7, 1.0)
    yo.mode.append((t + 0.7, "around", (3.0, 2.0)))
    yo.mode.append((t + 3.7, "line", None))
    for k in range(9):
        a = 2 * math.pi * 2.0 * k / 8
        pose(m, t + 0.7 + 3.0 * k / 8, R=hand + P(0.0, 0.05 * math.sin(a), 0.10 - 0.05 * math.cos(a)))
    yo.out.add(t + 3.7, 1.0).add(t + 4.3, 0.0)
    pose(m, t + 4.3, R=hand, pitch=4)
    t += 4.8
    for k in (0, 1):
        t = CF._side(m, t, "pub", k)
        for q in range(2):
            yo.out.add(t + 0.25, 0.0).add(t + 0.85, 1.0).add(t + 1.45, 0.0)
            t += 1.6
    t = CF._side(m, t, "pub", None)
    yo.spin.add(t, 3.0).add(t + 1.0, 0.0)
    m.prop("YoYo", t + 0.2, ("hand", "R", np.array((0, 0, 0.03)), Q_ID), 4)
    m.prop("YoStr", t + 0.2, ("hide",), 0)
    t = vanish(m, t + 0.3, "YoYo")
    t = ready(m, t)
    return finish(m, t, t_bow, "yo-yo", 35)


# --- Balloon animals -------------------------------------------------------------------------------
kit("LBal", "BDog", "BSword", "BHat")


@mesh
def _balloon_mesh(Pt):
    Pt.ball("LBal", (0, 0, 0.45), 0.05, "f27aa8", scale=(1.0, 1.0, 9.0), segs=10, rings=8)    # (z: inflated length)

    def sausage(name, a, b, r, col):
        Pt.seg(name, a, b, r, r, col, segs=10)
        Pt.ball(name, a, r, col, segs=8, rings=5)
        Pt.ball(name, b, r, col, segs=8, rings=5)
    pk = "f27aa8"
    sausage("BDog", (0, -0.12, 0.30), (0, 0.10, 0.30), 0.045, pk)                       # body
    for sx in (-1, 1):
        for sy in (-0.10, 0.08):
            sausage("BDog", (sx * 0.05, sy, 0.28), (sx * 0.06, sy, 0.02), 0.035, pk)    # legs
    sausage("BDog", (0, 0.12, 0.32), (0, 0.17, 0.46), 0.04, pk)                         # neck
    sausage("BDog", (0, 0.17, 0.48), (0, 0.29, 0.46), 0.04, pk)                         # snout
    for sx in (-1, 1):
        sausage("BDog", (sx * 0.03, 0.17, 0.50), (sx * 0.05, 0.14, 0.60), 0.03, pk)     # ears
    sausage("BDog", (0, -0.14, 0.32), (0, -0.20, 0.44), 0.03, pk)                       # tail
    sausage("BSword", (0, 0, 0.10), (0, 0, 0.82), 0.04, "2a6ad8")
    for sx in (-1, 1):
        sausage("BSword", (0, 0, 0.10), (sx * 0.12, 0, 0.14), 0.035, "2a6ad8")
    sausage("BSword", (0, 0, -0.08), (0, 0, 0.08), 0.035, "2a6ad8")
    n = 10
    for k in range(n):
        a0, a1 = 2 * math.pi * k / n, 2 * math.pi * (k + 1) / n
        Pt.seg("BHat", (0.13 * math.cos(a0), 0.13 * math.sin(a0), 0), (0.13 * math.cos(a1), 0.13 * math.sin(a1), 0),
               0.035, 0.035, "f2c430", segs=8, caps=False)
    sausage("BHat", (0, -0.13, 0.0), (0, 0.0, 0.30), 0.035, "f2c430")
    sausage("BHat", (0, 0.13, 0.0), (0, 0.0, 0.30), 0.035, "f2c430")


def thu_balloons(m, t, t_bow):
    """Balloon animals: a long balloon blown up in breaths, knotted, twisted
    and twisted again: a dog. Set down, it trots off along the stage and he
    has to chase it, scold it, it sits. Then a long blue one: a sword, and a
    duel with nobody (he loses: run through under his arm, he dies at great
    length). And a yellow one: a hat, on top of his own."""
    f = m.f
    t = begin(m, t)
    t = centre(m, t)

    def blow_up(t, colour_from):
        pose(m, t + 0.8, R=P(0.12, 0.10, 1.00))         # out of his pocket
        m.prop("LBal", t + 0.9, ("hand", "L", np.array((0.0, 0.0, 0.0)), DF.qx(-90.0)), 0)
        pose(m, t + 1.4, L=P(-0.02, 0.18, 1.50), R=P(0.04, 0.22, 1.48), pitch=-4)   # to his lips
        m.prop("LBal", t + 1.4, ("hand", "L", np.array((0.0, 0.0, 0.0)), DF.qx(-90.0)), 6)
        for k in range(4):                              # breaths
            tb = t + 1.8 + 1.4 * k
            m.scale("LBal", tb, 0.05 + 0.24 * k, tb + 1.0, 0.05 + 0.24 * (k + 1))
            f.lean.add(tb, 2).add(tb + 0.5, -6).add(tb + 1.0, 2)
            f.pitch.add(tb + 0.5, -10).add(tb + 1.2, -2)
        pose(m, t + 7.6, L=P(-0.10, 0.36, 1.30), R=P(0.10, 0.36, 1.30), pitch=8)
        for k in range(5):                              # twisting
            pose(m, t + 8.0 + 0.6 * k, L=P(-0.08 + 0.03 * (k % 2), 0.36, 1.30), R=P(0.08 - 0.03 * (k % 2), 0.36, 1.32))
        return t + 11.0
    m.scale("LBal", t, 0.05, t + 0.1, 0.05)
    t = blow_up(t, "pink")
    m.scale("LBal", t - 0.4, 1.0, t, 0.001)
    m.prop("LBal", t + 0.05, ("hide",), 0)
    m.prop("BDog", t, ("hand", "R", np.array((0.0, -0.05, -0.30)), Q_ID), 0)
    m.scale("BDog", t, 0.001, t + 0.3, 1.0)
    pose(m, t + 0.6, R=P(0.20, 0.42, 1.42), pitch=-4)          # shown
    f.yaw.add(t + 1.4, 30).add(t + 2.4, -30).add(t + 3.2, 0)
    t += 3.4
    # Set down; it trots off; he chases; it sits.
    fw = CF._fwd_xy(m.yaw)
    rt = V((fw.y, -fw.x, 0))
    base = V((m.x, m.y, floor_z(m.x, m.y)))
    pose(m, t + 0.9, R=P(0.20, 0.50, 0.70), lean=40, pitch=30)
    down = base + fw3(fw) * 0.50
    pts = [down, down - rt * 0.45, down - rt * 0.70 + fw3(fw) * 0.25, down - rt * 0.40 + fw3(fw) * 0.50,
           down + rt * 0.20 + fw3(fw) * 0.45, down + rt * 0.55, down + rt * 0.30 - fw3(fw) * 0.25, down]
    trot = spline(pts, t + 1.2, 1.6)
    keys = Keys()
    for tt in np.arange(t + 1.2, t + 1.2 + 1.6 * 7 + 0.01, 0.2):
        p = trot(np.array([tt]))[0]
        keys.add(tt, V((p[0], p[1], p[2] + 0.025 * abs(math.sin(9 * tt)))), lin=True)

    def q_dog(tt, trot=trot):
        v = trot(tt + 0.05) - trot(tt - 0.05)
        return DF.qyaw(np.degrees(np.arctan2(-v[:, 0], v[:, 1] + 1e-9)))
    m.prop("BDog", t + 1.2, ("wkeys", keys, q_dog), 6)
    pose(m, t + 1.6, R=HR["R"], lean=3, pitch=10)
    for k in range(1, 8):                               # he follows it round, a step behind
        p = pts[k] - fw3(fw) * 0.0
        m.look_at(t + 1.2 + 1.6 * k - 0.6, (p.x, p.y))
        if k in (2, 4, 6):
            pose(m, t + 1.2 + 1.6 * k, R=P(0.22, 0.30, 1.30), L=P(-0.08, 0.30, 1.50))   # scolding finger
            pose(m, t + 1.2 + 1.6 * k + 0.6, R=HR["R"], L=HR["L"])
    t += 1.2 + 1.6 * 7
    m.prop("BDog", t, ("spot", down + V((0, 0, 0.0)), DF.qyaw(m.yaw + 180.0)), 6)
    f.yaw.add(t + 0.4, 0)
    pose(m, t + 0.8, R=P(0.24, 0.40, 1.10), pitch=24)          # "sit"
    t += 1.6
    # The sword, and a duel with nobody.
    m.scale("LBal", t, 0.05, t + 0.1, 0.05)
    t = blow_up(t, "blue")
    m.scale("LBal", t - 0.4, 1.0, t, 0.001)
    m.prop("LBal", t + 0.05, ("hide",), 0)
    m.prop("BSword", t, ("hand", "R", np.zeros(3), DF.qx(-70.0)), 0)
    m.scale("BSword", t, 0.001, t + 0.3, 1.0)
    pose(m, t + 0.6, R=P(0.22, 0.40, 1.20), L=P(-0.30, 0.0, 1.55), lean=4)       # en garde
    t += 1.0
    lunges = [(0.30, 0.55, 1.30, 12), (0.24, 0.30, 1.30, 0), (0.30, 0.55, 1.36, 14), (0.10, 0.36, 1.50, -6),
              (0.32, 0.58, 1.28, 16), (0.20, 0.30, 1.20, 0)]
    for k, (x, y, z, ln) in enumerate(lunges):
        pose(m, t + 0.5, R=P(x, y, z), lean=ln)
        if ln > 8:
            fwv = CF._fwd_xy(m.yaw)
            m.slide(t, (m.x + 0.15 * fwv.x, m.y + 0.15 * fwv.y), 0.5)
        elif ln < 0:
            fwv = CF._fwd_xy(m.yaw)
            m.slide(t, (m.x - 0.15 * fwv.x, m.y - 0.15 * fwv.y), 0.5)
        t += 1.0
    # Run through: the sword under his own arm, a stagger, a long death.
    pose(m, t + 0.6, R=P(0.02, 0.10, 1.25), L=P(-0.10, 0.20, 1.30), lean=20, pitch=20)
    m.prop("BSword", t + 0.6, ("hand", "R", np.array((0.0, 0.05, 0.0)), DF.qx(90.0)), 6)
    f.lean.add(t + 1.4, -10).add(t + 2.4, 18)
    fwv = CF._fwd_xy(m.yaw)
    m.slide(t + 1.0, (m.x - 0.25 * fwv.x, m.y - 0.25 * fwv.y), 1.2)
    t = squat(m, t + 2.4, 0.40, 1.2)
    pose(m, t, R=P(0.20, 0.10, 0.90), L=P(-0.30, 0.20, 1.40), lean=30, pitch=-20)
    pose(m, t + 1.0, L=P(-0.20, 0.30, 1.70), pitch=-30)          # one last gesture to the heavens
    pose(m, t + 3.0, L=P(-0.30, 0.20, 0.80), lean=55, pitch=40)    # ...gone
    t += 4.2
    t = stand_up(m, t, 0.8)
    pose(m, t + 0.4, R=P(0.24, 0.40, 1.30), L=P(-0.30, 0.30, 1.40), lean=3, pitch=-2)   # (just kidding)
    m.prop("BSword", t + 0.4, ("hand", "R", np.zeros(3), DF.qx(-70.0)), 6)
    t += 1.2
    m.slide(t, CF.FIN_SPOT, 0.8)
    # The hat: yellow, on top of his own.
    m.scale("BSword", t, 1.0, t + 0.3, 0.001)
    m.prop("BSword", t + 0.35, ("hide",), 0)
    m.scale("LBal", t, 0.05, t + 0.1, 0.05)
    t = blow_up(t + 0.4, "yellow")
    m.scale("LBal", t - 0.4, 1.0, t, 0.001)
    m.prop("LBal", t + 0.05, ("hide",), 0)
    m.prop("BHat", t, ("hand", "R", np.array((0.0, 0.0, 0.05)), Q_ID), 0)
    m.scale("BHat", t, 0.001, t + 0.3, 1.0)
    pose(m, t + 0.8, R=P(0.05, 0.05, 2.02), L=P(-0.05, 0.05, 2.02), pitch=0)
    hat = Keys().add(t + 1.0, P(0.0, 0.0, 1.98))
    m.prop("BHat", t + 1.0, ("local", hat, Q_ID), 6)
    pose(m, t + 2.3, R=HR["R"], L=HR["L"])
    m.hat_balloon = True
    t += 2.4
    # The dog back on its feet: it follows him to his bow.
    return finish(m, t, t_bow, "balloon animals")


def thu_wind(m, t, t_bow):
    """Walking into a gale: leaning on it, hand on his hat, legs going and
    getting nowhere (blown back a little); it changes: he is blown backwards
    across the stage, arms windmilling; it stops dead, and he falls flat on
    his face (nearly), straightens his clothes."""
    f = m.f
    t = begin(m, t)
    t = centre(m, t)
    fw = CF._fwd_xy(m.yaw)
    for k in range(12):                                 # walking into it
        side = 1 if k % 2 == 0 else -1
        foot = f.fR if side > 0 else f.fL
        sx = 0.10 * side
        tt = t + 0.6 * k
        foot.add(tt, P(sx, 0.02, 0.09)).add(tt + 0.3, P(sx, 0.22, 0.22)).add(tt + 0.6, P(sx, 0.02, 0.09))
    pose(m, t + 0.8, P(-0.08, 0.06, 1.98), P(0.30, -0.20, 1.10), 26, 10)   # hand on his hat, the other back
    for k in range(5):
        pose(m, t + 1.6 + 1.2 * k, lean=24 + 4 * (k % 2))
    m.slide(t + 0.5, (m.x - 0.20 * fw.x, m.y - 0.20 * fw.y), 6.8)
    t += 7.4
    # Blown back across the stage.
    pose(m, t + 0.5, P(-0.40, 0.30, 1.70), P(0.40, 0.30, 1.70), -18, -16)
    for k in range(5):
        a = math.pi * k / 2
        pose(m, t + 1.0 + 0.62 * k, P(-0.40, 0.24 * math.cos(a), 1.40 + 0.24 * math.sin(a)),
             P(0.40, 0.24 * math.cos(a + 1.5), 1.40 + 0.24 * math.sin(a + 1.5)))
    rt = V((fw.y, -fw.x))
    m.slide(t + 0.5, (CF.FIN_SPOT[0] - 0.70 * fw.x + 0.30 * rt.x, CF.FIN_SPOT[1] - 0.70 * fw.y + 0.30 * rt.y), 3.2)
    for k in range(6):
        side = 1 if k % 2 == 0 else -1
        foot = f.fR if side > 0 else f.fL
        tt = t + 0.6 + 0.5 * k
        foot.add(tt, P(0.10 * side, 0.02, 0.09)).add(tt + 0.25, P(0.10 * side, -0.15, 0.20)).add(tt + 0.5, P(0.10 * side, 0.02, 0.09))
    t += 4.0
    # Dead calm: he pitches forward, saves it, straightens up.
    pose(m, t + 1.0, P(-0.30, 0.50, 1.00), P(0.30, 0.50, 1.00), 42, 30)
    pose(m, t + 1.8, P(-0.30, 0.50, 1.05), P(0.30, 0.50, 1.05), 38, 24)
    pose(m, t + 2.6, P(-0.10, 0.22, 1.30), P(0.10, 0.22, 1.30), 3, 4)       # straightening his jumper
    pose(m, t + 3.2, P(-0.12, 0.20, 1.10), P(0.12, 0.20, 1.10))
    pose(m, t + 4.6, R=P(0.08, 0.08, 1.98))                                   # and his hat
    t = ready(m, t + 5.0, 1.2)
    return finish(m, t, t_bow, "the wind", 35)


def thu_flame(m, t):
    """The gift (Thursday): a snap of the fingers and a flame on his fingertip;
    it hops from hand to hand (just the one), he blows on it and it swells up
    into a ball of fire, and when it's gone there are flowers in his hand."""
    f = m.f
    t = centre(m, t)
    pose(m, t + 0.6, R=P(0.18, 0.32, 1.40), pitch=6)
    pose(m, t + 0.85, R=P(0.16, 0.34, 1.43))
    m.fire.add(t + 0.9, 0.0).add(t + 1.1, 1.0)
    t += 1.6
    for k in range(4):                                  # admired, carried round
        pose(m, t + 0.8, R=P(0.10 + 0.12 * (k % 2), 0.38, 1.34 + 0.08 * (k % 2)))
        f.yaw.add(t + 0.8, 20 if k % 2 else -20)
        t += 1.0
    f.yaw.add(t, 0)
    # It burns his finger: shaken out, blown on; snapped alight again; it
    # hops (he thinks) from finger to finger, each one tried in turn.
    for k in range(3):
        pose(m, t + 0.5, R=P(0.24, 0.36, 1.30))
        m.fire.add(t + 0.6, 1.0).add(t + 0.8, 0.0)
        for q in range(3):                              # shaking it
            pose(m, t + 0.8 + 0.25 * q, R=P(0.30, 0.34, 1.24 + 0.06 * (q % 2)))
        pose(m, t + 1.8, R=P(0.06, 0.28, 1.50), pitch=4)    # blown on
        pose(m, t + 2.6, R=P(0.18, 0.32, 1.40))
        pose(m, t + 2.9, R=P(0.16, 0.34, 1.43))             # the snap
        m.fire.add(t + 2.95, 0.0).add(t + 3.15, 1.0)
        f.yaw.add(t + 3.4, 15 * (1 - k)).add(t + 4.0, 0)
        t += 4.2
    # A puff: it swells.
    pose(m, t + 0.8, R=P(0.06, 0.32, 1.48), pitch=6, lean=6)
    m.fire.add(t + 1.0, 1.0).add(t + 2.2, 3.2)
    t += 2.6
    pose(m, t + 0.4, R=P(0.30, 0.20, 1.70), pitch=-16)
    m.fire.add(t + 0.5, 3.2).add(t + 0.7, 0.0)
    m.prop("Bouquet", t + 0.6, ("hand", "R", np.array((0.0, 0.0, 0.02)), Q_ID), 0)
    m.scale("Bouquet", t + 0.6, 0.001, t + 0.9, 1.0)
    pose(m, t + 1.4, R=CF.GIFT_HOLD, pitch=4)
    m.hold["R"] = "bouquet"
    return t + 1.6


# --- The snowstorm ---------------------------------------------------------------------------------
FLAKES = tuple(f"Snow{i}" for i in range(56))
kit(*FLAKES, "SFan", "Tissue")


@mesh
def _snow_mesh(Pt):
    for b in FLAKES:
        CF._rbox(Pt, b, Matrix(), (0.035, 0.002, 0.035), "fbfbff")
    for k in range(9):                                  # a paper fan, open (pivot at the bone)
        a = math.radians(-50 + 12.5 * k)
        M = Matrix.Rotation(-a, 4, 'Y') @ Matrix.Translation(V((0.0, 0.0, 0.11)))
        CF._rbox(Pt, "SFan", M, (0.04, 0.002, 0.22), "c8202e" if k % 2 else "e8c040")
    CF._rbox(Pt, "Tissue", Matrix.Translation(V((0, 0, 0.12))), (0.30, 0.002, 0.24), "fbfbff")


class Snow:
    """Paper snow: each flake let go from his left hand (where it is then),
    flung out and up by the fan, then drifting down, swirling, tumbling, to
    lie on the floor a while and melt away; a flake may be used again."""

    def __init__(self):
        self.drops = {f: [] for f in FLAKES}        # (t0, velocity (his frame), seed)

    def emit(self, t, n, k_fan, rng, spread=1.0):
        free = sorted(FLAKES, key=lambda f: (self.drops[f][-1][0] if self.drops[f] else -1e9))
        for i in range(n):
            fl = free[i % len(free)]
            if self.drops[fl] and self.drops[fl][-1][0] > t - 9.0:
                continue                                # (still falling or lying)
            v = np.array((rng.uniform(-0.6, 0.6) * spread, rng.uniform(0.9, 1.8) * k_fan, rng.uniform(0.6, 1.6)))
            self.drops[fl].append((t + rng.uniform(0.0, 0.5), v, rng.random()))

    def fn(self, fl):
        def fn(fis, C):
            tt = fis / FPS
            n = len(fis)
            Pn = np.zeros((n, 3))
            Q = np.tile(Q_ID, (n, 1))
            S = np.full(n, 0.001)
            drops = self.drops[fl]
            for j, (t0, v, seed) in enumerate(drops):
                t1 = drops[j + 1][0] if j + 1 < len(drops) else 1e9
                sel = (tt >= t0) & (tt < min(t1, t0 + 9.0))
                if not sel.any():
                    continue
                f0 = C["fi"](t0)
                start = C["palm"]["L"][f0] + np.array((0.0, 0.0, 0.05))
                vw = DF.qrot(C["qb"][f0], v)
                s = tt[sel] - t0
                damp = 1.0 - np.exp(-1.8 * s)                    # (paper: quickly slowed)
                drift = np.outer(damp / 1.8, vw)
                fall = np.minimum(0.0, -0.35 * (s - 0.6)) * (s > 0.6)
                sw = 0.12 * np.stack([np.sin(2.3 * s + 7 * seed), np.cos(1.9 * s + 5 * seed), np.zeros_like(s)], 1)
                p = start + drift + sw
                p[:, 2] = start[2] + damp / 1.8 * vw[2] + fall
                floor = np.array([floor_z(x, y) for x, y in p[:, :2]]) + 0.004
                landed = p[:, 2] <= floor
                p[:, 2] = np.maximum(p[:, 2], floor)
                p[:, 2] = np.minimum(p[:, 2], 3.0)
                Pn[sel] = p
                spin = 260.0 * s + 360 * seed
                q = DF.qmul(_qaxis((0, 0, 1), spin), _qaxis((1, 0, 0), 70.0 * np.sin(3.1 * s + seed * 9)))
                q[landed] = DF.qx(90.0)
                Q[sel] = q
                life = np.clip((t0 + 9.0 - tt[sel]) / 1.5, 0.0, 1.0)
                S[sel] = np.maximum(0.001, life)
            return Pn, Q, S
        return fn


def thu_snow(m, t, t_bow):
    """The finale: the snowstorm. A sheet of tissue paper out of the trunk,
    torn up small and rolled into a ball in his fist; a red paper fan; the
    lights go down to the spotlight, and as he fans, snow streams out of his
    fist into the light and over the audience, swirling, settling slowly;
    again, more, from each side; a last great flurry with the fan sweeping up."""
    f = m.f
    t = begin(m, t)
    t = to_trunk(m, t)
    sn = Snow()
    for fl in FLAKES:
        m.prop(fl, t, ("fn", sn.fn(fl)), 0)
    t = take(m, t, "L", ["Tissue"], ("hand", "L", np.zeros(3), Q_ID))
    t = centre(m, t)
    # Torn small: the hands work at it, it shrinks into a ball in his fist.
    pose(m, t + 0.6, P(-0.10, 0.36, 1.32), P(0.10, 0.36, 1.32), 4, 10)
    for k in range(6):
        pose(m, t + 1.0 + 0.6 * k, P(-0.06 - 0.06 * (k % 2), 0.36, 1.32), P(0.06 + 0.06 * (k % 2), 0.36, 1.34))
    m.scale("Tissue", t + 1.0, 1.0, t + 4.4, 0.18)
    pose(m, t + 4.8, P(-0.04, 0.36, 1.26), P(0.04, 0.36, 1.28), pitch=12)
    t += 5.2
    # The fan from his coat.
    pose(m, t + 0.8, R=P(0.04, 0.20, 1.30))
    m.prop("SFan", t + 0.9, ("hand", "R", np.zeros(3), DF.qx(-20.0)), 0)
    m.scale("SFan", t + 0.9, 0.001, t + 1.3, 1.0)
    pose(m, t + 1.6, R=P(0.30, 0.34, 1.40), L=P(-0.16, 0.38, 1.30))
    t += 2.0
    lights(m, t, 3.0, black=0.7, spot=0.8)
    t += 1.5
    rng = random.Random("snow")
    t_end = t_bow - 2.4 - 16.0
    wave = 0
    while t < t_end:
        side = (0, 1, None)[wave % 3]
        if wave % 2 == 0 and wave:
            t = CF._side(m, t, "pub", side)
        for k in range(10):                             # fanning: strokes across his fist
            tt = t + 0.75 * k
            pose(m, tt + 0.35, R=P(0.06, 0.48, 1.36), twist=-8)
            pose(m, tt + 0.70, R=P(0.36, 0.34, 1.46), twist=6)
            pose(m, tt + 0.5, L=P(-0.14, 0.40, 1.30 + 0.03 * (k % 2)))
            sn.emit(tt + 0.35, 2 if wave < 2 else 3, 1.0 + 0.3 * wave, rng)
        t += 7.6
        f.yaw.add(t - 3.0, rng.uniform(-15, 15)).add(t, 0)
        wave += 1
    t = CF._side(m, t, "pub", None)
    # The last flurry: the fan swept up, a cloud of it.
    for k in range(4):
        tt = t + 1.0 * k
        pose(m, tt + 0.5, R=P(0.12, 0.44, 1.24), twist=-6)
        pose(m, tt + 1.0, R=P(0.34, 0.30, 1.70), twist=6, pitch=-16)
        sn.emit(tt + 0.5, 8, 1.6, rng, spread=1.8)
    t += 4.4
    pose(m, t + 0.6, L=P(-0.40, 0.30, 1.60), R=P(0.40, 0.30, 1.60), twist=0, pitch=-20)
    m.scale("Tissue", t + 0.2, 0.18, t + 0.4, 0.001)
    m.prop("Tissue", t + 0.45, ("hide",), 0)
    lights(m, t + 2.0, 2.0, black=0.0, spot=1.0)
    t += 2.4
    return finish(m, t, t_bow, "snowstorm", 55, hat=False)


def thu_tidy(m, t):
    t = to_trunk(m, t)
    names = ["SFan"] + (["BHat"] if getattr(m, "hat_balloon", False) else [])
    if "BHat" in names:
        pose(m, t + 0.6, L=P(-0.05, 0.05, 2.0))
        m.prop("BHat", t + 0.8, ("hand", "L", np.zeros(3), Q_ID), 4)
    t = stow(m, t + 1.0, "R", names)
    m.scale("BDog", t, 1.0, t + 0.6, 0.001)
    m.prop("BDog", t + 0.65, ("hide",), 0)
    return CF._back(m, t, 0.8)



# =====================================================================================
# SATURDAY: lights
# =====================================================================================
GLOW_COLS = {"red": (1.0, 0.18, 0.22), "green": (0.25, 1.0, 0.35), "blue": (0.25, 0.5, 1.0),
             "yellow": (1.0, 0.85, 0.2), "magenta": (1.0, 0.25, 0.9), "cyan": (0.2, 0.95, 1.0)}
GLOW_SLOT = {n: 5 + k for k, n in enumerate(("red", "green", "blue", "yellow", "magenta", "cyan"))}


def _glow_mat(name, rgb):
    def make():
        mt = bpy.data.materials.get(f"FigGlow{name.title()}")
        if mt:
            return mt
        mt = bpy.data.materials.new(f"FigGlow{name.title()}")
        mt.use_nodes = True
        b = mt.node_tree.nodes['Principled BSDF']
        b.inputs['Base Color'].default_value = rgb + (1.0,)
        if b.inputs.get('Emission Color'):
            b.inputs['Emission Color'].default_value = rgb + (1.0,)
            b.inputs['Emission Strength'].default_value = 2.5
        return mt
    return make


def sat_ladder(m, t, t_bow):
    """Opener: the invisible ladder. Hands on the rungs, climbing (the hands
    come down, a foot comes up); at the top he peers over, waves to someone
    up there, and climbs down again."""
    f = m.f
    t = begin(m, t)
    hi, lo = 1.78, 1.42
    pose(m, t + 0.8, P(-0.16, 0.32, lo), P(0.16, 0.32, hi), 4, -6)
    t += 1.0
    for k in range(4):                                  # up: a hand moves up, the other hand and a foot follow
        up, dn = ("L", "R") if k % 2 == 0 else ("R", "L")
        su = -1 if up == "L" else 1
        sd = -su
        pose(m, t + 0.5, **{up: P(su * 0.16, 0.32, hi + 0.10)})
        pose(m, t + 1.2, **{up: P(su * 0.16, 0.32, hi), dn: P(sd * 0.16, 0.32, lo)})
        foot = f.fL if up == "L" else f.fR
        sx = -0.10 if up == "L" else 0.10
        foot.add(t + 0.4, P(sx, 0.02, 0.09)).add(t + 0.8, P(sx, 0.16, 0.36)).add(t + 1.3, P(sx, 0.02, 0.09))
        f.pitch.add(t + 0.6, -14).add(t + 1.2, -8)
        t += 1.4
    # The top: peering over, a wave, a nod.
    pose(m, t + 0.8, P(-0.16, 0.30, 1.86), P(0.16, 0.30, 1.86), 2, -24)
    pose(m, t + 1.6, R=P(0.30, 0.20, 2.02))
    for q in range(3):
        pose(m, t + 1.9 + 0.3 * q, R=P(0.36 + 0.06 * (q % 2), 0.20, 2.04))
    pose(m, t + 3.6, P(-0.16, 0.32, hi), P(0.16, 0.32, lo), 4, 0)
    t += 3.8
    for k in range(3):                                  # down again
        up, dn = ("L", "R") if k % 2 == 0 else ("R", "L")
        su = -1 if up == "L" else 1
        pose(m, t + 0.6, **{up: P(su * 0.16, 0.32, lo), dn: P(-su * 0.16, 0.32, hi)})
        foot = f.fL if up == "L" else f.fR
        sx = -0.10 if up == "L" else 0.10
        foot.add(t + 0.2, P(sx, 0.02, 0.09)).add(t + 0.5, P(sx, 0.14, 0.30)).add(t + 0.9, P(sx, 0.02, 0.09))
        t += 1.0
    pose(m, t + 0.6, P(-0.08, 0.30, 1.10), P(0.08, 0.30, 1.14), 4, 6)    # dusting his gloves
    pose(m, t + 1.0, P(-0.04, 0.30, 1.16), P(0.04, 0.30, 1.08))
    t = ready(m, t + 1.2)
    return finish(m, t, t_bow, "the ladder", 30)


# --- Juggling in the dark ----------------------------------------------------------------------
GLOWB = ("GlowB0", "GlowB1", "GlowB2")
GLOWC = ("GlowC0", "GlowC1", "GlowC2")
kit(*GLOWB, *GLOWC)
CF.NAMES["glow"] = GLOWB
CF.NAMES["gclub"] = GLOWC
CF.JUG["glow"] = CF.JUG["ball"]
CF.JUG["gclub"] = CF.JUG["club"]
CF.COM["glow"] = np.zeros(3)
CF.COM["gclub"] = CF.COM["club"]


@mesh
def _glow_mesh(Pt):
    for name, col in zip(GLOWB, ("red", "green", "blue")):
        CF._sphere(Pt, name, CF.BALL_R * 1.05, "ffffff", GLOW_SLOT[col], segs=10, rings=6)
    for name, col in zip(GLOWC, ("magenta", "yellow", "cyan")):
        Pt.seg(name, (0, 0, -0.09), (0, 0, 0.10), 0.013, 0.017, "222222", segs=8)
        Pt.seg(name, (0, 0, 0.10), (0, 0, 0.42), 0.020, 0.040, "ffffff", segs=10, mat=GLOW_SLOT[col])


def _glow_out(m, t, kind, names):
    """Out of the air: one in his left hand, two in his right."""
    f = m.f
    pose(m, t + 0.8, P(-0.30, 0.30, 1.70), P(0.30, 0.30, 1.70), pitch=-14)
    for i, (side, slot) in enumerate((("R", 0), ("L", 0), ("R", 1))):
        m.prop(names[i], t + 1.0, CF.hand_state(kind, side, slot), 0)
        m.scale(names[i], t + 1.0, 0.001, t + 1.3, 1.0)
        m.holding[kind][i] = (side, slot)
    m.hold["L"] = m.hold["R"] = kind
    IN, OUT = CF.JUG[kind]
    pose(m, t + 1.8, OUT["L"], IN["R"] if kind == "glow" else CF.CARRY["R"], pitch=12)
    return t + 2.0


def sat_glow(m, t, t_bow):
    """Juggling in the dark: the house black, the spot gone; three glowing balls
    out of nowhere (red, green, blue) and juggled, high, fast, in showers of
    colour; they turn into glowing clubs in a flash; clubs high and fast, a
    flash with a turn under it; gone in the dark, and the light finds him."""
    f = m.f
    t = begin(m, t)
    t = centre(m, t)
    m.holding.setdefault("glow", {})
    m.holding.setdefault("gclub", {})
    lights(m, t, 2.5, black=1.0, spot=0.0)
    m.beam.add(t, 1.0).add(t + 2.0, 0.0)
    t += 2.4
    t = _glow_out(m, t, "glow", GLOWB)
    t = CF.cascade(m, "glow", t + 0.3, 21, 0.40, style="high") + 0.4
    t = CF.cascade(m, "glow", t, 36, 0.30) + 0.3
    t = CF.flash(m, "glow", t + 0.3, T=0.9, b=0.2, pirouette=False) + 0.4
    for k in (0, 1):
        t = CF._side(m, t, "pub", k)
        t = CF.cascade(m, "glow", t + 0.3, 24, 0.30) + 0.3
        t = CF.flash(m, "glow", t + 0.3, T=0.85, b=0.2, pirouette=False) + 0.3
    t = CF._side(m, t, "pub", None)
    # The change: thrown up as balls, caught as clubs.
    t0 = t + 0.3
    t = CF.flash(m, "glow", t0, T=0.9, b=0.2, pirouette=False)
    for i in range(3):
        tt = t0 + 0.2 * i + 0.42
        m.scale(GLOWB[i], tt, 1.0, tt + 0.06, 0.001)
        m.prop(GLOWB[i], tt + 0.1, ("hide",), 0)
    new = {}
    for i, (side, slot) in enumerate((("R", 0), ("L", 0), ("R", 1))):
        m.prop(GLOWC[i], t - 0.3, CF.hand_state("gclub", side, slot), 0)
        m.scale(GLOWC[i], t - 0.3, 0.001, t - 0.15, 1.0)
        new[i] = (side, slot)
    m.holding["glow"] = {}
    m.holding["gclub"] = new
    m.hold["L"] = m.hold["R"] = "gclub"
    pose(m, t + 0.2, CF.CARRY["L"], CF.CARRY["R"])
    t += 0.6
    t = CF.cascade(m, "gclub", t + 0.3, 15, 0.42 * 0.86, 0.22, style="high") + 0.5
    t = CF.cascade(m, "gclub", t, 30, 0.34) + 0.4
    t = CF.flash(m, "gclub", t + 0.4, T=0.88) + 0.5
    t = CF.fill(m, "gclub", t, t_bow - 2.4 - 9.0, 0.34)
    t = CF.cascade(m, "gclub", t + 0.3, 12, 0.36) + 0.4
    # Gone: all three fade in his hands; the spot finds him.
    for n in GLOWC:
        m.scale(n, t + 0.4, 1.0, t + 1.0, 0.001)
        m.prop(n, t + 1.05, ("hide",), 0)
    m.holding["gclub"] = {}
    m.hold["L"] = m.hold["R"] = None
    pose(m, t + 1.2, P(-0.30, 0.30, 1.40), P(0.30, 0.30, 1.40), 3, -2)
    lights(m, t + 1.0, 1.5, black=0.0, spot=1.0)
    m.beam.add(t + 1.0, 0.0).add(t + 1.6, 1.0)
    t += 1.8
    return finish(m, t, t_bow, "glow juggling")


# --- The umbrella in the rain ------------------------------------------------------------------
RAIN = tuple(f"Rain{i}" for i in range(18))
kit("Umb", "UmbTop", *RAIN)


@mesh
def _umbrella_mesh(Pt):
    Pt.seg("Umb", (0, 0, -0.05), (0, 0, 0.72), 0.009, 0.009, "1c1c1e", segs=6)
    for k in range(10):                                 # a J handle
        a0, a1 = math.pi * k / 10, math.pi * (k + 1) / 10
        Pt.seg("Umb", (0.04 - 0.04 * math.cos(a0), 0, -0.05 - 0.04 * math.sin(a0)),
               (0.04 - 0.04 * math.cos(a1), 0, -0.05 - 0.04 * math.sin(a1)), 0.009, 0.009, "6a3a1e", segs=5, caps=False)
    for k in range(8):                                  # the canopy (its own bone, at the tip: it opens)
        a0, a1 = 2 * math.pi * k / 8, 2 * math.pi * (k + 1) / 8
        col = "c8202e" if k % 2 else "f4f2ea"
        Pt.seg("UmbTop", (0, 0, 0), (0.48 * math.cos(0.5 * (a0 + a1)), 0.48 * math.sin(0.5 * (a0 + a1)), -0.18),
               0.004, 0.004, "1c1c1e", segs=4)
        for flip in (False, True):                      # (both faces: seen from above and below)
            vs = [Pt.bm.verts.new(p) for p in ((0, 0, 0), (0.50 * math.cos(a0), 0.50 * math.sin(a0), -0.20),
                                                 (0.50 * math.cos(a1), 0.50 * math.sin(a1), -0.20))]
            Pt.bm.faces.new(list(reversed(vs)) if flip else vs)
            Pt._tag(vs, "UmbTop", col)
    for b in RAIN:
        Pt.seg(b, (0, 0, 0), (0, 0, 0.12), 0.003, 0.003, "b8d0e8", segs=4, mat=4)


def _rain_fn(i, t0, t1, centre_xy):
    rs = random.Random(f"rain{i}")
    period = rs.uniform(0.55, 0.8)
    ph = rs.uniform(0, period)
    ox, oy = rs.uniform(-1.0, 1.0), rs.uniform(-0.7, 0.7)

    def fn(fis, C):
        tt = fis / FPS
        k = np.floor((tt - t0 + ph) / period)
        u = ((tt - t0 + ph) / period) - k
        jx = np.sin(k * 12.9898 + i) * 0.35
        jy = np.cos(k * 78.233 + i) * 0.30
        x = centre_xy[0] + ox + jx
        y = centre_xy[1] + oy + jy
        z = 3.0 - u * 2.6
        P_ = np.stack([x, y, z], 1)
        on = ((tt >= t0) & (tt < t1) & (u > 0.25)).astype(float)
        return P_, np.tile(Q_ID, (len(fis), 1)), np.maximum(0.001, np.stack([on, on, on], 1))
    return fn


def sat_umbrella(m, t, t_bow):
    """The rain: a drop on his palm, another; he looks up; it pours. An umbrella
    out of his sleeve, opened; a stroll under it in the rain, swinging it,
    a kick through a puddle; a gust: inside out; wrestled right, and the rain
    stops; furled, a bow."""
    f = m.f
    t = begin(m, t)
    t = centre(m, t)
    pose(m, t + 0.8, R=P(0.20, 0.40, 1.20), pitch=20)           # a drop
    pose(m, t + 1.6, R=P(0.20, 0.42, 1.24))
    pose(m, t + 2.4, L=P(-0.24, 0.36, 1.26), pitch=-30)          # another; he looks up
    t_rain = t + 3.0
    t_dry = t + 26.0
    for i, r in enumerate(RAIN):
        m.prop(r, t_rain, ("fn", _rain_fn(i, t_rain, t_dry, (m.x, m.y))), 0)
    pose(m, t + 3.4, P(-0.12, 0.10, 1.96), P(0.12, 0.10, 1.96), 10, 20)     # hands over his head
    t += 4.2
    q_up = Q_ID
    pose(m, t + 0.8, R=P(0.10, 0.20, 1.20))
    m.prop("Umb", t + 0.9, ("hand", "R", np.array((0, 0, 0.0)), q_up), 0)
    m.scale("Umb", t + 0.9, 0.001, t + 1.2, 1.0)
    tip = lambda: ("local", None, None)
    canopy = Keys().add(t + 1.0, P(0.16, 0.30, 1.85))
    pose(m, t + 1.8, R=P(0.16, 0.30, 1.13))
    m.prop("UmbTop", t + 1.8, ("hand", "R", np.array((0, 0, 0.72)), Q_ID), 0)
    m.scale("UmbTop", t + 1.8, 0.001, t + 2.6, 1.0)                # opened
    t += 3.0
    # The stroll: round the stage, swinging it, a kick at a puddle.
    fw = CF._fwd_xy(m.yaw)
    rt = V((fw.y, -fw.x))
    loop = [(CF.FIN_SPOT[0] + 0.5 * math.cos(a) * rt.x + 0.35 * math.sin(a) * fw.x,
             CF.FIN_SPOT[1] + 0.5 * math.cos(a) * rt.y + 0.35 * math.sin(a) * fw.y) for a in np.linspace(0, 2 * math.pi, 9)]
    for k, xy in enumerate(loop[1:]):
        m.slide(t, xy, 1.6, heading((m.x, m.y), xy))
        pose(m, t + 0.8, R=P(0.16, 0.30, 1.13 + 0.05 * (k % 2)), L=P(-0.24, 0.10 + 0.10 * (k % 2), 1.00))
        f.fR.add(t + 0.4, V(STAND[1])).add(t + 0.8, P(0.10, 0.20, 0.25)).add(t + 1.2, V(STAND[1]))
        f.fL.add(t + 1.2, V(STAND[0])).add(t + 1.4, P(-0.10, 0.15, 0.20)).add(t + 1.6, V(STAND[0]))
        t += 1.6
    t = centre(m, t)
    # The gust: blown inside out.
    m.prop("UmbTop", t + 0.6, ("hand", "R", np.array((0, 0, 0.72)), DF.qx(180.0)), 4)
    pose(m, t + 0.6, R=P(0.30, 0.50, 1.40), lean=-10, pitch=-10)
    m.slide(t + 0.4, (m.x - 0.25 * fw.x, m.y - 0.25 * fw.y), 0.8)
    t += 1.4
    for k in range(3):                                  # wrestling it
        pose(m, t + 1.4, R=P(0.20, 0.40, 1.50), L=P(-0.05, 0.45, 1.80), lean=8)
        pose(m, t + 2.1, R=P(0.24, 0.36, 1.36), L=P(-0.10, 0.40, 1.60))
        t += 2.1
    m.prop("UmbTop", t, ("hand", "R", np.array((0, 0, 0.72)), Q_ID), 4)
    pose(m, t + 1.4, R=P(0.16, 0.30, 1.13), L=HR["L"], lean=3)
    t = max(t + 1.0, t_dry)
    # The rain stops: a palm held out, the umbrella furled.
    pose(m, t + 1.6, L=P(-0.24, 0.40, 1.24), pitch=-10)
    m.scale("UmbTop", t + 1.4, 1.0, t + 2.0, 0.001)
    m.prop("UmbTop", t + 2.05, ("hide",), 0)
    pose(m, t + 2.4, L=HR["L"], R=P(0.20, 0.30, 0.95), pitch=4)
    t += 2.6
    m.hold["R"] = "umbrella"
    return finish(m, t, t_bow, "umbrella", 35)


# --- The ribbon -------------------------------------------------------------------------------------
RIB = tuple(f"Rib{i}" for i in range(14))
RIB_STICK = 0.50
RIB_DT = 0.055
kit("RibStick", *RIB)
Q_RIB = DF.qx(-35.0)


@mesh
def _ribbon_mesh(Pt):
    Pt.seg("RibStick", (0, 0, -0.04), (0, 0, RIB_STICK), 0.006, 0.004, "f4f2ea", segs=6)
    for k, b in enumerate(RIB):
        CF._rbox(Pt, b, Matrix.Translation(V((0, 0, 0.5))), (0.05, 0.002, 1.0), "d8203a" if k % 2 == 0 else "e83850")


class Ribbon:
    """A gymnast's ribbon: segment k runs from where the stick's tip was k
    steps ago to where it was k+1 steps ago, sagging a little more the older
    it is."""

    def tip_at(self, C, tt):
        fi = np.clip(tt * FPS, 0, DF.N)
        i0 = np.floor(fi).astype(int)
        i1 = np.minimum(i0 + 1, DF.N)
        u = (fi - i0)[:, None]
        palm = C["palm"]["R"][i0] * (1 - u) + C["palm"]["R"][i1] * u
        yaw = C["yaw"][i0] * (1 - u[:, 0]) + C["yaw"][i1] * u[:, 0]
        return palm + DF.qrot(DF.qmul(DF.qyaw(yaw), Q_RIB), np.tile((0.0, 0.0, RIB_STICK), (len(tt), 1)))

    def fn(self, k):
        def fn(fis, C):
            tt = fis / FPS
            a = self.tip_at(C, tt - k * RIB_DT) - np.array((0, 0, 0.004 * k * k))
            b = self.tip_at(C, tt - (k + 1) * RIB_DT) - np.array((0, 0, 0.004 * (k + 1) ** 2))
            for p in (a, b):
                fl = np.array([floor_z(x, y) for x, y in p[:, :2]]) + 0.01
                p[:, 2] = np.maximum(p[:, 2], fl)
            d = b - a
            L = np.linalg.norm(d, axis=1)
            return a, _q_to(d), np.stack([np.ones_like(L), np.ones_like(L), np.maximum(L, 0.002)], 1)
        return fn


def _lead(m, t, p, dur=0.9):
    """The wand hand from wherever it is to p, unhurried."""
    DF.hold_live(m.f.R, t)
    m.f.R.add(t + dur, V(p))
    return t + dur


def _rib_circles(m, t, dur, c, r, hz, plane="wall", sgn=1):
    p0 = V(c) + (V((r, 0.0, 0.0)) if plane in ("wall", "flat") else V((0.0, r, 0.0)))
    t = _lead(m, t, p0, 1.8 if plane == "flat" else 1.2)
    n = max(8, int(dur * hz * 8))
    for k in range(n + 1):
        a = sgn * 2 * math.pi * hz * dur * k / n
        if plane == "wall":
            p = V(c) + V((r * math.cos(a), 0.0, r * math.sin(a)))
        elif plane == "flat":
            p = V(c) + V((r * math.cos(a), r * math.sin(a), 0.0))
        else:
            p = V(c) + V((0.0, r * math.cos(a), r * math.sin(a)))
        m.f.R.add(t + dur * k / n, p, lin=True)
    return t + dur


def sat_ribbon(m, t, t_bow):
    """The ribbon: a long red ribbon on a wand, out of the trunk; great circles
    in front of him, a spiral (little loops drawn across), a snake wriggling
    along the stage as he runs, circles over his head while he turns, figure
    eights at his side, a last big spiral up and round him."""
    f = m.f
    t = begin(m, t)
    t = to_trunk(m, t)
    if m.hold["R"] == "umbrella":                       # the furled umbrella goes back first
        t = stow(m, t, "R", "Umb")
    rb = Ribbon()
    t = take(m, t, "R", ["RibStick"], ("hand", "R", np.zeros(3), Q_RIB))
    for k, b in enumerate(RIB):
        m.prop(b, t - 1.0, ("fn", rb.fn(k)), 0)
    t = centre(m, t)
    t = _rib_circles(m, t + 0.6, 8.0, P(0.24, 0.36, 1.36), 0.28, 0.62)
    # A spiral: little loops drawn across from right to left and back.
    for d in (1, -1):
        t = _lead(m, t, P(0.40 * d * 0.5 + 0.10, 0.40, 1.30))
        n = 40
        for k in range(n + 1):
            u = k / n
            a = 2 * math.pi * 6 * u
            x = 0.40 * d * (0.5 - u) * 2 * 0.5
            m.f.R.add(t + 6.0 * u, P(x + 0.10 * math.cos(a), 0.40, 1.30 + 0.10 * math.sin(a)), lin=True)
        f.yaw.add(t + 3.0, -20 * d).add(t + 6.0, 0)
        t += 6.0
    # The snake, running across the stage and back with the wand low.
    fw = CF._fwd_xy(m.yaw)
    rt = V((fw.y, -fw.x))
    for d in (1, -1):
        to = (CF.FIN_SPOT[0] + rt.x * 0.65 * d, CF.FIN_SPOT[1] + rt.y * 0.65 * d)
        t = turn_to(m, t, heading((m.x, m.y), to))
        t = _lead(m, t, P(0.30, 0.20, 0.60))
        m.slide(t, to, 3.0)
        n = 18
        for k in range(n + 1):
            m.f.R.add(t + 3.0 * k / n, P(0.30, 0.20 - 0.03 * (k % 2), 0.66 + 0.06 * ((k % 2) * 2 - 1)), lin=True)
        f.lean.add(t + 0.5, 20).add(t + 3.0, 6)
        t += 3.2
    t = centre(m, t)
    # Overhead circles while he turns round.
    t0 = t
    t = _rib_circles(m, t + 0.6, 8.0, P(0.10, 0.10, 2.00), 0.26, 0.6, plane="flat")
    f.put(t0 + 1.0, m.x, m.y, m.yaw, lin=True)
    f.root.add(t0 + 4.8, V((m.x, m.y, m.yaw + 180.0)), True)
    f.root.add(t0 + 8.6, V((m.x, m.y, m.yaw + 360.0)))
    f._yaw = m.yaw = m.yaw + 360.0
    pose(m, t0 + 1.0, pitch=-20)
    pose(m, t + 0.2, pitch=4)
    # Figure eights at his side.
    t = _lead(m, t, P(0.40, 0.30, 1.20))
    n = 48
    for k in range(n + 1):
        a = 2 * math.pi * 3 * k / n
        m.f.R.add(t + 9.0 * k / n, P(0.40, 0.30 + 0.24 * math.sin(a), 1.20 + 0.20 * math.sin(2 * a)), lin=True)
    f.yaw.add(t + 1.0, -35).add(t + 8.0, -35).add(t + 9.0, 0)
    t += 9.4
    for k in (0, 1):                                    # circles to each side of the room
        t = CF._side(m, t, "pub", k)
        t = _rib_circles(m, t + 0.4, 7.0, P(0.24, 0.36, 1.36), 0.28, 0.62, sgn=1 - 2 * k)
    t = CF._side(m, t, "pub", None)
    # The fill, and the last: a spiral up and round him.
    t_last = t_bow - 2.4 - 14.0
    while t < t_last - 8.0:
        t = _rib_circles(m, t + 0.4, 7.0, P(0.24, 0.36, 1.36), 0.28, 0.62)
    t = _lead(m, t, P(0.30, 0.10, 1.00), 1.4)
    n = 40
    for k in range(n + 1):
        u = k / n
        a = 2 * math.pi * 4 * u
        m.f.R.add(t + 7.0 * u, P(0.30 * math.cos(a), 0.30 * math.sin(a) + 0.10, 1.00 + 0.95 * u), lin=True)
    pose(m, t + 3.5, pitch=-10)
    t += 7.6
    pose(m, t + 0.8, R=P(0.30, 0.30, 1.80), L=P(-0.30, 0.30, 1.60), pitch=-6)   # a flourish, held
    t += 2.0
    t = to_trunk(m, t)
    t = stow(m, t, "R", ["RibStick"] + list(RIB), dur=1.6)
    return finish(m, t, t_bow, "ribbon")


def sat_tug(m, t, t_bow):
    """The tug of war with somebody invisible, off the edge of the stage: hand
    over hand he pulls, gains, is dragged back to the edge, digs his heels in,
    leans right back; the rope goes, and he sits down hard. Up, a shrug."""
    f = m.f
    t = begin(m, t)
    t = centre(m, t)
    fw = CF._fwd_xy(m.yaw)
    base = (m.x, m.y)
    pose(m, t + 0.8, P(-0.04, 0.48, 1.12), P(0.04, 0.36, 1.10), -10, 6)
    t += 1.0

    def pull(t, n, lean, drift):
        for q in range(n):
            a, b = ("R", "L") if q % 2 == 0 else ("L", "R")
            sa = 1 if a == "R" else -1
            pose(m, t + 0.6 + q * 1.1, **{a: P(sa * 0.04, 0.52, 1.14)})
            pose(m, t + 1.1 + q * 1.1, **{a: P(sa * 0.06, 0.16, 1.06)})
        f.lean.add(t + 0.6, lean).add(t + n * 1.1, lean)
        m.slide(t, (m.x + drift * fw.x, m.y + drift * fw.y), n * 1.1)
        return t + n * 1.1 + 0.2
    t = pull(t, 4, -16, -0.20)                          # he gains
    t = pull(t, 3, 14, 0.45)                            # dragged to the edge
    f.fL.add(t, V(STAND[0])).add(t + 0.4, P(-0.12, 0.30, 0.14))      # heels in
    f.fR.add(t, V(STAND[1])).add(t + 0.4, P(0.12, 0.32, 0.14))
    t = squat(m, t + 0.4, 0.12, 0.5)
    t = pull(t, 4, -24, -0.30)
    # The rope gives: he sits down hard.
    f.zk.hold(t)
    f.fL.hold(t)
    f.fR.hold(t)
    z0 = floor_z(m.x, m.y)
    m.slide(t, (m.x - 0.25 * fw.x, m.y - 0.25 * fw.y), 0.5)
    f.zk.hold(t + 0.5)
    f.zk.add(t + 1.0, z0 - 0.62)
    f.fL.add(t + 1.0, P(-0.14, 0.50, 0.66))
    f.fR.add(t + 1.0, P(0.14, 0.52, 0.66))
    pose(m, t + 1.0, P(-0.30, 0.10, 0.80), P(0.30, 0.10, 0.80), -8, 10)
    t += 2.4
    pose(m, t + 0.6, P(-0.20, 0.30, 0.90), P(0.20, 0.30, 0.90), 6, 16)        # looks at his empty hands
    t += 1.4
    f.zk.add(t + 1.0, z0)
    f.fL.add(t + 1.0, V(STAND[0]))
    f.fR.add(t + 1.0, V(STAND[1]))
    pose(m, t + 1.0, P(-0.30, 0.22, 1.30), P(0.30, 0.22, 1.30), 3, 6)          # a shrug
    t = ready(m, t + 1.6)
    return finish(m, t, t_bow, "tug of war", 35)


def sat_hat(m, t):
    """The gift (Saturday): something in his hat. He hears it (hand to his
    ear), knocks on the crown, lifts it a little: a bouquet rises out of the
    top of his hat; plucked."""
    f = m.f
    t = centre(m, t)
    # Something's missing: pockets patted, a look round, a shrug.
    for k in range(3):
        pose(m, t + 0.6, P(-0.18, 0.10, 0.98), P(0.18, 0.10, 0.98), pitch=24)
        pose(m, t + 1.1, P(-0.16, 0.14, 1.32), P(0.16, 0.14, 1.32))
        f.yaw.add(t + 1.4, (-30, 30, 0)[k])
        t += 1.6
    pose(m, t + 0.8, P(-0.30, 0.24, 1.32), P(0.30, 0.24, 1.32), 3, 8)
    t += 1.8
    pose(m, t + 0.8, P(-0.17, 0.06, 0.87), R=P(0.14, 0.04, 1.62), pitch=0, yaw=-20)      # listening
    f.yaw.add(t + 2.4, 20)
    t += 3.0
    pose(m, t + 0.8, R=P(0.30, 0.30, 1.30), yaw=0, pitch=8)          # nothing; shrug
    pose(m, t + 2.0, R=P(0.14, 0.04, 1.62), yaw=-25)                 # there it is again
    f.yaw.add(t + 3.4, 25)
    t += 4.2
    for q in range(3):                                  # knock knock
        pose(m, t + 0.4 + 0.5 * q, R=P(0.10, 0.06, 2.00))
        pose(m, t + 0.65 + 0.5 * q, R=P(0.12, 0.10, 2.06))
    f.yaw.add(t + 0.4, 0)
    t += 2.0
    pose(m, t + 0.6, P(-0.12, 0.04, 1.96), P(0.12, 0.04, 1.96), pitch=4)    # hat lifted a touch
    rise = Keys().add(t + 1.2, P(0.0, 0.0, 1.90)).add(t + 3.4, P(0.0, 0.04, 2.20))
    m.prop("Bouquet", t + 1.2, ("local", rise, Q_ID), 0)
    m.scale("Bouquet", t + 1.2, 0.001, t + 2.4, 1.0)
    f.pitch.add(t + 2.0, -30).add(t + 3.4, -36)
    pose(m, t + 3.6, R=P(0.04, 0.10, 2.10), L=HR["L"])
    m.prop("Bouquet", t + 3.8, ("hand", "R", np.array((0.0, 0.0, 0.02)), Q_ID), 6)
    pose(m, t + 4.8, R=CF.GIFT_HOLD, pitch=4)
    m.hold["R"] = "bouquet"
    return t + 5.0


# --- The upside-down painting ---------------------------------------------------------------------
CAN_W, CAN_H = 0.92, 0.70
COLS, ROWS = 24, 18
STRIPS = tuple(f"Strip{k}" for k in range(12))
kit("Easel", "Canvas", *STRIPS, "Brush", "Palette")


def _paris(c, r):
    """The picture: the Eiffel Tower lit gold against a night sky, a moon."""
    x, y = c + 0.5, r + 0.5
    if (x - 19.5) ** 2 + (y - 3.5) ** 2 < 4.2:
        return "f2e08a"
    w = None
    if 1 <= r <= 2:
        w = 0.35
    elif 3 <= r <= 14:
        w = 0.6 + (r - 3) * 0.42
    if r in (8, 12):
        w = (w or 0) + 0.9
    if w is not None and abs(x - 12.0) <= w and not (r >= 13 and abs(x - 12.0) < (r - 12) * 0.9):
        return "e0a838" if (c + r) % 3 else "f4c860"
    if r >= 15:
        if abs(x - 12.0) <= 6.5 and not abs(x - 12.0) < 2.2:
            return "e0a838"
        return "182030"
    if (c * 7 + r * 13) % 23 == 0 and r < 12:
        return "f6f2d0"
    return ("101a3a", "142250", "1a2c60", "203470")[min(3, r // 5)]


@mesh
def _paint_mesh(Pt):
    # The easel: three legs and a ledge (the bone at the floor, in front).
    for sx in (-1, 1):
        Pt.seg("Easel", (sx * 0.32, 0.0, 0.0), (sx * 0.20, -0.04, 1.80), 0.016, 0.014, "8a5a2e", segs=6)
    Pt.seg("Easel", (0, -0.40, 0.0), (0, -0.06, 1.70), 0.014, 0.014, "8a5a2e", segs=6)
    CF._rbox(Pt, "Easel", Matrix.Translation(V((0, 0.02, 0.78))), (0.70, 0.07, 0.03), "8a5a2e")
    # The canvas: a frame, a white board (its middle at the bone, facing +y).
    CF._rbox(Pt, "Canvas", Matrix.Translation(V((0, -0.012, 0))), (CAN_W + 0.06, 0.02, CAN_H + 0.06), "6a3a1e")
    CF._rbox(Pt, "Canvas", Matrix.Translation(V((0, 0.0, 0))), (CAN_W, 0.006, CAN_H), "f4f2ea")
    cw, rh = CAN_W / COLS, CAN_H / ROWS
    for k, b in enumerate(STRIPS):
        for cc in range(2):
            c = 2 * k + cc
            for r in range(ROWS):
                x = -0.5 * cw + cc * cw + 0.5 * cw - cw       # (two columns either side of the strip's middle)
                x = (cc - 0.5) * cw
                z = -(r + 0.5) * rh                            # (rows down from the strip's top, at the bone)
                CF._rbox(Pt, b, Matrix.Translation(V((x, 0.0045, z))), (cw * 1.02, 0.002, rh * 1.02), _paris(c, r))
    Pt.seg("Brush", (0, 0, -0.10), (0, 0, 0.18), 0.006, 0.005, "c8a060", segs=6)
    Pt.seg("Brush", (0, 0, 0.18), (0, 0, 0.23), 0.008, 0.002, "e0a838", segs=6)
    Pt.seg("Palette", (0, 0, 0), (0, 0, 0.008), 0.14, 0.14, "c89060", segs=14)
    for k, col in enumerate(("e0a838", "1a2c60", "f2e08a", "f6f2d0", "101a3a")):
        a = 2 * math.pi * k / 5
        Pt.seg("Palette", (0.09 * math.cos(a), 0.09 * math.sin(a), 0.008), (0.09 * math.cos(a), 0.09 * math.sin(a), 0.014),
               0.022, 0.022, col, segs=8)


class Painting:
    """The canvas on the easel, turned (keyed, degrees about its face's
    normal: 180 = upside down); strip k painted in (0..1, keyed: it fills from
    the strip's top down)."""

    def __init__(self, at, yaw):
        self.at = at
        self.yaw = yaw
        self.turn = Keys().add(0.0, 180.0)
        self.paint = {k: Keys().add(0.0, 0.0) for k in range(len(STRIPS))}

    def frame(self, fis):
        self.turn.done()
        ang = np.array(DF.sample(self.turn), float)[fis]
        q = DF.qmul(DF.qyaw(np.full(len(fis), self.yaw)), _qaxis((0, 1, 0), ang))
        return np.tile(np.array(tuple(self.at)), (len(fis), 1)), q

    def fn_canvas(self):
        def fn(fis, C):
            return self.frame(fis)
        return fn

    def fn_strip(self, k):
        cw = CAN_W / COLS

        def fn(fis, C):
            P0, q = self.frame(fis)
            loc = np.tile((-CAN_W / 2 + (2 * k + 1) * cw, 0.0, CAN_H / 2), (len(fis), 1))
            pk = self.paint[k]
            pk.done()
            u = np.clip(np.array(DF.sample(pk), float)[fis], 0.001, 1.0)
            return P0 + DF.qrot(q, loc), q, np.stack([np.ones_like(u), np.ones_like(u), u], 1)
        return fn

    def point(self, u, v, turn=180.0):
        """World point on the canvas face (u right, v up, metres) as it stands."""
        a = math.radians(self.yaw)
        right = V((math.cos(a), math.sin(a), 0.0))
        out = V((-math.sin(a), math.cos(a), 0.0))
        r = math.radians(turn)
        uu, vv = u * math.cos(r) - v * math.sin(r), u * math.sin(r) + v * math.cos(r)
        return V(tuple(self.at)) + right * uu + V((0, 0, vv)) + out * 0.03


def sat_paint(m, t, t_bow):
    """The finale: the upside-down painting. An easel and a big canvas out of
    the trunk; a palette, a brush; he paints in great sweeps and dabs, strip by
    strip, a picture that makes no sense at all (it's upside down); steps back,
    squints, adds a touch; then turns the canvas over: Paris by night, the
    Eiffel Tower lit gold under the moon. He bows to it."""
    f = m.f
    t = begin(m, t)
    fw = CF._fwd_xy(CF.FIN_FACE)
    rt = V((fw.y, -fw.x, 0))
    spot = V((CF.FIN_SPOT[0] - 0.35 * rt.x + 0.10 * fw.x, CF.FIN_SPOT[1] - 0.35 * rt.y + 0.10 * fw.y, 0.0))
    spot.z = floor_z(spot.x, spot.y)
    yaw = CF.FIN_FACE
    pt = Painting(spot + V((0, 0, 0.80 + CAN_H / 2 + 0.02)), yaw)
    m.prop("Easel", t, ("spot", spot.copy(), DF.qyaw(yaw)), 0)
    m.scale("Easel", t, 0.001, t + 1.0, 1.0)
    m.prop("Canvas", t, ("fn", pt.fn_canvas()), 0)
    m.scale("Canvas", t, 0.001, t + 1.0, 1.0)
    for k, b in enumerate(STRIPS):
        m.prop(b, t, ("fn", pt.fn_strip(k)), 0)
    t = to_trunk(m, t + 0.4)
    t = take(m, t, "L", ["Palette"], ("hand", "L", np.zeros(3), DF.qx(-80.0)))
    t = take(m, t, "R", ["Brush"], ("hand", "R", np.zeros(3), DF.qx(-50.0)))
    # His place: beside the canvas, the audience's side of it.
    stand = (spot.x + 0.55 * rt.x + 0.25 * fw.x, spot.y + 0.55 * rt.y + 0.25 * fw.y)
    t = CF._step_to(m, t, stand)
    face = heading(stand, (spot.x, spot.y))
    t = turn_to(m, t, face)
    pose(m, t + 0.6, L=P(-0.24, 0.30, 1.10), pitch=10)
    t += 0.8
    order = [5, 6, 4, 7, 3, 8, 2, 9, 1, 10, 0, 11]
    per = (t_bow - 2.4 - 26.0 - t) / len(order)
    per = max(5.0, min(8.5, per))
    cw = CAN_W / COLS
    for j, k in enumerate(order):
        x = -CAN_W / 2 + (2 * k + 1) * cw
        n = 8
        for q in range(n + 1):                          # strokes along the strip, down one, up the next
            qq = q if j % 2 == 0 else n - q
            v = CAN_H / 2 - CAN_H * qq / n
            u = x + (0.04 if q % 2 else -0.04)
            # (the strip's top is the canvas's top turned: the bottom as it stands now)
            w = pt.point(u, v, 180.0)
            f.R.add(t + 0.4 + (per - 1.0) * q / n, f.at_world(w))
        pt.paint[k].add(t + 0.4, 0.0).add(t + per - 0.6, 1.0)
        f.lean.add(t + 0.6, 10 + 4 * (j % 2)).add(t + per - 0.4, 6)
        f.pitch.add(t + 0.6, -6 + 10 * (j % 3)).add(t + per - 0.4, 4)
        if j % 4 == 3:                                  # steps back, squints
            pose(m, t + per + 0.6, R=P(0.24, 0.30, 1.10), pitch=-4)
            t += 2.2
        t += per
    pose(m, t + 0.6, R=P(0.20, 0.30, 1.10))
    m.slide(t + 0.4, (stand[0] + 0.30 * fw.x, stand[1] + 0.30 * fw.y), 1.0)
    pose(m, t + 1.6, R=P(0.10, 0.24, 1.60), L=P(-0.24, 0.30, 1.10), pitch=10, yaw=12)   # head on one side
    t += 3.0
    m.slide(t, stand, 0.8)
    pose(m, t + 1.2, R=f.at_world(pt.point(0.10, 0.05, 180.0)))       # a last dab
    pose(m, t + 1.6, R=P(0.24, 0.30, 1.10))
    t += 2.0
    # Turned over: Paris.
    pose(m, t + 0.8, R=f.at_world(pt.point(CAN_W / 2 + 0.02, 0.0, 180.0)), L=HR["L"], lean=8)
    m.prop("Palette", t + 0.5, ("hide",), 0)
    m.prop("Brush", t + 0.5, ("hide",), 0)
    pt.turn.add(t + 1.0, 180.0).add(t + 3.4, 0.0)
    for q in range(5):
        tt = t + 1.0 + 0.6 * q
        ang = 180.0 * (1 - q / 4)
        f.R.add(tt, f.at_world(pt.point(CAN_W / 2 + 0.02, 0.0, ang)))
    t += 3.6
    m.slide(t, (stand[0] + 0.40 * rt.x, stand[1] + 0.40 * rt.y), 1.0)
    t = turn_to(m, t + 1.0, yaw)
    pose(m, t + 0.6, L=P(-0.40, 0.30, 1.40), R=P(0.40, 0.30, 1.40), pitch=-4)   # ta-da
    t += 1.2
    return finish(m, t, t_bow, "the painting", 50, hat=False)


def sat_tidy(m, t):
    for n in ("Easel", "Canvas") + STRIPS:
        m.scale(n, t + 0.5, 1.0, t + 1.2, 0.001)
        m.prop(n, t + 1.25, ("hide",), 0)
    return t + 1.4



# =====================================================================================
# SUNDAY: dance
# =====================================================================================
def sun_robot(m, t, t_bow):
    """Opener: a robot powering up, joint by joint: elbows, wrists, head ticks
    round, a stiff walk across and back, then his batteries run down (he
    sags) and he reboots himself with a thump on the chest."""
    f = m.f
    t = begin(m, t)
    pose(m, t + 1.2, P(-0.20, 0.10, 0.92), P(0.20, 0.10, 0.92), 3, 20, 0)      # off: head down
    t += 1.4
    seq = [(P(-0.20, 0.32, 1.04), P(0.20, 0.10, 0.92), 3, 10, 0), (P(-0.20, 0.32, 1.04), P(0.20, 0.32, 1.04), 3, 0, 0),
           (P(-0.20, 0.32, 1.28), P(0.20, 0.32, 1.04), 3, 0, 30), (P(-0.20, 0.32, 1.28), P(0.20, 0.32, 1.28), 3, 0, -30),
           (P(-0.34, 0.10, 1.28), P(0.34, 0.10, 1.28), 3, 0, 0)]
    for L_, R_, ln, pt, yw in seq:                      # a tick, a hold
        pose(m, t + 0.35, L_, R_, ln, pt, yw)
        pose(m, t + 0.8, L_, R_, ln, pt, yw)
        t += 0.9
    fw = CF._fwd_xy(m.yaw)
    rt = V((fw.y, -fw.x))
    for d in (1, -1):                                   # the stiff walk across and back
        to = (CF.FIN_SPOT[0] + rt.x * 0.45 * d, CF.FIN_SPOT[1] + rt.y * 0.45 * d)
        for q in range(4):
            side = 1 if q % 2 == 0 else -1
            foot = f.fR if side > 0 else f.fL
            sx = 0.10 * side
            foot.add(t + 0.2, P(sx, 0.02, 0.09)).add(t + 0.45, P(sx, 0.10, 0.22)).add(t + 0.7, P(sx, 0.02, 0.09))
            pose(m, t + 0.4, P(-0.20, 0.32 + 0.08 * side, 1.04), P(0.20, 0.32 - 0.08 * side, 1.04), yaw=20 * d)
            t += 0.75
        m.slide(t - 3.0, to, 3.0)
    m.slide(t, CF.FIN_SPOT, 1.0)
    # Run down: slower, sagging, stopped.
    pose(m, t + 1.2, P(-0.20, 0.20, 0.96), P(0.20, 0.20, 0.96), 18, 26, 0)
    t += 2.0
    pose(m, t + 0.6, R=P(0.02, 0.20, 1.30), lean=6, pitch=10)       # thump on the chest: reboot
    pose(m, t + 0.9, R=P(0.02, 0.26, 1.30), lean=2, pitch=-6)
    pose(m, t + 1.6, P(-0.34, 0.20, 1.40), P(0.34, 0.20, 1.40), 3, -4)
    t = ready(m, t + 2.2)
    return finish(m, t, t_bow, "robot", 30)


def sun_cane(m, t, t_bow):
    """Hat and cane: a soft-shoe. The cane out of the trunk; a shuffle and tap,
    the cane tapping the beat; a kick line on his own; leaning on the cane (it
    slips; he doesn't); the cane twirled; a strut round the stage; a turn;
    the hat tipped with the cane's crook; a big finish with the cane up."""
    f = m.f
    t = begin(m, t)
    t = to_trunk(m, t)
    t = take(m, t, "R", ["Cane"], ("hand", "R", np.array((0, 0, -CANE_GRIP)), Q_ID))
    m.hold["R"] = "cane"
    t = centre(m, t)
    fw = CF._fwd_xy(m.yaw)
    rt = V((fw.y, -fw.x))

    def shuffle(t, n, side_step=0.0):
        for q in range(n):
            side = 1 if q % 2 == 0 else -1
            foot = f.fR if side > 0 else f.fL
            sx = 0.10 * side
            foot.add(t + 0.15, P(sx, 0.02, 0.09)).add(t + 0.35, P(sx, 0.18, 0.13)).add(t + 0.55, P(sx, 0.02, 0.09))
            pose(m, t + 0.3, R=P(0.24, 0.32, 0.98 + 0.06 * (q % 2)), lean=4 + 2 * (q % 2))
            if side_step:
                m.slide(t, (m.x + rt.x * side_step, m.y + rt.y * side_step), 0.6)
            t += 0.62
        return t
    t = shuffle(t + 0.4, 10)
    t = shuffle(t, 6, 0.10)
    t = shuffle(t, 6, -0.10)
    # The kick line.
    for q in range(8):
        side = 1 if q % 2 == 0 else -1
        foot = f.fR if side > 0 else f.fL
        sx = 0.10 * side
        foot.add(t + 0.2, P(sx, 0.02, 0.09)).add(t + 0.5, P(sx, 0.40, 0.62)).add(t + 0.85, P(sx, 0.02, 0.09))
        pose(m, t + 0.5, R=P(0.30, 0.20, 1.50 if q % 2 else 1.20), L=P(-0.30, 0.10, 1.30), lean=-4)
        t += 0.9
    pose(m, t + 0.5, L=HR["L"], lean=3)
    # Leaning on the cane: it slides out; he stays leaning on nothing.
    pose(m, t + 1.0, R=P(0.36, 0.24, 0.98), lean=14, twist=12)
    m.prop("Cane", t + 1.0, ("hand", "R", np.array((0, 0, -CANE_GRIP)), DF.qmul(DF.qyaw(0.0), CF._qy(-12.0))), 6)
    m.prop("Cane", t + 2.6, ("hand", "R", np.array((0, 0, -CANE_GRIP)), CF._qy(-40.0)), 4)
    pose(m, t + 2.6, R=P(0.50, 0.24, 0.80))
    pose(m, t + 4.0, R=P(0.36, 0.24, 0.98), lean=14)             # still leaning: on air
    m.prop("Cane", t + 4.6, ("hand", "R", np.array((0, 0, -CANE_GRIP)), Q_ID), 6)
    pose(m, t + 5.2, R=P(0.24, 0.32, 0.98), lean=3, twist=0)
    t += 5.6
    # The twirl.
    for q in range(2):
        for k in range(4):
            m.prop("Cane", t + 0.22 * k, ("hand", "R", np.array((0, 0, -0.42)), CF._qy(-90.0 * (k + 1))), 2)
        t += 0.9
    m.prop("Cane", t, ("hand", "R", np.array((0, 0, -CANE_GRIP)), Q_ID), 4)
    t += 0.4
    # The strut round the stage and a turn.
    loop = [(CF.FIN_SPOT[0] + 0.5 * math.cos(a) * rt.x + 0.30 * math.sin(a) * fw.x,
             CF.FIN_SPOT[1] + 0.5 * math.cos(a) * rt.y + 0.30 * math.sin(a) * fw.y) for a in np.linspace(0, 2 * math.pi, 9)]
    for k, xy in enumerate(loop[1:]):
        m.slide(t, xy, 1.2, heading((m.x, m.y), xy))
        pose(m, t + 0.6, R=P(0.24, 0.40, 1.04 + 0.06 * (k % 2)), L=P(-0.24, 0.10 + 0.08 * (k % 2), 0.98))
        t += 1.2
    t = centre(m, t)
    t = shuffle(t, 12)
    # The hat tipped with the crook, and the big finish.
    pose(m, t + 1.0, R=P(0.16, 0.20, 1.70), L=P(-0.10, 0.06, 1.96), pitch=-4)
    pose(m, t + 1.8, L=P(-0.30, 0.10, 2.02))
    t += 2.4
    while t < t_bow - 2.4 - 12.0:                     # (to the trunk and back from where the slides leave him)
        t = shuffle(t, 8)
    pose(m, t + 1.4, R=P(0.30, 0.20, 1.86), L=P(-0.40, 0.20, 1.40), lean=-4, pitch=-10)
    t += 2.2
    t = to_trunk(m, t)
    t = stow(m, t, "R", ["Cane"], dur=1.6)
    return finish(m, t, t_bow, "hat and cane")


# --- The butterfly -------------------------------------------------------------------------------
kit("Bfly", "BflyWL", "BflyWR")


@mesh
def _bfly_mesh(Pt):
    Pt.seg("Bfly", (0, -0.025, 0), (0, 0.025, 0), 0.005, 0.004, "1c1c1e", segs=5)
    for s_, sx in (("L", -1), ("R", 1)):
        CF._rbox(Pt, f"BflyW{s_}", Matrix.Translation(V((sx * 0.035, 0.008, 0.0))), (0.065, 0.05, 0.002), "f08a20")
        CF._rbox(Pt, f"BflyW{s_}", Matrix.Translation(V((sx * 0.028, -0.026, 0.0))), (0.045, 0.03, 0.002), "e8c040")


class Butterfly(Dove):
    """A butterfly: like the doves (paths, perches) but smaller, fluttering."""

    def fn_wing(self, side):
        sx = -1.0 if side == "L" else 1.0

        def fn(fis, C):
            Pn, Q, flap = self.body(fis, C)
            beat = np.where(flap > 0.5, 60.0 * np.sin(2 * np.pi * 4.2 * fis / FPS), 70.0 + 10 * np.sin(fis * 0.7))
            Qw = DF.qmul(Q, _qaxis((0, 1, 0), -sx * beat))
            return Pn, Qw, self.shown(fis)
        return fn


def _flutter(base, n, rng, r=0.6, z=(1.4, 2.3)):
    return [base + V((rng.uniform(-r, r), rng.uniform(-r, r), rng.uniform(*z))) for _ in range(n)]


def sun_butterfly(m, t, t_bow):
    """The butterfly: he spots something fluttering (nothing there), follows it
    with his eyes, grabs (missed), creeps after it, claps his hands round it:
    caught. Peeks in. Opens his hands: a real butterfly flutters out, round
    his head, settles on his finger, on the brim of his hat, and flies away up
    into the light."""
    f = m.f
    t = begin(m, t)
    t = centre(m, t)
    bf = Butterfly("Bfly")
    m.prop("Bfly", t, ("fn", bf.fn_body()), 0)
    for s_ in "LR":
        m.prop(f"BflyW{s_}", t, ("fn", bf.fn_wing(s_)), 0)
    rng = random.Random("bfly")
    for k in range(6):                                  # watching nothing flit about
        yw = rng.uniform(-50, 50)
        pt = rng.uniform(-30, -5)
        f.yaw.add(t + 0.9 * k + 0.5, yw)
        f.pitch.add(t + 0.9 * k + 0.5, pt)
    t += 5.6
    pose(m, t + 0.6, R=P(0.30, 0.40, 1.70), pitch=-20)          # a grab: missed
    pose(m, t + 1.4, R=P(0.20, 0.30, 1.30), yaw=30)
    t += 2.0
    fw = CF._fwd_xy(m.yaw)
    rt = V((fw.y, -fw.x))
    m.slide(t, (m.x + rt.x * 0.35, m.y + rt.y * 0.35), 2.4)       # creeping after it
    pose(m, t + 1.2, P(-0.20, 0.36, 1.50), P(0.20, 0.36, 1.50), 14, -10, 30)
    t += 2.6
    pose(m, t + 0.5, P(-0.06, 0.42, 1.56), P(0.06, 0.42, 1.56))     # clap: caught
    pose(m, t + 1.4, P(-0.05, 0.30, 1.40), P(0.05, 0.30, 1.40), 6, 10, 0)
    pose(m, t + 2.4, P(-0.05, 0.24, 1.50), P(0.05, 0.24, 1.50), pitch=20)   # a peek
    t += 3.0
    m.slide(t, CF.FIN_SPOT, 1.0)
    # Opened: a real one.
    pose(m, t + 1.0, P(-0.14, 0.40, 1.44), P(0.14, 0.40, 1.44), 3, -4)
    base = V((m.x, m.y, floor_z(m.x, m.y)))
    bf.perch_hand(t + 0.9, "R", (-0.06, 0.0, 0.02))
    for n_ in ("Bfly", "BflyWL", "BflyWR"):
        m.scale(n_, t + 0.9, 0.001, t + 1.1, 1.0)
    pts = [base + V((0.05, 0.0, 1.85)), base + V((0.30, 0.20, 2.10)), base + V((-0.10, 0.40, 1.95)), base + V((-0.35, 0.0, 2.15)),
           base + V((-0.15, -0.25, 2.25)), base + V((0.25, -0.15, 2.05)), base + V((0.20, 0.30, 1.65))]
    bf.fly(t + 1.8, pts, 1.1)
    t_f = t + 1.8 + 1.1 * (len(pts) - 1)
    for k, p_ in enumerate(pts):
        m.look_at(t + 1.8 + 1.1 * k, (p_.x, p_.y))
        f.pitch.add(t + 1.8 + 1.1 * k, -20 if p_.z > base.z + 2.0 else -6)
    pose(m, t + 1.6, P(-0.17, 0.06, 0.87), P(0.20, 0.30, 1.40))
    pose(m, t_f - 0.6, R=P(0.20, 0.30, 1.40))
    bf.perch_hand(t_f, "R", (0.0, 0.03, 0.03))                     # on his finger
    f.yaw.add(t_f + 0.4, 0)
    pose(m, t_f + 1.0, R=P(0.10, 0.36, 1.52), pitch=6)             # brought up to look at it
    t = t_f + 3.0
    hat = base + V((0.0, 0.0, 2.12))
    bf.fly(t, [base + V((0.10, 0.36, 1.92)), base + V((0.20, 0.10, 2.15)), hat], 0.8)
    bf.ev.append((t + 1.6, "body", (0.06, 0.06, 2.10 - 0.0)))
    pose(m, t + 0.8, R=P(0.20, 0.30, 1.30), pitch=-24)
    t += 4.0
    up = [base + V((0.06, 0.06, 2.12)), base + V((0.40, 0.60, 2.40)), base + V((0.20, 1.60, 2.70)), base + V((-0.30, 2.80, 2.85))]
    bf.fly(t, up, 1.2)
    t_gone = t + 1.2 * 3
    for n_ in ("Bfly", "BflyWL", "BflyWR"):
        m.scale(n_, t_gone - 0.6, 1.0, t_gone, 0.001)
    bf.ev.append((t_gone + 0.05, "hide", None))
    m.look_at(t + 2.0, (base.x + fw.x * 2.0, base.y + fw.y * 2.0))
    f.pitch.add(t + 1.0, -30).add(t + 3.6, -20)
    pose(m, t + 1.6, R=P(0.30, 0.24, 1.86), L=P(-0.10, 0.16, 1.40))   # a little wave
    m.butterfly = bf
    t = ready(m, t + 4.0, 1.0)
    f.yaw.add(t, 0)
    return finish(m, t, t_bow, "butterfly", 35)


# --- Hula hoops -------------------------------------------------------------------------------------
HOOPS = ("Hoop0", "Hoop1", "Hoop2")
HOOP_R = (0.46, 0.40, 0.40)
kit(*HOOPS)


@mesh
def _hoop_mesh(Pt):
    for name, r, col in zip(HOOPS, HOOP_R, ("magenta", "cyan", "yellow")):
        n = 30
        for k in range(n):
            a0, a1 = 2 * math.pi * k / n, 2 * math.pi * (k + 1) / n
            Pt.seg(name, (r * math.cos(a0), r * math.sin(a0), 0), (r * math.cos(a1), r * math.sin(a1), 0), 0.012, 0.012,
                   "ffffff", segs=5, caps=False, mat=GLOW_SLOT[col])


class Hoops:
    """Each hoop: in a hand (hanging), round his waist (spinning: its middle
    circling his, the hoop flat, rev/s keyed), round an arm held out (its
    middle circling the wrist in the plane across the arm), round his neck,
    or flying up (tossed: ballistic from the hand)."""

    def __init__(self):
        self.ev = {h: [(0.0, "hide", None)] for h in HOOPS}
        self.rps = {h: Keys().add(0.0, 0.0) for h in HOOPS}

    def evalf(self, h, C):
        r = HOOP_R[HOOPS.index(h)]

        def ang(fs):
            k = self.rps[h]
            k.done()
            return (np.cumsum(np.array(DF.sample(k), float)) / FPS * 2 * np.pi)[fs]

        def f_(mode, arg, fs, t0):
            n = len(fs)
            qb = C["qb"][fs]
            if mode == "hand":
                side = arg
                ctr = C["palm"][side][fs] - np.outer(np.ones(n), (0.0, 0.0, r))
                return ctr, DF.qmul(qb, DF.qx(90.0)), np.zeros(n)
            if mode in ("waist", "neck", "chest"):
                h_ = {"waist": 1.02, "chest": 1.30, "neck": 1.50}[mode]
                body_r = {"waist": 0.15, "chest": 0.16, "neck": 0.07}[mode]
                a = ang(fs)
                off = (r - body_r)
                loc = np.stack([off * np.cos(a), off * np.sin(a), np.full(n, h_)], 1)
                ctr = C["pos"][fs] + DF.qrot(qb, loc)
                tilt = DF.qmul(qb, _qaxis((1, 0, 0), np.full(n, 6.0)))
                return ctr, DF.qmul(tilt, _qaxis((0, 0, 1), np.degrees(a))), np.zeros(n)
            if mode == "arm":                             # round the forearm, the arm held out to the side
                side = arg
                a = ang(fs)
                sx = -1.0 if side == "L" else 1.0
                off = r - 0.05
                loc_off = np.stack([np.zeros(n), off * np.cos(a), off * np.sin(a)], 1)
                ctr = C["palm"][side][fs] + DF.qrot(qb, loc_off + np.array((-sx * 0.10, 0.0, 0.0)))
                q = DF.qmul(qb, DF.qmul(DF.qyaw(np.full(n, 90.0)), DF.qx(90.0)))
                return ctr, DF.qmul(q, _qaxis((0, 0, 1), np.degrees(a))), np.zeros(n)
            # "toss": up from the hand at t0, caught in it again at arg[1]
            side, t1 = arg
            f0, f1 = C["fi"](t0), C["fi"](t1)
            p0 = C["palm"][side][f0] - np.array((0, 0, r))
            p1 = C["palm"][side][f1] - np.array((0, 0, r))
            T = max(0.1, t1 - t0)
            u = np.clip((fs / FPS - t0) / T, 0, 1)
            ctr = p0 + np.outer(u, p1 - p0) + np.outer(0.5 * G * T * T * u * (1 - u), (0, 0, 1))
            spin = DF.qx(90.0 + 720.0 * u)
            return ctr, DF.qmul(qb, spin), np.zeros(n)
        return f_

    def fn(self, h):
        def fn(fis, C):
            Pn, Q, _x, shown = run_events(self.ev[h], fis, self.evalf(h, C), blend=0.5)
            return Pn, Q, np.where(shown, 1.0, 0.001)
        return fn


def sun_hoops(m, t, t_bow):
    """Hula hoops (glowing): one round his waist, his hips going; a second on
    his arm held out, a third on the other; then the waist hoop walked up to
    his chest and his neck and down again; one tossed up spinning and caught
    back onto his waist; all three going at once, and he turns round inside
    them."""
    f = m.f
    t = begin(m, t)
    hp = Hoops()
    for h in HOOPS:
        m.prop(h, t, ("fn", hp.fn(h)), 0)
    t = to_trunk(m, t)
    t = take(m, t, "R", [], dur=1.0)
    for h in HOOPS:
        hp.ev[h].append((t - 0.9, "hand", "R"))
    t = centre(m, t)
    lights(m, t, 2.0, black=0.6, spot=0.6)

    def hips(t0, t1, rps):
        """His hips going round with the hoop (a little circle of the root)."""
        n = int((t1 - t0) * rps * 6)
        x0, y0 = m.x, m.y
        for k in range(n + 1):
            a = 2 * math.pi * rps * (t1 - t0) * k / max(1, n)
            f.root.add(t0 + (t1 - t0) * k / max(1, n), V((x0 + 0.025 * math.cos(a), y0 + 0.025 * math.sin(a), m.yaw)), True)
        f.root.add(t1 + 0.3, V((x0, y0, m.yaw)))
    # One round the waist.
    hp.ev["Hoop0"].append((t + 0.6, "waist", None))
    hp.rps["Hoop0"].add(t + 0.6, 0.0).add(t + 1.4, 1.5)
    pose(m, t + 0.8, P(-0.30, 0.14, 1.40), P(0.30, 0.14, 1.40), 2, 0)
    pose(m, t + 1.4, L=P(-0.24, 0.20, 1.36), R=P(0.18, 0.30, 1.30))
    hips(t + 1.0, t + 10.0, 1.5)
    t += 10.0
    # The second on his right arm, held out.
    hp.ev["Hoop1"].append((t + 0.4, "arm", "R"))
    hp.rps["Hoop1"].add(t + 0.4, 0.0).add(t + 1.2, 1.4)
    pose(m, t + 0.8, R=P(0.62, 0.10, 1.42))
    hips(t, t + 8.0, 1.5)
    t += 8.0
    # The third on his left (from his right hand to his left).
    pose(m, t + 0.8, L=P(-0.10, 0.30, 1.30))
    hp.ev["Hoop2"].append((t + 0.9, "hand", "L"))
    hp.ev["Hoop2"].append((t + 1.6, "arm", "L"))
    hp.rps["Hoop2"].add(t + 1.6, 0.0).add(t + 2.4, 1.4)
    pose(m, t + 1.8, L=P(-0.62, 0.10, 1.42))
    hips(t, t + 10.0, 1.5)
    t += 10.0
    # The waist hoop walked up to his chest and his neck, and back down.
    for where, dur in (("chest", 5.0), ("neck", 6.0), ("chest", 4.0), ("waist", 6.0)):
        hp.ev["Hoop0"].append((t, where, None))
        if where == "neck":
            pose(m, t + 0.6, pitch=-10)
        else:
            pose(m, t + 0.6, pitch=2)
        hips(t, t + dur, 1.5)
        t += dur
    # Arms down: the arm hoops off into his hands; one tossed up and caught back
    # onto his waist? (onto his hand, then the waist).
    pose(m, t + 0.8, P(-0.30, 0.20, 1.20), P(0.30, 0.20, 1.20))
    hp.ev["Hoop1"].append((t + 1.0, "hand", "R"))
    hp.ev["Hoop2"].append((t + 1.0, "hand", "L"))
    hp.rps["Hoop1"].add(t + 1.0, 1.4).add(t + 1.6, 0.0)
    hp.rps["Hoop2"].add(t + 1.0, 1.4).add(t + 1.6, 0.0)
    t += 2.0
    pose(m, t + 0.5, R=P(0.24, 0.30, 1.10))
    pose(m, t + 1.0, R=P(0.20, 0.36, 1.60), pitch=-20)
    hp.ev["Hoop1"].append((t + 1.0, "toss", ("R", t + 1.9)))
    hp.ev["Hoop1"].append((t + 1.9, "hand", "R"))
    pose(m, t + 1.9, R=P(0.20, 0.36, 1.40), pitch=-6)
    t += 3.0
    # All three: waist, both arms out, and a turn inside them.
    pose(m, t + 0.8, P(-0.62, 0.10, 1.42), P(0.62, 0.10, 1.42), 2, -2)
    hp.ev["Hoop1"].append((t + 0.9, "arm", "R"))
    hp.ev["Hoop2"].append((t + 0.9, "arm", "L"))
    hp.rps["Hoop1"].add(t + 0.9, 0.0).add(t + 1.6, 1.4)
    hp.rps["Hoop2"].add(t + 0.9, 0.0).add(t + 1.6, 1.4)
    t_end = t_bow - 2.4 - 9.0
    hips(t, t_end, 1.5)
    t = t_end
    # Down: all three caught, hung on his arm.
    for h in HOOPS:
        hp.rps[h].add(t, 1.5).add(t + 1.2, 0.0)
    pose(m, t + 1.2, P(-0.30, 0.20, 1.30), P(0.30, 0.20, 1.30), 3, 4)
    for h in HOOPS:
        hp.ev[h].append((t + 1.4, "hand", "R"))
    lights(m, t + 0.6, 1.5, black=0.0, spot=1.0)
    t += 2.0
    m.hoops = hp
    return finish(m, t, t_bow, "hula hoops")


def sun_dog(m, t, t_bow):
    """The invisible dog on a lead: it pulls him across the stage, stops dead
    (he nearly trips), runs round him (the lead round his legs: he hops out),
    sits; he pats it; it jumps up at him; a bow, the dog too."""
    f = m.f
    t = begin(m, t)
    t = centre(m, t)
    fw = CF._fwd_xy(m.yaw)
    rt = V((fw.y, -fw.x))
    pose(m, t + 0.8, R=P(0.20, 0.50, 0.95), lean=-8)          # the lead taut
    to = (CF.FIN_SPOT[0] + rt.x * 0.55, CF.FIN_SPOT[1] + rt.y * 0.55)
    t = turn_to(m, t + 0.8, heading((m.x, m.y), to))
    m.slide(t, to, 2.0)
    for q in range(4):
        side = 1 if q % 2 == 0 else -1
        foot = f.fR if side > 0 else f.fL
        foot.add(t + 0.5 * q, P(0.10 * side, 0.02, 0.09)).add(t + 0.5 * q + 0.25, P(0.10 * side, 0.20, 0.20)).add(t + 0.5 * q + 0.5, P(0.10 * side, 0.02, 0.09))
    t += 2.0
    pose(m, t + 0.4, R=P(0.20, 0.30, 0.95), lean=24, pitch=20)     # it stops dead
    t += 1.6
    # Round him: the lead round his legs.
    for k in range(3):
        a = k * 120.0
        pose(m, t + 0.6, R=P(0.30 * math.cos(math.radians(a)), 0.30 * math.sin(math.radians(a)), 0.95), lean=10)
        f.yaw.add(t + 0.6, -60 + 60 * k)
        t += 0.8
    for q in range(2):                                  # hopping out of it
        t = hop(m, t + 0.2, 0.16, 0.7)
    f.yaw.add(t, 0)
    t = turn_to(m, t, CF.FIN_FACE)
    # It sits; he pats it; it jumps up at him.
    t = squat(m, t + 0.3, 0.30, 0.8)
    for q in range(3):
        pose(m, t + 0.3 + 0.4 * q, R=P(0.16, 0.42, 0.70), lean=30)
        pose(m, t + 0.5 + 0.4 * q, R=P(0.16, 0.42, 0.62))
    t = stand_up(m, t + 1.6, 0.6)
    pose(m, t + 0.4, P(-0.24, 0.30, 1.50), P(0.24, 0.30, 1.50), -14, -10)     # whoa
    m.slide(t + 0.3, (m.x - fw.x * 0.20, m.y - fw.y * 0.20), 0.5)
    pose(m, t + 1.4, R=P(0.20, 0.50, 0.95), L=HR["L"], lean=3)
    t = ready(m, t + 2.2)
    t = centre(m, t)
    return finish(m, t, t_bow, "invisible dog", 35)


def sun_flowers(m, t):
    """The gift (Sunday): the butterfly comes back (it was up in the light all
    along), lands on his open hand; he closes his hand round it softly; opens
    it: a bouquet."""
    f = m.f
    t = centre(m, t)
    bf = getattr(m, "butterfly", None)
    if bf is None:                                      # (on its own, a fresh one)
        bf = Butterfly("Bfly")
        m.prop("Bfly", t, ("fn", bf.fn_body()), 0)
        for s_ in "LR":
            m.prop(f"BflyW{s_}", t, ("fn", bf.fn_wing(s_)), 0)
    base = V((m.x, m.y, floor_z(m.x, m.y)))
    fw = CF._fwd_xy(m.yaw)
    pts = [base + V((fw.x * 2.4, fw.y * 2.4, 2.45)), base + V((fw.x * 1.6 + 0.8, fw.y * 1.6 - 0.6, 2.35)),
           base + V((fw.x * 0.8 - 0.6, fw.y * 0.8 + 0.5, 2.4)), base + V((fw.x * 1.2, fw.y * 1.2, 2.0)),
           base + V((0.4, 0.3, 2.1)), base + V((-0.4, 0.2, 1.9)), base + V((0.05, 0.15, 1.95)),
           base + V((0.3, 0.3, 1.7)), base + V((-0.2, 0.2, 1.6)), base + V((0.15, 0.25, 1.55))]
    bf.ev.append((t, "hide", None))
    bf.fly(t + 0.5, pts, 1.3)
    for n_ in ("Bfly", "BflyWL", "BflyWR"):
        m.scale(n_, t + 0.5, 0.001, t + 1.0, 1.0)
    for k, p_ in enumerate(pts):
        m.look_at(t + 0.5 + 1.3 * k, (p_.x, p_.y))
        f.pitch.add(t + 0.5 + 1.3 * k, -24 + 5 * k)
    t_land = t + 0.5 + 1.3 * (len(pts) - 1)
    pose(m, t_land - 1.0, R=P(0.16, 0.34, 1.46))
    bf.perch_hand(t_land, "R", (0.0, 0.0, 0.03))
    f.yaw.add(t_land + 0.4, 0)
    t = t_land + 2.0
    pose(m, t + 0.8, L=P(0.06, 0.34, 1.52), R=P(0.12, 0.34, 1.46), pitch=10)      # closed round it
    for n_ in ("Bfly", "BflyWL", "BflyWR"):
        m.scale(n_, t + 0.9, 1.0, t + 1.1, 0.001)
    bf.ev.append((t + 1.15, "hide", None))
    t += 2.0
    pose(m, t + 0.6, L=P(-0.20, 0.34, 1.40), R=P(0.18, 0.40, 1.46), pitch=-2)   # opened: flowers
    m.prop("Bouquet", t + 0.6, ("hand", "R", np.array((0.0, 0.0, 0.02)), Q_ID), 0)
    m.scale("Bouquet", t + 0.6, 0.001, t + 1.0, 1.0)
    pose(m, t + 1.6, L=HR["L"], R=CF.GIFT_HOLD, pitch=4)
    m.hold["R"] = "bouquet"
    return t + 1.8


# --- Sparklers ---------------------------------------------------------------------------------------
SPARKS = tuple(f"Spark{i}" for i in range(54))
SPK_TR = [f"SpkT{s}{k}" for s in "LR" for k in range(1, 9)]
kit("SpkL", "SpkR", "SpkFL", "SpkFR", *SPARKS, *SPK_TR, "Fountain", "FountF")
SPK_STICK = 0.42
Q_SPK = DF.qx(-40.0)


@mesh
def _sparkler_mesh(Pt):
    for b in ("SpkL", "SpkR"):
        Pt.seg(b, (0, 0, -0.02), (0, 0, SPK_STICK), 0.0035, 0.0035, "6a6e74", segs=4)
        Pt.seg(b, (0, 0, SPK_STICK * 0.45), (0, 0, SPK_STICK), 0.006, 0.006, "3a3a3e", segs=5)
    for b in ("SpkFL", "SpkFR") + tuple(SPK_TR):
        CF._sphere(Pt, b, 0.022, "fff4d0", 1, segs=8, rings=5)
    for b in SPARKS:
        CF._sphere(Pt, b, 0.008, "fff0b0", 1, segs=5, rings=3)
    Pt.seg("Fountain", (0, 0, 0), (0, 0, 0.16), 0.05, 0.035, "c8202e", segs=10)
    Pt.seg("Fountain", (0, 0, 0.16), (0, 0, 0.18), 0.036, 0.02, "e8c040", segs=10)
    CF._sphere(Pt, "FountF", 0.03, "fff4d0", 1, segs=8, rings=5)


class Sparklers:
    """Two sparklers in his hands (their tips burning while lit), sparks thrown
    off the tips (and a fountain on the stage at the end): each spark bone is
    used over and over, a short life each time."""

    def __init__(self):
        self.lit = {s: Keys().add(0.0, 0.0) for s in "LR"}
        self.spawn = {sp: [] for sp in SPARKS}          # (t0, source, velocity, life)
        self.fountain = None                            # (t0, t1, where)

    def tip(self, C, side, fs):
        qb = C["qb"][fs]
        return C["palm"][side][fs] + DF.qrot(DF.qmul(qb, Q_SPK), np.tile((0.0, 0.0, SPK_STICK), (len(fs), 1)))

    def fn_tip(self, side):
        def fn(fis, C):
            k = self.lit[side]
            k.done()
            lit = np.array(DF.sample(k), float)[fis]
            fl = 1.0 + 0.25 * np.sin(fis * 2.3 + (0 if side == "L" else 1))
            S = np.stack([lit * fl] * 3, 1)
            return self.tip(C, side, fis), np.tile(Q_ID, (len(fis), 1)), np.maximum(S, 0.001)
        return fn

    def plan(self, t0, t1, rng):
        """Spread spawns over the spark bones from each lit source, t0..t1."""
        srcs = []
        tt = t0
        while tt < t1:
            for side in "LR":
                k = self.lit[side]
                k.done()
                if RF.track(k, tt) > 0.5:
                    srcs.append((tt, side))
            if self.fountain and self.fountain[0] <= tt < self.fountain[1]:
                srcs.append((tt, "F"))
                srcs.append((tt + 0.03, "F"))
            tt += 0.05
        free = {sp: -1.0 for sp in SPARKS}
        for t_s, src in srcs:
            sp = min(free, key=free.get)
            if free[sp] > t_s:
                continue
            life = rng.uniform(0.35, 0.8) if src != "F" else rng.uniform(0.7, 1.2)
            if src == "F":
                v = np.array((rng.uniform(-0.35, 0.35), rng.uniform(-0.35, 0.35), rng.uniform(2.6, 3.4)))
            else:
                a = rng.uniform(0, 2 * math.pi)
                e = rng.uniform(-0.4, 1.0)
                sp_ = rng.uniform(0.8, 1.7)
                v = np.array((math.cos(a) * math.cos(e), math.sin(a) * math.cos(e), math.sin(e))) * sp_
            self.spawn[sp].append((t_s, src, v, life))
            free[sp] = t_s + life + 0.02

    def fn_spark(self, sp):
        def fn(fis, C):
            tt = fis / FPS
            n = len(fis)
            Pn = np.zeros((n, 3))
            S = np.full(n, 0.001)
            for t0, src, v, life in self.spawn[sp]:
                sel = (tt >= t0) & (tt < t0 + life)
                if not sel.any():
                    continue
                f0 = np.array([C["fi"](t0)])
                if src == "F":
                    p0 = np.array(tuple(self.fountain[2])) + np.array((0, 0, 0.18))
                else:
                    p0 = self.tip(C, src, f0)[0]
                s = tt[sel] - t0
                Pn[sel] = p0 + np.outer(s, v) - np.outer(0.5 * G * s * s, (0, 0, 1))
                S[sel] = np.clip(1.0 - s / life, 0.1, 1.0)
            return Pn, np.tile(Q_ID, (n, 1)), np.maximum(S, 0.001)
        return fn


def _heart(u):
    """A heart drawn in the air (u 0..1), in his frame's front plane, metres."""
    a = 2 * math.pi * u
    x = 16 * math.sin(a) ** 3
    z = 13 * math.cos(a) - 5 * math.cos(2 * a) - 2 * math.cos(3 * a) - math.cos(4 * a)
    return 0.016 * x, 0.016 * z


def sun_sparklers(m, t, t_bow):
    """The finale: sparklers in the dark. Two out of the trunk, lit off his
    fingertip; the house black; he draws with them: circles, a figure eight,
    spirals, a heart for the café lady, his trails of light hanging in the
    air; spins them like Catherine wheels; dances; then sets a fountain on
    the front of the stage that throws a column of sparks up into the dark
    while he bows beside it."""
    f = m.f
    t = begin(m, t)
    t = to_trunk(m, t)
    sk = Sparklers()
    st = {"SpkL": ("hand", "L", np.zeros(3), Q_SPK), "SpkR": ("hand", "R", np.zeros(3), Q_SPK),
          "SpkFL": ("fn", sk.fn_tip("L")), "SpkFR": ("fn", sk.fn_tip("R"))}
    f.L.hold(t).add(t + 1.0, f.at_world(trunk_point(-0.10)))
    t = take(m, t, "R", ["SpkR", "SpkFR"], lambda n: st[n])
    m.prop("SpkL", t - 1.0, st["SpkL"], 0)
    m.prop("SpkFL", t - 1.0, st["SpkFL"], 0)
    m.scale("SpkL", t - 1.0, 0.001, t - 0.6, 1.0)
    m.trails = getattr(m, "trails", []) + [(f"SpkT{s}{k}", f"SpkF{s}", k / FPS, 0.95 - 0.08 * k)
                                          for s in "LR" for k in range(1, 9)]
    for n_ in SPK_TR:
        m.prop(n_, t, ("spot", V((CF.FIN_SPOT[0], CF.FIN_SPOT[1], 0.5)), Q_ID), 0)
    for sp in SPARKS:
        m.prop(sp, t, ("fn", sk.fn_spark(sp)), 0)
    t = centre(m, t)
    # Lit off his fingertip.
    pose(m, t + 0.8, P(-0.10, 0.34, 1.30), P(0.14, 0.34, 1.20), 4, 10)
    m.fire.add(t + 1.0, 0.0).add(t + 1.2, 1.0)
    sk.lit["L"].add(t + 1.8, 0.0).add(t + 2.1, 1.0)
    pose(m, t + 2.2, R=P(0.10, 0.36, 1.34))
    sk.lit["R"].add(t + 2.6, 0.0).add(t + 2.9, 1.0)
    m.fire.add(t + 2.9, 1.0).add(t + 3.1, 0.0)
    t += 3.4
    lights(m, t, 2.5, black=1.0, spot=0.15)
    m.beam.add(t, 1.0).add(t + 2.5, 0.3)
    t += 2.6
    t0_spk = t

    def trace(t, dur, fn_l, fn_r, n=40):
        DF.hold_live(f.L, t)
        DF.hold_live(f.R, t)
        f.L.add(t + 1.0, fn_l(0.0))
        f.R.add(t + 1.0, fn_r(0.0))
        for k in range(1, n + 1):
            u = k / n
            f.L.add(t + 1.0 + dur * u, fn_l(u), lin=True)
            f.R.add(t + 1.0 + dur * u, fn_r(u), lin=True)
        return t + 1.0 + dur
    # Circles (mirrored), a figure eight, spirals.
    t = trace(t, 6.0, lambda u: P(-0.30 + 0.24 * math.cos(2 * math.pi * 2 * u), 0.40, 1.40 + 0.24 * math.sin(2 * math.pi * 2 * u)),
              lambda u: P(0.30 - 0.24 * math.cos(2 * math.pi * 2 * u), 0.40, 1.40 + 0.24 * math.sin(2 * math.pi * 2 * u)))
    t = trace(t, 7.0, lambda u: P(-0.20, 0.30, 1.10),
              lambda u: P(0.10 + 0.28 * math.sin(2 * math.pi * 2 * u), 0.44, 1.45 + 0.22 * math.sin(4 * math.pi * u)))
    t = trace(t, 7.0, lambda u: P(-0.06 - 0.30 * u * math.cos(2 * math.pi * 3 * u), 0.42, 1.40 + 0.30 * u * math.sin(2 * math.pi * 3 * u)),
              lambda u: P(0.06 + 0.30 * u * math.cos(2 * math.pi * 3 * u), 0.42, 1.40 + 0.30 * u * math.sin(2 * math.pi * 3 * u)))
    # The heart, toward the café lady (he turns to her side of the room).
    lady = RF.CAB_SEATS["A"][:2]
    t = turn_to(m, t, heading((m.x, m.y), lady))
    t = trace(t, 6.0, lambda u: P(-0.22, 0.20, 1.10),
              lambda u: P(_heart(u)[0], 0.46, 1.42 + _heart(u)[1] * 0.85), n=48)
    t = trace(t, 6.0, lambda u: P(-0.22, 0.20, 1.10),
              lambda u: P(_heart(u)[0], 0.46, 1.42 + _heart(u)[1] * 0.85), n=48)
    pose(m, t + 0.8, P(-0.20, 0.20, 1.10), P(0.20, 0.40, 1.60), 6, -4)          # it's for her
    t += 1.6
    t = turn_to(m, t, CF.FIN_FACE)
    # Catherine wheels: arms out, the sparklers spun in circles, and he turns.
    t = trace(t, 8.0, lambda u: P(-0.50 + 0.14 * math.cos(2 * math.pi * 6 * u), 0.20, 1.42 + 0.14 * math.sin(2 * math.pi * 6 * u)),
              lambda u: P(0.50 + 0.14 * math.cos(2 * math.pi * 6 * u + math.pi), 0.20, 1.42 + 0.14 * math.sin(2 * math.pi * 6 * u + math.pi)), n=72)
    f.put(t - 8.0, m.x, m.y, m.yaw, lin=True)
    f.root.add(t - 4.0, V((m.x, m.y, m.yaw + 180.0)), True)
    f.root.add(t, V((m.x, m.y, m.yaw + 360.0)))
    f._yaw = m.yaw = m.yaw + 360.0
    # A dance: steps side to side, the sparklers swinging in arcs.
    fw = CF._fwd_xy(m.yaw)
    rt = V((fw.y, -fw.x))
    t_f = t_bow - 2.4 - 26.0
    k = 0
    while t < t_f - 3.0:
        d = 0.30 if k % 2 == 0 else -0.30
        m.slide(t, (CF.FIN_SPOT[0] + rt.x * d, CF.FIN_SPOT[1] + rt.y * d), 1.4)
        t = trace(t, 2.0, lambda u, d=d: P(-0.30 + 0.20 * math.sin(math.pi * u), 0.36, 1.20 + 0.40 * math.sin(math.pi * u)),
                  lambda u, d=d: P(0.30 - 0.20 * math.sin(math.pi * u), 0.36, 1.60 - 0.40 * math.sin(math.pi * u)), n=12)
        k += 1
    t = centre(m, t)
    # The fountain: set on the front of the stage, lit; he steps back beside it.
    fw = CF._fwd_xy(m.yaw)
    spot = V((m.x + fw.x * 0.55, m.y + fw.y * 0.55, 0.0))
    spot.z = floor_z(spot.x, spot.y)
    pose(m, t + 1.0, L=f.at_world(spot + V((0, 0, 0.30))), lean=40, pitch=30)
    m.prop("Fountain", t + 1.0, ("spot", spot.copy(), Q_ID), 0)
    m.scale("Fountain", t + 1.0, 0.001, t + 1.3, 1.0)
    m.prop("FountF", t + 1.0, ("spot", spot + V((0, 0, 0.19)), Q_ID), 0)
    m.scale("FountF", t + 1.0, 0.001, t + 1.1, 0.001)
    pose(m, t + 2.2, R=f.at_world(spot + V((0, 0, 0.32))))
    sk.fountain = (t + 2.6, t_bow + 4.0, spot)
    m.scale("FountF", t + 2.6, 0.001, t + 2.9, 1.4)
    pose(m, t + 3.2, P(-0.30, 0.30, 1.40), P(0.30, 0.30, 1.40), 3, -6)
    m.slide(t + 3.0, (m.x - fw.x * 0.20 + rt.x * 0.35, m.y - fw.y * 0.20 + rt.y * 0.35), 1.2)
    t += 4.6
    for s_ in "LR":
        sk.lit[s_].add(t_bow - 6.0, 1.0).add(t_bow - 5.0, 0.0)
    m.scale("FountF", t_bow + 3.5, 1.4, t_bow + 4.0, 0.001)
    sk.plan(t0_spk - 2.0, t_bow + 4.0, random.Random("sparks"))
    lights(m, t_bow + 2.5, 2.5, black=0.0, spot=1.0)
    m.beam.add(t_bow + 2.5, 0.3).add(t_bow + 5.0, 1.0)
    m.sparklers = sk
    t = CF._land(m, t, t_bow, "sparklers")
    t = m.bow(t, 50, "pub", hat=False)
    m.acts.append((m.act_t0, t, "sparklers", "pub"))
    return t


def sun_tidy(m, t):
    t = to_trunk(m, t)
    names = ["SpkL", "SpkR", "SpkFL", "SpkFR"] + SPK_TR
    t = stow(m, t, "R", names)
    for n_ in ("Fountain", "FountF") + HOOPS:
        m.scale(n_, t, 1.0, t + 0.6, 0.001)
        m.prop(n_, t + 0.65, ("hide",), 0)
    m.hold["L"] = None
    return CF._back(m, t, 0.8)


import os                                           # noqa: E402
_READY = {"mon": ((mon_marionette, mon_diabolo, mon_crystal, mon_lasso, mon_cane, mon_bloom, mon_poi), mon_tidy),
          "tue": ((tue_levitate, tue_table, tue_cards, tue_rings, tue_paper, tue_cone, tue_doves), tue_tidy),
          "wed": ((wed_chase, wed_boxes, wed_five, wed_devil, wed_chair, wed_flowers, wed_plates), wed_tidy),
          "thu": ((thu_windup, thu_knives, thu_yoyo, thu_balloons, thu_wind, thu_flame, thu_snow), thu_tidy),
          "sat": ((sat_ladder, sat_glow, sat_umbrella, sat_ribbon, sat_tug, sat_hat, sat_paint), sat_tidy),
          "sun": ((sun_robot, sun_cane, sun_butterfly, sun_hoops, sun_dog, sun_flowers, sun_sparklers), sun_tidy)}
# (A night's programme goes live once it is finished: LOUNGE_NIGHTS lists the
# ones in this build, "all" for every one ready.)
_live = os.environ.get("LOUNGE_NIGHTS", "")
for _n, _p in _READY.items():
    if _live == "all" or _n in _live.split(","):
        CF.PROGRAMS[_n] = _p

# --- Registering the kit with the prop rig ---------------------------------------------------
CF.DYNAMIC = CF.DYNAMIC + tuple(KIT)
CF.MESH_HOOKS[:] = MESHES
CF.EXTRA_MATS[:] = [_crystal_mat] + [_glow_mat(n, rgb) for n, rgb in GLOW_COLS.items()]
CF.FAST = CF.FAST + ("Poi", "Dia", "Honda", "Spoke", "Loop", "Cane", "Card", "Dove", "MTable", "MCloth", "Box", "Dev",
                     "Plate", "TKnife", "TBoard", "Bal", "YoYo", "YoStr", "BDog", "BSword", "Snow", "SFan", "WKey",
                     "Glow", "Rain", "Umb", "Rib", "Easel", "Canvas", "Strip", "Brush", "Palette", "Bfly", "Hoop", "Spk",
                     "Spark", "Fount")
