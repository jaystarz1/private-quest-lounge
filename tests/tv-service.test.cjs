const { test } = require("node:test");
const assert = require("node:assert/strict");
const { Readable } = require("node:stream");
const { TvService, handler } = require("../bin/lib/tv-service.cjs");
function fixture(options = {}) {
  let time = 10000, output = "Speakers", launches = 0;
  const store = { data: { admin: "a".repeat(64), controllers: [], restoreDevice: null }, save() {} };
  const audio = { available: () => true, current: () => output, set: value => { output = value; } };
  const service = new TvService({ store, audio, now: () => time, launch: () => { launches++; }, ...options });
  return { service, store, audio, advance: ms => { time += ms; }, output: () => output, launches: () => launches };
}
test("repeated Start preserves original audio and launches only once", async () => {
  const f = fixture();
  f.service.start(); f.service.start();
  await Promise.resolve();
  assert.equal(f.launches(), 1);
  assert.equal(f.output(), "BlackHole 2ch");
  assert.equal(f.store.data.restoreDevice, "Speakers");
  f.service.stop();
  assert.equal(f.output(), "Speakers");
});
test("Chrome launch is Connecting, not Live; live requires a video heartbeat", () => {
  const f = fixture();
  assert.equal(f.service.start().phase, "connecting");
  f.service.heartbeat(f.service.feeder, { audio: "permission denied" });
  assert.equal(f.service.phase, "connecting");
  f.service.heartbeat(f.service.feeder, { video: { width: 2560, height: 1440, fps: 30 }, audio: true });
  assert.equal(f.service.phase, "live");
  assert.equal(f.service.status().audio, "live");
  f.advance(16000); f.service.tick();
  assert.equal(f.service.phase, "failed");
  assert.equal(f.output(), "Speakers");
});
test("timeout and failed launch restore audio; old feeder is revoked on retry", async () => {
  const f = fixture();
  f.service.start(); const old = f.service.feeder;
  f.advance(91000); f.service.tick();
  assert.equal(f.output(), "Speakers");
  f.service.start();
  assert.deepEqual(f.service.heartbeat(old, {}), { command: "stop" });
  assert.notEqual(f.service.feeder, old);
  const failed = fixture({ launch: async () => { throw new Error("launch failed"); } });
  failed.service.start();
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(failed.service.phase, "failed");
  assert.equal(failed.output(), "Speakers");
});
test("output recovery survives daemon restart; user-selected output is respected", () => {
  const f = fixture(); f.service.start();
  new TvService({ store: f.store, audio: f.audio, launch() {} });
  assert.equal(f.output(), "Speakers");
  f.service.stop(); f.service.start(); f.audio.set("Headphones"); f.service.stop();
  assert.equal(f.output(), "Headphones");
});
test("one-time expiring pairing, hashed controller storage and brute-force limit", () => {
  const f = fixture();
  const { code } = f.service.newPairing();
  const { token } = f.service.pair(code);
  assert.equal(f.service.authorized(token), true);
  assert.equal(JSON.stringify(f.store.data).includes(token), false);
  assert.throws(() => f.service.pair(code), /Invalid/);
  for (let i = 0; i < 3; i++) assert.throws(() => f.service.pair("00000000"));
  assert.throws(() => f.service.pair("00000000"), /Too many/);
  f.advance(90 * 86400000 + 1);
  assert.equal(f.service.authorized(token), false);
  const next = f.service.newPairing(); f.advance(300001);
  assert.throws(() => f.service.pair(next.code), /expired/);
});
test("HTTP rejects old public trigger, GET mutations, cross-origin, and no token", async () => {
  const f = fixture();
  const serve = handler(f.service, "https://lounge.test");
  async function call(url, method = "POST", headers = {}, body = {}) {
    const req = Readable.from([JSON.stringify(body)]);
    Object.assign(req, { url, method, headers });
    const res = { setHeader() {}, writeHead(status) { this.status = status; }, end(data) { this.body = JSON.parse(data); } };
    await serve(req, res); return res;
  }
  assert.equal((await call("/lounge-tv/9c4f/on")).status, 404);
  assert.equal((await call("/lounge-tv/v1/start", "GET")).status, 405);
  assert.equal((await call("/lounge-tv/v1/start")).status, 401);
  assert.equal((await call("/lounge-tv/v1/pair", "POST", { origin: "https://evil.test" })).status, 403);
  assert.equal((await call("/lounge-tv/v1/pair-code")).status, 401);
  assert.equal((await call("/lounge-tv/v1/set-pin", "POST", {}, { pin: "2468" })).status, 401);
  const { token } = f.service.pair(f.service.newPairing().code);
  assert.equal((await call("/lounge-tv/v1/set-pin", "POST", { authorization: `Bearer ${token}` }, { pin: "2468" })).status, 401);
  assert.equal(f.launches(), 0);
});
test("permanent PIN is salted, reusable after restart, replaceable and rate limited", () => {
  const f = fixture();
  assert.throws(() => f.service.setPin("abc"), /4 to 8/);
  f.service.setPin("2468");
  assert.equal(JSON.stringify(f.store.data).includes('"2468"'), false);
  const first = f.service.pair("2468");
  const restarted = new TvService({ store: f.store, audio: f.audio, now: () => 10000 + 91 * 86400000, launch() {} });
  assert.ok(restarted.authorized(restarted.pair("2468").token));
  assert.equal(restarted.authorized(first.token), false);
  restarted.setPin("8642");
  assert.throws(() => restarted.pair("2468"), /Invalid/);
  assert.ok(restarted.authorized(restarted.pair("8642").token));
  for (let i = 0; i < 2; i++) assert.throws(() => restarted.pair("0000"), /Invalid/);
  assert.throws(() => restarted.pair("8642"), /Too many/);
});
