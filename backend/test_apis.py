"""
Quick test script for all API endpoints
Run with: python test_apis.py
"""

import asyncio
import httpx

BASE_URL = "http://localhost:8000"
API_KEY = "dev-test-key-123"
HEADERS = {"X-API-Key": API_KEY}


async def test_weather():
    """Test NOAA Weather API"""
    print("\n🌤️  Testing NOAA Weather...")
    try:
        async with httpx.AsyncClient() as client:
            # New York City
            response = await client.get(
                f"{BASE_URL}/api/weather/forecast?lat=40.7&lon=-74.0",
                headers=HEADERS,
                timeout=15.0
            )
            print(f"   Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"   ✅ Forecast data received: {len(data.get('data', {}).get('properties', {}).get('periods', []))} periods")
            else:
                print(f"   ❌ Error: {response.text[:100]}")
    except Exception as e:
        print(f"   ❌ Exception: {e}")


async def test_tv():
    """Test TVmaze API"""
    print("\n📺 Testing TVmaze...")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{BASE_URL}/api/tv/search?q=breaking+bad",
                headers=HEADERS,
                timeout=15.0
            )
            print(f"   Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                shows = data.get('data', [])
                print(f"   ✅ Found {len(shows)} shows")
                if shows:
                    print(f"   First result: {shows[0].get('show', {}).get('name', 'N/A')}")
            else:
                print(f"   ❌ Error: {response.text[:100]}")
    except Exception as e:
        print(f"   ❌ Exception: {e}")


async def test_countries():
    """Test REST Countries API"""
    print("\n🌍 Testing REST Countries...")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{BASE_URL}/api/countries/search?name=canada",
                headers=HEADERS,
                timeout=15.0
            )
            print(f"   Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                country = data.get('data', {})
                name = country.get('name', {}).get('common', 'N/A')
                capital = country.get('capital', ['N/A'])[0] if country.get('capital') else 'N/A'
                print(f"   ✅ Country: {name}, Capital: {capital}")
            else:
                print(f"   ❌ Error: {response.text[:100]}")
    except Exception as e:
        print(f"   ❌ Exception: {e}")


async def test_books():
    """Test Open Library API"""
    print("\n📚 Testing Open Library...")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{BASE_URL}/api/books/search?q=tolkien&limit=3",
                headers=HEADERS,
                timeout=15.0
            )
            print(f"   Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                books = data.get('data', [])
                print(f"   ✅ Found {len(books)} books")
                if books:
                    print(f"   First result: {books[0].get('title', 'N/A')}")
            else:
                print(f"   ❌ Error: {response.text[:100]}")
    except Exception as e:
        print(f"   ❌ Exception: {e}")


async def test_trivia():
    """Test Open Trivia DB API"""
    print("\n🎯 Testing Open Trivia DB...")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{BASE_URL}/api/trivia/questions?amount=3",
                headers=HEADERS,
                timeout=15.0
            )
            print(f"   Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                questions = data.get('data', {}).get('results', [])
                print(f"   ✅ Got {len(questions)} questions")
                if questions:
                    print(f"   First question: {questions[0].get('question', 'N/A')[:50]}...")
            else:
                print(f"   ❌ Error: {response.text[:100]}")
    except Exception as e:
        print(f"   ❌ Exception: {e}")


async def test_health():
    """Test health check"""
    print("\n❤️  Testing Health Check...")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{BASE_URL}/api/health",
                timeout=5.0
            )
            print(f"   Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"   ✅ Backend is healthy")
                services = data.get('providers', {})
                for name, status in services.items():
                    print(f"      {name}: {status}")
            else:
                print(f"   ❌ Error: {response.text[:100]}")
    except Exception as e:
        print(f"   ❌ Exception: {e}")


async def main():
    print("=" * 60)
    print("🚀 AI Hub API Test Suite")
    print("=" * 60)
    
    await test_health()
    await test_weather()
    await test_tv()
    await test_countries()
    await test_books()
    await test_trivia()
    
    print("\n" + "=" * 60)
    print("✅ Test suite complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())

