"""
Test Information APIs
=====================
Quick test script to verify Wikipedia and MusicBrainz lookups work.
"""

import asyncio
import aiohttp


async def test_tools():
    base_url = "http://localhost:8000"
    
    print("🧪 Testing AI Hub Information APIs")
    print("=" * 60)
    
    async with aiohttp.ClientSession() as session:
        
        # Test 1: Wikipedia lookup
        print("\n1️⃣ Testing Wikipedia lookup...")
        try:
            async with session.post(
                f"{base_url}/api/tools/wikipedia/search",
                json={
                    "query": "Pink Floyd",
                    "sentences": 2
                }
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ Wikipedia: {data['title']}")
                    print(f"   Summary: {data['summary'][:100]}...")
                    print(f"   URL: {data['url']}")
                else:
                    print(f"❌ Failed: {response.status}")
        except Exception as e:
            print(f"❌ Error: {e}")
        
        # Test 2: MusicBrainz lookup
        print("\n2️⃣ Testing MusicBrainz lookup...")
        try:
            async with session.post(
                f"{base_url}/api/tools/musicbrainz/lookup",
                json={
                    "artist": "Led Zeppelin",
                    "album": "Houses of the Holy"
                }
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ MusicBrainz:")
                    print(f"   Artist: {data.get('artist')}")
                    print(f"   Album: {data.get('album')}")
                    print(f"   Year: {data.get('year')}")
                    print(f"   Genres: {data.get('genre')}")
                else:
                    print(f"❌ Failed: {response.status}")
        except Exception as e:
            print(f"❌ Error: {e}")
        
        # Test 3: Genre normalization
        print("\n3️⃣ Testing genre normalization...")
        try:
            test_genres = ["alt-rock", "hip-hop", "metal", "indie"]
            for genre in test_genres:
                async with session.get(
                    f"{base_url}/api/tools/genres/normalize",
                    params={"genre": genre}
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        print(f"✅ '{genre}' → {data['normalized']} ({data['category']})")
                    else:
                        print(f"❌ Failed for '{genre}': {response.status}")
        except Exception as e:
            print(f"❌ Error: {e}")
    
    print("\n" + "=" * 60)
    print("✅ Testing complete!")


if __name__ == "__main__":
    print("Make sure AI Hub is running on http://localhost:8000")
    print("Start it with: python run.py")
    print()
    asyncio.run(test_tools())
