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

const TEMP_SETTINGS = {
  default: "ai_default_temperature",
  creative: "ai_creative_temperature",
  precise: "ai_precise_temperature",
  balanced: "ai_balanced_temperature"
};

const TEMP_PRESETS = {
  creative: { value: 0.9, description: "High creativity, more random responses" },
  balanced: { value: 0.7, description: "Default balanced mode" },
  precise: { value: 0.3, description: "Low temperature, focused responses" },
  deterministic: { value: 0.1, description: "Minimal randomness, very consistent" }
};

function ask(rl, question) {
  return new Promise(resolve => {
    rl.question(question, answer => resolve(answer.trim()));
  });
}

export function getTemperature(mode = "default") {
  const key = TEMP_SETTINGS[mode] || TEMP_SETTINGS.default;
  const stored = getState(key);
  if (stored !== undefined && stored !== null) {
    return parseFloat(stored);
  }
  // Return defaults if not configured
  switch (mode) {
    case "creative":
      return 0.9;
    case "precise":
      return 0.3;
    case "balanced":
      return 0.7;
    default:
      return 0.7;
  }
}

export function setTemperature(mode, value) {
  const key = TEMP_SETTINGS[mode] || TEMP_SETTINGS.default;
  if (typeof value !== "number" || value < 0 || value > 2) {
    throw new Error("Temperature must be a number between 0 and 2");
  }
  setState(key, value);
  return value;
}

export function showTemperatureSettings() {
  console.log("");
  console.log(color("═══════════════════════════════════════════", ansi.cyan));
  console.log(color("     🌡️  Temperature Settings", `${ansi.bold}${ansi.cyan}`));
  console.log(color("═══════════════════════════════════════════", ansi.cyan));
  console.log("");
  console.log(color("Current Settings:", ansi.bold));
  console.log(`  Default:   ${color(getTemperature("default").toFixed(2), ansi.green)}`);
  console.log(`  Creative:  ${color(getTemperature("creative").toFixed(2), ansi.green)}`);
  console.log(`  Balanced:  ${color(getTemperature("balanced").toFixed(2), ansi.green)}`);
  console.log(`  Precise:   ${color(getTemperature("precise").toFixed(2), ansi.green)}`);
  console.log("");
  console.log(color("Temperature Guide:", ansi.gray));
  console.log(color("  0.0 - 0.3   Very focused and deterministic", ansi.gray));
  console.log(color("  0.4 - 0.7   Balanced creativity and focus", ansi.gray));
  console.log(color("  0.8 - 1.2   Creative and varied responses", ansi.gray));
  console.log(color("  1.3 - 2.0   Very creative, highly random", ansi.gray));
  console.log("");
}

export async function configureTemperature() {
  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout
  });

  try {
    showTemperatureSettings();

    console.log(color("Presets:", ansi.bold));
    let idx = 1;
    for (const [name, preset] of Object.entries(TEMP_PRESETS)) {
      console.log(`  ${idx}. ${color(name.padEnd(15), ansi.cyan)} (${preset.value}) - ${preset.description}`);
      idx++;
    }
    console.log("");
    console.log(color("Commands:", ansi.bold));
    console.log(`  ${color("back", ansi.gray)}        Return to main menu`);
    console.log(`  ${color("Enter", ansi.gray)}       Exit without changes`);
    console.log("");

    const choice = await ask(
      rl,
      color("Choose preset (1-4), set custom (c), back, or press Enter to skip: ", ansi.yellow)
    );

    if (!choice || choice.toLowerCase() === "back") {
      if (choice?.toLowerCase() === "back") {
        console.log(color("Returning to main menu...", ansi.gray));
      } else {
        console.log(color("No changes made.", ansi.gray));
      }
      return;
    }

    if (choice.toLowerCase() === "c" || choice.toLowerCase() === "custom") {
      // Custom temperature
      const tempStr = await ask(
        rl,
        color("Enter temperature value (0.0 - 2.0), back, or press Enter to cancel: ", ansi.yellow)
      );

      if (!tempStr || tempStr.toLowerCase() === "back") {
        if (tempStr?.toLowerCase() === "back") {
          console.log(color("Returning to main menu...", ansi.gray));
        }
        return;
      }

      const tempValue = parseFloat(tempStr);

      if (Number.isNaN(tempValue) || tempValue < 0 || tempValue > 2) {
        console.log(color("Invalid temperature value. Must be between 0.0 and 2.0", ansi.red));
        return;
      }

      const mode = await ask(
        rl,
        color("Apply to which mode? (default/creative/balanced/precise), back, or press Enter to cancel: ", ansi.yellow)
      );

      if (!mode || mode.toLowerCase() === "back") {
        if (mode?.toLowerCase() === "back") {
          console.log(color("Returning to main menu...", ansi.gray));
        }
        return;
      }

      const validModes = ["default", "creative", "balanced", "precise"];
      if (!validModes.includes(mode.toLowerCase())) {
        console.log(color("Invalid mode. Choose from: default, creative, balanced, precise", ansi.red));
        return;
      }

      setTemperature(mode.toLowerCase(), tempValue);
      console.log("");
      console.log(color(`✓ ${mode} temperature set to ${tempValue.toFixed(2)}`, ansi.green));
      console.log("");
    } else {
      // Preset selection
      const presetIdx = parseInt(choice);
      const presetNames = Object.keys(TEMP_PRESETS);

      if (presetIdx < 1 || presetIdx > presetNames.length) {
        console.log(color("Invalid preset selection.", ansi.red));
        return;
      }

      const presetName = presetNames[presetIdx - 1];
      const preset = TEMP_PRESETS[presetName];

      // Apply preset to all modes
      setTemperature("default", preset.value);
      console.log("");
      console.log(color(`✓ Applied ${presetName} preset (${preset.value}) to all modes`, ansi.green));
      console.log("");
    }

    showTemperatureSettings();

  } finally {
    rl.close();
  }
}

export async function quickSetTemperature(value) {
  if (typeof value === "string") {
    // Check if it's a preset name
    const preset = TEMP_PRESETS[value.toLowerCase()];
    if (preset) {
      setTemperature("default", preset.value);
      console.log(color(`✓ Temperature set to ${value} (${preset.value})`, ansi.green));
      return preset.value;
    }

    // Try parsing as number
    const numValue = parseFloat(value);
    if (!Number.isNaN(numValue) && numValue >= 0 && numValue <= 2) {
      setTemperature("default", numValue);
      console.log(color(`✓ Temperature set to ${numValue.toFixed(2)}`, ansi.green));
      return numValue;
    }
  }

  if (typeof value === "number" && value >= 0 && value <= 2) {
    setTemperature("default", value);
    console.log(color(`✓ Temperature set to ${value.toFixed(2)}`, ansi.green));
    return value;
  }

  console.log(color("Invalid temperature. Use a number (0-2) or preset name (creative/balanced/precise/deterministic)", ansi.red));
  return null;
}
