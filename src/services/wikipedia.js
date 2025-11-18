// src/services/wikipedia.enhanced.js
// Enhanced Wikipedia API helpers with proper disambiguation, search fallback, and cover detection

import { logger } from "../utils/logger.js";

const wikiInfo = (message, meta) => logger.info(`[WIKI] ${message}`, meta);
const wikiWarn = (message, meta) => logger.warn(`[WIKI] ${message}`, meta);
const wikiError = (message, meta) => logger.error(`[WIKI] ${message}`, meta);
const wikiDebug = (message, meta) => logger.debug(`[WIKI] ${message}`, meta);

// Simple sleep helper
const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));

// In-memory cache for summary/infobox/search results (single-process)
const summaryCache = new Map();
const infoboxCache = new Map();
const searchCache = new Map();

// Get basic Wikipedia summary (includes extract, thumbnail, description)
export async function getWikiSummary(articleTitle) {
  const cacheKey = articleTitle.toLowerCase();
  if (summaryCache.has(cacheKey)) {
    return summaryCache.get(cacheKey);
  }
  
  await sleep(100); // Rate limit: 100ms between calls (reduced from 250ms for speed)
  const encoded = encodeURIComponent(articleTitle);
  const url = `https://en.wikipedia.org/api/rest_v1/page/summary/${encoded}`;
  
  try {
    const response = await fetch(url);
    if (!response.ok) return null;
    const data = await response.json();
    summaryCache.set(cacheKey, data);
    return data;
  } catch (err) {
    wikiError(`[WIKI] getWikiSummary error for "${articleTitle}":`, err.message);
    return null;
  }
}

// Full page plain-text extract (not limited to intro) - needed for cover detection
export async function getWikiExtractFull(articleTitle) {
  await sleep(100); // Reduced from 250ms
  const encoded = encodeURIComponent(articleTitle);
  const url = `https://en.wikipedia.org/w/api.php?action=query&prop=extracts&titles=${encoded}&format=json&explaintext=1&redirects=true`;
  
  try {
    const response = await fetch(url);
    if (!response.ok) return null;
    const data = await response.json();
    const pages = data?.query?.pages;
    if (!pages) return null;
    const pageId = Object.keys(pages)[0];
    return pages[pageId]?.extract || null;
  } catch (err) {
    wikiError(`[WIKI] getWikiExtractFull error:`, err.message);
    return null;
  }
}

// Wikipedia search API - returns array of search results with title, description
export async function searchWikipedia(query) {
  const cacheKey = query.toLowerCase();
  if (searchCache.has(cacheKey)) {
    return searchCache.get(cacheKey);
  }
  
  await sleep(100); // Reduced from 250ms
  const encoded = encodeURIComponent(query);
  const url = `https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch=${encoded}&format=json&srlimit=10`;
  
  try {
    const response = await fetch(url);
    if (!response.ok) return [];
    const data = await response.json();
    const results = data?.query?.search || [];
    searchCache.set(cacheKey, results);
    return results;
  } catch (err) {
    wikiError(`[WIKI] searchWikipedia error:`, err.message);
    return [];
  }
}

// Check if a page is a disambiguation page or generic concept
function isDisambiguationOrGeneric(summary) {
  if (!summary) return { isDisambiguation: false, isGeneric: false };
  
  const extract = (summary.extract || '').toLowerCase();
  const description = (summary.description || '').toLowerCase();
  
  // Check for disambiguation indicators
  const isDisambiguation = /may refer to:|refers to:/i.test(extract);
  
  // Check if it's a generic concept page (lacks music-related words)
  const musicWords = ['band', 'musical group', 'singer', 'musician', 'rapper', 'artist', 'duo', 'trio', 'song', 'single', 'album', 'track'];
  const hasMusic = musicWords.some(word => extract.includes(word) || description.includes(word));
  const isGeneric = !hasMusic;
  
  return { isDisambiguation, isGeneric };
}

// Clean wikitext markup to plain text
function cleanWikitext(text) {
  if (!text) return null;
  
  return text
    // Remove comments
    .replace(/<!--.*?-->/gs, '')
    // Preserve nowrap inner content
    .replace(/\{\{nowrap\|([^{}]+)\}\}/gi, '$1')
    // Remove templates like {{Start date|1991|09|10}} -> extract just the date parts
    .replace(/\{\{Start date\|(\d+)\|(\d+)\|(\d+)\}\}/gi, '$1-$2-$3')
    // Remove {{Duration|m=5|s=01}} -> convert to readable format
    .replace(/\{\{Duration\|m=(\d+)\|s=(\d+)\}\}/gi, '$1:$2')
    // Handle {{flatlist}} and similar - remove the wrapper but keep content
    .replace(/\{\{flatlist\s*\|\s*/gi, '')
    .replace(/\{\{hlist\s*\|\s*/gi, '')
    // Remove all other nested templates {{...}}
    .replace(/\{\{[^{}]*(?:\{\{[^{}]*\}\}[^{}]*)*\}\}/g, '')
    // Remove wiki links [[Link|Text]] -> Text or [[Link]] -> Link
    .replace(/\[\[(?:[^|\]]+\|)?([^\]]+)\]\]/g, '$1')
    // Remove simple brackets
    .replace(/\[\[|\]\]/g, '')
    // Remove HTML tags
    .replace(/<[^>]+>/g, '')
    // Remove extra asterisks and list markers
    .replace(/^\s*[\*#]+\s*/gm, '')
    // Remove ref tags
    .replace(/<ref[^>]*>.*?<\/ref>/gi, '')
    .replace(/<ref[^>]*\/>/gi, '')
    // Remove extra quotes
    .replace(/['''"""]/g, '')
    // Clean up multiple spaces
    .replace(/\s+/g, ' ')
    // Trim whitespace
    .trim()
    // Return null if empty after cleaning
    || null;
}

// Get infobox data from Wikipedia page (for structured data like genres, years, duration)
export async function getWikiInfobox(articleTitle) {
  const cacheKey = articleTitle.toLowerCase();
  if (infoboxCache.has(cacheKey)) {
    return infoboxCache.get(cacheKey);
  }
  
  await sleep(100); // Rate limit: 100ms between calls (reduced from 250ms for speed)
  const encoded = encodeURIComponent(articleTitle);
  const url = `https://en.wikipedia.org/w/api.php?action=query&prop=revisions&titles=${encoded}&rvprop=content&format=json&rvslots=main&redirects=true`;
  
  wikiDebug(`[WIKI] getWikiInfobox fetching: "${articleTitle}"`);
  
  try {
    const response = await fetch(url);
    if (!response.ok) {
      wikiDebug(`[WIKI] getWikiInfobox fetch failed:`, response.status);
      return null;
    }
    
    const data = await response.json();
    
    // Log if we followed a redirect
    if (data.query && data.query.redirects) {
      const redirect = data.query.redirects[0];
      wikiDebug(`[WIKI] Followed redirect: "${redirect.from}" -> "${redirect.to}"`);
    }

    const pages = data?.query?.pages;
    if (!pages) {
      wikiDebug(`[WIKI] getWikiInfobox no pages in response`);
      return null;
    }
    
    const pageId = Object.keys(pages)[0];
    const content = pages[pageId]?.revisions?.[0]?.slots?.main?.['*'];
    if (!content) {
      wikiDebug(`[WIKI] getWikiInfobox no content for pageId:`, pageId);
      return null;
    }
    
    // Find the infobox - handle nested braces properly
    // Look for case-insensitive "{{Infobox" (handles {{Infobox song}}, {{Infobox single}}, etc.)
    const infoboxMatch = content.match(/\{\{Infobox/i);
    if (!infoboxMatch) {
      wikiDebug(`[WIKI] getWikiInfobox no {{Infobox found in content`);
      return null;
    }
    const infoboxStart = infoboxMatch.index;
    
    wikiDebug(`[WIKI] getWikiInfobox found infobox at position:`, infoboxStart);
    
    // Find matching closing braces
    let braceCount = 0;
    let infoboxEnd = -1;
    for (let i = infoboxStart; i < content.length - 1; i++) {
      if (content[i] === '{' && content[i + 1] === '{') {
        braceCount++;
        i++;
      } else if (content[i] === '}' && content[i + 1] === '}') {
        braceCount--;
        i++;
        if (braceCount === 0) {
          infoboxEnd = i + 1;
          break;
        }
      }
    }
    
    if (infoboxEnd === -1) {
      wikiDebug(`[WIKI] getWikiInfobox couldn't find closing braces`);
      return null;
    }
    
    wikiDebug(`[WIKI] getWikiInfobox extracted infobox, length:`, infoboxEnd - infoboxStart);
    
    const infoboxContent = content.substring(infoboxStart, infoboxEnd);
    const fields = {};
    
    // Parse field by field, handling multi-line values
    const lines = infoboxContent.split('\n');
    let currentField = null;
    let currentValue = [];
    
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      
      // Check if this is a new field definition
      const fieldMatch = line.match(/^\s*\|\s*([^=]+?)\s*=\s*(.*)$/);
      
      if (fieldMatch) {
        // Save previous field if exists
        if (currentField) {
          const key = currentField.toLowerCase().trim();
          const value = currentValue.join('\n').trim();
          
          if (['album', 'from album', 'from', 'from_album', 'from-album'].includes(key)) fields.album = value;
          if (['released', 'published', 'recorded'].includes(key)) fields.released = value;
          if (['genre', 'genres'].includes(key)) fields.genre = value;
          if (['length', 'duration'].includes(key)) fields.length = value;
          if (['artist', 'name'].includes(key)) fields.artist = value;
          if (['original_artist', 'original artist', 'writer', 'cover_of'].includes(key)) fields.original_artist = value;
          if (['original_year', 'original year'].includes(key)) fields.original_year = value;
        }
        
        currentField = fieldMatch[1].trim();
        // Remove leading bullets/asterisks from value
        currentValue = [fieldMatch[2].replace(/^\s*[\*\-\•]\s*/, '')];
      } else if (currentField && line.trim() && !line.trim().startsWith('{{Infobox')) {
        if (!line.trim().startsWith('|')) {
          // Remove bullets from continuation lines too
          currentValue.push(line.replace(/^\s*[\*\-\•]\s*/, ''));
        }
      }
    }
    
    // Don't forget the last field
    if (currentField) {
      const key = currentField.toLowerCase().trim();
      const value = currentValue.join('\n').trim();
      
      if (['album', 'from album', 'from', 'from_album', 'from-album'].includes(key)) fields.album = value;
      if (['released', 'published', 'recorded'].includes(key)) fields.released = value;
      if (['genre', 'genres'].includes(key)) fields.genre = value;
      if (['length', 'duration'].includes(key)) fields.length = value;
      if (['artist', 'name'].includes(key)) fields.artist = value;
      if (['original_artist', 'original artist', 'writer', 'cover_of'].includes(key)) fields.original_artist = value;
      if (['original_year', 'original year'].includes(key)) fields.original_year = value;
    }
    
    // Clean all extracted fields EXCEPT genre (we need to split it first)
    for (const key in fields) {
      if (key !== 'genre') {
        fields[key] = cleanWikitext(fields[key]);
      }
    }
    
    wikiDebug(`[WIKI] getWikiInfobox extracted fields:`, Object.keys(fields).length, 'fields ->', fields);
    
    infoboxCache.set(cacheKey, fields);
    return fields;
  } catch (err) {
    wikiError(`[WIKI] getWikiInfobox error:`, err.message);
    return null;
  }
}

// Split and clean genre field properly - split on pipes, commas, newlines FIRST, then clean each
function splitAndCleanGenres(rawGenre) {
  if (!rawGenre) return [];
  
  wikiDebug(`[WIKI] splitAndCleanGenres - raw input:`, rawGenre);
  
  // First, split on newlines to preserve individual genre entries
  const lines = rawGenre.split(/\n+/).map(l => l.trim()).filter(Boolean);
  
  wikiDebug(`[WIKI] splitAndCleanGenres - after newline split:`, lines);
  
  const allGenres = [];
  
  for (const line of lines) {
    // Remove citation content BEFORE cleaning wikitext
    // Pattern 1: Remove everything inside <ref>...</ref> tags
    let processed = line.replace(/<ref[^>]*>.*?<\/ref>/gi, '');
    // Pattern 2: Remove self-closing ref tags like <ref name="..." />
    processed = processed.replace(/<ref[^>]*\/>/gi, '');
    
    // Clean the line to remove wiki markup
    let cleaned = cleanWikitext(processed);
    if (!cleaned) continue;
    
    // Now split on pipes, commas, semicolons
    const parts = cleaned.split(/[|,;]+/).map(p => p.trim()).filter(Boolean);
    
    for (const part of parts) {
      // Remove trailing words like "music" or "genre"
      let final = part.replace(/\b(music|genre)\b/i, '').trim();
      // Remove any remaining template artifacts like }} or {{
      final = final.replace(/^\{\{|\}\}$/g, '').trim();
      if (final && final.length > 0 && final !== '}}' && final !== '{{') {
        allGenres.push(final);
      }
    }
  }
  
  wikiDebug(`[WIKI] splitAndCleanGenres - final array:`, allGenres);
  
  return allGenres;
}

// Extract release date from infobox field or extract
function extractReleaseDate(releasedField, extract) {
  if (releasedField) {
    // Try to extract 4-digit year
    const yearMatch = releasedField.match(/\b(19\d{2}|20\d{2})\b/);
    if (yearMatch) return yearMatch[1];
  }
  
  if (extract) {
    // Look for "released in YYYY" or "published in YYYY" patterns
    const releaseMatch = extract.match(/(?:released|published)\s+(?:in\s+)?(\d{4})/i);
    if (releaseMatch) return releaseMatch[1];
  }
  
  return null;
}

// Extract cover information from full page content
function extractCoverInfo(fullExtract, artistName) {
  if (!fullExtract || !artistName) return { sentences: [], year: null };
  
  const artistLower = artistName.toLowerCase();
  const sentences = fullExtract.split(/[.!?]+/).map(s => s.trim()).filter(Boolean);
  
  const coverSentences = [];
  let coverYear = null;
  
  for (const sentence of sentences) {
    const sentenceLower = sentence.toLowerCase();
    
    // Look for sentences containing "cover" or "covered" AND the artist name
    if ((sentenceLower.includes('cover') || sentenceLower.includes('covered')) && 
        sentenceLower.includes(artistLower)) {
      coverSentences.push(sentence);
      
      // Try to extract a year from this sentence
      const yearMatch = sentence.match(/\b(19\d{2}|20\d{2})\b/);
      if (yearMatch && !coverYear) {
        coverYear = yearMatch[1];
      }
    }
  }
  
  return { sentences: coverSentences, year: coverYear };
}

// Normalize genres into canonical set (limit to max 3-5)
const GENRE_SYNONYM_MAP = {
  'progressive rock': 'Alternative',
  'prog rock': 'Alternative',
  'progressive pop': 'Alternative',
  'art rock': 'Alternative',
  'post-rock': 'Alternative',
  'post rock': 'Alternative',
  'indie rock': 'Alternative',
  'space rock': 'Alternative',
  'math rock': 'Alternative',
  'experimental rock': 'Alternative',
  'avant-garde': 'Alternative'
};

function titleCase(str) {
  return str.split(/\s+/).map(w => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase()).join(' ');
}

export function normalizeGenres(genresArray, max = 5) {
  // Coerce input to an array of strings
  if (!Array.isArray(genresArray)) {
    if (typeof genresArray === 'string') {
      genresArray = splitAndCleanGenres(genresArray);
    } else if (genresArray && typeof genresArray[Symbol.iterator] === 'function') {
      genresArray = Array.from(genresArray);
    } else {
      genresArray = [];
    }
  }
  if (genresArray.length === 0) return [];
  
  // Map to lowercase for comparison
  const mapped = genresArray.map(g => {
    const lower = g.toLowerCase();
    return GENRE_SYNONYM_MAP[lower] || lower;
  });
  
  // Deduplicate preserving order
  const deduped = [];
  for (const g of mapped) {
    const titled = titleCase(g);
    if (!deduped.includes(titled)) {
      deduped.push(titled);
    }
  }
  
  // Prioritize Alternative if present, then Hard Rock, then others
  const priorityOrder = ['Alternative', 'Hard Rock', 'Industrial Rock'];
  deduped.sort((a, b) => {
    const ia = priorityOrder.indexOf(a);
    const ib = priorityOrder.indexOf(b);
    if (ia !== -1 && ib === -1) return -1;
    if (ib !== -1 && ia === -1) return 1;
    if (ia !== -1 && ib !== -1) return ia - ib;
    return 0;
  });
  
  return deduped.slice(0, max);
}

// Generate punctuation variants of a title
function generateTitleVariants(title) {
  const variants = [title];
  
  // Try hyphenated version if there's no hyphen
  if (!title.includes('-')) {
    const words = title.split(' ');
    
    // Try adding hyphen between words (e.g., "Eurotrash Girl" -> "Eurotrash-Girl")
    if (words.length >= 2) {
      for (let i = 0; i < words.length - 1; i++) {
        const variant = [...words];
        variant[i] = variant[i] + '-' + variant[i + 1];
        variant.splice(i + 1, 1);
        variants.push(variant.join(' '));
      }
    }
    
    // Try splitting compound words with hyphens (e.g., "Eurotrash" -> "Euro-Trash")
    // PRESERVE CAPITALIZATION when splitting compound words
    for (let i = 0; i < words.length; i++) {
      const word = words[i];
      if (word.length > 6) { // Only try on longer words
        // Common prefixes that might need hyphenation
        const prefixes = ['Euro', 'Mega', 'Super', 'Ultra', 'Anti', 'Non', 'Semi', 'Multi', 'Pseudo'];
        for (const prefix of prefixes) {
          if (word.startsWith(prefix) && word.length > prefix.length) {
            const hyphenated = [...words];
            const rest = word.slice(prefix.length);
            // Capitalize first letter of the remainder (Euro-trash -> Euro-Trash)
            const restCapitalized = rest.charAt(0).toUpperCase() + rest.slice(1);
            hyphenated[i] = prefix + '-' + restCapitalized;
            variants.push(hyphenated.join(' '));
          }
        }
      }
    }
  }
  
  // Try removing hyphen if there is one
  if (title.includes('-')) {
    variants.push(title.replace(/-/g, ' '));
    variants.push(title.replace(/-/g, ''));
  }
  
  return variants;
}

// Resolve song page with disambiguation and variant handling
async function resolveSongPage(title, artistName) {
  wikiDebug(`[WIKI] resolveSongPage: "${title}" by "${artistName}"`);
  
  // Generate title variants (punctuation)
  const titleVariants = generateTitleVariants(title);
  
  // Try each title variant with different suffixes
  for (const titleVariant of titleVariants) {
    const attempts = [
      `${titleVariant} (song)`,
      `${titleVariant} (single)`,
      `${titleVariant} (${artistName} song)`,
      `${titleVariant} (${artistName} single)`,
      titleVariant // Exact title last (less likely to be correct)
    ];
    
    for (const attempt of attempts) {
  wikiDebug(`[WIKI] resolveSongPage trying title variant: "${attempt}"`);
      const summary = await getWikiSummary(attempt);
      
      if (summary) {
        const { isDisambiguation, isGeneric } = isDisambiguationOrGeneric(summary);
        
        // Skip if it's an album page (we're looking for songs)
        const isAlbumPage = /\balbum\b/i.test(summary.description || '');
        
        // If it's not disambiguation, generic, or album page, we found the song
        if (!isDisambiguation && !isGeneric && !isAlbumPage) {
          wikiDebug(`[WIKI] resolveSongPage found valid page: "${attempt}"`);
          return { articleTitle: attempt, summary };
        } else if (isAlbumPage) {
          wikiDebug(`[WIKI] resolveSongPage skipping album page: "${attempt}"`);
        }
      }
    }
  }
  
  // If all variants failed, try Wikipedia search
  wikiDebug(`[WIKI] resolveSongPage falling back to search`);
  const searchQueries = [
    `${title} (${artistName} song)`,
    `${title} ${artistName} song`,
    `${title} ${artistName} single`,
    `${title} ${artistName} track`
  ];
  
  for (const query of searchQueries) {
    const results = await searchWikipedia(query);
    
    if (results.length > 0) {
      // Prefer results that:
      // 1. Have "(song)" or "(single)" in title
      // 2. Mention artist in title or snippet
      // 3. Are not disambiguation pages
      // 4. Are NOT album pages (skip if has "(album)" in title)
      
      for (const result of results) {
        const resultTitle = result.title || '';
        const resultSnippet = result.snippet || '';
        
        // Skip if disambiguation
        if (/may refer to/i.test(resultSnippet)) continue;
        
        // Skip if it's an album page (we're looking for songs)
        if (/\(album\)/i.test(resultTitle)) continue;
        
        // Prefer if it has (song) or (single)
        const hasSongTag = /\((song|single)\)/i.test(resultTitle);
        const mentionsArtist = resultTitle.toLowerCase().includes(artistName.toLowerCase()) ||
                               resultSnippet.toLowerCase().includes(artistName.toLowerCase());
        
        if (hasSongTag || mentionsArtist) {
          const summary = await getWikiSummary(resultTitle);
          if (summary) {
            const { isDisambiguation, isGeneric } = isDisambiguationOrGeneric(summary);
            const isAlbumPage = /\balbum\b/i.test(summary.description || '');
            
            if (!isDisambiguation && !isGeneric && !isAlbumPage) {
              wikiDebug(`[WIKI] resolveSongPage found via search: "${resultTitle}"`);
              return { articleTitle: resultTitle, summary };
            }
          }
        }
      }
      
      // If no perfect match, try the first result that's not disambiguation or album
      for (const result of results) {
        const resultTitle = result.title || '';
        const resultSnippet = result.snippet || '';
        
        if (/may refer to/i.test(resultSnippet)) continue;
        // Skip album pages in fallback too
        if (/\(album\)/i.test(resultTitle)) continue;
        
        const summary = await getWikiSummary(resultTitle);
        if (summary) {
          const { isDisambiguation, isGeneric } = isDisambiguationOrGeneric(summary);
          const isAlbumPage = /\balbum\b/i.test(summary.description || '');
          
          if (!isDisambiguation && !isGeneric && !isAlbumPage) {
            wikiDebug(`[WIKI] resolveSongPage found via search (fallback): "${resultTitle}"`);
            return { articleTitle: resultTitle, summary };
          }
        }
      }
    }
  }
  
  wikiDebug(`[WIKI] resolveSongPage failed to resolve page`);
  return null;
}

// Get artist info from Wikipedia
export async function getArtistInfo(artistName) {
  wikiDebug(`[WIKI] getArtistInfo: "${artistName}"`);
  
  // Try exact name first
  let summary = await getWikiSummary(artistName);
  let articleTitle = artistName;
  
  if (summary) {
    const { isDisambiguation, isGeneric } = isDisambiguationOrGeneric(summary);
    
    // If disambiguation or generic, try with "(band)" or other suffixes
    if (isDisambiguation || isGeneric) {
      const attempts = [
        `${artistName} (band)`,
        `${artistName} (American band)`,
        `${artistName} (musical group)`,
        `${artistName} (musician)`,
        `${artistName} (singer)`
      ];
      
      for (const attempt of attempts) {
        const attemptSummary = await getWikiSummary(attempt);
        if (attemptSummary) {
          const check = isDisambiguationOrGeneric(attemptSummary);
          if (!check.isDisambiguation && !check.isGeneric) {
            summary = attemptSummary;
            articleTitle = attempt;
            break;
          }
        }
      }
      
      // If still no good match, try search
      if (isDisambiguation || isGeneric) {
        const results = await searchWikipedia(`${artistName} band`);
        if (results.length > 0) {
          for (const result of results) {
            const resultTitle = result.title || '';
            if (resultTitle.toLowerCase().includes('(band)') || 
                resultTitle.toLowerCase().includes('(musical group)')) {
              const searchSummary = await getWikiSummary(resultTitle);
              if (searchSummary) {
                const check = isDisambiguationOrGeneric(searchSummary);
                if (!check.isDisambiguation && !check.isGeneric) {
                  summary = searchSummary;
                  articleTitle = resultTitle;
                  break;
                }
              }
            }
          }
        }
      }
    }
  }
  
  if (!summary) return null;
  
  // Get infobox for genres
  const infobox = await getWikiInfobox(articleTitle);
  
  // Split and clean genres properly
  const genresArray = splitAndCleanGenres(infobox?.genre || '');
  const genres = genresArray.length > 0 ? genresArray.join(', ') : null;
  
  return {
    title: summary.title,
    summary: summary.extract || null,
    genres,
    genresArray,
    thumbnail: summary.thumbnail?.source || null,
    wikiUrl: summary.content_urls?.desktop?.page || null
  };
}

// Get song info from Wikipedia - main entry point
export async function getSongInfo(titleOrWikiId, artistName = null) {
  try {
    wikiDebug(`[WIKI] getSongInfo: titleOrWikiId="${titleOrWikiId}", artistName="${artistName}"`);
    
    let articleTitle = titleOrWikiId;
    let summary = null;
    
    // If artistName is provided, do full disambiguation resolution
    if (artistName) {
      const resolved = await resolveSongPage(titleOrWikiId, artistName);
      if (resolved) {
        articleTitle = resolved.articleTitle;
        summary = resolved.summary;
      }
    } else {
      // Just try to get the summary directly (assuming it's a valid wiki ID)
      summary = await getWikiSummary(titleOrWikiId);
    }
    
    if (!summary) return null;
    
    // Get infobox data
    const infobox = await getWikiInfobox(articleTitle);
    
    // Split and clean genres properly
    const genresArray = splitAndCleanGenres(infobox?.genre || '');
    const genresOriginal = genresArray.length > 0 ? genresArray.join(', ') : null;
    const genresNormalized = normalizeGenres(genresArray);
    const genreCombined = genresNormalized.length > 0 ? genresNormalized.join(', ') : null;
    
    // Get full page extract for cover detection
    let coverInfo = null;
    let coverOriginalArtist = null;
    let coverYear = null;
    let originalReleaseYear = null;
    let isCover = false;
    
    // Check infobox for cover indicators
    if (infobox?.original_artist || infobox?.original_year) {
      // Only mark as cover if original_artist is DIFFERENT from the requested artist
      const originalArtistLower = (infobox.original_artist || '').toLowerCase();
      const requestedArtistLower = (artistName || '').toLowerCase();
      const infoboxArtistLower = (infobox.artist || '').toLowerCase();
      
      // If infobox.artist matches requested artist, it's the ORIGINAL (not a cover)
      // This handles cases like NIN where original_artist="Trent Reznor" but artist="Nine Inch Nails"
      if (infoboxArtistLower && requestedArtistLower && infoboxArtistLower === requestedArtistLower) {
        wikiDebug(`[WIKI] getSongInfo: infobox artist matches requested artist - NOT a cover (original)`);
        isCover = false;
      }
      // If original_artist matches requested artist, it's also NOT a cover
      else if (originalArtistLower && requestedArtistLower && originalArtistLower === requestedArtistLower) {
        wikiDebug(`[WIKI] getSongInfo: original_artist matches requested artist - NOT a cover`);
        isCover = false;
      }
      // Otherwise, it's a cover
      else {
        isCover = true;
        // If original_artist is a person name but infobox.artist is a band, prefer the band name
        // (e.g., "Trent Reznor" -> "Nine Inch Nails")
        if (infobox.original_artist && infobox.artist) {
          coverOriginalArtist = infobox.artist; // Use the band/artist name from the song's infobox
        } else {
          coverOriginalArtist = infobox.original_artist;
        }
        originalReleaseYear = infobox.original_year;
      }
    }
    
    // Get full extract for additional cover detection
    const fullExtract = await getWikiExtractFull(articleTitle);
    if (fullExtract && artistName) {
      const coverDetection = extractCoverInfo(fullExtract, artistName);
      if (coverDetection.sentences.length > 0) {
        // Only mark as cover if the sentence indicates THIS artist covered someone else's song
        // NOT if someone else covered this artist's song
        const artistLower = artistName.toLowerCase();
        const hasCoveredBy = coverDetection.sentences.some(s => {
          const lower = s.toLowerCase();
          // Check for patterns like "Johnny Cash covered" or "covered by Johnny Cash"
          return (lower.includes(`${artistLower} covered`) || 
                  lower.includes(`covered by ${artistLower}`) ||
                  lower.includes(`${artistLower} cover`));
        });
        
        if (hasCoveredBy) {
          isCover = true;
          coverInfo = coverDetection.sentences.join(' ');
          if (coverDetection.year) {
            coverYear = coverDetection.year;
          }
        }
      }
      
      // Try to determine original artist from extract if not in infobox
      if (!coverOriginalArtist && artistName && infobox?.artist && 
          infobox.artist.toLowerCase() !== artistName.toLowerCase()) {
        coverOriginalArtist = infobox.artist;
      }
    }
    
    // If this resolution landed on an album page (no song page exists), set album to the album page
    // Detect album page by summary description or by absence of song-specific infobox fields
    let albumFallback = null;
    if (summary && /\balbum\b/i.test(summary.description || '') ) {
      // We were given a song title but Wikipedia returned an album page - treat album accordingly
      wikiDebug(`[WIKI] getSongInfo detected article is an album page for requested song: "${articleTitle}"`);
      // Use the article title as album if song-level album field not present
      if (!infobox?.album) {
        albumFallback = articleTitle;
      }
    }
    
    // Extract release date
    let releasedClean = extractReleaseDate(infobox?.released || null, summary.extract || '');
    let coverAlbumOverride = null;

    // If this appears to be a cover (artistName != infobox.artist) and we detected cover info in the page,
    // attempt to extract the cover's album and year from the full page extract (Johnny Cash case)
    if (isCover && fullExtract) {
      // If album is missing or the infobox points to original artist, try to find "album" mention near the artistName
      try {
        // Look for album mentions in context of the covering artist
        const albumPatterns = [
          // Pattern 1: "for his/her/their album ... , TITLE" (handles phrases like "for his final album during his lifetime, Title")
          new RegExp(`${artistName.replace(/[-\\/\\^$*+?.()|[\]{}]/g,'\\$&')}.{0,80}?(?:for (?:his|her|their)[^,]{0,50}album[^,]{0,50})[,\\s]+([A-Z][A-Za-z0-9][^.,()\n]{3,50})(?:[.,(]|$)`,'i'),
          // Pattern 2: "on the album TITLE" or "from the album TITLE"
          new RegExp(`${artistName.replace(/[-\\/\\^$*+?.()|[\]{}]/g,'\\$&')}.{0,80}?(?:on|from) the album\\s+([A-Z][^.,()\n]{5,60})(?:[.,(]|$)`,'i'),
          // Pattern 3: Album title in quotes
          new RegExp(`${artistName.replace(/[-\\/\\^$*+?.()|[\]{}]/g,'\\$&')}.{0,80}?(?:album|record)\\s+["']([^"']{3,60})["']`,'i'),
        ];
        
        for (const pattern of albumPatterns) {
          const match = fullExtract.match(pattern);
          if (match && match[1]) {
            let coverAlbum = match[1].trim();
            // Clean up common trailing artifacts
            coverAlbum = coverAlbum.replace(/\s+(in|during|from|with|Its|The|His|Her)\s*$/i, '');
            coverAlbum = coverAlbum.replace(/[,;:]$/,'');
            
            if (coverAlbum.length > 3) {
              wikiDebug(`[WIKI] getSongInfo detected cover album from extract: "${coverAlbum}"`);
              // Prefer setting album if not present or if infobox points to original
              if (!infobox?.album || (infobox.artist && infobox.artist.toLowerCase() !== artistName.toLowerCase())) {
                coverAlbumOverride = coverAlbum;
              }
              break;
            }
          }
        }
      } catch (e) {
        // ignore regex errors
      }

      // If coverYear not already set from extract detection, try to find a 4-digit year near the artistName
      if (!coverYear) {
        const yearMatch = fullExtract.match(new RegExp(`${artistName.replace(/[-\\/\\^$*+?.()|[\]{}]/g,'\\$&')}.{0,80}?(19|20)\\d{2}`,'i'));
        if (yearMatch && yearMatch[0]) {
          const yearExtract = yearMatch[0].match(/(19|20)\d{2}/);
          if (yearExtract) {
            coverYear = yearExtract[0];
            wikiDebug(`[WIKI] getSongInfo detected cover year from extract: "${coverYear}"`);
          }
        }
      }

      // If we found coverYear, prefer it as the released date for this cover
      if (coverYear) {
        releasedClean = coverYear;
      }
    }
    
    return {
      title: summary.title,
      artist: infobox?.artist || artistName || null,
      album: coverAlbumOverride || infobox?.album || albumFallback || null,
      released: releasedClean,
      genre: genreCombined, // legacy key
      genresOriginal,
      genresNormalized,
      genreCombined,
      length: infobox?.length || null,
      summary: summary.extract || null,
      isCover,
      coverInfo,
      coverYear,
      coverOriginalArtist,
      originalReleaseYear,
      thumbnail: summary.thumbnail?.source || null,
      wikiUrl: summary.content_urls?.desktop?.page || `https://en.wikipedia.org/wiki/${encodeURIComponent(articleTitle)}`
    };
  } catch (err) {
    wikiError(`[WIKI] getSongInfo error:`, err);
    return null;
  }
}

// Get album info from Wikipedia
export async function getAlbumInfo(albumTitle, artistName) {
  wikiDebug(`[WIKI] getAlbumInfo: "${albumTitle}" by "${artistName}"`);
  
  // Try multiple disambiguation patterns to find the album
  const attempts = [];
  
  if (artistName) {
    // Try "<Album> (<Artist> album)" first (most specific)
    attempts.push(`${albumTitle} (${artistName} album)`);
    // Try "<Album> (album by <Artist>)" variant
    attempts.push(`${albumTitle} (album by ${artistName})`);
  }
  
  // Try common year ranges for self-titled albums (limited to avoid too many API calls)
  const currentYear = new Date().getFullYear();
  const yearRanges = [
    currentYear, currentYear - 1, currentYear - 2, // Recent releases
    2020, 2015, 2010, 2005, 2000, // Common decades
    1995, 1990, 1985, 1980, 1975, 1970 // Classic albums
  ];
  for (const year of yearRanges) {
    if (year <= currentYear) {
      attempts.push(`${albumTitle} (${year} album)`);
    }
  }
  
  // Try generic "(album)" suffix
  attempts.push(`${albumTitle} (album)`);
  // Try bare album title last
  attempts.push(albumTitle);
  
  let summary = null;
  let articleTitle = albumTitle;
  
  for (const attempt of attempts) {
    summary = await getWikiSummary(attempt);
    if (summary) {
      const { isDisambiguation, isGeneric } = isDisambiguationOrGeneric(summary);
      // Accept if not disambiguation and not a generic page (like "trash/garbage")
      if (!isDisambiguation && !isGeneric) {
        articleTitle = attempt;
        wikiDebug(`[WIKI] getAlbumInfo found via: "${attempt}"`);
        break;
      }
      // If we get a disambiguation page, keep looking
      summary = null;
    }
  }
  
  if (!summary) return null;
  
  // Get infobox
  const infobox = await getWikiInfobox(articleTitle);
  
  // Split and clean genres properly
  const genresOriginalArray = splitAndCleanGenres(infobox?.genre || '');
  
  // Select featured genres (prioritize progressive rock, pop, avant-pop)
  function selectFeaturedGenres(list) {
    if (!list.length) return [];
    const lower = list.map(g => g.toLowerCase());
    const picked = [];
    
    // 1) Progressive rock first (else progressive pop)
    const progIdx = lower.findIndex(g => g.includes('progressive rock'));
    if (progIdx !== -1) {
      picked.push(list[progIdx]);
    } else {
      const progPopIdx = lower.findIndex(g => g.includes('progressive pop'));
      if (progPopIdx !== -1) picked.push(list[progPopIdx]);
    }
    
    // 2) Pop (mainstream)
    const popIdx = lower.findIndex(g => g === 'pop' || g.endsWith(' pop') || g.startsWith('pop '));
    if (popIdx !== -1 && !picked.includes(list[popIdx])) {
      picked.push(list[popIdx]);
    }
    
    // 3) Avant-pop (art aspect)
    const avantIdx = lower.findIndex(g => g.includes('avant') && g.includes('pop'));
    if (avantIdx !== -1 && !picked.includes(list[avantIdx])) {
      picked.push(list[avantIdx]);
    }
    
    // Fill to 3 with distinct leftovers
    for (const g of list) {
      if (picked.length >= 3) break;
      if (!picked.includes(g)) picked.push(g);
    }
    
    return picked.slice(0, 3);
  }
  
  const genresSelected = selectFeaturedGenres(genresOriginalArray);
  
  return {
    title: albumTitle,
    artist: infobox?.artist || artistName || null,
    released: infobox?.released || null,
    genre: infobox?.genre || null,
    genresOriginalArray,
    genresSelected,
    length: infobox?.length || null,
    summary: summary.extract || null,
    thumbnail: summary.thumbnail?.source || null,
    wikiUrl: summary.content_urls?.desktop?.page || null
  };
}

// Legacy export for backward compatibility
export { normalizeGenres as normalizeInfoboxGenres };

