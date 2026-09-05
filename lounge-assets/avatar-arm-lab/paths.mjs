// Continuity test: drag the hands along smooth paths in small steps and measure
// the per-step elbow displacement relative to the hand displacement (gain);
// then toggle tracking to measure the hand/elbow snap.
import { chromium } from "playwright";
import { writeFileSync } from "fs";
const avatar = process.argv[2] || "avatar-jay-real.glb";
const ik = process.argv[3] || "arm-ik-current.js";
const tag = process.argv[4] || "cur";
const lerp = (a, b, t) => a.map((v, i) => v + (b[i] - v) * t);
const mirror = p => [[-p[0][0], p[0][1], p[0][2]], [-p[1][0], p[1][1], p[1][2]], [-p[2][0], p[2][1], p[2][2]]];
// [pos, fingers, palm] keyframes, left hand, avatar root space (+x = avatar's left, +z = forward)
const PATHS = {
  // arm swing: hand from in front of the hip to behind the hip (walking)
  swing:   [[[0.22, 0.05, 0.35], [0, -0.5, 1], [-1, 0, 0]], [[0.22, 0.02, 0.05], [0, -1, 0.15], [-1, 0, 0]], [[0.20, 0.12, -0.30], [0, -0.7, -0.7], [-1, 0, 0]]],
  // hip to overhead through the side
  sideRaise: [[[0.24, 0.02, 0.10], [0, -1, 0.15], [-1, 0, 0]], [[0.62, 0.50, 0.05], [1, 0, 0], [0, -1, 0]], [[0.22, 0.98, 0.05], [0, 1, 0], [-1, 0, 0]]],
  // lap to a forward reach to the far side (cross body)
  crossReach: [[[0.16, 0.12, 0.28], [0.1, -0.4, 1], [0, -1, 0]], [[0.10, 0.40, 0.55], [0, 0, 1], [-1, 0, 0]], [[-0.25, 0.40, 0.35], [-0.7, 0, 0.7], [0, -1, 0]]],
  // hand circling close to the shoulder (adjusting the headset / scratching)
  nearShoulder: Array.from({ length: 9 }, (_, i) => { const a = i / 8 * Math.PI * 2; return [[0.20 + 0.12 * Math.cos(a), 0.45 + 0.12 * Math.sin(a), 0.22], [0, 1, 0.3], [-1, 0, 0]]; }),
  // arms hanging while the chest turns is emulated by the hand sweeping behind and around low
  // reaching behind the back: hip side -> small of the back -> behind the shoulder
  behindBack: [[[0.24, 0.02, 0.10], [0, -1, 0.15], [-1, 0, 0]], [[0.05, 0.15, -0.25], [-1, 0, 0], [0, 0, -1]], [[0.15, 0.45, -0.35], [0, 1, -0.5], [0, 0, -1]]],
  // hand travelling from the shoulder straight down the default elbow-hint direction (out, down, back)
  poleLine: Array.from({ length: 7 }, (_, i) => { const t = 0.15 + i / 6 * 0.45; const d = [0.32, -0.70, -0.64]; return [[0.16 + d[0] * t, 0.50 + d[1] * t, 0.02 + d[2] * t], [0, -1, -0.3], [-1, 0, 0]]; }),
  lowArc: Array.from({ length: 7 }, (_, i) => { const a = -0.5 + i / 6 * 2.0; return [[0.24 + 0.15 * Math.sin(a), 0.03, 0.15 * Math.cos(a) - 0.05], [0, -1, 0.15], [-1, 0, 0]]; }),
};
const STEPS = 12;
const browser = await chromium.launch({ headless: true, args: ["--ignore-gpu-blocklist", "--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"] });
const page = await browser.newPage({ viewport: { width: 1260, height: 560 } });
page.on("pageerror", e => console.log("PAGE EXC:", e.message));
await page.goto(`http://127.0.0.1:8765/lab.html?avatar=${avatar}&ik=${ik}`);
await page.waitForFunction(() => window.__ready === true, null, { timeout: 120000 });
const dist = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]);
const report = {};
for (const [name, keys] of Object.entries(PATHS)) {
  const frames = [];
  for (let k = 0; k < keys.length - 1; k++) for (let s = 0; s < STEPS; s++) {
    const t = s / STEPS;
    frames.push([lerp(keys[k][0], keys[k + 1][0], t), lerp(keys[k][1], keys[k + 1][1], t), lerp(keys[k][2], keys[k + 1][2], t)]);
  }
  frames.push(keys[keys.length - 1]);
  let prev = null, worst = { gain: 0 }, sumGain = 0, n = 0, worstElbowStep = 0, flips = 0;
  // hands do not teleport between paths: settle the solver at the path's first pose
  await page.evaluate(([l, r]) => window.__setHands(l, r), [frames[0], mirror(frames[0])]);
  await page.evaluate(() => window.__solveN(10));
  for (const L of frames) {
    await page.evaluate(([l, r]) => window.__setHands(l, r), [L, mirror(L)]);
    const m = await page.evaluate(() => { window.__armDt = 16; const r = window.__solveDt ? window.__solveDt(16) : (window.__comp ? null : null); return r || window.__solve(); });
    for (const side of ["Left", "Right"]) {
      if (prev) {
        const dh = dist(m[side].hand, prev[side].hand), de = dist(m[side].elbow, prev[side].elbow);
        const gain = de / Math.max(dh, 0.005);
        sumGain += gain; n++;
        worstElbowStep = Math.max(worstElbowStep, de);
        if (gain > worst.gain) worst = { gain: +gain.toFixed(2), side, de: +de.toFixed(3), dh: +dh.toFixed(3), hand: m[side].hand };
        if (de > 0.08) flips++;
      }
    }
    prev = m;
  }
  report[name] = { worstGain: worst, meanGain: +(sumGain / n).toFixed(2), worstElbowStep: +worstElbowStep.toFixed(3), bigJumps: flips };
  console.log(`${name.padEnd(13)} worst elbow step ${worstElbowStep.toFixed(3)} m  big jumps(>8cm) ${flips}  mean gain ${(sumGain / n).toFixed(2)}  worst ${JSON.stringify(worst)}`);
}
// tracking toggle at the hang pose: hand/elbow displacement per frame across a loss and a recovery
const L = [[0.24, 0.02, 0.10], [0, -1, 0.15], [-1, 0, 0]];
await page.evaluate(([l, r]) => window.__setHands(l, r), [L, mirror(L)]);
let m = await page.evaluate(() => window.__solve());
const seq = [];
let last = m;
const step = async (label) => { m = await page.evaluate(() => { window.__comp.tock(0, 16); window.__root.updateWorldMatrix(true, true); return window.__metrics(); }); const dh = dist(m.Left.hand, last.Left.hand), de = dist(m.Left.elbow, last.Left.elbow); seq.push({ label, dh: +dh.toFixed(3), de: +de.toFixed(3) }); last = m; };
await page.evaluate(() => window.__setTracked(false, false));
for (let i = 0; i < 6; i++) await step(`lost${i}`);
for (let i = 0; i < 40; i++) await page.evaluate(() => { window.__comp.tock(0, 16); });
last = await page.evaluate(() => { window.__root.updateWorldMatrix(true, true); return window.__metrics(); });
await page.evaluate(() => window.__setTracked(true, true));
// ik-controller writes the tracked hand pose every frame; emulate that before each solve
for (let i = 0; i < 6; i++) { await page.evaluate(([l, r]) => window.__setHands(l, r), [L, mirror(L)]); await step(`back${i}`); }
console.log("toggle@hang (left hand step / elbow step per frame):", seq.map(s => `${s.label}: h${s.dh} e${s.de}`).join("  "));
report.toggle = seq;
{
  const R = [[0.22, 0.95, 0.10], [0, 1, 0], [-1, 0, 0]];
  await page.evaluate(([l, r]) => window.__setHands(l, r), [R, mirror(R)]);
  last = await page.evaluate(() => window.__solve());
  const seq2 = [];
  const step2 = async (label) => { m = await page.evaluate(() => { window.__comp.tock(0, 16); window.__root.updateWorldMatrix(true, true); return window.__metrics(); }); const dh = dist(m.Left.hand, last.Left.hand), de = dist(m.Left.elbow, last.Left.elbow); seq2.push({ label, dh: +dh.toFixed(3), de: +de.toFixed(3) }); last = m; };
  await page.evaluate(() => window.__setTracked(false, false));
  for (let i = 0; i < 8; i++) await step2(`lost${i}`);
  for (let i = 0; i < 60; i++) await page.evaluate(() => { window.__comp.tock(0, 16); });
  last = await page.evaluate(() => { window.__root.updateWorldMatrix(true, true); return window.__metrics(); });
  await page.evaluate(() => window.__setTracked(true, true));
  for (let i = 0; i < 8; i++) { await page.evaluate(([l, r]) => window.__setHands(l, r), [R, mirror(R)]); await step2(`back${i}`); }
  console.log("toggle@raise:", seq2.map(s => `${s.label}: h${s.dh} e${s.de}`).join("  "));
  report.toggleRaise = seq2;
}
writeFileSync(`out/paths-${tag}-${avatar.replace("avatar-", "").replace("-real.glb", "")}.json`, JSON.stringify(report, null, 1));
await browser.close();
