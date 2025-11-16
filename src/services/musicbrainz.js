// src/services/musicbrainz.js (fixed)
// ESM module – MusicBrainz helpers + album-only discography filters

// Build a single UA string (don’t redeclare elsewhere)
const MB_UA = process.env.MB_UA ?? `${process.env.MB_UA_APP || "AIHubBot"}/${process.env.MB_UA_VERSION || "1.1"} (${process.env.MB_UA_CONTACT || "you@example.com"})`;

// Config-driven filters (no hardcoding)
const MB_PRIMARY_INCLUDE = (process.env.MB_RG_PRIMARY_INCLUDE || "album")
  .split(",").map(s => s.trim().toLowerCase()).filter(Boolean);
const MB_PRIMARY_EXCLUDE = (process.env.MB_RG_EXCLUDE_PRIMARY || "single,ep")
  .split(",").map(s => s.trim().toLowerCase()).filter(Boolean);
const MB_SECONDARY_EXCLUDE = (process.env.MB_RG_SECONDARY_EXCLUDE || "live,compilation")
  .split(",").map(s => s.trim().toLowerCase()).filter(Boolean);
const MB_STATUS_INCLUDE = (process.env.MB_RG_STATUS_INCLUDE || "").trim().toLowerCase();

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


export function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}


export async function mbSearchArtistByName(name, limit = 5) {
  const q = encodeURIComponent(`artist:"${name}"`);
  const url = `https://musicbrainz.org/ws/2/artist?query=${q}&limit=${limit}&fmt=json`;
  const j = await mbGet(url);
  const list = Array.isArray(j.artists) ? j.artists : [];
  list.sort((a, b) => (b.score ?? 0) - (a.score ?? 0));
  return list[0] || null;
}

export function summarizeDiscography(rgs) {
  const keep = rgs.filter(g => {
    const prim = (g["primary-type"] || "").toLowerCase();
    const secs = (g["secondary-types"] || []).map(x => (x || "").toLowerCase());
    if (MB_PRIMARY_INCLUDE.length && !MB_PRIMARY_INCLUDE.includes(prim)) return false;
    if (MB_PRIMARY_EXCLUDE.includes(prim)) return false;
    if (secs.some(s => MB_SECONDARY_EXCLUDE.includes(s))) return false;
    return true; // status lives on release, not RG; we used it in the Lucene query
  });
  const years = keep
    .map(g => (g["first-release-date"] || "").slice(0, 4))
    .filter(Boolean)
    .map(Number);
  const firstYear = years.length ? Math.min(...years) : null;
  const latestYear = years.length ? Math.max(...years) : null;
  const sampleAlbums = keep.slice(0, 5).map(g => g.title);
  return { count: keep.length, firstYear, latestYear, sampleAlbums };
}

// —— Release groups filtered by artist
export async function mbReleaseGroupsFilteredByArtist(artistMBID, limit = 100, offset = 0) {
  const includePrim = MB_PRIMARY_INCLUDE.length
    ? MB_PRIMARY_INCLUDE.join(" OR ")
    : "primarytype:album";
  const notSecondary = MB_SECONDARY_EXCLUDE.length
    ? ` AND NOT secondarytype:(${MB_SECONDARY_EXCLUDE.join(" OR ")})` : "";
  const notPrimary = MB_PRIMARY_EXCLUDE.length
    ? ` AND NOT primarytype:(${MB_PRIMARY_EXCLUDE.join(" OR ")})` : "";

  const baseQuery = `arid:${artistMBID} AND (${includePrim})${notSecondary}${notPrimary}`;
  const queryWithStatus = MB_STATUS_INCLUDE ? `${baseQuery} AND status:${MB_STATUS_INCLUDE}` : baseQuery;

  async function run(q) {
    const url = `https://musicbrainz.org/ws/2/release-group?query=${encodeURIComponent(q)}&limit=${limit}&offset=${offset}&fmt=json`;
    const j = await mbGet(url);
    return Array.isArray(j["release-groups"]) ? j["release-groups"] : [];
  }

  // Try with status first (if configured), then fall back without it if nothing returns.
  let rgs = await run(queryWithStatus);
  if ((!rgs || rgs.length === 0) && MB_STATUS_INCLUDE) {
    rgs = await run(baseQuery);
  }
  return rgs;
}

// —— Recording/track search (title + artist -> best match)
export async function mbSearchRecording(title, artistName, limit = 5) {
  const q = encodeURIComponent(`recording:"${title}" AND artist:"${artistName}"`);
  const url = `https://musicbrainz.org/ws/2/recording?query=${q}&limit=${limit}&fmt=json`;
  const j = await mbGet(url);
  const list = Array.isArray(j.recordings) ? j.recordings : [];
  list.sort((a, b) => (b.score ?? 0) - (a.score ?? 0));
  return list[0] || null;
}

// —— Wikipedia / Wikidata relation extraction helpers
// Returns { wikiId, source: 'wikipedia' | 'wikidata', wikidataId } or null
function extractWikiIdFromRelations(relations = []) {
  if (!Array.isArray(relations)) return null;
  // Prefer direct wikipedia link
  const wikiRel = relations.find(r => r.type === 'wikipedia' && r.url?.resource?.includes('wikipedia.org/wiki/'));
  if (wikiRel) {
    return {
      wikiId: wikiRel.url.resource.split('/wiki/')[1],
      source: 'wikipedia',
      wikidataId: null
    };
  }
  // Fallback to wikidata then convert later (caller can resolve page title via Wikidata API)
  const wdRel = relations.find(r => r.type === 'wikidata' && r.url?.resource?.includes('wikidata.org/wiki/'));
  if (wdRel) {
    return {
      wikiId: null,
      source: 'wikidata',
      wikidataId: wdRel.url.resource.split('/wiki/')[1]
    };
  }
  return null;
}

export async function mbGetWikipediaIdForArtist(artistId) {
  const id = String(artistId).trim();
  const url = `https://musicbrainz.org/ws/2/artist/${id}?inc=url-rels&fmt=json`;
  const j = await mbGet(url);
  return extractWikiIdFromRelations(j.relations || []);
}

export async function mbGetWikipediaIdForRecording(recordingId) {
  const id = String(recordingId).trim();
  const url = `https://musicbrainz.org/ws/2/recording/${id}?inc=url-rels&fmt=json`;
  const j = await mbGet(url);
  return extractWikiIdFromRelations(j.relations || []);
}

export async function mbGetWikipediaIdForReleaseGroup(rgId) {
  const id = String(rgId).trim();
  const url = `https://musicbrainz.org/ws/2/release-group/${id}?inc=url-rels&fmt=json`;
  const j = await mbGet(url);
  return extractWikiIdFromRelations(j.relations || []);
}

// High level resolver: passes available MBIDs and returns earliest direct wikiId found
// opts: { artistId?, recordingId?, releaseGroupId?, prefer?: ['recording','artist','release-group'] }
export async function mbResolveWikipediaId(opts = {}) {
  const order = Array.isArray(opts.prefer) && opts.prefer.length
    ? opts.prefer
    : ['recording','release-group','artist'];
  const tasks = [];
  for (const layer of order) {
 
    if (layer === 'recording' && opts.recordingId) {
      tasks.push(['recording', () => mbGetWikipediaIdForRecording(opts.recordingId)]);
    } else if (layer === 'release-group' && opts.releaseGroupId) {
      tasks.push(['release-group', () => mbGetWikipediaIdForReleaseGroup(opts.releaseGroupId)]);
    } else if (layer === 'artist' && opts.artistId) {
      tasks.push(['artist', () => mbGetWikipediaIdForArtist(opts.artistId)]);
    }
  }
  for (const [scope, fn] of tasks) {
    try {
      const res = await fn();
      if (res) return { scope, ...res };
      // Respect polite pacing
      await sleep(200);
    } catch { /* ignore */ }
  }
  return null;
}


export async function mbGetReleaseTracks(releaseId) {
  const clean = String(releaseId).trim().toLowerCase();
  const url = `https://musicbrainz.org/ws/2/release/${clean}?inc=recordings&fmt=json`;
  const j = await mbGet(url);
  
  const tracks = [];
  const media = j.media || [];
  
  for (const medium of media) {
    for (const track of (medium.tracks || [])) {
      tracks.push({
        position: track.position,
        title: track.title,
        length: track.length ? Math.round(track.length / 1000) : null, // convert ms to seconds
        recordingId: track.recording?.id
      });
    }
  }
  
  return tracks;
}


// —— Track -> album mapping (avoid singles)
export async function mbFindAlbumForRecording(artistMBID, title, limit = 25) {
  const q = encodeURIComponent(`recording:"${title}" AND arid:${artistMBID}`);
  const url = `https://musicbrainz.org/ws/2/recording?query=${q}&inc=releases&limit=${limit}&fmt=json`;
  const j = await mbGet(url);
  const recs = Array.isArray(j.recordings) ? j.recordings : [];
  
  for (const rec of recs) {
    const releases = rec.releases || [];
    for (const rel of releases) {
      const prim = (rel["primary-type"] || "").toLowerCase();
      if (MB_PRIMARY_INCLUDE.length && !MB_PRIMARY_INCLUDE.includes(prim)) continue;
      if (MB_PRIMARY_EXCLUDE.includes(prim)) continue;
      return { releaseId: rel.id, title: rel.title };
    }
  }
  return null;
}

// —— Artist genres and tags        

export async function mbArtistGenresTags(artistMBID) {
  const clean = String(artistMBID).trim().toLowerCase();
  const url = `https://musicbrainz.org/ws/2/artist/${clean}?inc=tags+genres&fmt=json`;
  const j = await mbGet(url);
  return {
    genres: (j.genres || []).map(g => g.name),
    tags: (j.tags || []).map(t => t.name),
    merged: [...(j.genres || []).map(g => g.name), ...(j.tags || []).map(t => t.name)]
  };
}
