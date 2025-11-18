// src/routes/enrich.track.js
import { Router } from "express";
import { getSongInfo, getAlbumInfo, getArtistInfo } from "../services/wikipedia.js";
import { mbSearchRecording, sleep, mbGetWikipediaIdForRecording, mbGetWikipediaIdForReleaseGroup, mbGetWikipediaIdForArtist } from "../services/musicbrainz.js";
import { getMusicBrainzDataEnhanced } from "../services/musicbrainz.enhanced.js";
import { wdGetEnwikiTitle } from "../services/wikidata.js";
import { logger } from "../utils/logger.js";

const router = Router();

// Simple in-memory cache for enriched results (per title+artist)
// TTL default: 15 minutes
const ENRICH_TTL_MS = 15 * 60 * 1000;
const enrichCache = new Map(); // key -> { ts, value }

function cacheKeyFor(title, artist) {
  return `${(title || '').toLowerCase().trim()}|${(artist || '').toLowerCase().trim()}`;
}

function getCached(key) {
  const entry = enrichCache.get(key);
  if (!entry) return null;
  if (Date.now() - entry.ts > ENRICH_TTL_MS) {
    enrichCache.delete(key);
    return null;
  }
  return entry.value;
}

function setCached(key, value) {
  enrichCache.set(key, { ts: Date.now(), value });
}

// GET /api/enrich/track?title=Paranoid%20Android&artist=Radiohead
// -> Returns song info with genre, song summary, and album summary
router.get("/track", async (req, res) => {
  const startTime = Date.now(); // Start timer
  
  try {
    const title = (req.query.title ?? "").toString().trim();
    const artist = (req.query.artist ?? "").toString().trim();
    // Optional overrides via Wikidata QIDs
    const songQid = (req.query.songQid || req.query.trackQid || req.query.qid || "").toString().trim() || null;
    const albumQid = (req.query.albumQid || "").toString().trim() || null;
    
    if (!title) return res.status(400).json({ error: "missing title" });
    if (!artist) return res.status(400).json({ error: "missing artist" });

    // Cache check
    const key = cacheKeyFor(title, artist);
    const cached = getCached(key);
    if (cached) {
      return res.json({
        ...cached,
        timing: {
          elapsedMs: Date.now() - startTime,
          elapsedSeconds: ((Date.now() - startTime) / 1000).toFixed(2),
          elapsedFormatted: (() => {
            const totalMs = Date.now() - startTime;
            const minutes = Math.floor(totalMs / 60000);
            const seconds = ((totalMs % 60000) / 1000).toFixed(2);
            return minutes > 0 ? `${minutes}m ${seconds}s` : `${seconds}s`;
          })()
        },
        cache: { hit: true, ttlMs: ENRICH_TTL_MS }
      });
    }

    // 1) Fast path: Try Wikipedia direct search first (often succeeds in ~2-3s)
    let wikiId = null;
    let wikiFrom = null;
    let wikidataId = null;
    let recordingMbid = null;
    let releaseGroupMbid = null;
    let artistMbid = null;
    let recordingDetails = null;
    let wikiData = null;

    // Quick Wikipedia lookup to see if we can skip expensive MB enhanced pipeline
    try {
      const quickWikiData = await getSongInfo(title, artist).catch(() => null);
      if (quickWikiData?.album) {
        // Good data found - use it and skip enhanced MB
        wikiData = quickWikiData;
        wikiFrom = 'wikipedia-fast-path';
        logger.debug(`[ENRICH] Fast path succeeded for "${title}" - skipping MB enhanced`);
      }
    } catch {}

    let mbEnhanced = null;
    // Only run expensive MB enhanced if Wikipedia fast path didn't get good data
    if (!wikiData?.album) {
      try {
        mbEnhanced = await getMusicBrainzDataEnhanced(title, artist);
      } catch {}
    }

    if (mbEnhanced) {
      recordingMbid = mbEnhanced?.metadata?.recordingMbid || mbEnhanced?.recording?.id || null;
      releaseGroupMbid = mbEnhanced?.releaseGroup?.id || mbEnhanced?.metadata?.releaseGroupMbid || null;
      artistMbid = mbEnhanced?.artist?.id || mbEnhanced?.metadata?.artistMbid || null;
      recordingDetails = mbEnhanced?.recording || null;

      // Prefer direct Wikipedia link from recording, then release group
      const recWiki = mbEnhanced?.recording?.wikiLinks || {};
      const rgWiki = mbEnhanced?.releaseGroup?.wikiLinks || {};
      if (recWiki.wikipedia) {
        const idx = recWiki.wikipedia.indexOf('/wiki/');
        if (idx !== -1) {
          wikiId = recWiki.wikipedia.slice(idx + 6);
          wikiFrom = 'musicbrainz-enhanced-recording-wikipedia';
        }
      } else if (recWiki.wikidata) {
        // recWiki.wikidata like https://www.wikidata.org/wiki/Qxxxx
        const qid = (recWiki.wikidata.split('/').pop() || '').trim();
        if (qid) {
          wikidataId = qid;
          const enTitle = await wdGetEnwikiTitle(qid).catch(() => null);
          if (enTitle) {
            wikiId = encodeURIComponent(enTitle);
            wikiFrom = 'musicbrainz-enhanced-recording-wikidata';
          }
        }
      } else if (rgWiki.wikipedia) {
        const idx2 = rgWiki.wikipedia.indexOf('/wiki/');
        if (idx2 !== -1) {
          wikiId = rgWiki.wikipedia.slice(idx2 + 6);
          wikiFrom = 'musicbrainz-enhanced-releasegroup-wikipedia';
        }
      } else if (rgWiki.wikidata) {
        const qid2 = (rgWiki.wikidata.split('/').pop() || '').trim();
        if (qid2) {
          wikidataId = qid2;
          const enTitle2 = await wdGetEnwikiTitle(qid2).catch(() => null);
          if (enTitle2) {
            wikiId = encodeURIComponent(enTitle2);
            wikiFrom = 'musicbrainz-enhanced-releasegroup-wikidata';
          }
        }
      }
    }

    // Fallback to basic MB-to-wiki resolution if enhanced path didn't yield wikiId
    if (!wikiId) {
      try {
        const recording = await mbSearchRecording(title, artist);
        if (recording?.id) {
          recordingMbid = recordingMbid || recording.id;
          // 2) Resolve Wikipedia/Wikidata from MB relations (prefers direct wikipedia)
          await sleep(200);
          const rel = await mbGetWikipediaIdForRecording(recording.id).catch(() => null);
          if (rel?.source === 'wikipedia' && rel.wikiId) {
            wikiId = rel.wikiId;
            wikiFrom = 'musicbrainz-wikipedia';
          } else if (rel?.source === 'wikidata' && rel.wikidataId) {
            wikidataId = rel.wikidataId; // e.g., Q12345
            // 3) Convert Wikidata -> English Wikipedia title via sitelink
            const enTitle = await wdGetEnwikiTitle(rel.wikidataId).catch(() => null);
            if (enTitle) {
              wikiId = encodeURIComponent(enTitle);
              wikiFrom = 'musicbrainz-wikidata';
            }
          } else {
            // 3b) Fallback: look at recording details to try release-group and artist relations
            await sleep(200);
            const ua = `${process.env.MB_UA_APP || "AIHubBot"}/${process.env.MB_UA_VERSION || "1.1"} (${process.env.MB_UA_CONTACT || "you@example.com"})`;
            const detailsUrl = `https://musicbrainz.org/ws/2/recording/${recording.id}?inc=releases+artist-credits+url-rels&fmt=json`;
            const details = await fetch(detailsUrl, { headers: { "User-Agent": ua, "Accept": "application/json" } }).then(r => r.ok ? r.json() : null);
            recordingDetails = recordingDetails || details;
            // Try release-group
            const firstRelease = details?.releases?.[0];
            const releaseGroupId = firstRelease?.["release-group"]?.id || firstRelease?.releaseGroup?.id; // accommodate casing
            if (releaseGroupId) releaseGroupMbid = releaseGroupMbid || releaseGroupId;
            if (releaseGroupId) {
              await sleep(200);
              const relRG = await mbGetWikipediaIdForReleaseGroup(releaseGroupId).catch(() => null);
              if (relRG?.source === 'wikipedia' && relRG.wikiId) {
                wikiId = relRG.wikiId;
                wikiFrom = 'musicbrainz-wikipedia-rg';
              } else if (relRG?.source === 'wikidata' && relRG.wikidataId) {
                wikidataId = relRG.wikidataId;
                const enTitle2 = await wdGetEnwikiTitle(relRG.wikidataId).catch(() => null);
                if (enTitle2) {
                  wikiId = encodeURIComponent(enTitle2);
                  wikiFrom = 'musicbrainz-wikidata-rg';
                }
              }
            }
            // Try primary artist if still missing
            if (!wikiId) {
              const firstArtist = details?.["artist-credit"]?.[0]?.artist || details?.artistCredit?.[0]?.artist;
              const artistIdMB = firstArtist?.id;
              if (artistIdMB) artistMbid = artistMbid || artistIdMB;
              if (artistIdMB) {
                await sleep(200);
                const relA = await mbGetWikipediaIdForArtist(artistIdMB).catch(() => null);
                if (relA?.source === 'wikipedia' && relA.wikiId) {
                  wikiId = relA.wikiId;
                  wikiFrom = 'musicbrainz-wikipedia-artist';
                } else if (relA?.source === 'wikidata' && relA.wikidataId) {
                  wikidataId = relA.wikidataId;
                  const enTitle3 = await wdGetEnwikiTitle(relA.wikidataId).catch(() => null);
                  if (enTitle3) {
                    wikiId = encodeURIComponent(enTitle3);
                    wikiFrom = 'musicbrainz-wikidata-artist';
                  }
                }
              }
            }
          }
        }
      } catch { /* ignore MusicBrainz errors */ }
    }

    // Explicit override via song/track Wikidata QID
    if (!wikiId && songQid) {
      const enTitle = await wdGetEnwikiTitle(songQid).catch(() => null);
      if (enTitle) {
        wikidataId = songQid;
        wikiId = encodeURIComponent(enTitle);
        wikiFrom = 'wikidata-param';
      }
    }

    // 4) Get Wikipedia info if not already fetched via fast path
    // The enhanced getSongInfo handles disambiguation and search fallback automatically
    if (!wikiData) {
      if (wikiId && !(wikiFrom && wikiFrom.endsWith('-artist'))) {
        wikiData = await getSongInfo(wikiId).catch(() => null);
      }
      if (!wikiData || !wikiData.album || (wikiFrom && wikiFrom.endsWith('-artist'))) {
        const searchData = await getSongInfo(title, artist).catch(() => null);
        if (searchData) {
          wikiData = searchData;
          if (wikiFrom && wikiFrom.endsWith('-artist')) {
            wikiFrom = wikiFrom + '+fallback-song-search';
          } else if (!wikiFrom) {
            wikiFrom = 'wikipedia-search';
          }
        }
      }
    }
    
    // 5) Get album summary if we have album info
    let albumSummary = null;
    let albumWikiId = null;
    let albumWikidataId = albumQid || null;
    let albumInfo = null;

    // 5a) Prepare album name: prefer wikiData.album, else MB releaseGroup title
    const albumNameForLookup = wikiData?.album || mbEnhanced?.releaseGroup?.title || null;

    // 5b) Run album and artist lookups in parallel when possible
    let artistSummary = null;
    let artistGenres = null;
    let artistGenresArray = null;
    if (albumNameForLookup || (wikiData?.artist || artist)) {
      const [albumInfoResult, artistInfo] = await Promise.all([
        albumNameForLookup ? getAlbumInfo(albumNameForLookup, artist).catch(() => null) : Promise.resolve(null),
        getArtistInfo(wikiData?.artist || artist).catch(() => null)
      ]);
      albumInfo = albumInfoResult;
      albumSummary = albumInfo?.summary || null;
      artistSummary = artistInfo?.summary || null;
      artistGenres = artistInfo?.genres || null;
      artistGenresArray = artistInfo?.genresArray || null;
    }
    
    // (artist info populated above in parallel step)

    // If albumQid provided, resolve its Wikipedia title for metadata (and optional future use)
    if (albumQid) {
      const enAlbum = await wdGetEnwikiTitle(albumQid).catch(() => null);
      if (enAlbum) {
        albumWikiId = encodeURIComponent(enAlbum);
      }
    }
    
    // Build a formatted line
    const parts = [title];
    // Prefer requested artist, add cover attribution when applicable
    const requestedArtist = artist;
    const isCover = !!wikiData?.isCover;
    const coverOriginalArtist = wikiData?.coverOriginalArtist || null;
    if (isCover && coverOriginalArtist && requestedArtist && requestedArtist.toLowerCase() !== (coverOriginalArtist || '').toLowerCase()) {
      parts.push(`${requestedArtist} (cover of ${coverOriginalArtist})`);
    } else if (wikiData?.artist) {
      parts.push(wikiData.artist);
    } else if (requestedArtist) {
      parts.push(requestedArtist);
    }
    if (wikiData?.album) {
      const year = wikiData.released ? ` (${wikiData.released})` : '';
      parts.push(`${wikiData.album}${year}`);
    }
    if (wikiData?.genreCombined) {
      parts.push(wikiData.genreCombined);
    }
    if (wikiData?.length) parts.push(wikiData.length);
    
    const line = parts.join(' — ');

    // If we didn't get wikiId via MB, derive it from the summary URL if available
    if (!wikiId && wikiData?.wikiUrl) {
      const idx = wikiData.wikiUrl.indexOf('/wiki/');
      if (idx !== -1) {
        wikiId = wikiData.wikiUrl.slice(idx + 6);
        wikiFrom = wikiFrom || 'wikipedia-search';
      }
    }

    // If we didn’t fetch recording details earlier and we want MB URLs, try a lightweight fetch
    if (!artistMbid || !releaseGroupMbid) {
      try {
        if (recordingMbid && !recordingDetails) {
          const ua = `${process.env.MB_UA_APP || "AIHubBot"}/${process.env.MB_UA_VERSION || "1.1"} (${process.env.MB_UA_CONTACT || "you@example.com"})`;
          const detailsUrl = `https://musicbrainz.org/ws/2/recording/${recordingMbid}?inc=releases+artist-credits&fmt=json`;
          const d = await fetch(detailsUrl, { headers: { "User-Agent": ua, "Accept": "application/json" } }).then(r => r.ok ? r.json() : null);
          const firstRelease = d?.releases?.[0];
          releaseGroupMbid = releaseGroupMbid || firstRelease?.["release-group"]?.id || firstRelease?.releaseGroup?.id || null;
          const firstArtist = d?.["artist-credit"]?.[0]?.artist || d?.artistCredit?.[0]?.artist;
          artistMbid = artistMbid || firstArtist?.id || null;
        }
      } catch {}
    }

    // Clean coverInfo section headers if present
    const cleanedCoverInfo = (() => {
      const raw = wikiData?.coverInfo || null;
      if (!raw) return null;
      // Remove lines like '== Section ==' and collapse extra blank lines
      return raw
        .replace(/^==[^=]+==\s*$/gm, "")
        .replace(/\n{3,}/g, "\n\n")
        .trim();
    })();

    // Build enhanced formatted display combining Wikipedia + MusicBrainz data
    const formatDuration = (ms) => {
      if (!ms) return null;
      const totalSeconds = Math.floor(ms / 1000);
      const minutes = Math.floor(totalSeconds / 60);
      const seconds = totalSeconds % 60;
      return `${minutes}:${seconds.toString().padStart(2, '0')}`;
    };

    const mbRecording = mbEnhanced?.recording;
    const mbArtist = mbEnhanced?.artist;
    const mbReleaseGroup = mbEnhanced?.releaseGroup;

    const formattedRows = [];
    
    // Header
    formattedRows.push(title);
    formattedRows.push('━'.repeat(70));
    
    // Artist row
    formattedRows.push(`Artist: ${wikiData?.artist || artist}`);
    if (mbArtist?.type) {
      formattedRows.push(`  Type: ${mbArtist.type}${mbArtist.country ? ` • ${mbArtist.country}` : ''}`);
    }
    if (mbArtist?.lifeSpan?.begin) {
      const years = mbArtist.lifeSpan.ended 
        ? `${mbArtist.lifeSpan.begin}–${mbArtist.lifeSpan.end || 'present'}`
        : `${mbArtist.lifeSpan.begin}–present`;
      formattedRows.push(`  Active: ${years}`);
    }
    formattedRows.push('─'.repeat(70));
    
    // Album row
    formattedRows.push(`Album: ${wikiData?.album || mbReleaseGroup?.title || 'Unknown'}`);
    if (wikiData?.released || mbReleaseGroup?.firstReleaseDate) {
      formattedRows.push(`  Released: ${wikiData?.released || mbReleaseGroup?.releaseYear || mbReleaseGroup?.firstReleaseDate}`);
    }
    if (mbReleaseGroup?.primaryType) {
      const types = [mbReleaseGroup.primaryType, ...(mbReleaseGroup.secondaryTypes || [])].join(' • ');
      formattedRows.push(`  Type: ${types}`);
    }
    if (mbReleaseGroup?.label) {
      formattedRows.push(`  Label: ${mbReleaseGroup.label}${mbReleaseGroup.catalogNumber ? ` (${mbReleaseGroup.catalogNumber})` : ''}`);
    }
    formattedRows.push('─'.repeat(70));
    
    // Track details row
    formattedRows.push('Track Details:');
    const wikiLength = wikiData?.length;
    const mbLength = mbRecording?.length ? formatDuration(mbRecording.length) : null;
    formattedRows.push(`  Duration: ${wikiLength || mbLength || 'Unknown'}`);
    if (mbRecording?.isrcs?.length > 0) {
      formattedRows.push(`  ISRC: ${mbRecording.isrcs[0]}`);
    }
    if (wikiData?.isCover) {
      formattedRows.push(`  Cover: ${wikiData.coverOriginalArtist || 'Unknown'} original${wikiData.coverYear ? ` (${wikiData.coverYear})` : ''}`);
    }
    formattedRows.push('─'.repeat(70));
    
    // Genres row (combined from all sources)
    const allGenres = new Set();
    if (wikiData?.genresNormalized) wikiData.genresNormalized.forEach(g => allGenres.add(g));
    if (albumInfo?.genresSelected) albumInfo.genresSelected.forEach(g => allGenres.add(g));
    if (mbRecording?.genres) mbRecording.genres.forEach(g => allGenres.add(g.name));
    if (mbReleaseGroup?.genres) mbReleaseGroup.genres.forEach(g => allGenres.add(g.name));
    if (artistGenresArray) artistGenresArray.forEach(g => allGenres.add(g));
    
    if (allGenres.size > 0) {
      formattedRows.push(`Genres: ${Array.from(allGenres).join(', ')}`);
      formattedRows.push('─'.repeat(70));
    }
    
    // Band members (if available)
    if (mbArtist?.members?.length > 0) {
      formattedRows.push('Band Members:');
      const displayMembers = mbArtist.members.slice(0, 6);
      displayMembers.forEach(member => {
        const period = member.begin ? ` (${member.begin}${member.end ? `–${member.end}` : '–present'})` : '';
        const instruments = member.attributes?.length > 0 ? ` • ${member.attributes.slice(0, 2).join(', ')}` : '';
        formattedRows.push(`  ${member.name}${period}${instruments}`);
      });
      if (mbArtist.members.length > 6) {
        formattedRows.push(`  ... and ${mbArtist.members.length - 6} more`);
      }
      formattedRows.push('─'.repeat(70));
    }
    
    // Wikipedia summaries
    if (wikiData?.summary) {
      formattedRows.push('Song Summary:');
      formattedRows.push(wikiData.summary);
      formattedRows.push('─'.repeat(70));
    }
    
    if (wikiData?.isCover && cleanedCoverInfo) {
      formattedRows.push('Cover Info:');
      formattedRows.push(cleanedCoverInfo);
      formattedRows.push('─'.repeat(70));
    }
    
    if (albumSummary) {
      formattedRows.push('Album Summary:');
      formattedRows.push(albumSummary);
      formattedRows.push('─'.repeat(70));
    }
    
    if (artistSummary) {
      formattedRows.push('Artist Summary:');
      formattedRows.push(artistSummary);
      formattedRows.push('─'.repeat(70));
    }

    const responsePayload = { 
      line,
      
      // Human-readable formatted output for display/bot parsing
      formatted: formattedRows.join('\n'),
      
      // Song details
      song: {
        title,
        artist: wikiData?.artist || artist,
        album: wikiData?.album || null,
        released: wikiData?.released || null,
        length: wikiData?.length || null,
        summary: wikiData?.summary || null,
        genresOriginal: wikiData?.genresOriginal || null,
        genresNormalized: wikiData?.genresNormalized || [],
        genreCombined: wikiData?.genreCombined || null,
        isCover: wikiData?.isCover || false,
        coverInfo: cleanedCoverInfo,
        coverOriginalArtist: wikiData?.coverOriginalArtist || null,
        coverYear: wikiData?.coverYear || null,
        originalReleaseYear: wikiData?.originalReleaseYear || null
      },
      
      // Album details with header + genre selections from infobox
      album: wikiData?.album ? {
        name: wikiData?.album,
        released: wikiData?.released || null,
        summary: albumSummary,
        genresOriginalArray: albumInfo?.genresOriginalArray || [],
        genresSelected: albumInfo?.genresSelected || [],
        genresSelectedDisplay: (albumInfo?.genresSelected || []).join(', ') || null,
        // Formatted display with sections
        display: [
          wikiData.album,
          '─'.repeat(60),
          'Album Genres: ' + ((albumInfo?.genresSelected || []).join(', ') || 'Unknown'),
          'Song Genres: ' + (wikiData?.genreCombined || 'Unknown'),
          '─'.repeat(60),
          'Released: ' + (wikiData.released || 'Unknown'),
          '─'.repeat(60),
          'Summary: ' + (albumSummary || 'No summary available')
        ].join('\n')
      } : null,
      
      // Artist details
      artist: {
        name: wikiData?.artist || artist,
        summary: artistSummary,
        genres: artistGenres,
        genresArray: artistGenresArray
      },
      
  // Genre display (combined)
  genre: wikiData?.genreCombined || null,
  genresOriginal: wikiData?.genresOriginal || null,
  genresNormalized: wikiData?.genresNormalized || [],
      
      // Additional metadata
      metadata: {
        wikiThumbnail: wikiData?.thumbnail || null,
        wikiUrl: wikiData?.wikiUrl || null,
        wikiId: wikiId || null,
        wikiFrom: wikiFrom || null,
        wikidataId: wikidataId || null,
        recordingMbid: recordingMbid || null,
        recordingUrl: recordingMbid ? `https://musicbrainz.org/recording/${recordingMbid}` : null,
        artistMbid: artistMbid || null,
        artistUrl: artistMbid ? `https://musicbrainz.org/artist/${artistMbid}` : null,
        releaseGroupMbid: releaseGroupMbid || null,
        releaseGroupUrl: releaseGroupMbid ? `https://musicbrainz.org/release-group/${releaseGroupMbid}` : null,
        albumWikidataId: albumWikidataId || null,
        albumWikiId: albumWikiId || null,
        albumWikiUrl: albumWikiId ? `https://en.wikipedia.org/wiki/${albumWikiId}` : null
      },
      
      // Timing information
      timing: {
        elapsedMs: Date.now() - startTime,
        elapsedSeconds: ((Date.now() - startTime) / 1000).toFixed(2),
        elapsedFormatted: (() => {
          const totalMs = Date.now() - startTime;
          const minutes = Math.floor(totalMs / 60000);
          const seconds = ((totalMs % 60000) / 1000).toFixed(2);
          return minutes > 0 ? `${minutes}m ${seconds}s` : `${seconds}s`;
        })()
      },
      cache: { hit: false, ttlMs: ENRICH_TTL_MS }
    };

    // Store in cache
    setCached(key, responsePayload);

    return res.json(responsePayload);

  } catch (err) {
    const elapsedMs = Date.now() - startTime;
    const minutes = Math.floor(elapsedMs / 60000);
    const seconds = ((elapsedMs % 60000) / 1000).toFixed(2);
    const elapsed = minutes > 0 ? `${minutes}m ${seconds}s` : `${seconds}s`;
    
    return res.status(500).json({ 
      error: err.message || "internal error",
      timing: { elapsedMs, elapsedFormatted: elapsed }
    });
  }
});

export default router;
