# Generates the emissive sky-dome gradients (day/dusk) for the ViewSky sphere
# from the top rows of the directional skyline photos, so the dome's horizon
# tone matches the panorama. Writes <scene>-sky-a50.jpg into the client's
# lounge-views folder (swapped at runtime by view-switcher.js) and
# bake/<scene>-sky.jpg for the Blender build.
#
# Usage: python3 make-sky.py <views-src-dir> <client-views-dir> <bake-dir>
import os, sys, colorsys
from PIL import Image

src_dir, out_dir, bake_dir = sys.argv[1:4]

def top_color(path, frac=0.04):
    im = Image.open(path).convert("RGB")
    w, h = im.size
    return im.crop((0, 0, w, max(1, int(h * frac)))).resize((1, 1), Image.BOX).getpixel((0, 0))

def blend(a, b, t):
    return tuple(int(round(a[i] * (1 - t) + b[i] * t)) for i in range(3))

def adjust(rgb, sat=1.0, val=1.0):
    h, s, v = colorsys.rgb_to_hsv(*[c / 255 for c in rgb])
    return tuple(int(round(c * 255)) for c in colorsys.hsv_to_rgb(h, min(1, s * sat), min(1, v * val)))

scenes = sorted({f.split("-")[0] for f in os.listdir(src_dir) if "-" in f and f.lower().endswith((".jpg", ".jpeg", ".png"))})
for scene in scenes:
    paths = [os.path.join(src_dir, f) for f in sorted(os.listdir(src_dir)) if f.startswith(scene + "-")]
    if scene in ("dusk", "night"):
        paths = [p for p in paths if "-north-" not in os.path.basename(p)]
        paths.append(os.path.join(src_dir, "aligned", f"{scene}-north-a46.png"))
    cols = [top_color(p) for p in paths]
    if not cols:
        continue
    horizon = tuple(int(sum(c[i] for c in cols) / len(cols)) for i in range(3))
    if scene == "night":
        # Light-polluted city night: near-black zenith, faint violet glow at the skyline.
        horizon = (24, 22, 40)
        zenith = (6, 8, 18)
        below = (16, 15, 24)
    else:
        zenith = adjust(horizon, sat=1.9 if scene == "day" else 1.5, val=0.72 if scene == "day" else 0.55)
        below = adjust(horizon, sat=0.6, val=0.62)
    W, H = 512, 256
    im = Image.new("RGB", (W, H))
    px = im.load()
    for y in range(H):
        v = y / (H - 1)
        if v < 0.46:
            c = blend(zenith, horizon, (v / 0.46) ** 1.6)
        elif v < 0.53:
            c = horizon
        else:
            c = blend(horizon, below, min(1, (v - 0.53) / 0.3))
        for x in range(W):
            px[x, y] = c
    im.save(os.path.join(bake_dir, f"{scene}-sky.jpg"), quality=88)
    im.save(os.path.join(out_dir, f"{scene}-sky-a50.jpg"), quality=88)
    print(scene, "horizon", horizon, "zenith", zenith, "below", below)
