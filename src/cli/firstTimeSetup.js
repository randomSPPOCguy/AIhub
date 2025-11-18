import readline from "node:readline";
import { getHardwareSnapshot } from "../utils/hardwareInfo.js";
import { detectTooling, getToolingInstructions } from "../services/onboardingWizard.js";
import { selectRecommendedDownload } from "../services/localRecommendations.js";
import { readModelCatalog } from "../services/modelCatalog.js";
import { detectCUDAStack, getCUDAInstallInstructions } from "../utils/cudaDetection.js";

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

function ask(rl, question) {
  return new Promise(resolve => {
    rl.question(question, answer => resolve(answer.trim()));
  });
}

function formatBytes(bytes) {
  if (!bytes || Number.isNaN(bytes)) return "Unknown";
  const gb = bytes / (1024 * 1024 * 1024);
  return `${gb.toFixed(1)} GB`;
}

function detectInferenceEngine(hardware, tooling) {
  const gpus = hardware.gpu || [];
  const nvidiaGpu = gpus.find(g => /nvidia/i.test(g.name || ""));
  const amdGpu = gpus.find(g => /amd|radeon/i.test(g.name || ""));
  const intelGpu = gpus.find(g => /intel/i.test(g.name || ""));

  const recommendations = [];

  // NVIDIA GPU recommendations
  if (nvidiaGpu) {
    const vram = nvidiaGpu.memoryBytes || 0;
    const vramGB = vram / (1024 * 1024 * 1024);

    if (vramGB >= 6) {
      recommendations.push({
        priority: 1,
        engine: "ONNX Runtime GPU + CUDA",
        reason: `${nvidiaGpu.name} with ${formatBytes(nvidiaGpu.memoryBytes)} VRAM detected - Excellent for GPU inference`,
        instructions: [
          "1. CUDA Toolkit 12.4: https://developer.nvidia.com/cuda-downloads",
          "2. ONNX Runtime GPU: pip install onnxruntime-gpu==1.18.0 onnxruntime-genai",
          "3. PyTorch CUDA: pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124"
        ],
        status: tooling.hasCuda && tooling.hasOnnx ? "installed" : "recommended"
      });
    } else {
      recommendations.push({
        priority: 2,
        engine: "ONNX Runtime GPU (Lightweight)",
        reason: `${nvidiaGpu.name} with ${formatBytes(nvidiaGpu.memoryBytes)} VRAM - Use smaller quantized models`,
        instructions: [
          "1. CUDA Toolkit 12.4: https://developer.nvidia.com/cuda-downloads",
          "2. ONNX Runtime GPU: pip install onnxruntime-gpu==1.18.0 onnxruntime-genai"
        ],
        status: tooling.hasCuda && tooling.hasOnnx ? "installed" : "recommended"
      });
    }
  }

  // AMD GPU recommendations
  if (amdGpu) {
    recommendations.push({
      priority: 3,
      engine: "ONNX Runtime (DirectML)",
      reason: `${amdGpu.name} detected - DirectML support for AMD GPUs`,
      instructions: [
        "1. ONNX Runtime with DirectML: pip install onnxruntime-directml",
        "2. Note: DirectML has limited model support compared to CUDA"
      ],
      status: "recommended"
    });
  }

  // CPU-only fallback
  const cpuCores = hardware.cpu?.logicalCores || 0;
  const ramGB = hardware.memory?.totalBytes ? hardware.memory.totalBytes / (1024 * 1024 * 1024) : 0;

  if (cpuCores >= 8 && ramGB >= 16) {
    recommendations.push({
      priority: nvidiaGpu || amdGpu ? 4 : 1,
      engine: "ONNX Runtime CPU (Fallback)",
      reason: `${cpuCores} CPU cores, ${ramGB.toFixed(1)} GB RAM - Good for CPU inference`,
      instructions: [
        "1. ONNX Runtime CPU: pip install onnxruntime onnxruntime-genai",
        "2. Note: CPU inference is slower than GPU but works on any system"
      ],
      status: tooling.hasOnnx ? "installed" : "recommended"
    });
  } else {
    recommendations.push({
      priority: nvidiaGpu || amdGpu ? 5 : 2,
      engine: "ONNX Runtime CPU (Limited)",
      reason: `Limited resources - Use small quantized models only`,
      instructions: [
        "1. ONNX Runtime CPU: pip install onnxruntime onnxruntime-genai",
        "2. Warning: Low RAM/CPU may struggle with larger models"
      ],
      status: tooling.hasOnnx ? "installed" : "recommended"
    });
  }

  // Ollama recommendation for easy setup
  recommendations.push({
    priority: 6,
    engine: "Ollama (Easy Setup)",
    reason: "Easiest to install - Works on CPU and GPU automatically",
    instructions: [
      "1. Download Ollama from: https://ollama.com/download",
      "2. Run: ollama pull phi3",
      "3. Set LOCAL_MODEL_KIND=ollama in config.env"
    ],
    status: "optional"
  });

  return recommendations.sort((a, b) => a.priority - b.priority);
}

export async function runFirstTimeSetup() {
  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout
  });

  try {
    console.log("");
    console.log(color("═══════════════════════════════════════════════════════", ansi.cyan));
    console.log(color("         🚀 AI Hub First-Time Setup Wizard", `${ansi.bold}${ansi.cyan}`));
    console.log(color("═══════════════════════════════════════════════════════", ansi.cyan));
    console.log("");

    // Step 1: Detect hardware
    console.log(color("Step 1: Detecting your hardware...", ansi.bold));
    console.log("");
    const hardware = getHardwareSnapshot();

    // Display CPU
    const cpu = hardware.cpu;
    console.log(color("  CPU:", ansi.green));
    console.log(`    Model: ${cpu.model}`);
    console.log(`    Cores: ${cpu.logicalCores} logical (${cpu.estimatedPhysicalCores} physical)`);
    console.log(`    Architecture: ${cpu.architecture}`);
    console.log("");

    // Display GPU(s)
    const gpus = hardware.gpu || [];
    if (gpus.length > 0) {
      console.log(color("  GPU(s) Detected:", ansi.green));
      gpus.forEach((gpu, idx) => {
        const mem = gpu.memoryBytes ? formatBytes(gpu.memoryBytes) : "Unknown VRAM";
        console.log(`    ${idx + 1}. ${gpu.name} (${mem})`);
      });
    } else {
      console.log(color("  GPU: Not detected (CPU-only mode)", ansi.yellow));
    }
    console.log("");

    // Display RAM
    const ramGB = hardware.memory.totalBytes / (1024 * 1024 * 1024);
    const freeGB = hardware.memory.freeBytes / (1024 * 1024 * 1024);
    console.log(color("  RAM:", ansi.green));
    console.log(`    Total: ${ramGB.toFixed(1)} GB`);
    console.log(`    Available: ${freeGB.toFixed(1)} GB`);
    console.log("");

    await ask(rl, color("Press Enter to continue...", ansi.gray));

    // Step 2: Check existing tooling
    console.log("");
    console.log(color("Step 2: Checking installed inference tools...", ansi.bold));
    console.log("");
    const tooling = detectTooling();
    const cudaStack = detectCUDAStack();

    console.log(`  ${cudaStack.nvidiaDriver ? color("✓", ansi.green) : color("✗", ansi.red)} NVIDIA Driver`);
    console.log(`  ${cudaStack.cuda.installed ? color("✓", ansi.green) : color("✗", ansi.red)} CUDA Toolkit ${cudaStack.cuda.version || ""}`);
    console.log(`  ${cudaStack.cudnn.installed ? color("✓", ansi.green) : color("✗", ansi.red)} cuDNN Library ${cudaStack.cudnn.version || ""}`);
    console.log(`  ${tooling.hasOnnx ? color("✓", ansi.green) : color("✗", ansi.red)} ONNX Runtime GenAI`);
    console.log(`  ${tooling.hasTorch ? color("✓", ansi.green) : color("✗", ansi.red)} PyTorch with CUDA`);
    console.log("");

    if (tooling.allReady && cudaStack.ready) {
      console.log(color("  🎉 All recommended tools are installed!", ansi.green));
    } else {
      if (cudaStack.missingComponents.length > 0) {
        console.log(color(`  ⚠️  Missing CUDA components: ${cudaStack.missingComponents.join(", ")}`, ansi.yellow));
      }
      if (!tooling.hasOnnx || !tooling.hasTorch) {
        console.log(color("  ⚠️  Missing Python inference libraries", ansi.yellow));
      }
      console.log("");
      console.log(color("  We'll help you install them...", ansi.cyan));
    }
    console.log("");

    await ask(rl, color("Press Enter to continue...", ansi.gray));

    // Step 3: Recommend inference engines
    console.log("");
    console.log(color("Step 3: Recommended Inference Engines for Your System", ansi.bold));
    console.log("");

    const recommendations = detectInferenceEngine(hardware, tooling);

    recommendations.slice(0, 3).forEach((rec, idx) => {
      const statusBadge = rec.status === "installed"
        ? color("[INSTALLED]", ansi.green)
        : rec.status === "recommended"
        ? color("[RECOMMENDED]", ansi.yellow)
        : color("[OPTIONAL]", ansi.gray);

      console.log(color(`  ${idx + 1}. ${rec.engine}`, ansi.cyan) + ` ${statusBadge}`);
      console.log(color(`     ${rec.reason}`, ansi.gray));
      console.log("");
    });

    const choice = await ask(rl, color("Which inference engine would you like to install? (1-3, or 'skip'): ", ansi.yellow));

    if (choice !== "skip" && choice !== "") {
      const selectedIdx = parseInt(choice) - 1;
      if (selectedIdx >= 0 && selectedIdx < 3) {
        const selected = recommendations[selectedIdx];
        console.log("");
        console.log(color(`Installing: ${selected.engine}`, ansi.bold));
        console.log("");

        // If NVIDIA GPU selected, show detailed CUDA stack requirements
        if (selected.engine.includes("CUDA") && !cudaStack.ready) {
          console.log(color("⚠️  CUDA Stack Installation Required", ansi.yellow));
          console.log("");
          const cudaInstructions = getCUDAInstallInstructions(cudaStack);

          cudaInstructions.forEach((inst, idx) => {
            console.log(color(`${idx + 1}. ${inst.component}`, ansi.cyan));
            inst.steps.forEach(step => {
              console.log(color(`   ${step}`, ansi.gray));
            });
            console.log("");
          });
        }

        console.log(color("Python Libraries Installation:", ansi.green));
        selected.instructions.forEach(instruction => {
          console.log(color(`  ${instruction}`, ansi.gray));
        });
        console.log("");
        await ask(rl, color("Press Enter once you've completed the installation above...", ansi.yellow));
      }
    }

    // Step 4: Recommend models based on hardware
    console.log("");
    console.log(color("Step 4: Recommended Models for Your Hardware", ansi.bold));
    console.log("");

    const catalog = readModelCatalog().filter(entry => !entry.requiresHuggingFace);
    const modelRec = selectRecommendedDownload(catalog, hardware);

    if (modelRec?.entry) {
      console.log(color("  Recommended Model:", ansi.green));
      console.log(`    Name: ${modelRec.entry.displayName || modelRec.entry.name}`);
      console.log(`    Size: ${modelRec.entry.size}`);
      console.log(`    Format: ${modelRec.entry.format?.toUpperCase() || "Unknown"}`);
      if (modelRec.nvidiaGpu) {
        console.log(`    Optimized for: ${modelRec.nvidiaGpu.name}`);
      }
      console.log("");

      const download = await ask(rl, color(`Would you like to download this model now? (Y/n): `, ansi.yellow));

      if (!download.toLowerCase().startsWith("n")) {
        console.log("");
        console.log(color("  To download this model:", ansi.cyan));
        console.log(color(`    1. Start AI Hub: npm start`, ansi.gray));
        console.log(color(`    2. Run command: /model download 1`, ansi.gray));
        console.log("");
      }
    } else {
      console.log(color("  No models available in catalog yet.", ansi.yellow));
    }

    // Step 5: Summary and next steps
    console.log("");
    console.log(color("═══════════════════════════════════════════════════════", ansi.cyan));
    console.log(color("         ✅ Setup Complete!", `${ansi.bold}${ansi.green}`));
    console.log(color("═══════════════════════════════════════════════════════", ansi.cyan));
    console.log("");
    console.log(color("Next Steps:", ansi.bold));
    console.log(color("  1. Copy config.env.example to config.env", ansi.gray));
    console.log(color("  2. Add your API keys to config.env (optional)", ansi.gray));
    console.log(color("  3. Start AI Hub: npm start", ansi.gray));
    console.log(color("  4. Run /help to see all available commands", ansi.gray));
    console.log(color("  5. Run /model to manage models", ansi.gray));
    console.log(color("  6. Use 'temp' command to adjust AI temperature", ansi.gray));
    console.log("");

  } finally {
    rl.close();
  }
}

export { detectInferenceEngine };
