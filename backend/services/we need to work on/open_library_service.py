"""
Open Library API Service
Provides book, author, and edition data from Internet Archive
No authentication required - open public API
"""

import asyncio
import os
from typing import Optional, Dict, List, Any
import httpx

# User-Agent for Open Library API (recommended for heavy use)
OL_UA_APP = os.getenv("OL_UA_APP", "AIHub")
OL_UA_VERSION = os.getenv("OL_UA_VERSION", "2.0")
OL_UA_CONTACT = os.getenv("OL_UA_CONTACT", "user@example.com")
OL_UA = f"{OL_UA_APP}/{OL_UA_VERSION} ({OL_UA_CONTACT})"

# Base URLs
BASE_URL = "https://openlibrary.org"
COVERS_URL = "https://covers.openlibrary.org"

# In-memory cache
_search_cache: Dict[str, List[Dict]] = {}
_work_cache: Dict[str, Any] = {}
_edition_cache: Dict[str, Any] = {}
_author_cache: Dict[str, Any] = {}


def ol_headers() -> Dict[str, str]:
    """Get Open Library API headers with proper user-agent"""
    return {
        "User-Agent": OL_UA,
        "Accept": "application/json"
    }


async def search_books(query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Search for books
    
    Args:
        query: Search query (title, author, ISBN, etc.)
        limit: Maximum number of results
        
    Returns:
        List of matching books
    """
    cache_key = f"{query}_{limit}"
    if cache_key in _search_cache:
        return _search_cache[cache_key]
    
    from urllib.parse import quote
    encoded_query = quote(query)
    url = f"{BASE_URL}/search.json?q={encoded_query}&limit={limit}"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=ol_headers(), timeout=10.0)
            if response.status_code != 200:
                print(f"[OPEN_LIBRARY] search_books non-200 response: {response.status_code}")
                return []
            data = response.json()
            docs = data.get('docs', [])
            _search_cache[cache_key] = docs
            return docs
    except Exception as e:
        print(f"[OPEN_LIBRARY] search_books error for '{query}': {e}")
        return []


async def get_work_details(work_id: str) -> Optional[Dict[str, Any]]:
    """
    Get details about a work
    
    Args:
        work_id: Open Library work ID (e.g., "OL45804W")
        
    Returns:
        Work details or None
    """
    if work_id in _work_cache:
        return _work_cache[work_id]
    
    # Ensure work_id has proper format
    if not work_id.startswith('/works/'):
        work_id = f"/works/{work_id}"
    
    url = f"{BASE_URL}{work_id}.json"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=ol_headers(), timeout=10.0)
            if response.status_code != 200:
                print(f"[OPEN_LIBRARY] get_work_details non-200 response: {response.status_code}")
                return None
            data = response.json()
            _work_cache[work_id] = data
            return data
    except Exception as e:
        print(f"[OPEN_LIBRARY] get_work_details error for '{work_id}': {e}")
        return None


async def get_edition_details(edition_id: str) -> Optional[Dict[str, Any]]:
    """
    Get details about an edition
    
    Args:
        edition_id: Open Library edition ID (e.g., "OL7353617M")
        
    Returns:
        Edition details or None
    """
    if edition_id in _edition_cache:
        return _edition_cache[edition_id]
    
    # Ensure edition_id has proper format
    if not edition_id.startswith('/books/'):
        edition_id = f"/books/{edition_id}"
    
    url = f"{BASE_URL}{edition_id}.json"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=ol_headers(), timeout=10.0)
            if response.status_code != 200:
                print(f"[OPEN_LIBRARY] get_edition_details non-200 response: {response.status_code}")
                return None
            data = response.json()
            _edition_cache[edition_id] = data
            return data
    except Exception as e:
        print(f"[OPEN_LIBRARY] get_edition_details error for '{edition_id}': {e}")
        return None


async def get_author_details(author_id: str) -> Optional[Dict[str, Any]]:
    """
    Get details about an author
    
    Args:
        author_id: Open Library author ID (e.g., "OL23919A")
        
    Returns:
        Author details or None
    """
    if author_id in _author_cache:
        return _author_cache[author_id]
    
    # Ensure author_id has proper format
    if not author_id.startswith('/authors/'):
        author_id = f"/authors/{author_id}"
    
    url = f"{BASE_URL}{author_id}.json"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=ol_headers(), timeout=10.0)
            if response.status_code != 200:
                print(f"[OPEN_LIBRARY] get_author_details non-200 response: {response.status_code}")
                return None
            data = response.json()
            _author_cache[author_id] = data
            return data
    except Exception as e:
        print(f"[OPEN_LIBRARY] get_author_details error for '{author_id}': {e}")
        return None


def get_cover_url(isbn: str = None, oclc: str = None, lccn: str = None, 
                   olid: str = None, id_type: str = None, size: str = "M") -> str:
    """
    Get cover image URL
    
    Args:
        isbn: ISBN number
        oclc: OCLC number
        lccn: LCCN number
        olid: Open Library ID
        id_type: Type of ID ('isbn', 'oclc', 'lccn', 'olid')
        size: Image size ('S' small, 'M' medium, 'L' large)
        
    Returns:
        Cover image URL
    """
    # Determine ID type and value
    if isbn:
        id_type = 'isbn'
        id_value = isbn
    elif oclc:
        id_type = 'oclc'
        id_value = oclc
    elif lccn:
        id_type = 'lccn'
        id_value = lccn
    elif olid:
        id_type = 'id'
        id_value = olid
    else:
        return ""
    
    return f"{COVERS_URL}/b/{id_type}/{id_value}-{size}.jpg"


async def search_by_author(author: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Search for books by author
    
    Args:
        author: Author name
        limit: Maximum number of results
        
    Returns:
        List of books by author
    """
    from urllib.parse import quote
    encoded_author = quote(author)
    url = f"{BASE_URL}/search.json?author={encoded_author}&limit={limit}"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=ol_headers(), timeout=10.0)
            if response.status_code != 200:
                print(f"[OPEN_LIBRARY] search_by_author non-200 response: {response.status_code}")
                return []
            data = response.json()
            return data.get('docs', [])
    except Exception as e:
        print(f"[OPEN_LIBRARY] search_by_author error for '{author}': {e}")
        return []


async def search_by_isbn(isbn: str) -> Optional[Dict[str, Any]]:
    """
    Search for book by ISBN
    
    Args:
        isbn: ISBN number
        
    Returns:
        Book details or None
    """
    url = f"{BASE_URL}/isbn/{isbn}.json"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=ol_headers(), timeout=10.0)
            if response.status_code != 200:
                print(f"[OPEN_LIBRARY] search_by_isbn non-200 response: {response.status_code}")
                return None
            data = response.json()
            return data
    except Exception as e:
        print(f"[OPEN_LIBRARY] search_by_isbn error for '{isbn}': {e}")
        return None


async def health_check() -> bool:
    """
    Health check for Open Library service
    
    Returns:
        True if service is accessible
    """
    try:
        async with httpx.AsyncClient() as client:
            # Try searching for a common book
            response = await client.get(
                f"{BASE_URL}/search.json?q=lord+of+the+rings&limit=1", 
                headers=ol_headers(), 
                timeout=5.0
            )
            return response.status_code == 200
    except Exception as e:
        print(f"[OPEN_LIBRARY] health_check failed: {e}")
        return False

