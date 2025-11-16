// test-enhanced.js
// Test script for the enhanced track enrichment API

import { getSongInfo, getAlbumInfo, getArtistInfo } from './src/services/wikipedia.js';

const testCases = [
  {
    name: 'Cracker - Eurotrash Girl',
    title: 'Eurotrash Girl',
    artist: 'Cracker',
    expectedAlbum: 'Kerosene Hat',
    expectedGenres: ['Alternative Country', 'Alternative Rock'],
    expectLength: true
  },
  {
    name: 'Garbage - Queer',
    title: 'Queer',
    artist: 'Garbage',
    expectedAlbum: 'Garbage',
    expectedReleased: '1995',
    expectedGenres: ['Alternative Rock', 'Grunge'],
    expectLength: true
  },
  {
    name: 'Johnny Cash - Hurt (cover)',
    title: 'Hurt',
    artist: 'Johnny Cash',
    expectedAlbum: 'American IV: The Man Comes Around',
    expectedReleased: '2002',
    expectedCover: true,
    expectedOriginalArtist: 'Nine Inch Nails'
  },
  {
    name: 'Nine Inch Nails - Hurt (original)',
    title: 'Hurt',
    artist: 'Nine Inch Nails',
    expectedAlbum: 'The Downward Spiral',
    expectedGenres: ['Industrial Rock'],
    expectLength: true
  },
  {
    name: 'Queen - Bohemian Rhapsody',
    title: 'Bohemian Rhapsody',
    artist: 'Queen',
    expectedAlbum: 'A Night at the Opera',
    expectGenres: true,
    expectSummary: true
  },
  {
    name: 'Metallica - Hero of the Day',
    title: 'Hero of the Day',
    artist: 'Metallica',
    expectAlbum: true,
    expectGenres: true,
    expectSummary: true
  }
];

async function runTests() {
  console.log('╔════════════════════════════════════════════════════════════╗');
  console.log('║  Enhanced Track Enrichment API - Test Suite               ║');
  console.log('╚════════════════════════════════════════════════════════════╝\n');
  
  let passed = 0;
  let failed = 0;
  
  for (const testCase of testCases) {
    console.log(`\n${'═'.repeat(60)}`);
    console.log(`TEST: ${testCase.name}`);
    console.log(`${'═'.repeat(60)}`);
    
    try {
      const result = await getSongInfo(testCase.title, testCase.artist);
      
      if (!result) {
        console.log(`❌ FAILED: No result returned for ${testCase.name}`);
        failed++;
        continue;
      }
      
      console.log('\n📊 RESULTS:');
      console.log(`   Title: ${result.title}`);
      console.log(`   Artist: ${result.artist}`);
      console.log(`   Album: ${result.album || 'Unknown'}`);
      console.log(`   Released: ${result.released || 'Unknown'}`);
      console.log(`   Length: ${result.length || 'Unknown'}`);
      console.log(`   Genres (Original): ${result.genresOriginal || 'Unknown'}`);
      console.log(`   Genres (Normalized): ${result.genresNormalized.join(', ') || 'Unknown'}`);
      console.log(`   Genres (Combined): ${result.genreCombined || 'Unknown'}`);
      console.log(`   Cover: ${result.isCover ? 'Yes' : 'No'}`);
      if (result.isCover) {
        console.log(`   Original Artist: ${result.coverOriginalArtist || 'Unknown'}`);
        console.log(`   Cover Year: ${result.coverYear || 'Unknown'}`);
        console.log(`   Original Release Year: ${result.originalReleaseYear || 'Unknown'}`);
      }
      
      // Validate expectations
      let testPassed = true;
      const errors = [];
      
      if (testCase.expectedAlbum && result.album !== testCase.expectedAlbum) {
        errors.push(`Expected album "${testCase.expectedAlbum}", got "${result.album}"`);
        testPassed = false;
      }
      
      if (testCase.expectedReleased && result.released !== testCase.expectedReleased) {
        errors.push(`Expected released "${testCase.expectedReleased}", got "${result.released}"`);
        testPassed = false;
      }
      
      if (testCase.expectLength && !result.length) {
        errors.push('Expected length to be present');
        testPassed = false;
      }
      
      if (testCase.expectAlbum && !result.album) {
        errors.push('Expected album to be present');
        testPassed = false;
      }
      
      if (testCase.expectGenres && !result.genreCombined) {
        errors.push('Expected genres to be present');
        testPassed = false;
      }
      
      if (testCase.expectSummary && !result.summary) {
        errors.push('Expected summary to be present');
        testPassed = false;
      }
      
      if (testCase.expectedCover && !result.isCover) {
        errors.push('Expected to be marked as cover');
        testPassed = false;
      }
      
      if (testCase.expectedOriginalArtist) {
        const originalArtistMatch = result.coverOriginalArtist?.toLowerCase().includes(testCase.expectedOriginalArtist.toLowerCase());
        if (!originalArtistMatch) {
          errors.push(`Expected original artist to include "${testCase.expectedOriginalArtist}", got "${result.coverOriginalArtist}"`);
          testPassed = false;
        }
      }
      
      // Check that genres don't have pipes or concatenated tokens
      if (result.genresOriginal && result.genresOriginal.includes('|')) {
        errors.push('Genres contain pipe characters - should be split properly');
        testPassed = false;
      }
      
      // Check for "Unknown" in critical fields
      if (result.album === 'Unknown' || !result.album) {
        errors.push('Album is "Unknown" or missing');
        testPassed = false;
      }
      
      console.log('\n🔍 VALIDATION:');
      if (testPassed) {
        console.log('   ✅ All checks passed');
        passed++;
      } else {
        console.log('   ❌ Some checks failed:');
        errors.forEach(err => console.log(`      - ${err}`));
        failed++;
      }
      
      // Fetch artist info for additional validation
      console.log('\n👤 ARTIST INFO:');
      const artistInfo = await getArtistInfo(testCase.artist);
      if (artistInfo) {
        console.log(`   Summary: ${artistInfo.summary?.substring(0, 100)}...`);
        console.log(`   Genres: ${artistInfo.genres || 'Unknown'}`);
        
        // Validate artist page resolution (e.g., Garbage should be band, not trash)
        if (testCase.artist === 'Garbage') {
          if (!artistInfo.summary?.toLowerCase().includes('band')) {
            console.log('   ❌ WARNING: Artist summary does not mention "band" - may be wrong page');
          } else {
            console.log('   ✅ Artist correctly resolved to band page');
          }
        }
      } else {
        console.log('   ⚠️  No artist info found');
      }
      
      // Fetch album info if album is present
      if (result.album && result.album !== 'Unknown') {
        console.log('\n💿 ALBUM INFO:');
        const albumInfo = await getAlbumInfo(result.album, testCase.artist);
        if (albumInfo) {
          console.log(`   Title: ${albumInfo.title}`);
          console.log(`   Released: ${albumInfo.released || 'Unknown'}`);
          console.log(`   Genres (Original Array): ${albumInfo.genresOriginalArray.join(', ') || 'Unknown'}`);
          console.log(`   Genres (Selected): ${albumInfo.genresSelected.join(', ') || 'Unknown'}`);
          
          // Check that album genres are properly split (no pipes)
          const hasPipes = albumInfo.genresOriginalArray.some(g => g.includes('|'));
          if (hasPipes) {
            console.log('   ❌ WARNING: Album genres contain pipes - should be split');
          } else {
            console.log('   ✅ Album genres properly split');
          }
        } else {
          console.log('   ⚠️  No album info found');
        }
      }
      
    } catch (error) {
      console.log(`❌ FAILED with error: ${error.message}`);
      console.error(error);
      failed++;
    }
  }
  
  console.log('\n\n╔════════════════════════════════════════════════════════════╗');
  console.log('║  TEST SUMMARY                                              ║');
  console.log('╚════════════════════════════════════════════════════════════╝');
  console.log(`   Total Tests: ${testCases.length}`);
  console.log(`   ✅ Passed: ${passed}`);
  console.log(`   ❌ Failed: ${failed}`);
  console.log(`   Success Rate: ${((passed / testCases.length) * 100).toFixed(1)}%\n`);
  
  if (failed === 0) {
    console.log('🎉 All tests passed! The implementation meets the specification.\n');
  } else {
    console.log('⚠️  Some tests failed. Review the output above for details.\n');
  }
}

runTests().catch(console.error);
