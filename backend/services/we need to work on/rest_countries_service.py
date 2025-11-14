"""
REST Countries API Service
Provides country data (flags, capitals, population, currencies, languages, etc.)
No authentication required - open public API
"""

import asyncio
from typing import Optional, Dict, List, Any
import httpx

# Base URL
BASE_URL = "https://restcountries.com/v3.1"

# In-memory cache
_all_countries_cache: Optional[List[Dict]] = None
_country_cache: Dict[str, Any] = {}
_region_cache: Dict[str, List[Dict]] = {}


async def get_all_countries(fields: List[str] = None) -> List[Dict[str, Any]]:
    """
    Get all countries with optional field filtering
    
    Args:
        fields: List of fields to include (e.g., ["name", "capital", "flags"])
        
    Returns:
        List of all countries
    """
    # Use cache if no specific fields requested
    if fields is None and _all_countries_cache is not None:
        return _all_countries_cache
    
    url = f"{BASE_URL}/all"
    if fields:
        fields_str = ",".join(fields)
        url += f"?fields={fields_str}"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=10.0)
            if response.status_code != 200:
                print(f"[REST_COUNTRIES] get_all_countries non-200 response: {response.status_code}")
                return []
            data = response.json()
            
            # Cache if no specific fields
            if fields is None:
                globals()['_all_countries_cache'] = data
            
            return data
    except Exception as e:
        print(f"[REST_COUNTRIES] get_all_countries error: {e}")
        return []


async def get_country_by_name(name: str, full_text: bool = False) -> Optional[Dict[str, Any]]:
    """
    Get country by name
    
    Args:
        name: Country name (full or partial)
        full_text: If True, only exact matches
        
    Returns:
        Country data or None
    """
    cache_key = f"{name}_{full_text}"
    if cache_key in _country_cache:
        return _country_cache[cache_key]
    
    from urllib.parse import quote
    encoded_name = quote(name)
    url = f"{BASE_URL}/name/{encoded_name}"
    if full_text:
        url += "?fullText=true"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=10.0)
            if response.status_code != 200:
                print(f"[REST_COUNTRIES] get_country_by_name non-200 response: {response.status_code}")
                return None
            data = response.json()
            
            # API returns list, get first match
            result = data[0] if data else None
            _country_cache[cache_key] = result
            return result
    except Exception as e:
        print(f"[REST_COUNTRIES] get_country_by_name error for '{name}': {e}")
        return None


async def get_country_by_code(code: str) -> Optional[Dict[str, Any]]:
    """
    Get country by 2 or 3 letter code
    
    Args:
        code: ISO 3166-1 alpha-2 or alpha-3 code (e.g., "US", "USA")
        
    Returns:
        Country data or None
    """
    cache_key = f"code_{code}"
    if cache_key in _country_cache:
        return _country_cache[cache_key]
    
    code_upper = code.upper()
    url = f"{BASE_URL}/alpha/{code_upper}"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=10.0)
            if response.status_code != 200:
                print(f"[REST_COUNTRIES] get_country_by_code non-200 response: {response.status_code}")
                return None
            data = response.json()
            _country_cache[cache_key] = data
            return data
    except Exception as e:
        print(f"[REST_COUNTRIES] get_country_by_code error for '{code}': {e}")
        return None


async def get_countries_by_region(region: str) -> List[Dict[str, Any]]:
    """
    Get countries by region
    
    Args:
        region: Region name (e.g., "Europe", "Asia", "Americas", "Africa", "Oceania")
        
    Returns:
        List of countries in region
    """
    cache_key = region.lower()
    if cache_key in _region_cache:
        return _region_cache[cache_key]
    
    from urllib.parse import quote
    encoded_region = quote(region)
    url = f"{BASE_URL}/region/{encoded_region}"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=10.0)
            if response.status_code != 200:
                print(f"[REST_COUNTRIES] get_countries_by_region non-200 response: {response.status_code}")
                return []
            data = response.json()
            _region_cache[cache_key] = data
            return data
    except Exception as e:
        print(f"[REST_COUNTRIES] get_countries_by_region error for '{region}': {e}")
        return []


async def get_countries_by_currency(currency: str) -> List[Dict[str, Any]]:
    """
    Get countries by currency code
    
    Args:
        currency: Currency code (e.g., "USD", "EUR", "GBP")
        
    Returns:
        List of countries using that currency
    """
    from urllib.parse import quote
    encoded_currency = quote(currency.upper())
    url = f"{BASE_URL}/currency/{encoded_currency}"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=10.0)
            if response.status_code != 200:
                print(f"[REST_COUNTRIES] get_countries_by_currency non-200 response: {response.status_code}")
                return []
            data = response.json()
            return data
    except Exception as e:
        print(f"[REST_COUNTRIES] get_countries_by_currency error for '{currency}': {e}")
        return []


async def get_countries_by_language(language: str) -> List[Dict[str, Any]]:
    """
    Get countries by language code
    
    Args:
        language: Language code (e.g., "en", "es", "fr")
        
    Returns:
        List of countries where that language is spoken
    """
    from urllib.parse import quote
    encoded_language = quote(language.lower())
    url = f"{BASE_URL}/lang/{encoded_language}"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=10.0)
            if response.status_code != 200:
                print(f"[REST_COUNTRIES] get_countries_by_language non-200 response: {response.status_code}")
                return []
            data = response.json()
            return data
    except Exception as e:
        print(f"[REST_COUNTRIES] get_countries_by_language error for '{language}': {e}")
        return []


async def get_countries_by_capital(capital: str) -> List[Dict[str, Any]]:
    """
    Get countries by capital city
    
    Args:
        capital: Capital city name
        
    Returns:
        List of matching countries
    """
    from urllib.parse import quote
    encoded_capital = quote(capital)
    url = f"{BASE_URL}/capital/{encoded_capital}"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=10.0)
            if response.status_code != 200:
                print(f"[REST_COUNTRIES] get_countries_by_capital non-200 response: {response.status_code}")
                return []
            data = response.json()
            return data
    except Exception as e:
        print(f"[REST_COUNTRIES] get_countries_by_capital error for '{capital}': {e}")
        return []


async def health_check() -> bool:
    """
    Health check for REST Countries service
    
    Returns:
        True if service is accessible
    """
    try:
        async with httpx.AsyncClient() as client:
            # Try getting USA data
            response = await client.get(f"{BASE_URL}/alpha/US", timeout=5.0)
            return response.status_code == 200
    except Exception as e:
        print(f"[REST_COUNTRIES] health_check failed: {e}")
        return False

