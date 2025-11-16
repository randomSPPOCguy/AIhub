import express from 'express';
import fetch from 'node-fetch';
import { cfg } from '../config.js';

const router = express.Router();

// Configure the Python AI Hub URL (adjust if your Python server runs elsewhere)
const PYTHON_AI_BASE = cfg.python.baseUrl.replace(/\/$/, '');

// Proxy POST /api/chat -> Python /api/chat
router.post('/chat', async (req, res) => {
  try {
    const url = `${PYTHON_AI_BASE}/api/chat`;
    const resp = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req.body),
      // forward client ip or other headers if needed
    });

    const contentType = resp.headers.get('content-type') || '';
    if (contentType.includes('application/json')) {
      const json = await resp.json();
      return res.status(resp.status).json(json);
    } else {
      const text = await resp.text();
      res.status(resp.status).send(text);
    }
  } catch (err) {
    console.error('[CHAT_PROXY] Error proxying to Python AI Hub', err);
    res.status(502).json({ error: 'Failed to proxy to Python AI Hub', detail: String(err) });
  }
});

// GET /api/local_models -> Python /api/local_models
router.get('/local_models', async (_req, res) => {
  try {
    const url = `${PYTHON_AI_BASE}/api/local_models`;
    const resp = await fetch(url);
    const json = await resp.json();
    res.status(resp.status).json(json);
  } catch (err) {
    console.error('[CHAT_PROXY] Error fetching local models', err);
    res.status(502).json({ error: 'Failed to fetch local models', detail: String(err) });
  }
});

// POST /api/local_chat -> Python /api/local_chat
router.post('/local_chat', async (req, res) => {
  try {
    const url = `${PYTHON_AI_BASE}/api/local_chat`;
    const resp = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req.body),
    });
    const contentType = resp.headers.get('content-type') || '';
    if (contentType.includes('application/json')) {
      const json = await resp.json();
      return res.status(resp.status).json(json);
    } else {
      const text = await resp.text();
      res.status(resp.status).send(text);
    }
  } catch (err) {
    console.error('[CHAT_PROXY] Error proxying local_chat to Python AI Hub', err);
    res.status(502).json({ error: 'Failed to proxy local_chat', detail: String(err) });
  }
});

export default router;
