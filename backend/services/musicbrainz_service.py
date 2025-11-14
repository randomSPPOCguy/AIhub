"""
MusicBrainz API Service
Integration with MusicBrainz database for music metadata
Ported from Node.js version
"""

import asyncio
import os
from typing import Optional, Dict, List, Any, Tuple
import httpx

# Build user-agent string
MB_UA_APP = os.getenv("MB_UA_APP", "AIHub")
MB_UA_VERSION = os.getenv("MB_UA_VERSION", "1.1")
MB_UA_CONTACT = os.getenv("MB_UA_CONTACT", "user@example.com")
MB_UA = f"{MB_UA_APP}/{MB_UA_VERSION} ({MB_UA_CONTACT})"

# Config-driven filters
MB_PRIMARY_INCLUDE = [s.strip().lower() for s in os.getenv("MB_RG_PRIMARY_INCLUDE", "album").split(",") if s.strip()]
MB_PRIMARY_EXCLUDE = [s.strip().lower() for s in os.getenv("MB_RG_EXCLUDE_PRIMARY", "single,ep").split(",") if s.strip()]
MB_SECONDARY_EXCLUDE = [s.strip().lower() for s in os.getenv("MB_RG_SECONDARY_EXCLUDE", "live,compilation").split(",") if s.strip()]
MB_STATUS_INCLUDE = os.getenv("MB_RG_STATUS_INCLUDE", "").strip().lower()


def mb_headers() -> Dict[str, str]:
    """Get MusicBrainz API headers with proper user-agent"""
    return {
        "User-Agent": MB_UA,
        "Accept": "application/json"
    }


async def mb_get(url: str) -> Dict[str, Any]:
    """
    Make a GET request to MusicBrainz API
    
    Args:
        url: MusicBrainz API URL
        
    Returns:
        JSON response data
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=mb_headers(), timeout=10.0)
        if response.status_code != 200:
            text = response.text if response.text else ""
            raise Exception(f"MB {response.status_code} for {url} {text}")
        return response.json()


async def sleep(ms: int):
    """Sleep helper for rate limiting"""
    await asyncio.sleep(ms / 1000)


async def mb_search_artist_by_name(name: str, limit: int = 5) -> Optional[Dict[str, Any]]:
    """
    Search for artist by name on MusicBrainz
    
    Args:
        name: Artist name
        limit: Maximum number of results
        
    Returns:
        Best matching artist data, or None
    """
    from urllib.parse import quote
    q = quote(f'artist:"{name}"')
    url = f"https://musicbrainz.org/ws/2/artist?query={q}&limit={limit}&fmt=json"
    
    data = await mb_get(url)
    artists = data.get('artists', [])
    
    if not artists:
        return None
    
    # Sort by score
    artists.sort(key=lambda a: a.get('score', 0), reverse=True)
    return artists[0]


def summarize_discography(release_groups: List[Dict]) -> Dict[str, Any]:
    """
    Summarize discography with filtering
    
    Args:
        release_groups: List of release group data
        
    Returns:
        Summary with count, years, and sample albums
    """
    keep = []
    for rg in release_groups:
        prim = (rg.get('primary-type', '') or '').lower()
        secs = [(s or '').lower() for s in rg.get('secondary-types', [])]
        
        if MB_PRIMARY_INCLUDE and prim not in MB_PRIMARY_INCLUDE:
            continue
        if prim in MB_PRIMARY_EXCLUDE:
            continue
        if any(s in MB_SECONDARY_EXCLUDE for s in secs):
            continue
        
        keep.append(rg)
    
    years = []
    for rg in keep:
        date = rg.get('first-release-date', '')
        if date:
            year_str = date[:4]
            try:
                years.append(int(year_str))
            except ValueError:
                pass
    
    first_year = min(years) if years else None
    latest_year = max(years) if years else None
    sample_albums = [rg.get('title') for rg in keep[:5]]
    
    return {
        'count': len(keep),
        'firstYear': first_year,
        'latestYear': latest_year,
        'sampleAlbums': sample_albums
    }


async def mb_release_groups_filtered_by_artist(artist_mbid: str, limit: int = 100, offset: int = 0) -> List[Dict]:
    """
    Get release groups filtered by artist with album filtering
    
    Args:
        artist_mbid: MusicBrainz artist ID
        limit: Maximum results
        offset: Offset for pagination
        
    Returns:
        List of release groups
    """
    from urllib.parse import quote
    
    include_prim = ' OR '.join(MB_PRIMARY_INCLUDE) if MB_PRIMARY_INCLUDE else 'primarytype:album'
    not_secondary = f' AND NOT secondarytype:({" OR ".join(MB_SECONDARY_EXCLUDE)})' if MB_SECONDARY_EXCLUDE else ''
    not_primary = f' AND NOT primarytype:({" OR ".join(MB_PRIMARY_EXCLUDE)})' if MB_PRIMARY_EXCLUDE else ''
    
    base_query = f'arid:{artist_mbid} AND ({include_prim}){not_secondary}{not_primary}'
    query_with_status = f'{base_query} AND status:{MB_STATUS_INCLUDE}' if MB_STATUS_INCLUDE else base_query
    
    async def run(q: str) -> List[Dict]:
        url = f'https://musicbrainz.org/ws/2/release-group?query={quote(q)}&limit={limit}&offset={offset}&fmt=json'
        data = await mb_get(url)
        return data.get('release-groups', [])
    
    # Try with status first (if configured), then fall back without it
    rgs = await run(query_with_status)
    if (not rgs or len(rgs) == 0) and MB_STATUS_INCLUDE:
        rgs = await run(base_query)
    
    return rgs


async def mb_search_recording(title: str, artist_name: str, limit: int = 5) -> Optional[Dict[str, Any]]:
    """
    Search for recording (track) by title and artist
    
    Args:
        title: Track title
        artist_name: Artist name
        limit: Maximum results
        
    Returns:
        Best matching recording data, or None
    """
    from urllib.parse import quote
    q = quote(f'recording:"{title}" AND artist:"{artist_name}"')
    url = f'https://musicbrainz.org/ws/2/recording?query={q}&limit={limit}&fmt=json'
    
    data = await mb_get(url)
    recordings = data.get('recordings', [])
    
    if not recordings:
        return None
    
    # Sort by score
    recordings.sort(key=lambda r: r.get('score', 0), reverse=True)
    return recordings[0]


def extract_wiki_id_from_relations(relations: List[Dict]) -> Optional[Dict[str, Any]]:
    """
    Extract Wikipedia ID from MusicBrainz relations
    
    Args:
        relations: List of relation objects
        
    Returns:
        Dict with wikiId, source, wikidataId, or None
    """
    if not relations or not isinstance(relations, list):
        return None
    
    # Prefer direct wikipedia link
    wiki_rel = next((r for r in relations 
                    if r.get('type') == 'wikipedia' 
                    and 'wikipedia.org/wiki/' in r.get('url', {}).get('resource', '')), None)
    
    if wiki_rel:
        resource = wiki_rel['url']['resource']
        wiki_id = resource.split('/wiki/')[1] if '/wiki/' in resource else None
        return {
            'wikiId': wiki_id,
            'source': 'wikipedia',
            'wikidataId': None
        }
    
    # Fallback to wikidata
    wd_rel = next((r for r in relations 
                  if r.get('type') == 'wikidata' 
                  and 'wikidata.org/wiki/' in r.get('url', {}).get('resource', '')), None)
    
    if wd_rel:
        resource = wd_rel['url']['resource']
        wikidata_id = resource.split('/wiki/')[1] if '/wiki/' in resource else None
        return {
            'wikiId': None,
            'source': 'wikidata',
            'wikidataId': wikidata_id
        }
    
    return None


async def mb_get_wikipedia_id_for_artist(artist_id: str) -> Optional[Dict[str, Any]]:
    """
    Get Wikipedia ID for artist from MusicBrainz
    
    Args:
        artist_id: MusicBrainz artist ID
        
    Returns:
        Dict with Wikipedia/Wikidata info, or None
    """
    artist_id_clean = str(artist_id).strip()
    url = f'https://musicbrainz.org/ws/2/artist/{artist_id_clean}?inc=url-rels&fmt=json'
    
    data = await mb_get(url)
    return extract_wiki_id_from_relations(data.get('relations', []))


async def mb_get_wikipedia_id_for_recording(recording_id: str) -> Optional[Dict[str, Any]]:
    """
    Get Wikipedia ID for recording from MusicBrainz
    
    Args:
        recording_id: MusicBrainz recording ID
        
    Returns:
        Dict with Wikipedia/Wikidata info, or None
    """
    recording_id_clean = str(recording_id).strip()
    url = f'https://musicbrainz.org/ws/2/recording/{recording_id_clean}?inc=url-rels&fmt=json'
    
    data = await mb_get(url)
    return extract_wiki_id_from_relations(data.get('relations', []))


async def mb_get_wikipedia_id_for_release_group(rg_id: str) -> Optional[Dict[str, Any]]:
    """
    Get Wikipedia ID for release group from MusicBrainz
    
    Args:
        rg_id: MusicBrainz release group ID
        
    Returns:
        Dict with Wikipedia/Wikidata info, or None
    """
    rg_id_clean = str(rg_id).strip()
    url = f'https://musicbrainz.org/ws/2/release-group/{rg_id_clean}?inc=url-rels&fmt=json'
    
    data = await mb_get(url)
    return extract_wiki_id_from_relations(data.get('relations', []))


async def mb_resolve_wikipedia_id(
    artist_id: Optional[str] = None,
    recording_id: Optional[str] = None,
    release_group_id: Optional[str] = None,
    prefer: Optional[List[str]] = None
) -> Optional[Dict[str, Any]]:
    """
    High level resolver: passes available MBIDs and returns earliest direct wikiId found
    
    Args:
        artist_id: MusicBrainz artist ID
        recording_id: MusicBrainz recording ID
        release_group_id: MusicBrainz release group ID
        prefer: Preferred order ['recording', 'release-group', 'artist']
        
    Returns:
        Dict with scope and wiki info, or None
    """
    if not prefer:
        prefer = ['recording', 'release-group', 'artist']
    
    tasks = []
    for layer in prefer:
        if layer == 'recording' and recording_id:
            tasks.append(('recording', mb_get_wikipedia_id_for_recording(recording_id)))
        elif layer == 'release-group' and release_group_id:
            tasks.append(('release-group', mb_get_wikipedia_id_for_release_group(release_group_id)))
        elif layer == 'artist' and artist_id:
            tasks.append(('artist', mb_get_wikipedia_id_for_artist(artist_id)))
    
    for scope, task in tasks:
        try:
            res = await task
            if res:
                return {'scope': scope, **res}
            # Respect polite pacing
            await sleep(200)
        except Exception:
            pass
    
    return None


async def mb_get_release_tracks(release_id: str) -> List[Dict[str, Any]]:
    """
    Get tracks from a release
    
    Args:
        release_id: MusicBrainz release ID
        
    Returns:
        List of track data
    """
    release_id_clean = str(release_id).strip().lower()
    url = f'https://musicbrainz.org/ws/2/release/{release_id_clean}?inc=recordings&fmt=json'
    
    data = await mb_get(url)
    
    tracks = []
    media = data.get('media', [])
    
    for medium in media:
        for track in medium.get('tracks', []):
            track_data = {
                'position': track.get('position'),
                'title': track.get('title'),
                'length': round(track.get('length', 0) / 1000) if track.get('length') else None,
                'recordingId': track.get('recording', {}).get('id')
            }
            tracks.append(track_data)
    
    return tracks


async def mb_find_album_for_recording(artist_mbid: str, title: str, limit: int = 25) -> Optional[Dict[str, str]]:
    """
    Track -> album mapping (avoid singles)
    
    Args:
        artist_mbid: MusicBrainz artist ID
        title: Track title
        limit: Maximum results
        
    Returns:
        Dict with releaseId and title, or None
    """
    from urllib.parse import quote
    q = quote(f'recording:"{title}" AND arid:{artist_mbid}')
    url = f'https://musicbrainz.org/ws/2/recording?query={q}&inc=releases&limit={limit}&fmt=json'
    
    data = await mb_get(url)
    recs = data.get('recordings', [])
    
    for rec in recs:
        releases = rec.get('releases', [])
        for rel in releases:
            prim = (rel.get('primary-type', '') or '').lower()
            if MB_PRIMARY_INCLUDE and prim not in MB_PRIMARY_INCLUDE:
                continue
            if prim in MB_PRIMARY_EXCLUDE:
                continue
            return {'releaseId': rel.get('id'), 'title': rel.get('title')}
    
    return None


async def mb_artist_genres_tags(artist_mbid: str) -> Dict[str, List[str]]:
    """
    Get artist genres and tags from MusicBrainz
    
    Args:
        artist_mbid: MusicBrainz artist ID
        
    Returns:
        Dict with genres, tags, and merged lists
    """
    artist_mbid_clean = str(artist_mbid).strip().lower()
    url = f'https://musicbrainz.org/ws/2/artist/{artist_mbid_clean}?inc=tags+genres&fmt=json'
    
    data = await mb_get(url)
    
    genres = [g.get('name') for g in data.get('genres', [])]
    tags = [t.get('name') for t in data.get('tags', [])]
    merged = genres + tags
    
    return {
        'genres': genres,
        'tags': tags,
        'merged': merged
    }

