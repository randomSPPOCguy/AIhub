import fs from "node:fs";
import path from "node:path";
import { cfg } from "../config.js";
import { getState, setState } from "./hubState.js";
import { providerSuggestions } from "./providerCatalog.js";

const downloadsDir = cfg.modelDownloadsDir;
const ACTIVE_MODEL_KEY = "active_model_id";

const cloudModels = buildCloudModels();
const configuredLocalModels = buildConfiguredLocalModels();
const baseModels = [...cloudModels, ...configuredLocalModels];
const defaultModelId = baseModels.find(m => m.default)?.id || baseModels[0]?.id || null;

function addCloudModel(list, { provider, model, apiKey, apiKeyEnv, name, description, note, isDefault }) {
  if (!model || !apiKey) return;
  const displayName = note ? `${name} ${note}` : name;
  list.push({
    id: `${provider}:${model}`,
    name: displayName,
    provider,
    type: "cloud",
    description,
    remoteModel: model,
    apiKeyEnv,
    note,
    default: Boolean(isDefault),
    source: "cloud",
    suggestions: providerSuggestions[provider]?.models || [],
    localNote: providerSuggestions[provider]?.localNote
  });
}

function buildCloudModels() {
  const models = [];

  // OpenAI models - add all available models from catalog if API key is present
  if (cfg.providers.openai.apiKey) {
    const openaiCatalog = providerSuggestions.openai?.models || [];
    openaiCatalog.forEach((catalogModel, idx) => {
      addCloudModel(models, {
        provider: "openai",
        model: catalogModel.remoteModel,
        apiKey: cfg.providers.openai.apiKey,
        apiKeyEnv: "OPENAI_API_KEY",
        name: catalogModel.remoteModel,
        description: catalogModel.description,
        isDefault: idx === 0 && !models.some(m => m.default)
      });
    });
  }

  // Anthropic models - add all available models from catalog if API key is present
  if (cfg.providers.anthropic.apiKey) {
    const anthropicCatalog = providerSuggestions.anthropic?.models || [];
    anthropicCatalog.forEach((catalogModel) => {
      addCloudModel(models, {
        provider: "anthropic",
        model: catalogModel.remoteModel,
        apiKey: cfg.providers.anthropic.apiKey,
        apiKeyEnv: "ANTHROPIC_API_KEY",
        name: catalogModel.remoteModel,
        description: catalogModel.description
      });
    });
  }

  // Google/Gemini models - add all available models from catalog if API key is present
  if (cfg.providers.google.apiKey) {
    const geminiCatalog = providerSuggestions.gemini?.models || [];
    geminiCatalog.forEach((catalogModel) => {
      addCloudModel(models, {
        provider: "gemini",
        model: catalogModel.remoteModel,
        apiKey: cfg.providers.google.apiKey,
        apiKeyEnv: "GOOGLE_API_KEY / GEMINI_API_KEY",
        name: catalogModel.remoteModel,
        description: catalogModel.description
      });
    });
  }

  // HuggingFace models - add all available models from catalog if API key is present
  if (cfg.providers.huggingface.apiKey) {
    const hfCatalog = providerSuggestions.huggingface?.models || [];
    hfCatalog.forEach((catalogModel) => {
      addCloudModel(models, {
        provider: "huggingface",
        model: catalogModel.remoteModel,
        apiKey: cfg.providers.huggingface.apiKey,
        apiKeyEnv: "HUGGINGFACE_API_KEY",
        name: catalogModel.remoteModel,
        description: catalogModel.description,
        note: "(requires huggingface API key)"
      });
    });
  }

  if (!models.some(m => m.default) && models[0]) {
    models[0].default = true;
  }
  return models;
}

function buildConfiguredLocalModels() {
  const models = [];
  const localModel = (cfg.providers.local.model || "").trim();
  if (localModel) {
    models.push({
      id: `local:${localModel}`,
      name: `Local ${localModel}`,
      provider: "local",
      type: "local",
      description: "Local runtime configured via LOCAL_MODEL_* environment variables.",
      remoteModel: localModel,
      fileHint: localModel === "phi-3-mini-128k-instruct" ? "Phi-3-mini-128k-instruct-q4.gguf" : undefined,
      runtime: {
        baseURL: cfg.providers.local.baseURL,
        kind: cfg.providers.local.kind,
        openAICompatiblePath: cfg.providers.local.openAICompatiblePath,
        onnxGenAiPath: cfg.providers.local.onnxGenAiPath
      },
      source: "local:configured"
    });
  }
  return models;
}

function discoverLocalModels() {
  if (!fs.existsSync(downloadsDir)) return [];
  const entries = fs.readdirSync(downloadsDir, { withFileTypes: true });
  const locals = [];

  // Recursively find model files
  function walkDir(dir) {
    let results = [];
    try {
      const items = fs.readdirSync(dir, { withFileTypes: true });
      for (const item of items) {
        const fullPath = path.join(dir, item.name);
        if (item.isDirectory()) {
          results = results.concat(walkDir(fullPath));
        } else if (/\.(gguf|ggml|safetensors|onnx|bin|data)$/i.test(item.name)) {
          results.push(fullPath);
        }
      }
    } catch (err) {
      // Ignore permission errors
    }
    return results;
  }

  for (const entry of entries) {
    if (!entry.isDirectory()) continue;
    const dirPath = path.join(downloadsDir, entry.name);
    const allFiles = walkDir(dirPath);

    // Calculate total size
    let totalSize = 0;
    const relativeFiles = [];
    for (const filePath of allFiles) {
      try {
        const stat = fs.statSync(filePath);
        totalSize += stat.size;
        relativeFiles.push(path.relative(dirPath, filePath));
      } catch (err) {
        // Skip files we can't stat
      }
    }

    locals.push({
      id: `local:${entry.name}`,
      name: `Local ${entry.name}`,
      provider: "local",
      type: "local",
      description: "User-downloaded local model artifact.",
      remoteModel: entry.name,
      files: relativeFiles,
      sizeBytes: totalSize,
      basePath: dirPath,
      source: "local:downloaded"
    });
  }
  return locals;
}

export function listModels() {
  return [...listCloudModels(), ...listInstalledLocalModels()];
}

export function listCloudModels() {
  return cloudModels.slice();
}

export function listConfiguredLocalModels() {
  return configuredLocalModels.slice();
}

export function listInstalledLocalModels() {
  const installed = discoverLocalModels();
  const map = new Map();
  for (const model of configuredLocalModels) {
    map.set(model.id, model);
  }
  for (const model of installed) {
    const existing = map.get(model.id) || {};
    map.set(model.id, { ...existing, ...model });
  }
  return Array.from(map.values());
}

export function listDownloadedLocalArtifacts() {
  return discoverLocalModels();
}

export function getModelById(id) {
  return listModels().find(m => m.id === id);
}

export function getActiveModel() {
  const storedId = getState(ACTIVE_MODEL_KEY, defaultModelId);
  if (storedId) {
    const model = getModelById(storedId);
    if (model) return model;
  }

  const models = listModels();
  const fallback = (defaultModelId && models.find(m => m.id === defaultModelId)) || models[0];
  if (fallback) {
    setState(ACTIVE_MODEL_KEY, fallback.id);
    return fallback;
  }

  throw new Error("No models registered in registry.");
}

export function setActiveModel(id) {
  const model = getModelById(id);
  if (!model) throw new Error(`Model ${id} not found`);
  setState(ACTIVE_MODEL_KEY, id);
  return model;
}

export function getActiveModelId() {
  return getActiveModel().id;
}

export function getLocalRuntimeConfig() {
  return {
    baseURL: cfg.providers.local.baseURL,
    kind: cfg.providers.local.kind,
    openAICompatiblePath: cfg.providers.local.openAICompatiblePath
  };
}
