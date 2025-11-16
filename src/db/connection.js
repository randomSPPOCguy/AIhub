import Database from "better-sqlite3";
import { cfg } from "../config.js";
import { logger } from "../utils/logger.js";
import fs from "node:fs";
import path from "node:path";

const dir = path.dirname(cfg.dbPath);
if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });

export const db = new Database(cfg.dbPath);
logger.info("DB opened at", cfg.dbPath);
