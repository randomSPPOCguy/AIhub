// src/services/classifier.js

const NEGATIVE_WORDS = ["fuck you", "stupid bot", "dumb bot", "hate", "sucks", "annoying", "shut up", "awful", "terrible"];
const POSITIVE_WORDS = ["love", "awesome", "great", "dope", "sick", "fire", "cool", "amazing", "nice", "thanks"];

/**
 * Classify user mood and intent from a message
 * This is a simple heuristic-based classifier that can be upgraded to use a local model later
 *
 * @param {string} message - The user's message text
 * @returns {Object} Classification result with mood and intent
 * @returns {string} mood - "negative" | "neutral" | "positive"
 * @returns {string} intent - "regular_chat" | "ask_how_bot_is_built" | "music_question" | "other"
 */
export function classifyMoodAndIntent(message) {
  const text = (message || "").toLowerCase();

  // Classify mood
  let mood = "neutral";

  if (NEGATIVE_WORDS.some((w) => text.includes(w))) {
    mood = "negative";
  } else if (POSITIVE_WORDS.some((w) => text.includes(w))) {
    mood = "positive";
  }

  // Classify intent
  let intent = "regular_chat";

  if (
    text.includes("how are you built") ||
    text.includes("how do you work") ||
    text.includes("who coded you") ||
    text.includes("how are you made") ||
    text.includes("how is this bot made") ||
    text.includes("show me your code") ||
    text.includes("how does this work")
  ) {
    intent = "ask_how_bot_is_built";
  } else if (
    text.includes("song") ||
    text.includes("track") ||
    text.includes("artist") ||
    text.includes("album") ||
    text.includes("playlist") ||
    text.includes("recommend") ||
    text.includes("music") ||
    text.includes("genre") ||
    text.includes("band")
  ) {
    intent = "music_question";
  } else if (
    !text.match(/[a-z]/) || // No letters (just symbols/emojis)
    text.length < 2
  ) {
    intent = "other";
  }

  return { mood, intent };
}

/**
 * Classify just the mood from a message
 * Convenience function for when you only need mood classification
 *
 * @param {string} message - The user's message text
 * @returns {string} mood - "negative" | "neutral" | "positive"
 */
export function classifyMood(message) {
  return classifyMoodAndIntent(message).mood;
}

/**
 * Classify just the intent from a message
 * Convenience function for when you only need intent classification
 *
 * @param {string} message - The user's message text
 * @returns {string} intent - "regular_chat" | "ask_how_bot_is_built" | "music_question" | "other"
 */
export function classifyIntent(message) {
  return classifyMoodAndIntent(message).intent;
}
