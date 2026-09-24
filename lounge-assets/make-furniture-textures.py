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
