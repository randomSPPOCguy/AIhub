// src/services/musicbrainz.enhanced.js
// Enhanced MusicBrainz data extraction - detailed recording, release, and artist info

import { logger } from "../utils/logger.js";
import {
  mbSearchRecording,
  mbSearchArtistByName
} from "./musicbrainz.js";

// Re-import the functions we need from base musicbrainz.js
const MB_UA =
  process.env.MB_UA ??
  `${process.env.MB_UA_APP || "AIHubBot"}/${process.env.MB_UA_VERSION || "1.1"} (${
    process.env.MB_UA_CONTACT || "you@example.com"
  })`;

const mbInfo = (message, meta) => logger.info(`[MB_ENHANCED] ${message}`, meta);
const mbWarn = (message, meta) => logger.warn(`[MB_ENHANCED] ${message}`, meta);
const mbError = (message, meta) => logger.error(`[MB_ENHANCED] ${message}`, meta);
const mbDebug = (message, meta) => logger.debug(`[MB_ENHANCED] ${message}`, meta);

function mbHeaders() {
  return { "User-Agent": MB_UA, Accept: "application/json" };
}

async function mbGet(url) {
  const r = await fetch(url, { headers: mbHeaders() });
  if (!r.ok) {
    const text = await r.text().catch(() => "");
    throw new Error(`MB ${r.status} for ${url} ${text}`);
  }
  return r.json();
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

/**
 * Get detailed recording (track) information
 * Returns: duration, ISRC, tags, relationships (covers, samples)
 */
export async function getRecordingDetails(recordingMbid) {
  if (!recordingMbid) return null;

  const url = `https://musicbrainz.org/ws/2/recording/${recordingMbid}?inc=artist-credits+isrcs+tags+genres+url-rels+work-rels&fmt=json`;
  
  try {
    const data = await mbGet(url);
    
    return {
      id: data.id,
      title: data.title,
      length: data.length, // milliseconds
      lengthFormatted: formatDuration(data.length),
      
      // ISRC codes (International Standard Recording Code)
      isrcs: data.isrcs || [],
      
      // Artist credits (handles featured artists, etc.) - limit to top 3
      artistCredits: (data['artist-credit'] || [])
        .slice(0, 3)
        .map(ac => ({
          name: ac.name,
          artistId: ac.artist?.id,
          joinphrase: ac.joinphrase || ''
        })),
      
      // Tags and genres - limit to top 5 by count
      tags: (data.tags || [])
        .sort((a, b) => (b.count || 0) - (a.count || 0))
        .slice(0, 5)
        .map(t => ({ name: t.name, count: t.count })),
      genres: (data.genres || [])
        .sort((a, b) => (b.count || 0) - (a.count || 0))
        .slice(0, 5)
        .map(g => ({ name: g.name, count: g.count })),
      
      // Relationships (covers, samples, remixes)
      relationships: parseRecordingRelationships(data.relations || []),
      
      // Wikipedia/Wikidata links
      wikiLinks: extractWikiLinks(data.relations || [])
    };
  } catch (error) {
    mbError("Error fetching recording details", {
      recordingMbid,
      error: error?.message || String(error)
    });
    return null;
  }
}

/**
 * Get detailed release group (album) information
 * Returns: release dates, types, artist credits, label info
 */
export async function getReleaseGroupDetails(releaseGroupMbid) {
  if (!releaseGroupMbid) return null;

  const url = `https://musicbrainz.org/ws/2/release-group/${releaseGroupMbid}?inc=artist-credits+tags+genres+url-rels+releases&fmt=json`;
  
  try {
    const data = await mbGet(url);
    
    // Get first release for additional details (release date, label)
    let firstRelease = null;
    if (data.releases && data.releases.length > 0) {
      const releaseId = data.releases[0].id;
      firstRelease = await getFirstReleaseDetails(releaseId);
      await sleep(200); // Rate limiting
    }
    
    return {
      id: data.id,
      title: data.title,
      primaryType: data['primary-type'],
      secondaryTypes: data['secondary-types'] || [],
      
      // Release date from first release
      firstReleaseDate: data['first-release-date'] || firstRelease?.date,
      releaseYear: (data['first-release-date'] || '').slice(0, 4) || firstRelease?.year,
      
      // Artist credits - limit to top 3
      artistCredits: (data['artist-credit'] || [])
        .slice(0, 3)
        .map(ac => ({
          name: ac.name,
          artistId: ac.artist?.id
        })),
      
      // Tags and genres - limit to top 5 by count
      tags: (data.tags || [])
        .sort((a, b) => (b.count || 0) - (a.count || 0))
        .slice(0, 5)
        .map(t => ({ name: t.name, count: t.count })),
      genres: (data.genres || [])
        .sort((a, b) => (b.count || 0) - (a.count || 0))
        .slice(0, 5)
        .map(g => ({ name: g.name, count: g.count })),
      
      // Label info from first release
      label: firstRelease?.label,
      catalogNumber: firstRelease?.catalogNumber,
      
      // Wikipedia/Wikidata links
      wikiLinks: extractWikiLinks(data.relations || [])
    };
  } catch (error) {
    mbError("Error fetching release group", {
      releaseGroupMbid,
      error: error?.message || String(error)
    });
    return null;
  }
}

/**
 * Get detailed artist information
 * Returns: type, country, active years, aliases, members
 */
export async function getArtistDetails(artistMbid) {
  if (!artistMbid) return null;

  const url = `https://musicbrainz.org/ws/2/artist/${artistMbid}?inc=aliases+tags+genres+url-rels+artist-rels&fmt=json`;
  
  try {
    const data = await mbGet(url);
    
    return {
      id: data.id,
      name: data.name,
      sortName: data['sort-name'],
      type: data.type, // 'Person', 'Group', 'Orchestra', etc.
      
      // Geographic info
      country: data.country,
      area: data.area?.name,
      
      // Active years
      lifeSpan: {
        begin: data['life-span']?.begin,
        end: data['life-span']?.end,
        ended: data['life-span']?.ended || false
      },
      
      // Aliases (other names) - limit to top 5
      aliases: (data.aliases || [])
        .slice(0, 5)
        .map(a => ({
          name: a.name,
          sortName: a['sort-name'],
          type: a.type,
          locale: a.locale
        })),
      
      // Tags and genres - limit to top 5 by count
      tags: (data.tags || [])
        .sort((a, b) => (b.count || 0) - (a.count || 0))
        .slice(0, 5)
        .map(t => ({ name: t.name, count: t.count })),
      genres: (data.genres || [])
        .sort((a, b) => (b.count || 0) - (a.count || 0))
        .slice(0, 5)
        .map(g => ({ name: g.name, count: g.count })),
      
      // Band members (if group) - limit to top 10 current/recent
      members: parseBandMembers(data.relations || []).slice(0, 10),
      
      // Wikipedia/Wikidata links
      wikiLinks: extractWikiLinks(data.relations || [])
    };
  } catch (error) {
    mbError("Error fetching artist", {
      artistMbid,
      error: error?.message || String(error)
    });
    return null;
  }
}

/**
 * Get first release details (for release date and label info)
 */
async function getFirstReleaseDetails(releaseId) {
  try {
    const url = `https://musicbrainz.org/ws/2/release/${releaseId}?inc=labels&fmt=json`;
    const data = await mbGet(url);
    
    const label = data['label-info']?.[0];
    
    return {
      date: data.date,
      year: (data.date || '').slice(0, 4),
      label: label?.label?.name,
      catalogNumber: label?.['catalog-number']
    };
  } catch {
    return null;
  }
}

/**
 * Parse recording relationships (covers, samples, remixes)
 */
function parseRecordingRelationships(relations) {
  const relationships = {
    covers: [],
    sampledBy: [],
    samples: [],
    remixOf: [],
    remixedBy: [],
    other: []
  };

  for (const rel of relations) {
    const type = rel.type;
    const direction = rel.direction || 'forward';
    
    if (type === 'cover') {
      if (direction === 'backward') {
        // This recording is a cover of another
        relationships.covers.push({
          originalTitle: rel.recording?.title,
          originalArtist: rel.recording?.['artist-credit']?.[0]?.name,
          originalId: rel.recording?.id
        });
      }
    } else if (type === 'samples material') {
      if (direction === 'forward') {
        relationships.samples.push({
          sampledTitle: rel.recording?.title,
          sampledArtist: rel.recording?.['artist-credit']?.[0]?.name
        });
      } else {
        relationships.sampledBy.push({
          samplingTitle: rel.recording?.title,
          samplingArtist: rel.recording?.['artist-credit']?.[0]?.name
        });
      }
    } else if (type === 'remix') {
      if (direction === 'backward') {
        relationships.remixOf.push({
          originalTitle: rel.recording?.title,
          originalArtist: rel.recording?.['artist-credit']?.[0]?.name
        });
      } else {
        relationships.remixedBy.push({
          remixTitle: rel.recording?.title,
          remixArtist: rel.recording?.['artist-credit']?.[0]?.name
        });
      }
    }
  }

  return relationships;
}

/**
 * Parse band member relationships - deduplicate by member name
 */
function parseBandMembers(relations) {
  const memberMap = new Map();
  
  for (const rel of relations) {
    if (rel.type === 'member of band') {
      const memberName = rel.artist?.name;
      if (!memberName) continue;
      
      // If we've seen this member before, merge their attributes
      if (memberMap.has(memberName)) {
        const existing = memberMap.get(memberName);
        // Merge attributes (instruments/roles)
        const newAttrs = rel.attributes || [];
        existing.attributes = [...new Set([...existing.attributes, ...newAttrs])];
        // Keep the earliest begin date
        if (rel.begin && (!existing.begin || rel.begin < existing.begin)) {
          existing.begin = rel.begin;
        }
        // Keep the latest end date
        if (rel.end && (!existing.end || rel.end > existing.end)) {
          existing.end = rel.end;
        }
      } else {
        // First time seeing this member
        memberMap.set(memberName, {
          name: memberName,
          id: rel.artist?.id,
          begin: rel.begin,
          end: rel.end,
          ended: rel.ended || false,
          attributes: rel.attributes || []
        });
      }
    }
  }
  
  return Array.from(memberMap.values());
}

/**
 * Extract Wikipedia/Wikidata links from relations
 */
function extractWikiLinks(relations) {
  const links = {
    wikipedia: null,
    wikidata: null,
    allmusic: null,
    discogs: null
  };

  for (const rel of relations) {
    if (rel.type === 'wikipedia' && rel.url?.resource) {
      links.wikipedia = rel.url.resource;
    } else if (rel.type === 'wikidata' && rel.url?.resource) {
      links.wikidata = rel.url.resource;
    } else if (rel.type === 'allmusic' && rel.url?.resource) {
      links.allmusic = rel.url.resource;
    } else if (rel.type === 'discogs' && rel.url?.resource) {
      links.discogs = rel.url.resource;
    }
  }

  return links;
}

/**
 * Format duration from milliseconds to MM:SS
 */
function formatDuration(ms) {
  if (!ms) return null;
  const totalSeconds = Math.floor(ms / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${seconds.toString().padStart(2, '0')}`;
}

/**
 * Filter releases to find the best "original" release
 * Excludes: Compilations, Soundtracks
 * Conditionally excludes Live albums (unless track title suggests it's a live recording)
 * Prioritizes: Studio albums, Singles, EPs
 */
function findBestRelease(releases, trackTitle) {
  if (!releases || releases.length === 0) return null;
  
  // Check if track title suggests it's a live recording
  const isLiveTrack = /\b(live|concert|unplugged|acoustic|sessions?|recorded live)\b/i.test(trackTitle);
  
  // Filter out unwanted types
  const filtered = releases.filter(release => {
    const rg = release['release-group'];
    if (!rg) return true; // Keep if no release group info
    
    const primaryType = rg['primary-type'];
    const secondaryTypes = rg['secondary-types'] || [];
    
    // Always exclude compilations and soundtracks
    if (secondaryTypes.includes('Compilation')) return false;
    if (secondaryTypes.includes('Soundtrack')) return false;
    
    // Only exclude live albums if track title doesn't suggest it's a live recording
    if (!isLiveTrack && secondaryTypes.includes('Live')) return false;
    
    return true;
  });
  
  // If we filtered everything out, return first release anyway
  const candidates = filtered.length > 0 ? filtered : releases;
  
  // Prioritize: Album > Single > EP > Other
  const priorityMap = { 'Album': 0, 'Single': 1, 'EP': 2, 'Broadcast': 3, 'Other': 4 };
  
  const sorted = candidates.sort((a, b) => {
    const aType = a['release-group']?.['primary-type'] || 'Other';
    const bType = b['release-group']?.['primary-type'] || 'Other';
    const aPriority = priorityMap[aType] ?? 999;
    const bPriority = priorityMap[bType] ?? 999;
    
    if (aPriority !== bPriority) return aPriority - bPriority;
    
    // If same priority, prefer earlier date
    const aDate = a.date || '9999';
    const bDate = b.date || '9999';
    return aDate.localeCompare(bDate);
  });
  
  return sorted[0];
}

/**
 * Main entry point - get comprehensive MusicBrainz data for a track
 */
export async function getMusicBrainzDataEnhanced(title, artist) {
  try {
    mbInfo("Fetching enhanced MusicBrainz data", { title, artist });

    // 1. Search for recording - limit to top 5 results for faster processing
    const q = encodeURIComponent(`recording:"${title}" AND artist:"${artist}"`);
    const url = `https://musicbrainz.org/ws/2/recording?query=${q}&limit=5&fmt=json`;
    const searchData = await mbGet(url);
    const recordings = (searchData.recordings || []).sort((a, b) => (b.score ?? 0) - (a.score ?? 0));
    
    if (recordings.length === 0) {
      mbWarn("No recording found during enhancement", { title, artist });
      return null;
    }

    // Check if track title suggests it's a live recording
    const isLiveTrack = /\b(live|concert|unplugged|acoustic|sessions?|recorded live)\b/i.test(title);
    
    // Filter recordings to find studio version (unless explicitly live track)
    let recording = null;
    if (!isLiveTrack) {
      // Try to find a studio recording (exclude live titles)
      recording = recordings.find(r => {
        const recTitle = (r.title || '').toLowerCase();
        return !/\b(live|concert|unplugged|acoustic|session)\b/i.test(recTitle);
      });
    }
    
    // Fall back to best match if no studio version found
    if (!recording) {
      recording = recordings[0];
    }

    await sleep(1100); // MusicBrainz requires 1 second between requests

    // 2-3. Parallelize recording details + artist search (independent operations)
    const [recordingDetails, artistSearchResult] = await Promise.all([
      getRecordingDetails(recording.id),
      (async () => {
        await sleep(1100); // Stagger by 1.1s to respect rate limit
        const artistSearch = await mbSearchArtistByName(artist, 1);
        if (!artistSearch) return null;
        await sleep(1100);
        return getArtistDetails(artistSearch.id);
      })()
    ]);

    await sleep(1100); // One more delay before release group

    // 4. Get release group (album) - filter out compilations/soundtracks/live (unless track is live)
    let releaseGroupDetails = null;
    if (recording.releases && recording.releases.length > 0) {
      const bestRelease = findBestRelease(recording.releases, title);
      if (bestRelease && bestRelease['release-group']) {
        releaseGroupDetails = await getReleaseGroupDetails(bestRelease['release-group'].id);
      }
    }

    mbInfo("Enhanced MusicBrainz data fetched", { title, artist });

    return {
      recording: recordingDetails,
      artist: artistSearchResult,
      releaseGroup: releaseGroupDetails,
      
      // Basic IDs for reference
      metadata: {
        recordingMbid: recording.id,
        artistMbid: artistSearchResult?.id,
        releaseGroupMbid: recording.releases?.[0]?.['release-group']?.id
      }
    };

  } catch (error) {
    mbError("Enhanced MusicBrainz data fetch failed", {
      error: error?.message || String(error),
      title,
      artist
    });
    return null;
  }
}
