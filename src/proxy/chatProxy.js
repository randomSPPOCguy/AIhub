import express from "express";
import fetch from "node-fetch";
import { cfg } from "../config.js";
import { logger } from "../utils/logger.js";

const router = express.Router();

// Configure the Python AI Hub URL (adjust if your Python server runs elsewhere)
const PYTHON_AI_BASE = cfg.python.baseUrl.replace(/\/$/, "");

// Proxy POST /api/chat -> Python /api/chat
router.post("/chat", async (req, res) => {
  const started = Date.now();
  try {
    const url = `${PYTHON_AI_BASE}/api/chat`;
    const resp = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req.body)
      // forward client ip or other headers if needed
    });

    const contentType = resp.headers.get("content-type") || "";
    if (contentType.includes("application/json")) {
      const json = await resp.json();
      logger.info("Forwarded chat request to Python AI hub", {
        path: "/api/chat",
        status: resp.status,
        durationMs: Date.now() - started
      });
      return res.status(resp.status).json(json);
    } else {
      const text = await resp.text();
      logger.info("Forwarded chat request to Python AI hub", {
        path: "/api/chat",
        status: resp.status,
        durationMs: Date.now() - started
      });
      res.status(resp.status).send(text);
    }
  } catch (err) {
    logger.error("Chat proxy error", {
      path: "/api/chat",
      error: err?.message || String(err)
    });
    res.status(502).json({ error: "Failed to proxy to Python AI Hub", detail: String(err) });
  }
});

// GET /api/local_models -> Python /api/local_models
router.get("/local_models", async (_req, res) => {
  const started = Date.now();
  try {
    const url = `${PYTHON_AI_BASE}/api/local_models`;
    const resp = await fetch(url);
    const json = await resp.json();
    logger.info("Fetched local models via proxy", {
      path: "/api/local_models",
      status: resp.status,
      durationMs: Date.now() - started
    });
    res.status(resp.status).json(json);
  } catch (err) {
    logger.error("Chat proxy error", {
      path: "/api/local_models",
      error: err?.message || String(err)
    });
    res.status(502).json({ error: "Failed to fetch local models", detail: String(err) });
  }
});

// POST /api/local_chat -> Python /api/local_chat
router.post("/local_chat", async (req, res) => {
  const started = Date.now();
  try {
    const url = `${PYTHON_AI_BASE}/api/local_chat`;
    const resp = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req.body)
    });
    const contentType = resp.headers.get("content-type") || "";
    if (contentType.includes("application/json")) {
      const json = await resp.json();
      logger.info("Forwarded local_chat request to Python AI hub", {
        path: "/api/local_chat",
        status: resp.status,
        durationMs: Date.now() - started
      });
      return res.status(resp.status).json(json);
    } else {
      const text = await resp.text();
      logger.info("Forwarded local_chat request to Python AI hub", {
        path: "/api/local_chat",
        status: resp.status,
        durationMs: Date.now() - started
      });
      res.status(resp.status).send(text);
    }
  } catch (err) {
    logger.error("Chat proxy error", {
      path: "/api/local_chat",
      error: err?.message || String(err)
    });
    res.status(502).json({ error: "Failed to proxy local_chat", detail: String(err) });
  }
});

export default router;
