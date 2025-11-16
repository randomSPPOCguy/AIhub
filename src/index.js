import express from "express";
import http from "http";
import cors from "cors";
import morgan from "morgan";
import { cfg } from "./config.js";
import ingestRouter from "./ingest/router.js";
import factsRouter from "./api/factsRouter.js";
import "./db/connection.js"; // open DB
import enrichRouter from "./routes/enrich.js";
import enrichArtistFull from "./routes/enrich.artistFull.js";
import enrichTrack from "./routes/enrich.track.js";
import enrichArtistLine from "./routes/enrich.artistLine.js";
import enrichArtistWiki from "./routes/enrich.artistWiki.js";
import { setupRoomWebSocket } from "./routes/roomWebSocket.js";
import modelProxy from "./proxy/modelProxy.js";
import { requireHubApiKey } from "./middleware/requireApiKey.js";
import modelsRouter from "./routes/modelsRouter.js";
import chatRouter from "./routes/chatRouter.js";
import chatProxy from "./proxy/chatProxy.js";
import { getHardwareSnapshot } from "./utils/hardwareInfo.js";
import { startCommandConsole } from "./cli/commandConsole.js";
import { listDownloadedLocalArtifacts, getActiveModel } from "./services/modelRegistry.js";

const app = express();
const server = http.createServer(app);

app.use(express.json());
app.use(cors({ origin: cfg.allowOrigin }));
app.use(morgan("dev"));
app.use("/api/enrich", enrichRouter);
app.use("/api/enrich", enrichArtistFull);
app.use("/api/enrich", enrichTrack);
app.use("/api/enrich", enrichArtistLine);
app.use("/api/enrich", enrichArtistWiki);

app.get("/", (_req, res) => res.json({ ok: true, name: "ai-hub", version: "1.2.0" }));

app.use("/ingest", ingestRouter);
app.use("/api", factsRouter);
// Proxy /api/chat to Python AI Hub (if running)
app.use("/api", chatProxy);
// Models catalog/download and secure runtime access
app.use("/api", modelProxy);
app.use("/models", requireHubApiKey, modelsRouter);
app.use("/hub", requireHubApiKey, chatRouter);

// health
app.get("/healthz", (_req, res) => res.send("ok"));
app.get("/health", (_req, res) => res.send("ok"));
app.get("/api/health", (_req, res) => res.json({ status: "ok", version: "1.1.0" }));

// Setup WebSocket for room events from hang-bot
setupRoomWebSocket(server);

function logHardwareBanner() {
  const hardware = getHardwareSnapshot();
  const cpu = hardware.cpu;
  console.log(
    `[SYS] CPU detected: ${cpu?.model || "Unknown"} | logical cores: ${
      cpu?.logicalCores ?? "n/a"
    }`
  );
  const gpus = hardware.gpu || [];
  if (!gpus.length) {
    console.log("[SYS] GPU detected: none");
  } else {
    gpus.forEach((gpu, idx) => {
      const mem =
        typeof gpu.memoryBytes === "number"
          ? `${Math.round((gpu.memoryBytes / 1024 / 1024 / 1024) * 10) / 10} GB`
          : "memory n/a";
      console.log(`[SYS] GPU ${idx + 1}: ${gpu.name} (${mem})`);
    });
  }
  console.log("[SYS] Type '/help' to see the built-in command console options.");
}

server.listen(cfg.port, cfg.host, () => {
  console.log(`[INF] AI Hub 1.2 listening on ${cfg.baseUrl}`);
  console.log(`[INF] Room WebSocket ready at ${cfg.wsBaseUrl}/ws/room`);
  logHardwareBanner();

  // Check and display active model status
  const activeModel = getActiveModel();
  if (activeModel) {
    console.log(`[SYS] ✓ Active model: ${activeModel.id} (${activeModel.provider})`);
  } else {
    console.log(`[SYS] ⚠️  No active model selected!`);
    console.log(`[SYS] → Run '/model' to see available models and select one`);
  }

  startCommandConsole();
  if (!listDownloadedLocalArtifacts().length) {
    console.log(
      "[INF] No local model downloads detected yet. Run '/model' to browse available models."
    );
  }
});
