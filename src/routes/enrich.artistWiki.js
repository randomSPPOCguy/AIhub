// src/routes/enrich.artistWiki.js
import { Router } from "express";
import { wdArtistOverview } from "../services/wikidata.js";

const router = Router();

// GET /api/enrich/artist/wiki?name=Radiohead&songs=10&albums=10&summaries=1
router.get("/artist/wiki", async (req, res) => {
  try {
    const name = (req.query.name ?? "").toString().trim();
    if (!name) return res.status(400).json({ error: "missing name" });
    const songs = Number(req.query.songs || 10);
    const albums = Number(req.query.albums || 10);
    const summaries = String(req.query.summaries || "0") === "1";
    const data = await wdArtistOverview(name, { maxSongs: songs, maxAlbums: albums, includeSummaries: summaries });
    if (!data) return res.status(404).json({ error: "artist not found" });
    return res.json(data);
  } catch (err) {
    return res.status(500).json({ error: err.message || "internal error" });
  }
});

export default router;
