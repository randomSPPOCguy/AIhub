// src/services/enrichmentClient.js
// Client for calling the Python enrichment service

import fetch from "node-fetch";
import { cfg } from "../config.js";
import { logger } from "../utils/logger.js";

const enrichLogLevel = (process.env.ENRICH_LOG_LEVEL || "").toLowerCase();
const ENRICH_MODE = ["quiet", "debug"].includes(enrichLogLevel) ? enrichLogLevel : "standard";
const FORCE_DEBUG = ENRICH_MODE === "debug";

const truncateText = (value = "") => {
  const normalized = value.trim().replace(/\s+/g, " ");
  return normalized.length > 80 ? `${normalized.slice(0, 77)}...` : normalized;
};

const summarizeSubjects = (hints) => {
  const subjects = Array.isArray(hints?.subjects) ? hints.subjects : [];
  if (!subjects.length) return "auto";
  const labels = subjects
    .map((s) => (typeof s === "string" ? s : s.name || s.type || "subject"))
    .filter(Boolean);
  const preview = labels.slice(0, 3).join(",");
  return `${subjects.length} [${preview}]`;
};

const summarizeProviders = (hints) => {
  if (Array.isArray(hints?.providers) && hints.providers.length) {
    return hints.providers.join(",");
  }
  return "auto";
};

function logEnrich(level, message, meta = {}, { force = false } = {}) {
  const payload = [`[ENRICH] ${message}`];
  if (meta && Object.keys(meta).length) {
    payload.push(meta);
  }
  if (force) {
    logger.force(level, ...payload);
    return;
  }
  if (typeof logger[level] === "function") {
    logger[level](...payload);
  } else {
    logger.log(level, ...payload);
  }
}

/**
 * Call the enrichment service with the given parameters.
 *
 * @param {Object} params - Enrichment request parameters
 * @param {string} params.text - Text to enrich (required)
 * @param {Object} [params.room] - Room context (optional)
 * @param {Object} [params.hints] - Enrichment hints (optional)
 * @param {string} [params.traceId] - Trace ID for request tracking (optional)
 * @returns {Promise<Object|null>} Enrichment response or null on failure
 */
export async function callEnrichment({ text, room, hints, traceId }) {
  // Check if enrichment is enabled
  if (!cfg.enrich.enabled) {
    logEnrich("info", "Skipping enrichment (disabled via config)");
    return null;
  }

  // Validate required text
  if (!text || typeof text !== "string" || !text.trim()) {
    logEnrich("warn", "Skipping enrichment (no text provided)");
    return null;
  }

  const url = `${cfg.enrich.url}/enrich`;
  const trace_id = traceId || null;
  const normalizedText = text.trim();
  const textPreview = truncateText(normalizedText);

  // Build request payload
  const payload = {
    trace_id,
    text: normalizedText,
    ...(room && { room }),
    ...(hints && { hints })
  };

  // Build headers
  const headers = {
    "Content-Type": "application/json"
  };

  if (cfg.enrich.token) {
    headers.Authorization = `Bearer ${cfg.enrich.token}`;
  }

  // Create AbortController for timeout
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), cfg.enrich.timeout);

  try {
    if (ENRICH_MODE !== "quiet") {
      logEnrich("info", `Request: text="${textPreview}" subjects=${summarizeSubjects(hints)}`, {
        traceId: trace_id,
        providers: summarizeProviders(hints)
      });
    }

    const startTime = Date.now();
    const response = await fetch(url, {
      method: "POST",
      headers,
      body: JSON.stringify(payload),
      signal: controller.signal
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      const errorText = await response.text().catch(() => "Unknown error");
      const err = new Error(`Enrich service error: ${response.status} - ${errorText}`);
      err.status = response.status;
      throw err;
    }

    const data = await response.json();
    const latency = Date.now() - startTime;

    const successMessage =
      ENRICH_MODE === "quiet"
        ? `Success text="${textPreview}"`
        : `Success: text="${textPreview}" subjects=${data.subjects?.length || 0} providers=${summarizeProviders(
            hints
          )}`;
    logEnrich("info", successMessage, {
      traceId: trace_id,
      facts: data.facts?.length || 0,
      latencyMs: latency,
      cacheStatus: data.meta?.cache_status
    });

    if (ENRICH_MODE === "debug") {
      logEnrich("debug", "Raw enrichment response", { traceId: trace_id, response: data }, { force: FORCE_DEBUG });
    }

    return data;
  } catch (error) {
    clearTimeout(timeoutId);

    if (error.name === "AbortError") {
      logEnrich("error", "Timeout", {
        traceId: trace_id,
        timeoutMs: cfg.enrich.timeout,
        text: textPreview
      });
    } else {
      const status = error?.status || error?.code || null;
      logEnrich("error", `Failed text="${textPreview}" status=${status ?? "n/a"}`, {
        traceId: trace_id,
        error: error?.message || String(error)
      });
    }

    // Return null on failure (don't throw) - graceful degradation
    return null;
  }
}

