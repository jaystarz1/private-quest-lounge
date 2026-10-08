# Generates the seamless furniture textures used by build-penthouse.py and
# build-spa.py: woven outdoor cushion fabric, resin wicker, ivory linen,
# Capri-blue canvas and teak grain. Deterministic (fixed seeds), 512 px tiles.
#
# Usage: python3 make-furniture-textures.py   (writes into art/)
import os
import numpy as np
from PIL import Image

N = 512
ART = os.path.join(os.path.dirname(os.path.abspath(__file__)), "art")


def periodic_noise(seed, cutoff, aniso=(1.0, 1.0)):
    """Band-limited noise that tiles exactly (FFT filtering is periodic).
    aniso (x, y): a large factor on one axis stretches features along the other."""
    rng = np.random.default_rng(seed)
    f = np.fft.fft2(rng.standard_normal((N, N)))
    ky, kx = np.meshgrid(np.fft.fftfreq(N) * N, np.fft.fftfreq(N) * N, indexing="ij")
    r = np.hypot(kx * aniso[0], ky * aniso[1])
    n = np.real(np.fft.ifft2(f * np.exp(-(r / cutoff) ** 2)))
    return (n - n.mean()) / (n.std() + 1e-9)


def hexrgb(h):
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], dtype=np.float64) / 255.0


def save(name, shade, base, tint_noise=None, tint=None):
    rgb = shade[..., None] * base[None, None, :]
    if tint_noise is not None:
        rgb = rgb + tint_noise[..., None] * tint[None, None, :]
    img = Image.fromarray((np.clip(rgb, 0, 1) * 255 + 0.5).astype(np.uint8), "RGB")
    img.save(os.path.join(ART, name), optimize=True)
    print("wrote", name)


def weave(cells, seed, relief, slub=0.0, twill=False):
    """Plain (or twill) weave. Returns a brightness field around 1.0."""
    y, x = np.mgrid[0:N, 0:N] / N * cells
    i, j = np.floor(x).astype(int), np.floor(y).astype(int)
    fx, fy = x - i, y - j
    over = ((i - j) % 3 < 2) if twill else ((i + j) % 2 == 0)
    # A thread is brightest along its centre line and dips at its edges and
    # where it passes under the crossing thread.
    along_h = np.abs(np.sin(np.pi * fy)) ** 0.6 * (0.75 + 0.25 * np.sin(np.pi * fx))
    along_v = np.abs(np.sin(np.pi * fx)) ** 0.6 * (0.75 + 0.25 * np.sin(np.pi * fy))
    thread = np.where(over, along_h, along_v)
    shade = 1.0 - relief + relief * thread
    # Per-thread brightness variation (yarn to yarn) and slubs along yarns.
    rng = np.random.default_rng(seed)
    row = rng.normal(0, 0.035, cells)[j % cells]
    col = rng.normal(0, 0.035, cells)[i % cells]
    shade = shade + np.where(over, row, col)
    if slub:
        sh = periodic_noise(seed + 1, 22, (1.0, 0.15))
        sv = periodic_noise(seed + 2, 22, (0.15, 1.0))
        shade = shade + slub * np.where(over, sh, sv)
    return shade


os.makedirs(ART, exist_ok=True)

# Patio sectional cushions: oatmeal outdoor canvas, 0.25 m tile, 48 yarns.
mottle = periodic_noise(11, 6)
shade = weave(48, 10, relief=0.30, slub=0.012) + 0.012 * mottle
save("fabric-oatmeal.png", shade, hexrgb("E8DCC2"))

# Capri chair pads: ivory slub linen, 0.25 m tile, 56 yarns.
shade = weave(56, 20, relief=0.22, slub=0.06) + 0.02 * periodic_noise(21, 5)
save("linen-ivory.png", shade, hexrgb("F6EAD2"))

# Capri foot cushions and stripes: blue twill canvas, 0.25 m tile.
shade = weave(60, 30, relief=0.32, slub=0.03, twill=True) + 0.04 * periodic_noise(31, 6)
save("canvas-capri-blue.png", shade, hexrgb("2A6AA6"))

# Patio frame: resin wicker basket weave. 0.30 m tile, 14 strand pairs, deep
# gaps between strands so the frame reads as woven, not painted.
cells = 14
y, x = np.mgrid[0:N, 0:N] / N * cells
i, j = np.floor(x).astype(int), np.floor(y).astype(int)
fx, fy = x - i, y - j
over = (i + j) % 2 == 0
strands = 3  # three flat strands side by side per cell
h = np.abs(np.sin(np.pi * fy * strands)) ** 0.5 * np.abs(np.sin(np.pi * fx)) ** 0.25
v = np.abs(np.sin(np.pi * fx * strands)) ** 0.5 * np.abs(np.sin(np.pi * fy)) ** 0.25
thread = np.where(over, h, v)
grain = np.where(over, periodic_noise(41, 40, (1.0, 0.08)), periodic_noise(42, 40, (0.08, 1.0)))
shade = 0.35 + 0.75 * thread + 0.06 * grain
save("wicker-espresso.png", shade, hexrgb("5A4030"), tint_noise=thread * 0.05, tint=hexrgb("C89A63"))

# Capri frames: teak grain running along U, 1 m tile.
y, x = np.mgrid[0:N, 0:N] / N
warp = periodic_noise(51, 3) * 0.035
rings = np.sin((y + warp + 0.02 * periodic_noise(52, 8, (1.0, 0.1))) * np.pi * 2 * 16)
fine = periodic_noise(53, 45, (1.0, 0.06))
shade = 1.0 + 0.12 * rings + 0.03 * fine + 0.05 * periodic_noise(54, 4)
save("teak-grain.png", shade, hexrgb("B07E4E"))

# Sauna lining: horizontal tongue-and-groove hemlock/cedar boards, 1 m tile,
# eight 125 mm boards per tile, each board its own honey tone, dark V-groove
# at every joint, grain running along U.
y, x = np.mgrid[0:N, 0:N] / N
boards = 8
b = np.floor(y * boards).astype(int)
fy = y * boards - b
tone = np.array([1.00, 0.93, 1.05, 0.96, 1.02, 0.90, 0.98, 1.04])[b % boards]
groove = np.clip(np.minimum(fy, 1 - fy) / 0.045, 0, 1) ** 0.6
grain = periodic_noise(61, 60, (1.0, 0.04))
knots = np.clip(periodic_noise(62, 6) - 2.2, 0, None)
shade = tone * (0.55 + 0.45 * groove) + 0.07 * grain - 0.25 * knots
save("sauna-cedar.png", shade, hexrgb("C8935C"))


# --- Neutral detail maps for the finish pass (build-penthouse.py) -----------
# Every flat-colour material in the scene multiplies one of these grey tiles
# into its own base colour (glTF baseColorFactor x baseColorTexture), so the
# palette stays exactly as chosen and only surface character is added. Each
# map is normalised to mean DETAIL_MEAN and peak 1.0; the build divides the
# factor by the same mean so the average colour does not darken.
DETAIL_MEAN = 0.9


def save_detail(name, shade, contrast):
    s = (shade - shade.mean()) / (shade.std() + 1e-9)
    s = s * contrast
    s = np.clip(s, -3 * contrast, 3 * contrast)
    s = s - s.max() + 1.0                      # peak exactly 1.0
    s = s * (DETAIL_MEAN / s.mean())           # mean exactly DETAIL_MEAN
    img = Image.fromarray((np.clip(s, 0, 1) * 255 + 0.5).astype(np.uint8), "L").convert("RGB")
    img.save(os.path.join(ART, name), quality=90)
    print("wrote", name)


# Plaster/limewash: soft trowel mottle, faint trowel arcs, fine sand. 2 m
# tile. Kept low: stronger mottle read as blotchy velvet on the navy walls.
y, x = np.mgrid[0:N, 0:N] / N
cloud = periodic_noise(71, 10) + 0.6 * periodic_noise(72, 28) + 0.5 * periodic_noise(73, 120)
arcs = np.sin((x * 9 + 0.6 * periodic_noise(74, 4)) * np.pi * 2) * np.clip(periodic_noise(75, 6), 0, None)
save_detail("detail-plaster.jpg", cloud + 0.18 * arcs, 0.018)

# Painted joinery and cabinet fronts: fine roller stipple, faint vertical
# brush drag. 1 m tile.
stipple = periodic_noise(81, 180) + 0.5 * periodic_noise(82, 60)
drag = periodic_noise(83, 50, (1.0, 0.05))
save_detail("detail-paint.jpg", stipple + 0.6 * drag + 0.4 * periodic_noise(84, 5), 0.022)

# Wood: long grain along U with growth-ring figure and pores. 1 m tile.
warp = periodic_noise(91, 3) * 0.05
rings = np.sin((y + warp + 0.015 * periodic_noise(92, 10, (1.0, 0.1))) * np.pi * 2 * 22)
pores = periodic_noise(93, 160, (1.0, 0.03))
save_detail("detail-wood.jpg", rings + 0.8 * pores + 0.5 * periodic_noise(94, 4), 0.085)

# Fabric/upholstery/rugs: plain weave. 0.2 m tile.
shade = weave(64, 101, relief=0.35, slub=0.03) + 0.03 * periodic_noise(102, 5)
save_detail("detail-fabric.jpg", shade, 0.07)

# Stone/concrete/worktops: honed speckle with soft clouding. 1 m tile.
speck = np.clip(periodic_noise(111, 200), 1.2, None) - np.clip(-periodic_noise(112, 200), 1.4, None)
save_detail("detail-stone.jpg", speck + 0.9 * periodic_noise(113, 6) + 0.4 * periodic_noise(114, 30), 0.045)

# Metal: brushed streaks along U. 0.5 m tile.
save_detail("detail-metal.jpg", periodic_noise(121, 220, (0.02, 1.0)) + 0.3 * periodic_noise(122, 8), 0.035)

# BBQ island: dark flamed granite worktop (coloured, used as-is). 0.6 m tile.
g = periodic_noise(131, 150)
flecks = (g > 1.6) * 0.35 - (periodic_noise(132, 150) > 1.8) * 0.25
shade = 1.0 + flecks + 0.08 * periodic_noise(133, 8)
save("granite-charcoal.png", shade, hexrgb("3A3836"))

# BBQ island: dry-stacked ledgestone, courses of long thin stones with deep
# shadow joints. 1 m tile, 10 courses.
courses = 10
c = np.floor(y * courses).astype(int)
fy = y * courses - c
rng = np.random.default_rng(141)
offsets = rng.uniform(0, 1, courses)
lengths = rng.uniform(0.18, 0.42, courses)
u = (x + offsets[c % courses]) / lengths[c % courses]
k = np.floor(u).astype(int)
fu = u - k
stone_tone = rng.normal(1.0, 0.08, (courses, 64))[c % courses, k % 64]
edge = np.clip(np.minimum(fy, 1 - fy) / 0.12, 0, 1) ** 0.5 * np.clip(np.minimum(fu, 1 - fu) * lengths[c % courses] / 0.02, 0, 1) ** 0.5
shade = stone_tone * (0.35 + 0.65 * edge) + 0.06 * periodic_noise(142, 40)
save("ledgestone.png", shade, hexrgb("9A9186"), tint_noise=periodic_noise(143, 4) * 0.03, tint=hexrgb("A0826A"))

# Closet contents atlas: 8 x 8 swatches (row-major, index = row * 8 + col).
# Rows 0-4 garments (weave), row 5 knits, row 6 leather, row 7 wood/kraft.
CLOSET_SWATCHES = [
    # shirting and blouses
    "F4F1EA", "DCE6F0", "A9C4DE", "F2D9D4", "E8E2D0", "C9D6C4", "FFFFFF", "D8D2E6",
    # suiting and trousers
    "2B2F38", "3C3F46", "5A5E66", "1E2A40", "6B5B4A", "8C8272", "2F3B2E", "4A3A36",
    # dresses and silks
    "7A1F2B", "1F4E5F", "C8A45A", "2E2E2E", "B85C4A", "5E3F6E", "E0C9A6", "345C4B",
    # coats and outerwear
    "8A6A48", "3E3A36", "B8A58C", "22252B", "6E2F2A", "56614A", "9C8F7E", "2E3F52",
    # denim and casual
    "35507A", "4C6B94", "23324F", "7E8C99", "B5B09F", "8E5A3C", "C77B5A", "5F7F6A",
    # knitwear
    "D9CDB8", "9A8F82", "6D4C41", "B84A3E", "2F4F6F", "C9B27C", "7C8B6F", "E6DDD0",
    # leather (shoes, boots, belts, bags)
    "1A1512", "3B2618", "6B3F22", "8C5A34", "A67B52", "2A2A2C", "5C2A2A", "D8C8B0",
    # oak shelves, kraft boxes, wicker, hangers, rail steel, soles
    "B08A5E", "A88B64", "C2A06E", "8B6B45", "C9C4BC", "262422", "E2D6C0", "4A3B2E",
]
cell = N // 8
atlas = np.zeros((N, N, 3))
yy, xx = np.mgrid[0:cell, 0:cell]
for idx, hx in enumerate(CLOSET_SWATCHES):
    r, cidx = divmod(idx, 8)
    col = hexrgb(hx)
    if r < 5:
        cells = 8
        fyc, fxc = yy / cell * cells, xx / cell * cells
        over = ((np.floor(fxc) + np.floor(fyc)) % 2 == 0)
        th = np.where(over, np.abs(np.sin(np.pi * fyc)), np.abs(np.sin(np.pi * fxc))) ** 0.6
        shade = 0.86 + 0.14 * th
    elif r == 5:
        shade = 0.84 + 0.16 * np.abs(np.sin(np.pi * xx / cell * 6)) ** 0.5 * np.abs(np.sin(np.pi * yy / cell * 12)) ** 0.3
    elif r == 6:
        shade = 0.93 + 0.07 * np.cos(yy / cell * np.pi * 2) * np.cos(xx / cell * np.pi * 2)
    else:
        shade = 0.9 + 0.1 * np.sin(yy / cell * np.pi * 2 * 3) ** 2
    atlas[r * cell:(r + 1) * cell, cidx * cell:(cidx + 1) * cell] = shade[..., None] * col
Image.fromarray((np.clip(atlas, 0, 1) * 255 + 0.5).astype(np.uint8), "RGB").save(os.path.join(ART, "closet-atlas.png"), optimize=True)
print("wrote closet-atlas.png")
