import fetch from "node-fetch";
import fs from "node:fs";
import path from "node:path";
import { cfg } from "../config.js";
import { logger } from "../utils/logger.js";

function normalizeContent(content) {
  if (typeof content === "string") return content;
  if (Array.isArray(content)) {
    return content
      .map(part => {
        if (typeof part === "string") return part;
        if (typeof part === "object" && part !== null) {
          if (typeof part.text === "string") return part.text;
          return JSON.stringify(part);
        }
        return "";
      })
      .join("\n");
  }
  if (content && typeof content === "object" && typeof content.text === "string") {
    return content.text;
  }
  return String(content ?? "");
}

function ensureKey(name, value) {
  if (!value) {
    throw new Error(`Missing credentials for provider: ${name}`);
  }
}

function buildLocalMessages(payload) {
  const baseMessages = Array.isArray(payload.messages) ? payload.messages : [];
  const normalized = baseMessages.map(m => ({
    role: m.role || "user",
    content: normalizeContent(m.content)
  }));
  if (payload.systemPrompt) {
    normalized.unshift({ role: "system", content: payload.systemPrompt });
  }
  return normalized;
}

const downloadsRoot = cfg.modelDownloadsDir;

function resolveOnnxModelPath(model) {
  if (model?.basePath) {
    const candidate = path.resolve(model.basePath);
    if (fs.existsSync(candidate)) return candidate;
  }
  if (model?.files?.some(file => file.toLowerCase().endsWith(".onnx")) && model.basePath) {
    return path.resolve(model.basePath);
  }
  if (model?.fileHint && model?.basePath) {
    const hinted = path.resolve(model.basePath, model.fileHint);
    if (fs.existsSync(hinted)) {
      return hinted.endsWith(".onnx") ? path.dirname(hinted) : hinted;
    }
  }
  const idSegment = (model?.id || "").includes(":") ? model.id.split(":")[1] : model?.remoteModel;
  if (!idSegment) return null;
  const candidateDir = path.join(downloadsRoot, idSegment);
  if (fs.existsSync(candidateDir)) {
    return candidateDir;
  }
  return null;
}

function mapMessagesForGemini(messages) {
  return messages.map(msg => ({
    role: msg.role === "assistant" ? "model" : "user",
    parts: [{ text: normalizeContent(msg.content) }]
  }));
}

function mapMessagesForAnthropic(messages) {
  const content = [];
  const system = [];
  for (const msg of messages) {
    if (msg.role === "system") {
      system.push(normalizeContent(msg.content));
      continue;
    }
    content.push({
      role: msg.role === "assistant" ? "assistant" : "user",
      content: [{ type: "text", text: normalizeContent(msg.content) }]
    });
  }
  return { system: system.join("\n\n") || undefined, content };
}

async function callOpenAI(model, payload) {
  ensureKey("OpenAI", cfg.providers.openai.apiKey);
  const url = `${cfg.providers.openai.baseURL.replace(/\/$/, "")}/chat/completions`;
  const body = {
    model: model.remoteModel,
    messages: payload.messages,
    temperature: payload.temperature ?? 0.7,
    max_tokens: payload.maxTokens ?? 1024
  };
  if (payload.systemPrompt) {
    body.messages = [{ role: "system", content: payload.systemPrompt }, ...body.messages];
  }
  const resp = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${cfg.providers.openai.apiKey}`
    },
    body: JSON.stringify(body)
  });
  const data = await resp.json();
  if (!resp.ok) {
    throw new Error(data.error?.message || "OpenAI request failed");
  }
  const text = data.choices?.[0]?.message?.content || "";
  return { text, raw: data };
}

async function callAnthropic(model, payload) {
  ensureKey("Anthropic", cfg.providers.anthropic.apiKey);
  const url = `${cfg.providers.anthropic.baseURL.replace(/\/$/, "")}/v1/messages`;
  const mapped = mapMessagesForAnthropic(payload.messages);
  const body = {
    model: model.remoteModel,
    max_tokens: payload.maxTokens ?? 1024,
    temperature: payload.temperature ?? 0.7,
    messages: mapped.content
  };
  if (payload.systemPrompt || mapped.system) {
    body.system = [mapped.system, payload.systemPrompt].filter(Boolean).join("\n\n");
  }
  const resp = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-api-key": cfg.providers.anthropic.apiKey,
      "anthropic-version": "2023-06-01"
    },
    body: JSON.stringify(body)
  });
  const data = await resp.json();
  if (!resp.ok) {
    throw new Error(data.error?.message || "Anthropic request failed");
  }
  const text = data.content?.map(part => part.text).join("\n") || "";
  return { text, raw: data };
}

async function callGemini(model, payload) {
  ensureKey("Gemini", cfg.providers.google.apiKey);
  const base = cfg.providers.google.baseURL.replace(/\/$/, "");
  const url = `${base}/v1beta/models/${model.remoteModel}:generateContent?key=${cfg.providers.google.apiKey}`;
  const body = {
    contents: mapMessagesForGemini(payload.messages)
  };
  if (payload.systemPrompt) {
    body.system_instruction = [{ role: "system", parts: [{ text: payload.systemPrompt }] }];
  }
  const resp = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });
  const data = await resp.json();
  if (!resp.ok) {
    const message = data.error?.message || "Gemini request failed";
    throw new Error(message);
  }
  const text = data.candidates?.[0]?.content?.parts?.map(part => part.text).join("\n") || "";
  return { text, raw: data };
}

async function callHuggingFace(model, payload) {
  ensureKey("HuggingFace", cfg.providers.huggingface.apiKey);
  const base = cfg.providers.huggingface.baseURL.replace(/\/$/, "");
  const url = `${base}/models/${model.remoteModel}`;
  const prompt = payload.messages.map(m => `${m.role}: ${normalizeContent(m.content)}`).join("\n");
  const body = {
    inputs: prompt,
    parameters: {
      max_new_tokens: payload.maxTokens ?? 512,
      temperature: payload.temperature ?? 0.7
    }
  };
  const resp = await fetch(url, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${cfg.providers.huggingface.apiKey}`,
      "Content-Type": "application/json"
    },
    body: JSON.stringify(body)
  });
  const data = await resp.json();
  if (!resp.ok) {
    const message = data.error || "Hugging Face request failed";
    throw new Error(message);
  }
  const text = Array.isArray(data) ? data.map(entry => entry.generated_text).join("\n") : data.generated_text || "";
  return { text, raw: data };
}

async function callLocal(model, payload) {
  const kind = cfg.providers.local.kind;
  if (!cfg.providers.local.baseURL) {
    throw new Error("Set LOCAL_MODEL_URL to route chat to your local runtime.");
  }
  const mergedMessages = buildLocalMessages(payload);
  if (kind === "onnx-genai") {
    const url = `${cfg.providers.local.baseURL.replace(/\/$/, "")}${
      cfg.providers.local.onnxGenAiPath || "/api/chat"
    }`;
    const body = {
      modelId: model.remoteModel || model.id,
      modelPath: resolveOnnxModelPath(model),
      messages: mergedMessages,
      temperature: payload.temperature ?? 0.7,
      maxTokens: payload.maxTokens ?? 1024
    };
    const resp = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) {
      const detail = data.detail || data.error || JSON.stringify(data);
      throw new Error(`ONNX GenAI runtime failed (${resp.status}): ${detail}`);
    }
    const text = data.text || "";
    return { text, raw: data };
  }
  if (kind === "openai") {
    const url = `${cfg.providers.local.baseURL.replace(/\/$/, "")}${cfg.providers.local.openAICompatiblePath}`;
    const body = {
      model: model.remoteModel,
      messages: mergedMessages,
      temperature: payload.temperature ?? 0.7,
      max_tokens: payload.maxTokens ?? 1024
    };
    const headers = { "Content-Type": "application/json" };
    if (cfg.providers.local.apiKey) {
      headers.Authorization = `Bearer ${cfg.providers.local.apiKey}`;
    }
    const resp = await fetch(url, {
      method: "POST",
      headers,
      body: JSON.stringify(body)
    });
    const data = await resp.json();
    if (!resp.ok) {
      throw new Error(data.error?.message || "Local OpenAI-compatible runtime failed");
    }
    const text = data.choices?.[0]?.message?.content || "";
    return { text, raw: data };
  }

  // Default to Ollama-compatible runtime
  const base = cfg.providers.local.baseURL.replace(/\/$/, "");
  const resp = await fetch(`${base}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      model: model.remoteModel,
      stream: false,
      messages: mergedMessages.map(m => ({
        role: m.role,
        content: m.content
      }))
    })
  });
  const data = await resp.json();
  if (!resp.ok) {
    const message = data.error || "Local Ollama runtime failed";
    throw new Error(message);
  }
  const text = data.message?.content || data.response || "";
  return { text, raw: data };
}

export async function callProvider(model, payload) {
  const started = Date.now();
  logger.info("Model request dispatched", {
    provider: model.provider,
    modelId: model.id,
    remoteModel: model.remoteModel || null
  });
  try {
    let result;
    switch (model.provider) {
      case "openai":
        result = await callOpenAI(model, payload);
        break;
      case "anthropic":
        result = await callAnthropic(model, payload);
        break;
      case "gemini":
        result = await callGemini(model, payload);
        break;
      case "huggingface":
        result = await callHuggingFace(model, payload);
        break;
      case "local":
        result = await callLocal(model, payload);
        break;
      default:
        throw new Error(`Unsupported provider ${model.provider}`);
    }
    logger.info("Model response received", {
      provider: model.provider,
      modelId: model.id,
      durationMs: Date.now() - started
    });
    return result;
  } catch (err) {
    logger.error("Model provider failed", {
      provider: model.provider,
      modelId: model.id,
      durationMs: Date.now() - started,
      error: err?.message || String(err)
    });
    throw err;
  }
}
