"""
Quick test script for the new enrichers and formatters.
Tests with Radiohead (MBID: a74b1b7f-71a5-4011-9441-d0b5e4122711)
"""

import asyncio
import sys
import os
import io

# Fix Windows console encoding issues
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Add python_enrichment directory to path (two levels up from tests/python_enrichment)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
python_enrichment_path = os.path.join(project_root, "python_enrichment")
sys.path.insert(0, python_enrichment_path)

from enrichers.band_members_enricher import enrich_band_members
from enrichers.album_credits_enricher import enrich_album_credits
from formatters.music_response_formatter import format_artist_response, format_album_response


async def test_band_members():
    """Test band members enricher with Radiohead."""
    print("=" * 60)
    print("Testing Band Members Enricher (Radiohead)")
    print("=" * 60)
    
    radiohead_mbid = "a74b1b7f-71a5-4011-9441-d0b5e4122711"
    
    result = await enrich_band_members(radiohead_mbid, trace_id="test-001")
    
    if result:
        print(f"\n[OK] Success! Found {result.get('member_count', 0)} current members")
        print(f"\nArtist: {result.get('name', 'N/A')}")
        print(f"Type: {result.get('type', 'N/A')}")
        print(f"Formation: {result.get('formation', 'N/A')}")
        
        print("\nCurrent Members:")
        for member in result.get("current_members", [])[:5]:
            name = member.get("name", "N/A")
            role = member.get("role", "member")
            since = member.get("since", "")
            print(f"  - {name} ({role})" + (f" since {since}" if since else ""))
        
        if result.get("past_members"):
            print("\nPast Members:")
            for member in result.get("past_members", [])[:3]:
                name = member.get("name", "N/A")
                period = member.get("period", "")
                print(f"  - {name} ({period})")
    else:
        print("\n[ERROR] Failed to get band members")
    
    print("\n")


async def test_album_credits():
    """Test album credits enricher with OK Computer."""
    print("=" * 60)
    print("Testing Album Credits Enricher (OK Computer)")
    print("=" * 60)
    
    # Search for OK Computer release first
    from providers.musicbrainz_complete import set_trace_id, search_release
    set_trace_id("test-002")
    
    release_data = await search_release("OK Computer", artist="Radiohead")
    if not release_data:
        print("\n[ERROR] Failed to find OK Computer release")
        return
    
    ok_computer_mbid = release_data.get("mbid")
    print(f"\nFound release: {release_data.get('title', 'N/A')} (MBID: {ok_computer_mbid})")
    
    result = await enrich_album_credits(ok_computer_mbid, trace_id="test-002")
    
    if result:
        print(f"\n[OK] Success! Retrieved credits for {result.get('title', 'N/A')}")
        
        producers = result.get("producers", [])
        if producers:
            print(f"\nProducers: {', '.join(producers)}")
        
        engineers = result.get("engineers", [])
        if engineers:
            print(f"Engineers: {', '.join(engineers)}")
        
        studios = result.get("studios", [])
        if studios:
            print(f"Studios: {', '.join(studios)}")
        
        cover_art = result.get("cover_art")
        if cover_art:
            print("\nCover Art:")
            if cover_art.get("front"):
                print(f"  Front: {cover_art['front']}")
            if cover_art.get("back"):
                print(f"  Back: {cover_art['back']}")
            if cover_art.get("thumbnails"):
                print(f"  Thumbnails: {cover_art['thumbnails']}")
    else:
        print("\n[ERROR] Failed to get album credits")
    
    print("\n")


async def test_formatter():
    """Test formatter with sample data."""
    print("=" * 60)
    print("Testing Music Response Formatter")
    print("=" * 60)
    
    # Sample artist data
    artist_data = {
        "name": "Radiohead",
        "type_name": "Group",
        "country": "GB",
        "active_years": "1991-present",
        "genres": ["alternative rock", "art rock", "electronic", "experimental"],
        "albums": [
            {"title": "OK Computer", "year": "1997", "type": "album"},
            {"title": "Kid A", "year": "2000", "type": "album"},
            {"title": "In Rainbows", "year": "2007", "type": "album"},
        ]
    }
    
    # Get members data
    radiohead_mbid = "a74b1b7f-71a5-4011-9441-d0b5e4122711"
    members_data = await enrich_band_members(radiohead_mbid, trace_id="test-003")
    
    # Format facts
    facts = format_artist_response(artist_data, members_data)
    
    print("\n[OK] Formatted Facts:")
    for i, fact in enumerate(facts, 1):
        print(f"{i}. {fact} ({len(fact)} chars)")
    
    print("\n")


async def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("Testing New Enrichers and Formatters")
    print("=" * 60 + "\n")
    
    try:
        await test_band_members()
        await test_album_credits()
        await test_formatter()
        
        print("=" * 60)
        print("All tests completed!")
        print("=" * 60 + "\n")
        
    except Exception as e:
        print(f"\n[ERROR] Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())

