# Generates the Rovers Return Inn finishes (Coronation Street's corner pub,
# built 1:1 on the south balcony) used by build-penthouse.py:
#   rovers-brick.jpg      red Accrington brick, stretcher bond, 0.9 m tile
#   rovers-riser.jpg      dark green glazed tile stall riser, 0.6 m tile
#   rovers-damask.jpg     oxblood + old-gold Victorian damask wallpaper, 0.64 m tile
#   rovers-panel.jpg      mahogany dado panelling, 1.2 m wide x 1.1 m tall
#   rovers-carpet.jpg     red pub carpet with a green/gold medallion, 1 m tile
#   rovers-boards.jpg     worn oak floorboards behind the bar, 1 m tile
#   rovers-ceiling.jpg    cream anaglypta ceiling paper, 0.6 m tile
#   rovers-velour.jpg     buttoned burgundy velour banquette, 0.4 m tile
#   rovers-etched.jpg     frosted etched window glass with "Rovers Return" (one pane, UV 0..1)
#   rovers-stained.jpg    leaded stained-glass transom (one pane, UV 0..1)
#   rovers-fascia.jpg     "THE ROVERS RETURN INN" gold on black fascia
#   rovers-newton.jpg     "NEWTON & RIDLEY" corner board
#   rovers-licensee.jpg   licensee plaque over the corner door
#   rovers-backbar.jpg    flat back bar: mirrors, optics, bottles, glasses
#   rovers-dartboard.jpg  dartboard
#   rovers-hotpot.jpg     chalkboard: Betty's Hotpot
#   rovers-poster.jpg     Newton & Ridley ale advert
# Deterministic (fixed seeds).
#
# Usage: python3 make-rovers-textures.py   (writes into art/)
import math
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ART = os.path.join(os.path.dirname(os.path.abspath(__file__)), "art")
SUP = "/System/Library/Fonts/Supplemental/"


def save(rgb, name, q=90):
    Image.fromarray((np.clip(rgb, 0, 1) * 255).astype(np.uint8)).save(os.path.join(ART, name), quality=q)


def save_img(img, name, q=90):
    img.convert("RGB").save(os.path.join(ART, name), quality=q)


def hexc(h):
    return np.array([int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)])


def rgb255(h):
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def noise(n, seed, blur, m=None):
    rng = np.random.default_rng(seed)
    m = m or n
    img = Image.fromarray(np.clip(rng.normal(128, 40, (m, n)), 0, 255).astype(np.uint8))
    return np.asarray(img.filter(ImageFilter.GaussianBlur(blur))).astype(np.float64) / 128.0


def font(name, size, index=0):
    return ImageFont.truetype(SUP + name, size, index=index)


def centre(d, W, text, y, f, fill):
    w = d.textlength(text, font=f)
    d.text(((W - w) / 2, y), text, font=f, fill=fill)


def make_brick():
    # 0.9 m tile = 4 bricks (225 mm incl. joint) x 12 courses (75 mm), drawn
    # brick by brick (wraps seamlessly: 4 bricks across, 12 courses down).
    N = 1024
    rng = np.random.default_rng(7)
    ch, bw, jt = N / 12.0, N / 4.0, 10
    img = Image.new("RGB", (N, N), rgb255("A79C8A"))
    d = ImageDraw.Draw(img)
    palette = ("8E3B28", "9A4630", "7E3324", "A2523A", "86402C", "6E2E22", "93503A")
    for row in range(12):
        off = (row % 2) * bw / 2
        for k in range(-1, 5):
            x0 = k * bw + off + jt
            c = np.array(rgb255(palette[int(rng.integers(0, len(palette)))])) * rng.uniform(0.86, 1.08)
            d.rectangle((x0, row * ch + jt, x0 + bw - jt - 1, (row + 1) * ch - 1), fill=tuple(int(v) for v in np.clip(c, 0, 255)))
    a = np.asarray(img).astype(np.float64) / 255
    a *= ((0.9 + 0.1 * noise(N, 8, 1.0)) * (0.95 + 0.05 * noise(N, 9, 12)))[..., None]
    save(a, "rovers-brick.jpg")


def make_riser():
    # 150 x 75 mm glazed bottle-green tiles, 0.6 m tile.
    N = 512
    px = N / 0.6
    y, x = np.mgrid[0:N, 0:N].astype(np.float64)
    tw, th, j = 0.15 * px, 0.075 * px, 0.004 * px
    joint = ((x % tw) < j) | ((y % th) < j)
    rng = np.random.default_rng(11)
    tone = rng.uniform(0.85, 1.12, 4096)
    ids = (np.floor(x / tw) * 13 + np.floor(y / th) * 7).astype(int) % 4096
    glaze = hexc("1F4A36") * tone[ids][..., None]
    # bevelled edge highlight inside each tile
    ex = np.minimum(x % tw, tw - x % tw) / tw
    ey = np.minimum(y % th, th - y % th) / th
    bev = np.clip(np.minimum(ex * 6, ey * 3), 0, 1)
    glaze = glaze * (0.75 + 0.25 * bev)[..., None] + 0.08 * (1 - bev)[..., None]
    rgb = np.where(joint[..., None], hexc("CFC6B0"), glaze)
    save(rgb, "rovers-riser.jpg")


def make_damask():
    # Old-gold damask medallions in a half-drop repeat on deep oxblood.
    N = 1024
    img = Image.new("RGB", (N, N), rgb255("5A1A1E"))
    d = ImageDraw.Draw(img)
    gold = rgb255("A8843E")
    dark = rgb255("4A1418")

    def medallion(cx, cy, s):
        # stacked leaf/lozenge motif
        for k, (w, h, oy) in enumerate(((0.30, 0.46, 0.0), (0.18, 0.26, -0.33), (0.18, 0.26, 0.33))):
            d.ellipse((cx - w * s, cy + oy * s - h * s, cx + w * s, cy + oy * s + h * s), outline=gold, width=10)
        d.ellipse((cx - 0.12 * s, cy - 0.12 * s, cx + 0.12 * s, cy + 0.12 * s), fill=gold)
        for sx in (-1, 1):
            pts = [(cx + sx * 0.10 * s, cy - 0.05 * s), (cx + sx * 0.46 * s, cy - 0.30 * s),
                   (cx + sx * 0.38 * s, cy + 0.02 * s), (cx + sx * 0.46 * s, cy + 0.30 * s),
                   (cx + sx * 0.10 * s, cy + 0.05 * s)]
            d.polygon(pts, outline=gold, width=8)
            d.ellipse((cx + sx * 0.44 * s - 18, cy - 18, cx + sx * 0.44 * s + 18, cy + 18), fill=gold)
        d.line((cx, cy - 0.62 * s, cx, cy - 0.46 * s), fill=gold, width=8)
        d.line((cx, cy + 0.46 * s, cx, cy + 0.62 * s), fill=gold, width=8)

    s = 420
    for cx, cy in ((N * 0.25, N * 0.25), (N * 0.75, N * 0.75), (N * 0.25 + N, N * 0.25), (N * 0.25 - N, N * 0.25),
                   (N * 0.75, N * 0.75 - N), (N * 0.75 - N, N * 0.75), (N * 0.25, N * 0.25 + N), (N * 0.75 + N, N * 0.75 - N),
                   (N * 0.75 - N, N * 0.75 - N), (N * 0.25 + N, N * 0.25 + N), (N * 0.25 - N, N * 0.25 + N), (N * 0.75 + N, N * 0.75)):
        medallion(cx, cy, s)
    # small fleurettes between
    for cx, cy in ((N * 0.75, N * 0.25), (N * 0.25, N * 0.75)):
        d.ellipse((cx - 30, cy - 30, cx + 30, cy + 30), outline=gold, width=6)
        d.ellipse((cx - 10, cy - 10, cx + 10, cy + 10), fill=gold)
    img = img.filter(ImageFilter.GaussianBlur(1.2))
    a = np.asarray(img).astype(np.float64) / 255
    a *= (0.9 + 0.1 * noise(N, 31, 1.0))[..., None] * (0.94 + 0.06 * noise(N, 32, 40))[..., None]
    save(a, "rovers-damask.jpg")


def make_panel():
    # 1.2 m wide x 1.1 m tall: two raised fielded panels under a moulded rail.
    W, H = 1024, 940
    px = W / 1.2
    y, x = np.mgrid[0:H, 0:W].astype(np.float64)
    grain = 0.82 + 0.18 * np.sin((x * 0.02 + 6 * noise(W, 41, 18, H)) * 3.0) * 0.5 + 0.1 * noise(W, 42, 1.0, H)
    base = hexc("4A2416")[None, None, :] * grain[..., None]
    shade = np.ones((H, W))
    top = 0.10 * px      # rail (from top)
    bot = 0.14 * px      # skirting
    stile = 0.08 * px
    pw = (W - 3 * stile) / 2
    for i in range(2):
        x0 = stile + i * (pw + stile)
        x1 = x0 + pw
        y0, y1 = top + 0.05 * px, H - bot - 0.05 * px
        inside = (x > x0) & (x < x1) & (y > y0) & (y < y1)
        dist = np.minimum.reduce([x - x0, x1 - x, y - y0, y1 - y]) / px
        bevel = np.clip(dist / 0.05, 0, 1)
        light = np.where((x - x0) < (y - y0), 1.15, 0.85)  # light from upper left on the bevel
        shade = np.where(inside, np.where(bevel < 1, light * (0.85 + 0.15 * bevel), 1.06), shade)
        edge = inside & (dist < 0.006)
        shade = np.where(edge, 0.55, shade)
    shade = np.where(y < top, 0.9 + 0.25 * (np.sin(y / top * np.pi * 2) > 0), shade)
    shade = np.where(y > H - bot, 0.72, shade)
    save(base * shade[..., None], "rovers-panel.jpg")


def make_carpet():
    # 1 m tile: claret ground, gold-and-green medallion lattice (classic pub Axminster).
    N = 1024
    img = Image.new("RGB", (N, N), rgb255("6E1620"))
    d = ImageDraw.Draw(img)
    gold, green, navy = rgb255("B48A3A"), rgb255("2F5135"), rgb255("2A2440")
    for cx, cy in ((0, 0), (N, 0), (0, N), (N, N), (N / 2, N / 2)):
        for r, colr, w in ((230, gold, 14), (190, green, 26), (130, gold, 10), (90, navy, 0), (40, gold, 0)):
            if w:
                d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=colr, width=w)
            else:
                d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=colr)
        for k in range(8):
            a = k * math.pi / 4
            px_, py_ = cx + 160 * math.cos(a), cy + 160 * math.sin(a)
            d.ellipse((px_ - 22, py_ - 22, px_ + 22, py_ + 22), fill=gold)
    for cx, cy in ((N / 2, 0), (0, N / 2), (N / 2, N), (N, N / 2)):
        d.polygon([(cx, cy - 80), (cx + 80, cy), (cx, cy + 80), (cx - 80, cy)], fill=green, outline=gold)
        d.ellipse((cx - 22, cy - 22, cx + 22, cy + 22), fill=gold)
    img = img.filter(ImageFilter.GaussianBlur(2.0))
    a = np.asarray(img).astype(np.float64) / 255
    a *= (0.82 + 0.18 * noise(N, 51, 0.7))[..., None] * (0.9 + 0.1 * noise(N, 52, 60))[..., None]
    save(a, "rovers-carpet.jpg")


def make_boards():
    N = 1024
    y, x = np.mgrid[0:N, 0:N].astype(np.float64)
    bw = N / 7
    board = np.floor(y / bw).astype(int)
    rng = np.random.default_rng(61)
    tone = rng.uniform(0.8, 1.1, 64)[board % 64]
    off = rng.uniform(0, N, 64)[board % 64]
    grain = 0.85 + 0.15 * np.sin(((x + off) * 0.015 + 5 * noise(N, 62, 10)) * 4)
    rgb = hexc("6A4426")[None, None, :] * (tone * grain)[..., None]
    gap = (y % bw) < 3
    butt = ((x + off) % (N * 0.9)) < 3
    rgb = np.where((gap | butt)[..., None], hexc("21140C"), rgb)
    rgb *= (0.88 + 0.12 * noise(N, 63, 30))[..., None]
    save(rgb, "rovers-boards.jpg")


def make_ceiling():
    N = 512
    y, x = np.mgrid[0:N, 0:N].astype(np.float64)
    u, v = x / N * 2 * np.pi * 4, y / N * 2 * np.pi * 4
    relief = np.sin(u) * np.sin(v) + 0.5 * np.sin(2 * u + v)
    shade = 0.9 + 0.06 * relief + 0.04 * noise(N, 71, 1.0)
    save(shade[..., None] * hexc("D9CDAE")[None, None, :], "rovers-ceiling.jpg")


def make_velour():
    # 0.4 m tile: buttoned (Chesterfield-style) burgundy velour.
    N = 512
    y, x = np.mgrid[0:N, 0:N].astype(np.float64)
    p = N / 2
    dx = (x % p) - p / 2
    dy = (y % p) - p / 2
    # diamond tufting: buttons at cell centres and corners
    du = np.abs(dx) + np.abs(dy)
    puff = np.clip(1 - np.abs(du - p / 2) / (p / 2), 0, 1)
    shade = 0.7 + 0.3 * puff
    for bx, by in ((p / 2, p / 2), (0, 0)):
        r = np.hypot(((x - bx) % p + p / 2) % p - p / 2, ((y - by) % p + p / 2) % p - p / 2)
        shade = np.where(r < 9, 0.45, shade)
    pile = 0.9 + 0.1 * noise(N, 81, 0.8)
    save((shade * pile)[..., None] * hexc("6A1A24")[None, None, :], "rovers-velour.jpg")


def make_etched():
    # One sash pane: frosted ground, clear-cut border and ornament, gilt-edged name.
    W, H = 512, 640
    img = Image.new("RGB", (W, H), rgb255("C9CFC8"))
    d = ImageDraw.Draw(img)
    clear = rgb255("8E9A96")
    d.rectangle((14, 14, W - 14, H - 14), outline=clear, width=10)
    d.rectangle((40, 40, W - 40, H - 40), outline=clear, width=3)
    for cx, cy in ((40, 40), (W - 40, 40), (40, H - 40), (W - 40, H - 40)):
        d.ellipse((cx - 22, cy - 22, cx + 22, cy + 22), outline=clear, width=5)
    # central cartouche
    d.ellipse((W / 2 - 170, H / 2 - 120, W / 2 + 170, H / 2 + 120), outline=clear, width=6)
    f1 = font("BigCaslon.ttf", 74)
    f2 = font("BigCaslon.ttf", 44)
    centre(d, W, "Rovers", H / 2 - 92, f1, clear)
    centre(d, W, "Return", H / 2 - 10, f1, clear)
    centre(d, W, "~ ALES ~", H / 2 + 70, f2, clear)
    # scrolls top and bottom
    for yy in (110, H - 110):
        for sx in (-1, 1):
            d.arc((W / 2 + sx * 60 - 70, yy - 40, W / 2 + sx * 60 + 70, yy + 40), 0, 360, fill=clear, width=5)
    img = img.filter(ImageFilter.GaussianBlur(1.0))
    a = np.asarray(img).astype(np.float64) / 255 * (0.94 + 0.06 * noise(W, 91, 1.5, H))[..., None]
    save(a, "rovers-etched.jpg")


def make_stained():
    # Leaded transom: amber field, red/green/blue jewels, central sunburst.
    W, H = 768, 256
    img = Image.new("RGB", (W, H), rgb255("C99A3E"))
    d = ImageDraw.Draw(img)
    lead = rgb255("1A1712")
    cols = [rgb255(h) for h in ("8E1B22", "2E6B3A", "23407A", "D9B65A", "B9562C")]
    rng = np.random.default_rng(101)
    cells = 12
    for i in range(cells):
        x0, x1 = i * W / cells, (i + 1) * W / cells
        c = cols[i % 3] if i % 2 else rgb255("D7B060")
        d.rectangle((x0, 0, x1, 50), fill=c, outline=lead, width=5)
        d.rectangle((x0, H - 50, x1, H), fill=cols[(i + 1) % 3] if i % 2 == 0 else rgb255("D7B060"), outline=lead, width=5)
    cx, cy = W / 2, H - 50
    for k in range(13):
        a0, a1 = math.pi + k * math.pi / 13, math.pi + (k + 1) * math.pi / 13
        pts = [(cx, cy), (cx + 360 * math.cos(a0), cy + 360 * math.sin(a0)), (cx + 360 * math.cos(a1), cy + 360 * math.sin(a1))]
        d.polygon(pts, fill=rgb255("E3C46E") if k % 2 else rgb255("C8923A"), outline=lead)
        d.line((pts[0], pts[1]), fill=lead, width=5)
    d.ellipse((cx - 60, cy - 60, cx + 60, cy + 60), fill=rgb255("8E1B22"), outline=lead, width=6)
    d.rectangle((0, 50, W, H - 50), outline=lead, width=6)
    d.rectangle((0, 0, W - 1, H - 1), outline=lead, width=10)
    a = np.asarray(img).astype(np.float64) / 255 * (0.92 + 0.08 * noise(W, 102, 2.0, H))[..., None]
    save(a, "rovers-stained.jpg")


def make_fascia():
    W, H = 1024, 96
    img = Image.new("RGB", (W, H), rgb255("121212"))
    d = ImageDraw.Draw(img)
    gold = rgb255("D2A94E")
    d.rectangle((3, 3, W - 4, H - 4), outline=gold, width=3)
    d.rectangle((10, 10, W - 11, H - 11), outline=rgb255("7A6430"), width=1)
    f = font("BigCaslon.ttf", 64)
    shadow = rgb255("5A4416")
    text = "THE  ROVERS  RETURN  INN"
    w = d.textlength(text, font=f)
    d.text(((W - w) / 2 + 2, 12 + 2), text, font=f, fill=shadow)
    d.text(((W - w) / 2, 12), text, font=f, fill=gold)
    save_img(img, "rovers-fascia.jpg", q=94)


def make_newton():
    W, H = 512, 128
    img = Image.new("RGB", (W, H), rgb255("121212"))
    d = ImageDraw.Draw(img)
    gold = rgb255("D2A94E")
    d.rectangle((3, 3, W - 4, H - 4), outline=gold, width=3)
    centre(d, W, "NEWTON & RIDLEY", 18, font("BigCaslon.ttf", 44), gold)
    centre(d, W, "FINE  ALES  &  STOUTS", 80, font("Copperplate.ttc", 26), gold)
    save_img(img, "rovers-newton.jpg", q=94)


def make_licensee():
    W, H = 768, 96
    img = Image.new("RGB", (W, H), rgb255("121212"))
    d = ImageDraw.Draw(img)
    cream = rgb255("E6D9B4")
    centre(d, W, "ROVERS RETURN INN", 6, font("Copperplate.ttc", 30), cream)
    centre(d, W, "LICENSED TO SELL BY RETAIL INTOXICATING LIQUOR", 44, font("Copperplate.ttc", 20), cream)
    centre(d, W, "FOR CONSUMPTION ON OR OFF THE PREMISES", 68, font("Copperplate.ttc", 20), cream)
    save_img(img, "rovers-licensee.jpg", q=94)


def make_backbar():
    # 2.4:1 flat back bar: mirrored centre with gilt lettering, shelves of
    # bottles and glasses, inverted optics on the lower rail.
    W, H = 1024, 448
    img = Image.new("RGB", (W, H), rgb255("3A1C10"))
    d = ImageDraw.Draw(img)
    rng = np.random.default_rng(111)
    wood, dark = rgb255("4A2416"), rgb255("2A140B")
    # mirror panels
    for x0, x1 in ((40, 300), (362, 662), (724, 984)):
        d.rectangle((x0, 30, x1, 330), fill=rgb255("6F6A5E"), outline=rgb255("B08A45"), width=6)
        for k in range(14):
            yy = 30 + k * 22
            d.line((x0 + 8, yy, x1 - 8, yy + 50), fill=rgb255("7B766A"), width=2)
    centre(d, W, "Newton & Ridley", 40, font("SnellRoundhand.ttc", 46, index=1), rgb255("D2A94E"))
    # shelves with bottles
    bottle_cols = [rgb255(h) for h in ("2C5E2A", "6B3A12", "A8A090", "7A1E1E", "C9A25A", "1E3A5E", "D8D2C0", "4A2A10")]
    for sy in (150, 245, 330):
        d.rectangle((30, sy, W - 30, sy + 10), fill=wood)
        x = 46
        while x < W - 60:
            bw = int(rng.integers(16, 28))
            bh = int(rng.integers(50, 84))
            c = bottle_cols[int(rng.integers(0, len(bottle_cols)))]
            d.rectangle((x, sy - bh + 26, x + bw, sy), fill=c)
            d.rectangle((x + bw // 3, sy - bh, x + 2 * bw // 3, sy - bh + 26), fill=c)
            if bh > 60:
                d.rectangle((x + 3, sy - bh + 40, x + bw - 3, sy - 14), fill=rgb255("E6DCC0"))
            d.line((x + 3, sy - bh + 28, x + 3, sy - 4), fill=rgb255("EEE6D0"), width=2)
            x += bw + int(rng.integers(4, 10))
    # optics rail with upside-down bottles
    d.rectangle((30, 340, W - 30, 352), fill=rgb255("B08A45"))
    for i in range(12):
        x = 70 + i * 76
        c = bottle_cols[i % len(bottle_cols)]
        d.rectangle((x, 352, x + 28, 412), fill=c)
        d.rectangle((x + 10, 412, x + 18, 432), fill=rgb255("C8C8C8"))
    d.rectangle((0, 432, W, H), fill=dark)
    a = np.asarray(img).astype(np.float64) / 255 * (0.94 + 0.06 * noise(W, 112, 1.2, H))[..., None]
    save(a, "rovers-backbar.jpg")


def make_dartboard():
    N = 512
    img = Image.new("RGB", (N, N), rgb255("1A1A1A"))
    d = ImageDraw.Draw(img)
    c = N / 2
    R = 230
    nums = [20, 1, 18, 4, 13, 6, 10, 15, 2, 17, 3, 19, 7, 16, 8, 11, 14, 9, 12, 5]
    f = font("Georgia Bold.ttf", 24)
    for i in range(20):
        a0 = math.radians(-90 - 9 + i * 18)
        a1 = a0 + math.radians(18)
        for r0, r1, col in ((R * 0.72, R * 0.80, ("C42A2A", "2A8A3A")), (R * 0.80, R * 0.72, None),
                            (R * 0.47, R * 0.53, ("C42A2A", "2A8A3A"))):
            pass
        for (rad, colpair) in ((R * 0.80, ("C42A2A", "2A8A3A")), (R * 0.74, ("1A1A1A", "EDE3C6")),
                               (R * 0.50, ("C42A2A", "2A8A3A")), (R * 0.45, ("1A1A1A", "EDE3C6"))):
            col = rgb255(colpair[i % 2])
            d.pieslice((c - rad, c - rad, c + rad, c + rad), math.degrees(a0), math.degrees(a1), fill=col)
        am = (a0 + a1) / 2
        t = str(nums[i])
        w = d.textlength(t, font=f)
        d.text((c + (R * 0.9) * math.cos(am) - w / 2, c + (R * 0.9) * math.sin(am) - 14), t, font=f, fill=rgb255("EEEEEE"))
    d.ellipse((c - 26, c - 26, c + 26, c + 26), fill=rgb255("2A8A3A"))
    d.ellipse((c - 11, c - 11, c + 11, c + 11), fill=rgb255("C42A2A"))
    for rad in (R * 0.80, R * 0.74, R * 0.50, R * 0.45):
        d.ellipse((c - rad, c - rad, c + rad, c + rad), outline=rgb255("C0C0C0"), width=2)
    save_img(img, "rovers-dartboard.jpg", q=92)


def make_hotpot():
    W, H = 512, 640
    img = Image.new("RGB", (W, H), rgb255("6A4A2A"))
    d = ImageDraw.Draw(img)
    d.rectangle((24, 24, W - 24, H - 24), fill=rgb255("1E2420"))
    chalk = rgb255("E8E4D8")
    yel = rgb255("E8D27A")
    pink = rgb255("E8A0A0")
    cd = font("Chalkduster.ttf", 54)
    cm = font("Chalkduster.ttf", 34)
    cs = font("Chalkduster.ttf", 26)
    centre(d, W, "TODAY", 52, cm, yel)
    centre(d, W, "Betty's", 120, cd, chalk)
    centre(d, W, "Hotpot", 190, cd, chalk)
    centre(d, W, "with pickled", 280, cs, chalk)
    centre(d, W, "red cabbage", 318, cs, chalk)
    centre(d, W, "£5.50", 390, cd, pink)
    centre(d, W, "Ploughman's  £6", 490, cs, chalk)
    centre(d, W, "Pie & Peas  £5", 530, cs, chalk)
    img = img.filter(ImageFilter.GaussianBlur(0.6))
    save_img(img, "rovers-hotpot.jpg")


def make_poster():
    W, H = 512, 704
    img = Image.new("RGB", (W, H), rgb255("E6D6AE"))
    d = ImageDraw.Draw(img)
    red, black = rgb255("8E1B22"), rgb255("1A1712")
    d.rectangle((16, 16, W - 16, H - 16), outline=red, width=8)
    centre(d, W, "NEWTON", 60, font("Rockwell.ttc", 80, index=1), red)
    centre(d, W, "& RIDLEY", 150, font("Rockwell.ttc", 60, index=1), red)
    # pint glass
    cx = W / 2
    d.polygon([(cx - 90, 260), (cx + 90, 260), (cx + 72, 560), (cx - 72, 560)], fill=rgb255("8A4A1A"), outline=black)
    d.rectangle((cx - 92, 240, cx + 92, 290), fill=rgb255("F2EAD2"), outline=black)
    centre(d, W, "Best Bitter", 590, font("BigCaslon.ttf", 54), black)
    centre(d, W, "BREWED IN WEATHERFIELD", 650, font("Copperplate.ttc", 22), red)
    save_img(img, "rovers-poster.jpg")


if __name__ == "__main__":
    for fn in (make_brick, make_riser, make_damask, make_panel, make_carpet, make_boards, make_ceiling,
               make_velour, make_etched, make_stained, make_fascia, make_newton, make_licensee,
               make_backbar, make_dartboard, make_hotpot, make_poster):
        fn()
        print("wrote", fn.__name__)
