"""
Test multi-source enrichment with context awareness.

This demonstrates the MusicBrainz-first approach with context-aware enrichment:
- Artist queries → Full artist profile
- Album queries → Album details with tracklist
- Track queries → Track info with releases
"""

import asyncio
import json
import sys
import os

# Add python_enrichment directory to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
python_enrichment_path = os.path.join(project_root, "python_enrichment")
sys.path.insert(0, python_enrichment_path)

from providers.multi_source_orchestrator import (
    enrich_artist_multi_source,
    enrich_album_multi_source,
    enrich_track_multi_source,
    enrich_music_entity,
)


def print_section(title: str):
    """Print formatted section header."""
    print(f"\n{'='*80}")
    print(f"  {title}")
    print(f"{'='*80}\n")


def print_result(result: dict):
    """Print enrichment result in readable format."""
    if not result:
        print("❌ No results found\n")
        return

    print("✅ SUCCESS!\n")

    # Basic info
    print(f"Type: {result.get('type', 'unknown').upper()}")
    print(f"Name/Title: {result.get('name') or result.get('title')}")

    # IDs
    print(f"\n🆔 Canonical IDs:")
    for id_type, id_value in result.get('ids', {}).items():
        print(f"  {id_type}: {id_value}")

    # URLs
    urls = result.get('urls', {})
    if urls:
        print(f"\n🔗 URLs ({len(urls)} sources):")
        priority = ['musicbrainz', 'wikipedia', 'wikidata', 'spotify', 'discogs', 'allmusic', 'official']
        for url_type in priority:
            if url_type in urls:
                print(f"  {url_type}: {urls[url_type]}")
        # Print remaining URLs
        for url_type, url in urls.items():
            if url_type not in priority:
                print(f"  {url_type}: {url}")

    # Facts
    facts = result.get('facts', [])
    if facts:
        print(f"\n📖 Facts ({len(facts)}):")
        for i, fact in enumerate(facts, 1):
            # Truncate long facts
            fact_preview = fact[:250] + "..." if len(fact) > 250 else fact
            print(f"  {i}. {fact_preview}")

    # Metadata
    metadata = result.get('metadata', {})
    if metadata:
        print(f"\n📊 Metadata:")
        for key, value in metadata.items():
            if isinstance(value, (list, dict)):
                if isinstance(value, list) and value:
                    print(f"  {key}: {len(value)} items")
                elif isinstance(value, dict) and value:
                    print(f"  {key}: {len(value)} items")
            elif value:
                print(f"  {key}: {value}")

    # Context-specific data
    if result.get('type') == 'artist':
        discog = result.get('discography', {})
        if discog.get('albums'):
            print(f"\n💿 Albums ({len(discog['albums'])}):")
            for album in discog['albums'][:5]:
                print(f"  - {album['title']} ({album.get('year', 'Unknown year')})")
            if len(discog['albums']) > 5:
                print(f"  ... and {len(discog['albums']) - 5} more")

    elif result.get('type') == 'album':
        tracklist = result.get('tracklist', [])
        if tracklist:
            print(f"\n🎵 Tracklist ({len(tracklist)} tracks):")
            for track in tracklist[:10]:
                pos = track.get('position', '?')
                title = track.get('title', 'Unknown')
                length = track.get('length', '')
                length_str = f"({length})" if length else ""
                print(f"  {pos}. {title} {length_str}")
            if len(tracklist) > 10:
                print(f"  ... and {len(tracklist) - 10} more tracks")

    elif result.get('type') == 'track':
        releases = metadata.get('releases', [])
        if releases:
            print(f"\n💿 Appears on {len(releases)} releases:")
            for release in releases[:3]:
                title = release['title']
                date = release.get('date', '')
                year_str = f"({date[:4]})" if date else ""
                print(f"  - {title} {year_str}")

    # Sources
    sources = result.get('sources', [])
    if sources:
        print(f"\n🔍 Data sources ({len(sources)}):")
        for source in sources:
            provider = source.get('provider', 'unknown')
            sections = source.get('sections', [])
            print(f"  - {provider}: {', '.join(sections)}")

    print()


async def test_artist():
    """Test artist enrichment."""
    print_section("🎤 ARTIST ENRICHMENT: Radiohead")

    result = await enrich_artist_multi_source("Radiohead", trace_id="test-artist-001")
    print_result(result)

    # Save to JSON
    if result:
        with open("test_artist_radiohead.json", "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print("💾 Full result saved to test_artist_radiohead.json")


async def test_album():
    """Test album enrichment."""
    print_section("💿 ALBUM ENRICHMENT: OK Computer by Radiohead")

    result = await enrich_album_multi_source("OK Computer", "Radiohead", trace_id="test-album-001")
    print_result(result)

    # Save to JSON
    if result:
        with open("test_album_ok_computer.json", "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print("💾 Full result saved to test_album_ok_computer.json")


async def test_track():
    """Test track enrichment."""
    print_section("🎵 TRACK ENRICHMENT: Karma Police by Radiohead")

    result = await enrich_track_multi_source("Karma Police", "Radiohead", trace_id="test-track-001")
    print_result(result)

    # Save to JSON
    if result:
        with open("test_track_karma_police.json", "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print("💾 Full result saved to test_track_karma_police.json")


async def test_auto_detection():
    """Test automatic entity type detection."""
    print_section("🤖 AUTO-DETECTION: Multiple query types")

    test_queries = [
        ("who is wet leg?", "auto", "Wet Leg", None),
        ("tell me about the album Wet Leg", "auto", "Wet Leg", "Wet Leg"),
        ("what is the song chaise longue about?", "auto", "Chaise Longue", "Wet Leg"),
    ]

    for query_text, entity_type, entity_name, artist_name in test_queries:
        print(f"\n📝 Query: \"{query_text}\"")
        print(f"   Entity: {entity_name} (type: {entity_type}, artist: {artist_name or 'N/A'})")

        result = await enrich_music_entity(
            query_text=query_text,
            entity_type=entity_type,
            entity_name=entity_name,
            artist_name=artist_name,
            trace_id=f"test-auto-{hash(query_text)}"
        )

        if result:
            print(f"   ✅ Detected as: {result.get('type', 'unknown')}")
            print(f"   📊 Found {len(result.get('facts', []))} facts from {len(result.get('sources', []))} sources")
        else:
            print("   ❌ No results")

        await asyncio.sleep(1.5)  # Rate limiting


async def main():
    """Run all tests."""
    print("""
╔════════════════════════════════════════════════════════════════════════════╗
║                                                                            ║
║            🎵 MULTI-SOURCE MUSIC ENRICHMENT TEST SUITE 🎵                 ║
║                                                                            ║
║  MusicBrainz (canonical) → Wikipedia → Wikidata → [Future: More sources] ║
║                                                                            ║
╚════════════════════════════════════════════════════════════════════════════╝
    """)

    try:
        # Test 1: Artist enrichment
        await test_artist()
        await asyncio.sleep(2)

        # Test 2: Album enrichment
        await test_album()
        await asyncio.sleep(2)

        # Test 3: Track enrichment
        await test_track()
        await asyncio.sleep(2)

        # Test 4: Auto-detection
        await test_auto_detection()

    except Exception as e:
        print(f"\n❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()

    print(f"\n{'='*80}")
    print("✅ Test suite complete!")
    print("📁 Check JSON files for full results")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    asyncio.run(main())
