import dotenv from "dotenv";
import fs from "node:fs";
import path from "node:path";

const envPath = fs.existsSync("config.env") ? "config.env" : fs.existsSync(".env") ? ".env" : null;
if (envPath) {
  dotenv.config({ path: envPath });
} else {
  dotenv.config();
}

const toBool = (value, fallback = false) => {
  if (value === undefined || value === null || value === "") return fallback;
  return ["1", "true", "yes", "on"].includes(String(value).trim().toLowerCase());
};

const parseIntWithFallback = (value, fallback) => {
  const parsed = parseInt(value ?? "", 10);
  return Number.isNaN(parsed) ? fallback : parsed;
};

const port = parseIntWithFallback(process.env.PORT, 7071);
const host = process.env.HOST || "0.0.0.0";
const baseUrl = process.env.AIHUB_BASE_URL || process.env.PUBLIC_BASE_URL || `http://localhost:${port}`;
const inferWs = (url) => {
  if (!url) return `ws://localhost:${port}`;
  if (url.startsWith("https://")) return url.replace("https://", "wss://");
  if (url.startsWith("http://")) return url.replace("http://", "ws://");
  return url;
};
const internalBaseUrl =
  process.env.AIHUB_INTERNAL_BASE_URL || process.env.HUB_INTERNAL_BASE_URL || `http://127.0.0.1:${port}`;
const pythonPort = parseIntWithFallback(process.env.PYTHON_AI_PORT, 8000);

export const cfg = {
  port,
  host,
  baseUrl,
  wsBaseUrl: process.env.AIHUB_WS_BASE_URL || inferWs(baseUrl),
  internalBaseUrl,
  allowOrigin: process.env.ALLOW_ORIGIN || "*",
  logLevel: process.env.LOG_LEVEL || "info",
  dbPath: process.env.DB_PATH || "./db/music.sqlite",
  wikiUA: process.env.WIKI_UA || "AIHubBot/1.0 (contact: you@example.com)",
  discogsToken: process.env.DISCOGS_TOKEN || "",
  mbUA: {
    app: process.env.MB_UA_APP || "AIHubBot",
    version: process.env.MB_UA_VERSION || "1.1",
    contact: process.env.MB_UA_CONTACT || "you@example.com"
  },
  botKeywords: (process.env.BOT_KEYWORDS || "bot,@bot,b0t,bot2,@bot2")
    .split(",")
    .map((s) => s.trim().toLowerCase())
    .filter(Boolean),
  harvestCAA: toBool(process.env.HARVEST_CAA, true),
  caaMaxSize: parseIntWithFallback(process.env.CAA_MAX_SIZE, 500),
  requireHubKey: toBool(process.env.AIHUB_REQUIRE_KEY, true),
  huggingFaceToken: process.env.HUGGINGFACE_TOKEN || "",
  modelDownloadsDir: path.resolve(process.env.MODEL_DOWNLOAD_DIR || "./models/downloads"),
  python: {
    host: process.env.PYTHON_AI_HOST || "0.0.0.0",
    port: pythonPort,
    baseUrl: process.env.PYTHON_AI_BASE || `http://localhost:${pythonPort}`,
    modelRoot: process.env.PYTHON_MODEL_ROOT || "./models/downloads",
    bin: process.env.PYTHON_AI_BIN || "",
    interpreter: process.env.PYTHON || "python"
  },
  behaviorPrompt: {
    inline: process.env.BOT_BEHAVIOR_PROMPT || "",
    file: process.env.BOT_BEHAVIOR_PROMPT_FILE || ""
  },
  providers: {
    openai: {
      apiKey: process.env.OPENAI_API_KEY || "",
      model: process.env.OPENAI_MODEL || process.env.DEFAULT_OPENAI_MODEL || "gpt-4o-mini",
      baseURL: process.env.OPENAI_BASE_URL || "https://api.openai.com/v1"
    },
    anthropic: {
      apiKey: process.env.ANTHROPIC_API_KEY || process.env.CLAUDE_API_KEY || "",
      model: process.env.ANTHROPIC_MODEL || process.env.DEFAULT_CLAUDE_MODEL || "claude-3-sonnet-20240229",
      baseURL: process.env.ANTHROPIC_BASE_URL || "https://api.anthropic.com"
    },
    google: {
      apiKey: process.env.GOOGLE_API_KEY || process.env.GEMINI_API_KEY || "",
      model:
        process.env.GOOGLE_GEMINI_MODEL ||
        process.env.GEMINI_MODEL ||
        process.env.DEFAULT_GEMINI_MODEL ||
        "gemini-1.5-pro",
      baseURL: process.env.GEMINI_BASE_URL || "https://generativelanguage.googleapis.com"
    },
    huggingface: {
      apiKey: process.env.HUGGINGFACE_API_KEY || "",
      model: process.env.HUGGINGFACE_MODEL || "mistralai/Mixtral-8x7B-Instruct-v0.1",
      baseURL: process.env.HUGGINGFACE_BASE_URL || "https://api-inference.huggingface.co"
    },
    local: {
      model: process.env.LOCAL_MODEL_NAME || "phi-3-mini-128k-instruct",
      baseURL: process.env.LOCAL_MODEL_URL || "http://localhost:11434",
      apiKey: process.env.LOCAL_MODEL_API_KEY || "",
      kind: (process.env.LOCAL_MODEL_KIND || "ollama").toLowerCase(),
      openAICompatiblePath: process.env.LOCAL_MODEL_CHAT_PATH || "/v1/chat/completions",
      onnxGenAiPath:
        process.env.LOCAL_MODEL_ONNX_PATH ||
        process.env.LOCAL_MODEL_CHAT_PATH ||
        "/api/chat"
    }
  }
};
