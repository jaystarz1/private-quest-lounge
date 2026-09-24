# Derives a night-time set of directional skyline photos from the dusk set,
# so the view switcher gets a third scene (day / dusk / night) with the same
# geometry and horizon anchors. Each dusk photo is graded: the city below the
# horizon is darkened with a cool cast while its already-lit windows and
# street glow are preserved and lifted, and the sky above the horizon is
# replaced by a deep night gradient with the dusk clouds faintly retained.
# Output: views-src/night-<dir>-aNN.jpg (same anchors as the dusk files).
#
# Usage: python3 make-night.py <views-src-dir>
import os, re, sys
import numpy as np
from PIL import Image, ImageFilter

src_dir = sys.argv[1]
ZENITH = np.array([0.020, 0.028, 0.070])
HORIZON = np.array([0.105, 0.085, 0.140])   # light-polluted glow just above the skyline
CITY_TINT = np.array([0.80, 0.86, 1.05])

for fn in sorted(os.listdir(src_dir)):
    m = re.match(r"^dusk-(north|east|south|west)-a(\d{1,2})\.(jpe?g|png)$", fn, re.I)
    if not m:
        continue
    d, anchor = m.group(1), int(m.group(2))
    if d == "north":
        # The registered night edit lives in aligned/night-north-a46.png.
        # Do not regenerate the obsolete different-camera north photo.
        continue
    im = Image.open(os.path.join(src_dir, fn)).convert("RGB")
    a = np.asarray(im, np.float64) / 255.0
    h, w, _ = a.shape
    lum = a @ np.array([0.299, 0.587, 0.114])
    warmth = (a[..., 0] - a[..., 2]).clip(0, 1)
    def blur(x, r):
        return np.asarray(Image.fromarray((x.clip(0, 1) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(r)), np.float64) / 255.0
    # --- lit windows and street lights: local highlights only (a high-pass),
    # so a bright sky or water band is not mistaken for city lights ---
    local = (lum - blur(lum, max(3, w // 140))).clip(0, 1)
    # only point-like highlights inside dark surroundings count as lights;
    # bright sky or water next to a dark tower is not a lit window
    surround = blur(lum, max(6, w // 60))
    lights = (local / 0.10).clip(0, 1) * ((lum - 0.30) / 0.30).clip(0, 1) * (0.55 + 0.45 * warmth) * ((0.42 - surround) / 0.18).clip(0, 1)
    glow = blur(lights, max(2, w // 300))
    # --- city: darkened and cooled, normalised so every direction lands at a
    # similar night level regardless of how bright the dusk photo was ---
    hr = anchor / 100.0 * h
    t = ((np.arange(h) - (hr - 0.03 * h)) / (0.11 * h)).clip(0, 1)[:, None, None]  # 0 sky .. 1 city
    dark = (a ** 1.45) * CITY_TINT
    city_rows = t[:, 0, 0] > 0.5
    mean_dark = float((dark[city_rows] @ np.array([0.299, 0.587, 0.114])).mean()) if city_rows.any() else 0.2
    gain = float(np.clip(0.085 / max(mean_dark, 1e-3), 0.25, 3.0))
    city = dark * gain
    # --- sky: deep night gradient with the dusk cloud structure faintly kept ---
    rows = (np.arange(h) / max(1.0, hr)).clip(0, 1)[:, None, None]
    grad = ZENITH * (1 - rows ** 1.4) + HORIZON * (rows ** 1.4)
    sky = grad + (a ** 1.8) * 0.14 * (0.3 + 0.7 * rows)
    out = sky * (1 - t) + city * t
    out = out + a * lights[..., None] * 0.95 + a * glow[..., None] * 0.30
    out = (out.clip(0, 1) ** 0.95 * 255).round().astype(np.uint8)
    print(f"  {d}: mean_dark {mean_dark:.3f} gain {gain:.2f}")
    dst = os.path.join(src_dir, f"night-{d}-a{anchor}.jpg")
    Image.fromarray(out).save(dst, quality=90)
    print(dst, im.size)
