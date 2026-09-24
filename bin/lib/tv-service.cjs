const crypto = require("crypto");
const fs = require("fs");
const path = require("path");
const digest = value => crypto.createHash("sha256").update(value).digest("hex");
const secret = () => crypto.randomBytes(32).toString("hex");

function openStore(directory) {
  fs.mkdirSync(directory, { recursive: true, mode: 0o700 });
  const filename = path.join(directory, "control.json");
  let data;
  try { data = JSON.parse(fs.readFileSync(filename, "utf8")); }
  catch (error) {
    if (error.code !== "ENOENT") throw error;
    data = { admin: secret(), controllers: [], restoreDevice: null };
  }
  const save = () => {
    fs.writeFileSync(filename + ".tmp", JSON.stringify(data), { mode: 0o600 });
    fs.renameSync(filename + ".tmp", filename);
  };
  save();
  return { data, save };
}

class TvService {
  constructor({ store, audio, launch, now = Date.now, source = "Screen 1" }) {
    Object.assign(this, { store, audio, launch, now, source });
    this.phase = "idle";
    this.video = null;
    this.audioState = "off";
    this.error = "";
    this.feeder = null;
    this.pairing = null;
    this.attempts = [];
    this.restoreAudio(); // Recover output after a daemon crash.
  }
  status() {
    return { phase: this.phase, source: this.source, video: this.video, audio: this.audioState,
      error: this.error, updatedAt: this.lastSeen || 0 };
  }
  authorized(token, admin = false) {
    if (typeof token !== "string" || token.length !== 64) return false;
    if (digest(token) === digest(this.store.data.admin)) return true;
    if (admin) return false;
    return this.store.data.controllers.some(c => c.hash === digest(token) && c.expires > this.now());
  }
  newPairing() {
    const code = String(crypto.randomInt(10000000, 100000000));
    this.pairing = { hash: digest(code), expires: this.now() + 300000 };
    return { code, expiresInSeconds: 300 };
  }
  setPin(pin) {
    if (typeof pin !== "string" || !/^\d{4,8}$/.test(pin)) throw Object.assign(new Error("PIN must contain 4 to 8 digits"), { status: 400 });
    const salt = crypto.randomBytes(16).toString("hex");
    this.store.data.pin = { salt, hash: crypto.scryptSync(pin, salt, 32).toString("hex") };
    this.store.save();
    return { configured: true };
  }
  pair(code) {
    this.attempts = this.attempts.filter(time => time > this.now() - 60000);
    if (this.attempts.length >= 5) throw Object.assign(new Error("Too many pairing attempts. Wait one minute."), { status: 429 });
    this.attempts.push(this.now());
    const pin = this.store.data.pin;
    const pinMatches = pin && typeof code === "string" && /^\d{4,8}$/.test(code) &&
      crypto.timingSafeEqual(crypto.scryptSync(code, pin.salt, 32), Buffer.from(pin.hash, "hex"));
    if (!pinMatches && (!this.pairing || this.pairing.expires <= this.now() || digest(String(code)) !== this.pairing.hash)) {
      throw Object.assign(new Error("Invalid or expired pairing code"), { status: 401 });
    }
    this.pairing = null;
    const token = secret();
    this.store.data.controllers = this.store.data.controllers.filter(c => c.expires > this.now()).slice(-19);
    this.store.data.controllers.push({ hash: digest(token), expires: this.now() + 90 * 86400000 });
    this.store.save();
    return { token };
  }
  routeAudio() {
    try {
      if (!this.audio.available()) { this.audioState = "BlackHole missing"; return; }
      const current = this.audio.current();
      // Save before switching. Repeated Start must not erase the original.
      if (!this.store.data.restoreDevice && current !== "BlackHole 2ch") {
        this.store.data.restoreDevice = current;
        this.store.save();
      }
      this.audio.set("BlackHole 2ch");
      this.audioState = "connecting";
    } catch { this.audioState = "Mac audio routing failed"; }
  }
  restoreAudio() {
    const original = this.store.data.restoreDevice;
    if (!original) return;
    try {
      // Respect a device the operator deliberately selected during sharing.
      if (this.audio.current() === "BlackHole 2ch") this.audio.set(original);
      this.store.data.restoreDevice = null;
      this.store.save();
    } catch {
      this.error = `Restore Mac audio to ${original}; automatic restore failed`;
      this.phase = "failed";
    }
  }
  start() {
    if (this.phase === "connecting" || this.phase === "live") return this.status();
    this.error = "";
    this.phase = "connecting";
    this.video = null;
    this.started = this.now();
    this.lastSeen = 0;
    this.feeder = secret();
    const generation = this.feeder;
    this.routeAudio();
    Promise.resolve().then(() => this.launch(generation, this.source)).catch(() => {
      if (this.feeder === generation) this.stop("Chrome could not start. Retry from the TV controls.");
    });
    return this.status();
  }
  stop(error = "") {
    this.feeder = null; // Revocation stops both tracks on the old feeder's next poll.
    this.phase = error ? "failed" : "idle";
    this.video = null;
    this.audioState = "off";
    this.error = error;
    this.restoreAudio();
    return this.status();
  }
  heartbeat(token, report) {
    if (!this.feeder || token !== this.feeder) return { command: "stop" };
    this.lastSeen = this.now();
    if (report.error) {
      this.stop(String(report.error).slice(0, 180));
      return { command: "stop" };
    }
    if (report.video && Number.isFinite(report.video.width) && report.video.width > 0 &&
        Number.isFinite(report.video.height) && report.video.height > 0) {
      this.video = { width: report.video.width, height: report.video.height,
        fps: Math.round(Number(report.video.fps) || 0), display: String(report.video.display || "display").slice(0, 80) };
      this.phase = "live";
    }
    this.audioState = report.audio === true ? "live" : String(report.audio || this.audioState).slice(0, 120);
    return { command: "continue" };
  }
  tick() {
    if (!this.feeder) return;
    if (this.phase === "connecting" && this.now() - this.started > 90000) this.stop("Screen capture timed out. Check Chrome's screen-recording permission on the Mac.");
    else if (this.phase === "live" && this.now() - this.lastSeen > 15000) this.stop("Screen feeder disconnected. Mac audio has been restored.");
  }
}

function handler(service, origin) {
  return async (req, res) => {
    const send = (status, body) => {
      res.writeHead(status, { "Content-Type": "application/json", "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff" });
      res.end(JSON.stringify(body));
    };
    try {
      if (req.headers.origin && req.headers.origin !== origin) return send(403, { error: "Wrong origin" });
      const route = new URL(req.url, origin).pathname;
      const token = (req.headers.authorization || "").replace(/^Bearer /, "");
      if (!route.startsWith("/lounge-tv/v1/")) return send(404, { error: "Not found" });
      const action = route.slice("/lounge-tv/v1/".length);
      if (req.method !== (action === "status" ? "GET" : "POST")) {
        res.setHeader("Allow", action === "status" ? "GET" : "POST");
        return send(405, { error: "Method not allowed" });
      }
      if (!["pair", "heartbeat"].includes(action) && !service.authorized(token, ["pair-code", "set-pin"].includes(action))) {
        return send(401, { error: "Pair this browser with the Mac first" });
      }
      let raw = "";
      for await (const chunk of req) {
        raw += chunk;
        if (raw.length > 4096) return send(413, { error: "Request too large" });
      }
      let body;
      try { body = raw ? JSON.parse(raw) : {}; }
      catch { return send(400, { error: "Invalid JSON" }); }
      if (!body || typeof body !== "object" || Array.isArray(body)) return send(400, { error: "Invalid body" });
      switch (action) {
        case "pair-code": return send(200, service.newPairing());
        case "set-pin": return send(200, service.setPin(body.pin));
        case "pair": return send(200, service.pair(body.code));
        case "status": return send(200, service.status());
        case "start": return send(200, service.start());
        case "stop": return send(200, service.stop());
        case "retry": service.stop(); return send(200, service.start());
        case "heartbeat": return send(200, service.heartbeat(token, body));
        default: return send(404, { error: "Not found" });
      }
    } catch (error) { send(error.status || 500, { error: error.status ? error.message : "TV service failed" }); }
  };
}
module.exports = { TvService, handler, openStore };
