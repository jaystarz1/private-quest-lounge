# Personal avatar lower-body posture

The two MetaPerson converters now preserve the original legs and footwear.
They still fold the extra spine/neck bones, reparent tracked hands to Spine,
collapse finger weights, recenter every facial shape key, cap images at 512
pixels, and tag jawOpen for voice-driven mouth movement. The exported rig has
29 joints, including all ten leg/toe joints, and 51 facial targets. There are
no animation clips embedded in these files.

The real application assets are in
`services/hubs/src/assets/models/lounge-avatars/`. The older
`lounge-assets/avatars/` copies and the copied files in `avatar-arm-lab/` are not
the production assets and must not be used as the full-body acceptance source.

## Regeneration

From the project root, for each of `jay` and `her`:

```sh
/Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup \
  -P lounge-assets/metaperson-jay/hubsify.py -- \
  lounge-assets/metaperson-jay/avatar/model.glb \
  lounge-assets/metaperson-jay/avatar-jay-real.glb
cp lounge-assets/metaperson-jay/avatar-jay-real.glb \
  services/hubs/src/assets/models/lounge-avatars/avatar-jay-real.glb
```

The same command with `her` substituted generates the second avatar. Blender
must have permission to run outside the graphics sandbox. The converters fail
if required leg joints or voice morph targets are missing.

## Runtime contract

Import `src/components/avatar-leg-ik.js` and attach `avatar-leg-ik` beside
`ik-controller avatar-arm-ik` on both the local and remote avatar entities.
The solver runs after stock IK and only rotates the thighs, shins and feet.
It never translates/scales bones, moves the avatar root, changes the head or
tracked hands, or relocates the camera.

`scene.systems["lounge-social"]?.poseFor(avatarEntity)` supplies an optional
pose with `name` and elapsed-seconds `phase`. `sit` and `sit_together` select
floor posture only when hips are actually within 0.5 m of the navigation floor.
The caller is responsible for an explicitly requested, comfort-safe relocation
through the existing character controller if a standing user chooses floor sit.
`dance` adds alternating 3 cm foot lifts and 2.5 cm forward steps without root
motion. Missing social state leaves ordinary standing/crouching posture active.

Hip height estimates choose standing, crouching or furniture seating. Forward
foot movement across seated transitions is bounded at 1 m/s in model space.
Segment lengths never stretch. Foot-to-sole clearance is derived once from
the actual footwear skin weights and bind geometry, not a shared fixed offset.

A private mesh proxy shares the navmesh geometry and samples down from the
hips at most ten times per second per avatar. The 1.45 m ray cannot latch onto
the next storey. Teleports invalidate the previous floor immediately. Source
visibility, source raycast handlers and source geometry ownership are unchanged.
The proxy uses Hubs' explicit dirty-matrix update contract. Missing or unreachable
floors are reported through the component's `debug` object rather than hidden
by stretching or moving the head.

The old standing camera lift was 0.5 m. It is now zero; the existing 0.15 m
seated comfort lift and the ease-out/ease-in logic remain unchanged. At Hubs'
default 1.6 m POV, neither personal avatar floats: stock IK leaves hips at
0.877117 m for Jay and 0.927434 m for Her, both within natural leg reach.
Real headset heights above the model's reach still require avatar-height
calibration. This is estimated posture, not tracked legs, collision physics,
foot locking while walking, or a stair-stepping animation system.

## Checks

From the running client container:

```sh
node --test scripts/avatar-leg-ik.test.js
./node_modules/.bin/eslint src/components/avatar-leg-ik.js \
  scripts/avatar-leg-ik.test.js src/systems/character-controller-system.js
```

The tests load the actual client GLBs using the installed patched Three.js
r141 runtime. They retain geometry, joints, morphs and bind matrices, skipping
only image/material decoding. They verify both avatars at three uniform scales,
standing/default POV, crouching, furniture seating, solo/paired floor sitting,
and alternating dance steps. Assertions cover unchanged head/wrists/hips,
natural segment lengths, grounded soles, transformed and stacked floors,
unreachable-floor reporting, stale-floor invalidation, sample rate, dirty-matrix
caching, seated-transition continuity, and source geometry ownership.

After integration, inspect the actual runtime render in front/side views and
on both Quest headsets. Check knees, footwear and clothing at each pose, the
mezzanine transition, mirror visibility, controller tracking, eye height, and
frame time with both personal avatars visible. Automated bone checks do not
replace these render and hardware checks.

## Measured asset cost

| Avatar | Previous triangles | Full-body triangles | Previous bytes | Full-body bytes |
| --- | ---: | ---: | ---: | ---: |
| Jay | 49,216 | 73,690 | 8,129,148 | 8,812,704 |
| Her | 103,366 | 128,791 | 11,984,852 | 12,869,916 |

Together the restored lower bodies add 49,899 triangles and 1,568,620 compressed
bytes. Texture caps are unchanged. The rig adds ten skinning joints per avatar;
the solver adds two analytic two-segment solves per rendered frame and one
short navigation-floor query per sample. Actual Quest frame-time impact has
not been measured by the geometry test.
