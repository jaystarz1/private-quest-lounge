# Penthouse controls and verification

## In-room interaction

Open **Together** from the left wrist in VR or the desktop button. The menu is
placed in front of you and stays in the room until closed. **Stop pose / Stand
up**, the wrist Stop button, and Escape cancel your current pose.

- **Touch feedback** starts off for every visit. Both people must turn it on.
  Hand proximity to another hand, upper arm, forearm, shoulder or face requests a short,
  capped controller pulse on both participants. It is proximity feedback, not
  collision physics. Hand tracking without a haptic actuator cannot vibrate.
- **Emotes:** wave, clap, dance and sit on the floor. The initial set is authored
  procedural motion, not Mixamo clips. Avatar wrists blend into motion and back
  to tracked poses; controller pointers and the headset remain tracked.
- **Partner:** choose the named person within one metre, then Hug, Hold hands,
  Sit together or Slow dance. They must explicitly accept within 15 seconds.
  Either person can stop. Disconnect, stale presence, moving apart or the
  one-minute pose limit also ends the pose. Invitations cannot be silently
  changed to another pose after consent.
  Face each other for hugs, hand-holding and slow dance; stand side by side,
  facing the same way, before Sit together. Poses do not rotate your viewpoint
  or teleport you into another person's body.
  For a bent-arm embrace, move closer after accepting the hug; a distant partner
  makes it an extended-arm reach. Stay inside your real-world safe play area.
- **Floor sitting:** choosing it explicitly uses the existing seated-waypoint
  relocation mechanism. Stop stands you up at the current valid floor. Leave a
  furniture seat before choosing a floor pose. Clear real-world space first.
- **Faces:** smile, sad, surprise, wink and neutral. These are selected
  expressions, not eye/face tracking. Speech keeps control of `jawOpen`.

The personal avatars now retain legs. Posture estimates use the actual navmesh
on each storey and fixed bone lengths. There is no claim of measured leg/body
tracking. Very tall headset heights can exceed a model's natural reach; the
solver exposes `avatar-leg-ik.debug.maxReachError` rather than stretching the
legs or pulling the headset down. See [leg implementation](../lounge-assets/avatar-leg-ik.md).

## Mac screen TV

The counter monitor remains removed. The wall TV is the one shared display.

1. Use the permanent TV PIN configured on the Mac. It is stored as a salted
   hash in ignored local configuration, never in the client or repository.
   Alternatively, run `node bin/tv-control pair` for a temporary eight-digit code.
2. Press **Pair TV** beneath the wall TV, enter the PIN and press **OK**.
   The PIN does not expire; each browser remembers pairing for 90 days.
   Temporary codes remain single-use with a five-minute expiry. Both methods
   share a limit of five attempts per minute.
3. Press **Start**. On the Mac, approve Chrome screen-recording and audio-input
   permissions if requested. The dedicated feeder Chrome profile selects
   `Screen 1` by default; set `LOUNGE_TV_DISPLAY` when starting the daemon to
   select another display label.
4. Read both status lines: **Live** requires an actual published video track.
   Pixel dimensions and frame rate are reported from capture, and audio status
   is separate. A launched browser is not considered a working screen feed.
5. **Stop** ends video and audio capture and restores the prior Mac output.
   **Retry** revokes the previous feeder and starts a fresh attempt.

BlackHole 2ch must exist as an input and output device. The feeder suppresses
room playback to prevent loopback echo and never substitutes the Mac's normal
microphone when BlackHole is unavailable. Video permission and audio permission
are independent, so a delayed microphone prompt does not block the screen.

For text clarity, use a 16:9 display or window, normal browser zoom and text
large enough to read on the virtual 2.55 m panel. The capture path requests
2560 x 1440 at 30 fps and publishes the actual dimensions supplied by Chrome.
The synthetic end-to-end test verified upright 1920 x 1080 at 30 fps, complete
frame edges, received video frames, independent audio and stopped capture.
It did not record the operator's Mac desktop or prove Quest optical clarity.

Local commands: `bin/tv start`, `bin/tv stop`, `bin/tv retry`,
`node bin/tv-control status`. The local admin capability and paired token hashes
live in private `.lounge-tv/`; never commit or share that directory. The old
unauthenticated trigger returns 404 and unpaired commands return 401.

## Central Park and time of day

Daytime is the orientation reference. Dusk and night north views are
lighting-only generated derivatives of that same photograph, not a mirrored
photograph taken from another direction. All three use the same crop, 0.46
horizon anchor and panorama placement. Generation prompts and source paths are
recorded beside the [aligned assets](../lounge-assets/views-src/aligned/README.md).

The selected day/dusk/night state is saved in the room database. New arrivals,
reloads and reconnects request the current revision. Concurrent changes are
serialized by the database; clients ignore older revisions.

Read-only asset registration gate:

```sh
python3 lounge-assets/verify-view-registration.py
```

Current feature matches cover most of the source image width: day to dusk
median landmark offset 0.94 px; dusk to night 1.82 px at 1933-pixel analysis width.
This tests geometric registration, not identical illumination or pixel content.

Regenerate the full panorama outputs after an asset change:

```sh
python3 lounge-assets/make-pano.py lounge-assets/views-src services/hubs/src/assets/images/lounge-views lounge-assets/bake
python3 lounge-assets/make-sky.py lounge-assets/views-src services/hubs/src/assets/images/lounge-views lounge-assets/bake
```

## Network and releases

Cloudflare Tunnel carries pages and signaling, not TURN media. Coturn now runs
locally with time-limited Reticulum credentials and a restricted peer allowlist.
The LAN forced-relay test established a real WebRTC connection. Internet relay
is still pending router forwarding; UPnP discovery found no usable gateway.

Forward to the Mac's reserved LAN address, currently `10.0.0.29`:

| Purpose | Ports |
|---|---|
| Direct voice/video | TCP and UDP 40000-40031 |
| TURN allocation | TCP and UDP 3478 |
| TURN relay | UDP 40032-40063 |

After forwarding, test from another network with `?force_turn=1`, then
`?force_turn=1&force_tcp=1`. Require a connected transport and growing received
media counters. A reachable web page alone does not verify media connectivity.

`bin/up-public` builds into a new client release directory, validates its HTML
and referenced assets, then atomically publishes a pointer. A failed build
leaves the live release untouched. Old hashed assets remain available to open
tabs. Old release directories are deliberately not deleted automatically.

To roll back the client, run the validated `publish` helper from `services/hubs`
with a known retained release path:

```sh
node -e "require('./scripts/public-release').publish(process.cwd(), '.public-releases/RETAINED_RELEASE_ID')"
```

Client rollback does not undo database state, server code, source files or
router configuration. Never reset the shared working tree to perform a rollback.

## Hardware acceptance gate

- Two Quests: touch disabled, one enabled, both enabled; slow approach, sustained
  contact, release, both hands, controller tracking loss and peer disconnect.
- Every emote and paired pose: acceptance/decline, immediate Stop, menu close,
  cancellation while request is in flight, and return to tracked hands.
- Legs at standing, crouched, furniture, floor and upstairs heights; no floor
  penetration or abrupt knee flip. Inspect both avatars and the mirror.
- Speech while smiling/winking; voice jaw keeps moving and expressions return
  to neutral. No false claim of tracked eyes/face.
- Screen test chart and actual desktop: all four corners, small text, video,
  system audio, permission denial, capture stopped at the Mac, Retry, reconnect.
- Identical north-window camera location in day/dusk/night, including a late
  arrival and reload after the view changes.
- Frame-time soak with both full-body avatars, mirror and TV active. Browser
  simulation is not a substitute for headset comfort/performance acceptance.

### Standing while using the Quest seated

After entering VR, remain in your usual comfortable posture for about a second. The room calibrates that headset height to a 1.6 m standing eye line when needed, moving hands and head together. Subsequent leaning/crouching is preserved, and selecting a furniture or floor seat still uses its seated height. Teleporting retains calibration. Exit and re-enter VR to recalibrate if you change your physical seating position. Touch feedback still requires both people to enable it and actual tracked controllers.
