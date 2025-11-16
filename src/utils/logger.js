export const logger = {
  info: console.log.bind(console, "[INF]"),
  warn: console.warn.bind(console, "[WRN]"),
  error: console.error.bind(console, "[ERR]"),
  debug: (...args) => { if (process.env.LOG_LEVEL === "debug") console.debug("[DBG]", ...args); }
};
