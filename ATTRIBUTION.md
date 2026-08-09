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

No third-party models, textures, fonts, audio or other media are bundled.
Upstream Hubs UI assets (icons, sounds) remain MPL-2.0 from the Hubs client.

If you add any external asset, record it here: file, author, source URL, and
licence, before it ships.
