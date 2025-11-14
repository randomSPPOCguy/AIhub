"""
Wikipedia API Service
Enhanced Wikipedia integration with disambiguation, infobox parsing, and metadata extraction
Ported from Node.js version
"""

import asyncio
import re
import os
from functools import lru_cache
from typing import Optional, Dict, List, Any
import httpx

# User-Agent for Wikipedia API (required!)
WIKI_UA_APP = os.getenv("WIKI_UA_APP", "AIHub")
WIKI_UA_VERSION = os.getenv("WIKI_UA_VERSION", "2.0")
WIKI_UA_CONTACT = os.getenv("WIKI_UA_CONTACT", "user@example.com")
WIKI_UA = f"{WIKI_UA_APP}/{WIKI_UA_VERSION} ({WIKI_UA_CONTACT})"

# In-memory cache for summary/infobox/search results
_summary_cache: Dict[str, Any] = {}
_infobox_cache: Dict[str, Any] = {}
_search_cache: Dict[str, List] = {}


def wiki_headers() -> Dict[str, str]:
    """Get Wikipedia API headers with proper user-agent"""
    return {
        "User-Agent": WIKI_UA,
        "Accept": "application/json"
    }


async def _sleep(ms: int):
    """Sleep helper for rate limiting"""
    await asyncio.sleep(ms / 1000)


async def get_wiki_summary(article_title: str) -> Optional[Dict[str, Any]]:
    """
    Get basic Wikipedia summary (includes extract, thumbnail, description)
    
    Args:
        article_title: Wikipedia article title
        
    Returns:
        Dictionary with title, extract, thumbnail, description, etc.
    """
    cache_key = article_title.lower()
    if cache_key in _summary_cache:
        return _summary_cache[cache_key]
    
    await _sleep(100)  # Rate limit: 100ms between calls
    
    from urllib.parse import quote
    encoded = quote(article_title)
    url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{encoded}"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=wiki_headers(), timeout=10.0)
            print(f"[WIKI] get_wiki_summary response status: {response.status_code} for URL: {url}")
            if response.status_code != 200:
                print(f"[WIKI] get_wiki_summary non-200 response: {response.text[:200]}")
                return None
            data = response.json()
            _summary_cache[cache_key] = data
            return data
    except Exception as e:
        print(f"[WIKI] get_wiki_summary error for '{article_title}': {e}")
        import traceback
        traceback.print_exc()
        return None


async def get_wiki_extract_full(article_title: str) -> Optional[str]:
    """
    Get full page plain-text extract (not limited to intro)
    
    Args:
        article_title: Wikipedia article title
        
    Returns:
        Full article text
    """
    await _sleep(100)
    
    from urllib.parse import quote
    encoded = quote(article_title)
    url = f"https://en.wikipedia.org/w/api.php?action=query&prop=extracts&titles={encoded}&format=json&explaintext=1&redirects=true"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=wiki_headers(), timeout=10.0)
            if response.status_code != 200:
                return None
            data = response.json()
            pages = data.get('query', {}).get('pages', {})
            if not pages:
                return None
            page_id = list(pages.keys())[0]
            return pages[page_id].get('extract')
    except Exception as e:
        print(f"[WIKI] get_wiki_extract_full error: {e}")
        return None


async def search_wikipedia(query: str) -> List[Dict[str, Any]]:
    """
    Wikipedia search API
    
    Args:
        query: Search query
        
    Returns:
        List of search results with title, description
    """
    cache_key = query.lower()
    if cache_key in _search_cache:
        return _search_cache[cache_key]
    
    await _sleep(100)
    
    from urllib.parse import quote
    encoded = quote(query)
    url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={encoded}&format=json&srlimit=10"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=wiki_headers(), timeout=10.0)
            if response.status_code != 200:
                return []
            data = response.json()
            results = data.get('query', {}).get('search', [])
            _search_cache[cache_key] = results
            return results
    except Exception as e:
        print(f"[WIKI] search_wikipedia error: {e}")
        return []


def is_disambiguation_or_generic(summary: Optional[Dict]) -> Dict[str, bool]:
    """
    Check if a page is a disambiguation page or generic concept
    
    Args:
        summary: Wikipedia summary data
        
    Returns:
        Dict with isDisambiguation and isGeneric booleans
    """
    if not summary:
        return {'isDisambiguation': False, 'isGeneric': False}
    
    extract = (summary.get('extract', '') or '').lower()
    description = (summary.get('description', '') or '').lower()
    
    # Check for disambiguation indicators
    is_disambiguation = bool(re.search(r'may refer to:|refers to:', extract, re.IGNORECASE))
    
    # Check if it's a generic concept page (lacks music-related words)
    music_words = ['band', 'musical group', 'singer', 'musician', 'rapper', 
                   'artist', 'duo', 'trio', 'song', 'single', 'album', 'track']
    has_music = any(word in extract or word in description for word in music_words)
    is_generic = not has_music
    
    return {'isDisambiguation': is_disambiguation, 'isGeneric': is_generic}


def clean_wikitext(text: Optional[str]) -> Optional[str]:
    """
    Clean wikitext markup to plain text
    
    Args:
        text: Raw wikitext
        
    Returns:
        Cleaned plain text
    """
    if not text:
        return None
    
    # Remove comments
    text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)
    
    # Preserve nowrap inner content
    text = re.sub(r'\{\{nowrap\|([^{}]+)\}\}', r'\1', text, flags=re.IGNORECASE)
    
    # Remove templates like {{Start date|1991|09|10}} -> extract date parts
    text = re.sub(r'\{\{Start date\|(\d+)\|(\d+)\|(\d+)\}\}', r'\1-\2-\3', text, flags=re.IGNORECASE)
    
    # Remove {{Duration|m=5|s=01}} -> convert to readable format
    text = re.sub(r'\{\{Duration\|m=(\d+)\|s=(\d+)\}\}', r'\1:\2', text, flags=re.IGNORECASE)
    
    # Handle {{flatlist}} and similar - remove wrapper but keep content
    text = re.sub(r'\{\{flatlist\s*\|\s*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\{\{hlist\s*\|\s*', '', text, flags=re.IGNORECASE)
    
    # Remove all other nested templates {{...}}
    text = re.sub(r'\{\{[^{}]*(?:\{\{[^{}]*\}\}[^{}]*)*\}\}', '', text)
    
    # Remove wiki links [[Link|Text]] -> Text or [[Link]] -> Link
    text = re.sub(r'\[\[(?:[^|\]]+\|)?([^\]]+)\]\]', r'\1', text)
    
    # Remove simple brackets
    text = re.sub(r'\[\[|\]\]', '', text)
    
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    
    # Remove extra asterisks and list markers
    text = re.sub(r'^\s*[\*#]+\s*', '', text, flags=re.MULTILINE)
    
    # Remove ref tags
    text = re.sub(r'<ref[^>]*>.*?</ref>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'<ref[^>]*\/>', '', text, flags=re.IGNORECASE)
    
    # Remove extra quotes
    text = re.sub(r'[\'"""]+', '', text)
    
    # Clean up multiple spaces
    text = re.sub(r'\s+', ' ', text)
    
    # Trim whitespace
    text = text.strip()
    
    return text if text else None


async def get_wiki_infobox(article_title: str) -> Optional[Dict[str, str]]:
    """
    Get infobox data from Wikipedia page (for structured data like genres, years, duration)
    
    Args:
        article_title: Wikipedia article title
        
    Returns:
        Dictionary with parsed infobox fields
    """
    cache_key = article_title.lower()
    if cache_key in _infobox_cache:
        return _infobox_cache[cache_key]
    
    await _sleep(100)
    
    from urllib.parse import quote
    encoded = quote(article_title)
    url = f"https://en.wikipedia.org/w/api.php?action=query&prop=revisions&titles={encoded}&rvprop=content&format=json&rvslots=main&redirects=true"
    
    print(f"[WIKI] get_wiki_infobox fetching: '{article_title}'")
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=wiki_headers(), timeout=15.0)
            if response.status_code != 200:
                print(f"[WIKI] get_wiki_infobox fetch failed: {response.status_code}")
                return None
            
            data = response.json()
            
            # Log redirects
            if 'query' in data and 'redirects' in data['query']:
                redirect = data['query']['redirects'][0]
                print(f"[WIKI] Followed redirect: '{redirect['from']}' -> '{redirect['to']}'")
            
            pages = data.get('query', {}).get('pages', {})
            if not pages:
                print("[WIKI] get_wiki_infobox no pages in response")
                return None
            
            page_id = list(pages.keys())[0]
            content = pages[page_id].get('revisions', [{}])[0].get('slots', {}).get('main', {}).get('*')
            if not content:
                print(f"[WIKI] get_wiki_infobox no content for pageId: {page_id}")
                return None
            
            # Find the infobox - handle nested braces properly
            infobox_match = re.search(r'\{\{Infobox', content, re.IGNORECASE)
            if not infobox_match:
                print("[WIKI] get_wiki_infobox no {{Infobox found in content")
                return None
            
            infobox_start = infobox_match.start()
            print(f"[WIKI] get_wiki_infobox found infobox at position: {infobox_start}")
            
            # Find matching closing braces
            brace_count = 0
            infobox_end = -1
            i = infobox_start
            while i < len(content) - 1:
                if content[i:i+2] == '{{':
                    brace_count += 1
                    i += 2
                elif content[i:i+2] == '}}':
                    brace_count -= 1
                    i += 2
                    if brace_count == 0:
                        infobox_end = i
                        break
                else:
                    i += 1
            
            if infobox_end == -1:
                print("[WIKI] get_wiki_infobox couldn't find closing braces")
                return None
            
            print(f"[WIKI] get_wiki_infobox extracted infobox, length: {infobox_end - infobox_start}")
            
            infobox_content = content[infobox_start:infobox_end]
            fields = {}
            
            # Parse field by field
            lines = infobox_content.split('\n')
            current_field = None
            current_value = []
            
            for line in lines:
                # Check if this is a new field definition
                field_match = re.match(r'^\s*\|\s*([^=]+?)\s*=\s*(.*)$', line)
                
                if field_match:
                    # Save previous field if exists
                    if current_field:
                        key = current_field.lower().strip()
                        value = '\n'.join(current_value).strip()
                        
                        if key in ['album', 'from album', 'from', 'from_album', 'from-album']:
                            fields['album'] = value
                        if key in ['released', 'published', 'recorded']:
                            fields['released'] = value
                        if key in ['genre', 'genres']:
                            fields['genre'] = value
                        if key in ['length', 'duration']:
                            fields['length'] = value
                        if key in ['artist', 'name']:
                            fields['artist'] = value
                        if key in ['original_artist', 'original artist', 'writer', 'cover_of']:
                            fields['original_artist'] = value
                        if key in ['original_year', 'original year']:
                            fields['original_year'] = value
                    
                    current_field = field_match.group(1).strip()
                    # Remove leading bullets/asterisks from value
                    current_value = [re.sub(r'^\s*[\*\-\•]\s*', '', field_match.group(2))]
                elif current_field and line.strip() and not line.strip().startswith('{{Infobox'):
                    if not line.strip().startswith('|'):
                        # Remove bullets from continuation lines too
                        current_value.append(re.sub(r'^\s*[\*\-\•]\s*', '', line))
            
            # Don't forget the last field
            if current_field:
                key = current_field.lower().strip()
                value = '\n'.join(current_value).strip()
                
                if key in ['album', 'from album', 'from', 'from_album', 'from-album']:
                    fields['album'] = value
                if key in ['released', 'published', 'recorded']:
                    fields['released'] = value
                if key in ['genre', 'genres']:
                    fields['genre'] = value
                if key in ['length', 'duration']:
                    fields['length'] = value
                if key in ['artist', 'name']:
                    fields['artist'] = value
                if key in ['original_artist', 'original artist', 'writer', 'cover_of']:
                    fields['original_artist'] = value
                if key in ['original_year', 'original year']:
                    fields['original_year'] = value
            
            # Clean all extracted fields EXCEPT genre (we need to split it first)
            for key in list(fields.keys()):
                if key != 'genre':
                    fields[key] = clean_wikitext(fields[key])
            
            print(f"[WIKI] get_wiki_infobox extracted fields: {len(fields)} fields -> {fields}")
            
            _infobox_cache[cache_key] = fields
            return fields
    except Exception as e:
        print(f"[WIKI] get_wiki_infobox error: {e}")
        return None


def split_and_clean_genres(raw_genre: Optional[str]) -> List[str]:
    """
    Split and clean genre field properly
    
    Args:
        raw_genre: Raw genre string from infobox
        
    Returns:
        List of cleaned genre names
    """
    if not raw_genre:
        return []
    
    print(f"[WIKI] split_and_clean_genres - raw input: {raw_genre}")
    
    # First, split on newlines to preserve individual genre entries
    lines = [l.strip() for l in raw_genre.split('\n') if l.strip()]
    
    print(f"[WIKI] split_and_clean_genres - after newline split: {lines}")
    
    all_genres = []
    
    for line in lines:
        # Remove citation content BEFORE cleaning wikitext
        processed = re.sub(r'<ref[^>]*>.*?</ref>', '', line, flags=re.IGNORECASE)
        processed = re.sub(r'<ref[^>]*\/>', '', processed, flags=re.IGNORECASE)
        
        # Clean the line to remove wiki markup
        cleaned = clean_wikitext(processed)
        if not cleaned:
            continue
        
        # Now split on pipes, commas, semicolons
        parts = [p.strip() for p in re.split(r'[|,;]+', cleaned) if p.strip()]
        
        for part in parts:
            # Remove trailing words like "music" or "genre"
            final = re.sub(r'\b(music|genre)\b', '', part, flags=re.IGNORECASE).strip()
            # Remove any remaining template artifacts
            final = re.sub(r'^\{\{|\}\}$', '', final).strip()
            if final and final not in ['}}', '{{']:
                all_genres.append(final)
    
    print(f"[WIKI] split_and_clean_genres - final array: {all_genres}")
    
    return all_genres


def normalize_genres(genres_array: Any, max_genres: int = 5) -> List[str]:
    """
    Normalize genres into canonical set (limit to max 3-5)
    
    Args:
        genres_array: List of genre strings or single string
        max_genres: Maximum number of genres to return
        
    Returns:
        List of normalized genre names
    """
    # Genre synonym mapping
    GENRE_SYNONYM_MAP = {
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
    }
    
    # Coerce input to an array of strings
    if not isinstance(genres_array, list):
        if isinstance(genres_array, str):
            genres_array = split_and_clean_genres(genres_array)
        else:
            genres_array = []
    
    if not genres_array:
        return []
    
    # Map to lowercase for comparison
    mapped = [GENRE_SYNONYM_MAP.get(g.lower(), g.lower()) for g in genres_array]
    
    # Deduplicate preserving order (title case)
    deduped = []
    for g in mapped:
        titled = g.title().replace(' ', ' ')  # Ensure proper title case
        if titled not in deduped:
            deduped.append(titled)
    
    # Prioritize Alternative if present, then Hard Rock, then others
    priority_order = ['Alternative', 'Hard Rock', 'Industrial Rock']
    
    def sort_key(genre):
        try:
            return priority_order.index(genre)
        except ValueError:
            return len(priority_order)
    
    deduped.sort(key=sort_key)
    
    return deduped[:max_genres]


def generate_title_variants(title: str) -> List[str]:
    """
    Generate punctuation variants of a title
    
    Args:
        title: Original title
        
    Returns:
        List of title variants
    """
    variants = [title]
    
    # Try hyphenated version if there's no hyphen
    if '-' not in title:
        words = title.split(' ')
        
        # Try adding hyphen between words
        if len(words) >= 2:
            for i in range(len(words) - 1):
                variant = words.copy()
                variant[i] = variant[i] + '-' + variant[i + 1]
                del variant[i + 1]
                variants.append(' '.join(variant))
        
        # Try splitting compound words with hyphens
        for i, word in enumerate(words):
            if len(word) > 6:
                prefixes = ['Euro', 'Mega', 'Super', 'Ultra', 'Anti', 'Non', 'Semi', 'Multi', 'Pseudo']
                for prefix in prefixes:
                    if word.startswith(prefix) and len(word) > len(prefix):
                        hyphenated = words.copy()
                        rest = word[len(prefix):]
                        rest_capitalized = rest[0].upper() + rest[1:] if rest else ''
                        hyphenated[i] = prefix + '-' + rest_capitalized
                        variants.append(' '.join(hyphenated))
    
    # Try removing hyphen if there is one
    if '-' in title:
        variants.append(title.replace('-', ' '))
        variants.append(title.replace('-', ''))
    
    return variants


async def resolve_song_page(title: str, artist_name: str) -> Optional[Dict[str, Any]]:
    """
    Resolve song page with disambiguation and variant handling
    
    Args:
        title: Song title
        artist_name: Artist name
        
    Returns:
        Dict with articleTitle and summary, or None
    """
    print(f"[WIKI] resolve_song_page: '{title}' by '{artist_name}'")
    
    # Generate title variants
    title_variants = generate_title_variants(title)
    
    # Try each title variant with different suffixes
    for title_variant in title_variants:
        attempts = [
            f"{title_variant} (song)",
            f"{title_variant} (single)",
            f"{title_variant} ({artist_name} song)",
            f"{title_variant} ({artist_name} single)",
            title_variant  # Exact title last
        ]
        
        for attempt in attempts:
            print(f"[WIKI] resolve_song_page trying title variant: '{attempt}'")
            summary = await get_wiki_summary(attempt)
            
            if summary:
                check = is_disambiguation_or_generic(summary)
                is_album_page = bool(re.search(r'\balbum\b', summary.get('description', ''), re.IGNORECASE))
                
                if not check['isDisambiguation'] and not check['isGeneric'] and not is_album_page:
                    print(f"[WIKI] resolve_song_page found valid page: '{attempt}'")
                    return {'articleTitle': attempt, 'summary': summary}
                elif is_album_page:
                    print(f"[WIKI] resolve_song_page skipping album page: '{attempt}'")
    
    # If all variants failed, try Wikipedia search
    print("[WIKI] resolve_song_page falling back to search")
    search_queries = [
        f"{title} ({artist_name} song)",
        f"{title} {artist_name} song",
        f"{title} {artist_name} single",
        f"{title} {artist_name} track"
    ]
    
    for query in search_queries:
        results = await search_wikipedia(query)
        
        if results:
            for result in results:
                result_title = result.get('title', '')
                result_snippet = result.get('snippet', '')
                
                # Skip disambiguation pages
                if re.search(r'may refer to', result_snippet, re.IGNORECASE):
                    continue
                
                # Skip album pages
                if re.search(r'\(album\)', result_title, re.IGNORECASE):
                    continue
                
                # Prefer if it has (song) or (single)
                has_song_tag = bool(re.search(r'\((song|single)\)', result_title, re.IGNORECASE))
                mentions_artist = (artist_name.lower() in result_title.lower() or 
                                 artist_name.lower() in result_snippet.lower())
                
                if has_song_tag or mentions_artist:
                    summary = await get_wiki_summary(result_title)
                    if summary:
                        check = is_disambiguation_or_generic(summary)
                        is_album_page = bool(re.search(r'\balbum\b', summary.get('description', ''), re.IGNORECASE))
                        
                        if not check['isDisambiguation'] and not check['isGeneric'] and not is_album_page:
                            print(f"[WIKI] resolve_song_page found via search: '{result_title}'")
                            return {'articleTitle': result_title, 'summary': summary}
    
    print("[WIKI] resolve_song_page failed to resolve page")
    return None


async def get_artist_info(artist_name: str) -> Optional[Dict[str, Any]]:
    """
    Get artist info from Wikipedia
    
    Args:
        artist_name: Artist name
        
    Returns:
        Dictionary with artist info including genres
    """
    print(f"[WIKI] get_artist_info: '{artist_name}'")
    
    # Try exact name first
    summary = await get_wiki_summary(artist_name)
    article_title = artist_name
    
    if summary:
        check = is_disambiguation_or_generic(summary)
        
        # If disambiguation or generic, try with suffixes
        if check['isDisambiguation'] or check['isGeneric']:
            attempts = [
                f"{artist_name} (band)",
                f"{artist_name} (American band)",
                f"{artist_name} (musical group)",
                f"{artist_name} (musician)",
                f"{artist_name} (singer)"
            ]
            
            for attempt in attempts:
                attempt_summary = await get_wiki_summary(attempt)
                if attempt_summary:
                    attempt_check = is_disambiguation_or_generic(attempt_summary)
                    if not attempt_check['isDisambiguation'] and not attempt_check['isGeneric']:
                        summary = attempt_summary
                        article_title = attempt
                        break
            
            # If still no good match, try search
            if check['isDisambiguation'] or check['isGeneric']:
                results = await search_wikipedia(f"{artist_name} band")
                if results:
                    for result in results:
                        result_title = result.get('title', '')
                        if '(band)' in result_title.lower() or '(musical group)' in result_title.lower():
                            search_summary = await get_wiki_summary(result_title)
                            if search_summary:
                                search_check = is_disambiguation_or_generic(search_summary)
                                if not search_check['isDisambiguation'] and not search_check['isGeneric']:
                                    summary = search_summary
                                    article_title = result_title
                                    break
    
    if not summary:
        return None
    
    # Get infobox for genres
    infobox = await get_wiki_infobox(article_title)
    
    # Split and clean genres properly
    genres_array = split_and_clean_genres(infobox.get('genre') if infobox else None)
    genres = ', '.join(genres_array) if genres_array else None
    
    return {
        'title': summary.get('title'),
        'summary': summary.get('extract'),
        'genres': genres,
        'genresArray': genres_array,
        'thumbnail': summary.get('thumbnail', {}).get('source') if summary.get('thumbnail') else None,
        'wikiUrl': summary.get('content_urls', {}).get('desktop', {}).get('page')
    }


async def get_song_info(title_or_wiki_id: str, artist_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Get song info from Wikipedia - main entry point
    
    Args:
        title_or_wiki_id: Song title or Wikipedia ID
        artist_name: Artist name (optional)
        
    Returns:
        Dictionary with comprehensive song information
    """
    try:
        print(f"[WIKI] get_song_info: titleOrWikiId='{title_or_wiki_id}', artistName='{artist_name}'")
        
        article_title = title_or_wiki_id
        summary = None
        
        # If artistName is provided, do full disambiguation resolution
        if artist_name:
            resolved = await resolve_song_page(title_or_wiki_id, artist_name)
            if resolved:
                article_title = resolved['articleTitle']
                summary = resolved['summary']
        else:
            # Just try to get the summary directly
            summary = await get_wiki_summary(title_or_wiki_id)
        
        if not summary:
            return None
        
        # Get infobox data
        infobox = await get_wiki_infobox(article_title)
        
        # Split and clean genres properly
        genres_array = split_and_clean_genres(infobox.get('genre') if infobox else None)
        genres_original = ', '.join(genres_array) if genres_array else None
        genres_normalized = normalize_genres(genres_array)
        genre_combined = ', '.join(genres_normalized) if genres_normalized else None
        
        # Extract release date
        released_field = infobox.get('released') if infobox else None
        released_clean = None
        if released_field:
            year_match = re.search(r'\b(19\d{2}|20\d{2})\b', released_field)
            if year_match:
                released_clean = year_match.group(1)
        
        return {
            'title': summary.get('title'),
            'artist': infobox.get('artist') if infobox else artist_name,
            'album': infobox.get('album') if infobox else None,
            'released': released_clean,
            'genre': genre_combined,
            'genresOriginal': genres_original,
            'genresNormalized': genres_normalized,
            'genreCombined': genre_combined,
            'length': infobox.get('length') if infobox else None,
            'summary': summary.get('extract'),
            'thumbnail': summary.get('thumbnail', {}).get('source') if summary.get('thumbnail') else None,
            'wikiUrl': summary.get('content_urls', {}).get('desktop', {}).get('page')
        }
    except Exception as e:
        print(f"[WIKI] get_song_info error: {e}")
        return None


async def get_album_info(album_title: str, artist_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Get album info from Wikipedia
    
    Args:
        album_title: Album title
        artist_name: Artist name (optional)
        
    Returns:
        Dictionary with album information
    """
    print(f"[WIKI] get_album_info: '{album_title}' by '{artist_name}'")
    
    # Try multiple disambiguation patterns
    attempts = []
    
    if artist_name:
        attempts.append(f"{album_title} ({artist_name} album)")
        attempts.append(f"{album_title} (album by {artist_name})")
    
    # Try common year ranges for albums
    import datetime
    current_year = datetime.datetime.now().year
    year_ranges = [current_year, current_year - 1, current_year - 2,
                   2020, 2015, 2010, 2005, 2000,
                   1995, 1990, 1985, 1980, 1975, 1970]
    
    for year in year_ranges:
        if year <= current_year:
            attempts.append(f"{album_title} ({year} album)")
    
    attempts.append(f"{album_title} (album)")
    attempts.append(album_title)
    
    summary = None
    article_title = album_title
    
    for attempt in attempts:
        summary = await get_wiki_summary(attempt)
        if summary:
            check = is_disambiguation_or_generic(summary)
            if not check['isDisambiguation'] and not check['isGeneric']:
                article_title = attempt
                print(f"[WIKI] get_album_info found via: '{attempt}'")
                break
            summary = None
    
    if not summary:
        return None
    
    # Get infobox
    infobox = await get_wiki_infobox(article_title)
    
    # Split and clean genres
    genres_original_array = split_and_clean_genres(infobox.get('genre') if infobox else None)
    
    return {
        'title': album_title,
        'artist': infobox.get('artist') if infobox else artist_name,
        'released': infobox.get('released') if infobox else None,
        'genre': infobox.get('genre') if infobox else None,
        'genresOriginalArray': genres_original_array,
        'genresSelected': genres_original_array[:3] if genres_original_array else [],
        'length': infobox.get('length') if infobox else None,
        'summary': summary.get('extract'),
        'thumbnail': summary.get('thumbnail', {}).get('source') if summary.get('thumbnail') else None,
        'wikiUrl': summary.get('content_urls', {}).get('desktop', {}).get('page')
    }


# Export normalize function with legacy name
normalize_infobox_genres = normalize_genres

