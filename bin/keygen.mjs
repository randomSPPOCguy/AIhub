#!/usr/bin/env node
import "../src/db/connection.js";
import { issueApiKey } from "../src/services/apiKeys.js";

function parseArgs(argv) {
  const args = {};
  for (let i = 0; i < argv.length; i++) {
    const token = argv[i];
    if (token === "--label" || token === "-l") {
      args.label = argv[i + 1];
      i++;
    } else if (!args.label) {
      args.label = token;
    }
  }
  return args;
}

const { label } = parseArgs(process.argv.slice(2));
const record = issueApiKey(label || null);
console.log("Generated API key:");
console.log(record.key);
console.log("\nStore this securely; it will not be shown again.");
