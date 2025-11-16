// src/routes/enrich.artistFull.js
import { Router } from "express";
import { wikiTitleSearch, wikiSummary } from "../services/wiki.js";
import { mbArtistFullByName, mbAlbumRGsByArtist, mbCanonicalReleaseForRG, mbRecentEventsForArtist, sleep } from "../services/mb-extra.js";

const router = Router();

// GET /api/enrich/artist/full?name=Deftones
router.get("/artist/full", async (req, res) => {
  try {
    const name = (req.query.name ?? "").toString().trim();
    if (!name) return res.status(400).json({ error: "missing name" });

    // 1) Wikipedia summary (primary)
    let wiki = null;
    try {
      const page = await wikiTitleSearch(name);
      const key = page?.key || page?.title || name;
      wiki = await wikiSummary(key);
    } catch { wiki = null; }

    // 2) MusicBrainz full: aliases, genres/tags/ratings, url-rels, plus recent album RGs and events
    const mb = await mbArtistFullByName(name);
    if (!mb?.hit?.id) return res.json({ artist: name, wiki, musicbrainz: null, discography: null, recent: null });

    const artistId = mb.hit.id;

    // Album-only release groups in last 24 months
    const since = new Date(Date.now() - (730*86400e3));
    const rgs = await mbAlbumRGsByArtist(artistId, { since });

    // For up to 3 recent RGs, resolve a canonical Release and cover art
    const recentAlbums = [];
    for (const rg of rgs.slice(0, 3)) {
      await sleep(800); // be nice
      const release = await mbCanonicalReleaseForRG(rg.id).catch(() => null);
      recentAlbums.push({
        rgid: rg.id,
        title: rg.title,
        firstReleaseDate: rg['first-release-date'] || null,
        primaryType: rg['primary-type'] || null,
        secondaryTypes: rg['secondary-types'] || [],
        canonicalRelease: release
      });
    }

    // Recent / upcoming events (gigs, festivals)
    const events = await mbRecentEventsForArtist(artistId, { daysBack: 365, daysForward: 120 }).catch(() => []);

    // Shape url rels (filter to useful sources)
    const urlRels = (mb.full["relations"] || []).filter(r => r["target-type"] === 'url').map(r => ({
      type: r.type, url: r.url?.resource || null
    })).filter(x => x.url).filter(x => /wikipedia\.org|wikidata\.org|discogs\.com|allmusic\.com|bbc\.co\.uk|officialsite|bandcamp\.com|last\.fm/i.test(x.url));

    return res.json({
      artist: name,
      wiki,
      musicbrainz: {
        id: artistId,
        name: mb.hit.name,
        type: mb.hit.type,
        country: mb.hit.country || null,
        aliases: mb.full.aliases || [],
        mb_genres: (mb.full.genres || []).map(g => g.name),
        mb_tags: (mb.full.tags || []).map(t => t.name),
        ratings: mb.full.rating || null,
        urls: urlRels
      },
      recent: {
        album_release_groups: rgs, // raw
        top_albums: recentAlbums,  // resolved with cover art & tracklist
        events
      }
    });
  } catch (err) {
    return res.status(500).json({ error: String(err?.message || err) });
  }
});

export default router;
