// src/services/mb-extra.js (ESM)
// Additive helper to pull "as much as possible" from MusicBrainz while respecting rate limits
// Does not modify your existing services/musicbrainz.js; you can import these alongside it.

const MB_UA = `${process.env.MB_UA_APP || "AIHubBot"}/${process.env.MB_UA_VERSION || "1.1"} (${process.env.MB_UA_CONTACT || "you@example.com"})`;
const MB_BASE = "https://musicbrainz.org/ws/2";
const CAA_BASE = "https://coverartarchive.org";

const SLEEP_MS = Number(process.env.MB_SLEEP_MS || 1000); // ~1 req/sec
const MB_ALBUM_FILTER = process.env.MB_ALBUM_FILTER ||
  'primarytype:album AND NOT secondarytype:(live OR compilation OR soundtrack OR remix)';

export async function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

async function mbGet(url) {
  const r = await fetch(url, { headers: { 'User-Agent': MB_UA, 'Accept': 'application/json' }});
  if (!r.ok) throw new Error(`MB ${r.status} ${r.statusText}`);
  return r.json();
}

// ————————————————————————————————————————————————————————————————————————————
// ARTIST FULL (aliases, tags/genres, ratings, rels including url-rels)
export async function mbArtistFullByName(name) {
  // Search hit (fielded, safer for names with punctuation)
  const q = encodeURIComponent(`artist:${name}`);
  const hit = await mbGet(`${MB_BASE}/artist?query=${q}&limit=5&fmt=json`).then(x =>
    (x.artists || []).sort((a,b) => (b.score||0)-(a.score||0))[0]
  );
  if (!hit?.id) return null;
  await sleep(SLEEP_MS);
  const inc = [
    'aliases','genres','tags','ratings',
    'artist-rels','url-rels'
  ].join('+');
  const full = await mbGet(`${MB_BASE}/artist/${hit.id}?inc=${inc}&fmt=json`);
  return { hit, full };
}

// ————————————————————————————————————————————————————————————————————————————
// RELEASE-GROUPS (Album-only) with optional recency window by firstreleasedate
export async function mbAlbumRGsByArtist(artistId, { since } = {}) {
  const parts = [ `arid:${artistId}`, MB_ALBUM_FILTER ];
  if (since) {
    const iso = since.toISOString().slice(0,10);
    parts.push(`firstreleasedate:[${iso} TO *]`);
  }
  const q = encodeURIComponent(parts.join(' AND '));
  const url = `${MB_BASE}/release-group?query=${q}&limit=100&fmt=json`;
  const json = await mbGet(url);
  return json['release-groups'] || [];
}

// ————————————————————————————————————————————————————————————————————————————
// Pick a canonical Release for an RG (prefer Official, earliest date), with tracklist + label info
export async function mbCanonicalReleaseForRG(rgid) {
  const url = `${MB_BASE}/release?release-group=${rgid}&inc=labels+recordings+artist-credits&limit=100&fmt=json`;
  const j = await mbGet(url);
  const rels = j.releases || [];
  if (!rels.length) return null;
  // prefer Official, then earliest release-event date
  const parseDate = d => (d||'').slice(0,10);
  const byPref = rels.map(r => ({
    r,
    statusScore: (r.status||'').toLowerCase()==='official' ? 1 : 0,
    firstDate: parseDate((r['release-events']?.[0]?.date) || r.date || '')
  }))
  .sort((a,b) => (b.statusScore - a.statusScore) || (a.firstDate.localeCompare(b.firstDate)));
  const chosen = byPref[0].r;
  // flatten label + catno
  const labels = (chosen['label-info']||[]).map(li => ({
    label: li.label?.name, catalog: li.catalog_number || null
  })).filter(x => x.label || x.catalog);
  // tracklist
  const media = chosen.media || [];
  const tracks = [];
  for (const m of media) {
    for (const t of (m.tracks||[])) {
      tracks.push({
        position: t.position,
        title: t.title,
        length_ms: t.length || null,
        recordingId: t.recording?.id || null,
        isrcs: t.recording?.isrcs || []
      });
    }
  }
  // cover art (Front, prefer approved)
  await sleep(SLEEP_MS);
  const art = await caaFrontForRelease(chosen.id).catch(() => null);
  return {
    id: chosen.id,
    title: chosen.title,
    status: chosen.status || null,
    country: chosen.country || null,
    date: (chosen['release-events']?.[0]?.date) || chosen.date || null,
    packaging: chosen.packaging || null,
    format: (chosen.media?.[0]?.format) || null,
    label_info: labels,
    tracks,
    cover_art: art
  };
}

async function caaFrontForRelease(releaseId){
  const j = await fetch(`${CAA_BASE}/release/${releaseId}`, { headers: { 'User-Agent': MB_UA, 'Accept': 'application/json' }})
    .then(r => r.ok ? r.json() : Promise.reject(new Error(`CAA ${r.status}`)));
  const images = j.images || [];
  const fronts = images.filter(i => i.front);
  const approved = fronts.find(i => i.approved) || fronts[0];
  if (!approved) return null;
  return { image: approved.image, thumbnails: approved.thumbnails || {} };
}

// ————————————————————————————————————————————————————————————————————————————
// Track → Album mapper: find a recording under artist + title, resolve to album RG that passes your filter
export async function mbFindAlbumForTrack(artistName, trackTitle) {
  const q = encodeURIComponent(`recording:${trackTitle} AND artist:${artistName}`);
  const recs = await mbGet(`${MB_BASE}/recording?query=${q}&limit=10&fmt=json`).then(x => x.recordings || []);
  if (!recs.length) return null;
  // take first with an attached release & release-group
  const pick = recs.find(r => (r.releases?.[0]?.['release-group']?.id)) || recs[0];
  const rgid = pick.releases?.[0]?.['release-group']?.id;
  if (!rgid) return null;
  // verify the RG matches album-only filter (by querying the RG against filter)
  const rg = await mbGet(`${MB_BASE}/release-group/${rgid}?fmt=json`);
  const isAlbum = (rg["primary-type"]||'').toLowerCase()==='album';
  const secs = (rg["secondary-types"]||[]).map(s => (s||'').toLowerCase());
  const blocked = ['live','compilation','soundtrack','remix'];
  if (!isAlbum || secs.some(s => blocked.includes(s))) return null; // track belongs to non-studio RG
  await sleep(SLEEP_MS);
  const release = await mbCanonicalReleaseForRG(rgid);
  return { rgid, rg_title: rg.title, release };
}

// ————————————————————————————————————————————————————————————————————————————
// Upcoming / recent Events for artist (last N days to future)
export async function mbRecentEventsForArtist(artistId, { daysBack = 365, daysForward = 90 } = {}) {
  const from = new Date(Date.now() - daysBack*86400e3).toISOString().slice(0,10);
  const to   = new Date(Date.now() + daysForward*86400e3).toISOString().slice(0,10);
  const q = encodeURIComponent(`arid:${artistId} AND (begin:[${from} TO *] OR end:[${from} TO *])`);
  const url = `${MB_BASE}/event?query=${q}&limit=100&fmt=json`;
  const j = await mbGet(url);
  const list = j.events || [];
  // normalize a few fields
  return list.map(e => ({ id: e.id, name: e.name, begin: e.begin || null, end: e.end || null, cancelled: !!e.cancelled, type: e.type || null }));
}
