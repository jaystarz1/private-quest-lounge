# Aligned Central Park lighting variants

Created 2026-09-05 with the imagegen editing tool, using
`../day-north-a46.jpg` as the reference for both images. The original daytime
asset is 2560 x 1078. Each output is 1933 x 814 with the same composition.
These replace the previous mirrored north photo from a different viewpoint.
They are AI lighting derivatives, not documentary nighttime photographs.

Canonical outputs: `dusk-north-a46.png` and `night-north-a46.png`.
The panorama builder applies the daytime 0.46 anchor to both and performs no
mirroring or horizontal offset. Preserve the daytime source's attribution.

## Dusk prompt

Use case: lighting-weather. Edit target: the supplied daytime north-facing Central Park photograph. Create the blue-hour dusk version of EXACTLY THIS photograph for a VR scene whose daytime/nighttime views must register. Preserve every building silhouette, park edge, reservoir, tree line, window grid, relative position and camera projection. No mirroring, horizontal shift, rotation, recropping, zoom, new buildings, or viewpoint changes. Preserve original extremely wide 2048:862 aspect ratio and full frame. Only change illumination: natural blue and muted violet twilight sky, very subtle warm horizon, cool city shadows with believable warm illuminated windows and street lights. Real photographic lighting, no captions or borders. This is a time-of-day edit, not a new city illustration. Output one full-width image.

## Night prompt

Use case: lighting-weather. Edit target: the supplied daytime north-facing Central Park photograph. Create the fully nighttime version of EXACTLY THIS photograph for a VR scene whose daytime/nighttime views must register. Preserve every building silhouette, park edge, reservoir, tree line, window grid, relative position and camera projection. No mirroring, horizontal shift, rotation, recropping, zoom, new buildings, or viewpoint changes. Preserve original extremely wide 2048:862 aspect ratio and full frame. Only change illumination: deep navy night sky with subtle urban light pollution, dark park foliage, faint park-path lighting, warm lit windows and streets, recognizable buildings without making the city bright daylight. Real photographic lighting, no captions or borders. This is a time-of-day edit, not a new city illustration. Output one full-width image.

## Verification

Run `python3 lounge-assets/verify-view-registration.py` from the project root.
The gate checks distributed feature landmarks, affine scale/rotation/offset
and the composed day-to-night transform. It does not require matching colors.
