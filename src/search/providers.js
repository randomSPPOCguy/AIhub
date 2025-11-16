import fetch from "node-fetch";
import { cfg } from "../config.js";
import { RateQueue } from "../utils/rateLimit.js";
import { logger } from "../utils/logger.js";

const WIKI_REST = "https://en.wikipedia.org/api/rest_v1";
const WM_CORE = "https://api.wikimedia.org/core/v1/wikipedia/en";
const DISCOGS = "https://api.discogs.com";
const MB = "https://musicbrainz.org/ws/2";
const CAA = "https://coverartarchive.org";

const wikiHeaders = { "Api-User-Agent": cfg.wikiUA };

export async function wikiSummary(title) {
  const url = `${WIKI_REST}/page/summary/${encodeURIComponent(title)}`;
  const r = await fetch(url, { headers: wikiHeaders });
  if (!r.ok) return null;
  return r.json();
}

export async function wikiTitleSearch(q, limit = 5) {
  const url = `${WM_CORE}/search/title?q=${encodeURIComponent(q)}&limit=${limit}`;
  const r = await fetch(url, { headers: wikiHeaders });
  if (!r.ok) return { pages: [] };
  return r.json();
}

export async function discogsSearch({ artist, track, release_title, style, year, genre }) {
  const params = new URLSearchParams();
  if (artist) params.set("artist", artist);
  if (track) params.set("track", track);
  if (release_title) params.set("release_title", release_title);
  if (style?.length) params.set("style", style.join(","));
  if (year) params.set("year", String(year));
  if (genre?.length) params.set("genre", genre.join(","));
  const url = `${DISCOGS}/database/search?${params.toString()}`;
  const r = await fetch(url, {
    headers: { Authorization: `Discogs token=${cfg.discogsToken}` }
  });
  if (!r.ok) {
    logger.warn("Discogs search failed", r.status);
    return null;
  }
  return r.json();
}

// MusicBrainz rate 1 req/s, enforced via queue
const mbQueue = new RateQueue(1000);

export async function mbReleaseGroupsByArtist(artistName, limit = 100) {
  return mbQueue.enqueue(async () => {
    const q = `artist:${JSON.stringify(artistName)} AND primarytype:album`;
    const url = `${MB}/release-group?query=${encodeURIComponent(q)}&limit=${limit}&fmt=json`;
    const r = await fetch(url, {
      headers: {
        "User-Agent": `${cfg.mbUA.app}/${cfg.mbUA.version} (${cfg.mbUA.contact})`
      }
    });
    if (!r.ok) return { count: 0, "release-groups": [] };
    return r.json();
  });
}

export async function caaFrontForRelease(releaseId) {
  // best-effort; may return 404
  const url = `${CAA}/release/${releaseId}`;
  const r = await fetch(url);
  if (!r.ok) return null;
  const data = await r.json();
  const front = data.images?.find(i => i.front) || data.images?.[0];
  return front?.thumbnails?.large || front?.image || null;
}

export async function caaFrontForReleaseGroup(rgId) {
  const url = `${CAA}/release-group/${rgId}`;
  const r = await fetch(url);
  if (!r.ok) return null;
  const data = await r.json();
  const front = data.images?.find(i => i.front) || data.images?.[0];
  return front?.thumbnails?.large || front?.image || null;
}
