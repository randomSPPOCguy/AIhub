#!/usr/bin/env node

/**
 * CUDA Stack Diagnostic Tool
 *
 * Checks for NVIDIA drivers, CUDA Toolkit, and cuDNN installation.
 * Provides detailed instructions for missing components.
 */

import { detectCUDAStack, getCUDAInstallInstructions } from "../src/utils/cudaDetection.js";
import { getHardwareSnapshot } from "../src/utils/hardwareInfo.js";

const ansi = {
  reset: "\x1b[0m",
  bold: "\x1b[1m",
  cyan: "\x1b[36m",
  yellow: "\x1b[33m",
  green: "\x1b[32m",
  gray: "\x1b[90m",
  red: "\x1b[31m"
};

const color = (text, code) => `${code}${text}${ansi.reset}`;

console.log("");
console.log(color("═══════════════════════════════════════════", ansi.cyan));
console.log(color("     🔍 CUDA Stack Diagnostic Tool", `${ansi.bold}${ansi.cyan}`));
console.log(color("═══════════════════════════════════════════", ansi.cyan));
console.log("");

// Check hardware
const hardware = getHardwareSnapshot();
const gpus = hardware.gpu || [];
const nvidiaGpu = gpus.find(g => /nvidia/i.test(g.name || ""));

console.log(color("Hardware Detection:", ansi.bold));
if (nvidiaGpu) {
  const vram = nvidiaGpu.memoryBytes
    ? `${(nvidiaGpu.memoryBytes / (1024 * 1024 * 1024)).toFixed(1)} GB VRAM`
    : "VRAM unknown";
  console.log(`  ${color("✓", ansi.green)} NVIDIA GPU: ${nvidiaGpu.name} (${vram})`);
} else {
  console.log(`  ${color("✗", ansi.yellow)} No NVIDIA GPU detected`);
  if (gpus.length > 0) {
    gpus.forEach(gpu => {
      console.log(`     - ${gpu.name} (not CUDA-compatible)`);
    });
  }
}
console.log("");

// Check CUDA stack
const cudaStack = detectCUDAStack();

console.log(color("CUDA Stack Components:", ansi.bold));
console.log("");

// NVIDIA Driver
if (cudaStack.nvidiaDriver) {
  console.log(`  ${color("✓", ansi.green)} NVIDIA Driver: Installed`);
} else {
  console.log(`  ${color("✗", ansi.red)} NVIDIA Driver: Not detected`);
}

// CUDA Toolkit
if (cudaStack.cuda.installed) {
  console.log(`  ${color("✓", ansi.green)} CUDA Toolkit: ${cudaStack.cuda.version || "Installed"}`);
  if (cudaStack.cuda.path) {
    console.log(`     Path: ${color(cudaStack.cuda.path, ansi.gray)}`);
  }
} else {
  console.log(`  ${color("✗", ansi.red)} CUDA Toolkit: Not installed`);
}

// cuDNN
if (cudaStack.cudnn.installed) {
  console.log(`  ${color("✓", ansi.green)} cuDNN Library: ${cudaStack.cudnn.version || "Installed"}`);
  if (cudaStack.cudnn.path) {
    console.log(`     Path: ${color(cudaStack.cudnn.path, ansi.gray)}`);
  }
} else {
  console.log(`  ${color("✗", ansi.red)} cuDNN Library: Not installed`);
  console.log(`     ${color("Missing cudnn64_9.dll or cudnn64_8.dll", ansi.yellow)}`);
}

console.log("");

// Overall status
if (cudaStack.ready) {
  console.log(color("═══════════════════════════════════════════", ansi.green));
  console.log(color("  ✅ CUDA Stack Complete - Ready for GPU inference!", ansi.green));
  console.log(color("═══════════════════════════════════════════", ansi.green));
  console.log("");
  console.log(color("You can now use ONNX Runtime GPU with CUDA acceleration.", ansi.gray));
} else {
  console.log(color("═══════════════════════════════════════════", ansi.yellow));
  console.log(color("  ⚠️  CUDA Stack Incomplete", ansi.yellow));
  console.log(color("═══════════════════════════════════════════", ansi.yellow));
  console.log("");

  if (cudaStack.missingComponents.length > 0) {
    console.log(color("Missing Components:", ansi.red));
    cudaStack.missingComponents.forEach(comp => {
      console.log(`  - ${comp}`);
    });
    console.log("");
  }

  console.log(color("Installation Instructions:", ansi.bold));
  console.log("");

  const instructions = getCUDAInstallInstructions(cudaStack);
  instructions.forEach((inst, idx) => {
    console.log(color(`${idx + 1}. ${inst.component}`, `${ansi.bold}${ansi.cyan}`));
    inst.steps.forEach(step => {
      console.log(color(`   ${step}`, ansi.gray));
    });
    console.log("");
  });

  console.log(color("Alternative: Use CPU Inference", ansi.yellow));
  console.log("");
  console.log(color("If you don't want to install CUDA components, you can use CPU inference:", ansi.gray));
  console.log(color("  1. pip install onnxruntime onnxruntime-genai", ansi.gray));
  console.log(color("  2. In config.env, ensure LOCAL_MODEL_KIND=onnx-genai", ansi.gray));
  console.log(color("  3. Restart AI Hub", ansi.gray));
  console.log("");
}

console.log(color("Need help? Check SETUP_GUIDE.md for detailed instructions.", ansi.cyan));
console.log("");
