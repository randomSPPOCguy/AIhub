import { db } from "../db/connection.js";
import { logger } from "../utils/logger.js";

/**
 * Get user profile by user_id
 * @param {string} userId - The user ID to look up
 * @returns {Object|null} User profile or null if not found
 */
export function getUserProfile(userId) {
  if (!userId) return null;
  const row = db.prepare("SELECT * FROM user_profiles WHERE user_id = ?").get(userId);
  return row || null;
}

/**
 * Get or create a default user profile
 * @param {string} userId - The user ID
 * @param {string} [username] - Optional username
 * @returns {Object} User profile (created if not exists)
 */
export function getOrCreateUserProfile(userId, username = null) {
  if (!userId) return null;
  let profile = getUserProfile(userId);
  if (!profile) {
    // Create default profile
    upsertUserProfile(userId, {
      username: username || null,
      tone_preference: "neutral",
      current_mood: "neutral",
      favorite_genres: [],
      favorite_artists: []
    });
    profile = getUserProfile(userId);
  }
  return profile;
}

/**
 * Upsert (insert or update) user profile
 * @param {string} userId - The user ID (required)
 * @param {Object} updates - Profile updates
 * @param {string} [updates.username] - Username
 * @param {string} [updates.tone_preference] - Tone preference: snarky | neutral | positive
 * @param {string} [updates.current_mood] - Current mood: negative | neutral | positive
 * @param {Array|string} [updates.favorite_genres] - Array of genres or JSON string
 * @param {Array|string} [updates.favorite_artists] - Array of artists or JSON string
 * @param {string} [updates.notes] - Notes
 * @returns {Object} Updated profile
 */
export function upsertUserProfile(userId, updates = {}) {
  if (!userId) {
    throw new Error("user_id is required");
  }

  const existing = getUserProfile(userId);

  // Prepare data
  const username = updates.username !== undefined ? updates.username : existing?.username || null;
  const tone_preference =
    updates.tone_preference !== undefined
      ? updates.tone_preference
      : existing?.tone_preference || "neutral";
  const current_mood =
    updates.current_mood !== undefined ? updates.current_mood : existing?.current_mood || "neutral";
  const notes = updates.notes !== undefined ? updates.notes : existing?.notes || null;

  // Handle JSON arrays
  let favorite_genres = existing?.favorite_genres || "[]";
  if (updates.favorite_genres !== undefined) {
    favorite_genres =
      typeof updates.favorite_genres === "string"
        ? updates.favorite_genres
        : JSON.stringify(updates.favorite_genres || []);
  }

  let favorite_artists = existing?.favorite_artists || "[]";
  if (updates.favorite_artists !== undefined) {
    favorite_artists =
      typeof updates.favorite_artists === "string"
        ? updates.favorite_artists
        : JSON.stringify(updates.favorite_artists || []);
  }

  // Use INSERT OR REPLACE
  const stmt = db.prepare(`
    INSERT OR REPLACE INTO user_profiles (
      user_id, username, tone_preference, favorite_genres, 
      favorite_artists, notes, current_mood, updated_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
  `);

  stmt.run(userId, username, tone_preference, favorite_genres, favorite_artists, notes, current_mood);

  return getUserProfile(userId);
}

/**
 * Update user mood (convenience function)
 * @param {string} userId - The user ID
 * @param {string} mood - Mood: negative | neutral | positive
 */
export function updateUserMood(userId, mood) {
  if (!userId) return;
  const validMoods = ["negative", "neutral", "positive"];
  if (!validMoods.includes(mood)) {
    logger.warn("[USER_PROFILES] Invalid mood provided", { userId, mood });
    mood = "neutral";
  }
  return upsertUserProfile(userId, { current_mood: mood });
}

/**
 * Update user tone preference (convenience function)
 * @param {string} userId - The user ID
 * @param {string} tone - Tone: snarky | neutral | positive
 */
export function updateUserTone(userId, tone) {
  if (!userId) return;
  const validTones = ["snarky", "neutral", "positive"];
  if (!validTones.includes(tone)) {
    logger.warn("[USER_PROFILES] Invalid tone provided", { userId, tone });
    tone = "neutral";
  }
  return upsertUserProfile(userId, { tone_preference: tone });
}

