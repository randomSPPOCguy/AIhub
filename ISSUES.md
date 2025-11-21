# Project Frank - Known Issues & Improvements

## 🔴 Critical Issues

### 1. AI Says "From the information I'm given"
**Problem:** AI hedges and doesn't act like it has current data
**Impact:** Makes responses feel uncertain even though enrichment data is current
**Status:** IN PROGRESS
**Fix:** Updated enrichment prompt instructions to be more authoritative
**Files affected:**
- `src/routes/chatRouter.js` (lines 523-533)
- `src/services/promptBuilder.js` (line 22)

### 2. Response Time Too Slow (11 seconds)
**Problem:** ONNX model inference takes 11 seconds
**Target:** 1-3 seconds
**Status:** ARCHITECTURE DECISION NEEDED
**Options:**
- Switch to cloud API (OpenAI/Anthropic) - hits 1-3s target
- Use smaller local model - achieves 3-5s
- Keep current setup - accept 11s responses

**See:** `PERFORMANCE_OPTIONS.md` for detailed analysis

### 3. Enrichment Cache Not Persistent
**Problem:** Cache is in-memory, lost on restart
**Impact:** Every restart requires re-fetching all Wikipedia/MusicBrainz data
**Status:** PLANNED
**Fix:** Implement SQLite-backed enrichment cache
**Expected improvement:** 1.5s → <100ms for cached entries

---

## 🟡 High Priority Issues

### 4. Limited Album Information
**Problem:** Only getting album name and year, missing:
- Production details
- Critical reception
- Chart performance
- Track listings with details
- Genre descriptions

**Status:** PARTIALLY FIXED
**Progress:**
- ✅ Created `wikipedia_full_content.py` to fetch full articles
- ✅ Updated orchestrator to use full content
- ⏳ Need to add Wikidata integration for related entities

**Next steps:**
- Fetch album Wikidata entity
- Get all track listings from Wikidata
- Get genre entities and descriptions
- Cache all related data in SQLite

### 5. Missing Wikidata Integration
**Problem:** Only using Wikipedia text, not structured Wikidata
**Impact:** Missing rich metadata like:
- Spotify IDs
- Apple Music IDs
- AllMusic IDs
- ISRC codes
- Release dates across regions
- Award information
- Genre hierarchies

**Status:** PLANNED
**Dependencies:** Need to add Wikidata SPARQL queries

### 6. No Proactive Information Sharing
**Problem:** AI only answers what's asked, doesn't volunteer interesting facts
**Impact:** Responses feel minimal
**Status:** IN PROGRESS
**Fix:** Updated prompts to be more proactive and informative

---

## 🟢 Medium Priority Issues

### 7. Conversation Context Limited
**Problem:** 13-second timeout is aggressive
**Impact:** Follow-up questions lose context quickly
**Status:** IMPLEMENTED
**Note:** May need to adjust timeout based on user feedback

### 8. Enrichment Service Startup Time
**Problem:** First query after startup times out (2s timeout too short)
**Impact:** First user query fails, enrichment disabled for 15s
**Status:** FIXED
**Fix:** Increased timeout from 2s to 5s in config.env

### 9. Album Article Fetching Not Automatic
**Problem:** When asking about an artist's album, only artist article is fetched
**Need:** Automatically fetch related album articles
**Status:** PLANNED
**Implementation:** Use Wikidata relations to find album entities

---

## 🔵 Low Priority / Enhancement Ideas

### 10. No Genre Article Content
**Problem:** Genre facts are minimal (just categories)
**Enhancement:** Fetch and parse genre Wikipedia articles for rich context

### 11. No Streaming Responses
**Problem:** User waits 11 seconds with no feedback
**Enhancement:** Stream AI responses as they generate (makes it feel faster)

### 12. No Response Variation
**Problem:** Same facts returned every time for same query
**Enhancement:** Rotate through different facts for variety

### 13. Limited Entity Linking
**Problem:** Can't follow references (e.g., "tell me about that producer")
**Enhancement:** Track mentioned entities in conversation

---

## 🛠️ Technical Debt

### 14. Enrichment Cache Key Conflicts
**Problem:** Cache keys might conflict between artists/albums with same name
**Fix needed:** Include entity type in cache key

### 15. No Enrichment Data Validation
**Problem:** Malformed Wikipedia responses could crash the service
**Fix needed:** Add schema validation for Wikipedia/MusicBrainz responses

### 16. Hardcoded Timeouts
**Problem:** Timeouts spread across multiple files
**Fix needed:** Centralize configuration

---

## 📊 Performance Metrics

### Current Performance:
- Enrichment (uncached): 1.5s ✅
- Enrichment (cached): ~50ms in-memory ⚠️ (lost on restart)
- Model inference: 11s ❌
- **Total response time:** ~12.5s

### Target Performance:
- Enrichment (cached): <100ms ⏳
- Enrichment (uncached): <2s ✅
- Model inference: 1-3s ❌ (requires cloud API)
- **Target total:** 1-3s

### Blockers to Target:
- ONNX model is inherently slow (11s)
- Must switch to cloud API or accept slower responses

---

## 🔧 Proposed Fixes (Priority Order)

1. **Add SQLite enrichment cache** (biggest impact for cached queries)
2. **Integrate Wikidata for comprehensive data** (richer responses)
3. **Fix AI prompts** (better tone, no hedging)
4. **Decide on model strategy** (cloud API vs local)
5. **Add album/track/genre article fetching** (more context)
6. **Implement response streaming** (better UX even if slow)

---

## 📝 Notes

- Project Frank aims to use best language for each feature
- Current stack (Node.js + Python + SQLite) is well-suited
- Main bottleneck is model inference speed, not architecture
- Enrichment service performance is GOOD (1.5s uncached)

---

**Last Updated:** 2025-11-20
**Next Review:** After implementing SQLite cache and Wikidata integration
