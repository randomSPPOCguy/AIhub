"""Test script for the enhanced music enrichment pipeline."""

import asyncio
import json
import sys
import os

# Add python_enrichment directory to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
python_enrichment_path = os.path.join(project_root, "python_enrichment")
sys.path.insert(0, python_enrichment_path)

from providers.music_orchestrator import enrich_artist_complete


async def test_artist(artist_name: str):
    """Test enrichment for a specific artist."""
    print(f"\n{'='*70}")
    print(f"Testing: {artist_name}")
    print(f"{'='*70}\n")

    result = await enrich_artist_complete(artist_name, trace_id="test-001")

    if result:
        print("✅ SUCCESS!\n")

        print(f"Name: {result.get('name')}")
        print(f"MBID: {result.get('mbid')}")
        print(f"Wikidata ID: {result.get('wikidata_id')}")
        print(f"Album Count: {result.get('album_count')}")

        print(f"\n📚 URLs:")
        for key, url in result.get('urls', {}).items():
            print(f"  {key}: {url}")

        print(f"\n📖 Facts ({len(result.get('facts', []))}):")
        for i, fact in enumerate(result.get('facts', []), 1):
            # Truncate long facts
            fact_preview = fact[:200] + "..." if len(fact) > 200 else fact
            print(f"  {i}. {fact_preview}")

        print(f"\n💿 Albums from MusicBrainz ({len(result.get('albums_from_mb', []))}):")
        for album in result.get('albums_from_mb', [])[:5]:
            title = album.get('title', 'Unknown')
            date = album.get('date', 'Unknown date')
            print(f"  - {title} ({date})")

        if result.get('albums_from_wikipedia'):
            print(f"\n💿 Albums from Wikipedia ({len(result.get('albums_from_wikipedia', []))}):")
            for album in result.get('albums_from_wikipedia', [])[:5]:
                title = album.get('title', 'Unknown')
                year = album.get('year', 'Unknown')
                print(f"  - {title} ({year})")

        print(f"\n📊 Sources ({len(result.get('sources', []))}):")
        for source in result.get('sources', []):
            provider = source.get('provider', 'unknown')
            section = source.get('section', '')
            print(f"  - {provider} ({section})")

        # Save full result to JSON
        with open(f"test_result_{artist_name.replace(' ', '_').lower()}.json", 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"\n💾 Full result saved to test_result_{artist_name.replace(' ', '_').lower()}.json")

    else:
        print("❌ FAILED - No results found")


async def main():
    """Run tests for multiple artists."""
    test_artists = [
        "Radiohead",
        "Wet Leg",
        "Nirvana",
        "Taylor Swift",
        "The Beatles",
    ]

    for artist in test_artists:
        try:
            await test_artist(artist)
            await asyncio.sleep(2)  # Rate limiting between tests
        except Exception as e:
            print(f"❌ Error testing {artist}: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    print("""
╔════════════════════════════════════════════════════════════════╗
║                                                                ║
║   🎵 Enhanced Music Enrichment Pipeline Test                  ║
║   ──────────────────────────────────────────────────────      ║
║   MusicBrainz → Wikidata → Wikipedia → Discography            ║
║                                                                ║
╚════════════════════════════════════════════════════════════════╝
    """)

    asyncio.run(main())

    print(f"\n{'='*70}")
    print("✅ All tests complete!")
    print("Check the JSON files for full results.")
    print(f"{'='*70}\n")
