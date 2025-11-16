import fetch from "node-fetch";
import { execSync } from "node:child_process";
import { getState, setState } from "./hubState.js";
import { buildModelOverviewPayload } from "../services/modelSummary.js";
import { readModelCatalog } from "./modelCatalog.js";
import { selectRecommendedDownload } from "./localRecommendations.js";
import { cfg } from "../config.js";

const ONBOARDING_KEY = "onboarding_completed";

function ask(rl, question) {
  return new Promise(resolve => {
    rl.question(question, answer => resolve(answer.trim()));
  });
}

export function needsOnboarding() {
  return !Boolean(getState(ONBOARDING_KEY, false));
}

export async function runOnboardingWizard(rl) {
  console.log("");
  console.log("[SETUP] Welcome! Let's configure local CUDA/ONNX tooling for the best model experience.");
  const overview = buildModelOverviewPayload();
  console.log(
    `[SETUP] Detected CPU: ${overview.hardware?.cpu?.model || "Unknown"}, GPU(s): ${
      (overview.hardware?.gpu || []).map(g => `${g.name} (${formatBytes(g.memoryBytes)})`).join(", ") ||
      "None"
    }`
  );
  console.log("");
  const detected = detectTooling();
  printDetectionSummary(detected);
  let answer;
  if (!detected.allReady) {
    printToolingInstructions();
    answer = await ask(
      rl,
      "[SETUP] Press Enter once you've installed the dependencies above (or type 'skip' to continue without installing): "
    );
    if (!/^skip$/i.test(answer)) {
      console.log("[SETUP] Continuing with setup; you can re-run 'tooling' later if needed.");
    } else {
      console.log("[SETUP] Skipping installs for now.");
    }
  } else {
    answer = await ask(rl, "[SETUP] ONNX Runtime + CUDA + PyTorch detected. Proceed with this environment? (Y/n) ");
    if (/^n(o)?$/i.test(answer)) {
      printToolingInstructions();
      await ask(rl, "[SETUP] Press Enter to continue once you're ready: ");
    }
  }

  const downloads = readModelCatalog().filter(entry => !entry.requiresHuggingFace);
  const recommendation = selectRecommendedDownload(downloads, overview.hardware);
  if (recommendation?.entry) {
    console.log("");
    console.log(
      `[SETUP] Recommended model for your GPU: ${recommendation.entry.displayName || recommendation.entry.name || recommendation.entry.id}`
    );
    console.log(
      `[SETUP] Rationale: ${recommendation.entry.format?.toUpperCase() || "unknown"} format ${
        recommendation.entry.cudaOptimized ? "(CUDA-optimized)" : ""
      } sized for ${recommendation.nvidiaGpu?.name || recommendation.bestGpu?.name || "your hardware"}`
    );
    answer = await ask(rl, `[SETUP] Would you like to download ${recommendation.entry.id} now? (Y/n) `);
    if (!/^n(o)?$/i.test(answer)) {
      await requestDownload(recommendation.entry);
    }
  } else {
    console.log("[SETUP] No local catalog entries available yet. Use 'local' later to refresh.");
  }

  setState(ONBOARDING_KEY, true);
  console.log("[SETUP] Onboarding finished. Type 'help' for the command list anytime, or 'tooling' for setup commands.");
  console.log("");
}

export function getToolingInstructions() {
  return [
    "1) CUDA Toolkit 12.4 for your NVIDIA GPU: https://developer.nvidia.com/cuda-downloads",
    "2) ONNX Runtime GPU + GenAI: pip install onnxruntime-gpu==1.18.0 onnxruntime-genai && python -m onnxruntime_genai.convert --help",
    "3) PyTorch CUDA wheels: pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124",
    "4) Optional HF helpers: pip install huggingface_hub optimum && huggingface-cli download <model> --include *.onnx"
  ];
}

function printToolingInstructions() {
  console.log("");
  console.log("[SETUP] Install the following (one-time):");
  for (const line of getToolingInstructions()) {
    console.log(` ${line}`);
  }
  console.log("");
}

export function detectTooling() {
  const hasOnnxGenAI = checkPythonModule("onnxruntime_genai");
  const hasOnnxGpu = hasOnnxGenAI || checkPythonModule("onnxruntime");
  const hasTorch = checkPythonModule("torch");
  const hasCudaToolkit = commandExists("nvcc --version") || commandExists("nvidia-smi");
  return {
    hasOnnx: hasOnnxGpu,
    hasTorch,
    hasCuda: hasCudaToolkit,
    allReady: hasOnnxGpu && hasTorch && hasCudaToolkit
  };
}

function printDetectionSummary(info) {
  console.log("[SETUP] Dependency check:");
  console.log(`  • ONNX Runtime (GPU/GenAI): ${info.hasOnnx ? "Detected" : "Missing"}`);
  console.log(`  • PyTorch (CUDA wheels): ${info.hasTorch ? "Detected" : "Missing"}`);
  console.log(`  • CUDA Toolkit / NVIDIA drivers: ${info.hasCuda ? "Detected" : "Missing"}`);
  console.log("");
}

function commandExists(command) {
  try {
    execSync(command, { stdio: "ignore" });
    return true;
  } catch {
    return false;
  }
}

function checkPythonModule(moduleName) {
  try {
    execSync(`python -c "import ${moduleName}"`, { stdio: "ignore" });
    return true;
  } catch {
    return false;
  }
}

async function requestDownload(entry) {
  console.log(`[SETUP] Requesting download for ${entry.displayName || entry.id}...`);
  const res = await fetch(`${cfg.internalBaseUrl}/api/models/download`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id: entry.id })
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    console.log(
      `[SETUP] Download for ${entry.id} failed (${res.status}): ${data.error || data.message || "unknown error"}`
    );
    return;
  }
  console.log(
    `[SETUP] Download job ${data.job || "<pending>"} started for ${entry.id}. Check /api/models/downloads/${data.job}/status for progress.`
  );
}

function formatBytes(bytes) {
  if (!bytes || Number.isNaN(bytes)) return "unknown VRAM";
  return `${Math.round((bytes / (1024 * 1024 * 1024)) * 10) / 10} GB`;
}
