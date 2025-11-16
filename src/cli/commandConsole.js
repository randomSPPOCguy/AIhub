import readline from "node:readline";
import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import fetch from "node-fetch";
import { cfg } from "../config.js";
import {
  buildModelOverviewPayload,
  buildCloudModelsPayload,
  buildLocalModelsPayload
} from "../services/modelSummary.js";
import { getActiveModel, setActiveModel } from "../services/modelRegistry.js";
import { printUnifiedModelList, getModelByIndex } from "./unifiedModelList.js";
import {
  MenuState,
  showMainMenu,
  showModelMenu,
  showAvailableModels,
  showDownloadModels,
  showActiveModel
} from "./menuSystem.js";
import { parseSizeGb, selectRecommendedDownload } from "../services/localRecommendations.js";
import {
  needsOnboarding,
  runOnboardingWizard,
  detectTooling,
  getToolingInstructions
} from "../services/onboardingWizard.js";

const ansi = {
  reset: "\x1b[0m",
  bold: "\x1b[1m",
  magenta: "\x1b[35m",
  cyan: "\x1b[36m",
  yellow: "\x1b[33m",
  green: "\x1b[32m",
  gray: "\x1b[90m",
  red: "\x1b[31m"
};
const color = (text, code) => `${code}${text}${ansi.reset}`;

const COMMAND_ENTRIES = [
  { category: "Models", usage: "/model", description: "List all available models (local + cloud)" },
  { category: "Models", usage: "/model select <#>", description: "Activate a model by number" },
  { category: "Models", usage: "/model download <#>", description: "Download a local model" },
  { category: "Models", usage: "/model active", description: "Show currently active model" },
  { category: "Setup", usage: "/keygen [label]", description: "🔑 Generate API key", highlight: true },
  { category: "Setup", usage: "/py", description: "Start Python ONNX server" },
  { category: "Info", usage: "/help", description: "Show this help" },
  { category: "Info", usage: "/clear", description: "Clear screen" },
  // Legacy commands (still supported)
  { category: "Legacy", usage: "local", description: "Old command (use /model instead)", hidden: true },
  { category: "Legacy", usage: "select", description: "Old command (use /model select)", hidden: true },
  { category: "Legacy", usage: "download", description: "Old command (use /model download)", hidden: true }
];

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PYTHON_SERVER_PATH = path.resolve(__dirname, "../../python_ai/server.py");
const PYTHON_VENV_WIN = path.resolve(__dirname, "../../python_ai/.venv/Scripts/python.exe");
const PYTHON_VENV_NIX = path.resolve(__dirname, "../../python_ai/.venv/bin/python");
let pythonServerProcess = null;

let started = false;
const lastCatalogSelections = new Map();
const menuState = new MenuState();
let modelCache = new Map(); // Cache for model selections in current view
function formatStatus(value) {
  return value ? color("Detected", ansi.green) : color("Missing", ansi.red);
}

function inferModelFormat(entry) {
  if (entry?.format) return entry.format;
  const files = entry?.files || [];
  if (files.some(file => file.toLowerCase().endsWith(".onnx"))) return "onnx";
  if (files.some(file => file.toLowerCase().endsWith(".gguf"))) return "gguf";
  if (files.some(file => file.toLowerCase().endsWith(".bin"))) return "bin";
  return "unknown";
}

function printCommandPalette() {
  console.log("");
  console.log(color("═══════════════════════════════════════════", ansi.cyan));
  console.log(color("         📖 COMMAND REFERENCE", `${ansi.bold}${ansi.cyan}`));
  console.log(color("═══════════════════════════════════════════", ansi.cyan));
  console.log("");

  // Group by category
  const categories = {};
  for (const entry of COMMAND_ENTRIES) {
    // Skip hidden commands (legacy)
    if (entry.hidden) continue;
    if (!categories[entry.category]) categories[entry.category] = [];
    categories[entry.category].push(entry);
  }

  // Print each category
  for (const [category, entries] of Object.entries(categories)) {
    console.log(color(`  ${category}:`, ansi.bold));
    for (const entry of entries) {
      const usage = entry.usage.padEnd(25, " ");
      const cmdColor = entry.highlight ? ansi.green : ansi.cyan;
      console.log(`    ${color(usage, cmdColor)} ${entry.description}`);
    }
    console.log("");
  }

  console.log(color("  💡 Tip: Run '/model' to see all available models", ansi.gray));
  console.log("");
}

function resolvePythonExecutable() {
  if (cfg.python.bin) {
    return cfg.python.bin;
  }
  if (fs.existsSync(PYTHON_VENV_WIN)) {
    return PYTHON_VENV_WIN;
  }
  if (fs.existsSync(PYTHON_VENV_NIX)) {
    return PYTHON_VENV_NIX;
  }
  return cfg.python.interpreter;
}

function startPythonServer() {
  if (pythonServerProcess && !pythonServerProcess.killed) {
    console.log(color("[PY] Python server already running in this terminal.", ansi.yellow));
    return;
  }
  if (!fs.existsSync(PYTHON_SERVER_PATH)) {
    console.log(
      color("[PY] python_ai/server.py not found. Download the Python helper first.", ansi.red)
    );
    return;
  }
  const pythonBin = resolvePythonExecutable();
  console.log(
    color(
      `[PY] Launching Python ONNX GenAI server via ${pythonBin} ${PYTHON_SERVER_PATH}`,
      ansi.cyan
    )
  );
  const projectRoot = path.resolve(__dirname, "../..");
  const appendPath = process.env.CUDA_PATH_APPEND || process.env.AIHUB_PATH_APPEND || "";
  const augmentedPath = appendPath ? `${appendPath};${process.env.PATH}` : process.env.PATH;
  const resolvedModelRoot = path.resolve(cfg.python.modelRoot || path.join(projectRoot, "models", "downloads"));

  pythonServerProcess = spawn(pythonBin, [PYTHON_SERVER_PATH], {
    cwd: path.dirname(PYTHON_SERVER_PATH),
    env: {
      ...process.env,
      PYTHON_MODEL_ROOT: resolvedModelRoot,
      PATH: augmentedPath
    },
    stdio: ["ignore", "pipe", "pipe"]
  });
  pythonServerProcess.stdout.on("data", chunk => {
    process.stdout.write(color(`[PY] ${chunk.toString()}`, ansi.green));
  });
  pythonServerProcess.stderr.on("data", chunk => {
    process.stdout.write(color(`[PY] ${chunk.toString()}`, ansi.red));
  });
  pythonServerProcess.on("close", code => {
    console.log(
      color(
        `[PY] Python server exited${typeof code === "number" ? ` (code ${code})` : ""}.`,
        ansi.yellow
      )
    );
    pythonServerProcess = null;
  });
  pythonServerProcess.on("error", err => {
    console.log(color(`[PY] Failed to launch Python server: ${err.message}`, ansi.red));
    pythonServerProcess = null;
  });
}

function logOverview() {
  const overview = buildModelOverviewPayload();
  const cpu = overview.hardware?.cpu;
  const gpu = overview.hardware?.gpu || [];
  const tooling = detectTooling();
  const recommended = selectRecommendedDownload(
    (overview.local.downloads || []).filter(entry => !entry.requiresHuggingFace),
    overview.hardware
  );
  console.log("");
  console.log(color("[CMD] === Overview ===", `${ansi.bold}${ansi.magenta}`));
  if (cpu) {
    console.log(
      `[CMD] CPU: ${cpu.model} | logical cores: ${cpu.logicalCores} | arch: ${cpu.architecture}`
    );
  }
  if (gpu.length) {
    for (const g of gpu) {
      const mem =
        typeof g.memoryBytes === "number"
          ? `${Math.round((g.memoryBytes / 1_073_741_824) * 10) / 10} GB`
          : "memory: n/a";
      console.log(`[CMD] GPU: ${g.name}${mem ? ` (${mem})` : ""}`);
    }
  } else {
    console.log(`${color("[CMD]", ansi.gray)} GPU: not detected`);
  }
  const activeModel = overview.activeModel;
  let activeLabel = activeModel?.id || "none";
  if (activeModel?.provider === "local") {
    activeLabel = `${activeModel.id} (local ${cfg.providers.local.kind || "runtime"})`;
  }
  console.log(`${color("[CMD]", ansi.gray)} Active model: ${color(activeLabel, ansi.green)}`);
  console.log(color("[CMD]", ansi.bold) + " Tooling:");
  console.log(`${color("[CMD]", ansi.gray)} • ONNX Runtime GenAI: ${formatStatus(tooling.hasOnnx)}`);
  console.log(`${color("[CMD]", ansi.gray)} • PyTorch CUDA: ${formatStatus(tooling.hasTorch)}`);
  console.log(`${color("[CMD]", ansi.gray)} • CUDA toolkit / drivers: ${formatStatus(tooling.hasCuda)}`);
  console.log(
    `${color("[CMD]", ansi.gray)} Cloud providers unlocked: ${overview.cloud.providers.length}`
  );
  console.log(
    `${color("[CMD]", ansi.gray)} Configured local runtimes: ${overview.local.configured?.length || 0}`
  );
  console.log(
    `${color("[CMD]", ansi.gray)} Downloaded local models: ${overview.local.installed?.length || 0}`
  );
  if (recommended?.entry) {
    console.log(
      color(
        `[CMD] Recommended download: ${recommended.entry.displayName} (fits ${recommended.nvidiaGpu?.name || "detected GPU"})`,
        ansi.green
      )
    );
  }
  console.log("");
}

function logCloud() {
  const payload = buildCloudModelsPayload();
  console.log("");
  console.log(color("[CMD] === Cloud Providers ===", `${ansi.bold}${ansi.magenta}`));
  if (!payload.providers.length) {
    console.log(`${color("[CMD]", ansi.gray)} No cloud providers unlocked. Add your API keys to config.env.`);
  } else {
    for (const provider of payload.providers) {
      console.log(
        `${color("[CMD]", ansi.gray)} ${color(provider.id, ansi.cyan)} :: ${provider.description} ${provider.note || ""}`.trim()
      );
      if (Array.isArray(provider.suggestions) && provider.suggestions.length) {
        provider.suggestions.forEach(suggestion => {
          console.log(
            `${color("[CMD]", ansi.gray)}    → try ${suggestion.remoteModel} – ${suggestion.description}`
          );
        });
      }
      if (provider.localNote) {
        console.log(`${color("[CMD]", ansi.yellow)}    ${provider.localNote}`);
      }
    }
  }
  console.log("");
}

function logLocal() {
  const payload = buildLocalModelsPayload({ includeHardware: true });
  const configured = payload.configured || [];
  const installed = payload.installed || [];
  const tooling = detectTooling();
  lastCatalogSelections.clear();
  console.log("");
  console.log(color("=== Local Models ===", `${ansi.bold}${ansi.magenta}`));

  // Tooling status
  const onnxStatus = tooling.hasOnnx ? color("✓", ansi.green) : color("✗", ansi.red);
  const cudaStatus = tooling.hasCuda ? color("✓", ansi.green) : color("✗", ansi.red);
  console.log(`${color("Tooling:", ansi.bold)} ONNX GenAI ${onnxStatus} | CUDA ${cudaStatus}`);
  console.log("");

  // Configured runtimes
  if (configured.length > 0) {
    console.log(color("Configured Runtimes:", ansi.bold));
    for (const model of configured) {
      const runtime = model.runtime || {};
      const kind = runtime.kind || "unknown";
      const readyIcon = (kind === "onnx-genai" && tooling.hasOnnx) ? color("✓", ansi.green) : color("○", ansi.gray);
      console.log(`  ${readyIcon} ${color(model.remoteModel, ansi.cyan)} (${kind})`);
    }
    console.log("");
  }

  // Downloaded artifacts
  if (installed.length > 0) {
    console.log(color("Downloaded Models:", ansi.bold));
    for (const model of installed) {
      const size = typeof model.sizeBytes === "number" ? `${(model.sizeBytes / 1_073_741_824).toFixed(1)} GB` : "?";
      const format = inferModelFormat(model);
      const readyIcon = (format === "onnx" && tooling.hasOnnx) ? color("✓", ansi.green) : color("○", ansi.gray);
      console.log(`  ${readyIcon} ${color(model.remoteModel, ansi.green)} (${size}, ${format.toUpperCase()})`);
    }
    console.log("");
  }

  if (payload.downloads.length) {
    const safeDownloads = payload.downloads.filter(entry => !entry.requiresHuggingFace);
    const requiresHf = payload.downloads.filter(entry => entry.requiresHuggingFace);
    const hubPort = cfg.port;
    const hardware = payload.hardware;
    const gpus = hardware?.gpu || [];
    const nvidiaGpu = gpus.find(g => /nvidia/i.test(g.name || ""));
    const bestGpu = gpus.reduce(
      (best, gpu) => {
        if (!gpu || typeof gpu.memoryBytes !== "number") return best;
        if (!best || gpu.memoryBytes > best.memoryBytes) return gpu;
        return best;
      },
      null
    );
    const describeCompatibility = entry => {
      const parts = [];
      if (entry.cudaOptimized) {
        if (nvidiaGpu) {
          parts.push(`CUDA-ready for ${nvidiaGpu.name}`);
        } else {
          parts.push("Needs NVIDIA CUDA runtime");
        }
      }
      if (entry.format) {
        parts.push(`${entry.format.toUpperCase()} format`);
      }
      const sizeGb = parseSizeGb(entry.size);
      if (sizeGb && bestGpu?.memoryBytes) {
        const vramGb = bestGpu.memoryBytes / (1024 * 1024 * 1024);
        if (sizeGb < vramGb * 0.6) {
          parts.push("fits comfortably in VRAM");
        } else if (sizeGb > vramGb) {
          parts.push("may stream/offload from RAM");
        }
      }
      return parts.join("; ");
    };
    const printEntry = (entry, idx, colorCode) => {
      const formatLabel = entry.format ? `${entry.format.toUpperCase()}` : "?";
      const cudaIcon = entry.cudaOptimized && nvidiaGpu ? color("⚡", ansi.yellow) : " ";
      const recommendedColor = entry.cudaOptimized && nvidiaGpu ? ansi.green : colorCode;
      console.log(
        `  ${cudaIcon} ${color(String(idx).padStart(2), ansi.gray)}. ${color(entry.displayName, recommendedColor)} (${entry.size}, ${formatLabel})`
      );
    };

    console.log(color("Available Downloads:", ansi.bold));
    let displayIndex = 1;
    let recommendedSelection = null;

    if (safeDownloads.length > 0) {
      safeDownloads.forEach(entry => {
        const info = { entry, index: displayIndex };
        lastCatalogSelections.set(String(displayIndex), info);
        lastCatalogSelections.set(entry.id, info);
        printEntry(entry, displayIndex, ansi.cyan);
        displayIndex += 1;
      });
      recommendedSelection = selectRecommendedDownload(safeDownloads, payload.hardware);
    }

    if (requiresHf.length > 0) {
      console.log(color("  Requires HuggingFace token:", ansi.yellow));
      requiresHf.forEach(entry => {
        const info = { entry, index: displayIndex };
        lastCatalogSelections.set(String(displayIndex), info);
        lastCatalogSelections.set(entry.id, info);
        printEntry(entry, displayIndex, ansi.gray);
        displayIndex += 1;
      });
    }

    console.log("");
    if (recommendedSelection) {
      const entry = recommendedSelection.entry;
      const selection = lastCatalogSelections.get(entry.id);
      if (selection) {
        console.log(color(`⭐ Recommended: #${selection.index} ${entry.displayName}`, ansi.green));
      }
    }
    console.log(color(`Type 'download <number>' to download a model`, ansi.gray));
  }

  // Hardware summary
  if (payload.hardware) {
    const gpu = (payload.hardware.gpu || []).find(g => /nvidia/i.test(g.name || ""));
    if (gpu) {
      const vram = gpu.memoryBytes ? `${(gpu.memoryBytes / 1_073_741_824).toFixed(1)} GB VRAM` : "";
      console.log(`${color("GPU:", ansi.bold)} ${gpu.name} ${vram ? `(${vram})` : ""}`);
    }
  }
  console.log("");
}

function logActive() {
  const active = getActiveModel();
  console.log("");
  if (!active) {
    console.log(`${color("[CMD]", ansi.gray)} Active model: ${color("none", ansi.green)}`);
  } else if (active.provider === "local") {
    console.log(
      `${color("[CMD]", ansi.gray)} Active model: ${color(
        `${active.id} (local ${cfg.providers.local.kind || "runtime"})`,
        ansi.green
      )}`
    );
  } else {
    console.log(`${color("[CMD]", ansi.gray)} Active model: ${color(active.id, ansi.green)}`);
  }
  console.log("");
}

function runKeygen(label) {
  return new Promise(resolve => {
    const args = ["./bin/keygen.mjs"];
    const trimmed = label?.trim();
    if (trimmed) {
      args.push("--label", trimmed);
    }
    console.log(color("[CMD] Generating API key...", ansi.yellow));
    const child = spawn("node", args, { stdio: ["ignore", "pipe", "pipe"] });
    child.stdout.on("data", chunk => {
      process.stdout.write(`${color("[KEYGEN]", ansi.cyan)} ${chunk.toString()}`);
    });
    child.stderr.on("data", chunk => {
      process.stdout.write(`${color("[KEYGEN]", ansi.red)} ${chunk.toString()}`);
    });
    child.on("close", code => {
      if (code === 0) {
        console.log(color("[CMD] Keygen complete. Copy the token above; it will not be shown again.", ansi.green));
      } else {
        console.log(color(`[CMD] Keygen exited with code ${code}.`, ansi.red));
      }
      resolve();
    });
  });
}

async function startModelDownload(entry) {
  console.log(color(`Starting download: ${entry.displayName || entry.id}`, ansi.cyan));
  const res = await fetch(`${cfg.internalBaseUrl}/api/models/download`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id: entry.id })
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.error || "Download request failed");
  }
  const jobId = data.job || "<pending>";
  console.log(color(`✓ Download started`, ansi.green));
  console.log(color(`  Job ID: ${jobId}`, ansi.gray));
  console.log(color(`  Check progress: status ${jobId}`, ansi.gray));
}

async function checkDownloadStatus(jobId) {
  if (!jobId) {
    console.log(color("Usage: status <jobId>", ansi.red));
    return;
  }
  try {
    const res = await fetch(`${cfg.internalBaseUrl}/api/models/downloads/${jobId}/status`);
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(data.error || "Status check failed");
    }
    const { name, status, downloaded, size, error } = data;
    console.log("");
    console.log(color(`Download: ${name || "unknown"}`, `${ansi.bold}${ansi.cyan}`));

    const statusIcon = status === "finished" ? color("✓", ansi.green) : status === "error" ? color("✗", ansi.red) : color("⋯", ansi.yellow);
    const statusColor = status === "finished" ? ansi.green : status === "error" ? ansi.red : ansi.yellow;
    console.log(`Status: ${statusIcon} ${color(status || "unknown", statusColor)}`);

    if (size && downloaded !== undefined) {
      const downloadedGb = (downloaded / (1024 * 1024 * 1024)).toFixed(2);
      const totalGb = (size / (1024 * 1024 * 1024)).toFixed(2);
      const percent = size > 0 ? ((downloaded / size) * 100).toFixed(1) : "0.0";
      const barLength = 30;
      const filled = Math.floor((downloaded / size) * barLength);
      const progressBar = color("█".repeat(filled), ansi.green) + color("░".repeat(barLength - filled), ansi.gray);
      console.log(`Progress: [${progressBar}] ${percent}%`);
      console.log(`Downloaded: ${downloadedGb} GB / ${totalGb} GB`);
    }

    if (error) {
      console.log(color(`Error: ${error}`, ansi.red));
    }
    console.log("");
  } catch (err) {
    console.log(color(`Failed to check status: ${err.message}`, ansi.red));
  }
}

function logToolingHelp() {
  const overview = buildModelOverviewPayload();
  const hardware = overview.hardware;
  const gpuNames = (hardware?.gpu || []).map(gpu => gpu.name).join(", ") || "detected GPU";
  const tooling = detectTooling();
  console.log("");
  console.log(color("[CMD] === Local tooling (CUDA / ONNX / PyTorch) ===", `${ansi.bold}${ansi.magenta}`));
  console.log(`${color("[CMD]", ansi.gray)} GPU(s): ${gpuNames}`);
  console.log(`${color("[CMD]", ansi.gray)} • ONNX Runtime GenAI: ${formatStatus(tooling.hasOnnx)}`);
  console.log(`${color("[CMD]", ansi.gray)} • PyTorch CUDA: ${formatStatus(tooling.hasTorch)}`);
  console.log(`${color("[CMD]", ansi.gray)} • CUDA toolkit / drivers: ${formatStatus(tooling.hasCuda)}`);
  console.log("");
  console.log(color("[CMD] Install / verify with:", ansi.bold));
  for (const line of getToolingInstructions()) {
    console.log(`${color("[CMD]", ansi.gray)} ${line}`);
  }
  console.log("");
}

function handleLine(input, rl) {
  const line = input.trim();
  if (!line) {
    rl.setPrompt(menuState.getPrompt());
    rl.prompt();
    return;
  }

  const [command, ...args] = line.split(/\s+/);
  const finish = () => {
    rl.setPrompt(menuState.getPrompt());
    rl.prompt();
  };

  // Route based on current context
  if (menuState.context === "root") {
    handleRootCommands(command, args, rl, finish);
  } else if (menuState.context === "model") {
    handleModelCommands(command, args, rl, finish);
  } else if (menuState.context === "model/avail") {
    handleAvailCommands(command, args, rl, finish);
  } else if (menuState.context === "model/download") {
    handleDownloadCommands(command, args, rl, finish);
  } else {
    finish();
  }
}

// Handle commands in root context
function handleRootCommands(command, args, rl, finish) {
  switch (command.toLowerCase()) {
    case "/help":
    case "help":
    case "?":
      showMainMenu();
      break;

    case "/model":
    case "model":
      menuState.context = "model";
      showModelMenu();
      break;

    case "/keygen":
    case "keygen":
      runKeygen(args.join(" "))
        .then(() => finish())
        .catch(err => {
          console.log(color(`[CMD] Keygen failed: ${err.message}`, ansi.red));
          finish();
        });
      return;

    case "/py":
    case "py":
    case "python":
      startPythonServer();
      break;

    case "/clear":
    case "clear":
      console.clear();
      break;

    // Legacy commands (backward compatibility)
    case "local":
      logLocal();
      break;
    case "cloud":
      logCloud();
      break;
    case "overview":
      logOverview();
      break;
    case "active":
      logActive();
      break;
    case "select":
      if (!args.length) {
        console.log(color("[CMD] Usage: select <model-id>", ansi.yellow));
        break;
      }
      try {
        const updated = setActiveModel(args[0]);
        console.log(color(`[CMD] ✓ Active model set to: ${updated.id}`, ansi.green));
      } catch (err) {
        console.log(color(`[CMD] Error: ${err.message}`, ansi.red));
      }
      break;
    case "tooling":
      logToolingHelp();
      break;
    case "onboard":
      runOnboardingWizard(rl)
        .then(() => finish())
        .catch(err => {
          console.log(color(`[CMD] Onboarding failed: ${err.message}`, ansi.red));
          finish();
        });
      return;
    case "exit":
    case "quit":
      console.log(color("[CMD] Press Ctrl+C to stop AI Hub.", ansi.yellow));
      break;

    default:
      console.log(color(`[CMD] Unknown command: ${command}`, ansi.red));
      console.log(color("Type '/help' to see available commands.", ansi.gray));
      break;
  }
  finish();
}

// Handle commands in model context
function handleModelCommands(command, args, rl, finish) {
  switch (command.toLowerCase()) {
    case "avail":
    case "available":
      menuState.context = "model/avail";
      modelCache = showAvailableModels();
      break;

    case "download":
      menuState.context = "model/download";
      modelCache = showDownloadModels();
      break;

    case "active":
      showActiveModel();
      break;

    case "back":
      menuState.context = "root";
      showMainMenu();
      break;

    default:
      console.log(color(`[CMD] Unknown command: ${command}`, ansi.red));
      console.log(color("Available: avail, download, active, back", ansi.gray));
      break;
  }
  finish();
}

// Handle commands in model/avail context
function handleAvailCommands(command, args, rl, finish) {
  switch (command.toLowerCase()) {
    case "select":
      if (!args.length) {
        console.log(color("[CMD] Usage: select <number>", ansi.yellow));
        break;
      }
      const modelIndex = parseInt(args[0]);
      const model = modelCache.get(modelIndex);
      if (!model) {
        console.log(color(`[CMD] No model found with index ${args[0]}`, ansi.red));
        console.log(color("Run 'avail' to see the list again", ansi.gray));
        break;
      }
      try {
        const updated = setActiveModel(model.id);
        console.log(color(`[CMD] ✓ Active model set to: ${updated.id} (${updated.provider})`, ansi.green));
        console.log("");
        // Refresh the view to show updated active indicator
        setTimeout(() => {
          modelCache = showAvailableModels();
          finish();
        }, 500);
        return;
      } catch (err) {
        console.log(color(`[CMD] Error: ${err.message}`, ansi.red));
      }
      break;

    case "back":
      menuState.context = "model";
      showModelMenu();
      break;

    case "refresh":
      modelCache = showAvailableModels();
      break;

    default:
      console.log(color(`[CMD] Unknown command: ${command}`, ansi.red));
      console.log(color("Available: select <number>, back, refresh", ansi.gray));
      break;
  }
  finish();
}

// Handle commands in model/download context
function handleDownloadCommands(command, args, rl, finish) {
  switch (command.toLowerCase()) {
    case "download":
      if (!args.length) {
        console.log(color("[CMD] Usage: download <number>", ansi.yellow));
        break;
      }
      const modelIndex = parseInt(args[0]);
      const model = modelCache.get(modelIndex);
      if (!model) {
        console.log(color(`[CMD] No model found with index ${args[0]}`, ansi.red));
        console.log(color("Run 'download' to see the list again", ansi.gray));
        break;
      }
      if (model.requiresHuggingFaceToken && !cfg.huggingFaceToken) {
        console.log(color(`[CMD] This model requires a HuggingFace token`, ansi.yellow));
        console.log(color("Set HUGGINGFACE_TOKEN in config.env before downloading.", ansi.gray));
        break;
      }
      startModelDownload(model)
        .then(() => {
          console.log(color("[CMD] ✓ Download complete!", ansi.green));
          finish();
        })
        .catch(err => {
          console.log(color(`[CMD] Download failed: ${err.message}`, ansi.red));
          finish();
        });
      return;

    case "back":
      menuState.context = "model";
      showModelMenu();
      break;

    case "refresh":
      modelCache = showDownloadModels();
      break;

    default:
      console.log(color(`[CMD] Unknown command: ${command}`, ansi.red));
      console.log(color("Available: download <number>, back, refresh", ansi.gray));
      break;
  }
  finish();
}

export function startCommandConsole() {
  if (started || !process.stdin.isTTY) {
    if (!process.stdin.isTTY) {
      console.log("[CMD] Terminal input not detected; interactive console disabled.");
    }
    started = true;
    return;
  }
  started = true;
  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
    prompt: "hub> "
  });
  const wizard = needsOnboarding()
    ? runOnboardingWizard(rl).catch(err => console.log(`[SETUP] ${err.message}`))
    : Promise.resolve();
  wizard.then(() => {
    warnLocalRuntimeTooling();
    showMainMenu(); // Show the main menu on startup
    rl.setPrompt(menuState.getPrompt());
    rl.prompt();
  });
  rl.on("line", line => handleLine(line, rl));
  rl.on("close", () => {
    console.log("[CMD] Console input closed. Hub still running.");
  });
}

function warnLocalRuntimeTooling() {
  if ((cfg.providers.local.kind || "").toLowerCase() === "onnx-genai") {
    const tooling = detectTooling();
    if (!tooling.hasOnnx || !tooling.hasCuda) {
      console.log(
        color(
          "[WARN] LOCAL_MODEL_KIND=onnx-genai but ONNX Runtime GenAI and/or CUDA are missing. Run 'tooling' for install commands.",
          ansi.red
        )
      );
    }
  }
}

process.on("exit", () => {
  if (pythonServerProcess && !pythonServerProcess.killed) {
    pythonServerProcess.kill("SIGTERM");
  }
});
