import { db } from "../db/connection.js";

export function getState(key, defaultValue = null) {
  const row = db.prepare(`SELECT value FROM hub_state WHERE key = ?`).get(key);
  if (!row) return defaultValue;
  try {
    return JSON.parse(row.value);
  } catch {
    return row.value;
  }
}

export function setState(key, value) {
  const serialized = typeof value === "string" ? value : JSON.stringify(value);
  db.prepare(
    `INSERT INTO hub_state (key, value) VALUES (?, ?)
     ON CONFLICT(key) DO UPDATE SET value = excluded.value`
  ).run(key, serialized);
}
