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

const router = Router();

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
  /^always respond as the room bot.*$/i
];

const latestFactsStmt = db.prepare(`
  SELECT p.*, f.wiki_title, f.wiki_url, f.discogs_id, f.discogs_type, f.mb_artist_id,
         f.mb_releasegroup_count, f.cover_url
  FROM plays p
  LEFT JOIN facts f ON f.play_id = p.id
  ORDER BY p.id DESC LIMIT 1
`);

function shouldFetchMusicFacts(intent, message, _metadata) {
  if (intent !== "music_question") return false;
  const normalized = (message || "").toLowerCase().trim();
  if (!normalized) return false;
  return isMusicQuery(normalized);
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
    console.error("[CHAT] Failed to fetch latest room facts", err);
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

function sanitizeAssistantText(text) {
  if (!text) return "";
  const cleaned = text
    .split(/\r?\n/)
    .filter((line) => !INTERNAL_LINE_PATTERNS.some((pattern) => pattern.test(line.trim())))
    .join("\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
  return cleaned;
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
    console.error("[CHAT] error loading user profile", err);
    // Continue without profile if there's an error
  }

  // 3) Get latest user message text for classification
  const lastUserMessage = [...messages]
    .reverse()
    .find((m) => m.role === "user")?.content;

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
        console.log(`[CHAT] Enriched music query with ${musicFacts.factCount} fact(s)`);
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
      console.error("[CHAT] Error enriching music query:", err.message);
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
    const { text, raw } = await callProvider(model, {
      messages,
      systemPrompt: mergedSystemPrompt || undefined,
      temperature,
      maxTokens
    });

    const baseContent = sanitizeAssistantText(text) || text || "";
    const toolSummary = buildToolDisplaySummary(toolArtifacts);
    const assistantContent = weaveToolSummaries(baseContent, toolSummary) || baseContent;

    // 7) Update user profile with the new mood (upsert to DB)
    if (userProfile && user_id !== "anonymous") {
      try {
        upsertUserProfile(user_id, { current_mood: mood });
      } catch (err) {
        // Don't fail the request if profile update fails
        console.error("[CHAT] error updating user profile", err);
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
    console.error("[CHAT] error calling provider", err);
    res.status(502).json({ error: "Provider call failed", detail: err.message });
  }
});

export default router;
