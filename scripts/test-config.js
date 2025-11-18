#!/usr/bin/env node
// Test script to verify that all configuration settings are correctly loaded from config.env

import dotenv from 'dotenv';
import fs from 'node:fs';
import path from 'node:path';

// Load config.env
if (fs.existsSync("config.env")) {
  dotenv.config({ path: "config.env" });
  console.log("✅ Loaded configuration from config.env");
} else {
  dotenv.config();
  console.log("⚠️ Using default .env file");
}

// Define all expected configuration settings with their categories
const expectedConfig = {
  // Core server settings
  "Core Server Settings": [
    "PORT",
    "HOST",
    "DB_PATH",
    "NODE_ENV",
    "LOG_LEVEL",
    "ALLOW_ORIGIN"
  ],

  // User Agent Settings
  "User Agent Settings": [
    "WIKI_UA",
    "MB_UA_APP",
    "MB_UA_VERSION",
    "MB_UA_CONTACT"
  ],

  // Bot Behavior Settings
  "Bot Behavior Settings": [
    "BOT_KEYWORDS"
  ],

  // Media Harvest Settings
  "Media Harvest Settings": [
    "HARVEST_CAA",
    "CAA_MAX_SIZE"
  ],

  // Hub Authentication
  "Hub Authentication": [
    "AIHUB_REQUIRE_KEY",
    "REQUIRE_HUB_API_KEY",
    "HUGGINGFACE_TOKEN"
  ],

  // Python ONNX Service
  "Python ONNX Service": [
    "PYTHON_AI_HOST",
    "PYTHON_AI_PORT",
    "PYTHON_MODEL_ROOT",
    "PYTHON_AI_BASE"
  ],

  // Local Model Settings
  "Local Model Settings": [
    "LOCAL_MODEL_NAME",
    "LOCAL_MODEL_KIND",
    "LOCAL_MODEL_URL",
    "LOCAL_MODEL_ONNX_PATH",
    "LOCAL_MODEL_API_KEY",
    "LOCAL_MODEL_PATH",
    "LOCAL_MODEL_CHAT_PATH"
  ],

  // External AI Providers - OpenAI
  "OpenAI Settings": [
    "OPENAI_API_KEY",
    "OPENAI_MODEL",
    "OPENAI_BASE_URL"
  ],

  // External AI Providers - Anthropic
  "Anthropic Settings": [
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_MODEL",
    "ANTHROPIC_BASE_URL",
    "CLAUDE_API_KEY",
    "DEFAULT_CLAUDE_MODEL"
  ],

  // External AI Providers - Google
  "Google Settings": [
    "GEMINI_API_KEY",
    "GEMINI_MODEL",
    "GEMINI_BASE_URL",
    "GOOGLE_API_KEY",
    "GOOGLE_GEMINI_MODEL"
  ],

  // External AI Providers - Hugging Face
  "Hugging Face Settings": [
    "HUGGINGFACE_API_KEY",
    "HUGGINGFACE_MODEL",
    "HUGGINGFACE_BASE_URL",
    "HUGGINGFACE_HUB_TOKEN"
  ],

  // External APIs
  "External APIs": [
    "DISCOGS_TOKEN"
  ]
};

// Test function to check if settings are defined in process.env
function testConfigurationSettings() {
  console.log("\n=== Configuration Test Results ===\n");

  let totalSettings = 0;
  let definedSettings = 0;

  // Check each category
  for (const [category, settings] of Object.entries(expectedConfig)) {
    console.log(`\n## ${category}`);

    // Check each setting in the category
    for (const setting of settings) {
      totalSettings++;

      const value = process.env[setting];
      const isDefined = value !== undefined;

      if (isDefined) {
        definedSettings++;
        // Mask sensitive values
        const isSensitive = setting.includes('KEY') || setting.includes('TOKEN') || setting.includes('API');
        const displayValue = isSensitive ? (value ? '********' : '(empty)') : value;
        console.log(`✅ ${setting} = ${displayValue}`);
      } else {
        console.log(`❌ ${setting} is not defined`);
      }
    }
  }

  // Summary
  console.log(`\n=== Summary ===`);
  console.log(`Total settings: ${totalSettings}`);
  console.log(`Defined settings: ${definedSettings}`);
  console.log(`Missing settings: ${totalSettings - definedSettings}`);

  const successRate = Math.round((definedSettings / totalSettings) * 100);
  console.log(`Configuration success rate: ${successRate}%`);

  if (successRate === 100) {
    console.log("\n✅ All configuration settings are defined!");
  } else {
    console.log("\n⚠️ Some configuration settings are missing. Check the results above.");
  }
}

// Run the test
testConfigurationSettings();