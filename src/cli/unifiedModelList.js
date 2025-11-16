// Unified model list builder - combines local + cloud + available downloads
import { buildCloudModelsPayload, buildLocalModelsPayload } from "../services/modelSummary.js";
import { getActiveModel } from "../services/modelRegistry.js";
import { cfg } from "../config.js";

const ansi = {
  reset: "\x1b[0m",
  bold: "\x1b[1m",
  magenta: "\x1b[35m",
  cyan: "\x1b[36m",
  yellow: "\x1b[33m",
  green: "\x1b[32m",
  gray: "\x1b[90m",
  red: "\x1b[31m",
  blue: "\x1b[34m"
};

const color = (text, code) => `${code}${text}${ansi.reset}`;

/**
 * Build a unified model list combining:
 * - Local models (downloaded & ready)
 * - Cloud models (with API keys configured)
 * - Available downloads
 */
export function buildUnifiedModelList() {
  const localPayload = buildLocalModelsPayload({ includeHardware: true });
  const cloudPayload = buildCloudModelsPayload();

  const unifiedList = [];
  let index = 1;

  // Section 1: Local Models (Downloaded & Ready)
  const downloaded = localPayload.downloaded || [];
  const downloadedEntries = downloaded.map(model => ({
    index: index++,
    id: model.id,
    name: model.displayName || model.id,
    provider: "local",
    type: "downloaded",
    format: model.format?.toUpperCase() || "ONNX",
    size: model.size,
    ready: true,
    runtime: cfg.providers.local.kind || "onnx-genai"
  }));

  // Section 2: Cloud Models (API Key Configured)
  const cloudModels = [];

  // OpenAI models
  if (cfg.providers.openai.apiKey) {
    const openaiModels = cloudPayload.models?.filter(m => m.provider === "openai") || [];
    openaiModels.forEach(model => {
      cloudModels.push({
        index: index++,
        id: model.id,
        name: model.displayName || model.id,
        provider: "openai",
        type: "cloud",
        ready: true,
        hasKey: true
      });
    });
  }

  // Anthropic models
  if (cfg.providers.anthropic.apiKey) {
    const anthropicModels = cloudPayload.models?.filter(m => m.provider === "anthropic") || [];
    anthropicModels.forEach(model => {
      cloudModels.push({
        index: index++,
        id: model.id,
        name: model.displayName || model.id,
        provider: "anthropic",
        type: "cloud",
        ready: true,
        hasKey: true
      });
    });
  }

  // Google models
  if (cfg.providers.google.apiKey) {
    const googleModels = cloudPayload.models?.filter(m => m.provider === "gemini" || m.provider === "google") || [];
    googleModels.forEach(model => {
      cloudModels.push({
        index: index++,
        id: model.id,
        name: model.displayName || model.id,
        provider: "gemini",
        type: "cloud",
        ready: true,
        hasKey: true
      });
    });
  }

  // Section 3: Available Downloads (Local Models Not Yet Downloaded)
  const availableDownloads = (localPayload.catalog || []).map(entry => ({
    index: index++,
    id: entry.id,
    name: entry.displayName || entry.id,
    provider: "local",
    type: "available",
    format: entry.format?.toUpperCase() || "?",
    size: entry.size,
    ready: false,
    cudaOptimized: entry.cudaOptimized,
    requiresHf: entry.requiresHuggingFaceToken
  }));

  return {
    downloaded: downloadedEntries,
    cloud: cloudModels,
    available: availableDownloads,
    all: [...downloadedEntries, ...cloudModels, ...availableDownloads],
    hardware: localPayload.hardware
  };
}

/**
 * Print the unified model list
 */
export function printUnifiedModelList() {
  const list = buildUnifiedModelList();
  const activeModel = getActiveModel();

  console.log("");
  console.log(color("═══════════════════════════════════════════", ansi.cyan));
  console.log(color("         📦 AVAILABLE MODELS", `${ansi.bold}${ansi.cyan}`));
  console.log(color("═══════════════════════════════════════════", ansi.cyan));
  console.log("");

  // Section 1: Local Models (Downloaded)
  if (list.downloaded.length > 0) {
    console.log(color("  🖥️  LOCAL MODELS (Downloaded & Ready)", ansi.bold));
    console.log("");
    list.downloaded.forEach(model => {
      const active = activeModel?.id === model.id ? color("  ●", ansi.green) : "  ○";
      const num = color(String(model.index).padStart(2), ansi.cyan);
      const name = model.name.padEnd(45);
      const provider = color(`[${model.runtime}]`, ansi.gray);
      const size = color(model.size, ansi.gray);
      console.log(`${active} ${num}. ${name} ${provider} ${size}`);
    });
    console.log("");
  }

  // Section 2: Cloud Models
  if (list.cloud.length > 0) {
    console.log(color("  ☁️  CLOUD MODELS (API Key Configured)", ansi.bold));
    console.log("");
    list.cloud.forEach(model => {
      const active = activeModel?.id === model.id ? color("  ●", ansi.green) : "  ○";
      const num = color(String(model.index).padStart(2), ansi.cyan);
      const name = model.name.padEnd(45);
      const provider = color(`[${model.provider}]`, ansi.gray);
      console.log(`${active} ${num}. ${name} ${provider}`);
    });
    console.log("");
  }

  // Section 3: Available for Download
  if (list.available.length > 0) {
    console.log(color("  📥 AVAILABLE FOR DOWNLOAD", ansi.bold));
    console.log("");

    // Separate CUDA-optimized and regular models
    const cudaModels = list.available.filter(m => m.cudaOptimized && !m.requiresHf);
    const regularModels = list.available.filter(m => !m.cudaOptimized && !m.requiresHf);
    const hfModels = list.available.filter(m => m.requiresHf);

    // CUDA-optimized models first
    if (cudaModels.length > 0) {
      cudaModels.forEach(model => {
        const num = color(String(model.index).padStart(2), ansi.cyan);
        const cuda = color("⚡", ansi.yellow);
        const name = model.name.padEnd(44);
        const size = color(`${model.size}`, ansi.gray);
        console.log(`     ${num}. ${cuda} ${name} ${size}`);
      });
    }

    // Regular models
    if (regularModels.length > 0) {
      regularModels.forEach(model => {
        const num = color(String(model.index).padStart(2), ansi.cyan);
        const name = model.name.padEnd(45);
        const size = color(`${model.size}`, ansi.gray);
        console.log(`     ${num}.   ${name} ${size}`);
      });
    }

    // HuggingFace models (grayed out)
    if (hfModels.length > 0) {
      console.log(color("     Requires HuggingFace token:", ansi.yellow));
      hfModels.forEach(model => {
        const num = color(String(model.index).padStart(2), ansi.gray);
        const name = color(model.name.padEnd(45), ansi.gray);
        const size = color(model.size, ansi.gray);
        console.log(`     ${num}.   ${name} ${size}`);
      });
    }

    console.log("");
  }

  // Active model indicator
  if (activeModel) {
    console.log(color(`  ● Currently Active: ${activeModel.id} (${activeModel.provider})`, ansi.green));
  } else {
    console.log(color(`  ⚠️  No model selected - use '/model select <number>' to choose one`, ansi.yellow));
  }

  // Hardware info
  if (list.hardware) {
    const gpu = (list.hardware.gpu || []).find(g => /nvidia/i.test(g.name || ""));
    if (gpu) {
      const vram = gpu.memoryBytes ? `${(gpu.memoryBytes / 1_073_741_824).toFixed(1)} GB VRAM` : "";
      console.log(color(`  💻 GPU: ${gpu.name} ${vram ? `(${vram})` : ""}`, ansi.gray));
    }
  }

  console.log("");
  console.log(color("═══════════════════════════════════════════", ansi.cyan));
  console.log("");
  console.log(color("  Commands:", ansi.bold));
  console.log(color("    /model select <number>   ", ansi.cyan) + "Activate a model");
  console.log(color("    /model download <number> ", ansi.cyan) + "Download a local model");
  console.log(color("    /model active            ", ansi.cyan) + "Show current active model");
  console.log("");

  return list;
}

/**
 * Get model by index from unified list
 */
export function getModelByIndex(index) {
  const list = buildUnifiedModelList();
  return list.all.find(m => m.index === parseInt(index));
}
