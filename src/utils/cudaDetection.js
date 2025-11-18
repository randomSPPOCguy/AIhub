import { execSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

function safeExec(command) {
  try {
    return execSync(command, { encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] }).trim();
  } catch {
    return "";
  }
}

/**
 * Detect CUDA Toolkit installation and version
 */
export function detectCUDAToolkit() {
  const result = {
    installed: false,
    version: null,
    path: null,
    nvccVersion: null
  };

  // Try nvcc --version
  const nvccOutput = safeExec("nvcc --version");
  if (nvccOutput) {
    result.installed = true;
    const match = nvccOutput.match(/release\s+([\d.]+)/i);
    if (match) {
      result.nvccVersion = match[1];
      result.version = match[1];
    }
  }

  // Try to find CUDA installation path on Windows
  if (process.platform === "win32") {
    const commonPaths = [
      "C:\\Program Files\\NVIDIA GPU Computing Toolkit\\CUDA",
      "C:\\Program Files (x86)\\NVIDIA GPU Computing Toolkit\\CUDA",
      process.env.CUDA_PATH
    ].filter(Boolean);

    for (const basePath of commonPaths) {
      if (fs.existsSync(basePath)) {
        try {
          const versions = fs.readdirSync(basePath);
          // Find the highest version
          const versionDirs = versions.filter(v => /^v?\d+\.\d+/.test(v));
          if (versionDirs.length > 0) {
            result.installed = true;
            result.path = path.join(basePath, versionDirs[versionDirs.length - 1]);
            if (!result.version) {
              const versionMatch = versionDirs[versionDirs.length - 1].match(/(\d+\.\d+)/);
              if (versionMatch) result.version = versionMatch[1];
            }
          }
        } catch {
          // Ignore read errors
        }
      }
    }
  }

  // Try nvidia-smi as fallback
  if (!result.installed) {
    const smiOutput = safeExec("nvidia-smi");
    if (smiOutput && smiOutput.includes("CUDA Version")) {
      result.installed = true;
      const match = smiOutput.match(/CUDA Version:\s+([\d.]+)/i);
      if (match) {
        result.version = match[1];
      }
    }
  }

  return result;
}

/**
 * Detect cuDNN installation
 */
export function detectCuDNN() {
  const result = {
    installed: false,
    version: null,
    path: null,
    dllFound: false
  };

  if (process.platform !== "win32") {
    // Linux/Mac detection would go here
    return result;
  }

  // Windows: Check for cudnn DLL files
  const cudaInfo = detectCUDAToolkit();
  const searchPaths = [];

  if (cudaInfo.path) {
    searchPaths.push(path.join(cudaInfo.path, "bin"));
  }

  // Also check common installation paths
  const commonPaths = [
    "C:\\Program Files\\NVIDIA GPU Computing Toolkit\\CUDA\\v12.4\\bin",
    "C:\\Program Files\\NVIDIA GPU Computing Toolkit\\CUDA\\v12.3\\bin",
    "C:\\Program Files\\NVIDIA GPU Computing Toolkit\\CUDA\\v12.2\\bin",
    "C:\\Program Files\\NVIDIA\\CUDNN\\v9.0\\bin",
    "C:\\Program Files\\NVIDIA\\CUDNN\\v8.9\\bin",
    process.env.CUDNN_PATH ? path.join(process.env.CUDNN_PATH, "bin") : null
  ].filter(Boolean);

  searchPaths.push(...commonPaths);

  // Check PATH environment variable
  const pathDirs = (process.env.PATH || "").split(";").filter(Boolean);
  searchPaths.push(...pathDirs);

  // Look for cudnn DLL files
  const cudnnDlls = [
    "cudnn64_9.dll",  // cuDNN v9
    "cudnn64_8.dll",  // cuDNN v8
    "cudnn_ops_infer64_9.dll",
    "cudnn_ops_infer64_8.dll"
  ];

  for (const searchPath of searchPaths) {
    if (!fs.existsSync(searchPath)) continue;

    try {
      const files = fs.readdirSync(searchPath);
      for (const dll of cudnnDlls) {
        if (files.includes(dll)) {
          result.installed = true;
          result.dllFound = true;
          result.path = searchPath;

          // Extract version from DLL name
          const versionMatch = dll.match(/cudnn64_(\d+)\.dll/);
          if (versionMatch) {
            result.version = `v${versionMatch[1]}.x`;
          }
          return result;
        }
      }
    } catch {
      // Ignore read errors
    }
  }

  return result;
}

/**
 * Comprehensive CUDA + cuDNN detection
 */
export function detectCUDAStack() {
  const cuda = detectCUDAToolkit();
  const cudnn = detectCuDNN();
  const nvidiaDriver = safeExec("nvidia-smi") !== "";

  return {
    nvidiaDriver: nvidiaDriver,
    cuda: cuda,
    cudnn: cudnn,
    ready: cuda.installed && cudnn.installed && nvidiaDriver,
    missingComponents: [
      !nvidiaDriver ? "NVIDIA Driver" : null,
      !cuda.installed ? "CUDA Toolkit" : null,
      !cudnn.installed ? "cuDNN Library" : null
    ].filter(Boolean)
  };
}

/**
 * Get installation instructions for missing components
 */
export function getCUDAInstallInstructions(detection) {
  const instructions = [];

  if (!detection.nvidiaDriver) {
    instructions.push({
      component: "NVIDIA Driver",
      priority: 1,
      steps: [
        "Download from: https://www.nvidia.com/Download/index.aspx",
        "Install the latest Game Ready or Studio driver for your GPU",
        "Restart your computer after installation"
      ]
    });
  }

  if (!detection.cuda.installed) {
    instructions.push({
      component: "CUDA Toolkit",
      priority: 2,
      steps: [
        "Download CUDA 12.4 from: https://developer.nvidia.com/cuda-downloads",
        "Run the installer and follow the installation wizard",
        "Choose 'Express' installation for all components",
        "Verify installation: nvcc --version"
      ]
    });
  }

  if (!detection.cudnn.installed) {
    instructions.push({
      component: "cuDNN Library",
      priority: 3,
      steps: [
        "Download cuDNN v9.x for CUDA 12.x from: https://developer.nvidia.com/cudnn-downloads",
        "(Requires free NVIDIA Developer account)",
        "Extract the ZIP file",
        "Copy files to CUDA installation:",
        "  - cudnn/bin/*.dll → C:\\Program Files\\NVIDIA GPU Computing Toolkit\\CUDA\\v12.4\\bin\\",
        "  - cudnn/include/*.h → C:\\Program Files\\NVIDIA GPU Computing Toolkit\\CUDA\\v12.4\\include\\",
        "  - cudnn/lib/*.lib → C:\\Program Files\\NVIDIA GPU Computing Toolkit\\CUDA\\v12.4\\lib\\x64\\",
        "Add to PATH: C:\\Program Files\\NVIDIA GPU Computing Toolkit\\CUDA\\v12.4\\bin"
      ]
    });
  }

  return instructions.sort((a, b) => a.priority - b.priority);
}
