import os from "node:os";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
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

const MODULE_DIR = path.dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = path.resolve(MODULE_DIR, "..", "..");

function collectDxDiagCandidates() {
  const candidates = [];
  const seen = new Set();
  const addCandidate = candidate => {
    if (!candidate) return;
    const resolved = path.resolve(candidate);
    if (seen.has(resolved)) return;
    seen.add(resolved);
    candidates.push(resolved);
  };

  addCandidate(process.env.DXDIAG_PATH || process.env.DXDIAG_TXT);
  addCandidate(path.join(process.cwd(), "DxDiag.txt"));
  addCandidate(path.join(PROJECT_ROOT, "DxDiag.txt"));
  const repoParent = path.dirname(PROJECT_ROOT);
  addCandidate(path.join(repoParent, "DxDiag.txt"));

  const dirsToScan = [process.cwd(), PROJECT_ROOT, repoParent];
  for (const dir of dirsToScan) {
    try {
      const entries = fs.readdirSync(dir, { withFileTypes: true });
      for (const entry of entries) {
        if (!entry.isDirectory()) continue;
        addCandidate(path.join(dir, entry.name, "DxDiag.txt"));
      }
    } catch {
      // Ignore directories we cannot read
    }
  }

  return candidates;
}

function parseDxDiagGpusFromFile(dxDiagPath) {
  if (!dxDiagPath || !fs.existsSync(dxDiagPath)) return [];
  let text;
  try {
    text = fs.readFileSync(dxDiagPath, "utf8");
  } catch {
    return [];
  }
  const lines = text.split(/\r?\n/);
  const gpus = [];
  let current = null;
  const pushCurrent = () => {
    if (!current || !current.name) return;
    if (typeof current.dedicatedBytes === "number") {
      current.memoryBytes = current.dedicatedBytes;
    } else if (typeof current.displayBytes === "number") {
      current.memoryBytes = current.displayBytes;
    }
    gpus.push({
      name: current.name,
      memoryBytes: typeof current.memoryBytes === "number" ? current.memoryBytes : null
    });
  };
  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (!line) continue;
    if (line.startsWith("Card name:")) {
      if (current) pushCurrent();
      current = { name: line.split(":")[1]?.trim() || "Unknown GPU" };
      continue;
    }
    if (!current) continue;
    if (line.startsWith("Dedicated Memory:")) {
      const match = line.match(/Dedicated Memory:\s*([\d.,]+)\s*MB/i);
      if (match) {
        const megabytes = parseFloat(match[1].replace(/,/g, ""));
        if (!Number.isNaN(megabytes)) {
          current.dedicatedBytes = Math.round(megabytes * 1024 * 1024);
        }
      }
      continue;
    }
    if (line.startsWith("Display Memory:")) {
      const match = line.match(/Display Memory:\s*([\d.,]+)\s*MB/i);
      if (match) {
        const megabytes = parseFloat(match[1].replace(/,/g, ""));
        if (!Number.isNaN(megabytes)) {
          current.displayBytes = Math.round(megabytes * 1024 * 1024);
        }
      }
    }
  }
  if (current) pushCurrent();
  return gpus;
}

function detectDxDiagGpus() {
  const candidates = collectDxDiagCandidates();
  for (const candidate of candidates) {
    const gpus = parseDxDiagGpusFromFile(candidate);
    if (gpus.length) {
      return gpus;
    }
  }
  return [];
}

function sanitizeMemoryBytes(value) {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value > 0 ? value : null;
  }
  if (typeof value === "string" && value.trim()) {
    const parsed = parseInt(value.replace(/[^0-9]/g, ""), 10);
    return Number.isNaN(parsed) ? null : parsed;
  }
  return null;
}

function readWmiGpuData() {
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
    .map(entry => {
      const name = typeof entry.Name === "string" ? entry.Name.trim() : "Unknown GPU";
      const memoryBytes = sanitizeMemoryBytes(entry.AdapterRAM);
      return { name, memoryBytes };
    })
    .filter(entry => entry.name);
}

function pickBetterMemory(existing, candidate) {
  if (typeof candidate !== "number" || Number.isNaN(candidate) || candidate <= 0) {
    return typeof existing === "number" && existing > 0 ? existing : null;
  }
  if (typeof existing !== "number" || Number.isNaN(existing) || existing <= 0) {
    return candidate;
  }
  return candidate > existing ? candidate : existing;
}

function vendorScore(name = "") {
  const lower = name.toLowerCase();
  if (lower.includes("nvidia")) return 3;
  if (lower.includes("amd") || lower.includes("radeon")) return 2;
  if (lower.includes("intel")) return 1;
  return 0;
}

function sortGpuEntries(entries) {
  return entries
    .map((entry, idx) => ({
      ...entry,
      memoryBytes:
        typeof entry.memoryBytes === "number" && entry.memoryBytes > 0 ? entry.memoryBytes : null,
      __idx: idx
    }))
    .sort((a, b) => {
      const vendorDiff = vendorScore(b.name) - vendorScore(a.name);
      if (vendorDiff !== 0) return vendorDiff;
      const memoryDiff = (b.memoryBytes || 0) - (a.memoryBytes || 0);
      if (memoryDiff !== 0) return memoryDiff;
      return a.__idx - b.__idx;
    })
    .map(({ __idx, ...entry }) => entry);
}

function mergeGpuEntries(primary, secondary) {
  const byName = new Map();
  const upsert = entry => {
    if (!entry || !entry.name) return;
    const name = entry.name.trim() || "Unknown GPU";
    const key = name.toLowerCase();
    if (!byName.has(key)) {
      byName.set(key, {
        name,
        memoryBytes:
          typeof entry.memoryBytes === "number" && entry.memoryBytes > 0 ? entry.memoryBytes : null
      });
      return;
    }
    const existing = byName.get(key);
    existing.memoryBytes = pickBetterMemory(existing.memoryBytes, entry.memoryBytes);
  };

  primary.forEach(upsert);
  secondary.forEach(upsert);

  return sortGpuEntries(Array.from(byName.values()));
}

function detectWindowsGpus() {
  const dxDiag = detectDxDiagGpus();
  const wmi = readWmiGpuData();
  const merged = mergeGpuEntries(dxDiag, wmi);
  if (merged.length) return merged;
  return sortGpuEntries(wmi);
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
