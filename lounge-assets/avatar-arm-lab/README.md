# avatar-arm-lab

Headless harness for the MetaPerson arm solver (`services/hubs/src/components/avatar-arm-ik.js`).
It loads a personal avatar GLB in plain three.js, runs the production component
against a set of hand poses (hanging, lap, reach, overhead, cross-body, face, T,
behind, out of reach, wave, wrist-roll sweep, untracked), renders front/side/top
views and reports bone lengths, wrist gap, elbow placement and skin edge stretch.

Run (from this folder):

```sh
ln -sfn ../node_modules/three three            # three r170 from lounge-assets
cp ../avatars/avatar-jay-real.glb ../avatars/avatar-her-real.glb .
cp ../../services/hubs/src/components/avatar-arm-ik.js arm-ik-current.js
python3 -m http.server 8765 --bind 127.0.0.1 &
node run.mjs avatar-jay-real.glb arm-ik-current.js cur   # needs playwright resolvable from here
node run.mjs avatar-her-real.glb arm-ik-current.js cur
```

Renders and `metrics.json` land in `out/<tag>-<avatar>/`.
