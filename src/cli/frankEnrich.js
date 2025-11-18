// src/cli/frankEnrich.js
// CLI command for testing enrichment service

import { callEnrichment } from "../services/enrichmentClient.js";
import { randomUUID } from "node:crypto";

function parseArgs() {
  const args = process.argv.slice(2);
  const parsed = {
    text: null,
    room: null,
    providers: ["wikipedia", "musicbrainz"],
    language: "en"
  };

  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    if (arg === "--text" && i + 1 < args.length) {
      parsed.text = args[++i];
    } else if (arg === "--room" && i + 1 < args.length) {
      parsed.room = args[++i];
    } else if (arg === "--providers" && i + 1 < args.length) {
      parsed.providers = args[++i].split(",").map((p) => p.trim());
    } else if (arg === "--language" && i + 1 < args.length) {
      parsed.language = args[++i];
    } else if (arg === "--help" || arg === "-h") {
      console.log(`
Usage: node src/cli/frankEnrich.js [options]

Options:
  --text <text>        Text to enrich (required)
  --room <roomId>      Room ID (optional)
  --providers <list>   Comma-separated provider list (default: wikipedia,musicbrainz)
  --language <lang>    Language code (default: en)
  --help, -h           Show this help message

Example:
  node src/cli/frankEnrich.js --text "Kendrick Lamar"
  node src/cli/frankEnrich.js --text "Tell me about Radiohead" --room "room-123"
`);
      process.exit(0);
    }
  }

  return parsed;
}

async function main() {
  const args = parseArgs();

  if (!args.text) {
    console.error("Error: --text is required");
    console.error("Use --help for usage information");
    process.exit(1);
  }

  const traceId = randomUUID();
  console.log(`[ENRICH] Calling enrichment service...`);
  console.log(`[ENRICH] Text: "${args.text}"`);
  console.log(`[ENRICH] Trace ID: ${traceId}`);
  console.log("");

  try {
    const room = args.room ? { id: args.room } : undefined;
    const hints = {
      language: args.language,
      providers: args.providers
    };

    const result = await callEnrichment({
      text: args.text,
      room,
      hints,
      traceId
    });

    if (!result) {
      console.error("[ENRICH] ✗ Enrichment failed or returned no data");
      process.exit(1);
    }

    // Print full JSON response
    console.log("=== Enrichment Response ===");
    console.log(JSON.stringify(result, null, 2));
    console.log("");

    // Print key metrics
    console.log("=== Key Metrics ===");
    console.log(`Confidence:        ${result.meta?.confidence ?? "N/A"}`);
    console.log(`Cache Status:      ${result.meta?.cache_status ?? "N/A"}`);
    console.log(`Enrichment Time:   ${result.meta?.enrichment_time_ms ?? "N/A"} ms`);
    console.log(`Partial:           ${result.meta?.partial ?? "N/A"}`);
    console.log(`Subjects Count:    ${result.subjects?.length ?? 0}`);
    console.log(`Facts Count:       ${result.facts?.length ?? 0}`);
    console.log(`Keywords Count:    ${result.keywords?.length ?? 0}`);
    console.log(`Sources Count:     ${result.sources?.length ?? 0}`);

    if (result.subjects && result.subjects.length > 0) {
      console.log("");
      console.log("=== Subjects ===");
      result.subjects.forEach((subject, idx) => {
        console.log(`${idx + 1}. ${subject.name} (${subject.type})`);
        if (subject.ids && Object.keys(subject.ids).length > 0) {
          console.log(`   IDs: ${JSON.stringify(subject.ids)}`);
        }
        if (subject.urls && Object.keys(subject.urls).length > 0) {
          console.log(`   URLs: ${JSON.stringify(subject.urls)}`);
        }
      });
    }

    if (result.facts && result.facts.length > 0) {
      console.log("");
      console.log("=== Facts ===");
      result.facts.forEach((fact, idx) => {
        const source = result.sources?.[idx];
        const sourceText = source ? ` [${source.provider}]` : "";
        console.log(`${idx + 1}. ${fact}${sourceText}`);
      });
    }
  } catch (error) {
    console.error(`[ENRICH] ✗ Error: ${error.message}`);
    process.exit(1);
  }
}

main().catch((error) => {
  console.error(`[ENRICH] ✗ Fatal error: ${error.message}`);
  process.exit(1);
});

