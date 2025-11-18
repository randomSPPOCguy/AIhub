// Page-based navigation system for AIhub console
// Navigate between different pages like flipping through a book

import { getActiveModel, setActiveModel, listDownloadedLocalArtifacts } from "../services/modelRegistry.js";
import { buildModelOverviewPayload } from "../services/modelSummary.js";
import { detectTooling } from "../services/onboardingWizard.js";
import fetch from "node-fetch";
import { cfg } from "../config.js";

const ansi = {
  reset: "\x1b[0m",
  bold: "\x1b[1m",
  dim: "\x1b[2m",
  magenta: "\x1b[35m",
  cyan: "\x1b[36m",
  yellow: "\x1b[33m",
  green: "\x1b[32m",
  gray: "\x1b[90m",
  red: "\x1b[31m",
  blue: "\x1b[34m"
};

const color = (text, code) => `${code}${text}${ansi.reset}`;

export class PageNavigator {
  constructor() {
    this.currentPage = "home";
    this.history = [];
    this.logLines = 100; // Number of log lines to show
    this.pages = {
      home: { name: "Dashboard", render: this.renderHome.bind(this) },
      models: { name: "Models", render: this.renderModels.bind(this) },
      status: { name: "Status", render: this.renderStatus.bind(this) },
      logs: { name: "Logs", render: this.renderLogs.bind(this) },
      settings: { name: "Settings", render: this.renderSettings.bind(this) },
      help: { name: "Help", render: this.renderHelp.bind(this) }
    };
  }

  getPrompt() {
    const page = this.pages[this.currentPage]?.name || "AIhub";
    return color(`${page}> `, ansi.cyan);
  }

  navigateTo(pageName) {
    if (this.pages[pageName]) {
      this.history.push(this.currentPage);
      this.currentPage = pageName;
      console.clear(); // Clear screen on navigation
      return true;
    }
    return false;
  }

  back() {
    if (this.history.length > 0) {
      this.currentPage = this.history.pop();
      console.clear(); // Clear screen when going back
      return true;
    }
    return false;
  }

  async renderCurrent() {
    // Disable log capture during page rendering
    if (typeof global.capturingLogs !== "undefined") {
      global.capturingLogs = false;
    }

    const page = this.pages[this.currentPage];
    if (page && page.render) {
      await page.render();
    }

    // Re-enable log capture after rendering
    if (typeof global.capturingLogs !== "undefined") {
      global.capturingLogs = true;
    }
  }

  renderHeader(title) {
    console.log("");
    console.log(color("================================================================", ansi.cyan));
    console.log(color(`  ${title}`, `${ansi.bold}${ansi.cyan}`));
    console.log(color("================================================================", ansi.cyan));
    console.log("");
  }

  renderFooter(commands) {
    console.log("");
    console.log(color("  Navigation:", ansi.dim));
    commands.forEach(cmd => {
      console.log(color(`    ${cmd}`, ansi.gray));
    });
    console.log("");
  }

  async renderHome() {
    this.renderHeader("AIhub Dashboard");

    // Quick status check
    const checkPort = async (port) => {
      try {
        const res = await fetch(`http://localhost:${port}/health`, { signal: AbortSignal.timeout(1000) });
        return res.ok;
      } catch {
        return false;
      }
    };

    const [nodeOk, pythonOk, enrichOk] = await Promise.all([
      checkPort(cfg.port || 3000),
      checkPort(8000),
      checkPort(8001)
    ]);

    const statusIcon = (ok) => ok ? color("[OK]", ansi.green) : color("[--]", ansi.red);

    console.log(color("  Services:", ansi.bold));
    console.log(`    Node.js (3000)    ${statusIcon(nodeOk)}`);
    console.log(`    Python AI (8000)  ${statusIcon(pythonOk)}`);
    console.log(`    Enrichment (8001) ${statusIcon(enrichOk)}`);
    console.log("");

    const active = getActiveModel();
    console.log(color("  Active Model:", ansi.bold));
    if (active) {
      console.log(`    ${color(active.id, ansi.green)} (${active.provider})`);
    } else {
      console.log(color("    No model selected - use 'models' to select", ansi.yellow));
    }
    console.log("");

    const overview = buildModelOverviewPayload();
    const downloaded = overview.local?.installed?.length || 0;
    const cloudProviders = overview.cloud?.providers?.length || 0;

    console.log(color("  Quick Stats:", ansi.bold));
    console.log(`    Downloaded models: ${color(String(downloaded), ansi.cyan)}`);
    console.log(`    Cloud providers:   ${color(String(cloudProviders), ansi.cyan)}`);
    console.log("");

    console.log(color("  Quick Actions:", ansi.bold));
    console.log(color("    models  ", ansi.green) + "- Browse and switch models");
    console.log(color("    status  ", ansi.green) + "- View detailed service status");
    console.log(color("    settings", ansi.green) + "- Configure AIhub");
    console.log(color("    help    ", ansi.green) + "- Show all commands");

    this.renderFooter([
      "Type a page name to navigate (models, status, logs, settings, help)",
      "Type 'clear' to clear screen, 'exit' to quit"
    ]);
  }

  async renderModels() {
    this.renderHeader("Model Management");

    const overview = buildModelOverviewPayload();
    const active = getActiveModel();

    // Cloud models
    if (overview.cloud?.providers?.length > 0) {
      console.log(color("  Cloud Models:", ansi.bold));
      let index = 1;
      overview.cloud.providers.forEach(provider => {
        provider.suggestions?.forEach(model => {
          const activeMarker = (active?.id === model.remoteModel) ? color(" [ACTIVE]", ansi.green) : "";
          console.log(`    ${color(String(index).padStart(2), ansi.gray)}. ${color(model.remoteModel, ansi.cyan)}${activeMarker}`);
          console.log(`        ${color(model.description, ansi.dim)}`);
          index++;
        });
      });
      console.log("");
    }

    // Local models
    if (overview.local?.installed?.length > 0) {
      console.log(color("  Downloaded Local Models:", ansi.bold));
      overview.local.installed.forEach((model, idx) => {
        const activeMarker = (active?.id === model.remoteModel) ? color(" [ACTIVE]", ansi.green) : "";
        const size = typeof model.sizeBytes === "number"
          ? `${(model.sizeBytes / 1_073_741_824).toFixed(1)} GB`
          : "?";
        console.log(`    ${color(String(idx + 100).padStart(2), ansi.gray)}. ${color(model.remoteModel, ansi.green)}${activeMarker}`);
        console.log(`        ${color(`Size: ${size}`, ansi.dim)}`);
      });
      console.log("");
    }

    console.log(color("  Quick Actions:", ansi.bold));
    console.log(color("    set <model-id>  ", ansi.yellow) + "- Switch to a model instantly");
    console.log(color("    set <number>    ", ansi.yellow) + "- Switch by number");
    console.log(color("    download        ", ansi.yellow) + "- Browse downloadable models");

    this.renderFooter([
      "Type 'set <id>' to switch models",
      "Type 'back' or 'home' to return to dashboard"
    ]);
  }

  async renderStatus() {
    this.renderHeader("Service Status");

    const checkPort = async (port) => {
      try {
        const res = await fetch(`http://localhost:${port}/health`, { signal: AbortSignal.timeout(2000) });
        return res.ok;
      } catch {
        return false;
      }
    };

    const [nodeOk, pythonOk, enrichOk] = await Promise.all([
      checkPort(cfg.port || 3000),
      checkPort(8000),
      checkPort(8001)
    ]);

    const statusText = (ok) => ok ? color("Running", ansi.green) : color("Stopped", ansi.red);
    const statusIcon = (ok) => ok ? color("[OK]", ansi.green) : color("[--]", ansi.red);

    console.log(color("  Services:", ansi.bold));
    console.log(`    Node.js AIhub (3000)        ${statusIcon(nodeOk)} ${statusText(nodeOk)}`);
    console.log(`    Python ONNX AI (8000)       ${statusIcon(pythonOk)} ${statusText(pythonOk)}`);
    console.log(`    Python Enrichment (8001)    ${statusIcon(enrichOk)} ${statusText(enrichOk)}`);
    console.log("");

    const active = getActiveModel();
    console.log(color("  Active Configuration:", ansi.bold));
    console.log(`    Model:  ${active ? color(active.id, ansi.green) : color("None", ansi.yellow)}`);
    console.log(`    Port:   ${color(String(cfg.port || 3000), ansi.cyan)}`);
    console.log(`    Host:   ${color(cfg.host || "localhost", ansi.cyan)}`);
    console.log("");

    const tooling = detectTooling();
    console.log(color("  Tooling Status:", ansi.bold));
    console.log(`    ONNX GenAI:  ${tooling.hasOnnx ? color("[OK]", ansi.green) : color("[--]", ansi.red)}`);
    console.log(`    CUDA:        ${tooling.hasCuda ? color("[OK]", ansi.green) : color("[--]", ansi.red)}`);
    console.log(`    PyTorch:     ${tooling.hasTorch ? color("[OK]", ansi.green) : color("[--]", ansi.red)}`);

    this.renderFooter([
      "Type 'logs' to view service logs",
      "Type 'back' or 'home' to return to dashboard"
    ]);
  }

  async renderLogs() {
    // Clean ASCII banner for unified logs
    console.log("");
    console.log(color("┌────────────────────────────────────────────────────────────────┐", ansi.cyan));
    console.log(color("│                      UNIFIED LOGS TERMINAL                     │", ansi.cyan));
    console.log(color("│              [Node.js · Python AI · Enrichment]                │", ansi.dim));
    console.log(color("└────────────────────────────────────────────────────────────────┘", ansi.cyan));
    console.log("");

    // Get all logs from global capture
    const allLogs = this.getAllLogs();

    if (allLogs && allLogs.length > 0) {
      // Show last N lines with color coding
      allLogs.slice(-this.logLines).forEach(log => {
        const { message, source } = log;

        // Color code by source and content
        if (message.includes("ERROR") || message.includes("error") || message.includes("✗")) {
          console.log(color(message, ansi.red));
        } else if (message.includes("WARN") || message.includes("warn") || message.includes("!")) {
          console.log(color(message, ansi.yellow));
        } else if (message.includes("SUCCESS") || message.includes("✓") || message.includes("[OK]")) {
          console.log(color(message, ansi.green));
        } else if (source === "enrich" || message.includes("[ENRICH]")) {
          console.log(color(message, ansi.cyan));
        } else if (source === "chat" || message.includes("[CHAT]")) {
          console.log(color(message, ansi.magenta));
        } else if (source === "python" || message.includes("[PY]")) {
          console.log(color(message, ansi.blue));
        } else {
          console.log(color(message, ansi.gray));
        }
      });
    } else {
      console.log(color("  [No logs yet - waiting for activity...]", ansi.dim));
      console.log("");
    }

    // Footer prompt hint - minimal
    console.log("");
    console.log(color("─────────────────────────────────────────────────────────────────", ansi.dim));
    console.log(color("  Type commands (/model, /status) or chat with AI", ansi.dim));
    console.log(color("  'back' or 'home' to navigate | 'clear' to refresh", ansi.dim));
    console.log("");
  }

  getAllLogs() {
    // Initialize global log storage if needed
    if (typeof global.aiHubLogs === "undefined") {
      global.aiHubLogs = [];
    }
    return global.aiHubLogs;
  }

  async renderSettings() {
    this.renderHeader("Settings & Configuration");

    console.log(color("  Available Settings:", ansi.bold));
    console.log("");
    console.log(color("    tune    ", ansi.yellow) + "- Fine-tune model parameters (temp, max tokens, etc.)");
    console.log(color("    temp    ", ansi.yellow) + "- Quick temperature adjustment");
    console.log(color("    setup   ", ansi.yellow) + "- Run first-time setup wizard");
    console.log(color("    cuda    ", ansi.yellow) + "- Check CUDA/GPU installation");
    console.log(color("    keygen  ", ansi.yellow) + "- Generate API key for bots");
    console.log("");

    console.log(color("  Configuration File:", ansi.bold));
    console.log(`    ${color("config.env", ansi.cyan)} - Edit this file to set API keys and preferences`);

    this.renderFooter([
      "Type a setting command to configure",
      "Type 'back' or 'home' to return to dashboard"
    ]);
  }

  async renderHelp() {
    this.renderHeader("Help & Commands");

    console.log(color("  Navigation:", ansi.bold));
    console.log(color("    home     ", ansi.cyan) + "- Return to dashboard");
    console.log(color("    models   ", ansi.cyan) + "- Browse and manage models");
    console.log(color("    status   ", ansi.cyan) + "- View service status");
    console.log(color("    logs     ", ansi.cyan) + "- View service logs");
    console.log(color("    settings ", ansi.cyan) + "- Configure AIhub");
    console.log(color("    back     ", ansi.cyan) + "- Go to previous page");
    console.log("");

    console.log(color("  Quick Commands (work from any page):", ansi.bold));
    console.log(color("    set <model>  ", ansi.yellow) + "- Switch active model");
    console.log(color("    clear        ", ansi.yellow) + "- Clear screen");
    console.log(color("    exit / quit  ", ansi.yellow) + "- Stop AIhub and exit");
    console.log("");

    console.log(color("  From Settings Page:", ansi.bold));
    console.log(color("    tune    ", ansi.green) + "- Configure model parameters");
    console.log(color("    temp    ", ansi.green) + "- Set temperature");
    console.log(color("    setup   ", ansi.green) + "- Run setup wizard");
    console.log(color("    cuda    ", ansi.green) + "- Check CUDA status");
    console.log(color("    keygen  ", ansi.green) + "- Generate API key");

    this.renderFooter([
      "Type a page name to navigate",
      "Type 'back' to return to previous page"
    ]);
  }
}
