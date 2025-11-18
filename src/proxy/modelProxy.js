import express from 'express';
import fs from 'fs';
import path from 'path';
import fetch from 'node-fetch';
import { cfg } from '../config.js';
import { readModelCatalog } from '../services/modelCatalog.js';
import { validateApiKey } from '../services/apiKeys.js';
import { logger } from '../utils/logger.js';

const router = express.Router();
const modelsDir = cfg.modelDownloadsDir;
const PYTHON_AI_BASE = cfg.python.baseUrl.replace(/\/$/, '');
if (!fs.existsSync(modelsDir)) fs.mkdirSync(modelsDir, { recursive: true });

function slugify(value) {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

function extractKey(req) {
  const header = req.headers["x-aihub-key"] || req.headers["x-api-key"];
  if (header) return header.trim();
  const auth = req.headers.authorization || "";
  if (auth.toLowerCase().startsWith("bearer ")) {
    return auth.slice(7).trim();
  }
  return null;
}

function checkApiKey(req, res) {
  if (!cfg.requireHubKey) return true;
  const key = extractKey(req);
  const record = validateApiKey(key);
  if (!record) {
    res.status(401).json({ error: "API key required", detail: "Provide a valid X-AIHub-Key header." });
    return false;
  }
  req.apiKey = record;
  return true;
}

// GET /api/models/catalog
router.get('/models/catalog', async (_req, res) => {
  const catalog = readModelCatalog();
  res.json(catalog);
});

// In-memory jobs
const jobs = {}; // jobId -> { id, status, downloaded, size, path, registered }

// POST /api/models/download { id } or { url, name }
router.post('/models/download', async (req, res) => {
  const { id, url: customUrl, name } = req.body || {};
  if (!id && !customUrl) return res.status(400).json({ error: 'Missing model id or url' });

  const catalog = readModelCatalog();
  let item = id ? catalog.find(c => c.id === id) : null;
  if (!item && !customUrl) return res.status(404).json({ error: 'Model not in trusted catalog' });
  
  // Check if API key is required for this download
  let requiresApiKey = false;
  if (item) {
    // For catalog models: require API key only if requiresApiKey is not null
    requiresApiKey = item.requiresApiKey !== null && item.requiresApiKey !== undefined;
  } else {
    // For custom URL downloads: require API key if AIHUB_REQUIRE_KEY is enabled
    requiresApiKey = cfg.requireHubKey;
    const derivedId = slugify(name || path.basename(customUrl).split('.')[0] || `custom-${Date.now()}`);
    item = {
      id: `custom-${derivedId}`,
      name: name || derivedId,
      description: 'User-specified custom model download',
      url: customUrl
    };
  }

  // Apply API key requirement if needed
  if (requiresApiKey && !checkApiKey(req, res)) {
    return; // checkApiKey already sent error response
  }

  const url = item.url;
  if (!url || (!url.startsWith('https://') && !url.startsWith('http://'))) {
    return res.status(400).json({ error: 'Invalid model URL' });
  }

  const destDir = path.join(modelsDir, item.id);
  if (!fs.existsSync(destDir)) fs.mkdirSync(destDir, { recursive: true });
  const destFile = path.join(destDir, path.basename(url.split('?')[0]));

  const jobId = `${Date.now()}-${Math.random().toString(36).slice(2,8)}`;
  jobs[jobId] = { id: item.id, status: 'started', downloaded: 0, size: null, path: destFile, name: item.name };

  logger.info("Model download started", {
    jobId,
    modelId: item.id,
    name: item.name,
    url: url.substring(0, 100) // Truncate long URLs
  });

  // Start background download
  (async () => {
    try {
      const resp = await fetch(url, {
        redirect: 'follow',
        headers: {
          'User-Agent': 'AIHub/1.0'
        }
      });

      // Check HTTP status
      if (!resp.ok) {
        const errorText = await resp.text().catch(() => 'Unknown error');
        logger.error("Model download HTTP error", {
          jobId,
          modelId: item.id,
          status: resp.status,
          statusText: resp.statusText
        });
        throw new Error(`HTTP ${resp.status}: ${resp.statusText}. Response: ${errorText.slice(0, 200)}`);
      }

      const size = resp.headers.get('content-length');
      if (size) {
        jobs[jobId].size = parseInt(size, 10);
        const sizeGb = (parseInt(size, 10) / (1024 * 1024 * 1024)).toFixed(2);
        logger.info("Model download size detected", {
          jobId,
          modelId: item.id,
          sizeGb: `${sizeGb} GB`
        });
      }

      // Validate expected size if available
      if (item.size && size) {
        const expectedGb = parseFloat(item.size.replace(/[^0-9.]/g, ''));
        const actualGb = parseInt(size, 10) / (1024 * 1024 * 1024);
        if (actualGb < expectedGb * 0.5) {
          throw new Error(`Download size mismatch: expected ~${item.size}, got ${actualGb.toFixed(2)}GB`);
        }
      }

      const fileStream = fs.createWriteStream(destFile);
      await new Promise((resolve, reject) => {
        resp.body.on('data', chunk => {
          jobs[jobId].downloaded += chunk.length;
        });
        resp.body.pipe(fileStream);
        resp.body.on('error', err => reject(err));
        fileStream.on('finish', () => resolve());
        fileStream.on('error', err => reject(err));
      });

      // Verify file was actually written
      if (!fs.existsSync(destFile)) {
        throw new Error('Download completed but file does not exist');
      }

      const actualSize = fs.statSync(destFile).size;
      if (actualSize < 1024) {
        const content = fs.readFileSync(destFile, 'utf8').slice(0, 500);
        fs.unlinkSync(destFile); // Delete the invalid file
        throw new Error(`Downloaded file is suspiciously small (${actualSize} bytes). Content: ${content}`);
      }

      jobs[jobId].status = 'finished';
      logger.info("Model download completed", {
        jobId,
        modelId: item.id,
        name: item.name,
        path: destFile,
        sizeBytes: jobs[jobId].size || null
      });

      // Attempt to notify Python AI Hub that the model download finished so it can register/validate
      (async () => {
        try {
          const registerPayload = {
            id: item.id,
            name: item.name,
            path: destFile,
            size: jobs[jobId].size || null,
          };
          const regRes = await fetch(`${PYTHON_AI_BASE}/api/models/register`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(registerPayload),
          });
          const regJson = await regRes.json().catch(() => ({}));
          jobs[jobId].registered = regJson;
          logger.info("Model registered with Python AI Hub", {
            jobId,
            modelId: item.id,
            registered: !!regJson
          });
        } catch (e) {
          jobs[jobId].registered = { error: String(e) };
          logger.warn("Failed to register model with Python AI Hub", {
            jobId,
            modelId: item.id,
            error: String(e)
          });
        }
      })();
    } catch (err) {
      jobs[jobId].status = 'error';
      jobs[jobId].error = String(err);
      logger.error("Model download failed", {
        jobId,
        modelId: item.id,
        name: item.name,
        error: err?.message || String(err)
      });
    }
  })();

  res.json({ job: jobId, status: jobs[jobId].status });
});

// GET /api/models/downloads/:jobId/status
router.get('/models/downloads/:jobId/status', (req, res) => {
  const { jobId } = req.params;
  const job = jobs[jobId];
  if (!job) return res.status(404).json({ error: 'Job not found' });
  return res.json({ id: job.id, name: job.name, status: job.status, downloaded: job.downloaded, size: job.size, path: job.path, error: job.error, registered: job.registered });
});

export default router;
