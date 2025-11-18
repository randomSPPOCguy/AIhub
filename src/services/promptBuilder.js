import fs from "node:fs";
import path from "node:path";
import { cfg } from "../config.js";
import { logger } from "../utils/logger.js";

function resolveBehaviorPrompt() {
  if (cfg.behaviorPrompt.inline) {
    return cfg.behaviorPrompt.inline.trim();
  }
  if (cfg.behaviorPrompt.file) {
    try {
      const prompt = fs.readFileSync(path.resolve(cfg.behaviorPrompt.file), "utf8");
      if (prompt.trim()) {
        return prompt.trim();
      }
    } catch (err) {
      logger.warn("[PROMPT] Failed to load BOT_BEHAVIOR_PROMPT_FILE", {
        error: err?.message || String(err)
      });
    }
  }
  return "You are the AI Hub room assistant. Use the provided metadata to answer concisely and stay on topic.";
}

const BASE_BEHAVIOR_PROMPT = resolveBehaviorPrompt();

/**
 * Build room context prompt from metadata
 * Converts metadata into a system prompt that provides context about the room, user, and current state
 */

export function buildRoomContextPrompt(metadata) {
  if (!metadata || typeof metadata !== "object") {
    return null;
  }

  const parts = [];

  // Room information
  if (metadata.room_id) {
    const source = metadata.room_source || "unknown";
    parts.push(`You are the AI DJ bot for room ${metadata.room_id} (${source}).`);
  }

  // Current song
  if (metadata.now_playing) {
    const np = metadata.now_playing;
    const songParts = [];
    if (np.artist) songParts.push(np.artist);
    if (np.title) songParts.push(`"${np.title}"`);
    if (np.album) songParts.push(`from "${np.album}"`);
    if (np.year) songParts.push(`(${np.year})`);
    if (songParts.length > 0) {
      parts.push(`Current song: ${songParts.join(" ")}.`);
    }
  }

  // User information
  if (metadata.user_id || metadata.username) {
    const userParts = [];
    if (metadata.username) userParts.push(metadata.username);
    if (metadata.user_id) userParts.push(`(id=${metadata.user_id})`);
    parts.push(`User: ${userParts.join(" ")}.`);
  }

  // Stage (DJs)
  if (metadata.stage && Array.isArray(metadata.stage) && metadata.stage.length > 0) {
    parts.push(`Stage: ${metadata.stage.join(", ")}.`);
  }

  // Dancefloor (users)
  if (
    metadata.dancefloor &&
    Array.isArray(metadata.dancefloor) &&
    metadata.dancefloor.length > 0
  ) {
    parts.push(`Dancefloor: ${metadata.dancefloor.join(", ")}.`);
  }

  // Last event
  if (metadata.last_event) {
    parts.push(`Last event: ${metadata.last_event}.`);
  }

  return parts.length > 0 ? parts.join("\n") : null;
}

/**
 * Build user profile context prompt
 * Adds user preferences, mood, and tone to the system prompt
 */
export function buildUserProfilePrompt(userProfile) {
  if (!userProfile) {
    return null;
  }

  const parts = [];

  if (userProfile.username) {
    parts.push(`User profile for: ${userProfile.username}`);
  }

  if (userProfile.tone_preference) {
    parts.push(`Tone preference: ${userProfile.tone_preference}.`);
  }

  if (userProfile.current_mood) {
    parts.push(`Current mood: ${userProfile.current_mood}.`);
  }

  // Parse and include favorite genres
  if (userProfile.favorite_genres) {
    try {
      const genres =
        typeof userProfile.favorite_genres === "string"
          ? JSON.parse(userProfile.favorite_genres)
          : userProfile.favorite_genres;
      if (Array.isArray(genres) && genres.length > 0) {
        parts.push(`Favorite genres: ${genres.join(", ")}.`);
      }
    } catch (e) {
      // Ignore JSON parse errors
    }
  }

  // Parse and include favorite artists
  if (userProfile.favorite_artists) {
    try {
      const artists =
        typeof userProfile.favorite_artists === "string"
          ? JSON.parse(userProfile.favorite_artists)
          : userProfile.favorite_artists;
      if (Array.isArray(artists) && artists.length > 0) {
        parts.push(`Favorite artists: ${artists.join(", ")}.`);
      }
    } catch (e) {
      // Ignore JSON parse errors
    }
  }

  return parts.length > 0 ? parts.join("\n") : null;
}

/**
 * Merge multiple prompt parts into a single system prompt
 * Filters out null/empty values and joins with double newlines
 */
export function mergeSystemPrompts(...prompts) {
  return prompts.filter((p) => p && typeof p === "string" && p.trim().length > 0).join("\n\n");
}

/**
 * Build a comprehensive system prompt from base behavior, user profile, mood, and metadata
 * This is the main prompt builder function that combines everything for the local model
 * @param {Object} options - Configuration options
 * @param {Object} options.userProfile - User profile object
 * @param {string} options.userMood - Current user mood (negative | neutral | positive)
 * @param {Object} options.metadata - Room and context metadata
 * @returns {string} Complete system prompt
 */
export function buildSystemPrompt({ userProfile, userMood, metadata }) {
  const lines = [];

  // Start with base behavior
  lines.push(BASE_BEHAVIOR_PROMPT);
  lines.push("");

  // Context header
  lines.push("=== CONTEXT ===");

  // Room information
  if (metadata) {
    const {
      room_id,
      room_source,
      now_playing,
      stage,
      dancefloor,
      last_event,
      user_id,
      username,
    } = metadata;

    if (room_id || room_source) {
      lines.push(
        `Room: id=${room_id || "unknown"}, source=${room_source || "unknown"}`
      );
    }

    if (user_id || username) {
      lines.push(
        `User: id=${user_id || "unknown"}, username=${username || "unknown"}`
      );
    }

    if (now_playing) {
      const { artist, title, album, year } = now_playing;
      lines.push(
        `Now playing: "${title || "unknown"}" by ${artist || "unknown artist"}` +
          (album ? ` from album "${album}"` : "") +
          (year ? ` (${year})` : "")
      );
    }

    if (Array.isArray(stage) && stage.length) {
      lines.push(`DJs on stage: ${stage.join(", ")}`);
    }

    if (Array.isArray(dancefloor) && dancefloor.length) {
      lines.push(`Listeners on dancefloor: ${dancefloor.join(", ")}`);
    }

    if (last_event) {
      lines.push(`Last event: ${last_event}`);
    }
  }

  // User mood
  if (userMood) {
    lines.push(`Current user_mood: ${userMood}`);
  }

  // User profile details
  if (userProfile) {
    const { tone_preference, favorite_genres, favorite_artists, notes } = userProfile;

    lines.push(
      `User profile: tone_preference=${tone_preference || "neutral"}`
    );

    // Parse favorite_genres if it's a JSON string
    let genres = favorite_genres;
    if (typeof genres === "string") {
      try {
        genres = JSON.parse(genres);
      } catch {
        genres = [];
      }
    }
    lines.push(
      `Favorite genres: ${
        Array.isArray(genres) && genres.length
          ? genres.join(", ")
          : "none yet"
      }`
    );

    // Parse favorite_artists if it's a JSON string
    let artists = favorite_artists;
    if (typeof artists === "string") {
      try {
        artists = JSON.parse(artists);
      } catch {
        artists = [];
      }
    }
    lines.push(
      `Favorite artists: ${
        Array.isArray(artists) && artists.length
          ? artists.join(", ")
          : "none yet"
      }`
    );

    if (notes) {
      lines.push(`Notes: ${notes}`);
    }
  }

  lines.push("");
  lines.push("Always respond as the room bot based on this context.");

  return lines.join("\n");
}

