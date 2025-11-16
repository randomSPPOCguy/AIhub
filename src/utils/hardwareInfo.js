import os from "node:os";
import fs from "node:fs";
import path from "node:path";
import { execSync } from "node:child_process";

let cachedInfo = null;
let lastFetch = 0;
const CACHE_WINDOW_MS = 5 * 60 * 1000;

function safeExec(command) {
  try {
    return execSync(command, { encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] }).trim();
  } catch {
    return "";
  }
}

function parseDxDiagGpus() {
  const dxDiagPath = path.resolve("./DxDiag.txt");
  if (!fs.existsSync(dxDiagPath)) return [];
  const text = fs.readFileSync(dxDiagPath, "utf8");
  const lines = text.split(/\r?\n/);
  const gpus = [];
  let current = null;
  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (!line) continue;
    if (line.startsWith("Card name:")) {
      if (current && current.name) {
        gpus.push(current);
      }
      current = { name: line.split(":")[1]?.trim() || "Unknown GPU" };
      continue;
    }
    if (!current) continue;
    if (line.startsWith("Dedicated Memory:")) {
      const match = line.match(/Dedicated Memory:\s*([\d.,]+)\s*MB/i);
      if (match) {
        const megabytes = parseFloat(match[1].replace(/,/g, ""));
        if (!Number.isNaN(megabytes)) {
          current.memoryBytes = Math.round(megabytes * 1024 * 1024);
        }
      }
      continue;
    }
    if (line.startsWith("Display Memory:") && !current.memoryBytes) {
      const match = line.match(/Display Memory:\s*([\d.,]+)\s*MB/i);
      if (match) {
        const megabytes = parseFloat(match[1].replace(/,/g, ""));
        if (!Number.isNaN(megabytes)) {
          current.memoryBytes = Math.round(megabytes * 1024 * 1024);
        }
      }
    }
  }
  if (current && current.name) {
    gpus.push(current);
  }
  return gpus;
}

function detectWindowsGpus() {
  const dxDiag = parseDxDiagGpus();
  if (dxDiag.length) return dxDiag;
  const script =
    "Get-CimInstance Win32_VideoController | Select-Object Name,AdapterRAM | ConvertTo-Json";
  const output = safeExec(`powershell -NoProfile -Command "${script}"`);
  if (!output) return [];
  let parsed;
  try {
    parsed = JSON.parse(output);
  } catch {
    return [];
  }
  const entries = Array.isArray(parsed) ? parsed : [parsed];
  return entries
    .map(entry => ({
      name: typeof entry.Name === "string" ? entry.Name.trim() : "Unknown GPU",
      memoryBytes:
        typeof entry.AdapterRAM === "number"
          ? entry.AdapterRAM
          : parseInt(entry.AdapterRAM, 10) || null
    }))
    .filter(entry => entry.name);
}

function detectDarwinGpus() {
  const output = safeExec("/usr/sbin/system_profiler SPDisplaysDataType -json");
  if (!output) return [];
  try {
    const parsed = JSON.parse(output);
    const displays = parsed.SPDisplaysDataType || [];
    return displays.flatMap(display => {
      const gpus = display.spdisplays_ndrvs || [];
      return gpus.map(gpu => ({
        name: gpu._name || "Unknown GPU",
        memoryBytes: gpu._spdisplays_vram || null
      }));
    });
  } catch {
    return [];
  }
}

function detectLinuxGpus() {
  const results = [];
  const nvidia = safeExec(
    "nvidia-smi --query-gpu=name,memory.total --format=csv,noheader,nounits"
  );
  if (nvidia) {
    for (const line of nvidia.split("\n")) {
      const [name, memory] = line.split(",").map(part => part.trim());
      if (!name) continue;
      const memoryBytes = memory ? parseInt(memory, 10) * 1024 * 1024 : null;
      results.push({ name, memoryBytes });
    }
  }
  if (results.length) return results;

  const lspci = safeExec("lspci | grep -i 'vga\\|3d\\|display'");
  if (!lspci) return [];
  return lspci.split("\n").map(line => ({
    name: line.replace(/^.+?:\s*/, "").trim() || "Unknown GPU",
    memoryBytes: null
  }));
}

function detectGpus() {
  switch (process.platform) {
    case "win32":
      return detectWindowsGpus();
    case "darwin":
      return detectDarwinGpus();
    default:
      return detectLinuxGpus();
  }
}

function summarizeCpu() {
  const cpus = os.cpus() || [];
  const logical = cpus.length;
  const model = cpus[0]?.model || "Unknown CPU";
  const physical = cpus.length ? Math.max(1, Math.round(logical / 2)) : null;
  return {
    model,
    logicalCores: logical,
    estimatedPhysicalCores: physical,
    architecture: os.arch()
  };
}

export function getHardwareSnapshot() {
  const now = Date.now();
  if (cachedInfo && now - lastFetch < CACHE_WINDOW_MS) {
    return cachedInfo;
  }
  const info = {
    cpu: summarizeCpu(),
    gpu: detectGpus(),
    memory: {
      totalBytes: os.totalmem(),
      freeBytes: os.freemem()
    }
  };
  cachedInfo = info;
  lastFetch = now;
  return info;
}
