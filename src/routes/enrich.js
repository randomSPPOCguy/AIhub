import { Router } from "express";
import { wikiTitleSearch, wikiSummary } from "../services/wiki.js";
import {
  mbSearchArtistByName,
  mbArtistGenresTags,
  mbReleaseGroupsFilteredByArtist,
  summarizeDiscography,
  sleep,
    } from "../services/musicbrainz.js";

      const router = Router();

// GET /api/enrich/artist?name=Massive%20Attack
router.get("/artist", async (req, res) => {
  try {
    const name = (req.query.name ?? "").toString().trim();
    if (!name) return res.status(400).json({ error: "missing name" });

    // ——— Wikipedia (primary): title search -> summary
    let wiki = null;
    try {
      const page = await wikiTitleSearch(name);
      const key = page?.key || page?.title || name;
      wiki = await wikiSummary(key);
    } catch (_) {
      wiki = null; // stay resilient
    }

    // ——— MusicBrainz (backfill): name -> MBID -> genres/tags -> album-only discography
    let hit = null;
    let mb = null;
    let discography = null;
    try {
      hit = await mbSearchArtistByName(name);
      if (hit?.id) {
        await sleep(1000); // ~1 req/sec per MB policy
        mb = await mbArtistGenresTags(hit.id);

        await sleep(1000);
        const rgs = await mbReleaseGroupsFilteredByArtist(hit.id, 200, 0);
        discography = summarizeDiscography(rgs);
      }
    } catch (_) {
      // leave mb/discography as null if MB errors
    }

    return res.json({
      artist: name,
      wiki,
      musicbrainz: hit
        ? {
            id: hit.id,
            name: hit.name,
            type: hit.type,
            country: hit.country,
            mb_genres: mb?.genres ?? [],
            mb_tags: mb?.tags ?? [],
            mb_merged: mb?.merged ?? [],
          }
        : null,
      discography,
    });
  } catch (err) {
    return res.status(500).json({ error: String(err?.message || err) });
  }
});

export default router;

