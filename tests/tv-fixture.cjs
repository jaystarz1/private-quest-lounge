// Local end-to-end fixture. No desktop launch, audio-device access, or disk state.
// Browser tests route only their own /lounge-tv requests here and provide a
// synthetic display/audio stream. Never expose this fixture through the tunnel.
const http = require("node:http");
const { TvService, handler } = require("../bin/lib/tv-service.cjs");
let output = "Test speakers";
let launchToken = null;
const service = new TvService({
  store: { data: { admin: "f".repeat(64), controllers: [], restoreDevice: null }, save() {} },
  audio: { available: () => true, current: () => output, set: name => { output = name; } },
  launch: token => { launchToken = token; },
  source: "Synthetic test chart"
});
const { code } = service.newPairing();
const api = handler(service, "https://lounge.thechatbotgenius.com");
const server = http.createServer((req, res) => {
  if (req.url === "/fixture") {
    res.writeHead(200, { "Content-Type": "application/json", "Cache-Control": "no-store" });
    res.end(JSON.stringify({ code, launchToken, output, status: service.status() }));
  } else api(req, res);
});
server.listen(9919, "127.0.0.1", () => console.log("Synthetic TV test fixture at http://127.0.0.1:9919. No Mac capture."));
const tick = setInterval(() => service.tick(), 1000);
process.once("SIGTERM", () => { clearInterval(tick); service.stop(); server.close(); });
