// Menu-driven CLI system with context navigation
import { buildLocalModelsPayload, buildCloudModelsPayload } from "../services/modelSummary.js";
import { getActiveModel, setActiveModel } from "../services/modelRegistry.js";
import { cfg } from "../config.js";
import { providerSuggestions } from "../services/providerCatalog.js";

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

// Menu state
export class MenuState {
  constructor() {
    this.context = "root"; // root, model, model/avail, model/download
    this.modelCache = null; // Cache for model selections
  }

  getPrompt() {
    switch (this.context) {
      case "root":
        return "hub> ";
      case "model":
        return "model> ";
      case "model/avail":
        return "model/avail> ";
      case "model/download":
        return "model/download> ";
      default:
        return "hub> ";
    }
  }

  reset() {
    this.context = "root";
    this.modelCache = null;
  }
}

// Clear screen and show header
function clearAndShowHeader(title, emoji = "📦") {
  console.clear();
  console.log("");
  console.log(color("═══════════════════════════════════════════", ansi.cyan));
  console.log(color(`         ${emoji} ${title}`, `${ansi.bold}${ansi.cyan}`));
  console.log(color("═══════════════════════════════════════════", ansi.cyan));
  console.log("");
}

// Main menu (root)
export function showMainMenu() {
  clearAndShowHeader("AI HUB CONSOLE", "🤖");

  console.log(color("  Available Commands:", ansi.bold));
  console.log("");
  console.log(`    ${color("/model", ansi.cyan).padEnd(25)}  Manage AI models`);
  console.log(`    ${color("/keygen [label]", ansi.green).padEnd(25)}  Generate API key`);
  console.log(`    ${color("/py", ansi.cyan).padEnd(25)}  Start Python ONNX server`);
  console.log(`    ${color("/help", ansi.cyan).padEnd(25)}  Show this menu`);
  console.log(`    ${color("/clear", ansi.cyan).padEnd(25)}  Clear screen`);
  console.log("");

  const activeModel = getActiveModel();
  if (activeModel) {
    console.log(color(`  ● Active model: ${activeModel.id} (${activeModel.provider})`, ansi.green));
  } else {
    console.log(color(`  ⚠️  No active model selected - use '/model' to select one`, ansi.yellow));
  }

  console.log("");
  console.log(color("═══════════════════════════════════════════", ansi.cyan));
  console.log("");
}

// Model menu (inside /model)
export function showModelMenu() {
  clearAndShowHeader("MODEL MANAGER", "📦");

  console.log(color("  Available Commands:", ansi.bold));
  console.log("");
  console.log(`    ${color("avail", ansi.cyan).padEnd(15)}     View available models (local + cloud)`);
  console.log(`    ${color("download", ansi.cyan).padEnd(15)}   Browse downloadable models`);
  console.log(`    ${color("active", ansi.cyan).padEnd(15)}     Show current active model`);
  console.log(`    ${color("back", ansi.gray).padEnd(15)}       Return to main menu`);
  console.log("");

  const activeModel = getActiveModel();
  if (activeModel) {
    console.log(color(`  ● Current: ${activeModel.id} (${activeModel.provider})`, ansi.green));
  }

  console.log("");
  console.log(color("═══════════════════════════════════════════", ansi.cyan));
  console.log("");
}

// Available models view (local + cloud) - renamed from "installed"
export function showAvailableModels() {
  clearAndShowHeader("AVAILABLE MODELS", "✨");

  const localPayload = buildLocalModelsPayload({ includeHardware: true });
  const cloudPayload = buildCloudModelsPayload();
  const activeModel = getActiveModel();

  const modelCache = new Map();
  let index = 1;

  // Local models (selectable/installed)
  const selectable = localPayload.selectable || [];
  if (selectable.length > 0) {
    console.log(color("  LOCAL MODELS (Downloaded & Ready):", ansi.bold));
    console.log("");
    selectable.forEach(model => {
      const active = activeModel?.id === model.id ? color("●", ansi.green) : "○";
      const num = color(String(index).padStart(2), ansi.cyan);
      const name = model.name || model.id;
      const size = color(model.size || "", ansi.gray);
      const runtime = color(`[${cfg.providers.local.kind || "onnx-genai"}]`, ansi.gray);
      console.log(`    ${active} ${num}. ${name.padEnd(35)} ${runtime} ${size}`);
      modelCache.set(index, { id: model.id, provider: "local", name });
      index++;
    });
    console.log("");
  }

  // Cloud models - show all available models from catalog if API key is present
  const cloudModels = [];

  // OpenAI models
  if (cfg.providers.openai.apiKey) {
    const openaiModels = providerSuggestions.openai.models || [];
    openaiModels.forEach(model => {
      const id = `openai:${model.remoteModel}`;
      cloudModels.push({
        id,
        name: model.remoteModel,
        provider: "openai",
        description: model.description
      });
    });
  }

  // Anthropic models
  if (cfg.providers.anthropic.apiKey) {
    const anthropicModels = providerSuggestions.anthropic.models || [];
    anthropicModels.forEach(model => {
      const id = `anthropic:${model.remoteModel}`;
      cloudModels.push({
        id,
        name: model.remoteModel,
        provider: "anthropic",
        description: model.description
      });
    });
  }

  // Google/Gemini models
  if (cfg.providers.google.apiKey) {
    const geminiModels = providerSuggestions.gemini.models || [];
    geminiModels.forEach(model => {
      const id = `gemini:${model.remoteModel}`;
      cloudModels.push({
        id,
        name: model.remoteModel,
        provider: "gemini",
        description: model.description
      });
    });
  }

  // HuggingFace models
  if (cfg.providers.huggingface.apiKey) {
    const hfModels = providerSuggestions.huggingface.models || [];
    hfModels.forEach(model => {
      const id = `huggingface:${model.remoteModel}`;
      cloudModels.push({
        id,
        name: model.remoteModel,
        provider: "huggingface",
        description: model.description
      });
    });
  }

  if (cloudModels.length > 0) {
    console.log(color("  CLOUD MODELS (API Keys Configured):", ansi.bold));
    console.log("");
    cloudModels.forEach(model => {
      const active = activeModel?.id === model.id ? color("●", ansi.green) : "○";
      const num = color(String(index).padStart(2), ansi.cyan);
      const name = model.name.padEnd(35);
      const provider = color(`[${model.provider}]`, ansi.gray);
      console.log(`    ${active} ${num}. ${name} ${provider}`);
      modelCache.set(index, { id: model.id, provider: model.provider, name: model.name });
      index++;
    });
    console.log("");
  }

  if (selectable.length === 0 && cloudModels.length === 0) {
    console.log(color("  No models available yet.", ansi.yellow));
    console.log(color("  Use 'download' to browse and download local models.", ansi.gray));
    console.log("");
  }

  // GPU info
  if (localPayload.hardware) {
    const gpu = (localPayload.hardware.gpu || []).find(g => /nvidia/i.test(g.name || ""));
    if (gpu) {
      const vram = gpu.memoryBytes ? `${(gpu.memoryBytes / 1_073_741_824).toFixed(1)} GB VRAM` : "";
      console.log(color(`  💻 GPU: ${gpu.name} ${vram ? `(${vram})` : ""}`, ansi.gray));
      console.log("");
    }
  }

  console.log(color("  Commands:", ansi.bold));
  console.log(`    ${color("select <number>", ansi.cyan).padEnd(25)}  Activate a model`);
  console.log(`    ${color("back", ansi.gray).padEnd(25)}              Return to model menu`);
  console.log("");
  console.log(color("═══════════════════════════════════════════", ansi.cyan));
  console.log("");

  return modelCache;
}

// Download models view (available to download)
export function showDownloadModels() {
  clearAndShowHeader("AVAILABLE DOWNLOADS", "📥");

  const localPayload = buildLocalModelsPayload({ includeHardware: false });
  const catalog = localPayload.downloads || [];

  const modelCache = new Map();
  let index = 1;

  // Separate by type
  const cudaModels = catalog.filter(m => m.cudaOptimized && !m.requiresHuggingFace);
  const regularModels = catalog.filter(m => !m.cudaOptimized && !m.requiresHuggingFace);
  const hfModels = catalog.filter(m => m.requiresHuggingFace);

  // CUDA-optimized models
  if (cudaModels.length > 0) {
    console.log(color("  CUDA-OPTIMIZED:", ansi.bold));
    console.log("");
    cudaModels.forEach(model => {
      const num = color(String(index).padStart(2), ansi.cyan);
      const cuda = color("⚡", ansi.yellow);
      const name = model.displayName || model.id;
      const size = color(model.size || "", ansi.gray);
      console.log(`    ${num}. ${cuda} ${name.padEnd(40)} ${size}`);
      modelCache.set(index, model);
      index++;
    });
    console.log("");
  }

  // Regular models
  if (regularModels.length > 0) {
    console.log(color("  STANDARD MODELS:", ansi.bold));
    console.log("");
    regularModels.forEach(model => {
      const num = color(String(index).padStart(2), ansi.cyan);
      const name = model.displayName || model.id;
      const size = color(model.size || "", ansi.gray);
      console.log(`    ${num}.   ${name.padEnd(40)} ${size}`);
      modelCache.set(index, model);
      index++;
    });
    console.log("");
  }

  // HuggingFace models (requires token)
  if (hfModels.length > 0) {
    console.log(color("  REQUIRES HUGGINGFACE TOKEN:", ansi.yellow));
    console.log("");
    hfModels.forEach(model => {
      const num = color(String(index).padStart(2), ansi.gray);
      const name = color(model.displayName || model.id, ansi.gray);
      const size = color(model.size || "", ansi.gray);
      console.log(`    ${num}.   ${name.padEnd(40)} ${size}`);
      modelCache.set(index, model);
      index++;
    });
    console.log("");
    console.log(color("  💡 Set HUGGINGFACE_TOKEN in config.env to download these models", ansi.yellow));
    console.log("");
  }

  if (catalog.length === 0) {
    console.log(color("  No models available for download.", ansi.yellow));
    console.log("");
  }

  console.log(color("  Commands:", ansi.bold));
  console.log(`    ${color("download <number>", ansi.cyan).padEnd(25)}  Download a model`);
  console.log(`    ${color("back", ansi.gray).padEnd(25)}                Return to model menu`);
  console.log("");
  console.log(color("═══════════════════════════════════════════", ansi.cyan));
  console.log("");

  return modelCache;
}

// Show active model
export function showActiveModel() {
  clearAndShowHeader("ACTIVE MODEL", "✓");

  const activeModel = getActiveModel();

  if (activeModel) {
    console.log(color("  Currently Active:", ansi.bold));
    console.log("");
    console.log(`    ${color("●", ansi.green)} ${activeModel.id}`);
    console.log(`      Provider: ${activeModel.provider}`);
    if (activeModel.format) {
      console.log(`      Format: ${activeModel.format}`);
    }
    console.log("");
  } else {
    console.log(color("  ⚠️  No model currently selected", ansi.yellow));
    console.log("");
    console.log(color("  Use 'installed' to view and select a model", ansi.gray));
    console.log("");
  }

  console.log(color("  Commands:", ansi.bold));
  console.log(`    ${color("back", ansi.gray).padEnd(15)}  Return to model menu`);
  console.log("");
  console.log(color("═══════════════════════════════════════════", ansi.cyan));
  console.log("");
}
