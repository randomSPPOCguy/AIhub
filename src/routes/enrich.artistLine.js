// src/routes/enrich.artistLine.js
import { Router } from "express";
import {
  mbSearchArtistByName,
  mbArtistGenresTags,
  mbReleaseGroupsFilteredByArtist,
  sleep,
} from "../services/musicbrainz.js";
import { getWikiSummary } from "../services/wikipedia.js";

const router = Router();

// GET /api/enrich/artist/line?name=Massive%20Attack
// -> { line: "Artist — genres: g1, g2, g3 — latest album: Title (YYYY), N tracks", wikiId: "Artist_Name", artistMbid: "..." }
router.get("/artist/line", async (req, res) => {
  try {
    const name = (req.query.name ?? "").toString().trim();
    if (!name) return res.status(400).json({ error: "missing name" });

    // 1) resolve artist
    const hit = await mbSearchArtistByName(name).catch(() => null);
    if (!hit?.id) return res.status(404).json({ error: "artist not found" });

    // 1b) Fetch artist details with Wikipedia URL
    let wikiId = null;
    let wikiSummary = null;
    let wikiThumbnail = null;
    try {
      const ua = `${process.env.MB_UA_APP || "AIHubBot"}/${process.env.MB_UA_VERSION || "1.1"} (${process.env.MB_UA_CONTACT || "you@example.com"})`;
      const artistUrl = `https://musicbrainz.org/ws/2/artist/${hit.id}?inc=url-rels&fmt=json`;
      await sleep(250);
      const artistData = await fetch(artistUrl, { 
        headers: { "User-Agent": ua, "Accept": "application/json" } 
      }).then(r => r.ok ? r.json() : null);
      // Find Wikipedia URL in relations
      const wikiRel = artistData?.relations?.find(r => 
        r.type === 'wikipedia' && r.url?.resource?.includes('wikipedia.org/wiki/')
      );
      if (wikiRel) {
        wikiId = wikiRel.url.resource.split('/wiki/')[1];
        // Fetch Wikipedia summary and thumbnail
        const wikiData = await getWikiSummary(wikiId).catch(() => null);
        if (wikiData) {
          wikiSummary = wikiData.extract || null;
          wikiThumbnail = wikiData.thumbnail?.source || null;
        }
      }
    } catch { /* ignore wiki lookup errors */ }

    // 2+3) Run genres and release groups in parallel (saves ~1 second)
    await sleep(250);
    const [mb, rgs] = await Promise.all([
      mbArtistGenresTags(hit.id).catch(() => ({ genres: [], tags: [], merged: [] })),
      mbReleaseGroupsFilteredByArtist(hit.id, 200, 0).catch(() => [])
    ]);

    const score = new Map();
    const norm = s => (s || "").toString().trim().toLowerCase().replace(/\s*-\s*/g, " ");
    const push = (s, w) => { if (!s) return; const k = norm(s); score.set(k, (score.get(k) || 0) + w); };
    (mb.genres || []).forEach(g => push(g, 2)); // curated "genres" (subset of tags) → higher weight
    (mb.tags || []).forEach(t => push(t, 1));
    const top3 = [...score.entries()].sort((a,b) => b[1]-a[1]).slice(0,3).map(([k]) => k);

    // Find most recent studio album
    let latest = null;
    if (Array.isArray(rgs) && rgs.length) {
      latest = [...rgs].sort((a,b) =>
        (b["first-release-date"]||"").localeCompare(a["first-release-date"]||"")
      )[0];
    }

    let latestBits = null;
    if (latest?.id) {
      const ua = `${process.env.MB_UA_APP || "AIHubBot"}/${process.env.MB_UA_VERSION || "1.1"} (${process.env.MB_UA_CONTACT || "you@example.com"})`;
      const url = `https://musicbrainz.org/ws/2/release?release-group=${latest.id}&inc=labels+recordings+artist-credits&limit=100&fmt=json`;
      await sleep(250);
      try {
        const j = await fetch(url, { headers: { "User-Agent": ua, "Accept": "application/json" } })
          .then(r => r.ok ? r.json() : Promise.reject(new Error(`MB ${r.status}`)));
        const rels = j.releases || [];
        if (rels.length) {
          const pick = rels
            .map(r => ({ r, s: (r.status || "").toLowerCase()==="official" ? 1 : 0, d: (r["release-events"]?.[0]?.date) || r.date || "" }))
            .sort((a,b) => (b.s - a.s) || a.d.localeCompare(b.d))[0].r;
          const label = (pick["label-info"] || []).map(li => li.label?.name).filter(Boolean)[0] || null;
          let tracks = 0; (pick.media || []).forEach(m => { tracks += (m.tracks || []).length; });
          latestBits = { title: latest.title, year: (latest["first-release-date"]||"").slice(0,4) || null, label, tracks };
        }
      } catch { /* ignore */ }
    }

    const parts = [ hit.name ];
    if (top3.length) parts.push(`genres: ${top3.join(', ')}`);
    if (latestBits) {
      const y  = latestBits.year ? ` (${latestBits.year})` : '';
      const tr = latestBits.tracks ? `, ${latestBits.tracks} tracks` : '';
      parts.push(`latest album: ${latestBits.title}${y}${tr}`);
    }
    const line = parts.join(' — ');

    // Return both line and Wikipedia info
    return res.json({ 
      line,
      wikiId: wikiId || null,
      artistMbid: hit.id,
      wikiSummary,
      wikiThumbnail
    });

  } catch (err) {
    return res.status(500).json({ error: err.message || "internal error" });
  }
});

export default router;
