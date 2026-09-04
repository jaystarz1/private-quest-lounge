# Stitches the four directional skyline photos of a scene (north/east/south/
# west, each with a "-aNN" horizon anchor = percent from the top) into one
# cylindrical panorama with feathered seams, so the view wraps around the
# penthouse without 90-degree corners. Layout: u=0 at the NW corner, then
# north, east, south, west quadrants left to right; horizon at 55.9% of the
# height (z 3.5 m on a cylinder spanning z -4..13). Also writes a 1024-wide
# placeholder for the Blender bake.
#
# Usage: python3 make-pano.py <views-src-dir> <client-views-dir> <bake-dir>
import os, re, sys, colorsys
import numpy as np
from PIL import Image

src_dir, out_dir, bake_dir = sys.argv[1:4]
W, H = 8192, 1312          # 2048 px per 90 degrees; 17 m of height
HORIZON_ROW = int(round((13.0 - 3.5) / 17.0 * H))
QUAD = W // 4
FEATHER = 182              # 8 degrees each side of every seam
ORDER = ["north", "east", "south", "west"]

files = {}
for fn in os.listdir(src_dir):
    m = re.match(r"^([a-z0-9]+)-(north|east|south|west)(?:-a(\d{1,2}))?\.(?:jpe?g|png)$", fn, re.I)
    if m:
        files.setdefault(m.group(1), {})[m.group(2).lower()] = (os.path.join(src_dir, fn), int(m.group(3) or 50) / 100)

for scene, byDir in sorted(files.items()):
    if any(d not in byDir for d in ORDER):
        print(f"{scene}: missing directions, skipped"); continue
    acc = np.zeros((H, W, 3), np.float64)
    wsum = np.zeros((H, W, 1), np.float64)
    span = QUAD + 2 * FEATHER
    ramp = np.minimum(np.minimum(np.arange(span) / FEATHER, (span - 1 - np.arange(span)) / FEATHER), 1.0).clip(0, 1)
    for qi, d in enumerate(ORDER):
        path, anchor = byDir[d]
        im = Image.open(path).convert("RGB")
        w0, h0 = im.size
        h = int(round(span * h0 / w0))
        im = im.resize((span, h), Image.LANCZOS)
        arr = np.asarray(im, np.float64)
        top = HORIZON_ROW - int(round(anchor * h))
        # Full-height strip: image rows in place; above the photo, blend its
        # mean sky colour up to a deeper zenith tone (clamping edge rows made
        # vertical streaks); below it, its mean ground colour darkens slightly.
        top_col = arr[:8].mean(axis=(0, 1))
        bot_col = arr[-8:].mean(axis=(0, 1))
        hsv = colorsys.rgb_to_hsv(*(top_col / 255.0))
        zenith = np.array(colorsys.hsv_to_rgb(hsv[0], min(1.0, hsv[1] * 1.7), hsv[2] * 0.72)) * 255.0
        strip = np.empty((H, span, 3), np.float64)
        for r in range(H):
            if r < top:
                t = ((top - r) / max(top, 1)) ** 0.8
                strip[r] = top_col * (1 - t) + zenith * t
            elif r >= top + h:
                t = min(1.0, (r - top - h) / 400.0)
                strip[r] = bot_col * (1 - 0.18 * t)
            else:
                strip[r] = arr[r - top]
        # feather the photo's own top/bottom edges into the fill
        for k in range(min(40, h)):
            f = k / 40.0
            if 0 <= top + k < H:
                strip[top + k] = strip[top + k] * f + (top_col * (1 - f))
            rb = top + h - 1 - k
            if 0 <= rb < H:
                strip[rb] = strip[rb] * f + (bot_col * (1 - f))

        x0 = qi * QUAD - FEATHER
        cols = (np.arange(span) + x0) % W
        acc[:, cols] += strip * ramp[None, :, None]
        wsum[:, cols] += ramp[None, :, None]
        print(f"{scene}/{d}: {w0}x{h0} anchor {anchor:.2f} -> strip rows {top}..{top + h}")
    pano = (acc / np.maximum(wsum, 1e-6)).clip(0, 255).astype(np.uint8)
    out = Image.fromarray(pano)
    out.save(os.path.join(out_dir, f"{scene}-pano.jpg"), quality=86, optimize=True)
    out.resize((1024, H * 1024 // W), Image.LANCZOS).save(os.path.join(bake_dir, f"{scene}-pano.jpg"), quality=85)
    print(f"{scene}: wrote {W}x{H} panorama")
