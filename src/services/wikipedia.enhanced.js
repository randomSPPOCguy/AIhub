// src/services/wikipedia.enhanced.js
// Enhanced Wikipedia API helpers with proper disambiguation, search fallback, and cover detection

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
  
  await sleep(250); // Rate limit: 250ms between calls
  const encoded = encodeURIComponent(articleTitle);
  const url = `https://en.wikipedia.org/api/rest_v1/page/summary/${encoded}`;
  
  try {
    const response = await fetch(url);
    if (!response.ok) return null;
    const data = await response.json();
    summaryCache.set(cacheKey, data);
    return data;
  } catch (err) {
    console.error(`[WIKI] getWikiSummary error for "${articleTitle}":`, err.message);
    return null;
  }
}

// Full page plain-text extract (not limited to intro) - needed for cover detection
export async function getWikiExtractFull(articleTitle) {
  await sleep(250);
  const encoded = encodeURIComponent(articleTitle);
  const url = `https://en.wikipedia.org/w/api.php?action=query&prop=extracts&titles=${encoded}&format=json&explaintext=1`;
  
  try {
    const response = await fetch(url);
    if (!response.ok) return null;
    const data = await response.json();
    const pages = data?.query?.pages;
    if (!pages) return null;
    const pageId = Object.keys(pages)[0];
    return pages[pageId]?.extract || null;
  } catch (err) {
    console.error(`[WIKI] getWikiExtractFull error:`, err.message);
    return null;
  }
}

// Wikipedia search API - returns array of search results with title, description
export async function searchWikipedia(query) {
  const cacheKey = query.toLowerCase();
  if (searchCache.has(cacheKey)) {
    return searchCache.get(cacheKey);
  }
  
  await sleep(250);
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
    console.error(`[WIKI] searchWikipedia error:`, err.message);
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
  
  await sleep(250); // Rate limit: 250ms between calls
  const encoded = encodeURIComponent(articleTitle);
  const url = `https://en.wikipedia.org/w/api.php?action=query&prop=revisions&titles=${encoded}&rvprop=content&format=json&rvslots=main`;
  
  console.log(`[WIKI] getWikiInfobox fetching: "${articleTitle}"`);
  
  try {
    const response = await fetch(url);
    if (!response.ok) {
      console.log(`[WIKI] getWikiInfobox fetch failed:`, response.status);
      return null;
    }
    
    const data = await response.json();
    const pages = data?.query?.pages;
    if (!pages) {
      console.log(`[WIKI] getWikiInfobox no pages in response`);
      return null;
    }
    
    const pageId = Object.keys(pages)[0];
    const content = pages[pageId]?.revisions?.[0]?.slots?.main?.['*'];
    if (!content) {
      console.log(`[WIKI] getWikiInfobox no content for pageId:`, pageId);
      return null;
    }
    
    // Find the infobox - handle nested braces properly
    const infoboxStart = content.indexOf('{{Infobox');
    if (infoboxStart === -1) {
      console.log(`[WIKI] getWikiInfobox no {{Infobox found in content`);
      return null;
    }
    
    console.log(`[WIKI] getWikiInfobox found infobox at position:`, infoboxStart);
    
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
      console.log(`[WIKI] getWikiInfobox couldn't find closing braces`);
      return null;
    }
    
    console.log(`[WIKI] getWikiInfobox extracted infobox, length:`, infoboxEnd - infoboxStart);
    
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
    
    console.log(`[WIKI] getWikiInfobox extracted fields:`, Object.keys(fields).length, 'fields ->', fields);
    
    infoboxCache.set(cacheKey, fields);
    return fields;
  } catch (err) {
    console.error(`[WIKI] getWikiInfobox error:`, err.message);
    return null;
  }
}

// Split and clean genre field properly - split on pipes, commas, newlines FIRST, then clean each
function splitAndCleanGenres(rawGenre) {
  if (!rawGenre) return [];
  
  console.log(`[WIKI] splitAndCleanGenres - raw input:`, rawGenre);
  
  // First, split on newlines to preserve individual genre entries
  const lines = rawGenre.split(/\n+/).map(l => l.trim()).filter(Boolean);
  
  console.log(`[WIKI] splitAndCleanGenres - after newline split:`, lines);
  
  const allGenres = [];
  
  for (const line of lines) {
    // Clean the line to remove wiki markup
    let cleaned = cleanWikitext(line);
    if (!cleaned) continue;
    
    // Now split on pipes, commas, semicolons
    const parts = cleaned.split(/[|,;]+/).map(p => p.trim()).filter(Boolean);
    
    for (const part of parts) {
      // Remove trailing words like "music" or "genre"
      const final = part.replace(/\b(music|genre)\b/i, '').trim();
      if (final && final.length > 0) {
        allGenres.push(final);
      }
    }
  }
  
  console.log(`[WIKI] splitAndCleanGenres - final array:`, allGenres);
  
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
  if (!genresArray || genresArray.length === 0) return [];
  
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
    // Try adding hyphen between words (e.g., "Eurotrash Girl" -> "Euro-trash Girl")
    const words = title.split(' ');
    if (words.length >= 2) {
      for (let i = 0; i < words.length - 1; i++) {
        const variant = [...words];
        variant[i] = variant[i] + '-' + variant[i + 1];
        variant.splice(i + 1, 1);
        variants.push(variant.join(' '));
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
  console.log(`[WIKI] resolveSongPage: "${title}" by "${artistName}"`);
  
  // Generate title variants (punctuation)
  const titleVariants = generateTitleVariants(title);
  
  // Try each title variant with different suffixes
  for (const titleVariant of titleVariants) {
    const attempts = [
      titleVariant, // Exact title
      `${titleVariant} (${artistName} song)`,
      `${titleVariant} (${artistName} single)`,
      `${titleVariant} (song)`,
      `${titleVariant} (single)`
    ];
    
    for (const attempt of attempts) {
      console.log(`[WIKI] resolveSongPage trying: "${attempt}"`);
      const summary = await getWikiSummary(attempt);
      
      if (summary) {
        const { isDisambiguation, isGeneric } = isDisambiguationOrGeneric(summary);
        
        // If it's not disambiguation or generic, we found it
        if (!isDisambiguation && !isGeneric) {
          console.log(`[WIKI] resolveSongPage found valid page: "${attempt}"`);
          return { articleTitle: attempt, summary };
        }
      }
    }
  }
  
  // If all variants failed, try Wikipedia search
  console.log(`[WIKI] resolveSongPage falling back to search`);
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
      
      for (const result of results) {
        const resultTitle = result.title || '';
        const resultSnippet = result.snippet || '';
        
        // Skip if disambiguation
        if (/may refer to/i.test(resultSnippet)) continue;
        
        // Prefer if it has (song) or (single)
        const hasSongTag = /\((song|single)\)/i.test(resultTitle);
        const mentionsArtist = resultTitle.toLowerCase().includes(artistName.toLowerCase()) ||
                               resultSnippet.toLowerCase().includes(artistName.toLowerCase());
        
        if (hasSongTag || mentionsArtist) {
          const summary = await getWikiSummary(resultTitle);
          if (summary) {
            const { isDisambiguation, isGeneric } = isDisambiguationOrGeneric(summary);
            if (!isDisambiguation && !isGeneric) {
              console.log(`[WIKI] resolveSongPage found via search: "${resultTitle}"`);
              return { articleTitle: resultTitle, summary };
            }
          }
        }
      }
      
      // If no perfect match, try the first result that's not disambiguation
      for (const result of results) {
        const resultTitle = result.title || '';
        const resultSnippet = result.snippet || '';
        
        if (/may refer to/i.test(resultSnippet)) continue;
        
        const summary = await getWikiSummary(resultTitle);
        if (summary) {
          const { isDisambiguation, isGeneric } = isDisambiguationOrGeneric(summary);
          if (!isDisambiguation && !isGeneric) {
            console.log(`[WIKI] resolveSongPage found via search (fallback): "${resultTitle}"`);
            return { articleTitle: resultTitle, summary };
          }
        }
      }
    }
  }
  
  console.log(`[WIKI] resolveSongPage failed to resolve page`);
  return null;
}

// Get artist info from Wikipedia
export async function getArtistInfo(artistName) {
  console.log(`[WIKI] getArtistInfo: "${artistName}"`);
  
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
    console.log(`[WIKI] getSongInfo: titleOrWikiId="${titleOrWikiId}", artistName="${artistName}"`);
    
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
      isCover = true;
      coverOriginalArtist = infobox.original_artist;
      originalReleaseYear = infobox.original_year;
    }
    
    // Get full extract for additional cover detection
    const fullExtract = await getWikiExtractFull(articleTitle);
    if (fullExtract && artistName) {
      const coverDetection = extractCoverInfo(fullExtract, artistName);
      if (coverDetection.sentences.length > 0) {
        isCover = true;
        coverInfo = coverDetection.sentences.join(' ');
        if (coverDetection.year) {
          coverYear = coverDetection.year;
        }
      }
      
      // Try to determine original artist from extract if not in infobox
      if (!coverOriginalArtist && artistName && infobox?.artist && 
          infobox.artist.toLowerCase() !== artistName.toLowerCase()) {
        coverOriginalArtist = infobox.artist;
      }
    }
    
    // Extract release date
    const releasedClean = extractReleaseDate(infobox?.released || null, summary.extract || '');
    
    return {
      title: summary.title,
      artist: infobox?.artist || artistName || null,
      album: infobox?.album || null,
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
    console.error(`[WIKI] getSongInfo error:`, err);
    return null;
  }
}

// Get album info from Wikipedia
export async function getAlbumInfo(albumTitle, artistName) {
  console.log(`[WIKI] getAlbumInfo: "${albumTitle}" by "${artistName}"`);
  
  // Try "<Album> (<Artist> album)" format first
  let articleTitle = artistName ? `${albumTitle} (${artistName} album)` : albumTitle;
  let summary = await getWikiSummary(articleTitle);
  
  // If that failed, try just the album title
  if (!summary && artistName) {
    articleTitle = albumTitle;
    summary = await getWikiSummary(articleTitle);
  }
  
  // If summary looks like disambiguation, try "(album)" suffix
  if (summary) {
    const { isDisambiguation } = isDisambiguationOrGeneric(summary);
    if (isDisambiguation) {
      const albumAlt = await getWikiSummary(`${albumTitle} (album)`);
      if (albumAlt) {
        const check = isDisambiguationOrGeneric(albumAlt);
        if (!check.isDisambiguation) {
          summary = albumAlt;
          articleTitle = `${albumTitle} (album)`;
        }
      }
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
