import { Router } from "express";
import { db } from "../db/connection.js";
import { getActiveModel, getModelById, setActiveModel } from "../services/modelRegistry.js";
import { callProvider } from "../services/aiProviders.js";
import {
  buildModelOverviewPayload,
  buildCloudModelsPayload,
  buildLocalModelsPayload
} from "../services/modelSummary.js";
import {
  buildRoomContextPrompt,
  buildUserProfilePrompt,
  buildSystemPrompt,
  mergeSystemPrompts
} from "../services/promptBuilder.js";
import {
  getOrCreateUserProfile,
  upsertUserProfile,
  updateUserMood
} from "../services/userProfiles.js";
import { classifyMoodAndIntent } from "../services/classifier.js";
import { enrichMusicQuery, isMusicQuery } from "../services/musicKnowledge.js";
import { callEnrichment } from "../services/enrichmentClient.js";
import { getTemperature } from "../cli/temperatureConfig.js";
import { getAllModelParams } from "../cli/modelTuning.js";
import { randomUUID } from "node:crypto";
import { cfg } from "../config.js";
import { logger } from "../utils/logger.js";

const router = Router();

const chatInfo = (message, meta) => logger.info(`[CHAT] ${message}`, meta);
const chatWarn = (message, meta) => logger.warn(`[CHAT] ${message}`, meta);
const chatError = (message, meta) => logger.error(`[CHAT] ${message}`, meta);
const chatDebug = (message, meta) => logger.debug(`[CHAT] ${message}`, meta);
const enrichInfo = (message, meta) => logger.info(`[ENRICH] ${message}`, meta);
const enrichWarn = (message, meta) => logger.warn(`[ENRICH] ${message}`, meta);
const enrichError = (message, meta) => logger.error(`[ENRICH] ${message}`, meta);

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

// Conversation history store: { user_id: { messages: [...], lastActivity: timestamp } }
const conversationHistory = new Map();
const MAX_HISTORY_PER_USER = 10; // Keep last 10 messages per user
const CONVERSATION_TIMEOUT_MS = 13000; // Reset conversation after 13 seconds of inactivity

function getConversationHistory(userId) {
  if (!conversationHistory.has(userId)) {
    conversationHistory.set(userId, { messages: [], lastActivity: Date.now() });
    return [];
  }

  const userData = conversationHistory.get(userId);
  const timeSinceLastActivity = Date.now() - userData.lastActivity;

  // Reset conversation if timeout exceeded
  if (timeSinceLastActivity > CONVERSATION_TIMEOUT_MS) {
    chatDebug("Conversation timeout - resetting history", {
      userId,
      inactiveMs: timeSinceLastActivity
    });
    userData.messages = [];
    userData.lastActivity = Date.now();
    return [];
  }

  return userData.messages;
}

function addToHistory(userId, role, content) {
  if (!conversationHistory.has(userId)) {
    conversationHistory.set(userId, { messages: [], lastActivity: Date.now() });
  }

  const userData = conversationHistory.get(userId);
  const timeSinceLastActivity = Date.now() - userData.lastActivity;

  // Reset if timeout exceeded
  if (timeSinceLastActivity > CONVERSATION_TIMEOUT_MS) {
    chatDebug("Conversation timeout - starting new conversation", {
      userId,
      inactiveMs: timeSinceLastActivity
    });
    userData.messages = [];
  }

  userData.messages.push({ role, content, timestamp: Date.now() });
  userData.lastActivity = Date.now();

  // Keep only last MAX_HISTORY_PER_USER messages
  if (userData.messages.length > MAX_HISTORY_PER_USER) {
    userData.messages.shift();
  }

  chatDebug("Conversation history updated", {
    userId,
    entries: userData.messages.length,
    timeoutIn: `${(CONVERSATION_TIMEOUT_MS / 1000).toFixed(1)}s`
  });
}

function interpretSlashCommand(content) {
  if (typeof content !== "string") return null;
  const trimmed = content.trim();
  if (!trimmed.startsWith("/")) return null;
  const parts = trimmed.split(/\s+/).filter(Boolean);
  if (!parts.length) return null;
  const base = parts[0].toLowerCase();
  if (base === "/local") return { action: "local" };
  if (base === "/cloud") return { action: "cloud" };
  if (base !== "/models" && base !== "/model") return null;
  if (parts.length === 1) return { action: "overview" };
  const next = parts[1].toLowerCase();
  const normalized = next.replace(/^\//, "");
  if (normalized === "list") return { action: "overview" };
  if (normalized === "local") return { action: "local" };
  if (normalized === "cloud") return { action: "cloud" };
  if (normalized === "downloads" || normalized === "download") {
    return { action: "local" };
  }
  if (normalized === "set") {
    const target = parts[2];
    if (!target) return { action: "error", error: "id is required" };
    return { action: "select", target };
  }
  return { action: "select", target: parts[1] };
}

function findModelCommand(messages) {
  const reversed = [...messages].reverse();
  for (const message of reversed) {
    if (message.role === "user") {
      const result = interpretSlashCommand(message.content);
      if (result) return result;
      return null;
    }
  }
  return null;
}

const LATEST_FACTS_KEYWORDS = [
  "what's playing",
  "what is playing",
  "whats playing",
  "now playing",
  "current song",
  "current track",
  "last song",
  "last track",
  "what just played",
  "what song is this",
  "tell me about this song",
  "give me facts",
  "latest facts",
  "room facts"
];

const INTERNAL_LINE_PATTERNS = [
  /^===.*===\s*$/i,
  /^use these facts.*$/i,
  /^always respond as the room bot.*$/i,
  /^always respond as.*$/i,
  /^you are the ai hub room assistant.*$/i,
  /^use the provided metadata.*$/i,
  /^room:\s*id=/i,
  /^user:\s*id=/i,
  /^current user_mood:/i,
  /^user profile:/i,
  /^favorite genres:/i,
  /^favorite artists:/i,
  /^tone_preference=/i,
  /^notes:/i,
  /^now playing:/i,
  /^djs on stage:/i,
  /^listeners on dancefloor:/i,
  /^last event:/i
];

const latestFactsStmt = db.prepare(`
  SELECT p.*, f.wiki_title, f.wiki_url, f.discogs_id, f.discogs_type, f.mb_artist_id,
         f.mb_releasegroup_count, f.cover_url
  FROM plays p
  LEFT JOIN facts f ON f.play_id = p.id
  ORDER BY p.id DESC LIMIT 1
`);

function shouldFetchMusicFacts(intent, message, _metadata) {
  // Check if message is music-related regardless of intent classification
  const normalized = (message || "").toLowerCase().trim();
  if (!normalized) return false;

  // Use isMusicQuery to detect music-related content
  const isMusicRelated = isMusicQuery(normalized);
  if (isMusicRelated) {
    chatInfo("Music query detected", {
      snippet: `${message.substring(0, 60)}${message.length > 60 ? "..." : ""}`
    });
  }
  return isMusicRelated;
}

const SHORT_SUBJECT_BANNED_PHRASES = new Set(
  [
    "hi",
    "hello",
    "hey",
    "hi there",
    "hello there",
    "hey there",
    "yo",
    "sup",
    "whats up",
    "what's up",
    "good morning",
    "good afternoon",
    "good evening",
    "good night",
    "goodnight",
    "thanks",
    "thank you",
    "thankyou",
    "ty",
    "tysm",
    "thx",
    "ok",
    "okay",
    "k",
    "kk",
    "gm",
    "gn",
    "hey bot",
    "hello bot",
    "hi bot",
    "thanks bot",
    "thank you bot",
    "bot"
  ].map((phrase) => phrase.toLowerCase())
);

const SHORT_SUBJECT_IGNORED_WORDS = new Set(
  [
    "the",
    "a",
    "an",
    "of",
    "and",
    "for",
    "to",
    "in",
    "on",
    "at",
    "by",
    "from",
    "with",
    "feat",
    "featuring",
    "ft",
    "vs",
    "x",
    "&",
    "pt",
    "part",
    "vol",
    "volume"
  ].map((word) => word.toLowerCase())
);

const SHORT_SUBJECT_SMALL_TALK_WORDS = new Set(
  [
    "hi",
    "hello",
    "hey",
    "yo",
    "sup",
    "whats",
    "what's",
    "up",
    "there",
    "thanks",
    "thank",
    "thankyou",
    "ty",
    "tysm",
    "thx",
    "ok",
    "okay",
    "k",
    "kk",
    "gm",
    "gn",
    "morning",
    "afternoon",
    "evening",
    "night",
    "buddy",
    "pal",
    "bro",
    "dude",
    "man",
    "mate",
    "ya",
    "you",
    "u",
    "ur",
    "me",
    "im",
    "i'm",
    "bot",
    "lol",
    "haha"
  ].map((word) => word.toLowerCase())
);

const TOPIC_KEYWORDS = [
  "who is",
  "who was",
  "what is",
  "what was",
  "tell me about",
  "information about",
  "about",
  "what genre",
  "genre is",
  "history of",
  "facts about"
];

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

  for (const botKeyword of cfg.botKeywords || []) {
    const candidate = botKeyword?.toLowerCase();
    if (!candidate) continue;

    // Use regex with word boundary to avoid partial matches (e.g. "bot" matching "both")
    const regex = new RegExp(`^${candidate}\\b`, "i");
    if (regex.test(trimmed)) {
      // Remove the keyword and any following punctuation/whitespace
      trimmed = trimmed.replace(regex, "").trim();
      // Also remove leading punctuation like comma or colon if present
      trimmed = trimmed.replace(/^[,:]\s*/, "");
      hadBotPrefix = true;
      break; // Only strip one prefix
    }
  }

  trimmed = trimmed.replace(/^[\"'`\u201c\u201d\u2018\u2019]+/, "").replace(/[\"'`\u201c\u201d\u2018\u2019]+$/, "");
  const withoutTrailingPunct = trimmed.replace(/[?!.,]+$/g, "").trim();
  const finalText = withoutTrailingPunct || trimmed.trim();

  return {
    text: finalText,
    normalized: finalText.toLowerCase(),
    hadBotPrefix
  };
}

function extractEnrichmentKeywords(text = "") {
  if (!text || typeof text !== "string") {
    return [];
  }
  return text
    .toLowerCase()
    .replace(/[^a-z0-9\s]/gi, " ")
    .split(/\s+/)
    .filter((token) => token && token.length > 2 && !ENRICHMENT_STOPWORDS.has(token))
    .slice(0, 6);
}

function detectShortSubjectQuery(text) {
  const normalized = (text || "").toLowerCase().trim();
  if (!normalized) {
    return { isSubject: false, reason: "empty" };
  }

  if (SHORT_SUBJECT_BANNED_PHRASES.has(normalized)) {
    return { isSubject: false, reason: "banned_phrase" };
  }

  const tokens = normalized.split(/\s+/).filter(Boolean);
  if (!tokens.length) {
    return { isSubject: false, reason: "no_tokens" };
  }

  const filteredTokens = tokens.filter((token) => !SHORT_SUBJECT_IGNORED_WORDS.has(token));
  const candidateTokens = filteredTokens.length ? filteredTokens : tokens;

  if (!candidateTokens.length) {
    return { isSubject: false, reason: "no_meaningful_tokens" };
  }

  if (candidateTokens.length > 4) {
    return { isSubject: false, reason: "too_many_words" };
  }

  const hasNonSmallTalk = candidateTokens.some((token) => !SHORT_SUBJECT_SMALL_TALK_WORDS.has(token));
  if (!hasNonSmallTalk) {
    return { isSubject: false, reason: "small_talk_only" };
  }

  const hasLetters = candidateTokens.some((token) => /[a-z]/i.test(token));
  if (!hasLetters) {
    return { isSubject: false, reason: "no_letters" };
  }

  return {
    isSubject: true,
    tokens: candidateTokens
  };
}

function evaluateEnrichmentTrigger(intent, message, metadata) {
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

  const isMusicRelated = isMusicQuery(normalized);
  const hasTopicQuery = TOPIC_KEYWORDS.some((keyword) => normalized.includes(keyword));
  const shortSubject = detectShortSubjectQuery(text);
  const keywordFocus = extractEnrichmentKeywords(text);

  const shouldEnrich =
    isMusicRelated || hasTopicQuery || shortSubject.isSubject || (hadBotPrefix && keywordFocus.length > 0);

  return {
    shouldEnrich,
    text,
    normalized,
    reason: isMusicRelated
      ? "music_keyword"
      : hasTopicQuery
        ? "topic_keyword"
        : shortSubject.isSubject
          ? "short_subject"
          : hadBotPrefix && keywordFocus.length > 0
            ? "bot_keyword"
            : "none",
    meta: {
      hadBotPrefix,
      shortSubjectReason: shortSubject.reason,
      shortSubjectTokens: shortSubject.tokens,
      keywords: keywordFocus
    }
  };
}

function shouldCallEnrichment(intent, message, metadata) {
  return evaluateEnrichmentTrigger(intent, message, metadata).shouldEnrich;
}

function formatEnrichmentLogText(text = "") {
  if (!text) return "";
  const compact = text.replace(/\s+/g, " ").trim();
  if (compact.length <= 120) {
    return compact;
  }
  return `${compact.slice(0, 117)}...`;
}

function formatEnrichmentPrompt(enrichmentResponse) {
  if (!enrichmentResponse) return null;

  const lines = ["=== ENRICHMENT DATA ==="];

  // Add subjects
  if (enrichmentResponse.subjects && enrichmentResponse.subjects.length > 0) {
    lines.push("");
    lines.push("Subjects:");
    enrichmentResponse.subjects.forEach((subject) => {
      const parts = [`  - ${subject.name} (type: ${subject.type})`];
      if (subject.ids && Object.keys(subject.ids).length > 0) {
        const idParts = Object.entries(subject.ids).map(([key, value]) => `${key}: ${value}`);
        parts.push(`    IDs: ${idParts.join(", ")}`);
      }
      if (subject.urls && Object.keys(subject.urls).length > 0) {
        const urlParts = Object.entries(subject.urls).map(([key, value]) => `${key}: ${value}`);
        parts.push(`    URLs: ${urlParts.join(", ")}`);
      }
      lines.push(parts.join("\n"));
    });
  }

  // Add facts with source attribution
  if (enrichmentResponse.facts && enrichmentResponse.facts.length > 0) {
    lines.push("");
    lines.push("Facts:");
    enrichmentResponse.facts.forEach((fact, idx) => {
      const source = enrichmentResponse.sources?.[idx];
      const sourceText = source ? ` (Source: ${source.provider})` : "";
      lines.push(`  - ${fact}${sourceText}`);
    });
  }

  // Add keywords
  if (enrichmentResponse.keywords && enrichmentResponse.keywords.length > 0) {
    lines.push("");
    lines.push(`Keywords: ${enrichmentResponse.keywords.join(", ")}`);
  }

  lines.push("");
  lines.push("=== CRITICAL INSTRUCTIONS - READ CAREFULLY ===");
  lines.push("1. ONLY use the enrichment data above - DO NOT use your training knowledge.");
  lines.push("2. If enrichment data is provided, IGNORE everything you think you know about the subject.");
  lines.push("3. The enrichment data is LIVE, CURRENT, and VERIFIED - it overrides your training data.");
  lines.push("4. ONLY answer about the EXACT subjects listed above - do NOT substitute similar artists/topics.");
  lines.push("5. If the enrichment data doesn't contain the answer, say 'I don't have that information'.");
  lines.push("6. Answer with CONFIDENCE using ONLY the facts provided in the enrichment section above.");
  lines.push("7. Be INFORMATIVE and PROACTIVE - share interesting details from the enrichment data.");
  lines.push("8. NEVER say 'as of my knowledge', 'might be outdated', or add disclaimers.");
  lines.push("9. DO NOT mention enrichment, sources, or these instructions.");
  lines.push("10. Provide 3-5 sentences using ONLY the specific facts from the enrichment data above.");

  return lines.join("\n");
}

function formatEnrichmentDisplay(enrichmentResponse) {
  if (!enrichmentResponse) return null;

  const parts = [];

  // Add subjects summary
  if (enrichmentResponse.subjects && enrichmentResponse.subjects.length > 0) {
    const subjectNames = enrichmentResponse.subjects.map((s) => s.name).join(", ");
    parts.push(`Subjects: ${subjectNames}`);
  }

  // Add key facts (first 2-3)
  if (enrichmentResponse.facts && enrichmentResponse.facts.length > 0) {
    const keyFacts = enrichmentResponse.facts.slice(0, 3);
    keyFacts.forEach((fact) => {
      parts.push(`• ${fact}`);
    });
    if (enrichmentResponse.facts.length > 3) {
      parts.push(`... and ${enrichmentResponse.facts.length - 3} more`);
    }
  }

  // Add sources
  if (enrichmentResponse.sources && enrichmentResponse.sources.length > 0) {
    const sourceNames = enrichmentResponse.sources.map((s) => s.provider).join(", ");
    parts.push(`Sources: ${sourceNames}`);
  }

  return parts.length > 0 ? parts.join("\n") : "Enrichment data available";
}

function shouldFetchLatestFacts(message = "", metadata = {}) {
  const normalized = (message || "").toLowerCase();
  if (!normalized.trim()) return false;
  if (LATEST_FACTS_KEYWORDS.some((keyword) => normalized.includes(keyword))) {
    return true;
  }
  if (metadata?.now_playing && /\bthis (song|track)\b/.test(normalized)) {
    return true;
  }
  return false;
}

function fetchLatestRoomFacts() {
  try {
    return latestFactsStmt.get();
  } catch (err) {
    chatError("Failed to fetch latest room facts", { error: err?.message || String(err) });
    return null;
  }
}

function formatLatestFactsPrompt(row) {
  if (!row) return null;
  const lines = [
    "=== LOCAL ROOM FACTS ===",
    row.title && row.artist ? `Most recent track: "${row.title}" by ${row.artist}.` : null,
    row.album ? `Album: ${row.album}` : null,
    row.year ? `Year: ${row.year}` : null,
    row.genre ? `Genre: ${row.genre}` : null,
    row.wiki_title
      ? `Wiki entry: ${row.wiki_title}${row.wiki_url ? ` (${row.wiki_url})` : ""}`
      : null,
    row.cover_url ? `Cover art: ${row.cover_url}` : null,
    row.mb_artist_id ? `MusicBrainz artist id: ${row.mb_artist_id}` : null,
    "Use this context whenever the user asks about what played last or what is currently playing."
  ].filter(Boolean);
  return lines.join("\n");
}

function formatLatestFactsForUser(row) {
  if (!row) return "";
  const parts = [];
  if (row.title && row.artist) {
    parts.push(`Latest play: "${row.title}" by ${row.artist}.`);
  }
  if (row.album) {
    parts.push(`Album: ${row.album}.`);
  }
  if (row.year) {
    parts.push(`Year: ${row.year}.`);
  }
  if (row.genre) {
    parts.push(`Genre: ${row.genre}.`);
  }
  const links = [];
  if (row.wiki_url) {
    links.push(`Wiki: ${row.wiki_url}`);
  }
  if (row.cover_url) {
    links.push(`Cover: ${row.cover_url}`);
  }
  if (links.length) {
    parts.push(links.join(" | "));
  }
  return parts.join(" ").trim();
}

function stripPromptSections(text = "") {
  return text
    .split(/\r?\n/)
    .filter((line) => !/^=+.*=+\s*$/.test(line.trim()))
    .join("\n")
    .trim();
}

function summarizeMusicFactsForUser(musicFacts) {
  if (!musicFacts) return null;
  const summary = musicFacts.displayText || stripPromptSections(musicFacts.factsText || "");
  if (!summary) return null;
  return summary.includes("\n") ? `Music facts:\n${summary}` : `Music facts: ${summary}`;
}

function buildToolDisplaySummary(toolArtifacts) {
  const sections = toolArtifacts
    .map((artifact) => artifact.display)
    .filter((section) => section && section.trim().length > 0);
  return sections.join("\n\n").trim();
}

export function sanitizeAssistantText(text) {
  if (!text) return { clean: "", dashSegments: [] };

  // Remove anything after "---" separator that looks like system instructions
  // This catches cases where the model appends system prompts after a separator
  // Remove anything after "---" separator that looks like system instructions
  // This catches cases where the model appends system prompts after a separator
  let cleaned = text.replace(/---+\s*(?:you are|always respond|use the provided|###\s*Expert-Level|###\s*Example|===+\s*INSTRUCTIONS)[\s\S]*$/gi, "");

  // Aggressively remove instruction blocks
  cleaned = cleaned.replace(/###\s*Expert-Level Instruction[\s\S]*$/gi, "");
  cleaned = cleaned.replace(/===+\s*INSTRUCTIONS[\s\S]*$/gi, "");
  cleaned = cleaned.replace(/===+\s*ENRICHMENT DATA[\s\S]*$/gi, "");

  // First, filter out lines matching internal patterns
  const dashSegments = [];
  cleaned = cleaned
    .split(/\r?\n/)
    .filter((line) => {
      const trimmed = line.trim();
      if (/^[-‐—]{3,}\s*$/.test(trimmed)) {
        dashSegments.push(trimmed);
        return false;
      }
      return !INTERNAL_LINE_PATTERNS.some((pattern) => pattern.test(trimmed));
    })
    .join("\n");

  // Remove any remaining context blocks that start with "===" (even mid-text)
  cleaned = cleaned.replace(/===\s*CONTEXT\s*===[\s\S]*?(?=\n\n|$)/gi, "");
  cleaned = cleaned.replace(/===\s*[A-Z\s]+\s*===[\s\S]*?(?=\n\n|$)/gi, "");

  // Remove common metadata patterns that might appear mid-sentence
  cleaned = cleaned.replace(/\b(room|user):\s*id=[a-f0-9-]+,?\s*source=\w+\s*/gi, "");
  cleaned = cleaned.replace(/\bcurrent user_mood:\s*\w+\s*/gi, "");
  cleaned = cleaned.replace(/\buser profile:\s*tone_preference=\w+\s*/gi, "");
  cleaned = cleaned.replace(/\bfavorite (genres|artists):\s*[^\n]+\n?/gi, "");

  // Remove base behavior prompts that leaked through
  cleaned = cleaned.replace(/you are the ai hub room assistant[\s\S]*?(?=\n\n|$)/gi, "");
  cleaned = cleaned.replace(/use the provided metadata[\s\S]*?(?=\n\n|$)/gi, "");

  // Remove stray "Favorite artists" or "Favorite genres" that leak at the end
  cleaned = cleaned.replace(/\s*favorite (artists|genres)\s*$/gi, "");

  // Remove leaked "Music facts:" or "user:" prefixes
  cleaned = cleaned.replace(/-----+\s*user:[\s\S]*$/gi, "");
  cleaned = cleaned.replace(/\bmusic facts:\s*[^\n]*\n?/gi, "");

  // Clean up excessive whitespace
  cleaned = cleaned
    .replace(/\n{3,}/g, "\n\n")
    .replace(/^\s+|\s+$/gm, "")  // Trim each line
    .trim();

  const leakMarkers = [
    cleaned.search(/instruction\s*\d+/i),
    cleaned.search(/communication style:/i),
    cleaned.search(/bot,\s*I'm planning/i),
    cleaned.search(/bot:\s*absolutely/i)
  ].filter((idx) => idx >= 0);

  if (leakMarkers.length > 0) {
    const cutIndex = Math.min(...leakMarkers);
    cleaned = cleaned.slice(0, cutIndex).trim();
  }

  return { clean: cleaned, dashSegments };
}

function weaveToolSummaries(base, additions) {
  const safeBase = (base || "").trim();
  const safeAdditions = (additions || "").trim();
  if (!safeAdditions) return safeBase;
  if (!safeBase) return safeAdditions;
  const firstSentence = safeAdditions.split(/[.!?]/)[0]?.toLowerCase();
  if (firstSentence && safeBase.toLowerCase().includes(firstSentence)) {
    return safeBase;
  }
  return `${safeBase}\n\n${safeAdditions}`;
}

router.post("/chat", async (req, res) => {
  const {
    messages = [],
    modelId,
    systemPrompt,
    temperature,
    maxTokens,
    topP,
    topK,
    repetitionPenalty,
    frequencyPenalty,
    presencePenalty,
    metadata
  } = req.body || {};

  if (!Array.isArray(messages) || messages.length === 0) {
    return res.status(400).json({ error: "messages array is required" });
  }

  const toolArtifacts = [];

  const command = findModelCommand(messages);
  if (command) {
    if (command.action === "error") {
      return res.status(400).json({ error: command.error || "Invalid model command" });
    }
    if (command.action === "overview") {
      return res.json(buildModelOverviewPayload());
    }
    if (command.action === "local") {
      return res.json(buildLocalModelsPayload({ includeHardware: true }));
    }
    if (command.action === "cloud") {
      return res.json(buildCloudModelsPayload());
    }
    if (command.action === "select" && command.target) {
      try {
        const updated = setActiveModel(command.target);
        return res.json({
          object: "model.selected",
          activeModel: updated
        });
      } catch (err) {
        return res.status(400).json({ error: err.message });
      }
    }
  }

  // 1) Get user_id and username from metadata
  const user_id = metadata?.user_id || "anonymous";
  const username = metadata?.username || null;

  // 2) Load or create user profile
  let userProfile = null;
  try {
    userProfile = getOrCreateUserProfile(user_id, username);
  } catch (err) {
    chatError("Error loading user profile", {
      error: err?.message || String(err),
      userId: user_id
    });
    // Continue without profile if there's an error
  }

  // 3) Get latest user message text for classification
  const lastUserMessage = [...messages]
    .reverse()
    .find((m) => m.role === "user")?.content;

  // 3.5) Add user message to conversation history
  if (lastUserMessage && user_id !== "anonymous") {
    addToHistory(user_id, "user", lastUserMessage);
  }

  // 4) Classify mood and intent
  const { mood, intent } = classifyMoodAndIntent(lastUserMessage || "");

  // 5) Update profile with current mood
  if (userProfile) {
    userProfile.current_mood = mood;
  }

  // 5.5) Enrich music queries with facts from MusicBrainz/Wikipedia when intent warrants it
  let musicFacts = null;
  if (shouldFetchMusicFacts(intent, lastUserMessage || "", metadata)) {
    try {
      musicFacts = await enrichMusicQuery(lastUserMessage, metadata);
      if (musicFacts?.factsText) {
        chatInfo("Music query enrichment applied", { factCount: musicFacts.factCount });
        toolArtifacts.push({
          type: "musicFacts",
          prompt: [
            "=== VERIFIED MUSIC FACTS ===",
            musicFacts.factsText,
            "Blend these verified facts into your answer when relevant."
          ]
            .filter(Boolean)
            .join("\n"),
          display: summarizeMusicFactsForUser(musicFacts),
          metadata: {
            factCount: musicFacts.factCount,
            entities: musicFacts.entities
          }
        });
      }
    } catch (err) {
      chatWarn("Error enriching music query", { error: err?.message || String(err) });
      // Continue without facts if there's an error
    }
  }

  // 5.6) Pull the latest harvested room facts when the user asks about the current/last track
  let latestFactsRow = null;
  if (shouldFetchLatestFacts(lastUserMessage || "", metadata)) {
    latestFactsRow = fetchLatestRoomFacts();
    if (latestFactsRow) {
      toolArtifacts.push({
        type: "roomFacts",
        prompt: formatLatestFactsPrompt(latestFactsRow),
        display: formatLatestFactsForUser(latestFactsRow),
        metadata: {
          artist: latestFactsRow.artist,
          title: latestFactsRow.title,
          played_at_utc: latestFactsRow.played_at_utc
        }
      });
    }
  }

  // 5.7) Call enrichment service for structured enrichment data
  let enrichmentData = null;
  const traceId = randomUUID();
  const enrichmentDecision = evaluateEnrichmentTrigger(intent, lastUserMessage || "", metadata);
  if (enrichmentDecision.shouldEnrich) {
    const enrichmentQueryText = enrichmentDecision.text;
    const enrichmentLogText = formatEnrichmentLogText(enrichmentQueryText);
    enrichInfo("Trigger", {
      reason: enrichmentDecision.reason,
      text: enrichmentLogText,
      traceId
    });
    try {
      // Get recent conversation history for context
      const recentHistory = user_id !== "anonymous" ? getConversationHistory(user_id) : [];
      const conversationContext = recentHistory
        .slice(-3) // Last 3 messages for context
        .map(h => `${h.role}: ${h.content}`)
        .join("\n");

      // Build enrichment query with conversation context
      let enrichmentQueryWithContext = enrichmentQueryText;
      if (conversationContext) {
        enrichmentQueryWithContext = `${conversationContext}\nuser: ${enrichmentQueryText}`;
        chatDebug("Adding conversation context to enrichment", {
          contextLines: recentHistory.slice(-3).length,
          traceId
        });
      }

      // Map metadata to EnrichRequest.room format
      const roomContext = {
        ...(metadata?.room_id && { id: metadata.room_id }),
        ...(metadata?.id && !metadata?.room_id && { id: metadata.id }),
        ...(metadata?.topic && { topic: metadata.topic }),
        ...(metadata?.now_playing && {
          now_playing: {
            ...(metadata.now_playing.artist && { artist: metadata.now_playing.artist }),
            ...(metadata.now_playing.track && { track: metadata.now_playing.track })
          }
        })
      };

      const keywordSubjects = (enrichmentDecision.meta?.keywords || []).map((keyword) => ({
        type: "keyword",
        name: keyword
      }));
      if (keywordSubjects.length) {
        enrichInfo("Keyword focus extracted", {
          keywords: keywordSubjects.map((s) => s.name),
          traceId
        });
      }

      const hints = {
        language: "en",
        providers: ["wikipedia", "musicbrainz"],
        ...(keywordSubjects.length && { subjects: keywordSubjects })
      };

      enrichmentData = await callEnrichment({
        text: enrichmentQueryWithContext,
        room: Object.keys(roomContext).length > 0 ? roomContext : undefined,
        hints,
        traceId
      });

      if (enrichmentData) {
        const subjectsCount = enrichmentData.subjects?.length || 0;
        const factsCount = enrichmentData.facts?.length || 0;
        enrichInfo("Success", {
          subjects: subjectsCount,
          facts: factsCount,
          traceId,
          text: enrichmentLogText
        });
        const promptText = formatEnrichmentPrompt(enrichmentData);
        const displayText = formatEnrichmentDisplay(enrichmentData);

        if (promptText) {
          toolArtifacts.push({
            type: "enrichment",
            prompt: promptText,
            display: displayText,
            metadata: {
              confidence: enrichmentData.meta?.confidence,
              cache_status: enrichmentData.meta?.cache_status,
              enrichment_time_ms: enrichmentData.meta?.enrichment_time_ms,
              partial: enrichmentData.meta?.partial,
              subjects_count: enrichmentData.subjects?.length || 0,
              facts_count: enrichmentData.facts?.length || 0
            }
          });
        }
      } else {
        enrichWarn("No enrichment data returned", {
          text: enrichmentLogText,
          traceId
        });
      }
    } catch (err) {
      enrichError("Error in chat router enrichment call", {
        error: err?.message || String(err),
        traceId,
        text: enrichmentLogText
      });
      // Continue without enrichment if there's an error
    }
  }

  // 6) Build comprehensive system prompt using the new buildSystemPrompt
  let mergedSystemPrompt;
  if (userProfile) {
    // Use the full workflow system prompt
    mergedSystemPrompt = buildSystemPrompt({
      userProfile,
      userMood: mood,
      metadata: { ...metadata, user_id, username }
    });

    // Append any explicit systemPrompt if provided
    if (systemPrompt) {
      mergedSystemPrompt = mergeSystemPrompts(mergedSystemPrompt, systemPrompt);
    }
  } else {
    // Fallback to old behavior if no profile
    const systemPrompts = [];

    // Room context from metadata
    if (metadata) {
      const roomContext = buildRoomContextPrompt(metadata);
      if (roomContext) {
        systemPrompts.push(roomContext);
      }
    }

    // Add explicit systemPrompt if provided
    if (systemPrompt) {
      systemPrompts.push(systemPrompt);
    }

    // Merge all system prompts
    mergedSystemPrompt = mergeSystemPrompts(...systemPrompts);
  }

  if (toolArtifacts.length) {
    const supplementalPrompt = toolArtifacts
      .map((artifact) => artifact.prompt)
      .filter((section) => section && section.trim().length > 0)
      .join("\n\n");
    if (supplementalPrompt) {
      mergedSystemPrompt = mergedSystemPrompt
        ? mergeSystemPrompts(mergedSystemPrompt, supplementalPrompt)
        : supplementalPrompt;
    }
  }

  const model = modelId ? getModelById(modelId) : getActiveModel();
  if (!model) return res.status(400).json({ error: "Unknown model selection" });

  try {
    // Get configured model parameters (only returns configured values, not defaults)
    const configuredParams = getAllModelParams();

    // Build effective parameters:
    // 1. Request parameters take priority
    // 2. Configured parameters (from /tune) as fallback
    // 3. If neither, parameter is undefined and provider will use its own defaults
    const effectiveParams = {};

    if (temperature !== undefined) effectiveParams.temperature = temperature;
    else if (configuredParams.temperature !== undefined) effectiveParams.temperature = configuredParams.temperature;

    if (maxTokens !== undefined) effectiveParams.maxTokens = maxTokens;
    else if (configuredParams.maxTokens !== undefined) effectiveParams.maxTokens = configuredParams.maxTokens;

    if (topP !== undefined) effectiveParams.topP = topP;
    else if (configuredParams.topP !== undefined) effectiveParams.topP = configuredParams.topP;

    if (topK !== undefined) effectiveParams.topK = topK;
    else if (configuredParams.topK !== undefined) effectiveParams.topK = configuredParams.topK;

    if (repetitionPenalty !== undefined) effectiveParams.repetitionPenalty = repetitionPenalty;
    else if (configuredParams.repetitionPenalty !== undefined) effectiveParams.repetitionPenalty = configuredParams.repetitionPenalty;

    if (frequencyPenalty !== undefined) effectiveParams.frequencyPenalty = frequencyPenalty;
    else if (configuredParams.frequencyPenalty !== undefined) effectiveParams.frequencyPenalty = configuredParams.frequencyPenalty;

    if (presencePenalty !== undefined) effectiveParams.presencePenalty = presencePenalty;
    else if (configuredParams.presencePenalty !== undefined) effectiveParams.presencePenalty = configuredParams.presencePenalty;

    // Include conversation history for context (but not the current message since it's in messages array)
    let messagesWithHistory = messages;
    if (user_id !== "anonymous") {
      const history = getConversationHistory(user_id);
      // Skip the last message (current one) and get previous messages
      const previousMessages = history.slice(0, -1).map(h => ({ role: h.role, content: h.content }));
      if (previousMessages.length > 0) {
        chatDebug("Including previous messages for context", { userId: user_id, count: previousMessages.length });
        // Prepend history before current messages
        messagesWithHistory = [...previousMessages, ...messages];
      }
    }

    const { text, raw } = await callProvider(model, {
      messages: messagesWithHistory,
      systemPrompt: mergedSystemPrompt || undefined,
      ...effectiveParams
    });

    const { clean: sanitizedText, dashSegments } = sanitizeAssistantText(text);
    if (dashSegments.length) {
      chatDebug("Removed separator lines from assistant output", {
        removedSegments: dashSegments.length
      });
    }
    const baseContent = sanitizedText || text || "";
    const toolSummary = buildToolDisplaySummary(toolArtifacts);
    const assistantContent = weaveToolSummaries(baseContent, toolSummary) || baseContent;

    // 6.5) Add assistant response to conversation history
    if (assistantContent && user_id !== "anonymous") {
      addToHistory(user_id, "assistant", assistantContent);
    }

    // 7) Update user profile with the new mood (upsert to DB)
    if (userProfile && user_id !== "anonymous") {
      try {
        upsertUserProfile(user_id, { current_mood: mood });
      } catch (err) {
        // Don't fail the request if profile update fails
        chatWarn("Error updating user profile", {
          error: err?.message || String(err),
          userId: user_id
        });
      }
    }

    const payload = {
      id: `chatcmpl-${Date.now()}`,
      object: "chat.completion",
      created: Math.floor(Date.now() / 1000),
      model: model.id,
      provider: model.provider,
      choices: [
        {
          index: 0,
          finish_reason: "stop",
          message: {
            role: "assistant",
            content: assistantContent
          }
        }
      ],
      // Include workflow metadata for bots
      workflow: {
        mood,
        intent,
        user_profile: userProfile ? {
          tone_preference: userProfile.tone_preference,
          favorite_genres: userProfile.favorite_genres,
          favorite_artists: userProfile.favorite_artists,
          notes: userProfile.notes,
          current_mood: userProfile.current_mood
        } : null,
        tools: toolArtifacts.map((artifact) => ({
          type: artifact.type,
          metadata: artifact.metadata || null
        }))
      }
    };

    if (req.query.debug === "1") {
      payload.raw = raw;
      if (mergedSystemPrompt) {
        payload.debug = {
          systemPrompt: mergedSystemPrompt,
          metadata: metadata || null,
          mood,
          intent,
          userProfile: userProfile || null,
          toolArtifacts: toolArtifacts.map((artifact) => ({
            type: artifact.type,
            metadata: artifact.metadata || null,
            displayPreview: artifact.display ? artifact.display.slice(0, 400) : null
          }))
        };
      }
    }

    res.json(payload);
  } catch (err) {
    chatError("Error calling provider", { error: err?.message || String(err) });
    res.status(502).json({ error: "Provider call failed", detail: err.message });
  }
});

export default router;
