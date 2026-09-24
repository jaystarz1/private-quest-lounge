# TESTING — private-quest-lounge

## Capri spa renovation (2026-09-11)

The fake elevator bank and the west/north-return partitions are removed.
The hot tub deck, former pocket and covered lounge share a level travertine
floor. Two blue-and-ivory teak lounge chairs face one another across a low
ceramic table, with footrests, a scalloped canopy, towels and Capri signage.
`build-spa.py` runs within the main scene build before seats and navigation.

- `verify-spa.py`: 77 exported-geometry checks pass, including cleared wall
  and pocket, aisle floor/headroom, navigation coverage, cushion alignment,
  opposite seat directions, unobstructed seated sightlines and sign direction.
- Existing `verify-cafe.py`: all 107 checks pass.
- Build navigation gate: 22 occupied regions connected; 182,613 triangles,
  388 primitives, four real-time lights.
- Both additional chairs carry clickable, networked Hubs seat waypoints;
  the original four submerged hot tub seats remain.
- GLTF validator: zero errors and zero warnings (custom extension ignored).
- Four rendered viewpoints reviewed after correcting sign direction, floor
  overlap and the dark entrance-wall finish. Preview: `docs/screenshots/spa-capri.png`.
- Public room connection failed before deployment with mediasoup
  `no more available ports`; TCP also failed. Active transports were present,
  so the voice service was not restarted. This limits live multiplayer seating
  acceptance; geometry and waypoint metadata were checked independently.

Atomic release: `.public-releases/1789123932607-2eeb3e72`. Production build
passes. Public room requests `lounge-2daa589c16dd19d0c39f..glb`; HTTP 200,
15,478,880 bytes, SHA-256
`6d0d9ac9de175bfa8418cfdcd3243dfa1512d5e04955197fd175b2fbfc00d943`
matches the checked local GLB. Public asset contains both occupiable spa seats
and no fake lift nodes. Voice connection failure persists after deployment.

## Café finishing and Quest comfort (2026-09-08)

The serving slab ends at the hatch instead of covering the kitchen worktop.
A real open glazed door connects the kitchen to the café terrace. The covered
walk walls are finished, original 1940s-inspired Paris posters replace the
Great Wave outside, and the Great Wave is rehung inside the vestibule. The
upstairs east-ledge plant is moved into the sky den in a complete, smaller pot
with verified furniture clearance. The café table has draped gingham and a
modeled vase of roses.

- Exported Hubs GLB: 107 geometry checks pass, including bidirectional door
  rays, exposed original worktop, continuous doorway navmesh, all café seats,
  required finishes, planter room bounds and 24 furniture-clearance samples.
- Build navigation gate: all 20 occupied regions remain connected.
- Final geometry: 170,701 triangles, 383 primitives, four real-time lights.
- 32 client tests pass, including new `scripts/quest-comfort.test.cjs` tests
  that run the actual WebXR driver and haptic system to reach mock actuators.
  The missing WebXR actuator publication was the touch-buzz failure.
- Actual character-controller tick tests verify standing calibration from a
  seated headset height, equal head/hand lift, preserved crouching, no drift,
  explicit seat height, desktop exit, and teleporting between storeys.
- TypeScript, scoped ESLint, Python syntax and diff whitespace checks pass.
- Blender views reviewed the café frontage, approach, kitchen worktop,
  poster wall, planter and relocated Japanese painting.

Fresh public-browser verification confirms entry, all seven new/relocated assets,
a direct live navmesh route through the café door, the new standing-calibration
object, and no page errors. Atomic release: `.public-releases/1788924512959-bc47624f`.

Physical Quest pulses and headset comfort still require on-device acceptance.

## Café terrace renovation (2026-09-07)

The kitchen south wall now has a 2.66 m serving hatch, cut through the wall,
backsplash and upper cupboards, with a marble counter at 1.14 m. The café
stonework wraps the actual west return at x=6.086; limestone flags continue
into the covered walk. The original two seat anchors remain unchanged.

Regression gate: `blender -b -P lounge-assets/verify-cafe.py -- lounge-assets/penthouse-hubs.glb`.
All 42 checks pass: bidirectional hatch rays, counter height, unobstructed
walkway and actual chair surfaces/anchors. The build's navigation gate passes
all 20 occupied regions on one connected component. Three Blender renders
reviewed the frontage, covered-walk approach and kitchen-facing-out view.
No additional real-time lights were added; repeated façade parts are joined.

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

## September 5 penthouse release verification

The August figures above describe the former low-poly lounge, not the current
penthouse. Do not use them as current Quest performance acceptance.

Automated gates, 2026-09-05:

- 29 client tests pass: consent/replay/expiry, paired target geometry, Stop races,
  touch opt-in/heartbeat coalescing, upper-arm and forearm contact, face morph
  ownership, real full-body leg/arm rigs, render-order hand visibility, atomic
  client releases, wall-TV filtering and history restoration before hub metadata.
- 17 isolated Elixir tests pass, including real Phoenix PubSub, Presence and
  channel serialization. Sender/target identity, entered-room status, blocks,
  rate limits and Stop priority are verified without database-writing services.
- Six TV-control tests pass: one-time pairing, authentication, replay/retry,
  output recovery, heartbeat state, permission/launch failure and HTTP methods.
- TypeScript checks, scoped ESLint, shell/Node syntax and diff whitespace checks pass.
- Panorama registration: day/dusk 120 landmark inliers, median 0.94 px;
  dusk/night 28 inliers, median 1.82 px. Day is the orientation reference.

Run from the parent repository (Docker Desktop must be running):

```sh
docker compose -f docker-compose.yml -f docker-compose.public.yml exec -T hubs-client node --test scripts/lounge-social.test.js scripts/social-animation.test.cjs scripts/social-state.test.cjs scripts/avatar-leg-ik.test.js scripts/avatar-arm-ik-frame.test.js scripts/public-release.test.js scripts/lounge-tv.test.cjs scripts/change-hub.test.cjs
docker compose -f docker-compose.yml -f docker-compose.public.yml exec -T reticulum mix run --no-start -e 'ExUnit.start(); Code.require_file("test/ret/lounge_social_test.exs"); Code.require_file("test/ret_web/channels/lounge_social_channel_test.exs")'
node --test tests/tv-service.test.cjs
python3 lounge-assets/verify-view-registration.py
```

Live two-browser checks on the public room:

- Both full-body personal avatars load, feet follow the current storey, and
  floor sitting/standing returns motion control. Paired floor sitting has zero
  measured leg reach error on both avatars at desktop height.
- Wave activates from the visible menu. Hand-holding, hug, slow dance and
  sit-together require recipient acceptance. Either participant's Stop ends the
  pair. Standing emotes/paired poses do not relocate the headset viewpoint.
- The hug visual check caught two existing arm defects: world-space rest poses
  did not follow avatar yaw, and stock bone-visibility collapsed desktop hands
  to scale 1e-8. Both are fixed. Actual-GLB regression drift is below 2.7e-8 m;
  the rendered hug no longer has the torn hand/arm ribbons.
- A smile reaches the remote head and eyelashes while `jawOpen` remains under
  voice ownership. Procedural clips/expressions are not tracked bodies/faces.
- With synthetic contact supplied to the real two-client relay, one opt-in
  yields zero pulse requests; both opt-ins yield one left/right request at
  strength 0.22 for 80 ms each. Sustained contact does not repeat. This verifies
  transport and haptic requests, not physical Quest controller vibration.
- Synthetic TV: upright 1920 x 1080, 30 fps, all four chart corners visible,
  16x filtering on the wall without a counter monitor, decoded remote frames
  and received audio packets. Video publishes before the deliberately delayed
  15-second audio permission resolves. Stop ends both synthetic tracks and
  restores the fixture output. No Mac desktop or hardware microphone captured.
- Day is restored in the database at revision 8. Saved night state and a late
  arrival were checked before restoration. Geometry uses the same north image
  registration, crop and horizon anchor across day/dusk/night.
- Coturn establishes a forced LAN WebRTC relay connection with growing media
  counters. Public TURN TCP 3478 was refused; router forwarding is still needed.

The final reload check also found an early `popstate` dereference before
`APP.hub` exists. A guarded initial-loading path now has its own regression;
normal history navigation after metadata arrives remains enabled.
The deployed reload and an explicit history event now complete without a page
error. All six panorama/sky runtime inputs are removed from the ignore rules
and included in the pending client check-in so the window views are reproducible.

The full-body avatars add 49,899 triangles and about 1.57 MB combined to the
previous pair. Hardware frame-time/comfort acceptance remains separate from
these browser and geometry checks. See [controls and hardware gate](guides/penthouse-controls.md).

Publication gate: the attempted scoped commit/push was rejected before execution.
GitHub API confirmed all three configured `jaystarz1` repositories are public.
Source/assets remain uncommitted in the shared worktrees pending explicit public
publication approval. Live deployment is already running independently of GitHub.

## Quest Browser checklist (to run on hardware)

- [ ] Open invite URL in Meta Quest Browser (deployed HTTPS instance; Quest will not accept the local self-signed certs without fuss)
- [ ] Enter VR button appears and starts an immersive session
- [ ] Teleport locomotion works on the lounge nav mesh
- [ ] Both participants audible; mouth indicator moves on speech
- [ ] Sit on each couch cushion hotspot; stand up again
- [ ] Frame rate acceptable on Quest 2 (use `?stats=true`)
- [ ] Mic-permission denial shows feedback and recovers
- [ ] Second headset/browser joining beyond 2 occupants is rejected gracefully
