import fs from "node:fs";
import path from "node:path";
import { db } from "./connection.js";
import { fileURLToPath, pathToFileURL } from "node:url";
import { logger } from "../utils/logger.js";

const schemaPath = path.resolve("src/db/schema.sql");
const sql = fs.readFileSync(schemaPath, "utf-8");
db.exec(sql);
logger.info("Migration complete", { schemaPath });
// Exit only if this file is the entrypoint
const isDirect = import.meta.url === pathToFileURL(process.argv[1]).href;
if (isDirect) process.exit(0);
