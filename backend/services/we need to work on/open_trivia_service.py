"""
Open Trivia Database API Service
Provides trivia questions across multiple categories and difficulties
No authentication required - community-driven, CC BY-SA licensed
Rate limit: 1 request per 5 seconds
"""

import asyncio
from typing import Optional, Dict, List, Any
import httpx
import time

# Base URL
BASE_URL = "https://opentdb.com"

# In-memory cache
_categories_cache: Optional[List[Dict]] = None
_last_request_time: float = 0
_rate_limit_seconds: float = 5.0  # API allows 1 request per 5 seconds


async def _rate_limit_wait():
    """Enforce rate limit: 1 request per 5 seconds"""
    global _last_request_time
    current_time = time.time()
    time_since_last = current_time - _last_request_time
    
    if time_since_last < _rate_limit_seconds:
        wait_time = _rate_limit_seconds - time_since_last
        await asyncio.sleep(wait_time)
    
    _last_request_time = time.time()


async def get_questions(
    amount: int = 10, 
    category: int = None, 
    difficulty: str = None, 
    qtype: str = "multiple"
) -> Dict[str, Any]:
    """
    Get trivia questions
    
    Args:
        amount: Number of questions (1-50)
        category: Category ID (optional)
        difficulty: "easy", "medium", or "hard" (optional)
        qtype: "multiple" or "boolean" (optional)
        
    Returns:
        Dictionary with response_code and results
    """
    await _rate_limit_wait()
    
    # Limit amount to max 50
    amount = min(amount, 50)
    
    url = f"{BASE_URL}/api.php?amount={amount}"
    
    if category is not None:
        url += f"&category={category}"
    
    if difficulty:
        url += f"&difficulty={difficulty.lower()}"
    
    if qtype:
        url += f"&type={qtype}"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=10.0)
            if response.status_code != 200:
                print(f"[OPEN_TRIVIA] get_questions non-200 response: {response.status_code}")
                return {"response_code": -1, "results": []}
            data = response.json()
            return data
    except Exception as e:
        print(f"[OPEN_TRIVIA] get_questions error: {e}")
        return {"response_code": -1, "results": []}


async def get_categories() -> List[Dict[str, Any]]:
    """
    Get list of available trivia categories
    
    Returns:
        List of categories with ID and name
    """
    global _categories_cache
    
    # Return cached if available
    if _categories_cache is not None:
        return _categories_cache
    
    await _rate_limit_wait()
    
    url = f"{BASE_URL}/api_category.php"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=10.0)
            if response.status_code != 200:
                print(f"[OPEN_TRIVIA] get_categories non-200 response: {response.status_code}")
                return []
            data = response.json()
            categories = data.get('trivia_categories', [])
            _categories_cache = categories
            return categories
    except Exception as e:
        print(f"[OPEN_TRIVIA] get_categories error: {e}")
        return []


async def get_question_count(category: int = None) -> Dict[str, Any]:
    """
    Get count of questions available
    
    Args:
        category: Category ID (optional, if None returns global count)
        
    Returns:
        Dictionary with question counts by difficulty
    """
    await _rate_limit_wait()
    
    url = f"{BASE_URL}/api_count.php"
    if category is not None:
        url += f"?category={category}"
    else:
        url = f"{BASE_URL}/api_count_global.php"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=10.0)
            if response.status_code != 200:
                print(f"[OPEN_TRIVIA] get_question_count non-200 response: {response.status_code}")
                return {}
            data = response.json()
            return data
    except Exception as e:
        print(f"[OPEN_TRIVIA] get_question_count error: {e}")
        return {}


async def get_category_by_name(name: str) -> Optional[Dict[str, Any]]:
    """
    Find category by name (helper function)
    
    Args:
        name: Category name (case-insensitive)
        
    Returns:
        Category dict with id and name, or None
    """
    categories = await get_categories()
    name_lower = name.lower()
    
    for category in categories:
        if name_lower in category.get('name', '').lower():
            return category
    
    return None


async def get_random_questions(amount: int = 10) -> Dict[str, Any]:
    """
    Get random trivia questions (any category, any difficulty)
    
    Args:
        amount: Number of questions (1-50)
        
    Returns:
        Dictionary with response_code and results
    """
    return await get_questions(amount=amount)


async def get_questions_by_difficulty(difficulty: str, amount: int = 10) -> Dict[str, Any]:
    """
    Get trivia questions of specific difficulty
    
    Args:
        difficulty: "easy", "medium", or "hard"
        amount: Number of questions (1-50)
        
    Returns:
        Dictionary with response_code and results
    """
    return await get_questions(amount=amount, difficulty=difficulty)


async def get_true_false_questions(amount: int = 10, category: int = None) -> Dict[str, Any]:
    """
    Get true/false questions
    
    Args:
        amount: Number of questions (1-50)
        category: Category ID (optional)
        
    Returns:
        Dictionary with response_code and results
    """
    return await get_questions(amount=amount, category=category, qtype="boolean")


async def health_check() -> bool:
    """
    Health check for Open Trivia DB service
    
    Returns:
        True if service is accessible
    """
    try:
        await _rate_limit_wait()
        async with httpx.AsyncClient() as client:
            # Try getting one random question
            response = await client.get(f"{BASE_URL}/api.php?amount=1", timeout=5.0)
            if response.status_code == 200:
                data = response.json()
                # response_code 0 means success
                return data.get('response_code') == 0
            return False
    except Exception as e:
        print(f"[OPEN_TRIVIA] health_check failed: {e}")
        return False

