import fs from "node:fs";
import path from "node:path";

const catalogPath = path.resolve("./models/catalog.json");
const catalogDir = path.resolve("./models/catalog.d");

function readCatalogFile(filePath) {
  try {
    const txt = fs.readFileSync(filePath, "utf8");
    const parsed = JSON.parse(txt);
    if (Array.isArray(parsed)) return parsed;
    if (parsed && Array.isArray(parsed.models)) return parsed.models;
    return [];
  } catch {
    return [];
  }
}

export function readModelCatalog() {
  const merged = new Map();
  for (const entry of readCatalogFile(catalogPath)) {
    if (!entry || !entry.id) continue;
    merged.set(entry.id, entry);
  }
  if (fs.existsSync(catalogDir)) {
    const files = fs.readdirSync(catalogDir).filter(file => file.endsWith(".json"));
    for (const file of files) {
      for (const entry of readCatalogFile(path.join(catalogDir, file))) {
        if (!entry || !entry.id) continue;
        merged.set(entry.id, entry);
      }
    }
  }
  return Array.from(merged.values());
}

export function getLatestFreeCatalogEntry() {
  const catalog = readModelCatalog();
  return (
    catalog.find(item => item.latest) ||
    catalog.find(item => item.free) ||
    catalog[0] ||
    null
  );
}
