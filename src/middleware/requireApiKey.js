import { cfg } from "../config.js";
import { validateApiKey } from "../services/apiKeys.js";

function extractKey(req) {
  const header = req.headers["x-aihub-key"] || req.headers["x-api-key"];
  if (header) return header.trim();
  const auth = req.headers.authorization || "";
  if (auth.toLowerCase().startsWith("bearer ")) {
    return auth.slice(7).trim();
  }
  return null;
}

export function requireHubApiKey(req, res, next) {
  if (!cfg.requireHubKey) return next();
  const key = extractKey(req);
  const record = validateApiKey(key);
  if (!record) {
    return res.status(401).json({ error: "API key required", detail: "Provide a valid X-AIHub-Key header." });
  }
  req.apiKey = record;
  next();
}
