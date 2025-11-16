/**
 * Test script to see what MusicBrainz returns
 * Run: node test-musicbrainz.js
 */

import { getMusicBrainzDataEnhanced } from './src/services/musicbrainz.enhanced.js';

async function testTrack(title, artist) {
  console.log(`\n${'='.repeat(80)}`);
  console.log(`Testing: "${title}" by ${artist}`);
  console.log('='.repeat(80));
  
  const data = await getMusicBrainzDataEnhanced(title, artist);
  
  if (!data) {
    console.log('❌ No data found');
    return;
  }
  
  console.log('\n📀 RECORDING DATA:');
  console.log(`   Title: ${data.recording.title}`);
  console.log(`   Duration: ${data.recording.lengthFormatted} (${data.recording.length}ms)`);
  console.log(`   ISRCs: ${data.recording.isrcs.join(', ') || 'None'}`);
  console.log(`   Tags: ${data.recording.tags?.map(t => `${t.name} (${t.count})`).join(', ') || 'None'}`);
  
  console.log('\n🔗 RELATIONSHIPS:');
  if (data.recording.relationships) {
    const rels = data.recording.relationships;
    console.log(`   Is Cover: ${rels.isCover ? 'YES' : 'NO'}`);
    if (rels.coverOf) {
      console.log(`   Cover Of: "${rels.coverOf.title}" by ${rels.coverOf.originalArtist || 'Unknown'}`);
    }
    console.log(`   Samples: ${rels.samples?.length || 0} tracks`);
    console.log(`   Remixes: ${rels.remixes?.length || 0} tracks`);
  }
  
  console.log('\n🎸 ARTIST DATA:');
  if (data.artist) {
    console.log(`   Name: ${data.artist.name}`);
    console.log(`   Type: ${data.artist.type || 'Unknown'}`);
    console.log(`   Country: ${data.artist.country || data.artist.area || 'Unknown'}`);
    if (data.artist.lifeSpan) {
      console.log(`   Active: ${data.artist.lifeSpan.begin || '?'} - ${data.artist.lifeSpan.end || 'present'}`);
    }
    console.log(`   Aliases: ${data.artist.aliases?.map(a => a.name).join(', ') || 'None'}`);
    console.log(`   Tags: ${data.artist.tags?.map(t => `${t.name} (${t.count})`).join(', ') || 'None'}`);
    
    if (data.artist.members && data.artist.members.length > 0) {
      console.log(`   Band Members: ${data.artist.members.length} total`);
      // Show core/current members (those without end dates or recent)
      const currentYear = new Date().getFullYear();
      const currentMembers = data.artist.members.filter(m => 
        !m.end || parseInt(m.end) >= currentYear - 5
      );
      
      const toShow = currentMembers.length > 0 ? currentMembers.slice(0, 8) : data.artist.members.slice(0, 8);
      
      toShow.forEach(m => {
        const instruments = m.attributes?.length > 0 ? ` [${m.attributes.slice(0, 3).join(', ')}]` : '';
        const years = m.begin || m.end ? ` (${m.begin || '?'}-${m.end || 'present'})` : '';
        console.log(`      - ${m.name}${instruments}${years}`);
      });
      
      if (data.artist.members.length > toShow.length) {
        console.log(`      ... and ${data.artist.members.length - toShow.length} more`);
      }
    }
  }
  
  console.log('\n💿 RELEASE INFO:');
  if (data.release) {
    console.log(`   Album: ${data.release.title}`);
    console.log(`   Release Date: ${data.release.date || 'Unknown'}`);
    console.log(`   Country: ${data.release.country || 'Unknown'}`);
    console.log(`   Status: ${data.release.status || 'Unknown'}`);
    
    if (data.release.labelInfo && data.release.labelInfo.length > 0) {
      const label = data.release.labelInfo[0];
      console.log(`   Label: ${label.label?.name || 'Unknown'}`);
      console.log(`   Catalog #: ${label.catalogNumber || 'None'}`);
    }
    
    console.log(`   Barcode: ${data.release.barcode || 'None'}`);
    console.log(`   Track Count: ${data.release.trackCount || '?'}`);
  }
  
  console.log('\n🏆 RELEASE GROUP (ALBUM TYPE):');
  if (data.releaseGroup) {
    console.log(`   Title: ${data.releaseGroup.title}`);
    console.log(`   Type: ${data.releaseGroup.primaryType || 'Unknown'}`);
    console.log(`   Secondary Types: ${data.releaseGroup.secondaryTypes?.join(', ') || 'None'}`);
    console.log(`   First Release: ${data.releaseGroup.firstReleaseDate || 'Unknown'}`);
    console.log(`   Tags: ${data.releaseGroup.tags?.map(t => `${t.name} (${t.count})`).join(', ') || 'None'}`);
  }
  
  console.log('\n📊 METADATA:');
  if (data.metadata) {
    console.log(`   Recording MBID: ${data.metadata.recordingMbid || 'N/A'}`);
    console.log(`   Artist MBID: ${data.metadata.artistMbid || 'N/A'}`);
    console.log(`   Release Group MBID: ${data.metadata.releaseGroupMbid || 'N/A'}`);
  } else {
    console.log(`   No metadata available`);
  }
}

// Test the Big 4
async function runTests() {
  try {
    await testTrack('Hurt', 'Nine Inch Nails');
    await testTrack('Hurt', 'Johnny Cash');
    await testTrack('Queer', 'Garbage');
    await testTrack('Euro-Trash Girl', 'Cracker');
    
    console.log('\n\n' + '='.repeat(80));
    console.log('✅ ALL TESTS COMPLETE');
    console.log('='.repeat(80));
  } catch (error) {
    console.error('\n❌ ERROR:', error.message);
    console.error(error.stack);
  }
}

runTests();
