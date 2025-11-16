// Test music knowledge enrichment
import { enrichMusicQuery, isMusicQuery } from "./src/services/musicKnowledge.js";

console.log("=== Testing Music Knowledge Enrichment ===\n");

const testQueries = [
  { message: "who is mike jones?", metadata: {} },
  { message: "tell me about deftones", metadata: {} },
  { message: "who are run the jewels?", metadata: {} },
  {
    message: "tell me about this song",
    metadata: {
      now_playing: {
        artist: "Massive Attack",
        title: "Teardrop",
        album: "Mezzanine",
        year: 1998
      }
    }
  }
];

async function runTests() {
  for (const test of testQueries) {
    console.log(`\n📝 Query: "${test.message}"`);
    console.log(`   Is music query: ${isMusicQuery(test.message)}`);

    if (isMusicQuery(test.message)) {
      try {
        const enriched = await enrichMusicQuery(test.message, test.metadata);

        if (enriched) {
          console.log(`   ✓ Found ${enriched.factCount} fact(s)`);
          console.log(`   Entities:`, enriched.entities);
          console.log(`\n   Facts:\n${enriched.factsText}\n`);
        } else {
          console.log(`   ✗ No facts found`);
        }
      } catch (error) {
        console.log(`   ✗ Error: ${error.message}`);
      }
    }

    // Add delay between queries to respect rate limits
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }

  console.log("\n=== Test Complete ===");
  console.log("\nThe bot should now be able to answer artist questions with real data!");
  console.log("Try asking: 'who is mike jones bot?' in the room\n");
}

runTests().then(() => process.exit(0)).catch(err => {
  console.error("Test failed:", err);
  process.exit(1);
});
