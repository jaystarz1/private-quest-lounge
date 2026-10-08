# Generates the TV lounge's Malibu beach-house finishes (Charlie Harper's
# living room in Two and a Half Men: Spanish/Mediterranean, warm neutrals,
# gnarly wood, kilim, Mexican tile) used by build-penthouse.py:
#   malibu-sisal.jpg     natural sisal weave, 0.5 m tile
#   malibu-chenille.jpg  olive chenille upholstery, 0.25 m tile
#   malibu-saltillo.jpg  terracotta Saltillo floor tile, 1 m tile (3 x 3)
#   malibu-talavera.jpg  blue/ochre Talavera wall tile, 1 m tile (5 x 5)
#   malibu-kilim.jpg     kilim cushion weave, 0.5 m tile
#   malibu-ceiling.jpg   stained knotty plank ceiling, 1 m tile
#   malibu-jazz.jpg      mid-century jazz club poster for over the fireplace
#   malibu-jazz2.jpg     second poster for the piano room's west wall
# Deterministic (fixed seeds).
#
# Usage: python3 make-malibu-textures.py   (writes into art/)
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ART = os.path.join(os.path.dirname(os.path.abspath(__file__)), "art")


def save(rgb, name, q=90):
    Image.fromarray((np.clip(rgb, 0, 1) * 255).astype(np.uint8)).save(os.path.join(ART, name), quality=q)


def hexc(h):
    return np.array([int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)])


def noise(n, seed, blur):
    rng = np.random.default_rng(seed)
    img = Image.fromarray(np.clip(rng.normal(128, 40, (n, n)), 0, 255).astype(np.uint8))
    return np.asarray(img.filter(ImageFilter.GaussianBlur(blur))).astype(np.float64) / 128.0


def make_sisal():
    # Boucle-style basket weave: 1 cm cords, alternating 4-cord blocks.
    N = 512                       # 0.5 m
    y, x = np.mgrid[0:N, 0:N]
    cord = 10
    bx, by = x // (cord * 4), y // (cord * 4)
    horiz = (bx + by) % 2 == 0
    t = np.where(horiz, y % cord, x % cord) / cord
    ridge = 0.78 + 0.22 * np.sin(t * np.pi)
    twist = 1.0 + 0.06 * np.sin((np.where(horiz, x, y)) * 2 * np.pi / 6)
    shade = ridge * twist * (0.92 + 0.08 * noise(N, 3, 1.2)) * (0.96 + 0.04 * noise(N, 4, 20))
    rgb = shade[..., None] * hexc("B59F78")[None, None, :]
    save(rgb, "malibu-sisal.jpg")


def make_chenille():
    N = 512                       # 0.25 m
    base = hexc("5E5A36")
    pile = noise(N, 21, 0.8) * 0.5 + noise(N, 22, 3.0) * 0.5
    rows = 1.0 + 0.05 * np.sin(np.mgrid[0:N, 0:N][0] * 2 * np.pi / 8)
    shade = (0.82 + 0.18 * pile) * rows
    save(shade[..., None] * base[None, None, :], "malibu-chenille.jpg")


def make_saltillo():
    N = 1026                      # 1 m, 3 x 3 tiles of 342 px
    rng = np.random.default_rng(31)
    rgb = np.zeros((N, N, 3))
    grout = hexc("BFB09A")
    rgb[:] = grout
    T, g = 342, 8
    tones = [hexc(h) for h in ("B5603A", "A9542F", "C06B44", "9C4C2B", "B86A3F")]
    clay = noise(N, 32, 6) * 0.5 + noise(N, 33, 1.0) * 0.5
    for i in range(3):
        for j in range(3):
            c = tones[rng.integers(len(tones))] * rng.uniform(0.93, 1.05)
            y0, x0 = i * T + g // 2, j * T + g // 2
            tile = (0.86 + 0.14 * clay[y0:y0 + T - g, x0:x0 + T - g])[..., None] * c
            # sun-bleached patches, slightly darker edges
            yy, xx = np.mgrid[0:T - g, 0:T - g]
            edge = np.minimum.reduce([yy, xx, T - g - 1 - yy, T - g - 1 - xx]) / 30.0
            tile *= (0.9 + 0.1 * np.clip(edge, 0, 1))[..., None]
            rgb[y0:y0 + T - g, x0:x0 + T - g] = tile
    save(rgb, "malibu-saltillo.jpg")


def make_talavera():
    T = 200                       # 0.2 m tile
    N = T * 5
    img = Image.new("RGB", (N, N), (236, 228, 208))
    d = ImageDraw.Draw(img)
    blue, ochre, green = (31, 62, 128), (212, 150, 40), (60, 110, 70)
    for i in range(5):
        for j in range(5):
            x0, y0 = j * T, i * T
            cx, cy = x0 + T / 2, y0 + T / 2
            d.rectangle([x0, y0, x0 + T - 1, y0 + T - 1], outline=(190, 180, 160), width=4)
            # corner quarter-rosettes join into circles across tiles
            for (qx, qy) in ((x0, y0), (x0 + T, y0), (x0, y0 + T), (x0 + T, y0 + T)):
                d.ellipse([qx - 34, qy - 34, qx + 34, qy + 34], fill=blue)
                d.ellipse([qx - 16, qy - 16, qx + 16, qy + 16], fill=ochre)
            # central star of petals
            for k in range(8):
                a = k * np.pi / 4
                px, py = cx + 42 * np.cos(a), cy + 42 * np.sin(a)
                d.ellipse([px - 17, py - 17, px + 17, py + 17], fill=blue if k % 2 == 0 else green)
            d.ellipse([cx - 24, cy - 24, cx + 24, cy + 24], fill=ochre)
            d.ellipse([cx - 9, cy - 9, cx + 9, cy + 9], fill=blue)
    img = img.filter(ImageFilter.GaussianBlur(0.8))
    a = np.asarray(img).astype(np.float64) / 255.0
    a *= (0.95 + 0.05 * noise(N, 41, 2.0))[..., None]
    save(a, "malibu-talavera.jpg")


def make_kilim():
    N = 512                       # 0.5 m
    img = Image.new("RGB", (N, N), (150, 66, 40))
    d = ImageDraw.Draw(img)
    rust, indigo, ochre, cream, brown = (150, 66, 40), (40, 52, 92), (196, 140, 52), (226, 210, 178), (74, 44, 30)
    bands = [(0, 40, brown), (40, 56, cream), (200, 216, cream), (216, 256, brown)]
    for half in (0, 256):
        for a, b, c in bands:
            d.rectangle([0, half + a, N, half + b], fill=c)
        for k in range(4):
            cx, cy = k * 128 + 64, half + 128
            for r, c in ((62, indigo), (44, ochre), (26, cream), (10, rust)):
                d.polygon([(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)], fill=c)
        for k in range(16):
            x = k * 32 + 16
            d.polygon([(x - 10, half + 48), (x, half + 40), (x + 10, half + 48), (x, half + 56)], fill=indigo)
            d.polygon([(x - 10, half + 208), (x, half + 200), (x + 10, half + 208), (x, half + 216)], fill=indigo)
    a = np.asarray(img).astype(np.float64) / 255.0
    yy = np.mgrid[0:N, 0:N][0]
    a *= (0.9 + 0.1 * (np.sin(yy * np.pi / 3) ** 2))[..., None] * (0.94 + 0.06 * noise(N, 51, 1.0))[..., None]
    save(a, "malibu-kilim.jpg")


def make_ceiling():
    # Boards 12.5 cm wide run along u (the beams cross them), honey-brown
    # stain over knotty pine, dark joints.
    N = 1024
    rng = np.random.default_rng(61)
    rgb = np.zeros((N, N, 3))
    board = N // 8
    yy, xx = np.mgrid[0:N, 0:N]
    for b in range(8):
        y0 = b * board
        tone = hexc("7A5234") * rng.uniform(0.85, 1.08)
        phase = rng.uniform(0, 6.3)
        wav = np.sin(xx[y0:y0 + board] * 0.018 + phase + 0.5 * np.sin(yy[y0:y0 + board] * 0.05))
        streak = 0.9 + 0.1 * np.sin(yy[y0:y0 + board] * 0.9 + wav * 3.0)
        shade = streak * (0.93 + 0.07 * noise(N, 62 + b, 1.0)[y0:y0 + board])
        # knots
        for _ in range(2):
            kx, ky = rng.uniform(0, N), y0 + rng.uniform(board * 0.3, board * 0.7)
            r = np.hypot((xx[y0:y0 + board] - kx) / 1.6, yy[y0:y0 + board] - ky)
            shade *= 1 - 0.45 * np.exp(-(r / 9.0) ** 2) - 0.08 * np.sin(r * 0.6) * np.exp(-(r / 30.0) ** 2)
        rgb[y0:y0 + board] = shade[..., None] * tone
        rgb[y0:y0 + 3] *= 0.45
    save(rgb, "malibu-ceiling.jpg")


def make_jazz():
    W, H = 800, 1100
    img = Image.new("RGB", (W, H), (232, 216, 184))
    d = ImageDraw.Draw(img)
    navy, orange, red, cream, ink = (28, 40, 66), (218, 120, 44), (170, 52, 38), (238, 226, 198), (30, 26, 24)
    d.rectangle([40, 40, W - 40, H - 40], fill=navy)
    # setting sun over the Pacific
    d.ellipse([170, 210, 630, 670], fill=orange)
    for k in range(7):
        y = 470 + k * 30
        d.rectangle([40, y, W - 40, y + 12 + k * 2], fill=navy)
    # keyboard band
    d.rectangle([80, 700, W - 80, 820], fill=cream)
    for k in range(17):
        x = 80 + k * (W - 160) / 17
        d.line([x, 700, x, 820], fill=ink, width=3)
    for k in range(17):
        if k % 7 in (2, 6):
            continue
        x = 80 + (k + 0.68) * (W - 160) / 17
        d.rectangle([x, 700, x + 20, 772], fill=ink)
    futura = "/System/Library/Fonts/Supplemental/Futura.ttc"
    big = ImageFont.truetype(futura, 170, index=2)
    mid = ImageFont.truetype(futura, 54, index=0)
    sml = ImageFont.truetype(futura, 34, index=0)

    def centre(text, y, font, fill):
        w = d.textlength(text, font=font)
        d.text(((W - w) / 2, y), text, font=font, fill=fill)
    centre("JAZZ", 60, big, cream)
    centre("ON THE PIER", 850, mid, orange)
    centre("MALIBU  .  SATURDAY NIGHTS", 930, sml, cream)
    centre("PIANO TRIO  .  9 PM", 985, sml, cream)
    a = np.asarray(img).astype(np.float64) / 255.0
    paper = np.asarray(Image.fromarray(np.clip(np.random.default_rng(72).normal(128, 30, (H, W)), 0, 255)
                                       .astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.2))) / 128.0
    a *= (0.94 + 0.06 * paper)[..., None]
    save(a, "malibu-jazz.jpg", 92)


def make_jazz2():
    W, H = 800, 1100
    img = Image.new("RGB", (W, H), (232, 216, 184))
    d = ImageDraw.Draw(img)
    teal, orange, cream, ink, sand = (32, 92, 96), (214, 112, 46), (240, 228, 200), (28, 26, 24), (226, 196, 140)
    d.rectangle([40, 40, W - 40, H - 40], fill=cream)
    # sky band, sun, rolling waves
    d.rectangle([70, 70, W - 70, 640], fill=sand)
    d.ellipse([250, 180, 550, 480], fill=orange)
    for k in range(6):
        y0 = 400 + k * 42
        pts = [(70, y0 + 40)]
        for x in range(70, W - 69, 10):
            pts.append((x, y0 + 14 * np.sin((x + k * 37) / 38.0)))
        pts.append((W - 70, y0 + 40))
        d.polygon(pts, fill=teal if k % 2 == 0 else (46, 116, 118))
    d.rectangle([70, 600, W - 70, 640], fill=teal)
    # upright bass silhouette
    d.ellipse([330, 200, 470, 330], fill=ink)
    d.ellipse([310, 300, 490, 470], fill=ink)
    d.rectangle([393, 90, 407, 220], fill=ink)
    d.rectangle([386, 80, 414, 100], fill=ink)
    futura = "/System/Library/Fonts/Supplemental/Futura.ttc"
    big = ImageFont.truetype(futura, 100, index=2)
    mid = ImageFont.truetype(futura, 50, index=0)
    sml = ImageFont.truetype(futura, 32, index=0)

    def centre(text, y, font, fill):
        w = d.textlength(text, font=font)
        d.text(((W - w) / 2, y), text, font=font, fill=fill)
    centre("COOL JAZZ", 690, big, teal)
    centre("SUNSET SESSIONS", 830, mid, orange)
    centre("ON THE SAND  .  EVERY FRIDAY", 910, sml, ink)
    centre("BASS  .  PIANO  .  BRUSHES", 960, sml, ink)
    a = np.asarray(img).astype(np.float64) / 255.0
    paper = np.asarray(Image.fromarray(np.clip(np.random.default_rng(73).normal(128, 30, (H, W)), 0, 255)
                                       .astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.2))) / 128.0
    a *= (0.94 + 0.06 * paper)[..., None]
    save(a, "malibu-jazz2.jpg", 92)


if __name__ == "__main__":
    make_sisal()
    make_chenille()
    make_saltillo()
    make_talavera()
    make_kilim()
    make_ceiling()
    make_jazz()
    make_jazz2()
    print("wrote malibu-*.jpg")
