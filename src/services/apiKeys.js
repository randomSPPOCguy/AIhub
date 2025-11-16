import crypto from "node:crypto";
import { db } from "../db/connection.js";

const HASH_ALGO = "sha256";

function hashKey(value) {
  return crypto.createHash(HASH_ALGO).update(value).digest("hex");
}

function generateKey() {
  return "aih_" + crypto.randomBytes(24).toString("hex");
}

export function issueApiKey(label = null) {
  const key = generateKey();
  const keyHash = hashKey(key);
  const stmt = db.prepare(`INSERT INTO api_keys (key_hash, label) VALUES (?, ?)`);
  const info = stmt.run(keyHash, label);
  return { id: info.lastInsertRowid, key };
}

export function validateApiKey(rawKey) {
  if (!rawKey) return null;
  const keyHash = hashKey(rawKey);
  const row = db
    .prepare(`SELECT * FROM api_keys WHERE key_hash = ? AND revoked = 0 LIMIT 1`)
    .get(keyHash);
  if (!row) return null;
  db.prepare(`UPDATE api_keys SET last_used_at = datetime('now') WHERE id = ?`).run(row.id);
  return row;
}

export function listApiKeys() {
  return db
    .prepare(`SELECT id, label, created_at, last_used_at, revoked FROM api_keys ORDER BY created_at DESC`)
    .all();
}

export function revokeApiKey(id) {
  return db.prepare(`UPDATE api_keys SET revoked = 1 WHERE id = ?`).run(id);
}
