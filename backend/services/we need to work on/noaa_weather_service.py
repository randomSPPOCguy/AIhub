"""
NOAA National Weather Service API
Provides US weather forecasts, alerts, and observations
No authentication required - public US government data
"""

import asyncio
import os
from typing import Optional, Dict, List, Any
import httpx

# User-Agent for NOAA API (required!)
NOAA_UA_APP = os.getenv("NOAA_UA_APP", "AIHub")
NOAA_UA_VERSION = os.getenv("NOAA_UA_VERSION", "2.0")
NOAA_UA_CONTACT = os.getenv("NOAA_UA_CONTACT", "user@example.com")
NOAA_UA = f"{NOAA_UA_APP}/{NOAA_UA_VERSION} ({NOAA_UA_CONTACT})"

# Base URL
BASE_URL = "https://api.weather.gov"

# In-memory cache for forecasts and point data
_forecast_cache: Dict[str, Any] = {}
_points_cache: Dict[str, Any] = {}
_alerts_cache: Dict[str, List[Dict]] = {}


def noaa_headers() -> Dict[str, str]:
    """Get NOAA API headers with proper user-agent"""
    return {
        "User-Agent": NOAA_UA,
        "Accept": "application/json"
    }


async def _sleep(ms: int):
    """Sleep helper for rate limiting"""
    await asyncio.sleep(ms / 1000)


async def get_point_metadata(lat: float, lon: float) -> Optional[Dict[str, Any]]:
    """
    Get point metadata (includes forecast URLs, grid coordinates)
    
    Args:
        lat: Latitude
        lon: Longitude
        
    Returns:
        Dictionary with forecast URLs, grid info, etc.
    """
    cache_key = f"{lat},{lon}"
    if cache_key in _points_cache:
        return _points_cache[cache_key]
    
    await _sleep(1000)  # Rate limit: 1 request per second
    
    url = f"{BASE_URL}/points/{lat},{lon}"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=noaa_headers(), timeout=10.0)
            if response.status_code != 200:
                print(f"[NOAA] get_point_metadata non-200 response: {response.status_code}")
                return None
            data = response.json()
            _points_cache[cache_key] = data
            return data
    except Exception as e:
        print(f"[NOAA] get_point_metadata error for {lat},{lon}: {e}")
        return None


async def get_forecast_by_coords(lat: float, lon: float) -> Optional[Dict[str, Any]]:
    """
    Get 7-day forecast for coordinates
    
    Args:
        lat: Latitude
        lon: Longitude
        
    Returns:
        Dictionary with forecast periods
    """
    cache_key = f"forecast_{lat},{lon}"
    if cache_key in _forecast_cache:
        return _forecast_cache[cache_key]
    
    # First get point metadata to get forecast URL
    point_data = await get_point_metadata(lat, lon)
    if not point_data:
        return None
    
    forecast_url = point_data.get('properties', {}).get('forecast')
    if not forecast_url:
        return None
    
    await _sleep(1000)  # Rate limit
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(forecast_url, headers=noaa_headers(), timeout=10.0)
            if response.status_code != 200:
                print(f"[NOAA] get_forecast_by_coords non-200 response: {response.status_code}")
                return None
            data = response.json()
            _forecast_cache[cache_key] = data
            return data
    except Exception as e:
        print(f"[NOAA] get_forecast_by_coords error: {e}")
        return None


async def get_hourly_forecast(lat: float, lon: float) -> Optional[Dict[str, Any]]:
    """
    Get hourly forecast for coordinates
    
    Args:
        lat: Latitude
        lon: Longitude
        
    Returns:
        Dictionary with hourly forecast periods
    """
    cache_key = f"hourly_{lat},{lon}"
    if cache_key in _forecast_cache:
        return _forecast_cache[cache_key]
    
    # First get point metadata to get hourly forecast URL
    point_data = await get_point_metadata(lat, lon)
    if not point_data:
        return None
    
    hourly_url = point_data.get('properties', {}).get('forecastHourly')
    if not hourly_url:
        return None
    
    await _sleep(1000)  # Rate limit
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(hourly_url, headers=noaa_headers(), timeout=10.0)
            if response.status_code != 200:
                print(f"[NOAA] get_hourly_forecast non-200 response: {response.status_code}")
                return None
            data = response.json()
            _forecast_cache[cache_key] = data
            return data
    except Exception as e:
        print(f"[NOAA] get_hourly_forecast error: {e}")
        return None


async def get_active_alerts(lat: float, lon: float) -> Optional[List[Dict[str, Any]]]:
    """
    Get active weather alerts for coordinates
    
    Args:
        lat: Latitude
        lon: Longitude
        
    Returns:
        List of active alerts
    """
    cache_key = f"{lat},{lon}"
    if cache_key in _alerts_cache:
        return _alerts_cache[cache_key]
    
    await _sleep(1000)  # Rate limit
    
    url = f"{BASE_URL}/alerts/active?point={lat},{lon}"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=noaa_headers(), timeout=10.0)
            if response.status_code != 200:
                print(f"[NOAA] get_active_alerts non-200 response: {response.status_code}")
                return []
            data = response.json()
            features = data.get('features', [])
            _alerts_cache[cache_key] = features
            return features
    except Exception as e:
        print(f"[NOAA] get_active_alerts error: {e}")
        return []


async def get_current_conditions(lat: float, lon: float) -> Optional[Dict[str, Any]]:
    """
    Get current weather conditions from nearest observation station
    
    Args:
        lat: Latitude
        lon: Longitude
        
    Returns:
        Dictionary with current conditions
    """
    # First get point metadata to get observation stations
    point_data = await get_point_metadata(lat, lon)
    if not point_data:
        return None
    
    stations_url = point_data.get('properties', {}).get('observationStations')
    if not stations_url:
        return None
    
    await _sleep(1000)  # Rate limit
    
    try:
        # Get list of stations
        async with httpx.AsyncClient() as client:
            response = await client.get(stations_url, headers=noaa_headers(), timeout=10.0)
            if response.status_code != 200:
                return None
            stations_data = response.json()
            stations = stations_data.get('features', [])
            if not stations:
                return None
            
            # Get latest observation from first station
            first_station = stations[0].get('id')
            if not first_station:
                return None
            
            await _sleep(1000)  # Rate limit
            
            obs_url = f"{first_station}/observations/latest"
            response = await client.get(obs_url, headers=noaa_headers(), timeout=10.0)
            if response.status_code != 200:
                return None
            
            data = response.json()
            return data
    except Exception as e:
        print(f"[NOAA] get_current_conditions error: {e}")
        return None


async def health_check() -> bool:
    """
    Health check for NOAA Weather service
    
    Returns:
        True if service is accessible
    """
    try:
        async with httpx.AsyncClient() as client:
            # Check if API is reachable
            response = await client.get(BASE_URL, headers=noaa_headers(), timeout=5.0)
            return response.status_code in [200, 301, 302, 404]  # API root may redirect or 404
    except Exception as e:
        print(f"[NOAA] health_check failed: {e}")
        return False

