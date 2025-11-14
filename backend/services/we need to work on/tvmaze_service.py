"""
TVmaze API Service
Provides TV show and movie metadata
No authentication required - community-driven, CC BY-SA licensed
"""

import asyncio
from typing import Optional, Dict, List, Any
import httpx
from datetime import datetime

# Base URL
BASE_URL = "https://api.tvmaze.com"

# In-memory cache
_show_cache: Dict[int, Any] = {}
_search_cache: Dict[str, List[Dict]] = {}
_episodes_cache: Dict[int, List[Dict]] = {}
_cast_cache: Dict[int, List[Dict]] = {}


async def search_shows(query: str) -> List[Dict[str, Any]]:
    """
    Search TV shows by title
    
    Args:
        query: Search query
        
    Returns:
        List of matching shows
    """
    cache_key = query.lower()
    if cache_key in _search_cache:
        return _search_cache[cache_key]
    
    from urllib.parse import quote
    encoded_query = quote(query)
    url = f"{BASE_URL}/search/shows?q={encoded_query}"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=10.0)
            if response.status_code != 200:
                print(f"[TVMAZE] search_shows non-200 response: {response.status_code}")
                return []
            data = response.json()
            _search_cache[cache_key] = data
            return data
    except Exception as e:
        print(f"[TVMAZE] search_shows error for '{query}': {e}")
        return []


async def get_show_details(show_id: int) -> Optional[Dict[str, Any]]:
    """
    Get detailed information about a TV show
    
    Args:
        show_id: TVmaze show ID
        
    Returns:
        Dictionary with show details
    """
    if show_id in _show_cache:
        return _show_cache[show_id]
    
    url = f"{BASE_URL}/shows/{show_id}"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=10.0)
            if response.status_code != 200:
                print(f"[TVMAZE] get_show_details non-200 response: {response.status_code}")
                return None
            data = response.json()
            _show_cache[show_id] = data
            return data
    except Exception as e:
        print(f"[TVMAZE] get_show_details error for show {show_id}: {e}")
        return None


async def get_episodes(show_id: int) -> List[Dict[str, Any]]:
    """
    Get all episodes for a TV show
    
    Args:
        show_id: TVmaze show ID
        
    Returns:
        List of episodes
    """
    if show_id in _episodes_cache:
        return _episodes_cache[show_id]
    
    url = f"{BASE_URL}/shows/{show_id}/episodes"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=10.0)
            if response.status_code != 200:
                print(f"[TVMAZE] get_episodes non-200 response: {response.status_code}")
                return []
            data = response.json()
            _episodes_cache[show_id] = data
            return data
    except Exception as e:
        print(f"[TVMAZE] get_episodes error for show {show_id}: {e}")
        return []


async def get_cast(show_id: int) -> List[Dict[str, Any]]:
    """
    Get cast information for a TV show
    
    Args:
        show_id: TVmaze show ID
        
    Returns:
        List of cast members
    """
    if show_id in _cast_cache:
        return _cast_cache[show_id]
    
    url = f"{BASE_URL}/shows/{show_id}/cast"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=10.0)
            if response.status_code != 200:
                print(f"[TVMAZE] get_cast non-200 response: {response.status_code}")
                return []
            data = response.json()
            _cast_cache[show_id] = data
            return data
    except Exception as e:
        print(f"[TVMAZE] get_cast error for show {show_id}: {e}")
        return []


async def get_schedule(country: str = "US", date: str = None) -> List[Dict[str, Any]]:
    """
    Get TV schedule for a country and date
    
    Args:
        country: Country code (default: US)
        date: Date in YYYY-MM-DD format (default: today)
        
    Returns:
        List of scheduled episodes
    """
    if date is None:
        date = datetime.now().strftime('%Y-%m-%d')
    
    url = f"{BASE_URL}/schedule?country={country}&date={date}"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=10.0)
            if response.status_code != 200:
                print(f"[TVMAZE] get_schedule non-200 response: {response.status_code}")
                return []
            data = response.json()
            return data
    except Exception as e:
        print(f"[TVMAZE] get_schedule error: {e}")
        return []


async def search_people(query: str) -> List[Dict[str, Any]]:
    """
    Search for people (actors, crew)
    
    Args:
        query: Search query
        
    Returns:
        List of matching people
    """
    from urllib.parse import quote
    encoded_query = quote(query)
    url = f"{BASE_URL}/search/people?q={encoded_query}"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=10.0)
            if response.status_code != 200:
                print(f"[TVMAZE] search_people non-200 response: {response.status_code}")
                return []
            data = response.json()
            return data
    except Exception as e:
        print(f"[TVMAZE] search_people error for '{query}': {e}")
        return []


async def get_show_by_name(name: str) -> Optional[Dict[str, Any]]:
    """
    Get single best match for a show name
    
    Args:
        name: Show name
        
    Returns:
        Show details or None
    """
    from urllib.parse import quote
    encoded_name = quote(name)
    url = f"{BASE_URL}/singlesearch/shows?q={encoded_name}"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=10.0)
            if response.status_code != 200:
                print(f"[TVMAZE] get_show_by_name non-200 response: {response.status_code}")
                return None
            data = response.json()
            return data
    except Exception as e:
        print(f"[TVMAZE] get_show_by_name error for '{name}': {e}")
        return None


async def health_check() -> bool:
    """
    Health check for TVmaze service
    
    Returns:
        True if service is accessible
    """
    try:
        async with httpx.AsyncClient() as client:
            # Try a simple show lookup (The Office - ID 526)
            response = await client.get(f"{BASE_URL}/shows/526", timeout=5.0)
            return response.status_code == 200
    except Exception as e:
        print(f"[TVMAZE] health_check failed: {e}")
        return False

