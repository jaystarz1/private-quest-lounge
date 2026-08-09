# TESTING — private-quest-lounge

## Phase 1: foundation verification (2026-08-08, local, automated)

Environment: macOS (Darwin 25.5.0), Docker Desktop 29.2.1, stack via `bin/up`.
Host resolution: `hubs.local`/`hubs-proxy.local` → 127.0.0.1 (mDNS proxy for
interactive use; the automated tests pin `--host-resolver-rules` in Chromium).

Test harness: Playwright + bundled Chromium (headless), flags
`--ignore-certificate-errors --use-fake-ui-for-media-stream
--use-fake-device-for-media-stream` (fake mic = auto-granted permission with a
test tone). Script: `phase1-test.mjs` (scratchpad; flow documented here).

Exact flow executed:
1. Client A → `https://hubs.local:4000/` → Sign In → email entered.
2. Magic link fished from `docker compose logs reticulum`, opened in A's context (first account = admin).
3. A clicked **Create Room** → room `https://hubs.local:4000/ePuQYhq/...` (unguessable 7-char hub_sid).
4. A completed join flow (display name → Enter on Screen). `APP.scene.is("entered")` = true.
5. Client B (separate browser context, anonymous, no account) opened the exact room URL and joined the same way.

Results (all read from live page state, not inferred):

| Check | A | B |
|---|---|---|
| Entered room | true | true |
| Presence count seen | 2 | 2 |
| Dialog (mediasoup) connected | true | true |
| Mic producer created | true | true |
| Remote audio consumers | 1 | 1 |

Voice verdict: each client both produces mic audio and consumes exactly one
remote audio track — the two-way SFU voice path works.

WebXR: `navigator.xr` present; `immersive-vr` **not** supported in headless
Chromium (no XR runtime) so the Enter VR button correctly does not appear.
Desktop (non-VR) fallback fully verified. **No Quest testing has occurred yet**
— actual VR entry remains unverified until tested on hardware.

Rendering: WebGL renders; the room shows a dark void because the dev database
seeds no scene (environment loads the stock loading-scene with spawn point +
nav mesh). Replaced by the lounge scene in Phase 2.

## Phase 2: private lounge verification (2026-08-08, local, automated)

Room `XDmNmuE` created by the admin account; all values read from live page
state. Screenshots in `docs/screenshots/`.

| Check | Result |
|---|---|
| Room `room_size` | 2 |
| Member permissions | voice_chat + text_chat only (all spawning false) |
| Lounge scene loads (63 meshes, bbox 6.4 x 3.2 x 5.2 m) | ✓ |
| Nav mesh + 2 spawn points + 4 seat waypoints inflated | ✓ |
| Spawn faces into the room (raycast: nearest wall 4.5 m) | ✓ |
| Preset avatar auto-assigned to both users (amber…plum set) | ✓ |
| Both users see each other's avatar + nameplate + voice ring | ✓ |
| Seat: `tryToOccupy(Seat_A1)` → occupied, rig at cushion (-0.44, 0, 1.46) | ✓ |
| Stand up: return to spawn releases seat | ✓ |
| Third participant: `canEnterRoom` false, never enters (lobby only) | ✓ |
| Anonymous user: no Create Room control anywhere | ✓ |
| Bad invite URL → "bad Room ID" screen | ✓ |

## Phase 3: performance + failure modes (2026-08-08, local, automated)

- Renderer with 2 avatars in room: **64 draw calls, 2,104 triangles,
  21 textures** — far inside Quest 2 budget (the usual mobile-VR guidance is
  ≤100 calls / ≤300k tris).
- Peer disconnect (tab closed): remaining user sees "Guest left the room" in
  the presence log within seconds; presence count drops 2 → 1.
- Rejoin: same invite URL re-enters cleanly; presence back to 2.
- Microphone denied (`getUserMedia` → NotAllowedError): user still enters the
  room muted; mic feedback shown in the setup screen.
- Room already full: third client held in lobby (see Phase 2).

## Quest Browser checklist (to run on hardware)

- [ ] Open invite URL in Meta Quest Browser (deployed HTTPS instance; Quest will not accept the local self-signed certs without fuss)
- [ ] Enter VR button appears and starts an immersive session
- [ ] Teleport locomotion works on the lounge nav mesh
- [ ] Both participants audible; mouth indicator moves on speech
- [ ] Sit on each couch cushion hotspot; stand up again
- [ ] Frame rate acceptable on Quest 2 (use `?stats=true`)
- [ ] Mic-permission denial shows feedback and recovers
- [ ] Second headset/browser joining beyond 2 occupants is rejected gracefully
