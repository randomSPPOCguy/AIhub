import fs from "node:fs";
import path from "node:path";
import util from "node:util";

const LEVELS = ["error", "warn", "info", "debug"];
const LEVEL_RANK = {
  error: 0,
  warn: 1,
  info: 2,
  debug: 3
};

const envLevel = (process.env.LOG_LEVEL || "info").toLowerCase();
const currentLevel = LEVEL_RANK[envLevel] ?? LEVEL_RANK.info;

const fileLoggingEnabled = process.env.LOG_FILE || process.env.LOG_TO_FILE === "true";
const logFilePath = process.env.LOG_FILE || path.resolve(process.cwd(), "logs", "aihub.log");
let fileStream = null;

if (fileLoggingEnabled) {
  try {
    fs.mkdirSync(path.dirname(logFilePath), { recursive: true });
    fileStream = fs.createWriteStream(logFilePath, { flags: "a" });
  } catch (err) {
    // Fall back to console only if file logging fails
    process.stderr.write(`Failed to initialize log file at ${logFilePath}: ${err.message}\n`);
  }
}

function formatArgs(args) {
  return args
    .map((arg) => {
      if (arg instanceof Error) {
        return `${arg.message}\n${arg.stack}`;
      }
      if (typeof arg === "string") return arg;
      return util.inspect(arg, { depth: 5, breakLength: 80, colors: false });
    })
    .join(" ");
}

function writeLog(level, args, force = false) {
  const levelRank = LEVEL_RANK[level] ?? LEVEL_RANK.info;
  if (!force && levelRank > currentLevel) {
    return;
  }
  const timestamp = new Date().toISOString();
  const line = `[${timestamp}] [${level.toUpperCase()}] ${formatArgs(args)}`;
  const consoleMethod =
    level === "error" ? console.error : level === "warn" ? console.warn : console.log;
  consoleMethod(line);
  if (fileStream) {
    fileStream.write(`${line}\n`);
  }
}

export const logger = {
  log(level, ...args) {
    if (!LEVELS.includes(level)) {
      throw new Error(`Unknown log level: ${level}`);
    }
    writeLog(level, args);
  },
  info: (...args) => writeLog("info", args),
  warn: (...args) => writeLog("warn", args),
  error: (...args) => writeLog("error", args),
  debug: (...args) => writeLog("debug", args),
  force(level, ...args) {
    writeLog(level, args, true);
  }
};
