"""
Information API Endpoints for AI Hub
=====================================
Provides tools/functions the AI can use to fetch external data:
- Wikipedia lookups
- MusicBrainz metadata
- Album/artist information
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import aiohttp
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


class WikipediaRequest(BaseModel):
    query: str
    sentences: int = 3  # Number of sentences to return


class MusicBrainzRequest(BaseModel):
    artist: Optional[str] = None
    album: Optional[str] = None
    song: Optional[str] = None


class WikipediaResponse(BaseModel):
    title: str
    summary: str
    url: str


class MusicMetadataResponse(BaseModel):
    artist: Optional[str] = None
    album: Optional[str] = None
    year: Optional[int] = None
    genre: Optional[List[str]] = None
    source: str


@router.post("/wikipedia/search", response_model=WikipediaResponse)
async def search_wikipedia(request: WikipediaRequest):
    """
    Search Wikipedia and return summary.
    
    Example:
        POST /api/tools/wikipedia/search
        {
            "query": "Led Zeppelin",
            "sentences": 3
        }
    """
    try:
        async with aiohttp.ClientSession() as session:
            # Use Wikipedia API
            params = {
                "action": "query",
                "format": "json",
                "prop": "extracts|info",
                "exintro": True,
                "explaintext": True,
                "exsentences": request.sentences,
                "titles": request.query,
                "inprop": "url",
                "redirects": 1
            }
            
            async with session.get(
                "https://en.wikipedia.org/w/api.php",
                params=params
            ) as response:
                data = await response.json()
                
                pages = data.get("query", {}).get("pages", {})
                if not pages:
                    raise HTTPException(status_code=404, detail="No Wikipedia page found")
                
                # Get first page
                page = next(iter(pages.values()))
                
                if "missing" in page:
                    raise HTTPException(status_code=404, detail="Page not found")
                
                return WikipediaResponse(
                    title=page.get("title", request.query),
                    summary=page.get("extract", "No summary available."),
                    url=f"https://en.wikipedia.org/wiki/{page.get('title', '').replace(' ', '_')}"
                )
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Wikipedia search error: {e}")
        raise HTTPException(status_code=500, detail=f"Wikipedia search failed: {str(e)}")


@router.post("/musicbrainz/lookup", response_model=MusicMetadataResponse)
async def lookup_musicbrainz(request: MusicBrainzRequest):
    """
    Lookup music metadata from MusicBrainz.
    
    Example:
        POST /api/tools/musicbrainz/lookup
        {
            "artist": "Pink Floyd",
            "album": "The Wall"
        }
    """
    try:
        async with aiohttp.ClientSession() as session:
            headers = {
                "User-Agent": "AIHub/1.0 (music bot assistant)",
                "Accept": "application/json"
            }
            
            result = MusicMetadataResponse(source="musicbrainz")
            
            # Search for artist
            if request.artist:
                params = {
                    "query": f'artist:"{request.artist}"',
                    "fmt": "json",
                    "limit": 1
                }
                
                async with session.get(
                    "https://musicbrainz.org/ws/2/artist",
                    params=params,
                    headers=headers
                ) as response:
                    data = await response.json()
                    artists = data.get("artists", [])
                    
                    if artists:
                        artist_data = artists[0]
                        result.artist = artist_data.get("name")
                        
                        # Get genres/tags
                        tags = artist_data.get("tags", [])
                        if tags:
                            result.genre = [tag["name"] for tag in tags[:5]]
            
            # Search for release (album)
            if request.album and request.artist:
                params = {
                    "query": f'release:"{request.album}" AND artist:"{request.artist}"',
                    "fmt": "json",
                    "limit": 1
                }
                
                async with session.get(
                    "https://musicbrainz.org/ws/2/release",
                    params=params,
                    headers=headers
                ) as response:
                    data = await response.json()
                    releases = data.get("releases", [])
                    
                    if releases:
                        release = releases[0]
                        result.album = release.get("title")
                        result.year = release.get("date", "")[:4] if release.get("date") else None
                        
                        if result.year:
                            try:
                                result.year = int(result.year)
                            except ValueError:
                                result.year = None
            
            return result
            
    except Exception as e:
        logger.error(f"MusicBrainz lookup error: {e}")
        raise HTTPException(status_code=500, detail=f"MusicBrainz lookup failed: {str(e)}")


@router.get("/genres/normalize")
async def normalize_genre(genre: str) -> Dict[str, Any]:
    """
    Normalize genre labels to consistent categories.
    
    Maps various genre names to standardized categories.
    
    Example:
        GET /api/tools/genres/normalize?genre=alt-rock
        
        Returns:
            {
                "input": "alt-rock",
                "normalized": "Alternative Rock",
                "category": "Rock",
                "tags": ["rock", "alternative"]
            }
    """
    # Genre normalization map
    genre_map = {
        # Rock variants
        "alt-rock": ("Alternative Rock", "Rock", ["rock", "alternative"]),
        "alternative": ("Alternative Rock", "Rock", ["rock", "alternative"]),
        "indie-rock": ("Indie Rock", "Rock", ["rock", "indie"]),
        "indie": ("Indie Rock", "Rock", ["rock", "indie"]),
        "hard-rock": ("Hard Rock", "Rock", ["rock", "hard rock"]),
        "prog-rock": ("Progressive Rock", "Rock", ["rock", "progressive"]),
        "progressive": ("Progressive Rock", "Rock", ["rock", "progressive"]),
        "punk": ("Punk Rock", "Rock", ["rock", "punk"]),
        "punk-rock": ("Punk Rock", "Rock", ["rock", "punk"]),
        
        # Metal variants
        "metal": ("Heavy Metal", "Metal", ["metal", "heavy"]),
        "heavy-metal": ("Heavy Metal", "Metal", ["metal", "heavy"]),
        "death-metal": ("Death Metal", "Metal", ["metal", "death metal"]),
        "black-metal": ("Black Metal", "Metal", ["metal", "black metal"]),
        
        # Hip Hop variants
        "hip-hop": ("Hip Hop", "Hip Hop/Rap", ["hip hop", "rap"]),
        "rap": ("Hip Hop", "Hip Hop/Rap", ["hip hop", "rap"]),
        "trap": ("Trap", "Hip Hop/Rap", ["hip hop", "trap"]),
        
        # Electronic variants
        "electronic": ("Electronic", "Electronic", ["electronic", "edm"]),
        "edm": ("EDM", "Electronic", ["electronic", "edm"]),
        "house": ("House", "Electronic", ["electronic", "house"]),
        "techno": ("Techno", "Electronic", ["electronic", "techno"]),
        "ambient": ("Ambient", "Electronic", ["electronic", "ambient"]),
        
        # Pop/Other
        "pop": ("Pop", "Pop", ["pop"]),
        "jazz": ("Jazz", "Jazz", ["jazz"]),
        "blues": ("Blues", "Blues", ["blues"]),
        "country": ("Country", "Country", ["country"]),
        "folk": ("Folk", "Folk", ["folk"]),
    }
    
    # Normalize input
    normalized_input = genre.lower().strip().replace(" ", "-")
    
    if normalized_input in genre_map:
        name, category, tags = genre_map[normalized_input]
        return {
            "input": genre,
            "normalized": name,
            "category": category,
            "tags": tags
        }
    else:
        # Return original if no mapping found
        return {
            "input": genre,
            "normalized": genre.title(),
            "category": "Other",
            "tags": [genre.lower()]
        }
