# Generates the den's painted-on finishes used by build-penthouse.py: a flat
# library wall (cupboards below, open shelves of leather-bound books above),
# a raised-panel oak wainscot module, a desk oak grain tile and an oriental
# rug. Deterministic (fixed seeds); drawn at 2x and downsampled.
#
# Usage: python3 make-den-textures.py   (writes into art/)
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ART = os.path.join(os.path.dirname(os.path.abspath(__file__)), "art")
OAK = (0.42, 0.26, 0.14)
OAK_DARK = (0.24, 0.14, 0.08)


def grain(w, h, seed, along='y', scale=1.0):
    """Wood grain shade field (mean 1): long streaks along one axis."""
    rng = np.random.default_rng(seed)
    n = w if along == 'y' else h
    base = np.cumsum(rng.standard_normal(n)) * 0.02
    base = base - np.convolve(base, np.ones(41) / 41, mode='same')
    lines = 1.0 + 0.10 * np.sin(np.linspace(0, 60 * scale, n) + base * 25)
    fine = 1.0 + 0.06 * rng.standard_normal(n)
    fine = np.convolve(fine, np.ones(3) / 3, mode='same')
    row = lines * fine
    field = np.tile(row[None, :], (h, 1)) if along == 'y' else np.tile(row[:, None], (1, w))
    wob = 1.0 + 0.04 * rng.standard_normal((h, w))
    img = Image.fromarray(np.clip(field * wob * 128, 0, 255).astype(np.uint8))
    img = img.filter(ImageFilter.GaussianBlur(0.8))
    return np.asarray(img).astype(np.float64) / 128.0


# Palette values are sRGB (0-1), written straight to 8-bit.
def to_img(rgb):
    return Image.fromarray((np.clip(rgb, 0, 1) * 255).astype(np.uint8))


def col(c, k=1.0):
    return tuple(int(255 * min(1.0, v * k)) for v in c)


# --- Oak tile (desk, rails, credenza) ----------------------------------------
def make_oak():
    N = 512
    g = grain(N, N, 7, 'x', 1.4)
    rgb = g[..., None] * np.array(OAK)[None, None, :]
    to_img(rgb).save(os.path.join(ART, "den-oak.jpg"), quality=90)


# --- Raised-panel wainscot module: 0.625 m wide x 1.00 m tall -----------------
def make_wainscot():
    W, H = 320, 512            # 512 px per metre
    m = lambda v: int(round(v * 512))
    gv = grain(W, H, 11, 'y', 0.8)
    gh = grain(W, H, 12, 'x', 0.8)
    shade = gv.copy()
    rgb = np.zeros((H, W, 3))
    # rows from the top (v=1 at z 1.0): top rail 0.00-0.10, panel 0.16-0.72,
    # bottom rail 0.72-0.86, skirting 0.86-1.00
    rails = [(0, m(.10)), (m(.72), m(.86))]
    for a, b in rails:
        shade[a:b] = gh[a:b]
    rgb[:] = shade[..., None] * np.array(OAK)
    rgb[m(.86):] = gh[m(.86):, :, None] * np.array(OAK_DARK)          # skirting
    rgb[m(.86):m(.86) + 3] *= 0.55
    # raised panel: x 0.07..0.555 m, y 0.16..0.66 from top
    x0, x1, y0, y1, bev = m(.07), m(.555), m(.16), m(.66), m(.035)
    rgb[y0:y1, x0:x1] *= 0.93
    rgb[y0:y0 + bev, x0:x1] *= 1.18                   # lit top bevel
    rgb[y0:y1, x0:x0 + bev] *= 1.10                   # lit left bevel
    rgb[y1 - bev:y1, x0:x1] *= 0.72                   # shaded bottom bevel
    rgb[y0:y1, x1 - bev:x1] *= 0.80                   # shaded right bevel
    for yy in (y0, y1 - 1):
        rgb[yy:yy + 2, x0:x1] *= 0.6
    for xx in (x0, x1 - 1):
        rgb[y0:y1, xx:xx + 2] *= 0.6
    # moulding shadow under the top rail and above the bottom rail
    rgb[m(.10):m(.10) + 4] *= 0.7
    rgb[m(.72) - 3:m(.72)] *= 0.8
    to_img(rgb).save(os.path.join(ART, "den-wainscot.jpg"), quality=92)


# --- Library wall: 2.415 m wide x 3.14 m tall, three bays --------------------
LEATHER = [(0.36, 0.09, 0.08), (0.10, 0.20, 0.14), (0.10, 0.14, 0.24), (0.50, 0.32, 0.16),
           (0.36, 0.19, 0.09), (0.09, 0.08, 0.07), (0.28, 0.26, 0.13), (0.74, 0.66, 0.50),
           (0.27, 0.07, 0.10), (0.44, 0.13, 0.08), (0.15, 0.24, 0.20)]
GILT = (0.78, 0.60, 0.26)


def make_library():
    PPM = 840                                   # drawn at 2x (420 px/m final)
    Wm, Hm = 2.415, 3.14
    W, H = int(Wm * PPM), int(Hm * PPM)
    Z = lambda z: int(round((Hm - z) * PPM))    # metres above floor -> row
    X = lambda x: int(round(x * PPM))
    rng = np.random.default_rng(1851)
    im = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(im)
    oak_g = grain(W, H, 21, 'y', 3.0)
    oak = to_img(oak_g[..., None] * np.array(OAK))
    oak_dark = to_img(oak_g[..., None] * np.array(OAK_DARK))
    im.paste(oak, (0, 0))
    upr, bays = 0.05, 3
    bay_w = (Wm - upr * (bays + 1)) / bays
    shelves = [0.90, 1.34, 1.78, 2.22, 2.66]
    top = 3.00
    # plinth and cornice
    im.paste(oak_dark.crop((0, Z(0.10), W, H)), (0, Z(0.10)))
    d.rectangle([0, 0, W, Z(top)], fill=col(OAK, 0.85))
    d.rectangle([0, Z(top) - 6, W, Z(top)], fill=col(OAK, 0.55))
    d.rectangle([0, 0, W, 10], fill=col(OAK, 1.15))
    for b in range(bays):
        bx0 = upr + b * (bay_w + upr)
        bx1 = bx0 + bay_w
        # cupboard doors (0.10-0.85): two raised-panel leaves with brass knobs
        for k in range(2):
            lx0 = bx0 + k * bay_w / 2 + 0.006
            lx1 = bx0 + (k + 1) * bay_w / 2 - 0.006
            d.rectangle([X(lx0), Z(0.84), X(lx1), Z(0.11)], outline=col(OAK_DARK, 0.7), width=5)
            px0, px1 = X(lx0 + 0.05), X(lx1 - 0.05)
            py0, py1 = Z(0.76), Z(0.19)
            d.rectangle([px0, py0, px1, py1], fill=col(OAK, 0.92))
            d.rectangle([px0, py0, px1, py0 + 14], fill=col(OAK, 1.12))
            d.rectangle([px0, py1 - 14, px1, py1], fill=col(OAK, 0.68))
            d.rectangle([px0, py0, px0 + 12, py1], fill=col(OAK, 1.04))
            d.rectangle([px1 - 12, py0, px1, py1], fill=col(OAK, 0.74))
            kx = X(lx1 - 0.035) if k == 0 else X(lx0 + 0.035)
            ky = Z(0.52)
            d.ellipse([kx - 14, ky - 14, kx + 14, ky + 14], fill=col(GILT, 0.85))
            d.ellipse([kx - 7, ky - 9, kx + 3, ky - 1], fill=col(GILT, 1.25))
        # counter ledge
        d.rectangle([X(bx0 - upr), Z(0.90), X(bx1 + upr), Z(0.85)], fill=col(OAK, 1.05))
        d.rectangle([X(bx0 - upr), Z(0.90), X(bx1 + upr), Z(0.90) + 6], fill=col(OAK, 1.3))
        # open compartments
        for s in range(len(shelves)):
            z0 = shelves[s] + 0.03
            z1 = (shelves[s + 1] if s + 1 < len(shelves) else top)
            cx0, cx1 = X(bx0), X(bx1)
            cy0, cy1 = Z(z1), Z(z0)
            # back panel with shadow under the shelf above and at the sides
            hh = cy1 - cy0
            ww = cx1 - cx0
            yy = np.linspace(0, 1, hh)[:, None]
            xx = np.linspace(0, 1, ww)[None, :]
            sh = (0.45 + 0.55 * np.clip(yy * 2.2, 0, 1)) * (0.75 + 0.25 * np.clip(np.minimum(xx, 1 - xx) * 8, 0, 1))
            back = np.array((0.16, 0.10, 0.06))[None, None, :] * sh[..., None] * oak_g[cy0:cy1, cx0:cx1, None]
            im.paste(to_img(back), (cx0, cy0))
            fill_books(im, d, rng, bx0, bx1, z0, z1, X, Z, s, b)
            # shelf board (front edge) under this compartment
            d.rectangle([X(bx0), Z(shelves[s] + 0.03), X(bx1), Z(shelves[s])], fill=col(OAK, 1.0))
            d.rectangle([X(bx0), Z(shelves[s] + 0.03), X(bx1), Z(shelves[s] + 0.03) + 5], fill=col(OAK, 1.3))
    # uprights on top of everything, with a lit edge
    for b in range(bays + 1):
        ux0 = b * (bay_w + upr)
        d.rectangle([X(ux0), Z(top), X(ux0 + upr), Z(0.90)], fill=col(OAK, 0.95))
        d.rectangle([X(ux0), Z(top), X(ux0) + 6, Z(0.90)], fill=col(OAK, 1.2))
        d.rectangle([X(ux0 + upr) - 6, Z(top), X(ux0 + upr), Z(0.90)], fill=col(OAK, 0.65))
    im = im.resize((W // 2, H // 2), Image.LANCZOS)
    im.save(os.path.join(ART, "den-library.jpg"), quality=90)


def spine(d, x0, x1, ytop, ybot, c, rng):
    w = x1 - x0
    for i in range(w):
        t = (i + 0.5) / w
        k = 0.62 + 0.45 * np.sin(np.pi * t) ** 0.6
        d.line([(x0 + i, ytop), (x0 + i, ybot)], fill=col(c, k))
    if rng.random() < 0.85:
        g = col(GILT, 0.9 + 0.3 * rng.random())
        h = ybot - ytop
        for f in (0.08, 0.13, 0.87, 0.92):
            yy = int(ytop + f * h)
            d.line([(x0 + 2, yy), (x1 - 2, yy)], fill=g, width=3)
        if rng.random() < 0.6 and w > 18:
            ly0, ly1 = int(ytop + 0.22 * h), int(ytop + 0.34 * h)
            lc = LEATHER[rng.integers(len(LEATHER))]
            d.rectangle([x0 + 3, ly0, x1 - 3, ly1], fill=col(lc, 0.8))
            d.line([(x0 + 5, (ly0 + ly1) // 2), (x1 - 5, (ly0 + ly1) // 2)], fill=g, width=2)


def fill_books(im, d, rng, bx0, bx1, z0, z1, X, Z, s, b):
    x = bx0 + 0.01
    clear = z1 - z0
    stack_at = rng.integers(0, 3) if (s + b) % 3 == 1 else -1
    pos = 0
    while x < bx1 - 0.02:
        if pos == stack_at:
            # a short horizontal stack
            sw = 0.22 + 0.06 * rng.random()
            if x + sw > bx1 - 0.01:
                break
            zz = z0
            for _ in range(rng.integers(3, 5)):
                th = 0.03 + 0.025 * rng.random()
                inset = 0.01 * rng.random()
                c = LEATHER[rng.integers(len(LEATHER))]
                for i in range(Z(zz) - Z(zz + th)):
                    k = 0.6 + 0.45 * np.sin(np.pi * (i + 0.5) / max(1, Z(zz) - Z(zz + th))) ** 0.6
                    yy = Z(zz + th) + i
                    d.line([(X(x + inset), yy), (X(x + sw - inset), yy)], fill=col(c, k))
                zz += th
            x += sw + 0.02
            pos += 1
            continue
        bw = 0.022 + 0.035 * rng.random() ** 1.5
        if x + bw > bx1 - 0.01:
            break
        bh = min(clear - 0.02, 0.21 + 0.13 * rng.random())
        c = LEATHER[rng.integers(len(LEATHER))]
        if rng.random() < 0.06 and x + 0.12 < bx1 - 0.04:
            # one leaning book, resting against its neighbour
            ang = np.radians(14 + 8 * rng.random())
            px, pz = x + 0.005, z0
            pts = [(px, pz), (px + bw * np.cos(ang), pz - bw * np.sin(ang) * 0),
                   (px + bw * np.cos(ang) + bh * np.sin(ang), pz + bh * np.cos(ang)),
                   (px + bh * np.sin(ang), pz + bh * np.cos(ang))]
            d.polygon([(X(a), Z(bz)) for a, bz in pts], fill=col(c, 0.85), outline=col(c, 0.55))
            x += bw + bh * np.sin(ang) + 0.005
        else:
            spine(d, X(x), X(x + bw), Z(z0 + bh), Z(z0), c, rng)
            d.line([(X(x + bw), Z(z0 + bh)), (X(x + bw), Z(z0))], fill=col((0.05, 0.04, 0.03)), width=2)
            x += bw + 0.001
        pos += 1
        if rng.random() < 0.03:
            x += 0.05 + 0.08 * rng.random()          # a gap on the shelf


# --- Oriental rug: 3.0 m x 1.9 m ---------------------------------------------
def make_rug():
    PPM = 300
    W, H = int(3.0 * PPM), int(1.9 * PPM)
    rng = np.random.default_rng(1877)
    im = Image.new("RGB", (W, H), col((0.30, 0.07, 0.06)))
    d = ImageDraw.Draw(im)
    NAVY, IVORY, GOLD, RED = (0.06, 0.08, 0.16), (0.70, 0.62, 0.46), (0.62, 0.43, 0.16), (0.40, 0.09, 0.07)
    def band(inset, width, c):
        d.rectangle([inset, inset, W - 1 - inset, H - 1 - inset], outline=col(c), width=width)
    band(0, 18, NAVY)
    band(18, 6, IVORY)
    band(24, 60, NAVY)
    band(84, 6, GOLD)
    band(90, 10, RED)
    # border motif: rosettes along the navy main border
    for x in range(60, W - 40, 70):
        for y in (54, H - 54):
            d.ellipse([x - 16, y - 16, x + 16, y + 16], fill=col(RED))
            d.ellipse([x - 7, y - 7, x + 7, y + 7], fill=col(GOLD))
    for y in range(120, H - 100, 70):
        for x in (54, W - 54):
            d.ellipse([x - 16, y - 16, x + 16, y + 16], fill=col(RED))
            d.ellipse([x - 7, y - 7, x + 7, y + 7], fill=col(GOLD))
    # field lattice of small diamonds
    for y in range(130, H - 120, 46):
        for x in range(130 + (23 if (y // 46) % 2 else 0), W - 120, 46):
            d.polygon([(x, y - 7), (x + 7, y), (x, y + 7), (x - 7, y)], fill=col((0.22, 0.05, 0.05)))
    # small repeating boteh-like flowers in the field
    for y in range(125, H - 115, 34):
        for x in range(125 + (17 if (y // 34) % 2 else 0), W - 115, 34):
            c = (IVORY, GOLD, NAVY)[(x // 34 + y // 34) % 3]
            d.ellipse([x - 4, y - 4, x + 4, y + 4], fill=col(c, 0.8))
    # central medallion (layered lozenge with pendants) and corner spandrels
    cx, cy = W // 2, H // 2
    for r, c in ((125, NAVY), (112, IVORY), (104, NAVY), (78, RED), (60, GOLD), (46, NAVY), (24, IVORY), (12, RED)):
        rx = int(r * 1.5)
        d.polygon([(cx, cy - r), (cx + rx, cy), (cx, cy + r), (cx - rx, cy)], fill=col(c))
    for sgn in (-1, 1):
        px = cx + sgn * 225
        d.polygon([(px, cy - 28), (px + sgn * 42, cy), (px, cy + 28), (px - sgn * 10, cy)], fill=col(NAVY))
        d.ellipse([px + sgn * 12 - 9, cy - 9, px + sgn * 12 + 9, cy + 9], fill=col(GOLD))
    for sx, sy in ((100, 100), (W - 100, 100), (100, H - 100), (W - 100, H - 100)):
        dx = 1 if sx < cx else -1
        dy = 1 if sy < cy else -1
        d.polygon([(sx, sy), (sx + dx * 120, sy), (sx, sy + dy * 90)], fill=col(NAVY))
        d.polygon([(sx, sy), (sx + dx * 78, sy), (sx, sy + dy * 58)], fill=col(IVORY, 0.85))
        d.polygon([(sx, sy), (sx + dx * 44, sy), (sx, sy + dy * 33)], fill=col(RED))
    a = np.asarray(im).astype(np.float64) / 255.0
    wool = 1.0 + 0.07 * rng.standard_normal(a.shape[:2])
    a = np.clip(a * wool[..., None], 0, 1)
    Image.fromarray((a * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.6)).save(
        os.path.join(ART, "den-rug.jpg"), quality=90)


if __name__ == "__main__":
    make_oak()
    make_wainscot()
    make_library()
    make_rug()
    print("den textures written")
