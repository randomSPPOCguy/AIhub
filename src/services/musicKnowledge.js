// src/services/musicKnowledge.js
// Service to classify music-related queries
// NOTE: Actual enrichment now handled by Python enrichment service

import { logger } from "../utils/logger.js";

const musicInfo = (message, meta) => logger.info(`[MUSIC] ${message}`, meta);
const musicWarn = (message, meta) => logger.warn(`[MUSIC] ${message}`, meta);
const musicDebug = (message, meta) => logger.debug(`[MUSIC] ${message}`, meta);
const knowledgeError = (message, meta) => logger.error(`[MUSIC_KNOWLEDGE] ${message}`, meta);

const KEYWORD_STOPWORDS = new Set([
  "the", "and", "for", "with", "that", "this", "what", "who", "how", "why",
  "when", "where", "need", "want", "know", "tell", "anything", "about",
  "your", "you", "does", "is", "are", "i", "im", "imma", "its", "it's", "let",
  "me", "please", "can", "could", "should", "would", "also", "just", "bot"
]);

const COMMON_NON_ARTISTS = new Set([
  "the bot", "bot", "you", "this", "that", "yourself", "myself",
  "their", "them", "himself", "herself", "itself", "themselves", "me", "us",
  "it", "here", "there", "what", "how", "why", "when", "where", "themself"
]);

const PHRASE_NOISE_WORDS = new Set([
  "last", "latest", "newest", "recent", "album", "release",
  "record", "song", "track", "playlist", "made", "they", "them",
  "any", "some", "other", "another", "recommend", "suggest", "from", "by",
  "what", "was", "is", "are", "a", "the", "to", "for", "this", "that"
]);

const userArtistContext = new Map();

function rememberArtistForUser(userId, artist) {
  if (!userId || !artist) return;
  userArtistContext.set(userId, artist.toLowerCase());
}

function recallArtistForUser(userId) {
  if (!userId) return null;
  return userArtistContext.get(userId) || null;
}

function normalizeKeyword(value) {
  if (!value) return null;
  const cleaned = value
    .toLowerCase()
    .replace(/["']/g, "")
    .trim();
  if (!cleaned) return null;
  return cleaned;
}

function addArtistCandidate(entities, name, addKeyword, commonNonArtists = COMMON_NON_ARTISTS) {
  if (!name) return;
  const normalized = name.toLowerCase().trim();
  if (normalized.length <= 2 || commonNonArtists.includes(normalized)) return;
  if (!entities.artists.includes(normalized)) {
    entities.artists.push(normalized);
    addKeyword(normalized);
  }
}

/**
 * Extract potential artist/song names from a user message
 * Returns: { artists: string[], songs: string[], albums: string[] }
 */
function extractMusicEntities(message, metadata = {}) {
  const text = message.toLowerCase();
  const keywordSets = {
    wikipedia: new Set(),
    musicbrainz: new Set()
  };
  const entities = {
    artists: [],
    songs: [],
    albums: [],
    queryType: null
  };

  const recordKeyword = (value, sources = ["wikipedia", "musicbrainz"]) => {
    const normalized = normalizeKeyword(value);
    if (!normalized) return;
    sources.forEach((source) => {
      if (keywordSets[source]) {
        keywordSets[source].add(normalized);
      }
    });
  };

  const addArtistKeyword = (artistName) => {
    recordKeyword(artistName);
    recordKeyword(`${artistName} artist`, ["musicbrainz"]);
    recordKeyword(`${artistName} biography`, ["wikipedia"]);
  };

  const addSongKeyword = (songTitle) => {
    recordKeyword(songTitle);
    recordKeyword(`${songTitle} song`, ["musicbrainz"]);
    recordKeyword(`${songTitle} lyrics`, ["wikipedia"]);
  };

  const addAlbumKeyword = (albumName) => {
    recordKeyword(albumName);
    recordKeyword(`${albumName} album`, ["musicbrainz"]);
  };

  const addMessageKeywords = () => {
    const tokens = extractMessageTokens(text);
    tokens.forEach((token) => recordKeyword(token));
    const phraseCandidates = generatePhraseCandidates(tokens, 2, 3);
    phraseCandidates.forEach((phrase) => recordKeyword(phrase));
  };

  // Check if now_playing is mentioned and available in metadata
  const mentionsCurrentSong =
    text.includes("this song") ||
    text.includes("this track") ||
    text.includes("current song") ||
    text.includes("playing");

  if (mentionsCurrentSong && metadata?.now_playing) {
    const np = metadata.now_playing;
    if (np.artist) {
      addArtistCandidateSafe(np.artist);
    }
    if (np.title) {
      entities.songs.push(np.title);
      addSongKeyword(np.title);
    }
    if (np.album) {
      entities.albums.push(np.album);
      addAlbumKeyword(np.album);
    }
    entities.queryType = "now_playing";
    entities.keywords = {
      wikipedia: [...keywordSets.wikipedia],
      musicbrainz: [...keywordSets.musicbrainz]
    };
    return entities;
  }

  // Artist query patterns
  const artistPatterns = [
    /who (?:is|are) ([a-z0-9 &'-]+?)(?:\?|$)/i,
    /tell me about ([a-z0-9 &'-]+?)(?:\?|$)/i,
    /what (?:do you know|can you tell me) about ([a-z0-9 &'-]+?)(?:\?|$)/i,
    /(?:artist|band|rapper|singer) ([a-z0-9 &'-]+?)(?:\?|$)/i,
  ];

  const artistPhrase = "([a-z0-9]+(?:[ &'-][a-z0-9]+)*)";
  const trailingBoundary = "(?=(?:\\s|$|\\?|bot))";

  const recommendationArtistPatterns = [
    new RegExp(`from\\s+${artistPhrase}${trailingBoundary}`, "i"),
    new RegExp(`recommend(?:\\s+\\w+){0,4}?\\s+(?:song|track|album|playlist|tune)(?:\\s+to listen to)?(?:\\s+by|\\s+from)?\\s+${artistPhrase}${trailingBoundary}`, "i"),
    new RegExp(`suggest(?:\\s+another|\\s+some)?\\s+(?:song|track|album|playlist|tune)(?:\\s+by|\\s+from)?\\s+${artistPhrase}${trailingBoundary}`, "i"),
    new RegExp(`what about\\s+${artistPhrase}${trailingBoundary}`, "i")
  ];

  const albumQueryPatterns = [
    new RegExp(`(?:what|which)\\s+(?:was|is|are)\\s+(?:the\\s+)?${artistPhrase}\\s+(?:last|latest|newest|most recent)\\s+(?:album|release|record)`, "i"),
    new RegExp(`${artistPhrase}\\s+(?:last|latest|newest|most recent)\\s+(?:album|release|record)`, "i")
  ];

  // Common words/phrases that are NOT artist names
  const addArtistCandidateSafe = (value) => addArtistCandidate(entities, value, addArtistKeyword);

  for (const pattern of artistPatterns) {
    const match = text.match(pattern);
    if (match && match[1]) {
      const name = match[1].trim();
      // Filter out common words that aren't artist names
      if (name.length > 2 && !COMMON_NON_ARTISTS.has(name.toLowerCase())) {
        addArtistCandidateSafe(name);
        entities.queryType = "artist";
        break;
      }
    }
  }

  for (const pattern of recommendationArtistPatterns) {
    const match = text.match(pattern);
    if (match && match[1]) {
      addArtistCandidateSafe(match[1].trim());
    }
  }

  for (const pattern of albumQueryPatterns) {
    const match = text.match(pattern);
    if (match && match[1]) {
      addArtistCandidateSafe(match[1].trim());
    }
  }

  // Song query patterns
  const songPatterns = [
    /song (?:called |titled )?["']?([a-z0-9 &'-]+?)["']?(?:\?|$| by)/i,
    /track (?:called |titled )?["']?([a-z0-9 &'-]+?)["']?(?:\?|$| by)/i,
  ];

  for (const pattern of songPatterns) {
    const match = text.match(pattern);
    if (match && match[1]) {
      const songTitle = match[1].trim();
      entities.songs.push(songTitle);
      addSongKeyword(songTitle);
      entities.queryType = "song";
    }
  }

  // Extract "by [artist]" if present
  const byArtistMatch = text.match(/by ([a-z0-9 &'-]+?)(?:\?|$)/i);
  if (byArtistMatch && byArtistMatch[1]) {
    addArtistCandidateSafe(byArtistMatch[1].trim());
  }

  addMessageKeywords();

  if (!entities.artists.length) {
    const remembered = recallArtistForUser(metadata?.user_id);
    if (remembered) {
      addArtistCandidateSafe(remembered);
      entities.queryType = entities.queryType || "context";
    }
  }

  entities.keywords = {
    wikipedia: [...keywordSets.wikipedia],
    musicbrainz: [...keywordSets.musicbrainz]
  };

  return entities;
}

/**
 * DEPRECATED: Now handled by Python enrichment service
 * Kept as stub for backwards compatibility
 */
async function resolveArtistFromKeywords(entities) {
  // No-op: Python enrichment service handles this now
  return null;
}

/**
 * DEPRECATED: Now handled by Python enrichment service
 * Kept as stub for backwards compatibility
 */
async function fetchArtistFacts(artistName) {
  // No-op: Python enrichment service handles this now
  return null;
}

/**
 * DEPRECATED: Now handled by Python enrichment service
 * Kept as stub for backwards compatibility
 */
async function fetchSongFacts(songTitle, artistName = null) {
  // No-op: Python enrichment service handles this now
  return null;
}

/**
 * Main function: enrich music-related queries with facts
 * Returns formatted text to add to system prompt
 */
export async function enrichMusicQuery(message, metadata = {}) {
  const entities = extractMusicEntities(message, metadata);
  await resolveArtistFromKeywords(entities);

  musicInfo("Extracting music entities", { message });
  musicDebug("Entity extraction summary", {
    artists: entities.artists.length,
    songs: entities.songs.length,
    albums: entities.albums.length
  });
  if (entities.artists.length > 0) {
    musicDebug("Artists detected", { artists: entities.artists });
  }
  if (entities.songs.length > 0) {
    musicDebug("Songs detected", { songs: entities.songs });
  }
  if (entities.queryType) {
    musicDebug("Query type detected", { queryType: entities.queryType });
  }

  // No music entities found
  if (entities.artists.length === 0 && entities.songs.length === 0) {
    musicWarn("No music entities found, skipping enrichment");
    return null;
  }

  const promptSegments = [];
  const displaySegments = [];

  // Fetch artist facts
  for (const artistName of entities.artists.slice(0, 2)) { // Limit to 2 artists
    musicInfo("Searching for artist facts", { artist: artistName });
    const artistFacts = await fetchArtistFacts(artistName);
    if (artistFacts) {
      musicInfo("Artist facts found", { artist: artistName, source: artistFacts.source });
      const formatted = formatArtistFacts(artistFacts);
      if (formatted.prompt) {
        promptSegments.push(formatted.prompt);
      }
      if (formatted.display) {
        displaySegments.push(formatted.display);
      }
      if (metadata?.user_id && artistFacts.artist) {
        rememberArtistForUser(metadata.user_id, artistFacts.artist);
      }
    } else {
      musicWarn("No artist facts found", { artist: artistName });
    }
  }

  // Fetch song facts
  if (entities.songs.length > 0) {
    const songTitle = entities.songs[0];
    const artistName = entities.artists[0] || null;
    musicInfo("Searching for song facts", {
      song: songTitle,
      artist: artistName || null
    });
    const songFacts = await fetchSongFacts(songTitle, artistName);
    if (songFacts) {
      musicInfo("Song facts found", {
        song: songTitle,
        artist: artistName,
        source: songFacts.source
      });
      const formatted = formatSongFacts(songFacts);
      if (formatted.prompt) {
        promptSegments.push(formatted.prompt);
      }
      if (formatted.display) {
        displaySegments.push(formatted.display);
      }
    } else {
      musicWarn("No song facts found", { song: songTitle });
    }
  }

  if (promptSegments.length === 0) {
    musicWarn("No facts collected despite finding entities");
    return null;
  }

  musicInfo("Music enrichment complete", { factCount: promptSegments.length });

  return {
    entities,
    factsText: promptSegments.join("\n\n"),
    displayText: displaySegments.length ? displaySegments.join("\n\n") : null,
    factCount: promptSegments.length
  };
}

/**
 * Format artist facts for system prompt
 */
function buildArtistFactsPrompt(facts) {
  const lines = [`📚 ARTIST FACTS: ${facts.artist}`];

  if (facts.source === "wikipedia") {
    if (facts.summary) {
      lines.push(`Summary: ${truncate(facts.summary, 300)}`);
    }
    if (facts.description) {
      lines.push(`Description: ${facts.description}`);
    }
    if (facts.genres) {
      const genresArray = Array.isArray(facts.genres) ? facts.genres : [facts.genres];
      if (genresArray.length > 0) {
        lines.push(`Genres: ${genresArray.slice(0, 5).join(", ")}`);
      }
    }
    if (facts.activeYears) {
      lines.push(`Active: ${facts.activeYears}`);
    }
    if (facts.origin) {
      lines.push(`Origin: ${facts.origin}`);
    }
    if (facts.members) {
      lines.push(`Members: ${facts.members}`);
    }
  } else if (facts.source === "musicbrainz") {
    if (facts.type) {
      lines.push(`Type: ${facts.type}`);
    }
    if (facts.country) {
      lines.push(`Country: ${facts.country}`);
    }
    if (facts.disambiguation) {
      lines.push(`Note: ${facts.disambiguation}`);
    }
  }

  return lines.join("\n");
}

/**
 * Format song facts for system prompt
 */
function buildSongFactsPrompt(facts) {
  const lines = [`📚 SONG FACTS: "${facts.title}"${facts.artist ? ` by ${facts.artist}` : ""}`];

  if (facts.summary) {
    lines.push(`Summary: ${truncate(facts.summary, 300)}`);
  }
  if (facts.album) {
    lines.push(`Album: ${facts.album}`);
  }
  if (facts.releaseDate || facts.released) {
    lines.push(`Released: ${facts.releaseDate || facts.released}`);
  }
  if (facts.duration || facts.length) {
    lines.push(`Duration: ${facts.duration || facts.length}`);
  }
  if (facts.genre) {
    lines.push(`Genre: ${facts.genre}`);
  }
  if (facts.genres && facts.genres.length > 0) {
    lines.push(`Genres: ${facts.genres.join(", ")}`);
  }

  return lines.join("\n");
}

/**
 * Truncate text to max length with ellipsis
 */
function truncate(text, maxLength) {
  if (!text || text.length <= maxLength) return text;
  return text.substring(0, maxLength).trim() + "...";
}

function extractMessageTokens(text) {
  if (!text) return [];
  return text
    .toLowerCase()
    .split(/[^a-z0-9']+/)
    .map((token) => token.trim())
    .filter((token) => token.length >= 2 && !KEYWORD_STOPWORDS.has(token));
}

function generatePhraseCandidates(tokens, minWords = 2, maxWords = 3) {
  const phrases = new Set();
  for (let i = 0; i < tokens.length; i++) {
    for (let len = minWords; len <= maxWords && i + len <= tokens.length; len++) {
      phrases.add(tokens.slice(i, i + len).join(" "));
    }
  }
  return Array.from(phrases);
}

/**
 * Quick check if a message might be music-related (for optimization)
 */
export function isMusicQuery(message) {
  const text = message.toLowerCase();
  const musicKeywords = [
    "who is", "who are", "tell me about",
    "song", "track", "album", "artist", "band", "rapper", "singer",
    "music", "genre", "listen", "play",
    "this song", "current song", "now playing"
  ];

  return musicKeywords.some(keyword => text.includes(keyword));
}
function buildArtistFactsDisplay(facts) {
  const segments = [];

  if (facts.summary) {
    segments.push(`${facts.artist}: ${truncate(facts.summary, 200)}`);
  } else if (facts.description) {
    segments.push(`${facts.artist}: ${truncate(facts.description, 200)}`);
  }

  const genresArray = Array.isArray(facts.genres)
    ? facts.genres
    : Array.isArray(facts.genresArray)
      ? facts.genresArray
      : [facts.genres].filter(Boolean);
  if (genresArray.length > 0) {
    segments.push(`Genres: ${genresArray.slice(0, 5).join(", ")}.`);
  }

  if (facts.activeYears) {
    segments.push(`Active years: ${facts.activeYears}.`);
  }
  if (facts.origin) {
    segments.push(`Origin: ${facts.origin}.`);
  }
  if (facts.members) {
    segments.push(`Members: ${facts.members}.`);
  }
  if (facts.type) {
    segments.push(`${facts.artist} is a ${facts.type}.`);
  }
  if (facts.country) {
    segments.push(`Country of origin: ${facts.country}.`);
  }
  if (facts.disambiguation) {
    segments.push(facts.disambiguation);
  }

  return segments.join(" ").trim();
}

function buildSongFactsDisplay(facts) {
  const segments = [];

  if (facts.summary) {
    const summary = truncate(facts.summary, 200);
    segments.push(summary.endsWith(".") ? summary : `${summary}.`);
  }
  if (facts.album) {
    segments.push(`Album: ${facts.album}.`);
  }
  if (facts.releaseDate || facts.released) {
    segments.push(`Released: ${facts.releaseDate || facts.released}.`);
  }
  if (facts.duration || facts.length) {
    segments.push(`Duration: ${facts.duration || facts.length}.`);
  }
  if (facts.genre) {
    segments.push(`Genre: ${facts.genre}.`);
  }
  if (facts.genres && facts.genres.length > 0) {
    segments.push(`Genres: ${facts.genres.join(", ")}.`);
  }

  return segments.join(" ").trim();
}

function formatArtistFacts(facts) {
  return {
    prompt: buildArtistFactsPrompt(facts),
    display: buildArtistFactsDisplay(facts)
  };
}

function formatSongFacts(facts) {
  return {
    prompt: buildSongFactsPrompt(facts),
    display: buildSongFactsDisplay(facts)
  };
}
