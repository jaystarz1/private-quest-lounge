// Drives lab.html through the arm-IK poses and records renders + metrics.
import { chromium } from "playwright";
import { mkdirSync, writeFileSync } from "fs";
const avatar = process.argv[2] || "avatar-jay-real.glb";
const ik = process.argv[3] || "arm-ik-current.js";
const tag = process.argv[4] || "cur";
const out = `out/${tag}-${avatar.replace("avatar-", "").replace("-real.glb", "")}`;
mkdirSync(out, { recursive: true });
// left-hand poses in avatar root space (Hips origin, +y up, faces +z, +x = avatar's left):
// [pos, fingersDir, palmNormal]; the right hand mirrors x.
const POSES = {
  bind:     null,
  hang:     [[0.24, 0.02, 0.10], [0, -1, 0.15], [-1, 0, 0]],
  lap:      [[0.16, 0.12, 0.28], [0.1, -0.4, 1], [0, -1, 0]],
  forward:  [[0.18, 0.45, 0.50], [0, 0, 1], [-1, 0, 0]],
  raise:    [[0.22, 0.95, 0.10], [0, 1, 0], [-1, 0, 0]],
  cross:    [[-0.10, 0.40, 0.30], [-0.7, 0, 0.7], [0, -1, 0]],
  face:     [[0.10, 0.60, 0.20], [0, 1, 0], [-1, 0, 0]],
  tpose:    [[0.69, 0.50, -0.05], [1, 0, 0], [0, -1, 0]],
  back:     [[0.20, 0.20, -0.22], [0, -1, -0.3], [0, 0, -1]],
  overreach:[[0.20, 0.50, 0.85], [0, 0, 1], [-1, 0, 0]],
  wave:     [[0.45, 0.85, 0.15], [0, 1, 0], [0, 0, 1]],
  palmup:   [[0.18, 0.45, 0.50], [0, 0, 1], [1, 0, 0]],
  palmdown: [[0.18, 0.45, 0.50], [0, 0, 1], [0, -1, 0]],
  untracked: "relax"
};
const mirror = p => p && [[-p[0][0], p[0][1], p[0][2]], [-p[1][0], p[1][1], p[1][2]], [-p[2][0], p[2][1], p[2][2]]];
const browser = await chromium.launch({ headless: true, args: ["--ignore-gpu-blocklist", "--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"] });
const page = await browser.newPage({ viewport: { width: 1260, height: 560 } });
page.on("console", m => { if (m.type() === "error") console.log("PAGE ERROR:", m.text()); });
page.on("pageerror", e => console.log("PAGE EXC:", e.message));
await page.goto(`http://127.0.0.1:8765/lab.html?avatar=${avatar}&ik=${ik}`);
await page.waitForFunction(() => window.__ready === true, null, { timeout: 120000 });
const results = {};
for (const [name, L] of Object.entries(POSES)) {
  let m;
  if (L === "relax") {
    await page.evaluate(() => window.__setTracked(false, false));
    m = await page.evaluate(() => window.__solveN(120));
    await page.evaluate(() => window.__setTracked(true, true));
  } else {
    if (L) await page.evaluate(([l, r]) => window.__setHands(l, r), [L, mirror(L)]);
    m = await page.evaluate(() => window.__solve());
  }
  results[name] = m;
  await page.screenshot({ path: `${out}/${name}.png` });
  const l = m.Left;
  console.log(`${name.padEnd(10)} L: upper ${l.upperLen}/${l.upperBind} clav ${l.clavLen}/${l.clavBind} armHeadShift ${l.armHeadShift} wristGap ${l.wristGap} elbow ${l.elbowAngleDeg}deg elbowPos ${JSON.stringify(l.elbow)} stretch worst ${l.worstStretch} mean ${l.meanStretch}`);
}
// wrist roll sweep at the forward pose: forearm twist continuity. Tracking was
// just re-enabled, so let the blend-in finish before measuring.
{
  const L = [[0.18, 0.45, 0.50], [0, 0, 1], [-1, 0, 0]];
  await page.evaluate(([l, r]) => window.__setHands(l, r), [L, mirror(L)]);
  await page.evaluate(() => window.__solveN(60));
}
const twist = [];
for (let deg = 0; deg <= 360; deg += 30) {
  const a = deg * Math.PI / 180;
  const palm = [-Math.cos(a), -Math.sin(a), 0];
  const L = [[0.18, 0.45, 0.50], [0, 0, 1], palm];
  await page.evaluate(([l, r]) => window.__setHands(l, r), [L, mirror(L)]);
  const t = await page.evaluate(() => { window.__solve(); return window.__twist(); });
  twist.push({ deg, ...t });
  console.log(`twist ${String(deg).padStart(3)}: L f0 ${t.Left.f0} f1 ${t.Left.f1} f2 ${t.Left.f2} hand ${t.Left.hand} | R f0 ${t.Right.f0} f1 ${t.Right.f1} f2 ${t.Right.f2} hand ${t.Right.hand}`);
  if (deg % 90 === 0) await page.screenshot({ path: `${out}/twist${deg}.png` });
}
writeFileSync(`${out}/metrics.json`, JSON.stringify({ results, twist }, null, 1));
await browser.close();
