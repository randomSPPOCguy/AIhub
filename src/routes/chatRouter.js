import { Router } from "express";
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

  // 5.5) Enrich music queries with facts from MusicBrainz/Wikipedia
  let musicFacts = null;
  if (intent === "music_question" && isMusicQuery(lastUserMessage || "")) {
    try {
      musicFacts = await enrichMusicQuery(lastUserMessage, metadata);
      if (musicFacts) {
        console.log(`[CHAT] Enriched music query with ${musicFacts.factCount} fact(s)`);
      }
    } catch (err) {
      console.error("[CHAT] Error enriching music query:", err.message);
      // Continue without facts if there's an error
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

    // Append music facts if available
    if (musicFacts && musicFacts.factsText) {
      mergedSystemPrompt += "\n\n=== AVAILABLE FACTS ===\n" + musicFacts.factsText;
      mergedSystemPrompt += "\n\nUse these facts to answer the user's question. Be specific and cite information from the facts.";
    }

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

  const model = modelId ? getModelById(modelId) : getActiveModel();
  if (!model) return res.status(400).json({ error: "Unknown model selection" });

  try {
    const { text, raw } = await callProvider(model, {
      messages,
      systemPrompt: mergedSystemPrompt || undefined,
      temperature,
      maxTokens
    });

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
            content: text
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
        } : null
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
          userProfile: userProfile || null
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
