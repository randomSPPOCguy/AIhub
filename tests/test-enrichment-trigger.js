// test-enrichment-trigger.js
// Test script to verify enrichment trigger logic

import { cfg } from "./src/config.js";

// Copy the stopwords set from chatRouter.js
const ENRICHMENT_STOPWORDS = new Set([
  "a",
  "an",
  "and",
  "are",
  "as",
  "at",
  "be",
  "bot",
  "can",
  "could",
  "for",
  "have",
  "help",
  "hi",
  "hey",
  "how",
  "i",
  "if",
  "in",
  "is",
  "it",
  "its",
  "me",
  "my",
  "of",
  "on",
  "please",
  "show",
  "tell",
  "that",
  "the",
  "this",
  "to",
  "what",
  "who",
  "with",
  "would",
  "you",
  "your"
]);

function stripBotPrefixForEnrichment(message = "") {
  if (typeof message !== "string") {
    return { text: "", normalized: "", hadBotPrefix: false };
  }

  let trimmed = message.trim();
  if (!trimmed) {
    return { text: "", normalized: "", hadBotPrefix: false };
  }

  let hadBotPrefix = false;
  const lowerTrimmed = trimmed.toLowerCase();

  console.log("  🔍 Checking bot prefix...");
  console.log(`  - Input: "${trimmed}"`);
  console.log(`  - Lowercase: "${lowerTrimmed}"`);
  console.log(`  - Bot keywords: ${JSON.stringify(cfg.botKeywords)}`);

  for (const botKeyword of cfg.botKeywords || []) {
    const candidate = botKeyword?.toLowerCase();
    if (!candidate) continue;

    console.log(`  - Checking keyword: "${candidate}"`);
    if (lowerTrimmed.startsWith(candidate)) {
      const nextChar = lowerTrimmed.charAt(candidate.length);
      console.log(`  - Starts with "${candidate}"! Next char: "${nextChar}"`);
      if (!nextChar || !/[a-z0-9]/i.test(nextChar)) {
        console.log(`  ✅ Bot prefix detected: "${candidate}"`);
        trimmed = trimmed.slice(botKeyword.length);
        trimmed = trimmed.replace(/^[\s,:;@#-]+/, "");
        hadBotPrefix = true;
        break;
      } else {
        console.log(`  ❌ Next char is alphanumeric, not a prefix`);
      }
    }
  }

  trimmed = trimmed.replace(/^["'\`\u201c\u201d\u2018\u2019]+/, "").replace(/["'\`\u201c\u201d\u2018\u2019]+$/, "");
  const withoutTrailingPunct = trimmed.replace(/[?!.,]+$/g, "").trim();
  const finalText = withoutTrailingPunct || trimmed.trim();

  console.log(`  - After strip: "${finalText}"`);
  console.log(`  - Had bot prefix: ${hadBotPrefix}`);

  return {
    text: finalText,
    normalized: finalText.toLowerCase(),
    hadBotPrefix
  };
}

function extractEnrichmentKeywords(text = "") {
  console.log("  🔍 Extracting keywords...");
  console.log(`  - Input text: "${text}"`);

  if (!text || typeof text !== "string") {
    return [];
  }

  const lowercase = text.toLowerCase();
  console.log(`  - Lowercase: "${lowercase}"`);

  const noPunct = lowercase.replace(/[^a-z0-9\s]/gi, " ");
  console.log(`  - No punct: "${noPunct}"`);

  const tokens = noPunct.split(/\s+/);
  console.log(`  - Tokens: ${JSON.stringify(tokens)}`);

  const filtered = tokens.filter((token) => {
    if (!token) {
      console.log(`    ❌ "${token}" - empty`);
      return false;
    }
    if (token.length <= 2) {
      console.log(`    ❌ "${token}" - too short (length ${token.length})`);
      return false;
    }
    if (ENRICHMENT_STOPWORDS.has(token)) {
      console.log(`    ❌ "${token}" - in stopwords`);
      return false;
    }
    console.log(`    ✅ "${token}" - KEPT`);
    return true;
  });

  const result = filtered.slice(0, 6);
  console.log(`  - Keywords extracted: ${JSON.stringify(result)}`);

  return result;
}

function evaluateEnrichmentTrigger(intent, message, metadata) {
  console.log("\n📊 Evaluating enrichment trigger...");
  console.log(`- Message: "${message}"`);
  console.log(`- Enrichment enabled: ${cfg.enrich.enabled}`);

  if (!cfg.enrich.enabled) {
    return { shouldEnrich: false, text: "", normalized: "", reason: "disabled" };
  }

  if (metadata?.enrichment_enabled === false) {
    return { shouldEnrich: false, text: "", normalized: "", reason: "room_disabled" };
  }

  const { text, normalized, hadBotPrefix } = stripBotPrefixForEnrichment(message);
  if (!text) {
    return { shouldEnrich: false, text, normalized, reason: "empty_after_strip", hadBotPrefix };
  }

  const keywordFocus = extractEnrichmentKeywords(text);

  console.log("\n📋 Decision factors:");
  console.log(`  - hadBotPrefix: ${hadBotPrefix}`);
  console.log(`  - keywordFocus: ${JSON.stringify(keywordFocus)}`);
  console.log(`  - keywordFocus.length: ${keywordFocus.length}`);
  console.log(`  - Condition (hadBotPrefix && keywordFocus.length > 0): ${hadBotPrefix && keywordFocus.length > 0}`);

  const shouldEnrich = hadBotPrefix && keywordFocus.length > 0;

  return {
    shouldEnrich,
    text,
    normalized,
    reason: hadBotPrefix && keywordFocus.length > 0 ? "bot_keyword" : "none",
    meta: {
      hadBotPrefix,
      keywords: keywordFocus
    }
  };
}

// Test cases
const testCases = [
  "bot tell me about Radiohead",
  "@bot who is Nirvana",
  "bot Radiohead",
  "tell me about Radiohead",
  "bot"
];

console.log("🧪 Testing Enrichment Trigger Logic\n");
console.log("=".repeat(60));

for (const testCase of testCases) {
  console.log(`\n\n🔬 TEST: "${testCase}"`);
  console.log("=".repeat(60));

  const result = evaluateEnrichmentTrigger("chat", testCase, {});

  console.log("\n✨ RESULT:");
  console.log(`  - shouldEnrich: ${result.shouldEnrich}`);
  console.log(`  - reason: ${result.reason}`);
  console.log(`  - text: "${result.text}"`);
  console.log(`  - keywords: ${JSON.stringify(result.meta?.keywords)}`);
}

console.log("\n\n" + "=".repeat(60));
console.log("✅ Test complete!");
