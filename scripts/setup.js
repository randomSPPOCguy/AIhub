#!/usr/bin/env node

/**
 * AI Hub First-Time Setup
 *
 * This script runs when you first download AI Hub from GitHub.
 * It detects your hardware, recommends the best inference engine,
 * and helps you get started quickly.
 *
 * Usage:
 *   node setup.js
 *
 * Or if built as an executable:
 *   aihub-setup.exe
 */

import { runFirstTimeSetup } from "./src/cli/firstTimeSetup.js";

console.log("");
console.log("╔════════════════════════════════════════════════════════╗");
console.log("║                                                        ║");
console.log("║              🤖 Welcome to AI Hub 1.4.1                ║");
console.log("║                                                        ║");
console.log("║   A local-first AI inference hub with hardware         ║");
console.log("║   detection and automatic optimization                ║");
console.log("║                                                        ║");
console.log("╚════════════════════════════════════════════════════════╝");
console.log("");

async function main() {
  try {
    await runFirstTimeSetup();
    process.exit(0);
  } catch (error) {
    console.error("\x1b[31m[ERROR] Setup failed:\x1b[0m", error.message);
    if (error.stack) {
      console.error("\x1b[90m" + error.stack + "\x1b[0m");
    }
    process.exit(1);
  }
}

main();
