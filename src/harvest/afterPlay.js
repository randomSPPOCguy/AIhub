import { db } from "../db/connection.js";
import { wikiSummary, wikiTitleSearch, discogsSearch, mbReleaseGroupsByArtist, caaFrontForReleaseGroup } from "../search/providers.js";
import { logger } from "../utils/logger.js";
import GENRES from "../config/genres.js";

function keyify(s='') { return s.toLowerCase().replace(/[^a-z0-9]+/g, "_"); }

function canonicalGenre(input) {
  const k = keyify(input || "");
  return GENRES.aliasToKey[k] || null;
}

export async function onSongEnded(ev) {
  const playedAt = new Date().toISOString();
  const ins = db.prepare(`INSERT INTO plays
    (played_at_utc,room_id,username,user_id,artist,title,album,year,genre,provider,source)
    VALUES (?,?,?,?,?,?,?,?,?,?,?)`);
  const info = ins.run(
    playedAt, ev.roomId || null, ev.username || null, ev.userId || null,
    ev.artist || null, ev.title || null, ev.album || null, ev.year || null,
    ev.genre || null, ev.provider || "hang.fm", ev.eventId || null
  );
  const playId = info.lastInsertRowid;

  // resolve hints from genre map
  const gKey = canonicalGenre(ev.genre);
  const g = (gKey && GENRES.byKey[gKey]) ? GENRES.byKey[gKey] : null;

  // Discogs search with style hint
  const d = await discogsSearch({
    artist: ev.artist, track: ev.title, release_title: ev.album,
    style: g?.discogs?.style, year: ev.year
  });

  // Wikipedia: exact genre title first, then search by artist+title
  const wikiTry = g?.wikipedia?.[0] ? await wikiSummary(g.wikipedia[0]) : null;
  const titlePages = await wikiTitleSearch(`${ev.artist} ${ev.title}`);
  const wikiFirst = titlePages?.pages?.[0] || null;
  const wikiUrl = wikiFirst?.key ? `https://en.wikipedia.org/wiki/${wikiFirst.key}` :
    (wikiTry?.content_urls?.desktop?.page || null);
  const wikiTitle = wikiFirst?.title || wikiTry?.title || null;

  // MusicBrainz release-group count for the artist
  const rg = await mbReleaseGroupsByArtist(ev.artist || "");
  const rgCount = rg?.["release-groups"]?.length || 0;
  const rgId = rg?.["release-groups"]?.[0]?.id || null;

  let cover = null;
  try {
    if (rgId) {
      cover = await caaFrontForReleaseGroup(rgId);
    }
  } catch (e) {
    logger.debug("CAA fetch error:", e.message);
  }

  const up = db.prepare(`INSERT OR REPLACE INTO facts
    (play_id,wiki_title,wiki_url,discogs_id,discogs_type,mb_artist_id,mb_releasegroup_count,cover_url)
    VALUES (?,?,?,?,?,?,?,?)`);
  up.run(
    playId,
    wikiTitle, wikiUrl,
    d?.results?.[0]?.id || null,
    d?.results?.[0]?.type || null,
    rg?.["release-groups"]?.[0]?.["artist-credit"]?.[0]?.artist?.id || null,
    rgCount,
    cover
  );

  logger.info("Harvested play", playId, ev.artist, "-", ev.title);
  return { playId };
}
