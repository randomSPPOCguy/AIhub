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
import { logger } from "./utils/logger.js";

const app = express();
const server = http.createServer(app);

logger.info("=== AIhub Experimental - starting up ===", {
  version: "1.2.0",
  pid: process.pid
});

app.use(express.json());
app.use(cors({ origin: cfg.allowOrigin }));
const requestLogFormat = ":method :url :status :res[content-length] - :response-time ms";
app.use(
  morgan(requestLogFormat, {
    stream: {
      write: (message) => logger.info("[HTTP]", message.trim())
    }
  })
);
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
  logger.info("Hardware ready", {
    cpuModel: cpu?.model || "unknown",
    logicalCores: cpu?.logicalCores ?? "n/a"
  });
  const gpus = hardware.gpu || [];
  if (!gpus.length) {
    logger.info("GPU detected: none");
  } else {
    gpus.forEach((gpu, idx) => {
      const mem =
        typeof gpu.memoryBytes === "number"
          ? `${Math.round((gpu.memoryBytes / 1024 / 1024 / 1024) * 10) / 10} GB`
          : "memory n/a";
      logger.info("GPU detected", {
        index: idx + 1,
        name: gpu.name,
        memory: mem
      });
    });
  }
  logger.info("Command console tip: type '/help' to see available commands");
}

async function reportEnrichmentHealth() {
  if (!cfg.enrich.enabled) {
    logger.warn("Enrichment service disabled via configuration");
    return;
  }
  const healthUrl = `${cfg.enrich.url.replace(/\/$/, "")}/health`;
  const controller = new AbortController();
  const timeoutMs = Math.min(cfg.enrich.timeout, 2000);
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(healthUrl, { signal: controller.signal });
    clearTimeout(timeout);
    if (response.ok) {
      logger.info("Enrichment service: OK", {
        url: healthUrl,
        status: response.status
      });
    } else {
      logger.warn("Enrichment service: FAILED", {
        url: healthUrl,
        status: response.status
      });
    }
  } catch (err) {
    clearTimeout(timeout);
    logger.warn("Enrichment service: FAILED", {
      url: healthUrl,
      error: err?.message || String(err)
    });
  }
}

server.listen(cfg.port, cfg.host, () => {
  logger.info("HTTP server listening", {
    host: cfg.host,
    port: cfg.port,
    baseUrl: cfg.baseUrl
  });
  logger.info("Room WebSocket ready", { url: `${cfg.wsBaseUrl}/ws/room` });

  if (cfg.enrich.enabled) {
    logger.info("Enrichment service configured", {
      url: cfg.enrich.url,
      timeoutMs: cfg.enrich.timeout
    });
  } else {
    logger.warn("Enrichment service disabled");
  }

  logHardwareBanner();
  reportEnrichmentHealth();

  // Check and display active model status
  const activeModel = getActiveModel();
  if (activeModel) {
    logger.info("Active model ready", {
      id: activeModel.id,
      provider: activeModel.provider
    });
  } else {
    logger.warn("No active model selected", {
      guidance: "Run /model inside the console to choose one"
    });
  }

  startCommandConsole();
  logger.info("Command console started");
  if (!listDownloadedLocalArtifacts().length) {
    logger.info("No local model downloads detected yet", {
      action: "Run /model to browse available models"
    });
  }
});
