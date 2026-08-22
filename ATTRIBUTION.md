# Attribution

## Code

- **Hubs client, Reticulum, Dialog, Spoke, hubs-compose** — Hubs Foundation,
  [MPL-2.0](https://www.mozilla.org/en-US/MPL/2.0/). Forked; licence and
  notices preserved in each `services/*` checkout and `upstream` git remotes
  kept.

## Art assets

All scene and avatar assets are **original procedural work** created for this
project by generator scripts in `lounge-assets/`:

| Asset | Source | Licence |
|---|---|---|
| `lounge.glb` (room, furniture, lamps, window, art) | `generate-lounge.mjs` (procedural geometry, flat colours, no textures) | Same as repo |
| `avatar-*.glb` × 6 | `generate-avatars.mjs` (procedural; bone naming/proportions follow the upstream MPL-2.0 `DefaultAvatar.glb` skeleton convention, no upstream mesh data copied) | Same as repo |
| `lounge.glb` environment (penthouse: rooms, furniture, stairs, textures; decimated + Hubs components added via `lounge-assets/build-penthouse.py` + `inject-hubs.mjs`) | ["Luxury Penthouse (Fully Furnished)"](https://sketchfab.com/3d-models/luxury-penthouse-fully-furnished-c7b74d9fd0334b55b66fba937d99b6e1) by Home Design 3D, Sketchfab | **CC BY-NC-SA 4.0** — non-commercial use only; derivatives (our modified GLB) carry the same licence. Do NOT reuse this room in any paid product. |
| Central Park day view (embedded placeholder in `lounge.glb` + `00-centralpark-day-a46.jpg` in `lounge-views/`) | ["Central Park from the Top of the Rock 2"](https://commons.wikimedia.org/wiki/File:Central_Park_from_the_Top_of_the_Rock_2_(4693129360).jpg) by Tony Hisgett, via Wikimedia Commons | **CC BY 2.0** (attribution required — this row is it) |
| Central Park dusk view (`01-centralpark-dusk-a55.jpg` in `lounge-views/`) | ["Central Park & Beyond"](https://commons.wikimedia.org/wiki/File:Central_Park_%26_Beyond_(24077159163).jpg) by Phil Dolby, via Wikimedia Commons | **CC BY 2.0** (attribution required — this row is it) |

Gallery art embedded in `lounge.glb` (all **public domain**, via Wikimedia Commons):
Tom Thomson *The Jack Pine* & *The West Wind*; J.E.H. MacDonald *The Tangled
Garden*; Monet *Impression, Sunrise*; Van Gogh *The Starry Night*, *Sunflowers*
& *Café Terrace at Night*; Renoir *Bal du moulin de la Galette*; Klimt *The
Kiss*; Hokusai *The Great Wave off Kanagawa*. (Requested Dalí/Warhol were not
used: their works remain under copyright.)

No other third-party models, textures, fonts, audio or media are bundled.
Upstream Hubs UI assets (icons, sounds) remain MPL-2.0 from the Hubs client.

If you add any external asset, record it here: file, author, source URL, and
licence, before it ships.
