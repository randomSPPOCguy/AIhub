// src/services/wikidata.js
// Wikidata/Wikipedia aggregation via SPARQL + REST summaries
import { normalizeInfoboxGenres, getWikiInfobox } from "./wikipedia.js";

const UA = process.env.WIKIMEDIA_USER_AGENT || "AIHubBot/1.0 (contact: you@example.com)";
const MAX_SONGS = Number(process.env.MAX_SONGS || 20);
const MAX_ALBUMS = Number(process.env.MAX_ALBUMS || 20);
const SUMMARY_CONCURRENCY = Number(process.env.SUMMARY_CONCURRENCY || 4);

const sleep = (ms) => new Promise(r => setTimeout(r, ms));

async function fetchJSON(url, init = {}) {
  const headers = { "User-Agent": UA, "Api-User-Agent": UA, "Accept": "application/json", ...(init.headers || {}) };
  for (let attempt = 0; attempt < 3; attempt++) {
    const res = await fetch(url, { ...init, headers });
    if (res.status === 429 || res.status === 503) { await sleep(500 * (attempt + 1)); continue; }
    if (!res.ok) { const t = await res.text().catch(() => ""); throw new Error(`HTTP ${res.status} ${url} ${t.slice(0,200)}`); }
    return res.json();
  }
  throw new Error(`Failed after retries: ${url}`);
}

function toYear(x) {
  try { if (!x) return null; const y = new Date(x).getUTCFullYear(); return Number.isFinite(y) ? y : null; } catch { return null; }
}

function titleFromWikipediaUrl(url) {
  if (!url) return null;
  const i = url.indexOf("/wiki/");
  return i >= 0 ? decodeURIComponent(url.slice(i + 6)) : null;
}

async function sparql(query) {
  const endpoint = "https://query.wikidata.org/sparql";
  const url = new URL(endpoint);
  url.searchParams.set("format", "json");
  url.searchParams.set("query", query);
  return (await fetchJSON(url.toString(), { headers: {
    "User-Agent": UA, "Api-User-Agent": UA, "Accept": "application/sparql-results+json"
  }})).results.bindings;
}

function literal(v) { return v?.value ?? null; }
function collectGenres(row) {
  const g = literal(row.genres);
  return g ? g.split(", ").map(s => s.trim()).filter(Boolean) : [];
}

// --- Disambiguation helpers ---
async function wdGetEntities(ids) {
  const url = new URL("https://www.wikidata.org/w/api.php");
  url.searchParams.set("action", "wbgetentities");
  url.searchParams.set("ids", ids.join("|"));
  url.searchParams.set("props", "claims|descriptions|labels|sitelinks/urls");
  url.searchParams.set("languages", "en");
  url.searchParams.set("format", "json");
  const data = await fetchJSON(url.toString());
  return data.entities || {};
}

const P31 = "P31"; // instance of
const MUSICAL_TYPES = new Set([
  "Q215380", // musical group
  "Q2088357", // musical ensemble
  "Q177220", // singer
  "Q639669", // musician
  "Q2259451", // rapper
  "Q483501", // disc jockey
  "Q5741069", // band
]);
const NON_MUSICAL_TYPES = new Set([
  "Q484170", // commune of France
  "Q486972", // human settlement
  "Q515", // city
  "Q532", // village
  "Q11424", // film
  "Q482994", // album
  "Q11451", // single
]);

function extractP31(ent) {
  const cl = ent?.claims?.[P31] || [];
  const out = [];
  for (const c of cl) {
    const id = c?.mainsnak?.datavalue?.value?.id;
    if (id) out.push(id);
  }
  return out;
}

function scoreEntity(name, ent) {
  const label = ent?.labels?.en?.value || "";
  const desc = ent?.descriptions?.en?.value || "";
  const types = extractP31(ent);
  const enwiki = ent?.sitelinks?.enwiki?.title || null;
  let score = 0;
  if (label.toLowerCase() === name.toLowerCase()) score += 3;
  if (enwiki && enwiki.toLowerCase() === name.toLowerCase()) score += 4;
  if (types.some(t => MUSICAL_TYPES.has(t))) score += 6;
  if (["band","musical group","musician","singer","rapper","dj"].some(k => desc.toLowerCase().includes(k))) score += 2;
  if (enwiki) score += 1;
  if (types.some(t => NON_MUSICAL_TYPES.has(t))) score -= 6;
  return score;
}

export async function wdSearchArtist(name) {
  const url = new URL("https://www.wikidata.org/w/api.php");
  url.searchParams.set("action", "wbsearchentities");
  url.searchParams.set("search", name);
  url.searchParams.set("type", "item");
  url.searchParams.set("language", "en");
  url.searchParams.set("format", "json");
  const data = await fetchJSON(url.toString());
  const candidates = (data.search || []).slice(0, 10);
  if (!candidates.length) return null;
  const ids = candidates.map(c => c.id);
  const entities = await wdGetEntities(ids);
  let best = null, bestScore = -Infinity;
  for (const id of ids) {
    const ent = entities[id];
    if (!ent) continue;
    const s = scoreEntity(name, ent);
    if (s > bestScore) { best = ent; bestScore = s; }
  }
  // If best is non-musical, try to pick a musical candidate from the same batch
  if (best && !extractP31(best).some(t => MUSICAL_TYPES.has(t))) {
    let altBest = null; let altScore = -Infinity;
    for (const id of ids) {
      const ent = entities[id];
      if (!ent) continue;
      const types = extractP31(ent);
      if (!types.some(t => MUSICAL_TYPES.has(t))) continue;
      const s = scoreEntity(name, ent);
      if (s > altScore) { altBest = ent; altScore = s; }
    }
    if (altBest) best = altBest;
  }

  // Fallback searches with band-specific hints if still non-musical
  if (!best || !extractP31(best).some(t => MUSICAL_TYPES.has(t))) {
    const hints = [
      `${name} band`,
      `${name} (band)`,
      `${name} musical group`
    ];
    for (const h of hints) {
      url.searchParams.set("search", h);
      const d2 = await fetchJSON(url.toString());
      const cand2 = (d2.search || []).slice(0, 10);
      if (!cand2.length) continue;
      const ids2 = cand2.map(c => c.id);
      const ents2 = await wdGetEntities(ids2);
      let b2 = null; let s2 = -Infinity;
      for (const id of ids2) {
        const ent = ents2[id];
        if (!ent) continue;
        if (!extractP31(ent).some(t => MUSICAL_TYPES.has(t))) continue;
        const sc = scoreEntity(name, ent);
        if (sc > s2) { b2 = ent; s2 = sc; }
      }
      if (b2) { best = b2; break; }
    }
  }

  if (!best) return null;
  return {
    qid: best.id,
    label: best?.labels?.en?.value || name,
    description: best?.descriptions?.en?.value || null
  };
}

export async function wdGetEnwikiTitle(qid) {
  const url = new URL("https://www.wikidata.org/w/api.php");
  url.searchParams.set("action", "wbgetentities");
  url.searchParams.set("ids", qid);
  url.searchParams.set("props", "sitelinks/urls|labels");
  url.searchParams.set("format", "json");
  const data = await fetchJSON(url.toString());
  return data.entities?.[qid]?.sitelinks?.enwiki?.title || null;
}

export async function wdGetArtistGenres(qid) {
  const q = `
    SELECT (GROUP_CONCAT(DISTINCT ?gLabel; separator=", ") AS ?genres)
    WHERE { wd:${qid} wdt:P136 ?g . ?g rdfs:label ?gLabel FILTER(LANG(?gLabel) = "en") }
  `;
  const rows = await sparql(q);
  return rows.length ? collectGenres(rows[0]) : [];
}

export async function wdGetSongs(qid, limit = MAX_SONGS) {
  const q = `
    SELECT ?item ?itemLabel ?date (GROUP_CONCAT(DISTINCT ?gLabel; separator=", ") AS ?genres) ?wpUrl WHERE {
      VALUES ?class { wd:Q7366 wd:Q134556 } # song, single
      ?item wdt:P31/wdt:P279* ?class ;
            wdt:P175 wd:${qid} .
      OPTIONAL { ?item wdt:P577 ?date . }
      OPTIONAL { ?item wdt:P136 ?g . ?g rdfs:label ?gLabel FILTER(LANG(?gLabel) = "en") }
      OPTIONAL {
        ?article schema:about ?item ;
                 schema:inLanguage "en" ;
                 schema:isPartOf <https://en.wikipedia.org/> .
        BIND(STR(?article) AS ?wpUrl)
      }
      SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
    }
    GROUP BY ?item ?itemLabel ?date ?wpUrl
    ORDER BY ASC(?date)
    LIMIT ${limit}
  `;
  const rows = await sparql(q);
  return rows.map(r => ({
    title: literal(r.itemLabel),
    year: toYear(literal(r.date)),
    genres: collectGenres(r),
    wikipedia_url: literal(r.wpUrl) || null,
    wikidata: literal(r.item) || null
  }));
}

export async function wdGetAlbums(qid, limit = MAX_ALBUMS) {
  const q = `
    SELECT ?item ?itemLabel ?date (GROUP_CONCAT(DISTINCT ?gLabel; separator=", ") AS ?genres) ?wpUrl WHERE {
      VALUES ?class { wd:Q482994 wd:Q169930 wd:Q2031291 wd:Q209756 wd:Q208569 } # album, EP, mixtape, live, compilation
      ?item wdt:P31/wdt:P279* ?class ;
            wdt:P175 wd:${qid} .
      OPTIONAL { ?item wdt:P577 ?date . }
      OPTIONAL { ?item wdt:P136 ?g . ?g rdfs:label ?gLabel FILTER(LANG(?gLabel) = "en") }
      OPTIONAL {
        ?article schema:about ?item ;
                 schema:inLanguage "en" ;
                 schema:isPartOf <https://en.wikipedia.org/> .
        BIND(STR(?article) AS ?wpUrl)
      }
      SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
    }
    GROUP BY ?item ?itemLabel ?date ?wpUrl
    ORDER BY ASC(?date)
    LIMIT ${limit}
  `;
  const rows = await sparql(q);
  return rows.map(r => ({
    title: literal(r.itemLabel),
    year: toYear(literal(r.date)),
    genres: collectGenres(r),
    wikipedia_url: literal(r.wpUrl) || null,
    wikidata: literal(r.item) || null
  }));
}

export async function wikipediaSummary(title) {
  if (!title) return null;
  const url = `https://en.wikipedia.org/api/rest_v1/page/summary/${encodeURIComponent(title)}`;
  try {
    const j = await fetchJSON(url);
    return { title: j.title, extract: j.extract, url: j.content_urls?.desktop?.page || `https://en.wikipedia.org/wiki/${encodeURIComponent(title)}`, thumbnail: j.thumbnail?.source || null };
  } catch { return null; }
}

export async function withSummaries(list, concurrency = SUMMARY_CONCURRENCY, { enrichInfobox = false } = {}) {
  const out = [];
  let i = 0;
  function extractYear(text) {
    if (!text) return null;
    const m = text.match(/\b(19\d{2}|20\d{2})\b/);
    return m ? Number(m[1]) : null;
  }
  async function worker() {
    while (i < list.length) {
      const idx = i++;
      const item = list[idx];
      const title = titleFromWikipediaUrl(item.wikipedia_url);
      const summary = title ? await wikipediaSummary(title) : null;
      let year = item.year;
      if (!year && summary?.extract) {
        const y = extractYear(summary.extract);
        if (y) year = y;
      }
      let infoboxGenresRaw = [];
      let infoboxGenresNormalized = [];
      let genresMergedNormalized = item.genres;
      if (enrichInfobox && title) {
        const infobox = await getWikiInfobox(title).catch(() => null);
        if (infobox?.genre) {
          infoboxGenresRaw = infobox.genre.split(/\s*[;,|]\s*|\n+/).map(g => g.trim()).filter(Boolean);
          infoboxGenresNormalized = normalizeInfoboxGenres(infobox.genre, 6);
          const wdGenresNorm = normalizeInfoboxGenres((item.genres || []).join(" | "), 10);
          const mergedSet = new Set([...wdGenresNorm, ...infoboxGenresNormalized]);
          genresMergedNormalized = Array.from(mergedSet);
        }
      }
      out[idx] = { ...item, year, summary, infoboxGenresRaw, infoboxGenresNormalized, genresMergedNormalized };
      await sleep(50);
    }
  }
  await Promise.all(Array.from({ length: Math.max(1, concurrency) }, worker));
  return out;
}

export async function wdArtistOverview(name, opts = {}) {
  const { maxSongs = MAX_SONGS, maxAlbums = MAX_ALBUMS, includeSummaries = false } = opts;
  const entity = await wdSearchArtist(name);
  if (!entity) return null;
  const title = await wdGetEnwikiTitle(entity.qid);
  const artistSummary = await wikipediaSummary(title);
  const artistGenres = await wdGetArtistGenres(entity.qid);
  let songs = await wdGetSongs(entity.qid, maxSongs);
  let albums = await wdGetAlbums(entity.qid, maxAlbums);
  if (includeSummaries) {
    songs = await withSummaries(songs, SUMMARY_CONCURRENCY, { enrichInfobox: true });
    albums = await withSummaries(albums, SUMMARY_CONCURRENCY, { enrichInfobox: true });
  }
  const genresOriginal = artistGenres;
  const genresNormalized = genresOriginal && genresOriginal.length
    ? normalizeInfoboxGenres(genresOriginal.join(" | "), 4) : [];
  const genreCombined = genresNormalized.length ? genresNormalized.join(", ") : null;
  return {
    artist: { name: entity.label || name, qid: entity.qid, description: entity.description || null, wikipedia: artistSummary, genres: artistGenres, genresOriginal, genresNormalized, genreCombined },
    counts: { songs: songs.length, albums: albums.length },
    songs, albums, generatedAt: new Date().toISOString()
  };
}
