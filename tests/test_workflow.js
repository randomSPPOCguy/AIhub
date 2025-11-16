// Quick test script to verify the workflow implementation
import { db } from "./src/db/connection.js";
import { getOrCreateUserProfile, upsertUserProfile } from "./src/services/userProfiles.js";
import { classifyMoodAndIntent } from "./src/services/classifier.js";
import { buildSystemPrompt } from "./src/services/promptBuilder.js";

console.log("=== Testing AIhub Workflow Implementation ===\n");

// 1. Test database connection and user_profiles table
console.log("1. Testing database and user_profiles table...");
try {
  const tables = db.prepare("SELECT name FROM sqlite_master WHERE type='table' AND name='user_profiles'").all();
  if (tables.length > 0) {
    console.log("✓ user_profiles table exists");
  } else {
    console.log("✗ user_profiles table NOT found");
  }
} catch (err) {
  console.log("✗ Database error:", err.message);
}

// 2. Test user profile creation
console.log("\n2. Testing user profile service...");
try {
  const profile = getOrCreateUserProfile("test-user-123", "TestUser");
  console.log("✓ Created/retrieved user profile:", {
    user_id: profile.user_id,
    username: profile.username,
    tone_preference: profile.tone_preference,
    current_mood: profile.current_mood
  });

  // Update profile
  upsertUserProfile(profile.user_id, {
    favorite_genres: ["hip-hop", "electronic"],
    favorite_artists: ["Deftones", "Run The Jewels"],
    notes: "Test user for workflow validation"
  });
  console.log("✓ Updated user profile with favorites");
} catch (err) {
  console.log("✗ User profile error:", err.message);
}

// 3. Test mood and intent classifier
console.log("\n3. Testing mood and intent classifier...");
const testMessages = [
  "This bot sucks!",
  "I love this song!",
  "Can you recommend some music?",
  "How are you built?",
  "Hello"
];

testMessages.forEach(msg => {
  const { mood, intent } = classifyMoodAndIntent(msg);
  console.log(`✓ "${msg}" → mood: ${mood}, intent: ${intent}`);
});

// 4. Test system prompt builder
console.log("\n4. Testing system prompt builder...");
try {
  const profile = getOrCreateUserProfile("test-user-123", "TestUser");
  const systemPrompt = buildSystemPrompt({
    userProfile: profile,
    userMood: "positive",
    metadata: {
      room_id: "test-room-123",
      room_source: "hangfm",
      username: "TestUser",
      user_id: "test-user-123",
      now_playing: {
        artist: "Deftones",
        title: "Change",
        album: "White Pony",
        year: 2000
      },
      stage: ["dj1", "dj2"],
      dancefloor: ["user1", "user2", "user3"],
      last_event: "song_started"
    }
  });

  if (systemPrompt.includes("central brain")) {
    console.log("✓ System prompt includes BASE_BEHAVIOR_PROMPT");
  }
  if (systemPrompt.includes("Deftones")) {
    console.log("✓ System prompt includes now_playing info");
  }
  if (systemPrompt.includes("hip-hop")) {
    console.log("✓ System prompt includes user favorites");
  }
  if (systemPrompt.includes("positive")) {
    console.log("✓ System prompt includes mood");
  }

  console.log("\nSample system prompt (first 500 chars):");
  console.log(systemPrompt.substring(0, 500) + "...\n");
} catch (err) {
  console.log("✗ System prompt error:", err.message);
}

console.log("=== Test Complete ===");
console.log("\nNext steps:");
console.log("1. Start AIhub: npm start");
console.log("2. Start python_ai service: npm run python-ai (in another terminal)");
console.log("3. Set active model: use CLI command 'select' or POST to /hub/chat with modelId");
console.log("4. Test /hub/chat endpoint with a bot or curl\n");

process.exit(0);
