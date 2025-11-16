import { Router } from "express";
import { db } from "../db/connection.js";
import GENRES from "../config/genres.js";

const router = Router();

router.get("/facts/latest", (req, res) => {
  const row = db.prepare(`
    SELECT p.*, f.wiki_title, f.wiki_url, f.discogs_id, f.discogs_type, f.mb_artist_id, f.mb_releasegroup_count, f.cover_url
    FROM plays p
    LEFT JOIN facts f ON f.play_id = p.id
    ORDER BY p.id DESC LIMIT 1;
  `).get();
  res.json(row || {});
});

router.get("/facts/by-artist", (req, res) => {
  const name = (req.query.name || "").toString().toLowerCase();
  if (!name) return res.status(400).json({ error: "name query required" });
  const row = db.prepare(`
    SELECT p.*, f.wiki_title, f.wiki_url, f.discogs_id, f.discogs_type, f.mb_artist_id, f.mb_releasegroup_count, f.cover_url
    FROM plays p
    LEFT JOIN facts f ON f.play_id = p.id
    WHERE lower(p.artist) = ?
    ORDER BY p.id DESC LIMIT 1;
  `).get(name);
  res.json(row || {});
});

router.get("/plays/recent", (req, res) => {
  const limit = Math.min(200, parseInt(req.query.limit || "20", 10));
  const rows = db.prepare(`SELECT * FROM plays ORDER BY id DESC LIMIT ?`).all(limit);
  res.json(rows);
});

router.get("/genres", (_req, res) => {
  res.json(GENRES);
});

export default router;
