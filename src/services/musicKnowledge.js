// src/services/musicKnowledge.js
// Service to enrich music-related queries with MusicBrainz and Wikipedia data

import { getArtistInfo, getSongInfo, getAlbumInfo } from "./wikipedia.enhanced.js";
import { getMusicBrainzDataEnhanced } from "./musicbrainz.enhanced.js";
import { mbSearchArtistByName } from "./musicbrainz.js";

/**
 * Extract potential artist/song names from a user message
 * Returns: { artists: string[], songs: string[], albums: string[] }
 */
function extractMusicEntities(message, metadata = {}) {
  const text = message.toLowerCase();
  const entities = {
    artists: [],
    songs: [],
    albums: [],
    queryType: null
  };

  // Check if now_playing is mentioned and available in metadata
  const mentionsCurrentSong =
    text.includes("this song") ||
    text.includes("this track") ||
    text.includes("current song") ||
    text.includes("playing");

  if (mentionsCurrentSong && metadata?.now_playing) {
    const np = metadata.now_playing;
    if (np.artist) entities.artists.push(np.artist);
    if (np.title) entities.songs.push(np.title);
    if (np.album) entities.albums.push(np.album);
    entities.queryType = "now_playing";
    return entities;
  }

  // Artist query patterns
  const artistPatterns = [
    /who (?:is|are) ([a-z0-9 &'-]+?)(?:\?|$)/i,
    /tell me about ([a-z0-9 &'-]+?)(?:\?|$)/i,
    /what (?:do you know|can you tell me) about ([a-z0-9 &'-]+?)(?:\?|$)/i,
    /(?:artist|band|rapper|singer) ([a-z0-9 &'-]+?)(?:\?|$)/i,
  ];

  for (const pattern of artistPatterns) {
    const match = text.match(pattern);
    if (match && match[1]) {
      const name = match[1].trim();
      // Filter out common words that aren't artist names
      if (name.length > 2 && !["the bot", "bot", "you", "this", "that"].includes(name)) {
        entities.artists.push(name);
        entities.queryType = "artist";
        break;
      }
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
      entities.songs.push(match[1].trim());
      entities.queryType = "song";
    }
  }

  // Extract "by [artist]" if present
  const byArtistMatch = text.match(/by ([a-z0-9 &'-]+?)(?:\?|$)/i);
  if (byArtistMatch && byArtistMatch[1]) {
    entities.artists.push(byArtistMatch[1].trim());
  }

  return entities;
}

/**
 * Fetch artist information from Wikipedia and MusicBrainz
 */
async function fetchArtistFacts(artistName) {
  if (!artistName) return null;

  try {
    // Try Wikipedia first (faster, more comprehensive)
    const wikiInfo = await getArtistInfo(artistName);

    if (wikiInfo && wikiInfo.summary) {
      return {
        source: "wikipedia",
        artist: artistName,
        summary: wikiInfo.summary,
        genres: wikiInfo.genresArray || [], // Use genresArray instead of genres (which is a string)
        activeYears: wikiInfo.activeYears || null,
        members: wikiInfo.members || null,
        origin: wikiInfo.origin || null,
        labels: wikiInfo.labels || null,
        description: wikiInfo.description || null
      };
    }

    // Fallback to MusicBrainz artist search
    const mbArtist = await mbSearchArtistByName(artistName);
    if (mbArtist) {
      return {
        source: "musicbrainz",
        artist: artistName,
        mbid: mbArtist.id,
        type: mbArtist.type,
        country: mbArtist.country,
        lifeSpan: mbArtist["life-span"],
        disambiguation: mbArtist.disambiguation
      };
    }

    return null;
  } catch (error) {
    console.error(`[MUSIC_KNOWLEDGE] Error fetching artist facts for "${artistName}":`, error.message);
    return null;
  }
}

/**
 * Fetch song information
 */
async function fetchSongFacts(songTitle, artistName = null) {
  if (!songTitle) return null;

  try {
    // If we have both title and artist, try MusicBrainz enhanced search
    if (artistName) {
      const mbData = await getMusicBrainzDataEnhanced(songTitle, artistName);
      if (mbData && mbData.recording) {
        return {
          source: "musicbrainz",
          title: songTitle,
          artist: artistName,
          duration: mbData.recording.lengthFormatted || null,
          releaseDate: mbData.releaseGroup?.firstReleaseDate || null,
          album: mbData.releaseGroup?.title || null,
          genres: mbData.recording.genres?.map(g => g.name) || []
        };
      }
    }

    // Try Wikipedia (works well for popular songs)
    const wikiInfo = await getSongInfo(songTitle, artistName);
    if (wikiInfo && wikiInfo.summary) {
      return {
        source: "wikipedia",
        title: songTitle,
        artist: artistName,
        summary: wikiInfo.summary,
        releaseDate: wikiInfo.released || null,
        album: wikiInfo.album || null,
        genre: wikiInfo.genre || null,
        length: wikiInfo.length || null
      };
    }

    return null;
  } catch (error) {
    console.error(`[MUSIC_KNOWLEDGE] Error fetching song facts:`, error.message);
    return null;
  }
}

/**
 * Main function: enrich music-related queries with facts
 * Returns formatted text to add to system prompt
 */
export async function enrichMusicQuery(message, metadata = {}) {
  const entities = extractMusicEntities(message, metadata);

  // No music entities found
  if (entities.artists.length === 0 && entities.songs.length === 0) {
    return null;
  }

  const facts = [];

  // Fetch artist facts
  for (const artistName of entities.artists.slice(0, 2)) { // Limit to 2 artists
    const artistFacts = await fetchArtistFacts(artistName);
    if (artistFacts) {
      facts.push(formatArtistFacts(artistFacts));
    }
  }

  // Fetch song facts
  if (entities.songs.length > 0) {
    const songTitle = entities.songs[0];
    const artistName = entities.artists[0] || null;
    const songFacts = await fetchSongFacts(songTitle, artistName);
    if (songFacts) {
      facts.push(formatSongFacts(songFacts));
    }
  }

  if (facts.length === 0) {
    return null;
  }

  return {
    entities,
    factsText: facts.join("\n\n"),
    factCount: facts.length
  };
}

/**
 * Format artist facts for system prompt
 */
function formatArtistFacts(facts) {
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
function formatSongFacts(facts) {
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
