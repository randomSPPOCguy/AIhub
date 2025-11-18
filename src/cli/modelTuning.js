import { getState, setState } from "../services/hubState.js";
import readline from "node:readline";

const ansi = {
  reset: "\x1b[0m",
  bold: "\x1b[1m",
  cyan: "\x1b[36m",
  yellow: "\x1b[33m",
  green: "\x1b[32m",
  gray: "\x1b[90m",
  red: "\x1b[31m",
  magenta: "\x1b[35m"
};

const color = (text, code) => `${code}${text}${ansi.reset}`;

// Model parameter keys
const PARAM_KEYS = {
  temperature: "model_temperature",
  maxTokens: "model_max_tokens",
  topP: "model_top_p",
  topK: "model_top_k",
  repetitionPenalty: "model_repetition_penalty",
  frequencyPenalty: "model_frequency_penalty",
  presencePenalty: "model_presence_penalty"
};

// Default values
const DEFAULTS = {
  temperature: 0.7,
  maxTokens: 1024,
  topP: 0.9,
  topK: 40,
  repetitionPenalty: 1.1,
  frequencyPenalty: 0.0,
  presencePenalty: 0.0
};

// Parameter descriptions and ranges
const PARAM_INFO = {
  temperature: {
    name: "Temperature",
    description: "Controls randomness. Lower = focused, Higher = creative",
    range: "0.0 - 2.0",
    default: 0.7,
    presets: {
      deterministic: 0.1,
      precise: 0.3,
      balanced: 0.7,
      creative: 0.9,
      chaotic: 1.5
    }
  },
  maxTokens: {
    name: "Max Tokens",
    description: "Maximum response length in tokens",
    range: "50 - 4096",
    default: 1024,
    presets: {
      short: 256,
      medium: 1024,
      long: 2048,
      veryLong: 4096
    }
  },
  topP: {
    name: "Top P (Nucleus Sampling)",
    description: "Cumulative probability cutoff. Lower = more focused",
    range: "0.0 - 1.0",
    default: 0.9,
    presets: {
      focused: 0.7,
      balanced: 0.9,
      diverse: 0.95
    }
  },
  topK: {
    name: "Top K",
    description: "Number of highest probability tokens to consider",
    range: "1 - 100",
    default: 40,
    presets: {
      focused: 20,
      balanced: 40,
      diverse: 80
    }
  },
  repetitionPenalty: {
    name: "Repetition Penalty",
    description: "Penalize repeated tokens. Higher = less repetition",
    range: "1.0 - 2.0",
    default: 1.1,
    presets: {
      none: 1.0,
      slight: 1.1,
      moderate: 1.3,
      strong: 1.5
    }
  },
  frequencyPenalty: {
    name: "Frequency Penalty",
    description: "Reduce likelihood of frequent tokens",
    range: "-2.0 - 2.0",
    default: 0.0,
    presets: {
      none: 0.0,
      slight: 0.3,
      moderate: 0.6,
      strong: 1.0
    }
  },
  presencePenalty: {
    name: "Presence Penalty",
    description: "Reduce likelihood of any repeated token",
    range: "-2.0 - 2.0",
    default: 0.0,
    presets: {
      none: 0.0,
      slight: 0.3,
      moderate: 0.6,
      strong: 1.0
    }
  }
};

function ask(rl, question) {
  return new Promise(resolve => {
    rl.question(question, answer => resolve(answer.trim()));
  });
}

export function getModelParam(param) {
  const key = PARAM_KEYS[param];
  if (!key) return undefined; // Return undefined if not configured

  const stored = getState(key);
  if (stored !== undefined && stored !== null) {
    return typeof stored === "string" ? parseFloat(stored) : stored;
  }

  return undefined; // Return undefined, not defaults
}

export function setModelParam(param, value) {
  const key = PARAM_KEYS[param];
  if (!key) throw new Error(`Unknown parameter: ${param}`);

  const info = PARAM_INFO[param];
  if (!info) throw new Error(`Unknown parameter: ${param}`);

  // Validate based on parameter type
  if (typeof value !== "number" || isNaN(value)) {
    throw new Error(`${info.name} must be a number`);
  }

  setState(key, value);
  return value;
}

export function getAllModelParams() {
  // Only return configured parameters (exclude undefined)
  const params = {};

  const temp = getModelParam("temperature");
  if (temp !== undefined) params.temperature = temp;

  const maxTokens = getModelParam("maxTokens");
  if (maxTokens !== undefined) params.maxTokens = maxTokens;

  const topP = getModelParam("topP");
  if (topP !== undefined) params.topP = topP;

  const topK = getModelParam("topK");
  if (topK !== undefined) params.topK = topK;

  const repPenalty = getModelParam("repetitionPenalty");
  if (repPenalty !== undefined) params.repetitionPenalty = repPenalty;

  const freqPenalty = getModelParam("frequencyPenalty");
  if (freqPenalty !== undefined) params.frequencyPenalty = freqPenalty;

  const presPenalty = getModelParam("presencePenalty");
  if (presPenalty !== undefined) params.presencePenalty = presPenalty;

  return params;
}

export function showModelParams() {
  console.log("");
  console.log(color("═══════════════════════════════════════════", ansi.cyan));
  console.log(color("     🎛️  Model Fine-Tuning Parameters", `${ansi.bold}${ansi.cyan}`));
  console.log(color("═══════════════════════════════════════════", ansi.cyan));
  console.log("");

  const params = getAllModelParams();
  const hasConfigured = Object.keys(params).length > 0;

  if (!hasConfigured) {
    console.log(color("  No parameters configured - using AI provider defaults", ansi.yellow));
    console.log("");
    console.log(color("  Run '/tune' to configure parameters", ansi.gray));
    console.log("");
    return;
  }

  console.log(color("Current Settings:", ansi.bold));
  console.log("");

  Object.keys(PARAM_INFO).forEach((key, idx) => {
    const info = PARAM_INFO[key];
    const value = params[key];
    const isConfigured = value !== undefined;

    if (isConfigured) {
      console.log(`  ${idx + 1}. ${color(info.name.padEnd(25), ansi.cyan)} ${color(value, ansi.green)}`);
    } else {
      console.log(`  ${idx + 1}. ${color(info.name.padEnd(25), ansi.gray)} ${color("not set (using provider default)", ansi.gray)}`);
    }
    console.log(`     ${color(info.description, ansi.gray)}`);
    console.log(`     ${color(`Range: ${info.range}`, ansi.gray)}`);
    console.log("");
  });
}

export async function configureModelParams() {
  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout
  });

  try {
    showModelParams();

    console.log(color("Options:", ansi.bold));
    console.log(`  ${color("1-7", ansi.cyan)}        Configure individual parameter`);
    console.log(`  ${color("preset", ansi.cyan)}     Apply preset configuration`);
    console.log(`  ${color("reset", ansi.cyan)}      Reset all to defaults`);
    console.log(`  ${color("back", ansi.gray)}       Return to main menu`);
    console.log(`  ${color("Enter", ansi.cyan)}      Exit without changes`);
    console.log("");

    const choice = await ask(rl, color("Choose option: ", ansi.yellow));

    if (!choice || choice.toLowerCase() === "back") {
      if (choice?.toLowerCase() === "back") {
        console.log(color("Returning to main menu...", ansi.gray));
      } else {
        console.log(color("No changes made.", ansi.gray));
      }
      return;
    }

    // Reset all to defaults
    if (choice.toLowerCase() === "reset") {
      Object.keys(PARAM_KEYS).forEach(param => {
        setModelParam(param, DEFAULTS[param]);
      });
      console.log("");
      console.log(color("✓ All parameters reset to defaults", ansi.green));
      console.log("");
      showModelParams();
      return;
    }

    // Apply preset
    if (choice.toLowerCase() === "preset") {
      console.log("");
      console.log(color("Available Presets:", ansi.bold));
      console.log(`  ${color("1", ansi.cyan)} Chatbot      - Balanced for conversation (temp: 0.7, tokens: 512)`);
      console.log(`  ${color("2", ansi.cyan)} Creative     - High creativity (temp: 0.9, tokens: 2048)`);
      console.log(`  ${color("3", ansi.cyan)} Precise      - Focused responses (temp: 0.3, tokens: 1024)`);
      console.log(`  ${color("4", ansi.cyan)} Code         - For coding tasks (temp: 0.2, tokens: 2048)`);
      console.log(`  ${color("5", ansi.cyan)} Storytelling - Long creative output (temp: 0.9, tokens: 4096)`);
      console.log("");
      console.log(color("Commands:", ansi.bold));
      console.log(`  ${color("back", ansi.gray)}        Return to main menu`);
      console.log(`  ${color("Enter", ansi.gray)}       Cancel preset selection`);
      console.log("");

      const presetChoice = await ask(rl, color("Select preset (1-5), back, or press Enter to cancel: ", ansi.yellow));

      if (!presetChoice || presetChoice.toLowerCase() === "back") {
        if (presetChoice?.toLowerCase() === "back") {
          console.log(color("Returning to main menu...", ansi.gray));
        }
        return;
      }

      const presets = {
        "1": { name: "Chatbot", temperature: 0.7, maxTokens: 512, topP: 0.9, repetitionPenalty: 1.2 },
        "2": { name: "Creative", temperature: 0.9, maxTokens: 2048, topP: 0.95, repetitionPenalty: 1.1 },
        "3": { name: "Precise", temperature: 0.3, maxTokens: 1024, topP: 0.7, repetitionPenalty: 1.3 },
        "4": { name: "Code", temperature: 0.2, maxTokens: 2048, topP: 0.8, repetitionPenalty: 1.0 },
        "5": { name: "Storytelling", temperature: 0.9, maxTokens: 4096, topP: 0.95, repetitionPenalty: 1.0 }
      };

      const preset = presets[presetChoice];
      if (preset) {
        Object.keys(preset).forEach(key => {
          if (key !== "name" && PARAM_KEYS[key]) {
            setModelParam(key, preset[key]);
          }
        });
        console.log("");
        console.log(color(`✓ Applied ${preset.name} preset`, ansi.green));
        console.log("");
        showModelParams();
      } else {
        console.log(color("Invalid preset selection", ansi.red));
      }
      return;
    }

    // Configure individual parameter
    const paramIdx = parseInt(choice);
    if (paramIdx >= 1 && paramIdx <= 7) {
      const paramKeys = Object.keys(PARAM_INFO);
      const paramKey = paramKeys[paramIdx - 1];
      const info = PARAM_INFO[paramKey];

      console.log("");
      console.log(color(`Configuring: ${info.name}`, ansi.bold));
      console.log(color(info.description, ansi.gray));
      console.log(color(`Range: ${info.range}`, ansi.gray));
      console.log(color(`Current: ${getModelParam(paramKey)}`, ansi.yellow));
      console.log("");

      // Show presets if available
      if (info.presets) {
        console.log(color("Presets:", ansi.cyan));
        Object.keys(info.presets).forEach(presetName => {
          console.log(`  ${color(presetName.padEnd(15), ansi.gray)} ${info.presets[presetName]}`);
        });
        console.log("");
      }
      console.log(color("Commands:", ansi.bold));
      console.log(`  ${color("back", ansi.gray)}        Return to main menu`);
      console.log(`  ${color("Enter", ansi.gray)}       Cancel without changes`);
      console.log("");

      const valueStr = await ask(rl, color("Enter new value (or preset name), back, or press Enter to cancel: ", ansi.yellow));

      if (!valueStr || valueStr.toLowerCase() === "back") {
        if (valueStr?.toLowerCase() === "back") {
          console.log(color("Returning to main menu...", ansi.gray));
        } else {
          console.log(color("No changes made.", ansi.gray));
        }
        return;
      }

      // Check if it's a preset name
      let value;
      if (info.presets && info.presets[valueStr]) {
        value = info.presets[valueStr];
      } else {
        value = parseFloat(valueStr);
      }

      if (isNaN(value)) {
        console.log(color("Invalid value", ansi.red));
        return;
      }

      setModelParam(paramKey, value);
      console.log("");
      console.log(color(`✓ ${info.name} set to ${value}`, ansi.green));
      console.log("");

    } else {
      console.log(color("Invalid selection", ansi.red));
    }

  } finally {
    rl.close();
  }
}

export function quickSetPreset(presetName) {
  const presets = {
    chatbot: { temperature: 0.7, maxTokens: 512, topP: 0.9, repetitionPenalty: 1.2 },
    creative: { temperature: 0.9, maxTokens: 2048, topP: 0.95, repetitionPenalty: 1.1 },
    precise: { temperature: 0.3, maxTokens: 1024, topP: 0.7, repetitionPenalty: 1.3 },
    code: { temperature: 0.2, maxTokens: 2048, topP: 0.8, repetitionPenalty: 1.0 },
    storytelling: { temperature: 0.9, maxTokens: 4096, topP: 0.95, repetitionPenalty: 1.0 }
  };

  const preset = presets[presetName.toLowerCase()];
  if (!preset) {
    console.log(color(`Unknown preset: ${presetName}. Available: chatbot, creative, precise, code, storytelling`, ansi.red));
    return false;
  }

  Object.keys(preset).forEach(key => {
    if (PARAM_KEYS[key]) {
      setModelParam(key, preset[key]);
    }
  });

  console.log(color(`✓ Applied ${presetName} preset`, ansi.green));
  return true;
}
