import { getHardwareSnapshot } from "../utils/hardwareInfo.js";
import { readModelCatalog } from "./modelCatalog.js";

export function parseSizeGb(size) {
  if (!size) return null;
  const match = String(size).match(/([\d.]+)/);
  if (!match) return null;
  const value = parseFloat(match[1]);
  return Number.isNaN(value) ? null : value;
}

function scoreEntry(entry, hardware) {
  let score = 0;
  if (entry.cudaOptimized) score += 100;
  if ((entry.format || "").toLowerCase() === "onnx") score += 60;
  if (entry.latest) score += 20;
  const gpus = hardware?.gpu || [];
  const bestGpu = gpus.reduce(
    (best, gpu) => {
      if (!gpu || typeof gpu.memoryBytes !== "number") return best;
      if (!best || gpu.memoryBytes > best.memoryBytes) return gpu;
      return best;
    },
    null
  );
  const sizeGb = parseSizeGb(entry.size);
  if (sizeGb && bestGpu?.memoryBytes) {
    const vramGb = bestGpu.memoryBytes / (1024 * 1024 * 1024);
    if (sizeGb < vramGb * 0.6) score += 15;
    else if (sizeGb > vramGb * 1.2) score -= 5;
  }
  if (entry.provider && /microsoft|qwen/i.test(entry.provider)) score += 5;
  return { score, bestGpu, gpus };
}

export function selectRecommendedDownload(downloads, hardware) {
  if (!downloads.length) return null;
  let bestEntry = null;
  let bestData = null;
  for (const entry of downloads) {
    const info = scoreEntry(entry, hardware);
    if (!bestEntry || info.score > bestData.score) {
      bestEntry = entry;
      bestData = info;
    }
  }
  if (!bestEntry) return null;
  const nvidiaGpu = bestData.gpus.find(gpu => /nvidia/i.test(gpu.name || ""));
  return { entry: bestEntry, bestGpu: bestData.bestGpu, nvidiaGpu };
}

export function getRecommendedDownloadFromCatalog() {
  const downloads = readModelCatalog().filter(entry => !entry.requiresHuggingFace);
  if (!downloads.length) return null;
  const hardware = getHardwareSnapshot();
  const selection = selectRecommendedDownload(downloads, hardware);
  if (!selection) return null;
  return { ...selection, hardware, downloads };
}
