import {
  getActiveModel,
  listCloudModels,
  listInstalledLocalModels,
  listConfiguredLocalModels,
  listDownloadedLocalArtifacts,
  getLocalRuntimeConfig
} from "./modelRegistry.js";
import { readModelCatalog, getLatestFreeCatalogEntry } from "./modelCatalog.js";
import { getHardwareSnapshot } from "../utils/hardwareInfo.js";

function formatCatalogEntry(entry) {
  let requiresLabel = entry.requiresApiKey;
  if (
    requiresLabel === undefined &&
    typeof entry.url === "string" &&
    entry.url.toLowerCase().includes("huggingface.co")
  ) {
    requiresLabel = "huggingface";
  }
  const requiresHf = requiresLabel === "huggingface";
  const requires = requiresLabel ? `(requires ${requiresLabel} API key)` : "";
  return {
    ...entry,
    displayName: requires ? `${entry.name} ${requires}` : entry.name,
    requiresHuggingFace: Boolean(requiresHf)
  };
}

export function buildCloudModelsPayload() {
  const models = listCloudModels();
  return {
    object: "model.cloud",
    activeModel: getActiveModel(),
    count: models.length,
    providers: models
  };
}

export function buildLocalModelsPayload(options = {}) {
  const configured = listConfiguredLocalModels();
  const installed = listDownloadedLocalArtifacts();
  const selectable = listInstalledLocalModels();
  const downloadsRaw = readModelCatalog();
  const downloads = downloadsRaw.map(formatCatalogEntry);
  const latest = getLatestFreeCatalogEntry();
  const payload = {
    object: "model.local",
    activeModel: getActiveModel(),
    configured,
    installed,
    selectable,
    downloads,
    latestFreeDownload: latest ? formatCatalogEntry(latest) : null,
    runtime: getLocalRuntimeConfig()
  };
  if (options.includeHardware) {
    payload.hardware = getHardwareSnapshot();
  }
  return payload;
}

export function buildModelOverviewPayload() {
  const hardware = getHardwareSnapshot();
  const cloud = buildCloudModelsPayload();
  const local = buildLocalModelsPayload();
  return {
    object: "model.overview",
    hardware,
    activeModel: getActiveModel(),
    cloud: {
      count: cloud.count,
      providers: cloud.providers
    },
    local: {
      configured: local.configured,
      installed: local.installed,
      selectable: local.selectable,
      downloads: local.downloads,
      latestFreeDownload: local.latestFreeDownload,
      runtime: local.runtime
    }
  };
}
