# Patio -> rooftop cocktail lounge (exec'd from build-penthouse.py's finish pass,
# so it shares its globals: rv_box, mal_cyl, mk, artmat, region_delete_mats, ...).
#
# Jay asked (2026-10-04) for the BBQ patio cleared and turned into a fancy
# cocktail lounge with its own bar, where the dinner party goes after supper to
# look at the view of New York and mingle; one waiter works the floor, the
# other the bar. The patio is the glass box x -5.35..5.95, y 4.0..9.84 between
# the Malibu lounge (west, open at x -5.4 for y 4.05..5.3), the house (south
# glass) and the dining room (east glass), with the glass balustrade and the
# skyline to the north.
#
# Plan (dinner_figures.py COCKTAIL_* must match):
#   - the bar against the south glass, centred on the solid pier (x -0.1..0.9):
#     counter x -1.40..2.20, front face y 5.50, bartender's aisle y 4.47..4.92,
#     back bar of lit shelves and bottles on the glass; the east end of the
#     counter (x 1.3..2.2) is the waiters' pick-up, three stools to its west;
#   - a velvet sofa and two leather club chairs round a marble table in the
#     west (clear of the way in from the Malibu lounge), a loveseat and two
#     chairs in the east (clear of the dining-room door);
#   - three high marble cocktail tables near the balustrade for people who
#     stand, and an open lane from the dining-room door (y ~7.9) west along
#     the patio;
#   - a French door: the north leaf of the dining room's west window slid open
#     (glass y 7.35..8.35), so nobody walks through glass to get in and out.
CK_BAR_X = (-1.40, 2.20)
CK_BAR_Y = (5.00, 5.50)           # counter body, front (public) face at 5.50
CK_BAR_Z = 1.08
CK_BACK_Y = (4.06, 4.36)          # back bar cabinet against the south glass; aisle 4.39..5.0
CK_STOOLS = (-1.05, -0.25, 0.55)  # bar stools (x), seats at y 5.95
CK_STOOL_Y = 5.95
CK_POSEUR = ((-2.90, 8.75), (0.30, 8.85), (3.20, 8.75))
CK_DOOR_Y = (7.35, 8.35)

# --- Clear the patio -----------------------------------------------------------
region_delete_mats(-4.4, -0.5, 4.8, 8.7, 0.0, 1.3, {'PatioCushionCanvas', 'PatioResinWicker'}, "patio-sectional")
region_delete_mats(0.05, 1.20, 5.90, 8.60, -0.06, 1.70,
                   {'BBQSteel', 'BBQLedgestone', 'BBQGranite', 'fake_mat_230_220_187_255', 'fake_mat_69_64_65_255'},
                   "patio-bbq")
delete_object_faces(("Object_65",), 3.0, 5.05, 5.1, 8.0, -0.01, 1.2, "patio-terrace-set")
delete_object_faces(("Object_69",), 0.2, 5.85, 4.2, 9.5, 0.01, 2.6, "patio-dark-bits")
delete_object_faces(("Object_50",), 0.0, 1.3, 5.8, 8.7, 0.01, 2.0, "patio-bbq-tools")
# z from -0.01: the sectional's leg pads and base slabs sit at z 0 (exported as
# -0.0), double-sided and coplanar with the floor, and shimmered once the
# sofa above them was gone (2026-10-06).
delete_object_faces(("Object_45", "Object_54", "Object_67"), -4.4, -0.5, 4.8, 8.7, -0.01, 1.3, "patio-sectional-rest")
delete_object_faces(("Object_68",), 2.4, 2.9, 5.3, 6.0, -0.01, 0.4, "patio-debris")

# --- Materials -------------------------------------------------------------------
M_CK_VELVET = mk('CockVelvet', '1E4A3B', 0.95)            # emerald velvet
M_CK_LEATHER = mk('CockLeather', '6A3A1F', 0.55)          # cognac leather
M_CK_WOOD = mk('CockWood', '2A1B14', 0.45)                # ebonised walnut
M_CK_RUG = mk('CockRug', '2B2A31', 0.95)
M_CK_RUGB = mk('CockRugBorder', '8A7346', 0.9)
M_CK_STONE = M_MARB                                       # white marble (ensuite)
M_CK_BLACK = mk('CockStoneBlack', '1A1A1C', 0.25)
M_CK_GLOW = mk('CockGlow', '2A2016', 0.5)
_g = M_CK_GLOW.node_tree.nodes['Principled BSDF']
_g.inputs['Emission Color'].default_value = (1.0, 0.78, 0.48, 1)
_g.inputs['Emission Strength'].default_value = 1.6
M_CK_GLOBE = mk('CockGlobe', 'F2E6C8', 0.5)
_g = M_CK_GLOBE.node_tree.nodes['Principled BSDF']
_g.inputs['Emission Color'].default_value = (1.0, 0.86, 0.62, 1)
_g.inputs['Emission Strength'].default_value = 2.2
M_CK_BOTTLES = [mk(f'CockBottle{i}', h, 0.15) for i, h in enumerate(('6B3A12', '2F5A2A', 'C8C2B0', '8A1E24', '3A3020'))]


def ck_box(name, x1, x2, y1, y2, z1, z2, mat, scale=None):
    return rv_box(name, x1, x2, y1, y2, z1, z2, mat, scale)


def ck_cyl(name, x, y, z1, z2, r, mat, verts=20, r2=None):
    return mal_cyl(name, x, y, (z1 + z2) / 2, r, z2 - z1, mat, verts=verts, r2=r2)


# --- The bar -----------------------------------------------------------------------
bx1, bx2 = CK_BAR_X
by1, by2 = CK_BAR_Y
ck_box("CkBarBody", bx1, bx2, by1, by2, 0.0, CK_BAR_Z - 0.04, M_CK_WOOD)
for k in range(int((bx2 - bx1) / 0.12)):                  # fluted front
    x = bx1 + 0.06 + k * 0.12
    ck_box(f"CkBarFlute{k}", x - 0.035, x + 0.035, by2, by2 + 0.025, 0.10, CK_BAR_Z - 0.10, M_CK_WOOD)
ck_box("CkBarKick", bx1, bx2, by2, by2 + 0.035, 0.0, 0.10, M_BRASS)
ck_box("CkBarTrim", bx1, bx2, by2, by2 + 0.035, CK_BAR_Z - 0.10, CK_BAR_Z - 0.04, M_BRASS)
ck_box("CkBarTop", bx1 - 0.05, bx2 + 0.05, by1 - 0.03, by2 + 0.10, CK_BAR_Z - 0.04, CK_BAR_Z, M_CK_STONE)
# Foot rail along the stools only: the east end of the counter is the waiters'
# pick-up, where they stand right up to it.
RAIL_X = (bx1 + 0.10, 1.05)
mal_cyl("CkBarRail", sum(RAIL_X) / 2, by2 + 0.24, 0.22, 0.022, RAIL_X[1] - RAIL_X[0], M_BRASS, verts=10,
        rot=(0, math.pi / 2, 0))
for k, x in enumerate((RAIL_X[0] + 0.2, sum(RAIL_X) / 2, RAIL_X[1] - 0.2)):
    ck_box(f"CkBarRailFoot{k}", x - 0.012, x + 0.012, by2 + 0.035, by2 + 0.24, 0.20, 0.24, M_BRASS)
# Back bar: cabinet with a marble top, three lit glass shelves of bottles above.
cy1, cy2 = CK_BACK_Y
ck_box("CkBackCab", bx1, bx2, cy1, cy2, 0.0, 0.92, M_CK_WOOD)
ck_box("CkBackTop", bx1 - 0.03, bx2 + 0.03, cy1, cy2 + 0.03, 0.92, 0.96, M_CK_STONE)
ck_box("CkBackGlow", bx1, bx2, cy1, cy1 + 0.02, 0.96, 2.30, M_CK_GLOW)
for nm, x1, x2 in (("W", bx1 - 0.05, bx1), ("E", bx2, bx2 + 0.05)):
    ck_box(f"CkBackPost{nm}", x1, x2, cy1, cy2, 0.0, 2.36, M_BRASS)
ck_box("CkBackHead", bx1 - 0.05, bx2 + 0.05, cy1, cy2, 2.30, 2.40, M_CK_WOOD)
_rng = random.Random("cocktail-bottles")
for s, z in enumerate((1.22, 1.58, 1.94)):
    ck_box(f"CkBackShelf{s}", bx1, bx2, cy1 + 0.02, cy2 - 0.06, z - 0.015, z, M_BRASS)
    x = bx1 + 0.08
    while x < bx2 - 0.08:
        h = _rng.uniform(0.24, 0.32)
        m = _rng.choice(M_CK_BOTTLES)
        ck_cyl(f"CkBottle{s}_{int(x * 100)}", x, (cy1 + cy2) / 2 - 0.04, z, z + h * 0.72, 0.035, m, verts=8)
        ck_cyl(f"CkBottleNeck{s}_{int(x * 100)}", x, (cy1 + cy2) / 2 - 0.04, z + h * 0.72, z + h, 0.012, m, verts=6,
               r2=0.010)
        x += _rng.uniform(0.09, 0.14)
# Pendants over the counter.
for k, x in enumerate((-0.80, 0.40, 1.60)):
    mal_cyl(f"CkPendRod{k}", x, (by1 + by2) / 2, 2.62, 0.006, 0.52, M_BRASS, verts=6)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=14, ring_count=7, radius=0.12, location=(x, (by1 + by2) / 2, 2.30))
    bpy.context.active_object.name = f"CkGlowPend{k}"
    bpy.context.active_object.data.materials.append(M_CK_GLOBE)
# Stools.
for k, x in enumerate(CK_STOOLS):
    ck_cyl(f"CkStoolSeat{k}", x, CK_STOOL_Y, 0.70, 0.77, 0.20, M_CK_VELVET)
    ck_cyl(f"CkStoolRing{k}", x, CK_STOOL_Y, 0.66, 0.70, 0.17, M_BRASS)
    ck_cyl(f"CkStoolLeg{k}", x, CK_STOOL_Y, 0.03, 0.66, 0.03, M_BRASS, verts=8)
    ck_cyl(f"CkStoolFoot{k}", x, CK_STOOL_Y, 0.25, 0.27, 0.15, M_BRASS)
    ck_cyl(f"CkStoolBase{k}", x, CK_STOOL_Y, 0.0, 0.03, 0.19, M_BRASS)


# --- Lounge seating ------------------------------------------------------------------
def ck_sofa(tag, cx, cy, yaw, length, mat, seats):
    """Low sofa centred on (cx, cy) facing yaw (0 = +y). Cushions get 5 cm gaps
    so the seat snapper keeps each seat on its own cushion."""
    def frame(lx1, lx2, ly1, ly2, z1, z2, m, nm):
        rv_rbox(f"Ck{tag}{nm}", (cx, cy), math.radians(yaw), lx1, lx2, ly1, ly2, z1, z2, m)
    L = length / 2
    frame(-L, L, -0.40, 0.42, 0.06, 0.40, mat, "Base")
    frame(-L, L, -0.42, -0.24, 0.40, 0.82, mat, "Back")
    frame(-L - 0.14, -L, -0.42, 0.42, 0.06, 0.62, mat, "ArmL")
    frame(L, L + 0.14, -0.42, 0.42, 0.06, 0.62, mat, "ArmR")
    cw = (length - 0.05 * (seats - 1)) / seats
    for k in range(seats):
        x0 = -L + k * (cw + 0.05)
        frame(x0, x0 + cw, -0.24, 0.40, 0.40, 0.50, mat, f"Cush{k}")
    for k, (lx, ly) in enumerate(((-L + 0.05, -0.35), (L - 0.05, -0.35), (-L + 0.05, 0.37), (L - 0.05, 0.37))):
        px, py = local_pt((cx, cy), math.radians(yaw), lx, ly)
        ck_cyl(f"Ck{tag}Foot{k}", px, py, 0.0, 0.06, 0.025, M_BRASS, verts=8)


def ck_chair(tag, cx, cy, yaw):
    ck_sofa(tag, cx, cy, yaw, 0.62, M_CK_LEATHER, 1)


def ck_table(tag, x, y, r, z, top=M_CK_STONE):
    ck_cyl(f"Ck{tag}Top", x, y, z - 0.03, z, r, top, verts=24)
    ck_cyl(f"Ck{tag}Stem", x, y, 0.04, z - 0.03, 0.04 if z > 0.6 else r * 0.55, M_BRASS, verts=12)
    ck_cyl(f"Ck{tag}Base", x, y, 0.0, 0.04, min(r, 0.24), M_BRASS, verts=16)


# West: sofa with its back to the Malibu glass, two chairs facing it.
ck_box("CkRugW", -5.05, -2.05, 5.25, 7.55, 0.004, 0.012, M_CK_RUGB)
ck_box("CkRugWIn", -4.95, -2.15, 5.35, 7.45, 0.006, 0.014, M_CK_RUG)
ck_sofa("SofaW", -4.62, 6.40, -90, 1.60, M_CK_VELVET, 2)
ck_chair("ChairW1", -2.60, 5.95, 90)
ck_chair("ChairW2", -2.60, 6.85, 90)
ck_table("TableW", -3.62, 6.40, 0.42, 0.42, M_CK_BLACK)
# East: loveseat against the house glass, two chairs facing it.
ck_box("CkRugE", 3.05, 5.45, 4.35, 6.95, 0.004, 0.012, M_CK_RUGB)
ck_box("CkRugEIn", 3.15, 5.35, 4.45, 6.85, 0.006, 0.014, M_CK_RUG)
ck_sofa("SofaE", 4.20, 4.72, 0, 1.40, M_CK_VELVET, 2)
ck_chair("ChairE1", 3.65, 6.30, 180)
ck_chair("ChairE2", 4.75, 6.30, 180)
ck_table("TableE", 4.20, 5.55, 0.36, 0.42, M_CK_BLACK)
# Standing: high marble cocktail tables by the balustrade.
for k, (x, y) in enumerate(CK_POSEUR):
    ck_table(f"Poseur{k}", x, y, 0.30, 1.08)
# A planter west of the bar (the east end is the bartender's way in).
ck_cyl("CkPlanter0", bx1 - 0.60, 4.40, 0.0, 0.62, 0.26, M_CK_BLACK)
plant("CkPlant0", bx1 - 0.60, 4.40, 0.62, 1.1, 0.0)

# --- The French door from the dining room ------------------------------------------
dy1, dy2 = CK_DOOR_Y
cut_opening(5.84, 6.14, dy1, dy2, 0.015, 2.47, "dining-french-door")
# The leaf, slid open in front of the middle pane (patio side), in the window's
# dark frame colour, and a flush threshold where the sill was.
M_CK_FRAME = bpy.data.materials.get('fake_mat_6_5_5_255') or M_CK_WOOD
LW = dy2 - dy1
lx = 5.90
ck_box("CkDoorLeafRailB", lx - 0.02, lx + 0.02, dy1 - LW + 0.02, dy1 + 0.02, 0.02, 0.10, M_CK_FRAME)
ck_box("CkDoorLeafRailT", lx - 0.02, lx + 0.02, dy1 - LW + 0.02, dy1 + 0.02, 2.40, 2.46, M_CK_FRAME)
ck_box("CkDoorLeafStileS", lx - 0.02, lx + 0.02, dy1 - LW + 0.02, dy1 - LW + 0.07, 0.02, 2.46, M_CK_FRAME)
ck_box("CkDoorLeafStileN", lx - 0.02, lx + 0.02, dy1 - 0.03, dy1 + 0.02, 0.02, 2.46, M_CK_FRAME)
if M_GLASSP:
    ck_box("CkDoorLeafGlass", lx - 0.004, lx + 0.004, dy1 - LW + 0.07, dy1 - 0.03, 0.10, 2.40, M_GLASSP)
ck_box("CkDoorHandle", lx - 0.05, lx - 0.02, dy1 - 0.10, dy1 - 0.07, 0.95, 1.15, M_BRASS)
flat_patch("CkDoorSill", 5.86, 6.08, dy1, dy2, 0.004, M_CK_FRAME)

join_objects("CkBar", ("CkBar", "CkBack", "CkPend", "CkBottle"))
join_objects("CkGlow", ("CkGlow",))
join_objects("CkFurniture", ("CkSofa", "CkChair", "CkTable", "CkPoseur", "CkRug", "CkStool", "CkPlanter"))
join_objects("CkDoor", ("CkDoor",))
print("COCKTAIL LOUNGE built")
